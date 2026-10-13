# mailing/helpers.py
import base64
import os
from azure.communication.email import EmailClient
from config import settings

# Configuration based on your requirements
AZURE_EMAIL_CONNECTION = settings.AZURE_COMMUNICATION_CONNECTION_STRING

# Investor Desk Mail
EMAIL_FOR_INVESTORDESK = settings.EMAIL_FOR_INVESTORDESK
# EMAIL_FOR_INVESTORDESK  = "praveen.dasari@anvi.co"

# Primary Main Mail
EMAIL_PRIMARY_ANVI = settings.EMAIL_PRIMARY_ANVI
EMAIL_PRIMARY_BOTFACTORY = settings.EMAIL_PRIMARY_BOTFACTORY

# Secondary Emails - Hidden Fallback (BCC)
EMAIL_BCC_FALLBACK_1 = settings.EMAIL_BCC_FALLBACK_1
EMAIL_BCC_FALLBACK_2 = settings.EMAIL_BCC_FALLBACK_2

# Anvi All Website
async def send_email(subject, html, to=None, reply=None, attachment=None, onlySender=False, investorDesk=False):
    if not AZURE_EMAIL_CONNECTION or not EMAIL_PRIMARY_ANVI:
        return {"status": "error", "message": "ACS is not correctly configured"}

    try:
        email_client = EmailClient.from_connection_string(AZURE_EMAIL_CONNECTION)
        to_recipients = []
        bcc_recipients = []

        # Determine Primary Sender based on investorDesk flag
        # If investorDesk is True, use the InvestorDesk mail, otherwise use default ACS Sender
        active_sender = EMAIL_FOR_INVESTORDESK if investorDesk else EMAIL_PRIMARY_ANVI

        target_email = to.strip() if (to and to.strip()) else None
        
        # 1. Logic for Primary Recipient (TO)
        if target_email:
            to_recipients.append({"address": target_email})
        else:
            # Fallback to the active sender if no 'to' provided
            to_recipients.append({"address": active_sender})

        # 2. Logic for Fallback (BCC - Invisible to the recipient)
        bcc_set = {b["address"].lower() for b in bcc_recipients}

        if not onlySender:
            if EMAIL_BCC_FALLBACK_1:
                fallback1_lc = EMAIL_BCC_FALLBACK_1.lower()
                if fallback1_lc != (target_email or "").lower() and fallback1_lc not in bcc_set:
                    bcc_recipients.append({"address": EMAIL_BCC_FALLBACK_1})
                    bcc_set.add(fallback1_lc)

        # 3. Adding BCC Mail for Anvi.Co specifically
        subject_lc = (subject or "").lower()
        if "anvi.co" in subject_lc and EMAIL_BCC_FALLBACK_2 and not onlySender:
            fallback2_lc = EMAIL_BCC_FALLBACK_2.lower()
            if fallback2_lc != (target_email or "").lower() and fallback2_lc not in bcc_set:
                bcc_recipients.append({"address": EMAIL_BCC_FALLBACK_2})
                bcc_set.add(fallback2_lc)

            
        # Construct the Message
        # print("//////////////////////")
        # print("Only Sender", to,onlySender)
        # print("Primary Email : ", active_sender)
        # print("Sending Email to : ", to_recipients)
        # print("BCC Hidden Sending Email to : ", bcc_recipients)
        # print("subject", subject)
        # print("html", html)
        # print("//////////////////////")
        email_message = {
            "senderAddress": active_sender, # Corrected based on your requirement
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

        # --- ATTACHMENT HANDLER (remains the same) ---
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
        # return {"status": "success"}

    except Exception as e:
        print(f"[ACS EMAIL ERROR] {str(e)}")
        return {"status": "error", "message": str(e)}  
    
 
# The BotFactory Website
async def botfactory_send_email(subject, html, to=None, reply=None, attachment=None, onlySender=False):
    if not AZURE_EMAIL_CONNECTION or not EMAIL_PRIMARY_BOTFACTORY:
        return {"status": "error", "message": "ACS is not correctly configured"}

    try:
        email_client = EmailClient.from_connection_string(AZURE_EMAIL_CONNECTION)
        to_recipients = []
        bcc_recipients = []

        # SET PRIMARY MAIL IDS as ACS Sender
        active_sender = EMAIL_PRIMARY_BOTFACTORY
        
        target_email = to.strip() if (to and to.strip()) else None
        
        # 1. Logic for Primary Recipient (TO)
        if target_email:
            to_recipients.append({"address": target_email})
        else:
            # Fallback to the active sender if no 'to' provided
            to_recipients.append({"address": active_sender})
        
                # 2. Logic for Fallback (BCC - Invisible to the recipient)
        bcc_set = {b["address"].lower() for b in bcc_recipients}

        if not onlySender:
            if EMAIL_BCC_FALLBACK_1:
                fallback1_lc = EMAIL_BCC_FALLBACK_1.lower()
                if fallback1_lc != (target_email or "").lower() and fallback1_lc not in bcc_set:
                    bcc_recipients.append({"address": EMAIL_BCC_FALLBACK_1})
                    bcc_set.add(fallback1_lc)

        # 3. Adding BCC Mail for Anvi.Co specifically
        subject_lc = (subject or "").lower()
        if "anvi.co" in subject_lc and EMAIL_BCC_FALLBACK_2 and not onlySender:
            fallback2_lc = EMAIL_BCC_FALLBACK_2.lower()
            if fallback2_lc != (target_email or "").lower() and fallback2_lc not in bcc_set:
                bcc_recipients.append({"address": EMAIL_BCC_FALLBACK_2})
                bcc_set.add(fallback2_lc)


        # Construct the Message
        print("//////////////////////")
        # print("Only Sender", to,onlySender)
        print("Primary Email : ", active_sender)
        print("Sending Email to : ", to_recipients)
        # print("BCC Hidden Sending Email to : ", bcc_recipients)
        # print("subject", subject)
        # print("html", html)
        print("//////////////////////")
        email_message = {
            "senderAddress": active_sender, # Corrected based on your requirement
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

        # --- ATTACHMENT HANDLER (remains the same) ---
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
        # return {"status": "success"}

    except Exception as e:
        print(f"[ACS EMAIL ERROR] {str(e)}")
        return {"status": "error", "message": str(e)}  
    
