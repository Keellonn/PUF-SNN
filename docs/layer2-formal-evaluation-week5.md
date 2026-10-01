# Layer 2 Formal Reconstruction Evaluation

**Owner:** Will Wallace  
**Week:** 5  
**Status:** Complete

## Purpose
This experiment formally evaluates the frozen Layer 2 PUF credential-reconstruction baseline over the established simulated-device cohort. The goal is to measure how reliably the enrolled credential can be reconstructed from noisy PUF responses, characterize how reconstruction changes as measurement noise increases, identify the types of failures that occur, and measure reconstruction latency. The experiment evaluates both the normal operating condition and a controlled six-point noise sweep. It preserves the existing BCH reconstruction design rather than changing or optimizing it, allowing the results to serve as a formal baseline for later reconstruction improvements. The primary nominal condition reuses the established historical devices, responses, and deterministic credential streams. Therefore, it is a reproducible formal re-evaluation of the existing cohort rather than an independent replication with new devices.

## Frozen Reconstruction Baseline

### BCH Configuration
The reconstruction system uses a full-length binary BCH code with the following fixed configuration,
- BCH(63,36,t=5)
- Code length: 63 bits
- Message length: 36 bits
- Maximum designed correction capability: 5 bit errors
- Fixed PUF response indices: 0 through 62
- Response bit 63 is omitted only because the BCH code requires 63 input bits
Each reconstruction attempt uses exactly one noisy PUF response and one BCH decode.
The system does not use retries, majority voting, erasures, stable-bit selection, or adaptive bit selection.

### Credential Construction

Each enrolled message contains,
- 32-bit pilot credential
- 4 zero padding bits
- 36 total message bits
The 36-bit message is BCH encoded during enrollment. Public helper data are then created by XORing the encoded message with the selected 63 bits of the enrolled PUF response.
During reconstruction, the same selected response positions are XORed with the helper data and passed to the BCH decoder.
If decoding succeeds, the final four message bits must equal `0000`. The first 32 bits are then returned as the reconstructed credential.
Padding validation verifies the expected message format, but it does not independently prove that the reconstructed 32-bit credential is the originally enrolled credential.

### What Stayed the Same
The purpose of this experiment was to characterize the existing reconstruction baseline, not improve it.
The following remained unchanged,
- BCH parameters
- 63-bit response subset
- 32-bit credential format
- four padding bits
- helper-data construction
- one-reading/one-decode reconstruction
- credential-generation stream
- Layer 1 PUF simulation model
No voting, retries, alternate ECC, stable-bit selection, or other reconstruction improvement was added.

## Experiment Design

### Formal Cohort
The experiment uses 20 previously established simulation runs with six devices per run,
- Simulation runs: 20
- Devices per run: 6
- Total devices: 120
- Reads per device per condition: 100
The exact simulation seeds are:
`1111, 1122, 1234, 2121, 2222, 2391, 3232, 3333, 4321, 4433, 4444, 5426, 5555, 6543, 6666, 7654, 7777, 8231, 8888, 9999`
All selected devices use the same frozen Layer 1 configuration,
- 128 ring oscillators per device
- adjacent oscillator pairing
- 64-bit PUF responses
- manufacturing SD = 1.0
- nominal frequency = 100.0
- noiseless enrollment
- no aging drift
- zero environmental offset


### Nominal Population

The nominal measurement-noise standard deviation is 0.1.
Each of the 120 devices contributes 100 nominal readings,
`20 runs x 6 devices x 100 reads = 12,000 nominal attempts`

The nominal condition uses the same archived responses and deterministic credential streams as the earlier historical Layer 2 evaluation.
This makes the nominal experiment a formal reproducibility check and characterization of the existing cohort, not a new independent population.

### Noise Sweep

