// FULL FIXED feed-components.js WITH OPTION C (inline permissions picker)
// --------------------------------------------------------------
// This version adds an inline permissions section inside the composer:
//   - A dropdown: Audience = All users OR Selected users
//   - When "Selected users" → shows a multi-select user picker (search API)
//   - On publish → sends audience_type + allowed_user_ids (IDs only)
//   - In post card → shows "Creator Name  >  To all employees" OR
//                    "Creator Name  >  Име Презиме, Име2 Презиме2, +N more"
//   - "+N more" opens a rounded dropdown listing all tagged users
// --------------------------------------------------------------

import {
  esc, el, toast, btnBusy,
  apiUpload, apiPost, apiPatch, apiDelete,
  openLightbox, setLikeButtonState, setPinButtonState,
  updatePinStateEverywhere, removePinnedCardGlobal,
  formatDateTime,
} from "./feed-utils.js";

// -------------------------------------------------------
// Lazy load comments modal
// -------------------------------------------------------
async function ensureOpenCommentsModal() {
  if (typeof window.openCommentsModal === "function") return window.openCommentsModal;
  const publicJsUrl = "/feed/static/feed-comments.js";

  try {
    const res = await fetch(publicJsUrl, { credentials: "same-origin", cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();

    if (/^\s*<!doctype html>|^\s*<html[\s>]/i.test(text)) throw new Error("HTML returned");

    const blobUrl = URL.createObjectURL(new Blob([text], { type: "text/javascript" }));
    try {
      await import(blobUrl + `#cb=${Date.now()}`);
    } finally {
      URL.revokeObjectURL(blobUrl);
    }

    if (typeof window.openCommentsModal === "function") return window.openCommentsModal;
  } catch {}

  await new Promise((resolve, reject) => {
    let tag = document.querySelector(`script[data-dyn-load="${publicJsUrl}"]`);
    if (!tag) {
      tag = document.createElement("script");
      tag.src = publicJsUrl + "?cb=" + Date.now();
      tag.defer = true;
      tag.async = true;
      tag.setAttribute("data-dyn-load", publicJsUrl);
      document.head.appendChild(tag);
    }
    tag.addEventListener("load", resolve, { once: true });
    tag.addEventListener("error", () => reject(new Error("feed-comments.js failed")), { once: true });
  });

  if (typeof window.openCommentsModal === "function") return window.openCommentsModal;
  return () => alert("Коментарите не се достапни.");
}

// -------------------------------------------------------
// Helpers
// -------------------------------------------------------
function buildHTMLFromParts(text, uploadPaths, extraBlocks = []) {
  let html = (text || "").trim();
  if (html) {
    html = esc(html).replace(/\n{2,}/g, "</p><p>").replace(/\n/g, "<br>");
    html = `<p>${html}</p>`;
  } else html = "";

  if (uploadPaths && uploadPaths.length) {
    const blocks = uploadPaths
      .map((p) => {
        const url = `/static/${p.replace(/^\/?static\/?/, "")}`;
        const isImg = /\.(png|jpe?g|gif|webp|bmp|svg)$/i.test(p);
        return isImg
          ? `<div class="mt-2"><img src="${esc(url)}" style="max-width:100%;border-radius:8px;"></div>`
          : `<div class="mt-1"><a href="${esc(url)}" target="_blank"><i class="bi bi-paperclip me-1"></i>${esc(p.split("/").pop() || "file")}</a></div>`;
      })
      .join("");
    html += blocks;
  }

  if (extraBlocks.length) html += extraBlocks.join("");
  return html || "<p></p>";
}

// =======================================================
// COMPOSER — ADD INLINE AUDIENCE PICKER (OPTION C)
// =======================================================
export function composerCard(AVATAR_FALLBACK, FEED_API, prependPost) {
  let uploadPaths = [];
  let pendingThumbs = 0;

  // STATE: permissions
  let audienceType = "all"; // "all" or "users"
  // selectedUsers: array of { id, name }
  let selectedUsers = [];

  const node = el(`
    <div class="card shadow-sm border-0 rounded-4 mb-3 feed-card">
      <div class="card-body">
        <div class="d-flex align-items-center mb-3">
          <img id="feedComposerAvatar" src="${esc(window.CURRENT_USER_AVATAR_URL || AVATAR_FALLBACK)}" width="40" height="40" class="rounded-circle border me-2">
          <div class="fw-semibold">Нова објава</div>
        </div>

        <div class="mb-2"><input class="form-control" placeholder="Наслов (опционално)" data-role="title"></div>
        <div class="mb-3"><textarea class="form-control" rows="5" placeholder="Што има ново?" data-role="html"></textarea></div>

        <!-- PERMISSIONS SECTION -->
        <div class="mb-3 p-2 border rounded-3 bg-light">
          <label class="fw-semibold mb-2">Кој може да ја види објавата?</label>
          <select class="form-select mb-2" data-role="audience-select">
            <option value="all">Сите корисници</option>
            <option value="users">Само одбрани корисници</option>
          </select>

          <div data-role="user-picker-section" style="display:none;">
            <input class="form-control mb-2" placeholder="Барај корисник..." data-role="user-search">
            <div class="d-flex flex-column gap-1 mb-2" data-role="user-search-results"></div>
            <div class="d-flex gap-2 flex-wrap" data-role="selected-users"></div>
          </div>
        </div>

        <div class="comp-attach-bar mb-3">
          <input type="file" multiple class="comp-attach-input" id="compUploadAny">
          <button class="btn btn-outline-secondary comp-attach-btn" id="compBtnUpload" type="button">
            <i class="bi bi-paperclip"></i><span> Додај датотека/фото</span>
          </button>
          <div class="d-flex gap-2 flex-wrap" id="compThumbs"></div>
          <div class="d-flex gap-2 flex-wrap" id="compChips"></div>
        </div>

        <button class="btn btn-primary" data-action="publish"><i class="bi bi-send me-1"></i>Објави</button>
      </div>
    </div>`);

  const $ = (s) => node.querySelector(s);

  // ---- AUDIENCE PICKER UI ----
  const audienceSelect = $("[data-role='audience-select']");
  const pickerSection  = $("[data-role='user-picker-section']");
  const userSearch     = $("[data-role='user-search']");
  const userResults    = $("[data-role='user-search-results']");
  const selectedBox    = $("[data-role='selected-users']");

  audienceSelect.addEventListener("change", () => {
    audienceType = audienceSelect.value;
    pickerSection.style.display = audienceType === "users" ? "block" : "none";
  });

  // Search users (using /users/api/list)
  async function searchUsers(q) {
    if (!q.trim()) return [];
    try {
      const url = `/users/api/list?search=${encodeURIComponent(q)}`;
      const res = await fetch(url, { credentials: "same-origin" });
      if (!res.ok) return [];
      const data = await res.json();
      return data.items || [];
    } catch {
      return [];
    }
  }

  userSearch.addEventListener("input", async () => {
    const q = userSearch.value.trim();
    const items = await searchUsers(q);
    userResults.innerHTML = "";

    items.forEach((u) => {
      // skip if already selected
      if (selectedUsers.some((s) => s.id === u.id)) return;
      const fullName = u.full_name || ((u.first_name || "") + " " + (u.last_name || "")).trim();
      const row = el(
        `<button class="btn btn-light text-start w-100">${esc(fullName || `User #${u.id}`)}</button>`
      );
      row.onclick = () => {
        selectedUsers.push({ id: u.id, name: fullName || `User #${u.id}` });
        renderSelectedUsers();
        userResults.innerHTML = "";
        userSearch.value = "";
      };
      userResults.appendChild(row);
    });
  });

  function renderSelectedUsers() {
    selectedBox.innerHTML = "";
    selectedUsers.forEach((u) => {
      const chip = el(
        `<span class="badge bg-primary p-2">${esc(u.name)} <i class="bi bi-x ms-1" role="button"></i></span>`
      );
      chip.querySelector("i").onclick = () => {
        selectedUsers = selectedUsers.filter((x) => x.id !== u.id);
        renderSelectedUsers();
      };
      selectedBox.appendChild(chip);
    });
  }

  // ---- ATTACH HANDLERS (UNCHANGED) ----
  const inputAny = $("#compUploadAny");
  const btnUpload = $("#compBtnUpload");
  const thumbs = $("#compThumbs");
  const chips = $("#compChips");
  btnUpload.onclick = () => inputAny.click();

  inputAny.addEventListener("change", async () => {
    const files = Array.from(inputAny.files || []);
    if (!files.length) return;

    for (const f of files) {
      const isImg = (f.type || "").startsWith("image/");
      if (isImg) {
        const url = URL.createObjectURL(f);
        pendingThumbs++;
        const th = el(
          `<div class='comp-thumb' data-uploading><img src='${esc(
            url
          )}'><div class='comp-x'><i class='bi bi-x'></i></div></div>`
        );
        thumbs.appendChild(th);

        try {
          const res = await apiUpload(`${FEED_API.replace(/\/$/, "")}/upload`, [f]);
          const it = (res.items || [])[0];
          if (it?.path) {
            uploadPaths.push(it.path);
            th.removeAttribute("data-uploading");
            th.querySelector("img").src = it.preview_url || it.file_url || url;
            th.querySelector(".comp-x").onclick = () => {
              uploadPaths = uploadPaths.filter((p) => p !== it.path);
              th.remove();
            };
          } else th.remove();
        } catch {
          th.remove();
        } finally {
          pendingThumbs--;
          URL.revokeObjectURL(url);
        }
      } else {
        try {
          const res = await apiUpload(`${FEED_API.replace(/\/$/, "")}/upload`, [f]);
          const it = (res.items || [])[0];
          if (it?.path) {
            uploadPaths.push(it.path);
            const chip = el(
              `<span class='comp-chip'><i class='bi bi-file-earmark'></i> ${esc(
                f.name
              )} <i class='bi bi-x ms-1'></i></span>`
            );
            chip.querySelector("i").onclick = () => {
              uploadPaths = uploadPaths.filter((p) => p !== it.path);
              chip.remove();
            };
            chips.appendChild(chip);
          }
        } catch {}
      }
    }
    inputAny.value = "";
  });

  // ---- PUBLISH ----
  $("[data-action='publish']").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    const title = ($("[data-role='title']").value || "").trim();
    const html = ($("[data-role='html']").value || "").trim();

    if (!html && !title && uploadPaths.length === 0) return;
    if (pendingThumbs > 0) return toast("Почекајте да заврши прикачувањето…");

    // Prepare permissions
    const payload = {
      title,
      html,
      upload_paths: uploadPaths,
      audience_type: audienceType,
      // send only IDs to backend
      allowed_user_ids: audienceType === "users" ? selectedUsers.map((u) => u.id) : [],
    };

    btnBusy(btn, true);
    try {
      const created = await apiPost(FEED_API, payload);

      // Reset composer
      $("[data-role='title']").value = "";
      $("[data-role='html']").value = "";
      thumbs.innerHTML = "";
      chips.innerHTML = "";
      uploadPaths = [];

      // reset permissions
      audienceType = "all";
      selectedUsers = [];
      audienceSelect.value = "all";
      pickerSection.style.display = "none";
      renderSelectedUsers();

      prependPost(created);
    } catch {
      toast("Неуспешна објава.");
    } finally {
      btnBusy(btn, false);
    }
  });

  // Live avatar update
  window.addEventListener("user:avatar-updated", (ev) => {
    const url = ev?.detail?.avatarUrl;
    const img = node.querySelector("#feedComposerAvatar");
    if (url && img) img.src = url;
  });

  return node;
}

