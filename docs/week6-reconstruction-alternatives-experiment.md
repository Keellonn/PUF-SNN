# Reconstruction Alternatives Experiment

**Owner:** Will Wallace  
**Week:** 6  
**Status:** Complete

**Version:** week6-reconstruction-alternatives-v1  
**Formal Experiment:** week6-reconstruction-alternatives-v1-formal-001

## Research Objective

The objective of this experiment was to investigate alternative reconstruction methods capable of improving the reliability of our simulated Physical Unclonable Function (PUF) credential reconstruction pipeline.

Our existing reconstruction implementation uses BCH(63,36,t=5) error correction with a single noisy PUF reading. A previous Week 5 formal experiment measured a nominal False Rejection Rate (FRR) of 1.625%, exceeding our research target of 0.5%.

To address this reliability limitation, we selected two reconstruction-improvement techniques:

1. Temporal majority voting to reduce bit errors before BCH decoding.
2. Stronger BCH error correction to increase the number of correctable bit errors.

The research objective was to determine whether either approach could reduce nominal reconstruction FRR to 0.5% or below while evaluating the resulting latency and credential-security tradeoffs.

A fresh baseline was included to ensure that alternatives were compared under matched experimental conditions rather than relying on unmatched historical measurements.

## Reconstruction Alternatives

### Existing Baseline — BCH(63,36,t=5)

The baseline reconstruction implementation uses a simulated ring-oscillator PUF containing 128 oscillators arranged into 64 disjoint adjacent pairs.
Each oscillator pair generates one response bit through a simulated frequency comparison. The first 63 response bits are used for BCH reconstruction.

The baseline configuration consists of,
- 128 simulated ring oscillators
- 64 generated response bits, with 63 selected
- BCH(63,36,t=5) error correction
- Designed minimum distance of 11
- A 32-bit credential with four zero-padding bits
- One noisy PUF reading per reconstruction attempt
- Independent credential verification

During enrollment, the padded credential is BCH-encoded into a 63-bit codeword. Public helper data are created by XORing the codeword with the reference PUF response.
During reconstruction, the noisy response is XORed with the helper data and decoded to recover a credential candidate.
The decoder can correct up to five bit errors. Larger error patterns may result in decoder failure, invalid padding, or an incorrect credential candidate.
Our historical nominal reconstruction experiment produced an FRR of 1.625%, motivating the investigation of alternative reconstruction techniques.

### Alternative A — Temporal Majority Voting

Temporal majority voting reduces transient measurement errors by combining multiple noisy readings from the same simulated PUF device before reconstruction.
Rather than supplying an individual noisy response directly to BCH decoding, the system collects multiple readings and determines the majority value at each response-bit position.
Two configurations were evaluated,
- A1: Three-read majority voting
- A2: Five-read majority voting

The voted response is then supplied to the existing BCH(63,36,t=5) reconstruction implementation.
For an odd number of readings, the majority decision is:

\[
r_j^{vote} =
\begin{cases}
1, & \sum_{i=1}^{m} r_{i,j} \geq (m+1)/2 \\
0, & \text{otherwise}
\end{cases}
\]

Where,
- m represents the number of readings
- r represents an individual measured response bit
- j represents the response-bit position

The primary advantage is improved resistance to independent transient measurement noise without modifying the existing BCH implementation or credential format.
The primary disadvantage is additional measurement overhead. Majority voting also cannot reliably correct systematic errors shared across repeated measurements.
Both voting configurations retain the original 32-bit credential, 63-bit BCH codeword, and independent credential verifier.

### Alternative B — Stronger BCH(63,30,t=6)

The second alternative increases BCH error-correction capability while preserving the 63-bit codeword length and single-read policy.
The experimental configuration uses,
- BCH(63,30,t=6)
- Designed minimum distance of 13
- Six correctable bit errors
- One noisy PUF reading
- A 30-bit experimental credential
- Independent credential verification

