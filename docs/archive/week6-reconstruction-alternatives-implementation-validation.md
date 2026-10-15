# Week 6 reconstruction alternatives: Stage 2 implementation validation

Date: 2026-10-07 (America/New_York). Scope: isolated implementation, automated tests, and one retained 80-attempt **NONFORMAL** noisy smoke. **READY FOR FORMAL EXPERIMENT REVIEW**, not authorized or directly enabled for formal execution.

## Repository state and preservation

Branch `main`; HEAD `acc46478dcde2ecffe706d8eab355b453b94fa30`. Initial index was clean. Previously modified files were `docs/research-logs/will.md` and `src/python/puf_snn/pipeline_timing.py`. Existing untracked work included the Authentication-v2 protocol specification, Tier-1 config/runner/module/tests/schemas and validation documents, current-repository audit, protocol-preparation document, and approved alternatives plan. None was edited, staged or discarded.

Before editing, the entire approved plan was read, production PUF/reconstruction/verifier APIs were inspected, and existing algebra/tests/evidence conventions were reviewed. `tmp/week6-alternatives-stage2-preservation.json` records SHA-256 fingerprints for all 699 initially tracked/nonignored-untracked files. Post-smoke comparison found **all 699 unchanged**, including the plan, production PUF/BCH/credential/verifier/admission/Auth-v2 code, Tier-1 user work, and tracked historical evidence. This inventory does not claim coverage of ignored files; the task did not write historical/ignored simulation archives. The index remains clean. No Git network or history-changing operation was performed.

## Created file inventory

- `src/python/puf_snn/reconstruction_alternatives.py`: strict 3/5-read voting, separately bound BCH(63,30) codec, credential conversion, helper enrollment/reconstruction, decoder consistency validation.
- `src/python/scripts/run_reconstruction_alternatives.py`: deterministic schedule compiler, isolated provisioning, measured runtime, evaluator accounting, intervals, paired summaries, artifact validation, smoke runner and fail-closed formal command.
- `configs/reconstruction_alternatives_v1.json`: byte-hash-frozen scientific configuration and separate smoke/warmup namespaces.
- `schemas/reconstruction-alternatives-attempt-v1.schema.json`: strict NONFORMAL ordinary/interrupted attempt schema; rejects additional fields.
- `tests/reconstruction/test_reconstruction_alternatives.py`: 15 codec/voting tests.
- `tests/experiments/test_reconstruction_alternatives_experiment.py`: 17 schedule/accounting/evidence tests.
- This implementation-validation report.

No existing source/config/test/document was modified. Temporary local artifacts outside `results/`: preservation snapshot, `tmp/week6-alternatives-plan-only/`, and `tmp/week6-reconstruction-alternatives-smoke-001/`. Tests also used temporary fixture directories that were cleaned up. These fixture executions are deterministic unit-test evidence, not additional formal or noisy smoke cohorts.

## Frozen configuration and compiled schedule

The formal scientific definition remains 20 populations with seeds 2026100701..2026100720, six devices each, one generation per code/device, nominal SD 0.1, stress SD 0.25, and 50 attempts per device/configuration/condition. Groups remain B0 one read/baseline, A1 majority-3/baseline, A2 majority-5/baseline, and B1 one read/BCH(63,30,t=6).

Compilation, without reading PUFs or executing reconstruction, produced 48,000 planned entries, 6,000 per cell, 120 devices, 120,000 planned read calls and 60,000 shared measurement identities. Each group occupies each execution slot 3,000 times. Base blocks are ordered population/device/condition/attempt, shuffled with 2026100791, then groups rotate by block index modulo four.

All stream labels follow the approved ASCII SHA-256-to-big-endian-integer derivation with unpadded decimal fields. Manufacturing, reference, baseline/B1 credentials and evaluation streams are separate. The same reading labels are regenerated inside each group's timed path, not reused from a response cache. Baseline helpers/credentials are shared across B0/A1/A2; B1 has separate enrollment and 30-bit credential. The independent OS-random verifier key remains unrelated to deterministic simulation streams.

Digests:

- Approved plan: `0206983264278f1485b36bdbff29463afe2dc153aa003954506e68e75b9ced2d`.
- Frozen config: `3b7caa56bf296aaa02bca8fea69d545d6f1395c9811770c6e4d19ad8ea94c18b`.
- Formal plan-only schedule: `d22e5eebe6ec55c9f890e02b4f010833e4f32ff9d64b5c777b22e9f794a26f10`.
- Smoke schedule: `abfe22e70955744e0e27300d404dce6cb39a44228f09dae5ee4eeb35e2cf1810`.

