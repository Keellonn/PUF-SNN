# Layer 3 Authentication

**Owner:** Will Wallace  
**Version:** 0.1  
**Last updated:** September 23, 2026

# How to run as of Week 4

## Prerequisites
The current Layer 3 runner uses a fixed synthetic credential and motion window thus, it does not require a previous Layer 2 simulation.

## Running the Simulator
To run the Layer 3 authentication simulation using the default configuration, run,
.\run_layer3.ps1

To run the simulation with a specified authentication configuration, use:
.\run_layer3.ps1 -Config "configs\authentication_v1.json"

## Results
The Layer 3 results are stored in the directory,
\results\week-4\will\authentication

The results record,
- Session establishment
- Authentication of three consecutive windows
- Accepted sequence numbers 0, 1, and 2
- Sender and verifier audit records
- Session establishment latency
- Sender and verifier key derivation latency
- Window preparation and HMAC latency
- Verifier authentication latency
- Audit writing latency
- Configuration and source hashes
- Run metadata and artifact manifest

# Layer 3 Overview
## Purpose
Layer 3 takes a credential candidate produced by Layer 2 and uses it to establish an authenticated session.
Once the session is established, Layer 3 protects each motion window before it is released to the inference pipeline.

Layer 3 includes,
- Device and session binding
- Credential possession confirmation
- Payload integrity
- Protected-metadata integrity
- Freshness
- Sequence ordering
- Replay rejection
- Session lifecycle enforcement

## Session Establishment
Layer 3 begins with a ReconstructionResult produced by Layer 2.
A valid-format reconstructed credential allows a session attempt to begin, but it does not prove that the reconstructed credential is correct.

The session establishment process follows,
- The sender begins a session attempt using the reconstructed credential
- The sender generates a fresh client nonce
- The verifier returns fresh session information and a server nonce
- The sender derives a session key from the reconstructed credential
- The verifier independently derives the expected session key using its enrolled credential
- The sender creates a client key-confirmation proof
- The verifier checks the client proof
- The verifier creates a server key-confirmation proof
- The sender verifies the server proof
- The session becomes active only if both sides demonstrate possession of matching credential-derived key material

## Session Key Derivation
The current implementation derives the Layer 3 session key with HKDF-SHA-256.

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
The Layer 3 runner is able to measure,
- Session establishment latency
- Sender preparation latency
- HMAC latency
- Verifier authentication latency
- Total Layer 3 latency
- Audit I/O latency

## Current Limitations
- The current implementation is a software prototype
- Timing measurements are workstation/Python measurements rather than Quest, FPGA, or embedded timing measurements
- The Layer 3 demonstration uses a fixed synthetic valid credential instead of a noisy Layer 2 reconstruction
- The three measured windows are a functional demonstration rather than a large-sample security experiment
- The 32-bit pilot credential is not intended to provide production-grade cryptographic strength
- The current design provides authentication and integrity but does not provide payload confidentiality
- Formal attack evaluation is performed separately using the Tier 1 experiment

## Important Takeaways
- Layer 3 establishes an authenticated session using credential-derived key material
- Motion windows are protected for integrity, device/session binding, freshness, and ordering before inference
- Layer 3 provides the credential confirmation that Layer 2 cannot provide by itself
- A valid-format but incorrect Layer 2 credential should fail session key confirmation
- The current Layer 3 runner demonstrates the normal successful authentication path
- Formal attack rejection and larger-sample authentication analysis are handled by the Tier 1 experiment