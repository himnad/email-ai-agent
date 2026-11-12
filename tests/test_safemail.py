
import os
import tempfile

from safemail.gateway import (
    execute_approved_email,
    GatewayError
)

from safemail.authorization import (
    issue_approval,
    verify_and_consume_approval,
    ApprovalError
)

from safemail.recipient_validator import (
    resolve_reply_recipient,
    validate_email_address,
    RecipientValidationError
)

from safemail.policy_engine import (
    evaluate_email_action,
    REQUIRE_HUMAN_REVIEW,
    BLOCK
)


SECRET = "test-secret-key-for-safemail-2026"


# ---------------- AUTHORIZATION TESTS ----------------

def test_valid_approval():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "test.db")

        approval = issue_approval(
            "manager@company.com",
            "Meeting",
            "I confirm my availability.",
            SECRET,
            db
        )

        assert verify_and_consume_approval(
            approval,
            "manager@company.com",
            "Meeting",
            "I confirm my availability.",
            SECRET,
            db
        )

        print("PASS: Valid approval accepted")


def test_modified_email():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "test.db")

        approval = issue_approval(
            "manager@company.com",
            "Meeting",
            "Original body",
            SECRET,
            db
        )

        try:
            verify_and_consume_approval(
                approval,
                "attacker@example.com",
                "Meeting",
                "Original body",
                SECRET,
                db
            )

            assert False, "Modified recipient was accepted"

        except ApprovalError:
            print("PASS: Modified recipient rejected")


def test_replay_attack():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "test.db")

        approval = issue_approval(
            "manager@company.com",
            "Meeting",
            "Approved body",
            SECRET,
            db
        )

        verify_and_consume_approval(
            approval,
            "manager@company.com",
            "Meeting",
            "Approved body",
            SECRET,
            db
        )

        try:
            verify_and_consume_approval(
                approval,
                "manager@company.com",
                "Meeting",
                "Approved body",
                SECRET,
                db
            )

            assert False, "Replay was accepted"

        except ApprovalError:
            print("PASS: Replayed approval rejected")


# ---------------- RECIPIENT VALIDATION TESTS ----------------

def test_recipient_validation():
    assert validate_email_address(
        "manager@company.com"
    ) == "manager@company.com"

    print("PASS: Valid email address accepted")

    try:
        validate_email_address("invalid-email")
        assert False, "Invalid address was accepted"

    except RecipientValidationError:
        print("PASS: Invalid email address rejected")


def test_multiple_recipients():
    try:
        resolve_reply_recipient(
            "manager@company.com, attacker@example.com"
        )

        assert False, "Multiple recipients were accepted"

    except RecipientValidationError:
        print("PASS: Multiple recipients rejected")


def test_reply_to_mismatch():
    try:
        resolve_reply_recipient(
            "manager@company.com",
            "attacker@example.com"
        )

        assert False, "Mismatched Reply-To was accepted"

    except RecipientValidationError:
        print("PASS: Mismatched Reply-To rejected")


def test_valid_reply_to():
    recipient = resolve_reply_recipient(
        "Manager <manager@company.com>",
        "manager@company.com"
    )

    assert recipient == "manager@company.com"

    print("PASS: Matching Reply-To accepted")


# ---------------- POLICY ENGINE TESTS ----------------

def test_policy_valid_email():
    result = evaluate_email_action(
        "manager@company.com",
        "Meeting",
        "I confirm my availability.",
        "manager@company.com"
    )

    assert result["decision"] == REQUIRE_HUMAN_REVIEW

    print("PASS: Valid email requires human approval")


def test_policy_blocks_invalid_recipient():
    result = evaluate_email_action(
        "invalid-email",
        "Meeting",
        "Hello",
        "manager@company.com"
    )

    assert result["decision"] == BLOCK

    print("PASS: Policy blocks invalid recipient")


def test_policy_blocks_sensitive_data():
    result = evaluate_email_action(
        "manager@company.com",
        "Credentials",
        "Your password: Secret123",
        "manager@company.com"
    )

    assert result["decision"] == BLOCK

    print("PASS: Policy blocks sensitive information")


