// /static/feed/feed-utils.js
export const esc = (s) => String(s ?? "")
  .replace(/&/g, "&amp;").replace(/</g, "&lt;")
  .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
export const fmt = (dt) => { try { return new Date(dt).toLocaleString(); } catch { return String(dt); } };
export const el = (html) => { const t = document.createElement("template"); t.innerHTML = html.trim(); return t.content.firstElementChild; };
export const toast = (msg) => alert(msg); // plug in your toaster if you have one

export const btnBusy = (btn, on) => {
  if (!btn) return;
  btn.disabled = !!on;
  let spinner = btn.querySelector('[data-role="spinner"]');
  const cls = 'spinner-border spinner-border-sm me-1';
  if (on) {
    if (!spinner) {
      spinner = document.createElement('span');
      spinner.setAttribute('data-role', 'spinner');
      spinner.className = cls;
      spinner.setAttribute('role', 'status'); spinner.setAttribute('aria-hidden', 'true');
      btn.prepend(spinner);
    }
  } else if (spinner) { spinner.remove(); }
};

// ---- API helpers
const hdr = () => ({ "X-Requested-With":"fetch", "X-CSRFToken": window.CSRF_TOKEN || "" });

export const apiGet = async (url) => {
  const res = await fetch(url, { credentials: "same-origin", headers: hdr() });
  if (!res.ok) throw new Error(`GET ${url} -> ${res.status}`);
  return res.json();
};
export const apiPost = async (url, body) => {
  const res = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { ...hdr(), "Content-Type":"application/json" },
    body: JSON.stringify(body || {})
  });
  if (!res.ok) {
    const txt = await res.text().catch(()=> "");
    const e = new Error(`POST ${url} -> ${res.status}`); e.status = res.status; e.body = txt; throw e;
  }
  return res.json().catch(()=> ({}));
};
export const apiPatch = async (url, body) => {
  let res = await fetch(url, {
    method: "PATCH",
    credentials: "same-origin",
    headers: { ...hdr(), "Content-Type":"application/json" },
    body: JSON.stringify(body || {})
  });
  if (res.status === 405 || res.status === 404) {
    res = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { ...hdr(), "Content-Type":"application/json", "X-HTTP-Method-Override":"PATCH" },
      body: JSON.stringify(body || {})
    });
  }
  if (!res.ok) {
    const txt = await res.text().catch(()=> "");
    const e = new Error(`PATCH ${url} -> ${res.status}`); e.status = res.status; e.body = txt; throw e;
  }
  return res.json().catch(()=> ({}));
};
export const apiDelete = async (url) => {
  let res = await fetch(url, {
    method: "DELETE",
    credentials: "same-origin",
    headers: hdr()
  });
  if (res.status === 405 || res.status === 404) {
    res = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { ...hdr(), "X-HTTP-Method-Override":"DELETE" }
    });
  }
  if (!res.ok) {
    const txt = await res.text().catch(()=> "");
    const e = new Error(`DELETE ${url} -> ${res.status}`); e.status = res.status; e.body = txt; throw e;
  }
  return res.json().catch(()=> ({}));
};
export const apiUpload = async (uploadUrl, files) => {
  const fd = new FormData();
  files.forEach(f => fd.append("files", f, f.name || "file"));
  const res = await fetch(uploadUrl, { method: "POST", credentials:"same-origin", headers: hdr(), body: fd });
  if (!res.ok) {
    const txt = await res.text().catch(()=> "");
    const e = new Error(`UPLOAD ${uploadUrl} -> ${res.status}`); e.status = res.status; e.body = txt; throw e;
  }
  return res.json();
};

