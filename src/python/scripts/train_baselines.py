"""
this file trains and evaluates the first conventional head-motion classifiers
it
- loads the generated Quest-like motion windows
- converts each 120-sample window into position and quaternion features
- keeps training, validation, and testing sessions separate
- trains logistic regression and random forest models
- measures accuracy, macro-f1, per-class results, and inference latency
- saves the results summary and confusion matrices in the week-3 results folder
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time

from collections import Counter
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


# keep the label order the same in every result
LABELS = (
    "nod",
    "shake",
    "look_left_return",
    "look_right_return",
    "still",
)

DISPLAY_LABELS = (
    "nod",
    "shake",
    "look left",
    "look right",
    "still",
)

EXPECTED_SAMPLES = 120
FEATURES_PER_SAMPLE = 7

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_INPUT_PATH = (
    REPOSITORY_ROOT
    / "data"
    / "generated"
    / "synthetic-windows.jsonl"
)

DEFAULT_OUTPUT_DIRECTORY = (
    REPOSITORY_ROOT
    / "results"
    / "week-3"
    / "keegan"
)


# load one window from each line of the dataset
def load_records(input_path: Path) -> list[dict]:
    if not input_path.exists():
        raise FileNotFoundError(
            f"dataset not found: {input_path}\n"
            "run generate_data.py before training the classifiers"
        )

    records = []

    with input_path.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            stripped_line = line.strip()

            if not stripped_line:
                continue

            try:
                record = json.loads(stripped_line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"invalid json on line {line_number}: {error}"
                ) from error

            records.append(record)

    if not records:
        raise ValueError("the dataset is empty")

    return records


# normalize every quaternion to a length of one
def normalize_quaternions(quaternions: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(quaternions, axis=1, keepdims=True)

    if np.any(norms <= 1e-12):
        raise ValueError("a sample contains a zero-length quaternion")

    return quaternions / norms


# multiply two quaternions stored in x, y, z, w order
def multiply_quaternions(
    first: np.ndarray,
    second: np.ndarray,
) -> np.ndarray:
    first_x, first_y, first_z, first_w = first
    second_x, second_y, second_z, second_w = second

    return np.array(
        [
            first_w * second_x
            + first_x * second_w
            + first_y * second_z
            - first_z * second_y,

            first_w * second_y
            - first_x * second_z
            + first_y * second_w
            + first_z * second_x,

            first_w * second_z
            + first_x * second_y
            - first_y * second_x
            + first_z * second_w,

            first_w * second_w
            - first_x * second_x
            - first_y * second_y
            - first_z * second_z,
        ],
        dtype=np.float64,
    )


# make orientation relative to the first pose in the window
def make_orientation_relative(
    orientations: np.ndarray,
) -> np.ndarray:
    continuous_orientations = normalize_quaternions(
        orientations.astype(np.float64)
    )

    continuous_orientations = continuous_orientations.copy()

    # keep equivalent quaternion signs from looking like sudden jumps
    for sample_index in range(1, len(continuous_orientations)):
        previous_orientation = continuous_orientations[sample_index - 1]
        current_orientation = continuous_orientations[sample_index]

        if np.dot(previous_orientation, current_orientation) < 0:
            continuous_orientations[sample_index] *= -1.0

    first_orientation = continuous_orientations[0]

    first_orientation_inverse = np.array(
        [
            -first_orientation[0],
            -first_orientation[1],
            -first_orientation[2],
            first_orientation[3],
        ],
        dtype=np.float64,
    )

    relative_orientations = []

    for orientation in continuous_orientations:
        relative_orientation = multiply_quaternions(
            first_orientation_inverse,
            orientation,
        )

        relative_orientations.append(relative_orientation)

    return normalize_quaternions(
        np.asarray(relative_orientations)
    )


# convert one motion window into 840 model features
def record_to_features(record: dict) -> np.ndarray:
    samples = record.get("samples")

    if not isinstance(samples, list):
        raise ValueError("record is missing its samples list")

    if len(samples) != EXPECTED_SAMPLES:
        raise ValueError(
            f"expected {EXPECTED_SAMPLES} samples, "
            f"but found {len(samples)}"
        )

    positions = []
    orientations = []

    for sample_index, sample in enumerate(samples):
        position = sample.get("position_m")
        orientation = sample.get("orientation_xyzw")

        if not isinstance(position, list) or len(position) != 3:
            raise ValueError(
                f"sample {sample_index} has an invalid position"
            )

        if not isinstance(orientation, list) or len(orientation) != 4:
            raise ValueError(
                f"sample {sample_index} has an invalid orientation"
            )

        positions.append(position)
        orientations.append(orientation)

    position_array = np.asarray(
        positions,
        dtype=np.float64,
    )

    orientation_array = np.asarray(
        orientations,
        dtype=np.float64,
    )

    if not np.all(np.isfinite(position_array)):
        raise ValueError("position values must be finite")

    if not np.all(np.isfinite(orientation_array)):
        raise ValueError("orientation values must be finite")

    # remove the starting position from the entire window
    relative_positions = (
        position_array
        - position_array[0]
    )

    relative_orientations = make_orientation_relative(
        orientation_array
    )

    feature_matrix = np.concatenate(
        [
            relative_positions,
            relative_orientations,
        ],
        axis=1,
    )

    expected_shape = (
        EXPECTED_SAMPLES,
        FEATURES_PER_SAMPLE,
    )

    if feature_matrix.shape != expected_shape:
        raise ValueError(
            f"expected feature shape {expected_shape}, "
            f"but found {feature_matrix.shape}"
        )

    return feature_matrix.reshape(-1)


# organize windows using their existing train validation and test labels
def build_datasets(
    records: list[dict],
) -> dict[str, dict[str, np.ndarray]]:
    allowed_splits = (
        "train",
        "validation",
        "test",
    )

    split_features = {
        split_name: []
        for split_name in allowed_splits
    }

    split_labels = {
        split_name: []
        for split_name in allowed_splits
    }

    for record_index, record in enumerate(records):
        split_name = record.get("split")
        label = record.get("label")

        if split_name not in allowed_splits:
            raise ValueError(
                f"record {record_index} has invalid split: "
                f"{split_name}"
            )

        if label not in LABELS:
            raise ValueError(
                f"record {record_index} has invalid label: "
                f"{label}"
            )

        features = record_to_features(record)

        split_features[split_name].append(features)
        split_labels[split_name].append(label)

    datasets = {}

    for split_name in allowed_splits:
        if not split_features[split_name]:
            raise ValueError(
                f"the {split_name} split is empty"
            )

        datasets[split_name] = {
            "features": np.vstack(
                split_features[split_name]
            ),
            "labels": np.asarray(
                split_labels[split_name]
            ),
        }

    missing_training_labels = (
        set(LABELS)
        - set(datasets["train"]["labels"])
    )

    if missing_training_labels:
        missing_text = ", ".join(
            sorted(missing_training_labels)
        )

        raise ValueError(
            f"training data is missing labels: {missing_text}"
        )

    return datasets


# create the two conventional classifiers
def create_models(seed: int) -> dict[str, object]:
    logistic_regression = Pipeline(
        steps=[
            (
                "scaler",
                StandardScaler(),
            ),
            (
                "classifier",
                LogisticRegression(
                    max_iter=5000,
                    solver="lbfgs",
                    random_state=seed,
                ),
            ),
        ]
    )

    random_forest = RandomForestClassifier(
        n_estimators=300,
        random_state=seed,
        n_jobs=1,
    )

    return {
        "logistic_regression": logistic_regression,
        "random_forest": random_forest,
    }


# calculate the main classification measurements
def calculate_metrics(
    expected_labels: np.ndarray,
    predicted_labels: np.ndarray,
) -> dict:
    precision, recall, class_f1, support = (
        precision_recall_fscore_support(
            expected_labels,
            predicted_labels,
            labels=LABELS,
            zero_division=0,
        )
    )

    per_class = {}

    for label_index, label in enumerate(LABELS):
        per_class[label] = {
            "precision": float(
                precision[label_index]
            ),
            "recall": float(
                recall[label_index]
            ),
            "f1": float(
                class_f1[label_index]
            ),
            "support": int(
                support[label_index]
            ),
        }

    matrix = confusion_matrix(
        expected_labels,
        predicted_labels,
        labels=LABELS,
    )

    return {
        "sample_count": int(len(expected_labels)),
        "accuracy": float(
            accuracy_score(
                expected_labels,
                predicted_labels,
            )
        ),
        "macro_f1": float(
            f1_score(
                expected_labels,
                predicted_labels,
                labels=LABELS,
                average="macro",
                zero_division=0,
            )
        ),
        "per_class": per_class,
        "confusion_matrix": matrix.tolist(),
    }


# measure how long one prediction takes
def measure_inference_latency(
    model: object,
    features: np.ndarray,
) -> dict:
    warmup_count = min(
        20,
        len(features),
    )

    for sample_index in range(warmup_count):
        sample = features[
            sample_index
        ].reshape(1, -1)

        model.predict(sample)

    latency_values_ms = []

    for sample in features:
        prepared_sample = sample.reshape(1, -1)

        start_time = time.perf_counter_ns()

        model.predict(prepared_sample)

        end_time = time.perf_counter_ns()

        elapsed_ms = (
            end_time
            - start_time
        ) / 1_000_000

        latency_values_ms.append(elapsed_ms)

    latency_array = np.asarray(
        latency_values_ms,
        dtype=np.float64,
    )

    return {
        "sample_count": int(len(latency_array)),
        "median_ms": float(
            np.median(latency_array)
        ),
        "p95_ms": float(
            np.percentile(
                latency_array,
                95,
            )
        ),
        "mean_ms": float(
            np.mean(latency_array)
        ),
    }


# save a readable confusion matrix image
def save_confusion_matrix(
    matrix: list[list[int]],
    title: str,
    output_path: Path,
) -> None:
    figure, axis = plt.subplots(
        figsize=(7, 6)
    )

    image = axis.imshow(
        matrix,
        interpolation="nearest",
        cmap="Blues",
    )

    axis.set_title(title)
    axis.set_xlabel("predicted class")
    axis.set_ylabel("actual class")

    axis.set_xticks(
        range(len(DISPLAY_LABELS))
    )

    axis.set_yticks(
        range(len(DISPLAY_LABELS))
    )

    axis.set_xticklabels(
        DISPLAY_LABELS,
        rotation=30,
        ha="right",
    )

    axis.set_yticklabels(
        DISPLAY_LABELS
    )

    figure.colorbar(
        image,
        ax=axis,
    )

    matrix_array = np.asarray(matrix)
    threshold = matrix_array.max() / 2.0

    for row_index in range(matrix_array.shape[0]):
        for column_index in range(matrix_array.shape[1]):
            value = matrix_array[
                row_index,
                column_index,
            ]

            text_color = (
                "white"
                if value > threshold
                else "black"
            )

            axis.text(
                column_index,
                row_index,
                str(value),
                ha="center",
                va="center",
                color=text_color,
            )

    figure.tight_layout()
    figure.savefig(
        output_path,
        dpi=200,
        bbox_inches="tight",
    )

    plt.close(figure)


# count labels in each split for the result record
def get_split_summary(
    datasets: dict[str, dict[str, np.ndarray]],
) -> dict:
    summary = {}

    for split_name, split_data in datasets.items():
        label_counts = Counter(
            split_data["labels"].tolist()
        )

        summary[split_name] = {
            "window_count": int(
                len(split_data["labels"])
            ),
            "label_counts": {
                label: int(
                    label_counts.get(label, 0)
                )
                for label in LABELS
            },
        }

    return summary


# calculate the dataset file hash for reproducibility
def calculate_file_hash(
    input_path: Path,
) -> str:
    hash_object = hashlib.sha256()

    with input_path.open("rb") as input_file:
        while True:
            chunk = input_file.read(
                1024 * 1024
            )

            if not chunk:
                break

            hash_object.update(chunk)

    return hash_object.hexdigest()


# record the current git commit when available
def get_git_commit() -> str:
    try:
        completed_process = subprocess.run(
            [
                "git",
                "rev-parse",
                "HEAD",
            ],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        return completed_process.stdout.strip()

    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
    ):
        return "unavailable"


# safely read an installed package version
def get_package_version(
    package_name: str,
) -> str:
    try:
        return version(package_name)

    except PackageNotFoundError:
        return "not installed"


# make the machine and package record
def get_environment_information() -> dict:
    return {
        "python": platform.python_version(),
        "operating_system": platform.platform(),
        "numpy": get_package_version("numpy"),
        "scikit_learn": get_package_version(
            "scikit-learn"
        ),
        "matplotlib": get_package_version(
            "matplotlib"
        ),
    }


# write a short result summary for people to read
def write_summary(
    results: dict,
    output_path: Path,
) -> None:
    lines = [
        "# Conventional Classification Baselines",
        "",
        "This experiment used the synthetic Quest-like dataset.",
        "These results test the pipeline and dont represent real Quest performance yet.",
        "",
        "## Dataset",
        "",
        f"- Training windows: {results['splits']['train']['window_count']}",
        f"- Validation windows: {results['splits']['validation']['window_count']}",
        f"- Testing windows: {results['splits']['test']['window_count']}",
        f"- Features per window: {results['features']['feature_count']}",
        f"- Random seed: {results['seed']}",
        "",
        "## Results",
        "",
        "| Model | Validation macro-F1 | Test accuracy | Test macro-F1 | Test p95 inference |",
        "|---|---:|---:|---:|---:|",
    ]

    for model_name, model_results in results["models"].items():
        readable_name = model_name.replace(
            "_",
            " ",
        ).title()

        validation_macro_f1 = (
            model_results["validation"]["macro_f1"]
        )

        test_accuracy = (
            model_results["test"]["accuracy"]
        )

        test_macro_f1 = (
            model_results["test"]["macro_f1"]
        )

        test_p95 = (
            model_results["test_inference_latency_ms"]["p95_ms"]
        )

        lines.append(
            f"| {readable_name} "
            f"| {validation_macro_f1:.4f} "
            f"| {test_accuracy:.4f} "
            f"| {test_macro_f1:.4f} "
            f"| {test_p95:.4f} ms |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Logistic regression is the simple linear baseline.",
            "Random forest is the nonlinear tree-based baseline.",
            "The models use the same data, features, and cross-session split.",
            "Later SNN results should be compared with these exact baseline results.",
            "",
        ]
    )

    output_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


# train both models and save their results
def run_experiment(
    input_path: Path,
    output_directory: Path,
    seed: int,
) -> dict:
    np.random.seed(seed)

    records = load_records(
        input_path
    )

    datasets = build_datasets(
        records
    )

    training_features = (
        datasets["train"]["features"]
    )

    training_labels = (
        datasets["train"]["labels"]
    )

    validation_features = (
        datasets["validation"]["features"]
    )

    validation_labels = (
        datasets["validation"]["labels"]
    )

    test_features = (
        datasets["test"]["features"]
    )

    test_labels = (
        datasets["test"]["labels"]
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    models = create_models(seed)
    model_results = {}

    for model_name, model in models.items():
        print(
            f"training {model_name.replace('_', ' ')}"
        )

        training_start = time.perf_counter_ns()

        model.fit(
            training_features,
            training_labels,
        )

        training_end = time.perf_counter_ns()

        training_latency_ms = (
            training_end
            - training_start
        ) / 1_000_000

        validation_predictions = model.predict(
            validation_features
        )

        test_predictions = model.predict(
            test_features
        )

        validation_metrics = calculate_metrics(
            validation_labels,
            validation_predictions,
        )

        test_metrics = calculate_metrics(
            test_labels,
            test_predictions,
        )

        test_latency = measure_inference_latency(
            model,
            test_features,
        )

        model_results[model_name] = {
            "training_latency_ms": float(
                training_latency_ms
            ),
            "validation": validation_metrics,
            "test": test_metrics,
            "test_inference_latency_ms": test_latency,
        }

        matrix_output_path = (
            output_directory
            / f"{model_name}-confusion-matrix.png"
        )

        save_confusion_matrix(
            matrix=test_metrics["confusion_matrix"],
            title=(
                f"{model_name.replace('_', ' ').title()} "
                "Test Confusion Matrix"
            ),
            output_path=matrix_output_path,
        )

    results = {
        "experiment": (
            "conventional head motion classification baselines"
        ),
        "seed": seed,
        "git_commit": get_git_commit(),
        "input": {
            "path": str(input_path),
            "sha256": calculate_file_hash(
                input_path
            ),
            "window_count": len(records),
        },
        "features": {
            "time_steps": EXPECTED_SAMPLES,
            "channels_per_time_step": FEATURES_PER_SAMPLE,
            "feature_count": (
                EXPECTED_SAMPLES
                * FEATURES_PER_SAMPLE
            ),
            "channels": [
                "relative_position_x",
                "relative_position_y",
                "relative_position_z",
                "relative_orientation_x",
                "relative_orientation_y",
                "relative_orientation_z",
                "relative_orientation_w",
            ],
            "tracking_validity_use": (
                "quality check only, not a classifier feature"
            ),
            "timestamp_use": (
                "ordering and validation only, not a classifier feature"
            ),
        },
        "splits": get_split_summary(
            datasets
        ),
        "models": model_results,
        "environment": get_environment_information(),
    }

    results_path = (
        output_directory
        / "baseline-results.json"
    )

    with results_path.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            results,
            output_file,
            indent=4,
        )

        output_file.write("\n")

    summary_path = (
        output_directory
        / "baseline-summary.md"
    )

    write_summary(
        results,
        summary_path,
    )

    print(
        f"saved results to {output_directory}"
    )

    return results


# read command line settings and start the experiment
def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "train conventional classifiers "
            "on the synthetic motion dataset"
        )
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="path to the generated jsonl dataset",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIRECTORY,
        help="directory for result files",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=2026,
        help="random seed used by the models",
    )

    arguments = parser.parse_args()

    run_experiment(
        input_path=arguments.input,
        output_directory=arguments.output,
        seed=arguments.seed,
    )


if __name__ == "__main__":
    main()