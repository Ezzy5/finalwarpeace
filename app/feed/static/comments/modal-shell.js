// modal-shell.js — ensure comments modal exists
import { el } from "./dom.js";

export function ensureCommentsModal() {
  if (document.getElementById("feedCommentsModal")) return;
  document.body.appendChild(el(`
<div class="modal fade" id="feedCommentsModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-scrollable modal-lg">
    <div class="modal-content rounded-4">
      <div class="modal-header">
        <h5 class="modal-title">Објава</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Затвори"></button>
      </div>
      <div class="modal-body">
        <div id="fcm-post" class="mb-3"></div>
        <hr>
        <div id="fcm-comments"></div>
        <div class="mt-3">
          <label class="form-label mb-1">Нов коментар</label>
          <textarea class="form-control mb-2" rows="3" id="fcm-input" placeholder="Напиши коментар..."></textarea>

          <div id="fcm-attach" class="mb-2">
            <div class="comp-attach-bar">
              <input type="file" multiple class="comp-attach-input" id="fcm-file">
              <button class="btn btn-outline-secondary btn-sm comp-attach-btn" id="fcm-file-btn" type="button">
                <i class="bi bi-paperclip"></i><span>Додај датотека/фото</span>
              </button>
              <div class="d-flex gap-2 flex-wrap mt-2" id="fcm-thumbs"></div>
              <div class="d-flex gap-2 flex-wrap mt-2" id="fcm-chips"></div>
            </div>
          </div>

          <div class="d-flex align-items-center justify-content-end">
            <button class="btn btn-primary btn-sm" id="fcm-send">Испрати</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>`));
}
