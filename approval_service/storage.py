
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone


DB_PATH = Path(__file__).resolve().parent / "approvals.db"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(DB_PATH),
        timeout=10
    )
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS approval_requests (
                request_id TEXT PRIMARY KEY,
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                decided_at TEXT
            )
        """)
        conn.commit()


def create_request(recipient, subject, body, ttl_seconds=300):
    if not all(isinstance(x, str) and x.strip()
               for x in [recipient, subject, body]):
        raise ValueError("Recipient, subject and body are required.")

    if not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
        raise ValueError("TTL must be a positive integer.")

    now = datetime.now(timezone.utc)
    request_id = str(uuid.uuid4())

    created_at = now.isoformat()
    expires_at = (
        now.timestamp() + ttl_seconds
    )

    expires_at = datetime.fromtimestamp(
        expires_at, timezone.utc
    ).isoformat()

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO approval_requests (
                request_id, recipient, subject, body,
                status, created_at, expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            request_id,
            recipient.strip(),
            subject.strip(),
            body,
            "PENDING",
            created_at,
            expires_at
        ))
        conn.commit()

    return request_id


def get_request(request_id):
    with get_connection() as conn:
        row = conn.execute("""
            SELECT * FROM approval_requests
            WHERE request_id = ?
        """, (request_id,)).fetchone()

    return dict(row) if row else None


def decide_request(request_id, decision):
    if decision not in {"APPROVED", "REJECTED"}:
        raise ValueError("Invalid decision.")

    now = datetime.now(timezone.utc)

    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")

        row = conn.execute("""
            SELECT status, expires_at
            FROM approval_requests
            WHERE request_id = ?
        """, (request_id,)).fetchone()

        if row is None:
            conn.rollback()
            return False, "Request not found."

        if row["status"] != "PENDING":
            conn.rollback()
            return False, "Request already processed."

        expiry = datetime.fromisoformat(row["expires_at"])

        if now >= expiry:
            conn.execute("""
                UPDATE approval_requests
                SET status = 'EXPIRED', decided_at = ?
                WHERE request_id = ?
            """, (now.isoformat(), request_id))
            conn.commit()
            return False, "Request has expired."

        conn.execute("""
            UPDATE approval_requests
            SET status = ?, decided_at = ?
            WHERE request_id = ? AND status = 'PENDING'
        """, (decision, now.isoformat(), request_id))

        conn.commit()

    return True, f"Request {decision.lower()} successfully."


def list_pending_requests():
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT request_id, recipient, subject, body,
                   created_at, expires_at
            FROM approval_requests
            WHERE status = 'PENDING'
              AND expires_at > ?
            ORDER BY created_at DESC
        """, (now,)).fetchall()

    return [dict(row) for row in rows]

