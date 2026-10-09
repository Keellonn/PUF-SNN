# Draft paper evaluation section

**Status:** Preliminary evaluation prose for review, October 8, 2026. Experimental snapshot `2c84cf8394bd444188291e254bbf1ddde3cc8661`. This draft adds no experiment or stronger claim. Will's numerical results below are taken from his committed reports; their raw formal result directories are absent from this checkout and require shared release closure before independent paper review.

## 1. Evaluation questions and experimental boundaries

We evaluate five distinct questions: reconstruction/admission availability and wrong-candidate handling; tested authenticated-window rejection and release behavior; conventional/SNN intended-motion inference; semantically abnormal but quality-valid/authenticated stream detection; and fresh/recurring software processing costs. We do not infer that successful authentication establishes sensor truth or that a simulated PUF is a physical hardware root of trust.

Independent credential verification and local admission prevent the tested wrong decoder candidates from reaching session derivation. They introduce separately protected trust material. The [actual protocol specification](authentication-v2-protocol-spec.md) defines enrollment, wire messages, key formulas, admission authority and fail-closed behavior. Its receiver registry retains the enrolled four-byte credential in addition to a separate credential-verifier tag/key. Co-located trusted-process objects are not a secure process boundary, remote attestation service or production keystore. HKDF and HMAC-SHA-256 do not turn the 32-bit pilot credential into a production-strength secret.

Window integrity, binding and replay/order enforcement primarily follow from canonical message authentication and verifier state. The incremental PUF admission role has not yet been isolated by the requested provisioned-random-credential control. That control must keep data, policy, message/HMAC format and motion/anomaly models identical while substituting the credential source. No control results are inferred from existing gating tests.

### Evidence cohorts are not pooled

