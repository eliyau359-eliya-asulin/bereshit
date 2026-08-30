/* Regression tests for shared/security.js — the HTML-escaping and
 * image-URL-scheme validation used by both index.html and
 * admin/js/admin.js. Run with plain Node (no dependencies, no build
 * step):
 *
 *   node --test shared/tests/security.test.js
 *
 * These prove the *escaping* contract holds for the representative XSS
 * payloads named in the security audit. They do not (and cannot,
 * without a real DOM/browser) prove that every call site in index.html
 * and admin.js actually applies escapeHtml/safeImageUrl — that was
 * verified by direct code audit of every innerHTML template site in
 * both files.
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { escapeHtml, escapeJsAttr, safeImageUrl } = require(path.join(__dirname, '..', 'security.js'));

// ---------------------------------------------------------------------
// escapeHtml — used for every product/customer/order/category/promotion
// field rendered via innerHTML, in both the customer storefront and the
// admin dashboard.
// ---------------------------------------------------------------------

test('escapeHtml neutralizes a raw <script> tag', () => {
  const out = escapeHtml('<script>alert(1)</script>');
  assert.equal(out, '&lt;script&gt;alert(1)&lt;/script&gt;');
  assert.ok(!out.includes('<script>'));
});

test('escapeHtml neutralizes an event-handler payload', () => {
  const out = escapeHtml('<img src=x onerror=alert(1)>');
  assert.ok(!out.includes('<img'));
  assert.equal(out, '&lt;img src=x onerror=alert(1)&gt;');
});

test('escapeHtml neutralizes an attribute-breakout payload', () => {
  const out = escapeHtml('"><img src=x onerror=alert(1)>');
  assert.ok(!out.includes('"'));
  assert.ok(!out.includes('<img'));
});

test('escapeHtml is a no-op on plain Hebrew/English/number text', () => {
  assert.equal(escapeHtml('גביע קידוש כסף 925'), 'גביע קידוש כסף 925');
  assert.equal(escapeHtml('Kiddush Cup 199'), 'Kiddush Cup 199');
});

test('escapeHtml treats null/undefined as empty string, never "null"/"undefined"', () => {
  assert.equal(escapeHtml(null), '');
  assert.equal(escapeHtml(undefined), '');
});

// ---------------------------------------------------------------------
// escapeJsAttr — for a value embedded inside a single-quoted JS string
// literal *inside* an inline event-handler attribute, e.g.
// onclick="selectCategory('VALUE')" (used for the category key).
// ---------------------------------------------------------------------

test('escapeJsAttr escapes every single quote so none can break out of the JS string', () => {
  const payload = "x'); alert(1); ('";
  const out = escapeJsAttr(payload);
  // Every quote in the output must be an escaped \' , never a bare '.
  assert.equal(/(?<!\\)'/.test(out), false);
  // Reconstructed exactly as the app does: onclick="selectCategory('VALUE')" —
  // only the two literal string-delimiter quotes are ever unescaped.
  const attr = `onclick="selectCategory('${out}')"`;
  const bareQuotesInsideValue = out.match(/(?<!\\)'/g) || [];
  assert.equal(bareQuotesInsideValue.length, 0);
});

test('escapeJsAttr still HTML-escapes the outer double-quote context', () => {
  const out = escapeJsAttr('"><script>alert(1)</script>');
  assert.ok(!out.includes('"'));
  assert.ok(!out.includes('<script>'));
});

// ---------------------------------------------------------------------
// safeImageUrl — the scheme allowlist for every <img src> on both
// surfaces (product/category photos): only http(s) may ever pass.
// ---------------------------------------------------------------------

test('safeImageUrl rejects a javascript: URL', () => {
  assert.equal(safeImageUrl('javascript:alert(1)'), null);
});

test('safeImageUrl rejects a data: URL', () => {
  assert.equal(safeImageUrl('data:text/html,<script>alert(1)</script>'), null);
});

test('safeImageUrl rejects a vbscript: URL', () => {
  assert.equal(safeImageUrl('vbscript:msgbox(1)'), null);
});

test('safeImageUrl accepts a real Vercel Blob https URL unchanged', () => {
  const url = 'https://abc123.public.blob.vercel-storage.com/products/x.webp';
  assert.equal(safeImageUrl(url), url);
});

test('safeImageUrl accepts a plain http(s) URL unchanged (e.g. an imported ImageURL)', () => {
  const url = 'https://example.com/photo.jpg';
  assert.equal(safeImageUrl(url), url);
});

test('safeImageUrl returns null for empty/missing input rather than throwing', () => {
  assert.equal(safeImageUrl(null), null);
  assert.equal(safeImageUrl(undefined), null);
  assert.equal(safeImageUrl(''), null);
});

test('safeImageUrl rejects a relative/schemeless path outright, never resolving it against any base', () => {
  assert.equal(safeImageUrl('/products/photo.jpg'), null);
  assert.equal(safeImageUrl('photo.jpg'), null);
  assert.equal(safeImageUrl('//evil.com/photo.jpg'), null);
});

test('safeImageUrl never throws on a malformed string', () => {
  assert.doesNotThrow(() => safeImageUrl('not a url at all :://'));
  assert.equal(safeImageUrl('not a url at all :://'), null);
});
