"""these tests check the permanent Tier 2 transforms, split safety and accepted-window boundary"""

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

import numpy as np

from puf_snn.attacks.stream import ATTACK_UNITS, _resample, apply_stream_attack, canonical_motion_record, iter_attack_cases, validate_attack_config
from puf_snn.auth.binary_window import encode_window
from puf_snn.auth.config import AuthConfig
from puf_snn.data.generator import generate_records
from puf_snn.data.validation import make_schema_validator, validate_record
from puf_snn.integration import ExactlyOnceClassifierRelease, processed_record_to_wire_window
from puf_snn.snn.dataset import record_to_sequence

ROOT = Path(__file__).resolve().parents[1]
ATTACK_CONFIG = ROOT / "configs/stream_attacks.json"
sys.path.insert(0, str(ROOT / "src/python/scripts"))
from run_layer3_demo import establish, initialize_material


class StreamAttackFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(ATTACK_CONFIG.read_text(encoding="utf-8"))
        pilot = json.loads((ROOT / "configs/pilot.json").read_text(encoding="utf-8"))
        pilot["synthetic_data"]["device_profiles"] = 1
        pilot["synthetic_data"]["trials_per_class_per_session"] = 1
        cls.records = generate_records(pilot)
        schema = json.loads((ROOT / "schemas/quest-window.schema.json").read_text(encoding="utf-8"))
        cls.validator = make_schema_validator(schema)

    def case_for(self, attack: str, severity: str = "medium", record: dict | None = None) -> dict:
        source = self.records[0] if record is None else record
        return next(case for case in iter_attack_cases([source], self.config) if case["attack_type"] == attack and (attack == "clean" or case["severity"] == severity))


