"""detect_language_variant — the routing primitive.

Host agents call this first to decide whether SEA-LION is worth calling for
follow-up work. Returns languages, regional variant, code-switching flag,
register, and short observations.
"""

from __future__ import annotations

from typing import Any

from sealion_sidecar.backends.base import Backend
from sealion_sidecar.config import Profile
from sealion_sidecar.tasks._common import (
    load_prompt,
    load_schema,
    parse_json_response,
    validate,
)

NAME = "detect_language_variant"
DESCRIPTION = """\
Identify the language, regional variant, code-switching status, and register of a piece of text.

WHEN TO USE: Call this first whenever you encounter user content that may contain a Southeast
Asian language or dialect — before deciding whether to translate, localize, or safety-check it.
Trigger examples:
  - User writes in Thai, Vietnamese, Indonesian, Malay, Tagalog, Burmese, Tamil, or Khmer
  - User writes in Singlish (Singapore English) or Manglish (Malaysian English)
  - Text mixes English with any SEA language (code-switching)
  - You are unsure whether the text is standard English or a SEA colloquial variant
  - You need to know the language before deciding which follow-up SEA-LION tool to call

Returns: language (BCP-47 code), variant (e.g. "singapore_colloquial_english",
"bahasa_indonesia", "manglish"), code_switching (bool), register ("formal"/"informal"/
"colloquial"), and short observations explaining the classification.

ROUTING: If code_switching=true or variant names a SEA language/dialect, route translation
or safety work to translate_localize or safety_check rather than handling it yourself.\
"""

_INPUT_SCHEMA = load_schema(f"{NAME}.input")
_OUTPUT_SCHEMA = load_schema(f"{NAME}.output")
_PROMPT = load_prompt(NAME)


def input_schema() -> dict[str, Any]:
    return _INPUT_SCHEMA


async def run(args: dict[str, Any], backend: Backend, profile: Profile) -> dict[str, Any]:
    validate(args, _INPUT_SCHEMA, what="input")

    user_prompt = _PROMPT.replace("{INPUT}", args["text"])
    raw = await backend.chat(
        messages=[{"role": "user", "content": user_prompt}],
        model=profile.model,
        temperature=profile.temperature,
        max_tokens=profile.max_tokens,
        extra_body=profile.extra_body() or None,
    )
    parsed = parse_json_response(raw)
    parsed["model"] = profile.model
    validate(parsed, _OUTPUT_SCHEMA, what="output")
    return parsed
