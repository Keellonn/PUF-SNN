# Week 8 formal three-arm resource feasibility plan — v1

Review date: **2026-10-20, America/New_York**. Scope: read-only source and saved
artifact inspection; this document is the only new deliverable. No experiment,
benchmark, test, replay audit, dependency installation or formal enabling occurred.

## 1. Executive feasibility status

**Bounded development profiling is feasible; 90,000-arm execution is not yet
resource-qualified or authorized.** Storage appears modest, but repeated hashing,
schema construction, synchronous writes, replay and retained Python object graphs
have no measured full-run runtime or peak-memory budget. There is no demonstrated
resource defect that prevents the existing 150-arm nonformal workload. Do not
interpret that as evidence that the formal workload fits available RAM or time.

The [formal methodology review](week8-three-arm-formal-methodology-review-v1.md)
remains controlling for scientific prerequisites. The CLI has only `plan`,
`run-nonformal` and `audit`; runtime and writer reject `planned-formal`.
The planned 20 populations × 6 devices × 50 trials × 5 conditions × 3 arms is
unchanged. Projections below describe that allocation under current mechanisms,
not an executable formal mode or completed formal measurements.

## 2. Observed pilot artifacts and measurements

Inspected bundle:
[`week8-three-arm-auth-v1-nonformal-20261020-001`](../results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/).
Its saved source ID is
`83001370f5a65f5d8c6cb55c38bd6f239a6c693a065182b22e1b24575e695153`.
Sizes below are actual file lengths, not allocated disk blocks or compressed sizes.
Calculations used file enumeration and standard-library JSON parsing only; no
project module, schema validator or evidence-audit function was executed.

- Attempts: `attempts.jsonl` **924,808 bytes**, 150 newline-terminated rows.
- Plan/configuration: `trial-plan.json` **50,497**; `config.json` **2,306**;
  combined **52,803 bytes**.
- Summary: `summary.json` **101,511 bytes**, with 15 arm-condition groups.
- Manifests: `manifest.json` **10,858**; `source-manifest.json` **9,662**;
  combined **20,520 bytes**.
- Source snapshots: **87 files, 1,173,346 bytes**.
- Validation receipts: `validation.json` **279** and
  `NONFORMAL_VALIDATED.json` **447**; combined **726 bytes**.
  These are reconciliation/completion receipts; no archived test-run receipt exists.
- Other files: `metadata.json` **2,682**; `enrollments.json` **425 bytes**.
- Entire bundle: **97 files, 2,276,821 bytes**; excluding snapshots,
  **1,103,475 bytes**. No separate timing or resource-profiler file exists.

Attempt sizes include the saved newline. Overall mean **6,165.39 bytes/arm**,
median **6,117**, range **4,253–7,385**. Each arm has 50 rows:

- Single-read: **289,759 bytes**, mean **5,795.18**, range **4,253–6,138**.
- Majority-3: **357,638 bytes**, mean **7,152.76**, range **5,481–7,385**.
- Stored: **277,411 bytes**, mean **5,548.22**, range **5,543–5,555**.

Read counts, outcome-dependent handshake/window spans, error-position lists and
numeric widths explain variation; future outcomes and timing digits can change it.
The 2,870 saved spans occupy **302,495 bytes** as serialized `timing` array values;
`stage_duration_ns` values add **73,516 bytes**. These bytes are already inside
the JSONL total. Summary timing aggregates are already inside `summary.json`.

Saved establishment spans total **2.6703435 s** over 150 arms; first-window roots
total **1.0751017 s** over 136 eligible sessions. Their **3.7454452 s** sum excludes
harness work and is not process wall time. Nested spans must not be added again.
The first BCH decode, execution index 1, lasted **2.4041319 s**; the 100 decode
spans have median **1.13615 ms**. This is consistent with the source's first-use
compilation warning, but is not an isolated measurement of compiler cost.

The saved metadata records Windows 11 build 26200, CPython 3.12.4, galois 0.4.11,
NumPy 2.5.3, Numba 0.67.0, SciPy 1.18.1 and jsonschema 4.26.0. It records no CPU,
RAM capacity, peak working set/private memory, full wall time, physical disk I/O,
fsync latency or replay duration. Filesystem timestamps cannot supply those
missing measurements. Saved legacy validation work is **one pass: 200 replay
measurements, 100 decodes, one reference reading**; the marker records two
finalization passes. The [accounting addendum](week8-validation-work-accounting-addendum-20261020.md)
explains the corrected scope. Historical files and hashes remain untouched.

