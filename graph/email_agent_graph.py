import re
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from agent.llm import llm
from tools.email_tools import send_email


class EmailAgentState(TypedDict):
    email: str
    category: str
    response: str

    recipient: str
    subject: str
    draft_body: str

    # Stores the human review decision
    review_status: str


# =========================================================
# 1. TRIAGE EMAIL
# =========================================================

def triage_email(state: EmailAgentState):
    """
    Classify the incoming email.

    If Gemini fails because of quota, timeout,
    network error, etc., mark the email as AI_ERROR.
    """

    prompt = f"""
You are an email triage assistant.

Classify the following email into exactly ONE category.

NEEDS_REPLY
- The sender expects a response from the user.

FYI
- The email is informational and does not require a response.

ACTION_NEEDED
- The user needs to perform some action.

Return ONLY one of:

NEEDS_REPLY
FYI
ACTION_NEEDED

Email:
{state["email"]}
"""

    try:

        # Ask Gemini to classify the email
        result = llm.invoke(prompt)

        category = result.content.strip().upper()

    except Exception as e:

        print("\nGemini API error during triage:")
        print(e)

        # Do NOT incorrectly classify the email.
        # The email will remain unread.
        category = "AI_ERROR"

    # Validate Gemini's response
    if category not in [
        "NEEDS_REPLY",
        "FYI",
        "ACTION_NEEDED",
        "AI_ERROR"
    ]:
        category = "AI_ERROR"

    return {
        "category": category
    }


# =========================================================
# 2. ROUTE EMAIL
# =========================================================

def route_email(state: EmailAgentState):
    """
    Decide which workflow branch to follow.
    """

    if state["category"] == "NEEDS_REPLY":
        return "reply"

    elif state["category"] == "ACTION_NEEDED":
        return "action"

    elif state["category"] == "AI_ERROR":
        return "error"

    return "fyi"


# =========================================================
# 3. GENERATE REPLY
# =========================================================

def generate_reply(state: EmailAgentState):
    """
    Generate a reply for emails that require a response.

    If Gemini fails, return AI_ERROR instead of
    crashing the entire application.
    """

    email = state["email"]

    # -----------------------------------------------------
    # Extract sender email address
    # -----------------------------------------------------

    match = re.search(
        r"[\w\.-]+@[\w\.-]+\.\w+",
        email
    )

    recipient = match.group(0) if match else ""

    # -----------------------------------------------------
    # Extract original subject
    # -----------------------------------------------------

    subject_match = re.search(
        r"SUBJECT:\s*(.*)",
        email
    )

    original_subject = (
        subject_match.group(1).strip()
        if subject_match
        else "Email"
    )

    # -----------------------------------------------------
    # Prompt Gemini
    # -----------------------------------------------------

    prompt = f"""
You are an email assistant.

Write a short, professional reply to the following email.

Rules:
- Do not invent information.
- Do not add unnecessary details.
- Keep the reply concise.
- Return ONLY the email body.
- Do not include a subject.
- Do not include explanations.

Email:
{email}
"""

    try:

        result = llm.invoke(prompt)

        draft_body = result.content.strip()

    except Exception as e:

        print("\nGemini API error while generating reply:")
        print(e)

        return {
            "category": "AI_ERROR",
            "response": (
                "AI processing failed while generating "
                "the reply. The email should be retried later."
            )
        }

    return {
        "recipient": recipient,
        "subject": f"Re: {original_subject}",
        "draft_body": draft_body,
        "response": draft_body
    }


# =========================================================
# 4. HANDLE FYI
# =========================================================

def handle_fyi(state: EmailAgentState):
    """
    Handle informational emails.
    """

    return {
        "response": (
            "This email is informational "
            "and does not require a reply."
        )
    }


# =========================================================
# 5. HANDLE ACTION NEEDED
# =========================================================

def handle_action(state: EmailAgentState):
    """
    Explain what action the user needs to take.

    If Gemini fails, return AI_ERROR instead of
    crashing the application.
    """

    prompt = f"""
You are an email assistant.

Explain clearly what action the user needs to take.

Do not perform the action.
Only explain what the user needs to do.

Email:
{state["email"]}
"""

    try:

        result = llm.invoke(prompt)

        return {
            "response": result.content.strip()
        }

    except Exception as e:

        print("\nGemini API error while analyzing action:")
        print(e)

        return {
            "category": "AI_ERROR",
            "response": (
                "AI processing failed while determining "
                "the required action. The email should be "
                "retried later."
            )
        }


