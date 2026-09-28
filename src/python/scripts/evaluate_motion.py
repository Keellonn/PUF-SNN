"""
this script records leakage evidence SNN reports feature ablations and motion errors
it preserves the original runs and does not choose settings from the test results
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import types

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import torch

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/python/scripts"))

import train_baselines as baseline

from puf_snn.data.generator import generate_records
from puf_snn.motion_diagnostics import angular_velocity, assert_no_full_window_duplicates, distribution, feature_group, full_window_duplicates, nearest_neighbors, pooled_metrics, record_times, rotation_vectors, transformed_record
from puf_snn.snn.configuration import seed_everything
from puf_snn.snn.dataset import LABELS, SPLITS, apply_channel_normalization, build_snn_datasets, load_records, record_to_sequence
from puf_snn.snn.evaluation import calculate_metrics, predict_indexes, save_confusion_matrix
from puf_snn.snn.model import create_model


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def generated_hash(records: list[dict]) -> str:
    digest = hashlib.sha256()

    for record in records:
        digest.update((json.dumps(record, allow_nan=False) + "\n").encode("utf-8"))

    return digest.hexdigest()


def original_records(ref: str, config_path: Path, expected_hash: str) -> list[dict]:
    source = subprocess.run(["git", "show", f"{ref}:src/python/puf_snn/data/generator.py"], cwd=ROOT, capture_output=True, check=True, text=True).stdout
    module = types.ModuleType("original_generator_audit")
    module.__file__ = f"git:{ref}:generator.py"
    sys.modules[module.__name__] = module
    # this executes only the explicitly selected historical repository generator
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    records = module.generate_records(json.loads(config_path.read_text(encoding="utf-8")))

    if generated_hash(records) != expected_hash:
        raise ValueError("historical regeneration does not match the original audited dataset hash")

    return records


def provenance(arguments: argparse.Namespace) -> dict:
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
    sources = [Path(__file__), ROOT / "src/python/puf_snn/motion_diagnostics.py", ROOT / "src/python/puf_snn/data/generator.py", ROOT / "src/python/puf_snn/snn/model.py", ROOT / "src/python/puf_snn/snn/dataset.py"]
    return {"created_utc": datetime.now(timezone.utc).isoformat(), "git_commit": git.stdout.strip(), "git_status": status.stdout.splitlines(), "command": sys.argv, "input_sha256": sha256(arguments.input), "source_sha256": {path.relative_to(ROOT).as_posix(): sha256(path) for path in sources}, "python": platform.python_version(), "platform": platform.platform(), "numpy": np.__version__, "torch": torch.__version__, "machine_model": arguments.machine_model}


def group_balance(records: list[dict]) -> dict:
    groups = {}

    for record in records:
        key = f"{record['device_id']}/{record['session_id']}"
        groups.setdefault(key, Counter())[record["label"]] += 1

    balanced = all(set(counts) == set(LABELS) and len(set(counts.values())) == 1 for counts in groups.values())
    return {"balanced_within_each_device_session": balanced, "counts": {key: dict(counts) for key, counts in groups.items()}, "limitation": "balanced groups and excluded IDs reduce direct label proxies; they do not establish real-device generalization"}


def data_report(arguments: argparse.Namespace, settings: dict) -> None:
    current = load_records(arguments.input)
    assert_no_full_window_duplicates(current)
    pilot = json.loads(arguments.pilot.read_text(encoding="utf-8"))

    if pilot["randomness"]["data_generation_seed"] != pilot["project"]["random_seed"]:
        raise ValueError("recorded generation seed disagrees with the generator seed")

    for role in ("attack_generation", "puf_simulation"):
        recorded = pilot["randomness"][role]
        source_config = json.loads((ROOT / recorded["config"]).read_text(encoding="utf-8"))

        if source_config[recorded["field"]] != recorded["value"]:
            raise ValueError(f"recorded {role} seed disagrees with its actual configuration")

    if generated_hash(generate_records(pilot)) != sha256(arguments.input):
        raise ValueError("current dataset is not the deterministic output of the current pilot configuration")

    old_audit = json.loads((arguments.original_audit / "baseline-diagnostics.json").read_text(encoding="utf-8"))
    original = original_records(arguments.original_generator_ref, arguments.original_audit / "original-pilot.json", old_audit["input"]["sha256"])
    thresholds = settings["combined_near_threshold"]
    results = {"thresholds": thresholds, "threshold_interpretation": "provisional sensitivity thresholds, not calibrated human-motion or universal leakage criteria", "balance": group_balance(current), "datasets": {}}
    figure, axes = plt.subplots(1, 2, figsize=(11, 4))

    for name, records in (("original", original), ("corrected", current)):
        train = [record for record in records if record["split"] == "train"]
        test = [record for record in records if record["split"] == "test"]
        neighbors = nearest_neighbors(train, test, thresholds["position_rms_m"], thresholds["orientation_rms_deg"])
        write_json(arguments.output / f"{name}-nearest-neighbors.json", neighbors)
        dataset_result = {"full_windows": full_window_duplicates(records), "neighbor_distributions": {}}

        for scope in ("any_label", "same_label"):
            rows = [row for row in neighbors if row["scope"] == scope]
            dataset_result["neighbor_distributions"][scope] = {"orientation_rms_deg": distribution([row["orientation_rms_deg"] for row in rows]), "combined_scaled_distance": distribution([row["combined_scaled_distance"] for row in rows]), "near_both_thresholds_count": sum(row["has_neighbor_within_both_thresholds"] for row in rows), "orientation_within_threshold_count": sum(row["orientation_rms_deg"] <= settings["rotation_near_threshold_deg"] for row in rows)}

        results["datasets"][name] = dataset_result
        rows = [row for row in neighbors if row["scope"] == "same_label"]

        for axis, field in zip(axes, ("orientation_rms_deg", "combined_scaled_distance")):
            values = np.sort([row[field] for row in rows])
            axis.plot(values, np.arange(1, len(values) + 1) / len(values), label=name)
            axis.set_xlabel(field)
            axis.set_ylabel("fraction of test windows")
            axis.legend()

    figure.tight_layout()
    figure.savefig(arguments.output / "nearest-neighbor-distributions.png", dpi=180)
    plt.close(figure)
    write_json(arguments.output / "data-diagnostics.json", results)
    write_json(arguments.output / "generator-settings.json", {"randomness": pilot["randomness"], "synthetic_motion": pilot["synthetic_motion"], "splits": pilot["splits"]})
    lines = ["# Corrected-data diagnostics", "", "| Original issue | Cause | Correction | Regression evidence |", "|---|---|---|---|", "| Repeated active-class orientations across splits | Fixed amplitude/rate/phase templates with position noise masking repetition | Trial-level motion variation, noise/drift/sway and group effects | Full-window split tests, physical nearest-neighbor distributions, existing quaternion/variation tests |", "", "Original audit and original perfect-score results remain historical evidence, not the corrected baseline.", "", "Distances use relative poses, position RMS in meters and sign-invariant quaternion geodesic RMS in degrees. The same physical units and procedure apply before and after correction. Combined distance uses the recorded fixed thresholds, not a scaler fitted separately to each dataset.", "", "Full-window equality includes all samples, relative timing and tracking quality; labels and identifiers cannot hide a copy.", "", f"Corrected full-window duplicate check passed: {results['datasets']['corrected']['full_windows']['passed']}", f"Balanced class counts in every device/session: {results['balance']['balanced_within_each_device_session']}", "", "See data-diagnostics.json for all split-pair counts and distance summaries and the nearest-neighbor files for every observation. Small distances are reported rather than automatically declared leakage. The still distribution can naturally overlap.", "", "Scope: fixed synthetic device profiles, cross-session only; no physical Quest or human calibration."]
    (arguments.output / "data-diagnostics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def snn_report(arguments: argparse.Namespace) -> None:
    summary = json.loads((arguments.snn_baseline / "summary.json").read_text(encoding="utf-8"))
    metrics = pooled_metrics([run["test"]["confusion_matrix"] for run in summary["per_seed"]], LABELS)
    write_json(arguments.output / "pooled-test-metrics.json", metrics)
    save_confusion_matrix(metrics["confusion_matrix"], "SNN pooled predictions on the same test windows", arguments.output / "pooled-confusion-matrix.png")
    lines = ["# SNN detailed results", "", "The per-seed evidence below is read from the saved baseline, not a newly claimed training run.", "", "| Seed | Best epoch | Stopping epoch |", "|---:|---:|---:|"]

    for run in summary["per_seed"]:
        seed = run["seed"]
        history = json.loads((arguments.snn_baseline / f"seed-{seed}/training-history.json").read_text(encoding="utf-8"))
        figure, axes = plt.subplots(1, 2, figsize=(10, 4))
        epochs = [row["epoch"] for row in history]
        axes[0].plot(epochs, [row["training_loss"] for row in history])
        axes[0].set_ylabel("training cross-entropy loss")
        axes[1].plot(epochs, [row["validation_macro_f1"] for row in history])
        axes[1].set_ylabel("validation macro-F1")

        for axis in axes:
            axis.axvline(run["best_epoch"], linestyle="--", label="best checkpoint")
            axis.axvline(run["epochs_completed"], linestyle=":", label="stopping epoch")
            axis.set_xlabel("epoch")
            axis.legend()

        figure.tight_layout()
        figure.savefig(arguments.output / f"seed-{seed}-training-curves.png", dpi=180)
        plt.close(figure)
        lines.append(f"| {seed} | {run['best_epoch']} | {run['epochs_completed']} |")

    for name, result in [(f"Seed {run['seed']}", run["test"]) for run in summary["per_seed"]] + [("Pooled predictions", metrics)]:
        lines.extend(["", f"## {name}", "", "| Class | Precision | Recall | F1 | Support |", "|---|---:|---:|---:|---:|"])

        for label, values in result["per_class"].items():
            lines.append(f"| {label} | {values['precision']:.4f} | {values['recall']:.4f} | {values['f1']:.4f} | {values['support']} |")

        lines.extend(["", "Confusion matrix: rows are true labels; columns are predicted labels in the configured class order.", "", "```text", *[str(row) for row in result["confusion_matrix"]], "```"])

    lines.extend(["", metrics["limitation"], "", "The saved latency is forward-only: normalization, tensor creation/transfer, argmax and CPU output decoding, authentication, audit and capture are excluded. Training batch size is 32; timing batch size is one.", "", "Conclusion: This report describes the saved SNN run. Determine the five-point macro-F1 criterion from a matched conventional comparison and distinguish the reference baseline from an architecture ablation. No measured energy advantage or real-world robustness is established."])
    (arguments.output / "snn-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_snn_models(directory: Path, input_path: Path) -> tuple[list[tuple[str, object]], dict]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))

    if manifest["input_sha256"] != sha256(input_path):
        raise ValueError("saved SNN models were trained on a different dataset")

    config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
    normalization = json.loads((directory / "normalization.json").read_text(encoding="utf-8"))
    models = []
    seed_everything(config["training"]["random_seeds"][0], config["training"]["torch_threads"])

    for seed in config["training"]["random_seeds"]:
        path = directory / f"seed-{seed}/model-state.pt"
        expected = manifest["artifacts"][f"seed-{seed}/model-state.pt"]

        if sha256(path) != expected:
            raise ValueError(f"checkpoint hash mismatch for seed {seed}")

        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        model = create_model(checkpoint["model_config"])
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        models.append((f"snn_seed_{seed}", model))

    return models, normalization


def predict_model(model: object, records: list[dict], normalization: dict | None = None) -> np.ndarray:
    sequences = np.stack([record_to_sequence(record) for record in records])

    if isinstance(model, torch.nn.Module):
        sequences = apply_channel_normalization(sequences, normalization)
        return predict_indexes(model, sequences, 32, torch.device("cpu"))

    names = model.predict(sequences.reshape(len(sequences), -1))
    return np.asarray([LABELS.index(str(name)) for name in names])


def motion_statistics(record: dict) -> dict:
    sequence = record_to_sequence(record)
    angle = np.degrees(np.linalg.norm(rotation_vectors(sequence[:, 3:7]), axis=1))
    velocity = np.degrees(np.linalg.norm(angular_velocity(sequence, record_times(record)), axis=1))
    position = np.linalg.norm(sequence[:, :3], axis=1)
    return {"window_id": record["window_id"], "label": record["label"], "orientation_peak_deg": float(angle.max()), "orientation_rms_deg": float(np.sqrt(np.mean(angle ** 2))), "angular_speed_rms_deg_s": float(np.sqrt(np.mean(velocity ** 2))), "position_rms_m": float(np.sqrt(np.mean(position ** 2)))}


def analysis_report(arguments: argparse.Namespace, settings: dict) -> None:
    records = load_records(arguments.input)
    assert_no_full_window_duplicates(records)
    datasets = build_snn_datasets(records)
    train = datasets["train"]["records"]
    train_labels = np.asarray([record["label"] for record in train])
    models, normalization = load_snn_models(arguments.snn_baseline, arguments.input)
    train_x = np.stack([record_to_sequence(record).reshape(-1) for record in train])

    for seed in settings["model_seeds"]:
        for name, model in baseline.create_models(seed).items():
            model.fit(train_x, train_labels)
            models.append((f"{name}_seed_{seed}", model))

    ablations = []

    for group in settings["feature_groups"]:
        train_x = np.stack([feature_group(record, group).reshape(-1) for record in train])

        for seed in settings["model_seeds"]:
            logistic = LogisticRegression(max_iter=5000, solver="lbfgs", random_state=seed)

            if group != "raw_relative_pose":
                logistic = Pipeline([("scaler", StandardScaler()), ("classifier", logistic)])

            for name, model in (("logistic_regression", logistic), ("random_forest", RandomForestClassifier(n_estimators=300, random_state=seed, n_jobs=1))):
                model.fit(train_x, train_labels)
                result = {"feature_group": group, "model": name, "seed": seed, "feature_count": train_x.shape[1], "scaling": "none" if name == "random_forest" or group == "raw_relative_pose" else "training-only per flattened feature"}

                for split in ("validation", "test"):
                    items = datasets[split]["records"]
                    features = np.stack([feature_group(record, group).reshape(-1) for record in items])
                    result[split] = baseline.calculate_metrics(np.asarray([record["label"] for record in items]), model.predict(features))

                ablations.append(result)

    write_json(arguments.output / "feature-ablations.json", {"runs": ablations, "interpretation": "raw relative pose versus position+quaternion is an explicit LR scaling control; RF uses the same unscaled features in both, not two distinct representations; feature ablations use conventional classifiers while the SNN architecture comparison keeps seven channels"})
    observations = []
    stress_results = []
    statistics = []
    prediction_rows = []

    for split in ("validation", "test"):
        items = datasets[split]["records"]
        expected = np.asarray([LABELS.index(record["label"]) for record in items])
        statistics.extend([{**motion_statistics(record), "split": split} for record in items])

        for name, model in models:
            predicted = predict_model(model, items, normalization)
            observations.append({"model": name, "split": split, "condition": "clean", "metrics": calculate_metrics(expected, predicted)})
            prediction_rows.extend({"model": name, "split": split, "window_id": record["window_id"], "true_label": record["label"], "prediction": LABELS[int(index)]} for record, index in zip(items, predicted))

            if split == "test":
                save_error_examples(items, predicted, name, arguments.output)

        conditions = [("amplitude", {"amplitude": value}) for value in settings["stress"]["amplitude_scales"]]
        conditions += [("speed", {"speed": value}) for value in settings["stress"]["speed_scales"]]
        conditions += [("initial_orientation", {"initial_orientation_deg": value}) for value in settings["stress"]["initial_orientation_deg"]]
        conditions += [("timing", {"shift_seconds": value}) for value in settings["stress"]["time_shift_seconds"]]

        for condition, parameters in conditions:
            changed = [transformed_record(record, **parameters) for record in items]

            for name, model in models:
                prediction = predict_model(model, changed, normalization)
                stress_results.append({"model": name, "split": split, "condition": condition, "parameters": parameters, "metrics": calculate_metrics(expected, prediction)})

    write_json(arguments.output / "clean-results.json", observations)
    write_json(arguments.output / "predictions.json", prediction_rows)
    write_json(arguments.output / "motion-statistics.json", statistics)
    write_json(arguments.output / "stress-results.json", {"runs": stress_results, "limitations": "paired synthetic sensitivity tests, not new independent recordings or real-world robustness; amplitude scales the observed motion including noise; time warps clamp endpoints; initial orientation is an invariance check after relative preprocessing"})
    nod_results = nod_sweep(arguments, settings, models, normalization)
    write_json(arguments.output / "nod-still-sweep.json", nod_results)
    write_json(arguments.output / "model-complexity.json", {name: model_complexity(model) for name, model in models})
    write_analysis_markdown(arguments.output, observations, ablations, statistics, nod_results)


def model_complexity(model: object) -> dict:
    if isinstance(model, torch.nn.Module):
        return {"trainable_parameters": sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad), "kind": "learned neural weights and biases"}

    classifier = model.named_steps["classifier"] if isinstance(model, Pipeline) else model

    if hasattr(classifier, "coef_"):
        return {"trainable_parameters": int(classifier.coef_.size + classifier.intercept_.size), "kind": "LR coefficients and intercepts; scaler statistics excluded"}

    return {"trainable_parameters": None, "trees": len(classifier.estimators_), "nodes": int(sum(tree.tree_.node_count for tree in classifier.estimators_)), "leaves": int(sum(tree.tree_.n_leaves for tree in classifier.estimators_)), "maximum_depth": int(max(tree.tree_.max_depth for tree in classifier.estimators_)), "kind": "tree structure counts, not neural trainable parameters"}


def save_error_examples(records: list[dict], predictions: np.ndarray, model_name: str, output: Path) -> None:
    cases = [("nod", "nod"), ("nod", "still"), ("still", "still"), ("still", "nod")]
    figure, axes = plt.subplots(4, 2, figsize=(10, 11))

    for row, (truth, prediction) in enumerate(cases):
        indexes = [index for index, record in enumerate(records) if record["label"] == truth and LABELS[int(predictions[index])] == prediction]
        axes[row, 0].set_title(f"{truth} predicted as {prediction}")

        if not indexes:
            axes[row, 0].text(0.1, 0.5, "no example in this run")
            continue

        record = records[indexes[0]]
        sequence = record_to_sequence(record)
        times = record_times(record)
        axes[row, 0].plot(times, np.degrees(rotation_vectors(sequence[:, 3:7])))
        axes[row, 0].set_ylabel("relative rotation vector (degrees)")
        axes[row, 1].plot(times, sequence[:, :3])
        axes[row, 1].set_ylabel("relative position (meters)")
        axes[row, 0].set_xlabel(record["window_id"] + "\ntime (s)", fontsize=7)
        axes[row, 1].set_xlabel("time (s)")

    figure.tight_layout()
    figure.savefig(output / f"{model_name}-nod-still-examples.png", dpi=160)
    plt.close(figure)


def nod_sweep(arguments: argparse.Namespace, settings: dict, models: list, normalization: dict) -> dict:
    pilot = json.loads(arguments.pilot.read_text(encoding="utf-8"))
    results = []

    for amplitude in settings["nod_sweep"]["amplitude_scales"]:
        for speed in settings["nod_sweep"]["speed_scales"]:
            changed = deepcopy(pilot)
            nod = changed["synthetic_motion"]["classes"]["nod"]
            nod["peak_rotation_deg"] *= amplitude
            nod["vertical_position_peak_m"] *= amplitude
            changed["synthetic_motion"]["motion_duration_s_range"] = [value / speed for value in pilot["synthetic_motion"]["motion_duration_s_range"]]
            generated = [record for record in generate_records(changed) if record["label"] == "nod"]

            for split in ("validation", "test"):
                items = [record for record in generated if record["split"] == split]
                expected = np.zeros(len(items), dtype=np.int64)
                values = [motion_statistics(record) for record in items]

                for name, model in models:
                    predicted = predict_model(model, items, normalization)
                    results.append({"model": name, "split": split, "amplitude_scale": amplitude, "speed_scale": speed, "duration_scale": 1.0 / speed, "sample_count": len(items), "nod_recall": float(np.mean(predicted == 0)), "still_prediction_fraction": float(np.mean(predicted == 4)), "mean_peak_rotation_deg": float(np.mean([value["orientation_peak_deg"] for value in values])), "mean_angular_speed_rms_deg_s": float(np.mean([value["angular_speed_rms_deg_s"] for value in values])), "metrics": calculate_metrics(expected, predicted)})

    figure, axis = plt.subplots(figsize=(10, 5))

    for name, _ in models:
        rows = [row for row in results if row["model"] == name and row["split"] == "test" and row["speed_scale"] == 1.0]
        axis.plot([row["amplitude_scale"] for row in rows], [row["still_prediction_fraction"] for row in rows], marker="o", label=name)

    axis.set_xlabel("intentional nod amplitude scale")
    axis.set_ylabel("fraction predicted as still")
    axis.legend(fontsize=7)
    figure.tight_layout()
    figure.savefig(arguments.output / "nod-amplitude-to-still.png", dpi=180)
    plt.close(figure)
    return {"runs": results, "method": "same generator draws and source IDs; only nod intentional rotation/position coefficients and motion-duration range change; noise/drift/sway and return error remain; actual duration is clipped by the original generator", "limitations": "diagnostic synthetic sweep; increasingly ambiguous nominal nod labels are not new independent trials; test results do not choose parameters; no claim of physical execution speed"}


def write_analysis_markdown(output: Path, observations: list, ablations: list, statistics: list, nod_results: dict) -> None:
    lines = ["# Motion baseline analysis", "", "All configurations were fixed before evaluation. Session 2 is validation; Session 3 is final comparison, not a tuning loop.", "", "## Fixed-model clean results", "", "| Model | Split | Accuracy | Macro-F1 |", "|---|---|---:|---:|"]

    for row in observations:
        lines.append(f"| {row['model']} | {row['split']} | {row['metrics']['accuracy']:.4f} | {row['metrics']['macro_f1']:.4f} |")

    lines.extend(["", "## Feature ablation", "", "Raw relative pose is an explicit unscaled LR control; position+quaternion uses the same seven channels with training-only scaling. RF uses no scaler in either condition. Quaternion+angular velocity has four quaternion plus three radians/second channels; the first velocity is zero. Euler angles are not model features.", "", "| Group | Model | Seed | Validation F1 | Test F1 |", "|---|---|---:|---:|---:|"])

    for row in ablations:
        lines.append(f"| {row['feature_group']} | {row['model']} | {row['seed']} | {row['validation']['macro_f1']:.4f} | {row['test']['macro_f1']:.4f} |")

    lines.extend(["", "## Nod and still motion", "", "| True class | Test windows | Mean rotation RMS (deg) | Mean position RMS (m) |", "|---|---:|---:|---:|"])

    for label in ("nod", "still"):
        rows = [row for row in statistics if row["label"] == label and row["split"] == "test"]
        lines.append(f"| {label} | {len(rows)} | {np.mean([row['orientation_rms_deg'] for row in rows]):.4f} | {np.mean([row['position_rms_m'] for row in rows]):.6f} |")

    lines.extend(["", "Per-window statistics, predictions, representative correct/incorrect trajectories, feature results, stress results and nod-sweep results are saved separately. Examine whether low-amplitude nods overlap still and whether speed/timing variation changes errors; do not infer realism from synthetic success.", "", nod_results["method"], "", nod_results["limitations"], "", "SNN checkpoints and preprocessing remain frozen during these diagnostics. Feature ablations are conventional-model comparisons, not a new SNN input contract."])
    (output / "motion-analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def architecture_report(arguments: argparse.Namespace) -> None:
    inputs = [arguments.snn_baseline, arguments.snn_32]
    runs = []
    hashes = []

    for directory in inputs:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        hashes.append(manifest["input_sha256"])
        config = json.loads((directory / "config.json").read_text(encoding="utf-8"))
        runs.append({"hidden_neurons": config["model"]["hidden_neurons"], "config": config, "summary": json.loads((directory / "summary.json").read_text(encoding="utf-8"))})

    if len(set(hashes)) != 1 or hashes[0] != sha256(arguments.input):
        raise ValueError("architecture comparison requires the exact same dataset")

    first = deepcopy(runs[0]["config"])
    second = deepcopy(runs[1]["config"])

    for config in (first, second):
        config.pop("experiment_name")
        config.pop("output_directory")
        config["model"].pop("hidden_neurons")

    if first != second:
        raise ValueError("architecture configurations differ in more than hidden-neuron count")

    selected = max(runs, key=lambda row: row["summary"]["validation_macro_f1"]["mean"])["hidden_neurons"]
    write_json(arguments.output / "architecture-comparison.json", {"runs": runs, "selected_by_validation_only": selected, "test_used_for_selection": False})
    lines = ["# Fixed 32 versus 64 recurrent-neuron comparison", "", "| Neurons | Validation macro-F1 | Test macro-F1 | Forward p95 (ms) |", "|---:|---:|---:|---:|"]

    for row in runs:
        summary = row["summary"]
        lines.append(f"| {row['hidden_neurons']} | {summary['validation_macro_f1']['mean']:.4f} | {summary['test_macro_f1']['mean']:.4f} | {summary['p95_inference_ms']['mean']:.4f} |")

    lines.extend(["", f"Validation-only selected size: {selected}. The original 64-neuron Week 4 baseline remains historical evidence; this comparison does not overwrite it."])
    (arguments.output / "architecture-comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("data", "snn", "analysis", "architecture"))
    parser.add_argument("--input", type=Path, default=ROOT / "data/generated/synthetic-windows.jsonl")
    parser.add_argument("--pilot", type=Path, default=ROOT / "configs/pilot.json")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/motion_evaluation.json")
    parser.add_argument("--original-audit", type=Path, default=ROOT / "results/week-3/keegan/original-baseline-audit")
    parser.add_argument("--original-generator-ref", default="3936cc6")
    parser.add_argument("--snn-baseline", type=Path, default=ROOT / "results/week-4/keegan/snn-baseline")
    parser.add_argument("--snn-32", type=Path, default=ROOT / "results/week-4/keegan/snn-architecture-32")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--machine-model", required=True)
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=False)

    try:
        settings = json.loads(arguments.config.read_text(encoding="utf-8"))
        write_json(arguments.output / "configuration.json", settings)

        if arguments.mode == "data":
            data_report(arguments, settings)
        elif arguments.mode == "snn":
            snn_report(arguments)
        elif arguments.mode == "analysis":
            analysis_report(arguments, settings)
        else:
            architecture_report(arguments)

        record = provenance(arguments)
        record["configuration_sha256"] = sha256(arguments.config)
        record["pilot_sha256"] = sha256(arguments.pilot)
        record["artifacts"] = {path.relative_to(arguments.output).as_posix(): sha256(path) for path in arguments.output.rglob("*") if path.is_file()}
        write_json(arguments.output / "manifest.json", record)
        (arguments.output / "COMPLETE").write_text("complete\n", encoding="utf-8")
    except Exception as error:
        write_json(arguments.output / "INCOMPLETE.json", {"error_type": type(error).__name__, "error": str(error)})
        raise

    print(f"Saved {arguments.mode} evidence to {arguments.output}")


if __name__ == "__main__":
    main()
