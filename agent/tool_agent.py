from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
import os
from dotenv import load_dotenv

load_dotenv()


@tool
def create_email_draft(to: str, subject: str, body: str):
    """Create an email draft with recipient, subject, and body."""
    return {
        "to": to,
        "subject": subject,
        "body": body,
        "status": "draft_created"
    }


llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY")
)

llm_with_tools = llm.bind_tools([create_email_draft])


def run_agent(email: str):
    prompt = f"""
You are an email assistant.

Read the email below.

If the email requires drafting a response, use the
create_email_draft tool.

Email:
{email}
"""

    response = llm_with_tools.invoke(prompt)

    # Execute the tool if Gemini requested it
    if response.tool_calls:
        tool_call = response.tool_calls[0]

        result = create_email_draft.invoke(tool_call["args"])

        return {
            "tool_called": tool_call["name"],
            "tool_result": result
        }

    return {
        "tool_called": None,
        "tool_result": None,
        "response": response.content
    }