// render-node.js — single comment renderer
import { el, esc } from "./dom.js";
import { renderTimeHTML } from "./time.js";

export function renderCommentNode(c) {
  const authorName = c.author?.full_name ? esc(c.author.full_name) : "Корисник";
  const node = el(`
    <div class="d-flex mb-3 fcm-comment" data-comment-id="${esc(c.id)}" data-author-name="${authorName}">
      <img src="${esc(c.author?.avatar_url || "/static/img/avatar-placeholder.png")}" width="32" height="32" class="rounded-circle border me-2" onerror="this.style.display='none'">
      <div class="flex-grow-1">
        <div class="d-flex align-items-start gap-2">
          <div class="flex-grow-1">
            <div class="small text-muted mb-1"><span class="fw-semibold">${authorName}</span> • ${renderTimeHTML(c.created_at, esc)}</div>
          </div>
          <div class="dropdown">
            <button class="btn btn-outline-secondary btn-xxs dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">More</button>
            <ul class="dropdown-menu dropdown-menu-end">
              <li><a class="dropdown-item" href="#" data-action="edit">Уреди</a></li>
              <li><a class="dropdown-item text-danger" href="#" data-action="delete">Избриши</a></li>
            </ul>
          </div>
        </div>

        <div class="mt-1" data-role="content">${c._parsedHtml}</div>

        <div class="mt-2 d-flex align-items-center gap-2 flex-wrap">
          <button class="btn btn-outline-secondary btn-xxs" data-action="reply"><i class="bi bi-reply"></i> Одговори</button>
          <button class="btn btn-outline-secondary btn-xxs fcm-toggle" data-action="toggle-replies" style="display:none;">
            <i class="bi bi-chevron-down" data-role="chev"></i>
            <span data-role="lbl">Прикажи одговори</span>
            <span class="badge bg-secondary-subtle text-secondary" data-role="cnt">0</span>
          </button>
        </div>

        <div class="fcm-replies mt-2 collapsed" data-role="replies"></div>
      </div>
    </div>`);

  // Minimal dropdown polyfill when Bootstrap JS is missing
  if (!window.bootstrap?.Dropdown) {
    node.querySelectorAll('.dropdown-toggle').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        const menu = btn.parentElement.querySelector('.dropdown-menu');
        menu?.classList.toggle('show');
        const off = (ev)=>{ if (!btn.parentElement.contains(ev.target)) menu?.classList.remove('show'); };
        setTimeout(()=> document.addEventListener('click', off, { once:true }), 0);
      });
    });
  }
  return node;
}
