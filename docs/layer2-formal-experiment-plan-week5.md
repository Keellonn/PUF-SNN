# Layer 2 Formal Reconstruction Experiment Plan

Audit date: 2026-09-29. Status: **proposal only; execution is not authorized**.

The existing runner contains the core formal evaluation machinery, but is not yet ready to satisfy every requested reproducibility and reporting requirement. `configs/reconstruction_experiment_v1.json` is absent. Its supported schema is narrower than the requested self-contained experiment definition. Reporting also needs small additions described below. This audit creates only this document, not the configuration or experimental results.

Repository checkpoint inspected: `40da3a388983030b7b696ce7bf2b801e0ed6903f`. Existing user changes in `docs/research-logs/will.md` and the untracked `docs/tier1-results-week4-draft.md` were left alone. No Layer 3, BCH, reconstruction, historical evidence, or research-log file was modified.

## Existing Baseline

The implementation in [bch.py](../src/python/puf_snn/reconstruction/bch.py) and [credential.py](../src/python/puf_snn/reconstruction/credential.py) is the frozen `puf-snn-reconstruction-v1` construction:

- One simulated 64-bit PUF response; fixed indices 0 through 62 enter reconstruction. Index 63 is omitted to fit the BCH code length, not because of its measured stability.
- Full-length binary primitive narrow-sense systematic BCH(63,36,t=5), designed distance 11, GF(64), primitive polynomial `0x43`, primitive element 2, first root exponent 1, generator polynomial `0x86E8113`; MSB-first/highest-degree-first representation; `galois==0.4.11`.
- A 32-bit/four-byte pilot credential followed by four zero padding bits makes the 36-bit message. Public helper data are the encoded message XOR the selected enrollment response.
- Each reconstruction uses exactly one response and one BCH decode. No retries, majority voting, erasures, stability selection, or independent credential verification occur inside `reconstruct()`.
- The algebra cache holds fixed code algebra, not credentials or PUF responses. Codeword consistency checks are not credential verification.

Read-only reconciliation of the 20 September 24 historical single-run artifacts confirms **12,000 attempts, 11,805 correct reconstructions, 195 failures, 98.375% success, and 1.625% FRR**. Failure categories are 186 decoder failures, 7 invalid-padding outcomes, and 2 valid-format wrong credentials. Their rates among all attempts are 1.55%, 0.0583333%, and 0.0166667%, respectively. Historical selected BER63 is 24,170 / 756,000 = 3.197089947%; Layer 1 BER64 is 24,634 / 768,000 = 3.207552083%.

These are historical observations, not newly executed formal results. The formal nominal condition will evaluate the same archived responses and deterministic credentials; it is a reproducible re-evaluation, not an independent replication or new sample of devices.

Evidence sources are [the historical CSV](../results/week-3/will/layer2baseline.csv), [historical results prose](reconstruction-experiment-results.md), [design documentation](puf-layer2-design.md), and the raw single-run artifacts under `results/week-4/will/reconstruction/`. Raw evidence takes precedence over prose and transcribed values.

## Formal Runner Audit

### CLI and configuration contract

[run_reconstruction.py](../src/python/scripts/run_reconstruction.py) accepts:

```text
python src/python/scripts/run_reconstruction.py [--config PATH] [--archive PATH] --output NEW_DIRECTORY
```

`--output` is required. Defaults are the repository-root paths `configs/reconstruction_experiment_v1.json` and `sim_results`. There is no nominal-only, sweep-only, seed override, dry-run, retry, or resume option. Existing output directories, including partial runs, are refused.

`load_plan()` requires exactly these seven keys, with no extra or missing fields:

- `experiment_version`: exactly `layer2-experiment-v1`.
- `checkpoint`: a Git revision for which `git merge-base --is-ancestor CHECKPOINT HEAD` succeeds. This is an ancestry check, not an exact-source or clean-tree check; the loader does not impose an explicit string-type check before calling Git.
- `simulation_seeds`: the exact ordered 20-element list shown below, equal to `SEEDS`, derived from the fixed `RUN_NAMES` in `analyze_week2_response_bits.py`.
- `layer1_config`: exactly `configs/puf_baseline.json`.
- `credential_stream`: exactly `layer2-v1:{simulation_seed}:{device_index}:credential`.
- `bootstrap_seed`: a nonnegative Python integer; booleans are rejected.
- `bootstrap_resamples`: a positive Python integer; booleans are rejected.

The referenced Layer 1 config is loaded with its own strict schema. After dropping `random_seed` and normalizing the sweep tuple to a list, it must equal the hard-coded `BASELINE` dictionary. The current file's seed 6767 is consequently not an experiment seed; it is replaced by each cohort seed. Plan JSON uses ordinary `json.loads`, so duplicate JSON keys are not explicitly rejected there, unlike Layer 1 config loading.

