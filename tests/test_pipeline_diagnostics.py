"""Diagnostic controls and real boundary fixtures, not performance evidence."""

from dataclasses import replace
import gc
import json
import unittest
from unittest.mock import Mock, patch

import test_pipeline_v2 as fixtures
from puf_snn import pipeline_v2
from puf_snn.auth.sender import Sender
from puf_snn.pipeline_diagnostics import (
    MODES, DiagnosticMode, NestedDiagnosticCapture, OuterDiagnosticCapture,
    TraceRetention, checked_mode, diagnostic_gc_policy, diagnostic_instrumentation,
    diagnostic_mode, make_diagnostic_capture, runtime_snapshot,
)
from puf_snn.pipeline_timing import run_timed_attempt
from puf_snn.pipeline_v2 import ModelCallCounts


class PipelineDiagnosticTests(unittest.TestCase):
    def test_four_fixed_modes_and_conditional_contrasts(self):
        self.assertEqual(len(MODES), 4)
        self.assertEqual([(m.nested_spans, m.retain_full_traces, m.automatic_gc) for m in MODES],
                         [(True, True, True), (True, False, True),
                          (False, False, True), (True, False, False)])
        self.assertTrue(all(diagnostic_mode(m.name) is m for m in MODES))

    def test_unknown_or_silently_changed_mode_refused(self):
        with self.assertRaises(ValueError):
            diagnostic_mode("tuned_fast_mode")
        for value in ("nested_stream_gc_on", replace(MODES[0], automatic_gc=False),
                      DiagnosticMode("unplanned", True, True, True),
                      replace(MODES[0], automatic_gc=1)):
            with self.assertRaises(ValueError):
                checked_mode(value)

    def test_modes_are_immutable(self):
        with self.assertRaises(AttributeError):
            MODES[0].automatic_gc = False

    def test_factories_choose_nested_and_outer_collectors(self):
        for mode in MODES:
            capture = make_diagnostic_capture(mode)
            cls = NestedDiagnosticCapture if mode.nested_spans else OuterDiagnosticCapture
            self.assertIsInstance(capture, cls)

    def test_mismatched_collector_and_mode_refused(self):
        with self.assertRaises(ValueError):
            diagnostic_instrumentation(MODES[0], OuterDiagnosticCapture())

    def test_outer_wrap_is_original_callable_and_records_only_root(self):
        capture = OuterDiagnosticCapture()
        action = lambda: 42
        self.assertIs(capture.wrap("ignored_child", action), action)
        self.assertEqual(capture.measure("outer", action), 42)
        self.assertEqual(len(capture.last_trace["spans"]), 1)
        self.assertEqual(capture.last_trace["spans"][0]["stage"], "outer")

    def test_nested_collector_preserves_stage_tree(self):
        capture = NestedDiagnosticCapture()
        self.assertEqual(capture.measure("outer", capture.wrap("inner", lambda: 42)), 42)
        self.assertEqual([s["stage"] for s in capture.last_trace["spans"]], ["outer", "inner"])
        self.assertEqual(capture.last_trace["spans"][1]["parent_id"], 0)

    def test_monotonic_bounds_and_public_native_identifiers(self):
        for cls in (NestedDiagnosticCapture, OuterDiagnosticCapture):
            capture = cls()
            capture.measure("outer", lambda: None)
            row = capture.last_trace
            self.assertEqual(row["clock_end_ns"] - row["clock_start_ns"], row["elapsed_ns"])
            self.assertGreater(row["process_id"], 0)
            self.assertGreater(row["native_thread_id"], 0)
            self.assertIn(row["observer"], ("nested", "outer_only"))

    def test_exception_propagates_without_secret_export_and_callbacks_restore(self):
        before = tuple(gc.callbacks)
        def fail():
            raise LookupError("NONSECRET-NOT-FOR-EVIDENCE")
        for cls in (NestedDiagnosticCapture, OuterDiagnosticCapture):
            capture = cls()
            with self.assertRaises(LookupError):
                capture.measure("outer", capture.wrap("inner", fail))
            self.assertTrue(capture.last_trace["spans"][0]["exception"])
            self.assertNotIn("NOT-FOR-EVIDENCE", json.dumps(capture.last_trace))
            self.assertFalse(capture.active)
            self.assertEqual(tuple(gc.callbacks), before)

    def test_overlapping_roots_refused(self):
        for cls in (NestedDiagnosticCapture, OuterDiagnosticCapture):
            capture = cls()
            with self.assertRaises(RuntimeError):
                capture.measure("outer", lambda: capture.measure("inner", lambda: None))
            self.assertFalse(capture.active)

    def test_secret_arguments_and_return_values_are_not_recorded(self):
        secret = b"NONSECRET-PAYLOAD-NOT-FOR-TRACE"
        for cls in (NestedDiagnosticCapture, OuterDiagnosticCapture):
            capture = cls()
            self.assertIs(capture.measure("outer", lambda: capture.wrap("inner", lambda x: x)(secret)), secret)
            self.assertNotIn("PAYLOAD", json.dumps(capture.last_trace))

    def test_outer_gc_overlap_has_same_interval_fields(self):
        capture = OuterDiagnosticCapture()
        capture.measure("outer", lambda: gc.collect(0))
        events = capture.last_trace["gc_events"]
        self.assertTrue(events)
        self.assertEqual(set(events[0]), {"generation", "start_ns", "end_ns", "collected", "uncollectable"})
        self.assertGreaterEqual(events[0]["end_ns"], events[0]["start_ns"])

    def test_outer_mode_does_not_patch_underlying_authentication_functions(self):
        capture = OuterDiagnosticCapture()
        original_decode, original_seal = pipeline_v2.reconstruct, Sender.seal_window
        with diagnostic_instrumentation(MODES[2], capture):
            self.assertIs(pipeline_v2.reconstruct, original_decode)
            self.assertIs(Sender.seal_window, original_seal)

    def test_nested_patches_restore_after_failure(self):
        original_decode, original_seal = pipeline_v2.reconstruct, Sender.seal_window
        capture = NestedDiagnosticCapture()
        with self.assertRaises(ZeroDivisionError):
            with diagnostic_instrumentation(MODES[0], capture):
                capture.measure("outer", lambda: 1 / 0)
        self.assertIs(pipeline_v2.reconstruct, original_decode)
        self.assertIs(Sender.seal_window, original_seal)

    def test_runtime_snapshot_is_coarse_not_allocation_bytes_or_peak_memory(self):
        result = runtime_snapshot()
        self.assertEqual(len(result["gc_stats"]), 3)
        self.assertEqual(len(result["gc_counts"]), 3)
        self.assertTrue(result["allocated_blocks_are_not_bytes_or_total_native_memory"])
        self.assertNotIn("allocation_bytes", result)
        self.assertNotIn("native_memory_peak", result)

    def test_housekeeping_refused_inside_root(self):
        capture = OuterDiagnosticCapture()
        retention = TraceRetention(MODES[1])
        for action in (lambda: runtime_snapshot(capture), lambda: retention.snapshot(capture),
                       lambda: retention.release(capture)):
            with self.assertRaises(RuntimeError):
                capture.measure("outer", action)

    def test_deferred_gc_restores_policy_and_accounts_cleanup(self):
        before, callbacks = gc.get_threshold(), tuple(gc.callbacks)
        with diagnostic_gc_policy(MODES[3]) as evidence:
            self.assertFalse(gc.isenabled())
            self.assertEqual(gc.get_threshold(), before)
        self.assertTrue(evidence["policy_consistent"])
        self.assertTrue(gc.isenabled())
        self.assertEqual(gc.get_threshold(), before)
        self.assertEqual(tuple(gc.callbacks), callbacks)
        self.assertTrue(evidence["cleanup"]["outside_root_timers"])
        self.assertEqual(evidence["cleanup"]["generation"], 2)
        self.assertGreaterEqual(evidence["cleanup"]["wall_ns"], 0)
        self.assertTrue(evidence["cleanup"]["includes_full_collection_and_builtin_free_list_effects"])

    def test_enabled_reference_does_not_force_collection_on_exit(self):
        with patch("puf_snn.pipeline_diagnostics.gc.collect") as collect:
            with diagnostic_gc_policy(MODES[0]) as evidence:
                self.assertTrue(gc.isenabled())
            collect.assert_not_called()
        self.assertIsNone(evidence["cleanup"])
        self.assertTrue(evidence["policy_consistent"])

    def test_deferred_gc_restores_even_on_action_exception(self):
        before = gc.get_threshold()
        with self.assertRaises(LookupError):
            with diagnostic_gc_policy(MODES[3]) as evidence:
                raise LookupError("original failure")
        self.assertTrue(gc.isenabled())
        self.assertEqual(gc.get_threshold(), before)
        self.assertIsNotNone(evidence["cleanup"])

    def test_policy_restores_even_if_after_work_snapshot_fails(self):
        snapshot = runtime_snapshot()
        with patch("puf_snn.pipeline_diagnostics.runtime_snapshot", side_effect=[snapshot, ValueError("snapshot")]):
            with self.assertRaises(ValueError):
                with diagnostic_gc_policy(MODES[3]):
                    self.assertFalse(gc.isenabled())
        self.assertTrue(gc.isenabled())

    def test_disabled_gc_on_entry_refused_not_silently_changed(self):
        try:
            gc.disable()
            with self.assertRaises(ValueError):
                with diagnostic_gc_policy(MODES[0]):
                    pass
            self.assertFalse(gc.isenabled())
        finally:
            gc.enable()

    def test_threshold_change_detected_and_original_thresholds_restored(self):
        before = gc.get_threshold()
        with diagnostic_gc_policy(MODES[0]) as evidence:
            gc.set_threshold(before[0] + 10, before[1], before[2])
        self.assertFalse(evidence["policy_consistent"])
        self.assertEqual(gc.get_threshold(), before)

    def test_explicit_collection_still_works_when_automatic_gc_deferred(self):
        capture = OuterDiagnosticCapture()
        with diagnostic_gc_policy(MODES[3], capture):
            capture.measure("outer", lambda: gc.collect(0))
            self.assertTrue(capture.last_trace["gc_events"])
            self.assertFalse(gc.isenabled())

    def test_retention_changes_ownership_not_trace_contents_or_counts(self):
        capture = OuterDiagnosticCapture()
        capture.measure("outer", lambda: None)
        row = capture.last_trace
        original = json.dumps(row, sort_keys=True)
        retained, streamed = TraceRetention(MODES[0]), TraceRetention(MODES[1])
        for _ in range(5):
            retained.record(row, capture)
            streamed.record(row, capture)
        self.assertEqual(retained.retained_trace_count, 5)
        self.assertEqual(streamed.retained_trace_count, 0)
        self.assertEqual(retained.snapshot()["observed_trace_count"], 5)
        self.assertEqual(streamed.snapshot()["observed_span_count"], 5)
        self.assertIs(retained._traces[0], row)
        self.assertEqual(json.dumps(row, sort_keys=True), original)
        self.assertEqual(retained.release()["retained_trace_count"], 5)
        self.assertEqual(retained.retained_span_count, 0)
        self.assertEqual(retained.snapshot()["observed_trace_count"], 5)

    def test_retention_record_refused_inside_timer_or_without_root(self):
        capture, retention = OuterDiagnosticCapture(), TraceRetention(MODES[0])
        with self.assertRaises(ValueError):
            retention.record({"path": "outer", "spans": []})
        with self.assertRaises(RuntimeError):
            capture.measure("outer", lambda: retention.record({"path": "outer", "spans": []}, capture))

    def fixture_pipeline(self, capture, **kwargs):
        return fixtures.PipelineV2Tests().peers(
            prepare_callback=capture.wrap("prepare_both_model_inputs", fixtures.prepare),
            motion_callback=capture.wrap("motion_consumer", lambda _: "nod"),
            anomaly_callback=capture.wrap("anomaly_consumer", lambda _: {"score": .1, "flag": False}), **kwargs)[0]

    def test_all_modes_preserve_real_one_read_and_accepted_rejected_state_controls(self):
        for mode in MODES:
            with self.subTest(mode=mode.name):
                capture = make_diagnostic_capture(mode)
                pipeline = self.fixture_pipeline(capture)
                rows, emitted_inside_timer = [], []
                read = Mock(return_value=fixtures.response_with_flips({2, 8, 19}))
                retention = TraceRetention(mode)
                def emit(row):
                    emitted_inside_timer.append(capture.active)
                    rows.append(row)
                    retention.record(row, capture)
                with diagnostic_gc_policy(mode, capture) as policy, diagnostic_instrumentation(mode, capture):
                    result = run_timed_attempt(pipeline, fixtures.source_record(), read,
                                               f"diagnostic-fixture-{mode.name}", capture, emit)
                read.assert_called_once_with()
                self.assertEqual(result.decision, "accept")
                self.assertTrue(policy["policy_consistent"])
                self.assertEqual(pipeline.calls, ModelCallCounts(4, 4, 4))
                self.assertEqual(len(rows), 8)
                self.assertEqual(emitted_inside_timer, [False] * 8)
                self.assertEqual(len(pipeline.consumed_event_ids), 4)
                for row in rows:
                    if row["decision"] == "reject":
                        self.assertFalse(any(row["model_calls"].values()))
                if not mode.nested_spans:
                    self.assertTrue(all(len(row["spans"]) == 1 for row in rows))
                else:
                    self.assertIn("independent_credential_verification", {s["stage"] for s in rows[0]["spans"]})
                self.assertEqual(retention.retained_trace_count, 8 if mode.retain_full_traces else 0)

    def test_all_modes_keep_admission_refusal_with_no_retry_or_model_calls(self):
        for mode in MODES:
            with self.subTest(mode=mode.name):
                capture = make_diagnostic_capture(mode)
                pipeline = self.fixture_pipeline(capture, missing_record=True)
                rows, read = [], Mock(return_value=fixtures.REFERENCE)
                with diagnostic_gc_policy(mode, capture), diagnostic_instrumentation(mode, capture):
                    result = run_timed_attempt(pipeline, fixtures.source_record(), read,
                                               f"diagnostic-refusal-{mode.name}", capture, rows.append)
                read.assert_called_once_with()
                self.assertEqual(result.decision, "reject")
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["read_count"], 1)
                self.assertEqual(pipeline.calls, ModelCallCounts())
                self.assertEqual(rows[0]["sender_kdf_ns"], [])
                self.assertEqual(rows[0]["verifier_kdf_ns"], [])


if __name__ == "__main__":
    unittest.main()
