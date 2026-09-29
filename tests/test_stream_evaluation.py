"""these tests check plan reconciliation, paired inputs and the composite accepted-window consumer"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

from puf_snn.attacks.evaluation import assert_case_split_separation, assert_plan_matches, composite_consumer, construct_cohorts, evaluate_authenticated_cases, prepare_model_inputs, summarize_construction, summarize_predictions
from puf_snn.attacks.stream import apply_stream_attack, iter_attack_cases
from puf_snn.auth.config import AuthConfig
from puf_snn.auth.session import Failure
from puf_snn.data.generator import generate_records
from puf_snn.integration import ExactlyOnceClassifierRelease, processed_record_to_wire_window

ROOT = Path(__file__).resolve().parents[1]
ATTACK_CONFIG = ROOT / "configs/stream_attacks.json"
EVALUATION_CONFIG = ROOT / "configs/stream_evaluation.json"
sys.path.insert(0, str(ROOT / "src/python/scripts"))
from run_layer3_demo import establish, initialize_material
from evaluate_stream_attacks import bind_recovery_context, check_artifacts, save_detection_figures, write_json, write_rows


class MotionStub:
    def __init__(self):
        self.calls = 0

    def predict(self, values):
        self.calls += 1
        return np.asarray(["nod"] * len(values))


class AnomalyStub:
    classes_ = np.asarray([0, 1])

    def __init__(self):
        self.calls = 0

    def predict_proba(self, values):
        self.calls += 1
        return np.tile([0.2, 0.8], (len(values), 1))


class StreamEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pilot = json.loads((ROOT / "configs/pilot.json").read_text(encoding="utf-8"))
        pilot["synthetic_data"]["device_profiles"] = 1
        pilot["synthetic_data"]["trials_per_class_per_session"] = 1
        cls.records = generate_records(pilot)
        cls.attack_config = json.loads(ATTACK_CONFIG.read_text(encoding="utf-8"))
        cls.evaluation_config = json.loads(EVALUATION_CONFIG.read_text(encoding="utf-8"))
        cls.material = initialize_material()

    def models(self):
        motion = MotionStub()
        anomaly = AnomalyStub()
        models = {"motion": {"kind": "logistic_regression", "seed": 7, "model": motion}}
        detectors = {"anomaly": {"kind": "random_forest", "seed": 6007, "model": anomaly, "threshold": {"threshold": 0.5}}}
        return models, detectors, motion, anomaly

    def test_saved_plan_must_match_every_reproducible_case(self) -> None:
        planned = list(iter_attack_cases(self.records, self.attack_config))
        assert_plan_matches(self.records, self.attack_config, planned)
        for change in ("missing", "seed", "duplicate"):
            altered = deepcopy(planned)
            if change == "missing":
                altered.pop()
            elif change == "seed":
                altered[5]["derived_seed"] += 1
            else:
                altered.append(altered[0])
            with self.assertRaises(ValueError):
                assert_plan_matches(self.records, self.attack_config, altered)

    def test_source_split_leakage_and_duplicate_cases_are_rejected(self) -> None:
        planned = list(iter_attack_cases(self.records, self.attack_config))
        assert_case_split_separation(planned)
        with self.assertRaises(ValueError):
            assert_case_split_separation(planned + [planned[0]])
        changed = deepcopy(planned)
        changed[1]["split"] = "test" if changed[0]["split"] != "test" else "train"
        with self.assertRaises(ValueError):
            assert_case_split_separation(changed)

    def test_full_construction_keeps_failures_and_split_denominators(self) -> None:
        planned = list(iter_attack_cases(self.records, self.attack_config))
        cohorts, outcomes = construct_cohorts(self.records, planned)
        summary = summarize_construction(outcomes)
        self.assertEqual(sum(row["planned"] for row in summary.values()), len(planned))
        failures = sum(row["status"] != "quality_valid" for row in outcomes)
        self.assertGreater(failures, 0)
        self.assertEqual(sum(len(group["cases"]) for group in cohorts.values()) + failures, len(planned))
        for split, group in cohorts.items():
            self.assertEqual(sum(not case["is_anomaly"] for case in group["cases"]), 5)
            self.assertEqual(group["sequences"].shape[1:], (120, 7))
            self.assertEqual(group["anomaly_features"].shape[1:], (48,))
            self.assertTrue(all(case["split"] == split for case in group["cases"]))

    def test_composite_callback_runs_both_models_from_one_input(self) -> None:
        models, detectors, motion, anomaly = self.models()
        record = self.records[0]
        result = composite_consumer(models, detectors)(prepare_model_inputs(record))
        self.assertEqual(motion.calls, 1)
        self.assertEqual(anomaly.calls, 1)
        self.assertEqual(result["motion"]["motion"], 0)
        self.assertTrue(result["anomaly"]["anomaly"]["flag"])

    def test_rejected_tag_calls_neither_model_and_valid_next_window_still_delivers(self) -> None:
        models, detectors, motion, anomaly = self.models()
        sender, verifier, _ = establish(AuthConfig(), self.material)
        gate = ExactlyOnceClassifierRelease(verifier, prepare_model_inputs, composite_consumer(models, detectors))
        try:
            packet = sender.seal_window(processed_record_to_wire_window(self.records[0]))
            wrapper = json.loads(packet)
            tag = wrapper["authentication"]["tag_hex"]
            wrapper["authentication"]["tag_hex"] = ("0" if tag[0] != "0" else "1") + tag[1:]
            rejected = verifier.verify_window(json.dumps(wrapper).encode("utf-8"))
            self.assertEqual(rejected.result, "reject")
            with self.assertRaises(ValueError):
                gate.deliver(rejected)
            self.assertEqual((motion.calls, anomaly.calls), (0, 0))
            self.assertEqual(verifier.session_status(sender.session_id).accepted_count, 0)
            accepted = verifier.verify_window(packet)
            gate.deliver(accepted)
            self.assertEqual((motion.calls, anomaly.calls), (1, 1))
            with self.assertRaises(ValueError):
                gate.deliver(accepted)
            self.assertEqual((motion.calls, anomaly.calls), (1, 1))
            self.assertEqual(verifier.session_status(sender.session_id).last_accepted, 0)
        finally:
            verifier.close_all_sessions()

    def test_anomaly_flag_does_not_roll_back_accepted_sequence(self) -> None:
        models, detectors, motion, anomaly = self.models()
        sender, verifier, _ = establish(AuthConfig(), self.material)
        gate = ExactlyOnceClassifierRelease(verifier, prepare_model_inputs, composite_consumer(models, detectors))
        try:
            for sequence in range(2):
                packet = sender.seal_window(processed_record_to_wire_window(self.records[sequence]))
                accepted = verifier.verify_window(packet)
                result = gate.deliver(accepted)
                self.assertTrue(result["anomaly"]["anomaly"]["flag"])
                self.assertEqual(verifier.session_status(sender.session_id).last_accepted, sequence)
            self.assertEqual((motion.calls, anomaly.calls), (2, 2))
        finally:
            verifier.close_all_sessions()

    def test_authenticated_evaluation_reconciles_inputs_and_rotates_short_sessions(self) -> None:
        source = next(record for record in self.records if record["split"] == "test")
        cases = [case for case in iter_attack_cases([source], self.attack_config) if case["attack_type"] in ("clean", "position_jump") and case["severity"] in ("clean", "medium")]
        inputs = [prepare_model_inputs(apply_stream_attack(source, case)["record"]) for case in cases]
        cohort = {"cases": cases, "sequences": np.stack([item[0] for item in inputs]), "anomaly_features": np.stack([item[1] for item in inputs])}
        models, detectors, motion, anomaly = self.models()
        result = evaluate_authenticated_cases([source], cohort, models, detectors, AuthConfig(), establish, self.material, 1)
        self.assertEqual(result["session_count"], len(cases))
        self.assertEqual(len(result["evidence"]), len(cases))
        self.assertTrue(all(row["accepted_model_inputs_match"] for row in result["evidence"]))
        self.assertEqual((motion.calls, anomaly.calls), (len(cases), len(cases)))
        self.assertTrue(all(row["sequence_number"] == 0 for row in result["evidence"]))
        config = deepcopy(self.evaluation_config)
        config["bootstrap_repetitions"] = 10
        report = summarize_predictions(cases, result["motion"], result["anomaly"], config)
        self.assertEqual(report["source_count"], 1)
        self.assertEqual(report["anomaly"]["anomaly"]["all_quality_valid"]["sample_count"], len(cases))

    def test_artifact_check_rejects_modified_files_and_directory_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            path = directory / "sample.json"
            path.write_text("{}", encoding="utf-8")
            manifest = {"artifacts": {"sample.json": hashlib.sha256(path.read_bytes()).hexdigest()}}
            check_artifacts(directory, manifest, ["sample.json"])
            path.write_text('{"changed":true}', encoding="utf-8")
            with self.assertRaises(ValueError):
                check_artifacts(directory, manifest, ["sample.json"])
            with self.assertRaises(ValueError):
                check_artifacts(directory, manifest, ["../sample.json"])

    def small_test_cohort(self) -> tuple[dict, dict]:
        source = next(record for record in self.records if record["split"] == "test")
        cases = [case for case in iter_attack_cases([source], self.attack_config) if case["attack_type"] in ("clean", "position_jump") and case["severity"] in ("clean", "medium")]
        return source, {"cases": cases}

    def test_session_renews_by_elapsed_time_before_the_case_limit(self) -> None:
        source, cohort = self.small_test_cohort()
        models, detectors, motion, anomaly = self.models()
        now = [1_000_000_000]
        original = motion.predict
        def slow_predict(values):
            result = original(values)
            now[0] += 241_000_000_000
            return result
        motion.predict = slow_predict
        with patch("time.monotonic_ns", side_effect=lambda: now[0]):
            result = evaluate_authenticated_cases([source], cohort, models, detectors, AuthConfig(), establish, self.material, 100)
        self.assertEqual(result["session_count"], 2)
        self.assertEqual([row["sequence_number"] for row in result["evidence"]], [0, 0])
        self.assertEqual((motion.calls, anomaly.calls), (2, 2))

    def test_sender_expiry_race_uses_a_new_session_without_duplicate_model_calls(self) -> None:
        source, cohort = self.small_test_cohort()
        models, detectors, motion, anomaly = self.models()
        establishments = [0]
        def expiring_establish(config, material):
            sender, verifier, elapsed = establish(config, material)
            establishments[0] += 1
            if establishments[0] == 1:
                original = sender.seal_window
                calls = [0]
                def seal(window):
                    calls[0] += 1
                    if calls[0] == 2:
                        expired_time = time.monotonic_ns() + 301_000_000_000
                        with patch("puf_snn.auth.sender.time.monotonic_ns", return_value=expired_time):
                            return original(window)
                    return original(window)
                sender.seal_window = seal
            return sender, verifier, elapsed
        with tempfile.TemporaryDirectory() as temporary:
            events = Path(temporary) / "session-events.jsonl"
            result = evaluate_authenticated_cases([source], cohort, models, detectors, AuthConfig(), expiring_establish, self.material, 100, session_events_path=events)
            observed = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(establishments[0], 2)
        self.assertEqual(observed[0]["reason"], "expired_session")
        self.assertEqual(observed[0]["classifier_calls_for_failed_attempt"], 0)
        self.assertEqual((motion.calls, anomaly.calls), (2, 2))
        self.assertEqual(len(result["evidence"]), 2)

    def test_verifier_expiry_race_retags_in_a_fresh_session_before_delivery(self) -> None:
        source, cohort = self.small_test_cohort()
        models, detectors, motion, anomaly = self.models()
        establishments = [0]
        def expiring_establish(config, material):
            sender, verifier, elapsed = establish(config, material)
            establishments[0] += 1
            if establishments[0] == 1:
                original = verifier.verify_window
                def verify(packet):
                    expired_time = time.monotonic_ns() + 301_000_000_000
                    with patch("puf_snn.auth.verifier.time.monotonic_ns", return_value=expired_time):
                        return original(packet)
                verifier.verify_window = verify
            return sender, verifier, elapsed
        result = evaluate_authenticated_cases([source], cohort, models, detectors, AuthConfig(), expiring_establish, self.material, 100)
        self.assertEqual(establishments[0], 2)
        self.assertEqual((motion.calls, anomaly.calls), (2, 2))
        self.assertEqual(len(result["evidence"]), 2)

    def test_other_sender_failures_are_not_hidden_by_session_retries(self) -> None:
        source, cohort = self.small_test_cohort()
        models, detectors, motion, anomaly = self.models()
        establishments = [0]
        def failed_establish(config, material):
            sender, verifier, elapsed = establish(config, material)
            establishments[0] += 1
            sender.seal_window = lambda window: Failure("invalid_payload_schema")
            return sender, verifier, elapsed
        with self.assertRaisesRegex(RuntimeError, "invalid_payload_schema"):
            evaluate_authenticated_cases([source], cohort, models, detectors, AuthConfig(), failed_establish, self.material, 100)
        self.assertEqual(establishments[0], 1)
        self.assertEqual((motion.calls, anomaly.calls), (0, 0))

    def test_checkpoint_resume_skips_already_completed_model_calls(self) -> None:
        source, cohort = self.small_test_cohort()
        models, detectors, motion, anomaly = self.models()
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint = Path(temporary) / "authentication-checkpoint.jsonl"
            first = evaluate_authenticated_cases([source], cohort, models, detectors, AuthConfig(), establish, self.material, 100, checkpoint_path=checkpoint)
            resumed = evaluate_authenticated_cases([source], cohort, models, detectors, AuthConfig(), establish, self.material, 100, checkpoint_path=checkpoint)
        self.assertEqual(resumed["reused_checkpoint_cases"], 2)
        self.assertEqual((motion.calls, anomaly.calls), (2, 2))
        self.assertEqual(first["evidence"], resumed["evidence"])

    def test_checkpoint_tampering_stops_before_model_execution(self) -> None:
        source, cohort = self.small_test_cohort()
        models, detectors, motion, anomaly = self.models()
        with tempfile.TemporaryDirectory() as temporary:
            checkpoint = Path(temporary) / "authentication-checkpoint.jsonl"
            evaluate_authenticated_cases([source], cohort, models, detectors, AuthConfig(), establish, self.material, 100, checkpoint_path=checkpoint)
            rows = [json.loads(line) for line in checkpoint.read_text(encoding="utf-8").splitlines()]
            rows[0]["prediction"]["motion"]["motion"] = 4
            checkpoint.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash chain"):
                evaluate_authenticated_cases([source], cohort, models, detectors, AuthConfig(), establish, self.material, 100, checkpoint_path=checkpoint)
        self.assertEqual((motion.calls, anomaly.calls), (2, 2))

    def test_checkpoint_context_rejects_changed_models_or_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            bind_recovery_context(output, {"input_sha256": "first", "model": "frozen"})
            bind_recovery_context(output, {"input_sha256": "first", "model": "frozen"})
            with self.assertRaises(ValueError):
                bind_recovery_context(output, {"input_sha256": "second", "model": "frozen"})

    def test_result_finalization_reuses_identical_files_but_never_overwrites_different_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            write_json(output / "result.json", {"value": 1})
            write_json(output / "result.json", {"value": 1})
            with self.assertRaises(ValueError):
                write_json(output / "result.json", {"value": 2})
            write_rows(output / "rows.jsonl", [{"value": 1}])
            write_rows(output / "rows.jsonl", [{"value": 1}])
            with self.assertRaises(ValueError):
                write_rows(output / "rows.jsonl", [{"value": 2}])

    def test_heatmap_marks_unconstructable_conditions_as_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            detectors = {"lr": {"kind": "logistic_regression"}, "rf": {"kind": "random_forest"}}
            report = {"anomaly": {"lr": {}, "rf": {}}}
            save_detection_figures(Path(temporary), report, detectors)
            self.assertTrue((Path(temporary) / "logistic_regression-detection-recall.png").is_file())
            self.assertTrue((Path(temporary) / "random_forest-detection-recall.png").is_file())


if __name__ == "__main__":
    unittest.main()
