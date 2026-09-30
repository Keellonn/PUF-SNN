# Credential Verifier Primitive Implementation

Phase 1, September 30, 2026. Implements the standalone comparison primitive from [the design](credential-verifier-design-week5.md), under the approved trusted co-located software pilot assumptions. The design document remains unchanged.

## Scope

Standalone primitive only; **not yet integrated into session/HKDF flow**. `CredentialAdmissionService` returns a comparison result, not a session authorization handle. Existing Layer 3 behavior, including its ability to derive from an unchecked valid-format candidate, is unchanged. No pre-HKDF rejection claim is made for the current session pipeline.

Files created:

- `src/python/puf_snn/auth/credential_verifier.py`
- `tests/auth/test_credential_verifier.py`
- `docs/credential-verifier-implementation-week5.md`

File modified: `src/python/puf_snn/auth/__init__.py`, exporting six public types: `CredentialVerifierRecord`, `CredentialVerifierKeyProvider`, `InMemoryCredentialVerifierKeyProvider`, `CredentialVerifierStore`, `CredentialAdmissionService`, and `CredentialAdmissionResult`. The latter name avoids colliding with the existing window `VerificationResult`.

No session, sender, receiver, reconstruction, Wire 2, audit schema, configuration, baseline manifest, or saved evidence changes are included. No local admission handles, networking, HSM/key-vault integration, persistence, or rotation service is implemented. No Tier 1 run, formal reconstruction rerun, 430-case evaluation, commit, or push was performed. Existing auth tests may exercise their small synthetic reconstruction fixtures; this is separate from rerunning a reconstruction experiment.

## Implemented Construction

```text
LP(x) = U16-big-endian(byte_length(x)) || x
M = LP(ASCII("PUF-SNN/credential-verifier/v1"))
 || LP(ASCII(device_id))
 || LP(ASCII(enrollment_id))
 || LP(ASCII(reconstruction_id))
 || LP(ASCII(verifier_key_id))
 || credential4
tag = HMAC-SHA256(K_verify, M)
```

The key and tag are exactly 32 bytes; the credential is exactly four bytes. No truncation, hexadecimal credential conversion, public credential hash, or credential-derived identifier is generated. Leading zero bytes are preserved.

Identifiers must be exact Python strings matching `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`. They are encoded as ASCII with no stripping, normalization, or case folding. Bytes, bytearray, memoryview, booleans, and non-ASCII strings are not coerced into valid identifiers. Credentials and keys must be exact `bytes`, not subclasses or other bytes-like objects. The reconstruction profile is an opaque trusted identifier: the primitive binds it, but does not execute or select a reconstruction implementation.

Framing/validation helpers remain private and have no dependency on the session or Wire 2 implementation. Tag verification uses `hmac.compare_digest` on two complete, validated, same-type 32-byte tags. This does not claim constant time for the entire lookup/verification operation.

## Enrollment Record

`CredentialVerifierRecord.enroll()` is the trusted enrollment entry point. It accepts keyword-only device, enrollment, reconstruction-profile and key identifiers, `credential4`, and a key provider. It frames the message, obtains that one key, and creates the record. It does not automatically insert/replace records or generate the credential.

Exact record fields:

| Field | Contents |
| --- | --- |
| `device_id` | Canonical, case-sensitive trusted device identifier |
| `enrollment_id` | Trusted enrollment generation identifier |
| `reconstruction_id` | Bound reconstruction profile identifier |
| `verifier_key_id` | Nonsecret key-provider lookup identifier |
| `tag` | Complete 32-byte HMAC-SHA-256 output, hidden from normal representation |
| `schema` | `puf-snn-credential-verifier-v1` |
| `algorithm` | `HMAC-SHA-256` |
| `enabled` | Exact boolean, initially `True` |
| `revoked` | Exact boolean, initially `False` |

There is no plaintext credential, reference response, helper material, verifier key, or session key field. Records are frozen dataclasses with slots. Direct construction represents an imported record and does not itself certify validity; verification checks every field. This permits unsupported/malformed records to be reported as explicit failures. Trusted `enroll()` performs input validation before creating a record.

`CredentialVerifierStore` copies an iterable of records into a read-only mapping indexed by `(device_id, enrollment_id)`. It rejects duplicate bindings even when one record is disabled or uses a different profile/key. It validates the record type and index identifiers on construction; other record validation happens at verification. It has no write/replace/re-enroll method. Different enrollment IDs for the same device can coexist; selecting the current trusted generation belongs to future integration, not this store.

Provisioning example (assumes `credential4` came from trusted enrollment; do not log it):

