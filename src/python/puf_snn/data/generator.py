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
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any, Iterable


NANOSECONDS_PER_SECOND = 1_000_000_000


def _check_motion_config(
    config: dict[str, Any],
) -> None:
    # this prevents the settings from claiming effects the generator does not apply
    motion = config["synthetic_motion"]
    capture = config["capture"]

    if capture["samples_per_window"] != 120 or capture["target_sample_rate_hz"] != 60:
        raise ValueError("the current schema requires 120 samples at 60 hz")

    if capture["source"] != "synthetic" or config["task"]["action_seconds"] != 2.0:
        raise ValueError("this generator requires synthetic 2 second windows")

    if motion["generation_method"] != "direct_fixed_grid" or motion["resampling_applied"]:
        raise ValueError("this generator creates a fixed grid and does not resample")

    if motion["device_effects"]["enabled"] or motion["session_effects"]["enabled"]:
        raise ValueError("stable device and session effects have not been implemented")

    fixed_settings = {
        "trial_amplitude_scale_range": [1.0, 1.0],
        "frequency_scale_range": [1.0, 1.0],
        "phase_offset_range_rad": [0.0, 0.0],
    }

    for field, expected in fixed_settings.items():
        if motion[field] != expected:
            raise ValueError(f"{field} is fixed; randomization is not implemented")

    if motion["tracking_valid_probability"] != 1.0:
        raise ValueError("the clean generator currently marks every sample as tracked")

    for label in ("look_left_return", "look_right_return"):
        if motion["classes"][label]["trajectory"] != "half_sine_return":
            raise ValueError("look-and-return classes currently use a half sine trajectory")


def _axis_quaternion(
    axis: str,
    angle_radians: list[float],
) -> list[list[float]]:
    # this converts rotation angles into xyzw quaternions
    axis_index = {
        "x": 0,
        "y": 1,
        "z": 2,
    }[axis]

    quaternions: list[list[float]] = []

    for angle in angle_radians:
        # sine stores the rotation on the selected axis
        half_angle_sine = math.sin(angle / 2.0)
        half_angle_cosine = math.cos(angle / 2.0)

        quaternion = [
            0.0,
            0.0,
            0.0,
            half_angle_cosine,
        ]

        quaternion[axis_index] = half_angle_sine
        quaternions.append(quaternion)

    return quaternions


def _motion(
    label: str,
    time_s: list[float],
    rng: random.Random,
    motion_config: dict[str, Any],
) -> tuple[list[list[float]], list[list[float]]]:
    # this reads the documented settings for the current motion class
    class_config = motion_config["classes"][label]

    # this starts every window with a small amount of position noise
    position = [
        [
            rng.gauss(0.0, motion_config["position_noise_std_m"])
            for _ in range(3)
        ]
        for _ in time_s
    ]

    # this curve starts at zero, reaches a peak, and returns to zero
    return_envelope = [
        math.sin(math.pi * value / time_s[-1])
        for value in time_s
    ]

    if label == "nod":
        # a nod mainly rotates around the headset's x axis
        angles = [
            math.radians(class_config["peak_rotation_deg"])
            * math.sin(2.0 * math.pi * class_config["cycles_per_window"] * value / time_s[-1])
            for value in time_s
        ]

        orientation = _axis_quaternion(class_config["rotation_axis"], angles)

        # this adds a small vertical movement during the nod
        for index, envelope in enumerate(return_envelope):
            position[index][1] += class_config["vertical_position_peak_m"] * envelope

    elif label == "shake":
        # a head shake mainly rotates around the y axis
        angles = [
            math.radians(class_config["peak_rotation_deg"])
            * math.sin(2.0 * math.pi * class_config["cycles_per_window"] * value / time_s[-1])
            for value in time_s
        ]

        orientation = _axis_quaternion(class_config["rotation_axis"], angles)

        # this adds a small side to side position change
        for index, value in enumerate(time_s):
            position[index][0] += class_config["horizontal_position_peak_m"] * math.sin(
                2.0 * math.pi * class_config["cycles_per_window"] * value / time_s[-1]
            )

    elif label == "look_left_return":
        # this turns left and then returns to the starting direction
        angles = [
            math.radians(class_config["peak_rotation_deg"]) * value
            for value in return_envelope
        ]

        orientation = _axis_quaternion(class_config["rotation_axis"], angles)

    elif label == "look_right_return":
        # this turns right and then returns to the starting direction
        angles = [
            math.radians(class_config["peak_rotation_deg"]) * value
            for value in return_envelope
        ]

        orientation = _axis_quaternion(class_config["rotation_axis"], angles)

    elif label == "still":
        # still includes a tiny amount of scripted drift
        angles: list[float] = []
        accumulated_angle = 0.0

        for _ in time_s:
            accumulated_angle += rng.gauss(
                0.0,
                math.radians(class_config["orientation_random_walk_step_std_deg"]),
            )

            angles.append(accumulated_angle)

        orientation = _axis_quaternion(class_config["rotation_axis"], angles)

    else:
        raise ValueError(f"unsupported label: {label}")

    return position, orientation


