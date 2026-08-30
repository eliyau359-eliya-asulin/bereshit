/* Regression tests for api/blob-upload-token.js — the small Node
 * function that mints a short-lived Vercel Blob upload credential for
 * the Admin image-upload flow. Run with plain Node (no dependencies, no
 * @vercel/blob install required — every external effect is injected as
 * a fake):
 *
 *   node --test api/tests/blob-upload-token.test.js
 *
 * createHandler() takes issueSignedToken/presignUrl/fetchImpl as
 * parameters specifically so this file never needs the real
 * @vercel/blob package, a network connection, or a real Flask server —
 * the actual wiring to those (the module's default export) is a single
 * line reviewed by hand, not re-tested here.
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { createHandler, buildStagingPathname, ALLOWED_CONTENT_TYPES, MAX_SOURCE_BYTES } =
  require(path.join(__dirname, '..', 'blob-upload-token.js'));

function makeRes(){
  return {
    statusCode: null,
    body: null,
    status(code){ this.statusCode = code; return this; },
    json(obj){ this.body = obj; return this; },
  };
}

function makeReq({ method = 'POST', cookie = 'bereshit_admin_session=abc123', host = 'shop.example.com' } = {}){
  return {
    method,
    headers: {
      cookie,
      host,
      'x-forwarded-proto': 'https',
    },
  };
}

function fakeAuthOk(){
  let calls = 0;
  const fetchImpl = async (url, options) => {
    calls++;
    fetchImpl.lastUrl = url;
    fetchImpl.lastOptions = options;
    return { ok: true, status: 200, json: async () => ({ authorized: true }) };
  };
  fetchImpl.callCount = () => calls;
  return fetchImpl;
}

function fakeAuthDenied(status, error, code){
  return async () => ({ ok: false, status, json: async () => ({ error, code }) });
}

test('buildStagingPathname matches the staging/<32-hex>.upload shape process_staged_image requires', () => {
  const pathname = buildStagingPathname();
  assert.match(pathname, /^staging\/[0-9a-f]{32}\.upload$/);
});

test('buildStagingPathname is different every call (never a predictable/reused path)', () => {
  const a = buildStagingPathname();
  const b = buildStagingPathname();
  assert.notEqual(a, b);
});

test('rejects a non-POST method without ever calling the auth check', async () => {
  let authCalled = false;
  const handler = createHandler({
    issueSignedToken: async () => { throw new Error('must not be called'); },
    presignUrl: async () => { throw new Error('must not be called'); },
    fetchImpl: async () => { authCalled = true; return { ok: true, json: async () => ({}) }; },
  });
  const res = makeRes();
  await handler(makeReq({ method: 'GET' }), res);
  assert.equal(res.statusCode, 405);
  assert.equal(authCalled, false);
});

test('forwards the request cookie to /api/images/upload-authorize', async () => {
  const fetchImpl = fakeAuthOk();
  const handler = createHandler({
    issueSignedToken: async () => ({ delegationToken: 'd', clientSigningToken: 'c', validUntil: 0 }),
    presignUrl: async () => ({ presignedUrl: 'https://blob.vercel-storage.com/?pathname=x&sig=abc' }),
    fetchImpl,
  });
  await handler(makeReq({ cookie: 'bereshit_admin_session=the-real-session-cookie' }), makeRes());
  assert.equal(fetchImpl.callCount(), 1);
  assert.match(fetchImpl.lastUrl, /\/api\/images\/upload-authorize$/);
  assert.equal(fetchImpl.lastOptions.headers.cookie, 'bereshit_admin_session=the-real-session-cookie');
});

test('denies the request and never mints a token when the auth check fails', async () => {
  let tokenCalls = 0;
  const handler = createHandler({
    issueSignedToken: async () => { tokenCalls++; return {}; },
    presignUrl: async () => { tokenCalls++; return {}; },
    fetchImpl: fakeAuthDenied(403, 'אין הרשאה מספקת לפעולה זו', 'FORBIDDEN'),
  });
  const res = makeRes();
  await handler(makeReq(), res);
  assert.equal(res.statusCode, 403);
  assert.equal(res.body.code, 'FORBIDDEN');
  assert.equal(tokenCalls, 0);
});

test('returns 502 (never throws unhandled) when the auth check itself fails to connect', async () => {
  const handler = createHandler({
    issueSignedToken: async () => ({}),
    presignUrl: async () => ({}),
    fetchImpl: async () => { throw new Error('ECONNREFUSED'); },
  });
  const res = makeRes();
  await handler(makeReq(), res);
  assert.equal(res.statusCode, 502);
});

test('on success, mints a token scoped to one staging pathname, one operation, capped size/type, short TTL', async () => {
  let issueArgs = null;
  let presignArgs = null;
  const handler = createHandler({
    issueSignedToken: async (opts) => { issueArgs = opts; return { delegationToken: 'd', clientSigningToken: 'c', validUntil: opts.validUntil }; },
    presignUrl: async (token, opts) => { presignArgs = { token, opts }; return { presignedUrl: 'https://blob.vercel-storage.com/?pathname=' + opts.pathname + '&sig=abc' }; },
    fetchImpl: fakeAuthOk(),
  });
  const res = makeRes();
  const before = Date.now();
  await handler(makeReq(), res);

  assert.equal(res.statusCode, 200);
  assert.deepEqual(issueArgs.operations, ['put']);
  assert.deepEqual(issueArgs.allowedContentTypes, ALLOWED_CONTENT_TYPES);
  assert.equal(issueArgs.maximumSizeInBytes, MAX_SOURCE_BYTES);
  assert.ok(issueArgs.validUntil > before, 'token must expire in the future');
  assert.ok(issueArgs.validUntil <= before + 5 * 60 * 1000 + 1000, 'token TTL must be short (~5 minutes), not session-length');
  assert.match(issueArgs.pathname, /^staging\/[0-9a-f]{32}\.upload$/);

  assert.equal(presignArgs.opts.operation, 'put');
  assert.equal(presignArgs.opts.access, 'public');
  assert.equal(presignArgs.opts.pathname, issueArgs.pathname);
});

test('the response contains ONLY presignedUrl and pathname — never a token, secret, or credential field', async () => {
  const handler = createHandler({
    issueSignedToken: async () => ({ delegationToken: 'DELEGATION-SECRET', clientSigningToken: 'SIGNING-SECRET', validUntil: 0 }),
    presignUrl: async (token, opts) => ({ presignedUrl: `https://blob.vercel-storage.com/?pathname=${opts.pathname}&sig=abc` }),
    fetchImpl: fakeAuthOk(),
  });
  const res = makeRes();
  await handler(makeReq(), res);

  assert.equal(res.statusCode, 200);
  assert.deepEqual(Object.keys(res.body).sort(), ['pathname', 'presignedUrl']);
  const serialized = JSON.stringify(res.body);
  assert.ok(!serialized.includes('DELEGATION-SECRET'));
  assert.ok(!serialized.includes('SIGNING-SECRET'));
});

test('a Blob API failure while minting the token returns 500 with a generic message, never raw error details', async () => {
  const handler = createHandler({
    issueSignedToken: async () => { throw new Error('BERESHIT_IMAGES_READ_WRITE_TOKEN is invalid: super-secret-detail-xyz'); },
    presignUrl: async () => ({}),
    fetchImpl: fakeAuthOk(),
  });
  const res = makeRes();
  await handler(makeReq(), res);
  assert.equal(res.statusCode, 500);
  assert.ok(!JSON.stringify(res.body).includes('super-secret-detail-xyz'));
});
