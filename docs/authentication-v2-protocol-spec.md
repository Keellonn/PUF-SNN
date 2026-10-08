# Authentication-v2 Protocol and Trust Specification

**Owner:** Will Wallace  
**Version** 1.0  
**Status:** Implemented Prototype
**Original Implementation Baseline:** 78f499a92f633a4793c776a070058e3a6a9a0b61 

This document describes the Authentication-v2 protocol implemented within our PUF + SNN research project. It explains how simulated PUF-based credential reconstruction, independent credential verification, authenticated session establishment, and protected sensor-window processing are combined to establish a trusted software pathway into SNN inference.
The specification describes the implemented research prototype, not a proposed production system. The main sections explain the architecture and security decisions, while the appendices preserve the exact cryptographic formulas, protocol representations, verification order, and failure behavior.
Where **MUST** and **MUST NOT** appear, they describe requirements of the implemented protocol under its stated trust assumptions.

## Introduction

### Research Motivation

Extended Reality (XR) systems rely on continuous streams of motion and tracking data to interpret user behavior. As these systems increasingly incorporate machine learning, the integrity of incoming sensor data becomes important. If motion information can be modified, replayed, or incorrectly associated with a device, the inference system may process data that it should not trust.
Our research investigates how Physical Unclonable Function (PUF) concepts can be combined with Spiking Neural Networks (SNNs) to improve the trustworthiness of XR sensing pipelines.
Authentication-v2 addresses the authentication and data-integrity portion of this problem. It establishes a controlled process for reconstructing device-associated credentials, verifying those credentials, establishing authenticated sessions, and validating motion windows before they reach inference.
A major consideration in this design is the distinction between reconstruction reliability and authentication security.
BCH error correction allows the system to recover a credential from a noisy PUF response. However, a successful decoding operation does not necessarily mean that the correct credential was reconstructed. Under sufficiently severe noise, the decoder may produce an incorrect credential that still satisfies the required format.
Authentication-v2 addresses this limitation by introducing an independent credential-verification stage before session-key derivation.
Once a credential is verified, the protocol uses session confirmation, HMAC message authentication, and strict sequence-number enforcement to protect subsequent motion-window processing.

The overall goal is to demonstrate a reproducible software architecture in which only successfully authenticated sensor windows can be released to the SNN inference pipeline.

### System Overview

Authentication-v2 connects three major research layers,
1. **PUF response generation:** A simulated ring-oscillator PUF generates a noisy, device-associated response.
2. **Credential reconstruction:** BCH error correction and enrollment helper data are used to recover a credential candidate.
3. **Authentication and inference protection:** Independent verification, session establishment, and protected sensor windows determine whether motion data may reach the inference pipeline.

The implemented processing sequence is,
- Simulated RO-PUF
- Noisy PUF Response
- BCH Credential Reconstruction
- Independent Credential Verification
- Local Credential Admission
- Authenticated Session Establishment
- HKDF Session-Key Derivation
- Mutual Session Confirmation
- HMAC-Protected Motion Window
- Session / Integrity / Sequence Verification
- Authenticated Window Release
- Preprocessing
- SNN Motion Classification
- Anomaly Detection

Each stage establishes a different property.
Credential reconstruction addresses the reliability of recovering credential material. Independent verification checks whether the recovered candidate matches trusted enrollment information. Session establishment creates a shared cryptographic context, while motion-window verification protects the integrity and ordering of transmitted sensor data.
The final authentication boundary is implemented through `V2InferencePipeline`, the audited sender and verifier, and `ExactlyOnceClassifierRelease`.
The current inference pipeline uses the binary Wire2 protocol. Older fixed-decimal JSON authentication modules remain in the repository for historical compatibility but are not part of the supported Authentication-v2 inference path.

### Scope and Security Goals

Authentication-v2 is implemented as a trusted, co-located Python research prototype.
The PUF is simulated rather than implemented in physical hardware. The current system also uses a 32-bit experimental credential, which is sufficient for studying protocol behavior but does not provide production-grade credential entropy.
Within these limitations, the architecture is designed to enforce the following security properties:

- **Credential verification:** Incorrect reconstructed credentials must be rejected before session-key derivation.
- **Device and session binding:** Authentication must depend on trusted enrollment and active-session information rather than unverified packet identifiers.
- **Message integrity:** Unauthorized modifications to authenticated motion-window bytes must invalidate the associated HMAC.
- **Replay protection:** Previously accepted sequence numbers must not be accepted again within the same session.
- **Ordering enforcement:** Packets must arrive with the exact expected sequence number.
- **Session freshness:** Session establishment and message acceptance are subject to defined time and lifecycle limits.
- **Inference gating:** Rejected packets must not invoke the supported preprocessing, motion-inference, or anomaly-inference callbacks.
- **Auditability:** Authentication decisions and relevant state transitions are recorded for inspection and experimental evaluation.

These are properties of the supported software implementation under its trust assumptions.
The protocol does not provide encryption, physical hardware attestation, secure key storage, forward secrecy, production-strength credential entropy, automatic network recovery, or general denial-of-service prevention.
Authentication also does not establish that motion data are behaviorally normal. An authenticated device may submit motion that is unusual or semantically manipulated. This is evaluated separately by the anomaly-detection portion of the research.

## System Architecture

### Components and Responsibilities

Authentication-v2 consists of several cooperating components responsible for credential recovery, session management, message authentication, and inference protection.
| Component | Responsibility |
|---|---|
| Simulated RO-PUF | Generates device-associated response bits from simulated oscillator characteristics |
| BCH reconstruction | Recovers a candidate credential using the noisy response and helper data |
| Credential verifier | Independently verifies candidate credentials against enrolled HMAC records |
| Admission service | Issues local authorization for a successfully verified candidate |
| Sender | Establishes sessions, seals motion windows, and maintains outgoing sequence state |
| Verifier | Establishes sessions, authenticates windows, and maintains receiver-side session state |
| Audit system | Records authentication decisions, errors, and relevant protocol events |
| Accepted-window release | Restricts inference access to payloads accepted by the verifier |
| Inference pipeline | Preprocesses accepted data and invokes the frozen motion and anomaly models |

These components are connected through local Python interfaces.
The sender is responsible for recovering and presenting credential material, completing session confirmation, and producing authenticated sensor windows.
The verifier maintains trusted enrollment and session records. It independently derives session keys and determines whether each incoming motion window satisfies the protocol's acceptance requirements.
The inference pipeline operates only on motion windows released through the authenticated receiver.
This separation makes it possible to evaluate credential reliability, authentication security, and model behavior as related but distinct research questions.

### Trust Boundaries

The main security boundary separates incoming protocol data from the trusted authentication state and downstream inference pipeline.
Information contained in a received packet is initially treated as untrusted.
For example, a device identifier or session identifier is not accepted simply because it appears in the message. The verifier must determine whether the identifier corresponds to a valid provisioned device, an appropriate session, and an authenticated message.
The supported implementation assumes the following components are trusted,
- Enrollment and provisioning logic
- Local sender and verifier implementations
- Credential-verification records and key provider
- Session registry and local admission service
- Cryptographic and serialization functions
- Operating-system randomness and local clocks
- Audit and accepted-window release mechanisms
- Pre-authentication data construction and downstream model callbacks

