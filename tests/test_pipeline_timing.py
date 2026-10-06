"""Timing machinery/boundary tests; fixtures are not benchmark evidence."""

from copy import deepcopy
import gc
import importlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

import test_pipeline_v2 as fixtures
from puf_snn import pipeline_v2
from puf_snn.auth.sender import Sender
from puf_snn.frozen_pipeline import FrozenModelBundle
from puf_snn.pipeline_timing import (
    ACCEPTED_PATHS, REJECTED_PATHS, CONDITIONS, TimingCapture, instrument_pipeline,
    latency_statistics, one_model_bundle, outlier_diagnosis, quantile, reconcile_timing,
    run_timed_attempt, select_outliers, select_timing_sources, summarize_traces, validate_timing_config,
)
from puf_snn.pipeline_v2 import ModelCallCounts
from scripts import benchmark_week6_v2 as runner


def settings():
    return json.loads((Path(runner.__file__).resolve().parents[3] / "configs/week6_timing.json").read_text(encoding="utf-8"))


def trace_row(elapsed=10_000_000, *, phase="measured", path="post_window_recurring", decision="accept"):
    return {"condition": "condition", "phase": phase, "attempt_index": 0,
            "path": path, "decision": decision, "reason": "accepted" if decision == "accept" else "invalid_tag",
            "elapsed_ns": elapsed, "thread_cpu_ns": elapsed,
            "model_calls": {"preprocessing": 1, "motion": 1, "anomaly": 1} if decision == "accept" else
                           {"preprocessing": 0, "motion": 0, "anomaly": 0},
            "spans": [{"id": 0, "parent_id": None, "stage": path, "start_ns": 100,
                       "wall_ns": elapsed, "thread_cpu_ns": elapsed, "exception": False}], "gc_events": []}


