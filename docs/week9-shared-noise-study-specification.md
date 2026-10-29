# Week 9: Shared-Noise Study Specification and Calibration Readiness

**Owner:** Will Wallace  
**Week:** 9
**Status:** Complete
**Date:** 10/28/26

The reviewed checkout was `457050b5361389364fbded464455f1f8684dbe5a`.

## Research Objective and Hypothesis-Neutral Question
Measure how Majority-3's correct-credential reconstruction benefit changes as within-attempt oscillator disturbance becomes more correlated, while holding the per-reading marginal measurement-noise distribution fixed. Independent readings (`rho = 0`) are the reference. A decrease, no detected change, or increase in benefit are all admissible findings; no monotonicity or positive attenuation is
assumed.

For acquisition policy S (Single-Read) or M (Majority-3), define reconstruction failure as any result other than the **correct enrolled credential**:

```text
FRR_policy(sigma,rho) = P(D or I or W | policy,sigma,rho)
Delta(sigma,rho) = FRR_S(sigma,rho) - FRR_M(sigma,rho)
A(sigma,rho) = Delta(sigma,0) - Delta(sigma,rho)
```

Positive Delta means a reconstruction benefit. Positive A means attenuation; zero means no measured change, and negative A means increased benefit. Report estimates and two-sided intervals without truncating negative values. Designate `A(sigma*,0.90)` as the principal correlation contrast, with the complete Delta curve, A at 0.50, and the rho=1 boundary reported alongside it. Here `sigma*` is selected using independent-read calibration only and frozen before evaluation. At rho=0, A=0 by definition, not an independently estimated treatment effect.

The target is the expectation over newly generated devices and repeated trials under this **specified simulation law**, conditional on noiseless enrollment, fixed manufacturing SD, code, and acquisition/protocol versions. It is not a physical-device, human-population, or cryptographic-security claim. Completed authenticated sessions are a separate downstream endpoint.

## Existing Evidence and Limitations
The requested `docs/week9-evidence-feasibility-reproduction.md` does not exist in this checkout. The relevant available consolidated report is
[week9-evidence-feasibility.md](week9-evidence-feasibility.md); the separately named [bounded reproduction note](week9-bounded-reproduction.md) concerns detector-table replay, not shared-noise experimental reproduction. No missing document's contents are inferred.

