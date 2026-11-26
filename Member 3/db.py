"""SQLite storage for accounts and their own gallery pictures. One file: data/stego.db"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
DB = DATA / "stego.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  handle TEXT NOT NULL UNIQUE,          -- lower-case username or e-mail address
  is_email INTEGER NOT NULL DEFAULT 0,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  avatar TEXT,                          -- file name under data/avatars, or NULL
  verified INTEGER NOT NULL DEFAULT 0,  -- e-mail confirmed with the 6-digit code
  code_hash TEXT,                       -- hash of the current verification code
  code_expires TEXT,
  code_sent TEXT,
  code_attempts INTEGER NOT NULL DEFAULT 0,
  accent TEXT,                          -- app colour chosen in Settings (navy, sky, red, green, purple)
  default_lock INTEGER NOT NULL DEFAULT 1,       -- Hide starts with Lock on
  created TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS user_gallery (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  name TEXT NOT NULL,
  file TEXT NOT NULL,                   -- base name under data/gallery (PNG + .thumb.jpg)
  width INTEGER NOT NULL,
  height INTEGER NOT NULL,
  created TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def init():
    DATA.mkdir(exist_ok=True)
    (DATA / "avatars").mkdir(exist_ok=True)
    (DATA / "gallery").mkdir(exist_ok=True)
    with connect() as con:
        con.executescript(SCHEMA)
        # Databases created before e-mail verification existed: add the columns,
        # treating accounts that already exist as verified.
        cols = {r[1] for r in con.execute("PRAGMA table_info(users)")}
        for name, ddl in (("verified", "INTEGER NOT NULL DEFAULT 1"), ("code_hash", "TEXT"), ("code_expires", "TEXT"),
                          ("code_sent", "TEXT"), ("code_attempts", "INTEGER NOT NULL DEFAULT 0"), ("accent", "TEXT"),
                          ("default_lock", "INTEGER NOT NULL DEFAULT 1")):
            if name not in cols:
                con.execute(f"ALTER TABLE users ADD COLUMN {name} {ddl}")
        # Messaging between users was removed: drop its old table (its rows point at users,
        # which would block deleting an account).
        con.execute("DROP TABLE IF EXISTS messages")


@contextmanager
def connect():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def one(query, *args):
    with connect() as con:
        row = con.execute(query, args).fetchone()
        return dict(row) if row else None


def all_(query, *args):
    with connect() as con:
        return [dict(r) for r in con.execute(query, args).fetchall()]


def run(query, *args) -> int:
    """Execute a write and return lastrowid."""
    with connect() as con:
        return con.execute(query, args).lastrowid
