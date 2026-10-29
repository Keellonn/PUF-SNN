# Week 9 — Shared-Noise PUF Calibration Results

**Owner:** Will Wallace  
**Week:** 9
**Status:** Complete
**Date:** 10/28/26

**Execution status: Completed and independently audited.** `week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318`.

Evidence: [sealed bundle](../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318). Required completion marker: `CALIBRATION_VALIDATED.json`; both reconciliation passes completed. Standalone evidence audit: **PASS**. Selected sigma: **0.15**. Selection acknowledgment remains **pending**; final evaluation remains disabled.

This report concerns the separately authorized complete restart. The prior 543-attempt interrupted bundle, sidecars, consumed authorization, and [interruption report](week9-shared-noise-calibration-results.md) remain unchanged. Those partial observations are not pooled with this cohort or counted as independent replication.

## Research Objective
Choose an informative independent-read noise magnitude for the later study of how correlated PUF measurements change Majority-3 correct-credential reconstruction reliability. The estimand is Single-Read reconstruction FRR minus Majority-3 reconstruction FRR under the specified simulation law, not a hardware-security or trained-inference claim. Calibration evaluates rho=0 and selects the lowest sigma meeting every prespecified gate; it cannot estimate empirical correlation attenuation.

## Faculty Feedback and Experimental Motivation
The [frozen specification](week9-shared-noise-study-specification.md), [readiness record](week9-shared-noise-calibration-readiness.md), [Week 8 methodology](week8-three-arm-auth-methodology.md), [archived methodology review](archive/week8-three-arm-formal-methodology-review-v1.md), [feedback consolidation](week6-feedback-consolidation.md), and [research log](research-logs/will.md) supply the preserved feedback/methodology context. No faculty signature or researcher selection acknowledgment is fabricated. Original correspondence was not located in the earlier connected-mail search; this report relies on the repository records.

The independent-read reference selects a noise region with observable reconstruction failures and voting benefit before inspecting correlated final-evaluation outcomes. Device clustering retains repeated-trial and cross-sigma dependence. Neutral two-sided estimation allows failure of qualification; the selection rule was not retuned from results.

| Guidance | Compliance / scope |
| --- | --- |
| Independent-read calibration | All four sigma conditions at rho=0, C=0; full schedule completed before selection. |
| Disjoint calibration/final identities | Calibration roots 2026102801–04 and w9c devices; final roots 2026102811–14 and w9f devices reserved and unused. |
| Fixed marginal noise in future correlation study | Selected sigma must remain fixed across rho; calibration itself varies sigma only at rho=0. |
| Reconstruction vs authentication | C/D/I/W, actual verifier reach/refusal, admissions, sessions, windows and releases reported separately below. |
| Denominators and timing | 480 attempts per sigma/arm; 24 device bootstrap units; measured nested spans and actual conditional eligibility retained. |
| Resources and reproducibility | Actual monitored restart observations and independent standalone computational audit; no claim of independent researcher reproduction. |
| Separate earlier evidence | Week 8 three-arm, quality-check and saved-model results remain separate and unpooled; physical validation and warmed/model latency remain outside scope. |

Earlier [three-arm results](week9-three-arm-results.md), [evidence feasibility](week9-evidence-feasibility.md), [quality validation](week8-keegan-validation.md), and [quality equivalence](week8-quality-equivalence.md) retain their own experimental populations and boundaries. Calibration recording callbacks are not trained SNN inference. Historical pipeline provenance questions, physical/Quest access, and independent external reproduction remain unresolved by this computational calibration.

## Exact Experimental Configuration

| Parameter | Prespecified and observed |
| --- | --- |
| Population groups / devices per group / devices | 4 / 6 / 24 |
| Trials per device per sigma | 20 |
| Sigmas | 0.10, 0.15, 0.20, 0.25 |
| rho / C / manufacturing SD | 0 / 0 / 1 |
| Policies | single-read-v1; majority-3-v1 |
| Matched trial identities / policy attempts | 1,920 / 3,840 |
| Experimental readings / runtime BCH decodes / votes | 7,680 / 3,840 / 1,920 |
| Enrollment reference readings | 24, separate setup work |
| Bootstrap | 10,000 paired whole-device draws, shared multiplicities across sigmas |
| Two-pass replay readings / decodes / references | 15,360 / 7,680 / 48; zero new samples |
| Standalone audit readings / decodes / references | 7,680 / 3,840 / 24; zero new samples |
| Timing / consumer | cold-process-no-harness-warmup-v1; recording-consumer-v1 |
| Final execution | disabled |

All 480 S and 480 M attempts at each sigma are retained. BCH(63,36,t=5), 32-bit credential plus four fixed padding bits, the first 63 of 64 PUF bits, 128 oscillators in adjacent pairs, independent verifier, admission service, Authentication-v2, and a stationary 120-sample sequence-zero window remain unchanged. No stored-provisioned arm is included in calibration.

## Noise Model and Randomization

```text
f(d,a,i,r) = 100 + M(d,i) + C(d,a)
           + sigma*sqrt(rho)*Z(d,a,i)
           + sigma*sqrt(1-rho)*E(d,a,i,r)
```