The BCH configuration was verified using galois 0.4.11. Its generator polynomial is identified by:

`0x37CD0EB67`

Because BCH(63,30) supports only 30 information bits, the original unrestricted 32-bit credential cannot fit within the new code.
The experimental credential therefore contains 30 variable bits represented in four big-endian bytes, with the two highest representation bits fixed to zero.
All 30 BCH information bits carry credential information.
This approach improves correction capability without requiring additional PUF readings. However, it reduces the nominal credential search space from 2^32 to 2^30 possibilities, a fourfold reduction.
The stronger BCH implementation was isolated from the production reconstruction system and did not modify Authentication-v2.

## Experimental Design

### Experimental Configurations

Four reconstruction configurations were evaluated.
| Group | Reconstruction Method | PUF Reads | Correctable Errors | Credential Bits |
|---|---|---:|---:|---:|
| B0 | BCH(63,36,t=5) | 1 | 5 | 32 |
| A1 | Majority-3 + BCH(63,36,t=5) | 3 | 5 | 32 |
| A2 | Majority-5 + BCH(63,36,t=5) | 5 | 5 | 32 |
| B1 | BCH(63,30,t=6) | 1 | 6 | 30 |

B0, A1, and A2 use the same enrollment credentials and helper data for each device.
B1 uses separately enrolled 30-bit credentials and corresponding helper data.
This allows A1 and A2 to isolate the effects of repeated measurement, while B1 evaluates the joint tradeoff between stronger error correction and reduced credential length.

### Device Population and Trial Allocation

The experiment evaluated 120 independently manufactured simulated PUF devices distributed across 20 seeded populations.
Experimental population,
- 20 simulated populations
- Six devices per population
- 120 total devices
- One enrollment generation per code/device
- 50 reconstruction attempts per device, configuration, and noise condition
- 6,000 attempts per experimental group/condition
- 48,000 total reconstruction attempts

The experiment required,
- 240 enrollment/helper records
- 120,000 timed PUF reading calls
- 60,000 unique matched measurement identities
- Eight experimental cells

Each experimental group was assigned equally across execution-order positions to reduce systematic timing-order effects.

### Noise Conditions and Experimental Controls

Two controlled measurement-noise conditions were evaluated,
| Condition | Measurement Noise SD | Purpose |
|---|---:|---|
| Nominal | 0.10 | Evaluate reconstruction under nominal simulated measurement noise |
| Stress | 0.25 | Evaluate reconstruction under increased measurement noise |

The PUF simulator used the following fixed conditions,
- 128 ring oscillators
- Nominal oscillator frequency of 100
- Manufacturing variation SD of 1.0
- Zero environmental offset
- No aging variation
- Noiseless reference enrollment

Manufacturing variation was generated once for each device and retained throughout evaluation.
Repeated authentication readings used independent measurement-noise streams while preserving the underlying device manufacturing characteristics.
The experiment used deterministic SHA-256-derived random seeds to reproduce simulated devices, enrollment credentials, measurement streams, and trial order.
The same underlying first-read measurement identities were reused across matched configurations, although responses were regenerated inside each timed execution path.
Enrollment and evaluation streams were separated.
No adaptive parameter tuning, outcome-dependent retries, or favorable-device exclusion was permitted.

### Evaluation Metrics

The experiment recorded reconstruction reliability, bit-error behavior, credential verification, latency, and uncertainty.
Four mutually exclusive reconstruction outcomes were defined,
- C: Correct credential reconstruction
- D: Decoder failure
- I: Invalid credential format or padding
- W: Valid-format incorrect credential

The reconstruction False Rejection Rate was calculated as,

\[
FRR = \frac{D + I + W}{N}
\]

Where N is the total number of reconstruction attempts.

Additional reliability measurements included,
- Raw selected-bit BER
- Effective decoder-input BER
- Correct reconstruction count
- Decoder failure count
- Invalid-format count
- Wrong-credential count
- Independent-verifier acceptance and rejection
- Legitimate credential-admission failure rate

