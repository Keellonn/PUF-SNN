# XR, Data, and SNN Design
**Owner:** Keegan Hoyne

## Purpose
This document describes my part of the project
- Quest 3 head motion logging
- Synthetic data
- Data validation and splits
- Conventional classifiers
- SNN classification
- Sensor abnormality detection
- Model and latency evaluation

The initial Unity Quest logger software prototype has been implemented. OpenXR and Meta Quest support are configured, and all nine core EditMode tests pass. Physical headset detection, Android deployment, and approved real-data collection are not complete. Until the approved data-collection workflow is confirmed, I'm using a synthetic generator that follows the same data format.

## Quest setup

If the lab doesn't require a different setup, our proposed tools are
- Unity 6.6 (6000.6.1f1)
- OpenXR Plugin 1.18.0
- Unity OpenXR: Meta 2.6.1
- Android Build Support
- ADB for installing and testing the app

Software development can continue on a personal computer using the approved repository and no human-derived data. Quest data collection and retention must wait until the institutional path and lab workflow are confirmed.

## Head tracking

The Unity logger finds the headset with
`UnityEngine.XR.InputDevices.GetDeviceAtXRNode(XRNode.Head)`

It collects
- CommonUsages.devicePosition
- CommonUsages.deviceRotation
- CommonUsages.isTracked
- CommonUsages.trackingState

The logger may use `Application.onBeforeRender` to collect the most recent pose once per rendered frame.
The callback should only collect data. It shouldn't write files or perform slow processing. Samples will be placed in a queue and saved afterward.
We'll record the application capture time for every sample. This isn't a trusted hardware timestamp.

## Position and orientation

The first logger will use Unity's device origin tracking space
- Positive x points right
- Positive y points up
- Positive z points forward
- Position is measured in meters

If the tracking origin changes during a trial, that trial will be restarted.
Source positions are stored in device-origin coordinates. After authentication, classifier preprocessing subtracts the first sample's position so room location is not a model feature.

Orientation will be stored as a quaternion
`x, y, z, w`

For every quaternion, the logger will
1. Reject a zero or invalid quaternion
2. Normalize it
3. Compare it with the previous quaternion
4. Flip its sign if their dot product is negative
5. Save the source quaternion; classifier preprocessing calculates first-pose-relative orientation after acceptance

The normalized, sign-continuous source quaternion is saved. The source data won't be converted to Euler angles.

## Windows and timing

Each action window will
- Last 2 seconds
- Target 60 samples per second
- Contain 120 samples after resampling
- Use the actual recorded timestamps
- Stay separate from other action windows

Position will use linear interpolation during resampling. Orientation will use quaternion SLERP.

A clean window will be rejected when
- A source timestamp gap is greater than 50 ms
- Less than 95% of its samples have valid tracking

We won't interpolate across a gap greater than 50 ms.
The 50 ms and 95% limits are starting values. We'll review them after seeing timing and tracking data from the real logger.

## Initial model input

The first model input has this shape
`[batch, 120, 7]`

The 7 channels are
1. Relative x position
2. Relative y position
3. Relative z position
4. Relative quaternion x
5. Relative quaternion y
6. Relative quaternion z
7. Relative quaternion w

Normalization is calculated using training data only.
Tracking validity remains authenticated metadata and is checked before classifier release, but it is not a model feature.

Possible later features include
- Velocity
- Angular velocity
- Acceleration
- Angular acceleration
- Summary statistics
- Delta encoding

These aren't required for the first baseline.

The conventional baselines and SNN use the same 7 pose channels per time step: 3 relative-position values and 4 relative-quaternion values. The conventional models flatten 120 time steps into 840 features, while the SNN preserves the 120-step sequence. Tracking validity and timestamps are authenticated and validated but aren't classifier features.

## Authenticated classifier boundary

The initial fixed-decimal authenticated-window interface and cross-language golden vector established the protected fields, quality boundary, and rejection-before-inference behavior. The final integration uses Will's Wire Protocol 2.0 binary implementation instead of the initial decimal JSON transport.

The final processed-record adapter converts a validated 120-sample record into an immutable binary window. The sender binds the authenticated device, session, and sequence values. The verifier releases only an accepted window through the existing class named `ExactlyOnceClassifierRelease`. Despite its name, the boundary provides at-most-once consumer invocation, not guaranteed callback completion. The verifier commits acceptance/sequence state before preprocessing; a rejected/duplicate result invokes no consumer, and a consumer failure leaves the event consumed without rolling authentication back.

