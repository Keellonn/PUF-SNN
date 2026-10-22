"""Observer/GC controls for a separate serial research diagnostic.

This module does not run an experiment, change authentication policy, load
models, or replace the original timing collector. Automatic-GC deferral is a
bounded counterfactual, never the reference performance configuration.
"""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
import gc
import os
import sys
from threading import get_ident, get_native_id
import time

from puf_snn.pipeline_timing import TimingCapture, instrument_pipeline


@dataclass(frozen=True)
class DiagnosticMode:
    name: str
    nested_spans: bool
    retain_full_traces: bool
    automatic_gc: bool


MODES = (
    DiagnosticMode("nested_retained_gc_on", True, True, True),
    DiagnosticMode("nested_stream_gc_on", True, False, True),
    DiagnosticMode("outer_stream_gc_on", False, False, True),
    DiagnosticMode("nested_stream_gc_deferred", True, False, False),
)


def diagnostic_mode(name):
    for mode in MODES:
        if name == mode.name:
            return mode
    raise ValueError("unknown predeclared diagnostic mode")


def checked_mode(mode):
    if (type(mode) is not DiagnosticMode or mode not in MODES
            or any(type(value) is not bool for value in
                   (mode.nested_spans, mode.retain_full_traces, mode.automatic_gc))):
        raise ValueError("use an unchanged predeclared diagnostic mode")
    return mode


def annotate_trace(capture):
    """Public identifiers and absolute clock bounds; outside the root timer.

    Absolute perf-counter times help a later OS trace correlate this process
    and native thread. They alone do not establish scheduling or cache causes.
    No argument, response, credential, key, tag or exception text is exported.
    """
    row = capture.last_trace
    if row is not None:
        start = capture.origin + row["spans"][0]["start_ns"]
        row.update(process_id=os.getpid(), native_thread_id=get_native_id(),
                   clock_start_ns=start, clock_end_ns=start + row["elapsed_ns"],
                   observer="nested" if capture.nested_spans else "outer_only")


class NestedDiagnosticCapture(TimingCapture):
    """Original nested observer, with public correlation fields added afterward."""
    nested_spans = True

    def measure(self, path, action):
        if self.active:
            raise RuntimeError("outer measurements cannot overlap")
        try:
            return super().measure(path, action)
        finally:
            annotate_trace(self)


class OuterDiagnosticCapture:
    """One root timer and the same GC-overlap concept, without nested wrappers.

    This is lower instrumentation, NOT uninstrumented application timing.
    GC callbacks, clocks and the diagnostic orchestration still add overhead.
    """
    nested_spans = False

    def __init__(self, wall_clock=time.perf_counter_ns, cpu_clock=time.thread_time_ns):
        self.wall_clock, self.cpu_clock = wall_clock, cpu_clock
        self.active = False
        self.last_trace = None

    @contextmanager
    def span(self, stage):
        if self.active and get_ident() != self.owner:
            raise RuntimeError("diagnostic orchestration must be serial")
        yield

    def wrap(self, stage, function):
        # Returning the original function avoids even an inactive nested wrapper.
        return function

    def _gc_event(self, phase, info):
        now = self.wall_clock() - self.origin
        generation = info["generation"]
        if phase == "start":
            self.gc_starts[generation] = now
        elif phase == "stop":
            self.gc_events.append({"generation": generation,
                                   "start_ns": self.gc_starts.pop(generation, 0),
                                   "end_ns": now, "collected": info.get("collected", 0),
                                   "uncollectable": info.get("uncollectable", 0)})

    def measure(self, path, action):
        if self.active:
            raise RuntimeError("outer measurements cannot overlap")
        self.owner = get_ident()
        self.last_trace = None
        self.gc_events, self.gc_starts = [], {}
        self.origin = self.wall_clock()
        self.active = True
        gc.callbacks.append(self._gc_event)
        start = self.wall_clock()
        cpu = self.cpu_clock()
        failed = False
        try:
            return action()
        except BaseException:
            failed = True
            raise
        finally:
            cpu_elapsed = self.cpu_clock() - cpu
            elapsed = self.wall_clock() - start
            self.active = False
            gc.callbacks.remove(self._gc_event)
            root = {"id": 0, "parent_id": None, "stage": path,
                    "start_ns": start - self.origin, "wall_ns": elapsed,
                    "thread_cpu_ns": cpu_elapsed,
                    "wall_minus_thread_cpu_ns": max(0, elapsed - cpu_elapsed),
                    "exception": failed}
            self.last_trace = {"path": path, "spans": [root],
                               "gc_events": self.gc_events,
                               "gc_spanning_trace_end": sorted(self.gc_starts),
                               "elapsed_ns": elapsed, "thread_cpu_ns": cpu_elapsed}
            annotate_trace(self)


