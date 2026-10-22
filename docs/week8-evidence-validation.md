# Week 8 validation-work accounting addendum — 2026-10-20

**Owner:** Will Wallace  
**Week:** 8
**Status:** Complete

## Status and historical evidence

The October 20 bounded nonformal pilot completed 50 matched trials and 150 arm attempts on one simulated population/device. It recorded 200 experimental PUF measurements, 100 runtime BCH decodes, 50 stored invocations, 136 authenticated sessions, 136 authorized recording-consumer releases, and zero unauthorized releases. The recording callbacks did not execute SNN or anomaly models.

The independent read-only audit returned **CONDITIONAL PASS — CORRECTABLE GAPS**. It found consistent source isolation, attempt records, summaries and release accounting, with no identified authentication bypass. It identified ambiguous validation-work scope and remaining formal-study prerequisites.

Preserved historical bundle,
`results/week-8/will/three-arm-auth-v1/nonformal/week8-three-arm-auth-v1-nonformal-20261020-001/`.
Its executed source ID is,
`83001370f5a65f5d8c6cb55c38bd6f239a6c693a065182b22e1b24575e695153`.
Its original attempts, source snapshots, manifests, receipts and completion marker have not been rewritten, regenerated, resealed or replaced.

The [pre-pilot implementation report](week8-three-arm-auth-implementation-report.md) and [static source manifest](week8-three-arm-auth-source-manifest.json) remain historical checkpoints. Their statements about missing tests and an unexecuted pilot describe that earlier checkpoint, not the completed pilot's current status.

The user reported 475 passing local PowerShell test executions before the pilot: 35 new three-arm, 203 pipeline/PUF/experiment, and 237 authentication executions. The independent auditor inspected source and saved evidence without rerunning those tests. The saved pilot bundle contains no archived test-execution receipts.

## Root cause and historical interpretation
`EvidenceRun.finalize()` first calls `reconcile()`, writes `validation.json`, and then calls `audit_evidence(require_marker=False)`. That audit calls `reconcile()` again. Only after both succeed does finalization create its completion marker. Each reconciliation regenerates enrollment/reference material and replays saved PUF measurements and BCH decodes. It does not add research attempts or samples.

The historical `validation_work` field is a valid **one-pass receipt with insufficiently explicit scope**: 200 replay measurements, 100 replay BCH decodes, one enrollment/reference reading, and zero statistical samples added.

Successful finalization therefore entails 400 replay measurements, 200 replay decodes and two validation reference readings. The later standalone audit, reported by the user, adds one further pass: 200/100/1. Across those three passes, the source-derived validation totals are 600/300/3, with zero added samples. These cumulative figures follow from the inspected call sequence and reported successful invocations; they are not new direct measurements or an execution ledger. The experimental enrollment/reference reading is separate setup work.

## Corrected future contract
Future receipts retain the scientific top-level counts and legacy `validation_work` one-pass alias. They add the separately versioned contract `validation_receipt_version="week8-three-arm-auth-v1:validation-work-v2"`,

- `per_pass_validation_work` explicitly gives one completed reconciliation's
  replay measurements, replay decodes, reference readings and zero added samples.
- `validation_scope="reconciliation-pass"` and
  `validation_passes_completed=1` apply to the `reconcile()` result and the saved
  `validation.json`. This file makes no assertion that finalization completed.
- `validation_scope="finalization"`, `validation_passes_completed=2`, and
  `finalization_validation_work` apply to the completion marker and successful
  `EvidenceRun.execute()`/`finalize()` return value. The latter is printed by the
  CLI's `run-nonformal` action. These fields are created only after both passes,
  the manifest audit and the final source check succeed.
- `validation_scope="standalone-audit"`, `validation_passes_completed=1`, and
  `standalone_audit_validation_work` describe the successful later audit's own
  work. The CLI's `audit` action prints this result. It does not combine the audit
  with prior invocations or modify any sealed file.
- `validation_work_basis="derived-from-completed-reconciliation-operations"`
  distinguishes operation-count accounting from independent resource profiling.

The existing marker's `validation_passes=2` remains compatible. The new `validation_passes_completed` always refers to its explicitly named scope. For a future run with the same allocation, per-pass work would be 200/100/1, finalization work 400/200/2, and each successful later audit's own work 200/100/1. These are contract examples, not results from a new pilot.

No existing attempt/plan/summary/config schema defines validation receipt scope. The new receipt version extends the separate validation/marker contract without changing those schemas, attempt identities, outcome definitions or denominators.

`per_pass_validation_work()` can interpret historical unversioned receipts without replaying or writing evidence. Full evidence auditing also accepts the legacy receipt/marker layout when all existing source/environment checks pass. It does not bypass those checks: corrected current source differs from the historical runtime snapshot. A full historical replay requires the appropriate frozen historical checkout and recorded environment. Do not rehash historical evidence to match the corrected implementation.

An exception or interruption returns no successful scoped result. A failed first reconciliation creates no validation receipt. If the second pass fails,
the already written one-pass receipt may remain alongside `INCOMPLETE.json`; no successful finalization totals or completion marker are issued. Partial work and failed invocations are not inferred from plan counts and remain unaccounted as completed work. There is no automatic retry or global audit accumulator.

## Correction validation and local commands
Eight focused tests were added to the existing three-arm suite. They cover actual replay-operation counts, both finalization passes, read-only standalone audit, partial/interrupted validation, legacy receipt interpretation/auditing, historical summary and file preservation, marker tampering and invalid receipt versions. Existing namespace, formal-gate, authentication and release tests remain.

The sandbox's existing `.venv` launcher reports no accessible Python at `C:\Users\wwall\AppData\Local\Programs\Python\Python312\python.exe`. No environment was recreated and no packages were installed. Behavioral tests remain pending local execution; static checks are not passing unittest results. Both the focused-suite command and existing experiment-evidence regression command exited 1 before test collection: zero tests executed. Stdlib syntax compilation passed for both changed Python files; AST inspection finds 43 test methods (35 existing plus eight added). AST comparison confirms unchanged metric, summary, protocol-validation, timing-validation and output-namespace functions. Preservation checks found all 97 historical bundle files unchanged, with all 95 manifest members and the completion marker's manifest hash still matching.

Run from local PowerShell using the existing environment. The test file already exists: do not reapply the historical fallback patch.

```powershell
Set-Location -LiteralPath 'C:\PUF+SNN_SharedRepo\PUF-SNN'
$env:PYTHONPATH = "$PWD\src\python;$PWD\tests"
& .\.venv\Scripts\python.exe -B -m unittest -v experiments.test_three_arm_auth_v1
if ($LASTEXITCODE -ne 0) { throw 'Three-arm accounting/regression tests failed.' }
& .\.venv\Scripts\python.exe -B -m unittest -v experiments.test_majority3_auth_v1 experiments.test_majority3_auth_corrections
if ($LASTEXITCODE -ne 0) { throw 'Existing experiment-evidence regressions failed.' }
```

Record actual terminal outcomes and counts. These commands run bounded unit fixtures in temporary storage; they launch no research pilot or formal study.

## Remaining formal-study prerequisites
The scientific outcomes and security boundaries are unchanged. Formal execution remains disabled. Outstanding work includes test receipts tied to frozen source, CPU/environment characterization, cold versus warmed and recurring-window timing decisions, paired statistical estimands, absolute-rate and zero-event uncertainty, population/control dependence, runtime/storage/peak-memory feasibility, protectedformal outputs, source/configuration freezing and separate execution authorization. This correction implements none of that preparation, optimization or execution.