Rejected, modified, malformed, replayed, low-quality, wrong-device, and wrong-session messages make zero classifier calls. Labels and split identifiers aren't included in the accepted classifier record.

## Dataset splits

The first experiment measures cross-session performance
- Session 1 is training data
- Session 2 is validation data
- Session 3 is final test data

Training data teaches the model.
Validation data helps us choose model settings and thresholds.
Test data is left untouched until the model choices are finished.
Every clean window and any changed copy of that window must stay in the same split.

The validator should catch
- One source trial appearing in multiple splits
- One session appearing in multiple splits
- Clean and changed copies being placed in different splits
- Duplicate windows across splits
- Normalization being fitted with validation or test data

Cross-device classifier generalization is not established by this fixed-profile cross-session split. Cross-device authentication-substitution tests are a separate security question.
Cross participant testing requires approved human data.

## Conventional classifiers

Models were implemented in this order
1. Logistic regression with standardized features
2. Random forest with 300 trees and one processing thread

The initial historical run used seed 2026; corrected conventional comparisons use seeds 7, 17, 27, 37 and 47. Logistic regression uses the lbfgs solver and a maximum of 5,000 iterations. Scaling is fitted on training data only.

Every model should use the same
- Source trials
- Splits
- Preprocessing
- Attack examples
- Random seeds

We'll report
- Accuracy
- Precision for each class
- Recall for each class
- F1 for each class
- Macro-F1
- Confusion matrix
- Inference time

## SNN classifier (initial historical run)

The first SNN baseline uses
- Input shape: `[batch, 120, 7]`
- Input method: normalized values at each time step
- Hidden layer: 64 recurrent LIF neurons
- Outputs: 5 motion classes
- LIF beta: 0.9
- Loss: cross-entropy
- Optimizer: Adam
- Learning rate: 0.001
- Batch size: 32
- Maximum training length: 50 epochs
- Early stopping: validation macro-F1 doesn't improve for 8 epochs
- Random seeds: 7, 17, and 27

The output membrane values are averaged across the 120 time steps to create the 5 class scores.

The three-seed baseline produced
- Mean validation macro-F1: 0.8557 ± 0.0033
- Mean test accuracy: 0.8550 ± 0.0036
- Mean test macro-F1: 0.8551 ± 0.0034
- Mean median inference time: 9.7660 ± 0.0278 ms
- Mean p95 inference time: 14.5208 ± 0.0338 ms

The best epochs were 20, 25, and 22. The SNN test macro-F1 was 4.81 percentage points below the corrected logistic-regression baseline, so it met the provisional maximum 5 point gap.

The latency values measure one already normalized window per CPU model call. They don't include authentication, preprocessing, audit persistence, loading, training, or the 2 second capture interval. They don't establish complete authenticated post-window latency.

This is a software SNN. We won't claim energy savings unless we measure them on comparable hardware.

## Separate abnormality detector

The motion classifier and abnormality detector have different jobs.

The motion classifier answers
> Which head movement occurred?

The abnormality detector answers
> Does this accepted sensor pattern look normal or suspicious?

For the first abnormality experiment
- `is_anomaly=false` means the clean window wasn't changed
- `is_anomaly=true` means one Tier-2 change was added before authentication

The completed first detector experiment is supervised because the synthetic program labels its defined transformations. It uses separate logistic-regression and random-forest models with 48 relative-motion/timing measurements, not the SNN classifier or its confidence. No SNN abnormality detector is added until conventional anomaly analysis and end-to-end timing are complete.

The detector will return
- A score between 0 and 1
- `normal` or `suspicious`

Each detector threshold was selected on Session 2 only under clean validation FPR <= 5%, then frozen before Session 3. The corresponding clean test FPR is 5.33% for LR and 2.94% for RF: satisfying validation does not guarantee the test target. The predeclared medium/high recall target remains 90%; both models miss it.

### Preventing trivial transform detection

- Source windows are assigned to train, validation, or test before transformations are created.
- Every transformed copy stays in its source window's split.
- Metadata identifying the transform is excluded from model inputs.
- Transform severity is varied within each split instead of using one fixed artifact.
- Source-specific attack draws vary across splits within the same declared ranges; this completed run is not evidence for an unseen attack family or disjoint held-out parameter range.
- Clean and transformed windows use the same serialization and preprocessing path.
- Results will be reported separately by transform type and severity.

