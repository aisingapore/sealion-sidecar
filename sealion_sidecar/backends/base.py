"""Backend protocol. v0.1 has a single concrete impl in backends/aisg.py."""

from __future__ import annotations

from typing import Any, Protocol


class Backend(Protocol):
    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        extra_body: dict[str, Any] | None = None,
    ) -> str:
        """Run a single non-streaming chat completion and return the text content."""
        ...

    async def list_models(self) -> list[str]:
        """Return the set of model IDs the API key can reach."""
        ...
