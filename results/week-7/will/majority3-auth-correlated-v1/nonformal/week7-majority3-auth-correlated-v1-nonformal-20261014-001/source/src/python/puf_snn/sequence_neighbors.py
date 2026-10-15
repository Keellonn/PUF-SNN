"""Fixed-grid nearest-training distances; no fitting of a classifier or threshold.

The physical orientation metric is sign-invariant geodesic RMS in degrees.
The complete-input metric is RMS over all 840 normalized pose coordinates.
"""

from __future__ import annotations

import numpy as np

from puf_snn.snn.dataset import apply_channel_normalization, fit_channel_normalization


def checked_sequences(values: np.ndarray) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 3 or array.shape[1:] != (120, 7) or len(array) == 0:
        raise ValueError("sequences must be nonempty [windows, 120, 7] arrays")
    if not np.all(np.isfinite(array)):
        raise ValueError("sequence components must be finite")
    return array


def fixed_grid_offsets(records: list[dict]) -> list[int]:
    """Require the same relative sample grid; never interpolate or time-warp it."""
    if not records:
        raise ValueError("fixed-grid analysis needs records")
    expected = None
    for record in records:
        samples = record.get("samples", [])
        if len(samples) != 120:
            raise ValueError("fixed-grid analysis requires exactly 120 samples")
        if [sample.get("sample_index") for sample in samples] != list(range(120)):
            raise ValueError("sample indexes must be ordered 0..119")
        times = [sample["capture_time_ns"] for sample in samples]
        if any(isinstance(value, bool) or not isinstance(value, int) for value in times):
            raise ValueError("timestamps must be integer nanoseconds")
        offsets = [value - times[0] for value in times]
        gaps = np.diff(offsets)
        if np.any(gaps <= 0) or np.any(gaps > 50_000_000):
            raise ValueError("sample timestamps violate increasing/gap policy")
        if not np.all(gaps == gaps[0]):
            raise ValueError("the source is not a fixed sample grid")
        if expected is not None and offsets != expected:
            raise ValueError("records have different grids; do not silently realign them")
        expected = offsets
    return expected


def fit_training_scaler(training: np.ndarray) -> dict[str, np.ndarray]:
    """Use the existing SNN channel scaler, fit only on reference training windows."""
    return fit_channel_normalization(checked_sequences(training))


def normalized_model_inputs(values: np.ndarray, scaler: dict) -> np.ndarray:
    mean = np.asarray(scaler["mean"], dtype=np.float64)
    scale = np.asarray(scaler["standard_deviation"], dtype=np.float64)
    if mean.shape != (7,) or scale.shape != (7,) or not np.all(np.isfinite(mean)):
        raise ValueError("scaler must contain seven finite channel means")
    if not np.all(np.isfinite(scale)) or np.any(scale <= 0):
        raise ValueError("scaler must contain seven finite positive standard deviations")
    # Match model-input float32 rounding, then accumulate distances in float64.
    result = apply_channel_normalization(checked_sequences(values), scaler)
    if not np.all(np.isfinite(result)):
        raise ValueError("normalization produced nonfinite model input")
    return result.astype(np.float64)


def full_sequence_rms(queries: np.ndarray, references: np.ndarray) -> np.ndarray:
    query = checked_sequences(queries)
    reference = checked_sequences(references)
    # Direct differences avoid catastrophic cancellation for equal/near-equal inputs.
    differences = query[:, None, :, :] - reference[None, :, :, :]
    return np.sqrt(np.mean(differences * differences, axis=(2, 3)))


def orientation_rms_degrees(queries: np.ndarray, references: np.ndarray) -> np.ndarray:
    query = checked_sequences(queries)[:, :, 3:7]
    reference = checked_sequences(references)[:, :, 3:7]
    query_norm = np.linalg.norm(query, axis=2, keepdims=True)
    reference_norm = np.linalg.norm(reference, axis=2, keepdims=True)
    if np.any(query_norm <= 1e-12) or np.any(reference_norm <= 1e-12):
        raise ValueError("orientation distance requires nonzero quaternions")
    dots = np.einsum("qtc,rtc->qrt", query / query_norm, reference / reference_norm)
    angles = np.degrees(2 * np.arccos(np.clip(np.abs(dots), 0, 1)))
    return np.sqrt(np.mean(angles * angles, axis=2))


