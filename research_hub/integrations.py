"""Connections to things outside the hub: local reference folders, BibTeX/RIS files,
OpenAlex search, a PaperRead library, and Python analysis scripts.

Nothing here writes to the hub directly. Functions either return data for the
user to act on, or build ``ops`` lists that the server turns into proposals the
user must confirm.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

REFERENCE_EXT = {".pdf", ".bib", ".ris", ".docx", ".doc", ".txt", ".md", ".epub"}
MAX_SCAN = 5000


# ---------------------------------------------------------------- paths
def expand(path: str) -> Path:
    return Path(os.path.expandvars(str(path or "").strip())).expanduser()


def inside(path: Path, roots: list[Path]) -> bool:
    try:
        real = path.resolve()
    except OSError:
        return False
    for root in roots:
        try:
            if real.is_relative_to(root.resolve()):
                return True
        except OSError:
            continue
    return False


def allowed_roots(settings: dict) -> list[Path]:
    """Folders whose files the hub may read and serve: reference folders, the
    code folder and the PaperRead library."""
    roots = [expand(p) for p in settings.get("reference_folders") or []]
    if settings.get("code_dir"):
        roots.append(expand(settings["code_dir"]))
    if settings.get("paperread_library"):
        roots.append(expand(settings["paperread_library"]))
    return [r for r in roots if str(r) not in ("", ".", "/")]


# ---------------------------------------------------------------- folder scan
def scan_folders(folders: list[str]) -> list[dict]:
    out: list[dict] = []
    for folder in folders or []:
        root = expand(folder)
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in sorted(filenames):
                if name.startswith(".") or Path(name).suffix.lower() not in REFERENCE_EXT:
                    continue
                full = Path(dirpath) / name
                try:
                    stat = full.stat()
                except OSError:
                    continue
                out.append({"path": str(full.resolve()), "name": name, "folder": str(root),
                            "rel": str(full.relative_to(root)), "size": stat.st_size, "mtime": int(stat.st_mtime),
                            "ext": full.suffix.lower()})
                if len(out) >= MAX_SCAN:
                    return out
    return out


def title_from_filename(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[_]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem or name


def ops_for_files(files: list[dict]) -> list[dict]:
    """Paper-create operations for PDFs/documents found in reference folders.
    .bib / .ris files are expanded into one paper per entry."""
    ops: list[dict] = []
    for f in files:
        path = Path(f["path"])
        if f["ext"] in (".bib", ".ris"):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            entries = parse_bibtex(text) if f["ext"] == ".bib" else parse_ris(text)
            for e in entries:
                ops.append({"op": "create", "entity": "paper", "data": {**e, "source": f"file:{f['name']}"}})
        else:
            ops.append({"op": "create", "entity": "paper", "data": {
                "title": title_from_filename(f["name"]), "local_path": f["path"], "source": "folder", "status": "to_read"}})
    return ops


# ---------------------------------------------------------------- BibTeX / RIS
_BIB_ENTRY = re.compile(r"@(\w+)\s*\{\s*([^,\s]*)\s*,", re.S)


def _bib_value(text: str, i: int) -> tuple[str, int]:
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    if i < len(text) and text[i] == "{":
        depth, j = 0, i
        while j < len(text):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    return text[i + 1:j], j + 1
            j += 1
        return text[i + 1:], len(text)
    if i < len(text) and text[i] == '"':
        j = i + 1
        while j < len(text) and not (text[j] == '"' and text[j - 1] != "\\"):
            j += 1
        return text[i + 1:j], j + 1
    m = re.match(r"[^,}\n]*", text[i:])
    return m.group(0).strip(), i + m.end()


def _tidy(value: str) -> str:
    value = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", value)
    value = re.sub(r"\\([&%$#_])", r"\1", value.replace("{", "").replace("}", ""))
    return re.sub(r"\s+", " ", value).strip()


def parse_bibtex(text: str) -> list[dict]:
    out = []
    for m in _BIB_ENTRY.finditer(text):
        kind = m.group(1).lower()
        if kind in ("comment", "string", "preamble"):
            continue
        fields: dict[str, str] = {}
        i = m.end()
        while i < len(text):
            fm = re.match(r"\s*([A-Za-z_][\w-]*)\s*=", text[i:])
            if not fm:
                break
            value, i = _bib_value(text, i + fm.end())
            fields[fm.group(1).lower()] = _tidy(value)
            rest = re.match(r"\s*,?", text[i:])
            i += rest.end()
            if i < len(text) and text[i] == "}":
                break
        if not fields.get("title"):
            continue
        year = re.search(r"\d{4}", fields.get("year", "") or fields.get("date", ""))
        authors = " ; ".join(a.strip() for a in fields.get("author", "").split(" and ") if a.strip())
        out.append({
            "title": fields["title"], "authors": authors, "year": int(year.group(0)) if year else 0,
            "venue": fields.get("journal") or fields.get("booktitle") or fields.get("publisher", ""),
            "doi": fields.get("doi", ""), "url": fields.get("url", ""), "abstract": fields.get("abstract", ""),
            "citekey": m.group(2), "tags": fields.get("keywords", "")[:500], "status": "to_read",
        })
    return out


def parse_ris(text: str) -> list[dict]:
    out, cur = [], {}
    for line in text.splitlines():
        m = re.match(r"^([A-Z][A-Z0-9])  - ?(.*)$", line)
        if not m:
            continue
        tag, value = m.group(1), m.group(2).strip()
        if tag == "TY":
            cur = {"authors": [], "keywords": []}
        elif tag == "ER":
            if cur.get("title"):
                out.append({
                    "title": cur["title"], "authors": " ; ".join(cur["authors"]), "year": cur.get("year", 0),
                    "venue": cur.get("venue", ""), "doi": cur.get("doi", ""), "url": cur.get("url", ""),
                    "abstract": cur.get("abstract", ""), "tags": ", ".join(cur["keywords"])[:500], "status": "to_read",
                })
            cur = {}
        elif cur is not None and "authors" in cur:
            if tag in ("TI", "T1") and not cur.get("title"):
                cur["title"] = value
            elif tag in ("AU", "A1"):
                cur["authors"].append(value)
            elif tag in ("PY", "Y1", "DA"):
                y = re.search(r"\d{4}", value)
                if y and not cur.get("year"):
                    cur["year"] = int(y.group(0))
            elif tag in ("JO", "JF", "T2", "BT") and not cur.get("venue"):
                cur["venue"] = value
            elif tag == "DO":
                cur["doi"] = value
            elif tag == "UR" and not cur.get("url"):
                cur["url"] = value
            elif tag == "AB":
                cur["abstract"] = value
            elif tag == "KW":
                cur["keywords"].append(value)
    return out


_TEX_SPECIAL = re.compile(r"([&%$#_])")


def _tex(value) -> str:
    return _TEX_SPECIAL.sub(r"\\\1", str(value).replace("{", "").replace("}", ""))


def to_bibtex(papers: list[dict]) -> str:
    chunks, used = [], set()
    for n, p in enumerate(papers, 1):
        first = re.sub(r"[^A-Za-z]", "", (p.get("authors") or "").split(";")[0].split(",")[0].split(" ")[-1])
        word = re.sub(r"[^A-Za-z]", "", (p.get("title") or "").split(" ")[0])
        key = p.get("citekey") or (f"{first.lower()}{p.get('year') or ''}{word.lower()}" if first and word else f"ref{p.get('year') or ''}_{p.get('id') or n}")
        key = re.sub(r"[^\w:.-]", "", key) or f"ref{n}"
        base, k = key, 1
        while key in used:
            k += 1
            key = f"{base}{chr(96 + k)}"
        used.add(key)
        authors = " and ".join(a.strip() for a in (p.get("authors") or "").split(";") if a.strip())
        fields = [("title", p.get("title")), ("author", authors), ("year", p.get("year") or ""),
                  ("journal", p.get("venue")), ("doi", p.get("doi")), ("url", p.get("url")),
                  ("abstract", p.get("abstract")), ("keywords", p.get("tags"))]
        body = ",\n".join(f"  {k} = {{{v if k in ('doi', 'url') else _tex(v)}}}" for k, v in fields if v)
        chunks.append(f"@article{{{key},\n{body}\n}}")
    return "\n\n".join(chunks) + "\n"


def _norm_title(title: str) -> str:
    return re.sub(r"[\W_]+", "", (title or "").casefold())


def dedupe(entries: list[dict], papers: list[dict]) -> tuple[list[dict], int]:
    """Drop entries already in the library (or repeated in the batch) by DOI, cite key or title."""
    dois = {p["doi"].lower() for p in papers if p.get("doi")}
    keys = {p["citekey"] for p in papers if p.get("citekey")}
    titles = {_norm_title(p["title"]) for p in papers if p.get("title")}
    paths = {p["local_path"] for p in papers if p.get("local_path")}
    out, skipped = [], 0
    for e in entries:
        doi, key, title = (e.get("doi") or "").lower(), e.get("citekey") or "", _norm_title(e.get("title", ""))
        if (doi and doi in dois) or (key and key in keys) or (title and title in titles) or (e.get("local_path") and e["local_path"] in paths):
            skipped += 1
            continue
        out.append(e)
        dois.add(doi) if doi else None
        keys.add(key) if key else None
        titles.add(title) if title else None
    return out, skipped


# ---------------------------------------------------------------- OpenAlex
def _abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    words = sorted(((pos, w) for w, positions in inv.items() for pos in positions))
    return " ".join(w for _, w in words)[:4000]


def openalex_search(query: str, *, year_from: int = 0, limit: int = 20, mailto: str = "") -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []
    params = {"search": query, "per-page": str(max(1, min(limit, 50)))}
    if year_from:
        params["filter"] = f"from_publication_date:{int(year_from)}-01-01"
    if mailto:
        params["mailto"] = mailto
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "research-hub/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    out = []
    for w in data.get("results", []):
        loc = w.get("primary_location") or {}
        src = loc.get("source") or {}
        authors = " ; ".join((a.get("author") or {}).get("display_name", "") for a in w.get("authorships", [])[:12])
        out.append({
            "title": w.get("display_name") or w.get("title") or "", "authors": authors,
            "year": w.get("publication_year") or 0, "venue": src.get("display_name", "") or "",
            "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
            "url": loc.get("landing_page_url") or w.get("doi") or w.get("id") or "",
            "abstract": _abstract(w.get("abstract_inverted_index")),
            "openalex_id": (w.get("id") or "").rsplit("/", 1)[-1], "cited_by": w.get("cited_by_count", 0),
        })
    return out


# ---------------------------------------------------------------- PaperRead
_ROLE = {"iv": "iv", "dv": "dv", "med": "med", "mod": "mod", "ctrl": "ctrl"}
_STATUS = {"unread": "to_read", "reading": "reading", "organizing": "reading", "done": "done", "paused": "to_read"}


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _text(value, limit: int) -> str:
    """Strings as-is; lists joined with ' ; '; anything else ignored."""
    if isinstance(value, str):
        return value.strip()[:limit]
    if isinstance(value, (list, tuple)):
        return " ; ".join(str(x).strip() for x in value if isinstance(x, (str, int, float)) and str(x).strip())[:limit]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)[:limit]
    return ""


def paperread_items(library: str, skipped: list | None = None) -> list[dict]:
    """Read a PaperRead library folder (read-only). Each paper lives in its own
    folder with paper.json (metadata, extracted variables) and item.json (status).
    Folders whose paper.json is unreadable or malformed are skipped (and listed in
    ``skipped`` when given), never guessed at."""
    root = expand(library)
    if not root.is_dir():
        return []
    out = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or folder.name.startswith(".") or not (folder / "paper.json").exists():
            continue
        paper = _read_json(folder / "paper.json")
        meta = paper.get("meta") if isinstance(paper, dict) else None
        if not isinstance(meta, dict):
            if skipped is not None:
                skipped.append(folder.name)
            continue
        item = _read_json(folder / "item.json")
        item = item if isinstance(item, dict) else {}
        meta = dict(meta)
        override = item.get("meta_override")
        if isinstance(override, dict):
            meta.update({k: v for k, v in override.items() if v})
        year = meta.get("year") or 0
        if not year or not str(year).isdigit():
            m = re.search(r"(19|20)\d{2}", str(meta.get("date", "")))
            year = int(m.group(0)) if m else 0
        raw_vars = paper.get("variables")
        raw_vars = raw_vars.get("items") if isinstance(raw_vars, dict) else raw_vars
        variables = []
        for v in raw_vars if isinstance(raw_vars, list) else []:
            if not isinstance(v, dict):
                continue
            role = _ROLE.get(str(v.get("role", "")).lower())
            en, zh = _text(v.get("en"), 120), _text(v.get("zh"), 80)
            if role and (en or zh):
                variables.append({"role": role, "en": en, "zh": zh, "abbr": _text(v.get("abbr"), 20)})
        tags = item.get("tags")
        tags = [t.strip() for t in tags.split(",")] if isinstance(tags, str) else tags if isinstance(tags, list) else []
        status = item.get("status") if isinstance(item.get("status"), str) else "unread"
        out.append({
            "paperread_id": folder.name,
            "title": _text(meta.get("title_en"), 500) or _text(meta.get("title_zh"), 500) or folder.name,
            "title_zh": _text(meta.get("title_zh"), 500), "authors": _text(meta.get("authors"), 500),
            "year": int(year) if str(year).isdigit() else 0, "venue": _text(meta.get("venue"), 300), "doi": _text(meta.get("doi"), 200),
            "status": _STATUS.get(status, "to_read"),
            "tags": ", ".join(str(t).strip() for t in tags if isinstance(t, (str, int)) and str(t).strip())[:500],
            "variables": variables,
        })
    return out


def paperread_sync_ops(items: list[dict], papers: list[dict], variables: list[dict],
                       links: list[dict] | None = None) -> tuple[list[dict], dict]:
    """Ops that bring PaperRead's library into the hub: new papers, reading-status
    changes, and variables PaperRead extracted, linked to their paper."""
    linked = {(l["variable_id"], l["paper_id"]) for l in links or []}
    by_pr = {p["paperread_id"]: p for p in papers if p.get("paperread_id")}
    by_doi = {p["doi"].lower(): p for p in papers if p.get("doi")}
    known_vars = {(v["name_en"] or "").casefold(): v for v in variables if v.get("name_en")}
    known_vars.update({(v["name_zh"] or "").casefold(): v for v in variables if v.get("name_zh")})
    used_symbols = {v["symbol"] for v in variables}
    counters = {"iv": "X", "dv": "Y", "med": "M", "mod": "Z", "ctrl": "C"}
    ops: list[dict] = []
    stats = {"new": 0, "status": 0, "variables": 0}
    new_vars: dict[str, str] = {}

    def next_symbol(role: str) -> str:
        prefix = counters.get(role, "V")
        n = 1
        while f"{prefix}{n}" in used_symbols:
            n += 1
        used_symbols.add(f"{prefix}{n}")
        return f"{prefix}{n}"

    for i, it in enumerate(items):
        existing = by_pr.get(it["paperread_id"]) or (by_doi.get(it["doi"].lower()) if it.get("doi") else None)
        if existing:
            paper_ref = existing["id"]
            patch = {}
            if not existing.get("paperread_id"):
                patch["paperread_id"] = it["paperread_id"]
            if existing.get("status") != it["status"] and existing.get("status") != "excluded":
                patch["status"] = it["status"]
                stats["status"] += 1
            if patch:
                ops.append({"op": "update", "entity": "paper", "id": existing["id"], "data": patch})
        else:
            ref = f"pr{i}"
            data = {k: it[k] for k in ("title", "authors", "year", "venue", "doi", "status", "tags", "paperread_id")}
            data["source"] = "paperread"
            ops.append({"op": "create", "entity": "paper", "ref": ref, "data": data})
            paper_ref = f"${ref}"
            stats["new"] += 1
        for j, v in enumerate(it["variables"]):
            key = (v["en"] or v["zh"]).casefold()
            if key in known_vars:
                var_ref = known_vars[key]["id"]
            elif key in new_vars:
                var_ref = new_vars[key]
            else:
                ref = f"prv{i}_{j}"
                ops.append({"op": "create", "entity": "variable", "ref": ref, "data": {
                    "symbol": next_symbol(v["role"]), "role": v["role"], "name_en": v["en"], "name_zh": v["zh"],
                    "notes": f"From PaperRead ({v['abbr']})" if v["abbr"] else "From PaperRead"}})
                var_ref = new_vars[key] = f"${ref}"
                stats["variables"] += 1
            if isinstance(var_ref, int) and isinstance(paper_ref, int) and (var_ref, paper_ref) in linked:
                continue  # already linked: keep the user's evidence and note
            # "keep": never overwrite an existing link if one appears before approval
            ops.append({"op": "link", "link": "variable_paper", "a": var_ref, "b": paper_ref, "data": {"evidence": "mentions"}, "keep": True})
    return ops, stats


def paperread_online(url: str) -> bool:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/api/version", timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


# ---------------------------------------------------------------- Python code
def list_scripts(code_dir: str) -> list[dict]:
    root = expand(code_dir)
    if not code_dir or not root.is_dir():
        return []
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in ("__pycache__", "venv", ".venv", "node_modules")]
        for name in sorted(filenames):
            if name.endswith((".py", ".ipynb")):
                full = Path(dirpath) / name
                try:
                    st = full.stat()
                except OSError:
                    continue
                out.append({"path": str(full.resolve()), "rel": str(full.relative_to(root)), "size": st.st_size,
                            "mtime": int(st.st_mtime), "runnable": name.endswith(".py")})
        if len(out) > 500:
            break
    return out


class Runner:
    """Runs one analysis script at a time in its own process; keeps recent runs."""

    def __init__(self):
        self.runs: list[dict] = []
        self.lock = threading.Lock()

    def start(self, script: Path, cwd: Path, timeout: int, on_done) -> dict:
        with self.lock:
            if any(r["state"] == "running" for r in self.runs):
                raise RuntimeError("another script is still running")
            run = {"id": int(time.time() * 1000), "script": str(script), "state": "running", "output": "",
                   "code": None, "started": time.time(), "ended": None}
            self.runs.insert(0, run)
            del self.runs[20:]
        threading.Thread(target=self._run, args=(run, script, cwd, timeout, on_done), daemon=True).start()
        return run

    def _run(self, run, script, cwd, timeout, on_done):
        try:
            proc = subprocess.run([sys.executable, str(script)], cwd=str(cwd), capture_output=True, text=True,
                                  timeout=timeout, env={**os.environ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg"})
            run["output"] = (proc.stdout + ("\n" + proc.stderr if proc.stderr else ""))[-200_000:]
            run["code"] = proc.returncode
            run["state"] = "ok" if proc.returncode == 0 else "failed"
        except subprocess.TimeoutExpired as e:
            out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
            run["output"] = (out + f"\n[timed out after {timeout}s]")[-200_000:]
            run["state"] = "failed"
        except OSError as e:
            run["output"] = str(e)
            run["state"] = "failed"
        run["ended"] = time.time()
        on_done(run)
