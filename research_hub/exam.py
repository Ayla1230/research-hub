"""Exam preparation: a starter bank of essay questions, question prediction, analysis and practice feedback.

Everything works without an AI key (rule-based templates and keyword coverage); with the AI assistant set
up in Settings the prediction, analysis and feedback become specific to the question.
The starter questions are original wording on standard research-methods topics.
"""
from __future__ import annotations

import re
from collections import Counter

from . import topic as topic_mod

# (folder, difficulty, question, answer outline)
SEED = [
    ("研究設計", "medium", "研究者若想主張「X 造成 Y」，需要滿足哪些條件？橫斷面問卷資料為何難以支持因果推論？請說明可行的補強設計。",
     "1. 因果三要件：共變、時間先後、排除替代解釋；再加上解釋機制（中介）\n2. 橫斷面的限制：無法確立時序、同源偏誤、反向因果\n3. 補強：分時點／縱貫、多來源資料、實驗或準實驗、控制變數與穩健性分析\n4. 結論：方法要能回答研究問題"),
    ("研究設計", "medium", "請說明投稿前應自我檢核的研究設計問題，並各舉一個常見缺失。",
     "1. 問題與資料的時間、因果邏輯是否相符\n2. 樣本與程序是否適合\n3. 構念定義與測量效度\n4. 控制變數與中介的理論依據\n5. 誠實評估限制並以其他研究補強\n每點各舉一例"),
    ("方法契合", "hard", "何謂方法契合（methodological fit）？請依理論發展成熟度（新生、中間、成熟）說明適合的研究問題、資料型態與分析方法。",
     "1. 定義：研究問題、既有文獻、研究設計與理論貢獻之間的內部一致性（Edmondson & McManus, 2007）\n2. 新生理論：開放式問題、質性資料、歸納找型態\n3. 中間理論：提出新構念間關係、質量並用\n4. 成熟理論：聚焦假設、量化資料、統計檢定\n5. 不契合的後果與例子"),
    ("方法契合", "medium", "若研究主題的既有理論仍在萌芽階段，研究者卻直接發放大樣本問卷檢驗假設，可能產生哪些問題？應如何調整？",
     "1. 問題：構念未明、量表缺乏效度、假設缺乏依據，結果難以解釋\n2. 調整：先以訪談／觀察歸納構念與機制，再發展量表\n3. 連結方法契合的對角線概念"),
    ("共同方法變異", "medium", "何謂共同方法變異（CMV）？請說明其來源，以及事前程序控制與事後統計控制的做法與限制。",
     "1. 定義：由測量方法而非構念造成的變異\n2. 來源：同一評量者、題項特性、題項情境、測量情境\n3. 程序控制：不同來源、時間／心理／方法分離、匿名、降低評價顧慮、改善題項\n4. 統計控制：Harman 單因子（限制大）、未測量潛在方法因子、標記變數\n5. 結論：程序優先於統計"),
    ("共同方法變異", "easy", "為什麼自變數與依變數都由同一位受訪者在同一時間填答會有問題？請提出兩種改善設計。",
     "1. 同源偏誤使相關被高估或低估\n2. 一致性動機、社會期許、情緒狀態\n3. 改善：主管評／客觀資料、分時點測量\n4. 各自的成本與限制"),
    ("控制變數", "medium", "研究者常「把手邊有的控制變數全部放進模型」。請說明這種做法的問題，以及選擇與報告控制變數的原則。",
     "1. 問題：降低檢定力、改變係數意義、可能控制掉部分機制、結果難以複製\n2. 選擇原則：與 Y 有理論關聯、與 X 有關聯、不是核心機制的一部分\n3. 報告：說明納入理由、如何測量、提供敘述統計與相關、比較有無控制變數的結果（Becker, 2005）"),
    ("控制變數", "hard", "何謂「無效的控制變數」（impotent control variables）？納入與自變數、依變數皆無關的控制變數會造成什麼影響？",
     "1. 定義：與依變數無關的控制變數\n2. 影響：耗損自由度、降低檢定力、增加型二錯誤\n3. 若控制變數其實是中介的一部分會低估效果\n4. 建議：理論依據＋有無控制的結果並陳"),
    ("量表", "medium", "研究者改編既有量表時常見哪些做法？各自需要提供哪些效度證據？",
     "1. 改編類型：翻譯、縮短、事後刪題、改反應尺度、改措辭、改指稱對象（自評→他評、個人→群體）\n2. 翻譯：回譯＋測量恆等性\n3. 縮短：理論與實證兼顧選題、透明報告\n4. 事後刪題：原則上避免\n5. 指稱對象改變：CFA／多層次 CFA\n6. 結論：透明報告並附效度證據（Heggestad et al., 2019）"),
    ("量表", "easy", "請說明構念定義不清時常見的 jingle 與 jangle 謬誤，並舉例說明其對研究累積的影響。",
     "1. jingle：同名不同義\n2. jangle：異名同義\n3. 影響：文獻無法比較、構念增生\n4. 對策：先定義再測量，檢驗區辨效度"),
    ("質性研究", "medium", "請說明 Gioia 方法的資料結構（一階概念、二階主題、彙總構面），以及它如何提升質性研究的嚴謹性。",
     "1. 一階：受訪者用語\n2. 二階：研究者的理論性主題\n3. 彙總構面\n4. 資料結構圖呈現由資料到理論的推演\n5. 再發展成動態的紮根模型\n6. 嚴謹性：可追溯、兼顧受訪者聲音與理論"),
    ("質性研究", "medium", "主題分析（thematic analysis）如何達到可信賴性（trustworthiness）？請依可信性、可遷移性、可靠性與可確認性說明。",
     "1. 可信性：長期投入、三角檢證、成員檢核\n2. 可遷移性：厚實描述\n3. 可靠性：過程可稽核\n4. 可確認性：反思、稽核軌跡\n5. 對應主題分析六階段的具體做法（Nowell et al., 2017）"),
    ("質性研究", "hard", "面對重大社會挑戰（grand challenges）這類複雜議題，為何歸納式方法特別合適？請說明其貢獻與限制。",
     "1. 議題特性：複雜、不確定、跨層次\n2. 既有理論不足以解釋，需要從現象歸納\n3. 貢獻：新構念、過程與機制\n4. 限制：可類推性、研究者主觀\n5. 嚴謹性的確保方式"),
    ("混合方法", "medium", "何謂三角檢證（triangulation）？請說明混合方法研究設計的類型與適用時機。",
     "1. 三角檢證：以不同資料、方法、研究者、理論交叉驗證\n2. 設計：聚合式、解釋性序列（量→質）、探索性序列（質→量）\n3. 選擇依據：研究目的、時序、權重、整合點\n4. 挑戰：資源、結果不一致時的處理"),
    ("論文寫作", "medium", "請以 5C（Common ground、Complication、Concern、Course of action、Contribution）說明一篇論文的緒論如何說出有吸引力的故事。",
     "1. Common ground：讀者已同意的共識\n2. Complication：缺口、問題或謎題\n3. Concern：為什麼重要\n4. Course of action：本研究怎麼做\n5. Contribution：對理論與實務的貢獻\n6. 以自己的題目示範（Lange & Pfarrer, 2017）"),
    ("論文寫作", "easy", "研究題目為什麼需要「原因」與「故事」？請說明如何說服讀者這個題目值得做。",
     "1. 題目不等於變數的排列\n2. 原因：現象或文獻中的張力\n3. 故事：誰會受益、能解決什麼\n4. 檢查新穎性與重疊度\n5. 以 5C 串起來"),
]