### Inputs and execution sequence

`prepare_cohort()` calls `inspect_runs()` and `analyze()` from [analyze_week2_response_bits.py](../src/python/scripts/analyze_week2_response_bits.py). Directory identities are hard-coded; matching a seed alone is insufficient. Each directory must contain:

```text
COMPLETE
config.json
metadata.json
devices.csv
metrics.csv
summary.csv
noise_sweep.csv
noise_sweep_summary.csv
uniqueness_pairs.csv
```

Input configuration, completion-marker presence, seed, response length, pair order, `week2-v1` RNG identity, and agreement of archived simulator-source maps across all 20 runs are checked. Baseline rows, IDs, Hamming distances, BER, device summaries, and run summaries are reconciled; pooled baseline flips must equal 24,634. The formal inspector checks marker presence, whereas the historical single-run loader additionally checks marker text and modification time. This audit independently checked marker text as well.

The formal runner then calls `simulate()` **in memory**, for each seed, and serializes all six generated tables with `csv.DictWriter`. Their SHA-256 values must match the corresponding archived CSVs byte for byte. Thus it evaluates regenerated-but-archive-verified Layer 1 tables; it does not directly decode rows read from the archives. It generates no replacement Layer 1 result directory. The audit performed here read and checked saved data only; it did not invoke this regeneration step, so its byte-for-byte regeneration gate remains an execution-time check.

After preparation, `run_evaluation()` creates an exclusive new directory, records configuration and provenance, performs synthetic warm-up, and enrolls each of the 120 seed/device identities once. All nominal attempts finish before the sweep starts. Sweep evaluation proceeds by ascending sweep index, then fixed run order, then device/read order. Helpers, references, and credentials are reused unchanged across conditions.

Each attempt records the full response, selected response, actual evaluator error counts and BER, identities, result/candidate fields, evaluator decision, backend exception field, and elapsed reconstruction time. `input_record()` computes evaluator BER before the timed call, but the credential comparison occurs only after `reconstruct()` returns. These evaluator values are never passed to the decoder.

Raw records are flushed after each call. Any failed reconstruction with at most five actual selected-bit errors stops the run for correctness review after retaining the record. It is not retried or replaced. Summaries are reconstructed from raw evidence read back from disk, not from parallel counters.

### Existing tests and their limits

Reviewed `tests/reconstruction/`, including independent BCH encoder fixtures, fixed-subset/omitted-bit checks, in-radius correction cases, invalid-padding and valid-format miscorrection fixtures, single-decode behavior, and malformed backend handling. Reviewed [test_reconstruction_experiment.py](../tests/experiments/test_reconstruction_experiment.py), which covers exact attempt counts, no replacement, ordering, outcome accounting, ground-truth separation, helper reuse, deterministic streams, source-change detection, bootstrap repeatability, latency inclusion, retained exceptions, and overwrite refusal.

The experiment tests mostly use two-seed/two-device/three-read fixtures. `test_frozen_plan_rejects_seed_selection` reads the missing production config and therefore has a file dependency that is currently unsatisfied. Test setup calls `warm_up()`, and several tests create fixture evidence and invoke reconstruction. **No reconstruction tests or diagnostic probes were executed for this audit.** Inspection of tests is not a claim that they passed in this session.

### Differences from historical single-run evaluation

`run_layer2.py` directly reads one saved `metrics.csv`, can select the most recently completed compatible run, and accepts compatible 64-bit Layer 1 configurations beyond this exact cohort. Its default output is a timestamp/UUID directory under Week 4. The formal runner pins 20 specific archives, checks regeneration, adds six sweep conditions, requires a plan/checkpoint, and uses an explicitly supplied output directory.

The historical script makes no warm-up reconstruction calls; first-decode compilation is inside its recorded latency. Formal timing follows six separate synthetic probes. Historical and formal latency figures are therefore not interchangeable. Both use the same credential stream, BCH construction, post-return candidate comparison, and four outcome categories. Formal metadata, manifests, clustered uncertainty, and failure-within-radius stopping provide additional controls. The historical workflow has a `COMPLETE` marker but no formal artifact manifest.

`validate_reconstruction.py` is a separate synthetic characterization tool, including wrong-device/wrong-helper controls; it is not part of the formal denominator. Its broader `miscorrection` flag includes decoded wrong messages with invalid padding. Formal `miscorrections` counts **only valid-format wrong credentials**. Those definitions must not be mixed.

## Input Cohort