Loading refuses a changed config or approved-plan hash. Semantic plan compilation does not depend on output path. Formal execution is unconditionally rejected before output creation; there is no CLI authorization override.

## BCH and credential verification

The isolated adapter verifies installed galois 0.4.11 and exact n=63,k=30,d=13,t=6, GF(64), polynomial 0x43, primitive element 2, first root 1, systematic primitive narrow-sense identity, generator 0x37cd0eb67. Returned codewords must have shape 63, binary values, zero independent polynomial remainder, and received-to-candidate distance matching an integer correction count in 0..6. Count -1 suppresses the backend payload; unexpected backend exceptions propagate.

Tests independently construct the generator through integer GF(64) arithmetic and roots 1..12 with cyclotomic closure, check divisibility of x^63+1 and all 30 message basis vectors against polynomial division, and verify the approved fixed codeword and six flips at positions 0,10,20,30,40,62. All selected single positions and fixed patterns through six errors pass. Seven leading flipped bits provide a pinned declared-failure fixture. A received word six bits from a different valid codeword demonstrates a wrong valid-format candidate beyond the true enrollment radius; correction count does not establish correctness.

A B1 credential is exactly 30 bits, stored as four big-endian bytes with the top two bits fixed zero. Those zeros are representation bits, not BCH padding. Zero, maximum, asymmetric and every individual-bit cases round-trip; oversized/high-bit/nonbyte inputs are rejected rather than truncated. B1 padding status is null/not applicable, while all 30 BCH information bits are used.

B0/A1/A2 call unchanged production enroll/reconstruct. B1 uses a distinct helper/config and reconstruction binding. Runtime material contains no evaluator reference or expected credential. A real `CredentialAdmissionService.verify` runs before evaluator scoring and receives only candidate bytes and trusted binding. Missing/wrong/invalid records retain their rejection semantics. No session/HKDF APIs are called by the new harness. Verifier keys/tags/private records are never serialized; exception evidence uses type only, avoiding secret-bearing exception text or locals.

## Automated validation

All requested suites passed under the normal installed backend. Distinct tests executed: **194**, comprising 32 new tests and 162 existing regressions. Repeated targeted runs are not double-counted.

Commands from repository root, with `$env:PYTHONPATH='src/python'`:

```powershell
.venv/Scripts/python.exe -B -m unittest discover -s tests/reconstruction -v
.venv/Scripts/python.exe -B -m unittest discover -s tests/auth -p 'test_credential*.py' -v
.venv/Scripts/python.exe -B -m unittest discover -s tests/experiments -p 'test_reconstruction_experiment.py' -v
.venv/Scripts/python.exe -B -m unittest discover -s tests/experiments -p 'test_credential_verifier_experiment.py' -v
.venv/Scripts/python.exe -B -m unittest discover -s tests/experiments -p 'test_reconstruction_alternatives_experiment.py' -v
```

Results respectively: 65 PASS (50 existing plus 15 new), 83 PASS, 22 PASS, seven PASS, and 17 PASS. Observed durations were 20.731, 6.605, 10.180, 0.574 and 7.744 seconds; some regression suites ran concurrently, so these are test-process durations, not benchmarks. No unexpected failures occurred. The displayed argparse rejection in the formal-mode test was expected and passed.

New checks include every majority truth pattern for 3/5, strict input validation, independent RNG objects/labels and actual call counts, unchanged baseline dispatch, stable formal schedule digest, exact cell/slot counts, strict schema/tamper rejection, independent verifier mismatch/noninvocation, no FRR repair by verifier rejection, missing-record rejection, exact timing spans, paired bootstrap population retention, config/output isolation, interrupted error preservation without retry, source-change rejection and manifest round trips. Accounting tests use deterministic synthetic/noiseless fixtures. Existing regressions cover additional verifier/admission failures, fixed reconstruction miscorrections, all 1,953 two-bit patterns and historical evidence-runner semantics; they do not execute historical formal cohorts.

## Retained NONFORMAL smoke

Command executed once for the retained noisy smoke:

