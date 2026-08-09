"""Password hashing and session tokens for the local admin login.

Deliberately without a new dependency. `hashlib.scrypt` is in the standard
library, memory-hard and parameterised here the way OWASP recommends; PyJWT is
already required for the Entra ID path and signs the session tokens.

The local login exists for one reason: if Entra ID is unreachable or an app
registration is broken, somebody still has to get into the tool. It is
therefore treated as the emergency door it is - the initial password must be
changed before anything else works, failed attempts lock the account for a
while, and every login lands in the audit log.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from .config import settings

try:  # pragma: no cover - the dependency is required, the guard mirrors auth.py
    import jwt
except Exception:  # pragma: no cover
    jwt = None  # type: ignore[assignment]

# OWASP baseline for scrypt (2023): N = 2^15, r = 8, p = 1.
SCRYPT_N = 32768
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
KEY_BYTES = 32
# 128 * N * r is 32 MiB at these parameters, which is exactly OpenSSL's default
# ceiling - so it has to be raised explicitly or the hash refuses to compute.
SCRYPT_MAXMEM = 96 * 1024 * 1024

TOKEN_ISSUER = "niederlassung-ops"
TOKEN_TYPE = "session"

MIN_PASSWORD_LENGTH = 12
# Wrong password this often in a row and the account rests for a while. Aimed
# at an attacker guessing, not at the colleague who mistyped twice.
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; PostgreSQL does not.

    Comparing the two raises, so anything read from the database is pinned to
    UTC before it meets `datetime.now(timezone.utc)`.
    """
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    """Returns a self-describing hash, so the parameters can be raised later."""
    salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=KEY_BYTES,
        maxmem=SCRYPT_MAXMEM,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(derived)}"


def verify_password(password: str, encoded: str | None) -> bool:
    """Constant-time check against a stored hash.

    A missing hash returns False rather than raising: an account without a
    password simply cannot use the password login.
    """
    if not encoded:
        return False
    try:
        scheme, n, r, p, salt, expected = encoded.split("$")
        if scheme != "scrypt":
            return False
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_unb64(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(_unb64(expected)),
            maxmem=SCRYPT_MAXMEM,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived, _unb64(expected))


def password_problem(password: str, *, display_name: str = "", email: str = "") -> str | None:
    """German-language complaint about a new password, or None when it passes.

    Length first, because it is what actually matters; the character classes
    stop the "Sommer2026!!" school of password and nothing more.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Das Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein."
    classes = sum(
        [
            any(character.islower() for character in password),
            any(character.isupper() for character in password),
            any(character.isdigit() for character in password),
            any(not character.isalnum() for character in password),
        ]
    )
    if classes < 3:
        return (
            "Das Passwort muss mindestens drei der vier Arten enthalten: "
            "Kleinbuchstaben, Grossbuchstaben, Ziffern, Sonderzeichen."
        )
    lowered = password.casefold()
    for part in (display_name, email.split("@")[0] if email else ""):
        if len(part) >= 4 and part.casefold() in lowered:
            return "Das Passwort darf den Namen oder die Anmeldung nicht enthalten."
    if lowered == settings.admin_initial_password.casefold():
        return "Das Startpasswort kann nicht als neues Passwort gesetzt werden."
    return None


# --------------------------------------------------------------------------
# Session tokens
# --------------------------------------------------------------------------

# Set once per process when no secret is configured. Sessions then end with a
# restart, which is the right trade for a local test run and refused outright
# in production (see config.Settings._validate).
_EPHEMERAL_SECRET = secrets.token_urlsafe(48)


def session_secret() -> str:
    return settings.auth_session_secret or _EPHEMERAL_SECRET


def issue_session(user_id: str, token_version: int) -> tuple[str, datetime]:
    """Signs a session token and returns it with its expiry.

    `token_version` is the revocation handle: changing a password or
    deactivating an account raises it and every token issued before stops
    being accepted, without a session table to keep clean.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.auth_session_hours)
    payload = {
        "iss": TOKEN_ISSUER,
        "typ": TOKEN_TYPE,
        "sub": user_id,
        "tv": token_version,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, session_secret(), algorithm="HS256"), expires_at


def read_session(token: str) -> dict | None:
    """Returns the claims of a local session token, or None if it is not one.

    None also covers an expired or tampered token; the caller cannot tell the
    difference and does not need to.
    """
    try:
        claims = jwt.decode(
            token,
            session_secret(),
            algorithms=["HS256"],
            issuer=TOKEN_ISSUER,
            options={"require": ["exp", "sub", "iss"]},
        )
    except Exception:
        return None
    return claims if claims.get("typ") == TOKEN_TYPE else None


def looks_like_session(token: str) -> bool:
    """Cheap pre-check: is this our own token rather than an Entra ID one?

    Read from the unverified header and issuer claim, so a request under
    AUTH_MODE=azure_ad is not sent through both validators every time.
    """
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "HS256":
            return False
        claims = jwt.decode(token, options={"verify_signature": False})
    except Exception:
        return False
    return claims.get("iss") == TOKEN_ISSUER
