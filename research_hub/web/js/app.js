/* Research Hub — app shell: topbar, hero, rendering, live updates. */
(function () {
  const H = window.H;
  const { el, t } = H;

  /* ---------- sections: one at a time, chosen from the side menu ---------- */
  const SECTIONS = [["home", "nav_home", "home"], ["core", "core", "layers"], ["exam", "exam", "edit"], ["hub", "hub", "plug"], ["activity", "activity", "activity"]];
  const sectionOf = (hash) => (hash === "pipeline" ? "home" : SECTIONS.some((x) => x[0] === hash) ? hash : "home");
  H.ui.section = sectionOf(location.hash.slice(1));
  H.goSection = function (id, opts = {}) {
    H.ui.section = sectionOf(id);
    if (opts.coreTab) H.ui.coreTab = opts.coreTab;
    if (location.hash.slice(1) !== H.ui.section) history.replaceState(null, "", "#" + H.ui.section);
    closeMenu();
    H.renderAll(true);
    window.scrollTo(0, 0);
  };
  window.addEventListener("hashchange", () => { const next = sectionOf(location.hash.slice(1)); if (next !== H.ui.section) H.goSection(next); });

  let menuOpener = null;
  function closeMenu() {
    const nav = document.getElementById("sidenav");
    if (!nav) return;
    nav.remove();
    document.body.classList.remove("locked");
    if (menuOpener && document.contains(menuOpener)) menuOpener.focus();
  }
  function openMenu() {
    if (document.getElementById("sidenav")) return closeMenu();
    menuOpener = document.activeElement;
    const s = H.state, otherLang = H.lang === "en" ? "zh" : "en";
    const counts = { core: s.papers.length, exam: s.questions.length };
    const panel = el("aside.sidenav-panel", { role: "dialog", "aria-modal": "true", "aria-label": t("sections") },
      el("div.sidenav-head", null, el("img.mark", { src: "/favicon.svg", alt: "", width: 28, height: 28 }), el("span.brand-name", null, "Research Hub"),
        H.btn(t("close"), { icon: "x", iconOnly: true, variant: "ghost", class: "push", onclick: closeMenu })),
      el("nav.sidenav-list", { "aria-label": t("sections") }, SECTIONS.map(([id, label, icon]) =>
        el("button.sidenav-item" + (H.ui.section === id ? ".on" : ""), { type: "button", "aria-current": H.ui.section === id ? "page" : null, onclick: () => H.goSection(id) },
          H.icon(icon, 18), el("span", null, t(label)), counts[id] ? el("span.mono.muted", null, String(counts[id])) : null))),
      el("div.sidenav-foot", null,
        el("button.sidenav-item", { type: "button", onclick: () => { closeMenu(); H.openSettings(); } }, H.icon("settings", 18), el("span", null, t("settings"))),
        el("a.sidenav-item", { href: "/" + otherLang + "/" + location.hash, hreflang: otherLang,
          onclick: async (e) => { e.preventDefault(); try { await H.api("/api/settings", { body: { language: otherLang } }); } catch (_) { /* still switch */ } location.href = "/" + otherLang + "/" + location.hash; } },
          H.icon("globe", 18), el("span", null, otherLang === "en" ? "English" : "中文"))));
    const nav = el("div#sidenav.sidenav", null, el("div.sidenav-scrim", { onclick: closeMenu }), panel);
    nav.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { e.stopPropagation(); closeMenu(); }
      if (e.key !== "Tab") return;
      const items = [...panel.querySelectorAll("button, a")];
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
    document.body.append(nav);
    document.body.classList.add("locked");
    (panel.querySelector(".sidenav-item.on") || panel.querySelector("button")).focus();
  }

  /* Sub-options of the section you are in: the only navigation shown in the top bar. */
  function subnav() {
    const s = H.state, sec = H.ui.section;
    const item = (label, on, onclick, count, id) => el("button.subnav-item" + (on ? ".on" : ""), { type: "button", id, "aria-current": on ? "true" : null, onclick },
      label, count != null ? el("span.count", null, String(count)) : null);
    if (sec === "core") {
      const counts = { rq: s.rqs.length, variables: s.variables.length, literature: s.papers.length };
      return H.CORE_TABS.map(([id, label]) => item(t(label), H.ui.coreTab === id, () => { H.ui.coreTab = id; H.render.core(); topbar(); document.getElementById("nav-" + id)?.focus(); }, counts[id], "nav-" + id));
    }
    if (sec === "exam") {
      const mode = H.ui.examMode || "questions";
      return [["questions", H.lang === "en" ? "Questions" : "考題整理", s.questions.length], ["papers", H.lang === "en" ? "Readings" : "文獻整理", s.papers.filter((p) => p.folder).length]]
        .map(([id, label, n]) => item(label, mode === id, () => { H.ui.examMode = id; H.render.exam(); topbar(); document.getElementById("nav-" + id)?.focus(); }, n, "nav-" + id));
    }
    if (sec === "home") {
      return s.stages.map((st) => item(H.stageTitle(st), H.ui.openStage === st.id, () => {
        H.ui.openStage = H.ui.openStage === st.id ? null : st.id; H.render.pipeline(); topbar();
        document.getElementById("stage-panel")?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }, null, "nav-stage-" + st.id));
    }
    return [];
  }

  function topbar() {
    const s = H.state;
    const root = document.getElementById("topbar");
    document.body.dataset.section = H.ui.section;
    const current = SECTIONS.find((x) => x[0] === H.ui.section);
    const subs = subnav();
    H.put(root, el("div.topbar-in", null,
      el("button.btn.ghost.icon-only.menu-btn", { type: "button", id: "menu-btn", "aria-label": t("sections"), title: t("sections"), "aria-haspopup": "dialog", onclick: openMenu }, H.icon("menu", 20)),
      el("a.brand", { href: "/" + H.lang + "/", "aria-label": t("app"), onclick: (e) => { e.preventDefault(); H.goSection("home"); } },
        el("img.mark", { src: "/favicon.svg", alt: "", width: 28, height: 28 }), el("span.brand-name.hide-sm", null, "Research Hub")),
      el("span.crumb", null, t(current[1])),
      el("div.top-actions", null,
        el("span.live", { id: "live", title: t("live") }, el("i"), el("span", null, t("live"))),
        el("div.mini-progress", { title: t("overall"), "aria-label": `${t("overall")} ${s.overall}%` },
          el("span.mp-bar", null, el("span", { style: { width: s.overall + "%" } })), el("span.mono", null, s.overall + "%")),
        el("button.btn.ghost.inbox-btn" + (s.pending ? ".has" : ""), { type: "button", onclick: H.openInbox, "aria-label": `${t("inbox")} (${s.pending})` },
          H.icon("inbox", 17), el("span.hide-sm", null, t("inbox")), s.pending ? el("span.badge", null, String(s.pending)) : null))),
      subs.length ? el("nav.subnav", { "aria-label": t(current[1]) }, el("div.subnav-in", null, subs)) : null);
  }
  H.renderTop = topbar;

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
    const go = (tab) => () => H.goSection("core", { coreTab: tab });
    H.put(root, el("div.hero-in", null,
      el("div.hero-copy", null,
        el("div.eyebrow", null, el("span.pulse"), t("app"), el("span", null, "/"), t("tagline")),
        title,
        el("div.hero-cta", null,
          H.btn(t("ci_hero"), { icon: "upload", variant: "primary", onclick: () => H.openCheckin({}) }),
          H.btn(t("sl_hero"), { icon: "layers", variant: "outline", onclick: () => H.openSlides() }),
          H.btn(t("word_hero"), { icon: "file", variant: "outline", onclick: () => H.openThesis() }),
          H.btn(t("voice_hero"), { icon: "play", variant: "outline", onclick: () => H.openVoice() }),
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
      el("span", null, "OpenAlex · Wiley · Semantic Scholar · MCP"),
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
    topbar(); hero(); H.render.pipeline(); H.render.core(); H.render.exam(); H.render.hub(); H.render.activity();
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
    if (H.ui.layer || document.getElementById("sidenav")) return;
    if (e.key === "m") { e.preventDefault(); openMenu(); }
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
    } catch (e) {
      document.getElementById("main").prepend(el("div.fatal", null, H.icon("alert", 18), e.message));
    }
  });
})();