Latency was measured across,
- PUF response generation
- Majority voting, where applicable
- BCH reconstruction
- Independent credential verification
- Total measured software reconstruction path

Latency distributions were reported using p50, p95, p99, and maximum measurements.
Statistical uncertainty was evaluated using two-sided 95% Clopper-Pearson intervals and population-cluster bootstrap intervals.

## Implementation and Validation

### Implementation Architecture

The alternatives were implemented as isolated experimental functionality rather than modifications to the existing production reconstruction system.
Primary implementation files,
- `src/python/puf_snn/reconstruction_alternatives.py`
- `src/python/scripts/run_reconstruction_alternatives.py`
- `configs/reconstruction_alternatives_v1.json`
- `schemas/reconstruction-alternatives-attempt-v1.schema.json`

The experimental module implements majority-vote preprocessing and a separate BCH(63,30,t=6) encoder/decoder adapter.
B0, A1, and A2 reuse the existing production BCH reconstruction API.
B1 uses its own experimental credential format, BCH configuration, and helper-data representation.
The experiment runner handles deterministic device generation, enrollment, reconstruction attempts, verifier calls, latency measurement, statistical analysis, and evidence reconciliation.
No changes were made to the production PUF reconstruction implementation, Authentication-v2 protocol, or Tier-1 evaluation system.

### Algorithm Verification and Automated Testing

BCH(63,30,t=6) correctness was verified through independent polynomial arithmetic and deterministic decoding fixtures.
The verification included,
- Generator-polynomial construction.
- Independent polynomial-division checks.
- All 30 message-basis vectors.
- Deterministic six-error correction fixtures.
- Beyond-radius decoding behavior.
- Credential bit ordering and byte representation.
- Wrong-credential identification.

Majority voting was tested against deterministic truth tables for three and five readings.
Additional tests verified independent noise streams, exact read counts, matched trial schedules, credential-verifier behavior, schema restrictions, source-integrity checks, and evidence accounting.
Stage 2 validation completed 194 automated tests.
After enabling and reviewing the formal execution pathway, Stage 3A validation completed:

**221 automated tests passed with zero unexpected failures or errors.**

Formal dry-preflight verified the complete trial schedule without executing reconstruction attempts.

### Informal Validation and Reproducibility

Before formal execution, a separate NONFORMAL smoke test evaluated the functioning of the experimental reconstruction pipeline.
The smoke test contained,
- Two simulated devices
- Two noise conditions
- Four reconstruction configurations
- Five attempts per device/configuration/condition
- 80 measured reconstruction attempts

Observed smoke outcomes,
- 71 correct reconstructions
- Nine decoder failures
- Zero invalid-format outcomes
- Zero wrong credentials
- 71 independent-verifier calls
- 200 measured PUF reading calls

All 80 attempts passed evidence reconciliation.
The smoke results were used exclusively for functional validation and were not included in the formal research statistics.
Formal readiness also verified source snapshots, fixed experiment digests, schema validation, exact trial populations, and evidence-completion safeguards.
The formal experiment subsequently completed all 48,000 attempts and passed independent post-run evidence verification.

## Experimental Results

### Reconstruction Reliability and FRR

The formal experiment completed 48,000 reconstruction attempts across eight experimental cells.
Each cell contained exactly 6,000 attempts.
| Condition | Group | Correct | Decoder Failures | Invalid Format | Wrong Credential | FRR |
|---|---|---:|---:|---:|---:|---:|
| Nominal | B0 | 5,941 | 59 | 0 | 0 | 0.9833% |
| Nominal | A1 | 5,994 | 6 | 0 | 0 | 0.1000% |
| Nominal | A2 | 6,000 | 0 | 0 | 0 | 0.0000% |
| Nominal | B1 | 5,985 | 15 | 0 | 0 | 0.2500% |
| Stress | B0 | 3,867 | 2,035 | 56 | 42 | 35.5500% |
| Stress | A1 | 5,421 | 563 | 11 | 5 | 9.6500% |
| Stress | A2 | 5,750 | 241 | 5 | 4 | 4.1667% |
| Stress | B1 | 4,777 | 1,214 | 0 | 9 | 20.3833% |

