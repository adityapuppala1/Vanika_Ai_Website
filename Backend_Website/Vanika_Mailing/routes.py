# Vanika_Mailing/routes.py
from config import settings
# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Form
from Vanika_Mailing.helpers import send_email
from Vanika_Mailing.email_templates import vanika_subscribe_admin, vanika_subscribe_user

router = APIRouter()

@router.get("/ping")
async def ping():
    return {"status": "Vanika_Mailing router is working!"}

@router.post("/subscribe")
async def subscribe(clientemail: str = Form(...), accesskey: str = Form(...)):
    print(f"=== New Request from {clientemail} ===")

    if accesskey != settings.VANIKA_ROUTES_KEY:
        return {"status": "Failed", "message": "Invalid Access Key"}

    # 1. Send notification to Admin (EMAIL_PRIMARY_VANIKA) + BCC to Dev (EMAIL_BCC_FALLBACK_1)
    admin_html = vanika_subscribe_admin(clientemail)
    await send_email(
        subject=f"Vanika.ai - New Connection from {clientemail}",
        html=admin_html
    )

    # 2. Send Success / Thank You response to Client (clientemail) without BCC to Dev
    user_html = vanika_subscribe_user()
    await send_email(
        subject="Thanks for connecting with Vanika.ai!",
        html=user_html,
        to=clientemail,
        onlySender=False
    )

    return {"status": "Success", "message": "Successfully sent to Vanika mail and client."}
