/* Research Hub — title strength check, exam practice, podcast voice and Word export. */
(function () {
  const H = window.H;
  const { el } = H;
  const L = (zh, en) => (H.lang === "en" ? en : zh);
  const prefs = (key, value) => {
    try {
      if (value === undefined) return JSON.parse(localStorage.getItem("hub-" + key) || "{}");
      localStorage.setItem("hub-" + key, JSON.stringify(value));
    } catch (_) { /* private mode */ }
    return {};
  };
  const download = (url) => { const a = el("a", { href: url + "?token=" + encodeURIComponent(H.token) }); document.body.append(a); a.click(); a.remove(); };
  const busy = async (btn, fn) => {
    btn.disabled = true; btn.classList.add("busy");
    try { return await fn(); } catch (e) { H.toast(e.message, "error"); } finally { btn.disabled = false; btn.classList.remove("busy"); }
  };

  /* ================= 1. title strength (like a password meter) ================= */
  const LEVEL = { weak: ["簡單", "Easy", "很多人做過，或還沒有故事"], medium: ["中間", "Medium", "有方向，再把原因與差異說清楚"], strong: ["難", "Hard", "新穎、具體，而且說得出為什麼"] };
  const LEVEL_EN = { weak: "Crowded, or no story yet", medium: "A direction — sharpen the reason and the difference", strong: "Novel, specific, with a clear why" };
  const BAND = { crowded: ["很多人做過", "Crowded"], done: ["有人做過", "Done before"], partial: ["部分重疊", "Partial overlap"], rare: ["少見", "Rare"] };
  const MISSING = {
    reason: ["寫下為什麼要做這個題目（原因）", "Say why this topic (the reason)"], benefit: ["寫下這個題目能做什麼、有什麼幫助", "Say what it enables and how it helps"],
    audience: ["說明誰會受益", "Name who benefits"], complication: ["5C：寫出缺口／問題／謎題", "5C: state the gap, problem or puzzle"],
    concern: ["5C：寫出為什麼重要", "5C: state why it matters"], contribution: ["5C：寫出貢獻", "5C: state the contribution"],
    concepts: ["題目至少包含 3 個具體概念", "Use at least 3 concrete concepts"], relation: ["點出關係（影響、中介、調節…）", "Name the relationship (effect, mediation, moderation…)"],
    context: ["加上研究情境或對象（以…為例）", "Add the context or sample"], length: ["題目長度不宜過短或過長", "Keep the title a sensible length"],
  };
  const METHOD = { ai: ["AI 翻譯", "AI"], mymemory: ["MyMemory 免費翻譯", "MyMemory"], glossary: ["內建詞庫", "built-in glossary"], manual: ["自訂", "manual"], none: ["原文", "original"] };

  H.topicView = function () {
    const tp = H.state.topic || {};
    if (!tp.id) return null;
    let res = null;
    try { res = tp.checked ? JSON.parse(tp.checked) : null; } catch (_) { res = null; }
    const save = el("span.save-state.mono", { "aria-live": "polite" });
    const title = H.autosave(H.input(tp.title, { id: "tp-title", placeholder: L("論文題目，例如：信任對知覺有用性與使用意圖關係之調節效果：以台灣網路購物為例", "Thesis title"), dataset: { fkey: "tp-title" } }), "topic", tp.id, "title", save);
    const titleEn = H.autosave(H.input(tp.title_en, { placeholder: L("英文題目（留空會自動翻譯後檢測）", "English title (optional)"), dataset: { fkey: "tp-en" } }), "topic", tp.id, "title_en", save);
    const reason = H.autosave(H.textarea(tp.reason, { rows: 3, placeholder: L("原因：你看到什麼現象或矛盾？為什麼現在要做？", "Reason: what did you observe, and why now?") }), "topic", tp.id, "reason", save);
    const benefit = H.autosave(H.textarea(tp.benefit, { rows: 3, placeholder: L("故事：做出來能做什麼？能幫誰解決什麼問題？", "Story: what does it enable, whose problem does it solve?") }), "topic", tp.id, "benefit", save);
    const audience = H.autosave(H.input(tp.audience, { placeholder: L("誰會受益：例如 電商平台經理、政策制定者", "Who benefits") }), "topic", tp.id, "audience", save);
    const useAi = el("input", { type: "checkbox" });
    const online = el("input", { type: "checkbox", checked: true });
    const run = H.btn(L("檢測題目", "Check title"), { icon: "search", variant: "primary", onclick: () => busy(run, async () => {
      if (!title.value.trim()) { title.focus(); throw new Error(L("請先輸入題目", "Enter a title first")); }
      await H.api("/api/topic/check", { body: { title: title.value, title_en: titleEn.value, online: online.checked, ai: useAi.checked } });
      await H.refresh(true);
    }) });

    const meter = (level) => el("div.tp-meter", { role: "img", "aria-label": level ? LEVEL[level][H.lang === "en" ? 1 : 0] : "" },
      ["weak", "medium", "strong"].map((k, i) => el("span.tp-seg" + (level && i <= ["weak", "medium", "strong"].indexOf(level) ? ".on." + level : ""), null)));
    const bar = (label, value) => el("div.tp-bar", null, el("span.lbl", null, label),
      el("div.tp-track", null, el("i", { style: { width: (value == null ? 0 : value) + "%" } })), el("span.mono", null, value == null ? "—" : value + "%"));
    const works = (list) => el("ul.tp-works", null, list.map((w) => {
      const url = H.safeUrl(w.url);
      return el("li", null, el("span.tp-pct.mono." + (w.overlap >= 70 ? "hi" : w.overlap >= 50 ? "mid" : "lo"), null, w.overlap + "%"),
        url ? el("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, w.title) : el("span", null, w.title), w.year ? el("span.mono.muted", null, " " + w.year) : null);
    }));

    let result = el("p.empty.sm", null, L("輸入題目後按「檢測題目」：系統會斷詞、把中文題目翻成英文，再到 OpenAlex 比對台灣與國外已發表的研究。", "Enter a title and press Check: the hub segments it, translates Chinese to English and compares it with published work in Taiwan and abroad (OpenAlex)."));
    if (res && res.title === (tp.title || "").trim()) {
      const lv = res.level, tr = res.translation || {};
      const region = (key, name) => {
        const r = (res.regions || {})[key];
        if (!r) return el("div.tp-region", null, el("h5", null, name), el("p.muted.sm", null, L("未連線，無法比對", "Offline — not compared")));
        return el("div.tp-region", null,
          el("h5", null, name, el("span.pill.tp-" + r.band, null, `${BAND[r.band][H.lang === "en" ? 1 : 0]} · ${r.max}%`)),
          el("p.muted.sm", null, L(`相關研究 ${r.count.toLocaleString()} 篇${r.relaxed ? "（以前三個概念放寬搜尋）" : ""}，其中重疊 ≥50% 的有 ${r.similar} 篇`, `${r.count.toLocaleString()} related works${r.relaxed ? " (relaxed to the first three concepts)" : ""}; ${r.similar} with ≥50% overlap`)),
          r.works.length ? works(r.works) : el("p.muted.sm", null, L("沒有重疊 30% 以上的題目", "No title overlaps 30% or more")));
      };
      const missing = [...(res.missing?.story || []), ...(res.missing?.specificity || [])];
      result = el("div.tp-result", null,
        el("div.tp-head", null, meter(lv),
          el("div", null, el("strong.tp-level." + lv, null, LEVEL[lv][H.lang === "en" ? 1 : 0]), el("span.muted.sm", null, " · " + (H.lang === "en" ? LEVEL_EN[lv] : LEVEL[lv][2]))),
          el("span.mono.tp-score", null, res.score + " / 100")),
        res.parts.novelty == null ? el("p.muted.sm", null, L("尚未連線比對重疊度，所以最高只會顯示「中間」。勾選「連線比對」再檢測一次。", "Overlap was not checked online, so the level is capped at Medium. Tick Compare online and check again.")) : null,
        el("div.tp-bars", null, bar(L("新穎性（與既有研究不重疊）", "Novelty"), res.parts.novelty), bar(L("具體性（概念、關係、情境）", "Specificity"), res.parts.specificity), bar(L("故事性（原因與幫助）", "Story"), res.parts.story)),
        el("div.tp-tokens", null, el("span.lbl", null, L("斷詞", "Tokens")), el("div.chips", null, res.tokens.map((w) => el("span.chip", null, w)))),
        tr.method && tr.method !== "none" ? el("p.tp-tr", null, el("span.lbl", null, L("英文檢測用題目", "English used for the check") + `（${METHOD[tr.method][H.lang === "en" ? 1 : 0]}）`), tr.text || "—",
          tr.missing?.length ? el("span.muted.sm", null, L(" · 詞庫未收錄：", " · not in glossary: ") + tr.missing.join("、")) : null) : null,
        el("div.tp-regions", null, region("tw", L("台灣", "Taiwan")), region("abroad", L("國外", "Abroad"))),
        res.library?.length ? el("div.tp-region", null, el("h5", null, L("與我的文獻庫重疊", "Overlap with my library")), works(res.library)) : null,
        missing.length ? el("div.tp-todo", null, el("span.lbl", null, L("讓題目更強", "To strengthen it")), el("ul", null, missing.map((k) => el("li", null, MISSING[k][H.lang === "en" ? 1 : 0])))) : null,
        res.errors?.length ? el("p.muted.sm", null, L("部分來源無法連線：", "Some sources were unreachable: ") + res.errors.join("; ").slice(0, 200)) : null);
    }

    return el("section.card.tp", null,
      el("div.card-head", null, el("h4", null, L("題目設定與強度檢測", "Title and strength check")), save),
      el("p.hint", null, L("好題目不是變數的排列：要有原因和故事，說得出這個題目能做什麼、對誰有幫助。", "A good title is not a list of variables: it needs a reason and a story — what it enables and whom it helps.")),
      el("div.form-grid", null,
        el("div.span2", null, H.field(L("論文題目", "Thesis title"), title)), el("div.span2", null, H.field(L("英文題目", "English title"), titleEn)),
        H.field(L("為什麼做（原因）", "Why (reason)"), reason), H.field(L("能做什麼、有什麼幫助（故事）", "What it enables (story)"), benefit),
        el("div.span2", null, H.field(L("誰會受益", "Who benefits"), audience))),
      el("div.toolbar.wrap", null, run,
        el("label.ci-prov", null, online, el("span", null, L("連線比對（題目會送到 OpenAlex 與翻譯服務）", "Compare online (the title is sent to OpenAlex and a translator)"))),
        el("label.ci-prov", null, useAi, el("span", null, L("用 AI 翻譯", "Translate with AI")))),
      result);
  };

  /* ================= 2. exam practice ================= */
  /* Spaced review: every pass doubles the gap, a weak answer brings the item back tomorrow. */
  const today = () => { const d = new Date(); return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
  const addDays = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10); };
  const STEPS = [1, 3, 7, 14, 30, 60];
  const nextGap = (gap, score) => (score < 60 ? 1 : score < 80 ? Math.max(2, Math.min(gap || 2, 3)) : STEPS.find((x) => x > (gap || 0)) || 60);
  const isDue = (x) => !!x.review_date && x.review_date <= today();
  H.reviewQueue = function () {
    const s = H.state;
    const due = s.questions.filter(isDue).sort((a, b) => a.score - b.score || a.review_date.localeCompare(b.review_date));
    const fresh = s.questions.filter((q) => q.status === "new" && !q.review_date);
    return { questions: [...due, ...fresh].slice(0, 3), dueQuestions: due.length, papers: s.papers.filter(isDue).sort((a, b) => a.review_date.localeCompare(b.review_date)) };
  };
  /* Weak spots: per folder, the average of each practised question's latest score. */
  H.examStats = function () {
    const by = new Map();
    for (const q of H.state.questions) {
      const f = q.folder || "";
      const g = by.get(f) || by.set(f, { folder: f, total: 0, done: 0, sum: 0, mastered: 0 }).get(f);
      g.total += 1;
      if (q.status !== "new") { g.done += 1; g.sum += q.score; }
      if (q.status === "mastered") g.mastered += 1;
    }
    return [...by.values()].map((g) => ({ ...g, avg: g.done ? Math.round(g.sum / g.done) : null })).sort((a, b) => (a.avg ?? 101) - (b.avg ?? 101));
  };
  const reviewPaper = (p) => { const gap = STEPS.find((x) => x > (p.review_interval || 0)) || 60; return H.ops([{ op: "update", entity: "paper", id: p.id, data: { review_interval: gap, review_date: addDays(gap) } }]); };

  const KIND = { past: ["歷屆考題", "Past"], predicted: ["考題預測", "Predicted"], practice: ["自訂練習", "Practice"] };
  const DIFF = { "": ["—", "—"], easy: ["簡單", "Easy"], medium: ["中等", "Medium"], hard: ["難", "Hard"] };
  const QSTATUS = { new: ["未練習", "New"], practiced: ["已練習", "Practiced"], mastered: ["已掌握", "Mastered"] };
  const pick = (map, k) => (map[k] || map[""] || ["", ""])[H.lang === "en" ? 1 : 0];
  const countWords = (text) => (text.match(/[㐀-鿿]/g) || []).length + (text.match(/[A-Za-z]+/g) || []).length;

  H.editQuestion = function (q, defaults) {
    const d = q || { kind: "past", folder: H.ui.examFolder && H.ui.examFolder !== "*" ? H.ui.examFolder : "", minutes: 30, ...defaults };
    const text = H.textarea(d.text, { rows: 4 }), folder = H.input(d.folder, { placeholder: L("資料夾，例如 研究方法／第 5 週", "Folder"), list: "exam-folders" });
    const kind = H.select(d.kind, Object.keys(KIND).map((k) => [k, pick(KIND, k)])), diff = H.select(d.difficulty || "", Object.keys(DIFF).map((k) => [k, pick(DIFF, k)]));
    const source = H.input(d.source, { placeholder: L("出處，例如 113 年博士班資格考", "Source") }), year = H.input(d.year || "", { type: "number", min: 0, max: 3000 });
    const minutes = H.input(d.minutes || 30, { type: "number", min: 0, max: 600 });
    const analysis = H.textarea(d.analysis, { rows: 4 }), outline = H.textarea(d.outline, { rows: 6 });
    const paper = H.select(String(d.paper_id || 0), [["0", "—"], ...H.state.papers.map((p) => [String(p.id), p.title.slice(0, 70)])]);
    const save = async () => {
      if (!text.value.trim()) { text.focus(); return H.toast(L("請輸入題目", "Enter the question"), "error"); }
      const data = { text: text.value, folder: folder.value.trim(), kind: kind.value, difficulty: diff.value, source: source.value, year: Number(year.value || 0),
        minutes: Number(minutes.value || 0), analysis: analysis.value, outline: outline.value, paper_id: Number(paper.value) };
      try { await H.ops([q ? { op: "update", entity: "question", id: q.id, data } : { op: "create", entity: "question", data }], true); H.closeLayer(); } catch (e) { H.toast(e.message, "error"); }
    };
    H.openLayer("modal", q ? L("編輯考題", "Edit question") : L("新增考題", "Add question"), el("div.form-grid", null,
      el("div.span2", null, H.field(L("題目", "Question") + " *", text)), H.field(L("資料夾", "Folder"), folder), H.field(L("類型", "Kind"), kind),
      H.field(L("難度", "Difficulty"), diff), H.field(L("作答時間（分鐘）", "Minutes"), minutes), H.field(L("出處", "Source"), source), H.field(L("年度", "Year"), year),
      el("div.span2", null, H.field(L("相關文獻", "Related paper"), paper)),
      el("div.span2", null, H.field(L("考題解析", "Analysis"), analysis)), el("div.span2", null, H.field(L("答題架構（一行一個重點）", "Answer outline (one point per line)"), outline))),
    [q ? H.btn(L("刪除", "Delete"), { icon: "trash", variant: "danger-ghost", class: "left", onclick: async () => { if (await H.confirm(L("刪除這題？", "Delete this question?"))) H.ops([{ op: "delete", entity: "question", id: q.id }]); } }) : null,
      H.btn(L("取消", "Cancel"), { variant: "ghost", onclick: H.closeLayer }), H.btn(L("儲存", "Save"), { variant: "primary", onclick: save })], { wide: true });
  };

  /* Timed essay practice: write, hand in, get coverage of the outline (and AI comments when available). */
  H.practiceQuestion = function (q) {
    const total = (q.minutes || 30) * 60;
    let left = total, timer = null, done = false;
    const clock = el("span.ex-clock.mono", null, "");
    const answer = H.textarea(q.answer, { rows: 16, placeholder: L("在這裡作答。建議先用 3 分鐘列出架構，再分段書寫。", "Write your answer. Spend 3 minutes outlining first."), class: "ex-answer" });
    const words = el("span.mono.muted.sm");
    const feedback = el("div.ex-feedback");
    const useAi = el("input", { type: "checkbox" });
    const show = () => { clock.textContent = `${String(Math.floor(Math.abs(left) / 60)).padStart(2, "0")}:${String(Math.abs(left) % 60).padStart(2, "0")}${left < 0 ? " +" : ""}`; clock.classList.toggle("late", left < 0); };
    const tick = () => { left -= 1; show(); if (!document.body.contains(clock)) clearInterval(timer); };
    const start = () => { if (!timer && !done) timer = setInterval(tick, 1000); };
    answer.addEventListener("input", () => { words.textContent = L(`${countWords(answer.value)} 字`, `${countWords(answer.value)} words`); start(); });
    words.textContent = L(`${countWords(answer.value)} 字`, `${countWords(answer.value)} words`);
    show();
    const submit = H.btn(L("交卷並評分", "Hand in and grade"), { icon: "check", variant: "primary", onclick: () => busy(submit, async () => {
      const r = await H.api("/api/exam/grade", { body: { id: q.id, answer: answer.value, ai: useAi.checked, lang: H.lang } });
      clearInterval(timer); done = true;
      const text = [L(`涵蓋答題架構 ${r.coverage}%`, `Outline coverage ${r.coverage}%`), r.strengths ? L("優點：", "Strengths: ") + r.strengths : "", r.gaps ? L("不足：", "Gaps: ") + r.gaps : "",
        r.tip ? L("改寫建議：", "Tip: ") + r.tip : "", r.missed.length ? L("尚未寫到：", "Not covered: ") + r.missed.join("；") : ""].filter(Boolean).join("\n");
      const gap = nextGap(q.review_interval, r.score);
      await H.api("/api/ops", { body: { ops: [
        { op: "update", entity: "question", id: q.id, data: { answer: answer.value, score: r.score, feedback: text, status: r.score >= 80 ? "mastered" : "practiced", review_interval: gap, review_date: addDays(gap) } },
        { op: "create", entity: "attempt", data: { question_id: q.id, answer: answer.value, score: r.score, coverage: r.coverage, feedback: text, seconds: Math.max(0, total - left) } }] } });
      q.review_interval = gap;
      H.toast(L(`已記錄，${gap} 天後再複習`, `Recorded — review again in ${gap} day(s)`), "ok");
      H.put(feedback, el("div.ex-score", null, el("strong.mono", null, r.score), el("span", null, " / 100 · " + (r.method === "ai" ? "AI" : L("依答題架構關鍵詞比對", "outline keyword match")))),
        r.hit.length ? el("ul.ex-hit", null, r.hit.map((p) => el("li", null, H.icon("check", 13), p))) : null,
        r.missed.length ? el("ul.ex-miss", null, r.missed.map((p) => el("li", null, H.icon("alert", 13), p))) : null,
        r.strengths ? el("p", null, el("b", null, L("優點 ", "Strengths ")), r.strengths) : null, r.gaps ? el("p", null, el("b", null, L("不足 ", "Gaps ")), r.gaps) : null,
        r.tip ? el("p", null, el("b", null, L("改寫建議 ", "Tip ")), r.tip) : null);
      H.refresh(true);
    }) });
    H.openLayer("modal", L("申論模擬練習", "Essay practice"), el("div.ex-practice", null,
      el("div.ex-qbox", null, el("p.ex-qtext", null, q.text), el("div.ex-meta", null, clock, words, el("span.muted.sm", null, L(`建議 ${q.minutes || 30} 分鐘，開始打字後計時`, `${q.minutes || 30} min · the clock starts when you type`)))),
      answer,
      q.outline ? el("details.c5-more", null, el("summary", null, L("看答題架構（先自己寫完再看）", "Show the outline (try first)")), el("pre.ex-pre", null, q.outline)) : el("p.muted.sm", null, L("這題還沒有答題架構：先按「解析」產生，評分會更準。", "No outline yet — run Analyse first for better grading.")),
      feedback),
    [el("label.ci-prov.left", null, useAi, el("span", null, L("AI 講評（需在設定填 AI 金鑰）", "AI comments (needs an AI key)"))),
      H.btn(L("關閉", "Close"), { variant: "ghost", onclick: H.closeLayer }), submit], { wide: true });
  };

  async function analyze(q, btn, ai) {
    await busy(btn, async () => {
      const r = await H.api("/api/exam/analyze", { body: { id: q.id, ai, lang: H.lang } });
      await H.ops([{ op: "update", entity: "question", id: q.id, data: { analysis: r.analysis, ...(q.outline && !ai ? {} : { outline: r.outline }) } }], true);
      H.toast(L("已產生解析", "Analysis ready"), "ok");
    });
  }

  async function predict(ai, btn) {
    const folder = H.ui.examFolder && H.ui.examFolder !== "*" ? H.ui.examFolder : "";
    const r = await busy(btn, () => H.api("/api/exam/predict", { body: { folder, ai, lang: H.lang } }));
    if (!r) return;
    if (!r.questions.length) return H.toast(L("資料還不夠：先加入歷屆考題或在文獻寫 5C 筆記", "Not enough data yet: add past questions or 5C notes"), "error");
    showCandidates(r, L("考題預測", "Predicted questions"), r.method === "ai" ? L("由 AI 依歷屆考題與文獻筆記預測。", "Predicted by AI from past questions and notes.")
      : L("依歷屆考題高頻主題、文獻 5C 筆記與你的變數產生。", "From frequent past topics, 5C notes and your variables."));
  }

  function showCandidates(r, heading, note) {
    const chosen = new Set(r.questions.map((_, i) => i));
    const spans = [];
    const list = el("ul.ex-predict", null, r.questions.map((q, i) => {
      const box = el("input", { type: "checkbox", checked: true, onchange: () => (box.checked ? chosen.add(i) : chosen.delete(i)) });
      const span = el("span", null, q.text); spans.push(span);
      return el("li", null, el("label.ci-prov", null, box, span), el("span.mono.muted.sm", null, `${pick(DIFF, q.difficulty)} · ${q.reason || ""}`));
    }));
    // The detected paper title can be wrong (journal headers, slides): let the user correct it once for every question.
    let current = (r.facts || {}).title || "";
    const titleFix = current ? H.input(current, { "aria-label": L("論文題目", "Paper title") }) : null;
    if (titleFix) titleFix.addEventListener("input", () => {
      const next = titleFix.value.trim() || current;
      r.questions.forEach((q, i) => { q.text = q.text.split(current).join(next); spans[i].textContent = q.text; });
      current = next;
    });
    H.openLayer("modal", heading, el("div", null, el("p.hint", null, note),
      titleFix ? H.field(L("偵測到的論文題目（不對可以直接改，題目文字會一起更新）", "Detected paper title (edit it if wrong; the questions update)"), titleFix) : null, list),
    [H.btn(L("取消", "Cancel"), { variant: "ghost", onclick: H.closeLayer }), H.btn(L("加入題庫", "Add to bank"), { variant: "primary", onclick: async () => {
      const ops = r.questions.filter((_, i) => chosen.has(i)).map((q) => ({ op: "create", entity: "question", data: { text: q.text, folder: q.folder || "", kind: "predicted",
        difficulty: q.difficulty || "", outline: q.outline || "", paper_id: q.paper_id || 0, source: r.source || (r.method === "ai" ? "AI" : ""), minutes: 30 } }));
      if (ops.length) await H.ops(ops, true);
      H.closeLayer();
    } })], { wide: true });
  }

  H.examView = function () {
    const s = H.state, ui = H.ui;
    ui.examFolder = ui.examFolder || "*"; ui.examKind = ui.examKind || "all"; ui.examMode = ui.examMode || "questions";
    const folders = [...new Set([...s.questions.map((q) => q.folder || ""), ...s.papers.map((p) => p.folder || "").filter(Boolean)])].sort((a, b) => a.localeCompare(b, "zh-Hant"));
    const inFolder = (x) => ui.examFolder === "*" || (x.folder || "") === ui.examFolder;
    const qs = s.questions.filter((q) => inFolder(q) && (ui.examKind === "all" || q.kind === ui.examKind));
    const ps = s.papers.filter((p) => inFolder(p) && (ui.examFolder !== "*" || p.folder));
    const go = (patch) => { Object.assign(ui, patch); H.render.exam(); };
    const side = el("nav.ex-folders", { "aria-label": L("資料夾", "Folders") },
      el("datalist", { id: "exam-folders" }, folders.filter(Boolean).map((f) => el("option", { value: f }))),
      [["*", L("全部", "All")], ...folders.map((f) => [f, f || L("未分類", "Unfiled")])].map(([f, name]) =>
        el("button.ex-folder" + (ui.examFolder === f ? ".on" : ""), { type: "button", dataset: { fkey: "exf-" + f }, onclick: () => go({ examFolder: f }) },
          H.icon("folder", 14), el("span", null, name),
          el("span.mono.muted", null, String(f === "*" ? s.questions.length : s.questions.filter((q) => (q.folder || "") === f).length)))));
    const aiBox = el("input", { type: "checkbox", checked: !!ui.examAi, onchange: (e) => { ui.examAi = e.target.checked; } });
    const predictBtn = H.btn(L("考題預測", "Predict"), { icon: "sparkle", variant: "outline", onclick: () => predict(aiBox.checked, predictBtn) });
    const seedBtn = H.btn(L("載入研究方法範例題庫", "Load starter bank"), { icon: "download", variant: "ghost", onclick: () => busy(seedBtn, async () => {
      const r = await H.api("/api/exam/seed", { body: {} }); H.toast(L(`已加入 ${r.added} 題`, `${r.added} added`), "ok"); await H.refresh(true);
    }) });
    const toolbar = el("div.toolbar.wrap", null,
      ui.examMode === "questions" ? el("div.seg.small", { role: "radiogroup" }, [["all", L("全部", "All")], ...Object.keys(KIND).map((k) => [k, pick(KIND, k)])].map(([k, l]) =>
        el("button.seg-btn", { type: "button", role: "radio", "aria-checked": String(ui.examKind === k), dataset: { fkey: "exk-" + k }, onclick: () => go({ examKind: k }) }, l))) : null,
      el("span.grow"), el("label.ci-prov", null, aiBox, el("span", null, "AI")), predictBtn,
      H.btn(L("新增考題", "Add question"), { icon: "plus", variant: "primary", onclick: () => H.editQuestion() }));

    let main;
    if (ui.examMode === "papers") {
      main = ps.length ? el("div.ex-list", null, ps.map((p) => el("article.ex-card", null,
        el("div.ex-card-head", null, el("button.paper-title", { type: "button", onclick: () => H.editPaper(p) }, p.title), H.fiveCDots(p)),
        el("p.muted.sm", null, `${(p.authors || "").split(";")[0]}${p.year ? " · " + p.year : ""}${p.folder ? " · " + p.folder : ""}`),
        el("dl.ex-5c", null, H.FIVE_C.filter((c) => (p["c_" + c.key] || "").trim()).map((c) => [el("dt", null, H.lang === "en" ? c.en : c.zh), el("dd", null, p["c_" + c.key])])),
        el("div.ex-actions", null,
          H.btn(L("依此文獻出題", "Make a question"), { icon: "plus", small: true, variant: "ghost", onclick: () => H.editQuestion(null, { kind: "predicted", folder: p.folder || "", paper_id: p.id,
            text: L(`請說明「${p.title}」一文想解決的缺口、採取的研究方法與主要貢獻，並評論其研究設計的限制。`, `Explain the gap, method and contribution of “${p.title}”, and critique its design.`),
            outline: H.FIVE_C.map((c, i) => `${i + 1}. ${H.lang === "en" ? c.en : c.zh}：${(p["c_" + c.key] || "").trim()}`).join("\n") }) }),
          H.btn(L("朗讀／Podcast", "Read aloud"), { icon: "play", small: true, variant: "ghost", onclick: () => H.openVoice({ title: p.title, text: H.paperScript(p) }) }),
          H.btn(p.review_date ? L("已複習", "Reviewed") : L("加入複習排程", "Start reviewing"), { icon: "check", small: true, variant: isDue(p) ? "outline" : "ghost", onclick: () => reviewPaper(p) }),
          p.review_date ? el("span.muted.sm" + (isDue(p) ? ".due" : ""), null, isDue(p) ? L("今天該複習", "Due today") : L(`下次複習 ${p.review_date}`, `Next review ${p.review_date}`)) : null))))
        : el("p.empty", null, L("在文獻的編輯視窗填「資料夾」，文獻就會出現在這裡，並可依 5C 筆記做文獻解析與出題。", "Give papers a Folder in their editor to organise readings here."));
    } else {
      main = qs.length ? el("div.ex-list", null, qs.map((q) => {
        const aBtn = H.btn(L("解析", "Analyse"), { icon: "sparkle", small: true, variant: "ghost", onclick: () => analyze(q, aBtn, aiBox.checked) });
        const paper = q.paper_id ? H.by(s.papers, q.paper_id) : null;
        return el("article.ex-card." + q.status, null,
          el("div.ex-card-head", null,
            el("span.pill.kind-" + q.kind, null, pick(KIND, q.kind)), q.difficulty ? el("span.pill.diff-" + q.difficulty, null, pick(DIFF, q.difficulty)) : null,
            el("span.pill" + (q.status === "mastered" ? ".approved" : ""), null, pick(QSTATUS, q.status) + (q.score ? ` · ${q.score}` : "")),
            el("span.mono.muted.sm.push", null, [q.folder, q.source, q.year || ""].filter(Boolean).join(" · "))),
          el("p.ex-qtext", null, q.text),
          paper ? el("p.muted.sm", null, H.icon("file", 12), " " + paper.title) : null,
          (() => {
            const tries = s.attempts.filter((a) => a.question_id === q.id).reverse();
            if (!tries.length) return null;
            return el("p.ex-history", { title: L("歷次分數", "Score history") }, el("span.lbl", null, L(`練習 ${tries.length} 次`, `${tries.length} attempt(s)`)),
              tries.slice(-8).map((a) => el("span.ex-try.mono" + (a.score >= 80 ? ".hi" : a.score >= 60 ? ".mid" : ".lo"), { title: a.created.slice(0, 10) }, String(a.score))),
              q.review_date ? el("span.muted.sm" + (isDue(q) ? ".due" : ""), null, isDue(q) ? L("今天該複習", "Due today") : L(`下次複習 ${q.review_date}`, `Next review ${q.review_date}`)) : null);
          })(),
          q.analysis || q.outline || q.feedback ? el("details.c5-more", null, el("summary", null, L("解析與答題架構", "Analysis and outline")),
            q.analysis ? el("pre.ex-pre", null, q.analysis) : null, q.outline ? el("pre.ex-pre", null, q.outline) : null,
            q.feedback ? el("pre.ex-pre.fb", null, L("上次講評\n", "Last feedback\n") + q.feedback) : null) : null,
          el("div.ex-actions", null,
            H.btn(L("申論練習", "Practise"), { icon: "play", small: true, variant: "outline", onclick: () => H.practiceQuestion(q) }), aBtn,
            H.btn(L("朗讀", "Read aloud"), { icon: "play", small: true, variant: "ghost", onclick: () => H.openVoice({ title: q.text.slice(0, 40), text: H.questionScript(q) }) }),
            H.btn(L("編輯", "Edit"), { icon: "edit", small: true, variant: "ghost", onclick: () => H.editQuestion(q) })));
      })) : el("div.empty", null, el("p", null, L("還沒有考題。可以新增歷屆考題、載入範例題庫，或按「考題預測」。", "No questions yet. Add past questions, load the starter bank or predict.")), seedBtn);
    }
    const fileIn = el("input", { type: "file", accept: ".pdf,.docx,.txt,.md,.tex", hidden: true });
    const upFolder = H.input(ui.examFolder !== "*" ? ui.examFolder : "", { placeholder: L("存到資料夾（選填）", "Folder (optional)"), list: "exam-folders", class: "sm", "aria-label": L("資料夾", "Folder") });
    const upBtn = H.btn(L("選擇論文檔案", "Choose a paper"), { icon: "upload", variant: "primary", onclick: () => fileIn.click() });
    const fromFile = (file) => busy(upBtn, async () => {
      if (!file) return;
      const qsx = new URLSearchParams({ lang: H.lang, folder: upFolder.value.trim(), ai: aiBox.checked ? "1" : "0" });
      const r = await H.api("/api/exam/from-file?" + qsx, { body: file, headers: { "X-Filename": encodeURIComponent(file.name), "Content-Type": "application/octet-stream" } });
      const f = r.facts || {};
      const found = [f.title ? L("題目：", "Title: ") + f.title : "", f.methods?.length ? L("方法：", "Method: ") + f.methods.map((m) => m[H.lang === "en" ? 1 : 0]).join(L("、", ", ")) : "",
        f.hypotheses?.length ? L(`假設 ${f.hypotheses.length} 條`, `${f.hypotheses.length} hypotheses`) : "", f.terms?.length ? L("關鍵詞：", "Terms: ") + f.terms.join(L("、", ", ")) : ""].filter(Boolean).join(" ｜ ");
      showCandidates(r, L("由論文出題", "Questions from the paper") + " · " + file.name, (r.method === "ai" ? L("由 AI 閱讀全文後出題。", "Written by AI from the text. ") : L("依規則從全文辨識題目、方法、假設與關鍵詞後出題（勾選 AI 可出更貼近內容的題目）。", "Rule-based from the detected title, methods, hypotheses and terms (tick AI for closer questions). ")) + found);
    });
    fileIn.addEventListener("change", () => { fromFile(fileIn.files[0]); fileIn.value = ""; });
    const drop = el("div.ex-upload", { ondragover: (e) => { e.preventDefault(); drop.classList.add("over"); }, ondragleave: () => drop.classList.remove("over"),
      ondrop: (e) => { e.preventDefault(); drop.classList.remove("over"); fromFile(e.dataTransfer.files[0]); } },
      el("div", null, el("h4", null, L("由上傳的論文檔案出題", "Questions from an uploaded paper")),
        el("p.muted.sm", null, L("拖曳或選擇一篇論文（PDF、Word .docx、.txt）。系統讀取全文後產生申論題與答題架構，你勾選要留下的題目才會存進題庫。檔案只在這台電腦處理；勾選 AI 時才會把文字送到你設定的 AI 服務。",
          "Drop or choose a paper (PDF, .docx, .txt). The hub reads it and drafts essay questions with outlines; only the ones you tick are saved. The file stays on this computer unless AI is ticked."))),
      el("div.ex-upload-act", null, upFolder, upBtn, fileIn));
    const practiced = s.questions.filter((q) => q.status !== "new").length;
    const queue = H.reviewQueue(), stats = H.examStats().filter((g) => g.total);
    const todayCard = s.questions.length || queue.papers.length ? el("div.ex-today", null,
      el("div.card", null, el("div.card-head", null, el("h4", null, L("今天該複習", "Review today")),
        el("span.mono.muted", null, L(`到期考題 ${queue.dueQuestions} · 文獻 ${queue.papers.length}`, `${queue.dueQuestions} questions · ${queue.papers.length} papers due`))),
        queue.questions.length ? el("ol.ex-queue", null, queue.questions.map((q) => el("li", null,
          el("button.ex-queue-q", { type: "button", onclick: () => H.practiceQuestion(q) }, q.text),
          el("span.pill" + (isDue(q) ? ".warn" : ""), null, isDue(q) ? L(`上次 ${q.score} 分`, `last ${q.score}`) : L("未練習", "New")))))
          : el("p.muted.sm", null, L("今天沒有到期的考題。", "No questions due today.")),
        queue.papers.length ? el("ul.ex-queue.papers", null, queue.papers.slice(0, 3).map((p) => el("li", null,
          el("button.ex-queue-q", { type: "button", onclick: () => H.openVoice({ title: p.title, text: H.paperScript(p) }) }, H.icon("play", 13), " " + p.title),
          H.btn(L("已複習", "Reviewed"), { small: true, variant: "ghost", icon: "check", onclick: () => reviewPaper(p) })))) : null),
      el("div.card", null, el("div.card-head", null, el("h4", null, L("弱點分析", "Weak spots")), el("span.mono.muted", null, L("各資料夾最近一次分數的平均", "average latest score per folder"))),
        stats.some((g) => g.done) ? el("ul.ex-weak", null, stats.map((g) => el("li", null,
          el("button.ex-weak-name", { type: "button", onclick: () => go({ examFolder: g.folder, examMode: "questions" }) }, g.folder || L("未分類", "Unfiled")),
          el("div.tp-track", null, el("i." + (g.avg == null ? "none" : g.avg >= 80 ? "hi" : g.avg >= 60 ? "mid" : "lo"), { style: { width: (g.avg ?? 0) + "%" } })),
          el("span.mono", null, g.avg == null ? "—" : String(g.avg)), el("span.mono.muted.sm", null, `${g.done}/${g.total}`))))
          : el("p.muted.sm", null, L("完成第一次申論練習後，這裡會顯示各主題的分數，最弱的排最上面。", "After your first practice, scores per topic appear here, weakest first.")))) : null;
    return el("div.ex", null, drop, todayCard, toolbar,
      el("div.ex-body", null, el("div", null, side, s.questions.length ? el("p.muted.sm.ex-stat", null, L(`已練習 ${practiced} / ${s.questions.length} 題`, `${practiced} / ${s.questions.length} practised`)) : null,
        s.questions.length ? seedBtn : null), main));
  };

  H.render = H.render || {};
  H.render.exam = function () {
    const root = document.getElementById("exam");
    if (!root) return;
    H.put(root, el("div.band-head", null, el("div", null, el("div.eyebrow", null, "03", el("span", null, "/"), H.t("exam")), el("h2", null, H.t("exam")), el("p.sub", null, H.t("exam_hint")))),
      el("div.panel", null, el("div.tab-panel", null, H.examView())));
  };

  /* ================= 3. podcast voice ================= */
  const para = (zh, en) => L(zh, en);
  H.storyScript = function () {
    const s = H.state, tp = s.topic || {};
    const lines = [tp.title ? para(`今天要談的研究題目是：${tp.title}。`, `Today's research topic: ${tp.title}.`) : "", tp.reason ? para("為什麼做這個題目？", "Why this topic? ") + tp.reason : "",
      ...H.FIVE_C.map((c) => (s.story.find((r) => r.key === c.key) || {}).sentence || ""), tp.benefit ? para("這個研究的幫助是：", "How it helps: ") + tp.benefit : ""];
    return lines.filter((x) => x && x.trim()).join("\n\n");
  };
  H.paperScript = function (p) {
    const who = `${(p.authors || "").split(";")[0].split(",")[0]}${p.year ? para(` ${p.year} 年`, ` ${p.year}`) : ""}`;
    return [para(`這一集導讀：${who} 的文章，${p.title}。`, `This episode: ${who}, ${p.title}.`),
      ...H.FIVE_C.map((c) => ((p["c_" + c.key] || "").trim() ? `${H.lang === "en" ? c.en : c.zh}。${p["c_" + c.key].trim()}` : "")), (p.notes || "").trim()].filter(Boolean).join("\n\n");
  };
  H.questionScript = function (q) {
    return [para("考題。", "Question. ") + q.text, q.analysis ? para("解析。", "Analysis. ") + q.analysis : "", q.outline ? para("答題架構。", "Outline. ") + q.outline : ""].filter(Boolean).join("\n\n");
  };
  const TONES = { steady: ["平穩講解", "Steady", 1, 1], lively: ["活潑輕快", "Lively", 1.15, 1.1], calm: ["沉穩低緩", "Calm", 0.85, 0.9], news: ["新聞播報", "Newsreader", 1.05, 1.2] };

  H.openVoice = async function (init = {}) {
    const saved = prefs("voice");
    const o = { tone: saved.tone || "steady", rate: saved.rate || 1, pitch: saved.pitch || 1, voice: saved.voice || "", sysVoice: saved.sysVoice || "" };
    const script = H.textarea(init.text || H.storyScript(), { rows: 12, placeholder: L("貼上或撰寫要朗讀的講稿…", "Paste or write the script…") });
    const titleIn = H.input(init.title || (H.state.topic || {}).title || "podcast", { placeholder: L("檔名", "File name") });
    const synth = window.speechSynthesis;
    const browserVoices = () => (synth ? synth.getVoices() : []).filter((v) => /^(zh|en|ja)/i.test(v.lang));
    const voiceSel = el("select.inp"), sysSel = el("select.inp");
    const fill = () => { H.put(voiceSel, [el("option", { value: "" }, L("瀏覽器預設", "Browser default")), ...browserVoices().map((v) => el("option", { value: v.name }, `${v.name} · ${v.lang}`))]); voiceSel.value = o.voice; };
    fill(); if (synth) synth.onvoiceschanged = fill;
    let sys = { engine: "", voices: [] };
    try { sys = await H.api("/api/tts/voices"); } catch (_) { /* optional */ }
    const preferred = sys.voices.filter((v) => /^(zh|cmn|yue|en)/i.test(v.lang));
    H.put(sysSel, [el("option", { value: "" }, L("系統預設", "System default")), ...(preferred.length ? preferred : sys.voices).map((v) => el("option", { value: v.name }, `${v.name} · ${v.lang}`))]);
    sysSel.value = o.sysVoice;
    const rate = el("input", { type: "range", min: 0.5, max: 2, step: 0.05, value: o.rate, "aria-label": L("速度", "Speed") });
    const pitch = el("input", { type: "range", min: 0.5, max: 2, step: 0.05, value: o.pitch, "aria-label": L("語調", "Pitch") });
    const rateOut = el("span.mono"), pitchOut = el("span.mono"), length = el("span.mono.muted.sm");
    const toneSeg = el("div.seg.small", { role: "radiogroup", "aria-label": L("語氣", "Tone") });
    const sync = () => {
      rateOut.textContent = Number(rate.value).toFixed(2) + "×"; pitchOut.textContent = Number(pitch.value).toFixed(2);
      const n = countWords(script.value);
      length.textContent = L(`${n} 字，約 ${Math.max(1, Math.round(n / (240 * rate.value)))} 分鐘`, `${n} words, about ${Math.max(1, Math.round(n / (150 * rate.value)))} min`);
      H.put(toneSeg, Object.keys(TONES).map((k) => el("button.seg-btn", { type: "button", role: "radio", "aria-checked": String(o.tone === k),
        onclick: () => { o.tone = k; rate.value = TONES[k][2]; pitch.value = TONES[k][3]; sync(); } }, TONES[k][H.lang === "en" ? 1 : 0])));
      prefs("voice", { tone: o.tone, rate: Number(rate.value), pitch: Number(pitch.value), voice: voiceSel.value, sysVoice: sysSel.value });
    };
    [rate, pitch, script, voiceSel, sysSel].forEach((n) => n.addEventListener("input", sync));
    sync();
    const stop = () => synth && synth.cancel();
    const play = () => {
      if (!synth) return H.toast(L("這個瀏覽器不支援試聽", "This browser cannot preview speech"), "error");
      stop();
      for (const chunk of script.value.split(/\n{2,}/).map((x) => x.trim()).filter(Boolean)) {
        const u = new SpeechSynthesisUtterance(chunk);
        const v = browserVoices().find((x) => x.name === voiceSel.value);
        if (v) { u.voice = v; u.lang = v.lang; } else u.lang = /[㐀-鿿]/.test(chunk) ? "zh-TW" : "en-US";
        u.rate = Number(rate.value); u.pitch = Number(pitch.value);
        synth.speak(u);
      }
    };
    const exportBtn = H.btn(L("匯出音檔（WAV）", "Export audio (WAV)"), { icon: "download", variant: "primary", disabled: !sys.engine, onclick: () => busy(exportBtn, async () => {
      const r = await H.api("/api/tts", { body: { text: script.value, voice: sysSel.value, rate: Number(rate.value), pitch: Number(pitch.value), filename: titleIn.value || "podcast" } });
      download(r.url); H.toast(L(`已匯出 ${H.size(r.size)}`, `Exported ${H.size(r.size)}`), "ok");
    }) });
    const sources = el("div.sl-chips", null,
      el("button.chip", { type: "button", onclick: () => { script.value = H.storyScript(); sync(); } }, L("我的研究故事 5C", "My 5C story")),
      ...H.state.papers.filter((p) => H.FIVE_C.some((c) => (p["c_" + c.key] || "").trim())).slice(0, 6).map((p) =>
        el("button.chip", { type: "button", title: p.title, onclick: () => { script.value = H.paperScript(p); titleIn.value = p.title.slice(0, 60); sync(); } }, L("文獻：", "Paper: ") + p.title.slice(0, 24))),
      ...H.state.questions.filter((q) => q.outline).slice(0, 4).map((q) =>
        el("button.chip", { type: "button", title: q.text, onclick: () => { script.value = H.questionScript(q); sync(); } }, L("考題：", "Q: ") + q.text.slice(0, 20))));
    const panel = H.openLayer("modal", L("語音 Podcast", "Voice podcast"), el("div.vo", null,
      el("p.hint", null, L("把研究故事、文獻筆記或考題解析變成可以聽的內容。試聽用瀏覽器語音；匯出用這台電腦內建的語音，不會上傳到任何服務。", "Turn your story, reading notes or exam analysis into audio. Preview uses the browser; export uses this computer's built-in voices — nothing is uploaded.")),
      el("span.lbl", null, L("講稿來源", "Script from")), sources,
      H.field(L("講稿", "Script"), script), length,
      el("div.form-grid", null,
        H.field(L("試聽聲音", "Preview voice"), voiceSel), H.field(L("匯出聲音", "Export voice"), sysSel, sys.engine ? null : L("找不到系統語音引擎（Linux 請安裝 espeak-ng）", "No system speech engine found (Linux: install espeak-ng)")),
        el("div.span2", null, el("span.lbl", null, L("語氣", "Tone")), toneSeg),
        el("label.vo-slider", null, el("span.lbl", null, L("速度 ", "Speed "), rateOut), rate), el("label.vo-slider", null, el("span.lbl", null, L("語調（音高） ", "Pitch "), pitchOut), pitch),
        el("div.span2", null, H.field(L("檔名", "File name"), titleIn)))),
    [H.btn(L("試聽", "Preview"), { icon: "play", variant: "outline", class: "left", onclick: play }), H.btn(L("停止", "Stop"), { variant: "ghost", class: "left", onclick: stop }),
      H.btn(L("關閉", "Close"), { variant: "ghost", onclick: () => { stop(); H.closeLayer(); } }), exportBtn], { wide: true });
    new MutationObserver((_, obs) => { if (!document.body.contains(panel)) { stop(); obs.disconnect(); } }).observe(document.getElementById("layer"), { childList: true });
  };

  /* ================= 4. Word thesis export ================= */
  H.openThesis = function () {
    const p = { font_zh: "標楷體", font_en: "Times New Roman", size: 12, line: 1.5, margin_top: 2.54, margin_bottom: 2.54, margin_left: 3, margin_right: 2.54, header: true, degree: "碩士論文", ...prefs("thesis") };
    const tp = H.state.topic || {};
    const f = {
      title: H.input(tp.title || H.state.settings.project_title || ""), title_en: H.input(tp.title_en || ""),
      school: H.input(p.school, { placeholder: L("例如 國立中興大學", "University") }), department: H.input(p.department, { placeholder: L("例如 企業管理學系", "Department") }),
      degree: H.select(p.degree, [["碩士論文", L("碩士論文", "Master's thesis")], ["博士論文", L("博士論文", "Doctoral dissertation")], ["研究計畫書", L("研究計畫書", "Research proposal")]]),
      advisor: H.input(p.advisor, { placeholder: L("王大明 博士", "Dr …") }), author: H.input(p.author), date: H.input(p.date, { placeholder: L("中華民國一百一十五年六月", "June 2027") }),
      font_zh: H.select(p.font_zh, [["標楷體", "標楷體"], ["新細明體", L("新細明體（明體）", "PMingLiU")], ["思源宋體", L("思源宋體（開源宋體）", "Source Han Serif")], ["Noto Serif TC", "Noto Serif TC"], ["微軟正黑體", "微軟正黑體"], ["思源黑體", "思源黑體"]]),
      font_en: H.select(p.font_en, [["Times New Roman", "Times New Roman"], ["Arial", "Arial"], ["Calibri", "Calibri"]]),
      size: H.select(String(p.size), [["12", "12 pt"], ["13", "13 pt"], ["14", "14 pt"]]), line: H.select(String(p.line), [["1.5", L("1.5 倍行高", "1.5 lines")], ["2", L("2 倍行高", "Double")], ["1.25", "1.25"], ["1", L("單行", "Single")]]),
      margin_top: H.input(p.margin_top, { type: "number", step: 0.01, min: 1, max: 5 }), margin_bottom: H.input(p.margin_bottom, { type: "number", step: 0.01, min: 1, max: 5 }),
      margin_left: H.input(p.margin_left, { type: "number", step: 0.01, min: 1, max: 5 }), margin_right: H.input(p.margin_right, { type: "number", step: 0.01, min: 1, max: 5 }),
    };
    const header = el("input", { type: "checkbox", checked: p.header !== false });
    const langSel = H.select(H.lang, [["zh", "繁體中文"], ["en", "English"]]);
    const go = H.btn(L("匯出 Word（.docx）", "Export Word (.docx)"), { icon: "download", variant: "primary", onclick: () => busy(go, async () => {
      const body = Object.fromEntries(Object.entries(f).map(([k, n]) => [k, n.value]));
      Object.assign(body, { header: header.checked, lang: langSel.value, filename: (f.title.value || "thesis").slice(0, 60) });
      const keep = { ...body }; delete keep.title; delete keep.title_en; delete keep.filename; prefs("thesis", keep);
      const r = await H.api("/api/export/docx", { body });
      download(r.url); H.toast(L("已匯出，開啟後請在目錄按右鍵「更新功能變數」", "Exported — in Word, right-click the contents and Update Field"), "ok");
    }) });
    H.openLayer("modal", L("匯出論文 Word 檔", "Export thesis to Word"), el("div", null,
      el("p.hint", null, L("依學位論文格式產生初稿：封面、誌謝、摘要、目錄／圖目錄／表目錄（頁碼 i, ii, iii）、第一章至第三章（頁碼 1, 2, 3）與 APA 參考文獻。內文樣式名稱為「論文設定0」，在 Word 修改這個樣式即可一次調整全文。",
        "Builds a thesis draft: cover, acknowledgements, abstract, contents and lists (pages i, ii, iii), chapters 1–3 (pages 1, 2, 3) and APA references. Body text uses the style “論文設定0”: change it once in Word to restyle everything.")),
      el("h3.mini", null, L("封面資料", "Cover")),
      el("div.form-grid", null, el("div.span2", null, H.field(L("論文題目", "Title"), f.title)), el("div.span2", null, H.field(L("英文題目", "English title"), f.title_en)),
        H.field(L("學校", "University"), f.school), H.field(L("系所", "Department"), f.department), H.field(L("論文類別", "Type"), f.degree), H.field(L("日期", "Date"), f.date),
        H.field(L("指導教授", "Advisor"), f.advisor), H.field(L("研究生", "Author"), f.author)),
      el("h3.mini", null, L("格式設定（樣式：論文設定0）", "Format (style: 論文設定0)")),
      el("div.form-grid", null, H.field(L("中文字型", "Chinese font"), f.font_zh), H.field(L("英數字型", "Latin font"), f.font_en), H.field(L("內文字級", "Body size"), f.size), H.field(L("行距", "Line spacing"), f.line),
        H.field(L("上邊界 (cm)", "Top margin (cm)"), f.margin_top), H.field(L("下邊界 (cm)", "Bottom margin (cm)"), f.margin_bottom),
        H.field(L("左邊界／裝訂邊 (cm)", "Left / binding margin (cm)"), f.margin_left), H.field(L("右邊界 (cm)", "Right margin (cm)"), f.margin_right),
        H.field(L("內容語言", "Language"), langSel), el("label.ci-prov", null, header, el("span", null, L("頁首顯示論文題目", "Show the title in the header")))),
      el("p.hint", null, L("頁碼：前置頁（誌謝～表目錄）為小寫羅馬數字，正文從第一章起為阿拉伯數字 1，皆置中於頁尾；封面不編頁碼。", "Page numbers: lower-case roman for front matter, arabic from chapter 1, centred in the footer; the cover is unnumbered."))),
    [H.btn(L("取消", "Cancel"), { variant: "ghost", onclick: H.closeLayer }), go], { wide: true });
  };
})();
