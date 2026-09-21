""" 
this file creates synthetic Quest-like recordings for
- 6 simulated devices
- 3 sessions per device
- 20 trials per motion class
- 5 motion classes
- 120 samples per 2 second window

each window contains
- head position
- orientation quaternion
- timestamps
- tracking-valid values
- device, session, trial, and window IDs
- motion label
- train, validation, or test assignment

makes 6 * 3 * 20 * 5 = 1,800 clean windows * 120 samples = 216,000 samples in total

motion settings come from pilot.json device and session ids only group the data
this generator uses a fixed grid and does not model stable device/session motion effects

overall, this file creates the variable synthetic motion used by the conventional baseline
it keeps the existing schema and session split while removing the repeated orientation templates
the variation settings are engineering assumptions and are not calibrated human or Quest motion
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


NANOSECONDS_PER_SECOND = 1_000_000_000


@dataclass(frozen=True)
class GroupEffects:
    amplitude_scale: float
    duration_scale: float


def _require_range(config: dict[str, Any], name: str) -> tuple[float, float]:
    value = config.get(name)

    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{name} must contain [minimum, maximum]")

    minimum = float(value[0])
    maximum = float(value[1])

    if not math.isfinite(minimum) or not math.isfinite(maximum) or minimum > maximum:
        raise ValueError(f"{name} contains an invalid range")

    return minimum, maximum


def _uniform(rng: random.Random, bounds: tuple[float, float]) -> float:
    return rng.uniform(bounds[0], bounds[1])


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _normalize_quaternion(value: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    magnitude = math.sqrt(sum(component * component for component in value))

    if magnitude <= 1e-12:
        raise ValueError("cannot normalize a zero quaternion")

    return tuple(component / magnitude for component in value)


def _multiply_quaternions(first: tuple[float, float, float, float], second: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    first_x, first_y, first_z, first_w = first
    second_x, second_y, second_z, second_w = second

    return _normalize_quaternion(
        (
            first_w * second_x
            + first_x * second_w
            + first_y * second_z
            - first_z * second_y,
            first_w * second_y
            - first_x * second_z
            + first_y * second_w
            + first_z * second_x,
            first_w * second_z
            + first_x * second_y
            - first_y * second_x
            + first_z * second_w,
            first_w * second_w
            - first_x * second_x
            - first_y * second_y
            - first_z * second_z,
        )
    )


def _axis_quaternion(axis: str, angle_radians: float) -> tuple[float, float, float, float]:
    half_angle = angle_radians / 2.0
    sine = math.sin(half_angle)
    cosine = math.cos(half_angle)

    if axis == "x":
        return (sine, 0.0, 0.0, cosine)
    if axis == "y":
        return (0.0, sine, 0.0, cosine)
    if axis == "z":
        return (0.0, 0.0, sine, cosine)

    raise ValueError(f"unsupported rotation axis: {axis}")


def _euler_xyz_quaternion(x_deg: float, y_deg: float, z_deg: float) -> tuple[float, float, float, float]:
    x_rotation = _axis_quaternion("x", math.radians(x_deg))
    y_rotation = _axis_quaternion("y", math.radians(y_deg))
    z_rotation = _axis_quaternion("z", math.radians(z_deg))
    return _multiply_quaternions(z_rotation, _multiply_quaternions(y_rotation, x_rotation))


def _positive_normal_scale(rng: random.Random, standard_deviation: float) -> float:
    return _clamp(rng.gauss(1.0, standard_deviation), 0.75, 1.25)


def _make_group_effects(rng: random.Random, config: dict[str, Any]) -> GroupEffects:
    if not config.get("enabled", False):
        return GroupEffects(amplitude_scale=1.0, duration_scale=1.0)

    return GroupEffects(amplitude_scale=_positive_normal_scale(rng, float(config["amplitude_scale_std"])), duration_scale=_positive_normal_scale(rng, float(config["duration_scale_std"])))


def _warped_progress(progress: float, peak_fraction: float, phase_warp_rad: float) -> float:
    # this changes the timing without changing the start and end of the motion
    progress = _clamp(progress, 0.0, 1.0)

    if progress <= peak_fraction:
        adjusted = 0.5 * progress / peak_fraction
    else:
        adjusted = 0.5 + 0.5 * (progress - peak_fraction) / (1.0 - peak_fraction)

    phase_amount = phase_warp_rad / (2.0 * math.pi)
    adjusted += phase_amount * math.sin(math.pi * adjusted)
    return _clamp(adjusted, 0.0, 1.0)


def _motion_parameters(rng: random.Random, motion_config: dict[str, Any], device_effects: GroupEffects, session_effects: GroupEffects) -> dict[str, Any]:
    amplitude = _uniform(rng, _require_range(motion_config, "trial_amplitude_scale_range"))
    amplitude *= device_effects.amplitude_scale * session_effects.amplitude_scale

    duration = _uniform(rng, _require_range(motion_config, "motion_duration_s_range"))
    duration *= device_effects.duration_scale * session_effects.duration_scale

    start_delay = _uniform(rng, _require_range(motion_config, "start_delay_s_range"))
    duration = _clamp(duration, 0.75, 1.95 - start_delay)

    start_position_range = _require_range(motion_config, "start_position_m_range")
    start_orientation_range = _require_range(motion_config, "start_orientation_deg_range")

    return {
        "amplitude_scale": amplitude,
        "duration_s": duration,
        "start_delay_s": start_delay,
        "phase_warp_rad": _uniform(rng, _require_range(motion_config, "phase_warp_range_rad")),
        "peak_timing_fraction": _uniform(rng, _require_range(motion_config, "peak_timing_fraction_range")),
        "secondary_axis_scale": _uniform(rng, _require_range(motion_config, "secondary_axis_scale_range")),
        "return_error_deg": rng.gauss(0.0, float(motion_config["return_error_std_deg"])),
        "start_position_m": [_uniform(rng, start_position_range) for _ in range(3)],
        "start_orientation_deg": [_uniform(rng, start_orientation_range) for _ in range(3)],
        "position_drift_m": [rng.gauss(0.0, float(motion_config["position_drift_std_m"])) for _ in range(3)],
        "orientation_drift_deg": [rng.gauss(0.0, float(motion_config["orientation_drift_std_deg"])) for _ in range(3)],
        "position_sway_amplitude_m": _uniform(rng, _require_range(motion_config, "position_sway_amplitude_m_range")),
        "orientation_sway_amplitude_deg": _uniform(rng, _require_range(motion_config, "orientation_sway_amplitude_deg_range")),
        "sway_frequency_hz": rng.uniform(0.35, 0.80),
        "sway_phase_rad": rng.uniform(-math.pi, math.pi),
    }


def _intentional_angle_deg(label: str, time_value: float, class_config: dict[str, Any], parameters: dict[str, Any]) -> tuple[float, float]:
    start = float(parameters["start_delay_s"])
    duration = float(parameters["duration_s"])

    if time_value < start:
        return 0.0, 0.0

    raw_progress = (time_value - start) / duration
    progress = _clamp(raw_progress, 0.0, 1.0)
    warped = _warped_progress(progress, float(parameters["peak_timing_fraction"]), float(parameters["phase_warp_rad"]))

    if label in ("nod", "shake"):
        shape = math.sin(2.0 * math.pi * float(class_config["cycles_per_action"]) * warped)
        position_envelope = math.sin(math.pi * warped)
    elif label in ("look_left_return", "look_right_return"):
        shape = math.sin(math.pi * warped)
        position_envelope = shape
    else:
        return 0.0, 0.0

    return_progress = progress * progress * (3.0 - 2.0 * progress)
    angle = float(class_config["peak_rotation_deg"]) * float(parameters["amplitude_scale"]) * shape + float(parameters["return_error_deg"]) * return_progress

    if raw_progress > 1.0:
        angle = float(parameters["return_error_deg"])
        position_envelope = 0.0

    return angle, position_envelope


def _generate_motion(label: str, time_s: list[float], rng: random.Random, motion_config: dict[str, Any], device_effects: GroupEffects, session_effects: GroupEffects) -> tuple[list[list[float]], list[list[float]]]:
    class_config = motion_config["classes"][label]
    parameters = _motion_parameters(rng, motion_config, device_effects, session_effects)

    start_orientation = _euler_xyz_quaternion(*parameters["start_orientation_deg"])
    position_noise_std = float(motion_config["position_noise_std_m"])
    orientation_noise_std = float(motion_config["orientation_noise_std_deg"])
    duration = time_s[-1] if time_s[-1] > 0 else 1.0

    orientation_noise_state = [0.0, 0.0, 0.0]
    still_orientation_walk = [0.0, 0.0, 0.0]
    still_position_walk = [0.0, 0.0, 0.0]
    positions: list[list[float]] = []
    orientations: list[list[float]] = []

    for time_value in time_s:
        normalized_time = time_value / duration
        angle_deg, position_envelope = _intentional_angle_deg(label, time_value, class_config, parameters)

        sway_phase = 2.0 * math.pi * float(parameters["sway_frequency_hz"]) * time_value + float(parameters["sway_phase_rad"])

        position = [
            float(parameters["start_position_m"][axis])
            + float(parameters["position_drift_m"][axis]) * normalized_time
            + float(parameters["position_sway_amplitude_m"])
            * math.sin(sway_phase + axis * 2.0 * math.pi / 3.0)
            + rng.gauss(0.0, position_noise_std)
            for axis in range(3)
        ]

        if label == "nod":
            position[1] += float(class_config["vertical_position_peak_m"]) * float(parameters["amplitude_scale"]) * position_envelope
        elif label == "shake":
            motion_progress = (time_value - float(parameters["start_delay_s"])) / float(parameters["duration_s"])
            position[0] += float(class_config["horizontal_position_peak_m"]) * float(parameters["amplitude_scale"]) * math.sin(2.0 * math.pi * _clamp(motion_progress, 0.0, 1.0))

        if label == "still":
            for axis in range(3):
                still_orientation_walk[axis] += rng.gauss(0.0, float(class_config["orientation_random_walk_step_std_deg"]))
                still_position_walk[axis] += rng.gauss(0.0, float(class_config["position_random_walk_step_std_m"]))
                position[axis] += still_position_walk[axis]

        for axis in range(3):
            innovation = rng.gauss(0.0, orientation_noise_std)
            orientation_noise_state[axis] = 0.85 * orientation_noise_state[axis] + innovation

        delta_euler = [
            float(parameters["orientation_drift_deg"][axis]) * normalized_time
            + float(parameters["orientation_sway_amplitude_deg"])
            * math.sin(sway_phase + axis * 2.0 * math.pi / 3.0)
            + orientation_noise_state[axis]
            + still_orientation_walk[axis]
            for axis in range(3)
        ]

        main_axis = class_config["rotation_axis"]
        main_axis_index = {"x": 0, "y": 1, "z": 2}[main_axis]
        delta_euler[main_axis_index] += angle_deg

        for axis in range(3):
            if axis != main_axis_index:
                delta_euler[axis] += angle_deg * float(parameters["secondary_axis_scale"])

        delta_orientation = _euler_xyz_quaternion(*delta_euler)
        orientation = _multiply_quaternions(start_orientation, delta_orientation)

        positions.append(position)
        orientations.append(list(orientation))

    return positions, orientations


def _split_for_session(session_index: int, split_config: dict[str, Any]) -> str:
    mapping = {
        int(split_config["train_session_index"]): "train",
        int(split_config["validation_session_index"]): "validation",
        int(split_config["test_session_index"]): "test",
    }

    if session_index not in mapping:
        raise ValueError(f"no split is configured for session {session_index}")

    return mapping[session_index]


def _validate_config(config: dict[str, Any]) -> None:
    capture = config["capture"]
    motion = config["synthetic_motion"]

    if motion["generation_method"] != "variable_fixed_grid_v1":
        raise ValueError("the generator requires variable_fixed_grid_v1")
    if motion["resampling_applied"]:
        raise ValueError("the synthetic generator creates a fixed grid")
    if capture["samples_per_window"] != 120 or capture["target_sample_rate_hz"] != 60:
        raise ValueError("the current schema requires 120 samples at 60 Hz")
    if config["task"]["action_seconds"] != 2.0:
        raise ValueError("the current generator requires 2-second windows")
    if float(motion["tracking_valid_probability"]) != 1.0:
        raise ValueError("clean synthetic windows must retain fully valid tracking")

    required_ranges = (
        "trial_amplitude_scale_range",
        "motion_duration_s_range",
        "start_delay_s_range",
        "phase_warp_range_rad",
        "peak_timing_fraction_range",
        "secondary_axis_scale_range",
        "position_sway_amplitude_m_range",
        "orientation_sway_amplitude_deg_range",
        "start_position_m_range",
        "start_orientation_deg_range",
    )

    for field in required_ranges:
        _require_range(motion, field)


def generate_records(config: dict[str, Any]) -> list[dict[str, Any]]:
    # the same seed recreates the same data while every trial still gets its own variation
    _validate_config(config)
    rng = random.Random(int(config["project"]["random_seed"]))
    capture = config["capture"]
    motion = config["synthetic_motion"]
    synthetic = config["synthetic_data"]

    labels = list(config["task"]["labels"])
    sample_rate = int(capture["target_sample_rate_hz"])
    sample_count = int(capture["samples_per_window"])
    device_count = int(synthetic["device_profiles"])
    session_count = int(synthetic["sessions_per_device"])
    trials_per_class = int(synthetic["trials_per_class_per_session"])
    decimal_places = int(motion["round_decimal_places"])
    session_spacing_ns = round(float(motion["session_spacing_seconds"]) * NANOSECONDS_PER_SECOND)
    trial_period_seconds = float(config["task"]["prompt_seconds"]) + float(config["task"]["action_seconds"]) + float(config["task"]["rest_seconds"])
    trial_period_ns = round(trial_period_seconds * NANOSECONDS_PER_SECOND)
    interval_ns = round(NANOSECONDS_PER_SECOND / sample_rate)
    time_s = [index / sample_rate for index in range(sample_count)]

    device_profiles = {
        device_index: _make_group_effects(rng, motion["device_effects"])
        for device_index in range(1, device_count + 1)
    }

    records: list[dict[str, Any]] = []

    for device_index in range(1, device_count + 1):
        device_id = f"sim-device-{device_index:02d}"

        for session_index in range(1, session_count + 1):
            session_id = f"{device_id}-session-{session_index:02d}"
            split = _split_for_session(session_index, config["splits"])
            session_effects = _make_group_effects(rng, motion["session_effects"])
            session_number = (device_index - 1) * session_count + (session_index - 1)
            session_offset_ns = session_number * session_spacing_ns

            trial_specs = [
                (label, repetition)
                for label in labels
                for repetition in range(1, trials_per_class + 1)
            ]
            rng.shuffle(trial_specs)

            for sequence_number, (label, repetition) in enumerate(trial_specs):
                trial_id = f"{session_id}-{label}-{repetition:03d}"
                start_ns = session_offset_ns + (sequence_number + 1) * trial_period_ns
                position, orientation = _generate_motion(label, time_s, rng, motion, device_profiles[device_index], session_effects)

                samples = []
                for sample_index in range(sample_count):
                    samples.append(
                        {
                            "sample_index": sample_index,
                            "capture_time_ns": start_ns + sample_index * interval_ns,
                            "position_m": [
                                round(value, decimal_places)
                                for value in position[sample_index]
                            ],
                            "orientation_xyzw": [
                                round(value, decimal_places)
                                for value in orientation[sample_index]
                            ],
                            "tracking_valid": True,
                        }
                    )

                records.append(
                    {
                        "schema_version": "0.2",
                        "window_id": f"{trial_id}-window-000",
                        "source_trial_id": trial_id,
                        "device_id": device_id,
                        "session_id": session_id,
                        "trial_id": trial_id,
                        "split": split,
                        "sequence_number": sequence_number,
                        "label": label,
                        "coordinate_frame": capture["coordinate_frame"],
                        "target_sample_rate_hz": sample_rate,
                        "window_start_ns": start_ns,
                        "window_end_ns": start_ns + sample_count * interval_ns,
                        "samples": samples,
                    }
                )

    return records


def write_jsonl(records: Iterable[dict[str, Any]], output_path: Path) -> int:
    # jsonl stores one complete sensor window on each line
    output_path.parent.mkdir(parents=True, exist_ok=True)
    record_count = 0

    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, allow_nan=False) + "\n")
            record_count += 1

    return record_count