def make_diagnostic_capture(mode, **clocks):
    checked_mode(mode)
    cls = NestedDiagnosticCapture if mode.nested_spans else OuterDiagnosticCapture
    return cls(**clocks)


def diagnostic_instrumentation(mode, capture):
    checked_mode(mode)
    if capture.nested_spans != mode.nested_spans:
        raise ValueError("collector and diagnostic mode disagree")
    return instrument_pipeline(capture) if mode.nested_spans else nullcontext()


def require_outside_timer(capture):
    if capture is not None and capture.active:
        raise RuntimeError("diagnostic housekeeping must stay outside root timers")


def runtime_snapshot(capture=None):
    """Coarse outside-timer counters, not allocation traces or native-memory peaks."""
    require_outside_timer(capture)
    count, stats = list(gc.get_count()), gc.get_stats()
    blocks = sys.getallocatedblocks() if hasattr(sys, "getallocatedblocks") else None
    return {"automatic_gc_enabled": gc.isenabled(), "gc_thresholds": list(gc.get_threshold()),
            "gc_counts": count, "gc_stats": stats, "python_allocated_blocks": blocks,
            "allocated_blocks_are_not_bytes_or_total_native_memory": True}


@contextmanager
def diagnostic_gc_policy(mode, capture=None):
    """Restore normal GC even on failure and account for deferred cleanup.

    Entry requires enabled automatic GC. No threshold tuning, gc.freeze,
    per-window forced collection, power-plan changes or hidden warmup occurs.
    The deferred control changes only automatic cyclic collection. Explicit
    gc.collect still works, and reference counting still operates. Its cleanup
    cost is separately measured after automatic GC is restored, outside root
    timers; it must not disappear from the diagnostic's accounting.
    """
    checked_mode(mode)
    require_outside_timer(capture)
    if not gc.isenabled():
        raise ValueError("start every diagnostic mode from normal enabled GC")
    thresholds, callbacks = gc.get_threshold(), tuple(gc.callbacks)
    result = {"mode": mode.name, "automatic_gc_requested": mode.automatic_gc,
              "entry": runtime_snapshot(capture), "cleanup": None}
    if not mode.automatic_gc:
        gc.disable()
    try:
        yield result
    finally:
        # Snapshot before restoring policy. Normal timed actions must already
        # have removed their temporary callbacks, including exceptional paths.
        try:
            result["after_work"] = runtime_snapshot(capture)
            result["policy_consistent"] = (gc.isenabled() == mode.automatic_gc
                                           and gc.get_threshold() == thresholds
                                           and tuple(gc.callbacks) == callbacks)
        finally:
            # Even a failed housekeeping assertion must not leave GC disabled.
            gc.set_threshold(*thresholds)
            gc.enable()
        if not mode.automatic_gc:
            start, cpu = time.perf_counter_ns(), time.thread_time_ns()
            collected = gc.collect(2)
            cpu_elapsed = time.thread_time_ns() - cpu
            elapsed = time.perf_counter_ns() - start
            result["cleanup"] = {"outside_root_timers": True, "generation": 2,
                                 "wall_ns": elapsed, "thread_cpu_ns": cpu_elapsed,
                                 "collected_objects": collected,
                                 "includes_full_collection_and_builtin_free_list_effects": True}
        result["restored"] = runtime_snapshot(capture)


class TraceRetention:
    """Explicitly isolate growing full-trace retention from streamed evidence.

    A runner must write every trace before dropping it. This object does not
    perform I/O, aggregate timings, filter failures or sample away slow rows.
    No deep copy is introduced: the retained mode matches the old live-tree
    ownership. Streaming still keeps the current collector's last trace.
    """

    def __init__(self, mode):
        self.mode = checked_mode(mode)
        self._traces = []
        self.observed_trace_count = 0
        self.observed_span_count = 0
        self.retained_span_count = 0

    @property
    def retained_trace_count(self):
        return len(self._traces)

    def record(self, trace, capture=None):
        require_outside_timer(capture)
        if not trace.get("spans") or trace["spans"][0]["stage"] != trace["path"]:
            raise ValueError("trace must contain its root span")
        self.observed_trace_count += 1
        self.observed_span_count += len(trace["spans"])
        if self.mode.retain_full_traces:
            self._traces.append(trace)
            self.retained_span_count += len(trace["spans"])

    def snapshot(self, capture=None):
        require_outside_timer(capture)
        return {"mode": self.mode.name, "observed_trace_count": self.observed_trace_count,
                "observed_span_count": self.observed_span_count,
                "retained_trace_count": self.retained_trace_count,
                "retained_span_count": self.retained_span_count,
                "counts_are_metadata_nodes_not_memory_bytes": True}

    def release(self, capture=None):
        require_outside_timer(capture)
        before = self.snapshot(capture)
        self._traces.clear()
        self.retained_span_count = 0
        return before