The formal noise sweep evaluates six measurement-noise standard deviations,
- 0.0
- 0.05
- 0.1
- 0.25
- 0.5
- 1.0
Each noise level contains 12,000 reconstruction attempts.
Therefore,
- Nominal attempts: 12,000
- Sweep attempts: 72,000
- Total experimental attempts: 84,000
The sweep's SD 0.1 condition is separate from the primary nominal SD 0.1 condition. The same simulated devices are used, but later measurement-noise draws are generated, so the two populations are reported separately.

### Metrics

Each reconstruction attempt is classified into one of four outcomes,

**Correct reconstruction:**  
A valid-format credential is returned and exactly matches the enrolled credential.

**Decoder failure:**  
The BCH decoder reports the received value as uncorrectable and returns no candidate credential.

**Invalid format/padding:**  
The decoder returns a message, but the final four padding bits are not `0000`.

**Miscorrection:**  
The decoder returns a valid-format credential, but the 32-bit credential differs from the enrolled credential.

The reconstruction false-rejection rate (FRR) is defined as:

`FRR = (decoder failures + invalid-format outcomes + miscorrections) / total legitimate reconstruction attempts`

Additional measurements include,
- selected-bit BER across the 63 BCH input bits
- full-response BER across all 64 PUF bits
- actual selected-bit error count
- per-run and per-device reconstruction behavior
- reconstruction latency

### Statistical Method
Because each simulation run contains multiple devices and repeated readings, individual reconstruction attempts are not treated as independent device samples.
Uncertainty is estimated using a cluster bootstrap over the 20 complete simulation runs.
For each condition,
- 20 whole simulation-run clusters are sampled with replacement
- all six devices and their 100 readings remain together
- 10,000 bootstrap replicates are performed
- bootstrap seed = 20260929
- a 95% percentile interval is reported

### Timing Method
Latency measures only the execution of `reconstruct()`.
The timer includes,
- input and helper validation
- selected-bit extraction
- XOR/helper reconstruction
- BCH decoding
- decoder consistency checks
- padding validation
- credential extraction

It excludes,
- PUF simulation or acquisition
- enrollment
- error-count calculation
- evaluator comparison against the enrolled credential
- disk output
- summary generation
- bootstrap calculations
- plotting
- authentication/session establishment

A six-call synthetic warm-up was performed before experimental timing so that one-time BCH initialization would not dominate the formal latency measurements.
No experimental readings were consumed during warm-up, and no latency outliers were removed.

## Preflight Verification

### Input Cohort Verification

Before formal execution, all 20 required Layer 1 simulation directories were verified.
Each directory contained the required completion and data files, and the selected cohort was checked for,
- correct simulation seed
- expected device count
- expected response length
- expected Layer 1 configuration
- correct device and reading identities
- correct saved Hamming distances and BER values
- compatibility with the frozen Week 2 PUF simulation model

The preflight verified,
- 120 enrolled reference responses
- 12,000 nominal saved readings
- 72,000 saved sweep readings
- all 180 required input files across the selected 20 runs

### Source and Configuration Hashes

The approved experiment configuration is:

`configs/reconstruction_experiment_v1.json`

Configuration SHA-256:

`07be1acd3c3980842a867de3fc08e32a79543c4262dd3a42832f4284a76525cb`

The complete 180-file input fingerprint is:

`e3332b944bfae4a8fcb9b04522277b13c9312608d36d1e35e7ccbcbb171a60fd`

The formal experiment was pinned to source checkpoint:

`40da3a388983030b7b696ce7bf2b801e0ed6903f`

These values establish the specific configuration, input cohort, and source state used by the formal experiment.

### Protected Reconstruction Files

The two core reconstruction files were verified before execution and remained unchanged.

`src/python/puf_snn/reconstruction/bch.py`

SHA-256:

`4b17daf39a97698a368d817a765c2bc8a7e5804468396573329428c01d3f44a6`

`src/python/puf_snn/reconstruction/credential.py`

SHA-256:

`14463ca853ac5a54f326d18537e5ae76008ffde7240433ad52afa8acf2ae08ef`

This confirms that the formal experiment measured the frozen baseline rather than a reconstruction algorithm modified immediately before execution.

### Preflight Test Results

