# Vanika_Mailing/mailer.py
"""Outbound email for Vanika (sender and team inbox: info@vanika.ai).

vanika.ai mail is hosted on Microsoft 365. Transports, picked by
VANIKA_MAIL_TRANSPORT (default "auto" = first one that is configured):

  graph  Microsoft Graph sendMail with an Entra ID app (client credentials).
         Microsoft's recommended path; not affected by the SMTP basic-auth retirement.
  smtp   smtp.office365.com:587 + STARTTLS with the mailbox username/password.
         Microsoft disables SMTP basic auth by default for existing tenants at the
         end of December 2026 — use only as a bridge.
  acs    Azure Communication Services (legacy; sender must be an ACS-verified domain).

All transports use TLS with certificate verification.
"""
import html as html_lib
import re
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Dict, List, Optional

# pyrefly: ignore [missing-import]
import httpx
# pyrefly: ignore [missing-import]
from starlette.concurrency import run_in_threadpool

from config import settings

GRAPH_SCOPE = "https://graph.microsoft.com/.default"
_token_cache: Dict[str, float] = {}
_token_value: Dict[str, str] = {}


def active_transport() -> str:
    choice = (settings.VANIKA_MAIL_TRANSPORT or "auto").lower()
    if choice != "auto":
        return choice
    if settings.GRAPH_TENANT_ID and settings.GRAPH_CLIENT_ID and settings.GRAPH_CLIENT_SECRET:
        return "graph"
    if settings.SMTP_PASSWORD:
        return "smtp"
    if settings.AZURE_COMMUNICATION_CONNECTION_STRING:
        return "acs"
    return "none"


_EMAIL_RE = re.compile(r"[^\s@<>'\"(){}\[\],;:]+@[^\s@<>'\"(){}\[\],;:]+")


def _redact(text: str) -> str:
    """Errors are logged and stored; keep subscriber addresses out of them."""
    return _EMAIL_RE.sub("<address>", text)


def _plain_text(html: str) -> str:
    text = re.sub(r"<(br|/p|/h[1-6]|/div)\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    return re.sub(r"\n\s*\n+", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


# ---------------------------------------------------------
# Microsoft Graph
# ---------------------------------------------------------
async def _graph_token(client: httpx.AsyncClient) -> str:
    if _token_value.get("graph") and _token_cache.get("graph", 0) > time.monotonic():
        return _token_value["graph"]
    response = await client.post(
        f"https://login.microsoftonline.com/{settings.GRAPH_TENANT_ID}/oauth2/v2.0/token",
        data={
            "client_id": settings.GRAPH_CLIENT_ID,
            "client_secret": settings.GRAPH_CLIENT_SECRET,
            "scope": GRAPH_SCOPE,
            "grant_type": "client_credentials",
        },
    )
    response.raise_for_status()
    body = response.json()
    _token_value["graph"] = body["access_token"]
    _token_cache["graph"] = time.monotonic() + int(body.get("expires_in", 3600)) - 120
    return body["access_token"]


async def _send_graph(to: List[str], subject: str, html: str, bcc: List[str], reply_to: str) -> None:
    message = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": html},
        "toRecipients": [{"emailAddress": {"address": a}} for a in to],
        "bccRecipients": [{"emailAddress": {"address": a}} for a in bcc],
        "replyTo": [{"emailAddress": {"address": reply_to}}],
    }
    async with httpx.AsyncClient(timeout=20) as client:
        token = await _graph_token(client)
        response = await client.post(
            f"https://graph.microsoft.com/v1.0/users/{settings.VANIKA_MAIL_FROM}/sendMail",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": message, "saveToSentItems": True},
        )
        if response.status_code != 202:
            raise RuntimeError(f"Graph sendMail {response.status_code}: {response.text[:300]}")


# ---------------------------------------------------------
# SMTP (Microsoft 365)
# ---------------------------------------------------------
def _send_smtp(to: List[str], subject: str, html: str, bcc: List[str], reply_to: str) -> None:
    msg = EmailMessage()
    msg["From"] = formataddr((settings.VANIKA_MAIL_FROM_NAME, settings.VANIKA_MAIL_FROM))
    msg["To"] = ", ".join(to)
    msg["Reply-To"] = reply_to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=settings.VANIKA_MAIL_FROM.split("@")[-1])
    msg.set_content(_plain_text(html))
    msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()  # verifies the server certificate
    username = settings.SMTP_USERNAME or settings.VANIKA_MAIL_FROM
    if settings.SMTP_SECURITY.lower() == "ssl":
        server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20, context=context)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20)
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
    try:
        server.login(username, settings.SMTP_PASSWORD)
        # Bcc goes in the envelope only, never in the headers
        server.send_message(msg, from_addr=settings.VANIKA_MAIL_FROM, to_addrs=to + bcc)
    finally:
        try:
            server.quit()
        except Exception:
            pass


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------
async def send_mail(
    subject: str,
    html: str,
    to: Optional[str] = None,
    bcc: Optional[List[str]] = None,
    reply_to: Optional[str] = None,
) -> Dict[str, str]:
    """Send one email. `to` defaults to the team inbox. Never raises."""
    transport = active_transport()
    recipients = [to or settings.VANIKA_TEAM_INBOX]
    bcc = [b for b in (bcc or []) if b and b.lower() not in {r.lower() for r in recipients}]
    reply_to = reply_to or settings.VANIKA_TEAM_INBOX
    try:
        if transport == "graph":
            await _send_graph(recipients, subject, html, bcc, reply_to)
        elif transport == "smtp":
            await run_in_threadpool(_send_smtp, recipients, subject, html, bcc, reply_to)
        elif transport == "acs":
            from Vanika_Mailing.helpers import send_email as acs_send

            result = await acs_send(subject=subject, html=html, to=to, reply=reply_to, onlySender=to is not None)
            if result.get("status") != "success":
                raise RuntimeError(result.get("message", "ACS error"))
        else:
            raise RuntimeError("No mail transport configured (set GRAPH_* or SMTP_PASSWORD)")
    except smtplib.SMTPAuthenticationError as e:
        detail = e.smtp_error.decode(errors="replace") if isinstance(e.smtp_error, bytes) else str(e.smtp_error)
        print(f"[Vanika] [MAIL ERROR] smtp auth failed: {e.smtp_code} {_redact(detail)[:200]}")
        return {"status": "error", "transport": transport, "message": f"SMTP auth failed ({e.smtp_code})"}
    except Exception as e:
        detail = _redact(f"{type(e).__name__}: {e}")
        print(f"[Vanika] [MAIL ERROR] {transport}: {detail[:300]}")
        return {"status": "error", "transport": transport, "message": detail[:200]}
    print(f"[Vanika] Mail sent via {transport} ({'subscriber' if to else 'team inbox'})")
    return {"status": "success", "transport": transport}