Under nominal conditions, the baseline reconstruction FRR was 0.9833%, exceeding the 0.5% research target.
All three alternatives achieved observed nominal FRR values below 0.5%.
Majority-3 reduced nominal FRR to 0.1000%, while majority-5 recorded zero failures across its 6,000 nominal attempts.
Stronger BCH achieved an FRR of 0.2500% with one reading.
Under increased measurement noise, all alternatives improved reliability relative to B0, but none achieved the 0.5% target.
The results indicate that both repeated measurement and increased correction capability improve simulated reconstruction reliability, with majority voting providing the largest observed reductions.

### Bit Error Rate

The experiment separately measured raw response-bit errors and effective errors entering BCH decoding,
| Condition | Group | Raw BER | Effective BER |
|---|---|---:|---:|
| Nominal | B0 | 3.0796% | 3.0796% |
| Nominal | A1 | 3.0829% | 2.0881% |
| Nominal | A2 | 3.0798% | 1.6511% |
| Nominal | B1 | 3.0796% | 3.0796% |
| Stress | B0 | 7.6712% | 7.6712% |
| Stress | A1 | 7.7039% | 5.1558% |
| Stress | A2 | 7.7092% | 4.1220% |
| Stress | B1 | 7.6712% | 7.6712% |

The first-read BER was identical across matched experimental configurations.
Under nominal conditions, majority-3 reduced effective BER to approximately 2.09%, while majority-5 reduced it to approximately 1.65%.
Under stress conditions, majority-3 reduced effective BER to approximately 5.16%, while majority-5 reduced it to approximately 4.12%.
These results demonstrate that temporal voting reduces the number of bit errors presented to the BCH decoder.
In comparison, stronger BCH does not reduce the raw or effective BER. Its reliability improvement comes from correcting a larger number of errors.

### Reconstruction Latency

Latency was measured for the complete local software path, including PUF response generation, optional voting, BCH reconstruction, and independent verification.
All measurements are in milliseconds.

| Condition | Group | p50 | p95 | p99 | Maximum |
|---|---|---:|---:|---:|---:|
| Nominal | B0 | 1.1312 | 2.3022 | 2.9581 | 11.0220 |
| Nominal | A1 | 1.4547 | 2.6012 | 3.2713 | 6.5707 |
| Nominal | A2 | 1.7722 | 2.9034 | 3.5038 | 8.0607 |
| Nominal | B1 | 1.1333 | 2.3129 | 2.9661 | 7.4807 |
| Stress | B0 | 1.1675 | 2.3140 | 3.0230 | 15.4312 |
| Stress | A1 | 1.5267 | 2.7354 | 3.3672 | 10.7362 |
| Stress | A2 | 1.8515 | 3.0553 | 3.6549 | 21.3014 |
| Stress | B1 | 1.1884 | 2.4082 | 3.0660 | 5.3553 |

Under nominal conditions, majority-3 increased median latency by approximately 28.6% relative to B0.
Majority-5 increased median latency by approximately 56.7%.
The additional latency resulted from generating and processing multiple PUF readings.
Stronger BCH had a nominal median latency of approximately 1.1333 ms, compared with 1.1312 ms for B0. This represents an observed difference of approximately 0.2%, although it does not establish general performance equivalence.

The maximum retained latency was 21.3014 ms, observed under stress conditions for majority-5.
The largest latency outlier was dominated by reconstruction processing rather than PUF reading or voting. The available timing data could not definitively identify its cause.
No timing observations were removed, trimmed, or retried.
The measured latencies represent execution of the software simulator and BCH implementation, not physical PUF hardware acquisition latency.

