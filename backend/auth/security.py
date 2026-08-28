"""Password hashing and session-token primitives. Passwords are never
stored or logged in plaintext — only their salted PBKDF2 hash (via
werkzeug.security, already a Flask dependency, so no extra package is
needed). Session tokens are opaque random values; only their SHA-256
hash is ever persisted, so a database read/dump never reveals a usable
cookie value.
"""
import hashlib
import secrets

from werkzeug.security import generate_password_hash, check_password_hash


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        return check_password_hash(password_hash, password)
    except ValueError:
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
