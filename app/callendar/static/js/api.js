// app/callendar/static/js/api.js
(function () {
  const API = {};

  // ---- CSRF helpers ----
  function getCSRFToken() {
    // Prefer <meta name="csrf-token" content="..."> (present on dashboard.html)
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute('content')) return meta.getAttribute('content');
    // Fallback to any <input name="csrf_token">
    const el = document.querySelector('input[name="csrf_token"]');
    return el ? el.value : null;
  }

  function withDefaultHeaders(extra) {
    const headers = Object.assign(
      { 'X-Requested-With': 'fetch' }, // so server can detect SPA requests
      extra || {}
    );
    const csrf = getCSRFToken();
    if (csrf) headers['X-CSRFToken'] = csrf;
    return headers;
  }

  // ---- Querystring ----
  function qs(obj) {
    const p = new URLSearchParams();
    Object.entries(obj || {}).forEach(([k, v]) => {
      if (v === undefined || v === null || v === '') return;
      p.append(k, v);
    });
    return p.toString();
  }

  // ---- Error handling ----
  async function parseError(res, fallback) {
    try {
      const json = await res.json();
      if (json && (json.error || json.message)) {
        return json.error || json.message;
      }
    } catch (_) { /* ignore JSON parse error */ }
    try {
      const text = await res.text();
      if (text) return text;
    } catch (_) { /* ignore text parse error */ }
    return fallback || `HTTP ${res.status}`;
  }

  // ---- HTTP helpers ----
  async function getJSON(url, params) {
    const u = params ? `${url}?${qs(params)}` : url;
    const res = await fetch(u, {
      credentials: 'same-origin',
      headers: withDefaultHeaders()
    });
    if (!res.ok) throw new Error(await parseError(res, `GET ${url} failed: ${res.status}`));
    return res.json();
  }

  async function postForm(url, formData) {
    const res = await fetch(url, {
      method: 'POST',
      headers: withDefaultHeaders(), // no Content-Type so browser sets multipart/form-data
      body: formData,
      credentials: 'same-origin'
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `POST ${url} failed`);
    return data;
  }

  async function postJSON(url, payload) {
    const res = await fetch(url, {
      method: 'POST',
      headers: withDefaultHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload || {}),
      credentials: 'same-origin'
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `POST ${url} failed`);
    return data;
  }

  async function putJSON(url, payload) {
    const res = await fetch(url, {
      method: 'PUT',
      headers: withDefaultHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload || {}),
      credentials: 'same-origin'
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `PUT ${url} failed`);
    return data;
  }

  async function deleteJSON(url) {
    const res = await fetch(url, {
      method: 'DELETE',
      headers: withDefaultHeaders(),
      credentials: 'same-origin'
    });
    if (!res.ok) throw new Error(await parseError(res, `DELETE ${url} failed`));
    return { ok: true };
  }

  // ---- Domain-specific wrappers ----
  // Calendar instances (events + tickets when include_tickets=1)
  API.fetchInstances = (params) => getJSON('/callendar/api/events', params);

  // CRUD for calendar events (not tickets)
  API.createEvent = (formData) => postForm('/callendar/api/events', formData);
  API.updateEvent = (id, payload) => putJSON(`/callendar/api/events/${id}`, payload);
  API.deleteEvent = (id) => deleteJSON(`/callendar/api/events/${id}`);

  // Invitations
  API.fetchInvitationsPartial = () =>
    fetch('/callendar/invitations', {
      credentials: 'same-origin',
      headers: withDefaultHeaders()
    }).then(r => {
      if (!r.ok) return r.text().then(t => { throw new Error(t || 'Failed to load invitations'); });
      return r.text();
    });

  API.respondInvitation = (event_id, status) =>
    postJSON('/callendar/api/invitations/respond', { event_id, status });

  // Ticket details (description + comments)
  API.fetchTicketDetails = (ticket_id) =>
    getJSON(`/callendar/api/ticket/${encodeURIComponent(ticket_id)}`);

  // Expose
  window.CalendarAPI = API;
})();
