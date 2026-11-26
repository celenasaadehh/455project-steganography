
#For English carriers, each symbol holds 2 bits. For carriers containing Arabic
#letters, joining-safe symbols hold 1 bit each..
#
#An optional password locks the secret with AES-256-GCM (key from scrypt, the same
#settings as Member 1's image module). This module is the text carrier of the
#Stego Studio website: the site calls hide() / reveal(), which are encode_text() /
#decode_text() with the website's names.

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import unicodedata
import zlib

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# English mapping: 2 bits per invisible character.
SYMBOLS = ("​", "‌", "⁠", "⁣")
SYMBOL_TO_VALUE = {symbol: value for value, symbol in enumerate(SYMBOLS)}

# Arabic mapping: 1 bit per invisible character, placed at a word boundary.
ARABIC_BIT_SYMBOLS = ("​", "⁠")
ARABIC_SYMBOL_TO_BIT = {symbol: value for value, symbol in enumerate(ARABIC_BIT_SYMBOLS)}

MAGIC = b"TS"          # unlocked packet: TS + length + secret + CRC32
LOCKED_MAGIC = b"TL"   # locked packet:   TL + salt + nonce + AES-GCM(secret) + tag
HEADER_BYTES = 4       # 2 magic bytes + 2-byte message length
CHECKSUM_BYTES = 4     # CRC32 for detecting accidental corruption
OVERHEAD_BYTES = HEADER_BYTES + CHECKSUM_BYTES
SALT_BYTES, NONCE_BYTES, TAG_BYTES = 16, 12, 16
LOCKED_OVERHEAD_BYTES = 2 + SALT_BYTES + NONCE_BYTES + TAG_BYTES
MAX_SECRET_BYTES = 65535

# A hidden message is always ONE long run of invisible characters. Persian words use
# U+200C and emoji use U+200D one at a time, so short runs belong to the carrier.
MIN_RUN = 8
# The website's first text format ("ZW", 4 symbols incl. U+200D) is still readable,
# so messages sent before the website switched to this module keep opening.
_LEGACY_SYMBOLS = ("​", "‌", "‍", "⁠")
_HIDDEN = set(SYMBOLS) | set(ARABIC_BIT_SYMBOLS) | set(_LEGACY_SYMBOLS)


class TextStegoError(ValueError):
    """Every error from this module; the message is safe to show to users."""


class TextPasswordError(TextStegoError):
    """A password is missing, empty or wrong."""


def _arabic_letter(character: str) -> bool:
    return (
        unicodedata.category(character).startswith("L")
        and unicodedata.name(character, "").startswith("ARABIC")
    )


def _choose_mode(carrier: str) -> str:
    if any(_arabic_letter(character) for character in carrier):
        return "Arabic (after first space)"
    return "English (after first word)"


def _runs(text: str) -> list[tuple[int, int]]:
    """(start, end) of every run of MIN_RUN or more invisible characters.

    Spaces and line breaks may sit inside a run, because apps that wrap long
    lines can break the hidden block in two. Any visible character ends the run.
    """
    runs, index = [], 0
    while index < len(text):
        if text[index] not in _HIDDEN:
            index += 1
            continue
        start = last = scan = index
        count = 0
        while scan < len(text) and (text[scan] in _HIDDEN or text[scan].isspace()):
            if text[scan] in _HIDDEN:
                last, count = scan, count + 1
            scan += 1
        if count >= MIN_RUN:
            runs.append((start, last + 1))
        index = last + 1
    return runs


def find_hidden(text: str) -> str:
    """The invisible characters of the hidden message ("" if there is none)."""
    runs = _runs(text or "")
    if len(runs) > 1:
        raise TextStegoError("This text holds more than one hidden message. Paste only the message you received.")
    if not runs:
        return ""
    return "".join(ch for ch in text[runs[0][0]:runs[0][1]] if ch in _HIDDEN)


def _check_carrier(carrier: str) -> None:
    if not isinstance(carrier, str) or not carrier.strip():
        raise TextStegoError("Enter a nonempty carrier paragraph.")
    if _runs(carrier):
        raise TextStegoError("Carrier already contains a hidden message. Use clean text.")


def _check_password(password) -> None:
    """Same rule as Member 1's image module: None means no lock, otherwise a nonempty string."""
    if password is not None and (not isinstance(password, str) or not password):
        raise TextPasswordError("Enter a password, or switch Lock off.")


def _key(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**15, r=8, p=1,
                          dklen=32, maxmem=64 * 1024 * 1024)


def _clear_side(carrier: str, spot: int, step: int) -> bool:
    """True if, walking from `spot` over spaces only, the next character is visible (or the text ends).

    A hidden run may contain spaces (see _runs), so one of the carrier's own invisible
    characters that is only spaces away from the run would join it.
    """
    index = spot - 1 if step < 0 else spot
    while 0 <= index < len(carrier) and carrier[index].isspace():
        index += step
    return not (0 <= index < len(carrier)) or carrier[index] not in _HIDDEN


