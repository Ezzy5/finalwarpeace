// app/users/static/vacations.js
(function () {
  "use strict";

  // ----- App/globals with safe fallbacks -----
  const A = window.UsersApp || (window.UsersApp = { helpers: {}, api: {} });
  const H = A.helpers || {};
  const getMetaCsrf =
    H.getMetaCsrf ||
    function () {
      const m = document.querySelector('meta[name="csrf-token"]');
      return m ? m.getAttribute("content") : "";
    };
  const fetchJSON =
    H.fetchJSON ||
    (async (url) => {
      const r = await fetch(url, { credentials: "same-origin" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    });
  const postJSON =
    H.postJSON ||
    (async (url, body) => {
      const r = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getMetaCsrf(),
        },
        body: JSON.stringify(body || {}),
      });
      if (!r.ok) {
        const t = await r.text().catch(() => "");
        throw new Error(t || `HTTP ${r.status}`);
      }
      try {
        return await r.json();
      } catch {
        return {};
      }
    });
  const clearErrors = H.clearErrors || function () {};
  const setErrors = H.setErrors || function () {};

  // ----- UI helpers -----
  function headerButton(text, targetId) {
    return `<button class="btn btn-link p-0 text-decoration-none"
              data-bs-toggle="collapse" data-bs-target="#${targetId}"
              aria-expanded="false" aria-controls="${targetId}">${text}</button>`;
  }

  function normalizedFilesArray(bucket) {
    // Accept both `attachments` and `files` from backend
    if (Array.isArray(bucket)) return bucket;
    return [];
  }

  function filesHTML(bucket) {
    const files = normalizedFilesArray(bucket);
    if (!files.length) return `<div class="small text-muted">No files</div>`;
    return `<div class="small">
      Files:
      ${files
        .map(
          (x) =>
            `<a class="text-decoration-underline attachment-link" href="/users/attachments/${x.stored_name}" target="_blank" rel="noopener">${x.filename}</a>`
        )
        .join(" | ")}
    </div>`;
  }

  function itemHTML(v, userId) {
    const cid = `vac-${userId}-${v.id}`;
    const daysText = v.days != null ? `${v.days} days` : "";
    const retText = v.return_date ? `, return ${v.return_date}` : "";
    const fileBucket =
      typeof v.attachments !== "undefined" ? v.attachments : v.files;

    return `<div class="list-group-item">
      <div class="d-flex justify-content-between align-items-center">
        <div>
          ${headerButton(
            `${v.start_date} → ${v.end_date || "—"}${
              daysText ? " (" + daysText + retText + ")" : ""
            }`,
            cid
          )}
          <span class="badge bg-${
            v.status === "active" ? "success" : "secondary"
          } ms-2">${v.status || ""}</span>
        </div>
      </div>
      <div class="collapse mt-2" id="${cid}">
        ${filesHTML(fileBucket)}
      </div>
    </div>`;
  }

  async function fillVacations(userId, data, wrap) {
    if (!wrap) return;
    const active = wrap.querySelector(`[data-vac-active='${userId}']`);
    const history = wrap.querySelector(`[data-vac-history='${userId}']`);

    const actItems = Array.isArray(data?.active) ? data.active : [];
    const histItems = Array.isArray(data?.history) ? data.history : [];

    if (active) {
      active.innerHTML = actItems.length
        ? actItems.map((v) => itemHTML(v, userId)).join("")
        : `<div class="list-group-item text-muted">No active vacations</div>`;
    }
    if (history) {
      history.innerHTML = histItems.length
        ? histItems.map((v) => itemHTML(v, userId)).join("")
        : `<div class="list-group-item text-muted">No history</div>`;
    }
  }

  async function renderVacation(userId, wrap) {
    if (!wrap) return;
    wrap.innerHTML = `<div class="text-muted">Loading vacation...</div>`;
    // cache-bust to ensure fresh attachments after upload
    const data = await fetchJSON(`/users/api/vacations/${userId}?_=${Date.now()}`);
    const left =
      data && typeof data.vacation_days_left !== "undefined"
        ? data.vacation_days_left
        : "—";
    wrap.innerHTML = `
      <div class="mb-2">
        <button class="btn btn-sm btn-outline-primary" data-action="vac-toggle" data-user="${userId}">＋ New Vacation</button>
        <span class="small text-muted ms-2">Vacation days left: ${left}</span>
      </div>
      <form class="card card-body p-3 mb-3 d-none" data-vac-form="${userId}">
        <div class="row g-2">
          <div class="col-md-4">
            <label class="form-label">Start</label>
            <input type="date" name="start_date" class="form-control" required>
            <div class="text-danger small" data-err="start_date"></div>
          </div>
          <div class="col-md-2">
            <label class="form-label">Days</label>
            <input type="number" name="days" class="form-control" min="1" step="1" required>
            <div class="text-danger small" data-err="days"></div>
          </div>
          <div class="col-md-6">
            <label class="form-label">Attach files (optional)</label>
            <input type="file" class="form-control" name="files" multiple>
          </div>
        </div>
        <div class="mt-2">
          <button class="btn btn-sm btn-link p-0" type="button" data-action="vac-holidays-toggle" data-user="${userId}">Holidays ⌄</button>
          <div class="border rounded p-2 mt-2 d-none" data-vac-holidays="${userId}">
            <div class="d-flex flex-wrap gap-2 align-items-end">
              <div>
                <label class="form-label">Add holiday</label>
                <input type="date" class="form-control" data-holiday-input>
              </div>
              <button class="btn btn-sm btn-outline-secondary" type="button" data-action="vac-holiday-add" data-user="${userId}">Add</button>
            </div>
            <div class="small text-muted mt-2">Excluded holiday dates:</div>
            <div class="d-flex flex-wrap gap-2 mt-1" data-holiday-list></div>
          </div>
        </div>
        <div class="mt-3 d-flex gap-2">
          <button class="btn btn-success btn-sm" data-action="vac-save" data-user="${userId}">Save</button>
          <button class="btn btn-outline-secondary btn-sm" data-action="vac-cancel">Close</button>
        </div>
      </form>
      <h6>Active</h6><div class="list-group" data-vac-active="${userId}"></div>
      <h6 class="mt-3">History</h6><div class="list-group" data-vac-history="${userId}"></div>
    `;
    await fillVacations(userId, data || { active: [], history: [] }, wrap);
  }

  // ----- uploads -----
  async function uploadAttachments(uid, formEl, createdId) {
    const filesInput = formEl.querySelector("input[name='files']");
    const files = filesInput?.files || [];
    if (!files.length || !createdId) return;

    // Primary: backend expects singular "file"
    const up1 = new FormData();
    // send each file under "file" key (multiple parts named "file")
    for (const f of files) up1.append("file", f);
    up1.append("vacation_id", String(createdId));

    let resp = await fetch(`/users/api/attachments/${uid}`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": getMetaCsrf() },
      body: up1,
    });

    if (!resp.ok) {
      // Try to read error to check if it was the "file" key validation
      let errText = "";
      try {
        errText = await resp.text();
      } catch {}
      // Fallback: try plural "files" if server didn’t accept "file"
      const up2 = new FormData();
      for (const f of files) up2.append("files", f);
      up2.append("vacation_id", String(createdId));
      resp = await fetch(`/users/api/attachments/${uid}`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": getMetaCsrf() },
        body: up2,
      });
      if (!resp.ok) {
        console.warn("Vacation attachment upload failed:", errText || (await resp.text().catch(() => resp.status)));
      }
    }
  }

  // ----- scope resolver -----
  function resolveWrap(fromTarget) {
    return fromTarget.closest(`[data-vac-wrap]`) || null;
  }

  // ----- events -----
  async function onClick(e) {
    const t = e.target;
    const wrap = resolveWrap(t);
    if (!wrap) return false;

    const toggle = t.closest("[data-action='vac-toggle']");
    if (toggle) {
      e.preventDefault();
      const uid = toggle.dataset.user;
      wrap.querySelector(`[data-vac-form='${uid}']`)?.classList.toggle("d-none");
      return true;
    }

    const close = t.closest("[data-action='vac-cancel']");
    if (close) {
      e.preventDefault();
      const form = wrap.querySelector("form[data-vac-form]");
      if (form) {
        form.classList.add("d-none");
        form.reset();
      }
      return true;
    }

    const hToggle = t.closest("[data-action='vac-holidays-toggle']");
    if (hToggle) {
      e.preventDefault();
      const box = wrap.querySelector(`[data-vac-holidays='${hToggle.dataset.user}']`);
      if (box) box.classList.toggle("d-none");
      return true;
    }

    const addHol = t.closest("[data-action='vac-holiday-add']");
    if (addHol) {
      e.preventDefault();
      const box = wrap.querySelector("[data-vac-holidays]");
      const input = box?.querySelector("[data-holiday-input]");
      const list = box?.querySelector("[data-holiday-list]");
      if (!input || !list || !input.value) return true;
      const chip = document.createElement("span");
      chip.className = "badge text-bg-secondary";
      chip.dataset.holiday = input.value;
      chip.innerHTML = `${input.value} <button type="button" class="btn-close btn-close-white btn-sm ms-1" data-action="vac-holiday-remove" aria-label="Remove"></button>`;
      list.appendChild(chip);
      input.value = "";
      return true;
    }

    const remHol = t.closest("[data-action='vac-holiday-remove']");
    if (remHol) {
      e.preventDefault();
      remHol.closest(".badge[data-holiday]")?.remove();
      return true;
    }

    const save = t.closest("[data-action='vac-save']");
    if (save) {
      e.preventDefault();
      const uid = Number(save.dataset.user);
      const form = wrap.querySelector(`[data-vac-form='${uid}']`);
      if (!form) return true;

      clearErrors(form);
      const fd = new FormData(form);
      const start_date = fd.get("start_date");
      const days = Number(fd.get("days") || 0);
      const holidays = Array.from(
        form.querySelectorAll(".badge[data-holiday]")
      ).map((el) => el.dataset.holiday);

      try {
        // 1) create vacation
        const created = await postJSON(`/users/api/vacations/${uid}/create`, {
          start_date,
          days,
          holidays,
        });

        const createdId =
          created?.item?.id ??
          created?.vacation?.id ??
          created?.id ??
          null;

        // 2) upload files (if any)
        await uploadAttachments(uid, form, createdId);

        // 3) reset + re-render (cache-bust) so we see the new files
        form.classList.add("d-none");
        form.reset();
        await renderVacation(uid, wrap);
      } catch (err) {
        try {
          setErrors(form, JSON.parse(err.message || "{}").errors || {});
        } catch {
          alert(err.message || "Save failed");
        }
      }
      return true;
    }

    return false;
  }

  // ----- exports / wiring -----
  window.renderVacation = renderVacation;
  A.api.renderVacation = renderVacation;

  if (typeof A.registerClick === "function") {
    A.registerClick(onClick);
  } else if (!window.__vacationsClickBound__) {
    document.addEventListener("click", onClick);
    window.__vacationsClickBound__ = true;
  }
})();
