// app/callendar/static/js/views/weekView.js
(function () {
  const grid = document.getElementById('WeekGrid');
  const header = document.getElementById('WeekHeaderRange');
  if (!grid) return;

  const MAX_VISIBLE_TOP = 2;
  let lastAnchor = new Date();

  function startOfWeek(d) {
    const x = new Date(d);
    const day = (x.getDay() + 6) % 7; // Mon=0
    x.setDate(x.getDate() - day);
    x.setHours(0, 0, 0, 0);
    return x;
  }
  const SOD = (d) => { const x = new Date(d); x.setHours(0,0,0,0); return x; };

  function build(anchor) {
    lastAnchor = new Date(anchor);
    grid.innerHTML = '';

    const start = startOfWeek(lastAnchor);
    const end = new Date(start); end.setDate(end.getDate() + 6);
    header.textContent =
      `${start.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} — ${end.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}`;

    for (let h = 0; h < 24; h++) {
      const lab = document.createElement('div');
      lab.className = 'hour-label';
      lab.textContent = `${String(h).padStart(2, '0')}:00`;
      grid.appendChild(lab);

      for (let d = 0; d < 7; d++) {
        const cell = document.createElement('div');
        cell.className = 'cell';
        if (h === 0) cell.classList.add('is-top-row');

        const spans = document.createElement('div');
        spans.className = 'spans';
        cell.appendChild(spans);

        if (h === 0) {
          const moreBox = document.createElement('div');
          moreBox.className = 'more-container';
          cell.appendChild(moreBox);
        }

        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-sm btn-outline-primary create-btn js-quick-create';
        btn.innerHTML = '<i class="bi bi-plus-lg"></i>';

        const dt = new Date(start);
        dt.setDate(start.getDate() + d);
        dt.setHours(h, 0, 0, 0);
        const dtEnd = new Date(dt.getTime() + 60 * 60 * 1000);
        btn.setAttribute('data-start-iso', dt.toISOString());
        btn.setAttribute('data-end-iso', dtEnd.toISOString());

        cell.appendChild(btn);
        grid.appendChild(cell);
      }
    }
  }

  function place(items) {
    const start = startOfWeek(lastAnchor);
    const end = new Date(start); end.setDate(end.getDate() + 6);

    const topByDay = Array.from({ length: 7 }, () => []);
    const singles = [];

    (items || []).forEach(it => {
      const s = new Date(it.start_dt);
      const e = new Date(it.end_dt);
      const Ss = SOD(s < start ? start : s);
      const Ee = SOD(e > end ? end : e);
      const multi = Ee > Ss;

      if (multi) {
        let d0 = new Date(Ss);
        while (d0 <= Ee) {
          const dayIdx = ((d0.getDay() + 6) % 7);
          topByDay[dayIdx].push({
            item: it,
            dayIdx,
            isStart: +SOD(d0) === +Ss,
            isEnd: +SOD(d0) === +Ee
          });
          d0.setDate(d0.getDate() + 1);
        }
      } else {
        singles.push(it);
      }
    });

    // top lane
    for (let d = 0; d < 7; d++) {
      const cellIndex = 1 + d; // hour 0 row (after hour label)
      const cell = grid.children[cellIndex];
      const spans = cell.querySelector('.spans');
      const moreBox = cell.querySelector('.more-container');
      const list = topByDay[d];

      spans.innerHTML = '';
      if (moreBox) moreBox.innerHTML = '';
      if (!list.length) continue;

      const toShow = list.slice(0, MAX_VISIBLE_TOP);
      const hidden = list.length - toShow.length;

      toShow.forEach(seg => {
        const it = seg.item;
        const frag = document.createElement('div');
        frag.className = 'cal-span' + (it.type === 'ticket' ? ' ticket' : '');
        if (seg.isStart) frag.classList.add('start');
        if (seg.isEnd)   frag.classList.add('end');

        // Drag only if event
        if (it.type === 'event' && it._isDraggable) {
          const payload = it._dragId || `event:${it.id}`;
          frag.setAttribute('draggable', 'true');
          frag.dataset.entity = 'event';
          frag.dataset.id = payload;
          frag.dataset.draggable = 'true';
          frag.addEventListener('dragstart', (ev) => {
            window.__CAL_DRAG_ID = payload;
            try {
              ev.dataTransfer.setData('text/plain', payload);
              ev.dataTransfer.effectAllowed = 'move';
            } catch {}
            console.debug('[DnD] week span dragstart', payload);
          });
        }

        const label = document.createElement('span');
        label.className = 'label';
        label.textContent = it.title || '(Без наслов)';
        frag.appendChild(label);

        frag.title = it.title;
        frag.addEventListener('click', () => {
          if (it.type === 'ticket' && window.TicketModal) { window.TicketModal.open(it); return; }
          document.dispatchEvent(new CustomEvent('calendar:open-edit', { detail: { event: it } }));
        });
        spans.appendChild(frag);
      });

      if (hidden > 0 && moreBox) {
        const more = document.createElement('button');
        more.type = 'button';
        more.className = 'more-chip';
        more.innerHTML = `<i>+${hidden}</i> Повеќе`;
        more.addEventListener('click', () => {
          const dayDate = new Date(start); dayDate.setDate(start.getDate() + d);
          window.DayListModal && window.DayListModal.open(dayDate, list.map(x => x.item));
        });
        moreBox.appendChild(more);
      }
    }

    // hour chips
    singles.forEach(it => {
      const s = new Date(it.start_dt);
      const dayIdx = ((s.getDay() + 6) % 7);
      const h = s.getHours();
      const idx = h * (7 + 1) + 1 + dayIdx;
      const cell = grid.children[idx];
      if (!cell) return;

      const el = document.createElement('div');
      el.className = 'cal-event' + (it.type === 'ticket' ? ' ticket' : '');
      el.title = it.title;
      el.textContent = `${String(s.getHours()).padStart(2,'0')}:${String(s.getMinutes()).padStart(2,'0')} ${it.title}`;

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
          console.debug('[DnD] week hour dragstart', payload);
        });
      }

      el.addEventListener('click', () => {
        if (it.type === 'ticket' && window.TicketModal) { window.TicketModal.open(it); return; }
        document.dispatchEvent(new CustomEvent('calendar:open-edit', { detail: { event: it } }));
      });
      cell.appendChild(el);
    });
  }

  document.addEventListener('calendar:view-changed', (ev) => {
    if (ev.detail.view === 'week') build(ev.detail.anchor);
  });
  document.addEventListener('calendar:anchor-changed', (ev) => {
    const host = document.getElementById('WeekView');
    if (!host || host.classList.contains('d-none')) return;
    build(ev.detail.anchor);
  });
  document.addEventListener('calendar:data', (ev) => {
    const host = document.getElementById('WeekView');
    if (!host || host.classList.contains('d-none')) return;
    build(ev.detail.state.anchor);
    place(ev.detail.items || []);
  });
})();
