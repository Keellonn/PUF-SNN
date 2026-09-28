# SNN detailed results

The per-seed evidence below is read from the saved baseline, not a newly claimed training run.

| Seed | Best epoch | Stopping epoch |
|---:|---:|---:|
| 7 | 11 | 19 |
| 17 | 26 | 34 |
| 27 | 30 | 38 |

## Seed 7

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| nod | 0.9091 | 0.8333 | 0.8696 | 120 |
| shake | 0.8173 | 0.7083 | 0.7589 | 120 |
| look_left_return | 0.8504 | 0.9000 | 0.8745 | 120 |
| look_right_return | 0.8947 | 0.8500 | 0.8718 | 120 |
| still | 0.6966 | 0.8417 | 0.7623 | 120 |

Confusion matrix: rows are true labels; columns are predicted labels in the configured class order.

```text
[100, 0, 1, 0, 19]
[2, 85, 10, 7, 16]
[3, 6, 108, 0, 3]
[0, 12, 0, 102, 6]
[5, 1, 8, 5, 101]
```

## Seed 17

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| nod | 0.9091 | 0.8333 | 0.8696 | 120 |
| shake | 0.9474 | 0.7500 | 0.8372 | 120 |
| look_left_return | 0.8692 | 0.9417 | 0.9040 | 120 |
| look_right_return | 0.8594 | 0.9167 | 0.8871 | 120 |
| still | 0.7299 | 0.8333 | 0.7782 | 120 |

Confusion matrix: rows are true labels; columns are predicted labels in the configured class order.

```text
[100, 1, 2, 1, 16]
[2, 90, 3, 12, 13]
[2, 2, 113, 0, 3]
[3, 2, 0, 110, 5]
[3, 0, 12, 5, 100]
```

## Seed 27

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| nod | 0.8966 | 0.8667 | 0.8814 | 120 |
| shake | 0.8644 | 0.8500 | 0.8571 | 120 |
| look_left_return | 0.9256 | 0.9333 | 0.9295 | 120 |
| look_right_return | 0.9068 | 0.8917 | 0.8992 | 120 |
| still | 0.7480 | 0.7917 | 0.7692 | 120 |

Confusion matrix: rows are true labels; columns are predicted labels in the configured class order.

```text
[104, 0, 0, 0, 16]
[2, 102, 3, 6, 7]
[1, 2, 112, 0, 5]
[1, 8, 0, 107, 4]
[8, 6, 6, 5, 95]
```

## Pooled predictions

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| nod | 0.9048 | 0.8444 | 0.8736 | 360 |
| shake | 0.8738 | 0.7694 | 0.8183 | 360 |
| look_left_return | 0.8810 | 0.9250 | 0.9024 | 360 |
| look_right_return | 0.8861 | 0.8861 | 0.8861 | 360 |
| still | 0.7237 | 0.8222 | 0.7698 | 360 |

Confusion matrix: rows are true labels; columns are predicted labels in the configured class order.

```text
[304, 1, 3, 1, 51]
[6, 277, 16, 25, 36]
[6, 10, 333, 0, 11]
[4, 22, 0, 319, 15]
[16, 7, 26, 15, 296]
```

pooled model predictions on repeated source windows; not independent new recordings

The saved latency is forward-only: normalization, tensor creation/transfer, argmax and CPU output decoding, authentication, audit and capture are excluded. Training batch size is 32; timing batch size is one.

Conclusion: The separately seeded 64-neuron reference has mean test macro-F1 0.8500 versus 0.9032 for the matched logistic baseline, a 5.32-percentage-point gap that misses the provisional five-point criterion. The predefined 32-neuron architecture ablation has macro-F1 0.8619 and a 4.12-point gap, meeting the criterion; selection used validation macro-F1 only. Neither SNN outperforms the conventional baselines. The 64-neuron reference remains the baseline. No measured energy advantage or real-world robustness is established.

Reporting note: This paragraph corrects the original fixed conclusion without changing the saved training histories, checkpoints, confusion matrices or numerical metrics. The report's original and amended SHA-256 values are recorded in manifest.json.
