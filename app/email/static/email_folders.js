// app/email/static/email_folders.js
(function () {
  if (window.__emailFoldersWired) return;
  window.__emailFoldersWired = true;

  const CSRF =
    window.CSRF_TOKEN ||
    document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
    '';

  function getCtx() {
    const host = document.getElementById('EmailPanel') || document;
    const acc = host.querySelector('[data-acc-id]')?.getAttribute('data-acc-id') || '';
    const currentFolder =
      host.querySelector('[data-current-folder]')?.getAttribute('data-current-folder') || 'INBOX';
    const delim = host.querySelector('[data-folder-delim]')?.getAttribute('data-folder-delim') || '/';
    return { acc, currentFolder, delim };
  }

  async function postJSON(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'X-CSRFToken': CSRF
      },
      credentials: 'same-origin',
      body: JSON.stringify(body || {})
    });
    let json = {};
    try { json = await res.json(); } catch (_) {}
    if (!res.ok || json.ok === false) {
      const msg = (json && (json.error || json.message)) || ('HTTP ' + res.status);
      throw new Error(msg);
    }
    return json;
  }

  function getActionButton(e, action) {
    return e.target.closest('[data-action="' + action + '"]');
  }

  async function handleCreateFolder(ev) {
    ev.preventDefault(); ev.stopPropagation(); ev.stopImmediatePropagation();

    const ctx = getCtx();
    const btn = getActionButton(ev, 'new-folder') || getActionButton(ev, 'new-subfolder');
    if (!btn) return;

    const parent = btn.getAttribute('data-parent') || '';
    const question = parent ? ('New subfolder in ' + parent + ' :') : 'New folder name:';
    const baseRaw = prompt(question, '');
    if (baseRaw == null) return;
    const base = (baseRaw || '').trim();
    if (!base) { alert('Folder name cannot be empty.'); return; }

    try {
      // Primary shape expected by server: {acc, name, parent}
      let out;
      try {
        out = await postJSON('/email/mail/folder/create', { acc: ctx.acc, name: base, parent: parent });
      } catch (e1) {
        // Backward-compat fallback if server expects {acc, path}
        const path = parent ? (parent + (ctx.delim || '/') + base) : base;
        out = await postJSON('/email/mail/folder/create', { acc: ctx.acc, path: path });
      }

      const expand = parent || (out.expand || out.full_path || base);
      // Go back to mailbox and expand the branch containing the new folder
      window.location.href =
        '/email/mail?acc=' + encodeURIComponent(ctx.acc) +
        '&expand=' + encodeURIComponent(expand);
    } catch (e) {
      console.error('Create folder failed:', e);
      alert('Create folder failed:\n' + e.message);
    }
  }

  async function handleDeleteFolder(ev) {
    ev.preventDefault(); ev.stopPropagation(); ev.stopImmediatePropagation();

    const ctx = getCtx();
    const btn = getActionButton(ev, 'delete-folder');
    if (!btn) return;

    const path = btn.getAttribute('data-path') || '';
    if (!path) return;

    const warning =
      'This will permanently delete the subfolder:\n' +
      '  ' + path + '\n\n' +
      'All messages inside will be moved to the parent folder.\n' +
      'This action CANNOT be undone.\n\n' +
      'Type DELETE to confirm:';
    const conf = prompt(warning, '');
    if (conf !== 'DELETE') return;

    try {
      const out = await postJSON('/email/mail/folder/delete', { acc: ctx.acc, path });
      const parent = path.includes(ctx.delim) ? path.slice(0, path.lastIndexOf(ctx.delim)) : 'INBOX';
      const next = (ctx.currentFolder === path) ? parent : ctx.currentFolder;
      window.location.href =
        '/email/mail/folder/' + encodeURIComponent(next) +
        '?acc=' + encodeURIComponent(ctx.acc) +
        '&expand=' + encodeURIComponent(parent);
    } catch (e) {
      console.error('Delete folder failed:', e);
      alert('Delete folder failed:\n' + e.message);
    }
  }

  function onClick(e) {
    const createTop = getActionButton(e, 'new-folder');
    if (createTop) return handleCreateFolder(e);

    const createSub = getActionButton(e, 'new-subfolder');
    if (createSub) return handleCreateFolder(e);

    const del = getActionButton(e, 'delete-folder');
    if (del) return handleDeleteFolder(e);
  }

  document.addEventListener('click', onClick, true);
  const tree = document.getElementById('folderTree');
  if (tree) tree.addEventListener('click', onClick, true);
})();