/* -------------------------------------------------------
   Full post editor
   ------------------------------------------------------- */
export function makePostFullEditor(postNode, p, FEED_API) {
  const container = document.createElement("div");
  container.innerHTML = p.html || "";
  const imgs = Array.from(container.querySelectorAll("img"))
    .map((img) => ({ url: img.getAttribute("src") || "" }))
    .filter((x) => x.url);
  const files = Array.from(container.querySelectorAll("a"))
    .map((a) => ({ url: a.getAttribute("href") || "", name: (a.textContent || "").trim() }))
    .filter((x) => x.url);

  let keptImages = imgs.slice();
  let keptFiles = files.slice();
  let newUploadPaths = [];
  let pending = 0;

  const editor = el(`
    <div class="card border-0 rounded-4 my-3" data-role="post-full-editor">
      <div class="card-body">
        <div class="mb-2"><input class="form-control" placeholder="Наслов (опционално)" data-role="title"></div>
        <div class="mb-3"><textarea class="form-control" rows="5" placeholder="Измени содржина..." data-role="html"></textarea></div>

        <div class="comp-attach-bar mb-3">
          <input type="file" multiple class="comp-attach-input" data-role="file">
          <button class="btn btn-outline-secondary comp-attach-btn" data-role="file-btn" type="button">
            <i class="bi bi-paperclip"></i><span>Додај датотека/фото</span>
          </button>
          <div class="d-flex gap-2 flex-wrap" data-role="thumbs"></div>
          <div class="d-flex gap-2 flex-wrap" data-role="chips"></div>
        </div>

        <div class="d-flex gap-2">
          <button class="btn btn-primary" data-action="save"><i class="bi bi-check2-circle me-1"></i>Зачувај</button>
          <button class="btn btn-light" data-action="cancel">Откажи</button>
        </div>
      </div>
    </div>`);

  const tmp = document.createElement("div");
  tmp.innerHTML = p.html || "";
  tmp.querySelectorAll("img").forEach((n) => n.remove());
  tmp.querySelectorAll("a").forEach((n) => n.remove());
  editor.querySelector('[data-role="title"]').value = p.title || "";
  editor.querySelector('[data-role="html"]').value = (tmp.textContent || "").trim();

  const fileInput = editor.querySelector('[data-role="file"]');
  const fileBtn = editor.querySelector('[data-role="file-btn"]');
  const thumbs = editor.querySelector('[data-role="thumbs"]');
  const chips = editor.querySelector('[data-role="chips"]');
  const btnSave = editor.querySelector('[data-action="save"]');
  const btnCancel = editor.querySelector('[data-action="cancel"]');

  function renderExisting() {
    thumbs.innerHTML = "";
    chips.innerHTML = "";
    keptImages.forEach((it, idx) => {
      const t = el(`
        <div class="comp-thumb">
          <img src="${esc(it.url)}" alt="">
          <div class="comp-x" title="Отстрани"><i class="bi bi-x"></i></div>
        </div>`);
      t.querySelector(".comp-x").onclick = () => {
        keptImages.splice(idx, 1);
        renderExisting();
      };
      thumbs.appendChild(t);
    });
    keptFiles.forEach((it, idx) => {
      const c = el(`
        <span class="comp-chip">
          <i class="bi bi-file-earmark"></i>
          <span>${esc(it.name || (it.url.split("/").pop() || "file"))}</span>
          <span class="chip-x" title="Отстрани"><i class="bi bi-x"></i></span>
        </span>`);
      c.querySelector(".chip-x").onclick = () => {
        keptFiles.splice(idx, 1);
        renderExisting();
      };
      chips.appendChild(c);
    });
  }
  renderExisting();

  function addThumb(src, { uploading = false, onRemove } = {}) {
    const t = el(`
      <div class="comp-thumb" ${uploading ? 'data-uploading="1"' : ""}>
        <img src="${esc(src)}" alt="">
        <div class="comp-x" title="Отстрани"><i class="bi bi-x"></i></div>
      </div>`);
    t.querySelector(".comp-x").onclick = () => {
      onRemove && onRemove();
      t.remove();
    };
    thumbs.appendChild(t);
    return t;
  }
  function addChip(name, { onRemove } = {}) {
    const c = el(`
      <span class="comp-chip">
        <i class="bi bi-file-earmark"></i>
        <span>${esc(name)}</span>
        <span class="chip-x" title="Отстрани"><i class="bi bi-x"></i></span>
      </span>`);
    c.querySelector(".chip-x").onclick = () => {
      onRemove && onRemove();
      c.remove();
    };
    chips.appendChild(c);
    return c;
  }

  fileBtn.onclick = () => fileInput.click();
  fileInput.onchange = async () => {
    const files = Array.from(fileInput.files || []);
    if (!files.length) return;
    for (const f of files) {
      const isImg = (f.type || "").startsWith("image/");
      if (isImg) {
        const url = URL.createObjectURL(f);
        pending++;
        const th = addThumb(url, { uploading: true });
        try {
          const res = await apiUpload(`${FEED_API.replace(/\/$/, "")}/upload`, [f]);
          const it = (res.items || [])[0];
          if (it?.path) {
            newUploadPaths.push(it.path);
            th.removeAttribute("data-uploading");
            th.querySelector("img").src = it.preview_url || it.file_url || url;
            th.querySelector(".comp-x").onclick = () => {
              newUploadPaths = newUploadPaths.filter((p) => p !== it.path);
              th.remove();
            };
          } else {
            th.remove();
            toast("Неуспешно прикачување на датотека.");
          }
        } catch {
          th.remove();
          toast("Неуспешно прикачување на датотека.");
        } finally {
          pending--;
          URL.revokeObjectURL(url);
        }
      } else {
        try {
          const res = await apiUpload(`${FEED_API.replace(/\/$/, "")}/upload`, [f]);
          const it = (res.items || [])[0];
          if (it?.path) {
            newUploadPaths.push(it.path);
            addChip(it.file_name || f.name, {
              onRemove: () => {
                newUploadPaths = newUploadPaths.filter((p) => p !== it.path);
              },
            });
          } else {
            toast("Неуспешно прикачување на датотека.");
          }
        } catch {
          toast("Неуспешно прикачување на датотека.");
        }
      }
    }
    fileInput.value = "";
  };

  const doSave = async () => {
    if (pending > 0) {
      toast("Почекајте да заврши прикачувањето.");
      return;
    }
    const newTitle = (editor.querySelector('[data-role="title"]').value || "").trim();
    const text = (editor.querySelector('[data-role="html"]').value || "").trim();

    const extraBlocks = [];
    keptImages.forEach((it) => {
      extraBlocks.push(
        `<div class="mt-2"><img src="${esc(
          it.url
        )}" alt="" style="max-width:100%;height:auto;border:1px solid #e5e7eb;border-radius:8px;"></div>`
      );
    });
    keptFiles.forEach((it) => {
      const name = esc(it.name || (it.url.split("/").pop() || "file"));
      extraBlocks.push(
        `<div class="mt-1"><a href="${esc(
          it.url
        )}" target="_blank" rel="noopener"><i class="bi bi-paperclip me-1"></i>${name}</a></div>`
      );
    });

    const newHtml = buildHTMLFromParts(text, newUploadPaths, extraBlocks);

    btnBusy(btnSave, true);
    try {
      await apiPatch(`${FEED_API.replace(/\/$/, "")}/${p.id}`, { title: newTitle, html: newHtml });

      const titleEl = postNode.querySelector("h5.mb-1");
      const bodyEl = postNode.querySelector(".feed-html");

      if (titleEl && newTitle) titleEl.textContent = newTitle;
      if (titleEl && !newTitle) titleEl.remove();
      if (!titleEl && newTitle) {
        const newTitleEl = el(`<h5 class="mb-1"></h5>`);
        newTitleEl.textContent = newTitle;
        postNode.querySelector(".card-body").insertBefore(newTitleEl, bodyEl);
      }
      if (bodyEl) bodyEl.innerHTML = newHtml;

      const imageUrls = Array.from(postNode.querySelectorAll(".feed-photo img")).map((i) => i.src);
      postNode.querySelectorAll(".feed-photo").forEach((ph, i) => {
        ph.addEventListener("click", () => openLightbox(imageUrls, i));
      });

      postNode.querySelector('[data-role="post-original"]').style.display = "";
      editor.remove();
    } catch (e) {
      if (e.status === 401 || e.status === 403) toast("Немате дозвола да уредувате оваа објава.");
      else toast("Неуспешно уредување на објавата.");
    } finally {
      btnBusy(btnSave, false);
    }
  };

  btnSave.onclick = doSave;
  btnCancel.onclick = () => {
    postNode.querySelector('[data-role="post-original"]').style.display = "";
    editor.remove();
  };

  return editor;
}

