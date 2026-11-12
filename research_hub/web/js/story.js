/* Research Hub — the 5C research story (Lange & Pfarrer, 2017: "Sense and structure — the core
   building blocks of an AMR article") and 5C reading notes for every paper. */
(function () {
  const H = window.H;
  const { el, t } = H;

  /* The five core building blocks, with the guiding questions used in class. */
  H.FIVE_C = [
    { key: "common", mark: "⊙", zh: "共同基礎", en: "Common ground", starterZh: "我們已知……", starterEn: "We know that…",
      qZh: "文獻已形成哪些理解？", qEn: "What does the literature already understand?",
      promptsZh: ["學術對話：主要文獻正在討論什麼？", "假設與邊界：哪些前提支撐既有解釋？", "準確綜整：把研究連成讀者能理解的起點", "引導讀者，不要讓讀者疏離（orient, don't alienate）"],
      promptsEn: ["Academic conversation: what are the key works discussing?", "Assumptions and boundaries behind current explanations", "Accurate synthesis: a starting point readers can follow", "Orient, don't alienate, the reader"],
      paperZh: "這篇建立在哪些既有理解上？", paperEn: "What shared understanding does it build on?" },
    { key: "complication", mark: "◇", zh: "問題張力", en: "Complication", starterZh: "然而……", starterEn: "Yet…",
      qZh: "哪個解釋仍不充分？", qEn: "Which explanation is still inadequate?",
      promptsZh: ["問題 Problem：既有解釋不充分", "謎題 Puzzle：理論預期與觀察出現矛盾", "轉折 Twist：原本接受的假設需要重看", "權衡新穎與可理解：太漸進顯得瑣碎，太激進難以接受，有根據的挑戰最好"],
      promptsEn: ["Problem: an inadequate explanation", "Puzzle: theory and observation disagree", "Twist: an accepted assumption to reconsider", "Balance novelty and incrementalism: a grounded challenge works best"],
      paperZh: "它指出哪個解釋不充分？", paperEn: "Which explanation does it find inadequate?" },
    { key: "concern", mark: "!", zh: "重要性", en: "Concern", starterZh: "這很重要，因為……", starterEn: "This matters because…",
      qZh: "這會造成什麼理論或實務後果？", qEn: "What are the theoretical or practical consequences?",
      promptsZh: ["只指出文獻缺口（某事尚未被研究）不足以構成研究動機", "理論後果：這些限制如何妨礙我們理解組織與管理？", "實務後果：沿用既有理解可能產生哪些錯誤判斷？"],
      promptsEn: ["Pointing out an unstudied gap is not enough to motivate a study", "Theoretical consequence: how do the limits hinder understanding?", "Practical consequence: what wrong decisions could follow?"],
      paperZh: "它為什麼重要？", paperEn: "Why does it matter?" },
    { key: "course", mark: "↗", zh: "解決路徑", en: "Course of action", starterZh: "本研究發展……", starterEn: "We develop…",
      qZh: "你將進行什麼理論工作？", qEn: "What theoretical work will you do?",
      promptsZh: ["構念：闡明新構念及其意義", "關係：建立構念之間的關係", "過程或類型：解釋理論過程，或發展類型學", "挑戰或綜整：挑戰主導理論，或綜整理論觀點"],
      promptsEn: ["Constructs: clarify new constructs and their meaning", "Relationships between constructs", "Process or typology", "Challenge a dominant theory, or synthesise perspectives"],
      paperZh: "它做了什麼理論或實證工作？", paperEn: "What theoretical or empirical work does it do?" },
    { key: "contribution", mark: "✦", zh: "貢獻", en: "Contribution", starterZh: "這改變了……", starterEn: "This changes…",
      qZh: "我們將如何重新理解原有問題？", qEn: "How will we understand the problem differently?",
      promptsZh: ["重新詮釋：既有理論的哪些觀點需要修正？", "研究走向：後續理論與實證可以提出什麼新問題？", "實務洞見：對組織與管理的理解有何啟示？"],
      promptsEn: ["Reinterpretation: which views need revising?", "Research trajectory: what new questions open up?", "Practical insight for organisations and management"],
      paperZh: "它改變了哪些理解？", paperEn: "What understanding does it change?" },
  ];
  const L = (c, f) => c[f + (H.lang === "en" ? "En" : "Zh")];
  const label = (c) => (H.lang === "en" ? c.en : `${c.zh} ${c.en}`);
  const storyRow = (key) => (H.state.story || []).find((r) => r.key === key) || { key, sentence: "", notes: "" };
  const countOf = (text) => {
    const cjk = (text.match(/[㐀-鿿]/g) || []).length;
    const words = (text.replace(/[㐀-鿿]/g, " ").match(/[A-Za-z0-9'’-]+/g) || []).length;
    return { cjk, words };
  };

  /* Papers attached to one C of my story (via the paper's story_role). */
  function pickPapers(c) {
    const papers = H.state.papers;
    const before = new Set(papers.filter((p) => p.story_role === c.key).map((p) => p.id));
    const chosen = new Set(before);
    const list = el("ul.pick-list");
    const search = H.input("", { type: "search", placeholder: t("filter_ph"), "aria-label": t("filter_ph") });
    const draw = () => {
      const q = search.value.trim().toLowerCase();
      H.put(list, papers.filter((p) => !q || `${p.title} ${p.authors}`.toLowerCase().includes(q)).map((p) => {
        const other = p.story_role && p.story_role !== c.key ? H.FIVE_C.find((x) => x.key === p.story_role) : null;
        const box = el("input", { type: "checkbox", checked: chosen.has(p.id), onchange: () => { box.checked ? chosen.add(p.id) : chosen.delete(p.id); } });
        return el("li.pick" + (chosen.has(p.id) ? ".on" : ""), null, el("label.check", null, box, el("span.box", null, H.icon("check", 12))),
          el("span.pick-label", { onclick: () => box.click() }, `${p.title}${p.year ? ` (${p.year})` : ""}`),
          other ? el("span.pill.tiny", { title: t("st_moves") }, other.mark + " " + (H.lang === "en" ? other.en : other.zh)) : null);
      }));
    };
    search.addEventListener("input", draw);
    draw();
    H.openLayer("modal", `${c.mark} ${label(c)} · ${t("st_papers")}`, el("div.picker", null, el("p.hint", null, t("st_pick_hint")), search, list), [
      H.btn(t("cancel"), { variant: "ghost", onclick: H.closeLayer }),
      H.btn(t("save"), { variant: "primary", onclick: async () => {
        const ops = [];
        for (const id of chosen) if (!before.has(id)) ops.push({ op: "update", entity: "paper", id, data: { story_role: c.key } });
        for (const id of before) if (!chosen.has(id)) ops.push({ op: "update", entity: "paper", id, data: { story_role: "" } });
        if (ops.length) await H.ops(ops);
        H.closeLayer();
      } })], { wide: true });
  }

  /* ---------- the story board ---------- */
  H.storyView = function () {
    const filled = H.FIVE_C.filter((c) => storyRow(c.key).sentence.trim()).length;
    const flow = el("ol.c5-flow", { "aria-label": t("st_title") }, H.FIVE_C.map((c, i) => {
      const done = !!storyRow(c.key).sentence.trim();
      return el("li.c5-step" + (done ? ".done" : ""), null,
        el("button.c5-dot", { type: "button", "aria-label": label(c), onclick: () => document.getElementById("c5-" + c.key)?.focus() }, done ? H.icon("check", 14) : c.mark),
        el("span.c5-name", null, H.lang === "en" ? c.en : c.zh), el("span.c5-q", null, L(c, "q")),
        i < 4 ? el("span.c5-arrow", { "aria-hidden": "true" }, "→") : null);
    }));
    const rows = H.FIVE_C.map((c, i) => {
      const row = storyRow(c.key);
      const save = el("span.save-state.mono", { "aria-live": "polite" });
      const sentence = H.textarea(row.sentence, { rows: 2, id: "c5-" + c.key, placeholder: L(c, "starter"), "aria-label": label(c) });
      if (row.id) H.autosave(sentence, "story", row.id, "sentence", save);
      const notes = H.textarea(row.notes, { rows: 4, placeholder: t("st_notes_ph"), "aria-label": t("notes") });
      if (row.id) H.autosave(notes, "story", row.id, "notes", save);
      const papers = H.state.papers.filter((p) => p.story_role === c.key);
      return el("article.c5-card", null,
        el("div.c5-side", null, el("span.c5-num.mono", null, String(i + 1).padStart(2, "0")), el("span.c5-mark", { "aria-hidden": "true" }, c.mark),
          el("h4", null, H.lang === "en" ? c.en : c.zh), H.lang === "en" ? null : el("span.c5-en.mono", null, c.en),
          el("span.c5-starter.mono", null, H.lang === "en" ? c.starterEn : `${c.starterEn} ${c.starterZh}`)),
        el("div.c5-main", null,
          el("div.c5-qrow", null, el("strong", null, L(c, "q")), save),
          sentence,
          el("details.c5-more", null, el("summary", null, t("st_prompts")),
            el("ul.c5-prompts", null, L(c, "prompts").map((p) => el("li", null, p))), notes),
          el("div.c5-papers", null, el("span.lbl", null, `${t("st_papers")} · ${papers.length}`),
            el("div.chips", null, papers.map((p) => el("button.chip.paper", { type: "button", title: p.title, onclick: () => H.editPaper(p) },
              H.icon("file", 13), el("span", null, `${(p.authors || p.title).split(/[;,]/)[0]}${p.year ? " " + p.year : ""}`))),
            H.btn(t("st_link"), { icon: "link", small: true, variant: "ghost", onclick: () => pickPapers(c) })))));
    });
    const sentences = H.FIVE_C.map((c) => storyRow(c.key).sentence.trim()).filter(Boolean);
    const pitch = sentences.join(H.lang === "en" || !/[㐀-鿿]/.test(sentences.join("")) ? " " : "");
    const n = countOf(pitch);
    const guide = [["st_g_abstract", "≈ 200 words"], ["st_g_intro", "3–4 pages"], ["st_g_second", "5–7 pages"], ["st_g_body", "10–15 pages"], ["st_g_discussion", "3–5 pages"]];
    return el("div.c5", null,
      H.topicView ? H.topicView() : null,
      el("div.toolbar.wrap", null, el("p.hint-line.grow", null, t("st_hint")),
        el("span.pill" + (filled === 5 ? ".approved" : ""), null, t("st_filled", { n: filled }))),
      flow,
      el("div.c5-cards", null, rows),
      el("div.c5-bottom", null,
        el("div.card", null, el("div.card-head", null, el("h4", null, t("st_pitch")),
          el("span.mono.muted", null, n.cjk > n.words ? t("st_chars", { n: n.cjk + n.words }) : t("st_words", { n: n.words }))),
          pitch ? el("p.c5-pitch", null, pitch) : el("p.empty.sm", null, t("st_pitch_empty")),
          el("p.hint", null, t("st_abstract_hint")),
          el("div.toolbar", null, H.btn(t("copy"), { icon: "copy", small: true, variant: "outline", disabled: !pitch, onclick: () => H.copy(pitch) }),
            H.btn(t("sl_hero"), { icon: "layers", small: true, variant: "ghost", onclick: () => H.openSlides() }))),
        el("div.card", null, el("div.card-head", null, el("h4", null, t("st_guide")), el("span.mono.muted", null, "Lange & Pfarrer, 2017")),
          el("table.c5-guide", null, el("tbody", null, guide.map(([k, len]) => el("tr", null, el("th", { scope: "row" }, t(k + "_name")), el("td.mono", null, len), el("td", null, t(k)))))),
          el("p.hint", null, t("st_guide_note")))));
  };

  /* ---------- 5C reading notes ---------- */
  H.paperFiveCFields = () => [
    ["story_role", "select", { label: "st_role", options: [["", t("none")], ...H.FIVE_C.map((c) => [c.key, `${c.mark} ${H.lang === "en" ? c.en : c.zh}`])] }],
    ["complication_type", "select", { label: "st_ctype", options: [["", "—"], ["problem", t("st_problem")], ["puzzle", t("st_puzzle")], ["twist", t("st_twist")]] }],
    ...H.FIVE_C.map((c) => ["c_" + c.key, "text", { label: "c5_" + c.key, wide: true, rows: 2, hint: L(c, "paper") }]),
  ];
  H.fiveCDots = function (p) {
    const n = H.FIVE_C.filter((c) => (p["c_" + c.key] || "").trim()).length;
    return el("span.c5-dots", { title: t("st_notes_done", { n }), "aria-label": t("st_notes_done", { n }) },
      H.FIVE_C.map((c) => el("i" + ((p["c_" + c.key] || "").trim() ? ".on" : ""), null)));
  };

  /* Compare the 5C notes of several papers side by side. */
  H.fiveCCompare = function (papers) {
    const rows = papers.filter((p) => H.FIVE_C.some((c) => (p["c_" + c.key] || "").trim()));
    if (!rows.length) return el("div.empty-state", null, H.icon("grid", 22), el("p", null, t("st_compare_empty")));
    const typeLabel = { problem: t("st_problem"), puzzle: t("st_puzzle"), twist: t("st_twist") };
    return el("div.matrix-wrap", null, el("table.c5-table", null,
      el("thead", null, el("tr", null, el("th", { scope: "col" }, t("papers")), H.FIVE_C.map((c) => el("th", { scope: "col" }, `${c.mark} ${H.lang === "en" ? c.en : c.zh}`)))),
      el("tbody", null, rows.map((p) => el("tr", null,
        el("th", { scope: "row" }, el("button.linkish", { type: "button", onclick: () => H.editPaper(p), title: p.title },
          `${(p.authors || "").split(/[;,]/)[0] || p.title.slice(0, 30)}${p.year ? " " + p.year : ""}`),
          p.story_role ? el("span.pill.tiny", null, H.FIVE_C.find((c) => c.key === p.story_role).mark) : null),
        H.FIVE_C.map((c) => el("td", null, c.key === "complication" && p.complication_type ? el("span.pill.tiny", null, typeLabel[p.complication_type]) : null,
          el("span.c5-cell", null, p["c_" + c.key] || "—"))))))));
  };
})();
