# Week 9 — Shared-Noise PUF Calibration Results

Run ID: `week9-shared-noise-calibration-v1-20261029t003215z-d55070ef`. Evidence: [preserved incomplete bundle](../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t003215z-d55070ef). Authorization ID: `task2h-20261029t003215z-d55070ef`; consumed and unavailable for reuse. The required `CALIBRATION_VALIDATED.json` does **not** exist; `INCOMPLETE.json` remains.

The Windows supervisor failed while atomically replacing `worker/monitor.json` with `monitor.json.new`: `PermissionError: [WinError 5] Access is denied`. Containment terminated the worker.

## Research Objective

Select the lowest prespecified sigma that gives an informative independent-measurement-noise operating region for a later correlated-noise study of Majority-3 reconstruction. Calibration uses rho=0 only. This interrupted invocation cannot determine whether an informative operating point exists or whether Majority-3 has a population-level benefit. It supplies no empirical attenuation estimate.

## Faculty Feedback and Experimental Motivation

The preserved [study specification](week9-shared-noise-study-specification.md), [readiness report](week9-shared-noise-calibration-readiness.md), [Week 8 methodology](week8-three-arm-auth-methodology.md), [archived methodology review](archive/week8-three-arm-formal-methodology-review-v1.md), [feedback consolidation](week6-feedback-consolidation.md), and relevant entries in [Will’s research log](research-logs/will.md) were reviewed. These repository records are the feedback basis; original faculty correspondence was not located in the connected-mail search. No faculty signature, direct quotation, or newly verified faculty approval is invented.

Independent-read calibration avoids selecting an operating point using later correlation outcomes. The earlier nominal/correlation all-success cells could obscure attenuation through a floor effect. The current design uses neutral two-sided estimation, device clusters, fixed marginal noise in the future rho comparison, separate reconstruction and authentication endpoints, and explicit timing boundaries. Historical prose marked “proposed” or “not implemented” describes earlier design stages; the current validated implementation and appendix/readiness contracts govern this invocation. Frozen proposal-status labels were retained; the user’s explicit instruction supplies bounded operator authority.

| Feedback / guidance | Treatment in this invocation | Status / scope |
| --- | --- | --- |
| Independent reference before correlation | Frozen rho=0 four-sigma schedule launched once | Interrupted; no calibration conclusion |
| Separate calibration/final data | Calibration master 2026102801 and w9c IDs; final master 2026102811 and w9f IDs remain reserved | No final data generated |
| Hold marginal noise fixed as rho varies | Noise law unchanged; later final design must hold selected sigma fixed | Future final-study requirement |
| C/D/I/W and verifier outcomes | Partial categories and actual verifier reach/refusal in section 11 | Diagnostics, not certified scientific estimates |
| Denominators and timing boundaries | Partial attempt/call/session/window denominators stated; observed spans preserved | No invented end-to-end latency |
| Reproducibility | Source snapshot comparison and persisted-prefix checks | Computational checks; no independent researcher reproduction |
| Calibration resource observations | Published and failed-replacement monitor records retained separately | No completed resource acceptance |
| Week 8 three-arm / quality / trained-model evidence | Existing Week 8 and Week 9 reports cited below | Separate experiments; not rerun or pooled |

Existing [Week 9 evidence feasibility](week9-evidence-feasibility.md), [three-arm results](week9-three-arm-results.md), [Week 8 quality validation](week8-keegan-validation.md), and [quality equivalence](week8-quality-equivalence.md) retain the earlier three-arm, quality-check, and trained-model findings. The present recording consumer does not run trained SNN inference. Physical/Quest validation, historical provenance questions, external reproduction, warmed model timing, and full-scale resource qualification remain separate work.

## Exact Experimental Configuration

