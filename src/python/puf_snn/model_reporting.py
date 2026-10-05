"""Reconcile frozen classification counts and SNN checkpoint-selection evidence."""

from __future__ import annotations

import math

import numpy as np


LABELS = ("nod", "shake", "look_left_return", "look_right_return", "still")


def metrics_from_counts(matrix: list[list[int]]) -> dict:
    raw = np.asarray(matrix)
    if raw.shape != (5, 5) or raw.dtype.kind not in "iu" or np.any(raw < 0) or raw.sum() <= 0:
        raise ValueError("confusion matrix must contain nonnegative integer 5 x 5 counts")
    if any(isinstance(value, (bool, np.bool_)) for row in matrix for value in row):
        raise ValueError("boolean values are not confusion counts")
    values = raw.astype(np.int64)
    correct = np.diag(values)
    support = values.sum(axis=1)
    predicted = values.sum(axis=0)
    precision = np.divide(correct, predicted, out=np.zeros(5), where=predicted > 0)
    recall = np.divide(correct, support, out=np.zeros(5), where=support > 0)
    f1 = np.divide(2 * precision * recall, precision + recall, out=np.zeros(5), where=precision + recall > 0)
    return {"sample_count": int(values.sum()), "accuracy": float(correct.sum() / values.sum()),
            "macro_f1": float(f1.mean()), "confusion_matrix": values.tolist(),
            "per_class": {label: {"precision": float(precision[index]), "recall": float(recall[index]),
                                  "f1": float(f1[index]), "support": int(support[index])}
                          for index, label in enumerate(LABELS)}}


def reconcile_metrics(saved: dict) -> dict:
    calculated = metrics_from_counts(saved["confusion_matrix"])
    if saved["sample_count"] != calculated["sample_count"] or set(saved["per_class"]) != set(LABELS):
        raise ValueError("saved sample count or class set differs from confusion counts")
    for field in ("accuracy", "macro_f1"):
        if not math.isfinite(saved[field]) or abs(saved[field] - calculated[field]) > 1e-10:
            raise ValueError(f"saved {field} differs from confusion counts")
    for label in LABELS:
        for field in ("precision", "recall", "f1", "support"):
            value = saved["per_class"][label][field]
            if not math.isfinite(value) or abs(value - calculated["per_class"][label][field]) > 1e-10:
                raise ValueError(f"saved {label} {field} differs from confusion counts")
    return calculated


def snn_parameter_count(hidden_neurons: int) -> int:
    if isinstance(hidden_neurons, bool) or hidden_neurons not in (32, 64):
        raise ValueError("only the frozen 32/64 architectures are supported")
    # 7->H with bias, H->H without bias, H->5 with bias.
    return hidden_neurons * hidden_neurons + 13 * hidden_neurons + 5


def training_decision(history: list[dict], config: dict, run: dict) -> dict:
    training = config["training"]
    maximum = training["maximum_epochs"]
    patience = training["early_stopping_patience"]
    if maximum <= 0 or patience <= 0 or not history or len(history) > maximum:
        raise ValueError("invalid or empty training history")
    if run["seed"] not in training["random_seeds"]:
        raise ValueError("initialization seed is not in the frozen configuration")
    index = training["random_seeds"].index(run["seed"])
    if run["training_seed"] != training["training_seeds"][index]:
        raise ValueError("training seed differs from its recorded initialization pair")
    if run["trainable_parameters"] != snn_parameter_count(config["model"]["hidden_neurons"]):
        raise ValueError("recorded parameter count differs from the frozen architecture")
    best, best_epoch, stale = -1.0, 0, 0
    for index, row in enumerate(history, start=1):
        if row["epoch"] != index:
            raise ValueError("training epochs must be consecutive starting at one")
        for field in ("training_loss", "validation_accuracy", "validation_macro_f1"):
            if not math.isfinite(row[field]) or row[field] < 0:
                raise ValueError("training history contains invalid observations")
        if row["validation_macro_f1"] > 1 or row["validation_accuracy"] > 1:
            raise ValueError("validation metric is outside [0, 1]")
        score = row["validation_macro_f1"]
        if score > best + 1e-12:
            best, best_epoch, stale = score, index, 0
        else:
            stale += 1
        if stale >= patience and index != len(history):
            raise ValueError("history continued beyond the documented stopping rule")
    if best_epoch != run["best_epoch"] or len(history) != run["epochs_completed"]:
        raise ValueError("selected/stopping epoch differs from saved history")
    if abs(best - run["validation"]["macro_f1"]) > 1e-10:
        raise ValueError("selected checkpoint validation score differs from history")
    if stale >= patience:
        reason = f"no validation macro-F1 improvement > 1e-12 for {patience} consecutive epochs"
    elif len(history) == maximum:
        reason = "maximum epoch limit reached"
    else:
        raise ValueError("history ended without the configured stopping condition")
    return {"initialization_seed": run["seed"], "training_seed": run["training_seed"],
            "selected_epoch": best_epoch, "stopping_epoch": len(history),
            "best_validation_macro_f1": best, "epochs_without_improvement": stale,
            "stopping_reason": reason, "maximum_epochs_reached": len(history) == maximum}


def check_refit_counts(actual: list[list[int]], saved: dict) -> None:
    frozen = reconcile_metrics(saved)
    if metrics_from_counts(actual)["confusion_matrix"] != frozen["confusion_matrix"]:
        raise ValueError("fixed storage refit differs from frozen results; do not tune or overwrite them")


def validate_refit_complexity(actual: dict, saved: dict) -> None:
    for field in ("trainable_parameters", "trees", "nodes", "leaves"):
        if actual.get(field) != saved.get(field):
            raise ValueError(f"fixed storage refit {field} differs from the historical fit")


def validation_selected_width(results: dict[int, dict]) -> int:
    if set(results) != {32, 64}:
        raise ValueError("the predefined comparison must contain exactly widths 32 and 64")
    means = {width: np.mean([reconcile_metrics(run["validation"])["macro_f1"]
                            for run in summary["per_seed"]]) for width, summary in results.items()}
    if not all(len(summary["per_seed"]) == 3 for summary in results.values()):
        raise ValueError("each architecture must retain all three recorded seeds")
    # A deterministic smaller-width tie policy; no test result is read here.
    return max(sorted(means), key=means.get)


def per_class_rows(family: str, seed: int, split: str, saved: dict) -> list[dict]:
    values = reconcile_metrics(saved)
    return [{"model": family, "seed": seed, "split": split, "class": label, **values["per_class"][label]}
            for label in LABELS]
