// Feed Search (vanilla JS)
// Mount: <div id="feed-search" data-endpoint="/api/feed/search" data-avatar-fallback="/static/img/avatar-placeholder.png"></div>

(function(){
  const mount = document.getElementById("feed-search");
  if(!mount) return;

  const API = mount.dataset.endpoint || "/api/feed/search";
  const AVATAR = mount.dataset.avatarFallback || "/static/img/avatar-placeholder.png";
  let cursor = null;

  mount.classList.add("fs-wrap");
  mount.innerHTML = `
    <link rel="stylesheet" href="/static/feed-search/feed-search.css">
    <div class="fs-bar">
      <input class="fs-input" id="fs-q" placeholder="Пребарај објави…">
      <button class="fs-btn" id="fs-go">🔎 Барај</button>
    </div>
    <div class="fs-list" id="fs-list"></div>
    <button class="fs-btn fs-more" id="fs-more" style="display:none">Прикажи повеќе</button>
  `;
  const qEl = mount.querySelector("#fs-q");
  const goEl = mount.querySelector("#fs-go");
  const list = mount.querySelector("#fs-list");
  const more = mount.querySelector("#fs-more");

  goEl.onclick = () => search(true);
  qEl.addEventListener("keydown", (e)=>{ if (e.key === "Enter") search(true); });
  more.onclick = () => search();

  async function jfetch(url){ const r = await fetch(url, {credentials:"same-origin"}); return r.json(); }

  async function search(reset=false){
    const q = (qEl.value || "").trim();
    if (!q){ list.innerHTML = ""; more.style.display="none"; return; }

    if (reset){ cursor = null; list.innerHTML = ""; }
    const url = new URL(API + "/", window.location.origin);
    url.searchParams.set("q", q);
    if (cursor?.after_created && cursor?.after_id){
      url.searchParams.set("after_created", cursor.after_created);
      url.searchParams.set("after_id", cursor.after_id);
    }
    const res = await jfetch(url.toString());
    if (!res.ok) return;
    cursor = res.next || null;

    (res.items || []).forEach(p=>{
      const el = document.createElement("div");
      el.className = "fs-item";
      el.innerHTML = `
        <div class="fs-hdr">
          <img class="fs-avatar" src="${p.author?.avatar || AVATAR}">
          <div>
            <div class="fs-title">${escapeHtml(p.title || "—")}</div>
            <div class="fs-meta">${escapeHtml(p.author?.name || "—")} · ${new Date(p.created_at).toLocaleString()}</div>
          </div>
          <button class="fs-btn" style="margin-left:auto" data-open>Отвори</button>
        </div>
        <div class="fs-snippet">${p.snippet || ""}</div>
      `;
      el.querySelector("[data-open]").onclick = () => {
        // open via drawer event
        window.dispatchEvent(new CustomEvent("open-feed-post", { detail: { postId: p.id }}));
      };
      list.appendChild(el);
    });

    more.style.display = cursor ? "" : "none";
  }

  function escapeHtml(s){
    return s?.replace(/[&<>"']/g, m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])) || "";
  }
})();
