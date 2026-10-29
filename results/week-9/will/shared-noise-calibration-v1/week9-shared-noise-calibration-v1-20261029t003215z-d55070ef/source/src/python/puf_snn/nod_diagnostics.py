"""Paired nod-amplitude diagnostics; no fitting, threshold selection or authentication.

Low-amplitude nods are legitimate synthetic execution variants in this analysis.
Anomaly flags therefore describe false alarms on these variants, not attack recall.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import math
from pathlib import Path

import numpy as np


AMPLITUDES = (.1, .25, .5, .75, 1.0)
SPEEDS = (.75, 1.0, 1.25)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def require_hash(path: Path, expected: str) -> None:
    if not path.is_file() or sha256(path) != expected:
        raise ValueError(f"missing or hash-mismatched input: {path}")


def nod_config(pilot: dict, amplitude: float, speed: float) -> dict:
    if amplitude not in AMPLITUDES or speed not in SPEEDS:
        raise ValueError("only the historical predeclared nod sweep is supported")
    changed = deepcopy(pilot)
    nod = changed["synthetic_motion"]["classes"]["nod"]
    nod["peak_rotation_deg"] *= amplitude
    nod["vertical_position_peak_m"] *= amplitude
    changed["synthetic_motion"]["motion_duration_s_range"] = [
        value / speed for value in pilot["synthetic_motion"]["motion_duration_s_range"]]
    return changed


def nominal_values(pilot: dict, amplitude: float, speed: float) -> dict:
    changed = nod_config(pilot, amplitude, speed)
    nod = changed["synthetic_motion"]["classes"]["nod"]
    return {"amplitude_scale": amplitude, "speed_scale": speed,
            "nominal_rotation_coefficient_deg": nod["peak_rotation_deg"],
            "nominal_vertical_position_coefficient_m": nod["vertical_position_peak_m"],
            "duration_range_before_group_effects_and_clipping_s": changed["synthetic_motion"]["motion_duration_s_range"]}


def validate_saved_sweep(sweep: dict, configuration: dict, sources: list[dict]) -> list[dict]:
    settings = configuration["nod_sweep"]
    if tuple(settings["amplitude_scales"]) != AMPLITUDES or tuple(settings["speed_scales"]) != SPEEDS:
        raise ValueError("saved sweep is not the predeclared amplitude/time grid")
    names = {f"{family}_seed_{seed}" for family in ("logistic_regression", "random_forest", "snn")
             for seed in configuration["model_seeds"]}
    expected_keys = {(name, split, amplitude, speed) for name in names for split in ("validation", "test")
                     for amplitude in AMPLITUDES for speed in SPEEDS}
    counts = {split: sum(record["split"] == split and record["label"] == "nod" for record in sources)
              for split in ("validation", "test")}
    keys, rows = set(), []
    for row in sweep["runs"]:
        key = (row["model"], row["split"], row["amplitude_scale"], row["speed_scale"])
        if key in keys or key not in expected_keys:
            raise ValueError("duplicate or unexpected saved sweep condition")
        keys.add(key)
        matrix = np.asarray(row["metrics"]["confusion_matrix"])
        count = counts[row["split"]]
        if (matrix.shape != (5, 5) or not np.all(matrix == np.floor(matrix)) or np.any(matrix < 0)
                or count <= 0 or matrix.sum() != count or matrix[1:].sum() != 0
                or row["sample_count"] != count or row["metrics"]["sample_count"] != count):
            raise ValueError("saved nod confusion counts do not match the fixed source cohort")
        nod_count, still_count = int(matrix[0, 0]), int(matrix[0, 4])
        if (abs(row["nod_recall"] - nod_count / count) > 1e-12
                or abs(row["still_prediction_fraction"] - still_count / count) > 1e-12
                or abs(row["duration_scale"] - 1 / row["speed_scale"]) > 1e-12):
            raise ValueError("saved nod sensitivity rates disagree with counts")
        rows.append({"model": row["model"], "split": row["split"], "amplitude_scale": row["amplitude_scale"],
                     "speed_scale": row["speed_scale"], "sample_count": count,
                     "nod_prediction_count": nod_count, "still_prediction_count": still_count,
                     "other_prediction_count": count - nod_count - still_count,
                     "nod_recall": row["nod_recall"], "still_prediction_fraction": row["still_prediction_fraction"],
                     "mean_observed_peak_rotation_deg": row["mean_peak_rotation_deg"],
                     "mean_observed_angular_speed_rms_deg_s": row["mean_angular_speed_rms_deg_s"]})
    if keys != expected_keys:
        raise ValueError("incomplete saved nod sweep; do not silently report a subset")
    return rows


def assert_paired_sources(generated: list[dict], sources: list[dict]) -> None:
    """Keep all identities, labels, source trials, timestamps and tracking flags paired."""
    originals = {record["window_id"]: record for record in sources if record["label"] == "nod"}
    if len(originals) != sum(record["label"] == "nod" for record in sources):
        raise ValueError("duplicate original nod source")
    if len(generated) != len(originals) or {record["window_id"] for record in generated} != set(originals):
        raise ValueError("regenerated nod source mapping differs")
    for record in generated:
        original = originals[record["window_id"]]
        for field in ("label", "split", "source_trial_id", "trial_id", "device_id", "session_id", "sequence_number", "window_start_ns", "window_end_ns"):
            if record[field] != original[field]:
                raise ValueError(f"paired nod {field} changed")
        if len(record["samples"]) != 120 or len(original["samples"]) != 120:
            raise ValueError("nod source must retain 120 samples")
        for changed, initial in zip(record["samples"], original["samples"]):
            for field in ("sample_index", "capture_time_ns", "tracking_valid"):
                if changed[field] != initial[field]:
                    raise ValueError(f"paired nod sample {field} changed")


def example_source_ids(sources: list[dict]) -> dict:
    examples = {}
    for split in ("validation", "test"):
        for label in ("nod", "still"):
            identifiers = sorted(record["window_id"] for record in sources if record["split"] == split and record["label"] == label)
            if not identifiers:
                raise ValueError("missing predeclared trajectory example cohort")
            examples[f"{split}:{label}"] = identifiers[0]
    return examples


def load_verified_detectors(directory: Path, manifest: dict, thresholds: dict,
                            feature_names: tuple[str, ...], loader) -> tuple[dict, dict]:
    """Verify every trusted local pickle's hash before loading any of them."""
    paths, hashes = {}, {}
    for name in sorted(thresholds):
        if not name.startswith("anomaly_") or not name.replace("_", "").isalnum():
            raise ValueError("invalid detector artifact name")
        path = directory / "models" / f"{name}.joblib"
        relative = f"models/{name}.joblib"
        require_hash(path, manifest["artifacts"].get(relative, ""))
        paths[name], hashes[relative] = path, sha256(path)
    detectors = {}
    for name, path in paths.items():
        saved = loader(path)
        expected = {key: value for key, value in thresholds[name].items() if key not in ("kind", "seed")}
        if (tuple(saved["feature_names"]) != feature_names or saved["seed"] != thresholds[name]["seed"]
                or saved["threshold"] != expected or thresholds[name]["selected_from"] != "validation"):
            raise ValueError("frozen detector metadata differs from saved validation decisions")
        detectors[name] = saved["model"]
    return detectors, hashes


