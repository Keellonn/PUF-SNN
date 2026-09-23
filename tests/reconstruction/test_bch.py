import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/python"))
sys.path.insert(0, str(ROOT / "tests"))

from puf_snn.reconstruction import BCH_PARAMETERS, BCHCodec
from puf_snn.reconstruction import bch
from reconstruction.reference import bits, construct_generator, encode, remainder


class BCHTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec = BCHCodec()
        cls.codec.initialize()
        cls.fixtures = json.loads((Path(__file__).parent / "fixtures/bch63_vectors.json").read_text())

    def test_exact_parameters(self):
        p = self.codec.parameters
        self.assertEqual((self.codec.n, self.codec.k, self.codec.t), (63, 36, 5))
        self.assertEqual((p.designed_distance, p.field_order), (11, 64))
        self.assertEqual((p.primitive_polynomial, p.primitive_element), (0x43, 2))
        self.assertEqual((p.first_root_exponent, p.generator_polynomial), (1, 0x86E8113))
        self.assertTrue(p.systematic)
        self.assertEqual((p.backend, p.backend_version), ("galois", "0.4.11"))
        self.assertEqual((p.bit_order, p.coefficient_order), ("msb-first", "highest-degree-first"))

    def test_independent_generator_from_roots(self):
        generator, cosets = construct_generator()
        self.assertEqual(cosets, [[1, 2, 4, 8, 16, 32], [3, 6, 12, 24, 48, 33],
                                 [5, 10, 20, 40, 17, 34], [7, 14, 28, 56, 49, 35],
                                 [9, 18, 36]])
        self.assertEqual(generator.bit_length() - 1, 27)
        self.assertEqual(generator, BCH_PARAMETERS.generator_polynomial)
        self.assertEqual(remainder((1 << 63) | 1, generator), 0)

    def test_all_message_basis_vectors_against_independent_encoder(self):
        for position in range(36):
            with self.subTest(position=position):
                message = bits(1 << position, 36)
                actual = self.codec.encode(message)
                self.assertEqual(actual, bits(encode(1 << position), 63))
                self.assertEqual(actual[:36], message)

    def test_checkpoint_vectors_and_leading_zeros(self):
        for row in self.fixtures["vectors"]:
            with self.subTest(credential=row["credential_hex"]):
                message_integer = int(row["credential_hex"], 16) << 4
                expected_integer = int(row["packed_codeword_hex"], 16) >> 1
                self.assertEqual(encode(message_integer), expected_integer)
                encoded = self.codec.encode(bits(message_integer, 36))
                self.assertEqual(encoded, bits(expected_integer, 63))
                result = self.codec.decode(encoded)
                self.assertEqual(result.candidate_message, bits(message_integer, 36))
                self.assertEqual(result.corrected_codeword, encoded)
                self.assertEqual(result.reported_correction_count, 0)

    def test_adapter_does_not_impose_credential_padding(self):
        message = (1,) * 36
        encoded = self.codec.encode(message)
        self.assertEqual(len(encoded), 63)
        self.assertEqual(self.codec.decode(encoded).candidate_message, message)

    def test_invalid_messages_rejected_before_backend(self):
        invalid = [None, [0] * 36, (0,) * 32, (0,) * 35, (0,) * 37, "0" * 36]
        invalid += [(0,) * 35 + (value,) for value in (-1, 2, True, 0.0, "1", np.int64(1))]
        with patch.object(bch, "_backend", side_effect=AssertionError("backend called")):
            for message in invalid:
                with self.subTest(message=message), self.assertRaises(ValueError):
                    self.codec.encode(message)

    def test_invalid_received_words_rejected_before_backend(self):
        invalid = [None, [0] * 63, (0,) * 59, (0,) * 62, (0,) * 64, "0" * 63]
        invalid += [(0,) * 62 + (value,) for value in (-1, 2, False, 1.0, "0")]
        with patch.object(bch, "_backend", side_effect=AssertionError("backend called")):
            for received in invalid:
                with self.subTest(received=received), self.assertRaises(ValueError):
                    self.codec.decode(received)

    def test_declared_failure_discards_backend_payload(self):
        with patch.object(bch, "_backend") as backend:
            backend.return_value.decode.return_value = (object(), -1)
            result = self.codec.decode((0,) * 63)
        self.assertEqual(result.status, "uncorrectable")
        self.assertEqual(result.reported_correction_count, -1)
        self.assertIsNone(result.candidate_message)
        self.assertIsNone(result.corrected_codeword)
        self.assertEqual(result.failure_reason, "decoder_declared_failure")

    def test_impossible_correction_counts_raise(self):
        for count in (-2, 6, 0.0, True, None):
            with self.subTest(count=count), patch.object(bch, "_backend") as backend:
                backend.return_value.decode.return_value = (np.zeros(63, dtype=int), count)
                with self.assertRaises(RuntimeError):
                    self.codec.decode((0,) * 63)

    def test_nonbinary_or_misshaped_backend_output_raises(self):
        for output in (np.zeros(62, dtype=int), np.zeros((1, 63), dtype=int),
                       np.zeros(63, dtype=float), np.full(63, 2, dtype=int)):
            with self.subTest(shape=output.shape), patch.object(bch, "_backend") as backend:
                backend.return_value.decode.return_value = (output, 0)
                with self.assertRaises(RuntimeError):
                    self.codec.decode((0,) * 63)

    def test_backend_must_return_a_codeword_at_reported_distance(self):
        for word, count in ((np.array((0,) * 62 + (1,)), 1),
                            (np.zeros(63, dtype=int), 1)):
            with self.subTest(count=count), patch.object(bch, "_backend") as backend:
                backend.return_value.decode.return_value = (word, count)
                with self.assertRaises(RuntimeError):
                    self.codec.decode((0,) * 63)

    def test_encoder_must_preserve_message_and_return_valid_codeword(self):
        with patch.object(bch, "_backend") as backend:
            backend.return_value.encode.return_value = np.zeros(63, dtype=int)
            with self.assertRaises(RuntimeError):
                self.codec.encode((1,) * 36)
            backend.return_value.encode.return_value = np.array((0,) * 62 + (1,))
            with self.assertRaises(RuntimeError):
                self.codec.encode((0,) * 36)

    def test_unexpected_backend_exceptions_propagate(self):
        with patch.object(bch, "_backend") as backend:
            backend.return_value.decode.side_effect = OSError("backend malfunction")
            backend.return_value.encode.side_effect = OSError("backend malfunction")
            with self.assertRaisesRegex(OSError, "backend malfunction"):
                self.codec.decode((0,) * 63)
            with self.assertRaisesRegex(OSError, "backend malfunction"):
                self.codec.encode((0,) * 36)

    def test_wrong_backend_version_refused(self):
        with patch.object(bch, "version", return_value="0.4.10"):
            with self.assertRaisesRegex(RuntimeError, "requires galois==0.4.11"):
                bch._backend.__wrapped__()

    def test_changed_backend_parameters_refused(self):
        wrong = SimpleNamespace(n=62, k=36, t=5, d=11, alpha=2, c=1,
                                generator_poly=0x86E8113, is_systematic=True,
                                is_primitive=True, is_narrow_sense=True)
        with patch.object(bch.galois, "BCH", return_value=wrong):
            with self.assertRaisesRegex(RuntimeError, "frozen codec"):
                bch._backend.__wrapped__()


if __name__ == "__main__":
    unittest.main()
