# Quest Logger

This folder contains the Unity Quest head-motion logger. The logger can be developed and tested without collecting human data. Headset recording must remain disabled until the approved lab workflow permits it.

## Unity setup

The project uses:

- the Unity version recorded in `QuestLogger/ProjectSettings/ProjectVersion.txt`
- XR Plug-in Management
- OpenXR Plugin
- Unity OpenXR: Meta
- Android Build Support
- Android SDK and NDK Tools
- OpenJDK

The resolved Unity and package versions should be recorded in the Week 3 results.

The logger gets the head device with:

`UnityEngine.XR.InputDevices.GetDeviceAtXRNode(XRNode.Head)`

It collects:

- `CommonUsages.devicePosition`
- `CommonUsages.deviceRotation`
- `CommonUsages.isTracked`
- `CommonUsages.trackingState`

`HeadPoseCapture` uses `Application.onBeforeRender` to queue at most one pose per rendered frame. The callback does not write files or resample data. `RawPoseBuffer` is the queue between capture and later processing.

Each raw timestamp is calculated from `System.Diagnostics.Stopwatch.ElapsedTicks`, converted to nanoseconds using `Stopwatch.Frequency`. The stopwatch begins in the component's `Awake` method. This is monotonic elapsed application time. It is not Quest hardware time, Unity wall-clock time, UTC, or a cryptographically trusted timestamp.

## Position and orientation

Unity uses these directions:

- positive x points right
- positive y points up
- positive z points forward

The logger stores the source position and quaternion in the `unity_device_origin` coordinate frame. Position components are meters. Quaternion components are dimensionless and stored in `[x, y, z, w]` order. The conventional classifier later subtracts the first position and calculates orientation relative to the first quaternion. This keeps the saved logger output consistent with `schemas/quest-window.schema.json`.

Orientation is stored as a normalized quaternion in `[x, y, z, w]` order. Equivalent quaternion signs are made continuous so an ordinary rotation is not represented as a sudden sign jump.

## Window rules

Each accepted motion window:

- lasts 2 seconds
- targets 60 samples per second
- contains exactly 120 samples after resampling
- uses recorded monotonic timestamps
- stays separate from every other trial

Position uses linear interpolation. Orientation uses normalized quaternion SLERP after enforcing equivalent-quaternion sign continuity.

Tracking coverage is calculated by counting the 120 resampled output poses whose lower and upper source poses are both valid. A window is accepted at exactly 114/120 valid samples (95%) and rejected below that threshold. This is a sample-count rule, not a percentage-of-time rule.

A window is rejected when:

- source timestamps do not strictly increase;
- any adjacent source timestamp gap is greater than 50 ms;
- source data does not reach the final required 60 Hz target time;
- a position or orientation contains NaN or infinity;
- an orientation is missing or has zero magnitude;
- fewer than 114 of 120 resampled poses are valid; or
- processing cannot construct the required output.

Rejected windows are currently dropped from the classifier JSONL file and reported with a Unity warning containing the trial ID and reason. They are not repaired or silently retained. A later authenticated audit-record layer should store structured acceptance/rejection records. Tier-2 synthetic anomaly copies should be created from already accepted clean source windows, remain in the source split, and be reported separately so capture-quality rejection is not confused with anomaly detection.

## Trial process

Each trial follows this order:

1. show the motion label for 1 second
2. record the motion for 2 seconds
3. show a rest prompt for 1 second
4. continue with the next seeded random label

The five labels are:

- `nod`
- `shake`
- `look_left_return`
- `look_right_return`
- `still`

`still` means the participant is asked not to intentionally move for 2 seconds. It is separate from the rest period.

## Output

Every accepted window follows `schemas/quest-window.schema.json` and is appended as one JSON object per line. The default path is:

`Application.persistentDataPath/puf-snn/quest-windows.jsonl`

The logger creates sensor and experiment data. It does not implement PUF credential reconstruction, authentication, replay prevention, or the shared authenticated-message envelope.

## Tests

The EditMode suite contains these explicit checks:

| Test | What it verifies |
|---|---|
| `CreateWindowProduces120OrderedNormalizedSamples` | Accepted artificial input produces 120 ordered, tracked, normalized, sign-continuous output samples. |
| `CreateWindowRejectsTimestampGapAbove50Milliseconds` | A raw gap above the configured limit is rejected with a reason. |
| `CreateWindowRejectsTrackingBelow95Percent` | Tracking coverage below 95% is rejected. |
| `CreateWindowAcceptsExactly95PercentTracking` | The threshold is inclusive: exactly 114/120 valid output samples pass. |
| `CreateWindowNormalizesNonUnitQuaternionInput` | Non-unit but nonzero quaternion inputs are normalized. |
| `CreateWindowMakesEquivalentQuaternionSignsContinuous` | Alternating equivalent `q`/`-q` inputs do not create false jumps. |
| `CreateWindowRejectsMissingOrZeroOrientation` | A zero/missing orientation is rejected. |
| `WriterRejectsMalformedJsonlLine` | Malformed or structurally incomplete JSONL is rejected during reload. |
| `ArtificialStreamPassesQueueInterpolationJsonlAndReload` | Artificial raw poses pass through the queue, interpolation/windowing, JSONL writer, reload, and expected-field/value checks. |

These tests use artificial raw poses and do not require a headset. They verify software behavior only; they do not prove physical Quest capture, Android deployment, real motion quality, or permission to retain human-derived recordings.

After an authorized JSONL file is copied from the headset, validate it from the repository root with:

`python src/python/scripts/validate_quest_log.py path/to/quest-windows.jsonl`

## Before an authorized headset recording

- confirm the assigned headset and computer
- confirm developer mode and ADB access
- confirm the allowed test and data-retention workflow
- record the Unity, OpenXR, Android, Meta, and headset versions
- run Unity Project Validation without unresolved errors
- verify that the Android build installs and launches
- keep the controller's `recordingAuthorized` field disabled until recording is permitted
