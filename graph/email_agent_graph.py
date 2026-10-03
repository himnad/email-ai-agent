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
    review_status: str
    error_message: str


def triage_email(state: EmailAgentState):
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
        result = llm.invoke(prompt)
        category = result.content.strip().upper()

    except Exception as e:
        print("\nGemini API error during triage:")
        print(e)

        return {
            "category": "AI_ERROR",
            "error_message": str(e),
        }

    if category not in [
        "NEEDS_REPLY",
        "FYI",
        "ACTION_NEEDED",
    ]:
        return {
            "category": "AI_ERROR",
            "error_message": (
                "Gemini returned an invalid classification: "
                f"{category}"
            ),
        }

    return {
        "category": category,
        "error_message": "",
    }


def route_email(state: EmailAgentState):
    if state["category"] == "NEEDS_REPLY":
        return "reply"

    elif state["category"] == "ACTION_NEEDED":
        return "action"

    elif state["category"] == "AI_ERROR":
        return "error"

    return "fyi"


def generate_reply(state: EmailAgentState):
    email = state["email"]

    match = re.search(
        r"[\w\.-]+@[\w\.-]+\.\w+",
        email
    )

    recipient = match.group(0) if match else ""

    subject_match = re.search(
        r"SUBJECT:\s*(.*)",
        email
    )

    original_subject = (
        subject_match.group(1).strip()
        if subject_match
        else "Email"
    )

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
            "error_message": str(e),
            "response": (
                "AI processing failed while generating "
                "the reply. The email should be retried later."
            ),
        }

    return {
        "recipient": recipient,
        "subject": f"Re: {original_subject}",
        "draft_body": draft_body,
        "response": draft_body,
        "error_message": "",
    }


def handle_fyi(state: EmailAgentState):
    return {
        "category": "FYI",
        "response": (
            "This email is informational "
            "and does not require a reply."
        )
    }


def handle_action(state: EmailAgentState):
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
            "category": "ACTION_NEEDED",
            "response": result.content.strip()
        }

    except Exception as e:
        print("\nGemini API error while analyzing action:")
        print(e)

        return {
            "category": "AI_ERROR",
            "error_message": str(e),
            "response": (
                "AI processing failed while determining "
                "the required action. The email should be "
                "retried later."
            ),
        }


def handle_ai_error(state: EmailAgentState):
    return {
        "category": "AI_ERROR",
        "response": (
            "AI processing failed. "
            "The email was not classified and "
            "should be retried later."
        ),
    }


def human_review(state: EmailAgentState):
    decision = interrupt(
        {
            "message": "Please review the generated email draft.",
            "to": state["recipient"],
            "subject": state["subject"],
            "draft": state["draft_body"],
            "options": [
                "approve",
                "reject",
            ],
        }
    )

    if isinstance(decision, dict):
        action = str(
            decision.get("decision", "")
        ).strip().lower()

        edited_draft = decision.get(
            "draft_body",
            state["draft_body"]
        )

    else:
        action = str(decision).strip().lower()
        edited_draft = state["draft_body"]

    if action == "approve":
        return {
            "review_status": "approved",
            "draft_body": edited_draft,
            "response": "Email approved.",
        }

    return {
        "category": "REJECTED",
        "review_status": "rejected",
        "response": "Email rejected. It will not be sent.",
    }


def route_after_review(state: EmailAgentState):
    if state["review_status"] == "approved":
        return "send"

    return "stop"


def send_approved_email(state: EmailAgentState):
    try:
        result = send_email(
            to=state["recipient"],
            subject=state["subject"],
            body=state["draft_body"],
        )

        return {
            "category": "SENT",
            "response": (
                "Email sent successfully.\n\n"
                f"Message ID: {result['message_id']}"
            ),
        }

    except Exception as e:
        print("\nGmail sending error:")
        print(e)

        return {
            "category": "SEND_ERROR",
            "error_message": str(e),
            "response": (
                "The email could not be sent. "
                "Please try again later."
            ),
        }


graph_builder = StateGraph(EmailAgentState)

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


graph_builder.add_edge(
    START,
    "triage_email"
)


graph_builder.add_conditional_edges(
    "triage_email",
    route_email,
    {
        "reply": "generate_reply",
        "fyi": "handle_fyi",
        "action": "handle_action",
        "error": "handle_ai_error",
    }
)


graph_builder.add_conditional_edges(
    "generate_reply",
    lambda state: (
        "error"
        if state["category"] == "AI_ERROR"
        else "review"
    ),
    {
        "review": "human_review",
        "error": "handle_ai_error",
    }
)


graph_builder.add_conditional_edges(
    "human_review",
    route_after_review,
    {
        "send": "send_approved_email",
        "stop": END,
    }
)


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

graph_builder.add_edge(
    "send_approved_email",
    END
)


memory = MemorySaver()

email_agent_graph = graph_builder.compile(
    checkpointer=memory
)