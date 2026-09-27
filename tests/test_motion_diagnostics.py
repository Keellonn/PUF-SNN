"""these tests prevent copied windows and incorrect rotation diagnostics"""

from copy import deepcopy
import json
from pathlib import Path
import unittest

import numpy as np

from puf_snn.data.generator import generate_records
from puf_snn.motion_diagnostics import angular_velocity, assert_no_full_window_duplicates, feature_group, full_window_hash, nearest_neighbors, physical_distances, pooled_metrics, record_times, transformed_record, vectors_to_quaternions
from puf_snn.snn.dataset import record_to_sequence

ROOT = Path(__file__).resolve().parents[1]


class MotionDiagnosticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        config = json.loads((ROOT / "configs/pilot.json").read_text(encoding="utf-8"))
        config["synthetic_data"]["device_profiles"] = 1
        config["synthetic_data"]["trials_per_class_per_session"] = 1
        cls.records = generate_records(config)

    def test_clean_windows_have_no_full_content_overlap(self) -> None:
        assert_no_full_window_duplicates(self.records)

    def test_model_seed_changes_do_not_change_generated_motion(self) -> None:
        config = json.loads((ROOT / "configs/pilot.json").read_text(encoding="utf-8"))
        config["synthetic_data"]["device_profiles"] = 1
        config["synthetic_data"]["trials_per_class_per_session"] = 1
        changed = deepcopy(config)
        changed["randomness"]["snn_training_seeds"] = [207, 217, 227]
        self.assertEqual(generate_records(config), generate_records(changed))

    def test_data_seed_changes_motion_without_changing_split_mapping(self) -> None:
        config = json.loads((ROOT / "configs/pilot.json").read_text(encoding="utf-8"))
        config["synthetic_data"]["device_profiles"] = 1
        config["synthetic_data"]["trials_per_class_per_session"] = 1
        first = generate_records(config)
        config["project"]["random_seed"] = 8
        config["randomness"]["data_generation_seed"] = 8
        second = generate_records(config)
        self.assertNotEqual(first, second)
        first_splits = {record["session_id"]: record["split"] for record in first}
        second_splits = {record["session_id"]: record["split"] for record in second}
        self.assertEqual(first_splits, second_splits)

    def test_copy_with_different_identifiers_and_label_fails_each_split_pair(self) -> None:
        for first, second in (("train", "validation"), ("train", "test"), ("validation", "test")):
            with self.subTest(pair=(first, second)):
                source = deepcopy(next(record for record in self.records if record["split"] == first))
                copy = deepcopy(source)
                copy.update(split=second, window_id="different-window", source_trial_id="different-trial", session_id="different-session", label="still")
                with self.assertRaises(ValueError):
                    assert_no_full_window_duplicates([source, copy])

    def test_absolute_time_offset_does_not_hide_a_copy(self) -> None:
        source = self.records[0]
        copy = deepcopy(source)
        copy["window_start_ns"] += 1000000
        copy["window_end_ns"] += 1000000

        for sample in copy["samples"]:
            sample["capture_time_ns"] += 1000000

        self.assertEqual(full_window_hash(source), full_window_hash(copy))

    def test_tracking_and_relative_timestamps_are_part_of_full_content(self) -> None:
        source = self.records[0]

        for field, value in (("tracking_valid", False), ("capture_time_ns", source["samples"][5]["capture_time_ns"] + 1)):
            copy = deepcopy(source)
            copy["samples"][5][field] = value
            self.assertNotEqual(full_window_hash(source), full_window_hash(copy))

    def test_rotation_distance_ignores_equivalent_quaternion_signs(self) -> None:
        sequence = record_to_sequence(self.records[0])[None, :, :]
        other = sequence.copy()
        other[:, :, 3:7] *= -1
        position, orientation = physical_distances(sequence, other)
        self.assertAlmostEqual(float(position[0, 0]), 0.0)
        self.assertLess(float(orientation[0, 0]), 0.00001)

    def test_small_jitter_is_not_exact_but_is_detected_as_near(self) -> None:
        source = self.records[0]
        copy = deepcopy(source)
        copy["samples"][10]["position_m"][0] += 0.00001
        self.assertNotEqual(full_window_hash(source), full_window_hash(copy))
        rows = nearest_neighbors([source], [copy], 0.001, 1.0)
        self.assertTrue(all(row["has_neighbor_within_both_thresholds"] for row in rows))

    def test_feature_group_shapes_and_metadata_exclusion(self) -> None:
        source = self.records[0]
        changed = deepcopy(source)
        changed.update(label="still", device_id="different-device", window_id="different-window")

        for group, channels in (("raw_relative_pose", 7), ("quaternion_only", 4), ("quaternion_plus_angular_velocity", 7), ("position_plus_quaternion", 7)):
            self.assertEqual(feature_group(source, group).shape, (120, channels))
            np.testing.assert_allclose(feature_group(source, group), feature_group(changed, group))

    def test_angular_velocity_uses_timestamp_intervals(self) -> None:
        times = np.arange(120) / 60.0
        sequence = np.zeros((120, 7))
        vectors = np.zeros((120, 3))
        vectors[:, 1] = times * 0.2
        sequence[:, 3:7] = vectors_to_quaternions(vectors)
        velocity = angular_velocity(sequence, times)
        np.testing.assert_allclose(velocity[1:, 1], 0.2, atol=1e-10)

    def test_initial_orientation_shift_is_relative_pose_invariant(self) -> None:
        source = self.records[0]
        changed = transformed_record(source, initial_orientation_deg=15.0)
        np.testing.assert_allclose(record_to_sequence(source), record_to_sequence(changed), atol=1e-12)

    def test_time_warp_preserves_unit_quaternions_and_source_split(self) -> None:
        source = self.records[0]
        changed = transformed_record(source, speed=0.85, shift_seconds=0.1)
        values = np.asarray([sample["orientation_xyzw"] for sample in changed["samples"]])
        np.testing.assert_allclose(np.linalg.norm(values, axis=1), 1.0, atol=1e-12)
        np.testing.assert_array_equal(record_times(source), record_times(changed))
        self.assertEqual(changed["split"], source["split"])

    def test_pooled_metrics_are_calculated_from_counts(self) -> None:
        first = [[9, 1], [0, 10]]
        second = [[1, 9], [0, 10]]
        result = pooled_metrics([first, second], ("nod", "still"))
        self.assertEqual(result["confusion_matrix"], [[10, 10], [0, 20]])
        self.assertEqual(result["prediction_count"], 40)
        self.assertAlmostEqual(result["accuracy"], 0.75)
        self.assertAlmostEqual(result["per_class"]["nod"]["f1"], 2 / 3)


if __name__ == "__main__":
    unittest.main()
