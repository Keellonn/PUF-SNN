# Tier 1 Attacks

**Owner:** Will Wallace  
**Version:** 0.1  
**Last updated:** September 23, 2026

# How to run as of Week 4

## Prerequisites
The Layer 3 baseline files must match the frozen baseline. The Tier 1 runner checks the baseline before executing any attack trials.

## Running the Simulator
To run the Tier 1 attack simulations using the default configuration, run,
.\run_tier1.ps1

The simulation performs,
- 100 legitimate control trials
- 100 same-session replay attacks
- 100 prior-session replay attacks
- 100 cross-device substitution attacks
- 100 payload modification attacks
- 100 metadata modification attacks
- 100 supporting cross-session substitution attacks
- 20 warmup trials excluded from the formal result totals

## Results
The Tier 1 results are stored in a directory within:
\results\week-4\will\authentication

The results measure,
- Total attempts for each attack
- Accepted and rejected attempts
- Observed rejection rate
- Unexpected accepts and unexpected-accept rate
- Legitimate control acceptance rate
- Expected and actual rejection reasons
- State-mutation violations
- Payload-release violations
- Unexpected behavior
- Wilson 95 percent confidence intervals
- Sender preparation and HMAC latency
- Verifier authentication latency
- Total Layer 3 latency
- Per-variant attack performance
- Audit and trial-plan reconciliation
- Baseline integrity before and after the experiment

# Tier 1 Attacks Overview

## Purpose
The Tier 1 experiment evaluates attacks that should be rejected by the Layer 3 authentication gate before motion data is allowed to reach inference.
The attacks focus,
- Replay protection
- Session binding
- Device binding
- Payload integrity
- Protected-metadata integrity
- Sequence enforcement

Tier 1 does not evaluate whether an authenticated motion pattern is semantically abnormal.
Noise, drift, freezes, pose jumps, and other correctly authenticated motion changes all belong to Tier 2 experiments which are not yet implemented.

## Threat Model
The Tier 1 attacker can observe and manipulate transmitted authenticated traffic but does not possess the session key.

The attacker may,
- Replay a previously valid message
- Change protected device information
- Change protected session information
- Modify motion payload data
- Modify protected metadata
- Submit traffic under the wrong session or device context

The attacker does not have access to the credential-derived authentication key.
An attack is considered successful only if manipulated or replayed traffic is incorrectly accepted by the verifier.

## Legitimate Control
The legitimate-control trials provide the positive baseline.

A correctly generated window with,
- The correct device
- The correct active session
- A valid HMAC
- Acceptable tracking quality
- The expected sequence number
shall be accepted

## Same-Session Replay
The attacker resubmits a previously accepted authenticated window in the same active session.
The original message and HMAC remain unchanged.
Since the message was previously accepted, the sequence number has already been consumed.

The expected rejection reason,
duplicate_sequence

## Prior-Session Replay
The attacker captures a legitimate authenticated window from one session.
A new valid session is later established and the previous session becomes inactive.
The attacker then replays the old window.

The expected rejection reason,
inactive_session

## Cross-Device Substitution
The attacker takes a valid authenticated message for one device and changes the protected device identity while retaining the original authentication tag.
Changing the protected device identifier changes the authenticated data.
Because the attacker cannot generate a new valid tag, verification should fail.

The expected rejection reason,
invalid_tag

## Payload Modification
The attacker modifies part of the motion payload after the sender has generated the HMAC.
The original authentication tag is retained.
Because the sensor payload is included in the authenticated Wire-2 representation, the modified payload should fail HMAC verification.

The expected rejection reason,
invalid_tag

## Metadata Modification
The attacker modifies protected metadata after authentication.
The Tier 1 experiment modifies protected sequence information while retaining the original HMAC.
Because the sequence number is part of the authenticated data, the modified message should fail authentication.

The expected rejection reason,
invalid_tag

## Supporting Cross-Session Substitution
The attacker changes the protected session identifier to another active session while retaining the original authentication tag.
The message no longer matches the session context under which the tag was generated.

The expected rejection reason,
invalid_tag

## State-Safety Checks
Rejecting the attack is not enough by itself.
The experiment also checks that rejected traffic does not incorrectly change trusted verifier state.

That means it checks for,
- Unexpected sequence advancement
- Unexpected accepted-window count changes
- Unexpected session-state mutation
- Rejected payload reaching the trusted consumer

A rejected attack should leave trusted accepted-window state unchanged.

## Payload-Release Checks
Rejected traffic must not reach the accepted-payload callback.
Only windows associated with a successful accepted verification result should be released to the inference pipeline.
Payload-release violations are therefore recorded separately from the verifier's accept/reject decision.

## Attack Rejection Metric
The primary attack metric is,

Observed Rejection Rate = Rejected Attack Trials / Total Attack Trials

Results should be described as observed finite-trial results.
For example: 100/100 observed rejection
This should not be treated as proof that the attack can never succeed.

## Latency Measurements
Tier 1 measures authentication timing during both legitimate and attack traffic.
The primary timing measurements are,
- Sender preparation latency
- HMAC latency
- Verifier authentication latency
- Total Layer 3 latency

For each window,
- Total Layer 3 = Sender Preparation + Verifier Authentication
- HMAC timing is already included inside sender preparation and should not be added separately
- Percentiles should be calculated from the total per-window measurements rather than by adding independently calculated percentile values

## Reproducibility
The Tier 1 experiment records the following,
- Experiment configuration
- Experiment seed
- Trial plan
- Raw attempts
- Expected results
- Actual results
- Audit records
- Latency results
- Reconciliation information
- Baseline hashes
- Environment metadata
- Artifact manifest
- Completion marker

## Current Limitations
- The experiment evaluates a software authentication prototype
- The experiment does not evaluate a physical Quest PUF
- Tier 1 does not evaluate semantic abnormalities in authenticated motion data
- Tier 1 does not evaluate SNN adversarial examples
- Finite attack trials do not prove universal rejection
- The attacker is not assumed to possess the credential-derived authentication key
- Timing results are workstation/Python measurements rather than embedded Quest or FPGA performance measurements
- More advanced semantic and adaptive attacks remain outside the current Tier 1 scope

## Important Takeaways
- Tier 1 evaluates whether replayed, modified, or misattributed traffic is rejected before inference
- Legitimate controls are included to verify that valid traffic continues to be accepted
- Replay protection depends on session and sequence tracking in addition to HMAC verification
- Payload and protected-metadata modification should be detected through HMAC verification
- Rejected traffic must not advance trusted state
- Rejected traffic must not reach the inference callback
- The Tier 1 experiment provides the formal security-evaluation framework for Layer 3
- The smaller Layer 3 synthetic runner is primarily used to demonstrate the successful authentication path