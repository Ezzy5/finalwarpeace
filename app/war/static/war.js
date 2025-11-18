// app/war/static/war.js
// Exposes window.mountWarPanel(container?) so your panel loader can call it.
// Accepts: DOM node, jQuery object, or selector string. Automatically attaches CSRF header.

(function () {
  // ---- CSRF helpers ----
  function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
  }
  function jsonHeaders() {
    const h = { 'Content-Type': 'application/json' };
    const t = getCsrfToken();
    if (t) h['X-CSRFToken'] = t; // Flask-WTF default header name
    return h;
  }

  // Normalize any input into a DOM Element
  function toEl(anyRoot) {
    if (!anyRoot) return document;
    if (typeof anyRoot === 'object' && anyRoot !== null) {
      if ('querySelector' in anyRoot) return anyRoot;                 // DOM Element or Document
      if ('0' in anyRoot && anyRoot[0] && 'querySelector' in anyRoot[0]) return anyRoot[0]; // jQuery
    }
    if (typeof anyRoot === 'string') {
      const el = document.querySelector(anyRoot);
      return el || document;
    }
    return document;
  }

  // Scoped query helper that tolerates jQuery/document roots
  function $q(sel, root) {
    const base = toEl(root);
    return base.querySelector(sel);
  }

  window.mountWarPanel = function (container) {
    const root = toEl(container) || document.getElementById('war-app') || document;
    const warRoot = root.id === 'war-app' ? root : document.getElementById('war-app');
    if (!warRoot) {
      console.error('mountWarPanel: #war-app not found');
      return;
    }

    // ---- NEW: permissions state ----
    const abilities = { view: false, edit: false, export: false, manage: false };

    // Small helper to render a badge strip with current abilities
    function renderAbilitiesBar() {
      let bar = warRoot.querySelector('#warAbilitiesBar');
      if (!bar) {
        bar = document.createElement('div');
        bar.id = 'warAbilitiesBar';
        bar.className = 'mb-2';
        warRoot.prepend(bar);
      }
      const on = (k) => abilities[k];
      const pill = (name, ok) =>
        `<span class="badge ${ok ? 'bg-success' : 'bg-secondary'} me-1">${name}</span>`;
      bar.innerHTML = `
        <div class="small text-muted mb-1">Ваши дозволи:</div>
        ${pill('Преглед', on('view'))}
        ${pill('Уреди',   on('edit'))}
        ${pill('Експорт', on('export'))}
        ${pill('Админ',   on('manage'))}
      `;
    }

    async function fetchAbilities() {
      try {
        const res = await fetch('/war/api/abilities', { headers: jsonHeaders(), credentials: 'same-origin' });
        if (!res.ok) throw new Error('abilities fetch failed');
        const j = await res.json();
        abilities.view   = !!(j?.war?.view);
        abilities.edit   = !!(j?.war?.edit);
        abilities.export = !!(j?.war?.export);
        abilities.manage = !!(j?.war?.manage);
      } catch (_) {
        // If endpoint fails, default to safest (view only false)
        abilities.view = abilities.edit = abilities.export = abilities.manage = false;
      }
      applyAbilityUI();
    }

    function hide(el) { if (el) el.style.display = 'none'; }
    function show(el, display = 'block') { if (el) el.style.display = display; }

    function applyAbilityUI() {
      // If user cannot even view, block panel content
      if (!abilities.view) {
        warRoot.innerHTML = `
          <div class="alert alert-warning my-3">
            Немате дозвола за пристап до War модулот. Обратете се кај администратор.
          </div>`;
        return;
      }

      renderAbilitiesBar();

      // Manage gates company CRUD
      if (!abilities.manage) {
        hide(addBtn);
        hide(editCompanyBtn);
        hide(deleteCompanyBtn);
      } else {
        show(addBtn, 'inline-block');
        show(editCompanyBtn, 'inline-block');
        show(deleteCompanyBtn, 'inline-block');
      }

      // Export gate
      if (!abilities.export) hide(exportPdfBtn); else show(exportPdfBtn, 'inline-block');

      // Edit gates interactions creation/comments/archiving
      if (!abilities.edit) {
        hide(newInteraction);
      } else {
        show(newInteraction, 'block');
      }

      // Filters and header are visible to viewers
      show(companyHeader, 'flex');
      show(filters, 'block');
    }

    let viewMode = localStorage.getItem('war_view') || 'grid';
    let companies = [];
    let currentCompanyId = null;

    const companiesWrap      = $q('#companiesWrap',      warRoot);
    const searchInput        = $q('#companySearch',      warRoot);
    const addBtn             = $q('#addCompanyBtn',      warRoot);
    const viewGridBtn        = $q('#viewGridBtn',        warRoot);
    const viewListBtn        = $q('#viewListBtn',        warRoot);

    const companyHeader      = $q('#companyHeader',      warRoot);
    const companyName        = $q('#companyName',        warRoot);
    const companyExternalId  = $q('#companyExternalId',  warRoot);
    const editCompanyBtn     = $q('#editCompanyBtn',     warRoot);
    const deleteCompanyBtn   = $q('#deleteCompanyBtn',   warRoot);

    const filters            = $q('#filters',            warRoot);
    const fFrom              = $q('#fFrom',              warRoot);
    const fTo                = $q('#fTo',                warRoot);
    const fKind              = $q('#fKind',              warRoot);
    const fArchived          = $q('#fArchived',          warRoot);
    const applyFiltersBtn    = $q('#applyFiltersBtn',    warRoot);
    const exportPdfBtn       = $q('#exportPdfBtn',       warRoot);

    const newInteraction     = $q('#newInteraction',     warRoot);
    const newKind            = $q('#newKind',            warRoot);
    const newText            = $q('#newText',            warRoot);
    const sendInteractionBtn = $q('#sendInteractionBtn', warRoot);

    const interactionsList   = $q('#interactionsList',   warRoot);

    // Modal (Bootstrap expects element by id in the document)
    const companyModalEl     = document.getElementById('companyModal');
    const companyModal       = new bootstrap.Modal(companyModalEl);
    const companyModalTitle  = document.getElementById('companyModalTitle');
    const cName              = document.getElementById('cName');
    const cExternalId        = document.getElementById('cExternalId');
    const cDepartments       = document.getElementById('cDepartments');
    const saveCompanyBtn     = document.getElementById('saveCompanyBtn');

    function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn.apply(null, a), ms); }; }
    function escapeHtml(s) { if (!s) return ''; return s.replace(/[&<>"]/g, m => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[m])); }

    async function fetchCompanies() {
      const q = (searchInput?.value || '').trim();
      const res = await fetch(`/war/api/companies?search=${encodeURIComponent(q)}`, { headers: jsonHeaders() });
      if (!res.ok) { if (companiesWrap) companiesWrap.innerHTML = '<div class="text-danger">Failed to load companies</div>'; return; }
      companies = await res.json();
      renderCompanies();
    }

    function renderCompanies() {
      if (!companiesWrap) return;
      companiesWrap.innerHTML = '';
      companies.forEach(c => {
        const el = document.createElement('div');
        el.className = viewMode === 'grid' ? 'card p-2' : 'list-group-item list-group-item-action';
        el.style.cursor = 'pointer';
        el.innerHTML = viewMode === 'grid'
          ? (`<div class="d-flex justify-content-between align-items-start">
                <div>
                  <div class="fw-bold">${escapeHtml(c.name)}</div>
                  <div class="text-muted small">ID: ${escapeHtml(c.external_id || '-')}</div>
                  <div class="small">${(c.departments || []).map(d => escapeHtml(d.name)).join(', ')}</div>
                </div>
                <div class="btn-group">
                  ${abilities.manage ? '<button class="btn btn-outline-secondary btn-sm edit-btn" title="Edit"><i class="bi bi-pencil"></i></button>' : ''}
                  ${abilities.manage ? '<button class="btn btn-outline-danger btn-sm delete-btn" title="Delete"><i class="bi bi-trash"></i></button>' : ''}
                </div>
              </div>`)
          : (`<div class="d-flex justify-content-between align-items-center">
                <div>
                  <span class="fw-bold">${escapeHtml(c.name)}</span>
                  <span class="text-muted ms-2">${escapeHtml(c.external_id || '-')}</span>
                  <span class="small text-muted ms-2">${(c.departments || []).map(d => escapeHtml(d.name)).join(', ')}</span>
                </div>
                <div class="btn-group">
                  ${abilities.manage ? '<button class="btn btn-outline-secondary btn-sm edit-btn" title="Edit"><i class="bi bi-pencil"></i></button>' : ''}
                  ${abilities.manage ? '<button class="btn btn-outline-danger btn-sm delete-btn" title="Delete"><i class="bi bi-trash"></i></button>' : ''}
                </div>
              </div>`);

        el.addEventListener('click', (e) => {
          if (e.target.closest('.edit-btn')) return;
          if (e.target.closest('.delete-btn')) return;
          openCompany(c.id);
        });

        if (abilities.manage) {
          el.querySelector('.edit-btn')?.addEventListener('click', () => editCompany(c.id));
          el.querySelector('.delete-btn')?.addEventListener('click', () => deleteCompany(c.id));
        }
        companiesWrap.appendChild(el);
      });
    }

    async function loadDepartments() {
      const res = await fetch(`/war/api/departments`, { headers: jsonHeaders() });
      const deps = await res.json();
      if (!cDepartments) return;
      cDepartments.innerHTML = '';
      deps.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.id; opt.textContent = d.name; cDepartments.appendChild(opt);
      });
    }

    function resetCompanyModal() {
      if (!cName || !cExternalId || !cDepartments) return;
      cName.value = '';
      cExternalId.value = '';
      Array.from(cDepartments.options).forEach(o => o.selected = false);
    }

    addBtn?.addEventListener('click', async () => {
      if (!abilities.manage) return;
      await loadDepartments();
      resetCompanyModal();
      if (companyModalTitle) companyModalTitle.textContent = 'New Company';
      if (saveCompanyBtn) { saveCompanyBtn.dataset.mode = 'create'; saveCompanyBtn.dataset.companyId = ''; }
      companyModal.show();
    });

    saveCompanyBtn?.addEventListener('click', async () => {
      if (!abilities.manage) return;
      const payload = {
        name: (cName?.value || '').trim(),
        external_id: (cExternalId?.value || '').trim(),
        department_ids: cDepartments ? Array.from(cDepartments.selectedOptions).map(o => Number(o.value)) : [],
      };
      if (!payload.name) { alert('Name is required'); return; }

      if (saveCompanyBtn?.dataset.mode === 'create') {
        const res = await fetch('/war/api/company', {
          method: 'POST',
          headers: jsonHeaders(),
          body: JSON.stringify(payload)
        });
        if (res.ok) { companyModal.hide(); fetchCompanies(); }
        else {
          const txt = await res.text();
          try { alert(JSON.parse(txt).error || 'Error'); } catch { alert(txt || 'Error'); }
        }
      } else {
        const id = Number(saveCompanyBtn?.dataset.companyId || 0);
        const res = await fetch(`/war/api/company/${id}`, {
          method: 'PUT',
          headers: jsonHeaders(),
          body: JSON.stringify(payload)
        });
        if (res.ok) { companyModal.hide(); fetchCompanies(); if (currentCompanyId === id) openCompany(id); }
        else {
          const txt = await res.text();
          try { alert(JSON.parse(txt).error || 'Error'); } catch { alert(txt || 'Error'); }
        }
      }
    });

    async function editCompany(id) {
      if (!abilities.manage) return;
      await loadDepartments();
      const res = await fetch(`/war/api/company/${id}`, { headers: jsonHeaders() });
      if (!res.ok) { alert('Not allowed'); return; }
      const c = await res.json();
      if (cName) cName.value = c.name || '';
      if (cExternalId) cExternalId.value = c.external_id || '';
      if (cDepartments) {
        const set = new Set((c.departments || []).map(d => d.id));
        Array.from(cDepartments.options).forEach(o => o.selected = set.has(Number(o.value)));
      }
      if (companyModalTitle) companyModalTitle.textContent = 'Edit Company';
      if (saveCompanyBtn) { saveCompanyBtn.dataset.mode = 'edit'; saveCompanyBtn.dataset.companyId = String(id); }
      companyModal.show();
    }

    async function deleteCompany(id) {
      if (!abilities.manage) return;
      if (!confirm('Delete this company?')) return;
      const res = await fetch(`/war/api/company/${id}`, { method: 'DELETE', headers: jsonHeaders() });
      if (res.ok) { if (currentCompanyId === id) { currentCompanyId = null; clearRight(); } fetchCompanies(); }
      else alert('Failed');
    }

    function clearRight() {
      if (companyHeader) hide(companyHeader);
      if (filters) hide(filters);
      if (newInteraction) hide(newInteraction);
      if (interactionsList) { hide(interactionsList); interactionsList.innerHTML = ''; }
    }

    async function openCompany(id) {
      if (!abilities.view) return;
      const res = await fetch(`/war/api/company/${id}`, { headers: jsonHeaders() });
      if (!res.ok) { alert('No access'); return; }
      const c = await res.json();
      currentCompanyId = id;
      if (companyName) companyName.textContent = c.name || '';
      if (companyExternalId) companyExternalId.textContent = c.external_id || '';
      if (companyHeader) show(companyHeader, 'flex');
      if (filters) show(filters, 'block');
      if (interactionsList) show(interactionsList, 'block');
      if (abilities.edit) show(newInteraction, 'block'); else hide(newInteraction);
      await reloadInteractions();
    }

    editCompanyBtn?.addEventListener('click', () => { if (abilities.manage && currentCompanyId) editCompany(currentCompanyId); });
    deleteCompanyBtn?.addEventListener('click', () => { if (abilities.manage && currentCompanyId) deleteCompany(currentCompanyId); });

    applyFiltersBtn?.addEventListener('click', reloadInteractions);

    exportPdfBtn?.addEventListener('click', async () => {
      if (!abilities.export || !currentCompanyId) return;
      const res = await fetch('/war/export', {
        method: 'POST',
        headers: jsonHeaders(),
        body: JSON.stringify({
          company_id: currentCompanyId,
          from: fFrom?.value || null,
          to: fTo?.value || null,
          kind: fKind?.value || null,
          archived: fArchived?.value || 'active',
        })
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        alert('Export failed: ' + (j.error || ''));
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = 'export.pdf'; a.click(); URL.revokeObjectURL(url);
    });

    async function reloadInteractions() {
      if (!currentCompanyId || !abilities.view) return;
      const params = new URLSearchParams();
      if (fFrom?.value) params.set('from', fFrom.value);
      if (fTo?.value) params.set('to', fTo.value);
      if (fKind?.value) params.set('kind', fKind.value);
      params.set('archived', (fArchived?.value || 'active'));
      const res = await fetch(`/war/api/company/${currentCompanyId}/interactions?${params.toString()}`, { headers: jsonHeaders() });
      if (!res.ok) { if (interactionsList) interactionsList.innerHTML = '<div class="text-danger">Failed to load</div>'; return; }
      const rows = await res.json();
      renderInteractions(rows);
    }

    function renderInteractions(items) {
      if (!interactionsList) return;
      interactionsList.innerHTML = '';
      if (!items.length) { interactionsList.innerHTML = '<div class="text-muted">No entries.</div>'; return; }
      items.forEach((it) => {
        const id = `it-${it.id}`;
        const canArchive = abilities.edit;     // decide archive right under EDIT
        const canComment = abilities.edit;

        const card = document.createElement('div');
        card.className = 'accordion-item';
        card.innerHTML = `
          <h2 class="accordion-header" id="h-${id}">
            <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#c-${id}">
              <div class="d-flex flex-column">
                <div><span class="badge bg-secondary me-2">${it.kind}</span> <strong>${escapeHtml(it.department || '')}</strong> <span class="text-muted">${new Date(it.created_at).toLocaleString()}</span> ${it.archived ? '<span class="badge bg-dark ms-2">Archived</span>' : ''}</div>
                <div class="small text-truncate" style="max-width:70vw;">${escapeHtml(it.text)}</div>
              </div>
            </button>
          </h2>
          <div id="c-${id}" class="accordion-collapse collapse" data-bs-parent="#interactionsList">
            <div class="accordion-body">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <div class="text-muted">user ${it.user_id}</div>
                <div class="btn-group">
                  ${canArchive ? `<button class="btn btn-outline-secondary btn-sm archive-btn">${it.archived ? 'Unarchive' : 'Archive'}</button>` : ''}
                </div>
              </div>
              <div class="mb-2">${escapeHtml(it.text)}</div>
              <div class="border rounded p-2 mb-2">
                <div class="fw-bold mb-1">Comments</div>
                <div class="vstack gap-2 comments"></div>
                ${canComment ? `
                  <div class="input-group mt-2">
                    <input class="form-control comment-input" placeholder="Write a comment...">
                    <button class="btn btn-outline-primary add-comment-btn">Add</button>
                  </div>` : `<div class="text-muted small">Немате дозвола за коментирање.</div>`}
              </div>
            </div>
          </div>`;

        const commentsWrap = card.querySelector('.comments');
        (it.comments || []).forEach(co => {
          const row = document.createElement('div');
          row.className = 'small';
          row.textContent = `${new Date(co.created_at).toLocaleString()} – user ${co.user_id}: ${co.text}`;
          commentsWrap.appendChild(row);
        });

        if (canArchive) {
          card.querySelector('.archive-btn')?.addEventListener('click', async () => {
            const res = await fetch(`/war/api/interaction/${it.id}/archive`, {
              method: 'POST',
              headers: jsonHeaders(),
              body: JSON.stringify({ archived: !it.archived })
            });
            if (res.ok) reloadInteractions();
          });
        }

        if (canComment) {
          card.querySelector('.add-comment-btn')?.addEventListener('click', async () => {
            const input = card.querySelector('.comment-input');
            const txt = (input?.value || '').trim(); if (!txt) return;
            const res = await fetch(`/war/api/interaction/${it.id}/comments`, {
              method: 'POST',
              headers: jsonHeaders(),
              body: JSON.stringify({ text: txt })
            });
            if (res.ok) { if (input) input.value = ''; reloadInteractions(); }
          });
        }

        interactionsList.appendChild(card);
      });
    }

    sendInteractionBtn?.addEventListener('click', async () => {
      if (!abilities.edit || !currentCompanyId) return;
      const payload = { kind: newKind?.value, text: (newText?.value || '').trim() };
      if (!payload.text) { alert('Text required'); return; }
      const res = await fetch(`/war/api/company/${currentCompanyId}/interactions`, {
        method: 'POST',
        headers: jsonHeaders(),
        body: JSON.stringify(payload)
      });
      if (res.ok) { if (newText) newText.value = ''; reloadInteractions(); }
      else {
        const txt = await res.text();
        try { alert(JSON.parse(txt).error || 'Failed'); } catch { alert(txt || 'Failed'); }
      }
    });

    searchInput?.addEventListener('input', debounce(fetchCompanies, 250));
    viewGridBtn?.addEventListener('click', () => { viewMode = 'grid'; localStorage.setItem('war_view', 'grid'); renderCompanies(); });
    viewListBtn?.addEventListener('click', () => { viewMode = 'list'; localStorage.setItem('war_view', 'list'); renderCompanies(); });

    // initial load: first fetch abilities, then apply UI, then fetch data
    (async () => {
      await fetchAbilities();
      if (abilities.view) {
        await fetchCompanies();
      }
    })();
  };
})();
