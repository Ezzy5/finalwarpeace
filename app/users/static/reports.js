// app/users/static/reports.js
(function () {
  "use strict";

  const A = window.UsersApp || (window.UsersApp = { helpers: {}, api: {} });
  const H = A.helpers || {};

  const fetchJSON =
    H.fetchJSON ||
    ((u) =>
      fetch(u, { credentials: "same-origin" }).then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        try { return await r.json(); } catch { return {}; }
      }));

  const postJSON =
    H.postJSON ||
    ((u, b) =>
      fetch(u, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken":
            (H.getMetaCsrf
              ? H.getMetaCsrf()
              : document.querySelector('meta[name="csrf-token"]')?.getAttribute("content")) || "",
        },
        body: JSON.stringify(b || {}),
      }).then(async (r) => {
        if (!r.ok) {
          const t = await r.text().catch(() => "");
          throw new Error(t || `HTTP ${r.status}`);
        }
        try { return await r.json(); } catch { return {}; }
      }));

  const getMetaCsrf =
    H.getMetaCsrf ||
    function () {
      const m = document.querySelector('meta[name="csrf-token"]');
      return m ? m.getAttribute("content") : "";
    };

  // ---------- Date helpers ----------
  function parseYMD(s) {
    if (!s) return null;
    const [y, m, d] = s.split("-").map(Number);
    if (!y || !m || !d) return null;
    const dt = new Date(Date.UTC(y, m - 1, d));
    return new Date(dt.getUTCFullYear(), dt.getUTCMonth(), dt.getUTCDate());
  }
  function fmtYMD(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${dd}`;
  }
  function ensureISO(dateStr) {
    if (!dateStr) return "";
    const ymd = parseYMD(dateStr);
    if (ymd) return fmtYMD(ymd);
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return "";
    return fmtYMD(d);
  }
  function countdownPreview(lastStr, monthsEvery) {
    const last = parseYMD(lastStr);
    if (!last) return "";
    const due = new Date(last);
    due.setMonth(due.getMonth() + monthsEvery);
    const now = parseYMD(fmtYMD(new Date()));
    if (due <= now) return "0m 0d";
    let months =
      (due.getFullYear() - now.getFullYear()) * 12 +
      (due.getMonth() - now.getMonth());
    const anchor = new Date(
      now.getFullYear(),
      now.getMonth() + months,
      now.getDate()
    );
    let days = Math.round((due - anchor) / 86400000);
    if (days < 0) {
      months -= 1;
      const anchor2 = new Date(
        now.getFullYear(),
        now.getMonth() + months,
        now.getDate()
      );
      days = Math.round((due - anchor2) / 86400000);
    }
    return `${months}m ${days}d`;
  }

  // ---------- Row renderers (one file per row) ----------
  function fileRowHTML(file) {
    const stored = encodeURIComponent(file.stored_name || file.path || file.filename || file.name || "");
    const display = file.filename || file.name || stored || "file";
    const uploaded = file.uploaded_at || file.created_at || "";
    const href = stored ? `/users/attachments/${stored}` : "#";
    return `
      <div class="list-group-item d-flex justify-content-between align-items-center">
        <div class="text-truncate">
          <a class="text-decoration-underline attachment-link" href="${href}" target="_blank" rel="noopener" download>${display}</a>
        </div>
        ${uploaded ? `<span class="small text-muted ms-2">${uploaded}</span>` : ""}
      </div>`;
  }

  function groupHTML(group) {
    const dateLabel = group.date || "—";
    const header = `
      <div class="list-group-item bg-light-subtle small text-muted fw-semibold">
        ${dateLabel}
      </div>`;
    const files = Array.isArray(group.files) ? group.files : [];
    return files.length ? header + files.map(fileRowHTML).join("") : header + `<div class="list-group-item text-muted">No files</div>`;
  }

  // Small CSS polish
  (function injectStyle() {
    if (document.getElementById("reports_ui_fix_css")) return;
    const style = document.createElement("style");
    style.id = "reports_ui_fix_css";
    style.textContent = `
      [data-report-wrap] .row.g-2 { align-items: stretch; }
      [data-report-wrap] .card.card-body { overflow: visible; }
      [data-report-wrap] .form-label { white-space: nowrap; }
      [data-report-wrap] .btn[data-action='rep-save'] { white-space: nowrap; }
      .collapse-box { display: none; }
      .collapse-box.show { display: block; }
      .bg-light-subtle { background: rgba(0,0,0,.03); }
      [data-report-wrap] .list-group-item .attachment-link { text-decoration: underline; }
    `;
    document.head.appendChild(style);
  })();

  // ---------- Data renderers ----------
  async function refreshReports(userId, wrap) {
    if (!wrap) return;
    const data = await fetchJSON(`/users/api/reports/${userId}`);

    // summary
    const sLast = wrap.querySelector("[data-rep-sanitary-last]");
    const sDue  = wrap.querySelector("[data-rep-sanitary-due]");
    const sLeft = wrap.querySelector("[data-rep-sanitary-left]");
    if (sLast) sLast.textContent = data.sanitary?.last || "—";
    if (sDue)  sDue.textContent  = data.sanitary?.next_due || "—";
    if (sLeft) sLeft.textContent = `${data.sanitary?.left_months ?? "—"}m ${data.sanitary?.left_days ?? "—"}d`;

    const tLast = wrap.querySelector("[data-rep-system-last]");
    const tDue  = wrap.querySelector("[data-rep-system-due]");
    const tLeft = wrap.querySelector("[data-rep-system-left]");
    if (tLast) tLast.textContent = data.system?.last || "—";
    if (tDue)  tDue.textContent  = data.system?.next_due || "—";
    if (tLeft) tLeft.textContent = `${data.system?.left_months ?? "—"}m ${data.system?.left_days ?? "—"}d`;

    // set form defaults (dates only)
    const sForm = wrap.querySelector(`[data-rep-sanitary-form='${userId}']`);
    if (sForm) sForm.querySelector("input[name='sanitary_last']").value = data.sanitary?.last || "";
    const tForm = wrap.querySelector(`[data-rep-system-form='${userId}']`);
    if (tForm) tForm.querySelector("input[name='system_last']").value = data.system?.last || "";

    // histories
    const sHist = wrap.querySelector(`[data-rep-sanitary-history='${userId}']`);
    const tHist = wrap.querySelector(`[data-rep-system-history='${userId}']`);
    if (sHist) {
      const sItems = data.sanitary_history || [];
      sHist.innerHTML = sItems.length ? sItems.map(groupHTML).join("") : `<div class="list-group-item text-muted">No files</div>`;
    }
    if (tHist) {
      const tItems = data.system_history || [];
      tHist.innerHTML = tItems.length ? tItems.map(groupHTML).join("") : `<div class="list-group-item text-muted">No files</div>`;
    }
  }

  async function renderReports(userId, wrap) {
    if (!wrap) return;
    wrap.innerHTML = `
      <div class="row g-3">
        <!-- SANITARY -->
        <div class="col-md-6"><div class="border rounded p-3" data-report-wrap>
          <div class="d-flex justify-content-between align-items-center">
            <div class="h6 m-0">Санитарен преглед</div>
            <button class="btn btn-sm btn-outline-primary" data-action="rep-sanitary-toggle" data-user="${userId}">Edit</button>
          </div>
          <div class="d-none mt-2" data-rep-sanitary-form="${userId}">
            <div class="row g-2 align-items-end">
              <div class="col-md-7">
                <label class="form-label">Last date</label>
                <input type="date" class="form-control" name="sanitary_last">
              </div>
              <div class="col-md-5">
                <label class="form-label">Countdown to 6 months</label>
                <input type="text" class="form-control" name="sanitary_countdown" disabled>
              </div>
            </div>
            <div class="row g-2 mt-2 align-items-end">
              <div class="col-md-12 d-flex gap-2">
                <button class="btn btn-success btn-sm" data-action="rep-save" data-user="${userId}" data-type="sanitary">Save</button>
                <button class="btn btn-outline-secondary btn-sm" data-action="rep-cancel">Close</button>
              </div>
            </div>
          </div>

          <div class="mt-2 small">
            Last: <span data-rep-sanitary-last>—</span><br>
            Next due: <span data-rep-sanitary-due>—</span><br>
            Left: <span data-rep-sanitary-left>—</span>
          </div>

          <div class="mt-3">
            <div class="d-flex align-items-center justify-content-between">
              <span class="small text-muted">History</span>
              <button class="btn btn-sm btn-outline-secondary" data-action="rep-upload-toggle" data-type="sanitary" data-user="${userId}">Attach files</button>
            </div>
            <div class="collapse-box mt-2" data-rep-upload-box="sanitary" data-user="${userId}">
              <div class="row g-2 align-items-end">
                <div class="col-md-9">
                  <label class="form-label">Select files</label>
                  <input type="file" class="form-control" name="rep_upload_files_sanitary" multiple>
                </div>
                <div class="col-md-3 d-flex align-items-end">
                  <button class="btn btn-primary btn-sm w-100" data-action="rep-upload" data-type="sanitary" data-user="${userId}">Upload</button>
                </div>
              </div>
              <div class="small text-muted mt-1">Files will be attached to the Sanitary report context.</div>
            </div>
            <div class="list-group mt-2" data-rep-sanitary-history="${userId}">
              <div class="list-group-item text-muted">Loading...</div>
            </div>
          </div>
        </div></div>

        <!-- SYSTEM -->
        <div class="col-md-6"><div class="border rounded p-3" data-report-wrap>
          <div class="d-flex justify-content-between align-items-center">
            <div class="h6 m-0">Систематски преглед</div>
            <button class="btn btn-sm btn-outline-primary" data-action="rep-system-toggle" data-user="${userId}">Edit</button>
          </div>
          <div class="d-none mt-2" data-rep-system-form="${userId}">
            <div class="row g-2 align-items-end">
              <div class="col-md-7">
                <label class="form-label">Last date</label>
                <input type="date" class="form-control" name="system_last">
              </div>
              <div class="col-md-5">
                <label class="form-label">Countdown to 24 months</label>
                <input type="text" class="form-control" name="system_countdown" disabled>
              </div>
            </div>
            <div class="row g-2 mt-2 align-items-end">
              <div class="col-md-12 d-flex gap-2">
                <button class="btn btn-success btn-sm" data-action="rep-save" data-user="${userId}" data-type="system">Save</button>
                <button class="btn btn-outline-secondary btn-sm" data-action="rep-cancel">Close</button>
              </div>
            </div>
          </div>

          <div class="mt-2 small">
            Last: <span data-rep-system-last>—</span><br>
            Next due: <span data-rep-system-due>—</span><br>
            Left: <span data-rep-system-left>—</span>
          </div>

          <div class="mt-3">
            <div class="d-flex align-items-center justify-content-between">
              <span class="small text-muted">History</span>
              <button class="btn btn-sm btn-outline-secondary" data-action="rep-upload-toggle" data-type="system" data-user="${userId}">Attach files</button>
            </div>
            <div class="collapse-box mt-2" data-rep-upload-box="system" data-user="${userId}">
              <div class="row g-2 align-items-end">
                <div class="col-md-9">
                  <label class="form-label">Select files</label>
                  <input type="file" class="form-control" name="rep_upload_files_system" multiple>
                </div>
                <div class="col-md-3 d-flex align-items-end">
                  <button class="btn btn-primary btn-sm w-100" data-action="rep-upload" data-type="system" data-user="${userId}">Upload</button>
                </div>
              </div>
              <div class="small text-muted mt-1">Files will be attached to the System report context.</div>
            </div>
            <div class="list-group mt-2" data-rep-system-history="${userId}">
              <div class="list-group-item text-muted">Loading...</div>
            </div>
          </div>
        </div></div>
      </div>
    `;
    await refreshReports(userId, wrap);
  }

  // ---------- Event wiring ----------
  function resolveWrap(fromTarget) {
    return fromTarget.closest("[data-report-wrap]") || null;
  }

  function onInput(e) {
    const wrap = resolveWrap(e.target);
    if (!wrap) return false;

    const repSan = e.target.closest(`[data-rep-sanitary-form]`);
    if (repSan && wrap.contains(repSan)) {
      const last = repSan.querySelector("input[name='sanitary_last']").value;
      repSan.querySelector("input[name='sanitary_countdown']").value = countdownPreview(last, 6);
      return false;
    }
    const repSys = e.target.closest(`[data-rep-system-form]`);
    if (repSys && wrap.contains(repSys)) {
      const last = repSys.querySelector("input[name='system_last']").value;
      repSys.querySelector("input[name='system_countdown']").value = countdownPreview(last, 24);
      return false;
    }
    return false;
  }

  async function tryUploadTo(url, formData) {
    const resp = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": getMetaCsrf() },
      body: formData,
    });
    if (!resp.ok) {
      const txt = await resp.text().catch(() => `HTTP ${resp.status}`);
      const err = new Error(txt);
      err.status = resp.status;
      throw err;
    }
    try { await resp.json(); } catch {}
  }

  async function onClick(e) {
    const t = e.target;
    const wrap = resolveWrap(t);
    if (!wrap) return false;

    // Toggle edit forms
    const sanToggle = t.closest("[data-action='rep-sanitary-toggle']");
    if (sanToggle) {
      e.preventDefault();
      wrap.querySelector(`[data-rep-sanitary-form='${sanToggle.dataset.user}']`)?.classList.toggle("d-none");
      return true;
    }
    const sysToggle = t.closest("[data-action='rep-system-toggle']");
    if (sysToggle) {
      e.preventDefault();
      wrap.querySelector(`[data-rep-system-form='${sysToggle.dataset.user}']`)?.classList.toggle("d-none");
      return true;
    }

    // Toggle collapsible upload boxes in History
    const upToggle = t.closest("[data-action='rep-upload-toggle']");
    if (upToggle) {
      e.preventDefault();
      const type = upToggle.dataset.type;
      const uid  = upToggle.dataset.user;
      const box = wrap.querySelector(`[data-rep-upload-box='${type}'][data-user='${uid}']`);
      if (box) box.classList.toggle("show");
      return true;
    }

    // Cancel edit
    const cancel = t.closest("[data-action='rep-cancel']");
    if (cancel) {
      e.preventDefault();
      cancel.closest("[data-rep-sanitary-form],[data-rep-system-form]")?.classList.add("d-none");
      return true;
    }

    // Save dates (no files)
    const save = t.closest("[data-action='rep-save']");
    if (save) {
      e.preventDefault();
      const uid  = Number(save.dataset.user);
      const type = save.dataset.type;

      const payload = {};
      const sanitaryInput = wrap.querySelector(`[data-rep-sanitary-form='${uid}'] input[name='sanitary_last']`);
      const systemInput   = wrap.querySelector(`[data-rep-system-form='${uid}'] input[name='system_last']`);
      const sanitarySpan  = wrap.querySelector("[data-rep-sanitary-last]");
      const systemSpan    = wrap.querySelector("[data-rep-system-last]");

      const currentSanitary = ensureISO((sanitaryInput?.value || sanitarySpan?.textContent || "").trim());
      const currentSystem   = ensureISO((systemInput?.value   || systemSpan?.textContent   || "").trim());

      payload.sanitary_last = (type === "sanitary" ? ensureISO(sanitaryInput?.value || "") : currentSanitary) || undefined;
      payload.system_last   = (type === "system"   ? ensureISO(systemInput?.value   || "") : currentSystem)   || undefined;

      try {
        await postJSON(`/users/api/reports/${uid}/set`, payload);
        await refreshReports(uid, wrap);
        const form = wrap.querySelector(type === "sanitary" ? `[data-rep-sanitary-form='${uid}']` : `[data-rep-system-form='${uid}']`);
        form?.classList.add("d-none");
      } catch (err) {
        alert(err.message || "Save failed");
      }
      return true;
    }

    // Upload from History collapsible
    const uploadBtn = t.closest("[data-action='rep-upload']");
    if (uploadBtn) {
      e.preventDefault();
      const uid  = Number(uploadBtn.dataset.user);
      const type = uploadBtn.dataset.type;
      const box  = wrap.querySelector(`[data-rep-upload-box='${type}'][data-user='${uid}']`);
      if (!box) return true;

      const inputName = type === "sanitary" ? "rep_upload_files_sanitary" : "rep_upload_files_system";
      const files = box.querySelector(`input[name='${inputName}']`)?.files || [];
      if (!files.length) { alert("Please select one or more files."); return true; }

      // Prefer the form input value (if visible), fall back to summary text
      const formSel = type === "sanitary"
        ? `[data-rep-sanitary-form='${uid}'] input[name='sanitary_last']`
        : `[data-rep-system-form='${uid}'] input[name='system_last']`;
      const formVal = wrap.querySelector(formSel)?.value || "";
      const spanVal = (type === "sanitary"
        ? wrap.querySelector("[data-rep-sanitary-last]")
        : wrap.querySelector("[data-rep-system-last]"))?.textContent || "";
      const lastVal = ensureISO((formVal || spanVal).trim());

      // Build FormData (NO aliases → avoids duplicates)
      const up = new FormData();
      for (const f of files) up.append("files", f);
      up.append("report_kind", type);
      if (lastVal) up.append("last_date", lastVal);

      // Try primary endpoint, then a common fallback (handles both server versions)
      const primaryURL  = `/users/api/attachments/${uid}`;
      const fallbackURL = `/users/api/reports/${uid}/attachments`;

      try {
        try {
          await tryUploadTo(primaryURL, up);
        } catch (e1) {
          if (e1.status === 404 || e1.status === 405) {
            await tryUploadTo(fallbackURL, up);
          } else {
            throw e1;
          }
        }
      } catch (err) {
        console.error("Report upload failed:", err);
        alert(`Attachment upload failed: ${err.message || err}`);
        return true;
      }

      // After success: collapse the box, clear input, refresh lists
      box.classList.remove("show");
      const input = box.querySelector(`input[name='${inputName}']`);
      if (input) input.value = "";
      await refreshReports(uid, wrap);
      return true;
    }

    return false;
  }

  // ---------- Exports ----------
  window.renderReports = renderReports;
  A.api.renderReports = renderReports;

  // ---------- Register with dispatcher ----------
  if (typeof A.registerClick === "function") A.registerClick(onClick);
  if (typeof A.registerInput === "function") A.registerInput(onInput);
  else {
    if (!window.__reportsClickBound__) {
      document.addEventListener("click", onClick);
      window.__reportsClickBound__ = true;
    }
    if (!window.__reportsInputBound__) {
      document.addEventListener("input", onInput);
      window.__reportsInputBound__ = true;
    }
  }
})();
