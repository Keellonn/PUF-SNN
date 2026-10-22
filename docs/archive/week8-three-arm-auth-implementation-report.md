# Week 8 implementation and validation report

Status: infrastructure implemented; complete proposed tests delivered as a patch;
automated runtime validation remains pending local execution.
No nonformal pilot or formal study was executed. No completed experiment bundle
or completion marker was produced. This implementation is not yet ready for an
independent experiment-harness acceptance audit.

## Source identity and preserved work

Branch: `main`. HEAD: `d4e27abe42b7ac8ccd59f5c024c9ab3ca351bc53`.
The checkout already contained changes to `docs/research-logs/will.md`,
`src/python/puf_snn/auth/credential_verifier.py`, `auth/sender.py`, `auth/session.py`
and `pipeline_v2.py`, plus untracked `auth/stored_credential.py` and
`tests/test_stored_credential_pipeline.py` (Python paths relative to
`src/python/puf_snn/` unless fully stated). Those changes were inspected, including
the latest-invocation versus prepared-attempt status correction, and preserved.

A before/after SHA-256 comparison checked 1,741 pre-existing files under source,
tests, configurations, schemas, documentation and results. Zero changed.
The original two-policy configuration, source, schemas, evidence and research
log remain byte-for-byte as found. Git configuration was not changed; read-only
Git commands used a per-command safe-directory option. Nothing was committed
or pushed. New deliverables remain untracked.

## Exact files added

- `configs/three_arm_auth_v1.json`
- `schemas/three-arm-auth-config-v1.schema.json`
- `schemas/three-arm-auth-plan-v1.schema.json`
- `schemas/three-arm-auth-attempt-v1.schema.json`
- `schemas/three-arm-auth-summary-v1.schema.json`
- `src/python/puf_snn/experiments/three_arm_auth_v1.py`
- `src/python/puf_snn/experiments/three_arm_auth_runtime_v1.py`
- `src/python/puf_snn/experiments/three_arm_auth_evidence_v1.py`
- `src/python/scripts/run_three_arm_auth_v1.py`
- `docs/week8-three-arm-auth-methodology.md`
- `docs/week8-three-arm-auth-implementation-report.md`
- `docs/week8-three-arm-auth-tests.patch`
- `docs/week8-three-arm-auth-local-validation.md`
- `docs/week8-three-arm-auth-source-manifest.json`

The authorized fallback patch adds `tests/experiments/test_three_arm_auth_v1.py`
when applied locally. That test file could not be created by the agent and is
not yet present in the working tree.

No pre-existing file was modified. Development scratch files in ignored `tmp/`
are `week8-initial-state.json` (preservation hashes) and
`build_week8_schemas.py` (generator for new standalone schemas).

## Implemented design

The new planner recognizes exactly the two existing PUF acquisition policies
and `stored-provisioned-v1`. It uses a separate experiment identity, new device
and measurement-domain identities, deterministic block scheduling and all six
arm orders. It provisions the same enrolled credential into a bound trusted
in-memory provider before timing and creates fresh endpoints for every arm.

Existing enrollment, correlated-noise equations, acquisition, BCH decoding,
independent verification, admission, shared Authentication-v2 handshake, fixed
window template, release gate and recording consumer are reused. The stored
entry invokes the existing `establish_stored` path. Instrumentation wraps actual
verification and `authorize_with_outcome` once, captures real oscillator calls,
decodes and retrieval spans, and distinguishes callback entry/completion.
It changes no production authentication or cryptographic implementation.

Stored reconstruction fields and absent decode timings are null. PUF C/D/I/W
and stored retrieval outcomes have separate summary contracts. Reconciliation
checks complete scheduling, identities, enrollment replay, PUF readings and
decoder replay, actual operation counts, source-specific outcomes, verification,
admission, handshake/endpoint activation, accepted windows, release/callback
counts and nested timing. Infrastructure faults cannot complete a run.
The evidence writer uses a new exclusive Week 8 namespace and retains an
INCOMPLETE sentinel until semantic reconciliation and a second manifest audit
succeed. This behavior has not yet been exercised by automated tests.