M is drawn once per device with SD=1 and retained across all conditions. Here rho=0, C=0, noiseless enrollment; sigma uses abstract additive frequency units, not measured Hz. Oscillator pairing and reconstruction settings are fixed. Every Majority-3 attempt performs three measurements and one vote; S/M use separate readers with the same indexed reading-zero noise identity. No cached observation replaces acquisition. All 1,920 first-reading pairs reconcile.

Calibration master/schedule/bootstrap/group-sensitivity roots are 2026102801/02/03/04. Measurement domains are separate across the four sigmas; device manufacturing and enrollment persist. Final master/schedule/bootstrap/group roots are 2026102811/12/13/14 with separate w9f devices and phase domains. The balanced alternating policy order and deterministic whole-block shuffle are unchanged. Protocol nonces and verifier material retain OS randomness; traces/timing are not seed-identical. No unfavorable attempt was discarded or retried.

The restart repeats the original frozen cohort and schedule with a new authorization/output, rather than searching new seeds. Repeated partial-prefix observations from the failed invocation do not enlarge device or trial denominators.

## Execution Environment and Frozen Identities

| Identity | Exact value |
| --- | --- |
| config_sha256 | `79a275d06a8a1997981484f15d27cb5e76b39fd2a28b660a4251ddc35e83e756` |
| environment_sha256 | `6ef3b0cf006b693d9e8622044e7bd833299773c11b7276298a55caec713d2174` |
| plan_sha256 | `e5d4deaf8b944dd514fbdcf2bba31cd91ec5dc22e66478ca8a55701a594135ff` |
| source_id | `a888acae484452b4a85c8442c6d5c3d7fa39b555d27b699bd4f0eaf37fbaf5f6` |
| specification_sha256 | `f5a12c19e9228860b901e9abb0eee4c16aa4dbaa785bbea32fa4b5e31b244b23` |

Committed source: `6fd13d143fa5c57692851d24d65b62ec3732f98c`, branch `main`. All 116 required source files are committed and match the exact 197-test source freeze. The existing `.gitignore` edit and untracked prior reports are outside the required source identity and were left untouched. No source, configuration, dependency, or environment change was made for execution.

Interpreter: `C:\PUF+SNN_SharedRepo\PUF-SNN\.venv\Scripts\python.exe`; `3.12.4 (tags/v3.12.4:8e8a4ba, Jun  6 2024, 19:30:16) [MSC v.1940 64 bit (AMD64)]`; CPython; `Windows-11-10.0.26200-SP0`. Packages: galois=0.4.11, jsonschema=4.26.0, numba=0.67.0, numpy=2.5.3, scipy=1.18.1. CPU: `Intel64 Family 6 Model 151 Stepping 2, GenuineIntel`; 20 logical cores; host RAM 34,191,159,296 bytes. Native Windows access used the same venv/base interpreter, without substituting MSYS Python or installing dependencies.

The approved resource budget remains 1,800 s workflow/session, 4 GiB sampled process-memory cap, free RAM strictly >8 GiB, free disk strictly >1 GiB, bundle growth <512 MiB, aggregate growth <1 GiB, 0.05 s requested monitoring, and 2 s stop grace. The Week 9 mutex/snapshot adapter remains active. Every live inspection used the coordinated `status` CLI; no raw live monitor/progress reader was used.

No power plan/background-load policy or thread setting was changed. NUMBA_DISABLE_JIT, NUMBA_NUM_THREADS, OMP_NUM_THREADS, MKL_NUM_THREADS and OPENBLAS_NUM_THREADS were unset in recorded operator context. The scientific worker uses its new run-specific compiler-cache directory and PYTHONDONTWRITEBYTECODE=1. Zero harness warmups does not imply every package/system cache is empty; setup may initialize code outside timed roots.

## Experimental Completion and Evidence Validation

The validated completion marker exists and the incomplete sentinel is absent. Exactly **3,840** attempts, **1,920** matched identities, **24** devices, all four groups/sigmas, **7,680** readings, **3,840** runtime decodes and **1,920** votes reconcile. There are zero missing/duplicate attempts, infrastructure faults or unauthorized releases. Controller acceptance verified consumed authorization, source/environment freeze, manifest identity, resource supervision and final budget checks before atomic marker publication.

Both finalization reconciliation passes succeeded. Their additional 15,360 PUF readings, 7,680 BCH decodes and 48 reference readings are verification operations, not new samples. The later standalone CLI audit passed, adding 7,680 readings, 3,840 decodes and 24 references, also zero samples. Including original enrollment, finalization and that audit gives 30,816 simulator measurements and 15,360 decodes in this invocation/audit workflow; scientific denominators remain 1,920 pairs and 3,840 policy attempts.

After the audit, the unchanged frozen analysis implementation was explicitly rerun on all completed rows and matched the sealed analysis exactly. This numerical reanalysis adds no PUF measurements, decodes, or scientific samples. Computed selection-v2 was verified against all four decisions and hashed evidence. No new acknowledgment was created.

## Four-Sigma Reliability Results