The ordered cohort is established by `RUN_NAMES`, cross-checked against the seed rows in the historical CSV and historical Layer 2 `metadata.json` input paths and input hashes. Every selected Layer 1 directory is available, complete, and compatible. Every run has six devices, 128 ROs, adjacent pairs `(0,1)` through `(126,127)`, 64-bit responses, manufacturing SD 1.0, nominal frequency 100.0, aging SD 0, zero environmental offsets, noiseless enrollment, nominal measurement SD 0.1, and 100 reads/device/condition.

Exact repository-relative input paths, in required order:

1. 1111: `sim_results/run-seed-1111-vpo3sh6h`
2. 1122: `sim_results/run-seed-1122-lgur9fjd`
3. 1234: `sim_results/run-seed-1234-v1xoukxp`
4. 2121: `sim_results/run-seed-2121-usfoatqu`
5. 2222: `sim_results/run-seed-2222-db2lx0kk`
6. 2391: `sim_results/run-seed-2391-03wppo_e`
7. 3232: `sim_results/run-seed-3232-wj3a0_6t`
8. 3333: `sim_results/run-seed-3333-l3mtfhzs`
9. 4321: `sim_results/run-seed-4321-r4669ysl`
10. 4433: `sim_results/run-seed-4433-6zxhrlva`
11. 4444: `sim_results/run-seed-4444-nu3ol6ct`
12. 5426: `sim_results/run-seed-5426-i67ho8lf`
13. 5555: `sim_results/run-seed-5555-d6jxf7n6`
14. 6543: `sim_results/run-seed-6543-kq_0si3y`
15. 6666: `sim_results/run-seed-6666-s33zjn8w`
16. 7654: `sim_results/run-seed-7654-ewr1xcke`
17. 7777: `sim_results/run-seed-7777-uzkvg0an`
18. 8231: `sim_results/run-seed-8231-9rst2dey`
19. 8888: `sim_results/run-seed-8888-j0tqcdu5`
20. 9999: `sim_results/run-seed-9999-at7p2ufs`

Read-only checks verified 120 reference responses, 12,000 nominal readings and 72,000 saved sweep readings. For every sweep row, condition/noise, device/read identity, 64-bit format, saved Hamming distance and BER were checked; each run has exactly 600 rows at each of six sweep indices. Every selected historical Layer 2 nominal response matched its archived Layer 1 response, and its recorded Layer 1 input hashes matched current bytes.

### Duplicates, exclusions, and transcription discrepancies

- `sim_results/run-seed-1234-ud43sry0` and `sim_results/run-seed-4321-zf9zi47r` are older **10-device** runs and are excluded. The design document's example uses the former and must not be copied for this experiment. No other selected seed has duplicate Layer 1 directories in the inspected archive.
- Seed 2121 has two complete historical Layer 2 runs for the same intended Layer 1 archive: `layer2-single-run-v1-seed-2121-20260922T233639716880Z-bbe3fa70` and `layer2-single-run-v1-seed-2121-20260924T021850357687Z-3f12a4e6`. Both contain 589 successes and 11 decoder failures. The historical CSV's latency matches the September 24 artifact; count it once, not twice.
- The reconciled historical pool uses the September 24 single-run artifact for each of the 20 seeds. Other saved seeds, including 6767 and 9876, are outside this pool. No run was selected for favorable performance.
- For seed 2222, the historical CSV says maximum latency `230472810` ns; the September 24 raw summary says `2304728100` ns. The pooled maximum remains `2390163000` ns. The transcription error is documented here, not repaired in historical evidence.
- Historical prose refers to `results/week3/...`; the actual CSV is under `results/week-3/...`. Research-log narrative dates and artifact creation dates differ; use metadata for artifact chronology.

### Predeclared input fingerprint

The SHA-256 bundle of the 180 files (the nine listed filenames in each of the 20 selected directories) is:

```text
e3332b944bfae4a8fcb9b04522277b13c9312608d36d1e35e7ccbcbb171a60fd
```

Exact bundle definition: build a dictionary from `RUN_DIRECTORY/FILENAME` (forward slashes, no `sim_results/` prefix) to lowercase SHA-256 of the file's bytes; hash UTF-8 `json.dumps(mapping, sort_keys=True, separators=(',', ':'))`, with no trailing newline. This pins the inputs independently of the absolute machine path. It is a plan-level fingerprint; the current loader has no field to enforce it. No input file was rewritten.

## Proposed Formal Configuration

The exact **current-schema-compatible** proposal for `configs/reconstruction_experiment_v1.json` is below. It was validated in memory using the actual `load_plan()` function body extracted from the source, the actual Layer 1 config loader, and the actual Git ancestry check. The file itself has **not** been created.

