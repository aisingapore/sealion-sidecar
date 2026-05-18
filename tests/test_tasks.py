"""Tests for task implementations using a stubbed backend."""

from __future__ import annotations

from typing import Any

import pytest

from sealion_sidecar.config import Profile
from sealion_sidecar.tasks import (
    detect_language_variant,
    safety_check,
    translate_localize,
)
from sealion_sidecar.tasks._common import TaskError


class StubBackend:
    def __init__(self, response: str) -> None:
        self.response = response
        self.last_call: dict[str, Any] | None = None

    async def chat(self, messages, *, model, temperature, max_tokens, extra_body=None):
        self.last_call = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "extra_body": extra_body,
        }
        return self.response

    async def list_models(self):
        return []


def _profile(thinking_mode: str | None = None) -> Profile:
    return Profile(
        name="test",
        model="aisingapore/Test-Model",
        temperature=0.1,
        max_tokens=512,
        thinking_mode=thinking_mode,
    )


@pytest.mark.asyncio
async def test_detect_language_variant_happy_path() -> None:
    backend = StubBackend(
        '{"languages": ["english"], "variant": "singapore_colloquial_english", '
        '"code_switching": false, "register": "informal", '
        '"notes": ["Contains particle lah"], "confidence": 0.9}'
    )
    result = await detect_language_variant.run(
        {"text": "Can lah, but later I settle for you."},
        backend,
        _profile(),
    )
    assert result["variant"] == "singapore_colloquial_english"
    assert result["model"] == "aisingapore/Test-Model"
    assert backend.last_call is not None
    assert "Can lah" in backend.last_call["messages"][0]["content"]


@pytest.mark.asyncio
async def test_detect_language_variant_strips_code_fence() -> None:
    backend = StubBackend(
        '```json\n{"languages": ["thai"], "variant": "thai_standard", '
        '"code_switching": false, "register": "neutral", "notes": [], '
        '"confidence": 0.95}\n```'
    )
    result = await detect_language_variant.run({"text": "สวัสดี"}, backend, _profile())
    assert result["variant"] == "thai_standard"


@pytest.mark.asyncio
async def test_detect_language_variant_rejects_invalid_input() -> None:
    backend = StubBackend("")
    with pytest.raises(TaskError, match="input failed"):
        await detect_language_variant.run({}, backend, _profile())


@pytest.mark.asyncio
async def test_detect_language_variant_rejects_invalid_register() -> None:
    backend = StubBackend(
        '{"languages": ["english"], "variant": "standard", "code_switching": false, '
        '"register": "casual", "notes": [], "confidence": 0.5}'
    )
    with pytest.raises(TaskError, match="output failed"):
        await detect_language_variant.run({"text": "hello"}, backend, _profile())


@pytest.mark.asyncio
async def test_detect_language_variant_rejects_non_json() -> None:
    backend = StubBackend("Sure, here's my analysis: the language is English.")
    with pytest.raises(TaskError, match="valid JSON"):
        await detect_language_variant.run({"text": "hello"}, backend, _profile())


@pytest.mark.asyncio
async def test_translate_localize_happy_path() -> None:
    backend = StubBackend(
        '{"translation": "Kami memperkenalkan layanan identitas digital baru.", '
        '"localization_notes": ["Used memperkenalkan for softer public-service tone."], '
        '"confidence": 0.88}'
    )
    result = await translate_localize.run(
        {
            "text": "We are launching a new digital identity service.",
            "target_language": "bahasa_indonesia",
            "target_region": "indonesia",
            "tone": "public_service",
            "reading_level": "plain",
        },
        backend,
        _profile(),
    )
    assert result["translation"].startswith("Kami memperkenalkan")
    assert result["target_language"] == "bahasa_indonesia"
    assert result["target_region"] == "indonesia"
    assert result["model"] == "aisingapore/Test-Model"
    # Prompt should carry all the input parameters through.
    prompt = backend.last_call["messages"][0]["content"]
    assert "bahasa_indonesia" in prompt
    assert "indonesia" in prompt
    assert "public_service" in prompt
    assert "plain" in prompt