| Sigma | Single FRR | Majority-3 FRR | Delta | 95% CI for Delta | Qualifies |
| --- | --- | --- | --- | --- | --- |
| 0.10 | 11/480 (2.292%) | 4/480 (0.833%) | 1.458 pp | [0.208, 2.922] pp | Fail |
| 0.15 | 49/480 (10.208%) | 15/480 (3.125%) | 7.083 pp | [3.333, 11.250] pp | Pass |
| 0.20 | 118/480 (24.583%) | 34/480 (7.083%) | 17.500 pp | [11.667, 23.333] pp | Pass |
| 0.25 | 175/480 (36.458%) | 65/480 (13.542%) | 22.917 pp | [17.500, 28.333] pp | Pass |

FRR is `(D+I+W)/480`; Delta is S FRR minus M FRR, positive for an observed Majority-3 advantage. The balanced pooled rate equals the equally weighted mean over 24 devices. No p-value, latency, or largest-benefit ranking enters selection. Rounded display values do not govern gates.

## Paired Bootstrap Confidence Intervals

| Sigma | S FRR 95% CI (%) | M FRR 95% CI (%) | Paired Delta 95% CI (pp) | Degenerate / unseen-event flags |
| --- | --- | --- | --- | --- |
| 0.10 | [0.625, 4.375] | [0.208, 1.667] | [0.208, 2.922] | none |
| 0.15 | [5.417, 15.625] | [1.250, 5.417] | [3.333, 11.250] | none |
| 0.20 | [16.042, 33.958] | [3.125, 11.458] | [11.667, 23.333] | none |
| 0.25 | [26.667, 46.250] | [7.292, 20.417] | [17.500, 28.333] | none |

Exactly **10,000** whole-device resamples use D=24 sorted devices with replacement. Each multiplicity retains all 20 trials, both paired outcomes and all four sigma conditions. The same draws determine both FRRs and paired Delta; separate arm intervals are not substituted for the paired interval. Seed: `19165396453591445348413096519203674100362636039808941285057306549493178840826`; sorted-device digest: `502557a6441a687378ed0c8c2c7fa6ea155afd0eac8ae1a4f0275ce8881978f4`. Quantiles use linear interpolation at `(B−1)*p`, two-sided 2.5%/97.5% pointwise percentile intervals. All primary intervals have 10,000 defined resamples.

Intervals are approximate, pointwise and estimation-only, not simultaneous/confirmatory evidence after sigma selection. A zero-event [0,0] FRR interval, where flagged, is degenerate and uninformative about unseen failures; observed zero does not establish zero failure probability. No pseudocount, independent-attempt binomial interval, clipping, or revised estimator was introduced. Four labeled groups are descriptive sensitivity batches under independent device generation, not an unmodeled shared manufacturing random effect.

Beneficial discordance means S fails/M succeeds; harmful means S succeeds/M fails. Delta equals their net count divided by 480.

| Sigma | Beneficial | Harmful | Total discordant / 480 | Discordant devices / groups | S-failure devices / groups |
| --- | --- | --- | --- | --- | --- |
| 0.10 | 10 | 3 | 13 | 6/24; 3/4 | 5/24; 3/4 |
| 0.15 | 40 | 6 | 46 | 14/24; 4/4 | 14/24; 4/4 |
| 0.20 | 90 | 6 | 96 | 20/24; 4/4 | 20/24; 4/4 |
| 0.25 | 116 | 6 | 122 | 23/24; 4/4 | 23/24; 4/4 |

## Device and Population-Group Heterogeneity

| Sigma | Device S FRR range, SD (pp) | Device M FRR range, SD (pp) | Device Delta range, SD (pp) | Delete-one-device Delta (pp) | Delete-one-group Delta (pp) |
| --- | --- | --- | --- | --- | --- |
| 0.10 | 0.000–15.000 (SD 4.885) | 0.000–5.000 (SD 1.903) | -5.000–10.000 (SD 3.753) | 1.087–1.739 | 1.111–1.944 |
| 0.15 | 0.000–40.000 (SD 12.978) | 0.000–20.000 (SD 5.480) | -5.000–35.000 (SD 10.099) | 5.870–7.609 | 5.278–8.333 |
| 0.20 | 0.000–80.000 (SD 23.027) | 0.000–35.000 (SD 10.725) | 0.000–50.000 (SD 14.891) | 16.087–18.261 | 15.278–20.000 |
| 0.25 | 0.000–75.000 (SD 24.693) | 0.000–60.000 (SD 16.906) | 0.000–50.000 (SD 13.903) | 21.739–23.913 | 20.833–25.556 |

SD is the descriptive sample standard deviation over 24 device rates; no reading/trial is an independent device. Each delete-device estimate averages the remaining 23 whole devices; each delete-group estimate retains the other 18. Group bootstrap intervals are not presented from only four groups.

