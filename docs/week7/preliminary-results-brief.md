# Preliminary results and Week 7 update

**October 12, 2026 | Keegan Hoyne and Will Wallace | Evidence checkpoint `0895f92`**

The evaluated software prototype enforces the tested authentication and inference-release policies and offers improved nominal reconstruction reliability, but its original/default complete motion-plus-anomaly processing paths do not meet the provisional 20 ms p95 target. This is a software/synthetic study, not deployed Quest security. Independent verifier/admission material remains a separate trust dependency, and the 32-bit pilot credential is not production-strength.

| Evidence | Main finding | Limit |
| --- | --- | --- |
| Week 7 setup and selected tests | Offline Windows x64 / CPython 3.13.14 setup verified; 1,035 selected tests in 58 modules passed | Not all-module/security completeness or standalone wheel application validation |
| Separate formal-readiness diagnostic | 27 executed: 24 passed, two failures, one error; all three nonpassing tests hit the original 3.12.4 guard | Not a complete 3.13 compatibility pass; repeated attempts are not additional tests |
| Current-v2 Tier-1, Will's report | Five primary attacks rejected 1,200/1,200 each; 34,920 accepted and 8,520 rejected measured windows have one/zero calls per consumer | Finite implementation evidence, not a forgery bound or packet-loss/DoS solution; shared raw closure remains incomplete |
| Standalone reconstruction alternatives | Majority-3: 6/6,000 nominal failures (0.10%) versus matched B0 59/6,000 (0.9833%) | Old 1.625% is a different study; baseline reconciliation, fresh integration and shared-noise evaluation remain required |
| Original complete-path timing | Recurring p95: LR/LR 27.76 ms, LR/RF 30.30 ms, SNN-32/RF approximately 50-54 ms | Original/default misses; fresh-session costs are separate and higher |
| Bounded exact-quality candidate | LR/LR recurring p95 14.26/15.38 ms across two blocks | Opt-in only; LR/LR fresh still 22.23/23.41 ms; other candidate configurations miss |
| Frozen source-aware Tier-2 | Medium/high recall: logistic 82.85%, forest 87.95%; clean FPR 5.33% and 2.94% | Both miss 90% recall; logistic misses 5% FPR; thresholds remain frozen |

The added two-second acquisition window, physical acquisition, network and durable audit costs are excluded from post-window timing. Neither SNN outperforms conventional baselines. Legitimate low-amplitude nod/still ambiguity is distinct from deliberately abnormal stream corruption. Tier-2 preserves 50,400 cases: 44,899 quality-valid and 5,501 pre-tag blocks (3,493 gaps; 2,008 non-increasing timestamps), with uncertainty resampled by source rather than treating derivatives as independent recordings.

This week's new results concern setup, input receipt and implementation diagnostics, not new accuracy/FRR/latency measurements. Four missing compatibility documents and compact original formal-evidence subsets were verified; omitted raw artifacts still prevent full independent closure. Negative outcomes and historical numerical evidence remain intact. No human recording or production-security claim is made.

**Next priorities:** Will evaluates integrated majority-3 under independent/shared noise; Will/shared complete the same-policy provisioned-credential control and custody/availability review; shared work closes scoped evidence access and faculty/lab/institutional decisions for approved logger validation. Slides and the research log are not part of this reporting pass.

Details: [study status](study-status.md), [evaluation draft](evaluation-draft.md), [release status](release-status.md), [actual protocol](../authentication-v2-protocol-spec.md).
