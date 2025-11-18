/* app/users/static/agreements.js */
(function () {
  "use strict";

  // -------------------------------------------------------
  // i18n
  // -------------------------------------------------------
  const T = {
    loading: "Се вчитува...",
    loadError: "Грешка при вчитување",
    noFiles: "Нема датотеки",
    filesTitle: "Прикачени датотеки:",
    btnCreateFinite: "+ Временски договор",
    btnCreateIndef: "+ Неопределен договор",
    start: "Почеток",
    months: "Месеци",
    endAuto: "Крај (автоматски)",
    attachOptional: "Прикачи датотека (опционално)",
    save: "Зачувај",
    close: "Затвори",
    activeSection: "Активни",
    historySection: "Историја",
    activeBadge: "активен",
    indefiniteBadge: "неопределено",
    attachFile: "Прикачи датотека",
    upload: "Качи",
    delete: "Избриши",
    cancel: "Откажи",
    confirmDelete: "Дали сигурно сакате да го избришете овој договор? Оваа акција е трајна.",
    confirmCancel: "Дали сигурно сакате да го откажете овој договор?",
    errCreate: "Неуспешно креирање",
    errAttach: "Неуспешно прикачување",
    errDelete: "Неуспешно бришење",
    errCancel: "Неуспешно откажување",
    willCreateIndef: "ќе се креира договор: неопределено",

    // templates UX
    template: "Шаблон",
    selectTemplate: "Изберете шаблон…",
    manageTemplates: "Уреди шаблони",
    generate: "Генерирај",
    outputFilename: "Име на датотека (опционално)",
  };

  // -------------------------------------------------------
  // DOM utils
  // -------------------------------------------------------
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const on = (el, ev, fn, opts) => el.addEventListener(ev, fn, opts);

  // -------------------------------------------------------
  // Toast
  // -------------------------------------------------------
  function toast(msg, type = "info", timeout = 2200) {
    let host = $("#agreements_toast_host");
    if (!host) {
      host = document.createElement("div");
      host.id = "agreements_toast_host";
      Object.assign(host.style, {
        position: "fixed",
        zIndex: "1080",
        top: "1rem",
        right: "1rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.5rem",
      });
      document.body.appendChild(host);
    }
    const card = document.createElement("div");
    Object.assign(card.style, {
      padding: "10px 12px",
      borderRadius: "10px",
      boxShadow: "0 8px 24px rgba(0,0,0,.15)",
      color: "#fff",
      fontSize: "14px",
      maxWidth: "360px",
      wordBreak: "break-word",
      opacity: "0",
      transform: "translateY(-6px)",
      transition: "all .2s ease",
    });
    card.textContent = String(msg || "");
    const colors = { info: "#0d6efd", success: "#198754", warning: "#ffc107", danger: "#dc3545", error: "#dc3545" };
    card.style.background = colors[type] || colors.info;
    host.appendChild(card);
    requestAnimationFrame(() => {
      card.style.opacity = "1";
      card.style.transform = "translateY(0)";
    });
    setTimeout(() => {
      card.style.opacity = "0";
      card.style.transform = "translateY(-6px)";
      setTimeout(() => card.remove(), 180);
    }, timeout);
  }

  // -------------------------------------------------------
  // CSRF / fetch helpers
  // -------------------------------------------------------
  function getMetaCsrf() {
    if (window.UsersApp?.getMetaCsrf) return window.UsersApp.getMetaCsrf();
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  }

  async function fetchJSON(url) {
    if (window.UsersApp?.fetchJSON) return window.UsersApp.fetchJSON(url);
    const r = await fetch(url, { credentials: "same-origin" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  async function postJSON(url, body) {
    if (window.UsersApp?.postJSON) return window.UsersApp.postJSON(url, body);
    const r = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getMetaCsrf() },
      body: JSON.stringify(body || {}),
    });
    if (!r.ok) {
      const t = await r.text().catch(() => "");
      throw new Error(t || `HTTP ${r.status}`);
    }
    return r.json().catch(() => ({}));
  }

  // -------------------------------------------------------
  // API with fallback prefixes (/users/... → /...)
  // -------------------------------------------------------
  async function apiGet(userId) {
    try { return await fetchJSON(`/users/api/agreements/${userId}`); }
    catch { return await fetchJSON(`/api/agreements/${userId}`); }
  }

  async function apiPost(userId, suffix, payload) {
    const tries = [
      `/users/api/agreements/${userId}/${suffix}`,
      `/api/agreements/${userId}/${suffix}`,
    ];
    let err;
    for (const u of tries) {
      try { return await postJSON(u, payload || {}); }
      catch (e) { err = e; }
    }
    throw err;
  }

  async function apiAttach(userId, formData) {
    const tries = [
      `/users/api/agreements/${userId}/attach`,
      `/api/agreements/${userId}/attach`,
    ];
    let lastText = "";
    for (const u of tries) {
      const r = await fetch(u, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": getMetaCsrf() },
        body: formData,
      });
      if (r.ok) return r.json().catch(() => ({}));
      lastText = (await r.text().catch(() => "")) || `HTTP ${r.status}`;
    }
    throw new Error(lastText || T.errAttach);
  }

  // -------------------------------------------------------
  // Date helpers
  // -------------------------------------------------------
  const todayStr = () => {
    const d = new Date();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${d.getFullYear()}-${mm}-${dd}`;
  };

  const plusMonths = (startISO, months) => {
    if (!startISO || !months) return "";
    const [y, m, d] = (startISO || "").split("-").map(Number);
    if (!y || !m || !d) return "";
    const dt = new Date(y, m - 1, d);
    dt.setMonth(dt.getMonth() + Number(months));
    const mm = String(dt.getMonth() + 1).padStart(2, "0");
    const dd = String(dt.getDate()).padStart(2, "0");
    return `${dt.getFullYear()}-${mm}-${dd}`;
  };

  const isIndef = (a) => (a?.months || 0) === 0 || (a?.end_date && String(a.end_date).includes("2099"));

  // -------------------------------------------------------
  // Script loader helper (for /users/static/template.js)
  // -------------------------------------------------------
  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      // if already loaded, resolve immediately
      const abs = new URL(src, location.href).href;
      const existing = Array.from(document.querySelectorAll("script[src]"))
        .some(s => new URL(s.src, location.href).href === abs);
      if (existing) return resolve(src);

      const s = document.createElement("script");
      s.src = src;
      s.async = false;
      s.onload = function () { resolve(src); };
      s.onerror = function () { reject(new Error("Failed to load " + src)); };
      document.head.appendChild(s);
    });
  }

  // -------------------------------------------------------
  // Template helpers
  // -------------------------------------------------------
  async function ensureTemplatesModalLoaded() {
    if (!document.getElementById("TemplatesModal")) {
      const res = await fetch("/users/templates/manager", { credentials: "same-origin" });
      if (!res.ok) return; // might be forbidden by perms
      const html = await res.text();
      const tmp = document.createElement("div");
      tmp.innerHTML = html;
      const modal = tmp.querySelector("#TemplatesModal");
      if (modal) document.body.appendChild(modal);
    }

    // load the client generator module if not present
    if (typeof window.generateAgreementFromTemplate !== "function") {
      try {
        const v = Date.now(); // cache-bust
        await loadScript(`/users/static/template.js?v=${v}`);
      } catch (e) {
        // fallback path (if blueprint static_url_path differs)
        try { await loadScript(`/static/users/template.js?v=${Date.now()}`); }
        catch (e2) { console.warn(e2); }
      }
    }
  }

  async function loadAgreementTemplatesIntoSelect(selectEl) {
    if (!selectEl) return;
    selectEl.innerHTML = `<option value="">${T.selectTemplate}</option>`;
    try {
      const tries = ["/users/api/agreements/templates", "/api/agreements/templates"];
      let data = null;
      for (const u of tries) {
        try { data = await fetchJSON(u); break; }
        catch { /* try next */ }
      }
      if (!data) return;
      (data.items || []).forEach(t => {
        const opt = document.createElement("option");
        opt.value = t.id;
        opt.textContent = `${t.name} (${t.type})`;
        selectEl.appendChild(opt);
      });
    } catch (_e) { /* silent */ }
  }

  // -------------------------------------------------------
  // Render pieces
  // -------------------------------------------------------
  function renderAttachmentList(a) {
    const list = Array.isArray(a.attachments) ? a.attachments : [];
    if (!list.length) return `<span class="text-muted">${T.noFiles}</span>`;
    return `<ul class="list-unstyled mb-0">
      ${list
        .map((x) => {
          const stored = x.stored_name || x.filename || "";
          const label = x.filename || stored;
          const href = `/users/agreements/file/${encodeURIComponent(stored)}`;
          return `<li><a class="attachment-link" href="${href}" target="_blank" rel="noopener">${label}</a></li>`;
        })
        .join("")}
    </ul>`;
  }

  function renderAgreementItem(userId, a) {
    const indef = isIndef(a);
    const monthsLabel = (a.months === 0 || a.months === "0") ? T.indefiniteBadge : `${a.months} месеци`;
    const headerText = indef
      ? `${a.start_date} → ${T.indefiniteBadge}`
      : `${a.start_date} → ${a.end_date} (${monthsLabel})`;

    const statusBadge =
      a.status === "active"
        ? `<span class="badge bg-success ms-2">${T.activeBadge}</span>`
        : `<span class="badge bg-secondary ms-2">${a.status}</span>`;

    const collapseId = `agr-${userId}-${a.id}`;

    const btns = [
      `<button type="button" class="btn btn-sm btn-outline-danger"
               data-action="agr-delete" data-user="${userId}" data-id="${a.id}">
         ${T.delete}
       </button>`,
      a.status === "active"
        ? `<button type="button" class="btn btn-sm btn-outline-warning"
                   data-action="agr-cancel" data-user="${userId}" data-id="${a.id}">
             ${T.cancel}
           </button>`
        : ``,
    ].join("");

    return `
      <div class="list-group-item">
        <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
          <button type="button" class="btn btn-sm btn-light"
                  data-bs-toggle="collapse" data-bs-target="#${collapseId}"
                  aria-expanded="false" aria-controls="${collapseId}">
            ${headerText} ${statusBadge} ${indef ? `<span class="badge bg-info ms-2">${T.indefiniteBadge}</span>` : ""}
          </button>
          <div class="btn-group btn-group-sm">${btns}</div>
        </div>

        <div id="${collapseId}" class="collapse mt-2">
          <div class="small text-muted mb-1">${T.filesTitle}</div>
          <div>${renderAttachmentList(a)}</div>

          <div class="mt-2">
            <button type="button" class="btn btn-sm btn-outline-primary"
                    data-action="agr-attach-toggle" data-id="${a.id}">
              ${T.attachFile}
            </button>
          </div>

          <div class="d-none" data-agr-attach-wrap="${a.id}">
            <form class="card card-body p-2" data-agr-attach-form="${a.id}">
              <div class="row g-2 align-items-end">
                <div class="col-md-8">
                  <input type="file" class="form-control form-control-sm" name="file">
                </div>
                <div class="col-md-4 d-flex gap-2">
                  <button type="button" class="btn btn-success btn-sm"
                          data-action="agr-attach-save" data-user="${userId}" data-id="${a.id}">
                    ${T.upload}
                  </button>
                  <button type="button" class="btn btn-outline-secondary btn-sm"
                          data-action="agr-attach-cancel" data-id="${a.id}">
                    ${T.close}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      </div>`;
  }

  function renderCreateHeader(userId) {
    const finId = `agr-create-${userId}`;
    const indId = `agr-indef-${userId}`;

    return `
      <div class="mb-3">

        <!-- Generate from Template toolbar -->
        <div class="card card-body p-3 mb-3" data-agr-tplbar="${userId}">
          <div class="row g-2 align-items-end">
            <div class="col-md-3">
              <label class="form-label">${T.template}</label>
              <select id="AgreementTemplateSelect-${userId}" class="form-select">
                <option value="">${T.selectTemplate}</option>
              </select>
            </div>
            <div class="col-md-3">
              <label class="form-label">${T.start}</label>
              <input id="AgreementStartDate-${userId}" type="date" class="form-control" value="${todayStr()}">
            </div>
            <div class="col-md-2">
              <label class="form-label">${T.months} (0=${T.indefiniteBadge})</label>
              <input id="AgreementMonths-${userId}" type="number" min="0" class="form-control" value="12">
            </div>
            <div class="col-md-3">
              <label class="form-label">${T.outputFilename}</label>
              <input id="AgreementFilename-${userId}" type="text" class="form-control" placeholder="Договор_${userId}.docx">
            </div>
            <div class="col-md-1 d-grid">
              <button class="btn btn-primary"
                      data-action="agr-generate-from-template" data-user="${userId}">
                ${T.generate}
              </button>
            </div>
          </div>
          <div class="mt-2">
            <button class="btn btn-outline-secondary btn-sm"
                    data-bs-toggle="modal" data-bs-target="#TemplatesModal">
              ${T.manageTemplates}
            </button>
          </div>
        </div>

        <div class="collapse mt-2" id="${finId}">
          <form class="card card-body p-3" data-agr-form="${userId}">
            <div class="row g-2 align-items-end">
              <div class="col-md-3">
                <label class="form-label">${T.start}</label>
                <input type="date" class="form-control" name="start_date" value="${todayStr()}" required>
                <div class="text-danger small" data-err="start_date"></div>
              </div>
              <div class="col-md-3">
                <label class="form-label">${T.months}</label>
                <input type="number" class="form-control" name="months" value="6" min="1" step="1" required>
                <div class="text-danger small" data-err="months"></div>
              </div>
              <div class="col-md-3">
                <label class="form-label">${T.endAuto}</label>
                <input type="text" class="form-control" name="end_preview" value="${plusMonths(todayStr(), 6)}" readonly>
              </div>
              <div class="col-md-3">
                <label class="form-label">${T.attachOptional}</label>
                <input type="file" class="form-control" name="file">
              </div>
            </div>
            <div class="mt-2 d-flex gap-2">
              <button type="button" class="btn btn-success btn-sm" data-action="agr-save" data-user="${userId}">${T.save}</button>
              <button type="button" class="btn btn-outline-secondary btn-sm"
                      data-action="agr-create-cancel" data-bs-toggle="collapse" data-bs-target="#${finId}">${T.close}</button>
            </div>
          </form>
        </div>

        <div class="collapse mt-2" id="${indId}">
          <form class="card card-body p-3" data-agr-indef-form="${userId}">
            <div class="row g-2 align-items-end">
              <div class="col-md-4">
                <label class="form-label">${T.start}</label>
                <input type="date" name="start_date" class="form-control" required value="${todayStr()}">
                <div class="form-text">${T.willCreateIndef}</div>
                <div class="text-danger small" data-err="start_date"></div>
              </div>
              <div class="col-md-4">
                <label class="form-label">${T.attachOptional}</label>
                <input type="file" class="form-control" name="file">
              </div>
              <div class="col-md-4 d-flex gap-2">
                <button type="button" class="btn btn-info btn-sm" data-action="agr-indef-save" data-user="${userId}">${T.save}</button>
                <button type="button" class="btn btn-outline-secondary btn-sm"
                        data-action="agr-indef-cancel" data-bs-toggle="collapse" data-bs-target="#${indId}">${T.close}</button>
              </div>
            </div>
          </form>
        </div>
      </div>
    `;
  }

  function renderBody(userId) {
    return `
      <h6 class="mt-3">${T.activeSection}</h6>
      <div class="list-group mb-3" data-agr-active="${userId}"></div>

      <h6>${T.historySection}</h6>
      <div class="list-group" data-agr-history="${userId}"></div>
    `;
  }

  function renderShell(userId) {
    return `${renderCreateHeader(userId)}${renderBody(userId)}`;
  }

  // -------------------------------------------------------
  // Fill lists
  // -------------------------------------------------------
  function fillAgreements(userId, payload, container) {
    const wrap = container || document.querySelector(`[data-agreements-wrap='${userId}']`);
    if (!wrap) return;
    wrap.innerHTML = renderShell(userId);

    const activeEl = wrap.querySelector(`[data-agr-active='${userId}']`);
    const histEl = wrap.querySelector(`[data-agr-history='${userId}']`);

    (payload.active || []).forEach((a) => (activeEl.innerHTML += renderAgreementItem(userId, a)));
    (payload.history || []).forEach((a) => (histEl.innerHTML += renderAgreementItem(userId, a)));
  }

  // -------------------------------------------------------
  // Mount
  // -------------------------------------------------------
  async function mount(userId, intoEl) {
    const el = intoEl || document.querySelector(`[data-agreements-wrap='${userId}']`);
    if (!el) return;

    el.innerHTML = `<div class="text-muted">${T.loading}</div>`;

    try {
      // 1) Load agreements and render UI
      const data = await apiGet(userId);
      fillAgreements(userId, data, el);

      // 2) Ensure templates modal + client generator are available
      try { await ensureTemplatesModalLoaded(); } catch (_e) {}

      // 3) Populate the templates dropdown in toolbar
      try {
        const sel = document.getElementById(`AgreementTemplateSelect-${userId}`);
        await loadAgreementTemplatesIntoSelect(sel);
      } catch (_e) {}
    } catch (err) {
      el.innerHTML = `<div class="text-danger">${T.loadError}: ${err.message || err}</div>`;
    }
  }
  window.mountAgreements = mount;

  // -------------------------------------------------------
  // Auto-mount on DOM ready / tab / dynamic injection
  // -------------------------------------------------------
  function initialScan() {
    $$("[data-agreements-wrap]").forEach((el) => {
      const uid = el.getAttribute("data-agreements-wrap");
      if (!uid || el.dataset._agreementsLoaded) return;
      el.dataset._agreementsLoaded = "1";
      mount(uid, el);
    });
  }
  if (document.readyState === "loading") {
    on(document, "DOMContentLoaded", initialScan);
  } else {
    initialScan();
  }

  on(document, "shown.bs.tab", (ev) => {
    const sel = ev.target?.getAttribute("data-bs-target") || ev.target?.getAttribute("href");
    if (!sel) return;
    const pane = document.querySelector(sel);
    const wrap = pane?.querySelector?.("[data-agreements-wrap]");
    if (!wrap) return;
    const uid = wrap.getAttribute("data-agreements-wrap");
    if (uid && !wrap.dataset._agreementsLoaded) {
      wrap.dataset._agreementsLoaded = "1";
      mount(uid, wrap);
    }
  });

  new MutationObserver((muts) => {
    muts.forEach((m) => {
      m.addedNodes.forEach((n) => {
        if (!(n instanceof Element)) return;
        if (n.matches?.("[data-agreements-wrap]")) {
          const uid = n.getAttribute("data-agreements-wrap");
          if (uid && !n.dataset._agreementsLoaded) {
            n.dataset._agreementsLoaded = "1";
            mount(uid, n);
          }
        }
        n.querySelectorAll?.("[data-agreements-wrap]").forEach((el) => {
          const uid = el.getAttribute("data-agreements-wrap");
          if (uid && !el.dataset._agreementsLoaded) {
            el.dataset._agreementsLoaded = "1";
            mount(uid, el);
          }
        });
      });
    });
  }).observe(document.documentElement, { childList: true, subtree: true });

  // -------------------------------------------------------
  // Actions (click handlers)
  // -------------------------------------------------------
  on(document, "click", async (e) => {
    const t = e.target.closest("[data-action]");
    if (!t) return;

    const rootWrap =
      t.closest("[data-agreements-wrap]") ||
      document.querySelector(`[data-agreements-wrap='${t.dataset.user || ""}']`) ||
      document;

    // Close (reset only; collapse is driven by data-bs-*)
    if (t.matches("[data-action='agr-create-cancel']") || t.matches("[data-action='agr-indef-cancel']")) {
      e.preventDefault();
      t.closest("form")?.reset();
      return;
    }

    // Update end_preview when editing finite create form
    const finForm = t.closest(`[data-agr-form]`);
    if (finForm) {
      const s = finForm.querySelector(`input[name='start_date']`)?.value;
      const m = Number(finForm.querySelector(`input[name='months']`)?.value || 0);
      const endPrev = finForm.querySelector(`input[name='end_preview']`);
      if (endPrev) endPrev.value = plusMonths(s, m);
    }

    // ---------- Save finite ----------
    if (t.matches("[data-action='agr-save']")) {
      e.preventDefault();
      const btn = t;
      if (btn.disabled) return;
      btn.disabled = true;
      const uid = Number(btn.dataset.user);
      const form = rootWrap.querySelector(`[data-agr-form='${uid}']`);

      try {
        const fd = new FormData(form);
        const file = fd.get("file");
        const payload = {
          start_date: (fd.get("start_date") || "").trim(),
          months: Number(fd.get("months") || 0),
        };

        const created = await apiPost(uid, "create", payload);
        const newId = created?.agreement?.id ?? created?.id;
        let agreementId = newId;
        if (!agreementId) {
          const list = await apiGet(uid);
          const all = [...(list.active || []), ...(list.history || [])];
          const sameStart = all.filter(a => a.start_date === payload.start_date);
          agreementId = (sameStart.length ? sameStart : all).reduce((m, a) => a.id > m ? a.id : m, 0);
        }

        if (file && file.size > 0) {
          const up = new FormData();
          up.append("file", file);
          up.append("agreement_id", String(agreementId));
          await apiAttach(uid, up);
        }

        toast("Успешно креиран договор.", "success");
        form.reset();

        const finId = `#agr-create-${uid}`;
        try {
          const node = document.querySelector(finId);
          if (node && window.bootstrap?.Collapse) {
            window.bootstrap.Collapse.getOrCreateInstance(node).hide();
          }
        } catch {}

        const data = await apiGet(uid);
        const wrap = rootWrap.closest("[data-agreements-wrap]") || document.querySelector(`[data-agreements-wrap='${uid}']`);
        fillAgreements(uid, data, wrap);
      } catch (err) {
        toast(`${T.errCreate}: ${err.message || err}`, "error", 2800);
      } finally {
        btn.disabled = false;
      }
      return;
    }

    // ---------- Save indefinite ----------
    if (t.matches("[data-action='agr-indef-save']")) {
      e.preventDefault();
      const btn = t;
      if (btn.disabled) return;
      btn.disabled = true;
      const uid = Number(btn.dataset.user);
      const form = rootWrap.querySelector(`[data-agr-indef-form='${uid}']`);

      try {
        const fd = new FormData(form);
        const file = fd.get("file");
        const payload = { start_date: (fd.get("start_date") || "").trim() };

        const created = await apiPost(uid, "create_indefinite", payload);
        const newId = created?.agreement?.id ?? created?.id;
        let agreementId = newId;
        if (!agreementId) {
          const list = await apiGet(uid);
          const all = [...(list.active || []), ...(list.history || [])];
          const sameStart = all.filter(a => a.start_date === payload.start_date);
          agreementId = (sameStart.length ? sameStart : all).reduce((m, a) => a.id > m ? a.id : m, 0);
        }

        if (file && file.size > 0) {
          const up = new FormData();
          up.append("file", file);
          up.append("agreement_id", String(agreementId));
          await apiAttach(uid, up);
        }

        toast("Успешно креиран неопределен договор.", "success");
        form.reset();

        const indId = `#agr-indef-${uid}`;
        try {
          const node = document.querySelector(indId);
          if (node && window.bootstrap?.Collapse) {
            window.bootstrap.Collapse.getOrCreateInstance(node).hide();
          }
        } catch {}

        const data = await apiGet(uid);
        const wrap = rootWrap.closest("[data-agreements-wrap]") || document.querySelector(`[data-agreements-wrap='${uid}']`);
        fillAgreements(uid, data, wrap);
      } catch (err) {
        toast(`${T.errCreate}: ${err.message || err}`, "error", 2800);
      } finally {
        btn.disabled = false;
      }
      return;
    }

    // ---------- Generate from Template ----------
    if (t.matches("[data-action='agr-generate-from-template']")) {
      e.preventDefault();
      const btn = t;
      if (btn.disabled) return;
      btn.disabled = true;

      const uid = Number(btn.dataset.user);
      const sel = document.getElementById(`AgreementTemplateSelect-${uid}`);
      const startDate = document.getElementById(`AgreementStartDate-${uid}`)?.value || "";
      const months = document.getElementById(`AgreementMonths-${uid}`)?.value || 0;
      const filename = document.getElementById(`AgreementFilename-${uid}`)?.value || "";

      try {
        const templateId = sel?.value || "";
        if (!templateId) throw new Error("Изберете шаблон.");
        if (!startDate) throw new Error("Изберете почетен датум.");

        if (typeof window.generateAgreementFromTemplate !== "function") {
          // try to load on the fly (in case it wasn't loaded yet)
          try {
            await loadScript(`/users/static/template.js?v=${Date.now()}`);
          } catch (_e) {}
        }
        if (typeof window.generateAgreementFromTemplate !== "function") {
          throw new Error("Модулот за шаблони не е вчитан.");
        }

        await window.generateAgreementFromTemplate(uid, templateId, startDate, months, filename);

        const fresh = await apiGet(uid);
        const wrap = rootWrap.closest("[data-agreements-wrap]") || document.querySelector(`[data-agreements-wrap='${uid}']`);
        fillAgreements(uid, fresh, wrap);

        try {
          const sel2 = document.getElementById(`AgreementTemplateSelect-${uid}`);
          await loadAgreementTemplatesIntoSelect(sel2);
        } catch (_e) {}

        toast("Генерираниот договор е зачуван и прикачен.", "success");
      } catch (err) {
        toast(`${T.errCreate}: ${err.message || err}`, "error", 2800);
      } finally {
        btn.disabled = false;
      }
      return;
    }

    // ---------- Attach toggle/cancel/save ----------
    if (t.matches("[data-action='agr-attach-toggle']")) {
      e.preventDefault();
      const id = Number(t.dataset.id);
      rootWrap.querySelector(`[data-agr-attach-wrap='${id}']`)?.classList.toggle("d-none");
      return;
    }
    if (t.matches("[data-action='agr-attach-cancel']")) {
      e.preventDefault();
      t.closest("[data-agr-attach-wrap]")?.classList.add("d-none");
      return;
    }
    if (t.matches("[data-action='agr-attach-save']")) {
      e.preventDefault();
      const btn = t;
      if (btn.disabled) return;
      btn.disabled = true;
      const uid = Number(btn.dataset.user);
      const id = Number(btn.dataset.id);
      const form = rootWrap.querySelector(`[data-agr-attach-form='${id}']`);
      try {
        const fd = new FormData(form);
        const file = fd.get("file");
        if (!file || file.size <= 0) throw new Error("Нема избрана датотека");

        const up = new FormData();
        up.append("file", file);
        up.append("agreement_id", String(id));
        await apiAttach(uid, up);

        toast("Датотеката е прикачена.", "success");
        form.reset();
        form.closest("[data-agr-attach-wrap]")?.classList.add("d-none");
        const data = await apiGet(uid);
        const wrap = rootWrap.closest("[data-agreements-wrap]") || document.querySelector(`[data-agreements-wrap='${uid}']`);
        fillAgreements(uid, data, wrap);
      } catch (err) {
        toast(`${T.errAttach}: ${err.message || err}`, "error", 2800);
      } finally {
        btn.disabled = false;
      }
      return;
    }

    // ---------- Cancel agreement ----------
    if (t.matches("[data-action='agr-cancel']")) {
      e.preventDefault();
      const btn = t;
      if (btn.disabled) return;
      if (!confirm(T.confirmCancel)) return;
      btn.disabled = true;
      const uid = Number(btn.dataset.user);
      const id = Number(btn.dataset.id);
      try {
        await apiPost(uid, `${id}/cancel`, {});
        toast("Договорот е откажан.", "success");
        const data = await apiGet(uid);
        const wrap = rootWrap.closest("[data-agreements-wrap]") || document.querySelector(`[data-agreements-wrap='${uid}']`);
        fillAgreements(uid, data, wrap);
      } catch (err) {
        toast(`${T.errCancel}: ${err.message || err}`, "error", 2800);
      } finally {
        btn.disabled = false;
      }
      return;
    }

    // ---------- Delete agreement ----------
    if (t.matches("[data-action='agr-delete']")) {
      e.preventDefault();
      const btn = t;
      if (btn.disabled) return;
      if (!confirm(T.confirmDelete)) return;
      btn.disabled = true;
      const uid = Number(btn.dataset.user);
      const id = Number(btn.dataset.id);
      try {
        await apiPost(uid, `${id}/delete`, {});
        toast("Договорот е избришан.", "success");
        const data = await apiGet(uid);
        const wrap = rootWrap.closest("[data-agreements-wrap]") || document.querySelector(`[data-agreements-wrap='${uid}']`);
        fillAgreements(uid, data, wrap);
      } catch (err) {
        toast(`${T.errDelete}: ${err.message || err}`, "error", 2800);
      } finally {
        btn.disabled = false;
      }
      return;
    }
  });
})();
