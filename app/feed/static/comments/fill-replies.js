// fill-replies.js — populate replies recursively
import { renderCommentNode } from "./render-node.js";

export function fillReplies(parentNode, parentId, tree, autoExpand=false) {
  const repliesWrap = parentNode.querySelector('[data-role="replies"]');
  const toggleBtn = parentNode.querySelector('[data-action="toggle-replies"]');
  const chev = toggleBtn?.querySelector('[data-role="chev"]');
  const lbl  = toggleBtn?.querySelector('[data-role="lbl"]');
  const cnt  = toggleBtn?.querySelector('[data-role="cnt"]');
  const kids = tree.children.get(String(parentId)) || [];

  repliesWrap.innerHTML = "";

  if (!kids.length) { if (toggleBtn) toggleBtn.style.display = "none"; return; }

  kids.forEach(child => repliesWrap.appendChild(renderCommentNode(child)));

  if (toggleBtn && cnt && lbl && chev) {
    cnt.textContent = String(kids.length);
    toggleBtn.style.display = "";
    const collapsed = true;
    repliesWrap.classList.toggle("collapsed", collapsed);
    chev.className = collapsed ? 'bi bi-chevron-down' : 'bi bi-chevron-up';
    lbl.textContent = collapsed ? 'Прикажи одговори' : 'Скриј одговори';
  }

  kids.forEach(child => {
    const childNode = repliesWrap.querySelector(`[data-comment-id="${child.id}"]`);
    if (childNode) fillReplies(childNode, child.id, tree);
  });

  if (autoExpand && toggleBtn && repliesWrap.classList.contains("collapsed")) {
    repliesWrap.classList.remove("collapsed");
    if (chev) chev.className = 'bi bi-chevron-up';
    if (lbl)  lbl.textContent = 'Скриј одговори';
  }
}
