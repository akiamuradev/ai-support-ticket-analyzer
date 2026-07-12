"""Pydantic schemas for API payloads."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HealthResponse(BaseModel):
    """Response returned by the health endpoint."""

    status: str
    service: str


class ErrorResponse(BaseModel):
    """Consistent error response shape."""

    error: str
    details: list[dict[str, Any]] | None = None


class TicketAnalyzeRequest(BaseModel):
    """Request body for support ticket analysis."""

    text: str = Field(..., min_length=5, max_length=5000)

    @field_validator("text")
    @classmethod
    def strip_and_validate_text(cls, value: str) -> str:
        """Normalize ticket text and reject whitespace-only requests."""

        stripped = value.strip()
        if len(stripped) < 5:
            raise ValueError("Ticket text must contain at least 5 characters")
        if len(stripped) > 5000:
            raise ValueError("Ticket text must contain no more than 5000 characters")
        return stripped


TicketCategory = Literal[
    "Доступ к аккаунту",
    "Оплата",
    "Заказ",
    "Доставка",
    "Возврат",
    "Техническая проблема",
    "Жалоба",
    "Консультация",
    "Другое",
]

TicketPriority = Literal["Низкий", "Средний", "Высокий", "Критический"]


class LLMAnalysisResult(BaseModel):
    """Structured analysis returned by the LLM."""

    model_config = ConfigDict(extra="forbid")

    category: TicketCategory
    priority: TicketPriority
    summary: str = Field(..., min_length=1, max_length=500)
    suggested_reply: str = Field(..., min_length=1, max_length=2000)


class TicketAnalysis(BaseModel):
    """Stored support ticket analysis."""

    model_config = ConfigDict(extra="forbid")

    id: int
    original_text: str
    category: str
    priority: str
    summary: str
    suggested_reply: str
    created_at: str
