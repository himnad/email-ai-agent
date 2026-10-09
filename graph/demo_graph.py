
from typing import TypedDict
from email.utils import parseaddr

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver

from agent.llm import llm


class DemoEmailState(TypedDict, total=False):
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


# 1. Classify the sample email
def triage_email(state: DemoEmailState):
    prompt = f"""
Classify this email into exactly one category:
NEEDS_REPLY, FYI, ACTION_NEEDED.

NEEDS_REPLY: Sender expects a response.
FYI: Informational email.
ACTION_NEEDED: User needs to perform an action.

Return only the category.

Email:
{state["email"]}
"""

    try:
        result = llm.invoke(prompt)
        category = result.content.strip().upper()

        if category not in {
            "NEEDS_REPLY", "FYI", "ACTION_NEEDED"
        }:
            raise ValueError("Invalid AI classification")

        return {"category": category, "error_message": ""}

    except Exception as e:
        return {
            "category": "AI_ERROR",
            "error_message": str(e),
        }


def route_email(state: DemoEmailState):
    category = state.get("category")

    if category == "NEEDS_REPLY":
        return "reply"
    if category == "ACTION_NEEDED":
        return "action"
    if category == "AI_ERROR":
        return "error"
    return "fyi"


# 2. Generate AI reply
def generate_reply(state: DemoEmailState):
    recipient = parseaddr(state.get("sender", ""))[1]

    if not recipient or "@" not in recipient:
        return {
            "category": "AI_ERROR",
            "error_message": "Invalid sender address.",
        }

    original_subject = (
        state.get("original_subject") or "Email"
    ).strip()

    reply_subject = (
        original_subject
        if original_subject.lower().startswith("re:")
        else f"Re: {original_subject}"
    )

    prompt = f"""
Write a concise and professional email reply.

Rules:
- Do not invent facts.
- Do not make commitments.
- Return only the email body.

Email:
{state["email"]}
"""

    try:
        result = llm.invoke(prompt)
        draft = result.content.strip()

        if not draft:
            raise ValueError("Empty AI response")

        return {
            "recipient": recipient,
            "subject": reply_subject,
            "draft_body": draft,
            "response": draft,
        }

    except Exception as e:
        return {
            "category": "AI_ERROR",
            "error_message": str(e),
        }


# 3. FYI emails
def handle_fyi(state: DemoEmailState):
    return {
        "category": "FYI",
        "response": "Informational email. No reply needed.",
    }


# 4. Action-needed emails
def handle_action(state: DemoEmailState):
    prompt = f"""
Explain what action is required.
Do not perform any action.

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
        }


# 5. AI errors
def handle_ai_error(state: DemoEmailState):
    return {
        "category": "AI_ERROR",
        "response": "AI processing failed.",
    }


# 6. Human approval
def human_review(state: DemoEmailState):
    decision = interrupt({
        "message": "Review the generated demo reply.",
        "to": state["recipient"],
        "subject": state["subject"],
        "draft": state["draft_body"],
        "options": ["approve", "reject"],
    })

    action = str(decision).strip().lower()

    if action == "approve":
        return {
            "review_status": "approved",
            "response": "Demo reply approved.",
        }

    return {
        "category": "REJECTED",
        "review_status": "rejected",
        "response": "Demo reply rejected. Nothing sent.",
    }


def route_after_review(state: DemoEmailState):
    return (
        "simulate"
        if state.get("review_status") == "approved"
        else "stop"
    )


# 7. SIMULATION ONLY - No Gmail API
def simulate_send(state: DemoEmailState):
    return {
        "category": "SIMULATED_SENT",
        "response": (
            "Demo email approved successfully. "
            "No real email was sent."
        ),
    }


# 8. Build demo graph
builder = StateGraph(DemoEmailState)

builder.add_node("triage", triage_email)
builder.add_node("generate_reply", generate_reply)
builder.add_node("handle_fyi", handle_fyi)
builder.add_node("handle_action", handle_action)
builder.add_node("handle_ai_error", handle_ai_error)
builder.add_node("human_review", human_review)
builder.add_node("simulate_send", simulate_send)

builder.add_edge(START, "triage")

builder.add_conditional_edges(
    "triage",
    route_email,
    {
        "reply": "generate_reply",
        "fyi": "handle_fyi",
        "action": "handle_action",
        "error": "handle_ai_error",
    },
)

builder.add_conditional_edges(
    "generate_reply",
    lambda state: (
        "error"
        if state.get("category") == "AI_ERROR"
        else "review"
    ),
    {
        "error": "handle_ai_error",
        "review": "human_review",
    },
)

builder.add_conditional_edges(
    "human_review",
    route_after_review,
    {
        "simulate": "simulate_send",
        "stop": END,
    },
)

builder.add_edge("handle_fyi", END)
builder.add_edge("handle_action", END)
builder.add_edge("handle_ai_error", END)
builder.add_edge("simulate_send", END)

demo_graph = builder.compile(
    checkpointer=MemorySaver()
)
