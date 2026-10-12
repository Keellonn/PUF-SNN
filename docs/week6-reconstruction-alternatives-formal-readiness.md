# Week 6 reconstruction alternatives: Stage 3A formal execution readiness

Date: 2026-10-07 (America/New_York). Decision: **READY FOR USER-AUTHORIZED FORMAL RUN**.

This task enabled and tested the formal pathway and performed read-only preflight. It did not execute the 48,000-attempt experiment or create its result directory. The Stage 2 smoke remains NONFORMAL historical validation, not formal research evidence.

## 1. Git/source baseline

Branch `main`, HEAD `acc46478dcde2ecffe706d8eab355b453b94fa30`; index clean. The task began with 706 tracked/nonignored-untracked files. Existing modified user files were `docs/research-logs/will.md` and `src/python/puf_snn/pipeline_timing.py`. Previously untracked Authentication-v2/Tier-1 implementation, schemas, configuration, tests, protocol/audit/validation documents, and Stage 2 alternatives files were preserved.

A task-specific baseline is retained in `tmp/week6-alternatives-stage3a-baseline/`, with a SHA-256 inventory and exact pre-task runner/schema/test bytes. Comparison found only two changed pre-existing files: the isolated alternatives runner and its attempt schema. All other 704 inventoried files remain byte-identical, including the approved plan/config, alternatives codec, production PUF/reconstruction/verifier/Auth-v2, Tier-1 and research-log user work, and tracked historical evidence. No repository history/network operations or staging occurred.

Both authoritative documents were read completely. The entire alternatives module, runner, schema, configuration, relevant tests, saved smoke and transitive runtime imports were inspected before edits. All mandatory digests passed before modification. No AGENTS.md instruction was present in the repository/parent inspection inherited from this task series.

## 2. Formal-mode implementation changes

Modified:

- `src/python/scripts/run_reconstruction_alternatives.py`
- `schemas/reconstruction-alternatives-attempt-v1.schema.json`

Created:

- `tests/experiments/test_reconstruction_alternatives_formal.py`
- This report, `docs/week6-reconstruction-alternatives-formal-readiness.md`.

Local validation logs, prerequisite certificate, baseline/diff records, preflight reports and source-snapshot rehearsal are in `tmp/`, not formal results.

`formal` now dispatches through a shared execution loop with the existing smoke path. The loop keeps real PUF generation, decoding and independent credential verification; it exposes no injected verifier callback, reduced formal population, retry count, or alternate seed override. Formal preflight completes before output-directory creation. Formal errors preserve partial raw records and INCOMPLETE rather than becoming fabricated decoder rejections.

The existing schedule object remains `FORMAL_PLAN_ONLY` to preserve its exact approved digest. `execution_mode()` assigns FORMAL to measured formal records and execution metadata, while smoke remains NONFORMAL. A read-only `preflight` command checks readiness without enrollment, warmup or measured attempts. Optional `--source-snapshot` verifies a previously prepared sanitized bundle during preflight.

The frozen config's `execution_policy: formal-disabled-stage2` is retained byte-for-byte as historical Stage 2 metadata. It is not an authorization switch. Stage 3A's explicit formal dispatcher and its preflight checks implement the newly authorized mode-wiring change. Actual formal execution remains subject to a separate user request.

## 3. Scientific configuration integrity

All approved hashes remain unchanged:

- Plan SHA-256: `0206983264278f1485b36bdbff29463afe2dc153aa003954506e68e75b9ced2d`.
- Config SHA-256: `3b7caa56bf296aaa02bca8fea69d545d6f1395c9811770c6e4d19ad8ea94c18b`.
- Formal schedule digest: `d22e5eebe6ec55c9f890e02b4f010833e4f32ff9d64b5c777b22e9f794a26f10`.

