# Week 6: private Windows tracing support

Owner: Keegan Hoyne

Status: Capture-support implementation. This file does not report a new model
experiment or complete attribution of historical outliers.

## Purpose and preserved results

The completed `observer-experiment` remains unchanged at results commit
`9f7b737079281f72d183dba2867040c28ec01413`. This follow-up is for direct OS
evidence of scheduling and I/O around the existing v2 composite pipeline.
It does not retrain models, change anomaly thresholds, reconstruction or
authentication policy, suppress GC, or replace the original timing study.

The first tool check was a separate three-second interval between setup
markers, not a model latency measurement. A trace includes startup/save
overhead beyond that interval. Successful `xperf` exit codes alone are not
enough: inspect actual marker events, final events/buffers lost, required
event fields and decoder warnings. A command line mentioning a marker is
not the marker event itself.

## Clock correlation

`puf_snn.windows_trace` uses a fixed, process-local ETW provider:
`90553497-2ec7-49fa-a284-ade0159054fe`, event ID 1, version 1, level 4,
keyword 1. The 28-byte little-endian payload is `<8sQIII>`:
magic `PUFSNN6\0`, sequential marker index, process ID, native thread ID,
and one fixed phase code. It contains no sensor payload, PUF response,
credential, enrollment helper, key, tag, argument values or exception text.

EventRegister/EventWrite/EventUnregister are process-local; no manifest is
installed, no registry setting changes, and no service/driver is installed.
The raw bytes and descriptor must be decoded and checked in the actual saved
trace; a write returning success or a provider being enabled is not enough.

Each marker write is bracketed by absolute `perf_counter_ns()` readings.
Those use the same clock as the existing root traces. Markers must stay
outside root timers. Exported relative ETW microseconds and marker payloads
give an interval for the clock offset, not an assumed wall-clock conversion.
Intersect every marker's bounds, allowing one microsecond of export
quantization on either side. Reject missing/duplicate/mismatched events,
backward clocks, inconsistent bounds, mixed process/thread identities or
uncertainty above the predeclared 100 microseconds. Do not fit away failed
markers or select a different tolerance after seeing results.

A later workload must have all roots between its first and last markers.
Process/thread lifetime and PID reuse must also be checked. A valid clock
offset is permission to inspect intervals, not proof of an outlier's cause.

## Recording and privacy boundaries

`configs/week6_windows_trace.wprp` declares a limited system collector for
CPU samples, context switches, ready-thread events, disk/file I/O, hard
faults and DPC/interrupt activity, plus the public marker provider. It does
not enable heap tracing, hardware performance counters or third-party user
providers. CPU/I/O stacks remain private. Tracing imposes observer overhead;
this is a separate diagnostic, not a replacement p95 or a target-passing run.

Use AC power and close heavy applications. Record the actual environment;
frequency, hybrid-core placement, thermal and cache state are not controlled.
Do not change power plans, clear caches or silently add warmup. Preserve
first use, refusals and all measured observations.

Every capture needs a unique owned WPR instance and fresh output outside
Git. Stop/save only the instance started by its own helper, including errors.
Do not cancel another recording, overwrite an ETL, ignore event loss or use
`xperf -tle`/time-inversion bypasses. Failure leaves incomplete evidence for
inspection, not an automatic retry. Raw ETL, CSV dumps, command lines and
system-wide paths must never be published in the repository.

## Evidence limits

Require actual decoded CSwitch/ReadyThread events before interpreting
running, waiting or ready-to-run intervals. A Python wall-minus-thread-CPU
gap is not scheduling evidence. Resolve thread/process lifetimes, boundary
uncertainty, CPU migrations, DPC/interrupt activity and missing events.

File/disk events overlapping a root are observations, not automatically
blocking causes. Use issuing thread, IRP identity and operation completion
where supported. Decoder warnings remain explicit; zero dropped events
does not establish decoding of every newer Windows event version.

CPU samples are sampling evidence, not a complete execution/allocation
history. This profile does not trace every native/Python allocation, prove
cache causes or reconstruct old untraced OS events. New observations can
support a mechanism, but historical rows still need evidence-qualified
categories and explicitly unresolved causes. Do not claim every outlier
has a unique, fully demonstrated causal explanation.

## Primary references

- [Microsoft WPR command-line reference](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/wpr-command-line-options).
- [Microsoft recording collector definitions](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/1-collector-definitions).
- [Microsoft EventRegister](https://learn.microsoft.com/en-us/windows/win32/api/evntprov/nf-evntprov-eventregister).
- [Microsoft EventWrite](https://learn.microsoft.com/en-us/windows/win32/api/evntprov/nf-evntprov-eventwrite).
- [Microsoft xperf dumper](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/dumper).
