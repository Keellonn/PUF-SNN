# Quality check decision and timing interpretation

October 27, 2026. Keep the faster arithmetic optional. The retained comparisons
matched on their tested cases, and one historical recurring configuration met
20 ms p95. These findings do not establish universal equivalence or a complete
system deadline. No models, alert cutoffs or shared defaults changed here.

## What the implementation changes

Orientation quality checks previously constructed exact Python fractions
repeatedly. The candidate uses integers on a shared binary scale for the same
encoded numbers and exact comparisons. This reduces arithmetic overhead without
rounding values or relaxing the rules. Schema caching is a separate optimization
in the experiment workflow; it is not this per-window arithmetic change.

## Tested behavior and case coverage

| Evidence | Cases and scope | What matched |
|---|---|---|
| Dyadic unit tests | 26 tests: ordinary valid values, malformed/nonfinite inputs, exact limits and randomized comparisons | Exact quality decisions and reasons against the fraction reference |
| Differential tests | 6 tests, including 24 valid sender windows and three paired eight-window streams | Packet bytes/tags for the same inputs/key, processed arrays and downstream results |
| Benchmark controls | 28 software tests | Timer/control behavior and rejection/state checks |
| Week 8 admitted-session comparison | 13 integration tests; 30 validation sources, six fixed profiles × five labels, three model combinations, two arithmetic modes, two recovery policies | 360 sessions, 180 arithmetic pairs and 180 cross-recovery downstream comparisons matched |

These 73 focused tests were included in the historical 1,085 selected tests;
do not add them again. The 55 profiler tests were separate. Test fixtures are
not additional independent research observations. New logger totals are separate
later receipts: 1,117 Python and 50 native Unity cases.

Each controlled session exercises bad tag, clean input, exact replay, a
pre-authentication medium position jump, 113/120 tracking refusal, and the next
valid window after refusals. The 360 sessions contain 1,080 accepted windows and
1,080 refusal controls. No refused control reached preprocessing or either model.

Matching covers acceptance/rejection, stage and reason, sequence, exact processed
model inputs, motion predictions, anomaly predictions/scores/alerts exposed by
the consumer, inference-call counts, consumed verifier release events and relevant
session/sequence state. Public fingerprints compare shapes, finite values and
array bytes. Arithmetic pairs compare the same recorded fields except the mode
label. Fresh random session/key/event identifiers are not forced equal: the tests
verify valid, single-use releases and expected state rather than identical random
identifiers. Sender tests separately compare bytes and tags with the same key.

Three-read versus single-read downstream comparisons use controlled correctable
responses and compare behavior **conditional on successful admission**. They
exclude the deliberately different read-count/policy fields. They are not a
reliability experiment and do not show equal admission rates under shared noise.

## Historical laptop timing

Source: the retained Week 6 quality-benchmark manifest and direct-path CSV at
source commit `bddce50198d68b851f648d45638aa06d9eea152c`. All rows below use
single-read recovery and frozen models/cutoffs. Comparison 1 is block 0
(reference then candidate); comparison 2 is block 1 (candidate then reference).
Values are directly measured accepted wall-time p95 in milliseconds.

| Motion / anomaly | Comparison | Original recurring | Faster recurring | Original setup + first | Faster setup + first |
|---|---:|---:|---:|---:|---:|
| Logistic / logistic | 1 | 27.4285 | 14.2551 | 34.6154 | 22.2278 |
| Logistic / logistic | 2 | 25.1534 | 15.3827 | 31.3079 | 23.4115 |
| Logistic / forest | 1 | 40.9905 | 25.0066 | 45.0540 | 31.0356 |
| Logistic / forest | 2 | 41.3853 | 28.9934 | 48.2380 | 35.0740 |
| SNN-32 seed 7 / forest | 1 | 46.5381 | 32.1141 | 52.6902 | 37.7728 |
| SNN-32 seed 7 / forest | 2 | 48.6062 | 40.8279 | 68.1923 | 49.9577 |

Thus the slide's 14.3 and 15.4 ms are two recurring comparisons; 22.2 and
23.4 ms are their corresponding setup-plus-first-window results. Only faster
logistic/logistic recurring processing meets the provisional 20 ms p95 target.
Forest-anomaly combinations and every setup-plus-first result remain above it.
The original/default recurring configurations also remain above it.

Recurring timing wraps one `pipeline.process_record` in an active session:
sender processing/quality/serialization/tagging, receiver checks, authenticated
release, preprocessing, both consumers and included in-memory audit work.
Setup-plus-first wraps simulated response acquisition, reconstruction/verification,
session establishment and that first full window. Failed admissions are accounted
separately; this table is conditional on accepted admission/window processing.

Each config/mode/block planned 30 validation warm-up admissions, then 120 measured
test admissions. Block 0 accepted 120 per cell; block 1 accepted 119. Failures
were retained without replacement. The same fixed windows were reused across
paired modes/blocks. Separate sustained checks use 64 same-profile windows per
cell, 768 total; they are not an arrival-rate/backpressure study. These two blocks
are not two independent populations or a population confidence interval.

Machine: HP Pavilion Plus 16-ab1xxx, Core Ultra 7 155H, 16 cores/22 logical,
31.5 GiB, Windows 11 Home 10.0.26200, CPython 3.13.14, NumPy 2.5.3,
scikit-learn 1.9.1, Torch 2.14.0+cpu, galois 0.4.11, joblib 1.6.0.
Batch size 1; Torch threads 1, interop 16. GC stayed enabled with thresholds
2000/10/10. AC power, heavy apps closed and the existing power plan unchanged.
CPU affinity/frequency and thermal/background effects were not fully controlled.
Wall timing uses QueryPerformanceCounter through perf_counter; thread CPU uses
GetThreadTimes. Instrumentation remains included in the outer measured calls.

The two-second motion acquisition window is additional. Physical sensor/PUF
capture, network transmission, enrollment/model loading and durable audit
storage are excluded. Evidence streaming is outside each root timer but inside
closed-loop workflow throughput. Post-window processing is not total
motion-onset-to-decision time. Inclusive stage spans can overlap; selected
medians/p95 values cannot be added to reconstruct the root total.

P95 is not a worst-case bound. Retained candidate outliers include 334.6179 ms
for logistic/logistic setup in comparison 1 and 355.3507 ms for SNN/forest setup
in comparison 2. The new logger sidecar and current majority-three/stored arms
were not measured by these older runs. Do not transfer these numbers to them or
to Quest hardware.

## Decision before changing the shared default

The test-case evidence supports continued review of the optional candidate.
Independent review/reproduction, the shared activation/concurrency/rollback path
and a current frozen timing run with explicit recovery/model/environment labels
remain to be completed before proposing default promotion. Keep any future
benchmark separate from these retained numbers and record its own source hashes.

Primary evidence: `results/week-8/keegan/quality-validation-20261022-001`,
`docs/week8-quality-equivalence.md`, `docs/week8-keegan-validation.md`,
`results/week-6/keegan/quality-benchmark` and `configs/week6_quality_benchmark.json`.
The companion decision-report folder retains selected CSV rows and input hashes.
