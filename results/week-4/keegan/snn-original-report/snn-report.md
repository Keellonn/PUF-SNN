# SNN detailed results

The per-seed evidence below is read from the saved baseline, not a newly claimed training run.

| Seed | Best epoch | Stopping epoch |
|---:|---:|---:|
| 7 | 20 | 28 |
| 17 | 25 | 33 |
| 27 | 22 | 30 |

## Seed 7

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| nod | 0.9608 | 0.8167 | 0.8829 | 120 |
| shake | 0.8491 | 0.7500 | 0.7965 | 120 |
| look_left_return | 0.9032 | 0.9333 | 0.9180 | 120 |
| look_right_return | 0.8385 | 0.9083 | 0.8720 | 120 |
| still | 0.7319 | 0.8417 | 0.7829 | 120 |

Confusion matrix: rows are true labels; columns are predicted labels in the configured class order.

```text
[98, 2, 1, 0, 19]
[0, 90, 6, 15, 9]
[0, 4, 112, 0, 4]
[0, 6, 0, 109, 5]
[4, 4, 5, 6, 101]
```

## Seed 17

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| nod | 0.8803 | 0.8583 | 0.8692 | 120 |
| shake | 0.9300 | 0.7750 | 0.8455 | 120 |
| look_left_return | 0.8571 | 0.9500 | 0.9012 | 120 |
| look_right_return | 0.8790 | 0.9083 | 0.8934 | 120 |
| still | 0.7540 | 0.7917 | 0.7724 | 120 |

Confusion matrix: rows are true labels; columns are predicted labels in the configured class order.

```text
[103, 1, 3, 1, 12]
[3, 93, 3, 9, 12]
[1, 3, 114, 0, 2]
[3, 3, 0, 109, 5]
[7, 0, 13, 5, 95]
```

## Seed 27

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| nod | 0.8889 | 0.8667 | 0.8776 | 120 |
| shake | 0.9100 | 0.7583 | 0.8273 | 120 |
| look_left_return | 0.9180 | 0.9333 | 0.9256 | 120 |
| look_right_return | 0.8527 | 0.9167 | 0.8835 | 120 |
| still | 0.7424 | 0.8167 | 0.7778 | 120 |

Confusion matrix: rows are true labels; columns are predicted labels in the configured class order.

```text
[104, 0, 1, 1, 14]
[2, 91, 3, 13, 11]
[0, 3, 112, 0, 5]
[1, 5, 0, 110, 4]
[10, 1, 6, 5, 98]
```

## Pooled predictions

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| nod | 0.9077 | 0.8472 | 0.8764 | 360 |
| shake | 0.8954 | 0.7611 | 0.8228 | 360 |
| look_left_return | 0.8918 | 0.9389 | 0.9147 | 360 |
| look_right_return | 0.8564 | 0.9111 | 0.8829 | 360 |
| still | 0.7424 | 0.8167 | 0.7778 | 360 |

Confusion matrix: rows are true labels; columns are predicted labels in the configured class order.

```text
[305, 3, 5, 2, 45]
[5, 274, 12, 37, 32]
[1, 10, 338, 0, 11]
[4, 14, 0, 328, 14]
[21, 5, 24, 16, 294]
```

pooled model predictions on repeated source windows; not independent new recordings

The saved latency is forward-only: normalization, tensor creation/transfer, argmax and CPU output decoding, authentication, audit and capture are excluded. Training batch size is 32; timing batch size is one.

Conclusion: competitive but not superior in this CPU software prototype. No measured energy advantage or real-world robustness is established.
