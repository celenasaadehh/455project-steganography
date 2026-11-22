"""Automated tests for the second text algorithm, in the "Text Steganography" folder (text_stega.py).

Its public functions are encode_text(carrier, secret), decode_text(stego),
capacity_info(carrier) and remove_hidden_symbols(stego). All errors are ValueError.

The website does not use this module yet (it uses Member 2's text_stego.py), so
these tests call it directly.

Run from the "Member 5" folder:
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import random
import sys
import unicodedata
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common  # noqa: E402
from common import letter_paragraph  # noqa: E402

stego = common.text_stega
if stego is None:
    raise unittest.SkipTest('The "Text Steganography" folder is not in the repository')

HIDDEN = set(stego.SYMBOLS)
CARRIER = ("Dear team, the weekly meeting is moved to Thursday afternoon in the main hall. " * 6).strip()


def hidden_characters(text: str) -> str:
    return "".join(ch for ch in text if ch in HIDDEN)


def english_letters(text: str) -> int:
    return sum("A" <= ch <= "Z" or "a" <= ch <= "z" for ch in text)


class RoundTripTests(unittest.TestCase):
    def test_simple_message(self):
        self.assertEqual(stego.decode_text(stego.encode_text(CARRIER, "the code is 4551")), "the code is 4551")

    def test_unicode_messages(self):
        for secret in ("مرحبا، نلتقي غدا", "Rendez-vous à 17h ☕", "🔐 key under the mat", "line one\nline two", " a "):
            with self.subTest(secret=secret):
                self.assertEqual(stego.decode_text(stego.encode_text(CARRIER, secret)), secret)

    def test_random_messages(self):
        rng = random.Random(455)
        letters = "abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789 .,!? éàü"
        limit = stego.capacity_info(CARRIER)["max_secret_bytes"]
        for case in range(30):
            secret = "".join(rng.choice(letters) for _ in range(rng.randint(1, limit // 2)))
            secret = secret.encode("utf-8")[:limit].decode("utf-8", "ignore") or "x"
            with self.subTest(case=case):
                self.assertEqual(stego.decode_text(stego.encode_text(CARRIER, secret)), secret)

    def test_decoding_does_not_need_the_original_paragraph(self):
        text = stego.encode_text(CARRIER, "blind decoding")
        self.assertEqual(stego.decode_text("Forwarded message:\n" + text), "blind decoding")

    def test_same_input_always_gives_the_same_text(self):
        self.assertEqual(stego.encode_text(CARRIER, "same"), stego.encode_text(CARRIER, "same"))


class InvisibilityTests(unittest.TestCase):
    def test_visible_text_is_unchanged(self):
        text = stego.encode_text(CARRIER, "nothing to see")
        self.assertEqual(stego.remove_hidden_symbols(text), CARRIER)
        self.assertEqual(len(text) - len(CARRIER), len(hidden_characters(text)))

    def test_only_invisible_format_characters_are_used(self):
        for ch in stego.SYMBOLS:
            self.assertEqual(unicodedata.category(ch), "Cf")

    def test_hidden_characters_are_spread_through_the_paragraph(self):
        text = stego.encode_text(CARRIER, "abc")
        positions = [i for i, ch in enumerate(text) if ch in HIDDEN]
        # Each hidden character sits right after an English letter ...
        self.assertTrue(all(("A" <= text[i - 1] <= "Z") or ("a" <= text[i - 1] <= "z") for i in positions))
        # ... and they cover most of the paragraph instead of forming one block.
        self.assertLess(positions[0], len(text) * 0.1)
        self.assertGreater(positions[-1], len(text) * 0.9)
        self.assertEqual(len(set(positions)), len(positions))

    def test_size_of_the_hidden_part(self):
        # 4 invisible characters per byte, 8 bytes of overhead (2 tag, 2 length, 4 CRC-32).
        for secret in ("a", "hello", "é", "x" * 40):
            size = len(secret.encode("utf-8"))
            with self.subTest(secret=secret[:10]):
                self.assertEqual(len(hidden_characters(stego.encode_text(CARRIER, secret))), 4 * (size + 8))

    def test_emoji_made_of_joined_characters_is_kept(self):
        # U+200D is not one of this module's four characters, so joined emoji survive.
        cover = "Family \U0001F468‍\U0001F469‍\U0001F467 " + letter_paragraph(80)
        text = stego.encode_text(cover, "hi")
        self.assertEqual(stego.remove_hidden_symbols(text), cover)
        self.assertEqual(stego.decode_text(text), "hi")

    def test_reply_containing_a_joined_emoji_keeps_the_message_readable(self):
        text = stego.encode_text(CARRIER, "still here")
        self.assertEqual(stego.decode_text(text + " \U0001F468‍\U0001F469‍\U0001F467"), "still here")


class CapacityTests(unittest.TestCase):
    def test_capacity_formula(self):
        # max_secret_bytes = floor(English letters / 4) - 8, never below 0.
        for letters in (0, 1, 31, 32, 35, 36, 39, 40, 115, 240, 1000):
            with self.subTest(letters=letters):
                info = stego.capacity_info(letter_paragraph(letters))
                self.assertEqual(info["carrier_letters"], letters)
                self.assertEqual(info["raw_capacity_bits"], 2 * letters)
                self.assertEqual(info["overhead_bits"], 64)
                self.assertEqual(info["max_secret_bytes"], max(0, letters // 4 - 8))

    def test_numbers_quoted_in_the_research_document(self):
        # Research.md, section 8: 115 letters hold 20 bytes, 240 letters hold 52 bytes.
        self.assertEqual(stego.capacity_info(letter_paragraph(115))["max_secret_bytes"], 20)
        self.assertEqual(stego.capacity_info(letter_paragraph(240))["max_secret_bytes"], 52)

    def test_reported_capacity_is_exact(self):
        for letters in (40, 41, 48, 115, 240, 999):
            carrier = letter_paragraph(letters)
            limit = stego.capacity_info(carrier)["max_secret_bytes"]
            with self.subTest(letters=letters, limit=limit):
                self.assertEqual(stego.decode_text(stego.encode_text(carrier, "z" * limit)), "z" * limit)
                with self.assertRaises(ValueError):
                    stego.encode_text(carrier, "z" * (limit + 1))

    def test_capacity_counts_bytes_not_characters(self):
        carrier = letter_paragraph(4 * (8 + 10))  # room for exactly 10 bytes
        self.assertEqual(stego.decode_text(stego.encode_text(carrier, "é" * 5)), "é" * 5)
        with self.assertRaises(ValueError):
            stego.encode_text(carrier, "é" * 6)

    def test_short_sentences_hold_nothing(self):
        # Fewer than 36 letters leave no room after the 8 bytes of overhead.
        for sentence in ("See you at five.", "Hello there, see you at lunch."):
            with self.subTest(sentence=sentence):
                self.assertEqual(stego.capacity_info(sentence)["max_secret_bytes"], 0)
                with self.assertRaises(ValueError):
                    stego.encode_text(sentence, "x")

    def test_only_english_letters_count(self):
        arabic = "مرحبا بكم جميعا في الاجتماع الأسبوعي يوم الخميس بعد الظهر في القاعة الرئيسية " * 3
        self.assertEqual(stego.capacity_info(arabic)["carrier_letters"], 0)
        self.assertEqual(stego.capacity_info("éèàùç ñ ü " * 20)["carrier_letters"], 0)
        self.assertEqual(stego.capacity_info("1234567890 !?.,;: " * 20)["max_secret_bytes"], 0)

    def test_longest_message(self):
        carrier = "a" * (4 * (stego.MAX_SECRET_BYTES + 8)) + "."
        secret = "Z" * stego.MAX_SECRET_BYTES
        self.assertEqual(stego.decode_text(stego.encode_text(carrier, secret)), secret)
        with self.assertRaises(ValueError):
            stego.encode_text(carrier + "aaaa", secret + "Z")


class InvalidInputTests(unittest.TestCase):
    def test_missing_carrier_or_secret(self):
        for carrier in ("", "   ", None, 42):
            with self.subTest(carrier=carrier), self.assertRaises(ValueError):
                stego.encode_text(carrier, "secret")
        for secret in ("", None, 42, b"bytes"):
            with self.subTest(secret=secret), self.assertRaises(ValueError):
                stego.encode_text(CARRIER, secret)

    def test_carrier_that_already_contains_hidden_characters_is_refused(self):
        for symbol in stego.SYMBOLS:
            with self.subTest(symbol=hex(ord(symbol))), self.assertRaises(ValueError):
                stego.encode_text(CARRIER + symbol, "x")
        with self.assertRaises(ValueError):
            stego.encode_text(stego.encode_text(CARRIER, "first"), "second")

    def test_persian_text_is_refused_with_a_clear_error(self):
        # Persian spelling uses U+200C, which is one of the four reserved characters.
        with self.assertRaisesRegex(ValueError, "reserved invisible characters"):
            stego.encode_text("می‌خواهم " + letter_paragraph(80), "x")

    def test_decoding_text_without_a_message(self):
        for text in (CARRIER, "", None, 42):
            with self.subTest(text=repr(text)[:20]), self.assertRaises(ValueError):
                stego.decode_text(text)


class TamperingTests(unittest.TestCase):
    """After the text is edited, decode_text() must return the right secret or an error, never a wrong secret."""

    def setUp(self):
        self.text = stego.encode_text(CARRIER, "do not change me")
        self.positions = [i for i, ch in enumerate(self.text) if ch in HIDDEN]

    def test_every_single_character_substitution_is_detected(self):
        for position in self.positions:
            for replacement in stego.SYMBOLS:
                if replacement != self.text[position]:
                    damaged = self.text[:position] + replacement + self.text[position + 1:]
                    with self.assertRaises(ValueError):
                        stego.decode_text(damaged)

    def test_every_single_character_deletion_is_detected(self):
        for position in self.positions:
            with self.assertRaises(ValueError):
                stego.decode_text(self.text[:position] + self.text[position + 1:])

    def test_cut_off_text_is_rejected(self):
        for keep in (10, len(self.text) // 2, len(self.text) - 20):
            with self.subTest(keep=keep), self.assertRaises(ValueError):
                stego.decode_text(self.text[:keep])

    def test_two_stego_texts_pasted_together_are_rejected(self):
        other = stego.encode_text(letter_paragraph(200), "second")
        with self.assertRaises(ValueError):
            stego.decode_text(self.text + " " + other)

    def test_edits_to_the_visible_text_keep_the_message(self):
        edits = {
            "text added at the end": self.text + " Thanks!",
            "text added at the start": "Fwd: " + self.text,
            "upper case": self.text.upper(),
            "spaces trimmed": ("  " + self.text + "\n").strip(),
            "Unicode normalised (NFC)": unicodedata.normalize("NFC", self.text),
            "Unicode normalised (NFKC)": unicodedata.normalize("NFKC", self.text),
            "stored as JSON": json.loads(json.dumps(self.text)),
            "stored as UTF-16": self.text.encode("utf-16").decode("utf-16"),
        }
        for name, edited in edits.items():
            with self.subTest(edit=name):
                self.assertEqual(stego.decode_text(edited), "do not change me")

    def test_channels_that_drop_invisible_characters_destroy_the_message(self):
        for name, filtered in {
            "ASCII only": self.text.encode("ascii", "ignore").decode("ascii"),
            "printable characters only": "".join(ch for ch in self.text if ch.isprintable()),
        }.items():
            with self.subTest(channel=name):
                self.assertEqual(filtered, CARRIER)
                with self.assertRaises(ValueError):
                    stego.decode_text(filtered)


if __name__ == "__main__":
    unittest.main()
