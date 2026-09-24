"""Shared processed-window to authenticated classifier boundary tests."""

from dataclasses import replace
import json
from pathlib import Path
import struct
import sys
import unittest

import numpy as np

from puf_snn.auth.binary_window import F32, encode_window, parse_envelope, tracking_ppm, window_tag
from puf_snn.auth.config import AuthConfig
from puf_snn.integration import (
    ExactlyOnceClassifierRelease,
    processed_record_to_wire_window,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/python/scripts"))
from run_layer3_demo import establish, initialize_material
import train_baselines


def processed_window(tracking_count=120):
    return {
        "schema_version": "0.2",
        "window_id": "keegan-processed-window-000",
        "source_trial_id": "keegan-source-trial",
        "device_id": "dataset-device-must-not-bind",
        "session_id": "dataset-session-must-not-bind",
        "sequence_number": 987,
        "trial_id": "keegan-source-trial",
        "split": "test",
        "label": "nod",
        "coordinate_frame": "unity_device_origin",
        "target_sample_rate_hz": 60,
        "window_start_ns": 1_000_000_000,
        "window_end_ns": 3_000_000_000,
        "samples": [
            {
                "sample_index": index,
                "capture_time_ns": 1_000_000_000 + index * 16_666_667,
                "position_m": [index / 1000, -0.0, 0.1],
                "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
                "tracking_valid": index < tracking_count,
            }
            for index in range(120)
        ],
    }


def envelope_with(data, original, *, key=None, key_id=None, tag=None):
    obj = json.loads(original)
    obj["protected"]["bytes_b64"] = __import__("base64").b64encode(data).decode("ascii")
    if key_id is not None:
        obj["authentication"]["key_id"] = key_id
    if tag is not None:
        obj["authentication"]["tag_hex"] = tag.hex()
    elif key is not None:
        obj["authentication"]["tag_hex"] = window_tag(key, data).hex()
    return json.dumps(obj, separators=(",", ":")).encode("utf-8")


class AdapterTests(unittest.TestCase):
    def test_processed_record_rounds_once_and_leaves_binding_to_sender(self):
        source = processed_window()
        window = processed_record_to_wire_window(source)
        self.assertEqual(window.device_id, "unbound")
        self.assertEqual(window.session_id, bytes(16))
        self.assertEqual(window.sequence_number, 0)
        self.assertEqual(window.samples[0].position_m[1], F32(0))
        self.assertEqual(window.samples[0].position_m[2].bits, 0x3DCCCCCD)
        self.assertEqual((window.tracking_valid_count, window.tracking_valid_fraction_ppm), (120, 1_000_000))

    def test_numeric_policy_rejects_invalid_values(self):
        for value in (True, "0.1", float("nan"), float("inf"), -float("inf"), 1e100):
            with self.subTest(value=value):
                source = processed_window()
                source["samples"][0]["position_m"][0] = value
                with self.assertRaises(ValueError):
                    processed_record_to_wire_window(source)

    def test_classifier_record_matches_current_120_by_7_preprocessing(self):
        sender, verifier, _ = establish(AuthConfig(), initialize_material())
        records = []

        def preprocess(record):
            records.append(record)
            return train_baselines.record_to_features(record)

        gate = ExactlyOnceClassifierRelease(verifier, preprocess, lambda features: features)
        result = verifier.verify_window(
            sender.seal_window(processed_record_to_wire_window(processed_window()))
        )
        features = gate.deliver(result)
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertNotIn("label", record)
        self.assertNotIn("split", record)
        self.assertEqual(features.shape, (840,))
        self.assertEqual(features.reshape(120, 7).shape, (120, 7))


class SharedEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.material = initialize_material()

    def setup_path(self):
        sender, verifier, _ = establish(AuthConfig(), self.material)
        calls = []
        records = []

        def preprocess(record):
            records.append(record)
            return train_baselines.record_to_features(record)

        def classifier(features):
            calls.append(np.array(features, copy=True))
            return "classified"

        gate = ExactlyOnceClassifierRelease(verifier, preprocess, classifier)
        return sender, verifier, gate, calls, records

    def reject_without_delivery(self, verifier, gate, calls, packet, reason):
        sid = verifier.active_session_ids[0]
        before = verifier.session_status(sid)
        result = verifier.verify_window(packet)
        self.assertEqual(result.reason, reason)
        with self.assertRaises(ValueError):
            gate.deliver(result)
        self.assertEqual(calls, [])
        self.assertEqual(verifier.session_status(sid), before)

    def test_valid_window_delivers_exact_authenticated_payload_once(self):
        sender, verifier, gate, calls, records = self.setup_path()
        source = processed_window()
        envelope = sender.seal_window(processed_record_to_wire_window(source))
        accepted = verifier.verify_window(envelope)
        source["samples"][1]["position_m"][0] = 999.0
        self.assertEqual(gate.deliver(accepted), "classified")
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(records), 1)
        self.assertEqual(calls[0].shape, (840,))
        for sample, received in zip(accepted.accepted_window.samples, records[0]["samples"], strict=True):
            self.assertEqual(
                received["position_m"],
                [struct.unpack(">f", component.encode())[0] for component in sample.position_m],
            )
            self.assertEqual(
                received["orientation_xyzw"],
                [struct.unpack(">f", component.encode())[0] for component in sample.orientation_xyzw],
            )
            self.assertEqual(received["tracking_valid"], sample.tracking_valid)
        self.assertNotEqual(records[0]["samples"][1]["position_m"][0], 999.0)
        with self.assertRaisesRegex(ValueError, "already delivered"):
            gate.deliver(accepted)
        self.assertEqual(len(calls), 1)

    def test_modified_payload_is_rejected_without_delivery(self):
        sender, verifier, gate, calls, _ = self.setup_path()
        packet = sender.seal_window(processed_record_to_wire_window(processed_window()))
        parsed = parse_envelope(packet)
        samples = list(parsed.window.samples)
        samples[0] = replace(samples[0], position_m=(F32(0x3F800000), *samples[0].position_m[1:]))
        changed = encode_window(replace(parsed.window, samples=tuple(samples)))
        self.reject_without_delivery(verifier, gate, calls,
                                     envelope_with(changed, packet, tag=parsed.tag), "invalid_tag")

    def test_invalid_hmac_is_rejected_without_delivery(self):
        sender, verifier, gate, calls, _ = self.setup_path()
        packet = sender.seal_window(processed_record_to_wire_window(processed_window()))
        parsed = parse_envelope(packet)
        self.reject_without_delivery(verifier, gate, calls,
                                     envelope_with(parsed.authenticated_bytes, packet, tag=bytes(32)), "invalid_tag")

    def test_exact_replay_is_rejected_without_delivery_or_state_change(self):
        sender, verifier, gate, calls, _ = self.setup_path()
        packet = sender.seal_window(processed_record_to_wire_window(processed_window()))
        self.assertEqual(verifier.verify_window(packet).reason, "accepted")
        self.reject_without_delivery(verifier, gate, calls, packet, "duplicate_sequence")

    def test_future_gap_is_rejected_without_delivery_or_state_change(self):
        sender, verifier, gate, calls, _ = self.setup_path()
        sender.seal_window(processed_record_to_wire_window(processed_window()))
        future = sender.seal_window(processed_record_to_wire_window(processed_window()))
        self.reject_without_delivery(verifier, gate, calls, future, "future_sequence_gap")

    def test_wrong_device_is_rejected_without_delivery_or_state_change(self):
        sender, verifier, gate, calls, _ = self.setup_path()
        packet = sender.seal_window(processed_record_to_wire_window(processed_window()))
        parsed = parse_envelope(packet)
        changed = encode_window(replace(parsed.window, device_id="unknown-device"))
        self.reject_without_delivery(verifier, gate, calls,
                                     envelope_with(changed, packet, tag=parsed.tag), "unknown_device")

    def test_wrong_session_is_rejected_without_delivery_or_state_change(self):
        sender, verifier, gate, calls, _ = self.setup_path()
        packet = sender.seal_window(processed_record_to_wire_window(processed_window()))
        parsed = parse_envelope(packet)
        wrong_sid = b"?" * 16
        changed = encode_window(replace(parsed.window, session_id=wrong_sid))
        self.reject_without_delivery(
            verifier, gate, calls,
            envelope_with(changed, packet, key_id=wrong_sid.hex(), tag=parsed.tag),
            "unknown_session",
        )

    def test_low_quality_valid_tag_is_rejected_without_delivery_or_state_change(self):
        sender, verifier, gate, calls, _ = self.setup_path()
        packet = sender.seal_window(processed_record_to_wire_window(processed_window()))
        parsed = parse_envelope(packet)
        samples = tuple(
            replace(sample, tracking_valid=index < 113)
            for index, sample in enumerate(parsed.window.samples)
        )
        low = replace(parsed.window, samples=samples, tracking_valid_count=113,
                      tracking_valid_fraction_ppm=tracking_ppm(113))
        # encode_window correctly rejects low quality, so construct the structurally
        # valid authenticated bytes by modifying the accepted representation.
        data = bytearray(parsed.authenticated_bytes)
        device_length = int.from_bytes(data[19:21], "big")
        session_offset = 21 + device_length
        window_offset = session_offset + 16 + 8
        start_offset = window_offset + 2 + int.from_bytes(data[window_offset:window_offset + 2], "big")
        data[start_offset + 19:start_offset + 21] = (113).to_bytes(2, "big")
        data[start_offset + 21:start_offset + 25] = tracking_ppm(113).to_bytes(4, "big")
        sample_offset = start_offset + 32
        for index in range(113, 120):
            data[sample_offset + index * 39 + 38] = 0
        submitted = envelope_with(bytes(data), packet, key=sender._key)
        self.reject_without_delivery(verifier, gate, calls, submitted, "data_quality_failure")
        self.assertEqual(low.tracking_valid_count, 113)

    def test_malformed_window_is_rejected_without_delivery_or_state_change(self):
        _, verifier, gate, calls, _ = self.setup_path()
        self.reject_without_delivery(verifier, gate, calls, b"{}", "malformed_message")


if __name__ == "__main__":
    unittest.main()
