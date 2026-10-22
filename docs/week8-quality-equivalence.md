# Week 8: expanded quality-check equivalence validation

Date: October 22, 2026. Owner: Keegan.

## Scope

This work extends the optional exact-integer quality implementation's behavioral
validation. It does not change the production validator, its default, numerical
tolerances, authentication/recovery policy, saved models or alert thresholds.
It is independent of the missing historical archive and of the separate
three-arm evidence inventory path issue.

New file: `tests/test_quality_differential.py`. The starting project commit is
`c8a4053f8526b91dd856428fa0924d214f367106`; the new test and this note are current
uncommitted additions, not part of that commit. The new test file's observed
SHA-256 is `f994f6b9f318bff6e64d34f258e0f04fa5ab9a72864465fabfb5ca67762d035`.

## Added coverage

Six test methods use declared fixed seeds and disposable public synthetic
fixtures. They are not new train/validation/test dataset examples or scientific
trial counts.

- Reproducible, nonidentical 120-sample windows with varying positions,
  orientations, tracking counts and sample timing.
- 24 valid sender windows: exact payload bytes, parsed values, envelope bytes
  and HMAC tags agree across Fraction and integer modes for identical input/key.
- Sender-side quality and structural refusals preserve the exact reason.
- Adjacent binary32 words around existing component/norm limits, zero norm and
  quaternion sign discontinuity at seeded sample positions.
- Three paired eight-window streams through independently admitted real
  verifiers. Each stream interleaves valid traffic with shuffled quality,
  invalid-tag, schema, malformed-message, future-gap, duplicate and stale
  refusals as applicable. Refusals leave session state and consumer call counts
  unchanged; the exact next valid window remains acceptable.
- The actual exactly-once classifier-release gate and existing 120-by-7 SNN
  sequence / 48-value anomaly feature extractors receive only accepted data.
  Their input arrays agree byte-for-byte across modes, deterministic probe
  outputs agree, and repeated delivery is refused.
- Authenticated quaternion-boundary and invalid-representation mutations are
  refused without advancing the sequence, followed by successful exact-next
  continuation in both modes.

Fresh sessions correctly use different random IDs, keys and deadlines. The
stream comparison projects relevant state values rather than changing real
packets or forcing cryptographic randomness to match. Sender byte/tag identity
is checked separately using one identical public synthetic input and key.

## Results and reproduction

Initial focused execution: six new tests passed with no failures, errors or skips
in the existing Windows CPython 3.13.14 project environment. No new dependency
installation or clean-machine reproduction was performed.

The subsequent combined regression command below passed **60 tests**, with zero
failures, errors or skips: 26 existing exact-arithmetic tests, 28 existing
benchmark-control tests, and the six new differential tests. This is a focused
regression result, not a run of every repository test group.

Run the focused regression group from the repository root in PowerShell:

```powershell
$env:PYTHONPATH = "$PWD\src\python;$PWD\tests"
$env:PYTHONNOUSERSITE = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
& .\.venv\Scripts\python.exe -B -m unittest -v test_quality_dyadic test_quality_benchmark test_quality_differential
if ($LASTEXITCODE -ne 0) { throw 'Quality equivalence or benchmark-control regression failed.' }
```

The initial six-test smoke run and the combined run overlap. Do not sum repeated
test executions as additional distinct coverage. Unit-test elapsed seconds are
not window-processing latency.

## Limits and next step

The consumer outputs here are deterministic test probes, **not predictions from
the saved trained logistic/forest/SNN models**. Exact feature agreement supports
the intended boundary but does not replace a bounded frozen-model integration
check. These fixtures also do not measure reconstruction reliability, new
latency, headset behavior or security strength.

Follow-up completed later in this session: the separate bounded frozen-model
command compared both quality modes and both existing recovery policies on the
declared validation cohort. All 180 quality pairs matched. See the
[Week 8 decision and actual results](week8-keegan-validation.md). This does not
turn the probe outputs in this test file into trained-model predictions.

Normal supported activation/rollback still needs shared review before any
default change. The existing mode selector remains isolated and serial-only;
concurrency is not newly supported by these tests.
