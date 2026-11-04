"""Synthetic multi-file accounting, interrupted-write and legacy compatibility checks."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from puf_snn.accepted_source_visit import inspect_source_visit, POLICY
from puf_snn.trial_ledger import inspect_ledger


class AcceptedSourceVisitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="puf-snn-source-visit-")
        self.root = Path(self.temp.name)
        fixture = Path(__file__).resolve().parents[1] / "results/week-10/keegan/source-replay-20261103-001/fixture"
        self.source = json.loads((fixture / "accepted-source.json").read_bytes())
        self.source.update(schema_version="quest-accepted-source-v2", purpose="development_only")
        window = json.loads((fixture / "windows.jsonl").read_bytes())
        self.metrics = json.loads((fixture / "source-metrics.json").read_bytes())
        self.trials = [dict(trial_id=self.source["trial_id"] if i == 0 else f"synthetic-trial-{i}", trial_index=i,
                            block_index=1, prompted_task=task, repeat_of_trial_id="") for i, task in enumerate(
                                ("nod", "shake", "look_left_return", "look_right_return", "still"))]
        self.plan = dict(record_type="plan", schema_version="quest-trial-ledger-v2", participant_code="synthetic-person",
                         visit_code="synthetic-visit", device_id=self.source["device_id"], session_id=self.source["session_id"],
                         processing_version=self.source["processing_version"], window_file_name="windows.jsonl",
                         time_basis="head-capture-stopwatch-ns", raw_retention=POLICY, repeat_policy="none",
                         schedule_seed=2026, maximum_trials=75, created_elapsed_ns=0, trials=self.trials)
        self.events = []
        blob = self.json(window)
        (self.root / "windows.jsonl").write_bytes(blob)
        self.receipt = dict(file_name="windows.jsonl", window_id=window["window_id"], line_sha256=self.sha(blob), file_offset=0, line_length=len(blob))
        for i in range(3):
            for kind in ("prompted", "start_requested", "recording_started"):
                self.event(i, kind)
            if i < 2:
                self.event(i, "completed", raw_sample_count=self.metrics["source_sample_count"] if i == 0 else 0)
                self.event(i, "accepted" if i == 0 else "rejected", reason_code="" if i == 0 else "too_few_source_samples", **(self.receipt if i == 0 else {}))
            else:
                self.event(i, "stopped", reason_code="operator_stop")
        self.event(3, "skipped", reason_code="participant_skip")
        self.event(4, "not_attempted", reason_code="schedule_finished")
        self.event(None, "visit_closed", reason_code="schedule_finished")
        empty = {k: -1 for k in self.metrics}
        empty.update(status="empty", unavailable_reason="", **{k: 0 for k in (
            "source_sample_count", "tracking_valid_count", "tracking_invalid_count", "tracking_flag_available_count", "tracking_state_available_count",
            "positive_interval_count", "nonpositive_interval_count", "interval_overflow_count", "negative_timestamp_count", "gap_over_50ms_count", "nonfinite_pose_count", "zero_orientation_count")})
        self.quality_header = {k: self.plan[k] for k in ("participant_code", "visit_code", "device_id", "session_id", "processing_version", "time_basis", "raw_retention")}
        self.quality_header.update(record_type="source_quality_plan", schema_version="quest-source-quality-v2", ledger_file_name="ledger.jsonl",
                                   interval_quantile_method="nearest_rank", gap_limit_ns=50_000_000)
        self.quality_rows = [dict(record_type="source_quality", summary_index=i+1, elapsed_ns=3_000_000_000,
                                  trial_id=self.trials[i]["trial_id"], source_stage="completed" if i < 2 else "stopped",
                                  reason_code="capture_completed" if i < 2 else "operator_stop", metrics=self.metrics if i == 0 else empty)
                             for i in range(3)]
        self.directory = self.root / "synthetic-visit-accepted-source"
        self.directory.mkdir()
        source_bytes = self.json(self.source)
        self.source_path = self.directory / (self.source["trial_id"] + ".json")
        self.source_path.write_bytes(source_bytes)
        self.header = {k:self.plan[k] for k in ("participant_code", "visit_code", "device_id", "session_id", "processing_version", "raw_retention")}
        self.header.update(record_type="accepted_source_plan", schema_version="quest-accepted-source-visit-v2", purpose="development_only",
                           planned_acquisition_mode="pc_hosted_quest_link", ledger_file_name="ledger.jsonl", window_file_name="windows.jsonl",
                           quality_file_name="synthetic-visit-source-quality.jsonl", source_directory_name=self.directory.name)
        self.source_receipt = dict(record_type="accepted_source", trial_id=self.source["trial_id"], file_name=self.source_path.name,
                                   file_sha256=self.sha(source_bytes), byte_length=len(source_bytes), window_id=window["window_id"],
                                   window_line_sha256=self.receipt["line_sha256"])
        self.end = dict(record_type="accepted_source_closed", accepted_source_count=1)
        self.ledger = self.root / "ledger.jsonl"
        self.manifest = self.root / "synthetic-visit-accepted-source.jsonl"
        self.save()

    @staticmethod
    def sha(data): return hashlib.sha256(data).hexdigest()
    @staticmethod
    def json(obj): return (json.dumps(obj, separators=(",", ":")) + "\n").encode()
    def event(self, index, kind, **fields):
        e = dict(record_type="event", event_index=len(self.events)+1, event_type=kind, elapsed_ns=3_000_000_000,
                 trial_id="" if index is None else self.trials[index]["trial_id"], reason_code="", raw_sample_count=-1,
                 window_id="", file_name="", line_sha256="", file_offset=-1, line_length=0)
        e.update(fields); self.events.append(e)
    def save(self):
        self.ledger.write_bytes(b"".join(self.json(r) for r in [self.plan, *self.events]))
        (self.root / "synthetic-visit-source-quality.jsonl").write_bytes(b"".join(self.json(r) for r in [self.quality_header, *self.quality_rows]))
        self.manifest.write_bytes(b"".join(self.json(r) for r in [self.header, self.source_receipt, self.end]))
    def check(self): return inspect_source_visit(self.ledger)
    def invalid(self):
        report = self.check(); self.assertEqual(report["status"], "INVALID", report)
        self.assertEqual(inspect_ledger(self.ledger)["status"], "INVALID")
    def tearDown(self): self.temp.cleanup()

    def test_complete_mixed_outcomes_and_top_level_reconciliation(self):
        report = self.check(); self.assertEqual(report["status"], "COMPLETE", report)
        self.assertEqual(report["source_receipts"], 1); self.assertFalse(report["live_collection_ready"])
        self.assertFalse(report["unity_quaternion_replay_checked"])
        ledger = inspect_ledger(self.ledger); self.assertEqual(ledger["status"], "COMPLETE", ledger)
        self.assertEqual(ledger["counts"]["accepted"], 1); self.assertEqual(ledger["counts"]["quality_rejected"], 1)
        self.assertEqual(ledger["counts"]["stopped"], 1)

    def test_read_only_on_success_and_failure(self):
        before = {p:p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.check(); self.assertEqual(before, {p:p.read_bytes() for p in before})
        self.manifest.write_bytes(self.manifest.read_bytes()[:-1])
        before = {p:p.read_bytes() for p in before}
        self.invalid(); self.assertEqual(before, {p:p.read_bytes() for p in before})

    def test_missing_or_partial_source_file(self):
        original = self.source_path.read_bytes()
        for value in (b"", original[:50], original[:-1]):
            self.source_path.write_bytes(value); self.invalid()
        self.source_path.unlink(); self.invalid()

    def test_source_without_durable_acceptance_is_not_adopted(self):
        self.events = self.events[:4]
        self.save(); self.invalid()
        self.assertEqual(inspect_ledger(self.ledger, verify_sources=False)["unreferenced_window_records"], 1)

    def test_source_receipt_missing_after_acceptance(self):
        self.manifest.write_bytes(self.json(self.header)); self.invalid()

    def test_unreferenced_motion_file_is_reported_and_preserved(self):
        extra = self.directory / "stopped-trial.json"; extra.write_bytes(self.source_path.read_bytes())
        self.invalid(); self.assertTrue(extra.exists())

    def test_manifest_and_ledger_closure_are_both_required(self):
        self.manifest.write_bytes(self.json(self.header) + self.json(self.source_receipt))
        self.assertEqual(self.check()["status"], "INCOMPLETE")
        self.assertEqual(inspect_ledger(self.ledger)["status"], "INCOMPLETE")
        self.save(); self.ledger.write_bytes(b"".join(self.json(r) for r in [self.plan, *self.events[:-1]]))
        self.assertEqual(self.check()["status"], "INCOMPLETE")

    def test_hash_length_and_window_receipt_mismatch(self):
        for key, value in (("file_sha256", "0"*64), ("byte_length", True), ("window_line_sha256", "0"*64), ("window_id", "another")):
            old = self.source_receipt[key]; self.source_receipt[key] = value; self.save(); self.invalid(); self.source_receipt[key] = old

    def test_nonaccepted_duplicate_and_post_close_source_receipts(self):
        self.source_receipt["trial_id"] = self.trials[1]["trial_id"]; self.save(); self.invalid()
        self.source_receipt["trial_id"] = self.source["trial_id"]; self.save()
        self.manifest.write_bytes(self.json(self.header)+self.json(self.source_receipt)*2+self.json(self.end)); self.invalid()
        self.save(); self.manifest.write_bytes(self.manifest.read_bytes()+self.json(self.source_receipt)); self.invalid()

    def test_version_policy_and_link_mismatches(self):
        for key, value in (("raw_retention", "not_saved"), ("purpose", "research_approved"), ("ledger_file_name", "other.jsonl"), ("source_directory_name", "../outside")):
            old=self.header[key]; self.header[key]=value; self.save(); self.invalid(); self.header[key]=old

    def test_source_metrics_processing_version_and_grid_mismatches(self):
        self.quality_rows[0]["metrics"] = copy.deepcopy(self.metrics)
        self.quality_rows[0]["metrics"]["tracking_flag_available_count"] -= 1
        self.save(); self.invalid()
        self.quality_rows[0]["metrics"] = self.metrics; self.save()
        source = copy.deepcopy(self.source); source["processing_version"] = "changed-build"
        blob = self.json(source); self.source_path.write_bytes(blob)
        self.source_receipt.update(file_sha256=self.sha(blob), byte_length=len(blob)); self.save(); self.invalid()

    def test_unsafe_filename_and_duplicate_json_keys(self):
        self.source_receipt["file_name"] = "../outside.json"; self.save(); self.invalid()
        self.source_receipt["file_name"] = self.source_path.name; self.save()
        self.manifest.write_bytes(self.manifest.read_bytes().replace(b'"purpose":"development_only"', b'"purpose":"development_only","purpose":"development_only"')); self.invalid()

    def test_closed_count_and_missing_quality_summary(self):
        self.end["accepted_source_count"] = 2; self.save(); self.invalid()
        self.end["accepted_source_count"] = 1; self.quality_rows.pop(); self.save(); self.invalid()

    def test_legacy_plan_remains_readable_without_new_source_files(self):
        self.plan.update(schema_version="quest-trial-ledger-v1", raw_retention="not_saved")
        self.quality_header.update(schema_version="quest-source-quality-v1", raw_retention="not_saved")
        self.save()
        self.assertEqual(inspect_ledger(self.ledger)["status"], "COMPLETE")
        self.assertNotIn("accepted_source", inspect_ledger(self.ledger))
        self.assertEqual(self.check()["status"], "INVALID")
