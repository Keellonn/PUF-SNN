# Paper Outline

**Working title:** A Reproducible Software Evaluation of Simulated PUF-Derived Admission and Authenticated XR Motion Inference

**Scope:** Current synthetic software results and their limitations; not a claim that PUF plus SNN secures a deployed Quest headset.

## Abstract claim

We study a reproducible software prototype for authenticated XR motion-window processing. A simulated noisy PUF response supplies a reconstructed credential; independent credential verification and trusted local admission gate session-key derivation; canonical HMAC-protected windows enforce binding, integrity, freshness and ordering before inference. Separate experiments characterize reconstruction failure/miscorrection, admission checks, Tier-1 traffic rejection, conventional/SNN motion classification, and anomaly detection for defined pre-tag semantic changes. Corrected synthetic-data diagnostics preserve the original leakage finding and limit claims to cross-session evaluation with fixed simulated device profiles. Observed miscorrection blocking is distinct from unresolved reconstruction availability, and authentication does not make correctly tagged semantic changes benign. Conventional classifiers remain more accurate than the compact SNN; both anomaly families miss the predeclared medium/high recall target. Existing recurring-window timing is not fresh noisy-response-to-first-window v2 latency or a hardware deployment result.

## Research question

How do reconstruction reliability, independent pre-HKDF admission, authenticated-window enforcement and downstream inference interact, and what tradeoffs and failure boundaries can a controlled software evaluation establish?

## Contribution bullets

- A reproducible, stage-separated experimental pipeline with explicit credential, session, window-verification and inference boundaries.
- A reconstruction/miscorrection study and independent pre-HKDF verification experiment that distinguish integrity from legitimate-admission availability.
- Canonical binary-window validation, stateful replay/order enforcement and tested at-most-once accepted-event consumption without claiming guaranteed callback completion.
- Corrected-data leakage controls, complete-input similarity analysis and per-class/per-seed conventional/SNN comparison with bounded conclusions.
- Split-preserving Tier-2 accounting and frozen conventional anomaly calibration, including quality/construction blocks, detector misses and intended-motion ambiguity.
- Explicitly scoped workstation timing and preserved negative findings; fresh end-to-end v2 timing remains required before a stronger systems claim.

These are measured software/pilot contributions, not claims of protocol novelty, a production fuzzy extractor, a physical hardware root of trust, SNN superiority or general-purpose attack immunity.

## Evaluation questions and existing evidence

| Question | Current evidence | Limit / further required evidence |
|---|---|---|
| How does response noise affect reconstruction and miscorrection? | `docs/layer2-formal-evaluation-week5.md`: frozen 84,000-attempt study, nominal FRR 1.625%, 430 total valid-format wrong candidates | Nominal availability misses the clarified <=0.5% goal; controlled majority/stability/code alternatives remain Will-side work. Do not pool noise conditions into one operational rate. |
| Does independent admission stop wrong candidates before HKDF? | `docs/credential-verifier-formal-results-week5.md`: 430 saved miscorrections blocked, 120 positive integration controls | Saved-population reuse and trusted local authorization; precise enrollment/key/threat specification and fresh noisy-input timing must remain explicit. |
| Which Tier-1 mutations are rejected, with what state effects? | `docs/tier1-results-attacks.md`: five groups of 100 observed rejections, 100 legitimate accepted controls; software/parser/integration tests elsewhere | Expanded >=1,000 varied trials/type, exact binomial intervals, state-poisoning/parser cohorts and zero-consumer instrumentation are not supplied by Keegan's reporting addenda. |
| Are corrected query sequences duplicates or near copies of training? | `results/week-5/keegan/sequence-neighbors/`: exact orientation metric plus complete 120 x 7 normalized RMS, 2,400 query/scope rows; original leakage retained | Similarity is not a physical transfer or universal no-leakage proof; all splits share fixed synthetic device profiles. |
| What are the accuracy/complexity tradeoffs among LR, RF and SNN widths? | `results/week-5/keegan/model-evidence/`: per-class/per-seed counts, curves, stopping rules, equations and measured artifact sizes | SNN-64 misses the five-point tolerance; SNN-32 meets it but neither beats LR/RF. No energy/hardware advantage or new model search. |
| When does nod resemble still, and is it falsely flagged? | `results/week-5/keegan/nod-diagnostics/`: fixed amplitude/speed curves, nominal/observed units, paired trajectories and frozen detector flags | Legitimate variation/ambiguous intended labels; historical aggregate classifier data does not give joint per-case classifier/detector outcomes. |
| Which pre-tag changes pass quality checks, degrade classification and evade detection? | `results/week-5/keegan/tier2-breakdown/`: all 50,400 cases, 5,501 pre-tag blocks, nine attacks x three severities, detected/missed counts and conditional intervals | Both detectors miss 90% medium/high recall; LR also misses 5% clean test FPR. Freeze cues, shared ranges and synthetic supervision remain limitations. |
| What is accepted/rejected post-window and fresh session-to-first-window latency? | `results/week-4/shared/pipeline-benchmark/`: recurring-window timing, LR/SNN-64 accepted p95 below 20 ms, RF above; large maxima retained | Fresh v2 end-to-end accepted/rejected timing, p99, controlled timing conditions/outlier diagnosis and detector-inclusive/durable-audit costs remain outstanding. Never add nested percentiles or archived/current composites into a fresh total. |

