// styles.js — inject component-scoped CSS once
export function injectCommentsCSS() {
  if (document.getElementById("feed-comments-style")) return;
  const style = document.createElement("style");
  style.id = "feed-comments-style";
  style.textContent = `
    .btn-xxs{ --bs-btn-padding-y:.10rem; --bs-btn-padding-x:.35rem; --bs-btn-font-size:.70rem; --bs-btn-border-radius:.25rem; line-height:1; }
    .fcm-comment{ position:relative; }
    .fcm-replies{ margin-left:38px; border-left:2px solid #e5e7eb; padding-left:10px; }
    .fcm-replies.collapsed{ display:none; }
    .fcm-inline-reply{ border:1px solid #e5e7eb; border-radius:.5rem; padding:.5rem; margin-top:.5rem; background:#f9fafb; }
    .fcm-inline-actions{ display:flex; gap:.5rem; margin-top:.4rem; }
    .fcm-inline-edit{ border:1px solid #e5e7eb; border-radius:.5rem; padding:.6rem; margin-top:.5rem; background:#fff; }
    .fcm-inline-edit .edit-actions{ display:flex; gap:.5rem; margin-top:.5rem; }
    .fcm-inline-edit .edit-attach-bar{ display:flex; flex-wrap:wrap; gap:.4rem; margin-top:.35rem; }
    .comp-attach-input{ display:none; }
    .comp-attach-btn{ display:inline-flex; align-items:center; gap:.4rem; }
    .comp-thumb{ position:relative; width:84px; height:84px; border-radius:.5rem; overflow:hidden; background:#f6f7f9; border:1px solid #e5e7eb; }
    .comp-thumb img{ width:100%; height:100%; object-fit:cover; display:block; }
    .comp-thumb .comp-x{ position:absolute; top:4px; right:4px; width:22px; height:22px; display:flex; align-items:center; justify-content:center; border-radius:999px; background:rgba(0,0,0,.5); color:#fff; font-size:12px; cursor:pointer; }
    .comp-thumb[data-uploading="1"]::after{ content:""; position:absolute; inset:0; background:linear-gradient(90deg, rgba(0,0,0,.0), rgba(0,0,0,.1), rgba(0,0,0,.0)); animation: comp-upload 1s linear infinite; }
    @keyframes comp-upload{ 0%{transform:translateX(-100%)} 100%{transform:translateX(100%)} }
    .comp-chip{ display:inline-flex; align-items:center; gap:.4rem; padding:.35rem .6rem; border-radius:999px; font-size:.8rem; background:#f3f4f6; border:1px solid #e5e7eb; }
    .comp-chip .chip-x{ width:18px; height:18px; display:flex; align-items:center; justify-content:center; border-radius:999px; background:#e5e7eb; cursor:pointer; }
  `;
  document.head.appendChild(style);
}
