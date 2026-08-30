"""External object storage for product images — Vercel Blob. This is the
one place that talks to the Blob REST API; everything else works with
(bytes, content_type) in and a public URL out, exactly as before.

Why Vercel Blob's public storage, specifically: a Vercel Blob store's
access mode (public vs. private) is fixed at creation and cannot be
switched later. Private blobs require an authenticated request for
*every* read (no auth = no image), which is unusable for a customer
storefront <img src="...">. Public blobs are served at a stable,
unguessable URL (https://<store-id>.public.blob.vercel-storage.com/...)
that loads directly in a browser with no token involved — the only
architecture here that gives direct browser loading without ever
shipping a read/write credential to the client. See .env.example for
the exact store setup this requires.

No credentials are hardcoded anywhere. BERESHIT_IMAGES_READ_WRITE_TOKEN
is the long-lived read-write token Vercel adds automatically to a
project once the `bereshit-images-public` store is connected to it
(under a custom "BERESHIT_IMAGES" variable prefix, chosen when
connecting the store — the default unprefixed BLOB_READ_WRITE_TOKEN/
BLOB_STORE_ID names belong to a different, no-longer-used store and are
never read here). If it isn't set, is_configured() is False and every
route that needs storage returns a clear 503 rather than silently
pretending to succeed.
"""
import os
import re
import uuid
from urllib.parse import unquote, urlparse

import requests

_BLOB_API_BASE = "https://blob.vercel-storage.com"
# Vercel's Blob REST API is versioned via this header; bump if Vercel
# advances the required version and old uploads start failing. Verified
# against the currently-pinned @vercel/blob@2.8.0's own compiled source
# (its BLOB_API_VERSION constant) rather than guessed — an earlier,
# out-of-date value here (paired with the wrong access-mode header name
# below) is what caused a real "Invalid pathname" rejection in production.
_API_VERSION = "12"
_REQUEST_TIMEOUT = 20
# Every object in a public Blob store is served from this fixed domain
# suffix (the store-id subdomain varies, the suffix never does) — used
# to recognize "one of ours" without needing a separately configured
# public base URL the way the old S3 code did.
_PUBLIC_BLOB_HOST_SUFFIX = ".public.blob.vercel-storage.com"
# A real hostname: dot-separated labels of letters/digits/hyphens only
# (RFC 1035) — never underscores or anything else. Belt-and-suspenders
# against ever handing Vercel Blob's delete API a URL whose host is
# malformed for any reason (a bad env var, a future bug in how a URL
# gets built, ...): if the host doesn't even look like a real hostname,
# it's rejected here before it can ever reach that API and fail there
# with an opaque "malformed" error instead.
_VALID_HOSTNAME_RE = re.compile(
    r"^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)*$"
)


def _token():
    return os.environ.get("BERESHIT_IMAGES_READ_WRITE_TOKEN")


def _store_id():
    # Vercel adds this automatically once bereshit-images-public is
    # "Connected to Project" (Storage tab -> store -> Projects -> Connect
    # to Project) — separate from just adding the read-write token to the
    # project's env vars. Vercel provisions the value WITH a "store_"
    # prefix (e.g. "store_abc123xyz"); the public CDN hostname uses only
    # the bare id after that prefix (confirmed by reading @vercel/blob's
    # own compiled source: it strips this exact prefix in a helper it
    # calls normalizeStoreId before building any URL). Passing the raw
    # "store_..." value straight into a hostname produces an invalid host
    # (underscores aren't a legal DNS label character), which is what
    # caused Vercel Blob's delete API to reject it as malformed.
    raw = os.environ.get("BERESHIT_IMAGES_STORE_ID", "").strip()
    return raw[len("store_"):] if raw.startswith("store_") else raw


def _store_id_from_token(token):
    """The current Blob API requires an explicit x-vercel-blob-store-id
    header on every authenticated control-plane request (upload/delete) —
    confirmed the same way as everything else in this module, by reading
    @vercel/blob's compiled source (its resolveBlobAuth/
    parseStoreIdFromReadWriteToken). It derives that id from the
    read-write token itself (format: vercel_blob_rw_<storeId>_<secret>,
    so index 3 after splitting on "_"), not from BERESHIT_IMAGES_STORE_ID
    — deliberately, so this keeps working even if that separate env var
    were ever missing or stale."""
    if not token:
        return ""
    parts = token.split("_")
    return parts[3] if len(parts) > 3 else ""


def is_configured():
    return bool(_token())


def new_key(prefix, extension):
    return f"{prefix.strip('/')}/{uuid.uuid4().hex}.{extension.lstrip('.')}"


