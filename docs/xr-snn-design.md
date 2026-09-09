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

The physical Quest logger hasn't been built yet. Until headset access is approved, I'm using a synthetic generator that follows the same planned data format.

## Quest setup

If the lab doesn't require a different setup, our proposed tools are
- Unity 6.0 LTS
- OpenXR Plugin 1.16.1
- Meta Quest OpenXR features
- Android Build Support
- ADB for installing and testing the app

Before installing anything on a lab computer or headset, we need confirmation from faculty or the lab administrator.

## Head tracking

The Unity logger will find the headset with
`UnityEngine.XR.InputDevices.GetDeviceAtXRNode(XRNode.Head)`

It will collect
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
Position will be stored relative to the first valid pose in the trial. This helps prevent the headset's location in the room from becoming part of the movement classification.

Orientation will be stored as a quaternion
`x, y, z, w`

For every quaternion, the logger will
1. Reject a zero or invalid quaternion
2. Normalize it
3. Compare it with the previous quaternion
4. Flip its sign if their dot product is negative
5. Calculate orientation relative to the first valid orientation in the trial

The original normalized quaternion will also be saved. The source data won't be converted to Euler angles.

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

The first model input will have this shape
`[batch, 120, 8]`

The 8 channels are
1. Relative x position
2. Relative y position
3. Relative z position
4. Relative quaternion x
5. Relative quaternion y
6. Relative quaternion z
7. Relative quaternion w
8. Tracking-valid value

Normalization will be calculated using training data only.

Possible later features include
- Velocity
- Angular velocity
- Acceleration
- Angular acceleration
- Summary statistics
- Delta encoding

These aren't required for the first baseline.

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

Models will be implemented in this order
1. Logistic regression
2. Random forest with 300 trees
3. LightGBM, if the first two are working

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

The first SNN plan is
- Input shape: `[batch, 120, 8]`
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

The output membrane values will be averaged across the 120 time steps to create the 5 class scores.

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