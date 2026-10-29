# Week 9 — Independent Detector Table Reproduction

## Objective
Independently reproduce Keegan's logistic regression and random forest detector metrics using preserved prediction scores and frozen validation thresholds.

## Method
- Verified the original input package (17/17 files passed SHA-256 integrity checks)
- Executed the supplied Python reproduction script locally on Windows using Python 3.12.4
- Recomputed detector metrics for three fixed fits per model family
- Compared generated CSV results against Keegan's retained reference results
- Verified exact SHA-256 matches for both generated CSV files
- Preserved the execution log, environment information, reviewer notes, and results ZIP

## Reproduced Results
| Detector | Medium/High Recall | Clean False-Alert Rate |
|---|---:|---:|
| Logistic Regression | 82.848% | 5.333% |
| Random Forest | 87.953% | 2.944% |

Both detector families reproduced their reference metrics.

Neither model achieved the 90% recall target. Only random forest achieved the 5% clean false-alert target.

## Verification
- Input package integrity: PASS
- Reproduction execution: SUCCESS (exit code 0)
- Detector-family CSV SHA-256: MATCH
- Per-fit counts CSV SHA-256: MATCH
- Original input files unchanged: VERIFIED

## Limitations
This task independently reproduced detector metrics from frozen prediction scores and thresholds. It did not retrain the models, generate new predictions, or reproduce the original dataset construction.

## Evidence
- `input/` — Original frozen handoff from Keegan
- `output/reproduction-output/` — Recomputed tables and execution evidence
- `output/Will_Detector_Reproduction_Completed.zip` — Packaged results
