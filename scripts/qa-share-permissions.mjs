/**
 * One-off browser QA for the sharing permission workflow (PHASE 11).
 * Drives headless Chrome via CDP against the real Vite app.
 * Uses polling (waitFor) instead of fixed sleeps so slow SPA boots never
 * cause false failures. Disposable users only.
 */
import fs from 'node:fs/promises';

const APP = process.env.QA_APP || 'http://localhost:3004';
const CDP_HTTP = 'http://127.0.0.1:9222';
const API = 'http://127.0.0.1:8000/v1';
const ts = Date.now();
const OWNER = { email: `ui.owner.${ts}@example.com`, password: 'UiPass!2026owner', full_name: 'UI Owner' };
const REC = { email: `ui.rec.${ts}@example.com`, password: 'UiPass!2026rec', full_name: 'UI Recipient' };

const results = [];
const record = (id, name, status, note = '') => {
  results.push({ id, name, status, note });
  console.log(`${status} | ${id} ${name}${note ? ' — ' + note : ''}`);
};

// ---------------------------------------------------------------- CDP helpers
function wrapWs(ws) {
  if (typeof ws.on === 'function') return ws;
  const listeners = new Map();
  return {
    on(ev, cb) {
      const h = (e) => cb(e.data);
      listeners.set(cb, h);
      ws.addEventListener(ev, h);
    },
    off(ev, cb) {
      const h = listeners.get(cb);
      if (h) ws.removeEventListener(ev, h);
    },
    send(data) {
      ws.send(data);
    },
    close() {
      try { ws.close(); } catch { /* already closed */ }
    },
  };
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let idCounter = 0;
const nextId = () => ++idCounter;

async function connectPage() {
  const target = await (await fetch(`${CDP_HTTP}/json/new?about:blank`, { method: 'PUT' })).json();
  const ws = wrapWs(new WebSocket(target.webSocketDebuggerUrl));
  const pending = new Map();
  const passiveHandlers = [];
  ws.on('message', (raw) => {
    const msg = JSON.parse(raw);
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    } else if (msg.method) {
      passiveHandlers.forEach((h) => h(msg));
    }
  });
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = nextId();
      pending.set(id, (msg) => {
        if (msg.error) reject(new Error(method + ': ' + JSON.stringify(msg.error)));
        else resolve(msg.result);
      });
      ws.send(JSON.stringify({ id, method, params }));
    });
  await new Promise((res, rej) => {
    ws.on('open', res);
    ws.on('error', rej);
  });
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Console.enable');
  await send('Network.enable');
  const onMessage = (h) => passiveHandlers.push(h);
  return { ws, send, onMessage };
}

const evalJs = async (send, expression) => {
  const r = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) {
    throw new Error('Eval failed: ' + JSON.stringify(r.exceptionDetails.exception?.description || r.exceptionDetails.text).slice(0, 300));
  }
  return r.result?.value;
};

const waitFor = async (send, expression, timeoutMs = 12000, interval = 400) => {
  const start = Date.now();
  let last = null;
  while (Date.now() - start < timeoutMs) {
    last = await evalJs(send, expression);
    if (last) return last;
    await sleep(interval);
  }
  return last;
};

const goto = async (send, url) => {
  await send('Page.navigate', { url });
  await sleep(400);
};