Source AST comparison against Stage 2 confirmed unchanged bodies for `compile_plan`, `rng`, `provision`, `RuntimeMaterial`, `measured_attempt`, `score`, `proportion`, `latency`, `summarize`, `paired`, `cluster_intervals` and `warm_up`. The complete isolated codec file is byte-identical. This covers sampling, pairing, timing, reconstruction/scoring, exact Clopper-Pearson formulas, linear quantiles, and the 10,000-resample whole-population paired bootstrap.

No change to 20 populations, six devices/population, seeds 2026100701..2026100720, one generation, SD 0.1/0.25, 50 attempts per device/group/condition, B0/A1/A2/B1, read counts, BCH identities, 32/30-bit formats, stream prefixes/derivation, group rotation or independent verification.

## 4. Trial-plan verification

The entire schedule was recompiled and inspected without taking PUF measurements. Independent guards verify the canonical digest, equality to recompilation, unique trial/read identities, exact device set, cell counts and slot balance:

- 48,000 planned measured attempts.
- 6,000 attempts in each of eight group/condition cells.
- 120 devices in the exact 20 populations.
- 240 intended helper/verifier enrollments, one per code/device.
- 120,000 planned timed PUF read calls.
- 60,000 unique shared measurement identities.
- Each group in each execution slot exactly 3,000 times.

Rehashed altered schedules, smaller smoke schedules, changed labels, reordered/changed definitions and incorrect counts are refused. The compiled schedule is not relabeled or regenerated with new scientific inputs to obtain a desired digest.

## 5. Formal-output safety

Only this exact path is permitted by the formal entry point:

`results/week-6/will/reconstruction-alternatives/week6-reconstruction-alternatives-v1-formal-001`

The path must not exist. Wrong paths, historical paths, child paths, symbolic links/junctions and pre-existing output are refused. Creation uses exclusive directory semantics after preflight. The directory **does not exist after Stage 3A**. A subsequent authorized run will recheck it rather than trusting this observation.

NONFORMAL output remains forbidden anywhere under `results/`. It produces only NONFORMAL_VALIDATED and never formal COMPLETE. Full formal completion independently requires the fixed 48,000-row plan, FORMAL labels, 240 enrollments, source identity, exact accounting, successful readback and valid manifests. Small nonformal rows cannot qualify by changing their label.

## 6. Source snapshot/provenance method

No commit is required. `source_dependencies()` is a closed 31-file allowlist: the isolated runner/codec, package initializer, all PUF/reconstruction/auth source modules (including transitive auth initializer imports), frozen config, attempt schema, the three alternatives documents, requirements/pyproject, and the three alternatives test modules. Missing dependencies fail rather than disappearing from a directory glob. Runtime dependencies under `src/` are hashed when the process imports, so changes between import and preflight are rejected.

A future formal run creates a separate `source_snapshot/` bundle inside its exclusively created evidence directory. It stores exact raw bytes at `files/<repository-relative-path>` with its own manifest, source ID, allowlist and safe prerequisite identities. The main evidence manifest recursively hashes this bundle, including its manifest; metadata and COMPLETE bind the initial snapshot-manifest hash. Snapshot files are never rewritten by the runner. The bundle is immutable by convention, not a filesystem write-protection guarantee.

The snapshot excludes `.venv`, model binaries, unrelated files, output directories, runtime verifier keys/tags, private providers, credentials from live accounts, and session secrets. Synthetic experiment enrollment truth is separate from the source bundle and runtime verification inputs. Package installations are inventoried by exact version rather than copied. The test certificate/logs are retained locally and cryptographically referenced through the safe prerequisite record; they are not a signed trust service.

Source hashes are checked at preflight, before and during snapshot construction, immediately before measured collection, after collection/summaries, during readback, and immediately before COMPLETE. Snapshot copies are independently hashed and checked for unexpected files. Changed source or snapshot bytes prevent completion and, once output exists, produce incomplete evidence. HEAD, branch, dirty/untracked state, index state, Python executable, package versions, command, machine/OS/CPU, timer and actual backend/thread modes remain recorded. The output directory is not a source dependency.