## Proposed paper sections

1. Introduction: the distinction between authenticated origin/order and semantic sensor validity; bounded research question.
2. System and trust model: simulated PUF, reconstruction, independent admission, session establishment, Wire 2.0, verifier-owned state and accepted inference boundary.
3. Methods: fixed synthetic generator/splits, leakage correction, mathematical metrics, seed roles, frozen model/threshold selection, attack boundaries, case accounting and uncertainty assumptions.
4. Results: reconstruction/admission first; Tier-1 rejection/state evidence; conventional/SNN inference and nod ambiguity; Tier-2 blocks/misses; separately scoped timing.
5. Discussion: integrity versus availability, synthetic shortcuts/ambiguity, SNN tolerance versus actual advantage, negative findings and remaining systems evidence.
6. Limitations and reproducibility: grouped dependence, local trust, prototype credential/security assumptions, missing deployment/human data, manifests and artifact reuse.
7. Conclusion: what the recorded experiments establish, and what remains unmeasured.

## Figures and tables

- System/key-boundary figure: distinguish the independent credential-verification key/HMAC from per-session window keys/HMACs; show all fail-closed branches and committed sequence before at-most-once release. Final key/enrollment details require Will's specification.
- Leakage figure/table: original zero-distance orientation result alongside corrected orientation and complete-input distances, with exact units/alignment/scaling.
- Conventional/SNN comparison: per-class/per-seed confusion evidence and macro-F1; all three training/validation histories for each SNN width. Do not present repeated sources as independent pooled trials.
- Nod/still figures: existing `test-motion-sensitivity.png`, `paired-amplitude-trajectories.png` and `test-anomaly-flags.png`; state nominal coefficients and legitimate-variation interpretation.
- Tier-1 table: exact counts, varied-trial definitions, rejection reasons, intervals and downstream invocation counts; distinguish current 100-trial evidence from the required expanded study.
- Reconstruction table: credential length, BER, reads, code capability, FRR, miscorrection, verifier rejects, fresh reconstruction-plus-verification time and entropy limitations for each controlled alternative.
- Tier-2 tables: planned/eligible/blocked counts, per-type/severity detection/misses/clean FPR and paired motion loss. Zero-eligible conditions are N/A; four-case high dropout is not strong population evidence.
- Timing table: p50/p95/p99/max, measurement conditions/exclusions and outlier categories for fresh accepted/rejected v2 paths. Label existing recurring-window figures separately.

The unreached experiments above remain requirements, not completed figures or invented results. Existing generated addenda and their manifests remain unchanged.

## Reproducibility and seed roles

The frozen 1,800-window dataset SHA-256 is `752b009588f3e721a8bf2f8f8fcd1cdf0f7e998446b60953dd34dd5e9e54d661`. Generation seed 7 fixes one dataset; Session 1/2/3 assignments use no RNG. Conventional fitting seeds, SNN initialization 7/17/27 and training/shuffle 107/117/127, attack seed 5007, detector seeds 6007/6017/6027 and interval/reporting seeds have different roles. Deterministic LR lbfgs fitting explains zero seed SD. Model repeats do not create new recordings. Preserve exact commands, configurations, source/data/artifact hashes and environment in the per-run manifests. Local model binaries are omitted from Git and require the documented trusted reproduction path.

## Limitations that must remain in the paper

- Synthetic cross-session evaluation with six fixed simulated device profiles; no cross-device, cross-person or real Quest transfer.
- Original template leakage remains in the research log/methods appendix as evidence of pipeline correction, not silently deleted.
- Nominal reconstruction FRR remains 1.625%; blocking wrong credentials does not recover legitimate failed admissions.
- Prototype credential/helper/enrollment entropy and independent-key/local-service trust must be specified; do not call this a production fuzzy extractor or hardware root of trust.
- Observed Tier-1 rejection is a finite software result, not a guarantee.
- Quality-valid pre-tag anomalies can authenticate normally; anomaly scores never rewrite authentication or roll back committed state.
- Construction blocks are pre-inference quality-policy outcomes, not anomaly true positives; detector recall is conditional on eligible cases.
- Both anomaly detectors miss the unchanged recall target; no post-test threshold lowering.
- SNN-32 meets a project tolerance, not conventional-model superiority, energy efficiency or neuromorphic advantage; no further architecture expansion yet.
- Existing post-window p95 observations are not hard deadlines; RF misses 20 ms and large maxima remain unexplained. Fresh end-to-end/detector/durable-audit timings are not established.
- No human recording or full data-collection study before required approval and a narrowly scoped logger-validation/storage protocol.