## Tier 2 sensor changes

| Condition | Starting levels |
|---|---|
| Position noise | 0.5, 1, and 2 cm |
| Orientation noise | 0.5, 1, and 2 degrees |
| Position drift | 2, 5, and 10 cm |
| Orientation drift | 2, 5, and 10 degrees |
| Timestamp jitter | ±4, ±8, and ±16 ms |
| Dropped samples | 5%, 10%, and 20% |
| Frozen pose | 100, 250, and 500 ms |
| Position jump | 5, 10, and 20 cm |
| Orientation jump | 5, 10, and 20 degrees |

These are starting values. We'll compare them with real clean recordings before treating them as realistic physical attack levels.

## Main measurements

**Macro-F1:** Calculate F1 for each motion class and average the 5 results equally.
**Abnormality false positive rate:** The percentage of clean windows incorrectly called suspicious.
**Detection rate:** The percentage of changed windows correctly called suspicious.
**Inference latency:** Time from model input being ready to the model producing an output.
**Post window decision latency:** Time from the end of a 2 second window to the completed authentication, preprocessing, inference, and audit result.
**Authentication overhead:** The authenticated pipeline time minus the same pipeline without authentication.

For timing results, we'll report
- Number of measurements
- Median
- 95th percentile
- Results from multiple random seeds when practical

## Current synthetic motion generator

The current generator uses random seed 7 and creates
- 6 synthetic device groups
- 3 sessions per device
- 20 trials per class in each session
- 5 motion classes
- 1,800 windows
- 120 samples per window
- 216,000 total samples

The synthetic generator directly creates a fixed 60 Hz grid and doesn't perform resampling. The Quest logger separately implements linear position interpolation and quaternion SLERP for irregular captured poses.

Every class receives independent position and orientation variation. The current settings include position noise with a standard deviation of 0.003 meters, position drift with a standard deviation of 0.006 meters, 0.60 degree orientation noise, and 3 degree orientation drift. All tracking-valid values are true in the clean synthetic data.

The class patterns remain based on
- nod: an x-axis rotation with a -22 degree coefficient and vertical movement
- shake: a y-axis rotation with a 20 degree coefficient and side-to-side movement
- look_left_return: a y-axis turn reaching about -32 degrees and returning
- look_right_return: a y-axis turn reaching about 32 degrees and returning
- still: small nonzero position and orientation random walks

The corrected generator varies amplitude, motion duration, start delay, phase warp, peak timing, secondary-axis movement, return error, starting pose, noise, drift, and sway. It also applies separate synthetic device and session effects. Position and quaternion values are rounded to 8 decimal places.

The existing diagnostic found zero exact test-to-training orientation-feature and combined-feature matches. This is not itself a full raw-window duplicate proof. The Week 4 content-hash tests compare all split pairs and the physical nearest-neighbor analysis exposes near copies. The split still measures performance across synthetic session groups, not physical devices or people.

These parameters are provisional engineering assumptions. They aren't calibrated human or Quest motion distributions, and the current results shouldn't be treated as real-device or cross-person performance.


## Exact baseline methods and feedback evaluation

The data seed remains 7. Fixed session-index assignment has no split RNG. Model initialization seeds are 7, 17 and 27; the revised SNN training/shuffle seeds are 107, 117 and 127. Historical saved checkpoints used the same initialization/shuffle seed and remain unchanged. Separate-seed training produces a new named run, not a retroactive relabeling of those checkpoints.

For each window, positions are p[t] - p[0]. Quaternions are normalized and adjacent equivalent signs are made continuous; relative orientation is inverse(q[0]) multiplied by q[t] in xyzw order. LR StandardScaler learns a mean/SD for each of 840 flattened features from Session 1 only. SNN means/SDs use all Session-1 windows/time points separately for each of seven channels; zero-variance SD is replaced by one. RF does not scale. Angular velocity ablations use shortest quaternion increments converted to rotation vectors divided by actual timestamp intervals, with a zero first velocity. No classifier converts quaternions to Euler angles.

