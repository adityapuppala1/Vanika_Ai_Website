# config.py
from datetime import datetime
import os
from typing import Optional
from pydantic_settings import BaseSettings

# Optional Azure import
try:
    from azure.storage.blob import BlobServiceClient
except Exception:
    BlobServiceClient = None  # Azure SDK not installed, safe fallback


# =========================================================
# Settings using Pydantic BaseSettings
# =========================================================
class Settings(BaseSettings):
    # CORS
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    # Vanika Routes Access Key (shipped in the public frontend bundle — a light
    # filter, not a secret)
    VANIKA_ROUTES_KEY: str = os.getenv("VANIKA_ROUTES_KEY", "")

    # Vanika waitlist
    # Admin dashboard key (keep private; admin endpoints are disabled when empty)
    VANIKA_ADMIN_KEY: str = os.getenv("VANIKA_ADMIN_KEY", "")
    # Database for Vanika data; defaults to MONGODB_DB_NAME when empty
    VANIKA_DB_NAME: str = os.getenv("VANIKA_DB_NAME", "")
    VANIKA_WAITLIST_COLLECTION: str = os.getenv("VANIKA_WAITLIST_COLLECTION", "VanikaWaitlist")
    # Max subscribe attempts per client IP per minute
    VANIKA_SUBSCRIBE_RATE_LIMIT: int = int(os.getenv("VANIKA_SUBSCRIBE_RATE_LIMIT", 5))
    # 32-byte base64 key for AES-256-GCM field encryption of stored emails (required for storage)
    VANIKA_ENCRYPTION_KEY: str = os.getenv("VANIKA_ENCRYPTION_KEY", "")
    # "standard" (work, school, well-known personal providers) or "work_or_school"
    VANIKA_EMAIL_POLICY: str = os.getenv("VANIKA_EMAIL_POLICY", "standard")
    # Reject domains without MX records (DNS lookup per new domain, cached)
    VANIKA_EMAIL_DNS_CHECK: bool = os.getenv("VANIKA_EMAIL_DNS_CHECK", "true").lower() == "true"
    # Cloudflare Turnstile bot check (optional; enabled when set)
    TURNSTILE_SECRET_KEY: str = os.getenv("TURNSTILE_SECRET_KEY", "")

    # Vanika mail (Microsoft 365 mailbox)
    VANIKA_MAIL_FROM: str = os.getenv("VANIKA_MAIL_FROM", "info@vanika.ai")
    VANIKA_MAIL_FROM_NAME: str = os.getenv("VANIKA_MAIL_FROM_NAME", "Vanika.AI")
    # Receives new sign-up notifications and replies to the welcome email
    VANIKA_TEAM_INBOX: str = os.getenv("VANIKA_TEAM_INBOX", "info@vanika.ai")
    # auto | graph | smtp | acs
    VANIKA_MAIL_TRANSPORT: str = os.getenv("VANIKA_MAIL_TRANSPORT", "auto")
    # Microsoft Graph (recommended): Entra ID app with Mail.Send application permission
    GRAPH_TENANT_ID: str = os.getenv("GRAPH_TENANT_ID", "")
    GRAPH_CLIENT_ID: str = os.getenv("GRAPH_CLIENT_ID", "")
    GRAPH_CLIENT_SECRET: str = os.getenv("GRAPH_CLIENT_SECRET", "")
    # SMTP (bridge until Microsoft disables basic auth, end of Dec 2026)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.office365.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_SECURITY: str = os.getenv("SMTP_SECURITY", "starttls")  # starttls | ssl
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    # MongoDB Atlas
    MONGODB_URI: str = os.getenv("MONGODB_URI", "")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "investor_db")
    
    # Azure Communication Services
    AZURE_COMMUNICATION_CONNECTION_STRING: str = os.getenv("AZURE_COMMUNICATION_CONNECTION_STRING", "")

    # Email Addresses
    EMAIL_FOR_INVESTORDESK: str = os.getenv("EMAIL_FOR_INVESTORDESK", "")
    EMAIL_PRIMARY_ANVI: str = os.getenv("EMAIL_PRIMARY_ANVI", "")
    EMAIL_PRIMARY_BOTFACTORY: str = os.getenv("EMAIL_PRIMARY_BOTFACTORY", "")
    EMAIL_PRIMARY_VANIKA: str = os.getenv("EMAIL_PRIMARY_VANIKA", "")
    EMAIL_BCC_FALLBACK_1: str = os.getenv("EMAIL_BCC_FALLBACK_1", "")
    EMAIL_BCC_FALLBACK_2: str = os.getenv("EMAIL_BCC_FALLBACK_2", "")

    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "super-secret-jwt-key")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRES_SECONDS: int = int(os.getenv("JWT_EXPIRES_SECONDS", 60 * 60 * 24))

    # OTP
    OTP_TTL_SECONDS: int = int(os.getenv("OTP_TTL_SECONDS", 300))
    OTP_LENGTH: int = int(os.getenv("OTP_LENGTH", 6))

    # Azure Blob Storage
    AZURE_CONNECTION_STRING: Optional[str] = os.getenv("AZURE_CONNECTION_STRING", None)
    AZURE_CONTAINER_NAME: Optional[str] = os.getenv("AZURE_CONTAINER_NAME", None)
    STORAGE_PATH_URL: str = os.getenv("STORAGE_PATH_URL", "")

    # Allow extra environment variables & read .env
    model_config = {
        "extra": "allow",
        "env_file": ".env"
    }


