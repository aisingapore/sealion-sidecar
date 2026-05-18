"""Command-line entry point for the SEA-LION Sidecar."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sealion",
        description="SEA-LION Sidecar — MCP server for Southeast Asian language tools.",
    )
    parser.add_argument(
        "--config",
        help="Path to config.yaml (overrides SEALION_CONFIG env and the default).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    mcp_parser = subparsers.add_parser("mcp", help="Run the MCP server.")
    mcp_parser.add_argument(
        "--transport",
        choices=["streamable-http", "sse", "stdio"],
        default="streamable-http",
        help=(
            "Transport to use. "
            "'streamable-http' (default): HTTP server for network deployments. "
            "'sse': HTTP server using the older Server-Sent Events protocol. "
            "'stdio': subprocess mode for local clients like Claude Desktop."
        ),
    )
    mcp_parser.add_argument("--host", default="0.0.0.0", help="Host to bind (HTTP only).")
    mcp_parser.add_argument("--port", type=int, default=8000, help="Port to bind (HTTP only).")

    subparsers.add_parser("doctor", help="Check config and AISG API reachability.")

    args = parser.parse_args(argv)

    if args.command == "mcp":
        from sealion_sidecar.mcp_server import serve_http, serve_stdio

        if args.transport == "stdio":
            return serve_stdio(args.config)
        return serve_http(args.host, args.port, args.transport, args.config)

    if args.command == "doctor":
        from sealion_sidecar.doctor import run as doctor_run

        return doctor_run(args.config)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
