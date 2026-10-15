# Week 7 — Majority-3 Authentication-v2 Integration Validation

**Owner:** Will Wallace  
**Version** 1.0  
**Status:** Complete
Original checkpoint: October 12, 2026. Subsequent progress: October 14, 2026.

## October 14, 2026 — Subsequent Progress

**Current status:** Majority-3 is fully implemented as an optional Authentication-v2
acquisition policy; single-read remains the default. The correlated-noise model and
integrated experiment harness have since been implemented. The 100-attempt
nonformal integrated smoke completed successfully.

Formal integrated reliability and latency evaluation remain pending. The smoke
is a functional diagnostic and does not establish a statistical reliability or
latency improvement. See the [correlated-noise model record](week7-correlated-noise-model-validation.md)
and the [integrated harness record](week7-majority3-auth-correlated-harness-validation.md)
for later implementation and smoke evidence.

## October 12, 2026 — Implementation and Validation Record

The following record preserves the original implementation details, security
invariants, source identities, and **419 passing tests**. Its execution and
readiness statements describe the October 12 checkpoint.

Date: 2026-10-12 (America/New_York). This is a development implementation and
functional-regression record, not a reliability experiment or formal validation.

### Repository checkpoint and scope

- Branch: `main`.
- HEAD before and after implementation: `0895f920e29e16e6fd280f9c4b5cd3bcfb584ac3`.
- Starting worktree: clean; no commits or local changes since the supplied audit.
- Git's sandbox ownership warning was handled with per-command
  `-c safe.directory=C:/PUF+SNN_SharedRepo/PUF-SNN`, without changing Git configuration.
- No branch switch, synchronization, commit, push, merge, reset, or clean occurred.
- No formal reconstruction-alternatives, Tier-1, or other research runner ran.
- Historical reports, results, configurations, source snapshots, plans, and
  manifests were not edited. SNN/anomaly implementations were not edited.

### Implementation and acquisition selection

#### Establishment and protected-window flow

The previous establishment call chain was:

```text
V2InferencePipeline.establish -> read_response() -> reconstruct
-> Sender.begin_attempt -> CredentialAdmissionService.authorize / verify
-> request creation
-> Verifier.begin_session (consume authorization, bind challenge, receiver HKDF)
-> Sender.answer_challenge (claim admitted candidate, sender HKDF, client proof)
-> Verifier.confirm_session -> Sender.finish_session
```

Only the acquisition call is replaced: `acquire_response(read_response, config)`
returns one effective 64-bit tuple before the unchanged single reconstruction.
The window path remains:

```text
seal_window -> verify_window -> pipeline release
-> ExactlyOnceClassifierRelease.deliver -> Verifier.release_accepted
-> preprocessing -> motion and anomaly callbacks
```

#### Policy selection and configuration

`AcquisitionConfig()` defaults to `single-read-v1`, read count 1. The candidate
profile `configs/authentication_v2_majority3_acquisition.json` has schema
`puf-snn-acquisition-v1`, policy `majority-3-v1`, and read count 3. Load it through
`AcquisitionConfig.load` and pass `acquisition_config=profile` to the pipeline
constructor.

`pipeline.acquisition_config.to_dict()` exports the exact secret-free
configuration for future experiment provenance. It is separate from the unchanged
strict `AuthConfig`, existing audit schema, and `SessionAttempt` fields.

#### Fresh-read contract and simulator behavior

Each completed Majority-3 acquisition calls the same bound reader exactly three
times. Each result must contain exactly 64 Python integer bits; booleans and
coercions are rejected. A position is 1 exactly when at least two reads contain 1.
The resulting 64-bit tuple enters the existing fixed first-63-bit BCH selection.
There is one decode and one independent verification/admission sequence, with no
retry, adaptive read, or hidden fourth read.

`SimulatedResponseReader` binds an immutable persistent 128-RO device, adjacent
disjoint pairs, read conditions, nominal frequency, and a caller-owned continuing
measurement RNG. It calls the existing `generate_response` on each invocation.
Manufacturing is sampled elsewhere only once.

Nonzero-noise tests establish 384
Gaussian calls across three readings and exact agreement with the state/output of
three direct simulator calls. Zero-noise tests establish no RNG consumption.

Custom callbacks retain the same trusted-source obligation as the baseline; their
physical origin cannot be proven by inspecting a returned bit tuple.

The historical `reconstruction_alternatives.majority_vote` accepts three or five
reads and lives with experimental stronger-BCH code. It remains unchanged. The new
three-only core utility uses its voting rule without importing the experimental
module; all eight bit truth tables are cross-checked against it in tests only.

#### Failure handling and authority boundaries

Acquisition failures stop immediately, possibly before all three reads, and do not
decode partial input. Acquisition/backend exceptions preserve the existing
`PipelineExecutionError` and incomplete-evidence handling. Ordinary reconstruction
and independent-verification failures preserve their original reject path.

These pre-handshake failures emit no request, derive no key, create no verifier pending
or active session/release authority, and call no model or preprocessor. The usual
later-handshake caveats still apply: failure after key derivation must not be
misreported as a universal no-derivation guarantee.