OUTLINE_TEMPLATE = ("1. 破題：重述題意並定義關鍵名詞（{terms}）\n2. 理論或文獻依據：誰提出、核心主張\n3. 分點論述：比較、條件或步驟，每點附一句理由\n"
                    "4. 舉例：用自己的研究題目或一篇文獻說明\n5. 評論與限制\n6. 結論：一句話回答題目")
OUTLINE_TEMPLATE_EN = ("1. Opening: restate the question and define key terms ({terms})\n2. Theory or literature: who proposed it and the core claim\n"
                       "3. Main points: compare, conditions or steps, one reason each\n4. Example: your own topic or one paper\n5. Critique and limits\n6. Conclusion: answer in one sentence")


def seed_ops(existing: list[dict]) -> list[dict]:
    have = {q["text"].strip() for q in existing}
    return [{"op": "create", "entity": "question", "data": {"folder": folder, "kind": "predicted", "difficulty": level, "text": text,
                                                            "outline": outline, "source": "Research Hub 範例題庫", "minutes": 30}}
            for folder, level, text, outline in SEED if text not in have]


def key_terms(text: str, limit: int = 8) -> list[str]:
    return [w for w in topic_mod.tokens(text) if len(w) > 1][:limit]


def outline_for(question: str, lang: str = "zh") -> dict:
    terms = "、".join(key_terms(question, 5)) or "…"
    template = OUTLINE_TEMPLATE_EN if lang == "en" else OUTLINE_TEMPLATE
    verbs = [v for v in ("比較", "說明", "評論", "舉例", "定義", "分析", "設計", "compare", "explain", "evaluate", "define", "design") if v in question.lower()]
    asks = len(re.findall(r"[？?]|並|以及|；", question)) + 1
    analysis = (f"Key terms: {terms}\nTask verbs: {', '.join(verbs) or 'explain'}\nParts to answer: about {asks}" if lang == "en"
                else f"關鍵詞：{terms}\n題目要求的動作：{'、'.join(verbs) or '說明'}\n需要回答的子題：約 {asks} 個，逐一對應、不要漏答")
    return {"analysis": analysis, "outline": template.format(terms=terms), "method": "rules"}