```python
from puf_snn.auth import (
    CredentialAdmissionService, CredentialVerifierRecord,
    CredentialVerifierStore, InMemoryCredentialVerifierKeyProvider,
)

provider = InMemoryCredentialVerifierKeyProvider.generate("pilot-verifier-key-1")
binding = dict(device_id="Device-A", enrollment_id="enrollment-01",
               reconstruction_id="puf-snn-reconstruction-v1")
record = CredentialVerifierRecord.enroll(
    **binding, verifier_key_id="pilot-verifier-key-1",
    credential4=credential4, key_provider=provider,
)
service = CredentialAdmissionService(CredentialVerifierStore([record]), provider)
result = service.verify(candidate_credential4, **binding)
# result.verified is a comparison outcome only; no session gating exists yet.
```

## Verification Behavior

`CredentialAdmissionService.verify(candidate_credential4, *, device_id, enrollment_id, reconstruction_id)`:

1. Rejects invalid candidate type/length or invalid trusted binding identifiers.
2. Looks up the exact device/enrollment pair; duplicate pairs cannot enter a normally constructed store.
3. Validates the record's schema, algorithm, identifiers, tag shape, and lifecycle flag types.
4. Checks the returned record against the supplied trusted device/enrollment/profile binding, and denies disabled/revoked records.
5. Retrieves exactly the record's key ID and validates the returned 32-byte key.
6. Recomputes the framed HMAC and compares full tags with `hmac.compare_digest`.
7. Returns an immutable `CredentialAdmissionResult` containing only `outcome`; `.verified` and truth-value conversion are true only for `verified`.

It accepts no evaluator label, enrolled plaintext credential, PUF reference, BER, helper data, session material, or caller-selected key ID. It retains no candidate or freshly computed tag in service/result state. Missing records are not synthesized; mismatches do not trigger key search, enrollment, replacement, or retries. Lookup and ordinary provider/cryptographic exceptions become secret-free failure results. Process-control exceptions such as `KeyboardInterrupt` are not swallowed.

## Key Provider

`CredentialVerifierKeyProvider` is a narrow typing protocol with `get_key(verifier_key_id) -> bytes`. It is a trusted internal interface, not a public remote service. A provider returns exactly 32 bytes or raises for unavailable keys. Malformed returns and ordinary provider exceptions both map to `key_unavailable`.

`InMemoryCredentialVerifierKeyProvider` holds one service-level key and exact key ID. `generate(key_id)` calls `secrets.token_bytes(32)` once and validates the result. Failure has no fallback. No credential, simulation seed, PUF response, helper data, HKDF value, or session key is involved in generation.

The explicit constructor accepts an independently provisioned key, supporting trusted imports and the clearly marked deterministic unit fixtures. Independence cannot be inferred from arbitrary supplied key bytes: runtime/evaluation callers should use `generate()` and must not pass a credential-derived key. Unknown key IDs raise a fixed `LookupError("key_unavailable")`; invalid constructor inputs raise a fixed `ValueError("invalid_input")`.

Keys remain in private process memory. There is no persistence or recovery: losing the ephemeral key means the old records cannot verify until that original key is securely restored or fresh trusted enrollment occurs. No automatic re-enrollment is implemented. Custom providers are responsible for redacting their own representations.

## Failure Categories

| `outcome` | Meaning |
| --- | --- |
| `verified` | Full HMAC tags matched |
| `credential_mismatch` | Well-formed tag mismatch; includes wrong candidate, wrong key, or correctly shaped corrupted/relabeled tag |
| `record_missing` | Exact trusted device/enrollment lookup found no record |
| `record_disabled` | Record is disabled or revoked |
| `unsupported_record` | Wrong record type, schema/algorithm, identifier, tag type/length, or lifecycle flag type |
| `key_unavailable` | Unknown key, provider exception, or invalid returned key type/length |
| `binding_mismatch` | Retrieved record does not match the trusted device/enrollment/profile binding |
| `invalid_input` | Candidate or caller-supplied binding violates the contract |
| `internal_error` | Unexpected store or cryptographic operation failure |

A wrong device/enrollment with no entry yields `record_missing`; a returned entry that disagrees with the trusted binding yields `binding_mismatch`. The API does not disclose a special “wrong key” outcome because a valid-length incorrect key is indistinguishable from other tag mismatches.

Trusted enrollment raises fixed `ValueError` messages `invalid_input`, `key_unavailable`, or `internal_error`, suppressing chained provider/crypto exception text. Store construction additionally rejects duplicates with `duplicate_record` and bad record objects with `unsupported_record`. These are provisioning errors, not extra runtime result categories. Future session integration can collapse failures into its generic `credential_verification_failed`; that mapping is not implemented here.

## Secret Handling

Provider, store, service, and record representations are explicitly redacted. Record repr hides all fields, including malformed imported values, and its tag also has `repr=False`. Results contain only a validated fixed outcome. No logging/printing is performed, and exception messages never interpolate credential/key/tag bytes. The key provider necessarily exposes its key to trusted cryptographic code through `get_key`; private attributes and repr redaction are not process isolation.

