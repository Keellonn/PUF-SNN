"""Formula, training-only scaling, grid and historical-evidence regression tests."""

from copy import deepcopy
import unittest

import numpy as np

from puf_snn import sequence_neighbors as audit
from puf_snn.snn.dataset import record_to_sequence


def sequences(count=1):
    values = np.zeros((count, 120, 7), dtype=float)
    values[:, :, 6] = 1
    return values


def metadata(identifier, label="nod", split="train"):
    return {"window_id": identifier, "source_trial_id": identifier + "-trial",
            "session_id": "session-" + split, "split": split, "label": label}


def record():
    return {"samples": [{"sample_index": index, "capture_time_ns": 1000 + index * 16_666_667,
                          "position_m": [index / 1000, 0, 0], "orientation_xyzw": [0, 0, 0, 1],
                          "tracking_valid": True} for index in range(120)]}


class SequenceNeighborTests(unittest.TestCase):
    def setUp(self):
        self.training = sequences(2)
        self.training[1, :, 0] = 1
        self.training_metadata = [metadata("a"), metadata("b", "still")]
        self.query = sequences()
        self.query_metadata = [metadata("query", split="test")]
        self.scaler = audit.fit_training_scaler(self.training)

    def neighbors(self, **changes):
        arguments = {"training": self.training, "queries": self.query,
                     "training_metadata": self.training_metadata, "query_metadata": self.query_metadata,
                     "scaler": self.scaler}
        arguments.update(changes)
        return audit.nearest_training_rows(**arguments)

    def test_complete_metric_uses_all_840_coordinates(self):
        changed = sequences()
        changed[0, 30, 2] = 2
        changed[0, 90, 4] = 3
        self.assertAlmostEqual(audit.full_sequence_rms(changed, sequences())[0, 0], np.sqrt(13 / 840))

    def test_rms_not_sum_or_maximum(self):
        changed = sequences()
        changed[:, :, 0] = 1
        self.assertAlmostEqual(audit.full_sequence_rms(changed, sequences())[0, 0], np.sqrt(1 / 7))

    def test_identical_full_inputs_have_exact_zero_distance(self):
        np.testing.assert_array_equal(audit.full_sequence_rms(self.training, self.training).diagonal(), [0, 0])

    def test_orientation_metric_ignores_quaternion_sign(self):
        changed = sequences()
        changed[:, :, 3:7] *= -1
        self.assertAlmostEqual(audit.orientation_rms_degrees(changed, sequences())[0, 0], 0)

    def test_orientation_rms_is_not_mean_angle(self):
        changed = sequences()
        changed[0, 1, 3] = np.sin(np.pi / 4)
        changed[0, 1, 6] = np.cos(np.pi / 4)
        self.assertAlmostEqual(audit.orientation_rms_degrees(changed, sequences())[0, 0], 90 / np.sqrt(120))

    def test_quaternion_normalization_precedes_rotation_metric(self):
        changed = sequences()
        changed[:, :, 6] = 2
        self.assertAlmostEqual(audit.orientation_rms_degrees(changed, sequences())[0, 0], 0)

    def test_zero_quaternion_rejected(self):
        changed = sequences()
        changed[:, :, 3:7] = 0
        with self.assertRaises(ValueError):
            audit.orientation_rms_degrees(changed, sequences())

    def test_training_scaler_uses_windows_and_time_not_query(self):
        self.assertEqual(self.scaler["mean"][0], .5)
        self.assertEqual(self.scaler["standard_deviation"][0], .5)
        self.query[:, :, 0] = 1000
        before = deepcopy(self.scaler)
        self.neighbors()
        for name in before:
            np.testing.assert_array_equal(self.scaler[name], before[name])

    def test_zero_variance_sd_matches_existing_model_policy(self):
        scaler = audit.fit_training_scaler(sequences())
        np.testing.assert_array_equal(scaler["standard_deviation"], np.ones(7))

    def test_normalization_matches_float32_input_rounding(self):
        self.query[:, :, 0] = .123456789
        result = audit.normalized_model_inputs(self.query, self.scaler)
        self.assertEqual(result.dtype, np.float64)
        self.assertEqual(result[0, 0, 0], float(np.float32((.123456789 - .5) / .5)))

    def test_bad_shape_and_nonfinite_data_rejected(self):
        for bad in (np.zeros((1, 119, 7)), np.zeros((0, 120, 7)), np.full((1, 120, 7), np.nan)):
            with self.subTest(shape=bad.shape):
                with self.assertRaises(ValueError):
                    audit.full_sequence_rms(bad, sequences())

    def test_bad_scaler_rejected(self):
        for scale in (np.zeros(7), np.full(7, np.inf)):
            with self.assertRaises(ValueError):
                audit.normalized_model_inputs(self.query, {"mean": np.zeros(7), "standard_deviation": scale})

    def test_absolute_timestamp_origin_does_not_change_alignment(self):
        first, second = record(), record()
        for sample in second["samples"]:
            sample["capture_time_ns"] += 1_000_000
        offsets = audit.fixed_grid_offsets([first, second])
        self.assertEqual(offsets[1], 16_666_667)
        self.assertEqual(offsets[-1], 119 * 16_666_667)

    def test_irregular_grid_is_rejected_not_resampled(self):
        changed = record()
        changed["samples"][5]["capture_time_ns"] += 1
        with self.assertRaises(ValueError):
            audit.fixed_grid_offsets([changed])

    def test_different_regular_grid_is_not_time_aligned_silently(self):
        first, changed = record(), record()
        for sample in changed["samples"]:
            sample["capture_time_ns"] = 1000 + sample["sample_index"] * 16_666_666
        with self.assertRaises(ValueError):
            audit.fixed_grid_offsets([first, changed])

    def test_sample_index_order_is_enforced(self):
        changed = record()
        changed["samples"][4]["sample_index"] = 5
        with self.assertRaises(ValueError):
            audit.fixed_grid_offsets([changed])

    def test_metadata_never_changes_the_120_by_7_input(self):
        first, changed = record(), record()
        changed.update(label="still", split="test", window_id="different", device_id="different")
        for sample in changed["samples"]:
            sample["tracking_valid"] = False
        np.testing.assert_array_equal(record_to_sequence(first), record_to_sequence(changed))

    def test_any_label_and_same_label_have_separate_references(self):
        self.query[:, :, 0] = .99
        rows = self.neighbors()
        self.assertEqual(rows[0]["sequence_neighbor_id"], "b")
        self.assertEqual(rows[1]["sequence_neighbor_id"], "a")

    def test_ties_are_deterministic_and_chunk_size_does_not_change_results(self):
        self.training[1] = self.training[0]
        self.assertEqual(self.neighbors()[0]["sequence_neighbor_id"], "a")
        self.assertEqual(self.neighbors(), self.neighbors(chunk_size=1))

    def test_unsorted_reference_is_rejected(self):
        with self.assertRaises(ValueError):
            self.neighbors(training_metadata=self.training_metadata[::-1])

    def test_reference_and_query_splits_are_enforced(self):
        for training, query in (([metadata("a", split="test"), metadata("b")], self.query_metadata),
                                (self.training_metadata, [metadata("query", split="train")])):
            with self.assertRaises(ValueError):
                self.neighbors(training_metadata=training, query_metadata=query)

    def test_source_trial_and_session_overlap_rejected(self):
        for field in ("window_id", "source_trial_id", "session_id"):
            changed = deepcopy(self.query_metadata)
            changed[0][field] = self.training_metadata[0][field]
            with self.assertRaises(ValueError):
                self.neighbors(query_metadata=changed)

    def test_missing_same_label_reference_rejected(self):
        with self.assertRaises(ValueError):
            self.neighbors(query_metadata=[metadata("query", "shake", "test")])

    def test_historical_rows_reconciled_completely(self):
        rows = self.neighbors()
        self.assertEqual(audit.reconcile_historical_orientation(rows, rows), 0)
        for saved in (rows[:1], [*rows, rows[0]]):
            with self.assertRaises(ValueError):
                audit.reconcile_historical_orientation(rows, saved)

    def test_historical_orientation_change_is_not_accepted(self):
        rows = self.neighbors()
        saved = deepcopy(rows)
        saved[0]["orientation_rms_deg"] += .1
        with self.assertRaises(ValueError):
            audit.reconcile_historical_orientation(rows, saved)


if __name__ == "__main__":
    unittest.main()
