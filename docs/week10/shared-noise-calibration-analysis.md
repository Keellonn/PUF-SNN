# Shared-Noise Calibration: Reliability Comparison, Statistical Uncertainty, and Operating-Point Selection

**Owner:** Will Wallace
**Week:** 10
**Date:** November 5, 2026
**Status:** Complete

The numerical findings below were checked against saved attempts, device records, bootstrap estimates, and selection receipts. **Historical certification and present checkout integrity must be distinguished:** the saved receipts report PASS, but current byte-hash discrepancies prevent claiming a newly verified intact bundle. These discrepancies and the outstanding selection acknowledgment are documented under Evidence and Reproducibility.

## Interpretation of the 7.083-Percentage-Point Reliability Improvement

What precisely does the improvement measure, which acquisition policies are compared, and what observations support it?

### Acquisition procedures and controlled comparison

Single-Read (`single-read-v1`, S) acquires one 64-bit response from a persistent simulated device. Majority-3 (`majority-3-v1`, M) acquires three responses from that device and produces one effective response by bitwise voting:

\[
R^{M}_j=\mathbf{1}\{R_{j,0}+R_{j,1}+R_{j,2}\geq2\}.
\]

Each policy then performs exactly one reconstruction using the same BCH(63,36,t=5) mechanism, the first 63 response bits, public enrollment helper data, and a 32-bit credential with four fixed padding bits. Voting occurs before decoding; it is not three decoding attempts followed by credential selection. The frozen acquisition and reconstruction functions establish these operations [E4].

Policies are matched by device, condition, and trial index. Separate reader objects regenerate the same indexed reading-zero realization: S's response equals M's first response. M additionally acquires readings one and two. Thus the policies share the first noisy reading statistically, while actually performing their respective simulator calls; no cached response replaces acquisition. Inspection of all 1,920 saved pairs confirmed first-response and enrollment-hash agreement [E3].

Manufacturing offsets, noiseless enrollment, oscillator pairing, credential, reconstruction, independent-verifier policy, and protocol configuration are controlled. Endpoints and session state are fresh for each attempt; protocol entropy uses operating-system randomness rather than matched seeded nonces. The schedule balances policy order within each device-condition cell and shuffles complete matched blocks. The treatment difference is the additional two readings and vote, with their resource cost. Matching controls device difficulty and first-reading variation without implying independent arm samples [E1, E4].

### Reconstruction FRR and downstream outcomes

For policy \(p\), device \(d\), trial \(t\), and condition \(c\), define \(F_{pdtc}=1\) when reconstruction does not recover the correct enrolled credential, and zero otherwise. The implemented metric is

\[
\widehat{\mathrm{FRR}}_p(c)=\frac{D_p+I_p+W_p}{N_p}=1-\frac{C_p}{N_p}.
\]

The evaluator assigns mutually exclusive categories: C, correct credential; D, decoder failure; I, invalid format or padding; W, valid-format wrong credential. Truth classification is evaluator-only and grants no authentication authority. Raw bit errors are earlier diagnostics: BCH can correct some errors, and decoder status alone does not establish correct credential recovery. Invalid padding and valid-format miscorrection therefore cannot be collapsed into decoder failure [E1, E4].

Independent verification, local admission, active mutual session establishment, and authorized window release are successive, separately recorded outcomes. D/I ordinarily stop before verification; W can reach the verifier and be explicitly refused. A verifier that was never reached has not issued a refusal. At σ = 0.15, the saved rows establish:

| Policy |   C |  D | I | W | Actual verifier results                  | Active sessions / authorized releases |
| ------ | --: | -: | -: | -: | ---------------------------------------- | ------------------------------------- |
| S      | 431 | 48 | 1 | 0 | 431 verified; 49 not reached             | 431 / 431                             |
| M      | 465 | 13 | 1 | 1 | 465 verified; 1 mismatch; 14 not reached | 465 / 465                             |

Consequently, FRR is a **correct-credential reconstruction failure rate**, not an explicit-verifier-refusal rate. Here its failures coincide numerically with unsuccessful session/release attempts, but that agreement is an observed property of this dataset, not the metric's definition. Releases reach recording callbacks, not trained SNN inference [E3, E4].

### Verified numerical comparison

