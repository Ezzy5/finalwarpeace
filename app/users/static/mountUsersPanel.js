// app/users/static/mountUsersPanel.js
(function () {
  "use strict";

  // ---------- Namespace & helpers ----------
  const UA = (window.UsersApp = window.UsersApp || {});
  UA.helpers = UA.helpers || {};
  const H = UA.helpers;

  const getMetaCsrf =
    H.getMetaCsrf ||
    function () {
      const m = document.querySelector('meta[name="csrf-token"]');
      return m ? m.getAttribute("content") : "";
    };

  const fetchJSON =
    H.fetchJSON ||
    (async function (url, opts) {
      const res = await fetch(url, { credentials: "same-origin", ...(opts || {}) });
      let data = null;
      try { data = await res.json(); } catch (_) {}
      if (!res.ok || (data && data.ok === false)) {
        const detail =
          (data && (data.error_detail || data.message || data.error)) ||
          res.statusText || `HTTP ${res.status}`;
        const err = new Error(detail);
        err.status = res.status;
        err.payload = data;
        throw err;
      }
      return data ?? {};
    });

  const postJSON =
    H.postJSON ||
    (async function (url, body) {
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
      try { data = await res.json(); } catch (_) {}
      if (!res.ok || (data && data.ok === false)) {
        const detail =
          (data && (data.error_detail || data.message || data.error)) ||
          res.statusText || `HTTP ${res.status}`;
        const err = new Error(detail);
        err.status = res.status;
        err.payload = data;
        throw err;
      }
      return data ?? {};
    });

  const clearErrors =
    H.clearErrors ||
    function (form) {
      form?.querySelectorAll("[data-err]").forEach((e) => (e.textContent = ""));
    };

  const setErrors =
    H.setErrors ||
    function (form, errs) {
      Object.entries(errs || {}).forEach(([name, msg]) => {
        const el = form?.querySelector(`[data-err="${name}"]`);
        if (el) el.textContent = msg || "";
      });
    };

  const showAlert =
    H.showAlert ||
    function (container, message, type = "danger") {
      if (!container) return;
      container.innerHTML = `
        <div class="alert alert-${type} my-2" role="alert">${message}</div>
      `;
    };

  // ---------- Safe Tab Handling ----------
  function safeShowTab(a) {
    if (!a) return;
    const targetSel = a.getAttribute("data-bs-target") || a.getAttribute("href");
    if (!targetSel || !targetSel.startsWith("#")) return;

    try {
      if (window.bootstrap && typeof window.bootstrap.Tab === "function") {
        const tab = window.bootstrap.Tab.getOrCreateInstance(a);
        tab.show();
        return;
      }
      throw new Error("Bootstrap not available or failed");
    } catch {
      const nav = a.closest("[role='tablist']") || a.closest(".nav");
      if (!nav) return;
      nav
        .querySelectorAll("[data-bs-toggle='pill'],[data-bs-toggle='tab']")
        .forEach((el) => {
          el.classList.remove("active");
          const sel =
            el.getAttribute("data-bs-target") || el.getAttribute("href");
          if (sel && sel.startsWith("#")) {
            const pane = document.querySelector(sel);
            if (pane) pane.classList.remove("show", "active");
          }
        });
      a.classList.add("active");
      const pane = document.querySelector(targetSel);
      if (pane) pane.classList.add("active", "show");
    }
  }

  // ---------- tiny utils ----------
  function statusBadgeHTML(u) {
    return u.is_suspended
      ? `<span class="badge bg-warning text-dark ms-2" data-status-badge>SUSPENDED</span>`
      : "";
  }

  function rowHTMLList(u, index) {
    const attrs = [
      `data-id="${u.id}"`,
      `data-email="${u.email ?? ""}"`,
      `data-phone="${u.phone_number ?? ""}"`,
      `data-idnumber="${u.id_number ?? ""}"`,
      `data-embg="${u.embg ?? ""}"`,
      `data-vacdays="${u.vacation_days ?? 0}"`,
      `data-department="${u.department ?? ""}"`,
      `data-director_of="${u.director_of ?? ""}"`,
      `data-suspended="${u.is_suspended ? "1" : "0"}"`,
    ].join(" ");

    const deptHTML = `
      <div data-department-text>${u.department ?? ""}</div>
      ${
        u.director_of
          ? `<div class="small text-muted" data-director-badge>Director of <span class="fw-semibold">${u.director_of}</span></div>`
          : ""
      }
      ${statusBadgeHTML(u)}
    `;

    const actionBtn = u.is_suspended
      ? `<button type="button" class="btn btn-sm btn-outline-success" data-action="unsuspend" data-id="${u.id}">Unsuspend</button>`
      : `<button type="button" class="btn btn-sm btn-outline-warning" data-action="suspend" data-id="${u.id}">Suspend</button>`;

    const rowClass = `user-row ${u.is_suspended ? "opacity-50" : ""}`;

    return `
      <tr class="${rowClass}" ${attrs} style="cursor:pointer;">
        <td class="text-muted">${index}</td>
        <td>${u.first_name ?? ""}</td>
        <td>${u.last_name ?? ""}</td>
        <td>${deptHTML}</td>
        <td class="text-end actions" style="white-space:nowrap;">
          <button type="button" class="btn btn-sm btn-outline-primary" data-action="edit" data-id="${u.id}">Edit</button>
          ${actionBtn}
        </td>
      </tr>
    `;
  }

  function suspendedBannerHTML() {
    return `
      <div class="alert alert-warning d-flex align-items-center gap-2 mb-3" role="alert" data-suspended-banner>
        <i class="bi bi-exclamation-triangle-fill"></i>
        <div>This user is <strong>suspended</strong> and cannot sign in.</div>
      </div>
    `;
  }

  function detailTabsHTML(u) {
    return `
      <tr class="table-active user-detail-row" data-detail-for="${u.id}">
        <td colspan="5" class="p-0">
          <div class="p-3" data-user-card>
            ${u.is_suspended ? suspendedBannerHTML() : ""}
            <ul class="nav nav-pills mb-3" role="tablist">
              <li class="nav-item"><a class="nav-link active" data-bs-toggle="pill" href="#tab-general-${u.id}">General</a></li>
              <li class="nav-item"><a class="nav-link" data-bs-toggle="pill" href="#tab-agreements-${u.id}">Agreements</a></li>
              <li class="nav-item"><a class="nav-link" data-bs-toggle="pill" href="#tab-vacation-${u.id}">Vacation</a></li>
              <li class="nav-item"><a class="nav-link" data-bs-toggle="pill" href="#tab-sick-${u.id}">Боледување</a></li>
              <li class="nav-item"><a class="nav-link" data-bs-toggle="pill" href="#tab-report-${u.id}">Извештај</a></li>
              <li class="nav-item"><a class="nav-link" data-bs-toggle="pill" href="#tab-uniforms-${u.id}">Униформи</a></li>
              <li class="nav-item"><a class="nav-link" data-bs-toggle="pill" href="#tab-training-${u.id}">Обука</a></li>
              <li class="nav-item"><a class="nav-link" data-bs-toggle="pill" href="#tab-rewards-${u.id}">Казни и Награди</a></li>
            </ul>
            <div class="tab-content">
              <div class="tab-pane fade show active" id="tab-general-${u.id}">
                <div data-general-wrap="${u.id}"></div>
              </div>
              <div class="tab-pane fade" id="tab-agreements-${u.id}"><div data-agreements-wrap="${u.id}"></div></div>
              <div class="tab-pane fade" id="tab-vacation-${u.id}"><div data-vac-wrap="${u.id}"></div></div>
              <div class="tab-pane fade" id="tab-sick-${u.id}"><div data-sick-wrap="${u.id}"></div></div>
              <div class="tab-pane fade" id="tab-report-${u.id}"><div data-report-wrap="${u.id}"></div></div>
              <div class="tab-pane fade" id="tab-uniforms-${u.id}"><div data-uniform-wrap="${u.id}"></div></div>
              <div class="tab-pane fade" id="tab-training-${u.id}"><div data-training-wrap="${u.id}"></div></div>
              <div class="tab-pane fade" id="tab-rewards-${u.id}"><div data-rewards-wrap="${u.id}"></div></div>
            </div>
          </div>
        </td>
      </tr>
    `;
  }

  // ---------- Data: list loader ----------
  async function loadList(state) {
    const tbody = state.root.querySelector("#UsersTable");
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="5" class="text-muted">Loading…</td></tr>`;

    const API_BASE = state.apiBase;

    try {
      const data = await fetchJSON(
        `${API_BASE}/list?page=${state.page}&per_page=${state.pageSize}`
      );
      const items = Array.isArray(data.items) ? data.items
                  : Array.isArray(data.users) ? data.users
                  : [];
      tbody.innerHTML = "";
      items.forEach((u, i) =>
        tbody.insertAdjacentHTML("beforeend", rowHTMLList(u, i + 1))
      );
      if (!items.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-muted">No users found</td></tr>`;
      }
    } catch (e) {
      tbody.innerHTML = `
        <tr><td colspan="5">
          <div class="alert alert-danger my-2" role="alert">
            Failed to load users. ${e.message || ""}
          </div>
        </td></tr>
      `;
      console.error("User list load failed:", e.status || 0, e.message, e.payload);
    }
  }

  // ---------- Lazy mount for panes ----------
  function ensurePaneMounted(userId, paneEl) {
    if (!paneEl || paneEl.__mounted) return;

    const wrap =
      paneEl.querySelector(`[data-general-wrap='${userId}']`) ||
      paneEl.querySelector(`[data-agreements-wrap='${userId}']`) ||
      paneEl.querySelector(`[data-vac-wrap='${userId}']`) ||
      paneEl.querySelector(`[data-sick-wrap='${userId}']`) ||
      paneEl.querySelector(`[data-report-wrap='${userId}']`) ||
      paneEl.querySelector(`[data-uniform-wrap='${userId}']`) ||
      paneEl.querySelector(`[data-training-wrap='${userId}']`) ||
      paneEl.querySelector(`[data-rewards-wrap='${userId}']`);

    if (!wrap) {
      paneEl.__mounted = true;
      return;
    }

    if (wrap.hasAttribute("data-rewards-wrap")) {
      if (typeof window.renderRewards === "function") {
        window.renderRewards(userId, wrap);
      } else {
        showAlert(wrap, "Rewards module not loaded.", "warning");
      }
      paneEl.__mounted = true;
      return;
    }

    if (wrap.hasAttribute("data-agreements-wrap")) {
      if (typeof window.renderAgreements === "function")
        window.renderAgreements(userId, wrap);
    } else if (wrap.hasAttribute("data-vac-wrap")) {
      if (typeof window.renderVacation === "function")
        window.renderVacation(userId, wrap);
    } else if (wrap.hasAttribute("data-sick-wrap")) {
      if (typeof window.renderSick === "function")
        window.renderSick(userId, wrap);
    } else if (wrap.hasAttribute("data-report-wrap")) {
      if (typeof window.renderReports === "function")
        window.renderReports(userId, wrap);
    } else if (wrap.hasAttribute("data-uniform-wrap")) {
      if (typeof window.renderUniforms === "function")
        window.renderUniforms(userId, wrap);
    } else if (wrap.hasAttribute("data-training-wrap")) {
      if (typeof window.renderTrainings === "function")
        window.renderTrainings(userId, wrap);
    } else if (wrap.hasAttribute("data-general-wrap")) {
      if (typeof window.renderGeneral === "function") {
        const row = document.querySelector(`tr.user-row[data-id='${userId}']`);
        const u = row
          ? {
              id: userId,
              first_name: row.children[1]?.textContent?.trim() || "",
              last_name: row.children[2]?.textContent?.trim() || "",
              department:
                row.querySelector("[data-department-text]")?.textContent?.trim() || "",
              email: row.dataset.email || "",
              phone_number: row.dataset.phone || "",
              id_number: row.dataset.idnumber || "",
              embg: row.dataset.embg || "",
              vacation_days: Number(row.dataset.vacdays || 0),
              director_of: row.dataset.director_of || "",
              is_suspended: row.dataset.suspended === "1",
            }
          : { id: userId };
        window.renderGeneral(u, wrap);
      }
    }

    paneEl.__mounted = true;
  }

  // ---------- list events + detail open ----------
  function wireListEvents(state) {
    const root = state.root;
    const API_BASE = state.apiBase;

    root.addEventListener("click", async (e) => {
      const t = e.target;

      // Handle tab clicks safely
      const tabLink = t.closest("[data-bs-toggle='pill'],[data-bs-toggle='tab']");
      if (tabLink) {
        e.preventDefault();
        const trDetail = tabLink.closest("tr.user-detail-row");
        const userId = trDetail ? Number(trDetail.getAttribute("data-detail-for")) : null;
        safeShowTab(tabLink);
        const targetSel = tabLink.getAttribute("data-bs-target") || tabLink.getAttribute("href");
        if (userId && targetSel) ensurePaneMounted(userId, document.querySelector(targetSel));
        return;
      }

      // Suspend / Unsuspend
      const susBtn = t.closest("[data-action='suspend']");
      const unsBtn = t.closest("[data-action='unsuspend']");
      if (susBtn || unsBtn) {
        e.preventDefault();
        const id = Number((susBtn || unsBtn).dataset.id);
        const suspend = !!susBtn;
        try {
          await postJSON(`${API_BASE}/suspend/${id}`, { suspended: suspend });

          // Update row UI
          const row = root.querySelector(`tr.user-row[data-id='${id}']`);
          if (row) {
            row.dataset.suspended = suspend ? "1" : "0";
            row.classList.toggle("opacity-50", suspend);

            const cell = row.querySelector("td:nth-child(4)");
            const existingBadge = cell?.querySelector("[data-status-badge]");
            if (suspend) {
              if (!existingBadge && cell) {
                cell.insertAdjacentHTML(
                  "beforeend",
                  `<span class="badge bg-warning text-dark ms-2" data-status-badge>SUSPENDED</span>`
                );
              }
            } else {
              existingBadge?.remove();
            }

            const actions = row.querySelector(".actions");
            if (actions) {
              actions.querySelector("[data-action='suspend'],[data-action='unsuspend']")?.remove();
              actions.insertAdjacentHTML(
                "beforeend",
                suspend
                  ? ` <button type="button" class="btn btn-sm btn-outline-success" data-action="unsuspend" data-id="${id}">Unsuspend</button>`
                  : ` <button type="button" class="btn btn-sm btn-outline-warning" data-action="suspend" data-id="${id}">Suspend</button>`
              );
            }
          }

          // Update open detail banner if present
          const card = root.querySelector(`tr.user-detail-row[data-detail-for='${id}'] [data-user-card]`);
          if (card) {
            const banner = card.querySelector("[data-suspended-banner]");
            if (suspend) {
              if (!banner) card.insertAdjacentHTML("afterbegin", suspendedBannerHTML());
            } else {
              banner?.remove();
            }
          }
        } catch (err) {
          alert(err.message || "Suspend action failed");
        }
        return;
      }

      // Edit (open modal + populate)
      const editBtn = t.closest("[data-action='edit']");
      if (editBtn) {
        e.preventDefault();
        const row = editBtn.closest("tr.user-row");
        if (!row) return;
        const id = Number(row.dataset.id);

        const mId = document.querySelector("#EditUserId");
        const mFirst = document.querySelector("#EditFirstName");
        const mLast = document.querySelector("#EditLastName");
        const mEmail = document.querySelector("#EditEmail");
        const mPhone = document.querySelector("#EditPhone");
        const mIdn = document.querySelector("#EditIdNumber");
        const mEmbg = document.querySelector("#EditEmbg");
        const mVac = document.querySelector("#EditVacationDays");

        if (mId) mId.value = id;
        if (mFirst) mFirst.value = row.children[1].textContent.trim();
        if (mLast) mLast.value = row.children[2].textContent.trim();
        if (mEmail) mEmail.value = row.dataset.email || "";
        if (mPhone) mPhone.value = row.dataset.phone || "";
        if (mIdn) mIdn.value = row.dataset.idnumber || "";
        if (mEmbg) mEmbg.value = row.dataset.embg || "";
        if (mVac) mVac.value = row.dataset.vacdays || "0";

        const modalEl = document.querySelector("#userEditModal");
        if (modalEl && window.bootstrap?.Modal) {
          const inst = window.bootstrap.Modal.getOrCreateInstance(modalEl);
          inst.show();
        }
        return;
      }

      // Open/close detail row
      const tr = t.closest("tr.user-row");
      if (tr && !t.closest("button")) {
        const id = Number(tr.dataset.id);
        const open = root.querySelector(`tr.user-detail-row[data-detail-for='${id}']`);
        if (open) {
          open.remove();
          return;
        }

        // Close others (optional)
        root.querySelectorAll("tr.user-detail-row").forEach((r) => r.remove());

        const u = {
          id,
          first_name: tr.children[1].textContent.trim(),
          last_name: tr.children[2].textContent.trim(),
          department: tr.querySelector("[data-department-text]")?.textContent?.trim() || "",
          email: tr.dataset.email || "",
          phone_number: tr.dataset.phone || "",
          id_number: tr.dataset.idnumber || "",
          embg: tr.dataset.embg || "",
          vacation_days: Number(tr.dataset.vacdays || 0),
          director_of: tr.dataset.director_of || "",
          is_suspended: tr.dataset.suspended === "1",
        };

        tr.insertAdjacentHTML("afterend", detailTabsHTML(u));

        const gen = root.querySelector(`[data-general-wrap='${id}']`);
        const agr = root.querySelector(`[data-agreements-wrap='${id}']`);
        const vac = root.querySelector(`[data-vac-wrap='${id}']`);
        const sick = root.querySelector(`[data-sick-wrap='${id}']`);
        const rep = root.querySelector(`[data-report-wrap='${id}']`);
        const uni = root.querySelector(`[data-uniform-wrap='${id}']`);
        const trn = root.querySelector(`[data-training-wrap='${id}']`);
        const rwd = root.querySelector(`[data-rewards-wrap='${id}']`);

        try {
          const vacInfo = await fetchJSON(`${state.apiBase}/vacations/${id}`);
          u.vacation_days_left = vacInfo.vacation_days_left;
        } catch (_) {
          // ignore API error; keep UI responsive
        }

        if (typeof window.renderGeneral === "function" && gen && !gen.__mounted) {
          window.renderGeneral(u, gen);
          gen.__mounted = true;
        }

        [agr, vac, sick, rep, uni, trn, rwd].forEach((wrap) => {
          if (!wrap) return;
          const pane = wrap.closest(".tab-pane");
          if (!pane) return;
          pane.__mounted = false;
        });

        const container = root.querySelector(`tr.user-detail-row[data-detail-for='${id}']`);
        container?.addEventListener(
          "click",
          (ev) => {
            const lnk = ev.target.closest("[data-bs-toggle='pill'],[data-bs-toggle='tab']");
            if (!lnk) return;
            ev.preventDefault();
            safeShowTab(lnk);
            const targetSel = lnk.getAttribute("data-bs-target") || lnk.getAttribute("href");
            if (targetSel) ensurePaneMounted(id, document.querySelector(targetSel));
          },
          { once: true }
        );
      }
    });
  }

  // ---------- edit modal submit once ----------
  function wireEditForm(state) {
    const form = document.querySelector("#EditUserForm");
    if (!form || form.__wired) return;
    form.__wired = true;

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearErrors(form);
      const id = Number(document.querySelector("#EditUserId")?.value || 0);
      const payload = Object.fromEntries(new FormData(form).entries());
      try {
        const r = await postJSON(`${state.apiBase}/update/${id}`, payload);
        if (r && r.ok && r.item) {
          const row = state.root.querySelector(`tr.user-row[data-id='${id}']`);
          if (row) {
            row.children[1].textContent = r.item.first_name || "";
            row.children[2].textContent = r.item.last_name || "";
            row.dataset.email = r.item.email || "";
            row.dataset.phone = r.item.phone_number || "";
            row.dataset.idnumber = r.item.id_number || "";
            row.dataset.embg = r.item.embg || "";
            row.dataset.vacdays = r.item.vacation_days ?? 0;
            row.dataset.suspended = r.item.is_suspended ? "1" : "0";

            const depText = row.querySelector("[data-department-text]");
            if (depText) depText.textContent = r.item.department || "";

            const badge = row.querySelector("[data-director-badge]");
            if (badge) badge.remove();
            if (r.item.director_of) {
              row
                .querySelector("td:nth-child(4)")
                .insertAdjacentHTML(
                  "beforeend",
                  `<div class="small text-muted" data-director-badge>Director of <span class="fw-semibold">${r.item.director_of}</span></div>`
                );
            }

            const status = row.querySelector("[data-status-badge]");
            if (r.item.is_suspended) {
              row.classList.add("opacity-50");
              if (!status) {
                row
                  .querySelector("td:nth-child(4)")
                  .insertAdjacentHTML(
                    "beforeend",
                    `<span class="badge bg-warning text-dark ms-2" data-status-badge>SUSPENDED</span>`
                  );
              }
            } else {
              row.classList.remove("opacity-50");
              status?.remove();
            }
          }

          const detGen = state.root.querySelector(
            `tr.user-detail-row[data-detail-for='${id}'] [data-general-wrap='${id}']`
          );
          if (detGen && typeof window.renderGeneral === "function")
            window.renderGeneral(r.item, detGen);

          const modalEl = document.querySelector("#userEditModal");
          if (modalEl && window.bootstrap?.Modal) {
            const inst = window.bootstrap.Modal.getOrCreateInstance(modalEl);
            inst.hide();
          }
        }
      } catch (err) {
        const p = err.payload || {};
        if (p && p.errors && typeof p.errors === "object") {
          setErrors(form, p.errors);
        } else {
          try {
            setErrors(form, JSON.parse(err.message || "{}").errors || {});
          } catch {
            alert(err.message || "Save failed");
          }
        }
      }
    });
  }

  // ---------- create user form ----------
  function wireCreate(state) {
    const wrap = state.root.querySelector("#CreateUserWrap");
    const form = state.root.querySelector("#CreateUserForm");
    if (!wrap || !form || form.__wired) return;
    form.__wired = true;

    state.root.addEventListener("click", (e) => {
      if (e.target.closest("#btnToggleCreate")) {
        e.preventDefault();
        wrap.classList.toggle("d-none");
      }
      if (e.target.closest("#btnCancelCreate")) {
        e.preventDefault();
        form.reset();
        clearErrors(form);
        wrap.classList.add("d-none");
      }
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearErrors(form);
      const body = Object.fromEntries(new FormData(form).entries());

      // checkbox → hidden sync
      const isAdmin = document.querySelector("#CreateIsAdmin")?.checked;
      const hiddenAdmin = document.querySelector("#CreateIsAdminHidden");
      if (hiddenAdmin) hiddenAdmin.value = isAdmin ? "1" : "";

      try {
        await postJSON(`${state.apiBase}/create`, body);
        form.reset();
        wrap.classList.add("d-none");
        await loadList(state);
      } catch (err) {
        const p = err.payload || {};
        if (p && p.errors && typeof p.errors === "object") {
          setErrors(form, p.errors);
        } else {
          try {
            setErrors(form, JSON.parse(err.message || "{}").errors || {});
          } catch {
            alert(err.message || "Create failed");
          }
        }
      }
    });
  }

  // ---------- public mount ----------
  window.mountUsersPanel = async function mountUsersPanel(selector) {
    const root = document.querySelector(selector);
    if (!root) return;

    const apiBase = root.dataset.apiBase || "/users/api";
    const state = { root, apiBase, page: 1, pageSize: 50 };

    await loadList(state);
    wireListEvents(state);
    wireEditForm(state);
    wireCreate(state);

    // Broadcast from Departments
    window.addEventListener("user:department-changed", (ev) => {
      const { user_id, department_name } = ev.detail || {};
      const row = root.querySelector(`tr.user-row[data-id="${user_id}"]`);
      if (row) {
        row.dataset.department = department_name || "";
        const text = row.querySelector("[data-department-text]");
        if (text) text.textContent = department_name || "";
      }
      const det = root.querySelector(
        `tr.user-detail-row[data-detail-for="${user_id}"] [data-department-display="${user_id}"]`
      );
      if (det) det.textContent = department_name || "";
    });
  };
})();
