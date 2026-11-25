"""Automated tests for the image-carrier algorithm (Member 1's image_stego.py).

Only the functions the website uses are called: capacity(), embed(), extract()
and measure(). The tests therefore keep working if the inside of the algorithm
changes, as long as its behaviour stays the same.

Run from the "Member 5" folder:
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import os
import random
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common  # noqa: E402
from common import image_stego as stego  # noqa: E402
from common import to_array, to_bytes, to_image  # noqa: E402

JPEG_READY = common.jpeg_ready()
NEEDS_JPEG = "Member 1's JPEG helper is not built on this machine (see Member 1/support/TECHNICAL_GUIDE.md)"


class ImageTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = common.gradient_image()
        cls.cover = to_bytes(cls.image)

    def assert_round_trip(self, cover: bytes, message, password=None, output_format="PNG"):
        result = stego.embed(cover, message, password=password, output_format=output_format)
        expected = message.encode("utf-8") if isinstance(message, str) else message
        self.assertEqual(stego.extract(result.image, password=password), expected)
        return result


class RoundTripTests(ImageTestCase):
    """What goes in must come out, byte for byte."""

    def test_text_message(self):
        result = self.assert_round_trip(self.cover, "Meet me at the library at five.")
        self.assertEqual(result.output_format, "PNG")
        self.assertEqual(result.media_type, "image/png")
        self.assertEqual(result.message_bytes, len("Meet me at the library at five."))

    def test_unicode_message(self):
        for message in ("مرحبا، نلتقي غدا", "Rendez-vous à 17h — café ☕", "🔐🕵️‍♀️ secret", "line one\nline two\ttabbed"):
            with self.subTest(message=message):
                self.assert_round_trip(self.cover, message)

    def test_binary_message_with_every_byte_value(self):
        self.assert_round_trip(self.cover, bytes(range(256)))

    def test_empty_message(self):
        self.assert_round_trip(self.cover, b"")

    def test_one_byte_messages(self):
        for value in (0, 1, 127, 128, 255):
            with self.subTest(value=value):
                self.assert_round_trip(self.cover, bytes([value]))

    def test_bmp_output(self):
        result = self.assert_round_trip(to_bytes(self.image, "BMP"), b"bitmap carrier", output_format="BMP")
        self.assertEqual(result.media_type, "image/bmp")
        self.assertEqual(to_image(result.image).format, "BMP")

    def test_output_format_name_is_not_case_sensitive(self):
        for name in ("png", "Png", "bmp"):
            with self.subTest(name=name):
                self.assert_round_trip(self.cover, b"format name", output_format=name)

    def test_different_kinds_of_cover_image(self):
        covers = {
            "noise": common.noise_image(),
            "solid colour": common.flat_image(),
            "checkerboard": common.checker_image(),
            "greyscale": self.image.convert("L"),
            "palette": self.image.convert("P"),
            "black and white": self.image.convert("1"),
            "with alpha channel": self.image.convert("RGBA"),
            "odd dimensions": common.gradient_image(201, 131),
            "one pixel wide": common.noise_image(1, 4000),
            "one pixel high": common.noise_image(4000, 1),
        }
        for name, image in covers.items():
            with self.subTest(cover=name):
                self.assert_round_trip(to_bytes(image), f"hidden in {name}")

    def test_gallery_pictures_of_the_website(self):
        covers = common.gallery_covers()
        if not covers:
            self.skipTest("Member 3's gallery pictures are not in the repository")
        for name, cover in covers.items():
            with self.subTest(picture=name):
                self.assert_round_trip(cover, f"gallery picture {name}")

    def test_random_messages_of_random_length(self):
        rng = random.Random(455)
        limit = stego.capacity(self.cover, encrypted=True).max_message_bytes
        for case in range(20):
            message = rng.randbytes(rng.randint(0, limit))
            password = "pass-%d" % case if case % 4 == 0 else None
            with self.subTest(case=case, length=len(message), password=password):
                self.assert_round_trip(self.cover, message, password=password)

    def test_embedding_again_replaces_the_previous_message(self):
        first = stego.embed(self.cover, b"first message")
        second = stego.embed(first.image, b"second message")
        self.assertEqual(stego.extract(second.image), b"second message")


class PasswordTests(ImageTestCase):
    def setUp(self):
        self.locked = stego.embed(self.cover, "top secret", password="correct horse")

    def test_correct_password_opens_the_message(self):
        self.assertEqual(stego.extract(self.locked.image, password="correct horse"), b"top secret")

    def test_wrong_password_is_refused(self):
        for wrong in ("Correct horse", "correct horse ", "correcthorse", "x"):
            with self.subTest(password=wrong), self.assertRaises(stego.PasswordError):
                stego.extract(self.locked.image, password=wrong)

    def test_missing_password_is_refused(self):
        with self.assertRaises(stego.PasswordError):
            stego.extract(self.locked.image)

    def test_password_is_ignored_for_an_unlocked_message(self):
        unlocked = stego.embed(self.cover, "no lock")
        self.assertEqual(stego.extract(unlocked.image, password="not needed"), b"no lock")

    def test_unicode_password(self):
        self.assert_round_trip(self.cover, "unicode password", password="كلمة السر 🔑")

    def test_invalid_passwords_are_rejected_when_hiding(self):
        for bad in ("", 12345, b"bytes", "p" * 1025):
            with self.subTest(password=repr(bad)[:20]), self.assertRaises(stego.PasswordError):
                stego.embed(self.cover, b"x", password=bad)

    def test_longest_allowed_password(self):
        self.assert_round_trip(self.cover, b"x", password="p" * 1024)

    def test_same_message_and_password_never_give_the_same_file(self):
        again = stego.embed(self.cover, "top secret", password="correct horse")
        self.assertNotEqual(self.locked.image, again.image)
        self.assertEqual(stego.extract(again.image, password="correct horse"), b"top secret")


class CapacityTests(ImageTestCase):
    def test_reported_capacity_is_exact(self):
        for encrypted, password in ((False, None), (True, "capacity")):
            with self.subTest(encrypted=encrypted):
                limit = stego.capacity(self.cover, encrypted=encrypted).max_message_bytes
                self.assertGreater(limit, 0)
                self.assert_round_trip(self.cover, b"A" * limit, password=password)
                with self.assertRaises(stego.CapacityError):
                    stego.embed(self.cover, b"A" * (limit + 1), password=password)

    def test_password_costs_twelve_bytes_of_capacity(self):
        plain = stego.capacity(self.cover, encrypted=False).max_message_bytes
        locked = stego.capacity(self.cover, encrypted=True).max_message_bytes
        self.assertEqual(plain - locked, 12)

    def test_capacity_grows_with_the_image(self):
        sizes = [(64, 64), (128, 128), (256, 256), (512, 512)]
        limits = [stego.capacity(to_bytes(common.noise_image(w, h))).max_message_bytes for w, h in sizes]
        self.assertEqual(limits, sorted(limits))
        self.assertEqual(len(set(limits)), len(limits))

    def test_capacity_report_describes_the_image(self):
        report = stego.capacity(to_bytes(common.gradient_image(201, 131)), "PNG", encrypted=False)
        self.assertEqual((report.width, report.height), (201, 131))
        self.assertEqual((report.input_format, report.output_format), ("PNG", "PNG"))
        self.assertTrue(report.can_embed)
        self.assertFalse(report.encrypted)

    def test_embed_reports_the_same_capacity(self):
        limit = stego.capacity(self.cover, encrypted=False).max_message_bytes
        self.assertEqual(stego.embed(self.cover, b"x").capacity_bytes, limit)

    def test_images_too_small_for_any_message(self):
        for size in ((1, 1), (3, 3), (8, 8), (16, 16)):
            with self.subTest(size=size):
                tiny = to_bytes(common.noise_image(*size))
                report = stego.capacity(tiny)
                self.assertFalse(report.can_embed)
                self.assertEqual(report.max_message_bytes, 0)
                with self.assertRaises(stego.CapacityError):
                    stego.embed(tiny, b"")

    def test_small_images_hold_exactly_what_they_report(self):
        for side in (24, 28, 32, 40, 48):
            with self.subTest(side=side):
                small = to_bytes(common.noise_image(side, side))
                report = stego.capacity(small, encrypted=False)
                if report.can_embed:
                    self.assert_round_trip(small, b"z" * report.max_message_bytes)
                with self.assertRaises(stego.CapacityError):
                    stego.embed(small, b"z" * (report.max_message_bytes + 1))

    def test_message_over_the_two_megabyte_limit(self):
        with self.assertRaises(stego.CapacityError):
            stego.embed(self.cover, b"a" * (stego.MAX_MSG + 1))


class DistortionTests(ImageTestCase):
    """The stego image must look the same as the cover."""

    def test_pixels_change_by_at_most_one_level(self):
        limit = stego.capacity(self.cover, encrypted=False).max_message_bytes
        result = stego.embed(self.cover, random.Random(1).randbytes(limit))
        difference = np.abs(to_array(self.cover) - to_array(result.image))
        self.assertEqual(int(difference.max()), 1)

    def test_size_and_colour_mode_are_kept(self):
        result = stego.embed(self.cover, b"same shape")
        out = to_image(result.image)
        self.assertEqual(out.size, self.image.size)
        self.assertEqual(out.mode, "RGB")

    def test_number_of_changed_values_stays_under_the_design_bound(self):
        # The method hides 3 bits in a group of 7 colour values and changes at most
        # one value of the group, for the 43-byte header and for the message + 4-byte check.
        for length in (0, 10, 200, 1000):
            with self.subTest(length=length):
                result = stego.embed(self.cover, random.Random(length).randbytes(length))
                changed = int(np.count_nonzero(to_array(self.cover) != to_array(result.image)))
                groups = (stego.HEADER_BYTES * 8 + 2) // 3 + ((length + 4) * 8 + 2) // 3
                self.assertLessEqual(changed, groups)
                self.assertGreater(changed, 0)

    def test_quality_stays_high_even_when_the_image_is_full(self):
        limit = stego.capacity(self.cover, encrypted=False).max_message_bytes
        full = stego.embed(self.cover, random.Random(2).randbytes(limit))
        short = stego.embed(self.cover, b"short")
        self.assertGreater(stego.measure(self.cover, full.image).psnr_db, 55)
        self.assertGreater(stego.measure(self.cover, short.image).psnr_db, 70)

    def test_longer_messages_distort_more(self):
        scores = []
        for length in (10, 100, 1000, 3000):
            result = stego.embed(self.cover, random.Random(3).randbytes(length))
            scores.append(stego.measure(self.cover, result.image).psnr_db)
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_measure_agrees_with_a_direct_calculation(self):
        result = stego.embed(self.cover, random.Random(4).randbytes(500))
        report = stego.measure(self.cover, result.image)
        difference = to_array(self.cover) - to_array(result.image)
        mse = float(np.mean(difference.astype(np.float64) ** 2))
        self.assertAlmostEqual(report.mse, mse, places=12)
        self.assertAlmostEqual(report.psnr_db, 10 * np.log10(255 ** 2 / mse), places=9)
        self.assertAlmostEqual(report.changed_rgb_fraction, np.count_nonzero(difference) / difference.size, places=12)

    def test_measure_of_identical_images(self):
        report = stego.measure(self.cover, self.cover)
        self.assertEqual(report.mse, 0)
        self.assertIsNone(report.psnr_db)
        self.assertEqual(report.changed_rgb_fraction, 0)

    def test_measure_refuses_images_of_different_size(self):
        with self.assertRaises(stego.ImageError):
            stego.measure(self.cover, to_bytes(common.gradient_image(100, 100)))

    def test_transparency_is_preserved(self):
        pixels = np.array(self.image.convert("RGBA"))
        pixels[:40, :, 3] = 0      # fully transparent rows
        pixels[40:80, :, 3] = 128  # half transparent rows
        cover = to_bytes(Image.fromarray(pixels))
        result = stego.embed(cover, b"transparent cover")
        out = np.array(to_image(result.image))
        self.assertTrue(np.array_equal(out[:, :, 3], pixels[:, :, 3]), "alpha channel changed")
        self.assertTrue(np.array_equal(out[:40], pixels[:40]), "invisible pixels were modified")
        self.assertEqual(stego.extract(result.image), b"transparent cover")

    def test_transparent_cover_needs_png_output(self):
        pixels = np.array(self.image.convert("RGBA"))
        pixels[:40, :, 3] = 0
        cover = to_bytes(Image.fromarray(pixels))
        with self.assertRaises(stego.ImageError):
            stego.embed(cover, b"x", output_format="BMP")


class InvalidInputTests(ImageTestCase):
    def test_files_that_are_not_supported_images(self):
        bad_files = {
            "empty": b"",
            "random bytes": random.Random(5).randbytes(500),
            "text": b"this is not an image",
            "GIF": to_bytes(self.image.convert("P"), "GIF"),
            "truncated PNG": self.cover[: len(self.cover) // 2],
        }
        for name, data in bad_files.items():
            with self.subTest(file=name):
                with self.assertRaises(stego.ImageError):
                    stego.embed(data, b"x")
                with self.assertRaises(stego.ImageError):
                    stego.extract(data)
                with self.assertRaises(stego.ImageError):
                    stego.capacity(data)

    def test_cover_must_be_bytes(self):
        for bad in (None, "cover.png", bytearray(self.cover), 42):
            with self.subTest(cover=type(bad).__name__), self.assertRaises(stego.ImageError):
                stego.embed(bad, b"x")

    def test_message_must_be_text_or_bytes(self):
        for bad in (None, 42, 3.5, ["a"], bytearray(b"a")):
            with self.subTest(message=type(bad).__name__), self.assertRaises(stego.PayloadError):
                stego.embed(self.cover, bad)

    def test_unknown_output_formats(self):
        for bad in ("GIF", "HEIC", "TIFF", "", None, 7):
            with self.subTest(output_format=bad), self.assertRaises(stego.ImageError):
                stego.embed(self.cover, b"x", output_format=bad)

    def test_every_error_is_a_stego_error(self):
        # The website shows StegoError messages to the user, so nothing else may escape.
        for error in (stego.ImageError, stego.CapacityError, stego.PayloadError,
                      stego.PasswordError, stego.DependencyError):
            self.assertTrue(issubclass(error, stego.StegoError))
        self.assertTrue(issubclass(stego.StegoError, ValueError))

    def test_jpeg_without_the_helper_reports_a_missing_dependency(self):
        with patch.dict(os.environ, {"STEGO_JPEG_TOOL": "missing/jpegtool"}):
            with self.assertRaises(stego.DependencyError):
                stego.embed(self.cover, b"x", output_format="JPEG")


class TamperingTests(ImageTestCase):
    """After the stego image is edited, extract() must return the right message or an error, never a wrong message."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.message = b"do not change me"
        cls.stego = stego.embed(cls.cover, cls.message).image
        cls.stego_image = to_image(cls.stego)

    def test_clean_image_has_no_message(self):
        for name, cover in common.synthetic_covers().items():
            with self.subTest(cover=name), self.assertRaises(stego.PayloadError):
                stego.extract(cover)

    def test_lossless_copies_keep_the_message(self):
        copies = {
            "saved again as PNG": to_bytes(self.stego_image),
            "PNG with maximum compression": to_bytes(self.stego_image, optimize=True, compress_level=9),
            "converted to BMP": to_bytes(self.stego_image, "BMP"),
            "BMP converted back to PNG": to_bytes(to_image(to_bytes(self.stego_image, "BMP"))),
            "alpha channel added": to_bytes(self.stego_image.convert("RGBA")),
        }
        for name, data in copies.items():
            with self.subTest(copy=name):
                self.assertEqual(stego.extract(data), self.message)

    def test_edited_images_are_rejected(self):
        image = self.stego_image
        brighter = Image.fromarray(np.clip(np.asarray(image).astype(np.int16) + 1, 0, 255).astype(np.uint8))
        edits = {
            "cropped by one column": image.crop((1, 0, image.width, image.height)),
            "cropped at the bottom": image.crop((0, 0, image.width, image.height - 8)),
            "resized to half": image.resize((image.width // 2, image.height // 2)),
            "resized and restored": image.resize((image.width // 2, image.height // 2)).resize(image.size),
            "rotated": image.rotate(90, expand=True),
            "mirrored": image.transpose(Image.Transpose.FLIP_LEFT_RIGHT),
            "one level brighter": brighter,
            "greyscale": image.convert("L"),
        }
        for name, edited in edits.items():
            with self.subTest(edit=name), self.assertRaises(stego.StegoError):
                stego.extract(to_bytes(edited))

    def test_lossy_jpeg_copy_is_rejected(self):
        # Saving the PNG as a JPEG photo changes most pixel values, so the message is gone.
        with self.assertRaises(stego.StegoError):
            stego.extract(to_bytes(self.stego_image, "JPEG", quality=95))

    def test_undoing_any_single_embedding_change_is_detected(self):
        # Every value that embedding changed carries part of the header or the message,
        # so putting one of them back must be noticed by the checksum. The only exception
        # is the last group of the header and of the message: it can end with one or two
        # unused padding bits, and a change that only set padding does not alter the data.
        before, after = to_array(self.cover), to_array(self.stego)
        positions = np.argwhere(before != after)
        self.assertGreater(len(positions), 0)
        unnoticed = 0
        for y, x, channel in positions:
            damaged = after.copy()
            damaged[y, x, channel] = before[y, x, channel]
            try:
                recovered = stego.extract(to_bytes(Image.fromarray(damaged.astype(np.uint8))))
            except stego.PayloadError:
                continue
            self.assertEqual(recovered, self.message)
            unnoticed += 1
        self.assertLessEqual(unnoticed, 2)

    def test_random_bit_flips_never_produce_a_wrong_message(self):
        rng = np.random.default_rng(455)
        pixels = np.asarray(self.stego_image)
        outcomes = {"unchanged": 0, "rejected": 0}
        for flips in [1] * 40 + [10] * 20 + [1000] * 20:
            damaged = pixels.copy()
            ys = rng.integers(0, damaged.shape[0], flips)
            xs = rng.integers(0, damaged.shape[1], flips)
            channels = rng.integers(0, 3, flips)
            damaged[ys, xs, channels] ^= 1
            try:
                recovered = stego.extract(to_bytes(Image.fromarray(damaged)))
            except stego.StegoError:
                outcomes["rejected"] += 1
            else:
                self.assertEqual(recovered, self.message)
                outcomes["unchanged"] += 1
        self.assertGreater(outcomes["rejected"], 0)

    def test_damaged_locked_message_is_rejected(self):
        # Same rule as the unlocked test above: undoing a change must be noticed, except a change
        # that only set one of the unused padding bits at the end of the header or of the message.
        locked = stego.embed(self.cover, self.message, password="tamper")
        before, after = to_array(self.cover), to_array(locked.image)
        positions = np.argwhere(before != after)
        rng = np.random.default_rng(7)
        unnoticed = 0
        for y, x, channel in positions[rng.choice(len(positions), size=8, replace=False)]:
            damaged = after.copy()
            damaged[y, x, channel] = before[y, x, channel]
            try:
                recovered = stego.extract(to_bytes(Image.fromarray(damaged.astype(np.uint8))), password="tamper")
            except stego.StegoError:
                continue
            self.assertEqual(recovered, self.message)
            unnoticed += 1
        self.assertLessEqual(unnoticed, 2)


@unittest.skipUnless(JPEG_READY, NEEDS_JPEG)
class JpegTests(ImageTestCase):
    """JPEG output uses a different method (DCT coefficients) and needs Member 1's helper program."""

    @classmethod
    def setUpClass(cls):
        cls.image = common.gradient_image(512, 384)
        cls.cover = to_bytes(cls.image, "JPEG", quality=95, subsampling=0)

    def test_round_trip(self):
        result = self.assert_round_trip(self.cover, "hidden in a JPEG", output_format="JPEG")
        self.assertEqual(result.media_type, "image/jpeg")
        self.assertTrue(result.image.startswith(b"\xff\xd8"))
        self.assertEqual(to_image(result.image).size, self.image.size)

    def test_round_trip_with_password(self):
        self.assert_round_trip(self.cover, bytes(range(64)), password="jpeg pass", output_format="JPEG")
        locked = stego.embed(self.cover, b"x", password="jpeg pass", output_format="JPEG")
        with self.assertRaises(stego.PasswordError):
            stego.extract(locked.image, password="wrong")

    def test_reported_capacity_is_exact(self):
        limit = stego.capacity(self.cover, "JPEG", encrypted=False).max_message_bytes
        self.assert_round_trip(self.cover, b"#" * limit, output_format="JPEG")
        with self.assertRaises(stego.CapacityError):
            stego.embed(self.cover, b"#" * (limit + 1), output_format="JPEG")

    def test_png_cover_can_produce_a_jpeg(self):
        result = self.assert_round_trip(to_bytes(self.image), "from a PNG cover", output_format="JPEG")
        self.assertTrue(result.jpeg_normalized)

    def test_message_survives_saving_the_jpeg_again(self):
        message = b"survives recompression"
        result = stego.embed(self.cover, message, output_format="JPEG")
        for quality in (95, 85, 75):
            with self.subTest(quality=quality):
                saved_again = to_bytes(to_image(result.image), "JPEG", quality=quality, subsampling=2)
                self.assertEqual(stego.extract(saved_again), message)

    def test_jpeg_holds_less_than_png(self):
        jpeg = stego.capacity(self.cover, "JPEG", encrypted=False).max_message_bytes
        png = stego.capacity(self.cover, "PNG", encrypted=False).max_message_bytes
        self.assertLess(jpeg, png)

    def test_clean_jpeg_has_no_message(self):
        with self.assertRaises(stego.PayloadError):
            stego.extract(self.cover)


if __name__ == "__main__":
    unittest.main()
