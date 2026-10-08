# Week 6 Windows OS evidence

Separate serial tracing diagnostic; not a replacement benchmark or a target-passing result.

The two fresh processes each retained 540 one-read admissions and 4,320 root timings. Functional signatures matched and refused messages had zero model calls. No fitting or threshold change occurred.

All 27 actual native markers, exact QPC/Python clock brackets, final event-loss header and main-thread lifetimes were checked. CSwitch v5 full TDH metadata remains unavailable: a 24,495-event selected-prefix cross-check is not validation of the entire schema. An incorrect 0/1 interpretation in the original review was corrected separately, preserving the extracted bytes. Opaque byte13 is not used here.

## Accounted observations

- All 4,320 traced roots have full scheduling coverage and reconciled disjoint wall partitions.
- Retained 2,106 distinct absolute/tail/maxima observations across 144 groups, including all eight roots above 100 ms.
- GC callback overlap occurred in 2,160 roots; ready-but-not-dispatched time occurred in 2,639 roots.
- One root overlaps scoped main-thread file read/write operations; none overlaps the scoped disk or hard-fault intervals. This does not rule out cached/metadata/other-thread I/O or prove blocking.

## Every root above 100 ms

Durations are milliseconds. GC, ready delay, I/O and nested-stage values overlap and must not be summed as independent causes.

| Condition / phase / path | Wall | GC union | Ready delay | Largest nested stage | Stage wall |
|---|---:|---:|---:|---|---:|
| forest_motion_forest_anomaly / measured / fresh_to_first_window | 142.4030 | 0.3193 | 56.1910 | first_post_window_total | 81.0160 |
| logistic_motion_forest_anomaly / condition_first_use / fresh_to_first_window | 3735.7236 | 277.1067 | 7.3066 | admission_total | 3691.4790 |
| logistic_motion_forest_anomaly / measured / post_window_recurring | 458.1650 | 432.8645 | 7.1023 | verifier_authentication_total | 439.1822 |
| logistic_motion_logistic_anomaly / warmup / fresh_to_first_window | 386.1479 | 347.6478 | 3.9231 | first_post_window_total | 371.7706 |
| snn32_seed17_forest_anomaly / measured / post_window_after_refusals | 310.7126 | 286.4601 | 3.4663 | verifier_authentication_total | 290.4391 |
| snn32_seed27_forest_anomaly / measured / fresh_to_first_window | 101.9816 | 0.4362 | 9.6164 | first_post_window_total | 85.9449 |
| snn32_seed27_forest_anomaly / measured / fresh_to_first_window | 106.8539 | 0.6492 | 12.4648 | first_post_window_total | 80.6821 |
| snn32_seed7_forest_anomaly / measured / exact_replay_receiver | 340.3783 | 333.7304 | 1.4551 | verifier_authentication_total | 340.3611 |

The 3,735.7236 ms first-condition-use root spends 3,690.2300 ms in reconstruction, with 274.7025 ms GC overlap inside that stage. The remaining reconstruction duration is not automatically a cache/JIT/allocation diagnosis. Model loading and enrollment precede root timers; first condition use is not fully cold system startup.

Four other long pauses have 286.4601–432.8645 ms GC overlap (about 90–98% of each root); the previous paired GC controls support a collector contribution, not proof of a sole cause. The 142.4030 ms forest/forest case instead has only 0.3193 ms GC but 56.1910 ms of ready-but-not-dispatched time. The two roughly 102–107 ms SNN cases have under 1 ms GC and 9.6164–12.4648 ms ready delay; the residual consumer/reconstruction work remains unisolated. All eight therefore overlapping GC does not mean GC dominates all eight.

## Timing interpretation and limits

The disjoint partition prioritizes same-CPU interrupt union during scheduled residency, then scheduled GC excluding those interrupts, then other scheduled residency. Off-CPU time is split by documented ready-at-switchout state, observed ReadyThread-to-dispatch intervals, not-yet-observed readiness and unresolved state. Raw unknown states/reasons remain numeric and are not assigned guessed meanings. Scheduled residency is not useful CPU execution; GetThreadTimes is coarse on this host.

GC, scoped I/O operations, hard faults and nested stages are separately clipped interval-union overlays. Outstanding I/O does not prove a blocking dependency. ISR/DPC accounting joins the worker's current CPU, not global interrupt totals; nested interruptions are counted once. Exact native QPC conversion uses validated 10 MHz ticks, not a fitted export clock; the old export-relative uncertainty was 31.1 microseconds.

The paired reference precedes traced in fresh processes. Reported differences are observed right-minus-left contrasts, not isolated tracing overhead: order, marker/recorder cost, cache, frequency, hybrid-core placement, thermals and background activity are confounded. Group p50/p95/p99/max are descriptive for this diagnostic and do not replace the original complete-path target results.

Allocation stacks, cache misses, frequency/thermal transitions, dependency-specific waits and all other-thread activity were not fully instrumented. CPU sample counts do not establish these causes. New tracing cannot retroactively prove OS causes for earlier untraced roots. Complete causal attribution remains false; unknown residuals are retained, never relabeled as scheduling or removed.

No durable audit I/O, Quest deployment, real-data generalization, new FRR/Tier-1 study or hard real-time guarantee is established.

## Files and provenance

`root-accounting.csv` contains all allowlisted numeric root records; `retained-root-detail.jsonl` contains nested-stage observations for every retained root; `large-root-detail.json` retains all eight >100 ms cases; `group-observations.csv` retains separate accepted/refused paths, warmup, first use and measured p50/p95/p99/max. `provenance.json` binds the private review and original capture without copying private content. The public COMPLETE marker confirms reconciled export, not complete causality.

The original fresh-v2 run, timing addendum and [controlled GC/observer study](../observer-experiment/diagnostic-report.md) remain unchanged. Raw ETL, decoded kernel exports, absolute times, OS IDs, addresses, paths and IRP tokens remain private. Retain the private originals for a controlled evidence review; the public checkout cannot recreate the original OS capture without them.

Readiness/state interpretation follows [Microsoft's context-switch explanation](https://learn.microsoft.com/en-us/windows/win32/procthread/context-switches) and [CSwitch prefix documentation](https://learn.microsoft.com/en-us/windows/win32/etw/cswitch). DPC/ISR/hard-fault InitialTime conversion follows Microsoft's [TraceEvent implementation](https://github.com/microsoft/perfview/blob/main/src/TraceEvent/Parsers/KernelTraceEventParser.cs), with actual available fields checked against this capture's TDH metadata.
