import os
import pickle
import base64

from bs4 import BeautifulSoup

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# =========================================================
# GMAIL CONFIGURATION
# =========================================================

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify"
]


# =========================================================
# GET GMAIL SERVICE
# =========================================================

def get_gmail_service():
    """
    Authenticate with Gmail and return the Gmail API service.
    """

    creds = None

    # -----------------------------------------------------
    # Load previously saved token
    # -----------------------------------------------------

    if os.path.exists("gmail_token.pickle"):

        with open("gmail_token.pickle", "rb") as token:
            creds = pickle.load(token)


    # -----------------------------------------------------
    # Refresh expired credentials
    # -----------------------------------------------------

    if creds and creds.expired and creds.refresh_token:

        creds.refresh(Request())


    # -----------------------------------------------------
    # Create new OAuth credentials if necessary
    # -----------------------------------------------------

    if not creds or not creds.valid:

        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials.json",
            SCOPES
        )

        creds = flow.run_local_server(
            host="localhost",
            port=0
        )


        # Save credentials for future runs
        with open("gmail_token.pickle", "wb") as token:
            pickle.dump(creds, token)


    # -----------------------------------------------------
    # Build Gmail API service
    # -----------------------------------------------------

    service = build(
        "gmail",
        "v1",
        credentials=creds
    )

    return service


# =========================================================
# CLEAN HTML EMAIL
# =========================================================

def clean_html(html):
    """
    Convert HTML email content into readable plain text.
    """

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    return soup.get_text(
        separator="\n",
        strip=True
    )


# =========================================================
# EXTRACT EMAIL BODY
# =========================================================

def extract_email_body(payload):
    """
    Extract the readable body from a Gmail message payload.
    """

    # -----------------------------------------------------
    # Multipart email
    # -----------------------------------------------------

    if "parts" in payload:

        for part in payload["parts"]:

            mime_type = part.get(
                "mimeType",
                ""
            )

            # Prefer plain text
            if mime_type == "text/plain":

                data = part.get(
                    "body",
                    {}
                ).get(
                    "data"
                )

                if data:

                    decoded = base64.urlsafe_b64decode(
                        data
                    ).decode(
                        "utf-8",
                        errors="ignore"
                    )

                    return decoded


            # Handle HTML
            elif mime_type == "text/html":

                data = part.get(
                    "body",
                    {}
                ).get(
                    "data"
                )

                if data:

                    decoded = base64.urlsafe_b64decode(
                        data
                    ).decode(
                        "utf-8",
                        errors="ignore"
                    )

                    return clean_html(decoded)


            # Recursively handle nested multipart sections
            elif "parts" in part:

                result = extract_email_body(
                    part
                )

                if result:
                    return result


    # -----------------------------------------------------
    # Single-part email
    # -----------------------------------------------------

    body_data = payload.get(
        "body",
        {}
    ).get(
        "data"
    )

    if body_data:

        decoded = base64.urlsafe_b64decode(
            body_data
        ).decode(
            "utf-8",
            errors="ignore"
        )

        if payload.get("mimeType") == "text/html":

            return clean_html(decoded)

        return decoded


    return ""


# =========================================================
# GET UNREAD EMAILS
# =========================================================

def get_unread_emails():
    """
    Retrieve unread emails from the Gmail inbox.
    """

    service = get_gmail_service()

    results = (
        service.users()
        .messages()
        .list(
            userId="me",
            labelIds=[
                "INBOX",
                "UNREAD"
            ],
            maxResults=10
        )
        .execute()
    )

    messages = results.get(
        "messages",
        []
    )


    if not messages:
        return []


    emails = []


    # -----------------------------------------------------
    # Retrieve complete information for every email
    # -----------------------------------------------------

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


        headers = message[
            "payload"
        ].get(
            "headers",
            []
        )


        sender = ""
        subject = ""


        # -------------------------------------------------
        # Extract headers
        # -------------------------------------------------

        for header in headers:

            header_name = header[
                "name"
            ].lower()


            if header_name == "from":

                sender = header[
                    "value"
                ]


            elif header_name == "subject":

                subject = header[
                    "value"
                ]


        # -------------------------------------------------
        # Extract body
        # -------------------------------------------------

        body = extract_email_body(
            message["payload"]
        )


        # -------------------------------------------------
        # Store email
        # -------------------------------------------------

        emails.append(
            {
                "id": message["id"],
                "sender": sender,
                "subject": subject,
                "body": body
            }
        )


    return emails


# =========================================================
# MARK EMAIL AS READ
# =========================================================

def mark_email_as_read(message_id):
    """
    Mark a Gmail message as read by removing
    the UNREAD label.

    If Gmail is temporarily unreachable,
    do not crash the entire application.
    """

    try:

        service = get_gmail_service()


        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={
                "removeLabelIds": [
                    "UNREAD"
                ]
            }
        ).execute()


        return True


    except Exception as e:

        print(
            "\nCould not mark email as read."
        )

        print(
            "Gmail API error:",
            e
        )

        return False