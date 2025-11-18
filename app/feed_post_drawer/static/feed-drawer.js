// Feed Post Drawer (vanilla JS)
// Mount once in your SPA shell, then open by:
//   window.dispatchEvent(new CustomEvent('open-feed-post', { detail: { postId: 123 }}));
// Uses existing Feed API: /api/feed (list), /api/feed/<id>/comments, /api/feed/<id>/reactions, DELETE /api/feed/<id>

(function(){
  const AVATAR = "/static/img/avatar-placeholder.png";
  const API = "/api/feed"; // matches your feed API prefix

  // inject DOM
  const overlay = document.createElement("div");
  overlay.className = "fd-overlay";
  overlay.innerHTML = `
    <link rel="stylesheet" href="/static/feed-drawer/feed-drawer.css">
    <div class="fd-panel" role="dialog" aria-modal="true" aria-label="Post details">
      <div class="fd-head">
        <img class="fd-avatar" src="${AVATAR}" alt="">
        <div>
          <div class="fd-author">—</div>
          <div class="fd-meta">—</div>
        </div>
        <button class="fd-close" title="Затвори">✖</button>
      </div>
      <div class="fd-body">
        <div class="fd-title"></div>
        <div class="fd-html"></div>
        <div class="fd-attachments"></div>
      </div>
      <div class="fd-actions">
        <div class="btns">
          <button class="fd-chip" data-emoji="👍">👍 Like</button>
          <button class="fd-chip" data-emoji="🔥">🔥 Fire</button>
          <button class="fd-chip" data-emoji="🎉">🎉 Party</button>
        </div>
        <div class="fd-rx"><span class="fd-rx-count">0</span> реакции</div>
        <button class="fd-chip fd-del" data-act="del" style="display:none">🗑️ Избриши</button>
      </div>
      <div class="fd-comments"></div>
      <div class="fd-composer">
        <input class="fd-input" placeholder="Додади коментар…">
        <button class="fd-send">Испрати</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);

  const panel = overlay.querySelector(".fd-panel");
  const headAvatar = overlay.querySelector(".fd-avatar");
  const headAuthor = overlay.querySelector(".fd-author");
  const headMeta = overlay.querySelector(".fd-meta");
  const btnClose = overlay.querySelector(".fd-close");
  const titleEl = overlay.querySelector(".fd-title");
  const htmlEl = overlay.querySelector(".fd-html");
  const attWrap = overlay.querySelector(".fd-attachments");
  const rxCount = overlay.querySelector(".fd-rx-count");
  const rxBtns = overlay.querySelectorAll(".fd-chip[data-emoji]");
  const delBtn = overlay.querySelector('[data-act="del"]');
  const commentsWrap = overlay.querySelector(".fd-comments");
  const input = overlay.querySelector(".fd-input");
  const sendBtn = overlay.querySelector(".fd-send");

  let currentPost = null;

  // helpers
  function getCSRF(){
    const m = document.querySelector('meta[name="csrf-token"]');
    if (m?.content) return m.content;
    const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : null;
  }
  async function jfetch(url, opt={}){
    const headers = opt.headers || {};
    headers["Content-Type"] = "application/json";
    const t = getCSRF(); if (t) headers["X-CSRFToken"] = t;
    const r = await fetch(url, {credentials:"same-origin", ...opt, headers});
    return r.json();
  }

  // open/close
  function open(){ overlay.classList.add("open"); }
  function close(){ overlay.classList.remove("open"); currentPost = null; commentsWrap.innerHTML=""; input.value=""; }
  btnClose.onclick = close;
  overlay.addEventListener("click", (e)=>{ if(e.target === overlay) close(); });
  window.addEventListener("keydown", (e)=>{ if(e.key === "Escape" && overlay.classList.contains("open")) close(); });

  // listen to SPA event
  window.addEventListener("open-feed-post", (ev)=>{
    const postId = ev?.detail?.postId;
    if (!postId) return;
    loadPostById(postId);
  });

  // Strategy: our API lacks GET /api/feed/<id>. We page through /api/feed/ until found.
  async function loadPostById(id){
    let cursor = null;
    currentPost = null;
    while(true){
      const url = new URL(API + "/", window.location.origin);
      if (cursor?.after_created && cursor?.after_id){
        url.searchParams.set("after_created", cursor.after_created);
        url.searchParams.set("after_id", cursor.after_id);
      }
      const res = await jfetch(url.toString(), { method:"GET" });
      if (!res.ok) break;
      const hit = (res.items || []).find(p => p.id === id);
      if (hit){ currentPost = hit; break; }
      if (!res.next) break;
      cursor = res.next;
    }
    if (!currentPost){
      // Fallback: open first page + toast
      alert("Не можам да ја пронајдам објавата. Обидете се повторно.");
      return;
    }
    renderPost(currentPost);
    open();
  }

  function renderPost(p){
    headAvatar.src = p.author?.avatar || AVATAR;
    headAuthor.textContent = p.author?.name || "—";
    headMeta.textContent = new Date(p.created_at).toLocaleString();
    titleEl.textContent = p.title || "";
    titleEl.style.display = p.title ? "" : "none";
    htmlEl.innerHTML = p.html || "";
    attWrap.innerHTML = (p.attachments||[]).map(a=>{
      return `<a class="fd-attach" href="${a.url}" target="_blank">${
        a.preview_url ? `<img src="${a.preview_url}">` : `<span>${escapeHtml(a.name||"file")}</span>`
      }</a>`;
    }).join("");
    rxCount.textContent = p.reactions?.count || 0;
    rxBtns.forEach(b=>{
      const em = b.dataset.emoji;
      if (p.reactions?.you === em) b.classList.add("active"); else b.classList.remove("active");
      b.onclick = () => toggleReaction(p.id, em);
    });
    if (p.can_delete) { delBtn.style.display = ""; delBtn.onclick = () => deletePost(p.id); }
    else { delBtn.style.display = "none"; delBtn.onclick = null; }

    // comments
    commentsWrap.innerHTML = (p.comments||[]).map(c=>commentHTML(c)).join("");
    sendBtn.onclick = () => {
      const v = input.value.trim();
      if (!v) return;
      addComment(p.id, v);
    };
  }

  function commentHTML(c){
    return `<div class="fd-com">
      <img class="avatar" src="${c.author?.avatar || AVATAR}">
      <div class="bubble">
        <div class="meta"><strong>${c.author?.name || "—"}</strong> · ${new Date(c.created_at).toLocaleString()}</div>
        <div>${c.html}</div>
      </div>
    </div>`;
  }

  async function addComment(id, html){
    const res = await jfetch(`${API}/${id}/comments`, { method:"POST", body: JSON.stringify({ html }) });
    if (!res.ok) return;
    currentPost.comments.push(res.comment);
    commentsWrap.insertAdjacentHTML("beforeend", commentHTML(res.comment));
    input.value = "";
  }

  async function toggleReaction(id, emoji){
    const res = await jfetch(`${API}/${id}/reactions`, { method:"POST", body: JSON.stringify({ emoji }) });
    if (!res.ok) return;
    currentPost.reactions.count = res.count;
    currentPost.reactions.you = res.you;
    rxCount.textContent = res.count || 0;
    rxBtns.forEach(b=>{
      b.classList.toggle("active", b.dataset.emoji === res.you);
    });
  }

  async function deletePost(id){
    if (!confirm("Да се избрише објавата?")) return;
    const res = await jfetch(`${API}/${id}`, { method:"DELETE" });
    if (!res.ok) return;
    close();
    // Notify SPA so it can remove the card from list if present
    window.dispatchEvent(new CustomEvent("feed-post-deleted", { detail:{ postId: id }}));
  }

  function escapeHtml(s){
    return s?.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])) || "";
  }
})();