def _split_for_session(
    session_index: int,
    split_config: dict[str, Any],
) -> str:
    # this keeps each complete session inside one dataset split
    session_mapping = {
        int(split_config["train_session_index"]): "train",
        int(split_config["validation_session_index"]): "validation",
        int(split_config["test_session_index"]): "test",
    }

    try:
        return session_mapping[session_index]

    except KeyError as error:
        message = f"no split is configured for session {session_index}"
        raise ValueError(message) from error


def generate_records(
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    # this checks the supported settings before creating any records
    _check_motion_config(config)

    # this reads the fixed experiment settings from the config
    seed = int(config["project"]["random_seed"])
    rng = random.Random(seed)

    labels = list(config["task"]["labels"])
    sample_rate = int(
        config["capture"]["target_sample_rate_hz"]
    )
    sample_count = int(
        config["capture"]["samples_per_window"]
    )

    device_count = int(
        config["synthetic_data"]["device_profiles"]
    )
    session_count = int(
        config["synthetic_data"]["sessions_per_device"]
    )
    trials_per_class = int(
        config["synthetic_data"]["trials_per_class_per_session"]
    )

    # these settings were previously constants inside this file
    motion_config = config["synthetic_motion"]
    decimal_places = int(motion_config["round_decimal_places"])
    session_spacing_ns = round(
        motion_config["session_spacing_seconds"] * NANOSECONDS_PER_SECOND
    )
    trial_period_ns = round(
        (
            config["task"]["prompt_seconds"]
            + config["task"]["action_seconds"]
            + config["task"]["rest_seconds"]
        ) * NANOSECONDS_PER_SECOND
    )

    # these are the sample times inside one window
    time_s = [
        sample_index / sample_rate
        for sample_index in range(sample_count)
    ]

    # the timestamps in the saved data use nanoseconds
    interval_ns = round(
        NANOSECONDS_PER_SECOND / sample_rate
    )

    records: list[dict[str, Any]] = []

    # this loop creates each simulated device
    for device_index in range(1, device_count + 1):
        device_id = f"sim-device-{device_index:02d}"

        # this loop creates the three sessions for each device
        for session_index in range(1, session_count + 1):
            session_id = (
                f"{device_id}-session-{session_index:02d}"
            )

            split = _split_for_session(
                session_index,
                config["splits"],
            )

            sequence_number = 0

            # this keeps timestamps from separate sessions apart
            session_number = (
                (device_index - 1) * session_count
                + (session_index - 1)
            )

            session_offset_ns = (
                session_number
                * session_spacing_ns
            )

            # this makes the requested number of trials for every label
            trial_specs = [
                (label, repetition)
                for label in labels
                for repetition in range(
                    1,
                    trials_per_class + 1,
                )
            ]

            # this randomizes trial order while keeping the run repeatable
            rng.shuffle(trial_specs)

            for trial_order, trial_spec in enumerate(
                trial_specs,
                start=1,
            ):
                label, repetition = trial_spec

                trial_id = (
                    f"{session_id}-{label}-{repetition:03d}"
                )

                source_trial_id = trial_id
                window_id = f"{trial_id}-window-000"

                # each trial follows the configured prompt, action, and rest period
                start_ns = (
                    session_offset_ns
                    + trial_order
                    * trial_period_ns
                )

                # this creates the motion pattern for the current label
                position, orientation = _motion(
                    label,
                    time_s,
                    rng,
                    motion_config,
                )

                samples: list[dict[str, Any]] = []

                # this packages every sample inside the window
                for sample_index in range(sample_count):
                    sample_position = [
                        round(value, decimal_places)
                        for value in position[sample_index]
                    ]

                    sample_orientation = [
                        round(value, decimal_places)
                        for value in orientation[sample_index]
                    ]

                    capture_time_ns = (
                        start_ns
                        + sample_index * interval_ns
                    )

                    samples.append(
                        {
                            "sample_index": sample_index,
                            "capture_time_ns": capture_time_ns,
                            "position_m": sample_position,
                            "orientation_xyzw": sample_orientation,
                            "tracking_valid": True,
                        }
                    )

                # this creates the final 2 second window record
                records.append(
                    {
                        "schema_version": "0.2",
                        "window_id": window_id,
                        "source_trial_id": source_trial_id,
                        "device_id": device_id,
                        "session_id": session_id,
                        "trial_id": trial_id,
                        "split": split,
                        "sequence_number": sequence_number,
                        "label": label,
                        "coordinate_frame": config[
                            "capture"
                        ]["coordinate_frame"],
                        "target_sample_rate_hz": sample_rate,
                        "window_start_ns": start_ns,
                        "window_end_ns": (
                            start_ns
                            + sample_count * interval_ns
                        ),
                        "samples": samples,
                    }
                )

                # this increases once for each new window in the session
                sequence_number += 1

    return records


def write_jsonl(
    records: Iterable[dict[str, Any]],
    output_path: Path,
) -> int:
    # this creates the output folder if it does not exist
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    record_count = 0

    # jsonl stores one complete sensor window on each line
    with output_path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as handle:
        for record in records:
            serialized_record = json.dumps(record, allow_nan=False)
            handle.write(serialized_record + "\n")
            record_count += 1

    return record_count