# Vanika_Mailing/routes.py
import csv
import io
import secrets
from typing import Optional

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Request
# pyrefly: ignore [missing-import]
from fastapi.responses import JSONResponse, StreamingResponse
# pyrefly: ignore [missing-import]
from pydantic import EmailStr, TypeAdapter, ValidationError
# pyrefly: ignore [missing-import]
from pymongo.errors import PyMongoError

from config import settings, get_vanika_db
from Vanika_Mailing.helpers import send_email
from Vanika_Mailing.email_templates import vanika_subscribe_admin, vanika_subscribe_user
from Vanika_Mailing.security import client_ip, require_admin, subscribe_limiter
from Vanika_Mailing.waitlist import WaitlistRepository

router = APIRouter()

_email_adapter = TypeAdapter(EmailStr)
CSV_COLUMNS = [
    "email", "createdAt", "lastSignupAt", "firstSource", "sources", "signupCount",
    "status", "referrer", "utmSource", "utmMedium", "utmCampaign",
]


_indexes_ready = False


async def ensure_waitlist_indexes(waitlist: WaitlistRepository) -> bool:
    """Create the waitlist indexes once per process; retried until it succeeds.

    The unique email index is what prevents duplicate rows when two first
    sign-ups for the same address race, so it must not be skipped just because
    Atlas was unreachable at startup.
    """
    global _indexes_ready
    if _indexes_ready:
        return True
    try:
        await waitlist.ensure_indexes()
        _indexes_ready = True
        print("[Vanika] [OK] Waitlist indexes ensured.")
    except PyMongoError as e:
        print(f"[Vanika] [FAIL] Could not ensure waitlist indexes (will retry): {e}")
    return _indexes_ready


def get_waitlist() -> Optional[WaitlistRepository]:
    db = get_vanika_db()
    if db is None:
        return None
    return WaitlistRepository(db[settings.VANIKA_WAITLIST_COLLECTION])


def _failed(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"status": "Failed", "code": code, "message": message})


def _clean(value: Optional[str], max_len: int = 200) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value[:max_len] or None


def _normalize_email(raw: str) -> Optional[str]:
    try:
        return str(_email_adapter.validate_python(raw.strip())).lower()
    except ValidationError:
        return None


@router.get("/ping")
async def ping():
    return {"status": "Vanika_Mailing router is working!"}


# ---------------------------------------------------------
# Public: waitlist sign-up
# ---------------------------------------------------------
@router.post("/subscribe")
async def subscribe(
    request: Request,
    background_tasks: BackgroundTasks,
    clientemail: str = Form(...),
    accesskey: str = Form(""),
    source: str = Form("unknown"),
    website: str = Form(""),  # honeypot — humans never see or fill it
    referrer: Optional[str] = Form(None),
    utm_source: Optional[str] = Form(None),
    utm_medium: Optional[str] = Form(None),
    utm_campaign: Optional[str] = Form(None),
    waitlist: Optional[WaitlistRepository] = Depends(get_waitlist),
):
    if not subscribe_limiter.allow(client_ip(request)):
        return _failed(429, "RATE_LIMITED", "Too many attempts. Please wait a minute and try again.")

    if settings.VANIKA_ROUTES_KEY and not secrets.compare_digest(
        accesskey.encode(), settings.VANIKA_ROUTES_KEY.encode()
    ):
        return _failed(403, "INVALID_ACCESS_KEY", "Invalid Access Key")

    if website.strip():
        # Pretend success so bots don't learn they were caught
        print("[Vanika] Honeypot triggered — sign-up ignored")
        return {"status": "Success", "message": "You're on the list.", "alreadySubscribed": False}

    email = _normalize_email(clientemail)
    if email is None:
        return _failed(422, "INVALID_EMAIL", "Please enter a valid email address.")

    source = _clean(source, 40) or "unknown"
    metadata = {
        "referrer": _clean(referrer, 500),
        "utm_source": _clean(utm_source),
        "utm_medium": _clean(utm_medium),
        "utm_campaign": _clean(utm_campaign),
        "user_agent": _clean(request.headers.get("user-agent"), 300),
    }
    metadata = {k: v for k, v in metadata.items() if v}

    stored = False
    is_new = True
    if waitlist is None:
        print("[Vanika] [WARN] MongoDB not configured — sign-up NOT stored, sending emails only")
    else:
        try:
            await ensure_waitlist_indexes(waitlist)
            result = await waitlist.add_signup(email, source, metadata)
            stored, is_new = True, result.is_new
        except PyMongoError as e:
            print(f"[Vanika] [FAIL] Could not store sign-up: {e}")

    if is_new:
        # Respond immediately; the emails go out after the response is sent.
        background_tasks.add_task(_send_signup_emails, waitlist if stored else None, email, source, stored)
        print(f"[Vanika] New waitlist sign-up via {source} (stored={stored})")
        return {"status": "Success", "message": "You're on the list.", "alreadySubscribed": False}

    return {"status": "Success", "message": "You're already on the list.", "alreadySubscribed": True}