These assumptions are important because the current implementation uses co-located Python objects.
The admission service issues an opaque authorization object that cannot normally be constructed or serialized by an external caller. However, this does not provide security against malicious code already executing within the trusted process.
The system does not establish a secure process boundary, hardware enclave, remote attestation mechanism, or production network architecture.
A deployment involving separate devices and servers would therefore require additional work to define authenticated provisioning, communication transport, key custody, and process isolation.

### Credential and Key Storage

The system separates several types of credential and cryptographic material.
| Material | Current Storage or Owner | Purpose |
|---|---|---|
| Reference PUF response | Research enrollment environment | Generates helper data and supports evaluator measurements |
| PUF helper data | Sender enrollment information | Supports noisy credential reconstruction |
| 32-bit credential | Enrollment materials and receiver registry | Reconstruction target and HKDF input |
| Credential-verifier record | Verifier record store | Stores the enrolled HMAC verification tag |
| Independent verifier key | Credential-verifier key provider | Authenticates credential candidates |
| Admission authorization | Local admission service | Binds successful verification to one handshake attempt |
| Session key | Sender and verifier session state | Protects confirmation messages and motion windows |
| Session counters and lifecycle state | Verifier | Enforces ordering, expiration, and replay protection |

An important distinction is that the credential-verifier record stores an HMAC tag rather than the plaintext credential.
However, the complete receiver is not a tag-only verifier.
The receiver's `RegistryEntry` retains the raw four-byte enrolled credential because the receiver independently derives its session key during handshake establishment.
The verifier record, key provider, admission service, and session registry therefore have separate security responsibilities.
Current research runners retain provisioning materials in memory. No production database, protected keystore, hardware security module, persistent enrollment service, or secure memory-erasure procedure is implemented.

## PUF Credential Reconstruction and Authentication

### Enrollment and Helper Data

Enrollment establishes the relationship between a simulated device and the credential that will later be reconstructed.
The current PUF model uses 128 simulated ring oscillators organized into 64 adjacent, disjoint oscillator pairs.
Each pair generates one response bit through a frequency comparison. The resulting 64-bit reference response is used during enrollment.
The reconstruction implementation selects the first 63 response bits because the BCH codeword contains 63 bits.
The enrollment process follows these steps,
1. Generate the simulated device and its reference PUF response
2. Generate a four-byte experimental credential
3. Append four zero-padding bits to form a 36-bit BCH message
4. Encode the message using BCH(63,36,t=5)
5. XOR the 63-bit codeword with the selected reference PUF response to produce helper data
6. Generate an independent credential-verifier key
7. Create an enrolled HMAC verification record
8. Provision the sender and verifier with their required enrollment information

The helper data are intentionally public and are not treated as a secret credential.
The current helper-data construction follows the code-offset approach:

```text
helper = reference_response XOR BCH_codeword
```

During reconstruction, the system combines the helper data with a newly measured response to recover an estimate of the original BCH codeword.
The enrollment identifier is also retained so that the reconstruction and authentication components can associate the candidate with the appropriate provisioned generation.
The research implementation does not establish a secure physical enrollment process or persistent provisioning infrastructure.

### BCH Credential Reconstruction

Authentication-v2 uses the original reconstruction construction:
**BCH(63,36,t=5)**
The relevant parameters are,
| Parameter | Value |
|---|---|
| Codeword length | 63 bits |
| Message length | 36 bits |
| Correctable bit errors | 5 |
| Designed minimum distance | 11 |
| Credential length | 32 bits |
| Fixed padding | 4 zero bits |
| Selected response bits | Indices 0–62 |
| Readings per attempt | 1 |
| Decoder attempts | 1 |

At authentication time, the simulated device generates one new PUF response.
The selected response bits are combined with the stored helper data to produce the received BCH codeword estimate.
The BCH decoder attempts to correct the noisy codeword and recover the original message.
Three runtime outcomes are possible,
| Outcome | Meaning |
|---|---|
| `candidate_valid_format` | A decoded credential candidate satisfies the required message format |
| `decoder_failure` | The decoder cannot recover an acceptable codeword |
| `invalid_format_or_padding` | Decoding produces a message with invalid padding |

The four padding bits allow the implementation to reject some invalid decoded messages.
However, padding validation does not guarantee credential correctness.
If sufficiently many response bits change, BCH decoding may produce an incorrect credential that still contains valid padding.
This is why the reconstruction result must be independently verified before it can authorize session establishment.
The current Authentication-v2 implementation does not perform reconstruction retries, temporal majority voting, stable-bit selection, or adaptive error-correction changes.
Those techniques are evaluated separately in the Reconstruction Alternatives Experiment and have not been integrated into this version of the authentication protocol.

### Independent Credential Verification

Independent credential verification ensures that a valid-format reconstruction candidate is checked against trusted enrollment material before session-key derivation.
The system uses HMAC-SHA-256 with a separately generated 32-byte verifier key.
During enrollment, a keyed tag is calculated using the credential and its associated identifiers.
The enrolled tag binds,
- Device identity
- Enrollment identity
- Reconstruction identity
- Verifier-key identity
- The enrolled four-byte credential

During authentication, the credential-verification service retrieves the relevant record and independently computes the expected HMAC using the reconstructed candidate.
The calculated tag is compared with the stored tag using `hmac.compare_digest`.
A matching result indicates that the candidate matches the enrolled record under the trusted key and binding.
Verification may return outcomes such as:

- `verified`
- `credential_mismatch`
- `record_missing`
- `record_disabled`
- `unsupported_record`
- `key_unavailable`
- `binding_mismatch`
- `invalid_input`
- `internal_error`

Only successful verification permits the system to proceed toward credential admission.
A rejected credential candidate must not generate a new handshake request or cause either endpoint to derive session keys.
In the supported implementation, failed initial credential verification also prevents the creation of new receiver pending or active session state.
This mechanism protects the authentication pathway from incorrectly reconstructed candidates.
It does not improve the reconstruction success rate. An incorrect candidate that is successfully rejected still represents a legitimate authentication availability failure.
The exact HMAC construction is documented in Appendix B.

### Local Admission Authorization

After credential verification succeeds, the system issues a `LocalAdmissionAuthorization` object.
This authorization binds the verified credential to a particular local handshake attempt.
Its purpose is to prevent a caller from verifying one credential and then substituting a different credential, request, or handshake transcript during session establishment.
The authorization lifecycle consists of five operations,
1. **Authorize:** Verify the candidate and register a bounded-lifetime authorization.
2. **Bind request:** Associate the authorization with one exact handshake request.
3. **Consume:** Allow the receiver to consume the authorization once, after validating its context.
4. **Bind challenge:** Associate the authorization with the exact receiver-generated transcript.
5. **Claim candidate:** Allow the sender to retrieve the same verified credential for key derivation.

