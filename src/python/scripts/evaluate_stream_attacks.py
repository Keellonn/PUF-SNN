"""
this script evaluates the saved Tier 2 plan without retraining the SNN
it fits separate anomaly baselines, freezes validation thresholds, then evaluates paired test paths
"""

from __future__ import annotations

import argparse
from collections import Counter
from importlib.metadata import version
import hashlib
import json
from itertools import zip_longest
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/python"))
sys.path.insert(0, str(ROOT / "src/python/scripts"))

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

import train_baselines as baseline
from run_layer3_demo import establish, initialize_material
from puf_snn.anomaly.detector import anomaly_scores, fit_anomaly_models, select_validation_threshold, validate_evaluation_config
from puf_snn.anomaly.features import FEATURE_NAMES
from puf_snn.attacks.evaluation import assert_plan_matches, construct_cohorts, evaluate_authenticated_cases, predict_detectors, predict_motion_models, summarize_construction, summarize_predictions
from puf_snn.attacks.stream import validate_attack_config
from puf_snn.auth.config import AuthConfig
from puf_snn.data.validation import validate_dataset
from puf_snn.motion_diagnostics import assert_no_full_window_duplicates
from puf_snn.snn.configuration import validate_snn_config
from puf_snn.snn.dataset import LABELS, load_records
from puf_snn.snn.model import create_model


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict | list) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8-sig")) != value:
            raise ValueError(f"existing result differs; preserve it and stop: {path}")
        return
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def write_rows(path: Path, rows) -> None:
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            for saved, expected in zip_longest((json.loads(line) for line in handle), rows):
                if saved != expected:
                    raise ValueError(f"existing result rows differ; preserve them and stop: {path}")
        return
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")


def check_artifacts(directory: Path, manifest: dict, names: list[str]) -> None:
    for name in names:
        path = (directory / name).resolve()
        if not path.is_relative_to(directory.resolve()) or name not in manifest["artifacts"] or not path.is_file() or sha256(path) != manifest["artifacts"][name]:
            raise ValueError(f"missing or hash-mismatched artifact: {path}")


def load_plan(plan_directory: Path, input_hash: str) -> tuple[dict, list[dict], dict]:
    if not (plan_directory / "COMPLETE").is_file():
        raise ValueError("the saved attack plan is incomplete")
    manifest = read_json(plan_directory / "manifest.json")
    if manifest["input_sha256"] != input_hash:
        raise ValueError("the attack plan belongs to another dataset")
    check_artifacts(plan_directory, manifest, list(manifest["artifacts"]))
    config = read_json(plan_directory / "config.json")
    validate_attack_config(config)
    if config["source_dataset_sha256"] != input_hash:
        raise ValueError("saved attack configuration belongs to another dataset")
    # use repository-relative suffixes so this remains valid after moving a checkout
    for saved_path, expected in manifest["source_sha256"].items():
        normalized = saved_path.replace("\\", "/")
        relative = next((normalized[normalized.index(prefix):] for prefix in ("src/", "schemas/", "configs/") if prefix in normalized), None)
        if relative is None or sha256(ROOT / relative) != expected:
            raise ValueError(f"attack-plan source changed since generation: {saved_path}")
    with (plan_directory / "attack-plan.jsonl").open(encoding="utf-8") as handle:
        cases = [json.loads(line) for line in handle if line.strip()]
    return config, cases, manifest


