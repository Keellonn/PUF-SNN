# Layer 2 Formal Reconstruction Evaluation

Formal result draft. Execution date: September 29, 2026 (America/New_York); UTC execution crossed into September 30. Status: **COMPLETE; integrity verification PASS; independent audit PASS**.

## Scope

This software experiment evaluates a simulated ring-oscillator PUF with the frozen BCH(63,36,t=5) reconstruction baseline. It uses the established 20-run cohort and 120 simulated devices. The nominal condition is a reproducible re-evaluation of historical observations and deterministic credentials, not independent replication. The six-point noise sweep extends the characterization over the archived noise conditions.

Layer 2 selects the fixed response bits 0 through 62 from each 64-bit response, omitting bit 63 for the BCH code length. The message is a 32-bit pilot credential followed by four zero padding bits. Each attempt uses one reading and one decode; there are no retries, voting, erasures, stable-bit selection, alternative ECC parameters, or independent credential verification. Candidate correctness is evaluated against enrolled truth only after reconstruct() returns.

## Experiment Configuration

The approved [configuration](../configs/reconstruction_experiment_v1.json), [plan](layer2-formal-experiment-plan-week5.md), and [preflight](layer2-formal-experiment-preflight-week5.md) define this execution. The seven-field configuration was accepted as the pilot schema; its single-file predeclared-contract limitation remains.

- Source checkpoint and actual Git HEAD: `40da3a388983030b7b696ce7bf2b801e0ed6903f`.
- Config: `configs/reconstruction_experiment_v1.json`.
- Config SHA-256: `07be1acd3c3980842a867de3fc08e32a79543c4262dd3a42832f4284a76525cb`.
- Predeclared 180-file input fingerprint: `e3332b944bfae4a8fcb9b04522277b13c9312608d36d1e35e7ccbcbb171a60fd`.
- Reconstruction BCH SHA-256: `4b17daf39a97698a368d817a765c2bc8a7e5804468396573329428c01d3f44a6`.
- Credential source SHA-256: `14463ca853ac5a54f326d18537e5ae76008ffde7240433ad52afa8acf2ae08ef`.
- Runner source-map aggregate/source ID: `410cc949953619beeae988c7ff02c14b4f04780a9fa4c6d13d00265742e7929d`.
- Evidence directory: `results/week-5/will/reconstruction/layer2-experiment-v1-formal-001`.
- Population: 20 runs x 6 devices = 120 devices; 128 ROs/device, adjacent pairing, 64-bit responses; manufacturing SD 1.0, nominal frequency 100.0, noiseless enrollment, zero aging and environmental offsets.
- Nominal: measurement-noise SD 0.1; 100 reads/device; **12,000 attempts**.
- Sweep: SD `[0.0, 0.05, 0.1, 0.25, 0.5, 1.0]`; 100 reads/device/point; **12,000 attempts/point and 72,000 sweep attempts**.
- Total: **84,000 experimental attempts**. Six synthetic warm-up probes are excluded.
- Bootstrap: 10,000 replicates, seed 20260929, whole simulation-run clusters, 95% percentile intervals with linear quantile interpolation.
- Latency: warmed `time.perf_counter_ns()` around `reconstruct()` only; all completed outcomes included.

The exact ordered seed cohort is 1111, 1122, 1234, 2121, 2222, 2391, 3232, 3333, 4321, 4433, 4444, 5426, 5555, 6543, 6666, 7654, 7777, 8231, 8888, 9999. Exact archive identities remain in the plan and formal metadata. RNG streams separate manufacturing/enrollment/measurement (`week2-v1:{seed}:{device_index}:{phase}`) from credentials (`layer2-v1:{seed}:{device_index}:credential`). Measurement draws continue across conditions. The nominal and sweep SD 0.1 observations are different draws on the same devices.

The final immediate gate matched all expected values and confirmed that the output directory did not exist. Exactly one process executed the approved command:

```powershell
.\.venv\Scripts\python.exe -B src/python/scripts/run_reconstruction.py `
  --config configs/reconstruction_experiment_v1.json `
  --archive sim_results `
  --output results/week-5/will/reconstruction/layer2-experiment-v1-formal-001
