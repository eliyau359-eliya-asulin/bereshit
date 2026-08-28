"""Validates an uploaded file is actually a real, readable image (never
trusts the client's declared Content-Type or file extension), then
produces a display-sized main image and a small thumbnail — both
re-encoded as WebP, which is what keeps a 5MB source photo from ever
being shipped to a browser to render a 200px product card.
"""
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from backend.models.schemas import ValidationError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_SOURCE_BYTES = 8 * 1024 * 1024  # 8MB — generous for a phone photo, still a real ceiling
MAIN_MAX_EDGE = 1600
THUMB_MAX_EDGE = 400
MIN_EDGE = 80  # rejects e.g. a 1x1 tracking-pixel-style file masquerading as a product photo
WEBP_QUALITY = 82


def _resize_to_fit(img, max_edge):
    w, h = img.size
    if max(w, h) <= max_edge:
        return img
    scale = max_edge / max(w, h)
    return img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)


def _encode_webp(img, quality):
    buf = BytesIO()
    img.convert("RGB" if img.mode not in ("RGB", "RGBA") else img.mode).save(
        buf, format="WEBP", quality=quality, method=6
    )
    return buf.getvalue()


def validate_and_process(raw_bytes):
    """Returns {main_bytes, thumb_bytes, content_type, width, height}.
    Raises ValidationError (never a raw PIL/IO exception) on anything
    that isn't a real, acceptable image."""
    if not raw_bytes:
        raise ValidationError("לא התקבל קובץ")
    if len(raw_bytes) > MAX_SOURCE_BYTES:
        raise ValidationError(f"הקובץ גדול מדי — הגודל המרבי המותר הוא {MAX_SOURCE_BYTES // (1024*1024)}MB")

    try:
        probe = Image.open(BytesIO(raw_bytes))
        probe.verify()  # only checks structural integrity; the object is unusable afterward
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("הקובץ אינו תמונה תקינה")

    try:
        img = Image.open(BytesIO(raw_bytes))
        img.load()  # forces full decode now, not lazily inside the response cycle
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("הקובץ אינו תמונה תקינה")

    real_format = (img.format or "").upper()
    if real_format not in ALLOWED_FORMATS:
        raise ValidationError("סוג קובץ לא נתמך — יש להעלות JPG, PNG או WEBP בלבד")

    width, height = img.size
    if width < MIN_EDGE or height < MIN_EDGE:
        raise ValidationError(f"התמונה קטנה מדי (מינימום {MIN_EDGE}×{MIN_EDGE} פיקסלים)")

    # Strips EXIF/metadata as a side effect of re-encoding through a fresh
    # image buffer — nothing here ever writes the original bytes back out.
    main_img = _resize_to_fit(img, MAIN_MAX_EDGE)
    thumb_img = _resize_to_fit(img, THUMB_MAX_EDGE)

    return {
        "main_bytes": _encode_webp(main_img, WEBP_QUALITY),
        "thumb_bytes": _encode_webp(thumb_img, WEBP_QUALITY),
        "content_type": "image/webp",
        "width": main_img.size[0],
        "height": main_img.size[1],
    }