| Parameter | Frozen plan | Recorded before interruption |
| --- | --- | --- |
| Groups / devices per group / devices | 4 / 6 / 24 | 4 groups / 24 observed devices; 24 enrolled |
| Trials per device per sigma | 20 | Incomplete; no completed 20-trial cohort claim |
| Sigma / rho / common offset | 0.10, 0.15, 0.20, 0.25 / 0 / 0 | All four conditions present; none complete |
| Policies | Single-Read / Majority-3 | 272 / 271 persisted attempts |
| Matched trial identities | 1,920 | 272; 271 complete pairs + 1 unpaired identity |
| Policy attempts | 3,840 | 543 completed and persisted |
| Experimental PUF readings | 7,680 | 1,085 in persisted attempts |
| Runtime BCH decodes | 3,840 | 543 in persisted attempts |
| Majority votes | 1,920 | 271 in persisted attempts |
| Enrollment reference readings | 24 | 24; setup, not policy samples |
| Bootstrap resamples | 10,000 paired whole-device draws | 0; incomplete scientific cohort |
| Two-pass additional reads / decodes / references | 15,360 / 7,680 / 48 | 0 / 0 / 0; finalization not reached |

BCH(63,36,t=5), 32-bit credentials with four fixed padding bits, the first 63 of 64 PUF bits, adjacent oscillator pairing over 128 oscillators, independent verification, admission, Authentication-v2, a stationary 120-sample sequence-zero window, and `recording-consumer-v1` were unchanged. Each complete candidate would have 480 observations per policy. This report does not use 480 as a denominator for incomplete observations.

## Noise Model and Randomization

The unchanged model is:

```text
f(d,a,i,r) = 100 + M(d,i) + C(d,a)
           + sigma*sqrt(rho)*Z(d,a,i)
           + sigma*sqrt(1-rho)*E(d,a,i,r)
```

Manufacturing SD=1; enrollment is noiseless; rho=0 and C=0 throughout calibration. Sigma is in abstract additive frequency units. Each device retains its independently generated manufacturing realization across sigma conditions; sigma-specific domains remain separate. S/M share indexed reading zero while Majority-3 invokes three actual readings. The frozen alternating policy order and shuffled whole matched blocks were preserved. No failed authentication was discarded or retried, and no device was regenerated in response to its result.

Calibration seed roots are master 2026102801, schedule 2026102802, bootstrap 2026102803, and group sensitivity 2026102804. Final roots 2026102811–2026102814 and `w9f` populations are disjoint from calibration’s `w9c` populations and phase domains. The unused group-bootstrap root does not imply a performed group bootstrap. All 271 persisted complete pairs have identical stored first-reading observations; this check is not a deterministic measurement replay.

## Execution Environment and Frozen Identities

| Identity | Exact value |
| --- | --- |
| config_sha256 | `79a275d06a8a1997981484f15d27cb5e76b39fd2a28b660a4251ddc35e83e756` |
| environment_sha256 | `6ef3b0cf006b693d9e8622044e7bd833299773c11b7276298a55caec713d2174` |
| plan_sha256 | `e5d4deaf8b944dd514fbdcf2bba31cd91ec5dc22e66478ca8a55701a594135ff` |
| source_id | `8d4c187508ac847532b4bbdbd34267f7e14d622ac46131d31fcf8a590df790cc` |
| specification_sha256 | `f5a12c19e9228860b901e9abb0eee4c16aa4dbaa785bbea32fa4b5e31b244b23` |

Interpreter: `C:\PUF+SNN_SharedRepo\PUF-SNN\.venv\Scripts\python.exe`; CPython 3.12.4 (tags/v3.12.4:8e8a4ba, Jun  6 2024, 19:30:16) [MSC v.1940 64 bit (AMD64)]. OS: `Windows-11-10.0.26200-SP0`. CPU: `Intel64 Family 6 Model 151 Stepping 2, GenuineIntel`, 20 logical cores; host RAM 34,191,159,296 bytes. Package versions: galois=0.4.11, jsonschema=4.26.0, numba=0.67.0, numpy=2.5.3, scipy=1.18.1.

Git base: `cd63fc466cc5ac7bd9d535cd57594fedf1875410`; branch `main`. A pre-existing edit to `docs/research-logs/will.md` was left untouched. Exact frozen file hashes, rather than Git base alone, identify this run. The 114 required files and their bundled copies match the current source. The results report is outside that required source set.

The sandbox initially could not access the venv’s base interpreter. The same native interpreter succeeded outside the sandbox without installation, relocation, environment repair, or substituting MSYS Python. Fresh read-only `plan` and `preflight` passed. Config and plan digests match the previous baseline; the documented naming cleanup changed only the hashed specification and readiness Markdown relative to the prior test receipt.

