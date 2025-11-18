// app/callendar/static/js/panelMount.js
(function(){
  // Dashboard SPA calls this after injecting the panel HTML.
  window.mountCallendarPanel = function(selector) {
    if (window.CalendarApp && typeof window.CalendarApp.init === 'function') {
      window.CalendarApp.init();
    } else {
      // If scripts haven't loaded yet, try a short deferred init.
      setTimeout(function(){
        if (window.CalendarApp && typeof window.CalendarApp.init === 'function') {
          window.CalendarApp.init();
        }
      }, 0);
    }
  };
})();
