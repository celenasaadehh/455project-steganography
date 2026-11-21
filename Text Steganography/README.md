# Text Steganography — Member 2

## Overview
This module implements text steganography using invisible Unicode characters to hide secret messages inside ordinary paragraphs.

## How It Works
1. Convert the secret message into binary.
2. Represent every 2 bits using one of four zero-width Unicode characters.
3. Insert these characters throughout the carrier paragraph.
4. Extract the invisible characters to recover the secret message.

## Features
- Encode and decode secret messages.
- Preserve the visible paragraph.
- Decode without requiring the original paragraph.
- Check the paragraph's hiding capacity.
- Detect corrupted hidden data using CRC32.

## Files
- `text_stega.py` — Main Python implementation containing the encoder and decoder.

## Limitations
Zero-width characters can be detected or removed by certain applications. This technique provides steganography, not encryption.