def score_fixed_detectors(features: np.ndarray, detectors: dict, thresholds: dict, scorer) -> dict:
    if features.ndim != 2 or features.shape[1] != 48 or not np.all(np.isfinite(features)):
        raise ValueError("detector inputs must be finite [windows, 48] features")
    if set(detectors) != set(thresholds):
        raise ValueError("frozen detector set differs")
    result = {}
    for name, model in detectors.items():
        threshold = thresholds[name]["threshold"]
        if not math.isfinite(threshold):
            raise ValueError("nonfinite frozen threshold")
        scores = np.asarray(scorer(model, features), dtype=float)
        if scores.shape != (len(features),) or not np.all(np.isfinite(scores)) or np.any((scores < 0) | (scores > 1)):
            raise ValueError("invalid frozen detector scores")
        result[name] = {"scores": scores, "flags": scores >= threshold}
    return result


def summarize_flags(flagged: int, eligible: int, planned: int, interval_function) -> dict:
    if not 0 <= flagged <= eligible <= planned:
        raise ValueError("invalid legitimate-variation counts")
    interval = interval_function(flagged, eligible)
    return {"planned_count": planned, "quality_valid_count": eligible,
            "pre_tag_quality_blocked_count": planned - eligible,
            "legitimate_variant_flagged_count": flagged, "legitimate_variant_unflagged_count": eligible - flagged,
            "legitimate_variant_flag_rate": flagged / eligible if eligible else None,
            "flag_rate_ci_low": interval[0] if interval else None, "flag_rate_ci_high": interval[1] if interval else None,
            "interpretation": "flag frequency on legitimate synthetic motion; not adversarial detection recall"}