```json
{
  "experiment_version": "layer2-experiment-v1",
  "checkpoint": "40da3a388983030b7b696ce7bf2b801e0ed6903f",
  "simulation_seeds": [
    1111, 1122, 1234, 2121, 2222, 2391, 3232, 3333, 4321, 4433,
    4444, 5426, 5555, 6543, 6666, 7654, 7777, 8231, 8888, 9999
  ],
  "layer1_config": "configs/puf_baseline.json",
  "credential_stream": "layer2-v1:{simulation_seed}:{device_index}:credential",
  "bootstrap_seed": 20260929,
  "bootstrap_resamples": 10000
}
```

Bootstrap seed 20260929 and 10,000 resamples are proposed fixed analysis choices, not recovered historical settings and not selected by examining bootstrap results.

### What this configuration can and cannot freeze

The current schema indirectly binds reconstruction version, exact BCH parameters, subset, credential length, reading count, nominal noise, and sweep levels through source constants and the referenced Layer 1 JSON. Confidence level is hard-coded at 95%. Exact archive names live in `RUN_NAMES`. Output naming is supplied on the CLI. None of these can be added as top-level plan fields without changing `load_plan()` because it checks exact key equality.

At runtime, `config.json` expands the seven-key plan with `reconstruction: asdict(DEFAULT_CONFIG)` and `layer1_frozen_settings: BASELINE`; metadata records source and input hashes. These records describe what ran, but are **not pre-execution expected-hash checks**. The checkpoint permits descendant changes and uncommitted changes, so the seven-key JSON alone does not enforce the full requested definition.

For a literal single-file, predeclared experiment contract, a small, explicit **runner/schema change is required before execution**: accept and validate exact relative archive identities, expected source/input hashes, expected reconstruction settings, expected Layer 1 settings, confidence level, and output identity (including consistency with CLI arguments). These must be equality constraints for baseline v1, not new tunable reconstruction options. A finalized expanded JSON would require a separately reviewed schema; no unsupported fields are invented in the proposal above. Keep the protected BCH and credential modules unchanged.

If the current schema is retained, reproducibility instead requires the seven-key config **plus** this plan, the pinned source snapshot, the specified command, and the archived inputs. That is a documented limitation, not satisfaction of a self-contained-config requirement.

Proposed output identity: `results/week-5/will/reconstruction/layer2-experiment-v1-formal-001`. It does not exist at audit time. Subsequent authorized executions must use distinct names such as `formal-002`; never replace `formal-001`, even if incomplete. Audit and plots belong in separate sibling paths.

## Outcome Definitions

- **Success:** `reconstruction_outcome == candidate_valid_format`, a non-null returned credential, and a post-return exact match to evaluator-enrolled truth. The record carries `evaluator_correct_match` and `evaluator_success: true`.
- **Decoder failure:** `decoder_failure`, status `uncorrectable`, correction count -1, no candidate message/credential, null padding status, and `decoder_declared_failure`. Evaluator outcome is `no_valid_candidate`, success false.
- **Invalid format/padding:** `invalid_format_or_padding`; the BCH decoder returned a message but its last four bits are not `0000`. The message is retained; credential is null, `padding_valid` is false, reason is `nonzero_padding`, and evaluator outcome is `no_valid_candidate`. Malformed API inputs/backend data raise exceptions; they are not this ordinary noise-related category.
- **Miscorrection:** a valid-format credential is returned, but differs from enrolled truth. Reconstruction still reports `candidate_valid_format`; evaluator reports `evaluator_wrong_match`, success false, and `credential_mismatch`. Padding validity alone cannot detect this case.
- **FRR:** `(decoder_failures + invalid_format + miscorrections) / all_completed_legitimate_attempts`, equal to `1 - success_rate`. This is evaluator-defined reconstruction FRR, not an online authenticated-session rejection rate. Miscorrections count even though the reconstruction routine itself cannot reject them as wrong credentials.
- **Incomplete experiment:** an unexpected exception, interrupted attempt, failed reconciliation, unexpected failure within t=5, source change, or output failure prevents valid completion. A reconstruction exception retains a raw `backend_exception` record, `evaluator_outcome: not_evaluated`, and `evaluator_success: null`; `INCOMPLETE.json` records context, exception and traceback when writing remains possible. Do not count the exception as an ordinary FRR observation or publish partial data as the complete cohort. Preflight failure can occur before an output directory exists; later failures can leave summaries behind. Require a valid `COMPLETE` and manifest, not merely a summary file. Abrupt process/storage failure can prevent even an incomplete marker.

## Nominal Experiment

Nominal measurement-noise SD is **0.1**, in the simulator's abstract frequency units. Enroll once per device from its noiseless saved reference and the separately seeded 32-bit credential. Evaluate all 100 saved nominal readings per device, with no selection by BER, decoding success, or stability.

