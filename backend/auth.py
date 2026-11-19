import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import schemas
from .database import BASE_DIR, get_db

load_dotenv(BASE_DIR / ".env")

SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64

bearer_scheme = HTTPBearer(auto_error=False)


def _get_session_ttl_hours() -> int:
    raw = os.getenv("SESSION_TTL_HOURS", "24")
    try:
        hours = int(raw)
        return hours if hours > 0 else 24
    except ValueError:
        return 24


def hash_password(password: str) -> str:
    """Hash a plaintext password using scrypt with a random 16-byte salt."""
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return f"scrypt${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored scrypt hash in constant time."""
    try:
        algorithm, salt_hex, expected_hex = stored_hash.split("$", 2)
        if algorithm != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(expected_hex)
    except ValueError:
        return False

    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=len(expected),
    )
    return hmac.compare_digest(derived, expected)


def verify_master_password(provided_password: str) -> None:
    """Validate the registration master password configured in .env."""
    load_dotenv(BASE_DIR / ".env", override=False)
    expected = os.getenv("REGISTRATION_MASTER_PASSWORD", "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Registrace není nakonfigurována (chybí REGISTRATION_MASTER_PASSWORD v .env).",
        )
    if not hmac.compare_digest(provided_password, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Neplatné master heslo.",
        )


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: sqlite3.Connection, user_id: int) -> str:
    """Create a new server-side session and return the raw bearer token."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=_get_session_ttl_hours())
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)

    db.execute(
        "DELETE FROM sessions WHERE expires_at <= ?",
        (now.strftime("%Y-%m-%dT%H:%M:%SZ"),),
    )
    db.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (token_hash, user_id, expires_at.strftime("%Y-%m-%dT%H:%M:%SZ")),
    )
    db.commit()
    return token


def revoke_session(db: sqlite3.Connection, token: str) -> None:
    """Revoke an existing session token."""
    db.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))
    db.commit()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: sqlite3.Connection = Depends(get_db),
) -> schemas.UserResponse:
    """FastAPI dependency enforcing valid Bearer token authentication."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Pro přístup k backendu je nutné přihlášení.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_hash = _hash_token(credentials.credentials)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    row = db.execute(
        """
        SELECT u.id, u.username, u.farnost, u.created_at, s.expires_at
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ?
        """,
        (token_hash,),
    ).fetchone()

    if not row or row["expires_at"] <= now_str:
        if row:
            db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Relace vypršela nebo je neplatná. Přihlaste se prosím znovu.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return schemas.UserResponse(
        id=row["id"],
        username=row["username"],
        farnost=row["farnost"],
        created_at=row["created_at"],
    )
