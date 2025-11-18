// app/callendar/static/js/views/invitations.js
// Invitations modal: stylish list, event delegation, live counter updates.
(function(){
  const modal = document.getElementById('InvitationsModal');
  if (!modal) return;

  const list = modal.querySelector('#InvList');
  const btnsOpen = document.querySelectorAll('.js-open-invitations');
  const badge = document.getElementById('InvitesBadge');
  const notifBadge = document.getElementById('NotifBadge');

  function show(){
    modal.hidden = false;
    requestAnimationFrame(()=>modal.classList.add('evd-show'));
    document.addEventListener('keydown', esc);
  }
  function hide(){
    modal.classList.remove('evd-show');
    setTimeout(()=>{
      modal.hidden = true;
      document.removeEventListener('keydown', esc);
    }, 160);
  }
  function esc(e){ if (e.key === 'Escape') hide(); }
  modal.addEventListener('click', (e)=>{ if (e.target===modal) hide(); });
  modal.querySelectorAll('[data-close]').forEach(b=>b.addEventListener('click', hide));

  async function fetchInvites(){
    const r = await fetch('/callendar/api/invitations', { credentials:'same-origin' });
    if (!r.ok) throw new Error('Не може да се вчитаат поканите.');
    const data = await r.json();
    return (data.items || []);
  }

  // --- Time helpers: force local display even if API sends UTC-naive ---
  function toDateLocal(isoish){
    if (!isoish) return null;
    const s = String(isoish);
    // if already has timezone offset or Z, use as-is
    if (/[zZ]$/.test(s) || /[+\-]\d\d:\d\d$/.test(s)) {
      return new Date(s);
    }
    // otherwise treat as UTC-naive → append Z to interpret as UTC
    // (server stores UTC-naive; appending Z makes browser convert to local correctly)
    return new Date(s + 'Z');
  }
  function fmtLocal(isoish){
    try {
      const d = toDateLocal(isoish);
      if (!d || isNaN(d.getTime())) return isoish || '';
      return d.toLocaleString(undefined, { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' });
    } catch {
      return isoish || '';
    }
  }

  function render(items){
    list.innerHTML = '';
    if (!items.length){
      list.innerHTML = '<div class="text-muted p-3">Немате нови покани.</div>';
      return;
    }
    items.forEach(it=>{
      const title = it.event_title || '(Без наслов)';
      const when  = `${fmtLocal(it.start_dt)} — ${fmtLocal(it.end_dt)}`;
      const org   = it.organiser_name ? ` · Организатор: ${it.organiser_name}` : '';
      const row = document.createElement('div');
      row.className = 'list-group-item py-3';
      row.innerHTML = `
        <div class="d-flex align-items-start justify-content-between gap-3">
          <div class="flex-grow-1">
            <div class="fw-bold">${title}</div>
            <div class="text-muted small">${when}${org}</div>
          </div>
          <div class="d-flex gap-2">
            <button class="btn btn-sm btn-success js-invite-respond" data-event-id="${it.event_id}" data-status="ACCEPTED"><i class="bi bi-check2"></i> Прифати</button>
            <button class="btn btn-sm btn-warning js-invite-respond" data-event-id="${it.event_id}" data-status="TENTATIVE"><i class="bi bi-circle"></i> Наскоро</button>
            <button class="btn btn-sm btn-outline-danger js-invite-respond" data-event-id="${it.event_id}" data-status="DECLINED"><i class="bi bi-x"></i> Одбиј</button>
          </div>
        </div>
      `;
      list.appendChild(row);
    });
  }

  // Event delegation for RSVP buttons
  list.addEventListener('click', async (e)=>{
    const btn = e.target.closest('.js-invite-respond');
    if (!btn) return;
    e.preventDefault();

    const eid = parseInt(btn.dataset.eventId, 10);
    const status = btn.dataset.status;
    btn.disabled = true;

    try{
      const r = await fetch('/callendar/api/invitations/respond', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ event_id: eid, status })
      });
      const data = await r.json();
      if (!r.ok || data.error) throw new Error(data.error || 'Неуспешно ажурирање.');

      // Re-render invitations from payload so remaining buttons stay active
      const items = (data.invitations && data.invitations.items) ? data.invitations.items : await fetchInvites();
      render(items);

      // Update badge counters
      const cnt = (data.invitations && typeof data.invitations.count === 'number') ? data.invitations.count : items.length;
      updateBadge(cnt);

      if (notifBadge && data.notifications && typeof data.notifications.unread === 'number'){
        setBadge(notifBadge, data.notifications.unread);
      }

      // Refresh calendar (so event color/state updates)
      document.dispatchEvent(new CustomEvent('calendar:force-reload'));
    }catch(err){
      alert(err?.message || 'Грешка.');
    }finally{
      // keep delegation active
    }
  });

  function setBadge(b, n){
    if (!b) return;
    if (n > 0){
      b.textContent = n;
      b.classList.remove('d-none');
    } else {
      b.classList.add('d-none');
      b.textContent = '0';
    }
  }
  function updateBadge(n){ setBadge(badge, n); }

  // Open modal buttons
  btnsOpen.forEach(b => b.addEventListener('click', async ()=>{
    try{
      const items = await fetchInvites();
      render(items);
      updateBadge(items.length);
      show();
    }catch(err){
      alert(err?.message || 'Грешка при вчитување.');
    }
  }));

  // Prime counts on load
  (async function prime(){
    try{
      const r = await fetch('/callendar/api/invitations/count', { credentials:'same-origin' });
      if (r.ok){
        const d = await r.json();
        updateBadge(d.count || 0);
      }
    }catch{}
    try{
      const r2 = await fetch('/notifications/api/notifications/count', { credentials:'same-origin' });
      if (r2.ok){
        const d2 = await r2.json();
        setBadge(notifBadge, d2.unread || 0);
      }
    }catch{}
  })();
})();