// ------------------------------------------------------------- backend helper
const api = async (path, opts = {}, token) => {
  const headers = { ...(opts.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const r = await fetch(API + path, { ...opts, headers });
  let body = null;
  try { body = await r.json(); } catch { /* binary */ }
  return { status: r.status, body };
};

const UI_LOGIN = (email, password) => `
  (async () => {
    const find = (ms) => new Promise((res, rej) => {
      const t0 = Date.now();
      const tick = () => {
        const emailEl = [...document.querySelectorAll('input')].find(i => i.type === 'email');
        const passEl = [...document.querySelectorAll('input')].find(i => i.type === 'password');
        if (emailEl && passEl) return res([emailEl, passEl]);
        if (Date.now() - t0 > ms) return rej(new Error('login form not found'));
        setTimeout(tick, 200);
      };
      tick();
    });
    const [emailEl, passEl] = await find(10000);
    const setV = (el, v) => {
      const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      s.call(el, v);
      el.dispatchEvent(new Event('input', { bubbles: true }));
    };
    setV(emailEl, '${email}');
    setV(passEl, '${password}');
    await new Promise(r => setTimeout(r, 250));
    // Submit via the login FORM (the navbar also has a "Sign In" button that
    // merely opens the auth modal — clicking it does nothing here).
    const form = emailEl.closest('form');
    const submitBtn = form ? form.querySelector('button[type=submit]') : null;
    if (submitBtn) submitBtn.click();
    else if (form) form.requestSubmit();
    else return 'NO_FORM';
    await new Promise(r => setTimeout(r, 1800));
    return localStorage.getItem('vaultdocs_token') ? 'AUTHED' : 'NO_TOKEN';
  })()
`;

async function main() {
  // --- Setup: real users + real upload via backend
  await api('/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(OWNER) });
  await api('/auth/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(REC) });
  const ownerTok = (await api('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: OWNER.email, password: OWNER.password }) })).body?.access_token;
  const recTok = (await api('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: REC.email, password: REC.password }) })).body?.access_token;
  if (!ownerTok || !recTok) throw new Error('backend setup failed');

  const docRes = await api('/documents', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: 'UI QA Shared Doc' }) }, ownerTok);
  const DOC_ID = docRes.body.id;
  const fd = new FormData();
  fd.append('file', new Blob(['Shared permission QA — preview text content for the browser test.\n'.repeat(20)], { type: 'text/plain' }), 'ui-qa-doc.txt');
  const up = await fetch(`${API}/documents/${DOC_ID}/upload`, { method: 'POST', headers: { Authorization: `Bearer ${ownerTok}` }, body: fd });
  if (up.status !== 200) throw new Error('upload failed: ' + up.status);

  // ============================================================ A–F: OWNER
  const page1 = await connectPage();
  const consoleErrors = [];
  const failedRequests = [];
  page1.onMessage((msg) => {
    if (msg.method === 'Console.messageAdded' && msg.params.message.level === 'error') consoleErrors.push(msg.params.message.text);
    if (msg.method === 'Network.loadingFailed') failedRequests.push(msg.params.errorText);
  });
  const { send } = page1;

  await goto(send, `${APP}/login`);
  record('A', 'Owner login via real UI', (await evalJs(send, UI_LOGIN(OWNER.email, OWNER.password))) === 'AUTHED' ? 'PASS' : 'FAIL');

  await goto(send, `${APP}/documents/${DOC_ID}`);
  const docVisible = await waitFor(send, `document.body.innerText.includes('UI QA Shared Doc')`);
  record('B', 'Owner opens document detail', docVisible ? 'PASS' : 'FAIL');

  // C/D. Open Share UI
  const shareOpened = await waitFor(send, `
    (() => {
      const btn = [...document.querySelectorAll('button')].find(b => /^share$/i.test(b.textContent.trim()));
      if (!btn) return false;
      btn.click();
      return true;
    })()
  `);
  record('C', 'Share button opens workflow', shareOpened ? 'PASS' : 'FAIL');

  const selector = await waitFor(send, `
    (() => {
      const group = document.querySelector('.vd-share-permission-group');
      if (!group) return null;
      const options = [...group.querySelectorAll('.vd-share-permission-option')];
      return JSON.stringify({
        count: options.length,
        labels: options.map(o => o.querySelector('.vd-share-permission-head span')?.textContent),
        defaultChecked: options.findIndex(o => o.getAttribute('aria-checked') === 'true'),
      });
    })()
  `);
  const sel = selector ? JSON.parse(selector) : null;
  record('E', 'Permission selector: View only (default) + View + Download', sel && sel.count === 2 && sel.defaultChecked === 0 ? 'PASS' : 'FAIL', JSON.stringify(sel));

  // F. Share as View Only (default stays selected)
  const shareRow = await evalJs(send, `
    (async () => {
      const input = document.querySelector('.vd-share-form input[type="email"]');
      if (!input) return 'NO_INPUT';
      const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      s.call(input, '${REC.email}');
      input.dispatchEvent(new Event('input', { bubbles: true }));
      await new Promise(r => setTimeout(r, 250));
      const shareBtn = [...document.querySelectorAll('.vd-share-form button')].find(b => /share/i.test(b.textContent));
      shareBtn.click();
      await new Promise(r => setTimeout(r, 1500));
      return document.querySelector('.vd-share-modal-body')?.innerText || 'NO_ROWS';
    })()
  `);
  record('F', 'View Only share created and listed', typeof shareRow === 'string' && shareRow.includes('View Only') && shareRow.includes(REC.email) ? 'PASS' : 'FAIL', String(shareRow).slice(0, 80));

  const sharesApi = await api(`/documents/${DOC_ID}/shares`, {}, ownerTok);
  const shareId = sharesApi.body?.[0]?.id;
  record('F2', 'download_allowed=false persisted in backend', sharesApi.body?.[0]?.download_allowed === false ? 'PASS' : 'FAIL');

  // ============================================================ G–N: RECIPIENT (view-only)
  const page2 = await connectPage();
  page2.onMessage((msg) => {
    if (msg.method === 'Console.messageAdded' && msg.params.message.level === 'error') consoleErrors.push(msg.params.message.text);
    if (msg.method === 'Network.loadingFailed') failedRequests.push(msg.params.errorText);
  });
  const send2 = page2.send;

  await goto(send2, `${APP}/login`);
  record('G', 'Recipient login via real UI', (await evalJs(send2, UI_LOGIN(REC.email, REC.password))) === 'AUTHED' ? 'PASS' : 'FAIL');

  await goto(send2, `${APP}/shared`);
  const sharedListed = await waitFor(send2, `document.body.innerText.includes('UI QA Shared Doc')`);
  record('H', 'Shared With Me lists the document', sharedListed ? 'PASS' : 'FAIL');
  record('I', 'View Only label shown', (await evalJs(send2, `document.body.innerText.includes('View Only')`)) ? 'PASS' : 'FAIL');

  await goto(send2, `${APP}/documents/${DOC_ID}`);
  await waitFor(send2, `document.body.innerText.includes('UI QA Shared Doc')`);
  const previewOk = await waitFor(send2, `
    (() => {
      const pre = document.querySelector('.vd-docdetail-preview-text');
      if (pre && pre.textContent.includes('preview text content')) return 'PREVIEW_OK';
      if (document.querySelector('.vd-docdetail-preview-frame')) return 'PREVIEW_OK';
      if (document.querySelector('.vd-docdetail-preview-image')) return 'PREVIEW_OK';
      if (document.querySelector('.vd-docdetail-preview-error')) return 'PREVIEW_ERROR';
      return null;
    })()
  `);
  record('K', 'Preview renders content for view-only recipient', String(previewOk) === 'PREVIEW_OK' ? 'PASS' : 'FAIL', String(previewOk));

  const dlAudit = await evalJs(send2, `
    (() => {
      const actionable = [...document.querySelectorAll('button:not([disabled]), a')]
        .map(b => ((b.textContent || '') + ' ' + (b.title || '') + ' ' + (b.getAttribute('aria-label') || '')).trim());
      const dlLeak = actionable.filter(t => /download/i.test(t));
      const manageLeak = ['Rename', 'Move', 'Share', 'Delete', 'Upload'].filter(w =>
        [...document.querySelectorAll('button')].some(b => new RegExp('^' + w + '$', 'i').test(b.textContent.trim())));
      const badge = document.body.innerText.includes('View Only') || document.body.innerText.toLowerCase().includes('read-only');
      return JSON.stringify({ dlLeak, manageLeak, badge });
    })()
  `);
  const audit = JSON.parse(dlAudit);
  record('L', 'No Download/mutation actions leak for view-only', audit.dlLeak.length === 0 && audit.manageLeak.length === 0 ? 'PASS' : 'FAIL', dlAudit.slice(0, 140));

  const recDlStatus = await api(`/documents/${DOC_ID}/download`, {}, recTok).then((r) => r.status);
  record('M/N', 'Direct API download blocked (403) for view-only', recDlStatus === 403 ? 'PASS' : 'FAIL', `status=${recDlStatus}`);

  // ============================================================ P–U: View + Download
  const patched = await api(`/documents/${DOC_ID}/shares/${shareId}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ download_allowed: true }) }, ownerTok);
  record('P', 'Owner changes permission to View + Download', patched.status === 200 && patched.body?.download_allowed === true ? 'PASS' : 'FAIL', `status=${patched.status}`);

  await goto(send2, `${APP}/shared`);
  record('R', 'View + Download label shown', (await waitFor(send2, `document.body.innerText.includes('View + Download')`)) ? 'PASS' : 'FAIL');

  await goto(send2, `${APP}/documents/${DOC_ID}`);
  await waitFor(send2, `document.body.innerText.includes('UI QA Shared Doc')`);
  const dlClicked = await evalJs(send2, `
    (async () => {
      for (let i = 0; i < 12; i++) {
        const btn = [...document.querySelectorAll('button:not([disabled])')].find(b => /download/i.test((b.textContent || '') + ' ' + (b.title || '')));
        if (btn) { btn.click(); await new Promise(r => setTimeout(r, 1200)); return 'CLICKED'; }
        await new Promise(r => setTimeout(r, 500));
      }
      return 'NO_ENABLED_DOWNLOAD';
    })()
  `);
  const dlStatus = await api(`/documents/${DOC_ID}/download`, {}, recTok).then((r) => r.status);
  record('S', 'Download current file (UI + API 200)', dlClicked === 'CLICKED' && dlStatus === 200 ? 'PASS' : 'FAIL', `ui=${dlClicked} api=${dlStatus}`);

  const versions = await api(`/documents/${DOC_ID}/versions`, {}, recTok);
  const vId = versions.body?.[0]?.id;
  const vStatus = vId ? (await fetch(`${API}/documents/${DOC_ID}/versions/${vId}/download`, { headers: { Authorization: `Bearer ${recTok}` } })).status : 0;
  record('T', 'Version download works for View + Download', vStatus === 200 ? 'PASS' : 'FAIL', `status=${vStatus}`);

  const leaks = await evalJs(send2, `
    JSON.stringify(['Rename', 'Move', 'Share', 'Delete', 'Upload File', 'Upload / Replace'].filter(w =>
      [...document.querySelectorAll('button')].some(b => b.textContent.trim() === w)))
  `);
  record('U', 'No mutation controls for download-enabled recipient', leaks === '[]' ? 'PASS' : 'FAIL', leaks);

  // ============================================================ V–W: Revoke
  const revoked = await api(`/documents/${DOC_ID}/shares/${shareId}`, { method: 'DELETE' }, ownerTok);
  record('V', 'Owner revokes share', revoked.status === 204 ? 'PASS' : 'FAIL', `status=${revoked.status}`);
  await goto(send2, `${APP}/shared`);
  await sleep(800);
  const goneUi = !(await evalJs(send2, `document.body.innerText.includes('UI QA Shared Doc')`));
  const goneApi = await api(`/documents/${DOC_ID}`, {}, recTok).then((r) => r.status);
  record('W', 'Recipient loses access after revoke', goneUi && goneApi === 404 ? 'PASS' : 'FAIL', `ui=${goneUi} api=${goneApi}`);

  try { page1.ws.close(); } catch { /* ignore */ }
  try { page2.ws.close(); } catch { /* ignore */ }

  const realErrors = consoleErrors.filter((e) => !/favicon|Download the React DevTools|autofill/i.test(e));
  record('X', 'No unexpected browser console errors', realErrors.length === 0 ? 'PASS' : 'WARN', realErrors.slice(0, 2).join(' | ').slice(0, 180));
  record('Y', 'No failed network requests', failedRequests.length === 0 ? 'PASS' : 'WARN', failedRequests.slice(0, 2).join(' | ').slice(0, 140));

  const pass = results.filter((r) => r.status === 'PASS').length;
  console.log(`\nBROWSER QA SUMMARY: ${pass}/${results.length} PASS (${results.filter((r) => r.status === 'FAIL').length} FAIL, ${results.filter((r) => r.status === 'WARN').length} WARN)`);
  await fs.writeFile('var/browser-qa-results.json', JSON.stringify(results, null, 2));
  process.exit(results.some((r) => r.status === 'FAIL') ? 1 : 0);
}

main().catch((e) => {
  console.error('QA CRASH:', e.message);
  process.exit(2);
});