/* -------------------------------------------------------
   Post card
   ------------------------------------------------------- */
export function postCard(p, AVATAR_FALLBACK, FEED_API, { inPinnedStrip = false, callbacks = {} } = {}) {
  const title = p.title ? `<h5 class="mb-1">${esc(p.title)}</h5>` : "";
  const authorName = p.author?.full_name ? esc(p.author.full_name) : "Корисник";
  const avatar = p.author?.avatar_url || AVATAR_FALLBACK;
  const reactions = p.reactions_summary?.["👍"] || 0;
  const userReacted = !!p.user_reacted;
  const userPinned = !!p.user_pinned;

  const imageUrls = (p.attachments || [])
    .filter((a) => (a.file_type || "").startsWith("image"))
    .map((a) => a.preview_url || a.file_url)
    .filter(Boolean);

  const nonImages = (p.attachments || []).filter((a) => !(a.file_type || "").startsWith("image"));

  // ✅ absolute time in Europe/Skopje
  const whenAbs = formatDateTime(p.created_at);

  // ---- audience/tagged users label (same line as author) ----
  let audienceLabel = "";
  let dropdownHtml = "";
  let extraCount = 0;
  const maxVisibleTagged = 3;
  let allTaggedNames = [];

  if (p.audience_type === "users" && Array.isArray(p.allowed_users) && p.allowed_users.length) {
    const names = p.allowed_users
      .map((u) => u && (u.full_name || "").trim())
      .filter((n) => n && n.length > 0);

    allTaggedNames = names.slice();

    if (names.length) {
      const visible = names.slice(0, maxVisibleTagged);
      extraCount = Math.max(0, names.length - visible.length);
      audienceLabel = `> ${visible.join(", ")}`;

      if (extraCount > 0) {
        dropdownHtml = `
          <div class="feed-tagged-dropdown shadow-sm rounded-3 border bg-white small py-2 px-3"
               data-role="tagged-dropdown"
               style="display:none; position:absolute; z-index:20; top:100%; left:0; margin-top:4px; min-width:220px; background-color:#fff; border-radius:0.75rem;">
            ${names.map((n) => `<div class="py-1">${esc(n)}</div>`).join("")}
          </div>`;
      }
    }
  } else {
    // default label for all employees
    audienceLabel = "> To all employees";
  }

  let audienceHtml = "";
  if (audienceLabel) {
    if (extraCount > 0) {
      audienceHtml = `
        <span class="text-muted small ms-1">
          ${esc(audienceLabel)}
          <button type="button"
                  class="btn btn-link btn-sm p-0 align-baseline"
                  data-role="tagged-more">
            +${extraCount} more
          </button>
        </span>`;
    } else {
      audienceHtml = `<span class="text-muted small ms-1">${esc(audienceLabel)}</span>`;
    }
  }

  const node = el(`
    <article class="card shadow-sm border-0 rounded-4 mb-3 feed-card" data-post-id="${p.id}">
      <div class="card-body" data-role="post-original">
        <div class="d-flex align-items-center mb-2">
          <img src="${esc(
            avatar
          )}" width="40" height="40" class="rounded-circle border me-2" data-author-id="${esc(
    p.author?.id || ""
  )}" onerror="this.src='${esc(AVATAR_FALLBACK)}'">
          <div class="me-auto">
            <div class="fw-semibold d-flex align-items-center">
              <span>${authorName}</span>
              <div class="position-relative d-inline-block ms-1" data-role="tagged-wrapper">
                ${audienceHtml}
                ${dropdownHtml}
              </div>
            </div>
            <div class="text-muted small">
              <time datetime="${esc(p.created_at || "")}">${esc(whenAbs)}</time>
            </div>
          </div>
          <button class="btn btn-sm btn-outline-secondary me-1" data-action="pin" data-pinned="${
            userPinned ? "1" : "0"
          }" title="${userPinned ? "Откачи" : "Закачи"}" aria-label="${
    userPinned ? "Откачи" : "Закачи"
  }">
            <i class="bi ${userPinned ? "bi-pin-angle-fill" : "bi-pin-angle"}"></i>
            <span class="visually-hidden" data-role="pin-text">${
              userPinned ? "Откачи" : "Закачи"
            }</span>
          </button>
        </div>

        ${title}
        <div class="mb-3 feed-html">${p.html || ""}</div>

        ${
          imageUrls.length
            ? `
          <div class="feed-gallery">
            ${imageUrls
              .map(
                (u, i) =>
                  `<div class="feed-photo" data-idx="${i}"><img src="${esc(u)}" alt=""></div>`
              )
              .join("")}
          </div>`
            : ""
        }

        ${
          nonImages.length
            ? `
          <div class="d-flex flex-column gap-1 mb-2">
            ${nonImages
              .map(
                (a) => `
              <a class="small text-decoration-none" href="${esc(
                a.file_url
              )}" target="_blank" rel="noopener">
                <i class="bi bi-paperclip me-1"></i>${esc(a.file_name || a.file_url || "file")}
              </a>`
              )
              .join("")}
          </div>`
            : ""
        }

        <div class="d-flex align-items-center gap-2 flex-wrap">
          <button class="btn btn-outline-primary" data-action="react" data-emoji="👍" data-reacted="${
            userReacted ? "1" : "0"
          }">
            <i class="bi bi-hand-thumbs-up"></i>
            <span class="ms-1">Ми се допаѓа</span>
            <span class="badge bg-primary-subtle text-primary ms-1" data-role="reactions">${reactions}</span>
          </button>
          <button class="btn btn-outline-secondary" data-action="comment">
            <i class="bi bi-chat-dots"></i>
            <span class="ms-1">Коментар</span>
          </button>

          <div class="dropdown">
            <button class="btn btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">More</button>
            <ul class="dropdown-menu dropdown-menu-end">
              <li><a class="dropdown-item" href="#" data-action="post-edit">Уреди</a></li>
              <li><a class="dropdown-item text-danger" href="#" data-action="post-delete">Избриши</a></li>
            </ul>
          </div>
        </div>
      </div>
    </article>`);

  // --- Tagged users dropdown behavior ---
  const moreBtn = node.querySelector('[data-role="tagged-more"]');
  const dropdown = node.querySelector('[data-role="tagged-dropdown"]');
  if (moreBtn && dropdown) {
    let open = false;
    let docHandler = null;

    const openDropdown = () => {
      if (open) return;
      open = true;
      dropdown.style.display = "block";
      dropdown.style.opacity = "0";
      dropdown.style.transform = "translateY(-4px)";
      dropdown.style.transition = "opacity 150ms ease-out, transform 150ms ease-out";
      requestAnimationFrame(() => {
        dropdown.style.opacity = "1";
        dropdown.style.transform = "translateY(0)";
      });

      docHandler = (ev) => {
        if (!dropdown.contains(ev.target) && !moreBtn.contains(ev.target)) {
          closeDropdown();
        }
      };
      document.addEventListener("click", docHandler);
    };

    const closeDropdown = () => {
      if (!open) return;
      open = false;
      dropdown.style.opacity = "0";
      dropdown.style.transform = "translateY(-4px)";
      const onEnd = () => {
        dropdown.style.display = "none";
        dropdown.removeEventListener("transitionend", onEnd);
      };
      dropdown.addEventListener("transitionend", onEnd);
      if (docHandler) {
        document.removeEventListener("click", docHandler);
        docHandler = null;
      }
    };

    moreBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (open) closeDropdown();
      else openDropdown();
    });
  }

  // Fallback dropdown if Bootstrap JS missing
  if (!window.bootstrap?.Dropdown) {
    node.querySelectorAll(".dropdown-toggle").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        const menu = btn.parentElement.querySelector(".dropdown-menu");
        menu?.classList.toggle("show");
        const off = (ev) => {
          if (!btn.parentElement.contains(ev.target)) menu?.classList.remove("show");
        };
        setTimeout(() => document.addEventListener("click", off, { once: true }), 0);
      });
    });
  }

  // Lightbox
  if (imageUrls.length) {
    node.querySelectorAll(".feed-photo").forEach((ph) =>
      ph.addEventListener("click", () =>
        openLightbox(imageUrls, parseInt(ph.dataset.idx, 10) || 0)
      )
    );
  }

  // Like
  setLikeButtonState(node.querySelector('[data-action="react"]'), userReacted);
  node.querySelector('[data-action="react"]').addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    e.preventDefault();
    e.stopPropagation();
    btnBusy(btn, true);
    try {
      const res = await apiPost(`${FEED_API.replace(/\/$/, "")}/${p.id}/react`, { emoji: "👍" });
      const badge = node.querySelector('[data-role="reactions"]');
      if (badge && typeof res?.counts?.["👍"] === "number") badge.textContent = res.counts["👍"];
      setLikeButtonState(btn, !!res.reacted);
    } finally {
      btnBusy(btn, false);
    }
  });

  // Comment — lazy resolve modal & open
  node.querySelector('[data-action="comment"]').addEventListener("click", async (ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    try {
      const openModal = await ensureOpenCommentsModal();
      openModal({ FEED_API, postId: p.id, focus: "comments" });
    } catch (_e) {
      alert("Коментарите не се достапни (feed-comments.js).");
    }
  });

  // Pin
  setPinButtonState(node.querySelector('[data-action="pin"]'), userPinned);
  node.querySelector('[data-action="pin"]').addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    e.preventDefault();
    e.stopPropagation();
    const willPin = btn.getAttribute("data-pinned") !== "1";
    btnBusy(btn, true);
    try {
      const res = await apiPost(`${FEED_API.replace(/\/$/, "")}/${p.id}/pin`, { pinned: willPin });
      const pinned = !!res.pinned;
      setPinButtonState(btn, pinned);
      updatePinStateEverywhere(p.id, pinned);
      if (pinned) {
        callbacks.onPinAdd && callbacks.onPinAdd({ ...p, user_pinned: true });
      } else {
        callbacks.onPinRemove && callbacks.onPinRemove(p.id);
      }
    } finally {
      btnBusy(btn, false);
    }
  });

  // Edit / Delete
  node.querySelector('a[data-action="post-edit"]').addEventListener("click", (e) => {
    e.preventDefault();
    if (node.querySelector('[data-role="post-full-editor"]')) return;
    const orig = node.querySelector('[data-role="post-original"]');
    const editor = makePostFullEditor(node, p, FEED_API);
    orig.style.display = "none";
    node.appendChild(editor);
    editor.querySelector("textarea")?.focus();
  });

  node.querySelector('a[data-action="post-delete"]').addEventListener("click", async (e) => {
    e.preventDefault();
    if (!confirm("Дали сте сигурни дека сакате да ја избришете објавата?")) return;
    try {
      await apiDelete(`${FEED_API.replace(/\/$/, "")}/${p.id}`);
      node.remove();
      removePinnedCardGlobal(p.id);
    } catch (err) {
      if (err.status === 401 || err.status === 403) toast("Немате дозвола да ја избришете оваа објава.");
      else toast("Неуспешно бришење на објавата.");
    }
  });

  return node;
}
