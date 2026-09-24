"""
this file calculates SNN classification measurements confusion matrices and latency
all latency values measure one complete motion window per inference call
"""

from __future__ import annotations

import time

from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import torch

from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support

from .dataset import LABELS


DISPLAY_LABELS = (
    "nod",
    "shake",
    "look left",
    "look right",
    "still",
)


def calculate_metrics(expected_indexes: np.ndarray, predicted_indexes: np.ndarray) -> dict:
    expected_indexes = np.asarray(expected_indexes, dtype=np.int64)
    predicted_indexes = np.asarray(predicted_indexes, dtype=np.int64)

    if expected_indexes.ndim != 1 or predicted_indexes.ndim != 1 or len(expected_indexes) == 0 or len(expected_indexes) != len(predicted_indexes):
        raise ValueError("expected and predicted indexes must have the same nonzero one-dimensional shape")

    label_indexes = np.arange(len(LABELS))
    precision, recall, class_f1, support = precision_recall_fscore_support(expected_indexes, predicted_indexes, labels=label_indexes, zero_division=0)
    matrix = confusion_matrix(expected_indexes, predicted_indexes, labels=label_indexes)

    return {
        "sample_count": int(len(expected_indexes)),
        "accuracy": float(accuracy_score(expected_indexes, predicted_indexes)),
        "macro_f1": float(f1_score(expected_indexes, predicted_indexes, labels=label_indexes, average="macro", zero_division=0)),
        "per_class": {
            label: {
                "precision": float(precision[label_index]),
                "recall": float(recall[label_index]),
                "f1": float(class_f1[label_index]),
                "support": int(support[label_index]),
            }
            for label_index, label in enumerate(LABELS)
        },
        "confusion_matrix": matrix.tolist(),
    }


def predict_indexes(model: torch.nn.Module, sequences: np.ndarray, batch_size: int, device: torch.device) -> np.ndarray:
    model.eval()
    predictions = []

    with torch.inference_mode():
        for start_index in range(0, len(sequences), batch_size):
            batch = torch.from_numpy(sequences[start_index:start_index + batch_size]).to(device)
            scores = model(batch)
            predictions.append(scores.argmax(dim=1).cpu().numpy())

    return np.concatenate(predictions)


def measure_inference_latency(model: torch.nn.Module, sequences: np.ndarray, warmup_windows: int, timed_windows: int, device: torch.device) -> dict:
    if len(sequences) == 0:
        raise ValueError("latency measurement requires at least one sequence")

    model.eval()

    with torch.inference_mode():
        for window_index in range(warmup_windows):
            sequence = torch.from_numpy(sequences[window_index % len(sequences)]).unsqueeze(0).to(device)
            model(sequence)

        latency_values_ms = []

        for window_index in range(timed_windows):
            sequence = torch.from_numpy(sequences[window_index % len(sequences)]).unsqueeze(0).to(device)
            start_time = time.perf_counter_ns()
            model(sequence)
            end_time = time.perf_counter_ns()
            latency_values_ms.append((end_time - start_time) / 1_000_000.0)

    latency_array = np.asarray(latency_values_ms, dtype=np.float64)

    return {
        "unit": "milliseconds",
        "timing_method": "time.perf_counter_ns",
        "prediction_method": "one 120-sample window per model call",
        "warmup_count": int(warmup_windows),
        "timed_prediction_count": int(timed_windows),
        "median_ms": float(np.median(latency_array)),
        "p95_ms": float(np.percentile(latency_array, 95)),
        "mean_ms": float(np.mean(latency_array)),
        "minimum_ms": float(np.min(latency_array)),
        "maximum_ms": float(np.max(latency_array)),
    }


def save_confusion_matrix(matrix: list[list[int]], title: str, output_path: Path) -> None:
    matrix_array = np.asarray(matrix, dtype=np.int64)

    if matrix_array.shape != (len(LABELS), len(LABELS)):
        raise ValueError("confusion matrix must contain one row and column per class")

    figure, axis = plt.subplots(figsize=(7, 6))
    image = axis.imshow(matrix_array, interpolation="nearest", cmap="Blues")
    axis.set_title(title)
    axis.set_xlabel("predicted class")
    axis.set_ylabel("actual class")
    axis.set_xticks(range(len(DISPLAY_LABELS)), DISPLAY_LABELS, rotation=30, ha="right")
    axis.set_yticks(range(len(DISPLAY_LABELS)), DISPLAY_LABELS)
    figure.colorbar(image, ax=axis)
    threshold = matrix_array.max() / 2.0

    for row_index in range(matrix_array.shape[0]):
        for column_index in range(matrix_array.shape[1]):
            value = matrix_array[row_index, column_index]
            text_color = "white" if value > threshold else "black"
            axis.text(column_index, row_index, str(value), ha="center", va="center", color=text_color)

    figure.tight_layout()
    figure.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(figure)
