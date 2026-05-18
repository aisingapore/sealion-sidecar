from __future__ import annotations

from pathlib import Path

import pytest

from sealion_sidecar.config import ConfigError, load_config

EXAMPLE_PATH = Path(__file__).parent.parent / "config.example.yaml"


def test_example_config_loads() -> None:
    config = load_config(EXAMPLE_PATH)
    assert config.api.base_url == "https://api.sea-lion.ai/v1"
    assert config.api.key_env == "SEALION_API_KEY"
    assert "safety" in config.profiles
    assert config.profiles["safety"].model.startswith("aisingapore/SEA-Guard")
    assert config.profiles["reasoning"].thinking_mode == "on"


def test_routing_resolves_known_task() -> None:
    config = load_config(EXAMPLE_PATH)
    profile = config.profile_for("translate_localize")
    assert profile.name == "best-language"


def test_routing_falls_back_to_default() -> None:
    config = load_config(EXAMPLE_PATH)
    profile = config.profile_for("nonexistent_task")
    assert profile.name == config.default_profile


def test_thinking_mode_emits_extra_body() -> None:
    config = load_config(EXAMPLE_PATH)
    extra = config.profiles["reasoning"].extra_body()
    assert extra == {"chat_template_kwargs": {"thinking_mode": "on"}}


def test_safety_profile_has_no_extra_body() -> None:
    config = load_config(EXAMPLE_PATH)
    assert config.profiles["safety"].extra_body() == {}


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "does-not-exist.yaml")


def test_missing_model_field_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("profiles:\n  foo:\n    temperature: 0.1\n")
    with pytest.raises(ConfigError, match="missing required field"):
        load_config(bad)


def test_routing_to_unknown_profile_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "profiles:\n  foo:\n    model: m\nrouting:\n  default: foo\n  some_task: not-a-profile\n"
    )
    with pytest.raises(ConfigError, match="not defined"):
        load_config(bad)


def test_api_key_missing_raises_at_use(monkeypatch: pytest.MonkeyPatch) -> None:
    config = load_config(EXAMPLE_PATH)
    monkeypatch.delenv("SEALION_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="API key not found"):
        config.api_key()
