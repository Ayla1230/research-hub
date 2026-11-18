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
    req = urllib.request.Request(url, headers={"User-Agent": "research-hub/1.2", "Accept": "application/json"})
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
    req = urllib.request.Request(url, headers={"User-Agent": "research-hub/1.2", "Accept": "application/json", **(headers or {})})
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
    headers = {"Content-Type": "application/json", "User-Agent": "research-hub/1.2"}
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
    """Text of a PDF. Uses ``pdftotext`` (Poppler) when it is installed; otherwise the built-in reader
    (research_hub.pdftext), which also reads Chinese. Scanned PDFs have no text to read."""
    import shutil
    import subprocess
    exe = shutil.which("pdftotext")
    if exe:
        try:
            done = subprocess.run([exe, "-enc", "UTF-8", "-q", "-", "-"], input=data, capture_output=True, timeout=60)
            text = done.stdout.decode("utf-8", errors="replace")
            if len(text.strip()) > 200:
                return text
        except (OSError, subprocess.SubprocessError):
            pass
    from . import pdftext
    try:
        text = pdftext.extract(data)
    except Exception:  # a malformed file must not take the server down
        text = ""
    if len(re.findall(r"[A-Za-z]{3,}|[\u3400-\u9fff]", text)) < 40:
        raise ValueError("this PDF has no readable text (it is probably scanned images) — use the .docx file or a text PDF")
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
_TRIM = re.compile(r"^(?:(?:the|a|an)\s+|本研究|本文|研究|假設|則|而|且|即|旨在|目的在於|目的為|主要|探討|分析|檢驗|驗證|了解|瞭解|探究|檢視|以及|並)|(?:\s+(?:will|would|is|are|can)|會|將|的|之|了|顯著|地)$", re.I)


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


# ---- a research model from the title or purpose statement, when no hypothesis sentences are written yet
_T_SPLIT = re.compile(r"\s*(?:、|,|，|與|和|及|以及|\band\b|&)\s*", re.I)
_T_TAIL = r"(?:之|的)?(?:影響|關係|關聯|效果|效應)(?:之研究|研究|之探討|探討|分析)?"
_TITLE_ZH = [
    re.compile(r"(?P<x>[^：:，,。]{2,40}?)對(?P<y>[^：:，,。]{2,40}?)" + _T_TAIL),
    re.compile(r"(?P<x>[^：:，,。]{2,40}?)(?:如何|是否)(?:會)?(?:影響|提升|降低|促進|預測)(?P<y>[^：:，,。？?]{2,40})"),
    re.compile(r"(?P<x>[^：:，,。對]{2,40}?)(?:影響|預測|提升|促進)(?P<y>[^：:，,。]{2,30}?)(?:之研究|的研究|之探討|之實證)"),
    re.compile(r"(?P<y>[^：:，,。]{2,30}?)(?:之|的)(?:影響因素|前因|決定因素)(?:之研究|研究|探討)?[：:—–-]\s*(?P<x>[^：:。]{2,60})"),
    re.compile(r"(?P<x>[^：:，,。與和]{2,30}?)(?:與|和)(?P<y>[^：:，,。]{2,30}?)(?:之|的)?(?:關係|關聯)(?:之研究|研究)?"),
]
_TITLE_EN = [
    re.compile(r"(?:effects?|impacts?|influences?|roles?)\s+of\s+(?P<x>[^:;.]{2,80}?)\s+on\s+(?P<y>[^:;.,]{2,80})", re.I),
    re.compile(r"(?:relationships?|links?|associations?)\s+between\s+(?P<x>[^:;.]{2,80}?)\s+and\s+(?P<y>[^:;.,]{2,80})", re.I),
    re.compile(r"(?:how|whether|does|do)\s+(?P<x>[^:;.?]{2,80}?)\s+(?:affects?|influences?|shapes?|predicts?|drives?)\s+(?P<y>[^:;.,?]{2,80})", re.I),
]
_THIRD_ZH = re.compile(r"(?P<v>[^：:，,。對]{2,30}?)(?:對|在)(?P<x>[^：:，,。與和]{2,30}?)(?:與|和|對)(?P<y>[^：:，,。]{2,30}?)(?:之間|間)?(?:的|之)?(?:關係|影響|關聯)"
                       r"(?:中)?(?:之|的)?(?P<kind>調節|干擾|中介)(?:效果|角色|作用|效應)")
