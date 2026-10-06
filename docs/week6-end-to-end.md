# Week 6: Current v2 Admission-to-Inference Integration

**Owner:** Keegan Hoyne

**Shared authentication/reconstruction owner:** Will Wallace

**Stage:** Integration implementation; formal evaluation not yet run

## Purpose and historical boundary

The original Week 5 stream evaluation used supplied-correct candidate material.
Its results remain frozen. This new connector instead acquires one response,
actually runs the existing reconstruction function, and passes the returned
candidate through the current independent verification/local-admission APIs.
It does not claim that retrospective Week 5 results validate this newer path.

`src/python/puf_snn/pipeline_v2.py` connects the existing audited endpoints:

```text
one simulated response read -> one BCH reconstruction
 -> independent credential verification + local admission
 -> request/challenge -> HKDF + mutual confirmation -> active session
 -> processed-window adapter -> sender quality validation + window HMAC
 -> verifier integrity/binding/quality/order checks + audit/sequence commit
 -> at-most-once release -> prepare both inputs -> motion model + anomaly model
```

There is no protocol, reconstruction, code, credential-length, quality-policy,
session-TTL, or model-architecture change in this step. Enrollment, registry,
credential-verifier records and independent verifier-key custody remain owned by
the existing modules. The connector never silently substitutes an enrolled
credential for the decoded candidate. It makes no enrollment-truth comparison.

## Explicit outcomes and fail-closed behavior

- Decoder/padding rejection: no request, no HKDF, no active session or inference.
- Independent credential rejection: no request, no HKDF or inference. It is not
  an improvement in the probability of successful legitimate reconstruction.
- Receiver admission or confirmation rejection: no inference authorization.
- Response-acquisition/backend/internal error: execution error; preserve evidence
  and stop the experiment, rather than treating it as an ordinary FRR sample.
- Processed-record adapter failure: no packet/tag; a pre-tag construction outcome.
- Normal sender quality refusal: no packet/tag; a pre-tag quality outcome.
- Verifier refusal: neither preprocessing nor either model executes.
- Accepted window: one composite callback receives the exact accepted payload.
  Labels, splits and attack settings are absent; authenticated tracking remains
  metadata, not a model channel. Dataset identity/sequence values are replaced
  by the sender's provisioned identity, active session and next sequence.
- Anomaly flags are downstream results. They do not rewrite an accepted
  authentication decision or undo its sequence state.
- Consumer failure: the event stays consumed, sequence stays committed and the
  verifier marks evidence incomplete. No automatic callback retry or rollback.

The class is a serial research connector with fresh isolated endpoints and one
admission attempt. A later experiment runner must explicitly instantiate fresh
attempts/sessions and account for every failure. It must not extend expiry or
silently repeat PUF reads until one succeeds.

## Evidence in this implementation step

`tests/test_pipeline_v2.py` checks the real decoder on zero through five selected
bit flips, one-read/one-decode behavior, credential/admission failures, rejected
traffic, exact accepted-result authority, metadata exclusion, sequence ordering,
consumer failures, and an actual recurrent-SNN forward pass.

The wrong-valid-format control constructs a received alternate codeword beyond
the correction radius. It is a deliberately controlled integration fixture, not
a random-noise trial or an estimated miscorrection rate. Decoder/padding failure
controls use explicit result fixtures. Credentials and verifier keys in tests are
public NONSECRET test material. The SNN fixture is untrained; the anomaly callback
is a spy with real feature extraction. Neither establishes model performance.

No official checkpoint inference, detector retraining, threshold selection,
formal attack evaluation, PUF reliability study, physical Quest run, or latency
benchmark has occurred merely because these tests pass.

## Frozen-model experiment and timing boundaries

The next experiment will load existing validation-selected SNN-32 checkpoints
and the already frozen conventional/anomaly artifacts without new selection.
SNN-64 remains a historical/reference model, not an architecture search. The
source windows and their Session 1/2/3 split remain unchanged.

Fresh noisy-response-to-first-window timing is separate from recurring-window
post-window timing. It must be measured directly for each attempt, including
admission failures in their own denominators. Loading, trusted enrollment and
first-run backend initialization need explicit cold/warm boundaries. Report
accepted/rejected paths, p50/p95/p99/max, GC/timer/I/O/control conditions and
retained outliers; do not sum nested component percentiles into a total.

The future timing/evaluation stage is not completed by this connector. Expanded
Tier-1 trials, reconstruction alternatives, key/trust-specification work and
durable audit performance remain shared/Will work. Human recording remains
disabled pending the required approval. Claims stay limited to a trusted
co-located software prototype with synthetic motion and simulated responses.

## Step 2: Frozen-model functional smoke runner

`configs/week6_smoke.json` pins the three existing model manifests and the
corrected dataset. `puf_snn/frozen_pipeline.py` verifies all required local
binaries before deserialization, requires training-only SNN normalization and
unchanged validation-only anomaly thresholds, and never trains missing models.
The conventional estimators are the already recorded seed-7 storage refits;
all three validation-selected SNN-32 checkpoints and all six frozen conventional
anomaly detectors are loaded. This is not a new architecture/model selection.

