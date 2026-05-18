"""safety_check — wraps the SEA-Guard model on api.sea-lion.ai.

SEA-Guard does not accept system prompts or multi-turn conversations. The
"mode" is encoded by the shape of the single user message, per AISG's
documented templates.

Output schema is intentionally stable (two-value `category` enum) so the
tool surface doesn't churn if AISG publishes a richer taxonomy later.
Callers needing more detail than safe / sensitive_content can read the
verbatim `raw_output` field.
"""

from __future__ import annotations

from typing import Any

from sealion_sidecar.backends.base import Backend
from sealion_sidecar.config import Profile
from sealion_sidecar.tasks._common import load_schema, validate

NAME = "safety_check"
DESCRIPTION = """\
Classify content for safety using SEA-Guard, a moderation model trained specifically for
Southeast Asian languages and cultural context.

WHEN TO USE: Use this — rather than generic content moderation — whenever:
  - Content to check is in Burmese, English, Indonesian, Malay, Tagalog, Tamil, Thai, or Vietnamese
  - Content involves Southeast Asian cultural context where generic English moderation may misfire
  - detect_language_variant returned a SEA language or variant and safety screening is required
  - You need to check a user prompt before acting on it (mode: prompt_only)
  - You need to check your own response before returning it (mode: response_only)
  - You need to evaluate a full turn for harmful interaction patterns (mode: prompt_response)

WHY THIS OVER SELF-MODERATION: SEA-Guard is calibrated for SEA-language harm patterns including
region-specific slurs, culturally-specific manipulation tactics, and code-switched harmful content
that generic English classifiers frequently miss or misclassify.

MODES:
  - "prompt_only"     — check a user request for harmful intent (provide: prompt)
  - "response_only"   — check an AI-generated response before sending (provide: response)
  - "prompt_response" — evaluate the full interaction together (provide: prompt + response)

Returns: safe (bool), category ("safe" | "sensitive_content"), raw_output (verbatim model text),
advisory_note (always present — this is a classifier signal, not a hard gate).\
"""

ADVISORY_NOTE = (
    "Advisory only. SEA-Guard is a classifier, not a decisional moderation system. "
    "Human review required for high-stakes or public-facing use. Coverage: Burmese, "
    "English, Indonesian, Malay, Tagalog, Tamil, Thai, Vietnamese."
)

_INPUT_SCHEMA = load_schema(f"{NAME}.input")
_OUTPUT_SCHEMA = load_schema(f"{NAME}.output")


def input_schema() -> dict[str, Any]:
    return _INPUT_SCHEMA


def _build_message(mode: str, prompt: str | None, response: str | None) -> str:
    if mode == "prompt_only":
        return f"Human user: {prompt}"
    if mode == "prompt_response":
        return f"Human user: {prompt}\nAI assistant: {response}"
    if mode == "response_only":
        return f"Human user:\nAI assistant: {response}"
    raise AssertionError(f"unreachable: mode={mode}")  # schema enforces enum


def _classify(raw_output: str) -> tuple[bool, str]:
    """Map SEA-Guard's verbatim response to (safe, category).

    Conservative parse: only treat as safe if the first token of the cleaned
    response is 'safe'. Anything else — 'unsafe', empty, or unexpected
    prose — is labeled sensitive_content for human review.
    """
    first_token = raw_output.strip().lower().lstrip("\"'`*[(").split(maxsplit=1)
    first = first_token[0].rstrip(".,!?:;\"'`*])") if first_token else ""
    if first == "safe":
        return True, "safe"
    return False, "sensitive_content"


async def run(args: dict[str, Any], backend: Backend, profile: Profile) -> dict[str, Any]:
    validate(args, _INPUT_SCHEMA, what="input")

    mode = args["mode"]
    user_content = _build_message(mode, args.get("prompt"), args.get("response"))

    raw = await backend.chat(
        messages=[{"role": "user", "content": user_content}],
        model=profile.model,
        temperature=profile.temperature,
        max_tokens=profile.max_tokens,
        extra_body=profile.extra_body() or None,
    )

    safe, category = _classify(raw)
    result = {
        "safe": safe,
        "category": category,
        "mode": mode,
        "model": profile.model,
        "raw_output": raw,
        "advisory_note": ADVISORY_NOTE,
    }
    validate(result, _OUTPUT_SCHEMA, what="output")
    return result
