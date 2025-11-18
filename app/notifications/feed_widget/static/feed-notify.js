// Feed Notifications Widget (vanilla JS)
// Mount: <div id="feed-notify-root" data-endpoint="/api/notifications/feed" data-avatar="/static/img/avatar-placeholder.png"></div>
// Optional badge target: <span id="notif-badge"></span> and pass data-badge="#notif-badge"
// Optional onClick hook: window.onFeedNotificationClick = (notif) => {...}  (navigate to your feed/post)

(function(){
  const mount = document.getElementById("feed-notify-root");
  if(!mount) return;

  const API = mount.dataset.endpoint || "/api/notifications/feed";
  const AVATAR = mount.dataset.avatar || "/static/img/avatar-placeholder.png";
  const BADGE_SEL = mount.dataset.badge || null;
  const AUTO_POLL_SEC = Number(mount.dataset.poll || "20"); // poll unread count
  let cursor = null;
  let items = [];
  let loading = false;

  function getCSRF(){
    const m = document.querySelector('meta[name="csrf-token"]');
    if (m?.content) return m.content;
    const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : null;
  }
  async function jfetch(url, opt={}){
    const headers = opt.headers || {};
    headers["Content-Type"] = "application/json";
    const t = getCSRF();
    if (t) headers["X-CSRFToken"]=t;
    const r = await fetch(url, {credentials:"same-origin", ...opt, headers});
    return r.json();
  }

  // skeleton
  mount.classList.add("fn-wrap");
  mount.innerHTML = `
    <div class="fn-head">
      <div class="fn-title">🔔 Известувања</div>
      <div class="fn-actions">
        <button class="fn-btn" data-act="mark-all">Означи ги сите прочитани</button>
        <button class="fn-btn" data-act="refresh">Освежи</button>
      </div>
    </div>
    <div class="fn-list" id="fn-list"></div>
    <div class="fn-footer">
      <button class="fn-btn fn-load" data-act="more">Прикажи повеќе</button>
    </div>
  `;
  const list = mount.querySelector("#fn-list");
  const btnMore = mount.querySelector('[data-act="more"]');

  // wiring head actions
  mount.querySelector('[data-act="refresh"]').onclick = () => refresh(true);
  mount.querySelector('[data-act="mark-all"]').onclick = async () => {
    const res = await jfetch(API + "/mark-all-seen", {method:"POST", body: JSON.stringify({})});
    if (res.ok){ items = items.map(n => ({...n, seen_at: new Date().toISOString()})); render(); badge(); }
  };
  btnMore.onclick = () => load();

  // list loader
  async function load(){
    if (loading) return; loading = true;
    const url = new URL(API + "/", window.location.origin);
    if (cursor) url.searchParams.set("after_id", cursor);
    const res = await jfetch(url.toString(), {method:"GET"});
    if(res.ok){
      items = items.concat(res.items || []);
      cursor = res.next_after_id || null;
      render();
      btnMore.style.display = cursor ? "" : "none";
    }
    loading = false;
  }

  async function refresh(reset=false){
    if (reset){ items = []; cursor = null; list.innerHTML=""; }
    await load();
    badge();
  }

  // unread badge counter
  async function badge(){
    if (!BADGE_SEL) return;
    const el = document.querySelector(BADGE_SEL);
    if (!el) return;
    const res = await jfetch(API + "/unread-count", {method:"GET"});
    if(res.ok){
      const c = res.count || 0;
      if (!el.classList.contains("fn-badge")) el.classList.add("fn-badge");
      el.textContent = c > 99 ? "99+" : String(c);
      el.style.display = c ? "" : "none";
    }
  }

  // rendering
  function render(){
    if (!items.length){
      list.innerHTML = `<div class="fn-empty">Немате известувања.</div>`;
      return;
    }
    list.innerHTML = items.map(viewItem).join("");
    // infinite scroll listener
    list.onscroll = () => {
      if (!cursor) return;
      if (list.scrollTop + list.clientHeight >= list.scrollHeight - 20) load();
    };
    // clicks
    list.querySelectorAll(".fn-item").forEach(it => {
      it.onclick = async () => {
        const id = Number(it.dataset.id);
        const n = items.find(x => x.id === id);
        if (!n) return;
        // mark seen (optimistic)
        if (!n.seen_at){
          n.seen_at = new Date().toISOString();
          render();
          jfetch(API + "/mark-seen", {method:"POST", body: JSON.stringify({ids:[n.id]})}).then(()=>badge());
        }
        // hand over to SPA
        if (typeof window.onFeedNotificationClick === "function"){
          window.onFeedNotificationClick(n);
        } else {
          // fallback: navigate to your feed route with post id as query/hash
          window.location.href = `/feed#post=${n.post_id}`;
        }
      };
    });
  }

  function viewItem(n){
    const pill = kindPill(n.kind);
    const snippet = buildSnippet(n);
    const time = new Date(n.created_at).toLocaleString();
    const seenStyle = n.seen_at ? "opacity:.7" : "opacity:1";
    return `
      <div class="fn-item" data-id="${n.id}" style="${seenStyle}">
        <img class="fn-avatar" src="${avatarFor(n)}" alt="">
        <div class="fn-main">
          <div class="fn-kind">${kindLabel(n.kind)} ${pill}</div>
          <div class="fn-snippet">${snippet}</div>
        </div>
        <div class="fn-time">${time}</div>
      </div>
    `;
  }

  function kindLabel(k){
    if (k === "post_created") return "Нова објава";
    if (k === "comment_added") return "Нов коментар";
    if (k === "reacted") return "Реакција";
    return "Активност";
  }
  function kindPill(k){
    if (k === "post_created") return `<span class="fn-pill post">Post</span>`;
    if (k === "comment_added") return `<span class="fn-pill comment">Comment</span>`;
    if (k === "reacted") return `<span class="fn-pill react">React</span>`;
    return `<span class="fn-pill">Feed</span>`;
    }
  function buildSnippet(n){
    if (n.kind === "post_created"){
      return escapeHtml(n.payload?.title || "Објава");
    }
    if (n.kind === "comment_added"){
      return `Коментар на објавата #${n.post_id}`;
    }
    if (n.kind === "reacted"){
      return `Реакција ${escapeHtml(n.payload?.emoji || "👍")} на објавата #${n.post_id}`;
    }
    return `Активност на објавата #${n.post_id}`;
  }
  function avatarFor(n){
    // if you want actor avatars, expose them via payload and read here; using fallback for now
    return AVATAR;
  }
  function escapeHtml(s){
    return s?.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])) || "";
  }

  // boot
  refresh(true);
  if (AUTO_POLL_SEC > 0){
    setInterval(badge, AUTO_POLL_SEC*1000);
  }
})();
