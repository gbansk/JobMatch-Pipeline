"""Hallucination-resistant CV customisation using constrained JSON patches."""

from __future__ import annotations

import copy
import json
import logging
import re
from typing import Any

from llm_client import LLMClient, LLMResponseError, parse_json_response, sanitize_job_text

LOGGER = logging.getLogger(__name__)
ALLOWED_PATCH_FIELDS = {"summary", "skills_order", "highlighted_skills", "experience_updates"}
FACTUAL_FIELDS = {"role_header", "company", "employer", "dates", "start_date", "end_date"}


def build_cv_patch_prompt(base_cv: dict[str, Any], job_description: str, max_chars: int = 12000) -> str:
    """Build a strict patch-only prompt."""
    roles = []
    for index, role in enumerate(base_cv.get("experience", base_cv.get("work", []))):
        role_id = role.get("id", str(index))
        roles.append(
            {"role_id": role_id, "bullet_ids": list(map(str, range(len(role.get("highlights", [])))))}
        )
    return (
        "Return ONLY a JSON object containing a CV patch. Allowed top-level fields are "
        "summary, skills_order, highlighted_skills, and experience_updates. "
        "Only reference the supplied role and bullet IDs. Never invent employers, roles, dates, "
        "or unsupported facts. Use experience_updates in this exact form: "
        '{"role_id":{"bullet_updates":{"bullet_id":"replacement bullet text"}}}. '
        "bullet_id values must be existing numeric indexes.\n"
        f"Available roles: {roles}\n"
        f"Job description:\n{sanitize_job_text(job_description, max_chars)}\n"
        f"Base CV:\n{json.dumps(base_cv, ensure_ascii=True)}"
    )


def _experience_key(cv: dict[str, Any]) -> str:
    return "experience" if "experience" in cv else "work"


def _matching_base_skill(candidate: str, base_skills: list[str]) -> str | None:
    normalized = candidate.strip().casefold()
    if not normalized:
        return None
    for base_skill in base_skills:
        base_normalized = base_skill.strip().casefold()
        if normalized == base_normalized or re.search(
            rf"(?<!\w){re.escape(normalized)}(?!\w)", base_normalized
        ):
            return base_skill
    return None


def _apply_skill_patch(result: dict[str, Any], patch: dict[str, Any]) -> None:
    base_skills = result.get("skills", [])
    if not isinstance(base_skills, list) or not all(isinstance(item, str) for item in base_skills):
        return
    requested_order = patch.get("skills_order", [])
    if isinstance(requested_order, list):
        ordered = []
        for item in requested_order:
            if not isinstance(item, str):
                continue
            matched = _matching_base_skill(item, base_skills)
            if matched is not None and matched not in ordered:
                ordered.append(matched)
        result["skills"] = ordered + [item for item in base_skills if item not in ordered]
    highlighted = patch.get("highlighted_skills")
    if isinstance(highlighted, list):
        result["highlighted_skills"] = [
            matched
            for item in highlighted
            if isinstance(item, str)
            for matched in [_matching_base_skill(item, base_skills)]
            if matched is not None
        ]


def merge_cv_patch(base_cv: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Return a validated deep-copied CV with only safe patch fields applied."""
    _validate_cv(base_cv)
    if not isinstance(patch, dict):
        raise ValueError("CV patch must be a JSON object")
    result = copy.deepcopy(base_cv)
    if "summary" in patch and isinstance(patch["summary"], str):
        result["summary"] = patch["summary"]
    _apply_skill_patch(result, patch)
    roles = result.get(_experience_key(result), [])
    updates = patch.get("experience_updates", {})
    if isinstance(updates, list):
        updates = {str(item.get("role_id")): item for item in updates if isinstance(item, dict)}
    if isinstance(updates, dict):
        for role_id, role_update in updates.items():
            role = next(
                (item for index, item in enumerate(roles) if str(item.get("id", index)) == str(role_id)),
                None,
            )
            if role is None:
                LOGGER.warning("Ignoring unknown CV role ID '%s'", role_id)
                continue
            if not isinstance(role_update, dict):
                continue
            bullets = role.get("highlights", [])
            bullet_updates = role_update.get("bullet_updates", {})
            if isinstance(bullet_updates, list):
                bullet_updates = {
                    str(item.get("bullet_id")): item for item in bullet_updates if isinstance(item, dict)
                }
            if isinstance(bullet_updates, dict):
                for bullet_id, bullet_update in bullet_updates.items():
                    try:
                        bullet_index = int(bullet_id)
                    except (TypeError, ValueError):
                        LOGGER.warning("Ignoring unknown CV bullet ID '%s'", bullet_id)
                        continue
                    if not 0 <= bullet_index < len(bullets):
                        LOGGER.warning("Ignoring unknown CV bullet ID '%s'", bullet_id)
                        continue
                    if isinstance(bullet_update, str):
                        bullets[bullet_index] = bullet_update
                    elif isinstance(bullet_update, dict) and isinstance(
                        bullet_update.get("text"), str
                    ):
                        bullets[bullet_index] = bullet_update["text"]
            for field, value in role_update.items():
                if field in FACTUAL_FIELDS:
                    LOGGER.warning("Ignoring factual CV field '%s'", field)
    _validate_cv(result)
    return result


def _validate_cv(cv: dict[str, Any]) -> None:
    if not isinstance(cv, dict):
        raise ValueError("CV must be a JSON object")
    experiences = cv.get(_experience_key(cv), [])
    if not isinstance(experiences, list) or not all(
        isinstance(role, dict) and isinstance(role.get("highlights", []), list)
        for role in experiences
    ):
        raise ValueError("CV experience must be a list of objects")


def customise_cv(
    base_cv: dict[str, Any], job_description: str, client: LLMClient, max_chars: int = 12000
) -> dict[str, Any]:
    """Generate and safely merge one constrained CV patch."""
    raw = client.generate(build_cv_patch_prompt(base_cv, job_description, max_chars), structured=True)
    patch = parse_json_response(raw)
    unknown = set(patch) - ALLOWED_PATCH_FIELDS
    for field in unknown:
        LOGGER.warning("Ignoring unsupported CV patch field '%s'", field)
    allowed_patch = {key: value for key, value in patch.items() if key in ALLOWED_PATCH_FIELDS}
    if not allowed_patch:
        raise LLMResponseError(
            "CV patch is missing required tailored fields: "
            "summary, skills_order, highlighted_skills, or experience_updates"
        )
    return merge_cv_patch(base_cv, allowed_patch)
