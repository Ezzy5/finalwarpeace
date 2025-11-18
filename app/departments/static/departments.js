// app/departments/static/departments.js
/* globals bootstrap */
(function () {
  "use strict";

  // -------- inject CSS to allow scroll but hide scrollbar in perms modal -----
  function ensureInvisibleScrollCSS() {
    if (document.getElementById("dep-perms-invisible-scroll-css")) return;
    const css = `
      /* Scroll inside the permissions modal body, but hide the slider */
      #depPermsModal .modal-body {
        max-height: 70vh;
        overflow: auto;
        -ms-overflow-style: none;     /* IE/Edge */
        scrollbar-width: none;        /* Firefox */
        padding-right: 0.5rem;        /* slight padding to avoid content clipping */
      }
      #depPermsModal .modal-body::-webkit-scrollbar {
        display: none;                /* Chrome/Safari */
        width: 0;
        height: 0;
      }
    `;
    const style = document.createElement("style");
    style.id = "dep-perms-invisible-scroll-css";
    style.type = "text/css";
    style.appendChild(document.createTextNode(css));
    document.head.appendChild(style);
  }

  // ---------------- Basics ----------------
  function csrf() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  }

  async function getJSON(url) {
    const r = await fetch(url, {
      credentials: "same-origin",
      headers: { "X-Requested-With": "fetch" }
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  async function postJSON(url, body) {
    const r = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf(),
        "X-Requested-With": "fetch"
      },
      body: JSON.stringify(body || {}),
    });
    if (!r.ok) {
      const t = await r.text().catch(() => "");
      throw new Error(t || `HTTP ${r.status}`);
    }
    try { return await r.json(); } catch { return {}; }
  }

  function clearErrors(form) {
    form?.querySelectorAll("[data-err]").forEach(e => (e.textContent = ""));
  }
  function setErrors(form, errs) {
    Object.entries(errs || {}).forEach(([k, v]) => {
      const el = form.querySelector(`[data-err='${k}']`);
      if (el) el.textContent = String(v || "");
    });
  }

  // --------------- Table ------------------
  function trHTML(dep, index) {
    const director = dep.manager_name || "—";
    return `
      <tr data-id="${dep.id}">
        <td class="text-muted">${index}</td>
        <td>${dep.name}</td>
        <td>${director}</td>
        <td class="text-end" style="white-space:nowrap;">
          <button class="btn btn-sm btn-outline-secondary" data-action="edit" data-id="${dep.id}">Уреди</button>
          <button class="btn btn-sm btn-outline-danger" data-action="delete" data-id="${dep.id}">Избриши</button>
          <button class="btn btn-sm btn-outline-primary" data-action="perms" data-id="${dep.id}">Пермисии</button>
          <button class="btn btn-sm btn-outline-success" data-action="members" data-id="${dep.id}">Членови</button>
        </td>
      </tr>
    `;
  }

  async function loadUsersIntoSelect(select, currentDepId) {
    if (!select) return;
    const data = await getJSON("/departments/api/users");
    select.innerHTML = `<option value="">— Нема —</option>`;
    (data.items || []).forEach(u => {
      // исклучи корисници кои се веќе во друг оддел
      if (u.department_id !== null && u.department_id !== currentDepId) return;
      const o = document.createElement("option");
      o.value = String(u.id);
      o.textContent = u.name;
      select.appendChild(o);
    });
  }

  async function loadPage(state) {
    const tbody =
      state.root.querySelector("#DepartmentsTable") ||
      document.querySelector("#DepartmentsTable");
    if (!tbody) {
      console.error("[departments] #DepartmentsTable not found");
      return;
    }
    tbody.innerHTML = "";
    const data = await getJSON(
      `/departments/api/list?page=${state.page}&page_size=${state.pageSize}`
    );
    (data.items || []).forEach((d, i) => {
      tbody.insertAdjacentHTML(
        "beforeend",
        trHTML(d, i + 1 + (state.page - 1) * state.pageSize)
      );
    });
    state.hasPrev = state.page > 1;
    state.hasNext = (data.items || []).length === state.pageSize;
  }

  // --------------- Members ----------------
  async function refreshMembersList(depId, root) {
    const list = root.querySelector("#MembersList");
    if (!list) return;
    list.innerHTML = `<li class="list-group-item text-muted">Се вчитува...</li>`;
    const data = await getJSON(`/departments/api/members/${depId}`);
    list.innerHTML = "";
    const items = data.items || [];
    if (!items.length) {
      list.innerHTML = `<li class="list-group-item text-muted">Нема членови.</li>`;
      return;
    }
    items.forEach(m => {
      const li = document.createElement("li");
      li.className =
        "list-group-item d-flex justify-content-between align-items-center";
      li.innerHTML = `
        <div>
          <div class="fw-semibold">${m.name}</div>
          <div class="text-muted small">${m.email || ""}</div>
        </div>
        <button class="btn btn-sm btn-outline-danger" data-action="member-remove" data-user="${m.id}" data-dep="${depId}">
          Отстрани
        </button>
      `;
      list.appendChild(li);
    });
  }

  async function loadMembersCandidates(depId, root) {
    const sel = root.querySelector("#MembersAddSelect");
    if (!sel) return;
    const [allUsers, members] = await Promise.all([
      getJSON("/departments/api/users"),
      getJSON(`/departments/api/members/${depId}`),
    ]);
    const memberIds = new Set((members.items || []).map(m => m.id));
    sel.innerHTML = "";
    (allUsers.items || []).forEach(u => {
      if (memberIds.has(u.id)) return;
      const o = document.createElement("option");
      o.value = String(u.id);
      o.textContent = u.name;
      // disable ако веќе има оддел
      if (u.department_id) o.disabled = true;
      sel.appendChild(o);
    });
  }

  // ------------- Permissions UI --------------
  // Only USERS and WAR permissions (no "Others")
  const PERM_META = {
    // USERS group
    "users.view":         { label: "Users: Преглед",       desc: "Пристап до список на корисници." },
    "users.general":      { label: "Users: General",       desc: "Преглед на општ таб за корисник." },
    "users.create_edit":  { label: "Users: Креирај/Уреди", desc: "Креирање/ажурирање на корисници." },
    "users.agreement":    { label: "Users: Договори",      desc: "Управување со договори." },
    "users.vacation":     { label: "Users: Одмор",         desc: "Управување со одмори." },
    "users.sick":         { label: "Users: Боледување",    desc: "Управување со боледувања." },
    "users.reports":      { label: "Users: Извештаи",      desc: "Преглед/уредување на извештаи." },
    "users.uniforms":     { label: "Users: Униформи",      desc: "Управување со униформи." },
    "users.training":     { label: "Users: Обуки",         desc: "Управување со обуки." },
    "users.rewards":      { label: "Users: Награди",       desc: "Креирање/бришење награди." },
    "users.penalty":      { label: "Users: Казни",         desc: "Креирање/бришење казни." },
    "users.attachments":  { label: "Users: Прилози",       desc: "Прикачување/бришење прилози." },

    // WAR group
    "war.view":           { label: "War: Преглед",         desc: "Пристап и читање на War модулот." },
    "war.edit":           { label: "War: Уреди",           desc: "Измена и ажурирање на записи во War." },
    "war.export":         { label: "War: Експорт",         desc: "Извезување извештаи од War." },
    "war.manage":         { label: "War: Администрација",  desc: "Креирање/бришење и целосно управување." },
  };

  function renderPermCheckboxes(container, items) {
    // items: [{code, allowed}]
    container.innerHTML = "";

    const groups = [
      { title: "Users", prefix: "users." },
      { title: "War",   prefix: "war."   },
    ];

    let renderedAny = false;

    groups.forEach(g => {
      const groupItems = items.filter(it => it.code.startsWith(g.prefix));
      if (!groupItems.length) return;

      renderedAny = true;

      const card = document.createElement("div");
      card.className = "card mb-3";
      card.innerHTML =
        `<div class="card-header py-2"><strong>${g.title}</strong></div>` +
        `<div class="card-body py-2"></div>`;
      const body = card.querySelector(".card-body");

      groupItems.forEach(it => {
        const id = "perm_" + it.code.replace(/\./g, "_");
        const meta = PERM_META[it.code] || { label: it.code, desc: "" };
        const wrap = document.createElement("div");
        wrap.className = "form-check form-switch mb-2";
        wrap.innerHTML =
          `<input class="form-check-input" type="checkbox" id="${id}" data-code="${it.code}"${it.allowed ? " checked" : ""}>` +
          `<label class="form-check-label fw-semibold" for="${id}">${meta.label}</label>` +
          (meta.desc ? `<div class="text-muted small ms-4">${meta.desc}</div>` : "");
        body.appendChild(wrap);
      });

      container.appendChild(card);
    });

    // Do NOT render any other/leftover permissions
    if (!renderedAny) {
      container.innerHTML =
        '<div class="text-muted small">Нема пермисии за прикажување.</div>';
    }
  }

  async function loadDepPermissions(depId, root) {
    const data = await getJSON(`/departments/api/perms/${depId}`);
    const listEl = root.querySelector("#PermsList");
    if (!listEl) return;
    renderPermCheckboxes(listEl, (data.items || []).filter(it =>
      it.code.startsWith("users.") || it.code.startsWith("war.")
    ));
  }

  async function saveDepPermissions(depId, root) {
    const listEl = root.querySelector("#PermsList");
    if (!listEl) return;
    const inputs = Array.from(
      listEl.querySelectorAll('input[type="checkbox"][data-code]')
    );
    const items = inputs.map(inp => ({
      code: inp.getAttribute("data-code"),
      allowed: !!inp.checked,
    }));
    return postJSON(`/departments/api/perms/${depId}`, { items });
  }

  // --------------- Wiring -------------------
  function wire(state) {
    const root = state.root;

    root.addEventListener("click", async (e) => {
      const t = e.target;

      // Edit
      const edit = t.closest("button[data-action='edit']");
      if (edit) {
        e.preventDefault();
        const id = Number(edit.dataset.id);
        const row = edit.closest("tr");
        const name = row?.children?.[1]?.textContent?.trim() || "";
        const director = row?.children?.[2]?.textContent?.trim() || "";
        const modalEl = root.querySelector("#depEditModal");
        const idEl = root.querySelector("#EditDepId");
        const nameEl = root.querySelector("#EditDepName");
        const selEl = root.querySelector("#EditDirectorSelect");
        if (!modalEl || !idEl || !nameEl || !selEl) return;

        idEl.value = id;
        nameEl.value = name;
        await loadUsersIntoSelect(selEl, id);

        if (director && director !== "—") {
          const optNode = Array.from(selEl.options).find(
            o => o.textContent === director
          );
          selEl.value = optNode ? optNode.value : "";
        } else {
          selEl.value = "";
        }

        new bootstrap.Modal(modalEl).show();
        return;
      }

      // Delete
      const del = t.closest("button[data-action='delete']");
      if (del) {
        e.preventDefault();
        const id = Number(del.dataset.id);
        if (!confirm("Да се избрише овој оддел?")) return;
        try {
          await postJSON(`/departments/api/delete/${id}`, {});
          await loadPage(state);
        } catch (err) {
          alert(err.message || "Бришењето не успеа.");
        }
        return;
      }

      // Permissions
      const permsBtn = t.closest("button[data-action='perms']");
      if (permsBtn) {
        e.preventDefault();
        const id = Number(permsBtn.dataset.id);
        const row = permsBtn.closest("tr");
        const depName =
          (row && row.children && row.children[1]
            ? row.children[1].textContent.trim()
            : "") || "";

        const idInput = root.querySelector("#PermsDepId");
        if (idInput) idInput.value = String(id);

        const titleEl = root.querySelector("#depPermsModal .modal-title");
        if (titleEl && depName)
          titleEl.textContent = "Пермисии на одделот — " + depName;

        const listEl = root.querySelector("#PermsList");
        if (listEl)
          listEl.innerHTML = '<div class="text-muted small">Се вчитува...</div>';

        try {
          await loadDepPermissions(id, root);
        } catch (err) {
          console.error(err);
          if (listEl)
            listEl.innerHTML =
              '<div class="text-danger small">Неуспешно вчитување на пермисиите.</div>';
        }

        // show modal (scroll is handled by injected CSS)
        new bootstrap.Modal(root.querySelector("#depPermsModal")).show();
        return;
      }

      // Members (open)
      const membersBtn = t.closest("button[data-action='members']");
      if (membersBtn) {
        e.preventDefault();
        const id = Number(membersBtn.dataset.id);
        root.querySelector("#MembersDepId").value = id;

        const row = membersBtn.closest("tr");
        const depName =
          (row && row.children && row.children[1]
            ? row.children[1].textContent.trim()
            : "") || "";
        const nameEl = root.querySelector("#MembersDepName");
        if (nameEl) nameEl.value = depName;

        await Promise.all([
          refreshMembersList(id, root),
          loadMembersCandidates(id, root),
        ]);

        new bootstrap.Modal(root.querySelector("#depMembersModal")).show();
        return;
      }

      // Remove member
      const rem = t.closest("button[data-action='member-remove']");
      if (rem) {
        e.preventDefault();
        const depId = Number(rem.dataset.dep);
        const userId = Number(rem.dataset.user);
        try {
          await postJSON(`/departments/api/members/${depId}/remove`, {
            user_id: userId,
          });
          await Promise.all([
            refreshMembersList(depId, root),
            loadMembersCandidates(depId, root),
          ]);
          window.dispatchEvent(
            new CustomEvent("user:department-changed", {
              detail: { user_id: userId, department_id: null, department_name: "" },
            })
          );
          await loadPage(state);
        } catch (err) {
          alert(err.message || "Отстранувањето не успеа.");
        }
        return;
      }
    });

    // Add member
    root.querySelector("#MembersAddBtn")?.addEventListener("click", async (e) => {
      e.preventDefault();
      const depId = Number(root.querySelector("#MembersDepId").value);
      const sel = root.querySelector("#MembersAddSelect");
      const userId = Number(sel?.value || 0);
      if (!userId) return;
      try {
        await postJSON(`/departments/api/members/${depId}`, { user_id: userId });
        sel.value = "";
        await Promise.all([
          refreshMembersList(depId, root),
          loadMembersCandidates(depId, root),
        ]);
        const depName = root.querySelector("#MembersDepName")?.value || "";
        window.dispatchEvent(
          new CustomEvent("user:department-changed", {
            detail: { user_id: userId, department_id: depId, department_name: depName },
          })
        );
      } catch (err) {
        alert(err.message || "Додавањето не успеа.");
      }
    });

    // Edit submit
    root.querySelector("#EditDepartmentForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const form = e.currentTarget;
      clearErrors(form);
      const id = Number(form.querySelector("#EditDepId").value);
      const body = Object.fromEntries(new FormData(form).entries());
      if (body.manager_id === "") body.manager_id = null;
      try {
        const r = await postJSON(`/departments/api/update/${id}`, body);
        if (r && r.ok) {
          await loadPage(state);
          const modalEl = root.querySelector("#depEditModal");
          const inst = bootstrap.Modal.getInstance(modalEl);
          inst && inst.hide();
        }
      } catch (err) {
        try {
          setErrors(form, JSON.parse(err.message || "{}").errors || {});
        } catch {
          alert(err.message || "Грешка при зачувување.");
        }
      }
    });

    // Create show/hide
    const createWrap = root.querySelector("#CreateDepartmentWrap");
    root.addEventListener("click", (e) => {
      const a = e.target.closest("#btnToggleCreate");
      if (a && createWrap) {
        e.preventDefault();
        createWrap.classList.toggle("d-none");
      }
      const b = e.target.closest("#btnCancelCreate");
      if (b && createWrap) {
        e.preventDefault();
        createWrap.classList.add("d-none");
      }
    });

    // Create submit
    root.querySelector("#CreateDepartmentForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const form = e.currentTarget;
      clearErrors(form);
      const body = Object.fromEntries(new FormData(form).entries());
      if (body.manager_id === "") body.manager_id = null;
      try {
        const r = await postJSON("/departments/api/create", body);
        if (r && r.ok) {
          form.reset();
          createWrap?.classList.add("d-none");
          await loadPage(state);
        }
      } catch (err) {
        try {
          setErrors(form, JSON.parse(err.message || "{}").errors || {});
        } catch {
          alert(err.message || "Креирањето не успеа.");
        }
      }
    });

    // Permissions submit
    root.querySelector("#PermsForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const depId = Number(root.querySelector("#PermsDepId")?.value || 0);
      if (!depId) return;
      try {
        await saveDepPermissions(depId, root);
        alert("Пермисиите се зачувани.");
        const modalEl = root.querySelector("#depPermsModal");
        const inst = bootstrap.Modal.getInstance(modalEl);
        inst && inst.hide();
      } catch (err) {
        console.error(err);
        alert("Грешка при зачувување на пермисиите.");
      }
    });
  }

  // --------------- Mount -------------------
  window.mountDepartmentsPanel = async function (selector) {
    ensureInvisibleScrollCSS();

    const root =
      typeof selector === "string" ? document.querySelector(selector) : selector;
    if (!root) {
      console.error("[departments] mount root not found", selector);
      return;
    }
    const state = { root, page: 1, pageSize: 50, hasPrev: false, hasNext: false };
    await loadPage(state);
    wire(state);
  };
})();
