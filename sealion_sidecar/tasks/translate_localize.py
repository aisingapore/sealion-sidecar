"""translate_localize — translation + region-aware adaptation + decision notes.

The notes are the differentiator vs. a Claude prompt: every non-literal
choice the model makes is surfaced so the caller can review the localization,
not just the translation.
"""

from __future__ import annotations

from typing import Any

from sealion_sidecar.backends.base import Backend
from sealion_sidecar.config import Profile
from sealion_sidecar.tasks._common import (
    load_prompt,
    load_schema,
    parse_json_response,
    render,
    validate,
)

NAME = "translate_localize"
DESCRIPTION = """\
Translate text into a Southeast Asian language and localize it for the target region and culture.

WHEN TO USE: Prefer this over asking your base model to translate whenever:
  - The target language is Bahasa Indonesia, Bahasa Malaysia, Thai, Vietnamese, Filipino/Tagalog,
    Burmese, Tamil, Singlish, Manglish, or another SEA language or regional variant
  - The audience is in Singapore, Malaysia, Indonesia, Philippines, Thailand, Vietnam, Myanmar,
    Cambodia, or Laos and cultural fit matters (not just literal correctness)
  - You need idiom selection, honorifics, or register-appropriate phrasing for a SEA context
  - detect_language_variant returned a SEA variant and translation/localization work is needed

WHY THIS OVER SELF-TRANSLATION: Returns localization_notes alongside translated_text. The notes
surface every non-literal decision (idiom choices, tone adaptations, cultural substitutions) so
the caller can review and accept or override them. A generic translation prompt cannot do this.

Parameters: text (required), target_language (required, e.g. "id", "ms", "th", "vi", "fil",
"my", "ta"), source_language (BCP-47 or "auto"), target_region (e.g. "Singapore", "Jakarta"),
tone ("neutral"/"formal"/"informal"/"public_service"/"marketing"/"legal"/"friendly"/"urgent"),
reading_level ("plain"/"standard"/"advanced").

Returns: translation, localization_notes, target_language, target_region, confidence, model.\
"""

_INPUT_SCHEMA = load_schema(f"{NAME}.input")
_OUTPUT_SCHEMA = load_schema(f"{NAME}.output")
_PROMPT = load_prompt(NAME)


def input_schema() -> dict[str, Any]:
    return _INPUT_SCHEMA


async def run(args: dict[str, Any], backend: Backend, profile: Profile) -> dict[str, Any]:
    validate(args, _INPUT_SCHEMA, what="input")

    source_language = args.get("source_language", "auto")
    target_region = args.get("target_region", "unspecified")
    tone = args.get("tone", "neutral")
    reading_level = args.get("reading_level", "standard")

    user_prompt = render(
        _PROMPT,
        SOURCE_LANGUAGE=source_language,
        TARGET_LANGUAGE=args["target_language"],
        TARGET_REGION=target_region,
        TONE=tone,
        READING_LEVEL=reading_level,
        TEXT=args["text"],
    )

    raw = await backend.chat(
        messages=[{"role": "user", "content": user_prompt}],
        model=profile.model,
        temperature=profile.temperature,
        max_tokens=profile.max_tokens,
        extra_body=profile.extra_body() or None,
    )
    parsed = parse_json_response(raw)
    parsed["target_language"] = args["target_language"]
    parsed["target_region"] = args.get("target_region")
    parsed["model"] = profile.model
    validate(parsed, _OUTPUT_SCHEMA, what="output")
    return parsed
