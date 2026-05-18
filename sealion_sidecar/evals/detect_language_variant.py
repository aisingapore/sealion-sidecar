"""Eval for detect_language_variant. Scores on exact variant-label match."""

from __future__ import annotations

from typing import Any

from sealion_sidecar.evals._runner import Example, run, run_eval
from sealion_sidecar.tasks import detect_language_variant as tool

DATASET: list[Example] = [
    Example(
        name="singlish_lah_particle",
        args={"text": "Can lah, but later I settle for you."},
        expected={"variant": "singapore_colloquial_english"},
        claude_prompt=(
            "Identify the regional variant of this text. Return just the snake_case "
            "label (e.g. singapore_colloquial_english).\n\nText: "
            "Can lah, but later I settle for you."
        ),
    ),
    Example(
        name="bahasa_indonesia_formal",
        args={"text": "Mohon datang ke kantor untuk verifikasi data Anda."},
        expected={"variant": "bahasa_indonesia_formal"},
        claude_prompt=(
            "Identify the regional variant. Return just the snake_case label.\n\n"
            "Text: Mohon datang ke kantor untuk verifikasi data Anda."
        ),
    ),
    Example(
        name="manglish",
        args={"text": "Aiyoh, why like that one? Cannot lah, very mafan."},
        expected={"variant": "malaysia_colloquial_english"},
        claude_prompt="Identify the regional variant. Return just the snake_case label.\n\nText: Aiyoh, why like that one? Cannot lah, very mafan.",
    ),
    Example(
        name="thai_standard",
        args={"text": "ขอบคุณค่ะ วันนี้อากาศดีมาก"},
        expected={"variant": "thai_standard"},
        claude_prompt="Identify the regional variant. Return just the snake_case label.\n\nText: ขอบคุณค่ะ วันนี้อากาศดีมาก",
    ),
    Example(
        name="vietnamese_standard",
        args={"text": "Tôi muốn đặt một bàn cho hai người tối nay."},
        expected={"variant": "vietnamese_standard"},
        claude_prompt="Identify the regional variant. Return just the snake_case label.\n\nText: Tôi muốn đặt một bàn cho hai người tối nay.",
    ),
    Example(
        name="tagalog_code_switch",
        args={"text": "Pwede ba mag-ride share kasi traffic talaga ngayon?"},
        expected={"variant": "tagalog_standard", "code_switching": True},
        claude_prompt="Identify the regional variant. Return just the snake_case label.\n\nText: Pwede ba mag-ride share kasi traffic talaga ngayon?",
    ),
]


async def _call(ex: Example, backend: Any, config: Any) -> Any:
    return await tool.run(ex.args, backend, config.profile_for(tool.NAME))


def _score(ex: Example, result: Any) -> str:
    if ex.expected and result.get("variant") == ex.expected.get("variant"):
        return "PASS"
    return "FAIL"


async def main() -> int:
    return await run_eval(tool.NAME, DATASET, _call, _score)


if __name__ == "__main__":
    run(main)
