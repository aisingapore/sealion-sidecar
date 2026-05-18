"""Shared eval harness — runs SEA-LION through the task modules, optionally
compares against a Claude baseline if `anthropic` is installed and ANTHROPIC_API_KEY
is set.

The evals call the same code path the MCP server uses (load_config + AISGBackend
+ task.run) so they validate the deployed surface, not a separate test rig.

Run:
    uv run python -m sealion_sidecar.evals.<tool>
    uv run python -m sealion_sidecar.evals.<tool> --baseline claude
    uv run python -m sealion_sidecar.evals.<tool> --no-sealion --baseline claude
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sealion_sidecar.backends.aisg import AISGBackend
from sealion_sidecar.config import Config, ConfigError, load_config

CLAUDE_MODEL = "claude-haiku-4-5-20251001"


@dataclass
class Example:
    name: str
    args: dict[str, Any]
    expected: dict[str, Any] | None = None
    # claude_prompt: a single user-message string the baseline sees. If None,
    # Claude baseline is skipped for this example.
    claude_prompt: str | None = None


@dataclass
class Outcome:
    example: Example
    sealion_result: dict[str, Any] | str | None
    sealion_error: str | None
    claude_result: str | None
    claude_error: str | None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--config", help="Override SEALION_CONFIG / default config path.")
    p.add_argument("--baseline", choices=["claude"], help="Run a parallel baseline.")
    p.add_argument("--no-sealion", action="store_true", help="Skip the SEA-LION run.")
    return p.parse_args()


async def run_eval(
    tool_name: str,
    examples: list[Example],
    sealion_caller: Callable[[Example, AISGBackend, Config], Awaitable[Any]],
    score: Callable[[Example, Any], str] | None = None,
) -> int:
    args = parse_args()

    config: Config | None = None
    backend: AISGBackend | None = None
    if not args.no_sealion:
        try:
            config = load_config(args.config)
            backend = AISGBackend(config.api, config.api_key())
        except ConfigError as e:
            print(f"config error: {e}")
            return 1

    claude_client = _build_claude_client() if args.baseline == "claude" else None

    print(f"\n=== {tool_name} ===\n")
    outcomes: list[Outcome] = []
    try:
        for ex in examples:
            sealion_result: Any = None
            sealion_error: str | None = None
            if backend is not None and config is not None:
                try:
                    sealion_result = await sealion_caller(ex, backend, config)
                except Exception as e:
                    sealion_error = f"{type(e).__name__}: {e}"

            claude_result: str | None = None
            claude_error: str | None = None
            if claude_client is not None and ex.claude_prompt:
                try:
                    claude_result = await _call_claude(claude_client, ex.claude_prompt)
                except Exception as e:
                    claude_error = f"{type(e).__name__}: {e}"

            outcomes.append(Outcome(ex, sealion_result, sealion_error, claude_result, claude_error))
            _print_outcome(outcomes[-1], score)
    finally:
        if backend is not None:
            await backend.aclose()

    if score is not None:
        correct = sum(
            1
            for o in outcomes
            if o.sealion_result is not None and score(o.example, o.sealion_result) == "PASS"
        )
        total = sum(1 for o in outcomes if o.example.expected is not None)
        if total:
            print(f"\nSEA-LION accuracy: {correct}/{total} ({correct / total:.0%})")

    return 0


def _build_claude_client() -> Any | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("(skipping Claude baseline: ANTHROPIC_API_KEY not set)\n")
        return None
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        print("(skipping Claude baseline: `pip install anthropic` or `uv sync --extra evals`)\n")
        return None
    return AsyncAnthropic(api_key=api_key)


async def _call_claude(client: Any, prompt: str) -> str:
    msg = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text if msg.content else ""


def _print_outcome(o: Outcome, score: Callable[[Example, Any], str] | None) -> None:
    print(f"--- {o.example.name}")
    print(f"input: {_compact(o.example.args)}")
    if o.example.expected is not None:
        print(f"expected: {_compact(o.example.expected)}")
    if o.sealion_error:
        print(f"SEA-LION: ERROR {o.sealion_error}")
    elif o.sealion_result is not None:
        verdict = ""
        if score is not None and o.example.expected is not None:
            verdict = f"  [{score(o.example, o.sealion_result)}]"
        print(f"SEA-LION: {_compact(o.sealion_result)}{verdict}")
    if o.claude_error:
        print(f"Claude:   ERROR {o.claude_error}")
    elif o.claude_result is not None:
        print(f"Claude:   {o.claude_result[:200]}")
    print()


def _compact(obj: Any) -> str:
    if isinstance(obj, str):
        return obj if len(obj) <= 200 else obj[:200] + "..."
    return json.dumps(obj, ensure_ascii=False)


def run(main_coro: Callable[[], Awaitable[int]]) -> None:
    """Entry-point wrapper so each eval module ends in `_runner.run(main)`."""
    raise SystemExit(asyncio.run(main_coro()))
