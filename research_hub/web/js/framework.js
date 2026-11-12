/* Research Hub — research model from the user's own writing, hypothesis paths, SVG export. */
(function () {
  const H = window.H;
  const { el, t } = H;
  const NS = "http://www.w3.org/2000/svg";
  const mk = (tag, attrs, text) => { const n = document.createElementNS(NS, tag); for (const k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]); if (text != null) n.textContent = text; return n; };
  const ROLE_ORDER = { iv: 0, med: 1, mod: 2, dv: 3, ctrl: 4, other: 5 };
  const nameOf = (v) => (H.lang === "en" ? v.name_en || v.name_zh : v.name_zh || v.name_en) || "";
  const fit = (s, max) => { let w = 0, out = ""; for (const ch of s) { w += /[　-鿿]/.test(ch) ? 2 : 1; if (w > max) return out + "…"; out += ch; } return out; };
  const relLabel = (r) => [r.label, r.sign ? `(${r.sign})` : ""].filter(Boolean).join(" ");

  /**
   * Lay out a research model from explicit hypothesis paths (shared by the SVG view and the
   * PowerPoint export). vars: [{id, symbol, role, name_zh, name_en}],
   * rels: [{id, source_id, target_id, kind, moderates_id, sign, label}].
   * Columns follow the causal order (sources left, outcomes right); moderators sit above and
   * point at the middle of the path they moderate; paths that skip a column run above the boxes;
   * unconnected variables sit below. Every route is also given as orthogonal/straight points.
   */
  H.modelLayout = function (vars, rels) {
    const byId = new Map(vars.map((v) => [v.id, v]));
    const effects = rels.filter((r) => r.kind !== "moderates" && byId.has(r.source_id) && byId.has(r.target_id));
    const mods = rels.filter((r) => r.kind === "moderates" && byId.has(r.source_id));
    const inEffect = new Set(effects.flatMap((r) => [r.source_id, r.target_id]));
    const layer = new Map([...inEffect].map((id) => [id, 0]));
    for (let pass = 0; pass < inEffect.size; pass++) {
      let changed = false;
      for (const r of effects) {
        const next = Math.min(8, layer.get(r.source_id) + 1);
        if (next > layer.get(r.target_id)) { layer.set(r.target_id, next); changed = true; }
      }
      if (!changed) break;
    }
    const maxLayer = Math.max(0, ...layer.values());
    const hasOut = new Set(effects.map((r) => r.source_id));
    for (const id of inEffect) if (!hasOut.has(id)) layer.set(id, maxLayer); // outcomes line up on the right
    const top = vars.filter((v) => !inEffect.has(v.id) && mods.some((m) => m.source_id === v.id));
    const bottom = vars.filter((v) => !inEffect.has(v.id) && !top.includes(v));
    const L = maxLayer + 1, boxW = 196, boxH = 58, gapY = 26, zW = 176;
    const W = Math.max(960, L * 250 + 80);
    const cols = Array.from({ length: L }, (_, i) => vars.filter((v) => layer.get(v.id) === i)
      .sort((a, b) => ROLE_ORDER[a.role] - ROLE_ORDER[b.role] || String(a.symbol).localeCompare(String(b.symbol))));
    const rows = Math.max(1, ...cols.map((c) => c.length));
    const skips = effects.filter((r) => layer.get(r.target_id) - layer.get(r.source_id) > 1);
    const topPad = (top.length ? 140 : 44) + (skips.length ? 34 + 16 * Math.min(skips.length, 4) : 0);
    const bodyH = rows * boxH + (rows - 1) * gapY + 40;
    const Ht = topPad + bodyH + (bottom.length ? 120 : 30);
    const colX = (i) => (L === 1 ? (W - boxW) / 2 : 40 + (i * (W - 80 - boxW)) / (L - 1));
    const pos = new Map();
    cols.forEach((col, i) => {
      const total = col.length * boxH + (col.length - 1) * gapY;
      col.forEach((v, j) => pos.set(v.id, { x: colX(i), y: topPad + (bodyH - total) / 2 + j * (boxH + gapY), w: boxW }));
    });
    const box = (id) => { const p = pos.get(id); return p && { l: p.x, r: p.x + p.w, t: p.y, b: p.y + boxH, cx: p.x + p.w / 2, cy: p.y + boxH / 2 }; };
    const edges = [];
    const midpoint = new Map();
    for (const r of effects) {
      const a = box(r.source_id), b = box(r.target_id);
      if (!a || !b) continue;
      let d, pts, mx, my;
      const skip = skips.indexOf(r);
      if (skip >= 0) {
        // rounded bracket: rise in the gap after the source, run above the boxes in between, drop into the target
        const lo = layer.get(r.source_id), hi = layer.get(r.target_id);
        const between = vars.filter((v) => layer.get(v.id) > lo && layer.get(v.id) < hi && pos.has(v.id));
        const arcY = Math.min(a.t, b.t, ...between.map((v) => pos.get(v.id).y)) - 22 - 16 * skip;
        const r1 = Math.min(30, (b.l - a.r) / 4);
        d = `M${a.r} ${a.cy} C ${a.r + r1} ${a.cy}, ${a.r + r1} ${arcY}, ${a.r + 2 * r1} ${arcY} L ${b.l - 2 * r1} ${arcY} C ${b.l - r1} ${arcY}, ${b.l - r1} ${b.cy}, ${b.l} ${b.cy}`;
        pts = [[a.r, a.cy], [a.r + r1, a.cy], [a.r + r1, arcY], [b.l - r1, arcY], [b.l - r1, b.cy], [b.l, b.cy]];
        mx = (a.r + b.l) / 2; my = arcY;
      } else if (b.l > a.r + 4) {
        const c = (a.r + b.l) / 2;
        d = `M${a.r} ${a.cy} C ${c} ${a.cy}, ${c} ${b.cy}, ${b.l} ${b.cy}`;
        pts = [[a.r, a.cy], [b.l, b.cy]];
        mx = c; my = (a.cy + b.cy) / 2;
      } else { // same column or backwards: loop underneath
        const dip = Math.max(a.b, b.b) + 46;
        d = `M${a.cx} ${a.b} C ${a.cx} ${dip}, ${b.cx} ${dip}, ${b.cx} ${b.b}`;
        pts = [[a.cx, a.b], [a.cx, dip - 12], [b.cx, dip - 12], [b.cx, b.b]];
        mx = (a.cx + b.cx) / 2; my = dip - 12;
      }
      midpoint.set(r.id, { x: mx, y: my });
      edges.push({ rel: r, kind: "effect", neg: r.sign === "-", d, pts, mid: { x: mx, y: my }, text: relLabel(r) });
    }
    // moderators: top row, x near the paths they moderate
    const targets = top.map((v) => {
      const xs = mods.filter((m) => m.source_id === v.id).map((m) => { const mp = midpoint.get(m.moderates_id); return mp ? mp.x : box(m.target_id)?.cx ?? W / 2; });
      return { v, x: xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : W / 2 };
    }).sort((a, b) => a.x - b.x);
    let lastRight = 20;
    for (const { v, x } of targets) {
      const left = Math.max(lastRight + 16, Math.min(W - zW - 20, x - zW / 2));
      pos.set(v.id, { x: left, y: 34, w: zW });
      lastRight = left + zW;
    }
    // moderators of an effect first, then moderators of a moderation (three-way interaction, "moderated moderation")
    const modIds = new Set(mods.map((m) => m.id));
    const ordered = [...mods.filter((m) => !modIds.has(m.moderates_id)), ...mods.filter((m) => modIds.has(m.moderates_id))];
    for (const m of ordered) {
      const z = box(m.source_id);
      if (!z) continue;
      const to = midpoint.get(m.moderates_id) || (box(m.target_id) ? { x: box(m.target_id).cx, y: box(m.target_id).t } : null);
      if (!to) continue;
      const endY = to.y - (midpoint.has(m.moderates_id) ? 12 : 2);
      const midY = (z.b + endY) / 2;
      midpoint.set(m.id, { x: (z.cx + to.x) / 2 + (z.cx === to.x ? 0 : (to.x - z.cx) * 0.18), y: midY + 12 });
      edges.push({ rel: m, kind: "moderates", neg: false, text: relLabel(m), mid: { x: (z.cx + to.x) / 2, y: midY },
        d: `M${z.cx} ${z.b} C ${z.cx} ${midY}, ${to.x} ${midY}, ${to.x} ${endY}`,
        pts: Math.abs(z.cx - to.x) < 2 ? [[z.cx, z.b], [to.x, endY]] : [[z.cx, z.b], [z.cx, midY], [to.x, midY], [to.x, endY]] });
    }
    bottom.forEach((v, i) => pos.set(v.id, { x: W / 2 - (bottom.length * (zW + 16) - 16) / 2 + i * (zW + 16), y: topPad + bodyH + 50, w: zW }));
    return { W, H: Ht, boxH, nodes: vars.filter((v) => pos.has(v.id)).map((v) => ({ v, ...pos.get(v.id), h: boxH })), edges };
  };

  /* Variables without explicit paths still get a model: X → (M →) Y, Z moderates, C below. */
  H.implicitRelations = function (vars) {
    const by = (r) => vars.filter((v) => v.role === r);
    const X = by("iv"), Y = by("dv"), M = by("med"), Z = by("mod");
    const rels = [];
    let n = 0;
    for (const x of X) for (const y of Y) {
      if (M.length) for (const m of M) { rels.push({ id: "i" + n++, source_id: x.id, target_id: m.id, kind: "effect", sign: "", label: "" }); }
      else rels.push({ id: "i" + n++, source_id: x.id, target_id: y.id, kind: "effect", sign: "", label: "" });
    }
    for (const m of M) for (const y of Y) rels.push({ id: "i" + n++, source_id: m.id, target_id: y.id, kind: "effect", sign: "", label: "" });
    const base = rels.find((r) => X.some((x) => x.id === r.source_id));
    for (const z of Z) if (base) rels.push({ id: "i" + n++, source_id: z.id, target_id: base.target_id, kind: "moderates", moderates_id: base.id, sign: "", label: "" });
    return rels;
  };

  /** Draw the layout as SVG (dashboard view, preview, SVG download). */
  H.pathModelSvg = function (vars, rels, opts = {}) {
    const lay = H.modelLayout(vars, rels);
    const svg = mk("svg", { viewBox: `0 0 ${lay.W} ${lay.H}`, class: "model paths", role: "img", "aria-label": t("tab_model"), xmlns: NS });
    const defs = mk("defs", {});
    for (const [id, cls] of [["arr", "arrowhead"], ["arr-neg", "arrowhead neg"], ["arr-mod", "arrowhead modh"]]) {
      const m = mk("marker", { id: id + (opts.idSuffix || ""), viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: "auto-start-reverse" });
      m.append(mk("path", { d: "M0 0 L10 5 L0 10 z", class: cls }));
      defs.append(m);
    }
    svg.append(defs);
    const edges = mk("g", { class: "edges" }), labels = mk("g", { class: "labels" });
    for (const e of lay.edges) {
      const cls = e.kind === "moderates" ? "modl" : e.neg ? "neg" : "";
      const marker = e.kind === "moderates" ? "arr-mod" : e.neg ? "arr-neg" : "arr";
      edges.append(mk("path", { d: e.d, class: e.kind === "moderates" ? "edge modl" : "edge path" + (e.neg ? " neg" : ""), "marker-end": `url(#${marker}${opts.idSuffix || ""})` }));
      if (e.text) {
        const w = e.text.length * 7 + 12;
        labels.append(mk("rect", { x: e.mid.x - w / 2, y: e.mid.y - 10, width: w, height: 20, rx: 10, class: "lbl-bg " + cls }));
        labels.append(mk("text", { x: e.mid.x, y: e.mid.y + 4, "text-anchor": "middle", class: "lbl " + cls }, e.text));
      }
    }
    svg.append(edges);
    const nodes = mk("g", { class: "nodes" });
    const linkedRq = new Set((H.state.rq_variables || []).map((l) => l.variable_id));
    for (const p of lay.nodes) {
      const v = p.v;
      const papers = opts.interactive ? H.links("variable_paper", "a", v.id).length : null;
      const g = mk("g", { class: `mnode role-${v.role}${papers === 0 ? " bare" : ""}`, tabindex: opts.interactive ? 0 : null,
        role: opts.interactive ? "button" : null, "aria-label": `${v.symbol} ${nameOf(v)}` });
      g.append(mk("rect", { x: p.x, y: p.y, width: p.w, height: p.h, rx: 12 }));
      g.append(mk("text", { x: p.x + 14, y: p.y + 24, class: "sym" }, v.symbol + (opts.interactive && linkedRq.has(v.id) ? " ·RQ" : "")));
      g.append(mk("text", { x: p.x + 14, y: p.y + 44, class: "nm" }, fit(nameOf(v), papers != null ? 18 : 22)));
      if (papers != null) {
        const b = mk("g", { class: "badge" });
        b.append(mk("rect", { x: p.x + p.w - 40, y: p.y + 10, width: 28, height: 18, rx: 9 }));
        b.append(mk("text", { x: p.x + p.w - 26, y: p.y + 23, "text-anchor": "middle" }, String(papers)));
        g.append(b);
      }
      if (opts.interactive) {
        g.addEventListener("click", () => H.editVariable(v));
        g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); H.editVariable(v); } });
      }
      nodes.append(g);
    }
    svg.append(nodes, labels);
    return svg;
  };
  H.nameOf = nameOf;

  /* ---------- relation list + editor ---------- */
  const varLabel = (v) => (v ? `${v.symbol} ${nameOf(v)}` : "?");
  H.relationList = function () {
    const s = H.state;
    const rels = s.relations || [];
    return el("div.rel-list-wrap", null, el("h4.mini", null, t("fw_paths") + ` · ${rels.length}`),
      el("ul.rel-list", null, rels.map((r) => {
        const a = H.by(s.variables, r.source_id), b = H.by(s.variables, r.target_id);
        const base = r.moderates_id ? H.by(rels, r.moderates_id) : null;
        const text = r.kind === "moderates"
          ? `${varLabel(a)} ${t("fw_moderates_word")} ${base ? `${varLabel(H.by(s.variables, base.source_id))} → ${varLabel(H.by(s.variables, base.target_id))}` : varLabel(b)}`
          : `${varLabel(a)} → ${varLabel(b)}`;
        return el("li", null, el("span.rel-label.mono", null, r.label || "—"),
          el("span.rel-text", null, text), r.sign ? el("span.pill.tiny" + (r.sign === "-" ? ".late" : ""), null, r.sign === "-" ? t("fw_sign_neg") : t("fw_sign_pos")) : null,
          H.btn(t("edit"), { icon: "edit", iconOnly: true, small: true, variant: "ghost", onclick: () => H.editRelation(r) }),
          H.btn(t("delete"), { icon: "trash", iconOnly: true, small: true, variant: "ghost", onclick: () => H.ops([{ op: "delete", entity: "relation", id: r.id }]) }));
      })));
  };

  H.editRelation = function (rel) {
    const s = H.state;
    const opts = s.variables.map((v) => [String(v.id), varLabel(v)]);
    const effects = (s.relations || []).filter((r) => r.kind !== "moderates" && (!rel || r.id !== rel.id));
    const f = {
      kind: H.select(rel ? rel.kind : "effect", [["effect", t("fw_kind_effect")], ["moderates", t("fw_kind_moderates")]]),
      source_id: H.select(String(rel ? rel.source_id : opts[0]?.[0] || ""), opts),
      target_id: H.select(String(rel ? rel.target_id : opts[1]?.[0] || ""), opts),
      moderates_id: H.select(String(rel ? rel.moderates_id || "" : effects[0]?.id || ""), [["", "—"], ...effects.map((r) => [String(r.id),
        `${r.label ? r.label + " " : ""}${varLabel(H.by(s.variables, r.source_id))} → ${varLabel(H.by(s.variables, r.target_id))}`])]),
      sign: H.select(rel ? rel.sign : "+", [["+", t("fw_sign_pos")], ["-", t("fw_sign_neg")], ["", t("fw_sign_none")]]),
      label: H.input(rel ? rel.label : "H" + ((s.relations || []).length + 1)),
      note: H.textarea(rel ? rel.note : "", { rows: 2 }),
    };
    const modField = H.field(t("fw_moderated_path"), f.moderates_id);
    const targetField = H.field(t("fw_target"), f.target_id);
    const sync = () => { const mod = f.kind.value === "moderates"; modField.hidden = !mod; targetField.hidden = mod; };
    f.kind.addEventListener("change", sync);
    const body = el("div.form-grid", null, H.field(t("kind"), f.kind), H.field(t("fw_label"), f.label),
      H.field(t("fw_source"), f.source_id), targetField, modField, H.field(t("fw_sign"), f.sign),
      el("div.span2", null, H.field(t("notes"), f.note)));
    sync();
    const save = async () => {
      const data = { kind: f.kind.value, source_id: Number(f.source_id.value), sign: f.sign.value, label: f.label.value, note: f.note.value };
      if (data.kind === "moderates") {
        const base = H.by(s.relations || [], Number(f.moderates_id.value));
        if (!base) return H.toast(t("fw_pick_path"), "error");
        Object.assign(data, { moderates_id: base.id, target_id: base.target_id });
      } else Object.assign(data, { target_id: Number(f.target_id.value), moderates_id: null });
      try { await H.ops([rel ? { op: "update", entity: "relation", id: rel.id, data } : { op: "create", entity: "relation", data }], true); H.closeLayer(); }
      catch (e) { H.toast(e.message, "error"); }
    };
    H.openLayer("modal", rel ? `${t("edit")} · ${rel.label || t("fw_path")}` : t("fw_add_rel"), body, [
      H.btn(t("cancel"), { variant: "ghost", onclick: H.closeLayer }), H.btn(t("save"), { variant: "primary", onclick: save })]);
  };

  /* ---------- SVG download (styles inlined so it opens anywhere) ---------- */
  H.downloadSvg = function (svg, filename) {
    const host = svg.isConnected ? null : el("div", { style: { position: "fixed", left: "-9999px", top: "0", width: "1000px" } }, svg);
    if (host) document.body.append(host);
    const clone = svg.cloneNode(true);
    const src = [svg, ...svg.querySelectorAll("*")], dst = [clone, ...clone.querySelectorAll("*")];
    const props = ["fill", "stroke", "stroke-width", "stroke-dasharray", "opacity", "font-family", "font-size", "font-weight"];
    src.forEach((n, i) => {
      if (!(n instanceof SVGElement)) return;
      const cs = getComputedStyle(n);
      dst[i].setAttribute("style", props.map((p) => `${p}:${cs.getPropertyValue(p)}`).join(";"));
      dst[i].removeAttribute("class"); dst[i].removeAttribute("tabindex");
    });
    const [, , w, h] = (svg.getAttribute("viewBox") || "0 0 960 600").split(/\s+/).map(Number);
    clone.setAttribute("width", w); clone.setAttribute("height", h); clone.setAttribute("xmlns", NS);
    clone.insertBefore(mk("rect", { x: 0, y: 0, width: w, height: h, fill: "#ffffff" }), clone.firstChild);
    if (host) host.remove();
    const blob = new Blob(['<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(clone)], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = el("a", { href: url, download: filename }); document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  };

  /* ---------- dialog: draw the model from my own writing ---------- */
  function freshSymbols(found) {
    const used = new Set(H.state.variables.map((v) => v.symbol));
    const prefix = { iv: "X", dv: "Y", med: "M", mod: "Z", ctrl: "C", other: "V" };
    for (const v of found) {
      if (v.existing_id) { v.symbol = H.by(H.state.variables, v.existing_id).symbol; continue; }
      let n = 1;
      while (used.has(prefix[v.role] + n)) n++;
      v.symbol = prefix[v.role] + n;
      used.add(v.symbol);
    }
  }

  H.openFramework = async function () {
    const s = H.state;
    let usage = null;
    try { usage = await H.api("/api/usage"); } catch (_) { /* optional */ }
    let file = null, result = null;
    const text = H.textarea("", { rows: 8, placeholder: t("fw_text_ph") });
    const fileName = el("span.muted.sm");
    const picker = el("input", { type: "file", accept: ".docx,.txt,.md,.tex", hidden: true, onchange: () => {
      file = picker.files[0] || null; fileName.textContent = file ? file.name : ""; text.disabled = !!file; saveRow.hidden = !file;
    } });
    const useAi = el("input", { type: "checkbox", checked: !!(usage && usage.ai), disabled: !(usage && usage.ai) });
    const saveFile = el("input", { type: "checkbox", checked: true });
    const saveRow = el("label.toggle", { hidden: true }, saveFile, el("span.track-t", null, el("span.knob")), el("span", null, t("fw_save_file")));
    const replace = el("input", { type: "checkbox", checked: false });
    const out = el("div.fw-out");

    const analyze = async () => {
      if (!file && text.value.trim().length < 10) { text.focus(); return H.toast(t("fw_need_text"), "error"); }
      go.disabled = true; H.put(out, el("p.muted.sm", null, t("fw_reading")));
      try {
        result = file
          ? await H.api("/api/framework/extract" + (useAi.checked ? "?ai=1" : ""), { body: file, headers: { "X-Filename": encodeURIComponent(file.name), "Content-Type": "application/octet-stream" } })
          : await H.api("/api/framework/extract", { body: { text: text.value, ai: useAi.checked } });
        freshSymbols(result.variables);
        drawResult();
        H.loadUsage && H.loadUsage();
      } catch (e) { H.put(out); H.toast(e.message, "error"); }
      go.disabled = false;
    };
    const go = H.btn(t("fw_analyze"), { icon: "sparkle", variant: "outline", onclick: analyze });

    const previewHost = el("div.model-wrap.fw-preview");
    const drawPreview = () => {
      const vars = result.variables.filter((v) => v.keep !== false).map((v) => ({ id: v.key, symbol: v.symbol, role: v.role, name_zh: v.name_zh, name_en: v.name_en }));
      const keep = new Set(vars.map((v) => v.id));
      const rels = result.relations.map((r, i) => ({ id: "r" + i, source_id: r.source, target_id: r.target, kind: r.kind, sign: r.sign, label: r.label,
        moderates_id: r.moderates != null ? "r" + r.moderates : null, keep: r.keep !== false }))
        .filter((r) => r.keep && keep.has(r.source_id) && keep.has(r.target_id));
      H.put(previewHost, vars.length ? H.pathModelSvg(vars, rels, { idSuffix: "-pv" }) : el("p.empty.sm", null, t("fw_nothing")));
    };
    function drawResult() {
      if (!result.variables.length) {
        H.put(out, el("div.empty-state", null, H.icon("alert", 20), el("p", null, result.method === "rules" ? t("fw_none_rules") : t("fw_none_ai"))));
        return;
      }
      const roleOpts = H.ROLE_ORDER.map((r) => [r, t("role_" + r)]);
      const varRows = result.variables.map((v) => {
        const keep = el("input", { type: "checkbox", checked: v.keep !== false, onchange: () => { v.keep = keep.checked; drawPreview(); } });
        const sym = H.input(v.symbol, { class: "sm sym-in", "aria-label": t("symbol"), oninput: (e) => { v.symbol = e.target.value; drawPreview(); } });
        const name = H.input(nameOf(v), { class: "sm", "aria-label": t("name"), oninput: (e) => {
          if (H.lang === "en" ? v.name_en || !v.name_zh : !v.name_zh && v.name_en) v.name_en = e.target.value; else v.name_zh = e.target.value; drawPreview(); } });
        const role = H.select(v.role, roleOpts, { class: "sm", "aria-label": t("role"), disabled: !!v.existing_id, onchange: (e) => { v.role = e.target.value; drawPreview(); } });
        return el("tr", null, el("td", null, el("label.check", null, keep, el("span.box", null, H.icon("check", 12)))), el("td", null, sym), el("td", null, name), el("td", null, role),
          el("td", null, v.existing_id ? el("span.pill.tiny.approved", null, t("fw_existing")) : el("span.pill.tiny", null, t("fw_new"))));
      });
      const keyName = (k) => { const v = result.variables.find((x) => x.key === k); return v ? `${v.symbol} ${nameOf(v)}` : k; };
      const relRows = result.relations.map((r) => {
        const keep = el("input", { type: "checkbox", checked: r.keep !== false, onchange: () => { r.keep = keep.checked; drawPreview(); } });
        const base = r.moderates != null ? result.relations[r.moderates] : null;
        const text = r.kind === "moderates" && base ? `${keyName(r.source)} ${t("fw_moderates_word")} ${keyName(base.source)} → ${keyName(base.target)}` : `${keyName(r.source)} → ${keyName(r.target)}`;
        return el("li", null, el("label.check", null, keep, el("span.box", null, H.icon("check", 12))), el("span.rel-label.mono", null, r.label || "—"),
          el("span.rel-text", null, text), r.sign ? el("span.pill.tiny" + (r.sign === "-" ? ".late" : ""), null, r.sign) : null);
      });
      H.put(out,
        el("div.fw-meta", null, el("span.pill.tiny", null, result.method === "ai" ? "AI" : t("fw_rules")),
          el("span.muted.sm", null, t("fw_found", { v: result.variables.length, r: result.relations.length })),
          result.tokens ? el("span.mono.muted.sm", null, t("tokens_used", { n: result.tokens })) : null),
        previewHost,
        el("h4.mini", null, t("variables")),
        el("div.fw-table-wrap", null, el("table.fw-table", null, el("thead", null, el("tr", null, el("th"), el("th", null, t("symbol")), el("th", null, t("name")), el("th", null, t("role")), el("th"))), el("tbody", null, varRows))),
        el("h4.mini", null, t("fw_paths")),
        result.relations.length ? el("ul.rel-list", null, relRows) : el("p.empty.sm", null, t("fw_no_paths")),
        (s.relations || []).length ? el("label.toggle", null, replace, el("span.track-t", null, el("span.knob")), el("span", null, t("fw_replace", { n: s.relations.length }))) : null);
      drawPreview();
    }

    const apply = async () => {
      if (!result || !result.variables.length) return H.toast(t("fw_analyze_first"), "error");
      const ops = [];
      if (replace.checked) for (const r of H.state.relations || []) ops.push({ op: "delete", entity: "relation", id: r.id });
      const ref = new Map();
      result.variables.forEach((v, i) => {
        if (v.keep === false) return;
        if (v.existing_id) { ref.set(v.key, v.existing_id); return; }
        ops.push({ op: "create", entity: "variable", ref: "fv" + i, data: { symbol: v.symbol || "V", role: v.role, name_zh: v.name_zh, name_en: v.name_en, definition: v.definition || "" } });
        ref.set(v.key, "$fv" + i);
      });
      const existing = new Set(replace.checked ? [] : (H.state.relations || []).map((r) => `${r.source_id}>${r.target_id}>${r.kind}`));
      const made = new Map();
      const add = (r, i) => {
        if (r.keep === false || !ref.has(r.source) || !ref.has(r.target)) return;
        const a = ref.get(r.source), b = ref.get(r.target);
        if (typeof a === "number" && typeof b === "number" && existing.has(`${a}>${b}>${r.kind}`)) return;
        const data = { source_id: a, target_id: b, kind: r.kind, sign: r.sign || "", label: r.label || "" };
        if (r.kind === "moderates") { if (!made.has(r.moderates)) return; data.moderates_id = made.get(r.moderates); }
        ops.push({ op: "create", entity: "relation", ref: "fr" + i, data });
        made.set(i, "$fr" + i);
      };
      result.relations.forEach((r, i) => { if (r.kind !== "moderates") add(r, i); });
      result.relations.forEach((r, i) => { if (r.kind === "moderates") add(r, i); });
      if (!ops.length) return H.toast(t("fw_nothing_new"), "info");
      applyBtn.disabled = true;
      try {
        if (file && saveFile.checked) {
          const fwStage = H.state.stages.find((x) => x.key === "framework") || H.state.stages.find((x) => x.module === "variables");
          if (fwStage) await H.api("/api/upload?stage_id=" + fwStage.id, { body: file, headers: { "X-Filename": encodeURIComponent(file.name), "Content-Type": "application/octet-stream" } });
        }
        await H.ops(ops, true);
        H.closeLayer();
        H.toast(t("fw_applied"), "ok");
        H.ui.coreTab = "model"; H.ui.section = "core"; H.renderAll(true);
        document.getElementById("core").scrollIntoView({ behavior: "smooth" });
      } catch (e) { H.toast(e.message, "error"); applyBtn.disabled = false; }
    };
    const applyBtn = H.btn(t("fw_apply"), { icon: "check", variant: "primary", onclick: apply });
    const body = el("div.checkin.fw", null,
      el("section.ci-sec", null, el("div.ci-sec-head", null, el("span.ci-n.mono", null, "01"), el("h3", null, t("fw_source_title"))),
        el("p.hint", null, t("fw_source_hint")), text,
        el("div.toolbar", null, H.btn(t("fw_pick_file"), { icon: "upload", small: true, variant: "ghost", onclick: () => picker.click() }), picker, fileName),
        saveRow,
        el("label.toggle", { title: usage && usage.ai ? "" : t("fw_ai_off") }, useAi, el("span.track-t", null, el("span.knob")),
          el("span", null, usage && usage.ai ? t("fw_use_ai") : t("fw_ai_off"))),
        el("div.toolbar", null, go)),
      el("section.ci-sec", null, el("div.ci-sec-head", null, el("span.ci-n.mono", null, "02"), el("h3", null, t("fw_review"))), out));
    H.openLayer("modal", t("fw_title"), body, [H.btn(t("cancel"), { variant: "ghost", onclick: H.closeLayer }), applyBtn], { wide: true, eyebrow: t("fw_eyebrow"), id: "framework" });
    text.focus();
  };
})();
