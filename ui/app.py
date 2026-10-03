import sys
from pathlib import Path


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

from gmail.gmail_service import (
    get_unread_emails,
    mark_email_as_read,
)

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


# =========================================================
# TITLE
# =========================================================

st.title("📧 Email AI Agent")

st.markdown(
    """
    AI-powered Gmail assistant with **human-in-the-loop
    approval** before sending generated replies.
    """
)


# =========================================================
# SESSION STATE
# =========================================================

if "emails" not in st.session_state:
    st.session_state.emails = []

if "current_index" not in st.session_state:
    st.session_state.current_index = 0

if "graph_result" not in st.session_state:
    st.session_state.graph_result = None

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

# Prevent repeated Gmail READ calls during Streamlit reruns.
if "read_status_handled" not in st.session_state:
    st.session_state.read_status_handled = False


# =========================================================
# LOAD UNREAD EMAILS
# =========================================================

if st.button("🔄 Load Unread Emails"):

    with st.spinner("Connecting to Gmail..."):

        try:

            emails = get_unread_emails()

            st.session_state.emails = emails
            st.session_state.current_index = 0
            st.session_state.graph_result = None
            st.session_state.thread_id = None
            st.session_state.read_status_handled = False

            if emails:

                st.success(
                    f"Found {len(emails)} unread emails."
                )

                # Force Streamlit to run again so the
                # loaded emails are displayed immediately.
                st.rerun()

            else:

                st.info(
                    "No unread emails found."
                )

        except Exception as e:

            st.error(
                f"Could not connect to Gmail:\n\n{e}"
            )


# =========================================================
# NO EMAILS LOADED
# =========================================================

if not st.session_state.emails:

    st.info(
        "No unread emails loaded. "
        "Click **Load Unread Emails** to begin."
    )

    st.stop()


# =========================================================
# CURRENT EMAIL
# =========================================================

current_email = st.session_state.emails[
    st.session_state.current_index
]


# =========================================================
# EMAIL HEADER
# =========================================================

st.divider()

st.subheader(
    f"📨 Email "
    f"{st.session_state.current_index + 1} "
    f"of "
    f"{len(st.session_state.emails)}"
)

st.write(
    f"**From:** {current_email['sender']}"
)

st.write(
    f"**Subject:** {current_email['subject']}"
)


# =========================================================
# EMAIL BODY
# =========================================================

with st.expander(
    "📨 View Email Body",
    expanded=True,
):

    st.text(
        current_email["body"]
    )


# =========================================================
# ANALYZE EMAIL
# =========================================================

if st.session_state.graph_result is None:

    if st.button(
        "🤖 Analyze Email",
        type="primary",
    ):

        email = f"""
FROM: {current_email["sender"]}

SUBJECT: {current_email["subject"]}

BODY:

{current_email["body"]}
"""

        with st.spinner(
            "Gemini is analyzing the email..."
        ):

            try:

                result = email_agent_graph.invoke(
                    {
                        "email": email,
                        "category": "",
                        "response": "",
                        "recipient": "",
                        "subject": "",
                        "draft_body": "",
                        "review_status": "",
                        "error_message": "",
                    },
                    config={
                        "configurable": {
                            "thread_id":
                                current_email["id"]
                        }
                    },
                )

                st.session_state.graph_result = result

                st.session_state.thread_id = (
                    current_email["id"]
                )

                st.session_state.read_status_handled = False

                st.rerun()

            except Exception as e:

                st.error(
                    f"Email processing failed:\n\n{e}"
                )


# =========================================================
# DISPLAY AI RESULT
# =========================================================

