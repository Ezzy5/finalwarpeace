// app/users/static/uniforms.js
(function () {
  "use strict";

  const A = window.UsersApp || (window.UsersApp = { helpers: {}, api: {} });
  const H = A.helpers || {};

  // ---------- Helpers ----------
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

  const clearErrors = H.clearErrors || function(){};
  const setErrors   = H.setErrors   || function(){};
  const getMetaCsrf = H.getMetaCsrf || function () {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  };

  // Upload single (tries key "file" then "files")
  async function uploadSingle(userId, file, { uniform_id }) {
    const tryOnce = async (keyName) => {
      const up = new FormData();
      up.append(keyName, file);
      up.append("uniform_id", String(uniform_id)); // backend expects this
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
      try { return await r.json(); } catch { return {}; }
    };
    try { return await tryOnce("file"); }
    catch (_) { return await tryOnce("files"); }
  }

  async function uploadAttachments(userId, filesSource, context) {
    let files = [];
    if (filesSource instanceof FileList) files = Array.from(filesSource);
    else if (Array.isArray(filesSource)) files = filesSource;
    else if (filesSource && filesSource.tagName === "INPUT") files = Array.from(filesSource.files || []);
    else if (filesSource) files = [filesSource];
    if (!files.length) throw new Error("No files selected");

    const results = [];
    for (const f of files) {
      if (!f || !f.name || f.size === 0) continue;
      const res = await uploadSingle(userId, f, context);
      results.push(res);
    }
    return results;
  }

  function headerButton(text, targetId) {
    return `<button class="btn btn-link p-0 text-decoration-none"
                    data-bs-toggle="collapse" data-bs-target="#${targetId}"
                    aria-expanded="false" aria-controls="${targetId}">${text}</button>`;
  }

  // Format "YYYY-MM-DD HH:MM:SS"
  function fmtDateTime(s) {
    if (!s) return "";
    // If we already get "YYYY-MM-DD HH:MM:SS" from backend, keep it.
    if (s.includes(" ") && !s.includes("T")) return s;
    // Otherwise parse ISO and format
    const d = new Date(s);
    if (Number.isNaN(d.getTime())) return s;
    const y = d.getFullYear();
    const m = String(d.getMonth()+1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    const ss = String(d.getSeconds()).padStart(2, "0");
    return `${y}-${m}-${dd} ${hh}:${mm}:${ss}`;
    // If you prefer UTC, use getUTC* instead.
  }

  // One-file-per-row
  function filesListHTML(files) {
    if (!files?.length) return `<div class="list-group-item small text-muted">No files</div>`;
    return files.map(x => `
      <div class="list-group-item d-flex justify-content-between align-items-center">
        <a class="text-decoration-underline attachment-link text-truncate" href="/users/attachments/${x.stored_name}" target="_blank" rel="noopener">${x.filename}</a>
        ${x.uploaded_at ? `<span class="small text-muted ms-2">${fmtDateTime(x.uploaded_at)}</span>` : ""}
      </div>
    `).join("");
  }

  // prevent clipped controls in cards
  (function injectStyle(){
    if (document.getElementById("uniforms_ui_fix_css")) return;
    const style = document.createElement("style");
    style.id = "uniforms_ui_fix_css";
    style.textContent = `
      [data-uniform-wrap] .card.card-body { overflow: visible; }
      [data-uniform-wrap] .form-label { white-space: nowrap; }
      [data-uniform-wrap] .row.g-2 { align-items: stretch; }
      [data-uniform-wrap] a.attachment-link { text-decoration: underline; }
    `;
    document.head.appendChild(style);
  })();

  // ---------- Renderers ----------
  function uniformItemHTML(userId, un) {
    const cid = `un-${userId}-${un.id}`;
    const next = un.next_due_date || "—";
    const assigned = un.assigned_date || "—";
    const kind = un.kind || "—";
    const every = (un.renew_every_months != null ? `${un.renew_every_months}m` : "—");
    return `<div class="list-group-item">
      <div class="d-flex justify-content-between align-items-center">
        <div>${headerButton(`${kind} — ${assigned} • renew ${every}`, cid)}</div>
        <div class="small text-muted">Next due: ${next}</div>
      </div>
      <div class="collapse mt-2" id="${cid}">
        <div class="list-group" data-un-files="${un.id}">
          ${filesListHTML(un.attachments)}
        </div>
        <form class="row g-2 align-items-end mt-2" data-un-attach-form="${un.id}">
          <div class="col-md-9">
            <label class="form-label">Attach files</label>
            <input type="file" class="form-control form-control-sm" name="files" multiple>
          </div>
          <div class="col-md-3 d-flex gap-2">
            <button class="btn btn-sm btn-primary" data-action="un-attach" data-user="${userId}" data-id="${un.id}">Upload</button>
          </div>
        </form>
      </div>
    </div>`;
  }

  async function refreshUniforms(userId, wrap) {
    if (!wrap) return;
    // cache-buster to avoid stale lists after upload
    const data = await fetchJSON(`/users/api/uniforms/${userId}?t=${Date.now()}`);

    const act = wrap.querySelector(`[data-uniform-active='${userId}']`);
    const hist = wrap.querySelector(`[data-uniform-history='${userId}']`);

    const active = Array.isArray(data.active) ? data.active : [];
    const history = Array.isArray(data.history) ? data.history : [];

    if (act) {
      act.innerHTML = active.length
        ? active.map(un => uniformItemHTML(userId, un)).join("")
        : `<div class="list-group-item text-muted">No active uniforms</div>`;
    }
    if (hist) {
      hist.innerHTML = history.length
        ? history.map(un => uniformItemHTML(userId, un)).join("")
        : `<div class="list-group-item text-muted">No history</div>`;
    }
  }

  async function renderUniforms(userId, wrap) {
    if (!wrap) return;
    wrap.innerHTML = `
      <div class="mb-2 d-flex align-items-center justify-content-between flex-wrap gap-2">
        <div class="small text-muted">Assigned uniforms</div>
        <button class="btn btn-sm btn-outline-primary" data-action="un-toggle" data-user="${userId}">＋ Add Uniform</button>
      </div>

      <form class="card card-body p-3 mb-3 d-none" data-uniform-form="${userId}">
        <div class="row g-2">
          <div class="col-md-6">
            <label class="form-label">Kind</label>
            <input type="text" class="form-control" name="kind" required>
            <div class="text-danger small" data-err="kind"></div>
          </div>
          <div class="col-md-3">
            <label class="form-label">Assigned date</label>
            <input type="date" class="form-control" name="assigned_date" required>
            <div class="text-danger small" data-err="assigned_date"></div>
          </div>
          <div class="col-md-3">
            <label class="form-label">Renew every (months)</label>
            <input type="number" class="form-control" name="renew_every_months" min="1" step="1" required>
            <div class="text-danger small" data-err="renew_every_months"></div>
          </div>
        </div>
        <div class="row g-2 mt-2">
          <div class="col-12">
            <label class="form-label">Attach files (optional)</label>
            <input type="file" class="form-control" name="files" multiple>
          </div>
        </div>
        <div class="mt-3 d-flex gap-2">
          <button class="btn btn-success btn-sm" data-action="un-save" data-user="${userId}">Save</button>
          <button class="btn btn-outline-secondary btn-sm" data-action="un-cancel">Close</button>
        </div>
      </form>

      <h6>Active</h6>
      <div class="list-group" data-uniform-active="${userId}">
        <div class="list-group-item text-muted">Loading...</div>
      </div>

      <h6 class="mt-3">History</h6>
      <div class="list-group" data-uniform-history="${userId}">
        <div class="list-group-item text-muted">Loading...</div>
      </div>
    `;
    await refreshUniforms(userId, wrap);
  }

  // ---------- Events ----------
  function resolveWrap(fromTarget) {
    return fromTarget.closest("[data-uniform-wrap]") || null;
  }

  // helper: inject newly uploaded files into the open item immediately
  function appendUploadedFiles(wrap, uniformId, uploadedPayloads) {
    const box = wrap.querySelector(`[data-un-files='${uniformId}']`);
    if (!box) return;

    const items = [];
    for (const payload of uploadedPayloads) {
      const arr = Array.isArray(payload?.items) ? payload.items : []; // backend returns .items
      for (const f of arr) {
        if (f?.stored_name && f?.filename) {
          items.push(f);
        }
      }
    }
    if (!items.length) return;

    const rows = items.map(i => `
      <div class="list-group-item d-flex justify-content-between align-items-center">
        <a class="text-decoration-underline attachment-link text-truncate" href="/users/attachments/${i.stored_name}" target="_blank" rel="noopener">${i.filename}</a>
        ${i.uploaded_at ? `<span class="small text-muted ms-2">${fmtDateTime(i.uploaded_at)}</span>` : ""}
      </div>
    `).join("");

    if (box.textContent.trim() === "No files") {
      box.innerHTML = rows;
    } else {
      box.insertAdjacentHTML("beforeend", rows);
    }
  }

  async function onClick(e) {
    const t = e.target;
    const wrap = resolveWrap(t);
    if (!wrap) return false;

    // Toggle create form
    const unToggle = t.closest("[data-action='un-toggle']");
    if (unToggle) {
      e.preventDefault();
      const uid = unToggle.dataset.user;
      wrap.querySelector(`[data-uniform-form='${uid}']`)?.classList.toggle("d-none");
      return true;
    }

    // Cancel create
    const unCancel = t.closest("[data-action='un-cancel']");
    if (unCancel) {
      e.preventDefault();
      const form = wrap.querySelector("form[data-uniform-form]");
      if (form) { form.classList.add("d-none"); form.reset(); clearErrors(form); }
      return true;
    }

    // Save new uniform (and optional files)
    const unSave = t.closest("[data-action='un-save']");
    if (unSave) {
      e.preventDefault();
      const uid = Number(unSave.dataset.user);
      const form = wrap.querySelector(`[data-uniform-form='${uid}']`);
      if (!form) return true;

      clearErrors(form);
      const fd = new FormData(form);
      const body = Object.fromEntries(fd.entries());

      try {
        const created = await postJSON(`/users/api/uniforms/${uid}/create`, body);

        const filesEl = form.querySelector("input[name='files']");
        if (filesEl?.files?.length && created?.item?.id) {
          await uploadAttachments(uid, filesEl.files, { uniform_id: created.item.id });
        }

        form.classList.add("d-none");
        form.reset();
        await refreshUniforms(uid, wrap);
      } catch (err) {
        try { setErrors(form, JSON.parse(err.message || "{}").errors || {}); }
        catch { alert(err.message || "Save failed"); }
      }
      return true;
    }

    // Per-item attach upload
    const attach = t.closest("[data-action='un-attach']");
    if (attach) {
      e.preventDefault();
      const uid = Number(attach.dataset.user);
      const id  = Number(attach.dataset.id);
      const aForm = wrap.querySelector(`[data-un-attach-form='${id}']`);
      const filesEl = aForm?.querySelector("input[name='files']");
      if (!filesEl?.files?.length) return true;

      try {
        const payloads = await uploadAttachments(uid, filesEl.files, { uniform_id: id });
        appendUploadedFiles(wrap, id, payloads);  // immediate UX
        await refreshUniforms(uid, wrap);         // re-sync & auto-move if due today
      } catch (err) {
        alert(err.message || "Upload failed");
      }
      return true;
    }

    return false;
  }

  // ---------- Exports ----------
  window.renderUniforms = renderUniforms;
  A.api.renderUniforms = renderUniforms;

  // ---------- Register ----------
  if (typeof A.registerClick === "function") {
    A.registerClick(onClick);
  } else if (!window.__uniformsClickBound__) {
    document.addEventListener("click", onClick);
    window.__uniformsClickBound__ = true;
  }
})();
