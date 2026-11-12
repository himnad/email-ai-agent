
import base64

from bs4 import BeautifulSoup

from gmail.agent_gmail_service import get_agent_gmail_service


# =========================================================
# CLEAN HTML EMAIL
# =========================================================

def clean_html(html):
    """Convert HTML email content into readable plain text."""

    soup = BeautifulSoup(html, "html.parser")

    return soup.get_text(
        separator="\n",
        strip=True
    )


# =========================================================
# EXTRACT EMAIL BODY
# =========================================================

def extract_email_body(payload):
    """Extract readable text from Gmail message payload."""

    if "parts" in payload:

        # Prefer plain text.
        for part in payload["parts"]:

            mime_type = part.get("mimeType", "")

            if mime_type == "text/plain":

                data = part.get("body", {}).get("data")

                if data:
                    return base64.urlsafe_b64decode(
                        data
                    ).decode("utf-8", errors="ignore")

        # Use HTML if plain text is unavailable.
        for part in payload["parts"]:

            mime_type = part.get("mimeType", "")

            if mime_type == "text/html":

                data = part.get("body", {}).get("data")

                if data:
                    decoded = base64.urlsafe_b64decode(
                        data
                    ).decode("utf-8", errors="ignore")

                    return clean_html(decoded)

        # Handle nested multipart sections.
        for part in payload["parts"]:

            if "parts" in part:

                result = extract_email_body(part)

                if result:
                    return result

    # Handle single-part messages.
    body_data = payload.get("body", {}).get("data")

    if body_data:

        decoded = base64.urlsafe_b64decode(
            body_data
        ).decode("utf-8", errors="ignore")

        if payload.get("mimeType") == "text/html":
            return clean_html(decoded)

        return decoded

    return ""


# =========================================================
# EXTRACT EMAIL HEADERS
# =========================================================

def extract_email_headers(headers):
    """Extract From, Reply-To and Subject separately."""

    sender = ""
    reply_to = ""
    subject = ""

    for header in headers:

        header_name = header.get("name", "").lower()
        header_value = header.get("value", "")

        if header_name == "from":
            sender = header_value

        elif header_name == "reply-to":
            reply_to = header_value

        elif header_name == "subject":
            subject = header_value

    return {
        "sender": sender,
        "reply_to": reply_to,
        "subject": subject
    }


# =========================================================
# GET UNREAD EMAILS - READ ONLY
# =========================================================

def get_unread_emails():
    """
    Retrieve unread inbox emails.

    This function only reads messages.
    It does not mark messages as read or send emails.
    """

    service = get_agent_gmail_service()

    results = (
        service.users()
        .messages()
        .list(
            userId="me",
            labelIds=["INBOX", "UNREAD"],
            maxResults=10
        )
        .execute()
    )

    messages = results.get("messages", [])

    if not messages:
        return []

    emails = []

    for message_info in messages:

        message = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message_info["id"],
                format="full"
            )
            .execute()
        )

        payload = message.get("payload", {})

        headers = payload.get("headers", [])

        email_headers = extract_email_headers(headers)

        body = extract_email_body(payload)

        emails.append({
            "id": message["id"],
            "sender": email_headers["sender"],
            "reply_to": email_headers["reply_to"],
            "subject": email_headers["subject"],
            "body": body
        })

    return emails
