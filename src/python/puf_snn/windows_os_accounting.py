"""Pure interval accounting for an already-extracted, single-thread ETW worker.

No files, ETW APIs, models or clocks are accessed by this module. Residency is
not thread CPU time. Overlays are observations, not additive causal estimates.
CSwitch-v5 byte13 and ReadyThread flags are deliberately not interpreted.
"""
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass


def interval_union(intervals):
    result = []
    for start, end in sorted(intervals):
        if type(start) is not int or type(end) is not int or start < 0 or end < start:
            raise ValueError("invalid integer interval")
        if start == end:
            continue
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(end, result[-1][1]))
        else:
            result.append((start, end))
    return result


def intersect(left, right):
    """Intersection of sorted, disjoint half-open interval lists."""
    output, i, j = [], 0, 0
    while i < len(left) and j < len(right):
        a, b = max(left[i][0], right[j][0]), min(left[i][1], right[j][1])
        if a < b:
            output.append((a, b))
        if left[i][1] <= right[j][1]:
            i += 1
        else:
            j += 1
    return output


def duration(intervals):
    return sum(end - start for start, end in intervals)


class IntervalIndex:
    def __init__(self, intervals):
        self.rows = interval_union(intervals)
        self.ends = [row[1] for row in self.rows]

    def clipped(self, start, end):
        output, index = [], bisect_right(self.ends, start)
        while index < len(self.rows) and self.rows[index][0] < end:
            a, b = self.rows[index]
            output.append((max(start, a), min(end, b)))
            index += 1
        return output


class RecordIndex:
    """Non-overlapping intervals with metadata; never merge different CPUs."""
    def __init__(self, rows):
        self.rows = sorted(rows)
        if any(row[0] < 0 or row[1] <= row[0] for row in self.rows):
            raise ValueError("invalid record interval")
        if any(self.rows[i][0] < self.rows[i-1][1] for i in range(1, len(self.rows))):
            raise ValueError("record intervals overlap")
        self.ends = [row[1] for row in self.rows]

    def clipped(self, start, end):
        output, index = [], bisect_right(self.ends, start)
        while index < len(self.rows) and self.rows[index][0] < end:
            row = self.rows[index]
            output.append((max(start, row[0]), min(end, row[1]), *row[2:]))
            index += 1
        return output


@dataclass
class Schedule:
    runs: RecordIndex
    gaps: RecordIndex
    off_categories: dict
    ready_times: list
    tied_out_in_pairs: int


def build_schedule(switches, ready_times):
    """Pair CSwitch residency exactly; subdivide gaps using readiness evidence.

    switches: (ns, kind, cpu, raw_old_state, raw_old_reason). At the same tick
    an out followed by an in represents zero-time transition/self-switch.
    Raw state1/3/7 is ready/standby/deferred-ready in the checked prefix.
    Otherwise, ONLY an observed ready event establishes the ready tail.
    No-ready gaps remain unresolved, not automatically scheduler or I/O waits.
    """
    ordered = sorted(switches, key=lambda row: (row[0], 0 if row[1] == "switch_out" else 1))
    ready_times = sorted(ready_times)
    runs, gaps, running, prior_out = [], [], None, None
    tied_pairs = 0
    for time, kind, cpu, state, reason in ordered:
        if type(time) is not int or time < 0 or kind not in ("switch_in", "switch_out") or not 0 <= cpu < 22:
            raise ValueError("unexpected scheduling event")
        if kind == "switch_in":
            if running is not None:
                raise ValueError("two dispatches without a matching switch-out")
            if prior_out is not None:
                begin, old_state, old_reason = prior_out
                if begin < time:
                    gaps.append((begin, time, old_state, old_reason))
                elif begin == time:
                    tied_pairs += 1
            running = (time, cpu)
        else:
            if running is None or running[1] != cpu:
                raise ValueError("switch-out lacks the matching CPU dispatch")
            if running[0] < time:
                runs.append((running[0], time, cpu))
            prior_out = (time, state, reason)
            running = None
    if not ordered or running is not None:
        raise ValueError("saved dispatch sequence is empty or lacks its final switch-out")
    categories = defaultdict(list)
    for begin, end, state, reason in gaps:
        if state in (1, 3, 7):
            categories["off_ready_at_switchout"].append((begin, end))
        else:
            first = bisect_left(ready_times, begin)
            if first < len(ready_times) and ready_times[first] <= end:
                ready = ready_times[first]
                categories["off_not_yet_observed_ready"].append((begin, ready))
                categories["off_ready_after_event"].append((ready, end))
            else:
                categories["off_state_unresolved"].append((begin, end))
    return Schedule(RecordIndex(runs), RecordIndex(gaps),
                    {key: IntervalIndex(categories[key]) for key in (
                        "off_ready_at_switchout", "off_ready_after_event",
                        "off_not_yet_observed_ready", "off_state_unresolved")},
                    ready_times, tied_pairs)


