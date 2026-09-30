# Week 5 Results

This week I evaluated synthetic sensor-stream changes that occur before a legitimate sender authenticates a Quest-style motion window. I also trained separate logistic-regression and random-forest anomaly detectors. The existing recurrent SNN remains a five-class motion classifier; it was not converted into an anomaly detector. No human-derived or physical Quest motion was collected.

## Tier 2 attack plan

The frozen plan pairs each of the 1,800 clean source windows with one clean control and 27 transformed cases: nine attack types at low, medium, and high severity. Position and orientation noise, drift, and jumps; timestamp jitter; dropped samples; and frozen pose are applied before the legitimate sender creates a tag. Each transformed copy stays in its source window's original train, validation, or test split. Attack names, severities, source IDs, labels, and split assignments are evaluation metadata, not anomaly-model features or authenticated sensor fields.

This differs from Will's Tier 1 post-tag replay and substitution attacks. A quality-valid Tier 2 window can authenticate correctly because the legitimate sender signs the altered sensor data. That acceptance is not an HMAC failure.

| Full-plan outcome | Windows |
|---|---:|
| Planned cases | 50,400 |
| Quality-valid constructed cases | 44,899 |
| Construction failures retained in the denominator | 5,501 |
| Post-construction quality failures | 0 |

The held-out Session 3 test split had 600 clean sources and 16,800 planned paired cases. Of these, 14,956 were quality-valid and entered both model conditions; 1,844 failed construction before authentication. A construction failure is not a verifier rejection or a detector true positive.

## Evaluation method

The motion comparison used the frozen Week 4 64-neuron SNN checkpoints and unchanged conventional-model recipes. The conventional models were refitted on clean Session 1 data because Week 4 did not save their model binaries. The Week 4 32-neuron ablation was not substituted into this experiment.

The separate anomaly detectors used 48 relative-pose and timing-derived features. Training used Session 1 with source-balanced weights; each source contributed equal total weight split between its clean case and constructed changes. Model seeds 6007, 6017, and 6027 were separate from motion, attack, and bootstrap seeds. Each detector threshold was selected from Session 2 only under a maximum 5% clean validation false-positive rate. Session 3 remained held out for the reported results.

Each quality-valid test case was compared in an unauthenticated path and a real sender/verifier path. The authenticated path used known-correct synthetic credential material, checked the exact accepted sensor data, and delivered it through one at-most-once composite consumer to both the motion classifier and anomaly detector. It did not measure PUF reconstruction reliability.

## Held-out results

Mean macro-F1 across the three motion seeds, on the same quality-valid test cases:

| Five-class motion model | Clean controls | All quality-valid cases, unauthenticated | All quality-valid cases, authenticated |
|---|---:|---:|---:|
| Logistic regression | 0.9048 | 0.8112 | 0.8112 |
| Random forest | 0.8936 | 0.8760 | 0.8760 |
| 64-neuron SNN | 0.8500 | 0.7452 | 0.7452 |

Anomaly results are means across the three detector seeds. The false-positive rate uses clean held-out cases; medium/high recall uses quality-valid changed cases at those severities.

| Separate anomaly detector | Test precision | Test recall | Test F1 | Clean test false-positive rate | Medium/high recall |
|---|---:|---:|---:|---:|---:|
| Logistic regression | 0.9970 | 0.7293 | 0.8424 | 5.33% | 82.85% |
| Random forest | 0.9985 | 0.8197 | 0.9003 | 2.94% | 87.95% |

Both detectors missed the provisional 90% medium/high recall target. Logistic regression also exceeded the 5% clean false-positive target on the held-out test split, although its threshold met the validation constraint. Orientation drift was particularly difficult: mean detector recall was about 5-6% at medium severity and 13-14% at high severity. Full per-transform counts, confusion matrices, seed variation, and source-cluster bootstrap intervals are in `stream-evaluation/results.json`.

All 14,956 quality-valid test cases were accepted and released across 150 fresh synthetic sessions. The paired authenticated and unauthenticated paths produced zero motion-prediction differences and zero anomaly-flag differences; their maximum anomaly-score difference was approximately 2.7e-15. These checks show that the accepted-window boundary preserved the model input for this configured test. They do not establish a production false-reject rate, physical headset behavior, or generalization across people or unseen devices.

## Session-expiry recovery and validation

The first full evaluation stopped after its pilot authentication session expired. The corrected harness keeps the five-minute policy, renews sessions before their time limit, and permits one fresh-session retry for an expiry before model delivery. It saves a hash-chained accepted-case checkpoint so a later interruption can resume without repeating completed model calls. The completed run reused its saved construction results, six detector models, frozen validation thresholds, and unauthenticated predictions; the original uncheckpointed authentication portion had to be rerun.

The targeted stream-attack, anomaly, and stream-evaluation suites passed 26, 15, and 17 tests respectively. The full Python suite passed 380 tests. I checked the completion marker, case and prediction row counts, all 22 recorded artifact hashes in the local completed run, and the exact accepted-input reconciliation. The result text files are pinned to LF line endings so their recorded hashes remain stable across Windows checkouts.

## Evidence and limitations

- Attack plan and construction examples: `results/week-5/keegan/stream-attacks/`
- Complete held-out metrics, figures, case predictions, accepted-delivery evidence, recovery context, and manifest: `results/week-5/keegan/stream-evaluation/`
- Test evidence: `results/week-5/keegan/test-evidence/`
- Permanent method and threat-model detail: `docs/tier2-stream-attacks.md`
- Frozen source dataset SHA-256: `752b009588f3e721a8bf2f8f8fcd1cdf0f7e998446b60953dd34dd5e9e54d661`

The 50,400 planned cases are transformed copies of 1,800 synthetic source windows, not independent recordings. Severe transformations can make the original motion label ambiguous. The recorded runtime is not an inference-latency measurement; detector-inclusive matched timing remains unmeasured. This experiment does not demonstrate physical Quest capture, real-person anomaly detection, PUF reconstruction availability, Will's formal Tier 1 rates, or a deployed system.

The six locally generated detector binaries are Git-ignored. Their hashes and reproducible training settings are recorded, but a fresh clone does not contain those binaries; only trusted locally generated model files should be loaded.

## Repository provenance

- Attack implementation and plan source: `604bac8ce7dd191a18e0981daa795563cbf2dd53`
- Anomaly/evaluation implementation and first partial-run source: `57478f0967d996f7f8764589070e5c8ed63dd396`
- Session-expiry and checkpoint recovery fix: `40da3a388983030b7b696ce7bf2b801e0ed6903f`
- Completed evaluation artifacts: `ab93d493a4b8db351be19b94e5ccf53426907996`
- Stable result-file line endings: `392314314aa19f4393db66772a33a96baff642b5`