async def _send_signup_emails(
    waitlist: Optional[WaitlistRepository], email: str, source: str, stored: bool
) -> None:
    total = None
    if waitlist is not None:
        try:
            total = await waitlist.collection.count_documents({})
        except PyMongoError:
            pass

    admin_result = await send_email(
        subject=f"Vanika.ai - New waitlist sign-up: {email}",
        html=vanika_subscribe_admin(email, source=source, total=total, stored=stored),
    )
    # Confirmation to the subscriber only — no dev BCC
    user_result = await send_email(
        subject="You're on the Vanika.ai waitlist",
        html=vanika_subscribe_user(),
        to=email,
        onlySender=True,
    )

    if waitlist is not None:
        errors = [r.get("message", "") for r in (admin_result, user_result) if r.get("status") != "success"]
        try:
            await waitlist.set_email_status(
                email,
                admin="sent" if admin_result.get("status") == "success" else "failed",
                user="sent" if user_result.get("status") == "success" else "failed",
                error="; ".join(errors) or None,
            )
        except PyMongoError as e:
            print(f"[Vanika] [FAIL] Could not record email status: {e}")


# ---------------------------------------------------------
# Admin: waitlist dashboard API (X-Admin-Key header)
# ---------------------------------------------------------
def _require_storage(waitlist: Optional[WaitlistRepository]) -> WaitlistRepository:
    if waitlist is None:
        raise HTTPException(status_code=503, detail="STORAGE_UNAVAILABLE: set MONGODB_URI on the server")
    return waitlist


def _csv_safe(value) -> str:
    text = ", ".join(value) if isinstance(value, list) else ("" if value is None else str(value))
    # Stop spreadsheet apps from evaluating cells as formulas
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


@router.get("/admin/stats", dependencies=[Depends(require_admin)])
async def admin_stats(waitlist: Optional[WaitlistRepository] = Depends(get_waitlist)):
    repo = _require_storage(waitlist)
    try:
        stats = await repo.stats()
    except PyMongoError as e:
        raise HTTPException(status_code=503, detail=f"DATABASE_ERROR: {e}")
    return {**stats, "collection": settings.VANIKA_WAITLIST_COLLECTION}


@router.get("/admin/subscribers", dependencies=[Depends(require_admin)])
async def admin_subscribers(
    search: Optional[str] = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    waitlist: Optional[WaitlistRepository] = Depends(get_waitlist),
):
    repo = _require_storage(waitlist)
    try:
        return await repo.list_subscribers(search, limit, offset)
    except PyMongoError as e:
        raise HTTPException(status_code=503, detail=f"DATABASE_ERROR: {e}")


@router.get("/admin/subscribers/export.csv", dependencies=[Depends(require_admin)])
async def admin_export_csv(waitlist: Optional[WaitlistRepository] = Depends(get_waitlist)):
    repo = _require_storage(waitlist)
    try:
        rows = await repo.all_subscribers()
    except PyMongoError as e:
        raise HTTPException(status_code=503, detail=f"DATABASE_ERROR: {e}")

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerow([_csv_safe(row.get(col)) for col in CSV_COLUMNS])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="vanika-waitlist.csv"'},
    )


@router.delete("/admin/subscribers/{email:path}", dependencies=[Depends(require_admin)])
async def admin_delete_subscriber(email: str, waitlist: Optional[WaitlistRepository] = Depends(get_waitlist)):
    repo = _require_storage(waitlist)
    try:
        deleted = await repo.delete(email.strip().lower())
    except PyMongoError as e:
        raise HTTPException(status_code=503, detail=f"DATABASE_ERROR: {e}")
    if not deleted:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return {"status": "Success", "deleted": email}
