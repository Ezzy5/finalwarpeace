// app/static/js/boot_calendar.js
(function () {
  if (window.__CAL_AUTOboot) return;
  window.__CAL_AUTOboot = true;

  // Call this when CalendarPanel is present
  function tryMountCalendarPanel() {
    var host = document.querySelector('#CalendarPanel[data-init="mountCallendarPanel"]');
    if (!host) return;

    // Avoid double-initialization per panel instance
    if (host.__calMounted) return;
    host.__calMounted = true;

    // panel.html defines window.mountCallendarPanel; if not loaded yet, wait briefly
    function boot() {
      if (typeof window.mountCallendarPanel === 'function') {
        try { window.mountCallendarPanel(); } catch (e) { console.error('Calendar mount error:', e); }
      } else {
        // Try again a bit later (scripts may still be adding window.CalendarApp etc.)
        setTimeout(boot, 30);
      }
    }
    boot();
  }

  // Run on normal initial load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tryMountCalendarPanel);
  } else {
    tryMountCalendarPanel();
  }

  // MutationObserver — if your SPA injects the calendar markup later, we’ll catch it
  var mo = new MutationObserver(function (mutations) {
    for (var m of mutations) {
      if (m.type !== 'childList' || !m.addedNodes) continue;
      for (var n of m.addedNodes) {
        if (!(n instanceof HTMLElement)) continue;
        // Direct match
        if (n.id === 'CalendarPanel' && n.getAttribute('data-init') === 'mountCallendarPanel') {
          tryMountCalendarPanel();
          return;
        }
        // Or it’s inside a container that got injected
        if (n.querySelector && n.querySelector('#CalendarPanel[data-init="mountCallendarPanel"]')) {
          tryMountCalendarPanel();
          return;
        }
      }
    }
  });
  mo.observe(document.documentElement || document.body, { childList: true, subtree: true });

  // Hooks for common SPA libraries (fire tryMount whenever they finish navigation)
  window.addEventListener('popstate', tryMountCalendarPanel);
  document.addEventListener('pjax:end', tryMountCalendarPanel);
  document.addEventListener('htmx:afterSwap', tryMountCalendarPanel);
  document.addEventListener('turbo:load', tryMountCalendarPanel);
  document.addEventListener('turbolinks:load', tryMountCalendarPanel);

  // Custom hook you can dispatch yourself after injecting HTML:
  document.addEventListener('app:navigation:done', tryMountCalendarPanel);
})();