Denominator: **20 runs x 6 devices x 100 readings = 12,000 attempts**. Each device contributes 100 attempts; each run contributes 600. Zero-error observations are retained. One call to `reconstruct(response64, helper, DEFAULT_CONFIG)` is timed per attempt. The returned candidate is then evaluated against truth and the record retained. No wrong-device attempts are included.

The numerical report must expose total attempts, successes, success rate, FRR, the three separate failure-category counts **and rates**, mean raw BER63/BER64, selected-bit error-count distribution, per-seed and per-device results, clustered uncertainty, and latency mean/median/p95/max/sample count and warm-up policy. The current summaries provide everything in that list except explicit category-rate columns and a directly stored success CI. These are reporting additions, not decoder changes.

## Noise Sweep

The fixed ordered noise SDs are **[0.0, 0.05, 0.1, 0.25, 0.5, 1.0]**, with sweep indices 0 through 5. These are Gaussian per-oscillator measurement-noise levels, not bit-flip probabilities or requested BER values. BER is measured from each observed response.

Each point contains **12,000 attempts**: 100/device and 600/run. Six points contain **72,000 attempts**: 600/device and 3,600/run. Nominal plus sweep contains **84,000 experimental attempts**, 700/device and 4,200/run. Six separate synthetic warm-up calls are excluded from these denominators.

The Layer 1 simulator manufactures each device once, holds its offsets and reference fixed, and uses a continuing measurement RNG across the nominal readings and then the six sweep points. It does not reset the RNG at each point or scale one stored bit mask. Zero noise consumes no measurement RNG draws. The sweep's SD 0.1 readings use later draws than the primary nominal condition; keep their results separate. The same device populations and helpers appear across all conditions, so the conditions are paired, not independent device samples.

For every point report noise SD, measured BER63/BER64, success/FRR, separately labeled decoder-failure/invalid-padding/miscorrection counts and rates, error-count distribution, and latency. No favorable subset of readings or seeds may replace the fixed denominator.

## Statistics

### Random streams

- Manufacturing, enrollment and measurement use distinct `random.Random` instances seeded with `week2-v1:{simulation_seed}:{device_index}:{phase}`, `version=2`, for phases `manufacturing`, `enrollment`, and `measurement`.
- Manufacturing draws independent zero-mean Gaussian offsets once. Measurement draws fresh zero-mean Gaussian noise per RO/read when SD is positive. Enrollment is noiseless under this frozen config.
- Credentials use a separate `Random` seeded with `layer2-v1:{simulation_seed}:{device_index}:credential`, `version=2`, then `getrandbits(32).to_bytes(4, 'big')`. This is deterministic research material, not production secret generation.
- Each condition's bootstrap creates its own `Random(20260929)` and performs 10,000 resamples. It does not consume PUF or credential streams. Reusing the bootstrap seed across equal ordered run lists yields the same cluster-index draws per condition; the runner does not report paired condition-difference intervals.
- Warm-up uses fixed probes without experimental RNG draws. Enrollment IDs are `layer2-experiment-v1:{seed}:{device_id}` and are routing labels, not authenticity checks.

### Confidence intervals

`run_uncertainty()` resamples **20 entire simulation-run clusters with replacement**, 20 selections per replicate, retaining all six devices and all 100 reads/device within each selected run for that condition. Each replicate computes summed failures divided by summed attempts. It never bootstraps individual reads as independent experimental units.

The FRR interval is the **95% percentile cluster-bootstrap interval**, at quantiles 0.025 and 0.975, with linear interpolation at `(n-1)*q`. The runner also reports number of runs, mean run FRR, sample SD across runs (`statistics.stdev`), and minimum/maximum run FRR. Equal per-run denominators make pooled FRR equal to mean run FRR here.

The current runner stores `frr_ci95` only. The exact derived success interval is `[1 - upper_frr, 1 - lower_frr]`; include it explicitly in the planned reporting addition. There are no existing category-rate CIs, BER CIs, latency CIs, simultaneous bands, or paired-difference CIs. Do not claim them. A zero observed rare-event count can yield a degenerate percentile interval and does not demonstrate a zero population risk. Twenty clusters limit precision and generalization.

### Latency

Use `time.perf_counter_ns()` immediately before and after **only `reconstruct()`**, including its input/helper/config validation, XOR construction, BCH call, backend consistency checks, padding check and credential extraction. Exclude PUF generation, bit-string conversion, enrollment, evaluator comparisons, error counting, JSON/CSV writes, logging and plotting. All completed legitimate outcomes, including failures, contribute.

Before experimental enrollment/attempts, `warm_up()` separately records algebra initialization and synthetic warm-up time. It uses an alternating 64-bit response, an all-zero four-byte credential, and these six masks:

```text
()
(0,)
(0, 1, 2, 3, 4)
(0, 1, 2, 3, 4, 5)
(31, 36, 37, 39, 40, 41)
(35, 40, 41, 43, 44, 45)
```

