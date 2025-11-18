// app/notes/static/notes.js
/* eslint-disable no-console */
(function () {
  "use strict";

  const API = {
    meToday: "/notes/api/me/today",
    create: "/notes/api/me/block/create",
    update: "/notes/api/me/block/update",
    del: "/notes/api/me/block/delete",
    myHist: "/notes/api/me/history",
    dHist: "/notes/api/director/history",     // Director History (dept-wide)
    rt: "/notes/api/director/realtime",       // Real-Time (dept)
  };

  const ROOT_SELECTOR = "#NotesApp";

  // -------- utils --------
  function $(root, sel) {
    return (typeof root === "string" ? document.querySelector(root) : root).querySelector(sel);
  }
  function $all(root, sel) {
    return Array.from((typeof root === "string" ? document.querySelector(root) : root).querySelectorAll(sel));
  }
  function csrf() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  }
  async function getJSON(url) {
    const r = await fetch(url, { credentials: "same-origin" });
    if (!r.ok) {
      const t = await r.text().catch(() => "");
      throw new Error(t || `HTTP ${r.status}`);
    }
    return r.json();
  }
  async function postJSON(url, body) {
    const r = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf(),
      },
      body: JSON.stringify(body || {}),
    });
    if (!r.ok) {
      const t = await r.text().catch(() => "");
      throw new Error(t || `HTTP ${r.status}`);
    }
    return r.json().catch(() => ({}));
  }
  function minutesToHHMM(mins) {
    const s = Math.max(0, Math.floor(mins || 0));
    const h = Math.floor(s / 60);
    const m = s % 60;
    return `${h}h ${m}m`;
  }
  function escapeHtml(s) {
    return String(s || "").replace(/[&<>"']/g, c => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }
  function escapeAttr(s) {
    return escapeHtml(s).replace(/`/g, "&#96;");
  }

  // -------- TODAY (self) --------
  function renderToday(root, data) {
    $(root, "[data-notes='today-date']").textContent = data.today || "";
    $(root, "[data-notes='total-today']").textContent = `Вкупно денес: ${minutesToHHMM(data.total_minutes || 0)}`;

    const list = $(root, "#NotesTodayList");
    list.innerHTML = "";

    (data.blocks || []).forEach(b => {
      const row = document.createElement("div");
      row.className = "list-group-item d-flex align-items-center justify-content-between";
      row.dataset.id = b.id;

      const left = document.createElement("div");
      left.innerHTML =
        `<div><strong>${escapeHtml(b.start)}–${escapeHtml(b.end)}</strong> · <span class="text-muted">${escapeHtml(b.note || "")}</span></div>`;

      const right = document.createElement("div");
      right.className = "d-flex align-items-center gap-2";
      const mins = document.createElement("span");
      mins.className = "badge bg-secondary";
      mins.textContent = minutesToHHMM(b.minutes || 0);
      right.appendChild(mins);

      const editBtn = document.createElement("button");
      editBtn.className = "btn btn-sm btn-outline-primary";
      editBtn.textContent = "Уреди";
      editBtn.addEventListener("click", () => openEditModal(root, b));
      right.appendChild(editBtn);

      const delBtn = document.createElement("button");
      delBtn.className = "btn btn-sm btn-outline-danger";
      delBtn.textContent = "Избриши";
      delBtn.addEventListener("click", async () => {
        if (!confirm("Да се избрише записот?")) return;
        delBtn.disabled = true;
        try {
          await postJSON(API.del, { id: b.id });
          await loadToday(root);
        } catch (e) {
          alert(e.message || e);
        }
        delBtn.disabled = false;
      });
      right.appendChild(delBtn);

      row.appendChild(left);
      row.appendChild(right);
      list.appendChild(row);
    });
  }

  // -------- HISTORY (self) --------
  function renderHistorySelf(root, data) {
    const box = $(root, "#NotesHistory");
    box.innerHTML = "";

    const ownerName = data?.owner?.name || "";

    (data.days || []).forEach(day => {
      const card = document.createElement("div");
      card.className = "card mb-2";
      card.innerHTML = `
        <div class="card-header d-flex justify-content-between align-items-center">
          <div>
            <span class="fw-semibold">${escapeHtml(day.date)}</span>
            ${ownerName ? `<span class="badge bg-light text-dark ms-2">Корисник: ${escapeHtml(ownerName)}</span>` : ""}
          </div>
          <span class="badge bg-secondary">${minutesToHHMM(day.total_minutes || 0)}</span>
        </div>
        <div class="list-group list-group-flush"></div>
      `;
      const list = card.querySelector(".list-group");

      (day.blocks || []).forEach(b => {
        const row = document.createElement("div");
        row.className = "list-group-item d-flex justify-content-between";
        row.innerHTML = `
          <div><strong>${escapeHtml(b.start)}–${escapeHtml(b.end || "—")}</strong> · <span class="text-muted">${escapeHtml(b.note || "")}</span></div>
          <div><span class="badge bg-secondary">${minutesToHHMM(b.minutes || 0)}</span></div>
        `;
        list.appendChild(row);
      });

      (day.corrections || []).forEach(c => {
        const row = document.createElement("div");
        row.className = "list-group-item d-flex justify-content-between";
        const positive = (c.minutes_delta || 0) >= 0;
        row.innerHTML = `
          <div><em>Корекција</em> · <span class="text-muted">${escapeHtml(c.reason || "")}</span></div>
          <div><span class="badge ${positive ? "bg-success" : "bg-danger"}">${positive ? "+" : ""}${minutesToHHMM(Math.abs(c.minutes_delta || 0))}</span></div>
        `;
        list.appendChild(row);
      });

      box.appendChild(card);
    });
  }

  // -------- HISTORY (director, dept-wide) --------
  // Expected payload:
  // {
  //   department: { id, name },
  //   date_from, date_to,
  //   users: [
  //     { user_id, name, total_minutes, days: [{date, total_minutes, blocks: [...]}] }
  //   ]
  // }
  function renderHistoryDirector(root, data) {
    const box = $(root, "#NotesHistory");
    box.innerHTML = "";

    const header = document.createElement("div");
    header.className = "mb-2";
    header.innerHTML =
      `<div class="fw-semibold">${escapeHtml(data?.department?.name || "")}</div>
       <div class="text-muted small">${escapeHtml(data?.date_from || "")} → ${escapeHtml(data?.date_to || "")}</div>`;
    box.appendChild(header);

    (data.users || []).forEach(u => {
      const userCard = document.createElement("div");
      userCard.className = "card mb-3";
      userCard.innerHTML = `
        <div class="card-header d-flex justify-content-between align-items-center">
          <span class="fw-semibold">${escapeHtml(u.name)}</span>
          <span class="badge bg-secondary">${minutesToHHMM(u.total_minutes || 0)}</span>
        </div>
        <div class="list-group list-group-flush"></div>
      `;
      const userList = userCard.querySelector(".list-group");

      (u.days || []).forEach(day => {
        const dayRow = document.createElement("div");
        dayRow.className = "list-group-item";
        const blocks = (day.blocks || []).map(b =>
          `<div class="d-flex justify-content-between">
             <div><strong>${escapeHtml(b.start)}–${escapeHtml(b.end || "—")}</strong> · <span class="text-muted">${escapeHtml(b.note || "")}</span></div>
             <div><span class="badge bg-secondary">${minutesToHHMM(b.minutes || 0)}</span></div>
           </div>`
        ).join("");
        dayRow.innerHTML = `
          <div class="d-flex justify-content-between align-items-center mb-1">
            <span class="fw-semibold">${escapeHtml(day.date)}</span>
            <span class="badge bg-light text-dark">${minutesToHHMM(day.total_minutes || 0)}</span>
          </div>
          ${blocks || '<div class="text-muted">—</div>'}
        `;
        userList.appendChild(dayRow);
      });

      box.appendChild(userCard);
    });
  }

  // -------- REAL-TIME (dept) — unified list --------
  function renderRealtime(root, data) {
    const nameEl = $(root, "[data-notes='rt-dept-name']");
    if (nameEl) nameEl.textContent = data?.department?.name || "";
    const dateEl = $(root, "[data-notes='rt-date']");
    if (dateEl) dateEl.textContent = `Денес: ${escapeHtml(data.date || "")}`;

    const host = $(root, "#NotesRTAll");
    if (!host) return;
    host.innerHTML = "";

    (data.users || []).forEach(u => {
      const card = document.createElement("div");
      card.className = "card";

      const statusBadge =
        u.status === "active" ? `<span class="badge bg-success">Активен</span>` :
        u.status === "idle"   ? `<span class="badge bg-warning text-dark">Неактивен</span>` :
                                `<span class="badge bg-light text-dark">Без записи</span>`;

      card.innerHTML = `
        <div class="card-header d-flex justify-content-between align-items-center">
          <div class="d-flex align-items-center gap-2">
            <span class="fw-semibold">${escapeHtml(u.name)}</span>
            ${statusBadge}
          </div>
          <div class="d-flex align-items-center gap-2">
            ${u.status === "idle" && u.last_end ? `<span class="badge bg-warning text-dark">последно ${escapeHtml(u.last_end)}</span>` : ""}
            <span class="badge bg-secondary">${minutesToHHMM(u.total_minutes || 0)}</span>
          </div>
        </div>
        <div class="list-group list-group-flush"></div>
      `;
      const list = card.querySelector(".list-group");

      if ((u.blocks || []).length === 0) {
        const row = document.createElement("div");
        row.className = "list-group-item text-muted";
        row.textContent = "—";
        list.appendChild(row);
      } else {
        u.blocks.forEach(b => {
          const row = document.createElement("div");
          row.className = "list-group-item d-flex justify-content-between align-items-center";
          row.innerHTML = `
            <div>
              <strong>${escapeHtml(b.start)}–${escapeHtml(b.end || "—")}</strong>
              ${b.active_now ? `<span class="badge bg-success ms-2">сега</span>` : ""}
              · <span class="text-muted">${escapeHtml(b.note || "")}</span>
            </div>
            <div><span class="badge bg-secondary">${minutesToHHMM(b.minutes || 0)}</span></div>
          `;
          list.appendChild(row);
        });
      }

      host.appendChild(card);
    });
  }

  // -------- modal (edit self entry) --------
  function openEditModal(root, b) {
    const html = `
      <div class="modal fade" id="NotesEditModal" tabindex="-1">
        <div class="modal-dialog">
          <div class="modal-content">
            <form>
              <div class="modal-header">
                <h5 class="modal-title">Уреди запис</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
              </div>
              <div class="modal-body row g-2">
                <div class="col-4">
                  <label class="form-label">Почеток</label>
                  <input type="time" class="form-control" name="start" value="${escapeAttr(b.start)}">
                </div>
                <div class="col-4">
                  <label class="form-label">Крај</label>
                  <input type="time" class="form-control" name="end" value="${escapeAttr(b.end)}">
                </div>
                <div class="col-12">
                  <label class="form-label">Белешка</label>
                  <input class="form-control" name="note" value="${escapeAttr(b.note || "")}">
                </div>
              </div>
              <div class="modal-footer">
                <button class="btn btn-primary" type="submit">Зачувај</button>
                <button class="btn btn-secondary" type="button" data-bs-dismiss="modal">Затвори</button>
              </div>
            </form>
          </div>
        </div>
      </div>`;
    const wrap = document.createElement("div");
    wrap.innerHTML = html;
    const modal = wrap.firstElementChild;
    document.body.appendChild(modal);

    modal.querySelector("form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.currentTarget);
      const payload = {
        id: b.id,
        start: fd.get("start"),
        end: fd.get("end"),
        note: fd.get("note"),
      };
      try {
        await postJSON(API.update, payload);
        closeModal(modal, async () => {
          await loadToday(root);
        });
      } catch (err) {
        alert(err.message || err);
      }
    });

    const Modal = window.bootstrap?.Modal;
    if (Modal) {
      const m = new Modal(modal);
      modal.addEventListener("hidden.bs.modal", () => modal.remove(), { once: true });
      m.show();
    } else {
      modal.style.display = "block";
    }
  }
  function closeModal(modal, after) {
    const inst = window.bootstrap?.Modal?.getInstance(modal);
    if (inst) {
      modal.addEventListener("hidden.bs.modal", () => {
        modal.remove();
        if (typeof after === "function") after();
      }, { once: true });
      inst.hide();
    } else {
      modal.remove();
      if (typeof after === "function") after();
    }
  }

  // -------- loaders --------
  async function loadToday(root) {
    const data = await getJSON(API.meToday);
    renderToday(root, data);
  }

  // Decides which history to load based on “director mode”
  async function loadHistory(root) {
    const start = $(root, "[data-notes='hist-start']").value;
    const end   = $(root, "[data-notes='hist-end']").value;

    // Director mode if dept switcher is visible and has options
    const deptSel = $(root, "[data-notes='dept-select']");
    const isDirector = !!(deptSel && deptSel.options && deptSel.options.length > 0);

    if (isDirector) {
      if (!deptSel.value) { alert("Одберете оддел."); return; }
      const url = `${API.dHist}?department_id=${encodeURIComponent(deptSel.value)}&start=${encodeURIComponent(start || "")}&end=${encodeURIComponent(end || "")}`;
      const data = await getJSON(url);
      renderHistoryDirector(root, data);
    } else {
      const url = `${API.myHist}?start=${encodeURIComponent(start || "")}&end=${encodeURIComponent(end || "")}`;
      const data = await getJSON(url);
      renderHistorySelf(root, data);
    }
  }

  async function addEntry(root) {
    const start = $(root, "[data-notes='start']").value;
    const end   = $(root, "[data-notes='end']").value;
    const note  = $(root, "[data-notes='note']").value.trim();

    if (!/^\d{2}:\d{2}$/.test(start) || !/^\d{2}:\d{2}$/.test(end)) {
      alert("Внесете валидно време (HH:MM) за почеток и крај.");
      return;
    }

    try {
      await postJSON(API.create, { start, end, note });
      $(root, "[data-notes='start']").value = "";
      $(root, "[data-notes='end']").value = "";
      $(root, "[data-notes='note']").value = "";
      await loadToday(root);
    } catch (e) {
      alert(e.message || e);
    }
  }

  async function loadRealtime(root) {
    const sel = $(root, "[data-notes='dept-select']");
    if (!sel || !sel.value) return;
    const data = await getJSON(`${API.rt}?department_id=${encodeURIComponent(sel.value)}`);
    renderRealtime(root, data);
  }

  // -------- mount --------
  let realtimeTimer = null;

  async function mount(rootEl) {
    const root = typeof rootEl === "string" ? document.querySelector(rootEl) : rootEl;
    if (!root) return;

    // Buttons in panel
    root.addEventListener("click", async (e) => {
      const t = e.target.closest("[data-action]");
      if (!t) return;
      const act = t.getAttribute("data-action");
      try {
        if (act === "add-entry") {
          await addEntry(root);
        } else if (act === "load-history") {
          await loadHistory(root);
        }
      } catch (err) {
        alert(err.message || err);
      }
    });

    // Dept switcher: used by Real-Time and Director History
    const sel = $(root, "[data-notes='dept-select']");
    if (sel) sel.addEventListener("change", async () => {
      // refresh realtime immediately on change
      await loadRealtime(root).catch(()=>{});
      // if History tab is currently visible, also refresh history to match dept
      const activePane = root.querySelector(".tab-pane.active");
      if (activePane && activePane.id === "tab-my-history") {
        await loadHistory(root).catch(()=>{});
      }
    });

    // Initialize self "today"
    await loadToday(root);

    // Default history range = last 7 days
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - 7);
    const toISO = d => d.toISOString().slice(0, 10);
    const hs = $(root, "[data-notes='hist-start']");
    const he = $(root, "[data-notes='hist-end']");
    if (hs && he) { he.value = toISO(end); hs.value = toISO(start); }

    // Boot realtime if director
    if (sel && sel.options.length) {
      await loadRealtime(root).catch(()=>{});
      if (realtimeTimer) clearInterval(realtimeTimer);
      realtimeTimer = setInterval(() => loadRealtime(root).catch(()=>{}), 30000); // 30s
    }
  }

  // expose for SPA loader
  window.mountNotesPanel = function (selectorOrEl) {
    try { return mount(selectorOrEl || ROOT_SELECTOR); }
    catch (e) { console.error("mountNotesPanel error:", e); }
  };

  // auto-mount when directly visiting /notes/panel (non-SPA)
  if (document.readyState === "complete" || document.readyState === "interactive") {
    const el = document.querySelector(ROOT_SELECTOR);
    if (el && !window.__NOTES_AUTO_MOUNTED__) {
      window.__NOTES_AUTO_MOUNTED__ = true;
      mount(el).catch(err => console.error(err));
    }
  } else {
    document.addEventListener("DOMContentLoaded", () => {
      const el = document.querySelector(ROOT_SELECTOR);
      if (el && !window.__NOTES_AUTO_MOUNTED__) {
        window.__NOTES_AUTO_MOUNTED__ = true;
        mount(el).catch(err => console.error(err));
      }
    });
  }
})();