The final claim removes the authorization regardless of whether it succeeds.
The service also rejects expired, revoked, foreign, fabricated, or previously consumed authorizations.
The authorization object is never included in the transmitted protocol bytes.
This mechanism operates within the trusted Python application and is not a general remote authorization token.

## Authenticated Session Establishment

### Handshake Overview

Once a credential has been independently verified and admitted, the sender and verifier establish an authenticated session.
The handshake follows four principal messages:
| Message | Direction | Purpose |
|---|---|---|
| `P3RQ` | Sender → Verifier | Session request |
| `P3CH` | Verifier → Sender | Session challenge |
| `P3CF` | Sender → Verifier | Client confirmation |
| `P3OK` | Verifier → Sender | Server confirmation |

The verifier may also issue `P3NO`, a generic refusal.
The handshake begins when the sender constructs a request associated with its local admission authorization.
The verifier checks the request, confirms that the authorization is valid, and creates a challenge containing the session context.
The challenge includes the server nonce, session identifier, and other values required for consistent key derivation.
The sender checks the challenge against its original request and claims the credential that passed independent verification.
Both endpoints then derive the session key independently.
The sender generates a client confirmation proof, which the verifier validates before activating its session.
The verifier responds with a server confirmation proof, which the sender validates before activating its own session.
The handshake messages are currently exchanged through local Python methods. They define byte representations but do not establish an implemented network transport.
Appendix A preserves the exact message formats and rejection behavior.

### Session-Key Derivation

Authentication-v2 uses HKDF-SHA-256 to derive session-key material.
The derivation inputs include,
- The verified four-byte credential.
- The server-generated nonce.
- The complete handshake transcript.
- A fixed protocol-specific domain string.

The sender uses the credential recovered through the admission process.
The verifier independently uses the enrolled credential stored in its trusted registry.
Both endpoints derive the same 32-byte session key when their credentials and transcript information match.
The session key supports,
1. Client confirmation.
2. Server confirmation.
3. HMAC authentication of motion windows.

The current protocol uses one session key for these purposes rather than separate client, server, confirmation, and motion-window subkeys.
The independent credential-verifier key is not used in HKDF.
Although HKDF produces a 256-bit output, the original experimental credential contains only 32 bits of information.
Key derivation cannot increase the entropy of that credential.
The exact HKDF inputs and HMAC confirmation formulas are provided in Appendix B.

### Mutual Confirmation

Mutual confirmation demonstrates that both endpoints possess matching derived session-key material.
The sender first computes a client confirmation HMAC over the appropriate confirmation domain and full handshake transcript.
The verifier independently calculates the expected value and compares it with the received proof.
If the proof is valid, the verifier activates the new session and generates its server confirmation proof.
The sender validates this second proof before entering its own active state.
A significant implementation detail is that the endpoints do not become active simultaneously.
The verifier activates after accepting `P3CF`.
The sender activates only after accepting `P3OK`.
This means the verifier can temporarily hold an active session while the sender remains pending.
For example, if `P3OK` is lost or corrupted, the verifier may remain active even though the sender cannot complete its confirmation.
The current prototype does not include a network-level recovery process for this condition.
Both proofs use full HMAC-SHA-256 values and constant-time comparison.

### Session States and Lifetimes

Authentication-v2 maintains session lifecycle information independently at the sender and verifier.
The main states are,
| State | Meaning |
|---|---|
| `PENDING` | A handshake has begun but the endpoint's confirmation requirements are incomplete |
| `ACTIVE` | The endpoint has satisfied its activation conditions |
| `FAILED` | The handshake or session attempt has failed |
| `CLOSED` | The session has been closed, replaced, or terminated |
| `EXPIRED` | The verifier has explicitly recorded expiration after the applicable deadline |

The current configuration uses,
- A 10-second handshake timeout
- A 300-second session lifetime
- A maximum of 10,000 accepted windows per session
- A maximum of 128 pending sessions
- A maximum of 10,000 session identifiers issued per verifier process

Only one active session is permitted for each device.
A successfully confirmed replacement session closes the previous active session for that device.
The verifier tracks issued session identifiers to prevent reuse during the lifetime of the process.
Session expiration is evaluated using monotonic time. A session is considered expired at its deadline.
The sender measures its session lifetime from the beginning of its authentication attempt, while the verifier measures active-session lifetime from confirmation.
The sender may therefore expire earlier than the verifier.
Expiration cleanup is performed through protocol operations or explicit lifecycle methods rather than automatic background timers.

## Authenticated Motion-Window Protection

### Wire2 Message Structure

After session establishment, the sender protects XR motion windows using the existing Wire2 binary representation.
The encoding is identified as:

`puf-snn-binary32-be-v2`

Each motion window represents approximately two seconds of motion data and contains exactly 120 ordered samples.
Every sample includes,
- Sample index
- Capture timestamp
- Three position coordinates
- Four quaternion components
- Tracking-validity flag

The window also contains authenticated metadata such as,
- Device identifier
- Session identifier
- Sequence number
- Window identifier
- Capture start and end times
- Tracking-valid sample count
- Tracking-valid fraction
- Protocol and payload version fields

Integer values use big-endian encoding, while position and orientation values use IEEE-754 binary32 representation.
The sender places the resulting binary data inside a JSON envelope containing the encoded bytes and authentication information.
The complete binary format, field widths, and required constants are documented in Appendix C.

### Motion-Window Authentication

The sender calculates an HMAC-SHA-256 tag over the complete canonical binary-window representation.
This tag protects the motion samples and all metadata included in the authenticated byte sequence.
If an attacker modifies any of these protected bytes without a valid replacement tag, authentication fails.
The full 32-byte HMAC is transmitted as 64 lowercase hexadecimal characters.
The JSON envelope contains the binary data in canonical base64 form.
The outer JSON formatting and selected wrapper fields are not directly included in the HMAC calculation, but they are still subject to strict parsing and representation rules.
The receiver checks that the supplied authentication information is consistent with the current session.
The envelope's `key_id` is validated after HMAC verification and trusted session binding. It does not independently select a cryptographic key.
Authentication provides integrity and session association.
It does not encrypt the transmitted motion data. An observer who obtains the envelope can decode its motion values and metadata.

### Data Quality Requirements

Authentication-v2 applies a fixed set of data-quality checks to ensure that accepted motion windows satisfy the expected input representation.
These checks are part of the research protocol rather than universal physical limits on human movement.
The implemented requirements include,
- Exactly 120 samples per window
- A nominal two-second window duration, with a tolerance of 120 nanoseconds
- Between 114 and 120 tracking-valid samples
- Tracking-valid metadata consistent with the actual sample flags
- Strictly increasing sample timestamps
- No consecutive sample-time gap greater than 50 milliseconds
- Finite binary32 position and quaternion values
- Quaternion component and norm constraints
- Nonnegative quaternion dot products between consecutive samples

