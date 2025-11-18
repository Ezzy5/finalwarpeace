/* app/static/js/panel-loader.js
 * Robust panel loader that:
 * 1) Handles sidebar AJAX panel navigation
 * 2) Re-mounts SPA panels when the user hard-refreshes or lands directly on a panel URL
 * 3) Executes <script data-exec> tags both after AJAX injection and on direct loads
 */

(function () {
  "use strict";

  // 1) Declare every panel path here (include Feed, Callendar, etc.)
  const PANEL_PATHS = new Set([
    "/users/panel",
    "/departments/panel",
    "/war/panel",
    "/api/feed/panel",
    "/feed/panel",
    "/feed",
    "/callendar/panel",   // 👈 add calendar panel
    "/callendar",         // 👈 in case you ever use /callendar
  ]);

  // Helper: execute any <script data-exec> tags under a root (or the whole document)
  function execDataScripts(root) {
    const scope = root || document;
    const scripts = scope.querySelectorAll("script[data-exec]");
    scripts.forEach((oldScript) => {
      const s = document.createElement("script");
      // Copy important attributes
      if (oldScript.type) s.type = oldScript.type;
      if (oldScript.src) s.src = oldScript.src;
      // Preserve module/nomodule/etc.
      for (const attr of oldScript.attributes) {
        if (attr.name.startsWith("data-") && attr.name !== "data-exec") {
          s.setAttribute(attr.name, attr.value);
        }
      }
      // Inline content (rare in your app, but supported)
      if (oldScript.textContent && oldScript.textContent.trim().length) {
        s.textContent = oldScript.textContent;
      }
      // Replace in DOM so the browser actually executes it
      oldScript.parentNode.replaceChild(s, oldScript);
    });
  }

  // Helper: fetch a panel URL and inject into #MainPanel / #MainContent (central container)
  async function loadPanel(url) {
    const container =
      document.querySelector(
        "#MainPanel, #MainContent, [data-panel-root], main, #content"
      ); // 👈 added #MainContent
    if (!container) {
      // Fall back: if we don’t have a container, do a hard navigation.
      window.location.assign(url);
      return;
    }

    const res = await fetch(url, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    if (!res.ok) {
      // On error, let’s navigate normally so the user isn’t stuck blank.
      window.location.assign(url);
      return;
    }

    const html = await res.text();
    container.innerHTML = html;

    // Re-exec scripts that are meant to run after injection
    execDataScripts(container);

    // Also dispatch a custom event so SPA modules can hook if they want
    const ev = new CustomEvent("panel:loaded", { detail: { url, container } });
    window.dispatchEvent(ev);
  }

  // Sidebar / nav clicks: intercept and AJAX-load panels
  function interceptPanelLinks() {
    document.addEventListener("click", (e) => {
      const a = e.target.closest("a[data-panel]");
      if (!a) return;

      // 👇 IMPORTANT: prefer data-url over href
      const rawHref = a.dataset.url || a.getAttribute("href");
      if (!rawHref || rawHref === "#") return;

      const path = new URL(rawHref, window.location.origin).pathname;

      // If it looks like a panel URL, AJAX it.
      if (PANEL_PATHS.has(path)) {
        e.preventDefault();
        history.pushState({}, "", path);
        loadPanel(path);
      }
    });
  }

  // Handle back/forward
  window.addEventListener("popstate", () => {
    const path = window.location.pathname;
    if (PANEL_PATHS.has(path)) {
      loadPanel(path);
    }
  });

  // On initial load:
  // - If we’re already *on* a panel URL (e.g., user refreshed on /api/feed/panel),
  //   make sure any <script data-exec> inside the current DOM actually runs.
  function boot() {
    const path = window.location.pathname;

    // Always wire up link interception
    interceptPanelLinks();

    if (PANEL_PATHS.has(path)) {
      // We’re on a panel URL right now.
      execDataScripts(document);

      // Optional: if after a tick we still don’t see a mounted SPA, force-refresh via AJAX loader
      queueMicrotask(() => {
        const feedRoot = document.querySelector("#feed-root");
        const looksUninitialized =
          feedRoot && !feedRoot.__mounted && !window.__FEED_MOUNTED;

        if (looksUninitialized) {
          loadPanel(path);
        }
      });
    }
  }

  // Markers your SPA can set when it mounts so we can detect it
  window.__markFeedMounted = function () {
    const root = document.querySelector("#feed-root");
    if (root) root.__mounted = true;
    window.__FEED_MOUNTED = true;
  };

  // Start!
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
