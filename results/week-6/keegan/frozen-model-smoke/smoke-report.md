# Week 6 frozen-model v2 functional smoke

Source commit: `7d07a4f7f2de58b64ae17f98aa9c1478a9803f14`

Fresh single-read attempts: 30; admitted: 30; refused: 0.

Accepted composite deliveries: 90; motion models: 5; frozen detectors: 6.

Every active session exercised bad-tag rejection, clean acceptance, exact-replay rejection,
authenticated pre-tag position-jump inference, a 113/120 tracking-valid sender refusal,
and subsequent valid acceptance. Refusals preserved model-call and sequence state.

An anomaly flag is downstream metadata, not an authentication rejection. No expected
classification or anomaly flag was enforced. Conventional models are the existing
recorded seed-7 storage refits; all three saved SNN-32 checkpoints were used.

Functional validation cohort: 30 predeclared single-read admission attempts on six fixed simulated PUF profiles, with paired repeated windows and boundary controls. This is not a new held-out accuracy/attack-recall estimate, an FRR study, formal Tier-1 evaluation or latency benchmark. No claim of Quest, cross-device/person generalization, hardware acquisition time or production security.

Enrollment/model loading/backend cold-start behavior were not timed.
Audit is in memory. Durable I/O, full timing/outlier analysis and formal attack/reliability
evaluations remain pending. JSONL output is outside the inference path.
