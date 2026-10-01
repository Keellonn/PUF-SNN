# Layer 3 Authentication

**Owner:** Will Wallace
**Version:** 0.2  
**Last updated:** September 30, 2026

# How to Run

## Prerequisites
The Layer 3 demonstration uses synthetic enrollment material and motion windows, so it does not require a new Layer 2 simulation to be executed first.
The current authentication-v2 path provisions the synthetic credential with the independent credential verifier before session establishment.

## Running the Simulator
To run the Layer 3 authentication demonstration using the current default configuration, run:
`.\run_layer3.ps1`
The current credential-admission configuration is:
`configs/authentication_v2.json`
The historical authentication-v1 configuration and its saved Week 4 evidence remain preserved for reproducibility and should not be relabeled as v2 results.

## Results
Historical Layer 3 v1 demonstration and Tier 1 evidence remain under:
`\results\week-4\will\authentication`
The Week 5 formal credential-verifier evaluation is stored separately under:
`results/week-5/will/credential-verifier/credential-verifier-v1-formal-001`
Formal credential-verifier results are documented in:
`docs/credential-verifier-formal-results-week5.md`
The Layer 3 results and tests measure,
- Credential admission
- Session establishment
- Session-key confirmation
- Authentication of protected motion windows
- Accepted sequence numbers
- Sender and verifier audit behavior
- Session establishment latency
- Sender and verifier key-derivation behavior
- Window preparation and HMAC latency
- Verifier authentication latency
- Configuration and source provenance

# Layer 3 Overview
## Purpose
Layer 3 takes a credential candidate produced by Layer 2, independently verifies that candidate against trusted enrollment information, and uses an admitted credential to establish an authenticated session.
Once the session is established, Layer 3 protects each motion window before it is released to the inference pipeline.
Layer 3 includes,
- Independent pre-HKDF credential verification
- Device and enrollment binding
- Device and session binding
- Credential possession confirmation
- Payload integrity
- Protected-metadata integrity
- Freshness
- Sequence ordering
- Replay rejection
- Session lifecycle enforcement

## Session Establishment
Layer 3 begins with a `ReconstructionResult` produced by Layer 2.
A valid-format reconstructed credential is treated as a credential candidate. Valid BCH decoding and valid padding do not prove that the candidate matches the trusted enrollment.
The current authentication-v2 session establishment process follows,
- The sender receives the Layer 2 reconstruction result
- Reconstruction-result format and coherence checks are performed
- A valid-format candidate is checked by the independent credential verifier
- The verifier checks the candidate against the trusted device, enrollment, reconstruction-profile, and verifier-key context
- If credential verification fails, the attempt stops before session-request creation
- If credential verification succeeds, the trusted local admission service creates a single-use admission authorization
- The sender creates the session request only after successful credential admission
- The receiver validates and consumes the corresponding local authorization before performing its own session-key derivation
- The verifier returns fresh session information and a server nonce
- The sender derives a session key using the same credential candidate that passed independent verification
- The verifier independently derives the expected session key using its enrolled credential
- The sender creates a client key-confirmation proof
- The verifier checks the client proof
- The verifier creates a server key-confirmation proof
- The sender verifies the server proof
- The session becomes active only after successful credential admission and mutual possession of matching credential-derived key material

For a rejected credential candidate,
- No P3RQ is emitted
- No receiver pending session is created
- Sender HKDF is not executed
- Receiver HKDF is not executed
- No session confirmation is performed
- No new session becomes active

## Independent Credential Admission
Credential admission uses a separate HMAC-SHA-256 verifier created during trusted enrollment.
The verifier record binds the candidate credential to,
- Device identity
- Enrollment identity
- Reconstruction-profile identity
- Verifier-key identity

The verifier key is an independent 32-byte secret and is not derived from the PUF credential, helper data, HKDF, or session keys.
A successful credential check produces an opaque local admission authorization. This authorization is not transmitted in Wire 2 and cannot be replaced by a caller-provided boolean such as `verified=true`.
The authorization is tied to the exact admission attempt and is rejected if it is forged, replayed, stale, swapped between requests, or used with the wrong device or enrollment.
Credential admission grants permission to attempt the Layer 3 handshake. It does not itself establish an active session or release sensor data.