| Group | Sigma | S failures / 120 | M failures / 120 | Group Delta (pp) | Delete this group Delta (pp) |
| --- | --- | --- | --- | --- | --- |
| w9c-p000 | 0.10 | 0/120 (0.000%) | 0/120 (0.000%) | 0.000 | 1.944 |
| w9c-p001 | 0.10 | 3/120 (2.500%) | 0/120 (0.000%) | 2.500 | 1.111 |
| w9c-p002 | 0.10 | 3/120 (2.500%) | 2/120 (1.667%) | 0.833 | 1.667 |
| w9c-p003 | 0.10 | 5/120 (4.167%) | 2/120 (1.667%) | 2.500 | 1.111 |
| w9c-p000 | 0.15 | 5/120 (4.167%) | 1/120 (0.833%) | 3.333 | 8.333 |
| w9c-p001 | 0.15 | 20/120 (16.667%) | 5/120 (4.167%) | 12.500 | 5.278 |
| w9c-p002 | 0.15 | 12/120 (10.000%) | 4/120 (3.333%) | 6.667 | 7.222 |
| w9c-p003 | 0.15 | 12/120 (10.000%) | 5/120 (4.167%) | 5.833 | 7.500 |
| w9c-p000 | 0.20 | 14/120 (11.667%) | 2/120 (1.667%) | 10.000 | 20.000 |
| w9c-p001 | 0.20 | 30/120 (25.000%) | 10/120 (8.333%) | 16.667 | 17.778 |
| w9c-p002 | 0.20 | 39/120 (32.500%) | 10/120 (8.333%) | 24.167 | 15.278 |
| w9c-p003 | 0.20 | 35/120 (29.167%) | 12/120 (10.000%) | 19.167 | 16.944 |
| w9c-p000 | 0.25 | 21/120 (17.500%) | 3/120 (2.500%) | 15.000 | 25.556 |
| w9c-p001 | 0.25 | 60/120 (50.000%) | 29/120 (24.167%) | 25.833 | 21.944 |
| w9c-p002 | 0.25 | 46/120 (38.333%) | 11/120 (9.167%) | 29.167 | 20.833 |
| w9c-p003 | 0.25 | 48/120 (40.000%) | 22/120 (18.333%) | 21.667 | 23.333 |

Per-device failures, S/M out of 20 at each sigma (all 24 devices retained):

| Device | 0.10 S/M | 0.15 S/M | 0.20 S/M | 0.25 S/M |
| --- | --- | --- | --- | --- |
| w9c-p000-d00 | 0/0 | 0/0 | 0/0 | 1/0 |
| w9c-p000-d01 | 0/0 | 1/0 | 1/0 | 6/0 |
| w9c-p000-d02 | 0/0 | 0/0 | 2/0 | 1/0 |
| w9c-p000-d03 | 0/0 | 1/1 | 3/2 | 4/0 |
| w9c-p000-d04 | 0/0 | 0/0 | 4/0 | 1/0 |
| w9c-p000-d05 | 0/0 | 3/0 | 4/0 | 8/3 |
| w9c-p001-d00 | 2/0 | 8/1 | 16/6 | 15/12 |
| w9c-p001-d01 | 0/0 | 3/1 | 3/2 | 9/4 |
| w9c-p001-d02 | 0/0 | 0/0 | 0/0 | 5/0 |
| w9c-p001-d03 | 0/0 | 5/1 | 5/1 | 11/7 |
| w9c-p001-d04 | 0/0 | 0/0 | 2/0 | 6/1 |
| w9c-p001-d05 | 1/0 | 4/2 | 4/1 | 14/5 |
| w9c-p002-d00 | 3/1 | 7/4 | 9/5 | 13/4 |
| w9c-p002-d01 | 0/0 | 0/0 | 0/0 | 0/0 |
| w9c-p002-d02 | 0/0 | 1/0 | 7/0 | 8/2 |
| w9c-p002-d03 | 0/0 | 2/0 | 8/1 | 10/2 |
| w9c-p002-d04 | 0/1 | 2/0 | 13/4 | 13/3 |
| w9c-p002-d05 | 0/0 | 0/0 | 2/0 | 2/0 |
| w9c-p003-d00 | 0/0 | 2/0 | 6/0 | 10/6 |
| w9c-p003-d01 | 0/0 | 0/0 | 0/0 | 1/0 |
| w9c-p003-d02 | 0/0 | 0/0 | 2/1 | 3/0 |
| w9c-p003-d03 | 3/1 | 2/3 | 10/4 | 12/5 |
| w9c-p003-d04 | 0/0 | 0/0 | 3/0 | 7/1 |
| w9c-p003-d05 | 2/1 | 8/2 | 14/7 | 15/10 |

Failure-event concentration (shares of each arm’s failures, not shares of attempts):

| Sigma | S largest device / top 3 share | M largest device / top 3 share |
| --- | --- | --- |
| 0.10 | 27.273% / 72.727% | 25.000% / 75.000% |
| 0.15 | 16.327% / 46.939% | 26.667% / 60.000% |
| 0.20 | 13.559% / 36.441% | 20.588% / 52.941% |
| 0.25 | 8.571% / 25.143% | 18.462% / 44.615% |

Exact device rates, benefits and discordances are exported in [device-results.csv](../results/week-9/will/calibration-restart-v1/restart-20261028-01/device-results.csv); every leave-one-out value, group estimate and gate input is retained in [analysis.json](../results/week-9/will/calibration-restart-v1/restart-20261028-01/analysis.json). These sensitivity calculations do not add devices or trigger a new experiment.

