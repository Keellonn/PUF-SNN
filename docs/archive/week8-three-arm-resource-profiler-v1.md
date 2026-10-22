# Week 8 isolated resource profiler v1

Implementation only. **No research run, benchmark session, historical replay, or
historical audit was executed.** This document supplies no execution approval.
The methodology review and resource-feasibility plan remain unchanged.

## Files and preservation

The original implementation added these three files. The safety correction edits
only these same three files:

- `tools/profile_three_arm_resources_v1.py`: standalone controller/worker utility.
- `tests/tools/test_profile_three_arm_resources_v1.py`: stdlib, tiny stub fixtures.
- `docs/week8-three-arm-resource-profiler-v1.md`: this usage and preservation report.

Production PUF/authentication/pipeline/experiment code, schemas, configurations,
allocation, source snapshots, research logs and historical evidence are preserved
as found. Existing checkout changes remain in place. The correction's preservation
comparison covers 1,857 other files under `src`, `configs`, `schemas`, `results`,
`docs`, `tests` and `tools`, excluding bytecode. The older `sim_results` tree is not
part of that hash claim: sandbox access to one of its directories is denied, and
no operation in this task writes there. No package installation, commit or push
occurred.
The profiler and its tests are outside the harness's source-snapshot membership;
future sidecars separately record the utility hash and invocation.

## Reviewed delegation boundaries

The Week 8 CLI loads `StudyConfig`, compiles the plan, then constructs
`EvidenceRun` with `RUN-150-NONFORMAL` and the reviewed canonical plan digest.
The profiler repeats the same validation and delegates the complete existing
`EvidenceRun` context manager and `execute()` lifecycle, without copying its loop.

Construction compiles again, checks the protected direct-child output namespace,
hashes current sources, writes `INCOMPLETE.json`, snapshots sources and opens JSONL.
`execute()` prepares enrollments/providers, hashes sources before every arm,
calls the evidence module's bound `execute_attempt()`, calls `append()`, and rejects
faulted rows. Every append retains schema validation, canonical serialization,
write, flush, fsync, and row retention.

Week 8 `source_hashes()` invokes the inherited Week 7 scan and then scans its own
superset. Both bindings and both `file_digest` bindings are measured. The
defining Week 7, imported Week 8, and inherited evidence-writer canonical bindings
are wrapped independently. The latter is labeled `canonical_evidence_week7` and
accounts for the inherited `write_json()` function's own globals. These aliases
delegate directly to their original serializer, not to each other's wrappers;
one serialization is attributed once. Writer inclusive time still overlaps it.
Both schema-validation functions retain schema parsing, self-validation,
validator construction and instance validation.

Finalization retains stream close/fsync, source-drift checks, the first
reconciliation and summary, JSON writes, manifest construction, the internal
manifest/source/snapshot audit, the second reconciliation/summary, and the final
source check. Only the existing successful finalizer writes the validated marker
and removes `INCOMPLETE.json`. The profiler also checks the returned 150-arm,
two-pass PASS receipt and marker/incomplete state. It never reseals evidence.

## Modes and commands

Use the researcher's validated Python 3.12/3.13 environment with the existing
project dependencies. Controller/test code needs only stdlib. Execution monitoring
supports Windows; missing required memory/free-RAM/disk metrics stop execution.
POSIX process groups exist for portable stub tests, not an approved research host.

Read-only plan/source/path inspection, **example, not executed**:

~~~powershell
python tools/profile_three_arm_resources_v1.py preflight --session first-20261020
~~~

Preflight prints canonical configuration/plan hashes, configuration byte hash,
source hashes, utility hash and prospective paths. It creates no evidence,
sidecar, worker, enrollment or authentication attempts and does not audit evidence.
Bytecode writes are disabled for harness imports. Independently review the current
plan; do not substitute a historical plan digest.

Dry-run configuration checking, **example, not executed**:

