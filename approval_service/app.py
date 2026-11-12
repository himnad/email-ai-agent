
import os
from html import escape

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse

from approval_service.storage import (
    initialize_database,
    list_pending_requests,
    get_request,
    decide_request
)

from approval_service.security import (
    verify_login_password,
    create_session,
    verify_session,
    verify_csrf_token
)


app = FastAPI(title="SafeMail Approval Service")

SESSION_COOKIE = "safemail_session"

initialize_database()


def get_session(request):
    token = request.cookies.get(SESSION_COOKIE)
    return verify_session(token)


def page(content):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>SafeMail Approval Center</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: Arial;
                max-width: 800px;
                margin: 40px auto;
                padding: 20px;
                background: #f4f4f4;
            }}
            .card {{
                background: white;
                padding: 20px;
                margin-bottom: 20px;
                border-radius: 10px;
            }}
            input, textarea {{
                width: 100%;
                padding: 10px;
                margin: 8px 0;
                box-sizing: border-box;
            }}
            textarea {{ min-height: 120px; }}
            button {{
                padding: 10px 20px;
                cursor: pointer;
            }}
        </style>
    </head>
    <body>
        <h1>SafeMail Approval Center</h1>
        {content}
    </body>
    </html>
    """


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    if not get_session(request):
        return RedirectResponse("/login", status_code=303)

    return RedirectResponse("/dashboard", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return HTMLResponse(page("""
        <div class="card">
            <h2>Human Login</h2>
            <form method="POST" action="/login">
                <input type="password" name="password"
                       placeholder="Enter password" required>
                <button type="submit">Login</button>
            </form>
        </div>
    """))


@app.post("/login")
async def login(password: str = Form(...)):
    if not verify_login_password(password):
        return PlainTextResponse(
            "Invalid password.",
            status_code=401
        )

    session = create_session()

    response = RedirectResponse(
        "/dashboard",
        status_code=303
    )

    response.set_cookie(
        SESSION_COOKIE,
        session["session_token"],
        httponly=True,
        secure=os.getenv("SAFEMAIL_COOKIE_SECURE", "false").lower() == "true",
        samesite="strict",
        max_age=1800,
        path="/"
    )

    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    session = get_session(request)

    if not session:
        return RedirectResponse("/login", status_code=303)

    content = """
        <div class="card">
            <h2>Pending Email Approvals</h2>
        </div>
    """

    requests = list_pending_requests()

    if not requests:
        content += """
            <div class="card">
                No pending requests.
            </div>
        """

    for item in requests:
        rid = escape(item["request_id"])
        recipient = escape(item["recipient"])
        subject = escape(item["subject"])
        body = escape(item["body"])
        csrf = escape(session["csrf_token"])

        content += f"""
        <div class="card">
            <h3>Email Review</h3>
            <p><b>Recipient:</b> {recipient}</p>
            <p><b>Subject:</b> {subject}</p>
            <p><b>Message:</b></p>
            <textarea readonly>{body}</textarea>

            <form method="POST" action="/requests/{rid}/approve">
                <input type="hidden" name="csrf_token" value="{csrf}">
                <button type="submit">Approve</button>
            </form>

            <form method="POST" action="/requests/{rid}/reject">
                <input type="hidden" name="csrf_token" value="{csrf}">
                <button type="submit">Reject</button>
            </form>
        </div>
        """

    content += f"""
        <div class="card">
            <form method="POST" action="/logout">
                <input type="hidden" name="csrf_token"
                       value="{escape(session['csrf_token'])}">
                <button type="submit">Logout</button>
            </form>
        </div>
    """

    return HTMLResponse(page(content))


@app.post("/requests/{request_id}/approve")
async def approve(
    request_id: str,
    request: Request,
    csrf_token: str = Form(...)
):
    session = get_session(request)

    if not session:
        return RedirectResponse("/login", status_code=303)

    if not verify_csrf_token(session, csrf_token):
        return PlainTextResponse("CSRF validation failed.", status_code=403)

    if not get_request(request_id):
        return PlainTextResponse("Request not found.", status_code=404)

    success, message = decide_request(request_id, "APPROVED")

    return HTMLResponse(page(f"""
        <div class="card">
            <h2>{escape(message)}</h2>
            <p>No email has been sent. This only records the human decision.</p>
            <a href="/dashboard">Return to dashboard</a>
        </div>
    """), status_code=200 if success else 409)


@app.post("/requests/{request_id}/reject")
async def reject(
    request_id: str,
    request: Request,
    csrf_token: str = Form(...)
):
    session = get_session(request)

    if not session:
        return RedirectResponse("/login", status_code=303)

    if not verify_csrf_token(session, csrf_token):
        return PlainTextResponse("CSRF validation failed.", status_code=403)

    success, message = decide_request(request_id, "REJECTED")

    return HTMLResponse(page(f"""
        <div class="card">
            <h2>{escape(message)}</h2>
            <a href="/dashboard">Return to dashboard</a>
        </div>
    """), status_code=200 if success else 409)


@app.post("/logout")
async def logout(
    request: Request,
    csrf_token: str = Form(...)
):
    session = get_session(request)

    if not session:
        return RedirectResponse("/login", status_code=303)

    if not verify_csrf_token(session, csrf_token):
        return PlainTextResponse("CSRF validation failed.", status_code=403)

    response = RedirectResponse("/login", status_code=303)

    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=os.getenv("SAFEMAIL_COOKIE_SECURE", "false").lower() == "true",
        samesite="strict"
    )

    return response
