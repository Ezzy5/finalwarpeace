// Topbar User Menu + Time Clock + Avatar Uploader
(function () {
  "use strict";
  if (window.__TB_USER_MENU__) return;
  window.__TB_USER_MENU__ = true;

  // ---------- utils ----------
  const fmt = (ms) => {
    ms = Math.max(0, ms|0);
    const s = Math.floor(ms / 1000);
    const hh = Math.floor(s / 3600).toString().padStart(2, "0");
    const mm = Math.floor((s % 3600) / 60).toString().padStart(2, "0");
    const ss = (s % 60).toString().padStart(2, "0");
    return `${hh}:${mm}:${ss}`;
  };
  const dayKey = () => {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth()+1).padStart(2,"0");
    const da = String(d.getDate()).padStart(2,"0");
    return `timeclock:${y}-${m}-${da}`;
  };
  const load = () => { try { return JSON.parse(localStorage.getItem(dayKey()) || "{}"); } catch { return {}; } };
  const save = (st) => localStorage.setItem(dayKey(), JSON.stringify(st || {}));

  const cacheBust = (url) => {
    if (!url) return url;
    try {
      const u = new URL(url, window.location.origin);
      u.searchParams.set("t", Date.now().toString());
      return u.pathname + "?" + u.searchParams.toString();
    } catch {
      return url + (url.includes("?") ? "&" : "?") + "t=" + Date.now();
    }
  };

  const defaultState = { status: "off", workStart: 0, breakStart: 0, workAccum: 0, breakAccum: 0 };
  let tickTimer = null;

  // ---------- DOM scaffold ----------
  function ensureDOM() {
    if (document.getElementById("tbUserMenu")) return;

    const backdrop = document.createElement("div");
    backdrop.id = "tbUserBackdrop";

    const menu = document.createElement("div");
    menu.id = "tbUserMenu";
    menu.setAttribute("role","dialog");
    menu.setAttribute("aria-modal","true");
    menu.innerHTML = `
      <div class="tbuser__head">
        <img id="tbUserAvatarImg" src="" alt="Avatar" title="Смени аватар">
        <div>
          <div class="tbuser__name" id="tbUserFullName">Корисник</div>
          <div class="small text-muted" id="tbUserRole"></div>
        </div>
        <input type="file" id="tbUserAvatarFile" accept="image/*" style="display:none">
      </div>
      <div class="tbuser__body">
        <div class="tbuser__status">Статус: <b id="tbUserStatus">Невклучен</b></div>

        <div class="tbuser__row">
          <div class="tbuser__label">Работно време</div>
          <div class="tbuser__time" id="tbUserWorkTime">00:00:00</div>
        </div>
        <div class="tbuser__row">
          <div class="tbuser__label">Пауза</div>
          <div class="tbuser__time" id="tbUserBreakTime">00:00:00</div>
        </div>

        <div class="tbuser__actions mt-2">
          <button class="btn btn-primary btn-sm" id="tbBtnClockIn"><i class="bi bi-play-circle me-1"></i>Почеток</button>
          <button class="btn btn-outline-secondary btn-sm" id="tbBtnBreak"><i class="bi bi-pause-circle me-1"></i>Пауза</button>
          <button class="btn btn-outline-success btn-sm" id="tbBtnResume"><i class="bi bi-play-fill me-1"></i>Продолжи</button>
          <button class="btn btn-outline-danger btn-sm" id="tbBtnClockOut"><i class="bi bi-stop-circle me-1"></i>Заврши</button>
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);
    document.body.appendChild(menu);

    backdrop.addEventListener("click", hide);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") hide(); }, true);
    positionMenu(); // initial
    window.addEventListener("resize", positionMenu);
    window.addEventListener("scroll", positionMenu, true);
  }

  function positionMenu() {
    const menu = document.getElementById("tbUserMenu");
    const btn = document.getElementById("TopbarAvatarBtn");
    if (!menu || !btn) return;
    const r = btn.getBoundingClientRect();
    menu.style.top = `${(r.bottom + window.scrollY) + 8}px`;
    menu.style.left = `${Math.min(window.scrollX + r.right - menu.offsetWidth, window.scrollX + document.documentElement.clientWidth - menu.offsetWidth - 12)}px`;
    if (menu.offsetWidth === 0) menu.style.right = `12px`;
  }

  function setVisible(on) {
    const menu = document.getElementById("tbUserMenu");
    const backdrop = document.getElementById("tbUserBackdrop");
    if (!menu || !backdrop) return;
    menu.style.display = on ? "block" : "none";
    backdrop.style.display = on ? "block" : "none";
    if (on) positionMenu();
  }

  function hide() { setVisible(false); }
  function toggle() {
    const menu = document.getElementById("tbUserMenu");
    if (!menu) return;
    setVisible(menu.style.display !== "block");
  }

  // ---------- Topbar header sync ----------
  function refreshHeader() {
    const btn = document.getElementById("TopbarAvatarBtn");
    const full = (btn?.dataset?.fullname || "Корисник").trim();
    const avatar = btn?.dataset?.avatar || btn?.querySelector("img")?.src || "/static/img/avatar-placeholder.png";
    const role = btn?.dataset?.role || "";
    const img = document.getElementById("tbUserAvatarImg");
    const nm = document.getElementById("tbUserFullName");
    const rl = document.getElementById("tbUserRole");
    if (img) img.src = avatar;
    if (nm) nm.textContent = full;
    if (rl) rl.textContent = role;

    // expose for other modules (feed SPA reads/uses this too)
    window.CURRENT_USER_AVATAR_URL = avatar;
  }

  // ---------- Time clock ----------
  function setButtonsByStatus(st) {
    const bIn = document.getElementById("tbBtnClockIn");
    const bBr = document.getElementById("tbBtnBreak");
    const bRe = document.getElementById("tbBtnResume");
    const bOut= document.getElementById("tbBtnClockOut");
    if (!bIn) return;

    if (st.status === "off") {
      bIn.disabled = false;  bBr.disabled = true;   bRe.disabled = true;   bOut.disabled = true;
    } else if (st.status === "work") {
      bIn.disabled = true;   bBr.disabled = false;  bRe.disabled = true;   bOut.disabled = false;
    } else if (st.status === "break") {
      bIn.disabled = true;   bBr.disabled = true;   bRe.disabled = false;  bOut.disabled = false;
    }
  }

  function setStatusText(st) {
    const el = document.getElementById("tbUserStatus");
    if (!el) return;
    el.textContent = st.status === "work" ? "На работа"
                  : st.status === "break" ? "Пауза"
                  : "Невклучен";
  }

  function renderTimes(st) {
    const now = Date.now();
    const work = st.workAccum + (st.status === "work" ? (now - (st.workStart||now)) : 0);
    const brk  = st.breakAccum + (st.status === "break" ? (now - (st.breakStart||now)) : 0);
    const w = document.getElementById("tbUserWorkTime");
    const b = document.getElementById("tbUserBreakTime");
    if (w) w.textContent = fmt(work);
    if (b) b.textContent = fmt(brk);
  }

  function tick() { const st = { ...defaultState, ...load() }; renderTimes(st); }
  function startTick() { if (!tickTimer) tickTimer = setInterval(tick, 1000); }
  function stopTick() { if (tickTimer) { clearInterval(tickTimer); tickTimer = null; } }

  // ---------- Avatar upload + broadcast ----------
  function updateAllAvatars(userId, newUrlRaw) {
    const newUrl = cacheBust(newUrlRaw || "");
    // Topbar button
    const topBtn = document.getElementById("TopbarAvatarBtn");
    if (topBtn) {
      topBtn.dataset.avatar = newUrl;
      const img = topBtn.querySelector("img");
      if (img) img.src = newUrl;
    }
    // Menu img
    const menuImg = document.getElementById("tbUserAvatarImg");
    if (menuImg) menuImg.src = newUrl;

    // Update any avatars in the app:
    // - your previous selector: img[data-user-id="..."]
    // - feed SPA cards: img[data-author-id="..."]
    if (userId) {
      try {
        const escaped = CSS && CSS.escape ? CSS.escape(userId) : userId.replace(/"/g, '\\"');
        document.querySelectorAll(`img[data-user-id="${escaped}"], img[data-author-id="${escaped}"]`).forEach(im => { im.src = newUrl; });
      } catch {
        document.querySelectorAll(`img[data-user-id="${userId}"], img[data-author-id="${userId}"]`).forEach(im => { im.src = newUrl; });
      }
    }

    // cache var for other modules
    window.CURRENT_USER_AVATAR_URL = newUrl;

    // Broadcast so feed-spa.js can refresh composer avatar and any other views
    try {
      window.dispatchEvent(new CustomEvent('user:avatar-updated', { detail: { userId, avatarUrl: newUrl }}));
    } catch (_) {}
  }

  async function uploadAvatar(file) {
    if (!file || !file.type?.startsWith("image/")) {
      alert("Одберете валидна слика.");
      return;
    }
    const MAX_MB = 10 * 1024 * 1024; // must match server cap
    if (file.size > MAX_MB) {
      alert("Сликата е преголема (макс 10MB).");
      return;
    }

    const fd = new FormData();
    // IMPORTANT: the key must be "file" to match Flask (request.files.get("file"))
    fd.append("file", file, file.name);

    const res = await fetch("/api/users/me/avatar", {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-Requested-With":"fetch", "X-CSRFToken": window.CSRF_TOKEN || "" },
      body: fd
    });

    if (!res.ok) {
      const t = await res.text().catch(()=> "");
      throw new Error(`Upload failed: ${res.status} ${t}`);
    }

    const data = await res.json();
    const url = data?.avatar_url;
    if (!url) throw new Error("Одговорот не содржи avatar_url.");
    return url;
  }

  function wireAvatarChange() {
    const img = document.getElementById("tbUserAvatarImg");
    const input = document.getElementById("tbUserAvatarFile");
    const btn = document.getElementById("TopbarAvatarBtn");
    const userId = btn?.dataset?.userId || "";

    if (!img || !input) return;

    img.style.cursor = "pointer";
    img.addEventListener("click", () => input.click());

    input.addEventListener("change", async () => {
      const file = input.files && input.files[0];
      if (!file) return;
      const oldSrc = img.src;

      // Optimistic preview
      const tmp = URL.createObjectURL(file);
      img.src = tmp;

      try {
        const urlFromServer = await uploadAvatar(file);
        updateAllAvatars(userId, urlFromServer);
      } catch (err) {
        console.error(err);
        alert("Неуспешно прикачување на аватар.");
        img.src = oldSrc; // revert on failure
      } finally {
        input.value = "";
        setTimeout(() => URL.revokeObjectURL(tmp), 5000);
      }
    });
  }

  // ---------- Time clock actions ----------
  function onClockIn() {
    const st = { ...defaultState, ...load() };
    if (st.status !== "off") return;
    st.status = "work";
    st.workStart = Date.now();
    save(st);
    setButtonsByStatus(st); setStatusText(st); tick(); startTick();
  }
  function onBreak() {
    const st = { ...defaultState, ...load() };
    if (st.status !== "work") return;
    const now = Date.now();
    st.workAccum += Math.max(0, now - (st.workStart||now));
    st.workStart = 0;
    st.status = "break";
    st.breakStart = now;
    save(st);
    setButtonsByStatus(st); setStatusText(st); tick();
  }
  function onResume() {
    const st = { ...defaultState, ...load() };
    if (st.status !== "break") return;
    const now = Date.now();
    st.breakAccum += Math.max(0, now - (st.breakStart||now));
    st.breakStart = 0;
    st.status = "work";
    st.workStart = now;
    save(st);
    setButtonsByStatus(st); setStatusText(st); tick();
  }
  function onClockOut() {
    const st = { ...defaultState, ...load() };
    const now = Date.now();
    if (st.status === "work") {
      st.workAccum += Math.max(0, now - (st.workStart||now));
    } else if (st.status === "break") {
      st.breakAccum += Math.max(0, now - (st.breakStart||now));
    }
    st.status = "off";
    st.workStart = 0;
    st.breakStart = 0;
    save(st);
    setButtonsByStatus(st); setStatusText(st); tick(); stopTick();
  }

  // ---------- Wire all ----------
  function wire() {
    ensureDOM();
    refreshHeader();

    const st = { ...defaultState, ...load() };
    setButtonsByStatus(st);
    setStatusText(st);
    tick();
    if (st.status === "work" || st.status === "break") startTick();

    document.getElementById("tbBtnClockIn")?.addEventListener("click", onClockIn);
    document.getElementById("tbBtnBreak")?.addEventListener("click", onBreak);
    document.getElementById("tbBtnResume")?.addEventListener("click", onResume);
    document.getElementById("tbBtnClockOut")?.addEventListener("click", onClockOut);

    const btn = document.getElementById("TopbarAvatarBtn");
    if (btn) btn.addEventListener("click", (e) => { e.preventDefault(); toggle(); });

    wireAvatarChange();
  }

  // ---------- Public API ----------
  window.TopbarUserClock = {
    show: () => { ensureDOM(); setVisible(true); positionMenu(); },
    hide: () => setVisible(false),
    toggle,
    getState: () => ({ ...defaultState, ...load() }),
    resetToday: () => { save({ ...defaultState }); tick(); stopTick(); }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire, { once: true });
  } else {
    wire();
  }
})();