// ---- Lightbox
let _lbInjected = false;
export function ensureLightbox() {
  if (_lbInjected) return;
  document.body.appendChild(el(`
<div class="modal fade feed-lightbox" id="feedLightbox" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered position-relative">
    <div class="modal-content bg-black text-white border-0 rounded-4 overflow-hidden">
      <div class="lightbox-body position-relative">
        <img id="feedLightboxImg" src="" alt="">
        <div class="lightbox-nav position-absolute top-0 bottom-0 start-0 end-0 d-flex align-items-center justify-content-between" style="pointer-events:none">
          <button class="lightbox-btn btn btn-sm" id="feedLbPrev" style="pointer-events:auto"><i class="bi bi-chevron-left"></i></button>
          <button class="lightbox-btn btn btn-sm" id="feedLbNext" style="pointer-events:auto"><i class="bi bi-chevron-right"></i></button>
        </div>
      </div>
    </div>
  </div>
</div>`));
  _lbInjected = true;
}
export function openLightbox(urls, startIdx=0) {
  ensureLightbox();
  const modalEl = document.getElementById("feedLightbox");
  const img = document.getElementById("feedLightboxImg");
  const prev = document.getElementById("feedLbPrev");
  const next = document.getElementById("feedLbNext");
  let idx = startIdx;
  const set = (i) => { idx = (i + urls.length) % urls.length; img.src = urls[idx]; };
  prev.onclick = () => set(idx - 1);
  next.onclick = () => set(idx + 1);
  set(idx);
  window.bootstrap?.Modal?.getOrCreateInstance(modalEl)?.show?.();
}

// ---- UI states
export function setLikeButtonState(btn, reacted) {
  const icon = btn?.querySelector('i');
  if (!btn || !icon) return;
  if (reacted) {
    btn.classList.remove('btn-outline-primary'); btn.classList.add('btn-primary');
    icon.className = 'bi bi-hand-thumbs-up-fill';
    btn.setAttribute('data-reacted', '1');
  } else {
    btn.classList.remove('btn-primary'); btn.classList.add('btn-outline-primary');
    icon.className = 'bi bi-hand-thumbs-up';
    btn.setAttribute('data-reacted', '0');
  }
}
export function setPinButtonState(btn, pinned) {
  const icon = btn?.querySelector('i');
  const label = btn?.querySelector('[data-role="pin-text"]');
  if (!btn || !icon) return;
  if (pinned) {
    btn.classList.remove('btn-outline-secondary'); btn.classList.add('btn-light');
    icon.className = 'bi bi-pin-angle-fill';
    btn.setAttribute('data-pinned', '1');
    if (label) label.textContent = 'Откачи';
    btn.title = 'Откачи';
  } else {
    btn.classList.remove('btn-light'); btn.classList.add('btn-outline-secondary');
    icon.className = 'bi bi-pin-angle';
    btn.setAttribute('data-pinned', '0');
    if (label) label.textContent = 'Закачи';
    btn.title = 'Закачи';
  }
}
export function updatePinStateEverywhere(postId, pinned) {
  document.querySelectorAll(`[data-post-id="${postId}"] [data-action="pin"]`).forEach((btn) => {
    setPinButtonState(btn, pinned);
  });
}
export function removePinnedCardGlobal(id) {
  document.querySelectorAll(`#feed-pins [data-post-id="${id}"]`).forEach(n => n.remove());
  const root = document.getElementById("feed-root");
  if (!root) return;
  const n = root.querySelectorAll('#feed-pins [data-post-id]').length;
  setPinnedCount(n);
  if (n === 0) {
    const wrap = root.querySelector('#feed-pins-wrap');
    if (wrap) wrap.style.display = 'none';
  }
}
export function setPinnedCount(n) {
  const elCount = document.getElementById("feed-pins-count");
  if (!elCount) return;
  elCount.textContent = String(n);
  elCount.classList.remove("pin-count-bump"); void elCount.offsetWidth; elCount.classList.add("pin-count-bump");
}

// feed-utils.js
export function formatDateTime(isoUtcString) {
  if (!isoUtcString) return "";
  try {
    const d = new Date(isoUtcString); // must end with Z from API
    return new Intl.DateTimeFormat('mk-MK', {
      dateStyle: 'medium',
      timeStyle: 'short',
      timeZone: 'Europe/Skopje',
    }).format(d);
  } catch {
    return String(isoUtcString);
  }
}
