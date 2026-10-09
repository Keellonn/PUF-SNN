# Paper outline

**Working title:** A Reproducible Software Evaluation of Simulated PUF Admission and Authenticated XR Motion Inference

**Scope:** Cross-session synthetic motion with fixed device profiles, software admission/window enforcement, and explicitly bounded reliability/performance experiments. No deployed Quest, cross-person/device transfer, production-security or SNN-superiority claim.

## Abstract claim

We study a software prototype in which simulated-PUF credential reconstruction, independent verification and trusted local admission support session establishment, while canonical HMAC-protected motion windows gate inference. We measure reconstruction failure versus miscorrection, tested stateful rejection and release behavior, conventional/SNN motion accuracy, abnormal-but-authenticated stream detection, and fresh versus recurring processing cost. Corrected synthetic data and source-aware reporting preserve the original leakage finding and limit generalization claims. The original complete motion-plus-anomaly paths miss a provisional 20 ms p95 target. Stage accounting motivates one exact quality-arithmetic optimization: only an opt-in logistic/logistic recurring path is below that target in two bounded paired blocks; fresh and forest-anomaly paths still miss. Standalone majority voting improves nominal reconstruction under independent rereads, but integrated correlated-noise reliability and a provisioned-credential control remain required. Neither SNN outperforms conventional motion baselines; both anomaly families miss the frozen recall target. These negative results define practical limits rather than justify broader security or latency claims.

## Research question

What separate roles, failure boundaries and reliability/processing tradeoffs do simulated credential reconstruction, independent admission, authenticated-window enforcement, motion inference and anomaly detection contribute in a controlled software evaluation?

## Contributions supported by current evidence

- Explicit separation of reconstruction, independent verification, local authorization, session confirmation, canonical window authentication and at-most-once release.
- Documented current-v2 attack/state/recovery evaluation and standalone reconstruction alternatives, with implementation-test security limits and independently protected secrets acknowledged.
- Corrected-generator leakage controls, complete-sequence similarity, per-class/per-seed baselines and legitimate nod/still ambiguity; no superiority-driven model search.
- Per-attack/severity accounting that preserves quality blocks and detector misses, with source-aware uncertainty and frozen thresholds.
- Direct fresh/recurring totals, per-observation stage partitions, retained outlier evidence and one bounded exact-arithmetic optimization with cleanup/resource/throughput context.
- Scoped release/input/result pins and a transparent list of missing shared evidence and hardware approvals.

These are proof-of-mechanism/software evaluation contributions, not claims of protocol novelty, a production fuzzy extractor or hardware root of trust. Window integrity and replay rejection primarily come from HMAC and verifier state; the PUF-specific incremental role is not yet isolated by the required conventional-key control.

## Evaluation questions and evidence

| Question | Available evidence | Remaining limit / question |
|---|---|---|
| How does response noise affect correct reconstruction, failure and wrong candidates? | Historical 84,000-attempt study; [standalone alternatives](week6-reconstruction-alternatives-experiment.md), 6,000 attempts/cell | Reconcile old 1.625% versus new B0 0.9833%; independent rereads do not establish correlated-noise integrated reliability |
| Can independent verification block observed wrong candidates before HKDF? | Historical 430 saved wrong candidates; controlled admission tests; [actual v2 specification](authentication-v2-protocol-spec.md) | Verifier key/local authorization are separate trust; receiver retains credential; pilot entropy/custody are limited |
| Which current-v2 attacks/state/parser cases are rejected, with what recovery? | [Tier-1 formal report](week6-tier1-v2-experiment.md), five groups of 1,200, documented callback/state accounting | Raw evidence not in this checkout; complete experiment device/session/repetition mapping and review remain; exact-next policy stalls on packet loss |
| Is corrected motion near-identical to training? | Preserved original leakage, corrected orientation/full 120 x 7 nearest-training audit | Similarity checks do not establish real-world transfer or universal leakage absence |
| What is motion-model performance and nod/still ambiguity? | Frozen per-class/per-seed confusion metrics, all-seed curves and nod diagnostics | Neither SNN wins; small nods are legitimate/ambiguous and do not require an anomaly alert by definition |
| Which altered streams pass quality, degrade motion and evade anomaly detection? | Historical 50,400-case plan; [source-aware report](../results/week-6/keegan/tier2-source-uncertainty/tier2-source-uncertainty.md), 600 sources/2,000 draws | Both recall targets miss; LR FPR misses; conditional fixed-profile/session intervals; historical gate is not relabeled v2 |
| Which application stages dominate direct fresh/recurring latency? | [Saved stages](../results/week-6/keegan/stage-accounting/stage-accounting.md), every original root partition reconciled | Some sequence/handshake operations remain grouped; no stage-percentile summation; no physical/network/durable audit |
| Can one exact bottleneck be reduced without policy/output changes? | [Paired quality benchmark](../results/week-6/keegan/quality-benchmark/quality-benchmark.md): 1,800 attempts, 15,126 roots, 768 sustained windows | Candidate opt-in; two blocks/reused sources; only LR/LR recurring below target, fresh/forest paths not |
| What incremental benefit/cost does PUF admission add over provisioned credentials? | Protocol boundary and admission costs are characterized | Matched provisioned-random-credential control is still pending; do not infer a benefit from HMAC rejection alone |

