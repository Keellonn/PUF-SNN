# Week 7 — Correlated-Noise v1 Model and Matched Reader Validation

**Owner:** Will Wallace  
**Version** 1.0  
**Status:** Complete
Original checkpoint: October 12, 2026. Subsequent progress: October 14, 2026.


## October 14, 2026 — Subsequent Progress

**Current status:** The correlated-noise model is integrated into the Authentication-v2
experiment harness. Matched single-read/Majority-3 comparisons and evidence validation
are implemented. The independent harness re-audit returned **PASS**, as reported in
the October 14 project update; the attribution and available evidence are described
in the [integrated harness record](week7-majority3-auth-correlated-harness-validation.md).

The 100-attempt nonformal smoke passed. The full correlated-noise reliability study
remains pending; this functional smoke does not establish a statistical reliability
or latency improvement.

## October 12, 2026 — Implementation and Validation Record

The following record preserves the original equations, RNG design, assumptions,
validation methods, source identities, and **263 passing tests**. Its statements
about work not yet implemented or executed describe the October 12 checkpoint.

Date: 2026-10-12 (America/New_York). This record covers development implementation
and deterministic validation only. No experimental FRR or latency outcomes have
been generated. No formal experiment, large comparison, or historical runner ran.

### Scope and repository checkpoint

Branch `main`, HEAD `0895f920e29e16e6fd280f9c4b5cd3bcfb584ac3`, unchanged.
The initial worktree already contained the Majority-3 integration: modified
`docs/authentication-v2-protocol-spec.md` and `src/python/puf_snn/pipeline_v2.py`,
plus untracked `configs/authentication_v2_majority3_acquisition.json`,
`docs/authentication-v2-majority3-validation.md`,
`src/python/puf_snn/puf/acquisition.py`, `tests/puf/test_acquisition.py`, and
`tests/test_majority3_pipeline.py`. Those seven files were preserved byte for byte.

This stage adds only:

- `src/python/puf_snn/experiments/__init__.py`: package marker, no runtime actions.
- `src/python/puf_snn/experiments/correlated_noise_v1.py`: isolated model and reader.
- `tests/puf/test_correlated_noise_v1.py`: deterministic model and integration tests.
- `docs/week7-correlated-noise-model-validation.md`: this record.

No existing production source, configuration, historical evidence, experiment
runner, Week 5/6 manifest, or trial plan was edited. No commit or push occurred.
Git's ownership check required the per-command option
`-c safe.directory=C:/PUF+SNN_SharedRepo/PUF-SNN`; no Git configuration was changed.

### Inspected source and compatibility baseline

Inspection covered `puf/device.py`, `puf/ro_puf.py`, `puf/variables.py`,
`puf/acquisition.py`, `pipeline_v2.py`, `reconstruction_alternatives.py`, existing
device/PUF/acquisition/Majority-3 tests, the Majority-3 validation record, and the
Authentication-v2 protocol specification. No material design discrepancy required
a production-model change.

`Device` is a frozen dataclass whose manufacturing offsets are a tuple. The
existing frequency equation evaluates, in order, nominal frequency, manufacturing
offset, common environmental offset, aging offset, and independent measurement
noise. `Random.gauss(0.0, measurement_noise_std)` is called once per oscillator in
tuple order when its standard deviation is positive. Zero noise consumes no read
draws. Nonzero aging is explicitly unsupported. Finite negative modeled values
remain abstract values; there is no clipping.

Adjacent ordered pairs are `(0, 1), (2, 3), ..., (126, 127)`. Comparison is exactly
`int(f[u] > f[v])`, including zero for ties. The output is a tuple of 64 Python
integer bits. Acquisition accepts a zero-argument callback; default single-read
invokes it once, while Majority-3 invokes it three times and votes once. Both
enter the same single reconstruction and independent admission pathway.

The legacy adapter uses a continuing caller-owned RNG. The new experiment-local
adapter provides fresh indexed RNGs through the same callback interface, as
required for policy-independent matching. The legacy adapter remains unchanged.

### Mathematical model

For device d, attempt a, oscillator i, and reading r:

```text
f(d,a,i,r) = 100 + M(d,i) + C(d,a)
            + sigma * sqrt(rho) * Z(d,a,i)
            + sigma * sqrt(1-rho) * E(d,a,i,r)
```

The terms have distinct lifecycle roles:

- **M:** persistent manufacturing state supplied by the caller.
- **Z:** an independent standard-normal value per oscillator, fixed across readings
  of one attempt.
- **E:** independent standard-normal noise per oscillator and indexed reading.
- **C:** a caller-supplied finite, uniform additive offset for the attempt; v1 does
  not invent a distribution for C.

