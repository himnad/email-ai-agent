from gmail.oauth_service import get_gmail_service


# Send-only permission for SafeMail.
SAFEMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]


def get_safemail_gmail_service():
    """
    Gmail access for sending emails after authorization.
    """

    return get_gmail_service(
        scopes=SAFEMAIL_SCOPES,
        token_path="secrets/safemail_gmail_token.json"
    )