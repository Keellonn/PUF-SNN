"""Exact-arithmetic and boundary controls; not latency/security experiments."""

from dataclasses import replace
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import random
import struct
import unittest
from unittest.mock import Mock, patch

from puf_snn.auth import binary_window as codec, verifier as verifier_module
from puf_snn.quality_dyadic import (
    REFERENCE_VALIDATE_QUALITY, UNIT, binary32_units,
    quality_validator_mode, validate_quality_dyadic,
)
from auth.support import offsets, setup, window, wrap, mutate


def decision(function, value):
    try:
        function(value)
        return "accept"
    except codec.ProtocolError as error:
        return error.reason


def replace_q(value, words, index=None):
    q = tuple(codec.F32(word) for word in words)
    return replace(value, samples=tuple(replace(sample, orientation_xyzw=q) if index is None or i == index else sample
                                        for i, sample in enumerate(value.samples)))


def rounded_word(value):
    return int.from_bytes(struct.pack(">f", value), "big")


class DyadicQualityTests(unittest.TestCase):
    def setUp(self):
        self.value = window(bytes(range(16)))

    def assert_equivalent(self, value, expected=None):
        reference = decision(REFERENCE_VALIDATE_QUALITY, value)
        self.assertEqual(decision(validate_quality_dyadic, value), reference)
        if expected is not None:
            self.assertEqual(reference, expected)

    def test_exact_scalars_cover_all_finite_exponents_signs_and_edges(self):
        for exponent in range(255):
            for mantissa in (0, 1, 0x3504f3, 0x7fffff):
                for sign in (0, 1):
                    word = (sign << 31) | (exponent << 23) | mantissa
                    with self.subTest(word=hex(word)):
                        self.assertEqual(Fraction(binary32_units(word), UNIT), codec.F32(word).rational())

    def test_nonfinite_and_invalid_word_types_are_rejected(self):
        for word in (True, False, -1, 1 << 32, 1.0, "0", 0x7f800000, 0xff800000, 0x7fc00000):
            with self.subTest(word=word), self.assertRaisesRegex(codec.ProtocolError, "invalid_payload_schema"):
                binary32_units(word)

    def test_positive_and_negative_zero_have_exact_zero_value(self):
        self.assertEqual(binary32_units(0), 0)
        self.assertEqual(binary32_units(0x80000000), 0)
        self.assert_equivalent(replace_q(self.value, (0x80000000, 0, 0, 0x3f800000)), "accept")

    def test_nominal_typed_window_accepts_without_mutation(self):
        before = self.value
        self.assert_equivalent(self.value, "accept")
        self.assertEqual(self.value, before)

    def test_duration_boundaries_match_exactly(self):
        for delta in (-121, -120, 0, 120, 121):
            self.assert_equivalent(replace(self.value, capture_end_ns=self.value.capture_end_ns+delta),
                                   "accept" if abs(delta) <= 120 else "data_quality_failure")

    def test_tracking_threshold_and_summary_checks_match(self):
        for count in (113, 114, 115, 119, 120):
            value = replace(self.value, tracking_valid_count=count, tracking_valid_fraction_ppm=codec.tracking_ppm(count),
                            samples=tuple(replace(sample, tracking_valid=i < count) for i, sample in enumerate(self.value.samples)))
            self.assert_equivalent(value, "accept" if count >= 114 else "data_quality_failure")
        self.assert_equivalent(replace(self.value, tracking_valid_count=119), "data_quality_failure")
        self.assert_equivalent(replace(self.value, tracking_valid_fraction_ppm=999999), "data_quality_failure")

    def test_timestamp_start_end_and_monotonicity_checks_match(self):
        for index, capture_time in ((0, self.value.capture_start_ns-1), (119, self.value.capture_end_ns),
                                    (1, self.value.samples[0].capture_time_ns), (1, self.value.samples[0].capture_time_ns-1)):
            samples = list(self.value.samples)
            samples[index] = replace(samples[index], capture_time_ns=capture_time)
            self.assert_equivalent(replace(self.value, samples=tuple(samples)), "data_quality_failure")

    def test_timestamp_gap_boundary_is_not_relaxed(self):
        for gap in (50_000_000, 50_000_001):
            # Isolate the gap from sample zero to one without a later reversal.
            samples = list(self.value.samples)
            samples[0] = replace(samples[0], capture_time_ns=self.value.capture_start_ns)
            samples[1:] = [replace(sample, capture_time_ns=self.value.capture_start_ns+gap+(i-1)*16_000_000)
                           for i, sample in enumerate(samples[1:], 1)]
            self.assert_equivalent(replace(self.value, samples=tuple(samples)),
                                   "accept" if gap == 50_000_000 else "data_quality_failure")

    def test_component_adjacent_binary32_boundary_words_match(self):
        for word, accepted in ((0x3f800008, True), (0x3f800009, False)):
            self.assert_equivalent(replace_q(self.value, (0, 0, 0, word)),
                                   "accept" if accepted else "data_quality_failure")
            self.assert_equivalent(replace_q(self.value, (0, 0, 0, word | 0x80000000)),
                                   "accept" if accepted else "data_quality_failure")

    def test_norm_lower_adjacent_binary32_boundary_words_match(self):
        for word, accepted in ((0x3f7ff973, True), (0x3f7ff972, False)):
            self.assert_equivalent(replace_q(self.value, (0, 0, 0, word)),
                                   "accept" if accepted else "data_quality_failure")

    def test_norm_upper_adjacent_binary32_boundary_words_match(self):
        for word, accepted in ((0x3c67b5e6, True), (0x3c67b5e7, False)):
            self.assert_equivalent(replace_q(self.value, (word, 0, 0, 0x3f800000)),
                                   "accept" if accepted else "data_quality_failure")

    def test_zero_norm_and_huge_finite_components_are_rejected(self):
        for words in ((0, 0, 0, 0), (0x7f7fffff, 0, 0, 0), (0, 0, 0, 0xff7fffff)):
            self.assert_equivalent(replace_q(self.value, words), "data_quality_failure")

    def test_negative_dot_and_exact_zero_dot_boundary_match(self):
        self.assert_equivalent(replace_q(self.value, (0, 0, 0, 0xbf800000), index=1), "data_quality_failure")
        self.assert_equivalent(replace_q(self.value, (0x3f800000, 0, 0, 0), index=1), "accept")
        # Dot with the adjacent identity quaternion is exactly -2**-149.
        self.assert_equivalent(replace_q(self.value, (0x3f800000, 0, 0, 0x80000001), index=1), "data_quality_failure")

    def test_fixed_randomized_finite_words_match_fraction_reference(self):
        rng = random.Random(8127)
        for _ in range(1000):
            word = rng.randrange(1 << 32)
            if (word >> 23) & 255 == 255:
                continue
            self.assertEqual(Fraction(binary32_units(word), UNIT), codec.F32(word).rational())

    def test_fixed_randomized_quaternions_match_quality_reference(self):
        rng = random.Random(8128)
        for _ in range(60):
            q = [rng.uniform(-1, 1) for _ in range(4)]
            magnitude = math.sqrt(sum(value*value for value in q))
            scale = rng.choice((.9998, .9999, 1.0, 1.0001, 1.0002))
            words = tuple(rounded_word(scale*value/magnitude) for value in q)
            self.assert_equivalent(replace_q(self.value, words))

    def test_wire_bytes_and_hmac_match_public_literal_vectors(self):
        root = Path(codec.__file__).resolve().parents[4]
        vectors = json.loads((root / "tests/auth/fixtures/binary-v2/vectors.json").read_text(encoding="utf-8"))
        key = bytes.fromhex(vectors["key_hex"])
        for vector in vectors["windows"]:
            encoded = bytes.fromhex(vector["expected_hex"])
            parsed = codec.parse_window(encoded)
            with quality_validator_mode("candidate_dyadic"):
                if vector["valid"]:
                    self.assertEqual(codec.encode_window(parsed), encoded)
                    self.assertEqual(hashlib.sha256(encoded).hexdigest(), vector["sha256"])
                    self.assertEqual(codec.window_tag(key, encoded).hex(), vector["hmac"])
                else:
                    with self.assertRaisesRegex(codec.ProtocolError, "data_quality_failure"):
                        codec.validate_quality(parsed)

    def test_parser_still_rejects_structural_negative_zero_and_nonfinite_words(self):
        encoded = codec.encode_window(self.value)
        location = offsets(encoded)["sample"] + 22
        with quality_validator_mode("candidate_dyadic"):
            for word in (0x80000000, 0x7f800000, 0x7fc00000):
                with self.assertRaisesRegex(codec.ProtocolError, "invalid_payload_schema"):
                    codec.parse_window(mutate(encoded, location, codec.U32(word)))

    def test_unknown_and_nested_modes_are_rejected_without_leaking_patches(self):
        with self.assertRaises(ValueError):
            with quality_validator_mode("unknown"):
                pass
        with quality_validator_mode("candidate_dyadic"):
            with self.assertRaises(RuntimeError):
                with quality_validator_mode("reference_fraction"):
                    pass
            self.assertIs(codec.validate_quality, validate_quality_dyadic)
        self.assertIs(codec.validate_quality, REFERENCE_VALIDATE_QUALITY)
        self.assertIs(verifier_module.validate_quality, REFERENCE_VALIDATE_QUALITY)

    def test_reference_mode_has_no_candidate_patch(self):
        with quality_validator_mode("reference_fraction"):
            self.assertIs(codec.validate_quality, REFERENCE_VALIDATE_QUALITY)
            self.assertIs(verifier_module.validate_quality, REFERENCE_VALIDATE_QUALITY)

    def test_exception_restores_both_quality_aliases(self):
        with self.assertRaisesRegex(RuntimeError, "controlled-error"):
            with quality_validator_mode("candidate_dyadic"):
                raise RuntimeError("controlled-error")
        self.assertIs(codec.validate_quality, REFERENCE_VALIDATE_QUALITY)
        self.assertIs(verifier_module.validate_quality, REFERENCE_VALIDATE_QUALITY)
        with quality_validator_mode("candidate_dyadic"):
            pass

    def test_mode_must_be_selected_before_timing_wrappers(self):
        with patch.object(verifier_module, "validate_quality", Mock(wraps=REFERENCE_VALIDATE_QUALITY)):
            with self.assertRaises(RuntimeError):
                with quality_validator_mode("candidate_dyadic"):
                    pass
        self.assertIs(codec.validate_quality, REFERENCE_VALIDATE_QUALITY)

    def test_only_quality_aliases_change_not_parser_hmac_or_verifier_method(self):
        before = (codec.parse_window, codec.parse_envelope, codec.window_tag, codec.encode_window,
                  verifier_module.Verifier.verify_window, verifier_module.Verifier.release_accepted)
        with quality_validator_mode("candidate_dyadic"):
            after = (codec.parse_window, codec.parse_envelope, codec.window_tag, codec.encode_window,
                     verifier_module.Verifier.verify_window, verifier_module.Verifier.release_accepted)
            self.assertEqual(before, after)

    def test_bad_tag_still_returns_before_quality_and_release(self):
        verifier, sid, key = setup()
        encoded = codec.encode_window(window(sid))
        before = verifier.session_status(sid)
        with quality_validator_mode("candidate_dyadic"):
            with patch.object(verifier_module, "validate_quality", Mock(wraps=validate_quality_dyadic)) as quality:
                result = verifier.verify_window(wrap(encoded, sid, key, tag=bytes(32)))
                self.assertEqual(result.reason, "invalid_tag")
                quality.assert_not_called()
                with self.assertRaises(ValueError):
                    verifier.release_accepted(result, Mock())
        self.assertEqual(verifier.session_status(sid), before)

    def test_sender_envelope_quality_failure_remains_before_hmac(self):
        encoded = codec.encode_window(self.value)
        invalid = mutate(encoded, offsets(encoded)["ppm"], codec.U32(999999))
        with quality_validator_mode("candidate_dyadic"):
            with patch.object(codec, "window_tag", Mock(wraps=codec.window_tag)) as tag:
                with self.assertRaisesRegex(codec.ProtocolError, "data_quality_failure"):
                    codec.encode_envelope(invalid, bytes(range(32)))
                tag.assert_not_called()

    def test_existing_authenticated_quality_regressions_also_pass_in_candidate_mode(self):
        from auth.test_quality import QualityTests
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(QualityTests)
        count = suite.countTestCases()
        result = unittest.TestResult()
        with quality_validator_mode("candidate_dyadic"):
            suite.run(result)
        self.assertEqual(result.testsRun, count)
        self.assertGreaterEqual(count, 20)
        self.assertTrue(result.wasSuccessful(), f"Original quality regressions failed: {result.errors!r} {result.failures!r}")

    def test_receiver_controls_preserve_state_release_and_recovery_in_both_modes(self):
        for mode in ("reference_fraction", "candidate_dyadic"):
            verifier, sid, key = setup()
            consumer = Mock(return_value="fixture-only-output")
            with quality_validator_mode(mode):
                good = codec.encode_window(window(sid))
                result = verifier.verify_window(wrap(good, sid, key))
                self.assertEqual(result.reason, "accepted")
                verifier.release_accepted(result, consumer)
                before = verifier.session_status(sid)
                expected = codec.encode_window(window(sid, seq=1))
                location = offsets(expected)
                invalid_quality = mutate(expected, location["ppm"], codec.U32(999999))
                future = codec.encode_window(window(sid, seq=2))
                for packet, reason in ((wrap(invalid_quality, sid, key), "data_quality_failure"),
                                       (wrap(expected, sid, key, tag=bytes(32)), "invalid_tag"),
                                       (wrap(good, sid, key), "duplicate_sequence"),
                                       (wrap(future, sid, key), "future_sequence_gap"),
                                       (b"{", "malformed_message")):
                    refused = verifier.verify_window(packet)
                    self.assertEqual(refused.reason, reason)
                    self.assertEqual(verifier.session_status(sid), before)
                    with self.assertRaises(ValueError):
                        verifier.release_accepted(refused, consumer)
                    self.assertEqual(consumer.call_count, 1)
                continuation = verifier.verify_window(wrap(expected, sid, key))
                self.assertEqual(continuation.reason, "accepted")
                verifier.release_accepted(continuation, consumer)
                self.assertEqual(consumer.call_count, 2)
                self.assertEqual(verifier.session_status(sid).accepted_count, 2)
                self.assertFalse(verifier.incomplete)


if __name__ == "__main__":
    unittest.main()