The SNN uses three Linear layers: input 7->64 with bias, recurrent 64->64 without bias, and readout 64->5 with bias. Recurrent connectivity is dense and learned, including diagonal connections. Hidden state starts at zero for every window. Each step computes u = 0.9*u + input_current + recurrent(previous_spikes), emits a hard spike for u >= 1, then subtracts one threshold using detached spikes. The backward surrogate is 1 / (1 + 25*abs(u-threshold))^2. Readout is a nonspiking membrane with the same 0.9 decay; its 120 scores are averaged and argmax selects the class.

Initialization is PyTorch nn.Linear's reset_parameters procedure: Kaiming-uniform weights with a=sqrt(5), and uniform biases bounded by 1/sqrt(fan_in). Cross-entropy is optimized by Adam at 0.001 with batches of 32 and gradient clipping at norm one. Maximum training is 50 epochs, with the best Session-2 macro-F1 checkpoint and patience eight. The 64-neuron model has 4,933 trainable parameters; the 32-neuron comparison has 1,445. LR has 4,205 coefficients/intercepts for the 840-feature five-class model. RF structure is reported as 300 trees and fitted node/leaf counts, not a misleading neural parameter equivalent.

The original forward timer starts after tensor construction/transfer. It includes the recurrent forward loop and temporal aggregation, but excludes normalization, tensor preparation, argmax/CPU decoding, authentication, audit, loading, training and capture. Timing batch size is one, independently of training batch size. The historical Week 4 pipeline timing includes the common binary32 conversion, relative preprocessing/normalization, tensor handling, decoding and real in-memory gate/audit work. Durable audit I/O, network transfer and session setup are excluded and explicitly listed. Session setup uses an explicit known-correct synthetic candidate; it does not measure PUF reconstruction reliability.

Full-window hashes include sample indexes, relative capture times, position, orientation, tracking state, window duration, sample rate and coordinate frame. IDs, labels, split assignment and absolute time origin cannot hide a copy. Near-neighbor distances use first-pose-relative position RMS in meters and sign-invariant quaternion geodesic RMS in degrees, with the same physical procedure before/after correction. The configured 1 mm/1 degree sensitivity thresholds are provisional, not human-calibrated definitions of leakage.

Feature ablations use conventional classifiers: unscaled raw-relative-pose LR, scaled quaternion-only LR, scaled quaternion+angular-velocity LR, and scaled position+quaternion LR, with matching RF controls. Raw relative pose and position+quaternion contain the same seven channels; their distinction is a scaling control for LR, not a different RF representation. SNN input remains seven pose channels.

Stress tests are fixed paired transformations, not new independent recordings. Relative starting-orientation invariance is reported separately. Amplitude transforms scale the observed trajectory including noise; timing transforms clamp endpoints. The targeted nod sweep instead changes intentional nod rotation/position coefficients and duration range in the generator while retaining noise, drift, sway and return error. Report realized motion statistics because duration clipping can limit requested speed changes. Nominal low-amplitude nod labels become ambiguous near still; no physical realism is inferred.

The one architecture ablation compares 32 and 64 neurons with otherwise identical configurations and separated seed roles. Any selection uses validation macro-F1 only. Test comparisons do not trigger further tuning. Per-seed and pooled metrics/curves are derived from saved counts/history; pooled predictions reuse the same test windows and are not independent recordings.

The historical initial SNN run had macro-F1 0.8551 and met the provisional five-point gap. The separately seeded 64-neuron follow-up has macro-F1 0.8500 and a 5.32-point gap to LR, so it misses that criterion. The validation-selected 32-neuron ablation has macro-F1 0.8619 and a 4.12-point gap, so it meets the criterion. Neither SNN outperforms LR or RF. The 64-neuron model remains the reference baseline and the 32-neuron result remains the predefined architecture ablation.

The matched accepted pipeline benchmark uses the 64-neuron SNN. Its authenticated p95 range is 18.324-18.737 ms across three seeds, while authenticated LR is 10.894-11.099 ms and authenticated RF is 23.831-24.234 ms. Maximum authenticated times exceed 20 ms in every condition, including 335.650 ms for SNN, 354.627 ms for LR and 387.297 ms for RF. Slow observations occur inside the adapter timing boundary; their cause is not established. The accepted-window p95 measurements are not hard real-time guarantees. The bad-tag receiver path has p95 0.9814 ms over 600 timing repetitions and makes zero classifier calls without advancing sequence state.

The saved full Python suite passed 322 tests. The reviewed Unity screenshot records 15 passing EditMode tests, including actual final binary-writer execution. Supplemental .NET positive checks and the five controlled C# negative vectors are separate evidence, not a formal attack-rate study.

