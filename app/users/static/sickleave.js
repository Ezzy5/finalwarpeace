// app/users/static/sickleave.js
(function () {
  "use strict";

  const A = window.UsersApp || (window.UsersApp = { helpers: {}, api: {} });
  const H = A.helpers || {};

  const fetchJSON = H.fetchJSON || ((u) =>
    fetch(u, { credentials: "same-origin" }).then((r) => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    }));

  const postJSON = H.postJSON || ((u, b) =>
    fetch(u, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": (H.getMetaCsrf ? H.getMetaCsrf() : (document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "")),
      },
      body: JSON.stringify(b || {}),
    }).then(async (r) => {
      if (!r.ok) {
        const t = await r.text().catch(() => "");
        throw new Error(t || `HTTP ${r.status}`);
      }
      try { return await r.json(); } catch { return {}; }
    }));

  const clearErrors = H.clearErrors || function () {};
  const setErrors   = H.setErrors   || function () {};
  const getMetaCsrf = H.getMetaCsrf || function () { const m=document.querySelector('meta[name="csrf-token"]'); return m?m.getAttribute("content"):""; };

  // ---- Local date utils (don’t depend on missing helpers) ----
  function parseYMD(s) {
    if (!s) return null;
    const [y, m, d] = s.split("-").map(Number);
    if (!y || !m || !d) return null;
    const dt = new Date(Date.UTC(y, m - 1, d));
    // normalize to local date (strip time)
    return new Date(dt.getUTCFullYear(), dt.getUTCMonth(), dt.getUTCDate());
  }
  function fmtYMD(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${dd}`;
  }
  const isWeekend = (d) => d.getDay() === 0 || d.getDay() === 6;

  function countBusinessDaysInclusive(startStr, endStr, holidaySet) {
    const s = parseYMD(startStr), e = parseYMD(endStr);
    if (!s || !e || e < s) return 0;
    let days = 0;
    const d = new Date(s);
    while (d <= e) {
      if (!isWeekend(d) && !holidaySet.has(fmtYMD(d))) days++;
      d.setDate(d.getDate() + 1);
    }
    return days;
  }

  // ---- small UI helpers ----
  function headerButton(text, targetId) {
    return `<button class="btn btn-link p-0 text-decoration-none"
                    data-bs-toggle="collapse" data-bs-target="#${targetId}"
                    aria-expanded="false" aria-controls="${targetId}">${text}</button>`;
  }
  function filesHTML(files) {
    if (!files?.length) return `<div class="small text-muted">No files</div>`;
    return `<div class="small">Files: ${
      files.map(x => `<a class="text-decoration-underline attachment-link" href="/users/attachments/${x.stored_name}" target="_blank" rel="noopener">${x.filename}</a>`).join(" | ")
    }</div>`;
  }

  // ---- render & refresh ----
  async function refreshSick(userId, wrap) {
    if (!wrap) return;
    const data = await fetchJSON(`/users/api/sickleaves/${userId}`);

    const act = wrap.querySelector(`[data-sick-active='${userId}']`);
    const hist = wrap.querySelector(`[data-sick-history='${userId}']`);

    const item = (s) => {
      const cid = `sick-${userId}-${s.id}`;
      return `<div class="list-group-item">
        <div class="d-flex justify-content-between align-items-center">
          <div>
            ${headerButton(`${s.start_date} → ${s.end_date || "—"}`, cid)}
            <span class="ms-2">${s.kind || ""}</span>
            <span class="badge bg-${s.status === "active" ? "success" : "secondary"} ms-2">${s.status || ""}</span>
          </div>
        </div>
        <div class="collapse mt-2" id="${cid}">
          <div class="small text-muted">
            Business days: ${s.business_days ?? "—"}${s.holidays?.length ? ` • Holidays: ${s.holidays.join(", ")}` : ""}
          </div>
          ${s.comments ? `<div class="small">Comments: ${s.comments}</div>` : ""}
          ${filesHTML(s.attachments)}
        </div>
      </div>`;
    };

    if (act) {
      act.innerHTML = (data.active?.length)
        ? data.active.map(item).join("")
        : `<div class="list-group-item text-muted">No active sick leaves</div>`;
    }
    if (hist) {
      hist.innerHTML = (data.history?.length)
        ? data.history.map(item).join("")
        : `<div class="list-group-item text-muted">No history</div>`;
    }
  }

  async function renderSick(userId, wrap) {
    if (!wrap) return;
    wrap.innerHTML = `
      <div class="mb-2 d-flex align-items-center justify-content-between flex-wrap gap-2">
        <div class="small text-muted">Manage sick leaves</div>
        <button class="btn btn-sm btn-outline-primary" data-action="sick-toggle" data-user="${userId}">＋ Sick Leave</button>
      </div>
      <form class="card card-body p-3 mb-3 d-none" data-sick-form="${userId}">
        <div class="row g-2">
          <div class="col-md-3">
            <label class="form-label">Start</label>
            <input type="date" class="form-control" name="start_date" required>
            <div class="text-danger small" data-err="start_date"></div>
          </div>
          <div class="col-md-3">
            <label class="form-label">End</label>
            <input type="date" class="form-control" name="end_date" required>
            <div class="text-danger small" data-err="end_date"></div>
          </div>
          <div class="col-md-3">
            <label class="form-label">Тип</label>
            <select name="kind" class="form-select" required>
              <option value="">-- одбери --</option>
              <option>Терет на фирма</option><option>Терет на фонд</option>
              <option>Породилно</option><option>100% повреда на работа</option>
            </select>
            <div class="text-danger small" data-err="kind"></div>
          </div>
          <div class="col-md-3">
            <label class="form-label">Business days (auto)</label>
            <input type="text" class="form-control" name="biz_preview" disabled>
          </div>
        </div>
        <div class="row g-2 mt-2">
          <div class="col-md-6">
            <label class="form-label">Attachment (optional)</label>
            <input type="file" class="form-control" name="files" multiple>
          </div>
          <div class="col-md-6">
            <label class="form-label">Comments</label>
            <textarea name="comments" class="form-control" rows="1" placeholder="Коментар..."></textarea>
          </div>
        </div>
        <div class="mt-2">
          <button class="btn btn-sm btn-link p-0" type="button" data-action="sick-holidays-toggle" data-user="${userId}">Holidays ⌄</button>
          <div class="border rounded p-2 mt-2 d-none" data-sick-holidays="${userId}">
            <div class="d-flex flex-wrap gap-2 align-items-end">
              <div><label class="form-label">Add holiday</label><input type="date" class="form-control" data-holiday-input></div>
              <button class="btn btn-sm btn-outline-secondary" type="button" data-action="sick-holiday-add" data-user="${userId}">Add</button>
            </div>
            <div class="small text-muted mt-2">Excluded holiday dates:</div>
            <div class="d-flex flex-wrap gap-2 mt-1" data-holiday-list></div>
          </div>
        </div>
        <div class="mt-3 d-flex gap-2">
          <button class="btn btn-success btn-sm" data-action="sick-save" data-user="${userId}">Save</button>
          <button class="btn btn-outline-secondary btn-sm" data-action="sick-cancel">Close</button>
        </div>
      </form>
      <div class="mt-2">
        <h6>Active</h6>
        <div class="list-group" data-sick-active="${userId}"><div class="list-group-item text-muted">Loading...</div></div>
      </div>
      <div class="mt-3">
        <h6>History</h6>
        <div class="list-group" data-sick-history="${userId}"><div class="list-group-item text-muted">Loading...</div></div>
      </div>
    `;
    await refreshSick(userId, wrap);
  }

  // ---- scope helpers (fix the dispatcher “root” param mismatch) ----
  function resolveWrap(fromTarget) {
    return fromTarget.closest(`[data-sick-wrap]`) || null;
  }

  function onInput(e) {
    const wrap = resolveWrap(e.target);
    if (!wrap) return false;

    const sickForm = e.target.closest("form[data-sick-form]");
    if (!sickForm || !wrap.contains(sickForm)) return false;

    const start = sickForm.querySelector("input[name='start_date']").value;
    const end   = sickForm.querySelector("input[name='end_date']").value;
    const hol = new Set(Array.from(sickForm.querySelectorAll(".badge[data-holiday]")).map(b => b.dataset.holiday));
    const preview = sickForm.querySelector("input[name='biz_preview']");
    if (preview) preview.value = (start && end) ? `${countBusinessDaysInclusive(start, end, hol)} days` : "";
    return false;
  }

  async function onClick(e) {
    const t = e.target;
    const wrap = resolveWrap(t);
    if (!wrap) return false;

    const toggle = t.closest("[data-action='sick-toggle']");
    if (toggle) {
      e.preventDefault();
      const uid = toggle.dataset.user;
      wrap.querySelector(`[data-sick-form='${uid}']`)?.classList.toggle("d-none");
      return true;
    }

    const cancel = t.closest("[data-action='sick-cancel']");
    if (cancel) {
      e.preventDefault();
      const form = wrap.querySelector("form[data-sick-form]");
      if (form) { form.classList.add("d-none"); form.reset(); }
      return true;
    }

    const hToggle = t.closest("[data-action='sick-holidays-toggle']");
    if (hToggle) {
      e.preventDefault();
      const box = wrap.querySelector(`[data-sick-holidays='${hToggle.dataset.user}']`);
      if (box) box.classList.toggle("d-none");
      return true;
    }

    const hAdd = t.closest("[data-action='sick-holiday-add']");
    if (hAdd) {
      e.preventDefault();
      const box = wrap.querySelector("[data-sick-holidays]");
      const input = box?.querySelector("[data-holiday-input]");
      const list  = box?.querySelector("[data-holiday-list]");
      if (!input || !list || !input.value) return true;
      const chip = document.createElement("span");
      chip.className = "badge text-bg-secondary";
      chip.dataset.holiday = input.value;
      chip.innerHTML = `${input.value} <button class="btn-close btn-close-white btn-sm ms-1" data-action="sick-holiday-remove" aria-label="Remove"></button>`;
      list.appendChild(chip);
      input.value = "";
      // update preview
      const form = wrap.querySelector("form[data-sick-form]");
      form?.dispatchEvent(new Event("input", { bubbles: true }));
      return true;
    }

    const hRem = t.closest("[data-action='sick-holiday-remove']");
    if (hRem) {
      e.preventDefault();
      hRem.closest(".badge[data-holiday]")?.remove();
      const form = wrap.querySelector("form[data-sick-form]");
      form?.dispatchEvent(new Event("input", { bubbles: true }));
      return true;
    }

    const save = t.closest("[data-action='sick-save']");
    if (save) {
      e.preventDefault();
      const uid = Number(save.dataset.user);
      const form = wrap.querySelector(`[data-sick-form='${uid}']`);
      if (!form) return true;

      clearErrors(form);
      const fd = new FormData(form);
      const start_date = fd.get("start_date");
      const end_date   = fd.get("end_date");
      const kind       = fd.get("kind");
      const comments   = fd.get("comments");
      const holidays   = Array.from(form.querySelectorAll(".badge[data-holiday]")).map(el => el.dataset.holiday);

      try {
        const created = await postJSON(`/users/api/sickleaves/${uid}/create`, { start_date, end_date, kind, comments, holidays });

        // optional files
        const files = form.querySelector("input[name='files']")?.files || [];
        if (files.length && created?.sick_leave?.id) {
          const up = new FormData();
          for (const f of files) up.append("files", f);
          up.append("sick_leave_id", String(created.sick_leave.id));
          await fetch(`/users/api/attachments/${uid}`, {
            method: "POST",
            credentials: "same-origin",
            headers: { "X-CSRFToken": getMetaCsrf() },
            body: up
          }).catch(() => {});
        }

        form.classList.add("d-none");
        form.reset();
        await refreshSick(uid, wrap);
      } catch (err) {
        try { setErrors(form, JSON.parse(err.message || "{}").errors || {}); }
        catch { alert(err.message || "Save failed"); }
      }
      return true;
    }

    return false;
  }

  // Expose under all names your panel might call
  window.renderSick = renderSick;
  A.api.renderSick  = renderSick;

  // Register with your global dispatcher
  if (typeof A.registerClick === "function")  A.registerClick(onClick);
  if (typeof A.registerInput === "function")  A.registerInput(onInput);
  else {
    // Fallback direct binding (won’t double-bind thanks to flags)
    if (!window.__sickClickBound__) { document.addEventListener("click", onClick); window.__sickClickBound__ = true; }
    if (!window.__sickInputBound__) { document.addEventListener("input", onInput); window.__sickInputBound__ = true; }
  }
})();
