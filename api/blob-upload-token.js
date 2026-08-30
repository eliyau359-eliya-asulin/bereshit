/**
 * Mints a short-lived, narrowly-scoped Vercel Blob upload credential so
 * the Admin's browser can PUT a product photo directly to Blob storage —
 * bypassing this deployment's Python/Flask function entirely for that
 * transfer, which is what lets a full-size source photo (up to 8MB, per
 * backend/images/processing.py's MAX_SOURCE_BYTES) get through reliably:
 * Vercel Functions cap request/response bodies at ~4.5MB, a limit that
 * cannot be raised, but only applies to traffic that actually goes
 * through a Function — a direct browser-to-Blob PUT never does.
 *
 * This function does exactly two things and nothing else:
 *   1. Confirms the caller is an authenticated admin with the
 *      `products:write` permission — by forwarding their existing
 *      session cookie to the real Flask session/role check
 *      (GET /api/images/upload-authorize) rather than re-implementing
 *      any of that logic here. If Flask says no, this mints no token.
 *   2. Asks Vercel Blob for a token scoped to ONE temporary "staging"
 *      pathname, ONE operation (put), a capped size, an allowed-type
 *      list, and a few-minute expiry — then signs a one-time upload URL
 *      from it.
 *
 * BERESHIT_IMAGES_READ_WRITE_TOKEN (the bereshit-images-public store's
 * read-write token — a custom variable prefix, not the SDK's default
 * BLOB_READ_WRITE_TOKEN name, since that belongs to a different,
 * no-longer-used store) is read directly from this function's own
 * process environment and never appears in the response body, in a log
 * line, or anywhere the browser can see it. The only thing the browser
 * ever receives is the narrow, short-lived presigned URL — categorically
 * different from (and far less powerful than) the real read-write token.
 *
 * The uploaded raw file is never validated, resized, converted to WebP,
 * or persisted to a product here or anywhere else in this function —
 * that all still happens server-side in Flask (see
 * backend/services/images_service.py:process_staged_image), which fetches
 * these exact bytes back and is the sole authority on what becomes a real
 * product image.
 *
 * The core logic (createHandler) takes every external effect as a
 * parameter specifically so it's testable with fakes — see
 * api/tests/blob-upload-token.test.js — with no real @vercel/blob
 * install, no network, and no experimental module-mocking required.
 */
const crypto = require('crypto');

// Keep in sync with backend/images/processing.py.
const ALLOWED_CONTENT_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_SOURCE_BYTES = 8 * 1024 * 1024; // MAX_SOURCE_BYTES in processing.py
const TOKEN_TTL_MS = 5 * 60 * 1000; // only needs to cover one PUT, not the whole admin session

function buildStagingPathname(){
  // Never derived from anything the client sent — a fresh random id every
  // time, under a dedicated `staging/` prefix that process_staged_image()
  // (backend/services/images_service.py) is the only thing ever allowed
  // to read from.
  return `staging/${crypto.randomUUID().replace(/-/g, '')}.upload`;
}

function createHandler({ issueSignedToken, presignUrl, fetchImpl = fetch }){
  return async function handler(req, res){
    if (req.method !== 'POST') {
      res.status(405).json({ error: 'Method not allowed' });
      return;
    }

    const cookie = req.headers.cookie || '';
    const host = req.headers['x-forwarded-host'] || req.headers.host;
    const protocol = req.headers['x-forwarded-proto'] || 'https';

    let authRes;
    try {
      authRes = await fetchImpl(`${protocol}://${host}/api/images/upload-authorize`, {
        method: 'GET',
        headers: cookie ? { cookie } : {},
      });
    } catch (err) {
      res.status(502).json({ error: 'Authorization check failed' });
      return;
    }

    if (!authRes.ok) {
      let body = {};
      try {
        body = await authRes.json();
      } catch (err) {
        // Non-JSON error body from an unexpected failure mode — fall
        // through to the generic message below rather than leak raw text.
      }
      res.status(authRes.status).json({
        error: body.error || 'לא ניתן לאמת הרשאה להעלאת תמונה',
        code: body.code,
      });
      return;
    }

    const pathname = buildStagingPathname();

    try {
      const signedToken = await issueSignedToken({
        pathname,
        operations: ['put'],
        allowedContentTypes: ALLOWED_CONTENT_TYPES,
        maximumSizeInBytes: MAX_SOURCE_BYTES,
        validUntil: Date.now() + TOKEN_TTL_MS,
      });

      const { presignedUrl } = await presignUrl(signedToken, {
        operation: 'put',
        pathname,
        access: 'public',
        allowedContentTypes: ALLOWED_CONTENT_TYPES,
        maximumSizeInBytes: MAX_SOURCE_BYTES,
        addRandomSuffix: false,
        allowOverwrite: false,
        validUntil: Date.now() + TOKEN_TTL_MS,
      });

      res.status(200).json({ presignedUrl, pathname });
    } catch (err) {
      res.status(500).json({ error: 'לא ניתן להכין העלאת תמונה' });
    }
  };
}

// The real Vercel Function export — @vercel/blob is only required here,
// lazily, inside the real deployment path. Tests never hit this line at
// all: they call createHandler() directly with fake dependencies.
//
// The bereshit-images-public store is connected to this project under a
// custom "BERESHIT_IMAGES" variable prefix (chosen when connecting the
// store), not the SDK's own default names — so issueSignedToken's
// automatic env-var resolution (which only looks for the unprefixed
// BLOB_READ_WRITE_TOKEN/BLOB_STORE_ID/VERCEL_OIDC_TOKEN — names that
// belong to a different, no-longer-used store) would never find it.
// `token` must be passed explicitly. presignUrl needs no such override:
// it signs locally from the material issueSignedToken already returned,
// with no additional auth of its own.
module.exports = createHandler({
  issueSignedToken: (opts) => require('@vercel/blob').issueSignedToken({
    ...opts,
    token: process.env.BERESHIT_IMAGES_READ_WRITE_TOKEN,
  }),
  presignUrl: (...args) => require('@vercel/blob').presignUrl(...args),
});
module.exports.createHandler = createHandler;
module.exports.buildStagingPathname = buildStagingPathname;
module.exports.ALLOWED_CONTENT_TYPES = ALLOWED_CONTENT_TYPES;
module.exports.MAX_SOURCE_BYTES = MAX_SOURCE_BYTES;