## Paper structure

1. Introduction: narrow research question and the explicit target-miss conclusion.
2. Architecture/threat model: message and enrollment formats, independent verifier/admission secrets, release authority, pilot credential, exact-next availability limitation and conventional-key control rationale.
3. Methods: generator correction, fixed-profile session splits, seed roles, frozen models/thresholds, per-experiment populations, source dependence, timer boundaries and artifact pins.
4. Evaluation: [draft section](paper-evaluation-draft.md), with original runs distinguished from retrospective reporting and the new bounded comparison.
5. Discussion: integrity versus admission/packet-loss availability, intended-motion error versus anomaly alert, remaining inference cost, PUF-specific role and honest unmet criteria.
6. Limitations/reproducibility: local custody, source dependence, pilot entropy, missing raw shared evidence, ignored frozen inputs, timing/excluded costs and approved hardware validation.
7. Conclusion: bounded results and the few remaining practical decisions; no unmeasured platform/generalization claim.

## Figures and tables

- Architecture/key-boundary figure based on the actual v2 specification; distinguish credential-verifier HMAC from per-session window authentication, trusted local authorization and committed at-most-once release.
- One consolidated Tier-1 table: primary, state/parser, setup/control/recovery counts, versions/execution source, device/session/repetition counts, variation/reasons/calls/state/recovery and interval assumptions. Missing raw metadata must be resolved, not invented.
- Reconstruction table: B0/majority-3/majority-5/stronger BCH, exact failures/attempts, intervals, wrong candidates/verification refusals, reads, latency and 32-versus-30 variable credential bits. Do not silently reconcile baseline populations or claim zero underlying failure probability.
- Motion table/figures: frozen per-class/per-seed results, confusion matrices and nod/still trajectories/curves, with intended label and physical/synthetic units.
- Tier-2 table: all quality-valid/blocked/detected/missed cases by nine attacks x three severities; source-aware intervals, clean FPR and paired motion loss. Zero eligible is N/A, not zero recall.
- Stage table: three representative configurations, directly measured fresh/recurring totals and inclusive/exclusive stage definitions. Residuals are explicit, not fabricated substage measurements.
- Bounded optimization table: separate blocks/modes/sample sizes, direct p50/p95/p99/max, pair deltas and unchanged outcomes; add cleanup, burst/mixed capacity and resource context. Keep opt-in/default distinctions.
- [Required status and claim-evidence-limitation tables](week6-feedback-consolidation.md).
- Appendix only: established model setup, historical PUF plots, original leakage and historical motion-only timing; detailed GC/Windows cases retain uncertainty rather than drive another tracing campaign.

## Seed and uncertainty rules

Data generation seed 7 fixes one dataset; Session 1/2/3 split is deterministic. LR lbfgs fitting is deterministic here, so five repeated fitting seeds are not five independent performance samples. SNN initialization 7/17/27 and training/shuffle 107/117/127, attack seed 5007, anomaly fits 6007/6017/6027 and source-bootstrap seed 7027 have different roles. Model repeats do not create new recordings.

Tier-2 resamples 600 source windows jointly with all derivatives/fits within fixed device/class strata, using 2,000 shared draws. Reconstruction population intervals from Will's standalone report cluster complete simulated populations. Tier-1 binomial intervals are descriptive under sampling assumptions and dependence limits, not cryptographic-security bounds. Two paired timing blocks are descriptive and do not supply a robust population CI. Seeds and parameters are never tuned on held-out test data.

## Required limitations and missing studies

- Cross-session synthetic evaluation with fixed profiles; no cross-person/device, headset, energy or real-world transfer claim.
- Original generator leakage remains preserved as methodological evidence.
- Different reconstruction baseline studies require reconciliation; majority-3 integration/shared-noise tests and the provisioned-credential control are pending.
- Independent key custody/local admission are trusted; a receiver registry retains the credential; no production keystore, process isolation, secure erasure or 32-bit security-strength claim.
- Finite Tier-1 rejection/state results do not prove the protocol secure; missing traffic can block exact-next progress without application recovery.
- Quality blocks are separate from anomaly successes; authenticated semantic abnormality can remain a detector miss. Both frozen recall targets and LR FPR remain unmet.
- SNN tolerance is not superiority. Legitimate low-amplitude nod ambiguity is not automatically anomaly failure.
- Original/default complete timing misses 20 ms; only bounded opt-in LR/LR recurring attainment is observed. Acquisition, network and durable storage are excluded; GC cleanup/system costs remain real.
- GC/scheduling overlap is evidence rather than sole causation; tracing overhead/cache/allocation/power effects are incompletely isolated.
- Actual shared formal raw evidence and execution snapshots must accompany reproducible review. Human recording requires explicit lab/institutional authorization and a logger-validation plan.

The [release-evidence index](week6-release-evidence.md) and [preliminary brief](preliminary-results-brief.md) are submission entry points. This outline is not a claim that every missing experiment or slide update is complete.
