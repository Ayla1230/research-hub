"""Command line: ``python -m research_hub [serve|mcp|propose] ...``"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__

DEFAULT_DATA = os.environ.get("RESEARCH_HUB_HOME") or str(Path.home() / "ResearchHub")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="research_hub", description="Research Hub — research progress dashboard")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd")

    serve = sub.add_parser("serve", help="start the dashboard (default)")
    serve.add_argument("--data", default=DEFAULT_DATA, help=f"workspace folder (default {DEFAULT_DATA})")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=int(os.environ.get("RESEARCH_HUB_PORT") or 8770))
    serve.add_argument("--lang", choices=["zh", "en"], default="zh", help="language used when creating a new workspace")
    serve.add_argument("--no-browser", action="store_true")
    serve.add_argument("--demo", action="store_true", help="fill an empty workspace with sample RQs, variables and papers")
    serve.add_argument("--no-watch", action="store_true", help="do not watch reference folders for new files")

    mcp = sub.add_parser("mcp", help="run the MCP server over stdio (for AI agents)")
    mcp.add_argument("--url", default=os.environ.get("RESEARCH_HUB_URL", "http://127.0.0.1:8770"))
    mcp.add_argument("--token", default=os.environ.get("RESEARCH_HUB_TOKEN", ""))

    prop = sub.add_parser("propose", help="send a proposal (JSON file with title/summary/ops) to a running hub")
    prop.add_argument("file", help="JSON file, or - for stdin")
    prop.add_argument("--url", default=os.environ.get("RESEARCH_HUB_URL", "http://127.0.0.1:8770"))
    prop.add_argument("--token", default=os.environ.get("RESEARCH_HUB_TOKEN", ""))
    prop.add_argument("--source", default="cli")

    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in ("serve", "mcp", "propose", "-h", "--help", "--version"):
        argv.insert(0, "serve")
    args = parser.parse_args(argv)
    if args.cmd == "serve":
        from .server import serve as run
        from .store import Store
        if args.host not in ("127.0.0.1", "localhost", "::1"):
            print("WARNING: Research Hub has no login. Only bind to a non-loopback address behind an authenticating proxy.",
                  file=sys.stderr)
        store = Store(Path(args.data), lang=args.lang)
        if args.demo:
            from .demo import apply as demo
            print("Demo data added." if demo(store) else "Workspace is not empty; demo data skipped.")
        run(store, args.host, args.port, open_browser=not args.no_browser, watch=not args.no_watch)
        return 0
    if args.cmd == "mcp":
        if not args.token:
            print("missing --token (copy the agent token from Settings → Agents & MCP)", file=sys.stderr)
            return 2
        from .mcp_server import main as mcp_main
        mcp_main(args.url, args.token)
        return 0
    if args.cmd == "propose":
        from .mcp_server import Hub
        raw = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
        data = json.loads(raw)
        try:
            out = Hub(args.url, args.token).propose(data.get("title"), data.get("ops"), data.get("summary", ""), args.source)
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(json.dumps(out))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
