"""Fixed serial cohort bridge for a separate private traced diagnostic.

Importing this file never records, loads models, runs inference or changes GC.
The existing timing worker is reused without editing authentication or models.
"""

from __future__ import annotations

from contextlib import contextmanager
import ctypes
import json
import os
from pathlib import Path
import re
import threading

from puf_snn.windows_trace import BracketedMarkers


FIXED_CONFIG = {
    "config_version": "week6-windows-traced-workload-v1",
    "base_config": "configs/week6_outlier_experiment.json",
    "base_config_sha256": "60f27cdca6807ed42f25cdeea36bef93185c11fd66417bc28082f1a09dfec24b",
    "base_runner": "src/python/scripts/run_week6_outlier_experiment.py",
    "base_runner_sha256": "964943c63765f2f738e3b270bb4622e8e53c9d67a32ba60383328f6fb7321d57",
    "profile": "configs/week6_windows_trace.wprp",
    "profile_sha256": "ecffd956fb720706aa965dd6e94c63bd33470fe63d643c7037c2f56088a9eb21",
    "block": 0, "mode": "nested_stream_gc_on",
    "worker_order": ["reference", "traced"],
    "planned_attempts_per_worker": 540, "planned_marker_count": 27,
    "power_requirement": "ac", "maximum_clock_uncertainty_ns": 100000,
}
LIMITATION = (
    "Separate serial Windows tracing diagnostic on fixed synthetic sources and noisy simulated "
    "PUF reads; not new held-out accuracy, formal Tier-1/FRR evaluation, a performance-target run "
    "or a replacement for historical timing. Reference precedes traced in fresh processes: "
    "tracing/marker overhead, ordering, cache, thermal and background differences are confounded. "
    "GC remains enabled. Clock/loss validation alone establishes no OS cause. New tracing cannot "
    "retroactively prove causes for old untraced events. Raw ETL and system-wide exports stay private.")


def validate_trace_config(config):
    if json.dumps(config, sort_keys=True) != json.dumps(FIXED_CONFIG, sort_keys=True):
        raise ValueError("traced diagnostic design is fixed; no result-dependent tuning")


def selected_job(base_config):
    from puf_snn.outlier_experiment import build_jobs
    jobs = [job for job in build_jobs(base_config)
            if job.get("block") == FIXED_CONFIG["block"] and job.get("mode") == FIXED_CONFIG["mode"]]
    if len(jobs) != 1:
        raise ValueError("fixed reference/traced job absent or duplicated")
    return jobs[0]


def private_worker_path(output, repository, private_root):
    """Only fresh immediate reference/traced children of a unique private run."""
    raw, scope, repo = Path(output), Path(private_root).resolve(), Path(repository).resolve()
    if not raw.is_absolute() or ".." in raw.parts:
        raise ValueError("private worker output requires a canonical absolute path")
    resolved = raw.resolve()
    if (raw != resolved or resolved.name not in ("reference", "traced")
            or not re.fullmatch(r"week6-model-trace-[0-9a-f]{32}", resolved.parent.name)
            or resolved.parent.parent != scope or resolved.is_relative_to(repo)
            or not resolved.parent.is_dir() or resolved.exists()):
        raise ValueError("choose a fresh private worker destination outside Git")
    for parent in (scope, resolved.parent):
        if parent.is_symlink() or getattr(parent.stat(), "st_file_attributes", 0) & 0x400:
            raise ValueError("private parent is a link or junction")
    return resolved


def ac_power_status(api=None):
    """Read current AC status; never change power/frequency settings."""
    class Status(ctypes.Structure):
        _fields_ = [("ac", ctypes.c_ubyte), ("flags", ctypes.c_ubyte),
                    ("percent", ctypes.c_ubyte), ("reserved", ctypes.c_ubyte),
                    ("life", ctypes.c_uint32), ("full_life", ctypes.c_uint32)]
    if api is None:
        if os.name != "nt":
            raise RuntimeError("power check requires Windows")
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.GetSystemPowerStatus.argtypes = [ctypes.POINTER(Status)]
        api.GetSystemPowerStatus.restype = ctypes.c_int
    status = Status()
    if not api.GetSystemPowerStatus(ctypes.byref(status)) or status.ac != 1:
        raise RuntimeError("AC power absent or unconfirmed; preserve partial evidence")
    return dict(ac_online=True, battery_percent=None if status.percent == 255 else int(status.percent),
                cpu_frequency_core_affinity_and_thermal_state_controlled=False)


