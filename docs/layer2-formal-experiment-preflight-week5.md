# Layer 2 Formal Reconstruction Experiment Preflight

Date: 2026-09-29. Status: **READY FOR FORMAL EXECUTION** under the user's accepted seven-field schema. Execution still requires separate authorization; this task stopped before the formal experiment.

This preparation record follows [the reviewed experiment plan](layer2-formal-experiment-plan-week5.md). The plan's original missing-config and schema-blocker statements describe the earlier audit. The user has now accepted the existing schema, and the exact approved config has been created and validated. The single-file predeclared-contract limitation remains documented; it is not an execution blocker for this software pilot. No runner/schema, reporting, BCH, credential, Layer 3, or historical-result changes were made.

## Configuration and integrity gates

Created [configs/reconstruction_experiment_v1.json](../configs/reconstruction_experiment_v1.json) with exactly the seven approved fields and values, including checkpoint `40da3a388983030b7b696ce7bf2b801e0ed6903f`, bootstrap seed 20260929, and 10,000 bootstrap resamples. The actual imported `scripts.run_reconstruction.load_plan()` accepted the file, validated the referenced Layer 1 configuration and fixed ordered seeds, and passed the Git ancestry check. Importing the module for validation did not execute its CLI or experiment.

Config SHA-256:

```text
07be1acd3c3980842a867de3fc08e32a79543c4262dd3a42832f4284a76525cb
```

The exact 20 directory names parsed from the reviewed plan match `RUN_NAMES` in order. All nine required files in each directory were read: `COMPLETE`, `config.json`, `metadata.json`, `devices.csv`, `metrics.csv`, `summary.csv`, `noise_sweep.csv`, `noise_sweep_summary.csv`, and `uniqueness_pairs.csv`. The predeclared 180-file bundle fingerprint was recomputed using the plan's canonical mapping/JSON method and matched exactly:

```text
e3332b944bfae4a8fcb9b04522277b13c9312608d36d1e35e7ccbcbb171a60fd
```

Both frozen source fingerprints matched exactly before tests:

```text
src/python/puf_snn/reconstruction/bch.py
4b17daf39a97698a368d817a765c2bc8a7e5804468396573329428c01d3f44a6

src/python/puf_snn/reconstruction/credential.py
14463ca853ac5a54f326d18537e5ae76008ffde7240433ad52afa8acf2ae08ef
```

No input was repaired, regenerated, substituted, or overwritten. No reconstruction source was edited.

## Test execution

Working directory: `C:\PUF+SNN_SharedRepo\PUF-SNN`.

Interpreter: `C:\PUF+SNN_SharedRepo\PUF-SNN\.venv\Scripts\python.exe`.

Python: `3.12.4 (tags/v3.12.4:8e8a4ba, Jun 6 2024, 19:30:16) [MSC v.1940 64 bit (AMD64)]`.

