"""Research Hub tests — standard library only: ``python -m unittest discover tests``."""
from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research_hub import demo, integrations as integ, mcp_server  # noqa: E402
from research_hub.server import App, make_handler  # noqa: E402
from research_hub.store import Store, ValidationError  # noqa: E402


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = Store(Path(self.dir))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_seed_pipeline(self):
        snap = self.store.snapshot()
        self.assertEqual(len(snap["stages"]), 10)
        self.assertEqual(snap["stages"][0]["status"], "active")
        self.assertEqual(snap["overall"], 0)
        self.assertNotIn("agent_token", snap["settings"])
        self.assertTrue(self.store.settings()["agent_token"])

    def test_english_seed(self):
        d = tempfile.mkdtemp()
        try:
            s = Store(Path(d), lang="en")
            self.assertEqual(s.settings()["language"], "en")
            self.assertTrue(all(ord(c) < 128 for t in s.snapshot()["tasks"] for c in t["title"]))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_create_link_with_refs_and_cascade(self):
        res = self.store.apply_ops([
            {"op": "create", "entity": "paper", "ref": "p", "data": {"title": "A paper", "year": "2020"}},
            {"op": "create", "entity": "variable", "ref": "v", "data": {"symbol": "X1", "name_en": "Usefulness"}},
            {"op": "link", "link": "variable_paper", "a": "$v", "b": "$p", "data": {"evidence": "supports"}},
        ])
        pid, vid = res[0]["id"], res[1]["id"]
        snap = self.store.snapshot()
        self.assertEqual(snap["variables"][0]["role"], "iv")
        self.assertEqual(snap["variable_papers"], [{**snap["variable_papers"][0], "variable_id": vid, "paper_id": pid, "evidence": "supports"}])
        self.store.apply_ops([{"op": "delete", "entity": "paper", "id": pid}])
        self.assertEqual(self.store.snapshot()["variable_papers"], [])

    def test_batch_is_atomic(self):
        with self.assertRaises(ValidationError):
            self.store.apply_ops([
                {"op": "create", "entity": "paper", "data": {"title": "kept?"}},
                {"op": "create", "entity": "paper", "data": {"title": "bad", "status": "nonsense"}},
            ])
        self.assertEqual(self.store.snapshot()["papers"], [])

    def test_validation(self):
        bad = [
            {"op": "create", "entity": "paper", "data": {}},
            {"op": "create", "entity": "paper", "data": {"title": "x", "evil": 1}},
            {"op": "create", "entity": "nope", "data": {}},
            {"op": "update", "entity": "stage", "id": 9999, "data": {"progress": 5}},
            {"op": "update", "entity": "stage", "id": 1, "data": {"due_date": "tomorrow"}},
            {"op": "create", "entity": "file", "data": {"name": "x", "stored": "../../etc/passwd"}},
            {"op": "link", "link": "variable_paper", "a": 1, "b": 1},
            {"op": "update", "entity": "stage", "match": {"title_zh": "研究主題", "key": "x"}, "data": {}},
        ]
        for op in bad:
            with self.subTest(op=op), self.assertRaises(ValidationError):
                self.store.apply_ops([op])

    def test_progress_clamped_and_done_sets_100(self):
        self.store.apply_ops([{"op": "update", "entity": "stage", "match": {"key": "topic"}, "data": {"progress": 250}}])
        self.assertEqual(self.store.snapshot()["stages"][0]["progress"], 100)
        self.store.apply_ops([{"op": "update", "entity": "stage", "match": {"key": "literature"}, "data": {"status": "done"}}])
        snap = self.store.snapshot()
        self.assertEqual(snap["stages"][1]["progress"], 100)
        self.assertEqual(snap["overall"], 20)

    def test_cannot_delete_last_stage(self):
        ids = [s["id"] for s in self.store.snapshot()["stages"]]
        self.store.apply_ops([{"op": "delete", "entity": "stage", "id": i} for i in ids[1:]])
        with self.assertRaises(ValidationError):
            self.store.apply_ops([{"op": "delete", "entity": "stage", "id": ids[0]}])

    def test_proposal_gate(self):
        """Agent changes do nothing until approved; partial approval applies only the kept ops."""
        before = self.store.snapshot()["stages"][1]["progress"]
        ops = [{"op": "update", "entity": "stage", "match": {"key": "literature"}, "data": {"progress": 80}},
               {"op": "create", "entity": "paper", "data": {"title": "Suggested"}}]
        pid = self.store.propose("agent", "lit done", ops)["id"]
        self.assertEqual(self.store.snapshot()["stages"][1]["progress"], before)
        self.assertEqual(self.store.snapshot()["pending"], 1)
        self.store.decide(pid, True, ops[:1])
        snap = self.store.snapshot()
        self.assertEqual(snap["stages"][1]["progress"], 80)
        self.assertEqual(snap["papers"], [])
        self.assertEqual(snap["pending"], 0)
        with self.assertRaises(ValidationError):
            self.store.decide(pid, True)

    def test_dry_run_and_failed_batch_keep_files(self):
        (Path(self.dir) / "uploads" / "keep.txt").write_text("x")
        fid = self.store.apply_ops([{"op": "create", "entity": "file", "data": {"name": "keep.txt", "stored": "keep.txt"}}],
                                   allow_internal=True)[0]["id"]
        pid = self.store.propose("agent", "delete", [{"op": "delete", "entity": "file", "id": fid}])["id"]
        self.assertTrue((Path(self.dir) / "uploads" / "keep.txt").exists())
        with self.assertRaises(ValidationError):
            self.store.apply_ops([{"op": "delete", "entity": "file", "id": fid}, {"op": "create", "entity": "nope"}])
        self.assertTrue((Path(self.dir) / "uploads" / "keep.txt").exists())
        self.store.decide(pid, True)
        self.assertFalse((Path(self.dir) / "uploads" / "keep.txt").exists())

    def test_concurrent_approve_applies_once(self):
        pid = self.store.propose("agent", "x", [{"op": "create", "entity": "rq", "data": {"text": "once"}}])["id"]
        errors = []

        def go():
            try:
                self.store.decide(pid, True)
            except ValidationError as e:
                errors.append(e)

        threads = [threading.Thread(target=go) for _ in range(6)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertEqual(len(self.store.snapshot()["rqs"]), 1)
        self.assertEqual(len(errors), 5)

    def test_partial_approval_must_be_subset(self):
        ops = [{"op": "create", "entity": "rq", "data": {"text": "agent"}}]
        pid = self.store.propose("agent", "x", ops)["id"]
        sneaky = [{"op": "create", "entity": "rq", "data": {"text": "injected"}}]
        with self.assertRaises(ValidationError):
            self.store.decide(pid, True, sneaky)
        with self.assertRaises(ValidationError):
            self.store.decide(pid, True, ops + ops)
        self.assertEqual(self.store.snapshot()["rqs"], [])
        self.store.decide(pid, True, ops)
        self.assertEqual(len(self.store.snapshot()["rqs"]), 1)

    def test_reject_and_invalid_proposal(self):
        pid = self.store.propose("agent", "x", [{"op": "create", "entity": "paper", "data": {"title": "t"}}])["id"]
        self.store.decide(pid, False)
        self.assertEqual(self.store.snapshot()["papers"], [])
        with self.assertRaises(ValidationError):
            self.store.propose("agent", "bad", [{"op": "create", "entity": "paper", "data": {"status": "x"}}])
        with self.assertRaises(ValidationError):
            self.store.propose("agent", "file", [{"op": "create", "entity": "file", "data": {"name": "a", "stored": "a"}}])
        self.assertEqual(self.store.snapshot()["papers"], [])

    def test_settings(self):
        out = self.store.save_settings({"reference_folders": "a\n\n b ", "allow_code_run": 1, "code_timeout": "30"})
        self.assertEqual(out["reference_folders"], ["a", "b"])
        self.assertIs(out["allow_code_run"], True)
        self.assertEqual(out["code_timeout"], 30)
        with self.assertRaises(ValidationError):
            self.store.save_settings({"agent_token": "x"} | {"nope": 1})

    def test_events_emitted(self):
        seen = []
        self.store.listeners.append(seen.append)
        self.store.apply_ops([{"op": "create", "entity": "rq", "data": {"text": "Why?"}}])
        self.assertIn({"type": "changed", "entity": "rq"}, seen)

    def test_demo(self):
        self.assertTrue(demo.apply(self.store))
        snap = self.store.snapshot()
        self.assertEqual(len(snap["variables"]), 6)
        self.assertEqual(snap["pending"], 1)
        self.assertFalse(demo.apply(self.store))


class IntegrationTests(unittest.TestCase):
    def test_bibtex_roundtrip(self):
        bib = """@article{davis1989,
  title = {Perceived usefulness, perceived ease of use, and {User} acceptance},
  author = {Davis, Fred D. and Venkatesh, V.},
  journal = "MIS Quarterly", year = 1989, doi = {10.2307/249008}, keywords = {TAM}
}
@comment{ignored}
@inproceedings{x, title={Second}, booktitle={CHI}, year={2020}}"""
        entries = integ.parse_bibtex(bib)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["title"], "Perceived usefulness, perceived ease of use, and User acceptance")
        self.assertEqual(entries[0]["authors"], "Davis, Fred D. ; Venkatesh, V.")
        self.assertEqual(entries[0]["year"], 1989)
        self.assertEqual(entries[0]["venue"], "MIS Quarterly")
        self.assertEqual(entries[1]["venue"], "CHI")
        out = integ.to_bibtex(entries)
        self.assertEqual(len(integ.parse_bibtex(out)), 2)

    def test_ris(self):
        ris = "TY  - JOUR\nTI  - A title\nAU  - Doe, J.\nAU  - Roe, R.\nPY  - 2021/01/01\nJO  - Journal\nDO  - 10.1/x\nER  - \n"
        e = integ.parse_ris(ris)[0]
        self.assertEqual((e["title"], e["authors"], e["year"], e["doi"]), ("A title", "Doe, J. ; Roe, R.", 2021, "10.1/x"))

    def test_scan_and_paths(self):
        d = Path(tempfile.mkdtemp())
        try:
            (d / "sub").mkdir()
            (d / "sub" / "Smith_2020_Trust.pdf").write_bytes(b"%PDF-1.4")
            (d / ".hidden.pdf").write_bytes(b"x")
            (d / "notes.exe").write_bytes(b"x")
            (d / "lib.bib").write_text("@article{a, title={From bib}, year={2001}}", encoding="utf-8")
            files = integ.scan_folders([str(d)])
            self.assertEqual(sorted(f["name"] for f in files), ["Smith_2020_Trust.pdf", "lib.bib"])
            ops = integ.ops_for_files(files)
            titles = sorted(o["data"]["title"] for o in ops)
            self.assertEqual(titles, ["From bib", "Smith 2020 Trust"])
            self.assertTrue(integ.inside(d / "sub" / "Smith_2020_Trust.pdf", [d]))
            self.assertFalse(integ.inside(Path("/etc/passwd"), [d]))
            self.assertFalse(integ.inside(d / ".." / "x", [d]))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_paperread_sync(self):
        d = Path(tempfile.mkdtemp())
        try:
            p = d / "abc123"
            p.mkdir()
            (p / "paper.json").write_text(json.dumps({"meta": {"title_en": "PR paper", "date": "2022 年", "doi": "10.9/abc"},
                "variables": {"items": [{"role": "iv", "en": "Trust", "zh": "信任"}, {"role": "dv", "en": "Intention"}]}}), encoding="utf-8")
            (p / "item.json").write_text(json.dumps({"status": "reading", "tags": ["t1"]}), encoding="utf-8")
            (d / "broken").mkdir()
            (d / "broken" / "paper.json").write_text("{not json", encoding="utf-8")
            items = integ.paperread_items(str(d))
            broken = next(i for i in items if i["paperread_id"] == "broken")  # unreadable JSON is listed, not fatal
            self.assertEqual((broken["title"], broken["status"]), ("broken", "to_read"))
            item = next(i for i in items if i["paperread_id"] == "abc123")
            self.assertEqual((item["year"], item["status"]), (2022, "reading"))
            dd = tempfile.mkdtemp()
            store = Store(Path(dd))
            store.apply_ops([{"op": "create", "entity": "variable", "data": {"symbol": "X1", "name_en": "trust"}}])
            snap = store.snapshot()
            ops, stats = integ.paperread_sync_ops([item], snap["papers"], snap["variables"])
            self.assertEqual(stats, {"new": 1, "status": 0, "variables": 1})
            store.propose("t", "sync", ops)  # must validate
            store.decide(store.list_proposals()[0]["id"], True)
            snap = store.snapshot()
            self.assertEqual({v["symbol"] for v in snap["variables"]}, {"X1", "Y1"})
            self.assertEqual(len(snap["variable_papers"]), 2)
            ops2, stats2 = integ.paperread_sync_ops([item], snap["papers"], snap["variables"])
            self.assertEqual(stats2, {"new": 0, "status": 0, "variables": 0})
            shutil.rmtree(dd, ignore_errors=True)
        finally:
            shutil.rmtree(d, ignore_errors=True)


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.refs = Path(tempfile.mkdtemp())
        (cls.refs / "paper.pdf").write_bytes(b"%PDF-1.4 test")
        cls.store = Store(Path(cls.dir))
        cls.store.save_settings({"reference_folders": [str(cls.refs)], "watch_folders": True})
        cls.app = App(cls.store)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.app))
        cls.url = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.app.stop.set()
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.dir, ignore_errors=True)
        shutil.rmtree(cls.refs, ignore_errors=True)

    def req(self, path, body=None, token=True, headers=None, raw=None, method=None):
        h = {"X-Hub-Token": self.app.token} if token else {}
        h.update(headers or {})
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        if body is not None:
            h.setdefault("Content-Type", "application/json")
        r = urllib.request.Request(self.url + path, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(r, timeout=10) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_index_has_token_and_languages(self):
        for path, lang in (("/", "zh"), ("/en/", "en"), ("/zh/", "zh")):
            code, body = self.req(path, token=False)
            self.assertEqual(code, 200)
            self.assertIn(self.app.token.encode(), body)
            self.assertIn(f'data-lang="{lang}"'.encode(), body)

    def test_static_traversal_blocked(self):
        self.assertEqual(self.req("/static/js/app.js", token=False)[0], 200)
        self.assertEqual(self.req("/static/../store.py", token=False)[0], 404)
        self.assertEqual(self.req("/static/%2e%2e/store.py", token=False)[0], 404)

    def test_token_required(self):
        self.assertEqual(self.req("/api/state", token=False)[0], 403)
        self.assertEqual(self.req("/api/ops", {"ops": [{"op": "create", "entity": "rq", "data": {"text": "x"}}]}, token=False)[0], 403)
        self.assertEqual(self.req("/api/events", token=False)[0], 403)
        self.assertEqual(self.req("/api/state")[0], 200)

    def test_host_check(self):
        self.assertEqual(self.req("/api/version", token=False, headers={"Host": "attacker.example"})[0], 403)
        self.assertEqual(self.req("/api/version", token=False, headers={"Host": "localhost:1234"})[0], 200)

    def test_agent_can_only_propose(self):
        token = self.store.settings()["agent_token"]
        auth = {"Authorization": f"Bearer {token}"}
        self.assertEqual(self.req("/api/agent/state", token=False)[0], 401)
        self.assertEqual(self.req("/api/agent/state", token=False, headers={"Authorization": "Bearer nope"})[0], 401)
        self.assertEqual(self.req("/api/ops", {"ops": []}, token=False, headers=auth)[0], 403)
        code, body = self.req("/api/agent/state", token=False, headers=auth)
        self.assertEqual(code, 200)
        self.assertNotIn("settings", json.loads(body))
        n_before = len(self.store.snapshot()["rqs"])
        code, body = self.req("/api/agent/proposals", {"title": "RQ", "ops": [{"op": "create", "entity": "rq", "data": {"text": "agent rq"}}]},
                              token=False, headers=auth)
        self.assertEqual(code, 200, body)
        self.assertEqual(len(self.store.snapshot()["rqs"]), n_before)
        pid = json.loads(body)["id"]
        self.assertEqual(self.req(f"/api/proposals/{pid}/approve", {})[0], 200)
        self.assertEqual(len(self.store.snapshot()["rqs"]), n_before + 1)

    def test_upload_and_download(self):
        code, body = self.req("/api/upload?stage_id=1", raw=b"hello", headers={"X-Filename": "..%2F..%2Fevil.txt"})
        self.assertEqual(code, 200, body)
        fid = json.loads(body)["id"]
        row = self.store.get("file", fid)
        self.assertTrue(row["stored"].startswith("stage-1/") and row["stored"].count("/") == 1, row["stored"])
        self.assertTrue((Path(self.dir) / "uploads" / row["stored"]).resolve().is_relative_to((Path(self.dir) / "uploads").resolve()))
        code, data = self.req(f"/api/files/{fid}")
        self.assertEqual((code, data), (200, b"hello"))
        self.assertEqual(self.req("/api/upload?stage_id=999", raw=b"x", headers={"X-Filename": "a.txt"})[0], 400)

    def test_local_files_restricted(self):
        ok = self.req("/api/local?path=" + urllib.request.quote(str(self.refs / "paper.pdf")))
        self.assertEqual(ok[0], 200)
        self.assertEqual(self.req("/api/local?path=/etc/passwd")[0], 403)

    def test_watcher_and_import(self):
        prop = self.app.watch_once()
        self.assertIsNotNone(prop)
        self.assertIsNone(self.app.watch_once())  # already seen
        self.store.decide(prop["id"], False)
        self.assertIsNone(self.app.watch_once())  # rejected files are not re-proposed
        code, body = self.req("/api/import/files", {"paths": [str(self.refs / "paper.pdf")]})
        self.assertEqual(code, 200, body)

    def test_bibtex_import_export(self):
        code, body = self.req("/api/import/bibtex", raw="@article{k, title={Imported}, year={1999}}".encode(), headers={"Content-Type": "text/plain"})
        self.assertEqual((code, json.loads(body)["imported"]), (200, 1))
        code, body = self.req("/api/export/bibtex")
        self.assertIn(b"Imported", body)

    def test_script_run_disabled_by_default(self):
        code, body = self.req("/api/scripts/run", {"path": "/tmp/x.py"})
        self.assertEqual(code, 400)


class McpTests(unittest.TestCase):
    def test_protocol(self):
        class FakeHub:
            def __init__(self):
                self.sent = []

            def state(self):
                return {"overall": 10, "stages": [{"id": 1, "key": "lit", "title_zh": "文獻", "title_en": "Lit", "status": "active",
                                                   "progress": 10, "due_date": "", "notes": "old"}],
                        "tasks": [{"id": 5, "stage_id": 1, "title": "t", "done": 0}], "rqs": [], "variables": [], "papers": [],
                        "resources": [], "files": [], "pending": 0, "schema": {}}

            def propose(self, title, ops, summary="", source=""):
                self.sent.append((title, ops))
                return {"id": 1, "status": "pending"}

        hub = FakeHub()
        init = mcp_server.handle(hub, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
        self.assertEqual(init["result"]["protocolVersion"], "2025-06-18")
        self.assertIsNone(mcp_server.handle(hub, {"jsonrpc": "2.0", "method": "notifications/initialized"}))
        tools = mcp_server.handle(hub, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
        self.assertIn("propose_changes", {t["name"] for t in tools})
        out = mcp_server.handle(hub, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "report_stage_progress", "arguments": {"stage_key": "lit", "progress": 50, "note": "new", "done_task_ids": [5]}}})
        self.assertNotIn("isError", out["result"])
        title, ops = hub.sent[-1]
        self.assertEqual(ops[0]["data"], {"progress": 50, "notes": "old\n\nnew"})
        self.assertEqual(ops[1], {"op": "update", "entity": "task", "id": 5, "data": {"done": True}})
        err = mcp_server.handle(hub, {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "nope", "arguments": {}}})
        self.assertTrue(err["result"]["isError"])
        self.assertEqual(mcp_server.handle(hub, {"jsonrpc": "2.0", "id": 5, "method": "bogus"})["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
