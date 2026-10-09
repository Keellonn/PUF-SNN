# Preliminary results: authenticated XR motion-window software prototype

**October 8, 2026 | Keegan Hoyne and Will Wallace | Experimental snapshot `2c84cf8`**

We evaluate a reproducible software prototype, not a deployed Quest security system. A simulated noisy PUF-derived pilot credential passes independent verification and local admission before session establishment. Canonical HMAC-protected windows enforce tested binding, integrity, freshness and ordering before motion classification and separate anomaly detection. Trust also depends on independently protected verifier/admission material; the 32-bit pilot credential is not production-strength.

The evaluated prototype enforces the tested authentication and inference-release policies and offers improved nominal reconstruction reliability, but its original/default complete motion-plus-anomaly paths do not meet the provisional 20 ms p95 target. The two-second acquisition window is additional; physical acquisition, network and durable audit storage are excluded.

| Evidence | Preliminary finding | Scope / limitation |
|---|---|---|
| Current-v2 Tier-1, Will's documented formal run | Five attacks rejected 1,200/1,200 each; 34,920 measured accepted and 8,520 rejected windows have one/zero calls per consumer | Finite implementation tests, not a general forgery bound or packet-loss/DoS solution; raw formal folders unavailable in this checkout |
| Standalone independent-read reconstruction, Will's report | Majority-3 6/6,000 failures (0.10%), versus matched B0 59/6,000 (0.9833%); population-bootstrap interval 0.0167-0.2167% for majority-3 | Old nominal 1.625% uses another study; reconciliation, fresh v2 integration and correlated-noise tests remain pending |
| Original direct timing | Recurring p95: LR/LR 27.76 ms, LR/RF 30.30 ms, SNN-32/RF 50.54-54.12 ms | All original complete paths miss; successful-path quantiles condition on admission; in-memory audit/observers included |
| One bounded exact-quality optimization | Candidate recurring p95, two blocks: LR/LR 14.26/15.38 ms; LR/RF 25.01/28.99; SNN-32 seed-7/RF 32.11/40.83 | Only opt-in LR/LR recurring attains the numerical target; LR/LR fresh still 22.23/23.41 ms; default unchanged |
| Frozen Tier-2, source-aware uncertainty | Logistic F1 0.8424, recall 82.85%, clean FPR 5.33%; forest 0.9003, 87.95%, 2.94% | Both miss 90% recall; logistic misses 5% FPR; conditional on six fixed synthetic profiles and held-out session |

New Keegan revisions reconcile 29,718 original timing roots, all 50,400 Tier-2 cases and 2,000 shared source-bootstrap draws. Tier-2 retains 44,899 quality-valid cases and 5,501 pre-tag quality blocks (3,493 gaps; 2,008 timestamp-order failures), without counting blocks as anomaly successes. Legitimate small nods remain a motion/still ambiguity, not automatically suspicious. Neither SNN outperforms conventional baselines.

The paired optimization preserves exact quality rules, matching input/output/state signatures and zero inference on rejected windows. Automatic GC stays enabled. All 1,800 attempts, 15,126 roots and 768 sustained windows are retained; cleanup is separately 231-262 ms. This is bounded software evidence, not real-time deployment, physical generalization or a memory/energy advantage. GC/scheduling overlap remains evidence, not sole causal proof.

Next priorities: Will reconciles and integrates majority-3 with shared-noise testing; Will/shared provide the provisioned-credential control and key/availability review; shared work closes raw-evidence release provenance and faculty/lab/institutional decisions for approved logger-only Quest validation. Latest saved suite: 964 tests; test categories/gaps, not the count, determine coverage.

Methods and claims: [evaluation draft](paper-evaluation-draft.md), [status and limitations](week6-feedback-consolidation.md), [actual protocol](authentication-v2-protocol-spec.md), [release evidence](week6-release-evidence.md). No new human recording or slide/hour entry is asserted.