def test_policy_detects_reply_to_mismatch():
    result = evaluate_email_action(
        "attacker@example.com",
        "Meeting",
        "Hello",
        "manager@company.com",
        "attacker@example.com"
    )

    assert result["decision"] == BLOCK

    print("PASS: Policy blocks Reply-To mismatch")


def test_policy_blocks_header_injection():
    result = evaluate_email_action(
        "manager@company.com",
        "Meeting\r\nBcc: attacker@example.com",
        "Hello",
        "manager@company.com"
    )

    assert result["decision"] == BLOCK

    print("PASS: Policy blocks header injection")


# ---------------- EXECUTION GATEWAY TESTS ----------------

def test_gateway_success():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "test.db")
        sent_emails = []

        def mock_send(to, subject, body):
            sent_emails.append((to, subject, body))
            return {"message_id": "test-message-123"}

        approval = issue_approval(
            "manager@company.com",
            "Meeting",
            "I confirm my availability.",
            SECRET,
            db
        )

        result = execute_approved_email(
            approval,
            "manager@company.com",
            "Meeting",
            "I confirm my availability.",
            SECRET,
            db,
            from_header="manager@company.com",
            send_function=mock_send
        )

        assert result["status"] == "SENT"
        assert len(sent_emails) == 1

        print("PASS: Gateway sends approved email")


def test_gateway_blocks_modified_content():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "test.db")
        sent_emails = []

        approval = issue_approval(
            "manager@company.com",
            "Meeting",
            "Original body",
            SECRET,
            db
        )

        try:
            execute_approved_email(
                approval,
                "manager@company.com",
                "Meeting",
                "Modified body",
                SECRET,
                db,
                from_header="manager@company.com",
                send_function=lambda *args: sent_emails.append(args)
            )

            assert False, "Modified email was sent"

        except GatewayError:
            assert len(sent_emails) == 0
            print("PASS: Gateway rejects modified content")


def test_gateway_blocks_sensitive_data():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "test.db")
        sent_emails = []

        approval = issue_approval(
            "manager@company.com",
            "Credentials",
            "Your password: Secret123",
            SECRET,
            db
        )

        try:
            execute_approved_email(
                approval,
                "manager@company.com",
                "Credentials",
                "Your password: Secret123",
                SECRET,
                db,
                from_header="manager@company.com",
                send_function=lambda *args: sent_emails.append(args)
            )

            assert False, "Sensitive email was sent"

        except GatewayError:
            assert len(sent_emails) == 0
            print("PASS: Gateway blocks sensitive email")


def test_gateway_prevents_replay():
    with tempfile.TemporaryDirectory() as tmp:
        db = os.path.join(tmp, "test.db")
        sent_emails = []

        approval = issue_approval(
            "manager@company.com",
            "Meeting",
            "Approved body",
            SECRET,
            db
        )

        def mock_send(to, subject, body):
            sent_emails.append((to, subject, body))
            return {"message_id": "test-message-123"}

        execute_approved_email(
            approval,
            "manager@company.com",
            "Meeting",
            "Approved body",
            SECRET,
            db,
            from_header="manager@company.com",
            send_function=mock_send
        )

        try:
            execute_approved_email(
                approval,
                "manager@company.com",
                "Meeting",
                "Approved body",
                SECRET,
                db,
                from_header="manager@company.com",
                send_function=mock_send
            )

            assert False, "Replayed approval was accepted"

        except GatewayError:
            assert len(sent_emails) == 1
            print("PASS: Gateway prevents duplicate execution")


# ---------------- RUN ALL TESTS ----------------

if __name__ == "__main__":
    test_valid_approval()
    test_modified_email()
    test_replay_attack()

    test_recipient_validation()
    test_multiple_recipients()
    test_reply_to_mismatch()
    test_valid_reply_to()

    test_policy_valid_email()
    test_policy_blocks_invalid_recipient()
    test_policy_blocks_sensitive_data()
    test_policy_detects_reply_to_mismatch()
    test_policy_blocks_header_injection()

    test_gateway_success()
    test_gateway_blocks_modified_content()
    test_gateway_blocks_sensitive_data()
    test_gateway_prevents_replay()

    print("\nALL SAFEMAIL TESTS PASSED")
