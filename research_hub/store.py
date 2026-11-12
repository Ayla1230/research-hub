"""SQLite store for Research Hub.

One data directory = one research project. Everything the dashboard shows lives in
``hub.sqlite3``; uploaded files live under ``uploads/``. All writes go through
``Store.apply_ops`` so that user edits and approved agent proposals share one code
path, one validation layer and one activity log.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .defaults import DEFAULT_RESOURCES, DEFAULT_SETTINGS, DEFAULT_STAGES

SCHEMA_VERSION = 1

STAGE_STATUS = ("todo", "active", "review", "done", "blocked")
RQ_STATUS = ("draft", "refined", "answered")
VAR_ROLES = ("iv", "dv", "med", "mod", "ctrl", "other")
PAPER_STATUS = ("candidate", "to_read", "reading", "done", "excluded")
RESOURCE_KINDS = ("database", "folder", "mcp", "code", "link", "paperread")
MODULES = ("", "literature", "rq", "variables", "code", "writing")
EVIDENCE = ("", "supports", "contradicts", "mixed", "defines", "measures", "mentions")

# Field specs: name -> (type, extra). Types: str, text, int, bool, enum, ref, json
ENTITIES: dict[str, dict] = {
    "stage": {
        "table": "stages",
        "fields": {
            "key": ("str", None), "position": ("int", None),
            "title_zh": ("str", None), "title_en": ("str", None),
            "desc_zh": ("text", None), "desc_en": ("text", None),
            "status": ("enum", STAGE_STATUS), "progress": ("int", (0, 100)),
            "start_date": ("date", None), "due_date": ("date", None),
            "notes": ("text", None), "module": ("enum", MODULES),
        },
        "required": ("title_zh",),
    },
    "task": {
        "table": "tasks",
        "fields": {
            "stage_id": ("ref", "stage"), "title": ("str", None), "done": ("bool", None),
            "due_date": ("date", None), "position": ("int", None),
        },
        "required": ("stage_id", "title"),
    },
    "rq": {
        "table": "rqs",
        "fields": {
            "code": ("str", None), "text": ("text", None), "hypothesis": ("text", None),
            "status": ("enum", RQ_STATUS), "notes": ("text", None), "position": ("int", None),
        },
        "required": ("text",),
    },
    "variable": {
        "table": "variables",
        "fields": {
            "symbol": ("str", None), "name_zh": ("str", None), "name_en": ("str", None),
            "role": ("enum", VAR_ROLES), "definition": ("text", None),
            "measurement": ("text", None), "notes": ("text", None), "position": ("int", None),
        },
        "required": ("symbol",),
    },
    "paper": {
        "table": "papers",
        "fields": {
            "title": ("str", None), "authors": ("str", None), "year": ("int", (0, 3000)),
            "venue": ("str", None), "doi": ("str", None), "url": ("str", None),
            "abstract": ("text", None), "local_path": ("str", None), "citekey": ("str", None),
            "source": ("str", None), "status": ("enum", PAPER_STATUS), "rating": ("int", (0, 5)),
            "tags": ("str", None), "notes": ("text", None), "paperread_id": ("str", None),
            "openalex_id": ("str", None),
        },
        "required": ("title",),
    },
    "resource": {
        "table": "resources",
        "fields": {
            "kind": ("enum", RESOURCE_KINDS), "name": ("str", None), "target": ("str", None),
            "notes": ("text", None), "stage_id": ("ref?", "stage"), "position": ("int", None),
        },
        "required": ("kind", "name"),
    },
    "file": {
        "table": "files",
        "fields": {
            "stage_id": ("ref?", "stage"), "paper_id": ("ref?", "paper"), "name": ("str", None),
            "stored": ("str", None), "size": ("int", None), "mime": ("str", None),
        },
        "required": ("name", "stored"),
        "internal": True,  # created only by the upload endpoint, never through proposals
    },
}

LINKS: dict[str, dict] = {
    "rq_variable": {"table": "rq_variables", "a": ("rq_id", "rq"), "b": ("variable_id", "variable"), "extra": {}},
    "rq_paper": {"table": "rq_papers", "a": ("rq_id", "rq"), "b": ("paper_id", "paper"), "extra": {"note": ("text", None)}},
    "variable_paper": {
        "table": "variable_papers", "a": ("variable_id", "variable"), "b": ("paper_id", "paper"),
        "extra": {"evidence": ("enum", EVIDENCE), "note": ("text", None)},
    },
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS stages (
  id INTEGER PRIMARY KEY, key TEXT NOT NULL DEFAULT '', position INTEGER NOT NULL DEFAULT 0,
  title_zh TEXT NOT NULL DEFAULT '', title_en TEXT NOT NULL DEFAULT '',
  desc_zh TEXT NOT NULL DEFAULT '', desc_en TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'todo', progress INTEGER NOT NULL DEFAULT 0,
  start_date TEXT NOT NULL DEFAULT '', due_date TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '', module TEXT NOT NULL DEFAULT '',
  created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  id INTEGER PRIMARY KEY, stage_id INTEGER NOT NULL REFERENCES stages(id) ON DELETE CASCADE,
  title TEXT NOT NULL DEFAULT '', done INTEGER NOT NULL DEFAULT 0, due_date TEXT NOT NULL DEFAULT '',
  position INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rqs (
  id INTEGER PRIMARY KEY, code TEXT NOT NULL DEFAULT '', text TEXT NOT NULL DEFAULT '',
  hypothesis TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'draft', notes TEXT NOT NULL DEFAULT '',
  position INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS variables (
  id INTEGER PRIMARY KEY, symbol TEXT NOT NULL DEFAULT '', name_zh TEXT NOT NULL DEFAULT '',
  name_en TEXT NOT NULL DEFAULT '', role TEXT NOT NULL DEFAULT 'iv', definition TEXT NOT NULL DEFAULT '',
  measurement TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', position INTEGER NOT NULL DEFAULT 0,
  created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS papers (
  id INTEGER PRIMARY KEY, title TEXT NOT NULL DEFAULT '', authors TEXT NOT NULL DEFAULT '',
  year INTEGER NOT NULL DEFAULT 0, venue TEXT NOT NULL DEFAULT '', doi TEXT NOT NULL DEFAULT '',
  url TEXT NOT NULL DEFAULT '', abstract TEXT NOT NULL DEFAULT '', local_path TEXT NOT NULL DEFAULT '',
  citekey TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'manual', status TEXT NOT NULL DEFAULT 'to_read',
  rating INTEGER NOT NULL DEFAULT 0, tags TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
  paperread_id TEXT NOT NULL DEFAULT '', openalex_id TEXT NOT NULL DEFAULT '',
  created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS resources (
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'link', name TEXT NOT NULL DEFAULT '',
  target TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
  stage_id INTEGER REFERENCES stages(id) ON DELETE SET NULL, position INTEGER NOT NULL DEFAULT 0,
  created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
  id INTEGER PRIMARY KEY, stage_id INTEGER REFERENCES stages(id) ON DELETE SET NULL,
  paper_id INTEGER REFERENCES papers(id) ON DELETE SET NULL, name TEXT NOT NULL DEFAULT '',
  stored TEXT NOT NULL DEFAULT '', size INTEGER NOT NULL DEFAULT 0, mime TEXT NOT NULL DEFAULT '',
  created TEXT NOT NULL, updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rq_variables (
  rq_id INTEGER NOT NULL REFERENCES rqs(id) ON DELETE CASCADE,
  variable_id INTEGER NOT NULL REFERENCES variables(id) ON DELETE CASCADE,
  created TEXT NOT NULL, PRIMARY KEY (rq_id, variable_id)
);
CREATE TABLE IF NOT EXISTS rq_papers (
  rq_id INTEGER NOT NULL REFERENCES rqs(id) ON DELETE CASCADE,
  paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  note TEXT NOT NULL DEFAULT '', created TEXT NOT NULL, PRIMARY KEY (rq_id, paper_id)
);
CREATE TABLE IF NOT EXISTS variable_papers (
  variable_id INTEGER NOT NULL REFERENCES variables(id) ON DELETE CASCADE,
  paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  evidence TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', created TEXT NOT NULL,
  PRIMARY KEY (variable_id, paper_id)
);
CREATE TABLE IF NOT EXISTS proposals (
  id INTEGER PRIMARY KEY, source TEXT NOT NULL DEFAULT 'agent', title TEXT NOT NULL DEFAULT '',
  summary TEXT NOT NULL DEFAULT '', ops_json TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'pending',
  result TEXT NOT NULL DEFAULT '', created TEXT NOT NULL, decided TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS activity (
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT NOT NULL, action TEXT NOT NULL,
  entity TEXT NOT NULL DEFAULT '', entity_id INTEGER, summary TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS seen_files (path TEXT PRIMARY KEY, at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_tasks_stage ON tasks(stage_id);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON proposals(status);
CREATE INDEX IF NOT EXISTS idx_activity_at ON activity(at);
"""


