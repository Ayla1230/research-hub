/* Research Hub — shared helpers: DOM builder, icons, API, toasts, dialogs. */
(function () {
  const H = window.H;
  const t = H.t;
  H.token = document.querySelector('meta[name="hub-token"]').content;
  H.ui = { openStage: null, coreTab: "story", editPipeline: false, litFilter: "", litStatus: "all", inboxTab: "pending" };

  /* ---------- DOM ---------- */
  H.el = function el(tag, attrs, ...kids) {
    const [head, ...classes] = tag.split(".");
    const [name, id] = head.split("#");
    const node = document.createElement(name || "div");
    if (id) node.id = id;
    if (classes.length) node.className = classes.join(" ");
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v == null || v === false) continue;
        if (k === "class") node.className += (node.className ? " " : "") + v;
        else if (k === "text") node.textContent = v;
        else if (k === "style" && typeof v === "object") {
          for (const [prop, val] of Object.entries(v)) {
            if (prop.startsWith("--")) node.style.setProperty(prop, val);
            else node.style[prop] = val;
          }
        }
        else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
        else if (k === "dataset") Object.assign(node.dataset, v);
        else if (v === true) node.setAttribute(k, "");
        else node.setAttribute(k, v);
      }
    }
    for (const kid of kids.flat(Infinity)) {
      if (kid == null || kid === false) continue;
      node.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    }
    return node;
  };
  const el = H.el;
  /* replaceChildren that skips null/false (conditional children) */
  H.put = function (node, ...kids) {
    node.replaceChildren(...kids.flat(Infinity).filter((k) => k != null && k !== false));
    return node;
  };

  /* ---------- Icons (24px stroke, Lucide-style geometry, drawn inline) ---------- */
  const P = {
    check: "M20 6 9 17l-5-5", plus: "M12 5v14M5 12h14", x: "M18 6 6 18M6 6l12 12",
    inbox: "M22 12h-6l-2 3h-4l-2-3H2M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z",
    settings: "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z",
    globe: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z",
    file: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6",
    upload: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12",
    download: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3",
    search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.35-4.35",
    link: "M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71",
    external: "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14 21 3",
    folder: "M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z",
    database: "M12 8c4.97 0 9-1.34 9-3s-4.03-3-9-3-9 1.34-9 3 4.03 3 9 3zM21 12c0 1.66-4 3-9 3s-9-1.34-9-3M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5",
    plug: "M12 22v-5M9 8V2M15 8V2M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8z",
    code: "m16 18 6-6-6-6M8 6l-6 6 6 6", play: "M6 4l14 8-14 8z",
    book: "M4 19.5A2.5 2.5 0 0 1 6.5 17H20V2H6.5A2.5 2.5 0 0 0 4 4.5zM4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5",
    edit: "M12 20h9M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z",
    trash: "M3 6h18M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2",
    chevL: "m15 18-6-6 6-6", chevR: "m9 18 6-6-6-6", chevD: "m6 9 6 6 6-6",
    copy: "M20 9h-9a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2v-9a2 2 0 0 0-2-2zM5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1",
    refresh: "M21 2v6h-6M3 12a9 9 0 0 1 15-6.7L21 8M3 22v-6h6M21 12a9 9 0 0 1-15 6.7L3 16",
    sparkle: "M12 3l1.9 5.8L20 10.7l-6.1 1.9L12 18.5l-1.9-5.9L4 10.7l6.1-1.9z",
    bot: "M12 8V4H8M4 12a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v5a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3zM9 13v2M15 13v2",
    flag: "M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1zM4 22v-7",
    alert: "M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01",
    calendar: "M19 4H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zM16 2v4M8 2v4M3 10h18",
    grid: "M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z",
    layers: "M12 2 2 7l10 5 10-5zM2 17l10 5 10-5M2 12l10 5 10-5",
    star: "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01z",
    eye: "M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
    activity: "M22 12h-4l-3 9L9 3l-3 9H2", grip: "M9 5h.01M9 12h.01M9 19h.01M15 5h.01M15 12h.01M15 19h.01",
  };
  H.icon = function (name, size = 16) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", size);
    svg.setAttribute("height", size);
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "1.75");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    svg.classList.add("ic");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", P[name] || P.sparkle);
    svg.append(path);
    return svg;
  };

  H.btn = function (label, opts = {}) {
    const kids = [];
    if (opts.icon) kids.push(H.icon(opts.icon, opts.iconSize || 16));
    if (label && !opts.iconOnly) kids.push(el("span", null, label));
    return el("button.btn" + (opts.variant ? "." + opts.variant : "") + (opts.iconOnly ? ".icon-only" : "") + (opts.small ? ".sm" : ""), {
      type: opts.type || "button", onclick: opts.onclick, title: opts.title || (opts.iconOnly ? label : null),
      "aria-label": opts.iconOnly ? label : null, disabled: opts.disabled, class: opts.class, dataset: opts.dataset,
    }, kids);
  };

  /* ---------- API ---------- */
  H.api = async function (path, opts = {}) {
    const headers = { "X-Hub-Token": H.token };
    let body = opts.body;
    if (body && !(body instanceof Blob) && typeof body !== "string" && !(body instanceof ArrayBuffer)) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(body);
    }
    Object.assign(headers, opts.headers || {});
    let res;
    try {
      res = await fetch(path, { method: opts.method || (body != null ? "POST" : "GET"), headers, body });
    } catch (e) {
      throw new Error(t("offline"));
    }
    const ctype = res.headers.get("Content-Type") || "";
    const data = ctype.includes("json") ? await res.json() : await res.text();
    if (!res.ok) throw new Error((data && data.error) || res.statusText);
    return data;
  };
  H.ops = async function (ops, quiet) {
    try {
      const out = await H.api("/api/ops", { body: { ops } });
      await H.refresh(true);
      return out;
    } catch (e) {
      if (!quiet) H.toast(e.message, "error");
      throw e;
    }
  };

  /* ---------- Toasts ---------- */
  H.toast = function (message, kind = "info", action) {
    const box = el("div.toast." + kind, { role: kind === "error" ? "alert" : null },
      H.icon(kind === "error" ? "alert" : kind === "ok" ? "check" : "sparkle", 16), el("span", null, message),
      action ? el("button.toast-act", { type: "button", onclick: () => { action.fn(); box.remove(); } }, action.label) : null);
    document.getElementById("toasts").append(box);
    setTimeout(() => box.classList.add("out"), kind === "error" ? 6500 : 3800);
    setTimeout(() => box.remove(), kind === "error" ? 7000 : 4300);
  };

  /* ---------- Layers: modal & drawer ---------- */
  let lastFocus = null;
  H.closeLayer = function () {
    const layer = document.getElementById("layer");
    layer.textContent = "";
    document.body.classList.remove("locked");
    H.ui.layer = null;
    if (lastFocus && document.contains(lastFocus)) lastFocus.focus();
  };
  function trap(e, panel) {
    if (e.key === "Escape") { e.preventDefault(); H.closeLayer(); return; }
    if (e.key !== "Tab") return;
    const items = [...panel.querySelectorAll('button,[href],input,select,textarea,[tabindex]:not([tabindex="-1"])')].filter((n) => !n.disabled && n.offsetParent !== null);
    if (!items.length) return;
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  // Escape closes the open dialog even when focus has drifted out of it.
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && H.ui.layer && !e.defaultPrevented) { e.preventDefault(); H.closeLayer(); }
  });
  H.openLayer = function (kind, title, body, footer, opts = {}) {
    lastFocus = document.activeElement;
    const layer = document.getElementById("layer");
    const titleId = "layer-title";
    const panel = el("div." + kind, { role: "dialog", "aria-modal": "true", "aria-labelledby": titleId, class: opts.wide ? "wide" : null },
      el("div.layer-head", null,
        el("div", null, opts.eyebrow ? el("div.eyebrow", null, opts.eyebrow) : null, el("h2", { id: titleId }, title)),
        H.btn(t("close"), { icon: "x", iconOnly: true, variant: "ghost", onclick: H.closeLayer })),
      el("div.layer-body", null, body),
      footer ? el("div.layer-foot", null, footer) : null);
    const scrim = el("div.scrim", { onclick: H.closeLayer });
    H.put(layer, scrim, panel);
    panel.addEventListener("keydown", (e) => trap(e, panel));
    document.body.classList.add("locked");
    H.ui.layer = opts.id || kind;
    requestAnimationFrame(() => {
      const focus = panel.querySelector("[autofocus]") || panel.querySelector(".layer-body input, .layer-body textarea, .layer-body select") || panel.querySelector("button");
      if (focus) focus.focus();
    });
    return panel;
  };
  H.confirm = function (message, okLabel, danger = true) {
    return new Promise((resolve) => {
      const ok = H.btn(okLabel || t("delete"), { variant: danger ? "danger" : "primary", onclick: () => { H.closeLayer(); resolve(true); } });
      const cancel = H.btn(t("cancel"), { variant: "ghost", onclick: () => { H.closeLayer(); resolve(false); } });
      H.openLayer("modal", message, null, [cancel, ok], { id: "confirm" });
      ok.focus();
    });
  };

  /* ---------- Forms ---------- */
  H.field = function (label, input, hint) {
    const id = input.id || "f" + Math.random().toString(36).slice(2, 9);
    input.id = id;
    return el("div.field", null, el("label", { for: id }, label), input, hint ? el("div.hint", null, hint) : null);
  };
  H.input = (value, attrs = {}) => el("input.inp", { type: "text", value: value ?? "", ...attrs });
  H.textarea = (value, attrs = {}) => { const n = el("textarea.inp", { rows: 3, ...attrs }); n.value = value ?? ""; return n; };
  H.select = function (value, options, attrs = {}) {
    const s = el("select.inp", attrs, options.map(([v, label]) => el("option", { value: v }, label)));
    s.value = value ?? "";
    return s;
  };

  /* ---------- Format ---------- */
  H.when = function (iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const diff = (Date.now() - d.getTime()) / 1000;
    const en = H.lang === "en";
    if (diff < 60) return en ? "just now" : "剛剛";
    if (diff < 3600) return en ? `${Math.floor(diff / 60)} min ago` : `${Math.floor(diff / 60)} 分鐘前`;
    if (diff < 86400) return en ? `${Math.floor(diff / 3600)} h ago` : `${Math.floor(diff / 3600)} 小時前`;
    return d.toLocaleDateString(en ? "en-GB" : "zh-TW", { year: "numeric", month: "short", day: "numeric" });
  };
  H.daysUntil = function (date) {
    if (!date) return null;
    const today = new Date(); today.setHours(0, 0, 0, 0);
    const due = new Date(date + "T00:00:00");
    return Math.round((due - today) / 86400000);
  };
  H.dueLabel = function (date) {
    const n = H.daysUntil(date);
    if (n == null) return null;
    if (n < 0) return { text: t("overdue"), kind: "late" };
    if (n === 0) return { text: t("due_today"), kind: "soon" };
    return { text: t("days_left", { n }), kind: n <= 7 ? "soon" : "" };
  };
  /* Only http(s) links from user/agent data become hrefs (no javascript:, data:, file:). */
  H.safeUrl = (u) => (/^https?:\/\//i.test(String(u || "").trim()) ? String(u).trim() : null);
  /* Save a file the page generated. Non-ASCII names go through the local server so every
     browser receives the proper UTF-8 filename (some ignore it on in-page blob links). */
  H.saveBlob = async function (blob, name) {
    if (/^[\x20-\x7e]+$/.test(name)) {
      const url = URL.createObjectURL(blob);
      const a = el("a", { href: url, download: name }); document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      return;
    }
    const out = await H.api("/api/exports", { body: blob, headers: { "X-Filename": encodeURIComponent(name), "Content-Type": "application/octet-stream" } });
    const a = el("a", { href: out.url + "?token=" + encodeURIComponent(H.token) }); document.body.append(a); a.click(); a.remove();
  };
  H.size = (n) => (n < 1024 ? n + " B" : n < 1048576 ? (n / 1024).toFixed(0) + " KB" : (n / 1048576).toFixed(1) + " MB");
  H.stageTitle = (s) => (H.lang === "en" ? s.title_en || s.title_zh : s.title_zh || s.title_en);
  H.stageDesc = (s) => (H.lang === "en" ? s.desc_en || s.desc_zh : s.desc_zh || s.desc_en);
  H.varName = (v) => (H.lang === "en" ? v.name_en || v.name_zh : v.name_zh || v.name_en) || "";
  H.copy = async function (text) {
    try { await navigator.clipboard.writeText(text); H.toast(t("copied"), "ok"); }
    catch (e) {
      const ta = el("textarea", { style: { position: "fixed", opacity: "0" } }); ta.value = text; document.body.append(ta); ta.select();
      try { document.execCommand("copy"); H.toast(t("copied"), "ok"); } finally { ta.remove(); }
    }
  };
  H.debounce = function (fn, ms) {
    let timer;
    const wrapped = (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
    wrapped.flush = (...args) => { clearTimeout(timer); fn(...args); };
    return wrapped;
  };
  /* Autosaving text control: saves `field` of `entity` #id after typing pauses. */
  H.autosave = function (node, entity, id, field, statusNode) {
    let last = node.value;
    const save = async () => {
      if (node.value === last) return;
      const value = node.value;
      if (statusNode) statusNode.textContent = t("saving");
      try {
        await H.api("/api/ops", { body: { ops: [{ op: "update", entity, id, data: { [field]: value } }] } });
        last = value;
        if (statusNode) statusNode.textContent = t("saved");
      } catch (e) {
        if (statusNode) statusNode.textContent = "";
        H.toast(e.message, "error");
      }
    };
    const later = H.debounce(save, 700);
    node.addEventListener("input", later);
    node.addEventListener("blur", () => later.flush());
    return node;
  };

  /* ---------- Lookups ---------- */
  H.by = (list, id) => list.find((x) => x.id === id);
  H.links = function (name, side, id) {
    const s = H.state;
    const table = { rq_variable: s.rq_variables, rq_paper: s.rq_papers, variable_paper: s.variable_papers }[name];
    const cols = { rq_variable: ["rq_id", "variable_id"], rq_paper: ["rq_id", "paper_id"], variable_paper: ["variable_id", "paper_id"] }[name];
    return table.filter((r) => r[cols[side === "a" ? 0 : 1]] === id);
  };
  H.ROLE_ORDER = ["iv", "med", "mod", "dv", "ctrl", "other"];
  H.EVIDENCE = ["mentions", "supports", "contradicts", "mixed", "defines", "measures"];
  H.PAPER_STATUS = ["candidate", "to_read", "reading", "done", "excluded"];
  H.STAGE_STATUS = ["todo", "active", "review", "done", "blocked"];
})();
