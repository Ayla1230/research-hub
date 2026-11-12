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
from research_hub.store import QuotaError, Store, ValidationError  # noqa: E402


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
        with self.assertRaises(ValidationError):  # proposals cannot touch upload records at all
            self.store.propose("agent", "delete", [{"op": "delete", "entity": "file", "id": fid}])
        self.assertTrue((Path(self.dir) / "uploads" / "keep.txt").exists())
        with self.assertRaises(ValidationError):
            self.store.apply_ops([{"op": "delete", "entity": "file", "id": fid}, {"op": "create", "entity": "nope"}])
        self.assertTrue((Path(self.dir) / "uploads" / "keep.txt").exists())
        self.store.apply_ops([{"op": "delete", "entity": "file", "id": fid}])
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

    def test_append_and_conflicts(self):
        ops = [{"op": "update", "entity": "stage", "match": {"key": "topic"}, "data": {"progress": 40}, "append": {"notes": "agent note"}}]
        import time as _t
        pid = self.store.propose("agent", "x", ops)["id"]
        self.assertEqual(self.store.list_proposals()[0]["conflicts"], [])
        _t.sleep(1.1)
        self.store.apply_ops([{"op": "update", "entity": "stage", "match": {"key": "topic"}, "data": {"notes": "mine"}}])
        self.assertEqual(self.store.list_proposals()[0]["conflicts"], [0])
        self.store.decide(pid, True)
        self.assertEqual(self.store.snapshot()["stages"][0]["notes"], "mine\n\nagent note")
        with self.assertRaises(ValidationError):
            self.store.apply_ops([{"op": "update", "entity": "stage", "id": 1, "append": {"title_zh": "x"}}])

    def test_internal_entities_and_settings_validation(self):
        with self.assertRaises(ValidationError):
            self.store.propose("agent", "x", [{"op": "delete", "entity": "file", "id": 1}])
        with self.assertRaises(ValidationError):
            self.store.apply_ops([{"op": "update", "entity": "file", "id": 1, "data": {"stored": "../x"}}])
        for bad in ({"language": "fr"}, {"ai_base_url": "javascript:alert(1)"}, {"agent_token": "x"}, {"openalex_mailto": "nope"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                self.store.save_settings(bad)
        self.assertEqual(self.store.save_settings({"code_timeout": -5})["code_timeout"], 10)

    def test_unknown_ref_message(self):
        with self.assertRaises(ValidationError) as cm:
            self.store.apply_ops([{"op": "link", "link": "variable_paper", "a": "$nope", "b": 1}])
        self.assertIn("unknown reference", str(cm.exception))

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

    def test_old_paperread_settings_cleaned_up(self):
        with self.store.db() as db:
            db.execute("INSERT INTO settings (k, v) VALUES ('paperread_url', '\"http://127.0.0.1:8765\"')")
            db.execute("INSERT INTO resources (kind, name, target, created, updated) VALUES ('paperread', 'PaperRead', 'http://127.0.0.1:8765', 'x', 'x')")
            db.execute("INSERT INTO resources (kind, name, target, created, updated) VALUES ('paperread', 'My reader', 'http://lab', 'x', 'x')")
        store = Store(Path(self.dir))  # reopening runs the cleanup
        self.assertNotIn("paperread_url", store.settings())
        kinds = {r["name"]: r["kind"] for r in store.snapshot()["resources"]}
        self.assertNotIn("PaperRead", kinds)
        self.assertEqual(kinds["My reader"], "link")

    def test_demo(self):
        self.assertTrue(demo.apply(self.store))
        snap = self.store.snapshot()
        self.assertEqual(len(snap["variables"]), 6)
        self.assertEqual(snap["pending"], 1)
        self.assertFalse(demo.apply(self.store))


class TrackingTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = Store(Path(self.dir))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_progress_follows_tasks(self):
        lit = next(s for s in self.store.snapshot()["stages"] if s["key"] == "literature")
        tasks = [t for t in self.store.snapshot()["tasks"] if t["stage_id"] == lit["id"]]
        self.assertEqual(len(tasks), 3)
        self.store.apply_ops([{"op": "update", "entity": "task", "id": tasks[0]["id"], "data": {"done": True}}])
        stage = self.store.get("stage", lit["id"])
        self.assertEqual((stage["progress"], stage["status"]), (33, "active"))
        self.store.apply_ops([{"op": "update", "entity": "task", "id": t["id"], "data": {"done": True}} for t in tasks])
        stage = self.store.get("stage", lit["id"])
        self.assertEqual((stage["progress"], stage["status"]), (100, "review"))
        self.store.apply_ops([{"op": "create", "entity": "task", "data": {"stage_id": lit["id"], "title": "one more"}}])
        self.assertEqual(self.store.get("stage", lit["id"])["progress"], 75)
        # a manual slider change in the same batch is respected
        self.store.apply_ops([{"op": "update", "entity": "stage", "id": lit["id"], "data": {"progress": 40}}])
        self.assertEqual(self.store.get("stage", lit["id"])["progress"], 40)
        self.store.save_settings({"auto_progress_from_tasks": False})
        self.store.apply_ops([{"op": "update", "entity": "task", "id": tasks[0]["id"], "data": {"done": False}}])
        self.assertEqual(self.store.get("stage", lit["id"])["progress"], 40)

    def test_quota_and_reset_day(self):
        self.store.save_settings({"quota_semantic": 2})
        self.store.take_quota("semantic")
        self.store.take_quota("semantic")
        with self.assertRaises(QuotaError):
            self.store.take_quota("semantic")
        usage = self.store.usage()
        self.assertEqual(usage["providers"]["semantic"]["requests"], 2)
        self.assertGreaterEqual(usage["resets_in_minutes"], 0)
        with self.store.db() as db:  # yesterday's usage does not count today
            db.execute("UPDATE usage SET day='2000-01-01'")
        self.store.take_quota("semantic")

    def test_secrets_never_public(self):
        self.store.save_settings({"ai_api_key": "sk-secret", "wos_api_key": "w", "ai_provider": "groq"})
        public = self.store.settings(public=True)
        self.assertNotIn("ai_api_key", public)
        self.assertTrue(public["ai_api_key_set"] and public["wos_api_key_set"])
        self.assertNotIn("sk-secret", json.dumps(self.store.snapshot()))
        for bad in ({"ai_provider": "evil"}, {"watch_providers": ["scholar"]}, {"archive_rules": ["no arrow"]},
                    {"project_deadline": "soon"}, {"ai_base_url": "file:///etc"}):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                self.store.save_settings(bad)

    def test_classify(self):
        stages = self.store.snapshot()["stages"]
        key = lambda names, rules=None: integ.classify(names, stages, rules)["key"]  # noqa: E731
        self.assertEqual(key(["analysis/regression.py"]), "analysis")
        self.assertEqual(key(["文獻探討_v2.docx"]), "literature")
        self.assertEqual(key(["口試簡報.pptx"]), "defense")
        self.assertEqual(key(["thesis_chapter3.docx"]), "writing")
        self.assertIsNone(key(["IMG_0001.jpg"]))
        self.assertEqual(key(["IMG_0001.jpg"], ["img => data"]), "data")

    def test_ai_config_and_prompt(self):
        self.assertIsNone(integ.ai_config({"ai_provider": "groq"}))  # no key yet
        cfg = integ.ai_config({"ai_provider": "groq", "ai_api_key": "k"})
        self.assertTrue(cfg["base_url"].startswith("https://api.groq.com"))
        self.assertEqual(integ.ai_config({"ai_provider": "ollama"})["model"], "qwen2.5:7b")
        self.assertEqual(integ.parse_json_block('noise {"progress": 40, "query": "tam"} tail'), {"progress": 40, "query": "tam"})
        self.assertEqual(integ.parse_json_block("nothing"), {})
        q = integ.default_query({"title_en": "Lit"}, "finished screening trust papers", {"variables_en": ["Perceived usefulness"]})
        self.assertIn("Perceived usefulness", q)


class StoryTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = Store(Path(self.dir))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_story_rows_fixed(self):
        story = self.store.snapshot()["story"]
        self.assertEqual([r["key"] for r in story], ["common", "complication", "concern", "course", "contribution"])
        self.store.apply_ops([{"op": "update", "entity": "story", "match": {"key": "complication"}, "data": {"sentence": "Yet…"}}])
        self.assertEqual(self.store.snapshot()["story"][1]["sentence"], "Yet…")
        for op in ({"op": "create", "entity": "story", "data": {"key": "common"}},
                   {"op": "delete", "entity": "story", "id": story[0]["id"]},
                   {"op": "update", "entity": "story", "id": story[0]["id"], "data": {"key": "bogus"}}):
            with self.subTest(op=op), self.assertRaises(ValidationError):
                self.store.apply_ops([op])
        pid = self.store.propose("agent", "story", [{"op": "update", "entity": "story", "match": {"key": "concern"}, "append": {"notes": "idea"}}])["id"]
        self.store.decide(pid, True)
        self.assertEqual(self.store.snapshot()["story"][2]["notes"], "idea")

    def test_paper_five_c_fields(self):
        res = self.store.apply_ops([{"op": "create", "entity": "paper", "data": {"title": "P", "c_common": "we know", "complication_type": "puzzle", "story_role": "complication"}}])
        p = self.store.get("paper", res[0]["id"])
        self.assertEqual((p["c_common"], p["complication_type"], p["story_role"]), ("we know", "puzzle", "complication"))
        with self.assertRaises(ValidationError):
            self.store.apply_ops([{"op": "update", "entity": "paper", "id": p["id"], "data": {"story_role": "plot"}}])

    def test_old_workspace_migrates(self):
        with self.store.db() as db:
            db.executescript("""
              DROP TABLE story;
              CREATE TABLE papers_old AS SELECT id, title, authors, year, venue, doi, url, abstract, local_path, citekey, source, status,
                rating, tags, notes, openalex_id, created, updated FROM papers;
              DROP TABLE papers; ALTER TABLE papers_old RENAME TO papers;""")
        store = Store(Path(self.dir))
        with store.db() as db:
            cols = {r["name"] for r in db.execute("PRAGMA table_info(papers)")}
        self.assertTrue({"c_common", "c_contribution", "story_role", "complication_type"} <= cols)
        self.assertEqual(len(store.snapshot()["story"]), 5)
        store.apply_ops([{"op": "create", "entity": "paper", "data": {"title": "after migration", "c_course": "x"}}])


class FrameworkTests(unittest.TestCase):
    ZH = ("研究假設如下：\nH1：知覺有用性對使用意圖有正向影響。\nH2：知覺易用性正向影響知覺有用性。\n"
          "H3：信任調節知覺有用性與使用意圖之間的關係。\nH4：使用態度在知覺有用性與使用意圖之間具有中介效果。\n"
          "假設五：社會影響會顯著影響使用意圖。\n本研究以問卷調查法進行。")
    EN = ("H1: Perceived usefulness positively affects behavioral intention. H2: Perceived ease of use has a positive effect on "
          "perceived usefulness. H3: Trust moderates the relationship between perceived usefulness and behavioral intention. "
          "H4: Attitude mediates the relationship between perceived ease of use and behavioral intention. "
          "H5a: The amount of training is negatively associated with anxiety.")

    def names(self, result):
        return {v["name_zh"] or v["name_en"]: v for v in result["variables"]}

    def test_rules_chinese(self):
        r = integ.extract_framework_rules(self.ZH)
        names = self.names(r)
        self.assertEqual(set(names), {"知覺有用性", "知覺易用性", "信任", "使用態度", "使用意圖", "社會影響"})
        self.assertEqual(names["信任"]["role"], "mod")
        self.assertEqual(names["使用態度"]["role"], "med")
        self.assertEqual(names["使用意圖"]["role"], "dv")
        self.assertEqual(names["知覺易用性"]["role"], "iv")
        labels = {(x["source"], x["target"], x["kind"]): (x["label"], x["sign"]) for x in r["relations"]}
        self.assertEqual(labels[("知覺有用性", "使用意圖", "effect")], ("H1", "+"))
        self.assertEqual(labels[("社會影響", "使用意圖", "effect")][0], "H5")
        mod = next(x for x in r["relations"] if x["kind"] == "moderates")
        base = r["relations"][mod["moderates"]]
        self.assertEqual((mod["source"], base["source"], base["target"]), ("信任", "知覺有用性", "使用意圖"))
        self.assertEqual(len(r["sentences"]), 5)  # the method sentence is ignored

    def test_rules_english(self):
        r = integ.extract_framework_rules(self.EN)
        names = self.names(r)
        self.assertIn("Attitude", names)
        self.assertIn("amount of training", names)
        neg = next(x for x in r["relations"] if x["label"] == "H5a")
        self.assertEqual(neg["sign"], "-")
        self.assertEqual(names["Trust"]["role"], "mod")

    def test_rules_nothing(self):
        self.assertEqual(integ.extract_framework_rules("今天天氣很好，我們去散步。")["variables"], [])

    def test_read_docx(self):
        import io
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("word/document.xml", '<w:document><w:body><w:p><w:r><w:t>H1：系統品質會影響滿意度</w:t></w:r></w:p>'
                                            '<w:p><w:r><w:t>H2: A &amp; B affects C</w:t></w:r></w:p></w:body></w:document>')
        text = integ.read_document(buf.getvalue(), "draft.docx")
        self.assertIn("H1：系統品質會影響滿意度\n", text)
        self.assertIn("A & B", text)
        with self.assertRaises(ValueError):
            integ.read_document(b"%PDF", "x.pdf")
        self.assertEqual(integ.read_document("中文".encode("cp950"), "a.txt"), "中文")

    def test_normalize_ai(self):
        raw = {"variables": [{"key": "pu", "role": "iv", "name_en": "Perceived usefulness"}, {"key": "bi", "role": "dv", "name_en": "Intention"},
                             {"key": "tr", "role": "weird", "name_zh": "信任"}, {"key": "ghost"}],
               "relations": [{"source": "pu", "target": "bi", "kind": "effect", "sign": "+", "label": "H1"},
                             {"source": "tr", "kind": "moderates", "moderates_source": "pu", "moderates_target": "bi", "label": "H2"},
                             {"source": "pu", "target": "nope"}]}
        r = integ.normalize_framework(raw)
        self.assertEqual(len(r["variables"]), 3)
        self.assertEqual(len(r["relations"]), 2)
        self.assertEqual(self.names(r)["信任"]["role"], "mod")
        self.assertEqual(r["relations"][1]["moderates"], 0)

    def test_relation_entity(self):
        d = tempfile.mkdtemp()
        try:
            store = Store(Path(d))
            res = store.apply_ops([
                {"op": "create", "entity": "variable", "ref": "x", "data": {"symbol": "X1"}},
                {"op": "create", "entity": "variable", "ref": "y", "data": {"symbol": "Y1", "role": "dv"}},
                {"op": "create", "entity": "variable", "ref": "z", "data": {"symbol": "Z1", "role": "mod"}},
                {"op": "create", "entity": "relation", "ref": "r", "data": {"source_id": "$x", "target_id": "$y", "sign": "+", "label": "H1"}},
                {"op": "create", "entity": "relation", "data": {"source_id": "$z", "target_id": "$y", "kind": "moderates", "moderates_id": "$r"}},
            ])
            rels = store.snapshot()["relations"]
            self.assertEqual([r["kind"] for r in rels], ["effect", "moderates"])
            with self.assertRaises(ValidationError):
                store.apply_ops([{"op": "create", "entity": "relation", "data": {"source_id": res[0]["id"], "target_id": res[0]["id"]}}])
            with self.assertRaises(ValidationError):
                store.apply_ops([{"op": "create", "entity": "relation", "data": {"source_id": res[0]["id"], "target_id": res[1]["id"], "sign": "?"}}])
            store.apply_ops([{"op": "delete", "entity": "variable", "id": res[0]["id"]}])  # X1 gone: its path goes, the moderation stays unlinked
            rels = store.snapshot()["relations"]
            self.assertEqual(len(rels), 1)
            self.assertIsNone(rels[0]["moderates_id"])
        finally:
            shutil.rmtree(d, ignore_errors=True)


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
        code, body2 = self.req("/api/import/bibtex", raw=body, headers={"Content-Type": "text/plain"})
        self.assertEqual(json.loads(body2)["imported"], 0)
        self.assertEqual(self.req("/api/upload?stage_id=abc", raw=b"x", headers={"X-Filename": "a.txt"})[0], 400)
        code, body = self.req("/api/upload", raw=b"x", headers={"X-Filename": ".."})
        self.assertEqual(json.loads(body)["name"], "upload.bin")

    def test_checkin(self):
        stages = self.store.snapshot()["stages"]
        stage = next(s for s in stages if s["key"] == "analysis")
        code, body = self.req("/api/upload", raw=b"print(1)", headers={"X-Filename": "analysis_regression.py"})
        fid = json.loads(body)["id"]
        code, body = self.req("/api/classify", {"names": ["analysis_regression.py"]})
        self.assertEqual(json.loads(body)["stage_id"], stage["id"])
        self.assertEqual(self.req("/api/checkin", {"stage_id": stage["id"], "note": "  "})[0], 400)
        task = next(t for t in self.store.snapshot()["tasks"] if t["stage_id"] == stage["id"])
        code, body = self.req("/api/checkin", {"stage_id": stage["id"], "note": "cleaned the data", "file_ids": [fid],
                                               "done_task_ids": [task["id"]], "due_date": "2027-01-31", "goal": "all hypotheses tested",
                                               "project_deadline": "2027-06-30"})
        self.assertEqual(code, 200, body)
        after = self.store.get("stage", stage["id"])
        self.assertEqual((after["status"], after["progress"], after["due_date"], after["goal"]), ("active", 33, "2027-01-31", "all hypotheses tested"))
        self.assertEqual(self.store.get("file", fid)["stage_id"], stage["id"])
        log = self.store.snapshot()["updates"][0]
        self.assertEqual((log["note"], log["progress_before"], log["progress_after"]), ("cleaned the data", 0, 33))
        self.assertEqual(self.store.settings()["project_deadline"], "2027-06-30")
        code, body = self.req("/api/checkin", {"stage_id": stage["id"], "note": "more", "progress": 70})
        self.assertEqual(self.store.get("stage", stage["id"])["progress"], 70)
        code, body = self.req("/api/usage")
        self.assertIn("openalex", json.loads(body)["providers"])
        self.assertEqual(self.req("/api/ai/suggest", {"stage_id": stage["id"], "note": "x"})[0], 400)

    def test_literature_watch(self):
        original = integ.search
        calls = []

        def fake(provider, query, settings, **kw):
            calls.append(provider)
            if provider == "wos":
                raise ValueError("no key")
            return [{"title": f"{provider} paper on {query}", "authors": "A", "year": 2025, "doi": f"10.1/{provider}", "provider": provider},
                    {"title": "Shared paper", "doi": "10.1/shared", "provider": provider}]

        integ.search = fake
        try:
            stage = self.store.snapshot()["stages"][1]
            before = len(self.store.list_proposals())
            prop = self.app.literature_watch(stage, "trust", ["openalex", "wiley", "wos"], "note")
            self.assertEqual(calls, ["openalex", "wiley", "wos"])
            pending = self.store.list_proposals()
            self.assertEqual(len(pending), before + 1)
            titles = [o["data"]["title"] for o in pending[0]["ops"]]
            self.assertEqual(sorted(titles), ["Shared paper", "openalex paper on trust", "wiley paper on trust"])  # deduped
            self.assertTrue(all(o["data"]["status"] == "candidate" for o in pending[0]["ops"]))
            self.store.decide(prop["id"], False)
        finally:
            integ.search = original

    def test_ai_suggest_with_fake_provider(self):
        from http.server import BaseHTTPRequestHandler

        seen = {}

        class Fake(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                seen["auth"] = self.headers.get("Authorization")
                seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                stage_tasks = [t for t in ServerTests.store.snapshot()["tasks"] if t["stage_id"] == 3]
                reply = {"choices": [{"message": {"content": "Sure: " + json.dumps({
                    "progress": 55, "done_task_ids": [stage_tasks[0]["id"], 99999], "query": "trust adoption", "summary": "過半"})}}],
                    "usage": {"total_tokens": 321}}
                data = json.dumps(reply).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        fake = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=fake.serve_forever, daemon=True).start()
        try:
            self.store.save_settings({"ai_provider": "custom", "ai_base_url": f"http://127.0.0.1:{fake.server_address[1]}/v1",
                                      "ai_model": "test-model", "ai_api_key": "sk-test", "quota_ai": 1})
            code, body = self.req("/api/ai/suggest", {"stage_id": 3, "note": "screened 40 papers", "files": ["lit.docx"]})
            self.assertEqual(code, 200, body)
            out = json.loads(body)
            self.assertEqual((out["progress"], out["query"], out["tokens"]), (55, "trust adoption", 321))
            self.assertNotIn(99999, out["done_task_ids"])  # invented ids are dropped
            self.assertEqual(seen["auth"], "Bearer sk-test")
            self.assertEqual(seen["body"]["model"], "test-model")
            self.assertEqual(self.store.usage()["providers"]["ai"]["tokens"], 321)
            code, body = self.req("/api/ai/suggest", {"stage_id": 3, "note": "again"})
            self.assertEqual(code, 429)  # daily quota of 1 used up
        finally:
            fake.shutdown()
            fake.server_close()
            self.store.save_settings({"ai_provider": "", "ai_api_key": ""})

    def test_framework_endpoint(self):
        code, body = self.req("/api/framework/extract", {"text": FrameworkTests.ZH})
        self.assertEqual(code, 200, body)
        out = json.loads(body)
        self.assertEqual((out["method"], len(out["variables"])), ("rules", 6))
        code, body = self.req("/api/framework/extract", raw=FrameworkTests.EN.encode(), headers={"X-Filename": "draft.md"})
        self.assertEqual(json.loads(body)["method"], "rules")
        self.assertEqual(self.req("/api/framework/extract", {"text": "short"})[0], 400)
        self.assertEqual(self.req("/api/framework/extract", raw=b"%PDF-1.4", headers={"X-Filename": "a.pdf"})[0], 400)
        self.assertEqual(self.req("/api/framework/extract?ai=1", {"text": FrameworkTests.ZH})[0], 400)  # AI not configured
        self.store.apply_ops([{"op": "create", "entity": "variable", "data": {"symbol": "X9", "name_zh": "信任"}}])
        out = json.loads(self.req("/api/framework/extract", {"text": FrameworkTests.ZH})[1])
        trust = next(v for v in out["variables"] if v["name_zh"] == "信任")
        self.assertTrue(trust.get("existing_id"))

    def test_exports_one_shot_download(self):
        name = "我的研究 · 論文口試.pptx"
        code, body = self.req("/api/exports", raw=b"PK\x03\x04deck", headers={"X-Filename": urllib.request.quote(name)})
        self.assertEqual(code, 200, body)
        url = json.loads(body)["url"]
        self.assertEqual(self.req(url, token=False)[0], 403)  # needs the page token in the query
        r = urllib.request.Request(self.url + url + "?token=" + urllib.request.quote(self.app.token))
        with urllib.request.urlopen(r, timeout=10) as resp:
            self.assertEqual(resp.read(), b"PK\x03\x04deck")
            disp = resp.headers["Content-Disposition"]
            self.assertIn("filename*=UTF-8''" + urllib.request.quote(name), disp)
            self.assertIn("presentationml", resp.headers["Content-Type"])
        self.assertEqual(self.req(url + "?token=" + urllib.request.quote(self.app.token), token=False)[0], 404)  # one shot
        self.assertFalse(any((Path(self.dir) / "uploads" / ".exports").iterdir()))

    def test_slides_ai_with_fake_provider(self):
        from http.server import BaseHTTPRequestHandler

        class Fake(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers["Content-Length"]))
                reply = {"choices": [{"message": {"content": json.dumps({
                    "messages": {"overview": "進度穩定", "evil": "x"}, "notes": {"overview": "講稿內容", "model": 5}})}}],
                    "usage": {"total_tokens": 50}}
                data = json.dumps(reply).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        fake = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=fake.serve_forever, daemon=True).start()
        try:
            self.assertEqual(self.req("/api/slides/ai", {"sections": ["overview"]})[0], 400)  # AI not configured
            self.store.save_settings({"ai_provider": "custom", "ai_base_url": f"http://127.0.0.1:{fake.server_address[1]}/v1",
                                      "ai_model": "m", "ai_api_key": "k", "quota_ai": 10})
            self.assertEqual(self.req("/api/slides/ai", {"sections": ["bogus"]})[0], 400)
            code, body = self.req("/api/slides/ai", {"sections": ["overview", "model"], "instructions": "口試", "lang": "zh"})
            self.assertEqual(code, 200, body)
            out = json.loads(body)
            self.assertEqual(out["messages"], {"overview": "進度穩定"})  # unknown keys and non-text dropped
            self.assertEqual(out["notes"], {"overview": "講稿內容"})
        finally:
            fake.shutdown()
            fake.server_close()
            self.store.save_settings({"ai_provider": "", "ai_api_key": ""})

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
        self.assertEqual(ops[0]["data"], {"progress": 50})
        self.assertEqual(ops[0]["append"], {"notes": "new"})
        self.assertEqual(ops[1], {"op": "update", "entity": "task", "id": 5, "data": {"done": True}})
        err = mcp_server.handle(hub, {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "nope", "arguments": {}}})
        self.assertTrue(err["result"]["isError"])
        self.assertEqual(mcp_server.handle(hub, {"jsonrpc": "2.0", "id": 5, "method": "bogus"})["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
