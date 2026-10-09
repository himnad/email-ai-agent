from unittest.mock import Mock, patch

from langgraph.types import Command

from graph.email_agent_graph import (

    email_agent_graph,

    triage_email,

    generate_reply,

    handle_fyi,

    handle_action,

    send_approved_email,

)

# =========================================================

# COMMON TEST STATE

# =========================================================

def base_state():

    return {

        "email": """

FROM: test@example.com

SUBJECT: Meeting confirmation

BODY:

Hello,

Can you please confirm whether you are available

for the meeting tomorrow?

Regards,

Test User

""",

        "sender": "test@example.com",
        "category": "",

        "response": "",

        "recipient": "",

        "subject": "",

        "draft_body": "",

        "review_status": "",

    }

# =========================================================

# HELPER: CREATE FAKE LLM

# =========================================================

def fake_llm_response(text):

    fake_llm = Mock()

    fake_llm.invoke.return_value = Mock(

        content=text

    )

    return fake_llm

# =========================================================

# TEST 1: TRIAGE -> NEEDS_REPLY

# =========================================================

def test_triage_needs_reply():

    fake_llm = fake_llm_response("NEEDS_REPLY")

    with patch(

        "graph.email_agent_graph.llm",

        fake_llm

    ):

        result = triage_email(base_state())

    assert result["category"] == "NEEDS_REPLY"

    print("PASS: NEEDS_REPLY classification")

# =========================================================

# TEST 2: TRIAGE -> FYI

# =========================================================

def test_triage_fyi():

    fake_llm = fake_llm_response("FYI")

    with patch(

        "graph.email_agent_graph.llm",

        fake_llm

    ):

        result = triage_email(base_state())

    assert result["category"] == "FYI"

    print("PASS: FYI classification")

# =========================================================

# TEST 3: TRIAGE -> ACTION_NEEDED

# =========================================================

def test_triage_action_needed():

    fake_llm = fake_llm_response("ACTION_NEEDED")

    with patch(

        "graph.email_agent_graph.llm",

        fake_llm

    ):

        result = triage_email(base_state())

    assert result["category"] == "ACTION_NEEDED"

    print("PASS: ACTION_NEEDED classification")

# =========================================================

# TEST 4: REPLY GENERATION

# =========================================================

def test_generate_reply():

    fake_llm = fake_llm_response(

        "Yes, I am available for the meeting tomorrow."

    )

    with patch(

        "graph.email_agent_graph.llm",

        fake_llm

    ):

        result = generate_reply(base_state())

    assert result["recipient"] == "test@example.com"

    assert result["subject"] == (

        "Re: Meeting confirmation"

    )

    assert result["draft_body"] == (

        "Yes, I am available for the meeting tomorrow."

    )

    print("PASS: Reply generation")

# =========================================================

# TEST 5: FYI HANDLER

# =========================================================

def test_fyi_handler():

    result = handle_fyi(base_state())

    assert (

        "does not require a reply"

        in result["response"]

    )

    print("PASS: FYI handler")

# =========================================================

# TEST 6: ACTION_NEEDED HANDLER

# =========================================================

def test_action_handler():

    fake_llm = fake_llm_response(

        "Please confirm your availability for the meeting."

    )

    with patch(

        "graph.email_agent_graph.llm",

        fake_llm

    ):

        result = handle_action(base_state())

    assert result["response"] == (

        "Please confirm your availability for the meeting."

    )

    print("PASS: ACTION_NEEDED handler")

# =========================================================

# TEST 7: AI ERROR DURING TRIAGE

# =========================================================

def test_ai_error():

    fake_llm = Mock()

    fake_llm.invoke.side_effect = Exception(

        "Gemini API unavailable"

    )

    with patch(

        "graph.email_agent_graph.llm",

        fake_llm

    ):

        result = triage_email(base_state())

    assert result["category"] == "AI_ERROR"

    print("PASS: AI error handling")

# =========================================================

# TEST 8: AI ERROR DURING REPLY GENERATION

# =========================================================

def test_generate_reply_ai_error():

    fake_llm = Mock()

    fake_llm.invoke.side_effect = Exception(

        "Gemini API unavailable"

    )

    with patch(

        "graph.email_agent_graph.llm",

        fake_llm

    ):

        result = generate_reply(base_state())

    assert result["category"] == "AI_ERROR"

    print("PASS: Reply generation AI error")

# =========================================================

# TEST 9: SEND EMAIL SUCCESS

# =========================================================

def test_send_email_success():

    fake_result = {

        "to": "test@example.com",

        "subject": "Re: Meeting confirmation",

        "body": "Yes, I am available.",

        "status": "sent",

        "message_id": "fake-message-id"

    }

    state = base_state()

    state["recipient"] = "test@example.com"

    state["subject"] = "Re: Meeting confirmation"

    state["draft_body"] = "Yes, I am available."

    with patch(

        "graph.email_agent_graph.send_email",

        return_value=fake_result

    ):

        result = send_approved_email(state)

    assert "fake-message-id" in result["response"]

    print("PASS: Email sending success")