### Files changed

| File | Change and purpose |
|---|---|
| `src/python/puf_snn/puf/acquisition.py` | New strict profiles, three-only vote, acquisition loop, and bound simulator reader. |
| `src/python/puf_snn/pipeline_v2.py` | Keyword-only acquisition selection, observable immutable configuration, and acquisition call replacement. |
| `configs/authentication_v2_majority3_acquisition.json` | New explicit candidate identity; baseline JSON unchanged. |
| `tests/puf/test_acquisition.py` | 19 tests for voting, malformed input, strict configuration, read counts, device persistence, and RNG behavior. |
| `tests/test_majority3_pipeline.py` | 15 tests for real decoding, admission ordering, handshake compatibility, rejection/recovery, and release authority. |
| `docs/authentication-v2-protocol-spec.md` | Current specification updated for opt-in acquisition and its evidence limits. |
| `docs/authentication-v2-majority3-validation.md` | This validation, source-identity, and coverage record. |

### Security invariant review

All statuses below mean preserved within the existing trusted, co-located software
prototype, supported by source inspection and deterministic regression tests.
`candidate tests` refers to `tests/test_majority3_pipeline.py`.

| Invariant | Status | Supporting implementation/tests |
|---|---|---|
| Single-read remains the default | Preserved | Constructor defaults to `SINGLE_READ`; candidate `test_default_and_explicit_single_read_preserve_baseline`; original pipeline suite. |
| 32-bit credential and four zero padding bits | Preserved | Unchanged `reconstruction/credential.py`; real candidate decode and padding-failure tests; `reconstruction.test_credential`. |
| BCH(63,36,t=5) | Preserved | Unchanged codec/config; candidate requires five real corrections; `reconstruction.test_bch`. |
| Fixed response indices 0–62 | Preserved | Unchanged reconstruction selection; voted bit 63 excluded in candidate success; existing `test_fixed_subset_and_omitted_bit`. |
| Public code-offset helper format | Preserved | Unchanged enrollment and helper classes; helper equality between modes and independent code-offset tests. |
| Independent verification before request/HKDF | Preserved | Unchanged `Sender.begin_attempt`; real wrong valid-format candidate rejected, KDF spies uncalled, no authority minted. |
| Local admission authorization | Preserved | Unchanged service authorize/consume/bind/claim operations; candidate missing-authorization test; existing forged, swapped, expired, and revoked authorization tests. |
| Handshake message formats and mutual confirmation | Preserved | Candidate compares all four request/challenge/client/server messages byte-for-byte under identical fixture entropy; existing session and confirmation-tamper tests. |
| HKDF derivation and confirmation rules | Preserved | `auth/session.py` unchanged; successful candidate derives once per endpoint; `auth.test_hkdf` and `auth.test_session`. |
| Wire2 canonical serialization | Preserved | `binary_window.py` unchanged; sealed-envelope equality across modes; existing binary-window/rejection tests. |
| HMAC-SHA-256 motion authentication | Preserved | Unchanged sender/verifier HMAC; candidate protected-payload mutation retains old tag and is rejected. |
| Device, enrollment, and session binding | Preserved | Unchanged session/verifier ownership checks; existing `test_valid_tag_wrong_owner`, `test_enrollment_binding`, and admission binding tests. |
| Exact-next sequence and replay policy | Preserved | Both modes reject gap, duplicate, and stale packets, preserve accepted state, then accept the appropriate legitimate packet. |
| Verifier-issued inference authority | Preserved | Unchanged `release_accepted`; candidate rejects malformed-message results, fabricated accepts, and copied accepts before preprocessing. |
| At-most-once release | Preserved | Unchanged `ExactlyOnceClassifierRelease`; repeated release and consumer failure cannot redeliver; accepted sequence remains committed. |
| Failed acquisition/reconstruction/admission grants no authority | Preserved | Candidate tests assert no request, key, pending/active session, admission handle, accepted result, consumed event, or preprocessing/model calls. |
| Strict authentication configuration | Preserved | `AuthConfig`/baseline JSON unchanged; acquisition fields and the acquisition JSON are rejected by `AuthConfig`. |

### Executed validation

#### Recorded environment

Working directory for all commands: `C:\PUF+SNN_SharedRepo\PUF-SNN`.

Interpreter: `C:\PUF+SNN_SharedRepo\PUF-SNN\.venv\Scripts\python.exe`.
Python: CPython 3.12.4, MSC v.1940, Windows 64-bit (AMD64).
Installed versions: galois 0.4.11, NumPy 2.5.3, Numba 0.67.0,
PyTorch 2.14.0+cpu, scikit-learn 1.9.1.

The initial sandbox launch could not access the existing base interpreter under
the user's AppData directory. The same repository environment ran successfully
with tool-approved execution outside that sandbox restriction. No packages or
environment configuration were changed. The PATH MSYS Python was not used for tests.

#### Recorded commands

Set in each test process's PowerShell shell:

```powershell
$env:PYTHONPATH = 'C:\PUF+SNN_SharedRepo\PUF-SNN\src\python;C:\PUF+SNN_SharedRepo\PUF-SNN\tests'
```

