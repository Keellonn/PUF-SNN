# Quest Logger

The Quest logger hasn't been built yet. This folder documents what it will collect once we receive permission to use the lab headsets

When headset access isn't approved yet, we'll use the synthetic Python generator instead

## Unity setup

We plan to use
- The Unity 6 LTS version approved by the lab
- OpenXR
- Android Build Support
- Android SDK and NDK
- Java JDK

We'll record the exact versions in the research log.

The logger will get the head device with
`UnityEngine.XR.InputDevices.GetDeviceAtXRNode(XRNode.Head)`

It will collect
- CommonUsages.devicePosition
- CommonUsages.deviceRotation
- CommonUsages.isTracked
- CommonUsages.trackingState

We may use `Application.onBeforeRender` to collect the most recent pose once per rendered frame

The callback should only collect the data. It shouldn't write files or perform slow processing. The collected samples can be placed in a queue and saved afterward

We'll record the real capture time for every sample instead of assuming every frame happens exactly 1/60 of a second apart

## Position and orientation

Unity uses these directions
- Positive x points right
- Positive y points up
- Positive z points forward

Position will be stored relative to the headset pose at the beginning of the trial. This helps prevent the headset's location in the room from becoming part of the movement classification.

Orientation will be stored as a quaternion with four values:

`x, y, z, w`

Each quaternion will be normalized.

A quaternion and its negative can represent the same orientation. If the current quaternion has a negative dot product with the previous one, its sign will be flipped. This prevents a normal orientation from looking like a sudden jump.

Relative orientation will be calculated as:

inverse(trial_start_orientation) * current_orientation

## Window rules

Each motion window will:
- Last 2 seconds
- Target 60 samples per second
- Contain 120 samples after resampling
- Use the real recorded timestamps
- Stay separate from other windows

Position will use linear interpolation when resampling. Orientation will use spherical linear interpolation, also called SLERP

A window will be marked invalid when
- A gap between two source timestamps is greater than 50 ms
- Less than 95% of its samples have valid tracking

## Trial process

Each trial follows this order
1. Show the motion label for 1 second
2. Record the motion for 2 seconds
3. Show a rest screen for 1 second
4. Continue with the next randomly selected label

The 5 labels are
- nod
- shake
- look_left_return
- look_right_return
- still

still means the user is asked not to intentionally move for 2 seconds. Small natural movements are allowed.

The still class isn't the same as the 1 second rest period between trials.

## Output

Every exported window must follow:

`schemas/quest-window.schema.json`

The Quest logger creates sensor and experiment data. Will's authentication layer later adds the session and authentication information

## Before using a headset, we will

- Confirm which of the 6 Quest 3 headsets we can use
- Confirm whether they belong to a lab managed Meta developer organization
- Find out who controls the developer organization
- Confirm that developer mode and ADB access are allowed
- Confirm which computer we should use for deployment
- Record the Unity, OpenXR, Android, Meta, and headset versions
- Confirm which tests are allowed before the IRB decision
- Confirm whether test recordings may be saved