```powershell
$env:PYTHONPATH='src/python'
.venv/Scripts/python.exe -B src/python/scripts/run_reconstruction_alternatives.py smoke --output tmp/week6-reconstruction-alternatives-smoke-001
```

Exactly two separately manufactured smoke devices, two conditions, four groups, five attempts per device/cell: **80 measured attempts**, ten per condition/group. Namespace `w6ra-smoke-v1` separates them from formal populations despite reuse of the first numerical population label. Four helper/verifier enrollments were provisioned, two code identities per device.

Observed counts (C correct / D decoder failure / I invalid format / W wrong credential):

- Nominal B0, A1, A2 and B1: each 10 C / 0 D / 0 I / 0 W.
- Stress B0: 5 C / 5 D / 0 I / 0 W.
- Stress A1: 9 C / 1 D / 0 I / 0 W.
- Stress A2: 9 C / 1 D / 0 I / 0 W.
- Stress B1: 8 C / 2 D / 0 I / 0 W.

Total: 71 correct, nine decoder failures, zero invalid-format, zero wrong credentials, zero implementation exceptions. All 71 valid candidates received real verifier calls and were accepted; nine decoder failures skipped verification. No wrong acceptance or correct-candidate verifier rejection occurred. Reconstruction failures and legitimate admission failures both count nine; decoder failures were not hidden behind verifier metrics. No mismatch calls happened naturally in this tiny measured smoke; deterministic wrong-candidate tests and separate warmup exercise real mismatch decisions. These are validation observations only, not a 48,000-attempt result, population FRR estimate suitable for deployment, or demonstration of the 0.5% target.

Separate warmup used `w6ra-warm-v1`, a separate device/enrollments/key, 20 complete nominal attempts per group (80), 20 fixed encode/decode cycles per code and 100 verifier passes plus 100 mismatches. All 80 complete warmup attempts reconstructed correctly. Warmup is excluded from every measured smoke denominator. Warmup itself generated 200 noisy read calls; with the measured smoke's 200, the CLI performed 400 such calls in total, plus two smoke reference calls and one warmup reference call. This distinction prevents confusing warmup activity with the 80 measured attempts.

## Evidence and reconciliation

Saved evidence resides only in `tmp/week6-reconstruction-alternatives-smoke-001/`. It includes byte-exact config snapshot, full trial schedule, metadata, warmup, actual backend runtime modes, synthetic enrollment truth, 80 raw JSONL outcomes, summary JSON and condition/device/population/paired/latency CSVs, runtime observation, reconciliation, post-run provenance, manifest and `NONFORMAL_VALIDATED.json`.

Reconciliation PASS: 80 schema-valid unique rows in scheduled order; ten per cell; 200 actual timed read calls; 100 shared measurement identities; four enrollments; 71 verifier calls; matched read prefixes; selected-error/outcome/credential-format/verification equations; effective-error correction-radius checks; nonoverlapping timing spans and stage sums; summary CSV count readback. Trials retain C/D/I/W independently of admission. Exact Clopper-Pearson intervals retain x/n and null zero-denominator conditional rates. Paired counts are saved. Cluster uncertainty is explicitly not estimable for the single smoke population; the 10,000-resample formal algorithm was tested using synthetic paired population fixtures.

Manifest verification passed for all 16 artifacts. Manifest SHA-256: `91b90a2de1df3aa8652dbaa1bb7a0a73527454014a915501b2f93497b7a6bc26`. Its hash is bound by the NONFORMAL validation marker; no recursive hashing is used. Current runtime source hashes matched the smoke source snapshot. Neither `COMPLETE` nor a formal result directory was created. Unit tests confirmed exceptions/source changes retain partial records and INCOMPLETE without a validation seal. The evidence directory plus metadata command identifies the run; trial IDs identify entries within its saved schedule.

## Runtime observations and limitations

Measured smoke attempt loop: **0.2282207 s**, including per-attempt bookkeeping, schema checking and writes. Recorded total work: **6.6818689 s**, including setup/warmup and summary processing through the measurement point, excluding final manifest/marker writes and interpreter startup. Warmup: 6.112318 s, of which algebra initialization 3.6580044 s. These are separate scopes, not quantities to add together.

Linear 48,000/80 loop scaling: 136.93242 s. Cautious implementation estimate, twice that plus observed total setup/work: **280.5467089 s**, approximately 4.7 minutes, below the plan's provisional 900-second gate. It does not predict formal tail costs or establish hardware latency. Formal summary/bootstrap costs grow with cohort size, and JIT/background load can vary.