One stored invocation is scheduled per matched trial/noise cell. It is repeated
control workload, not independent noise-response evidence. Population counts
remain 20 for a planned allocation and one for the bounded pilot design.
Actual handshake entropy remains OS random and unmatched. The timing contract
is cold-process with zero harness warm-up; recurring-window timing is deferred.
No nonformal intervals or significance tests are implemented. See the companion
methodology for estimands, paired whole-population resampling, zero-event limits,
timing exclusions, conditional-cost interpretation and physical-security limits.

## Validation actually performed

`python -m compileall -q` on the three new experiment modules and the new runner:
exit 0, four modules compile. A second stdlib `compile()` check also passed.
Python was `C:\msys64\ucrt64\bin\python.exe`.

Stdlib JSON parsing of the new configuration and four schemas passed. All four
schemas have closed top-level properties and matching required/property sets.
Static assertions passed for exactly three policy IDs, planned-formal default,
`formal_execution_enabled=false` and zero configured warm-up. These checks do
not constitute JSON Schema validation or behavioral test coverage.

Additional AST/source consistency checks passed: runtime attempt fields match
the attempt schema; planner trial/plan fields match the plan schema; summary
and metric fields match their schemas; all timing/operation stage sets agree;
configuration constants agree with their schema; instrumentation targets
`verify` and `authorize_with_outcome` once each, with no `authorize` wrapper.
Reconciliation now validates row schemas before indexing their attempt IDs so
malformed rows are rejected as evidence errors.

The attempted regression command was:

```powershell
$env:PYTHONPATH='src/python'
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_stored_credential_pipeline.py' -v
```

It exited 1 before collecting tests: the virtual environment cannot access its
base interpreter at
`C:\Users\wwall\AppData\Local\Programs\Python\Python312\python.exe`.
An out-of-sandbox interpreter probe was not executed because automatic approval
review failed with reviewer-model capacity errors. A sandbox-only compatibility
probe using the MSYS interpreter and the existing site-packages also failed:
`ModuleNotFoundError: No module named 'rpds.rpds'` while importing jsonschema.
The available interpreter cannot use those native extension packages.

Automated tests collected/executed: zero. No pass/failure count is asserted for
the current stored, Majority-3, admission, correlated-noise or previous harness
suites. The historical report of 353 passes was not independently reproduced.

## Blockers and remaining work

Repeated attempts to create `tests/experiments/test_three_arm_auth_v1.py` were
not executed: automatic approval review reported its selected model at capacity.
That file does not exist. Following the user's explicit fallback instruction,
the full proposed file is supplied in `docs/week8-three-arm-auth-tests.patch`.
`git apply --check -- docs/week8-three-arm-auth-tests.patch` exited 0. The
proposed file compiled and parsed successfully using the stdlib, with 35 test
methods. No test method was executed. The tests cover deterministic counts/order,
strict configuration, provisioning/device binding, real C/D/I/W and stored
outcomes, zero stored PUF/BCH calls, independent admission, rejection before
HKDF, window/release rules, status attribution, faulting callbacks, evidence
tampering, interruption, historical paths, replay rejection and formal gates.

The runtime source-manifest check explicitly refuses execution while that
required test artifact is absent. After applying the patch, the operator must
still obtain actual passing test results before any pilot. File presence alone
is not evidence that tests passed. No runtime source identity, validated evidence
receipt, observed authentication counts or timing results are available. A
separately labeled static checkout manifest records current local source hashes;
it is not an execution receipt or attestation.

Use `docs/week8-three-arm-auth-local-validation.md` for exact PowerShell commands
to check/apply the patch and run the new suite, relevant existing regressions
and full authentication/admission suite with `.\.venv\Scripts\python.exe`.
The user's local environment works; the agent did not create, replace, reinstall
or modify it. Its base interpreter remains inaccessible in this sandbox.
Only after the tests pass may the single authorized 50-cell,
150-arm nonformal pilot run and reconcile. Do not expand its allocation.
The implementation may require fixes revealed by those tests; static checks
alone cannot establish correctness or audit readiness.

Formal execution remains disabled in the new configuration, runtime adapter,
writer and CLI. Historical formal gates were left untouched. No formal-scale
execution, deterministic production handshake entropy, cryptographic change,
model/training change, evidence overwrite, research-log edit, commit or push
was performed.
