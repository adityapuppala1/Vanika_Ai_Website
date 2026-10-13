# Vanika_Mailing/helpers.py
import base64
# pyrefly: ignore [missing-import]
from azure.communication.email import EmailClient
from config import settings

AZURE_EMAIL_CONNECTION = settings.AZURE_COMMUNICATION_CONNECTION_STRING
EMAIL_PRIMARY_VANIKA = settings.EMAIL_PRIMARY_VANIKA
EMAIL_BCC_FALLBACK_1 = settings.EMAIL_BCC_FALLBACK_1

async def send_email(subject, html, to=None, reply=None, attachment=None, onlySender=False):
    if not AZURE_EMAIL_CONNECTION or not EMAIL_PRIMARY_VANIKA:
        return {"status": "error", "message": "ACS is not correctly configured"}

    try:
        email_client = EmailClient.from_connection_string(AZURE_EMAIL_CONNECTION)
        to_recipients = []
        bcc_recipients = []

        active_sender = EMAIL_PRIMARY_VANIKA
        target_email = to.strip() if (to and to.strip()) else None
        
        # 1. Logic for Primary Recipient (TO)
        if target_email:
            to_recipients.append({"address": target_email})
        else:
            # Fallback to the active sender if no 'to' provided (e.g. sending to admin)
            to_recipients.append({"address": active_sender})

        # 2. Logic for Fallback (BCC - Invisible to the recipient)
        bcc_set = {b["address"].lower() for b in bcc_recipients}

        if not onlySender:
            if EMAIL_BCC_FALLBACK_1:
                fallback1_lc = EMAIL_BCC_FALLBACK_1.lower()
                if fallback1_lc != (target_email or "").lower() and fallback1_lc not in bcc_set:
                    bcc_recipients.append({"address": EMAIL_BCC_FALLBACK_1})
                    bcc_set.add(fallback1_lc)

        print("//////////////////////")
        print("Primary Email : ", active_sender)
        print("Sending Email to : ", to_recipients)
        print("BCC Hidden Sending Email to : ", bcc_recipients)
        print("subject", subject)
        print("//////////////////////")

        email_message = {
            "senderAddress": active_sender,
            "recipients": {
                "to": to_recipients,
                "bcc": bcc_recipients
            },
            "content": {
                "subject": subject,
                "html": html
            },
            "replyTo": [{"address": reply if reply else active_sender}]
        }

        # --- ATTACHMENT HANDLER ---
        if attachment:
            try:
                file_content = None
                file_name = "attachment.pdf"
                content_type = "application/pdf"
                if isinstance(attachment, dict):
                    file_content = attachment.get('data') 
                    file_name = attachment.get('name', 'attachment.pdf')
                    content_type = attachment.get('type', 'application/pdf')
                elif hasattr(attachment, 'read'):
                    file_content = attachment.read()
                    file_name = getattr(attachment, 'name', 'attachment.pdf')

                if file_content:
                    if isinstance(file_content, str):
                        file_content = file_content.encode('utf-8')
                    content_b64 = base64.b64encode(file_content).decode()
                    email_message["attachments"] = [{
                        "name": file_name,
                        "contentType": content_type,
                        "contentInBase64": content_b64
                    }]
            except Exception as e:
                print(f"ATTACHMENT ERROR: {e}")
        
        poller = email_client.begin_send(email_message)
        result = poller.result()
        return {"status": "success", "id": result["id"]}

    except Exception as e:
        print(f"[ACS EMAIL ERROR] {str(e)}")
        return {"status": "error", "message": str(e)}  
