"""
this file checks the classifier side of the authentication gate
it proves rejected windows stop before preprocessing and accepted payloads keep the same features
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

from puf_snn.auth.inference_gate import route_verified_window
from puf_snn.auth.window_message import build_authenticated_envelope
from puf_snn.auth.window_message import build_protected_message


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIRECTORY = REPOSITORY_ROOT / "src" / "python" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import train_baselines


def make_window() -> dict:
    samples = []

    for sample_index in range(120):
        samples.append(
            {
                "sample_index": sample_index,
                "capture_time_ns": sample_index * 16_666_667,
                "position_m": [sample_index * 0.0001, sample_index * 0.0002, 0.0],
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


def make_verification_result(protected_message: dict, result: str, reason: str) -> dict:
    return {
        "result": result,
        "reason": reason,
        "device_id": protected_message["device_id"],
        "session_id": protected_message["session_id"],
        "window_id": protected_message["window_id"],
        "sequence_number": protected_message["sequence_number"],
    }


class InferenceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.window = make_window()
        self.protected_message = build_protected_message(self.window)
        self.envelope = build_authenticated_envelope(self.protected_message, "week4-test-session-key-001", "00" * 32)

    def test_rejected_window_never_reaches_consumer(self) -> None:
        """a rejected verifier result stops before feature processing or inference"""
        consumer_calls = []

        def consumer(record: dict) -> str:
            consumer_calls.append(record)
            return "should-not-run"

        verification_result = make_verification_result(self.protected_message, "reject", "invalid_tag")
        outcome = route_verified_window(self.envelope, verification_result, consumer)

        self.assertFalse(outcome["forwarded"])
        self.assertEqual(outcome["reason"], "invalid_tag")
        self.assertEqual(consumer_calls, [])
        self.assertIsNone(outcome["consumer_result"])

    def test_accepted_window_keeps_identical_classifier_features(self) -> None:
        """canonical fixed-decimal transport does not change the conventional feature vector"""
        expected_features = train_baselines.record_to_features(self.window)
        verification_result = make_verification_result(self.protected_message, "accept", "accepted")
        outcome = route_verified_window(self.envelope, verification_result, train_baselines.record_to_features)

        self.assertTrue(outcome["forwarded"])
        np.testing.assert_allclose(outcome["consumer_result"], expected_features, atol=1e-8)

    def test_mismatched_verifier_result_is_rejected(self) -> None:
        """an acceptance for another window cannot unlock this payload"""
        verification_result = make_verification_result(self.protected_message, "accept", "accepted")
        verification_result["window_id"] = "different-window"

        with self.assertRaises(ValueError):
            route_verified_window(self.envelope, verification_result, train_baselines.record_to_features)

    def test_inconsistent_result_and_reason_is_rejected(self) -> None:
        """accept and reject decisions must use consistent reason values"""
        verification_result = make_verification_result(self.protected_message, "accept", "invalid_tag")

        with self.assertRaises(ValueError):
            route_verified_window(self.envelope, verification_result, train_baselines.record_to_features)


if __name__ == "__main__":
    unittest.main()
