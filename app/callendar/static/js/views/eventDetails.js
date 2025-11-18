// app/callendar/static/js/views/eventDetails.js
// Stylish Event Details modal with icons, chips, avatars, and attachment card + robust organiser fallback.

(function () {
  if (window.__EventDetailsLoaded) return;
  window.__EventDetailsLoaded = true;

  function el(tag, cls, html) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }

  // ---- Date parsing & formatting (timezone-safe) ----
  // Normalize incoming datetime to a Date by assuming UTC if no TZ info is present.
  function parseISODate(x) {
    if (!x && x !== 0) return null;
    if (x instanceof Date) return x;
    if (typeof x === 'number') {
      // epoch ms or seconds? heuristics: seconds are too small
      return new Date(x < 1e12 ? x * 1000 : x);
    }
    let s = String(x).trim();
    if (!s) return null;

    // Replace space between date/time with "T" for better parsing
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(s)) s = s.replace(' ', 'T');

    // If string already ends with Z or ±HH:MM, keep as-is; else assume UTC and append Z
    const hasTZ = /([Zz]|[+-]\d{2}:\d{2})$/.test(s);
    if (!hasTZ) s += 'Z';

    const d = new Date(s);
    return isNaN(d.getTime()) ? null : d;
  }

  function fmtDateTime(x) {
    try {
      const d = parseISODate(x);
      if (!d) return x || '';
      return d.toLocaleString(undefined, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        weekday: 'long',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch { return x || ''; }
  }

  function fmtTimeRange(startIso, endIso) {
    const s = parseISODate(startIso);
    const e = parseISODate(endIso);
    if (!s || !e) return '—';
    const startStr = s.toLocaleString(undefined, {
      year: 'numeric', month: 'long', day: 'numeric',
      weekday: 'long', hour: '2-digit', minute: '2-digit'
    });
    const endStr = e.toLocaleString(undefined, {
      year: 'numeric', month: 'long', day: 'numeric',
      weekday: 'long', hour: '2-digit', minute: '2-digit'
    });
    return `${startStr} — ${endStr}`;
  }

  function initials(name = '') {
    const p = String(name).trim().split(/\s+/);
    if (!p.length) return 'U';
    if (p.length === 1) return p[0].slice(0, 2).toUpperCase();
    return (p[0][0] + p[p.length - 1][0]).toUpperCase();
  }

  // Try to resolve organiser's name even when organiser_name isn't provided
  function resolveOrganiserName(ev) {
    // 1) Preferred: organiser_name from API
    if (ev.organiser_name && String(ev.organiser_name).trim()) return ev.organiser_name;

    // 2) If we have attendees and organiser_id, try to match by id
    if (Array.isArray(ev.attendees) && ev.attendees.length && ev.organiser_id != null) {
      const org = ev.attendees.find(a => Number(a.id) === Number(ev.organiser_id));
      if (org) return org.name || org.email || `user-${org.id ?? ''}`;
    }

    // 3) Any other API fields someone might have added
    if (ev.organiser && typeof ev.organiser === 'string' && ev.organiser.trim()) return ev.organiser;
    if (ev.organiser_email) return ev.organiser_email;
    if (ev.organiser_username) return ev.organiser_username;

    // 4) Fallback
    return null; // let caller decide label
  }

  // ---------- Modal shell (built once) ----------
  let root = document.getElementById('evd-backdrop');
  if (!root) {
    root = el('div', 'evd-backdrop'); // overlay
    root.id = 'evd-backdrop';
    root.innerHTML = `
      <div class="evd-modal" role="dialog" aria-modal="true" aria-labelledby="evd-title">
        <div class="evd-card">
          <div class="evd-hero">
            <div class="evd-hero-bg"></div>
            <div class="evd-hero-top">
              <div class="evd-hero-date">
                <div class="evd-date-day" data-field="date-day">—</div>
                <div class="evd-date-month" data-field="date-month">—</div>
              </div>
              <button class="evd-close" aria-label="Close" title="Затвори">
                <i class="bi bi-x-lg"></i>
              </button>
            </div>
            <div class="evd-hero-bottom">
              <div class="evd-title-wrap">
                <div id="evd-title" class="evd-title">Настан</div>
                <div class="evd-subtitle" data-field="subtitle">—</div>
              </div>
              <div class="evd-chips" data-field="chips"></div>
            </div>
          </div>

          <div class="evd-body">
            <div class="evd-grid">
              <!-- Left column -->
              <div class="evd-col">
                <section class="evd-section">
                  <div class="evd-sec-title"><i class="bi bi-info-circle"></i> Детали</div>
                  <div class="evd-kv">
                    <div class="evd-k"><i class="bi bi-clock"></i> Време</div>
                    <div class="evd-v" data-field="time">—</div>
                  </div>
                  <div class="evd-kv">
                    <div class="evd-k"><i class="bi bi-geo"></i> Временска зона</div>
                    <div class="evd-v" data-field="timezone">—</div>
                  </div>
                  <div class="evd-kv">
                    <div class="evd-k"><i class="bi bi-repeat"></i> Повторување</div>
                    <div class="evd-v" data-field="repeat">—</div>
                  </div>
                  <div class="evd-kv">
                    <div class="evd-k"><i class="bi bi-person-badge"></i> Организатор</div>
                    <div class="evd-v" data-field="organiser">—</div>
                  </div>
                </section>

                <section class="evd-section">
                  <div class="evd-sec-title"><i class="bi bi-people"></i> Учесници</div>
                  <div class="evd-attendees" data-field="attendees">
                    <div class="text-muted">—</div>
                  </div>
                </section>

                <section class="evd-section">
                  <div class="evd-sec-title"><i class="bi bi-paperclip"></i> Прилог</div>
                  <div class="evd-attach d-none" data-block="attachment">
                    <a class="evd-attach-card" data-field="attachment-link" target="_blank" rel="noopener">
                      <div class="evd-attach-icon"><i class="bi bi-file-earmark"></i></div>
                      <div class="evd-attach-meta">
                        <div class="evd-attach-name" data-field="attachment-name">file.ext</div>
                        <div class="evd-attach-hint">Преземи датотека</div>
                      </div>
                    </a>
                  </div>
                  <div class="text-muted" data-block="no-attachment">Нема додадена датотека.</div>
                </section>
              </div>

              <!-- Right column -->
              <div class="evd-col">
                <section class="evd-section">
                  <div class="evd-sec-title"><i class="bi bi-card-text"></i> Опис</div>
                  <div class="evd-desc" data-field="description">
                    <span class="text-muted">—</span>
                  </div>
                </section>
              </div>
            </div>
          </div>

          <div class="evd-footer">
            <button class="btn btn-light" data-close>Затвори</button>
          </div>
        </div>
      </div>
    `;
  }

  // refs
  const btnClose = root.querySelector('.evd-close');
  const btnClose2 = root.querySelector('[data-close]');
  const dateDay = root.querySelector('[data-field="date-day"]');
  const dateMonth = root.querySelector('[data-field="date-month"]');
  const titleEl = root.querySelector('#evd-title');
  const subtitleEl = root.querySelector('[data-field="subtitle"]');
  const chipsWrap = root.querySelector('[data-field="chips"]');
  const timeEl = root.querySelector('[data-field="time"]');
  const tzEl = root.querySelector('[data-field="timezone"]');
  const repeatEl = root.querySelector('[data-field="repeat"]');
  const orgEl = root.querySelector('[data-field="organiser"]');
  const attendeesWrap = root.querySelector('[data-field="attendees"]');
  const descEl = root.querySelector('[data-field="description"]');
  const attachBlock = root.querySelector('[data-block="attachment"]');
  const attachLink = root.querySelector('[data-field="attachment-link"]');
  const attachName = root.querySelector('[data-field="attachment-name"]');
  const noAttach = root.querySelector('[data-block="no-attachment"]');

  // helpers
  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  function setHeroDate(startIso) {
    const d = parseISODate(startIso);
    if (!d) { dateDay.textContent = '—'; dateMonth.textContent = '—'; return; }
    dateDay.textContent = String(d.getDate());
    dateMonth.textContent = d.toLocaleString(undefined, { month: 'short' }).toUpperCase();
  }

  function makeChip(text, icon) {
    const c = el('div', 'evd-chip');
    if (icon) c.innerHTML = `<i class="bi ${icon}"></i> ${text}`;
    else c.textContent = text;
    return c;
  }

  function renderAttendees(list) {
    clear(attendeesWrap);
    if (!Array.isArray(list) || list.length === 0) {
      attendeesWrap.appendChild(el('div', 'text-muted', '—'));
      return;
    }
    list.forEach(a => {
      const name = a.name || a.email || `user-${a.id || ''}`;
      const avatar = el('div', 'evd-avatar', initials(name));
      const info = el('div', 'evd-att-info');
      info.appendChild(el('div', 'evd-att-name', name));
      if (a.email) info.appendChild(el('div', 'evd-att-email text-muted', a.email));
      const row = el('div', 'evd-att-row');
      row.appendChild(avatar);
      row.appendChild(info);
      attendeesWrap.appendChild(row);
    });
  }

  function setAttachment(url, filename) {
    if (url) {
      attachBlock.classList.remove('d-none');
      noAttach.classList.add('d-none');
      attachLink.href = url;
      attachName.textContent = filename || 'attachment';
    } else {
      attachBlock.classList.add('d-none');
      noAttach.classList.remove('d-none');
      attachLink.removeAttribute('href');
      attachName.textContent = '';
    }
  }

  // show/hide
  let open = false;
  function show() {
    if (open) return;
    document.body.appendChild(root);
    requestAnimationFrame(() => root.classList.add('evd-show'));
    open = true;
    document.addEventListener('keydown', esc);
  }
  function hide() {
    if (!open) return;
    root.classList.remove('evd-show');
    setTimeout(() => { try { root.remove(); } catch {} open = false; document.removeEventListener('keydown', esc); }, 160);
  }
  function esc(e){ if (e.key === 'Escape') hide(); }

  // close handlers
  btnClose.addEventListener('click', hide);
  btnClose2.addEventListener('click', hide);
  root.addEventListener('click', (e) => { if (e.target === root) hide(); });

  async function openDetails(eventId) {
    try {
      const r = await fetch(`/callendar/api/events/${eventId}`, { credentials: 'same-origin' });
      if (!r.ok) throw new Error('Не може да се вчита настанот.');
      const data = await r.json();
      const ev = data.event;

      // header
      titleEl.textContent = ev.title || '(Без наслов)';
      const organiserName = resolveOrganiserName(ev);
      subtitleEl.textContent = organiserName ? `Организатор: ${organiserName}` : 'Организатор непознат';
      setHeroDate(ev.start_dt);

      // chips
      clear(chipsWrap);
      chipsWrap.appendChild(makeChip('Настан', 'bi-calendar-event'));
      if (ev.notify_on_responses) chipsWrap.appendChild(makeChip('Нотификации', 'bi-bell'));
      if (ev.timezone) chipsWrap.appendChild(makeChip(ev.timezone, 'bi-globe2'));
      chipsWrap.appendChild(makeChip((ev.repeat || 'NONE').toUpperCase(), 'bi-repeat'));

      // meta left (USE TZ-SAFE FORMATTERS)
      timeEl.textContent = fmtTimeRange(ev.start_dt, ev.end_dt);
      tzEl.textContent = ev.timezone || '—';
      repeatEl.textContent = (ev.repeat || 'NONE').toUpperCase();
      orgEl.textContent = organiserName || '—';

      // attendees
      renderAttendees(ev.attendees);

      // description
      clear(descEl);
      descEl.textContent = ev.description || '—';

      // attachment (prefer flat fields, fallback to standard route)
      let url = ev.attachment_url || null;
      let name = ev.attachment_filename || null;
      if (!url && ev.id && ev.attachment_path) {
        url = `/callendar/api/events/${ev.id}/attachment`;
        if (!name) try { name = ev.attachment_path.split(/[\\/]/).pop(); } catch {}
      }
      setAttachment(url, name);

      // If day-list popover was open, close it to avoid overlaying
      try { if (window.DayListModal?.close) window.DayListModal.close(); } catch {}

      show();
    } catch (err) {
      console.error('[EventDetails] open failed:', err);
      alert(err?.message || 'Грешка при вчитување на деталите.');
    }
  }

  // Public API
  window.EventDetails = { open: openDetails, close: hide };

  // Calendar chips -> details
  document.addEventListener('calendar:open-edit', (ev) => {
    const it = ev.detail?.event;
    if (!it || it.type !== 'event') return;
    const id = parseInt(String(it.id).replace(/^event:/, ''), 10);
    if (Number.isFinite(id)) {
      openDetails(id);
      ev.preventDefault();
      ev.stopPropagation();
    }
  }, true);
})();
