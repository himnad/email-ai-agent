
import hashlib
import json
import hmac


def canonicalize_email(recipient: str, subject: str, body: str) -> bytes:
    """Convert email fields into a consistent byte representation."""

    if not all(isinstance(x, str) for x in [recipient, subject, body]):
        raise ValueError("Email fields must be strings.")

    if not recipient.strip():
        raise ValueError("Recipient cannot be empty.")

    if not subject.strip():
        raise ValueError("Subject cannot be empty.")

    if not body.strip():
        raise ValueError("Email body cannot be empty.")

    email_data = {
        "recipient": recipient,
        "subject": subject,
        "body": body
    }

    return json.dumps(
        email_data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False
    ).encode("utf-8")


def generate_email_hash(recipient: str, subject: str, body: str) -> str:
    """Generate SHA-256 fingerprint of the email."""

    data = canonicalize_email(recipient, subject, body)
    return hashlib.sha256(data).hexdigest()


def verify_email_integrity(
    original_hash: str,
    recipient: str,
    subject: str,
    body: str
) -> bool:
    """Check whether email content has changed."""

    current_hash = generate_email_hash(recipient, subject, body)

    return hmac.compare_digest(original_hash, current_hash)
