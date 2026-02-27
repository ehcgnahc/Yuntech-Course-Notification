import email
import os
import base64
import asyncio
from email.message import EmailMessage
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.send']

_GMAIL_SERVICE = None

def get_gmail_service():
    global _GMAIL_SERVICE
    if _GMAIL_SERVICE:
        return  _GMAIL_SERVICE
    
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    _GMAIL_SERVICE = build('gmail', 'v1', credentials=creds)
    return _GMAIL_SERVICE

def sync_send_email(target_email, info):
    targetSemester, course_ID, course_name, course_type, current_students, max_limit = info

    msg = EmailMessage()
    msg["To"] = target_email
    msg["Subject"] = f"【搶課通知】{targetSemester} {course_name} "
    content = (
        f"您訂閱的課程已經釋出名額!\n\n"
        f"課程代碼: {course_ID}\n"
        f"課程名稱: {course_name}\n"
        f"目前人數/上限: {current_students}/{max_limit}\n\n"
        f"請盡速登入選課系統搶課"
    )
    msg.set_content(content)
    
    encoded_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    create_message = {
        'raw': encoded_message
    }
    
    try:
        service = get_gmail_service()
        send_message = service.users().messages().send(userId='me', body=create_message).execute()
        print(f"Email sent to {target_email} for course {course_ID} (Message ID: {send_message['id']})")
    except Exception as e:
        print(f"Failed to send email to {target_email} for course {course_ID}: {e}")

async def send_email(target_email, info):
    await asyncio.to_thread(sync_send_email, target_email, info)