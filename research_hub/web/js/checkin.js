/* Research Hub — upload check-in: every upload says where the stage stands, sets the goal,
   is archived to a stage automatically, and can start related-literature tracking. */
(function () {
  const H = window.H;
  const { el, t } = H;

  const PROVIDERS = [["openalex", "OpenAlex"], ["wiley", "Wiley"], ["semantic", "Semantic Scholar"], ["wos", "Web of Science"]];

  /* Expected progress from the stage's start/due dates, and how far ahead/behind it is. */
  H.pace = function (stage) {
    if (!stage || stage.status === "done" || !stage.start_date || !stage.due_date) return null;
    const start = new Date(stage.start_date + "T00:00:00"), due = new Date(stage.due_date + "T00:00:00");
    const span = due - start;
    if (!(span > 0)) return null;
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const expected = Math.max(0, Math.min(100, Math.round(((today - start) / span) * 100)));
    if (expected < 10) return null; // too early in the stage to judge the pace
    const delta = (stage.progress || 0) - expected;
    return { expected, delta, kind: delta <= -15 ? "behind" : delta >= 15 ? "ahead" : "on" };
  };
  H.paceLabel = (p) => (!p ? null : p.kind === "behind" ? t("pace_behind", { n: -p.delta }) : p.kind === "ahead" ? t("pace_ahead", { n: p.delta }) : t("pace_on"));

  function defaultQuery(note) {
    const vars = H.state.variables.map((v) => v.name_en).filter(Boolean).slice(0, 4);
    const words = (note.match(/[A-Za-z][A-Za-z-]{3,}/g) || []).filter((w) => !/^(this|that|with|from|have|been|will|into|about|draft|done|chapter)$/i.test(w));
    const seen = new Set(vars.join(" ").toLowerCase().split(/\s+/));
    const out = [...vars];
    for (const w of words) { const k = w.toLowerCase(); if (!seen.has(k)) { seen.add(k); out.push(w); } }
    out.splice(6);
    if (!out.length) out.push(...(H.state.settings.project_title.match(/[A-Za-z][A-Za-z-]{2,}/g) || []).filter((w) => !/^research$/i.test(w)));
    return out.join(" ").slice(0, 200);
  }

  async function uploadAll(files, stageId) {
    const ids = [];
    for (const f of files) {
      const out = await H.api("/api/upload?stage_id=" + stageId, { body: f, headers: { "X-Filename": encodeURIComponent(f.name), "Content-Type": "application/octet-stream" } });
      ids.push(out.id);
    }
    return ids;
  }

  /**
   * opts.files: File[] to upload (may be empty: a progress check-in without files)
   * opts.stageId: preferred stage (e.g. the stage whose drop zone was used)
   */
  H.openCheckin = async function (opts = {}) {
    const files = [...(opts.files || [])];
    const s = H.state;
    let usage = null;
    try { usage = await H.api("/api/usage"); } catch (_) { /* usage display is optional */ }
    let auto = { stage_id: null, matched: [] };
    if (files.length) { try { auto = await H.api("/api/classify", { body: { names: files.map((f) => f.webkitRelativePath || f.name) } }); } catch (_) { /* fall back */ } }
    const current = s.stages.find((x) => ["active", "review", "blocked"].includes(x.status)) || s.stages.find((x) => x.status !== "done") || s.stages[0];
    let stageId = opts.stageId || auto.stage_id || current.id;

    /* --- fields --- */
    const fileList = el("ul.ci-files");
    const drawFiles = () => H.put(fileList, files.length ? files.map((f, i) => el("li", null, H.icon("file", 14), el("span.ci-fname", { title: f.name }, f.name), el("span.mono.muted", null, H.size(f.size)),
      H.btn(t("delete"), { icon: "x", iconOnly: true, small: true, variant: "ghost", onclick: () => { files.splice(i, 1); drawFiles(); } }))) : el("li.muted.sm", null, t("ci_no_files")));
    drawFiles();
    const picker = el("input", { type: "file", multiple: true, hidden: true, onchange: () => { files.push(...picker.files); picker.value = ""; drawFiles(); } });
    const stageSel = H.select(String(stageId), s.stages.map((x, i) => [String(x.id), `${String(i + 1).padStart(2, "0")} ${H.stageTitle(x)}`]));
    const autoHint = el("div.hint");
    const note = H.textarea("", { rows: 4, placeholder: t("ci_note_ph"), required: true, "aria-required": "true" });
    const range = el("input.range", { type: "range", min: 0, max: 100, step: 5 });
    const pct = el("output.mono");
    let progressTouched = false;
    range.addEventListener("input", () => { progressTouched = true; pct.textContent = range.value + "%"; range.style.setProperty("--v", range.value + "%"); });
    const taskBox = el("ul.ci-tasks");
    const due = el("input.inp", { type: "date" });
    const goal = H.textarea("", { rows: 2, placeholder: t("ci_goal_ph") });
    const deadline = el("input.inp", { type: "date", value: s.settings.project_deadline || "" });
    const trackOn = el("input", { type: "checkbox", checked: true });
    const query = H.input("", { placeholder: t("search_ph") });
    let queryTouched = false;
    query.addEventListener("input", () => { queryTouched = true; });
    note.addEventListener("input", H.debounce(() => { if (!queryTouched) query.value = defaultQuery(note.value); }, 300));
    const chosen = new Set((s.settings.watch_providers || ["openalex"]).filter((p) => p !== "wos" || s.settings.wos_api_key_set));
    const left = (p) => { const u = usage && usage.providers[p]; return u && u.limit ? Math.max(0, u.limit - u.requests) : null; };
    const providerChips = el("div.ci-providers", null, PROVIDERS.map(([id, label]) => {
      const disabled = id === "wos" && !s.settings.wos_api_key_set;
      const box = el("input", { type: "checkbox", checked: chosen.has(id), disabled, onchange: () => (box.checked ? chosen.add(id) : chosen.delete(id)) });
      const n = left(id);
      return el("label.ci-prov" + (disabled ? ".off" : ""), { title: disabled ? t("wos_needs_key") : "" }, box, el("span", null, label),
        n != null ? el("span.count", null, t("left_today", { n })) : null);
    }), el("a.btn.ghost.sm", { href: "#", onclick: (e) => { e.preventDefault(); window.open("https://scholar.google.com/scholar?q=" + encodeURIComponent(query.value || defaultQuery(note.value)), "_blank", "noopener"); } },
      H.icon("external", 13), el("span", null, "Google Scholar")));

    const drawStage = () => {
      const st = H.by(s.stages, Number(stageSel.value));
      const prog = st.status === "done" ? 100 : st.progress;
      range.value = prog; pct.textContent = prog + "%"; range.style.setProperty("--v", prog + "%"); progressTouched = false;
      due.value = st.due_date || ""; goal.value = st.goal || "";
      const tasks = s.tasks.filter((x) => x.stage_id === st.id);
      const preview = () => {
        if (progressTouched || !H.state.settings.auto_progress_from_tasks || !tasks.length) return;
        const n = taskBox.querySelectorAll("input[data-task]:checked").length;
        const v = Math.round((n * 100) / tasks.length);
        range.value = v; pct.textContent = v + "%"; range.style.setProperty("--v", v + "%");
      };
      H.put(taskBox, tasks.length ? tasks.map((task) => el("li" + (task.done ? ".done" : ""), null,
        el("label.check", null, el("input", { type: "checkbox", checked: !!task.done, disabled: !!task.done, dataset: { task: task.id }, onchange: preview }), el("span.box", null, H.icon("check", 12))),
        el("span", null, task.title))) : el("li.muted.sm", null, t("ci_no_tasks")));
      const a = auto.stage_id ? H.by(s.stages, auto.stage_id) : null;
      H.put(autoHint, a ? [H.icon("sparkle", 12), " ", t("ci_auto", { stage: H.stageTitle(a), words: auto.matched.slice(0, 4).join(", ") }),
        a.id !== st.id ? el("button.linkish.inline", { type: "button", onclick: () => { stageSel.value = String(a.id); drawStage(); } }, t("ci_use")) : null]
        : files.length ? t("ci_auto_none") : null);
    };
    stageSel.addEventListener("change", drawStage);
    drawStage();

    /* --- optional AI reading of the note --- */
    const aiOut = el("div.ci-ai-out");
    const aiReady = usage && usage.ai;
    const aiBtn = aiReady ? H.btn(t("ci_ai"), { icon: "sparkle", small: true, variant: "outline", onclick: async () => {
      if (!note.value.trim()) { note.focus(); return H.toast(t("ci_note_required"), "error"); }
      aiBtn.disabled = true; H.put(aiOut, el("span.muted.sm", null, t("ci_ai_busy")));
      try {
        const r = await H.api("/api/ai/suggest", { body: { stage_id: Number(stageSel.value), note: note.value, files: files.map((f) => f.name) } });
        if (r.progress != null) { range.value = r.progress; range.dispatchEvent(new Event("input")); }
        for (const id of r.done_task_ids || []) { const b = taskBox.querySelector(`input[data-task="${id}"]`); if (b && !b.disabled) b.checked = true; }
        if (r.query && !queryTouched) query.value = r.query;
        H.put(aiOut, el("p.ci-ai-sum", null, H.icon("sparkle", 13), r.summary || t("ci_ai_done")), el("span.mono.muted.sm", null, t("tokens_used", { n: r.tokens })));
      } catch (e) { H.put(aiOut); H.toast(e.message, "error"); }
      aiBtn.disabled = false;
    } }) : null;

    const section = (n, title, ...kids) => el("section.ci-sec", null, el("div.ci-sec-head", null, el("span.ci-n.mono", null, n), el("h3", null, title)), ...kids);
    const body = el("div.checkin", null,
      section("01", t("ci_files"), fileList, el("div.toolbar", null, H.btn(t("ci_add_files"), { icon: "plus", small: true, variant: "ghost", onclick: () => picker.click() }), picker),
        H.field(t("ci_archive"), stageSel, null), autoHint),
      section("02", t("ci_where") + " *", note, el("div.ci-ai", null, aiBtn, aiOut)),
      section("03", t("progress"), el("div.progress-ctl", null, range, pct), el("p.hint", null, s.settings.auto_progress_from_tasks ? t("ci_auto_progress") : t("ci_manual_progress")), taskBox),
      section("04", t("ci_goal"), el("div.form-grid", null, H.field(t("ci_stage_due"), due), H.field(t("ci_deadline"), deadline),
        el("div.span2", null, H.field(t("ci_goal_text"), goal)))),
      section("05", t("ci_track"), el("label.toggle", null, trackOn, el("span.track-t", null, el("span.knob")), el("span", null, t("ci_track_on"))),
        query, providerChips, el("p.hint", null, t("ci_track_hint"))));

    const submit = H.btn(t("ci_submit"), { icon: "check", variant: "primary", onclick: async () => {
      if (!note.value.trim()) { note.focus(); return H.toast(t("ci_note_required"), "error"); }
      const sid = Number(stageSel.value);
      submit.disabled = true;
      try {
        const fileIds = await uploadAll(files, sid);
        const done = [...taskBox.querySelectorAll("input[data-task]")].filter((b) => b.checked && !b.disabled).map((b) => Number(b.dataset.task));
        const st = H.by(H.state.stages, sid);
        const payload = { stage_id: sid, note: note.value, file_ids: fileIds, done_task_ids: done,
          due_date: due.value, goal: goal.value, project_deadline: deadline.value || undefined };
        if (progressTouched) payload.progress = Number(range.value);
        if (trackOn.checked && chosen.size && query.value.trim()) payload.search = { query: query.value.trim(), providers: [...chosen] };
        const out = await H.api("/api/checkin", { body: payload });
        H.closeLayer();
        H.toast(t("ci_saved", { stage: H.stageTitle(st), n: out.stage.status === "done" ? 100 : out.stage.progress }) + (out.search_started ? " · " + t("ci_searching") : ""), "ok",
          out.search_started ? { label: t("inbox"), fn: H.openInbox } : null);
        H.ui.openStage = sid;
        await H.refresh(true);
      } catch (e) { H.toast(e.message, "error"); submit.disabled = false; }
    } });
    H.openLayer("modal", t("ci_title"), body, [H.btn(t("cancel"), { variant: "ghost", onclick: H.closeLayer }), submit], { wide: true, eyebrow: t("ci_eyebrow"), id: "checkin" });
    note.focus();
  };

  /* Drop zones now open the check-in instead of uploading silently. */
  H.dropzone = function (query, label) {
    const stageId = Number((query.match(/stage_id=(\d+)/) || [])[1]) || null;
    const input = el("input", { type: "file", multiple: true, hidden: true });
    const zone = el("button.dropzone", { type: "button", onclick: () => input.click() }, H.icon("upload", 18), el("span", null, label || t("drop_files")));
    const go = (files) => { if (files.length) H.openCheckin({ files, stageId }); };
    input.addEventListener("change", () => { go([...input.files]); input.value = ""; });
    zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
    zone.addEventListener("dragleave", () => zone.classList.remove("over"));
    zone.addEventListener("drop", (e) => { e.preventDefault(); zone.classList.remove("over"); go([...e.dataTransfer.files]); });
    return el("div", null, zone, input);
  };

  /* Progress log for one stage (newest first). */
  H.progressLog = function (stage) {
    const items = H.state.updates.filter((u) => u.stage_id === stage.id).slice(0, 12);
    if (!items.length) return el("p.empty.sm", null, t("log_empty"));
    return el("ol.plog", null, items.map((u) => {
      let names = [];
      try { names = JSON.parse(u.files || "[]"); } catch (_) { /* old rows */ }
      const delta = u.progress_after - u.progress_before;
      return el("li", null,
        el("div.plog-head", null, el("time.mono.muted", { datetime: u.created, title: u.created }, H.when(u.created)),
          el("span.plog-delta" + (delta > 0 ? ".up" : delta < 0 ? ".down" : ""), null, `${u.progress_before}% → ${u.progress_after}%`)),
        el("p.plog-note", null, u.note),
        names.length ? el("div.chips", null, names.map((n) => el("span.pill.tiny", null, H.icon("file", 11), n))) : null);
    }));
  };
})();
