"""Word (.docx) thesis draft built from the workspace, standard library only.

Layout follows the usual Taiwanese thesis format: cover page, front matter numbered i, ii, iii (abstracts,
table of contents, lists of figures and tables), body numbered from 1 with 第一章 / 第一節 headings, and
an APA reference list. Body text uses a paragraph style named 論文設定0 so the whole document can be
restyled in Word from one place.
"""
from __future__ import annotations

import io
import re
import zipfile
from xml.sax.saxutils import escape

BODY_STYLE = "論文設定0"
FONTS_ZH = ("標楷體", "新細明體", "思源宋體", "Noto Serif TC", "微軟正黑體", "思源黑體")
DEFAULTS = {
    "school": "", "department": "", "degree": "碩士論文", "title": "", "title_en": "", "advisor": "", "author": "", "date": "",
    "font_zh": "標楷體", "font_en": "Times New Roman", "size": 12, "line": 1.5,
    "margin_top": 2.54, "margin_bottom": 2.54, "margin_left": 3.0, "margin_right": 2.54,
    "header": True, "lang": "zh",
}
NUM_ZH = "零一二三四五六七八九十"
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def options(raw: dict | None) -> dict:
    opt = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        value = (raw or {}).get(key)
        if value is None:
            continue
        if isinstance(default, bool):
            opt[key] = bool(value)
        elif isinstance(default, (int, float)):
            try:
                opt[key] = float(value)
            except (TypeError, ValueError):
                pass
        else:
            opt[key] = re.sub(r"[\x00-\x08\x0b-\x1f]", "", str(value))[:300]
    opt["size"] = max(10, min(16, opt["size"]))
    opt["line"] = max(1.0, min(2.5, opt["line"]))
    for side in ("top", "bottom", "left", "right"):
        opt[f"margin_{side}"] = max(1.0, min(5.0, opt[f"margin_{side}"]))
    if opt["font_zh"] not in FONTS_ZH:
        opt["font_zh"] = DEFAULTS["font_zh"]
    opt["font_en"] = re.sub(r"[^A-Za-z0-9 \-]", "", opt["font_en"]) or DEFAULTS["font_en"]
    return opt


# ---------------------------------------------------------------- WordprocessingML helpers
def _t(text) -> str:
    return f'<w:t xml:space="preserve">{escape(str(text))}</w:t>'


def run(text, bold=False, italic=False, size=None) -> str:
    props = ("<w:b/><w:bCs/>" if bold else "") + ("<w:i/><w:iCs/>" if italic else "")
    if size:
        props += f'<w:sz w:val="{int(size * 2)}"/><w:szCs w:val="{int(size * 2)}"/>'
    return f"<w:r>{'<w:rPr>' + props + '</w:rPr>' if props else ''}{_t(text)}</w:r>"


def para(content="", style=None, *, align=None, indent=None, before=None, after=None, page_break=False, runs=None) -> str:
    props = f'<w:pStyle w:val="{style}"/>' if style else ""
    if page_break:
        props += "<w:pageBreakBefore/>"
    if before is not None or after is not None:
        props += f'<w:spacing w:before="{int((before or 0) * 20)}" w:after="{int((after or 0) * 20)}"/>'
    if indent is not None:
        props += f'<w:ind w:firstLineChars="{int(indent * 100)}" w:firstLine="{int(indent * 240)}"/>'
    if align:
        props += f'<w:jc w:val="{align}"/>'
    body = runs if runs is not None else (run(content) if content != "" else "")
    return f"<w:p>{'<w:pPr>' + props + '</w:pPr>' if props else ''}{body}</w:p>"


def field(code: str, placeholder: str = "") -> str:
    return (f'<w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r><w:r><w:instrText xml:space="preserve"> {escape(code)} </w:instrText></w:r>'
            f'<w:r><w:fldChar w:fldCharType="separate"/></w:r>{run(placeholder) if placeholder else ""}<w:r><w:fldChar w:fldCharType="end"/></w:r>')


