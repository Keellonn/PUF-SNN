"""Permanent regression checks for the paired legitimate-nod diagnostic."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from puf_snn.data.generator import generate_records
from puf_snn import nod_diagnostics as diagnostics


ROOT = Path(__file__).resolve().parents[1]


def fixture_sweep(sources):
    configuration = {"model_seeds": [7, 17, 27], "nod_sweep": {
        "amplitude_scales": list(diagnostics.AMPLITUDES), "speed_scales": list(diagnostics.SPEEDS)}}
    rows = []
    for family in ("logistic_regression", "random_forest", "snn"):
        for seed in configuration["model_seeds"]:
            for split in ("validation", "test"):
                count = sum(record["split"] == split and record["label"] == "nod" for record in sources)
                matrix = [[0] * 5 for _ in range(5)]
                matrix[0][0] = count
                for amplitude in diagnostics.AMPLITUDES:
                    for speed in diagnostics.SPEEDS:
                        rows.append({"model": f"{family}_seed_{seed}", "split": split,
                                     "amplitude_scale": amplitude, "speed_scale": speed,
                                     "duration_scale": 1 / speed, "sample_count": count,
                                     "nod_recall": 1.0, "still_prediction_fraction": 0.0,
                                     "mean_peak_rotation_deg": 22 * amplitude,
                                     "mean_angular_speed_rms_deg_s": 30.0,
                                     "metrics": {"sample_count": count, "confusion_matrix": deepcopy(matrix)}})
    return {"runs": rows}, configuration


class NodDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pilot = json.loads((ROOT / "configs/pilot.json").read_text(encoding="utf-8"))
        cls.pilot = deepcopy(cls.pilot)
        cls.pilot["synthetic_data"].update(device_profiles=1, trials_per_class_per_session=1)
        cls.sources = generate_records(cls.pilot)

    def setUp(self):
        self.sweep, self.configuration = fixture_sweep(self.sources)

    def test_half_and_tenth_coefficients_have_explicit_units(self):
        half = diagnostics.nominal_values(self.pilot, .5, 1)
        tenth = diagnostics.nominal_values(self.pilot, .1, 1)
        self.assertEqual(half["nominal_rotation_coefficient_deg"], -11)
        self.assertEqual(half["nominal_vertical_position_coefficient_m"], .003)
        self.assertAlmostEqual(tenth["nominal_rotation_coefficient_deg"], -2.2)
        self.assertAlmostEqual(tenth["nominal_vertical_position_coefficient_m"], .0006)

    def test_pilot_and_noise_are_not_changed(self):
        original = deepcopy(self.pilot)
        changed = diagnostics.nod_config(self.pilot, .1, 1.25)
        self.assertEqual(self.pilot, original)
        expected = deepcopy(original)
        expected["synthetic_motion"]["classes"]["nod"]["peak_rotation_deg"] *= .1
        expected["synthetic_motion"]["classes"]["nod"]["vertical_position_peak_m"] *= .1
        expected["synthetic_motion"]["motion_duration_s_range"] = [value / 1.25 for value in original["synthetic_motion"]["motion_duration_s_range"]]
        self.assertEqual(changed, expected)

    def test_unplanned_amplitude_or_speed_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "predeclared"):
            diagnostics.nod_config(self.pilot, .2, 1)
        with self.assertRaisesRegex(ValueError, "predeclared"):
            diagnostics.nod_config(self.pilot, .5, 2)

    def test_amplitude_one_speed_one_regenerates_original(self):
        self.assertEqual(generate_records(diagnostics.nod_config(self.pilot, 1, 1)), self.sources)

    def test_amplitude_change_does_not_change_non_nod_draws(self):
        changed = generate_records(diagnostics.nod_config(self.pilot, .1, 1))
        self.assertEqual([record for record in changed if record["label"] != "nod"],
                         [record for record in self.sources if record["label"] != "nod"])

    def test_nod_sources_stay_paired_at_every_speed(self):
        for speed in diagnostics.SPEEDS:
            changed = [record for record in generate_records(diagnostics.nod_config(self.pilot, .1, speed)) if record["label"] == "nod"]
            diagnostics.assert_paired_sources(changed, self.sources)

    def test_moved_split_is_rejected(self):
        changed = [deepcopy(record) for record in self.sources if record["label"] == "nod"]
        changed[0]["split"] = "test"
        with self.assertRaisesRegex(ValueError, "split changed"):
            diagnostics.assert_paired_sources(changed, self.sources)

    def test_timing_changes_are_not_silently_allowed(self):
        changed = [deepcopy(record) for record in self.sources if record["label"] == "nod"]
        changed[0]["samples"][1]["capture_time_ns"] += 1
        with self.assertRaisesRegex(ValueError, "capture_time_ns changed"):
            diagnostics.assert_paired_sources(changed, self.sources)

    def test_duplicate_source_does_not_expand_denominator(self):
        changed = [deepcopy(record) for record in self.sources if record["label"] == "nod"]
        changed.append(deepcopy(changed[0]))
        with self.assertRaisesRegex(ValueError, "mapping differs"):
            diagnostics.assert_paired_sources(changed, self.sources)

    def test_example_selection_is_order_independent(self):
        self.assertEqual(diagnostics.example_source_ids(self.sources), diagnostics.example_source_ids(list(reversed(self.sources))))
        examples = diagnostics.example_source_ids(self.sources)
        self.assertEqual(set(examples), {"validation:nod", "validation:still", "test:nod", "test:still"})

    def test_all_existing_classifier_families_and_conditions_are_retained(self):
        rows = diagnostics.validate_saved_sweep(self.sweep, self.configuration, self.sources)
        self.assertEqual(len(rows), 270)
        self.assertEqual({row["model"].rsplit("_seed_", 1)[0] for row in rows}, {"logistic_regression", "random_forest", "snn"})

    def test_missing_historical_condition_stops_reporting(self):
        self.sweep["runs"].pop()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            diagnostics.validate_saved_sweep(self.sweep, self.configuration, self.sources)

    def test_duplicate_historical_condition_stops_reporting(self):
        self.sweep["runs"].append(deepcopy(self.sweep["runs"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            diagnostics.validate_saved_sweep(self.sweep, self.configuration, self.sources)

    def test_changed_rates_do_not_override_saved_counts(self):
        self.sweep["runs"][0]["nod_recall"] = .9
        with self.assertRaisesRegex(ValueError, "disagree with counts"):
            diagnostics.validate_saved_sweep(self.sweep, self.configuration, self.sources)

    def test_other_predictions_are_not_called_still(self):
        row = self.sweep["runs"][0]
        row["metrics"]["confusion_matrix"][0] = [0, 1, 0, 0, 0]
        row["nod_recall"] = 0
        result = diagnostics.validate_saved_sweep(self.sweep, self.configuration, self.sources)[0]
        self.assertEqual(result["still_prediction_count"], 0)
        self.assertEqual(result["other_prediction_count"], 1)

    def test_frozen_scores_use_inclusive_threshold_without_fitting(self):
        thresholds = {"model": {"threshold": .5}}
        scores = diagnostics.score_fixed_detectors(np.zeros((3, 48)), {"model": object()}, thresholds,
                                                  lambda model, features: np.array([.49, .5, .51]))
        self.assertEqual(scores["model"]["flags"].tolist(), [False, True, True])
        self.assertEqual(thresholds["model"]["threshold"], .5)

    def test_nonfinite_or_wrong_shape_scores_stop(self):
        for values in ([.5, float("nan")], [.5], [.5, 1.1]):
            with self.assertRaisesRegex(ValueError, "detector scores"):
                diagnostics.score_fixed_detectors(np.zeros((2, 48)), {"model": object()}, {"model": {"threshold": .5}}, lambda model, features: values)

    def test_attack_metadata_cannot_be_extra_feature_channels(self):
        with self.assertRaisesRegex(ValueError, "48"):
            diagnostics.score_fixed_detectors(np.zeros((2, 49)), {}, {}, lambda model, features: [])

    def test_flag_rates_are_legitimate_variation_not_attack_recall(self):
        result = diagnostics.summarize_flags(1, 3, 4, lambda successes, count: [0, 1])
        self.assertEqual(result["pre_tag_quality_blocked_count"], 1)
        self.assertEqual(result["legitimate_variant_unflagged_count"], 2)
        self.assertIn("not adversarial", result["interpretation"])
        self.assertNotIn("true_positives", result)

    def test_no_eligible_nod_cases_have_no_rate(self):
        result = diagnostics.summarize_flags(0, 0, 1, lambda successes, count: None)
        self.assertIsNone(result["legitimate_variant_flag_rate"])
        self.assertIsNone(result["flag_rate_ci_low"])

    def test_model_hashes_are_checked_before_any_pickle_load(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            (directory / "models").mkdir()
            names = ("anomaly_first", "anomaly_second")
            for name in names:
                (directory / "models" / f"{name}.joblib").write_bytes(b"trusted-local-fixture")
            manifest = {"artifacts": {f"models/{name}.joblib": diagnostics.sha256(directory / "models" / f"{name}.joblib") for name in names}}
            manifest["artifacts"]["models/anomaly_second.joblib"] = "0" * 64
            calls = []
            with self.assertRaisesRegex(ValueError, "hash-mismatched"):
                diagnostics.load_verified_detectors(directory, manifest, {name: {} for name in names}, (), lambda path: calls.append(path))
            self.assertEqual(calls, [])

    def test_model_metadata_must_match_frozen_threshold(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            (directory / "models").mkdir()
            path = directory / "models/anomaly_model.joblib"
            path.write_bytes(b"trusted-local-fixture")
            manifest = {"artifacts": {"models/anomaly_model.joblib": diagnostics.sha256(path)}}
            threshold = {"kind": "fixture", "seed": 6007, "threshold": .5, "selected_from": "validation"}
            wrong = {"model": object(), "feature_names": ("feature",), "seed": 6007,
                     "threshold": {"threshold": .4, "selected_from": "validation"}}
            with self.assertRaisesRegex(ValueError, "metadata differs"):
                diagnostics.load_verified_detectors(directory, manifest, {"anomaly_model": threshold}, ("feature",), lambda path: wrong)


if __name__ == "__main__":
    unittest.main()