```

Process exit code: **0**. Wall runtime: **106.4572764 seconds** (1 minute 46.457 seconds), measured by a PowerShell Stopwatch around the invocation, including startup, archive regeneration/checks, warm-up, evaluation, summaries and final writes. Start: `2026-09-30T03:37:02.2131337Z`; finish: `2026-09-30T03:38:48.6700719Z`. These are execution-wrapper observations recorded here, separate from per-attempt latency and the sealed evidence manifest.

Environment: Windows Python 3.12.4 (MSC v.1940, AMD64); galois 0.4.11, NumPy 2.5.3, Numba 0.67.0, llvmlite 0.49.0, Matplotlib 3.10.6. Machine metadata identify Micro-Star International MS-7D98, Intel64 Family 6 Model 151 Stepping 2, with 34,191,159,296 bytes of physical memory. No Quest device or physical PUF participated.

## Nominal Results

All rates below use 12,000 attempts as the denominator. FRR includes decoder failures, invalid padding, and valid-format wrong credentials. It is evaluator-defined reconstruction FRR, not an online authentication rejection rate.

| Metric | Result |
| --- | --- |
| Attempts | 12,000 |
| Correct reconstructions | 11,805 |
| Reconstruction success | 98.375000% |
| Failures | 195 |
| FRR | 1.625000% |
| Decoder failures | 186 (1.550000%) |
| Invalid format/padding | 7 (0.058333%) |
| Valid-format wrong credentials | 2 (0.016667%) |
| Mean BER63 | 0.031970899470899469 (3.197090%) |
| Mean BER64 | 0.032075520833333336 (3.207552%) |
| FRR 95% cluster-bootstrap interval | [1.241667%, 2.016667%] |
| Derived success 95% interval | [97.983333%, 98.758333%] |

The raw selected-bit error total is 24,170 / 756,000 comparisons; full-response errors are 24,634 / 768,000. Exact counts are authoritative; displayed rates and millisecond timings are rounded.

## Historical Reconciliation

**The formal nominal re-evaluation exactly reproduces all historical outcome counts.**

| Outcome | Historical | Formal | Difference |
| --- | --- | --- | --- |
| Attempts | 12000 | 12000 | 0 |
| Correct credentials | 11805 | 11805 | 0 |
| All failures | 195 | 195 | 0 |
| Decoder failures | 186 | 186 | 0 |
| Invalid format/padding | 7 | 7 | 0 |
| Valid-format wrong credentials | 2 | 2 | 0 |

Both nominal FRRs are exactly 195/12,000 = **1.625%**. This agreement is expected from re-evaluating the same fixed cohort and credential streams; it does not add an independent sample. Historical latency included first-decode cold-start compilation, whereas this experiment warms the backend first. Timing equality was neither required nor observed. Historical evidence was not modified, relabeled or replaced.

## Noise-Sensitivity Results

Each row is a separate condition with 12,000 attempts. BER and success/FRR columns are percentages. Decoder failure, invalid padding and miscorrection columns are separate counts. Latencies are milliseconds.

| Noise SD | Attempts | Mean BER63 % | Successes | Success % | FRR % | Decoder failures | Invalid padding | Miscorrections | Median ms | p95 ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 12000 | 0.000000 | 12000 | 100.000000 | 0.000000 | 0 | 0 | 0 | 0.145000 | 0.251000 |
| 0.05 | 12000 | 1.605026 | 11997 | 99.975000 | 0.025000 | 3 | 0 | 0 | 0.894500 | 1.949805 |
| 0.1 | 12000 | 3.171693 | 11815 | 98.458333 | 1.541667 | 175 | 5 | 5 | 1.005450 | 2.130135 |
| 0.25 | 12000 | 7.814815 | 7610 | 63.416667 | 36.583333 | 4208 | 113 | 69 | 1.042650 | 2.070430 |
| 0.5 | 12000 | 14.862566 | 912 | 7.600000 | 92.400000 | 10552 | 342 | 194 | 0.976800 | 1.985400 |
| 1 | 12000 | 25.158201 | 3 | 0.025000 | 99.975000 | 11323 | 514 | 160 | 0.980500 | 1.936945 |

The sweep SD 0.1 result (185 failures; 1.541667% FRR) is distinct from the primary nominal SD 0.1 result (195 failures; 1.625% FRR). Later measurement RNG draws explain this distinction; the conditions were not pooled or substituted.

## BER and Reconstruction Behavior

- The first tested sweep level with nonzero FRR is **SD 0.05**: 3 decoder failures out of 12,000 (0.025%), at mean BER63 1.605026%.
- The first tested sweep level with a valid-format wrong credential is **SD 0.1**: 5/12,000 (0.041667%). The separate primary nominal condition at SD 0.1 has 2/12,000.
- As mean BER63 rises across the sweep from 0% to 25.158201%, FRR rises from 0% to 99.975%. At SD 0.25, mean BER63 is 7.814815% and FRR is 36.583333%; at SD 0.5, these become 14.862566% and 92.4%.
- Decoder-declared failures dominate the increase. At SD 0.25, 0.5 and 1.0 their counts are 4,208, 10,552 and 11,323, versus invalid-padding counts of 113, 342 and 514 and valid-format wrong-credential counts of 69, 194 and 160.
- **All 56,142 attempts with at most five actual selected-bit errors succeeded.** There were zero unexpected in-radius failures. All 27,858 beyond-radius attempts failed in this dataset; this observed behavior is not a universal claim about every possible beyond-radius error pattern.
- Miscorrection probability among attempts is not monotonic over the tested conditions: it peaks at SD 0.5 and declines at SD 1.0 while total FRR continues to rise. Do not infer a general continuous-noise threshold from these six sampled points.

These observations characterize the frozen single-read software baseline over its observed error distribution; they make no production-security claim.

## Miscorrections

A formal miscorrection is a **returned valid-format credential that differs from enrolled truth**. Padding is only a format check; it is not an independent credential verifier. Invalid-padding outcomes are separately classified and are not included in the formal miscorrection counts.

All seven formal conditions are listed separately below. Every rate uses the condition's 12,000 attempts, not its candidate-only or failure-only subset.

| Condition | Wrong credentials | Rate among all attempts |
| --- | --- | --- |
| Nominal (0.1) | 2 | 0.016667% |
| Sweep 0 | 0 | 0.000000% |
| Sweep 0.05 | 0 | 0.000000% |
| Sweep 0.1 | 5 | 0.041667% |
| Sweep 0.25 | 69 | 0.575000% |
| Sweep 0.5 | 194 | 1.616667% |
| Sweep 1 | 160 | 1.333333% |

There are **430 valid-format wrong credentials in the complete evidence: 2 nominal and 428 across the six sweep conditions**. This bookkeeping total does not define a pooled operational miscorrection probability across different noise conditions. The maximum observed condition rate is **194/12,000 = 1.616667%**, at SD 0.5.

The two nominal locations and five sweep SD 0.1 locations are listed explicitly below. Attempt numbers and device indices are zero-based; JSONL line numbers are one-based. All remaining miscorrection line locations are listed in the appendix.

| Condition | JSONL line | Seed | Device | Attempt | Actual errors63 |
| --- | --- | --- | --- | --- | --- |
| Nominal | 2789 | 2222 | device-3 | 88 | 6 |
| Nominal | 7976 | 6543 | device-1 | 75 | 7 |
| Sweep 0.1 | 38345 | 2121 | device-5 | 44 | 6 |
| Sweep 0.1 | 41972 | 4433 | device-5 | 71 | 6 |
| Sweep 0.1 | 42563 | 4444 | device-5 | 62 | 6 |
| Sweep 0.1 | 44232 | 6543 | device-4 | 31 | 6 |
| Sweep 0.1 | 45955 | 7777 | device-3 | 54 | 6 |

The authoritative filter in `attempts.jsonl` is `evaluator_outcome == "evaluator_wrong_match"`. Each located record retains candidate bits/credential, padding status, evaluator mismatch, response, selected errors, seed/device/read identity, and phase/sweep index. The independent audit JSON also includes both nominal wrong-credential records.

## Latency

Timing brackets only `reconstruct()` with `time.perf_counter_ns()`. It includes input/helper/config validation, subset/XOR construction, BCH decoding and consistency checks, padding validation, and candidate extraction. It excludes PUF simulation/acquisition, enrollment, reference/error counting, evaluator comparison, serialization, disk flushes, bootstrap calculations, plotting and audit work. All completed outcomes, including failures, contribute. These are software timings, not physical-device end-to-end latency.

The nominal warmed latency statistics are:

| Statistic | Milliseconds | Observations |
| --- | --- | --- |
| Mean | 1.170002408 | 12000 |
| Median | 1.037800000 | 12000 |
| p95 | 2.262365000 | 12000 |
| Maximum | 16.622600000 | 12000 |

The nominal mean is `1170002.4083333334` ns, median `1037800.0` ns, p95 `2262364.999999999` ns, and maximum `16622600` ns. p95 uses linear interpolation at `(n-1)*0.95`; the fractional floating-point value is retained in the raw summary. No latency outliers were removed.

Warm-up initialized fixed BCH algebra in 3.639368500 seconds, then enrolled a synthetic helper and performed six fixed probes in 2.278122000 seconds. These stages and backend import time are outside per-attempt latency. Warm-up consumed 0 experimental readings. Its outcomes included valid-format candidates, decoder failure and invalid padding. Six probes are not a proof that every possible backend path is warm. Total experimental latency sample count is 84,000, with 12,000 per condition.

## Statistical Uncertainty

The nominal **FRR 95% cluster-bootstrap interval is [1.241667%, 2.016667%]**, with exact stored fractional endpoints `[0.012416666666666666, 0.020166666666666666]`. The corresponding derived success interval is **[97.983333%, 98.758333%]**, calculated as `[1 - FRR upper, 1 - FRR lower]`.

For each condition, 20 simulation-run clusters are resampled with replacement, retaining all six devices and 100 readings/device within each selected run. Each of 10,000 replicates uses summed failures divided by summed attempts. Seed 20260929 initializes a separate bootstrap RNG for each condition. The 2.5th/97.5th percentiles use linear interpolation. This preserves within-run grouping rather than treating repeated reads as independent devices.

Saved condition-specific FRR intervals are:

| Condition | FRR % | 95% FRR interval % |
| --- | --- | --- |
| Nominal (0.1) | 1.625000 | [1.241667, 2.016667] |
| Sweep 0 | 0.000000 | [0.000000, 0.000000] |
| Sweep 0.05 | 0.025000 | [0.000000, 0.050000] |
| Sweep 0.1 | 1.541667 | [1.191667, 1.925000] |
| Sweep 0.25 | 36.583333 | [34.016667, 39.133333] |
| Sweep 0.5 | 92.400000 | [91.158333, 93.558333] |
| Sweep 1 | 99.975000 | [99.950000, 100.000000] |

Nominal run FRRs range from 0.166667% to 3.833333%, with sample SD 0.906241 percentage points. The independent accounting audit found 46 of 120 devices with nominal failures and 36 with nominal FRR above 1%.

A separate read-only recomputation from `per_run_summary.csv` exactly matched all seven saved bootstrap intervals. This supplementary check is distinct from the unchanged independent audit script, which does not itself recompute bootstrap intervals. No decoder or simulator was called for interval reconciliation. There are no category-specific or latency confidence intervals here. The zero-noise [0,0] bootstrap interval reflects zero observed failures; it does not establish zero population risk. Intervals are condition-specific, not simultaneous or paired-difference intervals, and use only 20 simulated run clusters.

## Integrity and Audit

The process exited 0, `COMPLETE` and `manifest.json` exist, and no `INCOMPLETE.json` exists. All 12 manifest-listed artifacts and the manifest hash stored in `COMPLETE` verified. The six required CSV families and JSON/JSONL artifacts exist.

Manifest SHA-256: `082db862432da3d1b523f247035d2ae5d27be3a387317792f6eda8e72960a71b`. Independent audit report SHA-256: `02f30f9fe9d4eca10e2691b769441fb39b4752e94f74ea993f8e999567f784ca`.

The unchanged independent audit was run only after successful completion verification:

```powershell
.\.venv\Scripts\python.exe -B src/python/scripts/audit_reconstruction_experiment.py `
  --evidence results/week-5/will/reconstruction/layer2-experiment-v1-formal-001 `
  --output results/week-5/will/reconstruction/layer2-experiment-v1-formal-001-audit.json