if st.session_state.graph_result:

    result = st.session_state.graph_result

    st.divider()

    st.subheader(
        "🤖 AI Analysis"
    )

    category = result.get(
        "category",
        "",
    )

    if category:

        st.write(
            f"**Category:** `{category}`"
        )


    # =====================================================
    # HUMAN REVIEW
    # =====================================================

    if "__interrupt__" in result:

        interrupt_data = result[
            "__interrupt__"
        ]

        st.subheader(
            "👤 Human Review Required"
        )

        st.warning(
            "The AI generated a reply. "
            "Review or edit it before sending."
        )

        try:

            review = interrupt_data[0].value

        except Exception:

            review = {}


        recipient = review.get(
            "to",
            "",
        )

        subject = review.get(
            "subject",
            "",
        )

        draft = review.get(
            "draft",
            "",
        )


        # -------------------------------------------------
        # RECIPIENT
        # -------------------------------------------------

        st.text_input(
            "To",
            value=recipient,
            disabled=True,
        )


        # -------------------------------------------------
        # SUBJECT
        # -------------------------------------------------

        st.text_input(
            "Subject",
            value=subject,
            disabled=True,
        )


        # -------------------------------------------------
        # EDITABLE DRAFT
        # -------------------------------------------------

        edited_draft = st.text_area(
            "Reply",
            value=draft,
            height=250,
        )


        col1, col2 = st.columns(2)


        # =================================================
        # APPROVE
        # =================================================

        with col1:

            if st.button(
                "✅ Approve & Send",
                type="primary",
            ):

                if not edited_draft.strip():

                    st.error(
                        "The reply cannot be empty."
                    )

                else:

                    with st.spinner(
                        "Sending email..."
                    ):

                        try:

                            final_result = (
                                email_agent_graph.invoke(
                                    Command(
                                        resume={
                                            "decision":
                                                "approve",

                                            "draft_body":
                                                edited_draft,
                                        }
                                    ),
                                    config={
                                        "configurable": {
                                            "thread_id":
                                                st.session_state.thread_id
                                        }
                                    },
                                )
                            )

                            st.session_state.graph_result = (
                                final_result
                            )


                            # ---------------------------------
                            # SUCCESSFUL SEND
                            # ---------------------------------

                            if (
                                final_result.get(
                                    "category"
                                )
                                == "SENT"
                            ):

                                marked_as_read = (
                                    mark_email_as_read(
                                        current_email["id"]
                                    )
                                )

                                st.session_state.read_status_handled = True

                                if marked_as_read:

                                    st.success(
                                        "Email approved, "
                                        "sent, and marked as READ."
                                    )

                                else:

                                    st.success(
                                        "Email approved and sent."
                                    )


                            # ---------------------------------
                            # SEND ERROR
                            # ---------------------------------

                            elif (
                                final_result.get(
                                    "category"
                                )
                                == "SEND_ERROR"
                            ):

                                # Keep the original email unread
                                # because sending failed.

                                st.session_state.read_status_handled = False

                                st.error(
                                    "The email could not be sent."
                                )

                            else:

                                st.info(
                                    final_result.get(
                                        "response",
                                        "Email processing finished.",
                                    )
                                )

                            st.rerun()

                        except Exception as e:

                            st.error(
                                f"Email sending failed:\n\n{e}"
                            )


        # =================================================
        # REJECT
        # =================================================

        with col2:

            if st.button(
                "❌ Reject"
            ):

                with st.spinner(
                    "Rejecting email..."
                ):

                    try:

                        final_result = (
                            email_agent_graph.invoke(
                                Command(
                                    resume={
                                        "decision":
                                            "reject",

                                        "draft_body":
                                            edited_draft,
                                    }
                                ),
                                config={
                                    "configurable": {
                                        "thread_id":
                                            st.session_state.thread_id
                                    }
                                },
                            )
                        )

                        st.session_state.graph_result = (
                            final_result
                        )

                        st.session_state.read_status_handled = False

                        st.rerun()

                    except Exception as e:

                        st.error(
                            f"Could not reject email:\n\n{e}"
                        )


    # =====================================================
    # FINAL RESULT
    # =====================================================

    else:

        response = result.get(
            "response",
            "",
        )

        if response:

            st.subheader(
                "📋 Result"
            )


            # =================================================
            # AI ERROR
            # =================================================

            if (
                result.get("category")
                == "AI_ERROR"
            ):

                # AI errors remain unread so the user
                # can retry processing the email.

                st.session_state.read_status_handled = False

                st.error(
                    "Gemini could not process this email."
                )

                st.warning(
                    "The Gemini API quota may be exhausted "
                    "or the service may be temporarily unavailable."
                )

                error_message = result.get(
                    "error_message",
                    "",
                )

                if error_message:

                    st.caption(
                        f"Technical details: {error_message}"
                    )

                st.info(
                    "Please wait for the Gemini quota "
                    "to become available and try again."
                )


            # =================================================
            # SEND ERROR
            # =================================================

            elif (
                result.get("category")
                == "SEND_ERROR"
            ):

                # The original email stays unread because
                # the reply was not successfully sent.

                st.session_state.read_status_handled = False

                st.error(
                    "The email could not be sent."
                )

                st.info(
                    response
                )


            # =================================================
            # REJECTED
            # =================================================

            elif (
                result.get("category")
                == "REJECTED"
            ):

                if not st.session_state.read_status_handled:

                    marked_as_read = mark_email_as_read(
                        current_email["id"]
                    )

                    st.session_state.read_status_handled = True

                else:

                    marked_as_read = True

                if marked_as_read:

                    st.success(
                        "Email rejected and marked as READ. "
                        "It was not sent."
                    )

                else:

                    st.warning(
                        "Email rejected, but Gmail "
                        "could not mark it as READ."
                    )


            # =================================================
            # SENT
            # =================================================

            elif (
                result.get("category")
                == "SENT"
            ):

                st.success(
                    response
                )


            # =================================================
            # FYI
            # =================================================

            elif (
                result.get("category")
                == "FYI"
            ):

                if not st.session_state.read_status_handled:

                    marked_as_read = mark_email_as_read(
                        current_email["id"]
                    )

                    st.session_state.read_status_handled = True

                else:

                    marked_as_read = True

                if marked_as_read:

                    st.success(
                        "FYI email processed "
                        "and marked as READ."
                    )

                else:

                    st.warning(
                        "FYI email was processed, "
                        "but Gmail could not mark it as READ."
                    )

                st.info(
                    response
                )


            # =================================================
            # ACTION NEEDED
            # =================================================

            elif (
                result.get("category")
                == "ACTION_NEEDED"
            ):

                if not st.session_state.read_status_handled:

                    marked_as_read = mark_email_as_read(
                        current_email["id"]
                    )

                    st.session_state.read_status_handled = True

                else:

                    marked_as_read = True

                if marked_as_read:

                    st.success(
                        "Action-needed email processed "
                        "and marked as READ."
                    )

                else:

                    st.warning(
                        "Action-needed email was processed, "
                        "but Gmail could not mark it as READ."
                    )

                st.info(
                    response
                )


            # =================================================
            # OTHER RESULT
            # =================================================

            else:

                st.info(
                    response
                )


# =========================================================
# NEXT EMAIL
# =========================================================

if (
    st.session_state.graph_result
    and "__interrupt__"
    not in st.session_state.graph_result
):

    st.divider()

    if (
        st.session_state.current_index
        < len(st.session_state.emails) - 1
    ):

        if st.button(
            "➡️ Process Next Email"
        ):

            st.session_state.current_index += 1
            st.session_state.graph_result = None
            st.session_state.thread_id = None
            st.session_state.read_status_handled = False

            st.rerun()

    else:

        st.success(
            "🎉 All loaded emails have been processed."
        )