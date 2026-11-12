/* Research Hub — research core: RQs, variables (X/Y/Z…), literature, matrix, model. */
(function () {
  const H = window.H;
  const { el, t } = H;

  const roleLabel = (r) => t("role_" + r);
  const evLabel = (e) => t("ev_" + (e || "mentions"));
  const paperLabel = (p) => p.title + (p.year ? ` (${p.year})` : "");
  const shortAuthors = (a) => {
    const list = (a || "").split(/\s*;\s*|\s+and\s+/).filter(Boolean);
    if (!list.length) return "";
    return list.length > 2 ? `${list[0]} et al.` : list.join(" & ");
  };

  /* ================= link picker (generic) ================= */
  function picker({ title, items, label, selected, extra, onSave }) {
    // selected: Map id -> extra value (e.g. evidence) ; extra: {options, value(id)} optional
    const state = new Map(selected);
    const search = H.input("", { placeholder: t("filter_ph"), "aria-label": t("filter_ph"), type: "search" });
    const list = el("ul.pick-list");
    const draw = () => {
      const q = search.value.trim().toLowerCase();
      H.put(list, ...items.filter((it) => !q || label(it).toLowerCase().includes(q)).map((it) => {
        const on = state.has(it.id);
        const box = el("input", { type: "checkbox", checked: on, onchange: () => { box.checked ? state.set(it.id, state.get(it.id) || extra?.default || "") : state.delete(it.id); draw(); } });
        const sel = extra && on ? H.select(state.get(it.id) || extra.default, extra.options, { "aria-label": t("evidence"), class: "sm",
          onchange: (e) => state.set(it.id, e.target.value) }) : null;
        return el("li.pick" + (on ? ".on" : ""), null, el("label.check", null, box, el("span.box", null, H.icon("check", 12))),
          el("span.pick-label", { onclick: () => box.click() }, label(it)), sel);
      }));
      if (!list.children.length) list.append(el("li.empty.sm", null, t("no_results")));
    };
    search.addEventListener("input", draw);
    draw();
    H.openLayer("modal", title, el("div.picker", null, search, list), [
      H.btn(t("cancel"), { variant: "ghost", onclick: H.closeLayer }),
      H.btn(t("save"), { variant: "primary", onclick: async () => { await onSave(state, selected); H.closeLayer(); } }),
    ], { wide: true });
  }

  async function syncLinks(link, fixedSide, fixedId, before, after, dataKey) {
    const ops = [];
    for (const id of before.keys()) if (!after.has(id)) ops.push({ op: "unlink", link, a: fixedSide === "a" ? fixedId : id, b: fixedSide === "a" ? id : fixedId });
    for (const [id, val] of after) {
      if (before.has(id) && before.get(id) === val) continue;
      ops.push({ op: "link", link, a: fixedSide === "a" ? fixedId : id, b: fixedSide === "a" ? id : fixedId, data: dataKey && val ? { [dataKey]: val } : {} });
    }
    if (ops.length) await H.ops(ops);
  }

  const evidenceOptions = H.EVIDENCE.map((e) => [e, evLabel(e)]);
  H.pickPapersForVariable = function (v) {
    const before = new Map(H.links("variable_paper", "a", v.id).map((l) => [l.paper_id, l.evidence || "mentions"]));
    picker({ title: `${t("link_papers")} · ${v.symbol}`, items: H.state.papers, label: paperLabel, selected: before,
      extra: { options: evidenceOptions, default: "supports" },
      onSave: (after) => syncLinks("variable_paper", "a", v.id, before, after, "evidence") });
  };
  H.pickVariablesForPaper = function (p) {
    const before = new Map(H.links("variable_paper", "b", p.id).map((l) => [l.variable_id, l.evidence || "mentions"]));
    picker({ title: `${t("linked_vars")} · ${p.title.slice(0, 60)}`, items: H.state.variables, label: (v) => `${v.symbol}  ${H.varName(v)} · ${roleLabel(v.role)}`,
      selected: before, extra: { options: evidenceOptions, default: "supports" },
      onSave: (after) => syncLinks("variable_paper", "b", p.id, before, after, "evidence") });
  };
  function pickVariablesForRq(rq) {
    const before = new Map(H.links("rq_variable", "a", rq.id).map((l) => [l.variable_id, ""]));
    picker({ title: `${t("linked_vars")} · ${rq.code || "RQ"}`, items: H.state.variables, label: (v) => `${v.symbol}  ${H.varName(v)} · ${roleLabel(v.role)}`,
      selected: before, onSave: (after) => syncLinks("rq_variable", "a", rq.id, before, after) });
  }
  function pickPapersForRq(rq) {
    const before = new Map(H.links("rq_paper", "a", rq.id).map((l) => [l.paper_id, ""]));
    picker({ title: `${t("link_papers")} · ${rq.code || "RQ"}`, items: H.state.papers, label: paperLabel,
      selected: before, onSave: (after) => syncLinks("rq_paper", "a", rq.id, before, after) });
  }

  /* ================= editors ================= */
  function editor(entity, item, fields, defaults, title) {
    const nodes = {};
    const grid = el("div.form-grid");
    for (const [name, kind, opts] of fields) {
      const value = item ? item[name] : (defaults || {})[name];
      let n;
      if (kind === "text") n = H.textarea(value, { rows: opts?.rows || 3 });
      else if (kind === "select") n = H.select(value ?? opts.options[0][0], opts.options);
      else if (kind === "number") n = H.input(value || "", { type: "number", min: opts?.min, max: opts?.max });
      else n = H.input(value, { placeholder: opts?.ph || "" });
      nodes[name] = n;
      grid.append(el("div" + (opts?.wide ? ".span2" : ""), null, H.field(t(opts?.label || name) + (opts?.required ? " *" : ""), n, opts?.hint)));
    }
    const save = async () => {
      const data = {};
      for (const [name, kind, opts] of fields) {
        const v = nodes[name].value;
        if (opts?.required && !String(v).trim()) { nodes[name].focus(); H.toast(t("required") + ": " + t(opts?.label || name), "error"); return; }
        data[name] = kind === "number" ? Number(v || 0) : v;
      }
      if (defaults) for (const [k, v] of Object.entries(defaults)) if (!(k in data)) data[k] = v;
      if (item) {
        // Send only what was changed here, so updates approved while the dialog was open survive.
        for (const k of Object.keys(data)) if (String(data[k] ?? "") === String(item[k] ?? "")) delete data[k];
        if (!Object.keys(data).length) { H.closeLayer(); return; }
      }
      const op = item ? { op: "update", entity, id: item.id, data } : { op: "create", entity, data };
      try { await H.ops([op], true); H.closeLayer(); H.toast(t("saved"), "ok"); } catch (e) { H.toast(e.message, "error"); }
    };
    const footer = [
      item ? H.btn(t("delete"), { icon: "trash", variant: "danger-ghost", class: "left", onclick: async () => {
        if (await H.confirm(t("confirm_delete", { name: item.title || item.symbol || item.code || item.name || "" }))) H.ops([{ op: "delete", entity, id: item.id }]);
      } }) : null,
      H.btn(t("cancel"), { variant: "ghost", onclick: H.closeLayer }),
      H.btn(t("save"), { variant: "primary", onclick: save }),
    ];
    const panel = H.openLayer("modal", title, grid, footer, { wide: true });
    panel.addEventListener("keydown", (e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") save(); });
  }

  H.editRq = (rq) => editor("rq", rq, [
    ["code", "str", { label: "rq_code", ph: "RQ" + (H.state.rqs.length + 1) }],
    ["status", "select", { options: ["draft", "refined", "answered"].map((s) => [s, t("rq_" + s)]) }],
    ["text", "text", { label: "rq_text", required: true, wide: true }],
    ["hypothesis", "text", { wide: true }],
    ["notes", "text", { wide: true }],
  ], rq ? null : { code: "RQ" + (H.state.rqs.length + 1) }, rq ? `${t("edit")} · ${rq.code || t("rq")}` : t("add_rq"));

  function nextSymbol(role) {
    const prefix = { iv: "X", dv: "Y", med: "M", mod: "Z", ctrl: "C", other: "V" }[role] || "V";
    let n = 1;
    while (H.state.variables.some((v) => v.symbol === prefix + n)) n++;
    return prefix + n;
  }
  H.editVariable = (v, role) => editor("variable", v, [
    ["symbol", "str", { required: true, ph: "X1" }],
    ["role", "select", { options: H.ROLE_ORDER.map((r) => [r, roleLabel(r)]) }],
    ["name_zh", "str"], ["name_en", "str"],
    ["definition", "text", { wide: true }],
    ["measurement", "text", { wide: true }],
    ["measure_source", "select", { label: "dz_source", options: [["", "—"], ...["self", "supervisor", "peer", "objective", "manipulated", "other"].map((x) => [x, t("src_" + x)])] }],
    ["wave", "select", { label: "dz_wave", options: [["0", "—"], ...[1, 2, 3, 4, 5, 6].map((n) => [String(n), "T" + n])] }],
    ["notes", "text", { wide: true }],
  ], v ? null : { role: role || "iv", symbol: nextSymbol(role || "iv") }, v ? `${t("edit")} · ${v.symbol}` : t("add_variable"));

  H.editPaper = (p, defaults) => editor("paper", p, [
    ["title", "str", { required: true, wide: true }],
    ["authors", "str", { wide: true, ph: "Davis, F. D. ; Venkatesh, V." }],
    ["year", "number", { min: 0, max: 3000 }], ["venue", "str"],
    ["status", "select", { options: H.PAPER_STATUS.map((s) => [s, t("ps_" + s)]) }],
    ["rating", "select", { options: [0, 1, 2, 3, 4, 5].map((n) => [String(n), n ? "★".repeat(n) : "—"]) }],
    ["doi", "str"], ["url", "str"],
    ["local_path", "str", { wide: true, ph: "/Users/me/Papers/davis1989.pdf" }],
    ["tags", "str"], ["citekey", "str"],
    ["folder", "str", { label: "paper_folder", ph: H.lang === "en" ? "e.g. Week 5 / Methods" : "例如 研究方法／第 5 週" }],
    ["abstract", "text", { wide: true, rows: 4 }],
    ["notes", "text", { wide: true, rows: 4 }],
    ...H.paperFiveCFields(),
  ], p ? null : { status: "to_read", source: "manual", ...(defaults || {}) }, p ? t("edit") : t("add_paper"));

  /* ================= chips ================= */
  function varChip(v, evidence) {
    return el("button.chip.role-" + v.role, { type: "button", title: `${H.varName(v)} · ${roleLabel(v.role)}${evidence ? " · " + evLabel(evidence) : ""}`,
      onclick: () => H.editVariable(v) }, el("b", null, v.symbol), H.varName(v) ? el("span", null, H.varName(v)) : null,
      evidence ? el("i.ev." + evidence, null, evLabel(evidence)) : null);
  }
  function paperChip(p, evidence) {
    return el("button.chip.paper", { type: "button", title: paperLabel(p), onclick: () => H.editPaper(p) },
      H.icon("file", 13), el("span", null, (shortAuthors(p.authors) || p.title.slice(0, 32)) + (p.year ? ` ${p.year}` : "")),
      evidence ? el("i.ev." + evidence, null, evLabel(evidence)) : null);
  }

  /* ================= RQs ================= */
  function rqView() {
    const rqs = H.state.rqs;
    const add = H.btn(t("add_rq"), { icon: "plus", variant: "primary", onclick: () => H.editRq(null) });
    if (!rqs.length) return el("div", null, el("div.toolbar", null, el("span"), add), el("div.empty-state", null, H.icon("flag", 22), el("p", null, t("rq_empty"))));
    return el("div", null, el("div.toolbar", null, el("span.mono.muted", null, `${rqs.length} RQ`), add),
      el("ol.rq-list", null, rqs.map((rq) => {
        const vars = H.links("rq_variable", "a", rq.id).map((l) => H.by(H.state.variables, l.variable_id)).filter(Boolean);
        const papers = H.links("rq_paper", "a", rq.id).map((l) => H.by(H.state.papers, l.paper_id)).filter(Boolean);
        return el("li.rq-card", null,
          el("div.rq-top", null, el("span.rq-code.mono", null, rq.code || "RQ"), el("span.pill.rq-" + rq.status, null, t("rq_" + rq.status)),
            H.btn(t("edit"), { icon: "edit", iconOnly: true, small: true, variant: "ghost", class: "push", onclick: () => H.editRq(rq) })),
          el("p.rq-text", null, rq.text),
          rq.hypothesis ? el("p.rq-hyp", null, el("span.mono", null, "H · "), rq.hypothesis) : null,
          el("div.rq-links", null,
            el("div", null, el("span.lbl", null, t("linked_vars")), el("div.chips", null, vars.map((v) => varChip(v)),
              H.btn(t("edit"), { icon: "link", small: true, variant: "ghost", onclick: () => pickVariablesForRq(rq) }))),
            el("div", null, el("span.lbl", null, t("linked_papers")), el("div.chips", null, papers.map((p) => paperChip(p)),
              H.btn(t("edit"), { icon: "link", small: true, variant: "ghost", onclick: () => pickPapersForRq(rq) })))));
      })));
  }

  /* ================= Variables ================= */
  function variablesView() {
    const vars = H.state.variables;
    const add = H.btn(t("add_variable"), { icon: "plus", variant: "primary", onclick: () => H.editVariable(null) });
    if (!vars.length) return el("div", null, el("div.toolbar", null, el("span"), add), el("div.empty-state", null, H.icon("layers", 22), el("p", null, t("var_empty"))));
    const unsupported = vars.filter((v) => !H.links("variable_paper", "a", v.id).length).length;
    const groups = H.ROLE_ORDER.map((role) => [role, vars.filter((v) => v.role === role)]).filter(([, list]) => list.length);
    return el("div", null,
      el("div.toolbar", null,
        el("div.summary-chips", null, groups.map(([role, list]) => el("span.pill.role-" + role, null, `${roleLabel(role)} · ${list.length}`)),
          unsupported ? el("span.pill.warn", null, H.icon("alert", 13), t("unsupported", { n: unsupported })) : null),
        add),
      el("div.var-groups", null, groups.map(([role, list]) => el("div.var-group", null,
        el("div.group-head", null, el("span.role-dot.role-" + role), el("h4", null, roleLabel(role)),
          H.btn(t("add"), { icon: "plus", small: true, variant: "ghost", onclick: () => H.editVariable(null, role) })),
        el("div.var-grid", null, list.map((v) => {
          const links = H.links("variable_paper", "a", v.id);
          return el("article.var-card.role-" + v.role + (links.length ? "" : ".bare"), null,
            el("div.var-top", null, el("span.var-sym", null, v.symbol),
              el("div.var-names", null, el("strong", null, H.varName(v) || "—"), el("span.muted", null, H.lang === "en" ? v.name_zh : v.name_en)),
              H.btn(t("edit"), { icon: "edit", iconOnly: true, small: true, variant: "ghost", class: "push", onclick: () => H.editVariable(v) })),
            v.definition ? el("p.var-def", null, v.definition) : null,
            v.measurement ? el("p.var-meas", null, el("span.lbl", null, t("measurement")), v.measurement) : null,
            el("div.var-papers", null,
              el("div.lbl-row", null, el("span.lbl", null, `${t("linked_papers")} · ${links.length}`),
                H.btn(t("link_papers"), { icon: "link", small: true, variant: "ghost", onclick: () => H.pickPapersForVariable(v) })),
              links.length ? el("div.chips", null, links.map((l) => { const p = H.by(H.state.papers, l.paper_id); return p ? paperChip(p, l.evidence) : null; }))
                : el("p.bare-note", null, H.icon("alert", 13), t("no_papers_linked"))));
        }))))));
  }

  /* ================= Literature ================= */
  let searchResults = null, searchBusy = false, searchQuery = "", searchYear = "", searchProvider = "openalex";
  function openalexPanel() {
    const q = H.input(searchQuery, { placeholder: t("search_ph"), "aria-label": t("search_ph"), type: "search" });
    const y = H.input(searchYear, { type: "number", placeholder: t("year_from"), "aria-label": t("year_from"), class: "year", min: 1900, max: 2100 });
    const go = async (e) => {
      e?.preventDefault();
      searchQuery = q.value.trim(); searchYear = y.value;
      if (!searchQuery) return;
      searchBusy = true; H.render.core();
      try { searchResults = (await H.api(`/api/search?provider=${searchProvider}&q=${encodeURIComponent(searchQuery)}&year_from=${encodeURIComponent(searchYear || "")}`)).results; H.loadUsage && H.loadUsage(); }
      catch (err) { searchResults = null; H.toast(err.message, "error"); }
      searchBusy = false; H.render.core();
      document.querySelector(".oa-form input")?.focus();
    };
    const known = new Set(H.state.papers.map((p) => (p.doi || "").toLowerCase()).filter(Boolean));
    const knownOa = new Set(H.state.papers.map((p) => p.openalex_id).filter(Boolean));
    return el("div.oa", null,
      el("form.oa-form", { onsubmit: go }, H.icon("search", 16), q, y,
        H.select(searchProvider, [["openalex", "OpenAlex"], ["wiley", "Wiley"], ["semantic", "Semantic Scholar"],
          ...(H.state.settings.wos_api_key_set ? [["wos", "Web of Science"]] : [])], { class: "sm prov-sel", "aria-label": t("source"), onchange: (e) => { searchProvider = e.target.value; } }),
        H.btn(searchBusy ? t("searching") : t("search"), { type: "submit", variant: "primary", small: true, disabled: searchBusy })),
      searchResults ? el("ul.oa-results", null, searchResults.length ? searchResults.map((r) => {
        const have = (r.doi && known.has(r.doi.toLowerCase())) || (r.openalex_id && knownOa.has(r.openalex_id));
        return el("li.oa-item", null,
          el("div.oa-main", null, el("a.oa-title", { href: H.safeUrl(r.url) || "#", target: "_blank", rel: "noopener noreferrer" }, r.title),
            el("div.meta", null, [shortAuthors(r.authors), r.year, r.venue].filter(Boolean).join(" · "),
              r.cited_by ? el("span.mono.muted", null, " · " + t("cited_by", { n: r.cited_by })) : null)),
          H.btn(have ? t("added") : t("add_to_library"), { icon: have ? "check" : "plus", small: true, variant: have ? "ghost" : "outline", disabled: have,
            onclick: () => H.ops([{ op: "create", entity: "paper", data: { title: r.title, authors: r.authors, year: r.year, venue: r.venue, doi: r.doi, url: r.url,
              abstract: r.abstract, openalex_id: r.openalex_id || "", source: r.provider || "openalex", status: "candidate" } }]) }));
      }) : el("li.empty.sm", null, t("no_results")))
        : null);
  }

  function literatureView(scope = "core") {
    const papers = H.state.papers;
    const filter = H.input(H.ui.litFilter, { type: "search", placeholder: t("filter_ph"), "aria-label": t("filter_ph"), class: "filter", dataset: { fkey: "lit-filter-" + scope } });
    const redraw = H.debounce(() => drawTable(), 150);
    filter.addEventListener("input", () => { H.ui.litFilter = filter.value; redraw(); });
    const statusChips = el("div.seg.small", { role: "radiogroup", "aria-label": t("status") }, ["all", ...H.PAPER_STATUS].map((s) => {
      const n = s === "all" ? papers.length : papers.filter((p) => p.status === s).length;
      return el("button.seg-btn", { type: "button", role: "radio", "aria-checked": String(H.ui.litStatus === s), onclick: () => { H.ui.litStatus = s; H.render.core(); } },
        s === "all" ? t("all") : t("ps_" + s), el("span.count", null, String(n)));
    }));
    const bibInput = el("input", { type: "file", accept: ".bib,.ris,.txt", hidden: true, onchange: async () => {
      const f = bibInput.files[0]; if (!f) return;
      try { const out = await H.api("/api/import/bibtex", { body: await f.text(), headers: { "Content-Type": "text/plain" } }); H.toast(t("imported", { n: out.imported }) + (out.skipped ? " · " + t("dup_skipped", { n: out.skipped }) : ""), "ok"); await H.refresh(true); }
      catch (e) { H.toast(e.message, "error"); }
      bibInput.value = "";
    } });
    const table = el("div.lit-table");
    const drawTable = () => {
      const q = H.ui.litFilter.trim().toLowerCase();
      const rows = papers.filter((p) => (H.ui.litStatus === "all" || p.status === H.ui.litStatus) &&
        (!q || [p.title, p.authors, p.tags, p.venue, p.notes, String(p.year)].join(" ").toLowerCase().includes(q)));
      if (!papers.length) { H.put(table, el("div.empty-state", null, H.icon("book", 22), el("p", null, t("lit_empty")))); return; }
      if (!rows.length) { H.put(table, el("p.empty", null, t("no_results"))); return; }
      H.put(table, H.ui.litView === "5c" ? H.fiveCCompare(rows) : el("ul.papers", null, rows.map((p) => paperRow(p, scope))));
    };
    drawTable();
    return el("div", null,
      el("div.toolbar.wrap", null, filter, statusChips,
        el("div.seg.small", { role: "radiogroup", "aria-label": t("st_view") }, [["list", t("st_view_list")], ["5c", t("st_view_5c")]].map(([v, l]) =>
          el("button.seg-btn", { type: "button", role: "radio", "aria-checked": String((H.ui.litView || "list") === v), onclick: () => { H.ui.litView = v; H.render.core(); H.render.pipeline(); } }, l))),
        el("div.tool-group", null,
          H.btn(t("import_bib"), { icon: "upload", variant: "ghost", small: true, onclick: () => bibInput.click() }), bibInput,
          H.btn(t("export_bib"), { icon: "download", variant: "ghost", small: true, onclick: () => exportBib() }),
          H.btn(t("add_paper"), { icon: "plus", variant: "primary", small: true, onclick: () => H.editPaper(null) }))),
      el("details.oa-wrap", { open: !!searchResults || searchBusy || null }, el("summary", null, H.icon("search", 15), t("search_openalex"), el("span.mono.muted", null, "OpenAlex · Wiley · Semantic Scholar · WoS")), openalexPanel()),
      table);
  }

  async function exportBib() {
    try {
      const res = await fetch("/api/export/bibtex", { headers: { "X-Hub-Token": H.token } });
      if (!res.ok) throw new Error((await res.json()).error);
      const url = URL.createObjectURL(await res.blob());
      const a = el("a", { href: url, download: "references.bib" }); document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } catch (e) { H.toast(e.message, "error"); }
  }
  H.exportBib = exportBib;

  function paperRow(p, scope) {
    const vlinks = H.links("variable_paper", "b", p.id);
    const status = H.select(p.status, H.PAPER_STATUS.map((s) => [s, t("ps_" + s)]), { class: "sm status-sel ps-" + p.status, "aria-label": t("status"), dataset: { fkey: `paper-st-${p.id}-${scope}` },
      onchange: (e) => H.ops([{ op: "update", entity: "paper", id: p.id, data: { status: e.target.value } }]) });
    return el("li.paper" + (p.status === "excluded" ? ".excluded" : ""), null,
      el("div.paper-main", null,
        el("button.paper-title", { type: "button", onclick: () => H.editPaper(p) }, p.title),
        el("div.meta", null, [shortAuthors(p.authors), p.year || null, p.venue].filter(Boolean).join(" · "), H.fiveCDots(p),
          p.story_role ? el("span.pill.tiny", { title: t("st_role") }, (H.FIVE_C.find((c) => c.key === p.story_role) || {}).mark + " " + t("c5_" + p.story_role + "_short")) : null,
          p.rating ? el("span.stars", { "aria-label": p.rating + "/5" }, "★".repeat(p.rating)) : null,
          p.source && p.source !== "manual" ? el("span.src.mono", null, p.source.split(":")[0]) : null),
        el("div.chips", null, vlinks.map((l) => { const v = H.by(H.state.variables, l.variable_id); return v ? varChip(v, l.evidence) : null; }),
          H.state.variables.length ? H.btn(t("linked_vars"), { icon: "link", small: true, variant: "ghost", onclick: () => H.pickVariablesForPaper(p) }) : null)),
      el("div.paper-side", null, status,
        el("div.icon-row", null,
          p.local_path ? H.btn(t("open_pdf"), { icon: "file", iconOnly: true, small: true, variant: "ghost", onclick: () => H.openLocal(p.local_path) }) : null,
          (() => { const href = p.doi ? `https://doi.org/${encodeURI(p.doi.replace(/^https?:\/\/(dx\.)?doi\.org\//i, ""))}` : H.safeUrl(p.url);
            return href ? el("a.btn.ghost.icon-only.sm", { href, target: "_blank", rel: "noopener noreferrer", title: p.doi || p.url, "aria-label": p.doi ? "DOI" : "URL" }, H.icon("external", 16)) : null; })(),
          H.btn(t("edit"), { icon: "edit", iconOnly: true, small: true, variant: "ghost", onclick: () => H.editPaper(p) }))));
  }

  /* ================= Matrix ================= */
  function matrixView() {
    const vars = [...H.state.variables].sort((a, b) => H.ROLE_ORDER.indexOf(a.role) - H.ROLE_ORDER.indexOf(b.role));
    const papers = H.state.papers.filter((p) => p.status !== "excluded");
    if (!vars.length || !papers.length) return el("div.empty-state", null, H.icon("grid", 22), el("p", null, t("matrix_empty")));
    const map = new Map(H.state.variable_papers.map((l) => [l.variable_id + ":" + l.paper_id, l.evidence || "mentions"]));
    const cycle = ["", ...H.EVIDENCE];
    const cell = (v, p) => {
      const ev = map.get(v.id + ":" + p.id) || "";
      return el("td", null, el("button.cell" + (ev ? "." + ev : ""), { dataset: { fkey: `cell-${v.id}-${p.id}` },
        type: "button", "aria-label": `${v.symbol} × ${p.title}: ${ev ? evLabel(ev) : t("unlinked")}`, title: ev ? evLabel(ev) : t("unlinked"),
        onclick: () => {
          const next = cycle[(cycle.indexOf(ev) + 1) % cycle.length];
          H.ops([next ? { op: "link", link: "variable_paper", a: v.id, b: p.id, data: { evidence: next } } : { op: "unlink", link: "variable_paper", a: v.id, b: p.id }]);
        },
      }, ev ? evLabel(ev).slice(0, H.lang === "en" ? 3 : 2) : ""));
    };
    return el("div", null,
      el("p.hint-line", null, t("matrix_hint")),
      el("div.matrix-wrap", null, el("table.matrix", null,
        el("thead", null, el("tr", null, el("th.corner", { scope: "col" }, t("papers") + " ╲ " + t("variables")),
          vars.map((v) => el("th.vh.role-" + v.role, { scope: "col", title: H.varName(v) }, el("span", null, v.symbol))))),
        el("tbody", null, papers.map((p) => el("tr", null,
          el("th.ph", { scope: "row" }, el("button.linkish", { type: "button", onclick: () => H.editPaper(p), title: p.title }, (shortAuthors(p.authors) || p.title.slice(0, 40)) + (p.year ? ` ${p.year}` : ""))),
          vars.map((v) => cell(v, p))))),
        el("tfoot", null, el("tr", null, el("th", { scope: "row" }, "Σ"),
          vars.map((v) => { const n = H.links("variable_paper", "a", v.id).length; return el("td.sum" + (n ? "" : ".zero"), null, String(n)); }))))),
      el("div.legend", null, H.EVIDENCE.map((e) => el("span.legend-item", null, el("i.sw." + e), evLabel(e)))));
  }

  /* ================= Model (SVG) ================= */
  /* Role-based sketch used until explicit hypothesis paths exist. */
  function roleModelSvg() {
    const vars = H.state.variables;
    const by = (r) => vars.filter((v) => v.role === r);
    const X = by("iv"), Y = by("dv"), M = by("med"), Z = by("mod"), C = by("ctrl");
    if (!X.length || !Y.length) return null;
    const ns = "http://www.w3.org/2000/svg";
    const mk = (tag, attrs, text) => { const n = document.createElementNS(ns, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); if (text != null) n.textContent = text; return n; };
    const W = 960, boxW = 200, boxH = 56, gap = 18;
    const colH = (n) => n * boxH + (n - 1) * gap;
    const topPad = Z.length ? 120 : 40;
    const bodyH = Math.max(colH(X.length), colH(Y.length), M.length ? colH(M.length) : 0, 120);
    const H_ = topPad + bodyH + (C.length ? 120 : 40);
    const svg = mk("svg", { viewBox: `0 0 ${W} ${H_}`, class: "model", role: "img", "aria-label": t("tab_model") });
    const defs = mk("defs", {});
    const marker = mk("marker", { id: "arrow", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" });
    marker.append(mk("path", { d: "M0 0 L10 5 L0 10 z", class: "arrowhead" }));
    defs.append(marker); svg.append(defs);
    const pos = new Map();
    const place = (list, x, role) => {
      const total = colH(list.length);
      list.forEach((v, i) => pos.set(v.id, { x, y: topPad + (bodyH - total) / 2 + i * (boxH + gap), role }));
    };
    const xCol = 40, yCol = W - 40 - boxW, mCol = (W - boxW) / 2;
    place(X, xCol, "iv"); place(Y, yCol, "dv"); if (M.length) place(M, mCol, "med");
    const edges = mk("g", { class: "edges" });
    const line = (x1, y1, x2, y2, cls) => edges.append(mk("path", { d: `M${x1} ${y1} C ${(x1 + x2) / 2} ${y1}, ${(x1 + x2) / 2} ${y2}, ${x2} ${y2}`, class: "edge " + (cls || ""), "marker-end": "url(#arrow)" }));
    const mid = (id) => { const p = pos.get(id); return { l: p.x, r: p.x + boxW, cy: p.y + boxH / 2, cx: p.x + boxW / 2, t: p.y, b: p.y + boxH }; };
    const linkedRq = new Set(H.state.rq_variables.map((l) => l.variable_id));
    // Direct X→Y paths. With mediators they detour below the mediator column (c′ path).
    const mBottom = M.length ? Math.max(...M.map((m) => mid(m.id).b)) : 0;
    for (const x of X) for (const y of Y) {
      const a = mid(x.id), b = mid(y.id);
      if (!M.length) { line(a.r, a.cy, b.l, b.cy, ""); continue; }
      const dip = mBottom + 26;
      edges.append(mk("path", { d: `M${a.r} ${a.cy} C ${mCol - 20} ${dip}, ${mCol + boxW + 20} ${dip}, ${b.l} ${b.cy}`, class: "edge direct", "marker-end": "url(#arrow)" }));
    }
    for (const m of M) {
      const c = mid(m.id);
      for (const x of X) { const a = mid(x.id); line(a.r, a.cy, c.l, c.cy, "med"); }
      for (const y of Y) { const b = mid(y.id); line(c.r, c.cy, b.l, b.cy, "med"); }
    }
    // moderators: boxes on top, arrow down onto the middle of the X→Y corridor
    const zW = 180;
    Z.forEach((z, i) => {
      const x = W / 2 - (Z.length * (zW + gap) - gap) / 2 + i * (zW + gap);
      pos.set(z.id, { x, y: 30, role: "mod", w: zW });
      edges.append(mk("path", { d: `M${x + zW / 2} ${30 + boxH} L ${x + zW / 2} ${topPad + bodyH / 2 - (M.length ? boxH / 2 + 10 : 4)}`, class: "edge mod", "marker-end": "url(#arrow)" }));
    });
    C.forEach((c, i) => {
      const x = W / 2 - (C.length * (zW + gap) - gap) / 2 + i * (zW + gap);
      pos.set(c.id, { x, y: topPad + bodyH + 50, role: "ctrl", w: zW });
      edges.append(mk("path", { d: `M${x + zW / 2} ${topPad + bodyH + 50} L ${x + zW / 2} ${topPad + bodyH / 2 + (M.length ? boxH / 2 + 10 : 4)}`, class: "edge ctrl", "marker-end": "url(#arrow)" }));
    });
    svg.append(edges);
    const nodes = mk("g", { class: "nodes" });
    for (const v of vars) {
      const p = pos.get(v.id);
      if (!p) continue;
      const w = p.w || boxW;
      const n = H.links("variable_paper", "a", v.id).length;
      const g = mk("g", { class: "mnode role-" + v.role + (n ? "" : " bare"), tabindex: 0, role: "button", "aria-label": `${v.symbol} ${H.varName(v)}` });
      g.append(mk("rect", { x: p.x, y: p.y, width: w, height: boxH, rx: 12 }));
      g.append(mk("text", { x: p.x + 14, y: p.y + 23, class: "sym" }, v.symbol + (linkedRq.has(v.id) ? " ·RQ" : "")));
      const name = H.varName(v) || "";
      g.append(mk("text", { x: p.x + 14, y: p.y + 42, class: "nm" }, name.length > 16 ? name.slice(0, 15) + "…" : name));
      const badge = mk("g", { class: "badge" });
      badge.append(mk("rect", { x: p.x + w - 40, y: p.y + 10, width: 28, height: 18, rx: 9 }));
      badge.append(mk("text", { x: p.x + w - 26, y: p.y + 23, "text-anchor": "middle" }, String(n)));
      g.append(badge);
      g.addEventListener("click", () => H.editVariable(v));
      g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); H.editVariable(v); } });
      nodes.append(g);
    }
    svg.append(nodes);
    return svg;
  }

  function modelView() {
    const rels = H.state.relations || [];
    const svg = rels.length ? H.pathModelSvg(H.state.variables, rels, { interactive: true }) : roleModelSvg();
    const tools = el("div.toolbar.wrap", null,
      el("p.hint-line.grow", null, rels.length ? t("model_hint_paths") : t("model_hint")),
      el("div.tool-group", null,
        H.btn(t("fw_from_text"), { icon: "sparkle", variant: "primary", small: true, onclick: () => H.openFramework() }),
        H.btn(t("pm_button"), { icon: "grid", variant: "outline", small: true, onclick: () => H.openProcessModels() }),
        H.btn(t("fw_add_rel"), { icon: "plus", variant: "ghost", small: true, disabled: H.state.variables.length < 2, onclick: () => H.editRelation(null) }),
        // the download is a clean figure for the thesis: no paper-count badges or RQ markers
        svg ? H.btn(t("fw_download"), { icon: "download", variant: "ghost", small: true, onclick: () =>
          H.downloadSvg(rels.length ? H.pathModelSvg(H.state.variables, rels, { idSuffix: "-dl" }) : svg, "research-model.svg") }) : null));
    if (!svg) return el("div", null, tools, el("div.empty-state", null, H.icon("layers", 22), el("p", null, t("model_empty_text")),
      el("div.toolbar", null, H.btn(t("fw_from_text"), { icon: "sparkle", variant: "primary", onclick: () => H.openFramework() }),
        H.btn(t("pm_button"), { icon: "grid", variant: "outline", onclick: () => H.openProcessModels() }),
        H.btn(t("add_variable"), { icon: "plus", variant: "ghost", onclick: () => H.editVariable(null, "iv") }))));
    return el("div", null, tools, el("div.model-wrap", null, svg),
      el("div.legend", null, ["iv", "med", "mod", "dv", "ctrl"].map((r) => el("span.legend-item", null, el("i.sw.role-" + r), roleLabel(r))),
        rels.length ? [el("span.legend-item", null, el("i.ln.pos"), t("fw_sign_pos")), el("span.legend-item", null, el("i.ln.neg"), t("fw_sign_neg")),
          el("span.legend-item", null, el("i.ln.modl"), t("fw_kind_moderates"))] : null),
      rels.length ? H.relationList() : null);
  }

  /* ================= section + modules ================= */
  const TABS = [["story", "tab_story", () => H.storyView()], ["rq", "tab_rq", rqView], ["variables", "tab_vars", variablesView], ["literature", "tab_lit", literatureView],
    ["matrix", "tab_matrix", matrixView], ["model", "tab_model", modelView], ["design", "tab_design", () => H.designView()]];

  H.CORE_TABS = TABS.map(([id, label]) => [id, label]);
  H.render = H.render || {};
  H.render.core = function () {
    const root = document.getElementById("core");
    const s = H.state;
    const counts = { rq: s.rqs.length, variables: s.variables.length, literature: s.papers.length };
    const tabs = el("div.tabs", { role: "tablist", "aria-label": t("core") }, TABS.map(([id, label]) =>
      el("button.tab", { type: "button", role: "tab", id: "tab-" + id, "aria-selected": String(H.ui.coreTab === id), "aria-controls": "core-panel",
        tabindex: H.ui.coreTab === id ? 0 : -1,
        onclick: () => { H.ui.coreTab = id; H.render.core(); document.getElementById("tab-" + id)?.focus(); },
        onkeydown: (e) => {
          if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
          const i = TABS.findIndex((x) => x[0] === H.ui.coreTab) + (e.key === "ArrowRight" ? 1 : -1);
          const next = TABS[(i + TABS.length) % TABS.length][0];
          H.ui.coreTab = next; H.render.core(); document.getElementById("tab-" + next)?.focus();
        } }, t(label), counts[id] != null ? el("span.count", null, String(counts[id])) : null)));
    const view = TABS.find((x) => x[0] === H.ui.coreTab)[2]();
    H.put(root, 
      el("div.band-head", null, el("div", null, el("div.eyebrow", null, "02", el("span", null, "/"), t("core")), el("h2", null, t("core")), el("p.sub", null, t("core_hint")))),
      el("div.panel", null, tabs, el("div.tab-panel", { id: "core-panel", role: "tabpanel", "aria-labelledby": "tab-" + H.ui.coreTab }, view)));
  };

  /* Stage modules reuse the same views inside a stage's workspace. */
  H.renderModule = function (module) {
    if (module === "literature") return literatureView("stage");
    if (module === "rq") return rqView();
    if (module === "variables") return el("div.module-stack", null, variablesView(), modelView());
    if (module === "code") return H.codeCard ? H.codeCard() : null;
    if (module === "writing") return el("div.card", null, el("p", null, t("writing_hint")),
      el("div.toolbar", null, H.btn(t("export_bib"), { icon: "download", variant: "primary", onclick: exportBib }),
        H.btn(t("sl_hero"), { icon: "layers", variant: "outline", onclick: () => H.openSlides() }),
        el("span.mono.muted", null, `${H.state.papers.filter((p) => p.status !== "excluded").length} ${t("papers")}`)));
    return null;
  };
})();
