# Week 9 — Windows Monitoring Remediation

Date: October 28, 2026
Affected interrupted run: `week9-shared-noise-calibration-v1-20261029t003215z-d55070ef`.

## Finding and attribution

The best-supported failure class is an incompatible open reader blocking Windows atomic rename. The actual traceback is `save_json` → `Path.replace` → `os.replace`, replacing `worker/monitor.json.new` with `worker/monitor.json`, `PermissionError [WinError 5]`. The preserved file contains 828 published samples; the uncommitted candidate contains sample 829. There is no recorded numerical resource-budget violation.

Isolated native fixtures reproduced the exact same WinError 5 while (1) an ordinary Python binary reader held the destination open and (2) an actual Windows PowerShell `Get-Content -ReadCount 1` pipeline was paused during enumeration. After each reader closed, the same original writer succeeded with unchanged permissions. The first 828 successful original replacements, reproducible lock/unlock behavior, and preserved inherited ACLs support a sharing race rather than a static access-control denial. There is no captured handle-owner trace proving the original agent read was the blocker; antivirus, indexing, or another transient holder cannot be retrospectively excluded. Only the failure class, not the historical lock owner, is confirmed.

The earlier authorization/provenance validation receipt records the same WinError 5 on `progress.json.new` → `progress.json` during the two-phase stub. The historical monitor reads `progress.json` with `Path.read_text`, so the worker's phase update can race its own controller reader. No historical blocker trace survives. This is a mechanism-level connection, not a claim that the two lock holders were identified.

Microsoft documents that sharing modes last for the open handle's lifetime and that delete sharing affects rename access: [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew). Merely adding FILE_SHARE_DELETE did **not** permit Python `os.replace` against a held destination on this host. The native API matrix found that ReplaceFileW with share-delete succeeded in a one-handle fixture, but repeated concurrency and a real supervised fixture exposed a missing-path observation and error 1175. That candidate was rejected; [ReplaceFileW documents distinct partial-failure outcomes](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew).

The initial reproduction receipt's prose prematurely anticipated that share-delete alone would succeed; its actual recorded result is false. Use the API matrix and this final finding rather than that sentence. `focused-1.json` preserves the rejected API candidate's failures; `focused-2.json` preserves an intermediate snapshot-yield programming defect. Both are resolved by the final implementation and `focused-3.json`; no scientific experiment was retried.

## Exact changes and ownership

All implementation changes are confined to Will's Week 9 calibration files:

| File | Change |
| --- | --- |
| `src/python/puf_snn/experiments/shared_noise_calibration_monitor_v1.py` (new) | Coordinated sidecar I/O, immutable status snapshots, finite sharing retries. |
| `src/python/puf_snn/experiments/shared_noise_calibration_resources_v1.py` | Apply the adapter to the already privately imported Week 9 supervisor instance; add read-only diagnostic status function. |
| `src/python/scripts/run_shared_noise_calibration_v1.py` | Add `status --output <run>` action. |
| `src/python/puf_snn/experiments/shared_noise_calibration_evidence_v1.py` | Add only the new monitoring test to future required-source snapshots. All package Python sources, including the new adapter, are already included automatically. |
| `tests/experiments/test_shared_noise_calibration_monitor_v1.py` (new) | Deterministic retry/concurrency/snapshot tests and real native success/failure fixtures. |
| `docs/week9-shared-noise-monitoring-remediation.md` (this file) | Investigation, validation, safe inspection procedure, and restart gates. |

Operator helpers and generated receipts are listed below. The shared `tools/profile_three_arm_resources_v1.py`, its historical tests, all scientific configs, noise/runtime/reconstruction/analysis/selection/authentication implementations, schemas, frozen methodology, and existing calibration tests are unchanged. The user's pre-existing research-log edit was not touched. No shared-file ownership exception was needed.

## Correction and failure boundaries

The adapter replaces only `read_json` and `save_json` on `_shared_noise_calibration_windows_primitives_v1`, the existing privately imported Week 9 module instance. It does not edit or patch the separately imported historical supervisor module. The original monitor loop, OS metrics, process/job containment, peer checks, heartbeat protocol, worker watchdog, resource calculations, stop grace, and controller evidence acceptance remain unchanged.

Each normalized absolute sidecar path maps to a Windows named mutex. Writers acquire it for staging and original `os.replace`. Readers acquire the same mutex, copy at most 1 MiB, close the file, release the mutex, and then decode/parse the detached snapshot. A returned snapshot can be held while publications continue; it has no live file handle or held mutex. Readers and writers in the same Windows session/account context coordinate across processes. The `Local` mutex namespace and default Windows security descriptor are explicit deployment boundaries; this is not hostile-user isolation or cross-session coordination. Microsoft specifies the cross-process named-mutex contract in [CreateMutexW](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-createmutexw).

