"""Sample content for trying the dashboard: ``python -m research_hub --demo``.

Uses a classic technology-acceptance example with real, well-known references so
the RQ → variable → paper links look like a real study. Only applied to an empty
workspace.
"""
from __future__ import annotations

from .store import Store

PAPERS = [
    dict(ref="davis", title="Perceived usefulness, perceived ease of use, and user acceptance of information technology",
         authors="Davis, F. D.", year=1989, venue="MIS Quarterly", doi="10.2307/249008", status="done", rating=5, tags="TAM, foundational"),
    dict(ref="utaut", title="User acceptance of information technology: Toward a unified view",
         authors="Venkatesh, V. ; Morris, M. G. ; Davis, G. B. ; Davis, F. D.", year=2003, venue="MIS Quarterly",
         doi="10.2307/30036540", status="reading", rating=5, tags="UTAUT"),
    dict(ref="gefen", title="Trust and TAM in online shopping: An integrated model",
         authors="Gefen, D. ; Karahanna, E. ; Straub, D. W.", year=2003, venue="MIS Quarterly", doi="10.2307/30036519",
         status="to_read", rating=4, tags="trust, e-commerce"),
    dict(ref="baron", title="The moderator–mediator variable distinction in social psychological research",
         authors="Baron, R. M. ; Kenny, D. A.", year=1986, venue="Journal of Personality and Social Psychology",
         doi="10.1037/0022-3514.51.6.1173", status="done", rating=4, tags="method, mediation"),
]

VARIABLES = [
    dict(ref="x1", symbol="X1", role="iv", name_zh="知覺有用性", name_en="Perceived usefulness",
         definition="使用者相信使用系統能提升其工作績效的程度。", measurement="Davis (1989) 六題，Likert 7 點"),
    dict(ref="x2", symbol="X2", role="iv", name_zh="知覺易用性", name_en="Perceived ease of use",
         definition="使用者認為使用系統不需費力的程度。", measurement="Davis (1989) 六題，Likert 7 點"),
    dict(ref="m1", symbol="M1", role="med", name_zh="使用態度", name_en="Attitude toward using"),
    dict(ref="z1", symbol="Z1", role="mod", name_zh="信任", name_en="Trust", definition="對系統與服務提供者的信任程度。"),
    dict(ref="y1", symbol="Y1", role="dv", name_zh="使用意圖", name_en="Behavioral intention",
         measurement="Venkatesh et al. (2003) 三題"),
    dict(ref="c1", symbol="C1", role="ctrl", name_zh="使用經驗", name_en="Prior experience"),
]

LINKS = [("x1", "davis", "defines"), ("x1", "utaut", "supports"), ("x2", "davis", "defines"), ("x2", "gefen", "supports"),
         ("m1", "baron", "mentions"), ("z1", "gefen", "supports"), ("y1", "utaut", "measures"), ("y1", "davis", "supports")]


def apply(store: Store) -> bool:
    snap = store.snapshot()
    if snap["papers"] or snap["variables"] or snap["rqs"]:
        return False
    ops = []
    for p in PAPERS:
        data = {k: v for k, v in p.items() if k != "ref"}
        ops.append({"op": "create", "entity": "paper", "ref": p["ref"], "data": {**data, "source": "demo"}})
    for v in VARIABLES:
        ops.append({"op": "create", "entity": "variable", "ref": v["ref"], "data": {k: x for k, x in v.items() if k != "ref"}})
    for a, b, ev in LINKS:
        ops.append({"op": "link", "link": "variable_paper", "a": f"${a}", "b": f"${b}", "data": {"evidence": ev}})
    ops += [
        {"op": "create", "entity": "rq", "ref": "rq1", "data": {"code": "RQ1", "status": "refined",
         "text": "知覺有用性與知覺易用性如何影響使用者的使用意圖？",
         "hypothesis": "H1: 知覺有用性正向影響使用意圖；H2: 知覺易用性正向影響使用意圖。"}},
        {"op": "create", "entity": "rq", "ref": "rq2", "data": {"code": "RQ2", "status": "draft",
         "text": "信任是否調節知覺有用性與使用意圖之間的關係？", "hypothesis": "H3: 信任越高，X1 → Y1 的效果越強。"}},
    ]
    for rq, vs in (("rq1", ["x1", "x2", "y1"]), ("rq2", ["x1", "z1", "y1"])):
        ops += [{"op": "link", "link": "rq_variable", "a": f"${rq}", "b": f"${v}"} for v in vs]
    ops += [{"op": "link", "link": "rq_paper", "a": "$rq1", "b": "$davis"}, {"op": "link", "link": "rq_paper", "a": "$rq2", "b": "$gefen"}]
    stages = {s["key"]: s for s in snap["stages"]}
    if "topic" in stages:
        ops.append({"op": "update", "entity": "stage", "match": {"key": "topic"}, "data": {"status": "done", "start_date": "2026-09-01"}})
    if "literature" in stages:
        ops.append({"op": "update", "entity": "stage", "match": {"key": "literature"},
                    "data": {"status": "active", "progress": 60, "start_date": "2026-09-20", "due_date": "2026-12-15"}})
    if "rq" in stages:
        ops.append({"op": "update", "entity": "stage", "match": {"key": "rq"}, "data": {"status": "active", "progress": 35, "due_date": "2026-12-31"}})
    store.apply_ops(ops, actor="demo")
    if "literature" in stages:
        store.propose("demo agent", "Literature screening finished: 1 new paper, stage 60% → 75%", [
            {"op": "update", "entity": "stage", "match": {"key": "literature"}, "data": {"progress": 75}},
            {"op": "create", "entity": "paper", "ref": "p", "data": {
                "title": "Introduction to mediation, moderation, and conditional process analysis", "authors": "Hayes, A. F.",
                "year": 2018, "venue": "Guilford Press", "status": "candidate", "source": "mcp"}},
            {"op": "link", "link": "variable_paper", "a": next(v for v in store.snapshot()["variables"] if v["symbol"] == "M1")["id"],
             "b": "$p", "data": {"evidence": "measures"}},
        ], "Example of an agent result waiting for your confirmation.")
    return True
