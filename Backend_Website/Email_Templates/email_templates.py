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
    website = (website or "").lower()
    print("Website in get logo =============: ", website)

    if "anvispace" in website:
        return "https://anvispace.com/logos/mail_logo.png"
        # return "https://koicspace.com/logos/koic_space_mail_logo.png"
    elif "anvirobotics" in website:
        return "https://www.anvirobotics.com/logos/anvi_robotics_White.png"
    elif "thebotfactory" in website:
        return "https://www.thebotfactory.in/logo.png"
    else:
        # Default fallback
        return "https://anvi.co/logos/anvi_logo.png"

def subscribe_template_admin(Website, Email):
    return f"""
    <div style="{EMAIL_WRAPPER}">

        <div style="{HEADER_LOGO}">
            <picture>
                <source srcset="{get_logo_url(Website).replace('.png', '.svg')}" type="image/svg+xml">  
                <img src="{get_logo_url(Website)}" alt="Logo" style="width:200px; display:block; margin: auto;">
            </picture>
        </div>

        <div style="{CARD_STYLE}">
            <h2 style="{TITLE_STYLE}">✨ New Subscriber</h2>

            <p><span style="{LABEL_STYLE}">Website:</span> {Website}</p>
            <p><span style="{LABEL_STYLE}">Email:</span> {Email}</p>
        </div>

        <p style="text-align:center; margin-top:12px; color:#555;">
            © {Website}
        </p>

    </div>
    """

def subscribe_template_user(Website):
    return f"""
    <div style="{EMAIL_WRAPPER}">

        <div style="{HEADER_LOGO}">
            <picture>
                <source srcset="{get_logo_url(Website).replace('.png', '.svg')}" type="image/svg+xml">  
                <img src="{get_logo_url(Website)}" alt="Logo" style="width:200px; display:block; margin: auto;">
            </picture>
        </div>

        <div style="{CARD_STYLE}">
            <h2 style="{TITLE_STYLE}">🎉 You're Subscribed!</h2>

            <p>Thank you for subscribing to <strong>{Website}</strong>.</p>
            <p>You’ll now receive updates, news, and exclusive offers.</p>

            <br>
            <p>Warm Regards,<br><strong>{Website} Team</strong></p>
        </div>

        <p style="text-align:center; margin-top:12px; color:#555;">
            © {Website}
        </p>
    </div>
    """

def contact_template(Website, Name, Email, PhNo="-", Subject="-", Message="-"):
    phone_html = ""
    if PhNo:
        phone_html = f"""
        <p><span style="{LABEL_STYLE}">Phone:</span> {PhNo}</p>
        """
    subject_html = ""
    if Subject:
        subject_html = f"""
        <p><span style="{LABEL_STYLE}">Phone:</span> {Subject}</p>
        """
    
    return f"""
    <div style="{EMAIL_WRAPPER}">

        <div style="{HEADER_LOGO}">
            <picture>
                <source srcset="{get_logo_url(Website).replace('.png', '.svg')}" type="image/svg+xml">  
                <img src="{get_logo_url(Website)}" alt="Logo" style="width:200px; display:block; margin: auto;">
            </picture>
        </div>

        <div style="{CARD_STYLE}">
            <h2 style="{TITLE_STYLE}">📧 New Contact Request</h2>

            <p><span style="{LABEL_STYLE}">Website:</span> {Website}</p>
            <p><span style="{LABEL_STYLE}">Name:</span> {Name}</p>
            <p><span style="{LABEL_STYLE}">Email:</span> {Email}</p>
            {phone_html}
            {subject_html}

            <p style="margin-top:20px;"><span style="{LABEL_STYLE}">Message:</span></p>
            <div style="background:#f7f7f7; padding:12px 14px; border-radius:8px;">
                {Message}
            </div>
        </div>

        <p style="text-align:center; margin-top:12px; color:#555;">
            © {Website}
        </p>
    </div>
    """

def thank_you_template(FullName, Website):
    return f"""
    <div style="{EMAIL_WRAPPER}">

        <div style="{HEADER_LOGO}">
            <picture>
                <source srcset="{get_logo_url(Website).replace('.png', '.svg')}" type="image/svg+xml">  
                <img src="{get_logo_url(Website)}" alt="Logo" style="width:200px; display:block; margin: auto;">
            </picture>
        </div>

        <div style="{CARD_STYLE}">
            <h2 style="{TITLE_STYLE}">Thank You, {FullName}! 🤝</h2>

            <p>We’ve received your message on <strong>{Website}</strong>.</p>
            <p>Our support team will reach out to you soon.</p>

            <p>If you need immediate help, simply reply to this email.</p>

            <br>
            <p>Best Regards,<br><strong>{Website} Team</strong></p>
        </div>

        <p style="text-align:center; margin-top:12px; color:#555;">
            © {Website}
        </p>
    </div>
    """

