# Authenticated Window Interface

> Historical fixed-decimal JSON prototype. Superseded by Wire Protocol 2.0. The byte count, hash and Unity canonical-JSON tests below describe the prototype only; the current binary interface and rejection policy are documented at the end of this file. Will's Layer 3 implementation overview is in docs/puf-layer3-design.md.

## Purpose

This interface connects Keegan's processed Quest motion windows to Will's session-authentication layer. It defines one exact sender message and one deterministic byte representation before Tier 1 attack testing begins.

The message does not implement PUF reconstruction. Will's layer supplies a reconstructed credential, derives a per-session key, computes the HMAC, verifies the HMAC, and maintains verifier-side sequence state.

## Ownership

Keegan owns:

- converting a validated 120-sample Quest window into the protected motion message;
- the processed motion payload and data-quality fields;
- deterministic fixed-decimal encoding of position and quaternion values;
- tests that prove every protected field changes the canonical HMAC input;
- passing only verifier-accepted payloads to the classifier later.

Will owns:

- PUF credential reconstruction;
- per-session key derivation and public key identifiers;
- HMAC-SHA-256 tag creation and constant-time verification;
- active-session, device, freshness, duplicate, and sequence state;
- the five Tier 1 attack mutations and verifier result measurements.

Both researchers must approve this interface before integration results are reported.

## Final envelope

The transmitted JSON object has two top-level fields:

- `protected`: every sender field covered by HMAC;
- `authentication`: the algorithm name, public session-key identifier, and tag.

The HMAC input is the canonical UTF-8 byte serialization of the `protected` object only. The tag is never included in its own HMAC input.

Verifier decisions and audit results do not belong in this sender message. The verifier records them separately using `experiment-record.schema.json` so a sender cannot claim that its own message was accepted.

## Protected metadata

The protected object includes:

- protocol version;
- authenticated-message schema version;
- motion-payload schema version;
- pseudonymous device ID;
- session ID;
- window ID;
- monotonic sequence number;
- capture start and end times;
- payload encoding identifier;
- protected data-quality summary;
- the complete processed motion payload.

Ground-truth motion labels, dataset splits, source-trial IDs, model predictions, and audit decisions are experiment metadata. They are not transmitted as trusted sensor-message fields.

## Canonical serialization rules

Both the sender and verifier must follow the same rules:

1. Build the complete `protected` object defined by `authenticated-window.schema.json`.
2. Convert each position and quaternion component to a finite base-10 string with exactly eight digits after the decimal point.
3. Use round-half-even when a value has more than eight decimal places.
4. Encode negative zero as `0.00000000`.
5. Keep timestamps, sequence numbers, sample indexes, and quality counts as JSON integers.
6. Keep tracking values as JSON booleans.
7. Sort every JSON object key lexicographically.
8. Use a comma between values and a colon between each key and value, with no added whitespace.
9. Encode strings and the final JSON document as UTF-8 without a byte-order mark.
10. Reject NaN, positive infinity, and negative infinity.

The Python reference implementation uses:

```python
json.dumps(
    protected_message,
    ensure_ascii=False,
    allow_nan=False,
    separators=(",", ":"),
    sort_keys=True,
).encode("utf-8")
```

The Unity/C# implementation must reproduce these bytes exactly. A shared golden message, canonical-byte SHA-256 value, and HMAC tag should be added after Will confirms the session-key test vector.

## Data-quality handling

The existing processor accepts exactly 120 samples and requires at least 114 tracking-valid samples. The message includes:

- sample count;
- tracking-valid count;
- tracking-valid fraction in integer parts per million;
- a `pass` status.

Using integer parts per million avoids a cross-language floating-point formatting difference. A rejected motion window never enters the authentication message builder.

The verifier should recompute the quality summary from the protected samples and reject a mismatch as `malformed_message` or `data_quality_failure` before inference.

## Authentication and sequence order

The authentication object specifies `HMAC-SHA-256`, a public `key_id`, and a lowercase 64-character hexadecimal tag. The key ID must not reveal the session key, reconstructed credential, raw PUF response, or helper secret.