_MED_ZH = [re.compile(r"以(?P<v>[^：:，,。]{2,30}?)為中介"), re.compile(r"(?P<v>[^：:，,。之的對]{2,30}?)(?:之|的)中介(?:效果|角色|作用|效應)")]
_MOD_ZH = [re.compile(r"以(?P<v>[^：:，,。]{2,30}?)為(?:調節|干擾)"), re.compile(r"(?P<v>[^：:，,。之的對]{2,30}?)(?:之|的)(?:調節|干擾)(?:效果|角色|作用|效應)")]
_MED_EN = [re.compile(r"mediat(?:ing|ed)\s+(?:roles?|effects?)?\s*(?:of|by)\s+(?P<v>[^:;.,]{2,60})", re.I), re.compile(r"(?P<v>[A-Za-z][A-Za-z \-]{2,50}?)\s+as\s+(?:a\s+)?mediator", re.I)]
_MOD_EN = [re.compile(r"moderat(?:ing|ed)\s+(?:roles?|effects?)?\s*(?:of|by)\s+(?P<v>[^:;.,]{2,60})", re.I), re.compile(r"(?P<v>[A-Za-z][A-Za-z \-]{2,50}?)\s+as\s+(?:a\s+)?moderator", re.I)]
_PURPOSE = re.compile(r"本研究|本文|旨在|目的|探討|this (?:study|paper|research|thesis)|we (?:examine|investigate|explore|test)|aims? to", re.I)
_CASE = re.compile(r"[：:—–-]\s*以.{1,30}為例\s*$|\s*[：:]\s*(?:evidence|a (?:case )?study|an? (?:empirical )?(?:analysis|investigation)).*$", re.I)


def _title_model(line: str) -> dict | None:
    """Variables and paths implied by one title or purpose sentence, e.g. 「A 對 B 之影響：以 C 為中介變數」."""
    zh = bool(_CJK.search(line))
    text = _CASE.sub("", line.strip())
    clean = lambda v: _clean_var(re.sub(r"(?:變數|變項|的角色|為例)$", "", v.strip()))  # noqa: E731
    third = _THIRD_ZH.search(text) if zh else None
    if third:  # 「Z 對 X 與 Y 關係之調節效果」: the first term is the moderator or mediator
        x, y, v = clean(third.group("x")), clean(third.group("y")), clean(third.group("v"))
        if x and y and v:
            role = "mod" if third.group("kind") in ("調節", "干擾") else "med"
            return {"xs": [x], "ys": [y], "med": v if role == "med" else "", "mod": v if role == "mod" else "", "line": line.strip()[:300]}
    med = next((m.group("v") for p in (_MED_ZH if zh else _MED_EN) for m in [p.search(text)] if m), "")
    mod = next((m.group("v") for p in (_MOD_ZH if zh else _MOD_EN) for m in [p.search(text)] if m), "")
    head = re.split(r"[：:—–]|\s-\s", text)[0] if (med or mod) else text
    hit = next((m for p in (_TITLE_ZH if zh else _TITLE_EN) for m in [p.search(head) or p.search(text)] if m), None)
    if not hit:
        return None
    xs = [clean(v) for v in _T_SPLIT.split(hit.group("x")) if clean(v)]
    ys = [clean(v) for v in _T_SPLIT.split(hit.group("y")) if clean(v)]
    med, mod = clean(med), clean(mod)
    xs = [v for v in xs if v not in (med, mod)][:4]
    ys = [v for v in ys if v not in (med, mod) and v not in xs][:2]
    if not xs or not ys or any(len(v) > 40 for v in xs + ys):
        return None
    return {"xs": xs, "ys": ys, "med": med, "mod": mod, "line": line.strip()[:300]}


_NOISE = re.compile(r"[0-9（）()\[\]「」『』%]|^(?:也|並|而|且|及|與|和|在|於|對|為|其|此|該|這|那|將|會|可|能|所|以|從|由|把|被|讓|使)|(?:與|和|及|的|之|對|於|在|為|也|並|等|中|上|下)$"
                    r"|角色|過程|研究|結果|方面|部分|情形|情況|問題|理論|文獻|學者|本文|整理|探討|分析|\b(?:and|or|the|this|that|these|which|study|paper|et al)\b", re.I)


