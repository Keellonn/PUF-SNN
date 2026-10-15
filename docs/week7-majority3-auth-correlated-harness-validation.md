# Week 7 — Majority-3 Authentication-v2 Correlated-Noise Harness Validation

**Owner:** Will Wallace  
**Version** 1.0  
**Status:** Complete
Original corrective checkpoint: October 13, 2026. Subsequent progress: October 14, 2026.


## Current Status

The integrated harness implements matched single-read/Majority-3 comparisons and evidence-v2 validation. The independent re-audit is reported **PASS**, with all F1–F7 corrections verified. The 100-attempt nonformal smoke completed successfully and has a valid `NONFORMAL_VALIDATED.json` completion marker. Formal execution remains disabled; formal reliability and latency evaluation remain pending.

The re-audit attribution and smoke evidence are detailed below. The original October 13 corrective report follows separately, preserving its **449 passing tests**, F1–F7 implementation details, evidence revision, and source identities.

## Independent Re-Audit and Nonformal Smoke Results — October 14, 2026

### Independent re-audit and evidence attribution

**Independent re-audit verdict: PASS; all F1–F7 corrections verified.** This verdict
is reported in the project update supplied for this documentation revision. A
standalone independent re-audit record was not located in the available repository
documentation or local Week 7 records; the verdict retains that attribution.

The smoke outcomes below are supported by the saved [attempt records][smoke-attempts],
[summary][smoke-summary], [validation receipt][smoke-validation], and
[completion marker][smoke-marker]. The two built-in reconciliation passes are
smoke-finalization checks, distinct from the independent source re-audit. This
documentation review inspected existing evidence without running a new audit,
experiment, test, or benchmark.

### Execution and functional outcomes

Run ID: `week7-majority3-auth-correlated-v1-nonformal-20261014-001`.
The smoke used one synthetic population and one device, with ten matched trials
per condition across five conditions. It completed **50 matched trials, 100 policy
attempts, and 200 measured readings**. Each matched trial included both policies;
their enrollment, session inputs, and first reading were matched.

| Recorded outcome | Single-read | Majority-3 | Total |
| --- | ---: | ---: | ---: |
| Completed policy attempts | 50 | 50 | 100 |
| Measured readings | 50 | 150 | 200 |
| Correct credential reconstructions | 47/50 | 50/50 | 97/100 |
| Decoder failures | 3 | 0 | 3 |
| Sessions established | 47 | 50 | 97 |
| Protected windows accepted | 47 | 50 | 97 |
| Authorized inference releases | 47 | 50 | 97 |
| Unauthorized releases | 0 | 0 | 0 |
| Preprocessing recording callback invocations | 47 | 50 | 97 |
| Motion recording callback invocations | 47 | 50 | 97 |
| Anomaly recording callback invocations | 47 | 50 | 97 |

All three decoder failures occurred under `independent_stress`, in single-read
attempts. They were completed fail-closed authentication refusals, with no emitted
protocol request, active session, protected window, or downstream callback. No
invalid-format or valid-format wrong-credential reconstruction occurred. The 97
established sessions each accepted one sequence-0 protected window and released
inference once; all three recording callbacks therefore ran 97 times each.

The recording consumers observe authorized release and callback execution. They
do **not** measure actual SNN/anomaly inference, prediction accuracy, or model
processing latency.

### Reconciliation, resource accounting, and completion

Both finalization reconciliation passes succeeded. Their recorded work reconciles
to **603 total simulator measurement invocations**:

| Recorded work | Measurement invocations |
| --- | ---: |
| Measured policy acquisition | 200 |
| `pre_summary` replay | 200 |
| `manifest_audit` replay | 200 |
| Execution enrollment/reference setup | 1 |
| Reference setup for the two replay passes | 2 |
| **Total** | **603** |

Thus replay accounts for 400 readings and reference/setup work for three readings.
Replay adds zero statistical samples. The completion marker and validation receipt
both record `status: PASS`; the marker records the 100 completed policy attempts,
50 matched trials, 200 measured readings, and zero unauthorized releases.

