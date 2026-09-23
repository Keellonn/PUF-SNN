# Currently missing experiment config from earlier commit

"""Accounting and isolation tests; no favorable cohort FRR is asserted."""

from collections import Counter
from dataclasses import replace
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/python"))

from puf_snn.puf.variables import load_config
from puf_snn.reconstruction import ReconstructionResult
from scripts import run_reconstruction as experiment
from scripts.run_puf_baseline import simulate


def result(outcome, credential=None):
    if outcome == "decoder_failure":
        return ReconstructionResult(outcome, "uncorrectable", -1, None, None, None,
                                    "decoder_declared_failure")
    if outcome == "invalid_format_or_padding":
        return ReconstructionResult(outcome, "decoded", 5, (0,) * 35 + (1,),
                                    None, False, "nonzero_padding")
    message = tuple(int(b) for b in f"{int.from_bytes(credential, 'big'):032b}") + (0,) * 4
    return ReconstructionResult(outcome, "decoded", 0, message, credential, True, None)


class ExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = load_config(ROOT / "configs/puf_baseline.json")
        cls.config = replace(config, number_of_devices=2, repeated_reads=3,
                             noise_sweep=(0.0, 0.1, 1.0))
        cls.runs = [{"seed": seed, "tables": simulate(replace(cls.config, random_seed=seed))}
                    for seed in (1111, 2222)]
        cls.plan = {"experiment_version": experiment.VERSION,
                    "simulation_seeds": [1111, 2222], "test_fixture": True,
                    "bootstrap_seed": 99, "bootstrap_resamples": 100}
        experiment.warm_up()

    def run_fixture(self, output, **kwargs):
        with patch.object(experiment, "environment", return_value={"test_fixture": True}):
            return experiment.run_evaluation(output, kwargs.get("runs", self.runs),
                                             self.plan, {"test_fixture": True})

    def read_rows(self, output):
        return [json.loads(line) for line in (output / "attempts.jsonl").read_text().splitlines()]

    def test_exact_counts_unique_readings_no_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "evidence"
            with patch.object(experiment, "warm_up", return_value={}), patch.object(
                    experiment, "reconstruct", wraps=experiment.reconstruct) as decode:
                summary = self.run_fixture(output)
            rows = self.read_rows(output)
            self.assertEqual(len(rows), 48)
            self.assertEqual(summary["attempt_count"], 48)
            self.assertEqual(decode.call_count, 48)
            self.assertEqual(len({experiment.attempt_key(r) for r in rows}), 48)
            expected = [(seed, row["response"]) for seed, row in experiment.attempt_inputs(self.runs)]
            self.assertEqual([(r["simulation_seed"], r["response64"]) for r in rows], expected)
            self.assertTrue((output / "COMPLETE").exists())

    def test_primary_finishes_before_sweep_and_nominal_samples_differ(self):
        inputs = list(experiment.attempt_inputs(self.runs))
        self.assertTrue(all(r["phase"] == "baseline" for _, r in inputs[:12]))
        self.assertTrue(all(r["phase"] == "noise_sweep" for _, r in inputs[12:]))
        tables = self.runs[0]["tables"]
        self.assertNotEqual([r["response"] for r in tables["metrics"]],
                            [r["response"] for r in tables["noise_sweep"] if r["sweep_index"] == 1])

    def test_all_four_outcomes_and_frr_denominator(self):
        credential = bytes.fromhex("12345678")
        cases = [result("decoder_failure"), result("invalid_format_or_padding"),
                 result("candidate_valid_format", bytes(4)),
                 result("candidate_valid_format", credential)]
        rows = [{**experiment.evaluate_result(r, credential), "evaluator_error_count63": 6,
                 "evaluator_error_count64": 6, "reconstruction_latency_ns": i + 1}
                for i, r in enumerate(cases)]
        summary = experiment.summarize(rows)
        self.assertEqual((summary["attempt_count"], summary["success_count"],
                          summary["failure_count"], summary["frr"]), (4, 1, 3, 0.75))
        self.assertEqual([summary[k] for k in ("decoder_failures", "invalid_format", "miscorrections")],
                         [1, 1, 1])
        self.assertEqual([r["evaluator_outcome"] for r in rows], ["no_valid_candidate",
                         "no_valid_candidate", "evaluator_wrong_match", "evaluator_correct_match"])

    def test_evaluation_happens_after_return_with_only_public_decoder_inputs(self):
        events = []
        original_decode, original_evaluate = experiment.reconstruct, experiment.evaluate_result

        def decode(*args, **kwargs):
            self.assertEqual(len(args), 3)
            self.assertEqual(kwargs, {})
            self.assertEqual(set(vars(args[1])), {"helper_bits", "config", "enrollment_id"})
            self.assertEqual(len(args[0]), 64)
            events.append("decode")
            return original_decode(*args, **kwargs)

        def evaluate(*args):
            self.assertEqual(events[-1], "decode")
            events.append("evaluate")
            return original_evaluate(*args)

        with tempfile.TemporaryDirectory() as tmp, patch.object(experiment, "warm_up", return_value={}), \
                patch.object(experiment, "reconstruct", side_effect=decode), \
                patch.object(experiment, "evaluate_result", side_effect=evaluate):
            self.run_fixture(Path(tmp) / "evidence")
        self.assertEqual(events, ["decode", "evaluate"] * 48)

    def test_one_enrollment_per_device_helpers_reused_across_conditions(self):
        helpers = {}
        original = experiment.reconstruct

        def decode(response, helper, config):
            key = helper.enrollment_id
            if key in helpers:
                self.assertIs(helpers[key], helper)
            helpers[key] = helper
            return original(response, helper, config)

        with tempfile.TemporaryDirectory() as tmp, patch.object(experiment, "warm_up", return_value={}), \
                patch.object(experiment, "enroll", wraps=experiment.enroll) as enrollment, \
                patch.object(experiment, "reconstruct", side_effect=decode):
            output = Path(tmp) / "evidence"
            self.run_fixture(output)
            self.assertEqual(enrollment.call_count, 4)
            self.assertEqual(len(helpers), 4)
            rows = self.read_rows(output)
            for key in helpers:
                device_rows = [r for r in rows if r["enrollment_id"] == key]
                self.assertEqual(len(device_rows), 12)
                self.assertEqual(len({r["credential_stream_identity"] for r in device_rows}), 1)

    def test_versioned_credential_stream_matches_spec_and_consumes_no_global_rng(self):
        state = random.getstate()
        identity, credential = experiment.credential_for(1111, 0)
        self.assertEqual(identity, "layer2-v1:1111:0:credential")
        rng = random.Random()
        rng.seed(identity, version=2)
        self.assertEqual(credential, rng.getrandbits(32).to_bytes(4, "big"))
        self.assertEqual(random.getstate(), state)

    def test_evaluation_preserves_layer1_tables_and_rng_outputs(self):
        before = json.dumps(self.runs, sort_keys=True)
        state = random.getstate()
        with tempfile.TemporaryDirectory() as tmp:
            self.run_fixture(Path(tmp) / "evidence")
        self.assertEqual(json.dumps(self.runs, sort_keys=True), before)
        self.assertEqual(random.getstate(), state)
        for run in self.runs:
            self.assertEqual(simulate(replace(self.config, random_seed=run["seed"])), run["tables"])

    def test_non_timing_records_reproduce_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs = [Path(tmp) / name for name in ("first", "second")]
            for output in outputs:
                self.run_fixture(output)
            records = []
            for output in outputs:
                rows = self.read_rows(output)
                for row in rows:
                    row.pop("reconstruction_latency_ns")
                records.append(rows)
            self.assertEqual(*records)
            self.assertEqual((outputs[0] / "enrollments.json").read_bytes(),
                             (outputs[1] / "enrollments.json").read_bytes())

    def test_backend_exception_retains_partial_evidence_without_frr_or_complete(self):
        original = experiment.reconstruct
        calls = 0

        def decode(*args):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise RuntimeError("injected backend error")
            return original(*args)

        with tempfile.TemporaryDirectory() as tmp, patch.object(experiment, "warm_up", return_value={}), \
                patch.object(experiment, "reconstruct", side_effect=decode):
            output = Path(tmp) / "evidence"
            with self.assertRaisesRegex(RuntimeError, "injected backend error"):
                self.run_fixture(output)
            rows = self.read_rows(output)
            self.assertEqual(len(rows), 3)
            self.assertIsNone(rows[-1]["evaluator_success"])
            self.assertEqual(rows[-1]["backend_exception"]["type"], "RuntimeError")
            self.assertEqual(calls, 3)
            self.assertFalse((output / "COMPLETE").exists())
            self.assertFalse((output / "summary.json").exists())
            self.assertTrue((output / "INCOMPLETE.json").exists())
            with self.assertRaises(ValueError):
                experiment.summarize(rows)

    def test_summary_write_failure_never_marks_complete(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(experiment, "save_summaries",
                                                               side_effect=OSError("disk error")):
            output = Path(tmp) / "evidence"
            with self.assertRaises(OSError):
                self.run_fixture(output)
            self.assertEqual(len(self.read_rows(output)), 48)
            self.assertFalse((output / "COMPLETE").exists())

    def test_existing_completed_or_partial_evidence_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "evidence"
            self.run_fixture(output)
            before = {p.name: p.read_bytes() for p in output.iterdir()}
            with self.assertRaises(FileExistsError):
                self.run_fixture(output)
            self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir()})
            partial = Path(tmp) / "partial"
            partial.mkdir()
            with self.assertRaises(FileExistsError):
                self.run_fixture(partial)

    def test_synthetic_warmup_excluded_from_attempts_and_latency_samples(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
                experiment, "reconstruct", wraps=experiment.reconstruct) as decode:
            output = Path(tmp) / "evidence"
            summary = self.run_fixture(output)
            warmup = json.loads((output / "warm_up.json").read_text())
            self.assertEqual(warmup["experimental_readings_consumed"], 0)
            self.assertEqual(decode.call_count, 48 + warmup["synthetic_probe_count"])
            self.assertEqual(sum(r["latency_sample_count"] for r in summary["conditions"]), 48)

    def test_every_summary_group_reconciles_with_raw_records(self):
        import csv
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "evidence"
            summary = self.run_fixture(output)
            rows = self.read_rows(output)
            for name, extra in (("per_run_summary", ["simulation_seed"]),
                                ("per_device_summary", ["simulation_seed", "device_id"]),
                                ("error_count_summary", ["evaluator_error_count63"])):
                with (output / f"{name}.csv").open(newline="") as stream:
                    groups = list(csv.DictReader(stream))
                self.assertEqual(sum(int(g["attempt_count"]) for g in groups), 48)
                for group in groups:
                    keys = ["phase", "sweep_index", "measurement_noise_std", *extra]
                    selected = [r for r in rows if all(str(r[k]) == group[k] for k in keys)]
                    expected = experiment.summarize(selected)
                    for key in ("attempt_count", "success_count", "failure_count", "decoder_failures",
                                "invalid_format", "miscorrections", "latency_sample_count"):
                        self.assertEqual(int(group[key]), expected[key])
                    self.assertEqual(json.loads(group["error_count_distribution"]),
                                     {str(k): v for k, v in expected["error_count_distribution"].items()})
            self.assertEqual(sum(r["attempt_count"] for r in summary["conditions"]), 48)

    def test_latency_statistics_include_failures(self):
        rows = []
        for elapsed in (10, 20, 30, 100):
            row = experiment.evaluate_result(result("decoder_failure"), bytes(4))
            rows.append({**row, "reconstruction_latency_ns": elapsed,
                         "evaluator_error_count63": 6, "evaluator_error_count64": 6})
        summary = experiment.summarize(rows)
        self.assertEqual(summary["latency_sample_count"], 4)
        self.assertEqual(summary["latency_mean_ns"], 40)
        self.assertEqual(summary["latency_median_ns"], 25)
        self.assertAlmostEqual(summary["latency_p95_ns"], 89.5)
        self.assertEqual(summary["latency_max_ns"], 100)

    def test_bootstrap_uses_whole_run_clusters_and_is_repeatable(self):
        runs = [{"attempt_count": 100, "failure_count": 0, "frr": 0},
                {"attempt_count": 100, "failure_count": 100, "frr": 1}]
        actual = experiment.run_uncertainty(runs, 99, 1000)
        self.assertEqual(actual, experiment.run_uncertainty(runs, 99, 1000))
        self.assertEqual(actual["frr_ci95"], [0, 1])
        self.assertEqual(actual["mean_run_frr"], 0.5)
        self.assertAlmostEqual(actual["sample_sd_run_frr"], 2 ** -0.5)

    def test_input_duplicates_are_not_silently_deduplicated(self):
        duplicated = json.loads(json.dumps(self.runs))
        duplicated[0]["tables"]["metrics"].append(duplicated[0]["tables"]["metrics"][0])
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "evidence"
            with self.assertRaisesRegex(ValueError, "Duplicate input"):
                self.run_fixture(output, runs=duplicated)
            self.assertFalse((output / "COMPLETE").exists())

    def test_fixed_subset_and_ground_truth_distance_fields(self):
        materials, _ = experiment.enroll_runs(self.runs)
        seed, row = next(experiment.attempt_inputs(self.runs))
        material = materials[seed, row["device_id"]]
        altered = dict(row, response="".join(map(str, material[1][:63])) + str(1 - material[1][63]))
        record, response = experiment.input_record(seed, altered, material, "test")
        self.assertEqual(record["evaluator_error_count64"], 1)
        self.assertEqual(record["evaluator_error_count63"], 0)
        self.assertEqual(record["selected_response63"], altered["response"][:63])
        self.assertEqual(len(response), 64)

    def test_evidence_manifest_matches_every_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "evidence"
            self.run_fixture(output)
            manifest = json.loads((output / "manifest.json").read_text())
            for name, fingerprint in manifest.items():
                self.assertEqual(experiment.digest(output / name), fingerprint)
            complete = json.loads((output / "COMPLETE").read_text())
            self.assertEqual(complete["manifest_sha256"], experiment.digest(output / "manifest.json"))

    def test_frozen_plan_rejects_seed_selection(self):
        plan = json.loads((ROOT / "configs/reconstruction_experiment_v1.json").read_text())
        plan["simulation_seeds"] = plan["simulation_seeds"][:-1]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "plan.json"
            path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, "20 cohort seeds"):
                experiment.load_plan(path)

    def test_noise_failures_retained_once_without_retry_in_saved_evidence(self):
        fixtures = json.loads(json.dumps(self.runs))
        credentials = {}
        for run in fixtures:
            for device in run["tables"]["devices"]:
                credentials[run["seed"], device["device_id"]] = experiment.credential_for(
                    run["seed"], int(device["device_id"].removeprefix("device-")))[1]
                reference = device["reference_response"]
                for name in ("metrics", "noise_sweep"):
                    for row in run["tables"][name]:
                        if row["device_id"] == device["device_id"]:
                            row["response"] = "".join(str(1 - int(b)) if i < 6 else b
                                                     for i, b in enumerate(reference))
        cases = []
        for i, (seed, row) in enumerate(experiment.attempt_inputs(fixtures)):
            credential = credentials[seed, row["device_id"]]
            cases.append([result("decoder_failure"), result("invalid_format_or_padding"),
                          result("candidate_valid_format", bytes(b ^ 255 for b in credential)),
                          result("candidate_valid_format", credential)][i % 4])
        with tempfile.TemporaryDirectory() as tmp, patch.object(experiment, "warm_up", return_value={}), \
                patch.object(experiment, "reconstruct", side_effect=cases) as decode:
            output = Path(tmp) / "evidence"
            self.run_fixture(output, runs=fixtures)
            rows = self.read_rows(output)
            summary = experiment.summarize(rows)
            self.assertEqual(decode.call_count, 48)
            self.assertEqual(summary["frr"], 0.75)
            self.assertEqual([summary[k] for k in ("success_count", "decoder_failures",
                                                  "invalid_format", "miscorrections")], [12] * 4)

    def test_within_radius_failure_stops_with_evidence_for_correctness_review(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(experiment, "warm_up", return_value={}), \
                patch.object(experiment, "reconstruct", return_value=result("decoder_failure")) as decode:
            output = Path(tmp) / "evidence"
            with self.assertRaisesRegex(RuntimeError, "within t=5"):
                self.run_fixture(output)
            self.assertEqual(decode.call_count, 1)
            self.assertEqual(len(self.read_rows(output)), 1)
            self.assertFalse((output / "COMPLETE").exists())

    def test_source_changes_during_experiment_invalidate_completion(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
                experiment, "source_hashes", side_effect=[{"source": "before"}, {"source": "after"}]):
            output = Path(tmp) / "evidence"
            with self.assertRaisesRegex(ValueError, "Source files changed"):
                self.run_fixture(output)
            self.assertFalse((output / "COMPLETE").exists())


if __name__ == "__main__":
    unittest.main()