def pair_operations(events):
    """Pair opaque extraction tokens. Operation duration is NOT blocking time.

    events: (ns, kind, token, size_or_status). Zero-duration operations remain
    in the inventory, although they contribute no interval duration.
    """
    pending, seen, output = {}, set(), []
    for time, kind, token, value in sorted(events, key=lambda row: row[0]):
        if token <= 0 or time < 0:
            raise ValueError("invalid opaque I/O token or timestamp")
        if kind.endswith("_begin"):
            if token in seen:
                raise ValueError("I/O token reused")
            pending[token] = (time, kind, value)
            seen.add(token)
        elif kind in ("file_end", "disk_end"):
            if token not in pending:
                raise ValueError("unmatched I/O completion")
            begin, operation, requested = pending.pop(token)
            if time < begin or operation.split("_")[0] != kind.split("_")[0]:
                raise ValueError("I/O family/time mismatch")
            output.append(dict(start_ns=begin, end_ns=time, kind=operation.removesuffix("_begin"),
                               token=token, requested_bytes=requested,
                               completion_value=value))
        else:
            raise ValueError("unexpected I/O event type")
    if pending:
        raise ValueError("uncompleted scoped I/O operations")
    return output


def trace_intervals(trace):
    begin, end = trace["clock_start_ns"], trace["clock_end_ns"]
    if (any(type(value) is not int for value in (begin, end, trace["elapsed_ns"]))
            or begin < 0 or end <= begin or end - begin != trace["elapsed_ns"]):
        raise ValueError("application root clocks do not reconcile")
    spans = trace["spans"]
    if (not spans or spans[0]["id"] != 0 or spans[0]["parent_id"] is not None
            or spans[0]["stage"] != trace["path"] or spans[0]["wall_ns"] != end - begin
            or spans[0]["exception"] is not False or trace["gc_spanning_trace_end"]):
        raise ValueError("root span or complete GC bounds are unavailable")
    origin = begin - spans[0]["start_ns"]
    stages = defaultdict(list)
    for expected, span in enumerate(spans):
        start = origin + span["start_ns"]
        finish = start + span["wall_ns"]
        if (span["id"] != expected or not begin <= start <= finish <= end
                or type(span["exception"]) is not bool):
            raise ValueError("application nested span is outside its root or its exception field is invalid")
        if expected:
            parent = span["parent_id"]
            if type(parent) is not int or not 0 <= parent < expected:
                raise ValueError("invalid span parent")
            ancestor = spans[parent]
            if not ancestor["start_ns"] <= span["start_ns"] <= span["start_ns"] + span["wall_ns"] <= ancestor["start_ns"] + ancestor["wall_ns"]:
                raise ValueError("span is outside its parent")
        stages[span["stage"]].append((start, finish))
    gc = []
    for event in trace["gc_events"]:
        if event["generation"] not in (0, 1, 2) or event["end_ns"] < event["start_ns"]:
            raise ValueError("invalid GC event")
        start, finish = max(begin, origin + event["start_ns"]), min(end, origin + event["end_ns"])
        if start < finish:
            gc.append((start, finish))
    return begin, end, interval_union(gc), {key: interval_union(value) for key, value in stages.items()}