No measured energy advantage, physical Quest performance, cross-person result or cross-device classifier generalization is established. Reconstruction reliability, independent credential verification and full session setup costs are not established by the recurring-window pipeline benchmark.


## Week 5 revision: exact nearest-training metrics

On the existing fixed grid, align each query sample index t with training sample t after removing the absolute timestamp origin. There is no resampling, dynamic time warping, phase/time-shift search or learned alignment in this audit. Quaternions are unit-normalized/sign-continuous and made first-pose-relative before computing the physical orientation distance; learned statistical normalization and Wire binary32 conversion have not yet occurred.

```text
q_rel[t] = inverse(q[0]) * q[t]          # xyzw; renormalize before dot
theta[t] = (180/pi)*2*acos(clip(abs(dot(q_rel_query[t],q_rel_train[t])),0,1))
d_orientation = sqrt(mean_t(theta[t]^2))
```

This is geodesic rotation RMS in degrees, not mean/max rotation. For the complete seven-channel sequence, fit per-channel means/population SDs across Session-1 windows/time points only (SD <= 1e-12 becomes one), apply the existing float32 SNN input normalization, then promote to float64 for distance accumulation:

```text
z[t,c] = float32((x_rel[t,c] - training_mean[c]) / training_sd[c])
d_sequence = sqrt(mean_over_all_840_coordinates((z_query - z_train)^2))
```

The complete metric is dimensionless and uses SNN channel scaling, not LR's 840-feature scaler or a quaternion-geodesic substitute. Any-label search uses all 600 training windows; same-label search is descriptive stratification over 120 references, not a model feature. Equal-distance ties choose the first sorted training ID; no held-out near/far cutoff is tuned.

The new audit queried 600 validation and 600 test windows and saved both scopes (2,400 rows). All 1,200 historical corrected test/orientation rows reconciled within 1e-5 degrees. Test any-label orientation RMS minimum/median is 2.509239/6.425321 degrees; the retained original dataset had zero minimum/median. Complete normalized-sequence RMS minimum/median/p95 is 0.481008/0.712748/0.977175 for validation and 0.517395/0.710372/1.100239 for test. Full per-class distributions, scaler/source lists and formulas are in `results/week-5/keegan/sequence-neighbors/`. Nonzero distance does not establish physical transfer or prove all leakage absent.

## Week 5 revision: frozen model reporting and selection

`results/week-5/keegan/model-evidence/` reconciles 16 existing model records into 32 validation/test confusion matrices and 160 per-class rows: five conventional seed labels per family and three separated seed pairs per SNN width. Both SNN widths have all-three-seed training-loss/validation-score figures and six verified best/stopping-epoch decisions. Historical training did not save validation loss or training accuracy; those measurements are not invented.

SNN-64 selected/stopping epochs are 11/19, 26/34 and 30/38; SNN-32 uses 23/31, 31/39 and 33/41. These correspond to initialization seeds 7/17/27 and training/shuffle seeds 107/117/127. Every run stopped after eight consecutive epochs without a validation macro-F1 improvement > 1e-12, restoring the selected best state. The exact LIF recurrence/surrogate/subtractive-reset/readout equations and optimizer settings match the frozen code/configurations.

Storage measurements retain all six existing SNN checkpoints (22,981 bytes each for SNN-64; 9,029 each for SNN-32; normalization sidecars separate). The original conventional binaries were not retained, so two explicit seed-7 storage refits use the unchanged recipes and must exactly reproduce saved validation/test confusion counts and fitted complexity before serialization. LR is 55,441 bytes including its scaler; RF is 4,019,633 bytes with 300 trees, 37,410 nodes and 18,855 leaves. Those local joblib files are Git-ignored; hashes/settings are recorded. Different formats/metadata mean these are file-size measurements, not runtime-memory, energy or neuromorphic-efficiency evidence.

Data seed 7 fixes one synthetic dataset; fixed session-index splits have no RNG. Model fitting never regenerates that dataset. LR lbfgs is deterministic here, so its five random_state labels do not represent independent stochastic performance samples and zero descriptive SD is expected. RF seeds affect fitting; SNN initialization/shuffle roles are separate. Model seed repeats still share the same query sources.

