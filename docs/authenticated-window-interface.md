# Authenticated Window Interface

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
