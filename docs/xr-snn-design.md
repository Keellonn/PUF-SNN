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

The final processed-record adapter converts a validated 120-sample record into an immutable binary window. The sender binds the authenticated device, session, and sequence values. The verifier releases only an accepted window through `ExactlyOnceClassifierRelease`.

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

Cross device testing is a secondary experiment. It won't represent physical headset differences until we have approved data from multiple real devices.
Cross participant testing requires approved human data.

## Conventional classifiers

Models were implemented in this order
1. Logistic regression with standardized features
2. Random forest with 300 trees and one processing thread
3. LightGBM, if the first two are working

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

## SNN classifier

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

The first detector will be supervised because the synthetic program tells us which windows were changed.
We'll start with logistic regression and random forest. A separate SNN abnormality detector comes later.
Motion classification confidence won't automatically be used as an abnormality score.

The detector will return
- A score between 0 and 1
- `normal` or `suspicious`

The threshold will be selected with validation data. The starting goal is no more than 5% of clean windows being incorrectly called suspicious.

### Preventing trivial transform detection

- Source windows are assigned to train, validation, or test before transformations are created.
- Every transformed copy stays in its source window's split.
- Metadata identifying the transform is excluded from model inputs.
- Transform severity is varied within each split instead of using one fixed artifact.
- Final tests should include parameter values or combinations not used for training.
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

The original forward timer starts after tensor construction/transfer. It includes the recurrent forward loop and temporal aggregation, but excludes normalization, tensor preparation, argmax/CPU decoding, authentication, audit, loading, training and capture. Timing batch size is one, independently of training batch size. New pipeline timing includes the common binary32 conversion, relative preprocessing/normalization, tensor handling, decoding and real in-memory gate/audit work. Durable audit I/O, network transfer and session setup are excluded and explicitly listed. Session setup uses an explicit known-correct synthetic candidate; it does not measure PUF reconstruction reliability.

Full-window hashes include sample indexes, relative capture times, position, orientation, tracking state, window duration, sample rate and coordinate frame. IDs, labels, split assignment and absolute time origin cannot hide a copy. Near-neighbor distances use first-pose-relative position RMS in meters and sign-invariant quaternion geodesic RMS in degrees, with the same physical procedure before/after correction. The configured 1 mm/1 degree sensitivity thresholds are provisional, not human-calibrated definitions of leakage.

Feature ablations use conventional classifiers: unscaled raw-relative-pose LR, scaled quaternion-only LR, scaled quaternion+angular-velocity LR, and scaled position+quaternion LR, with matching RF controls. Raw relative pose and position+quaternion contain the same seven channels; their distinction is a scaling control for LR, not a different RF representation. SNN input remains seven pose channels.

Stress tests are fixed paired transformations, not new independent recordings. Relative starting-orientation invariance is reported separately. Amplitude transforms scale the observed trajectory including noise; timing transforms clamp endpoints. The targeted nod sweep instead changes intentional nod rotation/position coefficients and duration range in the generator while retaining noise, drift, sway and return error. Report realized motion statistics because duration clipping can limit requested speed changes. Nominal low-amplitude nod labels become ambiguous near still; no physical realism is inferred.

The one architecture ablation compares 32 and 64 neurons with otherwise identical configurations and separated seed roles. Any selection uses validation macro-F1 only. Test comparisons do not trigger further tuning. Per-seed and pooled metrics/curves are derived from saved counts/history; pooled predictions reuse the same test windows and are not independent recordings.

The historical initial SNN run had macro-F1 0.8551 and met the provisional five-point gap. The separately seeded 64-neuron follow-up has macro-F1 0.8500 and a 5.32-point gap to LR, so it misses that criterion. The validation-selected 32-neuron ablation has macro-F1 0.8619 and a 4.12-point gap, so it meets the criterion. Neither SNN outperforms LR or RF. The 64-neuron model remains the reference baseline and the 32-neuron result remains the predefined architecture ablation.

The matched accepted pipeline benchmark uses the 64-neuron SNN. Its authenticated p95 range is 18.324-18.737 ms across three seeds, while authenticated LR is 10.894-11.099 ms and authenticated RF is 23.831-24.234 ms. Maximum authenticated times exceed 20 ms in every condition, including 335.650 ms for SNN, 354.627 ms for LR and 387.297 ms for RF. Slow observations occur inside the adapter timing boundary; their cause is not established. The accepted-window p95 measurements are not hard real-time guarantees. The bad-tag receiver path has p95 0.9814 ms over 600 timing repetitions and makes zero classifier calls without advancing sequence state.

The saved full Python suite passed 322 tests. The reviewed Unity screenshot records 15 passing EditMode tests, including actual final binary-writer execution. Supplemental .NET positive checks and the five controlled C# negative vectors are separate evidence, not a formal attack-rate study.

No measured energy advantage, physical Quest performance, cross-person result or cross-device classifier generalization is established. Reconstruction reliability, independent credential verification and full session setup costs are not established by the recurring-window pipeline benchmark.

