# Bounded application optimization candidate: exact quaternion quality checks

This step adds an opt-in arithmetic candidate and equivalence tests. It does NOT
change the default v2 implementation, run a benchmark, establish a speedup or
make the current complete-path 20 ms p95 target pass. The original Fraction
validator and all historical experiment artifacts remain unchanged.

## Why this bottleneck

The saved Week 6 stage-accounting revision places receiver quality-check p50 at
4.5545 ms for logistic motion / logistic anomaly, compared with 0.0162 ms for the
HMAC calculation alone. The sender also performs quality validation as part of
serialization. These are nested boundaries from the original instrumented run,
not separately summed costs or proof that quality checking explains all latency.

The original validator repeatedly constructs exact Fraction values for 120
four-component binary32 quaternions and computes component, norm and continuity
tests. Replacing that arithmetic is one bounded shared application optimization.
The SNN's motion consumer remains a separate dominant stage (17.7986 ms median
in its seed-7 recurring condition); this candidate is not expected to remove SNN
or forest inference costs or guarantee a 20 ms complete path.

## Exact correspondence, not weaker validation

Let D = 2^149. Every finite binary32 value x is n/D for integer n.
For exponent field e and fraction field m:

- e=0: n = signed m.
- 1<=e<=254: n = signed ((m + 2^23) << (e-1)).
- e=255: nonfinite; existing F32 construction/parsing rejects it.

The sign bit negates n; either zero sign maps to integer zero. This numerical
mapping does not permit noncanonical wire negative zero: the parser is unchanged.

The candidate compares only exact Python integers, using equivalent inequalities:

- Component: abs(n)*1,000,000 <= 1,000,001*D.
- Norm: 9,999^2*D^2 <= sum(n_j^2)*10,000^2 <= 10,001^2*D^2.
- Sign continuity: sum(n_j*previous_n_j) >= 0.

No floating-point approximation, tolerance relaxation, caching, source-label
shortcut, quality skip or repeated-window memoization is introduced. Duration,
tracking-count/fraction, timestamp-range and timestamp-gap checks keep their
original order and data_quality_failure reason. Structure/type validation still
belongs to the unchanged codec/parser before this typed-input quality routine.

## Experiment-only activation boundary

quality_validator_mode("reference_fraction") leaves the reference in place.
quality_validator_mode("candidate_dyadic") temporarily replaces only the codec's
quality global and the verifier's imported quality alias in one isolated serial
worker process. This reaches sender encoding and the receiver's existing
post-HMAC quality check. Context exit restores both aliases, including after
exceptions; nested selections or preexisting quality wrappers are refused.

Enter the mode context before the existing instrument_pipeline context so the
two modes receive identical timing wrappers. Concurrent threads and overlapping
mode contexts are unsupported. Default pipeline callers do not opt in and keep
the reference behavior. Shared authentication-owner review is required before
any later default integration; no edits to Will's codec/verifier files occur here.

Unchanged: wire bytes, parser limits and canonical representation, HMAC/key
hierarchy, credential reconstruction/admission, confirmation, exact-next-sequence
policy, session state, audit commit and inference-release authority. This does
not solve packet loss or denial of service, strengthen the pilot credential or
replace the separate protocol/security evaluation.

## Verification before timing

Focused tests compare all finite exponent fields with representative mantissas
and signs against F32.rational, plus fixed random finite words and near-unit
quaternions. They cover adjacent-word component/norm boundaries, subnormal
negative-dot versus zero-dot continuity, tracking thresholds, timestamp and
duration endpoints, literal golden wire bytes/HMACs and unchanged structural
rejections. The existing authenticated quality regression suite is also executed
inside candidate mode.

Receiver controls verify bad-tag rejection before quality, malformed/replay/gap
and valid-tag quality rejection, unchanged state on refusals, refusal of release
for rejected results and subsequent exact-next valid acceptance. A sender-side
envelope check refuses bad quality before computing a tag. Mode-restoration and
unchanged parser/HMAC/verifier-method identities are explicitly checked.

These are nonsecret synthetic unit fixtures, not formal Tier-1 trial counts,
classifier accuracy, general security proofs or new PUF reliability samples.
Full-repository tests remain a separate checkpoint after focused tests pass.

## Next controlled measurement, not executed by this step

Freeze the candidate and a small paired benchmark protocol before obtaining new
timings. Use the same frozen dataset, model bytes, thresholds and baseline
single-read reconstruction configuration for both modes. Compare only the three
requested configurations: logistic/logistic, logistic/forest and SNN-32 seed 7 /
forest. Seed 7 is the original predeclared first SNN checkpoint, not selected
because of its latency. Keep other seeds' historical results as context.

Use isolated fresh workers and counterbalanced order; pair source/noise streams,
input bytes, output predictions, functional decisions and call/state counts.
Retain admission failures and rejected paths separately instead of deleting
them. Preserve automatic GC rather than hiding cleanup outside timers. Record
cleanup time, sustained closed-loop throughput and process resource behavior
alongside timings; no OS tracing or architecture/threshold search is planned.

Measure direct recurring and fresh first-window totals plus consistent stage
boundaries. Never add stage p95 values to manufacture a total p95. Keep any
unisolated lock/sequence/state or key-confirmation remainder labeled honestly.
The two-second acquisition window stays visible; physical acquisition, network,
loading/enrollment, evidence I/O and durable audit storage remain excluded.

No speedup, target attainment, production adoption, default pipeline change or
completed controlled benchmark is claimed until that later experiment passes
equivalence/reconciliation and its accepted/refused timing results are reviewed.
