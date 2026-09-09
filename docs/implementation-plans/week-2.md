# Week 2 Implementation Plan

**Owners:** Keegan and Will  
**Goal:** Turn our Week 1 plan and faculty feedback into working code that uses one shared data format.

## What we need to finish

| Owner | Work | Evidence in the repository |
|---|---|---|
| Both | Finalize the 5 labels, 2-second window, schema, attack boundaries, and cross-session split | `docs/spec.md`, `configs/pilot-v0.2.json`, and `schemas/` |
| Keegan | Create repeatable Quest-style head-motion data | Generator code and tests |
| Keegan | Check the data format, timing, tracking, quaternions, IDs, sequences, and split leakage | Validator code, tests, and results summary |
| Will | Build a configurable simulated noisy PUF | PUF code, configuration, and tests |
| Will | Measure PUF reliability, uniqueness, uniformity, and raw bit-error rate | Results, figure, and short explanation |
| Both | Agree on the exact data that authentication will protect | `docs/spec.md` and `docs/puf-auth-design.md` |
| Both | Define the first 5 authentication attacks and their expected results | Authentication design and tests |
| Both | Finish the questions that need faculty decisions | `docs/faculty-decision-memo.md` |
| Each | Update individual work, results, decisions, and blockers | Research logs |

## Keegan's working artifact

I will produce a synthetic data generator and validator.

The generator will create data that follows:

`schemas/quest-window-v0.2.schema.json`

It will create
- 6 simulated devices
- 3 sessions per device
- 20 trials per class in each session
- 5 motion classes
- 1,800 total windows
- 120 samples in each window

The validator will check
- Required fields
- Sample count and order
- Increasing timestamps
- Timestamp gaps
- Quaternion normalization
- Quaternion sign continuity
- Tracking coverage
- Window and session IDs
- Sequence-number order
- Trial and session leakage

A clean dataset should pass with no unexplained errors. Intentionally damaged data should be rejected.

## Will's working artifact

Will will build a configurable simulated PUF that produces device-specific response bits with controlled noise.

He will measure
- Reliability
- Uniqueness
- Uniformity
- Raw bit-error rate
- Key reconstruction success, if reconstruction is included this week

The PUF settings and error-correction method shouldn't be copied from the old plan without evidence. They should be based on the first measurements.

## Shared work

Together, we will finish
- Specification version 0.2
- Data schema version 0.2
- Updated threat model
- Authenticated-window format
- First 5 Tier-1 attacks
- Faculty decision memo
- Repository README
- Revised presentation
- Individual research-log updates

The most important shared task is agreeing on the exact sensor window format.

My (Keegan) generator must create the same fields that Will's authentication layer expects to protect and verify.

## Week 2 checklist

- The same 5 labels are used everywhere.
- Each window contains exactly 120 ordered samples.
- The generator produces repeatable results with the same seed.
- The validator rejects timestamp gaps above 50 ms.
- The validator rejects tracking coverage below 95%.
- Invalid quaternions are rejected.
- Quaternion sign continuity is checked.
- Session 1 is used only for training.
- Session 2 is used only for validation.
- Session 3 is used only for testing.
- A source trial can't appear in multiple splits.
- Every PUF claim clearly says `simulated`.
- The authentication format protects the device, session, integrity, freshness, and sequence order.
- No human-subject data are collected without approval.
- Each person runs and records their own tests.
- Each result includes the configuration, seed, command, code version, and interpretation.
- Code and documentation are committed without generated data or private information.

## Current dependencies

Quest deployment depends on faculty or lab confirmation of
- Which Quest 3 headsets we can use
- The lab-managed Meta developer organization
- Developer-mode access
- ADB access
- The headset administrator
- The approved development computer

Until that is confirmed, I (Keegan) will use the synthetic generator.
Human recordings depend on faculty and institutional approval. We won't collect or save human motion data before that decision.
Integration depends on Will and I agreeing on the exact window fields and data that authentication will protect.