The real dry-preflight verifies the pinned Stage 2 smoke manifest and every artifact, re-reconciles its 80 saved rows without reconstruction, verifies unchanged scientific runtime files from that smoke, checks its runtime gate, and checks the current Stage 3A test certificate against source hashes and hashed logs. Missing, failed or stale validation is refused. The document-only finalization of this report is recorded in the test certificate; runtime/test/schema bytes remain those tested.

A sanitized snapshot rehearsal is retained at `tmp/week6-stage3a-source-snapshot/`. It exercises byte copying and hash verification outside the formal result path. This rehearsal is not a formal run or result bundle.

## 7. Test execution results

**221 distinct tests passed**, zero unexpected failures/errors: the previous 194 plus 27 new formal-readiness tests. Final full-suite logs are retained as `tmp/week6-stage3a-<suite>.log` and bound by `tmp/week6-alternatives-stage3a-validation.json`.

From repository root with `$env:PYTHONPATH='src/python'`:

```powershell
.venv/Scripts/python.exe -B -m unittest discover -s tests/reconstruction -p 'test*.py' -v
.venv/Scripts/python.exe -B -m unittest discover -s tests/auth -p 'test_credential*.py' -v
.venv/Scripts/python.exe -B -m unittest discover -s tests/experiments -p 'test_reconstruction_experiment.py' -v
.venv/Scripts/python.exe -B -m unittest discover -s tests/experiments -p 'test_credential_verifier_experiment.py' -v
.venv/Scripts/python.exe -B -m unittest discover -s tests/experiments -p 'test_reconstruction_alternatives_experiment.py' -v
.venv/Scripts/python.exe -B -m unittest discover -s tests/experiments -p 'test_reconstruction_alternatives_formal.py' -v
```

Results in that order: 65, 83, 22, seven, 17 and 27 passing tests. Final observed process durations: 41.922, 14.576, 24.898, 0.619, 19.432 and 26.127 seconds. Suites ran concurrently; these are validation durations, not experiment latency measurements. Earlier targeted passes are not double-counted.

New tests cover dispatch, formal schema/mode separation, exact population/digest enforcement, wrong/pre-existing paths, callbacks, package/code/credential checks, missing/stale source, snapshot exact bytes/manifest/extra-file tampering, read-only preflight, prerequisite rejection, interrupted formal setup, retention of the first failed attempt without retry, reduced-population completion refusal, CSV all-field readback and independent polynomial enrollment checks. Positive completion-seal mechanics are unit-tested with a mocked full-audit receipt in a disposable temporary directory; that fixture is explicitly not a formal cohort or valid research result. Production completion retains the actual full-population readback guard. Formal measurement entry points are mocked or forced to fail on their first call in these tests; no test iterates the real cohort.

## 8. Formal dry-preflight result

**PASS**, with zero executed attempts and `output_exists=false`. The initial actual preflight output is `tmp/week6-stage3a-dry-preflight-initial.json`; final-source/snapshot revalidation is `tmp/week6-stage3a-dry-preflight.json`. All quantities in section 4 and all three approved digests matched. No enrollment, noisy read generation, encode/decode attempt or warmup was executed by dry-preflight. Algebra initialization and credential-format conversion are parameter checks, not reconstruction trials.

Read-only command:

```powershell
.venv/Scripts/python.exe -B src/python/scripts/run_reconstruction_alternatives.py preflight --output results/week-6/will/reconstruction-alternatives/week6-reconstruction-alternatives-v1-formal-001 --source-snapshot tmp/week6-stage3a-source-snapshot
```

The optional snapshot argument verifies the saved rehearsal. It does not copy that rehearsal over future live-source evidence. The future formal run creates and verifies its own bundle from current validated source bytes.

## 9. Schema and reconciliation verification

