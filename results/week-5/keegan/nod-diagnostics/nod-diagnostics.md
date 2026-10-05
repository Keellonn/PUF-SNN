# Nod/still amplitude and temporal-ambiguity diagnostics

## Question and fixed interpretation

How do the existing motion classifiers distinguish an intentional nod from still as its intentional amplitude decreases, and do the frozen anomaly models falsely flag that legitimate execution variation?

These synthetic nod variants are treated as legitimate natural execution variation and an increasingly ambiguous class boundary. A similar motion reduction could be adversarial in another threat scenario, but intent is not observed here. Nod recall and still-confusion quantify sensitivity to the original intended label; detector flag frequency quantifies false alarms under this stated interpretation, not attack recall. An unflagged detector result is not a prediction of the still class.

No architecture, feature variant, threshold or attack parameter was selected using this report. The amplitude/speed grid is the already-saved Week 4 grid. Motion sensitivity results are reused, not refitted. The six local anomaly models and their validation-only thresholds are loaded unchanged; no anomaly training occurs.

## Nominal and observed amplitude

| Amplitude scale | Signed x-rotation coefficient (degrees) | Vertical coefficient (meters) |
|---:|---:|---:|
| 0.1 | -2.20 | 0.000600 |
| 0.25 | -5.50 | 0.001500 |
| 0.5 | -11.00 | 0.003000 |
| 0.75 | -16.50 | 0.004500 |
| 1 | -22.00 | 0.006000 |

The unscaled nominal nod uses an x-axis rotation coefficient of -22 degrees and a vertical-position coefficient of 0.006 m. Half amplitude uses -11 degrees / 0.003 m; one-tenth uses -2.2 degrees / 0.0006 m. These are synthetic coefficients before trial/device/session amplitude effects, phase shaping, secondary-axis coupling, noise, drift, sway and return error—not measured peak angles. Those nuisance terms remain unchanged, so a one-tenth coefficient does not imply one-tenth total observed motion.

Speed scale changes the generator's duration-range bounds by division; the generator still multiplies group duration effects and clips to [0.75, 1.95-start_delay] seconds. It is a synthetic temporal-ambiguity stress, not a measured physical speed or a resampled hardware capture. The original 120-point grid and sample timestamps remain unchanged.

`nominal-conditions.json` records every amplitude/speed condition. `physical-observations.csv` records observed peak geodesic rotation and angular speed statistics per condition. Representative trajectories use the first lexicographically sorted nod and still source IDs in each split, selected without prediction results. The same nod source is used at all five amplitudes; this one illustrative example is not a population summary.

## Matched nominal-speed summary

Rates below are means across fixed model seeds on the same 120 source nods—not independent recording replications. Each curve and CSV retains every seed and both validation/test splits. Other-class predictions are reported rather than silently combining them into still.

| Amplitude | Motion family | Test nod recall mean | Test still-confusion mean |
|---:|---|---:|---:|
| 0.1 | logistic_regression | 0.2333 | 0.7167 |
| 0.1 | random_forest | 0.1361 | 0.8500 |
| 0.1 | snn | 0.0694 | 0.9000 |
| 0.25 | logistic_regression | 0.4333 | 0.5000 |
| 0.25 | random_forest | 0.3694 | 0.6111 |
| 0.25 | snn | 0.2083 | 0.7556 |
| 0.5 | logistic_regression | 0.6667 | 0.2667 |
| 0.5 | random_forest | 0.6639 | 0.3250 |
| 0.5 | snn | 0.5944 | 0.3806 |
| 0.75 | logistic_regression | 0.8500 | 0.1083 |
| 0.75 | random_forest | 0.7694 | 0.2000 |
| 0.75 | snn | 0.7556 | 0.2361 |
| 1 | logistic_regression | 0.9250 | 0.0417 |
| 1 | random_forest | 0.8361 | 0.1056 |
| 1 | snn | 0.8444 | 0.1417 |

| Condition | Anomaly family | Test legitimate flag-rate mean |
|---|---|---:|
| Nod 0.1x | logistic_regression | 0.0417 |
| Nod 0.1x | random_forest | 0.0306 |
| Nod 0.25x | logistic_regression | 0.0333 |
| Nod 0.25x | random_forest | 0.0250 |
| Nod 0.5x | logistic_regression | 0.0250 |
| Nod 0.5x | random_forest | 0.0278 |
| Nod 0.75x | logistic_regression | 0.0333 |
| Nod 0.75x | random_forest | 0.0250 |
| Nod 1x | logistic_regression | 0.0500 |
| Nod 1x | random_forest | 0.0528 |
| Original still reference | logistic_regression | 0.0167 |
| Original still reference | random_forest | 0.0083 |

The motion summary and anomaly summary are matched by generator condition/source cohort, but the historical sweep saved aggregate classifier counts, not per-case classifier predictions. Do not infer a joint count of 'predicted still AND anomaly flagged' from these separate marginal rates. The per-source anomaly scores are saved for audit.

## Quality, preprocessing and uncertainty

Pre-tag canonical/quality blocks in this addendum: 0. Planned and eligible denominators remain in all detector tables. A block is not a successful authentication rejection or semantic anomaly detection. All generated cases retain the clean source IDs, intended labels, original split, timestamps and tracking flags.

The reused historical classifier curves use their original generator-to-relative-pose preprocessing. New anomaly scoring uses the same quaternion normalization and binary32 canonical conversion as the frozen Tier-2 experiment before extracting its 48 relative-motion/time features. The input conventions are recorded separately; no new authenticated/classifier equivalence claim is made. Labels, source IDs, amplitude/speed settings and quality outcomes are not features.

Per-seed flag rates and sensitivity rates have two-sided 95% Clopper-Pearson intervals. One source contributes once to each condition; shared fixed device/session profiles limit independence. The intervals are descriptive conditional uncertainty, not cross-device or human-population confidence. The same paired source is reused across conditions, and seed repetitions are not independent datasets. Logistic-regression lbfgs fits are deterministic; identical seed outputs do not prove independent performance stability.

Low-amplitude nod labels remain the original intended task, not a claim of visually unambiguous observed motion. Conclusions are limited to cross-session synthetic data with fixed device profiles. No classifier or SNN is trained here; no threshold is retuned; no end-to-end session, latency, human recording or Quest transfer is evaluated.

## Artifacts

- `motion-sensitivity.csv`: historical LR/RF/SNN counts and rates, all model seeds/amplitudes/speeds/splits, with new descriptive intervals.
- `anomaly-sensitivity.csv`: fixed detector flag counts/rates, eligible denominators and intervals for legitimate nod variants and original still controls.
- `predictions.jsonl`: each variant's source identity, canonical quality outcome and frozen detector scores/flags.
- `physical-observations.csv`, `nominal-conditions.json`, `trajectory-examples.json`, and figures: physical interpretation and paired examples.
- `manifest.json` and `COMPLETE`: historical input/model hashes, current reporting source hashes, settings and completion binding.

Example source IDs:

- test:nod: `sim-device-01-session-03-nod-001-window-000`
- test:still: `sim-device-01-session-03-still-001-window-000`
- validation:nod: `sim-device-01-session-02-nod-001-window-000`
- validation:still: `sim-device-01-session-02-still-001-window-000`
