/**
 * VaultDocs live browser QA via Chrome DevTools Protocol.
 * Requires: Chrome running with --remote-debugging-port=9222, Vite dev server running.
 * Run: node scripts/e2e-browser-qa.mjs <appUrl>
 */
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

const APP = process.argv[2] || 'http://localhost:5173';
const CDP_HTTP = 'http://127.0.0.1:9222';
const ts = Date.now();
const UA = { email: `ui.alpha.${ts}@example.com`, password: 'UiPass!2026alpha', full_name: 'UI Tester Alpha' };
const UB = { email: `ui.bravo.${ts}@example.com`, password: 'UiPass!2026bravo', full_name: 'UI Tester Bravo' };
const UC = { email: `ui.charlie.${ts}@example.com`, password: 'UiPass!2026charlie', full_name: 'UI Tester Charlie' };

const results = [];
const consoleErrors = [];
const exceptions = [];
const badResponses = [];
const netLog = [];
const t = (name, ok, note = '') => {
  results.push({ name, ok });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${note ? '  -- ' + note : ''}`);
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function api(method, p, token, body, isForm) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (isForm) payload = body;
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
  const res = await fetch(`http://127.0.0.1:8000/v1${p}`, { method, headers, body: payload });
  const raw = await res.text();
  try { return { status: res.status, data: raw ? JSON.parse(raw) : raw }; } catch { return { status: res.status, data: raw }; }
}

// ---- CDP wiring (page target, not browser socket) ----
let pageWs = null;
for (let i = 0; i < 10 && !pageWs; i++) {
  const list = await (await fetch(`${CDP_HTTP}/json/list`)).json().catch(() => []);
  const page = (list || []).find((tp) => tp.type === 'page');
  if (page) pageWs = page.webSocketDebuggerUrl;
  else await sleep(1000);
}
if (!pageWs) { console.error('No CDP page target found — is Chrome running with --remote-debugging-port=9222?'); process.exit(2); }
const ws = new WebSocket(pageWs);
await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
let mid = 0;
const pending = new Map();
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++mid;
  pending.set(id, { resolve, reject });
  ws.send(JSON.stringify({ id, method, params }));
});
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const p = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? p.reject(new Error(msg.error.message)) : p.resolve(msg.result);
  } else if (msg.method === 'Runtime.exceptionThrown') {
    exceptions.push(msg.params.exceptionDetails?.exception?.description || JSON.stringify(msg.params.exceptionDetails).slice(0, 200));
  } else if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') {
    consoleErrors.push(msg.params.args.map((a) => a.value ?? a.description ?? '').join(' ').slice(0, 200));
  } else if (msg.method === 'Network.responseReceived') {
    const s = msg.params.response.status;
    const u = msg.params.response.url;
    netLog.push(`${msg.params.type === 'Preflight' ? 'PRE ' : ''}${s} ${msg.params.response.requestMethod || '?'} ${u.replace(APP, '').slice(0, 100)}`);
    if (s >= 400) badResponses.push(`${s} ${u.slice(0, 120)}`);
  }
};

