"""
this file records the Python side of the shared cross-language golden vector
the key is public test material and must never be reused as a real session key
"""

from __future__ import annotations

import hashlib
import hmac
import unittest

from puf_snn.auth.window_message import build_protected_message
from puf_snn.auth.window_message import canonicalize_protected_message


TEST_SESSION_KEY = bytes.fromhex("11" * 32)
EXPECTED_BYTE_COUNT = 24_308
EXPECTED_SHA256 = "87c89fca1426ed031788192fbcee551e91036f5d72301da4a7d5137f63bfdf2d"
EXPECTED_HMAC_SHA256 = "b8ae3c52deefcb0432334388671bf82f8fec41b1a2f7edb016f5012301a882e1"


def make_golden_window() -> dict:
    samples = []
    start_time_ns = 1_000_000_000

    for sample_index in range(120):
        position = [0.0, 0.0, 0.0]

        if sample_index == 0:
            position = [0.125, -0.25, 0.0]

        samples.append(
            {
                "sample_index": sample_index,
                "capture_time_ns": start_time_ns + sample_index * 16_666_667,
                "position_m": position,
                "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
                "tracking_valid": True,
            }
        )

    return {
        "schema_version": "0.2",
        "window_id": "quest-02-session-01-nod-000-window-000",
        "device_id": "quest-02",
        "session_id": "quest-02-session-01",
        "sequence_number": 0,
        "coordinate_frame": "unity_device_origin",
        "target_sample_rate_hz": 60,
        "window_start_ns": start_time_ns,
        "window_end_ns": 3_000_000_000,
        "samples": samples,
    }


class GoldenWindowMessageTests(unittest.TestCase):
    def test_python_canonical_bytes_match_shared_golden_vector(self) -> None:
        """Python produces the fixed byte count, SHA-256, and test-only HMAC"""
        protected_message = build_protected_message(make_golden_window())
        canonical_bytes = canonicalize_protected_message(protected_message)
        sha256 = hashlib.sha256(canonical_bytes).hexdigest()
        tag_hex = hmac.new(TEST_SESSION_KEY, canonical_bytes, hashlib.sha256).hexdigest()

        self.assertEqual(len(canonical_bytes), EXPECTED_BYTE_COUNT)
        self.assertEqual(sha256, EXPECTED_SHA256)
        self.assertEqual(tag_hex, EXPECTED_HMAC_SHA256)


if __name__ == "__main__":
    unittest.main()