Lock wait is at most **50 ms**. Only replacement errors WinError **5, 32, 33** are eligible for retry, at 10 ms intervals, with **at most six calls total** and a **50 ms deadline from the first eligible failure**. A scheduler overrun causes rethrow without another call. Other errors, interrupted execution, staging/write failures, invalid JSON, oversized reads, and lock failures propagate. Permission errors are not presumed transient: persistent ACL denial also exhausts the bound and stops the worker. There is no non-atomic rewrite fallback and no automatic run retry.

The maximum programmed wait contribution is 50 ms for the mutex plus 50 ms for replacement retries. Local OS calls and scheduler delays are not made preemptible by this policy; no hard real-time guarantee is claimed. No heartbeat or resource sample is synthesized during waits. The existing monitor loop remains the heartbeat source, and the worker's 2-second stale-supervision watchdog plus containment remain active. A persistent publication failure escapes into the original supervisor's `finally` cleanup, terminates the job/worker, records failure, leaves authorization consumed, and prevents controller completion. Atomic scientific evidence sealing is unchanged; this adapter never publishes experiment evidence.

## Safe interactive status inspection

Use the Week 9 CLI, from the same Windows session/operator context as the controller:

```powershell
.\.venv\Scripts\python.exe src/python/scripts/run_shared_noise_calibration_v1.py status --output results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t003215z-d55070ef
```

It returns `diagnostic_only: true`, the copied monitor record, and whether a completion-marker file is present. It neither certifies evidence nor proves the worker is currently alive; old snapshots remain old. An absent initial monitor is reported as null; other errors are explicit. It does not load or consume approval, execute observations, audit/replay evidence, or write the bundle/sidecars.

Avoid direct `Get-Content`, `Path.read_text`, editor/file-tail tools, or other uncoordinated opens of live `monitor.json` or `progress.json`. They bypass the mutex and can still block Windows rename. Brief external holds can recover within the bounded retry; a long hold intentionally causes fail-closed termination. The supported status interface prevents its own interactive reads from retaining a conflicting handle. Closed historical/incomplete sidecars can still be read ordinarily when no writer is active.

## Validation results

| Suite | Tests | Failures / errors / skips | Seconds |
| --- | --- | --- | --- |
| focused-3 | 15 | 0 / 0 / 0 | 41.862 |
| baseline-65 | 65 | 0 / 0 / 0 | 51.374 |
| baseline-55 | 55 | 0 / 0 / 0 | 5.864 |
| baseline-62 | 62 | 0 / 0 / 0 | 15.065 |

The original **182-test baseline passed**, plus **15 new tests**, for **197 passing tests**. Exact methods, source hashes, environment and fixture metrics are retained in each receipt. The unchanged historical supervisor suite includes exception/KeyboardInterrupt cleanup, lease/stop behavior, finalization failures, and completion-publication checks. The calibration/authorization baseline retains consumed-ID rejection, missing/corrupt consumption refusal, interruption, no false marker, replay/manifest checks, and independent cross-sigma 10,000-draw reference arithmetic.

The new tests cover coordinated periodic monitoring/progress writes and repeated readers; held detached snapshots during replacement; temporary incompatible actual Windows handles; persistent incompatible handles; bounded deadline/attempt limits; scheduler overrun; non-sharing failures and KeyboardInterrupt propagation; lock contention and cleanup; parser/size-limit cleanup; private-module scope; read-only status dispatch; and real worker cleanup/consumption semantics.

Deterministic thread concurrency: 200 publications and two readers of 200 snapshots each, separately for monitor and progress, with zero inconsistent/missing snapshots or errors. Tests retain actual operating-system sharing errors rather than treating every PermissionError as a confirmed lock.

### Successful native supervised fixture

This is a temporary **fixture-only** 1-group/1-device/2-trials-per-sigma allocation, not calibration evidence: **16 attempts, 8 paired identities, 32 readings, 16 runtime BCH decodes**. It exercises actual Windows process/job supervision, peer-verified pipes, periodic metrics, lease checks, source validation, two-pass reconciliation, controller acceptance and completion publication.

Observed workflow: **17.016 seconds**, **247 monitor samples**, requested interval 0.05 s, maximum observed sample gap **0.094 s**, peak sampled private bytes **1,498,292,224**, RSS **266,854,400**, no resource violations. The independent inspector process made **4,097 reads** across **225 distinct published samples**, with zero errors, while retaining an unchanged detached snapshot.

Both finalization passes succeeded: **64 additional replay readings, 32 replay decodes, two reference readings**, zero added samples. Standalone audit passed and adds its separately recorded one-pass verification work. Reusing the consumed fixture authorization was refused before launch. This small fixture validates supervision/concurrency correctness, not full-calibration resource feasibility.

### Persistent failure native fixture

