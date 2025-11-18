// app/users/static/rewards.js
(function () {
  "use strict";

  // ---------- App namespace ----------
  const A = (window.UsersApp = window.UsersApp || { helpers: {}, api: {} });
  A.helpers = A.helpers || {};
  A.api = A.api || {};

  // ---------- Helper fallbacks (use global if provided) ----------
  const getMetaCsrf =
    A.helpers.getMetaCsrf ||
    function () {
      const m = document.querySelector('meta[name="csrf-token"]');
      return m ? m.getAttribute("content") : "";
    };

  const fetchJSON =
    A.helpers.fetchJSON ||
    (async function (url, opts) {
      const res = await fetch(url, {
        credentials: "same-origin",
        ...(opts || {}),
      });

      let data = null;
      try {
        data = await res.json();
      } catch (_) {
        // non-JSON; leave data null
      }

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
    });

  const postJSON =
    A.helpers.postJSON ||
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
      try {
        data = await res.json();
      } catch (_) {
        // ignore
      }

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
    });

  const showAlert =
    A.helpers.showAlert ||
    function (container, message, type = "danger") {
      if (!container) return;
      container.innerHTML = `
        <div class="alert alert-${type} my-2" role="alert">${message}</div>
      `;
    };

  const clearErrors =
    A.helpers.clearErrors ||
    function (form) {
      form?.querySelectorAll("[data-err]").forEach((e) => (e.textContent = ""));
    };

  const setErrors =
    A.helpers.setErrors ||
    function (form, errs) {
      Object.entries(errs || {}).forEach(([name, msg]) => {
        const el = form?.querySelector(`[data-err="${name}"]`);
        if (el) el.textContent = msg || "";
      });
    };

  // ---------- Utils ----------
  const esc = (s) =>
    String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");

  function normalizeType(item) {
    const t = String(item.type || item.kind || item.category || "").toLowerCase();
    if (t === "penalty" || t.includes("penal")) return "penalty";
    return "reward";
  }

  function filesHTML(files) {
    const arr = Array.isArray(files) ? files : [];
    if (!arr.length) return `<div class="small text-muted">No files</div>`;
    return `<div class="small">Files: ${
      arr
        .map(
          (x) =>
            `<a class="text-decoration-underline attachment-link" href="/users/attachments/${esc(
              x.stored_name
            )}" target="_blank" rel="noopener">${esc(x.filename)}</a>`
        )
        .join(" | ")
    }</div>`;
  }

  function headerButton(text, targetId) {
    return `
      <button class="btn btn-link p-0 text-decoration-none"
              data-bs-toggle="collapse" data-bs-target="#${targetId}"
              aria-expanded="false" aria-controls="${targetId}">${esc(text)}</button>`;
  }

  function itemHTML(entry, userId) {
    const id = Number(entry.id);
    const cid = `rp-${userId}-${id}`;
    const when = entry.date || entry.created_at || "—";
    const note = entry.note ? ` — ${esc(entry.note)}` : "";
    const typ = normalizeType(entry);
    const badge =
      typ === "penalty"
        ? `<span class="badge bg-danger ms-2">Penalty</span>`
        : `<span class="badge bg-success ms-2">Reward</span>`;

    return `
      <div class="list-group-item">
        <div class="d-flex justify-content-between align-items-center">
          <div>${headerButton(`${when}${note}`, cid)} ${badge}</div>
        </div>
        <div class="collapse mt-2" id="${cid}">
          ${filesHTML(entry.attachments)}
          <form class="row g-2 align-items-end mt-2" data-rp-attach-form="${id}">
            <div class="col-md-9">
              <label class="form-label">Attach files</label>
              <input type="file" class="form-control form-control-sm" name="file" multiple>
              <div class="text-danger small" data-err="file"></div>
            </div>
            <div class="col-md-3 d-flex gap-2">
              <button class="btn btn-sm btn-primary" data-action="rp-attach" data-user="${userId}" data-id="${id}">Upload</button>
            </div>
          </form>
        </div>
      </div>`;
  }

  function sectionHTML(kind, userId) {
    const title = kind === "penalty" ? "Penalties" : "Rewards";
    return `
      <div class="border rounded p-3 mb-3" data-rp-section="${kind}" data-user="${userId}">
        <div class="d-flex align-items-center justify-content-between flex-wrap gap-2">
          <div class="h6 m-0">${title}</div>
          <button class="btn btn-sm btn-outline-primary" data-action="rp-toggle" data-kind="${kind}" data-user="${userId}">＋ Add</button>
        </div>

        <form class="card card-body p-3 mt-2 d-none" data-rp-form="${kind}-${userId}">
          <input type="hidden" name="type" value="${kind}">
          <div class="row g-2">
            <div class="col-md-3">
              <label class="form-label">Date</label>
              <input type="date" class="form-control" name="date" required>
              <div class="text-danger small" data-err="date"></div>
            </div>
            <div class="col-md-9">
              <label class="form-label">Note</label>
              <input type="text" class="form-control" name="note" placeholder="${title.slice(0,-1)} note…">
              <div class="text-danger small" data-err="note"></div>
            </div>
          </div>
          <div class="mt-3 d-flex gap-2">
            <button class="btn btn-success btn-sm" data-action="rp-save">Save</button>
            <button class="btn btn-outline-secondary btn-sm" data-action="rp-cancel" type="button">Close</button>
          </div>
        </form>

        <div class="list-group mt-2" data-rp-list="${kind}-${userId}">
          <div class="list-group-item text-muted">Loading…</div>
        </div>
      </div>`;
  }

  // ---------- API integration ----------
  async function apiGetRewards(userId) {
    // Supports either {items:[...]} or {rewards:[...], penalties:[...]}
    const data = await fetchJSON(`/users/api/rewards/${userId}`);
    let rewards = [];
    let penalties = [];

    if (Array.isArray(data?.items)) {
      for (const it of data.items) {
        (normalizeType(it) === "penalty" ? penalties : rewards).push(it);
      }
    } else {
      rewards = Array.isArray(data?.rewards) ? data.rewards : [];
      penalties = Array.isArray(data?.penalties) ? data.penalties : [];
    }
    return { rewards, penalties };
  }

  // ---------- Rendering ----------
  async function refreshRewards(userId, wrap) {
    const listR = wrap.querySelector(`[data-rp-list="reward-${userId}"]`);
    const listP = wrap.querySelector(`[data-rp-list="penalty-${userId}"]`);
    if (listR) listR.innerHTML = `<div class="list-group-item text-muted">Loading…</div>`;
    if (listP) listP.innerHTML = `<div class="list-group-item text-muted">Loading…</div>`;

    try {
      const { rewards, penalties } = await apiGetRewards(userId);

      if (listR) {
        listR.innerHTML = rewards.length
          ? rewards.map((it) => itemHTML(it, userId)).join("")
          : `<div class="list-group-item text-muted">No rewards</div>`;
      }
      if (listP) {
        listP.innerHTML = penalties.length
          ? penalties.map((it) => itemHTML(it, userId)).join("")
          : `<div class="list-group-item text-muted">No penalties</div>`;
      }
    } catch (e) {
      const status = e.status || 0;
      const msg =
        status === 403
          ? "Немате дозвола да ги видите овие награди."
          : status === 404
          ? "Корисникот не е пронајден."
          : "Настана грешка при вчитување на наградите.";
      // Show in the rewards list area to keep layout stable
      if (listR) showAlert(listR, msg, "danger");
      if (listP) showAlert(listP, msg, "danger");
      console.error("Rewards load failed:", status, e.message, e.payload);
    }
  }

  async function renderRewards(userId, wrap) {
    if (!wrap || !userId) return;
    // Ensure a known wrapper attribute exists (used by event delegation)
    if (!wrap.hasAttribute("data-rewards-wrap")) {
      wrap.setAttribute("data-rewards-wrap", "1");
    }
    wrap.innerHTML = `${sectionHTML("reward", userId)}${sectionHTML("penalty", userId)}`;
    await refreshRewards(userId, wrap);
  }

  // ---------- Attachments ----------
  async function uploadAttachments(userId, rewardPenaltyId, files, errTarget) {
    if (!files || !files.length) {
      if (errTarget) errTarget.textContent = "Please choose a file.";
      return { ok: false };
    }

    const up = new FormData();
    for (const f of files) up.append("file", f);
    up.append("reward_penalty_id", String(rewardPenaltyId));

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
      if (errTarget) errTarget.textContent = "Upload failed.";
      return { ok: false, data };
    }

    return { ok: true, data: data ?? {} };
  }

  // ---------- Events (scoped to rewards pane) ----------
  async function onClick(ev) {
    const t = ev.target;
    const wrap = t.closest("[data-rewards-wrap]");
    if (!wrap) return false;

    // Toggle open/close form
    const toggle = t.closest("[data-action='rp-toggle']");
    if (toggle) {
      ev.preventDefault();
      const { user: uid, kind } = toggle.dataset;
      wrap
        .querySelector(`[data-rp-form='${kind}-${uid}']`)
        ?.classList.toggle("d-none");
      return true;
    }

    // Close form
    const cancel = t.closest("[data-action='rp-cancel']");
    if (cancel) {
      ev.preventDefault();
      const form = cancel.closest("form[data-rp-form]");
      form?.classList.add("d-none");
      form?.reset();
      clearErrors(form);
      return true;
    }

    // Save form
    const save = t.closest("[data-action='rp-save']");
    if (save) {
      ev.preventDefault();
      const form = save.closest("form[data-rp-form]");
      if (!form) return true;

      const formKey = form.getAttribute("data-rp-form"); // e.g. "penalty-12"
      const uid = Number(formKey.split("-").pop());
      const type = (form.querySelector("input[name='type']")?.value || "reward").toLowerCase();
      clearErrors(form);

      const fd = new FormData(form);
      const date = fd.get("date");
      const note = fd.get("note");

      try {
        await postJSON(`/users/api/rewards/${uid}/create`, {
          type,
          kind: type,
          category: type,
          date,
          note,
        });
        form.classList.add("d-none");
        form.reset();
        await refreshRewards(uid, wrap);
      } catch (err) {
        // If server returned structured validation errors in JSON, surface them
        const p = err.payload || {};
        if (p && p.errors && typeof p.errors === "object") {
          setErrors(form, p.errors);
        } else {
          // Try parsing message as JSON {errors:{...}}
          try {
            const parsed = JSON.parse(err.message || "{}");
            if (parsed.errors) {
              setErrors(form, parsed.errors);
            } else {
              alert(err.message || "Save failed");
            }
          } catch {
            alert(err.message || "Save failed");
          }
        }
      }
      return true;
    }

    // Upload attachments
    const attachBtn = t.closest("[data-action='rp-attach']");
    if (attachBtn) {
      ev.preventDefault();
      const uid = Number(attachBtn.dataset.user);
      const id = Number(attachBtn.dataset.id);
      const form = wrap.querySelector(`[data-rp-attach-form='${id}']`);
      const input = form?.querySelector("input[type='file']");
      const errEl = form?.querySelector("[data-err='file']");
      if (errEl) errEl.textContent = "";
      const files = input?.files || [];
      const ok = await uploadAttachments(uid, id, files, errEl);
      if (ok.ok) await refreshRewards(uid, wrap);
      return true;
    }

    return false;
  }

  // Global delegation (bind once)
  if (typeof A.registerClick === "function") {
    A.registerClick(onClick);
  } else if (!window.__rewardsClickBound__) {
    document.addEventListener("click", onClick);
    window.__rewardsClickBound__ = true;
  }

  // ---------- Exports ----------
  window.renderRewards = renderRewards; // legacy entrypoint if others call it
  A.api.renderRewards = renderRewards;
})();
