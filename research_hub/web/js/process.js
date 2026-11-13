/* Research Hub — model templates numbered as in Hayes' PROCESS macro (conceptual diagrams).
   Each template is described by which of the three paths carry moderators:
   a = X → M, b = M → Y, c = X → Y (direct). "three" marks a three-way interaction, where Z moderates
   W's moderation of that path. The drawings are generated here from that description.
   Reference: Hayes, A. F. (2022). Introduction to mediation, moderation, and conditional process
   analysis (3rd ed.). Check Appendix A of the book before running an analysis. */
(function () {
  const H = window.H;
  const { el } = H;
  const L = (zh, en) => (H.lang === "en" ? en : zh);
  const M = (n, group, zh, en, spec) => ({ n, group, zh, en, meds: 0, a: [], b: [], c: [], three: [], ...spec });
  H.PROCESS_MODELS = [
    M(1, "mod", "簡單調節", "Simple moderation", { c: ["W"] }),
    M(2, "mod", "雙調節（W、Z 各自調節）", "Two moderators (additive)", { c: ["W", "Z"] }),
    M(3, "mod", "調節的調節（三階交互作用）", "Moderated moderation (three-way)", { c: ["W"], three: ["c"] }),
    M(4, "med", "簡單中介（可平行多個中介）", "Simple / parallel mediation", { meds: 1 }),
    M(6, "med", "序列中介（M1 → M2）", "Serial mediation", { meds: 2, serial: true }),
    M(5, "cond", "中介＋W 調節直接效果", "Mediation, W moderates the direct effect", { meds: 1, c: ["W"] }),
    M(7, "cond", "第一階段調節中介（W 調節 X → M）", "First-stage moderated mediation", { meds: 1, a: ["W"] }),
    M(8, "cond", "W 調節 X → M 與 X → Y", "W moderates X → M and X → Y", { meds: 1, a: ["W"], c: ["W"] }),
    M(9, "cond", "W、Z 調節 X → M", "W and Z moderate X → M", { meds: 1, a: ["W", "Z"] }),
    M(10, "cond", "W、Z 調節 X → M 與 X → Y", "W and Z moderate X → M and X → Y", { meds: 1, a: ["W", "Z"], c: ["W", "Z"] }),
    M(11, "cond", "X → M 的三階交互作用", "Three-way on X → M", { meds: 1, a: ["W"], three: ["a"] }),
    M(12, "cond", "X → M 與 X → Y 的三階交互作用", "Three-way on X → M and X → Y", { meds: 1, a: ["W"], c: ["W"], three: ["a", "c"] }),
    M(13, "cond", "X → M 三階交互，W 調節 X → Y", "Three-way on X → M, W on X → Y", { meds: 1, a: ["W"], c: ["W"], three: ["a"] }),
    M(14, "cond", "第二階段調節中介（W 調節 M → Y）", "Second-stage moderated mediation", { meds: 1, b: ["W"] }),
    M(15, "cond", "W 調節 M → Y 與 X → Y", "W moderates M → Y and X → Y", { meds: 1, b: ["W"], c: ["W"] }),
    M(16, "cond", "W、Z 調節 M → Y", "W and Z moderate M → Y", { meds: 1, b: ["W", "Z"] }),
    M(17, "cond", "W、Z 調節 M → Y 與 X → Y", "W and Z moderate M → Y and X → Y", { meds: 1, b: ["W", "Z"], c: ["W", "Z"] }),
    M(18, "cond", "M → Y 的三階交互作用", "Three-way on M → Y", { meds: 1, b: ["W"], three: ["b"] }),
    M(19, "cond", "M → Y 與 X → Y 的三階交互作用", "Three-way on M → Y and X → Y", { meds: 1, b: ["W"], c: ["W"], three: ["b", "c"] }),
    M(20, "cond", "M → Y 三階交互，W 調節 X → Y", "Three-way on M → Y, W on X → Y", { meds: 1, b: ["W"], c: ["W"], three: ["b"] }),
    M(21, "cond", "W 調節 X → M，Z 調節 M → Y", "W on X → M, Z on M → Y", { meds: 1, a: ["W"], b: ["Z"] }),
    M(22, "cond", "W 調節 X → M 與 X → Y，Z 調節 M → Y", "W on X → M and X → Y, Z on M → Y", { meds: 1, a: ["W"], c: ["W"], b: ["Z"] }),
    M(28, "cond", "W 調節 X → M，Z 調節 M → Y 與 X → Y", "W on X → M, Z on M → Y and X → Y", { meds: 1, a: ["W"], b: ["Z"], c: ["Z"] }),
    M(29, "cond", "W 調節 X → M 與 X → Y，Z 調節 M → Y 與 X → Y", "W on X → M and X → Y, Z on M → Y and X → Y", { meds: 1, a: ["W"], b: ["Z"], c: ["W", "Z"] }),
    M(58, "cond", "W 同時調節 X → M 與 M → Y", "W moderates both stages", { meds: 1, a: ["W"], b: ["W"] }),
    M(59, "cond", "W 調節全部三條路徑", "W moderates all three paths", { meds: 1, a: ["W"], b: ["W"], c: ["W"] }),
    // two moderators, W on both stages
    M(60, "cond2", "W 調節兩階段，Z 調節 X → M", "W on both stages, Z on X → M", { meds: 1, a: ["W", "Z"], b: ["W"] }),
    M(61, "cond2", "Model 60＋W 調節 X → Y", "Model 60 plus W on X → Y", { meds: 1, a: ["W", "Z"], b: ["W"], c: ["W"] }),
    M(62, "cond2", "W 調節兩階段，Z 調節 X → M 與 X → Y", "W on both stages, Z on X → M and X → Y", { meds: 1, a: ["W", "Z"], b: ["W"], c: ["Z"] }),
    M(63, "cond2", "Model 62＋W 調節 X → Y", "Model 62 plus W on X → Y", { meds: 1, a: ["W", "Z"], b: ["W"], c: ["W", "Z"] }),
    M(64, "cond2", "W 調節兩階段，Z 調節 M → Y", "W on both stages, Z on M → Y", { meds: 1, a: ["W"], b: ["W", "Z"] }),
    M(65, "cond2", "Model 64＋W 調節 X → Y", "Model 64 plus W on X → Y", { meds: 1, a: ["W"], b: ["W", "Z"], c: ["W"] }),
    M(66, "cond2", "W 調節兩階段，Z 調節 M → Y 與 X → Y", "W on both stages, Z on M → Y and X → Y", { meds: 1, a: ["W"], b: ["W", "Z"], c: ["Z"] }),
    M(67, "cond2", "Model 66＋W 調節 X → Y", "Model 66 plus W on X → Y", { meds: 1, a: ["W"], b: ["W", "Z"], c: ["W", "Z"] }),
    M(68, "cond2", "W 調節兩階段，X → M 為三階交互", "W on both stages, three-way on X → M", { meds: 1, a: ["W"], b: ["W"], three: ["a"] }),
    M(69, "cond2", "W 調節三條路徑，X → M 與 X → Y 為三階交互", "W on all paths, three-way on X → M and X → Y", { meds: 1, a: ["W"], b: ["W"], c: ["W"], three: ["a", "c"] }),
    M(70, "cond2", "W 調節兩階段，M → Y 為三階交互", "W on both stages, three-way on M → Y", { meds: 1, a: ["W"], b: ["W"], three: ["b"] }),
    M(71, "cond2", "W 調節三條路徑，M → Y 與 X → Y 為三階交互", "W on all paths, three-way on M → Y and X → Y", { meds: 1, a: ["W"], b: ["W"], c: ["W"], three: ["b", "c"] }),
    M(72, "cond2", "兩階段皆為三階交互", "Three-way on both stages", { meds: 1, a: ["W"], b: ["W"], three: ["a", "b"] }),
    M(73, "cond2", "三條路徑皆為三階交互", "Three-way on all three paths", { meds: 1, a: ["W"], b: ["W"], c: ["W"], three: ["a", "b", "c"] }),
    M(74, "cond2", "X 自己調節 M → Y（X × M 交互）", "X moderates M → Y (X × M interaction)", { meds: 1, b: ["X"] }),
    M(75, "cond2", "W、Z 都調節兩階段", "W and Z on both stages", { meds: 1, a: ["W", "Z"], b: ["W", "Z"] }),
    M(76, "cond2", "W、Z 都調節三條路徑", "W and Z on all three paths", { meds: 1, a: ["W", "Z"], b: ["W", "Z"], c: ["W", "Z"] }),
    // combinations of parallel and serial mediators
    M(80, "chain", "平行中介匯入最後一個中介", "Parallel mediators feeding a final mediator", { meds: 3, custom: (k) => {
      const e = [["X", "Y"], ["X", "M" + k], ["M" + k, "Y"]];
      for (let i = 1; i < k; i++) e.push(["X", "M" + i], ["M" + i, "M" + k], ["M" + i, "Y"]);
      return { edges: e, mods: [] };
    } }),
    M(81, "chain", "第一個中介分流到平行中介", "A first mediator feeding parallel mediators", { meds: 3, custom: (k) => {
      const e = [["X", "Y"], ["X", "M1"], ["M1", "Y"]];
      for (let i = 2; i <= k; i++) e.push(["X", "M" + i], ["M1", "M" + i], ["M" + i, "Y"]);
      return { edges: e, mods: [] };
    } }),
    M(82, "chain", "兩條平行的序列中介（M1 → M2、M3 → M4）", "Two parallel serial chains", { meds: 4, fixed: true, custom: () => ({
      edges: [["X", "Y"], ["M1", "M2"], ["M3", "M4"], ...[1, 2, 3, 4].flatMap((i) => [["X", "M" + i], ["M" + i, "Y"]])], mods: [] }) }),
    ...[[83, "W 調節 X → M1", "W on X → M1", ["a1"]], [84, "W 調節 X → M1 與 X → M2", "W on X → M1 and X → M2", ["a1", "a2"]],
      [85, "W 調節 X → M1、X → M2 與 X → Y", "W on X → M1, X → M2 and X → Y", ["a1", "a2", "c"]], [86, "W 調節 X → M1 與 X → Y", "W on X → M1 and X → Y", ["a1", "c"]],
      [87, "W 調節 M2 → Y", "W on M2 → Y", ["b2"]], [88, "W 調節 M1 → Y 與 M2 → Y", "W on M1 → Y and M2 → Y", ["b1", "b2"]],
      [89, "W 調節 M1 → Y、M2 → Y 與 X → Y", "W on M1 → Y, M2 → Y and X → Y", ["b1", "b2", "c"]], [90, "W 調節 M2 → Y 與 X → Y", "W on M2 → Y and X → Y", ["b2", "c"]],
      [91, "W 調節 M1 → M2", "W on M1 → M2", ["d"]], [92, "W 調節全部六條路徑", "W on all six paths", ["a1", "a2", "d", "b1", "b2", "c"]]]
      .map(([n, zh, en, on]) => M(n, "serialmod", "序列中介：" + zh, "Serial mediation: " + en, { meds: 2, fixed: true, custom: () => {
        const P = { a1: ["X", "M1"], a2: ["X", "M2"], d: ["M1", "M2"], b1: ["M1", "Y"], b2: ["M2", "Y"], c: ["X", "Y"] };
        return { edges: Object.values(P), mods: on.map((k) => ["W", ...P[k]]) };
      } })),
  ];
  const GROUPS = [["mod", "調節模型", "Moderation"], ["med", "中介模型", "Mediation"], ["cond", "條件過程模型（調節中介）", "Conditional process"],
    ["cond2", "條件過程模型：兩階段皆調節（60–76）", "Conditional process: both stages (60–76)"], ["chain", "平行＋序列中介（80–82）", "Parallel and serial mediators (80–82)"],
    ["serialmod", "被調節的序列中介（83–92）", "Moderated serial mediation (83–92)"]];

  /* Variables and relations of a template with placeholder ids: X, Y, M1, M2, W, Z. */
  H.processModel = function (m, meds) {
    const k = m.fixed ? m.meds : m.meds ? Math.max(m.meds, Math.min(4, meds || m.meds)) : 0;
    if (m.custom) {
      const c = m.custom(k);
      const cv = [{ id: "X", symbol: "X", role: "iv" }, ...Array.from({ length: k }, (_, i) => ({ id: "M" + (i + 1), symbol: "M" + (i + 1), role: "med" })), { id: "Y", symbol: "Y", role: "dv" }];
      if (c.mods.length) cv.push({ id: "W", symbol: "W", role: "mod" });
      const cr = c.edges.map(([s, t], i) => ({ id: "e" + i, source_id: s, target_id: t, kind: "effect" }));
      for (const [z, s, t] of c.mods) cr.push({ id: "m" + cr.length, source_id: z, target_id: t, kind: "moderates", moderates_id: cr.find((r) => r.source_id === s && r.target_id === t).id });
      return { vars: cv, rels: cr };
    }
    const vars = [{ id: "X", symbol: "X", role: "iv" }];
    for (let i = 1; i <= k; i++) vars.push({ id: "M" + i, symbol: k > 1 ? "M" + i : "M", role: "med" });
    vars.push({ id: "Y", symbol: "Y", role: "dv" });
    const used = new Set([...m.a, ...m.b, ...m.c, ...(m.three.length ? ["W", "Z"] : [])]);
    for (const z of ["W", "Z"]) if (used.has(z)) vars.push({ id: z, symbol: z, role: "mod" });
    const rels = [];
    const effect = (s, t, path) => { const r = { id: `e${rels.length}`, source_id: s, target_id: t, kind: "effect", path }; rels.push(r); return r; };
    const paths = { a: [], b: [], c: [] };
    if (k && m.serial) {
      paths.a.push(effect("X", "M1", "a"));
      for (let i = 1; i < k; i++) { effect("M" + i, "M" + (i + 1), "d"); effect("X", "M" + (i + 1), "a"); effect("M" + i, "Y", "b"); }
      paths.b.push(effect("M" + k, "Y", "b"));
    } else for (let i = 1; i <= k; i++) { paths.a.push(effect("X", "M" + i, "a")); paths.b.push(effect("M" + i, "Y", "b")); }
    paths.c.push(effect("X", "Y", "c"));
    for (const key of ["a", "b", "c"]) for (const base of paths[key]) {
      let wEdge = null;
      for (const z of m[key]) {
        const r = { id: `m${rels.length}`, source_id: z, target_id: base.target_id, kind: "moderates", moderates_id: base.id };
        rels.push(r);
        if (z === "W") wEdge = r;
      }
      if (m.three.includes(key) && wEdge) rels.push({ id: `m${rels.length}`, source_id: "Z", target_id: base.target_id, kind: "moderates", moderates_id: wEdge.id });
    }
    return { vars, rels };
  };

  function apply(m, meds, replace) {
    const s = H.state, { vars, rels } = H.processModel(m, meds);
    const pool = { iv: s.variables.filter((v) => v.role === "iv"), dv: s.variables.filter((v) => v.role === "dv"),
      med: s.variables.filter((v) => v.role === "med"), mod: s.variables.filter((v) => v.role === "mod") };
    const taken = new Set(s.variables.map((v) => v.symbol));
    const ops = replace ? (s.relations || []).map((r) => ({ op: "delete", entity: "relation", id: r.id })) : [];
    const ref = new Map(), reused = [];
    const names = { iv: ["自變數", "Independent variable"], dv: ["依變數", "Dependent variable"], med: ["中介變數", "Mediator"], mod: ["調節變數", "Moderator"] };
    vars.forEach((v, i) => {
      const have = pool[v.role].shift();
      if (have) { ref.set(v.id, have.id); reused.push(have.symbol); return; }
      const base = { iv: "X", dv: "Y", med: "M", mod: v.id }[v.role];
      let n = 1, symbol = v.role === "mod" ? base : base + n;
      while (taken.has(symbol)) symbol = base + ++n;
      taken.add(symbol);
      ops.push({ op: "create", entity: "variable", ref: "pv" + i, data: { symbol, role: v.role, name_zh: names[v.role][0], name_en: names[v.role][1] } });
      ref.set(v.id, "$pv" + i);
    });
    const existing = new Set(replace ? [] : (s.relations || []).filter((r) => r.kind !== "moderates").map((r) => `${r.source_id}>${r.target_id}`));
    const existingId = new Map(replace ? [] : (s.relations || []).filter((r) => r.kind !== "moderates").map((r) => [`${r.source_id}>${r.target_id}`, r.id]));
    const made = new Map();
    let h = (replace ? 0 : (s.relations || []).length) + 1;
    for (const r of rels) {
      const a = ref.get(r.source_id), b = ref.get(r.target_id), key = `${a}>${b}`;
      if (r.kind === "effect") {
        if (existing.has(key)) { made.set(r.id, existingId.get(key)); continue; }
        ops.push({ op: "create", entity: "relation", ref: "pr" + r.id, data: { source_id: a, target_id: b, kind: "effect", label: "H" + h++ } });
      } else {
        if (!made.has(r.moderates_id)) continue;
        ops.push({ op: "create", entity: "relation", ref: "pr" + r.id, data: { source_id: a, target_id: b, kind: "moderates", moderates_id: made.get(r.moderates_id), label: "H" + h++ } });
      }
      made.set(r.id, "$pr" + r.id);
    }
    return { ops, reused };
  }

  H.openProcessModels = function () {
    let current = H.PROCESS_MODELS[0], meds = 1;
    const detail = el("div.pm-detail");
    const grid = el("div.pm-grid");
    const replace = el("input", { type: "checkbox", checked: false });
    const medSel = H.select("1", [["1", "1"], ["2", "2"], ["3", "3"], ["4", "4"]], { "aria-label": L("中介變數數量", "Number of mediators") });
    medSel.addEventListener("change", () => { meds = Number(medSel.value); draw(); });
    const describe = (m) => {
      const name = { a: "X → M", b: "M → Y", c: "X → Y" }, parts = [];
      if (m.custom) {
        const { rels } = H.processModel(m, meds), eff = rels.filter((r) => r.kind === "effect");
        parts.push(L("路徑：", "Paths: ") + eff.map((r) => `${r.source_id} → ${r.target_id}`).join(L("、", ", ")));
        const md = rels.filter((r) => r.kind !== "effect").map((r) => { const b = eff.find((e) => e.id === r.moderates_id); return `${b.source_id} → ${b.target_id}`; });
        if (md.length) parts.push(L(`W 調節：${md.join("、")}`, `W moderates: ${md.join(", ")}`));
        return parts;
      }
      if (m.meds) parts.push(m.serial ? L("序列中介：X → M1 → M2 → Y", "Serial mediation: X → M1 → M2 → Y") : L("中介：X → M → Y", "Mediation: X → M → Y"));
      for (const k of ["a", "b", "c"]) if (m[k].length) parts.push(m.three.includes(k) ? L(`${name[k]}：W 調節，Z 再調節 W 的調節效果（X×W×Z）`, `${name[k]}: moderated by W, with Z moderating that moderation (X×W×Z)`)
        : L(`${name[k]}：由 ${m[k].join("、")} 調節`, `${name[k]}: moderated by ${m[k].join(", ")}`));
      return parts;
    };
    const draw = () => {
      H.put(grid, GROUPS.map(([g, zh, en]) => [el("h3.mini", null, L(zh, en)),
        el("div.pm-cards", null, H.PROCESS_MODELS.filter((m) => m.group === g).map((m) =>
          el("button.pm-card" + (m === current ? ".on" : ""), { type: "button", "aria-pressed": String(m === current), onclick: () => { current = m; meds = m.meds || 0; medSel.value = String(Math.max(1, meds)); draw(); } },
            el("span.pm-num.mono", null, "Model " + m.n), el("span.pm-name", null, L(m.zh, m.en)))))]));
      const { vars, rels } = H.processModel(current, meds);
      medSel.disabled = !current.meds || !!current.fixed; if (current.meds && Number(medSel.value) < current.meds) medSel.value = String(current.meds);
      H.put(detail, el("div.card-head", null, el("h4", null, `Model ${current.n} · ${L(current.zh, current.en)}`)),
        el("div.model-wrap.fw-preview", null, H.pathModelSvg(vars, rels, { idSuffix: "-pm" })),
        el("ul.pm-desc", null, describe(current).map((x) => el("li", null, x))),
        el("div.toolbar.wrap", null, el("label.pm-meds", null, el("span.lbl", null, L("中介變數數量", "Mediators")), medSel),
          el("label.ci-prov", null, replace, el("span", null, L("取代現有的假設路徑", "Replace the existing paths")))));
    };
    draw();
    const go = H.btn(L("套用到我的研究架構", "Apply to my model"), { icon: "check", variant: "primary", onclick: async () => {
      const { ops, reused } = apply(current, meds, replace.checked);
      if (replace.checked && (H.state.relations || []).length && !(await H.confirm(L(`會刪除現有的 ${(H.state.relations || []).length} 條假設路徑，確定嗎？`, `This deletes the ${(H.state.relations || []).length} existing paths. Continue?`)))) return;
      if (!ops.length) return H.toast(L("這些路徑都已經存在", "These paths already exist"), "info");
      try {
        await H.ops(ops, true); H.closeLayer();
        H.toast(L(`已套用 Model ${current.n}` + (reused.length ? `，沿用變數 ${reused.join("、")}` : ""), `Model ${current.n} applied` + (reused.length ? `, reusing ${reused.join(", ")}` : "")), "ok");
      } catch (e) { H.toast(e.message, "error"); }
    } });
    H.openLayer("modal", L("PROCESS 模型範本", "PROCESS model templates"), el("div.pm", null,
      el("p.hint", null, L("依 Hayes PROCESS 的模型編號列出調節、中介與條件過程模型（Model 1–22、28、29、58–76、80–92）。選一個範本即可預覽概念圖，套用時會沿用你已建立的 X、M、W、Z、Y 變數，缺的自動新增。圖是系統依模型結構自行繪製；正式分析前請對照 Hayes (2022) 附錄 A。",
        "Moderation, mediation and conditional process models by their PROCESS number (1–22, 28, 29, 58–76, 80–92). Pick one to preview the conceptual diagram; applying it reuses your X, M, W, Z, Y variables and adds the missing ones. Diagrams are drawn here from the model structure — check Hayes (2022), Appendix A, before analysing.")),
      el("div.pm-body", null, grid, el("div.card.pm-side", null, detail))),
    [H.btn(L("取消", "Cancel"), { variant: "ghost", onclick: H.closeLayer }), go], { wide: true });
  };
})();
