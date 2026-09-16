# Synthetic data evidence

Status: passed
Generator seed: 7
Code commit: `3936cc60377368dead0bbfa692df113cb41c7798`
Working tree clean before report generation: True
Dataset SHA-256: `0e29a1091db2a82968e75ef879934cb3164c38f4df874766f2c29c76b3231f00`
Matches regeneration with the saved config: True

This is a synthetic software check. Group ids do not represent calibrated headset differences.
The complete configuration, source hashes, environment, errors, test output, and identifier lists are in [keegan-evidence.json](keegan-evidence.json).

## Class counts by device and session

| Device | Session | Split | nod | shake | look_left_return | look_right_return | still | Total |
|---|---|---|---:|---:|---:|---:|---:|---:|
| sim-device-01 | sim-device-01-session-01 | train | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-01 | sim-device-01-session-02 | validation | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-01 | sim-device-01-session-03 | test | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-02 | sim-device-02-session-01 | train | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-02 | sim-device-02-session-02 | validation | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-02 | sim-device-02-session-03 | test | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-03 | sim-device-03-session-01 | train | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-03 | sim-device-03-session-02 | validation | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-03 | sim-device-03-session-03 | test | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-04 | sim-device-04-session-01 | train | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-04 | sim-device-04-session-02 | validation | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-04 | sim-device-04-session-03 | test | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-05 | sim-device-05-session-01 | train | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-05 | sim-device-05-session-02 | validation | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-05 | sim-device-05-session-03 | test | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-06 | sim-device-06-session-01 | train | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-06 | sim-device-06-session-02 | validation | 20 | 20 | 20 | 20 | 20 | 100 |
| sim-device-06 | sim-device-06-session-03 | test | 20 | 20 | 20 | 20 | 20 | 100 |

## Data quality

| Measurement | Observed value |
|---|---:|
| Loaded windows | 1800 |
| Saved samples | 216000 |
| Missing saved sample slots | 0 |
| Extra saved samples | 0 |
| Invalid tracking flags | 0 |
| Windows failing individual validation | 0 |
| Dataset validation errors | 0 |
| Resampling events in verified generator | 0 |

Missing saved slots means fewer than 120 samples in a saved window. Raw acquisition loss is not measured because no raw capture occurred.
Individual validation rejection is a data-quality result, not an authentication result. Dataset errors can also describe relationships between otherwise valid records.

## Split identifiers

| Split | Windows | Source trials | Trials | Sessions | Devices | Human participants |
|---|---:|---:|---:|---:|---:|---:|
| train | 600 | 600 | 600 | 6 | 6 | 0 |
| validation | 600 | 600 | 600 | 6 | 6 | 0 |
| test | 600 | 600 | 600 | 6 | 6 | 0 |

| Split pair | Identifier | Prohibited overlap? | Shared ids |
|---|---|---|---:|
| train / validation | window_id | True | 0 |
| train / validation | source_trial_id | True | 0 |
| train / validation | trial_id | True | 0 |
| train / validation | session_id | True | 0 |
| train / validation | device_id | False | 6 |
| train / validation | participant_id | False | 0 |
| train / validation | profile_id | False | 6 |
| train / test | window_id | True | 0 |
| train / test | source_trial_id | True | 0 |
| train / test | trial_id | True | 0 |
| train / test | session_id | True | 0 |
| train / test | device_id | False | 6 |
| train / test | participant_id | False | 0 |
| train / test | profile_id | False | 6 |
| validation / test | window_id | True | 0 |
| validation / test | source_trial_id | True | 0 |
| validation / test | trial_id | True | 0 |
| validation / test | session_id | True | 0 |
| validation / test | device_id | False | 6 |
| validation / test | participant_id | False | 0 |
| validation / test | profile_id | False | 6 |

Device ids overlap intentionally. Profile ids are aliases for these device groups; there are no separate human participant profiles.
Unique ids alone do not prove statistical independence or prevent shared motion-template shortcuts.

