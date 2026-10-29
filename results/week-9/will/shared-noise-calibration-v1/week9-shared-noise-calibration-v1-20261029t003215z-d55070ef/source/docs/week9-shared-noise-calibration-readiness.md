# Week 9 Shared-Noise Calibration Validation and Readiness

**Owner:** Will Wallace  
**Week:** 9
**Status:** In-Progress

`457050b5361389364fbded464455f1f8684dbe5a`.

Development chronology: Shared-Noise Calibration Implementation preceded Execution Authorization and Provenance remediation.


## Audit findings and corrections
The initial calibration approval identified frozen inputs but lacked a unique authorization, run and canonical output binding. Its successful controller test used a mocked scientific receipt. Approval-v2 requires all three identities, experiment/rules versions, five freeze digests, exact budgets, approver and timestamp. An exclusive reservation directory atomically consumes its authorization ID before worker launch. Its durable, read-back-validated consumption receipt is checked at worker admission, live permit boundaries, controller acceptance and standalone evidence audit. Missing, corrupt or partially written receipts fail closed; the reservation stays consumed. Worker failure, interruption, setup failure and marker-publication failure never reset it. Concurrent invocations have one reservation winner. Existing output or sidecar paths also prevent overwrite/resume.

A restart requires a separately supplied approval with a new authorization ID, run ID and output path. `previous_failed_authorization_id` and `restart_reason` record its relationship to the old incomplete invocation. Prior output, sidecars, consumption and lifecycle receipts are retained. Completed invocations cannot be referenced as failed restarts. Hard interruptions may leave only the reservation; no incomplete receipt is automatically repaired or recycled.

The initial calibration selection receipt copied execution approval without a distinct selection timestamp or acknowledgment. Selection-v2 records algorithm and rules versions, run/config/plan/source identities, core evidence-file hashes, summary and analysis hashes, all four candidates and their gate outcomes, computed selection or explicit no-qualification, and a timezone-aware computation timestamp. Audit deterministically recomputes and compares it against replay-validated evidence.

Acknowledgment-v1 is a separately supplied named, dated recorded attestation, bound to that selection, analysis, frozen inputs, evidence, final manifest and completion marker. It must postdate both computation and completion. It is stored exclusively outside the sealed bundle, so acknowledgment does not rewrite experimental outcomes. Execution approval cannot serve as acknowledgment. A no-qualification result can be acknowledged with null sigma and remains ineligible for final-study planning. Certified evidence, verified computation and recorded acknowledgment are distinct statuses. Unacknowledged results and every fixture remain ineligible for planning; final evaluation is always disabled. There is no final-execution action.

## Version and file inventory
The experiment/config/plan/attempt/summary versions and proposed-rules-v1 remain unchanged. New bundles use `:bundle-v2`, approvals `:approval-v2`, computational selections `:selection-v2`, consumption `:consumption-v1`, acknowledgment `:acknowledgment-v1`, and algorithm `:selection-algorithm-v1`. Old approval-v1 is preserved but rejected for new execution. Old bundles require their preserved implementation; new audit does not silently reinterpret them.

Execution Authorization and Provenance remediation modifies these initial implementation files,
- `src/python/puf_snn/experiments/shared_noise_calibration_v1.py` (schema revision dispatch only)
- `src/python/puf_snn/experiments/shared_noise_calibration_evidence_v1.py`
- `src/python/puf_snn/experiments/shared_noise_calibration_resources_v1.py`
- `src/python/scripts/run_shared_noise_calibration_v1.py`
- `tests/experiments/test_shared_noise_calibration_v1.py`
- `docs/week9-shared-noise-study-specification.md` (implementation appendix only)
- `docs/week9-shared-noise-calibration-readiness.md`
- `docs/week9-shared-noise-calibration-dry-plan.json`
- `docs/week9-shared-noise-calibration-preflight.json`
- `docs/week9-shared-noise-calibration-validation.json`

Execution Authorization and Provenance remediation adds these files,
- `src/python/puf_snn/experiments/shared_noise_calibration_authorization_v2.py`
- `src/python/puf_snn/experiments/shared_noise_calibration_provenance_v2.py`
- `schemas/shared-noise-calibration-approval-v2.schema.json`
- `schemas/shared-noise-calibration-selection-v2.schema.json`
- `schemas/shared-noise-calibration-consumption-v1.schema.json`
- `schemas/shared-noise-calibration-acknowledgment-v1.schema.json`
- `tests/experiments/test_shared_noise_calibration_authorization_v2.py`
- `docs/archive/task2f-calibration-readiness-v1-20261028/snapshot-manifest.json`

and its 18 byte-for-byte superseded calibration implementation files, listed with hashes in that manifest.