The 182-test baseline passed: 65 calibration/authorization tests (41.733 s), 55 resource-supervisor tests (5.364 s), and 62 noise/planning/runtime tests (12.710 s), with zero test failures, errors, or skips in the completed suites. An operator receipt helper initially omitted the repository root from its Python import path; its resource-test import failed before executing that suite. The correction changed only the helper, and both original error and corrected pass are retained. Fixture executions are not scientific samples.

Approved by Will Wallace under the actual user instruction, recorded `2026-10-29T00:32:40.845329+00:00` (October 28, 20:32:40 EDT), with no faculty attribution. Authorization was consumed `2026-10-29T00:32:50.078481+00:00`. Exact source, specification, config, plan, environment, output, run, resource budget, and rules identities are bound by approval-v2. Selection acknowledgment is pending.

The cold-process, zero-harness-warmup profile was preserved. The scientific worker uses the existing run-specific compiler-cache directory and `PYTHONDONTWRITEBYTECODE=1`. NUMBA_DISABLE_JIT, NUMBA_NUM_THREADS, OMP_NUM_THREADS, MKL_NUM_THREADS, and OPENBLAS_NUM_THREADS were unset in recorded operator context; no power-plan or background-load control was changed. A new worker/cache location does not prove absence of every system/package cache or first-use setup effect.

## Experimental Completion and Evidence Validation

**Not complete.** Planned attempts: 3,840. Persisted attempts: 543; every persisted row records completed status and no per-attempt fault. At least 543 attempts started; the serial worker may have started attempt 544. Its completion/operations were not durably journaled. Exact total started and total completed counts beyond persisted evidence are unknown. Reported readings/decodes/votes are recorded-operation counts and may exclude unpersisted in-flight work.

The ledger is a valid contiguous scheduled prefix (execution indices 0–542) with no duplicate persisted identity. Schema, recorded protocol invariants, and timing containment passed for those rows; all frozen source snapshot hashes matched. These limited checks do **not** establish full-cohort semantic reconciliation or certify an incomplete bundle.

Last durable scientific attempt: index `542`, `s010`, `single-read-v1`, device `w9c-p002-d02`; policy-attempt SHA-256 `dd36f2494ba2e031e3bc15db6e6e932a52384c7be91a7ceb4447bc3690498015`. The next scheduled row’s execution is unconfirmed. Last recorded supervisor operation was sampling followed by the failed monitor-file replacement.

No `summary.json`, `validation.json`, `selection.json`, `manifest.json`, or completion marker was produced. Neither reconciliation pass ran. The independent standalone full-evidence audit was not invoked because its complete-bundle prerequisites are absent. A later audit would add verification work, not samples; no such completed audit is claimed. The original sentinel still states `not-finalized` and `interrupted_work: unknown`; it was not rewritten to manufacture a receipt.

## Four-Sigma Reliability Results

No complete-cohort rates or paired effects are available. The required primary table explicitly records missing results. It uses no historical or fixture estimates.

| Sigma | Single FRR | Majority-3 FRR | Delta | 95% CI for Delta | Qualifies |
| --- | --- | --- | --- | --- | --- |
| 0.10 | Unavailable | Unavailable | Unavailable | Not computed | Not assessed: incomplete |
| 0.15 | Unavailable | Unavailable | Unavailable | Not computed | Not assessed: incomplete |
| 0.20 | Unavailable | Unavailable | Unavailable | Not computed | Not assessed: incomplete |
| 0.25 | Unavailable | Unavailable | Unavailable | Not computed | Not assessed: incomplete |

Diagnostic coverage only:

| Sigma | Persisted S / planned S | Persisted M / planned M |
| --- | --- | --- |
| 0.10 | 68/480 | 67/480 |
| 0.15 | 71/480 | 71/480 |
| 0.20 | 73/480 | 73/480 |
| 0.25 | 60/480 | 60/480 |

## Paired Bootstrap Confidence Intervals

Not computed. The frozen estimator requires 10,000 paired whole-device multiplicity draws shared across all four sigma conditions, with every device’s complete trials and both outcomes retained. That cohort is missing. The 271 complete partial pairs are not a substitute. No unpaired, attempt-binomial, historical, zero-filled, or truncated confidence intervals are substituted. No zero-event conclusion or degenerate interval is reported from the partial ledger.

