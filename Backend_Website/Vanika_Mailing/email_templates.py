from html import escape
from typing import Optional

EMAIL_WRAPPER = """
max-width: 640px;
margin: auto;
padding: 0;
font-family: 'Inter', Arial, sans-serif;
"""

CARD_STYLE = """
background: #ffffff;
padding: 32px 28px;
border-radius: 14px;
border: 1px solid #e5e5e5;
box-shadow: 0 3px 12px rgba(0,0,0,0.06);
line-height: 1.7;
color: #111;
"""

HEADER_LOGO = """
width: 100%;
background: #000;
padding: 28px 0;
text-align: center;
display: flex;
margin: auto;
justify-content: center;
align-items: center;
place-content: center;
"""

TITLE_STYLE = "font-size: 24px; font-weight: 700; color: #000; margin-bottom: 14px;"
LABEL_STYLE = "font-weight: 600; color: #000;"

def get_logo_url(website: str) -> str:
    return "https://vanika.ai/logos/vanikaAi_mail_logo_white.png"

TYPE_LABELS = {"work": "Work", "education": "School / university", "personal": "Personal"}


def vanika_subscribe_admin(
    clientemail: str,
    source: str = "",
    total: Optional[int] = None,
    stored: bool = True,
    email_type: str = "",
):
    total_row = (
        f'<p><span style="{LABEL_STYLE}">Waitlist size:</span> {total}</p>' if total is not None else ""
    )
    storage_warning = (
        ""
        if stored
        else '<p style="color:#B42318; font-weight:600;">⚠ This sign-up could not be saved to the database. '
        "Add it manually and check the backend logs.</p>"
    )
    return f"""
    <div style="{EMAIL_WRAPPER}">
        <div style="{HEADER_LOGO}">
            <img src="{get_logo_url('vanika.ai')}" alt="Vanika Logo" style="width:200px; display:block; margin: auto;">
        </div>
        <div style="{CARD_STYLE}">
            <h2 style="{TITLE_STYLE}">✨ New Waitlist Sign-up</h2>
            <p><span style="{LABEL_STYLE}">Website:</span> Vanika.ai</p>
            <p><span style="{LABEL_STYLE}">Client Email:</span> {escape(clientemail)}</p>
            <p><span style="{LABEL_STYLE}">Email type:</span> {escape(TYPE_LABELS.get(email_type, email_type or "unknown"))}</p>
            <p><span style="{LABEL_STYLE}">Form:</span> {escape(source or "unknown")}</p>
            {total_row}
            {storage_warning}
        </div>
        <p style="text-align:center; margin-top:12px; color:#555;">
            © Vanika.ai
        </p>
    </div>
    """

def vanika_subscribe_user():
    return f"""
    <div style="{EMAIL_WRAPPER}">
        <div style="{HEADER_LOGO}">
            <img src="{get_logo_url('vanika.ai')}" alt="Vanika Logo" style="width:200px; display:block; margin: auto;">
        </div>
        <div style="{CARD_STYLE}">
            <h2 style="{TITLE_STYLE}">🎉 You're on the Vanika waitlist</h2>
            <p>Thank you for joining the waitlist for <strong>Vanika.ai</strong> — the AI copilot for robotics engineers.</p>
            <p>We'll email you when early access opens — one email when there's something real to share, and not before.</p>
            <p>Building a robot right now? Just reply to this email and tell us about it — we read every reply.</p>
            <br>
            <p>Warm Regards,<br><strong>Vanika.ai Team</strong><br>
            <a href="mailto:info@vanika.ai" style="color:#2D6A4F;">info@vanika.ai</a></p>
        </div>
        <p style="text-align:center; margin-top:12px; color:#555;">
            © Vanika.ai
        </p>
    </div>
    """
