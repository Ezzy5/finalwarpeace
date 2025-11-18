// Bridge your app's Drive picker to the Feed composer.
// Listens for:  feed:open-drive-picker  { detail: { multi: boolean } }
// Dispatches:   feed:drive-picked       { detail: { items: DriveItem[] } }
//
// DriveItem shape the Feed expects:
// { file_url: string, file_name?: string, file_type?: string, file_size?: number, preview_url?: string }

(function () {
  "use strict";
  if (window.__FEED_DRIVE_BRIDGE__) return;
  window.__FEED_DRIVE_BRIDGE__ = true;

  // Heuristics to turn various picker item shapes into Feed "DriveItem"
  function normalize(raw) {
    if (!raw) return null;

    // Common fields across different pickers
    const url =
      raw.file_url ||
      raw.webViewLink ||
      raw.alternateLink ||
      raw.url ||
      (raw.id ? `https://drive.google.com/file/d/${raw.id}/view` : "");

    if (!url) return null;

    const name = raw.file_name || raw.name || raw.title || "";
    const mime =
      raw.file_type || raw.mimeType || raw.type || guessMimeFromName(name) || "";

    // Prefer explicit preview/thumbnail; fallback to URL if it's an image
    const preview =
      raw.preview_url ||
      raw.thumbnailLink ||
      raw.iconUrl && mime.startsWith("image/") ? raw.iconUrl : "" ||
      (mime.startsWith("image/") ? url : "");

    const size = safeInt(
      raw.file_size ?? raw.sizeBytes ?? raw.size ?? raw.bytes ?? null
    );

    return {
      file_url: String(url),
      file_name: String(name || deriveNameFromUrl(url)),
      file_type: String(mime || "application/octet-stream"),
      file_size: size,
      preview_url: preview ? String(preview) : undefined
    };
  }

  function deriveNameFromUrl(u) {
    try { return decodeURIComponent(String(u).split("/").pop() || "file"); }
    catch { return "file"; }
  }

  function guessMimeFromName(name) {
    const ext = (name || "").split(".").pop()?.toLowerCase();
    if (!ext) return "";
    switch (ext) {
      case "png": return "image/png";
      case "jpg":
      case "jpeg": return "image/jpeg";
      case "webp": return "image/webp";
      case "gif": return "image/gif";
      case "pdf": return "application/pdf";
      case "doc": return "application/msword";
      case "docx": return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
      case "xls": return "application/vnd.ms-excel";
      case "xlsx": return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
      case "ppt": return "application/vnd.ms-powerpoint";
      case "pptx": return "application/vnd.openxmlformats-officedocument.presentationml.presentation";
      case "zip": return "application/zip";
      case "rar": return "application/vnd.rar";
      case "txt": return "text/plain";
      case "csv": return "text/csv";
      case "mp4": return "video/mp4";
      case "mp3": return "audio/mpeg";
      default: return "";
    }
  }

  function safeInt(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n : undefined;
  }

  async function pickWithDriveOpenPicker(multi) {
    // Mode A: Google-style API your app exposes:
    // window.Drive.openPicker({ multi, onSelect(items) })
    return new Promise((resolve) => {
      window.Drive.openPicker({
        multi: !!multi,
        onSelect: (items) => resolve(items || [])
      });
    });
  }

  async function pickWithOpenDrivePicker(multi) {
    // Mode B: Promise-based picker your app exposes:
    // window.openDrivePicker({ multi }) -> Promise<items>
    try {
      const items = await window.openDrivePicker({ multi: !!multi });
      return items || [];
    } catch {
      return [];
    }
  }

  async function runExternalPicker(multi) {
    if (window.Drive && typeof window.Drive.openPicker === "function") {
      return pickWithDriveOpenPicker(multi);
    }
    if (typeof window.openDrivePicker === "function") {
      return pickWithOpenDrivePicker(multi);
    }
    // No external picker available; return [] and let Feed's fallback mini-picker handle it.
    return [];
  }

  // The bridge: handle Feed's request to open a picker
  window.addEventListener("feed:open-drive-picker", async (ev) => {
    const multi = !!(ev.detail && ev.detail.multi);

    try {
      const rawItems = await runExternalPicker(multi);
      // If an external picker provided items quickly, send them back immediately.
      if (Array.isArray(rawItems) && rawItems.length) {
        const items = rawItems.map(normalize).filter(Boolean);
        window.dispatchEvent(new CustomEvent("feed:drive-picked", { detail: { items } }));
      }
      // If no items (user canceled or no picker), do nothing — Feed will show its mini picker fallback.
    } catch (err) {
      // Swallow errors to avoid breaking the Feed; fallback mini picker will still engage.
      console.warn("[feed-bridge] Drive picker error:", err);
    }
  });
})();
