# Text Steganography — Member 2

## Overview
This module implements text steganography using invisible Unicode characters to hide secret messages inside ordinary paragraphs. It is the text carrier of the Stego Studio website (Member 3), which calls `hide()` / `reveal()`.

## How It Works
1. Convert the secret message into binary, wrapped in a small packet (tag, length, CRC32).
2. English text: every 2 bits become one of four zero-width characters (U+200B, U+200C, U+2060, U+2063).
   Arabic text: every bit becomes U+200B or U+2060, which are safe between joined letters.
3. Insert the invisible run in one place, right after the first space of the carrier.
4. To decode, find the long run of invisible characters and turn it back into the secret.

## Features
- Encode and decode secret messages; decode without the original paragraph.
- Optional password: AES-256-GCM with a key from scrypt (same settings as Member 1's image module).
- Any carrier length, including one-word sentences.
- Persian text and joined emoji in the carrier are kept: only a long run (8 or more invisible characters) counts as a hidden message.
- Detects corrupted hidden data (CRC32 without a password, the GCM tag with one).
- Reads the website's first text format (tag `ZW`), so older website messages still open.

## Functions
- `encode_text(carrier, secret, password=None)` / `hide(...)`
- `decode_text(stego, password=None)` / `reveal(...)`
- `remove_hidden_symbols(stego)` / `strip_hidden(...)`
- `capacity_info(carrier)`
- Errors: `TextStegoError` (a `ValueError`) and `TextPasswordError` for a missing, empty or wrong password.

## Files
- `text_stega.py` — encoder, decoder and a small text menu (`python text_stega.py`).

Requires the `cryptography` package (already in `Member 3/requirements.txt`).

## Limitations
Zero-width characters can be detected or removed by certain applications. Without a password the message is only hidden, not secret, and CRC32 does not stop a deliberate swap (see Member 5's birthday attack).
