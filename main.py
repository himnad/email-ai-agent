from gmail.gmail_service import (
    get_unread_emails,
    mark_email_as_read
)

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

    print(result["response"])


    # =====================================================
    # 5. CHECK FOR AI ERROR
    # =====================================================

    # If Gemini failed:
    #
    # 1. Do NOT mark the email as read.
    # 2. Stop processing the remaining emails.
    #
    # This allows the failed email to be retried later.

    if result.get("category") == "AI_ERROR":

        print(
            "\nEmail was NOT marked as READ "
            "because AI processing failed."
        )

        print(
            "\nStopping email processing."
        )

        print(
            "The remaining emails will be processed "
            "when the AI service is available again."
        )

        break


    # =====================================================
    # 6. MARK SUCCESSFULLY PROCESSED EMAIL AS READ
    # =====================================================

    marked_as_read = mark_email_as_read(
    email_data["id"]
    )

    if marked_as_read:
        print("\nEmail marked as READ.")
    else:
        print(
        "\nEmail could not be marked as READ."
    )


# =========================================================
# 7. PROCESSING COMPLETED / STOPPED
# =========================================================

print("\n========================================")
print("EMAIL PROCESSING FINISHED")
print("========================================")