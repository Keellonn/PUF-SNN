"""
this file checks the feature processing used by the conventional classifiers
it
- creates small test windows with 120 motion samples
- checks that each window becomes 840 position and quaternion features
- checks that labels, device ids, and session ids arent used as model features
- checks quaternion normalization and sign continuity
- checks that training, validation, and testing data stay separate
- checks that incomplete windows are rejected
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

import numpy as np


# load the training script from its current repository location
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIRECTORY = REPOSITORY_ROOT / "src" / "python" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import train_baselines


# create one small but correctly shaped test window
def make_record(split_name: str = "train", label: str = "nod") -> dict:
    samples = []

    for sample_index in range(120):
        samples.append(
            {
                "sample_index": sample_index,
                "capture_time_ns": sample_index * 16_666_667,
                "position_m": [
                    5.0 + sample_index * 0.001,
                    2.0 + sample_index * 0.002,
                    -3.0 + sample_index * 0.003,
                ],
                "orientation_xyzw": [
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ],
                "tracking_valid": True,
            }
        )

    return {
        "window_id": f"{split_name}-{label}",
        "source_trial_id": f"trial-{split_name}-{label}",
        "device_id": "simulated-device-1",
        "session_id": f"session-{split_name}",
        "trial_id": f"trial-{split_name}-{label}",
        "split": split_name,
        "sequence_number": 1,
        "label": label,
        "samples": samples,
    }


class BaselineFeatureTests(unittest.TestCase):
    # make sure every window becomes 120 by 7 features
    def test_feature_shape_and_relative_pose(self) -> None:
        record = make_record()

        features = train_baselines.record_to_features(record)

        self.assertEqual(features.shape, (840,))

        feature_matrix = features.reshape(120, 7)

        np.testing.assert_allclose(feature_matrix[0, 0:3], np.zeros(3), atol=1e-10)

        np.testing.assert_allclose(
            feature_matrix[0, 3:7],
            np.array(
                [
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ]
            ),
            atol=1e-10,
        )

        self.assertTrue(np.all(np.isfinite(features)))

    # make sure labels and identifiers never enter the feature vector
    def test_metadata_does_not_change_features(self) -> None:
        first_record = make_record()

        second_record = copy.deepcopy(first_record)

        second_record["window_id"] = "different-window"
        second_record["source_trial_id"] = "different-trial"
        second_record["device_id"] = "different-device"
        second_record["session_id"] = "different-session"
        second_record["trial_id"] = "different-trial-id"
        second_record["split"] = "test"
        second_record["sequence_number"] = 999
        second_record["label"] = "still"
        second_record["window_start_ns"] = 99_000_000_000
        second_record["window_end_ns"] = 101_000_000_000

        for sample_index, sample in enumerate(second_record["samples"]):
            sample["capture_time_ns"] = 99_000_000_000 + sample_index
            sample["tracking_valid"] = sample_index % 2 == 0

        first_features = train_baselines.record_to_features(first_record)
        second_features = train_baselines.record_to_features(second_record)

        np.testing.assert_allclose(first_features, second_features, atol=1e-10)

    # make sure validation and test values do not affect the training scaler
    def test_logistic_scaler_is_fit_from_training_only(self) -> None:
        records = []

        for split_name, position_scale in (
            ("train", 1.0),
            ("validation", 100.0),
            ("test", 1000.0),
        ):
            for label_index, label in enumerate(train_baselines.LABELS):
                record = make_record(split_name=split_name, label=label)

                for sample_index, sample in enumerate(record["samples"]):
                    sample["position_m"][0] = position_scale * label_index * sample_index / 120.0

                records.append(record)

        datasets = train_baselines.build_datasets(records)
        model = train_baselines.create_models(seed=2026)["logistic_regression"]
        model.fit(datasets["train"]["features"], datasets["train"]["labels"])

        scaler = model.named_steps["scaler"]
        expected_mean = datasets["train"]["features"].mean(axis=0)
        np.testing.assert_allclose(scaler.mean_, expected_mean, atol=1e-12)

    # make sure q and negative q dont create false motion
    def test_quaternion_sign_continuity(self) -> None:
        record = make_record()

        for sample_index, sample in enumerate(record["samples"]):
            if sample_index % 2 == 1:
                sample["orientation_xyzw"] = [
                    0.0,
                    0.0,
                    0.0,
                    -1.0,
                ]

        features = train_baselines.record_to_features(record)
        feature_matrix = features.reshape(120, 7)

        expected_orientations = np.tile(
            np.array(
                [
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                ]
            ),
            (120, 1),
        )

        np.testing.assert_allclose(feature_matrix[:, 3:7], expected_orientations, atol=1e-10)

    # make sure the existing split labels stay separate
    def test_build_datasets_keeps_splits_separate(self) -> None:
        records = []

        for split_name in ("train", "validation", "test"):
            for label in train_baselines.LABELS:
                records.append(make_record(split_name=split_name, label=label))

        datasets = train_baselines.build_datasets(records)

        self.assertEqual(datasets["train"]["features"].shape, (5, 840))
        self.assertEqual(datasets["validation"]["features"].shape, (5, 840))
        self.assertEqual(datasets["test"]["features"].shape, (5, 840))
        self.assertEqual(set(datasets["train"]["labels"]), set(train_baselines.LABELS))

    # make sure incomplete windows are rejected
    def test_short_window_is_rejected(self) -> None:
        record = make_record()

        record["samples"] = record["samples"][:-1]

        with self.assertRaises(ValueError):
            train_baselines.record_to_features(record)


if __name__ == "__main__":
    unittest.main()
