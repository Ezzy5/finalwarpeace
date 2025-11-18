// open-comments-modal.js — orchestrates the whole modal
// IMPORTANT: this is an ES module. Load it with <script type="module"> or dynamic import().

import { injectCommentsCSS }     from "./styles.js";
import { openLightbox }          from "./lightbox.js";
import { ensureCommentsModal }   from "./modal-shell.js";
import { el, esc, btnBusy, toast } from "./dom.js";
import { apiGet, apiPost, apiPatch, apiDelete, apiUpload } from "./net.js";
import { buildCommentTree }      from "./tree.js";
import { extractAttachments }    from "./parse.js";
import { buildCommentHTMLFromParts } from "./build-html.js";

function addThumb(container, src, { uploading=false, onRemove } = {}) {
  const t = el(`
    <div class="comp-thumb" ${uploading ? 'data-uploading="1"':''}>
      <img src="${esc(src)}" alt="">
      <div class="comp-x" title="Отстрани"><i class="bi bi-x"></i></div>
    </div>`);
  t.querySelector(".comp-x").onclick = () => { onRemove && onRemove(); t.remove(); };
  container.appendChild(t); return t;
}
function addChip(container, name, { onRemove } = {}) {
  const c = el(`
    <span class="comp-chip">
      <i class="bi bi-file-earmark"></i>
      <span>${esc(name)}</span>
      <span class="chip-x" title="Отстрани"><i class="bi bi-x"></i></span>
    </span>`);
  c.querySelector(".chip-x").onclick = () => { onRemove && onRemove(); c.remove(); };
  container.appendChild(c); return c;
}

