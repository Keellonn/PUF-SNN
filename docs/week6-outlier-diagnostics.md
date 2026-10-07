# Week 6: Latency-outlier diagnostic controls

Owner: Keegan Hoyne

Status: Diagnostic machinery and boundary tests; no new experiment results.

## Question and preserved evidence

The faculty requested a diagnosis of large latency outliers, including GC,
allocation, scheduling, disk I/O, first use, logging, cache effects,
reconstruction, verifier checks and measurement code. The original completed
run and its read-only addendum remain unchanged:

- `results/week-6/keegan/fresh-v2-timing`, results commit `a4a9e25`;
- `results/week-6/keegan/timing-diagnostics`, results commit `cc8c86c`.

The largest measured root in each model condition has 90.30–92.33% recorded
GC overlap. This is substantial observed collector activity, not proof of a
single cause. The original collector also retains growing Python trace trees,
so the observer itself is a testable contributor. Windows thread-CPU gaps do
not establish descheduling; stage location does not establish root cause.

This is a separate diagnostic, not a replacement accuracy, FRR, attack-recall
or target-passing experiment. No model, threshold, reconstruction policy,
authentication contract, quality rule, session TTL or synthetic source changes.

## Predeclared observer controls

`puf_snn/pipeline_diagnostics.py` supplies four fixed modes:

| Mode | Stage wrappers | Full trace trees retained | Automatic GC |
|---|---|---|---|
| `nested_retained_gc_on` | Original nested observer | Yes | Enabled |
| `nested_stream_gc_on` | Original nested observer | No, after evidence write | Enabled |
| `outer_stream_gc_on` | Root timer + GC callback only | No, after evidence write | Enabled |
| `nested_stream_gc_deferred` | Original nested observer | No, after evidence write | Temporarily deferred |

The first contrast isolates full-tree retention conditional on nested timing.
The second isolates nested observer machinery conditional on streamed evidence.
The last isolates automatic cyclic-collection deferral conditional on nested,
streamed evidence. These are conditional contrasts, not a complete factorial
design. All controls still incur clocks/GC callback/orchestration overhead;
the lightweight mode must not be called uninstrumented application timing.

GC-enabled modes are the reference. The deferred mode is a counterfactual,
not an operational recommendation or a way to manufacture a passing p95.
Reference counting continues; explicit `gc.collect()` is not disabled.
The helper restores enabled GC and original thresholds on exit, including
errors. Full deferred cleanup is timed separately outside window roots and
must be reported, not hidden. Full collection can also clear built-in free
lists, so this control does not isolate every allocator/cache effect.

Snapshots describe GC counters/statistics and Python allocated-block counts.
Block counts are not bytes, peak memory, all native allocations, or allocation
stack evidence. Trace/span counts are metadata-node counts, not heap sizes.
No runtime threshold tuning, forced per-window collection, `gc.freeze()`,
power-plan adjustment or automatic retry occurs in this machinery.

## Follow-up experiment requirements

The runner/cohort is a separate checkpoint, not implemented or executed by
these tests. It must predeclare source selection, sample sizes, repeats and
counterbalanced mode/model order before collecting new timings. It must reuse
the pinned dataset, all frozen artifacts and the unchanged admission code;
pair source/noise streams across modes and keep all natural refusals visible.
Independent worker processes should separate mode heap/GC history, while
startup, loading, enrollment, first decoder/model use and warmup boundaries
remain explicitly recorded. A short retained cohort is not a reproduction
of the original 29,718-tree heap; any historical-heap replay/probe needs its
own verified input and clearly disclosed scope.

Every raw root trace must be written before release. Output/progress,
diagnostic snapshots, trace retention bookkeeping and cleanup stay outside
root timers. Root times include the active observer and are never adjusted
by subtracting a no-op estimate. Accepted/rejected paths, first use, warmup,
measured observations, p50/p95/p99/max and deferred cleanup stay separate.
Both consumers must run once on accepted events and never on refusals.
Anomaly flags must not rewrite authentication or sequence state.

## OS tracing and attribution requirements

Absolute monotonic start/end timestamps, process ID and native thread ID are
public correlation fields, not OS scheduling evidence by themselves. A later
Windows tracing checkpoint will inspect context switches/ready time, CPU
sampling and I/O for the diagnostic process. Availability of WPR/WPA does
not establish that the available WPA build supports every captured event.
Capture configuration, dropped events and clock alignment must be checked.

Raw ETL traces can contain system-wide process/file-path information. Keep
them outside the public repository; publish only relevant sanitized evidence.
Do not cancel somebody else's recording, change registry tracing flags,
install drivers, purge caches or modify machine power policy in this step.

Every retained historical outlier must receive an evidence-qualified account:
observed GC activity; measured stage location; first-use status; direct
benchmark-output exclusion; or an explicitly unresolved cause. Multiple
contributors may coexist. New controlled results can support a mechanism,
but cannot retroactively prove scheduling, allocation or cache causes for a
historical observation lacking that instrumentation. Do not label unexplained
residual time as OS scheduling or invent a complete causal attribution.

## Instruction sources

- [Python 3.13 GC interface](https://docs.python.org/3.13/library/gc.html):
  automatic collection versus reference counting, callbacks, explicit full
  collection and free-list effects.
- [Microsoft WPR command-line reference](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpr-command-line-options):
  recording profiles, status, event-loss reporting and trace files.
- [Microsoft CPU analysis](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/cpu-analysis):
  CPU usage and scheduling analysis; a Python wall/CPU gap is not a substitute.