## Device and Population-Group Heterogeneity

All 24 enrolled devices and four groups occur in the partial prefix, but trial coverage is incomplete and unequal. Device/group FRR distributions, failure concentration, discordance spread, leave-one-device-out and leave-one-group-out effects, and selection robustness are not assessed. Seeing every device does not complete its 20 trials at each sigma. Persistent-device dependence remains; 543 attempts and 1,085 readings are not independent device samples. No sensitivity conclusion is inferred from partial data.

## Operating-Point Selection

**Selection prohibited: incomplete calibration.** This is different from a certified “no qualifying operating point” result. The frozen algorithm would choose the lowest sigma passing every gate; it was not executed against an incomplete cohort.

| Sigma | Coverage / infrastructure gate | All numerical / uncertainty / heterogeneity gates | Candidate decision |
| --- | --- | --- | --- |
| 0.10 | Not satisfied: incomplete run; supervisor fault | Not assessed | Selection prohibited |
| 0.15 | Not satisfied: incomplete run; supervisor fault | Not assessed | Selection prohibited |
| 0.20 | Not satisfied: incomplete run; supervisor fault | Not assessed | Selection prohibited |
| 0.25 | Not satisfied: incomplete run; supervisor fault | Not assessed | Selection prohibited |

The unchanged numerical contract requires 0.05 ≤ S FRR ≤ 0.70, ≥24 S failures and ≥24 S correct; M FRR ≤0.50; Delta ≥0.02; ≥20 discordances across ≥6 devices and ≥3 groups; S failures across ≥6 devices and ≥3 groups; S interval lower ≥0.01 and upper ≤0.85; Delta interval lower **>0** and full width ≤0.20; every device deletion Delta ≥0.01; at least three group benefits **>0** and every group benefit ≥−0.02. Gates use unrounded values with inclusive bounds except the explicit strict comparisons. No thresholds, seeds, sample counts, or budgets were adjusted after interruption. No selection-v2 receipt or acknowledgment was fabricated.

## Reconstruction and Authentication Failure Accounting

The following are **uncertified partial-ledger diagnostics**, not completed-calibration FRRs. C/D/I/W partition each row’s persisted attempts. Each cell’s actual `n` is its denominator; missing scheduled attempts are not successes, failures, or synthetic zeros.

| Sigma | Arm | n | C | D | I | W |
| --- | --- | --- | --- | --- | --- | --- |
| 0.10 | S | 68 | 67 | 1 | 0 | 0 |
| 0.10 | M | 67 | 67 | 0 | 0 | 0 |
| 0.15 | S | 71 | 66 | 5 | 0 | 0 |
| 0.15 | M | 71 | 68 | 2 | 1 | 0 |
| 0.20 | S | 73 | 52 | 20 | 0 | 1 |
| 0.20 | M | 73 | 71 | 2 | 0 | 0 |
| 0.25 | S | 60 | 39 | 21 | 0 | 0 |
| 0.25 | M | 60 | 53 | 7 | 0 | 0 |

Counts and denominators for the independently observed downstream stages:

| Sigma | Arm | Verifier calls / n | Verified / calls | Refused / calls | Not reached / n | Admissions / n | Sessions / n |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.10 | S | 67/68 (98.53%) | 67/67 (100.00%) | 0/67 (0.00%) | 1/68 (1.47%) | 67/68 (98.53%) | 67/68 (98.53%) |
| 0.10 | M | 67/67 (100.00%) | 67/67 (100.00%) | 0/67 (0.00%) | 0/67 (0.00%) | 67/67 (100.00%) | 67/67 (100.00%) |
| 0.15 | S | 66/71 (92.96%) | 66/66 (100.00%) | 0/66 (0.00%) | 5/71 (7.04%) | 66/71 (92.96%) | 66/71 (92.96%) |
| 0.15 | M | 68/71 (95.77%) | 68/68 (100.00%) | 0/68 (0.00%) | 3/71 (4.23%) | 68/71 (95.77%) | 68/71 (95.77%) |
| 0.20 | S | 53/73 (72.60%) | 52/53 (98.11%) | 1/53 (1.89%) | 20/73 (27.40%) | 52/73 (71.23%) | 52/73 (71.23%) |
| 0.20 | M | 71/73 (97.26%) | 71/71 (100.00%) | 0/71 (0.00%) | 2/73 (2.74%) | 71/73 (97.26%) | 71/73 (97.26%) |
| 0.25 | S | 39/60 (65.00%) | 39/39 (100.00%) | 0/39 (0.00%) | 21/60 (35.00%) | 39/60 (65.00%) | 39/60 (65.00%) |
| 0.25 | M | 53/60 (88.33%) | 53/53 (100.00%) | 0/53 (0.00%) | 7/60 (11.67%) | 53/60 (88.33%) | 53/60 (88.33%) |

