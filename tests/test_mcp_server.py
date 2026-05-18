"""Wiring tests for the MCP server. The tools themselves are exercised in test_tasks.py."""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from sealion_sidecar.config import load_config
from sealion_sidecar.mcp_server import build_mcp
from sealion_sidecar.tasks import (
    detect_language_variant,
    safety_check,
    translate_localize,
)

EXAMPLE_PATH = Path(__file__).parent.parent / "config.example.yaml"
TASK_MODULES = [detect_language_variant, translate_localize, safety_check]


def test_task_modules_have_required_attributes() -> None:
    for task in TASK_MODULES:
        assert isinstance(task.NAME, str) and task.NAME
        assert isinstance(task.DESCRIPTION, str) and task.DESCRIPTION
        schema = task.input_schema()
        assert schema["type"] == "object"
        assert callable(task.run)


def test_build_mcp_returns_fastmcp_instance() -> None:
    config = load_config(EXAMPLE_PATH)
    mcp = build_mcp(config)
    assert isinstance(mcp, FastMCP)


def test_routing_covers_every_tool() -> None:
    config = load_config(EXAMPLE_PATH)
    for task in TASK_MODULES:
        profile = config.profile_for(task.NAME)
        assert profile.model