The marker's artifact-manifest SHA-256 is
`34652eed36b49b1fb55949fefd40f9e29ece1f5214ac306d1bf892a8ab5ee59e`.
Read-only inspection for this revision confirmed that hash and all **82 manifest
members** (74 source-snapshot files plus eight evidence records). This byte-level
check does not constitute a new semantic replay or independent post-run audit.

The smoke retains evidence revision `week7-majority3-auth-correlated-v1:evidence-v2`
and the corrected 74-file runtime source identity:
`c427234f9c37daf558a46c9732227bb296f4829433fe46cb3a6f927674dfcb07`.
The resolved nonformal configuration and plan identities match the October 13
provenance record below; their saved copies are in the [evidence directory][smoke-directory].

### Observed median timings and interpretation

The following are inclusive stage medians in milliseconds, pooled across the five
conditions. They retain all recorded attempts, including first use. Acquisition,
reconstruction, and establishment each have 50 spans per policy. First-window
timing includes only eligible established sessions: 47 single-read and 50 Majority-3
spans. Establishment includes failed attempts as well as successful sessions.

| Stage | Single-read | Majority-3 |
| --- | ---: | ---: |
| Acquisition | 0.352 ms | 1.024 ms |
| Reconstruction | 1.194 ms | 1.077 ms |
| Session establishment | 2.069 ms | 2.606 ms |
| First protected window | 8.736 ms | 8.746 ms |

These are **nonformal diagnostics affected by instrumentation and first-use
compilation**, not a controlled latency benchmark. The first measured Majority-3
attempt recorded 2343.180700 ms in BCH decode and 2344.544900 ms in establishment;
the excess is consistent with lazy galois/Numba compilation, but the compilation
share was not independently profiled. All samples remain in the official summary.
The runner performed no warmup loop. Nested inclusive stages must not be summed,
and an uninstrumented control is unavailable to isolate observer overhead.

This one-device, one-population smoke demonstrates bounded functional execution
and internally reconciled nonformal evidence. It does **not** prove a statistical
reliability or latency improvement. Bootstrap intervals are suppressed
(`suppressed_insufficient_populations`): zero resamples were performed, and interval
bounds and confidence level are null. Zero observed failures in a cell does not
establish zero failure probability.

Formal execution remains disabled: the CLI has no formal-run command, and the
evidence writer rejects planned-formal execution. Formal reliability and latency
evaluation require a separately reviewed study design, execution/completion gate,
frozen provenance, resource accounting, and timing protocol. The synthetic model,
32-bit pilot credential, co-located software trust, and recording-consumer
limitations remain.

[smoke-directory]: ../results/week-7/will/majority3-auth-correlated-v1/nonformal/week7-majority3-auth-correlated-v1-nonformal-20261014-001/
[smoke-attempts]: ../results/week-7/will/majority3-auth-correlated-v1/nonformal/week7-majority3-auth-correlated-v1-nonformal-20261014-001/attempts.jsonl
[smoke-summary]: ../results/week-7/will/majority3-auth-correlated-v1/nonformal/week7-majority3-auth-correlated-v1-nonformal-20261014-001/summary.json
[smoke-validation]: ../results/week-7/will/majority3-auth-correlated-v1/nonformal/week7-majority3-auth-correlated-v1-nonformal-20261014-001/validation.json
[smoke-marker]: ../results/week-7/will/majority3-auth-correlated-v1/nonformal/week7-majority3-auth-correlated-v1-nonformal-20261014-001/NONFORMAL_VALIDATED.json

## October 13, 2026 — Corrective Implementation and Validation Record

The following sections preserve the original F1–F7 corrective report. Statements
that re-audit or smoke execution were pending, that no finalized Week 7 research
evidence existed, and that resource counts were planning expectations describe
the October 13 checkpoint. Its Git status is also a historical snapshot.

Date: 2026-10-13 (America/New_York).

### Overall verdict

**Verdict at the October 13 checkpoint:**

F1–F7 are addressed by experiment-local implementation and deterministic regression fixtures. Independent re-audit remains required before separately authorizing the proposed smoke. No 100-attempt smoke, formal study, stochastic reliability sweep, timing benchmark, commit, or push was performed. Unit-test completion markers are development artifacts, not research results. Formal execution remains disabled.

