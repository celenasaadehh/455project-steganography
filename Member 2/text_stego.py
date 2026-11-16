"""Text-carrier steganography using zero-width Unicode characters.

The secret is turned into bytes, optionally encrypted with AES-256-GCM
(key from scrypt, same parameters as Member 1's image module), and each byte
is written as four invisible characters (2 bits each). The invisible run is
placed after the first word of the cover text, so the visible text does not change.

This module is self-contained so that a teammate's text algorithm can replace it:
the website only calls ``hide(cover, message, password)`` and ``reveal(text, password)``.
"""
from __future__ import annotations

import hashlib
import os
import struct
import zlib

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Four invisible characters -> 2 bits per character.
ALPHABET = ("​", "‌", "‍", "⁠")
_INDEX = {ch: i for i, ch in enumerate(ALPHABET)}

MAGIC = b"ZW"
VERSION = 1
MAX_MESSAGE_BYTES = 10_000
MAX_COVER_CHARS = 100_000


class TextStegoError(ValueError):
    """Base error; messages are safe to show to users."""


class TextPasswordError(TextStegoError):
    pass


def _key(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**15, r=8, p=1,
                          dklen=32, maxmem=64 * 1024 * 1024)


def _encode(data: bytes) -> str:
    out = []
    for b in data:
        out.extend(ALPHABET[(b >> shift) & 3] for shift in (6, 4, 2, 0))
    return "".join(out)


def _decode(symbols: str) -> bytes:
    vals = [_INDEX[c] for c in symbols]
    return bytes((vals[i] << 6) | (vals[i + 1] << 4) | (vals[i + 2] << 2) | vals[i + 3]
                 for i in range(0, len(vals), 4))


def strip_hidden(text: str) -> str:
    return "".join(c for c in text if c not in _INDEX)


def capacity() -> int:
    return MAX_MESSAGE_BYTES


def hide(cover: str, message: str, password: str | None = None) -> str:
    cover = strip_hidden(cover or "")
    if not cover.strip():
        raise TextStegoError("Write some cover text first. It is the visible message people will see.")
    if len(cover) > MAX_COVER_CHARS:
        raise TextStegoError("The cover text is too long.")
    data = (message or "").encode("utf-8")
    if not data:
        raise TextStegoError("Write the secret message you want to hide.")
    if len(data) > MAX_MESSAGE_BYTES:
        raise TextStegoError(f"The secret message is too long (limit {MAX_MESSAGE_BYTES:,} bytes).")

    if password:
        salt, nonce = os.urandom(16), os.urandom(12)
        header = MAGIC + bytes([VERSION, 1]) + salt + nonce
        payload = header + AESGCM(_key(password, salt)).encrypt(nonce, data, header)
    else:
        header = MAGIC + bytes([VERSION, 0])
        payload = header + data
        payload += struct.pack(">I", zlib.crc32(payload))

    hidden = _encode(payload)
    space = cover.find(" ")
    pos = space if space > 0 else len(cover)
    return cover[:pos] + hidden + cover[pos:]


def reveal(text: str, password: str | None = None) -> str:
    symbols = "".join(c for c in (text or "") if c in _INDEX)
    if not symbols or len(symbols) % 4:
        raise TextStegoError("No hidden message was found in this text. Make sure you pasted the full text exactly as you received it.")
    data = _decode(symbols)
    if len(data) < 8 or data[:2] != MAGIC or data[2] != VERSION or data[3] not in (0, 1):
        raise TextStegoError("No hidden message was found in this text, or it was damaged when it was copied.")

    if data[3] == 1:
        if not password:
            raise TextPasswordError("This message is protected. Enter the password to reveal it.")
        if len(data) < 4 + 16 + 12 + 16:
            raise TextStegoError("The hidden message is damaged.")
        header, salt, nonce = data[:32], data[4:20], data[20:32]
        try:
            plain = AESGCM(_key(password, salt)).decrypt(nonce, data[32:], header)
        except InvalidTag:
            raise TextPasswordError("Wrong password, or the text was changed after the message was hidden.") from None
    else:
        body, check = data[:-4], data[-4:]
        if struct.pack(">I", zlib.crc32(body)) != check:
            raise TextStegoError("The hidden message is damaged.")
        plain = body[4:]
    return plain.decode("utf-8", errors="replace")
