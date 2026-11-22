"""
English: original 4-character alphabet, 2 bits per eligible ASCII letter.
Arabic: 2-character safe alphabet, 2 characters after an ordinary word space
        to encode 2 bits; avoids Arabic letter joining controls.

"""

from pathlib import Path
import unicodedata
import zlib

# Original English format (preserved for backward compatibility).
SYMBOLS = ("\u200b", "\u200c", "\u2060", "\u2063")
SYMBOL_TO_VALUE = {symbol: index for index, symbol in enumerate(SYMBOLS)}

# Arabic-safe format: no ZWNJ (which can change joining), and no U+2063.
# Each ordinary-space anchor receives TWO symbols (one per bit).
ARABIC_BIT_SYMBOLS = ("\u200b", "\u2060")
ARABIC_SYMBOL_TO_BIT = {symbol: index for index, symbol in enumerate(ARABIC_BIT_SYMBOLS)}

MAGIC = b"TS"
HEADER_BYTES = 4           # 2-byte signature + 2-byte message length
CHECKSUM_BYTES = 4         # CRC32 detects accidental changes
OVERHEAD_BYTES = HEADER_BYTES + CHECKSUM_BYTES
MAX_SECRET_BYTES = 65535


def _ascii_letter(character: str) -> bool:
    return "A" <= character <= "Z" or "a" <= character <= "z"


def _arabic_letter(character: str) -> bool:
    return (
        unicodedata.category(character).startswith("L")
        and unicodedata.name(character, "").startswith("ARABIC")
    )


def _english_positions(carrier: str) -> list[int]:
    return [i for i, character in enumerate(carrier) if _ascii_letter(character)]


def _arabic_space_positions(carrier: str) -> list[int]:
    """Ordinary spaces before Arabic words (never inside an Arabic word).

    After such a space, control characters cannot separate joined Arabic letters.
    A carrier with few spaces still cannot hold a long message.
    """
    return [
        i for i in range(1, len(carrier) - 1)
        if carrier[i] == " " and _arabic_letter(carrier[i + 1])
    ]


def _choose_mode_and_positions(carrier: str) -> tuple[str, list[int]]:
    english_positions = _english_positions(carrier)
    arabic_positions = _arabic_space_positions(carrier)
    if len(arabic_positions) > len(english_positions):
        return "Arabic (between words)", arabic_positions
    return "English (after letters)", english_positions


def _check_carrier(carrier: str) -> None:
    if not isinstance(carrier, str) or not carrier.strip():
        raise ValueError("Enter a nonempty carrier paragraph.")
    if any(character in SYMBOL_TO_VALUE for character in carrier):
        raise ValueError(
            "The carrier already contains reserved invisible characters. "
            "Use a clean original paragraph."
        )