All requested p50/p95/p99/max/sample-count distributions are saved for stages/total and outcome/verifier strata. Ten observations per cell make smoke tail quantiles unstable. As an example, nominal B0 p95 total was about 6.755 ms, exceeding both voting groups in this tiny run; do not use that ordering as a performance conclusion. No outliers were trimmed. A skipped verifier is zero all-attempt occupancy, not an observed zero-time HMAC; conditional verifier distributions include only actual calls.

Environment: Python 3.12.4; galois 0.4.11; numpy 2.5.3; numba 0.67.0; llvmlite 0.49.0; scipy 1.18.1; jsonschema 4.26.0. Observed GF2 mode `jit-calculate`, extension mode `jit-lookup`, Numba thread count 20. Full package/machine/clock/command provenance is in metadata. No package install or library modification occurred.

The model remains noiseless enrollment plus independent Gaussian measurement noise with fixed manufacturing variation. It does not model correlated noise, differential environment or aging. B1 has 30-bit format entropy and publicly seeded synthetic credentials have no secrecy. Helper/entropy and wrong-device limitations remain as stated in the approved plan. Fresh OS-random verifier keys/tags are intentionally not reproducible; non-timing decisions and synthetic inputs are. There are no remaining observed codec/test/reconciliation failures.

## Systematic conformance review and formal readiness

Confirmed: production baseline/API untouched; Authentication-v2 and Tier-1 untouched; approved plan unchanged; fixed population/noise/seed/read-order parameters; exact BCH identities; no credential truncation; all 30 B1 message bits used; no adaptive tuning; no outcome-dependent retries or dropped failures; no historical overwrite; counts and measured-stage denominators reconciled. Only new isolated implementation/config/schema/tests/report and local nonformal artifacts were added.

Recommendation: **READY FOR FORMAL EXPERIMENT REVIEW**. The algebra, implementation, regressions, nonformal evidence and provisional runtime gate passed. This is deliberately not a claim that the checked-in Stage 2 CLI can execute the formal study: it currently rejects `formal` before any output or sampling. The schema and execution/report labels are intentionally NONFORMAL-only during this task. Enabling formal execution requires a separately authorized, reviewed mode-wiring change, not merely passing an undocumented flag.

Exact next-task procedure:

1. Review these local uncommitted files and the preserved user work. Explicitly authorize formal-mode enablement/execution in a separate task.
2. Keep the scientific config and approved-plan hashes above unchanged. Add the reviewed formal execution wiring to consume the existing compiled schedule, with the same provisioning/measurement/scoring/reconciliation functions. Permit FORMAL record/report labels only through that gate, enforce exactly 48,000 attempts/120 devices/240 enrollments/6,000 per cell, and restrict formal output to a new approved results directory. Retain NONFORMAL isolation and seal formal COMPLETE only after all checks. Extend mode-isolation tests; rerun affected tests and inspect source/environment provenance. Do not change trial counts, streams, noise or algorithms to enable the mode.
3. Compile and inspect the schedule without measurements using a new output directory:

```powershell
.venv/Scripts/python.exe -B src/python/scripts/run_reconstruction_alternatives.py compile --output tmp/week6-alternatives-formal-review-plan
```

Require digest `d22e5eebe6ec55c9f890e02b4f010833e4f32ff9d64b5c777b22e9f794a26f10`. The currently saved compilation is also available for review without repeating this command.

4. Only after authorization, reviewed gate wiring and checks, the intended command is:

```powershell
.venv/Scripts/python.exe -B src/python/scripts/run_reconstruction_alternatives.py formal --output results/week-6/will/reconstruction-alternatives/week6-reconstruction-alternatives-v1-formal-001
```

**This command intentionally fails with the current Stage 2 code. It was not run to perform measurements.** There is no supported bypass in this implementation. The exact future command does not itself constitute authorization.

5. Reconcile/seal the separate formal evidence and report every group's failures and uncertainty, regardless of target attainment. Never promote this smoke or overwrite historical cohorts.

NO FORMAL EXPERIMENT WAS RUN.
NO HISTORICAL RESULTS WERE MODIFIED.
NO FILES WERE STAGED OR COMMITTED.
NOTHING WAS PUSHED.