## Operating-Point Selection

| Sigma | Coverage | Baseline | M region | Benefit | Counts/spread | Uncertainty | Heterogeneity | Decision / failed criteria |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.10 | Pass | Fail | Pass | Fail | Fail | Fail | Pass | baseline_region, minimum_benefit, informative_counts, uncertainty |
| 0.15 | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Qualifies |
| 0.20 | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Qualifies |
| 0.25 | Pass | Pass | Pass | Pass | Pass | Pass | Pass | Qualifies |

The unchanged gates require 0.05≤S FRR≤0.70; ≥24 S failures and ≥24 correct; M FRR≤0.50; Delta≥0.02; ≥20 discordances spanning ≥6 devices/≥3 groups; S failures spanning ≥6 devices/≥3 groups; S CI lower≥0.01 and upper≤0.85; Delta CI lower **>0**, full width≤0.20; every device deletion Delta≥0.01; ≥3 strictly positive group benefits; no group benefit below −0.02. Unrounded inputs and inclusive boundaries apply except explicit strict positivity. Groups have equal size. Gates are evaluated once on complete observed data, not reapplied inside bootstrap draws.

**Select sigma=0.15: the lowest numeric candidate passing every gate.** At this point, deleting any one device leaves Delta between 5.870 and 7.609 pp; deleting any group leaves 5.278–8.333 pp. Group benefits are 3.333, 12.500, 6.667, 5.833 pp. This supports the prespecified calibration robustness screen, with device-population uncertainty still represented by its pointwise interval. It is not a deployment reliability or confirmatory superiority guarantee.

Selection-v2 records the actual algorithm, all four candidate decisions, computation timestamp and evidence digests. It is not a researcher acknowledgment. No named/datetime acknowledgment has been supplied; acknowledgment and final-study planning eligibility remain pending, and final execution is disabled.

Sigma 0.10 specifically fails because S FRR is 2.292% (<5%) with only 11 S failures (<24); Delta is 1.458 pp (<2 pp); there are 13 discordances (<20) and S failures span five devices (<6); and the S FRR interval lower endpoint is 0.625% (<1%). Its other subcriteria pass. Sigmas 0.15, 0.20 and 0.25 pass every gate; choosing 0.15 follows the lowest-qualifying rule even though larger sigmas have larger observed benefits.

## Reconstruction and Authentication Failure Accounting

| Sigma | Arm | C / 480 | D / 480 | I / 480 | W / 480 |
| --- | --- | --- | --- | --- | --- |
| 0.10 | S | 469/480 (97.71%) | 11/480 (2.29%) | 0/480 (0.00%) | 0/480 (0.00%) |
| 0.10 | M | 476/480 (99.17%) | 4/480 (0.83%) | 0/480 (0.00%) | 0/480 (0.00%) |
| 0.15 | S | 431/480 (89.79%) | 48/480 (10.00%) | 1/480 (0.21%) | 0/480 (0.00%) |
| 0.15 | M | 465/480 (96.88%) | 13/480 (2.71%) | 1/480 (0.21%) | 1/480 (0.21%) |
| 0.20 | S | 362/480 (75.42%) | 110/480 (22.92%) | 6/480 (1.25%) | 2/480 (0.42%) |
| 0.20 | M | 446/480 (92.92%) | 34/480 (7.08%) | 0/480 (0.00%) | 0/480 (0.00%) |
| 0.25 | S | 305/480 (63.54%) | 173/480 (36.04%) | 1/480 (0.21%) | 1/480 (0.21%) |
| 0.25 | M | 415/480 (86.46%) | 65/480 (13.54%) | 0/480 (0.00%) | 0/480 (0.00%) |

| Sigma | Arm | Verifier calls / 480 | Verified / calls | Explicit refusals / calls | Not reached / 480 | Admissions / 480 | Sessions / 480 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.10 | S | 469/480 (97.71%) | 469/469 (100.00%) | 0/469 (0.00%) | 11/480 (2.29%) | 469/480 (97.71%) | 469/480 (97.71%) |
| 0.10 | M | 476/480 (99.17%) | 476/476 (100.00%) | 0/476 (0.00%) | 4/480 (0.83%) | 476/480 (99.17%) | 476/480 (99.17%) |
| 0.15 | S | 431/480 (89.79%) | 431/431 (100.00%) | 0/431 (0.00%) | 49/480 (10.21%) | 431/480 (89.79%) | 431/480 (89.79%) |
| 0.15 | M | 466/480 (97.08%) | 465/466 (99.79%) | 1/466 (0.21%) | 14/480 (2.92%) | 465/480 (96.88%) | 465/480 (96.88%) |
| 0.20 | S | 364/480 (75.83%) | 362/364 (99.45%) | 2/364 (0.55%) | 116/480 (24.17%) | 362/480 (75.42%) | 362/480 (75.42%) |
| 0.20 | M | 446/480 (92.92%) | 446/446 (100.00%) | 0/446 (0.00%) | 34/480 (7.08%) | 446/480 (92.92%) | 446/480 (92.92%) |
| 0.25 | S | 306/480 (63.75%) | 305/306 (99.67%) | 1/306 (0.33%) | 174/480 (36.25%) | 305/480 (63.54%) | 305/480 (63.54%) |
| 0.25 | M | 415/480 (86.46%) | 415/415 (100.00%) | 0/415 (0.00%) | 65/480 (13.54%) | 415/480 (86.46%) | 415/480 (86.46%) |

