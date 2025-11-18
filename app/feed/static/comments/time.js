// time.js — absolute time only, Europe/Skopje
export const LOCALE = "mk-MK";            // or "en-GB"
export const TIMEZONE = "Europe/Skopje";

export function formatDateTime(isoUtcString) {
  try {
    const d = new Date(isoUtcString);
    return new Intl.DateTimeFormat(LOCALE, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: TIMEZONE,
    }).format(d);
  } catch {
    return String(isoUtcString || "");
  }
}

export function renderTimeHTML(isoUtcString, esc) {
  const absText = formatDateTime(isoUtcString);
  return `<time datetime="${esc(isoUtcString||"")}" title="${esc(absText)}">${esc(absText)}</time>`;
}
