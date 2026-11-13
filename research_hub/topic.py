"""Thesis-title check: word segmentation, Chinese → English, overlap with published work, story strength.

Like a password meter for a research topic. A title scores well when (1) few published titles cover the
same combination of concepts, (2) it names concrete constructs, a relationship and a context, and (3) it
comes with a reason and a story: why this matters and who it helps (Lange & Pfarrer, 2017).
"""
from __future__ import annotations

import json
import re
import urllib.parse

from . import integrations as integ

# ---------------------------------------------------------------- segmentation
# Small research lexicon for forward maximum matching; anything else falls back to character bigrams.
GLOSSARY = {
    "知覺有用性": "perceived usefulness", "知覺易用性": "perceived ease of use", "使用意圖": "behavioral intention",
    "使用態度": "attitude", "信任": "trust", "滿意度": "satisfaction", "顧客滿意度": "customer satisfaction",
    "工作滿意度": "job satisfaction", "忠誠度": "loyalty", "顧客忠誠度": "customer loyalty", "品牌忠誠度": "brand loyalty",
    "組織承諾": "organizational commitment", "離職傾向": "turnover intention", "工作績效": "job performance",
    "組織績效": "organizational performance", "績效": "performance", "領導": "leadership", "轉換型領導": "transformational leadership",
    "家長式領導": "paternalistic leadership", "僕人式領導": "servant leadership", "真誠領導": "authentic leadership",
    "組織公民行為": "organizational citizenship behavior", "工作投入": "work engagement", "工作壓力": "job stress",
    "工作倦怠": "burnout", "情緒勞務": "emotional labor", "心理資本": "psychological capital", "自我效能": "self-efficacy",
    "組織氣候": "organizational climate", "組織文化": "organizational culture", "組織認同": "organizational identification",
    "心理契約": "psychological contract", "組織正義": "organizational justice", "知識分享": "knowledge sharing",
    "知識管理": "knowledge management", "創新": "innovation", "創新行為": "innovative behavior", "創造力": "creativity",
    "動態能力": "dynamic capabilities", "吸收能力": "absorptive capacity", "競爭優勢": "competitive advantage",
    "企業社會責任": "corporate social responsibility", "永續": "sustainability", "永續發展": "sustainable development",
    "公司治理": "corporate governance", "數位轉型": "digital transformation", "人工智慧": "artificial intelligence",
    "生成式人工智慧": "generative artificial intelligence", "科技接受模式": "technology acceptance model",
    "社群媒體": "social media", "電子商務": "e-commerce", "網路購物": "online shopping", "行動支付": "mobile payment",
    "購買意圖": "purchase intention", "購買意願": "purchase intention", "品牌形象": "brand image", "品牌": "brand",
    "服務品質": "service quality", "知覺價值": "perceived value", "知覺風險": "perceived risk", "口碑": "word of mouth",
    "價值共創": "value co-creation", "生態系統": "ecosystem", "地方創生": "regional revitalization", "社區": "community",
    "合作社": "cooperative", "利害關係人": "stakeholder", "社會企業": "social enterprise", "社會資本": "social capital",
    "創業": "entrepreneurship", "創業導向": "entrepreneurial orientation", "家族企業": "family business", "中小企業": "SMEs",
    "供應鏈": "supply chain", "策略": "strategy", "人力資源管理": "human resource management", "高績效工作系統": "high-performance work systems",
    "員工": "employee", "主管": "supervisor", "顧客": "customer", "消費者": "consumer", "團隊": "team", "遠距工作": "remote work",
    "工作家庭衝突": "work-family conflict", "幸福感": "well-being", "學習動機": "learning motivation", "學習成效": "learning outcomes",
    "調節": "moderating", "調節效果": "moderating effect", "中介": "mediating", "中介效果": "mediating effect",
    "台灣": "Taiwan", "臺灣": "Taiwan", "銀行業": "banking", "製造業": "manufacturing", "服務業": "service industry",
    "餐旅業": "hospitality", "醫院": "hospital", "護理人員": "nurses", "教師": "teachers", "大學生": "university students",
    "高齡": "aging", "長期照顧": "long-term care", "組織變革": "organizational change", "組織學習": "organizational learning",
    "共同方法變異": "common method variance", "控制變數": "control variables", "方法契合": "methodological fit", "量表": "scale",
    "效度": "validity", "信度": "reliability", "質性研究": "qualitative research", "主題分析": "thematic analysis",
    "三角檢證": "triangulation", "混合方法": "mixed methods", "因果推論": "causal inference", "中介變數": "mediator",
    "調節變數": "moderator", "研究設計": "research design", "紮根理論": "grounded theory", "個案研究": "case study",
    "心理安全感": "psychological safety", "建言行為": "voice behavior", "辱虐管理": "abusive supervision", "職場霸凌": "workplace bullying",
}
ZH_STOP = set("的 之 與 和 及 對 於 在 以 為 例 其 及其 或 而 是 中 從 由 並 等 一 個 性 之間 探討 研究 分析 影響 關係 效果 作用 角色 "
              "視角 觀點 機制 模式 因素 相關 實證 初探 為例 個案 案例 何謂 請說明 說明 請 舉例 為何 如何 哪些 什麼 為什麼 研究者 可能 需要 各自 以及 "
              "並 若 時 常 會 有 做法 常見 提出 產生 造成".split())