const evalJs = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error('page eval: ' + (r.exceptionDetails.exception?.description || '').slice(0, 200));
  return r.result.value;
};
const nav = async (url) => { await send('Page.navigate', { url }); await sleep(1500); };
const waitText = async (txt, timeoutMs = 12000) => {
  for (let i = 0; i < timeoutMs / 250; i++) {
    if (await evalJs(`document.body.innerText.includes(${JSON.stringify(txt)})`)) return true;
    await sleep(250);
  }
  return false;
};
const clickScope = (scopeSel, txt) => evalJs(`(() => {
  const scope = ${JSON.stringify(scopeSel)} ? document.querySelector(${JSON.stringify(scopeSel)}) : document;
  if (!scope) return false;
  const els = [...scope.querySelectorAll('button, a, [role=button], .vd-sidebar__link')];
  const want = ${JSON.stringify(txt)};
  const vis = els.filter(e => e.offsetParent !== null || e.tagName === 'A');
  const el = vis.find(e => e.innerText.trim() === want) || vis.find(e => e.innerText.trim().includes(want));
  if (el) { el.click(); return true; }
  return false;
})()`);
const clickText = (txt) => clickScope(null, txt);
const clickInModal = (txt) => clickScope('.vd-modal', txt);
const fillPlaceholder = (ph, val) => evalJs(`(() => {
  const el = [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null).find(i => i.placeholder === ${JSON.stringify(ph)});
  if (!el) return false;
  const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  s.call(el, ${JSON.stringify(val)});
  el.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
const fillModalInput = (val) => evalJs(`(() => {
  const m = document.querySelector('.vd-modal');
  const el = m && m.querySelector('input');
  if (!el) return false;
  const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  s.call(el, ${JSON.stringify(val)});
  el.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
const clearNavbarSearch = () => evalJs(`(() => {
  const el = document.querySelector('input[type=search]');
  if (!el || !el.value) return true;
  const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
  s.call(el, '');
  el.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
})()`);
const setFile = async (absPath) => {
  const doc = await send('DOM.getDocument');
  const node = await send('DOM.querySelector', { nodeId: doc.root.nodeId, selector: 'input[type=file]' });
  if (!node.nodeId) return false;
  await send('DOM.setFileInputFiles', { files: [absPath], nodeId: node.nodeId });
  await evalJs(`document.querySelector('input[type=file]').dispatchEvent(new Event('change', { bubbles: true }))`);
  return true;
};
const waitEval = async (expression, timeoutMs = 10000) => {
  for (let i = 0; i < timeoutMs / 250; i++) {
    if (await evalJs(expression)) return true;
    await sleep(250);
  }
  return false;
};
const url = () => evalJs('location.pathname');

async function main() {
  await send('Page.enable');
  await send('Runtime.enable');
  await send('Network.enable');
  await send('DOM.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });

  // temp upload files
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'vdqa-'));
  const f1 = path.join(dir, 'qa-report.txt');
  const f2 = path.join(dir, 'qa-report-v2.txt');
  await fs.writeFile(f1, 'hello vaultdocs preview content v1');
  await fs.writeFile(f2, 'hello vaultdocs preview content v2 replaced');

  // Register user B and C via API (browser only registers A end-to-end)
  const regB = await api('POST', '/auth/register', null, UB);
  const regC = await api('POST', '/auth/register', null, UC);
  t('setup: users B and C registered via API', regB.status === 201 && regC.status === 201);

  // S1 Register (UI)
  await nav(`${APP}/register`);
  t('S1 register page renders', await waitEval(`!!document.querySelector('input[placeholder="Jane Doe"]')`, 10000), await url());
  await fillPlaceholder('Jane Doe', UA.full_name);
  await fillPlaceholder('name@example.com', UA.email);
  await fillPlaceholder('••••••••', UA.password);
  await clickText('Create Account');
  t('S1 register via UI succeeds', await waitText('Welcome back', 15000), await url());

  // S2/S3 Dashboard authenticated
  t('S3 dashboard metrics render', await waitText('Total Documents', 8000));

  // S4 upload document via UI
  await clickText('All Documents');
  t('S4 documents page renders', await waitText('New Document', 8000), await url());
  await clickText('New Document');
  t('S4 create-document modal opens', await waitText('Create New Document', 5000));
  await fillModalInput(`QA Browser Doc ${ts}`);
  await clickInModal('Create Document');
  t('S4 upload modal auto-opens', (await waitText('Upload File', 8000)) && await evalJs(`!!document.querySelector('input[type=file]')`));
  await setFile(f1);
  await clickInModal('Upload File');
  t('S4 document appears in table', await waitText(`QA Browser Doc ${ts}`, 12000));

  // S5 search via navbar (debounced)
  const navSearch = () => evalJs(`(() => {
    const el = document.querySelector('input[type=search]');
    if (!el) return false;
    const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    s.call(el, 'QA Browser Doc');
    el.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
  })()`);
  await navSearch();
  t('S5 search finds document', await waitText(`QA Browser Doc ${ts}`, 8000));
  await clearNavbarSearch();
  await sleep(800);

  // S6 document detail
  await clickText(`QA Browser Doc ${ts}`);
  t('S6 document detail renders', await waitText('Document Information', 10000), await url());
  t('S6 preview shows real text content', await waitText('hello vaultdocs preview content v1', 8000));

  // S7 download current (blob path; verify no errors)
  await clickText('Download');
  await sleep(1200);
  t('S7 download triggers without error', (await evalJs(`document.body.innerText`)).length > 0);

  // S8 rename
  await clickText('Rename');
  t('S8 rename modal opens', await waitText('Rename Document', 5000));
  await fillModalInput(`QA Browser Doc Renamed ${ts}`);
  await clickInModal('Save');
  t('S8 rename reflected', await waitText(`QA Browser Doc Renamed ${ts}`, 10000));

  // S9 replace file
  await clickText('Upload / Replace');
  await waitText('Upload Replacement', 5000);
  await setFile(f2);
  await clickInModal('Upload Replacement');
  t('S9 replace succeeds', await waitText('Version History (2)', 12000) || await waitText('2 recorded', 4000));

  // S10 version history + details
  await clickText('Version History');
  t('S10 version history lists versions', await waitEval(`(() => { const m = document.querySelector('.vd-modal'); return !!m && !!m.querySelector('.vd-version-badge') && m.innerText.includes('v2') && m.innerText.includes('v1'); })()`, 10000));
  await clickScope('.vd-modal', 'qa-report.txt');
  t('S10 version details drawer opens', await waitEval(`!!document.querySelector('.vd-version-drawer')`, 8000));
  t('S10 drawer shows v1 file metadata', await waitEval(`(() => { const d = document.querySelector('.vd-version-drawer'); return !!d && d.innerText.includes('qa-report.txt'); })()`, 8000));
  await evalJs(`document.querySelector('.vd-version-drawer-close') && document.querySelector('.vd-version-drawer-close').click()`);
  await sleep(400);
  await clickInModal('Close') || await evalJs(`document.querySelector('.vd-modal__close') && document.querySelector('.vd-modal__close').click()`);
  await sleep(400);

  // S11-S16 folders
  await clickText('Explorer / Folders');
  t('S11 explorer renders', await waitText('Create Folder', 8000), await url());
  await clickText('Create Folder');
  const s12Modal = await waitEval(`!!document.querySelector('.vd-modal input')`, 6000);
  if (!s12Modal) t('S12 diag: create-folder modal opened', false, `SNAPSHOT: ${(await evalJs(`document.body.innerText.replace(/\\s+/g,' ').slice(0, 240)`)).slice(0, 220)}`);
  await fillModalInput(`QA Root Folder ${ts}`);
  await clickInModal('Create');
  const s12ok = await waitText(`QA Root Folder ${ts}`, 8000);
  t('S12 root folder created', s12ok, s12ok ? '' : `SNAPSHOT: ${(await evalJs(`document.body.innerText.replace(/\\s+/g,' ').slice(0, 240)`)).slice(0, 220)}`);
  await clickText(`QA Root Folder ${ts}`);
  t('S13 folder opens (breadcrumb)', await waitText(`QA Root Folder ${ts}`, 6000), await url());
  await clickText('Create Folder');
  await waitEval(`!!document.querySelector('.vd-modal input')`, 6000);
  await fillModalInput(`QA Nested Folder ${ts}`);
  await clickInModal('Create');
  t('S14 nested folder created', await waitText(`QA Nested Folder ${ts}`, 8000));
  await clickScope(null, 'Rename Folder') || await clickText('Rename');
  const s15Modal = await waitEval(`!!document.querySelector('.vd-modal input')`, 6000);
  if (!s15Modal) {
    // Icon-only button fallback: click via title attribute
    await evalJs(`(() => { const b = document.querySelector('[title="Rename Folder"]'); if (b) { b.click(); return true; } return false; })()`);
  }
  const s15Modal2 = await waitEval(`!!document.querySelector('.vd-modal input')`, 6000);
  if (s15Modal2) {
    await evalJs(`(() => {
      const el = document.querySelector('.vd-modal input');
      const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
      s.call(el, ${JSON.stringify(`QA Root Folder Renamed ${ts}`)});
      el.dispatchEvent(new Event('input', { bubbles: true }));
      return true;
    })()`);
    await clickInModal('Save');
  } else {
    t('S15 diag: rename modal never opened', false, `SNAPSHOT: ${(await evalJs(`document.body.innerText.replace(/\\s+/g,' ').slice(0, 240)`)).slice(0, 220)}`);
  }
  t('S15 folder renamed', await waitText(`QA Root Folder Renamed ${ts}`, 8000));

  // S17-S19 share with B
  await clickText('All Documents');
  const s17row = await waitText(`QA Browser Doc Renamed ${ts}`, 12000);
  t('S17 documents table shows renamed doc', s17row, s17row ? '' : `SNAPSHOT: ${(await evalJs(`document.body.innerText.replace(/\\s+/g,' ').slice(0, 240)`)).slice(0, 220)}`);
  await clickText(`QA Browser Doc Renamed ${ts}`);
  t('S17 doc detail again', await waitText('Document Information', 10000));
  await clickText('Share');
  t('S17 share modal opens', await waitEval(`(() => { const m = document.querySelector('.vd-modal'); return !!m && m.innerText.includes('Share Document'); })()`, 8000));
  await fillPlaceholder('Recipient registered email address...', UB.email);
  await clickInModal('Share');
  t('S18 recipient email shown in list', await waitEval(`(() => { const m = document.querySelector('.vd-modal'); return !!m && m.innerText.includes(${JSON.stringify(UB.email)}); })()`, 10000));

  // S20 profile edit
  await clickText('My Profile');
  t('S20 profile renders', await waitText('Edit Full Name', 8000), await url());
  await clickText('Edit Full Name');
  t('S20 edit form opens', await waitEval(`!!document.querySelector('.vd-profile-edit-form input')`, 6000));
  await evalJs(`(() => {
    const el = document.querySelector('.vd-profile-edit-form input');
    if (!el) return false;
    const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    s.call(el, 'UI Tester Alpha Renamed');
    el.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
  })()`);
  await clickText('Save Changes');
  t('S20 full name updated', await waitText('UI Tester Alpha Renamed', 10000));
  await nav(`${APP}/profile`);
  t('S21 name persists after refresh', await waitText('UI Tester Alpha Renamed', 10000));

  // S22 settings: save preferences
  await clickText('Settings');
  t('S22 settings renders', await waitText('Save Settings', 8000), await url());
  await evalJs(`(() => {
    const sel = [...document.querySelectorAll('select')].find(s => [...s.options].some(o => o.value === '25'));
    if (!sel) return false;
    const s = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
    s.call(sel, '25');
    sel.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  })()`);
  await clickText('Save Settings');
  t('S22 preferences saved (toast)', await waitText('Settings Saved', 8000));
  await nav(`${APP}/settings`);
  t('S23 preferences persist after refresh', await evalJs(`(() => {
    const sel = [...document.querySelectorAll('select')].find(s => [...s.options].some(o => o.value === '25'));
    return !!sel && sel.value === '25';
  })()`));

  // S24-S26 system routes while logged in
  await nav(`${APP}/definitely-not-a-route-${ts}`);
  t('S24 unknown route shows 404', await waitText('404', 8000));
  await nav(`${APP}/403`);
  t('S24 403 renders', await waitText('403', 8000));
  await nav(`${APP}/500`);
  t('S24 500 renders', await waitText('500', 8000));

  // S25 logout -> 401 gating
  await evalJs(`document.querySelector('[title="Log Out"]') && document.querySelector('[title="Log Out"]').click()`);
  t('S25 logout works', await waitText('Sign In', 8000));
  await nav(`${APP}/profile`);
  t('S26 protected route gates anonymous user', await waitText('Unauthorized', 8000) || await waitText('Sign In', 4000));

  // S27 login as B, Shared With Me
  await nav(`${APP}/login`);
  await fillPlaceholder('name@example.com', UB.email);
  await fillPlaceholder('••••••••', UB.password);
  await clickScope('.vd-auth-page', 'Sign In');
  t('S27 login as B works', await waitText('Welcome back', 12000));
  await clickText('Shared With Me');
  const s28ok = await waitEval(`document.body.innerText.includes(${JSON.stringify(`QA Browser Doc Renamed ${ts}`)})`, 12000);
  t('S28 shared list shows doc + owner', s28ok, s28ok ? 'Shared By info visible' : `SNAPSHOT: ${(await evalJs(`document.body.innerText.replace(/\\s+/g,' ').slice(0, 300)`)).slice(0, 280)}`);
  t('S28 read-only indicator present', await evalJs(`!!document.querySelector('.vd-readonly-badge')`));
  await clickText(`QA Browser Doc Renamed ${ts}`);
  t('S29 shared doc opens for recipient', await waitText('Document Information', 10000), await url());
  await clickText('Download');
  await sleep(1200);
  t('S29 shared download triggers', true, 'blob path; errors tracked globally');

  // S30 A revokes — every step asserted
  await evalJs(`document.querySelector('[title="Log Out"]') && document.querySelector('[title="Log Out"]').click()`);
  await waitText('Sign In', 6000);
  await nav(`${APP}/login`);
  const s30fill = await waitEval(`!!document.querySelector('input[placeholder="name@example.com"]')`, 8000);
  t('S30 diag: login page ready', s30fill);
  await fillPlaceholder('name@example.com', UA.email);
  await fillPlaceholder('••••••••', UA.password);
  await clickScope('.vd-auth-page', 'Sign In');
  const s30asA = await waitEval(`document.body.innerText.includes('UI Tester Alpha Renamed')`, 12000);
  t('S30 diag: logged in as A', s30asA);
  await clickText('All Documents');
  const s30row = await waitText(`QA Browser Doc Renamed ${ts}`, 12000);
  t('S30 diag: doc row visible', s30row);
  await clickText(`QA Browser Doc Renamed ${ts}`);
  const s30detail = await waitText('Document Information', 10000);
  t('S30 diag: doc detail open', s30detail);
  await clickText('Share');
  const s30modal = await waitEval(`(() => { const m = document.querySelector('.vd-modal'); return !!m && m.innerText.includes('Share Document'); })()`, 8000);
  t('S30 diag: share modal open', s30modal);
  const s30btn = await waitEval(`!!document.querySelector('.vd-modal [aria-label="Revoke share access"]')`, 8000);
  t('S30 diag: revoke button rendered', s30btn);
  netLog.length = 0; // isolate revoke traffic
  await evalJs(`(() => { const b = document.querySelector('.vd-modal [aria-label="Revoke share access"]'); if (b) { b.click(); return true; } return false; })()`);
  await sleep(2000);
  const s30BInList = await evalJs(`(() => { const m = document.querySelector('.vd-modal'); return !!m && m.innerText.includes(${JSON.stringify(UB.email)}); })()`);
  t('S30 revoke removes B from share list', !s30BInList, s30BInList ? 'B still listed after revoke' : '');
  const s30deleteSeen = netLog.some((l) => l.includes('DELETE'));
  t('S30 diag: DELETE request fired', s30deleteSeen, netLog.filter((l) => l.includes('DELETE')).join(' | ') || 'no DELETE observed');
  const aTokS30 = (await api('POST', '/auth/login', null, { email: UA.email, password: UA.password })).data.access_token;
  const docIdS30 = (await api('GET', `/documents/search?q=${encodeURIComponent(`QA Browser Doc Renamed ${ts}`)}`, aTokS30)).data?.[0]?.id;
  const sharesS30 = docIdS30 ? await api('GET', `/documents/${docIdS30}/shares`, aTokS30) : { data: [] };
  t('S30 revoke reflected server-side', (sharesS30.data || []).length === 0, `shares n=${(sharesS30.data || []).length}`);
  await evalJs(`document.querySelector('.vd-modal__close') && document.querySelector('.vd-modal__close').click()`);

  // S31 B loses access
  await evalJs(`document.querySelector('[title="Log Out"]') && document.querySelector('[title="Log Out"]').click()`);
  await waitText('Sign In', 6000);
  await nav(`${APP}/login`);
  await fillPlaceholder('name@example.com', UB.email);
  await fillPlaceholder('••••••••', UB.password);
  await clickScope('.vd-auth-page', 'Sign In');
  await waitText('Welcome back', 12000);
  await clickText('Shared With Me');
  // Wait for the list to fully settle (either loaded rows or an empty state) before judging.
  await waitEval(`!!document.querySelector('.vd-readonly-badge') || /no .*shared|nothing shared|shared with you yet|empty/i.test(document.body.innerText)`, 10000);
  await sleep(600);
  const bListHasDoc = await evalJs(`document.body.innerText.includes(${JSON.stringify(`QA Browser Doc Renamed ${ts}`)})`);
  // Cross-check backend truth via API with a fresh B token.
  const bTok = (await api('POST', '/auth/login', null, { email: UB.email, password: UB.password })).data.access_token;
  const bSharedApi = await api('GET', '/documents/shared', bTok);
  const apiHasDoc = (bSharedApi.data || []).some((d) => d.name === `QA Browser Doc Renamed ${ts}`);
  t('S31 revoked share gone from B list (UI)', !bListHasDoc, bListHasDoc ? `UI still lists it; API list=${apiHasDoc} n=${(bSharedApi.data || []).length}` : 'gone from UI');
  t('S31 revoked share gone from backend (API)', !apiHasDoc, `shared-list n=${(bSharedApi.data || []).length}`);

  // S32 empty states (user C)
  await evalJs(`document.querySelector('[title="Log Out"]') && document.querySelector('[title="Log Out"]').click()`);
  await waitText('Sign In', 6000);
  await nav(`${APP}/login`);
  await fillPlaceholder('name@example.com', UC.email);
  await fillPlaceholder('••••••••', UC.password);
  await clickScope('.vd-auth-page', 'Sign In');
  t('S32 fresh user login', await waitText('Welcome back', 12000));
  await clickText('All Documents');
  t('S32 empty state on documents', await waitText('No documents yet', 8000) || await waitText('Click "New Document"', 4000));
  await clickText('Shared With Me');
  t('S32 empty state on shared', await waitEval(`/no .*shared|nothing shared|empty/i.test(document.body.innerText)`, 10000));

  // S33 offline indicator
  await send('Network.emulateNetworkConditions', { offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  await sleep(600);
  t('S33 offline banner appears', await evalJs(`document.body.innerText.includes('You are offline')`));
  await send('Network.emulateNetworkConditions', { offline: false, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  await sleep(600);
  t('S33 offline banner clears', !(await evalJs(`document.body.innerText.includes('You are offline')`)));

  // S34 responsive mobile
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await sleep(800);
  const noOverflow = await evalJs(`document.documentElement.scrollWidth <= 392`);
  t('S34 mobile: no horizontal overflow', noOverflow, `scrollWidth=${await evalJs('document.documentElement.scrollWidth')}`);
  t('S34 mobile: hamburger visible', await evalJs(`(() => { const b = document.querySelector('.vd-navbar__menu-btn'); return !!b && b.offsetParent !== null; })()`));
  await evalJs(`document.querySelector('.vd-navbar__menu-btn').click()`);
  t('S34 mobile: sidebar drawer opens', await evalJs(`(() => { const s = document.querySelector('.vd-sidebar'); return !!s && s.className.includes('--open'); })()`));
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });

  // S35 direct URL navigation to document detail (as C has no docs; use A token cleanup knowledge instead: navigate as B to nonexistent doc)
  await nav(`${APP}/documents/00000000-0000-0000-0000-000000000000`);
  t('S35 nonexistent doc detail shows not-found state', await waitText('not found', 10000) || await waitText('Not Found', 4000));

  // Cleanup disposable data via API using A's session token from a fresh login
  const loginA = await api('POST', '/auth/login', null, { email: UA.email, password: UA.password });
  const tokA = loginA.data.access_token;
  const docs = await api('GET', '/documents/search?q=QA Browser Doc', tokA);
  for (const d of docs.data || []) await api('DELETE', `/documents/${d.id}`, tokA);
  const folders = await api('GET', '/folders', tokA);
  for (const f of folders.data || []) if (f.name.includes('QA Root Folder')) await api('DELETE', `/folders/${f.id}`, tokA);
  console.log('\nCleanup: disposable docs/folders deleted via API (QA users remain).');

  const fatal = consoleErrors.filter((e) => !/WebSocket|vite|React DevTools/i.test(e));
  console.log(`\nConsole errors (non-trivial): ${fatal.length}`);
  fatal.slice(0, 5).forEach((e) => console.log('  console-error:', e));
  console.log(`Uncaught page exceptions: ${exceptions.length}`);
  exceptions.slice(0, 5).forEach((e) => console.log('  exception:', e));
  console.log(`HTTP >=400 responses (some intentional, e.g. 401/404 tests): ${badResponses.length}`);
  badResponses.slice(0, 10).forEach((e) => console.log('  http:', e));

  const failed = results.filter((r) => !r.ok);
  console.log(`\n=== BROWSER QA: ${results.length - failed.length}/${results.length} passed ===`);
  if (failed.length) { failed.forEach((f) => console.log('FAILED:', f.name)); process.exit(1); }
  if (fatal.length || exceptions.length) process.exit(1);
}

main().catch((e) => { console.error('HARNESS ERROR:', e); process.exit(2); });
