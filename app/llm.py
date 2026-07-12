"""OpenRouter LLM client."""

import json
import logging
from typing import Any

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.prompts import SYSTEM_PROMPT, build_user_prompt
from app.schemas import LLMAnalysisResult


logger = logging.getLogger(__name__)


class LLMAnalysisError(RuntimeError):
    """Base error for LLM analysis failures."""


class LLMClientNotConfiguredError(LLMAnalysisError):
    """Raised when the LLM client is used before configuration is complete."""


class LLMProviderError(LLMAnalysisError):
    """Raised when OpenRouter cannot return a usable analysis."""


class OpenRouterClient:
    """Minimal OpenRouter chat completions client."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.chat_completions_url = (
            f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
        )

    def analyze(self, ticket_text: str) -> LLMAnalysisResult:
        """Analyze one support ticket through OpenRouter."""

        if not self.settings.openrouter_api_key:
            logger.error("OpenRouter API key is not configured")
            raise LLMClientNotConfiguredError("OpenRouter API key is not configured")

        try:
            response = httpx.post(
                self.chat_completions_url,
                headers=self._headers(),
                json=self._payload(ticket_text),
                timeout=self.settings.llm_timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.warning("OpenRouter request timed out")
            raise LLMProviderError("OpenRouter request timed out") from exc
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "OpenRouter returned HTTP status %s",
                exc.response.status_code,
            )
            raise LLMProviderError("OpenRouter returned an error status") from exc
        except httpx.HTTPError as exc:
            logger.warning("OpenRouter request failed: %s", exc.__class__.__name__)
            raise LLMProviderError("OpenRouter request failed") from exc

        try:
            response_payload = response.json()
        except json.JSONDecodeError as exc:
            logger.warning("OpenRouter returned a non-JSON HTTP response")
            raise LLMProviderError("OpenRouter returned a non-JSON response") from exc

        return self._parse_response(response_payload)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.app_url,
            "X-OpenRouter-Title": self.settings.app_name,
        }

    def _payload(self, ticket_text: str) -> dict[str, Any]:
        return {
            "model": self.settings.openrouter_model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(ticket_text)},
            ],
            "response_format": {"type": "json_object"},
        }

    def _parse_response(self, payload: dict[str, Any]) -> LLMAnalysisResult:
        provider_error = payload.get("error")
        if provider_error:
            logger.warning("OpenRouter returned an error payload")
            raise LLMProviderError("OpenRouter returned an error payload")

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.warning("OpenRouter response shape is unexpected")
            raise LLMProviderError("OpenRouter returned an unexpected response") from exc

        if not isinstance(content, str):
            logger.warning("OpenRouter message content is not text")
            raise LLMProviderError("OpenRouter returned non-text content")

        cleaned_content = _strip_markdown_json_wrapper(content)
        try:
            decoded = json.loads(cleaned_content)
        except json.JSONDecodeError as exc:
            logger.warning("OpenRouter message content is not valid JSON")
            raise LLMProviderError("OpenRouter returned invalid JSON") from exc

        try:
            return LLMAnalysisResult.model_validate(decoded)
        except ValidationError as exc:
            logger.warning("OpenRouter JSON failed Pydantic validation")
            raise LLMProviderError("OpenRouter returned invalid analysis data") from exc


def _strip_markdown_json_wrapper(content: str) -> str:
    """Remove a Markdown JSON code fence if the model adds one."""

    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) >= 3 and lines[0].strip().lower() in {"```json", "```"}:
        return "\n".join(lines[1:-1]).strip()

    return stripped.strip("`").strip()
