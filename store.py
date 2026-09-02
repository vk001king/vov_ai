"""
VOV AI - Chat persistence.

The original kept all history in the browser's localStorage, so it was
lost when you switched machines or cleared the browser. This stores
sessions server side in SQLite (standard library, no extra install).
"""

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from typing import List, Optional

import config

_lock = threading.Lock()
_local = threading.local()


def _connection() -> sqlite3.Connection:
    connection = getattr(_local, "connection", None)

    if connection is None:
        connection = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        _local.connection = connection

    return connection


def init_db() -> None:
    with _lock:
        connection = _connection()

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                model       TEXT,
                images      TEXT,
                created_at  TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session
                ON messages(session_id, id);
            """
        )

        connection.commit()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _touch(session_id: str) -> None:
    connection = _connection()

    connection.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?",
        (_now(), session_id),
    )

    connection.commit()


def create_session(title: str = "New chat") -> dict:
    session_id = uuid.uuid4().hex[:16]
    now = _now()

    with _lock:
        connection = _connection()

        connection.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (session_id, title[:120], now, now),
        )

        connection.commit()

    return {"id": session_id, "title": title[:120], "created_at": now, "updated_at": now}


def session_exists(session_id: str) -> bool:
    with _lock:
        row = _connection().execute(
            "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()

    return row is not None


def list_sessions(limit: int = 100) -> List[dict]:
    with _lock:
        rows = _connection().execute(
            """
            SELECT s.id, s.title, s.created_at, s.updated_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS message_count
            FROM sessions s
            ORDER BY s.updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_messages(session_id: str, limit: int = 500) -> List[dict]:
    with _lock:
        rows = _connection().execute(
            """
            SELECT role, content, model, images, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()

    messages = []

    for row in rows:
        item = dict(row)

        if item.get("images"):
            try:
                item["images"] = json.loads(item["images"])
            except (TypeError, ValueError):
                item["images"] = []
        else:
            item["images"] = []

        messages.append(item)

    return messages


def get_history_for_model(session_id: str) -> List[dict]:
    """Plain role/content turns for replaying into the model."""

    return [
        {"role": item["role"], "content": item["content"]}
        for item in get_messages(session_id)
        if item["role"] in ("user", "assistant") and item["content"]
    ]


def append_message(
    session_id: str,
    role: str,
    content: str,
    model: Optional[str] = None,
    images: Optional[List[str]] = None,
) -> None:
    with _lock:
        connection = _connection()

        connection.execute(
            """
            INSERT INTO messages (session_id, role, content, model, images, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                model,
                json.dumps(images) if images else None,
                _now(),
            ),
        )

        connection.commit()

        _touch(session_id)


def rename_session(session_id: str, title: str) -> bool:
    with _lock:
        connection = _connection()

        cursor = connection.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title[:120], _now(), session_id),
        )

        connection.commit()

    return cursor.rowcount > 0


def autotitle_session(session_id: str, text: str) -> None:
    """Set the title from the first user message, if still untitled."""

    with _lock:
        connection = _connection()

        row = connection.execute(
            "SELECT title FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()

        if not row or row["title"] not in ("New chat", "", None):
            return

        title = " ".join(text.split())[:60]

        if len(text) > 60:
            title += "..."

        connection.execute(
            "UPDATE sessions SET title = ? WHERE id = ?",
            (title or "New chat", session_id),
        )

        connection.commit()


def delete_session(session_id: str) -> bool:
    with _lock:
        connection = _connection()

        connection.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))

        cursor = connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

        connection.commit()

    return cursor.rowcount > 0


def clear_all_sessions() -> int:
    with _lock:
        connection = _connection()

        cursor = connection.execute("SELECT COUNT(*) AS total FROM sessions").fetchone()
        total = cursor["total"] if cursor else 0

        connection.execute("DELETE FROM messages")
        connection.execute("DELETE FROM sessions")
        connection.commit()

    return total
