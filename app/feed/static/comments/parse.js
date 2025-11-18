// parse.js — extract reply meta & attachments
export function parseReplyMeta(html) {
  const div = document.createElement("div");
  div.innerHTML = html || "";
  const m = div.querySelector('span[data-reply-to]');
  if (!m) return { html: html || "", meta: null };
  const replyTo = m.getAttribute("data-reply-to");
  const author  = m.getAttribute("data-reply-author") || "";
  m.remove(); // keep html clean
  return { html: div.innerHTML, meta: { replyTo, author } };
}

export function extractAttachments(html) {
  const c = document.createElement("div"); c.innerHTML = html || "";
  const images = Array.from(c.querySelectorAll("img"))
    .map(i => ({ url: i.getAttribute("src") || "" }))
    .filter(x => x.url);
  const files = Array.from(c.querySelectorAll("a"))
    .map(a => ({ url: a.getAttribute("href") || "", name: (a.textContent || "").trim() }))
    .filter(x => x.url);
  return { images, files };
}