def insert_position(carrier: str) -> int:
    """Right after the first space, but never next to (or only spaces away from) one of the
    carrier's own invisible characters. Falls back to the end, then the start of the carrier."""
    spots = [index + 1 for index, character in enumerate(carrier) if character == " "] + [len(carrier), 0]
    for spot in spots:
        if _clear_side(carrier, spot, -1) and _clear_side(carrier, spot, +1):
            return spot
    raise TextStegoError("This text has invisible characters where the message would go. Please use a different sentence.")


def capacity_info(carrier: str) -> dict:
    """Report packet capacity; not limited by the number of carrier letters."""
    _check_carrier(carrier)
    mode = _choose_mode(carrier)
    return {
        "mode": mode,
        "max_secret_bytes": MAX_SECRET_BYTES,
        "overhead_bits": 8 * OVERHEAD_BYTES,
        "locked_overhead_bits": 8 * LOCKED_OVERHEAD_BYTES,
        "symbols_per_byte": 8 if mode.startswith("Arabic") else 4,
    }


def _packet(secret_bytes: bytes, password: str | None) -> bytes:
    if password is None:
        header = MAGIC + len(secret_bytes).to_bytes(2, "big")
        checksum = zlib.crc32(header + secret_bytes).to_bytes(4, "big")
        return header + secret_bytes + checksum
    salt, nonce = os.urandom(SALT_BYTES), os.urandom(NONCE_BYTES)
    header = LOCKED_MAGIC + salt + nonce
    return header + AESGCM(_key(password, salt)).encrypt(nonce, secret_bytes, header)


def encode_text(carrier: str, secret: str, password: str | None = None) -> str:
    """Hide a UTF-8 secret inside a carrier without changing visible text."""
    _check_carrier(carrier)
    if not isinstance(secret, str) or not secret:
        raise TextStegoError("Enter a nonempty secret message.")
    _check_password(password)

    secret_bytes = secret.encode("utf-8")
    if len(secret_bytes) > MAX_SECRET_BYTES:
        raise TextStegoError("Secret must be 65535 UTF-8 bytes or fewer.")

    bits = "".join(f"{byte:08b}" for byte in _packet(secret_bytes, password))

    if _choose_mode(carrier).startswith("Arabic"):
        hidden = "".join(ARABIC_BIT_SYMBOLS[int(bit)] for bit in bits)
    else:
        hidden = "".join(
            SYMBOLS[int(bits[index:index + 2], 2)]
            for index in range(0, len(bits), 2)
        )

    # Member 3's short-carrier approach: put the hidden run in one location.
    # A normal space boundary reduces interference with joined Arabic letters.
    position = insert_position(carrier)
    stego = carrier[:position] + hidden + carrier[position:]
    if remove_hidden_symbols(stego) != carrier or find_hidden(stego) != hidden:  # check our own work
        raise TextStegoError("This text cannot carry a message safely. Please use a different sentence.")
    return stego


def read_packet(stego: str) -> tuple[str, str, bytes]:
    """Find the hidden run and turn it back into bytes: (mode, run, packet)."""
    if not isinstance(stego, str) or not stego:
        raise TextStegoError("Paste or load a stego paragraph first.")
    run = find_hidden(stego)
    if not run:
        raise TextStegoError("No hidden message found in this text.")

    # The English header always contains U+200C; the Arabic mapping never does.
    # Only the website's first format used U+200D.
    if "‍" in run:
        mode, values, per = "Legacy", [_LEGACY_SYMBOLS.index(ch) if ch in _LEGACY_SYMBOLS else -1 for ch in run], 4
    elif "‌" in run or "⁣" in run:
        mode, values, per = "English", [SYMBOL_TO_VALUE.get(ch, -1) for ch in run], 4
    else:
        mode, values, per = "Arabic", [ARABIC_SYMBOL_TO_BIT.get(ch, -1) for ch in run], 8
    if -1 in values or len(values) % per:
        raise TextStegoError("Hidden message is incomplete or corrupted.")
    width = 8 // per
    bits = "".join(f"{value:0{width}b}" for value in values)
    packet = bytes(int(bits[index:index + 8], 2) for index in range(0, len(bits), 8))
    return mode, run, packet


def decode_text(stego: str, password: str | None = None) -> str:
    """Recover and validate a secret using only the stego paragraph."""
    if password is not None and not isinstance(password, str):
        raise TextPasswordError("The password must be text.")
    mode, _, packet = read_packet(stego)

    if mode == "Legacy":
        payload = _legacy_payload(packet, password)
    elif packet[:2] == LOCKED_MAGIC:
        if not password:
            raise TextPasswordError("This message is protected. Enter the password to reveal it.")
        if len(packet) < LOCKED_OVERHEAD_BYTES:
            raise TextStegoError("Hidden message is incomplete or corrupted.")
        header = packet[:2 + SALT_BYTES + NONCE_BYTES]
        salt, nonce = packet[2:2 + SALT_BYTES], packet[2 + SALT_BYTES:len(header)]
        try:
            payload = AESGCM(_key(password, salt)).decrypt(nonce, packet[len(header):], header)
        except InvalidTag:
            raise TextPasswordError("Wrong password, or the text was changed after the message was hidden.") from None
    else:
        if len(packet) < OVERHEAD_BYTES or packet[:2] != MAGIC:
            raise TextStegoError("This text does not contain a valid TS stego message.")
        message_length = int.from_bytes(packet[2:4], "big")
        if len(packet) != OVERHEAD_BYTES + message_length:
            raise TextStegoError("Hidden message length does not match; text may have changed.")
        payload = packet[HEADER_BYTES:-CHECKSUM_BYTES]
        found_checksum = int.from_bytes(packet[-CHECKSUM_BYTES:], "big")
        if found_checksum != zlib.crc32(packet[:HEADER_BYTES] + payload):
            raise TextStegoError("Hidden message failed CRC32 check; text was modified.")

    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TextStegoError("Hidden message is not valid UTF-8.") from exc


