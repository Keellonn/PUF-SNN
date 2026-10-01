# Layer 2 Credential Reconstruction

**Owner:** Will Wallace
**Version:** 0.2
**Last updated:** September 30, 2026

# How to run as of Week 4

## Prerequisites
Working layer 1 simulation

## Running the Simulator
To run the layer 2 simulation, first you must run a successful layer 1 simulation. To run the layer 2 simulation on the most previous layer 1 simulation ran, use:
.\run_layer2.ps1
To run the layer 2 simulation for a specified layer 1 simulation use:
.\run_layer2.ps1 -InputRun "sim_results\run-seed-[existing-seed]-[existing-id]"
Ex: .\run_layer2.ps1 -InputRun "sim_results\run-seed-1234-ud43sry0"
The example will run a layer 2 simulation for the existing layer 1 simulation with seed 1234 and ID: ud43sry0

## Results
The reconstruction statistics and results are stored within the directory:
\results\week-4\will\reconstruction

The results measure:
# How to Run

## Prerequisites
Working Layer 1 simulation evidence.

## Running a Single Layer 2 Reconstruction Experiment

To run the original single-run Layer 2 workflow on the most recent compatible Layer 1 simulation, use:

`.\run_layer2.ps1`

To run Layer 2 for a specified Layer 1 simulation, use:

`.\run_layer2.ps1 -InputRun "sim_results\run-seed-[existing-seed]-[existing-id]"`

This helper workflow produces individual Layer 2 reconstruction results under:

`\results\week-4\will\reconstruction`

## Formal Layer 2 Evaluation

The completed Week 5 formal reconstruction evaluation is documented in:

`docs/layer2-formal-evaluation-week5.md`

Its sealed evidence is stored under:

`results/week-5/will/reconstruction/layer2-experiment-v1-formal-001`

The formal evaluation used the frozen BCH reconstruction design and evaluated 84,000 total reconstruction attempts across the nominal condition and six noise-sweep conditions.

The formal evidence directory should not be reused or overwritten by future runs.

## Results

Layer 2 reconstruction results measure,
- Total reconstruction attempts
- Successful credential reconstructions
- Failed credential reconstructions
- Reconstruction success rate
- False rejection rate (FRR)
- Decoder failures
- Invalid format or invalid padding outcomes
- Miscorrections
- 63-bit response BER
- Distribution of actual bit errors in the 63-bit response
- Reconstruction outcomes grouped by actual error count
- Reconstruction latency:
  - Mean
  - Median
  - p95
  - Maximum
- Per-device reconstruction performance

# Layer 2 Overview

## Purpose
Layer 2 takes the noisy 64-bit response from Layer 1 and attempts to reconstruct the same device credential that was established during enrollment.
The main goal of this layer is to determine whether a stable credential candidate can be recovered from a noisy PUF response.
Layer 2 does not independently authenticate the returned credential. A valid-format result is passed forward as a candidate credential. In the current authentication-v2 pipeline, Layer 3 independently verifies that candidate against trusted enrollment information before allowing it to reach session-key derivation.

## Reconstruction Design
The current design uses a BCH(63,36,t=5) error correcting code,
- Layer 1 produces a 64-bit PUF response
- Layer 2 uses response bits 0 through 62
- Bit 63 is omitted because the selected BCH code operates on 63-bit codewords
- The credential is 32 bits
- Four zero padding bits are appended to form the 36-bit BCH message
- BCH can correct up to five bit errors in the selected 63-bit response

## Enrollment Process
Within the enrollment process,
- A trusted 64-bit reference PUF response is provided
- A 32-bit credential is generated for the simulated device
- Four zero padding bits are appended to the credential
- The 36-bit message is BCH encoded into a 63-bit codeword
- The codeword is XORed with the selected 63 reference bits
- The resulting 63-bit value is stored as public helper data

## Reconstruction Process
During reconstruction,
- A noisy 64-bit PUF response is received
- Bits 0 through 62 are selected
- The noisy response is XORed with the stored helper data
- The resulting 63-bit word is passed to the BCH decoder
- The decoded message is checked for valid zero padding
- If valid, the first 32 bits are returned as the candidate credential

The reconstruction process does not compare the candidate credential against the enrolled credential. 
During formal Layer 2 experiments, an evaluator compares the returned candidate against enrolled truth only after `reconstruct()` returns so that reconstruction success, decoder failure, invalid padding, and miscorrection can be measured.
During the current authentication-v2 runtime path, evaluator truth is not used. Instead, a valid-format candidate must pass the independent credential verifier before it can enter Layer 3 session-key derivation.

## Reconstruction Outcomes
A reconstruction attempt produces,
- `candidate_valid_format`; BCH returned a candidate credential with valid padding
- `decoder_failure`; the BCH decoder could not return a usable codeword
- `invalid_format_or_padding`; BCH returned a message, but the required padding bits were invalid

A valid-format candidate is not automatically known to be the correct credential.
If a valid-format credential differs from enrolled truth, the formal evaluator classifies it as a miscorrection. The completed formal Layer 2 evaluation observed this behavior when the selected-bit error count exceeded the BCH correction radius.
In the current runtime authentication path, this distinction is handled by the independent pre-HKDF credential verifier rather than by Layer 2 itself.

## Metrics Collected
The results measure,
- Total reconstruction attempts
- Successful credential reconstructions
- Failed credential reconstructions
- Reconstructions success rate
- False rejection rate (FRR)
- Decoder failures
- Invalid format or invalid padding outcomes
- Miscorrections
- 63 bit response BER
- Distribution of actual bit errors in the 63 bit response
- Reconstruction outcomes grouped by actual error count
- Reconstruction latency including,
    - Mean
    - Median
    - p95
    - Maximum
- Per device reconstruction performance

## Current Limitations
- The PUF responses are simulated rather than collected from a physical PUF
- Enrollment currently uses an ideal noiseless reference response
- The 32-bit credential is intended to validate the reconstruction mechanism, not provide production-grade cryptographic strength
- BCH(63,36,t=5) guarantees correction of up to five selected-bit errors; beyond that radius, decoder failure, invalid padding, or a valid-format wrong credential can occur
- Reconstruction success alone does not authenticate the device
- Layer 2 intentionally returns a credential candidate rather than performing independent credential authentication
- In the current authentication-v2 pipeline, independent credential verification occurs after reconstruction and before HKDF
- Session key confirmation and authenticated-window protection remain separate Layer 3 responsibilities