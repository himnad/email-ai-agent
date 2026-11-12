
from safemail.recipient_validator import (
    validate_email_address,
    resolve_reply_recipient,
    RecipientValidationError
)

ALLOW = "ALLOW"
REQUIRE_HUMAN_REVIEW = "REQUIRE_HUMAN_REVIEW"
BLOCK = "BLOCK"


SENSITIVE_PATTERNS = {
    "private_key": r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    "password": r"(?i)\bpassword\s*[:=]\s*\S+",
    "api_key": r"(?i)\b(?:api[_-]?key|access[_-]?token)\s*[:=]\s*\S+",
    "aws_key": r"\bAKIA[0-9A-Z]{16}\b"
}


def evaluate_email_action(
    recipient,
    subject,
    body,
    from_header=None,
    reply_to_header=None
):
    """
    Evaluate an email before execution.

    Security policy:
    1. Invalid recipients are blocked.
    2. Sender/recipient mismatches are blocked.
    3. Reply-To mismatches are blocked.
    4. Sensitive information leakage is blocked.
    5. All other emails require human approval.
    """

    import re

    reasons = []

    # Validate required fields
    if not all(isinstance(x, str) for x in (recipient, subject, body)):
        return {
            "decision": BLOCK,
            "reasons": ["Recipient, subject, and body must be strings."]
        }

    if not recipient.strip():
        return {
            "decision": BLOCK,
            "reasons": ["Recipient cannot be empty."]
        }

    # Prevent header injection
    if any(char in recipient + subject for char in ("\r", "\n")):
        return {
            "decision": BLOCK,
            "reasons": ["Header injection detected."]
        }

    # Validate recipient format
    try:
        validate_email_address(recipient)
    except RecipientValidationError as exc:
        return {
            "decision": BLOCK,
            "reasons": [f"Invalid recipient: {exc}"]
        }

    # Require sender identity for reply operations
    if not from_header:
        return {
            "decision": BLOCK,
            "reasons": ["Original sender identity is missing."]
        }

    # Verify that recipient is the actual sender and
    # that Reply-To has not been manipulated.
    try:
        resolved_recipient = resolve_reply_recipient(
            from_header,
            reply_to_header
        )

        if resolved_recipient.lower() != recipient.lower():
            return {
                "decision": BLOCK,
                "reasons": [
                    "Recipient does not match the verified sender."
                ]
            }

    except RecipientValidationError as exc:
        return {
            "decision": BLOCK,
            "reasons": [
                f"Sender or Reply-To validation failed: {exc}"
            ]
        }

    # Detect sensitive information in outgoing content
    for pattern_name, pattern in SENSITIVE_PATTERNS.items():
        if re.search(pattern, body):
            return {
                "decision": BLOCK,
                "reasons": [
                    f"Potential sensitive information detected: {pattern_name}"
                ]
            }

    # No automatic sending: human approval is mandatory.
    return {
        "decision": REQUIRE_HUMAN_REVIEW,
        "reasons": [
            "Email passed security checks but requires human approval."
        ]
    }
