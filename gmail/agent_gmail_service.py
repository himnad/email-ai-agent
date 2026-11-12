from gmail.oauth_service import get_gmail_service

# Read-only permission for the AI agent.
AGENT_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]


def get_agent_gmail_service():
    """Gmail access for reading and analyzing emails only."""

    return get_gmail_service(
        scopes=AGENT_SCOPES,
        token_path="secrets/agent_gmail_token.json"
    )