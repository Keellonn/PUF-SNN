# Evidence status, test counts and historical timing

November 10, 2026. Reporting corrections use retained results. No timing,
reconstruction or model-quality experiment was rerun for this report.

## Reproduction status resolved

The detailed reviewer record is completed. The canonical record is
[`reviewer-notes.md`](../../results/week-9/will/keegan-detector-table-reproduction/output/reproduction-output/reviewer-notes.md), published in commit `6fbf4f5b2e553c7fec0796005b7c192cd94ea3bb`.
Will attests that he ran and reviewed the saved-score replay locally on Windows
AMD64 / Python 3.12.4. His reported source checkpoint is
`3835ef55f9d6f5795521379ab5541c608fe5e6ac`. Both retained CSVs still match the
receipt's SHA-256 values; this checkpoint checks their Git-retained bytes.

Use the same status on every slide: **Saved-score detector table reproduced;
reviewer record completed.** The scope excludes training, new predictions,
dataset regeneration, PUF authentication, SNN inference and bootstrap reruns.
The runner's `independent_person_reproduction_verified: false` field is retained:
the later human attestation supplements it and does not alter an automated receipt.

The review includes a qualification: the package-manifest hash was calculated
later from Git bytes, not independently captured at execution. Windows CRLF
checkout differences also affect raw hashes. That limits retrospective byte
identity claims; it does not turn saved-score replay into full pipeline reproduction.
The finalized human record and its qualification must travel together.

## Test totals without double-counting

| Suite/category | Included cases | Newly added in this checkpoint |
|---|---:|---:|
| Python quality checks | 73 | 0 |
| Python ledger/source summaries/source candidate/source visit | 17 + 15 + 10 + 14 = 56 | 0 |
| Other selected Python cases | 1,012 | 0 |
| **Selected Python total** | **1,141** | **0** |
| Unity earlier core | 50 | 0 |
| Unity bench controls | 13 | 3 |
| Unity source candidate | 12 | 1 |
| Unity source visit integration | 14 | 0 |
| **Unity total** | **89** | **4** |

All rows in each suite partition that suite's selected IDs. The 73 Python
quality cases are 26 dyadic + 28 benchmark + 6 differential + 13 Week 8 cases.
The historical 1,141 Python and 85 Unity totals remain correct for November 3.
Relative to the earlier 1,117/60 checkpoint, Week 10 added 24 Python and 25 Unity
cases. The 61-case first-half Unity run is an overlapping subset, not an extra
suite to add. This checkpoint adds four native cases and fixes one existing
Python test's reference to the archived v1 config. It changes no auth policy.

Python root discovery excludes the nonpackage `experiments`, `tier1` and `tools`
directories. The separate 55 profiler tests and 197 calibration/remediation
tests are not added to the 1,141 total. Native and Python IDs are listed in
[the new result bundle](../../results/week-11/keegan/technical-review-20261110-001/README.md).

## Actual timing configurations

These are **historical Week 6 laptop measurements**, release/source commit
`bddce50198d68b851f648d45638aa06d9eea152c`, run type `week6-quality-benchmark-v1`. Both arithmetic
implementations use the same frozen models/validation alert cutoffs and
single-read BCH(63,36,t=5) recovery with the 32-bit pilot credential. They do
not measure Week 11 source retention, current majority-three/stored recovery
or the Quest Link acquisition path.

For the logistic/logistic figure, replace the vague comparison columns with
the actual quality-check configurations below. The order is a row label because
the two blocks repeat the same configurations, not different model setups.

| Timing path and execution order | Original fractions, logistic motion/logistic anomaly, single-read p95 | Faster integers, logistic motion/logistic anomaly, single-read p95 |
|---|---:|---:|
| Existing session; original first, B0 | 27.4285 ms | 14.2551 ms |
| Existing session; faster first, B1 | 25.1534 ms | 15.3827 ms |
| Setup plus first window; original first, B0 | 34.6154 ms | 22.2278 ms |
| Setup plus first window; faster first, B1 | 31.3079 ms | 23.4115 ms |

Machine: HP Pavilion Plus 16-ab1xxx, Intel Core Ultra 7 155H, 16 cores/22 logical,
31.5 GiB, Windows 11 Home 10.0.26200. Recorded software: CPython 3.13.14,
NumPy 2.5.3, scikit-learn 1.9.1, CPU Torch 2.14.0+cpu, galois 0.4.11 and
joblib 1.6.0. Batch size 1, Torch threads 1, interop 16, GC enabled (2000/10/10).
The machine report is retained with the historical reporting, not a measurement
of the current execution environment.

Each configuration/block planned 30 validation warm-up admissions and 120
measured test admissions. B0 accepted 120 per cell, B1 119; failures were kept
without replacement. Blocks reuse fixed sources, so they are neither independent
populations nor confidence intervals. B0 runs fraction then dyadic; B1 reverses
that order. Thermal/background and operating-system effects remain uncontrolled.

Recurring timing spans one `pipeline.process_record` in an existing session:
sender quality/serialization/tagging, receiver checks/release, preprocessing,
both model consumers and included in-memory audit work. Fresh timing adds the
simulated read, reconstruction, verification and session setup before the first
complete window. Reported p95 rows condition on accepted admissions/windows.
The two-second acquisition interval is additional. Physical capture, network,
enrollment/model loading and durable audit storage are excluded. Post-window
time is not motion-onset-to-decision latency. Inclusive stage times can overlap.

Only the optional faster recurring logistic/logistic path met the provisional
20 ms target in these blocks. Setup plus first window, forest-anomaly paths
and the default/original paths remained above it. Retained setup outliers reach
334.6179 ms for faster logistic/logistic in B0 and 355.3507 ms for faster SNN/forest
in B1. Keep the faster checks optional. The fully labeled 24-row CSV retains
both implementations, both boundaries and all three model combinations:
[historical timing](../../results/week-11/keegan/technical-review-20261110-001/historical-timing.csv).

For the next presentation, lead with these changes and their open closure
requirements. Move unchanged historical pilot, profiler and schema-cache
material to an appendix. This repository update does not edit the slides.
