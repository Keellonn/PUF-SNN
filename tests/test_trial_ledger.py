"""Synthetic ledger fixtures only; no human recordings or Unity substitutes."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from puf_snn.trial_ledger import inspect_ledger


class TrialLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="puf-snn-ledger-python-")
        self.root = Path(self.temp.name)
        self.path = self.root / "ledger.jsonl"
        self.plan = dict(record_type="plan", schema_version="quest-trial-ledger-v1", participant_code="synthetic-person",
                         visit_code="synthetic-visit", device_id="synthetic-device", session_id="synthetic-session",
                         processing_version="synthetic-unit-test-build", window_file_name="windows.jsonl",
                         time_basis="head-capture-stopwatch-ns", raw_retention="not_saved", repeat_policy="none",
                         schedule_seed=2026, maximum_trials=75, created_elapsed_ns=10,
                         trials=[dict(trial_id=f"trial-{i}", trial_index=i, block_index=1, prompted_task=label,
                                      repeat_of_trial_id="") for i, label in enumerate(
                             ("nod", "shake", "look_left_return", "look_right_return", "still"))])
        self.rows = [self.plan]

    def tearDown(self):
        self.temp.cleanup()

    def event(self, kind, index=None, reason="", **fields):
        row = dict(record_type="event", event_index=len(self.rows), event_type=kind, elapsed_ns=10,
                   trial_id="" if index is None else f"trial-{index}", reason_code=reason,
                   raw_sample_count=-1, window_id="", file_name="", line_sha256="", file_offset=-1, line_length=0)
        row.update(fields)
        self.rows.append(row)
        return row

    def begin(self, index):
        for kind in ("prompted", "start_requested", "recording_started"):
            self.event(kind, index)

    def remaining(self, indices, reason="operator_stop"):
        for index in indices:
            self.event("not_attempted", index, reason)
        self.event("visit_closed", reason=reason)

    def write(self, tail=b""):
        self.path.write_bytes(b"".join((json.dumps(row, separators=(",", ":")) + "\n").encode() for row in self.rows) + tail)
        return inspect_ledger(self.path)

    def window(self, index=0):
        record = dict(window_id=f"trial-{index}-window-000", trial_id=f"trial-{index}", source_trial_id=f"trial-{index}",
                      device_id=self.plan["device_id"], session_id=self.plan["session_id"], sequence_number=index,
                      label=self.plan["trials"][index]["prompted_task"], samples=[{}] * 120)
        line = (json.dumps(record, separators=(",", ":")) + "\n").encode()
        path = self.root / "windows.jsonl"
        offset = path.stat().st_size if path.exists() else 0
        with path.open("ab") as stream:
            stream.write(line)
        return dict(window_id=record["window_id"], file_name=path.name, line_sha256=hashlib.sha256(line).hexdigest(),
                    file_offset=offset, line_length=len(line))

    def accepted(self, index=0):
        self.begin(index)
        self.event("completed", index, raw_sample_count=120)
        return self.event("accepted", index, **self.window(index))

    def test_mixed_visit_counts_partition_without_losing_rejections(self):
        self.accepted()
        self.begin(1); self.event("completed", 1, raw_sample_count=0); self.event("rejected", 1, "too_few_source_samples")
        self.event("skipped", 2, "participant_skip")
        self.begin(3); self.event("stopped", 3, "participant_stop")
        self.remaining([4])
        result = self.write()
        self.assertEqual(result["status"], "COMPLETE", result["issues"])
        counts = result["counts"]
        self.assertEqual((counts["scheduled"], counts["attempted"], counts["not_started"]), (5, 3, 2))
        self.assertEqual((counts["completed"], counts["accepted"], counts["quality_rejected"], counts["stopped"]), (2, 1, 1, 1))

    def test_uncertain_capture_start_is_not_falsely_counted_as_recording(self):
        self.event("prompted", 0); self.event("start_requested", 0)
        result = self.write()
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["counts"]["attempted"], 1)
        self.assertEqual(result["counts"]["recording_began_confirmed"], 0)
        self.assertEqual(result["counts"]["recording_began_uncertain"], 1)

    def test_completed_but_unprocessed_trial_remains_pending(self):
        self.begin(0); self.event("completed", 0, raw_sample_count=120)
        result = self.write()
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(result["counts"]["pending_processing"], 1)
        self.assertEqual(result["counts"]["quality_rejected"], 0)

    def test_torn_event_keeps_the_prefix_without_repairing_the_file(self):
        self.begin(0)
        result = self.write(b'{"record_type":"event"')
        before = self.path.read_bytes()
        self.assertEqual(result["status"], "INVALID")
        self.assertEqual(result["counts"]["unfinished_attempts"], 1)
        self.assertIn("oversized_or_torn_ledger_record", result["issues"])
        self.assertEqual(before, self.path.read_bytes())

    def test_missing_plan_is_invalid_not_a_zero_trial_success(self):
        self.path.write_bytes(b"")
        result = inspect_ledger(self.path)
        self.assertEqual(result["status"], "INVALID")
        self.assertIsNone(result["counts"])

    def test_missing_accepted_file_is_not_reclassified_as_quality_rejection(self):
        self.accepted(); self.remaining(range(1, 5)); (self.root / "windows.jsonl").unlink()
        result = self.write()
        self.assertIn("missing_window_file", result["issues"])
        self.assertEqual(result["counts"]["accepted"], 1)
        self.assertEqual(result["counts"]["quality_rejected"], 0)

    def test_changed_window_bytes_fail_the_receipt(self):
        self.accepted(); self.remaining(range(1, 5))
        path = self.root / "windows.jsonl"; path.write_bytes(path.read_bytes().replace(b'"nod"', b'"bad"'))
        result = self.write()
        self.assertIn("window_receipt_mismatch", result["issues"])
        self.assertIn("window_identity_or_prompt_mismatch", result["issues"])

    def test_wrong_label_is_rejected_even_with_a_recomputed_hash(self):
        event = self.accepted(); self.remaining(range(1, 5))
        path = self.root / "windows.jsonl"; path.write_bytes(path.read_bytes().replace(b'"nod"', b'"bad"'))
        event["line_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertIn("window_identity_or_prompt_mismatch", self.write()["issues"])

    def test_orphan_window_from_a_write_before_an_interruption_is_reported(self):
        self.begin(0); self.event("completed", 0, raw_sample_count=120); self.window()
        result = self.write()
        self.assertEqual(result["unreferenced_window_records"], 1)
        self.assertIn("unreferenced_window_records", result["issues"])
        self.assertEqual(result["counts"]["pending_processing"], 1)

    def test_duplicate_event_and_early_close_are_invalid(self):
        self.begin(0)
        self.rows.append(copy.deepcopy(self.rows[-1]))
        self.assertIn("event_order_mismatch", self.write()["issues"])
        self.rows = [self.plan]; self.event("visit_closed", reason="operator_stop")
        self.assertIn("closed_with_unresolved_trials", self.write()["issues"])

    def test_false_integer_duplicate_json_and_nonfinite_are_invalid(self):
        self.plan["maximum_trials"] = True
        self.assertEqual(self.write()["status"], "INVALID")
        self.path.write_bytes(b'{"record_type":"plan","record_type":"plan"}\n')
        self.assertIn("duplicate_json_key", inspect_ledger(self.path)["issues"])
        self.path.write_bytes(b'{"record_type":NaN}\n')
        self.assertIn("nonfinite_json_number", inspect_ledger(self.path)["issues"])

    def test_malformed_task_types_are_reported_without_crashing(self):
        self.plan["trials"][0]["prompted_task"] = []
        self.assertIn("invalid_task_or_repeat", self.write()["issues"])

    def test_processing_failure_has_a_separate_denominator(self):
        self.begin(0); self.event("completed", 0, raw_sample_count=120)
        self.event("processing_failed", 0, "window_write_failed"); self.remaining(range(1, 5))
        result = self.write()
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["counts"]["processing_failed"], 1)
        self.assertEqual(result["counts"]["quality_rejected"], 0)

    def test_execution_notes_do_not_change_prompted_labels(self):
        self.begin(0); self.event("execution_note", 0, "participant_reported_mistake")
        self.event("completed", 0, raw_sample_count=120); self.event("rejected", 0, "tracking_coverage")
        self.remaining(range(1, 5)); result = self.write()
        self.assertEqual(result["trials"][0]["prompted_task"], "nod")
        self.assertEqual(result["trials"][0]["notes"], ["participant_reported_mistake"])

    def test_parallel_capture_and_events_after_close_are_invalid(self):
        self.event("prompted", 0); self.event("prompted", 1)
        self.assertIn("invalid_trial_transition", self.write()["issues"])
        self.rows = [self.plan]; self.remaining(range(5)); self.event("skipped", 0, "participant_skip")
        self.assertIn("event_after_visit_close", self.write()["issues"])

    def test_reference_paths_and_unknown_fields_are_refused(self):
        self.plan["window_file_name"] = "../outside.jsonl"
        self.assertIn("invalid_window_filename", self.write()["issues"])
        self.plan["window_file_name"] = "windows.jsonl"; self.plan["raw_samples"] = ["not permitted"]
        self.assertIn("invalid_plan_fields", self.write()["issues"])

    def test_backward_clock_is_not_accepted(self):
        self.event("prompted", 0, elapsed_ns=9)
        self.assertIn("event_clock_mismatch", self.write()["issues"])


if __name__ == "__main__":
    unittest.main()
