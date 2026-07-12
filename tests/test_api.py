import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import init_db
from app.llm import LLMProviderError, OpenRouterClient
from app.main import create_app
from app.repository import TicketRepository
from app.schemas import LLMAnalysisResult


class FakeAnalyzer:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def analyze(self, ticket_text: str) -> LLMAnalysisResult:
        if self.should_fail:
            raise LLMProviderError("OpenRouter unavailable")

        return LLMAnalysisResult(
            category="Доступ к аккаунту",
            priority="Высокий",
            summary="Клиент не может войти в аккаунт после смены пароля.",
            suggested_reply=(
                "Здравствуйте. Спасибо за обращение. Мы проверим ситуацию с "
                "доступом к аккаунту и сообщим вам дальнейшие шаги."
            ),
        )


def build_client(database_path: Path, analyzer: FakeAnalyzer | None = None) -> TestClient:
    settings = Settings(
        openrouter_api_key="test-key",
        database_url=f"sqlite:///{database_path}",
    )
    repository = TicketRepository(settings.database_path)
    app = create_app(
        settings=settings,
        repository=repository,
        analyzer=analyzer or FakeAnalyzer(),
    )
    return TestClient(app)


def test_health_endpoint(tmp_path: Path) -> None:
    with build_client(tmp_path / "test.db") as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "AI Support Ticket Analyzer",
    }


def test_index_page_is_served(tmp_path: Path) -> None:
    with build_client(tmp_path / "test.db") as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "AI Support Ticket Analyzer" in response.text


def test_analyze_ticket_uses_mock_llm_and_saves_result(tmp_path: Path) -> None:
    text = "Клиент не может войти в личный кабинет после смены пароля."

    with build_client(tmp_path / "test.db") as client:
        response = client.post("/api/tickets/analyze", json={"text": text})

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 1
    assert payload["original_text"] == text
    assert payload["category"] == "Доступ к аккаунту"
    assert payload["priority"] == "Высокий"
    assert payload["summary"] == "Клиент не может войти в аккаунт после смены пароля."
    assert payload["suggested_reply"].startswith("Здравствуйте.")
    assert payload["created_at"]


def test_analyze_ticket_rejects_short_text(tmp_path: Path) -> None:
    with build_client(tmp_path / "test.db") as client:
        response = client.post("/api/tickets/analyze", json={"text": "abc"})

    assert response.status_code == 422
    assert response.json()["error"] == "Request validation failed"


def test_analyze_ticket_returns_503_and_does_not_save_on_llm_error(
    tmp_path: Path,
) -> None:
    with build_client(tmp_path / "test.db", analyzer=FakeAnalyzer(should_fail=True)) as client:
        response = client.post(
            "/api/tickets/analyze",
            json={"text": "Клиент не может оплатить заказ банковской картой."},
        )
        history_response = client.get("/api/tickets")

    assert response.status_code == 503
    assert response.json() == {"error": "LLM service unavailable"}
    assert history_response.status_code == 200
    assert history_response.json() == []


def test_list_tickets_returns_newest_first_with_limit(tmp_path: Path) -> None:
    with build_client(tmp_path / "test.db") as client:
        first = client.post("/api/tickets/analyze", json={"text": "Первое обращение"})
        second = client.post("/api/tickets/analyze", json={"text": "Второе обращение"})
        response = client.get("/api/tickets?limit=1")

    assert first.status_code == 200
    assert second.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["original_text"] == "Второе обращение"


def test_list_tickets_validates_limit_range(tmp_path: Path) -> None:
    with build_client(tmp_path / "test.db") as client:
        response = client.get("/api/tickets?limit=101")

    assert response.status_code == 422


def test_get_ticket_by_id(tmp_path: Path) -> None:
    text = "Нужно изменить адрес доставки в заказе."

    with build_client(tmp_path / "test.db") as client:
        created = client.post("/api/tickets/analyze", json={"text": text}).json()
        response = client.get(f"/api/tickets/{created['id']}")

    assert response.status_code == 200
    assert response.json()["original_text"] == text


def test_get_ticket_returns_404_for_missing_ticket(tmp_path: Path) -> None:
    with build_client(tmp_path / "test.db") as client:
        response = client.get("/api/tickets/999")

    assert response.status_code == 404
    assert response.json() == {"error": "Ticket not found"}


def test_delete_ticket_removes_ticket(tmp_path: Path) -> None:
    with build_client(tmp_path / "test.db") as client:
        created = client.post(
            "/api/tickets/analyze",
            json={"text": "Прошу проверить статус возврата средств."},
        ).json()
        delete_response = client.delete(f"/api/tickets/{created['id']}")
        get_response = client.get(f"/api/tickets/{created['id']}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


def test_delete_ticket_returns_404_for_missing_ticket(tmp_path: Path) -> None:
    with build_client(tmp_path / "test.db") as client:
        response = client.delete("/api/tickets/999")

    assert response.status_code == 404


def test_repository_creates_database_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "test.db"

    init_db(database_path)
    repository = TicketRepository(database_path)
    created = repository.create(
        original_text="Проверить начисление бонусов.",
        category="Другое",
        priority="Средний",
        summary="Проверить начисление бонусов.",
        suggested_reply="Тестовый ответ.",
    )

    assert created.id == 1
    assert repository.get_by_id(created.id) is not None


def test_openrouter_client_parses_valid_json() -> None:
    client = OpenRouterClient(Settings(openrouter_api_key="test-key"))
    payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "category": "Оплата",
                            "priority": "Средний",
                            "summary": "Клиент не может оплатить заказ.",
                            "suggested_reply": "Здравствуйте. Мы проверим оплату.",
                        },
                        ensure_ascii=False,
                    )
                }
            }
        ]
    }

    result = client._parse_response(payload)

    assert result.category == "Оплата"
    assert result.priority == "Средний"


def test_openrouter_client_strips_markdown_json_wrapper() -> None:
    client = OpenRouterClient(Settings(openrouter_api_key="test-key"))
    payload = {
        "choices": [
            {
                "message": {
                    "content": """```json
{
  "category": "Доставка",
  "priority": "Низкий",
  "summary": "Клиент спрашивает о доставке.",
  "suggested_reply": "Здравствуйте. Мы уточним информацию по доставке."
}
```"""
                }
            }
        ]
    }

    result = client._parse_response(payload)

    assert result.category == "Доставка"


def test_openrouter_client_rejects_invalid_json() -> None:
    client = OpenRouterClient(Settings(openrouter_api_key="test-key"))
    payload = {"choices": [{"message": {"content": "not-json"}}]}

    with pytest.raises(LLMProviderError, match="invalid JSON"):
        client._parse_response(payload)