## 3. Source-derived behavior and formal projections

Primary inspection points:
[planner](../src/python/puf_snn/experiments/three_arm_auth_v1.py),
[runtime](../src/python/puf_snn/experiments/three_arm_auth_runtime_v1.py),
[evidence writer/auditor](../src/python/puf_snn/experiments/three_arm_auth_evidence_v1.py),
[CLI](../src/python/scripts/run_three_arm_auth_v1.py), and inherited
[hashing/writes/environment](../src/python/puf_snn/experiments/majority3_auth_evidence_v1.py),
[enrollment/configuration](../src/python/puf_snn/experiments/majority3_auth_v1.py),
[noise replay](../src/python/puf_snn/experiments/correlated_noise_v1.py) and
[BCH backend](../src/python/puf_snn/reconstruction/bch.py).
Counts assume successful, uninterrupted completion with unchanged source lists.

**Timing boundary.** Establishment includes acquisition or retrieval,
reconstruction/BCH, admission verification, HKDF and mutual confirmation, with
observation wrappers and endpoint in-memory auditing where called. First-window
work has a separate root and uses recording callbacks, not SNN/anomaly inference.
Enrollment/encoding, provisioning, shared-noise setup, fresh endpoints, window
creation, instrumentation installation, post-attempt row construction, source
hashing, schema validation, JSONL/fsync, summaries and replay are outside these
roots. The `measurement` child times frequency calculation, not the entire reader.
Process launch/imports and initial enrollment/backend algebra/encode setup are
also outside; first lazy decode compilation can occur inside establishment.
`BCHCodec._backend()` caches fixed algebra; no harness warm-up is performed.

**Raw output extrapolation, not a storage guarantee.**
`924,808 / 150 × 90,000 = 554,884,800 bytes` (**554.9 MB / 529.2 MiB**) of JSONL,
independently confirming the earlier approximately 555 MB projection. Scaling the
pilot plan suggests approximately **30.3 MB**; one current snapshot is **1.187 MB**,
the fixed 15-group summary is roughly **0.1 MB**, and 120 enrollment records are
roughly **0.05 MB**. Thus approximately **587 MB** for one comparable bundle,
before new analysis/profiling artifacts, filesystem allocation and backups.
Do not multiply fixed snapshots/summary by 600. Applying observed minimum/maximum
row lengths uniformly gives **382.77–664.65 MB** of JSONL as a sensitivity range,
not prediction bounds. Longer identities and larger indices also change bytes.

**Hashing.** Week 8 `source_hashes()` first invokes the inherited Week 7 hashing
routine, discards its result, then hashes its own superset. The current sets are
**78 files / 920,549 bytes** and **87 files / 1,187,245 bytes**: **165 file digests
and 2,107,794 logical input bytes per outer call**. Both traverse the overlapping
sources; file hashing uses `read_bytes()`. There is one outer call at construction,
one before each arm, one before reconciliation, one inside the manifest audit,
and one before the marker: **N + 4 = 90,004 outer calls**, also 90,004 inherited
calls, or **14,850,660 file-digest operations** in these scans.

Those scans read **189,709,891,176 bytes = 189.71 GB / 176.68 GiB logically**.
Snapshot creation rehashes the current set once; manifest construction, manifest
verification and explicit snapshot verification hash a snapshot set three more
times: another **4,748,980 bytes / 348 source-file digests**. Copying source bytes
adds another 1,187,245 logical bytes without hashing. Artifact hashes are extra.
The saved snapshot's corresponding inherited/superset sizes are 917,321 and
1,173,346 bytes: historical-size scans imply **188.17 GB** at 90,004 calls.
This reconciles the earlier approximately 188 GB estimate with the larger
corrected source. **Logical reads are not physical disk traffic**: OS caches may
serve them, while file opens, directory traversal and hashing still consume time.

Relevant current file sizes: planner **6,192**, runtime **12,456**, evidence module
**36,313**, attempt schema **30,603**, summary schema **129,562**, three-arm tests
**46,243**, and saved test patch **36,424 bytes**. Historical evidence/tests were
**33,085 / 35,572 bytes**; total snapshot growth is **13,899 bytes**. The source
list includes all package Python files, even components unused by this study.

