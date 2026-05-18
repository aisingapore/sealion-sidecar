# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this product is

SEA-LION packaged as a **specialist sidecar for agents**, not a replacement for the main model. Host agents (Claude Desktop, Cursor, Hermes, LangGraph, Pipecat) keep their general reasoner and call SEA-LION when Southeast Asian language, culture, safety, or localization is the bottleneck.

The MCP tools are the product. The chat endpoint is a fallback — task tools (`translate_localize`, `safety_check`, `detect_language_variant`) are what makes this worth installing.

## v0.1 scope — committed

**Backend:** one HTTP client (`aisg_hosted`) wrapping AI Singapore's hosted endpoints for SEA-LION instruct models, SEA-Guard, and SEA-Embedding. No local inference in v0.1 — Ollama/vLLM/MLX deferred to v0.2.

**Interface:** MCP server only (`sealion mcp`). OpenAI-compat HTTP server deferred to v0.1.1.

**Tools (3):** all return validated JSON against their schemas.

| Tool | Role | Notes |
|------|------|-------|
| `detect_language_variant` | Routing primitive | First call the host agent makes. Returns language, variant (e.g. `singapore_colloquial_english`), code-switching flag, register. |
| `translate_localize` | The wedge | Translation + localization notes + tone control. The notes are the differentiator vs. a Claude prompt. |
| `safety_check` | SEA-Guard wrapper | Ship with **advisory, not decisional** framing in docs and response. Needs calibration baseline before launch. |

**Deferred to v0.2:** `voice_respond`, `cultural_review`, `extract_structured`, `rag_query`, OpenAI-compat HTTP, Docker Compose, web demo, local inference backends.

## Architectural shape (v0.1)

```
Host agent (Claude Desktop / Cursor / Hermes / Pipecat)
        |
        | MCP (stdio)
        v
sealion_sidecar
  ├── mcp_server.py     ── tool registration + dispatch
  ├── router            ── task → profile → model id
  ├── tasks/            ── one module per tool (prompts + call + schema validation)
  ├── schemas/          ── JSON schemas, validated before return
  ├── prompts/          ── per-task templates, versioned
  └── backends/aisg.py  ── single HTTP client to hosted AISG APIs
```

Key invariants:

- **Profiles, not raw model names.** Tasks reference profiles (`standard`, `best-language`, `safety`, `reasoning`); profiles map to specific model IDs in `~/.sealion/config.yaml`. Lets us re-route as the AISG catalogue evolves without touching task code.
- **Pin model versions in config.** Profile names are routing labels; actual model + version belongs in config so deployments are reproducible.
- **Schema validation is non-negotiable.** Every tool validates against its JSON schema before the response leaves the sidecar. If validation fails, retry once then return a structured error — never return invalid JSON to the agent.
- **No prompt logging by default.** Logging is opt-in via config; PII/secrets redacted when enabled.

## Reference layout

```
sealion_sidecar/
  __init__.py
  cli.py            # `sealion mcp`, `sealion doctor`
  config.py         # ~/.sealion/config.yaml loader, env overrides
  mcp_server.py     # MCP entry point
  router.py         # task → profile → model
  backends/
    base.py
    aisg.py         # hosted AISG client (v0.1)
  tasks/
    detect_language_variant.py
    translate_localize.py
    safety_check.py
  schemas/
    *.json          # one per task, validated on return
  prompts/
    *.md            # one per task
  evals/
    *.py            # one per task, Claude baseline
```

`tasks/`, `schemas/`, `prompts/` are parallel — adding a tool means a file in each plus an eval.

## Conventions

- **Python**, `uv`-based. `pyproject.toml` declares `sealion` console script → `sealion_sidecar.cli:main`.
- **CLI (v0.1):** `sealion mcp` (start MCP server), `sealion doctor` (health check against AISG endpoints).
- **Config:** `~/.sealion/config.yaml`. Env overrides use `SEALION_*` prefix (`SEALION_CONFIG`, `SEALION_API_KEY`, `SEALION_PROFILE`). API key never logged.
- **MCP transport:** stdio (default for Claude Desktop / Cursor).
- **Schema validation:** `jsonschema` library. Schemas live in `sealion_sidecar/schemas/` as `.json`, loaded at startup.
- **HTTP client:** `httpx` async. Per-tool timeout configured in each task module.

## Routing policy (encoded in docs + the `detect_language_variant` tool)

**Call SEA-LION when:** SEA language / code-switching / regional slang / translation or localization for SEA audience / regional safety moderation.

**Don't call SEA-LION for:** general world knowledge / long strategic reasoning without a SEA dimension / final high-stakes advice without verification / unsupported languages.

The host agent runs `detect_language_variant` first and routes from there. This is the integration pattern — preserve it in every example.

## Evals (ship with v0.1)

One per tool, runnable locally:

- **Localization** — paired English / SEA-language messages, scored on clarity, tone, regional fit. Baseline: Claude with a translation prompt.
- **Safety** — SEA-language and code-switched content, scored on category accuracy + severity calibration. Baseline: generic English moderation.
- **Variant detection** — labeled corpus across 5+ SEA languages and Singlish/Manglish variants. Baseline: Claude classification prompt.

Each eval prints a single comparison table. No fancy harness yet — that's v0.2.

## Build / lint / test

Once `pyproject.toml` is in place, expect:

```bash
uv sync
uv run sealion doctor
uv run sealion mcp
uv run pytest
uv run ruff check
```

Update this section as commands solidify.
