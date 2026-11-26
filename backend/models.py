from datetime import datetime
import sqlite3
from fastapi import HTTPException, status

from . import auth, schemas


def get_health() -> schemas.HealthResponse:
    return schemas.HealthResponse(status="ok")


def _ensure_parish_access(
    db: sqlite3.Connection,
    current_user: schemas.UserResponse,
    parish_id: int,
) -> None:
    parish = db.execute("SELECT id FROM parishes WHERE id = ?", (parish_id,)).fetchone()
    if not parish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farnost nebyla nalezena.",
        )

    if current_user.is_admin:
        return

    membership = db.execute(
        "SELECT 1 FROM user_parishes WHERE user_id = ? AND parish_id = ?",
        (current_user.id, parish_id),
    ).fetchone()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nemáte přístup k vybrané farnosti.",
        )


def list_all_parishes(db: sqlite3.Connection) -> list[schemas.ParishResponse]:
    rows = db.execute("SELECT id, name FROM parishes ORDER BY id ASC").fetchall()
    return [schemas.ParishResponse(**dict(row)) for row in rows]


def list_user_parishes(
    db: sqlite3.Connection,
    current_user: schemas.UserResponse,
) -> list[schemas.UserParishResponse]:
    if current_user.is_admin:
        rows = db.execute(
            """
            SELECT p.id, p.name, COALESCE(up.is_home, 0) AS is_home
            FROM parishes p
            LEFT JOIN user_parishes up
                ON up.parish_id = p.id AND up.user_id = ?
            ORDER BY COALESCE(up.is_home, 0) DESC, p.id ASC
            """,
            (current_user.id,),
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT p.id, p.name, up.is_home
            FROM parishes p
            JOIN user_parishes up ON up.parish_id = p.id
            WHERE up.user_id = ?
            ORDER BY up.is_home DESC, p.name ASC
            """,
            (current_user.id,),
        ).fetchall()
    return [
        schemas.UserParishResponse(id=row["id"], name=row["name"], is_home=bool(row["is_home"]))
        for row in rows
    ]


def register_user(
    db: sqlite3.Connection,
    user_in: schemas.UserRegisterRequest,
    client_ip: str = "unknown",
) -> schemas.AuthTokenResponse:
    auth.check_register_rate_limit(client_ip)
    try:
        auth.verify_master_password(user_in.master_password)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_403_FORBIDDEN:
            auth.record_register_failure(client_ip)
        raise

    username = user_in.username.strip()
    if len(username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uživatelské jméno musí mít alespoň 3 znaky.",
        )

    parish = db.execute(
        "SELECT id, name FROM parishes WHERE id = ?",
        (user_in.home_parish_id,),
    ).fetchone()
    if not parish:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vybraná domovská farnost neexistuje.",
        )

    password_hash = auth.hash_password(user_in.password)

    try:
        row = db.execute(
            """
            INSERT INTO users (username, farnost, password_hash, is_admin)
            VALUES (?, ?, ?, 0)
            RETURNING id, username, farnost, is_admin, created_at
            """,
            (username, parish["name"], password_hash),
        ).fetchone()
        db.execute(
            """
            INSERT INTO user_parishes (user_id, parish_id, is_home)
            VALUES (?, ?, 1)
            """,
            (row["id"], parish["id"]),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Uživatelské jméno už existuje.",
        )

    user = schemas.UserResponse(
        id=row["id"],
        username=row["username"],
        farnost=row["farnost"],
        is_admin=bool(row["is_admin"]),
        created_at=row["created_at"],
    )
    token = auth.create_session(db=db, user_id=user.id)
    return schemas.AuthTokenResponse(access_token=token, user=user)


def login_user(
    db: sqlite3.Connection,
    credentials: schemas.UserLoginRequest,
    client_ip: str = "unknown",
) -> schemas.AuthTokenResponse:
    username = credentials.username.strip()
    auth.check_login_rate_limit(username=username, client_ip=client_ip)

    row = db.execute(
        "SELECT id, username, farnost, is_admin, password_hash, created_at FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if not row or not auth.verify_password(credentials.password, row["password_hash"]):
        auth.record_login_failure(username=username, client_ip=client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Neplatné uživatelské jméno nebo heslo.",
        )

    auth.reset_login_rate_limit(username=username)

    user = schemas.UserResponse(
        id=row["id"],
        username=row["username"],
        farnost=row["farnost"],
        is_admin=bool(row["is_admin"]),
        created_at=row["created_at"],
    )
    token = auth.create_session(db=db, user_id=user.id)
    return schemas.AuthTokenResponse(access_token=token, user=user)


def logout_user(db: sqlite3.Connection, token: str) -> None:
    auth.revoke_session(db=db, token=token)
    return None


def list_logs(
    db: sqlite3.Connection,
    current_user: schemas.UserResponse,
    parish_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[schemas.LogEntryResponse]:
    if parish_id is not None:
        _ensure_parish_access(db, current_user, parish_id)
        rows = db.execute(
            """
            SELECT id, title, author, notes, parish_id, created_at
            FROM log_entries
            WHERE parish_id = ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (parish_id, limit, skip),
        ).fetchall()
    elif current_user.is_admin:
        rows = db.execute(
            """
            SELECT id, title, author, notes, parish_id, created_at
            FROM log_entries
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, skip),
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT id, title, author, notes, parish_id, created_at
            FROM log_entries
            WHERE parish_id IN (
                SELECT parish_id FROM user_parishes WHERE user_id = ?
            )
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (current_user.id, limit, skip),
        ).fetchall()
    return [schemas.LogEntryResponse(**dict(row)) for row in rows]


def read_log(
    db: sqlite3.Connection,
    log_id: int,
    current_user: schemas.UserResponse,
) -> schemas.LogEntryResponse:
    row = db.execute(
        "SELECT id, title, author, notes, parish_id, created_at FROM log_entries WHERE id = ?",
        (log_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found")
    if row["parish_id"] is not None:
        _ensure_parish_access(db, current_user, row["parish_id"])
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
    current_user: schemas.UserResponse,
) -> schemas.LogEntryResponse:
    _ensure_parish_access(db, current_user, log_in.parish_id)

    if log_in.date:
        timestamp = _normalize_entry_timestamp(log_in.date)
        row = db.execute(
            """
            INSERT INTO log_entries (title, author, notes, parish_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            RETURNING id, title, author, notes, parish_id, created_at
            """,
            (log_in.title, log_in.author, log_in.notes, log_in.parish_id, timestamp),
        ).fetchone()
    else:
        row = db.execute(
            """
            INSERT INTO log_entries (title, author, notes, parish_id, created_at)
            VALUES (?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            RETURNING id, title, author, notes, parish_id, created_at
            """,
            (log_in.title, log_in.author, log_in.notes, log_in.parish_id),
        ).fetchone()
    db.commit()
    return schemas.LogEntryResponse(**dict(row))


def update_log(
    db: sqlite3.Connection,
    log_id: int,
    log_in: schemas.LogEntryUpdate,
    current_user: schemas.UserResponse,
) -> schemas.LogEntryResponse:
    existing = db.execute(
        "SELECT id, title, author, notes, parish_id, created_at FROM log_entries WHERE id = ?",
        (log_id,),
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found")
    if existing["parish_id"] is not None:
        _ensure_parish_access(db, current_user, existing["parish_id"])

    updated_data = dict(existing)
    for key, value in log_in.model_dump(exclude_unset=True).items():
        updated_data[key] = value

    row = db.execute(
        """
        UPDATE log_entries
        SET title = ?, author = ?, notes = ?
        WHERE id = ?
        RETURNING id, title, author, notes, parish_id, created_at
        """,
        (updated_data["title"], updated_data["author"], updated_data["notes"], log_id),
    ).fetchone()
    db.commit()
    return schemas.LogEntryResponse(**dict(row))


def delete_log(
    db: sqlite3.Connection,
    log_id: int,
    current_user: schemas.UserResponse,
) -> None:
    existing = db.execute(
        "SELECT id, parish_id FROM log_entries WHERE id = ?",
        (log_id,),
    ).fetchone()
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log entry not found")
    if existing["parish_id"] is not None:
        _ensure_parish_access(db, current_user, existing["parish_id"])

    db.execute("DELETE FROM log_entries WHERE id = ?", (log_id,))
    db.commit()
    return None


def create_access_request(
    db: sqlite3.Connection,
    current_user: schemas.UserResponse,
    req_in: schemas.AccessRequestCreate,
) -> schemas.AccessRequestResponse:
    parish = db.execute(
        "SELECT id, name FROM parishes WHERE id = ?",
        (req_in.parish_id,),
    ).fetchone()
    if not parish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farnost nebyla nalezena.",
        )

    if current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Administrátor má již přístup ke všem farnostem.",
        )

    existing_membership = db.execute(
        "SELECT 1 FROM user_parishes WHERE user_id = ? AND parish_id = ?",
        (current_user.id, req_in.parish_id),
    ).fetchone()
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="K této farnosti už máte přístup.",
        )

    try:
        row = db.execute(
            """
            INSERT INTO access_requests (user_id, parish_id)
            VALUES (?, ?)
            RETURNING id, user_id, parish_id, created_at
            """,
            (current_user.id, req_in.parish_id),
        ).fetchone()
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Žádost o přístup do této farnosti už byla odeslána.",
        )

    return schemas.AccessRequestResponse(
        id=row["id"],
        user_id=row["user_id"],
        username=current_user.username,
        parish_id=row["parish_id"],
        parish_name=parish["name"],
        created_at=row["created_at"],
    )


def list_my_access_requests(
    db: sqlite3.Connection,
    current_user: schemas.UserResponse,
) -> list[schemas.AccessRequestResponse]:
    rows = db.execute(
        """
        SELECT
            ar.id,
            ar.user_id,
            u.username,
            ar.parish_id,
            p.name AS parish_name,
            ar.created_at
        FROM access_requests ar
        JOIN users u ON u.id = ar.user_id
        JOIN parishes p ON p.id = ar.parish_id
        WHERE ar.user_id = ?
        ORDER BY ar.created_at DESC, ar.id DESC
        """,
        (current_user.id,),
    ).fetchall()
    return [schemas.AccessRequestResponse(**dict(row)) for row in rows]


def list_all_access_requests(
    db: sqlite3.Connection,
) -> list[schemas.AccessRequestResponse]:
    rows = db.execute(
        """
        SELECT
            ar.id,
            ar.user_id,
            u.username,
            ar.parish_id,
            p.name AS parish_name,
            ar.created_at
        FROM access_requests ar
        JOIN users u ON u.id = ar.user_id
        JOIN parishes p ON p.id = ar.parish_id
        ORDER BY ar.created_at ASC, ar.id ASC
        """
    ).fetchall()
    return [schemas.AccessRequestResponse(**dict(row)) for row in rows]


def delete_access_request(
    db: sqlite3.Connection,
    request_id: int,
) -> schemas.AccessRequestResponse:
    row = db.execute(
        """
        SELECT
            ar.id,
            ar.user_id,
            u.username,
            ar.parish_id,
            p.name AS parish_name,
            ar.created_at
        FROM access_requests ar
        JOIN users u ON u.id = ar.user_id
        JOIN parishes p ON p.id = ar.parish_id
        WHERE ar.id = ?
        """,
        (request_id,),
    ).fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Žádost o přístup nebyla nalezena.",
        )

    db.execute("DELETE FROM access_requests WHERE id = ?", (request_id,))
    db.commit()
    return schemas.AccessRequestResponse(**dict(row))


def grant_user_parish(
    db: sqlite3.Connection,
    grant_in: schemas.UserParishGrantRequest,
) -> schemas.UserParishGrantResponse:
    user_row = db.execute("SELECT id FROM users WHERE id = ?", (grant_in.user_id,)).fetchone()
    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uživatel nebyl nalezen.",
        )

    parish_row = db.execute("SELECT id FROM parishes WHERE id = ?", (grant_in.parish_id,)).fetchone()
    if not parish_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farnost nebyla nalezena.",
        )

    db.execute(
        """
        INSERT OR IGNORE INTO user_parishes (user_id, parish_id, is_home)
        VALUES (?, ?, 0)
        """,
        (grant_in.user_id, grant_in.parish_id),
    )
    db.commit()

    saved = db.execute(
        "SELECT user_id, parish_id, is_home FROM user_parishes WHERE user_id = ? AND parish_id = ?",
        (grant_in.user_id, grant_in.parish_id),
    ).fetchone()
    return schemas.UserParishGrantResponse(
        user_id=saved["user_id"],
        parish_id=saved["parish_id"],
        is_home=bool(saved["is_home"]),
    )


def create_denied_request(
    db: sqlite3.Connection,
    admin_user: schemas.UserResponse,
    denied_in: schemas.DeniedRequestCreate,
) -> schemas.DeniedRequestResponse:
    user_row = db.execute("SELECT id FROM users WHERE id = ?", (denied_in.user_id,)).fetchone()
    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Uživatel nebyl nalezen.",
        )

    parish_row = db.execute("SELECT id FROM parishes WHERE id = ?", (denied_in.parish_id,)).fetchone()
    if not parish_row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farnost nebyla nalezena.",
        )

    row = db.execute(
        """
        INSERT INTO denied_requests (user_id, parish_id, reason, denied_by, requested_at)
        VALUES (?, ?, ?, ?, ?)
        RETURNING id, user_id, parish_id, reason, denied_by, requested_at, denied_at
        """,
        (
            denied_in.user_id,
            denied_in.parish_id,
            denied_in.reason,
            admin_user.id,
            denied_in.requested_at,
        ),
    ).fetchone()
    db.commit()
    return schemas.DeniedRequestResponse(**dict(row))
