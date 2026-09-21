"""
this script runs the Week 3 checks requested for the conventional classifiers
it audits the input, checks leakage, compares feature groups, checks repeated trajectories, and runs five model seeds
it also records laptop timing with clear boundaries and does not train an SNN
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, pairwise_distances
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIRECTORY = ROOT / "src" / "python" / "scripts"
sys.path.insert(0, str(SCRIPT_DIRECTORY))

import train_baselines as baseline


LABELS = baseline.LABELS
DISPLAY_LABELS = baseline.DISPLAY_LABELS
CHANNELS = (
    {
        "name": "relative_position_x",
        "unit": "meters",
        "source": "position_m[0] minus the first sample's position_m[0]",
    },
    {
        "name": "relative_position_y",
        "unit": "meters",
        "source": "position_m[1] minus the first sample's position_m[1]",
    },
    {
        "name": "relative_position_z",
        "unit": "meters",
        "source": "position_m[2] minus the first sample's position_m[2]",
    },
    {
        "name": "relative_orientation_x",
        "unit": "dimensionless quaternion component",
        "source": "normalized, sign-continuous orientation relative to the first orientation",
    },
    {
        "name": "relative_orientation_y",
        "unit": "dimensionless quaternion component",
        "source": "normalized, sign-continuous orientation relative to the first orientation",
    },
    {
        "name": "relative_orientation_z",
        "unit": "dimensionless quaternion component",
        "source": "normalized, sign-continuous orientation relative to the first orientation",
    },
    {
        "name": "relative_orientation_w",
        "unit": "dimensionless quaternion component",
        "source": "normalized, sign-continuous orientation relative to the first orientation",
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "generated" / "synthetic-windows.jsonl")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "pilot.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "week-3" / "keegan")
    parser.add_argument("--machine-model", required=True, help="Human-readable workstation model for the timing record.")
    parser.add_argument("--seeds", nargs="+", type=int, default=[7, 17, 27, 37, 47])
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--timed-windows", type=int, default=600, help="Number of individual test windows timed per boundary and model seed.")
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_value(*arguments: str) -> str | None:
    try:
        result = subprocess.run(["git", "-C", str(ROOT), *arguments], check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def metric_record(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)),
    }


def summarize(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "mean": float(np.mean(array)),
        "standard_deviation": float(np.std(array, ddof=1)) if len(array) > 1 else 0.0,
        "minimum": float(np.min(array)),
        "maximum": float(np.max(array)),
    }


def latency_summary(values_ms: list[float]) -> dict[str, float | int | str]:
    values = np.asarray(values_ms, dtype=np.float64)
    return {
        "unit": "milliseconds",
        "count": int(len(values)),
        "mean_ms": float(np.mean(values)),
        "median_ms": float(np.median(values)),
        "p95_ms": float(np.percentile(values, 95)),
        "maximum_ms": float(np.max(values)),
    }


def distribution_summary(values: list[float]) -> dict[str, float | int]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": int(len(array)),
        "minimum": float(np.min(array)),
        "p05": float(np.percentile(array, 5)),
        "median": float(np.median(array)),
        "mean": float(np.mean(array)),
        "p95": float(np.percentile(array, 95)),
        "maximum": float(np.max(array)),
    }


def timed_calls(values: list[Any], operation: Callable[[Any], Any], warmup_count: int, timed_count: int) -> dict[str, float | int | str]:
    if not values:
        raise ValueError("cannot time an empty input list")
    if warmup_count < 0 or timed_count <= 0:
        raise ValueError("warmup must be nonnegative and timed count must be positive")

    for index in range(warmup_count):
        operation(values[index % len(values)])

    elapsed_ms = []
    for index in range(timed_count):
        item = values[index % len(values)]
        start = time.perf_counter_ns()
        operation(item)
        end = time.perf_counter_ns()
        elapsed_ms.append((end - start) / 1_000_000.0)

    summary = latency_summary(elapsed_ms)
    summary["timer"] = "time.perf_counter_ns"
    summary["warmup_count"] = warmup_count
    return summary


def build_arrays(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_split: dict[str, dict[str, list[Any]]] = {
        name: {"records": [], "matrices": [], "labels": []}
        for name in ("train", "validation", "test")
    }

    for record in records:
        split = record["split"]
        matrix = baseline.record_to_features(record).reshape(baseline.EXPECTED_SAMPLES, baseline.FEATURES_PER_SAMPLE)
        by_split[split]["records"].append(record)
        by_split[split]["matrices"].append(matrix)
        by_split[split]["labels"].append(record["label"])

    result: dict[str, dict[str, Any]] = {}
    for split, values in by_split.items():
        matrices = np.stack(values["matrices"])
        result[split] = {
            "records": values["records"],
            "matrices": matrices,
            "features": matrices.reshape(len(matrices), -1),
            "labels": np.asarray(values["labels"]),
        }
    return result


def create_logistic(seed: int) -> Pipeline:
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=5000, solver="lbfgs", random_state=seed)),
        ]
    )


def create_forest(seed: int) -> RandomForestClassifier:
    return RandomForestClassifier(n_estimators=300, random_state=seed, n_jobs=1)


def fit_and_score(model: Any, training_features: np.ndarray, training_labels: np.ndarray, evaluation_features: np.ndarray, evaluation_labels: np.ndarray) -> dict[str, float]:
    model.fit(training_features, training_labels)
    return metric_record(evaluation_labels, model.predict(evaluation_features))


def feature_audit() -> dict[str, Any]:
    return {
        "shape": ["windows", 120, 7],
        "flattened_features_per_window": 840,
        "channels": CHANNELS,
        "included": ["trial-relative position", "trial-relative normalized quaternion orientation"],
        "excluded": [
            "label",
            "trial_id",
            "source_trial_id",
            "window_id",
            "session_id",
            "device_id",
            "class-name strings",
            "file name",
            "row order",
            "generator seed",
            "sequence_number",
            "timestamps",
            "tracking_valid",
            "velocity",
            "angular velocity",
            "acceleration",
            "imputation",
            "dimensionality reduction",
            "feature selection",
        ],
        "preprocessing": {
            "all_models": (
                "subtract first position; normalize quaternion signs; express orientation "
                "relative to first pose"
            ),
            "logistic_regression": (
                "StandardScaler is inside the sklearn Pipeline; model.fit is called on training "
                "only, then the unchanged fitted pipeline predicts validation/test"
            ),
            "random_forest": "no scaling or imputation",
        },
    }


def label_permutation_test(arrays: dict[str, dict[str, Any]], seeds: list[int]) -> dict[str, Any]:
    train_x = arrays["train"]["features"]
    train_y = arrays["train"]["labels"]
    test_x = arrays["test"]["features"]
    test_y = arrays["test"]["labels"]
    runs = []

    for seed in seeds:
        permuted = np.random.default_rng(seed).permutation(train_y)
        models = {
            "logistic_regression": create_logistic(seed),
            "random_forest": create_forest(seed),
        }
        run = {"seed": seed, "models": {}}
        for name, model in models.items():
            run["models"][name] = fit_and_score(model, train_x, permuted, test_x, test_y)
        runs.append(run)

    summary: dict[str, Any] = {}
    for name in ("logistic_regression", "random_forest"):
        summary[name] = {
            metric: summarize([run["models"][name][metric] for run in runs])
            for metric in ("accuracy", "macro_f1")
        }

    return {
        "chance_accuracy_for_balanced_five_class_task": 0.2,
        "training_labels_permuted_only": True,
        "runs": runs,
        "summary": summary,
    }


def ablation_test(arrays: dict[str, dict[str, Any]], seed: int) -> dict[str, Any]:
    groups = {
        "position_only": slice(0, 3),
        "orientation_only": slice(3, 7),
        "position_plus_orientation": slice(0, 7),
    }
    results: dict[str, Any] = {}

    for group_name, channel_slice in groups.items():
        train_matrix = arrays["train"]["matrices"][:, :, channel_slice]
        test_matrix = arrays["test"]["matrices"][:, :, channel_slice]
        train_x = train_matrix.reshape(len(train_matrix), -1)
        test_x = test_matrix.reshape(len(test_matrix), -1)
        train_y = arrays["train"]["labels"]
        test_y = arrays["test"]["labels"]

        results[group_name] = {
            "channels": (
                [item["name"] for item in CHANNELS[channel_slice]]
                if isinstance(channel_slice, slice)
                else []
            ),
            "logistic_regression": fit_and_score(create_logistic(seed), train_x, train_y, test_x, test_y),
            "random_forest": fit_and_score(create_forest(seed), train_x, train_y, test_x, test_y),
        }

    return {"seed": seed, "results": results}


def metadata_rows(records: list[dict[str, Any]]) -> np.ndarray:
    rows = []
    for record in records:
        session_index = int(record["session_id"].rsplit("-", 1)[-1])
        rows.append(
            [
                record["device_id"],
                session_index,
                record["sequence_number"],
                record["window_start_ns"],
                record["window_end_ns"],
            ]
        )
    return np.asarray(rows, dtype=object)


def metadata_only_test(arrays: dict[str, dict[str, Any]], seed: int) -> dict[str, Any]:
    train_records = arrays["train"]["records"]
    test_records = arrays["test"]["records"]
    train_y = arrays["train"]["labels"]
    test_y = arrays["test"]["labels"]

    safe_model = Pipeline(
        [
            (
                "metadata",
                ColumnTransformer(
                    [
                        ("device", OneHotEncoder(handle_unknown="ignore"), [0]),
                        ("numeric", StandardScaler(), [1, 2, 3, 4]),
                    ]
                ),
            ),
            (
                "classifier",
                LogisticRegression(max_iter=5000, solver="lbfgs", random_state=seed),
            ),
        ]
    )
    train_safe = metadata_rows(train_records)
    test_safe = metadata_rows(test_records)
    safe_model.fit(train_safe, train_y)
    safe_result = metric_record(test_y, safe_model.predict(test_safe))

    def identifier_text(record: dict[str, Any]) -> str:
        return " ".join([record["trial_id"], record["source_trial_id"], record["window_id"]])

    identifier_model = Pipeline(
        [
            (
                "text",
                TfidfVectorizer(analyzer="char", ngram_range=(2, 5), lowercase=True),
            ),
            (
                "classifier",
                LogisticRegression(max_iter=5000, solver="lbfgs", random_state=seed),
            ),
        ]
    )
    train_identifiers = [identifier_text(record) for record in train_records]
    test_identifiers = [identifier_text(record) for record in test_records]
    identifier_model.fit(train_identifiers, train_y)
    identifier_result = metric_record(test_y, identifier_model.predict(test_identifiers))

    return {
        "seed": seed,
        "safe_metadata": {
            "fields": [
                "device_id",
                "session index",
                "sequence_number",
                "window_start_ns",
                "window_end_ns",
            ],
            "result": safe_result,
        },
        "label_bearing_identifiers": {
            "fields": ["trial_id", "source_trial_id", "window_id"],
            "result": identifier_result,
            "interpretation": (
                "These identifiers contain the class name by construction. This intentionally "
                "unsafe control demonstrates why they must remain excluded from model input."
            ),
        },
    }


def hash_matrix(matrix: np.ndarray, decimals: int | None = None) -> str:
    value = np.round(matrix, decimals=decimals) if decimals is not None else matrix
    return hashlib.sha256(np.asarray(value, dtype=np.float64).tobytes()).hexdigest()


def duplicate_test(arrays: dict[str, dict[str, Any]]) -> dict[str, Any]:
    exact: dict[str, Any] = {}

    for label in LABELS:
        exact[label] = {}
        for group_name, channel_slice in {
            "orientation": slice(3, 7),
            "combined": slice(0, 7),
        }.items():
            hashes: dict[str, list[str]] = {}
            for split in ("train", "validation", "test"):
                matrices = arrays[split]["matrices"]
                labels = arrays[split]["labels"]
                hashes[split] = [
                    hash_matrix(matrix[:, channel_slice])
                    for matrix, item_label in zip(matrices, labels)
                    if item_label == label
                ]

            train_hashes = set(hashes["train"])
            exact[label][group_name] = {
                "unique_train": len(set(hashes["train"])),
                "unique_validation": len(set(hashes["validation"])),
                "unique_test": len(set(hashes["test"])),
                "test_windows_with_exact_train_match": sum(value in train_hashes for value in hashes["test"]),
            }

    train_x = arrays["train"]["features"]
    test_x = arrays["test"]["features"]
    scaler = StandardScaler().fit(train_x)
    standardized_train = scaler.transform(train_x)
    standardized_test = scaler.transform(test_x)
    distances = pairwise_distances(standardized_test, standardized_train, metric="euclidean")
    nearest_any = np.min(distances, axis=1)

    same_label_distances = []
    for index, label in enumerate(arrays["test"]["labels"]):
        mask = arrays["train"]["labels"] == label
        same_label_distances.append(float(np.min(distances[index, mask])))

    return {
        "exact_hashes": exact,
        "near_duplicate_distance": {
            "method": (
                "Euclidean distance after StandardScaler fit only on training payload features; "
                "zero means an exact standardized payload match"
            ),
            "nearest_training_window_any_label": distribution_summary(nearest_any.tolist()),
            "nearest_training_window_same_label": distribution_summary(same_label_distances),
            "test_windows_below_1e-6_same_label_distance": int(np.sum(np.asarray(same_label_distances) < 1e-6)),
        },
    }


def run_multiseed_baselines(arrays: dict[str, dict[str, Any]], seeds: list[int], warmup_count: int, timed_count: int) -> dict[str, Any]:
    train_x = arrays["train"]["features"]
    train_y = arrays["train"]["labels"]
    validation_x = arrays["validation"]["features"]
    validation_y = arrays["validation"]["labels"]
    test_x = arrays["test"]["features"]
    test_y = arrays["test"]["labels"]
    test_records = arrays["test"]["records"]
    test_feature_rows = [row.reshape(1, -1) for row in test_x]

    preprocessing_latency = timed_calls(test_records, baseline.record_to_features, warmup_count, timed_count)
    runs = []

    for seed in seeds:
        models = {
            "logistic_regression": create_logistic(seed),
            "random_forest": create_forest(seed),
        }
        run: dict[str, Any] = {"seed": seed, "models": {}}

        for model_name, model in models.items():
            training_start = time.perf_counter_ns()
            model.fit(train_x, train_y)
            training_ms = (time.perf_counter_ns() - training_start) / 1_000_000.0

            inference_latency = timed_calls(test_feature_rows, model.predict, warmup_count, timed_count)

            def preprocess_and_predict(record: dict[str, Any]) -> Any:
                features = baseline.record_to_features(record).reshape(1, -1)
                return model.predict(features)

            combined_latency = timed_calls(test_records, preprocess_and_predict, warmup_count, timed_count)

            run["models"][model_name] = {
                "training_latency_ms": float(training_ms),
                "validation": metric_record(validation_y, model.predict(validation_x)),
                "test": metric_record(test_y, model.predict(test_x)),
                "inference_only_latency": inference_latency,
                "preprocessing_plus_inference_latency": combined_latency,
            }

        runs.append(run)

    summary: dict[str, Any] = {}
    for model_name in ("logistic_regression", "random_forest"):
        summary[model_name] = {
            "validation_accuracy": summarize([run["models"][model_name]["validation"]["accuracy"] for run in runs]),
            "validation_macro_f1": summarize([run["models"][model_name]["validation"]["macro_f1"] for run in runs]),
            "test_accuracy": summarize([run["models"][model_name]["test"]["accuracy"] for run in runs]),
            "test_macro_f1": summarize([run["models"][model_name]["test"]["macro_f1"] for run in runs]),
            "inference_only_mean_ms_across_seeds": summarize([run["models"][model_name]["inference_only_latency"]["mean_ms"] for run in runs]),
            "inference_only_p95_ms_across_seeds": summarize([run["models"][model_name]["inference_only_latency"]["p95_ms"] for run in runs]),
            "inference_only_maximum_ms_across_seeds": summarize([run["models"][model_name]["inference_only_latency"]["maximum_ms"] for run in runs]),
            "preprocessing_plus_inference_p95_ms_across_seeds": summarize([run["models"][model_name]["preprocessing_plus_inference_latency"]["p95_ms"] for run in runs]),
        }

    return {
        "timing_scope": {
            "input": "synthetic in-memory JSON records",
            "unit_of_work": "one window per function/predict call",
            "loading_excluded": True,
            "training_excluded_from_inference_boundaries": True,
            "authentication_excluded": True,
            "anomaly_detection_excluded": True,
            "logging_excluded": True,
            "capture_window_excluded": True,
            "preprocessing_boundary": (
                "record_to_features only: relative position, quaternion normalization/sign "
                "continuity, relative orientation, flattening"
            ),
            "inference_boundary": "model.predict on one already-preprocessed 840-feature window",
            "combined_boundary": "record_to_features followed by model.predict for one window",
            "warmup_count": warmup_count,
            "timed_window_count": timed_count,
            "timer": "time.perf_counter_ns",
        },
        "preprocessing_only_latency": preprocessing_latency,
        "runs": runs,
        "summary": summary,
    }


def plot_trajectories(arrays: dict[str, dict[str, Any]], output_directory: Path) -> list[str]:
    selected: dict[tuple[str, str, str], tuple[dict[str, Any], np.ndarray]] = {}
    for split in ("train", "validation", "test"):
        for record, matrix in zip(arrays[split]["records"], arrays[split]["matrices"]):
            key = (record["label"], record["device_id"], record["session_id"])
            selected.setdefault(key, (record, matrix))

    time_axis = np.arange(120) / 60.0
    orientation_path = output_directory / "orientation-trajectories-by-class.png"
    position_path = output_directory / "position-trajectories-by-class.png"

    figure, axes = plt.subplots(5, 1, figsize=(11, 15), sharex=True)
    for label_index, label in enumerate(LABELS):
        axis = axes[label_index]
        component_index = 3 if label == "nod" else 4
        component_name = "relative quaternion x" if label == "nod" else "relative quaternion y"
        for (item_label, _, _), (record, matrix) in selected.items():
            if item_label != label:
                continue
            axis.plot(time_axis, matrix[:, component_index], alpha=0.32, linewidth=0.9, label=f"{record['device_id']}/{record['session_id'].rsplit('-', 1)[-1]}")
        axis.set_title(f"{label}: {component_name}")
        axis.set_ylabel("unitless")
        axis.grid(alpha=0.2)
    axes[-1].set_xlabel("time (seconds)")
    figure.suptitle("One orientation example per device and session for each class")
    figure.tight_layout()
    figure.savefig(orientation_path, dpi=180, bbox_inches="tight")
    plt.close(figure)

    figure, axes = plt.subplots(5, 1, figsize=(11, 15), sharex=True)
    for label_index, label in enumerate(LABELS):
        axis = axes[label_index]
        for (item_label, _, _), (record, matrix) in selected.items():
            if item_label != label:
                continue
            magnitude = np.linalg.norm(matrix[:, 0:3], axis=1)
            axis.plot(time_axis, magnitude, alpha=0.32, linewidth=0.9)
        axis.set_title(f"{label}: relative-position magnitude")
        axis.set_ylabel("meters")
        axis.grid(alpha=0.2)
    axes[-1].set_xlabel("time (seconds)")
    figure.suptitle("One position example per device and session for each class")
    figure.tight_layout()
    figure.savefig(position_path, dpi=180, bbox_inches="tight")
    plt.close(figure)

    return [orientation_path.name, position_path.name]


def markdown_number(value: float) -> str:
    return f"{value:.4f}"


def write_markdown(results: dict[str, Any], path: Path) -> None:
    lines = [
        "# Week 3 Baseline Diagnostics",
        "",
        "This report diagnoses the conventional classification baseline. It does not contain an SNN result.",
        "",
        "## Input audit",
        "",
        "The model input is exactly 120 time points by seven payload channels (840 flattened values).",
        "",
        "| Channel | Unit | Transformation |",
        "|---|---|---|",
    ]
    for channel in results["feature_audit"]["channels"]:
        lines.append(f"| {channel['name']} | {channel['unit']} | {channel['source']} |")

    lines.extend(
        [
            "",
            "Labels, identifiers, timestamps, tracking state, file names, row order, and generator seeds are excluded.",
            "Logistic-regression scaling is fit only on training data through its sklearn Pipeline.",
            "",
            "## Single-channel-group ablation",
            "",
            "| Features | Logistic test accuracy | Logistic test macro-F1 | Forest test accuracy | Forest test macro-F1 |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for name, record in results["ablation"]["results"].items():
        lines.append(
            f"| {name} | {markdown_number(record['logistic_regression']['accuracy'])} | "
            f"{markdown_number(record['logistic_regression']['macro_f1'])} | "
            f"{markdown_number(record['random_forest']['accuracy'])} | "
            f"{markdown_number(record['random_forest']['macro_f1'])} |"
        )

    permutation = results["label_permutation"]["summary"]
    metadata = results["metadata_only"]
    lines.extend(
        [
            "",
            "## Leakage controls",
            "",
            f"- Five-class chance accuracy: 0.2000.",
            f"- Permuted-label logistic mean test accuracy: {markdown_number(permutation['logistic_regression']['accuracy']['mean'])}.",
            f"- Permuted-label random-forest mean test accuracy: {markdown_number(permutation['random_forest']['accuracy']['mean'])}.",
            f"- Safe metadata-only logistic test accuracy: {markdown_number(metadata['safe_metadata']['result']['accuracy'])}.",
            f"- Label-bearing identifier-text test accuracy: {markdown_number(metadata['label_bearing_identifiers']['result']['accuracy'])}.",
            "",
            "The identifier-text control is intentionally unsafe: trial_id, source_trial_id, and window_id contain the class name. "
            "Its purpose is to prove why these strings must never enter the classifier.",
            "",
            "## Five-seed conventional baseline",
            "",
            "| Model | Test accuracy mean ± SD | Test macro-F1 mean ± SD | Inference p95 mean ± SD (ms) | Preprocess + inference p95 mean ± SD (ms) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for model_name, summary in results["multiseed_baselines"]["summary"].items():
        lines.append(
            f"| {model_name} | "
            f"{summary['test_accuracy']['mean']:.4f} ± {summary['test_accuracy']['standard_deviation']:.4f} | "
            f"{summary['test_macro_f1']['mean']:.4f} ± {summary['test_macro_f1']['standard_deviation']:.4f} | "
            f"{summary['inference_only_p95_ms_across_seeds']['mean']:.4f} ± "
            f"{summary['inference_only_p95_ms_across_seeds']['standard_deviation']:.4f} | "
            f"{summary['preprocessing_plus_inference_p95_ms_across_seeds']['mean']:.4f} ± "
            f"{summary['preprocessing_plus_inference_p95_ms_across_seeds']['standard_deviation']:.4f} |"
        )

    exact_hashes = results["duplicates"]["exact_hashes"]
    exact_orientation_matches = sum(group["orientation"]["test_windows_with_exact_train_match"] for group in exact_hashes.values())
    exact_combined_matches = sum(group["combined"]["test_windows_with_exact_train_match"] for group in exact_hashes.values())
    near_matches = results["duplicates"]["near_duplicate_distance"][
        "test_windows_below_1e-6_same_label_distance"
    ]

    lines.extend(
        [
            "",
            "## Timing interpretation",
            "",
            "These are per-window laptop/Python measurements on synthetic in-memory records. Loading, training, "
            "authentication, anomaly detection, logging, and the two-second capture interval are excluded. "
            "The JSON artifact contains mean, median, p95, maximum, warm-up count, timed count, timer, workstation, "
            "and software versions for every seed.",
            "",
            "## Duplicate and near-duplicate interpretation",
            "",
            f"- Test windows with an exact training orientation match: {exact_orientation_matches}.",
            f"- Test windows with an exact training combined-payload match: {exact_combined_matches}.",
            f"- Test windows with same-label standardized distance below 1e-6: {near_matches}.",
            "",
            "The JSON artifact contains the per-class hash counts and full nearest-distance summaries. Exact "
            "orientation matches on the original data identify a reused synthetic template; zero matches on the "
            "revised data confirm that the added trial-level variation removed exact cross-split copies.",
            "",
            "## Figures",
            "",
        ]
    )
    for figure in results["figures"]:
        lines.append(f"- `{figure}`")

    lines.extend(
        [
            "",
            "## Scope statement",
            "",
            "The results validate or diagnose this software generator and preprocessing pipeline only. They do not "
            "establish expected performance on real Quest motion, cross-person generalization, embedded latency, or "
            "physical-device effects.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    input_path = resolve_path(args.input)
    config_path = resolve_path(args.config)
    output_directory = resolve_path(args.output)
    output_directory.mkdir(parents=True, exist_ok=True)

    if len(args.seeds) < 5:
        raise ValueError("faculty requested at least five random seeds")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    records = baseline.load_records(input_path)
    arrays = build_arrays(records)
    figures = plot_trajectories(arrays, output_directory)

    results = {
        "experiment": "week 3 conventional-classification diagnostics",
        "scope": "diagnostics and conventional baselines only; no SNN",
        "input": {
            "path": str(input_path),
            "sha256": sha256_file(input_path),
            "window_count": len(records),
            "split_counts": dict(Counter(record["split"] for record in records)),
            "label_counts": dict(Counter(record["label"] for record in records)),
        },
        "configuration": {
            "path": str(config_path),
            "sha256": sha256_file(config_path),
            "generator_seed": config["project"]["random_seed"],
            "generation_method": config["synthetic_motion"]["generation_method"],
            "model_seeds": args.seeds,
        },
        "feature_audit": feature_audit(),
        "ablation": ablation_test(arrays, args.seeds[0]),
        "label_permutation": label_permutation_test(arrays, args.seeds),
        "metadata_only": metadata_only_test(arrays, args.seeds[0]),
        "duplicates": duplicate_test(arrays),
        "multiseed_baselines": run_multiseed_baselines(arrays, args.seeds, args.warmup, args.timed_windows),
        "figures": figures,
        "environment": {
            "machine_model": args.machine_model,
            "processor": platform.processor(),
            "operating_system": platform.platform(),
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
            "matplotlib": matplotlib.__version__,
            "implementation": "Python scikit-learn software prototype",
        },
        "provenance": {
            "git_commit": git_value("rev-parse", "HEAD"),
            "git_status_porcelain": git_value("status", "--short"),
        },
    }

    json_path = output_directory / "baseline-diagnostics.json"
    markdown_path = output_directory / "baseline-diagnostics.md"
    json_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    write_markdown(results, markdown_path)

    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    for figure in figures:
        print(f"Wrote {output_directory / figure}")


if __name__ == "__main__":
    main()
