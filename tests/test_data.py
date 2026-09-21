"""
this file checks that generated windows are repeatable, variable, and valid
it
- imports our generator and validator
- generates a small set of windows, 60 instead of 1.8k
- checks that the same config always gives the same windows
- checks that the windows pass the validator
- also breaks a quarternion to make sure the validator catches it
- adds explicit schema, time, tracking, sign-continuity, and identifier checks
- proves active classes do not reuse one orientation template
- proves still contains small nonzero motion
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import sys
import unittest
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "python"))
sys.path.insert(0, str(ROOT / "src" / "python" / "scripts"))

from puf_snn.data.generator import generate_records
from puf_snn.data.validation import validate_dataset
import train_baselines


def small_config() -> dict:
    # this keeps each test small while using the real project settings
    config_path = ROOT / "configs" / "pilot.json"

    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    config["synthetic_data"].update(
        {
            "device_profiles": 2,
            "sessions_per_device": 3,
            "trials_per_class_per_session": 2,
        }
    )

    return config


def schema() -> dict:
    # this loads the same schema used by the command line validator
    schema_path = ROOT / "schemas" / "quest-window.schema.json"

    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # generate the clean fixture once and copy it before each mutation
        cls.config = small_config()
        cls.window_schema = schema()
        cls.clean_records = generate_records(cls.config)

    def check_records(self, records: list[dict]) -> list[str]:
        return validate_dataset(records, self.window_schema, config=self.config)

    def test_generator_is_deterministic_and_balanced(self) -> None:
        """same seed reproduces records and every device-session has balanced class counts"""
        # this makes sure the fixed seed always gives the same balanced data
        config = small_config()
        first = generate_records(config)
        second = generate_records(config)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 2 * 3 * 2 * 5)

        observed_splits = {
            record["split"]
            for record in first
        }

        expected_splits = {
            "train",
            "validation",
            "test",
        }

        self.assertEqual(observed_splits, expected_splits)

        all_windows_have_120_samples = all(
            len(record["samples"]) == 120
            for record in first
        )

        self.assertTrue(all_windows_have_120_samples)

        # every device-session group must contain the requested count of each class
        observed_counts = Counter(
            (record["device_id"], record["session_id"], record["label"])
            for record in first
        )
        expected_counts = Counter({
            (f"sim-device-{device:02d}", f"sim-device-{device:02d}-session-{session:02d}", label): 2
            for device in (1, 2)
            for session in (1, 2, 3)
            for label in config["task"]["labels"]
        })
        self.assertEqual(observed_counts, expected_counts)

    def test_generated_records_pass_validation(self) -> None:
        """clean records pass the schema, quality rules, and configured identifier checks"""
        # this makes sure clean generated data passes every current rule
        records = generate_records(small_config())
        errors = validate_dataset(records, schema(), config=small_config())

        self.assertEqual(errors, [])

    def test_validator_catches_bad_quaternion(self) -> None:
        """an invalid zero quaternion is rejected"""
        altered = copy.deepcopy(generate_records(small_config()))
        altered[0]["samples"][10]["orientation_xyzw"] = [0.0, 0.0, 0.0, 0.0]

        errors = validate_dataset(altered, schema())

        found_quaternion_error = any("not unit normalized" in error for error in errors)

        self.assertTrue(found_quaternion_error)

    def test_generated_windows_have_120_ordered_samples(self) -> None:
        """every fixed-grid window has 120 consecutive indexes and increasing times"""
        for record in self.clean_records:
            samples = record["samples"]
            self.assertEqual(len(samples), 120)
            self.assertEqual([sample["sample_index"] for sample in samples], list(range(120)))
            timestamps = [sample["capture_time_ns"] for sample in samples]
            self.assertTrue(all(right > left for left, right in zip(timestamps, timestamps[1:])))

    def test_generated_quaternions_are_normalized_and_continuous(self) -> None:
        """all generated quaternions have unit norm and continuous signs"""
        for record in self.clean_records:
            quaternions = [sample["orientation_xyzw"] for sample in record["samples"]]
            for quaternion in quaternions:
                self.assertAlmostEqual(math.sqrt(sum(value * value for value in quaternion)), 1.0, delta=1e-4)
            for left, right in zip(quaternions, quaternions[1:]):
                self.assertGreaterEqual(sum(a * b for a, b in zip(left, right)), 0.0)

    def test_generated_identifiers_match_their_records(self) -> None:
        """device, session, trial, label, source, and window ids agree"""
        for record in self.clean_records:
            self.assertIn(record["label"], self.config["task"]["labels"])
            self.assertTrue(record["session_id"].startswith(record["device_id"] + "-session-"))
            self.assertTrue(record["trial_id"].startswith(record["session_id"] + "-" + record["label"] + "-"))
            self.assertEqual(record["source_trial_id"], record["trial_id"])
            self.assertEqual(record["window_id"], record["trial_id"] + "-window-000")

    def test_schema_rejects_wrong_types_and_extra_fields(self) -> None:
        """schema types, required fields, enums, and extra-field rules are enforced"""
        for mutation in ("string_rate", "string_tracking", "missing_label", "unknown_label", "extra_field", "list_id"):
            with self.subTest(mutation=mutation):
                altered = copy.deepcopy(self.clean_records)
                record = altered[0]
                if mutation == "string_rate":
                    record["target_sample_rate_hz"] = "60"
                elif mutation == "string_tracking":
                    record["samples"][0]["tracking_valid"] = "true"
                elif mutation == "missing_label":
                    del record["label"]
                elif mutation == "unknown_label":
                    record["label"] = "walking"
                elif mutation == "extra_field":
                    record["unexpected_field"] = 1
                else:
                    record["window_id"] = ["invalid-id"]
                self.assertTrue(any("schema error" in error for error in self.check_records(altered)))

    def test_validator_catches_quaternion_sign_flip(self) -> None:
        """an isolated equivalent quaternion sign flip is rejected"""
        altered = copy.deepcopy(self.clean_records)
        sample = altered[0]["samples"][10]
        sample["orientation_xyzw"] = [-value for value in sample["orientation_xyzw"]]
        self.assertTrue(any("sign continuity" in error for error in self.check_records(altered)))

    def test_validator_rejects_short_window(self) -> None:
        """a saved window with only 119 samples fails the schema"""
        altered = copy.deepcopy(self.clean_records)
        altered[0]["samples"].pop()
        self.assertTrue(any("schema error" in error for error in self.check_records(altered)))

    def test_validator_rejects_nonfinite_position(self) -> None:
        """nan and infinity cannot pass as valid position values"""
        for invalid_value in (float("nan"), float("inf")):
            with self.subTest(value=invalid_value):
                altered = copy.deepcopy(self.clean_records)
                altered[0]["samples"][0]["position_m"][0] = invalid_value
                self.assertTrue(any("finite" in error for error in self.check_records(altered)))

    def test_validator_catches_timestamp_gap_and_order(self) -> None:
        """large gaps and repeated timestamps are rejected"""
        altered = copy.deepcopy(self.clean_records)
        for sample in altered[0]["samples"][10:]:
            sample["capture_time_ns"] += 60_000_000
        self.assertTrue(any("timestamp gap exceeds" in error for error in self.check_records(altered)))

        altered = copy.deepcopy(self.clean_records)
        altered[0]["samples"][10]["capture_time_ns"] = altered[0]["samples"][9]["capture_time_ns"]
        self.assertTrue(any("strictly increasing" in error for error in self.check_records(altered)))

    def test_tracking_threshold_accepts_114_and_rejects_113(self) -> None:
        """exactly 95 percent tracking passes and a lower fraction fails"""
        altered = copy.deepcopy(self.clean_records)
        for sample in altered[0]["samples"][:6]:
            sample["tracking_valid"] = False
        self.assertEqual(self.check_records(altered), [])

        altered[0]["samples"][6]["tracking_valid"] = False
        self.assertTrue(any("tracking-valid fraction" in error for error in self.check_records(altered)))

    def test_validator_catches_id_mismatch(self) -> None:
        """changing a device without its session and trial relationships fails"""
        altered = copy.deepcopy(self.clean_records)
        altered[0]["device_id"] = "sim-device-02"
        self.assertTrue(any("session_id does not match" in error for error in self.check_records(altered)))

    def test_validator_catches_missing_group(self) -> None:
        """removing a whole session cannot pass just because the remaining records are valid"""
        session_id = self.clean_records[0]["session_id"]
        altered = [record for record in self.clean_records if record["session_id"] != session_id]
        self.assertTrue(any("expected" in error for error in self.check_records(altered)))

    def test_active_classes_use_multiple_orientation_trajectories(self) -> None:
        """active classes vary instead of copying one orientation template"""
        for label in ("nod", "shake", "look_left_return", "look_right_return"):
            hashes = set()

            for record in self.clean_records:
                if record["label"] != label:
                    continue

                matrix = train_baselines.record_to_features(record).reshape(120, 7)
                hashes.add(hashlib.sha256(matrix[:, 3:7].tobytes()).hexdigest())

            self.assertGreater(len(hashes), 3)

    def test_still_contains_small_nonzero_variable_motion(self) -> None:
        """still is not an exact zero-motion shortcut"""
        activity = []

        for record in self.clean_records:
            if record["label"] != "still":
                continue

            matrix = train_baselines.record_to_features(record).reshape(120, 7)
            orientation_activity = np.mean(np.linalg.norm(matrix[:, 3:7] - matrix[0, 3:7], axis=1))
            activity.append(float(orientation_activity))

        self.assertTrue(activity)
        self.assertGreater(min(activity), 0.0001)
        self.assertGreater(np.std(activity), 0.0)


if __name__ == "__main__":
    unittest.main()
