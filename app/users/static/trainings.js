// app/users/static/trainings.js
(function () {
  "use strict";

  // Namespace + safe helpers
  const A = (window.UsersApp = window.UsersApp || { helpers: {}, api: {} });
  const H = A.helpers || {};

  const fetchJSON = H.fetchJSON || (async (url) => {
    const r = await fetch(url, { credentials: "same-origin", cache: "no-store" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    try { return await r.json(); } catch { return {}; }
  });

  const postJSON = H.postJSON || (async (url, body) => {
    const r = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": (H.getMetaCsrf
          ? H.getMetaCsrf()
          : document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || ""),
      },
      body: JSON.stringify(body || {}),
    });
    if (!r.ok) {
      const t = await r.text().catch(() => "");
      throw new Error(t || `HTTP ${r.status}`);
    }
    try { return await r.json(); } catch { return {}; }
  });

  const clearErrors = H.clearErrors || function (form) {
    form?.querySelectorAll("[data-err]").forEach((e) => (e.textContent = ""));
  };
  const setErrors = H.setErrors || function (form, errs) {
    Object.entries(errs || {}).forEach(([name, msg]) => {
      const el = form?.querySelector(`[data-err="${name}"]`);
      if (el) el.textContent = msg || "";
    });
  };
  const getMetaCsrf = H.getMetaCsrf || function () {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  };

  // Styles
  (function injectStyle() {
    if (document.getElementById("trainings_ui_fix_css")) return;
    const style = document.createElement("style");
    style.id = "trainings_ui_fix_css";
    style.textContent = `
      [data-training-wrap] .card.card-body { overflow: visible; }
      [data-training-wrap] .form-label { white-space: nowrap; }
      [data-training-wrap] .row.g-2 { align-items: stretch; }
      a.attachment-link { text-decoration: underline; }
    `;
    document.head.appendChild(style);
  })();

  // UI helpers
  function headerButton(text, targetId) {
    return `<button class="btn btn-link p-0 text-decoration-none"
                    data-bs-toggle="collapse" data-bs-target="#${targetId}"
                    aria-expanded="false" aria-controls="${targetId}">${text}</button>`;
  }
  function fmtDT(s) {
    if (!s) return "";
    if (s.includes(" ") && !s.includes("T")) return s;
    const d = new Date(s);
    if (Number.isNaN(d.getTime())) return s;
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    const ss = String(d.getSeconds()).padStart(2, "0");
    return `${y}-${m}-${dd} ${hh}:${mm}:${ss}`;
  }
  function filesListHTML(files) {
    if (!files?.length) {
      return `<div class="list-group-item small text-muted">No files</div>`;
    }
    return files.map(x => `
      <div class="list-group-item d-flex justify-content-between align-items-center">
        <a class="text-decoration-underline attachment-link text-truncate" href="/users/attachments/${x.stored_name}" target="_blank" rel="noopener">${x.filename}</a>
        ${x.uploaded_at ? `<span class="small text-muted ms-2">${fmtDT(x.uploaded_at)}</span>` : ""}
      </div>
    `).join("");
  }
  function rowHTML(userId, t) {
    const cid = `tr-${userId}-${t.id}`;
    return `<div class="list-group-item">
      <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
        <div>
          ${headerButton(`${t.title} — ${t.start_date} → ${t.end_date}`, cid)}
          <span class="badge bg-${t.status === 'active' ? 'success' : 'secondary'} ms-2">${t.status}</span>
        </div>
        <div class="btn-group btn-group-sm">
          <button class="btn btn-outline-secondary" data-action="tr-edit" data-user="${userId}" data-id="${t.id}">Edit</button>
          <button class="btn btn-outline-danger" data-action="tr-del" data-user="${userId}" data-id="${t.id}">Delete</button>
        </div>
      </div>
      <div class="collapse mt-2" id="${cid}">
        <div class="list-group" data-tr-files="${t.id}">
          ${filesListHTML(t.attachments)}
        </div>
        <div class="mt-2 d-none" data-tr-editbox="${t.id}">
          <div class="row g-2">
            <div class="col-md-4">
              <label class="form-label">Title</label>
              <input class="form-control form-control-sm" data-tr-title="${t.id}" value="${t.title}">
            </div>
            <div class="col-md-3">
              <label class="form-label">Start</label>
              <input type="date" class="form-control form-control-sm" data-tr-start="${t.id}" value="${t.start_date}">
            </div>
            <div class="col-md-3">
              <label class="form-label">End</label>
              <input type="date" class="form-control form-control-sm" data-tr-end="${t.id}" value="${t.end_date}">
            </div>
            <div class="col-md-2">
              <label class="form-label">Files</label>
              <input type="file" class="form-control form-control-sm" data-tr-files-input="${t.id}" multiple>
            </div>
          </div>
          <div class="mt-2 d-flex gap-2">
            <button class="btn btn-success btn-sm" data-action="tr-update" data-user="${userId}" data-id="${t.id}">Save</button>
            <button class="btn btn-outline-secondary btn-sm" data-action="tr-edit-cancel" data-id="${t.id}">Close</button>
          </div>
        </div>
      </div>
    </div>`;
  }

  async function refreshTrainings(userId, root) {
    if (!root) return;
    const act = root.querySelector(`[data-training-active='${userId}']`);
    const hist = root.querySelector(`[data-training-history='${userId}']`);

    try {
      const data = await fetchJSON(`/users/api/trainings/${userId}?t=${Date.now()}`);
      const active = Array.isArray(data.active) ? data.active : [];
      const history = Array.isArray(data.history) ? data.history : [];

      if (act) {
        act.innerHTML = active.length
          ? active.map(t => rowHTML(userId, t)).join("")
          : `<div class="list-group-item text-muted">No active trainings</div>`;
      }
      if (hist) {
        hist.innerHTML = history.length
          ? history.map(t => rowHTML(userId, t)).join("")
          : `<div class="list-group-item text-muted">No history</div>`;
      }
    } catch (err) {
      const msg = (err && err.message) ? err.message : "Failed to load trainings.";
      if (act) act.innerHTML = `<div class="list-group-item text-danger">Error: ${msg}</div>`;
      if (hist) hist.innerHTML = `<div class="list-group-item text-danger">Error: ${msg}</div>`;
    }
  }

  async function renderTrainings(userId, container) {
    if (!container) return;
    container.setAttribute("data-training-wrap", String(userId));
    container.innerHTML = `
      <div class="mb-2 d-flex align-items-center justify-content-between flex-wrap gap-2">
        <div class="small text-muted">Trainings</div>
        <button class="btn btn-sm btn-outline-primary" data-action="tr-toggle" data-user="${userId}">＋ Add Training</button>
      </div>

      <form class="card card-body p-3 mb-3 d-none" data-training-form="${userId}">
        <div class="row g-2">
          <div class="col-md-6">
            <label class="form-label">Title</label>
            <input type="text" class="form-control" name="title" required>
            <div class="text-danger small" data-err="title"></div>
          </div>
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
        </div>
        <div class="row g-2 mt-2">
          <div class="col-12">
            <label class="form-label">Attach files (optional)</label>
            <input type="file" class="form-control" name="files" multiple>
          </div>
        </div>
        <div class="mt-3 d-flex gap-2">
          <button class="btn btn-success btn-sm" data-action="tr-save" data-user="${userId}">Save</button>
          <button class="btn btn-outline-secondary btn-sm" data-action="tr-cancel">Close</button>
        </div>
      </form>

      <div class="mt-2">
        <h6>Active</h6>
        <div class="list-group" data-training-active="${userId}">
          <div class="list-group-item text-muted">Loading...</div>
        </div>
      </div>
      <div class="mt-3">
        <h6>History</h6>
        <div class="list-group" data-training-history="${userId}">
          <div class="list-group-item text-muted">Loading...</div>
        </div>
      </div>
    `;
    await refreshTrainings(userId, container);
  }

  // Upload helper (graceful fallback to "file" or "files")
  async function uploadTrainingFiles(userId, trainingId, files) {
    if (!files?.length) return;
    const tryOnce = async (keyName) => {
      const up = new FormData();
      for (const f of files) up.append(keyName, f);
      up.append("training_id", String(trainingId));
      const r = await fetch(`/users/api/attachments/${userId}`, {
        method: "POST",
        credentials: "same-origin",
        headers: { "X-CSRFToken": getMetaCsrf() },
        body: up,
      });
      if (!r.ok) {
        const txt = await r.text().catch(() => "");
        throw new Error(txt || `HTTP ${r.status}`);
      }
    };
    try { await tryOnce("files"); } catch { await tryOnce("file"); }
  }

  // Events
  function resolveRoot(el) {
    return el.closest("[data-training-wrap]") || el.closest("[data-users-wrap]") || document;
  }

  async function onClick(e) {
    const t = e.target;
    const root = resolveRoot(t);

    const trToggle = t.closest("[data-action='tr-toggle']");
    if (trToggle) {
      e.preventDefault();
      root.querySelector(`[data-training-form='${trToggle.dataset.user}']`)?.classList.toggle("d-none");
      return true;
    }

    const trCancel = t.closest("[data-action='tr-cancel']");
    if (trCancel) {
      e.preventDefault();
      const form = trCancel.closest("form[data-training-form]");
      if (form) { form.classList.add("d-none"); form.reset(); clearErrors(form); }
      return true;
    }

    const trSave = t.closest("[data-action='tr-save']");
    if (trSave) {
      e.preventDefault();
      const uid = Number(trSave.dataset.user);
      const form = root.querySelector(`[data-training-form='${uid}']`);
      if (!form) return true;

      clearErrors(form);
      const body = Object.fromEntries(new FormData(form).entries());
      try {
        const created = await postJSON(`/users/api/trainings/${uid}/create`, body);
        const files = form.querySelector("input[name='files']")?.files || [];
        if (files.length && created?.item?.id) {
          await uploadTrainingFiles(uid, created.item.id, files);
        }
        form.classList.add("d-none");
        form.reset();
        await refreshTrainings(uid, root);
      } catch (err) {
        try { setErrors(form, JSON.parse(err.message || "{}").errors || {}); }
        catch { alert(err.message || "Save failed"); }
      }
      return true;
    }

    const trEdit = t.closest("[data-action='tr-edit']");
    if (trEdit) {
      e.preventDefault();
      root.querySelector(`[data-tr-editbox='${trEdit.dataset.id}']`)?.classList.toggle("d-none");
      return true;
    }

    const trEditCancel = t.closest("[data-action='tr-edit-cancel']");
    if (trEditCancel) {
      e.preventDefault();
      trEditCancel.closest("[data-tr-editbox]")?.classList.add("d-none");
      return true;
    }

    const trUpdate = t.closest("[data-action='tr-update']");
    if (trUpdate) {
      e.preventDefault();
      const uid = Number(trUpdate.dataset.user);
      const id  = Number(trUpdate.dataset.id);
      const box = root.querySelector(`[data-tr-editbox='${id}']`);
      if (!box) return true;
      const payload = {
        title:      box.querySelector(`[data-tr-title='${id}']`)?.value || "",
        start_date: box.querySelector(`[data-tr-start='${id}']`)?.value || "",
        end_date:   box.querySelector(`[data-tr-end='${id}']`)?.value || "",
      };
      try {
        await postJSON(`/users/api/trainings/${uid}/${id}/update`, payload);
        const files = box.querySelector(`[data-tr-files-input='${id}']`)?.files || [];
        if (files.length) await uploadTrainingFiles(uid, id, files);
        await refreshTrainings(uid, root);
        box.classList.add("d-none");
      } catch (err) {
        alert(err.message || "Update failed");
      }
      return true;
    }

    const trDel = t.closest("[data-action='tr-del']");
    if (trDel) {
      e.preventDefault();
      const uid = Number(trDel.dataset.user);
      const id  = Number(trDel.dataset.id);
      if (!confirm("Delete this training?")) return true;
      try {
        await postJSON(`/users/api/trainings/${uid}/${id}/delete`, {});
        await refreshTrainings(uid, root);
      } catch (err) {
        alert(err.message || "Delete failed");
      }
      return true;
    }

    return false;
  }

  // Export
  window.renderTrainings = renderTrainings;
  A.api.renderTrainings = renderTrainings;

  // Register click handler (idempotent)
  if (typeof A.registerClick === "function") {
    A.registerClick(onClick);
  } else if (!window.__trainingsClickBound__) {
    document.addEventListener("click", onClick);
    window.__trainingsClickBound__ = true;
  }

  // --- Auto-mount if a container exists ---
  function autoMount() {
    document.querySelectorAll("[data-training-wrap]").forEach((el) => {
      const uidAttr = el.getAttribute("data-user");
      if (!uidAttr) return;
      const uid = Number(uidAttr);
      if (!Number.isFinite(uid)) return;
      renderTrainings(uid, el);
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", autoMount, { once: true });
  } else {
    autoMount();
  }
})();
