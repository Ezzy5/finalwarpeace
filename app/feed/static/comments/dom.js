// dom.js — tiny DOM + UI helpers
export const esc = (s) => String(s ?? "")
  .replace(/&/g, "&amp;").replace(/</g, "&lt;")
  .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");

export const el = (html) => {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
};

export const btnBusy = (btn, on) => {
  if (!btn) return;
  btn.disabled = !!on;
  let sp = btn.querySelector('[data-role="spinner"]');
  if (on) {
    if (!sp) {
      sp = document.createElement('span');
      sp.className = 'spinner-border spinner-border-sm me-1';
      sp.setAttribute('data-role','spinner');
      sp.setAttribute('role','status');
      sp.setAttribute('aria-hidden','true');
      btn.prepend(sp);
    }
  } else if (sp) sp.remove();
};

// Replace with your toast system if you have one
export const toast = (msg) => alert(msg);
