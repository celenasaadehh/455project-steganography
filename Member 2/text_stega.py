
#For English carriers, each symbol holds 2 bits. For carriers containing Arabic
#letters, joining-safe symbols hold 1 bit each..

from pathlib import Path
import unicodedata
import zlib

# English mapping: 2 bits per invisible character.
SYMBOLS = ("\u200b", "\u200c", "\u2060", "\u2063")
SYMBOL_TO_VALUE = {symbol: value for value, symbol in enumerate(SYMBOLS)}

# Arabic mapping: 1 bit per invisible character, placed at a word boundary.
ARABIC_BIT_SYMBOLS = ("\u200b", "\u2060")
ARABIC_SYMBOL_TO_BIT = {symbol: value for value, symbol in enumerate(ARABIC_BIT_SYMBOLS)}

MAGIC = b"TS"
HEADER_BYTES = 4       # 2 magic bytes + 2-byte message length
CHECKSUM_BYTES = 4     # CRC32 for detecting accidental corruption
OVERHEAD_BYTES = HEADER_BYTES + CHECKSUM_BYTES
MAX_SECRET_BYTES = 65535


def _arabic_letter(character: str) -> bool:
    return (
        unicodedata.category(character).startswith("L")
        and unicodedata.name(character, "").startswith("ARABIC")
    )


def _choose_mode(carrier: str) -> str:
    if any(_arabic_letter(character) for character in carrier):
        return "Arabic (after first space)"
    return "English (after first word)"


def _check_carrier(carrier: str) -> None:
    if not isinstance(carrier, str) or not carrier.strip():
        raise ValueError("Enter a nonempty carrier paragraph.")
    if any(character in SYMBOL_TO_VALUE for character in carrier):
        raise ValueError("Carrier already contains reserved invisible characters. Use clean text.")


def capacity_info(carrier: str) -> dict:
    """Report packet capacity; not limited by the number of carrier letters."""
    _check_carrier(carrier)
    mode = _choose_mode(carrier)
    return {
        "mode": mode,
        "max_secret_bytes": MAX_SECRET_BYTES,
        "overhead_bits": 8 * OVERHEAD_BYTES,
        "symbols_per_byte": 8 if mode.startswith("Arabic") else 4,
    }


def encode_text(carrier: str, secret: str) -> str:
    """Hide a UTF-8 secret inside a carrier without changing visible text."""
    _check_carrier(carrier)
    if not isinstance(secret, str) or not secret:
        raise ValueError("Enter a nonempty secret message.")

    secret_bytes = secret.encode("utf-8")
    if len(secret_bytes) > MAX_SECRET_BYTES:
        raise ValueError("Secret must be 65535 UTF-8 bytes or fewer.")

    header = MAGIC + len(secret_bytes).to_bytes(2, "big")
    checksum = zlib.crc32(header + secret_bytes).to_bytes(4, "big")
    packet = header + secret_bytes + checksum
    bits = "".join(f"{byte:08b}" for byte in packet)

    if _choose_mode(carrier).startswith("Arabic"):
        hidden = "".join(ARABIC_BIT_SYMBOLS[int(bit)] for bit in bits)
    else:
        hidden = "".join(
            SYMBOLS[int(bits[index:index + 2], 2)]
            for index in range(0, len(bits), 2)
        )

    # Member 3's short-carrier approach: put the hidden run in one location.
    # A normal space boundary reduces interference with joined Arabic letters.
    first_space = carrier.find(" ")
    position = first_space + 1 if first_space >= 0 else len(carrier)
    stego = carrier[:position] + hidden + carrier[position:]
    assert remove_hidden_symbols(stego) == carrier
    return stego


def decode_text(stego: str) -> str:
    """Recover and validate a secret using only the stego paragraph."""
    if not isinstance(stego, str) or not stego:
        raise ValueError("Paste or load a stego paragraph first.")

    # The English TS header always contains U+200C; the Arabic mapping never does.
    english_format = "\u200c" in stego or "\u2063" in stego
    if english_format:
        values = [SYMBOL_TO_VALUE[ch] for ch in stego if ch in SYMBOL_TO_VALUE]
        if len(values) % 4:
            raise ValueError("Hidden message is incomplete or corrupted.")
        bits = "".join(f"{value:02b}" for value in values)
    else:
        values = [ARABIC_SYMBOL_TO_BIT[ch] for ch in stego if ch in ARABIC_SYMBOL_TO_BIT]
        if len(values) % 8:
            raise ValueError("Hidden message is incomplete or corrupted.")
        bits = "".join(str(value) for value in values)

    if not bits:
        raise ValueError("No hidden message found in this text.")
    packet = bytes(int(bits[index:index + 8], 2) for index in range(0, len(bits), 8))
    if len(packet) < OVERHEAD_BYTES or packet[:2] != MAGIC:
        raise ValueError("This text does not contain a valid TS stego message.")

    message_length = int.from_bytes(packet[2:4], "big")
    if len(packet) != OVERHEAD_BYTES + message_length:
        raise ValueError("Hidden message length does not match; text may have changed.")
    payload = packet[HEADER_BYTES:-CHECKSUM_BYTES]
    found_checksum = int.from_bytes(packet[-CHECKSUM_BYTES:], "big")
    if found_checksum != zlib.crc32(packet[:HEADER_BYTES] + payload):
        raise ValueError("Hidden message failed CRC32 check; text was modified.")

    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Hidden message is not valid UTF-8.") from exc


def remove_hidden_symbols(stego: str) -> str:
    """Return the original carrier by removing the four reserved characters."""
    return "".join(ch for ch in stego if ch not in SYMBOL_TO_VALUE)


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
            print("\nRecovered secret:", decode_text(path.read_text(encoding="utf-8")))

        elif mode == "3":
            stego = input("Paste the exact stego text (including invisible characters): ")
            print("\nRecovered secret:", decode_text(stego))

        elif mode == "4":
            carrier = input("Enter your carrier paragraph: ")
            info = capacity_info(carrier)
            print("\nHiding method:", info["mode"])
            print("No minimum carrier length: hidden data is placed after the first word.")
            print("Invisible characters per packet byte:", info["symbols_per_byte"])
            print("Protocol overhead:", info["overhead_bits"], "bits")
            print("Maximum secret:", info["max_secret_bytes"], "UTF-8 bytes")

        else:
            print("Invalid option.")

    except (ValueError, OSError) as exc:
        print("\nERROR:", exc)


if __name__ == "__main__":
    main()
