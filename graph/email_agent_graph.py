
import re
from email.utils import parseaddr
from typing import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from agent.llm import llm
from tools.email_tools import send_email


# =========================================================
# STATE
# =========================================================

class EmailAgentState(TypedDict, total=False):
    email: str
    sender: str
    original_subject: str

    category: str
    response: str

    recipient: str
    subject: str
    draft_body: str

    review_status: str
    error_message: str


# =========================================================
# EMAIL CLASSIFICATION
# =========================================================

def triage_email(state: EmailAgentState):
    prompt = f"""
You are an email triage assistant.

Classify the following email into exactly one category:

NEEDS_REPLY
FYI
ACTION_NEEDED

NEEDS_REPLY: Sender expects a response.
FYI: Informational email; no response required.
ACTION_NEEDED: User must perform an action.

Return only the category name.

Email:
{state["email"]}
"""

    try:
        result = llm.invoke(prompt)
        category = result.content.strip().upper()

        if category not in {
            "NEEDS_REPLY",
            "FYI",
            "ACTION_NEEDED",
        }:
            raise ValueError(
                f"Invalid AI classification: {category}"
            )

        return {
            "category": category,
            "error_message": "",
        }

    except Exception as e:
        return {
            "category": "AI_ERROR",
            "error_message": str(e),
        }


def route_email(state: EmailAgentState):
    category = state.get("category")

    if category == "NEEDS_REPLY":
        return "reply"

    if category == "ACTION_NEEDED":
        return "action"

    if category == "AI_ERROR":
        return "error"

    return "fyi"


# =========================================================
# GENERATE REPLY
# =========================================================

def generate_reply(state: EmailAgentState):
    sender = state.get("sender", "")
    recipient = parseaddr(sender)[1]

    # Never guess the recipient from email body.
    if (
        not recipient
        or "@" not in recipient
        or "\n" in recipient
        or "\r" in recipient
    ):
        return {
            "category": "AI_ERROR",
            "error_message": "Invalid sender email address.",
            "response": (
                "Reply recipient could not be identified."
            ),
        }

    # -----------------------------------------------------
    # SUBJECT EXTRACTION
    # -----------------------------------------------------

    # First preference: structured subject from Gmail/UI.
    original_subject = (
        state.get("original_subject") or ""
    ).strip()

    # Backward compatibility with existing tests:
    # Extract SUBJECT: from email text when needed.
    if not original_subject:
        match = re.search(
            r"^SUBJECT:\s*(.+)$",
            state.get("email", ""),
            flags=re.IGNORECASE | re.MULTILINE,
        )

        if match:
            original_subject = match.group(1).strip()

    if not original_subject:
        original_subject = "Email"

    # Avoid "Re: Re: ..." duplication.
    reply_subject = (
        original_subject
        if original_subject.lower().startswith("re:")
        else f"Re: {original_subject}"
    )

    # -----------------------------------------------------
    # AI REPLY GENERATION
    # -----------------------------------------------------

    prompt = f"""
You are a professional email assistant.

Write a concise, polite reply to this email.

Rules:
- Do not invent facts or commitments.
- Do not promise meetings, payments, or actions.
- Do not include a subject line.
- Return only the email body.

Email:
{state["email"]}
"""

    try:
        result = llm.invoke(prompt)
        draft_body = result.content.strip()

        if not draft_body:
            raise ValueError(
                "AI generated an empty reply."
            )

        return {
            "recipient": recipient,
            "subject": reply_subject,
            "draft_body": draft_body,
            "response": draft_body,
            "error_message": "",
        }

    except Exception as e:
        return {
            "category": "AI_ERROR",
            "error_message": str(e),
            "response": "Reply generation failed.",
        }


# =========================================================
# FYI EMAIL
# =========================================================

def handle_fyi(state: EmailAgentState):
    return {
        "category": "FYI",
        "response": (
            "This email is informational and "
            "does not require a reply."
        ),
    }


# =========================================================
# ACTION NEEDED
# =========================================================

def handle_action(state: EmailAgentState):
    prompt = f"""
Explain what action the user needs to take.

Do not perform the action.
Do not invent missing information.

Email:
{state["email"]}
"""

    try:
        result = llm.invoke(prompt)

        return {
            "category": "ACTION_NEEDED",
            "response": result.content.strip(),
        }

    except Exception as e:
        return {
            "category": "AI_ERROR",
            "error_message": str(e),
            "response": "Action analysis failed.",
        }