At each σ, four groups × six devices × 20 matched trials yield 480 pairs and **480 attempts per policy**, or 960 policy attempts. Across four σ settings, this gives 1,920 pairs and 3,840 policy attempts, not 3,840 independent devices or noise realizations [E2, E3].

| Policy      | Failed attempts | Total attempts | Reconstruction FRR |
| ----------- | --------------: | -------------: | -----------------: |
| Single-Read |              49 |            480 |            10.208% |
| Majority-3  |              15 |            480 |             3.125% |

\[
\begin{aligned}
100\widehat{\mathrm{FRR}}_S&=100(49/480)=10.208333\ldots\%,\\
100\widehat{\mathrm{FRR}}_M&=100(15/480)=3.125\%,\\
100\widehat\Delta&=100(49/480-15/480)=7.083333\ldots\ \text{percentage points},\\
\text{relative reduction}&=100\frac{49/480-15/480}{49/480}
=100(34/49)=69.387755\ldots\%.
\end{aligned}
\]

The absolute reduction subtracts rates on their percentage scale; the relative reduction divides that difference by S's observed failure rate. Thus 7.083 percentage points and approximately 69.4% describe different quantities. There are 40 beneficial pairs (S fails, M succeeds), six harmful pairs (S succeeds, M fails), nine concordant failures, and 425 concordant successes. The net improvement is \((40-6)/480\), not 40 rescues without counterexamples [E3, E5].

### Bounded scientific finding

Under the specified independent-read model (ρ = 0), Majority-3 reduced observed reconstruction FRR at σ = 0.15, at the cost of three readings instead of one and one additional vote. Both policies still perform one decode. Across the sweep, 7,680 acquisition readings, 3,840 runtime decodes, and 1,920 votes are recorded; replay operations add no samples [E2].

This is simulated reliability evidence conditional on noiseless enrollment and the chosen manufacturing/noise laws. σ is an abstract additive oscillator-frequency standard deviation, not a physical hardware measurement. Improved reconstruction does not demonstrate increased credential entropy or cryptographic attack resistance. Nor does ρ = 0 establish performance under correlated readings, physical aging, or environmental disturbances. The defensible finding is a reduction in **simulated correct-credential reconstruction failures for the specified comparison**, not universal PUF or security improvement.

## Statistical Resampling Unit and Uncertainty Estimation

What unit was resampled, why is it appropriate, and how should the uncertainty interval be interpreted?

### Experimental hierarchy and independence

The frozen generation path samples each device's 128 Gaussian manufacturing offsets once, with standard deviation one, using a device-specific stream. Each device retains its reference response, helper data, credential, and verifier enrollment across trials and σ settings. Manufacturing, reference, credential-generation, and measurement streams use distinct domains; measurement identities include device, condition, trial, and reading index [E1, E4].

| Level                 | Structure and dependence                                                                              |
| --------------------- | ----------------------------------------------------------------------------------------------------- |
| Reproducibility group | Four indexed groups, each containing six devices                                                      |
| Device                | Independent manufacturing stream under the intended simulation law; persistent margins and enrollment |
| Condition             | Four σ values on the same device; separate measurement domains                                       |
| Trial                 | Twenty per device-condition; new indexed measurement noise, shared device characteristics             |
| Policy pair           | Same device/trial/condition and reading zero; M adds two readings                                     |

At ρ = 0, reading disturbances are independent conditional on the device. Repeated failures can nevertheless be associated marginally because the same fragile oscillator margins recur. Enrollment is also shared. Resampling attempts independently would erase that heterogeneity and treat repeated measurements as additional devices.

The four groups are indexing batches, not sampled shared wafer effects. Inspection of `create_device`, `enrollment_material`, and noise seed derivation finds no random group mean, shared manufacturing shock, estimated group parameter, or cross-device measurement disturbance. The master root is shared numerically, but streams incorporate both population and device IDs. Device independence is therefore supported **under the intended indexed pseudorandom simulation law**, not established empirically for physical populations. The analysis does not estimate uncertainty over alternative master roots, model parameters, or simulator implementations. Shared host behavior also precludes transferring this reliability-independence argument automatically to timing [E1, E4].

### Actual paired whole-device bootstrap

The frozen `bootstrap_devices` implementation and saved `bootstrap` metadata agree: 24 sorted devices, 10,000 resamples, `cluster_unit="device"`, and `method="percentile-linear-(B-1)*p"` [E4, E5]. Define

