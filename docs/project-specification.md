# SNN + PUF Research Specification

**Researchers:** Keegan Hoyne and Will Wallace  

## Research question

Can a software prototype using a simulated noisy PUF-derived session credential reject replayed, modified, or misattributed Quest 3 head-motion windows before SNN inference while meeting defined targets for attack rejection, macro-F1 loss, and processing latency?

## Project goal

Quest applications continuously process motion data. An attacker could replay old data, change it after collection, claim it came from another device or session, or create unusual motion before the data is authenticated.

Our prototype separates these problems
- PUF-derived credential reconstruction recovers stable credential material from a noisy simulated response.
- Session establishment/authentication uses that credential to establish a session and its key.
- Per-window integrity/authenticity verification checks the protected message and its tag.
- Replay/freshness/order checking uses verifier-side session and sequence state.
- Motion classification identifies which head movement occurred.
- A separate anomaly detector checks accepted windows for suspicious sensor behavior.

We will evaluate how these parts work separately and together. Based on our targeted review so far, we have not found a study that evaluates this exact combination of simulated PUF-based credentials, authenticated XR motion windows, SNN inference, anomaly detection, replay and substitution attacks, and per-stage latency in one reproducible experiment.

This is a software prototype and reproducible pilot framework, not yet a demonstrated publishable result. We are not claiming that the Quest 3 gives us access to a physical PUF.

## Initial scope

The pilot will use
- Quest 3 head position and quaternion orientation
- Application capture time and headset tracking validity
- Five head-motion classes
- Fixed, nonoverlapping 2-second windows
- A target rate of 60 Hz, giving 120 samples per window
- Logistic regression and random forest before the SNN
- A separate supervised anomaly detector
- A simulated noisy PUF and software authentication layer
- Synthetic or approved scripted data until the human-subjects path is confirmed

We select head motion as the initial task because it provides a compact temporal signal suitable for validating the authenticated pipeline. Hand-joint tracking will be considered after end-to-end integration is stable.

## Head-motion task

The five classes are:

- nod: nod once and return to the starting pose
- shake: shake left and right once and return
- look_left_return: turn left once and return
- look_right_return: turn right once and return
- still: face forward without intentional movement for 2 seconds

Small natural movement is allowed during still. It is a recorded class, not the rest period between trials.

Each trial uses
1. A 1 second action prompt
2. A 2 second recording period
3. A 1 second rest period

Each trial produces one uniquely identified model window. The 1,800 windows are not claimed to be statistically independent because windows share class definitions and device/session grouping assumptions.

## Quest logging and preprocessing

The planned logger uses Unity 6 LTS, OpenXR, and Android Build Support unless the lab already requires another supported setup.

Head tracking will come from Unity's XR input system
- CommonUsages.devicePosition
- CommonUsages.deviceRotation
- CommonUsages.isTracked
- CommonUsages.trackingState

The logger will store actual application capture times instead of assuming that every sample arrives exactly at 60 Hz.

Position and orientation will be relative to the first valid pose in each trial. Position will use Unity device-origin coordinates in meters, where x is right, y is up, and z is forward.

Quaternions will be normalized. If two consecutive quaternions have a negative dot product, the newer quaternion will be flipped to avoid a false jump between `q` and `-q`.

Each captured Quest window will be resampled to 120 points
- Linear interpolation for position
- SLERP for quaternion orientation
- No interpolation across a timestamp gap greater than 50 ms
- At least 95% valid tracking for a clean window

The current synthetic generator directly constructs 120 samples on a fixed grid; it does not perform or validate resampling. The 50 ms gap and 95% tracking limits are starting values. We will check them against real logger behavior before treating them as final.

## Data format and split

Each window includes
- Internal schema version and window ID
- Source-trial ID
- Pseudonymous device ID
- Session and trial IDs
- Dataset split
- Increasing sequence number
- Ground-truth motion label
- Coordinate frame and target sample rate
- Window start and end times
- 120 ordered sensor samples

Each sample includes its index, capture time, head position, quaternion orientation, and tracking-valid value.

The complete machine readable format is stored in schemas/quest-window.schema.json. The filename is unversioned, but each record retains schema_version for compatibility and reproducibility. This is the motion-data schema, not the complete authenticated-message interface; that shared interface will also define protocol version, serialization, tag, and verifier-generated audit fields.

The scripted pilot will create
- 6 simulated device profiles
- 3 sessions per device
- 20 trials per class in each session
- 5 classes
- 1,800 synthetic windows across six device profiles and 18 device-session groups.

In the current generator, device profiles are grouping identifiers, not calibrated headset models. No stable device or session motion effects are implemented. Position noise is independently drawn without using the class label; the still class also uses a small orientation random walk. The other orientation trajectories share fixed class templates, which can make classification artificially easy. These limits and all generator settings are documented in configs/pilot.json and the XR/SNN design document.

