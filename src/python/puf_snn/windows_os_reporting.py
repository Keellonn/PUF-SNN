"""Whitelist and reconcile saved numeric OS accounting before public export.

No ETL APIs, files, subprocesses, sensor records or models are accessed here.
Private clocks/OS identities/tokens and arbitrary observation text are excluded.
"""
from collections import Counter, defaultdict
import json
import math

from puf_snn.windows_os_accounting import quantile

CONDITIONS = frozenset(("logistic_motion_logistic_anomaly", "logistic_motion_forest_anomaly",
    "forest_motion_forest_anomaly", "snn32_seed7_forest_anomaly",
    "snn32_seed17_forest_anomaly", "snn32_seed27_forest_anomaly"))
PHASES = frozenset(("condition_first_use", "warmup", "measured"))
PATHS = frozenset(("fresh_to_first_window", "post_window_recurring", "bad_tag_receiver",
    "valid_receiver_after_bad_tag", "exact_replay_receiver", "malformed_json_receiver",
    "pre_tag_quality_refusal", "post_window_after_refusals"))
REASONS = frozenset(("accepted", "data_quality_failure", "duplicate_sequence", "invalid_tag", "malformed_message"))
STAGES = frozenset((
    "accepted_release_and_consumers", "admission_total", "anomaly_consumer_including_threshold",
    "binary32_adapter", "envelope_and_binary_parser", "first_post_window_total",
    "independent_credential_verification", "local_authorization_including_verification",
    "local_challenge_binding", "local_request_binding", "motion_consumer_including_normalization",
    "prepare_both_model_inputs", "receiver_challenge", "receiver_confirmation", "receiver_local_admission",
    "reconstruction", "response_generation_simulator", "sender_activation", "sender_admission_and_request",
    "sender_audit_commit", "sender_audit_prepare", "sender_audit_record", "sender_confirmation",
    "sender_local_admission_claim", "sender_seal_total", "serialization_including_quality",
    "verifier_audit_commit", "verifier_audit_prepare", "verifier_audit_record", "verifier_authentication_total",
    "verifier_quality_check", "window_hmac_generation", "window_hmac_verification_calculation"))
FLAGS = ("above_20ms_diagnostic_cutoff_not_target_claim", "above_100ms", "group_p99_tail", "group_maximum")
IDENTITY = ("condition", "phase", "path", "decision", "reason", "attempt_index")
PARTITION = ("off_ready_at_switchout_ns", "off_ready_after_event_ns", "off_not_yet_observed_ready_ns",
    "off_state_unresolved_ns", "scheduled_interrupt_ns", "scheduled_gc_without_interrupt_ns",
    "scheduled_other_ns", "schedule_uncovered_ns")
NS_FIELDS = (*PARTITION, "elapsed_ns", "thread_cpu_ns", "scheduled_residency_ns", "off_cpu_ns",
    "gc_wall_union_ns", "gc_while_scheduled_ns", "gc_while_offcpu_ns", "gc_interrupt_overlap_ns",
    "dpc_while_scheduled_ns", "isr_while_scheduled_ns", "file_operation_overlap_ns", "disk_operation_overlap_ns",
    "file_operation_offcpu_overlap_ns", "disk_operation_offcpu_overlap_ns",
    "hard_fault_interval_overlap_ns", "hard_fault_offcpu_overlap_ns")
COUNT_FIELDS = ("cpu_profile_sample_count", "caught_nested_exception_count")
HISTOGRAMS = ("raw_switchout_state_offcpu_ns", "raw_switchout_reason_offcpu_ns")
BOOL_FIELDS = ("schedule_fully_covered", "complete_causal_attribution_established")
ROOT_FIELDS = set((*IDENTITY, "retention_reasons", *NS_FIELDS, *COUNT_FIELDS, *HISTOGRAMS,
    "cpu_indices_observed", *BOOL_FIELDS))
STAGE_NS = ("wall_union_ns", "gc_overlap_ns", "scheduled_residency_ns", "off_cpu_ns",
    "same_cpu_interrupt_ns", "file_operation_overlap_ns", "disk_operation_overlap_ns", "hard_fault_overlap_ns")
MEAN_FIELDS = ("scheduled_residency_ns", "off_cpu_ns", "off_ready_at_switchout_ns", "off_ready_after_event_ns",
    "off_not_yet_observed_ready_ns", "off_state_unresolved_ns", "scheduled_interrupt_ns",
    "gc_wall_union_ns", "file_operation_overlap_ns", "disk_operation_overlap_ns",
    "hard_fault_interval_overlap_ns", "schedule_uncovered_ns")


def nonnegative(value):
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        value = int(value)
    if type(value) is not int or value < 0:
        raise ValueError("expected a nonnegative integer")
    return value


def boolean(value):
    if value in ("True", "False"):
        value = value == "True"
    if type(value) is not bool:
        raise ValueError("expected an exact boolean")
    return value


def structured(value):
    return json.loads(value) if isinstance(value, str) else value