# Instantiate settings
settings = Settings()

if settings.JWT_SECRET in ("", "super-secret-jwt-key"):
    print("[Config] [WARN] JWT_SECRET is empty or the insecure default. Set a strong value in the environment.")


# =========================================================
# MongoDB Connection Setup + DEV-LOGGING
# =========================================================
_mongo_client = None
_db = None

if settings.MONGODB_URI:
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        _mongo_client = AsyncIOMotorClient(settings.MONGODB_URI)
        _db = _mongo_client[settings.MONGODB_DB_NAME]
        print(f"[MongoDB] [OK] Connected to database: {settings.MONGODB_DB_NAME}")
    except Exception as e:
        print(f"[MongoDB] [FAIL] Connection FAILED: {e}")
        _db = None

# Collections (MUST NOT use truthiness)
investors_profiles = _db.get_collection("InvestorsProfiles") if _db is not None else None
investors_content = _db.get_collection("InvestorsContent") if _db is not None else None


def get_vanika_db():
    """Database holding Vanika data, or None when MongoDB is not configured."""
    if _mongo_client is None:
        return None
    if settings.VANIKA_DB_NAME:
        return _mongo_client[settings.VANIKA_DB_NAME]
    return _db


async def print_mongo_collections():
    if _db is None:
        print("[MongoDB] No DB Connection")
        return

    try:
        collections = await _db.list_collection_names()
        print("[MongoDB] Collections:", collections)
    except Exception as e:
        print("[MongoDB] Error listing collections:", e)