The verifier should process a message in this order:

1. Parse and validate the strict envelope schema.
2. Confirm that the device, session, and key ID are known and active.
3. Canonicalize the protected object.
4. Verify the HMAC with a constant-time comparison.
5. Recompute and verify the data-quality summary.
6. Apply duplicate, stale, and expected-sequence checks using verifier-owned state.
7. Record the decision and latency.
8. Send the protected motion payload to inference only after acceptance.

The verifier must not update its accepted-sequence state for a rejected message.

## Required interface tests

The first tests must show that:

- identical logical protected messages produce identical bytes;
- dictionary insertion order does not change the bytes;
- negative zero is normalized;
- nonfinite values are rejected;
- exactly 114 tracking-valid samples pass and 113 fail;
- modifying the protocol version invalidates the original tag;
- modifying device, session, window, sequence, or capture times invalidates the original tag;
- modifying data-quality fields invalidates the original tag;
- modifying one position, orientation, or tracking value invalidates the original tag;
- malformed or unexpected fields fail the strict schema;
- verifier-generated audit fields are not accepted from the sender.

## Tier 1 integration order

After both researchers approve the schema:

1. Will supplies one fixed test session key and key ID that contain no real secret material.
2. Python and Unity generate the same protected message and canonical bytes.
3. The team records a golden canonical-byte SHA-256 value and expected HMAC tag.
4. Will connects the derived session key to the same HMAC interface.
5. The team implements exact replay, prior-session replay, cross-device substitution, post-tag payload modification, and post-tag metadata modification.
6. Every attack record includes the original message ID, precise mutation, expected reason, observed reason, trial count, rejection rate, and authentication latency.

The SNN baseline remains deferred until this Tier 1 path is stable and reproducible.

## Current Wire Protocol 2.0 interface

This final shared boundary replaces the historical fixed-decimal JSON design above. The SNN baseline and authenticated classifier gate are now implemented; the historical deferral statement above no longer describes project status.

### Canonical window byte layout

The authenticated object is the exact binary byte string A, not its outer JSON/base64 text. All integers are unsigned big-endian. Versions contain two u16 values (major, minor). Identifiers are restricted ASCII, each prefixed by a u16 byte length. No implicit padding, field reordering, trailing bytes or alternate binary layout is accepted.

| Order | Field | Width / representation |
|---|---|---|
| 1 | Magic | 4 bytes: P3AW |
| 2 | Protocol version | u16 major=2, u16 minor=0 |
| 3 | Authenticated-message version | u16 major=2, u16 minor=0 |
| 4 | Motion payload version | u16 major=1, u16 minor=0 |
| 5 | Fixed encoding/authentication/tag-length selectors | 3 bytes: 01 01 20 |
| 6 | Device identifier | u16 length + ASCII |
| 7 | Session identifier | 16 bytes |
| 8 | Sequence number | u64 |
| 9 | Window identifier | u16 length + ASCII |
| 10 | Capture start and end | two u64 nanosecond timestamps, each below 2^63 |
| 11 | Fixed frame selector | byte 01 |
| 12 | Sample count | u16=120 |
| 13 | Tracking-valid count | u16 |
| 14 | Tracking-valid fraction | u32 parts per million, round-half-even |
| 15 | Payload length | u32=4683 |
| 16 | Fixed payload header | bytes 01 00 3c |
| 17 | Samples, ordered 0..119 | 120 records, 39 bytes each |

Each sample contains u16 sample index, u64 capture time, three position and four xyzw-quaternion binary32 values, then one tracking byte (0/1). Position is in meters in Unity device-origin coordinates. Float bytes are finite IEEE-754 binary32 big-endian; sender conversion rounds once to nearest/even and canonicalizes negative zero. The parser rejects negative-zero/nonfinite encodings. Quaternion and tracking quality checks run before accepted release.

