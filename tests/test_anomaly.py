"""these tests check motion-only anomaly features, source weights and validation-only thresholds"""

from copy import deepcopy
import json
from pathlib import Path
import unittest

import numpy as np

from puf_snn.anomaly.detector import anomaly_scores, binary_metrics, fit_anomaly_models, select_validation_threshold, source_balanced_weights, source_cluster_intervals, validate_evaluation_config
from puf_snn.anomaly.features import FEATURE_NAMES, record_to_anomaly_features
from puf_snn.data.generator import generate_records

ROOT = Path(__file__).resolve().parents[1]
EVALUATION_CONFIG = ROOT / "configs/stream_evaluation.json"


def small_cases(split: str = "validation") -> list[dict]:
    return [{"case_id": f"case-{source}-{copy}", "source_window_id": f"source-{source}", "source_trial_id": f"trial-{source}", "split": split, "is_anomaly": copy > 0, "attack_type": "position_noise" if copy > 0 else "clean"} for source in range(3) for copy in range(3)]


class AnomalyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pilot = json.loads((ROOT / "configs/pilot.json").read_text(encoding="utf-8"))
        pilot["synthetic_data"]["device_profiles"] = 1
        pilot["synthetic_data"]["trials_per_class_per_session"] = 1
        cls.records = generate_records(pilot)
        cls.config = json.loads(EVALUATION_CONFIG.read_text(encoding="utf-8"))

    def test_configuration_has_distinct_seed_roles_and_frozen_reference(self) -> None:
        validate_evaluation_config(self.config)
        changed = deepcopy(self.config)
        changed["anomaly_model_seeds"][0] = changed["motion_model_seeds"][0]
        with self.assertRaises(ValueError):
            validate_evaluation_config(changed)
        changed = deepcopy(self.config)
        changed["snn_hidden_neurons"] = 32
        with self.assertRaises(ValueError):
            validate_evaluation_config(changed)

    def test_feature_names_and_finite_shape(self) -> None:
        self.assertEqual(len(FEATURE_NAMES), 48)
        self.assertEqual(len(set(FEATURE_NAMES)), 48)
        for record in self.records:
            values = record_to_anomaly_features(record)
            self.assertEqual(values.shape, (48,))
            self.assertTrue(np.isfinite(values).all())

    def test_model_features_exclude_all_supervision_and_quality_metadata(self) -> None:
        original = self.records[0]
        changed = deepcopy(original)
        for name in ("window_id", "device_id", "session_id", "source_trial_id", "label", "split", "attack_type", "severity", "sequence_number", "seed", "construction_outcome", "authentication_result"):
            changed[name] = "not-a-feature"
        for sample in changed["samples"]:
            sample["tracking_valid"] = False
        np.testing.assert_array_equal(record_to_anomaly_features(original), record_to_anomaly_features(changed))

    def test_position_and_large_time_origin_do_not_change_features(self) -> None:
        original = self.records[0]
        changed = deepcopy(original)
        for sample in changed["samples"]:
            sample["position_m"] = [value + 5.0 for value in sample["position_m"]]
            sample["capture_time_ns"] += 1_700_000_000_000_000_000
        np.testing.assert_allclose(record_to_anomaly_features(original), record_to_anomaly_features(changed), atol=1e-8, rtol=1e-8)

    def test_equivalent_quaternion_signs_do_not_change_features(self) -> None:
        changed = deepcopy(self.records[0])
        for sample in changed["samples"]:
            sample["orientation_xyzw"] = [-value for value in sample["orientation_xyzw"]]
        np.testing.assert_allclose(record_to_anomaly_features(self.records[0]), record_to_anomaly_features(changed), atol=1e-12)

    def test_velocity_uses_actual_timestamp_intervals(self) -> None:
        record = deepcopy(self.records[0])
        for index, sample in enumerate(record["samples"]):
            sample["capture_time_ns"] = index * 10_000_000
            sample["position_m"] = [index * 0.01, 0.0, 0.0]
            sample["orientation_xyzw"] = [0.0, 0.0, 0.0, 1.0]
        features = record_to_anomaly_features(record)
        self.assertAlmostEqual(features[FEATURE_NAMES.index("linear_speed_m_s_mean")], 1.0)
        for sample in record["samples"]:
            sample["capture_time_ns"] *= 2
        features = record_to_anomaly_features(record)
        self.assertAlmostEqual(features[FEATURE_NAMES.index("linear_speed_m_s_mean")], 0.5)

    def test_constant_pose_has_visible_repeat_features(self) -> None:
        record = deepcopy(self.records[0])
        for sample in record["samples"]:
            sample["position_m"] = [0.0, 0.0, 0.0]
            sample["orientation_xyzw"] = [0.0, 0.0, 0.0, 1.0]
        features = record_to_anomaly_features(record)
        self.assertEqual(features[FEATURE_NAMES.index("repeated_position_step_fraction")], 1.0)
        self.assertEqual(features[FEATURE_NAMES.index("repeated_orientation_step_fraction")], 1.0)
        self.assertGreater(features[FEATURE_NAMES.index("longest_repeated_position_run_s")], 1.9)

    def test_invalid_shape_nonfinite_motion_or_bad_timestamps_fail(self) -> None:
        for kind in ("short", "nonfinite", "repeated_time", "large_gap"):
            with self.subTest(kind=kind):
                changed = deepcopy(self.records[0])
                if kind == "short":
                    changed["samples"].pop()
                elif kind == "nonfinite":
                    changed["samples"][5]["position_m"][0] = float("nan")
                elif kind == "repeated_time":
                    changed["samples"][5]["capture_time_ns"] = changed["samples"][4]["capture_time_ns"]
                else:
                    for sample in changed["samples"][5:]:
                        sample["capture_time_ns"] += 100_000_000
                with self.assertRaises(ValueError):
                    record_to_anomaly_features(changed)

    def test_source_weights_balance_sources_and_clean_transformed_mass(self) -> None:
        cases = small_cases("train")
        cases.pop()
        weights = source_balanced_weights(cases)
        self.assertAlmostEqual(weights.mean(), 1.0)
        totals = []
        for source in range(3):
            indexes = [index for index, case in enumerate(cases) if case["source_window_id"] == f"source-{source}"]
            clean = sum(weights[index] for index in indexes if not cases[index]["is_anomaly"])
            transformed = sum(weights[index] for index in indexes if cases[index]["is_anomaly"])
            self.assertAlmostEqual(clean, transformed)
            totals.append(clean + transformed)
        np.testing.assert_allclose(totals, totals[0])

    def test_source_weights_reject_missing_or_duplicate_clean_control(self) -> None:
        cases = small_cases()
        cases.pop(0)
        with self.assertRaises(ValueError):
            source_balanced_weights(cases)
        cases = small_cases()
        cases[1]["is_anomaly"] = False
        with self.assertRaises(ValueError):
            source_balanced_weights(cases)

    def test_training_is_reproducible_and_fits_scaler_from_weighted_train_only(self) -> None:
        cases = small_cases("train")
        generator = np.random.Generator(np.random.PCG64(88))
        features = generator.normal(size=(len(cases), 48))
        features[:, 0] = [int(case["is_anomaly"]) * 5 for case in cases]
        config = deepcopy(self.config)
        config["random_forest"]["n_estimators"] = 6
        first = fit_anomaly_models(features, cases, config, 6007)
        second = fit_anomaly_models(features, cases, config, 6007)
        expected_mean = np.average(features, axis=0, weights=source_balanced_weights(cases))
        np.testing.assert_allclose(first["logistic_regression"].named_steps["scaler"].mean_, expected_mean)
        for kind in first:
            np.testing.assert_array_equal(anomaly_scores(first[kind], features), anomaly_scores(second[kind], features))
        for split in ("validation", "test"):
            with self.assertRaises(ValueError):
                fit_anomaly_models(features, small_cases(split), config, 6007)

    def test_threshold_meets_validation_fpr_and_keeps_score_ties_together(self) -> None:
        cases = small_cases()
        scores = np.asarray([0.1, 0.8, 0.7] * 3)
        threshold = select_validation_threshold(scores, cases, 0.05)
        self.assertEqual(threshold["threshold"], 0.7)
        self.assertEqual(threshold["validation_clean_fpr"], 0.0)
        self.assertEqual(threshold["validation_source_weighted_f1"], 1.0)
        threshold = select_validation_threshold(np.ones(9), cases, 0.05)
        self.assertGreater(threshold["threshold"], 1.0)
        self.assertFalse((np.ones(9) >= threshold["threshold"]).any())

    def test_threshold_cannot_be_selected_from_train_or_test(self) -> None:
        for split in ("train", "test"):
            with self.assertRaises(ValueError):
                select_validation_threshold(np.ones(9) * 0.5, small_cases(split), 0.05)

    def test_binary_metrics_use_counts_not_average_percentages(self) -> None:
        measured = binary_metrics(np.asarray([0, 0, 1, 1, 1]), np.asarray([0, 1, 1, 1, 0]))
        self.assertEqual([measured[name] for name in ("true_positives", "false_positives", "true_negatives", "false_negatives")], [2, 1, 1, 1])
        self.assertAlmostEqual(measured["f1"], 2 / 3)
        self.assertEqual(measured["clean_false_positive_rate"], 0.5)

    def test_bootstrap_resamples_sources_reproducibly_not_individual_copies(self) -> None:
        cases = small_cases("test")
        flags = np.asarray([False, True, False] * 3)
        first = source_cluster_intervals(cases, flags, 30, 7007)
        second = source_cluster_intervals(cases, flags, 30, 7007)
        self.assertEqual(first, second)
        self.assertEqual(first["source_count"], 3)
        self.assertEqual(first["percentile_95_intervals"]["recall"], [0.5, 0.5])


if __name__ == "__main__":
    unittest.main()