def _credible(found: dict, text: str) -> dict:
    """Sentences without a hypothesis number match a lot of ordinary prose in a long document. Keep a path
    only when both ends look like construct names and are used repeatedly in the text."""
    if not found["relations"]:
        return found
    low = text.casefold()
    need = 1 if len(text) < 1500 else 3

    def ok(v: dict) -> bool:
        name = v.get("name_zh") or v.get("name_en") or ""
        size_ok = 2 <= len(name) <= 12 if _CJK.search(name) else 1 <= len(name.split()) <= 4
        return size_ok and not _NOISE.search(name) and low.count(name.casefold()) >= need

    good = {v["key"] for v in found["variables"] if ok(v)}
    index, relations = {}, []
    for i, r in enumerate(found["relations"]):
        if r["source"] in good and r["target"] in good and (r["kind"] != "moderates" or r.get("moderates") in index):
            index[i] = len(relations)
            relations.append({**r, "moderates": index.get(r.get("moderates")) if r["kind"] == "moderates" else None})
    used = {k for r in relations for k in (r["source"], r["target"])}
    return {**found, "variables": [v for v in found["variables"] if v["key"] in used], "relations": relations[:12],
            "sentences": found.get("sentences", []) if relations else []}


def infer_framework(text: str, title: str = "") -> dict:
    """A research model from a document even when it has no hypothesis sentences: first the written
    hypotheses, then the title and purpose statements. ``method`` says which one produced the result."""
    found = extract_framework_rules(text)
    if any(r.get("label") for r in found["relations"]):
        return found  # numbered hypotheses (H1, 假設一) are the author's own statement of the model
    found = _credible(found, text)
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    titles = ([title] if title else []) + [ln for ln in lines[:12] if len(ln) <= 90 and "。" not in ln and not ln.endswith((".", "；", ";"))]
    model = next((m for m in map(_title_model, titles) if m), None)
    if not model and found["relations"]:
        return found  # plain sentences such as 「A 對 B 有正向影響」
    if not model:
        model = next((m for m in map(_title_model, [s for s in _sentences(text[:30000]) if _PURPOSE.search(s)][:20]) if m), None)
    if not model:
        roles = _role_statements(text)
        if roles.get("iv") and roles.get("dv"):  # 「以 A 為自變數、B 為依變數」 in the method chapter
            model = {"xs": roles["iv"], "ys": roles["dv"][:2], "med": (roles.get("med") or [""])[0], "mod": (roles.get("mod") or [""])[0],
                     "line": "；".join(f"{k}: {'、'.join(v)}" for k, v in roles.items())[:300], "ctrl": roles.get("ctrl", [])}
    if not model:
        return {**found, "method": "none"}
    raw_vars: dict[str, dict] = {}
    relations: list[dict] = []

    def var(name: str, role: str) -> str:
        key = re.sub(r"\s+", "", name).casefold()
        raw_vars.setdefault(key, {"key": key, "name": name, "hint": role, "role": role, "src": 0, "dst": 0})
        return key

    def edge(a: str, b: str) -> int:
        relations.append({"source": a, "target": b, "kind": "effect", "sign": "", "label": "", "moderates": None})
        raw_vars[a]["src"] += 1
        raw_vars[b]["dst"] += 1
        return len(relations) - 1

    xs = [var(v, "iv") for v in model["xs"]]
    ys = [var(v, "dv") for v in model["ys"]]
    med = var(model["med"], "med") if model["med"] else None
    direct = [edge(x, y) for x in xs for y in ys]
    if med:
        for x in xs:
            edge(x, med)
        for y in ys:
            edge(med, y)
    if model["mod"]:
        z = var(model["mod"], "mod")
        relations.append({"source": z, "target": ys[0], "kind": "moderates", "sign": "", "label": "", "moderates": direct[0]})
    for name in model.get("ctrl", []):
        var(name, "ctrl")
    for i, r in enumerate(relations, 1):
        r["label"] = f"H{i}"
    return _finish_framework(raw_vars, relations, [model["line"]], "roles" if "ctrl" in model else "title")


_ROLE_ZH = [("iv", r"自變(?:數|項)|前因變(?:數|項)|預測變(?:數|項)"), ("dv", r"依變(?:數|項)|應變(?:數|項)|結果變(?:數|項)|效標變(?:數|項)"),
            ("med", r"中介變(?:數|項)"), ("mod", r"調節變(?:數|項)|干擾變(?:數|項)"), ("ctrl", r"控制變(?:數|項)")]