def nearest_training_rows(training: np.ndarray, queries: np.ndarray,
                          training_metadata: list[dict], query_metadata: list[dict],
                          scaler: dict, chunk_size: int = 8) -> list[dict]:
    training = checked_sequences(training)
    queries = checked_sequences(queries)
    if len(training_metadata) != len(training) or len(query_metadata) != len(queries):
        raise ValueError("metadata length differs from its sequences")
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size < 1:
        raise ValueError("chunk size must be a positive integer")
    if any(row["split"] != "train" for row in training_metadata):
        raise ValueError("references must all be training windows")
    if any(row["split"] not in ("validation", "test") for row in query_metadata):
        raise ValueError("queries must all be validation or test windows")
    training_ids = [row["window_id"] for row in training_metadata]
    query_ids = [row["window_id"] for row in query_metadata]
    if len(set(training_ids)) != len(training_ids) or len(set(query_ids)) != len(query_ids):
        raise ValueError("duplicate window ID")
    for field in ("window_id", "source_trial_id", "session_id"):
        if {row[field] for row in training_metadata} & {row[field] for row in query_metadata}:
            raise ValueError(f"training/query {field} overlap")
    if training_ids != sorted(training_ids):
        raise ValueError("sort training windows by ID for deterministic nearest-neighbor ties")
    training_labels = np.asarray([row["label"] for row in training_metadata])
    scaled_training = normalized_model_inputs(training, scaler)
    scaled_queries = normalized_model_inputs(queries, scaler)
    rows = []
    for start in range(0, len(queries), chunk_size):
        feature = full_sequence_rms(scaled_queries[start:start + chunk_size], scaled_training)
        orientation = orientation_rms_degrees(queries[start:start + chunk_size], training)
        for offset in range(len(feature)):
            query = query_metadata[start + offset]
            same_label = training_labels == query["label"]
            if not np.any(same_label):
                raise ValueError("a query class is missing from training")
            for scope, mask in (("any_label", np.ones(len(training), dtype=bool)),
                                ("same_label", same_label)):
                feature_index = int(np.argmin(np.where(mask, feature[offset], np.inf)))
                orientation_index = int(np.argmin(np.where(mask, orientation[offset], np.inf)))
                rows.append({
                    "window_id": query["window_id"], "split": query["split"],
                    "label": query["label"], "scope": scope,
                    "sequence_neighbor_id": training_ids[feature_index],
                    "sequence_neighbor_label": training_metadata[feature_index]["label"],
                    "normalized_sequence_rms": float(feature[offset, feature_index]),
                    "orientation_neighbor_id": training_ids[orientation_index],
                    "orientation_neighbor_label": training_metadata[orientation_index]["label"],
                    "orientation_rms_deg": float(orientation[offset, orientation_index]),
                    "orientation_rms_at_sequence_neighbor_deg": float(orientation[offset, feature_index]),
                })
    return rows


def reconcile_historical_orientation(rows: list[dict], historical: list[dict],
                                     tolerance_deg: float = 1e-5) -> float:
    """Check all saved test distances, allowing only quaternion roundoff, not omissions."""
    current = {(row["window_id"], row["scope"]): row for row in rows if row["split"] == "test"}
    saved = {(row["window_id"], row["scope"]): row for row in historical}
    if len(saved) != len(historical) or len(current) != sum(row["split"] == "test" for row in rows):
        raise ValueError("duplicate historical/current orientation row")
    if current.keys() != saved.keys() or not current:
        raise ValueError("historical orientation source cohort is incomplete or changed")
    maximum_difference = 0.0
    for key, row in current.items():
        if row["label"] != saved[key]["label"]:
            raise ValueError("historical orientation label changed")
        difference = abs(row["orientation_rms_deg"] - saved[key]["orientation_rms_deg"])
        if not np.isfinite(difference) or difference > tolerance_deg:
            raise ValueError("recomputed orientation distance differs from historical evidence")
        maximum_difference = max(maximum_difference, difference)
    return maximum_difference
