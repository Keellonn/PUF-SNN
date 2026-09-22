"""
this file checks the shared authenticated-window message contract
it verifies deterministic serialization and proves that changing any protected section changes the HMAC input
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import unittest

from puf_snn.auth.window_message import build_authenticated_envelope
from puf_snn.auth.window_message import build_protected_message
from puf_snn.auth.window_message import canonicalize_protected_message


TEST_SESSION_KEY = bytes.fromhex("11" * 32)


def make_window() -> dict:
    samples = []

    for sample_index in range(120):
        samples.append(
            {
                "sample_index": sample_index,
                "capture_time_ns": sample_index * 16_666_667,
                "position_m": [sample_index * 0.0001, 0.0, -0.0],
                "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
                "tracking_valid": True,
            }
        )

    return {
        "schema_version": "0.2",
        "window_id": "sim-device-01-session-01-nod-001-window-000",
        "device_id": "sim-device-01",
        "session_id": "sim-device-01-session-01",
        "sequence_number": 0,
        "coordinate_frame": "unity_device_origin",
        "target_sample_rate_hz": 60,
        "window_start_ns": 0,
        "window_end_ns": 2_000_000_040,
        "samples": samples,
    }


def compute_test_tag(protected_message: dict) -> str:
    message_bytes = canonicalize_protected_message(protected_message)
    return hmac.new(TEST_SESSION_KEY, message_bytes, hashlib.sha256).hexdigest()


class WindowMessageTests(unittest.TestCase):
    def test_builder_creates_expected_versioned_message(self) -> None:
        """the builder includes the required protected metadata, quality, and payload"""
        protected_message = build_protected_message(make_window())

        self.assertEqual(protected_message["protocol_version"], "1.0")
        self.assertEqual(protected_message["message_schema_version"], "1.0")
        self.assertEqual(protected_message["payload_schema_version"], "0.2")
        self.assertEqual(protected_message["data_quality"]["tracking_valid_count"], 120)
        self.assertEqual(protected_message["data_quality"]["tracking_valid_fraction_ppm"], 1_000_000)
        self.assertEqual(len(protected_message["payload"]["samples"]), 120)

    def test_motion_values_use_fixed_eight_decimal_strings(self) -> None:
        """motion values have one language-independent decimal representation"""
        protected_message = build_protected_message(make_window())
        first_sample = protected_message["payload"]["samples"][0]
        second_sample = protected_message["payload"]["samples"][1]

        self.assertEqual(first_sample["position_m"], ["0.00000000", "0.00000000", "0.00000000"])
        self.assertEqual(second_sample["position_m"][0], "0.00010000")
        self.assertEqual(first_sample["orientation_xyzw"][3], "1.00000000")

    def test_canonical_bytes_are_deterministic(self) -> None:
        """equivalent protected objects always produce the same compact UTF-8 bytes"""
        first_message = build_protected_message(make_window())
        second_message = copy.deepcopy(first_message)
        second_message = dict(reversed(list(second_message.items())))

        first_bytes = canonicalize_protected_message(first_message)
        second_bytes = canonicalize_protected_message(second_message)

        self.assertEqual(first_bytes, second_bytes)
        self.assertNotIn(b" ", first_bytes)
        self.assertNotIn(b"\n", first_bytes)

    def test_each_protected_section_changes_the_tag(self) -> None:
        """changing protected metadata, quality, or motion data invalidates the original tag"""
        original_message = build_protected_message(make_window())
        original_tag = compute_test_tag(original_message)

        mutations = {
            "protocol_version": lambda message: message.__setitem__("protocol_version", "1.1"),
            "message_schema_version": lambda message: message.__setitem__("message_schema_version", "1.1"),
            "payload_schema_version": lambda message: message.__setitem__("payload_schema_version", "0.3"),
            "device_id": lambda message: message.__setitem__("device_id", "sim-device-02"),
            "session_id": lambda message: message.__setitem__("session_id", "different-session"),
            "window_id": lambda message: message.__setitem__("window_id", "different-window"),
            "sequence_number": lambda message: message.__setitem__("sequence_number", 1),
            "capture_start_ns": lambda message: message.__setitem__("capture_start_ns", 1),
            "capture_end_ns": lambda message: message.__setitem__("capture_end_ns", 2_000_000_041),
            "payload_encoding": lambda message: message.__setitem__("payload_encoding", "different-encoding"),
            "data_quality": lambda message: message["data_quality"].__setitem__("tracking_valid_count", 119),
            "position": lambda message: message["payload"]["samples"][0]["position_m"].__setitem__(0, "0.00000001"),
            "orientation": lambda message: message["payload"]["samples"][0]["orientation_xyzw"].__setitem__(3, "0.99999999"),
            "tracking": lambda message: message["payload"]["samples"][0].__setitem__("tracking_valid", False),
        }

        for mutation_name, mutation in mutations.items():
            with self.subTest(mutation=mutation_name):
                altered_message = copy.deepcopy(original_message)
                mutation(altered_message)
                altered_tag = compute_test_tag(altered_message)
                self.assertFalse(hmac.compare_digest(original_tag, altered_tag))

    def test_builder_accepts_exactly_114_tracking_valid_samples(self) -> None:
        """the protected message accepts the existing 95 percent quality boundary"""
        window = make_window()

        for sample in window["samples"][:6]:
            sample["tracking_valid"] = False

        protected_message = build_protected_message(window)

        self.assertEqual(protected_message["data_quality"]["tracking_valid_count"], 114)
        self.assertEqual(protected_message["data_quality"]["tracking_valid_fraction_ppm"], 950_000)

    def test_builder_rejects_bad_input_before_authentication(self) -> None:
        """short, low-quality, and nonfinite windows cannot enter the authentication layer"""
        short_window = make_window()
        short_window["samples"].pop()

        with self.assertRaises(ValueError):
            build_protected_message(short_window)

        low_tracking_window = make_window()

        for sample in low_tracking_window["samples"][:7]:
            sample["tracking_valid"] = False

        with self.assertRaises(ValueError):
            build_protected_message(low_tracking_window)

        nonfinite_window = make_window()
        nonfinite_window["samples"][0]["position_m"][0] = float("nan")

        with self.assertRaises(ValueError):
            build_protected_message(nonfinite_window)

    def test_envelope_keeps_tag_outside_the_protected_object(self) -> None:
        """the final envelope separates protected sender data from authentication output"""
        protected_message = build_protected_message(make_window())
        tag_hex = compute_test_tag(protected_message)
        envelope = build_authenticated_envelope(protected_message, "session-key-001", tag_hex)

        self.assertEqual(envelope["protected"], protected_message)
        self.assertEqual(envelope["authentication"]["algorithm"], "HMAC-SHA-256")
        self.assertEqual(envelope["authentication"]["tag_hex"], tag_hex)


if __name__ == "__main__":
    unittest.main()
