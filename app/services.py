"""Application service layer."""

from typing import Protocol

from app.repository import TicketRepository
from app.schemas import LLMAnalysisResult, TicketAnalysis


class TicketAnalyzer(Protocol):
    """Interface implemented by LLM-backed ticket analyzers."""

    def analyze(self, ticket_text: str) -> LLMAnalysisResult:
        """Analyze support ticket text."""


class TicketNotFoundError(RuntimeError):
    """Raised when a ticket does not exist."""


class TicketAnalysisService:
    """Coordinate ticket analysis and ticket history persistence."""

    def __init__(self, repository: TicketRepository, analyzer: TicketAnalyzer) -> None:
        self.repository = repository
        self.analyzer = analyzer

    def analyze(self, ticket_text: str) -> TicketAnalysis:
        """Analyze a support ticket with the configured LLM and save the result."""

        analysis = self.analyzer.analyze(ticket_text)
        return self.repository.create(
            original_text=ticket_text,
            category=analysis.category,
            priority=analysis.priority,
            summary=analysis.summary,
            suggested_reply=analysis.suggested_reply,
        )

    def list_recent(self, limit: int = 20) -> list[TicketAnalysis]:
        """Return recent analyzed support tickets."""

        return self.repository.list_recent(limit=limit)

    def get_by_id(self, ticket_id: int) -> TicketAnalysis:
        """Return a ticket by id or raise when it does not exist."""

        ticket = self.repository.get_by_id(ticket_id)
        if ticket is None:
            raise TicketNotFoundError(f"Ticket {ticket_id} was not found")
        return ticket

    def delete_by_id(self, ticket_id: int) -> None:
        """Delete a ticket by id or raise when it does not exist."""

        deleted = self.repository.delete_by_id(ticket_id)
        if not deleted:
            raise TicketNotFoundError(f"Ticket {ticket_id} was not found")
