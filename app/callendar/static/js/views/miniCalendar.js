(function () {
  const wrap = document.getElementById('MiniCalendar');
  if (!wrap) return;

  const monthLabel = wrap.querySelector('#MiniMonthLabel');
  const grid = wrap.querySelector('#MiniGrid');

  let anchor = new Date();

  function build() {
    grid.innerHTML = '';
    const y = anchor.getFullYear(), m = anchor.getMonth();
    const first = new Date(y, m, 1);
    const start = new Date(first);
    start.setDate(first.getDate() - ((first.getDay()+6)%7)); // start on Monday

    monthLabel.textContent = anchor.toLocaleString(undefined, { month:'long', year:'numeric' });

    for (let i=0;i<42;i++) {
      const d = new Date(start); d.setDate(start.getDate()+i);
      const el = document.createElement('div');
      el.className = 'day' + (d.getMonth()!==m ? ' muted':'') + (sameDate(d, new Date()) ? ' active' : '');
      el.textContent = d.getDate();
      el.addEventListener('click', () => {
        document.dispatchEvent(new CustomEvent('calendar:jump-date', { detail: { date: d } }));
      });
      grid.appendChild(el);
    }
  }

  function sameDate(a,b){ return a.getFullYear()==b.getFullYear() && a.getMonth()==b.getMonth() && a.getDate()==b.getDate(); }

  wrap.querySelector('.js-mini-prev')?.addEventListener('click', () => { anchor.setMonth(anchor.getMonth()-1); build(); });
  wrap.querySelector('.js-mini-next')?.addEventListener('click', () => { anchor.setMonth(anchor.getMonth()+1); build(); });

  document.addEventListener('calendar:anchor-changed', (ev) => { anchor = new Date(ev.detail.anchor); build(); });
  build();
})();
