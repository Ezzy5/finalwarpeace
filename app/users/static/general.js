// app/users/static/general.js
(function () {
  "use strict";

  // Global namespace (keeps your existing API shape)
  const A = (window.UsersApp = window.UsersApp || { api: {}, helpers: {} });
  A.api = A.api || {};

  // --- helpers ---
  const safe = (v) => (v == null ? "" : String(v));
  const dash = (v) => (v == null || v === "" ? "—" : String(v));

  function hasExtras(u) {
    return u && ("bank_account" in u) && ("city" in u) && ("address" in u);
  }

  function renderNow(u, container) {
    if (!container) return;
    container.innerHTML = `
      <div class="row g-3">
        <div class="col-md-4">
          <div class="small text-muted">First name</div>
          <div class="fw-semibold">${safe(u.first_name)}</div>
        </div>

        <div class="col-md-4">
          <div class="small text-muted">Last name</div>
          <div class="fw-semibold">${safe(u.last_name)}</div>
        </div>

        <div class="col-md-4">
          <div class="small text-muted">Department</div>
          <div class="fw-semibold" data-department-display="${safe(u.id)}">${dash(u.department)}</div>
          ${u.director_of ? `<div class="small text-muted">Director of ${safe(u.director_of)}</div>` : ""}
        </div>

        <div class="col-md-4">
          <div class="small text-muted">Email</div>
          <div class="fw-semibold">${safe(u.email)}</div>
        </div>

        <div class="col-md-4">
          <div class="small text-muted">Phone</div>
          <div class="fw-semibold">${dash(u.phone_number)}</div>
        </div>

        <div class="col-md-4">
          <div class="small text-muted">ID number</div>
          <div class="fw-semibold">${safe(u.id_number)}</div>
        </div>

        <div class="col-md-4">
          <div class="small text-muted">EMBG</div>
          <div class="fw-semibold">${dash(u.embg)}</div>
        </div>

        <div class="col-md-4">
          <div class="small text-muted">Трансакциска сметка</div>
          <div class="fw-semibold">${dash(u.bank_account)}</div>
        </div>

        <div class="col-md-4">
          <div class="small text-muted">Град</div>
          <div class="fw-semibold">${dash(u.city)}</div>
        </div>

        <div class="col-md-4">
          <div class="small text-muted">Адреса на живеење</div>
          <div class="fw-semibold">${dash(u.address)}</div>
        </div>

        <div class="col-md-4">
          <div class="small text-muted">Vacation Days</div>
          <div class="fw-semibold">
            ${safe(u.vacation_days)} (Left: ${
              u.vacation_days_left != null ? safe(u.vacation_days_left) : "—"
            })
          </div>
        </div>
      </div>
    `;
  }

  function renderGeneral(u, container) {
    if (!container || !u) return;

    if (hasExtras(u)) {
      renderNow(u, container);
      return;
    }

    try {
      const fetchJSON =
        A.fetchJSON || A.helpers?.fetchJSON || (async (url) => {
          const res = await fetch(url, { credentials: "same-origin" });
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        });

      if (u.id) {
        fetchJSON(`/users/api/show/${u.id}`)
          .then((resp) => {
            const full = resp?.item || u;
            window.__usersById = window.__usersById || {};
            window.__usersById[full.id] = full;
            renderNow(full, container);
          })
          .catch(() => {
            renderNow(u, container);
          });
      } else {
        renderNow(u, container);
      }
    } catch (e) {
      renderNow(u, container);
    }
  }

  // Expose
  window.renderGeneral = renderGeneral;
  A.api.renderGeneral = renderGeneral;
  A.renderGeneral = renderGeneral;
})();
