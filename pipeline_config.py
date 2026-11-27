"""Configuration and provider routing for pipeline LLM stages."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)
STAGES = ("evaluate", "cover_letter", "cv_customise")
DEFAULT_OLLAMA_MODEL = "llama3.2"


def configured_gemini_key() -> str:
    """Read the key from the environment, with a minimal optional .env fallback."""
    value = os.getenv("GEMINI_API_KEY", "")
    if value:
        return value
    try:
        with open(".env", "r", encoding="utf-8") as handle:
            for line in handle:
                name, separator, raw_value = line.partition("=")
                if separator and name.strip() == "GEMINI_API_KEY":
                    return raw_value.strip().strip("\"'")
    except OSError:
        pass
    return ""


class ConfigurationError(ValueError):
    """Raised when pipeline configuration is invalid."""


@dataclass(frozen=True)
class StageConfig:
    provider: str = "ollama"
    model: str = DEFAULT_OLLAMA_MODEL
    min_score: float | None = None


@dataclass(frozen=True)
class PipelineConfig:
    stages: dict[str, StageConfig]
    ollama_host: str = "http://localhost:11434"
    max_job_chars: int = 12000

    @classmethod
    def defaults(cls) -> "PipelineConfig":
        return cls({stage: StageConfig() for stage in STAGES})

    @classmethod
    def from_mapping(
        cls, mapping: dict[str, Any] | None = None, gemini_api_key: str | None = None
    ) -> "PipelineConfig":
        raw = mapping or {}
        api_key = configured_gemini_key() if gemini_api_key is None else gemini_api_key
        stages: dict[str, StageConfig] = {}
        for stage in STAGES:
            values = raw.get(stage, {}) or {}
            if not isinstance(values, dict):
                raise ConfigurationError(f"Configuration for stage '{stage}' must be an object")
            provider = str(values.get("provider", "ollama")).lower()
            if provider not in {"ollama", "gemini"}:
                raise ConfigurationError(
                    f"Unsupported provider '{provider}' for stage '{stage}'. "
                    "Supported providers: ollama, gemini."
                )
            model = str(values.get("model", DEFAULT_OLLAMA_MODEL)).strip()
            if not model:
                raise ConfigurationError(f"Model for stage '{stage}' must not be empty")
            min_score = values.get("min_score")
            if min_score is not None:
                try:
                    min_score = float(min_score)
                except (TypeError, ValueError) as exc:
                    raise ConfigurationError(
                        f"min_score for stage '{stage}' must be numeric"
                    ) from exc
            if provider == "gemini" and not api_key.strip():
                LOGGER.warning(
                    "GEMINI_API_KEY is missing; stage '%s' is falling back to Ollama (%s).",
                    stage,
                    DEFAULT_OLLAMA_MODEL,
                )
                provider, model = "ollama", DEFAULT_OLLAMA_MODEL
            stages[stage] = StageConfig(provider, model, min_score)
        try:
            max_job_chars = int(raw.get("max_job_chars", 12000))
        except (TypeError, ValueError) as exc:
            raise ConfigurationError("max_job_chars must be a positive integer") from exc
        if max_job_chars <= 0:
            raise ConfigurationError("max_job_chars must be a positive integer")
        return cls(
            stages=stages,
            ollama_host=str(raw.get("ollama_host", "http://localhost:11434")).rstrip("/"),
            max_job_chars=max_job_chars,
        )

    @classmethod
    def from_file(cls, path: str, gemini_api_key: str | None = None) -> "PipelineConfig":
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ConfigurationError("Pipeline configuration must be a JSON object")
        return cls.from_mapping(data, gemini_api_key=gemini_api_key)


def should_run_stage(stage: str, score: float | None, config: PipelineConfig) -> bool:
    """Return whether a stage passes its optional score gate."""
    threshold = config.stages[stage].min_score
    if threshold is None:
        return True
    if score is None:
        return False
    try:
        return float(score) >= threshold
    except (TypeError, ValueError):
        return False