\[
f_{pd,c}=\frac1{20}\sum_{t=1}^{20}F_{pdtc},\quad
b_{d,c}=f_{Sd,c}-f_{Md,c},\quad
\widehat\Delta_c=\frac1{24}\sum_{d=1}^{24}b_{d,c}.
\]

Equal trial counts make the equal-device estimator identical to the pooled paired-attempt difference. Each bootstrap replicate draws 24 device IDs uniformly with replacement. If \(w_d^{(b)}\) is device \(d\)'s multiplicity, then

\[
\widehat\Delta_c^{*(b)}=\frac1{24}\sum_dw_d^{(b)}b_{d,c},
\qquad \sum_dw_d^{(b)}=24.
\]

Every selected device contributes its complete record: all 20 trials, both matched policies, and all four σ settings. The same multiplicities produce S FRR, M FRR, and Δ across conditions. Repeated selection duplicates the record; it does not generate fresh trial noise. Aggregating complete records into device failure counts is equivalent for these estimators. Eligibility gates are applied to original data, not reapplied inside bootstrap replicates [E1, E4].

For each statistic, the implementation sorts the 10,000 replicate estimates and linearly interpolates the 0.025 and 0.975 quantiles at index \((B-1)p\). This is a two-sided **percentile interval**, not basic, BCa, normal-approximation, or independent-binomial inference. Inspection of the imported `percentile` function confirms that convention. Read-only arithmetic using saved device records and the recorded seed reproduced all 12 saved S/M/Δ intervals exactly, without invoking acquisition or decoding.

### Reported uncertainty and interpretation

At σ = 0.15, the saved Δ endpoints are 0.03333333333333334 and 0.1125, giving **[3.333, 11.250] percentage points**. All 10,000 replicates are defined; the interval is nondegenerate. Its interpretation is approximate sampling uncertainty for the mean policy difference over newly generated devices and repeated trials under the fixed simulation law, using the observed device records as the empirical cluster distribution [E5].

The relevant sample size is **24 resampled devices**, each with 20 paired trials per condition. Additional trials improve measurement of device-specific rates; they do not replace independent devices. Pairing retains the covariance between policy outcomes. Independently bootstrapping arms would remove it: \(\operatorname{Var}(S-M)=\operatorname{Var}(S)+\operatorname{Var}(M)-2\operatorname{Cov}(S,M)\). Ignoring pairing can therefore distort uncertainty in either direction; it is not repaired by subtracting separate arm-interval endpoints.

The interval is pointwise and descriptive. It does not assign a 95% probability to a fixed parameter, guarantee exact coverage with 24 devices, or incorporate model misspecification. If shared group effects existed, a device bootstrap could understate uncertainty; four groups would offer weak evidence for group-level inference. The frozen specification requires reconsidering clustering prospectively if such effects are introduced. Calibration instead reports group and deletion sensitivities [E1, E5].

Finally, the same data and interval helped select σ. A positive lower endpoint is one qualification gate, not confirmatory significance after searching four candidates. There is no simultaneous or selection-adjusted confidence procedure. Fresh devices and prespecified disjoint phase streams are needed for subsequent evaluation. **The resampling unit is the whole device; the reported uncertainty is conditional, pointwise calibration uncertainty, not independent confirmation of the selected setting.**

## Scientific Justification for Selecting σ = 0.15

Why was this operating point selected, and which evidence demonstrates compliance with the original rules?

### Purpose and authority of the selection rule

Correlation effects require an independent-read reference with enough failures and discordances to reveal changes in voting benefit. A near-perfect baseline creates a floor; excessive failure can make the stress condition unrepresentative of useful reconstruction. Broad rate bounds, minimum counts, uncertainty screens, and device/group checks jointly define an informative region. They calibrate an experimental stress condition, not a production deployment optimum or a power calculation [E1].

The authoritative numerical origin is the frozen specification's **Prespecified Calibration Procedure** table, operationalized by frozen `selection_rules` and `candidate_gates`. It requires every gate, completion of all four candidates before selection, and selection of the **lowest numeric σ** that qualifies. If none qualifies, selection must report no operating point; there is no automatic expansion, seed search, or fallback to 0.25 [E1, E4].

