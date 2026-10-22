"""Pure-stdlib analysis of saved instrumented timing; never run the pipeline.

Inclusive span durations are retained separately. An exclusive interval partition
subtracts only direct children inside each observation, never summary percentiles.
Residuals are explicitly unisolated work/observer time, not new stage measurements.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path

INPUT_MANIFEST_SHA256 = "10135c6e3849015c6afcfb96c91d9bc25bdeabdbdc1da2531b1ec65501403b50"
BENCHMARK_COMMIT = "78f499a92f633a4793c776a070058e3a6a9a0b61"
RESULTS_COMMIT = "a4a9e2548fd30ee2383923dbd0de6cd5c45c587f"
GROUP_FIELDS = ("condition", "phase", "path", "decision", "reason")
CONDITIONS = (
    "logistic_motion_logistic_anomaly", "logistic_motion_forest_anomaly",
    "forest_motion_forest_anomaly", "snn32_seed7_forest_anomaly",
    "snn32_seed17_forest_anomaly", "snn32_seed27_forest_anomaly",
)
PRIMARY_CONDITIONS = (CONDITIONS[0], CONDITIONS[1], CONDITIONS[3])
ACCEPTED_PATHS = frozenset({"fresh_to_first_window", "post_window_recurring",
                          "valid_receiver_after_bad_tag", "post_window_after_refusals"})
REJECTED_PATHS = frozenset({"bad_tag_receiver", "exact_replay_receiver",
                          "malformed_json_receiver", "pre_tag_quality_refusal"})

# Category, interpretation. These name measured work, not pure crypto/kernel time.
STAGE_DEFINITIONS = {
    "simulated_response_read": "Modeled response generation, not physical acquisition.",
    "reconstruction": "Actual recorded BCH reconstruction; includes any observer/GC delay.",
    "credential_verification": "Recorded independent credential-verification call(s).",
    "local_admission_checks": "Measured local authorization/binding/consumption calls, excluding nested credential verification.",
    "session_establishment_unisolated": "Handshake/request/activation remainder, including unseparated HKDF/confirmation work and observer cost.",
    "admission_orchestration_unisolated": "Admission orchestration remainder not covered by named children.",
    "binary32_adapter": "Canonical binary32 input adaptation before sender sealing.",
    "sender_serialization_and_quality": "Sender serialization including its quality validation; not separately timed.",
    "sender_window_hmac": "Recorded window-tag generation call.",
    "sender_binding_unisolated": "Sender seal remainder: binding/state/orchestration/observer work not separately timed.",
    "receiver_parsing": "Envelope and binary parser call.",
    "receiver_window_hmac": "Recorded verifier window-tag calculation, not complete authentication.",
    "receiver_quality_check": "Verifier quality-check call.",
    "receiver_binding_sequence_state_unisolated": "Verifier remainder including binding, sequence checks, locks/state publication and observer work; NOT isolated sequence latency.",
    "model_input_preprocessing": "Shared model-input preparation; model-specific normalization remains in consumer timing.",
    "motion_consumer": "Motion consumer including normalization/tensor preparation/prediction decoding.",
    "anomaly_consumer": "Anomaly consumer including feature scaling and frozen-threshold decision.",
    "release_conversion_unisolated": "Accepted release remainder including conversion/dispatch/observer work outside consumer children.",
    "in_memory_audit_measured": "Recorded audit record/prepare/commit spans, exclusive of their children; not all audit-related overhead and not durable storage.",
    "outer_orchestration_unisolated": "Direct root/first-post-window remainder outside named child spans.",
}
STAGE_MAP = {
    "response_generation_simulator": "simulated_response_read",
    "reconstruction": "reconstruction",
    "independent_credential_verification": "credential_verification",
    "admission_total": "admission_orchestration_unisolated",
    "binary32_adapter": "binary32_adapter",
    "serialization_including_quality": "sender_serialization_and_quality",
    "window_hmac_generation": "sender_window_hmac",
    "sender_seal_total": "sender_binding_unisolated",
    "envelope_and_binary_parser": "receiver_parsing",
    "window_hmac_verification_calculation": "receiver_window_hmac",
    "verifier_quality_check": "receiver_quality_check",
    "verifier_authentication_total": "receiver_binding_sequence_state_unisolated",
    "prepare_both_model_inputs": "model_input_preprocessing",
    "motion_consumer_including_normalization": "motion_consumer",
    "anomaly_consumer_including_threshold": "anomaly_consumer",
    "accepted_release_and_consumers": "release_conversion_unisolated",
    "first_post_window_total": "outer_orchestration_unisolated",
    **{name: "outer_orchestration_unisolated" for name in ACCEPTED_PATHS | REJECTED_PATHS},
    **{name: "session_establishment_unisolated" for name in (
        "sender_admission_and_request", "receiver_challenge", "sender_confirmation",
        "receiver_confirmation", "sender_activation")},
    **{name: "local_admission_checks" for name in (
        "local_authorization_including_verification", "local_request_binding",
        "receiver_local_admission", "local_challenge_binding", "sender_local_admission_claim")},
    **{f"{owner}_audit_{operation}": "in_memory_audit_measured"
       for owner in ("sender", "verifier") for operation in ("record", "prepare", "commit")},
}


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def scoped_path(root, relative):
    root, raw = Path(root).resolve(), Path(relative)
    target = (root / raw).resolve()
    if (not isinstance(relative, str) or "\\" in relative or ":" in relative
            or raw.is_absolute() or ".." in raw.parts or target == root
            or not target.is_relative_to(root)):
        raise ValueError("artifact paths must stay within the evidence directory")
    return target


def statistics(values):
    values = sorted(values)
    if not values or any(type(value) is not int or value < 0 for value in values):
        raise ValueError("statistics require nonnegative integer nanoseconds")
    def percentile(fraction):
        position = fraction * (len(values) - 1)
        low = math.floor(position)
        return (values[low] + (values[min(low + 1, len(values) - 1)] - values[low])
                * (position - low)) / 1e6
    return dict(count=len(values), p50_ms=percentile(.5), p95_ms=percentile(.95),
                p99_ms=percentile(.99), max_ms=values[-1] / 1e6)


def validate_tree(trace):
    spans = trace["spans"]
    if (not spans or spans[0]["id"] != 0 or spans[0]["parent_id"] is not None
            or spans[0]["stage"] != trace["path"] or spans[0]["exception"] is not False
            or spans[0]["wall_ns"] != trace["elapsed_ns"]
            or spans[0]["thread_cpu_ns"] != trace["thread_cpu_ns"]):
        raise ValueError("invalid direct timing root")
    children, seen = defaultdict(list), {}
    for span in spans:
        for name in ("id", "start_ns", "wall_ns", "thread_cpu_ns"):
            if type(span[name]) is not int or span[name] < 0:
                raise ValueError("span identifiers/times require nonnegative integers")
        if span["id"] in seen or type(span["exception"]) is not bool:
            raise ValueError("duplicate span or invalid exception flag")
        if span["stage"] not in STAGE_MAP:
            raise ValueError(f"unregistered saved stage: {span['stage']}")
        parent = span["parent_id"]
        if parent is None:
            if seen:
                raise ValueError("more than one root")
        else:
            if type(parent) is not int or parent not in seen:
                raise ValueError("parent must precede its child")
            owner = seen[parent]
            if (span["start_ns"] < owner["start_ns"] or span["start_ns"] + span["wall_ns"]
                    > owner["start_ns"] + owner["wall_ns"]):
                raise ValueError("child extends outside parent")
            children[parent].append(span)
        seen[span["id"]] = span
    for siblings in children.values():
        end = -1
        for child in sorted(siblings, key=lambda row: (row["start_ns"], row["id"])):
            if child["start_ns"] < end:
                raise ValueError("overlapping sibling spans cannot form a serial partition")
            end = child["start_ns"] + child["wall_ns"]
    return children


def partition_trace(trace):
    """Per-observation exclusive partition; residuals are derived, not isolated calls."""
    children = validate_tree(trace)
    exclusive = Counter({category: 0 for category in STAGE_DEFINITIONS})
    inclusive, occurrences = Counter(), Counter()
    for span in trace["spans"]:
        remainder = span["wall_ns"] - sum(child["wall_ns"] for child in children[span["id"]])
        if remainder < 0:
            raise ValueError("negative exclusive interval")
        category = STAGE_MAP[span["stage"]]
        exclusive[category] += remainder
        occurrences[category] += 1
        if span["id"] != 0:
            inclusive[span["stage"]] += span["wall_ns"]
    if sum(exclusive.values()) != trace["elapsed_ns"]:
        raise ValueError("exclusive partition does not reconcile with direct root")
    return dict(exclusive), dict(inclusive), dict(occurrences)


def rows_from_groups(groups, field_names):
    return [dict(zip(field_names, key), **statistics(values))
            for key, values in sorted(groups.items())]


def reconcile_attempts(attempts, condition_names=CONDITIONS, measured=600, warmup=20):
    accepted, refused, signatures = Counter(), Counter(), defaultdict(set)
    for condition in condition_names:
        for phase, indices in (("measured", range(measured)), ("warmup", range(1, warmup)),
                               ("condition_first_use", range(1))):
            for index in indices:
                key = (condition, phase, index)
                if key not in attempts or "fresh_to_first_window" not in attempts[key]:
                    raise ValueError("missing planned fresh admission")
                entry = attempts[key]["fresh_to_first_window"]
                expected_paths = (ACCEPTED_PATHS | REJECTED_PATHS if entry["decision"] == "accept"
                                  else {"fresh_to_first_window"})
                if (set(attempts[key]) != expected_paths or type(entry["read_count"]) is not int
                        or entry["read_count"] != 1):
                    raise ValueError("admission/control paths or read policy do not reconcile")
                signatures[(phase, index)].add((entry["source_window_id"], entry["device_id"],
                    entry["selected_bit_error_count"], entry["decision"], entry["reason"],
                    entry["admission"]["decision"], entry["admission"]["reason"]))
                if entry["decision"] == "accept":
                    accepted[(condition, phase)] += 1
                else:
                    refused[(condition, phase, entry["stage"], entry["reason"])] += 1
    if len(attempts) != len(condition_names) * (measured + warmup):
        raise ValueError("unexpected condition/phase/attempt")
    if any(len(group) != 1 for group in signatures.values()):
        raise ValueError("paired source/noise/admission outcomes differ")
    return dict(fresh_attempt_count=len(attempts), response_read_count=len(attempts),
        trace_count=sum(len(paths) for paths in attempts.values()),
        accepted_by_condition_phase=[dict(condition=key[0], phase=key[1], count=count)
                                     for key, count in sorted(accepted.items())],
        refused_by_condition_phase_reason=[dict(condition=key[0], phase=key[1], stage=key[2],
            reason=key[3], count=count) for key, count in sorted(refused.items())],
        rejected_window_model_calls=0, paired_admission_signatures_match=True)


class SavedStageAnalysis:
    """Retain numeric accounting, not every original span tree in memory."""
    def __init__(self):
        self.roots, self.inclusive, self.exclusive = defaultdict(list), defaultdict(list), defaultdict(list)
        self.present = Counter()
        self.attempts = defaultdict(dict)
        self.observations = []

    def add(self, trace):
        group = tuple(trace[name] for name in GROUP_FIELDS)
        if trace["condition"] not in CONDITIONS or trace["path"] not in ACCEPTED_PATHS | REJECTED_PATHS:
            raise ValueError("unknown saved condition/path")
        if type(trace["attempt_index"]) is not int or trace["attempt_index"] < 0:
            raise ValueError("invalid attempt index")
        if type(trace["selected_bit_error_count"]) is not int or not 0 <= trace["selected_bit_error_count"] <= 63:
            raise ValueError("invalid selected-bit error count")
        if any(not isinstance(trace[name], str) or not trace[name] for name in ("source_window_id", "device_id")):
            raise ValueError("missing source/device identity")
        if trace["decision"] not in {"accept", "reject"}:
            raise ValueError("invalid decision")
        calls = trace["model_calls"]
        if set(calls) != {"preprocessing", "motion", "anomaly"} or any(type(v) is not int for v in calls.values()):
            raise ValueError("invalid consumer counters")
        if calls != {name: int(trace["decision"] == "accept") for name in calls}:
            raise ValueError("decision and consumer calls disagree")
        if (trace["path"] in REJECTED_PATHS and trace["decision"] != "reject"
                or trace["path"] in ACCEPTED_PATHS - {"fresh_to_first_window"} and trace["decision"] != "accept"):
            raise ValueError("control has unexpected decision")
        key = (trace["condition"], trace["phase"], trace["attempt_index"])
        if trace["path"] in self.attempts[key]:
            raise ValueError("duplicate timing observation")
        exclusive, inclusive, present = partition_trace(trace)
        if trace["path"] == "fresh_to_first_window":
            if trace["admission"]["decision"] != trace["decision"]:
                raise ValueError("fresh admission and root decision disagree")
            first_count = sum(span["stage"] == "first_post_window_total" for span in trace["spans"])
            if first_count != int(trace["decision"] == "accept"):
                raise ValueError("first-window measurement does not match admission")
        elif any(span["stage"] in {"reconstruction", "admission_total"} for span in trace["spans"]):
            raise ValueError("recurring/receiver paths must not include new admission")
        kept = {name: trace[name] for name in ("decision", "source_window_id", "device_id",
                                              "selected_bit_error_count", "source_split")}
        if trace["path"] == "fresh_to_first_window":
            kept.update(read_count=trace["read_count"], admission=trace["admission"],
                        reason=trace["reason"], stage=trace["stage"])
        self.attempts[key][trace["path"]] = kept
        self.roots[group].append(trace["elapsed_ns"])
        for stage, ns in inclusive.items():
            self.inclusive[(*group, stage)].append(ns)
        for category, ns in exclusive.items():
            self.exclusive[(*group, category)].append(ns)
            self.present[(*group, category)] += int(present.get(category, 0) > 0)
        self.observations.append(dict(zip(GROUP_FIELDS, group), attempt_index=trace["attempt_index"],
            source_window_id=trace["source_window_id"], device_id=trace["device_id"],
            source_split=trace["source_split"], elapsed_ns=trace["elapsed_ns"],
            partition_sum_ns=sum(exclusive.values()), **{f"{name}_ns": ns for name, ns in exclusive.items()}))

    def finalize(self, condition_names=CONDITIONS, measured=600, warmup=20):
        for key, paths in self.attempts.items():
            fresh = paths.get("fresh_to_first_window")
            if fresh is None:
                raise ValueError("window without admission")
            expected_split = "test" if key[1] == "measured" else "validation"
            for row in paths.values():
                if any(row[name] != fresh[name] for name in (
                        "source_window_id", "device_id", "selected_bit_error_count", "source_split")):
                    raise ValueError("source/noise differs within one attempt")
                if row["source_split"] != expected_split:
                    raise ValueError("wrong warmup/test split")
        reconciliation = reconcile_attempts(self.attempts, condition_names, measured, warmup)
        summary = dict(units="ms", quantile_method="linear interpolation at q*(n-1)",
            root_paths=rows_from_groups(self.roots, GROUP_FIELDS),
            nested_stages=rows_from_groups(self.inclusive, (*GROUP_FIELDS, "stage")))
        exclusive = rows_from_groups(self.exclusive, (*GROUP_FIELDS, "category"))
        for row in exclusive:
            row["observations_with_registered_span"] = self.present[tuple(row[name] for name in GROUP_FIELDS) + (row["category"],)]
            row["interpretation"] = STAGE_DEFINITIONS[row["category"]]
            row["accounting"] = "per-observation exclusive interval; no sum-of-percentiles total"
        return dict(summary=summary, exclusive_stages=exclusive, reconciliation=reconciliation,
                    observations=self.observations)


def verify_completed_input(directory, expected_manifest=INPUT_MANIFEST_SHA256):
    directory = Path(directory).resolve()
    if (directory / "INCOMPLETE").exists() or sha256(directory / "manifest.json") != expected_manifest:
        raise ValueError("source evidence is incomplete or its pinned manifest changed")
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    complete = json.loads((directory / "COMPLETE").read_text(encoding="utf-8"))
    if complete["manifest_sha256"] != expected_manifest:
        raise ValueError("completion marker does not match pinned manifest")
    checked = {"manifest.json": expected_manifest, "COMPLETE": sha256(directory / "COMPLETE")}
    for name, expected in manifest["artifacts"].items():
        if name in {"manifest.json", "COMPLETE", "INCOMPLETE"}:
            raise ValueError("reserved artifact name")
        path = scoped_path(directory, name)
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"saved artifact hash mismatch: {name}; preserve original files")
        checked[name] = expected
    return manifest, complete, checked


def read_checked_run(directory):
    directory = Path(directory).resolve()
    manifest, complete, checked = verify_completed_input(directory)
    if manifest["source_commit"] != BENCHMARK_COMMIT or manifest["run_type"] != "week6-fresh-v2-timing-v1":
        raise ValueError("wrong benchmark provenance")
    analysis = SavedStageAnalysis()
    for condition in CONDITIONS:
        with (directory / f"timings-{condition}.jsonl").open(encoding="utf-8") as handle:
            for line in handle:
                trace = json.loads(line)
                if trace["condition"] != condition:
                    raise ValueError("condition file contains other condition")
                analysis.add(trace)
    result = analysis.finalize()
    saved_summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    saved_reconciliation = json.loads((directory / "reconciliation.json").read_text(encoding="utf-8"))
    if result["summary"] != saved_summary:
        raise ValueError("recomputed direct/inclusive quantiles differ from saved summary")
    if result["reconciliation"] != manifest["reconciliation"] or saved_reconciliation != result["reconciliation"]:
        raise ValueError("admission/delivery accounting differs from saved run")
    for name in ("fresh_attempt_count", "trace_count"):
        if complete[name] != result["reconciliation"][name]:
            raise ValueError("completion counts disagree")
    if complete["outlier_count"] != manifest["outlier_count"]:
        raise ValueError("outlier marker counts disagree")
    result.update(manifest=manifest, checked_input_hashes=checked)
    return result