The independent source audit had returned **CONDITIONAL — Specific fixes required
before the 100-policy-attempt nonformal smoke**. Initial inspection confirmed
`main`, HEAD `0895f920e29e16e6fd280f9c4b5cd3bcfb584ac3`, two tracked modifications,
21 untracked development files, and no staged files. There was no material source
discrepancy. An apparent missing instrumentation block in an initial tool display
was disproved by a narrower line-by-line read before editing.

### Findings resolution

Source names below refer to `src/python/puf_snn/experiments/` unless specified.
New tests are in `tests/experiments/test_majority3_auth_corrections.py`.
Original severity was not specified for recommended F6 and F7.

| Finding | Original severity | Resolution and modified source location | Supporting regression | Remaining limitation |
| --- | --- | --- | --- | --- |
| F1 | High | `majority3_auth_evidence_v1.py::validate_protocol`, `validate_timing`, `reconcile`; runtime `Capture.wrap` records verifier outcomes | `test_original_counterexample_rehashed_and_resummarized_is_rejected`, `test_real_partial_timeouts_pass_full_reconciliation`, window/endpoint mutation matrices | Semantic consistency is not a signature or remote attestation |
| F2 | Medium | Runtime `Capture.wrap` and `execute_attempt` distinguish issuance/configuration/verification faults; writer stops incomplete | `test_swallowed_issuance_exception_after_verification_is_a_fault`, `test_authorization_fault_stops_writer_and_preserves_actual_counts`, disabled/revoked and missing-service tests | Classification assumes the supported fresh serial service; policy changes are outside the study design |
| F3 | Medium | `resource_estimate`, `execution_resources`, `completion_resources`, reconciliation receipts, writer finalization phases; CLI `main`; planner count/schedule calculations | `test_smoke_plan_counts_without_executing_attempts`, `test_three_replay_phases_are_measured_not_hardcoded`, `test_replay_counts_and_audit_do_not_modify_evidence_or_statistics` | Interrupted work before a persisted observation may be unknown |
| F4 | Medium | `checked_output_path`, `EvidenceRun.__init__`, run-identity audit; authorization and plan hash are checked independently | historical-ID/root, traversal/alias, real Windows junction, exclusive-output and `test_correct_token_wrong_plan_hash_fails_independently_in_cli` | Requires a trusted local filesystem without concurrent malicious namespace mutation |
| F5 | Low | `DISCLOSURE`, writer metadata and audit enforcement; removed `secrets_persisted` | `test_disclosure_and_new_evidence_revision`, `test_rehashed_disclosure_claim_is_rejected`, retained public-field allowlist test | Public synthetic replay inputs are credential-equivalent; no confidentiality claim |
| F6 | Recommended; unspecified | `majority3_auth_analysis_v1.py::bootstrap_populations`, summary schema v2 | `test_one_population_suppresses_inferential_interval` | A one-population smoke provides no population-to-population uncertainty estimate |
| F7 | Recommended; unspecified | New paired-bootstrap and independent CLI negative tests | `test_every_draw_pairs_both_policies_and_all_conditions`, correct-token/wrong-hash CLI test | Formal statistical design still requires independent review |

### Source changes and evidence revision

#### Modified development files

Seven files from the initial development set were edited:

- `src/python/puf_snn/experiments/majority3_auth_v1.py`: separate evidence revision
  from experiment/RNG identity; select revision-2 attempt/summary schemas; derive
  policy counts, read counts and execution ordinals from the actual schedule.
- `src/python/puf_snn/experiments/majority3_auth_runtime_v1.py`: capture authorization
  diagnostics and actual verifier window results; classify swallowed issuance and
  configuration faults; invalidate otherwise swallowed exceptional timing spans.
- `src/python/puf_snn/experiments/majority3_auth_evidence_v1.py`: bidirectional
  protocol reconciliation, ordered conditional timing checks, portable output
  namespace enforcement, disclosure checks, planned/observed resource reporting,
  and incomplete-run accounting.
- `src/python/puf_snn/experiments/majority3_auth_analysis_v1.py`: suppress bootstrap
  intervals with fewer than two populations; retain point estimates.