def predict_rules(snapshot: dict, folder: str = "", lang: str = "zh") -> list[dict]:
    """Candidate questions from what the workspace already holds: frequent past topics, 5C reading notes, variables."""
    out: list[dict] = []
    past = [q for q in snapshot.get("questions", []) if q["kind"] == "past" and (not folder or q["folder"] == folder)]
    counts = Counter(w for q in past for w in set(key_terms(q["text"], 12)))
    asked = {q["text"].strip() for q in snapshot.get("questions", [])}
    for term, n in counts.most_common(6):
        if n < 2:
            break
        out.append({"text": f"「{term}」在歷屆考題出現 {n} 次。請完整說明{term}的定義、理論基礎與研究上的應用，並評論其限制。" if lang != "en"
                    else f"“{term}” appeared in {n} past questions. Define it, explain its theoretical basis and research use, and discuss its limits.",
                    "folder": folder or "考題預測", "reason": f"past ×{n}", "difficulty": "medium"})
    for p in snapshot.get("papers", []):
        if folder and (p.get("folder") or "") != folder:
            continue
        if not (p.get("c_complication") or p.get("c_contribution")):
            continue
        who = (p.get("authors") or "").split(";")[0].split(",")[0].strip() or p["title"][:30]
        ref = f"{who} ({p.get('year') or 'n.d.'})"
        out.append({"text": f"請說明 {ref} 一文想解決的缺口、採取的研究方法與主要貢獻，並評論其研究設計的限制。" if lang != "en"
                    else f"Explain the gap, method and main contribution of {ref}, and critique its research design.",
                    "folder": folder or p.get("folder") or "文獻解析", "reason": "5C notes", "difficulty": "medium", "paper_id": p["id"]})
    core = [v for v in snapshot.get("variables", []) if v["role"] in ("iv", "dv", "med", "mod")]
    for v in core[:4]:
        nm = v.get("name_zh") or v.get("name_en") or v["symbol"]
        out.append({"text": f"請定義「{nm}」，說明常用的測量方式與效度證據，並討論以自評問卷測量時可能的偏誤。" if lang != "en"
                    else f"Define “{v.get('name_en') or nm}”, describe common measures and validity evidence, and discuss biases of self-report.",
                    "folder": folder or "我的研究", "reason": "my variables", "difficulty": "easy"})
    seen, unique = set(), []
    for q in out:
        if q["text"] not in asked and q["text"] not in seen:
            seen.add(q["text"])
            unique.append(q)
    return unique[:12]


def coverage(outline: str, answer: str) -> dict:
    """How many outline points the answer touches (keyword overlap per point). Rule-based feedback."""
    points = [re.sub(r"^\s*\d+[.、)]\s*", "", line).strip() for line in (outline or "").splitlines() if line.strip()]
    answer_tokens = set(topic_mod.tokens(answer))
    answer_text = answer or ""
    hit, missed = [], []
    for point in points:
        words = [w for w in topic_mod.tokens(point) if len(w) > 1]
        found = sum(1 for w in words if w in answer_tokens or w in answer_text)
        (hit if words and found / len(words) >= 0.34 else missed).append(point)
    length = len(re.findall(r"[㐀-鿿]", answer_text)) + len(re.findall(r"[A-Za-z]+", answer_text))
    pct = round(100 * len(hit) / len(points)) if points else 0
    structure = 10 if len(re.findall(r"\n\s*\S", answer_text)) >= 3 else 0
    score = max(0, min(100, round(pct * 0.75 + min(length, 800) / 800 * 15 + structure)))
    return {"score": score, "coverage": pct, "hit": hit, "missed": missed, "length": length, "method": "rules"}