**Serialization, schema and synchronization.** Each append validates a row,
serializes it once with canonical JSON plus newline, writes, flushes and fsyncs,
then retains that same row in `self.rows`. At formal allocation this is **90,000
row serializations and 90,000 per-row flush/fsync pairs**, plus one stream-close
pair. Ten non-snapshot JSON writes each flush/fsync, giving **90,011 fsync calls**
for a successful bundle. Snapshot files close after writing but have no explicit
fsync; no additional directory fsync is implemented. These counts describe the
current implementation, not a stronger crash-durability guarantee.

`validate_schema()` rereads/parses the schema, checks the schema itself and
constructs a validator every time. Append plus two reconciliations give **270,000
attempt validations/schema constructions**, reading **8,262,810,000 logical schema
bytes**, separately from source hashing. Each reconciliation also validates and
recompiles the plan; a CLI run builds the plan four times including its preliminary
plan and writer construction. Summary schema validation occurs twice. Canonical object
hashes for identities, enrollment and replay add serialization beyond JSONL;
the 90,000 count is only persisted attempt serialization.

**Execution, finalization and later audit.** There are 30,000 matched identities,
120 devices, **120,000 experimental PUF readings, 60,000 runtime BCH decodes,
30,000 runtime votes and 30,000 stored invocations**, plus 120 setup references
and credential/helper encodes. Each reconciliation re-creates 120 enrollment
materials, replays **120,000 measurements / 60,000 decodes / 30,000 votes**, and
checks recorded protocol/timing semantics. It does not rerun the handshake or
add statistical samples. Two-pass finalization therefore adds **240,000 replay
measurements / 120,000 decodes / 60,000 votes / 240 reference readings**.
Execution plus finalization totals **360,360 simulator measurements including
references, and 180,000 decodes**, excluding any future warm-up.

Finalization closes the stream, reconciles retained rows, computes the summary,
writes validation, hashes all manifest members, then audits the manifest and
reconciles/reshapes summaries again before the completion marker. The JSONL is
read once for manifest construction, once for manifest verification, and once
for parsing: approximately **1.665 GB logical reads** at the central projection,
in addition to its write. One later standalone audit adds **120,000 replay
measurements / 60,000 decodes / 30,000 votes / 120 references**, 90,000 attempt
validations (another **2.754 GB** schema reads), full manifest/snapshot checking,
one outer-plus-inherited source scan, and another summary computation. It reads
JSONL once to hash and once to parse. Each audit is separately budgeted; the CLI
launch also incurs imports and possibly compilation. Its exact source/environment
checks require the corresponding frozen checkout/environment. The corrected
checkout must not be used to replay or reseal the historical bundle.

## 4. Unknown quantities and scaling risks

Peak RAM is unknown. `self.rows` retains every nested dict/list/string; internal
audit loads a second complete parsed row graph while the first remains live.
Whole-file `read_bytes().splitlines()` adds transient byte buffers; manifest
hashing also materializes the entire JSONL as bytes. Original,
audit-loaded and temporarily recompiled plans, expected-schedule tuples,
duplicate-ID sets, pairing maps and summary lists also coexist at various phases.
Raw JSONL bytes cannot determine Python heap size or peak process memory.

Runtime is unknown. Millions of small file opens, repeated schema self-validation,
90,011 synchronous persistence calls, decoder compilation and two replay passes
may dominate different machines. Summary filtering and repeated quantile sorting
add work; the current summary does not execute the planned three-arm 10,000-draw
inferential analysis. That future analysis and approved timing diagnostics need
their own resource allowance. The serial instrumentation lock precludes simply
threading attempts; process sharding would require a separately reviewed design.
There is no resume path: interruption can waste accumulated execution and replay
work. Neither stage-time multiplication nor pilot file size proves runtime/RAM
scaling; small-run memory slopes cannot certify the 90,000-row audit peak.

## 5. Proposed bounded development benchmark — not executed