The session and reading RNG domains are separate.
All values use abstract simulator frequency units, without hardware calibration.

Writing N(i,r) for the Z and E terms, conditional on manufacturing and C:

```text
Var[N(i,r)]       = sigma^2*rho + sigma^2*(1-rho) = sigma^2
Cov[N(i,r),N(i,s)] = sigma^2*rho                 (r != s)
Cov[N(i,r),N(j,s)] = 0                          (i != j)

D(r) = M(u)-M(v) + sigma*sqrt(rho)*(Z(u)-Z(v))
                  + sigma*sqrt(1-rho)*(E(u,r)-E(v,r))
Var[D(r)]         = 2*sigma^2
Cov[D(r),D(s)]    = 2*rho*sigma^2
Corr[D(r),D(s)]   = rho                         (sigma > 0)
```

Increasing rho reallocates variance between components; it does not increase
marginal differential-noise variance. If a future planner randomizes C, raw
frequency variance also includes that common-mode variance, while D still cancels
C. Oscillator-noise rho is not binary response-error correlation. At sigma=0 the
noise variance is zero and a correlation coefficient is undefined.

At rho=0 the shared contribution vanishes. At rho=1 independent draws vanish and
all readings share their differential disturbance; voting cannot remove it.
At sigma=0 both components vanish and the ordinary noiseless response remains.

### Configuration and state

`NoiseConfig` is immutable and requires exactly `model_version`,
`oscillator_count`, `sigma`, `rho`, and `common_offset` in `from_dict`. Unsupported,
missing, or extra fields fail. Direct construction also requires every field.
The supported version is `puf-snn-correlated-noise-v1`, with exactly 128 ROs and
nominal frequency 100.

Negative sigma, rho outside [0,1], booleans, nonnumbers,
NaN/infinity, and unrepresentable integer magnitudes are rejected. A negative
finite C is valid. No value is clamped.

`AttemptIdentity` requires a nonnegative integer master seed and attempt ID,
nonempty printable population/device/noise-domain strings without edge whitespace,
and the supported model version. Booleans and float indices are rejected. Device
identity must match the supplied `Device`. Nonzero aging is rejected at binding.

`SharedDisturbance` contains the immutable attempt identity and 128 finite standard
normals. The reader derives it once. Every reading uses the same Device object,
manufacturing tuple, and shared state. The reader never creates a replacement
Device or changes manufacturing to represent session effects.

Shared standard normals are generated even when their scale is zero. Zero
independent scale makes no Gaussian read draws, matching the existing calculator.

### Frozen seed format and domains

`canonical_seed_bytes(identity, domain, reading_index)` serializes exactly:

```json
{"attempt_id":0,"device_id":"sim-device","domain":"independent-reading","master_seed":7301,"model_version":"puf-snn-correlated-noise-v1","noise_domain_id":"nominal","population_id":"unit-population","reading_index":0}
```

This is the golden test identity. Serialization is Python JSON with
`sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=True`, `allow_nan=False`,
then UTF-8 encoding without BOM or trailing newline. Strings are not normalized;
canonically equivalent but differently encoded Unicode strings remain different
identities. There are no floating-point fields in the seed object. The SHA-256
digest's full 32 bytes become an unsigned big-endian integer passed to a fresh
`random.Random`. Python's randomized `hash()` is never used.

The exact domain strings are:

- `manufacturing`
- `enrollment-reference`
- `credential-generation`
- `session-correlated-oscillator`
- `independent-reading`
- `common-mode-offset`

Only `independent-reading` includes `reading_index`, which must be 0, 1, or 2.
All other domains omit that key, and reject a supplied index. The generic seed
function exposes all six separate domains; the reader consumes only the session
and independent-reading domains. C is explicitly configured, so the common-mode
domain is reserved for a future planner that specifies its sampling distribution.
No manufacturing factory, enrollment procedure, or credential generator is
implemented in this module.

A future planner supplies a manufactured Device and retains separately designated
manufacturing and enrollment identities. For those lifecycle domains it must fix
the population/device identity, designate a stable `noise_domain_id` (for example
an enrollment generation), and fix `attempt_id`, rather than changing it with
measurement attempts. The unit fixture demonstrates manufacturing and reference
RNGs using this interface; the reader never receives the reference or credential.
These deterministic simulation seeds are not cryptographic entropy.

### Matched readings and common-mode control

