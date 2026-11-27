"""Provider-neutral LLM clients with JSON parsing and HTTP resilience."""

from __future__ import annotations

import json
import logging
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

import requests

LOGGER = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """Base class for LLM failures."""


class LLMRequestError(LLMError):
    """Raised when a provider request fails or retries are exhausted."""


class LLMResponseError(LLMError):
    """Raised when a provider response cannot be parsed as JSON."""


class LLMClient(Protocol):
    def generate(self, prompt: str, *, structured: bool = False) -> str:
        """Generate a response for a prompt."""


def sanitize_job_text(text: str | None, max_chars: int = 12000) -> str:
    """Remove common scrape noise, normalize whitespace, and cap prompt size."""
    if not text:
        return ""
    cleaned = re.sub(r"(?im)^\s*(apply now|see more|show less|easy apply)\s*$", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_chars].rstrip()


def parse_json_response(response: str | None) -> dict[str, Any]:
    """Parse raw or markdown-fenced JSON object responses."""
    cleaned = (response or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    if not cleaned:
        raise LLMResponseError("LLM returned an empty response; expected a JSON object")
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMResponseError("LLM returned malformed JSON") from exc
    if not isinstance(parsed, dict):
        raise LLMResponseError("LLM response must be a JSON object")
    return parsed


@dataclass
class _HTTPClient:
    session: requests.Session
    max_retries: int = 3
    base_delay: float = 0.5
    sleep: Any = time.sleep
    random_fn: Any = random.random

    def _post(self, url: str, *, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.post(url, headers=headers, json=payload, timeout=60)
            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempt >= self.max_retries:
                    raise LLMRequestError(f"LLM request failed after retries: {exc}") from exc
                self._backoff(attempt)
                continue
            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError as exc:
                    raise LLMResponseError("LLM provider returned invalid JSON") from exc
            transient = response.status_code == 429 or response.status_code >= 500
            if not transient:
                detail = response.text[:300] if response.text else "no response body"
                raise LLMRequestError(
                    f"LLM request failed with HTTP {response.status_code}: {detail}"
                )
            if attempt >= self.max_retries:
                raise LLMRequestError(
                    f"LLM request failed with HTTP {response.status_code} after retries"
                )
            self._backoff(attempt)
        raise LLMRequestError("LLM request failed unexpectedly")

    def _backoff(self, attempt: int) -> None:
        delay = self.base_delay * (2**attempt) + self.random_fn() * self.base_delay
        self.sleep(delay)


class OllamaClient:
    """Ollama REST API client."""

    def __init__(self, model: str, host: str = "http://localhost:11434", **kwargs: Any) -> None:
        self.model = model
        self.http = _HTTPClient(session=kwargs.pop("session", requests.Session()), **kwargs)
        self.url = host.rstrip("/") + "/api/chat"

    def generate(self, prompt: str, *, structured: bool = False) -> str:
        options: dict[str, Any] = {"temperature": 0}
        data = self.http._post(
            self.url,
            headers={"Content-Type": "application/json"},
            payload={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": options,
                **({"format": "json"} if structured else {}),
            },
        )
        try:
            return str(data["message"]["content"])
        except (KeyError, TypeError) as exc:
            raise LLMResponseError("Ollama response did not contain message.content") from exc


class GeminiClient:
    """Gemini generateContent REST API client."""

    def __init__(self, model: str, api_key: str, **kwargs: Any) -> None:
        if not api_key.strip():
            raise ValueError("GEMINI_API_KEY is required for GeminiClient")
        self.model = model
        self.http = _HTTPClient(session=kwargs.pop("session", requests.Session()), **kwargs)
        self.api_key = api_key
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def generate(self, prompt: str, *, structured: bool = False) -> str:
        generation_config: dict[str, Any] = {"temperature": 0}
        if structured:
            generation_config["responseMimeType"] = "application/json"
        data = self.http._post(
            self.url,
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            payload={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": generation_config,
            },
        )
        try:
            return str(data["candidates"][0]["content"]["parts"][0]["text"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError("Gemini response did not contain candidate text") from exc


def create_client(stage_config: Any, *, ollama_host: str, gemini_api_key: str | None) -> LLMClient:
    """Instantiate the provider selected by a validated StageConfig."""
    if stage_config.provider == "gemini":
        return GeminiClient(stage_config.model, gemini_api_key or "")
    return OllamaClient(stage_config.model, host=ollama_host)
