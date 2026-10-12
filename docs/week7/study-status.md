# Week 7: consolidated study status

**Updated October 12, 2026. Evidence checkpoint:** `0895f920e29e16e6fd280f9c4b5cd3bcfb584ac3`.

Week 7 work so far establishes a tested Windows dependency/setup profile, restores missing historical inputs, expands explicitly selected test coverage and records a separate, partially passing interpreter diagnostic. It adds no new motion-accuracy, anomaly-recall, reconstruction-FRR or formal pipeline-latency result. This reporting pass changes no model, threshold, protocol default, historical experiment, research log or slides.

## Current conclusion

The evaluated software prototype enforces the tested authentication and inference-release policies and offers improved nominal reconstruction reliability, but its original/default complete motion-plus-anomaly processing paths do not meet the provisional 20 ms p95 target.

The reconstruction improvement comes from the standalone alternatives study, not an integrated majority-3 v2 result. Only the separate opt-in exact-quality candidate's LR/LR recurring path meets the numerical latency target in both bounded blocks; fresh and forest-anomaly paths still miss. Two-second acquisition is additional. Physical acquisition, network transmission and durable audit storage remain excluded. Neither SNN outperforms the conventional baselines.

## What changed this week

| Completed checkpoint | Observed result | Claim boundary |
| --- | --- | --- |
| Hash-pinned observed dependency profile | 36 external wheels verified; static dependency closure checked | Windows x64 / CPython 3.13.14 profile, not every platform or historical training environment |
| Offline build and installation | 57 source/build inputs, 55 installed project files, 37 distributions checked | Supported source-checkout workflow; standalone installed-wheel application operation remains unvalidated |
| Original clean root discovery | 964 tests in 54 modules passed, no failures/errors/skips | Historical scope retained; not all repository folders |
| Expanded selected validation | 1,035 tests in 58 modules passed: 964 root plus 71 explicitly discovered supplemental tests | Separate execution at `3bb91b2`, not 964 + 1,035 new tests or security completeness |
| Exact compatibility-document receipt | Four missing documents restored with their original byte hashes | Receipt is not approval of new plans or a rerun of their experiments |
| Shared formal-evidence receipt | Included compact-subset artifacts and source snapshots verified | Full raw-evidence closure and independent raw-outcome recomputation remain incomplete |
| Reconstruction formal-readiness diagnostic | All 27 tests executed on 3.13.14: 24 passed, two failures, one error; zero skips | The three nonpassing tests stop at the unchanged historical 3.12.4 guard; not a complete compatibility pass |

The 71 supplemental tests are credential-verifier harness 7, reconstruction harness 22, alternatives harness 17 and current-v2 Tier-1 harness 25. The 27-test diagnostic is a different module and its repeated attempts are not additive. Legacy Tier-1-v1's 48 tests remain Will-reported historical evidence; they are not newly validated current-v2 tests. The exact historical legacy source remains incompletely recovered.

The private 80-attempt NONFORMAL fixture supplied the original inputs for the diagnostic. No replacement fixture was generated, version guard relaxed, formal experiment run or historical model retrained. Earlier setup/test failures were retained and distinguished from scientific results. The final diagnostic corrected missing Git context and preserved exact source bytes, including eight verified line-ending representations.

## Targets and remaining questions

| Requirement | Current status | Remaining action / owner |
| --- | --- | --- |
| Tested current-v2 authentication/release policies | Observed tested cases pass; current-v2 harness included in 1,035 | Will/shared: complete evidence/custody review; retain finite-test and availability limits |
| Nominal admission reconstruction FRR | Standalone alternatives meet observed target; integration provisional | Will: reconcile old/new baselines, integrate majority-3 and evaluate independent/shared noise |
| Complete-path p95 <=20 ms | Original/default not met | Keep fresh/recurring costs separate; exact-quality default adoption needs owner review |
| Medium/high anomaly recall >=90% | Not met; logistic also exceeds the clean-FPR criterion | Preserve frozen thresholds and source-aware per-attack interpretation; no test-set retuning |
| Reproducible shared release | Local setup and selected implementation checks supported; shared closure incomplete | Will/shared: remaining original raw artifacts or an explicitly reviewed evidence-access boundary |
| Python 3.13 formal-readiness support | Partial diagnostic only | Decide whether to version/revalidate support or retain historical 3.12.4 execution; do not force a pass |
| Real Quest / human-data validation | Pending; no human recording claimed | Faculty/lab: custodian, access schedule, institutional authorization and data-handling decisions |

## Next three priorities

1. **Will:** integrate the provisional majority-3 candidate and evaluate nominal plus controlled shared/correlated noise, with failure counts, uncertainty, wrong candidates, verifier refusals, credential format and latency together.
2. **Will/shared:** complete the same-policy provisioned-random-credential control and key-custody/packet-loss review. The control must hold data, models, HMAC/message format and verifier policy fixed.
3. **Shared reporting:** close the scoped release/evidence-access decisions, review the evaluation draft and preliminary brief, and request specific faculty/lab/institutional decisions for an approved logger-validation session.

Keegan's completed stage-accounting, source-aware Tier-2 and bounded bottleneck work remains Week 6 evidence. Current local validation/reporting can be handed off without more tracing, architecture search or automatically rerunning these studies. Slides and the research log are intentionally deferred.

Read: [current release status](release-status.md), [current evaluation draft](evaluation-draft.md), [preliminary brief](preliminary-results-brief.md), [selected-test evidence](../../results/week-7/keegan/expanded-test-validation/README.md), [partial diagnostic](../../results/week-7/keegan/reconstruction-compatibility/README.md).
