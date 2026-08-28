"""External object storage for product images — an S3-compatible bucket
(real AWS S3, or any S3-compatible provider: Cloudflare R2, Backblaze B2,
DigitalOcean Spaces, MinIO, ...). This is the one place that talks to
that bucket; everything else works with (bytes, content_type) in and a
public URL out.

Deliberately S3-compatible rather than tied to one vendor's proprietary
SDK/protocol: boto3 is AWS's official client and implements the real,
stable, unchanged-for-a-decade S3 REST API, so this works correctly
against any of the providers above just by pointing S3_ENDPOINT_URL at
them — no vendor lock-in, and no risk of this code being built against a
guessed-at, undocumented API shape.

No credentials are hardcoded anywhere — see .env.example for the
required variables. If they aren't set, is_configured() is False and
every route that needs storage returns a clear 503 rather than silently
pretending to succeed.
"""
import os
import uuid

_client = None


def _config():
    return {
        "bucket": os.environ.get("S3_BUCKET_NAME"),
        "access_key": os.environ.get("S3_ACCESS_KEY_ID"),
        "secret_key": os.environ.get("S3_SECRET_ACCESS_KEY"),
        "region": os.environ.get("S3_REGION", "us-east-1"),
        "endpoint_url": os.environ.get("S3_ENDPOINT_URL") or None,
        "public_base_url": os.environ.get("S3_PUBLIC_BASE_URL"),
        # Classic AWS S3 buckets grant public read via an object ACL; most
        # S3-compatible providers (R2, Backblaze, Spaces) instead manage
        # public access at the bucket level and reject/ignore ACL params.
        # Off by default so this works out of the box against those; a
        # real AWS S3 bucket that isn't otherwise public needs this on.
        "use_public_acl": os.environ.get("S3_USE_PUBLIC_ACL", "false").strip().lower() in ("1", "true", "yes"),
    }


def is_configured():
    cfg = _config()
    return bool(cfg["bucket"] and cfg["access_key"] and cfg["secret_key"] and cfg["public_base_url"])


def _get_client():
    global _client
    if _client is None:
        import boto3
        cfg = _config()
        _client = boto3.client(
            "s3",
            aws_access_key_id=cfg["access_key"],
            aws_secret_access_key=cfg["secret_key"],
            region_name=cfg["region"],
            endpoint_url=cfg["endpoint_url"],
        )
    return _client


def new_key(prefix, extension):
    return f"{prefix.strip('/')}/{uuid.uuid4().hex}.{extension.lstrip('.')}"


def upload_bytes(data, key, content_type):
    """Uploads `data` under `key`, returns the public URL to store on the
    product document. Raises whatever boto3 raises on failure — the route
    layer turns that into a clean error response, never a raw exception
    reaching the client."""
    cfg = _config()
    if not is_configured():
        raise RuntimeError("Image storage is not configured (S3_* environment variables missing)")

    kwargs = {"Bucket": cfg["bucket"], "Key": key, "Body": data, "ContentType": content_type,
              "CacheControl": "public, max-age=31536000, immutable"}
    if cfg["use_public_acl"]:
        kwargs["ACL"] = "public-read"

    _get_client().put_object(**kwargs)
    base = cfg["public_base_url"].rstrip("/")
    return f"{base}/{key}"


def delete_object(key):
    cfg = _config()
    if not is_configured():
        return
    _get_client().delete_object(Bucket=cfg["bucket"], Key=key)


def key_from_url(url):
    """Recovers the storage key from a URL previously returned by
    upload_bytes — the inverse of the base-url join above. Returns None
    for a URL that isn't one of ours (e.g. a legacy admin-pasted URL, or
    a locally-embedded placeholder), so callers can skip deletion instead
    of trying to delete something that was never in this bucket."""
    cfg = _config()
    base = (cfg["public_base_url"] or "").rstrip("/")
    if not base or not url or not url.startswith(base + "/"):
        return None
    return url[len(base) + 1:]
