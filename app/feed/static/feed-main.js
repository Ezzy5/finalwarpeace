// /static/feed/feed-main.js
import { el, apiGet, btnBusy, setPinnedCount } from "./feed-utils.js";
import { composerCard, postCard } from "./feed-components.js";

(function () {
  "use strict";
  if (window.__FEED_SPA_WIRED__) return;
  window.__FEED_SPA_WIRED__ = true;

  // Inject minimal styles once (gallery, chips, pins)
  (function injectCSS() {
    if (document.getElementById("feed-style")) return;
    const style = document.createElement("style");
    style.id = "feed-style";
    style.textContent = `
      #feed-root #feed-pins-wrap.is-collapsed #feed-pins { display: none !important; }
      #feed-root #feed-pins-wrap.is-collapsed #feed-pins-sep { display: none !important; }
      #feed-pins-toggle-icon { transition: transform .2s ease; }
      #feed-pins-wrap.is-collapsed #feed-pins-toggle-icon { transform: rotate(180deg); }

      .pin-count-pill{
        display:inline-flex; align-items:center; justify-content:center;
        min-width: 2.25rem; padding: .15rem .55rem;
        font-size:.75rem; line-height:1; font-weight:700;
        border-radius: 999px;
        color:#0b1324;
        background: linear-gradient(135deg, rgba(255,255,255,.75), rgba(255,255,255,.55));
        box-shadow: 0 2px 8px rgba(16,24,40,.08), inset 0 1px 0 rgba(255,255,255,.6);
        border: 1px solid rgba(15,23,42,.08);
      }
      @media (prefers-color-scheme: dark){
        .pin-count-pill{
          color:#e6edf6;
          background: linear-gradient(135deg, rgba(255,255,255,.08), rgba(255,255,255,.04));
          border-color: rgba(255,255,255,.08);
          box-shadow: 0 6px 16px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.06);
        }
      }
      @keyframes pin-bump{ 0%{transform:scale(1)} 35%{transform:scale(1.12)} 100%{transform:scale(1)} }
      .pin-count-bump { animation: pin-bump .25s ease-in-out; }

      .pinned-title{ display:flex; align-items:center; gap:.5rem; font-weight:700; letter-spacing:.2px; }

      /* Composer / Editor attachments */
      .comp-attach-bar{ display:flex; align-items:center; gap:.5rem; flex-wrap:wrap; }
      .comp-attach-input{ display:none; }
      .comp-thumb{
        position:relative; width:96px; height:96px; border-radius:.5rem; overflow:hidden;
        background:#f6f7f9; border:1px solid #e5e7eb;
      }
      .comp-thumb img{ width:100%; height:100%; object-fit:cover; display:block; }
      .comp-thumb .comp-x{
        position:absolute; top:4px; right:4px; width:22px; height:22px;
        display:flex; align-items:center; justify-content:center;
        border-radius:999px; background:rgba(0,0,0,.55); color:#fff; font-size:12px; cursor:pointer;
      }

      .comp-chip{
        display:inline-flex; align-items:center; gap:.4rem;
        padding:.35rem .6rem; border-radius:999px; font-size:.9rem;
        background:#f3f4f6; border:1px solid #e5e7eb;
      }
      .comp-chip .chip-x{
        width:18px; height:18px; display:flex; align-items:center; justify-content:center;
        border-radius:999px; background:#e5e7eb; cursor:pointer;
      }

      /* Post attachments (grid) */
      .feed-gallery{ display:grid; gap:6px; margin-bottom:.5rem; grid-template-columns: repeat(3, 1fr); }
      @media (max-width: 768px){ .feed-gallery{ grid-template-columns: repeat(2, 1fr); } }
      .feed-photo{ position:relative; border-radius:.6rem; overflow:hidden; background:#f6f7f9; border:1px solid #e5e7eb; cursor:pointer; }
      .feed-photo img{ width:100%; height:220px; object-fit:cover; display:block; }

      /* 🔍 Simple base styles for filter UI (details can go in feed.css) */
      #feed-root .feed-filter-wrap{
        display:flex;
        flex-direction:column;
        gap:.5rem;
      }
      #feed-root .feed-filter-toggle{
        border-radius:999px;
        display:inline-flex;
        align-items:center;
        gap:.4rem;
      }
      #feed-root .feed-filter-panel{
        border-radius:1rem;
        border:1px solid rgba(148,163,184,.5);
        padding:.75rem 1rem;
        background-color:rgba(248,250,252,.9);
      }
      @media (prefers-color-scheme: dark){
        #feed-root .feed-filter-panel{
          background-color:rgba(15,23,42,.9);
          border-color:rgba(148,163,184,.7);
        }
      }
      #feed-root .feed-filter-grid{
        display:grid;
        grid-template-columns:repeat(3, minmax(0,1fr));
        gap:.75rem;
      }
      @media (max-width: 768px){
        #feed-root .feed-filter-grid{
          grid-template-columns:1fr;
        }
      }
      #feed-root .feed-filter-label{
        font-size:.8rem;
        font-weight:600;
        color:#6b7280;
      }
    `;
    document.head.appendChild(style);
  })();

  function _doMount(panel) {
    const ROOT = panel?.querySelector?.("#feed-root");
    if (!ROOT || ROOT.__mounted || ROOT.dataset.feedMounted === "1") return;

    const FEED_API = (ROOT.dataset.endpoint || "/api/feed").replace(/\/+$/, "");
    const AVATAR_FALLBACK =
      ROOT.dataset.avatarFallback || "/static/img/avatar-placeholder.png";

    let _loading = false,
      _cursor = null,
      _done = false;
    let _pinsCollapsed = localStorage.getItem("feed.pins.collapsed") === "1";

    // 🔍 current active filters
    const _filters = {
      datePreset: "all",
      authorName: "",
      taggedOnly: 0,
      q: "",
      // NOTE: custom range (from/to) can be added later
    };

    function debounce(fn, delay) {
      let t = null;
      return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn.apply(null, args), delay);
      };
    }

    function resetAndReload() {
      const list = ROOT.querySelector("#feed-list");
      const bottom = ROOT.querySelector("#feed-bottom");
      if (list) list.innerHTML = "";
      if (bottom) bottom.innerHTML = "";
      _cursor = null;
      _done = false;
      fetchAndRender();
    }

    const buildSkeletonUI = () => {
      ROOT.innerHTML = "";

      // ----- Pins strip -----
      ROOT.appendChild(
        el(`
        <div class="mb-3" id="feed-pins-wrap" style="display:none;">
          <div class="d-flex align-items-center justify-content-between mb-2">
            <div class="d-flex align-items-center gap-2">
              <button class="btn btn-sm btn-outline-secondary" id="feed-pins-toggle" aria-expanded="true" title="Скриј/Прикажи закачени">
                <i class="bi bi-chevron-up" id="feed-pins-toggle-icon"></i>
              </button>
              <div class="pinned-title">
                <i class="bi bi-pin-angle"></i>
                <span>Закачени</span>
                <span class="pin-count-pill" title="Број на закачени"><span id="feed-pins-count">0</span></span>
              </div>
            </div>
            <div class="d-flex align-items-center gap-2">
              <button class="btn btn-sm btn-outline-secondary" id="feed-pins-refresh">Освежи</button>
            </div>
          </div>
          <div id="feed-pins" class="d-flex flex-column"></div>
          <hr class="mt-3" id="feed-pins-sep">
        </div>`)
      );

      // ----- 🔍 Search & Filter toolbar -----
      const filterWrap = el(`
        <div class="feed-filter-wrap mb-3">
          <div class="d-flex justify-content-between align-items-center">
            <button type="button"
                    class="btn btn-outline-secondary feed-filter-toggle"
                    id="feed-filter-toggle"
                    aria-expanded="false">
              <i class="bi bi-funnel"></i>
              <span>Пребарај & филтрирај</span>
            </button>
            <!-- Global search field always visible -->
            <div class="ms-2 flex-grow-1 d-none d-md-block">
              <input type="search"
                     class="form-control form-control-sm"
                     id="feed-search-input"
                     placeholder="Барај по клучен збор во објави…" />
            </div>
          </div>

          <div class="feed-filter-panel mt-2" id="feed-filter-panel" hidden>
            <div class="feed-filter-grid">
              <!-- Date preset -->
              <div>
                <div class="feed-filter-label mb-1">Филтер по датум</div>
                <select class="form-select form-select-sm" id="feed-filter-date">
                  <option value="all" selected>Сите датуми</option>
                  <option value="today">Денес</option>
                  <option value="yesterday">Вчера</option>
                  <option value="week">Оваа недела</option>
                  <option value="month">Овој месец</option>
                  <option value="year">Оваа година</option>
                  <option value="30">Последни 30 дена</option>
                  <option value="60">Последни 60 дена</option>
                  <option value="90">Последни 90 дена</option>
                  <!-- Кастом опсег ќе додадеме подоцна со datepicker -->
                </select>
              </div>

              <!-- Author filter (BY NAME) -->
              <div>
                <div class="feed-filter-label mb-1">Автор</div>
                <input type="search"
                       class="form-control form-control-sm"
                       id="feed-filter-author"
                       placeholder="Име или презиме на автор" />
              </div>

              <!-- Tagged-only + extra keyword (mobile search) -->
              <div>
                <div class="feed-filter-label mb-1">Означувања / пребарување</div>
                <div class="form-check mb-2">
                  <input class="form-check-input" type="checkbox" value="1" id="feed-filter-tagged">
                  <label class="form-check-label" for="feed-filter-tagged">
                    Само објави каде сум означен
                  </label>
                </div>
                <div class="d-block d-md-none">
                  <input type="search"
                         class="form-control form-control-sm"
                         id="feed-search-input-mobile"
                         placeholder="Барај по клучен збор…" />
                </div>
              </div>
            </div>

            <div class="d-flex justify-content-end mt-3 gap-2">
              <button type="button" class="btn btn-sm btn-outline-secondary" id="feed-filter-clear">
                Исчисти филтри
              </button>
            </div>
          </div>
        </div>
      `);
      ROOT.appendChild(filterWrap);

      // Composer + list
      ROOT.appendChild(composerCard(AVATAR_FALLBACK, FEED_API, prependPost));
      ROOT.appendChild(el(`<div id="feed-list" class="d-flex flex-column"></div>`));
      ROOT.appendChild(el(`<div id="feed-bottom"></div>`));

      // Pins controls
      ROOT.addEventListener(
        "click",
        (ev) => {
          const t = ev.target.closest("#feed-pins-toggle");
          if (t) {
            ev.preventDefault();
            setPinsCollapsed(!_pinsCollapsed);
          }
          const r = ev.target.closest("#feed-pins-refresh");
          if (r) {
            ev.preventDefault();
            fetchPins();
          }
        },
        true
      );

      // Filter controls
      const btnToggle = ROOT.querySelector("#feed-filter-toggle");
      const panelNode = ROOT.querySelector("#feed-filter-panel");
      const selDate = ROOT.querySelector("#feed-filter-date");
      const inpAuthor = ROOT.querySelector("#feed-filter-author");
      const chkTagged = ROOT.querySelector("#feed-filter-tagged");
      const btnClear = ROOT.querySelector("#feed-filter-clear");
      const inpSearch = ROOT.querySelector("#feed-search-input");
      const inpSearchMb = ROOT.querySelector("#feed-search-input-mobile");

      if (btnToggle && panelNode) {
        btnToggle.addEventListener("click", () => {
          const isHidden = panelNode.hasAttribute("hidden");
          if (isHidden) {
            panelNode.removeAttribute("hidden");
            btnToggle.setAttribute("aria-expanded", "true");
          } else {
            panelNode.setAttribute("hidden", "");
            btnToggle.setAttribute("aria-expanded", "false");
          }
        });
      }

      const onFilterChange = () => {
        resetAndReload();
      };

      if (selDate) {
        selDate.value = _filters.datePreset || "all";
        selDate.addEventListener("change", (e) => {
          _filters.datePreset = e.target.value || "all";
          onFilterChange();
        });
      }

      // AUTHOR NAME filter
      if (inpAuthor) {
        inpAuthor.addEventListener(
          "input",
          debounce((e) => {
            const val = e.target.value.trim();
            _filters.authorName = val ? val : "";
            onFilterChange();
          }, 400)
        );
      }

      if (chkTagged) {
        chkTagged.checked = !!_filters.taggedOnly;
        chkTagged.addEventListener("change", (e) => {
          _filters.taggedOnly = e.target.checked ? 1 : 0;
          onFilterChange();
        });
      }

      const applySearchValue = (val) => {
        _filters.q = val.trim();
        onFilterChange();
      };

      if (inpSearch) {
        inpSearch.addEventListener("focus", () => {
          if (panelNode && panelNode.hasAttribute("hidden")) {
            panelNode.removeAttribute("hidden");
            btnToggle?.setAttribute("aria-expanded", "true");
          }
        });
        inpSearch.addEventListener(
          "input",
          debounce((e) => {
            applySearchValue(e.target.value);
          }, 400)
        );
      }

      if (inpSearchMb) {
        inpSearchMb.addEventListener(
          "input",
          debounce((e) => {
            applySearchValue(e.target.value);
          }, 400)
        );
      }

      if (btnClear) {
        btnClear.addEventListener("click", () => {
          _filters.datePreset = "all";
          _filters.authorName = "";
          _filters.taggedOnly = 0;
          _filters.q = "";

          if (selDate) selDate.value = "all";
          if (inpAuthor) inpAuthor.value = "";
          if (chkTagged) chkTagged.checked = false;
          if (inpSearch) inpSearch.value = "";
          if (inpSearchMb) inpSearchMb.value = "";

          resetAndReload();
        });
      }
    };

    function setPinsCollapsed(collapsed) {
      _pinsCollapsed = !!collapsed;
      const wrap = ROOT.querySelector("#feed-pins-wrap");
      const toggle = ROOT.querySelector("#feed-pins-toggle");
      if (wrap) wrap.classList.toggle("is-collapsed", _pinsCollapsed);
      if (toggle) toggle.setAttribute("aria-expanded", _pinsCollapsed ? "false" : "true");
      const ic = ROOT.querySelector("#feed-pins-toggle-icon");
      if (ic) ic.className = _pinsCollapsed ? "bi bi-chevron-down" : "bi bi-chevron-up";
      localStorage.setItem("feed.pins.collapsed", _pinsCollapsed ? "1" : "0");
    }

    const appendPosts = (arr) => {
      const list = ROOT.querySelector("#feed-list");
      arr.forEach((p) =>
        list.appendChild(
          postCard(p, AVATAR_FALLBACK, FEED_API, { callbacks: pinCallbacks })
        )
      );
    };

    const prependPost = (p) => {
      const list = ROOT.querySelector("#feed-list");
      if (!list) return;
      list.prepend(
        postCard(p, AVATAR_FALLBACK, FEED_API, { callbacks: pinCallbacks })
      );
    };

    function updatePinnedCountFromDOM() {
      const n = ROOT.querySelectorAll('#feed-pins [data-post-id]').length;
      setPinnedCount(n);
      return n;
    }

    function addPinnedCard(p) {
      const wrap = ROOT.querySelector("#feed-pins-wrap");
      const pins = ROOT.querySelector("#feed-pins");
      if (pins.querySelector(`[data-post-id="${p.id}"]`)) return;
      pins.prepend(
        postCard(
          { ...p, user_pinned: true },
          AVATAR_FALLBACK,
          FEED_API,
          { inPinnedStrip: true, callbacks: pinCallbacks }
        )
      );
      wrap.style.display = "";
      setPinsCollapsed(_pinsCollapsed);
      const n = updatePinnedCountFromDOM();
      if (n > 0) wrap.style.display = "";
      document
        .querySelectorAll(`[data-post-id="${p.id}"] [data-action="pin"]`)
        .forEach((btn) => btn.setAttribute("data-pinned", "1"));
    }

    function removePinnedCard(id) {
      const wrap = ROOT.querySelector("#feed-pins-wrap");
      const pins = ROOT.querySelector("#feed-pins");
      const node = pins.querySelector(`[data-post-id="${id}"]`);
      if (node) node.remove();
      const n = updatePinnedCountFromDOM();
      if (n === 0) wrap.style.display = "none";
      document
        .querySelectorAll(`[data-post-id="${id}"] [data-action="pin"]`)
        .forEach((btn) => btn.setAttribute("data-pinned", "0"));
    }

    async function fetchPins() {
      try {
        const data = await apiGet(`${FEED_API}/pins`);
        const items = Array.isArray(data.items) ? data.items : [];
        const wrap = ROOT.querySelector("#feed-pins-wrap");
        const pins = ROOT.querySelector("#feed-pins");
        pins.innerHTML = "";
        if (!items.length) {
          setPinnedCount(0);
          wrap.style.display = "none";
          return;
        }
        items.forEach((p) =>
          pins.appendChild(
            postCard(
              { ...p, user_pinned: true },
              AVATAR_FALLBACK,
              FEED_API,
              { inPinnedStrip: true, callbacks: pinCallbacks }
            )
          )
        );
        wrap.style.display = "";
        setPinsCollapsed(_pinsCollapsed);
        setPinnedCount(items.length);
        items.forEach((p) => {
          document
            .querySelectorAll(`[data-post-id="${p.id}"] [data-action="pin"]`)
            .forEach((btn) => btn.setAttribute("data-pinned", "1"));
        });
      } catch {
        /* keep previous DOM */
      }
    }

    const pinCallbacks = { onPinAdd: addPinnedCard, onPinRemove: removePinnedCard };

    const loaderRow = () =>
      el(`
      <div class="d-flex justify-content-center my-3" id="feed-loader">
        <div class="spinner-border" role="status"><span class="visually-hidden">Loading…</span></div>
      </div>`);

    const loadMoreButton = () => {
      const btn = el(
        `<div class="text-center my-3"><button class="btn btn-outline-secondary" id="feed-load-more">Прикажи повеќе</button></div>`
      );
      btn
        .querySelector("#feed-load-more")
        .addEventListener("click", () => fetchAndRender());
      return btn;
    };

    const fetchAndRender = async () => {
      if (_loading || _done) return;
      _loading = true;
      const bottom = ROOT.querySelector("#feed-bottom");
      bottom.innerHTML = "";
      bottom.appendChild(loaderRow());
      try {
        const url = new URL(FEED_API, window.location.origin);
        if (_cursor) url.searchParams.set("cursor", _cursor);
        url.searchParams.set("limit", "10");

        // 🔍 attach filters as query params
        if (_filters.datePreset && _filters.datePreset !== "all") {
          url.searchParams.set("date_preset", _filters.datePreset);
        }
        if (_filters.authorName) {
          url.searchParams.set("author_name", _filters.authorName);
        }
        if (_filters.taggedOnly) {
          url.searchParams.set("tagged_only", "1");
        }
        if (_filters.q) {
          url.searchParams.set("q", _filters.q);
        }

        const data = await apiGet(url.toString());
        const items = Array.isArray(data.items) ? data.items : [];
        const list = ROOT.querySelector("#feed-list");
        items.forEach((p) =>
          list.appendChild(
            postCard(p, AVATAR_FALLBACK, FEED_API, { callbacks: pinCallbacks })
          )
        );
        _cursor = data.next_cursor || null;
        _done = !!data.done || items.length === 0;
        bottom.innerHTML = "";
        if (!_done) bottom.appendChild(loadMoreButton());
      } catch (_err) {
        bottom.innerHTML = `<div class="alert alert-warning border-0 rounded-4">Не може да се вчита фидот. <button class="btn btn-sm btn-outline-secondary ms-2" id="feed-retry">Повторно</button></div>`;
        document.getElementById("feed-retry")?.addEventListener("click", fetchAndRender);
      } finally {
        _loading = false;
      }
    };

    // Build and load
       // Build and load
    buildSkeletonUI();
    fetchPins();
    fetchAndRender();
    setPinsCollapsed(_pinsCollapsed); // reflect persisted collapsed state

    // 🔴 EXPOSE SIMPLE FEED APP API FOR REALTIME.JS
    window.FeedApp = {
      prependPost,                    // used by realtime.js for live new posts
      appendPosts,                    // keep if you want manual use
      reload: resetAndReload,         // optional helper
    };

    ROOT.__mounted = true;
    ROOT.dataset.feedMounted = "1";
  }


  // Public mount (called from panel)
  window.mountFeedPanel = function (selector) {
    const panel =
      selector ? document.querySelector(selector) : document.getElementById("FeedPanel");
    if (!panel) {
      console.warn("[feed] mount: panel not found", selector);
      return;
    }
    _doMount(panel);
  };

  // Auto-boot on load and when panels swap
  function tryBootNow() {
    const panel =
      document.getElementById("FeedPanel") ||
      document.querySelector('[data-init="mountFeedPanel"]') ||
      null;
    const root = panel && panel.querySelector && panel.querySelector("#feed-root");
    if (root && !root.__mounted && root.dataset.feedMounted !== "1") _doMount(panel);
  }
  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", tryBootNow, { once: true });
  else queueMicrotask(tryBootNow);
  window.addEventListener("panel:loaded", tryBootNow);
  new MutationObserver(() => tryBootNow()).observe(
    document.documentElement || document.body,
    { childList: true, subtree: true }
  );
})();