The configuration, analysis and runtime scientific code, oscillator/BCH/authentication components, legacy formal configurations and historical evidence are unchanged. The archive is a readiness snapshot, not experimental evidence. The three refreshed JSON readiness receipts are excluded from runtime source identity to avoid self-reference; this report and specification are included. Full current identities and source hashes are in the refreshed preflight and validation receipts. Do not use the archived freeze for modified source.

This documentation-only naming cleanup changes the two hashed Markdown sources. The saved JSON receipts and validation results below describe the pre-cleanup source freeze; they have not been rewritten. Obtain a fresh preflight/source freeze before requesting authorization for the edited documentation.

## Deterministic validation
The native CPython 3.12.4 Windows environment is unchanged; no dependency installation was performed. Exact suite names, method IDs, counts, durations, metrics and tested source hashes are machine-recorded in `week9-shared-noise-calibration-validation.json`. One existing 55-test supervisor pass encountered a transient Windows sharing violation replacing `progress.json` between its stub cold/reused phases. The worker failed closed; the unchanged suite passed on rerun (55/55). Both results are retained in the validation receipt. This intermittent I/O failure affects availability, not acceptance of bad evidence; the new single-bundle native calibration fixture succeeded. No automatic scientific retry was introduced. The earlier development pass found one old test setup missing `enrollments.json`; that fixture setup was corrected before final validation.

The focused suites cover exact output/run binding, all frozen identities, reuse after success/failure/interruption, concurrent reservation, mkdir/write failure, missing and corrupt consumption, documented restart, live STOP/lease checks, evidence replay and publication failure; selection timestamps, every acknowledgment digest, candidate/sigma tampering, copied approval rejection, no qualification and unacknowledged planning refusal. Existing numerical boundary, C/D/I/W, noise independence, first-reading matching, allocation and resource primitive tests remain in the validation set. Mocked controller fixtures now test rejection only and use tiny fixture counts.

The real native success fixture uses the smallest permitted allocation: one device, one group, two paired trials per sigma, all four sigmas, two policies: 16 attempts, 32 acquisition readings and 16 runtime BCH decodes. It uses the actual approval, atomic consumption, Windows worker/job/pipe/lease/monitor, resource sampling, source checks, replay, controller acceptance and marker publication. Scientific mode is disabled and all records are explicitly automated fixtures in temporary namespaces. Two-pass replay is 64 measurements, 32 decodes and two enrollment reference readings, adding zero statistical samples. Its fixture limits are 60 seconds, 2 GiB memory, 16 MiB free RAM, 64 MiB free disk, 16 MiB bundle growth, 64 MiB total growth, 50 ms sampling and 200 ms stop grace. Actual results are retained in the validation receipt; this tiny success does not qualify full-scale resource fit.

The independent bootstrap reference has four devices in two groups, eight paired outcomes per device at each of four sigmas, beneficial and harmful discordances, positive/negative device effects and group variation. Fraction arithmetic gives paired deltas `[0, -0.03125, 0.03125, -0.03125]`. An independent seeded index generator checks every one of 10,000 whole-device multiplicity vectors against actual production estimator inputs. Independent order-statistic interpolation checks all 12 S/M/delta pointwise intervals; a repeat verifies reproducibility. It is synthetic reference arithmetic, not research evidence or a scientific sigma selection.

## Read-only preflight and later authorized workflow
From the repo root, using the existing native interpreter:
```powershell
.\.venv\Scripts\python.exe src/python/scripts/run_shared_noise_calibration_v1.py plan
.\.venv\Scripts\python.exe src/python/scripts/run_shared_noise_calibration_v1.py preflight
```
These commands generate zero observations and approve nothing. Repeat preflight immediately before requesting approval; any source, specification, environment, configuration or plan change requires a new freeze and approval. Approval-v2 must bind `experiment_id`, `rules_version`, unique `authorization_id`, exact canonical `output_directory` and its basename `run_id`, `fixture_only=false`, named `approved_by`, nonfuture timezone-aware `approved_at`, all five freeze fields, exact scientific `resource_budgets`, `allocation_rules_and_resources_reviewed=true`, the scientific execution token, and explicit nullable restart fields. Consult the strict schema; no real approval file has been generated as part of remediation.

Only after separate authorization may an operator invoke `run-calibration` with `--output` and `--approval-file`. It cannot invoke the legacy formal runner. Scientific output, sidecars and one-time authorizations use distinct new Week 9 namespaces. `audit --output <bundle>` validates complete evidence without acknowledgment. `audit-selection --output <bundle>` reports computation and missing acknowledgment. A reviewer must independently provide an acknowledgment-v1 record; the `acknowledge-selection --output <bundle> --acknowledgment-file <record>` action validates and records it. `audit-selection` with that file verifies their relationship. These actions never enable final evaluation. Final-study implementation, planning approval and formal execution authorization remain separate future work.