class Accounting:
    def __init__(self, schedule, interrupts, file_operations, disk_operations, hard_faults, samples):
        self.schedule = schedule
        self.interrupts = {cpu: {kind: IntervalIndex(rows) for kind, rows in kinds.items()}
                           for cpu, kinds in interrupts.items()}
        self.file_operations, self.disk_operations = file_operations, disk_operations
        self.file_io = IntervalIndex((row["start_ns"], row["end_ns"]) for row in file_operations)
        self.disk_io = IntervalIndex((row["start_ns"], row["end_ns"]) for row in disk_operations)
        self.hard_faults = IntervalIndex(hard_faults)
        self.samples = sorted(samples)

    def root(self, trace, *, stages=False):
        begin, end, gc, nested = trace_intervals(trace)
        run_rows = self.schedule.runs.clipped(begin, end)
        runs = interval_union((a, b) for a, b, cpu in run_rows)
        gaps = self.schedule.gaps.clipped(begin, end)
        off = interval_union((a, b) for a, b, state, reason in gaps)
        if intersect(runs, off):
            raise ValueError("scheduled and off-CPU intervals overlap")
        interrupt = defaultdict(list)
        for start, finish, cpu in run_rows:
            for kind, index in self.interrupts.get(cpu, {}).items():
                interrupt[kind].extend(index.clipped(start, finish))
        dpc, isr = interval_union(interrupt["dpc"]), interval_union(interrupt["isr"])
        irq = interval_union([*dpc, *isr])
        gc_scheduled = intersect(gc, runs)
        gc_irq = intersect(gc_scheduled, irq)
        masks = {key: index.clipped(begin, end) for key, index in self.schedule.off_categories.items()}
        wall, scheduled, off_ns = end - begin, duration(runs), duration(off)
        partition = {key + "_ns": duration(value) for key, value in masks.items()}
        partition.update(
            scheduled_interrupt_ns=duration(irq),
            scheduled_gc_without_interrupt_ns=duration(gc_scheduled) - duration(gc_irq),
            scheduled_other_ns=scheduled - duration(irq) - duration(gc_scheduled) + duration(gc_irq),
            schedule_uncovered_ns=wall - scheduled - off_ns,
        )
        if min(partition.values()) < 0 or sum(partition.values()) != wall or sum(duration(value) for value in masks.values()) != off_ns:
            raise ValueError("disjoint wall accounting does not reconcile")
        file_io, disk_io = self.file_io.clipped(begin, end), self.disk_io.clipped(begin, end)
        faults = self.hard_faults.clipped(begin, end)
        raw_states, raw_reasons = Counter(), Counter()
        for start, finish, state, reason in gaps:
            raw_states[str(state)] += finish - start
            raw_reasons[str(reason)] += finish - start
        result = dict(**partition, elapsed_ns=wall, thread_cpu_ns=trace["thread_cpu_ns"],
                      scheduled_residency_ns=scheduled, off_cpu_ns=off_ns,
                      gc_wall_union_ns=duration(gc), gc_while_scheduled_ns=duration(gc_scheduled),
                      gc_while_offcpu_ns=duration(intersect(gc, off)),
                      gc_interrupt_overlap_ns=duration(gc_irq),
                      dpc_while_scheduled_ns=duration(dpc), isr_while_scheduled_ns=duration(isr),
                      file_operation_overlap_ns=duration(file_io), disk_operation_overlap_ns=duration(disk_io),
                      file_operation_offcpu_overlap_ns=duration(intersect(file_io, off)),
                      disk_operation_offcpu_overlap_ns=duration(intersect(disk_io, off)),
                      hard_fault_interval_overlap_ns=duration(faults),
                      hard_fault_offcpu_overlap_ns=duration(intersect(faults, off)),
                      cpu_profile_sample_count=bisect_left(self.samples, end) - bisect_left(self.samples, begin),
                      raw_switchout_state_offcpu_ns=dict(raw_states),
                      raw_switchout_reason_offcpu_ns=dict(raw_reasons),
                      cpu_indices_observed=sorted({cpu for _, _, cpu in run_rows}),
                      caught_nested_exception_count=sum(span["exception"] for span in trace["spans"][1:]),
                      schedule_fully_covered=partition["schedule_uncovered_ns"] == 0,
                      complete_causal_attribution_established=False)
        if stages:
            result["nested_stage_observations"] = [dict(
                stage=stage, wall_union_ns=duration(intervals),
                gc_overlap_ns=duration(intersect(intervals, gc)),
                scheduled_residency_ns=duration(intersect(intervals, runs)),
                off_cpu_ns=duration(intersect(intervals, off)),
                same_cpu_interrupt_ns=duration(intersect(intervals, irq)),
                file_operation_overlap_ns=duration(intersect(intervals, file_io)),
                disk_operation_overlap_ns=duration(intersect(intervals, disk_io)),
                hard_fault_overlap_ns=duration(intersect(intervals, faults)),
                exception_span_count=sum(span["exception"] for span in trace["spans"] if span["stage"] == stage),
            ) for stage, intervals in sorted(nested.items()) if stage != trace["path"]]
        observations = []
        if result["gc_wall_union_ns"]:
            observations.append("GC callback interval overlaps this root; not sole-cause proof")
        if result["off_ready_at_switchout_ns"] + result["off_ready_after_event_ns"]:
            observations.append("Ready-but-not-dispatched intervals observed on the main thread")
        if result["off_not_yet_observed_ready_ns"] or result["off_state_unresolved_ns"]:
            observations.append("Other off-CPU intervals remain dependency/state unresolved")
        if result["scheduled_interrupt_ns"]:
            observations.append("Same-CPU DPC/ISR interval union overlaps main-thread residency")
        if result["file_operation_overlap_ns"] or result["disk_operation_overlap_ns"]:
            observations.append("Scoped main-thread I/O operation interval overlaps; blocking cause not proved")
        if result["hard_fault_interval_overlap_ns"]:
            observations.append("Scoped main-thread hard-fault interval overlaps")
        if trace.get("phase") == "condition_first_use":
            observations.append("First condition use; initialization/cache/backend causes not isolated")
        if result["schedule_uncovered_ns"]:
            observations.append("Incomplete scheduling coverage; uncovered duration retained explicitly")
        result["observations"] = observations
        return result


