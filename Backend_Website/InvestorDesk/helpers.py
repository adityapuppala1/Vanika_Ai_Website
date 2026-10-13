# investorDesk/helpers.py
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Dict
from urllib.parse import quote
import jwt
from azure.communication.email import EmailClient
from azure.storage.blob import generate_blob_sas, BlobSasPermissions

from .config import (
    settings,
    investors_profiles,
    azure_blob_service_client,
    azure_container_name,
)

from Anvi_Mailing.helpers import send_email
from Email_Templates.email_templates import anvi_investor_desk_sendOtp, anvi_investor_desk_loggedin_admin, anvi_investor_desk_loggedin_client

# -------------------------------------------------------
# OTP / Token generators
# ---------------------------
def generate_otp(length: int = None) -> str:
    length = length or settings.OTP_LENGTH
    digits = string.digits
    return "".join(secrets.choice(digits) for _ in range(length))


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def generate_jwt(payload: dict, expires_seconds: Optional[int] = None) -> str:
    to_encode = payload.copy()
    exp_seconds = expires_seconds or settings.JWT_EXPIRES_SECONDS
    to_encode.update({"exp": datetime.utcnow() + timedelta(seconds=exp_seconds)})
    token = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token


# ------------------------------------------------------------
# Send OTP using Azure Communication Services (ACS)
# ------------------------------------------------------------
def send_otp_via_acs(to_email: str, otp: str) -> None:
    """
    Sends OTP email using Azure Communication Services Email.
    """
    # print("Sending OTP via ACS to:", settings.EMAIL_FOR_INVESTORDESK, "->", to_email)
    # print("OTP is:", otp)
    # print("ACS Connection String:", settings.AZURE_COMMUNICATION_CONNECTION_STRING)
    if not settings.AZURE_COMMUNICATION_CONNECTION_STRING or not settings.EMAIL_FOR_INVESTORDESK:
        raise RuntimeError("Azure Email not configured (missing ACS connection string or sender)")

    client = EmailClient.from_connection_string(settings.AZURE_COMMUNICATION_CONNECTION_STRING)
    # print("EmailClient created:", client)
    subject = "Your Anvi-InvestorDesk Login OTP"
    
    class EmailInfo:
        def __init__(self):
            self.otp = otp
            self.OTP_TTL_SECONDS = settings.OTP_TTL_SECONDS
            self.Website = 'Anvi.co'
    
    info = EmailInfo()
    # print("info : ", info)
    
    html_body = anvi_investor_desk_sendOtp(info)

    message = {
        "senderAddress": settings.EMAIL_FOR_INVESTORDESK,
        "recipients": {
            "to": [{"address": to_email}]
        },
        "content": {
            "subject": subject,
            "html": html_body
        }
    }

    try:
        send_poller = client.begin_send(message)
        result = send_poller.result()
        print("[ACS EMAIL] Sent OTP ", otp,"→ Message ID:", result.get("messageId"))
    except Exception as e:
        print("[ACS EMAIL ERROR]", str(e))
        raise RuntimeError("OTP_EMAIL_FAILED")

# -------------------------------------------------------
# Create OTP for investor
async def create_otp_for_investor(email: str) -> Dict:
    """
    Generate OTP + session token, save in DB, send OTP email.
    Returns session_token + expiry (OTP returned only for DEV).
    """
    otp = generate_otp()
    session_token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(seconds=settings.OTP_TTL_SECONDS)

    result = await investors_profiles.update_one(
        {"investor_emailid": email},
        {
            "$set": {
                "investor_login_otp": otp,
                "investor_session_token": session_token,
                "otp_expires_at": expires_at,
            }
        },
    )

    if result.matched_count == 0:
        raise ValueError("email_not_found")

    # Send OTP using Azure Communication Services
    try:
        send_otp_via_acs(email, otp)
    except Exception:
        # cleanup OTP if sending failed
        await investors_profiles.update_one(
            {"investor_emailid": email},
            {"$unset": {"investor_login_otp": "", "investor_session_token": "", "otp_expires_at": ""}}
        )
        raise RuntimeError("OTP_SEND_FAILED")

    return {"session_token": session_token, "expires_at": expires_at, "otp": otp}  # include otp for dev only

