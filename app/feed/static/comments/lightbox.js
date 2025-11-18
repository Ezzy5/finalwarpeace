// lightbox.js — minimal gallery lightbox
import { el } from "./dom.js";

function ensureLightbox() {
  if (document.getElementById("feedLightbox")) return;
  document.body.appendChild(el(`
<div class="modal fade feed-lightbox" id="feedLightbox" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered position-relative">
    <div class="modal-content bg-black text-white border-0 rounded-4 overflow-hidden">
      <div class="lightbox-body position-relative d-flex align-items-center justify-content-center">
        <img id="feedLightboxImg" src="" alt="">
        <div class="position-absolute top-50 start-0 translate-middle-y ms-2">
          <button class="btn btn-sm btn-light" id="feedLbPrev" aria-label="Претходна"><i class="bi bi-chevron-left"></i></button>
        </div>
        <div class="position-absolute top-50 end-0 translate-middle-y me-2">
          <button class="btn btn-sm btn-light" id="feedLbNext" aria-label="Следна"><i class="bi bi-chevron-right"></i></button>
        </div>
      </div>
    </div>
  </div>
</div>`));
}

export function openLightbox(urls, startIdx = 0) {
  ensureLightbox();
  const modalEl = document.getElementById("feedLightbox");
  const img = document.getElementById("feedLightboxImg");
  const prev = document.getElementById("feedLbPrev");
  const next = document.getElementById("feedLbNext");
  if (!modalEl || !img || !prev || !next) return;
  let idx = startIdx;
  const set = (i) => { idx = (i + urls.length) % urls.length; img.src = urls[idx]; };
  prev.onclick = () => set(idx - 1);
  next.onclick = () => set(idx + 1);
  set(idx);
  window.bootstrap?.Modal?.getOrCreateInstance(modalEl)?.show?.();
}

// Keep global convenience (optional)
window.openLightbox = openLightbox;