D/I did not reach independent verification; this is distinct from an explicit verifier refusal. The sole W candidate is sigma=.20, S, execution index 326: `credential_mismatch`, session inactive, zero releases. It was refused before session establishment. A format-valid/BCH-valid candidate is not necessarily authenticated. All actual successful verifications produced admissions and completed sessions in the persisted prefix; conditional admission/verification and session/admission rates are 100% with each cell’s verified/admitted count as denominator. There were no observed disabled-policy refusals.

| Sigma | Arm | Accepted / tested windows | Rejected / tested windows | Authorized releases / sessions | Unauthorized releases / tested windows | Release entry / complete | Each recording callback invoke / complete |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.10 | S | 67/67 (100.00%) | 0/67 (0.00%) | 67/67 (100.00%) | 0/67 (0.00%) | 67 / 67 | 67 / 67 |
| 0.10 | M | 67/67 (100.00%) | 0/67 (0.00%) | 67/67 (100.00%) | 0/67 (0.00%) | 67 / 67 | 67 / 67 |
| 0.15 | S | 66/66 (100.00%) | 0/66 (0.00%) | 66/66 (100.00%) | 0/66 (0.00%) | 66 / 66 | 66 / 66 |
| 0.15 | M | 68/68 (100.00%) | 0/68 (0.00%) | 68/68 (100.00%) | 0/68 (0.00%) | 68 / 68 | 68 / 68 |
| 0.20 | S | 52/52 (100.00%) | 0/52 (0.00%) | 52/52 (100.00%) | 0/52 (0.00%) | 52 / 52 | 52 / 52 |
| 0.20 | M | 71/71 (100.00%) | 0/71 (0.00%) | 71/71 (100.00%) | 0/71 (0.00%) | 71 / 71 | 71 / 71 |
| 0.25 | S | 39/39 (100.00%) | 0/39 (0.00%) | 39/39 (100.00%) | 0/39 (0.00%) | 39 / 39 | 39 / 39 |
| 0.25 | M | 53/53 (100.00%) | 0/53 (0.00%) | 53/53 (100.00%) | 0/53 (0.00%) | 53 / 53 | 53 / 53 |

All three callbacks—preprocessing, motion, anomaly—have identical per-cell invocation/completion counts shown above; each count equals accepted windows in that cell. These are recording callbacks, not trained-model inference. Totals: 483 correct reconstructions/543 persisted attempts; 484 verifier calls, 1 refusal, 483 verified credentials/admissions/sessions/accepted windows/authorized releases; 0 unauthorized releases/483 tested accepted-window opportunities. There are 60 observed rejected attempts, including the W refusal, with 0 releases. Refused attempts did not receive constructed protected windows, so those counts do not represent a separate adversarial-window test suite. No universal replay/spoofing resistance is inferred.

## Timing and Resource Measurements

All timings below are partial observations, conditional on the preserved prefix. No finalization-complete workflow time exists. The launch lifecycle timestamp to failure lifecycle timestamp is 53.901847 seconds; this wall-timestamp interval includes launch/monitor work and exception cleanup and is not a separately instrumented scientific execution root. The monitor’s last published monotonic elapsed observation is 53.813000 seconds; its failed-replacement candidate reaches 53.875000 seconds. There is no final monitor/controller acceptance, completed worker receipt, or separately measured finalization duration.

