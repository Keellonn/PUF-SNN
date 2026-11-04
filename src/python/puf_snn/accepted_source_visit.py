"""Read-only accounting for optional v2 development source retention.

The ledger is authoritative for acceptance. Files without receipts are reported,
never adopted or deleted. COMPLETE is file accounting, not device/study readiness.
Unity supplies the exact quaternion replay; this checker checks links and grids.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from .accepted_source import decode_source, load_json, source_metrics, target_offset
from .source_quality import inspect_source_quality
from .trial_ledger import inspect_ledger

POLICY = "accepted_source_development_only"
HEADER = {"record_type", "schema_version", "purpose", "planned_acquisition_mode", "raw_retention",
          "participant_code", "visit_code", "device_id", "session_id", "processing_version",
          "ledger_file_name", "window_file_name", "quality_file_name", "source_directory_name"}
RECEIPT = {"record_type", "trial_id", "file_name", "file_sha256", "window_id", "window_line_sha256", "byte_length"}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def read(path, limit):
    need(not path.is_symlink() and path.is_file(), "missing_or_linked_file")
    need(path.stat().st_size <= limit, "oversized_file")
    data = path.read_bytes()
    need(data and data.endswith(b"\n"), "empty_or_torn_file")
    return data


def check_records(source, window, metrics):
    rows = decode_source(source)
    need(source["schema_version"] == "quest-accepted-source-v2", "not_integrated_source_format")
    for key in ("device_id", "session_id", "trial_id", "split", "label", "sequence_number", "coordinate_frame"):
        need(type(window.get(key)) is type(source[key]) and window[key] == source[key], "source_window_identity_mismatch")
    need(window.get("schema_version") == "0.2" and window.get("source_trial_id") == source["trial_id"] and
         window.get("window_id") == source["trial_id"] + "-window-000", "source_window_link_mismatch")
    start = rows[0]["capture_time_ns"]
    for key, value in (("window_start_ns", start), ("window_end_ns", start + 2_000_000_000), ("target_sample_rate_hz", 60)):
        need(type(window.get(key)) is int and window[key] == value, "window_time_mismatch")
    samples = window.get("samples")
    need(type(samples) is list and len(samples) == 120, "invalid_processed_sample_count")
    upper, valid = 1, 0
    for i, sample in enumerate(samples):
        need(type(sample) is dict and type(sample.get("sample_index")) is int and sample["sample_index"] == i, "window_sample_order_mismatch")
        target = start + target_offset(i)
        need(type(sample.get("capture_time_ns")) is int and sample["capture_time_ns"] == target, "window_grid_mismatch")
        while upper < len(rows) - 1 and rows[upper]["capture_time_ns"] < target:
            upper += 1
        expected = rows[upper - 1]["tracking_valid"] and rows[upper]["tracking_valid"]
        need(type(sample.get("tracking_valid")) is bool and sample["tracking_valid"] == expected, "resampled_tracking_mismatch")
        valid += expected
        for key, length in (("position_m", 3), ("orientation_xyzw", 4)):
            vector = sample.get(key)
            need(type(vector) is list and len(vector) == length and
                 all(type(v) in (int, float) and math.isfinite(v) for v in vector), "invalid_window_pose")
    need(valid >= 114, "resampled_tracking_refusal")
    measured = source_metrics(rows)
    need(type(metrics) is dict and metrics.keys() == measured.keys(), "source_metrics_fields_mismatch")
    for key, expected in measured.items():
        actual = metrics[key]
        need(type(actual) in (int, float) and math.isclose(actual, expected, rel_tol=1e-12)
             if key == "observed_rate_hz" else type(actual) is type(expected) and actual == expected, "source_metrics_mismatch")


def inspect_source_visit(ledger_path, *, base_report=None):
    path = Path(ledger_path)
    base = base_report if base_report is not None else inspect_ledger(path, verify_sources=False)
    result = dict(status="INVALID", issues=[], source_receipts=0, accepted_trials=0, closed=False,
                  live_collection_ready=False, unity_quaternion_replay_checked=False,
                  ledger_integration_checked=True, files_preserved=True)
    try:
        need(base["counts"] is not None, "unreadable_ledger")
        need(base["status"] != "INVALID", "invalid_base_ledger")
        plan = load_json(read(path, 33_554_432).splitlines()[0])
        need(plan["schema_version"] == "quest-trial-ledger-v2" and plan["raw_retention"] == POLICY, "source_retention_not_declared")
        root = path.parent
        manifest_path = root / (plan["visit_code"] + "-accepted-source.jsonl")
        directory = root / (plan["visit_code"] + "-accepted-source")
        need(not directory.is_symlink() and directory.is_dir() and directory.resolve().parent == root.resolve(), "missing_or_linked_source_directory")
        data = read(manifest_path, 1_048_576)
        result["manifest_sha256"] = hashlib.sha256(data).hexdigest()
        lines = data.splitlines(keepends=True)
        header = load_json(lines[0])
        need(type(header) is dict and set(header) == HEADER, "invalid_source_visit_header")
        for key, value in dict(record_type="accepted_source_plan", schema_version="quest-accepted-source-visit-v2",
                               purpose="development_only", planned_acquisition_mode="pc_hosted_quest_link", raw_retention=POLICY,
                               ledger_file_name=path.name, window_file_name=plan["window_file_name"],
                               quality_file_name=plan["visit_code"] + "-source-quality.jsonl",
                               source_directory_name=directory.name).items():
            need(header[key] == value, "source_visit_policy_or_file_link_mismatch")
        for key in ("participant_code", "visit_code", "device_id", "session_id", "processing_version"):
            need(header[key] == plan[key], "source_visit_identity_mismatch")
        quality = inspect_source_quality(path, root / header["quality_file_name"], verify_sources=False)
        need(quality["status"] != "INVALID", "invalid_source_quality")
        summaries = {r["trial_id"]: r for r in quality["summaries"]}
        accepted = {t["trial_id"]: t for t in base["trials"] if t["stage"] == "accepted"}
        result["accepted_trials"] = len(accepted)
        ledger_rows = [load_json(line) for line in read(path, 33_554_432).splitlines()[1:]]
        accepted_rows = {r["trial_id"]: r for r in ledger_rows if r["event_type"] == "accepted"}
        windows = {}
        if accepted:
            offset = 0
            for line in read(root / plan["window_file_name"], 80_000_000).splitlines(keepends=True):
                windows[offset] = load_json(line)
                offset += len(line)
        seen, used = set(), set()
        need(len(lines) <= plan["maximum_trials"] + 2, "too_many_source_receipts")
        for line in lines[1:]:
            need(line.endswith(b"\n"), "torn_source_receipt")
            row = load_json(line)
            need(type(row) is dict and not result["closed"], "invalid_or_post_close_receipt")
            if row.get("record_type") == "accepted_source_closed":
                need(set(row) == {"record_type", "accepted_source_count"} and type(row["accepted_source_count"]) is int
                     and row["accepted_source_count"] == len(seen), "source_close_count_mismatch")
                result["closed"] = True
                continue
            need(set(row) == RECEIPT and row["record_type"] == "accepted_source", "invalid_source_receipt")
            trial_id = row["trial_id"]
            need(type(trial_id) is str and trial_id in accepted and trial_id not in seen, "source_for_nonaccepted_or_duplicate_trial")
            trial = accepted[trial_id]
            need(row["file_name"] == trial_id + ".json", "source_filename_mismatch")
            blob = read(directory / row["file_name"], 16 * 1024 * 1024)
            need(type(row["byte_length"]) is int and len(blob) == row["byte_length"] and
                 hashlib.sha256(blob).hexdigest() == row["file_sha256"], "source_receipt_hash_or_length_mismatch")
            source = load_json(blob)
            need(source["processing_version"] == plan["processing_version"], "source_processing_version_mismatch")
            receipt = accepted_rows[trial_id]
            need(row["window_id"] == receipt["window_id"] and row["window_line_sha256"] == receipt["line_sha256"], "source_window_receipt_mismatch")
            summary = summaries[trial_id]
            need(summary["source_stage"] == "completed", "source_without_completed_summary")
            check_records(source, windows[receipt["file_offset"]], summary["metrics"])
            seen.add(trial_id)
            used.add(row["file_name"])
        actual = {f.name for f in directory.iterdir()}
        result["source_receipts"] = len(seen)
        result["unreferenced_source_files"] = sorted(actual - used)
        result["missing_source_trials"] = sorted(set(accepted) - seen)
        need(not result["unreferenced_source_files"], "unreferenced_source_files")
        need(not result["missing_source_trials"], "missing_accepted_source_receipts")
        need(actual == used, "source_file_set_mismatch")
        result["status"] = "COMPLETE" if result["closed"] and base["closed"] and quality["status"] == "COMPLETE" else "INCOMPLETE"
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        import sys
        error = sys.exc_info()[1]
        result["issues"].append(str(error) if isinstance(error, ValueError) else "unreadable_or_invalid_source_visit")
    return result
