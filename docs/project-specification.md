# SNN + PUF Research Specification

**Researchers:** Keegan Hoyne and Will Wallace  

## Research question

How do simulated noisy PUF credential reconstruction, independent pre-HKDF verification, authenticated-window enforcement, and downstream motion/anomaly inference interact in a reproducible software prototype, and what reliability, attack-rejection, classification and post-window latency limits do the experiments establish?

## Project goal

Quest applications continuously process motion data. An attacker could replay old data, change it after collection, claim it came from another device or session, or create unusual motion before the data is authenticated.

Our prototype separates these problems
- PUF-derived credential reconstruction attempts to recover enrolled credential material from a noisy simulated response.
- Independent credential verification and trusted local admission reject incorrect candidates before session-key derivation.
- Session establishment derives keys only after admission, followed by mutual confirmation before an active session.
- Per-window integrity/authenticity verification checks the protected message and its tag.
- Replay/freshness/order checking uses verifier-side session and sequence state.
- Motion classification identifies which head movement occurred.
- A separate anomaly detector checks accepted windows for suspicious sensor behavior.

We will evaluate how these parts work separately and together. Based on our targeted review so far, we have not found a study that evaluates this exact combination of simulated PUF-based credentials, authenticated XR motion windows, SNN inference, anomaly detection, replay and substitution attacks, and per-stage latency in one reproducible experiment.

This is a reproducible software prototype for authenticated XR motion-window processing: a simulated noisy PUF-derived credential supports session establishment; an independent verifier prevents observed BCH miscorrections from reaching key derivation; canonical HMAC-protected windows enforce binding, integrity, freshness and ordering before conventional or spiking inference; and a separate anomaly model evaluates defined pre-tag semantic perturbations. This is not a physical Quest PUF, production fuzzy extractor or demonstrated hardware root of trust.

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

The logger stores source position and orientation in Unity device-origin coordinates, where x is right, y is up, and z is forward. Classifier preprocessing later calculates position and orientation relative to the first valid pose in each window.

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

The corrected generator uses provisional device/session amplitude and duration effects shared across all labels, plus trial-level starting pose, amplitude, duration, onset, phase warp, peak/return timing, secondary-axis movement, return error, noise, drift and sway. Still includes nonzero position and orientation random walks. These are engineering assumptions, not calibrated headset or human distributions. The original repeated-orientation result remains preserved as methodological evidence. Full-window cross-split comparisons and rotation-aware nearest-neighbor analysis supplement the existing identifier and exact-feature checks.

The primary pilot split is cross session
- Session 1: training
- Session 2: validation and threshold selection
- Session 3: final testing

Device IDs intentionally occur in all three splits. This split does not measure cross-device or cross-person generalization, and the synthetic parametric motion families limit conclusions about real cross-session performance. Cross-device inference generalization is outside the initial pilot; cross-device authentication-substitution attacks remain in scope.

Attacked copies stay in the same split as their clean source. They don't count as new independent trials. Automated checks will fail if a source trial or session appears in more than one split.

## System flow

```text
simulated noisy PUF
        -> credential reconstruction
        -> independent credential verification + local admission
        -> HKDF + mutual confirmation
        -> active session

motion -> validated 120-sample window -> Wire 2.0 bytes + window HMAC
        -> verification of binding, integrity, quality and sequence
           reject: authentication audit, no model call
           accept: authentication audit + sequence commit
                   -> at-most-once release
                   -> motion classifier + separate anomaly detector
                   -> downstream inference evidence
```

The current v2 admission gate is documented in `docs/credential-verifier-setup.md`. Its credential-verification HMAC uses an independent verifier key/context; it is not the window HMAC under a derived session key. An incorrect candidate fails before request emission/HKDF. The receiver requires the trusted local admission authorization before allocating a pending session; mutual confirmation is still required before an active session can authorize window processing. This local authorization mechanism is a software-pilot trust assumption, not a remote attestation claim.
The integration uses separately instantiated software sender/device and verifier endpoints on one computer; the recorded evaluation does not establish process isolation or network deployment. The verifier owns session and accepted-sequence state; sender-supplied audit outcomes are not trusted.

The simulated PUF provides noisy, device-specific response bits. Reconstruction can fail or produce a valid-format wrong candidate; the independent verification/admission gate checks the actual candidate before key derivation. Blocking a miscorrection protects integrity but does not repair a failed legitimate reconstruction or improve availability.