def predict_prompt(snapshot: dict, folder: str, lang: str) -> tuple[str, str]:
    past = [q["text"][:300] for q in snapshot.get("questions", []) if q["kind"] == "past" and (not folder or q["folder"] == folder)][:25]
    notes = [f"{p['title'][:120]} — gap: {(p.get('c_complication') or '')[:200]} contribution: {(p.get('c_contribution') or '')[:200]}"
             for p in snapshot.get("papers", []) if (not folder or (p.get("folder") or "") == folder)][:20]
    language = "English" if lang == "en" else "Traditional Chinese (Taiwan)"
    system = ("You are an examiner for a graduate research-methods essay exam. From the past questions and reading notes, predict the essay "
              f"questions most likely to be asked next. Write in {language}. Reply with ONE JSON object: "
              '{"questions": [{"text": str, "reason": str, "difficulty": "easy"|"medium"|"hard", "outline": str}]} with 6 questions. '
              "Each outline is a numbered answer structure, one point per line.")
    return system, f"Folder/topic: {folder or '-'}\nPast questions:\n- " + "\n- ".join(past or ["(none)"]) + "\n\nReading notes:\n- " + "\n- ".join(notes or ["(none)"])


def analyze_prompt(question: dict, paper: dict | None, lang: str) -> tuple[str, str]:
    language = "English" if lang == "en" else "Traditional Chinese (Taiwan)"
    system = ("You coach a graduate student for an essay exam. Analyse the question: what it really asks, key terms, the theory or papers "
              f"to cite, common mistakes. Then give a numbered answer outline, one point per line. Write in {language}. "
              'Reply with ONE JSON object: {"analysis": str, "outline": str}.')
    user = "Question: " + question["text"][:2000]
    if paper:
        user += f"\nRelated paper: {paper['title']} — {(paper.get('c_complication') or '')[:300]} {(paper.get('c_contribution') or '')[:300]}"
    return system, user


def grade_prompt(question: dict, answer: str, lang: str) -> tuple[str, str]:
    language = "English" if lang == "en" else "Traditional Chinese (Taiwan)"
    system = ("You grade a graduate essay-exam answer strictly but constructively. Score 0-100 on: answering every part of the question, "
              "correct concepts and citations, structure, examples, and critique. "
              f"Write in {language}. Reply with ONE JSON object: "
              '{"score": int, "strengths": str, "gaps": str, "rewrite_tip": str}.')
    return system, f"Question: {question['text'][:2000]}\nExpected outline:\n{(question.get('outline') or '')[:2000]}\n\nAnswer:\n{answer[:8000]}"


# ---------------------------------------------------------------- questions from an uploaded paper
METHODS = [
    (r"問卷|survey|questionnaire", "問卷調查", "a survey"), (r"實驗|experiment|random(ly)? assign", "實驗設計", "an experiment"),
    (r"訪談|interview", "訪談", "interviews"), (r"個案研究|case study", "個案研究", "a case study"),
    (r"縱貫|longitudinal|panel data|time[- ]lagged", "縱貫／分時點資料", "longitudinal data"), (r"次級資料|archival|secondary data", "次級／檔案資料", "archival data"),
    (r"主題分析|thematic analysis", "主題分析", "thematic analysis"), (r"紮根|grounded theory|gioia", "紮根理論／Gioia 方法", "grounded theory"),
    (r"結構方程|SEM\b|structural equation", "結構方程模式", "structural equation modelling"), (r"迴歸|regression", "迴歸分析", "regression"),
    (r"後設分析|meta-analysis", "後設分析", "a meta-analysis"), (r"混合方法|mixed[- ]method", "混合方法", "mixed methods"),
]


