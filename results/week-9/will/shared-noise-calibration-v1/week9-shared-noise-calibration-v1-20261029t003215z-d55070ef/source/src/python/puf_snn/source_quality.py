"""Read-only reconciliation of source diagnostics with the existing trial ledger.

Metrics describe source samples before interpolation, not resampled tracking or
model behavior. A valid summary is not proof of physical capture or authenticity.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from .trial_ledger import inspect_ledger

HEADER = {"record_type", "schema_version", "participant_code", "visit_code", "device_id", "session_id",
          "processing_version", "ledger_file_name", "time_basis", "interval_quantile_method", "gap_limit_ns", "raw_retention"}
ROW = {"record_type", "summary_index", "elapsed_ns", "trial_id", "source_stage", "reason_code", "metrics"}
COUNTS = {"source_sample_count", "tracking_valid_count", "tracking_invalid_count", "tracking_flag_available_count",
          "tracking_state_available_count", "positive_interval_count", "nonpositive_interval_count", "interval_overflow_count",
          "negative_timestamp_count", "gap_over_50ms_count", "nonfinite_pose_count", "zero_orientation_count"}
TIMES = {"first_capture_ns", "last_capture_ns", "source_duration_ns", "maximum_positive_gap_ns", "median_positive_gap_ns", "p95_positive_gap_ns"}
METRICS = COUNTS | TIMES | {"status", "unavailable_reason", "observed_rate_hz"}


class SourceError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise SourceError(reason)


def decode(line):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result
    def nonfinite(_):
        raise SourceError("nonfinite_json_number")
    try:
        return json.loads(line.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)
    except SourceError:
        raise
    except (UnicodeError, ValueError, OverflowError) as error:
        raise SourceError("malformed_source_json") from error


def integer(value, minimum=-1, maximum=2**63-1):
    return type(value) is int and minimum <= value <= maximum


def metrics(value):
    require(type(value) is dict and set(value) == METRICS, "invalid_metric_fields")
    require(all(integer(value[k], -1, 2**31-1) for k in COUNTS), "invalid_metric_count")
    require(all(integer(value[k], -(2**63)) for k in TIMES), "invalid_metric_time")
    rate = value["observed_rate_hz"]
    require(type(rate) in (int, float) and math.isfinite(rate), "invalid_observed_rate")
    if value["status"] == "unavailable":
        require(isinstance(value["unavailable_reason"], str) and value["unavailable_reason"], "missing_unavailability_reason")
        require(all(value[k] == -1 for k in COUNTS | TIMES) and rate == -1, "unavailable_is_not_zero_samples")
        return
    n = value["source_sample_count"]
    require(value["status"] == ("empty" if n == 0 else "available") and n >= 0
            and value["unavailable_reason"] == "", "invalid_metric_status")
    require(all(value[k] >= 0 for k in COUNTS), "negative_measured_count")
    require(value["tracking_valid_count"] + value["tracking_invalid_count"] == n, "tracking_counts_do_not_partition")
    require(all(value[k] <= n for k in ("tracking_flag_available_count", "tracking_state_available_count",
                "negative_timestamp_count", "nonfinite_pose_count", "zero_orientation_count")), "count_exceeds_source_samples")
    positive = value["positive_interval_count"]
    require(positive + value["nonpositive_interval_count"] + value["interval_overflow_count"] == max(0,n-1), "interval_counts_do_not_partition")
    require(value["gap_over_50ms_count"] <= positive, "invalid_gap_count")
    quantiles = [value[k] for k in ("median_positive_gap_ns", "p95_positive_gap_ns", "maximum_positive_gap_ns")]
    if positive:
        require(0 < quantiles[0] <= quantiles[1] <= quantiles[2], "invalid_gap_quantiles")
        require((quantiles[2] > 50_000_000) == (value["gap_over_50ms_count"] > 0), "gap_limit_count_mismatch")
    else:
        require(quantiles == [-1,-1,-1], "no_intervals_have_no_quantiles")
    if n == 0:
        require(all(value[k] == -1 for k in ("first_capture_ns", "last_capture_ns", "source_duration_ns")) and rate == -1, "empty_source_has_no_timing")
    elif value["nonpositive_interval_count"] or value["interval_overflow_count"] or value["negative_timestamp_count"]:
        require(value["source_duration_ns"] == -1 and rate == -1, "invalid_clock_has_no_sampling_rate")
    else:
        duration = value["last_capture_ns"] - value["first_capture_ns"]
        require(value["first_capture_ns"] >= 0 and duration == value["source_duration_ns"]
                and (duration > 0 if n > 1 else duration == 0), "source_duration_mismatch")
        require(math.isclose(rate, (n-1)*1e9/duration, rel_tol=1e-9, abs_tol=1e-6) if n>1 else rate == -1,
                "source_rate_mismatch")


def inspect_source_quality(ledger_path: Path | str, source_path: Path | str) -> dict:
    ledger_path, source_path = Path(ledger_path), Path(source_path)
    base = inspect_ledger(ledger_path)
    result = dict(status="INVALID", ledger_status=base["status"], issues=[], summaries=[], counts=None,
                  scope="Source diagnostics; complete accounting does not establish headset readiness.")
    if base["counts"] is None:
        result["issues"] = ["unreadable_trial_plan"]
        return result
    trials = {t["trial_id"]:t for t in base["trials"]}
    expected = {identity for identity,t in trials.items() if t["attempted"]}
    try:
        require(source_path.resolve().parent == ledger_path.resolve().parent and not source_path.is_symlink(), "source_file_outside_visit_directory")
        require(source_path.stat().st_size <= 33_554_432, "source_file_too_large")
        data = source_path.read_bytes()
        result["source_quality_sha256"] = hashlib.sha256(data).hexdigest()
        lines = data.splitlines(keepends=True)
        require(lines and lines[0].endswith(b"\n"), "missing_or_torn_source_header")
        header = decode(lines[0])
        plan = json.loads(ledger_path.read_bytes().splitlines()[0]) # Already checked by inspect_ledger.
        require(type(header) is dict and set(header) == HEADER, "invalid_source_header_fields")
        require(header["record_type"] == "source_quality_plan" and header["schema_version"] == "quest-source-quality-v1", "unsupported_source_schema")
        require(all(header[k] == plan[k] for k in ("participant_code","visit_code","device_id","session_id","processing_version")), "source_identity_mismatch")
        require(header["ledger_file_name"] == ledger_path.name and header["time_basis"] == plan["time_basis"]
                and header["raw_retention"] == "not_saved" and header["interval_quantile_method"] == "nearest_rank"
                and type(header["gap_limit_ns"]) is int and header["gap_limit_ns"] == 50_000_000, "source_policy_mismatch")
    except (OSError, SourceError) as error:
        result["issues"].append(str(error) if isinstance(error, SourceError) else "source_file_read_failed")
        return result
    seen, previous_time = set(), -1
    for index,line in enumerate(lines[1:],1):
        try:
            require(line.endswith(b"\n") and len(line) <= 1_048_576, "oversized_or_torn_source_record")
            row=decode(line)
            require(type(row) is dict and set(row) == ROW and row["record_type"] == "source_quality", "invalid_source_row_fields")
            require(type(row["summary_index"]) is int and row["summary_index"] == index, "source_row_order_mismatch")
            require(integer(row["elapsed_ns"],0) and row["elapsed_ns"] >= previous_time, "source_clock_mismatch")
            identity=row["trial_id"]
            require(isinstance(identity,str) and identity in expected and identity not in seen, "unknown_unattempted_or_duplicate_summary")
            require(row["source_stage"] in {"completed","stopped","unconfirmed"} and isinstance(row["reason_code"],str)
                    and re.fullmatch(r"[a-z][a-z0-9_]{0,95}",row["reason_code"]), "invalid_source_stage_or_reason")
            metrics(row["metrics"])
            t=trials[identity]
            if row["source_stage"] == "completed":
                require(row["reason_code"] == "capture_completed" and row["metrics"]["status"] != "unavailable", "invalid_completed_summary")
                require(t["completed"] or not base["closed"], "source_completion_not_in_ledger")
                if t["completed"]:
                    require(row["metrics"]["source_sample_count"] == t["raw_sample_count"], "source_count_differs_from_completion")
            elif row["source_stage"] == "unconfirmed":
                require(not t["began"] and row["metrics"]["status"] == "unavailable"
                        and row["metrics"]["unavailable_reason"] == row["reason_code"], "unconfirmed_capture_not_unavailable")
            else:
                require(not t["completed"] and row["metrics"]["status"] != "unavailable", "stopped_capture_is_not_completed")
            seen.add(identity);previous_time=row["elapsed_ns"];result["summaries"].append(row)
        except (SourceError, TypeError, OverflowError) as error:
            result["issues"].append(str(error) if isinstance(error,SourceError) else "invalid_source_value_type")
            break
    missing=sorted(expected-seen)
    result["missing_trial_summaries"]=missing
    if missing:result["issues"].append("missing_attempted_trial_summaries")
    result["counts"]=dict(attempted=len(expected),summaries=len(seen),missing=len(missing),
                          measured=sum(r["metrics"]["status"]=="available" for r in result["summaries"]),
                          empty=sum(r["metrics"]["status"]=="empty" for r in result["summaries"]),
                          unavailable=sum(r["metrics"]["status"]=="unavailable" for r in result["summaries"]))
    result["status"]="INVALID" if result["issues"] or base["status"]=="INVALID" else "COMPLETE" if base["closed"] else "INCOMPLETE"
    return result
