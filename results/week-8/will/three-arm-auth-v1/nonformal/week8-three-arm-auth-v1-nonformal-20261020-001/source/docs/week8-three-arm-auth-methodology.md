# Week 8 three-arm authentication methodology

Experiment: `week8-three-arm-auth-v1`. Formal execution is disabled at the
configuration, runtime, evidence-writer and CLI boundaries. This version reuses
the existing correlated-noise simulator, enrollment, acquisition, decoder,
independent verifier, admission service and Authentication-v2 implementation.
No historical study identity or evidence is rewritten.

## Matching and sampling

Use one stored invocation per matched device/trial/noise cell. This gives the
same workload allocation and a paired downstream timing context. The planned
allocation is 20 populations, six devices, 50 trials and five conditions:
30,000 matched cells and 90,000 arm attempts. Repeated stored controls are
noise-independent workload repetitions, not five independent noise-response
experiments. The permitted pilot is one population, one device and ten trials
per condition: 50 cells, 150 arm attempts. Three Majority-3 readings are one
attempt. Independent sampling units remain whole simulated populations.

All arms share device, enrollment, credential bytes, verifier record/key
provider, protocol settings and a fixed stationary 120-sample sequence-zero
window. Each gets fresh sender, verifier, admission service and recording
consumer state. Provisioning occurs before establishment timing. Six arm
permutations cycle with condition/device offsets; frequencies differ by at
most one within a cell allocation. Blocks are deterministically shuffled.

The PUF policies share indexed reading zero and correlated shared disturbance.
`noise_shared_seed_sha256` identifies that noise domain only. Actual handshake
nonces and session identifiers retain OS entropy and are unmatched nuisance
variation. No deterministic handshake entropy is introduced. Week 8 uses new
device IDs and measurement domains; enrollment reuses the existing versioned
enrollment algorithm/domain with Week 8 device IDs and master seed.

## Outcomes and authority

PUF C/D/I/W retain correct reconstruction, decoder failure, invalid padding or
format, and wrong valid-format credential meanings. They partition completed
reconstructions. Reconstruction FRR is (D+I+W)/completed reconstructions.
Stored reconstruction, effective response and decode duration are null.
Stored retrieval outcomes are success, unavailable and malformed; retrieval
failure rate is (unavailable+malformed)/completed stored attempts.

For each arm, admission failure rate is (completed attempts minus authorized
admissions)/completed attempts; session failure rate uses successful sessions
in the same formula. These all-attempt rates include source refusals. Verification,
authorization, session activation, accepted windows and authorized releases
are successive stage totals, never additional mutually exclusive categories.
Candidate mismatch and policy refusal are separate observations. Infrastructure
faults leave evidence incomplete and never enter completed-run FRR denominators.

Instrumentation wraps `authorize_with_outcome` once, including delegation from
PUF `authorize`, and observes the actual `verify` call. Stored status is bound
to the latest invocation ID, cross-checked against observed service outcomes.
Prepared-attempt diagnostics grant no authority. The real admission service,
mutual confirmation and verifier-minted window remain the security boundaries.
Callback invocation and completion and release entry/completion are recorded
separately, including a faulting callback's partial progress.

## Timing

This version implements cold-process, zero-harness-warmup measurements. It does
not claim warmed timing. First-use compilation/cache effects remain visible;
the first measured BCH decode may be much slower. Existing process/package
caches can still affect measurements. Record environment and execution order.
Enrollment, helper encoding, stored provisioning, trusted verifier records,
endpoint construction, shared-Z preparation, template construction and model
loading are excluded. Independent per-read noise draws are inside reading.

Inclusive nanosecond spans with parent links cover source acquisition/retrieval,
effective response construction/voting where applicable, reconstruction/BCH,
independent verification, authorization, HKDF/mutual confirmation, directly
measured total establishment and first-window sealing/verification/release.
Exclusive duration subtracts immediate child spans. In particular, exclusive
authorization excludes verification; acquisition exclusive excludes measured
readings/voting and captures response validation/passthrough overhead. Single
read has no voting span. Missing/inapplicable stages have null durations, never
invented zero decode measurements. Summaries compute total p95 from measured
totals, never by adding stage quantiles. Instrumentation adds local overhead.

Report all-attempt establishment cost separately from successful-session cost;
the latter is conditional on survival and can be selection-biased. First-window
cost includes recording callbacks and is not recurring throughput. Recurring
window measurement, warmed isolated fixtures and timing review remain future
requirements. No physical PUF, Quest, network or real SNN latency is measured.

## Formal analysis contract (documented, not executed)

Primary PUF contrasts are single-read FRR minus Majority-3 FRR in nominal and
stress noise, and attenuation (nominal benefit minus correlated benefit at
rho=.90; rho=.50 secondary). Compare three-arm admission/session failure rates
and acquisition/retrieval and establishment costs separately. Report absolute
rates, paired contrasts, all-attempt cost and conditional successful-session
cost distinctly. Retain all arms/conditions/devices/trials within each whole
population when resampling populations with replacement. Never resample the
three readings or repeated stored invocations as independent populations.

Any eventual bootstrap intervals are pointwise, not simultaneous or evidence
of generalization to physical devices. Fewer than two independent populations
suppresses intervals. Zero observed events do not imply zero failure probability;
a degenerate bootstrap interval must be labeled uninformative about unseen
events. The nonformal implementation computes descriptive rates/latencies only
and emits no confidence intervals or significance claims.

## Evidence and limits

Week 8 output is an exclusively new direct child of
`results/week-8/will/three-arm-auth-v1/nonformal/`, with a versioned run prefix.
Unit evidence uses isolated temporary roots. Historical trees, aliases, linked
ancestors, nested evidence and existing bundles are rejected. An INCOMPLETE
sentinel remains through execution, semantic reconciliation and independent
manifest audit. Completion is marked only after both validation passes succeed.
PUF observations and decoder outcomes are deterministically replayed outside
measured work; replay adds no statistical samples. Replay/reference setup work
is accounted separately in validation receipts. Interruptions may leave unknown
unrecorded work and cannot complete. No automatic retry/resume is implemented.

Local source/configuration hashes and snapshots support reproducibility and
integrity checking, not remote attestation or proof against a malicious local
operator. Public synthetic replay inputs can reconstruct simulation credentials;
literal credentials, verifier keys, session keys and capabilities are omitted.
Auditing requires the recorded source/environment. The stored in-memory control
and simulated PUF make no equivalent physical secret-protection claim. HMAC
integrity and exact-next sequence replay rejection belong to the shared protocol.
Recording consumers are release probes and do not execute SNN/anomaly inference.
