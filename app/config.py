"""Application configuration."""

from functools import lru_cache
from os import environ, getenv
from pathlib import Path

from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent.parent


def load_env_file(path: Path) -> None:
    """Load simple KEY=value pairs from a local .env file."""

    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in environ:
            environ[key] = value


class Settings(BaseModel):
    """Runtime settings loaded from environment variables."""

    app_name: str = "AI Support Ticket Analyzer"
    environment: str = "development"
    app_url: str = "http://127.0.0.1:8000"
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_timeout_seconds: float = 30.0
    database_url: str = "sqlite:///./support_tickets.db"

    @property
    def database_path(self) -> Path:
        """Return the local SQLite database path from DATABASE_URL."""

        sqlite_prefix = "sqlite:///"
        if not self.database_url.startswith(sqlite_prefix):
            raise ValueError("Only sqlite:/// database URLs are supported")

        raw_path = self.database_url.removeprefix(sqlite_prefix)
        path = Path(raw_path)
        if not path.is_absolute():
            path = BASE_DIR / path
        return path


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""

    load_env_file(BASE_DIR / ".env")
    return Settings(
        environment=getenv("APP_ENV", "development"),
        app_url=getenv("APP_URL", "http://127.0.0.1:8000"),
        openrouter_api_key=getenv("OPENROUTER_API_KEY"),
        openrouter_model=getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        openrouter_base_url=getenv(
            "OPENROUTER_BASE_URL",
            "https://openrouter.ai/api/v1",
        ).rstrip("/"),
        llm_timeout_seconds=float(getenv("LLM_TIMEOUT_SECONDS", "30")),
        database_url=getenv("DATABASE_URL", "sqlite:///./support_tickets.db"),
    )
