
from safemail.authorization import (
    verify_and_consume_approval,
    ApprovalError
)

from safemail.policy_engine import (
    evaluate_email_action,
    BLOCK,
    REQUIRE_HUMAN_REVIEW
)


class GatewayError(Exception):
    """Raised when an email execution is denied or fails."""
    pass


def execute_approved_email(
    approval,
    recipient,
    subject,
    body,
    secret,
    db_path="safemail/approvals.db",
    from_header=None,
    reply_to_header=None,
    send_function=None
):
    """
    Securely execute an approved email.

    Security workflow:
    1. Apply deterministic security policy.
    2. Reject blocked actions.
    3. Verify approval authenticity.
    4. Verify that email content has not changed.
    5. Consume the approval to prevent replay.
    6. Send the exact approved email.
    7. Return the Gmail message ID when available.
    """

    # -----------------------------------------------------
    # STEP 1: Apply security policy
    # -----------------------------------------------------

    policy_result = evaluate_email_action(
        recipient=recipient,
        subject=subject,
        body=body,
        from_header=from_header,
        reply_to_header=reply_to_header
    )

    if policy_result["decision"] == BLOCK:
        raise GatewayError(
            "Email blocked by security policy: "
            + "; ".join(policy_result["reasons"])
        )

    if policy_result["decision"] != REQUIRE_HUMAN_REVIEW:
        raise GatewayError(
            "Unexpected policy decision."
        )

    # -----------------------------------------------------
    # STEP 2: Verify and consume human approval
    # -----------------------------------------------------

    try:
        verify_and_consume_approval(
            approval=approval,
            recipient=recipient,
            subject=subject,
            body=body,
            secret=secret,
            db_path=db_path
        )

    except ApprovalError as exc:
        raise GatewayError(
            f"Email execution denied: {exc}"
        ) from exc

    # -----------------------------------------------------
    # STEP 3: Obtain the email sending function
    # -----------------------------------------------------

    if send_function is None:
        from tools.email_tools import send_email
        send_function = send_email

    # -----------------------------------------------------
    # STEP 4: Execute the approved email
    # -----------------------------------------------------

    try:
        send_result = send_function(
            recipient,
            subject,
            body
        )

    except Exception as exc:
        # The approval has already been consumed.
        # Never retry automatically because Gmail may
        # have accepted the email before the error occurred.

        raise GatewayError(
            "Email sending failed or its outcome is uncertain. "
            "Approval has been consumed. Do not retry automatically; "
            "reconcile the Gmail Sent folder first."
        ) from exc

    # -----------------------------------------------------
    # STEP 5: Extract Gmail message ID
    # -----------------------------------------------------

    message_id = None

    if isinstance(send_result, dict):
        message_id = send_result.get("message_id")

    # -----------------------------------------------------
    # STEP 6: Return execution result
    # -----------------------------------------------------

    return {
        "status": "SENT",
        "recipient": recipient,
        "subject": subject,
        "message_id": message_id,
        "message": "Email execution completed successfully."
    }
