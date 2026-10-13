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

def vanika_subscribe_admin(clientemail: str):
    return f"""
    <div style="{EMAIL_WRAPPER}">
        <div style="{HEADER_LOGO}">
            <img src="{get_logo_url('vanika.ai')}" alt="Vanika Logo" style="width:200px; display:block; margin: auto;">
        </div>
        <div style="{CARD_STYLE}">
            <h2 style="{TITLE_STYLE}">✨ New Subscriber / Connection</h2>
            <p><span style="{LABEL_STYLE}">Website:</span> Vanika.ai</p>
            <p><span style="{LABEL_STYLE}">Client Email:</span> {clientemail}</p>
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
            <h2 style="{TITLE_STYLE}">🎉 Thank you for connecting!</h2>
            <p>Thank you for reaching out and connecting with <strong>Vanika.ai</strong>.</p>
            <p>We have successfully received your request and our team will keep you updated with our latest developments and news.</p>
            <br>
            <p>Warm Regards,<br><strong>Vanika.ai Team</strong></p>
        </div>
        <p style="text-align:center; margin-top:12px; color:#555;">
            © Vanika.ai
        </p>
    </div>
    """