The primary pilot split is cross session
- Session 1: training
- Session 2: validation and threshold selection
- Session 3: final testing

Device IDs intentionally occur in all three splits. This split does not measure cross-device or cross-person generalization, and the shared synthetic templates limit conclusions about real cross-session performance. Cross-device inference generalization is outside the initial pilot; cross-device authentication-substitution attacks remain in scope.

Attacked copies stay in the same split as their clean source. They don't count as new independent trials. Automated checks will fail if a source trial or session appears in more than one split.

## System flow

simulated noisy PUF
        ↓
device credential reconstruction
        ↓
session key establishment
        ↓
Quest data → 2 second window → authentication tag
                                      ↓
                              authentication gate
                                ↓            ↓
                         reject and log      accept
                                                ↓
                              classifier + anomaly detector
                                                ↓
                                         audit record

The planned integration uses a separate locally simulated sender/device process and verifier process, even when both run on one computer. The verifier owns session and accepted-sequence state; sender-supplied audit outcomes are not trusted.

The simulated PUF provides noisy, device-specific response bits. A reconstruction method recovers stable credential material, which is then used to derive a session key.

For the pilot, each window will be protected with HMAC-SHA-256. Encryption is not required because the initial study focuses on integrity, device and session binding, freshness, and replay protection.

A device ID is a public identifier, not proof of origin by itself. The security property comes from binding the device, session, sequence number, protocol version, and payload to a valid tag under the established session key.

HMAC verification alone does not detect a correctly tagged replay. Replay, duplicate, stale-window, and ordering decisions require verifier-side state for the active session and last accepted sequence number.

The authentication tag covers
- Protocol and schema version
- Pseudonymous device ID
- Session ID
- Increasing sequence number
- Window time range or index
- Payload format and length
- Exact serialized sensor data

The initial verifier will accept only the next expected sequence number. It will reject invalid tags, duplicates, stale or reordered windows, unexpected sequence gaps, expired sessions, and unknown devices or sessions. Rejected windows will be logged and won't reach normal inference. Under the proposed strict ordering policy, a detected missing sequence is logged, a later out-of-order window is rejected, and no implicit resynchronization occurs. If the expected window cannot be delivered, processing resumes only after a new authenticated session is established.
Enrollment happens once under trusted conditions. Session authentication happens when a new session begins. Window verification happens for every sensor window.
The final simulated-PUF structure and error-correction method will be selected after measuring raw bit-error rate, reliability, uniqueness, uniformity, and reconstruction success.

## Classification and anomaly detection

The classifier answers the question: Which of the five head motions occurred?

The proposed SNN input tensor will have the shape
[batch, 120 time steps, 8 channels]

The proposed SNN channels are relative position `(x, y, z)`, relative quaternion `(x, y, z, w)`, and the tracking-valid mask. The implemented conventional baselines instead flatten the seven pose channels across 120 time steps into 840 features; they do not include the tracking mask or metadata as model features. Any fitted scaling or normalization uses training data only.

The first classification baselines are
1. Multinomial logistic regression
2. Random forest with 300 trees
3. A small recurrent LIF SNN

LightGBM may be added after the first two conventional models work reliably. Later experiments may compare velocities, accelerations, derived features, or delta encoding.
The anomaly detector answers the question: Does this authenticated window contain a defined suspicious change?

The first anomaly experiment will be supervised and separate from motion classification
- normal: unchanged clean window
- suspicious: a documented sensor change was applied before authentication

Logistic regression and random forest will be used first. A separate SNN anomaly model may be added afterward. Classification confidence won't automatically be treated as an anomaly score. The anomaly labels, transform severities, and artifact controls must be documented and accepted before implementing the supervised anomaly baseline. Tier 2 semantic attacks and full SNN implementation wait until a stable, reproducible Tier 1 integration path is established.

## Threat model and attacks

The attacker may copy, replay, substitute, delay, reorder, drop, or modify sensor-window messages. The attacker may also alter sensor values before a valid authentication tag is created.
The initial prototype trusts the enrollment process, logger, window builder, verifier, experiment configuration, and cryptographic code.

### Tier 1: authentication attacks

The first authentication tests are
1. Replay a valid window in the same session
2. Replay a window from an earlier session
3. Substitute a window across devices or sessions
4. Change the sensor payload after tagging
5. Change protected metadata after tagging

The gate should also handle duplicate, stale, reordered, delayed, and missing-window cases. A missing window can't be rejected because it never arrives, so the system records the missing sequence instead.

### Tier 2: suspicious but authenticated motion

