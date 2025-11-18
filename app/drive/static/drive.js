// app/drive/static/drive.js
(function () {
  console.log('[DRIVE] script loaded');

  /** ---------- tiny utils ---------- */
  function alreadyMounted(el) { return el && el.dataset.driveMounted === '1'; }
  function markMounted(el) { if (el) el.dataset.driveMounted = '1'; }
  function csrf() { const m = document.querySelector('meta[name="csrf-token"]'); return m ? m.getAttribute('content') : ''; }
  function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function human(bytes) { const u=['B','KB','MB','GB','TB']; let i=0,v=bytes; while(v>=1024 && i<u.length-1){v/=1024;i++;} return `${v.toFixed((i===0)?0:1)} ${u[i]}`; }
  function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function ext(name){const m=/\.([a-z0-9]+)$/i.exec(name||'');return m?m[1].toLowerCase():'';}

  /** Map common extensions to Bootstrap “default” filetype icons */
  const FILETYPE_ICON = {
    // Office
    'xls':'bi-filetype-xls','xlsx':'bi-filetype-xlsx','csv':'bi-filetype-csv',
    'doc':'bi-filetype-doc','docx':'bi-filetype-docx',
    'ppt':'bi-filetype-ppt','pptx':'bi-filetype-pptx',
    // Docs
    'pdf':'bi-filetype-pdf','txt':'bi-filetype-txt','md':'bi-filetype-md','rtf':'bi-filetype-rtf',
    // Code / archives
    'zip':'bi-file-earmark-zip','rar':'bi-file-earmark-zip','7z':'bi-file-earmark-zip',
    'js':'bi-filetype-js','ts':'bi-filetype-ts','json':'bi-filetype-json','xml':'bi-filetype-xml',
    'html':'bi-filetype-html','css':'bi-filetype-css',
    // Media
    'jpg':'bi-file-earmark-image','jpeg':'bi-file-earmark-image','png':'bi-file-earmark-image','gif':'bi-file-earmark-image','webp':'bi-file-earmark-image','bmp':'bi-file-earmark-image','svg':'bi-file-earmark-image',
    'mp4':'bi-file-earmark-play','mov':'bi-file-earmark-play','avi':'bi-file-earmark-play','mkv':'bi-file-earmark-play','webm':'bi-file-earmark-play',
    'mp3':'bi-file-earmark-music','wav':'bi-file-earmark-music','flac':'bi-file-earmark-music','m4a':'bi-file-earmark-music',
  };
  function iconForFile(name, mimetype) {
    const e = ext(name);
    if (e && FILETYPE_ICON[e]) return FILETYPE_ICON[e];
    if ((mimetype||'').startsWith('image/')) return 'bi-file-earmark-image';
    if ((mimetype||'').startsWith('video/')) return 'bi-file-earmark-play';
    if ((mimetype||'').startsWith('audio/')) return 'bi-file-earmark-music';
    if ((mimetype||'').includes('pdf')) return 'bi-filetype-pdf';
    if ((mimetype||'').includes('zip') || (mimetype||'').includes('compressed')) return 'bi-file-earmark-zip';
    return 'bi-file-earmark';
  }

  /** ---------- css (injected) ---------- */
  (function injectCSS(){
    if (document.getElementById('drive-style')) return;
    const css = `
    .drive-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px}
    .tile{position:relative;border:1px solid rgba(0,0,0,.08);background:#fff;border-radius:14px;padding:12px;
      display:flex;flex-direction:column;align-items:center;gap:8px;min-height:180px;transition:box-shadow .15s,transform .15s,border-color .15s; cursor:pointer;}
    .tile:hover{box-shadow:0 10px 30px rgba(0,0,0,.08);transform:translateY(-2px);border-color:rgba(0,0,0,.16)}
    .tile-icon{width:64px;height:64px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:32px;background:#f8f9fa;color:#6c757d}
    .tile-icon.folder{background:#fff3cd;color:#a37500}
    .tile-thumb{width:100%;height:92px;border-radius:10px;object-fit:cover;background:#f8f9fa}
    .tile-name{width:100%;text-align:center;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .tile-meta{font-size:.8rem;color:#6b7280}
    .tile-actions{margin-top:auto;display:flex;gap:.4rem}
    .tile-actions .btn{pointer-events:auto}
    .badge-shared{position:absolute;top:8px;right:8px}
    /* list */
    .drive-list .list-row{display:flex;align-items:center;justify-content:space-between;padding:.65rem .9rem;border-bottom:1px solid rgba(0,0,0,.06); cursor:pointer;}
    .pill{display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:10px;background:#fff3cd;color:#a37500;font-size:18px}
    /* DnD + modal states */
    .is-drop-target{outline:2px dashed #0d6efd;outline-offset:3px;background:rgba(13,110,253,.06)}
    .is-dragging{opacity:.6}
    `;
    const n = document.createElement('style'); n.id = 'drive-style'; n.textContent = css; document.head.appendChild(n);
  })();

  /** ---------- http helpers ---------- */
  async function getJSON(url) {
    const r = await fetch(url, { credentials: 'same-origin' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }
  async function postJSON(url, body) {
    const r = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify(body || {}),
    });
    if (!r.ok) throw new Error((await r.text().catch(()=>'')) || `HTTP ${r.status}`);
    return r.json().catch(()=> ({}));
  }
  async function postForm(url, formData) {
    const r = await fetch(url, { method: 'POST', credentials: 'same-origin', body: formData });
    if (!r.ok) throw new Error((await r.text().catch(()=>'')) || `HTTP ${r.status}`);
    return r.json().catch(()=> ({}));
  }

  /** ---------- ACL api helpers ---------- */
  async function apiUsers() {
    const r = await fetch('/drive/api/users', { credentials: 'same-origin' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json();
  }
  async function apiAclGet(type, id) {
    const r = await fetch(`/drive/api/acl/${type}/${id}`, { credentials: 'same-origin' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json();
  }
  async function apiAclSet(type, id, grants) {
    const r = await fetch(`/drive/api/acl/${type}/${id}`, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify({ grants })
    });
    if (!r.ok) throw new Error(await r.text()); return r.json();
  }

  /** ---------- DnD helpers ---------- */
  function setDraggable(node, type, id) { if (!node) return; node.setAttribute('draggable','true'); node.dataset.dragType=type; node.dataset.dragId=id; }
  function setDropTarget(node, kind, folderId) { if (!node) return; node.dataset.dropTarget='1'; node.dataset.dropKind=kind; if (folderId!=null) node.dataset.dropFolderId=String(folderId); }
  function putDragPayload(ev, payload){ ev.dataTransfer.setData('application/json', JSON.stringify(payload)); ev.dataTransfer.effectAllowed='move'; }
  function getDragPayload(ev){ try{const raw=ev.dataTransfer.getData('application/json'); return raw?JSON.parse(raw):null;}catch{return null;} }
  function highlight(node,on){ if (!node) return; node.classList.toggle('is-drop-target',!!on); }

  /** ---------- delete modal (type 'delete' to confirm) ---------- */
  let deleteModal, deleteModalEl, deleteInputEl, deleteFormEl, deleteNameSpan, modalResolve, modalSubmitted;
  function ensureDeleteModal() {
    if (deleteModalEl) return;
    const html = `
      <div class="modal fade" id="folderDeleteModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog">
          <form class="modal-content" id="folderDeleteForm">
            <div class="modal-header">
              <h5 class="modal-title">Delete folder</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body">
              <p>Folder <strong>"<span data-fname></span>"</strong> is <strong>not empty</strong>.</p>
              <p class="mb-2">Type <code>delete</code> to confirm:</p>
              <input type="text" class="form-control" id="folderDeleteInput" placeholder="delete" autocomplete="off" />
              <div class="invalid-feedback">Please type <code>delete</code> to continue.</div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
              <button type="submit" class="btn btn-danger">Delete</button>
            </div>
          </form>
        </div>
      </div>`;
    const wrapper = document.createElement('div');
    wrapper.innerHTML = html;
    deleteModalEl = wrapper.firstElementChild;
    document.body.appendChild(deleteModalEl);

    deleteFormEl = deleteModalEl.querySelector('#folderDeleteForm');
    deleteInputEl = deleteModalEl.querySelector('#folderDeleteInput');
    deleteNameSpan = deleteModalEl.querySelector('[data-fname]');

    deleteFormEl.addEventListener('submit', (e) => {
      e.preventDefault();
      const val = (deleteInputEl.value || '').trim().toLowerCase();
      if (val === 'delete') {
        modalSubmitted = true;
        const m = bootstrap.Modal.getInstance(deleteModalEl);
        if (m) m.hide();
      } else {
        deleteInputEl.classList.add('is-invalid');
      }
    });

    deleteModalEl.addEventListener('shown.bs.modal', () => {
      deleteInputEl.value = '';
      deleteInputEl.classList.remove('is-invalid');
      deleteInputEl.focus();
    });
    deleteModalEl.addEventListener('hidden.bs.modal', () => {
      modalResolve && modalResolve(!!modalSubmitted);
      modalResolve = null;
    });

    deleteModal = new bootstrap.Modal(deleteModalEl);
  }
  async function confirmTypeDelete(folderName) {
    ensureDeleteModal();
    modalSubmitted = false;
    deleteNameSpan.textContent = folderName || '';
    deleteModal.show();
    return new Promise((resolve) => { modalResolve = resolve; });
  }

  /** ---------- preview modal ---------- */
  function openPreviewModal(title, url) {
    const frame = document.getElementById('drivePreviewFrame');
    const ttl = document.getElementById('drivePreviewTitle');
    const modalEl = document.getElementById('drivePreviewModal');
    if (!frame || !modalEl) return;

    if (ttl) ttl.textContent = title || 'File Preview';
    frame.src = url || 'about:blank';

    const m = new bootstrap.Modal(modalEl);
    m.show();

    modalEl.addEventListener('hidden.bs.modal', () => {
      try { frame.src = 'about:blank'; } catch (_) {}
    }, { once: true });
  }

  /** ---------- share modal (takes reloadFn!) ---------- */
  let shareState = { targetType:null, targetId:null, targetName:'' };
  async function openShareModal(type, id, name, reloadFn) {
    shareState = { targetType:type, targetId:id, targetName:name || '' };
    const [usersRes, aclRes] = await Promise.all([apiUsers(), apiAclGet(type, id)]);
    const users = usersRes.users || [];
    const grants = new Map((aclRes.grants || []).map(g => [String(g.user_id), g.permission]));
    const list = document.getElementById('shareUsersList');
    const title = document.getElementById('shareTargetName');
    if (title) title.textContent = name || '';

    list.innerHTML = '';
    users.forEach(u => {
      const row = document.createElement('div');
      row.className = 'd-flex align-items-center justify-content-between';

      const left = document.createElement('div');
      left.innerHTML = `<div class="fw-semibold">${escapeHtml(u.name)}</div>
                        <div class="text-muted">${escapeHtml(u.email)}</div>`;

      const right = document.createElement('div');
      right.innerHTML = `
        <select class="form-select form-select-sm" data-user-id="${u.id}" style="min-width: 140px;">
          <option value="">No access</option>
          <option value="read">Read</option>
          <option value="write">Write</option>
          <option value="full">Full</option>
        </select>`;
      row.appendChild(left);
      row.appendChild(right);
      list.appendChild(row);

      const sel = right.querySelector('select');
      const cur = grants.get(String(u.id)) || '';
      sel.value = cur;
    });

    const modalEl = document.getElementById('driveShareModal');
    const m = new bootstrap.Modal(modalEl);
    m.show();

    const saveBtn = document.getElementById('shareSaveBtn');
    saveBtn.onclick = async () => {
      try {
        const selections = Array.from(list.querySelectorAll('select'))
          .map(sel => ({ user_id: Number(sel.dataset.userId), permission: sel.value }))
          .filter(g => g.permission);
        await apiAclSet(shareState.targetType, shareState.targetId, selections);
        m.hide();
        if (typeof reloadFn === 'function') {
          await reloadFn();           // ✅ refresh provided by mount
        }
      } catch (e) {
        alert(e.message || 'Save failed');
      }
    };
  }

  /** ---------- main mount ---------- */
  window.mountDrivePanel = async function (selector) {
    const rootEl = document.querySelector(selector || '#DriveApp');
    if (!rootEl) { console.warn('[DRIVE] mount: root not found:', selector); return; }
    if (alreadyMounted(rootEl)) { console.debug('[DRIVE] already mounted; skip'); return; }
    markMounted(rootEl);
    console.log('[DRIVE] mounted on', rootEl);

    let currentFolderId = null;
    let viewMode = localStorage.getItem('drive.viewMode') || 'grid';

    function setViewMode(mode) {
      viewMode = (mode === 'list') ? 'list' : 'grid';
      localStorage.setItem('drive.viewMode', viewMode);
      const fWrap = rootEl.querySelector('#drive-folders');
      const fiWrap = rootEl.querySelector('#drive-files');
      if (!fWrap || !fiWrap) return;
      if (viewMode === 'grid') { fWrap.className='drive-grid'; fiWrap.className='drive-grid'; }
      else { fWrap.className='drive-list'; fiWrap.className='drive-list'; }
    }

    function ensureHidden(form, name, value) {
      if (!form) return;
      let h = form.querySelector(`input[name="${name}"]`);
      if (!h) { h = document.createElement('input'); h.type = 'hidden'; h.name = name; form.appendChild(h); }
      h.value = value;
    }

    async function load(folderId) {
      const q = folderId ? `?folder_id=${encodeURIComponent(folderId)}` : '';
      const data = await getJSON(`/drive/api/list${q}`);
      currentFolderId = data.current_folder ? data.current_folder.id : null;
      renderBreadcrumbs(data.breadcrumbs);
      renderFolders(data.folders);
      renderFiles(data.files);
      ensureHidden(rootEl.querySelector('#drive-upload-form'), 'folder_id', currentFolderId ?? '');
    }

    function renderBreadcrumbs(crumbs) {
      const bc = rootEl.querySelector('#drive-breadcrumbs');
      if (!bc) return;
      bc.innerHTML = '';
      const rootItem = el('li', 'breadcrumb-item');
      const rootLink = el('a', null, 'Root');
      rootLink.href='#'; rootLink.dataset.action='nav-root';
      setDropTarget(rootLink, 'root', null);
      rootItem.appendChild(rootLink); bc.appendChild(rootItem);
      if (!crumbs || crumbs.length === 0) return;
      crumbs.forEach((c, i) => {
        const li = el('li', 'breadcrumb-item' + (i===crumbs.length-1?' active':''));
        if (i===crumbs.length-1) { li.textContent=c.name; }
        else { const a=el('a',null,c.name); a.href='#'; a.dataset.action='nav-folder'; a.dataset.folderId=c.id; setDropTarget(a,'folder',c.id); li.appendChild(a); }
        bc.appendChild(li);
      });
    }

    /** ---------- FOLDERS ---------- */
    function folderTile(f){
      const card = document.createElement('div');
      card.className = 'tile';
      // Entire tile opens folder
      card.dataset.action = 'open-folder';
      card.dataset.folderId = f.id;

      card.innerHTML = `
        ${f.shared ? '<span class="badge text-bg-warning badge-shared">Shared</span>' : ''}
        <div class="tile-icon folder"><i class="bi bi-folder-fill"></i></div>
        <div class="tile-name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</div>
        <div class="tile-meta">Folder</div>
        <div class="tile-actions">
          <button class="btn btn-sm btn-outline-secondary" type="button"
            data-action="share-target" data-target-type="folder"
            data-target-id="${f.id}" data-target-name="${escapeHtml(f.name)}">
            <i class="bi bi-person-plus me-1"></i>Share
          </button>
          <button class="btn btn-sm btn-outline-danger" type="button"
            data-action="delete-folder" data-folder-id="${f.id}" data-folder-name="${escapeHtml(f.name)}">
            <i class="bi bi-trash me-1"></i>Delete
          </button>
        </div>
      `;
      setDraggable(card,'folder',f.id);
      setDropTarget(card,'folder',f.id);
      return card;
    }

    function renderFolders(folders) {
      const wrap = rootEl.querySelector('#drive-folders'); if (!wrap) return;
      wrap.innerHTML = '';
      if (!folders || folders.length===0) {
        wrap.innerHTML = '<div class="text-muted" style="border:1px dashed rgba(0,0,0,.15);border-radius:12px;padding:.9rem;text-align:center;">No folders</div>';
        return;
      }

      if (viewMode === 'list') {
        wrap.className='drive-list';
        folders.forEach(f=>{
          const row = document.createElement('div');
          row.className='list-row';
          row.dataset.action = 'open-folder';
          row.dataset.folderId = f.id;
          row.innerHTML = `
            <div class="d-flex align-items-center gap-2">
              <span class="pill"><i class="bi bi-folder-fill"></i></span>
              <span>${escapeHtml(f.name)}</span>
              ${f.shared ? '<span class="badge text-bg-warning ms-2">Shared</span>' : ''}
            </div>
            <div class="d-flex align-items-center gap-2">
              <button class="btn btn-sm btn-outline-secondary"
                data-action="share-target" data-target-type="folder"
                data-target-id="${f.id}" data-target-name="${escapeHtml(f.name)}" type="button">
                <i class="bi bi-person-plus me-1"></i>Share
              </button>
              <button class="btn btn-sm btn-outline-danger"
                data-action="delete-folder" data-folder-id="${f.id}" data-folder-name="${escapeHtml(f.name)}" type="button">
                <i class="bi bi-trash me-1"></i>Delete
              </button>
            </div>`;
          setDraggable(row,'folder',f.id);
          setDropTarget(row,'folder',f.id);
          wrap.appendChild(row);
        });
        return;
      }

      wrap.className='drive-grid';
      folders.forEach(f=>wrap.appendChild(folderTile(f)));
    }

    /** ---------- FILES ---------- */
    function fileTile(fi){
      const e = ext(fi.original_name);
      const icon = iconForFile(fi.original_name, fi.mimetype);
      const isImg = /^(jpg|jpeg|png|gif|webp|bmp|svg)$/i.test(e);

      const card = document.createElement('div');
      card.className='tile';
      // Entire tile opens preview
      card.dataset.action = 'open-file';
      card.dataset.fileId = fi.id;
      card.dataset.fileName = fi.original_name;

      card.innerHTML = `${fi.shared ? '<span class="badge text-bg-warning badge-shared">Shared</span>' : ''}`;
      if (isImg) {
        const img = document.createElement('img');
        img.className = 'tile-thumb';
        img.alt = fi.original_name;
        img.loading = 'lazy';
        img.referrerPolicy = 'no-referrer';
        img.src = `/drive/files/${fi.id}/download?disposition=inline`;
        card.appendChild(img);
      } else {
        const ico = document.createElement('div');
        ico.className='tile-icon';
        ico.innerHTML = `<i class="bi ${icon}"></i>`;
        card.appendChild(ico);
      }

      const name = document.createElement('div');
      name.className='tile-name';
      name.title = fi.original_name;
      name.textContent = fi.original_name;
      card.appendChild(name);

      const meta = document.createElement('div');
      meta.className='tile-meta';
      meta.textContent = fi.size ? human(fi.size) : '';
      card.appendChild(meta);

      const actions = document.createElement('div');
      actions.className='tile-actions';
      actions.innerHTML = `
        <button class="btn btn-sm btn-outline-secondary" type="button"
          data-action="share-target" data-target-type="file"
          data-target-id="${fi.id}" data-target-name="${escapeHtml(fi.original_name)}">
          <i class="bi bi-person-plus me-1"></i>Share
        </button>
        <a class="btn btn-sm btn-outline-primary" href="/drive/files/${fi.id}/download" onclick="event.stopPropagation()">
          <i class="bi bi-download me-1"></i>Download
        </a>
        <button class="btn btn-sm btn-outline-danger" type="button" data-action="delete-file" data-file-id="${fi.id}">
          <i class="bi bi-trash me-1"></i>Delete
        </button>
      `;
      card.appendChild(actions);

      setDraggable(card,'file',fi.id);
      return card;
    }

    function renderFiles(files) {
      const wrap = rootEl.querySelector('#drive-files'); if (!wrap) return;
      wrap.innerHTML = '';
      if (!files || files.length===0) {
        wrap.innerHTML = '<div class="text-muted" style="border:1px dashed rgba(0,0,0,.15);border-radius:12px;padding:.9rem;text-align:center;">No files</div>';
        return;
      }

      if (viewMode === 'list') {
        wrap.className='drive-list';
        files.forEach(fi=>{
          const row = document.createElement('div');
          row.className='list-row';
          row.dataset.action = 'open-file';
          row.dataset.fileId = fi.id;
          row.dataset.fileName = fi.original_name;

          row.innerHTML = `
            <div class="d-flex align-items-center gap-2">
              <span class="pill" style="background:#f1f3f5;color:#495057"><i class="bi ${iconForFile(fi.original_name, fi.mimetype)}"></i></span>
              <span>${escapeHtml(fi.original_name)}</span>
              ${fi.shared ? '<span class="badge text-bg-warning ms-2">Shared</span>' : ''}
              <small class="text-muted ms-2">${fi.size ? '('+human(fi.size)+')' : ''}</small>
            </div>
            <div class="d-flex align-items-center gap-2">
              <button class="btn btn-sm btn-outline-secondary"
                data-action="share-target" data-target-type="file"
                data-target-id="${fi.id}" data-target-name="${escapeHtml(fi.original_name)}" type="button">
                <i class="bi bi-person-plus me-1"></i>Share
              </button>
              <a class="btn btn-sm btn-outline-primary" href="/drive/files/${fi.id}/download" onclick="event.stopPropagation()"><i class="bi bi-download me-1"></i>Download</a>
              <button class="btn btn-sm btn-outline-danger" data-action="delete-file" data-file-id="${fi.id}" type="button"><i class="bi bi-trash me-1"></i>Delete</button>
            </div>`;
          setDraggable(row,'file',fi.id);
          wrap.appendChild(row);
        });
        return;
      }

      wrap.className='drive-grid';
      files.forEach(fi=>wrap.appendChild(fileTile(fi)));
    }

    /** ---------- MOVE endpoints (DnD) ---------- */
    async function moveFile(id, targetFolderId) { return postJSON('/drive/api/file/move', { id, target_folder_id: targetFolderId || null }); }
    async function moveFolder(id, targetParentId) {
      if (String(id) === String(targetParentId)) throw new Error('Cannot move a folder into itself.');
      return postJSON('/drive/api/folder/move', { id, target_parent_id: targetParentId || null });
    }

    /** ---------- Folder delete helpers ---------- */
    async function isFolderEmpty(folderId) {
      const data = await getJSON(`/drive/api/list?folder_id=${encodeURIComponent(folderId)}`);
      const subCount = (data.folders ? data.folders.length : 0) + (data.files ? data.files.length : 0);
      return subCount === 0;
    }
    async function handleDeleteFolder(folderId, folderName) {
      try {
        const empty = await isFolderEmpty(folderId);
        if (empty) {
          if (!confirm(`Delete empty folder "${folderName || ''}"?`)) return;
          await postJSON(`/drive/api/folder/${folderId}/delete`, {});
          await load(currentFolderId);
          return;
        }
        const ok = await confirmTypeDelete(folderName || '');
        if (!ok) return;
        await postJSON(`/drive/api/folder/${folderId}/delete`, { force: true });
        await load(currentFolderId);
      } catch (err) {
        console.error('[DRIVE] delete folder failed:', err);
        alert(err.message || 'Delete failed');
      }
    }

    /** ---------- DnD bindings ---------- */
    rootEl.addEventListener('dragstart', (ev) => {
      const src = ev.target.closest('[draggable="true"]'); if (!src) return;
      const type = src.dataset.dragType, id = src.dataset.dragId; if (!type||!id) return;
      putDragPayload(ev, { type, id }); ev.dataTransfer.dropEffect='move'; src.classList.add('is-dragging');
    });
    rootEl.addEventListener('dragend', () => {
      rootEl.querySelectorAll('.is-dragging').forEach(n=>n.classList.remove('is-dragging'));
      rootEl.querySelectorAll('.is-drop-target').forEach(n=>n.classList.remove('is-drop-target'));
    });
    rootEl.addEventListener('dragover', (ev) => {
      const t = ev.target.closest('[data-drop-target="1"]'); if (!t) return;
      ev.preventDefault(); ev.dataTransfer.dropEffect='move';
    });
    rootEl.addEventListener('dragenter', (ev) => {
      const t = ev.target.closest('[data-drop-target="1"]'); if (!t) return;
      highlight(t,true);
    });
    rootEl.addEventListener('dragleave', (ev) => {
      const t = ev.target.closest('[data-drop-target="1"]'); if (!t) return;
      if (!t.contains(ev.relatedTarget)) highlight(t,false);
    });
    rootEl.addEventListener('drop', async (ev) => {
      const t = ev.target.closest('[data-drop-target="1"]'); if (!t) return;
      ev.preventDefault(); highlight(t,false);
      const payload = getDragPayload(ev); if (!payload) return;

      let dest = null;
      if (t.dataset.dropKind === 'folder') dest = t.dataset.dropFolderId || null;
      if (t.dataset.dropKind === 'root') dest = null;

      try {
        if (payload.type==='file') await moveFile(payload.id, dest);
        else if (payload.type==='folder') await moveFolder(payload.id, dest);
        await load(currentFolderId);
      } catch (e) { console.error(e); alert(e.message||'Move failed'); }
    });

    /** ---------- Click actions ---------- */
    rootEl.addEventListener('click', async (e) => {
      const t = e.target.closest('[data-action]'); if (!t) return;
      if (t.dataset.action === 'delete-folder' || t.dataset.action === 'delete-file') e.stopPropagation();
      e.preventDefault();

      const action = t.dataset.action;
      try {
        if (action==='nav-root'){ await load(null); return; }
        if (action==='nav-folder' || action==='open-folder'){ await load(t.dataset.folderId || null); return; }

        if (action==='open-file'){  // click the item to preview
          const id = t.dataset.fileId || t.closest('[data-file-id]')?.dataset.fileId;
          const name = t.dataset.fileName || t.closest('[data-file-name]')?.dataset.fileName || 'File Preview';
          if (!id) return;
          openPreviewModal(name, `/drive/files/${id}/viewer`);
          return;
        }

        if (action==='share-target'){
          const type = t.dataset.targetType;
          const id = Number(t.dataset.targetId);
          const name = t.dataset.targetName || '';
          await openShareModal(type, id, name, () => load(currentFolderId));  // ✅ pass reload
          return;
        }

        if (action==='create-folder'){
          const nameInput = rootEl.querySelector('#drive-new-folder-name');
          const name = (nameInput.value||'').trim(); if (!name){ nameInput.focus(); return; }
          await postJSON('/drive/api/folder/create', { name, parent_id: currentFolderId });
          nameInput.value=''; await load(currentFolderId); return;
        }
        if (action==='delete-folder'){
          const id = t.dataset.folderId;
          const name = t.dataset.folderName || '';
          await handleDeleteFolder(id, name);
          return;
        }
        if (action==='delete-file'){ await postJSON(`/drive/api/file/${t.dataset.fileId}/delete`, {}); await load(currentFolderId); return; }
        if (action==='upload-now'){
          const form = rootEl.querySelector('#drive-upload-form'); if (!form) return;
          const fd = new FormData(form);
          if (!fd.has('csrf_token')) { const c = csrf(); if (c) fd.append('csrf_token', c); }
          if (!fd.has('folder_id')) fd.append('folder_id', currentFolderId ?? '');
          await postForm('/drive/api/file/upload', fd);
          form.reset(); await load(currentFolderId); return;
        }
        if (action==='set-view'){ setViewMode(t.dataset.mode); await load(currentFolderId); return; }
      } catch (err) { console.error(err); alert(err.message || 'Action failed'); }
    });

    // init
    setViewMode(viewMode);
    await load(null).catch(err => { console.error('[DRIVE] initial load failed:', err); alert('Drive failed to load: ' + (err.message || err)); });
  };

  /** ---------- auto-mount on SPA injections ---------- */
  function tryMountNow() {
    const el = document.querySelector('#DriveApp');
    if (el && !alreadyMounted(el) && typeof window.mountDrivePanel === 'function') {
      window.mountDrivePanel('#DriveApp');
    }
  }
  tryMountNow();
  const host = document.getElementById('MainContent') || document.body;
  const obs = new MutationObserver(() => tryMountNow());
  obs.observe(host, { childList: true, subtree: true });
})();