class StreamAttackTests(StreamAttackFixture):
    def test_configuration_has_all_documented_attacks_and_distinct_seed(self) -> None:
        validate_attack_config(self.config)
        self.assertEqual({attack["name"] for attack in self.config["attacks"]}, set(ATTACK_UNITS))
        self.assertNotIn(self.config["attack_generation_seed"], (7, 17, 27, 107, 117, 127))

    def test_configuration_rejects_unknown_duplicate_or_invalid_settings(self) -> None:
        for field, value in (("attack_generation_seed", True), ("magnitude_scale_range", [1.2, 0.8]), ("injection_stage", "after_tag")):
            with self.subTest(field=field):
                changed = deepcopy(self.config)
                changed[field] = value
                with self.assertRaises(ValueError):
                    validate_attack_config(changed)
        changed = deepcopy(self.config)
        changed["attacks"][0] = deepcopy(changed["attacks"][1])
        with self.assertRaises(ValueError):
            validate_attack_config(changed)

    def test_plan_has_one_clean_and_twenty_seven_transformed_cases_per_source(self) -> None:
        cases = list(iter_attack_cases(self.records, self.config))
        self.assertEqual(len(cases), len(self.records) * 28)
        self.assertEqual(len({case["case_id"] for case in cases}), len(cases))
        self.assertEqual(sum(not case["is_anomaly"] for case in cases), len(self.records))

    def test_source_order_does_not_change_seeded_cases(self) -> None:
        first = {case["case_id"]: case for case in iter_attack_cases(self.records, self.config)}
        second = {case["case_id"]: case for case in iter_attack_cases(list(reversed(self.records)), self.config)}
        self.assertEqual(first, second)

    def test_attack_seed_changes_cases_without_changing_splits(self) -> None:
        changed = deepcopy(self.config)
        changed["attack_generation_seed"] += 1
        first = list(iter_attack_cases(self.records, self.config))
        second = list(iter_attack_cases(self.records, changed))
        self.assertNotEqual(first[1]["derived_seed"], second[1]["derived_seed"])
        self.assertEqual([case["split"] for case in first], [case["split"] for case in second])

    def test_magnitudes_vary_within_predeclared_ranges(self) -> None:
        cases = [case for case in iter_attack_cases(self.records, self.config) if case["is_anomaly"]]
        scales = [case["magnitude"] / case["nominal_magnitude"] for case in cases]
        self.assertTrue(all(0.8 <= value <= 1.2 for value in scales))
        self.assertGreater(len(set(scales)), 20)

    def test_duplicate_sources_and_cross_split_source_or_session_reuse_fail(self) -> None:
        source = self.records[0]
        with self.assertRaises(ValueError):
            list(iter_attack_cases([source, source], self.config))
        for field in ("source_trial_id", "session_id"):
            changed = deepcopy(next(record for record in self.records if record["split"] == "test"))
            changed[field] = source[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                list(iter_attack_cases([source, changed], self.config))

    def test_transform_is_reproducible_and_does_not_mutate_source(self) -> None:
        source = self.records[0]
        before = deepcopy(source)
        for name in ATTACK_UNITS:
            case = self.case_for(name)
            with self.subTest(attack=name):
                self.assertEqual(apply_stream_attack(source, case), apply_stream_attack(source, case))
        self.assertEqual(source, before)

    def test_source_motion_change_invalidates_saved_plan_binding(self) -> None:
        source = deepcopy(self.records[0])
        case = self.case_for("position_noise", record=source)
        source["samples"][5]["position_m"][0] += 0.01
        with self.assertRaises(ValueError):
            apply_stream_attack(source, case)

    def test_case_cannot_be_applied_to_wrong_source_or_split(self) -> None:
        case = self.case_for("position_noise")
        with self.assertRaises(ValueError):
            apply_stream_attack(self.records[1], case)
        changed = deepcopy(self.records[0])
        changed["split"] = "test"
        with self.assertRaises(ValueError):
            apply_stream_attack(changed, case)

    def test_all_quality_valid_outputs_match_schema_and_wire_quality(self) -> None:
        for case in iter_attack_cases(self.records, self.config):
            source = next(record for record in self.records if record["window_id"] == case["source_window_id"])
            result = apply_stream_attack(source, case)
            with self.subTest(attack=case["attack_type"], severity=case["severity"]):
                if result["record"] is None:
                    self.assertIn(result["status"], ("construction_failure", "quality_failure"))
                    continue
                record = result["record"]
                self.assertEqual(validate_record(record, self.validator), [])
                encode_window(processed_record_to_wire_window(record))
                self.assertEqual(record["split"], source["split"])
                self.assertEqual(record["source_trial_id"], source["source_trial_id"])
                self.assertEqual(record["trial_id"], source["trial_id"])
                self.assertEqual(record["label"], source["label"])
                self.assertEqual(record["sequence_number"], source["sequence_number"])
                self.assertEqual(result["authentication_result"], "not_attempted")

    def test_clean_control_uses_the_same_binary32_conversion(self) -> None:
        source = self.records[0]
        result = apply_stream_attack(source, self.case_for("clean"))
        expected = canonical_motion_record(source)
        expected = canonical_motion_record(expected)
        expected["window_id"] = result["record"]["window_id"]
        self.assertEqual(result["record"], expected)
        self.assertFalse(result["case"]["is_anomaly"])

    def test_invalid_case_units_seed_or_supervision_fail(self) -> None:
        for field, value in (("unit", "wrong-units"), ("derived_seed", True), ("is_anomaly", False), ("injection_stage", "after_tag"), ("magnitude", -1)):
            changed = deepcopy(self.case_for("position_noise"))
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                apply_stream_attack(self.records[0], changed)

    def test_attack_metadata_never_enters_sensor_record_or_pose_input(self) -> None:
        source = self.records[0]
        case = self.case_for("position_noise")
        first = apply_stream_attack(source, case)["record"]
        changed = deepcopy(case)
        changed["experiment_note"] = "this field must not be a detector shortcut"
        second = apply_stream_attack(source, changed)["record"]
        self.assertEqual(set(first), set(source))
        np.testing.assert_array_equal(record_to_sequence(first), record_to_sequence(second))

    def test_rotations_remain_normalized_and_sign_continuous(self) -> None:
        for name in ("orientation_noise", "orientation_drift", "orientation_jump", "frozen_pose"):
            result = apply_stream_attack(self.records[0], self.case_for(name, "high"))
            values = np.asarray([sample["orientation_xyzw"] for sample in result["record"]["samples"]])
            with self.subTest(attack=name):
                np.testing.assert_allclose(np.linalg.norm(values, axis=1), 1.0, atol=1e-7)
                self.assertTrue(np.all(np.sum(values[1:] * values[:-1], axis=1) >= 0))

    def test_position_drift_reaches_recorded_magnitude(self) -> None:
        source = canonical_motion_record(self.records[0])
        case = self.case_for("position_drift", "high")
        result = apply_stream_attack(self.records[0], case)["record"]
        delta = np.asarray(result["samples"][-1]["position_m"]) - source["samples"][-1]["position_m"]
        self.assertAlmostEqual(float(np.linalg.norm(delta)), case["magnitude"], places=6)

    def test_orientation_drift_reaches_recorded_rotation_angle(self) -> None:
        source = canonical_motion_record(self.records[0])
        case = self.case_for("orientation_drift", "high")
        result = apply_stream_attack(self.records[0], case)["record"]
        original = np.asarray(source["samples"][-1]["orientation_xyzw"])
        changed = np.asarray(result["samples"][-1]["orientation_xyzw"])
        dot = abs(float(np.dot(original, changed) / (np.linalg.norm(original) * np.linalg.norm(changed))))
        angle = float(np.degrees(2 * np.arccos(np.clip(dot, 0.0, 1.0))))
        self.assertAlmostEqual(angle, case["magnitude"], places=4)

    def test_freeze_repeats_pose_but_not_timestamp_or_tracking(self) -> None:
        source = self.records[0]
        result = apply_stream_attack(source, self.case_for("frozen_pose"))
        onset = result["details"]["onset_sample"]
        count = result["details"]["frozen_sample_count"]
        samples = result["record"]["samples"]
        for index in range(onset, onset + count):
            self.assertEqual(samples[index]["position_m"], samples[onset - 1]["position_m"])
            self.assertEqual(samples[index]["orientation_xyzw"], samples[onset - 1]["orientation_xyzw"])
            self.assertEqual(samples[index]["capture_time_ns"], source["samples"][index]["capture_time_ns"])
            self.assertEqual(samples[index]["tracking_valid"], source["samples"][index]["tracking_valid"])

    def test_jump_is_persistent_after_random_onset(self) -> None:
        source = canonical_motion_record(self.records[0])
        result = apply_stream_attack(self.records[0], self.case_for("position_jump"))
        onset = result["details"]["onset_sample"]
        original = np.asarray([sample["position_m"] for sample in source["samples"]])
        changed = np.asarray([sample["position_m"] for sample in result["record"]["samples"]])
        np.testing.assert_array_equal(changed[:onset], original[:onset])
        expected = np.tile(changed[onset] - original[onset], (120 - onset, 1))
        np.testing.assert_allclose(changed[onset:] - original[onset:], expected, atol=1e-7)

    def test_jitter_resamples_onto_original_grid_or_reports_failure(self) -> None:
        source = self.records[0]
        for severity in ("low", "medium", "high"):
            result = apply_stream_attack(source, self.case_for("timestamp_jitter", severity))
            if result["record"] is not None:
                self.assertEqual([row["capture_time_ns"] for row in result["record"]["samples"]], [row["capture_time_ns"] for row in source["samples"]])
            else:
                self.assertEqual(result["status"], "construction_failure")
                self.assertEqual(result["authentication_result"], "not_attempted")

    def test_drop_retains_source_boundaries_and_reports_realized_fraction(self) -> None:
        source = self.records[0]
        result = apply_stream_attack(source, self.case_for("dropped_samples"))
        removed = result["details"]["dropped_sample_indexes"]
        self.assertNotIn(0, removed)
        self.assertNotIn(119, removed)
        self.assertEqual(result["details"]["realized_drop_fraction"], len(removed) / 120)
        self.assertEqual(result["details"]["source_sample_count"], 120 - len(removed))

    def test_resampling_does_not_interpolate_across_legacy_50_ms_rounding_gap(self) -> None:
        source = self.records[0]
        samples = source["samples"]
        keep = [index for index in range(120) if index not in (1, 2)]
        times = np.asarray([samples[index]["capture_time_ns"] - source["window_start_ns"] for index in keep])
        positions = np.asarray([samples[index]["position_m"] for index in keep])
        orientations = np.asarray([samples[index]["orientation_xyzw"] for index in keep])
        record, reason, details = _resample(source, times, positions, orientations, np.ones(len(keep), dtype=bool))
        self.assertIsNone(record)
        self.assertEqual(reason, "source_gap_exceeds_50_ms")
        self.assertAlmostEqual(details["maximum_source_gap_ms"], 50.000001)

    def test_invalid_source_quality_is_not_repaired_or_called_anomaly_detection(self) -> None:
        source = deepcopy(self.records[0])
        for sample in source["samples"][:7]:
            sample["tracking_valid"] = False
        case = self.case_for("position_noise", record=source)
        with self.assertRaises(ValueError):
            apply_stream_attack(source, case)


class StreamAttackIntegrationTests(StreamAttackFixture):
    # these checks reuse the existing legitimate sender without exposing its session key
    def test_quality_valid_change_authenticates_and_composite_consumer_runs_once(self) -> None:
        sender, verifier, _ = establish(AuthConfig(), initialize_material())
        result = apply_stream_attack(self.records[0], self.case_for("position_jump", "high"))
        motion_model = Mock(return_value="test-only-motion")
        anomaly_model = Mock(return_value="test-only-anomaly")

        def consume(record: dict) -> dict:
            self.assertNotIn("label", record)
            self.assertNotIn("attack_type", record)
            sequence = record_to_sequence(record)
            return {"motion_prediction": motion_model(sequence), "anomaly_prediction": anomaly_model(sequence)}

        gate = ExactlyOnceClassifierRelease(verifier, lambda record: record, consume)
        packet = sender.seal_window(processed_record_to_wire_window(result["record"]))
        accepted = verifier.verify_window(packet)
        self.assertEqual(accepted.result, "accept")
        gate.deliver(accepted)
        motion_model.assert_called_once()
        anomaly_model.assert_called_once()
        self.assertEqual(motion_model.call_args.args[0].shape, (120, 7))
        with self.assertRaises(ValueError):
            gate.deliver(accepted)
        motion_model.assert_called_once()
        anomaly_model.assert_called_once()

    def test_bad_tag_invokes_neither_model_and_preserves_sequence(self) -> None:
        sender, verifier, _ = establish(AuthConfig(), initialize_material())
        source = apply_stream_attack(self.records[0], self.case_for("position_noise"))["record"]
        motion_model = Mock()
        anomaly_model = Mock()

        def consume(record: dict) -> tuple:
            return motion_model(record), anomaly_model(record)

        gate = ExactlyOnceClassifierRelease(verifier, lambda record: record, consume)
        packet = sender.seal_window(processed_record_to_wire_window(source))
        changed = json.loads(packet)
        tag = changed["authentication"]["tag_hex"]
        changed["authentication"]["tag_hex"] = ("0" if tag[0] != "0" else "1") + tag[1:]
        session = verifier.active_session_ids[0]
        before = verifier.session_status(session)
        rejected = verifier.verify_window(json.dumps(changed).encode("utf-8"))
        self.assertEqual(rejected.reason, "invalid_tag")
        with self.assertRaises(ValueError):
            gate.deliver(rejected)
        motion_model.assert_not_called()
        anomaly_model.assert_not_called()
        self.assertEqual(verifier.session_status(session), before)
        self.assertEqual(verifier.verify_window(packet).result, "accept")

    def test_consumer_failure_does_not_allow_retry_or_roll_back_authentication(self) -> None:
        sender, verifier, _ = establish(AuthConfig(), initialize_material())
        source = apply_stream_attack(self.records[0], self.case_for("frozen_pose"))["record"]
        calls = []

        def failing_consumer(record: dict) -> None:
            calls.append(record)
            raise RuntimeError("test-only detector failure")

        gate = ExactlyOnceClassifierRelease(verifier, lambda record: record, failing_consumer)
        accepted = verifier.verify_window(sender.seal_window(processed_record_to_wire_window(source)))
        session = verifier.active_session_ids[0]
        committed = verifier.session_status(session)
        with self.assertRaises(RuntimeError):
            gate.deliver(accepted)
        with self.assertRaises(ValueError):
            gate.deliver(accepted)
        self.assertEqual(len(calls), 1)
        self.assertEqual(verifier.session_status(session), committed)


if __name__ == "__main__":
    unittest.main()