def _legacy_payload(packet: bytes, password: str | None) -> bytes:
    """The website's first format: ZW, version 1, lock flag, then CRC32 or AES-GCM."""
    if len(packet) < 8 or packet[:2] != b"ZW" or packet[2] != 1 or packet[3] not in (0, 1):
        raise TextStegoError("Hidden message is incomplete or corrupted.")
    if packet[3] == 0:
        body, check = packet[:-4], packet[-4:]
        if zlib.crc32(body).to_bytes(4, "big") != check:
            raise TextStegoError("Hidden message failed CRC32 check; text was modified.")
        return body[4:]
    if not password:
        raise TextPasswordError("This message is protected. Enter the password to reveal it.")
    if len(packet) < 48:
        raise TextStegoError("Hidden message is incomplete or corrupted.")
    try:
        return AESGCM(_key(password, packet[4:20])).decrypt(packet[20:32], packet[32:], packet[:32])
    except InvalidTag:
        raise TextPasswordError("Wrong password, or the text was changed after the message was hidden.") from None


def remove_hidden_symbols(stego: str) -> str:
    """Return the original carrier: the hidden run goes, the carrier's own joiners stay."""
    out, last = [], 0
    for start, end in _runs(stego):
        out.append(stego[last:start])
        out.append("".join(ch for ch in stego[start:end] if ch not in _HIDDEN))  # keep wrapped line breaks
        last = end
    out.append(stego[last:])
    return "".join(out)


# The names the Stego Studio website (Member 3) and the Learn tab (Member 4) call.
def hide(cover: str, message: str, password: str | None = None) -> str:
    return encode_text(cover, message, password)


def reveal(text: str, password: str | None = None) -> str:
    return decode_text(text, password)


strip_hidden = remove_hidden_symbols


def main() -> None:
    print("\n=== ZERO-WIDTH TEXT STEGANOGRAPHY ===")
    print("1 - Encode a secret message")
    print("2 - Decode saved stego_output.txt")
    print("3 - Decode pasted stego text")
    print("4 - Check carrier capacity")
    mode = input("Choose 1, 2, 3, or 4: ").strip()
    path = Path(__file__).resolve().with_name("stego_output.txt")

    try:
        if mode == "1":
            carrier = input("Enter your carrier paragraph: ")
            secret = input("Enter your secret message: ")
            password = input("Password (leave empty for no lock): ") or None
            info = capacity_info(carrier)
            stego = encode_text(carrier, secret, password)
            path.write_text(stego, encoding="utf-8")
            decoded = decode_text(path.read_text(encoding="utf-8"), password)

            print("\n--- ENCODER ---")
            print("Hiding method:", info["mode"])
            print("Locked with a password:", password is not None)
            print("Minimum carrier length: none (except nonempty text)")
            print("Maximum secret size:", info["max_secret_bytes"], "UTF-8 bytes")
            print("Secret bytes:", len(secret.encode("utf-8")))
            print("Original text preserved exactly:", remove_hidden_symbols(stego) == carrier)
            print("Saved stego text to:", path)
            print("Stego paragraph (may display differently in some apps):\n", stego)
            print("\n--- SAVED-FILE DECODER TEST ---")
            print("Recovered secret:", decoded)
            print("Match:", decoded == secret)

        elif mode == "2":
            if not path.exists():
                raise ValueError("stego_output.txt does not exist. Encode a message first.")
            password = input("Password (leave empty if not locked): ") or None
            print("\nRecovered secret:", decode_text(path.read_text(encoding="utf-8"), password))

        elif mode == "3":
            stego = input("Paste the exact stego text (including invisible characters): ")
            password = input("Password (leave empty if not locked): ") or None
            print("\nRecovered secret:", decode_text(stego, password))

        elif mode == "4":
            carrier = input("Enter your carrier paragraph: ")
            info = capacity_info(carrier)
            print("\nHiding method:", info["mode"])
            print("No minimum carrier length: hidden data is placed after the first word.")
            print("Invisible characters per packet byte:", info["symbols_per_byte"])
            print("Protocol overhead:", info["overhead_bits"], "bits")
            print("Overhead with a password:", info["locked_overhead_bits"], "bits")
            print("Maximum secret:", info["max_secret_bytes"], "UTF-8 bytes")

        else:
            print("Invalid option.")

    except (ValueError, OSError) as exc:
        print("\nERROR:", exc)


if __name__ == "__main__":
    main()
