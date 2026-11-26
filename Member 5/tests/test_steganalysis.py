"""Tests of the detection experiment in steganalysis.py.

A detector that is wrong would make the detection results meaningless, so each one is
checked on cases with a known answer: clean photos, and photos where a known share of
colour values was given a random last bit. The other tests cover the AUC and 5% metrics,
the three hiding methods, the black-and-white and known-gallery-cover checks, and the
text scanner.

Run from the "Member 5" folder:
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import steganalysis as sa  # noqa: E402
    TILES = sa.photo_tiles()
except ImportError as error:  # scipy or scikit-image not installed
    raise unittest.SkipTest(f"steganalysis needs scipy and scikit-image: {error}")

PHOTOS = ("rocket-00", "coffee-00", "brick-00", "astronaut-00")


class MetricTests(unittest.TestCase):
    def test_auc(self):
        self.assertEqual(sa.auc([0, 1], [2, 3]), 1.0)
        self.assertEqual(sa.auc([2, 3], [0, 1]), 0.0)
        self.assertEqual(sa.auc([1, 1], [1, 1]), 0.5)
        self.assertEqual(sa.auc([0, 2], [1, 3]), 0.75)

    def test_caught_at_5_percent(self):
        clean = list(range(100))
        self.assertEqual(sa.caught_at_5_percent(clean, [200] * 10), 1.0)
        self.assertEqual(sa.caught_at_5_percent(clean, [50] * 10), 0.0)


class DetectorTests(unittest.TestCase):
    def test_spa_and_rs_read_close_to_zero_on_clean_photos(self):
        for name in PHOTOS:
            with self.subTest(photo=name):
                self.assertLess(abs(sa.spa_estimate(TILES[name])), 0.05)
                self.assertLess(abs(sa.rs_estimate(TILES[name])), 0.05)

    def test_spa_and_rs_estimate_the_hidden_share(self):
        rng = np.random.default_rng(1)
        for name in PHOTOS:
            for share in (0.1, 0.25, 0.5):
                stego = sa.random_lsb(TILES[name], int(share * TILES[name].size), rng)
                with self.subTest(photo=name, share=share):
                    self.assertAlmostEqual(sa.spa_estimate(stego), share, delta=0.06)
                    self.assertAlmostEqual(sa.rs_estimate(stego), share, delta=0.06)

    def test_chi_square_flags_a_fully_used_picture(self):
        rng = np.random.default_rng(2)
        photo = TILES["rocket-00"]
        full = sa.random_lsb(photo, photo.size, rng)
        self.assertGreater(sa.chi_square_p(full), 0.9)
        self.assertLess(sa.chi_square_p(photo), 0.05)

    def test_chi_square_scan_finds_sequential_lsb_but_not_scattered_changes(self):
        rng = np.random.default_rng(3)
        photo = TILES["rocket-00"]
        self.assertLess(sa.chi_square_scan_score(photo), 0.05)
        self.assertGreater(sa.chi_square_scan_score(sa.hide(sa.SEQUENTIAL, photo, 0.2, rng)), 0.9)
        self.assertLess(sa.chi_square_scan_score(sa.hide(sa.RANDOM, photo, 0.2, rng)), 0.05)
        self.assertLess(sa.chi_square_scan_score(sa.hide(sa.TEAM, photo, 0.2, rng)), 0.05)


class HidingMethodTests(unittest.TestCase):
    def test_all_methods_hide_the_same_message_size(self):
        rng = np.random.default_rng(4)
        photo = TILES["coffee-00"]
        size = sa.message_bytes(photo, 0.1)
        bits = size * 8
        for method in sa.METHODS:
            with self.subTest(method=method):
                stego = sa.hide(method, photo, 0.1, rng)
                self.assertEqual(stego.shape, photo.shape)
                self.assertLessEqual(int(np.abs(stego.astype(int) - photo.astype(int)).max()), 1)
                changed = np.flatnonzero(stego.reshape(-1) != photo.reshape(-1))
                if method == sa.TEAM:
                    recovered = sa.image_stego.extract(sa.to_bytes(sa.common.Image.fromarray(stego)))
                    self.assertEqual(len(recovered), size)
                else:
                    # A random bit replaces the old last bit, so about half of the bits change a value.
                    self.assertGreater(changed.size, 0.45 * bits)
                    self.assertLess(changed.size, 0.55 * bits)
                    if method == sa.SEQUENTIAL:
                        self.assertLess(changed.max(), bits)
                        self.assertGreaterEqual(changed.max(), bits - 64)

    def test_team_method_changes_fewer_values_than_lsb(self):
        # Matrix embedding: about 3.4 bits per changed value, against 2 for LSB.
        rng = np.random.default_rng(5)
        photo = TILES["coffee-00"]
        team = np.mean(sa.hide(sa.TEAM, photo, 0.2, rng) != photo)
        lsb = np.mean(sa.hide(sa.RANDOM, photo, 0.2, rng) != photo)
        self.assertLess(team, lsb * 0.65)
        self.assertGreater(team, lsb * 0.5)


class GreyscaleCoverTests(unittest.TestCase):
    def test_black_and_white_upload_stays_black_and_white(self):
        # Issue 5 (fixed in Member 1): a greyscale upload used to come back as a colour picture whose
        # three channels differed, which gave the message away. It now stays a greyscale ("L") file.
        rows = sa.grey_cover_check({name: TILES[name] for name in ("camera-00", "moon-00")}, np.random.default_rng(8))
        self.assertEqual(len(rows), 2)
        self.assertFalse(any(row["channels_differ_after_10_byte_message"] for row in rows))
        self.assertEqual({row["stego_mode"] for row in rows}, {"L"})


class KnownCoverTests(unittest.TestCase):
    def test_comparing_with_the_public_gallery_picture_finds_every_message(self):
        rows = sa.known_cover_check(np.random.default_rng(6))
        if not rows:
            self.skipTest("Member 3's gallery pictures are not in the repository")
        self.assertTrue(all(row["detected"] for row in rows))
        self.assertFalse(any(row["false_alarm"] for row in rows))


class TextDetectionTests(unittest.TestCase):
    def test_scanner_flags_every_stego_text_and_no_clean_text(self):
        rows = sa.text_detection()
        self.assertTrue(all(row["flagged"] for row in rows if row["kind"] == "stego"))
        self.assertFalse(any(row["flagged"] for row in rows if row["kind"] == "clean"))
        self.assertGreaterEqual(sum(row["kind"] == "stego" for row in rows), 6)


if __name__ == "__main__":
    unittest.main()