async def setup_initial_schema():
    if _db is None:
        print("[MongoDB] No DB Connection — skipping schema setup")
        return

    # ----- InvestorsProfiles -----
    if investors_profiles is not None:
        count_profiles = await investors_profiles.count_documents({})
        if count_profiles == 0:
            print("[MongoDB] InvestorsProfiles empty — inserting default schema")

            sample_investor = [{
                "investor_name": "Avanikareddy Gyanaji",
                "investor_emailid": "avanikareddy16@gmail.com",
                "investor_sector": ["Robotics", "Textiles", "Space"],
                "investor_login_token": None,
                "investor_login_otp": None,
                "otp_expires_at": None,
                "investor_session_token": None
            },{
                "investor_name": "Praveen Dasari",
                "investor_emailid": "praveen.dasari@anvi.co",
                "investor_sector": ["Robotics", "Space"],
                "investor_login_token": None,
                "investor_login_otp": None,
                "otp_expires_at": None,
                "investor_session_token": None
            }]
            await investors_profiles.insert_many(sample_investor)

    # ----- InvestorsContent -----
    if investors_content is not None:
        count_content = await investors_content.count_documents({})
        if count_content == 0:
            print("[MongoDB] InvestorsContent empty — inserting sample content")

            sample_content = [{
                "investor_title": "Bot factory Testing",
                "investor_filepath": "Bot Factory 1.mp4",
                "investor_file_url": "",
                "investor_filetype": "video",
                "investor_sector": "robotics",
                "investor_description": "Watch our latest autonomous robots in action at a major manufacturing facility.",
                "investor_published_date": '',
                },
                {
                "investor_title": "Monthly Engineering Progress",
                "investor_filepath": "Updated_Newsletter_November.pdf",
                "investor_file_url": "",
                "investor_filetype": "pdf",
                "investor_sector": "robotics",
                "investor_description": "Anvi Robotics advanced engineering, completed field demos, and pushed prototypes closer to deployment-ready municipal pilot systems.",
                "investor_published_date": datetime(year=2025, month=11, day=1)
                }
            ]
            await investors_content.insert_many(sample_content) 


async def get_collection_data(coll_name: str):
    if _db is None:
        return {"error": "DB not connected"}

    try:
        collection = _db.get_collection(coll_name)
        cursor = collection.find({})
        items = await cursor.to_list(length=5000)
        print(f"[MongoDB] {coll_name} data:", items)
        return {"collection": coll_name, "count": len(items), "data": items}

    except Exception as e:
        return {"error": str(e)}


async def ensure_indexes() -> None:
    if _db is None or investors_profiles is None or investors_content is None:
        print("[MongoDB] [FAIL] Skipping index creation — DB not connected.")
        return

    try:
        await investors_profiles.create_index("investor_emailid", unique=True)
        await investors_profiles.create_index("otp_expires_at")
        await investors_content.create_index("investor_sector")
        await investors_content.create_index("investor_published_date")
        print("[MongoDB] [OK] Indexes ensured.")
    except Exception as e:
        print("[MongoDB] [FAIL] Index creation failed:", e)


# =========================================================
# Azure Blob Storage Setup + DEV-LOGGING
# =========================================================
azure_blob_service_client = None
azure_container_name = settings.AZURE_CONTAINER_NAME

if settings.AZURE_CONNECTION_STRING and BlobServiceClient is not None:
    try:
        azure_blob_service_client = BlobServiceClient.from_connection_string(
            settings.AZURE_CONNECTION_STRING
        )
        print(f"[Azure Blob] [OK] Connected to storage account container: {azure_container_name}")
    except Exception as e:
        print(f"[Azure Blob] [FAIL] Connection FAILED: {e}")
        azure_blob_service_client = None
else:
    print("[Azure Blob] [FAIL] Missing connection string OR azure-storage-blob not installed")


# =========================================================
# Utility: Parse Azure connection string into dict safely
# =========================================================
def parse_connection_string(conn: Optional[str]) -> dict:
    if not conn:
        return {}
    conn_dict = {}
    conn_str = conn.strip().strip('"').strip("'")
    for item in conn_str.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            conn_dict[k.strip()] = v.strip()
    return conn_dict


conn_info = parse_connection_string(settings.AZURE_CONNECTION_STRING)
AZURE_ACCOUNT_NAME = conn_info.get("AccountName")
AZURE_ACCOUNT_KEY = conn_info.get("AccountKey")


__all__ = [
    "settings",
    "investors_profiles",
    "investors_content",
    "get_vanika_db",
    "ensure_indexes",
    "azure_blob_service_client",
    "azure_container_name",
    "AZURE_ACCOUNT_NAME",
    "AZURE_ACCOUNT_KEY",
    "parse_connection_string",
    "setup_initial_schema",
    "print_mongo_collections",
    "get_collection_data"
]