The specification calls these numbers “new proposed quantitative defaults”; configuration and receipt retain proposal-status labels. However, the consumed approval-v2 names Will Wallace, records `allocation_rules_and_resources_reviewed=true`, and binds these exact rules/configuration/source identities before the restart. Its authorization basis explicitly records user-authorized bounded execution and disclaims a faculty signature. Thus these are prospectively fixed, researcher-authorized execution rules; their origin must not be described as faculty-approved thresholds. The later computational selection is a separate decision, and its acknowledgment remains pending [E2, E6].

### Complete gate-by-gate assessment

The seven implemented names are `coverage_correctness`, `baseline_region`, `majority_region`, `minimum_benefit`, `informative_counts`, `uncertainty`, and `heterogeneity`. The table expands every constituent test. Rates/endpoints are percentages; differences and widths are percentage points (pp). **P/F** means pass/fail using original unrounded values. All inequalities are inclusive except explicitly strict `>0`.

| Prespecified criterion / rule field                | Exact threshold                                                                                     | σ = 0.10                   | σ = 0.15                | σ = 0.20           | σ = 0.25           | Evidence   |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------- | ------------------------ | ------------------- | ------------------- | ---------- |
| `coverage_correctness`                           | Complete 3,840-attempt schedule; all pairs; two-pass validation; zero infrastructure/release faults | 480 pairs; P                | 480 pairs; P             | 480 pairs; P        | 480 pairs; P        | E1–E3     |
| `baseline_region`: `single_frr_min/max`        | 5% ≤ S FRR ≤ 70%                                                                                  | 2.292%; **F**         | 10.208%; P               | 24.583%; P          | 36.458%; P          | E1, E4, E5 |
| `single_failures_min`                            | S failures ≥ 24                                                                                    | 11; **F**             | 49; P                    | 118; P              | 175; P              | E1, E5     |
| `single_correct_min`                             | S correct ≥ 24                                                                                     | 469; P                      | 431; P                   | 362; P              | 305; P              | E1, E5     |
| `majority_region`: `majority_frr_max`          | M FRR ≤ 50%                                                                                        | 4/480 = 0.833%; P           | 15/480 = 3.125%; P       | 34/480 = 7.083%; P  | 65/480 = 13.542%; P | E1, E5     |
| `minimum_benefit`: `delta_min`                 | Δ ≥ 2 pp                                                                                          | 1.458; **F**          | 7.083; P                 | 17.500; P           | 22.917; P           | E1, E5     |
| `informative_counts`: `discordances_min`       | Beneficial + harmful pairs ≥ 20                                                                    | 10+3 = 13; **F**      | 40+6 = 46; P             | 90+6 = 96; P        | 116+6 = 122; P      | E1, E5     |
| `event_devices_min` for discordance              | Distinct discordant devices ≥ 6                                                                    | 6; P                        | 14; P                    | 20; P               | 23; P               | E1, E5     |
| `event_groups_min` for discordance               | Distinct discordant groups ≥ 3                                                                     | 3; P                        | 4; P                     | 4; P                | 4; P                | E1, E5     |
| `event_devices_min` for S failures               | Distinct S-failure devices ≥ 6                                                                     | 5; **F**              | 14; P                    | 20; P               | 23; P               | E1, E5     |
| `event_groups_min` for S failures                | Distinct S-failure groups ≥ 3                                                                      | 3; P                        | 4; P                     | 4; P                | 4; P                | E1, E5     |
| `uncertainty`: `single_ci_lower_min/upper_max` | S 95% CI lower ≥ 1%; upper ≤ 85%                                                                  | [0.625, 4.375]; **F** | [5.417, 15.625]; P       | [16.042, 33.958]; P | [26.667, 46.250]; P | E1, E4, E5 |
| Δ CI lower endpoint                               | Strictly > 0 pp                                                                                     | 0.208; P                    | 3.333; P                 | 11.667; P           | 17.500; P           | E1, E4, E5 |
| `delta_ci_width_max`                             | Full Δ CI width ≤ 20 pp                                                                           | 2.714; P                    | 7.917; P                 | 11.667; P           | 10.833; P           | E1, E5     |
| `heterogeneity`: `leave_device_delta_min`      | Every delete-one-device Δ ≥ 1 pp                                                                  | Minimum 1.087; P            | Minimum 5.870; P         | Minimum 16.087; P   | Minimum 21.739; P   | E1, E5     |
| `positive_groups_min`                            | ≥ 3 group means strictly > 0                                                                       | 3/4; P                      | 4/4; P                   | 4/4; P              | 4/4; P              | E1, E5     |
| `group_delta_min`                                | Every group mean ≥ −2 pp                                                                          | Minimum 0.000; P            | Minimum 3.333; P         | Minimum 10.000; P   | Minimum 15.000; P   | E1, E5     |
| Combined decision                                  | Every gate passes; choose lowest qualifying σ                                                      | Fail                        | **Pass; selected** | Pass                | Pass                | E2, E5     |

