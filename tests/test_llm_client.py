from unittest.mock import Mock

import pytest
import requests

from llm_client import (
    GeminiClient,
    LLMRequestError,
    LLMResponseError,
    OllamaClient,
    parse_json_response,
    sanitize_job_text,
)


def response(status=200, payload=None, text="error"):
    item = Mock(status_code=status, text=text)
    item.json.return_value = payload
    return item


def test_sanitize_and_parse_guardrails():
    assert sanitize_job_text(" Apply now \n lots   of text ", 20) == "lots of text"
    assert sanitize_job_text(None) == ""
    assert parse_json_response('```json\n{"ok": true}\n```') == {"ok": True}
    with pytest.raises(LLMResponseError):
        parse_json_response("")
    with pytest.raises(LLMResponseError):
        parse_json_response("{bad")
    with pytest.raises(LLMResponseError):
        parse_json_response("[]")


def test_ollama_structured_success():
    session = Mock()
    session.post.return_value = response(payload={"message": {"content": '{"fit_score": 90}'}})
    client = OllamaClient("llama3.2:3b", session=session)
    assert client.generate("prompt", structured=True) == '{"fit_score": 90}'
    payload = session.post.call_args.kwargs["json"]
    assert payload["format"] == "json"
    assert "format" not in payload["options"]


def test_gemini_success_and_headers():
    session = Mock()
    session.post.return_value = response(payload={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})
    client = GeminiClient("gemini-3.8-flash", "key", session=session)
    assert client.generate("prompt", structured=True) == "{}"
    assert session.post.call_args.kwargs["headers"]["x-goog-api-key"] == "key"
    assert session.post.call_args.kwargs["json"]["generationConfig"]["responseMimeType"] == "application/json"


def test_retry_429_then_success():
    session = Mock()
    session.post.side_effect = [
        response(429),
        response(payload={"message": {"content": "ok"}}),
    ]
    client = OllamaClient("model", session=session, sleep=lambda _: None, random_fn=lambda: 0)
    assert client.generate("p") == "ok"
    assert session.post.call_count == 2


@pytest.mark.parametrize("status", [401, 403, 400])
def test_non_transient_http_errors_are_immediate(status):
    session = Mock()
    session.post.return_value = response(status)
    client = OllamaClient("model", session=session, sleep=lambda _: None)
    with pytest.raises(LLMRequestError, match=f"HTTP {status}"):
        client.generate("p")
    assert session.post.call_count == 1


@pytest.mark.parametrize("status", [429, 500])
def test_retry_exhaustion(status):
    session = Mock()
    session.post.return_value = response(status)
    client = OllamaClient("model", session=session, max_retries=2, sleep=lambda _: None, random_fn=lambda: 0)
    with pytest.raises(LLMRequestError, match="after retries"):
        client.generate("p")
    assert session.post.call_count == 3


def test_connection_and_invalid_provider_response():
    session = Mock()
    session.post.side_effect = requests.Timeout("slow")
    client = OllamaClient("model", session=session, max_retries=0)
    with pytest.raises(LLMRequestError):
        client.generate("p")
    session.post.side_effect = None
    session.post.return_value = response(payload={"unexpected": True})
    with pytest.raises(LLMResponseError):
        client.generate("p")