- `src/python/scripts/run_majority3_auth_correlated.py`: CLI resource estimates
  explicitly separate measured acquisition, replay and enrollment/setup work.
- `tests/experiments/test_majority3_auth_v1.py`: retain all 42 existing tests;
  add semantic checking to existing C/D/I/W controls; adapt temporary destinations
  to the explicit test-output policy. No security assertion was removed.
- `docs/week7-majority3-auth-correlated-harness-validation.md`: this repair report
  supersedes the original pre-audit validation narrative and its broader secrecy,
  resource, audit-I/O, and one-population interval descriptions.

#### Added files

Three files were added:

- `schemas/majority3-auth-attempt-v2.schema.json`: required authorization diagnostics
  and verifier-window observations with strict fields and revision identity.
- `schemas/majority3-auth-summary-v2.schema.json`: explicit population count,
  performed resamples, suppression status and nullable confidence level.
- `tests/experiments/test_majority3_auth_corrections.py`: 32 new deterministic
  regression methods, including coordinated adversarial edits and negative CLI tests.

#### Evidence-v2 compatibility and preserved protocol behavior

New attempt, summary, metadata, validation receipt and completion-marker semantics
use `week7-majority3-auth-correlated-v1:evidence-v2`. The original v1 attempt and
summary schemas remain byte-for-byte intact. The current auditor rejects the old
evidence revision; it does not silently reinterpret or migrate it. No finalized
Week 7 research evidence exists and no migration outcome is claimed.

The experiment ID, config schema, plan schema, master/schedule/bootstrap seeds,
manufacturing/reference generation, five conditions, reading-0 matching,
Majority-3 vote, first-63 selection, BCH(63,36,t=5), credential generation,
production admission, Wire 2, HMAC and strict exact-next sequence rules are
unchanged. Keegan's model code and all production authentication functions were
preserved. `credential_verifier.py` required no production API change.

### Session evidence integrity

#### Establishment and endpoint semantics

Reconstruction still replays through the real decoder and independent credential
truth check. The new semantic validator then derives the establishment decision,
stage and reason from reconstruction, independent verification, authorization and
the terminal handshake branch. The recorded decision cannot substitute for that
derivation. It enforces the actual two-stage/four-stage sequence and valid
stage-specific success/refusal reason combinations.

Four accepted handshake stages imply both endpoints active and an accepted active
session. A successful receiver confirmation followed by sender timeout is instead
a valid failed establishment with receiver active and sender inactive. Receiver
and sender HKDF counts follow their actual challenge/confirmation outcomes; a
failed session can legitimately include one or both key derivations. Real clock
controls exercise pre-request capability expiry, receiver refusal after admission
expiry, sender timeout after challenge, receiver confirmation timeout and sender
timeout after receiver activation. Three partial-handshake cases also pass full
deterministic evidence replay. C/D/I/W controls retain their meaningful assertions.

#### Window and release consistency

Endpoint flags are sampled immediately after establishment, before a first window
can expire or close a session. Exactly an active establishment is eligible for the
first-window operation. Sender sealing refusal has no verifier observation.
Verifier-processed windows must match the separately captured production
`VerificationResult`: acceptance requires `accepted`, sequence zero, and an
accepted authenticated payload; rejection uses a rejection-only reason and omits
the untrusted sequence number, as the production API does. Releases and all three
consumer counts must equal legitimate verifier acceptance. Failed establishment
cannot have a window or release. Timing checks cover nesting, invocation counts,
execution order, actual HKDF dependencies and conditional first-window stages.

#### Adversarial regression coverage

The exact F1 counterexample now fails even after removing the first-window timing
subtree, zeroing release/model counts, clearing verifier-window observations,
regenerating the entire summary and recalculating the artifact manifest and marker
hash. Four retained successful stages cannot reconcile to rejected establishment.
Separate tests alter only the final decision, omit terminal success, contradict
either endpoint, use incompatible window reasons, invent acceptance after a
rejected verifier outcome, and retain releases without verifier acceptance.

### Authorization fault classification

The production `CredentialAdmissionService.authorize` validates its attempt and
timeout inputs, verifies the credential, enforces disabled/revoked policy, and
mints a local opaque capability. It catches issuance exceptions and returns None.
The study observer records its unchanged result and the nested verifier outcome.

