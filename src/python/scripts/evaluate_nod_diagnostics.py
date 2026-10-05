"""Reuse saved motion sensitivity and score legitimate nod variants with frozen detectors."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
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

from puf_snn.anomaly.detector import anomaly_scores
from puf_snn.anomaly.features import FEATURE_NAMES, record_to_anomaly_features
from puf_snn.attacks.reporting import binomial_interval, read_json, sha256
from puf_snn.attacks.stream import canonical_motion_record
from puf_snn.data.generator import generate_records
from puf_snn.motion_diagnostics import angular_velocity, record_times, rotation_vectors
from puf_snn import nod_diagnostics as diagnostics
from puf_snn.snn.dataset import load_records, record_to_sequence
from summarize_stream_evaluation import git_value, write_csv, write_json


def generated_hash(records) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update((json.dumps(record, allow_nan=False) + "\n").encode("utf-8"))
    return digest.hexdigest()


def check_historical_sources(commit: str, paths: list[str]) -> dict:
    hashes = {}
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ValueError("invalid historical source commit")
    for relative in paths:
        saved = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{commit}:{relative}"])
        current = (ROOT / relative).read_bytes()
        if saved.replace(b"\r\n", b"\n") != current.replace(b"\r\n", b"\n"):
            raise ValueError(f"historical generator/feature code changed: {relative}; stop rather than silently mixing methods")
        hashes[relative] = sha256(ROOT / relative)
    return hashes


def trajectories(record: dict) -> dict:
    sequence = record_to_sequence(record)
    rotation = np.rad2deg(rotation_vectors(sequence[:, 3:7]))
    angles = np.linalg.norm(rotation, axis=1)
    angular = np.rad2deg(angular_velocity(sequence, record_times(record)))
    return {"times_s": record_times(record).tolist(), "relative_rotation_vector_x_deg": rotation[:, 0].tolist(),
            "relative_vertical_position_m": sequence[:, 1].tolist(), "orientation_peak_deg": float(angles.max()),
            "angular_speed_rms_deg_s": float(np.sqrt(np.mean(np.linalg.norm(angular, axis=1) ** 2)))}


def save_curve_plots(motion_rows: list[dict], anomaly_rows: list[dict], output: Path) -> None:
    # Two splits, each fixed speed, with each seed visible rather than averaged into fake replication.
    for split in ("validation", "test"):
        figure, axes = plt.subplots(2, 3, figsize=(13, 7), sharex=True, sharey=True)
        for column, speed in enumerate(diagnostics.SPEEDS):
            for family, color in (("logistic_regression", "tab:blue"), ("random_forest", "tab:orange"), ("snn", "tab:green")):
                names = sorted({row["model"] for row in motion_rows if row["model"].startswith(family + "_seed_")})
                for index, name in enumerate(names):
                    rows = sorted([row for row in motion_rows if row["split"] == split and row["speed_scale"] == speed and row["model"] == name], key=lambda row: row["amplitude_scale"])
                    for axis, field in ((axes[0, column], "nod_recall"), (axes[1, column], "still_prediction_fraction")):
                        axis.plot([row["amplitude_scale"] for row in rows], [row[field] for row in rows],
                                  color=color, linestyle=("-", "--", ":")[index], marker="o", markersize=3,
                                  label=f"{family} / {name.rsplit('_', 1)[1]}")
            axes[0, column].set_title(f"Nominal speed scale {speed:g}")
            axes[1, column].set_xlabel("Intentional nod amplitude scale")
        axes[0, 0].set_ylabel("Nod recall")
        axes[1, 0].set_ylabel("Fraction predicted still")
        axes[0, 0].legend(fontsize=6)
        for axis in axes.flat:
            axis.set_ylim(-.02, 1.02)
            axis.grid(alpha=.2)
        figure.suptitle(f"{split}: historical LR/RF/SNN sensitivity, fixed models")
        figure.tight_layout()
        figure.savefig(output / f"{split}-motion-sensitivity.png", dpi=160)
        plt.close(figure)
        figure, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
        for axis, speed in zip(axes, diagnostics.SPEEDS):
            for name in sorted({row["detector"] for row in anomaly_rows}):
                rows = sorted([row for row in anomaly_rows if row["split"] == split and row["speed_scale"] == speed and row["condition"] == "nod_variant" and row["detector"] == name], key=lambda row: row["amplitude_scale"])
                axis.plot([row["amplitude_scale"] for row in rows], [row["legitimate_variant_flag_rate"] if row["legitimate_variant_flag_rate"] is not None else np.nan for row in rows], marker="o", label=name.removeprefix("anomaly_"))
            axis.set_title(f"Nominal speed scale {speed:g}")
            axis.set_xlabel("Intentional nod amplitude scale")
            axis.set_ylim(-.02, 1.02)
            axis.grid(alpha=.2)
        axes[0].set_ylabel("Legitimate nod variant flagged fraction")
        axes[0].legend(fontsize=6)
        figure.suptitle(f"{split}: saved anomaly models and frozen thresholds")
        figure.tight_layout()
        figure.savefig(output / f"{split}-anomaly-flags.png", dpi=160)
        plt.close(figure)


def save_example_plot(examples: dict, output: Path) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
    for column, split in enumerate(("validation", "test")):
        for amplitude in diagnostics.AMPLITUDES:
            row = examples[f"{split}:nod:{amplitude:g}"]
            axes[0, column].plot(row["times_s"], row["relative_rotation_vector_x_deg"], label=f"Nod {amplitude:g}x")
            axes[1, column].plot(row["times_s"], np.asarray(row["relative_vertical_position_m"]) * 1000)
        still = examples[f"{split}:still"]
        axes[0, column].plot(still["times_s"], still["relative_rotation_vector_x_deg"], color="black", linestyle="--", label="Still reference")
        axes[1, column].plot(still["times_s"], np.asarray(still["relative_vertical_position_m"]) * 1000, color="black", linestyle="--")
        axes[0, column].set_title(f"{split}: first sorted source ID, speed=1")
        axes[1, column].set_xlabel("Time from first sample (s)")
    axes[0, 0].set_ylabel("Relative rotation-vector x (degrees; not Euler pitch)")
    axes[1, 0].set_ylabel("Relative vertical position (mm)")
    axes[0, 0].legend(fontsize=7)
    for axis in axes.flat:
        axis.grid(alpha=.2)
    figure.tight_layout()
    figure.savefig(output / "paired-amplitude-trajectories.png", dpi=160)
    plt.close(figure)


def make_report(nominals, motion_rows, anomaly_rows, example_ids, blocked) -> str:
    lines = ["# Nod/still amplitude and temporal-ambiguity diagnostics", "",
             "## Question and fixed interpretation", "",
             "How do the existing motion classifiers distinguish an intentional nod from still as its intentional amplitude decreases, and do the frozen anomaly models falsely flag that legitimate execution variation?", "",
             "These synthetic nod variants are treated as legitimate natural execution variation and an increasingly ambiguous class boundary. A similar motion reduction could be adversarial in another threat scenario, but intent is not observed here. Nod recall and still-confusion quantify sensitivity to the original intended label; detector flag frequency quantifies false alarms under this stated interpretation, not attack recall. An unflagged detector result is not a prediction of the still class.", "",
             "No architecture, feature variant, threshold or attack parameter was selected using this report. The amplitude/speed grid is the already-saved Week 4 grid. Motion sensitivity results are reused, not refitted. The six local anomaly models and their validation-only thresholds are loaded unchanged; no anomaly training occurs.", "",
             "## Nominal and observed amplitude", "",
             "| Amplitude scale | Signed x-rotation coefficient (degrees) | Vertical coefficient (meters) |",
             "|---:|---:|---:|"]
    for row in nominals:
        if row["speed_scale"] == 1:
            lines.append(f'| {row["amplitude_scale"]:g} | {row["nominal_rotation_coefficient_deg"]:.2f} | {row["nominal_vertical_position_coefficient_m"]:.6f} |')
    lines.extend(["", "The unscaled nominal nod uses an x-axis rotation coefficient of -22 degrees and a vertical-position coefficient of 0.006 m. Half amplitude uses -11 degrees / 0.003 m; one-tenth uses -2.2 degrees / 0.0006 m. These are synthetic coefficients before trial/device/session amplitude effects, phase shaping, secondary-axis coupling, noise, drift, sway and return error—not measured peak angles. Those nuisance terms remain unchanged, so a one-tenth coefficient does not imply one-tenth total observed motion.", "",
                  "Speed scale changes the generator's duration-range bounds by division; the generator still multiplies group duration effects and clips to [0.75, 1.95-start_delay] seconds. It is a synthetic temporal-ambiguity stress, not a measured physical speed or a resampled hardware capture. The original 120-point grid and sample timestamps remain unchanged.", "",
                  "`nominal-conditions.json` records every amplitude/speed condition. `physical-observations.csv` records observed peak geodesic rotation and angular speed statistics per condition. Representative trajectories use the first lexicographically sorted nod and still source IDs in each split, selected without prediction results. The same nod source is used at all five amplitudes; this one illustrative example is not a population summary.", "",
                  "## Matched nominal-speed summary", "",
                  "Rates below are means across fixed model seeds on the same 120 source nods—not independent recording replications. Each curve and CSV retains every seed and both validation/test splits. Other-class predictions are reported rather than silently combining them into still.", "",
                  "| Amplitude | Motion family | Test nod recall mean | Test still-confusion mean |",
                  "|---:|---|---:|---:|"])
    for amplitude in diagnostics.AMPLITUDES:
        for family in ("logistic_regression", "random_forest", "snn"):
            rows = [row for row in motion_rows if row["split"] == "test" and row["speed_scale"] == 1 and row["amplitude_scale"] == amplitude and row["model"].startswith(family + "_seed_")]
            lines.append(f'| {amplitude:g} | {family} | {np.mean([row["nod_recall"] for row in rows]):.4f} | {np.mean([row["still_prediction_fraction"] for row in rows]):.4f} |')
    lines.extend(["", "| Condition | Anomaly family | Test legitimate flag-rate mean |",
                  "|---|---|---:|"])
    for amplitude in diagnostics.AMPLITUDES:
        for family in ("logistic_regression", "random_forest"):
            rows = [row for row in anomaly_rows if row["split"] == "test" and row["condition"] == "nod_variant" and row["speed_scale"] == 1 and row["amplitude_scale"] == amplitude and row["detector"].startswith(f"anomaly_{family}_seed")]
            values = [row["legitimate_variant_flag_rate"] for row in rows if row["legitimate_variant_flag_rate"] is not None]
            rate = f"{np.mean(values):.4f}" if values else "N/A"
            lines.append(f"| Nod {amplitude:g}x | {family} | {rate} |")
    for family in ("logistic_regression", "random_forest"):
        rows = [row for row in anomaly_rows if row["split"] == "test" and row["condition"] == "clean_still" and row["detector"].startswith(f"anomaly_{family}_seed")]
        values = [row["legitimate_variant_flag_rate"] for row in rows if row["legitimate_variant_flag_rate"] is not None]
        rate = f"{np.mean(values):.4f}" if values else "N/A"
        lines.append(f"| Original still reference | {family} | {rate} |")
    lines.extend(["", "The motion summary and anomaly summary are matched by generator condition/source cohort, but the historical sweep saved aggregate classifier counts, not per-case classifier predictions. Do not infer a joint count of 'predicted still AND anomaly flagged' from these separate marginal rates. The per-source anomaly scores are saved for audit.", "",
                  "## Quality, preprocessing and uncertainty", "",
                  f"Pre-tag canonical/quality blocks in this addendum: {blocked}. Planned and eligible denominators remain in all detector tables. A block is not a successful authentication rejection or semantic anomaly detection. All generated cases retain the clean source IDs, intended labels, original split, timestamps and tracking flags.", "",
                  "The reused historical classifier curves use their original generator-to-relative-pose preprocessing. New anomaly scoring uses the same quaternion normalization and binary32 canonical conversion as the frozen Tier-2 experiment before extracting its 48 relative-motion/time features. The input conventions are recorded separately; no new authenticated/classifier equivalence claim is made. Labels, source IDs, amplitude/speed settings and quality outcomes are not features.", "",
                  "Per-seed flag rates and sensitivity rates have two-sided 95% Clopper-Pearson intervals. One source contributes once to each condition; shared fixed device/session profiles limit independence. The intervals are descriptive conditional uncertainty, not cross-device or human-population confidence. The same paired source is reused across conditions, and seed repetitions are not independent datasets. Logistic-regression lbfgs fits are deterministic; identical seed outputs do not prove independent performance stability.", "",
                  "Low-amplitude nod labels remain the original intended task, not a claim of visually unambiguous observed motion. Conclusions are limited to cross-session synthetic data with fixed device profiles. No classifier or SNN is trained here; no threshold is retuned; no end-to-end session, latency, human recording or Quest transfer is evaluated.", "",
                  "## Artifacts", "",
                  "- `motion-sensitivity.csv`: historical LR/RF/SNN counts and rates, all model seeds/amplitudes/speeds/splits, with new descriptive intervals.",
                  "- `anomaly-sensitivity.csv`: fixed detector flag counts/rates, eligible denominators and intervals for legitimate nod variants and original still controls.",
                  "- `predictions.jsonl`: each variant's source identity, canonical quality outcome and frozen detector scores/flags.",
                  "- `physical-observations.csv`, `nominal-conditions.json`, `trajectory-examples.json`, and figures: physical interpretation and paired examples.",
                  "- `manifest.json` and `COMPLETE`: historical input/model hashes, current reporting source hashes, settings and completion binding.", "",
                  "Example source IDs:", "", *[f"- {key}: `{value}`" for key, value in sorted(example_ids.items())], ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/generated/synthetic-windows.jsonl")
    parser.add_argument("--pilot", type=Path, default=ROOT / "configs/pilot.json")
    parser.add_argument("--motion-reference", type=Path, default=ROOT / "results/week-4/keegan/motion-analysis")
    parser.add_argument("--detector-reference", type=Path, default=ROOT / "results/week-5/keegan/stream-evaluation")
    parser.add_argument("--output", type=Path, default=ROOT / "results/week-5/keegan/nod-diagnostics")
    args = parser.parse_args()
    output = args.output.resolve()
    references = [args.motion_reference.resolve(), args.detector_reference.resolve()]
    if any(output == path or path in output.parents or output in path.parents for path in references):
        raise ValueError("output must be separate from both historical references")
    if output.exists():
        raise FileExistsError("output exists; preserve it and choose another --output directory")
    for path in references:
        if not (path / "COMPLETE").is_file():
            raise ValueError("historical reference is incomplete")
    motion_manifest = read_json(args.motion_reference / "manifest.json")
    detector_manifest = read_json(args.detector_reference / "manifest.json")
    input_hash = sha256(args.input)
    if input_hash != motion_manifest["input_sha256"] or input_hash != detector_manifest["input_sha256"]:
        raise ValueError("historical references belong to another dataset")
    diagnostics.require_hash(args.pilot, motion_manifest["pilot_sha256"])
    checked = {"dataset": input_hash, "pilot": sha256(args.pilot)}
    for directory, manifest, names in ((args.motion_reference, motion_manifest, ["nod-still-sweep.json", "configuration.json"]),
                                       (args.detector_reference, detector_manifest, ["frozen-validation-thresholds.json", "anomaly-feature-names.json"])):
        for name in names:
            diagnostics.require_hash(directory / name, manifest["artifacts"].get(name, ""))
            checked[f"{directory.name}/{name}"] = sha256(directory / name)
    sources = load_records(args.input)
    pilot = read_json(args.pilot)
    if generated_hash(generate_records(pilot)) != input_hash:
        raise ValueError("pilot no longer regenerates the frozen source dataset")
    motion_rows = diagnostics.validate_saved_sweep(read_json(args.motion_reference / "nod-still-sweep.json"),
                                                  read_json(args.motion_reference / "configuration.json"), sources)
    for row in motion_rows:
        for field, count_field in (("nod_recall", "nod_prediction_count"), ("still_fraction", "still_prediction_count")):
            low, high = binomial_interval(row[count_field], row["sample_count"])
            row[f"{field}_ci_low"], row[f"{field}_ci_high"] = low, high
    source_hashes = check_historical_sources(motion_manifest["git_commit"], [
        "src/python/puf_snn/data/generator.py", "src/python/puf_snn/motion_diagnostics.py", "src/python/puf_snn/snn/dataset.py"])
    source_hashes.update(check_historical_sources(detector_manifest["source_commit"], [
        "src/python/puf_snn/anomaly/features.py", "src/python/puf_snn/anomaly/detector.py",
        "src/python/puf_snn/attacks/stream.py", "src/python/puf_snn/integration.py",
        "src/python/puf_snn/auth/binary_window.py"]))
    thresholds = read_json(args.detector_reference / "frozen-validation-thresholds.json")
    if tuple(read_json(args.detector_reference / "anomaly-feature-names.json")) != FEATURE_NAMES:
        raise ValueError("frozen detector feature ordering differs")
    detectors, model_hashes = diagnostics.load_verified_detectors(args.detector_reference, detector_manifest,
                                                                  thresholds, FEATURE_NAMES, joblib.load)
    example_ids = diagnostics.example_source_ids(sources)
    nominals = [diagnostics.nominal_values(pilot, amplitude, speed) for amplitude in diagnostics.AMPLITUDES for speed in diagnostics.SPEEDS]
    git_status = git_value(ROOT, "status", "--porcelain")
    anomaly_rows, physical_rows, examples = [], [], {}
    blocked = 0
    output.mkdir(parents=True, exist_ok=False)
    with (output / "predictions.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        conditions = [("nod_variant", amplitude, speed) for amplitude in diagnostics.AMPLITUDES for speed in diagnostics.SPEEDS] + [("clean_still", None, None)]
        for condition, amplitude, speed in conditions:
            generated = [record for record in generate_records(diagnostics.nod_config(pilot, amplitude, speed)) if record["label"] == "nod"] if condition == "nod_variant" else [deepcopy(record) for record in sources if record["label"] == "still"]
            if condition == "nod_variant":
                diagnostics.assert_paired_sources(generated, sources)
            for split in ("validation", "test"):
                cohort = sorted([record for record in generated if record["split"] == split], key=lambda record: record["window_id"])
                ready, measurements, features = [], [], []
                for record in cohort:
                    metadata = {"source_window_id": record["window_id"], "source_trial_id": record["source_trial_id"],
                                "split": split, "condition": condition, "amplitude_scale": amplitude, "speed_scale": speed,
                                "intended_label": record["label"], "semantic_interpretation": "legitimate_variation_or_still_control"}
                    try:
                        canonical = canonical_motion_record(record)
                        feature = record_to_anomaly_features(canonical)
                    except (ValueError, OverflowError) as error:
                        blocked += 1
                        stream.write(json.dumps({**metadata, "status": "pre_tag_quality_blocked", "reason": str(error)}, sort_keys=True, allow_nan=False) + "\n")
                        continue
                    measured = trajectories(canonical)
                    label = record["label"]
                    if record["window_id"] == example_ids[f"{split}:{label}"] and (condition == "clean_still" or speed == 1):
                        key = f"{split}:still" if condition == "clean_still" else f"{split}:nod:{amplitude:g}"
                        examples[key] = {**metadata, **measured}
                    ready.append(metadata)
                    measurements.append(measured)
                    features.append(feature)
                scores = diagnostics.score_fixed_detectors(np.stack(features), detectors, thresholds, anomaly_scores) if features else {}
                for index, metadata in enumerate(ready):
                    predictions = {name: {"score": float(value["scores"][index]), "flag": bool(value["flags"][index])} for name, value in scores.items()}
                    stream.write(json.dumps({**metadata, "status": "quality_valid", "anomaly": predictions,
                                             "orientation_peak_deg": measurements[index]["orientation_peak_deg"]}, sort_keys=True, allow_nan=False) + "\n")
                for name in detectors:
                    flagged = int(scores[name]["flags"].sum()) if ready else 0
                    anomaly_rows.append({"detector": name, "split": split, "condition": condition,
                                         "amplitude_scale": amplitude, "speed_scale": speed, "frozen_threshold": thresholds[name]["threshold"],
                                         **diagnostics.summarize_flags(flagged, len(ready), len(cohort), binomial_interval)})
                physical_rows.append({"split": split, "condition": condition, "amplitude_scale": amplitude, "speed_scale": speed,
                                      "planned_count": len(cohort), "quality_valid_count": len(ready),
                                      "mean_observed_peak_rotation_deg": float(np.mean([row["orientation_peak_deg"] for row in measurements])) if ready else None,
                                      "mean_observed_angular_speed_rms_deg_s": float(np.mean([row["angular_speed_rms_deg_s"] for row in measurements])) if ready else None})
            print(f"Scored frozen detectors: {condition}, amplitude={amplitude}, speed={speed}", flush=True)
    if len(examples) != 12:
        raise ValueError("a preselected trajectory example failed quality checks; preserve partial outputs and investigate")
    write_csv(output / "motion-sensitivity.csv", motion_rows)
    write_csv(output / "anomaly-sensitivity.csv", anomaly_rows)
    write_csv(output / "physical-observations.csv", physical_rows)
    write_json(output / "nominal-conditions.json", nominals)
    write_json(output / "trajectory-examples.json", examples)
    write_json(output / "frozen-validation-thresholds.json", thresholds)
    save_curve_plots(motion_rows, anomaly_rows, output)
    save_example_plot(examples, output)
    (output / "nod-diagnostics.md").write_text(make_report(nominals, motion_rows, anomaly_rows, example_ids, blocked), encoding="utf-8", newline="\n")
    (output / ".gitattributes").write_text("* -text\n.gitattributes text eol=lf\n", encoding="utf-8", newline="\n")
    source_hashes.update({Path(__file__).relative_to(ROOT).as_posix(): sha256(Path(__file__)),
                          "src/python/puf_snn/nod_diagnostics.py": sha256(Path(diagnostics.__file__)),
                          "src/python/puf_snn/attacks/stream.py": sha256(ROOT / "src/python/puf_snn/attacks/stream.py"),
                          "src/python/puf_snn/attacks/reporting.py": sha256(ROOT / "src/python/puf_snn/attacks/reporting.py")})
    write_json(output / "manifest.json", {
        "run_type": "paired_legitimate_nod_diagnostics_v1", "source_commit": git_value(ROOT, "rev-parse", "HEAD"),
        "source_worktree_dirty": None if git_status is None else bool(git_status),
        "command": subprocess.list2cmdline([sys.executable, *sys.argv]), "input_sha256": checked,
        "model_artifacts_sha256": model_hashes, "source_sha256": source_hashes,
        "historical_motion_manifest_sha256": sha256(args.motion_reference / "manifest.json"),
        "historical_detector_manifest_sha256": sha256(args.detector_reference / "manifest.json"),
        "pre_tag_quality_blocked_count": blocked, "classifier_inference_executed": False,
        "anomaly_inference_executed": True, "training_executed": False, "threshold_selection_executed": False,
        "authentication_executed": False, "historical_files_modified": False,
        "nominal_conditions": nominals, "example_selection": "first sorted source ID in each split and label, before inference",
        "environment": {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__,
                        "sklearn": sklearn.__version__, "joblib": joblib.__version__},
        "artifacts": {path.name: sha256(path) for path in sorted(output.iterdir()) if path.is_file()},
    })
    write_json(output / "COMPLETE", {"manifest_sha256": sha256(output / "manifest.json"),
                                     "historical_motion_condition_rows": len(motion_rows),
                                     "anomaly_condition_rows": len(anomaly_rows), "pre_tag_quality_blocked_count": blocked})
    print(f"PASS: reused {len(motion_rows)} historical motion rows; scored {len(anomaly_rows)} detector condition rows")
    print("No model fitting, threshold selection, classifier rerun or authentication occurred")
    print(f"Saved results to {output}")


if __name__ == "__main__":
    main()