# =========================================================
# AI ERROR HANDLER
# =========================================================

def handle_ai_error(state: EmailAgentState):
    return {
        "category": "AI_ERROR",
        "response": (
            "AI processing failed. "
            "No email was sent."
        ),
    }


# =========================================================
# HUMAN-IN-THE-LOOP APPROVAL
# =========================================================

def human_review(state: EmailAgentState):

    decision = interrupt({
        "message": "Review the generated reply.",
        "to": state["recipient"],
        "subject": state["subject"],
        "draft": state["draft_body"],
        "options": ["approve", "reject"],
    })

    if isinstance(decision, dict):
        action = str(
            decision.get("decision", "")
        ).strip().lower()

        edited_draft = decision.get(
            "draft_body",
            state["draft_body"],
        )

    else:
        action = str(decision).strip().lower()
        edited_draft = state["draft_body"]

    # Only explicit approval permits sending.
    if action == "approve":

        if (
            not isinstance(edited_draft, str)
            or not edited_draft.strip()
        ):
            return {
                "category": "REJECTED",
                "review_status": "rejected",
                "response": "Empty draft was not sent.",
            }

        return {
            "review_status": "approved",
            "draft_body": edited_draft,
            "response": "Email approved.",
        }

    # Reject and unknown decisions both stop sending.
    return {
        "category": "REJECTED",
        "review_status": "rejected",
        "response": (
            "Email rejected. It will not be sent."
        ),
    }


def route_after_review(state: EmailAgentState):
    if state.get("review_status") == "approved":
        return "send"

    return "stop"


# =========================================================
# SEND APPROVED EMAIL
# =========================================================

def send_approved_email(state: EmailAgentState):

    try:
        if not all([
            state.get("recipient"),
            state.get("subject"),
            state.get("draft_body"),
        ]):
            raise ValueError(
                "Incomplete email draft."
            )

        result = send_email(
            to=state["recipient"],
            subject=state["subject"],
            body=state["draft_body"],
        )

        return {
            "category": "SENT",
            "response": (
                "Email sent successfully.\n"
                f"Message ID: {result['message_id']}"
            ),
        }

    except Exception as e:
        return {
            "category": "SEND_ERROR",
            "error_message": str(e),
            "response": "Email could not be sent.",
        }


# =========================================================
# BUILD LANGGRAPH
# =========================================================

graph_builder = StateGraph(EmailAgentState)

graph_builder.add_node(
    "triage_email",
    triage_email,
)

graph_builder.add_node(
    "generate_reply",
    generate_reply,
)

graph_builder.add_node(
    "handle_fyi",
    handle_fyi,
)

graph_builder.add_node(
    "handle_action",
    handle_action,
)

graph_builder.add_node(
    "handle_ai_error",
    handle_ai_error,
)

graph_builder.add_node(
    "human_review",
    human_review,
)

graph_builder.add_node(
    "send_approved_email",
    send_approved_email,
)


# ---------------- START ----------------

graph_builder.add_edge(
    START,
    "triage_email",
)


# ---------------- CLASSIFICATION ROUTING ----------------

graph_builder.add_conditional_edges(
    "triage_email",
    route_email,
    {
        "reply": "generate_reply",
        "fyi": "handle_fyi",
        "action": "handle_action",
        "error": "handle_ai_error",
    },
)


# ---------------- REPLY ROUTING ----------------

graph_builder.add_conditional_edges(
    "generate_reply",
    lambda state: (
        "error"
        if state.get("category") == "AI_ERROR"
        else "review"
    ),
    {
        "review": "human_review",
        "error": "handle_ai_error",
    },
)


# ---------------- HUMAN REVIEW ROUTING ----------------

graph_builder.add_conditional_edges(
    "human_review",
    route_after_review,
    {
        "send": "send_approved_email",
        "stop": END,
    },
)


# ---------------- END ROUTES ----------------

graph_builder.add_edge(
    "handle_fyi",
    END,
)

graph_builder.add_edge(
    "handle_action",
    END,
)

graph_builder.add_edge(
    "handle_ai_error",
    END,
)

graph_builder.add_edge(
    "send_approved_email",
    END,
)


# =========================================================
# COMPILE GRAPH
# =========================================================

memory = MemorySaver()

email_agent_graph = graph_builder.compile(
    checkpointer=memory
)