- Correct candidate + `verified` + handle: `issued`; normal production path.
- Wrong valid-format candidate + `credential_mismatch` + no handle: legitimate
  authentication rejection, with no request, HKDF, session or release.
- `record_disabled` + no handle: `policy_refusal`, a legitimate disabled/revoked
  production policy outcome, not an issuance fault. It passes standalone protocol
  validation with the explicit policy-fixture option. Full study reconciliation
  rejects it as outside the fresh enabled setup, so it is not noisy-PUF FRR.
- `verified` + no handle: `issuance_fault` in the supported fresh serial setup.
  No concurrent policy mutator exists in that path. The deterministic test raises
  inside `_Admission` after real verification; the production API still returns
  None and emits no request. The experiment records a fault and stops incomplete.
- Missing record or missing nested verification: `configuration_fault`.
  Key-provider, binding, malformed-input and verifier internal faults are also
  invalid evidence. A missing service rejected during endpoint construction leaves
  the writer incomplete before any measured trial reading.
- Other exceptions or exceptional instrumented spans invalidate completion.
  Exception messages, objects and secret-bearing return values are not serialized.

An issued capability can legitimately expire at request binding or later handshake
admission; these supported refusals remain valid and are tested. No auth failure
was made fatal indiscriminately. Final reconciliation independently rejects a
verified/no-authorization contradiction even if its execution fault label is
erased. No cryptographic primitive, verification comparison, or admission decision
was changed, and no new permissive fallback was added.

### Resource accounting

#### Planned successful smoke

All figures below are **planning expectations on successful completion**, not
observed smoke results. The proposed smoke remains one population, one device,
ten matched trials per condition, five conditions and two policies:

| Category | Expected count |
| --- | ---: |
| Measured policy attempts | 100 |
| Measured trial reading invocations | 200 |
| Finalization validation-replay passes | 2 |
| Validation-replay reading invocations | 400 |
| Execution enrollment/reference readings | 1 |
| Validation enrollment/reference readings | 2 |
| Total simulator measurement invocations for a successful command | 603 |

The three reference readings remain setup work, including the two performed during
validation. The workflow also constructs three manufacturing/enrollment/credential
and helper-data sets, 100 execution endpoint pairs and 300 shared-noise vectors.
These setup operations are explicitly separate from measured trial acquisition.
Runtime, memory, RNG-draw, cryptographic-operation and full storage costs are not
estimated by these invocation counts.

#### Accounting design and interruption handling

Counts derive from scheduled policies' `read_count`, distinct device identities
and `FINALIZATION_REPLAYS`, the same phase tuple that drives actual finalization.
The first pass reconciles before summary creation; subsequent passes independently
audit the complete artifact set. At least one independent manifest audit is
required. A three-pass unit fixture observes 160 indexed readings (40 measured,
120 replay) and four reference readings, demonstrating workflow-sensitive counts.
Supported unit allocations with one/two populations and one/two devices are
covered. Configuration still permits exactly the two reviewed acquisition policies;
other policy sets are rejected by the unchanged strict configuration contract.

Metadata holds labeled expected counts. Each successful reconciliation receipt
records actual replay reader counts and completed enrollment constructions. The
completion marker and successful CLI result distinguish measured invocations,
returned observations and per-phase validation work. Replay adds zero statistical
samples and never changes summary denominators. Incomplete sentinels retain counts
from persisted attempts and completed enrollment catalogs, explicitly marking work
interrupted before observation/append as unknown. Failed simulator invocations can
exceed returned observations, and have a regression assertion for that distinction.

#### Standalone audit costs

Each later standalone audit adds 200 replay measurements and one reference reading
for this proposed smoke. It does not update cumulative evidence counts or append
new statistical samples. Audit is read-only **with respect to evidence files**;
it runs deterministic simulation, decoder replay and summary/bootstrap computation.
Python/Numba imports/JIT may create or warm caches outside the evidence directory.
`-B` suppresses Python bytecode writes, not every dependency cache. The audit test
compares evidence member sets and byte hashes before/after and observes replay calls.

