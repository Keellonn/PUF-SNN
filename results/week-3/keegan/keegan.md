# Week 3 Results

This week covered two software tasks:

1. training conventional classifiers on the synthetic dataset;
2. implementing and testing the initial Unity Quest head-motion logger.

No human-derived motion data was collected during this work.

## Conventional classification baseline

The first conventional classifiers were tested on 1,800 synthetic Quest-like motion windows. The dataset contains 600 training, 600 validation, and 600 testing windows. Each window contains 120 time steps with seven motion values per time step, which produced 840 features.

Session 1 was used for training, session 2 for validation, and session 3 for testing. This keeps the initial experiment focused on cross-session performance.

The same synthetic device groups appear in all three splits. This is not cross-device or cross-person generalization.

### Models

- Logistic regression with standardized features
- Random forest with 300 trees and one processing thread
- Random seed: 2026
- Logistic regression uses the lbfgs solver, a maximum of 5,000 iterations, and a StandardScaler fitted on training data
- Random forest uses 300 trees and one processing thread

For both models, each window is converted to relative position and relative quaternion values. Labels, IDs, timestamps, tracking-valid values, and other metadata aren't classifier features. The existing train, validation, and test assignments are kept separate.

### Results

| Model | Validation macro-F1 | Test accuracy | Test macro-F1 | Median inference | p95 inference |
|---|---:|---:|---:|---:|---:|
| Logistic regression | 1.0000 | 1.0000 | 1.0000 | 0.2322 ms | 0.3896 ms |
| Random forest | 1.0000 | 1.0000 | 1.0000 | 14.1423 ms | 21.6515 ms |

Logistic regression's inference-only p95 is below the provisional 20 ms post-window target. Random forest is slightly above the target at 21.6515 ms p95. Authentication, feature extraction, abnormality detection, and the other processing stages aren't included in these inference measurements.

Both models correctly classified all 120 test windows from each of the five motion classes. The confusion matrices contain only diagonal values.

| Class | Precision | Recall | F1 | Test windows |
|---|---:|---:|---:|---:|
| nod | 1.0000 | 1.0000 | 1.0000 | 120 |
| shake | 1.0000 | 1.0000 | 1.0000 | 120 |
| look_left_return | 1.0000 | 1.0000 | 1.0000 | 120 |
| look_right_return | 1.0000 | 1.0000 | 1.0000 | 120 |
| still | 1.0000 | 1.0000 | 1.0000 | 120 |

These results confirm that the feature and classification pipeline works on the current synthetic data. No class-confusion failures were observed. The generator reuses fixed class templates and doesn't model stable device or session motion effects, which can make the task artificially easy. The perfect scores shouldn't be treated as expected real Quest performance.

### Artifacts and environment

- Five baseline processing tests passed in the recorded run
- `baseline-results.json`
- `baseline-summary.md`
- `logistic_regression-confusion-matrix.png`
- `random_forest-confusion-matrix.png`

The recorded environment was an HP Pavilion Plus Laptop 16-ab1xxx running Windows 11 with an Intel64 Family 6 Model 170 processor. The software environment was CPython 3.13.14, NumPy 2.5.3, scikit-learn 1.9.1, and Matplotlib 3.11.2.

The timing code uses 20 warm-up predictions and then times 600 individual one-window predictions using `time.perf_counter_ns()`.

Repository: https://github.com/Keellonn/PUF-SNN  
Recorded code commit: `4f540a7c9d32035a66d775bedd047756960242de`  
Working tree clean before run: `True`  
Recorded input SHA-256: `0e29a1091db2a82968e75ef879934cb3164c38f4df874766f2c29c76b3231f00`

### Recreate my conventional classification baseline

From the repository root with the normal Windows virtual environment activated:

```powershell
python -m pip install -e .
python src/python/scripts/generate_data.py
python src/python/scripts/validate_data.py
python -m unittest tests.test_baselines -v
python src/python/scripts/train_baselines.py --machine-model "YOUR LAPTOP MODEL"
```

## Quest head-motion logger prototype

An initial Unity logger was implemented for collecting Quest head-position, head-orientation, timestamp, and tracking-validity data. The logger was developed and tested without collecting human-derived motion data.

