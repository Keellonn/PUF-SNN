# Tier 1 pilot plan v1

Frozen before formal execution on 2026-09-23. Evaluate Layer 3 Authentication
Baseline v1 / wire 2.0 through its existing public APIs. No baseline changes.
The normative protocol and final handoff agree on the selected cases.

The versioned config predeclares 100 trials for each of five primary attacks,
100 independent legitimate controls, and 100 separately reported supporting
cross-session substitutions. This pilot count repeats lifecycle/state handling
enough to expose bookkeeping/order errors at modest software execution cost; it
is not a power calculation or a security-strength estimate. Never change these
counts or seed in response to observed outcomes. Twenty isolated legitimate
session/window warmups precede measured trials, as required by Layer 3.

Seed 20260923 controls public synthetic motion and mutation planning using
SHA256 of explicit ASCII domain/seed/index strings. It does not control session
randomness. Both endpoints retain the frozen OS CSPRNG. Reproduction means the
same plan and attack operations, not identical session IDs, tags or timings.

Every trial owns a fresh verifier, sender(s), enrollment objects and sessions.
Two devices are independently provisioned from separate public synthetic streams.
Explicit correct synthetic candidates enter the normal Sender handshake API;
no reconstruction success rate is measured and no PUF readings are generated.
The provisioning role never passes secrets to the external mutation function.
The mutation function accepts only intercepted envelope bytes, public target
identifiers and the public plan. Shared code, seed and motion family prevent a
claim of independent samples from an attacker or hardware population.

Fixed trial order repeats control, same-session replay, prior-session replay,
cross-device substitution, payload modification, metadata modification, then
supporting cross-session substitution. No retries or adaptive ordering. Each
attack starts with a seq-0 envelope accepted during setup; this setup acceptance
and exact release are retained separately from formal control denominators.
Cross-device/session cases additionally accept a target-device seq-0 window.
For prior-session replay a normal authenticated replacement creates a new ACTIVE
session for the source owner; the old CLOSED/session_replaced tombstone yields
inactive_session with authentication not_checked. This pilot does not measure
expired-session replay; it uses the explicitly permitted replacement variant.

Attack access is observation/injection at the complete-envelope input to
verify_window, after legitimate sealing. No credentials, candidate bytes, keys,
PRKs, PUF/helper contents or secret hashes reach the attacker or evidence files.

| Class | Sole attack operation | Defense / expected reason |
|---|---|---|
| Same-session replay | Resubmit identical complete accepted envelope | Valid tag then strict order: duplicate_sequence |
| Prior-session replay | Resubmit identical old envelope after authenticated replacement | CLOSED lookup: inactive_session before HMAC |
| Cross-device substitution | Replace A device ID with registered, ACTIVE B of equal encoded length; keep A session and tag | HMAC: invalid_tag |
| Payload modification | XOR one selected mantissa bit 0..22 of one finite position component | HMAC: invalid_tag before quality/order |
| Metadata modification | Change only sequence_number from 0 to 1, original tag | HMAC: invalid_tag before order |
| Supporting cross-session | Replace protected session ID with B's known ACTIVE ID and match redundant envelope key_id; retain tag | HMAC: invalid_tag |

Full public envelopes, byte hashes, precise mutation offsets/words, state
snapshots, decisions, audit IDs and release observations are retained. Replay
snapshots use session_status, active_session_ids and tombstones; owner mappings
come from verifier-authenticated establishment audit, not packet identity.
No private secret state is inspected. No lifecycle/timer control runs between
the immediate before/after snapshots. Attempt release with the exact minted
result for both accepts and rejects, observing consumer calls and payload
equality. No inference implementation exists; inference is explicitly false.

Verifier timing is the frozen result's verifier_auth_ns, not an outer harness
timer. Setup, mutation, hashing, schema validation, release and disk writes lie
outside it. Preserve sender/KDF/establishment timings separately. Attack sender
and paired-total timings are null. Report all measurements including slow ones;
p95 is linear interpolation at sorted index 0.95*(n-1).


# First formal Tier 1 authentication-gate pilot

The frozen software authentication prototype rejected **500/500 observed primary
Tier 1 attack trials** while accepting **100/100 legitimate controls**. Separately,
it rejected **100/100 supporting cross-session substitutions**. All expected
reasons matched. No tested rejected attack caused a replay/session-state or
payload-release violation. This is finite software-prototype evidence, not a
universal security result.

## Threat model and injection model

The attacker observes one valid, complete, authenticated envelope and injects
bytes at the verifier input after sender tag creation. It knows public framing,
identifiers and the documented mutation plan. Identity substitutions additionally
know the enabled target device or its ACTIVE session ID. The attacker has no
runtime credential, reconstructed candidate, session key, PRK, helper contents or
PUF reference/response. It never recomputes a tag.

Privileged synthetic enrollment and normal sender/verifier mutual confirmation
remain separate from the mutation function. Every trial independently provisions
two simulated devices from separate public synthetic streams and owns fresh
verifier/session state. Explicit correct synthetic candidates follow the existing
demo convention; this pilot does not measure reconstruction or PUF reliability.
Session nonces and IDs remain OS-generated, without deterministic replacement.

The common knowledge/access boundary above applies to each primary attack and
the supporting substitution. All changes are external to the frozen modules.
Compromised legitimate senders, credential guessing, semantic motion attacks,
network availability and process-memory compromise are outside this experiment.

## Environment and predeclared design

## Exact attack definitions and professor-ready traces

## Primary results

## Reason distribution

## State and payload-release results

## Latency

## Confidence intervals and finite-trial interpretation

## Evidence, reconciliation and validation

## Limitations and defensible conclusion
