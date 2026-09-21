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
- Synthetic-data generator seed: 7
- Diagnostic model seeds: 7, 17, 27, 37, and 47
- Logistic regression uses the lbfgs solver, a maximum of 5,000 iterations, and a StandardScaler fitted on training data
- Random forest uses 300 trees and one processing thread

For both models, each window is converted to relative position and relative quaternion values. Labels, IDs, timestamps, tracking-valid values, and other metadata aren't classifier features. The existing train, validation, and test assignments are kept separate.

### Results

The original fixed-template dataset produced perfect results, so I audited that run before treating it as a baseline. The audit found 480 exact orientation-trajectory matches between test windows and training windows. That explains why orientation-only and combined features gave 1.0000 test accuracy. Position-only accuracy was lower at 0.6167 for logistic regression and 0.5967 for random forest.

I regenerated the same 1,800-window cross-session dataset after adding deterministic per-trial variation to position, orientation, timing, noise, drift, and still-motion behavior. The corrected diagnostic found zero exact test-to-training orientation matches, zero exact combined-feature matches, and zero near-duplicate orientation pairs under the 1e-6 tolerance. The synthetic data are still not real Quest data or a cross-device/cross-person study.

| Model | Validation macro-F1 | Test accuracy | Test macro-F1 | p95 inference | p95 preprocessing + inference |
|---|---:|---:|---:|---:|---:|
| Logistic regression | 0.8825 +/- 0.0000 | 0.9017 +/- 0.0000 | 0.9032 +/- 0.0000 | 0.2432 +/- 0.0548 ms | 0.9447 +/- 0.1519 ms |
| Random forest | 0.8607 +/- 0.0024 | 0.8933 +/- 0.0033 | 0.8936 +/- 0.0033 | 12.7610 +/- 0.4017 ms | 14.1448 +/- 1.4158 ms |

Each value is the mean +/- sample standard deviation across the five diagnostic model seeds. Both measured preprocessing-plus-inference p95 values are below the provisional 20 ms post-window target for this classifier stage. Authentication, abnormality detection, and other system stages are not included, so this is not a total authenticated-system latency claim.

The corrected ablations show that orientation is still the strongest synthetic feature group, but it is no longer a lookup through exact repeated templates.

| Diagnostic check | Logistic regression | Random forest |
|---|---:|---:|
| Position only test accuracy | 0.3533 | 0.3250 |
| Orientation only test accuracy | 0.8733 | 0.9000 |
| Combined feature test accuracy | 0.9017 | 0.8950 |
| Permuted-label test accuracy | 0.1910 +/- 0.0312 | 0.1717 +/- 0.0319 |
| Safe-metadata-only test accuracy | 0.1900 | 0.1900 |
| Unsafe identifier-only test accuracy | 1.0000 | 1.0000 |

The identifier-only result is an intentional leakage control: class names in synthetic IDs make identifiers unsafe classifier features, and the actual feature builder excludes them. The near-chance permuted-label and safe-metadata checks are additional evidence that labels and safe metadata are not leaking into the corrected feature matrix.

### Artifacts and environment

- All 28 Python tests passed in the corrected recorded run
- `baseline-results.json`
- `baseline-diagnostics.json`
- `baseline-diagnostics.md`
- `baseline-summary.md`
- `logistic_regression-confusion-matrix.png`
- `random_forest-confusion-matrix.png`
- `position-trajectories-by-class.png`
- `orientation-trajectories-by-class.png`
- `original-baseline-audit/` with the original configuration and diagnostic output

The recorded environment was an HP Pavilion Plus Laptop 16-ab1xxx running Windows 11 with an Intel64 Family 6 Model 170 processor. The software environment was CPython 3.13.14, NumPy 2.5.3, scikit-learn 1.9.1, and Matplotlib 3.11.2.

The timing code uses 20 warm-up predictions and then times 600 individual one-window predictions using `time.perf_counter_ns()`.

Repository: https://github.com/Keellonn/PUF-SNN  
Corrected implementation and results commit: `e4e0523d9232ded6c7ff266fd5d495a8c8d31fc0`
Base commit reported by the diagnostic: `2c11de84bf4e321e81ce34d88dd371a25e7d8cc6`  
Working tree clean before run: `False`; the corrected files had not been committed yet  
Corrected pilot configuration SHA-256: `7e9b12fa8679c9fe08e9396b1a9ea0f3c36465afce07f666c6d5817021924846`  
Corrected input SHA-256: `752b009588f3e721a8bf2f8f8fcd1cdf0f7e998446b60953dd34dd5e9e54d661`  
Original audited input SHA-256: `0e29a1091db2a82968e75ef879934cb3164c38f4df874766f2c29c76b3231f00`

### Recreate my conventional classification baseline

From the repository root with the normal Windows virtual environment activated:

```powershell
python -m pip install -e .
python src/python/scripts/generate_data.py
python src/python/scripts/validate_data.py
python -m unittest discover -s tests -v
python src/python/scripts/run_baseline_diagnostics.py --input data/generated/synthetic-windows.jsonl --config configs/pilot.json --output results/week-3/keegan --machine-model "YOUR LAPTOP MODEL" --seeds 7 17 27 37 47 --warmup 20 --timed-windows 600
```

## Quest head-motion logger prototype

An initial Unity logger was implemented for collecting Quest head-position, head-orientation, timestamp, and tracking-validity data. The logger was developed and tested without collecting human-derived motion data.

The logger contains:

- head-pose capture using `Application.onBeforeRender` and `InputDevices.GetDeviceAtXRNode(XRNode.Head)`;
- monotonic capture timestamps;
- a queue that separates pose capture from file writing and window processing;
- two-second motion windows;
- fixed-grid output containing exactly 120 samples across the two-second window;
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

Recording remains disabled by default through the trial controller's `recordingAuthorized` setting. No human-derived Quest recording was collected for this software-only work.

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

The Unity EditMode test suite completed with all nine tests passing in 0.043 seconds.

| Test | Purpose | Actual result |
|---|---|---|
| Artificial stream, interpolation, JSONL, and reload | Exercise the queued end-to-end path with artificial raw poses | Passed |
| Exactly 95 percent tracking | Accept exactly 114 valid samples out of 120 | Passed |
| Equivalent quaternion signs | Keep quaternion sign continuity | Passed |
| Non-unit quaternion input | Normalize orientation input | Passed |
| Fixed-grid output | Produce 120 ordered normalized samples | Passed |
| Missing or zero orientation | Reject invalid orientation input | Passed |
| Timestamp-gap rejection | Reject a source gap greater than 50 milliseconds | Passed |
| Tracking-validity rejection | Reject tracking coverage below 95 percent | Passed |
| Malformed JSONL writer input | Reject a malformed JSONL line | Passed |

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

### Limitations and next integration step

The passing EditMode tests verify the window-processing code using artificial raw poses. They do not prove that the project has been successfully installed on a physical Quest 3 or that real headset motion has been captured correctly.

The following hardware tasks remain for a later approved hardware phase:

- connect an assigned Quest 3 through ADB;
- confirm that Unity detects the headset;
- build and install the Android application;
- confirm that the application launches on the headset;
- validate any future approved captured file with `validate_quest_log.py`.

The immediate shared software task is to agree on the canonical versioned authenticated-window representation, protect the complete serialized message, and add the first Tier-1 authentication tests before starting the SNN baseline.

No claim about physical Quest deployment, real-motion quality, authentication performance, or human-data collection is made from the current software-only tests.

Logger implementation commit: `d2f613c9b7b6f460855d3e120849c33b2ea1278d`
