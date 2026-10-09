# Week 6 feedback consolidation and study status

**Revision date:** October 8, 2026. **Experimental snapshot:** `2c84cf8394bd444188291e254bbf1ddde3cc8661`.

This is a reporting revision. It changes no trained model, threshold, original run, authentication default or research-hour entry. The actual protocol and Will-side reports are supplied below; their formal raw-evidence folders are not present in this checkout and are not claimed to have been independently verified here.

## Explicit conclusion

The evaluated software prototype enforces the tested authentication and inference-release policies and offers improved nominal reconstruction reliability, but its complete motion-plus-anomaly processing paths do not meet the provisional 20 ms p95 target.

That conclusion refers to the original released/default complete paths. Reliability improvement is reported by the separate reconstruction-alternatives study, not by the integrated single-read timing cohort. A bounded opt-in quality-arithmetic candidate subsequently puts only LR/LR recurring p95 below 20 ms in both paired blocks; its fresh path and forest-anomaly paths still miss. The default remains unchanged. Do not carry historical motion-only attainment forward or call the architecture low-latency without its boundary and unmet requirement.

The two-second motion-acquisition window is additional. Physical sensor/PUF acquisition, network transmission and durable audit storage remain excluded. Session setup is separate from recurring processing and affects startup/recovery. Timing includes in-memory audit and observer work, not a production transport or hard deadline.

## Required status table

| Requirement | Current status | Evidence | Next action |
|---|---|---|---|
| Current-v2 Tier-1 rejection | Observed tests pass in Will's documented run | [Attack/state report](week6-tier1-v2-experiment.md): five groups of 1,200; state/parser/recovery counts | Finalize experiment metadata, uncertainty assumptions, protocol/key review and raw-evidence release closure |
| Nominal reconstruction FRR | Standalone alternatives pass observed nominal target | [Reconstruction comparison](week6-reconstruction-alternatives-experiment.md): majority-3 6/6,000; baseline 59/6,000 | Reconcile old/new baselines; integrate majority-3 provisionally and test shared/correlated noise |
| Complete-path p95 <=20 ms | Original/default not met; bounded LR/LR recurring candidate only is below target | [Original stages](../results/week-6/keegan/stage-accounting/stage-accounting.md); [paired comparison](../results/week-6/keegan/quality-benchmark/quality-benchmark.md) | Review exact-quality candidate for default adoption; keep fresh and other configuration misses explicit |
| Medium/high anomaly recall >=90% | Not met; logistic also exceeds 5% clean FPR | [Frozen, source-aware outcomes](../results/week-6/keegan/tier2-source-uncertainty/tier2-source-uncertainty.md) | Interpret per-attack/severity failures without retuning test thresholds |
| Real Quest validation | Pending; no human recording | Synthetic-only evidence and logger development | Resolve faculty/lab access and institutional authorization; start with approved logger validation |

## What changed in this revision

- Reconciled every original timing root and exclusive stage partition without another original benchmark: 29,718 roots, 3,720 attempts, unchanged quantiles and refusal outcomes.
- Reconciled all 50,400 Tier-2 cases and frozen points, then resampled sources with their derivatives and fitted-seed predictions together: 600 test sources, 2,000 draws, 168 detector and 252 motion-condition rows.
- Tested one application bottleneck: exact Fraction-to-dyadic quaternion-quality arithmetic. Four fresh AB/BA workers, 1,800 admission attempts, 15,126 roots and 768 sustained windows reconcile; rejected traffic still invokes no models.
- Retained default misses, failures, first uses, cleanup and resource observations. Only opt-in LR/LR recurring candidate attains the numerical target in this bounded cohort.
- Added a paper evaluation draft, preliminary brief and scoped release/evidence index. Earlier leakage, trained artifacts, thresholds and negative findings remain preserved.

## Claim-evidence-limitation table

| Claim | Evidence | Limitation |
|---|---|---|
| Tested current-v2 traffic is refused before inference when required | Will documents 34,920 measured accepted and 8,520 rejected windows, with one/zero consumer calls respectively | Finite implementation tests; trusted-process assumptions; not a cryptographic forgery bound, proof of protocol security or DoS availability |
| Independent verification prevents observed wrong candidates reaching derivation | Saved Week 5 miscorrection replay and controlled integration tests; actual [specification](authentication-v2-protocol-spec.md) | Separate protected verifier secret/admission service; receiver also retains enrolled credential; 32-bit pilot is not production-strength |
| Repeated independent reads improve nominal reconstruction in the standalone simulator | Majority-3 6/6,000 versus matched B0 59/6,000; documented uncertainty | Independent rereads, noiseless enrollment and different population from old 1.625% study; correlated noise and integrated FRR pending |
| Exact quality arithmetic reduces a measured application cost | Paired quality comparison: receiver quality median roughly 5.0-5.6 to 0.60-0.77 ms, matching public input/output/state signatures | Candidate is opt-in; two paired blocks/reused sources; other stage/system costs vary; not every window is faster |
| Original/default complete latency misses 20 ms | Direct original recurring p95 27.7629 ms LR/LR; SNN/RF 50.5355-54.1160 ms | Instrumented CPU boundary, conditional on admission; excludes acquisition/network/durable storage |
| Source-aware Tier-2 results miss the frozen recall criterion | Logistic 82.85%, forest 87.95% medium/high recall, source-cluster intervals | Conditional on fixed synthetic profiles/session; attacks are not independent transformed recordings; quality blocks are separate |
| Neither SNN beats conventional motion baselines | Preserved per-class/per-seed evidence and nod/still diagnostics | Meeting a tolerance is not superiority, energy efficiency or hardware advantage; small nods are legitimate ambiguity |
| Outlier evidence supports some GC and ready-delay contributions | Preserved observer experiment and sanitized Windows partitions | Overlap is not sole causation; tracing overhead and allocation/cache/power causes remain unresolved; no new tracing required |