Two existing test suites were run before the formal experiment.
Reconstruction tests,
- 50 tests passed
- 0 failures
- 0 errors
- 0 skips
- runtime: 18.171 seconds
Formal experiment tests,
- 22 tests passed
- 0 failures
- 0 errors
- 0 skips
- runtime: 9.026 seconds

Total,
**72/72 tests passed**

The tests covered reconstruction correctness, BCH behavior, experiment accounting, deterministic streams, warm-up exclusion, source-change detection, overwrite protection, retained failures, and experimental ordering.

### Execution Readiness

The preflight passed all required gates.
Expected experiment size was confirmed as,
- 12,000 nominal attempts
- 72,000 sweep attempts
- 84,000 total attempts

The intended formal output directory did not exist before execution, and the formal runner was configured to refuse existing output directories.
The experiment was therefore cleared for one formal execution using the approved configuration and fixed evidence cohort.

## Formal Experiment Execution

### Command
The formal Layer 2 runner was executed once using the approved configuration, archived Layer 1 inputs, and a new output directory.
The experiment completed normally with exit code 0.
Total process wall time was approximately,
**106.46 seconds**
This process time includes archive preparation and verification, warm-up, reconstruction attempts, summary generation, and final evidence writes. It is separate from the per-attempt reconstruction latency reported later.

### Output Directory

The completed formal evidence is stored at:

`results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/`

The independent audit is stored at:

`results/week-5/will/reconstruction/layer2-experiment-v1-formal-001-audit.json`

### Attempt Counts

The completed experiment contains exactly,
- 12,000 nominal attempts
- 12,000 attempts at SD 0.0
- 12,000 attempts at SD 0.05
- 12,000 attempts at SD 0.1
- 12,000 attempts at SD 0.25
- 12,000 attempts at SD 0.5
- 12,000 attempts at SD 1.0

Total:

**84,000 reconstruction attempts**

### Evidence and Completion

The formal process completed successfully with:
- exit code 0
- valid `manifest.json`
- valid `COMPLETE`
- no `INCOMPLETE.json`
- all expected experiment artifacts present
- stable reconstruction source hashes
- successful independent reconciliation


## Nominal Reconstruction Results

### Success and FRR

The nominal population contained 12,000 reconstruction attempts.
Results,
- Correct reconstructions: 11,805
- Failed reconstructions: 195
- Reconstruction success rate: 98.375%
- Reconstruction FRR: 1.625%

The nominal condition therefore successfully reconstructed the enrolled credential in approximately 98.4% of the observed attempts.

### Failure Breakdown

The 195 nominal failures consisted of,
- Decoder failures: 186
- Invalid-format/padding outcomes: 7
- Valid-format wrong credentials: 2
Rates across all 12,000 nominal attempts,
- Decoder failure rate: 1.550000%
- Invalid-format rate: 0.058333%
- Miscorrection rate: 0.016667%

Decoder-declared failures therefore accounted for most observed nominal reconstruction failures.
The two valid-format wrong credentials are important because they demonstrate that successful BCH decoding and valid padding do not necessarily guarantee reconstruction of the originally enrolled credential.

### BER

Nominal selected-bit BER across the 63 bits used by BCH was,
**3.197090%**

The raw selected-bit error count was:

`24,170 / 756,000`

Full 64-bit response BER was:

**3.207552%**

with:

`24,634 / 768,000`

The close agreement between BER63 and BER64 indicates that omission of response bit 63 did not materially change the measured nominal error level in this cohort.

### Bootstrap Confidence Interval

The observed nominal FRR was,
**1.625%**

The 95% run-cluster bootstrap interval was,
**1.241667% to 2.016667%**

The corresponding reconstruction-success interval was,
**97.983333% to 98.758333%**

The interval reflects uncertainty across the 20 simulated run clusters. It does not create additional independent devices or establish the FRR of physical hardware.

### Reconstruction Latency

Nominal warmed `reconstruct()` latency was:
- Mean: 1.170002 ms
- Median: 1.037800 ms
- p95: 2.262365 ms
- Maximum: 16.622600 ms
- Observations: 12,000

