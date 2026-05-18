"""`sealion doctor` — verify config and AISG API reachability."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from sealion_sidecar.backends.aisg import AISGBackend
from sealion_sidecar.config import (
    DEFAULT_CONFIG_PATH,
    ConfigError,
    load_config,
)


def run(config_path: str | Path | None = None) -> int:
    """Run the doctor checks. Returns the exit code."""
    problems = 0
    print("SEA-LION Sidecar — sealion doctor\n")

    resolved_path = (
        Path(config_path)
        if config_path
        else Path(os.environ.get("SEALION_CONFIG", DEFAULT_CONFIG_PATH))
    )
    try:
        config = load_config(config_path)
    except ConfigError as e:
        _print_row("config", str(resolved_path), f"FAIL — {e}")
        return 1
    _print_row("config", str(resolved_path), "OK")

    try:
        api_key = config.api_key()
    except ConfigError as e:
        _print_row("api key", config.api.key_env, f"FAIL — {e}")
        return 1
    _print_row("api key", config.api.key_env, "OK")

    try:
        available = asyncio.run(_fetch_models(config, api_key))
    except Exception as e:  # surface network/auth errors verbatim
        _print_row("api", config.api.base_url, f"FAIL — {type(e).__name__}: {e}")
        return 1
    _print_row("api", config.api.base_url, f"OK ({len(available)} models available)")

    print("\nprofiles")
    available_set = set(available)
    for name, profile in config.profiles.items():
        status = "OK" if profile.model in available_set else "MISSING (not in /v1/models)"
        if "MISSING" in status:
            problems += 1
        print(f"  {name:<16} {profile.model:<46} {status}")

    print()
    if problems:
        print(f"{problems} problem{'s' if problems != 1 else ''} found.")
        return 1
    print("All checks passed.")
    return 0


async def _fetch_models(config, api_key: str) -> list[str]:
    backend = AISGBackend(config.api, api_key)
    try:
        return await backend.list_models()
    finally:
        await backend.aclose()


def _print_row(label: str, value: str, status: str) -> None:
    print(f"{label:<12} {value:<46} {status}", file=sys.stdout)
