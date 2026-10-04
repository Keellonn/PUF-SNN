"""Permanent checks for Tier-2 denominators, evidence joins and paired reporting."""

from copy import deepcopy
import json
import math
from pathlib import Path
import tempfile
import unittest

from puf_snn.attacks import reporting


def fixture():
    config = {"motion_model_seeds": [7], "anomaly_model_seeds": [6007],
              "validation_clean_fpr_limit": .05, "medium_high_detection_target": .9,
              "source_dataset_sha256": "test-dataset"}
    attack_config = {"attacks": [{"name": "position_noise"}], "severity_names": ["low", "medium", "high"],
                     "source_dataset_sha256": "test-dataset"}
    motion_names = [f"motion_{kind}_seed7" for kind in ("logistic_regression", "random_forest", "snn")]
    anomaly_names = [f"anomaly_{kind}_seed6007" for kind in ("logistic_regression", "random_forest")]
    thresholds = {name: {"kind": name.removeprefix("anomaly_").removesuffix("_seed6007"),
                         "seed": 6007, "threshold": .5, "validation_clean_fpr": 0.0,
                         "validation_clean_false_positives": 0, "validation_clean_count": 2,
                         "selected_from": "validation", "comparison": "score >= threshold"}
                  for name in anomaly_names}
    outcomes, predictions, evidence = [], [], []
    for split in ("train", "validation", "test"):
        for source_index, label in enumerate(("nod", "still")):
            source = f"{split}-source-{source_index}"
            for attack, severity in [("clean", "clean"), ("position_noise", "low"),
                                     ("position_noise", "medium"), ("position_noise", "high")]:
                failed = severity == "medium" or (severity == "high" and source_index == 1)
                row = {"case_id": f"{source}-{severity}", "source_window_id": source,
                       "source_trial_id": f"{source}-trial", "split": split,
                       "attack_type": attack, "severity": severity,
                       "status": "construction_failure" if failed else "quality_valid",
                       "reason": "source_gap_exceeds_50_ms" if failed else "ready_for_legitimate_sender"}
                outcomes.append(row)
                if failed or split != "test":
                    continue
                score = .8 if source_index == 0 and attack != "clean" else .2
                predicted = "still" if severity == "low" and source_index == 0 else label
                predictions.append({key: row[key] for key in ("case_id", "source_window_id", "source_trial_id", "attack_type", "severity")}
                                   | {"motion_label": label, "is_anomaly": attack != "clean",
                                      "motion": {name: predicted for name in motion_names},
                                      "anomaly": {name: {"score": score, "flag": score >= .5} for name in anomaly_names}})
                sequence = len(evidence)
                evidence.append({"case_id": row["case_id"], "source_window_id": source,
                                 "event_id": f"event-{sequence}", "session_id": "session-1", "sequence_number": sequence,
                                 "decision": "accept", "reason": "accepted", "accepted_model_inputs_match": True,
                                 "motion_model_calls": 3, "anomaly_model_calls": 2,
                                 "verifier_last_accepted_before_models": sequence,
                                 "verifier_last_accepted_after_models": sequence})
    return {"outcomes": outcomes, "authenticated": predictions, "unprotected": deepcopy(predictions),
            "evidence": evidence, "thresholds": thresholds, "config": config, "attack_config": attack_config}


