"""Route decorators that resolve identity strictly from the server-side
session (see session_store.py) — never from any client-supplied id,
role, or header. This is the one place `request.cookies` is read for
auth purposes; every protected route goes through here.
"""
from functools import wraps

from flask import request, jsonify, g

from backend.auth.session_store import get_session, TYPE_ADMIN, TYPE_CUSTOMER
from backend.auth.roles import has_permission
from backend.auth.cookies import ADMIN_COOKIE, CUSTOMER_COOKIE


def _load_admin():
    if not hasattr(g, "_admin_loaded"):
        token = request.cookies.get(ADMIN_COOKIE)
        session = get_session(token)
        g.current_admin = session if session and session["userType"] == TYPE_ADMIN else None
        g._admin_loaded = True
    return g.current_admin


def _load_customer():
    if not hasattr(g, "_customer_loaded"):
        token = request.cookies.get(CUSTOMER_COOKIE)
        session = get_session(token)
        g.current_customer = session if session and session["userType"] == TYPE_CUSTOMER else None
        g._customer_loaded = True
    return g.current_customer


def get_current_admin():
    """Returns the session doc ({userId, role, ...}) or None. Safe to call
    from anywhere in a request (e.g. an endpoint that behaves differently
    for guests vs. logged-in customers, like checkout)."""
    return _load_admin()


def get_current_customer():
    return _load_customer()


def require_admin(*permissions):
    """Any of `permissions` grants access. No permissions given = any
    authenticated admin (still never an unauthenticated request)."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            admin = _load_admin()
            if not admin:
                return jsonify({"error": "נדרשת התחברות מנהל", "code": "UNAUTHENTICATED"}), 401
            if permissions and not has_permission(admin.get("role"), permissions):
                return jsonify({"error": "אין הרשאה מספקת לפעולה זו", "code": "FORBIDDEN"}), 403
            g.admin = admin
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_customer(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        customer = _load_customer()
        if not customer:
            return jsonify({"error": "נדרשת התחברות", "code": "UNAUTHENTICATED"}), 401
        g.customer = customer
        return fn(*args, **kwargs)
    return wrapper
