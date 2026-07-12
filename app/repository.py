"""SQLite repository for analyzed support tickets."""

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.schemas import TicketAnalysis


logger = logging.getLogger(__name__)


class DatabaseError(RuntimeError):
    """Raised when the repository cannot complete a database operation."""


class TicketRepository:
    """Persist and read analyzed support tickets."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def create(
        self,
        original_text: str,
        category: str,
        priority: str,
        summary: str,
        suggested_reply: str,
    ) -> TicketAnalysis:
        """Save an analyzed ticket and return the stored item."""

        created_at = datetime.now(UTC).isoformat()

        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO tickets (
                        original_text,
                        category,
                        priority,
                        summary,
                        suggested_reply,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        original_text,
                        category,
                        priority,
                        summary,
                        suggested_reply,
                        created_at,
                    ),
                )
                connection.commit()
                ticket_id = cursor.lastrowid
        except sqlite3.Error as exc:
            logger.exception("Failed to create ticket")
            raise DatabaseError("Failed to create ticket") from exc

        return TicketAnalysis(
            id=int(ticket_id),
            original_text=original_text,
            category=category,
            priority=priority,
            summary=summary,
            suggested_reply=suggested_reply,
            created_at=created_at,
        )

    def list_recent(self, limit: int = 20) -> list[TicketAnalysis]:
        """Return recently analyzed tickets, newest first."""

        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT
                        id,
                        original_text,
                        category,
                        priority,
                        summary,
                        suggested_reply,
                        created_at
                    FROM tickets
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        except sqlite3.Error as exc:
            logger.exception("Failed to list tickets")
            raise DatabaseError("Failed to list tickets") from exc

        return [self._row_to_ticket(row) for row in rows]

    def get_by_id(self, ticket_id: int) -> TicketAnalysis | None:
        """Return one ticket by id, if it exists."""

        try:
            with self._connect() as connection:
                row = connection.execute(
                    """
                    SELECT
                        id,
                        original_text,
                        category,
                        priority,
                        summary,
                        suggested_reply,
                        created_at
                    FROM tickets
                    WHERE id = ?
                    """,
                    (ticket_id,),
                ).fetchone()
        except sqlite3.Error as exc:
            logger.exception("Failed to get ticket %s", ticket_id)
            raise DatabaseError("Failed to get ticket") from exc

        if row is None:
            return None
        return self._row_to_ticket(row)

    def delete_by_id(self, ticket_id: int) -> bool:
        """Delete one ticket by id and return whether a row was removed."""

        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "DELETE FROM tickets WHERE id = ?",
                    (ticket_id,),
                )
                connection.commit()
        except sqlite3.Error as exc:
            logger.exception("Failed to delete ticket %s", ticket_id)
            raise DatabaseError("Failed to delete ticket") from exc

        return cursor.rowcount > 0

    def _row_to_ticket(self, row: sqlite3.Row) -> TicketAnalysis:
        return TicketAnalysis(
            id=row["id"],
            original_text=row["original_text"],
            category=row["category"],
            priority=row["priority"],
            summary=row["summary"],
            suggested_reply=row["suggested_reply"],
            created_at=row["created_at"],
        )
