"""Shared helpers for MCP tool implementations: schema loading, JSON parsing, validation."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = PACKAGE_ROOT / "schemas"
PROMPTS_DIR = PACKAGE_ROOT / "prompts"

# Strip ```json ... ``` or ``` ... ``` fences if the model wraps the response.
_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class TaskError(RuntimeError):
    """Raised when a task call fails — surfaced as an MCP tool error."""


@lru_cache(maxsize=64)
def load_schema(name: str) -> dict[str, Any]:
    """Load a JSON Schema from sealion_sidecar/schemas/<name>.json."""
    path = SCHEMAS_DIR / f"{name}.json"
    return json.loads(path.read_text())


@lru_cache(maxsize=64)
def load_prompt(name: str) -> str:
    """Load a prompt template from sealion_sidecar/prompts/<name>.md."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text()


def validate(data: Any, schema: dict[str, Any], *, what: str) -> None:
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        raise TaskError(f"{what} failed schema validation: {e.message}") from e


def render(template: str, **substitutions: str) -> str:
    """Replace `{NAME}`-style placeholders in a prompt template.

    Uses str.replace, not str.format, so literal `{` and `}` in JSON examples
    inside the template are left untouched. Use SCREAMING_SNAKE_CASE markers.
    """
    result = template
    for name, value in substitutions.items():
        result = result.replace("{" + name + "}", value)
    return result


def parse_json_response(text: str) -> dict[str, Any]:
    """Parse JSON from a model response, stripping code fences if present."""
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    if match:
        stripped = match.group(1).strip()
    try:
        result = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise TaskError(f"Model did not return valid JSON: {e.msg}") from e
    if not isinstance(result, dict):
        raise TaskError(f"Model returned JSON of type {type(result).__name__}, expected object")
    return result