Keep the finite 32/64 comparison and all detector thresholds frozen. Any authorized later change must predeclare its question, candidates, data and seed roles, fit on Session 1, select on mean Session-2 macro-F1 with the smaller model as tie-break, and not revise choices using Session 3. Previously inspected Session 3 cannot become a fresh holdout for open-ended future tuning. No SNN architecture expansion is performed before the end-to-end authentication experiment.

The constrained conclusion is: SNN-32 is a viable temporal-inference baseline within the predeclared tolerance, but conventional models remain more accurate in this synthetic CPU evaluation. SNN-64 misses the tolerance and remains the frozen Tier-2 reference. A future SNN motivation requires an independently demonstrated systems, temporal-robustness or neuromorphic-hardware advantage.

## Week 5 revision: ambiguity and Tier-2 outcome reporting

The fixed nod sweep now reports conventional and SNN sensitivity alongside frozen LR/RF anomaly flags in `results/week-5/keegan/nod-diagnostics/`. A nominal nod uses -22 degrees x rotation and 0.006 m vertical coefficient; half uses -11/0.003 and one-tenth -2.2/0.0006. Noise/drift/sway stay fixed, so nominal scaling does not specify the observed peak. Speed changes duration bounds subject to existing group effects/clipping, not capture timestamps.

Interpret low-amplitude nods as legitimate execution variation and intended-class ambiguity in this diagnostic, not automatically as an adversarial success. At one-tenth amplitude/nominal speed, LR/RF/SNN-64 nod recall is 23.33%/13.61%/6.94%, with still confusion 71.67%/85.00%/90.00%; frozen LR/RF anomaly flag frequency is 4.17%/3.06%. The historical classifier sweep stores aggregates, so no joint per-case 'still AND flagged' count is claimed. Paired examples, observed units/statistics and descriptive intervals are retained.

The separate Tier-2 breakdown retains all 5,501 pre-tag failures (3,493 source gaps above 50 ms; 2,008 non-increasing timestamps), per-type/severity detector detected/missed counts and paired motion degradation. It does not count quality/construction blocks as detector successes. Frozen thresholds are selected from validation only; both detectors miss 90% medium/high recall and LR exceeds 5% held-out clean FPR. Synthetic freeze cues and shared parameter ranges remain limitations.

All new addenda preserve the original leakage reports and historical experiment artifacts. The original known-correct-candidate authenticated stream run predates the current pre-HKDF/local-admission gate; retrospective reporting does not validate fresh v2 sessions. The separate Week 6 connector, frozen-model smoke and first instrumented timing run now exercise actual one-read/one-decode v2 admission without changing those historical results. Will's expanded Tier-1 and standalone reconstruction-alternatives reports and actual v2 specification are now present. Baseline reconciliation, fresh majority-3/correlated-noise integration, a provisioned-credential control, shared formal evidence closure and durable audit performance remain separate/shared work. GC/observer controls and bounded Windows accounting are now recorded; complete causal isolation remains unresolved. Human recording stays disabled until approval.

## Week 6: frozen composite inference and timing

The frozen bundle verifies five motion models (the recorded seed-7 LR/RF storage refits and SNN-32 seeds 7/17/27) and six anomaly detectors (LR/RF seeds 6007/6017/6027). Manifest, dataset, normalization and threshold checks precede deserialization. No model is regenerated, refitted or selected by the Week 6 runners. The smoke exercises all 11 models; timing executes one motion model and one detector per accepted callback, with detector seed 6007 fixed in advance.

Current v2 admission uses the candidate returned by one actual reconstruction, followed by independent verification/local authorization and HKDF/mutual confirmation. A successfully authenticated window is released at most once to one composite consumer. Refusals invoke neither preprocessing nor either model; consumer exceptions leave the event consumed and sequence committed. The 30-attempt smoke validates this boundary, not accuracy, anomaly recall or reconstruction FRR.

The first instrumented timing run retains 20 validation warmups and 600 test-source single-read attempts for each of six paired conditions. Each measured condition has 599 admitted sessions and one reconstruction refusal; the repeated refusal is paired, not six independent failures. Direct recurring motion-plus-anomaly p95 is 27.7629 ms (LR/LR), 30.3028 ms (LR/RF), 52.8523 ms (RF/RF) and 51.3985/50.5355/54.1160 ms (SNN-32 seeds 7/17/27 with RF). First and after-refusal complete post-window p95 also exceed 20 ms. These results cannot be replaced by historical motion-only timings or used to infer an SNN hardware/energy advantage.