Frozen limits: 1,800 s workflow/session, process-memory stop at 4 GiB, free host RAM strictly >8 GiB, free disk strictly >1 GiB, bundle growth <512 MiB, aggregate growth <1 GiB, requested 0.05 s sampling, and 2 s stop grace. All remained enabled. No numeric violation appears in either retained monitor record; a monitor I/O exception prevents certifying uninterrupted availability or final budget acceptance.

| Observation | Actual value / boundary |
| --- | --- |
| Initial free RAM / disk | 15,913,754,624 / 63,073,693,696 bytes (14.821 GiB / 58.742 GiB) |
| Published samples / candidate sample | 828 / 829 (the candidate was not atomically published) |
| Published peak RSS / OS peak RSS | 274,165,760 / 274,165,760 bytes |
| Candidate peak RSS / OS peak RSS | 274,214,912 / 274,214,912 bytes |
| Sampled peak private commitment | 1,505,013,760 bytes (1.402 GiB); same in candidate |
| Last published free RAM / disk | 16,516,366,336 / 63,066,927,104 bytes |
| Candidate free RAM / disk | 16,513,015,808 / 63,066,927,104 bytes |
| Last published / candidate aggregate growth | 7,205,372 / 7,205,383 bytes |
| Preserved bundle / sidecars after interruption | 7,074,599 / 138,775 logical bytes |
| Resource violations | None recorded; infrastructure PermissionError terminated monitoring |
| RAM/disk minima; maximum sampling gap | Not retained as history/minima; final result with maximum-gap field was never produced |

Private commitment is different from resident working set. Sampled maxima do not guarantee instantaneous private-memory peaks; the OS peak working-set counter has its own semantics. Only latest monitor snapshots, not every RAM/disk sample, survive. No minimum host headroom or exact effective monitoring interval is invented.

The table below pools sigma conditions solely to summarize partial timing operations. `n / median / p95` uses actual span counts and milliseconds. Successful and rejected strata condition on observed session outcome. Policy counts are S=272 and M=271; reading/measurement spans can number three per M attempt. Inclusive stages nest and must not be summed. Missing stages are shown as `0 / — / —`.

| Arm | Span | All: n / median / p95 ms | Successful: n / median / p95 ms | Rejected: n / median / p95 ms |
| --- | --- | --- | --- | --- |
| S | establishment | 272 / 3.052550 / 5.700005 | 224 / 3.129150 / 5.729165 | 48 / 3.009750 / 5.581060 |
| S | acquisition | 272 / 0.360100 / 0.461465 | 224 / 0.359500 / 0.457720 | 48 / 0.364050 / 0.479660 |
| S | reading | 272 / 0.348900 / 0.446620 | 224 / 0.347800 / 0.443185 | 48 / 0.353350 / 0.463375 |
| S | measurement | 272 / 0.103400 / 0.129870 | 224 / 0.103250 / 0.129295 | 48 / 0.105450 / 0.129990 |
| S | voting | 0 / — / — | 0 / — / — | 0 / — / — |
| S | reconstruction | 272 / 2.230950 / 4.851170 | 224 / 2.192300 / 4.722565 | 48 / 2.413050 / 5.033865 |
| S | bch_decode | 272 / 2.170850 / 4.786440 | 224 / 2.122350 / 4.667250 | 48 / 2.326600 / 4.973460 |
| S | verification | 225 / 0.040400 / 0.054320 | 224 / 0.040400 / 0.054340 | 1 / 0.043300 / 0.043300 |
| S | authorization | 225 / 0.055000 / 0.075780 | 224 / 0.055050 / 0.075835 | 1 / 0.052600 / 0.052600 |
| S | mutual_handshake | 224 / 0.328750 / 0.520505 | 224 / 0.328750 / 0.520505 | 0 / — / — |
| S | first_window | 224 / 9.204650 / 12.811145 | 224 / 9.204650 / 12.811145 | 0 / — / — |
| S | window_verify | 224 / 4.848150 / 6.429365 | 224 / 4.848150 / 6.429365 | 0 / — / — |
| S | release | 224 / 0.459300 / 0.630810 | 224 / 0.459300 / 0.630810 | 0 / — / — |
| M | establishment | 271 / 3.858800 / 7.026200 | 259 / 3.861100 / 7.028790 | 12 / 3.601350 / 6.393535 |
| M | acquisition | 271 / 1.039700 / 1.352000 | 259 / 1.038500 / 1.342960 | 12 / 1.068250 / 1.489730 |
| M | reading | 813 / 0.333000 / 0.437040 | 777 / 0.331100 / 0.427920 | 36 / 0.347400 / 0.464775 |
| M | measurement | 813 / 0.095000 / 0.124520 | 777 / 0.094900 / 0.123820 | 36 / 0.096800 / 0.132350 |
| M | voting | 271 / 0.044300 / 0.055350 | 259 / 0.044300 / 0.055200 | 12 / 0.044200 / 0.056140 |
| M | reconstruction | 271 / 2.250300 / 5.375400 | 259 / 2.250300 / 5.451020 | 12 / 2.358150 / 5.009820 |
| M | bch_decode | 271 / 2.189500 / 5.317850 | 259 / 2.189500 / 5.393120 | 12 / 2.302350 / 4.949860 |
| M | verification | 259 / 0.040500 / 0.052420 | 259 / 0.040500 / 0.052420 | 0 / — / — |
| M | authorization | 259 / 0.055600 / 0.074710 | 259 / 0.055600 / 0.074710 | 0 / — / — |
| M | mutual_handshake | 259 / 0.330400 / 0.511820 | 259 / 0.330400 / 0.511820 | 0 / — / — |
| M | first_window | 259 / 9.156800 / 12.619350 | 259 / 9.156800 / 12.619350 | 0 / — / — |
| M | window_verify | 259 / 4.860500 / 6.948450 | 259 / 4.860500 / 6.948450 | 0 / — / — |
| M | release | 259 / 0.454900 / 0.796380 | 259 / 0.454900 / 0.796380 | 0 / — / — |

