from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "python"))

from puf_snn.puf.metrics import (
    hamming_distance, normalized_hamming_distance, pairwise_uniqueness,
    raw_ber, reliability, uniformity, uniqueness,
)

class MetricTests(unittest.TestCase):
    def test_hand_calculated_read(self) -> None:
        reference = [int(bit) for bit in "11010100"]
        reading = [int(bit) for bit in "11000110"]
        self.assertEqual(hamming_distance(reference, reading), 2)
        self.assertEqual(normalized_hamming_distance(reference, reading), 0.25)
        self.assertEqual(raw_ber(reference, reading), 0.25)
        self.assertEqual(reliability(reference, reading), 0.75)
        self.assertEqual(uniformity([1, 0, 1, 0]), 0.5)

    def test_boundaries(self) -> None:
        self.assertEqual(raw_ber([0, 1], [0, 1]), 0)
        self.assertEqual(reliability([0, 1], [1, 0]), 0)
        self.assertEqual(uniformity([0, 0]), 0)
        self.assertEqual(uniformity([1, 1]), 1)

    def test_unique_pairs_and_duplicate_patterns(self) -> None:
        references = [[0, 0], [0, 1], [1, 1]]
        self.assertEqual(pairwise_uniqueness(references),
                         [(0, 1, 0.5), (0, 2, 1.0), (1, 2, 0.5)])
        self.assertAlmostEqual(uniqueness(references), 2 / 3)
        self.assertEqual(pairwise_uniqueness([[0], [0]]), [(0, 1, 0)])

    def test_invalid_responses(self) -> None:
        for response in ([], [2], [-1], [0.5], [float("nan")],
                         "01", [[0]], None):
            with self.subTest(response=response):
                with self.assertRaises(ValueError):
                    uniformity(response)
                for function in (hamming_distance, normalized_hamming_distance,
                                 raw_ber, reliability):
                    with self.assertRaises(ValueError):
                        function(response, [0])
                    with self.assertRaises(ValueError):
                        function([0], response)
        for function in (hamming_distance, raw_ber, reliability):
            with self.assertRaises(ValueError):
                function([0], [0, 1])
        for responses in ([], [[0]], [[0], [1, 0]], [[0], [2]]):
            with self.assertRaises(ValueError):
                uniqueness(responses)
