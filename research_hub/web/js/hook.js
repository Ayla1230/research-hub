/* Research Hub — Introduction check, after Grant & Pollock (2011), "Publishing in AMJ — Part 3: Setting the hook":
   the three questions an introduction answers, how to problematize the field, the rewriting process, and the three
   most common pitfalls reviewers name. Checks run on the 5C story sentences plus the introduction draft. */
(function () {
  const H = window.H;
  const { el } = H;
  const L = (zh, en) => (H.lang === "en" ? en : zh);

  const GAP_ONLY = /首次|第一個研究|首篇|從未被(?:研究|探討)|尚未有(?:研究|文獻)|填補.{0,6}(?:缺口|空白|不足)|研究缺口|文獻缺口|first (?:study|to (?:examine|investigate))|never been (?:studied|examined)|fill(?:s|ing)? (?:the|this|a) gap|gap in the literature/gi;
  const PUZZLE = /矛盾|謎|悖論|衝突|不一致|分歧|為何|為什麼|如何|然而|卻|但是|puzzle|paradox|tension|contradict|inconsisten|why|how|yet\b|however/i;
  const ROADMAP = /本(?:研究|文|論文)(?:共分|分為|架構如下|結構如下|安排如下)|第[一二三四五六]章.{0,30}第[一二三四五六]章|the remainder of (?:this|the) (?:paper|article)|is (?:organized|structured) as follows|in section \d/i;
  const HYPE = /根本(?:改變|顛覆|性地改變)|顛覆|革命性|徹底改變|首創|全新(?:的)?理論|完全解決|劃時代|fundamental(?:ly)? (?:change|transform|alter)|revolutioni[sz]e|paradigm shift|groundbreaking|first ever|for the first time/gi;
  const THEORY = /([㐀-鿿]{2,10}?)(?:理論|觀點)(?![的之]?(?:貢獻|意涵|基礎|架構|視角上))|((?:[A-Z][a-z]+[ -]){0,3}[A-Z][a-z]+) (?:[Tt]heory|[Pp]erspective|[Vv]iew)/g;

  /* content words used to see whether the story keeps to one line */
  const words = (text) => {
    const out = new Set();
    for (const run of (text || "").match(/[㐀-鿿]+|[A-Za-z]{4,}/g) || []) {
      if (/[㐀-鿿]/.test(run)) for (let i = 0; i < run.length - 1; i++) out.add(run.slice(i, i + 2));
      else out.add(run.toLowerCase());
    }
    for (const w of ["本研究", "研究", "我們", "因為", "這個", "然而", "可以", "以及", "study", "research", "this", "that", "with", "from"]) out.delete(w);
    for (const w of [...out]) if (/^(?:本研|研究|究的|的研|我們|因為|這個|然而|可以|以及|進行|透過|提供|相關|探討|影響|重要|問題|過去)$/.test(w)) out.delete(w);
    return out;
  };
  const overlap = (a, b) => { let n = 0; for (const w of a) if (b.has(w)) n++; return n; };
  const uniq = (list) => [...new Set(list.map((x) => x.trim()).filter(Boolean))];

  /** Pure analysis. Returns { pitfalls: {motivate, focus, overpromise}: [{level, text}], abstract: [{key, ok}], counts } */
  H.hookFindings = function (s) {
    const hk = s.hook || {};
    const story = Object.fromEntries((s.story || []).map((r) => [r.key, (r.sentence || "").trim()]));
    const intro = (hk.intro || "").trim();
    const all = [intro, ...Object.values(story)].join("\n");
    const f = { motivate: [], focus: [], overpromise: [] };
    const add = (k, level, zh, en) => f[k].push({ level, text: L(zh, en) });

    // Pitfall 1 — failing to motivate and problematize (≈60%)
    if (!story.concern && !/重要|關鍵|值得|matters?|important|crucial/i.test(intro)) add("motivate", "issue", "沒有說明為什麼重要（So what?）：5C 的「重要性」還是空的。", "No “so what”: the Concern sentence is empty.");
    const gap = uniq(all.match(GAP_ONLY) || []);
    if (gap.length) add("motivate", "issue", `只以「${gap.slice(0, 3).join("、")}」作為研究價值：存在缺口不代表值得研究，請改說明它解決了什麼問題、謎題或矛盾。`,
      `Value rests on “${gap.slice(0, 3).join(", ")}”: a gap alone is not a reason. Frame a question, puzzle or paradox instead.`);
    const tension = story.complication || intro;
    if (tension && !PUZZLE.test(tension)) add("motivate", "warn", "問題張力沒有寫出疑問、謎題或矛盾（例如「然而…卻…」「為何…」）。", "The complication states no question, puzzle or paradox.");
    if (!story.complication && !intro) add("motivate", "issue", "還沒寫「問題張力」：既有研究知道什麼、還不知道什麼？", "No complication yet: what do we know, and what don't we know?");
    if (!story.contribution) add("motivate", "issue", "沒有預告貢獻（What will we learn?）。", "No preview of the contribution (What will we learn?).");
    if (!hk.problematize) add("motivate", "info", "還沒選擇問題化策略（不完整性／不足性／不相容性）。", "Choose how you problematize the field.");
    else if (hk.problematize === "incompleteness") add("motivate", "warn", "不完整性：容易讓貢獻顯得微小或顯而易見，請說明補上這塊會改變什麼理解。", "Incompleteness risks an incremental or obvious contribution.");
    else if (hk.problematize === "incommensurability") add("motivate", "warn", "不相容性：全盤否定前人研究容易引起爭論與反彈，請承認既有成果。", "Incommensurability risks controversy and backlash.");

    // Pitfall 2 — lack of focus (≈45%)
    if (!(hk.origin || "").trim()) add("focus", "info", "先寫下研究初衷：整篇緒論都要回到這句話，故事線才不會偏。", "Write down why you started this study; every paragraph should serve it.");
    const len = (intro.match(/[㐀-鿿]/g) || []).length + (intro.match(/[A-Za-z]+/g) || []).length;
    if (len > 2500) add("focus", "warn", `緒論草稿約 ${len} 字，偏長：背景、文獻與方法細節移到後面章節。`, `The draft is about ${len} words — move background, literature and method detail to later sections.`);
    const theoryName = (m) => (m[1] ? m[1].split(/採用|運用|結合|根據|基於|透過|藉由|從|以|與|和|及|、|，|的|之/).pop() + "理論" : m[2]);
    const theories = uniq([...all.matchAll(THEORY)].map(theoryName)).filter((t) => t.length >= 4 && !/^(?:本|此|該|這|相關|既有|過去|現有|主要|不同|其他|管理|研究)/.test(t));
    if (theories.length > 2) add("focus", "warn", `用了 ${theories.length} 個理論（${theories.slice(0, 4).join("、")}）：請說明彼此關係，或聚焦一個主要的理論視角。`,
      `${theories.length} theories (${theories.slice(0, 4).join(", ")}): explain how they relate, or lead with one lens.`);
    if (ROADMAP.test(intro)) add("focus", "warn", "緒論在交代章節安排：應建立研究論證，而不是說明後續章節包含哪些內容。", "The introduction lists the chapters instead of building the argument.");
    if (story.complication && story.course) {
      const problem = words(story.complication + story.concern), answer = words(story.course + story.contribution);
      if (problem.size >= 4 && answer.size >= 4 && overlap(problem, answer) === 0)
        add("focus", "warn", "故事線不連貫：「解決路徑」與「貢獻」沒有回應「問題張力」提到的內容。", "The course and contribution do not answer the complication — the story line breaks.");
    }
    const filled = ["common", "complication", "concern", "course", "contribution"].filter((k) => story[k]).length;
    if (filled && filled < 5) add("focus", "info", `5C 只完成 ${filled}／5 句，故事還不完整。`, `Only ${filled}/5 story sentences are written.`);

    // Pitfall 3 — overpromising (≈14%)
    const hype = uniq((story.contribution + "\n" + story.course + "\n" + intro).match(HYPE) || []);
    if (hype.length) add("overpromise", "warn", `「${hype.slice(0, 3).join("、")}」：貢獻要是研究真正能支持的，避免誇大。`, `“${hype.slice(0, 3).join(", ")}”: claim only what the study can support.`);
    const d = s.design || {};
    if (/因果|造成|導致|causal|causes?/i.test(story.contribution + story.course) && d.design === "cross_sectional")
      add("overpromise", "issue", "貢獻提到因果，但研究設計是橫斷面：結果無法支持這樣的主張。", "The contribution claims causality but the design is cross-sectional.");
    if (story.contribution && !story.course) add("overpromise", "warn", "有寫貢獻但沒寫研究實際怎麼做（解決路徑），讀者無法判斷貢獻是否可信。", "A contribution without a course of action cannot be judged.");

    // the introduction as a mini-abstract: five elements
    const has = (re) => re.test(all);
    const abstract = [
      ["position", !!story.common || has(/近年|隨著|趨勢|文獻|研究指出|in recent years|literature/i)],
      ["question", (s.rqs || []).length > 0 || has(/研究問題|探討|是否|如何|為何|question|whether|how|why/i)],
      ["lens", has(/理論|觀點|視角|theory|perspective|lens/i)],
      ["method", has(/問卷|訪談|實驗|資料|樣本|個案|為例|panel|survey|interview|experiment|data|sample|case/i) || !!d.design],
      ["contribution", !!story.contribution || has(/貢獻|有助於|啟示|contribut|implication/i)],
    ].map(([key, ok]) => ({ key, ok }));
    const issues = Object.values(f).flat().filter((x) => x.level !== "info").length;
    return { pitfalls: f, abstract, issues, theories, length: len };
  };

  const ABSTRACT = { position: ["研究定位", "Positioning", "將研究問題放入相關文獻，或說明現象的重要性", "Place the question in the literature or show why the phenomenon matters"],
    question: ["研究問題", "Question", "清楚、簡潔地提出研究究竟要回答什麼", "State clearly what the study answers"],
    lens: ["理論視角", "Theoretical lens", "概述採用的主要理論觀點", "Name the main theoretical lens"],
    method: ["方法與情境", "Method and context", "簡述研究方法及實證情境", "Sketch the method and empirical setting"],
    contribution: ["理論貢獻", "Contribution", "預告研究將如何推進既有知識", "Preview how the study advances knowledge"] };
  const PIT = { motivate: ["Pitfall 1｜未能激發動機與問題化", "Pitfall 1 · Failing to motivate and problematize", "60%"],
    focus: ["Pitfall 2｜缺乏焦點", "Pitfall 2 · Lack of focus", "45%"], overpromise: ["Pitfall 3｜過度承諾", "Pitfall 3 · Overpromising", "14%"] };
  const ICON = { issue: "alert", warn: "alert", info: "sparkle" };

  H.hookView = function () {
    const s = H.state, hk = s.hook || {};
    if (!hk.id) return el("p.empty", null, "…");
    const upd = (data) => H.ops([{ op: "update", entity: "hook", id: hk.id, data }]);
    const f = H.hookFindings(s);
    const save = el("span.save-state.mono", { "aria-live": "polite" });
    const story = Object.fromEntries((s.story || []).map((r) => [r.key, (r.sentence || "").trim()]));
    const choice = (field, options, label) => el("div.hk-choice", { role: "radiogroup", "aria-label": label }, options.map(([v, zh, en, dzh, den, risk]) =>
      el("button.hk-opt" + (hk[field] === v ? ".on" : "") + (risk ? "." + risk : ""), { type: "button", role: "radio", "aria-checked": String(hk[field] === v), dataset: { fkey: `hk-${field}-${v}` },
        onclick: () => upd({ [field]: hk[field] === v ? "" : v }) }, el("strong", null, L(zh, en)), el("span", null, L(dzh, den)))));

    const origin = H.autosave(H.textarea(hk.origin, { rows: 2, placeholder: L("我為什麼想做這個研究？想回答誰的什麼問題？（寫完就不要忘記）", "Why did you start this study? Whose question do you want to answer?"), dataset: { fkey: "hk-origin" } }), "hook", hk.id, "origin", save);
    const intro = H.autosave(H.textarea(hk.intro, { rows: 10, placeholder: L("在這裡貼上或撰寫緒論草稿，系統會依審稿人最常指出的三種錯誤檢查。", "Paste or write your introduction draft; it is checked against the three pitfalls reviewers name most."), dataset: { fkey: "hk-intro" } }), "hook", hk.id, "intro", save);
    const newVersion = H.btn(L("存成新版本", "Save as a new version"), { icon: "check", small: true, variant: "outline", onclick: async () => {
      await H.ops([{ op: "update", entity: "hook", id: hk.id, data: { versions: (hk.versions || 0) + 1, intro: intro.value } }], true);
      H.toast(L(`第 ${(hk.versions || 0) + 1} 版`, `Version ${(hk.versions || 0) + 1}`), "ok");
    } });

    const q3 = [
      ["Who cares?", "研究主題是什麼？為何在理論與實務上重要？", "What is the topic and why does it matter in theory and practice?", ["common", "concern"]],
      ["What do we know / don't we know / so what?", "既有研究已知什麼、尚未解決什麼？為何這些未知值得關注？", "What is known, what is not, and why does it matter?", ["complication", "concern"]],
      ["What will we learn?", "本研究將如何改變、挑戰或推進學界對現象的理解？", "How will the study change, challenge or advance understanding?", ["course", "contribution"]],
    ];
    const C = Object.fromEntries((H.FIVE_C || []).map((c) => [c.key, c]));
    const questions = el("ol.hk-q3", null, q3.map(([en, zh, enq, keys], i) => el("li", null,
      el("div.hk-q3-head", null, el("span.dz-num.mono", null, String(i + 1)), el("div", null, el("strong", null, en), el("p", null, L(zh, enq)))),
      el("div.hk-q3-c", null, keys.map((k) => el("div.hk-c" + (story[k] ? "" : ".empty"), null,
        el("span.lbl", null, C[k] ? (H.lang === "en" ? C[k].en : C[k].zh) : k), el("p", null, story[k] || L("（尚未填寫，到「研究故事 5C」填寫）", "(empty — fill it in the 5C story)"))))))));

    const pitfalls = el("div.hk-pits", null, Object.entries(PIT).map(([k, [zh, en, pct]]) => {
      const items = f.pitfalls[k];
      return el("div.card.hk-pit" + (items.some((x) => x.level === "issue") ? ".issue" : items.some((x) => x.level === "warn") ? ".warn" : ".ok"), null,
        el("div.card-head", null, el("h4", null, L(zh, en)), el("span.mono.muted", null, L(`審稿人指出比例 ${pct}`, `${pct} of reviews`))),
        items.length ? el("ul.dz-auto", null, items.map((x) => el("li." + (x.level === "issue" ? "issue" : x.level === "warn" ? "issue" : "info"), null, H.icon(ICON[x.level], 13), x.text)))
          : el("p.dz-clear", null, H.icon("check", 13), L("沒有發現這類問題", "Nothing found")));
    }));

    const mini = el("div.hk-mini", null, f.abstract.map(({ key, ok }) => el("div.hk-mini-i" + (ok ? ".ok" : ""), { title: L(ABSTRACT[key][2], ABSTRACT[key][3]) },
      H.icon(ok ? "check" : "alert", 13), el("span", null, L(ABSTRACT[key][0], ABSTRACT[key][1])))));

    return el("div.hk", null,
      el("div.toolbar.wrap", null, el("p.hint-line.grow", null, L("緒論是論文的第一印象：讀者看完緒論，才決定要不要讀後面 90% 的內容（Grant & Pollock, 2011）。這裡依你的 5C 故事與緒論草稿檢查。", "The introduction is the first impression that decides whether readers continue (Grant & Pollock, 2011). Checked against your 5C story and draft.")),
        el("span.pill" + (f.issues ? ".warn" : ".approved"), null, f.issues ? L(`${f.issues} 項待處理`, `${f.issues} to resolve`) : L("未發現問題", "No issues"))),
      el("div.card", null, el("div.card-head", null, el("h4", null, L("研究初衷", "Why you started")), save), el("p.hint", null, L("老師提醒：初衷是什麼？要記住。故事線要連貫，承諾的貢獻不要超過研究能做到的。", "Remember why you started: keep one story line and promise only what the study can deliver.")), origin),
      el("h3.mini", null, L("緒論要回答的三個問題", "Three questions an introduction answers")), questions,
      el("h3.mini", null, L("審稿人最常指出的三種錯誤", "The three pitfalls reviewers name most")), pitfalls,
      el("div.hk-two", null,
        el("div.card", null, el("div.card-head", null, el("h4", null, L("開場方式（Who cares?）", "Opening (Who cares?)"))),
          choice("hook_type", [["trend", "趨勢 The trend", "The trend", "社會或職場的近期變化（Main Street），或學術文獻的趨勢與矛盾（Ivory Tower）", "A recent change in practice, or a trend and contradiction in the literature"],
            ["quote", "引用 The quote", "The quote", "以引人注目的標題、報導或故事開場，凸顯主題的趣味與實用性", "Open with a striking headline, report or story"]], L("開場", "Opening"))),
        el("div.card", null, el("div.card-head", null, el("h4", null, L("預告貢獻（What will we learn?）", "Contribution (What will we learn?)"))),
          choice("contribution_type", [["shifting", "改變共識", "Consensus shifting", "指出被廣泛接受的假設，挑戰它，並說明對後續研究的影響", "Challenge a widely held assumption"],
            ["creation", "建立共識", "Consensus creation", "文獻意見分歧時，釐清爭論的界線或解決分歧", "Resolve a disagreement in the literature"]], L("貢獻", "Contribution")))),
      el("div.card", null, el("div.card-head", null, el("h4", null, L("建立與問題化文獻（Locke & Golden-Biddle, 1997）", "Establishing and problematizing the field")), el("span.mono.muted", null, "intertextual field")),
        el("span.lbl", null, L("建立文獻場域", "Establishing the field")),
        choice("establish", [["synthesized", "綜合一致性", "Synthesized coherence", "連結兩個原本分開的學術議題", "Connect two separate streams"],
          ["progressive", "漸進式一致性", "Progressive coherence", "說明目前的議題可以如何繼續發展", "Show how a conversation can move forward"],
          ["noncoherence", "非一致性", "Noncoherence", "呈現兩個對立觀點，並說明如何解決", "Present opposing views and how to resolve them"]], L("建立", "Establishing")),
        el("span.lbl", null, L("問題化策略", "Problematizing")),
        choice("problematize", [["incompleteness", "不完整性", "Incompleteness", "既有研究仍有未充分探討之處。風險：貢獻顯得微小或顯而易見", "Not fully explored. Risk: incremental or obvious", "risk"],
          ["inadequacy", "不足性（建議）", "Inadequacy (recommended)", "既有研究忽略重要觀點，解釋仍不充分。承認既有成果，又說明為何需要重新檢視", "Overlooked perspective; respects prior work", "best"],
          ["incommensurability", "不相容性", "Incommensurability", "既有研究的核心理解根本錯誤。風險：容易招致爭論與反彈", "Fundamentally wrong. Risk: controversy", "risk"]], L("問題化", "Problematizing"))),
      el("div.card", null, el("div.card-head", null, el("h4", null, L("緒論草稿", "Introduction draft")), el("span.mono.muted", null, L(`第 ${hk.versions || 0} 版 · 約 ${f.length} 字`, `v${hk.versions || 0} · about ${f.length} words`))),
        el("div.hk-mini-wrap", null, el("span.lbl", null, L("優秀緒論是獨立的微型摘要：", "A good introduction is a stand-alone mini-abstract:")), mini),
        intro,
        el("div.toolbar.wrap", null, newVersion, el("span.muted.sm", null, L("AMJ 最佳論文得主平均重寫緒論約 10 次，並把約 24% 的寫作時間花在緒論。", "AMJ best-paper authors rewrote the introduction about 10 times and spent about 24% of their writing time on it.")))),
      el("div.card", null, el("div.card-head", null, el("h4", null, L("重寫方法", "How to rewrite"))),
        choice("rewrite", [["ruthless", "無情式重寫", "Ruthless rewriting", "多位作者互相刪改、挑戰彼此的內容，但高度信任", "Co-authors cut each other's text, with trust"],
          ["iterative", "反覆式演進", "Iterative enactment", "反覆重寫，直到研究問題、缺口與貢獻的關係逐漸清晰；質性研究常見", "Rewrite until question, gap and contribution align"],
          ["map", "依圖前進", "Following a map", "釐清新穎性與重要性 → 找出缺口 → 列出理論貢獻與情境獨特性 → 反覆重寫", "Novelty and importance → gap → contribution and context → rewrite"]], L("重寫", "Rewriting"))));
  };
})();