def paper_facts(text: str, filename: str = "") -> dict:
    """What a rule-based reader can tell about a paper: title, methods, hypotheses, frequent terms."""
    from . import integrations as integ
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", filename)

    def titleish(ln: str) -> bool:
        if re.match(r"^(abstract|摘要|keywords|doi|https?:|vol\.|©|copyright|journal|article|original|research[- ]article)", ln, re.I) or re.search(r"\d{4}|@|www\.", ln):
            return False
        return (len(ln.split()) >= 4 and len(ln) <= 200) or (topic_mod.has_cjk(ln) and 8 <= len(ln) <= 80)

    head = lines[:25]
    first = next((i for i, ln in enumerate(head) if titleish(ln)), None)
    title = stem
    if first is not None:
        title = head[first]
        if first + 1 < len(head) and titleish(head[first + 1]) and not head[first].endswith((".", "。")) and len(title) < 90:
            title += ("" if topic_mod.has_cjk(title) else " ") + head[first + 1]  # titles often wrap onto a second line
    hits = sorted(((len(re.findall(pattern, text, re.I)), zh, en) for pattern, zh, en in METHODS), reverse=True)
    methods = [(zh, en) for n, zh, en in hits if n >= (3 if len(text) > 5000 else 1)][:2]
    try:
        fw = integ.extract_framework_rules(text[:120_000])
    except Exception:
        fw = {"variables": [], "relations": []}
    names = {v.get("key"): (v.get("name_zh") or v.get("name_en") or "") for v in fw.get("variables", [])}
    short = lambda n: bool(n) and (len(n) <= 16 if topic_mod.has_cjk(n) else len(n.split()) <= 5)  # noqa: E731
    hyps = []
    for r in fw.get("relations", []):
        a, b = names.get(r.get("source")), names.get(r.get("target"))
        if r.get("label") and short(a) and short(b):  # only labelled hypotheses (H1, 假設一): prose is too noisy
            hyps.append({"label": r["label"], "source": a, "target": b, "kind": r.get("kind") or "effect"})
    sample = text[:80_000]
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z\-]{2,}", sample)]
    pairs = Counter(f"{a} {b}" for a, b in zip(words, words[1:]) if a not in topic_mod.EN_STOP and b not in topic_mod.EN_STOP and len(a) > 3 and len(b) > 3)
    singles = Counter(w for w in topic_mod.tokens(sample, unique=False) if (len(w) > 4 or topic_mod.has_cjk(w)) and len(w) > 1)
    generic = {"author", "journal", "table", "figure", "result", "paper", "article", "example", "research", "researcher", "study", "which", "their", "these",
               "content", "downloaded", "subject", "https", "academy", "management", "chapter", "stage", "press", "university", "would", "could", "should", "other", "about", "there", "where", "have", "been", "were", "also", "more", "than", "such", "they", "many"}
    terms = [p for p, n in pairs.most_common(12) if n >= 5 and not (set(p.split()) & generic)][:5]
    covered = set(" ".join(terms).split())
    terms += [w for w, n in singles.most_common(60) if n >= 5 and w not in generic and not any(c.startswith(w[:5]) for c in covered)][: 8 - len(terms)]
    return {"title": title[:200], "methods": methods[:4], "hypotheses": hyps, "terms": terms, "chars": len(text)}


