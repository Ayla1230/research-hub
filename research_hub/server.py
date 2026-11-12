"""Local HTTP server: dashboard, JSON API, Server-Sent Events, agent inbox.

Security model:
* listens on 127.0.0.1 by default and rejects unknown Host headers (DNS rebinding);
* every state-changing request from the dashboard carries the per-process token
  that is embedded in the page, so other web pages cannot write;
* agents authenticate with a separate, rotatable agent token and can only *propose*
  changes — nothing they send is applied until the user approves it;
* local files are served only from configured folders and the uploads folder.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import queue
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from . import __version__, exam, integrations as integ, thesis, topic as topic_mod, voice
from .store import ENTITIES, QuotaError, Store, ValidationError

WEB = Path(__file__).with_name("web")
MAX_UPLOAD = 300 * 1024 * 1024
MAX_JSON = 20 * 1024 * 1024
LOOPBACK = {"localhost", "127.0.0.1", "::1"}
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("image/svg+xml", ".svg")


class App:
    def __init__(self, store: Store, *, allowed_hosts: set[str] | None = None):
        self.store = store
        self.token = secrets.token_urlsafe(24)
        self.allowed_hosts = LOOPBACK | {h.strip().lower() for h in (allowed_hosts or set()) if h.strip()}
        self.clients: set[queue.Queue] = set()
        self.clients_lock = threading.Lock()
        self.runner = integ.Runner()
        self.exports: dict[str, tuple[Path, str, float]] = {}  # one-shot downloads made in the browser
        self.exports_lock = threading.Lock()
        self.stop = threading.Event()
        store.listeners.append(self.broadcast)

    def broadcast(self, event: dict) -> None:
        with self.clients_lock:
            for q in list(self.clients):
                try:
                    q.put_nowait(event)
                except queue.Full:
                    pass

    # -------------------------------------------------------------- folder watcher
    def add_export(self, data: bytes, name: str) -> str:
        """Keep a file the page generated (e.g. a .pptx) for one download, so the browser
        receives it with a proper UTF-8 filename. Old entries expire after 10 minutes."""
        folder = self.store.root / "uploads" / ".exports"
        folder.mkdir(parents=True, exist_ok=True)
        key = secrets.token_urlsafe(16)
        path = folder / f"{key}.bin"
        path.write_bytes(data)
        with self.exports_lock:
            now_t = time.time()
            for k, (p, _, at) in list(self.exports.items()):
                if now_t - at > 600:
                    p.unlink(missing_ok=True)
                    self.exports.pop(k, None)
            self.exports[key] = (path, name, now_t)
        return key

    def take_export(self, key: str) -> tuple[Path, str] | None:
        with self.exports_lock:
            item = self.exports.pop(key, None)
        return (item[0], item[1]) if item and time.time() - item[2] <= 600 else None

    def watch_once(self) -> dict | None:
        """Look for new files in reference folders; queue them as one proposal."""
        settings = self.store.settings()
        if not settings.get("watch_folders") or not settings.get("reference_folders"):
            return None
        files = integ.scan_folders(settings["reference_folders"])
        new = set(self.store.unseen([f["path"] for f in files]))
        fresh = [f for f in files if f["path"] in new]
        if not fresh:
            return None
        entries, _ = integ.dedupe([o["data"] for o in integ.ops_for_files(fresh)], self.store.snapshot()["papers"])
        ops = [{"op": "create", "entity": "paper", "data": e} for e in entries]
        names = ", ".join(f["name"] for f in fresh[:5]) + (" …" if len(fresh) > 5 else "")
        result = None
        if ops:
            zh = settings.get("language") != "en"
            try:
                result = self.store.propose("folder-watcher",
                                            f"文獻資料夾有 {len(fresh)} 個新檔案" if zh else f"{len(fresh)} new file(s) in reference folders",
                                            ops, (f"找到：{names}" if zh else f"Found: {names}"))
            except ValidationError:
                return None  # not marked seen: offered again on the next scan
        self.store.mark_seen([f["path"] for f in fresh])
        return result

    def context(self) -> dict:
        snap = self.store.snapshot()
        return {"title": snap["settings"].get("project_title", ""),
                "rqs": [f"{r['code']}: {r['text']}" for r in snap["rqs"]][:8],
                "variables": [f"{v['symbol']} {v['name_en'] or v['name_zh']} ({v['role']})" for v in snap["variables"]][:20],
                "variables_en": [v["name_en"] for v in snap["variables"] if v["name_en"]]}

    def search_counted(self, provider: str, query: str, *, year_from: int = 0, limit: int = 20) -> list[dict]:
        self.store.take_quota(provider)
        return integ.search(provider, query, self.store.settings(), year_from=year_from, limit=limit)

    def literature_watch(self, stage: dict, query: str, providers: list[str], note: str) -> dict | None:
        """Search the chosen free sources for papers related to a check-in and queue the
        ones not yet in the library as one proposal (the user decides what to keep)."""
        found, errors = [], []
        for provider in providers:
            try:
                found += self.search_counted(provider, query, limit=10)
            except QuotaError as e:
                errors.append(str(e))
            except Exception as e:  # network/API failure of one source must not stop the others
                errors.append(f"{provider}: {e}")
        entries, _ = integ.dedupe([{k: r.get(k, "") for k in ("title", "authors", "year", "venue", "doi", "url", "abstract")}
                                   | {"source": r["provider"]} for r in found], self.store.snapshot()["papers"])
        zh = self.store.settings().get("language") != "en"
        if errors:
            self.store.log("literature-watch", "error", "; ".join(errors)[:300])
        if not entries:
            return None
        title = (f"「{stage['title_zh']}」相關新文獻 {len(entries)} 篇" if zh
                 else f"{len(entries)} new paper(s) related to “{stage['title_en'] or stage['title_zh']}”")
        summary = (f"檢索：{query}（{', '.join(providers)}）\n依據進度說明：{note[:300]}" if zh
                   else f"Query: {query} ({', '.join(providers)})\nFrom the progress note: {note[:300]}")
        ops = [{"op": "create", "entity": "paper", "data": {**e, "status": "candidate", "year": int(e.get("year") or 0),
                                                            "notes": f"literature watch · {stage['key'] or stage['title_en']}"}}
               for e in entries[:30]]
        return self.store.propose("literature-watch", title, ops, summary)

    def watch_loop(self, interval: float = 30.0) -> None:
        while not self.stop.wait(interval):
            try:
                self.watch_once()
            except Exception as e:  # never kill the watcher thread
                print(f"[watcher] {e}", file=sys.stderr)


def make_handler(app: App):
    store = app.store

    class Handler(BaseHTTPRequestHandler):
        server_version = f"ResearchHub/{__version__}"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # quiet by default
            if os.environ.get("HUB_DEBUG"):
                super().log_message(fmt, *args)

        # ---------------------------------------------------------- helpers
        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").strip().lower()
            if host.startswith("["):
                host = host[1:].split("]", 1)[0]
            else:
                host = host.rsplit(":", 1)[0] if host.count(":") == 1 else host
            return host.rstrip(".") in app.allowed_hosts

        def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, code: int, obj) -> None:
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8",
                       {"Cache-Control": "no-store"})

        def _error(self, code: int, message: str) -> None:
            self._json(code, {"error": message})

        def _body(self, limit: int = MAX_JSON) -> bytes:
            length = int(self.headers.get("Content-Length") or 0)
            if length > limit:
                raise ValidationError(f"request too large (limit {limit // (1024 * 1024)} MB)")
            return self.rfile.read(length) if length else b""

        def _payload(self) -> dict:
            raw = self._body()
            if not raw:
                return {}
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                raise ValidationError("invalid JSON") from None
            if not isinstance(data, dict):
                raise ValidationError("JSON body must be an object")
            return data

        def _user_ok(self) -> bool:
            return secrets.compare_digest(self.headers.get("X-Hub-Token", ""), app.token)

        def _agent_ok(self) -> bool:
            auth = self.headers.get("Authorization", "")
            token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
            expected = store.settings().get("agent_token") or ""
            return bool(token and expected) and secrets.compare_digest(token, expected)

        def _file(self, path: Path, *, download: str | None = None, trusted: bool = False):
            try:
                size = path.stat().st_size
                ctype = mimetypes.guess_type(download or path.name)[0] or "application/octet-stream"
                extra = {"Cache-Control": "no-cache"}
                if download:
                    ascii_name = re.sub(r"[^A-Za-z0-9._ -]", "_", download).strip() or "download"
                    extra["Content-Disposition"] = f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(download)}"
                elif not trusted and ctype not in ("application/pdf",) and not ctype.startswith(("image/", "text/plain")):
                    extra["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(path.name)}"
                if not trusted and (ctype.startswith("text/html") or ctype == "image/svg+xml"):
                    extra["Content-Security-Policy"] = "sandbox"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(size))
                self.send_header("X-Content-Type-Options", "nosniff")
                for k, v in extra.items():
                    self.send_header(k, v)
                self.end_headers()
                if self.command == "HEAD":
                    return
                with path.open("rb") as fh:
                    shutil.copyfileobj(fh, self.wfile, 1024 * 256)
            except OSError:
                self._error(404, "file not found")

        def _index(self, lang: str | None):
            html = (WEB / "index.html").read_text(encoding="utf-8")
            settings = store.settings(public=True)
            lang = lang or settings.get("language") or "zh"
            html = html.replace("{{TOKEN}}", app.token).replace("{{LANG}}", "en" if lang == "en" else "zh")
            html = html.replace("{{HTML_LANG}}", "en" if lang == "en" else "zh-Hant-TW").replace("{{VERSION}}", __version__)
            en = lang == "en"
            for key, zh_text, en_text in (("TITLE", "研究進度中樞 · Research Hub", "Research Hub · 研究進度中樞"),
                                          ("SKIP", "跳到主要內容", "Skip to content"),
                                          ("PIPELINE", "研究流程", "Research pipeline"),
                                          ("NOSCRIPT", "此頁面需要啟用 JavaScript。", "Research Hub needs JavaScript.")):
                html = html.replace("{{" + key + "}}", en_text if en else zh_text)
            self._send(200, html.encode("utf-8"), "text/html; charset=utf-8", {
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                                           "font-src 'self'; script-src 'self'; connect-src 'self'; "
                                           "frame-src 'self'; object-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            })

        def _events(self):
            q: queue.Queue = queue.Queue(maxsize=500)
            with app.clients_lock:
                app.clients.add(q)
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                self.wfile.write(b"retry: 3000\n\n")
                self.wfile.flush()
                while not app.stop.is_set():
                    try:
                        event = q.get(timeout=20)
                        self.wfile.write(f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8"))
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                with app.clients_lock:
                    app.clients.discard(q)
                self.close_connection = True

        # ---------------------------------------------------------- dispatch
        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            if not self._host_ok():
                return self._error(403, "host not allowed")
            url = urlparse(self.path)
            path, qs = url.path, parse_qs(url.query)
            try:
                return self._get(path, qs)
            except QuotaError as e:
                return self._error(429, str(e))
            except ValidationError as e:
                return self._error(400, str(e))
            except Exception as e:  # pragma: no cover - surfaced to the UI
                return self._error(500, f"{type(e).__name__}: {e}")

        def do_POST(self):
            if not self._host_ok():
                return self._error(403, "host not allowed")
            url = urlparse(self.path)
            path, qs = url.path, parse_qs(url.query)
            try:
                if path.startswith("/api/agent/"):
                    if not self._agent_ok():
                        return self._error(401, "invalid agent token")
                    return self._agent_post(path)
                if not self._user_ok():
                    return self._error(403, "missing or invalid page token; reload the dashboard")
                return self._post(path, qs)
            except QuotaError as e:
                return self._error(429, str(e))
            except ValidationError as e:
                return self._error(400, str(e))
            except Exception as e:  # pragma: no cover
                return self._error(500, f"{type(e).__name__}: {e}")

        # ---------------------------------------------------------- GET routes
        def _get(self, path: str, qs: dict):
            q1 = lambda k, d="": (qs.get(k) or [d])[0]  # noqa: E731
            if path in ("/", "/index.html"):
                return self._index(q1("lang") or None)
            if path in ("/zh", "/zh/", "/en", "/en/"):
                return self._index(path.strip("/"))
            if path.startswith("/static/"):
                rel = unquote(path[len("/static/"):])
                target = (WEB / rel).resolve()
                if not target.is_relative_to(WEB.resolve()) or not target.is_file():
                    return self._error(404, "not found")
                return self._file(target, trusted=True)
            if path == "/favicon.svg":
                return self._file(WEB / "favicon.svg", trusted=True)
            if path == "/api/version":
                return self._json(200, {"name": "research-hub", "version": __version__})
            if path.startswith("/api/agent/"):
                if not self._agent_ok():
                    return self._error(401, "invalid agent token")
                return self._agent_get(path, qs)
            if path == "/api/events":  # EventSource cannot send headers: token travels in the query
                if not secrets.compare_digest(q1("token"), app.token):
                    return self._error(403, "missing or invalid page token")
                return self._events()
            m = re.fullmatch(r"/api/exports/([A-Za-z0-9_-]{10,40})", path)
            if m:  # opened by navigation, so the token travels in the query
                if not secrets.compare_digest(q1("token"), app.token):
                    return self._error(403, "missing or invalid page token")
                item = app.take_export(m.group(1))
                if not item:
                    return self._error(404, "this download has expired — export again")
                try:
                    return self._file(item[0], download=item[1])
                finally:
                    item[0].unlink(missing_ok=True)
            # Everything below can expose project data: require the page token.
            if not self._user_ok():
                return self._error(403, "missing or invalid page token; reload the dashboard")
            if path == "/api/state":
                body = json.dumps(store.snapshot(), ensure_ascii=False).encode("utf-8")
                etag = '"' + hashlib.sha1(body).hexdigest()[:20] + '"'
                if self.headers.get("If-None-Match") == etag:
                    self.send_response(304)
                    self.send_header("ETag", etag)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return None
                return self._send(200, body, "application/json; charset=utf-8", {"ETag": etag, "Cache-Control": "no-cache"})
            if path == "/api/proposals":
                return self._json(200, {"items": store.list_proposals(q1("status", "pending"))})
            if path == "/api/agent-config":
                settings = store.settings()
                host, port = self.server.server_address[:2]
                return self._json(200, {"token": settings["agent_token"], "url": f"http://{host}:{port}",
                                        "python": sys.executable, "data_dir": str(store.root)})
            if path == "/api/scan":
                settings = store.settings()
                files = integ.scan_folders(settings.get("reference_folders") or [])
                linked = {p["local_path"] for p in store.snapshot()["papers"] if p["local_path"]}
                for f in files:
                    f["linked"] = f["path"] in linked
                return self._json(200, {"files": files, "folders": settings.get("reference_folders") or []})
            if path == "/api/scripts":
                settings = store.settings()
                return self._json(200, {"scripts": integ.list_scripts(settings.get("code_dir", "")),
                                        "runs": app.runner.runs, "allow_run": bool(settings.get("allow_code_run")),
                                        "code_dir": settings.get("code_dir", "")})
            if path == "/api/tts/voices":
                return self._json(200, {"engine": voice.engine(), "voices": voice.voices()})
            if path == "/api/usage":
                data = store.usage()
                data["ai"] = bool(integ.ai_config(store.settings()))
                return self._json(200, data)
            if path == "/api/search":
                provider = q1("provider", "openalex")
                try:
                    year = int(q1("year_from", "0") or 0)
                except ValueError:
                    year = 0
                try:
                    results = app.search_counted(provider, q1("q"), year_from=year)
                except QuotaError:
                    raise
                except ValueError as e:
                    raise ValidationError(str(e)) from None
                except Exception as e:
                    return self._error(502, f"{provider} unavailable: {e}")
                return self._json(200, {"results": results})
            if path == "/api/search/openalex":
                settings = store.settings()
                try:
                    year = int(q1("year_from", "0") or 0)
                except ValueError:
                    year = 0
                try:
                    results = app.search_counted("openalex", q1("q"), year_from=year)
                except QuotaError:
                    raise
                except Exception as e:
                    return self._error(502, f"OpenAlex unavailable: {e}")
                return self._json(200, {"results": results})
            if path == "/api/local":
                target = integ.expand(q1("path"))
                if not target.is_file() or not integ.inside(target, integ.allowed_roots(store.settings())):
                    return self._error(403, "file is outside the configured folders")
                return self._file(target.resolve())
            m = re.fullmatch(r"/api/files/(\d+)", path)
            if m:
                row = store.get("file", int(m.group(1)))
                if not row:
                    return self._error(404, "file not found")
                target = (store.root / "uploads" / row["stored"]).resolve()
                if not target.is_relative_to((store.root / "uploads").resolve()):
                    return self._error(403, "forbidden")
                return self._file(target, download=row["name"] if q1("download") else None)
            if path == "/api/export/bibtex":
                papers = [p for p in store.snapshot()["papers"] if p["status"] != "excluded"]
                return self._send(200, integ.to_bibtex(papers).encode("utf-8"), "application/x-bibtex; charset=utf-8",
                                  {"Content-Disposition": "attachment; filename=references.bib"})
            if path == "/api/export/json":
                snap = store.snapshot()
                snap["proposals"] = store.list_proposals("all", 1000)
                body = json.dumps(snap, ensure_ascii=False, indent=2).encode("utf-8")
                return self._send(200, body, "application/json; charset=utf-8",
                                  {"Content-Disposition": f"attachment; filename=research-hub-{time.strftime('%Y%m%d')}.json"})
            return self._error(404, "not found")

        # ---------------------------------------------------------- POST routes
        def _post(self, path: str, qs: dict):
            q1 = lambda k, d="": (qs.get(k) or [d])[0]  # noqa: E731
            if path == "/api/ops":
                data = self._payload()
                return self._json(200, {"results": store.apply_ops(data.get("ops"), actor="user")})
            if path == "/api/settings":
                return self._json(200, {"settings": store.save_settings(self._payload())})
            if path == "/api/agent-token/rotate":
                return self._json(200, {"token": store.rotate_agent_token()})
            m = re.fullmatch(r"/api/proposals/(\d+)/(approve|reject)", path)
            if m:
                data = self._payload()
                ops = data.get("ops") if m.group(2) == "approve" else None
                return self._json(200, store.decide(int(m.group(1)), m.group(2) == "approve", ops))
            if path == "/api/proposals/approve-all":
                done, failed = [], []
                for p in reversed(store.list_proposals("pending")):
                    try:
                        store.decide(p["id"], True)
                        done.append(p["id"])
                    except ValidationError as e:
                        failed.append({"id": p["id"], "error": str(e)})
                return self._json(200, {"approved": done, "failed": failed})
            if path == "/api/upload":
                name = unquote(self.headers.get("X-Filename", "")).strip()
                name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", Path(name).name)[:180].strip()
                if not name.strip("."):
                    name = "upload.bin"
                try:
                    stage_id = int(q1("stage_id", "0") or 0) or None
                    paper_id = int(q1("paper_id", "0") or 0) or None
                except ValueError:
                    raise ValidationError("stage_id and paper_id must be numbers") from None
                if stage_id and not store.get("stage", stage_id):
                    raise ValidationError("unknown stage")
                if paper_id and not store.get("paper", paper_id):
                    raise ValidationError("unknown paper")
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0:
                    raise ValidationError("empty file")
                if length > MAX_UPLOAD:
                    raise ValidationError(f"file too large (limit {MAX_UPLOAD // (1024 * 1024)} MB)")
                folder = f"stage-{stage_id}" if stage_id else (f"paper-{paper_id}" if paper_id else "general")
                target_dir = store.root / "uploads" / folder
                target_dir.mkdir(parents=True, exist_ok=True)
                stem, suffix = Path(name).stem, Path(name).suffix
                target, n = target_dir / name, 1
                while target.exists():
                    n += 1
                    target = target_dir / f"{stem} ({n}){suffix}"
                remaining = length
                try:  # stream to disk in chunks instead of holding the whole file in memory
                    with target.open("wb") as fh:
                        while remaining:
                            chunk = self.rfile.read(min(1024 * 1024, remaining))
                            if not chunk:
                                break
                            fh.write(chunk)
                            remaining -= len(chunk)
                    if remaining:
                        raise ValidationError("upload interrupted")
                except BaseException:
                    target.unlink(missing_ok=True)
                    raise
                rel = target.relative_to(store.root / "uploads").as_posix()
                res = store.apply_ops([{"op": "create", "entity": "file", "data": {
                    "name": target.name, "stored": rel, "size": length, "stage_id": stage_id, "paper_id": paper_id,
                    "mime": mimetypes.guess_type(target.name)[0] or ""}}], actor="user", allow_internal=True)
                return self._json(200, {"id": res[0]["id"], "name": target.name})
            if path == "/api/exports":
                name = unquote(self.headers.get("X-Filename", "")).strip()
                name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", Path(name).name)[:180] or "export.bin"
                data = self._body(MAX_UPLOAD)
                if not data:
                    raise ValidationError("empty file")
                key = app.add_export(data, name)
                return self._json(200, {"url": f"/api/exports/{key}"})
            if path == "/api/import/bibtex":
                text = self._body().decode("utf-8", errors="replace")
                entries = integ.parse_bibtex(text) or integ.parse_ris(text)
                if not entries:
                    raise ValidationError("no BibTeX/RIS entries found")
                entries, skipped = integ.dedupe(entries, store.snapshot()["papers"])
                if entries:
                    store.apply_ops([{"op": "create", "entity": "paper", "data": {**e, "source": "bibtex"}} for e in entries], actor="user")
                return self._json(200, {"imported": len(entries), "skipped": skipped})
            if path == "/api/import/files":
                data = self._payload()
                wanted = set(data.get("paths") or [])
                files = [f for f in integ.scan_folders(store.settings().get("reference_folders") or []) if f["path"] in wanted]
                if not files:
                    raise ValidationError("no matching files in the configured folders")
                entries, skipped = integ.dedupe([o["data"] for o in integ.ops_for_files(files)], store.snapshot()["papers"])
                if entries:
                    store.apply_ops([{"op": "create", "entity": "paper", "data": e} for e in entries], actor="user")
                store.mark_seen([f["path"] for f in files])
                return self._json(200, {"imported": len(entries), "skipped": skipped})
            if path == "/api/classify":
                names = [str(n)[:300] for n in (self._payload().get("names") or [])][:200]
                return self._json(200, integ.classify(names, store.snapshot()["stages"], store.settings().get("archive_rules")))
            if path == "/api/ai/suggest":
                data = self._payload()
                cfg = integ.ai_config(store.settings())
                if not cfg:
                    raise ValidationError("AI assistant is not set up — choose a provider and key in Settings")
                stage = store.get("stage", int(data.get("stage_id") or 0))
                if not stage:
                    raise ValidationError("unknown stage")
                tasks = [t for t in store.snapshot()["tasks"] if t["stage_id"] == stage["id"]]
                system, user = integ.checkin_prompt(stage, tasks, str(data.get("note") or "")[:4000],
                                                    [str(n)[:200] for n in data.get("files") or []][:30], app.context())
                store.take_quota("ai")
                try:
                    text, tokens = integ.ai_chat(cfg, system, user)
                except Exception as e:
                    return self._error(502, f"AI service unavailable: {e}")
                store.add_tokens("ai", tokens)
                out = integ.parse_json_block(text)
                ids = {t["id"] for t in tasks}
                try:
                    progress = max(0, min(100, int(out.get("progress"))))
                except (TypeError, ValueError):
                    progress = None
                return self._json(200, {"progress": progress,
                                        "done_task_ids": [i for i in out.get("done_task_ids") or [] if isinstance(i, int) and i in ids],
                                        "query": str(out.get("query") or "")[:200], "summary": str(out.get("summary") or "")[:500],
                                        "tokens": tokens})
            if path == "/api/framework/extract":
                return self._json(200, self._framework(qs))
            if path == "/api/slides/ai":
                return self._json(200, self._slides_ai(self._payload()))
            if path == "/api/topic/check":
                data = self._payload()
                title = str(data.get("title") or "").strip()[:300]
                if not title:
                    raise ValidationError("enter a title first")
                snap, settings = store.snapshot(), store.settings()
                online = data.get("online", True) is not False
                if online:
                    store.take_quota("openalex")
                ai = (lambda system, user: self._ai_text(system, user)) if online and integ.ai_config(settings) and data.get("ai") else None
                result = topic_mod.check(title, snap.get("topic") or {}, snap, settings, title_en=str(data.get("title_en") or "")[:300], online=online, ai=ai)
                store.apply_ops([{"op": "update", "entity": "topic", "match": {"key": "main"},
                                  "data": {"title": title, "checked": topic_mod.dumps(result)[:60000]}}], actor="user")
                return self._json(200, result)
            if path == "/api/export/docx":
                data = self._payload()
                blob = thesis.build(store.snapshot(), data)
                name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", str(data.get("filename") or "thesis"))[:120] + ".docx"
                return self._json(200, {"url": f"/api/exports/{app.add_export(blob, name)}", "name": name, "size": len(blob)})
            if path == "/api/tts":
                data = self._payload()
                try:
                    blob = voice.synthesize(str(data.get("text") or ""), str(data.get("voice") or ""), data.get("rate") or 1, data.get("pitch") or 1)
                except voice.VoiceError as e:
                    raise ValidationError(str(e)) from None
                except Exception as e:
                    return self._error(500, f"speech failed: {e}")
                name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", str(data.get("filename") or "podcast"))[:120] + ".wav"
                return self._json(200, {"url": f"/api/exports/{app.add_export(blob, name)}", "name": name, "size": len(blob)})
            if path == "/api/exam/seed":
                self._payload()
                ops = exam.seed_ops(store.snapshot()["questions"])
                if ops:
                    store.apply_ops(ops, actor="user")
                return self._json(200, {"added": len(ops)})
            if path == "/api/exam/predict":
                data = self._payload()
                lang, folder, snap = ("en" if data.get("lang") == "en" else "zh"), str(data.get("folder") or "")[:120], store.snapshot()
                if data.get("ai"):
                    out = self._ai_json(*exam.predict_prompt(snap, folder, lang))
                    items = [{"text": str(q.get("text") or "")[:2000], "reason": str(q.get("reason") or "")[:300], "outline": str(q.get("outline") or "")[:4000],
                              "difficulty": q.get("difficulty") if q.get("difficulty") in ("easy", "medium", "hard") else "medium", "folder": folder or "考題預測"}
                             for q in (out.get("questions") or []) if isinstance(q, dict) and str(q.get("text") or "").strip()][:10]
                    return self._json(200, {"questions": items, "method": "ai"})
                return self._json(200, {"questions": exam.predict_rules(snap, folder, lang), "method": "rules"})
            if path in ("/api/exam/analyze", "/api/exam/grade"):
                data = self._payload()
                question = store.get("question", int(data.get("id") or 0))
                if not question:
                    raise ValidationError("unknown question")
                lang = "en" if data.get("lang") == "en" else "zh"
                if path.endswith("analyze"):
                    if data.get("ai"):
                        paper = store.get("paper", question["paper_id"]) if question.get("paper_id") else None
                        out = self._ai_json(*exam.analyze_prompt(question, paper, lang))
                        return self._json(200, {"analysis": str(out.get("analysis") or "")[:6000], "outline": str(out.get("outline") or "")[:6000], "method": "ai"})
                    return self._json(200, exam.outline_for(question["text"], lang))
                answer = str(data.get("answer") or "")[:20000]
                if not answer.strip():
                    raise ValidationError("write an answer first")
                result = exam.coverage(question.get("outline") or "", answer)
                if data.get("ai"):
                    out = self._ai_json(*exam.grade_prompt(question, answer, lang))
                    try:
                        result["score"] = max(0, min(100, int(out.get("score"))))
                    except (TypeError, ValueError):
                        pass
                    result.update(method="ai", strengths=str(out.get("strengths") or "")[:2000], gaps=str(out.get("gaps") or "")[:2000],
                                  tip=str(out.get("rewrite_tip") or "")[:2000])
                return self._json(200, result)
            if path == "/api/checkin":
                return self._json(200, self._checkin(self._payload()))
            if path == "/api/watch/scan":
                result = app.watch_once()
                return self._json(200, {"proposal": result})
            if path == "/api/scripts/run":
                settings = store.settings()
                if not settings.get("allow_code_run"):
                    raise ValidationError("running scripts is disabled — enable it in Settings")
                root = integ.expand(settings.get("code_dir", ""))
                script = integ.expand(self._payload().get("path", ""))
                if not settings.get("code_dir") or not script.is_file() or script.suffix != ".py" or not integ.inside(script, [root]):
                    raise ValidationError("script must be a .py file inside the code folder")

                def done(run):
                    store.log("python", "run", f"{Path(run['script']).name}: {run['state']}")
                    app.broadcast({"type": "run", "id": run["id"], "state": run["state"]})

                try:
                    run = app.runner.start(script.resolve(), root.resolve(), int(settings.get("code_timeout") or 600), done)
                except RuntimeError as e:
                    raise ValidationError(str(e)) from None
                store.log("user", "run", f"started {script.name}")
                return self._json(200, {"run": run})
            if path == "/api/reveal":
                target = integ.expand(self._payload().get("path", ""))
                roots = integ.allowed_roots(store.settings()) + [store.root / "uploads"]
                if not target.exists() or not integ.inside(target, roots):
                    raise ValidationError("path is outside the configured folders")
                folder = target if target.is_dir() else target.parent
                try:
                    if sys.platform.startswith("win"):
                        os.startfile(str(folder))  # type: ignore[attr-defined]
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", str(folder)])
                    else:
                        subprocess.Popen(["xdg-open", str(folder)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except OSError as e:
                    raise ValidationError(f"cannot open the file manager here: {e}") from None
                return self._json(200, {"ok": True})
            return self._error(404, "not found")

        # ---------------------------------------------------------- research model from the user's writing
        def _framework(self, qs: dict) -> dict:
            """Read the user's own draft (pasted text or an uploaded .docx/.txt/.md/.tex) and
            propose a research model. Nothing is saved: the dashboard shows the result for
            review and the user applies what they keep."""
            use_ai = (qs.get("ai") or ["0"])[0] == "1"
            filename = unquote(self.headers.get("X-Filename", "")).strip()
            if filename:
                try:
                    text = integ.read_document(self._body(), filename)
                except ValueError as e:
                    raise ValidationError(str(e)) from None
            else:
                data = self._payload()
                text = str(data.get("text") or "")
                use_ai = use_ai or bool(data.get("ai"))
            text = text.strip()
            if len(text) < 10:
                raise ValidationError("the text is too short to find a research model")
            if use_ai:
                cfg = integ.ai_config(store.settings())
                if not cfg:
                    raise ValidationError("AI assistant is not set up — choose a provider and key in Settings")
                store.take_quota("ai")
                system, user = integ.framework_prompt(text)
                try:
                    reply, tokens = integ.ai_chat(cfg, system, user, timeout=120)
                except Exception as e:
                    raise ValidationError(f"AI service unavailable: {e}") from None
                store.add_tokens("ai", tokens)
                result = integ.normalize_framework(integ.parse_json_block(reply), "ai")
                result["tokens"] = tokens
            else:
                result = integ.extract_framework_rules(text)
            existing = {}
            for v in store.snapshot()["variables"]:
                for name in (v["name_zh"], v["name_en"]):
                    if name:
                        existing[re.sub(r"\s+", "", name).casefold()] = v["id"]
            for v in result["variables"]:
                for name in (v["name_zh"], v["name_en"]):
                    key = re.sub(r"\s+", "", name or "").casefold()
                    if key and key in existing:
                        v["existing_id"] = existing[key]
                        break
            result["chars"] = len(text)
            return result

        # ---------------------------------------------------------- slide text by the AI assistant
        def _ai_text(self, system: str, user: str) -> str:
            cfg = integ.ai_config(store.settings())
            if not cfg:
                raise ValidationError("AI assistant is not set up — choose a provider and key in Settings")
            store.take_quota("ai")
            text, tokens = integ.ai_chat(cfg, system, user)
            store.add_tokens("ai", tokens)
            return text

        def _ai_json(self, system: str, user: str) -> dict:
            try:
                return integ.parse_json_block(self._ai_text(system, user)) or {}
            except (ValidationError, QuotaError):
                raise
            except Exception as e:
                raise ValidationError(f"AI service unavailable: {e}") from None

        def _slides_ai(self, data: dict) -> dict:
            """Key message and speaker notes per slide, following the user's design instructions.
            Only text comes back; the deck itself is built in the browser."""
            cfg = integ.ai_config(store.settings())
            if not cfg:
                raise ValidationError("AI assistant is not set up — choose a provider and key in Settings")
            allowed = {"title", "overview", "rqs", "model", "hypotheses", "variables", "literature", "progress", "next", "closing"}
            sections = [k for k in data.get("sections") or [] if k in allowed]
            if not sections:
                raise ValidationError("no slides selected")
            lang = "English" if data.get("lang") == "en" else "Traditional Chinese (Taiwan)"
            snap = store.snapshot()
            var = {v["id"]: v for v in snap["variables"]}
            name = lambda v: (v["name_en"] or v["name_zh"]) if data.get("lang") == "en" else (v["name_zh"] or v["name_en"])  # noqa: E731
            facts = [f"Project: {snap['settings'].get('project_title', '')}", f"Overall progress: {snap['overall']}%",
                     f"Thesis deadline: {snap['settings'].get('project_deadline') or '-'}",
                     "Stages: " + "; ".join(f"{s_['title_en'] or s_['title_zh']} {s_['status']} {s_['progress']}%" for s_ in snap["stages"]),
                     "Research questions: " + " | ".join(f"{r['code']}: {r['text']}" for r in snap["rqs"][:8]),
                     "Variables: " + "; ".join(f"{v['symbol']} {name(v)} ({v['role']})" for v in snap["variables"][:20]),
                     "Hypotheses: " + "; ".join(f"{r['label']} {name(var[r['source_id']])} -> {name(var[r['target_id']])} {r['kind']} {r['sign']}"
                                                for r in snap.get("relations", [])[:20] if r["source_id"] in var and r["target_id"] in var),
                     f"Papers: {len(snap['papers'])}", "Recent progress notes: " + " | ".join(u["note"][:200] for u in snap["updates"][:5])]
            system = ("You prepare a graduate student's slides. Using ONLY the facts given, write for each requested slide key a short key "
                      "message (one sentence, max 40 words) and speaker notes (3-6 sentences). Follow the design instructions for tone and emphasis. "
                      f"Write in {lang}. Reply with ONE JSON object: {{\"messages\": {{key: text}}, \"notes\": {{key: text}}}}. Never invent results.")
            user = (f"Purpose: {str(data.get('purpose') or '')[:40]}\nSlides: {', '.join(sections)}\n"
                    f"Design instructions: {str(data.get('instructions') or '')[:2000]}\n\nFacts:\n" + "\n".join(facts))
            store.take_quota("ai")
            try:
                reply, tokens = integ.ai_chat(cfg, system, user[:24000], timeout=120)
            except Exception as e:
                raise ValidationError(f"AI service unavailable: {e}") from None
            store.add_tokens("ai", tokens)
            out = integ.parse_json_block(reply)
            clean = lambda d, limit: {k: str(v)[:limit] for k, v in (d or {}).items() if k in sections and isinstance(v, str) and v.strip()}  # noqa: E731
            return {"messages": clean(out.get("messages"), 300), "notes": clean(out.get("notes"), 2000), "tokens": tokens}

        # ---------------------------------------------------------- check-in
        def _checkin(self, data: dict) -> dict:
            """Upload check-in: the user says where the stage stands (required), may set the
            progress, tick tasks, set the goal and deadline; everything is applied at once and
            logged. Related-literature tracking runs in the background and lands in the inbox."""
            note = str(data.get("note") or "").strip()
            if not note:
                raise ValidationError("please describe where this stage stands")
            try:
                stage_id = int(data.get("stage_id") or 0)
            except (TypeError, ValueError):
                raise ValidationError("unknown stage") from None
            stage = store.get("stage", stage_id)
            if not stage:
                raise ValidationError("unknown stage")
            file_ids = [int(i) for i in data.get("file_ids") or [] if str(i).isdigit()][:100]
            files = [store.get("file", i) for i in file_ids]
            if any(f is None for f in files):
                raise ValidationError("unknown file")
            ops: list[dict] = []
            patch: dict = {}
            if data.get("due_date") is not None:
                patch["due_date"] = str(data["due_date"])
            if data.get("goal") is not None:
                patch["goal"] = str(data["goal"])
            if stage["status"] == "todo":
                patch["status"] = "active"
                if not stage["start_date"]:
                    patch["start_date"] = time.strftime("%Y-%m-%d")
            for tid in data.get("done_task_ids") or []:
                ops.append({"op": "update", "entity": "task", "id": int(tid), "data": {"done": True}})
            for f in files:  # auto-archive: attach the uploaded files to the chosen stage
                if f["stage_id"] != stage_id:
                    ops.append({"op": "update", "entity": "file", "id": f["id"], "data": {"stage_id": stage_id}})
            if patch:
                ops.insert(0, {"op": "update", "entity": "stage", "id": stage_id, "data": patch})
            if ops:
                store.apply_ops(ops, actor="user", allow_internal=True)
            # explicit progress wins over the task-derived value, so apply it last
            if data.get("progress") not in (None, ""):
                progress = max(0, min(100, int(data["progress"])))
                if progress != store.get("stage", stage_id)["progress"]:
                    extra = {"status": "review"} if progress == 100 and store.get("stage", stage_id)["status"] != "done" else {}
                    store.apply_ops([{"op": "update", "entity": "stage", "id": stage_id, "data": {"progress": progress, **extra}}], actor="user")
            if data.get("project_deadline"):
                store.save_settings({"project_deadline": str(data["project_deadline"])})
            after = store.get("stage", stage_id)
            store.apply_ops([{"op": "create", "entity": "update", "data": {
                "stage_id": stage_id, "note": note, "progress_before": stage["progress"],
                "progress_after": 100 if after["status"] == "done" else after["progress"],
                "files": json.dumps([f["name"] for f in files], ensure_ascii=False), "source": "check-in"}}],
                actor="user", allow_internal=True)
            search = data.get("search") or {}
            providers = [p for p in search.get("providers") or [] if p in ("openalex", "wiley", "semantic", "wos")]
            query = str(search.get("query") or "").strip()[:200]
            started = False
            if providers and query:
                threading.Thread(target=self._watch_safe, args=(after, query, providers, note), daemon=True).start()
                started = True
            return {"ok": True, "stage": after, "search_started": started}

        def _watch_safe(self, stage, query, providers, note):
            try:
                app.literature_watch(stage, query, providers, note)
            except Exception as e:  # pragma: no cover - logged for the user
                store.log("literature-watch", "error", str(e)[:300])

        # ---------------------------------------------------------- agent API
        def _agent_get(self, path: str, qs: dict):
            if path == "/api/agent/state":
                snap = store.snapshot()
                snap.pop("activity", None)
                snap["language"] = snap.pop("settings", {}).get("language", "zh")
                snap["schema"] = {name: {"fields": {f: [s[0], list(s[1]) if isinstance(s[1], tuple) and s[0] == "enum" else s[1]]
                                                    for f, s in spec["fields"].items()}, "required": list(spec["required"])}
                                  for name, spec in ENTITIES.items() if not spec.get("internal")}
                return self._json(200, snap)
            if path == "/api/agent/proposals":
                items = store.list_proposals((qs.get("status") or ["all"])[0], 50)
                return self._json(200, {"items": items})
            return self._error(404, "not found")

        def _agent_post(self, path: str):
            if path == "/api/agent/proposals":
                data = self._payload()
                result = store.propose(data.get("source") or "agent", data.get("title"), data.get("ops"), data.get("summary", ""))
                return self._json(200, result)
            return self._error(404, "not found")

    return Handler


def serve(store: Store, host: str = "127.0.0.1", port: int = 8770, *, open_browser: bool = True,
          watch: bool = True) -> None:
    extra = set(filter(None, os.environ.get("HUB_ALLOWED_HOSTS", "").split(",")))
    if host not in ("127.0.0.1", "localhost", "::1"):
        extra.add(host)
    app = App(store, allowed_hosts=extra)
    httpd = ThreadingHTTPServer((host, port), make_handler(app))
    httpd.daemon_threads = True
    if watch:
        threading.Thread(target=app.watch_loop, daemon=True).start()
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{httpd.server_address[1]}/"
    print(f"Research Hub {__version__} · data: {store.root}")
    print(f"Dashboard: {url}   (中文 {url}zh/ · English {url}en/)")
    if open_browser:
        import webbrowser
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop.set()
        httpd.server_close()
