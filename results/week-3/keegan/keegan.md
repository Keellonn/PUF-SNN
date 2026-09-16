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
| Logistic regression | 1.0000 | 1.0000 | 1.0000 | 0.29 ms | 0.5417 ms |
| Random forest | 1.0000 | 1.0000 | 1.0000 | 14.38 ms | 22.4288 ms |

Logistic regression's inference-only p95 is below the provisional 20 ms post-window target. Random forest is slightly above the target at 22.4288 ms p95. Authentication, feature extraction, abnormality detection, and the other processing stages aren't included in these inference measurements.

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
- baseline-results.json
- baseline-summary.md
- logistic_regression-confusion-matrix.png
- random_forest-confusion-matrix.png

The recorded environment was Python 3.13.14 on Windows 11 with NumPy 2.5.3, scikit-learn 1.9.1, and Matplotlib 3.11.2. The machine model wasn't recorded and should be added in the next timing run.

The timing code uses 20 warm-up predictions and then times 600 individual one-window predictions using `time.perf_counter_ns()`.

Repository: https://github.com/Keellonn/PUF-SNN  
Recorded code commit: `975fb10651857955fc7e3b0414691fe5508d9b47`  
Recorded input SHA-256: `0e29a1091db2a82968e75ef879934cb3164c38f4df874766f2c29c76b3231f00`

## Recreate Keegan's synthetic data baseline

From the repository root with the normal Windows virtual environment activated, do

python -m pip install -e .
python src/python/scripts/generate_data.py
python src/python/scripts/validate_data.py
python -m unittest tests.test_baselines -v
python src/python/scripts/train_baselines.py