class ValidationError(ValueError):
    """Raised for bad input; the message is shown to the user."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean(entity: str, name: str, spec: tuple, value):
    kind, extra = spec
    if kind in ("str", "text"):
        text = "" if value is None else str(value)
        limit = 500 if kind == "str" else 50_000
        return text.strip()[:limit] if kind == "str" else text[:limit]
    if kind == "date":
        text = "" if value is None else str(value).strip()[:10]
        if text:
            try:
                datetime.strptime(text, "%Y-%m-%d")
            except ValueError:
                raise ValidationError(f"{entity}.{name}: expected YYYY-MM-DD") from None
        return text
    if kind == "int":
        try:
            number = int(value or 0)
        except (TypeError, ValueError):
            raise ValidationError(f"{entity}.{name}: expected a number") from None
        if extra:
            number = max(extra[0], min(extra[1], number))
        return number
    if kind == "bool":
        return 1 if value in (True, 1, "1", "true", "yes", "on") else 0
    if kind == "enum":
        text = "" if value is None else str(value).strip()
        if text not in extra:
            raise ValidationError(f"{entity}.{name}: must be one of {', '.join(x or '(empty)' for x in extra)}")
        return text
    if kind in ("ref", "ref?"):
        if value in (None, "", 0) and kind == "ref?":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValidationError(f"{entity}.{name}: expected an id") from None
    raise AssertionError(kind)


class Store:
    def __init__(self, root: Path, lang: str = "zh"):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "uploads").mkdir(exist_ok=True)
        self.path = self.root / "hub.sqlite3"
        self._lock = threading.RLock()
        self.listeners: list = []  # callables(event: dict)
        with self.db() as db:
            db.executescript(SCHEMA)
            if not db.execute("SELECT 1 FROM meta WHERE k='schema'").fetchone():
                self._seed(db, "en" if lang == "en" else "zh")

    # ------------------------------------------------------------------ plumbing
    @contextmanager
    def db(self):
        with self._lock:
            conn = sqlite3.connect(self.path, timeout=15)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=15000")
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally:
                conn.close()

    def emit(self, event: dict) -> None:
        for listener in list(self.listeners):
            try:
                listener(event)
            except Exception:  # a dead SSE client must never break a write
                pass

    def _seed(self, db, lang: str) -> None:
        stamp = now()
        db.execute("INSERT INTO meta (k, v) VALUES ('schema', ?)", (str(SCHEMA_VERSION),))
        for i, stage in enumerate(DEFAULT_STAGES):
            db.execute(
                "INSERT INTO stages (key, position, title_zh, title_en, desc_zh, desc_en, module, status, created, updated)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (stage["key"], i, stage["title_zh"], stage["title_en"], stage["desc_zh"], stage["desc_en"],
                 stage.get("module", ""), "active" if i == 0 else "todo", stamp, stamp),
            )
            sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            for j, (zh, en) in enumerate(stage.get("tasks", [])):
                db.execute("INSERT INTO tasks (stage_id, title, position, created, updated) VALUES (?,?,?,?,?)",
                           (sid, en if lang == "en" else zh, j, stamp, stamp))
        for i, res in enumerate(DEFAULT_RESOURCES):
            db.execute("INSERT INTO resources (kind, name, target, notes, position, created, updated) VALUES (?,?,?,?,?,?,?)",
                       (res["kind"], res["name"], res["target"], res.get("notes", ""), i, stamp, stamp))
        settings = dict(DEFAULT_SETTINGS)
        settings["agent_token"] = secrets.token_urlsafe(24)
        settings["language"] = lang
        for k, v in settings.items():
            db.execute("INSERT INTO settings (k, v) VALUES (?, ?)", (k, json.dumps(v)))
        db.execute("INSERT INTO activity (at, actor, action, summary) VALUES (?,?,?,?)",
                   (stamp, "system", "init", "Workspace created"))

    # ------------------------------------------------------------------ settings
    def settings(self, *, public: bool = False) -> dict:
        with self.db() as db:
            out = {r["k"]: json.loads(r["v"]) for r in db.execute("SELECT k, v FROM settings")}
        for k, v in DEFAULT_SETTINGS.items():
            out.setdefault(k, v)
        if public:
            out.pop("agent_token", None)
        return out

    def save_settings(self, patch: dict, actor: str = "user") -> dict:
        allowed = set(DEFAULT_SETTINGS)
        clean = {}
        for k, v in (patch or {}).items():
            if k not in allowed:
                raise ValidationError(f"unknown setting: {k}")
            default = DEFAULT_SETTINGS[k]
            if isinstance(default, bool):
                v = bool(v)
            elif isinstance(default, int):
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    raise ValidationError(f"{k}: expected a number") from None
            elif isinstance(default, list):
                if isinstance(v, str):
                    v = [line.strip() for line in v.splitlines() if line.strip()]
                if not isinstance(v, list):
                    raise ValidationError(f"{k}: expected a list")
                v = [str(x).strip()[:1000] for x in v if str(x).strip()][:50]
            else:
                v = str(v or "").strip()[:2000]
            clean[k] = v
        with self.db() as db:
            for k, v in clean.items():
                db.execute("INSERT INTO settings (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, json.dumps(v)))
            if clean:
                self._log(db, actor, "settings", "", None, ", ".join(sorted(clean)))
        self.emit({"type": "changed", "entity": "settings"})
        return self.settings(public=True)

    def rotate_agent_token(self) -> str:
        token = secrets.token_urlsafe(24)
        with self.db() as db:
            db.execute("INSERT INTO settings (k, v) VALUES ('agent_token', ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (json.dumps(token),))
            self._log(db, "user", "settings", "", None, "agent token rotated")
        return token

    # ------------------------------------------------------------------ reads
    def snapshot(self) -> dict:
        """Everything the dashboard needs in one request."""
        with self.db() as db:
            def rows(sql, *args):
                return [dict(r) for r in db.execute(sql, args)]

            data = {
                "stages": rows("SELECT * FROM stages ORDER BY position, id"),
                "tasks": rows("SELECT * FROM tasks ORDER BY stage_id, done, position, id"),
                "rqs": rows("SELECT * FROM rqs ORDER BY position, id"),
                "variables": rows("SELECT * FROM variables ORDER BY position, id"),
                "papers": rows("SELECT * FROM papers ORDER BY updated DESC, id DESC"),
                "resources": rows("SELECT * FROM resources ORDER BY kind, position, id"),
                "files": rows("SELECT * FROM files ORDER BY created DESC, id DESC"),
                "rq_variables": rows("SELECT * FROM rq_variables"),
                "rq_papers": rows("SELECT * FROM rq_papers"),
                "variable_papers": rows("SELECT * FROM variable_papers"),
                "pending": db.execute("SELECT COUNT(*) FROM proposals WHERE status='pending'").fetchone()[0],
                "activity": rows("SELECT * FROM activity ORDER BY id DESC LIMIT 60"),
            }
        data["settings"] = self.settings(public=True)
        data["overall"] = overall_progress(data["stages"])
        return data

    def get(self, entity: str, eid: int) -> dict | None:
        spec = ENTITIES[entity]
        with self.db() as db:
            row = db.execute(f"SELECT * FROM {spec['table']} WHERE id=?", (eid,)).fetchone()
        return dict(row) if row else None

    def list_proposals(self, status: str = "pending", limit: int = 100) -> list[dict]:
        with self.db() as db:
            if status == "all":
                cur = db.execute("SELECT * FROM proposals ORDER BY id DESC LIMIT ?", (limit,))
            else:
                cur = db.execute("SELECT * FROM proposals WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit))
            out = []
            for r in cur:
                item = dict(r)
                item["ops"] = json.loads(item.pop("ops_json") or "[]")
                out.append(item)
        return out

    # ------------------------------------------------------------------ writes
    def apply_ops(self, ops: list[dict], actor: str = "user", *, allow_internal: bool = False) -> list[dict]:
        """Validate and apply a batch atomically. Returns per-op results.

        Supported ops::

            {"op": "create", "entity": "paper", "data": {...}, "ref": "p1"}
            {"op": "update", "entity": "stage", "id": 3, "data": {...}}   # or "match": {"key": "lit"}
            {"op": "delete", "entity": "task", "id": 9}
            {"op": "link" | "unlink", "link": "variable_paper", "a": 1, "b": "$p1", "data": {...}}

        ``"$ref"`` strings point at objects created earlier in the same batch.
        """
        if not isinstance(ops, list) or not ops:
            raise ValidationError("ops must be a non-empty list")
        if len(ops) > 500:
            raise ValidationError("too many operations in one batch (max 500)")
        results: list[dict] = []
        refs: dict[str, int] = {}
        touched: set[str] = set()
        with self.db() as db:
            for index, op in enumerate(ops):
                try:
                    results.append(self._apply_one(db, op, refs, actor, allow_internal, touched))
                except ValidationError as e:
                    raise ValidationError(f"op #{index + 1}: {e}") from None
                except sqlite3.IntegrityError as e:
                    raise ValidationError(f"op #{index + 1}: {e}") from None
        uploads = (self.root / "uploads").resolve()
        for item in touched:
            if isinstance(item, tuple) and item[0] == "unlink":
                try:
                    stored = (uploads / item[1]).resolve()
                    if stored.is_relative_to(uploads) and stored != uploads:
                        stored.unlink(missing_ok=True)
                except OSError:
                    pass
        for entity in sorted(e for e in touched if isinstance(e, str)):
            self.emit({"type": "changed", "entity": entity})
        return results

    def _resolve(self, value, refs: dict[str, int]):
        if isinstance(value, str) and value.startswith("$"):
            if value[1:] not in refs:
                raise ValidationError(f"unknown reference {value}")
            return refs[value[1:]]
        return value

    def _find(self, db, entity: str, op: dict, refs) -> int:
        spec = ENTITIES[entity]
        if "id" in op:
            eid = self._resolve(op["id"], refs)
            try:
                eid = int(eid)
            except (TypeError, ValueError):
                raise ValidationError("id must be a number") from None
            if not db.execute(f"SELECT 1 FROM {spec['table']} WHERE id=?", (eid,)).fetchone():
                raise ValidationError(f"{entity} #{eid} does not exist")
            return eid
        match = op.get("match")
        if isinstance(match, dict) and len(match) == 1:
            (field, value), = match.items()
            if field not in spec["fields"] or spec["fields"][field][0] not in ("str",):
                raise ValidationError(f"cannot match {entity} by {field}")
            rows = db.execute(f"SELECT id FROM {spec['table']} WHERE {field}=?", (str(value),)).fetchall()
            if len(rows) != 1:
                raise ValidationError(f"{entity} with {field}={value!r}: found {len(rows)} matches")
            return rows[0]["id"]
        raise ValidationError("update/delete needs an id or a single-field match")

    def _check_ref(self, db, target: str, value):
        if value is None:
            return
        table = ENTITIES[target]["table"]
        if not db.execute(f"SELECT 1 FROM {table} WHERE id=?", (value,)).fetchone():
            raise ValidationError(f"{target} #{value} does not exist")

    def _apply_one(self, db, op: dict, refs, actor, allow_internal, touched) -> dict:
        if not isinstance(op, dict):
            raise ValidationError("operation must be an object")
        kind = op.get("op")
        if kind in ("link", "unlink"):
            return self._link(db, op, refs, actor, touched)
        entity = op.get("entity")
        if entity not in ENTITIES:
            raise ValidationError(f"unknown entity {entity!r}")
        spec = ENTITIES[entity]
        if spec.get("internal") and not allow_internal and kind == "create":
            raise ValidationError(f"{entity} cannot be created this way")
        table = spec["table"]
        data = op.get("data") or {}
        if not isinstance(data, dict):
            raise ValidationError("data must be an object")
        clean = {}
        for field, value in data.items():
            if field not in spec["fields"]:
                raise ValidationError(f"unknown field {entity}.{field}")
            value = self._resolve(value, refs)
            fspec = spec["fields"][field]
            clean[field] = _clean(entity, field, fspec, value)
            if fspec[0] in ("ref", "ref?"):
                self._check_ref(db, fspec[1], clean[field])
        stamp = now()
        if kind == "create":
            for field in spec["required"]:
                if clean.get(field) in (None, ""):
                    raise ValidationError(f"{entity}.{field} is required")
            if "position" in spec["fields"] and "position" not in clean:
                clean["position"] = (db.execute(f"SELECT COALESCE(MAX(position), -1) + 1 FROM {table}").fetchone()[0])
            if entity == "variable" and "role" not in clean:
                clean["role"] = "iv"
            if entity == "stage" and not clean.get("title_en"):
                clean["title_en"] = clean["title_zh"]
            cols = list(clean) + ["created", "updated"]
            db.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                       [*clean.values(), stamp, stamp])
            eid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            if op.get("ref"):
                refs[str(op["ref"])] = eid
            self._log(db, actor, "create", entity, eid, _label(entity, clean))
            touched.add(entity)
            return {"op": "create", "entity": entity, "id": eid}
        if kind == "update":
            eid = self._find(db, entity, op, refs)
            if not clean:
                return {"op": "update", "entity": entity, "id": eid, "changed": []}
            for field in spec["required"]:
                if field in clean and clean[field] in (None, ""):
                    raise ValidationError(f"{entity}.{field} cannot be empty")
            if entity == "stage" and "status" in clean:
                if clean["status"] == "done" and "progress" not in clean:
                    clean["progress"] = 100
            sets = ", ".join(f"{k}=?" for k in clean)
            db.execute(f"UPDATE {table} SET {sets}, updated=? WHERE id=?", [*clean.values(), stamp, eid])
            row = dict(db.execute(f"SELECT * FROM {table} WHERE id=?", (eid,)).fetchone())
            self._log(db, actor, "update", entity, eid, f"{_label(entity, row)}: {', '.join(clean)}")
            touched.add(entity)
            return {"op": "update", "entity": entity, "id": eid, "changed": list(clean)}
        if kind == "delete":
            eid = self._find(db, entity, op, refs)
            row = dict(db.execute(f"SELECT * FROM {table} WHERE id=?", (eid,)).fetchone())
            if entity == "stage" and db.execute("SELECT COUNT(*) FROM stages").fetchone()[0] <= 1:
                raise ValidationError("the pipeline needs at least one stage")
            db.execute(f"DELETE FROM {table} WHERE id=?", (eid,))
            if entity == "file":
                # Remove the stored file only after the transaction commits (see apply_ops);
                # dry runs and failed batches must never touch the disk.
                touched.add(("unlink", row["stored"]))
            self._log(db, actor, "delete", entity, eid, _label(entity, row))
            touched.add(entity)
            return {"op": "delete", "entity": entity, "id": eid}
        raise ValidationError(f"unknown op {kind!r}")

    def _link(self, db, op, refs, actor, touched) -> dict:
        name = op.get("link")
        if name not in LINKS:
            raise ValidationError(f"unknown link {name!r}")
        spec = LINKS[name]
        a_col, a_ent = spec["a"]
        b_col, b_ent = spec["b"]
        try:
            a = int(self._resolve(op.get("a"), refs))
            b = int(self._resolve(op.get("b"), refs))
        except (TypeError, ValueError):
            raise ValidationError("link needs numeric a and b") from None
        self._check_ref(db, a_ent, a)
        self._check_ref(db, b_ent, b)
        table = spec["table"]
        names = []
        for ent, eid in ((a_ent, a), (b_ent, b)):
            row = db.execute(f"SELECT * FROM {ENTITIES[ent]['table']} WHERE id=?", (eid,)).fetchone()
            names.append(_label(ent, dict(row))[:60] if row else f"{ent} #{eid}")
        pair = f"{names[0]} ↔ {names[1]}"
        if op["op"] == "unlink":
            db.execute(f"DELETE FROM {table} WHERE {a_col}=? AND {b_col}=?", (a, b))
            self._log(db, actor, "unlink", name, a, pair)
        else:
            extra = {}
            for field, value in (op.get("data") or {}).items():
                if field not in spec["extra"]:
                    raise ValidationError(f"unknown field {name}.{field}")
                extra[field] = _clean(name, field, spec["extra"][field], value)
            cols = [a_col, b_col, *extra, "created"]
            update = ", ".join(f"{k}=excluded.{k}" for k in extra) or f"{a_col}=excluded.{a_col}"
            db.execute(
                f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
                f" ON CONFLICT({a_col}, {b_col}) DO UPDATE SET {update}",
                [a, b, *extra.values(), now()],
            )
            self._log(db, actor, "link", name, a, pair + (f" ({extra['evidence']})" if extra.get("evidence") else ""))
        touched.add(name)
        return {"op": op["op"], "link": name, "a": a, "b": b}

    def _log(self, db, actor, action, entity, eid, summary) -> None:
        db.execute("INSERT INTO activity (at, actor, action, entity, entity_id, summary) VALUES (?,?,?,?,?,?)",
                   (now(), str(actor)[:80], action, entity, eid, str(summary)[:300]))
        db.execute("DELETE FROM activity WHERE id <= (SELECT MAX(id) - 2000 FROM activity)")

    def log(self, actor: str, action: str, summary: str, entity: str = "", eid=None) -> None:
        with self.db() as db:
            self._log(db, actor, action, entity, eid, summary)
        self.emit({"type": "changed", "entity": "activity"})

    # ------------------------------------------------------------------ proposals
    def propose(self, source: str, title: str, ops: list[dict], summary: str = "") -> dict:
        """Queue changes for user confirmation. Ops are dry-run validated so the
        user never sees a proposal that cannot be applied as written."""
        source = (str(source or "agent").strip() or "agent")[:80]
        title = (str(title or "").strip() or "Untitled update")[:300]
        self.dry_run(ops)
        with self.db() as db:
            db.execute("INSERT INTO proposals (source, title, summary, ops_json, created) VALUES (?,?,?,?,?)",
                       (source, title, str(summary or "")[:5000], json.dumps(ops, ensure_ascii=False), now()))
            pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            self._log(db, source, "propose", "proposal", pid, title)
        self.emit({"type": "proposal", "id": pid, "title": title, "source": source})
        return {"id": pid, "status": "pending"}

    def dry_run(self, ops: list[dict]) -> None:
        """Validate a batch against current data without committing it."""
        if not isinstance(ops, list) or not ops:
            raise ValidationError("ops must be a non-empty list")
        with self._lock:
            conn = sqlite3.connect(self.path, timeout=15)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                refs: dict[str, int] = {}
                for index, op in enumerate(ops):
                    try:
                        self._apply_one(conn, op, refs, "dry-run", False, set())
                    except ValidationError as e:
                        raise ValidationError(f"op #{index + 1}: {e}") from None
                    except sqlite3.IntegrityError as e:
                        raise ValidationError(f"op #{index + 1}: {e}") from None
            finally:
                conn.rollback()
                conn.close()

    def decide(self, pid: int, approve: bool, ops: list[dict] | None = None) -> dict:
        # Hold the store lock for the whole check-apply-mark sequence so two
        # concurrent approvals of one proposal cannot both apply it.
        with self._lock:
            return self._decide(pid, approve, ops)

    def _decide(self, pid: int, approve: bool, ops: list[dict] | None) -> dict:
        with self.db() as db:
            row = db.execute("SELECT * FROM proposals WHERE id=?", (pid,)).fetchone()
        if not row:
            raise ValidationError(f"proposal #{pid} does not exist")
        if row["status"] != "pending":
            raise ValidationError(f"proposal #{pid} is already {row['status']}")
        result = ""
        status = "rejected"
        if approve:
            original = json.loads(row["ops_json"])
            if ops is not None:
                # Partial approval: only a subset of the proposed ops, unchanged and in order.
                remaining = [json.dumps(o, sort_keys=True) for o in original]
                for op in ops:
                    key = json.dumps(op, sort_keys=True)
                    if key not in remaining:
                        raise ValidationError("approved changes must be a subset of the proposal")
                    remaining = remaining[remaining.index(key) + 1:]
                if not ops:
                    raise ValidationError("select at least one change")
            batch = ops if ops is not None else original
            out = self.apply_ops(batch, actor=f"{row['source']} (approved)")
            status = "approved"
            result = json.dumps(out)
            if ops is not None:
                with self.db() as db:
                    db.execute("UPDATE proposals SET ops_json=? WHERE id=?", (json.dumps(ops, ensure_ascii=False), pid))
        with self.db() as db:
            db.execute("UPDATE proposals SET status=?, decided=?, result=? WHERE id=? AND status='pending'",
                       (status, now(), result, pid))
            self._log(db, "user", status, "proposal", pid, row["title"])
        self.emit({"type": "changed", "entity": "proposal"})
        return {"id": pid, "status": status}

    # ------------------------------------------------------------------ seen files (folder watcher)
    def unseen(self, paths: list[str]) -> list[str]:
        if not paths:
            return []
        with self.db() as db:
            known = {r["path"] for r in db.execute("SELECT path FROM seen_files")}
            known |= {r["local_path"] for r in db.execute("SELECT local_path FROM papers WHERE local_path<>''")}
        return [p for p in paths if p not in known]

    def mark_seen(self, paths: list[str]) -> None:
        with self.db() as db:
            db.executemany("INSERT OR IGNORE INTO seen_files (path, at) VALUES (?, ?)", [(p, now()) for p in paths])


def _label(entity: str, row: dict) -> str:
    for key in ("title", "title_zh", "symbol", "code", "name", "text"):
        if row.get(key):
            text = str(row[key])
            if entity == "variable" and (row.get("name_zh") or row.get("name_en")):
                text += f" {row.get('name_zh') or row.get('name_en')}"
            return text[:120]
    return f"{entity}"


def overall_progress(stages: list[dict]) -> int:
    if not stages:
        return 0
    return round(sum(100 if s["status"] == "done" else int(s["progress"] or 0) for s in stages) / len(stages))
