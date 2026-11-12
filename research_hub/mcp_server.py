"""MCP (Model Context Protocol) server for Research Hub, over stdio.

Lets an AI agent (Claude Code, Codex, Cursor, …) read the research state and
*propose* updates. Proposals land in the dashboard inbox and change nothing until
the user approves them — that is the confirmation gate for agent work.

Register with Claude Code, for example::

    claude mcp add research-hub -- python -m research_hub mcp \
        --url http://127.0.0.1:8770 --token <agent token from Settings>

Standard library only. Messages are newline-delimited JSON-RPC 2.0.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

from . import __version__

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

OP_SCHEMA = {
    "type": "object",
    "description": (
        "One change. create: {op:'create', entity, data, ref?}; update: {op:'update', entity, id | match:{key:value}, data, append?:{textField: text}}; "
        "delete: {op:'delete', entity, id}; link/unlink: {op:'link', link:'rq_variable'|'rq_paper'|'variable_paper', a, b, data?}. "
        "Entities: stage, task, rq, variable, relation (hypothesised path: source_id, target_id, kind effect|moderates, moderates_id, sign +|-, label e.g. H1), paper, resource. Use \"$ref\" to point at an object created earlier in the same batch. "
        "Call get_schema for field names and allowed values."
    ),
}

TOOLS = [
    {"name": "get_overview", "description": "Pipeline stages with status/progress, open tasks, counts of RQs, variables and papers, and pending proposals.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_schema", "description": "Fields, enum values and required fields for every entity agents can propose changes to.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_items", "description": "List items of one kind, optionally filtered by a case-insensitive text query.",
     "inputSchema": {"type": "object", "properties": {
         "kind": {"type": "string", "enum": ["stages", "tasks", "rqs", "variables", "relations", "papers", "resources", "files", "variable_papers", "rq_variables", "rq_papers"]},
         "query": {"type": "string"}, "limit": {"type": "integer", "default": 50}}, "required": ["kind"]}},
    {"name": "propose_changes", "description": "Submit a batch of changes for the user to review. Nothing is applied until the user approves it in the dashboard.",
     "inputSchema": {"type": "object", "properties": {
         "title": {"type": "string", "description": "Short headline shown in the inbox"},
         "summary": {"type": "string", "description": "What you did and why; include evidence/sources"},
         "ops": {"type": "array", "items": OP_SCHEMA}}, "required": ["title", "ops"]}},
    {"name": "report_stage_progress", "description": "Propose a status/progress update for one pipeline stage (by key, e.g. 'literature'), optionally ticking tasks done by id and appending a note.",
     "inputSchema": {"type": "object", "properties": {
         "stage_key": {"type": "string"}, "status": {"type": "string", "enum": ["todo", "active", "review", "done", "blocked"]},
         "progress": {"type": "integer", "minimum": 0, "maximum": 100}, "done_task_ids": {"type": "array", "items": {"type": "integer"}},
         "note": {"type": "string"}, "summary": {"type": "string"}}, "required": ["stage_key"]}},
    {"name": "propose_papers", "description": "Propose adding papers (e.g. from a literature-search MCP tool). Optionally link each to variables by id or RQs by id.",
     "inputSchema": {"type": "object", "properties": {
         "papers": {"type": "array", "items": {"type": "object", "properties": {
             "title": {"type": "string"}, "authors": {"type": "string"}, "year": {"type": "integer"}, "venue": {"type": "string"},
             "doi": {"type": "string"}, "url": {"type": "string"}, "abstract": {"type": "string"}, "notes": {"type": "string"},
             "variable_ids": {"type": "array", "items": {"type": "integer"}}, "rq_ids": {"type": "array", "items": {"type": "integer"}}},
             "required": ["title"]}},
         "summary": {"type": "string"}}, "required": ["papers"]}},
    {"name": "check_proposals", "description": "Status (pending/approved/rejected) of recent proposals, so you know what the user accepted.",
     "inputSchema": {"type": "object", "properties": {"status": {"type": "string", "enum": ["all", "pending", "approved", "rejected"], "default": "all"}}}},
]


class Hub:
    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.token = token

    def _req(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read().decode("utf-8")).get("error")
            except Exception:
                msg = str(e)
            raise RuntimeError(msg) from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"Research Hub is not reachable at {self.url} ({e.reason}). Start it with ./start.sh") from None

    def state(self):
        return self._req("GET", "/api/agent/state")

    def propose(self, title, ops, summary="", source="agent (MCP)"):
        return self._req("POST", "/api/agent/proposals", {"title": title, "ops": ops, "summary": summary, "source": source})

    def proposals(self, status="all"):
        return self._req("GET", f"/api/agent/proposals?status={status}")


def call_tool(hub: Hub, name: str, args: dict):
    if name == "get_overview":
        s = hub.state()
        open_tasks = {}
        done_stages = {st["id"] for st in s["stages"] if st["status"] == "done"}
        for t in s["tasks"]:
            if not t["done"] and t["stage_id"] not in done_stages:
                open_tasks.setdefault(t["stage_id"], []).append({"id": t["id"], "title": t["title"]})
        return {
            "overall_progress": s["overall"],
            "stages": [{"id": st["id"], "key": st["key"], "title": f"{st['title_zh']} / {st['title_en']}", "status": st["status"],
                        "progress": st["progress"], "due": st["due_date"], "open_tasks": open_tasks.get(st["id"], [])} for st in s["stages"]],
            "counts": {k: len(s[k]) for k in ("rqs", "variables", "papers", "resources", "files")},
            "pending_proposals": s["pending"],
        }
    if name == "get_schema":
        return hub.state()["schema"]
    if name == "list_items":
        kind = args.get("kind")
        s = hub.state()
        if kind not in s or not isinstance(s[kind], list):
            raise ValueError(f"unknown kind {kind}")
        items = s[kind]
        query = str(args.get("query") or "").casefold()
        if query:
            items = [i for i in items if query in json.dumps(i, ensure_ascii=False).casefold()]
        return items[: max(1, min(int(args.get("limit") or 50), 500))]
    if name == "propose_changes":
        return hub.propose(args.get("title"), args.get("ops"), args.get("summary", ""))
    if name == "report_stage_progress":
        data = {k: args[k] for k in ("status", "progress") if k in args}
        ops = []
        update = {"op": "update", "entity": "stage", "match": {"key": args["stage_key"]}, "data": data}
        if args.get("note"):
            update["append"] = {"notes": str(args["note"])}  # appended at approval time, never overwrites
        if data or args.get("note"):
            ops.append(update)
        for tid in args.get("done_task_ids") or []:
            ops.append({"op": "update", "entity": "task", "id": int(tid), "data": {"done": True}})
        if not ops:
            raise ValueError("nothing to report: give status, progress, note or done_task_ids")
        s = hub.state()
        stage = next((st for st in s["stages"] if st["key"] == args["stage_key"]), None)
        if not stage:
            raise ValueError(f"no stage with key {args['stage_key']!r}")
        if s.get("language") == "en":
            title = f"Stage “{stage['title_en'] or stage['title_zh']}” update" + (f" → {args['status']}" if args.get("status") else "")
        else:
            labels = {"todo": "未開始", "active": "進行中", "review": "審閱中", "done": "已完成", "blocked": "受阻"}
            title = f"階段「{stage['title_zh']}」更新" + (f" → {labels.get(args['status'], args['status'])}" if args.get("status") else "")
        if "progress" in args:
            title += f"（{args['progress']}%）" if s.get("language") != "en" else f" ({args['progress']}%)"
        return hub.propose(title, ops, args.get("summary", ""))
    if name == "propose_papers":
        ops = []
        for i, p in enumerate(args.get("papers") or []):
            data = {k: p[k] for k in ("title", "authors", "year", "venue", "doi", "url", "abstract", "notes") if p.get(k)}
            data.update({"source": "mcp", "status": "candidate"})
            ops.append({"op": "create", "entity": "paper", "ref": f"p{i}", "data": data})
            for vid in p.get("variable_ids") or []:
                ops.append({"op": "link", "link": "variable_paper", "a": int(vid), "b": f"$p{i}", "data": {"evidence": "mentions"}})
            for rid in p.get("rq_ids") or []:
                ops.append({"op": "link", "link": "rq_paper", "a": int(rid), "b": f"$p{i}"})
        if not ops:
            raise ValueError("no papers given")
        n = len(args["papers"])
        title = f"{n} paper(s) suggested" if hub.state().get("language") == "en" else f"建議加入 {n} 篇文獻"
        return hub.propose(title, ops, args.get("summary", ""))
    if name == "check_proposals":
        items = hub.proposals(args.get("status") or "all")["items"]
        return [{"id": p["id"], "title": p["title"], "status": p["status"], "created": p["created"], "decided": p["decided"]} for p in items]
    raise ValueError(f"unknown tool {name}")


def handle(hub: Hub, msg: dict) -> dict | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:  # notification
        return None

    def ok(result):
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    if method == "initialize":
        asked = (msg.get("params") or {}).get("protocolVersion")
        return ok({"protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                   "capabilities": {"tools": {}}, "serverInfo": {"name": "research-hub", "version": __version__},
                   "instructions": "Read the research state, then propose changes. Every change waits for the user's approval in the Research Hub inbox."})
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        try:
            result = call_tool(hub, params.get("name"), params.get("arguments") or {})
            return ok({"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=1)}]})
        except Exception as e:
            return ok({"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True})
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}


def main(url: str, token: str) -> None:
    hub = Hub(url, token)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            out = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            out = handle(hub, msg) if isinstance(msg, dict) else None
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()