_ROLE_EN = [("iv", r"independent variables?|predictors?"), ("dv", r"(?<!in)dependent variables?|outcome variables?|criterion variables?"),
            ("med", r"mediators?|mediating variables?"), ("mod", r"moderators?|moderating variables?"), ("ctrl", r"control variables?")]
_NAME = r"([^，,。；;：:（）()為是]{2,40})"


def _role_statements(text: str) -> dict[str, list[str]]:
    """Variables the author names by role: 「以 A 為自變數」「依變數為 B」 "the dependent variable is B"."""
    roles: dict[str, list[str]] = {}

    def add(role: str, raw: str):
        for part in _T_SPLIT.split(raw):
            name = _clean_var(re.sub(r"^(?:本研究|分別|包括|包含|則|以)|(?:等|作|做)$", "", part.strip()))
            if 2 <= len(name) <= 30 and not any(name in names for names in roles.values()) and not re.search(r"變(?:數|項)|variable", name, re.I):
                roles.setdefault(role, [])
                roles[role].append(name)

    for sentence in _sentences(text[:200000]):
        for role, word in _ROLE_ZH:
            for m in re.finditer(r"以([^，,。；;：:（）()]{2,40}?)(?:作)?為(?:本研究之|本研究的)?(?:" + word + r")", sentence):
                add(role, m.group(1))
            for m in re.finditer(r"(?:" + word + r")(?:則)?(?:為|是|包括|包含|有|：|:)" + _NAME, sentence):
                add(role, m.group(1))
        for role, word in _ROLE_EN:
            for m in re.finditer(r"(?:the\s+)?(?:" + word + r")\s+(?:is|are|was|were|include[sd]?)\s+([A-Za-z][A-Za-z ,\-]{2,80}?)(?:[.;]|,\s+(?:and|while|whereas)\b|$)", sentence, re.I):
                add(role, m.group(1))
            for m in re.finditer(r"([A-Za-z][A-Za-z \-]{2,50}?)\s+(?:is|are|was|were|serves?)\s+(?:treated\s+|used\s+)?as\s+(?:the\s+|an?\s+)?(?:" + word + r")", sentence, re.I):
                add(role, m.group(1))
    return {k: v[:4] for k, v in roles.items() if v}


_POS = re.compile(r"正向|正相關|正面|提升|提高|增加|增進|促進|強化|有助於|positive(?:ly)?|increas|enhanc|improv|promot|strengthen|foster", re.I)
_NEG = re.compile(r"負向|負相關|負面|降低|減少|減低|抑制|削弱|阻礙|negative(?:ly)?|decreas|reduc|lower|weaken|undermin|inhibit", re.I)


def infer_signs(found: dict, text: str) -> int:
    """Fill in + / - for paths that have none, from sentences that mention both variables. Returns how many."""
    names = {v["key"]: (v.get("name_zh") or v.get("name_en") or "") for v in found.get("variables", [])}
    sentences = _sentences(text[:300000])
    filled = 0
    for r in found.get("relations", []):
        if r.get("sign") or r["kind"] != "effect":
            continue
        a, b = names.get(r["source"], ""), names.get(r["target"], "")
        if not a or not b:
            continue
        pos = neg = 0
        for s in sentences:
            low = s.casefold()
            ia, ib = low.find(a.casefold()), low.find(b.casefold())
            if ia < 0 or ib < 0 or ia > ib:
                continue  # only "A … B" order says something about A's effect on B
            between = s[ia: ib + len(b) + 12]
            pos += len(_POS.findall(between))
            neg += len(_NEG.findall(between))
        if pos + neg and (pos >= 2 * neg + 1 or neg >= 2 * pos + 1):
            r["sign"] = "+" if pos > neg else "-"
            filled += 1
    return filled


_STORY_CUES = {
    "common": r"近年來|近年|隨著|長期以來|過去研究|既有研究|先前研究|已知|普遍認為|in recent years|recently|over the past|prior research|previous (?:research|studies)|it is well (?:known|established)|scholars have",
    "complication": r"然而|但是|不過|儘管|卻|尚未|仍未|缺乏|鮮少|較少|不足|有限|however|yet\b|nevertheless|despite|little is known|remains? unclear|few studies|has not been|lack of|gap",
    "concern": r"重要|關鍵|因此有必要|值得|亟需|不容忽視|將導致|important|crucial|critical|matters? because|essential|urgent|at stake",
    "course": r"本研究|本文|旨在|目的在於|this (?:study|paper|research|article|thesis)|we (?:examine|investigate|explore|test|propose|develop)|the purpose of",
    "contribution": r"貢獻|有助於|提供.{0,12}(?:建議|參考|啟示)|實務意涵|理論意涵|contribut|implications?|advances? (?:our )?understanding|extends? the literature",
}


