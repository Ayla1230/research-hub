"""Sample content for trying the dashboard: ``python -m research_hub --demo``.

Uses a classic technology-acceptance example with real, well-known references so
the RQ → variable → paper links look like a real study. Only applied to an empty
workspace.
"""
from __future__ import annotations

from .store import Store

PAPERS = [
    dict(ref="davis", title="Perceived usefulness, perceived ease of use, and user acceptance of information technology",
         authors="Davis, F. D.", year=1989, venue="MIS Quarterly", doi="10.2307/249008", status="done", rating=5, tags="TAM, foundational",
         c_common="組織大量投資資訊系統，但使用率常不如預期；既有研究用各種變數預測使用行為。",
         c_complication="用來預測使用的主觀信念缺乏經過驗證的量表，難以比較與累積。", complication_type="problem",
         c_concern="沒有可靠的測量，就無法解釋或預測使用者是否接受新系統。",
         c_course="發展並驗證「知覺有用性」與「知覺易用性」量表，以兩個研究檢驗其與使用的關係。",
         c_contribution="知覺有用性比易用性更能預測使用；提供後續 TAM 研究共用的量表。", story_role="common"),
    dict(ref="utaut", title="User acceptance of information technology: Toward a unified view",
         authors="Venkatesh, V. ; Morris, M. G. ; Davis, G. B. ; Davis, F. D.", year=2003, venue="MIS Quarterly",
         doi="10.2307/30036540", status="reading", rating=5, tags="UTAUT"),
    dict(ref="gefen", title="Trust and TAM in online shopping: An integrated model",
         authors="Gefen, D. ; Karahanna, E. ; Straub, D. W.", year=2003, venue="MIS Quarterly", doi="10.2307/30036519",
         status="to_read", rating=4, tags="trust, e-commerce",
         c_common="TAM 能解釋多數資訊科技的採用。", c_complication="網路購物還涉及對賣家的信任，TAM 原本的信念沒有涵蓋。",
         complication_type="puzzle", c_concern="線上交易的採用可能取決於信任，而不只是系統好不好用。",
         c_course="把信任整合進 TAM，以線上購物者的問卷資料檢驗。", c_contribution="信任與 TAM 信念共同影響線上購物意圖。",
         story_role="complication"),
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
    story = {
        "common": "我們已知知覺有用性與易用性能解釋多數資訊系統的使用意圖。",
        "complication": "然而在高風險的線上情境，使用者即使覺得系統有用仍可能遲疑，既有解釋不足以說明。",
        "concern": "這很重要，因為忽略信任會讓企業高估功能改善帶來的採用率。",
        "course": "本研究把信任作為調節變數，檢驗知覺有用性對使用意圖的效果何時增強或減弱。",
        "contribution": "研究結果將說明 TAM 的邊界條件，並提供提升信任的實務建議。",
    }
    ops += [{"op": "update", "entity": "story", "match": {"key": k}, "data": {"sentence": v}} for k, v in story.items()]
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