The sender checks data quality before producing the authenticated packet.
The receiver also validates quality during message verification.
Invalid binary representations may fail during parsing before HMAC verification. Quality requirements that depend on the decoded motion content are evaluated later in the receiver's validation process.
A data-quality rejection does not authorize inference or advance accepted sequence state.
Appendix C contains the exact acceptance bounds.

### Replay and Sequence-Number Protection

Authentication-v2 uses strict exact-next sequence ordering.
Each new session begins with an expected sequence number of zero.
After a window is accepted, the receiver increments its accepted-window count and expects the next consecutive sequence number.
The relevant decisions are:
| Sequence Condition | Result |
|---|---|
| Exact expected sequence | `accepted` |
| Equal to the last accepted sequence | `duplicate_sequence` |
| Older than the last accepted sequence | `stale_sequence` |
| Greater than the expected sequence | `future_sequence_gap` |

Rejected packets do not advance the accepted-window count or change the last accepted sequence.
This prevents invalid traffic from poisoning receiver state.
For example, submitting a packet with an invalid HMAC and a large sequence number cannot force the receiver to advance its expected sequence.
The receiver also rejects validly authenticated packets that arrive ahead of the expected sequence.
If the missing packet later arrives, it may be accepted normally. The previously rejected future packet can then be resubmitted once its sequence becomes the expected value.
The receiver does not automatically buffer future packets.
An important limitation is that the sender increments its outgoing sequence when it seals a packet, not when the receiver acknowledges it.
Consequently, packet loss can interrupt progress unless the original packet is retained and later submitted or a new session is established.
The system's freshness protection is based on session context, lifetime, and sequence numbers. It does not compare capture timestamps against the receiver's current wall-clock time.

## Authenticated SNN Inference

### Verification and Accepted-Window Release

Authentication-v2 separates message verification from downstream inference.
A received motion window must pass the applicable parser, session, HMAC, identity-binding, data-quality, and sequence checks before its payload can be released.
When the verifier accepts a window, it commits the corresponding audit and sequence state and creates a `VerificationResult`.
This result contains the authenticated identities, accepted motion window, event identifier, and information identifying the exact authenticated bytes.
The verifier retains the original accepted-result object.
To release the payload, the caller must provide that same result object through `Verifier.release_accepted`.
The verifier checks object identity rather than merely comparing an externally constructed structure with the expected fields.
A copied, fabricated, substituted, or rejected result therefore cannot authorize release.
This ensures that the inference pipeline receives the exact payload accepted by the verifier.
A successful authentication decision does not automatically mean the inference callbacks have completed.
Authentication establishes the authority to release the window; inference execution is a separate stage.

### Exactly-Once Classifier Integration

The current pipeline uses `ExactlyOnceClassifierRelease` to prevent repeated processing of the same authenticated event.
Before invoking preprocessing or model callbacks, the release wrapper checks whether the event identifier has already been consumed.
If it has not, the event is marked consumed.
The accepted motion window is then converted into the classifier's required representation.
The inference pipeline prepares the motion and anomaly inputs before calling the models.
The processing sequence is,
1. Release accepted window
2. Convert the authenticated payload
3. Prepare motion and anomaly inputs
4. Invoke motion classification
5. Invoke anomaly detection

The model inputs are generated from the accepted motion-window content. Dataset labels, experiment identifiers, and attack configuration values are not introduced as authenticated model features.
Although the class is named `ExactlyOnceClassifierRelease`, its guarantee is specifically **at-most-once delivery** through the supported wrapper.
If preprocessing or inference fails, the event remains consumed.
The system does not automatically retry the callback, roll back the accepted sequence, or guarantee successful completion after an exception.

### Failure and Recovery Behavior

Authentication-v2 distinguishes ordinary authentication rejection from internal processing failures.
Ordinary rejections include,
- Invalid HMAC
- Unknown or inactive session
- Expired session
- Malformed window
- Invalid data quality
- Duplicate sequence
- Stale sequence
- Future sequence gap

These rejections do not advance accepted sequence state or invoke downstream inference.
The system can continue after many ordinary rejections.
For example, if an attacker modifies a packet after authentication, the modified packet is rejected. The original retained packet can still be accepted if it remains the exact expected sequence for the active session.
Other failures have more significant effects.
A lost handshake confirmation may leave endpoint states inconsistent.
A missing sequence can prevent later packets from being accepted.
A preprocessing or model callback failure occurs after authentication acceptance has already committed sequence state.
An audit or internal execution failure can mark evidence incomplete and prevent further processing.
These limitations are intentional properties of the current implementation and must not be interpreted as automatic recovery capabilities.
The complete failure matrix is provided in Appendix D.

## Threat Model and Security Analysis

### Attacker Capabilities

Authentication-v2 is evaluated against a Tier-1 threat model focused on protocol manipulation and unauthorized sensor-window delivery.
The attacker is assumed to have access to transmitted or otherwise observable protocol data.
Within this model, the attacker can capture authenticated packets, replay messages, change public packet bytes, substitute identifiers, reorder packets, withhold messages, and submit malformed representations.
The attacker may observe,
- Device and session identifiers
- Handshake nonces and transcripts
- Confirmation messages
- Motion-window contents
- Capture timestamps
- Sequence and window identifiers
- Authentication tags
- Public helper data, where accessible

The attacker is not assumed to possess the private session key, independent credential-verifier key, trusted registry credential, or valid local admission authorization.
The trusted Python process, enrollment system, verifier, and cryptographic implementation are not assumed to be compromised.
These restrictions are important because the prototype does not provide isolation from malicious code inside its trusted process.
The threat model also does not establish an actual network transport or physical Quest 3 attack surface.
The broader project evaluates legitimately authenticated semantic attacks separately. Authentication protects the origin and integrity of transmitted data within its assumptions, but it cannot establish that authenticated motion is benign.

### Replay and Message Modification

The protocol uses three complementary mechanisms to protect authenticated motion windows,
1. HMAC integrity verification
2. Device and session binding
3. Strict sequence-number enforcement

Each mechanism addresses a different class of failure.
An exact replay of an already accepted packet can preserve a valid HMAC and matching session identity. The replay is nevertheless rejected because its sequence number has already been consumed.
A packet whose protected motion data or metadata have been modified without a new valid HMAC fails integrity verification.
A packet associated with the wrong session or device cannot be accepted merely because its wrapper claims a valid identity.
A validly authenticated packet with a future sequence number is also rejected until the missing expected sequence has been accepted.
Together, these mechanisms prevent the tested forms of invalid traffic from being accepted through the supported verifier pathway.
The separate Tier-1 v2 experiment is responsible for measuring observed rejection behavior, legitimate controls, recovery outcomes, and inference-call counts under the registered attack populations.

The protocol specification itself is not a substitute for the formal experiment's measured results.

### Credential and Key Compromise

