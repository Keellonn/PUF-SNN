# Scoped Week 6 release and evidence index

The machine-readable [revision-evidence-index.json](../results/week-6/keegan/revision-evidence-index.json) pins the experimental snapshot `2c84cf8394bd444188291e254bbf1ddde3cc8661`, tree `f8f400fabf89943301be3adc4dc7683a306717a4`, critical source/config bytes, recorded result manifests and exact frozen inputs. A later documentation commit identifies this reporting revision without trying to embed its own hash. The snapshot is not a declaration that the full shared release is complete.

## Locally verified Keegan evidence

| Evidence | Source commit | Recorded result commit | Original manifest SHA-256 |
|---|---|---|---|
| Fresh v2 timing | 78f499a | a4a9e25 | 10135c6e3849015c6afcfb96c91d9bc25bdeabdbdc1da2531b1ec65501403b50 |
| Saved stage accounting | 7921261 | f11f491 | 6c9691ef4a07b8f6ced4de96f7aec798046ebd743254aa3041b4d5941dd2bd48 |
| Source-aware Tier-2 uncertainty | c5e982b | 2b1d210 | dc234b0bbccbc56dacd6009b5bd444ff202ad09720fbf46443e1c87b97f41952 |
| Bounded paired quality benchmark | bddce50 | 2c84cf8 | a978cec8d4df41617b7db4616109b8e7b6a522c276efe73243de3c01ef6d9045 |

Each COMPLETE marker binds its original manifest. Benchmark worker manifests are separately pinned and their artifacts/completion markers must also be verified. Generated reports and original run files remain unchanged. A reporting COMPLETE means its declared artifact reconciliation/export finished, not deployment/security/hardware completion.

The latest saved full suite is 964 passing tests in 100.599 seconds at source bddce50. Its console SHA-256 is f73c9aad0d4044fd8441f13072487b6d8afd294638c63cade2fb524bca91c41b. Categories and remaining gaps are in [feedback consolidation](week6-feedback-consolidation.md); no suite or benchmark is rerun for this documentation-only step.

## Frozen payload availability and environment

A clone does not supply the generated dataset or the 11 frozen model binaries. The index lists 19 payload/support files, including the dataset, weights, bundle manifests, training-only normalization, anomaly features and thresholds, with exact repository-relative paths, sizes and hashes. The dataset SHA-256 is 752b009588f3e721a8bf2f8f8fcd1cdf0f7e998446b60953dd34dd5e9e54d661. Obtain the original trusted frozen bundle; verify all required payload/support hashes and original manifests before loading. Do not silently regenerate, retrain or replace conflicting files. Model deserialization additionally requires trusting the sender; a matching hash is identity/integrity evidence, not proof that arbitrary model files are safe.

The bounded comparison's recorded environment is Windows 11 build 26200, Python 3.13.14, NumPy 2.5.3, PyTorch 2.14.0+cpu, scikit-learn 1.9.1, joblib 1.6.0 and galois 0.4.11. The machine is an HP Pavilion Plus 16, Core Ultra 7 155H, 31.5 GiB memory, on AC with heavy apps closed. QueryPerformanceCounter and GetThreadTimes are used. Native/torch compute pools use the recorded limits; torch interop is separately recorded as 16. GC is enabled with thresholds 2000/10/10. Core/frequency/thermal conditions are not fixed. All four worker environment files are retained; requirements.txt alone is not a complete inference dependency lock.

Original timing, Will's runs and historical training have their own recorded environments. Do not blend their latency distributions or claim exact numerical reproduction on another machine. Nonsecret schedules are reproducible, while OS-random credentials/nonces/session IDs and machine timing will legitimately differ.

## Reproduction procedure, not a command to run now

1. Select the experimental/source commit appropriate to the cohort, verify tracked tree/source/config pins and obtain the exact frozen payloads. Keep the current development checkout and all recorded evidence untouched.
2. For offline reporting, verify original artifacts and completion bindings before reading them. Stage/source-aware revisions perform no new inference; a new report requires an unused output directory.
3. For the paired benchmark, use the declared AB/BA configuration, original frozen bytes and recorded environment/AC conditions. It is a new timed run and must have a new output path; never reuse or overwrite quality-benchmark/.
4. Preserve its refusals, first uses, environment observations, cleanup, worker/master hashes and all timing records. Compare candidate with its matched reference, not historical laptop quantiles; do not sum stage percentiles.
5. Record the actual new source/config/command/environment and results, including differences or failures. Do not assert that timing must numerically match an earlier machine/run.

Recorded entry points (archival examples with NEW placeholder outputs, not additional instructions for the current copy step):

```powershell
python -B src/python/scripts/summarize_week6_stages.py --input results/week-6/keegan/fresh-v2-timing --output <unused-stage-report-directory>
python -B src/python/scripts/summarize_tier2_source_uncertainty.py --input results/week-5/keegan/stream-evaluation --output <unused-source-report-directory>
python -B -u src/python/scripts/benchmark_week6_quality.py --config configs/week6_quality_benchmark.json --output <unused-benchmark-directory> --power ac --background heavy_apps_closed
```

These angle-bracket placeholders must be replaced before use. Commands are documentation of the workflow, not authorization to rerun a saved experiment or alter a held-out evaluation. A separately planned majority-3/provisioned-key study needs its own source/configuration and declared question.

## Shared release components not yet locally closed

The actual [v2 protocol specification](authentication-v2-protocol-spec.md), [Tier-1 report](week6-tier1-v2-experiment.md) and [reconstruction report](week6-reconstruction-alternatives-experiment.md) are committed, and their current document bytes are pinned in the index. Raw folders results/week-6/will/authentication/tier1-v2-formal-001/ and results/week-6/will/reconstruction-alternatives/week6-reconstruction-alternatives-v1-formal-001/ are absent from this checkout. Their numerical findings are documented, not independently recomputed here.

The Tier-1 report records isolated execution commit 0d088079d025e50411c8a752b32507bbb87d5d5b, original evidence manifest 098ebcf6488e7d2b5c2054200bab289e5428c859904108059d0437612c137177 and source manifest d1367398222037dc9f6bc92c1b5d4610f68a6e0513b02b61bbb74e6ba31892b3. That commit is retained in its source bundle rather than pushed main; recover the documented exact-byte source ZIP and verify the actual manifest. The alternatives report also used a separate source snapshot because relevant experiment files were uncommitted at execution. Current main is not automatically the identical formal execution source.

For full shared release closure, obtain the original formal result/verification manifests and exact execution snapshots through the approved transfer, verify their closures and relevant registered plan/configuration hashes, reconcile baselines and unique experiment metadata, and document any omissions. Do not invent a missing hash, infer custody evidence from a slide, or mark shared_release_complete true before those checks. A dependency lock and tested setup instructions also remain needed for a turnkey clean-environment release.

Raw ETL, kernel payloads and private OS recovery evidence are excluded from public release. Existing sanitized numeric reports provide bounded audit evidence, not public access to sensitive trace files. No raw trace upload, deletion, rescan, recording or new model run is part of this package. Faculty access/human-data authorization and physical logger validation remain separate pending decisions.
