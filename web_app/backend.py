
import os
import secrets

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from web_app.oauth import (
    get_authorization_url,
    exchange_code_for_credentials,
)

load_dotenv()

app = FastAPI(title="AI Email Agent OAuth Backend")

session_secret = os.getenv("SESSION_SECRET_KEY")

if not session_secret or len(session_secret) < 32:
    raise RuntimeError("Set a strong SESSION_SECRET_KEY in .env")

app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    session_cookie="email_agent_session",
    same_site="lax",
    https_only=False,  # Local HTTP development only
    max_age=600,
)


@app.get("/")
def home():
    return {"message": "AI Email Agent OAuth backend running"}


@app.get("/auth/login")
def login(request: Request):
    authorization_url, state = get_authorization_url()

    request.session["oauth_state"] = state

    return RedirectResponse(authorization_url)


@app.get("/auth/callback")
def callback(request: Request):
    code = request.query_params.get("code")
    received_state = request.query_params.get("state")
    expected_state = request.session.pop("oauth_state", None)

    if not code or not received_state or not expected_state:
        raise HTTPException(
            status_code=400,
            detail="Missing OAuth code or state",
        )

    if not secrets.compare_digest(received_state, expected_state):
        raise HTTPException(
            status_code=403,
            detail="OAuth state verification failed",
        )

    # Token exchange and per-user credential storage
    # will be implemented in the next step.
    # Do not expose authorization codes or tokens in responses.
    return JSONResponse({
        "status": "state_verified",
        "message": "OAuth callback state verified successfully.",
    })
