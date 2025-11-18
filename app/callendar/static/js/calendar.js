// app/callendar/static/js/calendar.js
(function () {
  const CalendarApp = {
    state: {
      view: 'month',
      anchor: new Date(),
      filters: {
        q: '',
        invitations: 0,
        organiser: 0,
        participant: 0,
        declined: 0,
        period: 'THIS_MONTH',
        next_n_days: ''
      }
    },

    init() {
      const root = document.getElementById('CalendarRoot');
      if (!root) return;

      const selected = (root.dataset.selectedView || 'month').toLowerCase();
      this.state.view = ['day','week','month'].includes(selected) ? selected : 'month';
      this.state.anchor = new Date(root.dataset.now || Date.now());

      // Toolbar
      document.querySelectorAll('.js-switch-view').forEach(btn => {
        btn.addEventListener('click', () => this.switchView(btn.dataset.view));
      });
      document.querySelector('.js-prev')?.addEventListener('click', () => this.move(-1));
      document.querySelector('.js-next')?.addEventListener('click', () => this.move(+1));
      document.querySelector('.js-today')?.addEventListener('click', () => {
        this.state.anchor = new Date();
        this._setLabel();
        this.loadAndRender();
        this._emit('calendar:anchor-changed', { view: this.state.view, anchor: this.state.anchor });
      });

      // Invitations
      const panel = document.getElementById('InvitationsPanel');
      document.querySelector('.js-open-invitations')?.addEventListener('click', async () => {
        const html = await window.CalendarAPI.fetchInvitationsPartial();
        panel.innerHTML = html;
        panel.classList.remove('d-none');

        panel.querySelector('.js-close-invitations')?.addEventListener('click', () => {
          panel.classList.add('d-none');
          panel.innerHTML = '';
        });

        panel.querySelectorAll('.js-invite-respond')?.forEach(b => {
          b.addEventListener('click', async () => {
            b.disabled = true;
            try {
              await window.CalendarAPI.respondInvitation(parseInt(b.dataset.eventId, 10), b.dataset.status);
              const html2 = await window.CalendarAPI.fetchInvitationsPartial();
              panel.innerHTML = html2;
              this.loadAndRender();
            } catch (e) {
              alert(e.message || 'Failed to respond');
            } finally { b.disabled = false; }
          });
        });
      });

      // Create event
      document.querySelector('.js-open-create')?.addEventListener('click', () => {
        this._emit('calendar:create', { start: new Date(this.state.anchor), end: new Date(this.state.anchor) });
      });

      // Search
      const qInput = document.querySelector('.js-filter-q');
      if (qInput) {
        let t = null;
        qInput.addEventListener('input', () => {
          clearTimeout(t);
          t = setTimeout(() => {
            this.state.filters.q = qInput.value || '';
            this.loadAndRender();
          }, 250);
        });
      }

      // Mini calendar jump
      document.addEventListener('calendar:jump-date', (ev) => {
        this.state.anchor = new Date(ev.detail.date);
        this._setLabel();
        this.loadAndRender();
        this._emit('calendar:anchor-changed', { view: this.state.view, anchor: this.state.anchor });
      });

      // Filters
      document.addEventListener('calendar:filters-applied', (ev) => {
        this.state.filters = { ...this.state.filters, ...(ev.detail || {}) };
        this.loadAndRender();
      });

      // External reloads
      document.addEventListener('calendar:force-reload', () => this.loadAndRender());
      document.addEventListener('calendar:refetch',       () => this.loadAndRender());

      // DnD delete bin
      this._wireTrashDnD();

      // First paint
      this._setLabel();
      this.switchView(this.state.view);
      this._emit('calendar:ready', { state: this.state });
    },

    getState() { return { ...this.state }; },

    switchView(view) {
      if (!['day','week','month'].includes(view)) view = 'month';
      this.state.view = view;

      const views = {
        day: document.getElementById('DayView'),
        week: document.getElementById('WeekView'),
        month: document.getElementById('MonthView')
      };
      Object.values(views).forEach(el => el && el.classList.add('d-none'));
      if (views[view]) views[view].classList.remove('d-none');

      this._setLabel();
      this.loadAndRender();
      this._emit('calendar:view-changed', { view, anchor: this.state.anchor });
    },

    move(delta) {
      const d = new Date(this.state.anchor);
      if (this.state.view === 'day') d.setDate(d.getDate() + delta);
      else if (this.state.view === 'week') d.setDate(d.getDate() + 7 * delta);
      else d.setMonth(d.getMonth() + delta);
      this.state.anchor = d;
      this._setLabel();
      this.loadAndRender();
      this._emit('calendar:anchor-changed', { view: this.state.view, anchor: this.state.anchor });
    },

    async loadAndRender() {
      const { start, end } = this._calcWindow();
      const params = {
        start: start.toISOString(),
        end: end.toISOString(),
        q: this.state.filters.q || undefined,
        invitations: this.state.filters.invitations ? '1' : undefined,
        organiser:  this.state.filters.organiser  ? '1' : undefined,
        participant:this.state.filters.participant? '1' : undefined,
        declined:   this.state.filters.declined   ? '1' : undefined,
        include_tickets: '1'
      };

      try {
        const data = await window.CalendarAPI.fetchInstances(params);
        const items = data.items || [];

        // mark event items draggable
        items.forEach(it => {
          it._isDraggable = (it.type === 'event' && it.id != null);
          if (it._isDraggable) it._dragId = `event:${it.id}`;
        });

        this._emit('calendar:data', { items, window: { start, end }, state: this.getState() });
      } catch (e) {
        console.error('Failed to load calendar data:', e);
      }
    },

    _calcWindow() {
      const a = this.state.anchor;
      const startOfDay = (d) => { const x = new Date(d); x.setHours(0,0,0,0); return x; };
      const endOfDay   = (d) => { const x = new Date(d); x.setHours(23,59,59,999); return x; };
      const startOfWeek= (d) => { const x = new Date(d); const day=(x.getDay()+6)%7; x.setDate(x.getDate()-day); x.setHours(0,0,0,0); return x; };
      const endOfWeek  = (d) => { const x = startOfWeek(d); x.setDate(x.getDate()+6); x.setHours(23,59,59,999); return x; };
      const startOfMonth=(d)=> new Date(d.getFullYear(), d.getMonth(), 1);
      const endOfMonth  =(d)=> new Date(d.getFullYear(), d.getMonth()+1, 0, 23,59,59,999);

      if (this.state.view === 'day')  return { start: startOfDay(a),  end: endOfDay(a) };
      if (this.state.view === 'week') return { start: startOfWeek(a), end: endOfWeek(a) };
      return { start: startOfMonth(a), end: endOfMonth(a) };
    },

    _setLabel() {
      const el = document.getElementById('RangeLabel');
      if (!el) return;
      const { start, end } = this._calcWindow();
      const opts = { year:'numeric', month:'short', day:'numeric' };
      el.textContent = (this.state.view === 'day')
        ? start.toLocaleDateString(undefined, opts)
        : `${start.toLocaleDateString(undefined, opts)} — ${end.toLocaleDateString(undefined, opts)}`;
    },

    _wireTrashDnD() {
      const trash = document.getElementById('CalTrash');
      if (!trash) return;

      let draggingEvent = false;

      // Global fallback store in case dataTransfer is blocked
      window.__CAL_DRAG_ID = null;

      // Visual state reset
      function clearTrashVisual() {
        trash.classList.remove('is-armed', 'is-hover');
      }

      // Accepts only payloads like "event:123"
      function payloadFromEvent(ev) {
        let t = '';
        try { t = ev.dataTransfer.getData('text/plain') || ''; } catch {}
        if (!/^event:\d+$/.test(t)) {
          // fallback to global
          if (typeof window.__CAL_DRAG_ID === 'string' && /^event:\d+$/.test(window.__CAL_DRAG_ID)) {
            t = window.__CAL_DRAG_ID;
          }
        }
        return t;
      }

      // Global drag events to flip the armed state
      document.addEventListener('dragstart', (ev) => {
        const el = ev.target.closest('[data-entity="event"][data-id]');
        if (!el) return;
        const id = el.getAttribute('data-id') || '';
        if (!/^event:\d+$/.test(id)) return;

        draggingEvent = true;
        trash.classList.add('is-armed');
        window.__CAL_DRAG_ID = id;

        try {
          ev.dataTransfer.setData('text/plain', id);
          ev.dataTransfer.effectAllowed = 'move';
        } catch {}
        // helpful log:
        console.debug('[TrashDnD] dragstart', id);
      });

      document.addEventListener('dragend', () => {
        draggingEvent = false;
        window.__CAL_DRAG_ID = null;
        clearTrashVisual();
      });

      trash.addEventListener('dragover', (ev) => {
        if (!draggingEvent) return;
        const t = payloadFromEvent(ev);
        if (!/^event:\d+$/.test(t)) return;
        ev.preventDefault(); // REQUIRED to allow drop
        try { ev.dataTransfer.dropEffect = 'move'; } catch {}
      });

      trash.addEventListener('dragenter', (ev) => {
        if (!draggingEvent) return;
        const t = payloadFromEvent(ev);
        if (!/^event:\d+$/.test(t)) return;
        trash.classList.add('is-hover');
      });

      trash.addEventListener('dragleave', () => {
        trash.classList.remove('is-hover');
      });

      trash.addEventListener('drop', async (ev) => {
        ev.preventDefault();
        const payload = payloadFromEvent(ev);
        console.debug('[TrashDnD] drop payload:', payload);
        clearTrashVisual();
        if (!/^event:\d+$/.test(payload)) return;

        const id = parseInt(payload.split(':')[1], 10);
        if (!Number.isFinite(id)) return;

        const ok = confirm('Дали сигурно сакате да го избришете настанот?');
        if (!ok) return;

        try {
          await window.CalendarAPI.deleteEvent(id);
          // flash
          trash.classList.add('is-armed');
          setTimeout(clearTrashVisual, 450);
          this.loadAndRender();
        } catch (e) {
          console.error('[TrashDnD] delete failed', e);
          alert(e?.message || 'Неуспешно бришење.');
        }
      });
    },

    _emit(name, detail) { document.dispatchEvent(new CustomEvent(name, { detail })); },
  };

  window.CalendarApp = CalendarApp;
})();
