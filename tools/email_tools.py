from email.message import EmailMessage
import base64

from gmail.gmail_service import get_gmail_service


def send_email(to: str, subject: str, body: str):
    """
    Send an email using the Gmail API.
    """

    # Get authenticated Gmail service
    service = get_gmail_service()

    # Create the email
    message = EmailMessage()

    message["To"] = to
    message["Subject"] = subject

    # Set email body
    message.set_content(body)

    # Convert email to Gmail API format
    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode()

    # Send email through Gmail API
    result = (
        service.users()
        .messages()
        .send(
            userId="me",
            body={
                "raw": encoded_message
            }
        )
        .execute()
    )

    return {
        "to": to,
        "subject": subject,
        "body": body,
        "status": "sent",
        "message_id": result["id"]
    }