### 7. Historical identity and output protection

Nonformal output must be a direct child of the portable repository-relative root:

`results/week-7/will/majority3-auth-correlated-v1/nonformal/`

Its basename must be `week7-majority3-auth-correlated-v1-nonformal-<suffix>`, with a
lowercase alphanumeric/hyphen suffix of 1–64 characters beginning alphanumeric.
Thus `tier1-v2-formal-001` and
`week6-reconstruction-alternatives-v1-formal-001` cannot be reused in a different
parent. Fresh directory creation remains exclusive; no existing destination is
overwritten. `RUN-100-NONFORMAL` and the exact reviewed plan hash are independently
required. This token is an accidental-execution guard, not a cryptographic grant.

Unit writers require an explicit `test_output_root`, an isolated directory beneath
repository `tmp` or the operating system temporary root. Their direct-child names
use `week7-majority3-auth-correlated-v1-unit-<suffix>`. This override cannot be used
in nonformal mode or to select repository historical evidence trees.

Validation rejects lexical `..`, escaped/nested parents, UNC/device/drive-relative
paths, Windows stream/trailing-space/trailing-dot aliases, any existing symlink or
junction ancestor, case variants of Week 5/6 historical components, historical run
identity ancestors, and nesting beneath an existing evidence manifest/sentinel.
Containment compares resolved, case-folded parent paths. A real Windows junction
regression passed on this host. Checks do not provide a race-proof sandbox against
another local process concurrently replacing checked directories; the research
workspace and output namespace must remain trusted and exclusively controlled.

### Statistical and disclosure corrections

#### Population-bootstrap intervals and pairing

For fewer than two populations, point estimates remain available but interval
bounds and `confidence_level` are null, `performed_resamples` is zero, and
`interval_status` is `suppressed_insufficient_populations`. The one-population
smoke therefore cannot display a degenerate interval as a meaningful 95% CI.
With at least two populations, the existing seeded whole-population bootstrap,
FRR(single) minus FRR(Majority-3), attenuation contrasts, pointwise interval scope,
primary rho 0.90 and secondary rho 0.50 remain unchanged.

The new three-population paired fixture varies outcomes for **both** policies and
all five conditions. For every resample, it independently expands the same drawn
population indices across policies, conditions and both estimands, then verifies
all interval quantiles. The existing analytic direction/attenuation tests remain.

#### Synthetic replay disclosure

Metadata no longer says `secrets_persisted=False`. Its checked `disclosure` object
explicitly states literal credential fields, verifier secret keys, session keys
and authorization capabilities are omitted; synthetic pilot credentials **are
reconstructible from replay inputs**; replay material is **not confidential**;
and the intended audience is `public_synthetic_research`. No actual new protocol
secret is serialized. Public synthetic seeds/identities and enrollment information
are credential-equivalent research material. Source/environment metadata may also
expose machine-local paths and is not a personal-information redaction service.

### Validation commands and results

#### Recorded environment

Executing environment: CPython 3.12.4 (`tags/v3.12.4:8e8a4ba`, MSC v.1940 AMD64),
`Windows-11-10.0.26200-SP0`, executable
`C:\PUF+SNN_SharedRepo\PUF-SNN\.venv\Scripts\python.exe`.
Packages: galois 0.4.11, NumPy 2.5.3, Numba 0.67.0, SciPy 1.18.1,
jsonschema 4.26.0. No dependency or Git configuration was changed.
Tool-approved interpreter execution was needed because sandbox access to the base
Python installation initially failed. Repository ownership checks used per-command
`git -c safe.directory=...`; no persistent safe-directory setting was added.

#### Recorded commands

Every test shell set:

```powershell
$env:PYTHONPATH='C:\PUF+SNN_SharedRepo\PUF-SNN\src\python;C:\PUF+SNN_SharedRepo\PUF-SNN\tests'
```

Exact final regression commands (PowerShell):