def checked_identity(row):
    if (row["condition"] not in CONDITIONS or row["phase"] not in PHASES or row["path"] not in PATHS
            or row["decision"] not in ("accept", "reject") or row["reason"] not in REASONS):
        raise ValueError("unapproved diagnostic condition/phase/path/outcome")
    if (row["decision"] == "accept") != (row["reason"] == "accepted"):
        raise ValueError("decision/reason conflict")
    return {**{key: row[key] for key in IDENTITY[:-1]}, "attempt_index": nonnegative(row["attempt_index"])}


def key(row):
    return tuple(row[field] for field in ("condition", "phase", "path", "attempt_index"))


def group(row):
    return tuple(row[field] for field in IDENTITY[:-1])


def sanitize_root(row, index):
    if set(row) != ROOT_FIELDS:
        raise ValueError("unexpected or missing private root columns")
    output = dict(public_root_index=nonnegative(index), **checked_identity(row))
    output.update({field: nonnegative(row[field]) for field in (*NS_FIELDS, *COUNT_FIELDS)})
    output.update({field: boolean(row[field]) for field in BOOL_FIELDS})
    flags = structured(row["retention_reasons"])
    if (not isinstance(flags, list) or any(type(flag) is not str for flag in flags)
            or len(flags) != len(set(flags)) or any(flag not in FLAGS for flag in flags)):
        raise ValueError("invalid predeclared retention reasons")
    output["retention_reasons"] = list(flags)
    for field in HISTOGRAMS:
        histogram = structured(row[field])
        if not isinstance(histogram, dict) or any(not isinstance(k, str) or not k.isascii() or not k.isdecimal() or int(k) > 255 for k in histogram):
            raise ValueError("non-numeric/unknown histogram fields")
        output[field] = {k: nonnegative(value) for k, value in histogram.items()}
        if sum(output[field].values()) != output["off_cpu_ns"]:
            raise ValueError("raw off-CPU histogram does not reconcile")
    cpus = structured(row["cpu_indices_observed"])
    if (not isinstance(cpus, list) or cpus != sorted(set(cpus))
            or any(type(cpu) is not int or not 0 <= cpu < 22 for cpu in cpus)):
        raise ValueError("invalid single-group CPU inventory")
    output["logical_cpu_count_observed"] = len(cpus)  # not OS CPU identities
    wall = output["elapsed_ns"]
    if (wall <= 0 or sum(output[field] for field in PARTITION) != wall
            or output["complete_causal_attribution_established"] is not False
            or output["schedule_fully_covered"] != (output["schedule_uncovered_ns"] == 0)):
        raise ValueError("wall partition/coverage/causal flag does not reconcile")
    if (sum(output[field] for field in PARTITION[:4]) != output["off_cpu_ns"]
            or sum(output[field] for field in PARTITION[4:7]) != output["scheduled_residency_ns"]):
        raise ValueError("scheduled/off-CPU partition does not reconcile")
    for field in NS_FIELDS:
        if field != "thread_cpu_ns" and output[field] > wall:
            raise ValueError("overlay duration exceeds its root")
    if (output["gc_while_scheduled_ns"] + output["gc_while_offcpu_ns"] > output["gc_wall_union_ns"]
            or output["gc_interrupt_overlap_ns"] > min(output["gc_while_scheduled_ns"], output["scheduled_interrupt_ns"])
            or not max(output["dpc_while_scheduled_ns"], output["isr_while_scheduled_ns"]) <= output["scheduled_interrupt_ns"] <= output["dpc_while_scheduled_ns"] + output["isr_while_scheduled_ns"]):
        raise ValueError("GC/interrupt union accounting is inconsistent")
    return output


def sanitize_detail(detail, roots_by_key):
    expected = set((*IDENTITY, "retention_reasons", "clock_start_ns", "clock_end_ns", "observations"))
    if set(detail) != expected:
        raise ValueError("unexpected private detail columns")
    identity = checked_identity(detail)
    root = roots_by_key.get(key(identity))
    if root is None or any(root[field] != identity[field] for field in IDENTITY):
        raise ValueError("retained detail has no matching numeric root")
    observations = detail["observations"]
    extra = {"observations", "nested_stage_observations"}
    if set(observations) != (ROOT_FIELDS - set(IDENTITY) - {"retention_reasons"}) | extra:
        raise ValueError("unexpected nested observation fields")
    candidate = {**identity, "retention_reasons": detail["retention_reasons"],
                 **{field: value for field, value in observations.items() if field not in extra}}
    if sanitize_root(candidate, root["public_root_index"]) != root:
        raise ValueError("retained detail accounting differs from root ledger")
    start, end = nonnegative(detail["clock_start_ns"]), nonnegative(detail["clock_end_ns"])
    if end - start != root["elapsed_ns"]:
        raise ValueError("private detail duration differs")
    stages, seen = [], set()
    for stage in observations["nested_stage_observations"]:
        if set(stage) != set(("stage", *STAGE_NS, "exception_span_count")) or stage["stage"] not in STAGES or stage["stage"] in seen:
            raise ValueError("unapproved/duplicate nested stage fields")
        seen.add(stage["stage"])
        clean = {"stage": stage["stage"], **{field: nonnegative(stage[field]) for field in (*STAGE_NS, "exception_span_count")}}
        if clean["wall_union_ns"] > root["elapsed_ns"] or any(clean[field] > clean["wall_union_ns"] for field in STAGE_NS[1:]):
            raise ValueError("nested overlay exceeds its stage")
        stages.append(clean)
    # Do NOT propagate arbitrary private free text or raw clocks/CPU IDs.
    return dict(public_root_index=root["public_root_index"], **identity,
                retention_reasons=list(root["retention_reasons"]),
                nested_stage_observations=stages, complete_causal_attribution_established=False)


