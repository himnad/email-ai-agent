
from gmail.gmail_service import get_unread_emails

from graph.email_agent_graph import email_agent_graph

from langgraph.types import Command


# =========================================================
# 1. GET ALL UNREAD EMAILS
# =========================================================

emails = get_unread_emails()

if not emails:
    print("\nNo unread emails found in Gmail.")
    exit()


print("\n========================================")
print("UNREAD EMAILS FOUND:", len(emails))
print("========================================")


# =========================================================
# 2. PROCESS EACH EMAIL
# =========================================================

for index, email_data in enumerate(emails, start=1):

    print("\n\n========================================")
    print(f"PROCESSING EMAIL {index}/{len(emails)}")
    print("========================================")

    print("From:", email_data["sender"])
    print("Subject:", email_data["subject"])

    # -----------------------------------------------------
    # Prepare email for LangGraph
    # -----------------------------------------------------

    email = f"""
FROM: {email_data["sender"]}

SUBJECT: {email_data["subject"]}

BODY:
{email_data["body"]}
"""

    # -----------------------------------------------------
    # Run LangGraph
    # -----------------------------------------------------

    result = email_agent_graph.invoke(
        {
            "email": email,
            "category": "",
            "response": "",
            "recipient": "",
            "subject": "",
            "draft_body": "",
            "review_status": ""
        },
        config={
            "configurable": {
                "thread_id": email_data["id"]
            }
        }
    )

    # =====================================================
    # 3. HUMAN REVIEW
    # =====================================================

    if "__interrupt__" in result:

        print("\nGraph interrupted for human review.")

        print("\nReview Data:")
        print(result["__interrupt__"])

        # -------------------------------------------------
        # Ask the user for approval
        # -------------------------------------------------

        decision = input(
            "\nEnter approve or reject: "
        ).strip().lower()

        # -------------------------------------------------
        # Validate user input
        # -------------------------------------------------

        while decision not in ["approve", "reject"]:

            print(
                "\nInvalid input."
                "\nPlease enter either approve or reject."
            )

            decision = input(
                "\nEnter approve or reject: "
            ).strip().lower()

        # -------------------------------------------------
        # Resume the interrupted graph
        # -------------------------------------------------

        result = email_agent_graph.invoke(
            Command(resume=decision),
            config={
                "configurable": {
                    "thread_id": email_data["id"]
                }
            }
        )

    # =====================================================
    # 4. DISPLAY FINAL RESULT
    # =====================================================

    print("\n----------------------------------------")
    print("FINAL RESULT")
    print("----------------------------------------")

    print(result.get("response", "No response returned."))

    # =====================================================
    # 5. HANDLE AI ERRORS
    # =====================================================

    if result.get("category") == "AI_ERROR":

        print(
            "\nAI processing failed."
        )

        print(
            "\nStopping email processing."
        )

        print(
            "The unread email will remain in your inbox "
            "and can be retried later."
        )

        break

    # =====================================================
    # 6. EMAIL PROCESSING STATUS
    # =====================================================

    print(
        "\nEmail processing completed."
    )

    print(
        "The original email remains unread."
    )


# =========================================================
# 7. PROCESSING COMPLETED / STOPPED
# =========================================================

print("\n========================================")
print("EMAIL PROCESSING FINISHED")
print("========================================")
