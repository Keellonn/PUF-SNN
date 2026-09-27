"""
this file checks copied sensor windows and compares motion without using identifiers
quaternion distances and angular velocity respect equivalent quaternion signs
"""

from __future__ import annotations

import hashlib
import json

from collections import Counter
from itertools import combinations

import numpy as np

from puf_snn.snn.dataset import SPLITS, multiply_quaternions, record_to_sequence


def full_window_hash(record: dict) -> str:
    samples = record["samples"]
    first_time = samples[0]["capture_time_ns"]
    content = {
        "coordinate_frame": record["coordinate_frame"],
        "target_sample_rate_hz": record["target_sample_rate_hz"],
        "duration_ns": record["window_end_ns"] - record["window_start_ns"],
        "first_sample_offset_ns": first_time - record["window_start_ns"],
        "samples": [{"sample_index": sample["sample_index"], "relative_time_ns": sample["capture_time_ns"] - first_time, "position_m": [float(value) for value in sample["position_m"]], "orientation_xyzw": [float(value) for value in sample["orientation_xyzw"]], "tracking_valid": sample["tracking_valid"]} for sample in samples],
    }
    encoded = json.dumps(content, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def full_window_duplicates(records: list[dict]) -> dict:
    hashes = {split: Counter(full_window_hash(record) for record in records if record["split"] == split) for split in SPLITS}
    pairs = {}

    for first, second in combinations(SPLITS, 2):
        shared = hashes[first].keys() & hashes[second].keys()
        pairs[f"{first}_to_{second}"] = {
            "shared_payload_hashes": len(shared),
            "matching_window_pairs": sum(hashes[first][value] * hashes[second][value] for value in shared),
        }

    return {"method": "full sample content and relative timestamps; excludes label, split, IDs, sequence and absolute time origin", "pairs": pairs, "passed": all(pair["matching_window_pairs"] == 0 for pair in pairs.values())}


def assert_no_full_window_duplicates(records: list[dict]) -> None:
    result = full_window_duplicates(records)

    if not result["passed"]:
        raise ValueError(f"sensor-window content overlaps across splits: {result['pairs']}")


def rotation_vectors(quaternions: np.ndarray) -> np.ndarray:
    values = np.asarray(quaternions, dtype=np.float64).copy()
    values /= np.linalg.norm(values, axis=-1, keepdims=True)
    values = np.where(values[..., 3:4] < 0.0, -values, values)
    lengths = np.linalg.norm(values[..., :3], axis=-1, keepdims=True)
    angles = 2.0 * np.arctan2(lengths, values[..., 3:4])
    scales = np.divide(angles, lengths, out=np.full_like(lengths, 2.0), where=lengths > 1e-12)
    return values[..., :3] * scales


def vectors_to_quaternions(vectors: np.ndarray) -> np.ndarray:
    angles = np.linalg.norm(vectors, axis=-1, keepdims=True)
    scales = np.divide(np.sin(angles / 2.0), angles, out=np.full_like(angles, 0.5), where=angles > 1e-12)
    return np.concatenate([vectors * scales, np.cos(angles / 2.0)], axis=-1)


def angular_velocity(sequence: np.ndarray, times_s: np.ndarray) -> np.ndarray:
    intervals = np.diff(times_s)

    if len(times_s) != len(sequence) or np.any(intervals <= 0.0):
        raise ValueError("angular velocity requires increasing sample timestamps")

    orientations = sequence[:, 3:7]
    increments = []

    for previous, current in zip(orientations[:-1], orientations[1:]):
        inverse = previous * np.array([-1.0, -1.0, -1.0, 1.0])
        increments.append(multiply_quaternions(inverse, current))

    velocity = rotation_vectors(np.asarray(increments)) / intervals[:, None]
    return np.vstack([np.zeros((1, 3)), velocity])


def record_times(record: dict) -> np.ndarray:
    values = np.asarray([sample["capture_time_ns"] for sample in record["samples"]], dtype=np.int64)
    return (values - values[0]).astype(np.float64) / 1_000_000_000.0


def feature_group(record: dict, group: str) -> np.ndarray:
    sequence = record_to_sequence(record)

    if group in ("raw_relative_pose", "position_plus_quaternion"):
        return sequence

    if group == "quaternion_only":
        return sequence[:, 3:7]

    if group == "quaternion_plus_angular_velocity":
        return np.concatenate([sequence[:, 3:7], angular_velocity(sequence, record_times(record))], axis=1)

    raise ValueError(f"unknown feature group: {group}")


def physical_distances(queries: np.ndarray, references: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    # position RMS uses meters and orientation RMS uses shortest rotation angles
    delta = queries[:, None, :, :3] - references[None, :, :, :3]
    position_rms = np.sqrt(np.mean(np.sum(delta * delta, axis=-1), axis=-1))
    dots = np.einsum("qtc,rtc->qrt", queries[:, :, 3:7], references[:, :, 3:7])
    angles = np.degrees(2.0 * np.arccos(np.clip(np.abs(dots), 0.0, 1.0)))
    orientation_rms = np.sqrt(np.mean(angles * angles, axis=-1))
    return position_rms, orientation_rms


def nearest_neighbors(reference_records: list[dict], query_records: list[dict], position_threshold_m: float, orientation_threshold_deg: float) -> list[dict]:
    if not reference_records or not query_records or position_threshold_m <= 0.0 or orientation_threshold_deg <= 0.0:
        raise ValueError("neighbor analysis requires nonempty data and positive thresholds")

    references = np.stack([record_to_sequence(record) for record in reference_records])
    queries = np.stack([record_to_sequence(record) for record in query_records])
    reference_labels = np.asarray([record["label"] for record in reference_records])
    rows = []

    for start in range(0, len(queries), 8):
        position, orientation = physical_distances(queries[start:start + 8], references)
        combined = np.sqrt((position / position_threshold_m) ** 2 + (orientation / orientation_threshold_deg) ** 2)

        for offset in range(len(position)):
            record = query_records[start + offset]
            same_label = reference_labels == record["label"]

            if not np.any(same_label):
                raise ValueError(f"reference split has no {record['label']} windows")

            for scope, mask in (("any_label", np.ones(len(references), dtype=bool)), ("same_label", same_label)):
                orientation_index = int(np.argmin(np.where(mask, orientation[offset], np.inf)))
                combined_index = int(np.argmin(np.where(mask, combined[offset], np.inf)))
                near = mask & (position[offset] <= position_threshold_m) & (orientation[offset] <= orientation_threshold_deg)
                rows.append({"window_id": record["window_id"], "label": record["label"], "scope": scope, "orientation_neighbor_id": reference_records[orientation_index]["window_id"], "orientation_rms_deg": float(orientation[offset, orientation_index]), "combined_neighbor_id": reference_records[combined_index]["window_id"], "combined_scaled_distance": float(combined[offset, combined_index]), "combined_position_rms_m": float(position[offset, combined_index]), "combined_orientation_rms_deg": float(orientation[offset, combined_index]), "has_neighbor_within_both_thresholds": bool(np.any(near))})

    return rows


def distribution(values: list[float]) -> dict:
    array = np.asarray(values, dtype=np.float64)

    if len(array) == 0 or not np.all(np.isfinite(array)):
        raise ValueError("a distribution needs finite observations")

    return {"count": len(array), "minimum": float(array.min()), "p05": float(np.percentile(array, 5)), "median": float(np.median(array)), "mean": float(array.mean()), "p95": float(np.percentile(array, 95)), "maximum": float(array.max())}


def pooled_metrics(matrices: list[list[list[int]]], labels: tuple[str, ...]) -> dict:
    matrix = np.sum(np.asarray(matrices, dtype=np.int64), axis=0)

    if matrix.shape != (len(labels), len(labels)) or np.any(matrix < 0) or matrix.sum() <= 0:
        raise ValueError("pooled confusion matrices must contain nonnegative class counts")

    true_positive = np.diag(matrix)
    support = matrix.sum(axis=1)
    predicted = matrix.sum(axis=0)
    precision = np.divide(true_positive, predicted, out=np.zeros(len(labels), dtype=float), where=predicted > 0)
    recall = np.divide(true_positive, support, out=np.zeros(len(labels), dtype=float), where=support > 0)
    class_f1 = np.divide(2 * precision * recall, precision + recall, out=np.zeros(len(labels), dtype=float), where=precision + recall > 0)
    return {"prediction_count": int(matrix.sum()), "accuracy": float(true_positive.sum() / matrix.sum()), "macro_f1": float(class_f1.mean()), "confusion_matrix": matrix.tolist(), "per_class": {label: {"precision": float(precision[index]), "recall": float(recall[index]), "f1": float(class_f1[index]), "support": int(support[index])} for index, label in enumerate(labels)}, "limitation": "pooled model predictions on repeated source windows; not independent new recordings"}


def slerp(first: np.ndarray, second: np.ndarray, fraction: np.ndarray) -> np.ndarray:
    dots = np.sum(first * second, axis=1, keepdims=True)
    second = np.where(dots < 0.0, -second, second)
    dots = np.clip(np.abs(dots), 0.0, 1.0)
    angles = np.arccos(dots)
    denominator = np.sin(angles)
    safe = np.where(denominator < 1e-8, 1.0, denominator)
    spherical = np.sin((1.0 - fraction) * angles) / safe * first + np.sin(fraction * angles) / safe * second
    linear = (1.0 - fraction) * first + fraction * second
    result = np.where(dots > 0.9995, linear, spherical)
    return result / np.linalg.norm(result, axis=1, keepdims=True)


def transformed_record(record: dict, amplitude: float = 1.0, speed: float = 1.0, initial_orientation_deg: float = 0.0, shift_seconds: float = 0.0) -> dict:
    if amplitude <= 0.0 or speed <= 0.0:
        raise ValueError("amplitude and speed must be positive")

    sequence = record_to_sequence(record)
    times = record_times(record)
    source_indexes = np.interp((times - shift_seconds) * speed, times, np.arange(len(times), dtype=np.float64))
    lower = np.floor(source_indexes).astype(int)
    upper = np.minimum(lower + 1, 119)
    fractions = (source_indexes - lower)[:, None]
    positions = ((1.0 - fractions) * sequence[lower, :3] + fractions * sequence[upper, :3]) * amplitude
    quaternions = slerp(sequence[lower, 3:7], sequence[upper, 3:7], fractions)
    quaternions = vectors_to_quaternions(rotation_vectors(quaternions) * amplitude)
    rotation = vectors_to_quaternions(np.array([[0.0, np.radians(initial_orientation_deg), 0.0]]))[0]
    initial = np.asarray(record["samples"][0]["orientation_xyzw"], dtype=np.float64)
    initial /= np.linalg.norm(initial)
    initial = multiply_quaternions(rotation, initial)
    absolute = np.stack([multiply_quaternions(initial, quaternion) for quaternion in quaternions])
    original_position = np.asarray(record["samples"][0]["position_m"], dtype=np.float64)
    changed = dict(record)
    changed["samples"] = []

    for index, sample in enumerate(record["samples"]):
        row = dict(sample)
        row["position_m"] = (positions[index] + original_position).tolist()
        row["orientation_xyzw"] = absolute[index].tolist()
        changed["samples"].append(row)

    return changed