Warm-up records masks, returned outcomes, six probe calls, zero experimental readings consumed, and exclusion of backend import time. It exercises synthetic paths, but is not a proof that every possible backend/JIT path is warm. Preserve any remaining slow observation; do not trim latency outliers or retry them.

Report arithmetic mean, median, p95 by linear interpolation, maximum, and observation count in nanoseconds (optional derived milliseconds). Nominal n=12,000; each sweep point n=12,000; total n=84,000. Environment metadata includes machine/processor, OS, Python/executable, dependency versions, timer characteristics, and available Windows hardware inventory. This measures a warmed Windows Python software prototype, not physical PUF acquisition or embedded-device end-to-end latency.

## Planned Outputs

### Existing runner artifacts

The new evidence directory will contain:

- `config.json`: seven-key plan expanded with frozen reconstruction and Layer 1 settings.
- `metadata.json`: environment, Git HEAD/status, source hashes/source ID, archive-validation summary, per-run archive paths/input hashes, and original experiment-config hash.
- `warm_up.json`: excluded initialization/warm-up timings and synthetic probe policy/results.
- `enrollments.json`: 120 enrollment identities, helpers, credential-stream identities, and explicitly evaluator-only references/credentials.
- `attempts.jsonl`: all 84,000 experimental records on successful completion, with separate outcomes and per-attempt latency/BER.
- `baseline_summary.csv`: one condition row.
- `noise_sweep_summary.csv`: six condition rows.
- `per_run_summary.csv`: 140 rows (20 runs x 7 conditions).
- `per_device_summary.csv`: 840 rows (120 devices x 7 conditions).
- `error_count_summary.csv`: one row for each observed selected-bit error count within each condition; no fixed row count or omission of beyond-radius observations.
- `latency_summary.csv`: seven condition rows, with sample count/mean/median/p95/max.
- `summary.json`: all condition summaries and seven run-cluster uncertainty records.
- `manifest.json`: hashes of all files already written in that directory; it does not hash itself or `COMPLETE`.
- `COMPLETE`: experiment version, 84,000 completed attempts, source ID, and manifest SHA-256, written last after reconciliation.
- `INCOMPLETE.json` instead of valid completion if an error is caught and can be recorded. Partial evidence is preserved.

The raw records include actual selected and full-response errors as evaluator fields. A backend's reported correction count is not the actual number of errors relative to enrollment and must not replace that error distribution.

### Required report additions

Current detailed summaries retain all three failure-category counts separately, but not their rates. Add explicitly named columns `decoder_failure_rate = decoder_failures / attempt_count`, `invalid_format_rate = invalid_format / attempt_count`, and `miscorrection_rate = miscorrections / attempt_count` to a versioned derived report (or consistently extend summary generation and its audit). Include success CI endpoints derived from FRR endpoints and a visible warm-up-policy reference. Do not silently replace existing historical tables. These calculations require no additional reconstruction attempts.

### Plots

The existing [plot_reconstruction.py](../src/python/scripts/plot_reconstruction.py) is a separate command. It verifies the evidence manifest, refuses an existing plot directory, and produces these PNG/SVG pairs plus `provenance.json`:

- `performance_vs_noise`: success versus noise, FRR versus noise, and success versus observed mean BER63; the primary nominal point is distinguished from the sweep's later RNG draws.
- `baseline_error_outcomes`: nominal outcome counts by actual selected-bit error count and separate within-error-count failure-category fractions, with a boundary at 5.5 errors.
- `sweep_error_outcomes`: six error-count panels, with all four categories separated.

The plotter currently provides **no FRR-versus-BER panel, no direct miscorrection-rate-versus-noise/BER plot, and no CI error bars**. Add the first two to satisfy the requested plot set; expose computed cluster intervals on success/FRR plots if uncertainty visualization is desired. Retain explicit zero counts and denominators in rare-outcome plots. Historical miscorrections exist, but formal counts must come from the future completed evidence. Plot provenance hashes the plotting source and records Matplotlib and evidence-manifest identity. It does not create an independent experiment or belong to the runner's original evidence manifest.

### Reconciliation and completion checks

The runner checks unique reading identities, exact expected count, response equality, disk-readback accounting, and the identity `failures = decoder_failures + invalid_format + miscorrections`. It checks selected source hashes before and after evaluation and creates the manifest and `COMPLETE` last.

[audit_reconstruction_experiment.py](../src/python/scripts/audit_reconstruction_experiment.py) independently reads completed evidence without importing the simulator or decoder. It checks the 84,000 count, manifest hashes, current source hashes, 120 enrollments, unique archive-reading identity/response matching, selected subset, actual error counts/BER, candidate/evaluator decisions, outcome constraints, no backend exceptions, nonnegative times, within-radius correctness, nominal-before-sweep ordering, and seven 12,000-attempt groups. It independently recomputes the six CSV families and summary metrics, including latency, and writes a new audit JSON report.

