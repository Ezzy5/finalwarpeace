// app/callendar/static/js/views/eventModal.js
// Calendar Event Modal — robust singleton with Select2 attendees and API-compatible payloads.
// v2.4.0

(function () {
  if (window.__EventModalLoaded) return;
  window.__EventModalLoaded = true;

  const DEBUG = !!window.CAL_DEBUG;
  const log = (...a) => DEBUG && console.log('[EventModal]', ...a);
  const warn = (...a) => console.warn('[EventModal]', ...a);

  const $ = window.jQuery;

  // ----------------- Utilities -----------------
  function pad(n) { return String(n).padStart(2, '0'); }

  // "2025-10-13T09:00" local datetime-local value
  function fmtLocal(d) {
    if (!(d instanceof Date)) return '';
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function parseLocal(v) {
    if (!v) return null;
    // Accepts "YYYY-MM-DDTHH:MM" or "YYYY-MM-DD HH:MM"
    const s = v.replace(' ', 'T');
    const [ymd, hm = '00:00'] = s.split('T');
    const [y, m, d] = ymd.split('-').map(Number);
    const [hh, mm] = hm.split(':').map(Number);
    return new Date(y, (m - 1), d, hh, mm, 0, 0);
  }

  function parseIso(v) { return v ? new Date(v) : null; }

  // ----------------- Build Modal DOM -----------------
  let shell = document.getElementById('evm-shell');
  if (!shell) {
    shell = document.createElement('div');
    shell.id = 'evm-shell';
    shell.innerHTML = `
      <style>
        /* Minimal styling; adapt to your theme */
        #evm-shell { position: fixed; inset:0; display:none; z-index: 1060; }
        #evm-shell.evm-show { display:block; }
        .evm-backdrop { position:absolute; inset:0; background: rgba(17,17,17,.35); }
        .evm-modal {
          position:absolute; left:50%; top:6%;
          transform: translateX(-50%);
          width: min(860px, calc(100% - 24px));
          background: #fff; border-radius: 14px; box-shadow: 0 20px 60px rgba(0,0,0,.25);
          display:flex; flex-direction:column; max-height: 88%;
        }
        .evm-header { display:flex; align-items:center; justify-content:space-between; padding:14px 18px; border-bottom:1px solid #e8eaf1; }
        .evm-title { font-weight: 600; font-size: 1.05rem; }
        .evm-close { border:0; background:transparent; font-size:22px; line-height:1; cursor:pointer; }
        .evm-form { display:flex; flex-direction:column; min-height: 0; }
        .evm-body { padding:16px 18px; overflow:auto; }
        .evm-footer { padding:12px 18px; display:flex; align-items:center; justify-content:space-between; border-top:1px solid #e8eaf1; }
        .evm-left { color:#b02a37; }
        .evm-right { display:flex; gap:8px; }
        .collapse { display:none; }
        .collapse.show { display:block; }
      </style>
      <div class="evm-backdrop" data-backdrop></div>
      <div class="evm-modal" role="dialog" aria-modal="true">
        <div class="evm-header">
          <div class="evm-title" id="evm-title">Нов настан</div>
          <button type="button" class="evm-close" aria-label="Close">&times;</button>
        </div>

        <form class="evm-form" enctype="multipart/form-data" novalidate>
          <div class="evm-body">
            <div class="row gy-3">
              <div class="col-12">
                <label class="form-label">Име на настан</label>
                <input type="text" name="title" class="form-control" placeholder="Назив..." required>
              </div>

              <div class="col-md-6">
                <label class="form-label">Почеток</label>
                <input type="datetime-local" name="start_dt" class="form-control" required>
              </div>
              <div class="col-md-6">
                <label class="form-label">Крај</label>
                <input type="datetime-local" name="end_dt" class="form-control" required>
              </div>

              <div class="col-12">
                <button type="button" class="btn btn-sm btn-outline-secondary" data-collapse="tz">Временска зона</button>
                <div class="collapse mt-2" data-collapsible="tz">
                  <label class="form-label">Time zone (IANA)</label>
                  <input type="text" name="timezone" class="form-control" placeholder="Europe/Skopje">
                </div>
              </div>

              <div class="col-md-4">
                <label class="form-label">Повторување</label>
                <select name="repeat" class="form-select">
                  <option value="NONE" selected>Без повторување</option>
                  <option value="DAILY">Дневно</option>
                  <option value="WEEKLY">Неделно</option>
                  <option value="MONTHLY">Месечно</option>
                  <option value="YEARLY">Годишно</option>
                </select>
              </div>

              <div class="col-md-8">
                <label class="form-label">Учeсници</label>
                <select name="attendees" id="evm-attendees" class="form-select" multiple style="width:100%"></select>
                <div class="form-text">Изберете еден или повеќе корисници.</div>
              </div>

              <div class="col-12 form-check mt-2">
                <input type="checkbox" id="notify_att" name="notify_att" class="form-check-input">
                <label for="notify_att" class="form-check-label">Извести кога прифатат/одбијат покана</label>
              </div>

              <div class="col-12">
                <button type="button" class="btn btn-sm btn-outline-secondary" data-collapse="more">Повеќе</button>
                <div class="collapse mt-2" data-collapsible="more">
                  <label class="form-label">Опис</label>
                  <textarea name="description" class="form-control" rows="3" placeholder="Опционален опис..."></textarea>
                  <div class="mt-3">
                    <label class="form-label">Датотека (опционално)</label>
                    <input type="file" name="attachment" class="form-control">
                  </div>
                </div>
              </div>

              <div class="col-md-6">
                <label class="form-label">Потсетник (претходно)</label>
                <select name="reminder_predefined" class="form-select">
                  <option value="">Без потсетник</option>
                  <option value="5">5 минути порано</option>
                  <option value="10">10 минути порано</option>
                  <option value="15">15 минути порано</option>
                  <option value="30">30 минути порано</option>
                  <option value="60">1 час порано</option>
                  <option value="120">2 часа порано</option>
                  <option value="__custom__">Прилагодено…</option>
                </select>
              </div>
              <div class="col-md-6" data-reminder-custom style="display:none">
                <label class="form-label">Прилагодено (минути)</label>
                <input type="number" min="1" step="1" name="reminder_custom" class="form-control" placeholder="на пр. 7">
              </div>
            </div>
          </div>

          <div class="evm-footer">
            <div class="evm-left"><div class="small" data-error></div></div>
            <div class="evm-right">
              <button type="button" class="btn btn-light" data-cancel>Откажи</button>
              <button type="submit" class="btn btn-primary" data-submit>
                <span class="label">Сочувај</span>
                <span class="spinner-border spinner-border-sm d-none" role="status" aria-hidden="true"></span>
              </button>
            </div>
          </div>
        </form>
      </div>
    `;
    document.body.appendChild(shell);
  }

  // Elements
  const backdrop = shell.querySelector('[data-backdrop]');
  const modal = shell.querySelector('.evm-modal');
  const form = shell.querySelector('.evm-form');
  const titleEl = shell.querySelector('#evm-title');
  const closeBtn = shell.querySelector('.evm-close');
  const cancelBtn = shell.querySelector('[data-cancel]');
  const submitBtn = shell.querySelector('[data-submit]');
  const spinner = submitBtn.querySelector('.spinner-border');
  const errorEl = shell.querySelector('[data-error]');
  const selAtt = shell.querySelector('#evm-attendees');
  const selRepeat = shell.querySelector('[name="repeat"]');
  const selReminder = shell.querySelector('[name="reminder_predefined"]');
  const remCustomWrap = shell.querySelector('[data-reminder-custom]');
  const inputRemCustom = shell.querySelector('[name="reminder_custom"]');
  const inputTitle = shell.querySelector('[name="title"]');
  const inputStart = shell.querySelector('[name="start_dt"]');
  const inputEnd = shell.querySelector('[name="end_dt"]');
  const inputTZ = shell.querySelector('[name="timezone"]');
  const chkNotify = shell.querySelector('[name="notify_att"]');
  const txtDesc = shell.querySelector('[name="description"]');
  const inputFile = shell.querySelector('[name="attachment"]');

  // ----------------- Select2 attendees -----------------
  const USERS_ENDPOINT = '/callendar/api/users/options';
  let select2Ready = false;
  let prefetchDone = false;

  function haveSelect2() {
    return !!($ && $.fn && $.fn.select2);
  }

  function initSelect2IfNeeded() {
    if (!haveSelect2()) {
      warn('Select2 not present. Using plain <select>.');
      return;
    }
    if ($(selAtt).data('select2')) {
      select2Ready = true;
      return;
    }
    $(selAtt).select2({
      theme: 'bootstrap-5',
      width: '100%',
      multiple: true,
      placeholder: 'Изберете учесници…',
      allowClear: true,
      dropdownParent: $(shell),
      minimumInputLength: 0,
      ajax: {
        url: USERS_ENDPOINT,
        dataType: 'json',
        delay: 200,
        data: (params) => ({ q: params.term || '' }),
        processResults: (data) => ({ results: (data && data.results) || [] }),
        cache: true
      }
    });
    select2Ready = true;
    log('Select2 initialized @', USERS_ENDPOINT);
  }

  async function prefetchUsersOnce() {
    if (prefetchDone) return;
    try {
      const res = await fetch(USERS_ENDPOINT, { credentials: 'same-origin' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      const results = (data && data.results) || [];

      if (!results.length) {
        log('Prefetch returned 0 users.');
        prefetchDone = true;
        return;
      }

      if (haveSelect2()) {
        const $sel = $(selAtt);
        if (!$sel.data('select2')) initSelect2IfNeeded();
        results.forEach(u => {
          const opt = new Option(u.text, u.id, false, false);
          $sel.append(opt);
        });
        $sel.trigger('change');
      } else {
        selAtt.innerHTML = '';
        results.forEach(u => {
          const opt = document.createElement('option');
          opt.value = u.id;
          opt.textContent = u.text;
          selAtt.appendChild(opt);
        });
      }

      prefetchDone = true;
      log('Prefetched', results.length, 'users.');
    } catch (err) {
      warn('Prefetch users failed:', err);
      prefetchDone = true;
    }
  }

  // ----------------- Collapsibles / reminder -----------------
  shell.addEventListener('click', (ev) => {
    const btn = ev.target.closest('[data-collapse]');
    if (!btn) return;
    const key = btn.getAttribute('data-collapse');
    const box = shell.querySelector(`[data-collapsible="${key}"]`);
    if (!box) return;
    box.classList.toggle('show');
  });

  selReminder.addEventListener('change', () => {
    const isCustom = selReminder.value === '__custom__';
    remCustomWrap.style.display = isCustom ? '' : 'none';
    if (!isCustom) inputRemCustom.value = '';
  });

  // ----------------- Modal open/close -----------------
  let opened = false;

  function openShell() {
    if (opened) return;
    shell.classList.add('evm-show');
    opened = true;
    document.addEventListener('keydown', onKey);
    initSelect2IfNeeded();
    prefetchUsersOnce();
  }

  function closeShell() {
    if (!opened) return;
    shell.classList.remove('evm-show');
    opened = false;
    document.removeEventListener('keydown', onKey);
  }

  function onKey(e) { if (e.key === 'Escape') closeShell(); }

  backdrop.addEventListener('click', closeShell);
  shell.querySelector('.evm-close').addEventListener('click', closeShell);
  cancelBtn.addEventListener('click', closeShell);

  // ----------------- Populate / Reset -----------------
  function resetForm() {
    errorEl.textContent = '';
    form.reset();
    if (haveSelect2() && select2Ready) $(selAtt).val(null).trigger('change');
  }

  function openCreate(init) {
    resetForm();
    titleEl.textContent = 'Нов настан';

    const now = new Date();
    let s = (init && init.start instanceof Date) ? init.start : now;
    let e = (init && init.end instanceof Date) ? init.end : new Date(s.getTime() + 60 * 60 * 1000);
    s.setSeconds(0, 0); e.setSeconds(0, 0);

    inputStart.value = fmtLocal(s);
    inputEnd.value = fmtLocal(e);
    inputTZ.value = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Europe/Skopje';
    selRepeat.value = 'NONE';
    openShell();
  }

  async function openEditByPayload(payload) {
    resetForm();
    titleEl.textContent = 'Уреди настан';

    // expected payload fields: id, title, start_dt, end_dt, timezone, repeat, description, notify_on_responses, attendees[]
    inputTitle.value = payload.title || '';
    inputStart.value = payload.start_dt ? payload.start_dt.replace('T', ' ').slice(0, 16).replace(' ', 'T') : '';
    inputEnd.value = payload.end_dt ? payload.end_dt.replace('T', ' ').slice(0, 16).replace(' ', 'T') : '';
    inputTZ.value = payload.timezone || '';
    selRepeat.value = (payload.repeat || 'NONE').toUpperCase();
    chkNotify.checked = !!payload.notify_on_responses;
    txtDesc.value = payload.description || '';

    // attendees (array of {id, name, email})
    const list = Array.isArray(payload.attendees) ? payload.attendees : [];
    if (haveSelect2()) {
      const $sel = $(selAtt);
      if (!$sel.data('select2')) initSelect2IfNeeded();
      $sel.empty();
      list.forEach(a => {
        const text = a.name || a.email || ('user-' + a.id);
        const opt = new Option(text, a.id, true, true);
        $sel.append(opt);
      });
      $sel.trigger('change');
    } else {
      selAtt.innerHTML = '';
      list.forEach(a => {
        const opt = document.createElement('option');
        opt.value = a.id;
        opt.selected = true;
        opt.textContent = a.name || a.email || ('user-' + a.id);
        selAtt.appendChild(opt);
      });
    }

    openShell();
  }

  async function openEditById(id) {
    try {
      const res = await fetch(`/callendar/api/events/${id}`, { credentials: 'same-origin' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      if (!data || !data.event) throw new Error('Invalid response');
      await openEditByPayload(data.event);
    } catch (err) {
      warn('Failed to load event details:', err);
      alert('Не може да се вчитаат деталите за настанот.');
    }
  }

  // ----------------- Submit (Create/Update) -----------------
  async function onSubmit(ev) {
    ev.preventDefault();
    errorEl.textContent = '';
    submitBtn.disabled = true;
    spinner.classList.remove('d-none');

    try {
      const t = (inputTitle.value || '').trim();
      if (!t) throw new Error('Внесете име на настан.');
      const s = parseLocal(inputStart.value);
      const e = parseLocal(inputEnd.value);
      if (!s || !e) throw new Error('Внесете валиден почеток и крај.');
      if (e <= s) throw new Error('Крајот мора да е после почетокот.');

      // Determine create vs update: we store "editId" on shell.dataset when editing
      const editId = shell.dataset.editId ? parseInt(shell.dataset.editId, 10) : null;

      const fd = new FormData();
      fd.append('title', t);
      fd.append('start_dt', s.toISOString()); // API expects ISO; converts to naive UTC server-side
      fd.append('end_dt', e.toISOString());
      if (inputTZ.value) fd.append('timezone', inputTZ.value.trim());

      // Repeat (UPPERCASE for API)
      const repeatVal = (selRepeat.value || 'NONE').toUpperCase();
      fd.append('repeat', repeatVal);

      // Notify flag
      if (chkNotify.checked) fd.append('notify_on_responses', '1');

      // Description / attachment
      if (txtDesc.value) fd.append('description', txtDesc.value);
      if (inputFile.files && inputFile.files[0]) fd.append('attachment', inputFile.files[0]);

      // Reminder preset/custom -> API uses reminder_predefined and reminder_custom
      const preset = selReminder.value;
      if (preset && preset !== '__custom__') {
        fd.append('reminder_predefined', preset);
      } else if (preset === '__custom__' && inputRemCustom.value) {
        fd.append('reminder_custom', inputRemCustom.value);
      }

      // Attendees -> attendees repeated field
      if (haveSelect2() && select2Ready) {
        const vals = $(selAtt).val() || [];
        vals.forEach(v => fd.append('attendees', v));
      } else {
        Array.from(selAtt.selectedOptions).forEach(opt => fd.append('attendees', opt.value));
      }

      let resp;
      if (editId) {
        resp = await fetch(`/callendar/api/events/${editId}`, {
          method: 'PUT',
          body: fd,
          credentials: 'same-origin'
        });
      } else {
        // create
        resp = await fetch('/callendar/api/events', {
          method: 'POST',
          body: fd,
          credentials: 'same-origin'
        });
      }

      let data = {};
      try { data = await resp.json(); } catch {}
      if (!resp.ok) throw new Error(data.error || 'Неуспешно зачувување.');

      closeShell();
      document.dispatchEvent(new CustomEvent('calendar:force-reload'));

    } catch (err) {
      errorEl.textContent = err?.message || 'Грешка при зачувување.';
    } finally {
      submitBtn.disabled = false;
      spinner.classList.add('d-none');
      // Clear edit flag
      delete shell.dataset.editId;
    }
  }

  // ----------------- Public API + Wiring -----------------
  window.EventModal = {
    open(init) {
      // Create
      delete shell.dataset.editId;
      openCreate(init || {});
    },
    openEdit(eventOrId) {
      // eventOrId can be {event:{...}} | {id:123} | number | object with id
      let id = null;
      let payload = null;

      if (typeof eventOrId === 'number') id = eventOrId;
      else if (eventOrId && typeof eventOrId === 'object') {
        if ('event' in eventOrId && eventOrId.event && eventOrId.event.id) {
          payload = eventOrId.event;
        } else if ('id' in eventOrId) {
          id = parseInt(eventOrId.id, 10);
        } else if ('start_dt' in eventOrId) {
          // direct payload (from calendar items)
          payload = eventOrId;
        }
      }

      if (payload) {
        shell.dataset.editId = String(payload.id || '');
        openEditByPayload(payload);
      } else if (id) {
        shell.dataset.editId = String(id);
        openEditById(id);
      } else {
        warn('openEdit called without a valid id/payload');
      }
    },
    close: closeShell
  };

  // Submit
  form.addEventListener('submit', onSubmit);

  // Prevent *double* modal open: we intercept early and stop propagation
  const QUICK_SELECTOR = '.create-btn, .js-quick-create, [data-action="new-event"], #CreateEventBtn, #NewEventBtn, .js-new-event';
  function handleQuickClick(btn, ev) {
    if (ev) { ev.preventDefault(); ev.stopPropagation(); }
    const sIso = btn.getAttribute('data-start-iso');
    const eIso = btn.getAttribute('data-end-iso');
    let s = sIso ? parseIso(sIso) : null;
    let e = eIso ? parseIso(eIso) : null;

    if (!s) {
      const cell = btn.closest('[data-date],[data-day]');
      if (cell?.dataset.date) s = parseIso(cell.dataset.date);
      const hour = cell?.dataset.hour ? Number(cell.dataset.hour) : null;
      if (s && Number.isFinite(hour)) s.setHours(hour, 0, 0, 0);
    }
    if (!s) s = new Date();
    if (!e) e = new Date(s.getTime() + 60 * 60 * 1000);

    window.EventModal.open({ start: s, end: e });
  }

  // Global delegates (capture true to beat other handlers)
  function delegateClicks(e) {
    const btn = e.target.closest(QUICK_SELECTOR);
    if (!btn) return;
    handleQuickClick(btn, e);
  }
  document.addEventListener('click', delegateClicks, true);
  document.addEventListener('pointerdown', delegateClicks, true);
  document.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    const btn = e.target.closest(QUICK_SELECTOR);
    if (!btn) return;
    handleQuickClick(btn, e);
  }, true);

  // Calendar bus events
  document.addEventListener('calendar:create', (ev) => {
    const d = ev.detail || {};
    window.EventModal.open(d);
  });

  document.addEventListener('calendar:open-edit', (ev) => {
    // detail: { event: {...} } or { id:123 }
    window.EventModal.openEdit(ev.detail);
  });

  log('ready');
})();
