// net.js — fetch wrappers (with CSRF + method override fallbacks)
const hdr = () => ({
  "X-Requested-With": "fetch",
});
const jsonHdr = () => ({
  "Content-Type": "application/json",
  "X-Requested-With": "fetch",
  "X-CSRFToken": window.CSRF_TOKEN || ""
});

export async function apiGet(url) {
  const r = await fetch(url, { credentials: "same-origin", headers: hdr() });
  if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
  return r.json();
}

export async function apiPost(url, body) {
  const r = await fetch(url, {
    method: "POST", credentials: "same-origin", headers: jsonHdr(),
    body: JSON.stringify(body || {})
  });
  if (!r.ok) {
    const t = await r.text().catch(()=>""); const e = new Error(`POST ${url} -> ${r.status}`); e.status=r.status; e.body=t; throw e;
  }
  return r.json().catch(() => ({}));
}

export async function apiPatch(url, body) {
  let r = await fetch(url, {
    method: "PATCH", credentials: "same-origin", headers: jsonHdr(),
    body: JSON.stringify(body || {})
  });
  if (r.status === 405 || r.status === 404) {
    r = await fetch(url, {
      method: "POST", credentials: "same-origin",
      headers: { ...jsonHdr(), "X-HTTP-Method-Override": "PATCH" },
      body: JSON.stringify(body || {})
    });
  }
  if (!r.ok) {
    const t = await r.text().catch(()=>""); const e = new Error(`PATCH ${url} -> ${r.status}`); e.status=r.status; e.body=t; throw e;
  }
  return r.json().catch(() => ({}));
}

export async function apiDelete(url) {
  let r = await fetch(url, { method:"DELETE", credentials:"same-origin", headers: hdr() });
  if (r.status === 405 || r.status === 404) {
    r = await fetch(url, { method:"POST", credentials:"same-origin",
      headers: { ...hdr(), "X-HTTP-Method-Override":"DELETE", "X-CSRFToken": window.CSRF_TOKEN || "" }
    });
  }
  if (!r.ok) {
    const t = await r.text().catch(()=>""); const e = new Error(`DELETE ${url} -> ${r.status}`); e.status=r.status; e.body=t; throw e;
  }
  return r.json().catch(() => ({}));
}

export async function apiUpload(url, files) {
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  const r = await fetch(url, { method:"POST", credentials:"same-origin", headers: hdr(), body: fd });
  if (!r.ok) {
    const t = await r.text().catch(()=>""); const e = new Error(`UPLOAD ${url} -> ${r.status}`); e.status=r.status; e.body=t; throw e;
  }
  return r.json();
}
