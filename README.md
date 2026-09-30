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

```



\## Workflow



1\. Connect to Gmail using the Gmail API.

2\. Retrieve unread messages from the inbox.

3\. Extract sender, subject, and email body.

4\. Send the email content to Gemini for classification.

5\. Route the email according to the classification.

6\. For `NEEDS\_REPLY`, generate a reply draft.

7\. Pause the LangGraph workflow for human review.

8\. If approved, send the email through Gmail.

9\. If rejected, do not send the email.

10\. Emails are only marked as read after successful processing.



\## Tech Stack



\- Python

\- LangGraph

\- LangChain

\- Google Gemini

\- Gmail API

\- Google OAuth 2.0

\- BeautifulSoup

\- Python `unittest`

\- Python `unittest.mock`



\## Project Structure



```text

email-ai-agent/

│

├── agent/

│   ├── llm.py

│   └── tool\_agent.py

│

├── gmail/

│   └── gmail\_service.py

│

├── graph/

│   ├── email\_agent\_graph.py

│   └── email\_graph.py

│

├── tools/

│   └── email\_tools.py

│

├── tests/

│   └── test\_graph.py

│

├── main.py

├── requirements.txt

├── .gitignore

└── README.md

```



\## Setup



\### 1. Clone the repository



```bash

git clone https://github.com/himnad/email-ai-agent.git

cd email-ai-agent

```



\### 2. Create a virtual environment



```bash

python -m venv venv

```



\### 3. Activate the virtual environment



\#### Windows CMD



```cmd

venv\\Scripts\\activate

```



\#### Windows PowerShell



```powershell

venv\\Scripts\\Activate.ps1

```



\### 4. Install dependencies



```bash

pip install -r requirements.txt

```



\## Environment Configuration



Create a `.env` file in the project root:



```text

GEMINI\_API\_KEY=YOUR\_GEMINI\_API\_KEY

```



Do not commit the `.env` file to GitHub.



The application loads the API key using `python-dotenv`.



\## Gmail API Configuration



The application uses the Gmail API with OAuth 2.0 authentication.



\### Steps



1\. Create a project in Google Cloud Console.

2\. Enable the Gmail API.

3\. Configure the OAuth consent screen.

4\. Create OAuth credentials for a desktop application.

5\. Download the credentials file.

6\. Save it in the project root as:



```text

credentials.json

```



On the first run, Google OAuth authentication will be performed.



The application stores the authentication token locally as:



```text

gmail\_token.pickle

```



The following files are excluded from Git:



```text

.env

credentials.json

gmail\_token.pickle

```



\## Run the Application



Activate the virtual environment:



```cmd

venv\\Scripts\\activate

```



Then run:



```cmd

python main.py

```



The application will:



1\. Find unread emails.

2\. Process each email through the LangGraph workflow.

3\. Classify the email.

4\. Generate a response when required.

5\. Ask for human approval before sending.

6\. Send the email only after approval.

7\. Mark the email as read after successful processing.



\## Email Classification



The agent classifies incoming emails into three categories.



\### NEEDS\_REPLY



The sender expects a response from the user.



The workflow:



```text

Email

&#x20; ↓

NEEDS\_REPLY

&#x20; ↓

Generate Reply

&#x20; ↓

Human Review

&#x20; ↓

Approve

&#x20; ↓

Send Email

```



\### FYI



The email is informational and does not require a response.



```text

Email

&#x20; ↓

FYI

&#x20; ↓

No Reply

```



\### ACTION\_NEEDED



The user needs to perform some action.



The agent explains what action is required but does not perform the action automatically.



```text

Email

&#x20; ↓

ACTION\_NEEDED

&#x20; ↓

Explain Required Action

```



\## Human-in-the-Loop Approval



For emails requiring a response, the LangGraph workflow pauses before sending.



Example:



```text

Graph interrupted for human review.



Review Data:

...



Enter approve or reject:

```



The available decisions are:



```text

approve

reject

```



\### Approve



The generated email is sent through Gmail.



\### Reject



The generated email is not sent.



This prevents the AI from automatically sending a generated response without human approval.



\## Error Handling



The application handles failures from external services.



Examples include:



\- Gemini API failures

\- Gmail API failures

\- Reply-generation failures

\- Email-sending failures



If AI processing fails:



```text