~~~powershell
$reviewedPlan = '<researcher-reviewed-current-canonical-plan-sha256>'
python tools/profile_three_arm_resources_v1.py dry-run `
  --session first-20261020 --reviewed-plan-sha256 $reviewedPlan
~~~

Dry-run requires the reviewed hash. If any resource budget is supplied, supply all
seven budgets; invalid, missing, nonfinite or nonpositive limits are rejected.
Without supplied limits, read-only modes report budgets as null. They never imply
that limits have been approved.

**Proposed first 150-arm command — NOT EXECUTED.** Separate researcher approval,
a working validated environment, host selection and budget selection are still
required. The following numerical limits are the feasibility plan's proposals,
not approved budgets:

~~~powershell
python tools/profile_three_arm_resources_v1.py execute `
  --session first-20261020 --pairs 1 --runs-per-pair 1 --audits 0 `
  --reviewed-plan-sha256 $reviewedPlan `
  --approval PROFILE-150-RESOURCE-V1 --authorization RUN-150-NONFORMAL `
  --bundle-seconds 900 --session-seconds 7200 `
  --memory-bytes 2147483648 --min-free-ram-bytes 2147483648 `
  --min-free-disk-bytes 2147483648 --bundle-growth-bytes 33554432 `
  --total-growth-bytes 134217728 --sample-seconds 0.05
~~~

That command would create only
`results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-resource-v1-first-20261020-p1-cold/`
and separate sidecars beneath
`tmp/week8-three-arm-resource-profile-v1/first-20261020/`.
Choose another unique lowercase session token if either output already exists.

For a separately approved complete arrangement, `--pairs 3 --runs-per-pair 2`
allows six bundles/900 arms maximum. Adding `--audits 3` also requires
`--audit-approval AUDIT-RESOURCE-V1`; only those newly created second bundles
are audited, once each, in separate monitored workers after all pairs succeed.
No arbitrary historical audit path is accepted. All limits are per exclusive
session; creating another session is a separate authorization decision.
There is no resume, retry, standalone arbitrary-audit, or formal-execution action.
`_worker` is an internal stdin-gated protocol. Authorization strings alone cannot
release research work: the supervision contract below is also mandatory.

## Corrected worker supervision contract

The controller creates an exclusive session, first commits an unsuccessful/pending
summary, and records its approved request in `request.json`. That request binds
the session token, exact pair/bundle/audit arrangement, configuration/source/plan
identities, controller PID, and all seven explicit budgets plus sampling/grace.
Workers require complete valid budgets, agreement with the recorded request and
its scalar budget fields, and the exact approved slot and evidence targets. Counts
cannot be enlarged by editing just the worker JSON. Exclusive once-only slot
claims remain mandatory, including for failed work.

Before releasing stdin, the controller attaches the worker to a uniquely named
Windows Job Object with kill-on-close, establishes the monitoring backend, checks
resources and opens a local duplex named pipe. Both peers verify the connected
process identity through `GetNamedPipeClientProcessId` /
`GetNamedPipeServerProcessId`. The worker requires that the server is its actual
parent controller. The handshake binds the full worker request, including its
slot, to the controller's in-memory request digest. This digest is an identity
comparison, not a new authentication/cryptography scheme.

On python.org Windows virtual environments, `launch_python()` starts
`sys._base_executable` directly with `__PYVENV_LAUNCHER__=sys.executable`, the same
environment setting used by CPython's venv redirector. This retains the current
virtual environment while avoiding an intermediate launcher process. The Popen
PID/handle, monitored interpreter, contained worker and pipe client are therefore
the same process, whose OS parent must still be the controller. Missing/invalid
direct-interpreter metadata fails closed. No ancestor-PID allowance or PID check
bypass is introduced. See the native integration validation below.

Before importing the study or claiming a slot, the worker opens that specific
named job, verifies its own membership using `IsProcessInJob`, and queries its
kill-on-close flag. Membership in an unrelated host/sandbox job is insufficient.
It immediately closes the query handle so the worker cannot keep the controller's
job alive after controller death. Missing APIs, wrong peers, missing budgets,
different requests, unavailable jobs or absent containment all fail closed.

Only the controller's resource-observation loop issues fresh heartbeat grants;
the pipe receiver thread cannot renew them. The worker checks the lease at safe
boundaries and runs a watchdog thread throughout imports, execution and reporting.
The lease expires after `max(2 seconds, 5 * sample_seconds)`. EOF, invalid/stale
heartbeats or lease expiry mark supervision lost and terminate the verified job;
an immediate process exit is the fallback. Diagnostic recording gets at most a
50 ms wait before emergency termination proceeds. Controller death independently
closes its final job handle and invokes OS process-tree cleanup.

Successful monitoring also requires the worker's containment acknowledgement and
a completion handshake bound to the exact worker-result file hash. A stale result
from a failed/replayed slot cannot establish completion of another worker.

