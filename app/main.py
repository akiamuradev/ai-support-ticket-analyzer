"""FastAPI entry point for AI Support Ticket Analyzer."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import Settings, get_settings
from app.database import init_db
from app.llm import LLMAnalysisError, OpenRouterClient
from app.repository import DatabaseError, TicketRepository
from app.schemas import (
    ErrorResponse,
    HealthResponse,
    TicketAnalysis,
    TicketAnalyzeRequest,
)
from app.services import TicketAnalysisService, TicketAnalyzer, TicketNotFoundError


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


def get_ticket_service(request: Request) -> TicketAnalysisService:
    """Return the configured ticket service."""

    return request.app.state.ticket_service


def create_app(
    settings: Settings | None = None,
    repository: TicketRepository | None = None,
    analyzer: TicketAnalyzer | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application."""

    resolved_settings = settings or get_settings()
    resolved_repository = repository or TicketRepository(resolved_settings.database_path)
    resolved_analyzer = analyzer or OpenRouterClient(resolved_settings)
    ticket_service = TicketAnalysisService(
        repository=resolved_repository,
        analyzer=resolved_analyzer,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db(resolved_repository.database_path)
        yield

    app = FastAPI(title=resolved_settings.app_name, lifespan=lifespan)
    app.state.ticket_service = ticket_service

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", response_class=FileResponse)
    def index() -> FileResponse:
        """Serve the main browser page."""

        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="Static index page not found")
        return FileResponse(index_path)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Return service health status."""

        return HealthResponse(status="ok", service=resolved_settings.app_name)

    @app.post("/api/tickets/analyze", response_model=TicketAnalysis)
    def analyze_ticket(
        payload: TicketAnalyzeRequest,
        service: Annotated[TicketAnalysisService, Depends(get_ticket_service)],
    ) -> TicketAnalysis:
        """Analyze a support ticket with OpenRouter and save it."""

        try:
            return service.analyze(payload.text)
        except LLMAnalysisError as exc:
            raise HTTPException(
                status_code=503,
                detail="LLM service unavailable",
            ) from exc
        except DatabaseError as exc:
            raise HTTPException(
                status_code=500,
                detail="Database operation failed",
            ) from exc

    @app.get("/api/tickets", response_model=list[TicketAnalysis])
    def list_tickets(
        service: Annotated[TicketAnalysisService, Depends(get_ticket_service)],
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> list[TicketAnalysis]:
        """Return recent analyzed tickets, newest first."""

        try:
            return service.list_recent(limit=limit)
        except DatabaseError as exc:
            raise HTTPException(
                status_code=500,
                detail="Database operation failed",
            ) from exc

    @app.get("/api/tickets/{ticket_id}", response_model=TicketAnalysis)
    def get_ticket(
        ticket_id: int,
        service: Annotated[TicketAnalysisService, Depends(get_ticket_service)],
    ) -> TicketAnalysis:
        """Return one analyzed ticket by id."""

        try:
            return service.get_by_id(ticket_id)
        except TicketNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Ticket not found") from exc
        except DatabaseError as exc:
            raise HTTPException(
                status_code=500,
                detail="Database operation failed",
            ) from exc

    @app.delete("/api/tickets/{ticket_id}", status_code=204)
    def delete_ticket(
        ticket_id: int,
        service: Annotated[TicketAnalysisService, Depends(get_ticket_service)],
    ) -> Response:
        """Delete one analyzed ticket by id."""

        try:
            service.delete_by_id(ticket_id)
        except TicketNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Ticket not found") from exc
        except DatabaseError as exc:
            raise HTTPException(
                status_code=500,
                detail="Database operation failed",
            ) from exc
        return Response(status_code=204)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Return a consistent JSON response for HTTP errors."""

        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(error=str(exc.detail)).model_dump(exclude_none=True),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return a consistent JSON response for request validation errors."""

        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                ErrorResponse(
                    error="Request validation failed",
                    details=exc.errors(),
                ).model_dump(exclude_none=True)
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Hide internal errors behind a generic response."""

        return JSONResponse(
            status_code=500,
            content=ErrorResponse(error="Internal server error").model_dump(
                exclude_none=True
            ),
        )

    return app


app = create_app()