Coverage is a global prerequisite, not four separate certifications. The completion marker records 3,840 attempts, 1,920 pairs, two completed validation passes, and zero unauthorized releases; saved rows contain zero infrastructure faults. Read-only checks also matched each row to the saved plan's execution order [E2, E3].

Count-spread tests count each affected device/group once, using the union of both discordance directions. A group FRR pools its six equal-sized device records (120 trials per policy), equivalently their equal-weight mean. Deleting a device averages the other 23 devices, not the surviving failed attempts. At σ = 0.15, group benefits are 3.333, 12.500, 6.667, and 5.833 pp; all are positive. Every device deletion leaves Δ between 5.870 and 7.609 pp. Group-deletion estimates range from 5.278 to 8.333 pp, a reported sensitivity rather than an additional selection gate [E5].

The implementation agrees with the frozen rules, including strict positivity and exact count-based fraction comparisons. It also requires defined interval endpoints. No minimum M-failure count, W/I count, per-device positive benefit, p-value, latency threshold, or maximum-benefit ranking is specified. Indeed, one selected-condition device has Δ = −5 pp; the actual consistency requirement concerns deletion stability and group means, not unanimous individual benefit. The rule does not require zero adverse discordances [E1, E4, E5].

### Why 0.15, rather than 0.10 or a higher setting?

