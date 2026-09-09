"""
this file checks the data format and catches common leakage mistakes, it prevents bad data from reaching our models. It checks
- 120 samples per window
- consecutive sample indexes
- strictly increasing timestamps
- no timestamp gap over 50 ms
- normalized quaternions
- quaternion sign continuity
- at least 95% valid tracking
- unique window IDs
- correct sequence-number order
- one split per session
- no source trial leaking between splits
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


def _schema_errors(
    record: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    # this checks the required and allowed window fields
    window_id = record.get(
        "window_id",
        "<missing-window-id>",
    )

    errors: list[str] = []

    required_fields = set(schema["required"])
    allowed_fields = set(schema["properties"])
    record_fields = set(record)

    missing_fields = sorted(
        required_fields - record_fields
    )

    extra_fields = sorted(
        record_fields - allowed_fields
    )

    if missing_fields:
        errors.append(
            f"{window_id}: missing required fields: "
            f"{missing_fields}"
        )

    if extra_fields:
        errors.append(
            f"{window_id}: unexpected fields: "
            f"{extra_fields}"
        )

    # this checks fixed values and approved choices
    for field, rule in schema["properties"].items():
        has_wrong_constant = (
            field in record
            and "const" in rule
            and record[field] != rule["const"]
        )

        has_unsupported_value = (
            field in record
            and "enum" in rule
            and record[field] not in rule["enum"]
        )

        if has_wrong_constant:
            expected_value = rule["const"]

            errors.append(
                f"{window_id}: {field} must equal "
                f"{expected_value!r}"
            )

        if has_unsupported_value:
            errors.append(
                f"{window_id}: unsupported {field}: "
                f"{record[field]!r}"
            )

    samples = record.get("samples")

    # later checks cannot continue if samples is not a list
    if not isinstance(samples, list):
        errors.append(
            f"{window_id}: samples must be a list"
        )

        return errors

    sample_rule = schema["$defs"]["sample"]
    required_sample_fields = set(
        sample_rule["required"]
    )
    allowed_sample_fields = set(
        sample_rule["properties"]
    )

    expected_sample_count = int(
        schema["properties"]["samples"]["minItems"]
    )

    if len(samples) != expected_sample_count:
        errors.append(
            f"{window_id}: samples must contain exactly "
            f"{expected_sample_count} items"
        )

    # this checks the structure of every sample
    for sample_index, sample in enumerate(samples):
        if not isinstance(sample, dict):
            errors.append(
                f"{window_id}: sample {sample_index} "
                f"must be an object"
            )

            continue

        sample_fields = set(sample)

        missing_sample_fields = (
            required_sample_fields - sample_fields
        )

        extra_sample_fields = (
            sample_fields - allowed_sample_fields
        )

        if missing_sample_fields:
            errors.append(
                f"{window_id}: sample {sample_index} "
                f"is missing required fields"
            )

        if extra_sample_fields:
            errors.append(
                f"{window_id}: sample {sample_index} "
                f"has unexpected fields"
            )

        position = sample.get("position_m")
        orientation = sample.get("orientation_xyzw")

        if not isinstance(position, list) or len(position) != 3:
            errors.append(
                f"{window_id}: sample {sample_index} "
                f"position must have 3 values"
            )

        if (
            not isinstance(orientation, list)
            or len(orientation) != 4
        ):
            errors.append(
                f"{window_id}: sample {sample_index} "
                f"orientation must have 4 values"
            )

    return errors


def _record_errors(
    record: dict[str, Any],
    maximum_gap_ms: float,
    minimum_tracking: float,
) -> list[str]:
    # this checks the contents of one complete sensor window
    window_id = record.get(
        "window_id",
        "<missing-window-id>",
    )

    errors: list[str] = []
    samples = record.get("samples", [])

    if not samples:
        return [f"{window_id}: samples are missing"]

    # sample indexes should be 0, 1, 2, and so on
    observed_indices = [
        sample.get("sample_index")
        for sample in samples
    ]

    expected_indices = list(
        range(len(samples))
    )

    if observed_indices != expected_indices:
        errors.append(
            f"{window_id}: sample indices are not "
            f"consecutive from zero"
        )

    # timestamps must always move forward
    timestamps = [
        int(sample.get("capture_time_ns", 0))
        for sample in samples
    ]

    gaps_ms = [
        (right - left) / 1_000_000.0
        for left, right in zip(
            timestamps,
            timestamps[1:],
        )
    ]

    if any(gap <= 0 for gap in gaps_ms):
        errors.append(
            f"{window_id}: capture timestamps are not "
            f"strictly increasing"
        )

    if gaps_ms and max(gaps_ms) > maximum_gap_ms:
        errors.append(
            f"{window_id}: timestamp gap exceeds "
            f"{maximum_gap_ms:g} ms"
        )

    # every valid quaternion should have a length near one
    quaternions = [
        sample.get(
            "orientation_xyzw",
            [0.0, 0.0, 0.0, 0.0],
        )
        for sample in samples
    ]

    quaternion_norms = [
        math.sqrt(
            sum(
                float(value) ** 2
                for value in quaternion
            )
        )
        for quaternion in quaternions
    ]

    has_bad_quaternion = any(
        abs(norm - 1.0) > 1e-4
        for norm in quaternion_norms
    )

    if has_bad_quaternion:
        errors.append(
            f"{window_id}: at least one quaternion "
            f"is not unit normalized"
        )

    # equivalent quaternions should keep the same sign over time
    sign_flips = [
        sum(
            left_value * right_value
            for left_value, right_value in zip(
                left,
                right,
            )
        ) < 0
        for left, right in zip(
            quaternions,
            quaternions[1:],
        )
    ]

    if any(sign_flips):
        errors.append(
            f"{window_id}: quaternion sign continuity "
            f"was not enforced"
        )

    # enough samples must have valid headset tracking
    valid_sample_count = sum(
        bool(sample.get("tracking_valid"))
        for sample in samples
    )

    tracking_fraction = (
        valid_sample_count / len(samples)
    )

    if tracking_fraction < minimum_tracking:
        errors.append(
            f"{window_id}: tracking-valid fraction "
            f"is below {minimum_tracking:.0%}"
        )

    # the saved window must have a positive duration
    window_start_ns = record.get(
        "window_start_ns",
        0,
    )

    window_end_ns = record.get(
        "window_end_ns",
        0,
    )

    if window_end_ns <= window_start_ns:
        errors.append(
            f"{window_id}: window end must be "
            f"after window start"
        )

    return errors


def validate_dataset(
    records: Iterable[dict[str, Any]],
    schema: dict[str, Any],
    maximum_gap_ms: float = 50.0,
    minimum_tracking: float = 0.95,
) -> list[str]:
    # this converts the input so it can be checked more than once
    records = list(records)
    errors: list[str] = []

    # these collections help catch problems across multiple windows
    session_splits: dict[str, set[str]] = defaultdict(set)
    trial_splits: dict[str, set[str]] = defaultdict(set)
    session_sequences: dict[str, list[int]] = defaultdict(list)
    observed_window_ids: set[str] = set()

    for record_number, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(
                f"record {record_number}: record must be an object"
            )

            continue

        window_id = record.get(
            "window_id",
            "<missing-window-id>",
        )

        # basic structure is checked before numerical rules
        schema_errors = _schema_errors(
            record,
            schema,
        )

        errors.extend(schema_errors)

        # malformed records are skipped so later checks do not crash
        if not schema_errors:
            errors.extend(
                _record_errors(
                    record,
                    maximum_gap_ms,
                    minimum_tracking,
                )
            )

        # every window needs its own id
        if window_id in observed_window_ids:
            errors.append(
                f"{window_id}: duplicate window ID"
            )

        observed_window_ids.add(window_id)

        session_id = record.get("session_id", "")
        source_trial_id = record.get(
            "source_trial_id",
            "",
        )
        split = record.get("split", "")
        sequence_number = record.get(
            "sequence_number",
            -1,
        )

        session_splits[session_id].add(split)
        trial_splits[source_trial_id].add(split)
        session_sequences[session_id].append(
            sequence_number
        )

    # one session cannot appear in multiple dataset splits
    for session_id, splits in session_splits.items():
        if len(splits) != 1:
            errors.append(
                f"{session_id}: session occurs in "
                f"multiple splits: {sorted(splits)}"
            )

    # copies of one source trial must stay in one split
    for source_trial_id, splits in trial_splits.items():
        if len(splits) != 1:
            errors.append(
                f"{source_trial_id}: source trial leaks "
                f"across splits: {sorted(splits)}"
            )

    # sequence numbers should start at zero and increase by one
    for session_id, sequence_numbers in session_sequences.items():
        expected_numbers = list(
            range(len(sequence_numbers))
        )

        if sequence_numbers != expected_numbers:
            errors.append(
                f"{session_id}: sequence numbers are "
                f"not consecutive from zero"
            )

    return errors


def validate_jsonl(
    data_path: Path,
    schema_path: Path,
    maximum_gap_ms: float = 50.0,
    minimum_tracking: float = 0.95,
) -> tuple[list[dict[str, Any]], list[str]]:
    # this loads the json schema used by the project
    with schema_path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        schema = json.load(handle)

    # this loads one complete sensor window from each jsonl line
    with data_path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        records = [
            json.loads(line)
            for line in handle
            if line.strip()
        ]

    # this returns all errors together instead of stopping at the first
    errors = validate_dataset(
        records,
        schema,
        maximum_gap_ms,
        minimum_tracking,
    )

    return records, errors