// app/callendar/static/js/views/dayView.js
(function () {
  const grid = document.getElementById('DayGrid');
  const headerDate = document.getElementById('DayHeaderDate');
  const headerMeta = document.getElementById('DayHeaderMeta');
  if (!grid) return;

  let anchor = new Date();

  function pad2(n){ return String(n).padStart(2,'0'); }

  function build(day) {
    anchor = new Date(day);
    grid.innerHTML = '';
    headerDate.textContent = anchor.toLocaleDateString(undefined, { weekday:'long', year:'numeric', month:'long', day:'numeric' });
    headerMeta.textContent = '';

    for (let h=0; h<24; h++) {
      const row = document.createElement('div'); row.className='hour-row';
      const lab = document.createElement('div'); lab.className='label'; lab.textContent = `${pad2(h)}:00`;
      const slot = document.createElement('div'); slot.className='slot';

      const btn = document.createElement('button');
      btn.type='button'; btn.className='btn btn-sm btn-outline-primary create-btn'; btn.innerHTML='<i class="bi bi-plus-lg"></i>';
      btn.addEventListener('click', () => {
        const start = new Date(anchor); start.setHours(h,0,0,0);
        const end = new Date(start); end.setMinutes(end.getMinutes()+60);
        document.dispatchEvent(new CustomEvent('calendar:create', { detail: { start, end } }));
      });

      slot.appendChild(btn);
      row.appendChild(lab); row.appendChild(slot);
      grid.appendChild(row);
    }
  }

  function place(items) {
    const dayStart = new Date(anchor); dayStart.setHours(0,0,0,0);
    const dayEnd = new Date(anchor); dayEnd.setHours(23,59,59,999);

    (items || []).forEach(it => {
      const s = new Date(it.start_dt), e = new Date(it.end_dt);
      if (e < dayStart || s > dayEnd) return;

      const hour = s.getHours();
      const row = grid.children[hour];
      if (!row) return;
      const slot = row.querySelector('.slot');

      const el = document.createElement('div');
      el.className = 'cal-event' + (it.type === 'ticket' ? ' ticket' : '');
      el.title = it.title;
      el.textContent = `${pad2(s.getHours())}:${pad2(s.getMinutes())} ${it.title}`;

      // Make draggable for events only (and write payload at dragstart)
      if (it.type === 'event' && it._isDraggable) {
        const payload = it._dragId || `event:${it.id}`;
        el.setAttribute('draggable', 'true');
        el.dataset.entity = 'event';
        el.dataset.id = payload;
        el.dataset.draggable = 'true';
        el.addEventListener('dragstart', (ev) => {
          window.__CAL_DRAG_ID = payload;
          try {
            ev.dataTransfer.setData('text/plain', payload);
            ev.dataTransfer.effectAllowed = 'move';
          } catch {}
          console.debug('[DnD] day dragstart', payload);
        });
      }

      el.addEventListener('click', () => {
        if (it.type === 'ticket' && it.url) { window.location.href = it.url; return; }
        document.dispatchEvent(new CustomEvent('calendar:open-edit', { detail: { event: it } }));
      });
      slot.appendChild(el);
    });
  }

  document.addEventListener('calendar:view-changed', (ev) => {
    if (ev.detail.view === 'day') build(ev.detail.anchor);
  });
  document.addEventListener('calendar:anchor-changed', (ev) => {
    const host = document.getElementById('DayView');
    if (!host || host.classList.contains('d-none')) return;
    build(ev.detail.anchor);
  });
  document.addEventListener('calendar:data', (ev) => {
    const host = document.getElementById('DayView');
    if (!host || host.classList.contains('d-none')) return;
    build(ev.detail.state.anchor);
    place(ev.detail.items || []);
  });
})();
