"""Fixed experiment/reconciliation tests; fixtures are not timing results."""

from collections import Counter
from copy import deepcopy
import gc
import io
from itertools import permutations
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import test_pipeline_v2 as fixtures
import test_pipeline_timing as timing_fixtures
from puf_snn.outlier_experiment import (
    CONTRASTS, MODE_ORDERS, build_jobs, checked_completion, checked_historical_inputs,
    functional_signature, iter_historical_traces, new_output_path, paired_comparison,
    read_job_traces, recheck_frozen_inputs, require_source_unchanged, select_experiment_sources,
    signed_delta_statistics, validate_experiment_config, validate_worker_traces,
)
from puf_snn.pipeline_diagnostics import TraceRetention, diagnostic_instrumentation, diagnostic_mode, make_diagnostic_capture
from puf_snn.pipeline_v2 import ModelCallCounts
from puf_snn.frozen_pipeline import sha256
from scripts import run_week6_outlier_experiment as runner


def settings():
    return json.loads((Path(runner.__file__).resolve().parents[3] / "configs/week6_outlier_experiment.json").read_text())


def row(elapsed=100):
    return dict(condition="condition", phase="measured", attempt_index=0, path="post_window_recurring",
                mode="nested_stream_gc_on", block=0, observer="nested",
                elapsed_ns=elapsed, thread_cpu_ns=elapsed, clock_start_ns=1000, clock_end_ns=1000+elapsed,
                process_id=1, native_thread_id=2, stage="inference", decision="accept", reason="accepted",
                source_window_id="source", device_id="device", source_split="test", selected_bit_error_count=1,
                model_calls={"preprocessing": 1, "motion": 1, "anomaly": 1}, sequence_number=1,
                last_accepted_before=0, last_accepted_after=1,
                gc_events=[], gc_spanning_trace_end=[],
                spans=[dict(id=0, parent_id=None, stage="post_window_recurring", start_ns=0,
                            wall_ns=elapsed, thread_cpu_ns=elapsed, exception=False)])