def from_paper_rules(text: str, filename: str = "", folder: str = "", lang: str = "zh") -> dict:
    f = paper_facts(text, filename)
    zh = lang != "en"
    name = f"「{f['title']}」" if zh else f"“{f['title']}”"
    out = []

    def add(q_zh, q_en, o_zh, o_en, level="medium", reason=""):
        out.append({"text": q_zh if zh else q_en, "outline": o_zh if zh else o_en, "difficulty": level, "reason": reason, "folder": folder})

    add(f"請以 5C 架構說明{name}一文：既有共識、研究缺口、為何重要、作者如何解決，以及主要貢獻。", f"Using the 5C structure, explain {name}: common ground, gap, why it matters, course of action and contribution.",
        "1. Common ground：文獻已知什麼\n2. Complication：缺口、問題或謎題\n3. Concern：為什麼重要\n4. Course of action：研究設計與資料\n5. Contribution：理論與實務貢獻",
        "1. Common ground\n2. Complication: the gap\n3. Concern: why it matters\n4. Course of action: design and data\n5. Contribution", "easy", "5C")
    for h in f["hypotheses"][:3]:
        verb = {"moderates": ("調節", "moderates"), "mediates": ("中介", "mediates")}.get(h["kind"], ("影響", "affects"))
        add(f"該文主張「{h['source']}」{verb[0]}「{h['target']}」{('（' + h['label'] + '）') if h['label'] else ''}。請說明其理論推導，並提出至少兩個替代解釋與可檢驗的方法。",
            f"The paper argues that {h['source']} {verb[1]} {h['target']}. Explain the theoretical reasoning and offer at least two alternative explanations and how to test them.",
            f"1. 定義 {h['source']} 與 {h['target']}\n2. 作者的理論機制\n3. 替代解釋一：反向因果或共同原因\n4. 替代解釋二：測量或樣本造成\n5. 如何以設計排除（分時點、實驗、控制變數）",
            "1. Define both constructs\n2. The authors' mechanism\n3. Alternative 1: reverse causality or a common cause\n4. Alternative 2: measurement or sample\n5. Designs that rule them out",
            "hard", h["label"] or "hypothesis")
    if f["methods"]:
        m_zh, m_en = "、".join(m[0] for m in f["methods"]), ", ".join(m[1] for m in f["methods"])
        add(f"該文採用{m_zh}。請評論這樣的研究設計能否回答其研究問題，並說明主要限制與改善方式。", f"The paper uses {m_en}. Evaluate whether this design can answer its research question; discuss limits and improvements.",
            "1. 研究問題的性質（描述、改變、因果）\n2. 設計與問題是否契合（方法契合）\n3. 因果推論三要件是否滿足\n4. 測量：共同方法變異、效度\n5. 樣本與外部效度\n6. 具體改善設計",
            "1. Nature of the question\n2. Methodological fit\n3. Conditions for causal inference\n4. Measurement: CMV, validity\n5. Sample and external validity\n6. Concrete improvements", "medium", m_zh if zh else m_en)
    if f["terms"]:
        terms = "、".join(f["terms"][:3]) if zh else ", ".join(f["terms"][:3])
        add(f"請定義該文的核心概念（{terms}），說明它們之間的關係，並比較與相近概念的差異。", f"Define the paper's core concepts ({terms}), explain how they relate, and distinguish them from neighbouring concepts.",
            "1. 逐一定義\n2. 概念間的關係\n3. 與相近概念的區辨（jingle／jangle）\n4. 常用測量方式\n5. 小結", "1. Definitions\n2. Relations\n3. Distinction from similar concepts\n4. Common measures\n5. Summary", "easy", terms)
    add(f"假設你是{name}的審稿人，請提出三項最重要的批評與具體修改建議。", f"As a reviewer of {name}, give the three most important criticisms with concrete suggestions.",
        "1. 理論：貢獻是否清楚、論證是否充分\n2. 方法：設計、測量、分析\n3. 結果詮釋與限制\n每點：問題 → 為何重要 → 建議", "1. Theory\n2. Method\n3. Interpretation and limits\nFor each: issue → why it matters → suggestion", "hard", "review")
    add("請說明該文的發現如何延伸到你自己的研究題目：可以借用什麼、需要修正什麼？", "Explain how this paper's findings extend to your own topic: what can you borrow and what must change?",
        "1. 該文的核心發現\n2. 與我的題目的連結\n3. 可借用的理論或測量\n4. 情境差異與需要的修正\n5. 我的研究能補上的缺口", "1. Core finding\n2. Link to my topic\n3. What to borrow\n4. Context differences\n5. The gap my study fills", "medium", "my topic")
    return {"questions": out, "facts": f, "method": "rules"}


def from_paper_prompt(text: str, filename: str, lang: str) -> tuple[str, str]:
    language = "English" if lang == "en" else "Traditional Chinese (Taiwan)"
    system = ("You are an examiner for a graduate seminar. Read the paper excerpt and write 6 essay exam questions that test real understanding of THIS "
              "paper: its gap and contribution, theory and hypotheses, research design and measurement, limitations, and extension. Use the paper's own "
              f"constructs and findings; never invent results that are not in the text. Write in {language}. Reply with ONE JSON object: "
              '{"title": str, "questions": [{"text": str, "reason": str, "difficulty": "easy"|"medium"|"hard", "outline": str}]}. '
              "Each outline is a numbered answer structure, one point per line.")
    excerpt = text[:9000] + ("\n…\n" + text[-3000:] if len(text) > 12000 else "")
    return system, f"File: {filename}\n\n{excerpt}"
