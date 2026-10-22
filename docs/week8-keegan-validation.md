# Week 8: Keegan's validation and optimization decision

Date: October 22, 2026. Scope: current software and synthetic inputs only.

## Decision and completed repo work

**Retain the integer quality checks as an optional research implementation.**
Behavioral evidence is stronger now, including saved-model integration with
single-read and Majority-3 setup. This is not a decision to replace the shared
default, select logistic/logistic as the final architecture, or claim that every
complete path meets 20 ms.

Completed in this working session:

1. Added six seeded differential test methods covering valid/malformed/boundary
   data, sender refusal, real receiver state and exactly-once release. See
   [expanded equivalence coverage](week8-quality-equivalence.md).
2. Added a fixed, bounded saved-model validation command, configuration and 13
   protocol/accounting test methods. No training or alert-cutoff selection.
3. Executed and reconciled the 360-session functional comparison below.
4. Prepared this decision table and a [reproduction handoff](week8-keegan-reproduction.md).

The subsequent root-discovery regression run passed **1,085 of 1,085 selected
tests**, with no failures, errors or skips. Its receipt is
`results/week-8/keegan/regression-20261022-001/summary.json`. Dependency checking
passed, current project imports were verified, and code/config hashes stayed
unchanged during execution. Ordinary root discovery excludes the non-package
`experiments`, `tier1` and `tools` test directories; this is not a declaration
that every historical study module passed. Some unit tests exercise mocked
experiment controllers or fit tiny fixture estimators; their printed counts
are not new scientific experiments or retraining of the saved models.

The starting Git commit is `c8a4053f8526b91dd856428fa0924d214f367106`. New code was
uncommitted during execution; the recorded current-file SHA-256 map, not that
base commit alone, identifies the run. This supports committing once at the end
of a work session instead of manufacturing a new commit before each check.

## New saved-model equivalence result

Result bundle:
`results/week-8/keegan/quality-validation-20261022-001/`.

| Check | Actual result |
|---|---|
| Fixed source cohort | 30 existing validation windows: six synthetic profiles × five motion labels |
| Model combinations | Logistic motion/logistic anomaly; logistic motion/forest anomaly; SNN-32 seed 7 motion/forest anomaly |
| Arithmetic modes | Original Fraction and optional exact integer comparisons |
| Acquisition policies | Existing single-read and integrated Majority-3 |
| Controlled sessions | 360 admitted; 180 original-versus-integer pairs |
| Cross-recovery comparison | 180 matched downstream comparisons |
| Accepted windows | 1,080; exactly one preprocessing/motion/anomaly call per acceptance |
| Rejection controls | 1,080; zero model calls; unchanged refusal state |
| Public behavioral signatures | Model-input fingerprints, motion predictions, anomaly scores/flags, decisions, reasons, calls and final state all matched exactly |
| Recorded response reads | 720: the declared one/three-read policies, with no retries |
| Frozen inputs | 18 artifact pins checked before and after; dataset, saved weights, normalization and thresholds retained |
| Runtime/default | Automatic GC enabled; reference aliases restored; no default change |

Each session processes a clean window, a legitimately authenticated medium
position-jump variant and a next-valid continuation. It also tests bad-tag and
replay refusal and sender rejection at 113 valid tracking samples. Structural
and quaternion-boundary coverage is supplied by the separate differential and
existing unit tests, not invented as extra cases in this functional run.

This run uses **controlled, correctable response fixtures**, not independent or
shared-noise RO measurements. Three reads are actually voted and reconstructed
through the existing pipeline, but the result establishes integration behavior,
not a recovery-success improvement or reconstruction latency. Wrong-credential
and admission-failure properties remain separate existing test coverage.

Fresh sessions retain real random nonces, IDs and keys. Public comparison rows
omit fresh event IDs only after the existing control checks verify their real
release authority. Actual authenticated packets and protocol checks are not
modified to make sessions match.

These repeated windows are not 1,080 independent recordings. No new accuracy,
anomaly recall, FRR, security-strength, timing or cross-person result is claimed.
The conventional frozen estimators are the previously saved storage refits;
this is not a recovery of the original unsaved Week 4 estimators.

## Optimization decision table

Timing below is the **existing Week 6 matched benchmark**, not remeasured by the
new functional run. All values are directly measured total-path p95 in ms.

| Motion / anomaly | Block | Original recurring | Faster recurring | Original setup + first | Faster setup + first |
|---|---:|---:|---:|---:|---:|
| Logistic / logistic | 0 | 27.43 | 14.26 | 34.62 | 22.23 |
| Logistic / logistic | 1 | 25.15 | 15.38 | 31.31 | 23.41 |
| Logistic / forest | 0 | 40.99 | 25.01 | 45.05 | 31.04 |
| Logistic / forest | 1 | 41.39 | 28.99 | 48.24 | 35.07 |
| SNN-32 seed 7 / forest | 0 | 46.54 | 32.11 | 52.69 | 37.77 |
| SNN-32 seed 7 / forest | 1 | 48.61 | 40.83 | 68.19 | 49.96 |