The logger contains:

- head-pose capture using `Application.onBeforeRender`;
- monotonic capture timestamps;
- a queue that separates pose capture from file writing and window processing;
- two-second motion windows;
- fixed-grid output containing exactly 120 samples at 60 Hz;
- linear interpolation for position;
- quaternion SLERP for orientation;
- quaternion normalization and sign continuity;
- JSONL output following `quest-window.schema.json`;
- a one-second prompt, two-second recording, and one-second rest trial process;
- a seeded randomized schedule containing the five motion labels.

The logger stores source poses in the `unity_device_origin` coordinate frame. Relative position and relative orientation are created later by the classifier feature-processing code.

Accepted windows are appended to:

`Application.persistentDataPath/puf-snn/quest-windows.jsonl`

The logger does not implement PUF credential reconstruction, authentication, replay prevention, or abnormality detection.

### Window-quality rules

A window is rejected when:

- a source timestamp gap is greater than 50 milliseconds;
- source data does not cover the final required sample time;
- fewer than 95 percent of the resampled poses have valid tracking;
- source timestamps are not strictly increasing;
- the processor cannot produce exactly 120 ordered output samples.

Recording remains disabled by default through the trial controller's `recordingAuthorized` setting. It must only be enabled for an approved headset-recording session.

### Unity environment

| Component | Recorded version or setting |
|---|---|
| Unity Editor | 6000.6.1f1 |
| Input System | 1.20.0 |
| XR Plug-in Management | 4.7.0 |
| OpenXR Plugin | 1.18.0 |
| Unity OpenXR: Meta | 2.6.1 |
| Unity Test Framework | 1.8.0 |
| Build profile | Meta Quest |
| OpenXR feature group | Meta Quest enabled |

Android Build Support, OpenJDK, and the Android SDK and NDK tools were installed through Unity Hub.

### Automated evidence

The Unity EditMode test suite completed with all three tests passing in 0.033 seconds.

| Test | Purpose | Actual result |
|---|---|---|
| Accepted-window processing | Produce 120 ordered samples with normalized, sign-continuous quaternions | Passed |
| Timestamp-gap rejection | Reject a source gap greater than 50 milliseconds | Passed |
| Tracking-validity rejection | Reject tracking coverage below 95 percent | Passed |

Unity OpenXR Project Validation reported zero issues for the active Meta Quest configuration. The Unity Console was also cleared after compilation and showed no red compilation errors.

Evidence:

- [Unity logger test run](logger-test-runs.png)
- [OpenXR Project Validation](project-validation.png)

### Logger files

- `src/quest-logger/QuestLogger/Assets/Scripts/QuestLogger/HeadPoseCapture.cs`
- `src/quest-logger/QuestLogger/Assets/Scripts/QuestLogger/QuestTrialController.cs`
- `src/quest-logger/QuestLogger/Assets/Scripts/QuestLogger/QuestWindowModels.cs`
- `src/quest-logger/QuestLogger/Assets/Scripts/QuestLogger/QuestWindowProcessor.cs`
- `src/quest-logger/QuestLogger/Assets/Scripts/QuestLogger/QuestWindowWriter.cs`
- `src/quest-logger/QuestLogger/Assets/Tests/EditMode/QuestWindowProcessorTests.cs`
- `src/python/scripts/validate_quest_log.py`
- `src/quest-logger/README.md`

### Limitations and next hardware step

The passing EditMode tests verify the window-processing code using artificial raw poses. They do not prove that the project has been successfully installed on a physical Quest 3 or that real headset motion has been captured correctly.

The following hardware tasks remain:

- connect an assigned Quest 3 through ADB;
- confirm that Unity detects the headset;
- build and install the Android application;
- confirm that the application launches on the headset;
- perform an approved test capture;
- copy the resulting JSONL file from the headset;
- validate the captured file with `validate_quest_log.py`.

No claim about physical Quest deployment, real-motion quality, authentication performance, or human-data collection is made from the current software-only tests.

Logger implementation commit: `d2f613c9b7b6f460855d3e120849c33b2ea1278d`