"""Tests for the mathematics and the collision search of the birthday experiment.

Run from the "Member 5" folder:
    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import random
import statistics
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import birthday_attack as birthday  # noqa: E402


class TheoryTests(unittest.TestCase):
    def test_classic_birthday_paradox(self):
        # 23 people are enough for a 50% chance of a shared birthday.
        self.assertAlmostEqual(birthday.collision_probability(23, 365), 0.5, delta=0.01)
        self.assertLess(birthday.collision_probability(22, 365), 0.5)

    def test_probability_goes_from_zero_to_one(self):
        self.assertEqual(birthday.collision_probability(1, 365), 0)
        self.assertGreater(birthday.collision_probability(100, 365), 0.999)
        chances = [birthday.collision_probability(k, 2 ** 32) for k in range(0, 300_000, 10_000)]
        self.assertEqual(chances, sorted(chances))

    def test_known_values_for_32_bits(self):
        self.assertAlmostEqual(birthday.tries_for_half(2 ** 32), 77_163, delta=1)
        self.assertAlmostEqual(birthday.expected_tries(2 ** 32), 82_138, delta=1)
        self.assertAlmostEqual(birthday.collision_probability(77_163, 2 ** 32), 0.5, delta=0.001)

    def test_work_grows_with_the_square_root(self):
        # Four times as many possible values only doubles the work.
        ratio = birthday.tries_for_half(2 ** 34) / birthday.tries_for_half(2 ** 32)
        self.assertAlmostEqual(ratio, 2, places=6)


class CollisionSearchTests(unittest.TestCase):
    def test_result_is_a_real_collision(self):
        rng = random.Random(1)
        for digest in (birthday.truncated_sha256(16), birthday.truncated_sha256(20), birthday.crc32):
            count, first, second = birthday.first_collision(digest, rng)
            self.assertNotEqual(first, second)
            self.assertEqual(digest(first), digest(second))
            self.assertGreaterEqual(count, 2)

    def test_truncated_digest_has_the_requested_size(self):
        rng = random.Random(2)
        for bits in (8, 12, 20):
            digest = birthday.truncated_sha256(bits)
            self.assertTrue(all(0 <= digest(rng.randbytes(16)) < 2 ** bits for _ in range(500)))

    def test_measured_tries_match_the_theory(self):
        rng = random.Random(3)
        for bits in (8, 12, 16):
            counts = birthday.measure(birthday.truncated_sha256(bits), 400, rng)
            expected = birthday.expected_tries(2 ** bits)
            self.assertAlmostEqual(statistics.mean(counts) / expected, 1, delta=0.1)

    def test_same_seed_gives_the_same_result(self):
        first = birthday.measure(birthday.truncated_sha256(12), 20, random.Random(4))
        second = birthday.measure(birthday.truncated_sha256(12), 20, random.Random(4))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
