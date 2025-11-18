// app/callendar/static/js/ui/dayListModal.js
// A lightweight, Bootstrap-free modal used by "+ Повеќе" to list all items for a day.
// Auto-closes when you click an item and THEN opens the ticket/event.

(function () {
  if (window.DayListModal) return;

  function el(tag, cls, html) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }

  const modal = el('div', 'dlm-backdrop', `
    <div class="dlm-modal" role="dialog" aria-modal="true" aria-labelledby="dlm-title">
      <div class="dlm-header">
        <div class="dlm-title" id="dlm-title"></div>
        <button type="button" class="dlm-close" aria-label="Close">&times;</button>
      </div>
      <div class="dlm-body">
        <ul class="dlm-list"></ul>
      </div>
      <div class="dlm-footer">
        <button type="button" class="dlm-action-close">Затвори</button>
      </div>
    </div>
  `);

  const titleEl = modal.querySelector('.dlm-title');
  const listEl  = modal.querySelector('.dlm-list');
  const closeBtn = modal.querySelector('.dlm-close');
  const closeBtn2 = modal.querySelector('.dlm-action-close');

  let isOpen = false;

  function formatWhen(it) {
    try {
      const s = new Date(it.start_dt), e = new Date(it.end_dt);
      const sameDay = s.toDateString() === e.toDateString();
      const t = (d)=>`${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
      if (sameDay) return `${t(s)} – ${t(e)}`;
      return `${s.toLocaleDateString()} ${t(s)} → ${e.toLocaleDateString()} ${t(e)}`;
    } catch { return ''; }
  }

  function close() {
    if (!isOpen) return;
    modal.classList.remove('dlm-show');
    setTimeout(() => {
      if (modal.parentNode) document.body.removeChild(modal);
    }, 120);
    isOpen = false;
    document.removeEventListener('keydown', onKey);
  }

  function onKey(ev) {
    if (ev.key === 'Escape') close();
  }

  function open(dayDate, items) {
    // Build content
    titleEl.textContent = dayDate instanceof Date
      ? dayDate.toLocaleDateString(undefined, { weekday:'long', year:'numeric', month:'long', day:'numeric' })
      : 'Избрани настани';

    listEl.innerHTML = '';

    (items || []).forEach((it) => {
      const li = el('li', 'dlm-item');
      const icon = it.type === 'ticket' ? '🎫' : '📅';
      const title = it.title || it.name || '(Без наслов)';
      const when = formatWhen(it);

      li.innerHTML = `
        <div class="dlm-row">
          <div class="dlm-icon">${icon}</div>
          <div class="dlm-meta">
            <div class="dlm-item-title">${title}</div>
            <div class="dlm-item-sub">${when}</div>
          </div>
          <div class="dlm-pill ${it.type === 'ticket' ? 'is-ticket' : 'is-event'}">
            ${it.type === 'ticket' ? 'Тикет' : 'Настан'}
          </div>
        </div>
      `;

      // 🔑 Auto-close then open detail
      li.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        // Close THIS popup first
        close();

        // Then open the actual detail
        if (it.type === 'ticket' && window.TicketModal && typeof window.TicketModal.open === 'function') {
          window.TicketModal.open(it);
        } else {
          document.dispatchEvent(new CustomEvent('calendar:open-edit', { detail: { event: it } }));
        }
      });

      // Hover state cue
      li.addEventListener('mouseenter', () => li.classList.add('hover'));
      li.addEventListener('mouseleave', () => li.classList.remove('hover'));

      listEl.appendChild(li);
    });

    // Mount & show
    document.body.appendChild(modal);
    requestAnimationFrame(() => {
      modal.classList.add('dlm-show');
    });
    isOpen = true;

    // Wire up one-time listeners
    closeBtn.onclick = close;
    closeBtn2.onclick = close;

    // Click on backdrop closes (but not inside dialog)
    modal.addEventListener('click', (ev) => {
      if (ev.target === modal) close();
    });

    document.addEventListener('keydown', onKey);
  }

  window.DayListModal = { open, close };
})();
