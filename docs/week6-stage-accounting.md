# Week 6 saved-data stage-accounting revision

Owner: Keegan Hoyne

This addendum implements the faculty request to prioritize application-stage
accounting over additional Windows tracing. It reads the unchanged completed
`results/week-6/keegan/fresh-v2-timing` run. It does not change protocol,
reconstruction, models, thresholds, historical evidence, slides or research logs.

## Boundaries and provenance

- Benchmark source: `78f499a92f633a4793c776a070058e3a6a9a0b61`.
- Results commit: `a4a9e2548fd30ee2383923dbd0de6cd5c45c587f`.
- Pinned original manifest SHA-256:
  `10135c6e3849015c6afcfb96c91d9bc25bdeabdbdc1da2531b1ec65501403b50`.
- Every manifest-listed historical artifact is hash-checked before analysis and
  rechecked before completion. Saved direct and inclusive stage quantiles and
  admission/delivery counts must reconcile exactly.
- The reporting implementation imports only the standard library and its pure
  reporting module. It does not import/load the pipeline, model checkpoints,
  dataset, authentication endpoints, ETL decoder or training libraries.

The integrated benchmark used one simulated response read and one actual
BCH(63,36,t=5) reconstruction of a 32-bit pilot credential per admission attempt.
It did not integrate majority-3. There were 599 accepted and one refused measured
admission per condition; the refusal is paired across conditions, not six
independent reliability trials. Accepted latency quantiles remain conditional on
successful admission, with refusals retained separately.

## Reporting design

Primary tables use LR motion/LR anomaly, LR motion/forest anomaly, and SNN-32
seed-7 motion/forest anomaly. Seed 7 follows the first SNN condition in the
original predeclared list; it is not selected for the fastest observed latency.
All three SNN seeds and the forest-motion configuration remain in the full tables.

Fresh first-window time includes admission/session setup and first processing.
Recurring-window time excludes repeat admission/setup. Direct roots, first-use,
warmup, accepted outcomes and refusals are reported separately. The original
two-second acquisition window is not part of these timers. Physical acquisition,
network transport and durable audit storage remain excluded.

Inclusive spans overlap. Their medians/p95/p99 values must never be summed to
construct a total. The total is the original directly timed root.

For a separate accounting view, subtract direct child intervals within each
individual serial span. Non-overlapping, contained children are required; unknown
stages and inconsistent trees fail closed. The exclusive categories sum exactly
to each original root's integer-nanosecond wall duration. The reporting code does
not subtract independently calculated percentiles or subtract GC from timings.

Residual categories explicitly include unisolated work and observer overhead:

- Receiver binding, sequence checks, mutex/state publication are not separate
  pure measurements. Their recorded remainder must not be labeled sequence-only.
- Handshake remainders do not separately isolate HKDF and key confirmation.
- Measured in-memory audit calls are not all audit-related system overhead and
  do not include durable persistence.
- Shared preprocessing is separate from normalization/tensor construction and
  output decoding inside model consumers.
- A missing stage in a path is not a measured zero-cost stage.

## Cross-experiment authentication context

The 5.1700 ms figure is documented in Will's
`docs/week6-tier1-v2-experiment.md`: native verifier median for 1,200 legitimate
controls. Its native timer begins before mutex acquisition and includes the
accepted parser/binding/HMAC/quality/order/audit/state path, excluding release
and inference. The documented receiver-to-return median is 19.4579 ms.

This addendum pins that document and the verifier source as context; it does not
recompute Will's raw Tier-1 results or merge that experiment's timing population
with Keegan's external wrapper measurements. Historical bad-tag p95 of 0.981 ms
is an earlier early-rejection boundary, not accepted authentication or current
complete-path cost. Current-run bad-tag totals are included for comparison.

## Output and remaining work

The runner requires committed reporting source, a clean checkout and a new,
non-overlapping output beneath `results/week-6/keegan`. It writes an INCOMPLETE
marker until input hashes, source/context hashes and finalization checks pass.
Original files are never overwritten. Output includes direct/inclusive/exclusive
tables, per-observation accounting, admission counts, definitions, a report and
hash-linked manifest/completion record. Output line endings are fixed to LF.

No new timing, response reads, authentication, model loading/inference, training,
threshold changes, recording or ETL scan occurs. No bottleneck optimization or
complete causal attribution is claimed by this addendum.

Review typical stage costs before selecting one bounded optimization. If separate
sequence/confirmation/audit totals are required, add narrow consistent timing
boundaries and run a declared follow-up, rather than fabricating them from this
saved run. Any optimized comparison must retain all functional checks and failed
attempts, report direct totals, and measure cleanup, sustained throughput and
memory/resource behavior. No architecture expansion or new Windows recording is
required for this reporting step.
