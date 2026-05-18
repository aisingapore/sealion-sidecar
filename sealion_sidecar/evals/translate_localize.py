"""Eval for translate_localize.

No automatic scoring — translation/localization quality needs human review.
The runner prints SEA-LION and Claude outputs side-by-side so you can
compare the localization_notes (the differentiating field) directly.
"""

from __future__ import annotations

from typing import Any

from sealion_sidecar.evals._runner import Example, run, run_eval
from sealion_sidecar.tasks import translate_localize as tool

DATASET: list[Example] = [
    Example(
        name="public_service_to_bahasa_indonesia",
        args={
            "text": (
                "We are launching a new digital identity service. "
                "Please register immediately to avoid disruption."
            ),
            "target_language": "bahasa_indonesia",
            "target_region": "indonesia",
            "tone": "public_service",
            "reading_level": "plain",
        },
        claude_prompt=(
            "Translate to Bahasa Indonesia for a public-service announcement in "
            "Indonesia, plain reading level. Also list the localization decisions "
            "you made beyond a literal translation.\n\nText: We are launching a new "
            "digital identity service. Please register immediately to avoid disruption."
        ),
    ),
    Example(
        name="customer_support_to_singlish",
        args={
            "text": "Your order is delayed by two business days. We apologize for the inconvenience.",
            "target_language": "singlish",
            "target_region": "singapore",
            "tone": "friendly",
            "reading_level": "standard",
        },
        claude_prompt=(
            "Translate/localize to Singlish (Singapore colloquial English), friendly "
            "tone. List localization decisions beyond literal translation.\n\n"
            "Your order is delayed by two business days. We apologize for the inconvenience."
        ),
    ),
    Example(
        name="health_alert_to_tagalog",
        args={
            "text": "Dengue cases are rising in your area. Empty standing water around your home.",
            "target_language": "tagalog",
            "target_region": "philippines",
            "tone": "public_service",
            "reading_level": "plain",
        },
        claude_prompt=(
            "Translate to Tagalog for a Philippines public-health alert, plain "
            "language. List localization decisions.\n\nDengue cases are rising in "
            "your area. Empty standing water around your home."
        ),
    ),
    Example(
        name="marketing_to_thai",
        args={
            "text": "Limited time offer: 30% off all rides this weekend!",
            "target_language": "thai",
            "target_region": "thailand",
            "tone": "marketing",
            "reading_level": "standard",
        },
        claude_prompt=(
            "Translate to Thai for a Thailand marketing message. List localization "
            "decisions.\n\nLimited time offer: 30% off all rides this weekend!"
        ),
    ),
]


async def _call(ex: Example, backend: Any, config: Any) -> Any:
    return await tool.run(ex.args, backend, config.profile_for(tool.NAME))


async def main() -> int:
    return await run_eval(tool.NAME, DATASET, _call, score=None)


if __name__ == "__main__":
    run(main)