def capacity_info(carrier: str) -> dict:
    """Calculate available hiding positions and maximum UTF-8 payload bytes."""
    _check_carrier(carrier)
    mode, positions = _choose_mode_and_positions(carrier)
    available = len(positions)
    return {
        "mode": mode,
        "carrier_letters": available,  # Retained for old website integrations.
        "eligible_positions": available,
        "raw_capacity_bits": 2 * available,
        "max_secret_bytes": min(
            MAX_SECRET_BYTES, max(0, available // 4 - OVERHEAD_BYTES)
        ),
        "overhead_bits": 8 * OVERHEAD_BYTES,
    }


def encode_text(carrier: str, secret: str) -> str:
    """Hide a secret and return the stego paragraph."""
    _check_carrier(carrier)
    if not isinstance(secret, str) or not secret:
        raise ValueError("Enter a nonempty secret message.")

    secret_bytes = secret.encode("utf-8")
    if len(secret_bytes) > MAX_SECRET_BYTES:
        raise ValueError("Secret must be 65535 UTF-8 bytes or fewer.")

    mode, positions = _choose_mode_and_positions(carrier)
    info = capacity_info(carrier)
    if len(secret_bytes) > info["max_secret_bytes"]:
        needed = 4 * (OVERHEAD_BYTES + len(secret_bytes))
        raise ValueError(
            f"Carrier is too short for this secret. It needs at least {needed} "
            f"hiding positions but has {len(positions)}. "
            "Use a longer paragraph (more words for Arabic). "
            f"Maximum secret here: {info['max_secret_bytes']} UTF-8 bytes."
        )

    header = MAGIC + len(secret_bytes).to_bytes(2, "big")
    checksum = zlib.crc32(header + secret_bytes).to_bytes(4, "big")
    packet = header + secret_bytes + checksum
    bits = "".join(f"{byte:08b}" for byte in packet)

    if mode.startswith("Arabic"):
        # Two bits -> two low-impact invisible characters after ONE space.
        # No U+200C, so Arabic joining is not deliberately interrupted.
        symbols = [
            ARABIC_BIT_SYMBOLS[int(bits[i])] + ARABIC_BIT_SYMBOLS[int(bits[i + 1])]
            for i in range(0, len(bits), 2)
        ]
    else:
        # Original four-symbol format for English, unchanged.
        symbols = [SYMBOLS[int(bits[i:i + 2], 2)] for i in range(0, len(bits), 2)]

    n, m = len(symbols), len(positions)
    anchor_to_symbol = {}
    for j, symbol in enumerate(symbols):
        anchor = positions[((2 * j + 1) * m) // (2 * n)]
        anchor_to_symbol[anchor] = symbol

    stego = "".join(
        character + anchor_to_symbol.get(i, "")
        for i, character in enumerate(carrier)
    )
    assert remove_hidden_symbols(stego) == carrier
    return stego


def decode_text(stego: str) -> str:
    """Recover message without the original carrier; reads both formats."""
    if not isinstance(stego, str) or not stego:
        raise ValueError("Paste or load a stego paragraph first.")

    # Original English format ALWAYS contains U+200C in the b'TS' header.
    old_format = "\u200c" in stego or "\u2063" in stego
    if old_format:
        values = [SYMBOL_TO_VALUE[c] for c in stego if c in SYMBOL_TO_VALUE]
        if len(values) % 4:
            raise ValueError("Hidden message is incomplete or corrupted.")
        bits = "".join(f"{value:02b}" for value in values)
    else:
        values = [ARABIC_SYMBOL_TO_BIT[c] for c in stego if c in ARABIC_SYMBOL_TO_BIT]
        if len(values) % 8:
            raise ValueError("Hidden message is incomplete or corrupted.")
        bits = "".join(str(value) for value in values)

    if not bits:
        raise ValueError("No hidden message found in this text.")
    packet = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
    if len(packet) < OVERHEAD_BYTES or packet[:2] != MAGIC:
        raise ValueError("This text does not contain a valid TS stego message.")

    secret_length = int.from_bytes(packet[2:4], "big")
    if len(packet) != OVERHEAD_BYTES + secret_length:
        raise ValueError("Hidden message length does not match; text may have changed.")

    payload = packet[HEADER_BYTES:-CHECKSUM_BYTES]
    found_checksum = int.from_bytes(packet[-CHECKSUM_BYTES:], "big")
    expected_checksum = zlib.crc32(packet[:HEADER_BYTES] + payload)
    if found_checksum != expected_checksum:
        raise ValueError("Hidden message failed CRC32 check; text was modified.")

    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Hidden message is not valid UTF-8.") from exc


def remove_hidden_symbols(stego: str) -> str:
    """Remove zero-width encoding characters to recover the original carrier."""
    return "".join(c for c in stego if c not in SYMBOL_TO_VALUE)


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
            info = capacity_info(carrier)
            stego = encode_text(carrier, secret)
            path.write_text(stego, encoding="utf-8")
            decoded = decode_text(path.read_text(encoding="utf-8"))

            print("\n--- ENCODER ---")
            print("Hiding method:", info["mode"])
            print("Available hiding positions:", info["eligible_positions"])
            print("Max secret size for this carrier:", info["max_secret_bytes"], "UTF-8 bytes")
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
            print("\nRecovered secret:", decode_text(path.read_text(encoding="utf-8")))

        elif mode == "3":
            stego = input("Paste the exact stego text (including invisible characters): ")
            print("\nRecovered secret:", decode_text(stego))

        elif mode == "4":
            carrier = input("Enter your carrier paragraph: ")
            info = capacity_info(carrier)
            print("\nHiding method:", info["mode"])
            print("Available hiding positions:", info["eligible_positions"])
            print("Raw embedding capacity:", info["raw_capacity_bits"], "bits")
            print("Protocol overhead:", info["overhead_bits"], "bits")
            print("Maximum secret:", info["max_secret_bytes"], "UTF-8 bytes")

        else:
            print("Invalid option.")

    except (ValueError, OSError) as exc:
        print("\nERROR:", exc)


if __name__ == "__main__":
    main()
