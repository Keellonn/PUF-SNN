# Layer 2 Credential Reconstruction

**Owner:** Will Wallace  
**Version:** 0.1
**Last updated:** September 22, 2026

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

# Layer 2 Overview

## Purpose
Layer 2 takes the noisy 64 bit response from layer 1 and attempts to reonstruct the same device credential that was established during enrollment.
The main goal for this layer is to determine if a stable credential can be recovered from a noisy response before the credential is used for layer 3 session authentication.

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

The reconstruction process does not compare the candidate credential against the enrolled credential. The credential correctness is measured by the experiment evaluator.

## Reconstruction Outcomes
A reconstruction attempt produces,
- `candidate_valid_format`; BCH returned a candidate credential with valid padding
- `decoder_failure`; the BCH decoder could not return a usable codeword
- `invalid_format_or_padding`; BCH returned a message, but the required padding bits were invalid

A valid-format candidate is not automatically known to be the correct credential. The experiment evaluator later determines whether the candidate matches the enrolled credential.

## Metrics Collected
The results measure:
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
- BCH(63,36,t=5) corrects at most five bit errors by design
- Reconstruction success alone does not authenticate the device; Layer 3 performs cryptographic key confirmation and session/window authentication