All completed outcomes were retained in the timing population, including failures.
The maximum observation was retained rather than removed as an outlier.
These values measure reconstruction software only and are not acquisition-to-authentication or end-to-end system latency.

## Noise Sweep Results

The noise sweep demonstrates how the frozen reconstruction baseline behaves as simulated measurement noise and measured BER increase.
Each noise condition contains 12,000 attempts.

### SD 0.0

At zero measurement noise,
- Mean BER63: 0.000000%
- Correct reconstructions: 12,000
- Success rate: 100.000000%
- FRR: 0.000000%
- Decoder failures: 0
- Invalid-format outcomes: 0
- Miscorrections: 0
- Median latency: 0.145000 ms
- p95 latency: 0.251000 ms

No reconstruction failures were observed in this condition.

### SD 0.05

At measurement-noise SD 0.05,
- Mean BER63: 1.605026%
- Correct reconstructions: 11,997
- Success rate: 99.975000%
- FRR: 0.025000%
- Decoder failures: 3
- Invalid-format outcomes: 0
- Miscorrections: 0
- Median latency: 0.894500 ms
- p95 latency: 1.949805 ms

This is the first tested sweep condition with a nonzero reconstruction failure rate.

### SD 0.1

At measurement-noise SD 0.1,
- Mean BER63: 3.171693%
- Correct reconstructions: 11,815
- Success rate: 98.458333%
- FRR: 1.541667%
- Decoder failures: 175
- Invalid-format outcomes: 5
- Miscorrections: 5
- Median latency: 1.005450 ms
- p95 latency: 2.130135 ms

This is the first sweep condition in which valid-format wrong credentials were observed.
This population is separate from the primary nominal SD 0.1 population because it uses later measurement RNG draws on the same simulated devices.

### SD 0.25

At measurement-noise SD 0.25,
- Mean BER63: 7.814815%
- Correct reconstructions: 7,610
- Success rate: 63.416667%
- FRR: 36.583333%
- Decoder failures: 4,208
- Invalid-format outcomes: 113
- Miscorrections: 69
- Median latency: 1.042650 ms
- p95 latency: 2.070430 ms

At this noise level, reconstruction reliability begins to degrade substantially. Decoder failures remain the dominant failure mode.

### SD 0.5

At measurement-noise SD 0.5,
- Mean BER63: 14.862566%
- Correct reconstructions: 912
- Success rate: 7.600000%
- FRR: 92.400000%
- Decoder failures: 10,552
- Invalid-format outcomes: 342
- Miscorrections: 194
- Median latency: 0.976800 ms
- p95 latency: 1.985400 ms

This condition produced the largest number and rate of valid-format miscorrections in the tested sweep.

### SD 1.0

At measurement-noise SD 1.0,
- Mean BER63: 25.158201%
- Correct reconstructions: 3
- Success rate: 0.025000%
- FRR: 99.975000%
- Decoder failures: 11,323
- Invalid-format outcomes: 514
- Miscorrections: 160
- Median latency: 0.980500 ms
- p95 latency: 1.936945 ms

At the highest tested noise level, reconstruction was effectively unusable, with nearly all attempts failing.
The number of miscorrections decreased relative to SD 0.5 even though total FRR increased. This occurs because severe noise increasingly produces outright decoder or format failures rather than valid-format wrong candidates.

## Miscorrection Analysis

### Total Miscorrections

Across the complete 84,000-attempt experiment, **430 valid-format wrong credentials** were observed.
These were distributed as,
- Nominal SD 0.1: 2
- Sweep SD 0.0: 0
- Sweep SD 0.05: 0
- Sweep SD 0.1: 5
- Sweep SD 0.25: 69
- Sweep SD 0.5: 194
- Sweep SD 1.0: 160

Of the 430 total miscorrections,
- 2 occurred in the nominal condition
- 428 occurred across the six noise-sweep conditions