## Tests: properties and gaps, not a security score

Latest saved full-suite checkpoint: **964 passing tests in 100.599 seconds**, at quality-benchmark source `bddce50198d68b851f648d45638aa06d9eea152c`. The 834-test count is an earlier checkpoint. This documentation-only revision does not claim a new test run.

| Category / recorded evidence | Tested properties | Remaining gap |
|---|---|---|
| Codec/parser, quality and protocol state tests | Canonical binary32/messages, quality boundaries, tags, bindings, sequence and lifecycle refusal | Not exhaustive parser fuzzing, network loss/reordering, concurrency/resource exhaustion or formal protocol verification |
| Credential and composite-consumer tests | Independent pre-HKDF gate, no consumer on refusal, at-most-once release, callback failure behavior | No hostile-process isolation, production custody, secure erasure or physical PUF attestation |
| Frozen loader and model/reporting tests | Manifest/path checks, training-only normalization, frozen thresholds, class/count/seed reconciliation | Does not establish physical transfer, model robustness or representativeness of synthetic motion |
| Stage accounting: 31 focused tests | Contained spans, disjoint partitions, directly measured totals and refusal/quantile reconciliation | Some binding/sequence/HKDF/confirmation operations remain grouped remainders |
| Tier-2 uncertainty: 30 focused tests | Source/split ownership, shared derivative weights, frozen-point reconciliation and empty-cell handling | Conditional source bootstrap; no new independent session/person/device population |
| Exact quality candidate: 26 focused tests | Exact finite-binary32 equivalence and threshold/sign/order edge cases | Finite tests supplement arithmetic reasoning; owner review and deployment validation remain required |
| Paired benchmark: 28 focused tests | Paired outcomes/state, failures, sustained final-session policy, cleanup/partition/hash controls | Two bounded blocks are not a general performance confidence bound or concurrent load test |
| Windows accounting/reporting: 43 historical focused tests | Scoped numeric accounting, lifetime/partition validation and privacy filters | Native schema/causal isolation limits remain explicit; raw OS traces stay private |

## Ownership and next three priorities

1. **Will:** reconcile reconstruction baselines, integrate majority-3 into a separately versioned v2 evaluation, and compare independent and shared/correlated measurement noise. Keep denominators, wrong candidates, verifier refusals, credential length and timing together.
2. **Will/shared:** provide the same-policy provisioned-random-credential control and complete key-custody/Tier-1 metadata/raw-evidence review. Key-control results must isolate PUF admission cost from HMAC/state gating and inference, not change models or data.
3. **Shared, with Keegan reporting:** close the reproducible release evidence, review the evaluation draft and brief, and resolve the specific hardware/approval decisions below. Keegan's stage/source-aware/one-bottleneck experiments are complete; default optimization adoption remains a separate owner decision.

The actual [v2 specification](authentication-v2-protocol-spec.md) exists and must accompany review. Its co-located trusted authorization and key providers are software assumptions, not remote attestation. Packet loss can stall exact-next-sequence progress; the documented S6 recovery supplies missing traffic and retries the retained packet. The implementation does not automatically buffer, retransmit or resynchronize.

Will's raw Tier-1 and alternatives result folders are missing from this checkout. The public reports identify their source snapshots/manifests, but the consolidated index is not a declaration that a fully verified shared release is complete. Use the exact-byte snapshot/manifest for the isolated Tier-1 execution commit, not just current main.

## Faculty/lab decisions requiring action

- Name the Quest/lab custodian, determine who may borrow/use it, and schedule a short logger-validation session; identify the actual development/runtime access granted.
- Obtain the institution's determination of whether short scripted motion from approved test users requires review/consent and specify the authorization needed before recording. Do not decide exemption locally or record while authorization is unresolved.
- Approve permitted fields and identifiers, storage location, access list, retention/deletion schedule and handling of transfers/backups. No unnecessary personal identifiers.
- Agree that the first authorized use is logger validation: measured sample rate/gaps, tracking validity, quaternion norm/sign continuity, real schema compatibility and realistic motion amplitude/timing. This is not yet a full dataset study.

Software/synthetic work can continue while these decisions are requested; their current status must remain explicit. Do not claim that synthetic results transfer to Quest data before that validation.

## Presentation handoff

Use a short update: changes this week, new numbers, targets met/missed, unresolved decisions and the three priorities. Include the status table above. Move established setup, original PUF plots and historical motion-only timing to an appendix. Slides and speaker notes are not changed by this Markdown package, and slide work is not recorded as completed here.
