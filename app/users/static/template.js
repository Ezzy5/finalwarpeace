(function () {
  "use strict";

  // ---------- utils ----------
  const $  = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const on = (el, ev, fn, opts) => el.addEventListener(ev, fn, opts);

  function csrfToken() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute("content") : (window.CSRF_TOKEN || "");
  }
  async function getJSON(url) {
    const r = await fetch(url, { credentials: "same-origin" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }
  async function postJSON(url, body) {
    const r = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type":"application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify(body || {})
    });
    if (!r.ok) throw new Error(await r.text().catch(()=>`HTTP ${r.status}`));
    return r.json().catch(()=> ({}));
  }
  async function postForm(url, formData) {
    const r = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrfToken() },
      body: formData
    });
    if (!r.ok) throw new Error(await r.text().catch(()=>`HTTP ${r.status}`));
    return r.json().catch(()=> ({}));
  }
  async function putJSON(url, body) {
    const r = await fetch(url, {
      method: "PUT",
      credentials: "same-origin",
      headers: { "Content-Type":"application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify(body || {})
    });
    if (!r.ok) throw new Error(await r.text().catch(()=>`HTTP ${r.status}`));
    return r.json().catch(()=> ({}));
  }
  async function putForm(url, formData) {
    const r = await fetch(url, {
      method: "PUT",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrfToken() },
      body: formData
    });
    if (!r.ok) throw new Error(await r.text().catch(()=>`HTTP ${r.status}`));
    return r.json().catch(()=> ({}));
  }
  async function del(url) {
    const r = await fetch(url, {
      method: "DELETE",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrfToken() },
    });
    if (!r.ok) throw new Error(await r.text().catch(()=>`HTTP ${r.status}`));
    return r.json().catch(()=> ({}));
  }

  function toast(msg, type = "info", timeout = 2200) {
    let host = $("#tpl_toast_host");
    if (!host) {
      host = document.createElement("div");
      host.id = "tpl_toast_host";
      Object.assign(host.style, {
        position: "fixed", zIndex: "1080", top: "1rem", right: "1rem",
        display: "flex", flexDirection: "column", gap: "0.5rem",
      });
      document.body.appendChild(host);
    }
    const card = document.createElement("div");
    Object.assign(card.style, {
      padding: "10px 12px", borderRadius: "10px", boxShadow: "0 8px 24px rgba(0,0,0,.15)",
      color: "#fff", fontSize: "14px", maxWidth: "360px", wordBreak: "break-word",
      opacity: "0", transform: "translateY(-6px)", transition: "all .2s ease",
    });
    card.textContent = String(msg || "");
    card.style.background = ({ info:"#0d6efd", success:"#198754", warning:"#ffc107", error:"#dc3545", danger:"#dc3545" })[type] || "#0d6efd";
    host.appendChild(card);
    requestAnimationFrame(() => { card.style.opacity = "1"; card.style.transform = "translateY(0)"; });
    setTimeout(() => { card.style.opacity = "0"; card.style.transform = "translateY(-6px)"; setTimeout(() => card.remove(), 180); }, timeout);
  }

  // ---------- DOM refs ----------
  const modalSel = "#TemplatesModal";
  const listSel  = "#TemplatesList";
  const emptySel = "#TemplatesEmpty";
  const edSel    = "#TemplateEditor";
  const nameSel  = "#tpl-name";
  const typeSel  = "#tpl-type";
  const descSel  = "#tpl-desc";
  const wysiWrap = "#tpl-wysi-wrap";
  const wysiSel  = "#tpl-wysi";
  const taWrap   = "#tpl-textarea-wrap"; // no longer used visually
  const taSel    = "#tpl-content";
  const docxWrap = "#tpl-docx-wrap";
  const docxFile = "#tpl-docx-file";
  const fontSel  = "#tpl-font";
  const sizeSel  = "#tpl-size";

  let editingId = null;

  function showEditor(data) {
    editingId = data?.id ?? null;
    $(nameSel).value = data?.name || "";
    $(typeSel).value = data?.type || "docx";
    $(descSel).value = data?.description || "";

    // Switch UI
    if ((data?.type || "docx") === "docx") {
      $(docxWrap).style.display = "";
      $(wysiWrap).style.display = "none";
    } else {
      $(docxWrap).style.display = "none";
      $(wysiWrap).style.display = "";
      $(wysiSel).innerHTML = data?.content || "";
    }

    $(edSel).classList.remove("d-none");
  }

  function hideEditor() {
    editingId = null;
    $(nameSel).value = "";
    $(typeSel).value = "docx";
    $(descSel).value = "";
    $(docxFile).value = "";
    $(wysiSel).innerHTML = "";
    $(docxWrap).style.display = "";
    $(wysiWrap).style.display = "none";
    $(edSel).classList.add("d-none");
  }

  function renderList(items) {
    const list = $(listSel), empty = $(emptySel);
    list.innerHTML = "";
    if (!items || !items.length) { empty.classList.remove("d-none"); return; }
    empty.classList.add("d-none");

    items.forEach(t => {
      const row = document.createElement("div");
      row.className = "list-group-item d-flex justify-content-between align-items-start gap-3";
      row.innerHTML = `
        <div>
          <div class="fw-semibold">${escapeHtml(t.name || "")}</div>
          <div class="small text-muted">${(t.type || "docx").toUpperCase()} ${t.description ? "· " + escapeHtml(t.description) : ""}</div>
        </div>
        <div class="btn-group btn-group-sm">
          <button class="btn btn-outline-secondary" data-action="tpl-edit" data-id="${t.id}">Уреди</button>
          <button class="btn btn-outline-danger" data-action="tpl-delete" data-id="${t.id}">Избриши</button>
        </div>`;
      list.appendChild(row);
    });
  }
  function escapeHtml(s){s=String(s==null?"":s);return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");}

  async function loadTemplates() {
    try { renderList((await getJSON("/users/api/agreements/templates")).items || []); }
    catch { renderList([]); }
  }

  // Toggle editor UI when type changes
  on(document, "change", (e) => {
    if (e.target?.id !== "tpl-type") return;
    const t = e.target.value;
    if (t === "docx") {
      $(docxWrap).style.display = "";
      $(wysiWrap).style.display = "none";
    } else {
      $(docxWrap).style.display = "none";
      $(wysiWrap).style.display = "";
    }
  });

  // WYSIWYG commands (simple)
  on(document, "click", (e) => {
    const b = e.target.closest("[data-wysi]");
    if (!b) return;
    const cmd = b.getAttribute("data-wysi");
    const el = $(wysiSel);
    el.focus();
    if (cmd === "bold") document.execCommand("bold");
    if (cmd === "italic") document.execCommand("italic");
    if (cmd === "underline") document.execCommand("underline");
    if (cmd === "left") document.execCommand("justifyLeft");
    if (cmd === "center") document.execCommand("justifyCenter");
    if (cmd === "right") document.execCommand("justifyRight");
    if (cmd === "justify") document.execCommand("justifyFull");
  });
  on(document, "change", (e) => {
    if (e.target?.id === "tpl-font") {
      document.execCommand("fontName", false, e.target.value || "inherit");
    }
    if (e.target?.id === "tpl-size") {
      const size = e.target.value || "";
      // apply to selection by wrapping in span
      document.execCommand("fontSize", false, "4"); // set a placeholder size
      // replace <font size="4"> with span style
      $$("font[size='4']", $(wysiSel)).forEach(n => {
        const s = document.createElement("span");
        s.style.fontSize = size || "";
        s.innerHTML = n.innerHTML;
        n.replaceWith(s);
      });
    }
  });

  // Events inside modal
  on(document, "shown.bs.modal", (ev) => {
    if (ev.target?.id !== "TemplatesModal") return;
    hideEditor();
    loadTemplates().catch(()=>{});
  });

  on(document, "click", async (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const modal = btn.closest("#TemplatesModal");
    if (!modal) return;

    if (btn.matches("[data-action='tpl-open-create']")) {
      e.preventDefault();
      showEditor({ type: "docx" });
      return;
    }

    if (btn.matches("[data-action='tpl-cancel']")) {
      e.preventDefault();
      hideEditor();
      return;
    }

    if (btn.matches("[data-action='tpl-edit']")) {
      e.preventDefault();
      const id = btn.getAttribute("data-id");
      try {
        const data = await getJSON(`/users/api/agreements/templates/${id}`);
        showEditor(data.item || {});
      } catch (err) {
        toast(`Не може да се вчита шаблонот: ${err.message || err}`, "error");
      }
      return;
    }

    if (btn.matches("[data-action='tpl-delete']")) {
      e.preventDefault();
      const id = btn.getAttribute("data-id");
      if (!confirm("Дали сигурно сакате да го избришете овој шаблон?")) return;
      try {
        await del(`/users/api/agreements/templates/${id}`);
        toast("Шаблонот е избришан.", "success");
        await loadTemplates();
      } catch (err) {
        toast(`Неуспешно бришење: ${err.message || err}`, "error");
      }
      return;
    }

    if (btn.matches("[data-action='tpl-save']")) {
      e.preventDefault();
      const name = $(nameSel).value.trim();
      const type = $(typeSel).value || "docx";
      const description = $(descSel).value.trim();

      if (!name) { toast("Внесете име.", "warning"); return; }

      if (type === "docx") {
        const f = $(docxFile).files?.[0] || null;
        if (!editingId && !f) { toast("Изберете DOCX датотека.", "warning"); return; }

        const fd = new FormData();
        fd.append("name", name);
        fd.append("type", "docx");
        fd.append("description", description);
        if (f) fd.append("file", f);

        try {
          if (editingId) await putForm(`/users/api/agreements/templates/${editingId}`, fd);
          else await postForm(`/users/api/agreements/templates`, fd);
          toast("Шаблонот е зачуван.", "success");
          hideEditor();
          await loadTemplates();
        } catch (err) {
          toast(`Грешка: ${err.message || err}`, "error");
        }
        return;
      }

      // HTML template
      const html = $(wysiSel).innerHTML || "";
      if (!html.trim()) { toast("Внесете содржина.", "warning"); return; }
      const payload = { name, type: "html", description, content: html };
      try {
        if (editingId) await putJSON(`/users/api/agreements/templates/${editingId}`, payload);
        else await postJSON(`/users/api/agreements/templates`, payload);
        toast("Шаблонот е зачуван.", "success");
        hideEditor();
        await loadTemplates();
      } catch (err) {
        toast(`Грешка: ${err.message || err}`, "error");
      }
      return;
    }
  });

  // Expose generator for agreements.js
  window.generateAgreementFromTemplate = async function (userId, templateId, startDate, months, filename) {
    const r = await fetch(`/users/api/agreements/${userId}/generate`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify({ template_id: templateId, start_date: startDate, months: Number(months || 0), filename: filename || null })
    });
    if (!r.ok) throw new Error(await r.text().catch(()=>`HTTP ${r.status}`));
    return r.json().catch(()=> ({}));
  };

})();