The security of the authentication system depends on the confidentiality and correct custody of its credential and cryptographic keys.
The independent credential-verifier key is separate from the session key.
This separation ensures that the verifier HMAC key is not directly used as the HKDF input or motion-window authentication key.
However, the 32-bit credential remains a major security limitation.
A successful captured handshake exposes the nonsecret values needed to reproduce HKDF derivation for candidate credentials and compare the resulting confirmation proofs.
An attacker with sufficient captured handshake information can therefore test guesses from the at-most-2^32 credential space offline.
The independent credential verifier does not prevent this attack because the session-confirmation transcript itself provides a way to validate candidate credentials.
The following distinctions are important,
| Compromised Material | Consequence |
|---|---|
| Public helper data alone | Does not automatically establish possession of the enrolled credential |
| Helper data and a sufficiently close PUF response | May allow reconstruction of the credential |
| Verifier record without verifier key | Exposes record metadata and tag but not the key required for the implemented verifier check |
| Verifier key plus records | Allows offline testing of credential guesses against enrolled tags |
| Enrolled credential | Exposes the value used for session-key derivation |
| Captured handshake transcript | Allows offline testing of 32-bit credential guesses |
| Session key | Allows valid HMAC generation for that session while the session remains usable |
| Trusted verifier-process compromise | Exposes or permits modification of internal enrollment, key, admission, and session state |

The receiver stores the enrolled credential in its registry for independent key derivation, so compromise of that registry can directly expose credential material.
Authentication-v2 also does not provide forward secrecy.
If the credential is later recovered, previously captured handshake transcripts can be used to derive their corresponding session keys.
These limitations prevent the current implementation from being described as production-grade authentication.

### Authentication Limitations

The current implementation demonstrates protocol mechanisms within a controlled software environment.
Its main security limitations are,
- Simulated rather than physical PUF behavior
- A 32-bit experimental credential vulnerable to offline guessing
- Raw enrolled credential storage in the receiver registry
- Co-located trusted Python execution
- No secure hardware key custody
- No encryption or payload confidentiality
- No forward secrecy
- No remote attestation
- No secure transport or automatic retransmission
- No protection against malicious code within the trusted process
- No general denial-of-service guarantee
- No persistent crash-safe replay or session-state recovery

Additional reliability limitations are separate from these security issues.
Single-read PUF reconstruction can fail because of noise. Independent verification prevents an incorrect candidate from being admitted but does not improve reconstruction availability.
Strict sequence ordering can also create availability problems when packets are lost.
Finally, the current implementation is evaluated using synthetic motion data and local software execution. It does not establish real-device PUF security, Quest 3 hardware latency, or real-world XR deployment performance.

## Implementation and Configuration

### Software Components

Authentication-v2 is implemented in the shared Python research repository.
The principal source components are:
| Component | Primary File |
|---|---|
| Simulated PUF | `src/python/puf_snn/puf/ro_puf.py` |
| PUF device model | `src/python/puf_snn/puf/device.py` |
| BCH reconstruction | `src/python/puf_snn/reconstruction/bch.py` |
| Credential reconstruction | `src/python/puf_snn/reconstruction/credential.py` |
| Independent credential verification | `src/python/puf_snn/auth/credential_verifier.py` |
| Session establishment and HKDF | `src/python/puf_snn/auth/session.py` |
| Authenticated sender | `src/python/puf_snn/auth/sender.py` |
| Authenticated verifier | `src/python/puf_snn/auth/verifier.py` |
| Binary Wire2 representation | `src/python/puf_snn/auth/binary_window.py` |
| Accepted-window integration | `src/python/puf_snn/integration.py` |
| Authentication-to-inference pipeline | `src/python/puf_snn/pipeline_v2.py` |
| Audit implementation | `src/python/puf_snn/auth/audit.py` |

The principal authentication configuration is:

`configs/authentication_v2.json`

The protocol specification corresponds to the supported Authentication-v2 pipeline and does not redefine the behavior of the older Authentication-v1 implementation.
The reconstruction-alternatives study and the expanded Tier-1 experiment are separate versioned evaluations.
The experiments do not automatically modify the protocol described here.

### Protocol Parameters

The implemented protocol uses the following configuration and representation parameters.

| Parameter | Value |
|---|---|
| Authentication configuration version | `puf-snn-auth-config-v2` |
| Protocol profile | `puf-snn-l3-credential-admission-v1-wire2` |
| Handshake protocol version | 2.0 |
| Authenticated-window protocol version | 2.0 |
| Motion payload version | 1.0 |
| Credential length | 32 bits |
| Credential-verifier key | 256 bits |
| Session key | 256 bits |
| Credential verification | HMAC-SHA-256 |
| Session derivation | HKDF-SHA-256 |
| Motion-window authentication | HMAC-SHA-256 |
| BCH parameters | BCH(63,36,t=5) |
| Handshake timeout | 10,000 ms |
| Session lifetime | 300,000 ms |
| Maximum windows per session | 10,000 |
| Maximum pending sessions | 128 |
| Maximum issued sessions per process | 10,000 |
| Motion samples per window | 120 |
| Motion representation | IEEE-754 binary32, big-endian |
| Maximum handshake body | 4,096 bytes |
| Maximum JSON envelope | 16,384 bytes |

The exact protocol constants and byte-level representations are defined in the appendices.
These settings describe the implemented research profile rather than tunable deployment policies.

### Implementation Traceability

The implementation can be traced through its source modules, configuration files, and automated tests.
The reconstruction behavior is primarily verified by tests under:
`tests/reconstruction/`

The authenticated session, credential-admission, binary-window, replay, lifecycle, and audit behavior are covered by tests under:

`tests/auth/`

The combined authentication-to-inference pathway is tested through,
- `tests/test_pipeline_v2.py`
- `tests/test_frozen_pipeline.py`

The expanded Tier-1 experimental harness is implemented separately through,
- `src/python/puf_snn/tier1_v2.py`
- `src/python/scripts/run_tier1_v2.py`
- `tests/tier1/test_tier1_v2.py`

The initial protocol-specification preparation recorded 237 passing authentication tests and 50 passing reconstruction tests at the original implementation baseline.
These are historical validation results and should not be interpreted as a fresh full-suite execution for every later repository revision.
The exact byte formats, message transitions, cryptographic calculations, and first-failure behavior described in this specification remain grounded in the implemented source and corresponding test expectations.
If a discrepancy is discovered between this document and a later source revision, the discrepancy must be investigated rather than silently assuming the documentation or new source is correct.

## Conclusions and Future Work

Authentication-v2 provides a structured software architecture for protecting XR motion data before it reaches SNN inference.
The implementation combines simulated PUF credential reconstruction, independent credential verification, local credential admission, authenticated session establishment, and HMAC-protected motion windows.
The independent credential-verification mechanism is particularly important because BCH reconstruction can produce incorrect but valid-format candidates. By checking credentials before session-key derivation, the system prevents those candidates from creating new authenticated sessions through the supported application flow.
After session establishment, HMAC integrity checks, trusted session binding, and strict sequence-number enforcement determine whether incoming motion windows may be accepted.
The accepted-window release mechanism then prevents rejected or substituted payloads from entering the supported inference pipeline.
The resulting architecture establishes a clear separation between credential recovery, authentication, message integrity, and downstream motion interpretation.
However, the current prototype is not a production security system.
Its simulated PUF behavior, 32-bit credential, co-located trust assumptions, and lack of secure key custody impose important limitations.
Future work may investigate,
- Integration of a validated reconstruction-reliability improvement
- Stronger credential entropy and production-appropriate key material
- More realistic PUF noise and environmental variation
- Authentication across separate device and verifier processes
- Reliable packet-loss and retransmission behavior
- Capture-time freshness under a trusted clock model
- Persistent session and audit-state management
- Formal evaluation of additional protocol attack classes
- Physical hardware or approved XR-device validation

