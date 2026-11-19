from datetime import datetime
import sqlite3
from fastapi import HTTPException, status

from . import auth, schemas


def get_health() -> schemas.HealthResponse:
    return schemas.HealthResponse(status="ok")


def register_user(
    db: sqlite3.Connection,
    user_in: schemas.UserRegisterRequest,
) -> schemas.AuthTokenResponse:
    auth.verify_master_password(user_in.master_password)

    username = user_in.username.strip()
    if len(username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uživatelské jméno musí mít alespoň 3 znaky.",
        )

    farnost = user_in.farnost.strip() if user_in.farnost and user_in.farnost.strip() else None
    password_hash = auth.hash_password(user_in.password)

    try:
        row = db.execute(
            """
            INSERT INTO users (username, farnost, password_hash)
            VALUES (?, ?, ?)
            RETURNING id, username, farnost, created_at
            """,
            (username, farnost, password_hash),
        ).fetchone()
        db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Uživatelské jméno už existuje.",
        )

    user = schemas.UserResponse(**dict(row))
    token = auth.create_session(db=db, user_id=user.id)
    return schemas.AuthTokenResponse(access_token=token, user=user)


def login_user(
    db: sqlite3.Connection,
    credentials: schemas.UserLoginRequest,
) -> schemas.AuthTokenResponse:
    username = credentials.username.strip()
    row = db.execute(
        "SELECT id, username, farnost, password_hash, created_at FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if not row or not auth.verify_password(credentials.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Neplatné uživatelské jméno nebo heslo.",
        )

    user = schemas.UserResponse(
        id=row["id"],
        username=row["username"],
        farnost=row["farnost"],
        created_at=row["created_at"],
    )
    token = auth.create_session(db=db, user_id=user.id)
    return schemas.AuthTokenResponse(access_token=token, user=user)


def logout_user(db: sqlite3.Connection, token: str) -> None:
    auth.revoke_session(db=db, token=token)
    return None


def list_logs(
    db: sqlite3.Connection,
    skip: int = 0,
    limit: int = 100,
) -> list[schemas.LogEntryResponse]:
    rows = db.execute(
        "SELECT id, title, author, notes, created_at FROM log_entries ORDER BY id DESC LIMIT ? OFFSET ?",
        (limit, skip),
    ).fetchall()
    return [schemas.LogEntryResponse(**dict(row)) for row in rows]


def read_log(
    db: sqlite3.Connection,
    log_id: int,
) -> schemas.LogEntryResponse:
    row = db.execute(
        "SELECT id, title, author, notes, created_at FROM log_entries WHERE id = ?",
        (log_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found")
    return schemas.LogEntryResponse(**dict(row))


def _normalize_entry_timestamp(raw_date: str) -> str:
    """Parse an ISO date or datetime string and normalize it to YYYY-MM-DDTHH:MM:SSZ."""
    cleaned = raw_date.strip()
    try:
        if len(cleaned) == 10 and "T" not in cleaned and " " not in cleaned:
            parsed = datetime.fromisoformat(f"{cleaned}T00:00:00")
        else:
            parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Neplatný formát data nebo času. Očekává se ISO formát (např. YYYY-MM-DDTHH:MM:SS).",
        )
    return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def create_log(
    db: sqlite3.Connection,
    log_in: schemas.LogEntryCreate,
) -> schemas.LogEntryResponse:
    if log_in.date:
        timestamp = _normalize_entry_timestamp(log_in.date)
        row = db.execute(
            "INSERT INTO log_entries (title, author, notes, created_at) VALUES (?, ?, ?, ?) RETURNING id, title, author, notes, created_at",
            (log_in.title, log_in.author, log_in.notes, timestamp),
        ).fetchone()
    else:
        row = db.execute(
            "INSERT INTO log_entries (title, author, notes, created_at) VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now')) RETURNING id, title, author, notes, created_at",
            (log_in.title, log_in.author, log_in.notes),
        ).fetchone()
    db.commit()
    return schemas.LogEntryResponse(**dict(row))


def update_log(
    db: sqlite3.Connection,
    log_id: int,
    log_in: schemas.LogEntryUpdate,
) -> schemas.LogEntryResponse:
    existing = db.execute(
        "SELECT id, title, author, notes, created_at FROM log_entries WHERE id = ?",
        (log_id,),
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found")

    updated_data = dict(existing)
    for key, value in log_in.model_dump(exclude_unset=True).items():
        updated_data[key] = value

    row = db.execute(
        """
        UPDATE log_entries
        SET title = ?, author = ?, notes = ?
        WHERE id = ?
        RETURNING id, title, author, notes, created_at
        """,
        (updated_data["title"], updated_data["author"], updated_data["notes"], log_id),
    ).fetchone()
    db.commit()
    return schemas.LogEntryResponse(**dict(row))


def delete_log(
    db: sqlite3.Connection,
    log_id: int,
) -> None:
    cursor = db.execute("DELETE FROM log_entries WHERE id = ?", (log_id,))
    db.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found")
    return None
