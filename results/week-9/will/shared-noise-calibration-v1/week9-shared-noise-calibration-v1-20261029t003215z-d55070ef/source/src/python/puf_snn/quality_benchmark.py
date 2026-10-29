"""Fixed paired arithmetic experiment controls; no model fitting or policy change."""

from collections import Counter, defaultdict
from contextlib import contextmanager
from copy import deepcopy
import ctypes
from dataclasses import asdict
import gc
import hashlib
import json
import platform
import time
from unittest.mock import patch

import numpy as np

from puf_snn.auth import binary_window, sender as sender_module
from puf_snn.outlier_experiment import functional_signature, signed_delta_statistics
from puf_snn.pipeline_diagnostics import runtime_snapshot
from puf_snn.pipeline_timing import CONDITIONS, latency_statistics, reconcile_timing, select_timing_sources
from puf_snn.quality_dyadic import QUALITY_MODES
from puf_snn.stage_accounting import partition_trace


PRIMARY = tuple(dict(name=n, motion=m, anomaly=a) for n, m, a in (CONDITIONS[0], CONDITIONS[1], CONDITIONS[3]))
BASELINE_HASHES = {
    "src/python/puf_snn/auth/binary_window.py": "78159d6a8c8601b40ff0158f7d2ac4b85e2179b72ebeae0ea186bf70f408877e",
    "src/python/puf_snn/auth/verifier.py": "49f4e0946d4a54569be2746a7a0fa2c0feee587ee75351df9bd1c2062177944e",
    "src/python/puf_snn/quality_dyadic.py": "a3f71a79ab48941807a0ba75e99b67f7cebdaa0b81ba75d9f2ae9d8171a12947",
}


def fixed_config():
    return deepcopy(dict(config_version="week6-quality-benchmark-v1", frozen_config="configs/week6_smoke.json",
        modes=list(QUALITY_MODES), conditions=list(PRIMARY), blocks=2,
        measured_attempts_per_condition=120, warmup_attempts_per_condition=30,
        source_selection="first_four_sorted_test_windows_per_device_class",
        warmup_selection="first_sorted_validation_window_per_device_class",
        sustained_windows_per_condition=64, sustained_selection="first_64_test_windows_of_final_planned_device",
        native_threads=1, batch_size=1, gc_enabled=True, gc_thresholds=[2000, 10, 10],
        response_reads_per_admission=1, reconstruction="baseline_BCH_63_36_t5_32bit_pilot",
        read_domain="week6-quality-v1:6767:{block}:{device_index}:{cohort}:measurement",
        post_window_p95_target_ms=20, reference_source_hashes=BASELINE_HASHES))


def validate_config(config):
    if json.dumps(config, sort_keys=True) != json.dumps(fixed_config(), sort_keys=True):
        raise ValueError("fixed bounded experiment differs; do not tune modes/models/counts/GC after results")


def build_jobs(config):
    validate_config(config)
    jobs = []
    for block in range(2):
        # AB then BA: mode positions balanced; same condition order within a pair.
        modes = QUALITY_MODES if block == 0 else QUALITY_MODES[::-1]
        conditions = list(PRIMARY) if block == 0 else list(PRIMARY[::-1])
        for position, mode in enumerate(modes):
            jobs.append(dict(job_id=f"block-{block}-{mode}", block=block, position=position,
                             mode=mode, condition_order=conditions))
    return jobs


def select_sources(records):
    test, _ = select_timing_sources(records)
    validation = sorted((r for r in records if r["split"] == "validation"),
                        key=lambda r: (r["device_id"], r["label"], r["window_id"]))
    def first(rows, count):
        groups = defaultdict(list)
        for row in rows:
            groups[row["device_id"], row["label"]].append(row)
        return [r for key in sorted(groups) for r in groups[key][:count]]
    measured, warmup = first(test, 4), first(validation, 1)
    burst = [r for r in test if r["device_id"] == measured[-1]["device_id"]][:64]
    if (len(measured), len(warmup), len(burst)) != (120, 30, 64):
        raise ValueError("cohort does not match the predeclared selection")
    return measured, warmup, burst


def normal_gc_conditions(config):
    validate_config(config)
    wall, cpu = time.get_clock_info("perf_counter"), time.get_clock_info("thread_time")
    if not gc.isenabled() or list(gc.get_threshold()) != config["gc_thresholds"] or not wall.monotonic or wall.adjustable:
        raise ValueError("start with unchanged enabled GC and a monotonic non-adjustable wall timer")
    return dict(gc_enabled=True, gc_thresholds=list(gc.get_threshold()),
                wall_timer=wall.implementation, thread_cpu_timer=cpu.implementation,
                wall_resolution_seconds=wall.resolution, frequency_and_core_placement_controlled=False)


