// app/email/static/email_dnd.js
(function () {
  const HOST = document.getElementById("EmailPanel");
  if (!HOST) return;

  // Utility: find container state
  function getState() {
    const root = document.querySelector("#EmailPanel");
    const accEl = root && root.querySelector("[data-acc-id]");
    const accId = accEl ? accEl.getAttribute("data-acc-id") : null;
    const folderEl = root && root.querySelector("[data-current-folder]");
    const currentFolder = folderEl ? folderEl.getAttribute("data-current-folder") : "INBOX";
    return { accId, currentFolder };
  }

  // Drag source: message rows
  HOST.addEventListener("dragstart", function (e) {
    const row = e.target.closest("[data-uid]");
    if (!row) return;
    const { accId, currentFolder } = getState();
    const uid = row.getAttribute("data-uid");
    e.dataTransfer.setData("text/plain", JSON.stringify({ accId, uid, fromFolder: currentFolder }));
    e.dataTransfer.effectAllowed = "move";
    row.classList.add("dragging");
  });

  HOST.addEventListener("dragend", function (e) {
    const row = e.target.closest(".dragging");
    if (row) row.classList.remove("dragging");
  });

  // Drop targets: folder items
  HOST.addEventListener("dragover", function (e) {
    const folder = e.target.closest("[data-folder-name]");
    if (!folder) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    folder.classList.add("droptarget");
  });

  HOST.addEventListener("dragleave", function (e) {
    const folder = e.target.closest("[data-folder-name]");
    if (folder) folder.classList.remove("droptarget");
  });

  HOST.addEventListener("drop", async function (e) {
    const folder = e.target.closest("[data-folder-name]");
    if (!folder) return;
    e.preventDefault();
    folder.classList.remove("droptarget");

    let payload;
    try {
      payload = JSON.parse(e.dataTransfer.getData("text/plain") || "{}");
    } catch (_) {
      return;
    }
    const toFolder = folder.getAttribute("data-folder-name");
    if (!payload.accId || !payload.uid || !toFolder) return;

    const res = await fetch("/email/mail/move", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "fetch",
      },
      credentials: "same-origin",
      body: JSON.stringify({
        acc: Number(payload.accId),
        uid: String(payload.uid),
        from_folder: payload.fromFolder || "INBOX",
        to_folder: toFolder,
      }),
    });

    if (!res.ok) {
      const msg = await res.text().catch(() => "");
      alert("Move failed: " + msg);
      return;
    }

    // Remove the dragged row from the list for immediate feedback
    const row = HOST.querySelector('[data-uid="' + payload.uid + '"]');
    if (row && row.parentNode) row.parentNode.removeChild(row);
  });
})();
