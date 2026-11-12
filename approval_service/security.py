
import os
import secrets
import hmac

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired


SESSION_MAX_AGE = 30 * 60  # 30 minutes
SESSION_SALT = "safemail-human-session-v1"


class SecurityError(Exception):
    pass


def get_serializer():
    secret = os.getenv("SAFEMAIL_SESSION_SECRET")

    if not secret or len(secret) < 32:
        raise SecurityError(
            "SAFEMAIL_SESSION_SECRET must contain at least 32 characters."
        )

    return URLSafeTimedSerializer(
        secret_key=secret,
        salt=SESSION_SALT
    )


def verify_login_password(password):
    expected = os.getenv("SAFEMAIL_HUMAN_PASSWORD")

    if not expected:
        raise SecurityError(
            "SAFEMAIL_HUMAN_PASSWORD is not configured."
        )

    if not isinstance(password, str):
        return False

    return hmac.compare_digest(password, expected)


def create_session():
    csrf_token = secrets.token_urlsafe(32)

    payload = {
        "session_id": secrets.token_urlsafe(32),
        "csrf_token": csrf_token
    }

    session_token = get_serializer().dumps(payload)

    return {
        "session_token": session_token,
        "csrf_token": csrf_token
    }


def verify_session(session_token):
    if not session_token:
        return None

    try:
        payload = get_serializer().loads(
            session_token,
            max_age=SESSION_MAX_AGE
        )

        if not isinstance(payload, dict):
            return None

        if not payload.get("session_id"):
            return None

        if not payload.get("csrf_token"):
            return None

        return payload

    except (BadSignature, SignatureExpired):
        return None


def verify_csrf_token(session, submitted_token):
    if not session or not submitted_token:
        return False

    expected = session.get("csrf_token")

    if not isinstance(expected, str):
        return False

    if not isinstance(submitted_token, str):
        return False

    return hmac.compare_digest(expected, submitted_token)