These changes happen before the tag is created, so the authentication gate should accept them
- Added sensor noise
- Constant bias or gradual drift
- Timestamp jitter or changed sampling rate
- Dropped samples
- Frozen pose values
- Sudden position or orientation jumps

The anomaly detector should try to flag these windows, while the classifier is tested for changes in accuracy.
Targeted model attacks, PUF modeling attacks, and adaptive attacks are outside the first pilot.

## Experimental comparison

We will compare four system versions
1. Conventional classifier without authentication
2. SNN classifier without authentication
3. Authenticated stream with a conventional classifier
4. Authenticated stream with an SNN classifier

All four will use the same source windows, splits, preprocessing, attacks, and random seeds. The anomaly detector will be reported as a separate experiment instead of being mixed with motion-classification confidence.

## Evaluation targets

### Authentication

- Target 100% observed rejection across at least 1,000 examples of each Tier-1 attack; report the actual rejection count and trial count, not a claim of universal rejection
- Valid window false reject rate no higher than 0.5%
- PUF session false reject rate no higher than 1%, pending reconstruction results
- Report false acceptance and false rejection separately

### Motion classification

- Accuracy
- Per-class precision, recall, and F1
- Macro-F1
- Confusion matrix
- No more than a 1 percentage-point macro-F1 decrease caused by authentication
- SNN macro-F1 within 5 percentage points of the strongest conventional baseline

The primary authentication-related macro-F1 loss is the unauthenticated macro-F1 minus authenticated macro-F1 on the same complete set of legitimate windows. A rejected legitimate window is an abstention with no motion prediction and contributes a false negative to its true class. Macro-F1 is averaged over the five motion classes, not a sixth rejection class. Also report accepted-only macro-F1 and legitimate-window rejection coverage separately. With the same model and preprocessing, authentication must not change the class prediction for an accepted window.

### Anomaly detection

- Precision, recall, F1, and false-positive rate
- At least 90% detection for medium and severe Tier-2 changes
- No more than 5% false positives on clean windows
- Choose the decision threshold using validation data only

### PUF simulation

- Reliability
- Uniqueness
- Uniformity
- Raw bit-error rate
- Credential-reconstruction success

### Latency

The following values are provisional engineering targets, not externally validated requirements.

- Authentication median and p95
- Inference median and p95
- Post-window decision median and p95
- Authentication p95 no higher than 1 ms
- Post-window decision p95 no higher than 20 ms
- Authentication overhead no higher than 10% compared with the same pipeline without authentication

The 2 second recording window is not included in the 20 ms processing target. Total capture-to-decision time is approximately
2,000 ms + post-window decision latency


This is a processing measurement, not motion-to-photon latency. Report machine model, operating system, Python version, implementation type, timing method, warm-up procedure, and repetition count alongside median and p95 results. Personal-laptop Python measurements are software-prototype results, not embedded Quest or FPGA performance.

## Experiment records

Each tested window will record
- Run, window, and source-trial IDs
- Code commit, configuration, and schema versions
- System condition and random seed
- Attack name, settings, and injection point
- Authentication result and reason
- Ground-truth and predicted motion
- Anomaly label, score, and prediction when applicable
- Authentication, preprocessing, inference, and total latency

Logs won't include session keys, reconstructed credentials, raw PUF responses, participant names, or headset serial numbers.

## Out of scope for the pilot

The first pilot won't include
- A claim that the Quest 3 contains an accessible physical PUF
- FPGA or Loihi deployment
- Eye tracking, hand tracking, video, or audio
- Modified headset firmware
- Production authentication infrastructure
- Sensor-data encryption
- A compromised verifier
- Physical side-channel attacks
- Advanced PUF modeling or targeted model attacks

## Data and ethics

Continue documentation, synthetic data, software simulation, and code development on personal computers using project-approved repositories and no human-derived data. Lab Quest data collection and retention of human-derived motion data must wait until the appropriate institutional path and lab workflow are confirmed. Public data and scripted headset tests may be used only when explicitly approved for the project.

The public repository may contain code, documentation, schemas, configurations, tests, aggregate results, and small synthetic examples. It won't contain participant motion traces, direct identifiers, device secrets, session keys, or raw PUF responses.

Storage, access, retention, backup, de-identification, and deletion rules must be approved before human-derived data are kept.

## Supporting documents

More detailed information is stored separately
- `docs/xr-snn-design.md`: logger, preprocessing, models, and anomaly design
- `docs/puf-auth-design.md`: simulated PUF and authentication design
- `docs/literature-review.md`: search process, literature matrix, gap, and references
- `docs/faculty-decision-memo.md`: decisions that require faculty or lab approval
- `schemas/`: machine-readable data and experiment-record formats
- `configs/pilot.json`: current experimental settings
