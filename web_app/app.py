import secrets
import streamlit as st

from web_app.oauth import (
    get_authorization_url,
    exchange_code_for_credentials,
)

st.set_page_config(
    page_title="AI-Powered Email Agent",
    page_icon="📧",
)

st.title("AI-Powered Email Agent")

st.write("Connect your Gmail account securely.")

# Temporary local development storage.
# Not suitable for a public multi-user deployment.
if "oauth_state" not in st.session_state:
    st.session_state.oauth_state = None

if "credentials" not in st.session_state:
    st.session_state.credentials = None

# Handle callback from Google
params = st.query_params

if "error" in params:
    st.error("Google authorization was cancelled or denied.")
    st.query_params.clear()

elif "code" in params and "state" in params:
    received_state = params["state"]
    expected_state = st.session_state.oauth_state

    if (
        not expected_state
        or not secrets.compare_digest(
            received_state,
            expected_state,
        )
    ):
        st.error(
            "OAuth session verification failed. "
            "Please restart login."
        )
    else:
        try:
            credentials = exchange_code_for_credentials(
                code=params["code"],
                state=received_state,
                expected_state=expected_state,
            )

            st.session_state.credentials = credentials
            st.success("Google authorization successful!")

        except Exception:
            st.error("Google authentication failed.")

    st.session_state.oauth_state = None
    st.query_params.clear()

# Main interface
if st.session_state.credentials:
    st.success("Gmail authorization completed.")

    if st.button("Disconnect"):
        st.session_state.credentials = None
        st.rerun()

else:
    if st.button("Connect Gmail"):
        authorization_url, state = get_authorization_url()

        st.session_state.oauth_state = state

        st.link_button(
            "Continue with Google",
            authorization_url,
        )