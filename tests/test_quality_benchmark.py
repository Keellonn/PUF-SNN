"""Experiment protocol/reconciliation tests; fixtures are not timing results."""

from copy import deepcopy
from dataclasses import asdict, replace
import gc
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

import test_pipeline_v2 as fixtures
from auth.support import window
from puf_snn.auth import binary_window
from puf_snn.pipeline_timing import ACCEPTED_PATHS, REJECTED_PATHS, TimingCapture, instrument_pipeline, run_timed_attempt
from puf_snn.quality_benchmark import (
    BASELINE_HASHES, PRIMARY, PublicLedger, array_fingerprint, build_jobs, cleanup, fixed_config,
    normal_gc_conditions, paired_rows, process_memory, select_sources, sustained_burst, validate_config, validate_rows,
    wire_fingerprint,
)
from puf_snn.quality_dyadic import quality_validator_mode
from scripts import benchmark_week6_quality as runner


def cohort():
    return [dict(split=split, device_id=f"device-{device}", label=label,
                 window_id=f"{split}-{device}-{label}-{index:02}")
            for split in ("test", "validation") for device in range(6)
            for label in ("nod", "shake", "left", "right", "still") for index in range(20)]


def simple_row(condition=PRIMARY[0]["name"], phase="measured", index=0, path="fresh_to_first_window"):
    accepted = path in ACCEPTED_PATHS
    calls = {name: int(accepted) for name in ("preprocessing", "motion", "anomaly")}
    row = dict(condition=condition, phase=phase, attempt_index=index, path=path,
        decision="accept" if accepted else "reject", reason="accepted" if accepted else "invalid_tag",
        stage="fixture", mode="reference_fraction", block=0, source_window_id=f"{phase}-{index}",
        device_id="fixture", source_split="validation" if phase != "measured" else "test",
        selected_bit_error_count=3, model_calls=calls, elapsed_ns=100, thread_cpu_ns=80,
        gc_events=[], spans=[dict(id=0, parent_id=None, stage=path, start_ns=0,
                                 wall_ns=100, thread_cpu_ns=80, exception=False)],
        public_inference=dict(model_inputs=[{}] if accepted else [], motion_outputs=["nod"] if accepted else [],
                              anomaly_outputs=[dict(score=.1, flag=False)] if accepted else [], sender_payload_session_neutral_sha256=[]))
    if path == "fresh_to_first_window":
        row.update(read_count=1, admission=dict(decision="accept", stage="active_session", reason="accepted"))
    return row


