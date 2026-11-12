
import os
import time
import hmac
import secrets
from html import escape

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse

from approval_service.storage import (
    initialize_database,
    list_pending_requests,
    get_request,
    decide_request
)

from approval_service.security import (
    SecurityError,
    get_serializer,
    verify_login_password,
    create_session,
    verify_session,
    verify_csrf_token
)


app = FastAPI(title="SafeMail Approval Service")

SESSION_COOKIE = "safemail_session"
LOGIN_COOKIE = "safemail_login_nonce"

LOGIN_ATTEMPTS = {}
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW = 300  # 5 minutes


initialize_database()


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)

    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; "
        "style-src 'unsafe-inline'; "
        "form-action 'self'; "
        "base-uri 'none'; "
        "frame-ancestors 'none'"
    )

    return response


def secure_cookie_enabled():
    return os.getenv(
        "SAFEMAIL_COOKIE_SECURE", "false"
    ).lower() == "true"


def get_authenticated_session(request):
    token = request.cookies.get(SESSION_COOKIE)
    return verify_session(token)


def render_page(title, content):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{escape(title)}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 850px;
                margin: 40px auto;
                padding: 0 20px;
                background: #f5f7fa;
                color: #202124;
            }}
            .card {{
                background: white;
                padding: 22px;
                margin: 18px 0;
                border-radius: 10px;
                border: 1px solid #ddd;
            }}
            input, textarea {{
                width: 100%;
                padding: 10px;
                margin: 8px 0 15px;
                box-sizing: border-box;
            }}
            textarea {{
                min-height: 150px;
            }}
            button {{
                padding: 10px 18px;
                margin-right: 10px;
                cursor: pointer;
            }}
            .approve {{ background: #d1fae5; }}
            .reject {{ background: #fee2e2; }}
            .muted {{ color: #666; }}
        </style>
    </head>
    <body>
        <h1>SafeMail Approval Center</h1>
        {content}
    </body>
    </html>
    """


def login_rate_limited(client_ip):
    now = time.monotonic()
    attempts = LOGIN_ATTEMPTS.get(client_ip, [])

    attempts = [
        timestamp for timestamp in attempts
        if now - timestamp < LOGIN_WINDOW
    ]

    LOGIN_ATTEMPTS[client_ip] = attempts

    return len(attempts) >= MAX_LOGIN_ATTEMPTS


def record_login_failure(client_ip):
    LOGIN_ATTEMPTS.setdefault(client_ip, []).append(
        time.monotonic()
    )


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    session = get_authenticated_session(request)

    if not session:
        return RedirectResponse("/login", status_code=303)

    return RedirectResponse("/dashboard", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    nonce = secrets.token_urlsafe(32)

    login_cookie = get_serializer().dumps({
        "login_nonce": nonce
    })

    content = f"""
    <div class="card">
        <h2>Human Authentication</h2>
        <form method="POST" action="/login">
            <input type="hidden" name="nonce"
                   value="{escape(nonce)}">

            <label>Password</label>
            <input type="password" name="password"
                   required autocomplete="current-password">

            <button type="submit">Login</button>
        </form>
    </div>
    """

    response = HTMLResponse(
        render_page("SafeMail Login", content)
    )

    response.set_cookie(
        LOGIN_COOKIE,
        login_cookie,
        httponly=True,
        secure=secure_cookie_enabled(),
        samesite="strict",
        max_age=300,
        path="/"
    )

    return response


@app.post("/login")
async def login(
    request: Request,
    password: str = Form(...),
    nonce: str = Form(...)
):
    client_ip = request.client.host if request.client else "unknown"

    if login_rate_limited(client_ip):
        return PlainTextResponse(
            "Too many login attempts. Try again later.",
            status_code=429
        )

    cookie_value = request.cookies.get(LOGIN_COOKIE)

    try:
        cookie_payload = get_serializer().loads(
            cookie_value,
            max_age=300
        ) if cookie_value else None
    except Exception:
        cookie_payload = None

    valid_nonce = (
        isinstance(cookie_payload, dict)
        and isinstance(cookie_payload.get("login_nonce"), str)
        and hmac.compare_digest(
            cookie_payload["login_nonce"],
            nonce
        )
    )

    if not valid_nonce:
        return PlainTextResponse(
            "Invalid login request. Reload the login page.",
            status_code=400
        )

    try:
        valid_password = verify_login_password(password)
    except SecurityError:
        return PlainTextResponse(
            "Approval service is not configured correctly.",
            status_code=500
        )

    if not valid_password:
        record_login_failure(client_ip)
        return RedirectResponse("/login", status_code=303)

    LOGIN_ATTEMPTS.pop(client_ip, None)

    session_data = create_session()

    response = RedirectResponse(
        "/dashboard",
        status_code=303
    )

    response.set_cookie(
        SESSION_COOKIE,
        session_data["session_token"],
        httponly=True,
        secure=secure_cookie_enabled(),
        samesite="strict",
        max_age=1800,
        path="/"
    )

    response.delete_cookie(
        LOGIN_COOKIE,
        path="/",
        secure=secure_cookie_enabled(),
        httponly=True,
        samesite="strict"
    )

    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    session = get_authenticated_session(request)

    if not session:
        return RedirectResponse("/login", status_code=303)

    requests = list_pending_requests()

    content = f"""
    <div class="card">
        <h2>Pending email approvals</h2>
        <p>Review every email before taking action.</p>

        <form method="POST" action="/logout">
            <input type="hidden" name="csrf_token"
                   value="{escape(session['csrf_token'])}">
            <button type="submit">Logout</button>
        </form>
    </div>
    """

    if not requests:
        content += """
        <div class="card">
            <p>No pending email requests.</p>
        </div>
        """

    for item in requests:
        request_id = escape(item["request_id"])
        recipient = escape(item["recipient"])
        subject = escape(item["subject"])
        body = escape(item["body"])
        created_at = escape(item["created_at"])

        csrf = escape(session["csrf_token"])

        content += f"""
        <div class="card">
            <h3>Email review</h3>

            <p><strong>Recipient:</strong> {recipient}</p>
            <p><strong>Subject:</strong> {subject}</p>
            <p><strong>Created:</strong> {created_at}</p>

            <p><strong>Message:</strong></p>
            <textarea readonly>{body}</textarea>

            <form method="POST"
                  action="/requests/{request_id}/approve"
                  style="display:inline">
                <input type="hidden" name="csrf_token"
                       value="{csrf}">
                <button class="approve" type="submit">
                    Approve
                </button>
            </form>

            <form method="POST"
                  action="/requests/{request_id}/reject"
                  style="display:inline">
                <input type="hidden" name="csrf_token"
                       value="{csrf}">
                <button class="reject" type="submit">
                    Reject
                </button>
            </form>
        </div>
        """

    return HTMLResponse(
        render_page("SafeMail Dashboard", content)
    )


@app.post("/requests/{request_id}/approve")
async def approve_request(
    request_id: str,
    request: Request,
    csrf_token: str = Form(...)
):
    session = get_authenticated_session(request)

    if not session:
        return RedirectResponse("/login", status_code=303)

    if not verify_csrf_token(session, csrf_token):
        return PlainTextResponse(
            "CSRF validation failed.",
            status_code=403
        )

    item = get_request(request_id)

    if not item:
        return PlainTextResponse(
            "Request not found.",
            status_code=404
        )

    success, message = decide_request(
        request_id,
        "APPROVED"
    )

    return HTMLResponse(
        render_page(
            "Approval Result",
            f"""
            <div class="card">
                <h2>{escape(message)}</h2>
                <p>Approval records a human decision only.
                No email has been sent.</p>
                <a href="/dashboard">Return to dashboard</a>
            </div>
            """
        ),
        status_code=200 if success else 409
    )


@app.post("/requests/{request_id}/reject")
async def reject_request(
    request_id: str,
    request: Request,
    csrf_token: str = Form(...)
):
    session = get_authenticated_session(request)

    if not session:
        return RedirectResponse("/login", status_code=303)

    if not verify_csrf_token(session, csrf_token):
        return PlainTextResponse(
            "CSRF validation failed.",
            status_code=403
        )

    success, message = decide_request(
        request_id,
        "REJECTED"
    )

    return HTMLResponse(
        render_page(
            "Rejection Result",
            f"""
            <div class="card">
                <h2>{escape(message)}</h2>
                <a href="/dashboard">Return to dashboard</a>
            </div>
            """
        ),
        status_code=200 if success else 409
    )


@app.post("/logout")
async def logout(
    request: Request,
    csrf_token: str = Form(...)
):
    session = get_authenticated_session(request)

    if not session:
        return RedirectResponse("/login", status_code=303)

    if not verify_csrf_token(session, csrf_token):
        return PlainTextResponse(
            "CSRF validation failed.",
            status_code=403
        )

    response = RedirectResponse(
        "/login",
        status_code=303
    )

    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=secure_cookie_enabled(),
        httponly=True,
        samesite="strict"
    )

    return response