σ = 0.10 fails four composite gates: `baseline_region` (2.292% and 11 failures), `minimum_benefit` (1.458 pp), `informative_counts` (13 discordances and only five S-failure devices), and `uncertainty` (S's lower endpoint 0.625%). Its positive Δ interval alone is insufficient. All other constituent tests pass.

σ = 0.15 is the next candidate and passes every requirement: observable baseline failure, acceptable M failure, sufficient absolute benefit and event spread, defined intervals within the specified bounds, and deletion/group consistency. Settings 0.20 and 0.25 also qualify and have larger observed improvements. They are not rejected as operationally unacceptable by these gates. They simply lose under the prespecified lowest-qualifying ordering, which selects the least severe candidate providing the required evidence. Choosing the largest Δ afterward would replace the scientific rule with a different objective.

The recorded computation follows the original rule without numerical retuning: `selection.json.result.selected_sigma=0.15` and the four recorded gate decisions match independent arithmetic checks. This supports procedural selection compliance, while leaving the selection-data estimates descriptive. Following a prospective rule constrains arbitrary parameter choice; it does not remove sampling variation or selection bias [E1, E2, E5].

### Connection to the future correlation evaluation

The selected value is bound into a computational receipt, but a complete final-study freeze is **not** established. `postcompletion-analysis-receipt.json` records acknowledgment pending, `eligible_for_final_planning=false`, and `final_evaluation_enabled=false`; configuration also disables final execution. No actual acknowledgment or completed selected-sigma final-evaluation bundle was located. The frozen specification's earlier “pending/not implemented” statements describe its prospective stage, not a contradiction of the later completed calibration [E1, E6, E7].

Before evaluation, the researcher must supply the separate dated acknowledgment, resolve the integrity limitation below, review/version and freeze the final specification/configuration/analysis/source/plan, qualify resources, and obtain separate execution authority. The proposed study holds σ = 0.15 fixed across ρ = 0, 0.50, 0.90, and 1.00, using fresh `w9f` devices and phase domains. Calibration roots 2026102801–04 differ from reserved final roots 2026102811–14; these are distinct stream roots, not four independently executed population replications. The proposed final allocation and controls remain future work. No final outcome may be used to retune σ [E1, E7].

**Selection finding:** σ = 0.15 is the lowest candidate satisfying the frozen calibration contract in the completed saved data. It is a justified experimental stress setting conditional on that contract, not a universally optimal noise level, a faculty-approved deployment value, or authorization to execute the next study.

## Evidence and Reproducibility

Paths below are repository-relative. **B** denotes [the completed restart bundle][bundle]:

`results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/`

**R** denotes [its associated analysis/approval records][records]:

`results/week-9/will/calibration-restart-v1/restart-20261028-01/`

| ID | Source and path                                                                                                                                                                                                                            | Relevant location and supported claim                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| -- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E1 | [Frozen specification][spec], `B/source/docs/week9-shared-noise-study-specification.md`                                                                                                                                                  | “Prespecified Calibration Procedure,” lines 205–266: every threshold and ordering rule; “Statistical Analysis and Cluster Bootstrap,” lines 411–517: independence, resampling, interval and selection limits; allocation/seed and outcome sections: future design and C/D/I/W. Authoritative prospective scientific contract.                                                                                                                                                                                                |
| E2 | [Selection][selection], `B/selection.json`; `B/config.json`, `B/authorization-consumption.json`, `B/CALIBRATION_VALIDATED.json`                                                                                                    | `candidates`, `result.candidates[].gates`, `result.selected_sigma`; `selection_rules`; embedded `approval`; marker counts and validation passes. Separates configured rules, observations, computational choice, and recorded execution certification.                                                                                                                                                                                                                                                                   |
| E3 | [Attempt ledger][attempts], `B/attempts.jsonl`; `B/trial-plan.json`                                                                                                                                                                    | `reconstruction.classification`, `observations`, enrollment hashes, verifier/session/release fields; `blocks` and execution indices. Primary outcomes, pairing, operations, denominators and schedule.                                                                                                                                                                                                                                                                                                                       |
| E4 | Frozen code under `B/source/src/python/puf_snn/`                                                                                                                                                                                         | `experiments/shared_noise_calibration_analysis_v1.py`: `complete_cells`, `device_records`, `bootstrap_devices`, `candidate_gates`, `select_candidates`; `majority3_auth_analysis_v1.percentile`; `shared_noise_calibration_v1.enrollment_material/compile_plan`; `shared_noise_calibration_runtime_v1.execute_attempt`; `correlated_noise_v1.derive_seed/measure_indexed`; `puf/device.py`, `puf/acquisition.py`, `reconstruction/credential.py`. Actual generation, metric and analysis implementation. |
| E5 | [Saved analysis][analysis], `R/analysis.json`; [device export][devices], `R/device-results.csv`; `B/summary.json`                                                                                                                    | `bootstrap`, `devices`, `candidates`, `selection`. Intervals, seed/digest, device/group aggregation and every gate input. Sidecar analysis equals the sealed summary's analysis as parsed JSON.                                                                                                                                                                                                                                                                                                                            |
| E6 | `R/approval-v2.json`, `R/authorization-basis.json`, [postcompletion receipt][post], `R/postcompletion-analysis-receipt.json`                                                                                                         | Reviewed allocation/rules and bounded authority; no faculty signature; exact analysis agreement; pending acknowledgment and disabled planning/evaluation.                                                                                                                                                                                                                                                                                                                                                                          |
| E7 | [Current results report](../week9-shared-noise-calibration-results.md); [readiness](../week9-shared-noise-calibration-readiness.md); [validation](../week9-shared-noise-calibration-validation.json); [research log](../research-logs/will.md) | Report tables and pending status; acknowledgment contract; earlier 182-test readiness freeze; log's Week 9 calibration/results/next-steps entry, lines 1876–2067. Later explanation and development chronology, not substitutes for frozen evidence.                                                                                                                                                                                                                                                                              |
| E8 | `B/manifest.json`, `B/source-manifest.json`; `R/final-verification.json`, `R/standalone-audit.json`                                                                                                                                | Recorded file/source identities, historical PASS receipts, and present integrity comparison described below.                                                                                                                                                                                                                                                                                                                                                                                                                       |

The consumed approval records canonical configuration identity `79a275d06a8a1997981484f15d27cb5e76b39fd2a28b660a4251ddc35e83e756`, plan identity `e5d4deaf8b944dd514fbdcf2bba31cd91ec5dc22e66478ca8a55701a594135ff`, source identity `a888acae484452b4a85c8442c6d5c3d7fa39b555d27b699bd4f0eaf37fbaf5f6`, environment identity `6ef3b0cf006b693d9e8622044e7bd833299773c11b7276298a55caec713d2174`, and frozen specification SHA-256 `f5a12c19e9228860b901e9abb0eee4c16aa4dbaa785bbea32fa4b5e31b244b23`. Recorded source revision is `6fd13d143fa5c57692851d24d65b62ec3732f98c`. Canonical parsed analysis and selection hashes reproduce `4e7f2aba7eacb2852596e4f01b2cae2fcf723ee4df283b37d0cf82f6ed34bcc9` and `7cd3f25b3abfe8472d38841f744134cf88981a5d2771a7cc9de4b15463e819c6`, respectively. Canonical object digests are distinct from serialized-file byte hashes.

Bootstrap reproduction uses saved seed `19165396453591445348413096519203674100362636039808941285057306549493178840826`, sorted-device digest `502557a6441a687378ed0c8c2c7fa6ea155afd0eac8ae1a4f0275ce8881978f4`, the recorded Python `Random.randrange` algorithm, and the 24 device records. The historical execution environment records CPython 3.12.4; full dependency identities remain in `B/metadata.json`.

**Discrepancies requiring explicit qualification.** The current specification differs from the frozen bytes, but its calibration-procedure and statistical-analysis sections agree after whitespace normalization. The older validation JSON describes pre-execution readiness, not completed calibration; its pending authority labels cannot override the later run-bound approval. The completed report's interruption link points back to itself; the actual interrupted report is [in the archive](../archive/week9-shared-noise-calibration-results.md). Its device-export link also omits the actual `restart-20261028-01` sidecar location. Locations above were resolved directly; these historical documents were not edited.

Present read-only hashing found **76 of 126 manifest entries matching raw bytes, 49 matching only after in-memory CRLF-to-LF conversion, and one unreconciled by uniform LF/CRLF conversion**: `B/source/src/python/puf_snn/pipeline_timing.py`. That file's recorded digest is `1b9ddc6926877babca9a4bc7453b2ac71ff774f230656127416654ad2f052ba2`; current raw digest is `e204b6c5fb2607714aaf713a224ece5230d17737450e4b096c6472f66b446228`; LF-normalized digest is `1f0e23de9a17c9e44ee643c70417aa2452f218c016f2eb234ba78ddcc19e80d9`. The normalized content agrees with the corresponding Git blob at the recorded source revision, but that does not recover the receipt's original bytes or explain their hash. Mixed historical line endings or another provenance difference remain unresolved; no substantive source alteration is inferred solely from this mismatch.

The manifest and marker themselves likewise match their historical hashes only after in-memory newline normalization. Numerical JSON agreement and reproduced intervals therefore support the saved calculations, **not a new successful exact-byte audit**. No files were normalized on disk, repaired, repinned, or resealed. Human review should locate the original exact-byte evidence and resolve provenance before claiming present audit readiness or binding a new acknowledgment to this checkout.

## Limitations and Research Conclusions

The completed saved data support a 7.083-pp reconstruction-FRR reduction at σ = 0.15, a paired whole-device percentile interval based on 24 devices, and selection of the lowest candidate passing all prospective gates. These are descriptive calibration findings under a fixed software model. They establish neither physical-PUF performance, cryptographic security improvement, nor correlated-noise attenuation.

Generalization depends on the device-generation independence assumptions and simulator law; selected-data intervals are not confirmatory. Before the proposed correlation study, remaining human review concerns are exact-byte provenance, a genuine dated selection acknowledgment, and the final study's frozen design, resources, and execution authority. This document preserves the separation between those outstanding requirements and the completed numerical calibration. Only this new Markdown document was created; source, configurations, historical reports, frozen evidence, Git branch, and staging were left unchanged. No commit or push was performed.

[bundle]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/
[records]: ../../results/week-9/will/calibration-restart-v1/restart-20261028-01/
[spec]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/source/docs/week9-shared-noise-study-specification.md
[selection]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/selection.json
[attempts]: ../../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318/attempts.jsonl
[analysis]: ../../results/week-9/will/calibration-restart-v1/restart-20261028-01/analysis.json
[devices]: ../../results/week-9/will/calibration-restart-v1/restart-20261028-01/device-results.csv
[post]: ../../results/week-9/will/calibration-restart-v1/restart-20261028-01/postcompletion-analysis-receipt.json
