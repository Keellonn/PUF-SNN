""" 
this file proves that session and source-trial leakage are caught
it
- creates a tiny dataset with 1 device, 3 sessions, 1 trial per class per session
- creates source trial leakage by copying one training trial id into test data on purpose
- creates session split leakage by moving one record into the wrong split on purpose
- checks that the validator catches both problems
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


def records_and_schema() -> tuple[list[dict], dict]:
    # this loads a tiny dataset and the real schema for leakage tests
    config_path = ROOT / "configs" / "pilot-v0.2.json"
    schema_path = ROOT / "schemas" / "quest-window-v0.2.schema.json"

    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    config["synthetic_data"].update(
        {
            "device_profiles": 1,
            "sessions_per_device": 3,
            "trials_per_class_per_session": 1,
        }
    )

    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)

    return generate_records(config), schema


class SplitTests(unittest.TestCase):
    def test_validator_catches_source_trial_leakage(self) -> None:
        # this copies one training trial id into test data on purpose
        records, schema = records_and_schema()
        altered = copy.deepcopy(records)

        test_record = next(record for record in altered if record["split"] == "test")

        train_record = next(
            record
            for record in altered
            if record["split"] == "train"
        )

        test_record["source_trial_id"] = train_record["source_trial_id"]
        errors = validate_dataset(altered, schema)

        found_trial_leakage = any(
            "source trial leaks across splits" in error
            for error in errors
        )

        self.assertTrue(found_trial_leakage)

    def test_validator_catches_session_split_leakage(self) -> None:
        # this moves one record into the wrong split on purpose
        records, schema = records_and_schema()
        altered = copy.deepcopy(records)

        session_id = altered[0]["session_id"]

        same_session = [
            record
            for record in altered
            if record["session_id"] == session_id
        ]

        same_session[-1]["split"] = "test"
        errors = validate_dataset(altered, schema)

        found_session_leakage = any(
            "session occurs in multiple splits" in error
            for error in errors
        )

        self.assertTrue(found_session_leakage)


if __name__ == "__main__":
    unittest.main()
