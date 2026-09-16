""" 
this file proves that session and source-trial leakage are caught
it
- creates a tiny dataset with 1 device, 3 sessions, 1 trial per class per session
- creates source trial leakage by copying one training trial id into test data on purpose
- creates session split leakage by moving one record into the wrong split on purpose
- checks that the validator catches both problems
- adds explicit overlap, whole-session assignment, duplicate-id, and sequence tests
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "python"))

from puf_snn.data.generator import generate_records
from puf_snn.data.validation import validate_dataset


def records_and_schema(include_config: bool = False) -> tuple[list[dict], dict] | tuple[list[dict], dict, dict]:
    # this loads a tiny dataset and the real schema for leakage tests
    config_path = ROOT / "configs" / "pilot.json"
    schema_path = ROOT / "schemas" / "quest-window.schema.json"

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

    if include_config:
        return generate_records(config), schema, config

    return generate_records(config), schema


class SplitTests(unittest.TestCase):
    def test_validator_catches_source_trial_leakage(self) -> None:
        """a source-trial id shared between training and testing is rejected"""
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
        """placing part of a session in another split is rejected"""
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


    def test_clean_dataset_has_no_prohibited_split_overlap(self) -> None:
        """window, trial, source-trial, and session ids are disjoint between splits"""
        records, schema, config = records_and_schema(include_config=True)
        self.assertEqual(validate_dataset(records, schema, config=config), [])
        split_names = ("train", "validation", "test")

        for left_split, right_split in combinations(split_names, 2):
            for field in ("window_id", "trial_id", "source_trial_id", "session_id"):
                left_ids = {record[field] for record in records if record["split"] == left_split}
                right_ids = {record[field] for record in records if record["split"] == right_split}
                self.assertEqual(left_ids & right_ids, set())

        # the same simulated device intentionally appears in all three splits
        for split in split_names:
            self.assertEqual(
                {record["device_id"] for record in records if record["split"] == split},
                {"sim-device-01"},
            )

    def test_validator_catches_whole_session_in_wrong_split(self) -> None:
        """moving a complete session to the wrong configured split is rejected"""
        records, schema, config = records_and_schema(include_config=True)
        altered = copy.deepcopy(records)
        for record in altered:
            if record["split"] == "train":
                record["split"] = "test"
        errors = validate_dataset(altered, schema, config=config)
        self.assertTrue(any("configured session assignment" in error for error in errors))

    def test_validator_catches_duplicate_window(self) -> None:
        """reusing a window id across records is rejected"""
        records, schema, config = records_and_schema(include_config=True)
        records[1]["window_id"] = records[0]["window_id"]
        errors = validate_dataset(records, schema, config=config)
        self.assertTrue(any("duplicate window ID" in error for error in errors))

    def test_validator_catches_sequence_gap(self) -> None:
        """a missing sequence number in the saved clean session is rejected"""
        records, schema, config = records_and_schema(include_config=True)
        records[1]["sequence_number"] += 1
        errors = validate_dataset(records, schema, config=config)
        self.assertTrue(any("sequence numbers are not consecutive" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
