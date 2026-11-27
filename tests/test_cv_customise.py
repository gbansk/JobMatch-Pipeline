import copy
import logging

import pytest

from cv_customise import build_cv_patch_prompt, customise_cv, merge_cv_patch
from llm_client import LLMResponseError


@pytest.fixture
def base_cv():
    return {
        "basics": {"name": "Candidate"},
        "summary": "Original",
        "skills": ["Python", "Go"],
        "experience": [{"role_header": "Engineer", "highlights": ["Built APIs", "Led delivery"]}],
    }


class FakeClient:
    def __init__(self, value):
        self.value = value
        self.calls = 0

    def generate(self, prompt, *, structured=False):
        self.calls += 1
        return self.value


def test_prompt_sanitizes_job_and_merge_is_pure(base_cv):
    original = copy.deepcopy(base_cv)
    prompt = build_cv_patch_prompt(base_cv, "Apply now\nNeed Python")
    assert "Apply now" not in prompt
    result = merge_cv_patch(
        base_cv,
        {
            "summary": "Targeted",
            "skills_order": ["Go", "Python"],
            "experience_updates": {"0": {"bullet_updates": {"1": "Led platform delivery"}}},
        },
    )
    assert result["summary"] == "Targeted"
    assert result["experience"][0]["highlights"][1] == "Led platform delivery"
    assert base_cv == original


def test_unknown_ids_and_factual_fields_are_ignored(base_cv, caplog):
    with caplog.at_level(logging.WARNING):
        result = merge_cv_patch(
            base_cv,
            {
                "experience_updates": {
                    "missing": {"bullet_updates": {"0": "invented"}},
                    "0": {"bullet_updates": {"99": "bad"}, "dates": "invented"},
                }
            },
        )
    assert result == base_cv
    assert "Ignoring unknown CV role ID" in caplog.text
    assert "factual CV field" in caplog.text


def test_customise_cv_accepts_fenced_json_and_filters_unknown_fields(base_cv, caplog):
    client = FakeClient('```json\n{"summary":"Tailored","unknown":"x"}\n```')
    with caplog.at_level(logging.WARNING):
        result = customise_cv(base_cv, "Python role", client)
    assert result["summary"] == "Tailored"
    assert client.calls == 1
    assert "unsupported CV patch field" in caplog.text


@pytest.mark.parametrize("payload", ["", "{bad", "{}"])
def test_customise_cv_rejects_bad_json(base_cv, payload):
    with pytest.raises(LLMResponseError):
        customise_cv(base_cv, "job", FakeClient(payload))


def test_invalid_cv_structure_rejected():
    with pytest.raises(ValueError, match="experience"):
        merge_cv_patch({"experience": "bad"}, {})
