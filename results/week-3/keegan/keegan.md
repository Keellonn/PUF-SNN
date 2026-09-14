## Conventional classification baseline

The first conventional classifiers were tested on 1,800 synthetic Quest like motion windows. The dataset contains 600 training, 600 validation, and 600 testing windows. Each window contains 120 time steps with seven motion values per time step, which produced 840 features.

As we've discussed before, session 1 was used for training, session 2 for validation, and session 3 for testing. This keeps the initial experiment focused on cross-session performance.

### Models

- Logistic regression with standardized features
- Random forest with 300 trees and one processing thread
- Random seed: 2026

### Results

| Model | Validation macro-F1 | Test accuracy | Test macro-F1 | Median inference | p95 inference |
|---|---:|---:|---:|---:|---:|
| Logistic regression | 1.0000 | 1.0000 | 1.0000 | 0.29 ms | 0.5417 ms |
| Random forest | 1.0000 | 1.0000 | 1.0000 | 14.38 ms | 22.4288 ms |

Logistic regression is well below the 20 ms post window target. Random forest is slightly above the target at 22.4288 ms p95. Authentication and the other processing stages are not included in these inference measurements.
Both models correctly classified all 120 test windows from each of the five motion classes. The confusion matrices contain only diagonal values
These results confirm that the feature and classification pipeline works. The perfect classification scores are expected to decrease with less predictable real Quest data, so they should not be treated as final model performance.

### Results

- Five passing baseline processing tests when you run the tests
- baseline-results.json
- baseline-summary.md
- logistic_regression-confusion-matrix.png`
- random_forest-confusion-matrix.png

### Run everything

From the repository root with the normal Windows virtual environment activated, do
python -m pip install -e .
python src/python/scripts/generate_data.py
python src/python/scripts/validate_data.py
python -m unittest tests.test_baselines -v
python src/python/scripts/train_baselines.py