def process_memory():
    """Coarse numeric process snapshots, not allocation stacks or stage peaks."""
    if platform.system() != "Windows":
        return dict(status="unavailable_not_windows")
    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong)] + [
            (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
                "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = (ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong)
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return dict(status="unavailable_api_failure")
    return dict(status="collected", working_set_bytes=counters.WorkingSetSize,
                peak_working_set_bytes=counters.PeakWorkingSetSize, private_commit_bytes=counters.PrivateUsage,
                peak_commit_bytes=counters.PeakPagefileUsage, process_lifetime_peaks_not_stage_peaks=True)


def resource_snapshot(capture=None):
    return dict(python=runtime_snapshot(capture), process_memory=process_memory())


def array_fingerprint(value, shape):
    array = np.asarray(value, dtype="<f8")
    if array.shape != shape or not np.all(np.isfinite(array)):
        raise ValueError("unexpected public model-input shape or nonfinite value")
    return hashlib.sha256(array.tobytes(order="C")).hexdigest()


def wire_fingerprint(value):
    """Pair the SAME wire content except the deliberately fresh random session ID.

    Only the post-timer comparison copy has those 16 bytes neutralized. Actual
    transmitted/authenticated bytes, identifiers, sequence and HMAC are untouched.
    Parse first; no field other than that exact session ID is removed from the hash.
    """
    window = binary_window.parse_window(value)
    prefix = b"P3AW" + binary_window.V(2, 0) + binary_window.V(2, 0) + binary_window.V(1, 0) + b"\x01\x01\x20"
    offset = len(prefix) + 2 + len(binary_window.identifier(window.device_id))
    if value[offset:offset+16] != window.session_id:
        raise ValueError("comparison session-ID offset differs from the parsed header")
    return hashlib.sha256(value[:offset] + bytes(16) + value[offset+16:]).hexdigest()


class PublicLedger:
    """Hold references during a root; hash only PUBLIC inputs/outputs afterward.

    No credentials, keys, response bits, tags or full wire payloads are exported.
    Reference bookkeeping inside callbacks is observer cost in BOTH modes.
    """
    def __init__(self, capture):
        self.capture = capture
        self.pending = defaultdict(list)

    def observe(self, name, function):
        def callback(*args, **kwargs):
            result = function(*args, **kwargs)
            if self.capture.active:
                self.pending[name].append(result)
            return result
        return callback

    def finish(self, calls):
        if self.capture.active:
            raise RuntimeError("fingerprinting must stay outside root timers")
        if any(len(self.pending[name]) != calls[name] for name in ("preprocessing", "motion", "anomaly")):
            raise ValueError("input/output evidence disagrees with inference-call counts")
        inputs = [dict(motion_sha256=array_fingerprint(motion, (120, 7)),
                       anomaly_sha256=array_fingerprint(anomaly, (48,)))
                  for motion, anomaly in self.pending["preprocessing"]]
        result = dict(model_inputs=inputs, motion_outputs=self.pending["motion"],
                      anomaly_outputs=self.pending["anomaly"],
                      sender_payload_session_neutral_sha256=[wire_fingerprint(value) for value in self.pending["wire"]])
        json.dumps(result, sort_keys=True, allow_nan=False)
        self.pending = defaultdict(list)
        return result

    @contextmanager
    def observe_sender(self):
        # Before instrument_pipeline: same measured encode wrapper in both modes.
        with patch.object(sender_module, "encode_window", self.observe("wire", sender_module.encode_window)):
            yield


def sustained_burst(pipeline, sources, capture, emit, count=64):
    """Reuse the final PLANNED admission, never retry/select a successful one.

    Closed-loop wall time includes evidence emission and assertions between roots.
    Each direct root excludes that I/O. This is unpaced service capacity, not an
    arrival-rate/backpressure experiment or independently sampled classification.
    """
    if len(sources) != count or pipeline.sender.session_id is None:
        raise ValueError("sustained run requires the fixed cohort and an already active session")
    before = asdict(pipeline.calls)
    initial = pipeline.verifier.session_status(pipeline.sender.session_id)
    seen = set(pipeline.consumed_event_ids)
    start = time.perf_counter_ns()
    for index, source in enumerate(sources):
        previous = pipeline.verifier.session_status(pipeline.sender.session_id)
        result = capture.measure("post_window_recurring", lambda: pipeline.process_record(source))
        status = pipeline.verifier.session_status(pipeline.sender.session_id)
        if (result.decision != "accept" or result.event_id in seen
                or status.last_accepted != result.sequence_number
                or status.accepted_count != initial.accepted_count + index + 1
                or asdict(pipeline.calls) != {key: value + index + 1 for key, value in before.items()}):
            raise ValueError("sustained valid traffic did not advance/release exactly once")
        seen.add(result.event_id)
        row = capture.last_trace
        row.update(decision=result.decision, stage=result.stage, reason=result.reason,
                   sequence_number=result.sequence_number,
                   last_accepted_before=previous.last_accepted,
                   last_accepted_after=status.last_accepted,
                   model_calls={key: 1 for key in before})
        emit(row, source, index)
    elapsed = time.perf_counter_ns() - start
    return dict(planned_windows=count, completed_windows=count, closed_loop_wall_ns=elapsed,
                windows_per_second=count * 1e9 / elapsed, admission_included=False,
                evidence_io_assertions_and_observers_included=True, cleanup_included=False,
                source_windows_distinct=len({r["window_id"] for r in sources}),
                session_start_last_accepted=initial.last_accepted,
                session_end_last_accepted=status.last_accepted)


def validate_rows(rows, job, config):
    normal, bursts = [], []
    seen = set()
    for row in rows:
        key = tuple(row[k] for k in ("condition", "phase", "attempt_index", "path"))
        if key in seen or row["mode"] != job["mode"] or row["block"] != job["block"]:
            raise ValueError("duplicate trace or wrong worker identity")
        seen.add(key)
        partition_trace(row)
        if row["condition"] not in {c["name"] for c in job["condition_order"]}:
            raise ValueError("unknown model condition")
        expected_split = "validation" if row["phase"] in {"warmup", "condition_first_use"} else "test"
        if row["source_split"] != expected_split:
            raise ValueError("wrong source split")
        outputs = row["public_inference"]
        expected = int(row["decision"] == "accept")
        if any(len(outputs[name]) != expected for name in ("model_inputs", "motion_outputs", "anomaly_outputs")):
            raise ValueError("public inference inventory differs from root decision")
        if row["phase"] == "sustained":
            if row["path"] != "post_window_recurring" or row["decision"] != "accept" or row["model_calls"] != {
                    "preprocessing": 1, "motion": 1, "anomaly": 1}:
                raise ValueError("sustained path differs or invoked consumers incorrectly")
            expected_sequence = 0 if row["last_accepted_before"] is None else row["last_accepted_before"] + 1
            if row["last_accepted_after"] != expected_sequence:
                raise ValueError("sustained sequence did not advance exactly once")
            bursts.append(row)
        else:
            normal.append(row)
    result = reconcile_timing(normal, job["condition_order"],
        measured=config["measured_attempts_per_condition"], warmup=config["warmup_attempts_per_condition"])
    for condition in job["condition_order"]:
        name = condition["name"]
        final = next(row for row in normal if row["condition"] == name and row["phase"] == "measured"
                     and row["attempt_index"] == 119 and row["path"] == "fresh_to_first_window")
        selected = [row for row in bursts if row["condition"] == name]
        expected = 64 if final["decision"] == "accept" else 0
        if len(selected) != expected or {row["attempt_index"] for row in selected} != set(range(expected)):
            raise ValueError("burst must follow only the final planned admission; no retry or selective substitution")
    return dict(result, trace_count=len(rows), sustained_window_count=len(bursts),
                exclusive_partition_reconciled=True, public_input_output_inventory_reconciled=True)


def paired_rows(reference, candidate):
    def index(rows):
        result = {}
        for row in rows:
            key = tuple(row[k] for k in ("condition", "phase", "attempt_index", "path"))
            if key in result:
                raise ValueError("duplicate paired key")
            result[key] = row
        return result
    left, right = index(reference), index(candidate)
    if set(left) != set(right):
        raise ValueError("paired modes have different path/admission inventories")
    groups = defaultdict(list)
    for key in sorted(left):
        a, b = left[key], right[key]
        if (functional_signature(a) != functional_signature(b)
                or a["public_inference"] != b["public_inference"]):
            raise ValueError("paired public input bytes, predictions, decisions, calls or state differ")
        groups[(a["block"], a["condition"], a["phase"], a["path"], a["decision"], a["reason"])].append(
            b["elapsed_ns"] - a["elapsed_ns"])
    return [dict(zip(("block", "condition", "phase", "path", "decision", "reason"), key),
                 **signed_delta_statistics(values), direction="candidate_minus_reference",
                 independent_accuracy_or_FRR_samples=False) for key, values in sorted(groups.items())]


def cleanup(capture, ledger):
    if capture.active or any(ledger.pending.values()) or not gc.isenabled():
        raise ValueError("cleanup requires finished roots, empty public ledger and enabled GC")
    capture.last_trace = None
    before = resource_snapshot(capture)
    start, cpu = time.perf_counter_ns(), time.thread_time_ns()
    collected = gc.collect(2)
    result = dict(wall_ns=time.perf_counter_ns()-start, thread_cpu_ns=time.thread_time_ns()-cpu,
                  generation=2, collected_objects=collected, outside_window_timers=True,
                  automatic_collection_was_not_deferred=True, includes_free_list_effects=True)
    return dict(before=before, cleanup=result, after=resource_snapshot(capture))
