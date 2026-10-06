"""Serial research instrumentation; never alters admission or window policy.

Only stage names, durations, GC events and exception booleans are collected.
Arguments, return objects, credentials, keys, tags and responses are not logged.
Class/function wrappers are temporary process-wide patches: no concurrent use.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import contextmanager, ExitStack
from copy import deepcopy
from dataclasses import asdict
from functools import wraps
import gc
import math
from threading import get_ident
import time
from unittest.mock import patch

from puf_snn import pipeline_v2
from puf_snn.auth import sender as sender_module, verifier as verifier_module
from puf_snn.auth.audit import AuditRecorder
from puf_snn.auth.credential_verifier import CredentialAdmissionService
from puf_snn.auth.sender import Sender
from puf_snn.auth.session import Failure
from puf_snn.auth.verifier import Verifier
from puf_snn.frozen_pipeline import bad_tag_packet, FrozenModelBundle
from puf_snn.integration import processed_record_to_wire_window
from puf_snn.pipeline_v2 import ModelCallCounts


CONDITIONS = (
    ("logistic_motion_logistic_anomaly", "logistic_regression_seed_7_storage_refit", "anomaly_logistic_regression_seed6007"),
    ("logistic_motion_forest_anomaly", "logistic_regression_seed_7_storage_refit", "anomaly_random_forest_seed6007"),
    ("forest_motion_forest_anomaly", "random_forest_seed_7_storage_refit", "anomaly_random_forest_seed6007"),
    ("snn32_seed7_forest_anomaly", "snn_32_seed_7", "anomaly_random_forest_seed6007"),
    ("snn32_seed17_forest_anomaly", "snn_32_seed_17", "anomaly_random_forest_seed6007"),
    ("snn32_seed27_forest_anomaly", "snn_32_seed_27", "anomaly_random_forest_seed6007"),
)
ACCEPTED_PATHS = frozenset({"fresh_to_first_window", "post_window_recurring",
                          "valid_receiver_after_bad_tag", "post_window_after_refusals"})
REJECTED_PATHS = frozenset({"bad_tag_receiver", "exact_replay_receiver", "malformed_json_receiver",
                          "pre_tag_quality_refusal"})


def validate_timing_config(config):
    fixed = {"config_version": "week6-fresh-v2-timing-v1", "frozen_config": "configs/week6_smoke.json",
             "source_split": "test", "source_selection": "all_600_sorted_device_label_window",
             "warmup_attempts_per_condition": 20, "measured_attempts_per_condition": 600,
             "batch_size": 1, "native_threads": 1, "gc_enabled": True,
             "post_window_p95_target_ms": 20, "outlier_absolute_ms": 20}
    if set(config) != set(fixed) | {"conditions"} or any(config.get(k) != v or type(config.get(k)) is not type(v)
                                                        for k, v in fixed.items()):
        raise ValueError("timing protocol is fixed; do not silently change sample sizes or conditions")
    expected = [dict(name=name, motion=motion, anomaly=anomaly) for name, motion, anomaly in CONDITIONS]
    if config["conditions"] != expected:
        raise ValueError("model/detector choices must be predeclared, not selected from timing results")


def select_timing_sources(records):
    """No inference, amplitude filtering, PUF outcome or class balancing by result."""
    test = sorted((r for r in records if r["split"] == "test"),
                  key=lambda r: (r["device_id"], r["label"], r["window_id"]))
    validation = sorted((r for r in records if r["split"] == "validation"),
                        key=lambda r: (r["device_id"], r["label"], r["window_id"]))
    for rows in (test, validation):
        if len(rows) != 600 or len({r["window_id"] for r in rows}) != 600:
            raise ValueError("timing requires the unchanged complete 600-window splits")
        counts = Counter((r["device_id"], r["label"]) for r in rows)
        if len(counts) != 30 or set(counts.values()) != {20}:
            raise ValueError("expected six fixed devices by five classes by twenty windows")
    if {r["window_id"] for r in test} & {r["window_id"] for r in validation}:
        raise ValueError("warmup and measured source windows overlap")
    return test, validation[:20]


def one_model_bundle(bundle, condition):
    """Reference saved models; no fit, copy of weights, or threshold change."""
    return FrozenModelBundle({condition["motion"]: bundle.motion[condition["motion"]]},
                             {condition["anomaly"]: bundle.detectors[condition["anomaly"]]},
                             bundle.artifact_hashes)


class TimingCapture:
    def __init__(self, wall_clock=time.perf_counter_ns, cpu_clock=time.thread_time_ns):
        self.wall_clock, self.cpu_clock = wall_clock, cpu_clock
        self.active = False
        self.last_trace = None

    @contextmanager
    def span(self, stage):
        if not self.active:
            yield
            return
        if get_ident() != self.owner:
            raise RuntimeError("timing wrappers require single-threaded serial orchestration")
        ordinal = len(self.spans)
        row = {"id": ordinal, "parent_id": self.stack[-1] if self.stack else None, "stage": stage}
        self.spans.append(row)
        self.stack.append(ordinal)
        start = self.wall_clock()
        cpu = self.cpu_clock()
        failed = False
        try:
            yield
        except BaseException:
            failed = True
            raise
        finally:
            cpu_elapsed = self.cpu_clock() - cpu
            elapsed = self.wall_clock() - start
            self.stack.pop()
            row.update(start_ns=start - self.origin, wall_ns=elapsed, thread_cpu_ns=cpu_elapsed,
                       wall_minus_thread_cpu_ns=max(0, elapsed - cpu_elapsed), exception=failed)

    def wrap(self, stage, function):
        @wraps(function)
        def measured(*args, **kwargs):
            with self.span(stage):
                return function(*args, **kwargs)
        return measured

    def _gc_event(self, phase, info):
        now = self.wall_clock() - self.origin
        generation = info["generation"]
        if phase == "start":
            self.gc_starts[generation] = now
        elif phase == "stop":
            self.gc_events.append({"generation": generation, "start_ns": self.gc_starts.pop(generation, 0),
                                   "end_ns": now, "collected": info.get("collected", 0),
                                   "uncollectable": info.get("uncollectable", 0)})

    def measure(self, path, action):
        if self.active:
            raise RuntimeError("outer measurements cannot overlap")
        self.owner = get_ident()
        self.spans, self.stack, self.gc_events, self.gc_starts = [], [], [], {}
        self.origin = self.wall_clock()
        self.active = True
        gc.callbacks.append(self._gc_event)
        try:
            with self.span(path):
                return action()
        finally:
            self.active = False
            gc.callbacks.remove(self._gc_event)
            self.last_trace = {"path": path, "spans": self.spans, "gc_events": self.gc_events,
                               "gc_spanning_trace_end": sorted(self.gc_starts),
                               "elapsed_ns": self.spans[0]["wall_ns"],
                               "thread_cpu_ns": self.spans[0]["thread_cpu_ns"]}


@contextmanager
def instrument_pipeline(capture):
    """Wrap existing operations unchanged, restoring even when a run raises.

    The current verifier's public authentication call includes sequence checking,
    lock wait and state publication. These are NOT falsely labeled disjoint spans.
    Audit calls are nested; commit alone is not the full audit cost.
    """
    methods = (
        (pipeline_v2, "reconstruct", "reconstruction"),
        (pipeline_v2, "processed_record_to_wire_window", "binary32_adapter"),
        (Sender, "begin_attempt", "sender_admission_and_request"),
        (Sender, "answer_challenge", "sender_confirmation"),
        (Sender, "finish_session", "sender_activation"),
        (Sender, "seal_window", "sender_seal_total"),
        (Verifier, "begin_session", "receiver_challenge"),
        (Verifier, "confirm_session", "receiver_confirmation"),
        (Verifier, "verify_window", "verifier_authentication_total"),
        (Verifier, "release_accepted", "accepted_release_and_consumers"),
        (CredentialAdmissionService, "verify", "independent_credential_verification"),
        (CredentialAdmissionService, "authorize", "local_authorization_including_verification"),
        (CredentialAdmissionService, "bind_request", "local_request_binding"),
        (CredentialAdmissionService, "consume", "receiver_local_admission"),
        (CredentialAdmissionService, "bind_challenge", "local_challenge_binding"),
        (CredentialAdmissionService, "claim_candidate", "sender_local_admission_claim"),
        (sender_module, "encode_window", "serialization_including_quality"),
        (sender_module, "window_tag", "window_hmac_generation"),
        (verifier_module, "parse_envelope", "envelope_and_binary_parser"),
        (verifier_module, "window_tag", "window_hmac_verification_calculation"),
        (verifier_module, "validate_quality", "verifier_quality_check"),
    )
    with ExitStack() as stack:
        for owner, name, stage in methods:
            stack.enter_context(patch.object(owner, name, capture.wrap(stage, getattr(owner, name))))
        for name in ("record", "prepare", "commit"):
            original = getattr(AuditRecorder, name)

            def audit_call(self, *args, _original=original, _name=name, **kwargs):
                with capture.span(f"{self.origin}_audit_{_name}"):
                    return _original(self, *args, **kwargs)

            stack.enter_context(patch.object(AuditRecorder, name, audit_call))
        yield


def run_timed_attempt(pipeline, source, read_response, attempt_id, capture, emit):
    """One natural admission attempt, then short paired state controls if active.

    Evidence emission, status assertions, packet mutation, copying the quality
    control and housekeeping are outside each outer timing span. The first
    full-window call is INSIDE the fresh outer measurement, not separately run.
    """
    def fresh():
        attempt = capture.wrap("admission_total", pipeline.establish)(
            capture.wrap("response_generation_simulator", read_response), attempt_id)
        window = None
        if attempt.decision == "accept":
            window = capture.wrap("first_post_window_total", pipeline.process_record)(source)
        return attempt, window

    attempt, first = capture.measure("fresh_to_first_window", fresh)
    trace = capture.last_trace
    trace.update(decision=attempt.decision, stage=attempt.stage, reason=attempt.reason,
                 admission=asdict(attempt), read_count=1,
                 sender_kdf_ns=list(pipeline.sender.kdf_timings_ns),
                 verifier_kdf_ns=list(pipeline.verifier.kdf_timings_ns))
    if attempt.decision == "reject":
        if pipeline.calls != ModelCallCounts() or pipeline.verifier.active_session_ids:
            raise RuntimeError("failed admission released inference or an active session")
        trace["model_calls"] = asdict(pipeline.calls)
        emit(trace)
        return attempt
    if (first is None or first.decision != "accept" or first.sequence_number != 0
            or pipeline.calls != ModelCallCounts(1, 1, 1)):
        raise RuntimeError("fresh accepted session did not deliver its first window once")
    trace.update(decision=first.decision, stage=first.stage, reason=first.reason,
                 event_id=first.event_id, model_calls=asdict(pipeline.calls))
    emit(trace)
    event_ids = {first.event_id}

    def window_measure(path, action, expected, *, reason=None):
        before_calls = pipeline.calls
        before = pipeline.verifier.session_status(pipeline.sender.session_id)
        before_send = pipeline.sender.next_to_send
        result = capture.measure(path, action)
        after = pipeline.verifier.session_status(pipeline.sender.session_id)
        if result.decision != expected or (reason and result.reason != reason):
            raise RuntimeError(f"unexpected functional result for {path}")
        if expected == "reject":
            if (pipeline.calls != before_calls or after != before
                    or pipeline.sender.next_to_send != before_send):
                raise RuntimeError("rejection changed inference or sequence state")
        else:
            if (pipeline.calls != ModelCallCounts(before_calls.preprocessing + 1, before_calls.motion + 1,
                                                 before_calls.anomaly + 1)
                    or after.accepted_count != before.accepted_count + 1
                    or after.last_accepted != result.sequence_number or result.event_id in event_ids):
                raise RuntimeError("accepted delivery/state/callback accounting failed")
            event_ids.add(result.event_id)
        row = capture.last_trace
        row.update(decision=result.decision, stage=result.stage, reason=result.reason, event_id=result.event_id,
                   sequence_number=result.sequence_number,
                   model_calls={k: asdict(pipeline.calls)[k] - asdict(before_calls)[k] for k in asdict(before_calls)},
                   last_accepted_before=before.last_accepted, last_accepted_after=after.last_accepted)
        emit(row)

    window_measure("post_window_recurring", lambda: pipeline.process_record(source), "accept")
    packet = pipeline.sender.seal_window(processed_record_to_wire_window(source))
    if isinstance(packet, Failure):
        raise RuntimeError("control-packet creation failed outside timed span")
    changed = bad_tag_packet(packet)
    window_measure("bad_tag_receiver", lambda: pipeline.process_envelope(changed), "reject", reason="invalid_tag")
    window_measure("valid_receiver_after_bad_tag", lambda: pipeline.process_envelope(packet), "accept")
    window_measure("exact_replay_receiver", lambda: pipeline.process_envelope(packet), "reject")
    window_measure("malformed_json_receiver", lambda: pipeline.process_envelope(b"{"), "reject")
    low = deepcopy(source)
    for index, sample in enumerate(low["samples"]):
        sample["tracking_valid"] = index < 113
    window_measure("pre_tag_quality_refusal", lambda: pipeline.process_record(low), "reject",
                   reason="data_quality_failure")
    window_measure("post_window_after_refusals", lambda: pipeline.process_record(source), "accept")
    if (pipeline.calls != ModelCallCounts(4, 4, 4) or len(pipeline.consumed_event_ids) != 4
            or set(pipeline.consumed_event_ids) != event_ids or pipeline.sender.incomplete or pipeline.verifier.incomplete):
        raise RuntimeError("final at-most-once/state/audit control reconciliation failed")
    return attempt


def quantile(values, fraction):
    ordered = sorted(values)
    if not ordered or not 0 <= fraction <= 1:
        raise ValueError("quantile needs observations and a fraction in [0, 1]")
    position = fraction * (len(ordered) - 1)
    low = math.floor(position)
    return ordered[low] + (ordered[min(low + 1, len(ordered) - 1)] - ordered[low]) * (position - low)


def latency_statistics(values):
    values = list(values)
    if any(type(v) is not int or v < 0 for v in values):
        raise ValueError("timings must be nonnegative integer nanoseconds")
    if not values:
        return {"count": 0, "p50_ms": None, "p95_ms": None, "p99_ms": None, "max_ms": None}
    return {"count": len(values), "p50_ms": quantile(values, .5) / 1e6,
            "p95_ms": quantile(values, .95) / 1e6, "p99_ms": quantile(values, .99) / 1e6,
            "max_ms": max(values) / 1e6}


def summarize_traces(traces):
    """Keep phases/outcomes separate; repeated nested calls sum WITHIN a trace.

    Different stages overlap. Their percentiles are never added to derive totals.
    """
    roots, stages = defaultdict(list), defaultdict(list)
    for trace in traces:
        key = (trace["condition"], trace["phase"], trace["path"], trace["decision"], trace["reason"])
        roots[key].append(trace["elapsed_ns"])
        totals = Counter()
        for span in trace["spans"][1:]:
            totals[span["stage"]] += span["wall_ns"]
        for stage, elapsed in totals.items():
            stages[(*key, stage)].append(elapsed)
    def rows(groups, include_stage=False):
        result = []
        for key, values in sorted(groups.items()):
            row = dict(zip(("condition", "phase", "path", "decision", "reason", "stage"), key))
            row.update(latency_statistics(values))
            result.append(row)
        return result
    return {"units": "ms", "quantile_method": "linear interpolation at q*(n-1)",
            "root_paths": rows(roots), "nested_stages": rows(stages, True)}


def outlier_diagnosis(trace):
    wall, cpu = trace["elapsed_ns"], trace["thread_cpu_ns"]
    root_start = trace["spans"][0]["start_ns"]
    gc_ns = sum(max(0, min(event["end_ns"], root_start + wall) - max(event["start_ns"], root_start))
                for event in trace["gc_events"])
    gap = max(0, wall - cpu)
    observations = []
    if gc_ns:
        observations.append("gc_overlap_observed_not_proof_of_sole_cause")
    if gap > max(1_000_000, wall // 4):
        observations.append("wall_thread_cpu_gap_wait_or_other_thread_work_or_descheduling_not_resolved")
    if trace["phase"] == "condition_first_use":
        observations.append("condition_first_use_possible_backend_or_cache_overhead_not_isolated")
    reconstruction = sum(s["wall_ns"] for s in trace["spans"] if s["stage"] == "reconstruction")
    if reconstruction > 20_000_000:
        observations.append("large_elapsed_time_observed_inside_reconstruction")
    return {"gc_overlap_ns": gc_ns, "wall_minus_thread_cpu_ns": gap, "observations": observations,
            "largest_nested_spans": sorted(trace["spans"][1:], key=lambda s: s["wall_ns"], reverse=True)[:5],
            "causal_attribution": "unresolved; stage location and overlap are observations, not causal proof",
            "unmeasured_causes": ["allocation", "OS scheduling", "CPU frequency/power transitions",
                                   "cache effects", "external contention"],
            "disk_and_progress_io_inside_span": False}


def select_outliers(traces, absolute_ms=20):
    groups = defaultdict(list)
    for trace in traces:
        groups[(trace["condition"], trace["phase"], trace["path"], trace["decision"], trace["reason"])].append(trace)
    result = []
    for rows in groups.values():
        cutoff = quantile([r["elapsed_ns"] for r in rows], .99)
        for row in rows:
            if row["elapsed_ns"] >= cutoff or row["elapsed_ns"] > absolute_ms * 1e6:
                result.append({"trace": row, "diagnosis": outlier_diagnosis(row)})
    return result


def reconcile_timing(traces, conditions, measured=600, warmup=20):
    accepted, refused = Counter(), Counter()
    fresh = {}
    by_attempt = defaultdict(Counter)
    for trace in traces:
        key = (trace["condition"], trace["phase"], trace["attempt_index"])
        if trace["path"] == "fresh_to_first_window":
            if key in fresh or trace["read_count"] != 1:
                raise ValueError("duplicate admission or response-read accounting")
            fresh[key] = trace
        by_attempt[key][trace["path"]] += 1
        if trace["path"] in REJECTED_PATHS and trace["decision"] != "reject":
            raise ValueError("a refusal control has an accepted decision")
        if trace["path"] in ACCEPTED_PATHS - {"fresh_to_first_window"} and trace["decision"] != "accept":
            raise ValueError("a valid continuation was rejected")
        calls = trace["model_calls"]
        if trace["decision"] == "reject" and any(calls.values()):
            raise ValueError("rejection invoked a consumer")
        if trace["decision"] == "accept" and calls != {"preprocessing": 1, "motion": 1, "anomaly": 1}:
            raise ValueError("acceptance did not invoke both models exactly once")
    for condition in conditions:
        name = condition["name"]
        for phase, expected in (("measured", measured), ("warmup", warmup - 1), ("condition_first_use", 1)):
            selected = [(key, row) for key, row in fresh.items() if key[:2] == (name, phase)]
            if len(selected) != expected or {key[2] for key, _ in selected} != (
                    set(range(measured)) if phase == "measured" else set(range(1, warmup)) if phase == "warmup" else {0}):
                raise ValueError("not every planned admission attempt is accounted for")
            for key, row in selected:
                expected_paths = ACCEPTED_PATHS | REJECTED_PATHS if row["decision"] == "accept" else {"fresh_to_first_window"}
                actual = {path for path, count in by_attempt[key].items() if count == 1}
                if actual != expected_paths or sum(by_attempt[key].values()) != len(expected_paths):
                    raise ValueError("per-attempt timing/control paths do not reconcile")
                if row["decision"] == "accept":
                    accepted[(name, phase)] += 1
                else:
                    refused[(name, phase, row["stage"], row["reason"])] += 1
    if len(fresh) != len(conditions) * (measured + warmup):
        raise ValueError("unexpected condition or phase in admission evidence")
    if set(by_attempt) != set(fresh):
        raise ValueError("window traces exist without their planned admission attempt")
    # Paired read streams must produce identical error/outcome evidence across
    # conditions; differences are not silently hidden behind aggregate latency.
    signatures = defaultdict(set)
    for (_, phase, index), row in fresh.items():
        signatures[(phase, index)].add((row["source_window_id"], row["selected_bit_error_count"],
                                        row["admission"]["decision"], row["admission"]["reason"]))
    if any(len(values) != 1 for values in signatures.values()):
        raise ValueError("paired response/read/admission evidence differs across model conditions")
    return {"fresh_attempt_count": len(fresh), "response_read_count": len(fresh),
            "trace_count": len(traces), "accepted_by_condition_phase": [
                dict(condition=k[0], phase=k[1], count=v) for k, v in sorted(accepted.items())],
            "refused_by_condition_phase_reason": [dict(condition=k[0], phase=k[1], stage=k[2], reason=k[3], count=v)
                                                   for k, v in sorted(refused.items())],
            "rejected_window_model_calls": 0, "paired_admission_signatures_match": True}
