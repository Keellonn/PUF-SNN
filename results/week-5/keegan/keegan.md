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

## Week 5 feedback revision — October 4, 2026

The sections above preserve the original completed run. This revision adds reconciled reporting, question-driven nod/still diagnostics and a complete-input similarity audit. It does not repeat the historical authenticated stream evaluation, train either SNN, change the nine attacks or lower anomaly thresholds after test inspection.

### Complete construction and attack accounting

All 50,400 plan rows reconcile with 44,899 quality-valid cases and 5,501 construction failures: 3,493 source gaps above 50 ms and 2,008 non-increasing source timestamps. Final post-construction canonical/quality failures = 0. In test, 14,956 accepted deliveries plus 1,844 pre-tag blocks reconcile to all 16,800 planned cases; those blocks are 1,160 gap failures and 684 timestamp-order failures.

`construction_failure` means source reconstruction/interpolation produced no processed 120-sample window under the existing policy. It is not a verifier rejection, detector true positive or silently dropped case. The detector/classifier analyses remain conditional on quality-valid cases. High timestamp jitter has zero eligible windows (N/A detection rate); high dropout has four, so its apparent all-pass detection rate is based on a very small cohort.

`tier2-breakdown/` records all three splits, every attack/severity, stage/reason counts, per-seed detector detected/missed counts, clean FPR and calibration, paired accuracy/macro-F1 degradation, per-class metrics and complete confusion matrices. Condition-specific clean comparisons use the same eligible source subset. Detector recall/FPR has fixed-model 95% Clopper-Pearson intervals; paired accuracy-loss intervals use 400 source-paired bootstrap resamples with seed 7017. Shared device/session profiles and repeated seeds limit independence; these are conditional descriptive intervals.

The original LR/RF anomaly F1 remains 0.8424/0.9003, clean FPR 5.33%/2.94%, and medium/high recall 82.85%/87.95%. Neither reaches the unchanged 90% recall target; LR also exceeds 5% clean test FPR. Session-2 thresholds remain frozen. Metadata exclusion, split-preserving pairing and equal canonical/preprocessing paths reduce explicit cues, but freeze repeats and synthetic regularities remain possible shortcuts. This is not an unseen attack-family/parameter-range or physical robustness evaluation.

### Nod/still ambiguity and anomaly response

`nod-diagnostics/` reuses 270 saved conventional/SNN motion-condition rows from the existing amplitude/speed grid and adds 192 frozen-detector condition rows with 3,840 per-source anomaly predictions. Zero cases were blocked at the pre-tag quality check. No classifier inference, authentication, anomaly training or threshold selection was executed in this addendum; the six existing detector models were scored unchanged.

Nominal nod coefficients are -22 degrees about x and 0.006 m vertically. Half amplitude uses -11 degrees/0.003 m; one-tenth uses -2.2 degrees/0.0006 m. Trial/group shaping, noise, drift, sway and return error remain, so those coefficients are not observed peak amplitudes. Speed scales duration bounds with the generator's existing clipping. Observed peak rotation/angular-speed statistics and paired representative trajectories are saved separately.

| Test, nominal speed | LR | RF | SNN-64 |
|---|---:|---:|---:|
| Nod recall at nominal amplitude | 92.50% | 83.61% | 84.44% |
| Nod recall at one-tenth amplitude | 23.33% | 13.61% | 6.94% |
| Still confusion at one-tenth amplitude | 71.67% | 85.00% | 90.00% |

At one-tenth amplitude, the frozen LR/RF anomaly flag frequencies are 4.17%/3.06%. These are legitimate execution variations and increasingly ambiguous intended labels in this experiment: detector flags are false alarms under that interpretation, not attack recall. Similar attenuation could be adversarial in another scenario, but intent is not observed here. Separate marginal summaries do not establish a joint 'predicted still AND flagged' count.

### Exact nearest-training orientation and complete-input audit

`sequence-neighbors/` compares 600 validation and 600 test queries to Session-1 references only, saving any-label and same-label searches (2,400 rows). All 1,200 historical corrected test/orientation rows reconcile. It trains no model, uses no RNG and selects no distance threshold.

Aligned sample indices use the existing 120-point grid without DTW, interpolation or phase search. After unit/sign normalization and first-pose-relative quaternions, per-time rotation distance is `2*acos(abs(dot(q_query,q_train)))` converted to degrees; the window distance is RMS across 120 angles, before learned statistical scaling and Wire binary32 conversion. This is neither average angle nor maximum angle.

The complete 120 x 7 input distance is RMS over all 840 normalized coordinates using Session-1-only seven-channel means/population SDs (near-zero SD becomes one), the existing float32 SNN input, and float64 accumulation. It is dimensionless and differs from geodesic rotation distance and LR's per-flattened-feature scaling.

| Corrected any-label query metric | Minimum | Median | p95 |
|---|---:|---:|---:|
| Validation complete-input RMS | 0.481008 | 0.712748 | 0.977175 |
| Test complete-input RMS | 0.517395 | 0.710372 | 1.100239 |
| Test orientation RMS (degrees) | 2.509239 | 6.425321 | 11.773732 |

The original zero minimum/median orientation distances and leakage result remain preserved. Nonzero corrected distances are a similarity diagnostic, not proof of real-world generalization or universal absence of leakage.