Limits of that auditor: it does not independently recompute the bootstrap intervals or verify warm-up policy; it reads archive response tables but does not individually revalidate every recorded archive hash; it assumes current sources equal recorded sources and absolute archive paths remain usable. It uses Python `assert`, so run it without `-O`. The core runner source map does not include the audit or plot scripts; those record their own hashes. The manifest is an integrity/reconciliation record, not a signed authenticity proof. Before formal publication, add independent bootstrap/config/hash checks to close these provenance gaps.

## Bias/Leakage Controls

Static inspection found no forbidden bit selection, retries, voting, erasures, or ground-truth feedback into reconstruction. The fixed subset is encoded in `ReconstructionConfig.response_indices = tuple(range(63))`; every config field is validated against the frozen defaults. The bit-instability analysis imported by the runner is descriptive; its rankings are not consumed by `enroll()` or `reconstruct()`. Bit 63 is omitted solely for code length.

Each experimental call receives only the noisy 64-bit tuple, public helper object, and fixed config. Helper data contain helper bits, config, and an enrollment ID, not the evaluator reference or credential. Truth is used during trusted enrollment and separately during evaluation; the returned candidate is compared to enrolled truth only after the call returns. Computing evaluator BER before the formal call does not feed that BER to the decoder. One original reading yields one attempt, including zero-error and high-error readings.

All 20 runs and every saved reading are retained by predeclared identity. The same dataset has already informed the pilot's design and historical reporting, so this is not a blinded holdout evaluation. Do not present bootstrap uncertainty as correcting for prior design choices or proving selection-free generalization to hardware. Future variants must have separate versioned evidence and evaluation design; none are introduced here.

Wrong-device reconstruction is **excluded** from the nominal and sweep denominators. Existing synthetic wrong-device/helper controls remain separate. This experiment makes no false-acceptance, authentication, or independent-verifier claim.

## Known Limitations

- Synthetic, uncalibrated Gaussian RO model; no physical PUF measurements or production-security claim.
- Idealized noiseless enrollment, no aging, and zero environment offsets; the common additive environmental model would cancel in pair comparisons and is not realistic differential environmental sensitivity.
- A deterministic 32-bit proof-of-mechanism credential, four padding bits, and no independent credential verification inside reconstruction. Padding is format validation only.
- Single-read BCH(63,36,t=5) baseline. Beyond five actual errors, decoder failure, invalid padding, or an undetected valid-format wrong candidate can occur.
- Only 20 simulation-run clusters and 120 devices; repeated reads and paired noise conditions are not independent population samples. Rare-event uncertainty is limited.
- The nominal re-evaluation reuses historical responses, devices and credentials. It must not replace historical results or be described as fresh experimental replication.
- Reproducibility of simulated bytes and candidate outcomes is distinct from timing reproducibility. Historical cold-start and planned warmed timing answer different questions.
- Exact-byte regeneration depends on simulator code and serialization/runtime behavior. It has intentionally not been executed in this audit. A mismatch must stop execution and be investigated, never repaired by silently replacing archives.
- The current config cannot enforce every requested fixed field/hash/output identity. Runtime-recorded provenance is not equivalent to a predeclared expected-input contract.

### Readiness and required work before execution

1. Review this proposal and explicitly authorize subsequent config creation/execution. Until then, leave the requested config absent and do not run reconstruction.
2. Resolve the single-file requirement with the runner/schema equality checks described above; preserve the BCH and credential algorithm unchanged. Add schema tests and read-only expected-hash validation before the long run. If the existing seven-key schema is accepted instead, acknowledge the external plan/source/input dependencies explicitly.
3. Add reporting for category rates and success CI, and the missing FRR-versus-BER and miscorrection-rate plots. These can be derived from saved evidence without changing decoding; prepare their definitions before the experiment. Extend accounting checks to cover any new fields and independently reconcile bootstrap output.
4. Confirm the approved source snapshot and input fingerprint immediately before execution, record any runner/reporting-only revisions explicitly, and use a new output directory. Do not treat the ancestry check alone as source locking.

No core reconstruction change is required to execute the existing nominal/sweep algorithm. Creating a compatible config removes the immediate missing-file blocker. The extra items above are needed for the full requested reproducibility/reporting contract, not to redesign reconstruction.