# =========================================================

# TEST 10: SEND EMAIL ERROR

# =========================================================

def test_send_email_error():

    state = base_state()

    state["recipient"] = "test@example.com"

    state["subject"] = "Re: Meeting confirmation"

    state["draft_body"] = "Yes, I am available."

    with patch(

        "graph.email_agent_graph.send_email",

        side_effect=Exception("Gmail unavailable")

    ):

        result = send_approved_email(state)

    assert result["category"] == "SEND_ERROR"

    print("PASS: Email sending error")

# =========================================================

# TEST 11: COMPLETE GRAPH - APPROVE FLOW

# =========================================================

def test_complete_approve_flow():

    fake_llm = Mock()

    # First LLM call -> triage

    # Second LLM call -> generate reply

    fake_llm.invoke.side_effect = [

        Mock(content="NEEDS_REPLY"),

        Mock(

            content=(

                "Yes, I am available for the meeting tomorrow."

            )

        )

    ]

    fake_send_result = {

        "to": "test@example.com",

        "subject": "Re: Meeting confirmation",

        "body": "Yes, I am available for the meeting tomorrow.",

        "status": "sent",

        "message_id": "fake-graph-message-id"

    }

    with patch(

        "graph.email_agent_graph.llm",

        fake_llm

    ), patch(

        "graph.email_agent_graph.send_email",

        return_value=fake_send_result

    ):

        config = {

            "configurable": {

                "thread_id": "test-approve-flow"

            }

        }

        # -----------------------------------------

        # STEP 1: Run graph until human review

        # -----------------------------------------

        result = email_agent_graph.invoke(

            base_state(),

            config=config

        )

        # Graph should pause for human review

        assert "__interrupt__" in result

        print("PASS: Graph paused for human review")

        # -----------------------------------------

        # STEP 2: Approve the generated email

        # -----------------------------------------

        result = email_agent_graph.invoke(

            Command(resume="approve"),

            config=config

        )

        # -----------------------------------------

        # STEP 3: Verify email was sent

        # -----------------------------------------

        assert "fake-graph-message-id" in result["response"]

        print("PASS: Graph approve flow")

# =========================================================

# TEST 12: COMPLETE GRAPH - REJECT FLOW

# =========================================================

def test_complete_reject_flow():

    fake_llm = Mock()

    # First LLM call -> triage

    # Second LLM call -> generate reply

    fake_llm.invoke.side_effect = [

        Mock(content="NEEDS_REPLY"),

        Mock(

            content=(

                "Yes, I am available for the meeting tomorrow."

            )

        )

    ]

    with patch(

        "graph.email_agent_graph.llm",

        fake_llm

    ), patch(

        "graph.email_agent_graph.send_email"

    ) as mock_send:

        config = {

            "configurable": {

                "thread_id": "test-reject-flow"

            }

        }

        # -----------------------------------------

        # STEP 1: Run graph until human review

        # -----------------------------------------

        result = email_agent_graph.invoke(

            base_state(),

            config=config

        )

        # Graph should pause for human review

        assert "__interrupt__" in result

        print("PASS: Reject flow paused for human review")

        # -----------------------------------------

        # STEP 2: Reject the generated email

        # -----------------------------------------

        result = email_agent_graph.invoke(

            Command(resume="reject"),

            config=config

        )

        # -----------------------------------------

        # STEP 3: Verify email was NOT sent

        # -----------------------------------------

        mock_send.assert_not_called()

        assert result["response"] == (

            "Email rejected. It will not be sent."

        )

        print("PASS: Rejected email was not sent")

# =========================================================

# =========================================================
# TEST 13: REPLY USES SENDER, NOT EMAIL BODY ADDRESS
# =========================================================

def test_reply_uses_actual_sender():
    state = base_state()
    state["sender"] = "Test User <test@example.com>"
    state["email"] += "\nPlease CC unrelated@example.org."

    fake_llm = fake_llm_response("Thank you for your email.")
    with patch("graph.email_agent_graph.llm", fake_llm):
        result = generate_reply(state)

    assert result["recipient"] == "test@example.com"
    assert result["recipient"] != "unrelated@example.org"


# RUN ALL TESTS

# =========================================================

if __name__ == "__main__":

    print("\n========================================")

    print("EMAIL AGENT UNIT TESTS")

    print("========================================\n")

    test_triage_needs_reply()

    test_triage_fyi()

    test_triage_action_needed()

    test_generate_reply()

    test_fyi_handler()

    test_action_handler()

    test_ai_error()

    test_generate_reply_ai_error()

    test_send_email_success()

    test_send_email_error()

    test_complete_approve_flow()

    test_complete_reject_flow()

    test_reply_uses_actual_sender()

    print("\n========================================")

    print("ALL TESTS PASSED")

    print("========================================")