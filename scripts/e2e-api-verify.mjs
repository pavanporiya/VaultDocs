/**
 * VaultDocs live API E2E verification harness (disposable users, real backend).
 * Run: node scripts/e2e-api-verify.mjs   (from repo root)
 */
import fs from 'node:fs/promises';

const BASE = 'http://127.0.0.1:8000/v1';
const ts = Date.now();
const A = { email: `qa.alpha.${ts}@example.com`, password: 'QaPass!2026alpha', full_name: 'QA Tester Alpha' };
const B = { email: `qa.bravo.${ts}@example.com`, password: 'QaPass!2026bravo', full_name: 'QA Tester Bravo' };
const C = { email: `qa.charlie.${ts}@example.com`, password: 'QaPass!2026charlie', full_name: 'QA Tester Charlie' };

const results = [];
const t = (name, ok, note = '') => {
  results.push({ name, ok });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${note ? '  -- ' + note : ''}`);
};

async function api(method, path, token, body, isForm = false) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (isForm) payload = body;
  else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  const res = await fetch(BASE + path, { method, headers, body: payload });
  const ct = res.headers.get('content-type') || '';
  const raw = await res.text();
  const data = ct.includes('application/json') && raw ? JSON.parse(raw) : raw;
  return { status: res.status, data };
}

async function main() {
  fs; // noop
  // ---- Auth ----
  const regA = await api('POST', '/auth/register', null, A);
  t('register user A (201)', regA.status === 201, `got ${regA.status}`);
  const regB = await api('POST', '/auth/register', null, B);
  t('register user B (201)', regB.status === 201, `got ${regB.status}`);
  const regC = await api('POST', '/auth/register', null, C);
  t('register user C (201)', regC.status === 201, `got ${regC.status}`);

  const loginA = await api('POST', '/auth/login', null, { email: A.email, password: A.password });
  t('login A (200 + token)', loginA.status === 200 && !!loginA.data.access_token, `got ${loginA.status}`);
  const tokA = loginA.data.access_token;
  const loginB = await api('POST', '/auth/login', null, { email: B.email, password: B.password });
  t('login B (200 + token)', loginB.status === 200 && !!loginB.data.access_token, `got ${loginB.status}`);
  const tokB = loginB.data.access_token;

  const me = await api('GET', '/auth/me', tokA);
  t('GET /auth/me returns A', me.status === 200 && me.data.email === A.email, `got ${me.status}`);

  const bad = await api('POST', '/auth/login', null, { email: A.email, password: 'wrong-password' });
  t('wrong password rejected (401)', bad.status === 401, `got ${bad.status}`);

  const unauth = await api('GET', '/documents');
  t('unauthenticated /documents blocked (401)', unauth.status === 401, `got ${unauth.status}`);

  // ---- Profile update ----
  const patchMe = await api('PATCH', '/auth/me', tokA, { full_name: 'QA Tester Alpha Renamed' });
  t('PATCH /auth/me full_name (200)', patchMe.status === 200 && patchMe.data.full_name === 'QA Tester Alpha Renamed', `got ${patchMe.status}`);
  const meAgain = await api('GET', '/auth/me', tokA);
  t('full_name persisted after PATCH', meAgain.data.full_name === 'QA Tester Alpha Renamed');
  const patchRestore = await api('PATCH', '/auth/me', tokA, { full_name: A.full_name });
  t('PATCH /auth/me restore name (200)', patchRestore.status === 200, `got ${patchRestore.status}`);

  // ---- Preferences ----
  const prefEmpty = await api('GET', '/users/me/preferences', tokA);
  t('GET /users/me/preferences (200)', prefEmpty.status === 200, `got ${prefEmpty.status} ${JSON.stringify(prefEmpty.data).slice(0, 60)}`);
  const putPref = await api('PUT', '/users/me/preferences', tokA, { theme: 'dark', density: 'compact', notifications: true });
  t('PUT /users/me/preferences (200)', putPref.status === 200, `got ${putPref.status}`);
  const prefRead = await api('GET', '/users/me/preferences', tokA);
  const prefs = (prefRead.data && prefRead.data.preferences) || {};
  t('preferences persist server-side', prefRead.status === 200 && prefs.theme === 'dark' && prefs.density === 'compact', JSON.stringify(prefRead.data).slice(0, 80));
  const prefB = await api('GET', '/users/me/preferences', tokB);
  t('preferences isolated per user', prefB.status === 200 && (!((prefB.data || {}).preferences || {}).theme), JSON.stringify(prefB.data).slice(0, 60));
  await api('PUT', '/users/me/preferences', tokA, {});

  // ---- Folders ----
  const foldRoot = await api('POST', '/folders', tokA, { name: `QA Root ${ts}` });
  t('create root folder (201)', foldRoot.status === 201, `got ${foldRoot.status}`);
  const rootId = foldRoot.data && foldRoot.data.id;
  const foldNested = rootId ? await api('POST', '/folders', tokA, { name: `QA Nested ${ts}`, parent_id: rootId }) : { status: 0 };
  t('create nested folder (201)', foldNested.status === 201, `got ${foldNested.status}`);
  const foldRename = rootId ? await api('PATCH', `/folders/${rootId}`, tokA, { name: `QA Root Renamed ${ts}` }) : { status: 0 };
  t('rename folder (200)', foldRename.status === 200, `got ${foldRename.status}`);
  const foldList = await api('GET', '/folders', tokA);
  const listedRoot = foldList.status === 200 && (foldList.data || []).some((f) => f.id === rootId);
  t('folder list contains renamed folder', listedRoot);

  // ---- Documents + files ----
  const docCreate = await api('POST', '/documents', tokA, { name: `QA Doc ${ts}` });
  t('create document (201)', docCreate.status === 201, `got ${docCreate.status}`);
  const docId = docCreate.data && docCreate.data.id;

  const fd1 = new FormData();
  fd1.append('file', new Blob(['alpha confidential v1'], { type: 'text/plain' }), 'qa-alpha.txt');
  const up1 = docId ? await api('POST', `/documents/${docId}/upload`, tokA, fd1, true) : { status: 0 };
  t('upload file v1 (200)', up1.status === 200, `got ${up1.status} size=${up1.data && up1.data.file_size}`);

  const docGet = docId ? await api('GET', `/documents/${docId}`, tokA) : { status: 0 };
  t('GET document detail (200)', docGet.status === 200 && docGet.data.original_filename === 'qa-alpha.txt', `got ${docGet.status}`);

  const search = await api('GET', `/documents/search?q=${encodeURIComponent(`QA Doc ${ts}`)}`, tokA);
  t('search finds document', search.status === 200 && (search.data || []).some((d) => d.id === docId), `got ${search.status} n=${(search.data || []).length}`);

  const dl1 = docId ? await api('GET', `/documents/${docId}/download`, tokA) : { status: 0, data: '' };
  t('download current file (200 + content)', dl1.status === 200 && dl1.data === 'alpha confidential v1', `got ${dl1.status}`);

  const fd2 = new FormData();
  fd2.append('file', new Blob(['alpha confidential v2 replaced'], { type: 'text/plain' }), 'qa-alpha.txt');
  const up2 = docId ? await api('PUT', `/documents/${docId}/upload`, tokA, fd2, true) : { status: 0 };
  t('replace file v2 via PUT (200)', up2.status === 200, `got ${up2.status}`);

  const vers = docId ? await api('GET', `/documents/${docId}/versions`, tokA) : { status: 0, data: [] };
  t('version history has 2 versions', vers.status === 200 && (vers.data || []).length === 2, `got ${vers.status} n=${(vers.data || []).length}`);
  const v1 = (vers.data || []).find((v) => v.version_number === 1);
  const v1get = v1 ? await api('GET', `/documents/${docId}/versions/${v1.id}`, tokA) : { status: 0 };
  t('version details endpoint (200)', v1get.status === 200, `got ${v1get.status}`);
  const v1dl = v1 ? await api('GET', `/documents/${docId}/versions/${v1.id}/download`, tokA) : { status: 0, data: '' };
  t('download older version (content = v1)', v1dl.status === 200 && v1dl.data === 'alpha confidential v1', `got ${v1dl.status}`);

  const docRename = docId ? await api('PATCH', `/documents/${docId}`, tokA, { name: `QA Doc Renamed ${ts}` }) : { status: 0 };
  t('rename document (200)', docRename.status === 200, `got ${docRename.status}`);

  // ---- Sharing ----
  const share = docId ? await api('POST', `/documents/${docId}/shares`, tokA, { user_email: B.email }) : { status: 0 };
  const shareId = share.data && share.data.id;
  t('share with B (201 + email populated)', share.status === 201 && share.data.shared_with_email === B.email, `got ${share.status} email=${share.data && share.data.shared_with_email}`);
  const shareList = docId ? await api('GET', `/documents/${docId}/shares`, tokA) : { status: 0, data: [] };
  t('share list shows recipient email', shareList.status === 200 && (shareList.data || []).some((s) => s.shared_with_email === B.email), `got ${shareList.status}`);

  const sharedB = await api('GET', '/documents/shared', tokB);
  t('GET /documents/shared lists for B', sharedB.status === 200 && (sharedB.data || []).some((d) => d.id === docId && d.shared_by_email === A.email), `got ${sharedB.status} n=${(sharedB.data || []).length}`);

  const bRead = docId ? await api('GET', `/documents/${docId}`, tokB) : { status: 0 };
  t('recipient can read shared doc', bRead.status === 200, `got ${bRead.status}`);
  const bDl = docId ? await api('GET', `/documents/${docId}/download`, tokB) : { status: 0, data: '' };
  t('recipient can download shared doc', bDl.status === 200 && bDl.data === 'alpha confidential v2 replaced', `got ${bDl.status}`);

  // ---- Security: recipient cannot mutate ----
  const bPatch = docId ? await api('PATCH', `/documents/${docId}`, tokB, { name: 'hijacked' }) : { status: 0 };
  t('recipient CANNOT rename (404/403)', [403, 404].includes(bPatch.status), `got ${bPatch.status}`);
  const bDelete = docId ? await api('DELETE', `/documents/${docId}`, tokB) : { status: 0 };
  t('recipient CANNOT delete (404/403)', [403, 404].includes(bDelete.status), `got ${bDelete.status}`);
  const bfd = new FormData();
  bfd.append('file', new Blob(['hijack'], { type: 'text/plain' }), 'hijack.txt');
  const bPut = docId ? await api('PUT', `/documents/${docId}/upload`, tokB, bfd, true) : { status: 0 };
  t('recipient CANNOT replace file (404/403)', [403, 404].includes(bPut.status), `got ${bPut.status}`);

  // ---- Security: unrelated user cannot access ----
  const loginC = await api('POST', '/auth/login', null, { email: C.email, password: C.password });
  const tokC = loginC.data.access_token;
  const cRead = docId ? await api('GET', `/documents/${docId}`, tokC) : { status: 0 };
  t('unrelated user CANNOT read (404)', cRead.status === 404, `got ${cRead.status}`);
  const cShared = await api('GET', '/documents/shared', tokC);
  t('unrelated user has empty shared list', cShared.status === 200 && (cShared.data || []).length === 0, `got ${cShared.status}`);

  // ---- Revoke ----
  const rev = shareId ? await api('DELETE', `/documents/${docId}/shares/${shareId}`, tokA) : { status: 0 };
  t('revoke share (200/204)', [200, 204].includes(rev.status), `got ${rev.status}`);
  const sharedAfter = await api('GET', '/documents/shared', tokB);
  t('revoked share disappears from B list', sharedAfter.status === 200 && !(sharedAfter.data || []).some((d) => d.id === docId), `n=${(sharedAfter.data || []).length}`);
  const bReadAfter = docId ? await api('GET', `/documents/${docId}`, tokB) : { status: 0 };
  t('revoked recipient loses access (404)', bReadAfter.status === 404, `got ${bReadAfter.status}`);

  // ---- Cleanup disposable data ----
  if (docId) await api('DELETE', `/documents/${docId}`, tokA);
  if (foldNested.status === 201) await api('DELETE', `/folders/${foldNested.data.id}`, tokA);
  if (rootId) await api('DELETE', `/folders/${rootId}`, tokA);
  console.log('\nDisposable test data cleaned up (documents/folders deleted; test users remain).');

  const failed = results.filter((r) => !r.ok);
  console.log(`\n=== API E2E: ${results.length - failed.length}/${results.length} passed ===`);
  if (failed.length) process.exit(1);
}

main().catch((e) => {
  console.error('HARNESS ERROR:', e);
  process.exit(2);
});