The sandbox initially could not access archived files or the venv's base Python. Read-only elevated inspection resolved this visibility issue: the existing venv works and reports Python 3.12.4, galois 0.4.11, NumPy 2.5.3, Numba 0.67.0, llvmlite 0.49.0, and Matplotlib 3.10.6. No environment repair or package installation was performed. Actual BCH initialization has not been tested in this audit. The sandbox's separate MSYS Python lacks galois and is not the intended experiment interpreter.

## Execution Command

**For review only. Do not execute until explicitly authorized and the pre-execution requirements are resolved.** From the repository root, using the existing Windows venv:

```powershell
.\.venv\Scripts\python.exe -B src/python/scripts/run_reconstruction.py `
  --config configs/reconstruction_experiment_v1.json `
  --archive sim_results `
  --output results/week-5/will/reconstruction/layer2-experiment-v1-formal-001
```

After successful completion, these are the existing separate audit/plot command shapes; use them only against the new evidence, never historical single-run folders:

```powershell
.\.venv\Scripts\python.exe -B src/python/scripts/audit_reconstruction_experiment.py `
  --evidence results/week-5/will/reconstruction/layer2-experiment-v1-formal-001 `
  --output results/week-5/will/reconstruction/layer2-experiment-v1-formal-001-audit.json

.\.venv\Scripts\python.exe -B src/python/scripts/plot_reconstruction.py `
  --evidence results/week-5/will/reconstruction/layer2-experiment-v1-formal-001 `
  --output results/week-5/will/reconstruction/layer2-experiment-v1-formal-001-plots
```

No command above was executed. No simulator, reconstruction, warm-up, synthetic characterization, noise sweep, or new experimental batch was run. Read-only archival reconciliation and in-memory configuration/schema validation produced no experimental result files.

## Audited Source Fingerprints

The current runner's source-map aggregate (`sha256(json.dumps(source_hashes, sort_keys=True).encode())`, using default JSON separators) is:

```text
410cc949953619beeae988c7ff02c14b4f04780a9fa4c6d13d00265742e7929d
```

The exact current map is retained here for review. If approved runner/reporting changes alter a hashed file, update the approved pre-execution snapshot explicitly; the BCH/credential fingerprints must remain unchanged for baseline v1.

```json
{
  "configs/puf_baseline.json": "fb54059dc268ef86300d90a4468fcf200b0c73d13c28fad1402a84a075271cda",
  "pyproject.toml": "4388921be04c897c8f13327c4ad911bc2831d4eb8f0bfbecb689eea1d174e0f0",
  "requirements.txt": "cad4e21b64d0fe1a4c2c4855e5b779a1ef9ff1601d06acf50e3aa1716dc4d059",
  "src/python/puf_snn/puf/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "src/python/puf_snn/puf/device.py": "a9298bd1f9b9f8c8bd6527f63c2cacd8fcb7fb4fe72fa3f1f1c847bedf130d2b",
  "src/python/puf_snn/puf/metrics.py": "5e97202f8edac0564fe365f018a723eefada04845fdaa04ad3911f0aa39895e5",
  "src/python/puf_snn/puf/ro_puf.py": "ff553522eba5e94283ec49b668bb758a3e7595d03c3f5596666925edb4dbc995",
  "src/python/puf_snn/puf/variables.py": "128f6f7dd7ccc0dc4d5752b21525562149d661c6c79f9752be8fe132afd55af7",
  "src/python/puf_snn/reconstruction/__init__.py": "83051b37b18ecfbdf6cb57ad3c9ee6ae34c1cee3042ad1e809c4e1d6e140ab92",
  "src/python/puf_snn/reconstruction/bch.py": "4b17daf39a97698a368d817a765c2bc8a7e5804468396573329428c01d3f44a6",
  "src/python/puf_snn/reconstruction/credential.py": "14463ca853ac5a54f326d18537e5ae76008ffde7240433ad52afa8acf2ae08ef",
  "src/python/scripts/analyze_week2_response_bits.py": "8c36eb7705bd302b7871cba72bb49b8107885082c5ab2eafe4a3330c515e8efc",
  "src/python/scripts/run_puf_baseline.py": "4892ca0f99c4b86db63cb2a0f4ab4e7c167762de794782955bea85019de77773",
  "src/python/scripts/run_reconstruction.py": "5101e3ac1cca1d4d09dc4c35feb40f83c610b6393f5ac60f7f2f56897baa4f75"
}
```

Additional audited files:

```text
src/python/scripts/audit_reconstruction_experiment.py
56fd4cfe39857f738d238124286cc7e0ae9345a6f9adeabddda70bd7396adc8c
src/python/scripts/plot_reconstruction.py
ce072087d0d80a7e2d11bdd130478eb61f9abd30b5614587555b5b8011d1b888
tests/experiments/test_reconstruction_experiment.py
40f42adf3734b20b0933098653ff09fe178df58730728217384f1e7634f59273
```
