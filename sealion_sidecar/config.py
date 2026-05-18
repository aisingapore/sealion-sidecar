"""Config loader for SEA-LION Sidecar.

Loads ~/.sealion/config.yaml (or the path in SEALION_CONFIG) into typed dataclasses.
The API key is read from the env var named by `api.key_env` at use time, never logged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path.home() / ".sealion" / "config.yaml"
DEFAULT_BASE_URL = "https://api.sea-lion.ai/v1"
DEFAULT_KEY_ENV = "SEALION_API_KEY"


class ConfigError(ValueError):
    """Raised when a config file is missing required fields or has an invalid shape."""


@dataclass(frozen=True)
class ApiConfig:
    base_url: str = DEFAULT_BASE_URL
    key_env: str = DEFAULT_KEY_ENV
    retry_max_attempts: int = 3
    # When True, HTTP requests without a Bearer key fall back to the server's env API key.
    # When False (default), requests without a Bearer key are rejected.
    allow_env_key_fallback: bool = False


@dataclass(frozen=True)
class Profile:
    name: str
    model: str
    temperature: float = 0.3
    max_tokens: int = 1024
    thinking_mode: str | None = None  # "on" or "off" for reasoning models
    extra: dict[str, Any] = field(default_factory=dict)

    def extra_body(self) -> dict[str, Any]:
        """Return non-OpenAI-standard fields to pass via extra_body."""
        body: dict[str, Any] = {}
        if self.thinking_mode is not None:
            body["chat_template_kwargs"] = {"thinking_mode": self.thinking_mode}
        if self.extra:
            body.update(self.extra)
        return body


@dataclass(frozen=True)
class Config:
    api: ApiConfig
    profiles: dict[str, Profile]
    routing: dict[str, str]
    default_profile: str

    def profile_for(self, task: str) -> Profile:
        profile_name = self.routing.get(task, self.default_profile)
        if profile_name not in self.profiles:
            raise ConfigError(
                f"Routing for task '{task}' points to profile '{profile_name}' which is not defined"
            )
        return self.profiles[profile_name]

    def api_key(self) -> str:
        key = os.environ.get(self.api.key_env)
        if not key:
            raise ConfigError(
                f"API key not found in env var {self.api.key_env}. "
                f"Generate one at the SEA-LION Playground and export it."
            )
        return key


def load_config(path: str | Path | None = None) -> Config:
    """Load config from disk. Path resolution: arg > SEALION_CONFIG env > default."""
    resolved = Path(path) if path else Path(os.environ.get("SEALION_CONFIG", DEFAULT_CONFIG_PATH))
    if not resolved.exists():
        raise ConfigError(
            f"Config file not found at {resolved}. "
            f"Copy config.example.yaml to ~/.sealion/config.yaml to get started."
        )
    raw = yaml.safe_load(resolved.read_text()) or {}
    return _parse(raw)


def _parse(raw: dict[str, Any]) -> Config:
    api_raw = raw.get("api", {})
    _env_fallback_override = os.environ.get("SEALION_ALLOW_ENV_KEY_FALLBACK", "").lower()
    allow_env_key_fallback = (
        _env_fallback_override in ("1", "true", "yes")
        if _env_fallback_override
        else bool(api_raw.get("allow_env_key_fallback", False))
    )
    api = ApiConfig(
        base_url=api_raw.get("base_url", DEFAULT_BASE_URL),
        key_env=api_raw.get("key_env", DEFAULT_KEY_ENV),
        retry_max_attempts=int(api_raw.get("retry_max_attempts", 3)),
        allow_env_key_fallback=allow_env_key_fallback,
    )

    profiles_raw = raw.get("profiles") or {}
    if not profiles_raw:
        raise ConfigError("Config must define at least one entry under `profiles:`.")
    profiles: dict[str, Profile] = {}
    for name, body in profiles_raw.items():
        if "model" not in body:
            raise ConfigError(f"Profile '{name}' is missing required field `model`.")
        known = {"model", "temperature", "max_tokens", "thinking_mode"}
        extra = {k: v for k, v in body.items() if k not in known}
        profiles[name] = Profile(
            name=name,
            model=body["model"],
            temperature=float(body.get("temperature", 0.3)),
            max_tokens=int(body.get("max_tokens", 1024)),
            thinking_mode=body.get("thinking_mode"),
            extra=extra,
        )

    routing = raw.get("routing") or {}
    default_profile = routing.get("default") or next(iter(profiles))
    if default_profile not in profiles:
        raise ConfigError(
            f"`routing.default` points to profile '{default_profile}' which is not defined."
        )
    task_routing = {k: v for k, v in routing.items() if k != "default"}
    for task, prof in task_routing.items():
        if prof not in profiles:
            raise ConfigError(f"Task '{task}' routes to profile '{prof}' which is not defined.")

    return Config(
        api=api,
        profiles=profiles,
        routing=task_routing,
        default_profile=default_profile,
    )
