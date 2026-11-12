/* Research Hub — PowerPoint export with a design-instruction window.
   The deck is built in the browser with the bundled PptxGenJS (MIT); nothing leaves the computer
   unless the optional AI assistant is asked to write the key messages and speaker notes. */
(function () {
  const H = window.H;
  const { el, t } = H;

  /* ---------- design vocabulary ---------- */
  const FONTS = [
    ["Noto Serif TC", "思源宋體（開源明體）· Noto Serif TC", "https://fonts.google.com/noto/specimen/Noto+Serif+TC"],
    ["PMingLiU", "新細明體 · PMingLiU（Windows 內建明體）", ""],
    ["Microsoft JhengHei", "微軟正黑體 · Microsoft JhengHei", ""],
    ["Noto Sans TC", "思源黑體（開源）· Noto Sans TC", "https://fonts.google.com/noto/specimen/Noto+Sans+TC"],
    ["DFKai-SB", "標楷體 · DFKai-SB", ""],
    ["PingFang TC", "蘋方 · PingFang TC（macOS）", ""],
  ];
  const THEMES = {
    minimal: { zh: "白色極簡", en: "White minimal", dark: "0B0C10", accent: "2B50E8", tint: "F3F5FB", ink: "15171C", muted: "5D6270", line: "DCDEE3", onDark: "FFFFFF", onDarkMuted: "B9BDC7" },
    navy: { zh: "學術深藍", en: "Academic navy", dark: "1E2761", accent: "1E2761", tint: "EEF1FB", ink: "161B33", muted: "5A607A", line: "D5D9EA", onDark: "FFFFFF", onDarkMuted: "CADCFC" },
    forest: { zh: "森林綠", en: "Forest", dark: "2C5F2D", accent: "2C5F2D", tint: "EEF5E9", ink: "17261A", muted: "56665A", line: "D3E0CF", onDark: "FFFFFF", onDarkMuted: "CFE3B5" },
    berry: { zh: "酒紅", en: "Berry", dark: "6D2E46", accent: "6D2E46", tint: "F7EEF2", ink: "2A1520", muted: "6E5763", line: "E6D3DB", onDark: "FFFFFF", onDarkMuted: "ECE2D0" },
    charcoal: { zh: "炭灰", en: "Charcoal", dark: "36454F", accent: "36454F", tint: "F2F3F4", ink: "1E2529", muted: "5F6A70", line: "D9DDE0", onDark: "FFFFFF", onDarkMuted: "C9D1D6" },
  };
  const STATUS = { done: "0F7A52", active: "2B50E8", review: "6342CF", blocked: "C0322B", todo: "B9BDC7" };
  const ROLE = { iv: "2B50E8", dv: "0F7A52", med: "A35A00", mod: "6342CF", ctrl: "5D6270", other: "8A5A44" };
  const SECTIONS = ["title", "overview", "rqs", "model", "hypotheses", "variables", "literature", "progress", "next", "closing"];
  const PURPOSE = {
    advisor: ["title", "overview", "progress", "rqs", "model", "next", "closing"],
    defense: ["title", "rqs", "model", "hypotheses", "variables", "literature", "overview", "closing"],
    conference: ["title", "rqs", "model", "hypotheses", "literature", "closing"],
  };
  const PRIORITY = ["title", "model", "rqs", "overview", "next", "hypotheses", "progress", "literature", "variables", "closing"];

  /* ---------- slide wording (the deck's own language) ---------- */
  const W = {
    zh: { overview: "研究進度總覽", rqs: "研究問題", model: "研究架構", hypotheses: "研究假設", variables: "變數與操作型定義", literature: "文獻回顧",
      progress: "近期進度", next: "下一步", thanks: "謝謝聆聽", qa: "敬請指教 · Q&A", overall: "整體進度", stagesDone: "已完成階段", deadline: "論文完成日",
      daysLeft: (n) => `剩 ${n} 天`, overdue: "已逾期", sym: "符號", variable: "變數", role: "角色", measure: "操作型定義／測量", papers: "文獻", total: "收錄文獻",
      read: "已讀完", reading: "閱讀中", noData: "（尚無資料）", hyp: (a, b, sign) => `${a}對${b}有${sign === "-" ? "負向" : sign === "+" ? "正向" : ""}影響`,
      modHyp: (z, a, b) => `${z}調節${a}與${b}之間的關係`, purpose: { advisor: "指導教授進度報告", defense: "論文口試", conference: "研討會發表" },
      roles: { iv: "自變數", dv: "依變數", med: "中介變數", mod: "調節變數", ctrl: "控制變數", other: "其他" }, status: { todo: "未開始", active: "進行中", review: "審閱中", done: "已完成", blocked: "受阻" },
      msgOverview: (p, s, sp) => `整體進度 ${p}%，目前進行「${s}」（${sp}%）`, msgModel: (n, r) => `${n} 個變數、${r} 條假設路徑`, msgNext: "接下來的待辦與期限" },
    en: { overview: "Progress overview", rqs: "Research questions", model: "Research model", hypotheses: "Hypotheses", variables: "Variables & measures", literature: "Literature",
      progress: "Recent progress", next: "Next steps", thanks: "Thank you", qa: "Questions & discussion", overall: "Overall", stagesDone: "Stages done", deadline: "Thesis deadline",
      daysLeft: (n) => `${n} days left`, overdue: "Overdue", sym: "Symbol", variable: "Variable", role: "Role", measure: "Operationalisation", papers: "Papers", total: "Papers",
      read: "Read", reading: "Reading", noData: "(nothing yet)", hyp: (a, b, sign) => `${a} has ${sign === "-" ? "a negative" : sign === "+" ? "a positive" : "an"} effect on ${b}`,
      modHyp: (z, a, b) => `${z} moderates the effect of ${a} on ${b}`, purpose: { advisor: "Progress report", defense: "Thesis defense", conference: "Conference talk" },
      roles: { iv: "Independent", dv: "Dependent", med: "Mediator", mod: "Moderator", ctrl: "Control", other: "Other" }, status: { todo: "Not started", active: "In progress", review: "In review", done: "Done", blocked: "Blocked" },
      msgOverview: (p, s, sp) => `${p}% overall; now working on ${s} (${sp}%)`, msgModel: (n, r) => `${n} variables, ${r} hypothesised paths`, msgNext: "What comes next, and when" },
  };

  /* ---------- helpers ---------- */
  const units = (s) => [...String(s || "")].reduce((n, ch) => n + (/[　-鿿＀-￯]/.test(ch) ? 2 : 1), 0);
  /* Cut text to what fits in a box: width (in) × lines at a font size (pt), with slack. */
  const clip = (s, wIn, pt, lines = 1) => {
    const max = Math.floor((wIn * 144) / pt * lines * 0.9);
    let used = 0, out = "";
    for (const ch of String(s || "").replace(/\s+/g, " ").trim()) {
      used += /[　-鿿＀-￯]/.test(ch) ? 2 : 1;
      if (used > max) return out.replace(/\s+\S*$/, "") + "…";
      out += ch;
    }
    return out;
  };
  const nameIn = (v, lang) => (lang === "en" ? v.name_en || v.name_zh : v.name_zh || v.name_en) || v.symbol;
  const stageIn = (s, lang) => (lang === "en" ? s.title_en || s.title_zh : s.title_zh || s.title_en);
  const shortAuthors = (a) => { const l = (a || "").split(/\s*;\s*|\s+and\s+/).filter(Boolean); return !l.length ? "" : l.length > 2 ? `${l[0].split(",")[0]} et al.` : l.map((x) => x.split(",")[0]).join(" & "); };

  let loading = null;
  function loadPptx() {
    if (window.PptxGenJS) return Promise.resolve();
    loading = loading || new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "/static/vendor/pptxgen.bundle.js";
      s.onload = resolve; s.onerror = () => reject(new Error("PptxGenJS failed to load"));
      document.head.append(s);
    });
    return loading;
  }

  /* ---------- deck builder ---------- */
  async function buildDeck(o) {
    await loadPptx();
    const s = H.state, w = W[o.lang], th = THEMES[o.theme];
    const pres = new window.PptxGenJS();
    if (o.size === "43") { pres.defineLayout({ name: "RH43", width: 10, height: 7.5 }); pres.layout = "RH43"; } else pres.layout = "LAYOUT_WIDE";
    const SW = o.size === "43" ? 10 : 13.333, SH = 7.5, M = 0.6;
    pres.title = s.settings.project_title;
    if (o.presenter) pres.author = o.presenter;
    pres.theme = { headFontFace: o.headFont, bodyFontFace: o.bodyFont };
    const head = { fontFace: o.headFont }, body = { fontFace: o.bodyFont };
    pres.defineSlideMaster({ title: "RH_CONTENT", background: { color: "FFFFFF" },
      objects: [{ text: { text: clip(s.settings.project_title, SW / 2, 10), options: { x: M, y: SH - 0.5, w: SW / 2, h: 0.3, fontSize: 10, color: th.muted, ...body, margin: 0 } } }],
      slideNumber: { x: SW - M - 0.6, y: SH - 0.5, w: 0.6, h: 0.3, fontSize: 10, color: th.muted, align: "right", ...body } });
    pres.defineSlideMaster({ title: "RH_DARK", background: { color: th.dark } });

    const notes = o.notes || {};
    const msg = o.messages || {};
    let n = 0;
    const slideFor = (key, title) => {
      n++;
      const slide = pres.addSlide({ masterName: "RH_CONTENT" });
      slide.addText(`${String(n).padStart(2, "0")}  ·  ${w.purpose[o.purpose] || ""}`, { x: M, y: 0.38, w: SW - 2 * M, h: 0.3, fontSize: 11, color: th.accent, bold: true, ...body, margin: 0, isTextBox: true });
      slide.addText(title, { x: M, y: 0.68, w: SW - 2 * M, h: 0.7, fontSize: 30, bold: true, color: th.ink, ...head, margin: 0, isTextBox: true, valign: "top" });
      const m = msg[key];
      if (m) slide.addText(clip(m, SW - 2 * M, 15), { x: M, y: 1.38, w: SW - 2 * M, h: 0.4, fontSize: 15, color: th.muted, ...body, margin: 0, isTextBox: true });
      if (notes[key]) slide.addNotes(notes[key]);
      return { slide, top: m ? 2.0 : 1.65 };
    };
    const card = (slide, x, y, wIn, hIn, fill) => slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: wIn, h: hIn, fill: { color: fill || th.tint }, line: { color: fill || th.tint, width: 0.5 }, rectRadius: 0.12 });
    const circle = (slide, text, x, y, d, color, size) => slide.addText(text, { shape: pres.shapes.OVAL, x, y, w: d, h: d, fill: { color }, line: { color, width: 0.5 }, color: "FFFFFF", bold: true, fontSize: size || 12, align: "center", valign: "middle", ...body, margin: 0 });

    const doneStages = s.stages.filter((x) => x.status === "done").length;
    const current = s.stages.find((x) => ["active", "review", "blocked"].includes(x.status)) || s.stages.find((x) => x.status !== "done") || s.stages[0];
    const rels = (s.relations || []).length ? s.relations : H.implicitRelations(s.variables);

    const build = {
      title() {
        n++;
        const slide = pres.addSlide({ masterName: "RH_DARK" });
        slide.addText(w.purpose[o.purpose] || "", { x: M + 0.1, y: 1.7, w: SW - 2 * M, h: 0.4, fontSize: 14, color: th.onDarkMuted, bold: true, ...body, margin: 0, isTextBox: true });
        slide.addText(clip(s.settings.project_title, SW - 2 * M - 0.2, 40, 2), { x: M + 0.1, y: 2.2, w: SW - 2 * M - 0.2, h: 1.9, fontSize: 40, bold: true, color: th.onDark, ...head, margin: 0, isTextBox: true, valign: "top" });
        const date = new Date().toLocaleDateString(o.lang === "en" ? "en-GB" : "zh-TW", { year: "numeric", month: "long", day: "numeric" });
        slide.addText([o.presenter, date].filter(Boolean).join("　·　"), { x: M + 0.1, y: 4.4, w: SW - 2 * M, h: 0.4, fontSize: 16, color: th.onDarkMuted, ...body, margin: 0, isTextBox: true });
        slide.addText(`${w.overall}  ${s.overall}%`, { shape: pres.shapes.ROUNDED_RECTANGLE, x: M + 0.1, y: SH - 1.5, w: 2.3, h: 0.5, rectRadius: 0.25,
          fill: { color: th.dark }, line: { color: th.onDarkMuted, width: 1 }, color: th.onDark, fontSize: 13, bold: true, align: "center", valign: "middle", ...body, margin: 0 });
        if (notes.title) slide.addNotes(notes.title);
      },
      overview() {
        const { slide, top } = slideFor("overview", w.overview);
        const leftW = SW * 0.3;
        slide.addText(String(s.overall), { x: M, y: top, w: leftW, h: 1.3, fontSize: 72, bold: true, color: th.ink, ...head, margin: 0, isTextBox: true });
        slide.addText(`% ${w.overall}`, { x: M, y: top + 1.3, w: leftW, h: 0.35, fontSize: 13, color: th.muted, ...body, margin: 0, isTextBox: true });
        slide.addText(`${doneStages}/${s.stages.length}`, { x: M, y: top + 1.95, w: leftW, h: 0.6, fontSize: 30, bold: true, color: th.ink, ...head, margin: 0, isTextBox: true });
        slide.addText(w.stagesDone, { x: M, y: top + 2.55, w: leftW, h: 0.3, fontSize: 12, color: th.muted, ...body, margin: 0, isTextBox: true });
        const dl = s.settings.project_deadline;
        if (dl) {
          const days = H.daysUntil(dl);
          slide.addText(dl, { x: M, y: top + 3.15, w: leftW, h: 0.45, fontSize: 22, bold: true, color: days < 0 ? STATUS.blocked : th.ink, ...head, margin: 0, isTextBox: true });
          slide.addText(`${w.deadline} · ${days < 0 ? w.overdue : w.daysLeft(days)}`, { x: M, y: top + 3.6, w: leftW, h: 0.3, fontSize: 12, color: th.muted, ...body, margin: 0, isTextBox: true });
        }
        const x0 = M + leftW + 0.3, colW = SW - x0 - M, rowH = Math.min(0.48, (SH - top - 0.8) / s.stages.length);
        s.stages.forEach((st, i) => {
          const y = top + i * rowH;
          const prog = st.status === "done" ? 100 : st.progress;
          circle(slide, String(i + 1), x0, y + (rowH - 0.3) / 2, 0.3, STATUS[st.status] || STATUS.todo, 10);
          slide.addText(clip(stageIn(st, o.lang), colW * 0.42, 13), { x: x0 + 0.42, y, w: colW * 0.42, h: rowH, fontSize: 13, color: th.ink, ...body, margin: 0, valign: "middle", isTextBox: true });
          const bx = x0 + 0.42 + colW * 0.44, bw = colW * 0.38;
          slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: bx, y: y + rowH / 2 - 0.05, w: bw, h: 0.1, fill: { color: "ECEEF1" }, line: { color: "ECEEF1", width: 0.5 }, rectRadius: 0.05 });
          if (prog > 0) slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: bx, y: y + rowH / 2 - 0.05, w: Math.max(0.1, (bw * prog) / 100), h: 0.1, fill: { color: STATUS[st.status] || th.accent }, line: { color: STATUS[st.status] || th.accent, width: 0.5 }, rectRadius: 0.05 });
          slide.addText(`${prog}%`, { x: bx + bw + 0.1, y, w: colW - (bx - x0) - bw - 0.1, h: rowH, fontSize: 12, color: th.muted, ...body, margin: 0, valign: "middle", align: "right", isTextBox: true });
        });
      },
      rqs() {
        const list = s.rqs.length ? s.rqs : [{ code: "RQ", text: w.noData, hypothesis: "" }];
        for (let i = 0; i < list.length; i += 4) {
          const { slide, top } = slideFor("rqs", w.rqs);
          const page = list.slice(i, i + 4), cols = page.length > 1 ? 2 : 1, gap = 0.35;
          const cw = (SW - 2 * M - gap * (cols - 1)) / cols, rowsN = Math.ceil(page.length / cols), ch = Math.min(2.4, (SH - top - 0.8 - gap * (rowsN - 1)) / rowsN);
          page.forEach((rq, j) => {
            const x = M + (j % cols) * (cw + gap), y = top + Math.floor(j / cols) * (ch + gap);
            card(slide, x, y, cw, ch);
            circle(slide, clip(rq.code || "RQ", 0.6, 11), x + 0.25, y + 0.25, 0.62, th.accent, 11);
            slide.addText(clip(rq.text, cw - 1.3, 16, 3), { x: x + 1.05, y: y + 0.22, w: cw - 1.3, h: ch * 0.55, fontSize: 16, color: th.ink, bold: true, ...body, margin: 0, valign: "top", isTextBox: true });
            if (rq.hypothesis) slide.addText(clip(rq.hypothesis, cw - 1.3, 12, 2), { x: x + 1.05, y: y + ch * 0.62, w: cw - 1.3, h: ch * 0.32, fontSize: 12, color: th.muted, ...body, margin: 0, valign: "top", isTextBox: true });
          });
        }
      },
      model() {
        const { slide, top } = slideFor("model", w.model);
        if (!s.variables.length) { slide.addText(w.noData, { x: M, y: top, w: 6, h: 0.5, fontSize: 14, color: th.muted, ...body, isTextBox: true }); return; }
        const lay = H.modelLayout(s.variables, rels);
        const rw = SW - 2 * M, rh = SH - top - 0.75, k = Math.min(rw / lay.W, rh / lay.H);
        const ox = M + (rw - lay.W * k) / 2, oy = top + (rh - lay.H * k) / 2;
        const X = (px) => ox + px * k, Y = (py) => oy + py * k;
        const seg = (x1, y1, x2, y2, line) => slide.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.max(0.001, Math.abs(x2 - x1)), h: Math.max(0.001, Math.abs(y2 - y1)),
          flipH: x2 < x1, flipV: y2 < y1, line });
        for (const e of lay.edges) {
          const color = e.kind === "moderates" ? ROLE.mod : e.neg ? STATUS.blocked : "4A4F5C";
          const dash = e.kind === "moderates" || e.neg ? "dash" : "solid";
          e.pts.forEach((p, i) => {
            if (!i) return;
            const last = i === e.pts.length - 1;
            seg(X(e.pts[i - 1][0]), Y(e.pts[i - 1][1]), X(p[0]), Y(p[1]), { color, width: 1.5, dashType: dash, endArrowType: last ? "triangle" : undefined });
          });
        }
        const pt = Math.max(10, Math.min(14, Math.round(lay.boxH * k * 21)));
        for (const nd of lay.nodes) {
          const c = ROLE[nd.v.role] || ROLE.other;
          slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: X(nd.x), y: Y(nd.y), w: nd.w * k, h: nd.h * k, fill: { color: "FFFFFF" }, line: { color: c, width: 1.5 }, rectRadius: 0.08 });
          // symbol and name share the box; long names may wrap onto a second line
          const name = clip(nameIn(nd.v, o.lang), nd.w * k - 0.2, pt, 2.2 - units(nd.v.symbol + " ") * pt / (144 * (nd.w * k - 0.2)));
          slide.addText([{ text: nd.v.symbol + "  ", options: { bold: true, color: c, fontSize: pt } }, { text: name, options: { color: th.ink, fontSize: pt } }],
          { x: X(nd.x) + 0.08, y: Y(nd.y), w: nd.w * k - 0.16, h: nd.h * k, valign: "middle", ...body, margin: 0, isTextBox: true, lineSpacingMultiple: 0.95 });
        }
        for (const e of lay.edges) {
          if (!e.text) continue;
          const lw = Math.max(0.45, units(e.text) * 0.075 + 0.16);
          slide.addText(e.text, { shape: pres.shapes.ROUNDED_RECTANGLE, x: X(e.mid.x) - lw / 2, y: Y(e.mid.y) - 0.13, w: lw, h: 0.26, rectRadius: 0.13,
            fill: { color: "FFFFFF" }, line: { color: "DCDEE3", width: 0.75 }, fontSize: 9, bold: true, align: "center", valign: "middle",
            color: e.kind === "moderates" ? ROLE.mod : e.neg ? STATUS.blocked : th.ink, ...body, margin: 0 });
        }
      },
      hypotheses() {
        const list = (s.relations || []).filter((r) => r.label || r.kind === "moderates" || r.sign);
        const byId = (id) => H.by(s.variables, id);
        const text = (r) => {
          if (r.kind === "moderates") { const base = H.by(s.relations, r.moderates_id); const z = byId(r.source_id);
            return base ? w.modHyp(nameIn(z, o.lang), nameIn(byId(base.source_id), o.lang), nameIn(byId(base.target_id), o.lang)) : nameIn(z, o.lang); }
          return w.hyp(nameIn(byId(r.source_id), o.lang), nameIn(byId(r.target_id), o.lang), r.sign);
        };
        const rows = list.length ? list : [];
        for (let i = 0; i < Math.max(1, rows.length); i += 7) {
          const { slide, top } = slideFor("hypotheses", w.hypotheses);
          if (!rows.length) { slide.addText(w.noData, { x: M, y: top, w: 6, h: 0.5, fontSize: 14, color: th.muted, ...body, isTextBox: true }); break; }
          const rowH = Math.min(0.68, (SH - top - 0.8) / 7);
          rows.slice(i, i + 7).forEach((r, j) => {
            const y = top + j * rowH;
            slide.addText(r.label || "H", { shape: pres.shapes.ROUNDED_RECTANGLE, x: M, y: y + 0.08, w: 0.75, h: rowH - 0.16, rectRadius: 0.1, fill: { color: th.tint }, line: { color: th.tint, width: 0.5 },
              fontSize: 13, bold: true, color: th.accent, align: "center", valign: "middle", ...body, margin: 0 });
            slide.addText(clip(text(r), SW - 2 * M - 2.3, 15, 2), { x: M + 0.95, y, w: SW - 2 * M - 2.3, h: rowH, fontSize: 15, color: th.ink, ...body, margin: 0, valign: "middle", isTextBox: true });
            if (r.sign) slide.addText(r.sign === "-" ? (o.lang === "en" ? "negative" : "負向") : (o.lang === "en" ? "positive" : "正向"),
              { x: SW - M - 1.2, y, w: 1.2, h: rowH, fontSize: 12, bold: true, color: r.sign === "-" ? STATUS.blocked : STATUS.done, align: "right", valign: "middle", ...body, margin: 0, isTextBox: true });
          });
        }
      },
      variables() {
        const vars = [...s.variables].sort((a, b) => H.ROLE_ORDER.indexOf(a.role) - H.ROLE_ORDER.indexOf(b.role));
        const cw = [0.8, 2.6, 1.4, SW - 2 * M - 0.8 - 2.6 - 1.4 - 1.0, 1.0];
        const hdr = [w.sym, w.variable, w.role, w.measure, w.papers].map((x) => ({ text: x, options: { bold: true, color: "FFFFFF", fill: { color: th.dark } } }));
        for (let i = 0; i < Math.max(1, vars.length); i += 7) {
          const { slide, top } = slideFor("variables", w.variables);
          const rows = [hdr, ...vars.slice(i, i + 7).map((v) => [
            { text: v.symbol, options: { bold: true, color: ROLE[v.role] || th.ink } },
            { text: clip(nameIn(v, o.lang), cw[1] - 0.15, 12, 2) },
            { text: w.roles[v.role] || v.role },
            { text: clip(v.measurement || v.definition || "—", cw[3] - 0.15, 12, 2), options: { color: th.muted } },
            { text: String(H.links("variable_paper", "a", v.id).length), options: { align: "center" } }])];
          if (rows.length === 1) rows.push([{ text: w.noData, options: { colspan: 5, color: th.muted } }]);
          slide.addTable(rows, { x: M, y: top, w: SW - 2 * M, colW: cw, fontSize: 12, color: th.ink, ...body, valign: "middle", rowH: 0.5, margin: 0.08,
            border: { type: "solid", color: th.line, pt: 0.75 }, autoPage: false });
        }
      },
      literature() {
        const { slide, top } = slideFor("literature", w.literature);
        const P = s.papers.filter((p) => p.status !== "excluded");
        const stats = [[P.length, w.total], [P.filter((p) => p.status === "done").length, w.read], [P.filter((p) => p.status === "reading").length, w.reading]];
        const colW = SW * 0.26;
        stats.forEach(([num, label], i) => {
          card(slide, M, top + i * 1.5, colW, 1.3);
          slide.addText(String(num), { x: M + 0.3, y: top + i * 1.5 + 0.12, w: colW - 0.6, h: 0.75, fontSize: 40, bold: true, color: th.ink, ...head, margin: 0, isTextBox: true });
          slide.addText(label, { x: M + 0.3, y: top + i * 1.5 + 0.85, w: colW - 0.6, h: 0.3, fontSize: 12, color: th.muted, ...body, margin: 0, isTextBox: true });
        });
        const x0 = M + colW + 0.45, lw = SW - x0 - M;
        const key = [...P].sort((a, b) => (b.rating || 0) - (a.rating || 0) || (b.year || 0) - (a.year || 0)).slice(0, 6);
        const rowH = Math.min(0.78, (SH - top - 0.8) / Math.max(1, key.length));
        if (!key.length) slide.addText(w.noData, { x: x0, y: top, w: lw, h: 0.5, fontSize: 14, color: th.muted, ...body, isTextBox: true });
        key.forEach((p, i) => slide.addText([
          { text: `${shortAuthors(p.authors) || "—"}${p.year ? ` (${p.year})` : ""}`, options: { bold: true, color: th.ink, fontSize: 14, breakLine: true } },
          { text: clip(p.title, lw, 12), options: { color: th.muted, fontSize: 12 } }],
        { x: x0, y: top + i * rowH, w: lw, h: rowH, valign: "top", ...body, margin: 0, isTextBox: true }));
      },
      progress() {
        const { slide, top } = slideFor("progress", w.progress);
        const ups = (s.updates || []).slice(0, 5);
        if (!ups.length) { slide.addText(w.noData, { x: M, y: top, w: 6, h: 0.5, fontSize: 14, color: th.muted, ...body, isTextBox: true }); return; }
        const rowH = Math.min(1.0, (SH - top - 0.8) / ups.length);
        slide.addShape(pres.shapes.LINE, { x: M + 0.12, y: top + 0.1, w: 0.001, h: rowH * (ups.length - 1) + 0.1, line: { color: th.line, width: 1.5 } });
        ups.forEach((u, i) => {
          const y = top + i * rowH, st = H.by(s.stages, u.stage_id);
          slide.addShape(pres.shapes.OVAL, { x: M, y: y + 0.04, w: 0.24, h: 0.24, fill: { color: "FFFFFF" }, line: { color: th.accent, width: 2 } });
          slide.addText([{ text: `${(u.created || "").slice(0, 10)}　${st ? stageIn(st, o.lang) : ""}　${u.progress_before}% → ${u.progress_after}%`, options: { bold: true, color: th.ink, fontSize: 13, breakLine: true } },
            { text: clip(u.note, SW - 2 * M - 0.6, 12, 2), options: { color: th.muted, fontSize: 12 } }],
          { x: M + 0.5, y, w: SW - 2 * M - 0.6, h: rowH, valign: "top", ...body, margin: 0, isTextBox: true });
        });
      },
      next() {
        const { slide, top } = slideFor("next", w.next);
        const active = s.stages.filter((x) => ["active", "review", "blocked"].includes(x.status));
        const focus = active.length ? active : [current];
        const tasks = s.tasks.filter((x) => !x.done && focus.some((st) => st.id === x.stage_id)).slice(0, 8);
        const cols = 2, gap = 0.3, cw = (SW - 2 * M - gap) / cols, ch = 0.62;
        if (!tasks.length) slide.addText(w.noData, { x: M, y: top, w: 6, h: 0.5, fontSize: 14, color: th.muted, ...body, isTextBox: true });
        tasks.forEach((task, i) => {
          const x = M + (i % cols) * (cw + gap), y = top + Math.floor(i / cols) * (ch + 0.2);
          card(slide, x, y, cw, ch);
          slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.22, y: y + ch / 2 - 0.12, w: 0.24, h: 0.24, fill: { color: "FFFFFF" }, line: { color: th.accent, width: 1.5 }, rectRadius: 0.05 });
          const st = H.by(s.stages, task.stage_id);
          slide.addText([{ text: clip(task.title, cw - 0.8, 14), options: { color: th.ink, fontSize: 14, bold: true, breakLine: true } },
            { text: st ? stageIn(st, o.lang) + (st.due_date ? ` · ${st.due_date}` : "") : "", options: { color: th.muted, fontSize: 11 } }],
          { x: x + 0.6, y, w: cw - 0.75, h: ch, valign: "middle", ...body, margin: 0, isTextBox: true });
        });
      },
      closing() {
        n++;
        const slide = pres.addSlide({ masterName: "RH_DARK" });
        slide.addText(w.thanks, { x: M + 0.1, y: SH / 2 - 1.0, w: SW - 2 * M, h: 1.0, fontSize: 44, bold: true, color: th.onDark, ...head, margin: 0, isTextBox: true });
        slide.addText(w.qa, { x: M + 0.1, y: SH / 2 + 0.1, w: SW - 2 * M, h: 0.5, fontSize: 18, color: th.onDarkMuted, ...body, margin: 0, isTextBox: true });
        if (notes.closing) slide.addNotes(notes.closing);
      },
    };
    for (const key of o.sections) build[key]();

    // Point the theme fonts at the chosen faces too (Latin, East Asian and Traditional Chinese),
    // so text typed later in PowerPoint uses them as well.
    const buf = await pres.write({ outputType: "arraybuffer" });
    const zip = await window.JSZip.loadAsync(buf);
    const path = Object.keys(zip.files).find((f) => /^ppt\/theme\/theme\d+\.xml$/.test(f));
    if (path) {
      let xml = await zip.file(path).async("string");
      const esc = (f) => f.replace(/&/g, "&amp;").replace(/"/g, "&quot;");
      const setFonts = (block, face) => block.replace(/<a:latin typeface="[^"]*"/, `<a:latin typeface="${esc(face)}"`)
        .replace(/<a:ea typeface="[^"]*"/, `<a:ea typeface="${esc(face)}"`).replace(/<a:font script="Hant" typeface="[^"]*"/, `<a:font script="Hant" typeface="${esc(face)}"`);
      xml = xml.replace(/<a:majorFont>[\s\S]*?<\/a:majorFont>/, (b) => setFonts(b, o.headFont)).replace(/<a:minorFont>[\s\S]*?<\/a:minorFont>/, (b) => setFonts(b, o.bodyFont));
      zip.file(path, xml);
    }
    // Drop bare folder entries (not their contents: JSZip's remove() would be recursive);
    // they make some cloud viewers refuse the file.
    for (const [name, entry] of Object.entries(zip.files)) if (entry.dir) delete zip.files[name];
    return { blob: await zip.generateAsync({ type: "blob", mimeType: "application/vnd.openxmlformats-officedocument.presentationml.presentation" }), slides: n };
  }

  /* ---------- default key messages and speaker notes (no AI needed) ---------- */
  function autoText(o) {
    const s = H.state, w = W[o.lang];
    const current = s.stages.find((x) => ["active", "review", "blocked"].includes(x.status)) || s.stages.find((x) => x.status !== "done") || s.stages[0];
    const rels = (s.relations || []).length ? s.relations : H.implicitRelations(s.variables);
    const messages = {
      overview: current ? w.msgOverview(s.overall, stageIn(current, o.lang), current.status === "done" ? 100 : current.progress) : "",
      model: s.variables.length ? w.msgModel(s.variables.length, rels.length) : "",
      next: w.msgNext,
    };
    const notes = {};
    if (current && current.notes) notes.overview = current.notes.slice(0, 1500);
    const latest = (s.updates || [])[0];
    if (latest) notes.progress = latest.note.slice(0, 1500);
    return { messages, notes };
  }

  /* ---------- design instructions → options ---------- */
  function parseInstructions(text, o) {
    const applied = [];
    const has = (re) => re.test(text);
    const fontOf = (frag) => /思源宋|宋體|明體|serif/i.test(frag) && !/新細明/.test(frag) ? "Noto Serif TC" : /新細明/.test(frag) ? "PMingLiU"
      : /思源黑|noto sans/i.test(frag) ? "Noto Sans TC" : /正黑|微軟黑|jhenghei/i.test(frag) ? "Microsoft JhengHei" : /楷/.test(frag) ? "DFKai-SB" : /蘋方|pingfang/i.test(frag) ? "PingFang TC" : null;
    for (const [re, theme] of [[/深藍|海軍藍|navy|學術藍/i, "navy"], [/綠|forest|green/i, "forest"], [/酒紅|紅色|berry|burgundy/i, "berry"], [/炭灰|灰色|charcoal|gray|grey/i, "charcoal"], [/白色|極簡|簡約|minimal|white/i, "minimal"]]) {
      if (has(re)) { o.theme = theme; applied.push(THEMES[theme][H.lang === "en" ? "en" : "zh"]); break; }
    }
    const headM = text.match(/(?:標題|title)[^，。,;\n]{0,8}?(思源宋|宋體|新細明|明體|思源黑|正黑|微軟黑|黑體|楷|蘋方|serif|sans)/i);
    const bodyM = text.match(/(?:內文|本文|內容|正文|body)[^，。,;\n]{0,8}?(思源宋|宋體|新細明|明體|思源黑|正黑|微軟黑|黑體|楷|蘋方|serif|sans)/i);
    if (headM && fontOf(headM[1])) { o.headFont = fontOf(headM[1]); applied.push((H.lang === "en" ? "Title: " : "標題：") + o.headFont); }
    if (bodyM && fontOf(bodyM[1])) { o.bodyFont = fontOf(bodyM[1]); applied.push((H.lang === "en" ? "Body: " : "內文：") + o.bodyFont); }
    if (!headM && !bodyM) {
      const any = text.match(/思源宋|宋體|新細明|明體|思源黑|正黑|微軟黑|黑體|楷|蘋方/);
      if (any && fontOf(any[0])) { o.headFont = o.bodyFont = fontOf(any[0]); applied.push(o.headFont); }
    }
    for (const [re, p] of [[/口試|defen[cs]e|答辯/i, "defense"], [/研討會|conference|發表會/i, "conference"], [/指導教授|進度報告|meeting|advisor|組會|meeting/i, "advisor"]]) {
      if (has(re)) { o.purpose = p; o.sections = [...PURPOSE[p]]; applied.push(W[H.lang === "en" ? "en" : "zh"].purpose[p]); break; }
    }
    if (has(/英文|english/i)) { o.lang = "en"; applied.push("English"); } else if (has(/中文|chinese/i)) { o.lang = "zh"; applied.push("中文"); }
    if (has(/4\s*[:：比]\s*3/)) { o.size = "43"; applied.push("4:3"); } else if (has(/16\s*[:：比]\s*9|寬螢幕|widescreen/i)) { o.size = "169"; applied.push("16:9"); }
    const pages = text.match(/(\d{1,2})\s*(?:頁|張|slides?|pages?)/i);
    if (pages) { o.maxSlides = Number(pages[1]); applied.push((H.lang === "en" ? "max " : "最多 ") + pages[1] + (H.lang === "en" ? " slides" : " 頁")); }
    const LABELS = { overview: /總覽|進度|overview/i, rqs: /研究問題|rq/i, model: /架構|model/i, hypotheses: /假設|hypothes/i, variables: /變數|variable/i, literature: /文獻|literature/i, progress: /近期|日誌|recent/i, next: /下一步|待辦|next/i, closing: /結尾|謝謝|q&a|closing/i };
    for (const m of text.matchAll(/(?:不要|不用|不需要|拿掉|去掉|移除|without|no)\s*([^，。,;\n]{1,10})/gi)) {
      for (const [k, re] of Object.entries(LABELS)) if (re.test(m[1]) && o.sections.includes(k)) { o.sections = o.sections.filter((x) => x !== k); applied.push("− " + t("sl_sec_" + k)); }
    }
    for (const m of text.matchAll(/(?:加上|加入|需要|包含|include|add)\s*([^，。,;\n]{1,10})/gi)) {
      for (const [k, re] of Object.entries(LABELS)) if (re.test(m[1]) && !o.sections.includes(k)) { o.sections.push(k); applied.push("+ " + t("sl_sec_" + k)); }
    }
    o.sections = SECTIONS.filter((k) => o.sections.includes(k));
    return applied;
  }

  function trimToMax(o) {
    if (!o.maxSlides || o.sections.length <= o.maxSlides) return o.sections;
    const keep = new Set(PRIORITY.filter((k) => o.sections.includes(k)).slice(0, o.maxSlides));
    return SECTIONS.filter((k) => keep.has(k));
  }

  /* ---------- the design-instruction window ---------- */
  const PREF_KEY = "rh-slides";
  function savedPrefs() { try { return JSON.parse(localStorage.getItem(PREF_KEY) || "{}"); } catch (_) { return {}; } }
  function savePrefs(o) { try { localStorage.setItem(PREF_KEY, JSON.stringify({ theme: o.theme, headFont: o.headFont, bodyFont: o.bodyFont, size: o.size, purpose: o.purpose, presenter: o.presenter, instructions: o.instructions })); } catch (_) { /* optional */ } }

  H.openSlides = async function () {
    const prefs = savedPrefs();
    const o = { theme: prefs.theme || "minimal", headFont: prefs.headFont || "Noto Serif TC", bodyFont: prefs.bodyFont || "Microsoft JhengHei",
      size: prefs.size || "169", lang: H.lang, purpose: prefs.purpose || "advisor", presenter: prefs.presenter || "", instructions: prefs.instructions || "", maxSlides: 0 };
    o.sections = [...PURPOSE[o.purpose]];
    let usage = null;
    try { usage = await H.api("/api/usage"); } catch (_) { /* optional */ }

    const instr = H.textarea(o.instructions, { rows: 3, placeholder: t("sl_instr_ph") });
    const chips = el("div.sl-chips");
    const useAi = el("input", { type: "checkbox", checked: false, disabled: !(usage && usage.ai) });
    const purposeSeg = el("div.seg.small", { role: "radiogroup", "aria-label": t("sl_purpose") });
    const sectionBox = el("div.sl-sections");
    const themeRow = el("div.sl-themes", { role: "radiogroup", "aria-label": t("sl_theme") });
    const headSel = H.select(o.headFont, FONTS.map(([v, l]) => [v, l]));
    const bodySel = H.select(o.bodyFont, FONTS.map(([v, l]) => [v, l]));
    const sizeSel = H.select(o.size, [["169", "16:9"], ["43", "4:3"]]);
    const langSel = H.select(o.lang, [["zh", "繁體中文"], ["en", "English"]]);
    const presenter = H.input(o.presenter, { placeholder: t("sl_presenter_ph") });
    const fontNote = el("p.hint");
    const preview = el("div.sl-preview");
    const count = el("span.mono.muted.sm");
    const fwStage = H.state.stages.find((x) => x.key === "defense") || H.state.stages.find((x) => x.key === "writing");
    const saveToStage = el("input", { type: "checkbox", checked: !!fwStage, disabled: !fwStage });

    const draw = () => {
      H.put(purposeSeg, Object.keys(PURPOSE).map((p) => el("button.seg-btn", { type: "button", role: "radio", "aria-checked": String(o.purpose === p),
        onclick: () => { o.purpose = p; o.sections = [...PURPOSE[p]]; draw(); } }, W[H.lang === "en" ? "en" : "zh"].purpose[p])));
      H.put(sectionBox, SECTIONS.map((k) => {
        const box = el("input", { type: "checkbox", checked: o.sections.includes(k), onchange: () => { o.sections = box.checked ? SECTIONS.filter((x) => x === k || o.sections.includes(x)) : o.sections.filter((x) => x !== k); draw(); } });
        return el("label.ci-prov", null, box, el("span", null, t("sl_sec_" + k)));
      }));
      H.put(themeRow, Object.entries(THEMES).map(([k, th]) => el("button.sl-theme", { type: "button", role: "radio", "aria-checked": String(o.theme === k), title: th[H.lang === "en" ? "en" : "zh"],
        onclick: () => { o.theme = k; draw(); } }, el("span.sl-sw", { style: { background: "#" + th.dark } }), el("span.sl-sw", { style: { background: "#" + th.tint } }), el("span", null, th[H.lang === "en" ? "en" : "zh"]))));
      headSel.value = o.headFont; bodySel.value = o.bodyFont; sizeSel.value = o.size; langSel.value = o.lang;
      const links = FONTS.filter(([v, , url]) => url && (v === o.headFont || v === o.bodyFont));
      H.put(fontNote, links.length ? [t("sl_font_install"), " ", ...links.map(([v, , url], i) => [i ? "、" : "", el("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, v)])] : t("sl_font_system"));
      const th = THEMES[o.theme];
      const sections = trimToMax(o);
      H.put(preview,
        el("div.sl-mini.dark" + (o.size === "43" ? ".r43" : ""), { style: { background: "#" + th.dark, color: "#" + th.onDark } },
          el("span.sl-mini-eyebrow", { style: { color: "#" + th.onDarkMuted, fontFamily: `"${o.bodyFont}", sans-serif` } }, W[o.lang].purpose[o.purpose]),
          el("span.sl-mini-title", { style: { fontFamily: `"${o.headFont}", serif` } }, H.state.settings.project_title)),
        el("div.sl-mini" + (o.size === "43" ? ".r43" : ""), { style: { background: "#fff", color: "#" + th.ink } },
          el("span.sl-mini-eyebrow", { style: { color: "#" + th.accent, fontFamily: `"${o.bodyFont}", sans-serif` } }, "02 / " + W[o.lang].rqs),
          el("span.sl-mini-head", { style: { fontFamily: `"${o.headFont}", serif` } }, W[o.lang].rqs),
          el("span.sl-mini-card", { style: { background: "#" + th.tint, fontFamily: `"${o.bodyFont}", sans-serif` } },
            el("i", { style: { background: "#" + th.accent } }), (H.state.rqs[0] || { text: W[o.lang].noData }).text)));
      count.textContent = t("sl_count", { n: sections.length });
    };
    headSel.addEventListener("change", () => { o.headFont = headSel.value; draw(); });
    bodySel.addEventListener("change", () => { o.bodyFont = bodySel.value; draw(); });
    sizeSel.addEventListener("change", () => { o.size = sizeSel.value; draw(); });
    langSel.addEventListener("change", () => { o.lang = langSel.value; draw(); });
    const applyInstr = () => {
      const applied = parseInstructions(instr.value, o);
      H.put(chips, applied.length ? applied.map((a) => el("span.pill.tiny", null, H.icon("check", 11), a)) : el("span.muted.sm", null, t("sl_instr_none")));
      draw();
    };
    draw();

    const exportBtn = H.btn(t("sl_export"), { icon: "download", variant: "primary", onclick: async () => {
      if (!o.sections.length) return H.toast(t("sl_pick_one"), "error");
      o.instructions = instr.value; o.presenter = presenter.value.trim();
      parseInstructions(instr.value, o);
      o.sections = trimToMax(o);
      exportBtn.disabled = true;
      try {
        let { messages, notes } = autoText(o);
        if (useAi.checked && instr.value.trim()) {
          try {
            const r = await H.api("/api/slides/ai", { body: { instructions: instr.value, lang: o.lang, sections: o.sections, purpose: o.purpose } });
            messages = { ...messages, ...r.messages };
            notes = { ...notes, ...r.notes };
            H.loadUsage && H.loadUsage();
          } catch (e) { H.toast(e.message, "error"); }
        }
        const { blob, slides } = await buildDeck({ ...o, messages, notes });
        const safe = (H.state.settings.project_title || "research").replace(/[\\/:*?"<>|]+/g, " ").trim().slice(0, 60) || "research";
        const name = `${safe} - ${W[o.lang].purpose[o.purpose]} ${new Date().toISOString().slice(0, 10)}.pptx`;
        await H.saveBlob(blob, name);
        if (saveToStage.checked && fwStage) {
          await H.api("/api/upload?stage_id=" + fwStage.id, { body: blob, headers: { "X-Filename": encodeURIComponent(name), "Content-Type": "application/octet-stream" } });
          await H.refresh(true);
        }
        savePrefs(o);
        H.closeLayer();
        H.toast(t("sl_done", { n: slides }), "ok");
      } catch (e) { H.toast(e.message, "error"); exportBtn.disabled = false; }
    } });

    const section = (num, title, ...kids) => el("section.ci-sec", null, el("div.ci-sec-head", null, el("span.ci-n.mono", null, num), el("h3", null, title)), ...kids);
    const body = el("div.checkin.sl", null,
      section("01", t("sl_instr"), el("p.hint", null, t("sl_instr_hint")), instr,
        el("div.toolbar.wrap", null, H.btn(t("sl_apply_instr"), { icon: "sparkle", small: true, variant: "outline", onclick: applyInstr }), chips),
        el("label.toggle", { title: usage && usage.ai ? "" : t("fw_ai_off") }, useAi, el("span.track-t", null, el("span.knob")),
          el("span", null, usage && usage.ai ? t("sl_ai") : t("sl_ai_off")))),
      section("02", t("sl_purpose"), purposeSeg),
      section("03", t("sl_content"), sectionBox, count),
      section("04", t("sl_design"), themeRow,
        el("div.form-grid", null, H.field(t("sl_head_font"), headSel), H.field(t("sl_body_font"), bodySel), H.field(t("sl_size"), sizeSel), H.field(t("language"), langSel),
          el("div.span2", null, H.field(t("sl_presenter"), presenter))), fontNote),
      section("05", t("sl_preview"), preview,
        el("label.toggle", null, saveToStage, el("span.track-t", null, el("span.knob")), el("span", null, fwStage ? t("sl_save_stage", { stage: H.stageTitle(fwStage) }) : t("sl_no_stage")))));
    H.openLayer("modal", t("sl_title"), body, [H.btn(t("cancel"), { variant: "ghost", onclick: H.closeLayer }), exportBtn], { wide: true, eyebrow: t("sl_eyebrow"), id: "slides" });
    instr.focus();
  };
  H._slides = { parseInstructions, trimToMax, PURPOSE, THEMES, FONTS }; // for tests
})();
