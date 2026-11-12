"""Connections to things outside the hub: local reference folders, BibTeX/RIS files,
literature search (OpenAlex, Wiley via Crossref, Semantic Scholar, Web of Science),
the optional AI assistant, and Python analysis scripts.

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
    """Folders whose files the hub may read and serve: reference folders and the code folder."""
    roots = [expand(p) for p in settings.get("reference_folders") or []]
    if settings.get("code_dir"):
        roots.append(expand(settings["code_dir"]))
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


# ---------------------------------------------------------------- auto-archive
def classify(names: list[str], stages: list[dict], rules: list[str] | None = None) -> dict:
    """Pick the pipeline stage a set of uploaded/added files belongs to, from words in
    their names or folders. Custom "keyword => stage_key" rules win over built-ins.
    Returns {"stage_id", "key", "matched": [...]} or {"stage_id": None} when nothing matches."""
    from .defaults import STAGE_KEYWORDS

    by_key = {s["key"]: s for s in stages if s.get("key")}
    table: list[tuple[str, str, int]] = []
    for line in rules or []:
        if "=>" in line:
            word, key = (x.strip() for x in line.split("=>", 1))
            if word and key in by_key:
                table.append((word.casefold(), key, 3))
    for key, words in STAGE_KEYWORDS.items():
        if key in by_key:
            table += [(w.casefold(), key, 1) for w in words]
    scores: dict[str, int] = {}
    matched: dict[str, list[str]] = {}
    for name in names:
        text = str(name).replace("\\", "/").casefold()
        ext = Path(text).suffix
        for word, key, weight in table:
            hit = (ext == word) if word.startswith(".") else (word in text)
            if hit:
                scores[key] = scores.get(key, 0) + weight
                matched.setdefault(key, []).append(word)
    if not scores:
        return {"stage_id": None, "key": None, "matched": []}
    order = {s["key"]: i for i, s in enumerate(stages)}
    best = max(scores, key=lambda k: (scores[k], -order.get(k, 99)))
    return {"stage_id": by_key[best]["id"], "key": best, "matched": sorted(set(matched[best]))}


# ---------------------------------------------------------------- more literature sources
def _get_json(url: str, headers: dict | None = None, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": "research-hub/1.1", "Accept": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _strip_tags(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def crossref_search(query: str, *, year_from: int = 0, limit: int = 20, publisher_member: str = "311", mailto: str = "") -> list[dict]:
    """Crossref works search, filtered to one publisher (311 = Wiley). Free, no key."""
    filters = [f"member:{publisher_member}"] if publisher_member else []
    if year_from:
        filters.append(f"from-pub-date:{int(year_from)}")
    params = {"query": query, "rows": str(max(1, min(limit, 50))),
              "select": "DOI,title,author,issued,container-title,URL,abstract,is-referenced-by-count"}
    if filters:
        params["filter"] = ",".join(filters)
    if mailto:
        params["mailto"] = mailto
    data = _get_json("https://api.crossref.org/works?" + urllib.parse.urlencode(params))
    out = []
    for w in (data.get("message") or {}).get("items", []):
        authors = " ; ".join(", ".join(x for x in (a.get("family"), a.get("given")) if x) for a in (w.get("author") or [])[:12])
        parts = ((w.get("issued") or {}).get("date-parts") or [[0]])[0]
        out.append({"title": _strip_tags((w.get("title") or [""])[0]), "authors": authors, "year": int(parts[0] or 0) if parts else 0,
                    "venue": (w.get("container-title") or [""])[0], "doi": w.get("DOI", ""), "url": w.get("URL", ""),
                    "abstract": _strip_tags(w.get("abstract", ""))[:4000], "cited_by": w.get("is-referenced-by-count", 0)})
    return [r for r in out if r["title"]]


def semantic_search(query: str, *, year_from: int = 0, limit: int = 20) -> list[dict]:
    """Semantic Scholar Graph API search. Free, no key (shared rate limit)."""
    params = {"query": query, "limit": str(max(1, min(limit, 50))),
              "fields": "title,authors,year,venue,externalIds,abstract,url,citationCount"}
    if year_from:
        params["year"] = f"{int(year_from)}-"
    data = _get_json("https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(params))
    out = []
    for w in data.get("data") or []:
        ids = w.get("externalIds") or {}
        out.append({"title": w.get("title") or "", "authors": " ; ".join(a.get("name", "") for a in (w.get("authors") or [])[:12]),
                    "year": w.get("year") or 0, "venue": w.get("venue") or "", "doi": ids.get("DOI", "") or "",
                    "url": w.get("url") or "", "abstract": (w.get("abstract") or "")[:4000], "cited_by": w.get("citationCount") or 0})
    return [r for r in out if r["title"]]


def wos_search(query: str, api_key: str, *, year_from: int = 0, limit: int = 20) -> list[dict]:
    """Clarivate Web of Science Starter API (needs a free/institutional API key)."""
    if not api_key:
        raise ValueError("Web of Science needs an API key (Settings → literature sources)")
    q = f"TS=({query})" + (f" AND PY=({int(year_from)}-2100)" if year_from else "")
    params = {"q": q, "limit": str(max(1, min(limit, 50))), "db": "WOS"}
    data = _get_json("https://api.clarivate.com/apis/wos-starter/v1/documents?" + urllib.parse.urlencode(params), {"X-ApiKey": api_key})
    out = []
    for w in data.get("hits") or []:
        src = w.get("source") or {}
        names = ((w.get("names") or {}).get("authors") or [])[:12]
        ids = w.get("identifiers") or {}
        out.append({"title": w.get("title") or "", "authors": " ; ".join(a.get("displayName") or a.get("wosStandard") or "" for a in names),
                    "year": int(src.get("publishYear") or 0), "venue": src.get("sourceTitle") or "", "doi": ids.get("doi") or "",
                    "url": (w.get("links") or {}).get("record") or "", "abstract": "", "cited_by": 0})
    return [r for r in out if r["title"]]


def search(provider: str, query: str, settings: dict, *, year_from: int = 0, limit: int = 20) -> list[dict]:
    """One entry point for every automatic literature source."""
    if provider == "openalex":
        results = openalex_search(query, year_from=year_from, limit=limit, mailto=settings.get("openalex_mailto", ""))
    elif provider == "wiley":
        results = crossref_search(query, year_from=year_from, limit=limit, mailto=settings.get("openalex_mailto", ""))
    elif provider == "semantic":
        results = semantic_search(query, year_from=year_from, limit=limit)
    elif provider == "wos":
        results = wos_search(query, settings.get("wos_api_key", ""), year_from=year_from, limit=limit)
    else:
        raise ValueError(f"unknown literature source {provider}")
    for r in results:
        r["provider"] = provider
    return results


# ---------------------------------------------------------------- optional AI assistant
def ai_config(settings: dict) -> dict | None:
    from .defaults import AI_PRESETS

    provider = settings.get("ai_provider") or ""
    if not provider:
        return None
    preset = AI_PRESETS.get(provider, {})
    base = (settings.get("ai_base_url") or preset.get("base_url") or "").rstrip("/")
    model = settings.get("ai_model") or preset.get("model") or ""
    if not base or not model:
        return None
    if provider != "ollama" and not settings.get("ai_api_key"):
        return None
    return {"provider": provider, "base_url": base, "model": model, "key": settings.get("ai_api_key", "")}


def ai_chat(cfg: dict, system: str, user: str, *, timeout: int = 60) -> tuple[str, int]:
    """One chat completion against an OpenAI-compatible endpoint. Returns (text, tokens used)."""
    body = json.dumps({"model": cfg["model"], "temperature": 0.2,
                       "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "research-hub/1.1"}
    if cfg.get("key"):
        headers["Authorization"] = f"Bearer {cfg['key']}"
    req = urllib.request.Request(cfg["base_url"] + "/chat/completions", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    tokens = int((data.get("usage") or {}).get("total_tokens") or (len(system) + len(user) + len(text)) // 3)
    return text, tokens


def parse_json_block(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def checkin_prompt(stage: dict, tasks: list[dict], note: str, files: list[str], context: dict) -> tuple[str, str]:
    system = ("You help a graduate student track thesis progress. Read their progress note and the files they uploaded, "
              "then reply with ONE JSON object only: {\"progress\": 0-100 integer for this stage, "
              "\"done_task_ids\": [ids of listed tasks the note shows are finished], "
              "\"query\": \"4-8 English keywords for finding related recent papers\", "
              "\"summary\": \"one sentence, in the language of the note, saying where the stage stands\"}. "
              "Never invent task ids. Be conservative with progress.")
    lines = [f"Stage: {stage.get('title_zh')} / {stage.get('title_en')} (current progress {stage.get('progress')}%)",
             f"Stage goal: {stage.get('goal') or '-'}", "Tasks:"]
    lines += [f"  [{ 'x' if t['done'] else ' ' }] id={t['id']} {t['title']}" for t in tasks] or ["  (none)"]
    lines += [f"Uploaded files: {', '.join(files) or '-'}", f"Project: {context.get('title', '')}",
              f"Research questions: {'; '.join(context.get('rqs', [])) or '-'}",
              f"Variables: {', '.join(context.get('variables', [])) or '-'}", "", "Progress note:", note]
    return system, "\n".join(lines)


def default_query(stage: dict, note: str, context: dict) -> str:
    """Keywords for literature tracking when no AI is configured: English variable names,
    then English words from the note, then the stage title."""
    words = [v for v in context.get("variables_en", []) if v][:4]
    if len(words) < 3:
        latin = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", note or "")
        stop = {"this", "that", "with", "from", "have", "been", "will", "into", "about", "draft", "done", "chapter"}
        words += [w for w in latin if w.casefold() not in stop][: 6 - len(words)]
    if not words and context.get("title"):
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", context["title"]) if w.casefold() != "research"]
    return " ".join(dict.fromkeys(words))[:200] or (stage.get("title_en") or "")


# ---------------------------------------------------------------- research model from the user's own writing
def read_pdf(data: bytes) -> str:
    """Text of a PDF. Uses ``pdftotext`` (Poppler) when it is installed; otherwise a small built-in reader
    that handles simple text PDFs. Scanned or CJK-subset PDFs need pdftotext or a .docx/.txt copy."""
    import shutil
    import subprocess
    import zlib
    exe = shutil.which("pdftotext")
    if exe:
        try:
            done = subprocess.run([exe, "-enc", "UTF-8", "-q", "-", "-"], input=data, capture_output=True, timeout=60)
            text = done.stdout.decode("utf-8", errors="replace")
            if len(text.strip()) > 200:
                return text
        except (OSError, subprocess.SubprocessError):
            pass
    chunks = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
        raw = m.group(1)
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            pass
        for block in re.findall(rb"BT(.*?)ET", raw, re.S):
            parts = re.findall(rb"\((?:\\.|[^\\()])*\)", block)
            line = b"".join(re.sub(rb"\\([()\\])", rb"\1", part[1:-1]) for part in parts)
            if line.strip():
                chunks.append(line.decode("latin-1", errors="replace"))
    text = "\n".join(chunks)
    if len(re.findall(r"[A-Za-z]{3,}", text)) < 80:
        raise ValueError("could not read the text of this PDF — install pdftotext (Poppler), or save it as .docx or .txt")
    return text


def read_document(data: bytes, name: str) -> str:
    """Plain text from an uploaded draft: .docx, .pdf, .txt, .md, .tex (and similar text files)."""
    ext = Path(name or "").suffix.lower()
    if ext == ".docx":
        import html
        import io
        import zipfile
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                xml = z.read("word/document.xml").decode("utf-8", errors="replace")
        except (zipfile.BadZipFile, KeyError):
            raise ValueError("could not read this .docx file") from None
        xml = re.sub(r"</w:p>|<w:br[^>]*/>|<w:tab[^>]*/>", "\n", xml)
        return html.unescape(re.sub(r"<[^>]+>", "", xml))[:400_000]
    if ext == ".pdf":
        return read_pdf(data)[:400_000]
    if ext in (".doc", ".pages", ".odt"):
        raise ValueError(f"{ext} is not supported — save it as .docx or paste the text")
    for enc in ("utf-8", "cp950", "big5", "utf-16"):
        try:
            return data.decode(enc)[:400_000]
        except UnicodeDecodeError:
            continue
    raise ValueError("could not read the text of this file")


_CJK = re.compile(r"[㐀-鿿]")
_LABEL = re.compile(r"^\s*(?:(?:研究)?假設\s*([一二三四五六七八九十]+|\d+)\s*([a-zA-Z]?)|H\s*(\d+)\s*([a-zA-Z]?))\s*[:：.、)）]?\s*", re.I)
_ZH_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
_SIGN = {"positive": "+", "positively": "+", "正向": "+", "正面": "+", "negative": "-", "negatively": "-", "負向": "-", "負面": "-"}
_V = r"(?P<{0}>[^，,。；;：:]{{1,60}}?)"
_VE = r"(?P<{0}>[^，,。；;：:]{{1,60}})$"  # a variable that ends the sentence: take all of it
_VG = r"(?P<{0}>[^，,。；;：:]{{1,60}})"  # greedy: split at the LAST verb, so names may contain 影響
_REL_EN = r"(?:positive\s+|negative\s+|significant\s+)?(?:relationship|relation|effect|association|link|impact|influence)s?"
_PATTERNS = [
    # mediation / moderation first: they also contain effect words
    ("mediates", re.compile(_V.format("m") + r"\s+(?:significantly\s+|partially\s+|fully\s+)?mediates?\s+the\s+" + _REL_EN + r"\s+(?:between|of)\s+" + _V.format("x") + r"\s+(?:and|on|with)\s+" + _V.format("y") + r"\s*$", re.I)),
    ("moderates", re.compile(_V.format("z") + r"\s+(?:significantly\s+|positively\s+|negatively\s+)?(?:moderates?|strengthens|weakens)\s+the\s+" + _REL_EN + r"\s+(?:between|of)\s+" + _V.format("x") + r"\s+(?:and|on|with)\s+" + _V.format("y") + r"\s*$", re.I)),
    ("mediates", re.compile(_V.format("m") + r"(?:在|於)" + _V.format("x") + r"(?:對|與|和)" + _V.format("y") + r"(?:之間|間)?(?:的)?(?:關係|影響|關聯)?(?:中)?(?:具有|有|扮演|存在|具)?(?:顯著|部分|完全)?(?:的)?中介")),
    ("moderates", re.compile(_V.format("z") + r"(?:在|於)" + _V.format("x") + r"(?:對|與|和)" + _V.format("y") + r"(?:之間|間)?(?:的)?(?:關係|影響|關聯)?(?:中)?(?:具有|有|扮演|存在|具)?(?:顯著)?(?:的)?(?:正向|負向)?(?:調節|干擾)")),
    ("moderates", re.compile(_V.format("z") + r"(?:會|將|能)?(?:顯著)?(?:正向|負向)?(?:調節|干擾)(?:了)?" + _V.format("x") + r"(?:對|與|和)" + _V.format("y") + r"(?:之間)?(?:的)?(?:關係|影響|效果|關聯)")),
    ("mediates", re.compile(_V.format("m") + r"(?:會|將|能)?(?:中介)(?:了)?" + _V.format("x") + r"(?:對|與|和)" + _V.format("y") + r"(?:之間)?(?:的)?(?:關係|影響|效果|關聯)")),
    ("effect", re.compile(_V.format("x") + r"\s+(?:will\s+|would\s+|should\s+)?(?:has|have|had|exerts?|shows?)\s+(?:a\s+|an\s+)?(?:significant(?:ly)?\s+)?(?P<sign>positive|negative)?\s*(?:and\s+significant\s+)?(?:effect|influence|impact)s?\s+on\s+" + _V.format("y") + r"\s*$", re.I)),
    ("effect", re.compile(_V.format("x") + r"\s+(?:will\s+|would\s+|should\s+)?(?:is\s+|are\s+)?(?P<sign>positively|negatively)?\s*(?:and\s+)?(?:significantly\s+)?(?:affects?|influences?|predicts?|impacts?|increases?|decreases?|reduces?|(?:related|associated)\s+(?:to|with))\s+" + _V.format("y") + r"\s*$", re.I)),
    ("effect", re.compile(_V.format("x") + r"(?:會|將|能|可)?(?:對|與)" + _V.format("y") + r"(?:有|具有|呈|產生|具|存在)?(?:顯著)?(?:的)?(?P<sign>正向|負向|正面|負面)?(?:且)?(?:顯著)?(?:的)?(?:影響|效果|關聯|相關)")),
    ("effect", re.compile(_VG.format("x") + r"(?:會|將|能|可)?(?:顯著)?(?:地)?(?P<sign>正向|負向|正面|負面)(?:且顯著)?(?:地)?(?:影響|預測)" + _VE.format("y"))),
    ("effect", re.compile(_VG.format("x") + r"(?:影響|預測)" + _VE.format("y"))),
]
_TRIM = re.compile(r"^(?:(?:the|a|an)\s+|本研究|研究|假設|則|而|且|即)|(?:\s+(?:will|would|is|are|can)|會|將|的|之|了|顯著|地)$", re.I)


def _clean_var(name: str) -> str:
    name = re.sub(r"[\s　]+", " ", name or "").strip(" \t\"'“”「」『』()（）.。、")
    for _ in range(3):
        name = _TRIM.sub("", name).strip(" .。、")
    return name[:60]


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。；;！？!?])|\n+|(?<=\.)\s+(?=[A-Z(\[]|H\d)", text or "")
    return [p.strip() for p in parts if p and 4 <= len(p.strip()) <= 400]


def _label(sentence: str) -> tuple[str, str]:
    m = _LABEL.match(sentence)
    if not m:
        return "", sentence
    if m.group(1):
        num = m.group(1)
        num = str(_ZH_NUM.get(num, num)) if not num.isdigit() else num
        label = f"H{num}{(m.group(2) or '').lower()}"
    else:
        label = f"H{m.group(3)}{(m.group(4) or '').lower()}"
    return label, sentence[m.end():]


def extract_framework_rules(text: str) -> dict:
    """Find hypothesised paths in the user's own writing without any AI: sentences like
    "H1: Perceived usefulness positively affects intention", "知覺易用性對使用意圖有正向影響",
    "信任調節知覺有用性與使用意圖之間的關係", "Attitude mediates the relationship between X and Y"."""
    raw_vars: dict[str, dict] = {}
    relations: list[dict] = []
    matched: list[str] = []

    def var(name: str, role_hint: str = "") -> str | None:
        name = _clean_var(name)
        if not name or len(name) > 60:
            return None
        key = re.sub(r"\s+", "", name).casefold()
        v = raw_vars.setdefault(key, {"key": key, "name": name, "hint": "", "src": 0, "dst": 0})
        if role_hint and not v["hint"]:
            v["hint"] = role_hint
        return key

    def effect(x, y, sign="", label="") -> int | None:
        if not x or not y or x == y:
            return None
        for i, r in enumerate(relations):
            if r["kind"] == "effect" and r["source"] == x and r["target"] == y:
                if label and not r["label"]:
                    r["label"] = label
                if sign and not r["sign"]:
                    r["sign"] = sign
                return i
        relations.append({"source": x, "target": y, "kind": "effect", "sign": sign, "label": label, "moderates": None})
        raw_vars[x]["src"] += 1
        raw_vars[y]["dst"] += 1
        return len(relations) - 1

    for sentence in _sentences(text):
        label, body = _label(sentence)
        body = body.strip().rstrip("。.;；")
        for kind, pattern in _PATTERNS:
            m = pattern.search(body)
            if not m:
                continue
            g = m.groupdict()
            sign = _SIGN.get((g.get("sign") or "").lower(), "")
            if not sign and re.search(r"正向|positive|strengthen", body, re.I):
                sign = "+"
            elif not sign and re.search(r"負向|negative|weaken", body, re.I):
                sign = "-"
            if kind == "effect":
                ok = effect(var(g["x"]), var(g["y"]), sign, label) is not None
            elif kind == "mediates":
                x, med, y = var(g["x"]), var(g["m"], "med"), var(g["y"])
                ok = bool(x and med and y) and effect(x, med, "", label) is not None and effect(med, y, "", label) is not None
            else:
                x, z, y = var(g["x"]), var(g["z"], "mod"), var(g["y"])
                base = effect(x, y) if x and y else None
                ok = base is not None and z is not None and z not in (x, y)
                if ok:
                    relations.append({"source": z, "target": y, "kind": "moderates", "sign": sign, "label": label, "moderates": base})
            if ok:
                matched.append(sentence[:300])
                break
    return _finish_framework(raw_vars, relations, matched, "rules")


def _finish_framework(raw_vars: dict, relations: list[dict], matched: list[str], method: str) -> dict:
    """Assign roles (X sources, Y outcomes, M in between, Z moderators) and symbols."""
    counters = {"iv": "X", "dv": "Y", "med": "M", "mod": "Z", "ctrl": "C", "other": "V"}
    used: dict[str, int] = {}
    out_vars = []
    for v in raw_vars.values():
        role = v.get("role") or v.get("hint") or ""
        if role not in counters:
            role = "med" if v["src"] and v["dst"] else "iv" if v["src"] else "dv" if v["dst"] else "other"
        if role in ("iv", "dv") and v["src"] and v["dst"] and not v.get("role"):
            role = "med"
        used[role] = used.get(role, 0) + 1
        name = v["name"]
        cjk = bool(_CJK.search(name))
        out_vars.append({"key": v["key"], "symbol": f"{counters[role]}{used[role]}", "role": role,
                         "name_zh": v.get("name_zh") or (name if cjk else ""), "name_en": v.get("name_en") or ("" if cjk else name),
                         "definition": v.get("definition", "")})
    order = {"iv": 0, "med": 1, "mod": 2, "dv": 3, "ctrl": 4, "other": 5}
    out_vars.sort(key=lambda v: (order[v["role"]], v["symbol"]))
    return {"variables": out_vars, "relations": relations, "sentences": matched, "method": method}


def framework_prompt(text: str) -> tuple[str, str]:
    system = ("You read a graduate student's own draft (any language) and extract its research model. Reply with ONE JSON object only: "
              "{\"variables\": [{\"key\": short id, \"role\": \"iv|dv|med|mod|ctrl\", \"name_zh\": Chinese name or \"\", "
              "\"name_en\": English name or \"\", \"definition\": one short sentence or \"\"}], "
              "\"relations\": [{\"source\": key, \"target\": key, \"kind\": \"effect\" or \"moderates\", \"sign\": \"+\", \"-\" or \"\", "
              "\"label\": hypothesis label like \"H1\" or \"\", \"moderates_source\": key, \"moderates_target\": key}]}. "
              "For a moderator, give kind \"moderates\" with source = the moderator and moderates_source/moderates_target = the path it moderates. "
              "For a mediator, give the two effect paths through it. Use only variables the text actually names; never invent hypotheses.")
    return system, "Draft:\n" + text[:20000]


def normalize_framework(raw: dict, method: str = "ai") -> dict:
    """Make an AI answer safe and shaped like the rule-based result."""
    raw_vars: dict[str, dict] = {}
    for v in (raw.get("variables") or [])[:40]:
        if not isinstance(v, dict):
            continue
        key = str(v.get("key") or v.get("name_en") or v.get("name_zh") or "").strip()[:60]
        name_zh, name_en = _clean_var(str(v.get("name_zh") or "")), _clean_var(str(v.get("name_en") or ""))
        if not key or not (name_zh or name_en):
            continue
        role = str(v.get("role") or "").lower()
        raw_vars[key] = {"key": key, "name": name_zh or name_en, "name_zh": name_zh, "name_en": name_en,
                         "role": role if role in ("iv", "dv", "med", "mod", "ctrl") else "", "hint": "",
                         "definition": str(v.get("definition") or "")[:500], "src": 0, "dst": 0}
    relations: list[dict] = []
    pending_mod = []
    for r in (raw.get("relations") or [])[:80]:
        if not isinstance(r, dict):
            continue
        s, t = str(r.get("source") or ""), str(r.get("target") or "")
        kind = "moderates" if str(r.get("kind")) == "moderates" else "effect"
        sign = r.get("sign") if r.get("sign") in ("+", "-") else ""
        label = str(r.get("label") or "")[:12]
        if kind == "moderates":
            pending_mod.append((s, str(r.get("moderates_source") or ""), str(r.get("moderates_target") or t), sign, label))
            continue
        if s in raw_vars and t in raw_vars and s != t:
            relations.append({"source": s, "target": t, "kind": "effect", "sign": sign, "label": label, "moderates": None})
            raw_vars[s]["src"] += 1
            raw_vars[t]["dst"] += 1
    for z, x, y, sign, label in pending_mod:
        if z not in raw_vars:
            continue
        base = next((i for i, r in enumerate(relations) if r["source"] == x and r["target"] == y), None)
        if base is None and x in raw_vars and y in raw_vars and x != y:
            relations.append({"source": x, "target": y, "kind": "effect", "sign": "", "label": "", "moderates": None})
            base = len(relations) - 1
        if base is not None:
            relations.append({"source": z, "target": relations[base]["target"], "kind": "moderates", "sign": sign, "label": label, "moderates": base})
            raw_vars[z]["role"] = raw_vars[z]["role"] or "mod"
    return _finish_framework(raw_vars, relations, [], method)