The immediate experimental focus is to characterize the current protocol rather than introduce unmeasured design changes.
The separate Tier-1 v2 evaluation provides the framework for measuring replay rejection, protected-message integrity, state preservation, legitimate recovery, and inference gating under controlled attack populations.
Together with the reconstruction-alternatives experiment and the project's inference evaluations, these results can support a broader assessment of the reliability, security, and processing overhead of authenticated XR sensing.

## Appendix A — Exact Handshake Message Formats

This appendix preserves the exact framing and message definitions of the implemented Authentication-v2 handshake.

### A.1 Common Encoding Rules

All handshake messages use the following framing convention:

```text
frame(body) = U32_BE(len(body)) || body
```

Protocol versions are represented as:

```text
V(major, minor) = U16_BE(major) || U16_BE(minor)
```

Identifiers use length-prefixed restricted ASCII:

```text
LP16(x) = U16_BE(len(x)) || x
```

Each identifier must contain 1–128 bytes matching:

```text
[A-Za-z0-9][A-Za-z0-9._:-]{0,127}
```

The maximum handshake body length is 4,096 bytes.

The maximum total framed message length is therefore 4,100 bytes.

Parsers reject truncated frames, inconsistent lengths, trailing bytes, incorrect message identifiers, and unsupported versions.

### A.2 P3RQ — Session Request

**Direction:** Sender → Verifier

**Purpose:** Begin an authenticated session attempt after local credential admission.

```text
P3RQ body =
    "P3RQ"
    || V(2,0)
    || LP16(device_id)
    || client_nonce[32]
```

For device-ID length `d`, the body length is:

```text
42 + d bytes
```

The request does not include a cryptographic proof in its transmitted bytes.

Instead, the supported local API requires a live admission authorization bound to the exact request.

Successful receiver processing consumes that authorization before key derivation.

An invalid or unavailable authorization results in refusal without creating new receiver pending session state.

### A.3 P3CH — Session Challenge

**Direction:** Verifier → Sender

**Purpose:** Establish the session transcript and provide the values required for key derivation.

```text
P3CH body =
    "P3CH"
    || LP16(transcript)
```

For transcript length `len(T)`:

```text
P3CH body length = 6 + len(T)
```

The challenge does not contain an additional outer protocol-version tuple. The required version values are included in the transcript.

The verifier generates a 16-byte session identifier and 32-byte server nonce.

The transcript also includes the client nonce, verifier boot identifier, device identifier, and session limits.

The sender checks the transcript against its original request and configuration before deriving its key.

### A.4 Handshake Transcript

The transcript is encoded in the following order.

| Order | Field | Encoding |
|---|---|---|
| 1 | Handshake domain | `LP16("PUF-SNN/L3/handshake/v2")` |
| 2 | Fixed version tuple | `V(2,0)` |
| 3 | Fixed version tuple | `V(2,0)` |
| 4 | Fixed version tuple | `V(1,0)` |
| 5 | Fixed selector | `U16_BE(1)` |
| 6 | Device identifier | `LP16(device_id)` |
| 7 | Client nonce | 32 bytes |
| 8 | Verifier boot identifier | 16 bytes |
| 9 | Session identifier | 16 bytes |
| 10 | Server nonce | 32 bytes |
| 11 | Handshake timeout | U32 milliseconds |
| 12 | Session lifetime | U32 milliseconds |
| 13 | Maximum windows | U64 |

For device-ID length `d`:

```text
len(T) = 153 + d
```

The fixture using the eight-byte identifier `quest-02` produces a 161-byte transcript.

The fixed version and selector values are preserved exactly as implemented. Their positions are normative, even where the source does not establish additional semantic names.

### A.5 P3CF — Client Confirmation

**Direction:** Sender → Verifier

**Purpose:** Demonstrate possession of the derived session key.

```text
P3CF body =
    "P3CF"
    || V(2,0)
    || session_id[16]
    || client_proof[32]
```

The body length is exactly 56 bytes.

The client proof is an HMAC over its confirmation domain and the complete handshake transcript.

A correct proof permits the verifier to activate the session.

Malformed confirmation messages leave pending receiver state intact. An invalid proof or expired pending handshake terminates the pending attempt.

### A.6 P3OK — Server Confirmation

**Direction:** Verifier → Sender

**Purpose:** Demonstrate the verifier's possession of the derived session key.

```text
P3OK body =
    "P3OK"
    || V(2,0)
    || session_id[16]
    || server_proof[32]
```

The body length is exactly 56 bytes.

The server proof authenticates its confirmation domain, transcript, and original client proof.

Successful sender verification activates the sender session.

A failed sender verification does not undo the verifier's earlier activation.

### A.7 P3NO — Session Refusal

**Direction:** Verifier → Sender

**Purpose:** Indicate that the session request or confirmation has been refused.

```text
P3NO body =
    "P3NO"
    || V(2,0)
```

The body length is exactly eight bytes.

The message does not transmit a detailed failure reason.

Detailed protocol reasons remain available through local verification and audit information.

### A.8 Handshake Activation Summary

```text
Sender:
    IDLE
      |
      v
    PENDING
      |
      | P3CF sent
      |
      | P3OK verified
      v
    ACTIVE

Verifier:
    P3RQ received
      |
      v
    PENDING
      |
      | P3CF verified
      v
    ACTIVE
      |
      | P3OK emitted
```

Verifier activation occurs before the sender processes `P3OK`.

A lost `P3OK` may therefore leave the verifier active while the sender remains pending or eventually fails.

No automatic handshake reconciliation is implemented.

## Appendix B — Cryptographic Formulas and Key Hierarchy

This appendix records the cryptographic constructions used by the current Authentication-v2 implementation.

### B.1 BCH Helper-Data Construction

Let:

- `R` be the enrolled 64-bit PUF reference response.
- `credential4` be the four-byte experimental credential.
- `E` be the BCH(63,36,t=5) encoder.
- `m` be the credential message.

The BCH message is:

```text
m = bits_MSB(credential4) || 0000
```

The codeword is:

```text
c = E(m)
```

The helper bits are:

```text
helper[i] = R[i] XOR c[i]
```

for:

```text
i = 0..62
```

During reconstruction:

```text
received[i] = noisy_response[i] XOR helper[i]
```

The decoder is invoked once:

```text
candidate_message = BCH_decode_once(received)
```

A valid-format result must have zero values in its final four padding bits.

