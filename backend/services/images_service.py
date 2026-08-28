from backend.db.mongo import get_db
from backend.models.schemas import ValidationError
from backend.images import storage
from backend.images.processing import validate_and_process


def upload_product_image(raw_bytes):
    # Validate the file itself before ever checking storage configuration —
    # a bad upload is a 400 regardless of whether storage happens to be
    # configured in this environment; the two failure modes shouldn't be
    # conflated just because of check ordering.
    processed = validate_and_process(raw_bytes)

    if not storage.is_configured():
        raise RuntimeError(
            "אחסון תמונות אינו מוגדר בסביבה זו (חסרים משתני סביבה S3_*). "
            "פנה למנהל המערכת להגדרת שירות אחסון."
        )

    main_key = storage.new_key("products", "webp")
    thumb_key = storage.new_key("products/thumbs", "webp")

    main_url = storage.upload_bytes(processed["main_bytes"], main_key, processed["content_type"])
    try:
        thumb_url = storage.upload_bytes(processed["thumb_bytes"], thumb_key, processed["content_type"])
    except Exception:
        # Don't leave an orphaned main image behind if the thumbnail half fails.
        storage.delete_object(main_key)
        raise

    return {
        "url": main_url,
        "thumbnailUrl": thumb_url,
        "width": processed["width"],
        "height": processed["height"],
    }


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

    storage.delete_object(key)
    return {"deleted": True}
