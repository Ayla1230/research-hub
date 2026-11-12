/* Research Hub — pipeline of stage nodes and the expandable stage workspace. */
(function () {
  const H = window.H;
  const { el, t } = H;

  const STATUS_ICON = { done: "check", blocked: "alert", review: "eye" };

  function ring(stage) {
    const pct = stage.status === "done" ? 100 : Math.max(0, Math.min(100, stage.progress || 0));
    const r = 25, c = 2 * Math.PI * r;
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 60 60");
    svg.setAttribute("class", "ring");
    svg.setAttribute("aria-hidden", "true");
    const track = document.createElementNS(ns, "circle");
    Object.entries({ cx: 30, cy: 30, r, class: "ring-track" }).forEach(([k, v]) => track.setAttribute(k, v));
    const bar = document.createElementNS(ns, "circle");
    Object.entries({ cx: 30, cy: 30, r, class: "ring-bar", "stroke-dasharray": `${(pct / 100) * c} ${c}`, transform: "rotate(-90 30 30)" })
      .forEach(([k, v]) => bar.setAttribute(k, v));
    svg.append(track);
    if (pct > 0) svg.append(bar);
    return svg;
  }

  function stageTasks(stage) {
    return H.state.tasks.filter((x) => x.stage_id === stage.id);
  }

  function node(stage, index, total) {
    const tasks = stageTasks(stage);
    const done = tasks.filter((x) => x.done).length;
    const open = H.ui.openStage === stage.id;
    const due = stage.status !== "done" ? H.dueLabel(stage.due_date) : null;
    const button = el("button.node-btn", {
      type: "button", "aria-expanded": String(open), "aria-controls": "stage-panel",
      "aria-label": `${String(index + 1).padStart(2, "0")} ${H.stageTitle(stage)} — ${t("st_" + stage.status)}, ${stage.status === "done" ? 100 : stage.progress}%`,
      dataset: { stage: stage.id, fkey: "node-" + stage.id },
      onclick: () => { H.ui.openStage = open ? null : stage.id; H.render.pipeline(); if (!open) requestAnimationFrame(() => document.getElementById("stage-panel")?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "nearest" })); },
      onkeydown: (e) => {
        if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
        const all = [...document.querySelectorAll(".node-btn")];
        const i = all.indexOf(e.currentTarget) + (e.key === "ArrowRight" ? 1 : -1);
        if (all[i]) { e.preventDefault(); all[i].focus(); }
      },
    },
      el("span.disc", null, ring(stage),
        STATUS_ICON[stage.status] ? el("span.disc-ic", null, H.icon(STATUS_ICON[stage.status], 18)) : el("span.disc-num", null, String(index + 1).padStart(2, "0"))),
      el("span.node-title", null, H.stageTitle(stage)),
      el("span.node-meta", null,
        el("span.dot." + stage.status), t("st_" + stage.status),
        tasks.length ? el("span.sep", null, "·") : null, tasks.length ? `${done}/${tasks.length}` : null),
      due ? el("span.node-due." + (due.kind || "plain"), null, due.text) : null);

    const tools = H.ui.editPipeline ? el("div.node-tools", null,
      H.btn(t("move_left"), { icon: "chevL", iconOnly: true, small: true, variant: "ghost", disabled: index === 0, onclick: () => move(stage, -1), dataset: { fkey: "move-l-" + stage.id } }),
      H.btn(t("move_right"), { icon: "chevR", iconOnly: true, small: true, variant: "ghost", disabled: index === total - 1, onclick: () => move(stage, 1), dataset: { fkey: "move-r-" + stage.id } }),
      H.btn(t("delete"), { icon: "trash", iconOnly: true, small: true, variant: "ghost", disabled: total <= 1, onclick: () => removeStage(stage) })) : null;

    return el("li.node." + stage.status + (open ? ".open" : ""), { style: { "--i": index } }, button, tools);
  }

  async function move(stage, dir) {
    const list = [...H.state.stages];
    const i = list.findIndex((s) => s.id === stage.id);
    const j = i + dir;
    if (j < 0 || j >= list.length) return;
    [list[i], list[j]] = [list[j], list[i]];
    await H.ops(list.map((s, k) => ({ op: "update", entity: "stage", id: s.id, data: { position: k } })));
    const btn = document.querySelector(`[data-fkey="move-${dir < 0 ? "l" : "r"}-${stage.id}"]`);
    if (btn && btn.disabled) document.querySelector(`[data-fkey="move-${dir < 0 ? "r" : "l"}-${stage.id}"]`)?.focus();
  }
  async function removeStage(stage) {
    if (!(await H.confirm(t("delete_stage_q")))) return;
    if (H.ui.openStage === stage.id) H.ui.openStage = null;
    const list = H.state.stages;
    const i = list.findIndex((s) => s.id === stage.id);
    const neighbour = list[i + 1] || list[i - 1];
    await H.ops([{ op: "delete", entity: "stage", id: stage.id }]);
    if (neighbour) document.querySelector(`.node-btn[data-stage="${neighbour.id}"]`)?.focus();
  }
  async function addStage() {
    const pos = H.state.stages.length;
    const out = await H.ops([{ op: "create", entity: "stage", data: { title_zh: H.lang === "en" ? "New stage" : t("new_stage"), title_en: "New stage", key: "stage" + (pos + 1), position: pos } }]);
    H.ui.openStage = out.results[0].id;
    H.render.pipeline();
    stageSettings(H.by(H.state.stages, H.ui.openStage));
  }

  /* ---------------- stage workspace ---------------- */
  function statusControl(stage) {
    return el("div.seg", { role: "radiogroup", "aria-label": t("status") },
      H.STAGE_STATUS.map((st) => el("button.seg-btn." + st, {
        type: "button", role: "radio", "aria-checked": String(stage.status === st), dataset: { fkey: `stage-st-${stage.id}-${st}` },
        onclick: () => {
          const data = { status: st };
          if (st === "active" && !stage.start_date) data.start_date = new Date().toISOString().slice(0, 10);
          H.ops([{ op: "update", entity: "stage", id: stage.id, data }]);
        },
      }, el("span.dot." + st), t("st_" + st))));
  }

  function progressControl(stage) {
    const value = stage.status === "done" ? 100 : stage.progress;
    const out = el("output.mono", null, value + "%");
    const range = el("input.range", { type: "range", min: 0, max: 100, step: 5, value, "aria-label": t("progress"), dataset: { fkey: "stage-prog-" + stage.id },
      style: { "--v": value + "%" } });
    range.addEventListener("input", () => { out.textContent = range.value + "%"; range.style.setProperty("--v", range.value + "%"); });
    range.addEventListener("change", () => {
      const v = Number(range.value);
      const data = { progress: v };
      if (v === 100 && stage.status !== "done") data.status = "review";
      if (v < 100 && stage.status === "done") data.status = "active";
      H.ops([{ op: "update", entity: "stage", id: stage.id, data }]);
    });
    return el("div.progress-ctl", null, el("span.lbl", null, t("progress")), range, out);
  }

  function dateControl(stage, field, label) {
    const input = el("input.inp.sm", { type: "date", value: stage[field] || "", "aria-label": label, dataset: { fkey: `stage-${field}-${stage.id}` } });
    input.addEventListener("change", () => H.ops([{ op: "update", entity: "stage", id: stage.id, data: { [field]: input.value } }]));
    return el("label.date-ctl", null, el("span.lbl", null, label), input);
  }

  function taskList(stage) {
    const tasks = stageTasks(stage);
    const list = el("ul.tasks", null, tasks.map((task) => {
      const box = el("input", { type: "checkbox", checked: !!task.done, "aria-label": task.title, dataset: { fkey: "task-" + task.id },
        onchange: () => H.ops([{ op: "update", entity: "task", id: task.id, data: { done: box.checked } }]) });
      const title = el("span.task-title", { contenteditable: "plaintext-only", spellcheck: "false", role: "textbox", "aria-label": t("edit") }, task.title);
      title.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); title.blur(); } });
      title.addEventListener("blur", () => {
        const v = title.textContent.trim();
        if (v && v !== task.title) H.ops([{ op: "update", entity: "task", id: task.id, data: { title: v } }]);
        else title.textContent = task.title;
      });
      return el("li.task" + (task.done ? ".done" : ""), null, el("label.check", null, box, el("span.box", null, H.icon("check", 12))), title,
        H.btn(t("delete"), { icon: "x", iconOnly: true, small: true, variant: "ghost", class: "task-del",
          onclick: () => H.ops([{ op: "delete", entity: "task", id: task.id }]) }));
    }));
    const add = el("input.inp.task-add", { type: "text", placeholder: t("add_task_ph"), "aria-label": t("add_task_ph"), dataset: { fkey: "task-add-" + stage.id } });
    add.addEventListener("keydown", async (e) => {
      if (e.key !== "Enter" || !add.value.trim()) return;
      const title = add.value.trim();
      add.value = "";
      try { await H.ops([{ op: "create", entity: "task", data: { stage_id: stage.id, title } }]); }
      catch (_) { add.value = title; }
    });
    const done = tasks.filter((x) => x.done).length;
    return el("div.card", null,
      el("div.card-head", null, el("h4", null, t("tasks")), tasks.length ? el("span.mono.muted", null, t("tasks_done", { a: done, b: tasks.length })) : null),
      list, add);
  }

  H.dropzone = function (query, label) {
    const input = el("input", { type: "file", multiple: true, hidden: true });
    const zone = el("button.dropzone", { type: "button", onclick: () => input.click() }, H.icon("upload", 18), el("span", null, label || t("drop_files")));
    const upload = async (files) => {
      if (!files.length) return;
      zone.classList.add("busy");
      zone.querySelector("span").textContent = t("uploading");
      let n = 0;
      try {
        for (const f of files) {
          await H.api("/api/upload?" + query, { body: f, headers: { "X-Filename": encodeURIComponent(f.name), "Content-Type": "application/octet-stream" } });
          n++;
        }
        H.toast(t("uploaded", { n }), "ok");
      } catch (e) { H.toast(e.message, "error"); }
      await H.refresh();
    };
    input.addEventListener("change", () => upload([...input.files]));
    zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
    zone.addEventListener("dragleave", () => zone.classList.remove("over"));
    zone.addEventListener("drop", (e) => { e.preventDefault(); zone.classList.remove("over"); upload([...e.dataTransfer.files]); });
    return el("div", null, zone, input);
  };

  H.fileRow = function (f) {
    return el("li.file-row", null, H.icon("file", 16),
      el("a.file-name", { href: `/api/files/${f.id}?token=`, target: "_blank", rel: "noopener", onclick: (e) => { e.preventDefault(); openFile(f); } }, f.name),
      el("span.mono.muted", null, H.size(f.size)),
      H.btn(t("download"), { icon: "download", iconOnly: true, small: true, variant: "ghost", onclick: () => openFile(f, true) }),
      H.btn(t("delete"), { icon: "trash", iconOnly: true, small: true, variant: "ghost",
        onclick: async () => { if (await H.confirm(t("confirm_delete", { name: f.name }))) H.ops([{ op: "delete", entity: "file", id: f.id }]); } }));
  };
  /* Files need the page token, so fetch them and hand the browser a blob URL. */
  async function openFile(f, download) {
    // Never render uploaded HTML/SVG as a page from this origin: hand it over as a download.
    if (/\.(x?html?|svg|xml)$/i.test(f.name) || /html|svg|xml/i.test(f.mime || "")) download = true;
    const win = download ? null : window.open("", "_blank");
    try {
      const res = await fetch(`/api/files/${f.id}${download ? "?download=1" : ""}`, { headers: { "X-Hub-Token": H.token } });
      if (!res.ok) throw new Error((await res.json()).error);
      const url = URL.createObjectURL(await res.blob());
      if (download) { const a = el("a", { href: url, download: f.name }); document.body.append(a); a.click(); a.remove(); }
      else if (win) win.location = url;
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) { if (win) win.close(); H.toast(e.message, "error"); }
  }
  H.openFile = openFile;
  H.openLocal = async function (path) {
    const win = window.open("", "_blank");
    try {
      const res = await fetch("/api/local?path=" + encodeURIComponent(path), { headers: { "X-Hub-Token": H.token } });
      if (!res.ok) throw new Error((await res.json()).error);
      const url = URL.createObjectURL(await res.blob());
      win.location = url;
      setTimeout(() => URL.revokeObjectURL(url), 120000);
    } catch (e) { win?.close(); H.toast(e.message, "error"); }
  };

  function filesCard(stage) {
    const files = H.state.files.filter((f) => f.stage_id === stage.id);
    return el("div.card", null,
      el("div.card-head", null, el("h4", null, t("files")), files.length ? el("span.mono.muted", null, String(files.length)) : null),
      H.dropzone("stage_id=" + stage.id),
      files.length ? el("ul.file-list", null, files.map(H.fileRow)) : null);
  }

  function resourcesCard(stage) {
    const res = H.state.resources.filter((r) => r.stage_id === stage.id);
    return el("div.card", null,
      el("div.card-head", null, el("h4", null, t("linked_resources")),
        H.btn(t("add_resource"), { icon: "plus", small: true, variant: "ghost", onclick: () => H.editResource(null, { stage_id: stage.id }) })),
      res.length ? el("ul.res-list", null, res.map(H.resourceRow)) : el("p.empty.sm", null, t("none")));
  }

  function stageSettings(stage) {
    const f = {
      title_zh: H.input(stage.title_zh), title_en: H.input(stage.title_en), key: H.input(stage.key),
      desc_zh: H.textarea(stage.desc_zh), desc_en: H.textarea(stage.desc_en),
      module: H.select(stage.module, ["", "literature", "rq", "variables", "code", "writing"].map((m) => [m, t("mod_" + (m || "none"))])),
    };
    const body = el("div.form-grid", null,
      H.field(t("stage_title_zh"), f.title_zh), H.field(t("stage_title_en"), f.title_en),
      H.field(t("desc_zh"), f.desc_zh), H.field(t("desc_en"), f.desc_en),
      H.field(t("module"), f.module), H.field(t("key"), f.key, "MCP: report_stage_progress(stage_key)"));
    const save = H.btn(t("save"), { variant: "primary", onclick: async () => {
      const data = Object.fromEntries(Object.entries(f).map(([k, n]) => [k, n.value]));
      if (!data.title_zh.trim()) { f.title_zh.focus(); return H.toast(t("required"), "error"); }
      await H.ops([{ op: "update", entity: "stage", id: stage.id, data }]);
      H.closeLayer();
    } });
    H.openLayer("modal", t("stage_settings"), body, [H.btn(t("cancel"), { variant: "ghost", onclick: H.closeLayer }), save], { eyebrow: H.stageTitle(stage) });
  }

  function panel(stage) {
    const stages = H.state.stages;
    const index = stages.findIndex((s) => s.id === stage.id);
    const saveState = el("span.save-state.mono", { "aria-live": "polite" });
    const notes = H.autosave(H.textarea(stage.notes, { rows: 7, placeholder: t("notes_ph"), "aria-label": t("notes") }), "stage", stage.id, "notes", saveState);
    const mod = stage.module ? H.renderModule(stage.module, stage) : null;
    return el("div.stage-panel", { id: "stage-panel", role: "region", "aria-label": H.stageTitle(stage), style: { "--caret": `${index}` } },
      el("div.sp-head", null,
        el("div.sp-title", null,
          el("div.eyebrow", null, t("stage_of", { i: index + 1, n: stages.length }), stage.key ? el("span.mono.key", null, stage.key) : null),
          el("h3", null, H.stageTitle(stage)),
          H.stageDesc(stage) ? el("p.lead", null, H.stageDesc(stage)) : null),
        el("div.sp-actions", null,
          H.btn(t("stage_settings"), { icon: "settings", iconOnly: true, variant: "ghost", onclick: () => stageSettings(stage) }),
          H.btn(t("close"), { icon: "x", iconOnly: true, variant: "ghost", onclick: () => { H.ui.openStage = null; H.render.pipeline(); document.querySelector(`.node-btn[data-stage="${stage.id}"]`)?.focus(); } }))),
      el("div.sp-controls", null, statusControl(stage), progressControl(stage),
        el("div.dates", null, dateControl(stage, "start_date", t("start_date")), dateControl(stage, "due_date", t("due_date")))),
      el("div.sp-grid", null,
        el("div.card.notes-card", null, el("div.card-head", null, el("h4", null, t("notes")), saveState), notes),
        taskList(stage),
        filesCard(stage),
        resourcesCard(stage)),
      mod ? el("div.sp-module", null, el("div.module-head", null, el("span.eyebrow", null, t("module")), el("h4", null, t("mod_" + stage.module))), mod) : null);
  }

  H.render = H.render || {};
  H.render.pipeline = function () {
    const root = document.getElementById("pipeline");
    const stages = H.state.stages;
    if (H.ui.openStage && !H.by(stages, H.ui.openStage)) H.ui.openStage = null;
    const doneCount = stages.filter((s) => s.status === "done").length;
    const lastDone = stages.reduce((acc, s, i) => (s.status === "done" ? i : acc), -1);
    const head = el("div.band-head", null,
      el("div", null, el("div.eyebrow", null, "01", el("span", null, "/"), t("pipeline")), el("h2", null, t("pipeline")), el("p.sub", null, t("pipeline_hint"))),
      el("div.band-actions", null,
        H.ui.editPipeline ? H.btn(t("add_stage"), { icon: "plus", variant: "ghost", onclick: addStage }) : null,
        H.btn(H.ui.editPipeline ? t("done_editing") : t("edit_pipeline"), { icon: H.ui.editPipeline ? "check" : "edit", variant: H.ui.editPipeline ? "primary" : "ghost",
          onclick: () => { H.ui.editPipeline = !H.ui.editPipeline; H.render.pipeline(); } })));
    const fill = stages.length > 1 ? Math.max(0, lastDone) / (stages.length - 1) : 0;
    const track = el("ol.track", { style: { "--n": stages.length, "--fill": fill }, "aria-label": t("pipeline") + ` — ${doneCount}/${stages.length}` },
      stages.map((s, i) => node(s, i, stages.length)));
    const open = H.ui.openStage ? H.by(stages, H.ui.openStage) : null;
    H.put(root, head, el("div.track-wrap", null, el("div.track-scroll", null, track)), open ? panel(open) : null);
  };
})();