| Evidence inspected | What it supports | What it does not supply |
| --- | --- | --- |
| [Week 6 reconstruction alternatives](week6-reconstruction-alternatives-experiment.md), [configuration](../configs/reconstruction_alternatives_v1.json) | Reported formal 120 devices/20 groups; 6,000 attempts per arm-condition. Single/majority-3 FRR: 59/6,000 vs 6/6,000 at .10; 2,133/6,000 vs 579/6,000 at .25. | A correlated-noise curve, or a choice of the new operating point. These are historical standalone reconstruction results, not new integrated sessions. |
| [Week 7 nonformal record](week7-majority3-auth-correlated-harness-validation.md) and its preserved completion marker | One device; 50 matched cells, 100 attempts, 200 readings; S/M correct reconstructions 47/50 and 50/50. All three failures were S under independent stress. | Population/device-generalized inference; recording callbacks are not models. |
| [Week 9 analysis of October 20 evidence](week9-three-arm-results.md), preserved Week 8 bundle | One device; 150 attempts, 50 matched cells. S/M/stored sessions 41/50, 45/50, 50/50. Stress reconstruction failures 9/10 vs 5/10; other PUF cells zero failures. One valid-format wrong S credential was independently refused. | An informative sigma=.10 attenuation estimate, a precision guarantee, trained-model timing, or independent experimental reproduction. |
| [Week 8 methodology](week8-three-arm-auth-methodology.md), [archived formal review](archive/week8-three-arm-formal-methodology-review-v1.md) | Matching, C/D/I/W accounting, timing/evidence boundaries, candidate population bootstrap, and unresolved formal gates. | Implemented three-arm inferential analysis or an approved quantitative calibration rule. |
| [Faculty memo](faculty-decision-memo.md), [feedback consolidation](week6-feedback-consolidation.md), [Will's log](research-logs/will.md) | Prior decision context, independent-read reliability motivation, and proposed operating-region reasoning. | Approval of the defaults in section 5 or formal execution. |
| [Week 9 feasibility report](week9-evidence-feasibility.md), [resource plan](archive/week8-three-arm-formal-resource-feasibility-plan-v1.md) | Pilot-scale workflow/storage observations and source-derived scaling risks. | A qualified full-scale completion time or peak-memory guarantee. |

The old five conditions are .10/rho0 nominal, .25/rho0 stress, .10/rho0 common control, and .10/rho.50/.90 differential conditions. The old design varies sigma between nominal and stress, but correlation only at .10. It cannot measure the new correlation question at a calibrated sigma unless that sigma happens to be .10. Week 6's population average and the later one-device outcomes differ in devices, seed identities, and workload. Do not pool them or diagnose the difference as an implementation defect from rates alone.

The archived review proposed directional attenuation hypotheses and primary population clustering. For this proposed new study, the supplied faculty feedback supersedes those choices: neutral two-sided estimation and device clustering under the source-established independence described in section 9. Historical methods and results retain their original interpretation. The prior 0.5% nominal reliability target is a deployment-oriented research target, not an informative stress-region threshold; forcing calibration below it would recreate a floor.

## Simulated Noise Model
Read-only inspection of [device generation](../src/python/puf_snn/puf/device.py),
[frequency calculation](../src/python/puf_snn/puf/ro_puf.py), and
[indexed correlated noise](../src/python/puf_snn/experiments/correlated_noise_v1.py)
gives, for device d, attempt a, oscillator i, and reading r in {0,1,2}:

```text
f(d,a,i,r) = 100 + M(d,i) + C(d,a)
            + sigma sqrt(rho) Z(d,a,i)
            + sigma sqrt(1-rho) E(d,a,i,r)
M(d,i) ~ N(0,1^2), drawn once and retained
Z(d,a,i), E(d,a,i,r) ~ N(0,1), in separate indexed RNG domains
```

The base frequency calculator's more general equation is nominal + manufacturing + environmental offset + aging offset + independent read noise. The correlated adapter calls it with nominal 100, environmental offset 0, independent SD `sigma sqrt(1-rho)`, and disabled aging, then adds scaled Z and finally C. Nonzero aging is rejected. M is never resampled to simulate shared measurement noise.

All frequencies, M, sigma, and C are in **abstract additive frequency units**; no Hz or measured hardware normalization is established. Manufacturing SD is 1, so sigma=.10,.15,.20,.25 is respectively 10%,15%,20%,25% of that SD. Relative to the nominal 100, these are .10%,.15%,.20%,.25% per-reading SD, not 10% to 25% of oscillator frequency. Sigma is the total stochastic *per oscillator, per reading* measurement SD, excluding persistent M and the prescribed common C.

Z is oscillator-specific, shared across all three readings of one attempt, and regenerated for another indexed attempt. E is independent across oscillators and readings. C is uniform across oscillators and readings in the control; it is not the Z vector. In the existing control, C is -1 or +1 selected deterministically from a separate common-mode RNG domain. It is a cancellation check, not a measured environmental distribution.

For `N(i,r) = sigma sqrt(rho) Z(i) + sigma sqrt(1-rho) E(i,r)`, conditional on M and C, and for distinct readings r,s:

```text
N(i,r) ~ N(0,sigma^2) for every rho
Var[N(i,r)] = sigma^2
Cov[N(i,r),N(i,s)] = rho sigma^2
Cov[N(i,r),N(j,s)] = 0 for i != j
```

Pairs are (0,1),(2,3),...,(126,127), with bit `int(f_u > f_v)` (ties yield 0). There are 64 response bits; reconstruction uses positions 0 through 62. In a pair difference, 100 and C cancel; manufacturing *differences* and oscillator *differential* Z and E remain:

```text
f_u(r)-f_v(r) = M_u-M_v + sigma sqrt(rho)(Z_u-Z_v)
                         + sigma sqrt(1-rho)(E_u(r)-E_v(r))
conditional variance = 2 sigma^2
cross-reading conditional covariance = 2 rho sigma^2
conditional analog correlation = rho, when sigma > 0
```

These conditional statements exclude between-device manufacturing variation. Pooling frequencies over devices would add persistent M variance and would not estimate measurement rho. Randomizing C would also add raw common frequency variance; it still cancels from pair comparisons.

Analog rho is **not binary PUF error correlation**. Thresholding depends on the fixed pair margin; pooling device margins can itself induce binary association. Report any empirical binary-error correlation separately with its conditioning and zero-variance limitations. BER and errors outside t=5 are diagnostics, not substitutes for correct-credential reconstruction.

At rho=0 the Z contribution vanishes and E readings are independent conditional on the fixed device. At rho=1 E vanishes and all three responses are identical within an attempt: matched S and M reconstructions must agree and Delta=0 exactly in a complete deterministic reconstruction comparison. Attempts still vary through Z. All three simulator calls must occur; this limit does not authorize caching or skipping reads. At sigma=0, measurement correlation is undefined because both noise variances vanish.

**Implementation assessment:** the inspected addition order and scales agree algebraically with these equations. Zero additions are skipped for legacy exact compatibility. `CommonModeNumericalError` rejects any floating-point offset that changes bit ordering; it is an infrastructure/numerical fault, not a physical common-mode effect or a D/I/W outcome. Negative finite modeled frequencies are unclipped abstract values. No simulator correction is needed for this equation.

[Existing noise tests](../tests/puf/test_correlated_noise_v1.py) contain fixtures for component scaling, finite second moments, pair variance/covariance, rho0/1, common-mode cancellation/roundoff refusal, domain separation, matched reading zero, and actual one/three measurement counts. These tests were **inspected, not run**. The [prior model validation](week7-correlated-noise-model-validation.md) records historical testing; it is not a new test receipt.

## Experimental Arms and Matching

| Arm | Runtime source operations per completed attempt | Role |
| --- | --- | --- |
| S: `single-read-v1` | 1 actual reading; 1 BCH reconstruction/decode | Primary comparator |
| M: `majority-3-v1` | 3 actual readings; 1 bitwise vote; 1 BCH reconstruction/decode | Primary acquisition policy |
| T: `stored-provisioned-v1` | 1 trusted retrieval; 0 reads/votes/decodes | Final-evaluation credential-source/downstream control |

Keep BCH(63,36,t=5), the 32-bit credential plus four fixed padding bits, 63 selected response bits, independent credential verifier, admission service, Authentication-v2, fixed stationary 120-sample sequence-zero window, and recording consumer unchanged. T retrieves the same enrolled credential from trusted process memory; it is not a reconstruction and is excluded from Delta and A. A 256-bit derived session key does not increase the credential's 32-bit entropy limit.

Within a device/trial/condition, S and M use identical noise identity, shared Z, and indexed reading zero. M additionally reads indices 1 and 2. Separate reader objects regenerate the actual matched reading; no response cache substitutes for acquisition. Every arm uses fresh endpoints/session/admission/consumer state and the same enrollment and independent-verifier material. Protocol entropy continues to use OS randomness; it is not seed-matched.

Across rho conditions, match by device and attempt index while using distinct measurement domains. Same index does not mean common random realizations across rho. Keep all conditions in the same resampled device to preserve their shared manufacturing/enrollment dependence. The common-mode control explicitly aliases the rho0 operating condition's noise domain and must agree in PUF bits and C/D/I/W; it is a linked repeat, not an independent noise observation.

Calibration uses S/M only, alternating S-M and M-S with device/condition/group offsets (10 each of the 20 trials). Final evaluation cycles six S/M/T permutations with these offsets (8 or 9 occurrences per 50-trial cell). Shuffle whole matched blocks using the dedicated schedule stream. Record order and execution index. Keep stored repetitions inside the same device; their repetition across conditions does not create a PUF reliability sample.

## Prespecified Calibration Procedure
**Recommended default: 4 disjoint seed groups x 6 devices x 20 matched trials per device x 4 sigmas x 2 policies = 3,840 attempts.** A group is an independently indexed collection of six independently manufactured devices, not a random shared wafer/environment effect. The 24 devices and their enrollment are reused across all four candidate sigmas, with distinct measurement domains by sigma. All calibration conditions have rho=0 and C=0. No correlated outcome may be used to select sigma.

Complete all four candidates in one prespecified schedule before selection; there is no early stopping when a favorable candidate appears. At each sigma, there are N=480 matched pairs and N=480 outcomes per policy. For each device d, let `f_Sd`, `f_Md` be its 20-trial failure fractions and `b_d=f_Sd-f_Md`. Compute equal-device averages and the paired bootstrap in section 9.

The following are **new proposed quantitative defaults**. The prior review required an informative region and practical thresholds but supplied no approved numbers for them. Do not describe these gates as faculty-approved or as power calculations. Require **every row** to qualify:

| Gate | Exact proposed criterion | Rationale |
| --- | --- | --- |
| Coverage/correctness | All 3,840 scheduled attempts complete, two-pass evidence validation passes, all S/M pairs present, zero infrastructure/release-invariant faults. | Avoid outcome-dependent complete-case selection. Ordinary D/I/W refusals are completed outcomes. |
| Observable, nonsaturated baseline | `0.05 <= FRR_S <= 0.70`; S failures >=24 and S correct outcomes >=24. | Avoid a rare-event floor and a mostly unusable source. At N=480, the range gives 24 to 336 S failures. |
| Useful M region | `FRR_M <= 0.50`. No positive minimum M-failure count. | Avoid selecting a setting where both reconstructions are mostly failing; a zero-M-failure cell can still give an informative paired difference. |
| Meaningful independent benefit | `Delta(sigma,0) >= 0.02` (2 percentage points). | A modest absolute reconstruction benefit, independent of any later attenuation. This is an operating-region gate, not a deployment target. |
| Informative matched counts | At least 20 discordant S/M pairs in total, distributed across >=6 devices and >=3 groups; S failures also span >=6 devices and >=3 groups. Publish both discordance directions. | Many failures on one fragile device, or many concordant failures, need not identify voting benefit across devices. No minimum W/I count is imposed. |
| Sampling uncertainty | The 95% pointwise device-bootstrap interval for S FRR has lower endpoint >=0.01 and upper endpoint <=0.85; Delta's interval has lower endpoint >0 and full width <=0.20. | Screen out floor/saturation uncertainty and severely imprecise apparent benefit. Width 20 pp is a modest calibration screen, not final precision. |
| Device/group heterogeneity | Deleting any single device leaves Delta >=0.01. At least 3 of 4 group mean benefits are >0; no group mean benefit is below -0.02. | Avoid selection driven by one device or a substantial opposite group result. Groups have equal size. Report all device/group estimates, including failures of this gate. |

Use unrounded values for gates, inclusive endpoints except explicitly `>0`. Discordance means `F_S != F_M`: beneficial discordance is S failure/M correct; harmful discordance is S correct/M failure. Delta equals their net count divided by 480. Device coverage counts the union of either discordance direction. All eligibility gates use the original complete data; do not reapply gates inside bootstrap samples. Delete-one-device means recomputing the equal mean over the remaining 23 complete devices, not deleting individual failed trials.

These bounds are intentionally broad because calibration is for selection, not precise publication claims. Twenty trials on each of 24 independent devices provide 480 pairs per candidate without starting a 90,000-attempt study. Four groups permit basic consistency checks; they do not support precise group-level inference. This is the smallest recommended initial allocation under these explicit count/heterogeneity gates, not a proven mathematical minimum or an assured qualifying sample size. Increasing trials on one device would not replace additional independent devices.

Select the **lowest numeric sigma** passing all gates, ordered .10,.15,.20,.25. Do not rank by maximum Delta, maximum future A, minimum latency, or a visually favorable correlation curve. Write a signed/dated selection receipt containing all gates, unrounded values, hashes and selected sigma before generating any final-evaluation outcomes. Calibration intervals describe selection data and are not confirmatory evidence of the selected setting's true benefit.

If none passes, report **no qualifying operating point** and the exact failed gates for every candidate. Distinguish fully assessed failures from an incomplete or faulty calibration, for which selection is prohibited. A promising point with insufficient events or wide uncertainty still does not qualify. Do not default to .25 or enlarge the sample, retune gates, change seeds, or add sigmas automatically. Any follow-up requires a new prospective amendment and independent calibration data; retain this unsuccessful cohort and its result.

## Noise Conditions and Operating-Point Selection
Calibration evaluates only independent readings at .10,.15,.20,.25. Final evaluation holds sigma* fixed and uses **rho={0,.50,.90,1.00}, C=0**. This retains the existing positive-correlation levels and adds the analytically checkable fully shared boundary. Four points establish discrete contrasts, not a continuous response surface or proof of monotonicity. Intermediate .25/.75 rho values are deferred to a separately approved extension.

Also retain a separately labeled nominal comparison (.10,0,C=0) and a common-mode control (sigma*,0,C=-1/+1) linked to the operating rho0 realization. The signs are selected once per trial using the common-mode seed, not two extra full conditions. If sigma*=.10, nominal is the **same cell** as operating rho0: use one physical allocation with two roles, never duplicate its denominator. If sigma* differs, nominal gets a separate measurement domain. Historical .25 stress does not require a new standalone final cell unless it is sigma*.

After calibration, publish a compact sensitivity summary with exactly four rows: sigma; S/M C/D/I/W and N; FRRs and device-bootstrap intervals; Delta and interval; beneficial/harmful discordances; numbers of failure/discordant devices and groups; device/group summaries; each gate pass/fail and selected/not selected. Include zero-event and uncertainty flags. No such values exist from this task. Do not invent them from Week 6 or the single-device pilots. Correlation sensitivity across **sigmas** is outside this calibration and final design.

## Calibration and Final-Evaluation Allocations
All counts below are planned successful-run counts, excluding warmups (none in the recommended initial profile) and validation. One pair/block means two PUF attempts in calibration, three source attempts in final evaluation.

| Phase/cells | Groups x devices/group x trials/device/cell | S/M/T attempts | PUF readings | Runtime BCH decodes | Runtime votes/retrievals |
| --- | --- | --- | --- | --- | --- |
| Calibration, each sigma at rho0 | 4 x 6 x 20 = 480 blocks | 480/480/0 = 960 | 1,920 | 960 | 480/0 |
| Calibration, all 4 sigmas | Same 24 devices, 1,920 blocks | 1,920/1,920/0 = **3,840** | **7,680** | **3,840** | 1,920/0 |
| Final, each unique condition | 20 x 6 x 50 = 6,000 blocks | 6,000/6,000/6,000 = 18,000 | 24,000 | 12,000 | 6,000/6,000 |
| Final, 4-point operating rho grid | Same 120 devices, 24,000 blocks | 24,000 each = 72,000 | 96,000 | 48,000 | 24,000/24,000 |
| Final common-mode control | Same 120 devices, 6,000 linked blocks | 6,000 each = 18,000 | 24,000 | 12,000 | 6,000/6,000 |
| Final nominal, only if sigma* != .10 | Same 120 devices, 6,000 blocks | 6,000 each = 18,000 | 24,000 | 12,000 | 6,000/6,000 |
| Final total, sigma* != .10 | 6 unique conditions; 36,000 blocks | 36,000 each = **108,000** | **144,000** | **72,000** | 36,000/36,000 |
| Final total, sigma* = .10 | 5 unique conditions; 30,000 blocks | 30,000 each = **90,000** | **120,000** | **60,000** | 30,000/30,000 |

There are 24 calibration and 120 final enrollment/reference constructions, once per unique device per execution. Enrollment encoding is setup, not one of the runtime BCH decodes. Each phase has disjoint devices, not 144 shared devices. Maximum eligible first windows/releases equal attempts; actual counts depend on completed sessions. Rejected attempts do not get synthetic zero-latency windows. T is deliberately omitted from calibration because it does not inform the reconstruction operating region; it remains in final evaluation.

The historical **90,000-attempt proposal generally requires revision**. Its fixed five-condition list cannot express calibration or the chosen-sigma grid. The recommended final allocation is normally 108,000 attempts; only selection of .10 permits 90,000 with the nominal role merged, and even then the conditions change (rho1 replaces standalone .25 stress). Keeping exactly 90,000 for other sigma choices would require dropping a condition or changing replication and is not silently permitted. Preserve [three_arm_auth_v1.json](../configs/three_arm_auth_v1.json) unchanged; use a new versioned final config after selection and approval.

### Deterministic seed identities
The existing `canonical_seed_bytes`/`derive_seed` machinery is implemented: sorted compact ASCII-escaped JSON, UTF-8 without newline, SHA-256, all digest bytes interpreted as an unsigned big-endian integer, then Python `Random`. Its fields are model_version, master_seed, population_id, device_id, noise_domain_id, attempt_id, domain; `reading_index` is added only for `independent-reading`. Python hash(), policy, execution order, secrets, sigma/rho floating-point serialization, and stream consumption do not enter this seed.

**The following new identities/mapping are proposed, not implemented.** Let phase version V be `week9-shared-noise-calibration-v1` or `week9-shared-noise-final-v1`, respectively. Use stable integer-coded condition tokens rather than float repr. These roots are disjoint from old 20261019xx roots and must be frozen, not rerolled after outcomes.

| Stream | Calibration identity | Final-evaluation identity |
| --- | --- | --- |
| Simulation master | 2026102801 | 2026102811 |
| Group/device labels | `w9c-p000..003`; append `-d00..05` | `w9f-p000..019`; append `-d00..05` |
| Manufacturing | phase master, group/device, `noise_domain_id=V:enrollment-v1`, attempt_id=0, domain=`manufacturing` | Same construction with final V/master/IDs |
| Enrollment reference | Same fixed identity, domain=`enrollment-reference`; zero SD consumes no Gaussian read draws | Separate final identity, also noiseless |
| Synthetic credential | Same fixed identity, domain=`credential-generation`; 32 seeded bits | Separate final identity; truth stays transient |
| Measurement Z | `V:s010:r000`, `V:s015:r000`, `V:s020:r000`, `V:s025:r000`; attempt_id=0..19; domain=`session-correlated-oscillator` | `V:op:r000/r050/r090/r100`, attempt_id=0..49; same selected sigma throughout; domain as at left |
| Measurement E | Same measurement identity, domain=`independent-reading`, reading_index=0/1/2 | Same with final identities; reading0 shared S/M |
| Nominal/common | No additional calibration conditions | Separate `V:nominal:s010:r000` if needed; common aliases `V:op:r000`, with domain=`common-mode-offset` for sign |
| Schedule root | 2026102802; domain=`schedule` | 2026102812; domain=`schedule` |
| Device bootstrap root | 2026102803; domain=`device-bootstrap` | 2026102813; domain=`device-bootstrap` |
| Group sensitivity root | 2026102804; domain=`group-bootstrap-sensitivity` (descriptive group checks are primary sensitivity at 4 groups) | 2026102814; domain=`group-bootstrap-sensitivity` |

For schedule/bootstrap, derive the integer seed as SHA-256 of canonical JSON `{experiment_id:V, domain:DOMAIN, seed:ROOT_SEED, config_sha256:CONFIG_DIGEST}` using the same canonical encoding and full-digest conversion. Freeze sorted device/group order and draw algorithm with the Python/RNG version. All calibration sigmas use common bootstrap multiplicities, not independent draws per cell. The final simulation master is independent of the calibration choice; no search over final seeds is allowed. Freeze the selected sigma in its config/plan before generating final data. Versions in the table are design identities, not claims that files or commands with these names already exist.

The current enrollment helper retains a Week 7 domain even for Week 8 device labels, and current planners hard-code Week 7/8 identities. The proposed phase domains must be explicitly implemented in the new harness rather than assuming the old enrollment helper already uses them. OS-random verifier keys, protocol nonces/session IDs, authorization capabilities, and actual durations remain unmatched; deterministic simulation does not imply byte-identical protocol traces.

## Primary and Secondary Outcomes
For each completed PUF attempt, C/D/I/W are mutually exclusive and exhaustive:

| Outcome | Definition / recorded basis | Denominator |
| --- | --- | --- |
| C: correct credential | Candidate equals enrolled credential in evaluator-only truth classification | All scheduled completed PUF attempts |
| D: decoder failure | `decoder_failure` | Same |
| I: invalid format/padding | `invalid_format_or_padding` | Same |
| W: valid-format wrong credential | Candidate passes format but differs from truth | Same; counts as reconstruction failure |
| Independent verification refusal | Actual `verification_outcomes`, with mismatch/disabled-policy reasons separate; not reached is separate | Calls reached, plus all-attempt rate explicitly labeled |
| Successful credential verification | Actual `verified` result | Actual calls and all attempts, both labeled |
| Local authorized admission | Actual admission issued; distinct from verification and active session | All attempts; also verified-eligible conditional rate |
| Completed authenticated-session admission | Establishment accepted and sender/receiver active after mutual confirmation (`session_active` with endpoint checks) | All source attempts |
| Authorized inference release | Accepted verifier-owned window reaches release, with entry/completion and each callback invocation/completion recorded separately | All attempts and eligible sessions/windows, labeled separately |

The primary FRR is `(D+I+W)/N`, equivalently `1-C/N`. Count truth classification only in the evaluator; it grants no authentication authority. A BCH-valid output is not a verified credential. D/I ordinarily stop before verification; W can reach verification and be refused before HKDF. A not-reached verifier is not an explicit refusal. Infrastructure faults are not a fifth reconstruction outcome: they prevent complete-study certification, with scheduled/started/persisted coverage reported rather than a selected completed subset.

For T, reconstruction outcome/FRR and decode time are inapplicable/null, not zero failures or successful BCH. Report retrieval success/unavailable/malformed, then verification/admission/session/window/release counts. For every arm report source refusal, credential mismatch, policy refusal, handshake refusal, and infrastructure failure separately. These successive stage counts overlap and must not be added as a partition. Wrong-candidate refusal rate is undefined if W=0; report no observed opportunity rather than 100% protection.

Secondary outcomes are session/admission failure rates, raw/first/effective BER over the selected 63 bits, error-count histograms, discordance counts, source operations, and declared timing distributions. Recording release demonstrates a software authorization boundary, not trained SNN execution or model accuracy.

## Statistical Analysis and Cluster Bootstrap

### Independence assessment and population meaning
`create_device()` draws independent Gaussian manufacturing offsets from a device-specific RNG. `enrollment_material()` derives separate manufacturing,
reference and credential streams using both population_id and device_id. Z and E also include those IDs. A shared numeric master seed or a group label is not a shared latent physical effect: the implemented model has no random group mean, shared wafer term, sampled population SD, shared measurement shock across devices, or estimated parameter learned from one group and fed back into its devices. The manufacturing SD=1, sigma, and rho are fixed design parameters. Fresh protocol endpoints are not shared session state. Under the intended independent indexed PRNG-stream simulation law, **devices are the appropriate primary clusters for reconstruction reliability**, not readings, trials, or arbitrary six-device groups.

Group labels define disjoint reproducibility batches: four calibration groups and twenty final groups. Persistent device margins induce dependence among its trials and conditions; all must be retained. Shared host/JIT/OS load can induce timing dependence even when reconstruction noise is independent, so reliability independence does not certify timing intervals. Hold inference conditional on the specified simulator; pseudorandom streams are not a proof of physical independence or a source of secret entropy.

Before freeze, inspect the final generating path again. If a group-level random effect is introduced or discovered, change primary resampling **before viewing outcomes** to whole independent groups with all devices/conditions/trials retained. Use a hierarchical scheme only if it matches the actual generation/sampling target; never resample devices across shared groups as independent. Four calibration groups would be too few for persuasive group-level uncertainty: pause for a prospective allocation amendment rather than using narrow device intervals. This contingency is not a proposed simulator change.

### Estimator and resampling algorithm
For complete balanced data at each phase, define `F_p,d,t,c=1` for D/I/W and 0 for C, and `b_d,c = mean_t(F_S,d,t,c-F_M,d,t,c)`.

```text
Delta_hat(c) = mean_d b_d,c
A_hat(rho) = mean_d [ b_d,op_rho0 - b_d,op_rho ]
```

Each device has equal weight; balanced trials make these equal to pooled matched-attempt differences. A nominal cell with another sigma is never the reference for A. No pooled S/M/T reconstruction rate is allowed.

1. Verify complete coverage and pairing using phase, device, condition, and
   attempt index, not `trial_id` alone across conditions (trial IDs differ by
   condition). Form per-device records containing **all** trials, arms, sigmas
   or rho conditions, and linked controls. T may travel with the records for
   secondary outcomes but never enters b.
2. With a fresh `Random(derived_phase_device_bootstrap_seed)`, draw D device
   indices uniformly with replacement, D=24 for calibration or 120 for final.
   Use sorted device IDs and `rng.randrange(D)` D times for each draw.
3. Give each selected device its multiplicity. Retain every trial and S/M pair
   and use the **same multiplicities** for every condition, Delta and both
   components of A in that draw. Repeatedly selected devices repeat their entire
   record, not fresh noise or independently sampled trials.
4. Perform exactly **10,000** resamples. Save seed identity, D, B, sorted identity
   digest, algorithm/version and defined-draw counts. Compute two-sided 95%
   **pointwise percentile intervals** using .025/.975 quantiles and the existing
   linear interpolation at `(B-1)*p` between sorted bootstrap values. No normal
   approximation, clipping at zero, or post hoc switch of interval method.
5. Report failure counts, correct counts, both discordance directions, device
   distribution, estimate, interval and scope for Delta and A. Also estimate
   absolute FRRs using the same device draws. Preserve rho0/rho1 special cases.

These are approximate nonparametric intervals, not exact coverage guarantees. With D<2 suppress intervals; the prescribed complete cohorts have D=24/120. For a conditional secondary outcome whose denominator is zero in any draw, report defined/undefined counts and suppress that interval; do not silently discard/redraw undefined samples. The complete-data unconditional primary contrasts always have positive denominators. Partial runs are diagnostic only.

If all failures in a cell are zero, retain observed zero and label its [0,0] bootstrap interval **degenerate, uninformative about unseen failures**. No pseudocounts, independent-attempt binomial bounds, or equivalence claims. A contrast can have a nondegenerate interval even if M has zero observed failures; do not suppress an informative paired Delta merely for that reason. At rho1, matched reconstruction Delta should be identically zero by construction; this identity does not imply an empirically measured zero failure probability.

All intervals are estimation-only and pointwise. No joint superiority/attenuation claim, familywise significance, or equivalence margin is specified. A two-sided interval containing zero means unresolved direction, not equality. Any later confirmatory family/multiplicity or final precision requirement needs approval before final data, not selection of favorable contrasts afterward.

### Separate group/reproducibility sensitivity
Publish device-level and group-level FRRs/benefits, range/dispersion, event concentration, and leave-one-device/group-out contrasts. For final evaluation, add a **separately labeled** 10,000-draw whole-group bootstrap (20 groups of six) with its dedicated seed and all within-group evidence retained. It is a sensitivity analysis under this independent-device model, not 20 clusters silently substituted for 120 primary clusters. In calibration, show all four group estimates and leave-one-group-out results descriptively; avoid presenting four-group intervals as precise reproducibility evidence. No additional runs or seeds are automatically authorized by this sensitivity analysis. Disagreement is reported, not resolved by choosing whichever interval is narrower.

Existing [Week 7 analysis](../src/python/puf_snn/experiments/majority3_auth_analysis_v1.py) implements whole-population bootstrap for two arms at old fixed conditions. The [three-arm summary](../src/python/puf_snn/experiments/three_arm_auth_evidence_v1.py) emits `not-computed-nonformal`. Neither already implements this device-bootstrap contract, operating-point selection, or new phase seed mapping.

## Timing Measurement Boundaries
The existing serial [runtime instrumentation](../src/python/puf_snn/experiments/three_arm_auth_runtime_v1.py) and [inherited capture](../src/python/puf_snn/experiments/majority3_auth_runtime_v1.py) record `perf_counter_ns` inclusive spans, start offsets, parent IDs, exceptions, invocation counts and per-stage summed durations. Exact available boundaries:

| Work | Existing span / wrapped entry | Containment and limitation |
| --- | --- | --- |
| PUF acquisition | `acquisition`: `pipeline_v2.acquire_response`; `reading`: complete reader callback | Readings and vote are inside acquisition. |
| Oscillator calculation | `measurement`: `noise.calculate_frequencies` or `ro_puf.calculate_frequencies` | Inside reading; excludes the correlated adapter's later Z/C additions, comparisons and validation. It is not the full reader. |
| Majority vote | `voting`: `acquisition.majority_vote3` | Inside acquisition; no voting span for S/T. |
| Reconstruction/BCH | `reconstruction`: `pipeline_v2.reconstruct`; child `bch_decode`: `BCHCodec.decode` | Decode is included in reconstruction; format/helper work is in its remainder. |
| Independent verification | `verification`: `CredentialAdmissionService.verify` | Child of `authorization`. |
| Local admission | `authorization`: `authorize_with_outcome`, within `admission_request` (`Sender.begin_attempt` / `begin_stored_attempt`) | Authorization includes verification; exclusive authorization subtracts its child. T's `retrieval` wraps provider `get_credential`. |
| Establishment | Direct `establishment` root around `pipeline.establish` / `establish_stored` | Includes source, reconstruction if PUF, admission, and handshake, even on ordinary refusal. |
| Mutual confirmation/HKDF | `mutual_handshake`, `receiver_challenge`, `sender_confirmation`, `receiver_confirmation`, `sender_activation`; child sender/receiver HKDF spans | Nested within establishment; do not add to it again. |
| First protected window | Direct `first_window` root; `window_seal`, `window_verify`, `release` children | Only after session establishment; includes fresh-session sequence-zero processing and recording callbacks. |
| Authorized release | `release`: `V2InferencePipeline.release`; callback invocation/completion counters | Includes preprocessing/motion/anomaly recording callbacks. No separately timed trained-model inference is present. |

Exclusive duration is parent duration minus **immediate** child durations, after validating containment and nonoverlap. Only a complete partition of exclusive components plus remainders can be additive; inclusive parents/children cannot. Total p95 is computed from measured totals, never sums of stage p95 values. Establishment and first_window are separate roots with intervening untimed work; no existing direct fresh-attempt-to-release root is supplied. Their per-attempt sum may be labeled a sum of measured spans, not wall-clock end-to-end latency.

**Recommended bounded calibration timing profile:** retain the existing cold-process, zero-harness-warmup profile, with diagnostic timing only. Preserve all first-use/JIT observations, attempted refusals, execution order and environment; do not trim a slow decode or label its compilation share measured. Prior pilots had first BCH decodes around 2.3-2.4 seconds; that is historical evidence of a first-use issue, not a prediction for the next host. Setup can initialize code and caches even before the first measured decode.

Final evaluation under this specification also supports **diagnostic timing** with the same declared profile; warmed latency benchmarking is deferred. If warmed timing becomes an objective, approve a separate fixed warmup count, isolated fixture IDs/streams, acceptance/failure accounting, cache policy and new timing-profile version before execution. Record its operations separately; never warm until a convenient latency or successful outcome is reached. Do not quietly switch the existing zero-warmup contract.

For every condition/arm/stage report recorded span count, eligible count, mean, median and p95 (existing linear quantile convention), converted ns/1e6 to ms. Retain missing/inapplicable values as null. Show all-attempt establishment, successful sessions, and rejected attempts separately, with C/D/I/W/retrieval strata as available. Successful-only comparisons condition on survival and are not the all-attempt policy effect. First-window counts reflect only eligible established sessions, not total attempts.

Enrollment/helper encoding, provisioning, verifier-record preparation, fresh endpoints, shared-Z preparation, window-template creation, model loading, instrumentation installation, row construction/validation, source hashing, JSONL flush/fsync, summary/bootstrap and replay lie outside the measured roots. Independent per-read Gaussian draws and correlated additions lie inside reading. No physical PUF, sensor collection, external transport or actual trained model is timed here. Week 6 saved-model timings and October 21 workflow seconds are different experiments and must never be added to these spans as an invented end-to-end result. Shared-process drift prevents an automatic inferential timing interpretation from the reliability bootstrap.

## Resource Feasibility and Reproducibility

### Execution and replay accounting
Preserve the existing two-pass semantic/replay and manifest validation contract in any new harness. Replay reconstructs inputs, readings, votes and decoding; it does not rerun independent protocol handshakes or add statistical samples.

| Phase | Execution reads / decodes / reference reads | Additional two-pass replay reads / decodes / references | Execution plus finalization, including references |
| --- | --- | --- | --- |
| Calibration | 7,680 / 3,840 / 24 | 15,360 / 7,680 / 48 | 23,112 simulator measurements; 11,520 decodes |
| Final, 6 conditions | 144,000 / 72,000 / 120 | 288,000 / 144,000 / 240 | 432,360 simulator measurements; 216,000 decodes |
| Final, 5 conditions when sigma*=.10 | 120,000 / 60,000 / 120 | 240,000 / 120,000 / 240 | 360,360 simulator measurements; 180,000 decodes |

Each later standalone audit adds **one** execution-sized replay and one reference per device: calibration 7,680/3,840/24; six-condition final 144,000/72,000/120. Votes similarly occur once per M attempt and again per replay pass. Reference generation and helper encoding are setup/replay work, not runtime policy decodes. Receipts must distinguish per-pass, successful two-pass finalization, later audit, started versus completed work and zero added samples. A failed second pass must never receive a successful two-pass marker. Historic one-pass receipt fields must not be retroactively multiplied to assert unrecorded audit history.

### Storage, memory and runtime
The feasibility report records two 150-attempt profiling workflows of 142.875 and 48.734 seconds (before/after schema preparation caching), retaining 459 instance validations. Approximately 1.502 billion sampled private bytes in both does not demonstrate memory reduction or a guaranteed instantaneous peak. The cache improves harness overhead, not PUF or inference algorithms. Do not multiply 48.734 seconds by an allocation ratio and promise completion.

Using the historical 924,808-byte/150-attempt ledger solely as a byte projection:

| Planned bundle | Projected ledger | Approximate central complete bundle, before reserves |
| --- | --- | --- |
| Calibration, 3,840 attempts | 23.7 MB | about 27 MB |
| Final, 108,000 attempts | 665.9 MB (October 21 row sizes suggest about 673 MB) | about 0.7-0.72 GB |
| Final, 90,000 attempts | 554.9 MB (later row sizes suggest about 561 MB) | about 0.6 GB |

These are decimal units and projections from a different three-arm outcome mix; calibration excludes stored rows and may have different row sizes. Allow for new identities, plans, summaries, source snapshots, analysis artifacts, logs, caches, backups and retained incomplete runs. Serialized size does not estimate Python heap size. A proposed initial calibration reserve is **1 GiB free output space, 8 GiB available host RAM, a 4 GiB process-private-memory stop budget, and 30 minutes total workflow including finalization**. These are conservative administrative defaults to approve/adjust for the selected host, not measured needs or a promise of completion. A safe external supervisor must enforce and record the limits; the existing profiler cannot be assumed calibration-compatible. Do not bypass a budget stop or automatically retry with larger budgets.

`EvidenceRun.rows` retains nested records, plans and identities. Finalization audits parse a second full row graph while the first remains live, alongside JSON byte buffers and summaries. This is the main unqualified formal-scale memory risk. Source hashing before each attempt, full schema instance validation, row writes/flush/fsync, and two reconciliation passes remain mandatory costs. The schema cache does not remove them. Bound the much smaller calibration first; full final allocation remains resource-unqualified. Reserve and approve a new formal-scale qualification plan after the selected design is frozen.

### Source-path blocker and environment freeze

Current `three_arm_auth_evidence_v1.source_paths()` requires `docs/week8-three-arm-auth-tests.patch`. It is absent there; the file exists as [docs/archive/week8-three-arm-auth-tests.patch](archive/week8-three-arm-auth-tests.patch). `source_hashes()` checks all required files before execution and current audit compares source/environment identities. This is a static execution/audit blocker, not a failure run during this task. The new harness's reviewed source list must use the actual archive location and include its own code/config/schemas/tests, this specification, the approval and selection rules. Do not restore a dummy file, bypass integrity checks, edit historic manifests or use current source to reseal old bundles. Old auditors need their exact recorded source/environment.

Before bounded execution, freeze exact file bytes/hashes (including line endings), config and canonical plan digests, seed mapping, selected interpreter/architecture, dependency versions and test receipt. The package declares Python >=3.12,<3.14 and galois==0.4.11. Historical PUF metadata used CPython 3.12.4; another project handoff used Windows x64/Python 3.13.14. Neither proves the present interpreter compatible. Do not install anything under this task. Record OS/CPU/RAM, package versions, GC/thread/cache/JIT settings, power/load context, output disk and supervisor. Reproduction needs exact source and an actually compatible environment; seeded reliability inputs do not reproduce durations or OS-random protocol bytes.

Keep the unresolved historical `pipeline_timing.py` provenance question and unlocated ARM64 reproduction receipt visible as historical limitations. Present hash agreement or completing this specification does not resolve them or certify independent experimental reproduction.

### Protected outputs and interruption
Propose a new direct-child namespace `results/week-9/will/shared-noise-calibration-v1/` with run prefix `week9-shared-noise-calibration-v1-`, and a distinct future final namespace `results/week-9/will/shared-noise-final-v1/`. These are not created here. Require reviewed-plan-bound bounded authorization, exclusive creation, no existing output, traversal/alias/symlink/junction/nested-bundle paths, or historical tree writes. Unit fixtures stay in isolated temporary storage. Do not redirect new calibration into the Week 8 pilot namespace or reuse its authorization token.

Retain `INCOMPLETE` throughout execution, reconciliation, manifest audit and finalization; create a versioned completion marker only after both passes and source/config checks succeed. Record authorized planned/started/persisted counts, stop reason and any unknown unrecorded work. No automatic resume, replacement noise draw, outcome-based retry, or selective omission. A budget/interruption/ infrastructure stop yields diagnostic incomplete evidence, never a calibration decision or final study. A separately authorized restart uses a new output and the frozen plan/seed policy, discloses the prior stop, and adds no independent device samples by replaying the same identities.

### Minimum engineering work
There is **no compatible calibration runner identified** in `src/python/scripts` or `tools`. The existing CLI offers only `plan`, bounded `run-nonformal`, and `audit`; its config and inherited validation enforce exactly the old conditions and either 20x6x50, 1x1x10, or tiny unit allocations. Its planner loops a hard-coded `CONDITIONS` constant, not arbitrary config conditions. Runtime, writer, schemas, source list and authorization/output policy also enforce the old version. Editing JSON alone, splitting into many old pilots, or relabeling a unit-test  mode would not implement this calibration.

Mandatory changes for a future bounded-calibration implementation,
1. Add an isolated versioned calibration planner/config/schema/CLI for exactly
   4x6x20, four rho0 sigmas and two policies; generate all phase seed identities,
   balanced schedule, pair links and expected operation counts. Expose a dry-plan
   action that performs no generation/acquisition/decoding. Leave old formal and
   pilot guards unchanged; new final mode remains unavailable.
2. Adapt experiment-local runtime/evidence plumbing to the new version and two
   policies, invoking the existing unchanged reader, acquisition, reconstruction,
   verifier, protocol and recording path. Preserve faults, timing semantics,
   real measurement counts, truth isolation and fresh endpoints. New version
   checks are necessary; calling the old guarded runtime with forged old config
   is not acceptable.
3. Implement section 9's device bootstrap, section 5's deterministic gates,
   complete four-row sensitivity output and a hash-bound selection receipt;
   schema-check both ordinary and zero/undefined cases. Ensure final data cannot
   be read by selection. No formal analysis flags are enabled in the old runner.
4. Adapt coverage/semantic reconciliation, deterministic measurement/decode
   replay, two-pass receipts and completion marker. Correct the required patch
   path in the **new** source-set definition, freeze actual imported source,
   and keep archived evidence read-only. Reuse validation mechanisms, not their
   obsolete source/condition identities.
5. Add exclusive new output protections, explicit attempt/operation caps,
   reviewed-plan authorization, and resource-stop supervision. Reuse/adapt the
   existing supervisor only after its fixed workload/path/token assumptions are
   reviewed; keep its prior safety guarantees and no-automatic-resume behavior.
6. Verify these new contracts using small deterministic fixtures only: pairing,
   nonoverlapping phase streams, count arithmetic, known positive/negative/zero
   contrasts, device multiplicities across conditions, gate endpoints and
   lowest-selection/no-qualification, concentrated device failures, absent
   pairs, zero events, forbidden paths, source change, interruption and failed
   second-pass handling. Retain exact focused test commands/receipts; ordinary
   root test discovery omits some `experiments`/`tools` tests.

Optional performance work is **not required before bounded calibration** if it fits approved limits: streaming reconciliation/summaries, avoiding duplicate row graphs, reducing redundant hashing without weakening source-freeze guarantees, or revised persistence batching with a reviewed durability contract. Do not relax schema checks, replay passes, integrity, operation accounting, or fault handling to obtain speed. If calibration exceeds limits, report the stop and seek a scoped resource amendment rather than opportunistic optimization mid-run.

## Execution Gates and Unresolved Decisions
| Gate | Concrete requirement | Current status |
| --- | --- | --- |
| Methodology | Accept neutral objective, fixed marginal noise, C/D/I/W and independent-verification distinctions, calibration/final separation | Supplied faculty guidance incorporated; implementation not assessed by faculty here |
| Numerical calibration contract | Approve 24 devices/20 trials, all section 5 gates, four-candidate selection and no-qualification behavior | Proposed; no calibration outcomes inspected/generated |
| Independence/analysis | Accept device primary unit for current generation model, group sensitivity, 10,000-draw pointwise estimation and zero-event limitations | Source supports device independence; new analysis pending |
| Bounded engineering | Review new versioned planner/runtime/evidence/selection code, path resolution, fixtures and protected output | Not implemented; no compatible runner today |
| Host/resource budget | Name execution owner/host, approve memory/disk/workflow caps and safe supervision, freeze environment/source/plan | Not qualified; proposed calibration defaults in section 11 |
| Bounded execution authority | Explicit authorization of only the complete 3,840-attempt calibration plan and its checking costs | Not supplied by this documentation task |
| Operating point | Completed certified calibration, all four rows, lowest-qualifying decision receipt or no-qualification result | Pending calibration |
| Final design and resources | Approve selected-sigma four-point grid, nominal/common/T controls, 90,000 or 108,000 allocation and resource qualification | Proposed; old five-condition config remains untouched |
| Final execution authority | Separately reviewed frozen source/config/plan/analysis/selection identity and explicit formal-run authorization | Absent; formal execution remains disabled |

Timing is descriptive under this specification. A request for warmed/model/recurring performance or confirmatory multi-contrast claims adds a new prospective gate; it is not necessary to reopen basic reconstruction calibration decisions.

## Recommended Implementation and Evaluation Sequence
1. Review and approve the numerical defaults, independence target, estimation-only
   scope, calibration allocation and bounded host budgets in this specification.
   Record the decision; do not alter the old five-condition formal configuration.
2. **Next task: implement and validate the isolated bounded calibration harness**
   described in section 11, including the actual archived patch source path,
   device bootstrap, deterministic selection, new evidence namespace and safe
   resource supervision. Use only deterministic unit fixtures. Produce the exact
   dry-plan/config/source digests, planned 3,840 attempts/7,680 reads/3,840 decodes,
   15,360/7,680/48 two-pass replay allowance, environment and test receipts. This
   implementation task does not itself execute research calibration.
3. After those gates pass, separately authorize **one complete bounded calibration**
   under its frozen plan and approved supervisor. Retain ordinary failures, stop
   on infrastructure/resource faults, finalize both checking passes and report
   actual resources; no final-evaluation or legacy formal command is enabled.
4. Apply the frozen gates once to all four candidate summaries. Publish sensitivity
   and a selected-sigma receipt, or no qualification. In the latter case stop
   and propose a new prospective amendment only if requested.
5. For a qualifying point, prepare a new selected-sigma final config and analysis
   contract with the four-point rho grid and controls. Review independence again,
   qualify full-scale memory/finalization/storage, freeze all identities, and
   obtain separate formal execution authorization. Reuse no calibration device
   or final outcome to revise selection.
6. Only then execute the final study, certify complete evidence, estimate Delta/A
   without a directional assumption, and report downstream reliability/timing
   and limitations. Any trained-model timing or physical-device extension is a
   distinct study.