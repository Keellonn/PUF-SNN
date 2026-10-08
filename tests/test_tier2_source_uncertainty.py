"""Small saved-prediction fixtures; no generators, models, authentication or ETL."""

import ast
from collections import Counter
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from puf_snn.tier2_source_uncertainty import (
    GAP_REASON, LABELS, ORDER_REASON, build_source_analysis, case_accounting,
    check_historical_points, fixed_family, interval, motion_metrics, prepare_cohort,
    ratio, source_bootstrap_weights, source_metadata, validate_weights,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("tier2_reporting_runner", ROOT / "src/python/scripts/summarize_tier2_source_uncertainty.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def fixture():
    attacks = ["dropped_samples", "position_jump", "timestamp_jitter"]
    conditions = [("clean", "clean")] + [(name, level) for name in attacks for level in ("low", "medium", "high")]
    detectors = ["anomaly_logistic_regression_seed6007", "anomaly_random_forest_seed6007"]
    models = ["motion_logistic_regression_seed7", "motion_random_forest_seed7", "motion_snn_seed7"]
    data = dict(outcomes=[], authenticated=[],
        thresholds={name: dict(threshold=.5, selected_from="validation") for name in detectors},
        config=dict(validation_clean_fpr_limit=.05, medium_high_detection_target=.9),
        attack_config=dict(attacks=[dict(name=name) for name in attacks], severity_names=["low", "medium", "high"]))
    index = 0
    for profile in ("sim-device-01", "sim-device-02"):
        for label in ("nod", "still"):
            for trial in range(4):
                source_trial = f"{profile}-session-03-{label}-{trial:03d}"
                source = source_trial + "-window-000"
                for j, (attack, severity) in enumerate(conditions):
                    identity = dict(case_id=f"fixture-{index}-{j}", source_window_id=source,
                        source_trial_id=source_trial, attack_type=attack, severity=severity)
                    data["outcomes"].append(dict(**identity, split="test", status="quality_valid", reason="ready_for_legitimate_sender"))
                    flag = index % 4 == 0 if j == 0 else index % 4 != 0
                    motion = "shake" if index % 5 == 0 or (j and index % 3 == 0) else label
                    data["authenticated"].append(dict(**identity, motion_label=label, is_anomaly=j != 0,
                        motion={name: motion for name in models},
                        anomaly={name: dict(score=.8 if flag else .2, flag=flag) for name in detectors}))
                index += 1
    return data


def block(data, attack, severity, keep_sources=()):
    removed = set()
    for row in data["outcomes"]:
        if (row["attack_type"], row["severity"]) == (attack, severity) and row["source_window_id"] not in keep_sources:
            row.update(status="quality_failure", reason=GAP_REASON)
            removed.add(row["case_id"])
    data["authenticated"] = [row for row in data["authenticated"] if row["case_id"] not in removed]


def historical_summary(result):
    anomaly, motion = {}, {}
    for row in result["detector_outcomes"]:
        name, condition = row["detector"], f"{row['attack_type']}:{row['severity']}"
        saved = anomaly.setdefault(name, {})
        if not row["quality_valid_count"]:
            continue
        clean = row["attack_type"] == "clean"
        saved[condition] = dict(sample_count=row["quality_valid_count"],
            true_positives=0 if clean else row["flagged_count"], false_positives=row["flagged_count"] if clean else 0,
            true_negatives=row["quality_valid_count"]-row["flagged_count"] if clean else 0,
            false_negatives=0 if clean else row["quality_valid_count"]-row["flagged_count"])
    for row in result["detector_summary"]:
        group, field = (("medium_high_quality_valid", "recall") if row["metric"] == "medium_high_recall" else
            ("clean:clean", "clean_false_positive_rate") if row["metric"] == "clean_fpr" else
            ("all_quality_valid", row["metric"].removeprefix("all_quality_valid_").replace("all_attack_recall", "recall")))
        anomaly[row["detector"]].setdefault(group, {})[field] = row["point_estimate"]
    cohort = result["cohort"]
    for j, (attack, severity) in enumerate(cohort["conditions"]):
        mask = cohort["valid"][:, j]
        for k, name in enumerate(cohort["motion_models"]):
            saved = motion.setdefault(name, {})
            if mask.any():
                saved[f"{attack}:{severity}"] = motion_metrics(cohort["truth"][mask], cohort["predictions"][mask, j, k])
    return dict(authenticated=dict(anomaly=anomaly, motion=motion))


class SourceUncertaintyTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()

    def build(self, data=None):
        return build_source_analysis(self.data if data is None else data, repetitions=64, seed=7027)

    def test_source_identity_and_stratum_are_explicit(self):
        row = self.data["outcomes"][0]
        meta = source_metadata(row["source_window_id"], row["source_trial_id"])
        self.assertEqual(meta["stratum"], "sim-device-01:session-03:nod")
        self.assertEqual(fixed_family("anomaly_random_forest_seed6007"), "random_forest")

    def test_unknown_source_or_trial_or_family_is_rejected(self):
        for source, trial in (("unknown", "unknown"), (self.data["outcomes"][0]["source_window_id"], "different")):
            with self.assertRaises(ValueError):
                source_metadata(source, trial)
        with self.assertRaises(ValueError):
            fixed_family("new_detector_seed1")

    def test_complete_condition_counts_and_denominators(self):
        result = self.build()
        self.assertEqual(result["cohort"]["valid"].shape, (16, 10))
        self.assertEqual(len(result["detector_outcomes"]), 20)
        self.assertEqual(len(result["motion_degradation"]), 30)
        for row in result["detector_summary"]:
            expected = {"clean_fpr": 16, "all_attack_recall": 144, "medium_high_recall": 96}.get(row["metric"], 160)
            self.assertEqual(row["eligible_case_count"], expected)
            self.assertEqual(row["unique_source_count"], 16)

    def test_weights_preserve_every_fixed_stratum(self):
        result = self.build()
        metadata, weights = result["cohort"]["sources"], result["weights"]
        self.assertTrue(np.all(weights.sum(axis=1) == 16))
        for name in {row["stratum"] for row in metadata}:
            indices = [i for i, row in enumerate(metadata) if row["stratum"] == name]
            self.assertTrue(np.all(weights[:, indices].sum(axis=1) == 4))

    def test_reporting_seed_and_canonical_source_order_are_reproducible(self):
        first = self.build()
        data = deepcopy(self.data)
        data["outcomes"].reverse()
        data["authenticated"].reverse()
        second = self.build(data)
        self.assertEqual(first["cohort"]["sources"], second["cohort"]["sources"])
        np.testing.assert_array_equal(first["weights"], second["weights"])
        self.assertEqual(first["source_weight_sha256"], second["source_weight_sha256"])

    def test_different_resampling_seed_changes_weights_not_points(self):
        first = self.build()
        second = build_source_analysis(self.data, 64, 42)
        self.assertNotEqual(first["source_weight_sha256"], second["source_weight_sha256"])
        self.assertEqual([r["point_estimate"] for r in first["detector_summary"]], [r["point_estimate"] for r in second["detector_summary"]])

    def test_correlated_derivatives_do_not_create_independent_trials(self):
        result = self.build()
        # Every transformed condition deliberately has the same per-source flag.
        summary = next(row for row in result["detector_summary"] if row["metric"] == "all_attack_recall")
        condition = next(row for row in result["detector_outcomes"] if row["attack_type"] == "position_jump" and row["severity"] == "low" and row["detector"] == summary["detector"])
        self.assertAlmostEqual(summary["ci_low"], condition["ci_low"])
        self.assertAlmostEqual(summary["ci_high"], condition["ci_high"])
        self.assertEqual(summary["unique_source_count"], 16)
        self.assertEqual(summary["eligible_case_count"], 16*9)

    def test_identical_seed_fits_do_not_shrink_family_interval(self):
        data = deepcopy(self.data)
        for name in list(data["thresholds"]):
            copied = name.replace("6007", "6017")
            data["thresholds"][copied] = deepcopy(data["thresholds"][name])
            for row in data["authenticated"]:
                row["anomaly"][copied] = deepcopy(row["anomaly"][name])
        result = self.build(data)
        for family in result["family_summary"]:
            fixed = next(row for row in result["detector_summary"] if fixed_family(row["detector"]) == family["family"] and row["metric"] == family["metric"])
            self.assertEqual(family["fixed_model_count"], 2)
            self.assertFalse(family["seed_fits_are_independent_source_trials"])
            self.assertEqual(family["ci_low"], fixed["ci_low"])
            self.assertEqual(family["ci_high"], fixed["ci_high"])

    def test_quality_blocks_are_not_detections_or_misses(self):
        block(self.data, "dropped_samples", "high")
        result = self.build()
        rows = [row for row in result["detector_outcomes"] if row["attack_type"] == "dropped_samples" and row["severity"] == "high"]
        for row in rows:
            self.assertEqual(row["pre_tag_blocked_count"], 16)
            self.assertEqual(row["authenticated_accepted_count"], 0)
            self.assertEqual(row["authenticated_rejected_before_inference_count"], 0)
            self.assertEqual(row["anomaly_detected_count"], 0)
            self.assertEqual(row["anomaly_missed_count"], 0)
            self.assertIsNone(row["flag_rate"])
            self.assertEqual(row["undefined_bootstrap_draws"], 64)
            self.assertIsNone(row["ci_low"])

    def test_tiny_eligible_cohort_reports_undefined_draws_without_retries(self):
        source = self.data["outcomes"][0]["source_window_id"]
        block(self.data, "dropped_samples", "high", keep_sources=[source])
        result = self.build()
        row = next(row for row in result["detector_outcomes"] if row["attack_type"] == "dropped_samples" and row["severity"] == "high")
        self.assertEqual(row["unique_eligible_sources"], 1)
        self.assertTrue(row["small_eligible_cohort"])
        self.assertGreater(row["undefined_bootstrap_draws"], 0)
        self.assertEqual(row["defined_bootstrap_draws"] + row["undefined_bootstrap_draws"], 64)
        self.assertTrue(row["degenerate_bootstrap_interval"])

    def test_gap_and_timestamp_order_remain_separate(self):
        block(self.data, "timestamp_jitter", "high")
        selected = [row for row in self.data["outcomes"] if row["attack_type"] == "timestamp_jitter" and row["severity"] == "high"]
        selected[0]["reason"] = ORDER_REASON
        counts = next(row for row in case_accounting(self.data["outcomes"]) if row["attack_type"] == "timestamp_jitter" and row["severity"] == "high")
        self.assertEqual(counts["timestamp_order_blocks"], 1)
        self.assertEqual(counts["timestamp_gap_blocks"], 15)
        self.assertEqual(counts["pre_tag_blocked_count"], 16)

    def test_clean_comparison_is_paired_and_loss_zero_for_clean(self):
        for row in self.build()["motion_degradation"]:
            if row["attack_type"] == "clean":
                self.assertEqual(row["paired_accuracy_loss"], 0)
                self.assertEqual(row["ci_low"], 0)
                self.assertEqual(row["ci_high"], 0)
            self.assertFalse(row["macro_f1_interval_provided"])

    def test_motion_reference_uses_only_changed_condition_eligible_sources(self):
        source = self.data["outcomes"][0]["source_window_id"]
        block(self.data, "dropped_samples", "high", keep_sources=[source])
        row = next(row for row in self.build()["motion_degradation"] if row["attack_type"] == "dropped_samples" and row["severity"] == "high")
        self.assertEqual(row["unique_eligible_sources"], 1)
        self.assertEqual(row["clean_subset_accuracy"], 0)

    def test_duplicate_cases_or_unknown_split_status_are_rejected(self):
        variations = [self.data["outcomes"] + [deepcopy(self.data["outcomes"][0])]]
        for field, value in (("split", "unknown"), ("status", "unknown")):
            rows = deepcopy(self.data["outcomes"])
            rows[0][field] = value
            variations.append(rows)
        for rows in variations:
            with self.assertRaises(ValueError):
                case_accounting(rows)

    def test_source_derivatives_cannot_cross_splits(self):
        self.data["outcomes"][1]["split"] = "validation"
        with self.assertRaises(ValueError):
            prepare_cohort(self.data)

    def test_multiple_windows_per_trial_require_a_different_cluster_protocol(self):
        row = deepcopy(self.data["outcomes"][0])
        row.update(case_id="second-window", source_window_id=row["source_window_id"].replace("window-000", "window-001"))
        with self.assertRaises(ValueError):
            case_accounting([self.data["outcomes"][0], row])

    def test_missing_or_duplicate_planned_condition_is_rejected(self):
        for change in ("missing", "duplicate"):
            data = deepcopy(self.data)
            if change == "missing":
                data["outcomes"].pop()
            else:
                row = deepcopy(data["outcomes"][-1])
                row["case_id"] = "duplicate-slot"
                data["outcomes"].append(row)
            with self.assertRaises(ValueError):
                prepare_cohort(data)

    def test_saved_predictions_cannot_exist_for_quality_blocked_cases(self):
        self.data["outcomes"][1].update(status="quality_failure", reason=GAP_REASON)
        with self.assertRaises(ValueError):
            prepare_cohort(self.data)

    def test_missing_or_duplicate_saved_prediction_is_rejected(self):
        for change in ("missing", "duplicate"):
            data = deepcopy(self.data)
            if change == "missing":
                data["authenticated"].pop()
            else:
                data["authenticated"].append(deepcopy(data["authenticated"][-1]))
            with self.assertRaises(ValueError):
                prepare_cohort(data)

    def test_clean_control_is_required_for_every_source(self):
        self.data["authenticated"].pop(0)
        with self.assertRaises(ValueError):
            prepare_cohort(self.data)

    def test_labels_anomaly_identity_and_model_sets_cannot_change(self):
        for field, value in (("motion_label", "shake"), ("is_anomaly", False), ("motion", {}), ("source_trial_id", "wrong")):
            data = deepcopy(self.data)
            data["authenticated"][1][field] = value
            with self.assertRaises(ValueError):
                prepare_cohort(data)

    def test_flags_scores_and_thresholds_are_frozen_and_validated(self):
        name = next(iter(self.data["thresholds"]))
        for field, value in (("flag", "yes"), ("flag", True), ("score", float("nan")), ("score", 1.1)):
            data = deepcopy(self.data)
            data["authenticated"][1]["anomaly"][name][field] = value
            with self.assertRaises(ValueError):
                prepare_cohort(data)
        for field, value in (("selected_from", "test"), ("threshold", float("nan")), ("threshold", -1)):
            data = deepcopy(self.data)
            data["thresholds"][name][field] = value
            with self.assertRaises(ValueError):
                prepare_cohort(data)

    def test_invalid_resampling_settings_or_weight_partitions_are_rejected(self):
        metadata = prepare_cohort(self.data)["sources"]
        for repetitions, seed in ((0, 1), (True, 1), (20, -1), (20, True)):
            with self.assertRaises(ValueError):
                source_bootstrap_weights(metadata, repetitions, seed)
        weights = source_bootstrap_weights(metadata, 64, 1)
        weights[0, 0] += 1
        with self.assertRaises(ValueError):
            validate_weights(weights, metadata)

    def test_interval_reports_nonfinite_and_degenerate_draws(self):
        self.assertTrue(interval([1, 1, np.nan])["degenerate_bootstrap_interval"])
        self.assertEqual(interval([1, 1, np.nan])["undefined_bootstrap_draws"], 1)
        self.assertIsNone(interval([np.nan, np.inf])["ci_low"])
        np.testing.assert_allclose(ratio([1, 2], [2, 0]), [.5, np.nan], equal_nan=True)

    def test_fixed_five_class_macro_f1_and_unknown_indexes(self):
        self.assertEqual(motion_metrics([0], [0])["macro_f1"], .2)
        self.assertIsNone(motion_metrics([], [])["macro_f1"])
        for left, right in (([0], [5]), ([0], [-1]), ([0], []), ([.1], [0])):
            with self.assertRaises(ValueError):
                motion_metrics(left, right)

    def test_frozen_historical_point_estimates_and_confusions_reconcile(self):
        result = self.build()
        check_historical_points(result, historical_summary(result))

    def test_changed_historical_counts_or_f1_are_rejected(self):
        result = self.build()
        saved = historical_summary(result)
        name = result["cohort"]["detectors"][0]
        saved["authenticated"]["anomaly"][name]["clean:clean"]["false_positives"] += 1
        with self.assertRaises(ValueError):
            check_historical_points(result, saved)
        saved = historical_summary(result)
        name = result["cohort"]["motion_models"][0]
        saved["authenticated"]["motion"][name]["clean:clean"]["macro_f1"] += .1
        with self.assertRaises(ValueError):
            check_historical_points(result, saved)

    def test_output_cannot_overwrite_or_escape_week6_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / "results/week-5/keegan/stream-evaluation"
            output = root / "results/week-6/keegan/tier2-source-uncertainty"
            self.assertEqual(RUNNER.checked_output_path(root, directory, output), (directory.resolve(), output.resolve()))
            for target in (directory, root, root / "results/week-6/keegan", root / "outside"):
                with self.assertRaises(ValueError):
                    RUNNER.checked_output_path(root, directory, target)
            output.mkdir(parents=True)
            with self.assertRaises(ValueError):
                RUNNER.checked_output_path(root, directory, output)

    def test_writers_are_lf_and_refuse_overwrites_and_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            RUNNER.write_csv(root / "table.csv", [dict(count=1, value=None)])
            RUNNER.write_json(root / "record.json", dict(ok=True))
            RUNNER.write_weights(root / "weights.csv", np.asarray([[1, 2], [2, 1]], dtype=np.uint16))
            for name in ("table.csv", "record.json", "weights.csv"):
                self.assertNotIn(b"\r", (root / name).read_bytes())
            with self.assertRaises(FileExistsError):
                RUNNER.write_json(root / "record.json", {})
            with self.assertRaises(ValueError):
                RUNNER.write_json(root / "invalid.json", dict(value=float("nan")))
            with self.assertRaises(ValueError):
                RUNNER.write_csv(root / "empty.csv", [])

    def test_no_model_authentication_or_generator_imports_in_new_code(self):
        for relative in RUNNER.SOURCE_FILES[:2]:
            tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
            imports = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            imports += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
            self.assertFalse(any(name and (name.startswith(("torch", "sklearn", "joblib", "puf_snn.auth", "puf_snn.snn", "puf_snn.attacks"))) for name in imports))


if __name__ == "__main__":
    unittest.main()