**Exact workload.** Preserve the nonformal configuration's five conditions,
three arms, seeds, zero warm-up, no retries and allocation **1 × 1 × 10**:
**50 matched identities / 150 arms per bundle**. Inherited configuration validation
requires this exact nonformal allocation; arbitrary 30/60-arm nonformal sweeps
are not currently supported. Use **three sequential worker processes**, each
creating one process-cold 150-arm bundle followed by one further 150-arm bundle
in the same process. Release the first run object before starting the second.
Total cap: **six bundles / 900 development arms**; no pooling as research data.
Then run **one standalone audit on each second bundle**, three audits total,
in separate monitored processes using the unchanged source/environment. Each
bundle includes its normal two finalization passes. No historical audit occurs.

**Protected outputs.** Keep the existing enforced direct-child namespace:
`results/week-8/will/three-arm-auth-v1/nonformal/`, using exclusively new names
`week8-three-arm-auth-v1-nonformal-resource-v1-<session>-p1-cold` and `-p1-warm`,
with analogous `p2`/`p3` names. Use a unique lowercase session token and respect
the existing suffix length limit. Refuse any pre-existing, linked, aliased or
nested evidence path. Keep profiler logs outside sealed bundles, under an
exclusively new `tmp/week8-three-arm-resource-profile-v1/<session>/`; extra files
inside bundles would violate manifest closure. Archive these sidecars separately
afterward. Existing `RUN-150-NONFORMAL` authorization and reviewed plan digest
checks remain mandatory. This document supplies no execution authorization.

**Cold/warm interpretation.** Launch each pair in a fresh interpreter with a
new, initially empty profiling cache directory where the compiler supports it;
never delete shared caches. Record all effective cache paths/settings and cache
hits if observable. The second run tests same-process reuse after the first
complete workload, with fresh endpoints and evidence. It remains labeled with
the existing cold/no-harness-warmup configuration, with reuse disclosed in the
sidecar; it is not the proposed formal warmed timing profile. Empty requested
cache paths alone do not prove all dependency code was compiler-cold. Report
startup/import, enrollment/backend initialization, first-decode and subsequent
decode phases separately; do not discard the slow first observation.

**Measurements.** An external controller measures monotonic launch-to-exit wall
time, worker lifetime peak working set and sampled private bytes/working set
(50 ms interval), CPU time, free memory/disk and directory growth. Record OS peak
counters where available and distinguish sampled maxima from guaranteed peaks.
Same-process cold/warm runs share lifetime peak counters; report phase sample
maxima and the pair's OS peak, not differences between cumulative peaks.
Record child processes separately, including startup Git subprocesses. Measure
logical output bytes, file counts, allocated size if available, and compiler-cache
growth separately from evidence. Process I/O counters are not physical-device I/O.

Within the worker, separately time construction/setup, the attempt loop,
`execute_attempt`, `append`, finalization precheck, each reconciliation, each
summary, manifest operations and standalone audit. Record canonical serialization,
schema validation, file-hash byte/call counts and flush/fsync counts/durations
where instrumentable. Delegate every call unchanged. Maintain nested inclusive
and exclusive accounting: source hashing nests file hashing, append nests schema,
serialization and fsync, and finalization nests audit/reconciliation. Do not add
those overlapping durations or call the entire wall-time-minus-span residual
"writer overhead". Other setup and row-building work is also in that residual.
Do not write profiler events per arm synchronously; buffer bounded aggregates.

**Smallest future utility, if approved.** One standalone controller/worker script,
for example `tools/profile_three_arm_resources_v1.py`, can call the existing
writer/CLI APIs and temporarily wrap harness functions to collect those metrics.
Wrap both Week 8 and inherited hashing bindings; otherwise duplicate hashing is
missed. Restore all bindings on failure. Keep it outside the production package;
record its own hash/version and invocation separately. No runtime, authentication,
noise, schema or integrity behavior needs changing. Its small fixture-based test
file should cover exact workload and aggregate caps, path collision/historical
path refusal, time/memory/disk stop behavior, subprocess cleanup, nested metric
accounting, unchanged delegated returns/exceptions/serialized fixture bytes,
restoration after exceptions and no success receipt after failed finalization.
Neither utility nor tests are implemented here. Quantify observer cost with stub
fixtures; report profiling perturbation instead of subtracting guessed overhead.