def table(rows: list[list[str]], widths: list[int]) -> str:
    border = "".join(f'<w:{side} w:val="single" w:sz="4" w:space="0" w:color="000000"/>' for side in ("top", "left", "bottom", "right", "insideH", "insideV"))
    out = [f'<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>{border}</w:tblBorders></w:tblPr>'
           "<w:tblGrid>" + "".join('<w:gridCol w:w="%d"/>' % w for w in widths) + "</w:tblGrid>"]
    for i, row in enumerate(rows):
        cells = "".join(f'<w:tc><w:tcPr><w:tcW w:w="{widths[j]}" w:type="dxa"/></w:tcPr>'
                        f'{para(runs=run(cell, bold=i == 0), style="TableText", align="center" if i == 0 else None)}</w:tc>' for j, cell in enumerate(row))
        out.append(f"<w:tr>{'<w:trPr><w:tblHeader/></w:trPr>' if i == 0 else ''}{cells}</w:tr>")
    return "".join(out) + "</w:tbl>"


def caption(kind: str, chapter: int, text: str) -> str:
    """表 3-1 / 圖 3-1 caption with a SEQ field so the lists of tables and figures can be built by Word."""
    runs = run(f"{kind} {chapter}-") + field(f"SEQ {kind}{chapter} \\* ARABIC", "1") + run(" " + text)
    return para(runs=runs, style="Caption" + ("Table" if kind == "表" else "Figure"))


def section(*, fmt: str, start: int | None, footer: str | None, header: str | None, opt: dict, title_page=False) -> str:
    cm = lambda v: int(v * 567)
    refs = (f'<w:headerReference w:type="default" r:id="{header}"/>' if header else "") + (f'<w:footerReference w:type="default" r:id="{footer}"/>' if footer else "")
    num = f'<w:pgNumType w:fmt="{fmt}"' + (f' w:start="{start}"' if start is not None else "") + "/>"
    return (f'<w:sectPr>{refs}<w:type w:val="nextPage"/><w:pgSz w:w="11906" w:h="16838"/>'
            f'<w:pgMar w:top="{cm(opt["margin_top"])}" w:right="{cm(opt["margin_right"])}" w:bottom="{cm(opt["margin_bottom"])}" '
            f'w:left="{cm(opt["margin_left"])}" w:header="851" w:footer="992" w:gutter="0"/>{num}{"<w:titlePg/>" if title_page else ""}</w:sectPr>')


# ---------------------------------------------------------------- content
def apa(p: dict) -> str:
    authors = [a.strip() for a in re.split(r"\s*;\s*", p.get("authors") or "") if a.strip()]
    if len(authors) > 1:
        names = ", ".join(authors[:-1]) + (", & " if re.search(r"[A-Za-z]", authors[-1]) else "、") + authors[-1]
    else:
        names = authors[0] if authors else ""
    year = f"({p['year']})" if p.get("year") else "(n.d.)"
    parts = [f"{names} {year}." if names else f"{year}.", (p.get("title") or "").rstrip(".") + "."]
    if p.get("venue"):
        parts.append(p["venue"].rstrip(".") + ".")
    if p.get("doi"):
        parts.append("https://doi.org/" + p["doi"])
    return " ".join(parts)


def cite(p: dict) -> str:
    authors = [a.strip() for a in re.split(r"\s*;\s*", p.get("authors") or "") if a.strip()]
    last = [a.split(",")[0].strip() for a in authors]
    who = last[0] + (" et al." if len(last) > 2 else f" & {last[1]}" if len(last) == 2 else "") if last else (p.get("title") or "")[:30]
    return f"{who} ({p.get('year') or 'n.d.'})"