@pytest.mark.asyncio
async def test_translate_localize_handles_missing_optional_region() -> None:
    backend = StubBackend('{"translation": "Halo", "localization_notes": [], "confidence": 0.9}')
    result = await translate_localize.run(
        {"text": "Hello", "target_language": "bahasa_malay"},
        backend,
        _profile(),
    )
    assert result["target_region"] is None
    prompt = backend.last_call["messages"][0]["content"]
    assert "unspecified" in prompt  # default region placeholder


@pytest.mark.asyncio
async def test_translate_localize_rejects_invalid_tone() -> None:
    backend = StubBackend("")
    with pytest.raises(TaskError, match="input failed"):
        await translate_localize.run(
            {"text": "x", "target_language": "thai", "tone": "sarcastic"},
            backend,
            _profile(),
        )


@pytest.mark.asyncio
async def test_translate_localize_rejects_unbounded_confidence() -> None:
    backend = StubBackend('{"translation": "x", "localization_notes": [], "confidence": 1.5}')
    with pytest.raises(TaskError, match="output failed"):
        await translate_localize.run(
            {"text": "hello", "target_language": "thai"}, backend, _profile()
        )


@pytest.mark.asyncio
async def test_safety_check_safe_response() -> None:
    backend = StubBackend("safe")
    result = await safety_check.run(
        {"mode": "prompt_only", "prompt": "How do I bake bread?"},
        backend,
        _profile(),
    )
    assert result["safe"] is True
    assert result["category"] == "safe"
    assert result["raw_output"] == "safe"
    assert backend.last_call["messages"][0]["content"] == "Human user: How do I bake bread?"


@pytest.mark.asyncio
async def test_safety_check_unsafe_response() -> None:
    backend = StubBackend("unsafe")
    result = await safety_check.run(
        {"mode": "prompt_only", "prompt": "Why are people from X so stupid?"},
        backend,
        _profile(),
    )
    assert result["safe"] is False
    assert result["category"] == "sensitive_content"


@pytest.mark.asyncio
async def test_safety_check_prompt_response_message_shape() -> None:
    backend = StubBackend("unsafe")
    await safety_check.run(
        {
            "mode": "prompt_response",
            "prompt": "Is X true?",
            "response": "Yes, here are the slurs.",
        },
        backend,
        _profile(),
    )
    content = backend.last_call["messages"][0]["content"]
    assert content.startswith("Human user: Is X true?")
    assert "AI assistant: Yes, here are the slurs." in content


@pytest.mark.asyncio
async def test_safety_check_response_only_message_shape() -> None:
    backend = StubBackend("safe")
    await safety_check.run(
        {"mode": "response_only", "response": "Some response."},
        backend,
        _profile(),
    )
    content = backend.last_call["messages"][0]["content"]
    assert content == "Human user:\nAI assistant: Some response."


@pytest.mark.asyncio
async def test_safety_check_unparseable_treated_as_unsafe() -> None:
    backend = StubBackend("I think this is generally fine but...")
    result = await safety_check.run({"mode": "prompt_only", "prompt": "x"}, backend, _profile())
    # Conservative parse — anything not starting with "safe" → sensitive_content.
    assert result["safe"] is False
    assert result["category"] == "sensitive_content"
    assert result["raw_output"] == "I think this is generally fine but..."


@pytest.mark.asyncio
async def test_safety_check_rejects_missing_prompt_for_prompt_only() -> None:
    backend = StubBackend("safe")
    with pytest.raises(TaskError, match="input failed"):
        await safety_check.run({"mode": "prompt_only"}, backend, _profile())


@pytest.mark.asyncio
async def test_safety_check_rejects_missing_response_for_response_only() -> None:
    backend = StubBackend("safe")
    with pytest.raises(TaskError, match="input failed"):
        await safety_check.run({"mode": "response_only"}, backend, _profile())


@pytest.mark.asyncio
async def test_safety_check_strips_punctuation_around_safe_token() -> None:
    backend = StubBackend("Safe.")
    result = await safety_check.run({"mode": "prompt_only", "prompt": "x"}, backend, _profile())
    assert result["safe"] is True
