import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=30,
)


def ask_gemini(prompt: str) -> str:
    """
    Send a prompt to Gemini with a timeout.
    """

    response = llm.invoke(prompt)

    return response.content