export function openCommentsModal({ FEED_API, postId, focus }) {
  injectCommentsCSS();
  ensureCommentsModal();

  const modalEl = document.getElementById("feedCommentsModal");
  if (!modalEl) { toast("Коментарите не се вчитани."); return; }

  const postBox = modalEl.querySelector("#fcm-post");
  const listBox = modalEl.querySelector("#fcm-comments");
  const input   = modalEl.querySelector("#fcm-input");
  const send    = modalEl.querySelector("#fcm-send");

  // root attach state
  const fileInput = modalEl.querySelector("#fcm-file");
  const fileBtn   = modalEl.querySelector("#fcm-file-btn");
  const thumbs    = modalEl.querySelector("#fcm-thumbs");
  const chips     = modalEl.querySelector("#fcm-chips");

  const FEED = (FEED_API || "/api/feed").replace(/\/$/,"");

  let rootUploadPaths = [];
  let rootPending = 0;
  let lastRepliedParentId = null;

  // root uploads
  fileBtn.onclick = () => fileInput.click();
  fileInput.onchange = async () => {
    const files = Array.from(fileInput.files||[]); if (!files.length) return;
    for (const f of files) {
      const isImg = (f.type||"").startsWith("image/");
      if (isImg) {
        const url = URL.createObjectURL(f);
        rootPending++;
        const th = addThumb(thumbs, url, { uploading:true });
        try {
          const res = await apiUpload(`${FEED}/upload`, [f]);
          const it = (res.items||[])[0];
          if (it?.path) {
            rootUploadPaths.push(it.path);
            th.removeAttribute("data-uploading");
            th.querySelector("img").src = it.preview_url || it.file_url || url;
            th.querySelector(".comp-x").onclick = () => {
              rootUploadPaths = rootUploadPaths.filter(p => p !== it.path);
              th.remove();
            };
          } else { th.remove(); toast("Неуспешно прикачување на датотека."); }
        } catch { th.remove(); toast("Неуспешно прикачување на датотека."); }
        finally { rootPending--; URL.revokeObjectURL(url); }
      } else {
        try {
          const res = await apiUpload(`${FEED}/upload`, [f]);
          const it = (res.items||[])[0];
          if (it?.path) {
            rootUploadPaths.push(it.path);
            addChip(chips, it.file_name || f.name, { onRemove:()=> {
              rootUploadPaths = rootUploadPaths.filter(p => p !== it.path);
            }});
          } else { toast("Неуспешно прикачување на датотека."); }
        } catch { toast("Неуспешно прикачување на датотека."); }
      }
    }
    fileInput.value = "";
  };

  // load post header
  postBox.innerHTML = `<div class="text-muted">Вчитување објава...</div>`;
  listBox.innerHTML = `<div class="text-muted">Вчитување коментари...</div>`;
  input.value = ""; rootUploadPaths = []; rootPending = 0; thumbs.innerHTML = ""; chips.innerHTML = "";

  apiGet(`${FEED}/${postId}`).then(p => {
    const imgs = (p.attachments||[]).filter(a => (a.file_type||"").startsWith("image"))
      .map(a => a.preview_url || a.file_url).filter(Boolean);
    postBox.innerHTML = `
      <div class="d-flex align-items-center mb-2">
        <img src="${esc(p.author?.avatar_url || "/static/img/avatar-placeholder.png")}" width="36" height="36" class="rounded-circle border me-2" onerror="this.style.display='none'">
        <div>
          <div class="fw-semibold">${esc(p.author?.full_name || "Корисник")}</div>
          <div class="text-muted small">${/* absolute time only */p.created_at ? (()=> {
            // Inline escape to avoid import overhead here
            const s = String(p.created_at||"").replace(/&/g,"&amp;").replace(/</g,"&lt;")
              .replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
            const d = new Date(p.created_at);
            const abs = new Intl.DateTimeFormat("mk-MK",{dateStyle:"medium",timeStyle:"short",timeZone:"Europe/Skopje"}).format(d);
            const a = abs.replace(/&/g,"&amp;").replace(/</g,"&lt;")
              .replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
            return `<time datetime="${s}" title="${a}">${a}</time>`;
          })() : ""}</div>
        </div>
      </div>
      ${p.title ? `<h5 class="mb-2">${esc(p.title)}</h5>` : ""}
      <div class="feed-html">${p.html || ""}</div>
      ${imgs.length ? `<div class="feed-gallery">${imgs.map((u,i)=>`<div class="feed-photo" data-idx="${i}"><img src="${esc(u)}" alt=""></div>`).join("")}</div>` : ""}`;
    if (imgs.length) {
      postBox.querySelectorAll('.feed-photo').forEach(ph => {
        ph.addEventListener('click', () => openLightbox(imgs, parseInt(ph.dataset.idx,10)||0));
      });
    }
  }).catch(()=> { postBox.innerHTML = `<div class="text-danger">Не може да се вчита објавата.</div>`; });

  // list & render
  const refreshComments = () => {
    apiGet(`${FEED}/${postId}/comments`).then(data => {
      const items = data.items || [];
      if (!items.length) { listBox.innerHTML = `<div class="text-muted">Нема коментари.</div>`; return; }
      listBox.innerHTML = "";
      const tree = buildCommentTree(items);
      tree.roots.forEach(root => {
        const { renderCommentNode } = window.__comments_cache__ || {};
        // lazy import avoids circular import if someone bundles differently
        const render = renderCommentNode
          ? renderCommentNode
          : (awaitImportRenderNode());
        Promise.resolve(render).then(fn => {
          const node = fn(root);
          listBox.appendChild(node);
          const { fillReplies } = window.__comments_cache__ || {};
          const doFill = fillReplies ? fillReplies : (awaitImportFillReplies());
          Promise.resolve(doFill).then(fill => {
            const autoExpand = (lastRepliedParentId && String(lastRepliedParentId) === String(root.id));
            fill(node, root.id, tree, autoExpand);
          });
        });
      });
    }).catch(()=> { listBox.innerHTML = `<div class="text-danger">Не може да се вчитаат коментарите.</div>`; });
  };

  // Small dynamic import helpers to keep main file slim in initial parse
  function awaitImportRenderNode() {
    return import("./render-node.js").then(m => {
      window.__comments_cache__ = { ...(window.__comments_cache__||{}), renderCommentNode: m.renderCommentNode };
      return m.renderCommentNode;
    });
  }
  function awaitImportFillReplies() {
    return import("./fill-replies.js").then(m => {
      window.__comments_cache__ = { ...(window.__comments_cache__||{}), fillReplies: m.fillReplies };
      return m.fillReplies;
    });
  }

  // delegated interactions on comments list
  listBox.addEventListener("click", (e) => {
    // Reply
    const replyBtn = e.target.closest('[data-action="reply"]');
    if (replyBtn) {
      e.preventDefault();
      const commentNode = replyBtn.closest('.fcm-comment');
      if (!commentNode) return;
      const parentId = commentNode.getAttribute('data-comment-id');
      const authorName = commentNode.getAttribute('data-author-name') || "Корисник";

      let wrap = commentNode.querySelector('[data-role="replies"]');
      if (!wrap) {
        wrap = el(`<div class="fcm-replies mt-2" data-role="replies"></div>`);
        replyBtn.parentElement.after(wrap);
      }
      const toggleBtn = commentNode.querySelector('[data-action="toggle-replies"]');
      if (toggleBtn && wrap.classList.contains("collapsed")) {
        wrap.classList.remove("collapsed");
        const chev = toggleBtn.querySelector('[data-role="chev"]'); if (chev) chev.className = 'bi bi-chevron-up';
        const lbl  = toggleBtn.querySelector('[data-role="lbl"]');  if (lbl)  lbl.textContent = 'Скриј одговори';
      }
      if (wrap.querySelector(".fcm-inline-reply")) return;

      const box = el(`
        <div class="fcm-inline-reply">
          <textarea class="form-control form-control-sm" rows="2" placeholder="Ваш одговор..."></textarea>
          <div class="fcm-inline-actions">
            <button class="btn btn-primary btn-xxs" data-action="send-reply">Испрати</button>
            <button class="btn btn-light btn-xxs" data-action="cancel-reply">Откажи</button>
          </div>
        </div>`);
      wrap.prepend(box);
      const ta = box.querySelector("textarea");
      ta.value = `@${authorName.trim()} `;
      ta.focus();
      box.dataset.parentId = parentId;
      box.dataset.parentAuthor = authorName;
      return;
    }

    // Toggle replies
    const toggleBtn = e.target.closest('[data-action="toggle-replies"]');
    if (toggleBtn) {
      e.preventDefault();
      const commentNode = toggleBtn.closest('.fcm-comment');
      const repliesWrap = commentNode?.querySelector('[data-role="replies"]');
      const chev = toggleBtn.querySelector('[data-role="chev"]');
      const lbl  = toggleBtn.querySelector('[data-role="lbl"]');
      const curCollapsed = repliesWrap?.classList.contains('collapsed');
      if (repliesWrap) repliesWrap.classList.toggle('collapsed', !curCollapsed);
      if (chev) chev.className = !curCollapsed ? 'bi bi-chevron-down' : 'bi bi-chevron-up';
      if (lbl)  lbl.textContent = !curCollapsed ? 'Прикажи одговори' : 'Скриј одговори';
      return;
    }

    // Edit
    const editLink = e.target.closest('a[data-action="edit"]');
    if (editLink) {
      e.preventDefault();
      const commentNode = editLink.closest('.fcm-comment');
      if (!commentNode || commentNode.querySelector('.fcm-inline-edit')) return;
      const content = commentNode.querySelector('[data-role="content"]');
      const id = commentNode.getAttribute('data-comment-id');
      const currentHTML = content?.innerHTML || "";

      const { images, files } = extractAttachments(currentHTML);
      let keptImages = images.slice(), keptFiles = files.slice(), newUploadPaths = [], pending = 0;

      const box = el(`
        <div class="fcm-inline-edit">
          <textarea class="form-control form-control-sm" rows="3" placeholder="Измени текст..."></textarea>
          <div class="edit-attach-bar">
            <input type="file" multiple class="comp-attach-input" data-role="edit-file">
            <button class="btn btn-outline-secondary btn-xxs comp-attach-btn" data-role="edit-file-btn" type="button">
              <i class="bi bi-paperclip"></i><span>Додај датотека/фото</span>
            </button>
            <div class="d-flex gap-2 flex-wrap mt-2" data-role="thumbs"></div>
            <div class="d-flex gap-2 flex-wrap mt-2" data-role="chips"></div>
          </div>
          <div class="edit-actions">
            <button class="btn btn-primary btn-xxs" data-action="save-edit">Зачувај</button>
            <button class="btn btn-light btn-xxs" data-action="cancel-edit">Откажи</button>
          </div>
        </div>`);
      content.after(box);

      // seed text (strip reply meta, img, file links with paperclip icon)
      const tmp = document.createElement("div");
      tmp.innerHTML = currentHTML;
      tmp.querySelectorAll('span[data-reply-to]').forEach(n=>n.remove());
      tmp.querySelectorAll("img").forEach(n=>n.remove());
      tmp.querySelectorAll("a").forEach(n=>{
        const hasClip = n.querySelector(".bi.bi-paperclip") || n.innerHTML.includes("bi-paperclip");
        if (hasClip) n.remove();
      });
      box.querySelector("textarea").value = (tmp.textContent||"").trim();

      const fileInput = box.querySelector('[data-role="edit-file"]');
      const fileBtn   = box.querySelector('[data-role="edit-file-btn"]');
      const thumbs    = box.querySelector('[data-role="thumbs"]');
      const chips     = box.querySelector('[data-role="chips"]');
      const btnSave   = box.querySelector('[data-action="save-edit"]');
      const btnCancel = box.querySelector('[data-action="cancel-edit"]');

      const renderExisting = () => {
        thumbs.innerHTML = ""; chips.innerHTML = "";
        keptImages.forEach((it, idx) => {
          const t = el(`
            <div class="comp-thumb">
              <img src="${esc(it.url)}" alt="">
              <div class="comp-x" title="Отстрани"><i class="bi bi-x"></i></div>
            </div>`);
          t.querySelector(".comp-x").onclick = () => { keptImages.splice(idx,1); renderExisting(); };
          thumbs.appendChild(t);
        });
        keptFiles.forEach((it, idx) => {
          const c = el(`
            <span class="comp-chip">
              <i class="bi bi-file-earmark"></i>
              <span>${esc(it.name || (it.url.split("/").pop()||"file"))}</span>
              <span class="chip-x" title="Отстрани"><i class="bi bi-x"></i></span>
            </span>`);
          c.querySelector(".chip-x").onclick = () => { keptFiles.splice(idx,1); renderExisting(); };
          chips.appendChild(c);
        });
      };
      renderExisting();

      fileBtn.onclick = () => fileInput.click();
      fileInput.onchange = async () => {
        const files = Array.from(fileInput.files||[]); if (!files.length) return;
        for (const f of files) {
          const isImg = (f.type||"").startsWith("image/");
          if (isImg) {
            const url = URL.createObjectURL(f);
            pending++;
            const t = el(`
              <div class="comp-thumb" data-uploading="1">
                <img src="${esc(url)}" alt="">
                <div class="comp-x" title="Отстрани"><i class="bi bi-x"></i></div>
              </div>`);
            thumbs.appendChild(t);
            try {
              const res = await apiUpload(`${FEED}/upload`, [f]);
              const it = (res.items||[])[0];
              if (it?.path) {
                newUploadPaths.push(it.path);
                t.removeAttribute("data-uploading");
                t.querySelector("img").src = it.preview_url || it.file_url || url;
                t.querySelector(".comp-x").onclick = () => {
                  newUploadPaths = newUploadPaths.filter(p => p !== it.path);
                  t.remove();
                };
              } else { t.remove(); toast("Неуспешно прикачување на датотека."); }
            } catch { t.remove(); toast("Неуспешно прикачување на датотека."); }
            finally { pending--; URL.revokeObjectURL(url); }
          } else {
            try {
              const res = await apiUpload(`${FEED}/upload`, [f]);
              const it = (res.items||[])[0];
              if (it?.path) {
                newUploadPaths.push(it.path);
                const c = el(`
                  <span class="comp-chip">
                    <i class="bi bi-file-earmark"></i>
                    <span>${esc(it.file_name || f.name)}</span>
                    <span class="chip-x" title="Отстрани"><i class="bi bi-x"></i></span>
                  </span>`);
                c.querySelector(".chip-x").onclick = () => {
                  newUploadPaths = newUploadPaths.filter(p => p !== it.path);
                  c.remove();
                };
                chips.appendChild(c);
              } else { toast("Неуспешно прикачување на датотека."); }
            } catch { toast("Неуспешно прикачување на датотека."); }
          }
        }
        fileInput.value = "";
      };

      btnCancel.onclick = () => box.remove();
      btnSave.onclick = async () => {
        if (pending>0) { toast("Почекајте да заврши прикачувањето."); return; }
        const text = (box.querySelector("textarea").value||"").trim();
        const extra = [];
        keptImages.forEach(it => extra.push(`<div class="mt-2"><img src="${esc(it.url)}" alt="" style="max-width:100%;height:auto;border:1px solid #e5e7eb;border-radius:8px;"></div>`));
        keptFiles.forEach(it => { const name = esc(it.name || (it.url.split("/").pop()||"file"));
          extra.push(`<div class="mt-1"><a href="${esc(it.url)}" target="_blank" rel="noopener"><i class="bi bi-paperclip me-1"></i>${name}</a></div>`); });
        const newHtml = buildCommentHTMLFromParts(text, newUploadPaths, extra, null);
        btnBusy(btnSave, true);
        try {
          try { await apiPatch(`${FEED}/${postId}/comments/${id}`, { html:newHtml }); }
          catch { await apiPatch(`${FEED}/comments/${id}`, { html:newHtml }); }
          refreshComments();
        } catch (e) {
          if (e.status===401 || e.status===403) toast("Немате дозвола да уредувате овој коментар.");
          else toast("Неуспешно уредување на коментар.");
        } finally { btnBusy(btnSave, false); }
      };
      return;
    }

    // Delete
    const delLink = e.target.closest('a[data-action="delete"]');
    if (delLink) {
      e.preventDefault();
      const commentNode = delLink.closest('.fcm-comment');
      const id = commentNode?.getAttribute('data-comment-id');
      if (!id || !confirm("Дали сте сигурни?")) return;
      (async () => {
        try { try { await apiDelete(`${FEED}/${postId}/comments/${id}`); } catch { await apiDelete(`${FEED}/comments/${id}`); } refreshComments(); }
        catch (err) {
          if (err.status===401 || err.status===403) toast("Немате дозвола да го избришете овој коментар.");
          else toast("Неуспешно бришење на коментар.");
        }
      })();
      return;
    }
  });

  // Send/cancel inline reply
  listBox.addEventListener("click", (e) => {
    const sendBtn = e.target.closest('[data-action="send-reply"]');
    if (sendBtn) {
      e.preventDefault();
      const box = sendBtn.closest('.fcm-inline-reply');
      if (!box) return;
      const parentId = box.dataset.parentId;
      const authorName = box.dataset.parentAuthor || "Корисник";
      const ta = box.querySelector('textarea');
      const txt = (ta?.value||"").trim();
      if (!txt || !parentId) return;
      btnBusy(sendBtn, true);
      (async () => {
        try {
          const htmlPayload = buildCommentHTMLFromParts(txt, [], [], { id: parentId, authorName });
          await apiPost(`${FEED}/${postId}/comments`, { html: htmlPayload });
          lastRepliedParentId = parentId;
          box.remove();
          refreshComments();
        } catch (e) {
          if (e.status===401 || e.status===403) toast("Немате дозвола за оваа акција.");
          else toast("Неуспешно додавање коментар.");
        } finally { btnBusy(sendBtn, false); }
      })();
      return;
    }
    const cancelBtn = e.target.closest('[data-action="cancel-reply"]');
    if (cancelBtn) {
      e.preventDefault();
      cancelBtn.closest('.fcm-inline-reply')?.remove();
    }
  });

  // Send root
  const buildRootHTML = () => buildCommentHTMLFromParts(input.value, rootUploadPaths, [], null);
  const onSend = async () => {
    if (rootPending>0) { toast("Почекајте да заврши прикачувањето на датотеките."); return; }
    const text = (input.value||"").trim();
    const hasContent = text.length>0 || rootUploadPaths.length>0;
    if (!hasContent) return;
    btnBusy(send, true);
    try {
      const htmlPayload = buildRootHTML();
      await apiPost(`${FEED}/${postId}/comments`, { html: htmlPayload });
      input.value=""; rootUploadPaths=[]; thumbs.innerHTML=""; chips.innerHTML="";
      refreshComments();
    } catch (e) {
      if (e.status===401 || e.status===403) toast("Немате дозвола за коментирање.");
      else toast("Неуспешно додавање коментар.");
    } finally { btnBusy(send, false); }
  };
  send.onclick = onSend;

  // show
  window.bootstrap?.Modal?.getOrCreateInstance(modalEl)?.show?.();
  if (focus==="comments") setTimeout(()=> input.focus(), 250);

  // first render
  refreshComments();
}

// Expose globally for your existing code that calls window.openCommentsModal
if (!window.openCommentsModal) {
  window.openCommentsModal = openCommentsModal;
}