This is a local execution-safety contract under nonmalicious local-user assumptions.
It does not defend against an administrator or a parent deliberately implementing
a counterfeit controller. Research execution requires Windows. Injectable unit
test seams exercise tiny stubs and do not provide an alternate CLI execution mode.

Native API references: [pipe server identity](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeserverprocessid),
[pipe client identity](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeclientprocessid),
[specific job membership](https://learn.microsoft.com/en-us/windows/win32/api/jobapi/nf-jobapi-isprocessinjob),
and [job lifetime/kill-on-close](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).

## Stop and reuse behavior

Limits are never raised automatically. They cover each bundle/audit, session
time, worker RSS/private bytes/OS peak working set, available RAM, free output
disk, each bundle's growth, and aggregate evidence/sidecar/compiler-cache growth.
Reaching a maximum or falling to a free-space minimum fails the session.
Unavailable required safety metrics also fail it.

Before releasing the worker's stdin gate, the controller installs a Windows
kill-on-close Job Object and checks resources. A limit writes a sidecar STOP flag.
Wrappers check it at safe operation boundaries; a `BaseException` stop escapes
ordinary runtime fault handlers. After the configurable grace (default two seconds,
maximum ten), the controller kills the contained process tree and waits for exit.
Keyboard interruption and monitor exceptions also clean up processes. No later
worker launches after failure. Partial evidence is retained unchanged and no
profiler success is reported, even if a scientific marker happened to finish
before the controller observed the violation. Hard kills may leave no worker
result; the parent summary still reports failure.

Controller and session exceptions retain structured `stage`, exception `type`,
and bounded `message` details in sidecars. Failed worker completion records exit
status, violations, result availability and whether supervision completion was
verified. Monitoring exceptions and keyboard interruption are recorded before
cleanup/rethrow; resource and final-acceptance failures remain unsuccessful.
Diagnostic writes are best effort if storage itself fails and never authorize
success or replace scientific evidence. A hard controller kill can leave only
the previously committed pending summary and existing logs.

## Final acceptance and publication

Only the session's `summary.json` is an authoritative profiler acceptance receipt.
It starts with `success: false`, `state: pending`, and stays unsuccessful during
worker activity and final checks. After all authorized workers return successful
validated results, the controller stages the candidate summary in
`summary.json.new`. It checks aggregate growth including that staging file, free
disk space and the final session deadline, and requires no outstanding errors or
violations. The final action is atomic replacement of `summary.json` with
`success: true`, `state: accepted`. No acceptance check or filesystem write follows
that commit. A `.new` file is never an accepted receipt, including after a crash.

Interruptions, scan/disk errors, resource violations, and failed staging/replacement
leave the authoritative receipt pending or unsuccessful. Completed scientific
markers may remain alongside failed profiler acceptance; the profiler neither
deletes nor reseals them. Atomic replacement describes process-interruption
ordering, not a stronger guarantee of directory/power-loss durability.

Each pair starts a fresh interpreter with an exclusively new requested
`NUMBA_CACHE_DIR`. The second bundle runs in that interpreter after the first
active run object has been released and garbage collection requested. The
production runtime still creates fresh endpoints and admission/session state per
arm; no capability is reused by the utility. The unchanged experiment profile
remains `cold-process-no-harness-warmup-v1`. “Process-reused” does not mean the
future formal warmed methodology, empty dependency caches, or a machine-cold host.

## Measurements and interpretation

Parent summaries record launch-to-observed-exit monotonic wall time, requested
sampling interval and largest observed gap, sampled RSS/private-byte peaks,
OS lifetime peak working set, CPU time, process logical I/O counters, free RAM/disk,
directory logical bytes and file counts. Sampling requests 50 ms by default;
directory scans and scheduler delays can increase actual gaps. Startup and each
bundle/audit have separate sampled memory maxima. A reused process shares the OS
lifetime peak: never subtract cumulative peaks to estimate the second bundle.
CPU and I/O counters are cumulative worker counters, not phase-specific deltas.

Worker results buffer bounded aggregate calls/durations/bytes, split into startup,
process-cold, process-reused or standalone-audit phases. They include imports,
writer setup, population setup, execution including finalization, each
`execute_attempt`, append, source scans/file digests, both schema-validation paths,
validator construction/schema self-check, canonical serialization, JSON writes,
Python-visible stream write/flush/fsync, each reconciliation/summary, finalization
and internal/standalone audit. Individual reconciliation/finalization/bundle spans
are also retained. The first bundle/audit deadline includes launch/imports;
the second bundle receives a new deadline. No per-arm synchronous profiler log is
written. Stdout/stderr, request, progress, latest monitor snapshot, worker result
and parent/session summaries remain outside sealed evidence.

Inclusive spans overlap. Exclusive durations subtract only observed direct
children. Do not sum inclusive append/schema/serialization/fsync or
finalization/audit/reconciliation durations. Week 8 source-scan logical bytes
include inherited Week 7 bytes: do not add those scan totals. File-hash inputs
use observed input file sizes, appropriate for the frozen files; they include
snapshot/artifact hashes separately from the nested source-scan byte totals.
These are logical input bytes, not physical disk throughput. Authentication stage
timings in evidence are not total experiment wall time.

Wrappers pass original positional/keyword arguments unchanged, call originals once,
return original values, rethrow original exceptions and restore all bindings in
reverse order after any exception. C-call profiling observes I/O without replacing
stream objects, JSON formatting, validation, hashing, fsync or integrity checks.
Profiling adds hook dispatch, clocks, input-size stats, configuration drift reads,
extra preflight/drift checks and directory scanning. Observer cost is not subtracted
or claimed to be negligible. The supervision pipe and watchdog add scheduling,
thread and heartbeat overhead as well.

Resource limits remain sampled stop thresholds, not kernel RAM/disk quotas.
Detection may lag a transient allocation or write; monitor scans, scheduler delays
and graceful-stop latency can permit overshoot. A slow monitor can expire the
supervision lease and stop a run even without a measured resource violation. The
Python watchdog depends on thread/GIL scheduling; kill-on-close and the external
controller remain independent protections against controller death and budget
violations respectively. No hard real-time or instantaneous-peak claim is made.

Unavailable without broader instrumentation or host evidence:

- Separate child-process CPU/memory/I/O (including short-lived Git children).
  Children are contained and cleaned up; the worker counters exclude them.
- Physical disk throughput, allocated disk blocks, page-cache hits, all compiler
  cache hits, guaranteed instantaneous peaks, total Python heap size or energy.
- Separate manifest-construction/verification root durations; these are included
  in finalization/audit plus file-hash/JSON spans. Individual manifest file hashes
  are aggregated, not retained as an unbounded event stream.
- Implicit close-time/OS/cache flushes and directory durability. Explicit
  Python-visible flush/fsync counts are observed, not stronger durability claims.
- Separately labeled first/subsequent BCH decode and JIT compilation phases,
  uninstrumented thread activity, or an exact attempt-loop-only root.
- Storage type/filesystem, power policy, effective hardware/thread settings beyond
  recorded environment variables, background load and interruption provenance.
  Researchers must supply host notes. Evidence already retains dependency versions;
  sidecars record Python/OS/CPU/core/clock/cache settings and their own identity.

## Historical validation before these corrections

Executed with available `C:\msys64\ucrt64\bin\python.exe`, Python 3.12.7:

~~~powershell
python -m unittest discover -s tests/tools -p 'test_profile_three_arm_resources_v1.py' -v
python tools/profile_three_arm_resources_v1.py --help
python -m py_compile tools/profile_three_arm_resources_v1.py tests/tools/test_profile_three_arm_resources_v1.py
~~~

Original implementation report: **33 tests passed, zero failures/errors/skips**
(0.625 seconds). CLI help and Python syntax compilation also passed.
Tests use temporary files and tiny mock/stub lifecycles, not actual 150-arm
experiments. Real OS tests inspect the test process and terminate tiny sleeping
processes, including a descendant, to validate Windows APIs and cleanup.
Fixture receipts are temporary test assertions, not research/profiler results.

Subsequent researcher-reported local validation in the project `.venv` established:

- All 33 original profiler tests passed.
- Real-environment preflight passed.
- The corrected reviewed-plan dry-run passed using
  `74a07b7b06edee5dd58b9ad594fe70d00859ea1c4bceeaec2fb6bac52821a016`.
- Dry-run reported one bundle, zero audits, `budgets: null`, and
  `experiment_executed: false`. No profiling benchmark was executed.

Those historical steps are distinct from the corrected suite below. Preflight and
dry-run do not install the instrumentation or prove real monitored execution safety.
The prior 483-test research checkpoint was not rerun and is not part of these counts.

## Safety-correction validation

At this historical checkpoint, an unprivileged sandbox launch of
`.venv/Scripts/python.exe` reported no Python at the configured user Python312
path. No dependencies or interpreters were installed or replaced. Actual
corrected-suite command:

~~~powershell
& C:\msys64\ucrt64\bin\python.exe -B -m unittest discover -s tests/tools -p test_profile_three_arm_resources_v1.py -v
~~~

Result: **53 tests passed, zero failures/errors/skips**, using Windows Python
3.12.7 (5.084 seconds). This includes 20 added tests and updated original fixtures.
The first expanded run exposed two fixture/failure-reporting issues; those were
corrected before the passing final suite. Tests remain isolated from research work.

New coverage includes complete worker budgets, approved-session arrangement/budget
binding, wrong controller identity, direct worker refusal, once-only slots,
OS pipe/job supervision with a tiny fake two-bundle lifecycle, containment/peer
refusal, heartbeat expiry, listener cleanup, and abrupt controller death killing
the verified worker and its sleeping descendant. Failure injection covers pending
and accepted publication order, growth/disk/deadline violations, keyboard and
filesystem failures between final checks, failed success staging/replacement,
preservation of a completed fixture marker, structured monitor/session errors,
and inherited evidence canonical bytes/counters/restoration.

Real Windows tests exercise native pipes, membership queries, job flags, process
counters and process termination. Other lifecycle tests use explicitly injected
supervision fakes. No real `EvidenceRun`, enrollment, authentication, PUF acquisition
or 150-arm workload executes in this suite. Full project-dependency/jsonschema-hook
integration under supervised execution, other Windows versions/nested-job policies,
and behavior under actual host pressure remain untested. Source inspection retains
the unchanged real `EvidenceRun` lifecycle delegation and formal-execution gates.

AST syntax parsing passed for both Python files; this is separate from behavioral
test execution. Source comparison confirms unchanged `run_bundle`, `check_config`,
`check_approval`, `preflight`, `layout`, `io_schema_profile` and `patched` functions.
The final preservation comparison found zero changes among all 1,857 protected
files, including 1,441 files under `results`. `git diff --check` returned zero.
Because the three profiler files are untracked, each was also checked with
`git -c core.autocrlf=false diff --no-index --check -- /dev/null <file>`: no
whitespace diagnostics (exit 1 denotes the expected file addition).

Local repeat command, when the existing project environment is accessible:

~~~powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests/tools -p test_profile_three_arm_resources_v1.py -v
~~~

Ready for independent re-audit of the corrections, not benchmark authorization.
No new preflight, dry-run, historical audit, research experiment or resource
benchmark was executed during this correction task. Formal execution stays disabled.

## Native Windows integration correction, 2026-10-20

The subsequent native run invalidated the assumption that the 53-test MSYS2/UCRT
checkpoint established python.org venv compatibility. This correction reproduced
the exact reported result in the project `.venv`: **53 tests, 48 passes, four
failures and one error** (2.383 seconds). The unchanged suite also passed under
MSYS2/UCRT: **53 tests, zero failures/errors/skips** (5.068 seconds).

An unprivileged launch still reported the inaccessible user Python path. An
elevated execution of the explicitly authorized stub suite successfully accessed
the existing native interpreter. No installation, venv repair or dependency
change was needed. The versions actually observed were:

- Project `.venv`: python.org CPython **3.12.4**, MSC v.1940, 64-bit AMD64;
  `C:\PUF+SNN_SharedRepo\PUF-SNN\.venv\Scripts\python.exe`.
  Its base interpreter is
  `C:\Users\wwall\AppData\Local\Programs\Python\Python312\python.exe`.
- MSYS2/UCRT: CPython **3.12.7**, GCC UCRT 14.2.0, 64-bit AMD64;
  `C:\msys64\ucrt64\bin\python.exe`.

### Actual root cause and correction

The approved controller PID was correctly populated from the controller's
`os.getpid()`. Both normal `execute()` and the native fixtures then launched
`sys.executable` through Popen. In a python.org Windows venv that executable is a
redirector that starts a second process containing the actual interpreter.
A print-only OS PID probe observed controller **27128**, Popen/redirector
**27144**, and actual worker **10164**, whose `os.getppid()` was **27144**.
The expected direct relationship was absent. MSYS2's tested non-venv executable
starts the interpreter itself, so it did not expose this issue.

- Failure A: the legitimate stub failed the actual-parent check before claiming
  its slot or loading the harness. This was a launch defect shared with production,
  not an incorrect approved controller PID.
- Failure B: the healthy stub likewise failed the parent check in
  `WorkerSupervision.__enter__()`. It exited before verified completion, with no
  resource violation; an empty violations list does not imply profiler success.
- Failure C: the worker failed before entering its supervised block, creating its
  descendant, or writing readiness. Buffering did not cause the absent marker.
- Failure D: the worker failed before starting the heartbeat watchdog. No
  supervision-loss receipt was expected at that stage. Additionally, emergency
  watchdog termination cannot guarantee diagnostic persistence.
- Failure E: the direct worker correctly failed closed at an earlier guard; the
  test's required error substring was too specific.

Removing only the parent check would not fix the topology: the pipe-client PID
would still differ from Popen's PID, metrics would inspect the redirector, and
late attachment of a redirector cannot establish that its already-created
interpreter child belongs to the new controller job. `launch_python()` instead
removes the intermediate process from monitored launches. A second print-only
probe verified controller **23568**, Popen/worker **1140**, worker parent **23568**,
and unchanged venv executable/prefix. The approach follows
[CPython's redirector source](https://github.com/python/cpython/blob/v3.12.4/PC/launcher.c)
and [path initialization](https://github.com/python/cpython/blob/v3.12.4/Modules/getpath.py).

Only process launching and fixtures changed. The actual-parent checks, OS pipe
peer checks, exact request/budget/slot binding, specific-job membership query,
kill-on-close, monitor-issued heartbeat grants and final acceptance publication
remain mandatory. The new environment variable selects interpreter paths; it is
never treated as proof of supervision or authorization.

### Corrected fixtures and final validation

Monitored stub launchers now use the production launch helper. Successful tests
assert actual worker PID/parent and unchanged executable/venv prefix, and record
readiness only after supervision establishment. The controller-death fixture
launches the actual controller and sleeper directly and verifies the expected
controller/worker relationship before killing the controller.

The heartbeat fixture writes readiness inside established supervision before
withholding further grants. It requires exit code 70, no resource-limit violation,
no unsafe continuation and no worker success result. An emergency diagnostic,
when present, must identify supervision loss; its absence does not excuse any
termination or no-success assertion. The new diagnostic-storage test independently
exercises a real unavailable output directory. Direct-worker rejection now checks
failure, no slot claim, no research output, no worker result and no accepted
session receipt without depending on one error string.

A new Windows regression queries the launched process with native
`GetProcessId` and `QueryFullProcessImageNameW`. It checks the base-interpreter
image, agreement between the process handle and executing PID, the actual parent
PID, preserved executable/prefix/base-prefix, and preservation of supplied
environment values. PID returns are not mocked.

Final full-suite results: **55 tests passed, zero failures/errors/skips** in each
environment: native project `.venv` **4.862 seconds**, MSYS2/UCRT **5.130 seconds**.
The five previously failing/erroring methods all passed. Repeat from the repo root:

~~~powershell
& .\.venv\Scripts\python.exe -B -m unittest discover -s tests/tools -p test_profile_three_arm_resources_v1.py -v
& C:\msys64\ucrt64\bin\python.exe -B -m unittest discover -s tests/tools -p test_profile_three_arm_resources_v1.py -v
~~~

The existing interpreter environment is now tested for stub integration. Real
`EvidenceRun`, enrollment, authentication, PUF acquisition, full dependency/hook
integration under research execution, other Windows versions/nested-job policies,
and operation under host pressure remain untested here. The helper relies on
CPython's internal `_base_executable`/`__PYVENV_LAUNCHER__` interface; new interpreter
versions or distributions require equivalent native validation.

Only the profiler, its test file and this document were edited. The final SHA-256
comparison found **zero changed, added or removed files among 1,857 protected
files**, including **1,441 files under results**. It covers `src`, `configs`,
`schemas`, `results`, `docs`, `tests` and `tools`, excluding the three authorized
files and bytecode. Existing production edits, historical outputs and research
logs were preserved. `git diff --check` and the three untracked-file whitespace
checks produced no diagnostics. No real-harness preflight, dry-run, historical
audit, pilot, resource benchmark or research experiment ran. Formal execution
remains disabled. Because production launch
semantics changed, a focused independent review of launch/containment/identity
is recommended before the first benchmark; the earlier source-only PASS does not
authorize this changed implementation. The first real benchmark remains blocked.