### Frozen per-class/per-seed model evidence

`model-evidence/` packages 16 historical model records, 160 validation/test per-class rows, 32 complete confusion matrices, all-three-seed curves for each SNN width and six reconciled checkpoint/stopping decisions. Historical curves contain training cross-entropy and validation accuracy/macro-F1; missing validation loss/training accuracy is not invented.

| Model | Mean test macro-F1 | Learned coefficients/parameters | Seed-7 model-file bytes |
|---|---:|---:|---:|
| Logistic regression | 0.9032 | 4,205 | 55,441 |
| Random forest | 0.8936 | Tree structure, not a neural count | 4,019,633 |
| SNN-64 | 0.8500 | 4,933 | 22,981 |
| SNN-32 | 0.8619 | 1,445 | 9,029 |

RF seed 7 has 300 trees, 37,410 nodes and 18,855 leaves. The six SNN checkpoint files are original hash-verified artifacts; scaler sidecars are separate. The conventional binaries are explicit new seed-7 storage refits, with frozen validation/test confusion counts and fitted complexity reproduced exactly before writing uncompressed protocol-5 joblib files. They are Git-ignored, with hashes/sizes in the manifest. Different artifact formats/metadata mean these sizes do not establish runtime memory, energy or hardware advantage.

Initialization seeds 7/17/27 pair with training seeds 107/117/127. SNN-64 best/stopping epochs are 11/19, 26/34, 30/38; SNN-32 uses 23/31, 31/39, 33/41. All stopped after eight consecutive epochs without a validation macro-F1 improvement > 1e-12. Exact LIF beta 0.9, threshold 1, slope-25 surrogate, subtractive detached-spike reset, dense recurrence and mean nonspiking readout equations are documented in the addendum.

Generation seed 7 fixes one dataset; session-index splits have no RNG. Deterministic LR lbfgs fitting makes its five random_state labels identical descriptive repeats, not independent random performance samples. RF fitting and SNN initialization/shuffling vary separately from data generation. All model runs reuse the same source queries.

SNN-64 misses the five-point LR-gap tolerance (5.32 points); the predefined validation-selected SNN-32 meets it (4.12 points), but neither beats the conventional models. The compact SNN is a viable temporal baseline within tolerance, not demonstrated superiority. Any later motivation requires an independently measured systems, temporal-robustness or neuromorphic advantage. SNN-64 remains the historical Tier-2 reference.

The current candidates and detector thresholds remain frozen. Any later authorized change requires a predeclared question/finite candidates, Session-1 fitting and Session-2-only selection; previously inspected Session 3 is not a new untouched holdout for an open-ended search. No SNN architecture expansion occurs before the end-to-end authentication experiment.

### Validation, evidence and remaining shared work

The new reporting suites passed 27 Tier-2, 22 nod, 25 sequence-neighbor and 28 model-reporting tests. The latest full Python suite passed 565 tests; those targeted tests are included, not additional independent totals. Completion markers, historical inputs and generated artifact hashes were checked. Result-folder line-ending rules preserve byte hashes across checkouts.

Permanent method updates are in `docs/tier2-stream-attacks.md`, `docs/xr-snn-design.md` and `docs/project-specification.md`; `docs/paper-outline.md` organizes the bounded claim, evaluation questions and existing evidence. These revision files do not establish new measurements.

Will's current credential-verification report records rejection of all 430 saved valid-format wrong candidates before request/HKDF and 120 passing positive integration controls. That integrity result does not repair nominal reconstruction FRR of 1.625%. His preserved Tier-1 run reports 0 accepted attacks in 100 trials per primary type and 100 accepted legitimate controls, not universal rejection or the requested expanded 1,000-trial evaluation.

The historical authenticated stream run predates that admission change. Fresh noisy-response -> reconstruction -> verification/admission -> HKDF/confirmation -> first-window/model/audit timing remains outstanding, as do the expanded varied Tier-1 study, formal v2 trust/key details and controlled reliability alternatives. Detector-inclusive/durable-audit timing and large-outlier causes are not established. All classifier/detector conclusions remain cross-session synthetic fixed-profile results; no human motion or physical Quest data was collected.

### Revision provenance

| Revision | Implementation/test-evidence commit | Generated-evidence commit |
|---|---|---|
| Tier-2 accounting | `4e9f3930e35644c09868432938d65c41717987b7` | `1f1ba4d1c1402e656baceec94e47432c5b12ee03` |
| Nod/still diagnostics | `be316a415f0df9dff694e12a91c4e70b0477e52d` | `2e81255d9ac30ae296dbcb933df2ecd0d5fcc3a3` |
| Complete-sequence audit | `3f143cdc070e6af60e592eb73a407f9793d6b854` | `03137092af81091184cf93b9b4722360188a34e4` |
| Frozen model reporting | `833a6e8d139bd694cc9ecc2760cb6008a1ad8823` | `57ecf399b685b92d19156278f96104cf3d32a363` |

Commands, configurations, historical/source hashes, seed roles, environment and figures remain in each addendum's manifest/settings files. The source dataset is unchanged: `752b009588f3e721a8bf2f8f8fcd1cdf0f7e998446b60953dd34dd5e9e54d661`.