## Session Key Derivation
The current implementation derives the Layer 3 session key with HKDF-SHA-256 only after successful independent credential admission.
The session key is derived from,
- The reconstructed credential
- Fresh session randomness
- The session transcript

The verifier does not accept a sender-supplied session key. It independently derives the expected key using the credential provisioned for that device.
The current 32-bit credential is used only as a pilot credential to validate the mechanism. It is not intended to provide production-grade cryptographic strength.

## Wire Protocol 2.0
Layer 3 uses Wire Protocol 2.0 for authenticated motion windows.
Each motion window is converted into a deterministic fixed-width binary representation before authentication.

Protected information is as follows,
- Protocol information
- Device identifier
- Session identifier
- Sequence number
- Window identifier
- Capture start and end times
- Tracking-quality information
- Sample indexes
- Sample timestamps
- Position values
- Quaternion orientation values
- Tracking-valid flags

The serialized binary window is the data protected by the HMAC.

## Window Authentication
For each window, the sender,
- Assigns the current device identifier.
- Assigns the active session identifier.
- Assigns the next sequence number.
- Serializes the window into the Wire-2 binary representation.
- Computes HMAC-SHA-256 over the authenticated bytes.
- Creates the transport envelope containing the authenticated bytes and tag.

Afterwards the verifier,
- Parses the message.
- Looks up the device.
- Looks up and validates the session.
- Verifies the HMAC.
- Verifies device and session binding.
- Applies tracking-quality checks.
- Applies sequence and replay checks.
- Commits the final decision and audit information.

## Sequence and Replay Protection
The current implementation uses strict consecutive sequence numbers.
The first accepted window uses sequence number 0.
The later windows follow,
- The expected next sequence number is accepted
- A repeated sequence number is treated as a duplicate
- A lower sequence number is treated as stale
- A higher-than-expected sequence number creates a sequence gap
- Windows from inactive or expired sessions are rejected

HMAC protects the sequence number and other protected metadata from modification.
Replay protection itself comes from verifier-side session and sequence tracking.

## Accepted Payload Release
Inference is only allowed to receive a window after successful verification.
Verifier.release_accepted() releases the immutable window that was actually authenticated.
This prevents one window from being authenticated while a different window is passed into inference.

## Latency Measurements
The Layer 3 implementation is able to measure,
- Credential-verification latency
- Session-establishment latency
- Sender preparation latency
- HMAC latency
- Verifier authentication latency
- Audit I/O latency

The Week 5 formal credential-verifier experiment measured the independent credential-verification stage separately.
A current authentication-v2 acquisition/reconstruction/session/window/inference benchmark has not yet been completed, so the existing Layer 3 and credential-verifier timing measurements should not be presented as a newly measured full end-to-end v2 latency.

## Current Limitations
- The current implementation is a software research prototype
- Timing measurements are workstation/Python measurements rather than Quest, FPGA, or embedded-device measurements
- The standard Layer 3 demonstration uses synthetic enrollment material rather than a live physical PUF reconstruction
- The 32-bit pilot credential is intended to validate the mechanism and is not production-grade cryptographic secret material
- Independent credential verification prevents wrong reconstructed candidates from entering HKDF, but it does not eliminate the underlying low-entropy limitation of the 32-bit pilot credential
- The credential-admission service assumes trusted co-located software execution and is not remote attestation
- The design provides authentication and integrity but does not provide payload confidentiality
- Historical Tier 1 attack evidence evaluates the frozen v1 authentication baseline; a new formal Tier 1 population has not yet been executed for authentication v2
- A current full acquisition-to-reconstruction-to-authentication-to-inference v2 latency benchmark has not yet been completed

## Important Takeaways
- Layer 3 independently verifies a valid-format reconstructed credential before allowing it to reach HKDF
- Successful credential admission is required before either endpoint performs session-key derivation
- The same credential candidate that passed verification is used by the sender during session-key derivation
- Mutual key confirmation remains required after credential admission
- Motion windows are protected for integrity, device/session binding, freshness, and ordering before inference
- Layer 2 reconstructs a credential candidate; it does not independently authenticate that candidate
- A valid-format but incorrect Layer 2 credential is now rejected before P3RQ creation and before sender or receiver HKDF
- Wire Protocol 2.0 and the per-window HMAC construction were not changed by the credential-verifier integration
- Historical Tier 1 results remain associated with the frozen authentication-v1 baseline