The saved-run addendum reconciles 29,718 root traces, 12,621 retained slow/tail observations and every root-group maximum. The largest measured root per condition has 90.30-92.33% recorded GC overlap; this is observed activity, not a complete causal explanation. The later paired controls support a collector/retention contribution and scoped Windows accounting measures ready delays; allocation/cache/power causes and all residuals are not fully isolated. Nested durations overlap; component percentiles are not added. Capture, hardware acquisition, network and durable audit are excluded.

Exact commands, seed roles, hardware/timer conditions and artifact/commit pointers are in `results/week-6/keegan/keegan.md` and `docs/week6-end-to-end.md`. Keep architectures, preprocessing and thresholds frozen; these first timing results do not authorize a new architecture search or SNN anomaly detector.

### Recorded observer controls and Windows follow-up

The separate `observer-experiment/` result compares four predefined observer/GC
modes across four paired noise blocks and six frozen conditions: 8,640 admissions
and 68,952 roots, plus 20 explicit full-GC metadata probes. GC-deferred cleanup
is recorded outside window timers and the normal policy is restored; disabling
GC is not a deployment recommendation or a replacement target result.

The public `windows-os-evidence/` report retains all 4,320 traced roots,
2,106 slow/tail/maxima details, 144 groups and eight roots over 100 ms. Four large
pauses have about 90–98% GC overlap; a different 142.4030 ms case has 56.1910 ms
ready delay but only 0.3193 ms GC. The 3,735.7236 ms first-use case spends
3,690.2300 ms in reconstruction, without isolating its remaining initialization
cause. Tracing order/overhead, allocation/cache/power effects and dependency waits
remain unresolved. No model training, threshold change, SNN architecture/anomaly
expansion, revised p95 claim or new held-out accuracy estimate occurred.

Methods, decoder limits and privacy rules are in
`docs/week6-outlier-diagnostics.md` and `docs/week6-windows-os-evidence.md`.
The raw trace and failed/recovered decoding evidence remain private; the public
completion marker confirms filtered export, not complete causal attribution.



## October 8 consolidation: source dependence and one bounded optimization

The [source-aware Tier-2 addendum](../results/week-6/keegan/tier2-source-uncertainty/tier2-source-uncertainty.md) retains the original points and frozen thresholds while resampling each held-out source jointly with its clean and altered derivatives across all fitted seeds. The 2,000 stratified draws over 600 sources are conditional on fixed device/class composition and the held-out synthetic session; they do not estimate new-person/device/session generalization.

Motion classification decides intended motion; an anomaly alert indicates a defined abnormal-stream condition. A misclassified small legitimate nod can trigger a wrong motion action without warranting an anomaly alert. Neither low-amplitude ambiguity nor authentication correctness should be substituted for anomaly recall. Neither SNN outperforms the conventional baselines, and anomaly recall targets remain unmet.

[Original stage accounting](../results/week-6/keegan/stage-accounting/stage-accounting.md) identified repeated exact quaternion-quality arithmetic as one shared application cost. [The matched comparison](../results/week-6/keegan/quality-benchmark/quality-benchmark.md) changes that arithmetic only, using exact dyadic integers while preserving binary32 bounds/continuity and authenticated state policy. No motion/anomaly fitting or model search occurred.

Opt-in LR/LR recurring p95 is 14.2551/15.3827 ms in two bounded blocks, but fresh p95 remains 22.2278/23.4115 ms. LR/RF recurring is 25.0066/28.9934 ms and SNN-32 seed-7/RF is 32.1141/40.8279 ms. The default v2 remains unchanged. Reduced quality cost does not remove forest/SNN inference cost or establish a hardware/energy advantage.

Reported totals include timing observers and in-memory audit, while excluding physical acquisition, the additional two-second recording window, network and durable storage. GC remains enabled; cleanup, sustained capacity and coarse resource behavior are reported separately. Historical motion-only timings belong in comparison/appendix material, never as evidence that the complete default architecture meets 20 ms.

The [feedback/status/claim tables](week6-feedback-consolidation.md), [evaluation draft](paper-evaluation-draft.md) and [release index](week6-release-evidence.md) are the current reporting entry points. Logger validation remains pending explicit faculty/lab/institutional decisions; no human recording or real-Quest transfer claim is added.
