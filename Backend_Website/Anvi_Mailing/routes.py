# mailing/routes.py

from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional
from Anvi_Mailing.helpers import send_email, botfactory_send_email
from Email_Templates.email_templates import (
    subscribe_template_user, subscribe_template_admin,
    contact_template, apply_template, thank_you_template,
    apply_response_template
)

router = APIRouter()

@router.get("/ping")
async def ping():
    return {"status": "Anvi_Mailing router is working!"}

@router.post("/subscribe")
async def subscribe(Website: str = Form(...), Email: str = Form(...)):
    admin_html = subscribe_template_admin(Website, Email)
    await send_email(
        subject=f"{Website} - New Subscriber",
        html=admin_html
    )

    user_html = subscribe_template_user(Website)
    await send_email(
        subject=f"Thanks for subscribing to {Website}!",
        html=user_html,
        to=Email,
        onlySender=True
    )

    return {"status": "Success", "message": "Subscribed successfully!"}


@router.post("/contact")
async def contact(
    Website: str = Form(...),
    FullName: str = Form(...),
    Email: str = Form(...),
    Message: str = Form(...),
    Subject: Optional[str] = Form(None),
    PhNo: Optional[str] = Form(None),
):
    admin_html = contact_template(
        Website, FullName, Email, PhNo, Subject, Message
    )
    user_html = thank_you_template(FullName, Website)
    
    print("ANVI MAILING =======================")
    
    await send_email(
        subject=f"{Website} - Contact ping from {FullName}",
        html=admin_html
    )

    await send_email(
        subject=f"Thanks for contacting {Website}!",
        html=user_html,
        to=Email,
        onlySender=True,
    )
        

    return {"status": "Success", "message": "Contact form submitted successfully!"}


@router.post("/thebotfactory-contact")
async def thebotfactory_contact(
    Website: str = Form(...),
    FullName: str = Form(...),
    Email: str = Form(...),
    Message: str = Form(...),
    Subject: Optional[str] = Form(None),
    PhNo: Optional[str] = Form(None),
):
    print("=======================")
    print("=======================")
    print("Contact Details =======================")
    print(Website, FullName, Email, Message, Subject, PhNo)
    print("=======================")
    print("=======================")
    
    admin_html = contact_template(
        Website, FullName, Email, PhNo, Subject, Message
    )
    user_html = thank_you_template(FullName, Website)
    
    print("TheBotFactory Mailing =======================")

    await botfactory_send_email(
        subject=f"{Website} - Contact ping from {FullName}",
        html=admin_html
    )
    
    await botfactory_send_email(
        subject=f"Thanks for contacting {Website}!",
        html=user_html,
        to=Email,
        onlySender=True,
    )

    return {"status": "Success", "message": "Contact form submitted successfully!"}


@router.post("/jobapply")
async def apply(
    FullName: str = Form(...),
    Email: str = Form(...),
    Phone: Optional[str] = Form(None),
    Message: Optional[str] = Form(None),
    CurrentLocation: Optional[str] = Form(None),
    CurrentCTC: Optional[str] = Form(None),
    ExpectedCTC: Optional[str] = Form(None),
    PortfolioURL: Optional[str] = Form(None),
    Resume: UploadFile = File(...),
    Website: str = Form(...),
):

    applicant_details = {
        "Full Name": FullName,
        "Email": Email,
    }

    if CurrentLocation:
        applicant_details["Current Location"] = CurrentLocation
    if CurrentCTC:
        applicant_details["Current CTC"] = CurrentCTC
    if ExpectedCTC:
        applicant_details["Expected CTC"] = ExpectedCTC
    if Phone:
        only_digits = "".join(ch for ch in Phone if ch.isdigit())
        if len(only_digits) >= 10:
            applicant_details["Contact No."] = Phone
    if Message and Message.strip():
        applicant_details["Message"] = Message.strip()
    if PortfolioURL and len(PortfolioURL.strip()) > 6:
        applicant_details["Portfolio URL"] = PortfolioURL.strip()

    html_admin = apply_template(applicant_details, Website)
    attachment = {
        "data": await Resume.read(),
        "name": Resume.filename,
        "type": Resume.content_type,
    }

    await send_email(
        subject=f"{Website} - New Career Application from {FullName}",
        html=html_admin,
        attachment=attachment
    )

    user_html = apply_response_template(FullName, Website)
    await send_email(
        subject=f"Thanks for applying to {Website}!",
        html=user_html,
        to=Email,
        onlySender=True,
    )

    return {"status": "Success", "message": "Application submitted successfully!"}
