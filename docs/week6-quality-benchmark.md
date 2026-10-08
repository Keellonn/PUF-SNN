# Predeclared bounded quality-arithmetic comparison

This adds a runner and protocol tests, not completed timing results. Default v2
authentication code and historical experiments remain unchanged. The candidate
is activated only in its isolated experiment workers. No speedup, target
attainment or production adoption is claimed before the saved comparison passes
equivalence and its numerical results are reviewed.

## Question and one changed component

Does exact integer/dyadic quality arithmetic reduce the observed sender/receiver
quality cost and complete recurring-window latency without changing policy,
wire content, admitted inputs, predictions, state or release counts?

The earlier saved receiver quality-check median was 4.5545 ms for logistic motion
/ logistic anomaly, compared with 0.0162 ms for HMAC calculation alone. Sender
serialization also performs quality validation. This identifies one shared
application bottleneck, not the sole cause of all latency: SNN and forest
inference remain separate costs. See week6-stage-accounting.md and
week6-quality-dyadic.md for the original boundaries and exact inequalities.

The only selected modes are the unchanged Fraction reference and the frozen
exact-integer candidate. No caching, tolerance changes, quality skipping,
memoization, architecture change or threshold adjustment is allowed. Codec,
verifier and candidate bytes are pinned; drift stops the experiment.

## Frozen small protocol

- Three configurations: logistic motion / logistic anomaly; logistic motion /
  forest anomaly; SNN-32 seed 7 / forest anomaly. Anomaly seed 6007 and motion
  seed 7 were predeclared, not chosen from the new timing. Other seeds' historical
  results remain in the existing evidence, not discarded.
- Two paired noise blocks; four fresh serial Python workers. Block 0 runs
  reference then candidate; block 1 runs candidate then reference. Condition
  order is forward then reverse, identical within each pair. This balances mode
  positions but does not fully balance all three model positions or eliminate
  OS, thermal, cache, hybrid-core or CPU-frequency effects.
- Each condition/mode/block has 120 measured admission attempts: the first four
  sorted test windows per fixed profile/class. Thirty validation warmups use the
  first sorted window per profile/class. All 600-window splits are checked before
  selecting these fixed subsets; warmup and test sets are disjoint.
- Total: 1,800 natural fresh single-read admission attempts. The two blocks reuse
  the same sources with different predeclared response-noise domains. These are
  paired timing replicates, not 1,800 independent reliability/security samples.
- Baseline reconstruction stays single-read BCH(63,36,t=5), 63 selected bits,
  32-bit pilot credential, six fixed simulated profiles with seed 6767. This is
  NOT majority-3 integration or correlated-noise evaluation. Enrollment/read
  conditions and session limits are unchanged. No admission retries occur.
- All 11 trusted local frozen model binaries, dataset, manifests, training-only
  normalization and validation-selected thresholds are hash-checked. Loading
  the bundle does not run training, refitting or threshold selection.
- Batch size one; native thread limit one; automatic GC enabled at the recorded
  [2000,10,10] thresholds throughout both modes. Power/GC policy is recorded,
  not tuned to improve results. Actual timing requires AC and heavy apps closed.

Trusted enrollment and model loading precede timing in each fresh worker. The
first validation attempt per condition is retained as condition-first-use, not
claimed to be fully cold system startup. No hidden decoder/inference warmup or
forced collection precedes the first timed root.

## Measurements and correctness gates

Reuse the existing fresh-to-first-window and seven short recurring/rejection/
recovery controls with the SAME timers in both modes. Parsing, HMAC, quality,
admission, preprocessing, motion, anomaly and audit spans are preserved. Keep
fresh admission failures, rejected controls, first uses, slow values and group
maxima. Quantiles for accepted processing are conditional on successful admission;
failed admissions have their own recorded reasons/denominators and timings.

Every accepted root invokes preprocessing, motion and anomaly exactly once;
rejected roots invoke none. Refusals do not change accepted sequence state, and
the subsequent exact-next legitimate window must still pass. Mode pairs must
match sources, selected-bit errors, admission outcomes, input hashes, predictions,
anomaly scores/flags, call counts and public state transitions.

Fresh sessions correctly have different random session IDs/keys/tags. The
post-timer wire-comparison copy neutralizes ONLY the 16 session-ID bytes, after
parsing and validating their position. All other header/payload bytes stay in
the hash. Actual authenticated bytes and HMAC/session bindings are untouched.
Public model-input hashes include every value in the 120 x 7 sequence and
48-feature anomaly input. Fingerprints are computed outside root timers; small
reference bookkeeping inside callbacks is observer overhead in both modes.

Report direct root p50/p95/p99/max, paired signed root deltas, inclusive stage
tables and exclusive per-observation accounting. Never sum stage p95 values to
invent a total p95. Sequence/lock/state and handshake/HKDF/confirmation residuals
remain explicitly unisolated. Sender serialization still includes quality; the
receiver quality call is separately timed, consistently across both modes.

## Sustained processing, cleanup and resources

After the final PLANNED measured admission for a condition, reuse that session
for 64 additional distinct test windows, selected from its same fixed profile.
If that admission fails, report the burst as unavailable with zero completed
windows; do not find/retry a successful replacement. Each window has its own
new sequence and release checks. No extra reconstruction is paid in the burst.

Record direct per-window latency and unpaced closed-loop capacity. The burst
wall denominator includes between-window assertions, public fingerprints and
streamed evidence writes; it excludes admission/loading and final cleanup.
This is service-capacity observation, not sensor-rate scheduling, network or
backpressure evaluation. The 64 windows are repeated across mode/model/block
pairs and are not independent accuracy samples.

Trace trees are streamed, not retained as a growing history during timing.
After ALL worker timing, drop the final trace reference and measure one explicit
generation-2 collection, with normal automatic collection already enabled. Save
cleanup wall/thread-CPU time and before/after runtime/memory snapshots. GC was
never deferred to hide its cost. Worker-wide mixed-workload capacity includes
cleanup, endpoint/control handling and evidence I/O; it is separately labeled,
not passed off as recurring-only throughput. Loading/enrollment are excluded.

Resource evidence includes Python allocation-block/GC counters and numeric
Windows working-set/private-commit snapshots. Process-lifetime peaks include
loading and cannot be attributed to an individual stage. There is no tracemalloc,
raw OS tracing, allocation stack or causal cache/power explanation here.

## Scope and interpretation

Compare candidate timings to their NEW matched reference, not historical laptop
percentiles. Report blocks separately. Two blocks are inadequate for strong
population uncertainty claims; no independent-population CI is fabricated.
Reference and candidate input/prediction equality is mandatory for completion.

The original complete-path 20 ms p95 target remains unmet in the saved baseline.
If a bounded comparison observes a different target status, label the sample,
configuration and timing boundary; do not infer deployment qualification or
erase the old finding. Two-second physical motion acquisition is additional and
excluded. These are post-window software costs, not event-to-decision latency.
Physical acquisition, network, enrollment/loading and durable audit storage are
excluded; in-memory audit and instrumentation costs are included.

Shared authentication-owner review is still required before any default
integration. This control does not strengthen the 32-bit pilot secret, solve
packet loss/DoS, replace Will's majority-3/key-custody/control work, or motivate
an SNN superiority claim. No new platform, large model search or further Windows
tracing is introduced.