def infer_story(text: str) -> dict[str, str]:
    """One sentence per C from the opening of the document, picked by the signal words of each move
    (common ground → complication → concern → course of action → contribution), in that order."""
    intro = text[:12000]
    start = max(intro.find("摘要"), intro.lower().find("abstract"), 0)
    sentences = [s for s in _sentences(intro[start:]) if 12 <= len(s) <= 220 and not re.search(r"\.{4,}|…{2,}|\d+\s*$|^關鍵[詞字]|^keywords", s, re.I)]
    out: dict[str, str] = {}
    position = 0
    for key, cue in _STORY_CUES.items():
        for i in range(position, len(sentences)):
            if re.search(cue, sentences[i], re.I) and sentences[i] not in out.values():
                out[key] = sentences[i]
                position = i + 1 if key != "course" else i  # the purpose sentence often also states the contribution
                break
    return out


def infer_intro(text: str) -> str:
    """The introduction section of a document: from 「第一章 緒論」/「Introduction」 to the next chapter heading.
    Table-of-contents lines (with dot leaders or page numbers) are skipped."""
    lines = (text or "").splitlines()
    start = None
    for i, ln in enumerate(lines):
        t = ln.strip()
        if re.search(r"\.{3,}|…{2,}|\s\d{1,3}$", t):
            continue  # a table-of-contents entry
        if re.fullmatch(r"(?:第[一1]章\s*)?(?:緒論|導論|前言|緒\s*論)|(?:1\.?|I\.)?\s*Introduction|INTRODUCTION", t, re.I):
            start = i + 1
            break
    if start is None:
        return ""
    out = []
    for ln in lines[start:]:
        t = ln.strip()
        if re.fullmatch(r"第[二2]章.{0,20}|(?:2\.?|II\.)\s*[A-Z].{0,60}|(?:Literature Review|Theoretical Background|Theory and Hypothes[ie]s|THEORY.*|LITERATURE.*|METHODS?)", t):
            break
        out.append(ln)
    intro = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    return intro[:12000] if len(intro) >= 200 else ""