D/I stop before verifier reach and are not explicit verifier refusals. All **4** valid-format wrong candidates were independently refused as `credential_mismatch` before session establishment, with zero releases. Their exact execution identities are retained in research-diagnostics.json. A BCH-valid candidate is not necessarily authenticated. Total verifier calls: 3,373; successful verification/admissions/sessions: 3,369; explicit wrong-credential refusals: 4. No disabled-policy refusal or post-verification attrition was observed. Each cell’s admission/verified and session/admission conditional rates are 100% with its own nonzero eligible count as denominator.

| Sigma | Arm | Accepted / tested windows | Rejected / tested windows | Authorized releases / sessions | Unauthorized / tested windows | Release entry / completion | Each callback invoke / complete |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.10 | S | 469/469 (100.00%) | 0/469 (0.00%) | 469/469 (100.00%) | 0/469 (0.00%) | 469 / 469 | 469 / 469 |
| 0.10 | M | 476/476 (100.00%) | 0/476 (0.00%) | 476/476 (100.00%) | 0/476 (0.00%) | 476 / 476 | 476 / 476 |
| 0.15 | S | 431/431 (100.00%) | 0/431 (0.00%) | 431/431 (100.00%) | 0/431 (0.00%) | 431 / 431 | 431 / 431 |
| 0.15 | M | 465/465 (100.00%) | 0/465 (0.00%) | 465/465 (100.00%) | 0/465 (0.00%) | 465 / 465 | 465 / 465 |
| 0.20 | S | 362/362 (100.00%) | 0/362 (0.00%) | 362/362 (100.00%) | 0/362 (0.00%) | 362 / 362 | 362 / 362 |
| 0.20 | M | 446/446 (100.00%) | 0/446 (0.00%) | 446/446 (100.00%) | 0/446 (0.00%) | 446 / 446 | 446 / 446 |
| 0.25 | S | 305/305 (100.00%) | 0/305 (0.00%) | 305/305 (100.00%) | 0/305 (0.00%) | 305 / 305 | 305 / 305 |
| 0.25 | M | 415/415 (100.00%) | 0/415 (0.00%) | 415/415 (100.00%) | 0/415 (0.00%) | 415 / 415 | 415 / 415 |

The three callbacks—preprocessing, motion, anomaly—have identical invocation/completion counts in each cell as shown. They are recording callbacks, not trained inference. Total accepted windows and authorized releases: **3,369**. Unauthorized releases: **0/3,369 tested windows**, also **0/3,840 attempts**. The **471** failed-session attempts produced no release. Refused attempts were not given synthetic protected windows; these are not thousands of adversarial-window trials. No universal replay/spoofing-security conclusion follows.

## Timing and Resource Measurements

| Observation | Actual value / scope |
| --- | --- |
| Full CLI workflow, including imports/controller completion | 404.994636 s |
| Supervised worker launch-to-exit, including finalization | 403.250000 s |
| Separate execution vs finalization split | Not separately instrumented; both included in combined workflow |
| Standalone audit / explicit analysis | 32.568265 s / 0.441669 s; post-run checking |
| Monitor samples / requested interval / maximum observed gap | 6,045 / 0.050 s / 0.094000 s |
| Peak sampled private / RSS / OS peak RSS | 1,683,345,408 / 450,351,104 / 473,579,520 bytes |
| Preflight available RAM / disk | 13,910,237,184 / 63,687,880,704 bytes |
| Last published available RAM / disk | 14,658,519,040 / 63,656,783,872 bytes |
| Final monitor available RAM / disk | 14,916,927,488 / 63,656,783,872 bytes |
| Sealed bundle / sidecars size | 28,781,930 / 143,259 logical bytes |
| Last monitored aggregate growth | 28,919,908 bytes; bundle plus supervisor sidecars |
| Resource violations / supervision | [] / verified=True |
| RAM/disk minima across all samples | Not retained; only latest snapshots/final counters are available |

Sampled maxima do not prove instantaneous private-memory peaks; private commitment differs from RSS. The OS peak working-set counter has its own lifetime semantics. No minimum host headroom is invented from last-snapshot values. Resource enforcement remained active throughout, including final controller acceptance. Operator report/CSV and post-audit outputs sit outside the sealed experiment bundle and are excluded from the supervisor’s bundle/sidecar growth totals.

Timing below pools sigma conditions for descriptive stage summaries only. Each cell is **span count / median / p95 milliseconds**. Successful-session strata condition on admission; rejected-attempt strata retain all source/refusal costs. There are 1,920 attempts per policy. Individual measurement/reading counts differ by actual one/three acquisition calls. Missing/inapplicable stages remain empty, not zero-latency measurements.