The schema accepts explicit FORMAL/NONFORMAL ordinary/interrupted rows with no extra fields. Formal constraints bind approved plan/config/schedule digests, formal namespace, population range, device/attempt bounds and zero generation. Semantic reconciliation checks every row against the exact scheduled identity, group parameters, candidate/padding format, true errors, verifier invocation/outcome, source ID and timing spans.

Readback now independently polynomial-encodes saved candidate messages and enrollment credentials to verify helper/codeword consistency and reported received-to-candidate distance, without calling the BCH decoder. It preserves correct, decoder failure, invalid format and wrong credential categories. A valid-format wrong candidate remains a reconstruction failure even when verification correctly rejects it.

All summary CSV fields, including paired comparisons and every latency stratum, are read back and compared. Formal audit additionally reloads raw records, plan/config, enrollments and summaries, recomputes accounting and population-cluster intervals, and verifies metadata/source/snapshot identities. COMPLETE is published through a pending file and atomic rename only after readback and hash checks. It means evidence integrity, not achievement of the 0.5% FRR target. Interruptions and exceptions retain type-only diagnostics and INCOMPLETE; no retries, discarded ordinary failures or fabricated rejection records are introduced.

## 10. Remaining technical limitations

No observed readiness blocker remains. Actual 48,000-row execution, full-cohort tail latency and final artifact volume are intentionally unmeasured. Formal bootstrap/readback adds runtime beyond the Stage 2 smoke estimate. The small smoke's 4.7-minute cautious estimate remains a provisional planning estimate, not a new Stage 3A benchmark.

The environment is pinned to validated Python 3.12.4 and required packages galois 0.4.11, numpy 2.5.3, numba 0.67.0, llvmlite 0.49.0, scipy 1.18.1 and jsonschema 4.26.0. Changes require review/revalidation, not silently updating expected values. Retain the local prerequisite certificate/logs and Stage 2 smoke artifacts until the formal run; missing/stale prerequisites block execution. Editing an allowlisted file, including this report, invalidates the recorded source fingerprint until validation provenance is refreshed appropriately.

Hash checks and callback identity checks guard accidental changes/substitution in a trusted local process; they are not tamper-proof protection from malicious code with control of the process/filesystem. Before/after checks do not prove that a file could never have been transiently modified and restored between checks. Python/OS/package timing and publicly seeded synthetic credentials retain the approved plan's limitations. No production-security, wrong-device FAR, real hardware latency, drift/temperature robustness or FRR-target claim follows from readiness.

## 11. Exact future formal-run command

Run only after a separate explicit user authorization, from repository root, keeping all scientific hashes unchanged:

```powershell
$env:PYTHONPATH='src/python'
.venv/Scripts/python.exe -B src/python/scripts/run_reconstruction_alternatives.py formal --output results/week-6/will/reconstruction-alternatives/week6-reconstruction-alternatives-v1-formal-001
```

This pathway is now enabled and will re-run preflight. It was **not executed for measurements during Stage 3A**. No `--force`, reduced cohort, alternate verifier or overwrite option exists. If preflight rejects, investigate the cause; do not change expected scientific hashes or overwrite an existing result directory to make it pass.

## 12. Readiness decision

**READY FOR USER-AUTHORIZED FORMAL RUN**.

Formal wiring, fixed schedule, source-snapshot safeguards, affected regressions, schema/readback checks and read-only preflight passed. Formal result directory remains absent. Existing production/Auth-v2/Tier-1 code, the scientific design/config, saved smoke and historical evidence are unchanged. All changes remain local and uncommitted for review.

NO FORMAL RECONSTRUCTION EXPERIMENT WAS RUN.
NO SCIENTIFIC PARAMETERS WERE CHANGED.
NO HISTORICAL RESULTS WERE MODIFIED.
NO FILES WERE STAGED OR COMMITTED.
NOTHING WAS PUSHED.
