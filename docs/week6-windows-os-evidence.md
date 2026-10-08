# Week 6: saved Windows OS accounting and public reporting

Owner: Keegan Hoyne

This follows the completed GC/observer experiment and Windows-traced workload.
It does not change motion models, anomaly thresholds, reconstruction, admission,
authentication, quality policy or the original timing results.

## Captured evidence and completed private review

Capture source: `624807b9095b7be41f7c3bbe7d18a31d50f95478`.
Reference and traced workers each performed 540 fresh single-read attempts and
retained 4,320 application root timings. Outcomes matched; rejected messages
made zero model calls. These are paired diagnostic observations, not independent
security/reliability trials or a replacement performance-target experiment.

All 27 actual native markers and their exact Python/native-QPC clock brackets
were checked. Final event/buffer loss was zero. Process/main-thread birth/end
records enclose all roots and rule out numeric thread-ID reuse in that lifetime.
The relative xperf-export clock uncertainty is 31.1 microseconds; per-root joins
instead use the directly checked 10 MHz native QPC-to-Python conversion.

The selected native inventory has 23 event/version families, 22 with TDH
metadata available. CSwitch v5 metadata is unavailable. A bounded 24,495-event
native/export cross-check reconciles selected clocks, CPU/thread IDs and known
state/reason fields; it does not prove every v5 field's meaning. The original
checker wrongly compared raw byte13 with a 0/1 export label. A separate recovery
review corrected only that interpretation, preserving all original code,
extracted bytes and failure evidence. Byte13 remains opaque and is unused.

Offline numeric extraction retained 1,547,821 scoped rows. Completed per-root
accounting covers all 4,320 roots and retains 2,106 distinct absolute/tail/maxima
observations across 144 condition/phase/path/outcome groups, including all eight
roots above 100 ms. All disjoint wall-time partitions reconcile. GC overlap
occurs in 2,160 roots; ready-to-dispatch intervals in 2,639. A single root overlaps
scoped main-thread file operations; no root overlaps the scoped disk/hard-fault
intervals. Absence of those scoped intervals is not absence of all I/O.

## Pure accounting and privacy filter

`src/python/puf_snn/windows_os_accounting.py` contains the interval mathematics
used for the private review. It performs no file/OS/model access. Tests cover
half-open boundaries, interval union, CPU migration, same-tick self-switches,
unmatched/reused I/O tokens, readiness partitions, unknown states, GC/interrupt
overlap, expected caught refusal exceptions and complete maxima retention.

Residency is paired from dispatch/switch-out events on the main thread.
Interrupts must overlap residency on that same logical CPU. DPC/ISR overlaps
are unioned, never added. The disjoint partition uses:

- Same-CPU interrupt union during scheduled residency.
- Scheduled GC excluding those interrupt intervals.
- Other scheduled residency, which still contains useful work and instrumentation.
- Off-CPU intervals initially ready/standby/deferred-ready at switch-out.
- Off-CPU intervals from an observed ReadyThread event to dispatch.
- Off-CPU intervals before observed readiness, or unresolved state if no readiness
  event was observed.
- Uncovered schedule time, if any; it is never extrapolated or hidden.

Only that partition sums to elapsed wall time. GC wall overlap, I/O operation
duration, hard-fault intervals and nested-stage locations are non-additive
overlays. Scheduled residency is not useful CPU execution; GetThreadTimes is
coarse on this host. I/O token pairing identifies outstanding operations, not
the dependency that blocked a thread. Raw unrecognized state/reason values
retain no invented semantic label. Ready-event flags are inventory only.

`src/python/puf_snn/windows_os_reporting.py` permits only predeclared project
labels, numeric durations/counts and approved nested-stage names. It rejects
unknown columns, invalid types, mismatched ledger/detail rows, omitted groups,
changed quantiles, broken interval partitions, missing maxima and unsupported
claims of isolated overhead. It removes private absolute clocks, OS identities,
CPU identities, I/O tokens and arbitrary observation text.

`src/python/scripts/summarize_week6_os_evidence.py` binds the exact completed
private accounting manifest and hashes every listed input before and after
filtering. It exports a new `results/week-6/keegan/windows-os-evidence` directory
only from clean committed source, without ETL scanning, model loading, recording,
authentication, training or new timing. Existing outputs are never overwritten.
LF byte-preservation rules and a manifest/COMPLETE record protect public hashes.
COMPLETE means the sanitized export reconciles, not complete causal attribution.

## Interpretation of the long cases

The 3,735.7236 ms first-condition-use root spends 3,690.2300 ms in reconstruction;
274.7025 ms of that stage overlaps GC. This locates the delay but does not isolate
JIT, backend initialization, allocation or cache effects. Loading/enrollment
precede root timers; first condition use is not fully cold system startup.

Four other pauses have 286.4601–432.8645 ms of GC overlap (about 90–98% of each
root), consistent with the earlier controlled collector evidence. In contrast,
the 142.4030 ms forest/forest root has 0.3193 ms GC and 56.1910 ms ready delay.
The two roughly 102–107 ms SNN roots have under 1 ms GC and about 9.6–12.5 ms
ready delay; residual consumer/reconstruction execution remains unisolated.
All eight overlapping GC therefore does not mean GC dominates all eight.

The full retained numeric/stage records, not only these eight examples, belong
in the scoped public export. Original accepted/refused paths, first use, warmup
and measured observations remain separate, with p50/p95/p99/max.

## Remaining evidence limits

Reference precedes traced in fresh processes. Their paired differences do not
isolate recorder/marker overhead from order, cache, thermals, frequency, core
placement or background activity. Do not subtract an overhead estimate to
manufacture a passing p95. The earlier observer controls remain a separate study.

Allocation stacks, cache misses, frequency/thermal transitions, dependency-level
waits and all other-thread activity are not fully resolved by this extraction.
CPU sample counts alone establish none of these causes. New tracing cannot
retroactively prove OS causes for old untraced observations. Retain an explicit
unresolved category rather than assigning all residual time to scheduling.
Complete causal attribution remains false. This adds evidence-qualified diagnosis,
not a promise that every outlier has one independently established cause.

Raw ETL and numeric kernel exports remain private, outside Git. No sensor samples,
PUF responses, credentials, keys or window tags enter the new public report.
Publishing input hashes permits controlled audit but does not make private
trace contents publicly reproducible. It establishes no Quest deployment,
durable-audit performance, new Tier-1/FRR result or hard real-time guarantee.
The research log and slide deck are not modified by the copy/test step.

## Primary references

- [Microsoft context switches](https://learn.microsoft.com/en-us/windows/win32/procthread/context-switches).
- [Microsoft CSwitch prefix states](https://learn.microsoft.com/en-us/windows/win32/etw/cswitch).
- [Microsoft TraceEvent kernel parser](https://github.com/microsoft/perfview/blob/main/src/TraceEvent/Parsers/KernelTraceEventParser.cs), including native-QPC InitialTime interpretation for DPC/ISR and hard faults.
