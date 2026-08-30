"""
Field shapes mirror shared/models.js (the JSDoc typedefs the frontend was
already built against) — this is the same data model, just enforced here
before anything is written to MongoDB.
"""

from urllib.parse import urlparse

from backend.auth.roles import ADMIN_ROLES  # noqa: F401  (re-exported for callers that validate a role string)

NUMBER = (int, float)


class ValidationError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def validate_image_url(value, field_name="image"):
    """Product `image`/`thumbnail` URLs come from three places: our own
    upload pipeline (always https://*.public.blob.vercel-storage.com/...),
    an admin manually pasting a link, or an imported CSV/Excel ImageURL
    column — the last two are untrusted strings that end up in a
    customer's <img src="...">. Only http(s) is ever acceptable; this is
    what stops a `javascript:`/`data:`/`vbscript:` value from being
    stored at all, rather than relying solely on the frontend to filter
    it out at render time."""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValidationError(f"'{field_name}' must be a string URL")
    scheme = urlparse(value).scheme.lower()
    if scheme not in ("http", "https"):
        raise ValidationError(f"'{field_name}' must be a valid http(s) URL")
    return value


def validate_fields(data, spec, partial=False):
    """spec: {field: (type_or_tuple_of_types, required)}.
    In partial mode (PUT), only fields present in `data` are checked and
    `required` is ignored — you can patch a single field without resending
    the whole document."""
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object")

    errors = []
    for field, (types, required) in spec.items():
        if field in data:
            value = data[field]
            if value is not None and not isinstance(value, types):
                expected = types if isinstance(types, tuple) else (types,)
                names = ", ".join(t.__name__ for t in expected)
                errors.append(f"'{field}' must be of type: {names}")
        elif required and not partial:
            errors.append(f"'{field}' is required")

    if errors:
        raise ValidationError("; ".join(errors))


PRODUCT_SPEC = {
    "sku": (str, True),
    "barcode": (str, False),  # standard product barcode (EAN/UPC) — used by the admin barcode scanner to look up a product
    "cat": (str, True),
    "catLabel": (str, True),
    "name": (str, True),
    "price": (NUMBER, True),
    "oldPrice": (NUMBER, False),
    "badge": (str, False),
    "short": (str, False),
    "desc": (str, False),
    "material": (str, False),
    "dim": (str, False),
    "stock": (int, True),
    "threshold": (int, True),
    "status": (str, False),
    "sold": (int, False),
    "image": (str, False),  # URL/path to a hosted product photo; None = use the UI's placeholder
    "thumbnail": (str, False),  # small resized variant of `image` from the upload pipeline; tracked so it can be cleaned up on replace/delete
}

# Valid forward workflow. Cancellation ("בוטל") is allowed from either of
# the first two states only — handled as a special case in orders_service,
# not in this table, since it's not a "next step" but a side-exit.
ORDER_STATUS_FLOW = ["ממתין לאישור", "בטיפול", "נשלח", "נמסר"]
ORDER_CANCELLABLE_FROM = {"ממתין לאישור", "בטיפול"}

ORDER_UPDATE_SPEC = {
    "status": (str, False),
    "pay": (str, False),
}

PROMOTION_SPEC = {
    "name": (str, True),
    "code": (str, True),
    "discount": (NUMBER, True),
    "start": (str, True),
    "end": (str, True),
    "status": (str, False),
}

CATEGORY_SPEC = {
    "key": (str, True),
    "label": (str, True),
    "status": (str, False),
    "order": (int, False),
}

STORE_INFO_SPEC = {
    "name": (str, False),
    "email": (str, False),
    "phone": (str, False),
    "address": (str, False),
    "currency": (str, False),
    "description": (str, False),
    "shippingCost": (NUMBER, False),
    "freeShippingThreshold": (NUMBER, False),
    "paymentMethods": (list, False),
}

CUSTOMER_REGISTER_SPEC = {
    "name": (str, True),
    "email": (str, True),
    "phone": (str, True),
    "password": (str, True),
}

CUSTOMER_LOGIN_SPEC = {
    "email": (str, True),
    "password": (str, True),
}

CUSTOMER_PROFILE_UPDATE_SPEC = {
    "name": (str, False),
    "phone": (str, False),
}

ADMIN_USER_CREATE_SPEC = {
    "name": (str, True),
    "email": (str, True),
    "password": (str, True),
    "role": (str, True),
}

ADMIN_USER_UPDATE_SPEC = {
    "name": (str, False),
    "role": (str, False),
    "active": (bool, False),
}

ADMIN_LOGIN_SPEC = {
    "email": (str, True),
    "password": (str, True),
}
