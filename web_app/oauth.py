import os
import secrets

from dotenv import load_dotenv
from google_auth_oauthlib.flow import Flow

load_dotenv()


# =========================================================
# GOOGLE OAUTH CONFIGURATION
# =========================================================

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify"
]


# =========================================================
# CREATE OAUTH FLOW
# =========================================================

def create_oauth_flow(state=None):
    """
    Create Google OAuth flow for the web application.
    """

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

    if not all([client_id, client_secret, redirect_uri]):
        raise RuntimeError(
            "Google OAuth configuration is missing."
        )

    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }

    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        state=state,
        redirect_uri=redirect_uri,
    )


# =========================================================
# GENERATE GOOGLE LOGIN URL
# =========================================================

def get_authorization_url():
    """
    Generate Google login URL and random CSRF state.

    The caller must securely store the returned state
    and associate it with the initiating browser session.
    """

    flow = create_oauth_flow()

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )

    return authorization_url, state


# =========================================================
# EXCHANGE AUTHORIZATION CODE
# =========================================================

def exchange_code_for_credentials(
    code: str,
    state: str,
    expected_state: str,
):
    """
    Validate OAuth state and exchange authorization code
    for Google credentials.
    """

    if not state or not expected_state:
        raise ValueError("Missing OAuth state.")

    if not secrets.compare_digest(state, expected_state):
        raise ValueError(
            "OAuth state mismatch. Authentication rejected."
        )

    if not code:
        raise ValueError("Missing authorization code.")

    flow = create_oauth_flow(state=expected_state)

    flow.fetch_token(code=code)

    return flow.credentials