def load_motion_models(records: list[dict], config: dict, input_hash: str) -> tuple[dict, dict]:
    reference = ROOT / config["snn_reference_directory"]
    if not (reference / "COMPLETE").is_file():
        raise ValueError("the frozen SNN reference run is incomplete")
    manifest = read_json(reference / "manifest.json")
    if manifest["input_sha256"] != input_hash:
        raise ValueError("the frozen SNN was trained on a different dataset")
    required = ["config.json", "normalization.json"] + [f"seed-{seed}/model-state.pt" for seed in config["motion_model_seeds"]]
    check_artifacts(reference, manifest, required)
    snn_config = read_json(reference / "config.json")
    validate_snn_config(snn_config)
    if snn_config["model"]["hidden_neurons"] != config["snn_hidden_neurons"] or snn_config["training"]["random_seeds"] != config["motion_model_seeds"]:
        raise ValueError("the selected SNN checkpoints differ from the frozen baseline policy")
    normalization = read_json(reference / "normalization.json")
    if normalization["fitted_from"] != "train":
        raise ValueError("SNN normalization must come from the historical training split")
    datasets = baseline.build_datasets(records)
    models = {}
    for seed, training_seed in zip(config["motion_model_seeds"], snn_config["training"]["training_seeds"]):
        # conventional model states were not saved in Week 4, so refit the unchanged clean-only recipe
        for name, model in baseline.create_models(seed).items():
            model.fit(datasets["train"]["features"], datasets["train"]["labels"])
            models[f"motion_{name}_seed{seed}"] = {"kind": name, "seed": seed, "model": model}
        path = reference / f"seed-{seed}/model-state.pt"
        state = torch.load(path, map_location="cpu", weights_only=True)
        if state["seed"] != seed or state["training_seed"] != training_seed or tuple(state["labels"]) != LABELS or state["model_config"] != snn_config["model"]:
            raise ValueError("checkpoint metadata does not match the frozen SNN configuration")
        model = create_model(state["model_config"])
        model.load_state_dict(state["state_dict"])
        model.eval()
        models[f"motion_snn_seed{seed}"] = {"kind": "snn", "seed": seed, "model": model, "normalization": normalization}
    provenance = {"reference_directory": str(reference), "reference_manifest_sha256": sha256(reference / "manifest.json"), "reference_source_commit": manifest["git"]["commit"], "files": {name: sha256(reference / name) for name in required}, "conventional_model_policy": "refit the frozen Week 4 recipe on original clean Session 1 only; no attack training or retuning", "snn_policy": "load frozen 64-neuron checkpoints; do not train or replace with the 32-neuron ablation"}
    return models, provenance


def fit_detectors(cohorts: dict, config: dict, output: Path) -> tuple[dict, dict]:
    train = cohorts["train"]
    validation = cohorts["validation"]
    detectors = {}
    thresholds = {}
    for seed in config["anomaly_model_seeds"]:
        fitted = fit_anomaly_models(train["anomaly_features"], train["cases"], config, seed)
        for kind, model in fitted.items():
            name = f"anomaly_{kind}_seed{seed}"
            scores = anomaly_scores(model, validation["anomaly_features"])
            threshold = select_validation_threshold(scores, validation["cases"], config["validation_clean_fpr_limit"])
            detectors[name] = {"kind": kind, "seed": seed, "model": model, "threshold": threshold}
            thresholds[name] = {"kind": kind, "seed": seed, **threshold}
            # model binaries are local reproducible artifacts, not secrets or checked-in datasets
            joblib.dump({"model": model, "threshold": threshold, "feature_names": FEATURE_NAMES, "seed": seed}, output / "models" / f"{name}.joblib", compress=3)
            print(f"Fitted {name}: validation clean FPR {threshold['validation_clean_fpr']:.4f}, threshold {threshold['threshold']:.6f}", flush=True)
    return detectors, thresholds


def verify_cached_stage_sources(source_commit: str) -> str:
    if len(source_commit) != 40 or any(character not in "0123456789abcdef" for character in source_commit):
        raise ValueError("resume source commit must be its full lowercase Git hash")
    resolved = git_value("rev-parse", source_commit + "^{commit}")
    paths = [ROOT / "src/python/scripts/train_baselines.py", ROOT / "src/python/puf_snn/integration.py", ROOT / "src/python/puf_snn/motion_diagnostics.py", ROOT / "configs/authentication_v1.json"]
    for directory in ("anomaly", "auth", "snn"):
        paths.extend((ROOT / "src/python/puf_snn" / directory).glob("*.py"))
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        command = ["git", "-c", f"safe.directory={ROOT.as_posix()}", "-C", str(ROOT), "show", f"{resolved}:{relative}"]
        saved = subprocess.run(command, capture_output=True, check=True).stdout.replace(b"\r\n", b"\n")
        if path.read_bytes().replace(b"\r\n", b"\n") != saved:
            raise ValueError(f"cached-stage model/feature/authentication code changed: {relative}")
    return resolved


