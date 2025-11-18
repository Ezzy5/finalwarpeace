// app/callendar/static/js/views/ticketDetails.js
// Stylish Ticket Details modal — robust date handling, attachments as cards, readable comments.

(function () {
  if (window.__TicketDetailsLoaded) return;
  window.__TicketDetailsLoaded = true;

  /* ----------------- utils ----------------- */
  function el(tag, cls, html) { const n=document.createElement(tag); if(cls) n.className=cls; if(html!=null) n.innerHTML=html; return n; }
  function clear(node){ while(node.firstChild) node.removeChild(node.firstChild); }
  function initials(name=''){ const p=String(name||'').trim().split(/\s+/); if(!p.length) return 'U'; if(p.length===1) return p[0].slice(0,2).toUpperCase(); return (p[0][0]+p[p.length-1][0]).toUpperCase(); }

  // Robust date parser: ISO, "YYYY-MM-DD HH:MM[:SS]", date-only, epoch sec/ms,
  // and common EU formats "DD.MM.YYYY[ HH:MM[:SS]]" and "DD/MM/YYYY[ HH:MM[:SS]]".
  function parseAnyDate(x){
    if (x === null || x === undefined) return null;
    if (x instanceof Date) return isNaN(x.getTime()) ? null : x;

    // numbers: epoch sec/ms
    if (typeof x === 'number'){
      if (x > 0 && x < 1e12) return new Date(x * 1000); // seconds
      if (x >= 1e12) return new Date(x);                // ms
      return null;
    }

    let s = String(x).trim();
    if (!s || /invalid/i.test(s)) return null;

    // If it is already something Date can read, try directly.
    let d = new Date(s);
    if (!isNaN(d.getTime())) return d;

    // Replace space with 'T' for SQL-like strings.
    if (s.indexOf('T') === -1 && s.indexOf(' ') !== -1) {
      d = new Date(s.replace(' ', 'T'));
      if (!isNaN(d.getTime())) return d;
      // try forcing Z
      d = new Date(s.replace(' ', 'T') + 'Z');
      if (!isNaN(d.getTime())) return d;
    }

    // Date-only "YYYY-MM-DD"
    let m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (m) {
      const [_, Y,M,D] = m.map(Number);
      d = new Date(Y, M-1, D, 0, 0, 0, 0);
      return isNaN(d.getTime()) ? null : d;
    }

    // "YYYY-MM-DD HH:MM[:SS]"
    m = s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?$/);
    if (m){
      const Y=+m[1], M=+m[2], D=+m[3], h=+m[4], mi=+m[5], se=+(m[6]||0);
      d = new Date(Y, M-1, D, h, mi, se, 0);
      return isNaN(d.getTime()) ? null : d;
    }

    // "DD.MM.YYYY[ HH:MM[:SS]]"
    m = s.match(/^(\d{2})\.(\d{2})\.(\d{4})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?$/);
    if (m){
      const D=+m[1], M=+m[2], Y=+m[3], h=+(m[4]||0), mi=+(m[5]||0), se=+(m[6]||0);
      d = new Date(Y, M-1, D, h, mi, se, 0);
      return isNaN(d.getTime()) ? null : d;
    }

    // "DD/MM/YYYY[ HH:MM[:SS]]"
    m = s.match(/^(\d{2})\/(\d{2})\/(\d{4})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?$/);
    if (m){
      const D=+m[1], M=+m[2], Y=+m[3], h=+(m[4]||0), mi=+(m[5]||0), se=+(m[6]||0);
      d = new Date(Y, M-1, D, h, mi, se, 0);
      return isNaN(d.getTime()) ? null : d;
    }

    // Last resort: append Z if it looks like ISO without zone
    if (/^\d{4}-\d{2}-\d{2}T/.test(s)){
      d = new Date(s + 'Z');
      if (!isNaN(d.getTime())) return d;
    }

    return null;
  }

  const dtf = new Intl.DateTimeFormat(undefined, {
    year:'numeric', month:'short', day:'numeric',
    hour:'2-digit', minute:'2-digit'
  });
  function fmtDT(x){
    const d = parseAnyDate(x);
    if (!d) return '—';
    try { return dtf.format(d); } catch { return '—'; }
  }
  function dayMonth(x){
    const d = parseAnyDate(x);
    if (!d) return { day:'—', mon:'—' };
    return { day:String(d.getDate()), mon:d.toLocaleString(undefined, { month:'short' }).toUpperCase() };
  }

  /* --------------- modal shell --------------- */
  let root = document.getElementById('tmd-backdrop');
  if (!root) {
    root = el('div', 'evd-backdrop');
    root.id = 'tmd-backdrop';
    root.innerHTML = `
      <div class="evd-modal" role="dialog" aria-modal="true" aria-labelledby="tmd-title">
        <div class="evd-card">
          <div class="evd-hero">
            <div class="evd-hero-bg"></div>
            <div class="evd-hero-top">
              <div class="evd-hero-date">
                <div class="evd-date-day" data-f="date-day">—</div>
                <div class="evd-date-month" data-f="date-mon">—</div>
              </div>
              <button class="evd-close" aria-label="Close"><i class="bi bi-x-lg"></i></button>
            </div>
            <div class="evd-hero-bottom">
              <div class="evd-title-wrap">
                <div id="tmd-title" class="evd-title">Тикет</div>
                <div class="evd-subtitle" data-f="subtitle">—</div>
              </div>
              <div class="evd-chips" data-f="chips"></div>
            </div>
          </div>

          <div class="evd-body">
            <div class="evd-grid">
              <div class="evd-col">
                <section class="evd-section">
                  <div class="evd-sec-title"><i class="bi bi-info-circle"></i> Детали</div>
                  <div class="evd-kv"><div class="evd-k"><i class="bi bi-clock"></i> Период</div><div class="evd-v" data-f="period">—</div></div>
                  <div class="evd-kv"><div class="evd-k"><i class="bi bi-flag"></i> Статус</div><div class="evd-v" data-f="status">—</div></div>
                  <div class="evd-kv"><div class="evd-k"><i class="bi bi-lightning"></i> Приоритет</div><div class="evd-v" data-f="priority">—</div></div>
                  <div class="evd-kv"><div class="evd-k"><i class="bi bi-diagram-3"></i> Оддели</div><div class="evd-v" data-f="departments">—</div></div>
                  <div class="evd-kv">
                    <div class="evd-k"><i class="bi bi-people"></i> Доделени</div>
                    <div class="evd-v" data-f="assignees">—</div>
                  </div>
                </section>

                <section class="evd-section">
                  <div class="evd-sec-title"><i class="bi bi-paperclip"></i> Прилози</div>
                  <div class="tmd-files" data-f="attachments"></div>
                  <div class="text-muted" data-f="no-files">Нема додадени датотеки.</div>
                </section>
              </div>

              <div class="evd-col">
                <section class="evd-section">
                  <div class="evd-sec-title"><i class="bi bi-card-text"></i> Опис</div>
                  <div class="evd-desc" data-f="description"><span class="text-muted">—</span></div>
                </section>

                <section class="evd-section">
                  <div class="evd-sec-title"><i class="bi bi-chat-dots"></i> Коментари</div>
                  <div class="tmd-comments" data-f="comments"></div>
                </section>
              </div>
            </div>
          </div>

          <div class="evd-footer">
            <a class="btn btn-primary" target="_self" data-f="open-url">Отвори тикет</a>
            <button class="btn btn-light" data-close>Затвори</button>
          </div>
        </div>
      </div>
    `;
  }

  /* --------------- refs --------------- */
  const btnX  = root.querySelector('.evd-close');
  const btnC  = root.querySelector('[data-close]');
  const titleEl  = root.querySelector('#tmd-title');
  const subEl    = root.querySelector('[data-f="subtitle"]');
  const chips    = root.querySelector('[data-f="chips"]');
  const dd       = root.querySelector('[data-f="date-day"]');
  const dm       = root.querySelector('[data-f="date-mon"]');
  const periodEl = root.querySelector('[data-f="period"]');
  const statusEl = root.querySelector('[data-f="status"]');
  const prioEl   = root.querySelector('[data-f="priority"]');
  const deptEl   = root.querySelector('[data-f="departments"]');
  const assEl    = root.querySelector('[data-f="assignees"]');
  const descEl   = root.querySelector('[data-f="description"]');
  const filesBox = root.querySelector('[data-f="attachments"]');
  const noFiles  = root.querySelector('[data-f="no-files"]');
  const commentsBox = root.querySelector('[data-f="comments"]');
  const openBtn  = root.querySelector('[data-f="open-url"]');

  /* --------------- rendering helpers --------------- */
  function setHero(startIso, title){
    const d = dayMonth(startIso);
    dd.textContent = d.day; dm.textContent = d.mon;
    titleEl.textContent = title || 'Тикет';
    subEl.textContent   = title || 'Тикет';
  }

  function setChips(t){
    clear(chips);
    chips.appendChild(el('div','evd-chip','Тикет'));
    if (t.priority) chips.appendChild(el('div','evd-chip', `<i class="bi bi-lightning"></i> ${t.priority}`));
    if (t.status)   chips.appendChild(el('div','evd-chip', `<i class="bi bi-flag"></i> ${t.status}`));
  }

  function setKV(t){
    periodEl.textContent = `${fmtDT(t.start_dt)} — ${fmtDT(t.end_dt)}`;
    statusEl.textContent = t.status || '—';
    prioEl.textContent   = t.priority || '—';

    // Departments: array of strings
    deptEl.textContent   = (Array.isArray(t.departments) && t.departments.length) ? t.departments.join(', ') : '—';

    // Assignees: expect [{name:'First Last'}]; fallback to other identifiers
    if (Array.isArray(t.assignees) && t.assignees.length){
      assEl.innerHTML = t.assignees
        .map(a => {
          const name = a.name || a.full_name || a.username || a.email || `user-${a.id ?? ''}`;
          return `<span class="evd-chip">${name}</span>`;
        })
        .join(' ');
    } else {
      assEl.textContent = '—';
    }

    descEl.textContent = t.description || '—';
  }

  function setFiles(list){
    clear(filesBox);
    if (Array.isArray(list) && list.length){
      noFiles.classList.add('d-none');
      list.forEach(f => {
        if (!f || (!f.url && !f.filename)) return; // skip empties
        const a = el('a', 'evd-attach-card', `
          <div class="evd-attach-icon"><i class="bi bi-file-earmark"></i></div>
          <div class="evd-attach-meta">
            <div class="evd-attach-name">${(f.filename || 'attachment')}</div>
            <div class="evd-attach-hint">${f.size ? `${f.size} · ` : ''}Преземи датотека</div>
          </div>
        `);
        if (f.url) { a.href = f.url; a.target = '_blank'; a.rel = 'noopener'; }
        filesBox.appendChild(a);
      });
    } else {
      noFiles.classList.remove('d-none');
    }
  }

  function setComments(list){
    clear(commentsBox);
    if (!Array.isArray(list) || !list.length){
      commentsBox.appendChild(el('div', 'text-muted', 'Нема коментари.'));
      return;
    }
    const safe = list.map(c => {
      const when = c.created_at_iso || c.created_at || c.timestamp || c.created || c.date;
      return { ...c, __d: parseAnyDate(when) };
    }).sort((a,b) => {
      const ta = a.__d ? a.__d.getTime() : Infinity;
      const tb = b.__d ? b.__d.getTime() : Infinity;
      return ta - tb;
    });

    safe.forEach(c => {
      const row = el('div', 'tmd-cmt-row');
      const av  = el('div', 'tmd-cmt-avatar', initials(c.author_name || c.author || ''));
      const body= el('div', 'tmd-cmt-body');
      const head= el('div', 'tmd-cmt-head', `
        <span class="tmd-cmt-name">${c.author_name || c.author || '—'}</span>
        <span class="tmd-cmt-time">${fmtDT(c.created_at_iso || c.created_at || c.timestamp || c.created || c.date)}</span>
      `);
      const text= el('div', 'tmd-cmt-text', String(c.text || c.body || '').replace(/\n/g,'<br>'));
      body.appendChild(head); body.appendChild(text);
      row.appendChild(av); row.appendChild(body);
      commentsBox.appendChild(row);
    });
  }

  /* --------------- show / hide --------------- */
  let isOpen = false, pollTimer = null, currentId = null;
  function show(){ if(isOpen) return; document.body.appendChild(root); requestAnimationFrame(()=>root.classList.add('evd-show')); isOpen=true; document.addEventListener('keydown', onEsc); }
  function hide(){
    if(!isOpen) return;
    root.classList.remove('evd-show');
    setTimeout(()=>{ try{root.remove();}catch{} isOpen=false; document.removeEventListener('keydown', onEsc); if (pollTimer){ clearInterval(pollTimer); pollTimer=null; } currentId=null; }, 160);
  }
  function onEsc(e){ if(e.key === 'Escape') hide(); }

  btnX.addEventListener('click', hide);
  btnC.addEventListener('click', hide);
  root.addEventListener('click', (e)=>{ if (e.target === root) hide(); });

  /* --------------- data fetch --------------- */
  async function fetchTicket(id){
    const r = await fetch(`/callendar/api/tickets/${id}`, { credentials: 'same-origin' });
    if (!r.ok) throw new Error('Не може да се вчита тикетот.');
    const data = await r.json();
    if (!data || !data.ticket) throw new Error('Неправилен одговор од сервер.');
    return data.ticket;
  }

  async function openTicketDetails(id){
    try{
      const t = await fetchTicket(id);
      currentId = id;

      setHero(t.start_dt, t.title);
      setChips(t);
      setKV(t);
      setFiles(t.attachments || []);
      setComments(t.comments || []);

      if (t.url) { openBtn.href = t.url; openBtn.classList.remove('disabled'); }
      else { openBtn.removeAttribute('href'); openBtn.classList.add('disabled'); }

      try { if (window.DayListModal?.close) window.DayListModal.close(); } catch {}

      show();

      // Refresh comments & attachments while open
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(async ()=>{
        if (!isOpen || !currentId) return;
        try {
          const t2 = await fetchTicket(currentId);
          setFiles(t2.attachments || []);
          setComments(t2.comments || []);
        } catch {}
      }, 20000);
    }catch(err){
      console.error('[TicketDetails] open failed', err);
      alert(err?.message || 'Грешка при вчитување на тикетот.');
    }
  }

  /* --------------- public API --------------- */
  window.TicketDetails = { open: openTicketDetails, close: hide };

  // Back-compat bridge used by calendar chips
  window.TicketModal = window.TicketModal || {};
  window.TicketModal.open = function(it){
    const raw = it && (it.id ?? String(it.id||'').replace(/^ticket:/,'')); // supports {id:"ticket:123"} or {id:123}
    const id = Number(raw);
    if (Number.isFinite(id)) openTicketDetails(id);
  };
})();
