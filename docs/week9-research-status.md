# Research status and evidence corrections

Updated October 30, 2026. Current conclusions remain limited to software and synthetic
data. Engineering targets are provisional, not established medical or device
requirements. No new models, attacks or platforms were added.

| Question | Latest supported finding | Limit / next evidence |
|---|---|---|
| What does the SNN add? | Recurrent spike-based comparator; clean synthetic mean macro-F1: logistic 90.32%, forest 89.36%, SNN-32 86.19%, matched SNN-64 85.00% | Neither SNN beats conventional baselines; no energy or real-device advantage measured |
| Clean false-alert target â‰¤5% | Logistic 5.33% misses; forest 2.94% meets the point target | Conditional 95% source intervals: logistic 3.83â€“7.17%, forest 1.78â€“4.22% |
| Medium/high recall target â‰¥90% | Logistic 82.85%, forest 87.95%; both miss | Conditional intervals 82.42â€“83.29% and 87.73â€“88.19%; gradual orientation drift remains difficult |
| Complete software path â‰¤20 ms p95 | Optional faster logistic/logistic recurring path met target in two old blocks | Setup + first was 22.2/23.4 ms; forest paths miss; single-read laptop scope only |
| Real-motion validation | Trial accounting and source-diagnostic software checks pass | Actual Quest/Android checks, institutional clearance and PI readiness review remain |
| Independent reproduction | Will returned local Windows/Python 3.12.4 metric recomputation; both CSVs match | Detailed reviewer form remains blank; full inference and bootstrap reruns remain separate |

Conventional motion results summarize five fixed fits on the same 600 test
windows; SNN width comparison summarizes three fixed fits and selected width
using validation only. Fits/seeds are not extra people. Motion macro-F1 is a
different endpoint from anomaly recall. The detector table averages three fixed
fits, each using 600 clean controls and 9,095 eligible medium/high modified copies.
All copies of a source remain together for the retained source bootstrap
(2,000 replicates); these intervals do not show cross-person or headset generalization.
Quality refusals, construction failures, detector misses and alerts are distinct.

## What the evidence audit corrected

The companion [discrepancy table](../results/week-9/keegan/decision-report-20261027-001/discrepancies.csv)
states issue, cause, correction, affected records and result impact. The important
receipt correction is plain: checking saved evidence replays reconstruction work.
One replay pass was recorded as 200 measurements and 100 decodes. Successful
finalization performs two passes, so its replay total is 400 and 200; a later
standalone audit adds another 200 and 100. These are checking operations, not new
experimental trials or additional participants. Old sealed bundles stay unchanged.

Will's Week 8 evidence note describes an independent read-only source/evidence
audit with correctable gaps. The inspected note does not establish the human
auditor's identity, so this report does not invent one. That activity checked
source/evidence contracts and accounting; it was not another person's reproduction
of Keegan's model-results table. Neither the current local dry run nor a second
automated agent establishes independent-person reproduction.

## Profiler and schema-cache interpretation

Will's bounded workload had 150 arm attempts, one virtual population/device and
50 matched identities. Repeated JSON Schema definition checking dominated its
workflow (459 checks, roughly 97.8 seconds of inclusive time). Content-keyed
validator caching reduced definition checks to five while retaining instance
validation, integrity checks and both finalization passes. Total supervised
workflow time was 142.875 then 48.734 seconds. Inclusive spans overlap and cannot
be added as independent stage costs. No motion/anomaly model inference ran there.
These seconds are experiment runtime, not per-window sensor decision latency.

Baseline sampled peak private memory was about 1.40 GiB. The optimized summary
had a decimal/binary display mismatch and is only approximately 1.4 decimal GB
until its byte counter is checked. Do not claim precise memory improvement.
The existing cache tests cover same-size/same-mtime edits, atomic replacement,
distinct bytes and validator classes, warm-cache malformed/missing files,
per-instance validation, canonical payload preservation, eviction and clearing.
Current source inspection confirms this coverage; those experiment tests are
outside root discovery and were not rerun as part of the new 1,117 receipt.
The cache rereads current bytes on each call. Its key is exact immutable schema
bytes plus validator class, not filename or mtime. Changed/invalid definitions
cannot silently fall back to a cached validator. Current schemas have no external
references; introducing mutable external references requires renewed review.

The retained benchmark note lists 97 evidence files, but an exact disk byte
receipt and the full-study resource estimate are not available in this checkout.
Obtain the original profiler sidecars from Will for disk, memory-unit correction
and interrupted-run/resource-limit details. Do not extrapolate the small run
linearly into a 90,000-attempt resource guarantee or execute that study here.

## Ownership and remaining work

Keegan's interpretation, historical timing labels and synthetic logger summaries
are prepared. Actual device controls, acquisition/transfer checks and the PI
readiness report remain. Will owns the shared-noise specification and three-arm
failure/admission/release denominators and overhead. The pilot's zero unauthorized
releases is not an adversarial-attempt denominator or a cryptographic proof.
Will has returned the bounded local metric replay. Complete its detailed reviewer
record with setup/deviations and human review context. See the
[October 30 follow-up](week9-follow-up-20261030.md). Keep optional defaults unchanged.

Primary retained sources and hashes are listed in the decision-report manifest.
The missing original frozen archive remains openly recorded; it does not prevent
the new scoped software checks.

## October 28 laptop follow-up

The [bench checkpoint](../results/week-9/keegan/quest-bench-20261028-001/README.md)
adds a tracked-camera scene, explicit controls and a successful ARM64 build.
All 60 Unity tests passed, including the earlier 50. Offline APK checks found
the OpenXR loader and Quest VR metadata. Actual device validation, independent
reproduction and institutional authorization remain pending. These engineering
checks do not change the model, anomaly or historical timing conclusions above.

## October 30 status

Will's returned local metric-table run now supplies Windows/Python 3.12.4 evidence
and matching outputs. Its detailed reviewer template remains blank. The next
Quest check uses PC-hosted Link; device execution and CITI remain planned for
next week. See [the current follow-up](week9-follow-up-20261030.md). The earlier
dated checkpoints and scientific results remain unchanged.
