"""SQLite storage for accounts and messages. One file: data/stego.db"""
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
  inbox_mode TEXT NOT NULL DEFAULT 'everyone',   -- who may send: everyone | contacts | nobody
  show_name INTEGER NOT NULL DEFAULT 1,          -- others see full name (1) or first name only (0)
  auto_delete_days INTEGER NOT NULL DEFAULT 0,   -- remove received messages after N days (0 = never)
  default_lock INTEGER NOT NULL DEFAULT 1,       -- new messages start with Lock on
  created TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY,
  sender_id INTEGER NOT NULL REFERENCES users(id),
  recipient_id INTEGER NOT NULL REFERENCES users(id),
  carrier TEXT NOT NULL,                -- 'image' | 'text'
  format TEXT,                          -- PNG/JPEG/BMP for images
  file TEXT,                            -- stego image file name under data/files
  text TEXT,                            -- stego text for text carrier
  subject TEXT NOT NULL DEFAULT '',
  locked INTEGER NOT NULL DEFAULT 0,
  gallery_id INTEGER,
  created TEXT NOT NULL DEFAULT (datetime('now')),
  read_at TEXT,
  sender_deleted INTEGER NOT NULL DEFAULT 0,
  recipient_deleted INTEGER NOT NULL DEFAULT 0,
  sender_pinned INTEGER NOT NULL DEFAULT 0,     -- pinned to the top of the sender's Sent
  recipient_pinned INTEGER NOT NULL DEFAULT 0   -- pinned to the top of the recipient's Inbox
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
CREATE INDEX IF NOT EXISTS idx_inbox ON messages(recipient_id, created);
CREATE INDEX IF NOT EXISTS idx_sent ON messages(sender_id, created);
"""


def init():
    DATA.mkdir(exist_ok=True)
    (DATA / "files").mkdir(exist_ok=True)
    (DATA / "avatars").mkdir(exist_ok=True)
    (DATA / "gallery").mkdir(exist_ok=True)
    with connect() as con:
        con.executescript(SCHEMA)
        # Databases created before e-mail verification existed: add the columns,
        # treating accounts that already exist as verified.
        cols = {r[1] for r in con.execute("PRAGMA table_info(users)")}
        for name, ddl in (("verified", "INTEGER NOT NULL DEFAULT 1"), ("code_hash", "TEXT"), ("code_expires", "TEXT"),
                          ("code_sent", "TEXT"), ("code_attempts", "INTEGER NOT NULL DEFAULT 0"), ("accent", "TEXT"),
                          ("inbox_mode", "TEXT NOT NULL DEFAULT 'everyone'"), ("show_name", "INTEGER NOT NULL DEFAULT 1"),
                          ("auto_delete_days", "INTEGER NOT NULL DEFAULT 0"), ("default_lock", "INTEGER NOT NULL DEFAULT 1")):
            if name not in cols:
                con.execute(f"ALTER TABLE users ADD COLUMN {name} {ddl}")
        mcols = {r[1] for r in con.execute("PRAGMA table_info(messages)")}
        for name in ("sender_pinned", "recipient_pinned"):
            if name not in mcols:
                con.execute(f"ALTER TABLE messages ADD COLUMN {name} INTEGER NOT NULL DEFAULT 0")


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
