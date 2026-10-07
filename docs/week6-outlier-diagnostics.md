# Week 6: Latency-outlier diagnostic controls

Owner: Keegan Hoyne

Status: Diagnostic machinery and fixed runner implemented; no new experiment results.

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

## Fixed runner and cohort (implementation, not results)

`configs/week6_outlier_experiment.json`, `puf_snn/outlier_experiment.py` and
`scripts/run_week6_outlier_experiment.py` declare a separate experiment.
No new measurement has occurred merely because its tests pass.

Each of four blocks runs all four modes in fresh, sequential Python workers.
The mode orders are `[0,1,3,2]`, `[1,2,0,3]`, `[2,3,1,0]`, `[3,0,2,1]`:
each mode occupies every position once and every directed adjacent-mode pair
appears once within the four blocks. Model order is rotated through all six
existing conditions; it is not completely position-balanced. Frequency,
hybrid-core placement, thermal drift, OS contention and cache state remain
uncontrolled, so order controls are not proof of a causal hardware advantage.

For each worker/model, select the first two sorted test windows from every
device/class group: 60 sources, including six fixed devices and five classes.
Thirty disjoint validation warmups use the first window of each group. Each
worker/model performs one natural nominal-noise read and real reconstruction
per attempt, with no retry, truth substitution, outcome filtering or new
training. There are 16 timing workers and 8,640 total fresh attempts, not
8,640 independent reliability/security trials. Post-window estimates remain
conditional on successful admission. The first validation attempt of each
condition is retained separately as condition-first-use; it is not fully cold
system startup. Loading and trusted enrollment precede the root timers.

Manufacturing/enrollment and simulated credential policy remain the existing
baseline. Read streams use
`week6-diagnostic-v1:6767:{block}:{device_index}:{cohort}:measurement`, reset
per model/mode. Matching source/noise decisions, refusal paths, consumer-call
counts and sequence transitions must reconcile across modes within each
block. Blocks have separate noise streams; repeated sources and six model
conditions remain paired. Verifier keys/nonces continue to use OS randomness.
Both consumers run once per accepted delivery and never on refusals.

The retained mode owns full metadata trees across its six conditions; streamed
modes write every trace before releasing it. Analysis reloads full worker
evidence only after measurement and cleanup. This shorter 4,320-root maximum
cohort is not a reproduction of the original 29,718-tree history.

Four additional fresh processes load the same frozen models and complete
dataset, then retain 0, 5,000, 15,000 or 29,718 verified historical trace rows.
Each measures five explicit generation-2 collections, separating the first
from the other four. These replay public metadata, not the old application
heap, authenticated traffic, responses or credentials. They perform no
admission/inference. This is a mechanistic retained-metadata probe, not a
new application latency estimate or proof of every historical pause's cause.
Full collections may also clear free lists. Heap doses run in fixed increasing
order in separate processes; OS/cache/thermal history is not eliminated.

All 11 frozen binaries and the original completed result inventory are
hash-checked. Source must be clean and committed before the controller runs;
only its scoped output may appear while workers execute. New directories,
LF text writers, worker manifests and a master completion marker preserve
provenance. Incomplete work remains intact on error. No automatic resumption,
overwrite or removal occurs. Post-run byte checks bind ignored artifacts too.

Root-only mode has no separately timed nested first-post-window span. Use
matched root boundaries for observer comparisons, not a missing span or a
sum of component percentiles. Paired differences are right minus left, kept
by block/condition/phase/path/decision/reason. Their quantiles are not
differences of path percentiles; no no-op overhead is subtracted.

Every raw root trace must be written before release. Output/progress,
diagnostic snapshots, trace retention bookkeeping and cleanup stay outside
root timers. Root times include the active observer and are never adjusted
by subtracting a no-op estimate. Accepted/rejected paths, first use, warmup,
measured observations, p50/p95/p99/max and deferred cleanup stay separate.
Both consumers must run once on accepted events and never on refusals.
Anomaly flags must not rewrite authentication or sequence state.

The experiment does not start WPR, alter registry flags, change power plans,
clear caches, write durable authentication audits or implement a new model.
GC deferral restores the normal policy and records full cleanup separately.
No diagnostic mode receives a target-passing production-performance claim.

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
