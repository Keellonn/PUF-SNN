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

`HeadPoseCapture` uses `Application.onBeforeRender` to queue at most one pose per rendered frame. The callback does not write files or resample data. Each raw sample uses a real monotonic capture time instead of an assumed frame interval.

## Position and orientation

Unity uses these directions:

- positive x points right
- positive y points up
- positive z points forward

The logger stores the source position and quaternion in the `unity_device_origin` coordinate frame. The conventional classifier later subtracts the first position and calculates orientation relative to the first quaternion. This keeps the saved logger output consistent with `schemas/quest-window.schema.json`.

Orientation is stored as a normalized quaternion in `[x, y, z, w]` order. Equivalent quaternion signs are made continuous so an ordinary rotation is not represented as a sudden sign jump.

## Window rules

Each accepted motion window:

- lasts 2 seconds
- targets 60 samples per second
- contains exactly 120 samples after resampling
- uses recorded monotonic timestamps
- stays separate from every other trial

Position uses linear interpolation. Orientation uses quaternion SLERP. A window is rejected when a source timestamp gap is greater than 50 ms, the source data does not cover the final target time, or fewer than 95 percent of the resampled poses have valid tracking.

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

The EditMode tests prove that the processor:

- creates exactly 120 ordered samples
- normalizes quaternions and keeps their signs continuous
- rejects a timestamp gap above 50 ms
- rejects tracking coverage below 95 percent

These tests use artificial raw poses and do not require a headset. They do not prove physical Quest capture, Android deployment, real motion quality, or permission to retain human-derived recordings.

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