| Arm | Stage | All: n / median / p95 ms | Successful: n / median / p95 ms | Rejected: n / median / p95 ms |
| --- | --- | --- | --- | --- |
| S | establishment | 1920 / 3.055950 / 5.984675 | 1567 / 3.127700 / 6.133490 | 353 / 2.690200 / 5.275340 |
| S | acquisition | 1920 / 0.361000 / 0.478560 | 1567 / 0.360800 / 0.481740 | 353 / 0.361900 / 0.471780 |
| S | reading | 1920 / 0.350050 / 0.461825 | 1567 / 0.349900 / 0.462860 | 353 / 0.351100 / 0.455840 |
| S | measurement | 1920 / 0.104400 / 0.132405 | 1567 / 0.104500 / 0.132140 | 353 / 0.104000 / 0.133940 |
| S | voting | 0 / — / — | 0 / — / — | 0 / — / — |
| S | reconstruction | 1920 / 2.175150 / 4.920065 | 1567 / 2.174700 / 5.038130 | 353 / 2.175600 / 4.713440 |
| S | bch_decode | 1920 / 2.118450 / 4.847090 | 1567 / 2.111500 / 4.978470 | 353 / 2.124300 / 4.644040 |
| S | verification | 1570 / 0.040500 / 0.052200 | 1567 / 0.040500 / 0.052200 | 3 / 0.045200 / 0.046190 |
| S | authorization | 1570 / 0.055400 / 0.075255 | 1567 / 0.055400 / 0.075270 | 3 / 0.055000 / 0.057070 |
| S | mutual_handshake | 1567 / 0.329600 / 0.508160 | 1567 / 0.329600 / 0.508160 | 0 / — / — |
| S | first_window | 1567 / 9.210300 / 12.317920 | 1567 / 9.210300 / 12.317920 | 0 / — / — |
| S | window_verify | 1567 / 4.837000 / 6.654020 | 1567 / 4.837000 / 6.654020 | 0 / — / — |
| S | release | 1567 / 0.461100 / 0.663640 | 1567 / 0.461100 / 0.663640 | 0 / — / — |
| M | establishment | 1920 / 3.794150 / 6.763285 | 1802 / 3.822850 / 6.793585 | 118 / 3.162000 / 6.002600 |
| M | acquisition | 1920 / 1.038450 / 1.390265 | 1802 / 1.039300 / 1.395600 | 118 / 1.028350 / 1.332410 |
| M | reading | 5760 / 0.335100 / 0.444100 | 5406 / 0.335350 / 0.445125 | 354 / 0.332700 / 0.419700 |
| M | measurement | 5760 / 0.095400 / 0.127105 | 5406 / 0.095400 / 0.127275 | 354 / 0.094850 / 0.122445 |
| M | voting | 1920 / 0.044000 / 0.057000 | 1802 / 0.044000 / 0.057095 | 118 / 0.043850 / 0.054415 |
| M | reconstruction | 1920 / 2.125350 / 4.978795 | 1802 / 2.135100 / 4.999125 | 118 / 1.967350 / 4.675210 |
| M | bch_decode | 1920 / 2.069350 / 4.896985 | 1802 / 2.078200 / 4.918645 | 118 / 1.911900 / 4.611210 |
| M | verification | 1803 / 0.040800 / 0.052180 | 1802 / 0.040750 / 0.052190 | 1 / 0.043300 / 0.043300 |
| M | authorization | 1803 / 0.055700 / 0.075490 | 1802 / 0.055700 / 0.075495 | 1 / 0.052800 / 0.052800 |
| M | mutual_handshake | 1802 / 0.329850 / 0.513500 | 1802 / 0.329850 / 0.513500 | 0 / — / — |
| M | first_window | 1802 / 9.231150 / 12.035995 | 1802 / 9.231150 / 12.035995 | 0 / — / — |
| M | window_verify | 1802 / 4.853250 / 6.567310 | 1802 / 4.853250 / 6.567310 | 0 / — / — |
| M | release | 1802 / 0.461850 / 0.680570 | 1802 / 0.461850 / 0.680570 | 0 / — / — |

First-use decode observations, retained without trimming:

| Arm | First execution index | First decode ms | All decode median ms | Maximum decode ms |
| --- | --- | --- | --- | --- |
| S | 1 | 1.992200 | 2.118450 | 10.695900 |
| M | 0 | 2979.366700 | 2.069350 | 2979.366700 |

A slower first decode is consistent with first-use/JIT/cache effects; compilation duration/cause is not separately measured. No slow initial observation was removed. [stage-timings.csv](../results/week-9/will/calibration-restart-v1/restart-20261028-01/stage-timings.csv) covers every sigma/arm and all 22 available stages with all/success/rejected/C/D/I/W strata, actual eligible-call/span counts, inclusive mean/median/p95/maximum and exclusive mean/median/p95. There are 1,232 exported diagnostic rows, including empty retrieval stages.

Acquisition contains readings and voting; reading contains oscillator measurement plus additional reader work; reconstruction contains BCH; authorization contains verification. Establishment and first-window are separate directly measured roots with untimed work between. Inclusive spans overlap and are not summed. Separate p95 values are never added into an end-to-end latency. No recurring throughput or actual trained-SNN timing is claimed.