def reconcile_public(roots, details, saved_groups):
    roots_by_key, cohorts = {}, defaultdict(list)
    for row in roots:
        if key(row) in roots_by_key:
            raise ValueError("duplicate numeric root")
        roots_by_key[key(row)] = row
        cohorts[group(row)].append(row)
    detail_keys = [key(row) for row in details]
    retained_keys = {key(row) for row in roots if row["retention_reasons"]}
    if len(detail_keys) != len(set(detail_keys)) or set(detail_keys) != retained_keys:
        raise ValueError("retained details missing, duplicated or unplanned")
    groups, seen = [], set()
    for saved in saved_groups:
        identity = {field: saved[field] for field in IDENTITY[:-1]}
        checked_identity({**identity, "attempt_index": 0})
        which = group(identity)
        if which not in cohorts or which in seen:
            raise ValueError("missing/duplicate/unexpected diagnostic group")
        seen.add(which)
        cohort = cohorts[which]
        values = [row["elapsed_ns"] for row in cohort]
        computed = dict(count=len(cohort), p50_ms=quantile(values, .5)/1e6,
                        p95_ms=quantile(values, .95)/1e6, p99_ms=quantile(values, .99)/1e6,
                        max_ms=max(values)/1e6)
        computed.update({field.removesuffix("_ns") + "_mean_ms": sum(row[field] for row in cohort)/len(cohort)/1e6
                         for field in MEAN_FIELDS})
        required = set((*IDENTITY[:-1], *computed, "paired_traced_minus_reference_p50_ms",
                        "paired_traced_minus_reference_p95_ms", "tracing_overhead_isolated"))
        if (set(saved) != required or type(saved["count"]) is not int
                or any(saved[field] != value for field, value in computed.items())):
            raise ValueError("saved group quantiles/means do not match numeric ledger")
        for field in ("paired_traced_minus_reference_p50_ms", "paired_traced_minus_reference_p95_ms"):
            if type(saved[field]) not in (int, float) or not math.isfinite(saved[field]):
                raise ValueError("invalid paired observed difference")
        if saved["tracing_overhead_isolated"] is not False:
            raise ValueError("fixed-order contrast cannot claim isolated tracing overhead")
        maximum, tail = max(values), quantile(values, .99)
        for row in cohort:
            expected = []
            if row["elapsed_ns"] > 20_000_000:
                expected.append(FLAGS[0])
            if row["elapsed_ns"] > 100_000_000:
                expected.append(FLAGS[1])
            if row["elapsed_ns"] >= tail:
                expected.append(FLAGS[2])
            if row["elapsed_ns"] == maximum:
                expected.append(FLAGS[3])
            if row["retention_reasons"] != expected:
                raise ValueError("predeclared retention/maxima do not reconcile")
        groups.append({**identity, **computed,
                       **{field: saved[field] for field in ("paired_traced_minus_reference_p50_ms", "paired_traced_minus_reference_p95_ms")},
                       "tracing_overhead_isolated": False})
    if seen != set(cohorts):
        raise ValueError("some diagnostic groups are omitted")
    large = [row for row in roots if row["elapsed_ns"] > 100_000_000]
    summary = dict(application_root_count=len(roots), retained_root_count=len(details), group_count=len(groups),
                   large_root_count_above_100ms=len(large), roots_fully_schedule_covered=sum(row["schedule_fully_covered"] for row in roots),
                   roots_with_gc_overlap=sum(row["gc_wall_union_ns"] > 0 for row in roots),
                   roots_with_ready_delay=sum(row["off_ready_at_switchout_ns"] + row["off_ready_after_event_ns"] > 0 for row in roots),
                   roots_with_scoped_file_operation_overlap=sum(row["file_operation_overlap_ns"] > 0 for row in roots),
                   roots_with_scoped_disk_operation_overlap=sum(row["disk_operation_overlap_ns"] > 0 for row in roots),
                   roots_with_scoped_hard_fault_overlap=sum(row["hard_fault_interval_overlap_ns"] > 0 for row in roots),
                   large_roots_with_gc_overlap=sum(row["gc_wall_union_ns"] > 0 for row in large),
                   largest_root_elapsed_ms=max(row["elapsed_ns"] for row in roots)/1e6,
                   disjoint_root_partitions_reconciled=True, all_group_maxima_retained=True,
                   tracing_overhead_isolated=False, complete_causal_attribution_established=False)
    return summary, groups, large