Email is NOT marked as READ

```



If email sending fails:



```text

Email is NOT treated as successfully sent

```



This prevents failed processing from being incorrectly treated as successful.



\## Testing



The project includes unit and integration tests using mocked Gemini and Gmail services.



Run the test suite with:



```cmd

python -m tests.test\_graph

```



\### Tests Cover



\- `NEEDS\_REPLY` classification

\- `FYI` classification

\- `ACTION\_NEEDED` classification

\- Reply generation

\- FYI handling

\- Action-required handling

\- AI error handling

\- Reply-generation error handling

\- Email sending success

\- Email sending failure

\- Human approval flow

\- Human rejection flow



Expected output:



```text

========================================

EMAIL AGENT UNIT TESTS

========================================



PASS: NEEDS\_REPLY classification

PASS: FYI classification

PASS: ACTION\_NEEDED classification

PASS: Reply generation

PASS: FYI handler

PASS: ACTION\_NEEDED handler

PASS: AI error handling

PASS: Reply generation AI error

PASS: Email sending success

PASS: Email sending error

PASS: Graph approve flow

PASS: Rejected email was not sent



========================================

ALL TESTS PASSED

========================================

```



\## Security



Sensitive credentials are intentionally excluded from version control.



The `.gitignore` file excludes:



```text

.env

credentials.json

gmail\_token.pickle

venv/

```



Never commit:



\- API keys

\- OAuth credentials

\- Gmail authentication tokens

\- Passwords

\- Other private credentials



\## Current Limitations



\- Gemini API availability and quota affect AI processing.

\- Gmail API connectivity is required for reading and sending emails.

\- Human approval is currently performed through the command-line interface.

\- Emails are currently processed sequentially.

\- The current system is designed for local execution.



\## Future Improvements



\- Web-based email review dashboard

\- Streamlit interface

\- Editable AI-generated drafts

\- Email priority detection

\- Conversation/thread awareness

\- Persistent database for processing history

\- Retry handling for temporary API failures

\- Background email monitoring

\- Scheduled email processing

\- More advanced email categorization

\- Multi-user support



\## Example Workflow



```text

&#x20;                   ┌──────────────────┐

&#x20;                   │   Gmail Inbox    │

&#x20;                   └────────┬─────────┘

&#x20;                            │

&#x20;                            ▼

&#x20;                   ┌──────────────────┐

&#x20;                   │ Read Unread Mail │

&#x20;                   └────────┬─────────┘

&#x20;                            │

&#x20;                            ▼

&#x20;                   ┌──────────────────┐

&#x20;                   │ Gemini / LLM     │

&#x20;                   │     Triage       │

&#x20;                   └────────┬─────────┘

&#x20;                            │

&#x20;             ┌──────────────┼──────────────┐

&#x20;             ▼              ▼              ▼

&#x20;      ┌────────────┐ ┌────────────┐ ┌──────────────┐

&#x20;      │ NEEDS\_REPLY│ │    FYI     │ │ ACTION\_NEEDED│

&#x20;      └──────┬─────┘ └─────┬──────┘ └───────┬──────┘

&#x20;             │             │                │

&#x20;             ▼             ▼                ▼

&#x20;      ┌────────────┐  No response     Explain action

&#x20;      │Generate    │

&#x20;      │Reply       │

&#x20;      └──────┬─────┘

&#x20;             │

&#x20;             ▼

&#x20;      ┌────────────┐

&#x20;      │Human Review│

&#x20;      └──────┬─────┘

&#x20;             │

&#x20;       ┌─────┴─────┐

&#x20;       ▼           ▼

&#x20;    APPROVE      REJECT

&#x20;       │           │

&#x20;       ▼           ▼

&#x20;  Gmail Send    No Send

```



\## Project Status



The core email processing workflow, Gmail integration, Gemini integration, human approval flow, error handling, and automated tests are implemented.



```text

Gmail Integration          ✓

Gemini Integration         ✓

Email Classification       ✓

Reply Generation           ✓

Human Approval             ✓

Email Sending              ✓

Error Handling             ✓

Automated Tests            ✓

GitHub Repository          ✓

```



\## Author



\*\*Akhil Himnad\*\*



GitHub:  

https://github.com/himnad