# -------------------------------------------------------
# Verify OTP and create login JWT
async def verify_otp_and_create_login(email: str, otp: str, session_token: str) -> str:
    """
    Validate OTP + session + expiry.
    On success → generate JWT, clear OTP/session fields, return login token.
    """
    # print("email, otp, session_token :", email, otp, session_token)

    doc = await investors_profiles.find_one({"investor_emailid": email})
    if not doc:
        raise ValueError("email_not_found")

    stored_otp = doc.get("investor_login_otp")
    stored_session = doc.get("investor_session_token")
    expires_at = doc.get("otp_expires_at")

    if not (stored_otp and stored_session and expires_at):
        raise ValueError("no_otp_session")

    # Handle whitespace
    session_token = session_token.strip()
    if isinstance(stored_session, str):
        stored_session = stored_session.strip()

    if stored_session != session_token:
        raise ValueError("invalid_session")

    if datetime.utcnow() > expires_at:
        raise ValueError("otp_expired")

    if stored_otp != otp:
        raise ValueError("invalid_otp")

    # Build JWT payload
    payload = {"email": email, "id": str(doc.get("_id"))}
    jwt_token = generate_jwt(payload)

    # 1. Update DB — save login token and clear OTP/session
    await investors_profiles.update_one(
        {"investor_emailid": email},
        {
            "$set": {"investor_login_token": jwt_token},
            "$unset": {
                "investor_login_otp": "",
                "investor_session_token": "",
                "otp_expires_at": "",
            },
        },
    )
    
    # 2. TRIGGER NOTIFICATIONS
    try:
        # Fetch website from doc to determine correct branding/logo
        # Defaulting to 'anvirobotics' if not found

        class EmailInfo:
            def __init__(self):
                self.email = email
                self.Website = 'Anvi.co'
                self.login_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        info = EmailInfo()

        # A. Notification to the Client (The one logging in)
        client_content = anvi_investor_desk_loggedin_client(info)
        await send_email(
            subject="Successful Login - Anvi Investor",
            html=client_content,
            to=email,
            onlySender=True,
            investorDesk=True,
        )

        # B. Notification to Admin
        # Since send_email handles Email_Fallback_Dev as BCC, 
        # passing 'onlySender=False' will notify your fallback admin.
        admin_content = anvi_investor_desk_loggedin_admin(info)
        await send_email(
            subject=f"Anvi Admin : Investor Login - {email}",
            html=admin_content,
            onlySender=True,
            investorDesk=True,
        )

    except Exception as e:
        print(f"Non-critical Error: Notification failed: {str(e)}")

    return jwt_token


# -------------------------------------------------------
# Helper: Generate SAS URL for a blob (private read-only)
# -------------------------------------------------------
def generate_private_sas(blob_name: str) -> str:
    # 1. Check if the service client is available (good practice from your original code)
    #    You'd need to define or import 'azure_blob_service_client' for this check to work.
    if not azure_blob_service_client:
        return None
    
    # Assuming config variables are available here
    from .config import AZURE_ACCOUNT_KEY, AZURE_ACCOUNT_NAME

    # URL-encode the blob name for safe inclusion in the final URL path
    encoded_blob_name = quote(blob_name) 

    # Define the expiry time (1 hour from now)
    expiry_time = datetime.utcnow() + timedelta(hours=1)
    
    # Note: Adding a 'start' time (e.g., 15 minutes ago) is highly recommended
    # to avoid clock skew issues, which may have caused your previous failure.
    start_time = datetime.utcnow() - timedelta(minutes=15)

    # 2. Generate the SAS Token
    # This is the Python equivalent of generateBlobSASQueryParameters()
    # print("AZURE_ACCOUNT_KEY : ", AZURE_ACCOUNT_KEY)
    try:
        sas_token = generate_blob_sas(
            account_name=AZURE_ACCOUNT_NAME,
            account_key=AZURE_ACCOUNT_KEY,
            container_name=azure_container_name,
            blob_name=blob_name, # SDK function expects the *unencoded* blob name
            permission=BlobSasPermissions(read=True), # Equivalent to BlobSASPermissions.parse("r")
            start=start_time,
            expiry=expiry_time
        )
    except Exception as e:
        # print(f"Error generating SAS: {e}")
        return None

    # 3. Construct and return the full secure URL
    # Format: https://{account}.blob.core.windows.net/{container}/{encoded_blob}?{sas_token}
    final_url = f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net/{azure_container_name}/{encoded_blob_name}?{sas_token}"
    
    # print(f"Generated SAS URL: {final_url}")
    # print(f"Token expires: {expiry_time} UTC")
    
    return final_url