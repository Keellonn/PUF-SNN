"""Package frozen model evidence and measure fixed-recipe conventional file sizes.

No SNN training, architecture change, threshold selection or authentication runs.
The two seed-7 conventional refits measure storage and must reproduce frozen counts.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/python"))
sys.path.insert(0, str(ROOT / "src/python/scripts"))

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import sklearn
from sklearn.metrics import confusion_matrix

import train_baselines as baseline
from puf_snn import model_reporting as reporting

FROZEN_RESULTS_COMMIT = "7cdbd81674740e6ff975542139766fa9e0ddd129"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def unchanged_since(path: Path, commit: str) -> str:
    relative = path.relative_to(ROOT).as_posix()
    old = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{commit}:{relative}"])
    if old.replace(b"\r\n", b"\n") != path.read_bytes().replace(b"\r\n", b"\n"):
        raise ValueError(f"frozen result/source changed: {relative}; stop rather than silently mixing runs")
    return sha256(path)


def checked_artifact(directory: Path, manifest: dict, name: str, checked: dict) -> Path:
    path = directory / name
    if not path.is_file() or sha256(path) != manifest["artifacts"].get(name):
        raise ValueError(f"missing or hash-mismatched frozen input: {path}")
    checked[path.relative_to(ROOT).as_posix()] = sha256(path)
    return path


def training_curves(width: int, histories: dict, decisions: list[dict], output: Path) -> None:
    figure, axes = plt.subplots(2, 3, figsize=(13, 6))
    for column, seed in enumerate((7, 17, 27)):
        history = histories[seed]
        chosen = next(row for row in decisions if row["model"] == f"snn_{width}" and row["initialization_seed"] == seed)
        epochs = [row["epoch"] for row in history]
        axes[0, column].plot(epochs, [row["training_loss"] for row in history], label="Training cross-entropy")
        axes[1, column].plot(epochs, [row["validation_macro_f1"] for row in history], label="Validation macro-F1")
        axes[1, column].plot(epochs, [row["validation_accuracy"] for row in history], linestyle="--", label="Validation accuracy")
        axes[0, column].set_title(f"SNN-{width}: initialization {seed}, training {chosen['training_seed']}")
        for axis in axes[:, column]:
            axis.axvline(chosen["selected_epoch"], color="black", linestyle=":", label="Selected epoch")
            axis.set_xlabel("Epoch")
            axis.grid(alpha=.2)
        axes[0, column].set_ylabel("Training loss")
        axes[1, column].set_ylabel("Validation score")
        axes[1, column].set_ylim(0, 1)
    axes[0, 0].legend(fontsize=8)
    axes[1, 0].legend(fontsize=8)
    figure.tight_layout()
    figure.savefig(output / f"snn-{width}-all-seed-curves.png", dpi=180)
    plt.close(figure)


def make_report(records: list[dict], decisions: list[dict], storage: list[dict], selected: int) -> str:
    families = ("logistic_regression", "random_forest", "snn_64", "snn_32")
    means = {family: np.mean([row["test"]["macro_f1"] for row in records if row["model"] == family]) for family in families}
    lines = ["# Frozen conventional and SNN model-evidence addendum", "",
             "This addendum packages existing corrected-data results. It does not retrain either SNN, choose a new architecture, replace historical results, retune an anomaly threshold or rerun authentication. Conventional storage measurements below are explicit new seed-7 reproductions, not recovered original model files.", "",
             "## Current comparison and interpretation", "",
             "| Model | Recorded seeds | Mean validation macro-F1 | Mean test macro-F1 | Gap below LR (percentage points) |", "|---|---:|---:|---:|---:|"]
    for family in families:
        rows = [row for row in records if row["model"] == family]
        validation = np.mean([row["validation"]["macro_f1"] for row in rows])
        lines.append(f"| {family} | {len(rows)} | {validation:.4f} | {means[family]:.4f} | {100 * (means['logistic_regression'] - means[family]):.2f} |")
    lines.extend(["", f"The predefined two-width comparison selects {selected} neurons using mean Session-2 macro-F1 alone; Session-3 scores are not selection inputs. SNN-64 remains the frozen reference for the existing Tier-2 evaluation. It misses the provisional five-point tolerance (5.32-point LR gap). SNN-32 meets it (4.12-point gap), but neither SNN beats the conventional models.", "",
                  "The compact SNN-32 provides a viable temporal-inference baseline within the predeclared performance tolerance, but conventional models remain more accurate in this synthetic CPU evaluation. Any eventual SNN motivation must come from an independently demonstrated systems, temporal-robustness or neuromorphic-hardware advantage. Passing a project tolerance is not evidence of superiority, energy savings or deployed performance.", "",
                  "## Exact LIF and readout equations", "",
                  "Each 120-step window resets hidden membrane, previous spikes and output membrane to zero. Direct continuous input has seven pose channels; no Poisson/rate encoder or Euler conversion is used. Both widths use beta=0.9, threshold=1, surrogate slope=25, dense learned H x H recurrence including its diagonal, and no recurrent bias.", "",
                  "```text", "a[t] = 0.9*u[t-1] + W_in*x[t] + b_in + W_rec*s[t-1]",
                  "s[t] = 1 if a[t] >= 1 else 0",
                  "u[t] = a[t] - stop_gradient(s[t])*1",
                  "surrogate d(s)/d(a) = 1 / (1 + 25*abs(a - 1))^2",
                  "v[t] = 0.9*v[t-1] + W_out*s[t] + b_out",
                  "logit[k] = (1/120)*sum_t v[t,k]",
                  "prediction = argmax_k logit[k]", "```", "",
                  "This is subtractive reset, not reset-to-zero; readout membrane does not spike. Input 7->H has bias, recurrence H->H has none, and readout H->5 has bias. Parameter count is H^2 + 13H + 5: 4,933 for H=64 and 1,445 for H=32. PyTorch Linear reset_parameters initialization is retained. Adam uses learning rate 0.001, batch size 32, cross-entropy, gradient norm clipping at 1 and a maximum of 50 epochs. Training-only per-channel normalization uses Session 1; the conventional LR scaler instead fits each of 840 flattened features on Session 1. RF does not scale.", "",
                  "## Checkpoint selection and stopping", "",
                  "Selection uses the first epoch whose validation macro-F1 improves the previous best by more than 1e-12. Stop after eight consecutive non-improving epochs, or at epoch 50. The selected best state is restored before evaluation. Every decision below was reconstructed from and reconciled against the saved history, seed pair, configuration and summary—not guessed from the final test score.", "",
                  "| Model | Initialization seed | Training/shuffle seed | Selected epoch | Stopping epoch | Reason |",
                  "|---|---:|---:|---:|---:|---|"])
    for row in decisions:
        lines.append(f"| {row['model']} | {row['initialization_seed']} | {row['training_seed']} | {row['selected_epoch']} | {row['stopping_epoch']} | {row['stopping_reason']} |")
    lines.extend(["", "![All three SNN-64 training and validation curves](snn-64-all-seed-curves.png)", "",
                  "![All three SNN-32 training and validation curves](snn-32-all-seed-curves.png)", "",
                  "The historical training routine saved training cross-entropy and validation accuracy/macro-F1, not validation loss or training accuracy. The plots identify those distinct units on separate axes; missing historical measurements are not invented.", "",
                  "## Parameters and serialized model storage", "",
                  "| Model | Seed | Learned coefficients | Trees / nodes / leaves | Artifact bytes | Format and scope |",
                  "|---|---:|---:|---|---:|---|"])
    for row in storage:
        complexity = f"{row['trees']} / {row['nodes']} / {row['leaves']}" if row["trees"] else "N/A"
        parameters = str(row["trainable_parameters"]) if row["trainable_parameters"] is not None else "N/A"
        lines.append(f"| {row['model']} | {row['seed']} | {parameters} | {complexity} | {row['artifact_bytes']} | {row['format_scope']} |")
    lines.extend(["", "LR has 4,205 coefficients/intercepts; scaler statistics are not trainable coefficients. Tree counts are structure, not a neural-parameter equivalent. SNN bytes measure the exact hash-verified existing torch.save checkpoint containing state_dict and seed/model metadata, not an optimizer checkpoint. Its normalization JSON is a separate sidecar, whose byte count/hash is recorded in model-storage.csv. LR's uncompressed joblib pipeline includes its fitted StandardScaler; RF has no scaler. Different serialization formats/dtypes/metadata make these artifact sizes a storage comparison, not a fair runtime-memory, energy or hardware-efficiency claim.", "",
                  "The original conventional fits were not serialized. This addendum refits only the predefined seed-7 LR and 300-tree RF recipes on the original Session-1 rows, with no hyperparameter search. Before writing either model, its Session-2/Session-3 confusion counts and parameter/tree/node/leaf counts must match the frozen seed-7 results exactly. Test data is used only as a reproduction assertion, not a tuning criterion; a mismatch stops the run. New joblib files use compress=0 and pickle protocol=5, stay under Git-ignored models/, and have byte sizes and hashes in the manifest. They are explicitly new storage reproductions; equality of aggregate counts does not prove recovery of original learned weights. No SNN state is loaded or retrained here.", "",
                  "## Randomness and further-selection protocol", "",
                  "Generation seed 7 determines the one frozen synthetic dataset. Session-index splits have no RNG. LR lbfgs is deterministic on these fixed data, and its random_state labels do not produce independent randomized model replications: identical five-seed macro-F1 values give 0.0000 descriptive SD. RF seeds control fitting randomness, and SNN initialization seeds 7/17/27 are paired with training/shuffle seeds 107/117/127. All seeds still reuse the same 600 test windows, not independent datasets or human recordings. Any pooled confusion matrix repeats those same sources and is labeled accordingly.", "",
                  "Freeze the current classifiers, widths and anomaly thresholds. No further SNN architecture expansion until the end-to-end authentication experiment is complete. For an authorized later change: record the research question, finite candidate list, fixed data/configuration and seed roles before fitting; fit on Session 1; use mean Session-2 macro-F1 across the fixed three seed pairs to choose the candidate, with the smaller model as a tie-break; do not inspect Session-3 scores to revise candidates, stopping rules or thresholds. Previously inspected Session 3 is not a fresh holdout for an open-ended future search—an independent final evaluation requires a separately specified untouched dataset. This addendum initiates no such search.", "",
                  "## Complete test per-class and confusion evidence", "",
                  "Class order is nod, shake, look_left_return, look_right_return, still. Rows are true classes and columns predicted classes. Each seed has 600 held-out windows, 120 per class. All 32 validation/test matrices and all 160 per-class rows are also saved in machine-readable artifacts."])
    for row in records:
        lines.extend(["", f"### {row['model']}, seed {row['seed']}", "",
                      "| Class | Precision | Recall | F1 | Support |", "|---|---:|---:|---:|---:|"])
        for label in reporting.LABELS:
            values = row["test"]["per_class"][label]
            lines.append(f"| {label} | {values['precision']:.4f} | {values['recall']:.4f} | {values['f1']:.4f} | {values['support']} |")
        lines.extend(["", "```text", *[str(values) for values in row["test"]["confusion_matrix"]], "```"])
    lines.extend(["", "## Scope", "",
                  "Cross-session synthetic evaluation with six fixed simulated device profiles only. No cross-device, cross-person, headset or real-world transfer claim follows. Existing leakage results and Week 4/Tier-2 runs remain unchanged. This report is not fresh end-to-end timing, reconstruction availability or security-rate evidence.", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/generated/synthetic-windows.jsonl")
    parser.add_argument("--conventional", type=Path, default=ROOT / "results/week-4/keegan/conventional-baselines")
    parser.add_argument("--snn-64", type=Path, default=ROOT / "results/week-4/keegan/snn-baseline-separate-seeds")
    parser.add_argument("--snn-32", type=Path, default=ROOT / "results/week-4/keegan/snn-architecture-32")
    parser.add_argument("--output", type=Path, default=ROOT / "results/week-5/keegan/model-evidence")
    args = parser.parse_args()
    for name, path in vars(args).items():
        setattr(args, name, path.resolve())
    output = args.output.resolve()
    references = [args.conventional.resolve(), args.snn_64.resolve(), args.snn_32.resolve()]
    if output.exists() or any(output == ref or ref in output.parents or output in ref.parents for ref in references):
        raise ValueError("output must be new and separate from all historical references")
    if any(not (ref / "COMPLETE").is_file() for ref in references):
        raise ValueError("a historical reference is incomplete")
    source_commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    status = subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True).strip()
    checked, sources = {}, {}
    conventional_path = args.conventional / "baseline-diagnostics.json"
    checked[conventional_path.relative_to(ROOT).as_posix()] = unchanged_since(conventional_path, FROZEN_RESULTS_COMMIT)
    conventional = read_json(conventional_path)
    input_hash = sha256(args.input)
    if input_hash != conventional["input"]["sha256"] or sklearn.__version__ != conventional["environment"]["scikit_learn"]:
        raise ValueError("dataset/sklearn version differs from the frozen conventional recipe")
    source_ref = conventional["provenance"]["git_commit"]
    for relative in ("src/python/scripts/train_baselines.py", "src/python/scripts/run_baseline_diagnostics.py",
                     "src/python/scripts/train_snn.py", "src/python/puf_snn/snn/model.py"):
        sources[relative] = unchanged_since(ROOT / relative, source_ref)
    records, per_class, decisions, matrices, storage, histories, summaries = [], [], [], {}, [], {}, {}
    frozen_runs = conventional["multiseed_baselines"]["runs"]
    if [row["seed"] for row in frozen_runs] != [7, 17, 27, 37, 47]:
        raise ValueError("conventional evidence must retain the frozen five seed labels")
    for run in frozen_runs:
        for family in ("logistic_regression", "random_forest"):
            record = {"model": family, "seed": run["seed"]}
            for split in ("validation", "test"):
                record[split] = reporting.reconcile_metrics(run["models"][family][split])
                per_class.extend(reporting.per_class_rows(family, run["seed"], split, record[split]))
                matrices[f"{family}:seed-{run['seed']}:{split}"] = record[split]["confusion_matrix"]
            records.append(record)
    for width, directory in ((64, args.snn_64), (32, args.snn_32)):
        manifest = read_json(directory / "manifest.json")
        checked[(directory / "manifest.json").relative_to(ROOT).as_posix()] = sha256(directory / "manifest.json")
        if manifest["input_sha256"] != input_hash:
            raise ValueError("SNN reference belongs to another dataset")
        config = read_json(checked_artifact(directory, manifest, "config.json", checked))
        summary = read_json(checked_artifact(directory, manifest, "summary.json", checked))
        if config["model"]["hidden_neurons"] != width or summary["seeds"] != [7, 17, 27]:
            raise ValueError("SNN width/seed identity differs")
        expected_model = {"lif_beta": .9, "lif_threshold": 1, "surrogate_slope": 25,
                          "output_classes": 5, "output_aggregation": "mean_output_membrane_across_time"}
        expected_training = {"learning_rate": .001, "batch_size": 32, "maximum_epochs": 50,
                             "gradient_clip_norm": 1, "early_stopping_patience": 8,
                             "early_stopping_metric": "validation_macro_f1", "optimizer": "adam", "loss": "cross_entropy"}
        if any(config["model"].get(key) != value for key, value in expected_model.items()) or any(
                config["training"].get(key) != value for key, value in expected_training.items()):
            raise ValueError("frozen LIF/training configuration differs from the documented equations")
        normalization = checked_artifact(directory, manifest, "normalization.json", checked)
        summaries[width], histories[width] = summary, {}
        for run in summary["per_seed"]:
            seed = run["seed"]
            history = read_json(checked_artifact(directory, manifest, f"seed-{seed}/training-history.json", checked))
            histories[width][seed] = history
            decisions.append({"model": f"snn_{width}", **reporting.training_decision(history, config, run)})
            record = {"model": f"snn_{width}", "seed": seed}
            for split in ("validation", "test"):
                saved = read_json(checked_artifact(directory, manifest, f"seed-{seed}/{split}-metrics.json", checked))
                record[split] = reporting.reconcile_metrics(saved)
                if record[split] != reporting.reconcile_metrics(run[split]):
                    raise ValueError("SNN summary and seed-specific metrics differ")
                per_class.extend(reporting.per_class_rows(f"snn_{width}", seed, split, saved))
                matrices[f"snn_{width}:seed-{seed}:{split}"] = record[split]["confusion_matrix"]
            records.append(record)
            checkpoint = checked_artifact(directory, manifest, f"seed-{seed}/model-state.pt", checked)
            storage.append({"model": f"snn_{width}", "seed": seed,
                            "trainable_parameters": reporting.snn_parameter_count(width), "trees": None, "nodes": None, "leaves": None,
                            "artifact_bytes": checkpoint.stat().st_size, "artifact_sha256": sha256(checkpoint),
                            "artifact_path": checkpoint.relative_to(ROOT).as_posix(), "origin": "original_frozen_checkpoint",
                            "normalization_sidecar_bytes": normalization.stat().st_size,
                            "normalization_sidecar_sha256": sha256(normalization),
                            "format_scope": "torch.save state_dict plus seed/model metadata; scaler separate"})
    if len(records) != 16 or len(matrices) != 32 or len(per_class) != 160 or len(decisions) != 6:
        raise ValueError("incomplete model evidence; do not silently report a subset")
    if any(record[split]["sample_count"] != 600 for record in records for split in ("validation", "test")):
        raise ValueError("a model reference does not retain 600 query windows")
    selected = reporting.validation_selected_width(summaries)
    # Freeze recipes before using evaluation rows. Refit only for storage, never tuning.
    arrays = baseline.build_datasets(baseline.load_records(args.input))
    models = baseline.create_models(7)
    binary_artifacts = {}
    for family, model in models.items():
        model.fit(arrays["train"]["features"], arrays["train"]["labels"])
        frozen = frozen_runs[0]["models"][family]
        for split in ("validation", "test"):
            predictions = model.predict(arrays[split]["features"])
            matrix = confusion_matrix(arrays[split]["labels"], predictions, labels=reporting.LABELS).tolist()
            reporting.check_refit_counts(matrix, frozen[split])
        if family == "logistic_regression":
            fitted = model.named_steps["classifier"]
            complexity = {"trainable_parameters": int(fitted.coef_.size + fitted.intercept_.size)}
        else:
            complexity = {"trainable_parameters": None, "trees": len(model.estimators_),
                          "nodes": int(sum(tree.tree_.node_count for tree in model.estimators_)),
                          "leaves": int(sum(tree.tree_.n_leaves for tree in model.estimators_))}
        reporting.validate_refit_complexity(complexity, frozen["model_complexity"])
        buffer = io.BytesIO()
        joblib.dump(model, buffer, compress=0, protocol=5)
        data = buffer.getvalue()
        name = f"models/{family}-seed-7-storage-refit.joblib"
        binary_artifacts[name] = data
        storage.append({"model": family, "seed": 7, "trainable_parameters": complexity.get("trainable_parameters"),
                        "trees": complexity.get("trees"), "nodes": complexity.get("nodes"), "leaves": complexity.get("leaves"),
                        "artifact_bytes": len(data), "artifact_sha256": hashlib.sha256(data).hexdigest(),
                        "artifact_path": name, "origin": "new_fixed_recipe_storage_refit",
                        "normalization_sidecar_bytes": 0, "normalization_sidecar_sha256": None,
                        "format_scope": "joblib compress=0 protocol=5; LR scaler embedded / RF no scaler"})
        print(f"PASS: seed-7 {family} storage refit matches frozen validation/test counts and complexity", flush=True)
    output.mkdir(parents=True, exist_ok=False)
    (output / "models").mkdir()
    for name, data in binary_artifacts.items():
        (output / name).write_bytes(data)
    write_csv(output / "per-class.csv", per_class)
    write_csv(output / "training-decisions.csv", decisions)
    write_csv(output / "model-storage.csv", storage)
    write_json(output / "confusion-matrices.json", {"class_order": reporting.LABELS, "row": "true", "column": "predicted", "matrices": matrices})
    write_json(output / "recorded-metrics.json", records)
    write_json(output / "selection-protocol.json", {"candidate_widths": [32, 64], "fit_split": "train",
        "selection_split": "validation", "selected_by_mean_validation_macro_f1": selected, "test_used_for_selection": False,
        "initialization_seeds": [7, 17, 27], "training_seeds": [107, 117, 127], "new_architecture_search_executed": False,
        "further_architecture_expansion": "disabled until end-to-end authentication experiment is complete"})
    for width in (64, 32):
        training_curves(width, histories[width], decisions, output)
    (output / "model-evidence.md").write_text(make_report(records, decisions, storage, selected), encoding="utf-8", newline="\n")
    (output / ".gitattributes").write_text("* -text\n.gitattributes text eol=lf\n", encoding="utf-8", newline="\n")
    for path in (Path(__file__), Path(reporting.__file__)):
        sources[path.relative_to(ROOT).as_posix()] = sha256(path)
    write_json(output / "manifest.json", {"run_type": "frozen_model_evidence_and_storage_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(), "source_commit": source_commit, "source_worktree_dirty": bool(status),
        "command": subprocess.list2cmdline([sys.executable, *sys.argv]), "input_sha256": input_hash,
        "historical_conventional_results_commit": FROZEN_RESULTS_COMMIT, "checked_historical_inputs_sha256": checked,
        "source_sha256": sources, "snn_training_executed": False, "conventional_storage_refits_executed": 2,
        "new_architecture_search_executed": False, "authentication_executed": False, "threshold_selection_executed": False,
        "historical_files_modified": False, "model_record_count": len(records), "per_class_rows": len(per_class),
        "confusion_matrix_count": len(matrices), "training_decision_count": len(decisions),
        "local_model_artifacts": {name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "git_ignored": True} for name, data in binary_artifacts.items()},
        "environment": {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__, "sklearn": sklearn.__version__, "joblib": joblib.__version__},
        "artifacts": {path.name: sha256(path) for path in sorted(output.iterdir()) if path.is_file()}})
    write_json(output / "COMPLETE", {"manifest_sha256": sha256(output / "manifest.json"), "per_class_rows": len(per_class),
                                     "confusion_matrix_count": len(matrices), "training_decision_count": len(decisions)})
    print("PASS: 160 per-class rows, 32 confusion matrices, six reconciled stopping decisions and eight storage measurements")
    print("No SNN training, architecture change, threshold selection or authentication occurred")
    print(f"Saved results to {output}")


if __name__ == "__main__":
    main()
