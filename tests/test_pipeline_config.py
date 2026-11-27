import json
import logging

import pytest

from pipeline_config import ConfigurationError, PipelineConfig, should_run_stage


@pytest.mark.parametrize("stage", ["evaluate", "cover_letter", "cv_customise"])
def test_stage_routes_to_configured_provider_and_model(stage):
    config = PipelineConfig.from_mapping(
        {stage: {"provider": "ollama", "model": "qwen2.5:3b"}}, gemini_api_key=""
    )
    assert config.stages[stage].provider == "ollama"
    assert config.stages[stage].model == "qwen2.5:3b"


def test_gemini_without_key_falls_back_to_ollama(caplog):
    with caplog.at_level(logging.WARNING):
        config = PipelineConfig.from_mapping(
            {"cover_letter": {"provider": "gemini", "model": "gemini-3.8-flash"}},
            gemini_api_key="",
        )
    assert config.stages["cover_letter"].provider == "ollama"
    assert "falling back to Ollama" in caplog.text


def test_gemini_with_key_is_retained():
    config = PipelineConfig.from_mapping(
        {"evaluate": {"provider": "gemini", "model": "gemini-3.5-flash-lite"}},
        gemini_api_key="secret",
    )
    assert config.stages["evaluate"].provider == "gemini"


def test_gemini_uses_gemini_default_model():
    config = PipelineConfig.from_mapping(
        {"evaluate": {"provider": "gemini"}}, gemini_api_key="secret"
    )
    assert config.stages["evaluate"].model == "gemini-3.8-flash"


def test_invalid_provider_fails_fast():
    with pytest.raises(ConfigurationError, match="Unsupported provider"):
        PipelineConfig.from_mapping({"evaluate": {"provider": "openai"}})


def test_config_file_and_invalid_values(tmp_path):
    path = tmp_path / "pipeline.json"
    path.write_text(json.dumps({"max_job_chars": 50, "evaluate": {"min_score": 70}}))
    config = PipelineConfig.from_file(str(path))
    assert config.max_job_chars == 50
    assert should_run_stage("evaluate", 70, config) is True
    assert should_run_stage("evaluate", 69, config) is False
    assert should_run_stage("evaluate", None, config) is False
    with pytest.raises(ConfigurationError):
        PipelineConfig.from_mapping({"evaluate": {"min_score": "bad"}})
    with pytest.raises(ConfigurationError):
        PipelineConfig.from_mapping({"max_job_chars": 0})


@pytest.mark.parametrize("score", [None, "bad"])
def test_score_gate_handles_invalid_scores(score):
    config = PipelineConfig.from_mapping({"cv_customise": {"min_score": 80}})
    assert should_run_stage("cv_customise", score, config) is False
