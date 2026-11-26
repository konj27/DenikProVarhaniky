from collections import defaultdict, deque
import hashlib
import hmac
import math
import os
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import schemas
from .database import BASE_DIR, get_db

load_dotenv(BASE_DIR / ".env")

SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64

bearer_scheme = HTTPBearer(auto_error=False)


def _get_env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


class _SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding window rate limiter for auth endpoints."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        cutoff = now - self.window_seconds
        bucket = self._attempts[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        return bucket

    def check(self, key: str, action_label: str) -> None:
        now = time.monotonic()
        with self._lock:
            bucket = self._prune(key, now)
            if len(bucket) >= self.max_attempts:
                retry_after = max(1, math.ceil(self.window_seconds - (now - bucket[0])))
                minutes = math.ceil(retry_after / 60)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Příliš mnoho neúspěšných pokusů o {action_label}. Zkuste to prosím znovu za {minutes} min.",
                    headers={"Retry-After": str(retry_after)},
                )
            if not bucket:
                self._attempts.pop(key, None)

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            bucket = self._prune(key, now)
            bucket.append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)


_login_user_limiter = _SlidingWindowRateLimiter(
    max_attempts=_get_env_int("LOGIN_MAX_ATTEMPTS", 5),
    window_seconds=_get_env_int("LOGIN_WINDOW_SECONDS", 900),
)
_login_ip_limiter = _SlidingWindowRateLimiter(
    max_attempts=_get_env_int("LOGIN_IP_MAX_ATTEMPTS", 20),
    window_seconds=_get_env_int("LOGIN_WINDOW_SECONDS", 900),
)
_register_ip_limiter = _SlidingWindowRateLimiter(
    max_attempts=_get_env_int("REGISTER_MAX_ATTEMPTS", 10),
    window_seconds=_get_env_int("REGISTER_WINDOW_SECONDS", 900),
)


def get_client_ip(request: Request) -> str:
    """Extract client IP address from the FastAPI request."""
    return request.client.host if request.client and request.client.host else "unknown"


def check_login_rate_limit(username: str, client_ip: str) -> None:
    user_key = username.strip().lower()
    if user_key:
        _login_user_limiter.check(user_key, "přihlášení")
    _login_ip_limiter.check(client_ip, "přihlášení")


def record_login_failure(username: str, client_ip: str) -> None:
    user_key = username.strip().lower()
    if user_key:
        _login_user_limiter.record_failure(user_key)
    _login_ip_limiter.record_failure(client_ip)


def reset_login_rate_limit(username: str) -> None:
    user_key = username.strip().lower()
    if user_key:
        _login_user_limiter.reset(user_key)


def check_register_rate_limit(client_ip: str) -> None:
    _register_ip_limiter.check(client_ip, "registraci")


def record_register_failure(client_ip: str) -> None:
    _register_ip_limiter.record_failure(client_ip)


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
        SELECT u.id, u.username, u.farnost, u.is_admin, u.created_at, s.expires_at
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
        is_admin=bool(row["is_admin"]),
        created_at=row["created_at"],
    )


def require_admin(
    current_user: schemas.UserResponse = Depends(get_current_user),
) -> schemas.UserResponse:
    """FastAPI dependency enforcing admin privileges."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pro tuto akci jsou vyžadována administrátorská práva.",
        )
    return current_user
