"""Inspect the synthetic accepted-source candidate without changing any files.

Unity performs the authoritative processor replay. This independent checker
validates the candidate format, source timing/tracking metrics, output links and
resampling brackets; it does not implement Unity's quaternion interpolation.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import struct
from pathlib import Path

SCHEMA = "quest-accepted-source-candidate-v1"
HEADER = {"schema_version", "purpose", "planned_acquisition_mode", "time_basis", "coordinate_frame",
          "numeric_encoding", "outcome", "processing_version", "device_id", "session_id", "trial_id",
          "split", "label", "sequence_number", "samples"}
SAMPLE = {"capture_time_ns", "position_m_float32_bits", "orientation_xyzw_float32_bits", "tracking_valid",
          "tracking_state", "tracking_flag_available", "tracking_state_available"}
LABELS = {"nod", "shake", "look_left_return", "look_right_return", "still"}


class SourceCandidateError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise SourceCandidateError(message)


def load_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result
    def nonfinite(_):
        raise SourceCandidateError("nonfinite_json_number")
    try:
        return json.loads(data, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, SourceCandidateError):
            raise
        raise SourceCandidateError("malformed_json") from error


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def vector(bits, length):
    require(type(bits) is list and len(bits) == length, "invalid_float32_vector")
    require(all(integer(v, -(2**31), 2**31 - 1) for v in bits), "invalid_float32_bits")
    values = [struct.unpack("<f", struct.pack("<i", v))[0] for v in bits]
    require(all(math.isfinite(v) for v in values), "nonfinite_source_pose")
    return values


def float32(value):
    try:
        return struct.unpack("<f", struct.pack("<f", value))[0]
    except OverflowError:
        return math.copysign(math.inf, value)


def decode_source(record):
    require(type(record) is dict and set(record) == HEADER, "invalid_source_fields")
    require(type(record["schema_version"]) is str and type(record["purpose"]) is str and (record["schema_version"], record["purpose"]) in {
        (SCHEMA, "synthetic_development_only"), ("quest-accepted-source-v2", "development_only")}, "unsupported_source_policy_or_encoding")
    for key, value in {
                       "planned_acquisition_mode": "pc_hosted_quest_link", "time_basis": "head-capture-stopwatch-ns",
                       "coordinate_frame": "unity_device_origin", "numeric_encoding": "signed_int32_ieee754_float32_bits",
                       "outcome": "accepted"}.items():
        require(record[key] == value, "unsupported_source_policy_or_encoding")
    for key in ("processing_version", "device_id", "session_id", "trial_id"):
        require(isinstance(record[key], str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", record[key]), "invalid_source_identity")
    require(isinstance(record["split"], str) and record["split"] in {"train", "validation", "test"}, "invalid_split")
    require(isinstance(record["label"], str) and record["label"] in LABELS, "invalid_label")
    require(integer(record["sequence_number"], 0, 2**31 - 1), "invalid_sequence")
    require(type(record["samples"]) is list and 2 <= len(record["samples"]) <= 20000, "invalid_source_count")
    decoded = []
    for row in record["samples"]:
        require(type(row) is dict and set(row) == SAMPLE, "invalid_source_sample_fields")
        require(integer(row["capture_time_ns"], 0, 2**63 - 1 - 2_000_000_000), "invalid_source_timestamp")
        require(integer(row["tracking_state"], 0, 63), "invalid_tracking_state")
        require(all(type(row[k]) is bool for k in ("tracking_valid", "tracking_flag_available", "tracking_state_available")), "invalid_tracking_flag")
        p = vector(row["position_m_float32_bits"], 3)
        q = vector(row["orientation_xyzw_float32_bits"], 4)
        # Match the existing C# float32 norm boundary rather than using float64 arithmetic.
        norm = float32(q[0]*q[0])
        for value in q[1:]:
            norm = float32(norm + float32(value*value))
        require(norm >= float32(0.000001), "zero_source_orientation")
        decoded.append(dict(row, position=p, orientation=q))
    times = [r["capture_time_ns"] for r in decoded]
    gaps = [b-a for a, b in zip(times, times[1:])]
    require(all(0 < gap <= 50_000_000 for gap in gaps), "source_timestamp_order_or_gap")
    require(times[-1] >= times[0] + target_offset(119), "source_time_coverage")
    return decoded


def target_offset(index):
    # Positive integer equivalent of rounding index*1e9/60 away from zero.
    return (index * 1_000_000_000 + 30) // 60


def source_metrics(rows):
    gaps = sorted(b["capture_time_ns"]-a["capture_time_ns"] for a, b in zip(rows, rows[1:]))
    count = len(rows); duration = rows[-1]["capture_time_ns"]-rows[0]["capture_time_ns"]
    valid = sum(r["tracking_valid"] for r in rows)
    return dict(status="available", unavailable_reason="", source_sample_count=count,
                first_capture_ns=rows[0]["capture_time_ns"], last_capture_ns=rows[-1]["capture_time_ns"],
                source_duration_ns=duration, observed_rate_hz=(count-1)*1e9/duration,
                tracking_valid_count=valid, tracking_invalid_count=count-valid,
                tracking_flag_available_count=sum(r["tracking_flag_available"] for r in rows),
                tracking_state_available_count=sum(r["tracking_state_available"] for r in rows),
                positive_interval_count=count-1, nonpositive_interval_count=0, interval_overflow_count=0,
                negative_timestamp_count=0, gap_over_50ms_count=0, maximum_positive_gap_ns=max(gaps),
                median_positive_gap_ns=gaps[math.ceil(len(gaps)*.5)-1],
                p95_positive_gap_ns=gaps[math.ceil(len(gaps)*.95)-1], nonfinite_pose_count=0, zero_orientation_count=0)


def inspect_candidate(source_path, windows_path, metrics_path):
    result = dict(status="INVALID", scope="synthetic_source_candidate", live_collection_ready=False,
                  unity_quaternion_replay_checked=False, ledger_integration_checked=False, issues=[], hashes={})
    try:
        inputs = {}
        for name, value in (("source", source_path), ("windows", windows_path), ("metrics", metrics_path)):
            data = Path(value).read_bytes()
            require(0 < len(data) <= 16 * 1024 * 1024 and data.endswith(b"\n"), "missing_oversized_or_torn_file")
            result["hashes"][name] = hashlib.sha256(data).hexdigest()
            inputs[name] = data
        source = load_json(inputs["source"]); rows = decode_source(source)
        window_lines = inputs["windows"].splitlines()
        require(len(window_lines) == 1, "expected_one_matching_window")
        window = load_json(window_lines[0]); summary = load_json(inputs["metrics"])
        require(type(window) is dict, "invalid_window")
        for key in ("device_id", "session_id", "trial_id", "split", "label", "sequence_number", "coordinate_frame"):
            require(window.get(key) == source[key] and type(window.get(key)) is type(source[key]), "window_identity_mismatch")
        require(window.get("schema_version") == "0.2" and window.get("source_trial_id") == source["trial_id"] and
                window.get("window_id") == source["trial_id"] + "-window-000", "window_source_link_mismatch")
        start = rows[0]["capture_time_ns"]
        require(type(window.get("window_start_ns")) is int and type(window.get("window_end_ns")) is int
                and window["window_start_ns"] == start and window["window_end_ns"] == start + 2_000_000_000
                and type(window.get("target_sample_rate_hz")) is int and window["target_sample_rate_hz"] == 60, "window_time_mismatch")
        samples = window.get("samples")
        require(type(samples) is list and len(samples) == 120, "invalid_window_sample_count")
        upper = 1; valid = 0
        for index, sample in enumerate(samples):
            require(type(sample) is dict and type(sample.get("sample_index")) is int and sample["sample_index"] == index,
                    "window_sample_order_mismatch")
            target = start + target_offset(index)
            require(type(sample.get("capture_time_ns")) is int and sample["capture_time_ns"] == target, "window_grid_mismatch")
            while upper < len(rows)-1 and rows[upper]["capture_time_ns"] < target:
                upper += 1
            expected = rows[upper-1]["tracking_valid"] and rows[upper]["tracking_valid"]
            require(type(sample.get("tracking_valid")) is bool and sample["tracking_valid"] == expected, "resampled_tracking_mismatch")
            valid += expected
            for key, length in (("position_m", 3), ("orientation_xyzw", 4)):
                values = sample.get(key)
                require(type(values) is list and len(values) == length and all(type(v) in (int, float) and math.isfinite(v) for v in values), "invalid_window_pose")
        require(valid >= 114, "resampled_tracking_refusal")
        expected_metrics = source_metrics(rows)
        require(type(summary) is dict and set(summary) == set(expected_metrics), "invalid_summary_fields")
        for key, expected in expected_metrics.items():
            actual = summary[key]
            if key == "observed_rate_hz":
                require(type(actual) in (int, float) and math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-12), "source_metric_mismatch")
            else:
                require(type(actual) is type(expected) and actual == expected, "source_metric_mismatch")
        result.update(status="COMPLETE", source_samples=len(rows), processed_samples=120,
                      source_metrics_match=True, resampling_grid_and_tracking_match=True)
    except (OSError, SourceCandidateError, TypeError, ValueError, OverflowError) as error:
        result["issues"].append(str(error) if isinstance(error, SourceCandidateError) else "unreadable_or_invalid_input")
    return result