def quantile(values, fraction):
    ordered = sorted(values)
    if not ordered or not 0 <= fraction <= 1:
        raise ValueError("invalid quantile request")
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    return ordered[lower] + (ordered[min(lower + 1, len(ordered) - 1)] - ordered[lower]) * (position - lower)


def trace_key(trace):
    return tuple(trace[key] for key in ("condition", "phase", "path", "attempt_index"))


def group_key(trace):
    return tuple(trace[key] for key in ("condition", "phase", "path", "decision", "reason"))


def retention_reasons(roots, absolute_ns=20_000_000, large_ns=100_000_000):
    groups, output = defaultdict(list), {}
    for root in roots:
        key = trace_key(root)
        if key in output:
            raise ValueError("duplicate application root identity")
        output[key] = []
        groups[group_key(root)].append(root)
    for rows in groups.values():
        tail, maximum = quantile([r["elapsed_ns"] for r in rows], .99), max(r["elapsed_ns"] for r in rows)
        for root in rows:
            flags = output[trace_key(root)]
            if root["elapsed_ns"] > absolute_ns:
                flags.append("above_20ms_diagnostic_cutoff_not_target_claim")
            if root["elapsed_ns"] > large_ns:
                flags.append("above_100ms")
            if root["elapsed_ns"] >= tail:
                flags.append("group_p99_tail")
            if root["elapsed_ns"] == maximum:
                flags.append("group_maximum")
    return output