No policy, acquisition count, execution ordinal, previous RNG state, or configuration
magnitude enters a noise seed. Given identical identities and noise configurations,
reading 0 therefore reproduces exactly under B0 and Majority-3 in either order.
Distinct reading indices derive distinct independent streams, although response
bits can legitimately agree. Failed and unrelated trials cannot advance another
trial's RNG. The condition/noise-domain identity must be recorded with configuration
by the future planner; the reader does not infer condition identities from sigma.

The common-mode control uses `common_mode_control(nominal_config, C)` and the
**same AttemptIdentity** as nominal. The helper changes only C; both conditions
therefore explicitly alias the same shared and indexed independent realizations.
A different reporting label for the control must not replace `noise_domain_id`.
This also supports the independent-noise cancellation control at rho=0.

Example for a caller-supplied persistent `device` (not an experiment runner):

```python
from puf_snn.experiments.correlated_noise_v1 import (
    MODEL_VERSION, AttemptIdentity, NoiseConfig, CorrelatedResponseReader,
    common_mode_control,
)
from puf_snn.puf.acquisition import SINGLE_READ, MAJORITY_3, acquire_response

identity = AttemptIdentity(7301, "population-v1", device.device_id, "nominal", 42)
config = NoiseConfig(MODEL_VERSION, 128, sigma=0.25, rho=0.0, common_offset=0.0)
b0 = CorrelatedResponseReader(device, config, identity, SINGLE_READ)
m3 = CorrelatedResponseReader(device, config, identity, MAJORITY_3)
control = CorrelatedResponseReader(
    device, common_mode_control(config, 8.0), identity, MAJORITY_3)
single_response = acquire_response(b0)  # Reading 0.
voted_response = acquire_response(m3, MAJORITY_3)  # Readings 0, 1, 2.
# Pass an unused reader to pipeline.establish with the same acquisition profile.
```

### Numerical implementation and reader contract

#### Simulator compatibility and numerical failure

`measure_indexed` invokes the unchanged `calculate_frequencies` on the original
Device with independent standard deviation `sigma*sqrt(1-rho)` and zero environment.
A private Random subclass records the actual scaled Gaussian draws for diagnostics
without changing generation order. Shared noise is then added, followed by C.
This is an algebraic reassociation of the approved equation. Zero-scale additions
are skipped. For rho=0 and C=0, tests establish exact tuple equality for both
frequencies and responses against the original calculator and `generate_response`
with the equivalent indexed RNG, including draw order and zero-noise behavior.

All comparisons use the existing `compare_oscillators`; ties remain zero. Finite
precision can change a comparison when adding a very large common offset. The
implementation compares responses with and without C and raises
`CommonModeNumericalError` if they differ. It does not silently substitute bits or
interpret the difference as physics. A deterministic fixture with margin 0.125
and C=1e20 demonstrates comparison collapse and the error. Exact rational algebra,
binary-exact fixtures, and ordinary seeded controls establish cancellation. Small
rounding differences in numeric pair differences are allowed only within explicit
test tolerances; response bits must match exactly. Nonfinite sums also fail.

#### Reader lifecycle and failure latch

`CorrelatedResponseReader` is a frozen binding with internally advancing counters.
Its zero-argument callback returns only a validated 64-bit tuple. Diagnostics live
in the separate `Measurement` result returned by `measure_indexed`; no reference
response, enrollment credential, or verifier key is retained by the reader.

The reader defaults to the existing single-read profile and permits one measurement.
An explicit Majority-3 profile permits indices 0, 1, 2 in that order. A fourth
reading (or second in the one-read profile) raises before measurement. A wrong
callback signature raises TypeError before any measurement. Every valid call runs
the calculator, even when rho=1 or sigma=0 causes identical responses. Responses
are never cached. `measurement_count` counts invocations started, including failures.
A failure latch is set before measuring and cleared only after valid output;
exceptions and malformed output permanently prohibit replacement reads. This is a
sequential trusted adapter, without a concurrency guarantee or remote attestation.

### Deterministic coverage

The 39 new unittest methods include subtests covering all requested categories:

- **Equation and endpoints (A):** exact scales (sigma=5, rho=0.36 gives 3 and 4),
  rho=0, rho=1, sigma=0, pair equations, ties, and 64 exhaustive orthogonal sign
  combinations at five rho values. This finite fixture has exact unit variances
  and zero cross moments; it verifies oscillator variance/covariance and pair
  variance/covariance/correlation directly. It is not a Gaussian Monte Carlo study.
- **Common-mode (B):** rational cancellation, binary-exact cancellation, matched
  components and bits for three rho values and all reading indices, and explicit
  investigation/rejection of an extreme floating-point artifact.