```powershell
.\.venv\Scripts\python.exe -B -m unittest -v experiments.test_majority3_auth_v1 experiments.test_majority3_auth_corrections 2>&1 | Tee-Object -FilePath tmp/week7-corrective-baseline/test-group-1.log; exit $LASTEXITCODE
.\.venv\Scripts\python.exe -B -m unittest -q puf.test_correlated_noise_v1 puf.test_acquisition test_majority3_pipeline 2>&1 | Tee-Object -FilePath tmp/week7-corrective-baseline/test-group-2.log; exit $LASTEXITCODE
.\.venv\Scripts\python.exe -B -m unittest -q test_pipeline_v2 reconstruction.test_bch reconstruction.test_credential reconstruction.test_validation auth.test_credential_verifier auth.test_credential_admission auth.test_session auth.test_hkdf auth.test_protocol_rejection auth.test_verifier auth.test_classifier_integration auth.test_lifecycle_audit auth.test_layer3_integration test_frozen_pipeline test_inference_gate puf.test_device puf.test_puf puf.test_metrics 2>&1 | Tee-Object -FilePath tmp/week7-corrective-baseline/test-group-3.log; exit $LASTEXITCODE
```

#### Recorded results

| Suite | Passed | Failed/errors | Skipped | Development command duration |
| --- | ---: | ---: | ---: | ---: |
| Existing harness plus new correction regressions | 74 | 0 | 0 | 60.245 s |
| Correlated noise, acquisition, Majority-3 pipeline | 73 | 0 | 0 | 11.589 s |
| Production authentication, reconstruction and inference regressions | 302 | 0 | 0 | 67.545 s |
| Total distinct methods | **449** | **0** | **0** | Not a research timing result |

All three commands exited 0. No Python/dependency warnings were emitted.
Windows PowerShell formatted unittest's normal stderr output as a
`NativeCommandError` display record when piped through `2>&1`; it was not a test
failure. Original command output remains in the local ignored development logs.
Earlier focused runs passed the original 42 tests and the first 29 correction
tests; the final 74-method combined suite adds three further checks. No assertion
was weakened to obtain a pass. Historical pre-audit validation had reported 331
tests on its original source; that is a prior checkpoint, not an extra current count.

#### Schema, planning, and whitespace checks

All six old/new Week 7 schemas pass Draft 2020-12 schema checks. Real bounded
fixture attempts/summaries validate against v2. Read-only config/plan inspection
passes, including a 100-attempt/200-measured-reading smoke plan; it executes zero
attempts. Python source parses successfully. Tracked and new-file Git whitespace
checks pass using:

```powershell
git -c safe.directory=C:/PUF+SNN_SharedRepo/PUF-SNN diff --check
git -c safe.directory=C:/PUF+SNN_SharedRepo/PUF-SNN -c core.autocrlf=false -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --no-index --check -- /dev/null <each-untracked-file>
```

No-index exit 1 with empty diagnostics means differences, not whitespace failure.
CRLF and LF warnings during an earlier comparison were Git conversion notices;
the checks above account for native line endings without changing Git settings.

### Source and configuration provenance

The current runtime source identity covers **74** source/configuration/schema files,
including the existing tracked and untracked production-development bytes:

- Runtime source ID: `c427234f9c37daf558a46c9732227bb296f4829433fe46cb3a6f927674dfcb07`.
- Canonical resolved proposed-formal configuration: `c2efbf2b42bf6e6c389b2201428428089171e2840c5267c7ab26583977864026`.
- Configuration file bytes: `d94d31a30e9f49e9d8bb42946023cb054abe89ebc8c24a5af5087276e330dede`.
- Proposed formal plan (planning only): `89ff888246e3bbf3cdde7da115b11bf4bc5e9feb6c81f4409deb0944ac2840e5`.
- Nonformal resolved configuration: `ac440fdc24af8dafd72c1beffe83dd3d65b2dfd3f34308f9d41d5d437fb15bf6`.
- Proposed nonformal plan (planning only): `250c3e595aa7c0e46f66b87782c95c7a3229f79b32efd0b354dfc6015cdcd3eb`.

Source ID is SHA-256 of the canonical relative-path-to-file-SHA-256 map returned by
`source_hashes()`. The config and formal-plan identities are unchanged from the
pre-audit checkpoint. The former 72-file source ID was
`09fde0da800674bd8fb08e8dd3ca7c4f05fef3fe62e4292dde59e0f01fa8a2df`;
it has not been relabeled as the corrected implementation. Test files and this
document are outside the runtime snapshot closure. Every future run freezes its
own source manifest, actual config, plan and environment.

