// app/users/static/users.js
(function () {
  "use strict";

  // ---- Permission flags (left as-is, but safe default) ----
  const PERMS = (window.USERS_PERMS =
    window.USERS_PERMS || { view: false, createEdit: false, tabs: {} });

  // ---- Global namespace ----
  const UsersApp = (window.UsersApp = window.UsersApp || {});
  UsersApp.helpers = UsersApp.helpers || {};
  UsersApp.api = UsersApp.api || {};

  // ========== Core Helpers (robust + exported) ==========
  function getMetaCsrf() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  }

  async function fetchJSON(url, opts) {
    const res = await fetch(url, { credentials: "same-origin", ...(opts || {}) });

    // Try JSON either way
    let data = null;
    try {
      data = await res.json();
    } catch (_) {
      /* non-JSON; leave null */
    }

    // Treat res.ok=false OR {ok:false} as error
    if (!res.ok || (data && data.ok === false)) {
      const detail =
        (data && (data.error_detail || data.message || data.error)) ||
        `HTTP ${res.status}`;
      const err = new Error(detail);
      err.status = res.status;
      err.payload = data;
      throw err;
    }

    return data ?? {};
  }

  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getMetaCsrf(),
      },
      body: JSON.stringify(body || {}),
    });

    let data = null;
    try {
      data = await res.json();
    } catch (_) {}

    if (!res.ok || (data && data.ok === false)) {
      const detail =
        (data && (data.error_detail || data.message || data.error)) ||
        `HTTP ${res.status}`;
      const err = new Error(detail);
      err.status = res.status;
      err.payload = data;
      throw err;
    }

    return data ?? {};
  }

  function clearErrors(form) {
    form?.querySelectorAll("[data-err]").forEach((e) => (e.textContent = ""));
  }

  function setErrors(form, errs) {
    Object.entries(errs || {}).forEach(([name, msg]) => {
      const el = form?.querySelector(`[data-err="${name}"]`);
      if (el) el.textContent = msg || "";
    });
  }

  function showAlert(container, message, type = "danger") {
    if (!container) return;
    container.innerHTML = `
      <div class="alert alert-${type} my-2" role="alert">${message}</div>
    `;
  }

  // ---- Export helpers everywhere for back-compat ----
  UsersApp.getMetaCsrf = getMetaCsrf;
  UsersApp.fetchJSON = fetchJSON;
  UsersApp.postJSON = postJSON;
  UsersApp.clearErrors = clearErrors;
  UsersApp.setErrors = setErrors;
  UsersApp.showAlert = showAlert;

  UsersApp.helpers.getMetaCsrf = getMetaCsrf;
  UsersApp.helpers.fetchJSON = fetchJSON;
  UsersApp.helpers.postJSON = postJSON;
  UsersApp.helpers.clearErrors = clearErrors;
  UsersApp.helpers.setErrors = setErrors;
  UsersApp.helpers.showAlert = showAlert;

  UsersApp.api.getMetaCsrf = getMetaCsrf;
  UsersApp.api.fetchJSON = fetchJSON;
  UsersApp.api.postJSON = postJSON;
  UsersApp.api.clearErrors = clearErrors;
  UsersApp.api.setErrors = setErrors;
  UsersApp.api.showAlert = showAlert;

  // ========== Global dispatcher (idempotent) ==========
  const _clickHandlers = (UsersApp._clickHandlers =
    UsersApp._clickHandlers || new Set());
  const _inputHandlers = (UsersApp._inputHandlers =
    UsersApp._inputHandlers || new Set());

  UsersApp.registerClick = (fn) => {
    if (typeof fn === "function") _clickHandlers.add(fn);
  };
  UsersApp.registerInput = (fn) => {
    if (typeof fn === "function") _inputHandlers.add(fn);
  };

  if (!window.__usersAppBound__) {
    document.addEventListener(
      "click",
      async (ev) => {
        for (const fn of _clickHandlers) {
          try {
            const stop = await fn(ev);
            if (stop === true) return;
          } catch (err) {
            console.error(err);
          }
        }
      },
      true
    );

    document.addEventListener(
      "input",
      async (ev) => {
        for (const fn of _inputHandlers) {
          try {
            const stop = await fn(ev);
            if (stop === true) return;
          } catch (err) {
            console.error(err);
          }
        }
      },
      true
    );

    window.__usersAppBound__ = true;
  }

  // ========== Small CSS tweak ==========
  (function injectStyleOnce() {
    if (document.getElementById("usersapp-style")) return;
    const style = document.createElement("style");
    style.id = "usersapp-style";
    style.textContent = `
      .btn, .btn:focus, .btn:hover { text-decoration: none !important; }
      a.attachment-link { text-decoration: underline; }
    `;
    document.head.appendChild(style);
  })();

  // ========== Admin helpers (unchanged behavior) ==========
  const AdminUI = (UsersApp.admin = UsersApp.admin || {});
  AdminUI.getCreateIsAdmin = () =>
    !!document.getElementById("CreateIsAdmin")?.checked;
  AdminUI.getEditIsAdmin = () =>
    !!document.getElementById("EditIsAdmin")?.checked;
  AdminUI.setEditAdminFromUser = (user) => {
    const chk = document.getElementById("EditIsAdmin");
    const hid = document.getElementById("EditIsAdminHidden");
    const isAdmin =
      !!user?.is_admin ||
      (typeof user?.role === "string" && user.role.toLowerCase() === "admin");
    if (chk) chk.checked = isAdmin;
    if (hid) hid.value = isAdmin ? "1" : "";
  };

  // Keep hidden fields in sync so form-serializers can pick it up
  document.addEventListener(
    "change",
    (ev) => {
      const t = ev.target;
      if (t?.id === "CreateIsAdmin") {
        const hid = document.getElementById("CreateIsAdminHidden");
        if (hid) hid.value = t.checked ? "1" : "";
      }
      if (t?.id === "EditIsAdmin") {
        const hid = document.getElementById("EditIsAdminHidden");
        if (hid) hid.value = t.checked ? "1" : "";
      }
    },
    true
  );

  // Enforce hidden values right before submit (in case no change fired)
  document.addEventListener(
    "submit",
    (ev) => {
      const f = ev.target;
      if (!(f instanceof HTMLFormElement)) return;
      if (f.id === "CreateUserForm") {
        const chk = document.getElementById("CreateIsAdmin");
        const hid = document.getElementById("CreateIsAdminHidden");
        if (hid) hid.value = chk?.checked ? "1" : "";
      }
      if (f.id === "EditUserForm") {
        const chk = document.getElementById("EditIsAdmin");
        const hid = document.getElementById("EditIsAdminHidden");
        if (hid) hid.value = chk?.checked ? "1" : "";
      }
    },
    true
  );

  // ========== Universal attachment upload helper ==========
  async function uploadAttachments(userId, { files, ...context }) {
    const up = new FormData();

    // Accept FileList, File[], or input[type=file]
    let list = [];
    if (files instanceof FileList) list = Array.from(files);
    else if (Array.isArray(files)) list = files;
    else if (files && files.tagName === "INPUT") list = Array.from(files.files || []);
    else if (files) list = [files];

    if (!list.length) throw new Error("No files selected");

    for (const f of list) up.append("files", f);

    // Extra context fields
    Object.entries(context || {}).forEach(([k, v]) => {
      if (v != null && v !== "") up.append(k, String(v));
    });

    const res = await fetch(`/users/api/attachments/${userId}`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": getMetaCsrf() },
      body: up,
    });

    let data = null;
    try {
      data = await res.json();
    } catch (_) {}

    if (!res.ok || (data && data.ok === false)) {
      const msg =
        (data && (data.error_detail || data.message || data.error)) ||
        `HTTP ${res.status}`;
      throw new Error(msg);
    }

    return data ?? {};
  }

  UsersApp.uploadAttachments = uploadAttachments;
  UsersApp.helpers.uploadAttachments = uploadAttachments;

  // ========== CREATE form handler (respects PERMS) ==========
  document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("CreateUserForm");
    const createWrap = document.getElementById("CreateUserWrap");

    // Extra guard: hide create area if no permission
    if (createWrap && !PERMS.createEdit) {
      createWrap.classList.add("d-none");
    }
    if (!form) return;
    if (!PERMS.createEdit) return; // don't bind if not allowed
    if (form.dataset.bound === "create") return;
    form.dataset.bound = "create";

    form.addEventListener("submit", async function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      ev.stopImmediatePropagation();

      if (!form.checkValidity()) {
        form.reportValidity();
        return;
      }

      // Use exported helpers (with fallbacks)
      const A = window.UsersApp || {};
      const _clearErrors = A.clearErrors || A.helpers?.clearErrors || function () {};
      const _setErrors = A.setErrors || A.helpers?.setErrors || function () {};
      const _postJSON = A.postJSON || A.helpers?.postJSON || _fallbackPostJSON;

      _clearErrors(form);

      const body = {
        first_name: form.first_name?.value || "",
        last_name: form.last_name?.value || "",
        email: form.email?.value || "",
        password: form.password?.value || "",
        password2: form.password2?.value || "",
        phone_number: form.phone_number?.value || "",
        id_number: form.id_number?.value || "",
        embg: form.embg?.value || "",
        vacation_days: form.vacation_days?.value || "0",
        bank_account: form.bank_account?.value || "",
        city: form.city?.value || "",
        address: form.address?.value || "",
        is_admin: !!document.getElementById("CreateIsAdmin")?.checked,
      };

      try {
        const res = await _postJSON("/users/api/create", body);
        const u = res.item || {};

        document.getElementById("CreateUserWrap")?.classList.add("d-none");
        form.reset();

        // Keep a little cache if you use it elsewhere
        window.__usersById = window.__usersById || {};
        if (u?.id != null) window.__usersById[u.id] = u;

        // Optional: render general if present
        if (window.UsersApp?.api?.renderGeneral) {
          const generalContainer =
            document.querySelector("[data-general-wrap]") ||
            document.querySelector('[data-tab="general"]');
          if (generalContainer) window.UsersApp.api.renderGeneral(u, generalContainer);
        }
      } catch (err) {
        // Prefer structured field errors
        const p = err.payload || {};
        if (p && p.errors && typeof p.errors === "object") {
          _setErrors(form, p.errors);
          return;
        }
        // Try parse message as JSON
        try {
          const parsed = JSON.parse(err.message || "{}");
          if (parsed.errors) {
            _setErrors(form, parsed.errors);
            return;
          }
        } catch {}
        const anyErr = form.querySelector('[data-err="__global"]');
        if (anyErr) anyErr.textContent = String(err?.message || "Create failed");
        console.error(err);
      }
    });
  });

  // ---- Fallback small POST util (rarely used) ----
  async function _fallbackPostJSON(url, body) {
    const res = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken":
          document.querySelector('meta[name="csrf-token"]')?.content || "",
      },
      body: JSON.stringify(body || {}),
    });
    let data = null;
    try {
      data = await res.json();
    } catch (_) {}
    if (!res.ok || (data && data.ok === false)) {
      const detail =
        (data && (data.error_detail || data.message || data.error)) ||
        `HTTP ${res.status}`;
      const err = new Error(detail);
      err.status = res.status;
      err.payload = data;
      throw err;
    }
    return data ?? {};
  }
})();