EN_STOP = set("a an the of on in at for to and or with by from as is are be its their this that between among into toward towards "
              "study studies research analysis effect effects impact impacts role roles relationship relationships influence "
              "evidence case empirical exploring examining investigating investigation approach perspective based using".split())
ZH_CUT = set("的之與和及對於在以為其或而是從由並等")  # function characters: never part of a term
RELATION = re.compile(r"影響|調節|中介|效果|關係|前因|後果|effect|impact|influence|moderat|mediat|relationship|antecedent|consequence", re.I)
CONTEXT = re.compile(r"以.{2,20}為例|為例|個案|產業|業|台灣|臺灣|evidence from|case of|a study of|in (the )?[A-Z]", re.I)
_CJK = re.compile(r"[㐀-鿿]")
_MAXLEN = max(len(k) for k in GLOSSARY)


def has_cjk(text: str) -> bool:
    return bool(_CJK.search(text or ""))


def _stem(word: str) -> str:
    for suffix, cut in (("ies", 3), ("sses", 2), ("ing", 3), ("es", 2), ("s", 1)):
        if word.endswith(suffix) and len(word) - cut >= 4 and not word.endswith("ss"):
            return word[:-cut] + ("y" if suffix == "ies" else "")
    return word


def segment_zh(text: str, extra: dict | None = None) -> list[str]:
    """Forward maximum matching against the lexicon; unknown runs are cut into bigrams."""
    lexicon = {**GLOSSARY, **(extra or {}), **{w: "" for w in ZH_STOP if len(w) > 1}}
    longest = max(_MAXLEN, max((len(k) for k in lexicon), default=1))
    out, i, run = [], 0, ""

    def flush():
        nonlocal run
        if len(run) == 1:
            out.append(run)
        elif run:
            out.extend(run[j:j + 2] for j in range(len(run) - 1))
        run = ""

    while i < len(text):
        for size in range(min(longest, len(text) - i), 1, -1):
            if text[i:i + size] in lexicon:
                flush()
                out.append(text[i:i + size])
                i += size
                break
        else:
            if _CJK.match(text[i]) and text[i] not in ZH_CUT:
                run += text[i]
            else:
                flush()
            i += 1
    flush()
    return [w for w in out if w not in ZH_STOP]


def tokens(text: str, extra: dict | None = None, unique: bool = True) -> list[str]:
    """Content words of a title, in order and without duplicates. Works for Chinese, English and mixed text."""
    text = (text or "").strip()
    found = []
    for part in re.findall(r"[㐀-鿿]+|[A-Za-z][A-Za-z\-']*", text):
        if _CJK.match(part):
            found += segment_zh(part, extra)
        else:
            word = part.lower().strip("-'")
            if word and word not in EN_STOP and len(word) > 1:
                found.append(_stem(word))
    if not unique:
        return found
    seen, out = set(), []
    for w in found:
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out