Because these conditions intentionally use different noise levels, the 430 records should not be interpreted as one pooled operational miscorrection probability.

### Nominal Miscorrections

The two nominal valid-format wrong credentials occurred at,
**Case 1**
- Simulation seed: 2222
- Device: device-3
- Attempt: 88
- Actual selected-bit errors: 6
**Case 2**
- Simulation seed: 6543
- Device: device-1
- Attempt: 75
- Actual selected-bit errors: 7

Both occur beyond the BCH design correction radius of five selected-bit errors.
These cases demonstrate why valid padding alone cannot be treated as proof that the reconstructed credential is authentic.

### BCH Correction-Radius Behavior

Across all 84,000 attempts,
**56,142 attempts contained five or fewer actual selected-bit errors.**

Every one of those attempts reconstructed successfully.
Observed in-radius result,
**56,142 / 56,142 successful**

There were zero unexpected reconstruction failures within the BCH design correction radius.

The remaining,
**27,858 attempts**
contained more than five selected-bit errors.

All of those attempts failed to reconstruct the correct credential in this dataset through one of the following outcomes,
- decoder failure
- invalid format/padding
- valid-format wrong credential

This strongly demonstrates the expected correction-radius behavior of the frozen baseline in the observed population.
It should not be interpreted as a mathematical claim that every possible error pattern above five errors must always fail. BCH guarantees correction up to its designed radius; behavior beyond that radius depends on the received error pattern.

## Evidence Reconciliation

### Independent Audit

After formal execution, an independent reconstruction-evidence auditor was run against the completed directory.

The audit returned:
**PASS**
It independently confirmed,
- 84,000 total attempts
- 84,000 unique archived-response matches
- 120 enrollments
- 12,000 nominal attempts
- six sweep populations of 12,000 attempts
- 72,000 total sweep attempts
- 1,087 independently reconciled summary groups
- no backend exceptions
- no failures with five or fewer selected-bit errors
- correct separation of decoder, invalid-format, miscorrection, and successful outcomes

The audit did not rerun reconstruction. It independently checked the saved experiment records and summaries.

### Manifest and COMPLETE

The formal evidence directory contains both `manifest.json` and `COMPLETE`.

No `INCOMPLETE.json` exists.

All manifest-listed artifacts passed integrity verification.

Manifest SHA-256:

`082db862432da3d1b523f247035d2ae5d27be3a387317792f6eda8e72960a71b`

Independent audit SHA-256:

`02f30f9fe9d4eca10e2691b769441fb39b4752e94f74ea993f8e999567f784ca`

`COMPLETE` was written only after the runner completed its attempt accounting, summary generation, source-stability checks, and manifest generation.

### Historical Baseline Comparison

The formal nominal evaluation exactly reproduced the outcome counts from the previous historical Layer 2 evaluation.

| Outcome | Historical | Formal |
|---|---:|---:|
| Attempts | 12,000 | 12,000 |
| Correct credentials | 11,805 | 11,805 |
| Total failures | 195 | 195 |
| Decoder failures | 186 | 186 |
| Invalid format/padding | 7 | 7 |
| Valid-format wrong credentials | 2 | 2 |
| FRR | 1.625% | 1.625% |

This exact agreement is expected because the formal experiment intentionally re-evaluates the same archived nominal responses using the same deterministic credential streams.
It demonstrates reproducibility of the existing result, not independent replication.
Historical and formal latency values are not directly comparable because the earlier evaluation included first-decode initialization while the formal experiment performed warm-up before timed observations.

---

## Interpretation