def load_cached_stages(output: Path, planned_cases: list[dict], config: dict, motion_models: dict, source_commit: str) -> tuple[dict, dict, dict, dict, dict, dict]:
    origin = verify_cached_stage_sources(source_commit)
    if read_json(output / "config.json") != config or read_json(output / "anomaly-feature-names.json") != list(FEATURE_NAMES):
        raise ValueError("saved detector settings or feature names changed; do not retune during recovery")
    names = ["config.json", "attack-config.json", "anomaly-feature-names.json", "construction-summary.json", "construction-outcomes.jsonl", "frozen-validation-thresholds.json", "unauthenticated-test-predictions.jsonl"]
    hashes = {name: sha256(output / name) for name in names}
    expected_rows = {case["case_id"]: case for case in planned_cases}
    outcomes = []
    with (output / "construction-outcomes.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            case = expected_rows.pop(row["case_id"], None)
            if case is None or any(row[field] != case[field] for field in ("source_window_id", "source_trial_id", "split", "attack_type", "severity")) or row["status"] not in ("quality_valid", "construction_failure", "quality_failure"):
                raise ValueError("saved construction rows do not match the complete attack plan")
            outcomes.append(row)
    construction = read_json(output / "construction-summary.json")
    if expected_rows or summarize_construction(outcomes) != construction:
        raise ValueError("saved construction denominators do not reconcile")
    valid_ids = {row["case_id"] for row in outcomes if row["split"] == "test" and row["status"] == "quality_valid"}
    test_cases = [case for case in planned_cases if case["case_id"] in valid_ids]
    thresholds = read_json(output / "frozen-validation-thresholds.json")
    detectors = {}
    for seed in config["anomaly_model_seeds"]:
        for kind in ("logistic_regression", "random_forest"):
            name = f"anomaly_{kind}_seed{seed}"
            relative = f"models/{name}.joblib"
            hashes[relative] = sha256(output / relative)
            # these are this researcher's own local models, not downloaded or untrusted pickle files
            saved = joblib.load(output / relative)
            threshold = thresholds[name]
            saved_threshold = {key: value for key, value in threshold.items() if key not in ("kind", "seed")}
            if saved["seed"] != seed or tuple(saved["feature_names"]) != FEATURE_NAMES or saved["threshold"] != saved_threshold or threshold["selected_from"] != "validation" or threshold["validation_clean_fpr"] > config["validation_clean_fpr_limit"] + 1e-12:
                raise ValueError("saved detector or validation threshold metadata changed")
            model = saved["model"]
            parameters = model.get_params()
            if kind == "random_forest":
                valid = parameters["n_estimators"] == config[kind]["n_estimators"] and parameters["min_samples_leaf"] == config[kind]["min_samples_leaf"] and parameters["random_state"] == seed
            else:
                valid = parameters["classifier__C"] == config[kind]["C"] and parameters["classifier__max_iter"] == config[kind]["max_iter"] and parameters["classifier__random_state"] == seed
            if not valid or model.n_features_in_ != len(FEATURE_NAMES):
                raise ValueError("saved detector hyperparameters or feature shape differ")
            detectors[name] = {"kind": kind, "seed": seed, "model": model, "threshold": saved_threshold}
    motion = {name: [] for name in motion_models}
    anomaly = {name: {"scores": [], "flags": []} for name in detectors}
    with (output / "unauthenticated-test-predictions.jsonl").open(encoding="utf-8") as handle:
        for case, row in zip_longest(test_cases, (json.loads(line) for line in handle)):
            if case is None or row is None or any(row[field] != case[field] for field in ("case_id", "source_window_id", "source_trial_id", "motion_label", "attack_type", "severity", "is_anomaly")) or set(row["motion"]) != set(motion) or set(row["anomaly"]) != set(anomaly):
                raise ValueError("saved unauthenticated predictions do not match the ordered test cohort")
            for name in motion:
                motion[name].append(LABELS.index(row["motion"][name]))
            for name in anomaly:
                value = row["anomaly"][name]
                if type(value["score"]) not in (int, float) or not np.isfinite(value["score"]) or not 0 <= value["score"] <= 1 or type(value["flag"]) is not bool or value["flag"] != (value["score"] >= detectors[name]["threshold"]["threshold"]):
                    raise ValueError("saved anomaly scores/flags do not match frozen thresholds")
                anomaly[name]["scores"].append(value["score"])
                anomaly[name]["flags"].append(value["flag"])
    predictions = {"motion": {name: np.asarray(values, dtype=np.int64) for name, values in motion.items()}, "anomaly": {name: {"scores": np.asarray(values["scores"]), "flags": np.asarray(values["flags"], dtype=bool)} for name, values in anomaly.items()}}
    provenance = {"cached_stages_source_commit": origin, "cached_artifact_sha256": hashes, "hash_capture_policy": "first recovery captures hashes of trusted local partial-run files; no original partial-run hash manifest existed", "scope": "reuse construction outcomes, fitted detectors, frozen validation thresholds and unauthenticated predictions; restart authentication unless checkpoint rows exist"}
    return {"cases": test_cases}, construction, detectors, thresholds, predictions, provenance


def bind_recovery_context(output: Path, context: dict) -> None:
    path = output / "authentication-context.json"
    if path.exists():
        if read_json(path) != context:
            raise ValueError("checkpoint inputs, models or evaluation code changed; preserve existing evidence and stop")
    else:
        write_json(path, context)


def prediction_rows(cases: list[dict], motion: dict, anomaly: dict):
    for index, case in enumerate(cases):
        yield {"case_id": case["case_id"], "source_window_id": case["source_window_id"], "source_trial_id": case["source_trial_id"], "motion_label": case["motion_label"], "attack_type": case["attack_type"], "severity": case["severity"], "is_anomaly": case["is_anomaly"], "motion": {name: LABELS[int(values[index])] for name, values in motion.items()}, "anomaly": {name: {"score": float(values["scores"][index]), "flag": bool(values["flags"][index])} for name, values in anomaly.items()}}


def seed_summary(report: dict, entries: dict, model_type: str, group: str, metric: str) -> tuple[float, float]:
    values = [report[name][group][metric] for name, entry in entries.items() if entry["kind"] == model_type]
    return float(np.mean(values)), float(np.std(values, ddof=1))


def write_report(output: Path, config: dict, construction: dict, unauthenticated: dict, authenticated: dict, thresholds: dict, motion_models: dict, detectors: dict, boundary: dict) -> None:
    test_counts = [counts for name, counts in construction.items() if name.startswith("test:")]
    planned = sum(counts["planned"] for counts in test_counts)
    valid = sum(counts["quality_valid"] for counts in test_counts)
    failures = planned - valid
    rows = ["# Week 5 Stream and Anomaly Evaluation", "", "## Scope and denominators", "", f"- Test sources: {unauthenticated['source_count']}; planned paired test cases: {planned}.", f"- Quality-valid evaluated cases: {valid}; pre-authentication construction/quality failures: {failures}.", "- Failed construction is not an authentication rejection or a detector true positive.", "- The separate detectors classify documented transformations, not malicious intent or real Quest behavior.", "", "## Frozen motion classifier vulnerability", "", "Mean +/- sample SD across motion seeds 7, 17 and 27. Each transform/severity has at most one case per source; pooled copies are correlated.", "", "| Model | Clean macro-F1 | Pooled quality-valid macro-F1 | Authenticated pooled macro-F1 |", "|---|---|---|---|"]
    for kind in ("logistic_regression", "random_forest", "snn"):
        clean = seed_summary(unauthenticated["motion"], motion_models, kind, "clean:clean", "macro_f1")
        pooled = seed_summary(unauthenticated["motion"], motion_models, kind, "all_quality_valid", "macro_f1")
        protected = seed_summary(authenticated["motion"], motion_models, kind, "all_quality_valid", "macro_f1")
        rows.append(f"| {kind} | {clean[0]:.4f} +/- {clean[1]:.4f} | {pooled[0]:.4f} +/- {pooled[1]:.4f} | {protected[0]:.4f} +/- {protected[1]:.4f} |")
    rows.extend(["", "The intended label stays the original clean-source task. Severe transforms can change or erase the observed task; classification errors are vulnerability measurements, not proof that the corrupted motion has an unambiguous label.", "", "## Separate anomaly detector", "", "Settings are fixed in the saved configuration. Thresholds maximize source-weighted validation F1 subject to clean validation FPR <= 5%; score >= threshold flags a case, and ties prefer the higher threshold. No test result selects a model or threshold.", "", "| Detector | Test precision | Test recall | Test F1 | Clean test FPR | Medium/high recall |", "|---|---|---|---|---|---|"])
    target_verdicts = []
    for kind in ("logistic_regression", "random_forest"):
        measured = [seed_summary(unauthenticated["anomaly"], detectors, kind, "all_quality_valid", metric) for metric in ("precision", "recall", "f1", "clean_false_positive_rate")]
        severe = seed_summary(unauthenticated["anomaly"], detectors, kind, "medium_high_quality_valid", "recall")
        rows.append(f"| {kind} | " + " | ".join(f"{mean:.4f} +/- {sd:.4f}" for mean, sd in measured + [severe]) + " |")
        target_verdicts.append(f"{kind}: mean medium/high recall {'meets' if severe[0] >= config['medium_high_detection_target'] else 'misses'} the provisional {config['medium_high_detection_target']:.0%} target. This pooled value does not establish that every transform meets it.")
    for verdict in target_verdicts:
        rows.extend(["", verdict])
    rows.extend(["", "Per-transform/severity counts, five-class confusion matrices, binary confusion counts and paired source-cluster bootstrap intervals are in results.json. Intervals condition on these synthetic devices/sessions; they do not establish cross-device or human generalization. Model-seed SD is reported separately from source uncertainty.", "", "## Authentication boundary", "", f"- Real sender/verifier accepts and releases: {boundary['accepted_test_cases']}; fresh synthetic sessions: {boundary['fresh_sessions']}.", "- Both branches use the same immutable accepted sensor data; paired motion and anomaly features match exactly before inference.", "- Anomaly flags remain downstream results and do not alter authentication acceptance, committed sequence state or at-most-once delivery.", f"- Batched unauthenticated versus single-window authenticated motion prediction differences: {boundary['motion_prediction_differences']}.", f"- Detector flag differences: {boundary['anomaly_flag_differences']}; maximum score difference: {boundary['maximum_anomaly_score_difference']:.12g}.", "- Differences are reported, not silently overwritten. Accuracy uses batched unauthenticated predictions and single-window authenticated predictions; this run is not a latency benchmark.", "", "## Limits and saved evidence", "", "- Training weights give each source equal mass, split equally between its one clean case and its constructed transforms. Reported precision/F1 still depend on the synthetic case mixture, not an operational attack prevalence.", "- Source jitter/drop metadata are not features. Resampled timestamp disturbances are visible only through effects retained in the motion payload.", "- Known-correct synthetic credential candidates isolate the stream boundary. Reconstruction reliability, independent pre-HKDF verification, formal Tier-1 attack rates and durable audit timings are not measured.", "- Authentication is run on the held-out test cohort only; training/validation construction success is not reported as measured authentication acceptance.", "- No new detector-inclusive matched latency benchmark, human recordings or deployed Quest results are claimed.", "- Local models/ binaries are ignored by Git. Their hashes, dependency versions, configuration and reproducible training path are recorded; load only your own trusted model artifacts.", "- COMPLETE means this configured stream evaluation finished, not that every Week 5 or shared-system requirement has finished.", ""])
    report = "\n".join(rows)
    report_path = output / "stream-evaluation.md"
    if report_path.exists():
        if report_path.read_text(encoding="utf-8") != report:
            raise ValueError("existing report differs; preserve it and stop")
    else:
        with report_path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(report)


def save_detection_figures(output: Path, report: dict, detectors: dict) -> None:
    attacks = ("position_noise", "orientation_noise", "position_drift", "orientation_drift", "timestamp_jitter", "dropped_samples", "frozen_pose", "position_jump", "orientation_jump")
    for kind in ("logistic_regression", "random_forest"):
        detector_name = next(name for name, entry in detectors.items() if entry["kind"] == kind)
        values = np.asarray([[seed_summary(report["anomaly"], detectors, kind, f"{attack}:{severity}", "recall")[0] if f"{attack}:{severity}" in report["anomaly"][detector_name] else np.nan for severity in ("low", "medium", "high")] for attack in attacks])
        figure, axis = plt.subplots(figsize=(6.8, 6.5))
        colors = plt.get_cmap("Blues").with_extremes(bad="lightgray")
        heatmap = axis.imshow(np.ma.masked_invalid(values), vmin=0, vmax=1, cmap=colors, aspect="auto")
        axis.set_xticks(range(3), ("low", "medium", "high"))
        axis.set_yticks(range(len(attacks)), [name.replace("_", " ") for name in attacks])
        axis.set_title(f"{kind.replace('_', ' ').title()} anomaly recall\nQuality-valid test cases; mean across detector seeds")
        for row in range(len(attacks)):
            for column in range(3):
                label = f"{values[row, column]:.2f}" if np.isfinite(values[row, column]) else "N/A"
                axis.text(column, row, label, ha="center", va="center", color="white" if values[row, column] > 0.6 else "black")
        figure.colorbar(heatmap, ax=axis, label="Detection recall")
        figure.tight_layout()
        figure_path = output / f"{kind}-detection-recall.png"
        if not figure_path.exists():
            figure.savefig(figure_path, dpi=160)
        plt.close(figure)


def git_value(*arguments: str) -> str:
    command = ["git", "-c", f"safe.directory={ROOT.as_posix()}", "-C", str(ROOT), *arguments]
    return subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate frozen motion models and separate Tier 2 anomaly detectors")
    parser.add_argument("--input", type=Path, default=ROOT / "data/generated/synthetic-windows.jsonl")
    parser.add_argument("--plan", type=Path, default=ROOT / "results/week-5/keegan/stream-attacks")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/stream_evaluation.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/week-5/keegan/stream-evaluation")
    parser.add_argument("--resume", action="store_true", help="reuse trusted local saved stages and any accepted-window checkpoints")
    parser.add_argument("--resume-source-commit", help="full source commit of the partial run; required for its first recovery")
    args = parser.parse_args()
    started = time.perf_counter()
    config = read_json(args.config)
    validate_evaluation_config(config)
    input_hash = sha256(args.input)
    if input_hash != config["source_dataset_sha256"]:
        raise ValueError("source data differs from the frozen Week 4 dataset")
    if args.resume and (not args.output.is_dir() or (args.output / "COMPLETE").exists()):
        raise ValueError("resume requires an existing incomplete evaluation; completed runs are never overwritten")
    if not args.resume and args.output.exists():
        raise FileExistsError("preserve existing evaluation evidence and choose a new output directory")
    attack_config, cases, plan_manifest = load_plan(args.plan, input_hash)
    records = load_records(args.input)
    schema = read_json(ROOT / "schemas/quest-window.schema.json")
    pilot = read_json(ROOT / "configs/pilot.json")
    errors = validate_dataset(records, schema, config=pilot)
    if errors:
        raise ValueError("source validation failed: " + "; ".join(errors[:5]))
    assert_no_full_window_duplicates(records)
    assert_plan_matches(records, attack_config, cases)
    torch.set_num_threads(config["torch_threads"])
    torch.use_deterministic_algorithms(True)
    models, reference = load_motion_models(records, config, input_hash)
    source_commit = git_value("rev-parse", "HEAD")
    status_arguments = ["status", "--porcelain"]
    if args.output.resolve().is_relative_to(ROOT.resolve()):
        status_arguments.extend(["--", ".", ":(exclude)" + args.output.resolve().relative_to(ROOT.resolve()).as_posix()])
    source_dirty = bool(git_value(*status_arguments))
    if source_dirty:
        raise ValueError("commit source/test changes before evaluation; only this output directory may remain untracked")
    recovery = None
    if args.resume:
        context_path = args.output / "authentication-context.json"
        existing_context = read_json(context_path) if context_path.exists() else None
        origin = args.resume_source_commit or (existing_context["origin_source_commit"] if existing_context is not None else None)
        if origin is None:
            raise ValueError("first recovery needs --resume-source-commit with the partial run's full source commit")
        if read_json(args.output / "attack-config.json") != attack_config:
            raise ValueError("cached attacks differ from the frozen plan")
        test, construction, detectors, thresholds, predictions, recovery = load_cached_stages(args.output, cases, config, models, origin)
        motion_predictions = predictions["motion"]
        anomaly_predictions = predictions["anomaly"]
        print(f"Reusing saved construction, six fitted detectors, frozen thresholds and {len(test['cases'])} unauthenticated test predictions", flush=True)
    else:
        origin = source_commit
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / "models").mkdir()
        write_json(args.output / "config.json", config)
        write_json(args.output / "attack-config.json", attack_config)
        write_json(args.output / "anomaly-feature-names.json", list(FEATURE_NAMES))
        print("Constructing the complete plan; failed cases remain recorded", flush=True)
        progress = lambda done, total: print(f"Constructed {done}/{total} planned cases", flush=True)
        cohorts, outcomes = construct_cohorts(records, cases, progress)
        construction = summarize_construction(outcomes)
        write_json(args.output / "construction-summary.json", construction)
        write_rows(args.output / "construction-outcomes.jsonl", outcomes)
        detectors, thresholds = fit_detectors(cohorts, config, args.output)
        write_json(args.output / "frozen-validation-thresholds.json", thresholds)
        print("Thresholds frozen; starting held-out test prediction", flush=True)
        test = cohorts["test"]
        motion_predictions = predict_motion_models(models, test["sequences"], config["unauthenticated_prediction_batch_size"])
        anomaly_predictions = predict_detectors(detectors, test["anomaly_features"])
    unauthenticated = summarize_predictions(test["cases"], motion_predictions, anomaly_predictions, config)
    write_rows(args.output / "unauthenticated-test-predictions.jsonl", prediction_rows(test["cases"], motion_predictions, anomaly_predictions))
    print("Starting real authenticated test delivery; this is the slow single-window stage", flush=True)
    auth_config = AuthConfig.load(ROOT / "configs/authentication_v1.json")
    material = initialize_material()
    cached_names = ["config.json", "attack-config.json", "anomaly-feature-names.json", "construction-summary.json", "construction-outcomes.jsonl", "frozen-validation-thresholds.json", "unauthenticated-test-predictions.jsonl"] + [f"models/{name}.joblib" for name in detectors]
    context = {"checkpoint_version": "accepted-stream-evaluation-v1", "origin_source_commit": origin, "input_sha256": input_hash, "plan_manifest_sha256": sha256(args.plan / "manifest.json"), "configuration": config, "cached_artifact_sha256": {name: sha256(args.output / name) for name in cached_names}, "evaluation_code_sha256": {"runner": sha256(Path(__file__)), "accepted_path": sha256(ROOT / "src/python/puf_snn/attacks/evaluation.py")}, "motion_reference": reference["files"], "authentication_config_sha256": sha256(ROOT / "configs/authentication_v1.json")}
    bind_recovery_context(args.output, context)
    progress = lambda done, total: print(f"Authenticated and evaluated {done}/{total} quality-valid test cases", flush=True)
    accepted = evaluate_authenticated_cases(records, test, models, detectors, auth_config, establish, material, config["authenticated_session_case_limit"], progress, args.output / "authentication-checkpoint.jsonl", args.output / "session-events.jsonl")
    authenticated = summarize_predictions(test["cases"], accepted["motion"], accepted["anomaly"], config)
    write_rows(args.output / "authenticated-test-predictions.jsonl", prediction_rows(test["cases"], accepted["motion"], accepted["anomaly"]))
    write_rows(args.output / "accepted-delivery-evidence.jsonl", accepted["evidence"])
    boundary = {"accepted_test_cases": len(accepted["evidence"]), "fresh_sessions": accepted["session_count"], "paired_model_inputs_match": True, "motion_prediction_differences": {name: int((motion_predictions[name] != accepted["motion"][name]).sum()) for name in models}, "anomaly_flag_differences": {name: int((anomaly_predictions[name]["flags"] != accepted["anomaly"][name]["flags"]).sum()) for name in detectors}, "maximum_anomaly_score_difference": max(float(np.max(np.abs(anomaly_predictions[name]["scores"] - accepted["anomaly"][name]["scores"]))) for name in detectors), "authentication_scope": "quality-valid test cases; known-correct synthetic candidate; no PUF reliability inference"}
    results = {"construction": construction, "thresholds": thresholds, "unauthenticated": unauthenticated, "authenticated": authenticated, "boundary": boundary, "latency_evaluation_executed": False}
    results["recovery"] = recovery
    results["reused_authenticated_checkpoint_cases"] = accepted["reused_checkpoint_cases"]
    results["session_event_count"] = sum(1 for line in (args.output / "session-events.jsonl").open(encoding="utf-8") if line.strip())
    write_json(args.output / "results.json", results)
    save_detection_figures(args.output, unauthenticated, detectors)
    write_report(args.output, config, construction, unauthenticated, authenticated, thresholds, models, detectors, boundary)
    sources = [Path(__file__), Path(baseline.__file__), ROOT / "src/python/scripts/run_layer3_demo.py", ROOT / "src/python/puf_snn/integration.py", ROOT / "src/python/puf_snn/motion_diagnostics.py", ROOT / "src/python/puf_snn/data/validation.py", ROOT / "configs/authentication_v1.json", ROOT / "configs/pilot.json", ROOT / "schemas/quest-window.schema.json"]
    for directory in ("anomaly", "attacks", "auth", "snn", "reconstruction"):
        sources.extend((ROOT / "src/python/puf_snn" / directory).glob("*.py"))
    artifacts = {path.relative_to(args.output).as_posix(): sha256(path) for path in sorted(args.output.rglob("*")) if path.is_file()}
    constructed_counts = {status: sum(row[status] for row in construction.values()) for status in ("quality_valid", "construction_failure", "quality_failure")}
    manifest = {"run_type": "tier2_motion_and_supervised_anomaly_evaluation", "source_commit": source_commit, "source_worktree_dirty": source_dirty, "input_sha256": input_hash, "attack_plan_manifest_sha256": sha256(args.plan / "manifest.json"), "attack_plan_source_commit": plan_manifest["source_commit"], "config_sha256": sha256(args.config), "source_sha256": {str(path.resolve()): sha256(path) for path in sources}, "frozen_motion_reference": reference, "command": [sys.executable, *sys.argv], "environment": {"python": platform.python_version(), "platform": platform.platform(), "versions": {name: version(name) for name in ("numpy", "scikit-learn", "torch", "galois", "joblib", "matplotlib")}, "torch_threads": config["torch_threads"]}, "runtime_seconds_not_inference_latency": time.perf_counter() - started, "runtime_scope": "this invocation only; reused earlier stages are not included", "planned_cases": len(cases), "constructed_counts": constructed_counts, "test_accepted_cases": len(accepted["evidence"]), "recovery": recovery, "reused_authenticated_checkpoint_cases": accepted["reused_checkpoint_cases"], "artifacts": artifacts, "git_ignored_artifacts": [name for name in artifacts if name.startswith("models/")], "limits": "paired synthetic transforms, fixed cross-session split, no detector-inclusive matched timing or physical Quest/PUF availability claims"}
    write_json(args.output / "manifest.json", manifest)
    write_json(args.output / "COMPLETE", {"source_commit": source_commit, "planned_cases": len(cases), "test_accepted_cases": len(accepted["evidence"])})
    print(f"Evaluation completed; saved {args.output.resolve()}", flush=True)
    print(f"Constructed outcomes: {manifest['constructed_counts']}", flush=True)


if __name__ == "__main__":
    main()
