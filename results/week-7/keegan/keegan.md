# Week 7 results: Keegan Hoyne

**Updated October 12, 2026. Reporting base:** `0895f920e29e16e6fd280f9c4b5cd3bcfb584ac3`.

## Work completed and scope

This week's completed local work consolidates reproducible environment/setup evidence, receives missing historical compatibility inputs, expands selected implementation-test coverage and records a separate interpreter diagnostic. It does not add a new motion/anomaly model, reconstruction policy, threshold, formal security/FRR experiment or pipeline-latency result. The research log and presentation are deferred.

| Checkpoint | Result | Published evidence |
| --- | --- | --- |
| Dependency/build/setup | 36 external wheels verified; 57 source/build inputs, 55 installed project files and 37 distributions checked | [Scoped setup checkpoint](release-readiness/manifest.json), publication `f0fbfb1` |
| Historical clean root scope | 964 tests passed in 54 modules | Preserved in the setup checkpoint; not added to the later 1,035 total |
| Historical input receipt | Four exact documents restored; included compact evidence/source snapshots verified | [Partial receipt](shared-handoff-receipt/README.md), `3bb91b2` |
| Expanded selected tests | 1,035 tests in 58 modules passed, zero failures/errors/skips | [Selected validation](expanded-test-validation/README.md), `e7c04a1` |
| Separate 3.13.14 diagnostic | 27 executed: 24 passed, two failures, one error; zero skips | [Partial diagnostic](reconstruction-compatibility/README.md), `0895f92` |

The expanded scope explicitly includes 7 credential-verifier harness tests, 22 reconstruction harness tests, 17 alternatives harness tests and 25 current-v2 Tier-1 tests, alongside the 964 root cases. The 27-test formal-readiness module is separate. Its first and corrected executions cover the same identities and are not additive. Legacy Tier-1-v1's 48 tests remain historical, not newly executed current-v2 validation.

## Diagnostic interpretation

The original 18-file, 80-attempt NONFORMAL fixture was privately supplied and all artifact hashes checked; it was not regenerated or published. The corrected Git context was `3bb91b2`, with the original 31-file scientific source snapshot and all 370 recorded source inputs checked byte-for-byte. Eight line-ending-only status entries were explicitly verified, not disguised as a pristine checkout.

Two initial errors came from missing Git provenance in the diagnostic scaffolding; those tests passed in the corrected run. Intermediate path-length and overstrict status checks stopped before executing repository tests. Prior attempts, failures and logs remain retained. The final three nonpassing tests stop at the unchanged explicit Python 3.12.4 guard. They do not establish an algorithm incompatibility, but the gated operations also cannot be declared compatible on 3.13.14. No original test, source pin or version restriction was edited to force a pass.

Existing clean setup/distribution metadata and installed project bytes, source and fixture bytes, model artifacts and historical results were preserved. Unit fixtures can provision synthetic enrollments and exercise authentication; this is not a full formal experiment or historical model retraining. Execution durations are not pipeline benchmarks or research-hours claims.

## What remains unchanged scientifically

- Original/default complete paths miss the 20 ms p95 target; fresh and recurring boundaries remain separate, with two-second acquisition and excluded physical/network/durable-audit costs explicit.
- The exact-quality candidate is opt-in; only LR/LR recurring meets the numerical target in both bounded blocks. No default adoption is asserted.
- Neither SNN beats conventional motion baselines. Frozen anomaly thresholds still miss the stated recall criterion; logistic also exceeds the clean-FPR criterion.
- Stage accounting, 50,400-case Tier-2 reconciliation and 2,000 source-bootstrap draws remain completed Week 6 results, not newly rerun studies.

## Shared and reporting handoff

Compact subsets verify included bytes, not full original formal-result closure: Tier-1 has 12 included primary entries and 12 omitted; alternatives has 43 included and six omitted. Majority-3 integration/shared-noise testing, the provisioned-credential control, custody/availability review, scoped raw-evidence access and hardware/human-data decisions remain separate owner/shared work. A complete shared release is not claimed.

Current reports are [study status](../../../docs/week7/study-status.md), [release status](../../../docs/week7/release-status.md), [evaluation draft](../../../docs/week7/evaluation-draft.md) and [preliminary brief](../../../docs/week7/preliminary-results-brief.md). [The reporting index](reporting-index.json) pins this documentation pass and the referenced evidence. Old manifests/checkpoint documents, code/defaults, research log and slides are unchanged.