Explicit trusted provisioning can access `record.tag`. Generic dataclass serialization, such as `asdict(record)`, includes the tag and is not approved for operational logging. Traceback-local inspection, debugger access, deliberate private-attribute access, or serialization of provider internals is not protected by redaction. No secure memory erasure of immutable Python bytes is claimed.

## Tests

There are **48 new unit-test methods**, with additional input matrices implemented as subtests. They cover all requested positive, negative, framing, binding, lifecycle, provider-failure, representation, and API cases. In particular:

- A fixed independent vector checks the exact message bytes and full HMAC output; the vector was calculated using `struct.pack('>H', ...)` and explicit SHA-256 HMAC inner/outer pads, independently of the module, and cross-checked with stdlib HMAC.
- The synthetic vector uses key `bytes(range(32))`, device `Device-A`, enrollment `enrollment-01`, reconstruction `puf-snn-reconstruction-v1`, key ID `synthetic-key-1`, and credential `000001a5`. Expected framed message and tag are literal constants in the test file; expected tag is `a98b73a20b15520ee5c5c7f4c57482268dcd5639d819158a8e3923cf45b038ba`. All of these values are nonsecret test fixtures.
- A wrapped real `hmac.compare_digest` verifies full-tag comparisons on both acceptance and rejection; it does not replace cryptographic comparison with a forced answer.
- Provider-call counts establish one-key lookup and no mismatch retry. Store tests cover duplicates, immutable snapshots and unexpected responses.
- Cross-device tests distinguish wrong distinct credentials/tag substitution from the documented case of two devices enrolled with identical bytes: both independently bound tags accept their own shared credential.
- The standalone test patches session derivation to reject any invocation, demonstrating the primitive itself does not run it. It does **not** prove that the existing session flow has a pre-HKDF gate.

### Commands and execution record

Commands were run from `C:\Users\wwall\PUF-SNN` with Python 3.12.10 on Windows ARM64. `-B` disables Python bytecode writes; `-W default` exposes warnings. Test-runner time below is distinct from tool process wall time (which includes startup/imports).

Initial command:

```powershell
.\.venv\Scripts\python.exe -B -W default -m unittest discover -s tests/auth -p test_credential_verifier.py -v
```

Result: exit 1; one failed-loader entry, 0.000 seconds test-runner time (1.768 seconds process wall time). `ModuleNotFoundError: No module named 'puf_snn'`. No unit test body ran. The local package was not installed into this environment; corrected by setting the source path, without modifying packaging files.

Corrected standalone command:

```powershell
$env:PYTHONPATH = 'src/python'
.\.venv\Scripts\python.exe -B -W default -m unittest discover -s tests/auth -p test_credential_verifier.py -v
```

Result: **48 passed**, 0.019 seconds test-runner time (1.044 seconds process wall time), exit 0, no warnings, failures, or skips.

Broader auth command:

```powershell
$env:PYTHONPATH = 'src/python'
.\.venv\Scripts\python.exe -B -W default -m unittest discover -s tests/auth -p 'test_*.py'
```

Initial broader result: exit 1; **139 test entries**, 0.959 seconds test-runner time (3.334 seconds process wall time), eight errors and zero assertion failures. The count includes import-failure placeholders; it is not the complete auth test population. Errors were three `test_audit` schema tests missing `jsonschema`; `test_classifier_integration` missing `sklearn`; `test_finalization`, `test_layer3_integration`, and `test_session` imports missing `galois`; and `test_protocol_rejection.setUpClass` missing `galois`. No existing session behavior was changed to address them.

The initial broader run also reported four `PyparsingDeprecationWarning` forms through matplotlib: `oneOf`/`one_of`, `parseString`/`parse_string`, `resetCache`/`reset_cache`, and `enablePackrat`/`enable_packrat`, plus matplotlib classic-style messages for `parseString` and `resetCache`.

The declared missing dependencies were requested with:

```powershell
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check --no-cache-dir --only-binary=:all: 'galois==0.4.11' 'jsonschema>=4.23,<5' 'scikit-learn>=1.5,<2'
```

The sandboxed attempt failed after five connection-retry warnings with Windows socket permission error 10013. The misleading final “no matching distribution” message followed blocked network access. The identical command was then retried with approved network access, scoped to this project's virtual environment, and completed successfully. No dependency declaration was changed. Installed packages were `attrs==26.1.0`, `cloudpickle==3.1.2`, `galois==0.4.11`, `joblib==1.6.0`, `jsonschema==4.26.0`, `jsonschema-specifications==2025.9.1`, `llvmlite==0.50.0`, `narwhals==2.26.0`, `numba==0.68.0`, `referencing==0.37.0`, `rpds-py==2026.6.3`, `scikit-learn==1.9.1`, `scipy==1.18.1`, `threadpoolctl==3.7.0`, and `typing_extensions==4.16.0`. Existing versions included NumPy 2.5.3, matplotlib 3.10.6, and pyparsing 3.3.2.