First decode observations were retained, without trimming:

| Arm | First execution index | First decode ms | Partial decode median ms | Partial decode maximum ms |
| --- | --- | --- | --- | --- |
| S | 1 | 2.403500 | 2.170850 | 21.983200 |
| M | 0 | 3089.229700 | 2.189500 | 3089.229700 |

A slower first use is consistent with initialization/JIT/cache effects but no separate compilation span measures the cause or its exact share. The worker had zero harness warmups; prior test processes are separate and not substituted for scientific observations.

[partial-stage-timings.csv](../results/week-9/will/shared-noise-calibration-task2h-v1/task2h-20261028-01/partial-stage-timings.csv) contains all 22 available stage names for every sigma/arm, with all-attempt, successful-session, rejected-attempt, and C/D/I/W strata; actual attempt and eligible-call/span counts; mean, median, p95 and maximum inclusive durations; and mean/median/p95 exclusive durations. Empty/inapplicable cells stay empty. This includes admission requests, HKDF, confirmation, activation, sealing and unused retrieval. [interrupted-diagnostics.json](../results/week-9/will/shared-noise-calibration-task2h-v1/task2h-20261028-01/interrupted-diagnostics.json) preserves first-use and aggregate details. These are diagnostics, not bootstrapped timing inference.

Acquisition contains readings and voting; reading includes more than oscillator `measurement`; reconstruction contains BCH decode; authorization contains independent verification. Establishment and first-window are separately timed roots with untimed work between them. No sum of separate p95s or fresh-attempt-to-release end-to-end latency is claimed. Setup/enrollment/helper encoding, verifier preparation, endpoints, shared-Z preparation, templates, instrumentation installation, source hashing, row creation/schema validation, JSONL write/flush/fsync, replay, bootstrap/statistical analysis, and reporting lie outside measured roots. No trained SNN, physical sensor/PUF, external network, or recurring throughput is timed here.

## Reproducibility and Audit Receipts

Primary preserved locations:

