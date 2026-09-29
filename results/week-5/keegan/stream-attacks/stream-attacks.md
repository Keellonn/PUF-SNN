# Tier 2 Stream Attack Plan

Clean source windows: 1,800
Planned cases: 50,400

Each source has one clean control and nine attacks at three severity levels. Seeded magnitudes vary within the predefined 0.8-1.2 multiplier range, with different directions/onsets/random samples. Clean and transformed copies retain their source split.

The plan stores metadata rather than repeated full motion windows. Evaluation regenerates each case from the frozen source and recorded seed. Attack names, labels, severities and seeds never become sensor/model features.

Constructed example cases: 84
Example outcomes: {'construction_failure': 8, 'quality_valid': 76}

Timestamp jitter and dropped samples are applied to synthetic source samples and reconstructed onto the original 120-point grid using linear position interpolation and quaternion SLERP. Non-increasing source times, gaps above 50 ms, or missing grid coverage cause a construction failure. The endpoints are retained/anchored, so this experiment does not measure boundary dropout or clock drift.

The output checks canonical binary32 quality but does not generate HMAC tags, invoke a verifier, run a classifier, or train an anomaly detector. COMPLETE means this plan and its example checks finished, not that Week 5 evaluation is complete.

Original motion labels describe the intended source task. Severe corruption can make the observed movement ambiguous; classification loss is measured relative to that source task. The anomaly label means a documented synthetic transform was applied, not that real malicious activity has been proven.

No reconstruction reliability, pre-HKDF credential verification, formal Tier-1 rejection rate, physical Quest behavior, or full-system availability is established here.
