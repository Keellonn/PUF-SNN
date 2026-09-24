"""
this script trains and evaluates the official three-seed recurrent SNN baseline
it saves reproducible metrics confusion matrices model states and CPU latency
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
import time

from copy import deepcopy
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np
import torch

from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from puf_snn.snn.configuration import load_snn_config, seed_everything
from puf_snn.snn.dataset import LABELS, apply_channel_normalization, build_snn_datasets, fit_channel_normalization, load_records
from puf_snn.snn.evaluation import calculate_metrics, measure_inference_latency, predict_indexes, save_confusion_matrix
from puf_snn.snn.model import create_model


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = REPOSITORY_ROOT / "configs" / "snn_baseline.json"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the three-seed recurrent SNN motion baseline.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--machine-model", required=True)
    parser.add_argument("--allow-dirty", action="store_true")

    return parser.parse_args()


def resolve_repository_path(path: Path) -> Path:
    if path.is_absolute():
        return path

    return REPOSITORY_ROOT / path


def write_json(output_path: Path, value: object) -> None:
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(value, output_file, indent=2)
        output_file.write("\n")


def sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()

    with file_path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def run_git(arguments: list[str]) -> str:
    completed = subprocess.run(["git", *arguments], cwd=REPOSITORY_ROOT, check=True, capture_output=True, text=True)

    return completed.stdout.strip()


def get_git_information() -> dict:
    return {
        "commit": run_git(["rev-parse", "HEAD"]),
        "branch": run_git(["branch", "--show-current"]),
        "status_porcelain": run_git(["status", "--porcelain"]).splitlines(),
    }


def get_package_version(package_name: str) -> str | None:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return None


def train_one_epoch(model: nn.Module, loader: DataLoader, optimizer: torch.optim.Optimizer, loss_function: nn.Module, gradient_clip_norm: float, device: torch.device) -> float:
    model.train()
    total_loss = 0.0
    total_examples = 0

    for sequences, label_indexes in loader:
        sequences = sequences.to(device)
        label_indexes = label_indexes.to(device)
        optimizer.zero_grad(set_to_none=True)
        scores = model(sequences)
        loss = loss_function(scores, label_indexes)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clip_norm)
        optimizer.step()
        total_loss += float(loss.item()) * len(sequences)
        total_examples += len(sequences)

    return total_loss / total_examples


def fit_seed(seed: int, config: dict, datasets: dict[str, dict[str, object]], output_directory: Path, device: torch.device) -> dict:
    training_config = config["training"]
    seed_everything(seed, training_config["torch_threads"])
    model = create_model(config["model"]).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=training_config["learning_rate"])
    loss_function = nn.CrossEntropyLoss()
    training_sequences = torch.from_numpy(datasets["train"]["sequences"])
    training_labels = torch.from_numpy(datasets["train"]["label_indexes"])
    generator = torch.Generator().manual_seed(seed)
    training_loader = DataLoader(TensorDataset(training_sequences, training_labels), batch_size=training_config["batch_size"], shuffle=True, generator=generator, num_workers=0)
    best_validation_macro_f1 = -1.0
    best_epoch = 0
    best_state = None
    epochs_without_improvement = 0
    history = []

    for epoch in range(1, training_config["maximum_epochs"] + 1):
        start_time = time.perf_counter()
        training_loss = train_one_epoch(model, training_loader, optimizer, loss_function, training_config["gradient_clip_norm"], device)
        validation_predictions = predict_indexes(model, datasets["validation"]["sequences"], training_config["batch_size"], device)
        validation_metrics = calculate_metrics(datasets["validation"]["label_indexes"], validation_predictions)
        epoch_seconds = time.perf_counter() - start_time
        history.append({
            "epoch": epoch,
            "training_loss": training_loss,
            "validation_accuracy": validation_metrics["accuracy"],
            "validation_macro_f1": validation_metrics["macro_f1"],
            "epoch_seconds": epoch_seconds,
        })

        print(f"seed {seed} epoch {epoch}: loss={training_loss:.6f} validation_macro_f1={validation_metrics['macro_f1']:.6f}")

        if validation_metrics["macro_f1"] > best_validation_macro_f1 + 1e-12:
            best_validation_macro_f1 = validation_metrics["macro_f1"]
            best_epoch = epoch
            best_state = deepcopy(model.state_dict())
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        if epochs_without_improvement >= training_config["early_stopping_patience"]:
            break

    if best_state is None:
        raise RuntimeError("training did not produce a model state")

    model.load_state_dict(best_state)
    validation_predictions = predict_indexes(model, datasets["validation"]["sequences"], training_config["batch_size"], device)
    test_predictions = predict_indexes(model, datasets["test"]["sequences"], training_config["batch_size"], device)
    validation_metrics = calculate_metrics(datasets["validation"]["label_indexes"], validation_predictions)
    test_metrics = calculate_metrics(datasets["test"]["label_indexes"], test_predictions)
    latency = measure_inference_latency(model, datasets["test"]["sequences"], config["evaluation"]["warmup_windows"], config["evaluation"]["timed_windows"], device)
    seed_directory = output_directory / f"seed-{seed}"
    seed_directory.mkdir()

    torch.save({
        "seed": seed,
        "labels": LABELS,
        "model_config": config["model"],
        "state_dict": model.state_dict(),
    }, seed_directory / "model-state.pt")

    write_json(seed_directory / "training-history.json", history)
    write_json(seed_directory / "validation-metrics.json", validation_metrics)
    write_json(seed_directory / "test-metrics.json", test_metrics)
    write_json(seed_directory / "inference-latency.json", latency)
    save_confusion_matrix(test_metrics["confusion_matrix"], f"SNN Test Confusion Matrix - Seed {seed}", seed_directory / "confusion-matrix.png")

    return {
        "seed": seed,
        "best_epoch": best_epoch,
        "epochs_completed": len(history),
        "validation": validation_metrics,
        "test": test_metrics,
        "inference_latency": latency,
    }


def summarize_runs(seed_results: list[dict]) -> dict:
    summary = {
        "seed_count": len(seed_results),
        "seeds": [result["seed"] for result in seed_results],
        "per_seed": seed_results,
    }

    metric_paths = {
        "validation_macro_f1": ("validation", "macro_f1"),
        "test_accuracy": ("test", "accuracy"),
        "test_macro_f1": ("test", "macro_f1"),
        "median_inference_ms": ("inference_latency", "median_ms"),
        "p95_inference_ms": ("inference_latency", "p95_ms"),
    }

    for summary_name, (section_name, metric_name) in metric_paths.items():
        values = np.asarray([result[section_name][metric_name] for result in seed_results], dtype=np.float64)
        summary[summary_name] = {
            "mean": float(values.mean()),
            "standard_deviation": float(values.std(ddof=0)),
            "minimum": float(values.min()),
            "maximum": float(values.max()),
        }

    return summary


def write_summary_csv(summary: dict, output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.writer(output_file)
        writer.writerow(["seed", "best_epoch", "validation_macro_f1", "test_accuracy", "test_macro_f1", "median_inference_ms", "p95_inference_ms"])

        for result in summary["per_seed"]:
            writer.writerow([
                result["seed"],
                result["best_epoch"],
                result["validation"]["macro_f1"],
                result["test"]["accuracy"],
                result["test"]["macro_f1"],
                result["inference_latency"]["median_ms"],
                result["inference_latency"]["p95_ms"],
            ])

        writer.writerow(["mean", "", summary["validation_macro_f1"]["mean"], summary["test_accuracy"]["mean"], summary["test_macro_f1"]["mean"], summary["median_inference_ms"]["mean"], summary["p95_inference_ms"]["mean"]])
        writer.writerow(["standard_deviation", "", summary["validation_macro_f1"]["standard_deviation"], summary["test_accuracy"]["standard_deviation"], summary["test_macro_f1"]["standard_deviation"], summary["median_inference_ms"]["standard_deviation"], summary["p95_inference_ms"]["standard_deviation"]])


def write_manifest(output_directory: Path, input_path: Path, config_path: Path, git_information: dict, environment: dict) -> None:
    artifact_hashes = {}

    for artifact_path in sorted(output_directory.rglob("*")):
        if artifact_path.is_file() and artifact_path.name not in {"manifest.json", "COMPLETE"}:
            relative_path = artifact_path.relative_to(output_directory).as_posix()
            artifact_hashes[relative_path] = sha256_file(artifact_path)

    write_json(output_directory / "manifest.json", {
        "schema_version": "snn-baseline-manifest-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": str(input_path),
        "input_sha256": sha256_file(input_path),
        "config_path": str(config_path),
        "config_sha256": sha256_file(config_path),
        "git": git_information,
        "environment": environment,
        "artifacts": artifact_hashes,
    })


def main() -> int:
    arguments = parse_arguments()
    config_path = resolve_repository_path(arguments.config)
    config = load_snn_config(config_path)
    input_path = resolve_repository_path(arguments.input if arguments.input is not None else Path(config["dataset"]["input_path"]))
    output_directory = resolve_repository_path(arguments.output if arguments.output is not None else Path(config["output_directory"]))
    git_information = get_git_information()

    if git_information["status_porcelain"] and not arguments.allow_dirty:
        raise RuntimeError("commit the SNN code and start from a clean working tree before the official run")

    if output_directory.exists():
        raise FileExistsError(f"output directory already exists: {output_directory}")

    output_directory.mkdir(parents=True)

    try:
        records = load_records(input_path)
        datasets = build_snn_datasets(records)
        normalization = fit_channel_normalization(datasets["train"]["sequences"])

        for split_name in ("train", "validation", "test"):
            datasets[split_name]["sequences"] = apply_channel_normalization(datasets[split_name]["sequences"], normalization)

        environment = {
            "machine_model": arguments.machine_model,
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "processor": platform.processor(),
            "logical_cpu_count": __import__("os").cpu_count(),
            "packages": {
                "numpy": get_package_version("numpy"),
                "scikit-learn": get_package_version("scikit-learn"),
                "matplotlib": get_package_version("matplotlib"),
                "torch": torch.__version__,
                "puf-snn": get_package_version("puf-snn"),
            },
            "torch_device": "cpu",
            "torch_threads": config["training"]["torch_threads"],
            "deterministic_algorithms": True,
        }

        write_json(output_directory / "config.json", config)
        write_json(output_directory / "normalization.json", {
            "channels": config["dataset"]["channels"],
            "fitted_from": "train",
            "mean": normalization["mean"].tolist(),
            "standard_deviation": normalization["standard_deviation"].tolist(),
        })
        write_json(output_directory / "dataset-summary.json", {
            split_name: {
                "window_count": int(len(datasets[split_name]["sequences"])),
                "shape": list(datasets[split_name]["sequences"].shape),
            }
            for split_name in ("train", "validation", "test")
        })
        write_json(output_directory / "environment.json", environment)

        device = torch.device("cpu")
        seed_results = []

        for seed in config["training"]["random_seeds"]:
            seed_results.append(fit_seed(seed, config, datasets, output_directory, device))

        summary = summarize_runs(seed_results)
        write_json(output_directory / "summary.json", summary)
        write_summary_csv(summary, output_directory / "summary.csv")
        combined_matrix = np.sum([np.asarray(result["test"]["confusion_matrix"], dtype=np.int64) for result in seed_results], axis=0)
        save_confusion_matrix(combined_matrix.tolist(), "SNN Test Confusion Matrix - All Seeds", output_directory / "confusion-matrix-all-seeds.png")
        write_manifest(output_directory, input_path, config_path, git_information, environment)
        (output_directory / "COMPLETE").write_text(datetime.now(timezone.utc).isoformat() + "\n", encoding="utf-8")

    except Exception as error:
        write_json(output_directory / "INCOMPLETE.json", {
            "failed_utc": datetime.now(timezone.utc).isoformat(),
            "error_type": type(error).__name__,
            "error": str(error),
        })
        raise

    print(f"SNN baseline complete: {output_directory}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
