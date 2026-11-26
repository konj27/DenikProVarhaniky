import os
import sqlite3
from collections.abc import Generator
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "app.db"

DEFAULT_PARISHES: tuple[str, ...] = (
    "Brno Mendlovo Náměstí",
    "Nový Hrozenkov",
)


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row["name"] == column_name for row in rows)


def init_db() -> None:
    """Initialize the SQLite database, create tables, migrate legacy columns, and seed initial data."""
    from .auth import hash_password

    load_dotenv(BASE_DIR / ".env", override=False)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS parishes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                farnost TEXT,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_parishes (
                user_id INTEGER NOT NULL,
                parish_id INTEGER NOT NULL,
                is_home INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                PRIMARY KEY (user_id, parish_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (parish_id) REFERENCES parishes(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS access_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                parish_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                UNIQUE (user_id, parish_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (parish_id) REFERENCES parishes(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS denied_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                parish_id INTEGER NOT NULL,
                reason TEXT,
                denied_by INTEGER,
                requested_at TEXT,
                denied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (parish_id) REFERENCES parishes(id) ON DELETE CASCADE,
                FOREIGN KEY (denied_by) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS log_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                notes TEXT,
                parish_id INTEGER,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                FOREIGN KEY (parish_id) REFERENCES parishes(id) ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        # --- Migrations for existing databases ---
        if not _column_exists(conn, "users", "is_admin"):
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")

        if not _column_exists(conn, "log_entries", "parish_id"):
            conn.execute(
                "ALTER TABLE log_entries ADD COLUMN parish_id INTEGER REFERENCES parishes(id) ON DELETE CASCADE"
            )

        # --- Seed default parishes ---
        for parish_name in DEFAULT_PARISHES:
            conn.execute(
                "INSERT OR IGNORE INTO parishes (name) VALUES (?)",
                (parish_name,),
            )

        default_parish = conn.execute(
            "SELECT id, name FROM parishes WHERE name = ?",
            (DEFAULT_PARISHES[0],),
        ).fetchone()
        if default_parish is None:
            default_parish = conn.execute(
                "SELECT id, name FROM parishes ORDER BY id ASC LIMIT 1"
            ).fetchone()

        # --- Seed Admin user from .env (row #1 on a fresh database) ---
        admin_username = os.getenv("ADMIN_USERNAME", "").strip()
        admin_password = os.getenv("ADMIN_PASSWORD", "")
        if admin_username and admin_password:
            existing_admin = conn.execute(
                "SELECT id, is_admin FROM users WHERE username = ?",
                (admin_username,),
            ).fetchone()
            if existing_admin is None:
                home_name = default_parish["name"] if default_parish else None
                admin_row = conn.execute(
                    """
                    INSERT INTO users (username, farnost, password_hash, is_admin)
                    VALUES (?, ?, ?, 1)
                    RETURNING id
                    """,
                    (admin_username, home_name, hash_password(admin_password)),
                ).fetchone()
                admin_id = admin_row["id"]
            else:
                admin_id = existing_admin["id"]
                if not existing_admin["is_admin"]:
                    conn.execute(
                        "UPDATE users SET is_admin = 1 WHERE id = ?",
                        (admin_id,),
                    )

            # Ensure admin has access to all seeded parishes
            all_parishes = conn.execute("SELECT id FROM parishes ORDER BY id ASC").fetchall()
            has_home = conn.execute(
                "SELECT 1 FROM user_parishes WHERE user_id = ? AND is_home = 1",
                (admin_id,),
            ).fetchone()
            for idx, parish in enumerate(all_parishes):
                is_home = 1 if (not has_home and idx == 0) else 0
                conn.execute(
                    """
                    INSERT OR IGNORE INTO user_parishes (user_id, parish_id, is_home)
                    VALUES (?, ?, ?)
                    """,
                    (admin_id, parish["id"], is_home),
                )

        # --- Migrate legacy users without user_parishes records ---
        if default_parish is not None:
            parishes_by_name = {
                row["name"]: row["id"]
                for row in conn.execute("SELECT id, name FROM parishes").fetchall()
            }
            orphan_users = conn.execute(
                """
                SELECT u.id, u.farnost
                FROM users u
                WHERE NOT EXISTS (
                    SELECT 1 FROM user_parishes up WHERE up.user_id = u.id
                )
                """
            ).fetchall()
            for user_row in orphan_users:
                matched_id = parishes_by_name.get((user_row["farnost"] or "").strip())
                target_parish_id = matched_id or default_parish["id"]
                target_parish_name = (
                    user_row["farnost"].strip() if matched_id else default_parish["name"]
                )
                conn.execute(
                    """
                    INSERT OR IGNORE INTO user_parishes (user_id, parish_id, is_home)
                    VALUES (?, ?, 1)
                    """,
                    (user_row["id"], target_parish_id),
                )
                if not user_row["farnost"]:
                    conn.execute(
                        "UPDATE users SET farnost = ? WHERE id = ?",
                        (target_parish_name, user_row["id"]),
                    )

            # --- Migrate legacy log_entries without parish_id ---
            conn.execute(
                "UPDATE log_entries SET parish_id = ? WHERE parish_id IS NULL",
                (default_parish["id"],),
            )

        conn.commit()
    finally:
        conn.close()


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency yielding a sqlite3 connection with Row factory."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()