An actual ordinary reader held the live destination after the fixture had persisted **1 attempt**. It caused **6** replacement failures (WinError 5); the adapter exhausted its fixed bounds and propagated the exception. Actual worker termination was confirmed by its process handle. Incomplete evidence and staged diagnostics remained; no calibration completion marker appeared; the fixture authorization stayed consumed. Reuse was refused without a launch, and ledger bytes remained unchanged. All fixtures use automated fixture identities and isolated temporary namespaces; no scientific authorization was created.

The original 543-attempt scientific bundle has not undergone reconciliation, statistical analysis, selection, or resealing during this task. Fixture markers are never attributed to that run.

## Scientific integrity and frozen identities

All configuration-file bytes and every non-I/O scientific source in the previous required set are unchanged. This includes seeds, 4×6×20 allocation, four sigma conditions, rho=0 noise law, manufacturing variation, BCH and credential settings, matched schedule, bootstrap/selection thresholds, resource budget and final-disable flag.

| Identity | Exact current value |
| --- | --- |
| config_sha256 | `79a275d06a8a1997981484f15d27cb5e76b39fd2a28b660a4251ddc35e83e756` |
| plan_sha256 | `e5d4deaf8b944dd514fbdcf2bba31cd91ec5dc22e66478ca8a55701a594135ff` |
| source_id | `a888acae484452b4a85c8442c6d5c3d7fa39b555d27b699bd4f0eaf37fbaf5f6` |
| environment_sha256 | `6ef3b0cf006b693d9e8622044e7bd833299773c11b7276298a55caec713d2174` |
| specification_sha256 | `f5a12c19e9228860b901e9abb0eee4c16aa4dbaa785bbea32fa4b5e31b244b23` |

Only the source ID changes; configuration, canonical plan, environment, and specification digests match the pre-remediation freeze. The new required set contains 116 files (previously 114); the new adapter and test are frozen for later runs. No prior source snapshot or approval is rewritten to match this new source.

All files under the interrupted bundle, its supervisor sidecars, its consumed authorization reservation, and the Task 2H receipts/results were compared byte-for-byte by SHA-256 against the pre-edit inventory and remain unchanged. The original completion marker is still absent. Source drift in the current checkout is disclosed; any old-bundle analysis needs its preserved source, not a fabricated current-source audit. The interrupted results report remains untouched and its scientific values remain unassessed.

## Artifacts and reproducibility

- [Receipt directory](../results/week-9/will/monitor-remediation-v1/monitor-remediation-20261028-01): pre-change `before.json`; `root-cause-reproduction.json` with actual traceback, ACL, prior failure and reader tests; `native-replacement-matrix.json`; all three development-focused test logs/JSON receipts; final `focused-3.json`; `baseline-65.json`, `baseline-55.json`, `baseline-62.json`; fresh `final-plan.json`, `final-preflight.json`, `final-status.json`; and `final-validation.json` with the complete new source identity, changed/added-file hashes and preservation checks.
- [Operator helpers](../tmp/week9-monitor-remediation-20261028-01): `investigate.py`, `probe_replacement.py`, `validate.py`, and `finalize.py`. They run only read-only planning/status/integrity actions, isolated reproductions, tests and report generation.
- [New regression tests](../tests/experiments/test_shared_noise_calibration_monitor_v1.py) and [sidecar adapter](../src/python/puf_snn/experiments/shared_noise_calibration_monitor_v1.py) are part of future frozen evidence.

Reproduce tests with native `.venv\Scripts\python.exe`, `PYTHONPATH=src/python;tests;.` and unittest modules listed in the receipts. The historical resource suite uses `tests/tools/test_profile_three_arm_resources_v1.py` discovery/import with the repository root available. No dependencies were installed. Test timings and tiny fixture outcomes are not scientific measurements or independent reproduction by another researcher.

## Recommendation and exact restart blockers

**GO for prospective restart preparation: the monitoring defect is remediated and all required validation passes. NO-GO for execution under the old authorization or this remediation task.** There are no unresolved implementation/test blockers identified within the supported same-session status procedure.

Before any scientific restart:

1. Obtain a new explicit approval-v2 authorization for one complete calibration, using a unique authorization ID and new run/output/sidecar identity. Bind the new source freeze, unchanged scientific plan/configuration/specification, environment, and actual resource budgets. Set `previous_failed_authorization_id` to `task2h-20261029t003215z-d55070ef` and record the monitoring I/O interruption honestly as the restart reason. The old reservation stays consumed.
2. Repeat native read-only plan/preflight and current RAM/disk/resource checks immediately before authorization. Verify the new output/sidecar do not exist and all current source hashes match the tested freeze; any further change requires a new freeze and review.
3. Use the coordinated status command in the same Windows session/operator context. No uncoordinated live readers or editors should hold the sidecar files. Persistent external locks and genuine filesystem/ACL faults remain intentional abort conditions, not errors to suppress.