"""MCP server — four SEA-LION tools over stdio or HTTP.

HTTP mode: each client passes their own AISG key as 'Authorization: Bearer <key>'.
stdio mode: key is read from the SEALION_API_KEY env var at startup.
"""

from __future__ import annotations

import contextvars
import os
import sys
from pathlib import Path
from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field
from starlette.middleware import Middleware
from starlette.types import ASGIApp, Receive, Scope, Send

from sealion_sidecar import __version__
from sealion_sidecar.backends.aisg import AISGBackend
from sealion_sidecar.config import ConfigError, load_config
from sealion_sidecar.tasks import (
    detect_language_variant as _dlv,
)
from sealion_sidecar.tasks import (
    safety_check as _sc,
)
from sealion_sidecar.tasks import (
    translate_localize as _tl,
)
from sealion_sidecar.tasks._common import TaskError

# Per-request API key. Set by ASGI middleware for HTTP; set at startup for stdio.
_api_key: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "sealion_api_key", default=None
)

# One backend per unique API key — reused across requests for that key.
_backends: dict[str, AISGBackend] = {}


def _get_backend(api_key: str, api_config) -> AISGBackend:
    if api_key not in _backends:
        _backends[api_key] = AISGBackend(api_config, api_key)
    return _backends[api_key]


def _require_key() -> str:
    key = _api_key.get()
    if not key:
        raise TaskError("No API key — pass your AISG key as 'Authorization: Bearer <key>'.")
    return key


def _extract_bearer(auth: str) -> str | None:
    if auth.lower().startswith("bearer "):
        value = auth[7:].strip()
        return value or None
    return None


class _ApiKeyMiddleware:
    """ASGI middleware that reads the API key from Authorization: Bearer into a ContextVar.

    When config.api.allow_env_key_fallback is True, requests without a Bearer key fall
    back to the server's env API key instead of being rejected.
    """

    def __init__(self, app: ASGIApp, config) -> None:
        self.app = app
        self.config = config

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            headers = {k.lower(): v for k, v in scope.get("headers", [])}
            auth = headers.get(b"authorization", b"").decode("utf-8", errors="ignore")
            key = _extract_bearer(auth)
            if not key and self.config.api.allow_env_key_fallback:
                key = os.environ.get(self.config.api.key_env) or None
            token = _api_key.set(key or None)
            try:
                await self.app(scope, receive, send)
            finally:
                _api_key.reset(token)
        else:
            await self.app(scope, receive, send)


def build_mcp(config) -> FastMCP:
    mcp = FastMCP("sealion-sidecar", version=__version__)

    @mcp.tool(description=_dlv.DESCRIPTION)
    async def detect_language_variant(
        text: Annotated[str, Field(description="The text to classify. May be in any language.")],
    ) -> dict:
        return await _dlv.run(
            {"text": text},
            _get_backend(_require_key(), config.api),
            config.profile_for(_dlv.NAME),
        )

    @mcp.tool(description=_tl.DESCRIPTION)
    async def translate_localize(
        text: Annotated[str, Field(description="The source text to translate.")],
        target_language: Annotated[
            str,
            Field(
                description=(
                    "BCP-47 language code for the output language. "
                    "Examples: 'id' (Indonesian), 'ms' (Malay), 'th' (Thai), "
                    "'vi' (Vietnamese), 'fil' (Filipino), 'my' (Burmese), 'ta' (Tamil)."
                )
            ),
        ],
        source_language: Annotated[
            str | None,
            Field(
                description=(
                    "BCP-47 code of the input language, or 'auto' to detect automatically. "
                    "Default: 'auto'."
                )
            ),
        ] = None,
        target_region: Annotated[
            str | None,
            Field(
                description=(
                    "Country or city to localize for, e.g. 'Singapore', 'Kuala Lumpur', "
                    "'Jakarta', 'Manila'. Influences idiom and register choices."
                )
            ),
        ] = None,
        tone: Annotated[
            str | None,
            Field(
                description=(
                    "Desired tone of the translation. One of: 'neutral', 'formal', 'informal',"
                    " 'public_service', 'marketing', 'legal', 'friendly', 'urgent'."
                    " Default: 'neutral'."
                )
            ),
        ] = None,
        reading_level: Annotated[
            str | None,
            Field(
                description=(
                    "Target reading complexity. "
                    "One of: 'plain', 'standard', 'advanced'. Default: 'standard'."
                )
            ),
        ] = None,
    ) -> dict:
        args: dict = {"text": text, "target_language": target_language}
        if source_language is not None:
            args["source_language"] = source_language
        if target_region is not None:
            args["target_region"] = target_region
        if tone is not None:
            args["tone"] = tone
        if reading_level is not None:
            args["reading_level"] = reading_level
        return await _tl.run(
            args, _get_backend(_require_key(), config.api), config.profile_for(_tl.NAME)
        )

    @mcp.tool(description=_sc.DESCRIPTION)
    async def safety_check(
        mode: Annotated[
            str,
            Field(
                description=(
                    "What to classify. "
                    "'prompt_only': check a user request for harmful intent (requires prompt). "
                    "'response_only': check an AI response before sending (requires response). "
                    "'prompt_response': evaluate the full turn together (requires both)."
                )
            ),
        ],
        prompt: Annotated[
            str | None,
            Field(
                description=(
                    "The user's message. Required for 'prompt_only' and 'prompt_response' modes."
                )
            ),
        ] = None,
        response: Annotated[
            str | None,
            Field(
                description=(
                    "The AI's response. Required for 'response_only' and 'prompt_response' modes."
                )
            ),
        ] = None,
    ) -> dict:
        args: dict = {"mode": mode}
        if prompt is not None:
            args["prompt"] = prompt
        if response is not None:
            args["response"] = response
        return await _sc.run(
            args, _get_backend(_require_key(), config.api), config.profile_for(_sc.NAME)
        )

    return mcp


def serve_stdio(config_path: str | Path | None = None) -> int:
    try:
        config = load_config(config_path)
        api_key = config.api_key()
    except ConfigError as e:
        print(f"sealion mcp: {e}", file=sys.stderr)
        return 1
    _api_key.set(api_key)
    mcp = build_mcp(config)
    mcp.run(transport="stdio")
    return 0


def serve_http(
    host: str,
    port: int,
    transport: str,
    config_path: str | Path | None = None,
) -> int:
    try:
        config = load_config(config_path)
    except ConfigError as e:
        print(f"sealion mcp: {e}", file=sys.stderr)
        return 1

    mcp = build_mcp(config)
    mcp.run(
        transport=transport,
        host=host,
        port=port,
        middleware=[Middleware(_ApiKeyMiddleware, config=config)],
    )
    return 0
