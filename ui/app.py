
import sys
import time
import uuid
from pathlib import Path
from email.utils import parseaddr

# =========================================================
# PROJECT ROOT
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# =========================================================
# IMPORTS
# =========================================================

import streamlit as st

from gmail.gmail_service import get_unread_emails
from graph.email_agent_graph import email_agent_graph
from langgraph.types import Command


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Email AI Agent",
    page_icon="📧",
    layout="wide",
)

st.title("📧 Email AI Agent")

st.write(
    "AI-powered Gmail assistant with human-in-the-loop "
    "approval before sending generated replies."
)


# =========================================================
# SESSION STATE
# =========================================================

defaults = {
    "emails": [],
    "current_index": 0,
    "graph_result": None,
    "thread_id": None,
    "load_duration": None,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


def reset_current_email():
    st.session_state.graph_result = None
    st.session_state.thread_id = None


# =========================================================
# LOAD UNREAD EMAILS
# =========================================================

if st.button("🔄 Load Unread Emails"):

    start = time.monotonic()

    try:
        with st.spinner("Connecting to Gmail..."):
            emails = get_unread_emails()

        st.session_state.emails = emails
        st.session_state.current_index = 0
        st.session_state.load_duration = (
            time.monotonic() - start
        )

        reset_current_email()

    except Exception as e:
        st.error(f"Gmail connection failed: {e}")
        st.exception(e)


if st.session_state.load_duration is not None:
    st.caption(
        "Last Gmail fetch took "
        f"{st.session_state.load_duration:.2f} seconds."
    )


# =========================================================
# DISPLAY EMAILS
# =========================================================

emails = st.session_state.emails

if not emails:
    st.info(
        "No emails loaded. Click 'Load Unread Emails'."
    )
    st.stop()

st.success(f"Loaded {len(emails)} unread emails.")

index = st.session_state.current_index

if index >= len(emails):
    st.success("All loaded emails have been reviewed.")
    st.stop()

current_email = emails[index]

sender = current_email.get("sender", "")
original_subject = current_email.get("subject", "")
email_body = current_email.get("body", "")

st.subheader(
    f"Email {index + 1} of {len(emails)}"
)

st.write("**From:**", sender or "Unknown")
st.write("**Subject:**", original_subject or "(No subject)")

st.text_area(
    "Email Body",
    value=email_body,
    height=200,
    disabled=True,
)


# =========================================================
# ANALYZE EMAIL
# =========================================================

if st.session_state.graph_result is None:

    if st.button("🤖 Analyze Email"):

        thread_id = str(uuid.uuid4())

        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        # The graph requires the "email" field.
        # Include the original subject for AI context.
        email_text = (
            f"SUBJECT: {original_subject}\n\n"
            f"{email_body}"
        )

        initial_state = {
            "email": email_text,
            "sender": sender,
            "original_subject": original_subject,
        }

        try:
            with st.spinner("AI is analyzing the email..."):

                result = email_agent_graph.invoke(
                    initial_state,
                    config=config,
                )

            st.session_state.thread_id = thread_id
            st.session_state.graph_result = result

            st.rerun()

        except Exception as e:
            st.error(f"AI analysis failed: {e}")
            st.exception(e)


# =========================================================
# SHOW AI ANALYSIS
# =========================================================

result = st.session_state.graph_result

if result is not None:

    st.divider()
    st.subheader("AI Analysis")

    category = result.get("category", "UNKNOWN")

    st.write("**Category:**", category)

    if result.get("error_message"):
        st.error(result["error_message"])

    interrupts = result.get("__interrupt__", [])

    # =====================================================
    # HUMAN REVIEW / GENERATED DRAFT
    # =====================================================

    if interrupts:

        recipient = result.get("recipient", "")
        reply_subject = result.get("subject", "")
        draft_body = result.get("draft_body", "")

        st.subheader("Generated Email Draft")

        st.write("**To:**", recipient or "Missing recipient")
        st.write(
            "**Subject:**",
            reply_subject or "Missing subject"
        )

        st.text_area(
            "Generated Reply",
            value=draft_body,
            height=220,
            disabled=True,
            key=f"draft_preview_{st.session_state.thread_id}",
        )

        # Validate draft before allowing real Gmail send.
        parsed_recipient = parseaddr(recipient)[1]

        draft_ready = bool(
            recipient
            and parsed_recipient == recipient
            and "@" in parsed_recipient
            and "\n" not in recipient
            and "\r" not in recipient
            and isinstance(reply_subject, str)
            and reply_subject.strip()
            and "\n" not in reply_subject
            and "\r" not in reply_subject
            and isinstance(draft_body, str)
            and draft_body.strip()
            and st.session_state.thread_id
        )

        if not draft_ready:
            st.error(
                "Draft is incomplete or invalid. "
                "Sending is disabled."
            )

        st.warning(
            "Human approval required before sending."
        )

        def resume_review(decision):

            config = {
                "configurable": {
                    "thread_id": st.session_state.thread_id
                }
            }

            return email_agent_graph.invoke(
                Command(resume=decision),
                config=config,
            )

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "✅ Approve & Send",
                type="primary",
                disabled=not draft_ready,
            ):

                try:
                    with st.spinner(
                        "Sending approved email..."
                    ):
                        updated_result = resume_review(
                            "approve"
                        )

                    st.session_state.graph_result = (
                        updated_result
                    )

                    st.rerun()

                except Exception as e:
                    st.error(f"Approval failed: {e}")
                    st.exception(e)

        with col2:

            if st.button("❌ Reject"):

                try:
                    with st.spinner("Rejecting draft..."):

                        updated_result = resume_review(
                            "reject"
                        )

                    st.session_state.graph_result = (
                        updated_result
                    )

                    st.rerun()

                except Exception as e:
                    st.error(f"Rejection failed: {e}")
                    st.exception(e)

    # =====================================================
    # COMPLETED WORKFLOW
    # =====================================================

    else:

        if result.get("response"):
            st.info(result["response"])

        if category == "SENT":
            st.success(
                "Email approved and sent successfully."
            )

        elif category == "REJECTED":
            st.success(
                "Email rejected. No reply was sent "
                "by this workflow."
            )

        elif category == "FYI":
            st.info(
                "This email is informational. "
                "No reply is required."
            )

        elif category == "ACTION_NEEDED":
            st.warning(
                "This email requires an action."
            )

        elif category == "AI_ERROR":
            st.error(
                "AI processing failed. "
                "No email was sent."
            )

        elif category == "SEND_ERROR":
            st.error(
                "Email sending failed."
            )

        else:
            st.info("Graph execution completed.")

        if st.button("➡️ Next Email"):

            st.session_state.current_index += 1

            reset_current_email()

            st.rerun()