| Cohort | Purpose and source | Boundary |
|---|---|---|
| Historical reconstruction/verifier studies | Saved Week 5 noise/miscorrection evidence | Different population from the fresh alternatives study; no silent baseline replacement |
| Current-v2 Tier-1 formal run | [Will's report](week6-tier1-v2-experiment.md), actual isolated execution `0d088079d025e50411c8a752b32507bbb87d5d5b` | Noiseless reference-condition admission, finite traffic/state tests, SNN-32 seed 7/RF anomaly; not noisy-admission FRR |
| Standalone reconstruction alternatives | [Will's report](week6-reconstruction-alternatives-experiment.md), retained source snapshot with execution main HEAD `acc4647` | Independent noisy rereads, not integrated majority-3; exact source snapshot must accompany release |
| Historical Tier-2 stream evaluation | Frozen models, transforms and accepted deliveries | Predates current-v2 independent admission; retrospective reporting is not a fresh v2 security study |
| Original fresh/composite timing | Source `78f499a`, result `a4a9e25` | Single-read baseline, six frozen conditions, 3,720 attempts/29,718 roots |
| Saved-stage/source-aware revisions | Sources `7921261` and `c5e982b` | No new inference, fitting, authentication or original latency measurements |
| Paired exact-quality comparison | Source `bddce50`, result `2c84cf8` | New bounded AB/BA timings, three fixed conditions; default unchanged |
| GC/Windows diagnostics | Separate saved cohorts and sanitized numeric evidence | Support scoped contributions, not complete causal isolation or replacement target measurements |

## 2. Data, models, seeds and split discipline

The corrected synthetic dataset contains 1,800 two-second windows, 120 samples/window, representing five motion classes and six fixed device profiles. Session 1 supplies training, Session 2 validation/calibration and Session 3 held-out testing, with 600 windows in each split. Motion models receive a 120 x 7 sequence; the separate conventional anomaly path has 48 aggregate features. The data hash is pinned in [the release index](week6-release-evidence.md).

Generator seed 7 defines one dataset. It is separate from model initialization, shuffle, transform, PUF-response and bootstrap seeds. LR lbfgs fitting is deterministic for these recipes: repeated random-state labels and a reported 0.0000 SD are not independent random performance replications. SNN initialization seeds 7/17/27 and training/shuffle seeds 107/117/127 are distinct roles. All-seed per-class/confusion/checkpoint evidence remains available, and model seeds do not create independent source recordings.

Transforms and clean controls retain their source/split ownership. Anomaly fitting uses training only, and thresholds are selected on validation then frozen for testing. No threshold, attack parameter or architecture is selected using held-out test results in these reporting revisions. The corrected generator's original leakage finding is retained in the methods appendix; corrected orientation and complete-sequence near-neighbor audits do not establish physical or cross-person/device transfer.

## 3. Current-v2 implementation enforcement

Will's committed Tier-1 report documents six simulated devices and two enrollment generations, with 100 trials per device/generation cell per primary attack. Each primary group and legitimate-control group uses all 600 test windows twice. Trials vary device/enrollment/session/nonce identities, sequence positions, source windows, mutation coordinates and relevant lifecycle states. The isolated execution source and exact-byte recovery artifacts, rather than a later main HEAD alone, identify the formal run.

The following count map is reproduced from that report. It is not a substitute for the remaining consolidated per-experiment unique-session/message/repetition metadata and raw-evidence verification.

| Experiment role | Decisions / outcomes | Observed reason or state / inference behavior |
|---|---|---|
| A1 duplicate replay | 1,200 rejected, zero accepted | `duplicate_sequence`; zero release/preprocessing/motion/anomaly calls |
| A2 lifecycle replay | 1,200 rejected, zero accepted | 400 `inactive_session`, 800 `expired_session`; replacement/live-expiry/cleanup strata retained |
| A3 device substitution | 1,200 rejected, zero accepted | `invalid_tag`; zero consumers |
| A4 payload modification | 1,200 rejected, zero accepted | `invalid_tag`; 600 position and 600 quaternion mutations |
| A5 protected metadata modification | 1,200 rejected, zero accepted | `invalid_tag`; 200 mutations per each of six fields |
| S1-S8 state negatives | 1,080 rejected across 960 scenarios | Expected reason/state match; S4 has two negatives per scenario |
| Window/binary parser negatives | 1,440 rejected | Part of 28 parser types x 60 repetitions; zero consumers |
| Handshake parser negatives | 240 rejected | Separate non-window submissions; pending state preserved, zero consumers |
| Legitimate controls | 1,200 accepted, zero rejected | One accepted release and each consumer per window; sequence/state committed once |
| Setup windows | 23,520 accepted | Counted separately from scored attack/control submissions |
| Recovery windows | 10,200 accepted | Distinct recovery rows; 1,040 additional successful recovery-handshake operations |
| Warmup windows | 20 accepted | Separate from measured totals |

Thus measured accepted windows are 23,520 + 1,200 + 10,200 = **34,920**; rejected windows are 6,000 + 1,080 + 1,440 = **8,520**. The additional 240 parser refusals are handshakes, not windows. Each measured accepted window invokes each processing boundary once; all rejected windows invoke none. The broader plan has 66,920 measured operation rows, including handshakes/lifecycle work, and these are not 66,920 motion windows.

Before/after rejected-state checks document no unintended accepted-counter, sequence, lifecycle, authority or consumed-event changes. Legitimate acceptance commits state before at-most-once consumer release. Arbitrary consumer failure does not provide guaranteed completion or automatic replay. S6 recovery explicitly supplies missing sequence traffic and retries the retained future packet; it is not automatic buffering/resynchronization. If a legitimate packet is lost, exact-next enforcement can refuse later packets until the application retransmits the missing packet or starts an authorized new session. Rejection without mutation does not solve packet-loss or DoS availability.

Per primary group, attack acceptance 0/1,200 has a descriptive two-sided 95% Clopper-Pearson interval of 0-0.3069346%; complementary rejection is 99.6930654-100%. Control rejection is likewise 0/1,200. Reused profiles/windows and shared software limit an independent Bernoulli interpretation. These empirical intervals are not HMAC forgery bounds, general attestation evidence or a proof of protocol security.

## 4. Reconstruction reliability and independent verification

The standalone alternatives report evaluates 120 simulated devices in 20 independently seeded six-device populations, with 50 attempts/device/configuration/noise condition: 6,000 attempts/cell, eight cells and 48,000 total attempts. Noiseless enrollment and independent measurement rereads are explicit assumptions. Nominal oscillator measurement SD is 0.10 and stress SD is 0.25; manufacturing characteristics are held fixed per device.

| Nominal configuration | Credential / reads | Failed attempts / total | FRR | Population-bootstrap 95% interval | Software p50 / p95 ms |
|---|---|---:|---:|---|---|
| B0, BCH(63,36,t=5) | 32 variable bits / 1 | 59 / 6,000 | 0.9833% | 0.4833-1.6167% | 1.1312 / 2.3022 |
| Majority-3, same code | 32 bits / 3 | 6 / 6,000 | 0.1000% | 0.0167-0.2167% | 1.4547 / 2.6012 |
| Majority-5, same code | 32 bits / 5 | 0 / 6,000 | 0.0000% observed | Degenerate 0-0%; not evidence of zero underlying probability | 1.7722 / 2.9034 |
| Stronger BCH(63,30,t=6) | 30 variable bits / 1 | 15 / 6,000 | 0.2500% | 0.0667-0.5000% | 1.1333 / 2.3129 |

The report also supplies descriptive Clopper-Pearson intervals; the zero-failure majority-5 upper endpoint is 0.0615%. FRR here includes decoder failures, invalid credential format and wrong valid-format credentials refused by verification. Nominal cells have no observed invalid-format/wrong candidates. In stress cells, valid-format wrong candidates total 60 across configurations, all documented as refused by independent verification. Neither zero nominal wrong candidates nor zero observed nominal majority-5 failures establishes zero underlying risk.

The stronger code does not encode an unconstrained 32-bit credential in a 30-bit message space. It uses four big-endian bytes with the top two representation bits fixed to zero, carrying 30 variable credential bits. Baseline BCH uses a 32-bit pilot plus four zero padding bits in the 36-bit message. Compare credential length and exposure alongside latency, failure/miscorrection and verification outcomes.

The old nominal 1.625% and fresh B0 0.9833% belong to different registered studies; this draft does not attribute their difference to an implementation improvement. Old/new seeds, population, enrollment, selected response bits, noise realization, read policy and procedure need a side-by-side reconciliation. Majority-3 is a provisional candidate, not an integrated-v2 reliability result. Shared/session perturbations and independent measurement noise must be compared, including whether pair-common oscillator offsets cancel and whether pair-differential components change comparisons.

A reconstruction refusal occurs during admission and can prevent an entire session. It is not an isolated motion-window false rejection. Physical PUF acquisition and deployment entropy are unmeasured. The provisioned-credential control remains necessary to separate this admission mechanism's cost/role from the message-authentication gate.

## 5. Intended motion and anomalous-but-authenticated streams

Frozen per-class/per-seed results show that neither SNN exceeds the conventional baselines. SNN-32 meets a predeclared performance tolerance; that is a viable temporal baseline, not superiority, energy efficiency or a neuromorphic advantage. One-tenth-amplitude nod recall is poor across models, while frozen anomaly detectors rarely alert. A small legitimate nod can resemble still without being suspicious: a wrong intended-motion decision and an anomaly alert have different operational meanings.

The historical Tier-2 plan has 50,400 cases: 44,899 quality-valid constructions and 5,501 pre-tag quality blocks, comprising 3,493 excessive timestamp gaps and 2,008 non-increasing-timestamp failures. Held-out test has 16,800 planned cases over 600 sources, 1,844 blocks and 14,956 accepted deliveries. Quality blocks occur before tagging/inference and are neither anomaly true positives nor authenticated detector misses. Per-nine-attack/three-severity detected/missed and paired motion-loss rows are retained in the [source-aware outcomes](../results/week-6/keegan/tier2-source-uncertainty/tier2-source-uncertainty.md).

The source-aware revision changes uncertainty, not points, predictions or validation thresholds. Two thousand stratified source-window bootstrap draws (seed 7027) share each source weight across its clean record, derivatives and frozen fits, conditional on six profiles, five classes and the held-out session. Mean family results are:

| Family | F1 [95% source interval] | Medium/high recall [interval] | Clean FPR [interval] |
|---|---|---|---|
| Logistic anomaly | 0.8424 [0.8383, 0.8466] | 82.85% [82.42%, 83.29%] | 5.33% [3.83%, 7.17%] |
| Forest anomaly | 0.9003 [0.8980, 0.9026] | 87.95% [87.73%, 88.19%] | 2.94% [1.78%, 4.22%] |

Medium/high recall uses 9,095 quality-valid test derivatives and clean FPR uses 600 controls, not new controls for every attack/fit. Neither meets the frozen 90% point-recall criterion; logistic also exceeds 5% point-FPR. Orientation drift is a major weakness. Zero-eligible cells are N/A; high-dropout results on four eligible cases and degenerate intervals are not general detection guarantees. Undefined resamples are recorded rather than retried. Intervals do not cover new synthetic populations, sessions, people or headset data.

## 6. Direct totals, stage accounting and one bounded optimization

The original baseline timing uses one noisy response read, BCH(63,36,t=5), a 32-bit credential and PUF seed 6767. Each of six fixed model conditions retains 20 validation warmups and 600 measured test attempts. Each admits 599/600 measured attempts: the same paired noisy failure appears across conditions and is not six independent failures. Successful-path latency is conditional on admission; failed attempts and first-use/warmup paths remain separately reported.

| Representative original configuration | Fresh first-window p50 / p95 ms | Recurring p50 / p95 ms | Accepted n |
|---|---:|---:|---:|
| LR motion / LR anomaly | 20.6127 / 31.3187 | 17.6496 / 27.7629 | 599 |
| LR motion / RF anomaly | 26.1044 / 33.3164 | 22.5875 / 30.3028 | 599 |
| SNN-32 seed 7 / RF anomaly | 55.8030 / 60.1001 | 47.4545 / 51.3985 | 599 |

All original first/recurring/after-refusal complete conditions miss 20 ms p95. Fresh adds modeled response, reconstruction, independent admission and session establishment; recurring does not repeat setup. The [stage report](../results/week-6/keegan/stage-accounting/stage-accounting.md) preserves p99/max, every root and exact exclusive partition. Nested reconstruction/verification/session, parsing/HMAC/quality, preprocessing/motion/anomaly and in-memory audit boundaries are available. Binding/sequence/locks/state and session/HKDF/confirmation residuals remain explicitly grouped, not fabricated individual timers. No stage p95 values are summed for total p95.

Will's native-verifier median 5.1700 ms covers accepted parsing/binding/HMAC/quality/order/audit/state and mutex acquisition, excluding release/inference. Historical bad-tag rejection p95 0.9814 ms is an earlier return path/instrumentation boundary. It is not the accepted authentication median and cannot replace complete-path cost.

In the original LR/LR first-window table, receiver quality p50 is 4.5545 ms, versus 0.0162 ms for HMAC. Sender serialization also checks quality. This motivates one exact-arithmetic experiment rather than more tracing. The candidate maps finite binary32 values to exact dyadic integers and preserves quality bounds/continuity/check order, parser/HMAC/state policies and model inputs. It is opt-in and not yet the default.

The new [comparison](../results/week-6/keegan/quality-benchmark/quality-benchmark.md) uses four fresh workers, two AB/BA blocks, three predeclared configurations, 30 validation warmups and 120 measured attempts/configuration/mode/block. Block 0 admits 120/120; block 1 119/120, with paired mirrored refusals retained. All 1,800 attempts, 15,126 roots, input/output/state signatures and zero rejected-model calls reconcile. Instrumentation and predeclared source/noise streams match; random session identifiers/tags legitimately differ. Only the session-ID field is neutralized in a post-timer comparison copy, never in an actual authenticated packet.

| Configuration | Matched reference recurring p95, blocks 0 / 1 ms | Candidate recurring p95, blocks 0 / 1 ms | Candidate fresh p95, blocks 0 / 1 ms |
|---|---:|---:|---:|
| LR/LR | 27.4285 / 25.1534 | 14.2551 / 15.3827 | 22.2278 / 23.4115 |
| LR/RF | 40.9905 / 41.3853 | 25.0066 / 28.9934 | 31.0356 / 35.0740 |
| SNN-32 seed 7/RF | 46.5381 / 48.6062 | 32.1141 / 40.8279 | 37.7728 / 49.9577 |

Only candidate LR/LR recurring meets the numerical target in both bounded blocks. Receiver-quality median falls to approximately 0.60-0.77 ms, from matched 5.0-5.6 ms. Other stage costs/system conditions vary, and not every paired window is faster. Compare against the fresh matched reference, not old percentiles. Two reused-source blocks do not establish a robust population timing CI. Core placement, frequency, thermals and background effects are incompletely controlled.

Automatic GC stays enabled. Four final explicit cleanup observations are 231.3012-261.7698 ms. The 12 predeclared 64-window same-session bursts complete all 768 windows; unpaced closed-loop rates are 30.876-61.203 windows/s for reference and 39.179-99.632 for candidate. Burst timing includes assertions/signatures/evidence writes but excludes admission/loading/final cleanup. Worker-wide mixed capacity separately includes cleanup; it is not recurring-only throughput. Coarse working-set/private-commit snapshots are approximately 662-716 MB / 2.045-2.096 GB, not stage peaks or demonstrated memory improvement.

Previous GC-deferral and scoped Windows observations retain cleanup and unknown residuals. Overlap supports contributions, not sole causes; tracing overhead, cache/allocation/power and some waits remain unresolved. No new tracing was used to obtain the optimization result.

## 7. Reproducibility, approval and conclusion

The [release index](week6-release-evidence.md) pins a tracked experimental commit, critical source/config bytes, original/comparison result manifests and ignored frozen payloads. Git clone alone omits the dataset/model binaries. Exact files must be trusted-transferred and hash-checked before loading; do not regenerate/refit to replace them. Will's isolated execution source and missing raw formal folders require separate closure. Latest saved full suite is 964 passing tests, not a security-completeness measure; [categories, gaps and claim-evidence-limitation table](week6-feedback-consolidation.md) accompany it.

All motion results remain cross-session synthetic evaluation with fixed profiles. Post-window time excludes the additional two-second acquisition window, physical PUF/sensor acquisition, network and durable audit. Real Quest validation requires explicit custodian/access scheduling, institutional authorization and a storage/access/retention/deletion plan, followed first by short approved logger-validation trials. No human recording or synthetic-to-headset transfer is claimed.

The original architecture's target miss is a useful measured result. One exact bottleneck reduction improves bounded timing without relaxing tested policies, but fresh and inference-heavy configurations retain practical costs. The next study must isolate the PUF-specific role, establish correlated-noise integrated availability, complete shared evidence/custody review and justify the first authorized hardware-validation step.
