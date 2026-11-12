"""Local HTTP server: dashboard, JSON API, Server-Sent Events, agent inbox.

Security model (same spirit as PaperRead):
* listens on 127.0.0.1 by default and rejects unknown Host headers (DNS rebinding);
* every state-changing request from the dashboard carries the per-process token
  that is embedded in the page, so other web pages cannot write;
* agents authenticate with a separate, rotatable agent token and can only *propose*
  changes — nothing they send is applied until the user approves it;
* local files are served only from configured folders and the uploads folder.
"""
from __future__ import annotations

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

from . import __version__, integrations as integ
from .store import ENTITIES, Store, ValidationError

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
        self.store.mark_seen([f["path"] for f in fresh])
        ops = integ.ops_for_files(fresh)
        if not ops:
            return None
        names = ", ".join(f["name"] for f in fresh[:5]) + (" …" if len(fresh) > 5 else "")
        try:
            zh = settings.get("language") != "en"
            return self.store.propose("folder-watcher",
                                      f"文獻資料夾有 {len(fresh)} 個新檔案" if zh else f"{len(fresh)} new file(s) in reference folders",
                                      ops, (f"找到：{names}" if zh else f"Found: {names}"))
        except ValidationError:
            return None

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
                ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                extra = {"Cache-Control": "no-cache"}
                if download:
                    extra["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(download)}"
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
            # Everything below can expose project data: require the page token.
            if not self._user_ok():
                return self._error(403, "missing or invalid page token; reload the dashboard")
            if path == "/api/state":
                return self._json(200, store.snapshot())
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
            if path == "/api/search/openalex":
                settings = store.settings()
                try:
                    year = int(q1("year_from", "0") or 0)
                except ValueError:
                    year = 0
                try:
                    results = integ.openalex_search(q1("q"), year_from=year, mailto=settings.get("openalex_mailto", ""))
                except Exception as e:
                    return self._error(502, f"OpenAlex unavailable: {e}")
                return self._json(200, {"results": results})
            if path == "/api/paperread/status":
                settings = store.settings()
                items = integ.paperread_items(settings.get("paperread_library", ""))
                return self._json(200, {"online": integ.paperread_online(settings.get("paperread_url", "")),
                                        "library_found": integ.expand(settings.get("paperread_library", "")).is_dir(),
                                        "count": len(items)})
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
                name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", Path(name).name)[:180] or "upload.bin"
                stage_id = int(q1("stage_id", "0") or 0) or None
                paper_id = int(q1("paper_id", "0") or 0) or None
                if stage_id and not store.get("stage", stage_id):
                    raise ValidationError("unknown stage")
                if paper_id and not store.get("paper", paper_id):
                    raise ValidationError("unknown paper")
                folder = f"stage-{stage_id}" if stage_id else (f"paper-{paper_id}" if paper_id else "general")
                data = self._body(MAX_UPLOAD)
                if not data:
                    raise ValidationError("empty file")
                target_dir = store.root / "uploads" / folder
                target_dir.mkdir(parents=True, exist_ok=True)
                stem, suffix = Path(name).stem, Path(name).suffix
                target, n = target_dir / name, 1
                while target.exists():
                    n += 1
                    target = target_dir / f"{stem} ({n}){suffix}"
                target.write_bytes(data)
                rel = target.relative_to(store.root / "uploads").as_posix()
                res = store.apply_ops([{"op": "create", "entity": "file", "data": {
                    "name": target.name, "stored": rel, "size": len(data), "stage_id": stage_id, "paper_id": paper_id,
                    "mime": mimetypes.guess_type(target.name)[0] or ""}}], actor="user", allow_internal=True)
                return self._json(200, {"id": res[0]["id"], "name": target.name})
            if path == "/api/import/bibtex":
                text = self._body().decode("utf-8", errors="replace")
                entries = integ.parse_bibtex(text) or integ.parse_ris(text)
                if not entries:
                    raise ValidationError("no BibTeX/RIS entries found")
                ops = [{"op": "create", "entity": "paper", "data": {**e, "source": "bibtex"}} for e in entries]
                store.apply_ops(ops, actor="user")
                return self._json(200, {"imported": len(entries)})
            if path == "/api/import/files":
                data = self._payload()
                wanted = set(data.get("paths") or [])
                files = [f for f in integ.scan_folders(store.settings().get("reference_folders") or []) if f["path"] in wanted]
                if not files:
                    raise ValidationError("no matching files in the configured folders")
                ops = integ.ops_for_files(files)
                if not ops:
                    raise ValidationError("no references found in the selected files")
                store.apply_ops(ops, actor="user")
                store.mark_seen([f["path"] for f in files])
                return self._json(200, {"imported": len(ops)})
            if path == "/api/watch/scan":
                result = app.watch_once()
                return self._json(200, {"proposal": result})
            if path == "/api/paperread/sync":
                settings = store.settings()
                items = integ.paperread_items(settings.get("paperread_library", ""))
                if not items:
                    raise ValidationError("PaperRead library not found or empty — check the library path in Settings")
                snap = store.snapshot()
                ops, stats = integ.paperread_sync_ops(items, snap["papers"], snap["variables"])
                if not ops:
                    return self._json(200, {"proposal": None, "stats": stats})
                if settings.get("language") == "en":
                    title = f"PaperRead: {stats['new']} new, {stats['status']} status, {stats['variables']} variables"
                    summary = "Papers, reading status and variables found in the PaperRead library."
                else:
                    title = f"PaperRead：新文獻 {stats['new']} 篇、狀態更新 {stats['status']} 筆、變數 {stats['variables']} 個"
                    summary = "從 PaperRead 文獻庫找到的論文、閱讀狀態與研究變數。"
                proposal = store.propose("PaperRead sync", title, ops, summary)
                return self._json(200, {"proposal": proposal, "stats": stats})
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

        # ---------------------------------------------------------- agent API
        def _agent_get(self, path: str, qs: dict):
            if path == "/api/agent/state":
                snap = store.snapshot()
                snap.pop("activity", None)
                snap.pop("settings", None)
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
