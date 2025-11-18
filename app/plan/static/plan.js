// app/plan/static/plan.js
(() => {
  if (window.__planMounted) return;
  window.__planMounted = true;

  // ---------------- Helpers ----------------
  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const fmtISO = (d) => d.toISOString().slice(0, 10);
  const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
  const mondayOf = (d) => { const x = new Date(d); const w = x.getDay(); const diff = (w + 6) % 7; x.setDate(x.getDate() - diff); x.setHours(0,0,0,0); return x; };

  // Read CSRF token from <meta name="csrf-token" content="...">
  function csrf() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : "";
  }

  async function mustOk(promiseOrResponse) {
    const res = await promiseOrResponse;
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(text || `HTTP ${res.status}`);
    }
    return res;
  }

  async function apiGet(url) {
    const r = await mustOk(fetch(url, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    }));
    try { return await r.json(); } catch { return {}; }
  }

  async function apiPost(url, body) {
    const r = await mustOk(fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrf(),
      },
      credentials: "same-origin",
      body: JSON.stringify(body || {}),
    }));
    try { return await r.json(); } catch { return {}; }
  }

  async function apiPostForm(url, formData) {
    const token = csrf();
    if (token && !formData.has("csrf_token")) {
      formData.append("csrf_token", token);
    }
    const r = await mustOk(fetch(url, {
      method: "POST",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": token,
      },
      credentials: "same-origin",
      body: formData,
    }));
    try { return await r.json(); } catch { return {}; }
  }

  function escapeHtml(s = "") {
    return String(s).replace(/[&<>"']/g, m => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[m]));
  }
  const prClass = (p) => p ? `priority-${p}` : "";
  const stClass = (s) => s ? `status-${s}` : "";

  // ---------------- File preview helpers (client-side) ----------------
  const _objectUrls = new Set();
  function revokeObjectUrls() {
    _objectUrls.forEach(url => URL.revokeObjectURL(url));
    _objectUrls.clear();
  }
  function isPreviewableLocal(file) {
    if (!file || !file.type) return false;
    if (file.type === "application/pdf") return true;
    if (file.type.startsWith("image/")) return true;
    return false;
  }
  function makeObjectUrl(file) {
    const url = URL.createObjectURL(file);
    _objectUrls.add(url);
    return url;
  }

  // ---------------- Mount ----------------
  window.mountPlanPanel = async () => {
    const app = $("#PlanApp");
    if (!app) return;
    const role = app.dataset.role;

    if (role === "director") {
      $("#DirectorTabs")?.classList.remove("d-none");
      initDirector(app);
    } else {
      $("#UserKanban")?.classList.remove("d-none");
      initUserKanban(app);
    }
  };

  // ---------------- Director UI ----------------
  function initDirector(app) {
    const weekHeadCells = $$("#WeekGrid thead th.day-head");
    const weekBody = $("#WeekBody");
    const weekRange = $("#WeekRange");
    const userList = $("#UserList");
    const search = $("#UserFilter");
    const trash = $("#TrashZone");

    let start = mondayOf(new Date());
    let data = { users: [], tasks: [], start: fmtISO(start), end: fmtISO(addDays(start, 6)) };
    let trashBound = false;

    const load = async () => {
      const url = `/plan/api/week?start=${fmtISO(start)}&days=7`;
      data = await apiGet(url);

      for (let i = 0; i < 7; i++) {
        const d = addDays(new Date(data.start), i);
        const th = weekHeadCells[i];
        if (!th) continue;
        th.textContent = d.toLocaleDateString(undefined, { weekday:"short", day:"2-digit", month:"short" });
      }
      weekRange.textContent = `${data.start} → ${data.end}`;

      renderUsers();
      renderWeek();
      bindCells();
      bindTrash();
      loadReview();
    };

    function visibleUsers() {
      const q = (search.value || "").toLowerCase();
      if (!q) return data.users;
      return data.users.filter(u => (u.name || "").toLowerCase().includes(q));
    }

    function renderUsers() {
      userList.innerHTML = "";
      visibleUsers().forEach(u => {
        const row = document.createElement("div");
        row.className = "list-group-item d-flex align-items-center";
        row.textContent = u.name;
        userList.appendChild(row);
      });
    }

    function byOwner(tasks) {
      const m = {};
      (tasks || []).forEach(t => { (m[t.owner_user_id] ||= []).push(t); });
      return m;
    }

    function intersects(t, dayDate) {
      const s = new Date(t.start_date + "T00:00:00");
      const e = new Date(t.due_date + "T00:00:00");
      const d = new Date(dayDate.getFullYear(), dayDate.getMonth(), dayDate.getDate());
      return s <= d && d <= e;
    }

    function renderTaskChip(t) {
      const el = document.createElement("div");
      el.className = `task-chip ${prClass(t.priority)} ${stClass(t.status)}`;
      el.draggable = true;
      el.innerHTML = `
        <div class="title">${escapeHtml(t.title)}</div>
        <div class="meta">${escapeHtml(t.status.replaceAll("_", " "))}</div>
      `;
      el.addEventListener("dragstart", (e) => {
        e.dataTransfer.setData("text/plain", JSON.stringify({ id: t.id }));
      });
      el.addEventListener("click", () => openTaskDetail(t.id));
      return el;
    }

    function renderWeek() {
      weekBody.innerHTML = "";
      const grouped = byOwner(data.tasks);

      visibleUsers().forEach(u => {
        const tr = document.createElement("tr");

        const nameTd = document.createElement("td");
        nameTd.textContent = u.name;
        nameTd.style.width = "160px";
        nameTd.style.verticalAlign = "top";
        tr.appendChild(nameTd);

        for (let i = 0; i < 7; i++) {
          const d = addDays(new Date(data.start), i);
          const td = document.createElement("td");
          td.className = "day-cell";
          td.dataset.user = u.id;
          td.dataset.date = fmtISO(d);

          const plus = document.createElement("button");
          plus.type = "button";
          plus.className = "btn btn-sm btn-light cell-plus";
          plus.textContent = "+";
          plus.addEventListener("click", () => openCreate(u.id, fmtISO(d)));
          td.appendChild(plus);

          (grouped[u.id] || []).filter(t => intersects(t, d)).forEach(t => {
            td.appendChild(renderTaskChip(t));
          });

          tr.appendChild(td);
        }

        weekBody.appendChild(tr);
      });
    }

    function bindCells() {
      $$("#WeekBody td.day-cell").forEach(td => {
        td.addEventListener("dragover", e => e.preventDefault());
        td.addEventListener("drop", async (e) => {
          e.preventDefault();
          const payload = JSON.parse(e.dataTransfer.getData("text/plain") || "{}");
          if (!payload.id) return;
          await apiPost(`/plan/api/comment`, {
            task_id: payload.id,
            text: `Rescheduled to ${td.dataset.date} by director`
          });
          await load();
        });
      });
    }

    function bindTrash() {
      if (!trash || trashBound) return;
      trashBound = true;

      const enter = () => trash.classList.add("dragover");
      const leave = () => trash.classList.remove("dragover");

      ["dragenter","dragover"].forEach(ev =>
        trash.addEventListener(ev, (e) => { e.preventDefault(); enter(); })
      );
      ["dragleave","drop"].forEach(ev =>
        trash.addEventListener(ev, (e) => { e.preventDefault(); leave(); })
      );

      trash.addEventListener("drop", async (e) => {
        const payload = JSON.parse(e.dataTransfer.getData("text/plain") || "{}");
        if (!payload.id) return;
        if (!confirm("Да се избрише задачата?")) return;
        await apiPost(`/plan/api/task/${payload.id}/delete`, {});
        await load();
      });
    }

    async function loadReview() {
      const res = await apiGet("/plan/api/review");
      const wrap = $("#ReviewList");
      const q = ($("#ReviewSearch")?.value || "").toLowerCase();
      wrap.innerHTML = "";
      (res.items || []).filter(x => {
        if (!q) return true;
        return (x.title.toLowerCase().includes(q) || x.owner_name.toLowerCase().includes(q));
      }).forEach(item => {
        const a = document.createElement("div");
        a.className = "list-group-item d-flex justify-content-between align-items-center";
        a.innerHTML = `
          <div>
            <div class="fw-semibold">${escapeHtml(item.title)}</div>
            <div class="text-muted small">${escapeHtml(item.owner_name)} • Due ${item.due_date}</div>
          </div>
          <div class="d-flex gap-2">
            <button class="btn btn-sm btn-outline-success" data-approve="${item.id}">Одобри</button>
            <button class="btn btn-sm btn-outline-danger" data-deny="${item.id}">Одбиј</button>
            <button class="btn btn-sm btn-outline-secondary" data-open="${item.id}">Отвори</button>
          </div>
        `;
        wrap.appendChild(a);
      });

      wrap.onclick = async (e) => {
        const ap = e.target.closest("[data-approve]"); const dn = e.target.closest("[data-deny]"); const op = e.target.closest("[data-open]");
        if (ap) {
          const id = ap.getAttribute("data-approve");
          await apiPost(`/plan/api/task/${id}/status`, { action: "approve" });
          await loadReview(); await load();
        } else if (dn) {
          const id = dn.getAttribute("data-deny");
          const note = prompt("Причина (задолжително):");
          if (!note) return;
          await apiPost(`/plan/api/task/${id}/status`, { action: "deny", comment: note });
          await loadReview(); await load();
        } else if (op) {
          const id = op.getAttribute("data-open");
          openTaskDetail(id);
        }
      };
    }
    $("#ReviewSearch")?.addEventListener("input", loadReview);

    function openCreate(ownerId, dateISO) {
      const form = $("#TaskForm");
      form.reset();
      $("#TaskOwnerId").value = ownerId;
      form.querySelector("[name='start_date']").value = dateISO;
      form.querySelector("[name='due_date']").value = dateISO;
      bootstrap.Modal.getOrCreateInstance($("#TaskModal")).show();
    }

    $("#TaskForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(e.currentTarget);
      try {
        const res = await apiPostForm("/plan/api/task", fd);
        if (!res || !res.ok) throw new Error(res?.error || "Create failed");
        bootstrap.Modal.getInstance($("#TaskModal")).hide();
        await load();
      } catch (err) {
        console.error("Create task failed:", err);
        alert(err.message || err);
      }
    });

    $("[data-action='prev-week']")?.addEventListener("click", () => { start = addDays(start, -7); load(); });
    $("[data-action='this-week']")?.addEventListener("click", () => { start = mondayOf(new Date()); load(); });
    $("[data-action='next-week']")?.addEventListener("click", () => { start = addDays(start, 7); load(); });
    $("#UserFilter")?.addEventListener("input", () => { renderUsers(); renderWeek(); bindCells(); });

    load();
  }

  // ---------------- User Kanban ----------------
  function initUserKanban(app) {
    const cols = [
      { key: "assigned",     title: "Assigned" },
      { key: "in_progress",  title: "In Progress" },
      { key: "under_review", title: "Under Review", readonly: true },
      { key: "returned",     title: "Returned" },
      { key: "completed",    title: "Completed", readonly: true },
    ];

    const wrap = $("#KanbanCols");
    wrap.innerHTML = "";
    cols.forEach(c => {
      const col = document.createElement("div");
      col.className = "col-12 col-md-6 col-xl";
      col.innerHTML = `
        <div class="card h-100">
          <div class="card-header d-flex justify-content-between align-items-center">
            <span>${c.title}</span>
          </div>
          <div class="card-body" data-col="${c.key}" ${c.readonly ? "data-readonly='1'" : ""} style="min-height: 200px;"></div>
        </div>
      `;
      wrap.appendChild(col);
    });

    async function load() {
      const data = await apiGet("/plan/api/kanban");
      cols.forEach(c => {
        const box = $(`[data-col='${c.key}']`);
        box.innerHTML = "";
        (data[c.key] || []).forEach(t => {
          const card = renderKanbanCard(t);
          if (!c.readonly) {
            card.draggable = true;
            card.addEventListener("dragstart", (e) => {
              e.dataTransfer.setData("text/plain", JSON.stringify({ id: t.id, from: c.key }));
            });
          }
          box.appendChild(card);
        });
      });
      bindDrops();
    }

    function renderKanbanCard(t) {
      const el = document.createElement("div");
      el.className = `card mb-2 ${prClass(t.priority)} ${stClass(t.status)}`;
      el.innerHTML = `
        <div class="card-body p-2" data-open>
          <div class="d-flex justify-content-between">
            <div class="fw-semibold">${escapeHtml(t.title)}</div>
            <div class="small text-muted">${t.priority ? t.priority : ""}</div>
          </div>
          <div class="small text-muted">Due ${t.due_date}</div>
          <div class="small text-muted">${escapeHtml(t.director_name)}</div>
          <div class="small mt-1">${t.attachments_count} 📎 • ${t.comments_count} 💬</div>
        </div>
        <div class="card-footer p-2 d-flex gap-2">
          ${actionButtonsForCard(t)}
        </div>
      `;
      el.querySelector("[data-open]")?.addEventListener("click", () => openTaskDetail(t.id));
      el.querySelectorAll("[data-action]").forEach(btn => {
        btn.addEventListener("click", async () => {
          const action = btn.dataset.action;
          if (action === "start") {
            await apiPost(`/plan/api/task/${t.id}/status`, { action: "start" });
            await load();
          } else if (action === "submit") {
            // open detail so the user can attach files & preview before submitting
            openTaskDetail(t.id);
          } else if (action === "restart") {
            await apiPost(`/plan/api/task/${t.id}/status`, { action: "restart" });
            await load();
          }
        });
      });
      return el;
    }

    function actionButtonsForCard(t) {
      if (t.status === "assigned")   return `<button class="btn btn-sm btn-outline-primary" data-action="start">Start</button>`;
      if (t.status === "in_progress") return `<button class="btn btn-sm btn-primary" data-action="submit">Submit for Review</button>`;
      if (t.status === "returned")   return `<button class="btn btn-sm btn-warning" data-action="restart">Restart</button>`;
      return `<span class="small text-muted">—</span>`;
    }

    function inferTransition(fromKey, toKey) {
      if (fromKey === "assigned" && toKey === "in_progress") return { action: "start" };
      if (fromKey === "in_progress" && toKey === "under_review") return { action: "submit" };
      if (fromKey === "returned" && toKey === "in_progress") return { action: "restart" };
      return null;
    }

    function bindDrops() {
      cols.forEach(c => {
        const box = $(`[data-col='${c.key}']`);
        if (!box) return;
        box.addEventListener("dragover", e => {
          if (box.dataset.readonly) return;
          e.preventDefault();
        });
        box.addEventListener("drop", async e => {
          if (box.dataset.readonly) return;
          e.preventDefault();
          const payload = JSON.parse(e.dataTransfer.getData("text/plain") || "{}");
          const target = c.key;
          const trans = inferTransition(payload.from, target);
          if (!trans) return;
          if (trans.action === "submit") {
            // open detail for attachments + inline preview before submit
            openTaskDetail(payload.id);
          } else {
            await apiPost(`/plan/api/task/${payload.id}/status`, { action: trans.action });
            await load();
          }
        });
      });
    }

    load();
  }

  // ---------------- Task Detail Modal ----------------
  async function openTaskDetail(taskId) {
    revokeObjectUrls();

    const task = await apiGet(`/plan/api/task/${taskId}`);

    $("#TDTitle").textContent = task.title || "Задача";
    $("#TDMeta").textContent = `Директор: ${task.director_name} • Извршител: ${task.owner_name} • ${task.start_date} → ${task.due_date}`;

    const st = $("#TDStatus"); st.className = `badge ${stClass(task.status)}`; st.textContent = (task.status || "").replaceAll("_"," ");
    const pr = $("#TDPriority"); pr.className = `badge ${prClass(task.priority)}`; pr.textContent = task.priority ? `Priority: ${task.priority}` : "";

    $("#TDDesc").textContent = task.description || "—";

    const list = $("#TaskAttList");
    const iframe = $("#TaskAttPreview");
    const btnOpen = $("#TaskAttOpen");
    const btnDl   = $("#TaskAttDownload");

    list.innerHTML = "";

    async function setPreviewFromAttachment(att) {
      if (!att) {
        iframe.src = "";
        iframe.srcdoc = "<div style='display:flex;align-items:center;justify-content:center;height:100%;font-size:14px;color:#999'>— Нема датотека за преглед —</div>";
        btnOpen.removeAttribute("href");
        btnDl.removeAttribute("href");
        return;
      }
      const previewUrl = att.inline_url || att.download_url;
      iframe.srcdoc = "";       // ensure iframe uses src, not stale srcdoc
      iframe.src = previewUrl;  // server returns inline stream (PDF/images or converted PDF)
      btnOpen.href = previewUrl;
      btnDl.href = att.download_url || previewUrl;
    }

    // --- Attachments (top list): default action = inline preview ---
    (task.attachments || []).forEach((a, idx) => {
      const li = document.createElement("li");
      li.className = "list-group-item d-flex justify-content-between align-items-center";
      li.dataset.attIdx = String(idx);
      li.innerHTML = `
        <span class="text-truncate" style="max-width:70%">${escapeHtml(a.filename)}</span>
        <span class="d-flex flex-wrap gap-2">
          <button class="btn btn-sm btn-outline-primary" data-inline-preview>Преглед (во рамка)</button>
          <a class="btn btn-sm btn-outline-secondary" href="${a.download_url}">Симни</a>
          <a class="btn btn-sm btn-outline-secondary" href="${a.inline_url}" target="_blank" rel="noopener">Отвори нов таб</a>
        </span>
      `;
      list.appendChild(li);
      if (idx === 0) setPreviewFromAttachment(a);
    });

    // Delegated inline preview handler for the list
    list.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-inline-preview]");
      if (!btn) return;
      e.preventDefault();
      const li = btn.closest("li");
      if (!li) return;
      const idx = Number(li.dataset.attIdx || -1);
      const att = (task.attachments || [])[idx];
      if (att) setPreviewFromAttachment(att);
    });

    if ((task.attachments || []).length === 0) {
      await setPreviewFromAttachment(null);
      const li = document.createElement("li");
      li.className = "list-group-item text-muted";
      li.textContent = "— Нема додадени датотеки —";
      list.appendChild(li);
    }

    const comm = $("#TDComments");
    comm.innerHTML = "";
    (task.comments || []).forEach(c => {
      const row = document.createElement("div");
      row.className = "list-group-item";
      const atts = (c.attachments || []).map(a => `
        <div class="d-flex gap-2 mt-1">
          <button class="btn btn-sm btn-outline-primary" data-comment-inline="${escapeHtml(a.inline_url)}">Преглед (во рамка)</button>
          <a class="btn btn-sm btn-outline-secondary" href="${a.download_url}">Симни</a>
          <a class="btn btn-sm btn-outline-secondary" href="${a.inline_url}" target="_blank" rel="noopener">Отвори нов таб</a>
          <span class="small text-truncate">${escapeHtml(a.filename)}</span>
        </div>
      `).join("");
      row.innerHTML = `
        <div class="d-flex justify-content-between">
          <div><strong>${escapeHtml(c.author_name)}</strong></div>
          <div class="text-muted small">${escapeHtml(c.created_at)}</div>
        </div>
        <div class="mt-1">${escapeHtml(c.text || "")}</div>
        ${atts}
      `;
      comm.appendChild(row);
    });

    // Delegated inline preview for comment attachments as well
    comm.addEventListener("click", (e) => {
      const b = e.target.closest("[data-comment-inline]");
      if (!b) return;
      e.preventDefault();
      const url = b.getAttribute("data-comment-inline");
      if (url) {
        iframe.srcdoc = "";
        iframe.src = url;
        btnOpen.href = url;
        btnDl.href = url;
      }
    });

    const actionsHost = $("#TDUserActions");
    actionsHost.innerHTML = "";

    // ----- User actions with optional attachments & live inline preview -----
    if (task.viewer_role === "user") {
      if (task.status === "assigned") {
        actionsHost.innerHTML = `<button class="btn btn-primary" data-act="start">Start</button>`;
      } else if (task.status === "in_progress") {
        actionsHost.innerHTML = `
          <div class="d-flex flex-column gap-2">
            <div class="d-flex flex-wrap gap-2">
              <input id="TDSubmitText" class="form-control" placeholder="Коментар за поднесување..." style="min-width:260px; flex:1;">
              <button class="btn btn-success" data-act="submit">Поднеси на преглед</button>
            </div>
            <div class="border rounded p-2">
              <div class="mb-2 fw-semibold">Прикачи датотеки (опционално)</div>
              <input class="form-control" type="file" id="TDSubmitFiles" multiple>
              <div class="form-text">PDF/Слики ќе се прикажат веднаш во прегледот. Office датотеки ќе се конвертираат во PDF по поднесување.</div>
              <div class="mt-2" id="TDLocalFiles"></div>
            </div>
          </div>`;

        // Bind file input for live previews inside iframe
        const fileInput = $("#TDSubmitFiles");
        const localList = $("#TDLocalFiles");
        const iframeEl  = $("#TaskAttPreview");

        fileInput?.addEventListener("change", () => {
          revokeObjectUrls();
          localList.innerHTML = "";
          const files = Array.from(fileInput.files || []);
          if (files.length === 0) {
            // If no local files selected, keep showing existing attachment preview
            return;
          }

          files.forEach((f, idx) => {
            const row = document.createElement("div");
            row.className = "small d-flex align-items-center justify-content-between border rounded p-2 mb-1";

            let previewAction = "";
            if (isPreviewableLocal(f)) {
              previewAction = `<button class="btn btn-sm btn-outline-primary ms-2" data-local-preview="${idx}">Прикажи во рамка</button>`;
            } else {
              previewAction = `<span class="text-muted ms-2">Преглед по поднесување</span>`;
            }

            row.innerHTML = `
              <div class="text-truncate"><strong>${escapeHtml(f.name)}</strong>
                <span class="text-muted">(${f.type || "unknown"}, ${(f.size/1024|0)} KB)</span>
              </div>
              <div>${previewAction}</div>
            `;
            localList.appendChild(row);
          });

          // Auto-preview the first previewable local file in the iframe
          const first = files.find(isPreviewableLocal);
          if (first) {
            const url = makeObjectUrl(first);
            iframeEl.srcdoc = "";   // ensure src is used
            iframeEl.src = url;
          } else {
            // Show a friendly message inside the iframe for non-previewable office docs before submit
            iframeEl.src = "";
            iframeEl.srcdoc = "<div style='display:flex;align-items:center;justify-content:center;height:100%;font-size:14px;color:#666'>Преглед ќе биде достапен по поднесување</div>";
          }

          // Click to preview any selected previewable file in the iframe
          localList.onclick = (e) => {
            const btn = e.target.closest("[data-local-preview]");
            if (!btn) return;
            const idx = +btn.getAttribute("data-local-preview");
            const f = (fileInput.files || [])[idx];
            if (!f) return;
            if (isPreviewableLocal(f)) {
              const url = makeObjectUrl(f);
              iframeEl.srcdoc = "";
              iframeEl.src = url;
            }
          };
        });
      } else if (task.status === "returned") {
        actionsHost.innerHTML = `<button class="btn btn-warning" data-act="restart">Restart</button>`;
      }
    } else if (task.viewer_role === "director" && task.status === "under_review") {
      actionsHost.innerHTML = `
        <div class="d-flex flex-wrap gap-2">
          <button class="btn btn-outline-success" data-act="approve">Одобри</button>
          <input id="TDDenyText" class="form-control" placeholder="Причина за одбивање..." style="min-width:260px; flex:1;">
          <button class="btn btn-outline-danger" data-act="deny">Одбиј</button>
        </div>`;
    }

    actionsHost.onclick = async (e) => {
      const btn = e.target.closest("[data-act]"); if (!btn) return;
      const act = btn.getAttribute("data-act");

      if (act === "start") {
        await apiPost(`/plan/api/task/${task.id}/status`, { action:"start" });
      } else if (act === "restart") {
        await apiPost(`/plan/api/task/${task.id}/status`, { action:"restart" });
      } else if (act === "approve") {
        await apiPost(`/plan/api/task/${task.id}/status`, { action:"approve" });
      } else if (act === "deny") {
        const txt = $("#TDDenyText")?.value.trim();
        if (!txt) { alert("Причина е задолжителна."); return; }
        await apiPost(`/plan/api/task/${task.id}/status`, { action:"deny", comment: txt });
      } else if (act === "submit") {
        // Submit with optional files via multipart
        const txt = $("#TDSubmitText")?.value.trim();
        if (!txt) { alert("Коментар е задолжителен."); return; }
        const fd = new FormData();
        fd.append("comment", txt);
        const fileInput = $("#TDSubmitFiles");
        if (fileInput && fileInput.files && fileInput.files.length) {
          Array.from(fileInput.files).forEach(f => fd.append("files[]", f, f.name));
        }
        try {
          const res = await apiPostForm(`/plan/api/task/${task.id}/submit`, fd);
          if (!res || !res.ok) throw new Error(res?.error || "Submit failed");
        } catch (err) {
          console.error("Submit failed:", err);
          alert(err.message || err);
          return;
        }
      }

      const app = $("#PlanApp");
      if (app?.dataset.role === "director") {
        $("[data-action='this-week']")?.click();
      } else {
        initUserKanban(app);
      }
      await openTaskDetail(task.id);
    };

    bootstrap.Modal.getOrCreateInstance($("#TaskDetailModal")).show();
  }

  // Auto-mount when visiting /plan/panel directly
  const _auto = () => {
    const el = document.querySelector("#PlanApp");
    if (el && !window.__PLAN_AUTO_MOUNTED__) {
      window.__PLAN_AUTO_MOUNTED__ = true;
      window.mountPlanPanel();
    }
  };
  if (document.readyState === "complete" || document.readyState === "interactive") {
    _auto();
  } else {
    document.addEventListener("DOMContentLoaded", _auto);
  }
})();
