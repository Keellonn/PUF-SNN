"""Read-only reconciliation of coded Quest trial ledgers and window receipts.

COMPLETE means all scheduled trials are accounted for, including skips/stops.
It does not mean that tracking passed, a visit met its target, or research is approved.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


LABELS = {"nod", "shake", "look_left_return", "look_right_return", "still"}
CODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
REASON = re.compile(r"[a-z][a-z0-9_]{0,95}\Z")
TERMINAL = {"accepted", "rejected", "processing_failed", "skipped", "not_attempted", "stopped"}
NOTES = {"participant_reported_mistake", "observed_nonexecution", "late_movement", "movement_after_interval"}
PLAN_KEYS = {"record_type", "schema_version", "participant_code", "visit_code", "device_id", "session_id",
             "processing_version", "window_file_name", "time_basis", "raw_retention", "repeat_policy", "schedule_seed",
             "maximum_trials", "created_elapsed_ns", "trials"}
TRIAL_KEYS = {"trial_id", "trial_index", "block_index", "prompted_task", "repeat_of_trial_id"}
EVENT_KEYS = {"record_type", "event_index", "event_type", "elapsed_ns", "trial_id", "reason_code",
              "raw_sample_count", "window_id", "file_name", "line_sha256", "file_offset", "line_length"}


class LedgerError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise LedgerError(message)


def _integer(value, minimum=0, maximum=2**63 - 1):
    return type(value) is int and minimum <= value <= maximum


def _filename(value):
    return isinstance(value, str) and value not in {"", ".", ".."} and not any(c in value for c in "/\\:")


def _object(pairs):
    value = {}
    for key, item in pairs:
        _require(key not in value, "duplicate_json_key")
        value[key] = item
    return value


def _decode(data):
    def nonfinite(_):
        raise LedgerError("nonfinite_json_number")
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_object, parse_constant=nonfinite)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise LedgerError("malformed_json") from error


def _plan(plan):
    _require(type(plan) is dict and set(plan) == PLAN_KEYS, "invalid_plan_fields")
    _require(plan["record_type"] == "plan" and plan["schema_version"] == "quest-trial-ledger-v1", "unsupported_plan")
    for field in ("participant_code", "visit_code", "device_id", "session_id"):
        _require(isinstance(plan[field], str) and CODE.fullmatch(plan[field]), "invalid_code")
    _require(isinstance(plan["processing_version"], str) and bool(plan["processing_version"].strip())
             and len(plan["processing_version"]) <= 256, "missing_processing_version")
    _require(_filename(plan["window_file_name"]), "invalid_window_filename")
    _require(plan["time_basis"] == "head-capture-stopwatch-ns" and plan["raw_retention"] == "not_saved"
             and plan["repeat_policy"] == "none", "unsupported_policy")
    _require(_integer(plan["schedule_seed"], -(2**31), 2**31 - 1), "invalid_seed")
    _require(_integer(plan["maximum_trials"], 1, 75) and _integer(plan["created_elapsed_ns"]), "invalid_plan_numbers")
    _require(type(plan["trials"]) is list and 1 <= len(plan["trials"]) <= plan["maximum_trials"], "invalid_trial_count")
    trials = {}
    for index, trial in enumerate(plan["trials"]):
        _require(type(trial) is dict and set(trial) == TRIAL_KEYS, "invalid_trial_fields")
        identity = trial["trial_id"]
        _require(isinstance(identity, str) and CODE.fullmatch(identity) and identity not in trials, "invalid_or_duplicate_trial")
        _require(type(trial["trial_index"]) is int and trial["trial_index"] == index
                 and _integer(trial["block_index"], 1, 75), "invalid_trial_order")
        _require(isinstance(trial["prompted_task"], str) and trial["prompted_task"] in LABELS
                 and trial["repeat_of_trial_id"] == "", "invalid_task_or_repeat")
        trials[identity] = dict(trial, stage="scheduled", attempted=False, began=False, completed=False, notes=[])
    return trials


def _artifacts(plan, trials, accepted, directory):
    issues = []
    path = directory / plan["window_file_name"]
    if not path.exists():
        return (["missing_window_file"] if accepted else []), 0, None
    if path.is_symlink() or path.resolve().parent != directory.resolve():
        return ["window_path_outside_visit_directory"], 0, None
    rows, digest, offset = {}, hashlib.sha256(), 0
    try:
        with path.open("rb") as stream:
            while True:
                line = stream.readline(1_048_577)
                if not line:
                    break
                digest.update(line)
                _require(len(line) <= 1_048_576 and line.endswith(b"\n"), "oversized_or_torn_window_record")
                record = _decode(line)
                _require(type(record) is dict, "invalid_window_record")
                rows[offset] = (record, len(line), hashlib.sha256(line).hexdigest())
                _require(len(rows) <= plan["maximum_trials"], "too_many_window_records")
                offset += len(line)
    except (OSError, LedgerError) as error:
        issues.append(str(error) if isinstance(error, LedgerError) else "window_read_failed")
    used = set()
    for entry in accepted:
        found = rows.get(entry["file_offset"])
        if found is None:
            issues.append("missing_referenced_window_record")
            continue
        record, length, sha256 = found
        trial = trials[entry["trial_id"]]
        if not (entry["file_name"] == plan["window_file_name"] and entry["line_length"] == length
                and entry["line_sha256"] == sha256 and entry["file_offset"] not in used):
            issues.append("window_receipt_mismatch")
        used.add(entry["file_offset"])
        expected = dict(window_id=entry["window_id"], source_trial_id=entry["trial_id"], trial_id=entry["trial_id"],
                        device_id=plan["device_id"], session_id=plan["session_id"],
                        sequence_number=trial["trial_index"], label=trial["prompted_task"])
        if any(record.get(key) != value for key, value in expected.items()):
            issues.append("window_identity_or_prompt_mismatch")
        if type(record.get("samples")) is not list or len(record["samples"]) != 120:
            issues.append("invalid_window_sample_count")
    orphan_count = len(set(rows) - used)
    if orphan_count:
        issues.append("unreferenced_window_records")
    return issues, orphan_count, digest.hexdigest()


def inspect_ledger(path: Path | str, *, verify_files: bool = True) -> dict:
    """Preserve all files; return counts even when the valid event prefix is incomplete."""
    path = Path(path)
    report = dict(status="INVALID", closed=False, issues=[], counts=None, trials=[], valid_prefix_events=0)
    try:
        _require(path.stat().st_size <= 33_554_432, "ledger_too_large")
        data = path.read_bytes()
        report["ledger_sha256"] = hashlib.sha256(data).hexdigest()
        lines = data.splitlines(keepends=True)
        _require(bool(lines) and lines[0].endswith(b"\n"), "missing_or_torn_plan")
        plan = _decode(lines[0])
        trials = _plan(plan)
    except (OSError, LedgerError) as error:
        report["issues"].append(str(error) if isinstance(error, LedgerError) else "ledger_read_failed")
        return report

    report.update(participant_code=plan["participant_code"], visit_code=plan["visit_code"],
                  processing_version=plan["processing_version"], raw_retention=plan["raw_retention"], repeat_policy=plan["repeat_policy"])
    previous_time, active, accepted = plan["created_elapsed_ns"], "", []
    for expected_index, line in enumerate(lines[1:], 1):
        try:
            _require(line.endswith(b"\n") and len(line) <= 1_048_576, "oversized_or_torn_ledger_record")
            entry = _decode(line)
            _require(type(entry) is dict and set(entry) == EVENT_KEYS, "invalid_event_fields")
            _require(not report["closed"], "event_after_visit_close")
            _require(entry["record_type"] == "event" and type(entry["event_index"]) is int
                     and entry["event_index"] == expected_index, "event_order_mismatch")
            _require(_integer(entry["elapsed_ns"]) and entry["elapsed_ns"] >= previous_time, "event_clock_mismatch")
            _require(all(isinstance(entry[key], str) for key in ("event_type", "trial_id", "reason_code", "window_id", "file_name", "line_sha256")), "invalid_event_strings")
            _require(_integer(entry["raw_sample_count"], -1, 2**31 - 1) and _integer(entry["file_offset"], -1)
                     and _integer(entry["line_length"], 0, 1_048_576), "invalid_event_numbers")
            kind, identity = entry["event_type"], entry["trial_id"]
            reason_required = kind in {"rejected", "processing_failed", "skipped", "not_attempted", "stopped", "execution_note", "visit_closed"}
            _require(bool(REASON.fullmatch(entry["reason_code"])) if reason_required else entry["reason_code"] == "", "invalid_reason_code")
            if kind != "completed":
                _require(entry["raw_sample_count"] == -1, "unexpected_sample_count")
            if kind != "accepted":
                _require(entry["window_id"] == entry["file_name"] == entry["line_sha256"] == ""
                         and entry["file_offset"] == -1 and entry["line_length"] == 0, "unexpected_window_reference")
            if kind == "visit_closed":
                _require(identity == "" and all(t["stage"] in TERMINAL for t in trials.values()), "closed_with_unresolved_trials")
                report["closed"] = True
                report["visit_end_reason"] = entry["reason_code"]
            else:
                _require(identity in trials, "unknown_trial")
                trial = trials[identity]
                stage = trial["stage"]
                allowed = ((kind == "prompted" and stage == "scheduled" and not active)
                           or (kind == "start_requested" and stage == "prompted")
                           or (kind == "recording_started" and stage == "start_requested")
                           or (kind == "completed" and stage == "recording_started" and entry["raw_sample_count"] >= 0)
                           or (kind in {"accepted", "rejected", "processing_failed"} and stage == "completed")
                           or (kind in {"skipped", "not_attempted"} and stage in {"scheduled", "prompted"})
                           or (kind == "stopped" and stage in {"start_requested", "recording_started"})
                           or (kind == "execution_note" and stage in {"recording_started", "completed", "accepted", "rejected", "processing_failed", "stopped"}))
                _require(allowed, "invalid_trial_transition")
                if kind == "accepted":
                    _require(entry["file_name"] == plan["window_file_name"] and _filename(entry["file_name"])
                             and bool(entry["window_id"]) and re.fullmatch(r"[0-9a-f]{64}", entry["line_sha256"])
                             and entry["file_offset"] >= 0 and entry["line_length"] >= 2, "invalid_acceptance_receipt")
                    accepted.append(entry)
                if kind == "execution_note":
                    _require(entry["reason_code"] in NOTES, "invalid_execution_note")
                    trial["notes"].append(entry["reason_code"])
                else:
                    trial["stage"] = kind
                if kind == "prompted":
                    active = identity
                if kind == "start_requested":
                    trial["attempted"] = True
                if kind == "recording_started":
                    trial["began"] = True
                if kind == "completed":
                    trial["completed"] = True
                    trial["raw_sample_count"] = entry["raw_sample_count"]
                if kind in TERMINAL and active == identity:
                    active = ""
            previous_time = entry["elapsed_ns"]
            report["valid_prefix_events"] += 1
        except LedgerError as error:
            report["issues"].append(str(error))
            break

    items = list(trials.values())
    count = lambda predicate: sum(1 for trial in items if predicate(trial))
    counts = dict(scheduled=len(items), attempted=count(lambda t: t["attempted"]),
                  not_started=count(lambda t: not t["attempted"]), recording_began_confirmed=count(lambda t: t["began"]),
                  recording_began_uncertain=count(lambda t: t["attempted"] and not t["began"]),
                  completed=count(lambda t: t["completed"]), accepted=count(lambda t: t["stage"] == "accepted"),
                  quality_rejected=count(lambda t: t["stage"] == "rejected"),
                  processing_failed=count(lambda t: t["stage"] == "processing_failed"),
                  stopped=count(lambda t: t["stage"] == "stopped"),
                  unfinished_attempts=count(lambda t: t["attempted"] and not t["completed"] and t["stage"] != "stopped"),
                  pending_processing=count(lambda t: t["stage"] == "completed"),
                  skipped=count(lambda t: t["stage"] == "skipped"),
                  not_attempted=count(lambda t: t["stage"] == "not_attempted"),
                  unresolved_scheduled=count(lambda t: t["stage"] in {"scheduled", "prompted"}),
                  execution_notes=sum(len(t["notes"]) for t in items))
    assert counts["scheduled"] == counts["attempted"] + counts["not_started"]
    assert counts["attempted"] == counts["completed"] + counts["stopped"] + counts["unfinished_attempts"]
    assert counts["completed"] == counts["accepted"] + counts["quality_rejected"] + counts["processing_failed"] + counts["pending_processing"]
    report["counts"], report["trials"] = counts, items
    if verify_files:
        issues, orphans, digest = _artifacts(plan, trials, accepted, path.parent)
        report["issues"].extend(issues)
        report["unreferenced_window_records"] = orphans
        report["window_file_sha256"] = digest
    report["artifact_check_performed"] = verify_files
    report["status"] = "INVALID" if report["issues"] else "COMPLETE" if report["closed"] else "INCOMPLETE"
    return report
