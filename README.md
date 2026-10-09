\# Email AI Agent



An AI-powered email management agent that connects to Gmail, classifies incoming emails, generates replies when required, and uses a human-in-the-loop approval step before sending emails.



\## Features



\- Read unread emails from Gmail

\- Automatically classify emails into:

&#x20; - `NEEDS\_REPLY`

&#x20; - `FYI`

&#x20; - `ACTION\_NEEDED`

\- Generate concise professional replies using Google Gemini

\- Human approval before sending generated replies

\- Send approved replies through the Gmail API

\- Explain required actions for action-oriented emails

\- Handle AI/API failures without marking emails as successfully processed

\- LangGraph-based workflow orchestration

\- Unit and integration tests with mocked external services



\## Architecture



```text

&#x20;                   Gmail Inbox

&#x20;                        |

&#x20;                        v

&#x20;                Read Unread Emails

&#x20;                        |

&#x20;                        v

&#x20;                 Gemini / LLM

&#x20;                        |

&#x20;                        v

&#x20;                    TRIAGE

&#x20;                /      |       \\

&#x20;               /       |        \\

&#x20;              v        v         v

&#x20;       NEEDS\_REPLY     FYI    ACTION\_NEEDED

&#x20;            |           |          |

&#x20;            v           v          v

&#x20;     Generate Reply   No Reply   Explain Action

&#x20;            |

&#x20;            v

&#x20;      Human Review

&#x20;       /          \\

&#x20;      /            \\

&#x20;  APPROVE          REJECT

&#x20;     |                |

&#x20;     v                v

&#x20; Gmail Send       No Email Sent


## Live Demo

[Try AI Email Agent](https://email-ai-agent-eqmi8z5twq97kwglgfdi2g.streamlit.app)