```

It exited **0** with **PASS**. It confirmed 84,000 unique archived-response matches, 120 enrollments, 12,000 nominal attempts, six sweep groups of 12,000, 72,000 sweep attempts, 1,087 independently reconciled summary groups, no backend exceptions, no in-radius failures, and separate outcome categories. Warm-up metadata and the total of all condition latency sample counts independently confirmed warm-up exclusion.

The runner's archive-regeneration/hash checks passed before evaluation. Source hashes were stable through evaluation and matched again in the independent audit. The raw evidence is sealed by its manifest; the audit and this draft are separate derived artifacts outside that manifest. The runner, auditor and plotting code were not modified. No plots were generated and no category-rate columns were added to saved experimental files; rates displayed in this document are derived from immutable counts.

No runtime, completion, accounting or integrity anomaly was found. The nominal/sweep SD 0.1 difference and nonmonotonic miscorrection rate are reported explicitly above. Maximum nominal latency was retained rather than filtered. Existing user changes were present before the run and are recorded in metadata; no source/config edits, staging, commits or pushes were performed in this execution task. The approved directory was used once, with no second run or retry.

## Limitations

- Simulation only: no physical PUF, FPGA, or Quest hardware was measured.
- Idealized noiseless enrollment, Gaussian manufacturing/read noise, no aging, and zero environmental offsets; these are not calibrated hardware conditions.
- Twenty simulated run clusters and 120 devices; repeated reads and paired conditions are dependent observations, and the bootstrap cannot create additional independent populations.
- The historical cohort was reused and had already informed pilot design. Nominal re-evaluation is not independent replication or blinded holdout validation.
- A deterministic 32-bit proof-of-mechanism credential is used. Padding is not credential authenticity or an independent verifier; no independent credential verifier has been implemented.
- A valid-format wrong candidate remains possible beyond the correction radius. Reconstruction FRR and miscorrection rates are not Layer 3 authentication/FAR measurements.
- Warmed Windows Python timings are machine/runtime-dependent and exclude PUF acquisition and end-to-end authentication. They are not directly comparable with historical cold-start timings.
- The accepted seven-field config relies on code constants, exact archive identities and recorded provenance for the full definition. Manifests provide integrity accounting, not signed authenticity.
- No production-security claim is made. No reconstruction alternative or optimization was introduced.

## Evidence Paths

- [COMPLETE](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/COMPLETE)

- [manifest.json](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/manifest.json)

- [config.json](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/config.json)

- [metadata.json](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/metadata.json)

- [warm_up.json](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/warm_up.json)

- [enrollments.json](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/enrollments.json)

- [attempts.jsonl](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/attempts.jsonl)

- [baseline_summary.csv](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/baseline_summary.csv)

- [noise_sweep_summary.csv](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/noise_sweep_summary.csv)

- [per_run_summary.csv](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/per_run_summary.csv)

- [per_device_summary.csv](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/per_device_summary.csv)

- [error_count_summary.csv](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/error_count_summary.csv)

- [latency_summary.csv](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/latency_summary.csv)

- [summary.json](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/summary.json)

- [Independent audit JSON](../results/week-5/will/reconstruction/layer2-experiment-v1-formal-001-audit.json)

- [Approved input configuration](../configs/reconstruction_experiment_v1.json)

## Appendix: Every Miscorrection Record Location

All locations below are one-based lines in `results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/attempts.jsonl`. They enumerate all 430 records with `evaluator_outcome == "evaluator_wrong_match"`. They are an index into the sealed evidence, not additional observations. Sweep SD 0 and 0.05 have no such records.

### Nominal (0.1): 2 records (0.016667%)

```text
2789, 7976
```

### Sweep 0.1: 5 records (0.041667%)

```text
38345, 41972, 42563, 44232, 45955
```

### Sweep 0.25: 69 records (0.575000%)

```text
48030, 48084, 48183, 48186, 48194, 48324, 48489, 48720, 48727, 48917, 48946, 48991, 49103, 49130,
50172, 50338, 50348, 50724, 50854, 50966, 50978, 51161, 51213, 51228, 52018, 52039, 52100, 52228,
52345, 52469, 52839, 52842, 52895, 53365, 53805, 53907, 53909, 54039, 54257, 54455, 54570, 55149,
55516, 55556, 55892, 55976, 56286, 56367, 56625, 56754, 56902, 56960, 56971, 57112, 57122, 57133,
57166, 57378, 57706, 57775, 57935, 58102, 58171, 58175, 58622, 58747, 58852, 59264, 59753
```

### Sweep 0.5: 194 records (1.616667%)

```text
60020, 60023, 60076, 60115, 60177, 60186, 60215, 60219, 60255, 60298, 60432, 60441, 60466, 60485,
60606, 60734, 60785, 60874, 60884, 61009, 61044, 61063, 61172, 61174, 61191, 61197, 61325, 61365,
61394, 61458, 61506, 61557, 61564, 61696, 61738, 61885, 61934, 61942, 61963, 61981, 62169, 62283,
62464, 62470, 62478, 62481, 62486, 62722, 62834, 62857, 62912, 62919, 63084, 63166, 63237, 63246,
63459, 63473, 63501, 63586, 63591, 63618, 63690, 63842, 63962, 64182, 64299, 64391, 64542, 64698,
64808, 64824, 64882, 64885, 64898, 65021, 65026, 65232, 65297, 65396, 65448, 65499, 65512, 65594,
65784, 65938, 65973, 66136, 66151, 66153, 66182, 66202, 66263, 66420, 66423, 66437, 66465, 66479,
66555, 66560, 66705, 66753, 66825, 66833, 66938, 66964, 66994, 67012, 67054, 67062, 67067, 67074,
67305, 67309, 67381, 67477, 67490, 67612, 67613, 67689, 67697, 67831, 67873, 67905, 68020, 68038,
68106, 68108, 68124, 68128, 68131, 68186, 68193, 68194, 68197, 68279, 68377, 68514, 68548, 68659,
68809, 68821, 68838, 68882, 68921, 68949, 68956, 69039, 69078, 69105, 69126, 69338, 69372, 69456,
69482, 69495, 69551, 69555, 69613, 69708, 69722, 69733, 69758, 69759, 69766, 70020, 70081, 70171,
70175, 70193, 70226, 70257, 70294, 70344, 70452, 70475, 70518, 70674, 70678, 70691, 70724, 70738,
70763, 70800, 70813, 70967, 71061, 71143, 71556, 71624, 71627, 71645, 71917, 71971
```

### Sweep 1: 160 records (1.333333%)

```text
72030, 72095, 72099, 72204, 72232, 72257, 72285, 72296, 72323, 72349, 72377, 72477, 72479, 72495,
72606, 72659, 72742, 72781, 72789, 72824, 73118, 73173, 73188, 73326, 73339, 73547, 73796, 73931,
74020, 74057, 74384, 74530, 74601, 74958, 74985, 75022, 75104, 75226, 75285, 75297, 75842, 75860,
76025, 76332, 76337, 76349, 76355, 76449, 76471, 76478, 76522, 76561, 76671, 76692, 76879, 76995,
77036, 77096, 77191, 77224, 77227, 77289, 77373, 77394, 77420, 77450, 77504, 77526, 77700, 77723,
78060, 78182, 78462, 78528, 78536, 78548, 78621, 78644, 78664, 78672, 78882, 78942, 78976, 78985,
79029, 79045, 79085, 79420, 79507, 79535, 79557, 79608, 79674, 79761, 79918, 79976, 79993, 80071,
80146, 80226, 80319, 80331, 80356, 80362, 80367, 80428, 80460, 80522, 80606, 80682, 80720, 80740,
80848, 80924, 81057, 81159, 81175, 81276, 81332, 81377, 81473, 81580, 81595, 81739, 81811, 81867,
81869, 81885, 82025, 82130, 82335, 82343, 82347, 82380, 82394, 82413, 82442, 82459, 82503, 82506,
82629, 82635, 82773, 82848, 82928, 82978, 83098, 83157, 83206, 83224, 83247, 83429, 83498, 83541,
83632, 83795, 83868, 83906, 83911, 83944
```