def save_fixture(run: Path, data: dict):
    counts = reporting.construction_counts(data["outcomes"])
    reconciled = reporting.reconcile(**data)
    values = {"config.json": data["config"], "attack-config.json": data["attack_config"],
              "construction-summary.json": counts, "frozen-validation-thresholds.json": data["thresholds"],
              "results.json": {"construction": counts, "thresholds": data["thresholds"],
                               "boundary": {"accepted_test_cases": 5, "fresh_sessions": 1,
                                            "paired_model_inputs_match": True,
                                            "motion_prediction_differences": {"model": 0},
                                            "anomaly_flag_differences": {"detector": 0}}},
              "COMPLETE": {"source_commit": "historical", "planned_cases": 24, "test_accepted_cases": 5}}
    for name, value in values.items():
        (run / name).write_text(json.dumps(value), encoding="utf-8")
    for name, rows in {"construction-outcomes.jsonl": data["outcomes"],
                       "authenticated-test-predictions.jsonl": data["authenticated"],
                       "unauthenticated-test-predictions.jsonl": data["unprotected"],
                       "accepted-delivery-evidence.jsonl": data["evidence"]}.items():
        (run / name).write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    manifest = {"artifacts": {name: reporting.sha256(run / name) for name in reporting.INPUT_ARTIFACTS},
                "input_sha256": "test-dataset", "source_commit": "historical"}
    (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return reconciled


class StreamReportingTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()

    def test_complete_evidence_reconciles_without_models(self):
        result = reporting.reconcile(**self.data)
        self.assertEqual(result["planned_cases"], 24)
        self.assertEqual(result["accepted_test_cases"], 5)
        self.assertEqual(result["fresh_sessions"], 1)

    def test_missing_predicted_case_is_not_silently_dropped(self):
        self.data["authenticated"].pop()
        with self.assertRaisesRegex(ValueError, "do not match"):
            reporting.reconcile(**self.data)

    def test_missing_planned_condition_is_rejected(self):
        self.data["outcomes"].pop()
        with self.assertRaisesRegex(ValueError, "incomplete planned"):
            reporting.reconcile(**self.data)

    def test_duplicate_case_identifier_is_rejected(self):
        self.data["outcomes"].append(deepcopy(self.data["outcomes"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate case_id"):
            reporting.reconcile(**self.data)

    def test_duplicate_source_condition_is_rejected(self):
        row = deepcopy(self.data["outcomes"][0])
        row["case_id"] = "different-id"
        self.data["outcomes"].append(row)
        with self.assertRaisesRegex(ValueError, "source condition"):
            reporting.reconcile(**self.data)

    def test_source_cannot_cross_splits(self):
        self.data["outcomes"][-1]["source_window_id"] = self.data["outcomes"][0]["source_window_id"]
        with self.assertRaisesRegex(ValueError, "crosses splits"):
            reporting.reconcile(**self.data)

    def test_source_trial_cannot_have_multiple_window_clusters(self):
        self.data["outcomes"][-1]["source_trial_id"] = self.data["outcomes"][-5]["source_trial_id"]
        with self.assertRaisesRegex(ValueError, "multiple windows"):
            reporting.reconcile(**self.data)

    def test_duplicate_release_event_is_rejected(self):
        self.data["evidence"][-1]["event_id"] = self.data["evidence"][0]["event_id"]
        with self.assertRaisesRegex(ValueError, "duplicate accepted"):
            reporting.reconcile(**self.data)

    def test_duplicate_session_sequence_is_rejected(self):
        self.data["evidence"][-1]["sequence_number"] = self.data["evidence"][0]["sequence_number"]
        with self.assertRaisesRegex(ValueError, "duplicate accepted"):
            reporting.reconcile(**self.data)

    def test_sequence_must_be_committed_before_models(self):
        self.data["evidence"][0]["verifier_last_accepted_before_models"] = -1
        with self.assertRaisesRegex(ValueError, "delivery evidence"):
            reporting.reconcile(**self.data)

    def test_model_call_counts_are_checked(self):
        self.data["evidence"][0]["anomaly_model_calls"] = 0
        with self.assertRaisesRegex(ValueError, "delivery evidence"):
            reporting.reconcile(**self.data)

    def test_authenticated_predictions_must_match(self):
        name = next(iter(self.data["authenticated"][0]["motion"]))
        self.data["authenticated"][0]["motion"][name] = "shake"
        with self.assertRaisesRegex(ValueError, "motion predictions differ"):
            reporting.reconcile(**self.data)

    def test_flags_must_match_frozen_threshold(self):
        name = next(iter(self.data["thresholds"]))
        self.data["authenticated"][0]["anomaly"][name]["flag"] = True
        with self.assertRaisesRegex(ValueError, "frozen threshold"):
            reporting.reconcile(**self.data)

    def test_threshold_must_be_validation_only(self):
        name = next(iter(self.data["thresholds"]))
        self.data["thresholds"][name]["selected_from"] = "test"
        with self.assertRaisesRegex(ValueError, "validation-only"):
            reporting.reconcile(**self.data)

    def test_nonfinite_anomaly_score_is_rejected(self):
        name = next(iter(self.data["thresholds"]))
        self.data["authenticated"][0]["anomaly"][name]["score"] = math.nan
        with self.assertRaisesRegex(ValueError, "score or flag"):
            reporting.reconcile(**self.data)

    def test_case_metadata_cannot_be_relabelled(self):
        self.data["authenticated"][0]["attack_type"] = "position_noise"
        with self.assertRaisesRegex(ValueError, "metadata differs"):
            reporting.reconcile(**self.data)

    def test_transformed_labels_must_match_clean_source(self):
        for field in ("authenticated", "unprotected"):
            self.data[field][1]["motion_label"] = "shake"
        with self.assertRaisesRegex(ValueError, "differs from clean source"):
            reporting.reconcile(**self.data)

    def test_failure_is_not_counted_as_detector_miss(self):
        self.data["reconciliation"] = reporting.reconcile(**self.data)
        result = reporting.build_breakdown(self.data, 10)
        high = next(row for row in result["detectors"] if row["severity"] == "high")
        self.assertEqual(high["planned_count"], 2)
        self.assertEqual(high["pre_tag_blocked_count"], 1)
        self.assertEqual(high["anomaly_detected_count"], 1)
        self.assertEqual(high["missed_count"], 0)
        self.assertEqual(high["verifier_rejected_count"], 0)

    def test_empty_condition_has_no_rate_or_confidence_interval(self):
        self.data["reconciliation"] = reporting.reconcile(**self.data)
        result = reporting.build_breakdown(self.data, 10)
        empty = next(row for row in result["detectors"] if row["severity"] == "medium")
        self.assertIsNone(empty["flag_rate"])
        self.assertIsNone(empty["ci_low"])
        self.assertIsNone(empty["medium_high_recall_target_met"])

    def test_clean_row_reports_fpr_not_attack_success(self):
        self.data["reconciliation"] = reporting.reconcile(**self.data)
        result = reporting.build_breakdown(self.data, 10)
        clean = next(row for row in result["detectors"] if row["severity"] == "clean")
        self.assertEqual(clean["rate_kind"], "clean_false_positive_rate")
        self.assertIsNone(clean["anomaly_detected_count"])

    def test_motion_comparison_uses_same_eligible_sources(self):
        self.data["reconciliation"] = reporting.reconcile(**self.data)
        result = reporting.build_breakdown(self.data, 10)
        high = next(row for row in result["motion"] if row["severity"] == "high")
        low = next(row for row in result["motion"] if row["severity"] == "low")
        self.assertEqual(high["quality_valid_count"], 1)
        self.assertEqual(high["matched_clean_accuracy"], 1.0)
        self.assertEqual(low["accuracy_loss"], .5)

    def test_fixed_label_confusion_matrix_includes_absent_classes(self):
        result = reporting.classification_metrics(["nod"], ["nod"])
        self.assertEqual(result["macro_f1"], .2)
        self.assertEqual(result["per_class"]["still"]["support"], 0)
        self.assertEqual(len(result["confusion_matrix"]), 5)

    def test_exact_interval_has_nonzero_uncertainty_at_endpoints(self):
        interval = reporting.binomial_interval(0, 100)
        self.assertEqual(interval[0], 0)
        self.assertAlmostEqual(interval[1], 1 - .025 ** .01)
        success = reporting.binomial_interval(100, 100)
        self.assertAlmostEqual(success[0], .025 ** .01)
        self.assertEqual(success[1], 1)
        self.assertIsNone(reporting.binomial_interval(0, 0))

    def test_exact_interval_matches_known_symmetric_case(self):
        low, high = reporting.binomial_interval(5, 10)
        self.assertAlmostEqual(low, .18708602844739855)
        self.assertAlmostEqual(high, .8129139715526015)

    def test_bootstrap_keeps_pairs_and_is_reproducible(self):
        first = reporting.paired_accuracy_interval([True, False], [False, False], 100, 7017)
        second = reporting.paired_accuracy_interval([True, False], [False, False], 100, 7017)
        self.assertEqual(first, second)
        self.assertEqual(reporting.paired_accuracy_interval([True, False], [True, False], 100, 7017), [0, 0])

    def test_old_inputs_are_not_modified_or_models_required(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            save_fixture(run, self.data)
            before = {path.name: reporting.sha256(path) for path in run.iterdir()}
            loaded = reporting.load_saved_run(run)
            self.assertEqual(loaded["reconciliation"]["accepted_test_cases"], 5)
            self.assertEqual(len(loaded["verified_input_sha256"]), 9)
            self.assertEqual(before, {path.name: reporting.sha256(path) for path in run.iterdir()})
            self.assertFalse((run / "models").exists())

    def test_changed_historical_hash_stops_reporting(self):
        with tempfile.TemporaryDirectory() as folder:
            run = Path(folder)
            save_fixture(run, self.data)
            with (run / "construction-outcomes.jsonl").open("a", encoding="utf-8") as stream:
                stream.write("{}\n")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                reporting.load_saved_run(run)


if __name__ == "__main__":
    unittest.main()