def apply_template(Data, Website):

    # Extract values first (safe access)
    full_name = Data.get("Full Name", "N/A")
    email = Data.get("Email", "N/A")
    phone = Data.get("Contact No.")
    current_location = Data.get("Current Location", "N/A")
    current_ctc = Data.get("Current CTC", "N/A")
    expected_ctc = Data.get("Expected CTC", "N/A")
    portfolio = Data.get("Portfolio URL", "N/A")
    message = Data.get("Message", "N/A")

    # Conditional Phone HTML
    phone_html = ""
    if phone:
        phone_html = f"""
        <p><span style="{LABEL_STYLE}">Phone:</span> {phone}</p>
        """

    return f"""
    <div style="{EMAIL_WRAPPER}">

        <div style="{HEADER_LOGO}">
            <picture>
                <source srcset="{get_logo_url(Website).replace('.png', '.svg')}" type="image/svg+xml">  
                <img src="{get_logo_url(Website)}" alt="Logo" style="width:200px; display:block; margin: auto;">
            </picture>
        </div>

        <div style="{CARD_STYLE}">
            <h2 style="{TITLE_STYLE}">💼 New Job Application</h2>

            <p><span style="{LABEL_STYLE}">Name:</span> {full_name}</p>
            <p><span style="{LABEL_STYLE}">Email:</span> {email}</p>

            {phone_html}

            <p><span style="{LABEL_STYLE}">Current Location:</span> {current_location}</p>
            <p><span style="{LABEL_STYLE}">Current CTC:</span> {current_ctc}</p>
            <p><span style="{LABEL_STYLE}">Expected CTC:</span> {expected_ctc}</p>

            <p><span style="{LABEL_STYLE}">Portfolio:</span> {portfolio}</p>

            <p style="margin-top:18px;"><span style="{LABEL_STYLE}">Message:</span></p>
            <div style="background:#f7f7f7; padding:12px 14px; border-radius:8px;">
                {message}
            </div>
        </div>

        <p style="text-align:center; margin-top:12px; color:#555;">
            © {Website}
        </p>
    </div>
    """
    
def apply_response_template(FullName, Website):
    return f"""
    <div style="{EMAIL_WRAPPER}">

        <div style="{HEADER_LOGO}">
            <picture>
                <source srcset="{get_logo_url(Website).replace('.png', '.svg')}" type="image/svg+xml">  
                <img src="{get_logo_url(Website)}" alt="Logo" style="width:200px; display:block; margin: auto;">
            </picture>
        </div>

        <div style="{CARD_STYLE}">
            <h2 style="{TITLE_STYLE}">Hi {FullName}, 👋</h2>

            <p>Thank you for applying at <strong>{Website}</strong>.</p>
            <p>Your application and resume have been successfully received.</p>
            <p>Our HR team will review your profile and get back to you shortly.</p>

            <p>If you have any questions, reply to this email anytime.</p>

            <br>
            <p>Warm Regards,<br><strong>{Website} HR Team</strong></p>
        </div>

        <p style="text-align:center; margin-top:12px; color:#555;">
            © {Website}
        </p>
    </div>
    """
















# =========================================
# INVESTORS DESK EMAIL TEMPLATES
# =========================================

# InvestorDesk Sending Otp
# -----------------------------------
def anvi_investor_desk_sendOtp(info):
    # print("""""""""""""""""""""""")
    # print("info : ", info)
    # print("""""""""""""""""""""""")
    return f"""
    <div style="{EMAIL_WRAPPER}">

        <div style="{HEADER_LOGO}">
            <picture>
                <source srcset="{get_logo_url(info.Website).replace('.png', '.svg')}" type="image/svg+xml">  
                <img src="{get_logo_url(info.Website)}" alt="Logo" style="width:200px; display:block; margin: auto;">
            </picture>
        </div>

        <div style="{CARD_STYLE}">
            <p>Your OTP for login is:</p>
            <h2 style="font-size: 26px; letter-spacing: 2px;">{info.otp}</h2>
            <p>This OTP expires in {info.OTP_TTL_SECONDS // 60} minutes.</p>
        </div>
    </div>
    """



# InvestorDesk Client Login to Admin
# -----------------------------------
def anvi_investor_desk_loggedin_admin(info):
    return f"""
    <div style="{EMAIL_WRAPPER}">
        <div style="{HEADER_LOGO}">
            <picture>
                <source srcset="{get_logo_url(info.Website).replace('.png', '.svg')}" type="image/svg+xml">  
                <img src="{get_logo_url(info.Website)}" alt="Logo" style="width:200px; display:block; margin: auto;">
            </picture>
        </div>
        <div style="{CARD_STYLE}">
            <h3>Login Alert (Admin)</h3>
            <p>User <strong>{info.email}</strong> has successfully logged into the Investors Desk.</p>
            <p><strong>Time:</strong> {info.login_time}</p>
        </div>
    </div>
    """


# InvestorDesk Client Login
# -----------------------------------
def anvi_investor_desk_loggedin_client(info):
    return f"""
    <div style="{EMAIL_WRAPPER}">
        <div style="{HEADER_LOGO}">
            <picture>
                <source srcset="{get_logo_url(info.Website).replace('.png', '.svg')}" type="image/svg+xml">  
                <img src="{get_logo_url(info.Website)}" alt="Logo" style="width:200px; display:block; margin: auto;">
            </picture>
        </div>
        <div style="{CARD_STYLE}">
            <h3>Successfully Logged In</h3>
            <p>Hi,</p>
            <p>You have successfully logged into your Investor Dashboard.</p>
            <p>If this wasn't you, please contact support immediately.</p>
        </div>
    </div>
    """