Repeating the broader auth command with dependencies available exited 1 during discovery/import, before a unittest count/runtime summary. LLVM printed `DefIdx 1 exceeds machine model writes`, `incomplete machine model`, and `UNREACHABLE executed ... TargetSchedule.cpp:226!`. The initial process wait lasted 10.007 seconds; a complete wall duration was not measured. This was a native Galois/Numba compiler abort under the host CPU target, not a verifier test assertion failure. The same matplotlib/pyparsing warnings appeared.

Inspection of the installed Numba configuration confirmed its supported `NUMBA_CPU_NAME` override. This isolated probe succeeded (exit 0, process wall time 2.761 seconds, no warnings):

```powershell
$env:NUMBA_CPU_NAME = 'generic'
.\.venv\Scripts\python.exe -B -W default -c "import galois; print('galois import passed', galois.__version__)"
```

It printed `galois import passed 0.4.11`. The override changes the JIT CPU target for the test process; no package source, reconstruction algorithm, or session behavior was edited. JIT was not disabled, and no synthetic stand-in for BCH was used.

### Final regression and integrity results

Final complete auth command:

```powershell
$env:PYTHONPATH = 'src/python'
$env:NUMBA_CPU_NAME = 'generic'
.\.venv\Scripts\python.exe -B -W default -m unittest discover -s tests/auth -p 'test_*.py'
```

Result: **202 tests passed in 19.555 seconds**, exit 0, zero failures, errors, or skips. This comprises all **48 new tests and 154 existing auth tests**, including the previously blocked modules. The four matplotlib/pyparsing deprecation forms and two classic-style messages listed above remain. No existing-auth assertion regression was found. The default host-target LLVM abort remains an environment limitation; successful full-suite reproduction on this machine uses the explicit generic CPU setting above. The standard-library verifier tests themselves require no Numba setting.

`git diff --check` passed. Git reported the existing checkout conversion policy warning that LF in the modified `auth/__init__.py` will become CRLF when Git next touches it; no protected file was normalized. New-file title/section/link/whitespace checks were also performed.

Before/after raw-byte SHA-256 comparison covered **252 existing files**, including **all 243 files under `results/`** (formal reconstruction and saved Tier 1 evidence), the two protected reconstruction sources, the reconstruction runner, all three protected session/sender/receiver sources, the existing audit schema, the frozen Layer 3 manifest, and the design document. Every captured hash stayed identical; no saved result file was added or removed.

| Protected source | Identical before/after SHA-256 |
| --- | --- |
| `src/python/puf_snn/reconstruction/bch.py` | `5bb11f2901a94c552c1b453eea092603d49cd749d476b07541a615487dffe1f8` |
| `src/python/puf_snn/reconstruction/credential.py` | `865ac1b9c26e439c872a7b7376ae393c79b324d389286c51f70be82e6d438193` |

There is no construction discrepancy from the approved Phase 1 design. The original design document was already an untracked file at the start of this phase and was neither created anew nor edited. The primitive is ready for the separately authorized session-integration phase; it does not yet enforce that phase's control-flow security goal.

## Known Limitations

- The credential is a **32-bit pilot credential**, not production-strength entropy. The full 256-bit HMAC tag does not strengthen the underlying credential's entropy.
- Service-key compromise together with records permits exhaustive offline search of the 32-bit credential space. A single service key creates a shared compromise scope.
- Existing Layer 3 transcripts/confirmation traffic still permit offline credential testing. This standalone primitive does not change the protocol or eliminate that risk.
- The existing plaintext `RegistryEntry.credential4` is unchanged. Its compromise directly discloses the reference credential. Tag-only database protection does not apply to theft of the entire pilot process or research artifacts.
- Identical credential bytes cannot reveal their physical device of origin, even with device-bound tags. Device/profile/enrollment binding is exact context binding, not hardware attestation.
- No persistence, active-generation/rollback policy, online rate limiting, remote transport, local authorization handles, audit integration, or session integration is implemented. Those remain later work under the design.
- Exporting the public types modifies `auth/__init__.py`, which is among the files pinned by the frozen Layer 3 baseline. That old hash contract is not silently updated or bypassed; a future baseline transition remains necessary before new-profile Tier 1 execution.
- **No production-security claim and no session integration claim are made.** The construction matches the approved Phase 1 scope. The broader design's enrollment lifecycle, audit, and session-admission responsibilities are deferred, not implemented by a boolean/result object.