Setup/enrollment/helper encoding, verifier provisioning, fresh endpoints, shared-Z preparation, templates, instrumentation installation, row construction/schema validation, source hashing, evidence write/flush/fsync, validation replay, summary/bootstrap and reporting lie outside measured stage roots. They contribute to workflow time as applicable. No physical PUF/sensor acquisition, external transport, or trained model is measured.

## Reproducibility and Audit Receipts

| Receipt identity | SHA-256 / timestamp |
| --- | --- |
| Final manifest | 18998ac06762e6a77ce9406754e82b97767433f33b4a7774c9f1106fb961f7fa |
| Completion marker | 0fc4ab9ba7a736878a539a1d241a285847f5495bced22ab9d9f9931d4e71f62c |
| Selection-v2 | 7cd3f25b3abfe8472d38841f744134cf88981a5d2771a7cc9de4b15463e819c6 |
| Analysis | 4e7f2aba7eacb2852596e4f01b2cae2fcf723ee4df283b37d0cf82f6ed34bcc9 |
| Selection computation timestamp | 2026-10-29T01:16:59.417824+00:00 |
| Completion timestamp | 2026-10-29T01:17:43.405641+00:00 |

Preserved artifacts:

- [Sealed experiment bundle](../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318): exact config and canonical trial plan, metadata/approval, consumption receipt, all 116 required source snapshots, enrollment catalog, attempts.jsonl, summary/analysis, validation receipt, selection-v2, manifest and validated completion marker.
- [Supervisor sidecars](../tmp/week9-shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t011009z-restart-9384a318): request, periodic coordinated snapshots, actual monitoring result, worker result/progress, controller validation, stdout/stderr and compiler cache.
- [Consumed restart authorization](../results/week-9/will/shared-noise-calibration-authorizations-v2/restart-f64a0c5bcd5f496b8189e4dbd13a871d): consumption, launch, and completion lifecycle receipts; prior failed authorization remains separately consumed.
- [Restart operator receipts](../results/week-9/will/calibration-restart-v1/restart-20261028-01): committed-checkout verification, preservation inventory, fresh plan/preflight/resource checks, authorization basis/approval-v2, exactly-one invocation/process timing, coordinated status observations, standalone audit/process receipt, frozen post-completion analysis/receipt, research diagnostics, device CSV and detailed timing CSV.
- [Operator helper scripts](../tmp/week9-calibration-restart-20261028-01): reproducible preparation, authorization recording, one-shot CLI launch, coordinated status, post-completion checking/export and this report generator.

Local computational audit verifies exact archived source/current environment, complete closure, hashes, replay and recorded protocol invariants. It is distinct from independent experimental reproduction by another researcher. Public seeded simulator inputs can reconstruct synthetic credentials; local attestations are not cryptographic signatures or remote attestation. No historic manifest or old partial outcome was rewritten. This new report leaves the old interruption report intact and is outside the completed run’s required-source manifest.

## Interpretation and Scientific Limitations

The calibration identifies sigma=0.15 as an informative independent-noise operating point under the frozen screen. Its observed paired benefit is 7.083 pp, with a pointwise device-bootstrap interval [3.333, 11.250] pp. The interval’s positive lower bound supports a measurable reconstruction advantage under this simulation law at the selected setting. Device/group ranges and concentration above show the variability and influence retained by the analysis; passing the delete-device and group gates supports limited calibration robustness, not immunity to every population shift.

Selection uses the same data that produce these descriptive pointwise intervals; the selected point is not a confirmatory estimate from independent evaluation data. Twenty trials per device give discrete device rates; only 24 independently generated simulated devices and four groups are represented. Bootstrap approximation and unseen-event limitations remain, and manufacturing/noiseless-enrollment assumptions restrict external generalization.

No empirical correlation attenuation, binary-error correlation curve, monotonic rho response, physical-device reliability, cryptographic security bound, universal replay/spoofing resistance, trained SNN inference benefit, or deployment-latency attainment follows from rho=0 calibration. Recorded zero unauthorized release is finite implementation evidence with actual denominators. The simulation has a 32-bit credential and trusted co-located verifier assumptions; the recording consumer is a release probe.

## Preparation for Final Correlation Evaluation
The calibration task stops here. Final execution remains disabled, and researcher selection acknowledgment remains pending. The computed choice, if qualifying, needs a genuine separately dated acknowledgment bound to selection/analysis/evidence/manifest/completion identities; execution approval is not that acknowledgment.

Only after acknowledgment and separate design/resource review should a new final configuration hold the selected marginal sigma fixed across rho={0,.50,.90,1}, with disjoint w9f devices/seeds and prescribed nominal/common/stored controls. The .10 choice can permit the revised 90,000-attempt design; another selected sigma normally requires 108,000 attempts under the specification. Those are prospective designs, not executed workloads. Full-scale memory/finalization/storage qualification and separate final authorization are still required. A nonqualifying result instead requires a separately approved prospective amendment before any additional calibration. No final evaluation, new seed search, commit or push was performed.