class OutlierExperimentTests(unittest.TestCase):
    def test_fixed_configuration_matches_all_six_conditions_and_four_modes(self):
        config = settings()
        validate_experiment_config(config)
        self.assertEqual(len(config["conditions"]), 6)
        self.assertEqual(len(config["modes"]), 4)
        self.assertEqual(config["blocks"] * 4 * 6 * (60 + 30), 8640)

    def test_changed_counts_models_gc_and_extra_fields_refused(self):
        for key, value in (("blocks", True), ("batch_size", True), ("gc_thresholds", [100, 10, 10]),
                           ("full_gc_probes_per_heap", 1), ("measured_attempts_per_condition", 600),
                           ("read_domain", "altered"), ("extra", 1)):
            config = settings()
            config[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_experiment_config(config)
        config = settings()
        config["conditions"][0]["anomaly"] = "anomaly_random_forest_seed6027"
        with self.assertRaises(ValueError):
            validate_experiment_config(config)

    def test_job_plan_has_fresh_mode_workers_and_separate_heap_workers(self):
        jobs = build_jobs(settings())
        self.assertEqual(len(jobs), 20)
        self.assertEqual(len({j["job_id"] for j in jobs}), 20)
        self.assertEqual([j["retained_trace_count"] for j in jobs if j["kind"] != "timing"],
                         [0, 5000, 15000, 29718])

    def test_mode_order_balances_positions_and_every_directed_predecessor(self):
        for position in range(4):
            self.assertEqual({order[position] for order in MODE_ORDERS}, set(range(4)))
        transitions = Counter((a, b) for order in MODE_ORDERS for a, b in zip(order, order[1:]))
        self.assertEqual(set(transitions), set(permutations(range(4), 2)))
        self.assertEqual(set(transitions.values()), {1})

    def test_each_job_keeps_all_models_and_rotates_without_selection(self):
        expected = {c["name"] for c in settings()["conditions"]}
        jobs = [j for j in build_jobs(settings()) if j["kind"] == "timing"]
        self.assertEqual(len({tuple(c["name"] for c in j["condition_order"]) for j in jobs}), 6)
        self.assertTrue(all({c["name"] for c in j["condition_order"]} == expected for j in jobs))

    def test_source_selection_is_group_complete_and_outcome_independent(self):
        records = timing_fixtures.PipelineTimingTests().cohort()
        records.reverse()
        original = deepcopy(records)
        test, warmup = select_experiment_sources(records)
        self.assertEqual(records, original)
        self.assertEqual(len(test), 60)
        self.assertEqual(len(warmup), 30)
        self.assertEqual(set(Counter((r["device_id"], r["label"]) for r in test).values()), {2})
        self.assertEqual(set(Counter((r["device_id"], r["label"]) for r in warmup).values()), {1})
        self.assertFalse({r["window_id"] for r in test} & {r["window_id"] for r in warmup})
        self.assertTrue(all(r["window_id"].endswith(("-00", "-01")) for r in test))

    def test_missing_complete_source_inventory_refused(self):
        with self.assertRaises(ValueError):
            select_experiment_sources(timing_fixtures.PipelineTimingTests().cohort()[:-1])

    def test_existing_outside_or_scope_root_outputs_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scope = root / "results/week-6/keegan"
            scope.mkdir(parents=True)
            for path in (scope, root / "outside", scope / ".."):
                with self.assertRaises(ValueError):
                    new_output_path(root, path)
            existing = scope / "existing"
            existing.mkdir()
            with self.assertRaises(ValueError):
                new_output_path(root, existing)
            self.assertEqual(new_output_path(root, scope / "new"), scope / "new")

    def test_source_guard_refuses_changed_head_and_unrelated_untracked_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root, commit = Path(temporary), "fixed"
            output = root / "results/week-6/keegan/new"
            with patch("subprocess.check_output", return_value="different\n"):
                with self.assertRaises(ValueError):
                    require_source_unchanged(root, commit, output)
            with patch("subprocess.run"), patch("subprocess.check_output", side_effect=["fixed\n", "outside.txt\0"]):
                with self.assertRaises(ValueError):
                    require_source_unchanged(root, commit, output)

    def test_source_guard_allows_only_current_output_untracked_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "results/week-6/keegan/new"
            with patch("subprocess.run") as command, patch("subprocess.check_output", side_effect=["fixed\n", "results/week-6/keegan/new/control.json\0"]):
                require_source_unchanged(root, "fixed", output)
            self.assertEqual(command.call_count, 2)
            self.assertTrue(all(c.kwargs["check"] for c in command.call_args_list))

    def historical_fixture(self, root):
        directory = root / "historical"
        directory.mkdir()
        runner.write_json(directory / "payload.json", {"fixture": True})
        runner.write_json(directory / "manifest.json", {"reconciliation": {"trace_count": 29718},
                          "artifacts": {"payload.json": sha256(directory / "payload.json")}})
        digest = sha256(directory / "manifest.json")
        runner.write_json(directory / "COMPLETE", {"manifest_sha256": digest, "trace_count": 29718})
        return directory, dict(historical_directory="historical", historical_manifest_sha256=digest)

    def test_historical_input_checks_bytes_without_retaining_trees(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory, config = self.historical_fixture(root)
            found, _, checked = checked_historical_inputs(root, config)
            self.assertEqual(found, directory)
            self.assertEqual(set(checked), {"COMPLETE", "manifest.json", "payload.json"})
            (directory / "payload.json").write_text("changed", encoding="utf-8")
            with self.assertRaises(ValueError):
                checked_historical_inputs(root, config)

    def test_historical_incomplete_or_marker_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory, config = self.historical_fixture(root)
            (directory / "INCOMPLETE").touch()
            with self.assertRaises(ValueError):
                checked_historical_inputs(root, config)
            (directory / "INCOMPLETE").unlink()
            (directory / "COMPLETE").write_text(json.dumps({"manifest_sha256": "wrong", "trace_count": 29718}))
            with self.assertRaises(ValueError):
                checked_historical_inputs(root, config)

    def test_frozen_post_checks_verify_bytes_without_deserialization(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "data").mkdir()
            (root / "models").mkdir()
            (root / "data/source.jsonl").write_text("NONSECRET DATA\n", encoding="utf-8")
            (root / "models/checkpoint.pt").write_text("NONSECRET CHECKPOINT\n", encoding="utf-8")
            frozen = dict(input_path="data/source.jsonl", input_sha256=sha256(root / "data/source.jsonl"),
                          bundles={"snn32": {"directory": "models"}})
            hashes = {"snn32/checkpoint.pt": sha256(root / "models/checkpoint.pt")}
            with patch("joblib.load") as deserialize:
                recheck_frozen_inputs(root, frozen, hashes)
                deserialize.assert_not_called()
            (root / "models/checkpoint.pt").write_text("changed", encoding="utf-8")
            with self.assertRaises(ValueError):
                recheck_frozen_inputs(root, frozen, hashes)

    def test_heap_prefix_zero_reads_no_metadata_and_short_prefix_refused(self):
        with patch.object(runner, "iter_historical_traces") as source:
            self.assertEqual(runner.load_heap_prefix(Path("unused"), [], 0), [])
            source.assert_not_called()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "timings-condition.jsonl").write_text(json.dumps(row()) + "\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                runner.load_heap_prefix(directory, [dict(name="condition")], 2)

    def test_historical_stream_checks_condition_and_root_exception(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            trace = row()
            path = directory / "timings-condition.jsonl"
            path.write_text(json.dumps(trace) + "\n", encoding="utf-8")
            self.assertEqual(len(list(iter_historical_traces(directory, [dict(name="condition")]))), 1)
            for changed in (dict(trace, condition="wrong"), deepcopy(trace)):
                if changed["condition"] == "condition":
                    changed["spans"][0]["exception"] = True
                path.write_text(json.dumps(changed) + "\n", encoding="utf-8")
                with self.assertRaises(ValueError):
                    list(iter_historical_traces(directory, [dict(name="condition")]))

    def test_completion_marker_and_artifact_hashes_and_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "job"
            runner.begin_directory(directory)
            runner.write_json(directory / "evidence.json", {"nonsecret": True})
            runner.complete_directory(directory, dict(job={"job_id": "fixture"}, source_commit="fixed"))
            checked_completion(directory, expected_job={"job_id": "fixture"}, expected_commit="fixed")
            with self.assertRaises(ValueError):
                checked_completion(directory, expected_commit="wrong")
            (directory / "extra").touch()
            with self.assertRaises(ValueError):
                checked_completion(directory)
            (directory / "extra").unlink()
            (directory / "evidence.json").write_text("changed", encoding="utf-8")
            with self.assertRaises(ValueError):
                checked_completion(directory)

    def test_completion_never_overwrites_marker_and_exact_lf(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "job"
            runner.begin_directory(directory)
            runner.complete_directory(directory, dict(job={}, source_commit="fixed"))
            for path in directory.iterdir():
                self.assertNotIn(b"\r", path.read_bytes())
            with self.assertRaises(ValueError):
                runner.complete_directory(directory, {})
            with self.assertRaises(FileExistsError):
                runner.begin_directory(directory)

    def test_signed_deltas_preserve_negative_values_not_percentile_subtraction(self):
        result = signed_delta_statistics([-1000000, 0, 1000000])
        self.assertEqual(result["mean_delta_ms"], 0)
        self.assertEqual(result["min_delta_ms"], -1)
        self.assertAlmostEqual(result["p95_delta_ms"], .9)
        for values in ([], [True], [1.2]):
            with self.assertRaises(ValueError):
                signed_delta_statistics(values)

    def test_pairing_requires_matching_sources_noise_sequences_and_callbacks(self):
        left, right = row(100), row(60)
        result = paired_comparison([left], [right], "test", 0)
        self.assertEqual(result[0]["p50_delta_ms"], -.00004)
        self.assertEqual(result[0]["direction"], "right_minus_left")
        for key, value in (("selected_bit_error_count", 2), ("decision", "reject"), ("source_window_id", "different"),
                           ("last_accepted_after", 99), ("model_calls", {"motion": 0})):
            with self.subTest(key=key), self.assertRaises(ValueError):
                paired_comparison([left], [dict(right, **{key: value})], "test", 0)

    def test_pairing_rejects_duplicates_and_missing_refusal(self):
        with self.assertRaises(ValueError):
            paired_comparison([row(), row()], [row()], "test", 0)
        with self.assertRaises(ValueError):
            paired_comparison([row()], [], "test", 0)

    def test_pairing_separates_first_use_warmup_and_rejection_groups(self):
        rows = [row(), dict(row(), phase="warmup"), dict(row(), phase="condition_first_use"),
                dict(row(), path="bad_tag_receiver", decision="reject", reason="invalid_tag", model_calls={"motion": 0})]
        self.assertEqual(len(paired_comparison(rows, rows, "test", 0)), 4)

    def test_pairing_ignores_volatile_event_ids_and_observer_timing(self):
        left, right = row(), row(50)
        left["event_id"], right["event_id"] = "left", "right"
        right["gc_events"] = [dict(start_ns=1, end_ns=2)]
        right["observer"] = "outer_only"
        self.assertEqual(functional_signature(left), functional_signature(right))
        paired_comparison([left], [right], "test", 0)

    def test_worker_traces_reconcile_and_reject_observer_clock_or_mode_drift(self):
        traces, conditions = timing_fixtures.PipelineTimingTests().synthetic_reconciliation()
        job = dict(mode="nested_stream_gc_on", block=0, condition_order=conditions)
        config = dict(measured_attempts_per_condition=1, warmup_attempts_per_condition=2)
        for trace in traces:
            trace.update(mode=job["mode"], block=0, observer="nested", process_id=1, native_thread_id=2,
                         clock_start_ns=1000, clock_end_ns=1000 + trace["elapsed_ns"])
        self.assertEqual(validate_worker_traces(traces, job, config)["fresh_attempt_count"], 3)
        for key, value in (("mode", "outer_stream_gc_on"), ("block", 4), ("observer", "outer_only"),
                           ("clock_end_ns", 0), ("native_thread_id", 0)):
            changed = deepcopy(traces)
            changed[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_worker_traces(changed, job, config)

    def test_lightweight_worker_refuses_hidden_nested_span(self):
        trace = row()
        trace.update(mode="outer_stream_gc_on", observer="outer_only")
        trace["spans"].append(dict(id=1, parent_id=0, stage="unexpected", start_ns=0,
                                   wall_ns=50, thread_cpu_ns=50, exception=False))
        with self.assertRaises(ValueError):
            validate_worker_traces([trace], dict(mode="outer_stream_gc_on", block=0, condition_order=[]),
                                   dict(measured_attempts_per_condition=1, warmup_attempts_per_condition=2))

    def test_run_condition_real_decoder_single_read_and_all_controls_outside_io(self):
        mode = diagnostic_mode("nested_stream_gc_on")
        capture, retention, evidence = make_diagnostic_capture(mode), TraceRetention(mode), io.StringIO()
        reads, peers_created = [], []
        def factory(source, rng, observer):
            peers = fixtures.PipelineV2Tests().peers(prepare_callback=observer.wrap("prepare", fixtures.prepare))
            peers_created.append(peers)
            read = Mock(return_value=fixtures.response_with_flips({1, 2, 3}))
            reads.append(read)
            return peers[0], fixtures.REFERENCE, read
        source = fixtures.source_record()
        with diagnostic_instrumentation(mode, capture):
            runner.run_condition(factory, dict(name="condition"), [source], {source["device_id"]: (0,)},
                settings()["read_domain"], 0, capture, evidence, retention, "measured")
        reads[0].assert_called_once_with()
        self.assertEqual(peers_created[0][0].calls, ModelCallCounts(4, 4, 4))
        traces = [json.loads(line) for line in evidence.getvalue().splitlines()]
        self.assertEqual(len(traces), 8)
        self.assertTrue(all(r["mode"] == mode.name and r["selected_bit_error_count"] == 3 for r in traces))
        self.assertEqual(retention.retained_trace_count, 0)

    def test_run_condition_records_admission_failure_without_retry(self):
        mode = diagnostic_mode("outer_stream_gc_on")
        capture, retention, evidence = make_diagnostic_capture(mode), TraceRetention(mode), io.StringIO()
        read = Mock(return_value=fixtures.REFERENCE)
        pipeline = fixtures.PipelineV2Tests().peers(missing_record=True)[0]
        source = fixtures.source_record()
        runner.run_condition(lambda *_: (pipeline, fixtures.REFERENCE, read), dict(name="condition"), [source],
            {source["device_id"]: (0,)}, settings()["read_domain"], 0, capture, evidence, retention, "measured")
        read.assert_called_once_with()
        self.assertEqual(len(evidence.getvalue().splitlines()), 1)
        self.assertEqual(pipeline.calls, ModelCallCounts())

    def test_read_streams_pair_across_model_and_mode_but_blocks_are_distinct(self):
        source = fixtures.source_record()
        observed = []
        def factory(source, rng, observer):
            observed.append(rng.getrandbits(64))
            return fixtures.PipelineV2Tests().peers(missing_record=True)[0], fixtures.REFERENCE, lambda: fixtures.REFERENCE
        for block, mode_name, condition in ((0, "outer_stream_gc_on", "one"), (0, "nested_stream_gc_on", "two"),
                                             (1, "outer_stream_gc_on", "one")):
            mode = diagnostic_mode(mode_name)
            capture = make_diagnostic_capture(mode)
            runner.run_condition(factory, dict(name=condition), [source], {source["device_id"]: (0,)},
                settings()["read_domain"], block, capture, io.StringIO(), TraceRetention(mode), "measured")
        self.assertEqual(observed[0], observed[1])
        self.assertNotEqual(observed[0], observed[2])

    def test_heap_worker_records_five_collections_and_never_authenticates(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            counts = runner.run_heap_worker(output, dict(retained_trace_count=0), settings(), output)
            self.assertEqual(counts["trace_count"], 5)
            self.assertFalse(counts["authentication_executed"])
            self.assertFalse(counts["model_inference_executed"])
            probes = json.loads((output / "gc-probes.json").read_text())
            self.assertEqual([r["phase"] for r in probes], ["first_full_collection"] + ["repeat_full_collection"] * 4)
            self.assertTrue(all(r["gc_events"] and r["retained_trace_count"] == 0 for r in probes))

    def test_timing_worker_streams_before_analysis_and_records_deferred_cleanup(self):
        # Three NONSECRET integration fixtures, not the declared experimental
        # cohort, and spy consumers rather than frozen model-performance data.
        mode_name = "nested_stream_gc_deferred"
        source = fixtures.source_record()
        source["device_id"] = fixtures.DEVICE
        warmup = [dict(deepcopy(source), split="validation", window_id=f"warm-{i}") for i in range(2)]
        base = fixtures.PipelineV2Tests().peers()[0]
        material = {fixtures.DEVICE: (0, object(), fixtures.REFERENCE, fixtures.CREDENTIAL,
                                     fixtures.ENROLLMENT, base.sender.enrollment.helper_data, base.sender._admission_service)}
        condition = settings()["conditions"][0]
        job = dict(job_id="fixture", mode=mode_name, block=0, condition_order=[condition])
        config = dict(settings(), measured_attempts_per_condition=1, warmup_attempts_per_condition=2)
        puf = SimpleNamespace(nominal_frequency=100, read_conditions=None)
        callbacks = SimpleNamespace(motion_predictions=lambda _: "nod", anomaly_predictions=lambda _: {"flag": False})
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            with patch.object(runner, "select_experiment_sources", return_value=([source], warmup)), \
                 patch.object(runner, "make_materials", return_value=(puf, fixtures.AuthConfig(), [], material)), \
                 patch.object(runner, "one_model_bundle", return_value=callbacks), \
                 patch.object(runner, "generate_response", return_value=fixtures.REFERENCE):
                counts = runner.run_timing_worker(output, output, job, config, {}, object(), [])
            self.assertEqual(counts["fresh_attempt_count"], 3)
            self.assertEqual(counts["trace_count"], 24)
            self.assertEqual(counts["rejected_window_model_calls"], 0)
            runtime = json.loads((output / "runtime-and-cleanup.json").read_text())
            self.assertEqual(runtime["final_retention_before_release"]["retained_trace_count"], 0)
            self.assertEqual(runtime["final_retention_before_release"]["observed_trace_count"], 24)
            self.assertTrue(runtime["policy"]["cleanup"]["outside_root_timers"])
            self.assertTrue(runtime["policy"]["restored"]["automatic_gc_enabled"])
            self.assertEqual(len(read_job_traces(output, job)), 24)

    def test_timer_checks_do_not_tune_thresholds_or_enable_disabled_gc(self):
        before = gc.get_threshold()
        config = settings()
        config["gc_thresholds"] = list(before)
        result = runner.timer_metadata(config)
        self.assertIn("resolution", result["thread_cpu"])
        try:
            gc.disable()
            with self.assertRaises(ValueError):
                runner.timer_metadata(config)
            self.assertFalse(gc.isenabled())
        finally:
            gc.enable()
        config["gc_thresholds"] = [before[0] + 1, before[1], before[2]]
        with self.assertRaises(ValueError):
            runner.timer_metadata(config)
        self.assertEqual(gc.get_threshold(), before)

    def test_report_no_target_claim_no_complete_causal_claim_and_cleanup_disclosed(self):
        text = runner.report_text(settings(), [], [])
        for fragment in ("cleanup", "unresolved", "not completely position-balanced", "not a replacement", "not differences",
                         "does not establish Windows", "raw ETL", "not fully cold", "29,718"):
            self.assertIn(fragment, text)

    def controller_fixture(self, root):
        config_path = root / "experiment.json"
        runner.write_json(config_path, settings())
        (root / "configs").mkdir()
        frozen = dict(puf_config="configs/puf.json", auth_config="configs/auth.json")
        runner.write_json(root / "configs/week6_smoke.json", frozen)
        for name in ("puf", "auth"):
            runner.write_json(root / f"configs/{name}.json", {"fixture": True})
        return config_path, root / "results/week-6/keegan/controller-fixture"

    def test_controller_worker_failure_preserves_incomplete_no_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, output = self.controller_fixture(root)
            with patch.object(runner, "require_clean_source", return_value="fixed"), \
                 patch.object(runner, "timer_metadata"), patch.object(runner, "require_source_unchanged"), \
                 patch.object(runner, "checked_historical_inputs", return_value=(root, {}, {})), \
                 patch.object(runner, "load_frozen_bundle", return_value=SimpleNamespace(artifact_hashes={})), \
                 patch.object(runner.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "fixture")) as launch:
                with self.assertRaises(subprocess.CalledProcessError):
                    runner.controller(root, config, output, "unconfirmed", "unconfirmed")
            launch.assert_called_once()
            self.assertTrue((output / "INCOMPLETE").exists())
            self.assertTrue((output / "execution-failure.json").exists())
            self.assertFalse((output / "COMPLETE").exists())

    def test_controller_launches_twenty_serial_hashed_jobs_and_binds_manifests(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, output = self.controller_fixture(root)
            jobs, launched = build_jobs(settings()), []
            def fake_launch(command, **kwargs):
                index = int(command[command.index("--worker") + 1])
                launched.append(index)
                self.assertTrue(kwargs["check"])
                control_hash = command[command.index("--control-hash") + 1]
                self.assertEqual(control_hash, sha256(output / "control.json"))
                worker_dir = output / "workers" / jobs[index]["job_id"]
                worker_dir.mkdir(parents=True)
                runner.write_json(worker_dir / "manifest.json", {"fixture": True})
            manifests = {j["job_id"]: {"fresh_attempt_count": 540 if j["kind"] == "timing" else 0} for j in jobs}
            with patch.object(runner, "require_clean_source", return_value="fixed"), \
                 patch.object(runner, "timer_metadata"), patch.object(runner, "require_source_unchanged"), \
                 patch.object(runner, "checked_historical_inputs", return_value=(root, {}, {})), \
                 patch.object(runner, "load_frozen_bundle", return_value=SimpleNamespace(artifact_hashes={})), \
                 patch.object(runner, "recheck_frozen_inputs"), patch.object(runner, "report_text", return_value="FIXTURE ONLY\n"), \
                 patch.object(runner, "reconcile_workers", return_value=(manifests, [{"fixture": True}], [{"fixture": True}], [{"fixture": True}])), \
                 patch.object(runner.subprocess, "run", side_effect=fake_launch):
                runner.controller(root, config, output, "unconfirmed", "unconfirmed")
            self.assertEqual(launched, list(range(20)))
            manifest = checked_completion(output, expected_commit="fixed")
            self.assertEqual(manifest["fresh_attempt_count"], 8640)
            self.assertEqual(len(manifest["worker_manifest_hashes"]), 20)
            self.assertFalse(manifest["performance_target_claim"])
            self.assertFalse(manifest["complete_causal_attribution_established"])


if __name__ == "__main__":
    unittest.main()
