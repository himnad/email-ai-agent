import streamlit as st

from web_app.oauth import get_authorization_url

st.set_page_config(
    page_title="AI Email Agent",
    page_icon="📧",
)

st.title("AI-Powered Email Agent")

st.write(
    "Connect your Gmail account to manage emails "
    "with AI assistance."
)

st.info(
    "Google login integration is under development. "
    "Real Gmail access is not enabled yet."
)

if st.button("Connect Gmail"):
    try:
        authorization_url, state = get_authorization_url()

        st.success("Google authorization URL generated.")

        st.write(
            "OAuth session verification must be configured "
            "before enabling the login redirect."
        )

    except Exception as error:
        st.error(f"OAuth configuration error: {error}")