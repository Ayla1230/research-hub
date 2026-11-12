/* Research Hub — app shell: topbar, hero, rendering, live updates. */
(function () {
  const H = window.H;
  const { el, t } = H;

  function topbar() {
    const s = H.state;
    const root = document.getElementById("topbar");
    const otherLang = H.lang === "en" ? "zh" : "en";
    H.put(root, el("div.topbar-in", null,
      el("a.brand", { href: "/" + H.lang + "/", "aria-label": t("app") },
        el("img.mark", { src: "/favicon.svg", alt: "", width: 28, height: 28 }),
        el("span.brand-name", null, "Research Hub"), el("span.brand-sub", null, "研究進度中樞")),
      el("nav.jump", { "aria-label": t("sections") },
        [["pipeline", t("pipeline")], ["core", t("core")], ["hub", t("hub")], ["activity", t("activity")]].map(([id, label]) =>
          el("a", { href: "#" + id }, label))),
      el("div.top-actions", null,
        el("span.live", { id: "live", title: t("live") }, el("i"), el("span", null, t("live"))),
        el("div.mini-progress", { title: t("overall"), "aria-label": `${t("overall")} ${s.overall}%` },
          el("span.mp-bar", null, el("span", { style: { width: s.overall + "%" } })), el("span.mono", null, s.overall + "%")),
        el("button.btn.ghost.inbox-btn" + (s.pending ? ".has" : ""), { type: "button", onclick: H.openInbox, "aria-label": `${t("inbox")} (${s.pending})` },
          H.icon("inbox", 17), el("span.hide-sm", null, t("inbox")), s.pending ? el("span.badge", null, String(s.pending)) : null),
        el("a.btn.ghost.lang", { href: "/" + otherLang + "/", hreflang: otherLang, "aria-label": t("language") + ": " + (otherLang === "en" ? "English" : "中文"),
          onclick: async (e) => { e.preventDefault(); try { await H.api("/api/settings", { body: { language: otherLang } }); } catch (_) { /* still switch */ } location.href = "/" + otherLang + "/"; } },
          H.icon("globe", 16), el("span", null, otherLang === "en" ? "EN" : "中")),
        H.btn(t("settings"), { icon: "settings", iconOnly: true, variant: "ghost", onclick: H.openSettings }))));
  }

  function hero() {
    const s = H.state;
    const root = document.getElementById("hero");
    const done = s.stages.filter((x) => x.status === "done").length;
    const current = s.stages.find((x) => x.status === "active" || x.status === "review" || x.status === "blocked") || s.stages.find((x) => x.status !== "done");
    const upcoming = s.stages.filter((x) => x.status !== "done" && x.due_date).sort((a, b) => a.due_date.localeCompare(b.due_date))[0];
    const unsupported = s.variables.filter((v) => !s.variable_papers.some((l) => l.variable_id === v.id)).length;
    const title = el("h1#hero-title", { contenteditable: "plaintext-only", spellcheck: "false", role: "textbox", "aria-label": t("s_project_title") }, s.settings.project_title);
    title.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); title.blur(); } });
    title.addEventListener("blur", async () => {
      const v = title.textContent.trim();
      if (!v) { title.textContent = s.settings.project_title; return; }
      if (v !== s.settings.project_title) { try { await H.api("/api/settings", { body: { project_title: v } }); await H.refresh(); } catch (e) { H.toast(e.message, "error"); } }
    });
    const stat = (label, value, extra, onclick) => el(onclick ? "button.stat" : "div.stat", onclick ? { type: "button", onclick } : null,
      el("span.stat-label", null, label), el("span.stat-value", null, value), extra ? el("span.stat-extra", null, extra) : null);
    const go = (tab) => () => { H.ui.coreTab = tab; H.render.core(); document.getElementById("core").scrollIntoView({ behavior: "smooth" }); };
    H.put(root, el("div.hero-in", null,
      el("div.hero-copy", null,
        el("div.eyebrow", null, el("span.pulse"), t("app"), el("span", null, "/"), t("tagline")),
        title,
        el("div.hero-cta", null,
          H.btn(t("ci_hero"), { icon: "upload", variant: "primary", onclick: () => H.openCheckin({}) }),
          el("span.muted.sm", null, t("ci_hero_hint"))),
        el("div.hero-now", null,
          current ? el("button.now-chip", { type: "button", onclick: () => { H.ui.openStage = current.id; H.render.pipeline(); document.getElementById("stage-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" }); } },
            el("span.lbl", null, t("current")), el("span.dot." + current.status), H.stageTitle(current), el("span.mono", null, (current.status === "done" ? 100 : current.progress) + "%")) : null,
          (() => {
            const dl = s.settings.project_deadline;
            const n = dl ? H.daysUntil(dl) : null;
            return el("button.now-chip.goal", { type: "button", onclick: H.openSettings, title: s.settings.project_goal || "" },
              H.icon("flag", 14), el("span.lbl", null, t("final_goal")),
              dl ? `${dl} · ${n < 0 ? t("overdue") : t("days_left", { n })}` : t("set_goal"));
          })(),
          el("span.now-chip.static", null, el("span.lbl", null, t("next_due")), upcoming ? `${H.stageTitle(upcoming)} · ${upcoming.due_date}` : t("none_due"),
            upcoming && H.dueLabel(upcoming.due_date)?.kind === "late" ? el("span.pill.late", null, t("overdue")) : null))),
      el("div.hero-stats", null,
        el("div.stat.big", null, el("span.stat-label", null, t("overall")),
          el("span.stat-value", null, String(s.overall), el("small", null, "%")),
          el("span.bar", null, el("span", { style: { width: s.overall + "%" } }))),
        stat(t("stages_done"), `${done}/${s.stages.length}`),
        stat(t("rqs"), String(s.rqs.length), null, go("rq")),
        stat(t("variables"), String(s.variables.length), unsupported ? t("unsupported", { n: unsupported }) : null, go("variables")),
        stat(t("papers"), String(s.papers.length), `${s.papers.filter((p) => p.status === "done").length} ${t("ps_done")}`, go("literature")),
        stat(t("tasks"), `${s.tasks.filter((x) => x.done).length}/${s.tasks.length}`),
        stat(t("pending"), String(s.pending), null, H.openInbox))));
  }

  function foot() {
    document.getElementById("foot").replaceChildren(el("div.foot-in", null,
      el("span.mono", null, "Research Hub v" + document.querySelector('meta[name="hub-version"]').content),
      el("span", null, "PaperRead · OpenAlex · MCP"),
      el("a", { href: "/static/diagrams/index.html", target: "_blank", rel: "noopener" }, H.lang === "en" ? "System map" : "系統架構圖")));
  }

  /* ---------- render scheduling: don't yank the DOM out from under the user ----------
     Controls that carry data-fkey (stable focus keys) keep focus, value and caret across
     re-renders. Free-text editors without a key (notes, inline titles, search boxes)
     defer background refreshes until they lose focus. */
  let deferred = false;
  function editing() {
    const a = document.activeElement;
    if (!a || a === document.body || a.dataset.fkey) return false;
    if (a.closest("#layer")) return false; // dialogs are not re-rendered by state refresh
    return a.matches("input[type=text], input[type=search], input[type=number], input[type=date], input:not([type]), textarea, [contenteditable]");
  }
  function keepFocus(fn) {
    return function (...args) {
      const a = document.activeElement;
      const key = a && a !== document.body && !a.closest("#layer") ? a.dataset.fkey || a.id : null;
      const isText = key && a.matches("input[type=text], input[type=search], input:not([type])");
      const snap = isText ? { value: a.value, start: a.selectionStart, end: a.selectionEnd } : null;
      const out = fn.apply(this, args);
      if (key && !document.contains(a)) {
        const next = document.querySelector(`[data-fkey="${CSS.escape(key)}"]`) || document.getElementById(key);
        if (next) {
          next.focus({ preventScroll: true });
          if (snap && next.matches("input")) {
            next.value = snap.value;
            try { next.setSelectionRange(snap.start, snap.end); } catch (_) { /* not a text input */ }
          }
        }
      }
      return out;
    };
  }
  for (const name of Object.keys(H.render)) H.render[name] = keepFocus(H.render[name]);
  /* force: the user just acted (H.ops) — show the result now instead of deferring. */
  H.renderAll = keepFocus(function (force) {
    if (!force && editing()) { deferred = true; return; }
    deferred = false;
    const y = window.scrollY;
    topbar(); hero(); H.render.pipeline(); H.render.core(); H.render.hub(); H.render.activity();
    window.scrollTo(0, y);
  });
  document.addEventListener("focusout", () => setTimeout(() => { if (deferred && !editing()) H.renderAll(); }, 0));

  H.refresh = async function (force) {
    H.state = await H.api("/api/state");
    H.renderAll(force === true);
  };
  const softRefresh = H.debounce(() => H.refresh().catch(() => {}), 200);

  /* ---------- live updates (Server-Sent Events) ---------- */
  function connect() {
    const es = new EventSource("/api/events?token=" + encodeURIComponent(H.token));
    es.onopen = () => { document.getElementById("live")?.classList.remove("off"); };
    es.onmessage = (msg) => {
      let ev;
      try { ev = JSON.parse(msg.data); } catch (_) { return; }
      if (ev.type === "proposal") {
        H.toast(t("new_proposal", { t: ev.title }), "info", { label: t("inbox"), fn: H.openInbox });
        if (H.ui.layer === "inbox") H.loadInbox();
      }
      if (ev.type === "run") H.onRun && H.onRun();
      if (ev.entity === "usage") { H.loadUsage && H.loadUsage(); return; }
      softRefresh();
    };
    es.onerror = () => { document.getElementById("live")?.classList.add("off"); };
  }

  document.addEventListener("keydown", (e) => {
    if (e.target.closest("input, textarea, select, [contenteditable]") || e.metaKey || e.ctrlKey || e.altKey) return;
    if (H.ui.layer) return;
    if (e.key === "i") { e.preventDefault(); H.openInbox(); }
    if (e.key === ",") { e.preventDefault(); H.openSettings(); }
  });

  document.addEventListener("DOMContentLoaded", async () => {
    try {
      await H.refresh();
      // Visiting /zh/ or /en/ makes that the remembered language for the root URL.
      const explicit = (location.pathname.match(/^\/(zh|en)\/?$/) || [])[1];
      if (explicit && H.state.settings.language !== explicit) {
        H.api("/api/settings", { body: { language: explicit } }).then(() => { H.state.settings.language = explicit; }).catch(() => {});
      }
      foot();
      connect();
      const hash = location.hash.slice(1);
      if (hash) document.getElementById(hash)?.scrollIntoView();
    } catch (e) {
      document.getElementById("main").prepend(el("div.fatal", null, H.icon("alert", 18), e.message));
    }
  });
})();
