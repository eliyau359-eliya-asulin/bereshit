/* Shared HTML/URL-safety helpers used by both the customer storefront
 * (index.html) and the admin dashboard (admin/js/admin.js) — one
 * implementation, so a fix here can never drift out of sync between the
 * two surfaces. Framework-free and effectively DOM-free (the only
 * optional DOM touch is defaulting to window.location inside
 * safeImageUrl), so it runs directly under plain Node with no browser —
 * see shared/tests/security.test.js.
 */
(function (root) {
  'use strict';

  // The one HTML-escaping routine every dynamic/DB-controlled string
  // must pass through before landing inside an innerHTML template
  // string (either as text content or inside a double-quoted HTML
  // attribute) — never trust product names, customer names, order data,
  // category/promotion names, imported spreadsheet values, or anything
  // else that ultimately came from a database record or an uploaded file.
  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  // Safe for a value embedded as a single-quoted JS string literal
  // *inside* an inline HTML event-handler attribute, e.g.
  // onclick="fn('VALUE')" — escapeHtml alone only guards the outer
  // double-quoted HTML attribute; this also escapes an embedded `'` so
  // the value can't break out of the inner JS string and inject its own
  // script.
  function escapeJsAttr(value) {
    return escapeHtml(String(value == null ? '' : value).replace(/\\/g, '\\\\').replace(/'/g, "\\'"));
  }

  // Only ever returns an http(s) absolute URL or null — never lets a
  // `javascript:`, `data:`, `vbscript:`, a bare relative path, or any
  // other unexpected value reach an <img src> or similar, regardless of
  // where it came from (our own Vercel Blob upload pipeline, an
  // admin-pasted link, or an imported spreadsheet ImageURL column). The
  // backend enforces the same rule at write time (see validate_image_url
  // in backend/models/schemas.py); this is that rule enforced again at
  // the render boundary, so a legacy/bad value already sitting in
  // MongoDB can't do anything unsafe in the browser either.
  //
  // Deliberately requires an explicit http(s):// prefix rather than
  // resolving against a base URL (as `new URL(url, base)` would) — a
  // relative/garbage string has no business being "safe" just because
  // it happens to resolve against the current page's own origin.
  function safeImageUrl(url) {
    if (!url || typeof url !== 'string' || !/^https?:\/\//i.test(url)) return null;
    try {
      var parsed = new URL(url);
      return (parsed.protocol === 'http:' || parsed.protocol === 'https:') ? url : null;
    } catch (e) {
      return null;
    }
  }

  var api = { escapeHtml: escapeHtml, escapeJsAttr: escapeJsAttr, safeImageUrl: safeImageUrl };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  if (root) {
    root.BereshitSecurity = api;
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : null));