- **Differential disturbance (C):** a chosen shared vector flips a near-margin
  comparison; one shared vector persists across all readings; another attempt
  deterministically derives its own vector.
- **Matching (D):** repeated identities reproduce components and bits; each seed
  field participates; six domains and reading indices separate streams; three
  devices by three attempts run both policy orders with exact reading-0 diagnostic
  equality; failed/unrelated executions and global RNG state cannot perturb inputs.
- **Device and acquisition (E):** spies observe real simulator calls, the same Device
  and shared objects, independent RNG objects and 128 draws per nonzero-noise read,
  indices/counts, equal-bit fresh reads, immutable inputs, invalid configuration
  and identity matrices, wrong invocation, exhausted readers, and permanent failure
  latching at every reading position. Malformed tuples are rejected without retry.
- **Compatibility/security (F):** exact legacy agreement at four sigma values and
  all three indices; real pipeline acceptance under both policies; exactly one
  vote for Majority-3, one BCH decode, and independent verification; default single
  acquisition; real wrong valid-format credential rejected before request/HKDF;
  acquisition exceptions reach the existing fail-closed pipeline path.

No verification shortcut or alternative decoder was introduced. BCH(63,36,t=5),
the fixed first 63 response bits, 32-bit credential, independent verification,
local admission, HKDF/mutual handshake, authenticated windows, and inference release
remain unchanged. Existing relevant regression tests supplement the new fixtures.

### Validation execution

#### Recorded environment

Working directory: `C:\PUF+SNN_SharedRepo\PUF-SNN`.
Interpreter: `C:\PUF+SNN_SharedRepo\PUF-SNN\.venv\Scripts\python.exe`.
CPython 3.12.4 (`tags/v3.12.4:8e8a4ba`, Jun 6 2024, MSC v.1940 64 bit AMD64).
Platform: `Windows-11-10.0.26200-SP0`.
Installed dependencies: galois 0.4.11, NumPy 2.5.3, Numba 0.67.0, SciPy 1.18.1,
scikit-learn 1.9.1, PyTorch 2.14.0+cpu. No package changes were made.

The first environment-inspection command under sandbox restrictions exited 1 with
`No Python at ...Python312\python.exe`; it did not execute tests. Tool-approved
execution using the same repository environment outside that restriction succeeded.
The PATH MSYS Python was not used. Every test shell set:

```powershell
$env:PYTHONPATH = 'C:\PUF+SNN_SharedRepo\PUF-SNN\src\python;C:\PUF+SNN_SharedRepo\PUF-SNN\tests'
```

#### Recorded commands

Exact test commands:

```powershell
& '.\.venv\Scripts\python.exe' -B -m unittest -v puf.test_correlated_noise_v1
& '.\.venv\Scripts\python.exe' -B -m unittest -q puf.test_device puf.test_puf puf.test_metrics
& '.\.venv\Scripts\python.exe' -B -m unittest -q puf.test_acquisition test_majority3_pipeline
& '.\.venv\Scripts\python.exe' -B -m unittest -q test_pipeline_v2 reconstruction.test_bch reconstruction.test_credential auth.test_credential_verifier auth.test_credential_admission
```

#### Recorded results

| Suite | Passed | Failures/errors/skips | Warnings |
| --- | ---: | --- | --- |
| New model/reader/integration tests | 39 | 0 / 0 / 0 | None emitted |
| Existing PUF/device/metrics | 37 | 0 / 0 / 0 | None emitted |
| Existing acquisition/Majority-3 pipeline | 34 | 0 / 0 / 0 | None emitted |
| Additional baseline pipeline/BCH/credential admission | 153 | 0 / 0 / 0 | None emitted |
| **Total** | **263** | **0 / 0 / 0** | **None emitted** |

All four test commands exited 0 on their first execution; no test failures or
test-driven changes were needed. Recorded unittest durations were 11.372 s,
0.043 s, 9.276 s, and 42.664 s respectively; these are test-suite runtimes, not
acquisition or pipeline latency measurements. `git diff --check` passed.

Tracked-file whitespace command:

```powershell
git -c safe.directory=C:/PUF+SNN_SharedRepo/PUF-SNN diff --check
```

Each of the four new files also passed
`git -c safe.directory=C:/PUF+SNN_SharedRepo/PUF-SNN -c core.autocrlf=false diff --no-index --check -- /dev/null <file>`
with no whitespace diagnostics. An initial wrapper incorrectly treated the normal
no-index difference exit code 1 as a failure; the corrected check accepts that code
when diagnostics are empty. Git initially emitted an LF-to-CRLF advisory; the final
per-command `core.autocrlf=false` check inspects exact bytes without that advisory.
These were validation-command handling issues, not code or test failures. Repository
Git settings and source bytes were not changed to address them.