def _paras(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def build(snapshot: dict, raw: dict | None = None) -> bytes:
    opt = options(raw)
    en = opt["lang"] == "en"
    L = (lambda zh, e: e) if en else (lambda zh, e: zh)
    topic = snapshot.get("topic") or {}
    title = opt["title"] or topic.get("title") or L("論文題目", "Thesis title")
    title_en = opt["title_en"] or topic.get("title_en") or ""
    story = {r["key"]: (r.get("sentence") or "").strip() for r in snapshot.get("story", [])}
    papers = {p["id"]: p for p in snapshot.get("papers", [])}
    variables = snapshot.get("variables", [])
    by_id = {v["id"]: v for v in variables}
    name = lambda v: (v.get("name_en") or v.get("name_zh")) if en else (v.get("name_zh") or v.get("name_en")) or v["symbol"]
    var_papers: dict[int, list[dict]] = {}
    for link in snapshot.get("variable_papers", []):
        if link["paper_id"] in papers:
            var_papers.setdefault(link["variable_id"], []).append(papers[link["paper_id"]])
    design = snapshot.get("design") or {}
    todo = lambda zh, e: f"［{L(zh, e)}］"
    body: list[str] = []
    P = lambda text: body.append(para(text, BODY_ID, indent=2))

    def chapter(n: int, zh: str, e: str):
        body.append(para(L(f"第{NUM_ZH[n]}章 {zh}", f"Chapter {n} {e}"), "Heading1", page_break=True))

    def sec(n: int, zh: str, e: str):
        body.append(para(L(f"第{NUM_ZH[n]}節 {zh}", f"{n}. {e}"), "Heading2"))

    def front(zh: str, e: str, first=False):
        body.append(para(L(zh, e), "FrontTitle", page_break=not first))

    # ---- cover (own section, no page number)
    cover = [para(opt["school"] or todo("校名", "University"), "Cover", before=24),
             para(opt["department"] or todo("系所", "Department"), "Cover"), para(opt["degree"], "Cover", after=60),
             para(runs=run(title, bold=True), style="Cover", after=12)]
    if title_en:
        cover.append(para(runs=run(title_en, bold=True), style="Cover", after=96))
    cover += [para(L("指導教授：", "Advisor: ") + (opt["advisor"] or todo("姓名", "name")), "Cover", before=96),
              para(L("研究生：", "Author: ") + (opt["author"] or todo("姓名", "name")), "Cover", after=60),
              para(opt["date"] or todo("中華民國　年　月", "Month Year"), "Cover"),
              f'<w:p><w:pPr>{section(fmt="lowerRoman", start=None, footer=None, header=None, opt=opt)}</w:pPr></w:p>']
    body += cover

    # ---- front matter (i, ii, iii …)
    front("誌　　謝", "Acknowledgements", first=True)
    P(todo("在此撰寫誌謝", "Write your acknowledgements here"))
    front("摘　　要", "Abstract")
    summary = [story.get(k) for k in ("common", "complication", "concern", "course", "contribution") if story.get(k)]
    P("".join(summary) if summary and not en else " ".join(summary) if summary else todo("摘要：研究背景、目的、方法、結果與貢獻", "Abstract: background, purpose, method, findings, contribution"))
    keywords = L("、", ", ").join(name(v) for v in variables if v["role"] != "ctrl")
    body.append(para(runs=run(L("關鍵詞：", "Keywords: "), bold=True) + run(keywords or todo("3–5 個關鍵詞", "3–5 keywords")), style=BODY_ID))
    if not en:
        front("Abstract", "Abstract")
        P(todo("English abstract", "English abstract"))
        body.append(para(runs=run("Keywords: ", bold=True) + run(", ".join(v.get("name_en") or "" for v in variables if v["role"] != "ctrl" and v.get("name_en")) or "…"), style=BODY_ID))
    front("目　　錄", "Table of contents")
    body.append(para(runs=field('TOC \\o "1-2" \\h \\z \\u', L("在 Word 按右鍵 →「更新功能變數」即可產生目錄與頁碼。", "Right-click → Update Field in Word to build the contents and page numbers.")), style=BODY_ID))
    front("圖目錄", "List of figures")
    body.append(para(runs=field('TOC \\h \\z \\t "CaptionFigure,1"', "…"), style=BODY_ID))
    front("表目錄", "List of tables")
    body.append(para(runs=field('TOC \\h \\z \\t "CaptionTable,1"', "…"), style=BODY_ID))
    body.append(f'<w:p><w:pPr>{section(fmt="lowerRoman", start=1, footer="rId3", header="rId2" if opt["header"] else None, opt=opt)}</w:pPr></w:p>')

    # ---- chapter 1
    chapter(1, "緒論", "Introduction")
    sec(1, "研究背景與動機", "Background and motivation")
    for text in [story.get("common"), story.get("complication"), story.get("concern"), *(_paras(topic.get("reason")))]:
        if text:
            P(text)
    if not any(story.get(k) for k in ("common", "complication", "concern")) and not topic.get("reason"):
        P(todo("研究背景：我們已知什麼？有什麼尚未解決？為什麼重要？", "Background: what is known, what is unresolved, why it matters"))
    sec(2, "研究目的與問題", "Purpose and research questions")
    for text in [story.get("course"), story.get("contribution"), *(_paras(topic.get("benefit")))]:
        if text:
            P(text)
    rqs = snapshot.get("rqs", [])
    if rqs:
        P(L("本研究之研究問題如下：", "This study addresses the following research questions:"))
        for rq in rqs:
            body.append(para(f"{rq.get('code') or 'RQ'}　{rq['text']}", BODY_ID, indent=0))
    else:
        P(todo("列出研究問題", "List the research questions"))
    sec(3, "研究流程", "Research process")
    stages = snapshot.get("stages", [])
    P(L("本研究之流程依序為：", "The research proceeds through: ") + L("、", ", ").join((s.get("title_en") if en else s.get("title_zh")) or s.get("title_zh") or "" for s in stages) + L("。", "."))
    body.append(caption("圖", 1, L("研究流程圖", "Research process")))

    # ---- chapter 2
    chapter(2, "文獻探討", "Literature review")
    core = [v for v in variables if v["role"] != "ctrl"]
    n = 0
    for n, v in enumerate(core, 1):
        if n > 9:
            break
        sec(n, name(v), name(v))
        if v.get("definition"):
            P(v["definition"])
        linked = var_papers.get(v["id"], [])
        for p in linked:
            notes = [p.get(k) for k in ("c_complication", "c_course", "c_contribution") if p.get(k)]
            P(f"{cite(p)}" + L("：", ": ") + ("".join(notes) if notes and not en else " ".join(notes) if notes else (p.get("notes") or p.get("title") or "")))
        if not v.get("definition") and not linked:
            P(todo(f"回顧「{name(v)}」的定義、相關理論與實證研究", f"Review definitions, theory and evidence on {name(v)}"))
    if not core:
        sec(1, "相關理論", "Theoretical background")
        P(todo("文獻回顧", "Literature review"))
        n = 1
    relations = snapshot.get("relations", [])
    hypotheses = [rq["hypothesis"] for rq in rqs if (rq.get("hypothesis") or "").strip()]
    if (relations or hypotheses) and n < 10:
        sec(n + 1, "假設推導", "Hypothesis development")
        for h in hypotheses:
            for line in _paras(h):
                P(line)
        for r in relations:
            a, b = by_id.get(r["source_id"]), by_id.get(r["target_id"])
            if a and b and r.get("label") and not hypotheses:
                P(f"{r['label']}：{name(a)} → {name(b)}" + (f"（{r['sign']}）" if r.get("sign") else ""))

    # ---- chapter 3
    chapter(3, "研究方法", "Method")
    sec(1, "研究架構", "Research framework")
    P(L("本研究之研究架構如圖 3-1 所示。", "Figure 3-1 shows the research framework."))
    body.append(para(todo("在此貼上研究架構圖（研究核心 → 研究架構圖 → 匯出 SVG/PNG）", "Paste the research model here (Research core → Research model → export)"), BODY_ID, align="center"))
    body.append(caption("圖", 3, L("研究架構圖", "Research framework")))
    sec(2, "研究設計與樣本", "Design and sample")
    purposes = {"describe": L("描述現況與變數間之相關", "describe and correlate"), "change": L("探討隨時間之改變", "study change over time"), "causal": L("檢驗因果關係與心理過程", "test causal relations and processes")}
    designs = {"cross_sectional": L("橫斷面設計", "a cross-sectional design"), "longitudinal": L("縱貫設計", "a longitudinal design"), "experiment": L("實驗設計", "an experimental design")}
    if design.get("purpose") or design.get("design"):
        waves = int(design.get("waves") or 0)
        P(L("本研究旨在", "This study aims to ") + purposes.get(design.get("purpose"), todo("研究目的", "purpose")) + L("，採用", ", using ")
          + designs.get(design.get("design"), todo("資料設計", "design")) + (L(f"，分 {waves} 個時點蒐集資料", f" with {waves} waves") if waves > 1 else "") + L("。", "."))
    for text in _paras(design.get("sample")) or [todo("樣本來源、抽樣方式與資料蒐集程序", "Sample, sampling and procedure")]:
        P(text)
    sec(3, "變數定義與衡量", "Measures")
    if variables:
        P(L("各變數之操作型定義與衡量方式彙整如表 3-1。", "Table 3-1 summarises the definitions and measures."))
        body.append(caption("表", 3, L("變數操作型定義與衡量", "Operational definitions and measures")))
        roles = {"iv": L("自變數", "Independent"), "dv": L("依變數", "Dependent"), "med": L("中介變數", "Mediator"), "mod": L("調節變數", "Moderator"), "ctrl": L("控制變數", "Control"), "other": L("其他", "Other")}
        rows = [[L("變數", "Variable"), L("類型", "Role"), L("操作型定義", "Definition"), L("衡量方式", "Measure")]]
        rows += [[name(v), roles.get(v["role"], ""), v.get("definition") or "", v.get("measurement") or ""] for v in variables]
        body.append(table(rows, [1700, 1300, 3000, 2500]))
        body.append(para("", BODY_ID))
    else:
        P(todo("變數定義與衡量", "Measures"))
    sec(4, "資料分析方法", "Analysis")
    P(todo("說明信效度檢驗與假設檢定方法", "Describe reliability/validity checks and hypothesis tests"))
    if (design.get("limitations") or "").strip():
        sec(5, "研究限制", "Limitations")
        for text in _paras(design["limitations"]):
            P(text)

    # ---- references
    body.append(para(L("參考文獻", "References"), "Heading1", page_break=True))
    used = sorted((p for p in papers.values() if p.get("status") != "excluded"), key=lambda p: ((p.get("authors") or p.get("title") or "").lower(), p.get("year") or 0))
    for p in used:
        body.append(para(apa(p), "Reference"))
    if not used:
        P(todo("參考文獻（APA 格式）", "References (APA)"))

    final = section(fmt="decimal", start=1, footer="rId3", header="rId2" if opt["header"] else None, opt=opt).replace('<w:type w:val="nextPage"/>', "")
    document = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {W}><w:body>{"".join(body)}{final}</w:body></w:document>'

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/document.xml", document)
        z.writestr("word/styles.xml", styles(opt))
        z.writestr("word/settings.xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings {W}><w:updateFields w:val="true"/></w:settings>')
        z.writestr("word/header1.xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:hdr {W}>{para(title, "Header")}</w:hdr>')
        z.writestr("word/footer1.xml", f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr {W}>{para(runs=field("PAGE", "1"), style="Footer")}</w:ftr>')
        z.writestr("docProps/core.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
                   f'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{escape(title)}</dc:title><dc:creator>{escape(opt["author"])}</dc:creator></cp:coreProperties>')
    return out.getvalue()


BODY_ID = "ThesisBody0"  # style id must be ASCII; its display name in Word is 論文設定0


def styles(opt: dict) -> str:
    zh, en, size = escape(opt["font_zh"]), escape(opt["font_en"]), opt["size"]
    line = int(opt["line"] * 240)
    fonts = f'<w:rFonts w:ascii="{en}" w:hAnsi="{en}" w:eastAsia="{zh}" w:cs="{en}"/>'

    def style(sid, name, *, based=None, size_pt=size, bold=False, align=None, before=0, after=0, line_=line, outline=None, extra="", ui=1, hanging=False):
        ppr = ("<w:keepNext/>" if outline is not None else "") + f'<w:spacing w:before="{before * 20}" w:after="{after * 20}" w:line="{line_}" w:lineRule="auto"/>'
        if hanging:
            ppr += '<w:ind w:left="480" w:hanging="480"/>'
        if align:
            ppr += f'<w:jc w:val="{align}"/>'
        if outline is not None:
            ppr += f'<w:outlineLvl w:val="{outline}"/>'
        rpr = fonts + ("<w:b/><w:bCs/>" if bold else "") + f'<w:sz w:val="{int(size_pt * 2)}"/><w:szCs w:val="{int(size_pt * 2)}"/>'
        return (f'<w:style w:type="paragraph" w:styleId="{sid}"><w:name w:val="{escape(name)}"/>'
                + (f'<w:basedOn w:val="{based}"/>' if based else "") + f'<w:uiPriority w:val="{ui}"/><w:qFormat/>'
                f'<w:pPr>{ppr}{extra}</w:pPr><w:rPr>{rpr}</w:rPr></w:style>')

    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {W}>'
            f'<w:docDefaults><w:rPrDefault><w:rPr>{fonts}<w:sz w:val="{int(size * 2)}"/><w:szCs w:val="{int(size * 2)}"/>'
            '<w:lang w:val="en-US" w:eastAsia="zh-TW"/></w:rPr></w:rPrDefault></w:docDefaults>'
            + style("Normal", "Normal", line_=240).replace('<w:style w:type="paragraph"', '<w:style w:type="paragraph" w:default="1"')
            + style(BODY_ID, BODY_STYLE, based="Normal", align="both")
            + style("Heading1", "heading 1", based="Normal", size_pt=18, bold=True, align="center", before=12, after=18, outline=0)
            + style("Heading2", "heading 2", based="Normal", size_pt=16, bold=True, before=12, after=6, outline=1)
            + style("FrontTitle", "前置標題", based="Normal", size_pt=18, bold=True, align="center", after=18, outline=0)
            + style("Cover", "封面", based="Normal", size_pt=22, align="center", line_=360)
            + style("CaptionTable", "表標題", based="Normal", align="center", before=6, after=3)
            + style("CaptionFigure", "圖標題", based="Normal", align="center", before=3, after=12)
            + style("TableText", "表格文字", based="Normal", size_pt=max(10, size - 1), line_=300)
            + style("Reference", "參考文獻", based="Normal", align="both", hanging=True)
            + style("Header", "header", based="Normal", size_pt=10, align="center", line_=240)
            + style("Footer", "footer", based="Normal", size_pt=10, align="center", line_=240)
            + "".join(f'<w:style w:type="paragraph" w:styleId="TOC{i}"><w:name w:val="toc {i}"/><w:basedOn w:val="Normal"/><w:uiPriority w:val="39"/>'
                      f'<w:pPr><w:tabs><w:tab w:val="right" w:leader="dot" w:pos="8296"/></w:tabs><w:spacing w:line="{line}" w:lineRule="auto"/>'
                      f'<w:ind w:left="{(i - 1) * 240}"/></w:pPr></w:style>' for i in (1, 2))
            + "</w:styles>")


CONTENT_TYPES = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                 '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                 '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                 '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
                 '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
                 '<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
                 '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
                 '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>')
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/></Relationships>')
DOC_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
            '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/></Relationships>')
