import re

from backend.db.mongo import get_db
from backend.models.schemas import ValidationError
from backend.images import storage
from backend.images.processing import validate_and_process

# Matches exactly what routes/images.py's Node upload-token endpoint
# generates as a staging pathname (see api/blob-upload-token.js) — nothing
# else is ever accepted by process_staged_image, so an authenticated caller
# can't point it at an arbitrary existing key (e.g. another product's
# already-published image) and have it "reprocessed" as if newly uploaded.
STAGING_PATHNAME_RE = re.compile(r"^staging/[0-9a-f]{32}\.upload$")


def _upload_processed(processed):
    """Uploads already-validated/resized/WebP-converted main+thumbnail
    bytes to their final product keys, with the same rollback-on-partial-
    -failure behavior regardless of how `processed` was produced."""
    if not storage.is_configured():
        raise RuntimeError(
            "אחסון תמונות אינו מוגדר בסביבה זו (חסר BERESHIT_IMAGES_READ_WRITE_TOKEN). "
            "פנה למנהל המערכת להגדרת שירות אחסון."
        )

    main_key = storage.new_key("products", "webp")
    thumb_key = storage.new_key("products/thumbs", "webp")

    main_url = storage.upload_bytes(processed["main_bytes"], main_key, processed["content_type"])
    try:
        thumb_url = storage.upload_bytes(processed["thumb_bytes"], thumb_key, processed["content_type"])
    except Exception:
        # Don't leave an orphaned main image behind if the thumbnail half fails.
        storage.delete_object(main_url)
        raise

    return {
        "url": main_url,
        "thumbnailUrl": thumb_url,
        "width": processed["width"],
        "height": processed["height"],
    }


def upload_product_image(raw_bytes):
    """Direct-bytes entry point — validates then uploads. Kept for
    anything that already has the whole file in memory (e.g. tests);
    the real Admin upload flow goes through process_staged_image below,
    since a source photo can exceed Vercel's ~4.5MB function body limit
    and must never be sent through this server at all."""
    # Validate the file itself before ever checking storage configuration —
    # a bad upload is a 400 regardless of whether storage happens to be
    # configured in this environment; the two failure modes shouldn't be
    # conflated just because of check ordering.
    processed = validate_and_process(raw_bytes)
    return _upload_processed(processed)


def process_staged_image(pathname):
    """Completes the client-direct-upload flow: the browser already PUT
    the raw file straight to a temporary Blob path using a short-lived
    signed URL minted by api/blob-upload-token.js, bypassing this server
    entirely for that transfer — which is what keeps a large photo from
    ever hitting Vercel's function body-size limit. This step is what
    makes the server authoritative again: it fetches those raw bytes back
    and runs them through the exact same validation/resize/WebP pipeline
    as any other upload.

    Cleaning up the temporary staging blob afterward is deliberately
    best-effort and never allowed to affect the outcome, in either
    direction: it's still attempted whether the upload above succeeded
    or failed (nothing unvalidated should linger in the store just
    because the file itself was bad), but a cleanup failure — a
    transient Blob error, an unexpected URL shape — must never mask a
    real result: not a successful upload's return value, and not a real
    validation/processing error either. Deleting a leftover temp file is
    a cleanliness concern, never a reason to change what actually
    happened above."""
    if not STAGING_PATHNAME_RE.match(pathname or ""):
        raise ValidationError("נתיב העלאה זמני לא תקין")

    try:
        raw_bytes = storage.fetch_bytes(pathname)
        processed = validate_and_process(raw_bytes)
        result = _upload_processed(processed)
    finally:
        try:
            staged_url = storage.public_url_for_key(pathname)
            if staged_url:
                storage.delete_object(staged_url)
        except Exception:
            pass  # best-effort cleanup only — see docstring above

    return result


def delete_product_image(url):
    """Deletes an image from storage UNLESS another product still
    references that exact URL — the same "don't orphan a still-used
    resource" protection categories already get against deletion. A URL
    that isn't one of ours (e.g. a legacy admin-pasted external link) is
    silently left alone; there's nothing in our bucket to delete."""
    if not url:
        raise ValidationError("'url' is required")

    db = get_db()
    key = storage.key_from_url(url)
    if key is None:
        return {"deleted": False, "reason": "not_ours"}

    # `url` may be a main image or a thumbnail — either is safe to check
    # against both fields, since a URL only ever really lives in one of them.
    still_used = db.products.count_documents({"$or": [{"image": url}, {"thumbnail": url}]}) > 0
    if still_used:
        return {"deleted": False, "reason": "in_use"}

    storage.delete_object(url)
    return {"deleted": True}