def infer_design(text: str) -> dict:
    """Design facts stated in the method section: data design, number of waves, sample sentence, purpose."""
    body = text[:300000]
    out: dict = {}
    count = lambda pattern: len(re.findall(pattern, body, re.I))  # noqa: E731
    experiment = count(r"實驗設計|實驗組|操弄|隨機分派|random(?:ly)? assign|manipulat|experimental (?:design|condition)")
    longitudinal = count(r"縱貫|追蹤調查|兩階段|三階段|兩個時點|三個時點|分時點|時間落差|longitudinal|time[- ]lagged|panel data|two[- ]wave|three[- ]wave|multi[- ]wave")
    survey = count(r"問卷|量表|survey|questionnaire")
    qualitative = count(r"訪談|質性|焦點團體|焦點群體|個案研究|interview|qualitative|focus group|case study")
    if qualitative > max(survey, 4):
        survey = experiment = longitudinal = 0  # interviews and cases: no quantitative design to record
    if experiment >= 3:
        out["design"] = "experiment"
    elif longitudinal >= 2:
        out["design"] = "longitudinal"
    elif survey >= 3:
        out["design"] = "cross_sectional"
    waves = re.search(r"([二兩三四五2-5]|two|three|four)\s*(?:個)?(?:階段|時點|波|[- ]?waves?|[- ]?time points?)", body, re.I)
    if waves and out.get("design") == "longitudinal":
        out["waves"] = {"二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "two": 2, "three": 3, "four": 4}.get(waves.group(1).lower(), int(waves.group(1)) if waves.group(1).isdigit() else 2)
    elif out.get("design") == "cross_sectional":
        out["waves"] = 1
    sample = next((s for s in _sentences(body) if re.search(r"(?:有效)?(?:問卷|樣本)\s*(?:共|為|計)?\s*\d+|共(?:回收|發放|訪談)\s*\d+|\d+\s*(?:份|位|名|participants|respondents|employees|students)|[Nn]\s*=\s*\d+", s)
                   and 15 <= len(s) <= 260), "")
    if sample:
        out["sample"] = sample
    if "design" in out:  # a purpose only means something next to a quantitative design
        if out["design"] == "experiment" or count(r"因果|causal|中介效果|中介變|mediat") >= 3:
            out["purpose"] = "causal"
        elif out["design"] == "longitudinal":
            out["purpose"] = "change"
        elif count(r"相關|關聯|correlat|associat") >= 3:
            out["purpose"] = "describe"
    return out


def analysis_prompt(text: str, filename: str) -> tuple[str, str]:
    system = ("You read a graduate student's research document and return what it implies for their research dashboard. "
              "Reply with ONE JSON object: {\"title\": str, \"variables\": [{\"key\": str, \"name_zh\": str, \"name_en\": str, "
              "\"role\": \"iv\"|\"dv\"|\"med\"|\"mod\"|\"ctrl\"}], \"relations\": [{\"source\": key, \"target\": key, "
              "\"kind\": \"effect\"|\"moderates\", \"sign\": \"+\"|\"-\"|\"\", \"label\": str, \"moderates\": index of the moderated effect or null}], "
              "\"story\": {\"common\": str, \"complication\": str, \"concern\": str, \"course\": str, \"contribution\": str}, "
              "\"design\": {\"purpose\": \"describe\"|\"change\"|\"causal\"|\"\", \"design\": \"cross_sectional\"|\"longitudinal\"|\"experiment\"|\"\", "
              "\"waves\": int, \"sample\": str}}. Infer the research model even when hypotheses are not written out, from the title, purpose and "
              "arguments. Each story value is ONE sentence in the document's language. Use only what the text supports; leave a field empty rather than guess.")
    excerpt = text[:10000] + ("\n…\n" + text[-2500:] if len(text) > 13000 else "")
    return system, f"File: {filename}\n\n{excerpt}"


def framework_ops(found: dict, snapshot: dict) -> tuple[list[dict], dict]:
    """Ops that add an inferred model to the workspace, reusing variables that already exist by name
    and skipping paths that are already there. Returns (ops, counts)."""
    by_name = {}
    for v in snapshot.get("variables", []):
        for name in (v.get("name_zh"), v.get("name_en")):
            if name:
                by_name[re.sub(r"\s+", "", name).casefold()] = v["id"]
    taken = {v["symbol"] for v in snapshot.get("variables", [])}
    have = {(r["source_id"], r["target_id"], r["kind"]): r["id"] for r in snapshot.get("relations", [])}
    ops, ref, new_vars, new_rels = [], {}, 0, 0
    prefix = {"iv": "X", "dv": "Y", "med": "M", "mod": "Z", "ctrl": "C", "other": "V"}
    for i, v in enumerate(found.get("variables", [])):
        key = v["key"]
        names = [re.sub(r"\s+", "", n).casefold() for n in (v.get("name_zh"), v.get("name_en")) if n]
        existing = next((by_name[n] for n in names if n in by_name), None)
        if existing:
            ref[key] = existing
            continue
        n, base = 1, prefix.get(v["role"], "V")
        while f"{base}{n}" in taken:
            n += 1
        taken.add(f"{base}{n}")
        ops.append({"op": "create", "entity": "variable", "ref": f"av{i}", "data": {
            "symbol": f"{base}{n}", "role": v["role"], "name_zh": v.get("name_zh") or "", "name_en": v.get("name_en") or ""}})
        ref[key] = f"$av{i}"
        new_vars += 1
    made: dict[int, object] = {}
    count = len(snapshot.get("relations", []))
    relations = found.get("relations", [])
    for i, r in sorted(enumerate(relations), key=lambda pair: pair[1]["kind"] == "moderates"):
        a, b = ref.get(r["source"]), ref.get(r["target"])
        if a is None or b is None:
            continue
        if isinstance(a, int) and isinstance(b, int) and (a, b, r["kind"]) in have:
            made[i] = have[(a, b, r["kind"])]
            continue
        data = {"source_id": a, "target_id": b, "kind": r["kind"], "sign": r.get("sign") or ""}
        if r["kind"] == "moderates":
            if r.get("moderates") not in made:
                continue
            data["moderates_id"] = made[r["moderates"]]
        count += 1
        data["label"] = r.get("label") if found.get("method") == "rules" and r.get("label") else f"H{count}"
        ops.append({"op": "create", "entity": "relation", "ref": f"ar{i}", "data": data})
        made[i] = f"$ar{i}"
        new_rels += 1
    return ops, {"variables": new_vars, "relations": new_rels}


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