Exact commands, executed sequentially using standard unittest discovery, verbose output, and fail-fast:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests/reconstruction -v -f
.\.venv\Scripts\python.exe -B -m unittest discover -s tests/experiments -p test_reconstruction_experiment.py -v -f
```

Results:

- Reconstruction suite: **50 tests, PASS**, unittest-reported runtime **18.171 seconds**, exit code 0.
- Formal-experiment suite: **22 tests, PASS**, unittest-reported runtime **9.026 seconds**, exit code 0.
- Total: **72 tests passed**, zero failures, errors, or skips. `test_frozen_plan_rejects_seed_selection` executed and passed.
- No warnings or errors were emitted by either test command. Runtime values above are the test runner's measurements, not shell startup/approval elapsed time.

The authorized tests exercised synthetic reconstruction controls, warm-up, and small in-memory experiment fixtures with temporary evidence directories managed by the tests. They did not run the production cohort or its formal noise sweep, call the formal runner CLI, or create the intended formal output directory. No test implementation was changed.

The Windows venv and protected archives were accessed outside the sandbox restriction through approved tool escalation. A later sandbox-only ignored-evidence inventory emitted archive permission warnings; repeating that read-only inventory with the same elevated access succeeded. These were inventory-access warnings, not test failures or input mismatches.

## Formal preflight

**PASS**, based on configuration, source inspection, and the completed tests:

- Nominal denominator: 20 seeds x 6 devices x 100 reads = **12,000**.
- Six sweep levels: `[0.0, 0.05, 0.1, 0.25, 0.5, 1.0]`; 12,000 attempts each = **72,000**.
- Total experimental denominator: **84,000**.
- **Six synthetic warm-up probes are excluded** from experimental counts and latency observations; the warm-up exclusion test passed.
- Intended output `results/week-5/will/reconstruction/layer2-experiment-v1-formal-001` does **not** exist and was not created.
- The CLI refuses existing output paths; evidence directory creation and file writes are exclusive. No historical directory will be used as output or overwritten.
- Before evaluation, `prepare_cohort()` will inspect the fixed archives, check the baseline reconciliation, regenerate Layer 1 tables in memory, and require byte-level CSV hashes to match the archives. This regeneration gate was inspected but deliberately **not executed** during preparation.
- Raw attempt records are flushed and read back for count/identity/outcome reconciliation. Source stability is checked, then `manifest.json` is written, then `COMPLETE` is written last.
- Caught evaluation failures preserve partial evidence and attempt to write `INCOMPLETE.json`; existing partial directories cannot be reused. The exception-retention, summary-write-failure, source-change, and overwrite-refusal tests passed. Preflight failures can occur before directory creation; abrupt process/storage failure can prevent an incomplete marker.

The exact approved future command is:

```powershell
.\.venv\Scripts\python.exe -B src/python/scripts/run_reconstruction.py `
  --config configs/reconstruction_experiment_v1.json `
  --archive sim_results `
  --output results/week-5/will/reconstruction/layer2-experiment-v1-formal-001
```

**This command was not executed.** Readiness does not bypass its runtime archive-regeneration, source-stability, or completion checks. If any gate fails at execution, retain evidence and investigate rather than substitute inputs.

The reviewed plan's reporting gaps remain future reporting work: explicit category-rate columns, a derived success interval, FRR-versus-BER and miscorrection-rate plots, and independent bootstrap reconciliation. They do not block collecting the existing runner's raw evidence under the accepted preparation scope, and no reporting changes were made in this task.

## Repository state

Git HEAD, from `git -c safe.directory=C:/PUF+SNN_SharedRepo/PUF-SNN rev-parse HEAD`:

```text
40da3a388983030b7b696ce7bf2b801e0ed6903f
```

Working-tree status, from `git -c safe.directory=C:/PUF+SNN_SharedRepo/PUF-SNN status --short`:

```text
 M docs/research-logs/will.md
?? configs/reconstruction_experiment_v1.json
?? docs/layer2-formal-experiment-plan-week5.md
?? docs/layer2-formal-experiment-preflight-week5.md
?? docs/tier1-results-week4-draft.md
```

The tracked research-log modification and untracked plan/Tier 1 draft predate this task and were left unchanged. The config and this preflight record are new, untracked files. Nothing was staged, committed, or pushed. The scoped `safe.directory` command option avoids changing global Git configuration.

Read-only ignored-evidence inventory identified:

```text
!! results/week-2/response-bit-analysis-2026-09-17/
!! results/week-2/will/layer1baseline.csv
!! results/week-4/will/authentication/
!! results/week-4/will/reconstruction/
!! sim_results/
```

There are zero tracked paths under `sim_results/`; its contents and the listed ignored evidence remain local historical artifacts. No ignore rules were changed. No formal experiment output exists. `git diff --check` passed.

No issue found in this preparation blocks execution under the accepted schema. The next step remains explicit user authorization to run the 84,000-attempt formal experiment.