Record CPU/model/core counts, RAM/free RAM, OS/build, Python executable/version,
dependency versions, source/config/canonical-plan hashes, utility hash, storage
type/filesystem/free space, cache policy, power/thread settings, clock resolution,
background load and interruptions. Preserve stdout/stderr, exit status, scoped
receipts and phase metrics. Compare all three paired runs; report spread and
phase throughput rather than a single extrapolated completion time.

**Proposed stop budgets, subject to researcher selection before profiling:**
15 minutes per bundle or audit, two hours for the session, 2 GiB worker private
bytes or working set, less than 2 GiB available system RAM, less than 2 GiB free
output-volume space, 32 MiB growth per evidence bundle, or 128 MiB aggregate
evidence/profiler/cache growth. Stop also on source/config drift, any execution
fault, failed integrity/receipt/count check or attempted seventh bundle/fourth
audit. Halt further launches and retain partial evidence/logs; do not retry,
delete, reseal or fabricate completion. Stop at a boundary when possible; a hard
deadline may require terminating the monitored process and retaining incomplete
work. Crossing a limit is a profiling result, not permission to raise it.

## 6. Ranked minimum corrective options — proposals only

1. **Cache parsed schemas and validated validator objects.** Potentially large
   CPU/open reduction at low implementation risk; retain every instance validation
   and bind caches to frozen schema bytes. No scientific state or timing-root
   changes. Measure before adopting.
2. **Remove duplicate source-content hashing, then consider a frozen-source cache.**
   Eliminating the discarded inherited digest pass could remove 78 opens and
   920,549 logical bytes per outer call while retaining import-location checks
   and full Week 8 checks. Expected high harness benefit, moderate integrity risk.
   Caching across arms is a separate, higher-risk change: a stat-only cache does
   not preserve mutation detection. Require a protected immutable snapshot,
   complete membership checking and explicit start/final verification with a
   reviewed threat/durability contract. Never merely skip integrity checks.
3. **Bounded-memory writing and streaming audit/reconciliation.** Highest likely
   RAM benefit, moderate/high implementation risk; prioritize if measured peaks
   or credible object-growth projections exceed budget. Stream rows and hashes,
   retain only necessary identity/pairing state, and preserve exact quantiles via
   an explicitly reviewed external method if needed. Keep two complete semantic
   passes, ordering, duplicate/missing detection and summary equivalence. Changing
   quantile definitions or replacing validation with sampling changes evidence.
4. **Revisit synchronization only if it dominates.** Batching may help slow
   storage but changes crash-loss bounds. Moderate/high operational risk; requires
   an approved durability/checkpoint policy, bounded unflushed records and
   interruption tests. Keep synchronous per-row persistence for initial profiling.

Harness caching/streaming can preserve scientific reproducibility if exact
identities, row order/content, checks and timing boundaries remain unchanged.
All performance changes can affect cache state and observed latency and need a
new source freeze and resource/timing validation. Reordering/sharding trials,
reusing authenticated endpoints, caching PUF responses/decodes, altering noise or
protocol entropy, moving timing boundaries, or changing warm-up is scientific
methodology work; none is an interchangeable harness optimization.

## 7. Researcher budgets and formal authorization gates

Researchers must select a profiling host/owner and approve the proposed finite
benchmark and stop budgets. For the formal study, decide usable RAM with OS
headroom and no paging-dependent timing claim; disk allocation for the approximately
587 MB central raw estimate, variability, analysis, logs, backups and incomplete
runs; maximum execution/finalization/audit wall time; audit frequency; acceptable
restart cost; and durability requirements. No concrete formal RAM or time minimum
is defensible from the saved evidence. Do not reserve 190 GB as output storage:
that figure describes repeated logical hashing reads.

Before formal authorization: obtain bounded profiling results and an explicitly
conservative scale assessment, including the second-graph audit peak; implement
and test only justified harness corrections; resolve the methodology review's
analysis, precision, timing and diagnostic prerequisites; archive the reported
483-test checkpoint and hash-bound receipts for subsequent approved changes;
freeze source/configuration/plan/environment; review protected formal outputs,
completion/interruption handling and audit reproducibility; and obtain separate
explicit execution authorization. Current formal gates stay disabled. If small
fixtures cannot bound retained-object growth reliably, require a separately
approved synthetic evidence-processing profile before claiming formal RAM fits.

**Recommendation: ready for bounded profiling.**
