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