HMAC-SHA-256 covers every byte of A. The wrapper identifies the binary encoding, carries base64(A), and carries the algorithm, public session key_id and lowercase tag hex separately. Labels, source-trial/split metadata, predictions and audit decisions are excluded. Sender binds its provisioned device, active cryptographic session and next sequence rather than trusting dataset identity fields.

Outer JSON object-key ordering is not binary field ordering. Reordering only the transport wrapper keys preserves A and is allowed; changing the canonical binary field order or value without a new valid tag is rejected. Negative cross-language tests distinguish these cases rather than demanding a cosmetic JSON order.

### Placement of preprocessing

A contains the validated/resampled 120-sample sensor window, before classifier-relative preprocessing and normalization. It does not authenticate the earlier irregular raw-pose queue, nor a normalized classifier tensor. The Quest processor performs linear-position/SLERP resampling before sender serialization. The synthetic generator directly produces a fixed grid. Following verification, the immutable accepted window is widened from binary32 and converted to first-pose-relative features; SNN normalization uses training-only saved statistics.

### Sequence and rejection policy

Only the exact next sequence is accepted, starting at zero. An accepted decision commits verifier audit/state before release; the classifier wrapper consumes that event before preprocessing so an exception cannot permit retry. No automatic gap skipping or bounded reordering is implemented.

| Condition | Current behavior |
|---|---|
| Duplicate most recently accepted sequence | duplicate_sequence; no new classifier call |
| Older accepted sequence | stale_sequence; no sequence advance |
| Future sequence | future_sequence_gap; log missing range, do not advance |
| Missing sequence | infer only when a later packet arrives; no packet exists to reject; retry expected packet or establish a new authenticated session |
| Malformed representation / binary length | controlled parse/schema rejection; no release |
| Bad tag, including high-sequence injection | invalid_tag; no advance |
| Unknown/disabled device | unknown_device; no release |
| Unknown or inactive session | unknown_session / inactive_session; no release |
| Failed mutual confirmation | no active session; key_confirmation_failed on the failed handshake |
| Expired session | expired_session; no release |
| Invalid quaternion/tracking/timestamp quality with valid tag | data_quality_failure; no advance |

The first failing check determines the reason; not all fields are authenticated on an early rejection. Audit identity fields from an unauthenticated packet are observations, not proof of origin. Session replacement/expiry may legitimately change lifecycle state; a parse/bad-tag rejection must not poison an active session's next sequence.

The current implementation bounds session resources but does not implement a per-message invalid-input rate limiter. Rejection is not a demonstrated denial-of-service defense.

### Audit ownership and retention

Verifier-generated fields include event ID, decision/reason, authentication/order result, expected/accepted sequence, missing range, lifecycle state and latency. These are never sender-authenticated verdicts. An authenticated-byte hash is recorded only after tag verification. Current audit rows contain metadata, not raw rejected motion payloads or credentials/session keys. The caller can still hold transient packet bytes; this is not an approved human-data retention policy. Synthetic fixtures are explicitly test-only. Human capture and retention remain disabled until approval.

### Evidence and unresolved reliability work

The initial canonical-JSON Unity evidence does not validate final binary parity. Run the final binary writer EditMode tests and supplemental .NET positive/negative checks separately and report their actual results. The negative C# export is tested by the Python verifier and records no classifier calls, unchanged sequence and subsequent valid-window acceptance. These deterministic cases are not a formal attack-rate estimate.

Current mutual confirmation prevents a wrong candidate from activating a session, but the independent enrollment verification requested before HKDF is not yet established here. Will owns that Layer-2 correction, miscorrection/noise evaluation and formal Tier-1 attack results. The 32-bit publicly reproducible pilot credential does not provide production key strength.

A known-correct-candidate pipeline benchmark measures recurring-window processing separately from reconstruction availability. Canonical serialization, HMAC primitives, combined verifier checks and real in-memory audit work are reported with explicit nested boundaries; they are not disjoint stages to sum. Durable audit cost and independent credential-verification/reconstruction timing remain explicit outstanding requirements.
