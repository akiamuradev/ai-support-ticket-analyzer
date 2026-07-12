"""SQLite database initialization."""

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


EXPECTED_COLUMNS = {
    "id",
    "original_text",
    "category",
    "priority",
    "summary",
    "suggested_reply",
    "created_at",
}

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_text TEXT NOT NULL,
    category TEXT NOT NULL,
    priority TEXT NOT NULL,
    summary TEXT NOT NULL,
    suggested_reply TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def init_db(database_path: Path) -> None:
    """Create SQLite tables when they do not exist yet."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(database_path) as connection:
            _ensure_tickets_table(connection)
            connection.commit()
    except sqlite3.Error:
        logger.exception("Failed to initialize SQLite database")
        raise


def _ensure_tickets_table(connection: sqlite3.Connection) -> None:
    """Create the tickets table or migrate the previous portfolio schema."""

    columns = _table_columns(connection, "tickets")
    if not columns:
        connection.execute(SCHEMA)
        return

    if EXPECTED_COLUMNS.issubset(columns):
        return

    legacy_columns = {
        "id",
        "ticket_text",
        "category",
        "priority",
        "summary",
        "recommended_response",
        "created_at",
    }
    if legacy_columns.issubset(columns):
        backup_name = f"tickets_legacy_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        connection.execute(f"ALTER TABLE tickets RENAME TO {backup_name}")
        connection.execute(SCHEMA)
        connection.execute(
            f"""
            INSERT INTO tickets (
                id,
                original_text,
                category,
                priority,
                summary,
                suggested_reply,
                created_at
            )
            SELECT
                id,
                ticket_text,
                category,
                priority,
                summary,
                recommended_response,
                created_at
            FROM {backup_name}
            """
        )
        return

    backup_name = f"tickets_backup_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    connection.execute(f"ALTER TABLE tickets RENAME TO {backup_name}")
    connection.execute(SCHEMA)


def _table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}
