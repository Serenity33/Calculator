import os
import sqlite3
from pathlib import Path

_default = Path.home() / ".bookkeeping" / "data.db"
DB_PATH = Path(os.environ.get("DB_PATH", str(_default)))


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS businesses (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                name    TEXT NOT NULL UNIQUE,
                created TEXT NOT NULL DEFAULT (date('now'))
            );

            CREATE TABLE IF NOT EXISTS categories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                name        TEXT NOT NULL,
                type        TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                UNIQUE(business_id, name)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
                category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                type        TEXT NOT NULL CHECK(type IN ('income', 'expense')),
                amount      REAL NOT NULL CHECK(amount > 0),
                description TEXT,
                date        TEXT NOT NULL DEFAULT (date('now')),
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