class MarkerJournal(BracketedMarkers):
    """Flush public marker brackets BETWEEN roots; preserve partial writes."""

    def __init__(self, writer, evidence, **kwargs):
        super().__init__(writer, **kwargs)
        self.evidence = evidence

    def mark(self, label, capture=None, *, condition=None, cohort=None):
        if (condition is None) != (cohort is None) or (cohort is not None and cohort not in ("warmup", "measured")):
            raise ValueError("marker context must name one planned condition/cohort")
        row = super().mark(label, capture)
        if condition is not None:
            row.update(condition=condition, cohort=cohort)
            self.rows[-1].update(condition=condition, cohort=cohort)
        self.evidence.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
        self.evidence.flush()
        return row


@contextmanager
def cohort_marker_bridge(runner, markers, job):
    """Temporary serial wrapper around the UNCHANGED original run_condition.

    No per-root marker or policy change. Always restore the original function,
    including exceptions. Preserve a missing end marker on failed cohorts.
    """
    original = runner.run_condition
    if getattr(original, "_week6_marker_bridge", False):
        raise RuntimeError("cohort marker bridges cannot overlap")
    owner_thread, completed = threading.get_ident(), []
    expected = [(condition["name"], cohort) for condition in job["condition_order"]
                for cohort in ("warmup", "measured")]

    def wrapped(factory, condition, sources, materials, read_domain, block, capture, evidence, retention, cohort):
        identity = (condition["name"], cohort)
        if (threading.get_ident() != owner_thread or capture.active or block != job["block"]
                or len(completed) >= len(expected) or expected[len(completed)] != identity
                or len(sources) != (30 if cohort == "warmup" else 60)):
            raise RuntimeError("cohort boundary differs or overlaps a root/serial worker")
        if markers is not None:
            markers.mark("condition_begin", capture, condition=identity[0], cohort=cohort)
        result = original(factory, condition, sources, materials, read_domain, block,
                          capture, evidence, retention, cohort)
        if capture.active:
            raise RuntimeError("cohort returned with an active root")
        if markers is not None:
            markers.mark("condition_end", capture, condition=identity[0], cohort=cohort)
        completed.append(identity)
        return result

    wrapped._week6_marker_bridge = True
    runner.run_condition = wrapped
    try:
        yield
        if completed != expected:
            raise RuntimeError("not all twelve planned cohorts completed")
    finally:
        runner.run_condition = original


def validate_marker_coverage(markers, traces, job):
    """Bind every retained root to its own cohort and public PID/TID bracket."""
    expected_contexts = [(condition["name"], cohort) for condition in job["condition_order"]
                         for cohort in ("warmup", "measured")]
    expected_labels = ["capture_begin", "inputs_verified"] + [
        label for _ in expected_contexts for label in ("condition_begin", "condition_end")] + ["capture_end"]
    if (len(markers) != 27 or [row["label"] for row in markers] != expected_labels
            or not traces):
        raise ValueError("marker phases/count or root inventory differs")
    identities, previous_after = set(), 0
    for index, row in enumerate(markers, 1):
        before, after = row["perf_before_ns"], row["perf_after_ns"]
        if (row["marker_index"] != index or row.get("write_succeeded") is not True
                or any(type(value) is not int for value in (before, after))
                or before <= 0 or after < before or before < previous_after):
            raise ValueError("marker order, success or clock bounds differ")
        identities.add((row["process_id"], row["native_thread_id"]))
        previous_after = after
    if len(identities) != 1 or any(type(v) is not int or v <= 0 for v in next(iter(identities))):
        raise ValueError("mixed or invalid marker process/thread identity")
    bounds = {}
    for index, context in enumerate(expected_contexts):
        begin, end = markers[2 + 2 * index:4 + 2 * index]
        if any((row.get("condition"), row.get("cohort")) != context for row in (begin, end)):
            raise ValueError("cohort marker context differs from fixed order")
        bounds[context] = (begin["perf_after_ns"], end["perf_before_ns"])
    roots_by_context = {context: [] for context in expected_contexts}
    for row in traces:
        phase = "warmup" if row["phase"] == "condition_first_use" else row["phase"]
        context = (row["condition"], phase)
        identity = (row["process_id"], row["native_thread_id"])
        start, end = row["clock_start_ns"], row["clock_end_ns"]
        if (context not in bounds or identity not in identities
                or any(type(value) is not int for value in (start, end, row["elapsed_ns"]))
                or end < start or end - start != row["elapsed_ns"]
                or not bounds[context][0] <= start <= end <= bounds[context][1]):
            raise ValueError("root clock/identity lies outside its planned cohort markers")
        roots_by_context[context].append((start, end))
    for roots in roots_by_context.values():
        ordered = sorted(roots)
        if not ordered or any(one[1] > two[0] for one, two in zip(ordered, ordered[1:])):
            raise ValueError("missing cohort roots or overlapping serial root timers")
    return dict(marker_count=27, root_count=len(traces), all_roots_within_markers=True,
                cohort_count=12, os_cause_established=False)
