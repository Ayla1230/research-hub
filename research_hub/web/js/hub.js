/* Research Hub — integration hub, resources, inbox (proposals), settings, activity. */
(function () {
  const H = window.H;
  const { el, t } = H;
  const KIND_ICON = { database: "database", folder: "folder", mcp: "plug", code: "code", link: "link", paperread: "book" };

  /* ================= resources ================= */
  H.resourceRow = function (r) {
    const isUrl = /^https?:\/\//i.test(r.target || "");
    const target = isUrl ? r.target.replace("{q}", "") : r.target;
    return el("li.res-row", null,
      el("span.res-ic", null, H.icon(KIND_ICON[r.kind] || "link", 15)),
      el("div.res-main", null,
        isUrl ? el("a.res-name", { href: target, target: "_blank", rel: "noopener noreferrer" }, r.name) : el("span.res-name", null, r.name),
        r.target && !isUrl ? el("code.res-target", null, r.target) : null,
        r.notes ? el("span.res-notes", null, r.notes) : null),
      r.target && !isUrl ? H.btn(t("copy"), { icon: "copy", iconOnly: true, small: true, variant: "ghost", onclick: () => H.copy(r.target) }) : null,
      (r.kind === "folder" || r.kind === "code") && r.target ? H.btn(t("open_folder"), { icon: "folder", iconOnly: true, small: true, variant: "ghost", onclick: () => reveal(r.target) }) : null,
      H.btn(t("edit"), { icon: "edit", iconOnly: true, small: true, variant: "ghost", onclick: () => H.editResource(r) }));
  };
  async function reveal(path) {
    try { await H.api("/api/reveal", { body: { path } }); } catch (e) { H.toast(e.message, "error"); }
  }

  H.editResource = function (r, defaults = {}) {
    const f = {
      kind: H.select(r ? r.kind : defaults.kind || "link", Object.keys(KIND_ICON).map((k) => [k, t("k_" + k)])),
      name: H.input(r ? r.name : ""), target: H.input(r ? r.target : "", { placeholder: "https://… /Users/… npx …" }),
      stage_id: H.select(String(r ? r.stage_id || "" : defaults.stage_id || ""), [["", t("none")], ...H.state.stages.map((s) => [String(s.id), H.stageTitle(s)])]),
      notes: H.textarea(r ? r.notes : ""),
    };
    const body = el("div.form-grid", null, H.field(t("kind"), f.kind), H.field(t("stage"), f.stage_id),
      el("div.span2", null, H.field(t("name") + " *", f.name)), el("div.span2", null, H.field(t("target"), f.target, t("target_hint"))),
      el("div.span2", null, H.field(t("notes"), f.notes)));
    const save = async () => {
      if (!f.name.value.trim()) { f.name.focus(); return H.toast(t("required"), "error"); }
      const data = { kind: f.kind.value, name: f.name.value, target: f.target.value, notes: f.notes.value, stage_id: f.stage_id.value ? Number(f.stage_id.value) : null };
      try { await H.ops([r ? { op: "update", entity: "resource", id: r.id, data } : { op: "create", entity: "resource", data }], true); H.closeLayer(); }
      catch (e) { H.toast(e.message, "error"); }
    };
    H.openLayer("modal", r ? `${t("edit")} · ${r.name}` : t("add_resource"), body, [
      r ? H.btn(t("delete"), { icon: "trash", variant: "danger-ghost", class: "left", onclick: async () => { if (await H.confirm(t("confirm_delete", { name: r.name }))) H.ops([{ op: "delete", entity: "resource", id: r.id }]); } }) : null,
      H.btn(t("cancel"), { variant: "ghost", onclick: H.closeLayer }), H.btn(t("save"), { variant: "primary", onclick: save })]);
  };

  /* ================= cards ================= */
  function card(icon, title, sub, body, actions) {
    return el("article.hub-card", null,
      el("div.hub-card-head", null, el("span.hub-ic", null, H.icon(icon, 18)),
        el("div", null, el("h3", null, title), sub ? el("p.sub", null, sub) : null), actions ? el("div.push", null, actions) : null),
      body);
  }

  let dbQuery = "";
  function databasesCard() {
    const dbs = H.state.resources.filter((r) => r.kind === "database");
    const q = H.input(dbQuery, { type: "search", placeholder: t("db_ph"), "aria-label": t("db_ph") });
    q.addEventListener("input", () => { dbQuery = q.value; });
    const open = (r) => {
      const url = r.target.includes("{q}") ? r.target.split("{q}").join(encodeURIComponent(q.value.trim())) : r.target;
      if (H.safeUrl(url)) window.open(url, "_blank", "noopener");
    };
    return card("database", t("databases"), null, el("div", null, el("div.db-search", null, H.icon("search", 15), q),
      el("div.db-chips", null, dbs.map((r) => el("span.db-chip", null,
        el("button.db-go", { type: "button", onclick: () => open(r), title: r.target }, r.name, r.target.includes("{q}") ? H.icon("search", 12) : H.icon("external", 12)),
        el("button.db-edit", { type: "button", "aria-label": `${t("edit")} ${r.name}`, onclick: () => H.editResource(r) }, H.icon("edit", 12)))),
        H.btn(t("add"), { icon: "plus", small: true, variant: "ghost", onclick: () => H.editResource(null, { kind: "database" }) }))));
  }

  let scan = null;
  function foldersCard() {
    const folders = H.state.settings.reference_folders || [];
    const body = el("div");
    if (!folders.length) body.append(el("p.empty.sm", null, t("no_folders")), H.btn(t("settings"), { icon: "settings", small: true, variant: "outline", onclick: () => H.openSettings() }));
    else {
      body.append(el("ul.folder-list", null, folders.map((f) => el("li", null, H.icon("folder", 14), el("code", null, f),
        H.btn(t("open_folder"), { icon: "external", iconOnly: true, small: true, variant: "ghost", onclick: () => reveal(f) })))));
      const row = el("div.toolbar", null,
        H.btn(t("scan"), { icon: "refresh", small: true, variant: "outline", onclick: async () => {
          try { scan = await H.api("/api/scan"); H.render.hub(); } catch (e) { H.toast(e.message, "error"); }
        } }),
        H.btn(t("scan_new"), { icon: "inbox", small: true, variant: "ghost", onclick: async () => {
          try { const out = await H.api("/api/watch/scan", { body: {} }); H.toast(out.proposal ? t("pr_synced") : t("nothing_new"), out.proposal ? "ok" : "info"); }
          catch (e) { H.toast(e.message, "error"); }
        } }));
      body.append(row);
      if (scan) {
        const fresh = scan.files.filter((f) => !f.linked);
        const checks = new Map();
        body.append(el("p.mono.muted.sm", null, t("files_found", { n: scan.files.length })),
          el("ul.scan-list", null, scan.files.slice(0, 300).map((f) => {
            const box = el("input", { type: "checkbox", disabled: f.linked, checked: false });
            checks.set(f.path, box);
            return el("li" + (f.linked ? ".linked" : ""), null, el("label.check", null, box, el("span.box", null, H.icon("check", 12))),
              el("span.scan-name", { title: f.path }, f.rel), el("span.mono.muted", null, f.linked ? t("linked") : H.size(f.size)));
          })),
          fresh.length ? H.btn(t("import_selected"), { icon: "plus", small: true, variant: "primary", onclick: async () => {
            const paths = [...checks].filter(([, b]) => b.checked).map(([p]) => p);
            if (!paths.length) return H.toast(t("select_none"), "error");
            try { const out = await H.api("/api/import/files", { body: { paths } }); H.toast(t("imported", { n: out.imported }), "ok"); scan = null; await H.refresh(); }
            catch (e) { H.toast(e.message, "error"); }
          } }) : null);
      }
    }
    return card("folder", t("ref_folders"), null, body);
  }

  let prStatus = null;
  async function loadPr() { try { prStatus = await H.api("/api/paperread/status"); } catch (e) { prStatus = { error: e.message }; } H.render.hub(); }
  function paperreadCard() {
    if (!prStatus) setTimeout(loadPr, 0);
    const s = H.state.settings;
    const online = prStatus && prStatus.online;
    return card("book", t("paperread"), s.paperread_url, el("div", null,
      el("div.status-line", null, el("span.dot." + (online ? "done" : "todo")), prStatus ? (online ? t("pr_online") : t("pr_offline")) : "…",
        el("span.sep", null, "·"), prStatus ? (prStatus.library_found ? t("pr_library", { n: prStatus.count }) : t("pr_nolib")) : ""),
      el("code.path", null, s.paperread_library),
      el("div.toolbar", null,
        el("a.btn.outline.sm", { href: H.safeUrl(s.paperread_url) || "#", target: "_blank", rel: "noopener" }, H.icon("external", 14), el("span", null, t("pr_open"))),
        H.btn(t("pr_sync"), { icon: "refresh", small: true, variant: "primary", onclick: async () => {
          try { const out = await H.api("/api/paperread/sync", { body: {} }); H.toast(out.proposal ? t("pr_synced") : t("pr_uptodate"), "ok", out.proposal ? { label: t("inbox"), fn: H.openInbox } : null); loadPr(); }
          catch (e) { H.toast(e.message, "error"); }
        } }))), H.btn(t("scan"), { icon: "refresh", iconOnly: true, small: true, variant: "ghost", onclick: loadPr }));
  }

  let agentCfg = null;
  function mcpCard() {
    const mine = H.state.resources.filter((r) => r.kind === "mcp");
    const cmdBox = el("div.cmd-box");
    const drawCmd = () => {
      if (!agentCfg) { H.put(cmdBox, H.btn(t("show_token"), { icon: "eye", small: true, variant: "outline", onclick: async () => { try { agentCfg = await H.api("/api/agent-config"); drawCmd(); } catch (e) { H.toast(e.message, "error"); } } })); return; }
      const py = /\s/.test(agentCfg.python) ? `"${agentCfg.python}"` : agentCfg.python;
      const claude = `claude mcp add research-hub -- ${py} -m research_hub mcp --url ${agentCfg.url} --token ${agentCfg.token}`;
      const json = JSON.stringify({ mcpServers: { "research-hub": { command: agentCfg.python, args: ["-m", "research_hub", "mcp", "--url", agentCfg.url, "--token", agentCfg.token] } } }, null, 2);
      H.put(cmdBox, 
        el("div.cmd", null, el("span.lbl", null, "Claude Code"), el("pre", null, claude), H.btn(t("copy"), { icon: "copy", iconOnly: true, small: true, variant: "ghost", onclick: () => H.copy(claude) })),
        el("div.cmd", null, el("span.lbl", null, "mcp.json"), el("pre", null, json), H.btn(t("copy"), { icon: "copy", iconOnly: true, small: true, variant: "ghost", onclick: () => H.copy(json) })),
        el("div.toolbar", null, H.btn(t("rotate_token"), { icon: "refresh", small: true, variant: "ghost", onclick: async () => {
          if (!(await H.confirm(t("rotate_q"), t("rotate_token")))) return;
          await H.api("/api/agent-token/rotate", { body: {} }); agentCfg = await H.api("/api/agent-config"); drawCmd();
        } }), H.btn(t("close"), { icon: "x", small: true, variant: "ghost", onclick: () => { agentCfg = null; drawCmd(); } })));
    };
    drawCmd();
    return card("plug", t("mcp"), t("mcp_hint"), el("div", null,
      el("h4.mini", null, t("hub_mcp")), cmdBox,
      el("div.mini-head", null, el("h4.mini", null, t("your_mcp")), H.btn(t("add"), { icon: "plus", small: true, variant: "ghost", onclick: () => H.editResource(null, { kind: "mcp" }) })),
      mine.length ? el("ul.res-list", null, mine.map(H.resourceRow)) : null));
  }

  let scripts = null;
  async function loadScripts() { try { scripts = await H.api("/api/scripts"); } catch (e) { scripts = { error: e.message, scripts: [], runs: [] }; } H.render.hub(); H.render.pipeline(); }
  H.codeCard = function () {
    if (!scripts) setTimeout(loadScripts, 0);
    const s = H.state.settings;
    const body = el("div");
    if (!s.code_dir) body.append(el("p.empty.sm", null, t("code_dir_unset")), H.btn(t("settings"), { icon: "settings", small: true, variant: "outline", onclick: () => H.openSettings() }));
    else if (scripts) {
      body.append(el("div.status-line", null, el("code.path", null, s.code_dir),
        H.btn(t("open_folder"), { icon: "folder", iconOnly: true, small: true, variant: "ghost", onclick: () => reveal(s.code_dir) }),
        H.btn(t("scan"), { icon: "refresh", iconOnly: true, small: true, variant: "ghost", onclick: loadScripts })));
      if (!scripts.allow_run) body.append(el("p.hint-line", null, t("run_disabled")));
      body.append(el("ul.script-list", null, scripts.scripts.slice(0, 100).map((sc) => el("li", null, H.icon("code", 14), el("span.scan-name", { title: sc.path }, sc.rel),
        sc.runnable && scripts.allow_run ? H.btn(t("run"), { icon: "play", small: true, variant: "outline", disabled: scripts.runs.some((r) => r.state === "running"),
          onclick: async () => { try { await H.api("/api/scripts/run", { body: { path: sc.path } }); loadScripts(); } catch (e) { H.toast(e.message, "error"); } } }) : null))));
      if (scripts.runs.length) body.append(el("h4.mini", null, t("recent_runs")), el("ul.runs", null, scripts.runs.slice(0, 5).map((r) =>
        el("li", null, el("details", { open: r === scripts.runs[0] || null }, el("summary", null, el("span.dot." + (r.state === "ok" ? "done" : r.state === "running" ? "active" : "blocked")),
          r.script.split(/[\\/]/).pop(), el("span.mono.muted", null, r.state === "ok" ? t("run_ok") : r.state === "running" ? t("running") : t("run_failed"))),
          el("pre.output", null, r.output || "…"))))));
    }
    return body;
  };

  function filesCard() {
    const files = H.state.files.slice(0, 30);
    return card("file", t("all_files"), null, el("div", null, H.dropzone(""), files.length ? el("ul.file-list", null, files.map((f) => {
      const row = H.fileRow(f);
      const stage = f.stage_id ? H.by(H.state.stages, f.stage_id) : null;
      if (stage) row.insertBefore(el("span.pill.tiny", null, H.stageTitle(stage)), row.children[2]);
      return row;
    })) : el("p.empty.sm", null, t("no_files"))));
  }

  function linksCard() {
    const list = H.state.resources.filter((r) => ["link", "folder", "code", "paperread"].includes(r.kind));
    return card("link", t("other_links"), null, list.length ? el("ul.res-list", null, list.map(H.resourceRow)) : el("p.empty.sm", null, t("none")),
      H.btn(t("add"), { icon: "plus", small: true, variant: "ghost", onclick: () => H.editResource(null) }));
  }

  H.render = H.render || {};
  H.render.hub = function () {
    const root = document.getElementById("hub");
    H.put(root, 
      el("div.band-head", null, el("div", null, el("div.eyebrow", null, "03", el("span", null, "/"), t("hub")), el("h2", null, t("hub")), el("p.sub", null, t("hub_hint")))),
      el("div.hub-grid", null, databasesCard(), paperreadCard(), foldersCard(), mcpCard(),
        card("code", t("code"), null, H.codeCard()), filesCard(), linksCard()));
  };
  H.refreshScripts = loadScripts;

  /* ================= activity ================= */
  H.render.activity = function () {
    const root = document.getElementById("activity");
    const all = H.state.activity;
    const items = all.slice(0, H.ui.activityAll ? 60 : 12);
    const ACTOR = (a) => (a === "user" ? t("a_user") : a === "system" ? t("a_system") : a.replace(" (approved)", " ✓"));
    const actorIcon = (a) => (a === "user" ? "edit" : a === "system" ? "settings" : a.includes("approved") ? "check" : a === "python" ? "code" : "bot");
    H.put(root, 
      el("div.band-head", null, el("div", null, el("div.eyebrow", null, "04", el("span", null, "/"), t("activity")), el("h2", null, t("activity")))),
      items.length ? el("ol.timeline", null, items.map((a) => el("li", null,
        el("span.tl-ic", null, H.icon(actorIcon(a.actor), 13)),
        el("div.tl-main", null, el("span.tl-actor.mono", null, ACTOR(a.actor)),
          el("span.tl-act", null, (H.has("a_" + a.action) ? t("a_" + a.action) : a.action) + (a.entity ? " · " + (H.has("e_" + a.entity) ? t("e_" + a.entity) : a.entity) : "")),
          el("span.tl-sum", null, a.summary)),
        el("time.mono.muted", { datetime: a.at, title: a.at }, H.when(a.at))))) : el("p.empty", null, t("no_activity")),
      all.length > 12 ? el("div.more", null, H.btn(H.ui.activityAll ? t("show_less") : t("view_all"), { small: true, variant: "ghost", icon: "chevD",
        onclick: () => { H.ui.activityAll = !H.ui.activityAll; H.render.activity(); } })) : null);
  };

  /* ================= inbox ================= */
  const ENTITY = (e) => (H.has("e_" + e) ? t("e_" + e) : e);
  const FIELD = (f) => (H.has(f) ? t(f) : H.has("f_" + f) ? t("f_" + f) : f);
  const VALUE = (k, v) => {
    if (k === "status" && H.has("st_" + v)) return t("st_" + v);
    if (k === "status" && H.has("ps_" + v)) return t("ps_" + v);
    if (k === "status" && H.has("rq_" + v)) return t("rq_" + v);
    if (k === "role" && H.has("role_" + v)) return t("role_" + v);
    if (k === "evidence" && H.has("ev_" + v)) return t("ev_" + v);
    if (typeof v === "boolean") return v ? "✓" : "✗";
    return String(v).slice(0, 80);
  };
  function describe(op, all) {
    const s = H.state;
    const refTitle = (ref) => {
      const made = (all || []).find((o) => o.op === "create" && "$" + o.ref === ref);
      const d = (made && made.data) || {};
      return "＋ " + (d.title || d.title_zh || (d.symbol ? `${d.symbol} ${d.name_zh || d.name_en || ""}` : "") || d.name || d.text || ref);
    };
    const name = (entity, id) => {
      if (typeof id === "string" && id.startsWith("$")) return refTitle(id);
      const list = { stage: s.stages, task: s.tasks, rq: s.rqs, variable: s.variables, paper: s.papers, resource: s.resources }[entity] || [];
      const it = typeof id === "number" ? H.by(list, id) : null;
      if (!it) return typeof id === "string" ? id : `#${id}`;
      return entity === "stage" ? H.stageTitle(it) : it.title || (it.symbol ? `${it.symbol} ${H.varName(it)}` : "") || it.code || it.name || `#${id}`;
    };
    if (op.op === "link" || op.op === "unlink") {
      const [ae, be] = { rq_variable: ["rq", "variable"], rq_paper: ["rq", "paper"], variable_paper: ["variable", "paper"] }[op.link] || ["?", "?"];
      return { kind: op.op, text: `${name(ae, op.a)}  ↔  ${name(be, op.b)}`, detail: op.data && op.data.evidence ? t("ev_" + op.data.evidence) : "" };
    }
    const target = op.match ? Object.values(op.match)[0] : op.id;
    if (op.op === "create") {
      const d = op.data || {};
      return { kind: "create", text: `${ENTITY(op.entity)}: ${d.title || d.title_zh || (d.symbol ? d.symbol + " " + (d.name_zh || d.name_en || "") : "") || d.name || d.text || ""}`,
        detail: Object.entries(d).filter(([k, v]) => v && !["title", "title_zh"].includes(k)).slice(0, 5).map(([k, v]) => `${FIELD(k)}: ${VALUE(k, v)}`).join(" · ") };
    }
    if (op.op === "update") {
      const entity = op.entity;
      let label = name(entity, target);
      if (op.match && entity === "stage") { const st = s.stages.find((x) => x.key === target); if (st) label = H.stageTitle(st); }
      const parts = Object.entries(op.data || {}).map(([k, v]) => `${FIELD(k)} → ${VALUE(k, v)}`);
      for (const [k, v] of Object.entries(op.append || {})) parts.push(`${FIELD(k)} ＋ ${String(v).slice(0, 80)}`);
      return { kind: "update", text: `${ENTITY(entity)}: ${label}`, detail: parts.join(" · ") };
    }
    if (op.op === "delete") return { kind: "delete", text: `${ENTITY(op.entity)}: ${name(op.entity, target)}`, detail: "" };
    return { kind: "other", text: JSON.stringify(op).slice(0, 120), detail: "" };
  }
  const OP_ICON = { create: "plus", update: "edit", delete: "trash", link: "link", unlink: "x", other: "sparkle" };

  /* Indices of ops that reference "$ref" objects created by op i (directly or transitively). */
  function dependents(ops) {
    const refOf = new Map(ops.map((o, i) => [i, o && o.op === "create" && o.ref ? "$" + o.ref : null]));
    const uses = (o, ref) => JSON.stringify(o).includes(JSON.stringify(ref));
    const deps = ops.map(() => new Set());
    ops.forEach((_, i) => {
      const ref = refOf.get(i);
      if (!ref) return;
      ops.forEach((o, j) => { if (j !== i && uses(o, ref)) deps[i].add(j); });
    });
    return deps;
  }

  function proposalCard(p, pending) {
    const checks = [];
    const deps = dependents(p.ops);
    const conflicts = new Set(p.conflicts || []);
    const sync = () => {
      // Unticking a "create" also unticks (and locks) every change that refers to it.
      const blocked = new Set();
      const walk = (i) => deps[i].forEach((j) => { if (!blocked.has(j)) { blocked.add(j); walk(j); } });
      checks.forEach(([i, box]) => { if (!box.checked) walk(i); });
      checks.forEach(([i, box]) => {
        box.disabled = blocked.has(i);
        if (blocked.has(i)) box.checked = false;
        box.closest(".op").classList.toggle("off", !box.checked);
      });
    };
    const ops = p.ops.map((op, i) => {
      const d = describe(op, p.ops);
      const box = pending ? el("input", { type: "checkbox", checked: true, "aria-label": d.text, onchange: sync }) : null;
      if (box) checks.push([i, box]);
      return el("li.op." + d.kind, null, box ? el("label.check", null, box, el("span.box", null, H.icon("check", 12))) : null,
        el("span.op-ic", null, H.icon(OP_ICON[d.kind], 13)),
        el("div", null, el("div.op-text", null, d.text), d.detail ? el("div.op-detail", null, d.detail) : null,
          pending && conflicts.has(i) ? el("div.op-warn", null, H.icon("alert", 12), t("conflict")) : null));
    });
    let busy = false;
    const act = async (approve, btns) => {
      if (busy) return;
      try {
        let body = {};
        if (approve) {
          const keep = checks.filter(([, b]) => b.checked).map(([i]) => i);
          if (!keep.length) return H.toast(t("select_none"), "error");
          if (keep.length !== p.ops.length) body = { ops: keep.map((i) => p.ops[i]) };
        }
        busy = true;
        btns.forEach((b) => (b.disabled = true));
        await H.api(`/api/proposals/${p.id}/${approve ? "approve" : "reject"}`, { body });
        H.toast(approve ? t("approved") : t("rejected"), approve ? "ok" : "info");
        await loadInbox();
        await H.refresh(true);
      } catch (e) { H.toast(e.message, "error"); }
      finally { busy = false; btns.forEach((b) => (b.disabled = false)); }
    };
    const btns = [];
    const reject = H.btn(t("reject"), { variant: "ghost", small: true, onclick: () => act(false, btns) });
    const approve = H.btn(p.ops.length > 1 ? t("approve_sel") : t("approve"), { icon: "check", variant: "primary", small: true, onclick: () => act(true, btns) });
    btns.push(reject, approve);
    return el("li.proposal." + p.status, null,
      el("div.p-head", null, el("span.p-src", null, H.icon(p.source.includes("PaperRead") ? "book" : p.source.includes("folder") ? "folder" : "bot", 14), p.source),
        el("time.mono.muted", { datetime: p.created }, H.when(p.created)), !pending ? el("span.pill." + p.status, null, t(p.status)) : null),
      el("h3.p-title", null, p.title),
      p.summary ? el("p.p-summary", null, p.summary) : null,
      el("details.p-ops", { open: pending && p.ops.length <= 8 ? true : null }, el("summary", null, t("changes", { n: p.ops.length })), el("ul.ops", null, ops)),
      pending ? el("div.p-actions", null, reject, approve) : null);
  }

  let inboxItems = [];
  async function loadInbox() {
    try { inboxItems = (await H.api("/api/proposals?status=" + (H.ui.inboxTab === "pending" ? "pending" : "all"))).items; }
    catch (e) { H.toast(e.message, "error"); }
    if (H.ui.layer === "inbox") drawInbox();
  }
  H.loadInbox = loadInbox;
  let inboxBody = null;
  function drawInbox() {
    if (!inboxBody) return;
    const hadFocus = inboxBody.contains(document.activeElement) || document.activeElement === document.body;
    const pending = H.ui.inboxTab === "pending";
    const list = pending ? inboxItems : inboxItems.filter((p) => p.status !== "pending");
    H.put(inboxBody, 
      el("div.seg.small", { role: "radiogroup", "aria-label": t("inbox") },
        [["pending", t("pending_tab")], ["history", t("history")]].map(([id, label]) => el("button.seg-btn", { type: "button", role: "radio", "aria-checked": String(H.ui.inboxTab === id),
          onclick: () => { H.ui.inboxTab = id; loadInbox(); } }, label))),
      el("p.hint-line", null, t("inbox_hint")),
      list.length ? el("ol.proposals", null, list.map((p) => proposalCard(p, pending))) : el("div.empty-state", null, H.icon("inbox", 22), el("p", null, t("inbox_empty"))),
      pending && list.length > 1 ? el("div.toolbar", null, el("span"), H.btn(t("approve_all"), { icon: "check", variant: "outline", small: true, onclick: async (e) => {
        const b = e.currentTarget;
        b.disabled = true;
        try {
          const out = await H.api("/api/proposals/approve-all", { body: {} });
          if (out.failed.length) H.toast(out.failed.map((f) => `#${f.id}: ${f.error}`).join("\n"), "error");
          await loadInbox(); await H.refresh(true);
        } catch (err) { H.toast(err.message, "error"); b.disabled = false; }
      } })) : null);
    if (hadFocus && !inboxBody.contains(document.activeElement)) {
      (inboxBody.querySelector(".p-actions .btn.primary") || inboxBody.closest(".drawer")?.querySelector(".layer-head .btn"))?.focus({ preventScroll: true });
    }
  }
  H.openInbox = function () {
    inboxBody = el("div.inbox");
    H.openLayer("drawer", t("inbox"), inboxBody, null, { id: "inbox", eyebrow: t("pending") + " · " + H.state.pending });
    drawInbox();
    loadInbox();
  };

  /* ================= settings ================= */
  H.openSettings = function () {
    const s = H.state.settings;
    const f = {
      project_title: H.input(s.project_title), language: H.select(H.lang, [["zh", "繁體中文"], ["en", "English"]]),
      paperread_url: H.input(s.paperread_url), paperread_library: H.input(s.paperread_library),
      reference_folders: H.textarea((s.reference_folders || []).join("\n"), { rows: 3, placeholder: "/Users/me/Zotero/storage\nD:\\Papers" }),
      watch_folders: el("input", { type: "checkbox", checked: !!s.watch_folders }),
      code_dir: H.input(s.code_dir, { placeholder: "/Users/me/thesis-analysis" }),
      allow_code_run: el("input", { type: "checkbox", checked: !!s.allow_code_run }),
      code_timeout: H.input(s.code_timeout, { type: "number", min: 10, max: 86400 }),
      openalex_mailto: H.input(s.openalex_mailto, { type: "email" }),
    };
    const toggle = (input, label) => el("label.toggle", null, input, el("span.track-t", null, el("span.knob")), el("span", null, label));
    const body = el("div.settings", null,
      el("h3.mini", null, t("s_general")),
      el("div.form-grid", null, H.field(t("s_project_title"), f.project_title), H.field(t("language"), f.language)),
      el("h3.mini", null, t("s_integrations")),
      el("div.form-grid", null, H.field(t("s_pr_url"), f.paperread_url), H.field(t("s_pr_lib"), f.paperread_library),
        el("div.span2", null, H.field(t("s_ref_folders"), f.reference_folders)), el("div.span2", null, toggle(f.watch_folders, t("s_watch"))),
        H.field(t("s_code_dir"), f.code_dir), H.field(t("s_timeout"), f.code_timeout),
        el("div.span2", null, toggle(f.allow_code_run, t("s_allow_run"))),
        el("div.span2", null, H.field(t("s_mailto"), f.openalex_mailto))),
      el("h3.mini", null, t("s_data")),
      el("div.toolbar", null,
        H.btn(t("export_json"), { icon: "download", variant: "outline", small: true, onclick: () => download("/api/export/json", "research-hub-backup.json") }),
        H.btn(t("export_bib"), { icon: "download", variant: "outline", small: true, onclick: () => H.exportBib() })));
    const save = async () => {
      const patch = {};
      for (const [k, n] of Object.entries(f)) patch[k] = n.type === "checkbox" ? n.checked : n.value;
      try {
        await H.api("/api/settings", { body: patch });
        const langChanged = patch.language !== H.lang;
        H.closeLayer();
        if (langChanged) { location.href = "/" + patch.language + "/"; return; }
        scripts = null; prStatus = null; scan = null;
        await H.refresh();
        H.toast(t("saved"), "ok");
      } catch (e) { H.toast(e.message, "error"); }
    };
    H.openLayer("drawer", t("settings"), body, [H.btn(t("cancel"), { variant: "ghost", onclick: H.closeLayer }), H.btn(t("save"), { variant: "primary", onclick: save })], { id: "settings" });
  };
  async function download(path, name) {
    try {
      const res = await fetch(path, { headers: { "X-Hub-Token": H.token } });
      if (!res.ok) throw new Error((await res.json()).error);
      const url = URL.createObjectURL(await res.blob());
      const a = el("a", { href: url, download: name }); document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (e) { H.toast(e.message, "error"); }
  }
  H.onRun = loadScripts;
})();