### B.2 Independent Credential-Verifier HMAC

Define:

```text
LP16(x) = U16_BE(len(x)) || x
```

The credential-verification message is:

```text
M_verify =
    LP16("PUF-SNN/credential-verifier/v1")
    || LP16(device_id)
    || LP16(enrollment_id)
    || LP16(reconstruction_id)
    || LP16(verifier_key_id)
    || credential4
```

The enrolled tag is:

```text
tag_verify = HMAC-SHA-256(K_verify, M_verify)
```

Where:

- `K_verify` is an independent 32-byte key.
- `credential4` is exactly four bytes.
- `tag_verify` is the full 32-byte HMAC.

The verifier recomputes this tag using the reconstructed credential candidate and compares it with the enrolled tag using `hmac.compare_digest`.

The independent verifier key is not used during HKDF session-key derivation.

### B.3 HKDF Session-Key Derivation

Session-key derivation uses HKDF-SHA-256.

The extract operation is:

```text
PRK = HMAC-SHA-256(server_nonce32, credential4)
```

The expand context is:

```text
info =
    LP16("PUF-SNN/L3/session-key/v2")
    || LP16(T)
```

Where `T` is the complete handshake transcript.

The 32-byte session key is:

```text
session_key32 = HMAC-SHA-256(PRK, info || 0x01)
```

This is the single HKDF-Expand block required for a 32-byte output.

The sender and verifier independently calculate the same value from the matching credential and transcript.

### B.4 Client Confirmation Proof

The client confirmation proof is:

```text
client_proof32 =
    HMAC-SHA-256(
        session_key32,
        LP16("PUF-SNN/L3/client-confirm/v2")
        || LP16(T)
    )
```

This proof is included in `P3CF`.

The verifier independently calculates the expected proof and compares the complete values.

### B.5 Server Confirmation Proof

The server confirmation proof is:

```text
server_proof32 =
    HMAC-SHA-256(
        session_key32,
        LP16("PUF-SNN/L3/server-confirm/v2")
        || LP16(T)
        || client_proof32
    )
```

This proof is included in `P3OK`.

It includes the original client proof to bind the server confirmation to the same exchange.

### B.6 Motion-Window HMAC

Let `A` represent the complete canonical authenticated binary-window bytes.

The window authentication tag is:

```text
tag_window =
    HMAC-SHA-256(session_key32, A)
```

The full 32-byte tag is used.

There is no additional window-HMAC domain prefix beyond the structured authenticated bytes themselves.

### B.7 Key Hierarchy

```text
Independent Verifier Key
K_verify (32 bytes)
       |
       v
Credential-Verifier HMAC
       |
       v
Credential Candidate Verification


Enrolled Credential (4 bytes)
       |
       v
Independent Verification
       |
       v
Local Credential Admission
       |
       v
HKDF-Extract
       |
       v
HKDF-Expand
       |
       v
Session Key (32 bytes)
       |
       +----> Client Confirmation HMAC
       |
       +----> Server Confirmation HMAC
       |
       +----> Motion-Window HMAC
```

The same session key is used for both confirmation proofs and authenticated motion windows.

No separate client/server or window-specific session subkeys are derived.

The session key's length does not increase the underlying entropy of the 32-bit credential.

## Appendix C — Wire2 Binary Encoding Specifications

This appendix preserves the authenticated binary-window representation used by the current protocol.

### C.1 Authenticated Window Structure

The authenticated binary byte sequence is represented as `A`.

All unsigned integers use big-endian encoding.

All motion values use IEEE-754 binary32 big-endian representation.

| Order | Field | Required Encoding |
|---|---|---|
| 1 | Magic | Four ASCII bytes: `P3AW` |
| 2 | Protocol version | `V(2,0)` |
| 3 | Authenticated-message version | `V(2,0)` |
| 4 | Payload version | `V(1,0)` |
| 5 | Fixed selectors | `01 01 20` |
| 6 | Device ID | `LP16(device_id)` |
| 7 | Session ID | 16 bytes |
| 8 | Sequence | U64 |
| 9 | Window ID | `LP16(window_id)` |
| 10 | Capture start | U64 nanoseconds |
| 11 | Capture end | U64 nanoseconds |
| 12 | Frame selector | `01` |
| 13 | Sample count | U16, exactly 120 |
| 14 | Tracking-valid count | U16 |
| 15 | Tracking-valid fraction | U32 parts per million |
| 16 | Payload length | U32, exactly 4,683 |
| 17 | Payload header | `01 00 3c` |
| 18 | Motion samples | 120 records of 39 bytes each |

For device-ID length `d` and window-ID length `w`:

```text
len(A) = 4759 + d + w
```

The permitted authenticated-byte length is therefore 4,761–5,015 bytes.

### C.2 Motion Sample Encoding

Each sample contains:

| Field | Encoding | Size |
|---|---|---:|
| Sample index | U16 | 2 bytes |
| Capture time | U64 | 8 bytes |
| Position x, y, z | Three F32 values | 12 bytes |
| Quaternion x, y, z, w | Four F32 values | 16 bytes |
| Tracking-valid flag | U8 | 1 byte |
| **Total** | | **39 bytes** |

Sample indexes must follow the exact order 0 through 119.

Floating-point values must be finite.

NaN and infinity are rejected.

Negative zero is canonicalized to positive zero during encoding, and transmitted negative-zero representations are rejected during parsing.

### C.3 Data Quality Constraints

| Requirement | Exact Rule |
|---|---|
| Sample count | Exactly 120 |
| Window duration | `abs(end - start - 2,000,000,000) <= 120` ns |
| Tracking-valid count | 114–120 |
| Tracking-valid metadata | Must equal actual sample-flag count |
| Tracking-valid PPM | Round-half-even of `count * 1,000,000 / 120` |
| Timestamp order | Strictly increasing |
| Maximum sample gap | 50,000,000 ns |
| Sample timestamp bounds | Within `[capture_start, capture_end)` |
| Quaternion component | Absolute value at most 1.000001 |
| Quaternion squared norm | Within `[0.9999^2, 1.0001^2]` |
| Quaternion continuity | Consecutive quaternion dot product must be nonnegative |

The timestamp and quaternion rules are applied to the represented values.

The receiver does not repair malformed quaternion values or reorder samples.

### C.4 JSON Authentication Envelope

The authenticated bytes are carried in a UTF-8 JSON envelope.

The required structure is:

```json
{
  "protected": {
    "encoding": "puf-snn-binary32-be-v2",
    "bytes_b64": "<canonical base64 of A>"
  },
  "authentication": {
    "algorithm": "HMAC-SHA-256",
    "key_id": "<32 lowercase hexadecimal characters>",
    "tag_hex": "<64 lowercase hexadecimal characters>"
  }
}
```

The parser rejects:

- Duplicate JSON keys.
- Extra or missing fields.
- Incorrect field types.
- Invalid UTF-8.
- UTF-8 byte-order marks.
- Incorrect encoding or algorithm identifiers.
- Noncanonical base64.
- Incorrect hexadecimal representation.
- Envelopes larger than 16,384 bytes.