The formal experiment establishes a reproducible performance baseline for the current single-read BCH reconstruction design.
Under the nominal simulated-noise condition, the system reconstructs the enrolled credential correctly in **98.375%** of attempts, with an observed reconstruction FRR of **1.625%**.
The noise sweep shows a clear relationship between increasing measured BER and declining reconstruction reliability. At very low BER the baseline performs almost perfectly, while higher noise rapidly pushes the error count beyond the BCH correction radius and causes reconstruction failure.
Most failures are explicit decoder failures. However, the experiment also identified **430 valid-format miscorrections**, demonstrating an important limitation of relying only on BCH success and padding validation.
A decoded message can have the expected format while still containing the wrong credential.
The experiment also shows that all observed responses within the BCH correction radius were reconstructed correctly. Failures and miscorrections appeared only once the selected-bit error count exceeded five.
These findings support using the frozen reconstruction implementation as a measured baseline for the software pilot while clearly identifying the need to distinguish successful decoding from credential authenticity.


## Limitations
- This experiment uses a simulated ring-oscillator PUF rather than measurements from physical PUF hardware
- No FPGA, Quest, or other physical device participated in the formal evaluation
- Enrollment is idealized and noiseless
- The PUF model uses synthetic Gaussian manufacturing and measurement noise
- Aging is disabled and environmental offsets are zero
- The formal population contains 20 simulation-run clusters and 120 simulated devices, not an independent physical-device population
- Repeated reads from the same devices and different noise conditions are dependent observations
- The nominal condition reuses the historical device cohort and credential streams and is therefore not independent replication
- The credential is a deterministic 32-bit proof-of-mechanism value rather than production-strength secret material
- The baseline performs only one reconstruction attempt per reading and does not use voting, retries, erasures, stable-bit selection, or alternative ECC
- Valid-format miscorrections can occur beyond the BCH correction radius
- This Layer 2 experiment measures reconstruction behavior only. It does not treat padding as independent credential authentication
- Reconstruction FRR and miscorrection rates are not the same as Layer 3 authentication false-reject or false-accept rates
- Timing measures warmed Windows/Python reconstruction software only and excludes PUF acquisition and full authentication/inference processing
- The accepted seven-field experiment configuration relies on source code, fixed archive identities, and recorded provenance for part of the complete experiment definition
- The manifest provides evidence integrity and accounting but is not a cryptographic signature or independent third-party attestation
- No reconstruction alternative or optimization was compared in this experiment

## Reproducibility

### Config

Approved experiment configuration:
`configs/reconstruction_experiment_v1.json`

Formal source checkpoint:
`40da3a388983030b7b696ce7bf2b801e0ed6903f`

Configuration SHA-256:
`07be1acd3c3980842a867de3fc08e32a79543c4262dd3a42832f4284a76525cb`

Input-cohort fingerprint:
`e3332b944bfae4a8fcb9b04522277b13c9312608d36d1e35e7ccbcbb171a60fd`

### Commands

The completed formal experiment was produced by the repository's formal reconstruction runner using the approved configuration, archived Layer 1 inputs, and a new Week 5 evidence directory.
For provenance, the formal execution command was,
`.\.venv\Scripts\python.exe -B src/python/scripts/run_reconstruction.py --config configs/reconstruction_experiment_v1.json --archive sim_results --output results/week-5/will/reconstruction/layer2-experiment-v1-formal-001`

The completed output directory should not be reused or overwritten by a later experiment. Any future execution should use a new versioned output directory.

### Evidence Paths

Formal experiment:

`results/week-5/will/reconstruction/layer2-experiment-v1-formal-001/`

Independent audit:

`results/week-5/will/reconstruction/layer2-experiment-v1-formal-001-audit.json`

Important evidence inside the formal directory:

- `attempts.jsonl` — all 84,000 reconstruction observations
- `enrollments.json` — 120 synthetic enrollment records
- `baseline_summary.csv` — nominal reconstruction summary
- `noise_sweep_summary.csv` — six noise-sweep summaries
- `per_run_summary.csv` — per-simulation-run results
- `per_device_summary.csv` — per-device results
- `error_count_summary.csv` — outcomes by selected-bit error count
- `latency_summary.csv` — reconstruction timing summaries
- `summary.json` — complete condition and bootstrap summary
- `metadata.json` — environment and source provenance
- `warm_up.json` — excluded warm-up behavior
- `manifest.json` — evidence-file integrity hashes
- `COMPLETE` — successful experiment completion marker