The current per-window interface uses HMAC-SHA-256 over the exact canonical big-endian Wire Protocol 2.0 binary bytes (including binary32 motion), not the JSON/base64 transport formatting. Encryption is not required because the initial study focuses on integrity, device and session binding, freshness, and replay protection.

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

The implemented SNN input tensor has shape `[batch, 120 time steps, 7 channels]`.

The seven channels are relative position `(x, y, z)` and relative quaternion `(x, y, z, w)`. Tracking quality is authenticated and validated but never used as a model feature. Conventional baselines flatten the same seven pose channels into 840 values. LR uses training-only scaling per flattened feature; the SNN uses training-only scaling per channel across training windows/time points; RF is unscaled. Quaternion normalization and sign continuity precede first-pose-relative rotations. Euler angles are not model features.

The first classification baselines are
1. Multinomial logistic regression
2. Random forest with 300 trees
3. A small recurrent LIF SNN

The existing feature ablations are retained as evidence. No further feature variants or SNN architecture expansion are part of this revision; any later change requires a predeclared question and validation-only selection protocol after the end-to-end authentication experiment.
The anomaly detector answers the question: Does this authenticated window contain a defined suspicious change?

The completed first anomaly experiment is supervised and separate from motion classification
- normal: unchanged clean window
- suspicious: a documented sensor change was applied before authentication

Logistic regression and random forest were used in the first separate supervised anomaly experiment. No SNN anomaly detector will be added before the conventional anomaly analysis and end-to-end timing are complete. Classification confidence is not treated as an anomaly score. The anomaly labels, transform severities, and artifact controls are documented in `docs/tier2-stream-attacks.md`. The first recurrent SNN remains a motion classifier. The Week 5 Tier 2 attack evaluation and held-out detector results are recorded in `results/week-5/keegan/`. Both detectors missed the provisional 90% medium/high detection target; that Week 5 attack experiment does not establish detector-inclusive latency, physical Quest performance, or full-system availability. Separate first instrumented v2 composite timing is now recorded under `results/week-6/keegan/`, with the scope and limitations below.

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

These changes happen before tag creation. Only successfully constructed, quality-valid windows can be sealed by the legitimate sender and evaluated as authenticated semantic anomalies
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
- Reconstruction/admission false reject rate no higher than 0.5%, as clarified in the latest faculty feedback; retain the earlier 1% provisional wording as historical, not as an achieved target
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


This is a software-prototype processing target, not motion-to-photon latency or a hard real-time/headset guarantee. Report machine, OS/software, a high-resolution monotonic timer, warm-up/repetition counts, GC state, logging/I/O scope, CPU power/affinity controls (or their absence), p50/p95/p99/max and retained outliers. The historical Week 4 recurring-window benchmark excludes reconstruction, independent verification, session setup, a separate anomaly detector and durable audit I/O; its LR/SNN-64 accepted p95 is below 20 ms, while RF is above. The separate Week 6 instrumented v2 run measures fresh admission-to-first-inference and complete motion-plus-anomaly post-window paths. None of its six conditions meets 20 ms p95 for first, recurring or after-refusal complete post-window processing. Recorded GC overlaps locate substantial activity during large maxima, but observer effects and complete causal attribution remain unresolved. Physical acquisition, network and durable audit storage remain excluded. Never add nested stage percentiles to manufacture an end-to-end total.

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


## Week 4 evaluation clarification

The original historical SNN met the five-point gap, but the separately seeded SNN-64 follow-up misses it (0.8500 macro-F1; 5.32 points below LR). The validation-selected SNN-32 ablation meets it (0.8619; 4.12 points below LR). Neither outperforms LR or RF. Preserve historical runs and use Session 2, not Session 3, for selection. The feedback evaluation records separate initialization/training seeds, complete per-class metrics, learning curves, full-window and rotation-aware leakage diagnostics, nod/still analysis, fixed feature/stress comparisons and one 32-versus-64-neuron comparison.

Data generation uses seed 7 and retains its original draw sequence. Session-index splits are deterministic and have no random split seed. Role-specific model/training/permutation seeds and pointers to attack/PUF configurations are recorded in configs/pilot.json. OS session randomness remains cryptographic and unseeded. See docs/xr-snn-design.md for exact model and timing boundaries, docs/authenticated-window-interface.md for the current Wire Protocol 2.0 binary contract and rejection policy, and docs/puf-layer3-design.md for Will's Layer 3 implementation overview.