class QualityBenchmarkTests(unittest.TestCase):
    def test_json_configuration_matches_fixed_protocol(self):
        config_path = Path(runner.__file__).resolve().parents[3] / "configs/week6_quality_benchmark.json"
        validate_config(json.loads(config_path.read_text(encoding="utf-8")))
        self.assertEqual(fixed_config()["blocks"] * 2 * 3 * 150, 1800)

    def test_config_copies_do_not_mutate_protocol_constants(self):
        first = fixed_config()
        first["conditions"][0]["motion"] = "changed"
        first["reference_source_hashes"].clear()
        self.assertEqual(len(fixed_config()["reference_source_hashes"]), 3)
        self.assertNotEqual(fixed_config()["conditions"][0]["motion"], "changed")

    def test_all_pinned_reference_hashes_are_sha256(self):
        for relative, digest in BASELINE_HASHES.items():
            self.assertEqual(len(digest), 64)
            self.assertTrue(all(c in "0123456789abcdef" for c in digest))
            self.assertNotIn("..", relative)

    def test_sample_model_threshold_and_gc_tuning_are_refused(self):
        for key, value in (("blocks", 3), ("native_threads", True), ("gc_enabled", False),
                           ("measured_attempts_per_condition", 600), ("response_reads_per_admission", 3)):
            config = fixed_config()
            config[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_config(config)
        config = fixed_config()
        config["conditions"][2]["motion"] = "snn_32_seed_17"
        with self.assertRaises(ValueError):
            validate_config(config)

    def test_mode_positions_balanced_and_model_order_same_within_pair(self):
        jobs = build_jobs(fixed_config())
        self.assertEqual([j["mode"] for j in jobs], ["reference_fraction", "candidate_dyadic",
                                                  "candidate_dyadic", "reference_fraction"])
        self.assertEqual(jobs[0]["condition_order"], jobs[1]["condition_order"])
        self.assertEqual(jobs[2]["condition_order"], jobs[3]["condition_order"])
        self.assertEqual(jobs[0]["condition_order"], jobs[2]["condition_order"][::-1])

    def test_source_selection_fixed_balanced_disjoint_and_order_independent(self):
        a = select_sources(cohort())
        b = select_sources(cohort()[::-1])
        self.assertEqual(a, b)
        self.assertEqual([len(rows) for rows in a], [120, 30, 64])
        self.assertFalse({r["window_id"] for r in a[0]} & {r["window_id"] for r in a[1]})
        self.assertEqual({r["device_id"] for r in a[2]}, {a[0][-1]["device_id"]})
        self.assertEqual(len({r["window_id"] for r in a[2]}), 64)

    def test_missing_source_is_not_silently_replaced(self):
        with self.assertRaises(ValueError):
            select_sources(cohort()[:-1])

    def test_normal_gc_check_does_not_change_thresholds_or_policy(self):
        callbacks, thresholds, enabled = tuple(gc.callbacks), gc.get_threshold(), gc.isenabled()
        with patch("gc.get_threshold", return_value=(2000, 10, 10)):
            self.assertTrue(normal_gc_conditions(fixed_config())["gc_enabled"])
        self.assertEqual((tuple(gc.callbacks), gc.get_threshold(), gc.isenabled()), (callbacks, thresholds, enabled))

    def test_disabled_gc_or_different_thresholds_refused(self):
        with patch("gc.isenabled", return_value=False), self.assertRaises(ValueError):
            normal_gc_conditions(fixed_config())
        with patch("gc.get_threshold", return_value=(700, 10, 10)), self.assertRaises(ValueError):
            normal_gc_conditions(fixed_config())

    def test_array_hash_exact_values_shape_and_finiteness(self):
        array = np.zeros((120, 7))
        before = array_fingerprint(array, (120, 7))
        array[1, 2] = 1e-20
        self.assertNotEqual(array_fingerprint(array, (120, 7)), before)
        with self.assertRaises(ValueError):
            array_fingerprint(array, (48,))
        array[0, 0] = float("nan")
        with self.assertRaises(ValueError):
            array_fingerprint(array, (120, 7))

    def test_ledger_hashing_only_outside_root_and_no_wire_plaintext(self):
        capture = TimingCapture()
        ledger = PublicLedger(capture)
        public_bytes = binary_window.encode_window(window(bytes(range(16))))
        def action():
            ledger.observe("wire", lambda: public_bytes)()
            ledger.observe("preprocessing", lambda: (np.zeros((120, 7)), np.zeros(48)))()
            ledger.observe("motion", lambda: {"model": "nod"})()
            ledger.observe("anomaly", lambda: {"model": dict(score=.1, flag=False)})()
            with self.assertRaises(RuntimeError):
                ledger.finish(dict(preprocessing=1, motion=1, anomaly=1))
        capture.measure("fixture", action)
        result = ledger.finish(dict(preprocessing=1, motion=1, anomaly=1))
        self.assertEqual(result["sender_payload_session_neutral_sha256"], [wire_fingerprint(public_bytes)])
        self.assertNotIn(public_bytes.hex(), json.dumps(result))
        self.assertFalse(any(ledger.pending.values()))

    def test_ledger_rejects_missing_callbacks_or_nonfinite_output(self):
        ledger = PublicLedger(TimingCapture())
        with self.assertRaises(ValueError):
            ledger.finish(dict(preprocessing=1, motion=0, anomaly=0))
        ledger.pending["anomaly"].append(float("nan"))
        with self.assertRaises(ValueError):
            ledger.finish(dict(preprocessing=0, motion=0, anomaly=1))

    def test_ledger_ignores_outside_timer_operations(self):
        ledger = PublicLedger(TimingCapture())
        ledger.observe("wire", lambda: b"not-root")()
        self.assertEqual(ledger.finish(dict(preprocessing=0, motion=0, anomaly=0))["sender_payload_session_neutral_sha256"], [])

    def test_wire_pairing_neutralizes_only_fresh_session_entropy(self):
        value = window(bytes(range(16)))
        a = binary_window.encode_window(value)
        b = binary_window.encode_window(replace(value, session_id=bytes(16)))
        self.assertNotEqual(a, b)
        self.assertEqual(wire_fingerprint(a), wire_fingerprint(b))
        for changed in (replace(value, sequence_number=value.sequence_number+1), replace(value, window_id="different"),
                        replace(value, device_id="different")):
            self.assertNotEqual(wire_fingerprint(a), wire_fingerprint(binary_window.encode_window(changed)))

    def test_actual_fixture_protocol_matches_modes_and_rejections_release_nothing(self):
        rows = []
        for mode in ("reference_fraction", "candidate_dyadic"):
            capture, kept = TimingCapture(), []
            ledger = PublicLedger(capture)
            pipeline = fixtures.PipelineV2Tests().peers(
                prepare_callback=ledger.observe("preprocessing", fixtures.prepare),
                motion_callback=ledger.observe("motion", lambda _: {"fixture": "nod"}),
                anomaly_callback=ledger.observe("anomaly", lambda _: {"fixture": dict(score=.1, flag=False)}))[0]
            source = fixtures.source_record()
            def emit(row):
                row.update(condition=PRIMARY[0]["name"], phase="measured", attempt_index=0,
                    source_window_id=source["window_id"], device_id=source["device_id"], source_split="test",
                    selected_bit_error_count=3, mode=mode, block=0,
                    public_inference=ledger.finish(row["model_calls"]))
                kept.append(deepcopy(row))
            with quality_validator_mode(mode), ledger.observe_sender(), instrument_pipeline(capture):
                run_timed_attempt(pipeline, source, lambda: fixtures.response_with_flips({2, 8, 19}),
                                  f"fixture-{mode}", capture, emit)
            self.assertEqual(len(kept), 8)
            self.assertEqual(pipeline.calls.motion, 4)
            for row in kept:
                if row["decision"] == "reject":
                    self.assertEqual(row["public_inference"]["motion_outputs"], [])
            rows.append(kept)
            pipeline.verifier.close_all_sessions()
        self.assertEqual(len(paired_rows(*rows)), 8)

    def test_sustained_fixture_reuses_session_and_advances_state(self):
        capture, kept = TimingCapture(), []
        pipeline = fixtures.PipelineV2Tests().active()[0]
        before = asdict(pipeline.calls)
        sources = [fixtures.source_record() for _ in range(2)]
        for i, source in enumerate(sources):
            source["window_id"] = f"burst-{i}"
        def emit(row, source, index):
            self.assertFalse(capture.active)
            kept.append((deepcopy(row), source["window_id"], index))
        result = sustained_burst(pipeline, sources, capture, emit, count=2)
        self.assertEqual(result["completed_windows"], 2)
        self.assertEqual(result["source_windows_distinct"], 2)
        self.assertEqual(pipeline.calls.motion, before["motion"] + 2)
        self.assertEqual(kept[-1][0]["last_accepted_after"], 1)
        self.assertFalse(result["admission_included"])
        pipeline.verifier.close_all_sessions()

    def test_burst_count_mismatch_rejected(self):
        pipeline = fixtures.PipelineV2Tests().active()[0]
        with self.assertRaises(ValueError):
            sustained_burst(pipeline, [], TimingCapture(), lambda *args: None)
        pipeline.verifier.close_all_sessions()

    def test_paired_deltas_signed_not_percentile_subtraction(self):
        a = simple_row()
        b = deepcopy(a)
        b["elapsed_ns"] = 50
        row = paired_rows([a], [b])[0]
        self.assertEqual(row["p50_delta_ms"], -50 / 1e6)
        self.assertEqual(row["direction"], "candidate_minus_reference")

    def test_input_prediction_noise_state_mismatch_each_blocks_completion(self):
        a = simple_row()
        for name, value in (("selected_bit_error_count", 4), ("model_calls", {}), ("source_window_id", "different")):
            b = deepcopy(a)
            b[name] = value
            with self.subTest(name=name), self.assertRaises(ValueError):
                paired_rows([a], [b])
        b = deepcopy(a)
        b["public_inference"]["anomaly_outputs"][0]["score"] = .10000001
        with self.assertRaises(ValueError):
            paired_rows([a], [b])

    def test_missing_or_duplicate_paired_roots_refused(self):
        a = simple_row()
        with self.assertRaises(ValueError):
            paired_rows([a], [])
        with self.assertRaises(ValueError):
            paired_rows([a, a], [a])

    def complete_rows(self):
        rows = []
        for condition in PRIMARY:
            name = condition["name"]
            for phase, indices in (("condition_first_use", [0]), ("warmup", range(1, 30)), ("measured", range(120))):
                for index in indices:
                    for path in ACCEPTED_PATHS | REJECTED_PATHS:
                        row = simple_row(name, phase, index, path)
                        # The last predeclared admission fails: no burst is substituted.
                        if phase == "measured" and index == 119:
                            if path != "fresh_to_first_window":
                                continue
                            row.update(decision="reject", reason="failed_reconstruction", stage="reconstruction",
                                model_calls={key: 0 for key in row["model_calls"]},
                                public_inference=dict(model_inputs=[], motion_outputs=[], anomaly_outputs=[], sender_payload_session_neutral_sha256=[]),
                                admission=dict(decision="reject", stage="reconstruction", reason="failed_reconstruction"))
                        rows.append(row)
        return rows

    def test_all_natural_admission_failures_retained_and_no_burst_retry(self):
        rows = self.complete_rows()
        result = validate_rows(rows, build_jobs(fixed_config())[0], fixed_config())
        self.assertEqual(result["fresh_attempt_count"], 450)
        self.assertEqual(result["sustained_window_count"], 0)
        self.assertEqual(result["trace_count"], 3 * (149 * 8 + 1))

    def test_unplanned_successful_burst_after_failed_final_admission_refused(self):
        rows = self.complete_rows()
        extra = simple_row(phase="sustained", path="post_window_recurring")
        extra.update(source_split="test", last_accepted_before=3, last_accepted_after=4)
        rows.append(extra)
        with self.assertRaises(ValueError):
            validate_rows(rows, build_jobs(fixed_config())[0], fixed_config())

    def test_duplicate_wrong_split_and_rejected_callback_refused(self):
        for alteration in ("duplicate", "split", "calls"):
            rows = self.complete_rows()
            if alteration == "duplicate":
                rows.append(deepcopy(rows[0]))
            elif alteration == "split":
                rows[0]["source_split"] = "train"
            else:
                row = next(r for r in rows if r["decision"] == "reject")
                row["model_calls"]["motion"] = 1
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                validate_rows(rows, build_jobs(fixed_config())[0], fixed_config())

    def test_cleanup_outside_roots_keeps_normal_gc_and_accounts_cost(self):
        capture, ledger = TimingCapture(), PublicLedger(TimingCapture())
        callbacks, thresholds = tuple(gc.callbacks), gc.get_threshold()
        with patch("gc.collect", return_value=2) as collect:
            result = cleanup(capture, ledger)
        collect.assert_called_once_with(2)
        self.assertTrue(result["cleanup"]["outside_window_timers"])
        self.assertTrue(result["cleanup"]["automatic_collection_was_not_deferred"])
        self.assertGreaterEqual(result["cleanup"]["wall_ns"], 0)
        self.assertEqual((tuple(gc.callbacks), gc.get_threshold()), (callbacks, thresholds))

    def test_cleanup_with_pending_root_or_ledger_refused(self):
        capture = TimingCapture()
        ledger = PublicLedger(capture)
        ledger.pending["wire"].append(b"fixture")
        with self.assertRaises(ValueError):
            cleanup(capture, ledger)

    def test_process_memory_is_numeric_or_explicit_unavailable(self):
        result = process_memory()
        if result["status"] == "collected":
            self.assertGreater(result["working_set_bytes"], 0)
            self.assertGreaterEqual(result["peak_working_set_bytes"], result["working_set_bytes"])
        else:
            self.assertTrue(result["status"].startswith("unavailable"))

    def test_unconfirmed_power_blocks_controller_before_any_loading(self):
        with patch.object(runner, "read_json", return_value=fixed_config()), \
                patch.object(runner, "load_frozen_bundle") as load, self.assertRaises(ValueError):
            runner.controller(Path("."), Path("config"), Path("output"), "unconfirmed", "heavy_apps_closed")
        load.assert_not_called()

    def test_report_keeps_boundaries_unmet_historical_target_and_no_default_change(self):
        text = runner.report_text([], [])
        for phrase in ("default v2 path is unchanged", "Never add stage p95s", "TWO-SECOND acquisition",
                       "unmet", "not total event-to-decision", "NOT recurring-only throughput"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
