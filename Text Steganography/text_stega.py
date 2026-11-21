
from pathlib import Path
import zlib
# Four invisible Unicode characters; 2 bits per inserted character.
# They are deliberately different from the text's visible letters.
SYMBOLS = ("\u200b", "\u200c", "\u2060", "\u2063")
SYMBOL_TO_VALUE = {symbol: index for index, symbol in enumerate(SYMBOLS)}
MAGIC = b"TS"  # Recognizes this format when decoding
HEADER_BYTES = 4  # 2 magic bytes + 2 bytes of secret length
CHECKSUM_BYTES = 4  # CRC32 detects accidental corruption
OVERHEAD_BYTES = HEADER_BYTES + CHECKSUM_BYTES
MAX_SECRET_BYTES = 65535


def _ascii_letter(character: str) -> bool:
    return "A" <= character <= "Z" or "a" <= character <= "z"


def _check_carrier(carrier: str) -> None:
    if not isinstance(carrier, str) or not carrier.strip():
        raise ValueError("Enter a nonempty carrier paragraph.")
    if any(character in SYMBOL_TO_VALUE for character in carrier):
        raise ValueError(
            "The carrier already contains reserved invisible characters. "
            "Use a clean paragraph."
        )


def capacity_info(carrier: str) -> dict:
    """Calculate theoretical payload capacity for this exact carrier."""
    _check_carrier(carrier)
    available_letters = sum(_ascii_letter(c) for c in carrier)
    # 4 carrier letters hold 1 byte (2 hidden bits per letter).
    return {
        "carrier_letters": available_letters,
        "raw_capacity_bits": 2 * available_letters,
        "max_secret_bytes": min(
            MAX_SECRET_BYTES, max(0, available_letters // 4 - OVERHEAD_BYTES)
        ),
        "overhead_bits": 8 * OVERHEAD_BYTES,
    }


def encode_text(carrier: str, secret: str) -> str:
    """Return stego text; decode_text needs only this output."""
    _check_carrier(carrier)
    if not isinstance(secret, str) or not secret:
        raise ValueError("Enter a nonempty secret message.")

    secret_bytes = secret.encode("utf-8")
    if len(secret_bytes) > MAX_SECRET_BYTES:
        raise ValueError("Secret must be 65535 UTF-8 bytes or fewer.")

    info = capacity_info(carrier)
    if len(secret_bytes) > info["max_secret_bytes"]:
        required_letters = 4 * (OVERHEAD_BYTES + len(secret_bytes))
        raise ValueError(
            f"Not enough carrier capacity: {len(secret_bytes)} secret bytes "
            f"need at least {required_letters} English letters; "
            f"this carrier has {info['carrier_letters']}. "
            f"Maximum secret here: {info['max_secret_bytes']} bytes."
        )

    header = MAGIC + len(secret_bytes).to_bytes(2, "big")
    checksum = zlib.crc32(header + secret_bytes).to_bytes(4, "big")
    packet = header + secret_bytes + checksum
    bits = "".join(f"{byte:08b}" for byte in packet)
    symbols = [SYMBOLS[int(bits[i : i + 2], 2)] for i in range(0, len(bits), 2)]

    # Spread invisible characters evenly among English letters. This is not
    # needed for decoding, which extracts them in the order they appear.
    positions = [i for i, character in enumerate(carrier) if _ascii_letter(character)]
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
    """Extract and validate a UTF-8 secret WITHOUT the original carrier."""
    if not isinstance(stego, str) or not stego:
        raise ValueError("Paste or load a stego paragraph first.")

    values = [SYMBOL_TO_VALUE[c] for c in stego if c in SYMBOL_TO_VALUE]
    if not values:
        raise ValueError("No hidden message found in this text.")
    if len(values) % 4:
        raise ValueError("Hidden message is incomplete or corrupted.")

    bits = "".join(f"{value:02b}" for value in values)
    packet = bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))
    if len(packet) < OVERHEAD_BYTES or packet[:2] != MAGIC:
        raise ValueError("This text does not contain a valid TS stego message.")

    secret_length = int.from_bytes(packet[2:4], "big")
    expected_packet_bytes = OVERHEAD_BYTES + secret_length
    if len(packet) != expected_packet_bytes:
        raise ValueError("Hidden message length does not match; text may have been changed.")

    payload = packet[HEADER_BYTES:-CHECKSUM_BYTES]
    found_checksum = int.from_bytes(packet[-CHECKSUM_BYTES:], "big")
    expected_checksum = zlib.crc32(packet[:HEADER_BYTES] + payload)
    if found_checksum != expected_checksum:
        raise ValueError("Hidden message failed the checksum: the text was modified.")

    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Hidden message is not valid UTF-8.") from exc


def remove_hidden_symbols(stego: str) -> str:
    """For demonstration: reveal the original visible carrier text."""
    return "".join(character for character in stego if character not in SYMBOL_TO_VALUE)


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
            print("Carrier English letters:", info["carrier_letters"])
            print("Max secret size for this carrier:", info["max_secret_bytes"], "UTF-8 bytes")
            print("Secret bytes:", len(secret.encode("utf-8")))
            print("Visible text unchanged:", remove_hidden_symbols(stego) == carrier)
            print("Saved stego text to:", path)
            print("Stego paragraph (looks normal):\n", stego)
            print("\n--- INDEPENDENT DECODER TEST ---")
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
            print("\nCarrier English letters:", info["carrier_letters"])
            print("Raw embedding capacity:", info["raw_capacity_bits"], "bits")
            print("Protocol overhead:", info["overhead_bits"], "bits")
            print("Maximum secret:", info["max_secret_bytes"], "UTF-8 bytes")

        else:
            print("Invalid option.")

    except (ValueError, OSError) as exc:
        print("\nERROR:", exc)


if __name__ == "__main__":
    main()