Exact commands, in result-table order:

```powershell
& '.\.venv\Scripts\python.exe' -B -m unittest -v puf.test_acquisition test_majority3_pipeline
& '.\.venv\Scripts\python.exe' -B -m unittest -q reconstruction.test_bch reconstruction.test_credential reconstruction.test_reconstruction_alternatives
& '.\.venv\Scripts\python.exe' -B -m unittest discover -s tests/auth -q
& '.\.venv\Scripts\python.exe' -B -m unittest -q test_pipeline_v2 test_frozen_pipeline test_inference_gate
& '.\.venv\Scripts\python.exe' -B -m unittest -q puf.test_device puf.test_puf puf.test_metrics
```

#### Recorded results

| Suite | Tests | Passed | Failed/errors/skipped | Warnings |
|---|---:|---:|---|---|
| New acquisition and candidate pipeline | 34 | 34 | 0 / 0 / 0 | None emitted |
| Existing reconstruction unit tests | 58 | 58 | 0 / 0 / 0 | None emitted |
| Existing authentication suite | 237 | 237 | 0 / 0 / 0 | None emitted |
| Existing pipeline/frozen-integration/inference-gate tests | 53 | 53 | 0 / 0 / 0 | None emitted |
| Existing simulator/device/metrics unit tests | 37 | 37 | 0 / 0 / 0 | None emitted |
| Total | 419 | 419 | 0 / 0 / 0 | None emitted |

All five test commands returned exit code 0 on their first test execution. Counts
are unittest test methods, not the larger number of subtests or authentication
attempts inside fixtures. No code defects or security-assertion changes were needed
after the runs. `git diff --check` passed.

### New development-source identity

These are SHA-256 hashes of the tested local filesystem bytes, not a new commit or
formal experiment manifest. Line-ending conversion would change these hashes.

| File | SHA-256 |
|---|---|
| `src/python/puf_snn/puf/acquisition.py` | `737bb216770a8d9392d3123b0ac7843127b23c1bb2870921e3b6570c8b2d1b89` |
| `src/python/puf_snn/pipeline_v2.py` | `85d0216b44c09edb369d5aa933f92026e3d23bc2eab34d2262ba6de30bc667e7` |
| `configs/authentication_v2_majority3_acquisition.json` | `79f8e46361c4abb35d60ccadf1f2fd4b319ce0082fc5f3806fed4055e0b5e412` |
| `tests/puf/test_acquisition.py` | `e708919c2695bcef36b1102961fb77b4a4797a26660eba8e7ffced37c624385a` |
| `tests/test_majority3_pipeline.py` | `ad8b0724f425018b781f49aa1f2768d86d6f58e11f7bd071dd37aa5cdc20b0a0` |
| Unchanged `configs/authentication_v2.json` | `b0ee45b8a3ee5cf6c4c25813e876847303ada4209abc4632bce903a331cf0f60` |

`pipeline_v2.py` appears in the historical
`results/week-6/keegan/revision-evidence-index.json`, with historical hash
`0d9b482164f5e6da45ccd9ed4815ee1bc31f6d71ea66662bb15f0222e375be21`.
The modified current file is explicitly NEW development-source bytes. That
historical index was read only; its hash was not rewritten to match this candidate.
Future evaluations must freeze their own candidate sources and record both
authentication and acquisition configurations.

### Limitations and readiness
- Integrated nominal/session FRR and a controlled baseline-versus-candidate reliability comparison remain unmeasured at this checkpoint. Functional success is not an FRR result
- The Week 6 Majority-3 0.1000% nominal FRR measured standalone reconstruction on its own population; it is not evidence for this integrated candidate. Week 5's 1.625% and Week 6's 0.9833% baseline values used unmatched populations/noise streams with unchanged core reconstruction algorithms
- At this checkpoint, no correlated-noise model or evaluation was implemented. The existing independent per-oscillator/per-read Gaussian contract is retained
- Majority-3 adds exactly two reads plus voting/validation on a completed attempt. Acquisition latency, full-session latency, throughput, and physical acquisition cost remain unmeasured; three times the read count is not a measured latency ratio
- No conventional-credential control or comparative key-management/overhead study was implemented. The 32-bit credential, software custody, co-located trust model, and lack of physical hardware-root-of-trust evidence remain unchanged
- No formal research runners, reconstruction characterization sweep, full model training/evaluation, broad repository suite, or .NET cross-language check ran. The existing real SNN forward-path integration fixture did run in the scoped Python suite; it does not establish model accuracy or anomaly performance
- Custom callbacks are trusted to supply fresh reads from the correct persistent device; the bound simulator adapter provides that behavior for normal usage Reproducible seeds, stream partitioning, matching populations, configuration capture, and new source manifests belong to the separately reviewed study harness

The candidate is ready for a separately reviewed nominal pilot and subsequent
correlated-noise pilot once that separate model/study work is prepared. It is
functionally tested, not formally validated for reliability. No pilot was run.

Final intended change set: two tracked files modified and five new files, listed
above, on the unchanged branch/HEAD. All changes remain uncommitted.