## Automated tests

| Test | Purpose | Expected | Actual |
|---|---|---|---|
| test_data.DataTests.test_generated_identifiers_match_their_records | device, session, trial, label, source, and window ids agree | Assertions pass | passed |
| test_data.DataTests.test_generated_quaternions_are_normalized_and_continuous | all generated quaternions have unit norm and continuous signs | Assertions pass | passed |
| test_data.DataTests.test_generated_records_pass_validation | clean records pass the schema, quality rules, and configured identifier checks | Assertions pass | passed |
| test_data.DataTests.test_generated_windows_have_120_ordered_samples | every fixed-grid window has 120 consecutive indexes and increasing times | Assertions pass | passed |
| test_data.DataTests.test_generator_is_deterministic_and_balanced | same seed reproduces records and every device-session has balanced class counts | Assertions pass | passed |
| test_data.DataTests.test_generator_rejects_unimplemented_device_effects | enabling an unimplemented effect produces an error instead of a false claim | Assertions pass | passed |
| test_data.DataTests.test_schema_rejects_wrong_types_and_extra_fields | schema types, required fields, enums, and extra-field rules are enforced | Assertions pass | passed |
| test_data.DataTests.test_tracking_threshold_accepts_114_and_rejects_113 | exactly 95 percent tracking passes and a lower fraction fails | Assertions pass | passed |
| test_data.DataTests.test_validator_catches_bad_quaternion | an invalid zero quaternion is rejected | Assertions pass | passed |
| test_data.DataTests.test_validator_catches_id_mismatch | changing a device without its session and trial relationships fails | Assertions pass | passed |
| test_data.DataTests.test_validator_catches_missing_group | removing a whole session cannot pass just because the remaining records are valid | Assertions pass | passed |
| test_data.DataTests.test_validator_catches_quaternion_sign_flip | an isolated equivalent quaternion sign flip is rejected | Assertions pass | passed |
| test_data.DataTests.test_validator_catches_timestamp_gap_and_order | large gaps and repeated timestamps are rejected | Assertions pass | passed |
| test_data.DataTests.test_validator_rejects_nonfinite_position | nan and infinity cannot pass as valid position values | Assertions pass | passed |
| test_data.DataTests.test_validator_rejects_short_window | a saved window with only 119 samples fails the schema | Assertions pass | passed |
| test_splits.SplitTests.test_clean_dataset_has_no_prohibited_split_overlap | window, trial, source-trial, and session ids are disjoint between splits | Assertions pass | passed |
| test_splits.SplitTests.test_validator_catches_duplicate_window | reusing a window id across records is rejected | Assertions pass | passed |
| test_splits.SplitTests.test_validator_catches_sequence_gap | a missing sequence number in the saved clean session is rejected | Assertions pass | passed |
| test_splits.SplitTests.test_validator_catches_session_split_leakage | placing part of a session in another split is rejected | Assertions pass | passed |
| test_splits.SplitTests.test_validator_catches_source_trial_leakage | a source-trial id shared between training and testing is rejected | Assertions pass | passed |
| test_splits.SplitTests.test_validator_catches_whole_session_in_wrong_split | moving a complete session to the wrong configured split is rejected | Assertions pass | passed |

Tests run: 21. Full failure details are saved in the JSON if any test fails.

## Figures

![Representative trajectories](representative-trajectories.png)

![Device and session groups](device-session-variability.png)

## Interpretation and limits

- The current generator directly constructs 120 samples; it does not test a resampling algorithm.
- Stable device and session effects are disabled and unimplemented. Position differences in the group figure are trial noise.
- Nod, shake, and look-and-return angles share fixed templates within each class. This makes the class task easy and limits generalization claims.
- The still class has a small random walk in orientation, and all classes have Gaussian position noise.
- The split separates complete synthetic sessions but does not demonstrate cross-device, cross-person, or real-Quest generalization.
- Inspect the figures before making any claim about physical plausibility; the generator is not calibrated against approved human motion data.