Counts represent test methods, not subtests or simulated fixtures. These are test
outcomes, not experimental reliability/latency observations. The PUF tests import
existing utility functions, but no historical runner or formal trial plan executes.

### Source and configuration identities

SHA-256 below identifies actual filesystem bytes, including existing uncommitted
Majority-3 work; HEAD alone does not identify that starting implementation. These
are development provenance, not rewritten historical manifests. Line-ending
conversion would change them.

- New `experiments/__init__.py`: `37a4c8c5f8a2c386a625cead09f694bebe1813331ef3a342b6f02890f740e53d`
- New `experiments/correlated_noise_v1.py`: `4115cd20ba5e896043d17a11a2c6d4bcee1aad72cf65267aa892d838bc42791f`
- New `tests/puf/test_correlated_noise_v1.py`: `90f6e6d2ee4593f154414c0ba040ecdf3547ab67ee06b17a151114c786ba394a`
- Existing `puf/device.py`: `a9298bd1f9b9f8c8bd6527f63c2cacd8fcb7fb4fe72fa3f1f1c847bedf130d2b`
- Existing `puf/ro_puf.py`: `ff553522eba5e94283ec49b668bb758a3e7595d03c3f5596666925edb4dbc995`
- Existing `puf/variables.py`: `128f6f7dd7ccc0dc4d5752b21525562149d661c6c79f9752be8fe132afd55af7`
- Existing `puf/acquisition.py`: `737bb216770a8d9392d3123b0ac7843127b23c1bb2870921e3b6570c8b2d1b89`
- Existing `pipeline_v2.py`: `85d0216b44c09edb369d5aa933f92026e3d23bc2eab34d2262ba6de30bc667e7`
- Existing `reconstruction_alternatives.py`: `86245db2f4f7e81177a32a373f23cbfe9b03218c2dfc41c49ae9e4c9b06ef596`
- Existing `configs/authentication_v2.json`: `b0ee45b8a3ee5cf6c4c25813e876847303ada4209abc4632bce903a331cf0f60`
- Existing `configs/authentication_v2_majority3_acquisition.json`: `79f8e46361c4abb35d60ccadf1f2fd4b319ce0082fc5f3806fed4055e0b5e412`
- Existing `configs/puf_baseline.json`: `fb54059dc268ef86300d90a4468fcf200b0c73d13c28fad1402a84a075271cda`

Source paths above without a repository prefix are under `src/python/puf_snn/`.
The seven initially dirty files were also hashed at inspection and checked again
after validation. No new external configuration file is needed for this stage:
strict `NoiseConfig.to_dict()` and `AttemptIdentity` provide explicit future
provenance inputs without modifying historical configurations.

### Limitations and readiness

- This is a behavioral Gaussian model, not measured Quest 3/FPGA noise or hardware
  security evidence. Spatial differential coupling, drift, aging, and realistic
  environmental sensitivities are not modeled. C alone cannot change ideal bits.
- Algebra tests establish variance allocation, not empirical Gaussian calibration,
  binary error correlation, FRR, integrated availability, or Majority-3 benefits.
- At extreme magnitudes, overflow or common-mode comparison collapse fails the
  measurement. The future runner must preserve such failures as execution/evidence
  failures, not ordinary authentication rejections or reliability observations.
- Canonical seed bytes are frozen; exact Gaussian/float outputs are validated in
  the recorded Python environment. Cross-version/platform `Random.gauss` and
  floating-point bit equivalence is not promised. Future manifests must pin these.
- Domain-separated SHA-derived seeds provide deterministic simulation stream
  separation, not a proof of PRNG independence or cryptographic unpredictability.
- The future planner owns fixed populations, manufacturing/enrollment generation,
  condition aliases, matching configurations, enrollment-generation binding,
  acquisition-profile consistency, and recording identities alongside evidence.
- A trusted callback does not attest physical device origin. The 32-bit pilot
  credential and existing co-located software trust assumptions remain unchanged.
- No full experiment runner, stage-level timing, evidence reconciliation,
  conventional provisioned-credential control, Majority-5, stronger BCH integration,
  or formal comparison has been implemented. No experimental FRR or latency
  outcomes have been generated or inferred from these tests.

With the focused checks passing, this model is ready to connect to a separately
versioned Authentication-v2 runner with stage timing and evidence reconciliation.
That runner must preserve these identities and numerical-failure semantics, freeze
its own sources/configurations, and undergo separate validation before experiments.