- [Incomplete scientific evidence directory](../results/week-9/will/shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t003215z-d55070ef): `config.json`, `trial-plan.json`, `metadata.json`, `source-manifest.json`, all 114 source snapshots, `enrollments.json`, `authorization-consumption.json`, `attempts.jsonl`, `INCOMPLETE.json`.
- [Supervisor sidecars](../tmp/week9-shared-noise-calibration-v1/week9-shared-noise-calibration-v1-20261029t003215z-d55070ef): `request.json`; worker `monitor.json`, `monitor.json.new`, `controller-error.json`, `progress.json`, stdout/stderr, and compiler cache. No monitor-result or worker-result was produced.
- [Consumed authorization reservation](../results/week-9/will/shared-noise-calibration-authorizations-v2/task2h-20261029t003215z-d55070ef): `consumption.json`, `launch.json`, `failure.json`; all retained and consumed.
- [Task 2H operator receipts](../results/week-9/will/shared-noise-calibration-task2h-v1/task2h-20261028-01): fresh `plan.json`, `preflight.json`, `source-freeze.json`, baseline comparison, all test logs/receipts including the operator import error and correction, `resource-availability.json`, `preexecution-checks.json`, `authorization-basis.json`, `approval-v2.json`, execution stdout/stderr, interruption diagnostics, SHA-256 inventory, and partial timing CSV.
- [Operator helper scripts](../tmp/week9-task2h-20261028-01): preexecution, correction, authorization recording, interruption accounting, and report generation. These are outside the frozen scientific source set and do not change the runner.

The snapshot hash inventory [interrupted-artifact-hashes.json](../results/week-9/will/shared-noise-calibration-task2h-v1/task2h-20261028-01/interrupted-artifact-hashes.json) records preserved evidence, sidecar and authorization files without writing inside them. It is an interruption inventory, **not** a substitute experiment manifest or validation marker. The consumption receipt’s integrity checks passed; all required current and bundled source hashes matched; no config/environment/plan mismatch was detected. No full two-pass or independent evidence audit passed. Computational prefix/hash checks by this agent are not independent experimental reproduction by another researcher.

No historical evidence was modified, deleted, resealed, or relabeled. No data was copied into a final-study namespace. No dependency was installed and no scientific source was modified. This report and external operator artifacts are not required frozen-manifest source files.

## Interpretation and Scientific Limitations

This invocation demonstrates a fail-closed interruption during monitoring I/O, with preserved observations and consumed authorization. It does not complete calibration, establish a qualifying sigma, estimate the full matched reliability benefit, characterize complete device/group heterogeneity, or resolve influence sensitivity. There is no estimate of correlation attenuation from rho=0 alone.

Partial C/D/I/W and verifier diagnostics show the sole recorded wrong candidate was refused before a session, and no unauthorized release appears in recorded attempts. Unrecorded in-flight work remains unknown. These finite observations do not establish universal protocol, replay, spoofing, hardware, PRNG, or secret-custody security. Recording callbacks are not trained SNN inference. The 32-bit synthetic credential and trusted-process verifier retain their documented limitations.

The likely availability hazard is concurrent access to a Windows file that the monitor replaces atomically; exact lock ownership was not captured. The scientific implementation is deliberately unchanged. The original readiness history already documents a different transient Windows replacement-sharing failure in a stub fixture; that prior passing rerun did not guarantee availability of this scientific invocation. No attempt was made to repair or rerun the scientific process after interruption.

## Preparation for Final Correlation Evaluation

Final evaluation remains disabled. There is no selected sigma, computational selection receipt, or researcher acknowledgment. The next work is to review the monitoring I/O interruption prospectively and decide whether another calibration is warranted. A restart requires a new explicit approval-v2 authorization, unique run/output, the consumed authorization recorded as `previous_failed_authorization_id`, and an honest restart reason. The preserved partial bundle and receipts must remain intact. This report grants no restart authority and launches none.

Any prerequisite implementation/environment change must be separately reviewed, tested, frozen and authorized before a new scientific invocation; this task did not make one. A compatible operator status reader should permit Windows delete/rename sharing and avoid blocking supervisor publication. Thresholds and seeds must not be changed to obtain favorable outcomes.

Only a later complete, independently audited calibration could support the frozen lowest-qualifying selection; acknowledgment must remain separate and supplied by an actual authorized researcher. Subsequent final-study planning would require its new frozen design, fixed marginal selected sigma across rho={0,.50,.90,1}, disjoint devices/seeds, appropriate nominal/common/stored controls, full-scale resource qualification, and separate authorization. Neither the 90,000 nor 108,000-attempt final evaluation was launched.