Baseline byte hashes covered 1,275 checkout files and 1,271 accessible historical
output files. All **747 Week 5/6 files** (126 Week 5, 621 Week 6, including ignored
evidence) have baseline entries and remained unchanged. All 1,271 baselined output
files remained unchanged. Some unrelated legacy `sim_results` directories could
not be enumerated by the sandbox; they were not written, and no full hash comparison
is claimed for those inaccessible directories. Original checkout files changed
only at the seven scoped locations listed in section 3; the three new files are
also listed there. Initial production/acquisition/noise changes were preserved.

### Remaining limitations and review scope

- Re-audit the new state-machine rules, local authorization classification,
  path policy and evidence-v2 schemas before separately authorizing the smoke.
  No implementation blocker is currently known.
- Unsigned hashes and recorded semantic observations are not proof against an
  actor capable of replacing source and all evidence consistently. Audit requires
  matching source bytes and the exact recorded Python/dependency environment.
- Policy refusal is a supported production outcome but an out-of-design condition
  for this fixed fresh enabled experiment; it cannot enter noisy-PUF session FRR.
- The serial monkey-patch observer is study-local, not a concurrent production
  telemetry API. Unexpected setup faults may prevent a complete attempt record;
  their run stays incomplete, with unknown interrupted work explicitly labeled.
- Filesystem checks assume no malicious concurrent directory replacement. They
  protect the supported writer namespace and reject existing aliases/ancestors.
- The synthetic Gaussian noise model remains uncalibrated; oscillator-noise rho
  is not binary-error correlation. The 32-bit pilot credential, co-located software
  key custody and recording consumer limitations remain. No reliability, latency,
  SNN accuracy or production-strength security claim follows from unit tests.
- Formal execution, formal completion markers, preregistration approval, physical
  calibration and any confirmatory research run remain outside this change.

### Final Git status

Branch `main`; HEAD `0895f920e29e16e6fd280f9c4b5cd3bcfb584ac3`.
Two tracked modifications, 24 untracked files, no staged files, no commit or push.
The two tracked modifications below were already present and are unchanged by
this repair; corrected existing development files remain untracked.

```text
M docs/authentication-v2-protocol-spec.md
 M src/python/puf_snn/pipeline_v2.py
?? configs/authentication_v2_majority3_acquisition.json
?? configs/majority3_auth_correlated_v1.json
?? docs/authentication-v2-majority3-validation.md
?? docs/week7-correlated-noise-model-validation.md
?? docs/week7-majority3-auth-correlated-harness-validation.md
?? schemas/majority3-auth-attempt-v1.schema.json
?? schemas/majority3-auth-attempt-v2.schema.json
?? schemas/majority3-auth-config-v1.schema.json
?? schemas/majority3-auth-plan-v1.schema.json
?? schemas/majority3-auth-summary-v1.schema.json
?? schemas/majority3-auth-summary-v2.schema.json
?? src/python/puf_snn/experiments/__init__.py
?? src/python/puf_snn/experiments/correlated_noise_v1.py
?? src/python/puf_snn/experiments/majority3_auth_analysis_v1.py
?? src/python/puf_snn/experiments/majority3_auth_evidence_v1.py
?? src/python/puf_snn/experiments/majority3_auth_runtime_v1.py
?? src/python/puf_snn/experiments/majority3_auth_v1.py
?? src/python/puf_snn/puf/acquisition.py
?? src/python/scripts/run_majority3_auth_correlated.py
?? tests/experiments/test_majority3_auth_corrections.py
?? tests/experiments/test_majority3_auth_v1.py
?? tests/puf/test_acquisition.py
?? tests/puf/test_correlated_noise_v1.py
?? tests/test_majority3_pipeline.py
```

Ignored local artifacts under `tmp/week7-corrective-baseline/` retain original
byte-hash maps, initial copies, final verification details and test logs for this
development task. Temporary unit evidence is cleaned by the test fixtures. These
are not historical research evidence or a smoke run.
