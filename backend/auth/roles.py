"""Admin role/permission matrix. Roles are intentionally coarse — the UI
stays simple (a single role picker), but every admin-mutating route
checks a real permission server-side, never trusting a role claimed by
the browser. `g.admin`/`g.customer` (see decorators.py) are always
populated from the server-side session record, never from request data.
"""

SUPER_ADMIN = "super_admin"
ADMIN = "admin"
INVENTORY_MANAGER = "inventory_manager"
ORDERS_MANAGER = "orders_manager"
CONTENT_MANAGER = "content_manager"

ADMIN_ROLES = [SUPER_ADMIN, ADMIN, INVENTORY_MANAGER, ORDERS_MANAGER, CONTENT_MANAGER]

ROLE_LABELS = {
    SUPER_ADMIN: "מנהל-על",
    ADMIN: "מנהל",
    INVENTORY_MANAGER: "מנהל מלאי",
    ORDERS_MANAGER: "מנהל הזמנות",
    CONTENT_MANAGER: "מנהל תוכן",
}

_ALL_PERMISSIONS = {
    "products:write",     # create/delete/full edit of a product
    "products:stock",     # stock-only adjustment (inventory screen, barcode scanner)
    "categories:write",
    "orders:read",        # view the full order list / any order
    "orders:write",       # change order status/payment
    "customers:read",     # view the customer list / any customer record
    "promotions:write",
    "settings:write",     # store_info
    "admin_users:write",  # create/edit other admin accounts
}

ROLE_PERMISSIONS = {
    SUPER_ADMIN: set(_ALL_PERMISSIONS),
    ADMIN: set(_ALL_PERMISSIONS) - {"admin_users:write"},
    # Bulk import can rewrite name/price/description, not just stock — that's
    # full catalog authority ('products:write'), not the narrower stock-only
    # permission this role otherwise has.
    INVENTORY_MANAGER: {"products:stock", "orders:read"},
    ORDERS_MANAGER: {"orders:read", "orders:write", "customers:read"},
    CONTENT_MANAGER: {"categories:write", "promotions:write"},
}


def has_permission(role, required_permissions):
    """True if `role` grants ANY of `required_permissions` (an iterable).
    A route that accepts more than one permission is saying "any of these
    roles may call me at all" — finer-grained field-level checks (e.g.
    "this specific patch also touches non-stock fields") happen inside
    the route itself."""
    granted = ROLE_PERMISSIONS.get(role, set())
    return any(p in granted for p in required_permissions)