# =========================================================
# 6. HANDLE AI ERROR
# =========================================================

def handle_ai_error(state: EmailAgentState):
    """
    Handle cases where Gemini is unavailable.

    The email is NOT treated as successfully processed.
    It should remain unread so it can be retried later.
    """

    return {
        "category": "AI_ERROR",
        "response": (
            "AI processing failed. "
            "The email was not classified and "
            "should be retried later."
        )
    }


# =========================================================
# 7. HUMAN REVIEW
# =========================================================

def human_review(state: EmailAgentState):
    """
    Pause the workflow and ask the human
    to approve or reject the generated draft.
    """

    decision = interrupt(
        {
            "message": "Please review the generated email draft.",

            "to": state["recipient"],

            "subject": state["subject"],

            "draft": state["draft_body"],

            "options": [
                "approve",
                "reject"
            ]
        }
    )

    decision = str(decision).strip().lower()

    if decision == "approve":

        return {
            "review_status": "approved",
            "response": "Email approved."
        }

    return {
        "review_status": "rejected",
        "response": (
            "Email rejected. It will not be sent."
        )
    }


# =========================================================
# 8. ROUTE AFTER HUMAN REVIEW
# =========================================================

def route_after_review(state: EmailAgentState):
    """
    Decide whether the approved email should be sent.
    """

    if state["review_status"] == "approved":
        return "send"

    return "stop"


# =========================================================
# 9. SEND APPROVED EMAIL
# =========================================================
def send_approved_email(state: EmailAgentState):
    """
    Send the email only after human approval.
    """

    try:

        result = send_email(
            to=state["recipient"],
            subject=state["subject"],
            body=state["draft_body"]
        )

        return {
            "response": str(result)
        }

    except Exception as e:

        print("\nGmail sending error:")
        print(e)

        return {
            "category": "SEND_ERROR",
            "response": (
                "The email could not be sent. "
                "Please try again later."
            )
        }


# =========================================================
# BUILD LANGGRAPH
# =========================================================

graph_builder = StateGraph(EmailAgentState)


# =========================================================
# ADD NODES
# =========================================================

graph_builder.add_node(
    "triage_email",
    triage_email
)

graph_builder.add_node(
    "generate_reply",
    generate_reply
)

graph_builder.add_node(
    "handle_fyi",
    handle_fyi
)

graph_builder.add_node(
    "handle_action",
    handle_action
)

graph_builder.add_node(
    "handle_ai_error",
    handle_ai_error
)

graph_builder.add_node(
    "human_review",
    human_review
)

graph_builder.add_node(
    "send_approved_email",
    send_approved_email
)


# =========================================================
# START → TRIAGE
# =========================================================

graph_builder.add_edge(
    START,
    "triage_email"
)


# =========================================================
# TRIAGE → APPROPRIATE BRANCH
# =========================================================

graph_builder.add_conditional_edges(
    "triage_email",
    route_email,
    {
        "reply": "generate_reply",
        "fyi": "handle_fyi",
        "action": "handle_action",
        "error": "handle_ai_error"
    }
)


# =========================================================
# NEEDS_REPLY FLOW
# =========================================================

graph_builder.add_edge(
    "generate_reply",
    "human_review"
)


# =========================================================
# HUMAN APPROVAL ROUTING
# =========================================================

graph_builder.add_conditional_edges(
    "human_review",
    route_after_review,
    {
        "send": "send_approved_email",
        "stop": END
    }
)


# =========================================================
# OTHER BRANCHES
# =========================================================

graph_builder.add_edge(
    "handle_fyi",
    END
)

graph_builder.add_edge(
    "handle_action",
    END
)

graph_builder.add_edge(
    "handle_ai_error",
    END
)


# =========================================================
# SENDING EMAIL
# =========================================================

graph_builder.add_edge(
    "send_approved_email",
    END
)


# =========================================================
# MEMORY / CHECKPOINTING
# =========================================================

memory = MemorySaver()

email_agent_graph = graph_builder.compile(
    checkpointer=memory
)