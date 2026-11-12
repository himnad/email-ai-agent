from approval_service.storage import (
    initialize_database,
    create_request,
    get_request,
    decide_request
)

initialize_database()

request_id = create_request(
    recipient="test@example.com",
    subject="SafeMail test",
    body="This is a test draft."
)

print("Request created:", request_id)

request = get_request(request_id)
print("Initial status:", request["status"])

success, message = decide_request(request_id, "APPROVED")
print(message)

request = get_request(request_id)
print("Final status:", request["status"])

# Verify that the same request cannot be approved twice.
success, message = decide_request(request_id, "APPROVED")
print("Second approval:", message)