
import hmac
import json
import time
import sqlite3
import hashlib
import secrets

from safemail.integrity import generate_email_hash


class ApprovalError(Exception):
    """Raised when an approval is invalid or unauthorized."""
    pass


def get_signature(token_id, email_hash, expires_at, secret):
    """Create an HMAC-SHA256 signature for an approval."""

    payload = json.dumps(
        {
            "token_id": token_id,
            "email_hash": email_hash,
            "expires_at": expires_at
        },
        sort_keys=True,
        separators=(",", ":")
    ).encode("utf-8")

    return hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()


def initialize_db(db_path):
    """Create persistent approval storage."""

    conn = sqlite3.connect(db_path)

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                token_id TEXT PRIMARY KEY,
                email_hash TEXT NOT NULL,
                expires_at REAL NOT NULL,
                signature TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def issue_approval(
    recipient,
    subject,
    body,
    secret,
    db_path="safemail/approvals.db",
    ttl_seconds=300
):
    """Issue a signed, time-limited approval."""

    if not isinstance(secret, str) or len(secret) < 32:
        raise ApprovalError(
            "Signing secret must contain at least 32 characters."
        )

    if not isinstance(ttl_seconds, (int, float)) or isinstance(ttl_seconds, bool):
        raise ApprovalError("Invalid approval lifetime.")

    if ttl_seconds <= 0:
        raise ApprovalError("Approval lifetime must be positive.")

    email_hash = generate_email_hash(recipient, subject, body)

    token_id = secrets.token_urlsafe(32)
    expires_at = time.time() + ttl_seconds

    signature = get_signature(
        token_id,
        email_hash,
        expires_at,
        secret
    )

    initialize_db(db_path)

    conn = sqlite3.connect(db_path)

    try:
        conn.execute(
            """
            INSERT INTO approvals
            (token_id, email_hash, expires_at, signature, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (token_id, email_hash, expires_at, signature)
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "token_id": token_id,
        "email_hash": email_hash,
        "expires_at": expires_at,
        "signature": signature
    }


def verify_and_consume_approval(
    approval,
    recipient,
    subject,
    body,
    secret,
    db_path="safemail/approvals.db"
):
    """Verify approval and atomically consume it exactly once."""

    if not isinstance(secret, str) or len(secret) < 32:
        raise ApprovalError("Invalid signing secret.")

    if not isinstance(approval, dict):
        raise ApprovalError("Invalid approval token.")

    required = {
        "token_id",
        "email_hash",
        "expires_at",
        "signature"
    }

    if not required.issubset(approval):
        raise ApprovalError("Incomplete approval token.")

    token_id = approval["token_id"]
    email_hash = approval["email_hash"]
    expires_at = approval["expires_at"]
    signature = approval["signature"]

    if not isinstance(token_id, str) or not isinstance(email_hash, str):
        raise ApprovalError("Invalid token fields.")

    if (
        not isinstance(expires_at, (int, float))
        or isinstance(expires_at, bool)
    ):
        raise ApprovalError("Invalid expiry.")

    if not isinstance(signature, str):
        raise ApprovalError("Invalid signature.")

    # Verify the exact email content.
    expected_hash = generate_email_hash(
        recipient,
        subject,
        body
    )

    if not hmac.compare_digest(email_hash, expected_hash):
        raise ApprovalError(
            "Email content was modified after approval."
        )

    # Verify the HMAC signature.
    expected_signature = get_signature(
        token_id,
        email_hash,
        expires_at,
        secret
    )

    if not hmac.compare_digest(signature, expected_signature):
        raise ApprovalError("Approval signature is invalid.")

    initialize_db(db_path)

    conn = sqlite3.connect(db_path, timeout=10)

    try:
        # Serialize concurrent approval-consumption attempts.
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute(
            """
            SELECT email_hash, expires_at, signature, status
            FROM approvals
            WHERE token_id = ?
            """,
            (token_id,)
        ).fetchone()

        if row is None:
            raise ApprovalError("Approval does not exist.")

        stored_hash, stored_expiry, stored_signature, status = row

        if status != "pending":
            raise ApprovalError("Approval has already been used.")

        if time.time() >= stored_expiry:
            conn.execute(
                """
                UPDATE approvals
                SET status = 'expired'
                WHERE token_id = ?
                """,
                (token_id,)
            )
            conn.commit()

            raise ApprovalError("Approval has expired.")

        if (
            not hmac.compare_digest(stored_hash, email_hash)
            or stored_expiry != expires_at
            or not hmac.compare_digest(stored_signature, signature)
        ):
            raise ApprovalError("Stored approval does not match.")

        # Consume approval exactly once.
        conn.execute(
            """
            UPDATE approvals
            SET status = 'consumed'
            WHERE token_id = ?
            """,
            (token_id,)
        )

        conn.commit()

    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise

    finally:
        conn.close()

    return True