The outer JSON key order may vary, but the required schema must remain unchanged.

### C.5 Authenticated and Unauthenticated Fields

The HMAC covers the entire canonical binary representation `A`.

This includes:

- Protocol versions and fixed selectors.
- Device identifier.
- Session identifier.
- Sequence number.
- Window identifier.
- Capture timestamps.
- Tracking-valid metadata.
- Motion samples and their timestamps.
- Payload lengths and fixed header bytes.

The HMAC does not directly cover:

- Outer JSON formatting.
- Outer JSON key order.
- Base64 textual representation.
- The fixed envelope encoding string.
- The envelope authentication algorithm string.
- The envelope key-ID string.
- The HMAC tag itself.

Fields outside the HMAC input remain subject to the parser's fixed representation requirements.

The envelope key ID must match the authenticated session identifier after HMAC and owner-binding verification.

It does not select the authentication key.

## Appendix D — Verification Order and Failure Matrix

This appendix documents the implemented receiver-verification sequence and the consequences of common failures.

### D.1 Receiver Verification Order

The verifier evaluates incoming windows in the following order.

1. Acquire the decision lock, check evidence state, establish timing and audit context.
2. Parse the JSON envelope and binary motion window.
3. Look up the claimed device and session.
4. Check session activity, expiration, and accepted-window limits.
5. Calculate and verify the complete HMAC.
6. Check trusted device, enrollment, and session binding.
7. Validate the envelope key ID.
8. Check internal sequence-state consistency.
9. Validate the authenticated motion-window quality requirements.
10. Evaluate duplicate, stale, and future sequence conditions.
11. Recheck session expiration after quality and ordering work.
12. Prepare the accepted-result object, audit record, and updated session state.
13. Recheck expiration immediately before publication and atomically commit the accepted state and audit result.

The order matters because the first failing check determines the observed ordinary rejection reason.

For example:

- Invalid binary representations are rejected before HMAC verification.
- Unknown devices or sessions are rejected before authentication.
- Invalid HMACs are rejected before key-ID and sequence checks.
- Quality failures are identified before sequence-order failures.
- Accepted sequence state is committed only after all required checks pass.

### D.2 Replay-State Behavior

For an active session:

```text
expected_sequence = accepted_count
```

Initially:

```text
accepted_count = 0
last_accepted = None
```

After an accepted packet:

```text
accepted_count = accepted_count + 1
last_accepted = accepted_sequence
```

The receiver applies:

| Condition | Decision | State Change |
|---|---|---|
| Sequence equals expected | `accepted` | Increment count and update last accepted |
| Sequence equals last accepted | `duplicate_sequence` | None |
| Sequence less than last accepted | `stale_sequence` | None |
| Sequence greater than expected | `future_sequence_gap` | None |
| HMAC invalid | `invalid_tag` | None |
| Session expired | `expired_session` | None |

A rejected packet cannot consume the expected receiver sequence.

### D.3 Credential and Handshake Failure Matrix

| Failure | Expected Behavior | Session-Key Derivation | New Session State |
|---|---|---|---|
| BCH decoder failure | Reject reconstruction | None | None |
| Invalid BCH padding | Reject reconstruction | None | None |
| Wrong valid-format credential | Credential verification fails | None | None |
| Missing verifier record | Credential verification fails | None | None |
| Disabled or revoked record | Credential verification fails | None | None |
| Invalid admission authorization | Refuse request | No new derivation for refused request | No new pending session |
| Malformed session request | Refuse request | None for refused request | No new pending session |
| Invalid client confirmation proof | Refuse confirmation | Derivation may already have occurred | Pending terminated; no new active session |
| Malformed client confirmation | Refuse confirmation | Derivation may already have occurred | Pending can remain |
| Invalid server confirmation | Sender rejects confirmation | Both may already have derived keys | Verifier may remain active |
| Handshake timeout | Reject at applicable boundary | Depends on stage | Pending or sender state fails as applicable |

The no-derivation and no-new-session guarantees apply to failed initial credential verification and admission.

They must not be generalized to every later handshake failure, because some failures occur after the receiver has already derived a key or created pending state.

### D.4 Authenticated-Window Failure Matrix

| Failure | Expected Reason | Receiver Sequence Change | Inference |
|---|---|---|---|
| Invalid HMAC | `invalid_tag` | None | None |
| Unknown device | `unknown_device` | None | None |
| Unknown session | `unknown_session` | None | None |
| Inactive session | `inactive_session` | None | None |
| Expired session | `expired_session` | None | None |
| Device/session binding mismatch | `device_session_mismatch` | None | None |
| Invalid envelope key ID | `invalid_key_id` | None | None |
| Invalid data quality | `data_quality_failure` | None | None |
| Duplicate packet | `duplicate_sequence` | None | None |
| Stale packet | `stale_sequence` | None | None |
| Future sequence gap | `future_sequence_gap` | None | None |
| Malformed representation | Parser/schema/version reason | None | None |
| Valid expected packet | `accepted` | Increment and commit | Permitted through release |

Rejected packets do not receive accepted-window release authority.

### D.5 Inference and Audit Failures

Authentication acceptance and inference completion are separate events.

The receiver commits accepted sequence state before the inference callbacks execute.

The consequences of downstream failures are:

| Failure | Authentication State | Inference State |
|---|---|---|
| Accepted-window conversion failure | Acceptance remains committed | Event consumed; models not invoked |
| Preprocessing failure | Acceptance remains committed | Event consumed; models not invoked |
| Motion-model failure | Acceptance remains committed | Motion callback invoked; anomaly callback not invoked |
| Anomaly-model failure | Acceptance remains committed | Motion callback completed; anomaly callback invoked and failed |
| Audit/result preparation failure before acceptance commit | Acceptance not published | No inference authorized |
| Failure after acceptance commit | Committed acceptance retained; evidence marked incomplete | No automatic rollback or retry |

The inference-release wrapper marks an event consumed before processing begins.

Consequently, a failed model invocation does not make the same accepted event eligible for automatic repeated delivery.

Internal audit failures are treated as execution and evidence failures rather than ordinary authentication rejections.

### D.6 Audit and Evidence Behavior

The sender and verifier maintain separate audit recorders.

The audit system records selected information about:

- Authentication decisions and reasons.
- Observed identifiers.
- Authenticated identity when established.
- Session states and transitions.
- Sequence-number expectations.
- Missing sequence ranges.
- Authentication-byte hashes when available.
- Timing and internal failure information.

A sender's successful packet-sealing operation does not establish receiver acceptance.

Similarly, a successful HMAC comparison does not necessarily mean all device-binding, quality, or ordering checks passed.

Only the verifier's final accepted decision establishes authenticated release authority.

Audit records are maintained in memory and may be explicitly exported to JSONL.

The current implementation does not guarantee production-grade durable logging, tamper-resistant evidence storage, or recovery after a process crash.

These distinctions must be retained when interpreting authentication decisions and experimental evidence.