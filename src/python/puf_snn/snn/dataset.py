"""
this file converts the existing motion windows into 120 by 7 SNN sequences
labels identifiers timestamps and tracking flags stay outside the model input
"""

from __future__ import annotations

import json

from pathlib import Path

import numpy as np


LABELS = (
    "nod",
    "shake",
    "look_left_return",
    "look_right_return",
    "still",
)

SPLITS = (
    "train",
    "validation",
    "test",
)

EXPECTED_SAMPLES = 120
INPUT_CHANNELS = 7


def load_records(input_path: Path) -> list[dict]:
    if not input_path.exists():
        raise FileNotFoundError(f"dataset not found: {input_path}")

    records = []

    with input_path.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            stripped_line = line.strip()

            if not stripped_line:
                continue

            try:
                record = json.loads(stripped_line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSON on line {line_number}: {error}") from error

            if not isinstance(record, dict):
                raise ValueError(f"line {line_number} must contain one JSON object")

            records.append(record)

    if not records:
        raise ValueError("the dataset is empty")

    return records


def normalize_quaternions(orientations: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(orientations, axis=1, keepdims=True)

    if np.any(norms <= 1e-12) or not np.all(np.isfinite(norms)):
        raise ValueError("orientation quaternions must have finite nonzero norms")

    return orientations / norms


def multiply_quaternions(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    first_x, first_y, first_z, first_w = first
    second_x, second_y, second_z, second_w = second

    return np.array(
        [
            first_w * second_x + first_x * second_w + first_y * second_z - first_z * second_y,
            first_w * second_y - first_x * second_z + first_y * second_w + first_z * second_x,
            first_w * second_z + first_x * second_y - first_y * second_x + first_z * second_w,
            first_w * second_w - first_x * second_x - first_y * second_y - first_z * second_z,
        ],
        dtype=np.float64,
    )


def make_orientation_relative(orientations: np.ndarray) -> np.ndarray:
    continuous_orientations = normalize_quaternions(orientations.astype(np.float64)).copy()

    # q and negative q describe the same rotation so adjacent signs remain continuous
    for sample_index in range(1, len(continuous_orientations)):
        previous_orientation = continuous_orientations[sample_index - 1]
        current_orientation = continuous_orientations[sample_index]

        if np.dot(previous_orientation, current_orientation) < 0:
            continuous_orientations[sample_index] *= -1.0

    first_orientation = continuous_orientations[0]
    first_orientation_inverse = np.array(
        [
            -first_orientation[0],
            -first_orientation[1],
            -first_orientation[2],
            first_orientation[3],
        ],
        dtype=np.float64,
    )

    relative_orientations = []

    for orientation in continuous_orientations:
        relative_orientations.append(multiply_quaternions(first_orientation_inverse, orientation))

    return normalize_quaternions(np.asarray(relative_orientations))


def record_to_sequence(record: dict) -> np.ndarray:
    samples = record.get("samples")

    if not isinstance(samples, list):
        raise ValueError("record is missing its samples list")

    if len(samples) != EXPECTED_SAMPLES:
        raise ValueError(f"expected {EXPECTED_SAMPLES} samples but found {len(samples)}")

    positions = []
    orientations = []

    for sample_index, sample in enumerate(samples):
        position = sample.get("position_m")
        orientation = sample.get("orientation_xyzw")

        if not isinstance(position, list) or len(position) != 3:
            raise ValueError(f"sample {sample_index} has an invalid position")

        if not isinstance(orientation, list) or len(orientation) != 4:
            raise ValueError(f"sample {sample_index} has an invalid orientation")

        positions.append(position)
        orientations.append(orientation)

    position_array = np.asarray(positions, dtype=np.float64)
    orientation_array = np.asarray(orientations, dtype=np.float64)

    if not np.all(np.isfinite(position_array)):
        raise ValueError("position values must be finite")

    if not np.all(np.isfinite(orientation_array)):
        raise ValueError("orientation values must be finite")

    relative_positions = position_array - position_array[0]
    relative_orientations = make_orientation_relative(orientation_array)
    sequence = np.concatenate([relative_positions, relative_orientations], axis=1)

    if sequence.shape != (EXPECTED_SAMPLES, INPUT_CHANNELS):
        raise ValueError(f"expected sequence shape {(EXPECTED_SAMPLES, INPUT_CHANNELS)} but found {sequence.shape}")

    return sequence


def _check_split_separation(split_metadata: dict[str, list[dict]]) -> None:
    # no saved window source trial or session may occur in two data splits
    for metadata_field in ("window_id", "source_trial_id", "session_id"):
        split_values = {
            split_name: {str(item[metadata_field]) for item in split_metadata[split_name]}
            for split_name in SPLITS
        }

        for first_index, first_split in enumerate(SPLITS):
            for second_split in SPLITS[first_index + 1:]:
                overlap = split_values[first_split] & split_values[second_split]

                if overlap:
                    example = sorted(overlap)[0]
                    raise ValueError(f"{metadata_field} overlaps between {first_split} and {second_split}: {example}")


def build_snn_datasets(records: list[dict]) -> dict[str, dict[str, object]]:
    split_sequences = {split_name: [] for split_name in SPLITS}
    split_label_indexes = {split_name: [] for split_name in SPLITS}
    split_metadata = {split_name: [] for split_name in SPLITS}
    split_records = {split_name: [] for split_name in SPLITS}
    label_to_index = {label: label_index for label_index, label in enumerate(LABELS)}

    for record_index, record in enumerate(records):
        split_name = record.get("split")
        label = record.get("label")

        if split_name not in SPLITS:
            raise ValueError(f"record {record_index} has invalid split: {split_name}")

        if label not in LABELS:
            raise ValueError(f"record {record_index} has invalid label: {label}")

        metadata = {
            "window_id": record.get("window_id"),
            "source_trial_id": record.get("source_trial_id"),
            "device_id": record.get("device_id"),
            "session_id": record.get("session_id"),
            "trial_id": record.get("trial_id"),
            "sequence_number": record.get("sequence_number"),
            "label": label,
            "split": split_name,
        }

        for metadata_field in ("window_id", "source_trial_id", "session_id"):
            if not isinstance(metadata[metadata_field], str) or not metadata[metadata_field]:
                raise ValueError(f"record {record_index} has invalid {metadata_field}")

        split_sequences[split_name].append(record_to_sequence(record))
        split_label_indexes[split_name].append(label_to_index[label])
        split_metadata[split_name].append(metadata)
        split_records[split_name].append(record)

    _check_split_separation(split_metadata)
    datasets = {}

    for split_name in SPLITS:
        if not split_sequences[split_name]:
            raise ValueError(f"the {split_name} split is empty")

        datasets[split_name] = {
            "sequences": np.stack(split_sequences[split_name]),
            "label_indexes": np.asarray(split_label_indexes[split_name], dtype=np.int64),
            "metadata": split_metadata[split_name],
            "records": split_records[split_name],
        }

    missing_training_labels = set(range(len(LABELS))) - set(datasets["train"]["label_indexes"])

    if missing_training_labels:
        missing_names = ", ".join(LABELS[label_index] for label_index in sorted(missing_training_labels))
        raise ValueError(f"training data is missing labels: {missing_names}")

    return datasets


def fit_channel_normalization(training_sequences: np.ndarray) -> dict[str, np.ndarray]:
    if training_sequences.ndim != 3 or training_sequences.shape[1:] != (EXPECTED_SAMPLES, INPUT_CHANNELS):
        raise ValueError(f"training sequences must have shape [windows, {EXPECTED_SAMPLES}, {INPUT_CHANNELS}]")

    channel_mean = training_sequences.mean(axis=(0, 1))
    channel_standard_deviation = training_sequences.std(axis=(0, 1))
    channel_standard_deviation = np.where(channel_standard_deviation <= 1e-12, 1.0, channel_standard_deviation)

    return {
        "mean": channel_mean,
        "standard_deviation": channel_standard_deviation,
    }


def apply_channel_normalization(sequences: np.ndarray, normalization: dict[str, np.ndarray]) -> np.ndarray:
    if sequences.ndim != 3 or sequences.shape[1:] != (EXPECTED_SAMPLES, INPUT_CHANNELS):
        raise ValueError(f"sequences must have shape [windows, {EXPECTED_SAMPLES}, {INPUT_CHANNELS}]")

    channel_mean = np.asarray(normalization["mean"], dtype=np.float64)
    channel_standard_deviation = np.asarray(normalization["standard_deviation"], dtype=np.float64)

    if channel_mean.shape != (INPUT_CHANNELS,) or channel_standard_deviation.shape != (INPUT_CHANNELS,):
        raise ValueError("normalization statistics must contain one value per input channel")

    if np.any(channel_standard_deviation <= 0.0):
        raise ValueError("normalization standard deviations must be positive")

    return ((sequences - channel_mean) / channel_standard_deviation).astype(np.float32)


def make_epoch_order(window_count: int, seed: int) -> np.ndarray:
    if isinstance(window_count, bool) or not isinstance(window_count, int) or window_count <= 0:
        raise ValueError("window_count must be a positive integer")

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")

    return np.random.default_rng(seed).permutation(window_count)