# ---------------------------------------------------------------- translation
def translate_glossary(title: str, extra: dict | None = None) -> tuple[str, list[str]]:
    """Word-by-word translation with the built-in lexicon. Returns (english, words left untranslated)."""
    lexicon = {**GLOSSARY, **(extra or {})}
    words, missing = [], []
    for part in re.findall(r"[㐀-鿿]+|[A-Za-z][A-Za-z\-' ]*", title or ""):
        if not _CJK.match(part):
            words.append(part.strip())
            continue
        for w in segment_zh(part, extra):
            if w in lexicon:
                words.append(lexicon[w])
            elif len(w) > 1:
                missing.append(w)
    return " ".join(dict.fromkeys(w for w in words if w)), missing


def translate(title: str, settings: dict, extra: dict | None = None, ai=None) -> dict:
    """Chinese title → English. Order: AI assistant (if set up) → free MyMemory API → built-in glossary."""
    if not has_cjk(title):
        return {"text": title.strip(), "method": "none", "missing": []}
    if ai:
        try:
            text = ai("Translate this thesis title into concise academic English. Reply with the title only.", title).strip().strip('"')
            if text and not has_cjk(text):
                return {"text": text[:300], "method": "ai", "missing": []}
        except Exception:
            pass
    if settings.get("topic_online_translate", True):
        try:
            url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode({"q": title[:450], "langpair": "zh-TW|en"})
            text = ((integ._get_json(url, timeout=12).get("responseData") or {}).get("translatedText") or "").strip()
            if text and not has_cjk(text) and "MYMEMORY WARNING" not in text.upper():
                return {"text": text[:300], "method": "mymemory", "missing": []}
        except Exception:
            pass
    text, missing = translate_glossary(title, extra)
    return {"text": text, "method": "glossary", "missing": missing}


# ---------------------------------------------------------------- overlap
def overlap(mine: list[str], other: list[str]) -> int:
    """Share of my title's content words that also appear in the other title (0–100)."""
    if not mine:
        return 0
    theirs = set(other)
    hit = sum(1 for w in mine if w in theirs or any(len(w) > 4 and (w in o or o in w) and len(o) > 4 for o in theirs))
    return round(100 * hit / len(mine))


def band(pct: int) -> str:
    return "crowded" if pct >= 70 else "done" if pct >= 50 else "partial" if pct >= 30 else "rare"


def _openalex(query: str, region: str = "", mailto: str = "") -> tuple[int, list[dict]]:
    params = {"search": query, "per-page": "25", "select": "id,display_name,publication_year,cited_by_count,doi"}
    if region == "tw":
        params["filter"] = "institutions.country_code:tw"
    elif region == "abroad":
        params["filter"] = "institutions.country_code:!tw"
    if mailto:
        params["mailto"] = mailto
    data = integ._get_json("https://api.openalex.org/works?" + urllib.parse.urlencode(params))
    works = [{"title": w.get("display_name") or "", "year": w.get("publication_year") or 0, "cited_by": w.get("cited_by_count") or 0,
              "url": w.get("doi") or w.get("id") or ""} for w in data.get("results", []) if w.get("display_name")]
    return int((data.get("meta") or {}).get("count") or 0), works


def _rank(mine: list[str], works: list[dict], extra: dict | None) -> list[dict]:
    for w in works:
        w["overlap"] = overlap(mine, tokens(w["title"], extra))
    return sorted(works, key=lambda w: (-w["overlap"], -w["cited_by"]))


def _region(mine: list[str], query: str, region: str, mailto: str, extra: dict | None) -> dict:
    count, works = _openalex(query, region, mailto)
    ranked = _rank(mine, works, extra)
    top = ranked[0]["overlap"] if ranked else 0
    return {"count": count, "max": top, "band": band(top), "similar": sum(1 for w in ranked if w["overlap"] >= 50),
            "works": [w for w in ranked if w["overlap"] >= 30][:6]}


