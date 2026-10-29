"""
this file creates seeded sensor changes without touching authentication keys or verifier state
attack information stays outside the motion record and every copy stays in its source split
construction failures are reported separately from quality-valid changes that can be authenticated
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import struct

import numpy as np

from puf_snn.auth.binary_window import encode_window
from puf_snn.integration import processed_record_to_wire_window
from puf_snn.motion_diagnostics import full_window_hash, slerp, vectors_to_quaternions
from puf_snn.snn.dataset import multiply_quaternions


ATTACK_UNITS = {
    "position_noise": "meters_per_axis_standard_deviation",
    "orientation_noise": "degrees_signed_angle_standard_deviation",
    "position_drift": "meters_total_drift",
    "orientation_drift": "degrees_total_drift",
    "timestamp_jitter": "milliseconds_maximum_absolute_offset",
    "dropped_samples": "fraction_of_source_samples",
    "frozen_pose": "milliseconds",
    "position_jump": "meters_step_offset",
    "orientation_jump": "degrees_step_offset",
}
MAXIMUM_GAP_NS = 50_000_000
SPLITS = ("train", "validation", "test")


def validate_attack_config(config: dict) -> None:
    if config.get("config_version") != "tier2-stream-attacks-v1":
        raise ValueError("unsupported stream-attack configuration")
    if type(config.get("attack_generation_seed")) is not int or config["attack_generation_seed"] < 0:
        raise ValueError("attack_generation_seed must be a nonnegative integer")
    if config.get("injection_stage") != "before_tag":
        raise ValueError("Tier 2 changes must be applied before legitimate tag creation")
    if config.get("severity_names") != ["low", "medium", "high"]:
        raise ValueError("the attack sweep requires low, medium, and high severities")
    if type(config.get("examples_per_split")) is not int or config["examples_per_split"] < 1:
        raise ValueError("examples_per_split must be a positive integer")

    bounds = config.get("magnitude_scale_range")
    if not isinstance(bounds, list) or len(bounds) != 2:
        raise ValueError("magnitude_scale_range must contain two values")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in bounds):
        raise ValueError("magnitude scale bounds must be finite numbers")
    if not 0 < bounds[0] <= bounds[1]:
        raise ValueError("magnitude scale bounds must be positive and ordered")

    attacks = config.get("attacks")
    if not isinstance(attacks, list) or len(attacks) != len(ATTACK_UNITS):
        raise ValueError("the configuration must include all nine documented attacks")
    if any(not isinstance(attack, dict) for attack in attacks):
        raise ValueError("each attack setting must be an object")
    names = [attack.get("name") for attack in attacks]
    if len(set(names)) != len(names) or set(names) != set(ATTACK_UNITS):
        raise ValueError("attack names must be supported and unique")

    for attack in attacks:
        name = attack["name"]
        levels = attack.get("levels")
        if attack.get("unit") != ATTACK_UNITS[name]:
            raise ValueError(f"incorrect unit for {name}")
        if not isinstance(levels, list) or len(levels) != 3:
            raise ValueError(f"{name} must define three severity levels")
        if any(type(value) not in (int, float) or not math.isfinite(value) or value <= 0 for value in levels):
            raise ValueError(f"{name} levels must be positive finite numbers")
        if not levels[0] < levels[1] < levels[2]:
            raise ValueError(f"{name} levels must increase with severity")
        if name == "dropped_samples" and levels[-1] * bounds[1] >= 0.9:
            raise ValueError("drop settings must leave enough source samples for interpolation")
        if name == "frozen_pose" and levels[-1] * bounds[1] >= 1500:
            raise ValueError("freeze settings must leave an unfrozen part of the window")


def _case(record: dict, config: dict, attack: str, severity: str, nominal: float, unit: str, source_hash: str) -> dict:
    # each source and attack gets its own stream so file order cannot change the result
    seed_material = json.dumps([config["config_version"], config["attack_generation_seed"], record["window_id"], attack, severity], separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(seed_material).hexdigest()
    seed = int(digest[:16], 16)
    parameter_seed = int(digest[16:32], 16)
    rng = np.random.Generator(np.random.PCG64(parameter_seed))
    scale = float(rng.uniform(*config["magnitude_scale_range"])) if attack != "clean" else 1.0
    return {
        "case_id": "tier2-" + digest[:24],
        "source_window_id": record["window_id"],
        "source_trial_id": record["source_trial_id"],
        "source_motion_sha256": source_hash,
        "split": record["split"],
        "motion_label": record["label"],
        "attack_type": attack,
        "severity": severity,
        "is_anomaly": attack != "clean",
        "injection_stage": "before_tag" if attack != "clean" else "none",
        "nominal_magnitude": nominal,
        "magnitude": nominal * scale,
        "unit": unit,
        "derived_seed": seed,
        "parameter_seed": parameter_seed,
    }


def iter_attack_cases(records: list[dict], config: dict):
    validate_attack_config(config)
    windows = set()
    source_splits = {}
    session_splits = {}

    for record in records:
        if record["split"] not in SPLITS or record["window_id"] in windows:
            raise ValueError("source windows must have valid splits and unique identifiers")
        windows.add(record["window_id"])
        for key, mapping in ((record["source_trial_id"], source_splits), (record["session_id"], session_splits)):
            if key in mapping and mapping[key] != record["split"]:
                raise ValueError("a source trial or session cannot occur in multiple splits")
            mapping[key] = record["split"]

    for record in records:
        source_hash = full_window_hash(record)
        yield _case(record, config, "clean", "clean", 0.0, "none", source_hash)
        for attack in config["attacks"]:
            for severity, nominal in zip(config["severity_names"], attack["levels"], strict=True):
                yield _case(record, config, attack["name"], severity, float(nominal), attack["unit"], source_hash)


def canonical_motion_record(record: dict) -> dict:
    # both clean and changed conditions use the same canonical binary32 conversion
    window = processed_record_to_wire_window(record)
    encode_window(window)
    result = deepcopy(record)
    # the shared normalization is also applied to clean controls rather than only transformed copies
    orientations = _normalize_continuous(np.asarray([row["orientation_xyzw"] for row in result["samples"]], dtype=np.float64))
    for row, orientation in zip(result["samples"], orientations, strict=True):
        row["orientation_xyzw"] = orientation.tolist()
    window = processed_record_to_wire_window(result)
    encode_window(window)
    for row, sample in zip(result["samples"], window.samples, strict=True):
        row["position_m"] = [struct.unpack(">f", value.encode())[0] for value in sample.position_m]
        row["orientation_xyzw"] = [struct.unpack(">f", value.encode())[0] for value in sample.orientation_xyzw]
    return result


def _normalize_continuous(values: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    if np.any(norms <= 1e-12) or not np.all(np.isfinite(values)):
        raise ValueError("invalid quaternion while applying a sensor change")
    result = values / norms
    for index in range(1, len(result)):
        if np.dot(result[index - 1], result[index]) < 0:
            result[index] *= -1.0
    return result


def _direction(rng: np.random.Generator) -> np.ndarray:
    value = rng.normal(size=3)
    while np.linalg.norm(value) <= 1e-12:
        value = rng.normal(size=3)
    return value / np.linalg.norm(value)


def _rotate(orientations: np.ndarray, vectors: np.ndarray) -> np.ndarray:
    changes = vectors_to_quaternions(vectors)
    return np.stack([multiply_quaternions(change, original) for change, original in zip(changes, orientations, strict=True)])


def _resample(record: dict, times: np.ndarray, positions: np.ndarray, orientations: np.ndarray, tracking: np.ndarray) -> tuple[dict | None, str, dict]:
    # timestamps are handled relative to the window so large absolute times cannot lose precision
    target = np.asarray([row["capture_time_ns"] - record["window_start_ns"] for row in record["samples"]], dtype=np.int64)
    gaps = np.diff(times)
    details = {"source_sample_count": len(times), "maximum_source_gap_ms": float(np.max(gaps) / 1_000_000) if len(gaps) else None}
    if len(times) < 2 or np.any(gaps <= 0):
        return None, "source_timestamps_not_increasing", details
    if np.max(gaps) > MAXIMUM_GAP_NS:
        return None, "source_gap_exceeds_50_ms", details
    if times[0] > target[0] or times[-1] < target[-1]:
        return None, "source_does_not_cover_output_grid", details

    upper = np.searchsorted(times, target, side="right")
    upper = np.clip(upper, 1, len(times) - 1)
    lower = upper - 1
    fraction = ((target - times[lower]) / (times[upper] - times[lower]))[:, None]
    output_positions = (1.0 - fraction) * positions[lower] + fraction * positions[upper]
    output_orientations = slerp(orientations[lower], orientations[upper], fraction)
    output_tracking = tracking[lower] & tracking[upper]
    exact_lower = target == times[lower]
    exact_upper = target == times[upper]
    output_tracking[exact_lower] = tracking[lower[exact_lower]]
    output_tracking[exact_upper] = tracking[upper[exact_upper]]
    changed = deepcopy(record)
    for index, row in enumerate(changed["samples"]):
        row["position_m"] = output_positions[index].tolist()
        row["orientation_xyzw"] = output_orientations[index].tolist()
        row["tracking_valid"] = bool(output_tracking[index])
    return changed, "constructed", details


def apply_stream_attack(record: dict, case: dict) -> dict:
    bindings = {"source_window_id": "window_id", "source_trial_id": "source_trial_id", "split": "split", "motion_label": "label"}
    if any(case.get(field) != record.get(source) for field, source in bindings.items()):
        raise ValueError("attack case does not belong to this source record")
    if case.get("source_motion_sha256") != full_window_hash(record):
        raise ValueError("source motion changed after the attack plan was generated")
    attack = case.get("attack_type")
    if attack != "clean" and attack not in ATTACK_UNITS:
        raise ValueError("unsupported stream attack")
    magnitude = case.get("magnitude")
    if type(magnitude) not in (int, float) or not math.isfinite(magnitude) or magnitude < 0:
        raise ValueError("attack magnitude must be a finite nonnegative number")
    if case.get("is_anomaly") is not (attack != "clean"):
        raise ValueError("anomaly supervision must agree with the documented transform")
    if type(case.get("derived_seed")) is not int or case["derived_seed"] < 0:
        raise ValueError("each attack needs a nonnegative integer transform seed")
    if attack == "clean":
        if magnitude != 0 or case.get("injection_stage") != "none":
            raise ValueError("a clean control cannot contain an injected change")
    elif magnitude <= 0 or case.get("injection_stage") != "before_tag" or case.get("unit") != ATTACK_UNITS[attack]:
        raise ValueError("attack settings must retain their documented injection point and units")

    original = canonical_motion_record(record)
    rng = np.random.Generator(np.random.PCG64(case["derived_seed"]))
    changed = deepcopy(original)
    details = {}

    if attack != "clean":
        positions = np.asarray([row["position_m"] for row in original["samples"]], dtype=np.float64)
        orientations = _normalize_continuous(np.asarray([row["orientation_xyzw"] for row in original["samples"]], dtype=np.float64))
        times = np.asarray([row["capture_time_ns"] - original["window_start_ns"] for row in original["samples"]], dtype=np.int64)
        fraction = (times - times[0]) / (times[-1] - times[0])

        if attack == "position_noise":
            noise = rng.normal(0.0, magnitude, size=positions.shape)
            positions += noise
            details["realized_position_noise_rms_m"] = float(np.sqrt(np.mean(np.sum(noise * noise, axis=1))))

        elif attack == "orientation_noise":
            directions = rng.normal(size=(120, 3))
            directions /= np.linalg.norm(directions, axis=1, keepdims=True)
            angles = rng.normal(0.0, math.radians(magnitude), size=(120, 1))
            orientations = _rotate(orientations, directions * angles)
            details["realized_orientation_noise_rms_deg"] = float(np.degrees(np.sqrt(np.mean(angles * angles))))

        elif attack in ("position_drift", "orientation_drift"):
            direction = _direction(rng)
            ramp = fraction[:, None] * direction
            if attack == "position_drift":
                positions += ramp * magnitude
            else:
                orientations = _rotate(orientations, ramp * math.radians(magnitude))
            details["direction_xyz"] = direction.tolist()

        elif attack in ("position_jump", "orientation_jump"):
            onset = int(rng.integers(12, 108))
            direction = _direction(rng)
            if attack == "position_jump":
                positions[onset:] += direction * magnitude
            else:
                vectors = np.zeros((120, 3))
                vectors[onset:] = direction * math.radians(magnitude)
                orientations = _rotate(orientations, vectors)
            details.update(onset_sample=onset, direction_xyz=direction.tolist())

        elif attack == "frozen_pose":
            count = max(1, round(magnitude * 60 / 1000))
            if count >= 118:
                raise ValueError("freeze must leave room for surrounding source motion")
            onset = int(rng.integers(1, 120 - count))
            positions[onset:onset + count] = positions[onset - 1]
            orientations[onset:onset + count] = orientations[onset - 1]
            details.update(onset_sample=onset, frozen_sample_count=count, realized_duration_ms=count * 1000 / 60)

        elif attack in ("timestamp_jitter", "dropped_samples"):
            tracking = np.asarray([row["tracking_valid"] for row in original["samples"]], dtype=bool)
            if attack == "timestamp_jitter":
                # anchored endpoints isolate interior timestamp errors from capture-coverage loss
                offsets = np.rint(rng.uniform(-magnitude, magnitude, size=120) * 1_000_000).astype(np.int64)
                offsets[0] = 0
                offsets[-1] = 0
                times += offsets
                details["maximum_realized_offset_ms"] = float(np.max(np.abs(offsets)) / 1_000_000)
            else:
                count = max(1, round(magnitude * 120))
                if count >= 118:
                    raise ValueError("drop settings must retain both boundary samples")
                removed = np.sort(rng.choice(np.arange(1, 119), size=count, replace=False))
                keep = np.ones(120, dtype=bool)
                keep[removed] = False
                details.update(dropped_sample_indexes=removed.tolist(), realized_drop_fraction=count / 120)
                times, positions, orientations, tracking = times[keep], positions[keep], orientations[keep], tracking[keep]

            changed, reason, resampling_details = _resample(original, times, positions, orientations, tracking)
            details.update(resampling_details)
            if changed is None:
                return {"case": deepcopy(case), "status": "construction_failure", "reason": reason, "record": None, "details": details, "authentication_result": "not_attempted"}

        if attack not in ("timestamp_jitter", "dropped_samples"):
            orientations = _normalize_continuous(orientations)
            for index, row in enumerate(changed["samples"]):
                row["position_m"] = positions[index].tolist()
                row["orientation_xyzw"] = orientations[index].tolist()

    changed["window_id"] = case["case_id"]
    try:
        changed = canonical_motion_record(changed)
    except ValueError as error:
        return {"case": deepcopy(case), "status": "quality_failure", "reason": str(error), "record": None, "details": details, "authentication_result": "not_attempted"}

    # no tag is generated here and eligibility is not an authentication acceptance
    return {"case": deepcopy(case), "status": "quality_valid", "reason": "ready_for_legitimate_sender", "record": changed, "details": details, "authentication_result": "not_attempted"}
