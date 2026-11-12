
import re
from email.utils import parseaddr, getaddresses


class RecipientValidationError(Exception):
    """Raised when an email recipient is invalid or ambiguous."""
    pass


def validate_email_address(address: str) -> str:
    """Validate a single email address."""

    if not isinstance(address, str) or not address:
        raise RecipientValidationError("Email address is empty.")

    address = address.strip()

    # Prevent header injection and control characters.
    if any(ord(char) < 32 or ord(char) == 127 for char in address):
        raise RecipientValidationError(
            "Control characters are not allowed."
        )

    if len(address) > 254:
        raise RecipientValidationError("Email address is too long.")

    pattern = (
        r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+"
        r"@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
        r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
    )

    if not re.fullmatch(pattern, address):
        raise RecipientValidationError(
            "Invalid email address format."
        )

    return address


def extract_single_address(header: str) -> str:
    """Extract exactly one address from an email header."""

    if not isinstance(header, str) or not header.strip():
        raise RecipientValidationError("Email header is missing.")

    if any(ord(char) < 32 and char not in "\t" for char in header):
        raise RecipientValidationError(
            "Invalid control character in email header."
        )

    addresses = getaddresses([header])

    if len(addresses) != 1:
        raise RecipientValidationError(
            "Multiple or ambiguous email addresses detected."
        )

    _, address = addresses[0]

    return validate_email_address(address)


def resolve_reply_recipient(
    from_header: str,
    reply_to_header: str = None
) -> str:
    """
    Resolve the recipient using trusted structured email headers.

    If Reply-To differs from From, reject automatic resolution
    and require explicit human review.
    """

    from_address = extract_single_address(from_header)

    if reply_to_header:
        reply_to_address = extract_single_address(reply_to_header)

        if reply_to_address.lower() != from_address.lower():
            raise RecipientValidationError(
                "Reply-To differs from From. "
                "Explicit human verification is required."
            )

    return from_address