# ---------------------------------------------------------------- strength
def story_score(topic: dict, story: list[dict]) -> tuple[int, list[str]]:
    """0–100 for the reason and story behind the title, plus what is still missing."""
    sent = {r.get("key"): (r.get("sentence") or "").strip() for r in story or []}
    checks = [
        ("reason", len((topic.get("reason") or "").strip()) >= 15, 25),
        ("benefit", len((topic.get("benefit") or "").strip()) >= 15, 25),
        ("audience", bool((topic.get("audience") or "").strip()), 10),
        ("complication", len(sent.get("complication", "")) >= 10, 15),
        ("concern", len(sent.get("concern", "")) >= 10, 15),
        ("contribution", len(sent.get("contribution", "")) >= 10, 10),
    ]
    return sum(p for _, ok, p in checks if ok), [k for k, ok, _ in checks if not ok]


def specificity_score(title: str, toks: list[str]) -> tuple[int, list[str]]:
    checks = [("concepts", len(toks) >= 3, 40), ("relation", bool(RELATION.search(title)), 30),
              ("context", bool(CONTEXT.search(title)), 20), ("length", 8 <= len(title.strip()) <= (60 if has_cjk(title) else 160), 10)]
    return sum(p for _, ok, p in checks if ok), [k for k, ok, _ in checks if not ok]


def check(title: str, topic: dict, snapshot: dict, settings: dict, *, title_en: str = "", online: bool = True, ai=None) -> dict:
    """Full title check. Never raises for network trouble: the offline parts are still returned."""
    title = (title or "").strip()
    extra = {v["name_zh"]: v["name_en"] for v in snapshot.get("variables", []) if v.get("name_zh") and v.get("name_en")}
    result: dict = {"title": title, "tokens": tokens(title, extra), "errors": []}
    if title_en.strip():
        tr = {"text": title_en.strip(), "method": "manual", "missing": []}
    elif online:
        tr = translate(title, settings, extra, ai)
    else:
        text, missing = translate_glossary(title, extra)
        tr = {"text": text if has_cjk(title) else title, "method": "glossary" if has_cjk(title) else "none", "missing": missing}
    result["translation"] = tr
    mine = tokens(tr["text"], extra)
    result["tokens_en"] = mine

    # my own library (always available)
    library = _rank(mine, [{"title": p["title"], "year": p.get("year") or 0, "cited_by": 0, "url": p.get("url") or ""}
                           for p in snapshot.get("papers", []) if p.get("title")], extra)
    result["library"] = [w for w in library if w["overlap"] >= 30][:5]

    regions = {}
    if online and mine:
        query = " ".join(mine[:8])
        mailto = settings.get("openalex_mailto", "")
        for region in ("tw", "abroad"):
            try:
                regions[region] = _region(mine, query, region, mailto, extra)
            except Exception as e:
                result["errors"].append(f"{region}: {e}")
        if regions and all(r["count"] == 0 for r in regions.values()) and len(mine) > 3:
            # all words together matched nothing: retry with the leading concepts so "rare" is not a false zero
            for region in list(regions):
                try:
                    regions[region] = {**_region(mine, " ".join(mine[:3]), region, mailto, extra), "relaxed": True}
                except Exception as e:
                    result["errors"].append(f"{region}: {e}")
    result["regions"] = regions

    top = max([r["max"] for r in regions.values()] + [w["overlap"] for w in result["library"]] + [0])
    result["overlap"] = top
    novelty = None if not regions else max(0, 100 - top)
    spec, spec_missing = specificity_score(title, result["tokens"])
    story, story_missing = story_score(topic, snapshot.get("story", []))
    parts = {"novelty": novelty, "specificity": spec, "story": story}
    weights = {"novelty": 0.4, "specificity": 0.25, "story": 0.35}
    known = {k: v for k, v in parts.items() if v is not None}
    score = round(sum(v * weights[k] for k, v in known.items()) / sum(weights[k] for k in known)) if known else 0
    level = "strong" if score >= 70 else "medium" if score >= 40 else "weak"
    if novelty is None and level == "strong":
        level = "medium"  # overlap with published work was not checked, so "strong" would be a guess
    result.update(parts=parts, missing={"specificity": spec_missing, "story": story_missing}, score=score, level=level)
    return result


def dumps(result: dict) -> str:
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))
