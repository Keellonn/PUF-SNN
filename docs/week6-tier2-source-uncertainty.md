# Week 6 revision: source-aware Tier-2 uncertainty

This is reporting of the frozen Week 5 experiment, not a new attack or current-v2
experiment. Original predictions, calibration, thresholds and source artifacts
are read-only. The historical motion SNN is SNN-64; newer v2 timing used SNN-32.
Historical authenticated delivery evidence predates the current v2 independent
credential-verification integration and must retain that boundary in reporting.

## What the revision adds

- Exact per-attack/severity/seed quality blocks, accepted cases, anomaly detections
  and misses, clean false positives, and motion degradation.
- Source-aware intervals for detector recall, FPR, precision and F1, including
  pooled conditions, plus paired motion-accuracy loss.
- Shared source weights across every transformation, matched clean control and
  frozen fit; model seeds do not multiply the number of independent sources.
- Explicit zero/tiny-denominator and degenerate-interval flags.
- Replayable source multiplicities, input/code hashes and completion checks.

## Fixed historical input

Input: `results/week-5/keegan/stream-evaluation`.

The manifest is pinned to
`8c053eadacf67c97f4d886a8116df17f185afb818d2e25439090fb7d7275f13e`
and COMPLETE to
`7f6b319dc09b8d85a9ff47c9c8110ddc96ebf5c8fade134640dd02d0bf5bc4cb`.
The existing saved-file loader reconciles nine hashed inputs, source ownership,
all planned conditions, frozen validation thresholds, paired predictions and
accepted-delivery records. It is loaded directly, bypassing the attack package's
eager generator imports. No raw dataset or model binaries are required.

All splits: 50,400 planned; 44,899 quality-valid; 5,501 blocked before a tag.
Reasons: 3,493 excessive timestamp gaps and 2,008 non-increasing timestamps.
Test: 16,800 planned; 14,956 quality-valid and authenticated accepted; 1,844
pre-tag blocks (1,160 gap, 684 order). The 600 test source windows each have one
clean control and 27 transformations (nine attack types, three severities).

A quality block has no model prediction: it is neither a detector true positive
nor an authenticated detector miss. Conditional detector recall excludes those
cases, while planned counts and reasons keep them visible. All quality-valid
test cases were accepted in the historical authenticated branch; zero verifier
rejections is not a new Tier-1 result or security guarantee.

## Statistical unit and registered reporting settings

Fixed settings: 2,000 bootstrap draws; PCG64 seed 7027; 95% percentile interval;
NumPy quantile method `linear`. These settings concern reporting only and do not
select models or thresholds using the test set.

Cluster unit: one original source window. The loader verifies exactly one window
per trial; multiple windows per trial would require a new trial-cluster method.
Resample source windows with replacement independently within fixed synthetic
profile / source-session / motion-class strata. There are 30 test strata, with
20 sources each, from six fixed profiles and Session 3. Training/validation/test
remain Sessions 1/2/3, and no derivative crosses splits.

For draw b and source i, let w[b,i] be its sampled multiplicity. Reuse that same
weight for its quality outcomes, every transformed case, clean reference and all
frozen fits. For an attack subset A, detector recall is:

`sum_i w[b,i] * sum_a_in_A eligible[i,a] * flagged[i,a]`
divided by `sum_i w[b,i] * sum_a_in_A eligible[i,a]`.

Clean FPR is weighted clean false positives divided by 600 weighted sources.
For a condition, paired motion-accuracy loss is the weighted sum of
`eligible * (clean_correct - transformed_correct)` divided by weighted eligible
sources. Each transformed comparison uses clean predictions from exactly the
same eligible subset, not the entire clean population.

Detector precision/F1 use weighted TP/FP/FN. Family summaries average the three
fixed fit metrics within each shared bootstrap draw. They do not pool fits as
independent trials or estimate uncertainty over independently retrained models.
Motion macro-F1 and its loss remain descriptive points; only paired accuracy
loss has a motion interval here. Fixed five-class macro-F1 assigns absent-class
F1 zero, consistent with the historical reporting recipe.

## Interpretation and limits

Intervals are conditional on the fixed profile/session/class composition and
assume exchangeable independently generated source trials within strata. They
address shared derivatives and paired fits, not new people, devices, real Quest
motion, independently generated populations or new-session generalization.
One held-out session per profile cannot estimate a session-population interval.
Shared generator/profile effects and model-training variation remain limitations.

Undefined ratios have zero eligible denominator. Count them, do not redraw them
or turn them into detector successes. Report percentiles of defined draws and
their defined/undefined counts. High timestamp jitter has zero eligible cases.
High dropped samples has only four: empirical [1,1] detection intervals cannot
bound unseen failure risk. Small cohorts (<30 eligible sources) and degenerate
intervals are explicitly flagged. A bootstrap draw is not a new security trial.
Historical binomial intervals remain supplementary conditional descriptions;
they do not justify treating pooled derivatives as independent observations.

Frozen test results still miss the 90% medium/high anomaly-recall target; logistic
also misses the 5% clean-FPR target. Do not change thresholds after seeing test
performance. Motion correctness and anomaly alerts serve different objectives:
a legitimate small nod can be misclassified as still without being suspicious.
Low-amplitude execution variation remains a separate saved diagnostic analysis.
No architecture search or SNN advantage is introduced by this reporting revision.

## Outputs and safety

Default new output: `results/week-6/keegan/tier2-source-uncertainty`.

Tables: case-accounting, detector-outcomes, motion-degradation, detector-summary,
family-condition-uncertainty and family-summary. The report keeps historical
counts and new uncertainty distinct. source-cohort.csv maps source columns;
bootstrap-source-weights.csv saves all integer multiplicities. The weight hash
is SHA-256 of little-endian uint16 C-order bytes, with NumPy version recorded.

The runner requires committed reporting source and a clean checkout, refuses to
overwrite any output, pins historical hashes, checks all input/source hashes
again afterward, and reconciles all detector points and motion confusions/F1
against the frozen result. INCOMPLETE remains on failure; COMPLETE is written
only after successful checks. Result files use LF-preserving attributes.

Focused tests use small saved-prediction fixtures, not models or original data.
Full-suite evidence is a separate developer validation step, not a rerun of the
historical evaluation. No research-log hours, slides, historical evidence, private
traces or shared reconstruction/protocol implementation are modified.

Remaining priorities include narrow current-v2 stage measurement and one bounded
application optimization, Will's majority-3/correlated-noise and conventional-key
control work, and the shared release/paper/approval package. This report does not
mark those priorities complete.