### Confidence Intervals and Device Variation

Two-sided 95% Clopper-Pearson intervals were calculated for reconstruction FRR.

Population-cluster bootstrap intervals were also calculated using 10,000 resamples of the 20 complete device populations.

| Condition | Group | FRR | 95% Clopper-Pearson Interval | Population Bootstrap Interval |
|---|---|---:|---|---|
| Nominal | B0 | 0.9833% | 0.7494–1.2666% | 0.4833–1.6167% |
| Nominal | A1 | 0.1000% | 0.0367–0.2175% | 0.0167–0.2167% |
| Nominal | A2 | 0.0000% | 0.0000–0.0615% | 0.0000–0.0000% |
| Nominal | B1 | 0.2500% | 0.1400–0.4120% | 0.0667–0.5000% |
| Stress | B0 | 35.5500% | 34.3378–36.7763% | 33.0500–38.0333% |
| Stress | A1 | 9.6500% | 8.9143–10.4252% | 8.0996–11.3667% |
| Stress | A2 | 4.1667% | 3.6751–4.7034% | 3.1667–5.3167% |
| Stress | B1 | 20.3833% | 19.3703–21.4253% | 18.0833–22.6833% |

All alternatives achieved observed nominal FRR values below the 0.5% target, with descriptive Clopper-Pearson upper bounds also below 0.5%.
However, population dependence must be considered when interpreting these intervals.
B1 reached 0.5000% at the upper endpoint of its population-bootstrap interval.
Majority-5 produced no observed nominal failures, resulting in a degenerate zero-failure population-bootstrap interval. This does not demonstrate that its true failure probability is zero.
Device-specific variation was also significant.
The worst-performing simulated device experienced,
- 26% nominal FRR under B0
- 6% nominal FRR under A1
- 12% nominal FRR under B1

Under stress conditions, that same device experienced,
- 94% FRR under B0
- 70% FRR under A1
- 52% FRR under A2
- 84% FRR under B1

These results indicate that favorable population averages do not guarantee acceptable reliability for every individual device.

### Independent Credential Verification

Independent credential verification was retained across all four configurations.
The verifier was invoked only when reconstruction produced a credential candidate.
Attempts producing decoder failures or invalid-format outcomes did not invoke credential verification.

Across all experimental conditions,
- 43,735 correct credential candidates were accepted.
- 60 incorrect credential candidates were rejected.
- 4,205 attempts skipped verification because reconstruction did not produce an admissible candidate.
- Zero correct credentials were incorrectly rejected.
- Zero incorrect credentials were accepted.

All 60 wrong credentials occurred under the stress noise condition.
The observed wrong-candidate rejection rate was 60/60, with a descriptive two-sided 95% Clopper-Pearson interval of approximately 94.04–100%.
Although the verifier successfully rejected all observed incorrect candidates, these rejected credentials still represent reconstruction failures.
This distinction is important because independent verification protects credential admission but does not recover the correct credential or improve reconstruction availability.

## Reliability–Latency–Security Tradeoffs

### Majority Voting Tradeoffs

Temporal majority voting produced the greatest observed reconstruction-reliability improvements.

Under nominal conditions,
- B0 FRR: 0.9833%.
- A1 FRR: 0.1000%.
- A2 FRR: 0.0000% observed.

Majority-3 achieved approximately an 89.8% relative reduction in nominal FRR compared with B0.
Majority-5 eliminated observed nominal failures in the evaluated cohort, although this does not establish zero future failure risk.
The improvement required additional PUF readings.
Majority-3 increased nominal median latency by approximately 28.6%, while majority-5 increased it by approximately 56.7%.
Both methods retained the baseline 32-bit credential format and BCH correction capability.
The primary tradeoff is therefore improved reliability at the cost of additional reading and processing time.
The results also demonstrate sensitivity to measurement noise. Neither voting configuration achieved the 0.5% FRR target under the stress condition.

