"""
this file checks the data format and catches common leakage mistakes, it prevents bad data from reaching our models. It checks
- full schema field types and permitted values
- finite position and quaternion values
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
- configured device, session, trial, label, and group-count relationships

these are data-quality checks, not cryptographic authentication or proof of physical realism
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator


def make_schema_validator(
    schema: dict[str, Any],
) -> Draft202012Validator:
    # this validates the schema once before checking the dataset
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _schema_errors(
    record: dict[str, Any],
    schema: dict[str, Any],
    validator: Draft202012Validator | None = None,
) -> list[str]:
    # this adds full type and range checks before the existing detailed checks
    if validator is None:
        validator = make_schema_validator(schema)

    schema_errors = [
        f"schema error at {list(error.absolute_path)}: {error.message}"
        for error in validator.iter_errors(record)
    ]

    if schema_errors:
        return schema_errors

    # json permits finite numbers only, but python can load nan and infinity
    for sample in record["samples"]:
        values = sample["position_m"] + sample["orientation_xyzw"]
        if any(isinstance(value, float) and not math.isfinite(value) for value in values):
            return [f"{record['window_id']}: position and quaternion values must be finite"]

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
    quaternion_tolerance: float = 1e-4,
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
        abs(norm - 1.0) > quaternion_tolerance
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

    # every sample must lie inside the declared window
    if any(time < window_start_ns or time >= window_end_ns for time in timestamps):
        errors.append(f"{window_id}: sample time lies outside the window bounds")

    # allow the original fixed-grid timestamp rounding, but not a wrong duration
    expected_duration_ns = round(
        len(samples) * 1_000_000_000 / record["target_sample_rate_hz"]
    )
    if abs((window_end_ns - window_start_ns) - expected_duration_ns) > len(samples):
        errors.append(f"{window_id}: window duration does not match the nominal sample count and rate")

    return errors


def validate_record(
    record: Any,
    validator: Draft202012Validator,
    maximum_gap_ms: float = 50.0,
    minimum_tracking: float = 0.95,
    quaternion_tolerance: float = 1e-4,
) -> list[str]:
    # the analysis script uses this to count individual data-quality rejections
    errors = _schema_errors(record, validator.schema, validator)
    if errors:
        return errors

    return _record_errors(record, maximum_gap_ms, minimum_tracking, quaternion_tolerance)


def _synthetic_identifier_errors(
    record: dict[str, Any],
    config: dict[str, Any],
) -> list[str]:
    # apply the synthetic naming rules only when the caller supplies the pilot config
    errors = []
    window_id = record["window_id"]
    device_ids = {
        f"sim-device-{index:02d}"
        for index in range(1, int(config["synthetic_data"]["device_profiles"]) + 1)
    }

    if record["device_id"] not in device_ids:
        errors.append(f"{window_id}: device_id is not a configured synthetic device")

    split_by_session = {
        int(config["splits"]["train_session_index"]): "train",
        int(config["splits"]["validation_session_index"]): "validation",
        int(config["splits"]["test_session_index"]): "test",
    }
    session_prefix = re.escape(record["device_id"]) + r"-session-(\d{2})"
    session_match = re.fullmatch(session_prefix, record["session_id"])

    if session_match is None:
        errors.append(f"{window_id}: session_id does not match its device_id")
    else:
        session_index = int(session_match.group(1))
        if session_index not in split_by_session:
            errors.append(f"{window_id}: session_id has an unconfigured session index")
        elif record["split"] != split_by_session[session_index]:
            errors.append(f"{window_id}: split does not match the configured session assignment")

    trial_prefix = re.escape(record["session_id"] + "-" + record["label"] + "-")
    trial_match = re.fullmatch(trial_prefix + r"(\d{3,})", record["trial_id"])
    maximum_trial = int(config["synthetic_data"]["trials_per_class_per_session"])

    if trial_match is None or not 1 <= int(trial_match.group(1)) <= maximum_trial:
        errors.append(f"{window_id}: trial_id does not match its label, session, or repetition range")

    if record["source_trial_id"] != record["trial_id"]:
        errors.append(f"{window_id}: clean synthetic source_trial_id must equal trial_id")

    if record["window_id"] != record["trial_id"] + "-window-000":
        errors.append(f"{window_id}: window_id does not match its clean synthetic trial")

    return errors


def validate_dataset(
    records: Iterable[dict[str, Any]],
    schema: dict[str, Any],
    maximum_gap_ms: float = 50.0,
    minimum_tracking: float = 0.95,
    *,
    config: dict[str, Any] | None = None,
    quaternion_tolerance: float = 1e-4,
) -> list[str]:
    # this converts the input so it can be checked more than once
    records = list(records)
    errors: list[str] = []

    if not records:
        return ["dataset is empty"]

    validator = make_schema_validator(schema)

    # these collections help catch problems across multiple windows
    session_splits: dict[str, set[str]] = defaultdict(set)
    trial_splits: dict[str, set[str]] = defaultdict(set)
    session_sequences: dict[str, list[int]] = defaultdict(list)
    observed_window_ids: set[str] = set()
    actual_trial_splits: dict[str, set[str]] = defaultdict(set)
    session_devices: dict[str, set[str]] = defaultdict(set)
    group_counts = Counter()
    source_ids: set[str] = set()

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
            validator,
        )

        errors.extend(schema_errors)

        if schema_errors:
            continue

        # malformed records are skipped so later checks do not crash
        if not schema_errors:
            errors.extend(
                _record_errors(
                    record,
                    maximum_gap_ms,
                    minimum_tracking,
                    quaternion_tolerance,
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

        actual_trial_splits[record["trial_id"]].add(split)
        session_devices[session_id].add(record["device_id"])
        group_counts[(record["device_id"], session_id, record["label"])] += 1
        source_ids.add(source_trial_id)

        if config is not None:
            errors.extend(_synthetic_identifier_errors(record, config))

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

    # actual trial ids also cannot be reused in another split
    for trial_id, splits in actual_trial_splits.items():
        if len(splits) != 1:
            errors.append(f"{trial_id}: trial occurs in multiple splits: {sorted(splits)}")

    for session_id, devices in session_devices.items():
        if len(devices) != 1:
            errors.append(f"{session_id}: session belongs to more than one device")

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

    if config is not None:
        # validate every expected group, including a group missing from the file entirely
        device_count = int(config["synthetic_data"]["device_profiles"])
        session_count = int(config["synthetic_data"]["sessions_per_device"])
        trial_count = int(config["synthetic_data"]["trials_per_class_per_session"])
        expected_count = device_count * session_count * trial_count * len(config["task"]["labels"])

        if len(records) != expected_count:
            errors.append(f"dataset count is {len(records)}; expected {expected_count}")

        if len(source_ids) != expected_count:
            errors.append("clean synthetic dataset does not have one unique source trial per expected window")

        for device_index in range(1, device_count + 1):
            device_id = f"sim-device-{device_index:02d}"
            for session_index in range(1, session_count + 1):
                session_id = f"{device_id}-session-{session_index:02d}"
                for label in config["task"]["labels"]:
                    count = group_counts[(device_id, session_id, label)]
                    if count != trial_count:
                        errors.append(f"{session_id}/{label}: {count} windows; expected {trial_count}")


    return errors


def validate_jsonl(
    data_path: Path,
    schema_path: Path,
    maximum_gap_ms: float = 50.0,
    minimum_tracking: float = 0.95,
    *,
    config: dict[str, Any] | None = None,
    quaternion_tolerance: float = 1e-4,
) -> tuple[list[dict[str, Any]], list[str]]:
    # this loads the json schema used by the project
    with schema_path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        schema = json.load(handle)

    # this loads one complete sensor window from each jsonl line
    records = []
    parse_errors = []

    with data_path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                parse_errors.append(f"line {line_number}: invalid json: {error.msg}")

    # this returns all errors together instead of stopping at the first
    errors = validate_dataset(
        records,
        schema,
        maximum_gap_ms,
        minimum_tracking,
        config=config,
        quaternion_tolerance=quaternion_tolerance,
    )

    return records, parse_errors + errors
