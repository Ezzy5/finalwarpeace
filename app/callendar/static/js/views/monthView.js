// app/callendar/static/js/views/monthView.js
(function () {
  const grid = document.getElementById('MonthGrid');
  const header = document.getElementById('MonthHeader');
  if (!grid) return;

  const MAX_VISIBLE_PER_DAY = 2;
  let lastAnchor = new Date();

  function build(anchor) {
    lastAnchor = new Date(anchor);
    grid.innerHTML='';
    const y = lastAnchor.getFullYear(), m=lastAnchor.getMonth();
    header.textContent = lastAnchor.toLocaleString(undefined, { month:'long', year:'numeric' });

    const first = new Date(y, m, 1);
    const start = new Date(first);
    start.setDate(first.getDate() - ((first.getDay()+6)%7)); // Monday

    for (let i=0;i<42;i++) {
      const d = new Date(start); d.setDate(start.getDate()+i);
      const cell = document.createElement('div'); cell.className='mcell';

      const dayno = document.createElement('div');
      dayno.className='dayno' + (d.getMonth()!==m ? ' muted':'');
      dayno.textContent = d.getDate();
      cell.appendChild(dayno);

      const spans = document.createElement('div'); spans.className = 'spans'; cell.appendChild(spans);

      const moreBox = document.createElement('div'); moreBox.className = 'more-container'; cell.appendChild(moreBox);

      const btn = document.createElement('button');
      btn.type='button'; btn.className='btn btn-sm btn-outline-primary create-btn'; btn.innerHTML='<i class="bi bi-plus-lg"></i>';
      btn.addEventListener('click', () => {
        const startAt = new Date(d); startAt.setHours(9,0,0,0);
        const endAt = new Date(startAt); endAt.setHours(endAt.getHours()+1);
        document.dispatchEvent(new CustomEvent('calendar:create', { detail: { start: startAt, end: endAt } }));
      });
      cell.appendChild(btn);

      grid.appendChild(cell);
    }
  }

  function SOD(d){ const x=new Date(d); x.setHours(0,0,0,0); return x; }

  function place(items) {
    const y = lastAnchor.getFullYear(), m = lastAnchor.getMonth();
    const first = new Date(y, m, 1);
    const start = new Date(first); start.setDate(first.getDate() - ((first.getDay()+6)%7));
    const end   = new Date(start); end.setDate(start.getDate()+41);

    const byDay = Array.from({length: 42}, () => []);
    (items || []).forEach(it => {
      const s = new Date(it.start_dt), e = new Date(it.end_dt);
      const S = SOD(s < start ? start : s);
      const E = SOD(e > end ? end : e);

      const startIdx = Math.max(0, Math.floor((S - start)/(1000*60*60*24)));
      const endIdx   = Math.min(41, Math.floor((E - start)/(1000*60*60*24)));

      for (let i = startIdx; i <= endIdx; i++) {
        byDay[i].push({ item: it, i, startIdx, endIdx });
      }
    });

    for (let i = 0; i < 42; i++) {
      const cell = grid.children[i];
      const spans = cell.querySelector('.spans');
      const moreBox = cell.querySelector('.more-container');
      const list = byDay[i] || [];

      spans.innerHTML = '';
      moreBox.innerHTML = '';
      if (!list.length) continue;

      const toShow = list.slice(0, MAX_VISIBLE_PER_DAY);
      const hidden = list.length - toShow.length;

      toShow.forEach(seg => {
        const it = seg.item;
        const frag = document.createElement('div');
        frag.className = 'cal-span' + (it.type === 'ticket' ? ' ticket' : '');
        if (seg.i === seg.startIdx) frag.classList.add('start');
        if (seg.i === seg.endIdx)   frag.classList.add('end');

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
            console.debug('[DnD] month span dragstart', payload);
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

      if (hidden > 0) {
        const more = document.createElement('button');
        more.type = 'button';
        more.className = 'more-chip';
        more.innerHTML = `<i>+${hidden}</i> Повеќе`;
        more.addEventListener('click', () => {
          const dayDate = new Date(start); dayDate.setDate(start.getDate()+i);
          window.DayListModal && window.DayListModal.open(dayDate, byDay[i].map(x => x.item));
        });
        moreBox.appendChild(more);
      }
    }
  }

  document.addEventListener('calendar:view-changed', (ev) => { if (ev.detail.view === 'month') build(ev.detail.anchor); });
  document.addEventListener('calendar:anchor-changed', (ev) => { if (!document.getElementById('MonthView')?.classList.contains('d-none')) build(ev.detail.anchor); });
  document.addEventListener('calendar:data', (ev) => {
    if (document.getElementById('MonthView')?.classList.contains('d-none')) return;
    build(ev.detail.state.anchor);
    place(ev.detail.items || []);
  });
})();