`src/python/scripts/run_week6_smoke.py` requires committed, clean source and a
new output directory. It preselects one validation window for each of six
synthetic devices and five classes, before observing any inference/admission
outcome. Each of 30 attempts acquires one fresh nominal-noise RO-PUF simulation
read, actually reconstructs once and follows current v2 admission/confirmation.
No retry-until-success, forced correct candidate or discarded admission failure.

The six fixed PUF manufacturing profiles use the existing seed-6767 pilot
stream; noise reads and simulated 32-bit credentials have separate Week 6 RNG
domains. Credential-verifier keys and handshake nonces use OS randomness.
Enrollment/key material and raw responses are not exported. Selected-bit error
counts are computed after admission for accounting, never for candidate choice.

For every active session, the smoke checks a bad tag, clean acceptance, exact
replay, one quality-valid pre-tag medium position jump, a 113/120 tracking-valid
sender refusal, and subsequent valid traffic. Every accepted delivery runs both
model families on that same accepted payload; refusals preserve calls/state.
The smoke does not require correct classification or a particular anomaly flag.

Partial attempt records remain under `INCOMPLETE` if the runner stops. Only a
reconciled run writes `COMPLETE` and artifact hashes. The runner refuses to
overwrite any existing output directory. Scoped LF rules preserve text hashes.
This is a small functional check, not new attack success/FRR/accuracy estimates,
fresh latency measurements, formal Tier-1 evidence or proof of hardware security.
No historical result files, shared authentication policy or model are modified.

## Step 3: Fresh v2 composite timing protocol (implementation, not results)

The completed functional smoke is recorded under
`results/week-6/keegan/frozen-model-smoke`. Its 30 admissions and boundary checks
are functional evidence, not a timing or reliability estimate. Historical Week 5
results, the smoke records, all checkpoints and thresholds remain unchanged.

`configs/week6_timing.json`, `puf_snn/pipeline_timing.py` and
`src/python/scripts/benchmark_week6_v2.py` define a new, serial CPU measurement.
Six predeclared conditions use one motion model plus one frozen anomaly detector:
logistic motion/logistic anomaly, logistic motion/forest anomaly, forest
motion/forest anomaly, and each of the three saved SNN-32 seeds/forest anomaly.
Detector seeds are fixed at 6007 before measurement. SNN-64 stays historical;
this is not a model/threshold search or a repeat of the attack evaluation.

Each condition retains 20 validation warmups and 600 measured attempts using
all held-out test windows in a fixed device/label/window order. The first warmup
is labeled condition-first-use, not fully cold process startup. Trusted enrollment
initializes BCH algebra outside the boundary; the first decoder compilation can
still occur inside that first attempt. Warmup and study response streams are
separate. Matching per-device study streams are reset for each condition,
making source/noise comparisons paired, not independent reliability replications.

The directly timed fresh path is one simulated noisy read, one actual reconstruction,
independent verification/local authorization, current HKDF/mutual confirmation,
then the first accepted-window composite inference or admission refusal.
Natural refusals are retained, with no retry-until-success or truth substitution.
Physical motion capture, hardware PUF acquisition, endpoint construction, loading,
trusted enrollment, network transport and durable storage are excluded.

Short recurring-window, bad-tag, replay, malformed-JSON, pre-tag tracking-quality
and subsequent-valid controls use unchanged sequence/TTL policies and verify
zero model calls on refusals. Their output/assertions/mutations are outside the
timer. Receiver-only paths are distinguished from complete post-window paths.
The provisional 20 ms p95 target applies only to complete post-window processing,
including the anomaly detector here, not fresh admission or hard real-time bounds.

Temporary serial wrappers preserve the underlying implementation and restore
on error. Stage trees, thread CPU, GC overlaps, native nested HKDF values,
p50/p95/p99/max and all slow observations are retained. Nested percentiles are
never added into a total. Authentication includes lock wait, replay checks and
state commit; those are not claimed as separately isolated timings. Audit spans
describe in-memory record/prepare/commit only. Model consumer spans include
normalization, tensor creation, score/label conversion and threshold comparison.

All >20 ms observations, group p99 tails and maxima have retained diagnostic
records. GC overlap and wall/thread-CPU gaps locate possible contributors, not
prove causes. Allocation, scheduling, cache and frequency causes remain unresolved
unless separately measured; the report must not invent a complete outlier diagnosis.
A no-op instrumentation proxy is disclosed and never subtracted from totals.

GC stays enabled; high-resolution monotonic wall/thread-CPU clocks are recorded.
Torch intra-op and native thread pools are limited to one; inter-op thread count,
actual start/end machine and power-plan snapshots, self-reported AC/background
conditions and uncontrolled hybrid-core/frequency placement are recorded.
The runner never changes the power plan. LF writers cover every hashed text artifact.
Condition order is fixed; thermal/background drift is not controlled by source/noise
pairing. Post-window estimates are conditional on successful admission. Detailed
timing and outlier JSONL files are separated by condition for manageable artifacts.

Clean committed source and a new scoped result directory are required before the
actual benchmark. Partial JSONL/INCOMPLETE evidence is preserved on error;
COMPLETE binds the reconciled manifest. Passing the new tests alone does not
complete the timing experiment, causal outlier study, expanded Tier-1/reliability
experiments, Will's formal trust specification, or any Quest validation.
