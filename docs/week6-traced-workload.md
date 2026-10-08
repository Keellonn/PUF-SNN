# Week 6: fixed private Windows-traced workload

Owner: Keegan Hoyne

Status: Workload/reader implementation, not a new recorded model result.

## Capability check already completed

The five-marker compatibility capture from the tracing-support baseline
`ec5db19aafcf95362c620bee6a6bd88c404dcaa0` was reviewed using a native saved-file
ETL consumer. All five actual public payloads, event descriptors and process/thread
identities matched the Python brackets. Every native QPC timestamp fell inside
its API bracket. Correlation with the old xperf export gave an all-marker offset
intersection 60 microseconds wide, within the predeclared 100-microsecond limit.
The finalized native trace header reported zero events lost and zero buffers lost.
No models ran. This establishes marker capability, not model latency or an OS cause.

The old xperf analyzer labels our uninstalled manifest-free provider as unknown.
Its `-add_rawdata` lines expose raw timestamp metadata, NOT event payload bytes.
`windows_trace_reader.py` therefore reads the actual 28-byte payload through
OpenTraceW/ProcessTrace, filtering for our provider before accessing UserData.
It never exports other providers' payloads, process names, command lines or paths.
Zero lost events does not mean every newer Windows event schema is decoded.

## Predeclared workload

Reuse the unchanged original observer-experiment worker and configuration.
Select only block 0, `nested_stream_gc_on`, with its original rotated model order.
All six conventional/SNN-32 motion-plus-anomaly conditions remain fixed. Each
worker uses 30 disjoint validation warmups and 60 test sources per condition:
540 natural single-read admission attempts per worker. A new controller will
run an untraced reference first and a traced worker second in separate processes.
There are 1,080 planned admissions total, not 1,080 independent FRR/security trials.
Preserve any refusals; never retry until acceptance or change the read policy.

Keep the same paired per-device/cohort noise stream and source selection.
Normal automatic GC, thresholds `[2000, 10, 10]`, streamed trace retention,
single-window batches, native-thread limit and model thresholds are unchanged.
No fitting, architecture search, threshold selection, cache clearing, power-plan
change, forced collection or GC deferral occurs. The original implementation,
historical results and frozen binaries are not edited.

## Markers and timing boundaries

The traced process writes 27 public markers: capture begin, inputs verified,
begin/end around each of the twelve condition/cohort runs, then capture end.
There are no per-root ETW writes. A scoped serial bridge restores the original
run_condition function even on errors, and rejects markers inside active roots.
The tiny public JSONL marker journal is flushed only outside roots. A failed
cohort does not receive a fabricated successful end marker.

Every retained root must match the marker PID/native TID and fall between its
own cohort's begin/end brackets. Full functional source/noise/decision/callback/
sequence signatures must later match between reference and traced workers.
The saved ETL must independently validate all 27 actual payloads, final loss,
clock bounds, process/thread lifetimes and the required OS event schemas.

WPR starts before the traced process, so imports/loading and process lifecycle
are captured. Only application roots define model-path latency: pinned-input
checks, trusted enrollment/endpoint creation, marker writes, progress, result
serialization, full-result analysis and capture startup/save are outside roots.
In-memory authentication audit is included; durable storage, network, physical
motion capture and hardware PUF acquisition remain excluded.

## Interpretation and privacy

The reference is first and the traced worker second. Their difference includes
trace/marker costs and uncontrolled order/cache/thermal/background variation;
it is not a pure randomized tracing-overhead estimate. CPU frequency, hybrid-core
placement and thermal/cache state are not controlled. Read AC status before/after
each worker, record the environment, and do not silently tune it to pass 20 ms.

The native reader opens only saved files and cannot start or stop a recording.
The model worker also does not control WPR. A separate reviewed Administrator
PowerShell helper will own a uniquely named session and fresh private directory.
Do not run the worker manually before that checkpoint. Tests use fabricated
events/callbacks and do not run models or real recording sessions.

Raw ETL and system-wide exports remain outside Git, including on failure.
Application worker COMPLETE records do not certify OS event loss or attribution.
Keep a separate capture-level incomplete status until all checks are reviewed.
Only sanitized, hash-bound summaries should eventually be committed.

Scheduling needs actual CSwitch/ReadyThread evidence, not wall-minus-CPU guesses.
File/disk overlap alone is not blocking causation. This profile does not trace
every allocation or establish CPU-cache effects. New traces cannot retroactively
prove every old untraced root cause; retain evidence-qualified unresolved cases.

## Native reader references

- [EVENT_TRACE_LOGFILEW and file-consumer options](https://learn.microsoft.com/en-us/windows/win32/api/evntrace/ns-evntrace-event_trace_logfilew).
- [Final trace header, loss counts and QPC frequency](https://learn.microsoft.com/en-us/windows/win32/api/evntrace/ns-evntrace-trace_logfile_header).
- [EVENT_RECORD header and UserData](https://learn.microsoft.com/en-us/windows/win32/api/evntcons/ns-evntcons-event_record).
