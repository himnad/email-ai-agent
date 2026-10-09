
import sys
from pathlib import Path
from uuid import uuid4

import streamlit as st
from langgraph.types import Command

# Allow imports from the project root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from graph.demo_graph import demo_graph


st.set_page_config(
    page_title="AI Email Agent | Demo",
    page_icon="📧",
    layout="wide",
)

SAMPLE_EMAILS = {
    "Meeting Request": {
        "sender": "Sarah Johnson <sarah@example.com>",
        "subject": "Project Discussion",
        "body": (
            "Hi,\n\n"
            "Would you be available to discuss the project "
            "requirements next week? Please let me know "
            "what works for you.\n\n"
            "Best,\nSarah"
        ),
    },
    "Company Announcement": {
        "sender": "HR Team <hr@example.com>",
        "subject": "Office Holiday Announcement",
        "body": (
            "Hello Team,\n\n"
            "The office will remain closed next Friday "
            "for a company holiday.\n\n"
            "Regards,\nHR Team"
        ),
    },
    "Action Required": {
        "sender": "IT Support <support@example.com>",
        "subject": "Security Training Reminder",
        "body": (
            "Hello,\n\n"
            "Please complete the mandatory security "
            "training by Friday using the company "
            "learning portal.\n\n"
            "Thanks,\nIT Support"
        ),
    },
}


def reset_workflow():
    st.session_state.result = None
    st.session_state.thread_id = None


if "selected_email" not in st.session_state:
    st.session_state.selected_email = "Meeting Request"

if "result" not in st.session_state:
    st.session_state.result = None

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None


st.title("AI-Powered Email Agent")
st.caption("LangGraph + Gemini AI + Human-in-the-Loop")

st.info(
    "Public Demo Mode: All emails are synthetic. "
    "Approving a draft only simulates sending. "
    "No Gmail account is connected."
)

st.divider()

selected = st.selectbox(
    "Choose a sample email",
    options=list(SAMPLE_EMAILS.keys()),
    key="selected_email",
    on_change=reset_workflow,
)

email = SAMPLE_EMAILS[selected]

st.subheader("Sample Inbox")

with st.container(border=True):
    st.write(f"**From:** {email['sender']}")
    st.write(f"**Subject:** {email['subject']}")
    st.text(email["body"])

if st.button(
    "Analyze Email",
    type="primary",
    use_container_width=True,
):
    reset_workflow()

    thread_id = str(uuid4())
    st.session_state.thread_id = thread_id

    initial_state = {
        "email": (
            f"SUBJECT: {email['subject']}\n\n"
            f"{email['body']}"
        ),
        "sender": email["sender"],
        "original_subject": email["subject"],
    }

    with st.spinner("AI is analyzing the email..."):
        try:
            st.session_state.result = demo_graph.invoke(
                initial_state,
                config={
                    "configurable": {
                        "thread_id": thread_id
                    }
                },
            )
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")

result = st.session_state.result

if result is not None:
    st.divider()
    st.subheader("AI Analysis")

    category = result.get("category", "UNKNOWN")
    st.write(f"**Category:** `{category}`")

    if result.get("error_message"):
        st.error(result["error_message"])

    interrupts = result.get("__interrupt__", [])

    if interrupts:
        st.subheader("Human Approval Required")

        st.write(
            f"**To:** {result.get('recipient', '')}"
        )
        st.write(
            f"**Subject:** {result.get('subject', '')}"
        )

        st.text_area(
            "AI-Generated Draft",
            value=result.get("draft_body", ""),
            height=180,
            disabled=True,
        )

        left, right = st.columns(2)

        with left:
            if st.button(
                "Approve (Simulate Send)",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Simulating approval..."):
                    st.session_state.result = demo_graph.invoke(
                        Command(resume="approve"),
                        config={
                            "configurable": {
                                "thread_id": st.session_state.thread_id
                            }
                        },
                    )
                st.rerun()

        with right:
            if st.button(
                "Reject",
                use_container_width=True,
            ):
                st.session_state.result = demo_graph.invoke(
                    Command(resume="reject"),
                    config={
                        "configurable": {
                            "thread_id": st.session_state.thread_id
                        }
                    },
                )
                st.rerun()

    else:
        response = result.get("response", "")

        if category == "SIMULATED_SENT":
            st.success(response)
        elif category == "REJECTED":
            st.warning(response)
        elif category == "AI_ERROR":
            st.error(response or "AI processing failed.")
        else:
            st.write("**AI Response:**")
            st.write(response)

st.divider()
st.caption(
    "Demo only. No real emails are read, modified, or sent."
)
