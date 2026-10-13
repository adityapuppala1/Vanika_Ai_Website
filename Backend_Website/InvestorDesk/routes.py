# investorDesk/routes.py
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr

from .helpers import create_otp_for_investor, verify_otp_and_create_login, generate_private_sas
from .config import investors_profiles, investors_content, settings

router = APIRouter()

# --------------------------
# Models
# --------------------------
class SendMailRequest(BaseModel):
    email: EmailStr


class SendMailResponse(BaseModel):
    status: str
    sessionToken: str
    email: EmailStr


class VerifyMailRequest(BaseModel):
    email: EmailStr
    otp: str
    sessionToken: str


class VerifyMailResponse(BaseModel):
    status: str
    token: str

class ContentRequest(BaseModel):
    loginToken: str

# Testing Route
@router.get("/ping")
async def test_route():
    return {"status": "InvestorDesk router is working!"}


# --------------------------
# POST Send Mail Route
# --------------------------
@router.post("/sending_mail", response_model=SendMailResponse)
async def sending_mail(req: SendMailRequest, background_tasks: BackgroundTasks):
    """
    1) Ensure investor exists
    2) Create OTP + session token saved to db
    3) Send OTP email in background
    4) Return session token to frontend
    """
    doc = await investors_profiles.find_one({"investor_emailid": req.email})
    if not doc:
        raise HTTPException(status_code=404, detail="EMAIL_NOT_FOUND")

    # print("Creating OTP for:", req.email)
    # print("Investor record:", doc)
    # print("Settings in sending_mail:", settings.AZURE_COMMUNICATION_CONNECTION_STRING, settings.EMAIL_FOR_INVESTORDESK)
    try:
        # create_otp_for_investor will send email (and may raise on send-failure)
        otp_entry = await create_otp_for_investor(req.email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Generic send failure
        raise HTTPException(status_code=500, detail="OTP_SEND_FAILED")

    # NOTE: create_otp_for_investor already sent OTP via SendGrid synchronously.
    # If you prefer to send in background, you can modify create_otp_for_investor to NOT send and
    # instead schedule send_otp_via_sendgrid via background_tasks.add_task(...).
    print("OTP sent successfully to", req.email, otp_entry["session_token"])
    return SendMailResponse(status="OTP_SENT", sessionToken=otp_entry["session_token"], email=req.email)


# --------------------------
# POST Verify Mail Route
# --------------------------
@router.post("/verifying_mail", response_model=VerifyMailResponse)
async def verifying_mail(req: VerifyMailRequest):

    """
    Verify OTP + session token. On success return JWT token.   
    """
    try:
        jwt_token = await verify_otp_and_create_login(req.email, req.otp, req.sessionToken)
        # print("JWT generated for =============== ", req.email, req.otp, req.sessionToken)
    except ValueError as e:
        msg = str(e)
        if msg == "email_not_found":
            raise HTTPException(status_code=404, detail=msg)
        elif msg in ("no_otp_session", "invalid_session", "invalid_otp", "otp_expired"):
            raise HTTPException(status_code=401, detail=msg)
        else:
            raise HTTPException(status_code=400, detail=msg)
    except Exception:
        raise HTTPException(status_code=500, detail="INTERNAL_ERROR")

    # print("jwt_token : ", jwt_token)
    return VerifyMailResponse(status="LOGIN_SUCCESS", token=jwt_token)


# -------------------------------------------------------
# POST Investors Content Route 
# -------------------------------------------------------
@router.post("/content")
async def get_investors_content(req: ContentRequest):

    loginToken = req.loginToken

    # print("Received content fetch request with loginToken:", loginToken)
    # 1️⃣ Validate token
    investor = await investors_profiles.find_one({"investor_login_token": loginToken})
    # print("Investor fetched from token:", investor)
    if not investor:
        raise HTTPException(status_code=401, detail="INVALID_LOGIN_TOKEN")

    investor_sector = investor.get("investor_sector")
    if not investor_sector or not isinstance(investor_sector, list):
        raise HTTPException(status_code=400, detail="SECTOR_NOT_FOUND")

    # Convert all to lowercase for case-insensitive matching
    investor_sector = [s.lower() for s in investor_sector]

    # Debug: sample docs
    sample_docs = await investors_content.find({}).to_list(3)
    # print("Sample InvestorsContent docs:", sample_docs)

    # 2️⃣ Fetch content for ANY matching sector
    cursor = investors_content.find({
        "investor_sector": {"$in": investor_sector}
    })

    results = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])

        blob_name = doc.get("investor_filepath") or ""

        # 3️⃣ Generate SAS URL
        if blob_name:
            doc["investor_file_url"] = generate_private_sas(blob_name)
        else:
            doc["investor_file_url"] = None

        results.append(doc)

    return {
        "status": "SUCCESS",
        "investor_sectors": investor_sector,
        "count": len(results),
        "investor_profile": {
            "investor_name": investor.get("investor_name"),
            "investor_emailid": investor.get("investor_emailid"),
        },
        "investor_data": results
    }