### Stronger BCH Tradeoffs

Stronger BCH improved nominal FRR from 0.9833% to 0.2500%, representing approximately a 74.6% relative reduction.
It achieved this improvement without additional PUF readings and with little observed difference in median software latency.
However, the stronger code reduced the credential format from 32 variable bits to 30 variable bits.
This reduces the nominal exhaustive-search space by a factor of four.
The experimental credentials are also generated from public deterministic seeds for reproducibility and therefore are not secret credentials suitable for production deployment.
BCH error correction and independent verification do not eliminate this underlying credential-entropy limitation.
The alternative demonstrates that stronger correction can improve reliability without substantial additional measured software latency, but it introduces an unfavorable security tradeoff for an already short credential format.

### Comparative Analysis

The experiment demonstrated that both approaches improve reconstruction reliability compared with the fresh baseline.
Majority-5 achieved the lowest observed failure rate across both noise conditions.
Majority-3 offered a smaller latency increase than majority-5 while still achieving the nominal 0.5% target.
Stronger BCH provided improved reliability with nearly unchanged observed nominal median latency, but required reducing the experimental credential length.
The paired nominal FRR differences relative to B0 were,
| Alternative | FRR Difference | Population Bootstrap Interval |
|---|---:|---|
| A1 | -0.8833 percentage points | -1.4500 to -0.4167 |
| A2 | -0.9833 percentage points | -1.6167 to -0.4833 |
| B1 | -0.7333 percentage points | -1.1333 to -0.4167 |

These comparisons support majority voting as the most promising approach for further research under the evaluated conditions.
However, no alternative was demonstrated to provide adequate reliability under all simulated devices and noise conditions.

## Experimental Limitations

The experiment was performed entirely within a software-based simulated PUF environment.
The PUF model generates response bits through simulated oscillator-frequency comparisons and does not incorporate measured physical PUF hardware behavior.
Major limitations include,
- No physical Quest 3 PUF or hardware oscillator measurements
- Noiseless enrollment reference responses
- Independent Gaussian measurement noise
- No experimentally calibrated temporal error correlation
- No differential environmental variation
- No modeled long-term aging or persistent drift
- No noisy re-enrollment evaluation
- No additional oscillator-pair selection strategies
- No experimental wrong-device false-acceptance study
- Limited population diversity from 120 simulated devices
- Repeated measurements from the same devices are statistically dependent

The experiment's latency measurements represent software execution time and cannot be treated as physical RO-PUF acquisition latency or end-to-end Authentication-v2 latency.
The 30-bit and 32-bit credential formats also do not provide production-strength security. Deterministically generated experimental credentials should not be interpreted as deployed secrets.
Finally, population-level success against the nominal 0.5% FRR target does not establish equivalent reliability for every device, under elevated noise, or in physical hardware.

## Conclusions and Recommendations

### Primary Findings

The formal experiment demonstrated substantial improvements in simulated PUF credential-reconstruction reliability through both majority voting and stronger BCH error correction.
Under nominal measurement noise, the fresh baseline produced an FRR of 0.9833%.
Majority-3 reduced FRR to 0.1000%, while majority-5 produced zero observed failures across 6,000 attempts.
Stronger BCH reduced FRR to 0.2500%.
All three alternatives achieved the observed nominal 0.5% FRR target.
However, elevated measurement noise produced considerably larger failure rates across every configuration.
The results also showed that independent verification successfully rejected all 60 observed wrong credential candidates without treating those rejections as successful reconstruction.

The experiment provides reproducible evidence of the reliability, latency, and credential-format tradeoffs associated with each alternative.

### Recommended Reconstruction Approach