def public_url_for_key(key):
    """Constructs the public CDN URL for `key` from BERESHIT_IMAGES_STORE_ID,
    without needing a round-trip to the Blob API. Only meaningful for a
    public store (see the module docstring) — every object in one lives
    at this fixed, documented URL shape. Returns None if
    BERESHIT_IMAGES_STORE_ID isn't set."""
    store_id = _store_id()
    if not store_id or not key:
        return None
    return f"https://{store_id}.public.blob.vercel-storage.com/{key}"


def fetch_bytes(key):
    """Fetches the raw bytes of a public blob by its storage key (pathname).
    Used to read back a file the browser uploaded directly to Blob (see
    the client-upload-token flow in routes/images.py) so it can be
    validated/processed server-side. A public blob needs no authentication
    to read — this is the same plain GET a customer's browser makes."""
    url = public_url_for_key(key)
    if not url:
        raise RuntimeError("Image storage is not configured (BERESHIT_IMAGES_STORE_ID missing)")
    try:
        resp = requests.get(url, timeout=_REQUEST_TIMEOUT)
    except requests.RequestException as e:
        raise RuntimeError(f"Vercel Blob fetch request failed: {e}") from e
    if resp.status_code != 200:
        raise RuntimeError(f"Could not fetch staged upload ({resp.status_code})")
    return resp.content


def upload_bytes(data, key, content_type):
    """Uploads `data` under `key` to the public Blob store, returns the
    public URL to store on the product document. Raises RuntimeError on
    failure — the route layer turns that into a clean error response,
    never a raw exception reaching the client."""
    if not is_configured():
        raise RuntimeError("Image storage is not configured (BERESHIT_IMAGES_READ_WRITE_TOKEN missing)")

    headers = {
        "authorization": f"Bearer {_token()}",
        "x-api-version": _API_VERSION,
        "x-vercel-blob-store-id": _store_id_from_token(_token()),
        # Required by the Blob API on every write; must match the access
        # mode the target store was actually created with (see the module
        # docstring) — a private store rejects this. Header name (not the
        # more obvious plain "access") verified against the current SDK's
        # compiled source.
        "x-vercel-blob-access": "public",
        "x-content-type": content_type,
        # `key` is already an unguessable uuid4 (see new_key) — no random
        # suffix needed, which also keeps the returned URL's path exactly
        # equal to `key`, so key_from_url below is a plain inverse.
        "x-add-random-suffix": "0",
        "x-cache-control-max-age": "31536000",
    }
    try:
        resp = requests.put(
            _BLOB_API_BASE,
            params={"pathname": key},
            headers=headers,
            data=data,
            timeout=_REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Vercel Blob upload request failed: {e}") from e
    if resp.status_code != 200:
        raise RuntimeError(f"Vercel Blob upload failed ({resp.status_code}): {resp.text[:300]}")
    return resp.json()["url"]


def delete_object(url):
    """Deletes the blob at `url`. A no-op (never raises) if storage isn't
    configured or `url` isn't one of ours — the same "don't touch
    something that was never in our store" protection the old S3 code
    had, now enforced here directly rather than relying on every caller
    to check first."""
    if not is_configured() or key_from_url(url) is None:
        return
    try:
        resp = requests.post(
            f"{_BLOB_API_BASE}/delete",
            headers={
                "authorization": f"Bearer {_token()}",
                "x-api-version": _API_VERSION,
                "x-vercel-blob-store-id": _store_id_from_token(_token()),
            },
            json={"urls": [url]},
            timeout=_REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Vercel Blob delete request failed: {e}") from e
    if resp.status_code != 200:
        raise RuntimeError(f"Vercel Blob delete failed ({resp.status_code}): {resp.text[:300]}")


def key_from_url(url):
    """Recovers the storage key (the Blob `pathname`) from a URL
    previously returned by upload_bytes. Returns None for a URL that
    isn't one of ours (a legacy/admin-pasted external link, an imported
    ImageURL, a locally-embedded placeholder, a malformed value, or a
    relative/empty/None one), so callers can skip deletion instead of
    trying to delete something that was never in this store — and so
    Vercel Blob's delete API is never handed a URL it would itself
    reject as malformed."""
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.scheme != "https":
        return None
    if not parsed.netloc or not _VALID_HOSTNAME_RE.match(parsed.netloc):
        return None
    if not parsed.netloc.endswith(_PUBLIC_BLOB_HOST_SUFFIX):
        return None
    key = unquote(parsed.path.lstrip("/"))
    return key or None
