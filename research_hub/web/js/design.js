/* Research Hub — research-design check, after Bono & McNamara (2011), "Publishing in AMJ —
   Part 2: Research design": the five questions to think through before collecting data, the four
   conditions for a causal claim, control-variable judgments (Becker, 2005) and common method variance. */
(function () {
  const H = window.H;
  const { el, t } = H;

  const SOURCES = ["self", "supervisor", "peer", "objective", "manipulated", "other"];
  const nameOf = (v) => `${v.symbol}${(H.varName ? H.varName(v) : v.name_zh || v.name_en) ? " " + (H.varName ? H.varName(v) : v.name_zh || v.name_en) : ""}`;
  const list = (vs) => vs.map((v) => v.symbol).join("、");

  /**
   * Pure analysis of the design profile + variables + paths. Returns
   * { questions: {1..5: [{level, text}]}, causal: [{key, level, text}] } where level is ok | issue | info.
   */
  H.designFindings = function (state) {
    const d = state.design || {};
    const vars = state.variables || [];
    const rels = state.relations || [];
    const by = (r) => vars.filter((v) => v.role === r);
    const X = by("iv"), M = by("med"), Y = by("dv"), C = by("ctrl");
    const q = { 1: [], 2: [], 3: [], 4: [], 5: [] };
    const add = (n, level, key, vars_) => q[n].push({ level, text: t(key, vars_) });
    const cross = d.design === "cross_sectional";

    // Q1 — research question vs. time and causal logic of the data
    if (!d.purpose || !d.design) add(1, "info", "dz_set_design");
    if ((d.purpose === "causal" || d.purpose === "change") && cross) add(1, "issue", "dz_cross_causal");
    if (d.design === "longitudinal" && d.waves && d.waves < 2) add(1, "issue", "dz_waves");
    const order = [];
    for (const x of [...X, ...M]) for (const y of Y) if (x.wave && y.wave && x.wave >= y.wave) order.push(`${x.symbol}(T${x.wave}) → ${y.symbol}(T${y.wave})`);
    if (order.length && d.purpose !== "describe") add(1, "issue", "dz_order", { pairs: order.slice(0, 4).join("、") });

    // Q2 — sample and procedure
    if (!(d.sample || "").trim()) add(2, "info", "dz_sample");
    if (d.design === "experiment" && !vars.some((v) => v.measure_source === "manipulated")) add(2, "info", "dz_manip");

    // Q3 — constructs and measurement validity
    const core = vars.filter((v) => v.role !== "ctrl");
    const noDef = core.filter((v) => !(v.definition || "").trim());
    const noMeas = vars.filter((v) => !(v.measurement || "").trim());
    if (noDef.length) add(3, "issue", "dz_no_def", { vars: list(noDef) });
    if (noMeas.length) add(3, "issue", "dz_no_meas", { vars: list(noMeas) });
    const perceptual = (v) => v.measure_source && !["objective", "manipulated"].includes(v.measure_source);
    const sameTime = (a, b) => (a.wave && b.wave ? a.wave === b.wave : cross || d.waves === 1);
    const cmv = [];
    for (const x of [...X, ...M]) for (const y of Y) if (perceptual(x) && x.measure_source === y.measure_source && sameTime(x, y)) cmv.push(`${x.symbol}–${y.symbol}`);
    if (cmv.length) add(3, "issue", "dz_cmv", { pairs: cmv.slice(0, 4).join("、") });
    else if ([...X, ...Y].some((v) => !v.measure_source)) add(3, "info", "dz_cmv_unknown");

    // Q4 — controls and mediating mechanisms grounded in theory
    if (!C.length) add(4, "info", "dz_no_ctrl");
    const failing = C.filter((v) => !(v.ctrl_y && v.ctrl_x && v.ctrl_not_core));
    if (failing.length) add(4, "issue", "dz_ctrl_fail", { vars: list(failing) });
    const noWhy = C.filter((v) => !(v.rationale || "").trim());
    if (noWhy.length) add(4, "info", "dz_ctrl_why", { vars: list(noWhy) });
    if (M.length && (cross || (M.every((m) => m.wave) && new Set([...X, ...M, ...Y].map((v) => v.wave)).size === 1))) add(4, "issue", "dz_med_cross");
    if (M.length === 1) add(4, "info", "dz_med_single");

    // Q5 — honest limitations, other studies where needed
    const problems = [1, 2, 3, 4].some((n) => q[n].some((f) => f.level === "issue"));
    if (!(d.limitations || "").trim()) add(5, problems ? "issue" : "info", problems ? "dz_limits_needed" : "dz_limits");

    // the four conditions for a causal claim (class whiteboard)
    const effectToY = rels.some((r) => r.kind !== "moderates" && Y.some((y) => y.id === r.target_id));
    const causal = [
      { key: "cz_related", level: effectToY || (X.length && Y.length) ? "ok" : "info" },
      { key: "cz_order", level: d.design === "experiment" || (d.design === "longitudinal" && !order.length && X.some((x) => x.wave) && Y.some((y) => y.wave)) ? "ok"
        : cross || order.length ? "issue" : "info" },
      { key: "cz_alt", level: d.design === "experiment" || (C.length && !failing.length) ? "ok" : failing.length ? "issue" : "info" },
      { key: "cz_mech", level: M.length ? (cross ? "issue" : "ok") : "info" },
    ];
    return { questions: q, causal };
  };

  /* ---------- view ---------- */
  const LEVEL_ICON = { ok: "check", issue: "alert", info: "sparkle" };
  H.designView = function () {
    const s = H.state, d = s.design || {};
    if (!d.id) return el("p.empty", null, "…");
    const upd = (data) => H.ops([{ op: "update", entity: "design", id: d.id, data }]);
    const f = H.designFindings(s);
    const seg = (field, options, label) => el("div.seg.small", { role: "radiogroup", "aria-label": label }, options.map(([v, l]) =>
      el("button.seg-btn", { type: "button", role: "radio", "aria-checked": String((d[field] || "") === v), dataset: { fkey: `dz-${field}-${v}` },
        onclick: () => upd({ [field]: v }) }, l)));
    const saveState = el("span.save-state.mono", { "aria-live": "polite" });
    const sample = H.autosave(H.textarea(d.sample, { rows: 3, placeholder: t("dz_sample_ph") }), "design", d.id, "sample", saveState);
    const limits = H.autosave(H.textarea(d.limitations, { rows: 3, placeholder: t("dz_limits_ph") }), "design", d.id, "limitations", saveState);
    const waves = el("input.inp.sm", { type: "number", min: 0, max: 20, value: d.waves || "", "aria-label": t("dz_waves_label"), dataset: { fkey: "dz-waves" },
      onchange: (e) => upd({ waves: Number(e.target.value || 0) }) });

    const profile = el("div.card", null, el("div.card-head", null, el("h4", null, t("dz_profile")), saveState),
      el("div.dz-grid", null,
        el("div", null, el("span.lbl", null, t("dz_purpose")), seg("purpose", [["describe", t("dz_p_describe")], ["change", t("dz_p_change")], ["causal", t("dz_p_causal")]], t("dz_purpose"))),
        el("div", null, el("span.lbl", null, t("dz_design")), seg("design", [["cross_sectional", t("dz_d_cross")], ["longitudinal", t("dz_d_long")], ["experiment", t("dz_d_exp")]], t("dz_design"))),
        el("label.dz-waves", null, el("span.lbl", null, t("dz_waves_label")), waves)),
      el("div.form-grid", null, H.field(t("dz_sample_label"), sample), H.field(t("dz_limits_label"), limits)));

    const causal = el("div.card", null, el("div.card-head", null, el("h4", null, t("cz_title")), el("span.mono.muted", null, t("cz_note"))),
      el("ol.cz-list", null, f.causal.map((c, i) => el("li.cz." + c.level, null, el("span.cz-n.mono", null, String(i + 1)),
        el("div", null, el("strong", null, t(c.key)), el("p", null, t(c.key + "_" + c.level))), el("span.cz-ic", null, H.icon(LEVEL_ICON[c.level], 14))))));

    const questions = el("ol.dz-qs", null, [1, 2, 3, 4, 5].map((n) => {
      const status = d[`q${n}_status`] || "";
      const note = H.textarea(d[`q${n}_note`], { rows: 2, placeholder: t("dz_note_ph"), "aria-label": t("notes") });
      H.autosave(note, "design", d.id, `q${n}_note`, saveState);
      const auto = f.questions[n];
      return el("li.dz-q" + (status ? "." + status : ""), null,
        el("div.dz-q-head", null, el("span.dz-num.mono", null, String(n)), el("h4", null, t("dz_q" + n)),
          el("div.seg.small.push", { role: "radiogroup", "aria-label": t("status") }, [["", t("dz_s_open")], ["ok", t("dz_s_ok")], ["issue", t("dz_s_issue")]].map(([v, l]) =>
            el("button.seg-btn", { type: "button", role: "radio", "aria-checked": String(status === v), dataset: { fkey: `dz-q${n}-${v || "open"}` },
              onclick: () => upd({ [`q${n}_status`]: v }) }, l)))),
        el("p.dz-q-hint", null, t("dz_q" + n + "_hint")),
        auto.length ? el("ul.dz-auto", null, auto.map((a) => el("li." + a.level, null, H.icon(LEVEL_ICON[a.level], 13), a.text)))
          : el("p.dz-clear", null, H.icon("check", 13), t("dz_clear")),
        note);
    }));

    const srcOpts = [["", "—"], ...SOURCES.map((x) => [x, t("src_" + x)])];
    const varRows = [...s.variables].sort((a, b) => H.ROLE_ORDER.indexOf(a.role) - H.ROLE_ORDER.indexOf(b.role)).map((v) => {
      const setv = (data) => H.ops([{ op: "update", entity: "variable", id: v.id, data }]);
      const src = H.select(v.measure_source || "", srcOpts, { class: "sm", "aria-label": t("dz_source"), dataset: { fkey: `dzv-src-${v.id}` }, onchange: (e) => setv({ measure_source: e.target.value }) });
      const wave = H.select(String(v.wave || 0), [["0", "—"], ...[1, 2, 3, 4, 5, 6].map((n) => [String(n), "T" + n])], { class: "sm", "aria-label": t("dz_wave"), dataset: { fkey: `dzv-wave-${v.id}` }, onchange: (e) => setv({ wave: Number(e.target.value) }) });
      const box = (field, label) => el("label.check.dz-box", { title: label }, el("input", { type: "checkbox", checked: !!v[field], "aria-label": `${v.symbol} ${label}`, dataset: { fkey: `dzv-${field}-${v.id}` },
        onchange: (e) => setv({ [field]: e.target.checked }) }), el("span.box", null, H.icon("check", 12)));
      const why = v.role === "ctrl" ? H.input(v.rationale, { class: "sm", placeholder: t("dz_why_ph"), "aria-label": t("dz_why") }) : null;
      if (why) why.addEventListener("change", () => setv({ rationale: why.value }));
      return el("tr.role-" + v.role, null, el("th", { scope: "row" }, el("span.dz-sym", null, v.symbol), el("span.muted", null, " " + (H.varName ? H.varName(v) : ""))),
        el("td", null, t("role_" + v.role)), el("td", null, src), el("td", null, wave),
        v.role === "ctrl" ? el("td.dz-ctrl", null, box("ctrl_y", t("dz_c_y")), box("ctrl_x", t("dz_c_x")), box("ctrl_not_core", t("dz_c_core")), why)
          : el("td.muted.sm", null, "—"));
    });
    const varTable = el("div.card", null, el("div.card-head", null, el("h4", null, t("dz_vars")), el("span.mono.muted", null, "CMV · Becker (2005)")),
      s.variables.length ? el("div.fw-table-wrap", null, el("table.dz-table", null,
        el("thead", null, el("tr", null, [t("variable"), t("role"), t("dz_source"), t("dz_wave"), t("dz_ctrl_head")].map((h) => el("th", { scope: "col" }, h)))),
        el("tbody", null, varRows))) : el("p.empty.sm", null, t("var_empty")),
      el("p.hint", null, t("dz_ctrl_hint")));

    const fit = [["describe", "dz_fit_cross", "dz_fit_cross_lim"], ["change", "dz_fit_long", "dz_fit_long_lim"], ["causal", "dz_fit_exp", "dz_fit_exp_lim"]];
    const fitTable = el("div.card", null, el("div.card-head", null, el("h4", null, t("dz_fit")), el("span.mono.muted", null, "Bono & McNamara, 2011")),
      el("table.c5-guide", null, el("thead", null, el("tr", null, [t("dz_purpose"), t("dz_fit_design"), t("dz_fit_limit")].map((h) => el("th", { scope: "col" }, h)))),
        el("tbody", null, fit.map(([p, dk, lk]) => el("tr" + (d.purpose === p ? ".dz-hl" : ""), null, el("th", { scope: "row" }, t("dz_p_" + p)), el("td", null, t(dk)), el("td", null, t(lk)))))),
      el("p.hint", null, t("dz_fit_note")));

    const issues = [1, 2, 3, 4, 5].reduce((n, k) => n + f.questions[k].filter((a) => a.level === "issue").length, 0);
    return el("div.dz", null,
      el("div.toolbar.wrap", null, el("p.hint-line.grow", null, t("dz_intro")),
        el("span.pill" + (issues ? ".warn" : ".approved"), null, issues ? t("dz_issues", { n: issues }) : t("dz_no_issues"))),
      el("div.dz-top", null, profile, causal),
      el("h3.mini", null, t("dz_five")), questions,
      varTable, fitTable);
  };
})();
