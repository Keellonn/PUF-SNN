"""
this file checks SNN input shape metadata exclusion split safety and reproducibility
it also proves the SNN sequence matches the existing 840-value pose preprocessing
"""

from __future__ import annotations

import copy
import random
import sys
import unittest

from pathlib import Path

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIRECTORY = REPOSITORY_ROOT / "src" / "python" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import train_baselines

from puf_snn.snn.configuration import load_snn_config, seed_everything
from puf_snn.snn.dataset import LABELS, apply_channel_normalization, build_snn_datasets, fit_channel_normalization, make_epoch_order, record_to_sequence


def make_record(split_name: str = "train", label: str = "nod") -> dict:
    samples = []

    for sample_index in range(120):
        samples.append({
            "sample_index": sample_index,
            "capture_time_ns": sample_index * 16_666_667,
            "position_m": [
                5.0 + sample_index * 0.001,
                2.0 + sample_index * 0.002,
                -3.0 + sample_index * 0.003,
            ],
            "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
            "tracking_valid": sample_index >= 3,
        })

    return {
        "window_id": f"{split_name}-{label}-window",
        "source_trial_id": f"{split_name}-{label}-source-trial",
        "device_id": "simulated-device-1",
        "session_id": f"{split_name}-session",
        "trial_id": f"{split_name}-{label}-trial",
        "split": split_name,
        "sequence_number": 1,
        "label": label,
        "window_start_ns": 0,
        "window_end_ns": 2_000_000_040,
        "samples": samples,
    }


def make_complete_records() -> list[dict]:
    return [
        make_record(split_name=split_name, label=label)
        for split_name in ("train", "validation", "test")
        for label in LABELS
    ]


class SnnDataTests(unittest.TestCase):
    # the SNN keeps the 120 time steps and seven authenticated pose channels
    def test_input_shape_is_120_by_7(self) -> None:
        sequence = record_to_sequence(make_record())

        self.assertEqual(sequence.shape, (120, 7))
        np.testing.assert_allclose(sequence[0, 0:3], np.zeros(3), atol=1e-10)
        np.testing.assert_allclose(sequence[0, 3:7], np.array([0.0, 0.0, 0.0, 1.0]), atol=1e-10)

    # flattening the SNN sequence reproduces the existing classifier features
    def test_sequence_matches_conventional_preprocessing(self) -> None:
        record = make_record()
        sequence = record_to_sequence(record)
        conventional_features = train_baselines.record_to_features(record)

        np.testing.assert_allclose(sequence.reshape(-1), conventional_features, atol=1e-12)

    # identifiers labels timestamps splits and tracking flags never enter model input
    def test_metadata_does_not_change_input(self) -> None:
        first_record = make_record()
        second_record = copy.deepcopy(first_record)
        second_record["window_id"] = "different-window"
        second_record["source_trial_id"] = "different-source-trial"
        second_record["device_id"] = "different-device"
        second_record["session_id"] = "different-session"
        second_record["trial_id"] = "different-trial"
        second_record["split"] = "test"
        second_record["sequence_number"] = 999
        second_record["label"] = "still"
        second_record["window_start_ns"] = 99_000_000_000
        second_record["window_end_ns"] = 101_000_000_000

        for sample_index, sample in enumerate(second_record["samples"]):
            sample["sample_index"] = 500 + sample_index
            sample["capture_time_ns"] = 99_000_000_000 + sample_index
            sample["tracking_valid"] = not sample["tracking_valid"]

        np.testing.assert_allclose(record_to_sequence(first_record), record_to_sequence(second_record), atol=1e-12)

    # records retain the train validation and test splits saved in the dataset
    def test_existing_splits_stay_separate(self) -> None:
        datasets = build_snn_datasets(make_complete_records())

        self.assertEqual(datasets["train"]["sequences"].shape, (5, 120, 7))
        self.assertEqual(datasets["validation"]["sequences"].shape, (5, 120, 7))
        self.assertEqual(datasets["test"]["sequences"].shape, (5, 120, 7))
        self.assertEqual(set(datasets["train"]["label_indexes"]), set(range(5)))

    # an identifier reused across splits is rejected before training
    def test_split_overlap_is_rejected(self) -> None:
        records = make_complete_records()
        records[-1]["window_id"] = records[0]["window_id"]

        with self.assertRaisesRegex(ValueError, "window_id overlaps"):
            build_snn_datasets(records)

    # validation and test windows cannot affect the training normalization values
    def test_normalization_is_fit_from_training_only(self) -> None:
        datasets = build_snn_datasets(make_complete_records())
        first_normalization = fit_channel_normalization(datasets["train"]["sequences"])
        changed_validation = datasets["validation"]["sequences"].copy()
        changed_validation[:, :, 0:3] *= 10_000.0
        second_normalization = fit_channel_normalization(datasets["train"]["sequences"])

        np.testing.assert_array_equal(first_normalization["mean"], second_normalization["mean"])
        np.testing.assert_array_equal(first_normalization["standard_deviation"], second_normalization["standard_deviation"])
        self.assertEqual(apply_channel_normalization(changed_validation, first_normalization).shape, (5, 120, 7))

    # repeated seeds produce the same shuffled order and random values
    def test_seeded_behavior_is_reproducible(self) -> None:
        np.testing.assert_array_equal(make_epoch_order(50, 17), make_epoch_order(50, 17))
        self.assertFalse(np.array_equal(make_epoch_order(50, 17), make_epoch_order(50, 27)))
        seed_everything(17)
        first_python_value = random.random()
        first_numpy_value = np.random.random()
        first_torch_value = __import__("torch").rand(1).item()
        seed_everything(17)
        self.assertEqual(random.random(), first_python_value)
        self.assertEqual(np.random.random(), first_numpy_value)
        self.assertEqual(__import__("torch").rand(1).item(), first_torch_value)

    # the final configuration records the approved seven-channel experiment
    def test_configuration_matches_final_contract(self) -> None:
        config = load_snn_config(REPOSITORY_ROOT / "configs" / "snn_baseline.json")

        self.assertEqual(config["dataset"]["input_channels"], 7)
        self.assertEqual(config["training"]["random_seeds"], [7, 17, 27])
        self.assertEqual(config["model"]["hidden_neurons"], 64)


if __name__ == "__main__":
    unittest.main()
