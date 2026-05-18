"""AI Singapore hosted API client.

Wraps the OpenAI async SDK against https://api.sea-lion.ai/v1. The SDK retries on
429 and 5xx with exponential backoff (honoring Retry-After); rate limiting is
enforced server-side per API key.
"""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from sealion_sidecar.config import ApiConfig


class AISGBackend:
    def __init__(self, api: ApiConfig, api_key: str) -> None:
        self._client = AsyncOpenAI(
            base_url=api.base_url,
            api_key=api_key,
            max_retries=api.retry_max_attempts,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        extra_body: dict[str, Any] | None = None,
    ) -> str:
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            extra_body=extra_body or None,
        )
        content = response.choices[0].message.content
        return content or ""

    async def list_models(self) -> list[str]:
        page = await self._client.models.list()
        return sorted(m.id for m in page.data)

    async def aclose(self) -> None:
        await self._client.close()