Layer-2 session reconstruction FRR and per-window verifier FRR require separate denominators; do not equate them without an explicit end-to-end mapping. Current reconstruction and key-confirmation limitations remain Will's responsibility. A known-correct-candidate pipeline benchmark excludes reconstruction failures and cannot establish overall legitimate-window availability.

## Week 5 revision evidence and claim boundaries

The revised Tier-2 report reconciles all 50,400 planned cases, including 5,501 pre-tag construction blocks: 3,493 excessive source gaps and 2,008 non-increasing source timestamps. The 14,956 quality-valid held-out cases were accepted in the historical known-correct-credential run; reading those results does not validate the later v2 admission gate. Per-attack/severity detected/missed counts, paired classifier losses and conditional intervals are in `results/week-5/keegan/tier2-breakdown/`.

LR/RF anomaly F1 is 0.8424/0.9003, clean test FPR is 5.33%/2.94%, and medium/high recall is 82.85%/87.95%. Neither meets the unchanged 90% recall criterion; LR also misses the 5% test-FPR target. Thresholds remain frozen from Session 2, not lowered after inspecting Session 3.

Low-amplitude nods are evaluated as legitimate execution variation and an ambiguous intended-class boundary, not automatically as malicious behavior. The original amplitude/speed grid is retained, with conventional/SNN sensitivity and frozen detector flag rates in `results/week-5/keegan/nod-diagnostics/`. Orientation and full 120 x 7 nearest-training metrics, exact processing/alignment rules, and the retained original leakage evidence are in `results/week-5/keegan/sequence-neighbors/`.

Per-class/per-seed metrics, all six SNN learning histories/stopping decisions, exact LIF/readout equations, model storage and the fixed validation-only selection protocol are in `results/week-5/keegan/model-evidence/`. LR's deterministic lbfgs fitting explains its zero descriptive seed SD; five seed labels are not five independent stochastic performance samples. Data generation seed 7 fixes one dataset, separate from model/attack/uncertainty seeds.

Claims remain cross-session synthetic evaluation with six fixed simulated device profiles. No cross-device, cross-person, real Quest, energy or deployed-security claim follows. The paper outline is `docs/paper-outline.md`. The first fresh v2 accepted/refused timing and frozen-model functional evidence are now recorded separately in Week 6. Remaining shared evidence includes the formal v2 trust/key specification, expanded varied Tier-1 trials with exact intervals and parser/state instrumentation, controlled reconstruction alternatives, causal timing/observer-effect diagnosis and durable audit performance. Existing Will-side reports remain separate and unchanged.

## Week 6 integration and first instrumented timing evidence

`puf_snn/pipeline_v2.py` connects one modeled noisy response read and one actual BCH reconstruction to independent credential verification, trusted local admission, HKDF/mutual confirmation and accepted-window composite motion/anomaly inference. It does not substitute the enrolled credential, retry until success, change the session/sequence policy or let anomaly flags roll back authentication.

The 30-attempt frozen-model smoke passed all admission and boundary controls. The separate timing run retained 3,720 fresh attempts and 29,718 root traces across six predeclared conditions: 20 validation warmups and 600 test-source attempts per condition. Each condition admitted 599/600 measured attempts and all warmups. The same reconstruction refusal recurs in paired source/noise streams; these are not six independent failures or a new FRR estimate. Refused windows invoke no preprocessing or models.

Recurring complete-path p95 is 27.7629 ms for logistic motion/logistic anomaly, 30.3028 ms for logistic/forest, 52.8523 ms for forest/forest and 51.3985/50.5355/54.1160 ms for SNN-32 seeds 7/17/27 with the forest detector. First and after-refusal complete-path p95 values also exceed 20 ms. This is instrumented CPU evidence, not uninstrumented deployment performance or a causal ranking across model conditions.

`configs/week6_smoke.json` pins the unchanged dataset and all 11 frozen model binaries; `configs/week6_timing.json` fixes model conditions and attempt counts. No fitting or threshold selection occurred. Methods and exclusions are in `docs/week6-end-to-end.md`; the raw run is `results/week-6/keegan/fresh-v2-timing/` and its read-only diagnostic addendum is `results/week-6/keegan/timing-diagnostics/`. The latter reconciles all retained observations without rerunning the benchmark or establishing complete causal attribution.