| Decision area | Evidence | Decision / boundary |
|---|---|---|
| Arithmetic correctness | Exact binary32 integer mapping, existing boundary tests, expanded randomized/refusal tests | Same encoded-number comparisons; no added rounding or tolerance change |
| Downstream behavior | Historical matched signatures plus new frozen-model integration in both recovery modes | Agreement observed in the declared cases; not exhaustive equivalence over every possible input |
| Recurring performance | Lower p95 for every listed configuration in both historical blocks | Only logistic/logistic recurring processing is below 20 ms |
| First-window performance | Faster logistic/logistic p95 22.23–23.41 ms | Still above 20 ms; these are single-read timing results |
| Outliers | Faster logistic/logistic first-window max 334.62 ms in block 0; faster SNN/forest block 1 first-window max 355.35 ms | A passing p95 does not imply a hard deadline or eliminate long tails |
| Majority-3 combination | New exact behavioral agreement with the saved models | No fresh combined latency measurement; do not reuse single-read timing as Majority-3 timing |
| Default adoption | Selector is still an isolated serial-worker context; shared entry-point/rollback review is not complete | Retain optional at this checkpoint; no silent production/default activation |

Historical benchmark details: 120 successful measured admissions per
mode/configuration in block 0 and 119 in block 1, with failed planned admission
reported separately. Mode order was AB then BA. Existing 64-window same-session
bursts completed for every mode/configuration/block. GC stayed enabled. Two
reused-source blocks do not establish a population performance interval.

The physical two-second acquisition window is additional. Root latency excludes
physical acquisition, network, durable audit storage, enrollment/model loading
and evidence I/O. Never sum stage medians or p95s into a complete-path p95.

Timing reference:
`results/week-6/keegan/quality-benchmark/quality-benchmark.md`.

## Model choices, thresholds and balanced conclusions

- **Algorithm choice:** logistic regression is a conventional linear baseline;
  random forest supplies a nonlinear ensemble comparison; the recurrent SNN
  tests a temporal/spiking model hypothesis on the same motion task. The SNN
  need not win for this to be a useful comparison. No neuromorphic energy or
  hardware-speed advantage was measured on the laptop.
- **Threshold choice:** anomaly alert cutoffs were selected on validation data,
  then frozen. Algorithm selection and alert calibration are different steps.
  This week's validation changes neither; it does not tune against test failures.
- **Targets:** 20 ms post-window p95, 90% medium/high recall and 5% clean false
  alerts are provisional project engineering criteria here, not demonstrated
  universal literature/clinical requirements. A motion-to-photon target would
  have a different boundary from this software processing target.
- **Different errors:** motion-label mistakes, anomaly misses and legitimate
  low-amplitude nod/still ambiguity are separate outcomes. A legitimate small
  movement is not automatically an anomaly because the motion model misses it.
- **Tradeoff:** the saved clean-motion comparison favors conventional baselines
  over either SNN. Forest anomaly detection has higher reported recall and
  fewer false alerts, but both detector families still miss the 90% recall goal.
  Fast logistic/logistic processing alone does not justify choosing it as the
  final architecture or ignoring detection performance.

## Grouping and uncertainty boundary

The new preflight checks source-window uniqueness and trial/session split
ownership across the complete saved dataset, and retains the selected original
window's identity for its changed control. It does not move derivatives into a
new split or choose sources by predicted label or successful recovery.

The existing source-bootstrap analysis groups each original test window with
all its transformed variants and reuses its resampling weight across frozen
fits. Those intervals address dependent derivatives conditional on fixed
synthetic profiles and a held-out source session. They do not establish
cross-person, new-device or real-Quest generalization. See
[source-aware uncertainty](week6-tier2-source-uncertainty.md).

## Remaining shared or external work

- A second person still needs to reproduce the documented component from its
  frozen inputs and commands; this session is not cross-person reproduction.
- Normal supported activation, lifecycle/concurrency assumptions and rollback
  require shared-owner review before any default change.
- Will's larger shared-noise/reconstruction/control analysis is separate. The
  unresolved original archive hash and stale three-arm documentation reference
  remain recorded, not changed or prerequisites for the quality check above.
- Real headset transfer and approved human-motion collection remain separate
  from the present software/synthetic evidence.

There is no need to add new model families or start another large experiment to
report this checkpoint. Its contribution is stronger equivalence evidence, a
configuration-specific optimization decision, and a reproducible handoff.
