import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


def get_gmail_service(scopes: list[str], token_path: str):
    """
    Create a Gmail API service using a dedicated token file.

    Each caller must provide its own OAuth scopes and token path.
    """

    credentials = None
    token_file = Path(token_path)

    # Load only the token belonging to this service.
    if token_file.exists():
        credentials = Credentials.from_authorized_user_file(
            str(token_file),
            scopes
        )

        # Never reuse a token with a different permission set.
        granted_scopes = set(credentials.scopes or [])

        if not set(scopes).issubset(granted_scopes):
            credentials = None

    # Refresh an expired token if possible.
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    # Start OAuth if credentials are missing or invalid.
    if not credentials or not credentials.valid:
        client_file = os.getenv(
            "GOOGLE_CLIENT_SECRET_FILE",
            "credentials.json"
        )

        if not os.path.exists(client_file):
            raise FileNotFoundError(
                "Google OAuth client credentials file not found."
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            client_file,
            scopes
        )

        credentials = flow.run_local_server(
            host="localhost",
            port=0
        )

    # Persist this service's token separately.
    token_file.parent.mkdir(parents=True, exist_ok=True)

    token_file.write_text(
        credentials.to_json(),
        encoding="utf-8"
    )

    return build(
        "gmail",
        "v1",
        credentials=credentials
    )