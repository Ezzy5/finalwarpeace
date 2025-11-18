// build-html.js — create HTML payload for comments
import { esc } from "./dom.js";

export function buildCommentHTMLFromParts(text, uploadPaths, extraBlocks = [], replyTarget = null) {
  let html = (text||"").trim();
  if (html) {
    html = esc(html).replace(/\n{2,}/g,"</p><p>").replace(/\n/g,"<br>");
    html = `<p>${html}</p>`;
  } else html = "";

  if (replyTarget?.id) {
    const author = esc(replyTarget.authorName||"");
    html = `<span data-reply-to="${String(replyTarget.id)}" data-reply-author="${author}"></span>` + html;
  }

  if (uploadPaths?.length) {
    html += uploadPaths.map(p=>{
      const url = `/static/${p.replace(/^\/?static\/?/,'')}`;
      const isImg = /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(p);
      return isImg
        ? `<div class="mt-2"><img src="${esc(url)}" alt="" style="max-width:100%;height:auto;border:1px solid #e5e7eb;border-radius:8px;"></div>`
        : `<div class="mt-1"><a href="${esc(url)}" target="_blank" rel="noopener"><i class="bi bi-paperclip me-1"></i>${esc(p.split("/").pop()||"file")}</a></div>`;
    }).join("");
  }

  if (extraBlocks?.length) html += extraBlocks.join("");
  return html || "<p></p>";
}