Based on the measured results, majority-3 is the leading candidate for further investigation.
It reduced nominal FRR by approximately 89.8% relative to the fresh baseline while maintaining the original BCH(63,36,t=5) construction and 32-bit credential format.
Its measured median software latency increased by approximately 28.6%, which is lower than the additional overhead observed with majority-5.
Majority-5 demonstrated stronger observed reliability but required five readings per attempt.
Stronger BCH achieved improved reliability without a comparable latency penalty, but its reduction from 32 to 30 variable credential bits presents a less favorable security tradeoff.
Majority-3 therefore offers the most balanced observed reliability, latency, and credential-format characteristics among the evaluated alternatives.
This recommendation is for continued research only. No reconstruction alternative has been integrated into the production Authentication-v2 protocol.

### Future Research

Future experiments should investigate whether the observed improvements remain effective across more realistic PUF operating conditions.

Potential next steps include,
- Increasing the number of independent simulated device populations.
- Evaluating correlated measurement errors.
- Introducing noisy enrollment.
- Modeling environmental drift and oscillator aging.
- Investigating device-specific reliability variation.
- Evaluating majority voting with different hardware acquisition assumptions.
- Measuring reliability and latency using physical PUF data where available.
- Studying wrong-device false acceptance under alternative reconstruction policies.
- Evaluating integration of a selected alternative into Authentication-v2 as a separate versioned experiment.

Any future adoption should preserve the distinction between reconstruction reliability, credential entropy, and authentication security.

## Reproducibility and Evidence

### Experiment Configuration and Environment

**Experiment Version:** `week6-reconstruction-alternatives-v1`

**Formal Run ID:** `week6-reconstruction-alternatives-v1-formal-001`

**Repository Branch:** `main`

**Repository HEAD at execution:**

`acc46478dcde2ecffe706d8eab355b453b94fa30`

The formal run used a separate source snapshot because relevant research implementation files were uncommitted.

Experiment configuration:

`configs/reconstruction_alternatives_v1.json`

Approved experiment-plan SHA-256:

`0206983264278f1485b36bdbff29463afe2dc153aa003954506e68e75b9ced2d`

Frozen configuration SHA-256:

`3b7caa56bf296aaa02bca8fea69d545d6f1395c9811770c6e4d19ad8ea94c18b`

Trial-plan digest:

`d22e5eebe6ec55c9f890e02b4f010833e4f32ff9d64b5c777b22e9f794a26f10`

Execution environment:

- Windows 11 AMD64.
- Python 3.12.4.
- galois 0.4.11.
- NumPy 2.5.3.
- Numba 0.67.0.
- llvmlite 0.49.0.
- SciPy 1.18.1.
- jsonschema 4.26.0.
- GF2 execution mode: jit-calculate.
- Extension-field execution mode: jit-lookup.
- Numba thread count: 20.

Population seed range:

`2026100701` through `2026100720`

Execution-order seed:

`2026100791`

Bootstrap seed:

`2026100792`

Statistical uncertainty used two-sided 95% Clopper-Pearson intervals and 10,000 whole-population cluster bootstrap resamples.

### Source Code and Formal Results

Primary source implementation:

`src/python/puf_snn/reconstruction_alternatives.py`

Experiment runner:

`src/python/scripts/run_reconstruction_alternatives.py`

Configuration:

`configs/reconstruction_alternatives_v1.json`

Attempt schema:

`schemas/reconstruction-alternatives-attempt-v1.schema.json`

Relevant tests:

- `tests/reconstruction/test_reconstruction_alternatives.py`
- `tests/experiments/test_reconstruction_alternatives_experiment.py`
- `tests/experiments/test_reconstruction_alternatives_formal.py`

Formal evidence directory:

`results/week-6/will/reconstruction-alternatives/week6-reconstruction-alternatives-v1-formal-001/`

Formal execution command,
```powershell
$env:PYTHONPATH='src/python'
.venv/Scripts/python.exe -B src/python/scripts/run_reconstruction_alternatives.py formal --output results/week-6/will/reconstruction-alternatives/week6-reconstruction-alternatives-v1-formal-001