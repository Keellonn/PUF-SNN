"""
this file checks that generated windows are repeatable and valid
it
- imports our generator and validator
- generates a small set of windows, 60 instead of 1.8k
- checks that the same config always gives the same windows
- checks that the windows pass the validator
- also breaks a quarternion to make sure the validator catches it
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "python"))

from puf_snn.data.generator import generate_records
from puf_snn.data.validation import validate_dataset


def small_config() -> dict:
    # this keeps each test small while using the real project settings
    config_path = ROOT / "configs" / "pilot-v0.2.json"

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
    schema_path = ROOT / "schemas" / "quest-window-v0.2.schema.json"

    with schema_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class DataTests(unittest.TestCase):
    def test_generator_is_deterministic_and_balanced(self) -> None:
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

    def test_generated_records_pass_validation(self) -> None:
        # this makes sure clean generated data passes every current rule
        records = generate_records(small_config())
        errors = validate_dataset(records, schema())

        self.assertEqual(errors, [])

    def test_validator_catches_bad_quaternion(self) -> None:
        # this proves that an invalid zero quaternion is rejected
        altered = copy.deepcopy(generate_records(small_config()))
        altered[0]["samples"][10]["orientation_xyzw"] = [0.0, 0.0, 0.0, 0.0]

        errors = validate_dataset(altered, schema())

        found_quaternion_error = any(
            "not unit normalized" in error
            for error in errors
        )

        self.assertTrue(found_quaternion_error)


if __name__ == "__main__":
    unittest.main()
