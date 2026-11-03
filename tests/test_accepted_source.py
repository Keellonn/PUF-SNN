"""Independent refusal and file-preservation checks using artificial source samples."""
import copy
import json
import struct
import tempfile
import unittest
from pathlib import Path

from puf_snn.accepted_source import SCHEMA, decode_source, inspect_candidate, source_metrics, target_offset


def bits(value):
    return struct.unpack("<i", struct.pack("<f", value))[0]


class AcceptedSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="puf-snn-source-candidate-")
        self.root = Path(self.temp.name)
        self.paths = [self.root / name for name in ("source.json", "windows.jsonl", "metrics.json")]
        self.source = dict(schema_version=SCHEMA, purpose="synthetic_development_only", planned_acquisition_mode="pc_hosted_quest_link",
                           time_basis="head-capture-stopwatch-ns", coordinate_frame="unity_device_origin",
                           numeric_encoding="signed_int32_ieee754_float32_bits", outcome="accepted", processing_version="synthetic-v1",
                           device_id="synthetic-device", session_id="synthetic-session", trial_id="synthetic-trial",
                           split="validation", label="nod", sequence_number=0,
                           samples=[dict(capture_time_ns=i*10_000_000, position_m_float32_bits=[bits(.1), 0, 0],
                                         orientation_xyzw_float32_bits=[0, 0, 0, bits(1)], tracking_valid=True,
                                         tracking_state=3, tracking_flag_available=True, tracking_state_available=True)
                                    for i in range(201)])
        self.summary = source_metrics(decode_source(self.source))
        self.window = dict(schema_version="0.2", source_trial_id="synthetic-trial", window_id="synthetic-trial-window-000",
                           **{k:self.source[k] for k in ("device_id", "session_id", "trial_id", "split", "label", "sequence_number", "coordinate_frame")},
                           window_start_ns=0, window_end_ns=2_000_000_000, target_sample_rate_hz=60,
                           samples=[dict(sample_index=i, capture_time_ns=target_offset(i), position_m=[.1,0,0],
                                         orientation_xyzw=[0,0,0,1], tracking_valid=True) for i in range(120)])

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        for path, value in zip(self.paths, (self.source, self.window, self.summary)):
            path.write_bytes((json.dumps(value, separators=(",", ":")) + "\n").encode())

    def check(self):
        self.write()
        return inspect_candidate(*self.paths)

    def test_valid_case_does_not_claim_live_readiness_or_quaternion_replay(self):
        result = self.check()
        self.assertEqual(result["status"], "COMPLETE", result)
        self.assertFalse(result["live_collection_ready"])
        self.assertFalse(result["unity_quaternion_replay_checked"])
        self.assertFalse(result["ledger_integration_checked"])

    def test_read_only_success_and_failure(self):
        self.write(); before = [p.read_bytes() for p in self.paths]
        inspect_candidate(*self.paths)
        self.assertEqual(before, [p.read_bytes() for p in self.paths])
        self.paths[0].write_bytes(before[0][:-1]); before = [p.read_bytes() for p in self.paths]
        self.assertEqual(inspect_candidate(*self.paths)["status"], "INVALID")
        self.assertEqual(before, [p.read_bytes() for p in self.paths])

    def test_rejected_stopped_and_unknown_outcomes_cannot_pass(self):
        for outcome in ("rejected", "stopped", "processing_failed", None):
            with self.subTest(outcome=outcome):
                self.source["outcome"] = outcome
                self.assertEqual(self.check()["status"], "INVALID")

    def test_source_order_gap_and_coverage_are_checked_before_resampling(self):
        original = copy.deepcopy(self.source)
        for value in (0, -1, 100_000_000):
            self.source = copy.deepcopy(original); self.source["samples"][1]["capture_time_ns"] = value
            self.assertEqual(self.check()["status"], "INVALID")
        self.source = original; self.source["samples"] = self.source["samples"][:10]
        self.assertEqual(self.check()["status"], "INVALID")

    def test_bits_retain_original_float32_and_refuse_nonfinite_or_bool(self):
        self.source["samples"][0]["position_m_float32_bits"][0] = -(2**31)
        restored = decode_source(self.source)[0]["position"][0]
        self.assertEqual(bits(restored), -(2**31))
        for value in (0x7f800000, True, 2**32):
            self.source["samples"][0]["position_m_float32_bits"][0] = value
            self.assertEqual(self.check()["status"], "INVALID")

    def test_metadata_and_sample_shapes_are_strict(self):
        original = copy.deepcopy(self.source)
        for field, value in (("samples", None), ("label", []), ("sequence_number", True), ("trial_id", "../other")):
            self.source = copy.deepcopy(original); self.source[field] = value
            self.assertEqual(self.check()["status"], "INVALID")
        self.source = original; self.source["samples"][0]["extra_pose"] = [1,2,3]
        self.assertEqual(self.check()["status"], "INVALID")

    def test_tracking_and_time_grid_cannot_be_invented(self):
        self.source["samples"][50]["tracking_valid"] = False
        self.assertEqual(self.check()["status"], "INVALID")
        self.source["samples"][50]["tracking_valid"] = True
        self.window["samples"][1]["capture_time_ns"] += 1
        self.assertEqual(self.check()["status"], "INVALID")
        self.window["samples"][1]["capture_time_ns"] -= 1
        self.window["window_start_ns"] = False
        self.assertEqual(self.check()["status"], "INVALID")

    def test_trial_link_and_summary_are_compared(self):
        self.window["source_trial_id"] = "different-trial"
        self.assertEqual(self.check()["status"], "INVALID")
        self.window["source_trial_id"] = self.source["trial_id"]
        self.summary["source_sample_count"] += 1
        self.assertEqual(self.check()["status"], "INVALID")

    def test_missing_torn_duplicate_and_malformed_files_are_refused(self):
        self.write(); original = self.paths[0].read_bytes()
        for value in (b"", b"{\n", original[:-1], b'{"a":1,"a":2}\n'):
            self.paths[0].write_bytes(value)
            self.assertEqual(inspect_candidate(*self.paths)["status"], "INVALID")
        self.paths[0].unlink()
        self.assertEqual(inspect_candidate(*self.paths)["status"], "INVALID")

    def test_resampled_tracking_minimum_is_enforced(self):
        for row in self.source["samples"]:
            row["tracking_valid"] = False
        for row in self.window["samples"]:
            row["tracking_valid"] = False
        self.assertEqual(self.check()["status"], "INVALID")