class PipelineTimingTests(unittest.TestCase):
    def cohort(self):
        rows = []
        for split in ("test", "validation"):
            for device in range(6):
                for label in ("nod", "shake", "look_left_return", "look_right_return", "still"):
                    for index in range(20):
                        rows.append(dict(split=split, device_id=f"device-{device}", label=label,
                                         window_id=f"{split}-{device}-{label}-{index:02}"))
        return rows

    def test_fixed_timing_matrix_and_counts(self):
        config = settings()
        validate_timing_config(config)
        self.assertEqual(len(config["conditions"]), 6)
        self.assertEqual(config["measured_attempts_per_condition"], 600)
        self.assertEqual([r["motion"] for r in config["conditions"][-3:]],
                         [f"snn_32_seed_{seed}" for seed in (7, 17, 27)])

    def test_changed_threshold_choice_or_sample_count_is_refused(self):
        for key, value in (("measured_attempts_per_condition", 100), ("gc_enabled", False), ("batch_size", True)):
            with self.subTest(key=key):
                config = settings()
                config[key] = value
                with self.assertRaises(ValueError):
                    validate_timing_config(config)
        config = settings()
        config["conditions"][0]["anomaly"] = "anomaly_random_forest_seed6027"
        with self.assertRaises(ValueError):
            validate_timing_config(config)

    def test_all_test_sources_selected_without_outcome_filter(self):
        rows = self.cohort()
        rows.reverse()
        test, warm = select_timing_sources(rows)
        self.assertEqual(len(test), 600)
        self.assertEqual(len(warm), 20)
        self.assertEqual(test, sorted(test, key=lambda r: (r["device_id"], r["label"], r["window_id"])))
        self.assertFalse({r["window_id"] for r in test} & {r["window_id"] for r in warm})

    def test_missing_or_duplicate_source_refused(self):
        for rows in (self.cohort()[:-1], self.cohort() + [self.cohort()[0]]):
            with self.assertRaises(ValueError):
                select_timing_sources(rows)

    def test_one_model_bundle_uses_existing_objects_and_thresholds(self):
        condition = settings()["conditions"][0]
        motion, detector = object(), {"threshold": {"threshold": .5431}, "model": object()}
        original = FrozenModelBundle({condition["motion"]: motion}, {condition["anomaly"]: detector}, {"a": "b"})
        selected = one_model_bundle(original, condition)
        self.assertIs(selected.motion[condition["motion"]], motion)
        self.assertIs(selected.detectors[condition["anomaly"]], detector)
        self.assertEqual(detector["threshold"]["threshold"], .5431)

    def test_nested_spans_record_hierarchy_not_arguments_or_returns(self):
        capture = TimingCapture()
        secret = b"DO-NOT-EXPORT"
        with instrument_pipeline(capture):
            result = capture.measure("outer", lambda: capture.wrap("inner", lambda value: value)(secret))
        self.assertIs(result, secret)
        self.assertEqual([r["stage"] for r in capture.last_trace["spans"]], ["outer", "inner"])
        self.assertEqual(capture.last_trace["spans"][1]["parent_id"], 0)
        self.assertNotIn("DO-NOT-EXPORT", json.dumps(capture.last_trace))
        self.assertGreaterEqual(capture.last_trace["elapsed_ns"], capture.last_trace["spans"][1]["wall_ns"])

    def test_original_exception_propagates_without_message_in_evidence(self):
        capture = TimingCapture()
        def fail():
            raise LookupError("SECRET-EXCEPTION-TEXT")
        with self.assertRaises(LookupError):
            capture.measure("outer", capture.wrap("inner", fail))
        self.assertTrue(all(row["exception"] for row in capture.last_trace["spans"]))
        self.assertNotIn("SECRET", json.dumps(capture.last_trace))
        self.assertFalse(capture.active)

    def test_wrappers_and_gc_callbacks_restore_after_error(self):
        capture = TimingCapture()
        before_gc = tuple(gc.callbacks)
        original = Sender.seal_window
        original_decode = pipeline_v2.reconstruct
        with self.assertRaises(ZeroDivisionError):
            with instrument_pipeline(capture):
                capture.measure("outer", lambda: 1 / 0)
        self.assertIs(Sender.seal_window, original)
        self.assertIs(pipeline_v2.reconstruct, original_decode)
        self.assertEqual(tuple(gc.callbacks), before_gc)

    def test_inactive_wrapper_does_not_record_housekeeping(self):
        capture = TimingCapture()
        self.assertEqual(capture.wrap("outside", lambda: 42)(), 42)
        self.assertIsNone(capture.last_trace)

    def test_overlapping_outer_measurements_refused(self):
        capture = TimingCapture()
        with self.assertRaises(RuntimeError):
            capture.measure("outer", lambda: capture.measure("inner", lambda: None))

    def test_gc_overlap_records_generation_not_collected_objects(self):
        capture = TimingCapture()
        capture.measure("outer", lambda: gc.collect(0))
        self.assertTrue(capture.last_trace["gc_events"])
        self.assertEqual(capture.last_trace["gc_events"][0]["generation"], 0)
        self.assertEqual(set(capture.last_trace["gc_events"][0]),
                         {"generation", "start_ns", "end_ns", "collected", "uncollectable"})

    def timed_peers(self, **kwargs):
        capture = TimingCapture()
        peers = fixtures.PipelineV2Tests().peers(
            prepare_callback=capture.wrap("prepare_both_model_inputs", fixtures.prepare),
            motion_callback=capture.wrap("motion_consumer", lambda _: "nod"),
            anomaly_callback=capture.wrap("anomaly_consumer", lambda _: {"score": .1, "flag": False}), **kwargs)
        return capture, peers

    def test_real_admission_first_window_and_all_rejection_controls(self):
        capture, peers = self.timed_peers()
        pipeline = peers[0]
        rows = []
        read = Mock(return_value=fixtures.response_with_flips({2, 8, 19}))
        with instrument_pipeline(capture):
            attempt = run_timed_attempt(pipeline, fixtures.source_record(), read, "timing-test", capture, rows.append)
        self.assertEqual(attempt.decision, "accept")
        read.assert_called_once_with()
        self.assertEqual({r["path"] for r in rows}, ACCEPTED_PATHS | REJECTED_PATHS)
        self.assertEqual(len(rows), 8)
        self.assertEqual(pipeline.calls, ModelCallCounts(4, 4, 4))
        first_stages = {r["stage"] for r in rows[0]["spans"]}
        for name in ("reconstruction", "independent_credential_verification", "receiver_local_admission",
                     "receiver_confirmation", "first_post_window_total", "sender_audit_commit", "verifier_audit_commit"):
            self.assertIn(name, first_stages)
        for row in rows:
            if row["decision"] == "reject":
                self.assertFalse(any(row["model_calls"].values()))
        self.assertEqual(rows[-1]["sequence_number"], 3)

    def test_failed_admission_retained_without_retry_or_inference(self):
        capture, peers = self.timed_peers(missing_record=True)
        rows, read = [], Mock(return_value=fixtures.REFERENCE)
        with instrument_pipeline(capture):
            result = run_timed_attempt(peers[0], fixtures.source_record(), read, "refused-test", capture, rows.append)
        read.assert_called_once_with()
        self.assertEqual(result.decision, "reject")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["read_count"], 1)
        self.assertEqual(rows[0]["model_calls"], {"preprocessing": 0, "motion": 0, "anomaly": 0})
        self.assertEqual(rows[0]["sender_kdf_ns"], [])
        self.assertEqual(rows[0]["verifier_kdf_ns"], [])

    def test_io_emission_and_assertions_are_outside_timing(self):
        capture, peers = self.timed_peers()
        active = []
        with instrument_pipeline(capture):
            run_timed_attempt(peers[0], fixtures.source_record(), lambda: fixtures.REFERENCE,
                              "io-boundary", capture, lambda row: active.append(capture.active))
        self.assertEqual(active, [False] * 8)

    def test_exact_quantile_and_empty_statistics(self):
        self.assertEqual(quantile([0, 100], .95), 95)
        self.assertEqual(latency_statistics([0, 100_000_000])["p99_ms"], 99)
        self.assertEqual(latency_statistics([])["count"], 0)
        self.assertIsNone(latency_statistics([])["p95_ms"])
        with self.assertRaises(ValueError):
            latency_statistics([True])

    def test_nested_percentiles_are_not_added_into_outer_total(self):
        row = trace_row(10_000_000)
        row["spans"] += [dict(stage="parent", wall_ns=9_000_000), dict(stage="child", wall_ns=8_000_000)]
        result = summarize_traces([row])
        self.assertEqual(result["root_paths"][0]["p95_ms"], 10)
        self.assertEqual([r["p95_ms"] for r in result["nested_stages"]], [8, 9])

    def test_repeated_stage_calls_sum_only_within_each_trace(self):
        row = trace_row()
        row["spans"] += [dict(stage="audit", wall_ns=100), dict(stage="audit", wall_ns=200)]
        self.assertEqual(summarize_traces([row])["nested_stages"][0]["p50_ms"], .0003)

    def test_first_use_warmup_and_rejections_not_pooled(self):
        rows = [trace_row(), trace_row(phase="condition_first_use"), trace_row(phase="warmup"),
                trace_row(path="bad_tag_receiver", decision="reject")]
        self.assertEqual(len(summarize_traces(rows)["root_paths"]), 4)

    def test_all_absolute_outliers_and_group_maxima_retained(self):
        rows = [trace_row(i * 1_000_000) for i in (1, 25, 30)]
        outliers = select_outliers(rows)
        self.assertEqual([r["trace"]["elapsed_ns"] for r in outliers], [25_000_000, 30_000_000])
        small = trace_row(100)
        self.assertEqual(len(select_outliers([small])), 1)

    def test_outlier_gc_overlap_is_clipped_to_actual_root_bounds(self):
        row = trace_row(100)
        row["gc_events"] = [{"start_ns": 0, "end_ns": 150}]
        self.assertEqual(outlier_diagnosis(row)["gc_overlap_ns"], 50)

    def test_outlier_diagnostics_do_not_claim_causal_os_or_gc_explanation(self):
        row = trace_row(30_000_000)
        row["thread_cpu_ns"] = 1_000_000
        diagnosis = outlier_diagnosis(row)
        self.assertIn("unresolved", diagnosis["causal_attribution"])
        self.assertIn("CPU frequency/power transitions", diagnosis["unmeasured_causes"])
        self.assertEqual(diagnosis["wall_minus_thread_cpu_ns"], 29_000_000)

    def synthetic_reconciliation(self):
        conditions = [dict(name="condition")]
        rows = []
        for phase in ("measured", "condition_first_use", "warmup"):
            index = 1 if phase == "warmup" else 0
            for path in sorted(ACCEPTED_PATHS | REJECTED_PATHS):
                row = trace_row(phase=phase, path=path, decision="accept" if path in ACCEPTED_PATHS else "reject")
                row.update(attempt_index=index, source_window_id=f"{phase}-source", selected_bit_error_count=1)
                if path == "fresh_to_first_window":
                    row.update(read_count=1, admission={"decision": "accept", "reason": "accepted"})
                rows.append(row)
        return rows, conditions

    def test_reconciliation_requires_all_attempts_and_controls(self):
        rows, conditions = self.synthetic_reconciliation()
        result = reconcile_timing(rows, conditions, measured=1, warmup=2)
        self.assertEqual(result["fresh_attempt_count"], 3)
        for changed in (rows[:-1], rows + [rows[0]]):
            with self.assertRaises(ValueError):
                reconcile_timing(changed, conditions, measured=1, warmup=2)

    def test_reconciliation_rejects_calls_on_refused_messages(self):
        rows, conditions = self.synthetic_reconciliation()
        next(r for r in rows if r["decision"] == "reject")["model_calls"]["motion"] = 1
        with self.assertRaises(ValueError):
            reconcile_timing(rows, conditions, measured=1, warmup=2)

    def test_reconciliation_detects_orphan_window_traces(self):
        rows, conditions = self.synthetic_reconciliation()
        orphan = deepcopy(rows[0])
        orphan.update(path="bad_tag_receiver", attempt_index=999)
        with self.assertRaises(ValueError):
            reconcile_timing(rows + [orphan], conditions, measured=1, warmup=2)

    def test_measured_admission_refusal_is_not_discarded(self):
        rows, conditions = self.synthetic_reconciliation()
        rows = [r for r in rows if r["phase"] != "measured" or r["path"] == "fresh_to_first_window"]
        refusal = next(r for r in rows if r["phase"] == "measured")
        refusal.update(decision="reject", stage="reconstruction", reason="failed_reconstruction",
                       admission={"decision": "reject", "reason": "failed_reconstruction"},
                       model_calls={"preprocessing": 0, "motion": 0, "anomaly": 0})
        result = reconcile_timing(rows, conditions, measured=1, warmup=2)
        self.assertEqual(result["refused_by_condition_phase_reason"][0]["count"], 1)

    def test_text_csv_and_attributes_have_exact_lf_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner.write_csv(root / "table.csv", [dict(count=1, stage="test")])
            runner.write_json(root / "value.json", dict(value=1))
            runner.write_result_attributes(root / ".gitattributes")
            for path in root.iterdir():
                self.assertNotIn(b"\r", path.read_bytes())

    def test_report_does_not_claim_durability_or_invent_outlier_causes(self):
        text = runner.report_text("NONSECRET-TEST", {"root_paths": []}, {"fresh_attempt_count": 3})
        for value in ("unresolved", "durable audit", "not a fully cold", "never add nested percentiles"):
            self.assertIn(value.lower(), text.lower())

    def test_disabled_gc_refused_without_changing_runtime_setting(self):
        before = gc.isenabled()
        try:
            gc.disable()
            with self.assertRaises(ValueError):
                runner.timer_conditions()
            self.assertFalse(gc.isenabled())
        finally:
            if before:
                gc.enable()


if __name__ == "__main__":
    unittest.main()
