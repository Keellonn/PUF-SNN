"""This file checks that one verifier-accepted window reaches the SNN input once."""

from __future__ import annotations

import sys
import unittest

from pathlib import Path

from puf_snn.auth.config import AuthConfig
from puf_snn.integration import ExactlyOnceClassifierRelease, processed_record_to_wire_window
from puf_snn.snn.dataset import record_to_sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIRECTORY = REPOSITORY_ROOT / "src" / "python" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from run_layer3_demo import establish, initialize_material


def processed_window() -> dict:
    return {
        "schema_version": "0.2",
        "window_id": "snn-integration-window-000",
        "window_start_ns": 1_000_000_000,
        "window_end_ns": 3_000_000_000,
        "samples": [
            {
                "sample_index": sample_index,
                "capture_time_ns": 1_000_000_000 + sample_index * 16_666_667,
                "position_m": [sample_index / 1000.0, 0.0, 0.1],
                "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
                "tracking_valid": True,
            }
            for sample_index in range(120)
        ],
    }


class SnnIntegrationTests(unittest.TestCase):
    # only the immutable verifier-accepted payload becomes a 120 by 7 SNN sequence
    def test_accepted_window_reaches_snn_input_once(self) -> None:
        sender, verifier, _ = establish(AuthConfig(), initialize_material())
        received_shapes = []

        def classifier(sequence):
            received_shapes.append(sequence.shape)
            return "classified"

        gate = ExactlyOnceClassifierRelease(verifier, record_to_sequence, classifier)
        packet = sender.seal_window(processed_record_to_wire_window(processed_window()))
        accepted = verifier.verify_window(packet)

        self.assertEqual(gate.deliver(accepted), "classified")
        self.assertEqual(received_shapes, [(120, 7)])

        with self.assertRaisesRegex(ValueError, "already delivered"):
            gate.deliver(accepted)

        self.assertEqual(received_shapes, [(120, 7)])


if __name__ == "__main__":
    unittest.main()
