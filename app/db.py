"""SQLite logs, leads, unanswered questions, feedback, and disclaimer sessions."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from app.config import ROOT, get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    session_id TEXT,
    question TEXT,
    language TEXT,
    intent TEXT,
    rewritten_query TEXT,
    top_chunk_ids TEXT,
    rerank_top_score REAL,
    answer TEXT,
    grounded INTEGER,
    verifier_status TEXT,
    latency_ms INTEGER
);
CREATE TABLE IF NOT EXISTS unanswered (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    question TEXT,
    reason TEXT
);
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    session_id TEXT,
    name TEXT,
    email TEXT,
    interest TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    log_id INTEGER,
    rating TEXT,
    comment TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    disclaimer_shown INTEGER
);
"""


def connect() -> sqlite3.Connection:
    path = Path(get_settings().db_path)
    if not path.is_absolute():
        path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with connect() as connection:
        connection.executescript(SCHEMA)


def log_chat(**fields) -> int:
    with connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO logs (
                ts, session_id, question, language, intent, rewritten_query,
                top_chunk_ids, rerank_top_score, answer, grounded, verifier_status, latency_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time.time(),
                fields.get("session_id"),
                fields.get("question"),
                fields.get("language"),
                fields.get("intent"),
                fields.get("rewritten_query"),
                fields.get("top_chunk_ids"),
                fields.get("rerank_top_score"),
                fields.get("answer"),
                1 if fields.get("grounded") else 0,
                fields.get("verifier_status"),
                fields.get("latency_ms"),
            ),
        )
        return int(cursor.lastrowid)


def log_unanswered(question: str, reason: str) -> None:
    with connect() as connection:
        connection.execute(
            "INSERT INTO unanswered (ts, question, reason) VALUES (?, ?, ?)",
            (time.time(), question, reason),
        )


def claim_disclaimer(session_id: str) -> bool:
    """Return True the first time a session should see the disclaimer."""
    with connect() as connection:
        row = connection.execute(
            "SELECT disclaimer_shown FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row and row["disclaimer_shown"]:
            return False
        connection.execute(
            """
            INSERT INTO sessions (session_id, disclaimer_shown) VALUES (?, 1)
            ON CONFLICT(session_id) DO UPDATE SET disclaimer_shown = 1
            """,
            (session_id,),
        )
        return True


def save_lead(session_id: str, name: str, email: str, interest: str) -> None:
    with connect() as connection:
        connection.execute(
            "INSERT INTO leads (ts, session_id, name, email, interest) VALUES (?, ?, ?, ?, ?)",
            (time.time(), session_id, name, email, interest),
        )


def save_feedback(log_id: int, rating: str, comment: str | None) -> None:
    with connect() as connection:
        connection.execute(
            "INSERT INTO feedback (ts, log_id, rating, comment) VALUES (?, ?, ?, ?)",
            (time.time(), log_id, rating, comment),
        )


def unanswered_groups() -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT question, reason, COUNT(*) AS count FROM unanswered GROUP BY question, reason ORDER BY count DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def list_leads() -> list[dict]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, ts, session_id, name, email, interest FROM leads ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]
