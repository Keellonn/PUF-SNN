"""
this file describes a window using only its relative pose and sample timestamps
attack settings, labels, tracking flags and authentication decisions are not model features
"""

from __future__ import annotations

import numpy as np

from puf_snn.motion_diagnostics import angular_velocity, rotation_vectors
from puf_snn.snn.dataset import record_to_sequence


STATISTICS = ("mean", "standard_deviation", "p95", "maximum", "rms")
SERIES = ("position_displacement_m", "linear_speed_m_s", "linear_acceleration_m_s2", "orientation_displacement_deg", "angular_speed_deg_s", "angular_acceleration_deg_s2")
FEATURE_NAMES = tuple(f"{series}_{statistic}" for series in SERIES for statistic in STATISTICS) + tuple(f"{kind}_{axis}_{statistic}" for kind in ("relative_position_m", "relative_rotation_vector_deg") for axis in ("x", "y", "z") for statistic in ("standard_deviation", "range")) + ("end_position_displacement_m", "end_orientation_displacement_deg", "repeated_position_step_fraction", "longest_repeated_position_run_s", "repeated_orientation_step_fraction", "longest_repeated_orientation_run_s")


def _statistics(values: np.ndarray) -> list[float]:
    return [float(values.mean()), float(values.std()), float(np.percentile(values, 95)), float(values.max()), float(np.sqrt(np.mean(values * values)))]


def _repeat_features(repeated: np.ndarray, intervals: np.ndarray) -> list[float]:
    longest = 0.0
    current = 0.0
    for is_repeated, interval in zip(repeated, intervals):
        if is_repeated:
            current += float(interval)
            longest = max(longest, current)
        else:
            current = 0.0
    return [float(repeated.mean()), longest]


def record_to_anomaly_features(record: dict) -> np.ndarray:
    sequence = record_to_sequence(record)
    captures = [sample.get("capture_time_ns") for sample in record["samples"]]
    if any(type(value) is not int for value in captures):
        raise ValueError("sample timestamps must be integers")

    # subtract the integer origin before converting to seconds so large clocks retain their precision
    times = np.asarray([(value - captures[0]) / 1_000_000_000.0 for value in captures], dtype=np.float64)
    intervals = np.diff(times)
    if np.any(intervals <= 0.0) or np.any(intervals > 0.05 + 1e-12):
        raise ValueError("anomaly features require increasing timestamps with gaps no greater than 50 ms")

    positions = sequence[:, :3]
    rotations = np.rad2deg(rotation_vectors(sequence[:, 3:7]))
    velocity = np.diff(positions, axis=0) / intervals[:, None]
    midpoint_intervals = (intervals[:-1] + intervals[1:]) / 2.0
    acceleration = np.diff(velocity, axis=0) / midpoint_intervals[:, None]
    angular = np.rad2deg(angular_velocity(sequence, times)[1:])
    angular_acceleration = np.diff(angular, axis=0) / midpoint_intervals[:, None]
    measured_series = (np.linalg.norm(positions, axis=1), np.linalg.norm(velocity, axis=1), np.linalg.norm(acceleration, axis=1), np.linalg.norm(rotations, axis=1), np.linalg.norm(angular, axis=1), np.linalg.norm(angular_acceleration, axis=1))

    values = []
    for measured in measured_series:
        values.extend(_statistics(measured))
    for channels in (positions, rotations):
        for channel in channels.T:
            values.extend([float(channel.std()), float(np.ptp(channel))])
    values.extend([float(np.linalg.norm(positions[-1])), float(np.linalg.norm(rotations[-1]))])
    values.extend(_repeat_features(np.all(np.diff(positions, axis=0) == 0.0, axis=1), intervals))
    values.extend(_repeat_features(np.linalg.norm(angular, axis=1) <= 1e-10, intervals))
    result = np.asarray(values, dtype=np.float64)
    if result.shape != (len(FEATURE_NAMES),) or not np.all(np.isfinite(result)):
        raise ValueError("anomaly features must contain 48 finite measurements")
    return result
