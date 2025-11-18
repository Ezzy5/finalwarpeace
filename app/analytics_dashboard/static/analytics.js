// Feed Analytics SPA Widget
// Mount anywhere: <div id="feed-analytics" data-endpoint="/api/feed/analytics" data-days="14"></div>
// Optional: listens to Realtime SSE and refreshes lightweight KPIs.

(function(){
  const mount = document.getElementById("feed-analytics");
  if(!mount) return;

  const API = mount.dataset.endpoint || "/api/feed/analytics";
  const DAYS = Number(mount.dataset.days || "14");
  const AVATAR_FALLBACK = mount.dataset.avatarFallback || "/static/img/avatar-placeholder.png";

  // inject skeleton
  mount.classList.add("ad-wrap");
  mount.innerHTML = `
    <link rel="stylesheet" href="/static/analytics/analytics.css">
    <div class="ad-row cols-3">
      <div class="ad-card" id="ad-kpi-posts">
        <div class="ad-head"><div class="ad-title">Објави</div><div class="ad-sub">последни ${DAYS} дена</div></div>
        <div class="ad-kpi"><div class="num">—</div><div class="delta">—</div></div>
        <div class="ad-foot"><span class="badge-chip">Feed</span><span class="ts">—</span></div>
      </div>
      <div class="ad-card" id="ad-kpi-comments">
        <div class="ad-head"><div class="ad-title">Коментари</div><div class="ad-sub">последни ${DAYS} дена</div></div>
        <div class="ad-kpi"><div class="num">—</div><div class="delta">—</div></div>
        <div class="ad-foot"><span class="badge-chip">Engagement</span><span class="ts">—</span></div>
      </div>
      <div class="ad-card" id="ad-kpi-reactions">
        <div class="ad-head"><div class="ad-title">Реакции</div><div class="ad-sub">последни ${DAYS} дена</div></div>
        <div class="ad-kpi"><div class="num">—</div><div class="delta">—</div></div>
        <div class="ad-foot"><span class="badge-chip">Sentiment</span><span class="ts">—</span></div>
      </div>
    </div>

    <div class="ad-row cols-2">
      <div class="ad-card" id="ad-reactions">
        <div class="ad-head"><div class="ad-title">Emoji реакции</div><div class="ad-sub">распределба</div></div>
        <div class="ad-chart"><canvas id="chart-reactions"></canvas><div id="fb-reactions"></div></div>
      </div>
      <div class="ad-card" id="ad-hours">
        <div class="ad-head"><div class="ad-title">Активни часови</div><div class="ad-sub">кога се коментира најмногу</div></div>
        <div class="ad-chart"><canvas id="chart-hours"></canvas><div id="fb-hours"></div></div>
      </div>
    </div>

    <div class="ad-row">
      <div class="ad-card" id="ad-top">
        <div class="ad-head"><div class="ad-title">Топ автори</div><div class="ad-sub">постови и реакции</div></div>
        <div class="ad-list" id="top-list"></div>
      </div>
    </div>
  `;

  const kpi = {
    posts: byId("ad-kpi-posts"),
    comments: byId("ad-kpi-comments"),
    reactions: byId("ad-kpi-reactions")
  };

  function byId(id){ return mount.querySelector("#"+id); }
  function ts(el, when){ el.querySelector(".ts").textContent = new Date(when).toLocaleString(); }
  function setKPI(card, value, delta){
    card.querySelector(".num").textContent = value;
    const d = card.querySelector(".delta");
    if (delta === null || delta === undefined){ d.textContent = "—"; d.className="delta"; return; }
    const up = delta >= 0;
    d.className = "delta " + (up ? "up":"down");
    d.textContent = (up ? "▲ " : "▼ ") + Math.abs(delta) + "%";
  }

  async function fetchJSON(url){ const r = await fetch(url, {credentials:"same-origin"}); return r.json(); }

  async function loadOverview(){
    const res = await fetchJSON(`${API}/overview?days=${DAYS}`);
    if(!res.ok) return;
    setKPI(kpi.posts, res.stats.posts, null);
    setKPI(kpi.comments, res.stats.comments, null);
    setKPI(kpi.reactions, res.stats.reactions, null);
    ts(kpi.posts, res.since); ts(kpi.comments, res.since); ts(kpi.reactions, res.since);
  }

  function hasChartJS(){ return typeof window.Chart !== "undefined"; }

  function renderFallbackBars(container, pairs, maxW=100){
    container.innerHTML = pairs.map(([label, val, total])=>{
      const w = total ? Math.max(4, Math.round((val/total)*100)) : 0;
      return `<div class="ad-fallbackbar"><div class="label">${label}</div><div class="bar" style="width:${w}%"></div><div>${val}</div></div>`;
    }).join("");
  }

  async function loadReactions(){
    const res = await fetchJSON(`${API}/reactions?days=${DAYS}`);
    if(!res.ok) return;
    const labels = (res.items||[]).map(x=>x.emoji);
    const data = (res.items||[]).map(x=>x.count);
    if (hasChartJS()){
      const ctx = byId("chart-reactions").getContext("2d");
      new Chart(ctx, { type:"doughnut", data:{ labels, datasets:[{ data }] }, options:{ plugins:{legend:{position:"bottom"}} } });
    } else {
      const total = data.reduce((a,b)=>a+b,0);
      renderFallbackBars(byId("fb-reactions"), labels.map((l,i)=>[l, data[i], total]));
    }
  }

  async function loadHours(){
    const res = await fetchJSON(`${API}/active-hours?days=${DAYS}`);
    if(!res.ok) return;
    const labels = [...Array(24)].map((_,i)=>String(i).padStart(2,"0")+":00");
    const map = Object.fromEntries((res.items||[]).map(x=>[x.hour, x.count]));
    const data = labels.map((_,i)=>map[i]||0);
    if (hasChartJS()){
      const ctx = byId("chart-hours").getContext("2d");
      new Chart(ctx, { type:"bar", data:{ labels, datasets:[{ data }] }, options:{ scales:{ x:{ ticks:{ maxRotation:0,minRotation:0 }}, y:{ beginAtZero:true }}, plugins:{legend:{display:false}} } });
    } else {
      const max = Math.max(1, ...data);
      renderFallbackBars(byId("fb-hours"), labels.map((l,i)=>[l, data[i], max]));
    }
  }

  async function loadTop(){
    const res = await fetchJSON(`${API}/top-contributors?days=${DAYS}`);
    if(!res.ok) return;
    const list = byId("top-list");
    list.innerHTML = (res.items||[]).map(u=>{
      return `<div class="ad-item">
        <img src="${u.avatar || AVATAR_FALLBACK}">
        <div class="name">${escapeHtml(u.name)}</div>
        <div class="meta">Постови: ${u.posts} · Реакции: ${u.reactions}</div>
      </div>`;
    }).join("") || `<div class="ad-sub">Нема доволно податоци.</div>`;
  }

  function escapeHtml(s){ return s?.replace(/[&<>"']/g, m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])) || ""; }

  async function init(){
    await Promise.all([loadOverview(), loadReactions(), loadHours(), loadTop()]);
  }

  // Optional live refresh via SSE
  if (window.Realtime){
    window.addEventListener("feed_events", (e)=>{
      const t = e.detail?.type;
      if (t === "post" || t === "comment" || t === "reaction"){
        // light touch — just update KPIs; full refresh is cheap enough for your dataset
        loadOverview();
      }
    });
    window.addEventListener("notif_events", ()=>{/* could refresh badges elsewhere */});
  }

  init();
})();
