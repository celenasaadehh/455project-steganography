"""Automated tests for the website's text carrier (Member 2's text_stega.py).

The website calls hide(cover, message, password) and reveal(text, password);
strip_hidden() and capacity_info() are the two other public functions.

Tests marked "expectedFailure" describe behaviour the algorithm should have but
does not have yet. They are listed in the README under "Issues found". When a
teammate fixes one, unittest reports an "unexpected success" and the mark can be
removed.

Run from the "Member 5" folder:
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import random
import sys
import textwrap
import unicodedata
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common  # noqa: E402,F401
from common import text_stego as stego  # noqa: E402

COVER = "Hello there, see you at lunch tomorrow."
HIDDEN = set(stego.SYMBOLS)


def hidden_characters(text: str) -> str:
    return "".join(ch for ch in text if ch in HIDDEN)


def visible_characters(text: str) -> str:
    return "".join(ch for ch in text if ch not in HIDDEN)


class RoundTripTests(unittest.TestCase):
    def test_simple_message(self):
        self.assertEqual(stego.reveal(stego.hide(COVER, "the code is 4551")), "the code is 4551")

    def test_unicode_messages(self):
        for secret in ("مرحبا، نلتقي غدا", "Rendez-vous à 17h — café ☕", "🔐 key under the mat", "line one\nline two\ttabbed", " spaces kept "):
            with self.subTest(secret=secret):
                self.assertEqual(stego.reveal(stego.hide(COVER, secret)), secret)

    def test_unicode_cover_texts(self):
        for cover in ("مرحبا كيف حالك اليوم", "Ça va très bien, merci beaucoup", "今日はいい天気ですね", "Good morning 🙂 everyone"):
            with self.subTest(cover=cover):
                text = stego.hide(cover, "hidden")
                self.assertEqual(stego.reveal(text), "hidden")
                self.assertEqual(visible_characters(text), cover)

    def test_cover_with_several_lines(self):
        cover = "Dear all,\n\nThe meeting is moved to Monday.\n\nRegards"
        text = stego.hide(cover, "hidden")
        self.assertEqual(stego.reveal(text), "hidden")
        self.assertEqual(visible_characters(text), cover)

    def test_random_messages(self):
        rng = random.Random(455)
        letters = "abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789 .,!? éàü مرحبا 🔐"
        for case in range(30):
            secret = "".join(rng.choice(letters) for _ in range(rng.randint(1, 400)))
            password = "pass-%d" % case if case % 5 == 0 else None
            with self.subTest(case=case, password=password):
                self.assertEqual(stego.reveal(stego.hide(COVER, secret, password), password), secret)

    def test_hiding_again_is_refused(self):
        once = stego.hide(COVER, "first")
        with self.assertRaises(stego.TextStegoError):
            stego.hide(once, "second")


class InvisibilityTests(unittest.TestCase):
    """The visible text must stay exactly what the sender typed."""

    def test_visible_text_is_unchanged(self):
        text = stego.hide(COVER, "nothing to see")
        self.assertEqual(visible_characters(text), COVER)
        self.assertEqual(stego.strip_hidden(text), COVER)

    def test_only_invisible_characters_are_added(self):
        text = stego.hide(COVER, "nothing to see")
        added = len(text) - len(COVER)
        self.assertEqual(len(hidden_characters(text)), added)
        for ch in hidden_characters(text):
            self.assertEqual(unicodedata.category(ch), "Cf", "a hidden character is not an invisible format character")

    def test_hidden_part_goes_after_the_first_word(self):
        text = stego.hide(COVER, "x")
        self.assertTrue(text.startswith("Hello "))
        self.assertIn(text[len("Hello ")], HIDDEN)
        self.assertTrue(text.endswith(COVER[len("Hello "):]))

    def test_one_word_cover(self):
        text = stego.hide("Hello", "x")
        self.assertTrue(text.startswith("Hello"))
        self.assertEqual(visible_characters(text), "Hello")
        self.assertEqual(stego.reveal(text), "x")

    def test_size_of_the_hidden_part(self):
        # 4 invisible characters per byte; 8 bytes of overhead without a password, 46 with one.
        for secret in ("a", "hello", "é", "x" * 100):
            size = len(secret.encode("utf-8"))
            with self.subTest(secret=secret[:10]):
                self.assertEqual(len(hidden_characters(stego.hide(COVER, secret))), 4 * (size + 8))
                self.assertEqual(len(hidden_characters(stego.hide(COVER, secret, "pw"))), 4 * (size + 46))

    def test_without_password_the_result_is_always_the_same(self):
        self.assertEqual(stego.hide(COVER, "same"), stego.hide(COVER, "same"))

    def test_with_password_the_result_is_never_the_same(self):
        first, second = stego.hide(COVER, "same", "pw"), stego.hide(COVER, "same", "pw")
        self.assertNotEqual(first, second)
        self.assertEqual(stego.reveal(first, "pw"), stego.reveal(second, "pw"))


class LimitTests(unittest.TestCase):
    def test_capacity_is_the_message_limit(self):
        self.assertEqual(stego.capacity_info(COVER)["max_secret_bytes"], stego.MAX_SECRET_BYTES)
        self.assertEqual(stego.MAX_SECRET_BYTES, 65535)

    def test_longest_message(self):
        secret = "a" * stego.MAX_SECRET_BYTES
        self.assertEqual(stego.reveal(stego.hide(COVER, secret)), secret)
        with self.assertRaises(stego.TextStegoError):
            stego.hide(COVER, secret + "a")

    def test_limit_counts_bytes_not_characters(self):
        # "é" is one character but two bytes in UTF-8.
        self.assertEqual(stego.reveal(stego.hide(COVER, "é" * 32767)), "é" * 32767)
        with self.assertRaises(stego.TextStegoError):
            stego.hide(COVER, "é" * 32768)

    def test_capacity_does_not_depend_on_the_cover(self):
        secret = "b" * stego.MAX_SECRET_BYTES
        self.assertEqual(stego.reveal(stego.hide("Hi", secret)), secret)

    def test_long_cover(self):
        text = stego.hide("a" * 100_000, "x")
        self.assertEqual(stego.reveal(text), "x")

    def test_missing_cover_or_message(self):
        for cover in ("", "   ", "\n\t", None):
            with self.subTest(cover=cover), self.assertRaises(stego.TextStegoError):
                stego.hide(cover, "secret")
        for secret in ("", None):
            with self.subTest(secret=secret), self.assertRaises(stego.TextStegoError):
                stego.hide(COVER, secret)


class PasswordTests(unittest.TestCase):
    def setUp(self):
        self.locked = stego.hide(COVER, "top secret", "correct horse")

    def test_correct_password_opens_the_message(self):
        self.assertEqual(stego.reveal(self.locked, "correct horse"), "top secret")

    def test_wrong_password_is_refused(self):
        for wrong in ("Correct horse", "correct horse ", "correcthorse", "x"):
            with self.subTest(password=wrong), self.assertRaises(stego.TextPasswordError):
                stego.reveal(self.locked, wrong)

    def test_missing_password_is_refused(self):
        for missing in (None, ""):
            with self.subTest(password=missing), self.assertRaises(stego.TextPasswordError):
                stego.reveal(self.locked, missing)

    def test_password_is_ignored_for_an_unlocked_message(self):
        self.assertEqual(stego.reveal(stego.hide(COVER, "no lock"), "not needed"), "no lock")

    def test_unicode_password(self):
        text = stego.hide(COVER, "unicode password", "كلمة السر 🔑")
        self.assertEqual(stego.reveal(text, "كلمة السر 🔑"), "unicode password")

    def test_empty_password_is_refused_like_the_image_module(self):
        with self.assertRaises(stego.TextPasswordError):
            stego.hide(COVER, "secret", "")

    def test_password_error_is_a_text_stego_error(self):
        self.assertTrue(issubclass(stego.TextPasswordError, stego.TextStegoError))
        self.assertTrue(issubclass(stego.TextStegoError, ValueError))


class TamperingTests(unittest.TestCase):
    """After the text is edited, reveal() must return the right message or an error, never a wrong message."""

    def setUp(self):
        self.text = stego.hide(COVER, "do not change me")
        self.positions = [i for i, ch in enumerate(self.text) if ch in HIDDEN]

    def test_text_without_a_hidden_message(self):
        for text in (COVER, "", None, "   "):
            with self.subTest(text=text), self.assertRaises(stego.TextStegoError):
                stego.reveal(text)

    def test_every_single_character_substitution_is_detected(self):
        for position in self.positions:
            for replacement in stego.SYMBOLS:
                if replacement == self.text[position]:
                    continue
                damaged = self.text[:position] + replacement + self.text[position + 1:]
                with self.assertRaises(stego.TextStegoError):
                    stego.reveal(damaged)

    def test_every_single_character_deletion_is_detected(self):
        for position in self.positions:
            damaged = self.text[:position] + self.text[position + 1:]
            with self.assertRaises(stego.TextStegoError):
                stego.reveal(damaged)

    def test_deleting_a_whole_hidden_byte_is_detected(self):
        for start in self.positions[::4]:
            damaged = self.text[:start] + self.text[start + 4:]
            with self.assertRaises(stego.TextStegoError):
                stego.reveal(damaged)

    def test_cut_off_text_is_rejected(self):
        for keep in (1, 10, len(self.text) // 2):
            with self.subTest(keep=keep), self.assertRaises(stego.TextStegoError):
                stego.reveal(self.text[:keep])

    def test_damaged_locked_message_is_rejected(self):
        locked = stego.hide(COVER, "do not change me", "tamper")
        positions = [i for i, ch in enumerate(locked) if ch in HIDDEN]
        rng = random.Random(7)
        for position in rng.sample(positions[8:], 10):  # after the 2-byte "TL" tag
            replacement = next(ch for ch in stego.SYMBOLS if ch != locked[position])
            damaged = locked[:position] + replacement + locked[position + 1:]
            with self.assertRaises(stego.TextPasswordError):
                stego.reveal(damaged, "tamper")

    def test_two_stego_texts_pasted_together_are_rejected(self):
        with self.assertRaises(stego.TextStegoError):
            stego.reveal(self.text + " " + stego.hide("Another sentence here", "second"))

    def test_edits_to_the_visible_text_keep_the_message(self):
        edits = {
            "text added at the end": self.text + " Thanks!",
            "text added at the start": "Fwd: " + self.text,
            "upper case": self.text.upper(),
            "spaces trimmed": ("  " + self.text + "\n").strip(),
            "Unicode normalised (NFC)": unicodedata.normalize("NFC", self.text),
            "Unicode normalised (NFKC)": unicodedata.normalize("NFKC", self.text),
            "stored as JSON": json.loads(json.dumps(self.text)),
            "stored as UTF-8": self.text.encode("utf-8").decode("utf-8"),
            "stored as UTF-16": self.text.encode("utf-16").decode("utf-16"),
            "lines wrapped by an app": textwrap.fill(self.text, 30),
        }
        for name, edited in edits.items():
            with self.subTest(edit=name):
                self.assertEqual(stego.reveal(edited), "do not change me")

    def test_channels_that_drop_invisible_characters_destroy_the_message(self):
        filters = {
            "ASCII only": self.text.encode("ascii", "ignore").decode("ascii"),
            "printable characters only": "".join(ch for ch in self.text if ch.isprintable()),
            "hidden characters stripped": stego.strip_hidden(self.text),
        }
        for name, filtered in filters.items():
            with self.subTest(channel=name):
                self.assertEqual(visible_characters(filtered), COVER)
                with self.assertRaises(stego.TextStegoError):
                    stego.reveal(filtered)


class CoverJoinerTests(unittest.TestCase):
    """The cover's own invisible joiners (emoji, Persian) and wrong input types."""

    def test_emoji_made_of_joined_characters_survives_in_the_cover(self):
        # The family emoji is three emoji joined by U+200D. hide() must keep it so the emoji stays whole.
        cover = "Family \U0001F468\u200d\U0001F469\u200d\U0001F467 photo attached"
        text = stego.hide(cover, "x")
        self.assertEqual(stego.strip_hidden(text), cover)
        self.assertEqual(stego.reveal(text), "x")

    def test_persian_cover_keeps_its_zero_width_non_joiner(self):
        # Persian spelling uses U+200C inside words; hide() must keep it.
        cover = "می\u200cخواهم بروم"
        text = stego.hide(cover, "x")
        self.assertEqual(stego.strip_hidden(text), cover)
        self.assertEqual(stego.reveal(text), "x")

    def test_reply_containing_a_joined_emoji_keeps_the_message_readable(self):
        text = stego.hide(COVER, "still here")
        self.assertEqual(stego.reveal(text + " \U0001F468\u200d\U0001F469\u200d\U0001F467"), "still here")

    def test_message_of_the_wrong_type_raises_a_text_stego_error(self):
        for bad in (42, b"bytes", ["a"]):
            with self.subTest(message=type(bad).__name__), self.assertRaises(stego.TextStegoError):
                stego.hide(COVER, bad)


if __name__ == "__main__":
    unittest.main()
