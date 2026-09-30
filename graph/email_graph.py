from langgraph.graph import StateGraph, START, END
from typing import TypedDict

from agent.llm import llm


class EmailState(TypedDict):
    email: str
    category: str
    response: str


# -------------------------
# 1. Triage Email
# -------------------------
def triage_email(state: EmailState):
    prompt = f"""
You are an email triage assistant.

Classify the email into exactly ONE category:

NEEDS_REPLY
- The sender expects a response.

FYI
- The email is informational and does not require a response.

ACTION_NEEDED
- The user needs to perform some action.

Return ONLY the category name.

Email:
{state["email"]}
"""

    result = llm.invoke(prompt)

    return {
        "category": result.content.strip().upper()
    }


# -------------------------
# 2. Decide which path
# -------------------------
def route_email(state: EmailState):
    category = state["category"]

    if category == "NEEDS_REPLY":
        return "reply"

    elif category == "FYI":
        return "fyi"

    elif category == "ACTION_NEEDED":
        return "action"

    # Safety fallback
    return "reply"


# -------------------------
# 3. Reply Node
# -------------------------
def reply_email(state: EmailState):
    prompt = f"""
You are an email assistant.

The following email requires a reply.

Draft a short, professional response.

Email:
{state["email"]}
"""

    result = llm.invoke(prompt)

    return {
        "response": result.content
    }


# -------------------------
# 4. FYI Node
# -------------------------
def handle_fyi(state: EmailState):
    return {
        "response": "This email is informational and does not require a reply."
    }


# -------------------------
# 5. Action Node
# -------------------------
def handle_action(state: EmailState):
    prompt = f"""
You are an email assistant.

The following email requires the user to take some action.

Clearly explain what action the user needs to take.

Email:
{state["email"]}
"""

    result = llm.invoke(prompt)

    return {
        "response": result.content
    }


# -------------------------
# Build Graph
# -------------------------
graph_builder = StateGraph(EmailState)

# Add nodes
graph_builder.add_node("triage_email", triage_email)
graph_builder.add_node("reply_email", reply_email)
graph_builder.add_node("handle_fyi", handle_fyi)
graph_builder.add_node("handle_action", handle_action)

# Start → Triage
graph_builder.add_edge(START, "triage_email")

# Triage → decide which path
graph_builder.add_conditional_edges(
    "triage_email",
    route_email,
    {
        "reply": "reply_email",
        "fyi": "handle_fyi",
        "action": "handle_action",
    }
)

# All paths → END
graph_builder.add_edge("reply_email", END)
graph_builder.add_edge("handle_fyi", END)
graph_builder.add_edge("handle_action", END)

# Compile
email_graph = graph_builder.compile()