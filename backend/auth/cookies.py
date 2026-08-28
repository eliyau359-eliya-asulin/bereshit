"""Cookie read/write helpers, kept in one place so every route sets the
same security flags. COOKIE_SECURE defaults to True (required for
SameSite=None-free, HTTPS-only cookies in production); it must be
explicitly set to false in a local plain-HTTP dev environment (see
.env.example) or the browser will silently refuse to store the cookie.
"""
from backend.config import Config

ADMIN_COOKIE = "bereshit_admin_session"
CUSTOMER_COOKIE = "bereshit_customer_session"


def set_session_cookie(response, name, token, expires_at):
    response.set_cookie(
        name,
        token,
        httponly=True,
        secure=Config.COOKIE_SECURE,
        samesite="Lax",
        expires=expires_at,
        path="/",
    )
    return response


def clear_session_cookie(response, name):
    response.delete_cookie(name, path="/", samesite="Lax", secure=Config.COOKIE_SECURE, httponly=True)
    return response
