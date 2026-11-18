/* Research Hub — hypothesis grounding, after Sparrowe & Mayer (2011), "Publishing in AMJ — Part 4: Grounding
   hypotheses". The theory section is not a literature review: it explains WHY X relates to Y. Each path in the
   research model gets its theory, evidence and explanatory logic; the model as a whole gets positioning and
   coherence (why these variables, and only these), and a check on how several theories are used. */
(function () {
  const H = window.H;
  const { el } = H;
  const L = (zh, en) => (H.lang === "en" ? en : zh);

  const CITE = /[（(][^（()）]{0,60}?(?:19|20)\d{2}[a-z]?[）)]|(?:研究|學者|文獻)(?:發現|指出|認為|顯示)|et al\./g;
  const GENERIC = /社會交換|資源基礎|制度理論|代理理論|利害關係人理論|社會認同|計畫行為|期望理論|social exchange|resource[- ]based|institutional theory|agency theory|stakeholder theory|social identity|planned behavio/i;
  const varName = (v) => (v ? `${v.symbol} ${H.varName(v)}`.trim() : "?");
  const pathText = (s, r) => {
    const by = (id) => s.variables.find((v) => v.id === id);
    if (r.kind === "moderates") {
      const base = (s.relations || []).find((x) => x.id === r.moderates_id);
      return `${varName(by(r.source_id))} ${L("調節", "moderates")} ${base ? `${by(base.source_id)?.symbol || "?"} → ${by(base.target_id)?.symbol || "?"}` : varName(by(r.target_id))}`;
    }
    return `${varName(by(r.source_id))} → ${varName(by(r.target_id))}`;
  };

  /** Per-path findings and model-level findings. Pure. */
  H.groundingFindings = function (s) {
    const g = s.grounding || {};
    const rels = s.relations || [];
    const per = new Map();
    for (const r of rels) {
      const out = [];
      const add = (level, zh, en) => out.push({ level, text: L(zh, en) });
      const logic = (r.logic || "").trim(), theory = (r.theory || "").trim(), evidence = (r.evidence || "").trim();
      if (!logic) {
        if (theory || evidence) add("issue", "只有理論或實證，沒有解釋邏輯：讀者會問「為什麼？」", "Theory or evidence without explanatory logic: readers will ask “why?”");
        else add("issue", "還沒說明為什麼 X 會影響 Y（解釋邏輯是基礎）。", "No explanation yet of why X affects Y.");
      } else {
        const cites = (logic.match(CITE) || []).length;
        const sentences = logic.split(/[。！？.!?]\s*/).filter((x) => x.trim().length > 4).length || 1;
        if (cites >= 3 && cites / sentences >= 0.8) add("warn", "引證論證：幾乎每句都是「某研究發現」，請先寫自己的推論，再把文獻放回來。", "Citation stacking: nearly every sentence cites a study. Write your own argument first.");
        if (logic.replace(CITE, "").replace(/\s/g, "").length < 40) add("warn", "解釋太短：說明 X 透過什麼狀態或過程影響 Y。", "Too short: say through what state or process X affects Y.");
      }
      if (theory && GENERIC.test(theory) && logic.length < 120) add("warn", `「${theory}」偏一般，不足以單獨解釋這條路徑，請說明它對這兩個變項的具體推論（缺乏特異性）。`, `“${theory}” is general; spell out what it predicts for these variables (lack of specificity).`);
      if (!evidence) add("info", "可補上相似情境的實證，增加預測的可信度。", "Add evidence from similar settings.");
      if (!(r.alt || "").trim()) add("info", "想一想反向關係或虛無假設是否也合理，避免陳述顯而易見的事實。", "Consider whether the reverse or a null relation is also plausible.");
      const target = s.variables.find((v) => v.id === r.target_id), source = s.variables.find((v) => v.id === r.source_id);
      if ((source?.role === "med" || target?.role === "med") && !logic) add("issue", "中介路徑：要描述中間狀態或過程，並考慮如何操作化與檢驗。", "Mediated path: describe the intervening state and how it will be tested.");
      per.set(r.id, out);
    }

    const model = { position: [], logic: [], coherence: [], theories: [] };
    const add = (k, level, zh, en) => model[k].push({ level, text: L(zh, en) });
    if (!rels.length) add("logic", "info", "研究架構圖還沒有假設路徑：先到「研究架構圖」建立，或上傳文件讓系統推斷。", "No paths yet: build them in the research model or upload a document.");
    if (!(g.positioning || "").trim()) add("position", "info", "說明研究如何接續既有理論對話：補充、延伸，還是挑戰既有研究？", "Say how the study joins the conversation: extend, add to or challenge it.");
    const noLogic = rels.filter((r) => !(r.logic || "").trim()).length;
    if (rels.length && noLogic) add("logic", "issue", `${noLogic}／${rels.length} 條假設還沒寫解釋邏輯。`, `${noLogic}/${rels.length} hypotheses have no explanatory logic.`);
    const papers = new Set((s.variable_papers || []).map((l) => l.variable_id));
    const used = new Set(rels.flatMap((r) => [r.source_id, r.target_id]));
    const orphan = s.variables.filter((v) => used.has(v.id) && !papers.has(v.id));
    if (orphan.length) add("position", "warn", `忽略既有對話：${orphan.map((v) => v.symbol).join("、")} 沒有連結任何文獻（重要的文獻要自己看）。`, `Ignoring prior work: ${orphan.map((v) => v.symbol).join(", ")} link to no papers.`);

    // coherence: why these variables, and only these
    if (rels.length && !(g.why_these || "").trim()) add("coherence", "issue", "沒說明「為什麼是這些變項，而且只有這些」：沒講清楚就只是在做多變量作業。", "Not explained why these variables, and only these.");
    const rqVars = new Set((s.rq_variables || []).map((l) => l.variable_id));
    if (rqVars.size) {
      const off = [...used].filter((id) => !rqVars.has(id)).map((id) => s.variables.find((v) => v.id === id)?.symbol).filter(Boolean);
      if (off.length) add("coherence", "warn", `${off.join("、")} 出現在假設中，但沒有連到任何研究問題：所有假設要服務同一個核心研究問題。`, `${off.join(", ")} appear in hypotheses but in no research question.`);
    } else if (rels.length) add("coherence", "info", "研究問題還沒連結變數，無法檢查假設是否都服務同一個問題。", "Link variables to research questions to check that all hypotheses serve one question.");

    // several theories: integrate, don't collage
    const names = [...new Set(rels.map((r) => (r.theory || "").trim()).filter(Boolean))];
    if (names.length > 1 && !g.strategy) add("theories", "warn", `用了 ${names.length} 個理論（${names.slice(0, 4).join("、")}），但還沒說明怎麼使用：競爭、結合還是整合？`, `${names.length} theories, but no stated strategy.`);
    if (names.length > 1 && !(g.strategy_reason || "").trim()) add("theories", "warn", "每增加一個理論都要回答：為什麼研究問題需要它？它帶來什麼獨特貢獻？", "For each added theory: why does the question need it, and what does it add?");
    if (names.length >= Math.max(3, rels.filter((r) => r.kind === "effect").length) && names.length > 2)
      add("theories", "issue", "碎片化的理論：幾乎每條假設都用不同理論支撐，沒有整合成一致的敘事（Don't do that）。", "Fragmented theorizing: a different theory for nearly every hypothesis.");
    if (g.strategy === "combining") add("theories", "info", "理論結合的風險：只因兩個變項各自被證實重要，就放進同一模型。請說明它們的目的不同、但共同回答問題。", "Combining risks putting variables together only because each mattered elsewhere.");
    if (g.strategy === "competing") add("theories", "info", "競爭理論：說明讀者為何應該期待其中一種預測勝出。", "Competing theories: explain why one prediction should win.");
    const hasMed = s.variables.some((v) => v.role === "med" && used.has(v.id)), hasMod = s.variables.some((v) => v.role === "mod" && used.has(v.id));
    if (hasMed && hasMod && names.length < 2 && !(g.strategy_reason || "").trim()) add("theories", "info", "模型同時有中介與調節：常需要第二個理論解釋，請說明它為何不可或缺。", "Mediation and moderation together often need a second theory — explain why it is needed.");
    if (!(g.main_theory || "").trim() && rels.length) add("theories", "info", "盡量以一個理論為主：先寫下主要理論。", "Lead with one theory: name it.");
    if (!rels.some((r) => (r.context || "").trim()) && rels.length) add("logic", "info", "情境也要交代：假設適用於一般情況，還是特定產業、組織或國家文化？", "State the context the hypotheses apply to.");

    const issues = [...per.values()].flat().concat(Object.values(model).flat()).filter((x) => x.level !== "info").length;
    return { per, model, issues, theories: names };
  };

  const CHECK = [
    ["讀者是否知道我的研究如何接續既有理論對話？", "Do readers know how my study joins the theoretical conversation?", "position"],
    ["我是否清楚解釋 X 為什麼會影響 Y，而非只引用相關研究？", "Do I explain why X affects Y, not just cite studies?", "logic"],
    ["若提出中介機制，是否能清楚描述並考慮如何檢驗？", "If I propose a mediator, can I describe and test it?", "logic"],
    ["若使用多個理論，是否說明每個理論不可或缺的理由？", "If I use several theories, is each one indispensable?", "theories"],
    ["所有假設是否共同服務於同一個核心研究問題？", "Do all hypotheses serve one core research question?", "coherence"],
    ["我的假設是否只是顯而易見，還是能帶來新的理論洞見？", "Are my hypotheses obvious, or do they bring new insight?", "obvious"],
  ];
  const ICON = { issue: "alert", warn: "alert", info: "sparkle" };
  const list = (items) => items.length ? el("ul.dz-auto", null, items.map((x) => el("li." + (x.level === "info" ? "info" : "issue"), null, H.icon(ICON[x.level], 13), x.text)))
    : el("p.dz-clear", null, H.icon("check", 13), L("沒有發現問題", "Nothing found"));

  H.groundingView = function () {
    const s = H.state, g = s.grounding || {};
    if (!g.id) return el("p.empty", null, "…");
    const f = H.groundingFindings(s);
    const save = el("span.save-state.mono", { "aria-live": "polite" });
    const upd = (data) => H.ops([{ op: "update", entity: "grounding", id: g.id, data }]);
    const area = (field, ph, rows = 2) => H.autosave(H.textarea(g[field], { rows, placeholder: ph, dataset: { fkey: "gr-" + field } }), "grounding", g.id, field, save);
    const mainTheory = H.autosave(H.input(g.main_theory, { placeholder: L("例如：社會交換理論", "e.g. social exchange theory"), dataset: { fkey: "gr-main" } }), "grounding", g.id, "main_theory", save);

    const rels = [...(s.relations || [])].sort((a, b) => (a.kind === "moderates") - (b.kind === "moderates") || (a.label || "").localeCompare(b.label || "", undefined, { numeric: true }));
    const cards = rels.map((r) => {
      const field = (name, ph, rows) => {
        const n = rows ? H.textarea(r[name], { rows, placeholder: ph, dataset: { fkey: `gr-${name}-${r.id}` } }) : H.input(r[name], { placeholder: ph, dataset: { fkey: `gr-${name}-${r.id}` } });
        return H.autosave(n, "relation", r.id, name, save);
      };
      const items = f.per.get(r.id) || [];
      const bad = items.some((x) => x.level === "issue");
      H.ui.grOpen = H.ui.grOpen || {};
      const open = r.id in H.ui.grOpen ? H.ui.grOpen[r.id] : bad;  // keep what the user opened or closed across re-renders
      return el("details.gr-path" + (bad ? ".issue" : ""), { open: open || null, ontoggle: (e) => { H.ui.grOpen[r.id] = e.target.open; } },
        el("summary", null, el("strong.mono", null, r.label || "H"), el("span", null, pathText(s, r) + (r.sign ? ` (${r.sign})` : "")),
          el("span.pill" + (bad ? ".warn" : items.some((x) => x.level === "warn") ? ".warn" : ".approved"), null,
            bad ? L("缺解釋邏輯", "No logic") : items.some((x) => x.level === "warn") ? L("待改善", "Review") : L("完整", "Grounded"))),
        el("div.gr-flow", null,
          el("div.gr-step", null, el("span.lbl", null, L("方式一｜既有理論", "1 · Established theory")), field("theory", L("連結到哪個成熟理論的核心邏輯？", "Which established theory?"))),
          el("div.gr-step", null, el("span.lbl", null, L("方式二｜相似情境的實證", "2 · Evidence from similar settings")), field("evidence", L("類似關係在哪些情境出現過？（引用）", "Where has a similar relation appeared? (citations)"), 2)),
          el("div.gr-step.main", null, el("span.lbl", null, L("方式三｜解釋邏輯：X 如何透過中間狀態或過程影響 Y？", "3 · Explanatory logic: how does X affect Y through an intervening state or process?")),
            field("logic", L("用自己的話寫：X 發生了什麼 → 它如何影響個體、團隊或組織 → 為什麼這個過程會導向 Y。", "In your own words: what happens with X → how it affects people or units → why that leads to Y."), 4))),
        el("div.form-grid", null,
          H.field(L("適用情境", "Context"), field("context", L("一般情況，或特定產業、組織、國家文化？", "General, or a specific industry, organisation or culture?"))),
          H.field(L("反向關係或虛無假設也合理嗎？", "Is a reverse or null relation also plausible?"), field("alt", L("若也合理，這條假設就不是顯而易見的事實", "If so, the hypothesis is not merely obvious"), 2))),
        list(items));
    });

    const strategies = [["single", "以一個理論為主", "One main theory", "盡量以一個理論為主，其他理論只在必要時加入", "Lead with one theory"],
      ["competing", "競爭理論", "Competing theories", "讓不同理論提出競爭性預測，再以資料檢驗。風險：讀者不清楚為何其中一種應勝出", "Rival predictions tested with data"],
      ["combining", "理論結合", "Combining theories", "不同理論解釋同一現象的不同面向。風險：只因變項各自重要就放進同一模型", "Different facets of one phenomenon"],
      ["integrating", "整合理論", "Integrating theories", "說明兩個理論如何互補，甚至彼此需要對方才完整成立。要求：深入理解各理論的核心邏輯", "Theories that need each other"]];
    const stratRow = el("div.hk-choice", { role: "radiogroup", "aria-label": L("多理論策略", "Multiple theories") }, strategies.map(([v, zh, en, dzh, den]) =>
      el("button.hk-opt" + (g.strategy === v ? ".on" : ""), { type: "button", role: "radio", "aria-checked": String(g.strategy === v), dataset: { fkey: "gr-strategy-" + v },
        onclick: () => upd({ strategy: g.strategy === v ? "" : v }) }, el("strong", null, L(zh, en)), el("span", null, L(dzh, den)))));

    const checklist = el("ol.dz-qs", null, CHECK.map(([zh, en, area_], i) => {
      const n = i + 1, status = g[`c${n}_status`] || "";
      const auto = area_ === "obvious" ? [...f.per.values()].flat().filter((x) => /反向|顯而易見|reverse|obvious/.test(x.text)).slice(0, 1) : (f.model[area_] || []);
      return el("li.dz-q" + (status ? "." + status : ""), null,
        el("div.dz-q-head", null, el("span.dz-num.mono", null, String(n)), el("h4", null, L(zh, en)),
          el("div.seg.small.push", { role: "radiogroup" }, [["", L("未檢核", "Open")], ["ok", L("沒問題", "OK")], ["issue", L("需處理", "Needs work")]].map(([v, l]) =>
            el("button.seg-btn", { type: "button", role: "radio", "aria-checked": String(status === v), dataset: { fkey: `gr-c${n}-${v || "open"}` }, onclick: () => upd({ [`c${n}_status`]: v }) }, l)))),
        list(auto));
    }));

    return el("div.gr", null,
      el("div.toolbar.wrap", null, el("p.hint-line.grow", null, L("理論章節不是文獻回顧，而是用理論邏輯說明假設：為什麼 X 會與 Y 產生預期的關係（Sparrowe & Mayer, 2011）。讀者在讀到假設前，就應該理解這個預測為何合理、構念之間如何運作。", "The theory section is not a literature review: it explains why X should relate to Y (Sparrowe & Mayer, 2011).")),
        el("span.pill" + (f.issues ? ".warn" : ".approved"), null, f.issues ? L(`${f.issues} 項待處理`, `${f.issues} to resolve`) : L("未發現問題", "No issues"))),
      el("div.gr-three", null, [["1. Positioning 定位", "1. Positioning", "將假設放在相關研究脈絡中，說明與既有文獻的關係"], ["2. Explanatory logic 解釋邏輯", "2. Explanatory logic", "建立清楚且合乎邏輯的論證，解釋核心變項為何相關"], ["3. Coherence 一致性", "3. Coherence", "讓模型中的變數與假設彼此連結，形成一致的理論架構"]]
        .map(([zh, en, d]) => el("div.gr-three-i", null, el("strong", null, L(zh, en)), el("span", null, d)))),
      el("div.card", null, el("div.card-head", null, el("h4", null, L("定位：與既有研究對話", "Positioning: engaging prior research")), save),
        el("p.hint", null, L("避免兩個極端：只堆疊引用而沒有自己的邏輯，或只講自己的推論而漏掉重要研究。先把自己的論證寫清楚，再把相關研究放回來。", "Avoid both extremes: stacking citations without your own logic, or ignoring important prior work.")),
        area("positioning", L("我的研究如何補充、延伸或挑戰既有研究？", "How does the study extend, add to or challenge prior work?"), 3), list(f.model.position)),
      el("h3.mini", null, L("每條假設的論證（三種論證來源互相配合，解釋邏輯是基礎）", "Each hypothesis: theory, evidence and logic together — logic is the foundation")),
      rels.length ? el("div.gr-paths", null, cards) : el("p.empty", null, L("研究架構圖還沒有假設路徑。", "No paths in the research model yet.")),
      list(f.model.logic),
      el("div.card", null, el("div.card-head", null, el("h4", null, L("理論一致性：為什麼是這些變項，而且只有這些？", "Coherence: why these variables, and only these?"))),
        area("why_these", L("為什麼選這些變項？它們如何彼此連結？為什麼沒有納入其他看似相關的變項？", "Why these variables? How do they connect? Why not others?"), 3), list(f.model.coherence)),
      el("div.card", null, el("div.card-head", null, el("h4", null, L("使用多個理論：整合，而不是拼貼", "Several theories: integrate, don't collage")),
        f.theories.length ? el("span.mono.muted", null, f.theories.join("、")) : null),
        H.field(L("主要理論", "Main theory"), mainTheory), stratRow,
        area("strategy_reason", L("每增加一個理論都要回答：為什麼研究問題需要它？它帶來什麼獨特貢獻？", "For each added theory: why is it needed, and what does it add?"), 2), list(f.model.theories)),
      el("h3.mini", null, L("帶回自己的研究：假設建構檢核表", "Hypothesis checklist")), checklist,
      el("p.hint", null, L("核心提醒：合理（plausible）不等於有趣（interesting），更不必然代表有理論貢獻。", "Plausible is not the same as interesting, nor a theoretical contribution.")));
  };
})();
