// tree.js — build nested tree from flat comments
import { parseReplyMeta } from "./parse.js";

export function buildCommentTree(items) {
  const byId = new Map(), children = new Map(), roots=[];
  const parsed = items.map(c => {
    const p = parseReplyMeta(c.html);
    return { ...c, _parsedHtml: p.html, _replyMeta: p.meta };
  });
  parsed.forEach(c => byId.set(String(c.id), c));
  parsed.forEach(c => {
    const parentId = c._replyMeta?.replyTo ? String(c._replyMeta.replyTo) : null;
    if (parentId && byId.has(parentId)) {
      if (!children.has(parentId)) children.set(parentId, []);
      children.get(parentId).push(c);
    } else {
      roots.push(c);
    }
  });
  const asc = (a,b)=> (new Date(a.created_at) - new Date(b.created_at));
  roots.sort(asc); for (const arr of children.values()) arr.sort(asc);
  return { roots, children };
}
