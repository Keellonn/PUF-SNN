"""Audit nearest-training orientation and complete 120 x 7 inputs without retraining."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/python"))

import numpy as np

from puf_snn import sequence_neighbors as audit
from puf_snn.data.generator import generate_records
from puf_snn.motion_diagnostics import assert_no_full_window_duplicates, distribution
from puf_snn.snn.dataset import build_snn_datasets, load_records


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def generated_hash(records: list[dict]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update((json.dumps(record, allow_nan=False) + "\n").encode("utf-8"))
    return digest.hexdigest()


def historical_input(directory: Path, manifest: dict, name: str):
    path = directory / name
    if not path.is_file() or sha256(path) != manifest["artifacts"].get(name):
        raise ValueError(f"historical input is missing or hash-mismatched: {name}")
    return read_json(path)


def historical_sources(commit: str) -> dict:
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ValueError("invalid historical source commit")
    hashes = {}
    for relative in ("src/python/puf_snn/snn/dataset.py", "src/python/puf_snn/motion_diagnostics.py"):
        saved = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{commit}:{relative}"])
        current = (ROOT / relative).read_bytes()
        if saved.replace(b"\r\n", b"\n") != current.replace(b"\r\n", b"\n"):
            raise ValueError(f"historical preprocessing changed: {relative}")
        hashes[relative] = sha256(ROOT / relative)
    return hashes


def summarize(rows: list[dict]) -> list[dict]:
    summaries = []
    for split in ("validation", "test"):
        for scope in ("any_label", "same_label"):
            labels = ["all", *sorted({row["label"] for row in rows if row["split"] == split})]
            for label in labels:
                selected = [row for row in rows if row["split"] == split and row["scope"] == scope
                            and (label == "all" or row["label"] == label)]
                for metric in ("orientation_rms_deg", "normalized_sequence_rms"):
                    values = [row[metric] for row in selected]
                    summaries.append({"split": split, "scope": scope, "label": label,
                                      "metric": metric, **distribution(values)})
    return summaries


def make_report(summaries: list[dict], old_original: list[dict], old_corrected: list[dict],
                offsets: list[int], maximum_difference: float) -> str:
    lines = ["# Nearest-training orientation and complete-input audit", "",
             "## Question and frozen scope", "",
             "Does the corrected held-out motion remain close to training when the entire 120 x 7 model input is compared, rather than orientation alone? This is a data-similarity audit, not a new classifier, feature ablation, tuned leakage threshold or generalization experiment. Session 1 supplies all references/scaling; Sessions 2 and 3 are queries only. Original leakage evidence is retained, not replaced.", "",
             "## Exact orientation metric", "",
             "For each already fixed-grid window, use p_rel[t] = p[t] - p[0] and q_rel[t] = inverse(q[0]) * q[t] in xyzw order, after unit-normalizing quaternions and making adjacent equivalent signs continuous. Re-normalize relative quaternions before the dot product. For aligned sample index t:", "",
             "`theta[t] = (180/pi) * 2 * acos(clip(abs(dot(q_rel_query[t], q_rel_train[t])), 0, 1))`", "",
             "`d_orientation = sqrt((1/120) * sum_t theta[t]^2)`", "",
             "This is root-mean-square shortest rotation angle in degrees, not the mean angle or maximum angle. Absolute starting pose is removed. The absolute dot product makes the physical metric invariant to q versus -q. Find the minimum distance over all 600 training windows (any-label scope), or over the 120 training windows with the query's intended class (same-label scope). Same-label filtering is a descriptive stratification, not a feature or prediction.", "",
             "### Alignment and processing boundary", "",
             f"The input has 120 ordered samples on a shared grid: adjacent interval {offsets[1]} ns; last relative timestamp {offsets[-1]} ns. Align t with t after subtracting each window's first timestamp. There is no dynamic time warping, interpolation, phase matching or time-shift search. The clean synthetic generator already outputs this grid; no resampling occurs in this audit. The physical orientation distance is after quaternion normalization/first-pose subtraction, but before learned statistical normalization and before Wire 2.0 binary32 conversion. It is not a distance on irregular raw Quest captures.", "",
             "## Complete 120 x 7 input metric", "",
             "Fit one mean mu[c] and population standard deviation sigma[c] per pose channel across all 600 training windows and all 120 time points. Replace sigma <= 1e-12 with 1, matching the SNN pipeline. No validation/test observation affects scaling. Save all seven means/SDs and the ordered training source IDs. Normalize using the existing SNN routine and its float32 model-input rounding; promote to float64 only to accumulate distances.", "",
             "`z[t,c] = float32((x_rel[t,c] - mu[c]) / sigma[c])`", "",
             "`d_sequence = sqrt((1/840) * sum_{t=0..119,c=0..6} (z_query[t,c] - z_train[t,c])^2)`", "",
             "All 840 coordinates contribute: three relative-position channels and four relative-quaternion channels. This distance is dimensionless. It uses the SNN's seven-channel training scaler, not LR's 840-feature scaler. Quaternion-component Euclidean distance is not the same as geodesic rotation distance; the canonical first-relative identity and continuous-sign preprocessing fix the model's representation. Retain the physical orientation metric alongside it. Labels, IDs, timestamps, tracking flags and attack settings are not input coordinates.", "",
             "Nearest feature and nearest orientation references may differ; per-source rows save both reference IDs and the physical orientation distance to the feature-nearest reference. Ties choose the first lexicographically sorted training ID. No near/far cutoff is selected from held-out results. A small distance does not by itself prove leakage, and a nonzero distance does not establish real-world generalization. Still-like trajectories can legitimately be similar.", "",
             "## Historical orientation evidence, retained", "",
             "The rows below reuse the hash-checked Week 4 test-to-training physical distances. The original full 120 x 7 distance is not recalculated or implied here; the new full-input audit uses the corrected frozen dataset. This preserves the original orientation-template failure without executing an old generator.", "",
             "| Dataset | Scope | Windows | Minimum orientation RMS (deg) | Median orientation RMS (deg) |", "|---|---|---:|---:|---:|"]
    for name, rows in (("Original", old_original), ("Corrected", old_corrected)):
        for scope in ("any_label", "same_label"):
            values = [row["orientation_rms_deg"] for row in rows if row["scope"] == scope]
            stats = distribution(values)
            lines.append(f"| {name} | {scope} | {stats['count']} | {stats['minimum']:.6f} | {stats['median']:.6f} |")
    lines.extend(["", f"All 1,200 corrected historical test/scope distances were reconciled. Maximum recomputation difference: {maximum_difference:.9g} degrees (tolerance 1e-5 degrees, only for floating-point quaternion renormalization). No original report or result manifest was modified.", "",
                  "## New corrected-input results", "",
                  "| Query split | Scope | Metric | Windows | Minimum | Median | p95 |",
                  "|---|---|---|---:|---:|---:|---:|"])
    for row in summaries:
        if row["label"] == "all":
            lines.append(f"| {row['split']} | {row['scope']} | {row['metric']} | {row['count']} | {row['minimum']:.6f} | {row['median']:.6f} | {row['p95']:.6f} |")
    lines.extend(["", "`summary.json` also reports each class separately with count/minimum/p05/median/mean/p95/maximum. `nearest-training.csv` retains every query and both scopes (2,400 rows). Exact full-content equality across all three split pairs is checked separately by the existing full-window hash policy, which includes relative timing and tracking quality.", "",
                  "## Seed roles and limitations", "",
                  "Data generation uses seed 7. Fixed session-index assignment has no split RNG. Re-running that generator is deterministic reproduction, not a second sampled dataset. Conventional/SNN fitting seeds do not alter these frozen input windows. This audit trains no model and uses no RNG. Model-seed performance variation and data-generation variation must not be pooled as independent replications. LR's lbfgs solver is deterministic for its fixed inputs; identical scores across seed labels are not independent stochastic performance samples.", "",
                  "Claims remain limited to cross-session synthetic evaluation with six fixed simulated device profiles. No cross-device, cross-person, physical headset, adversarial robustness, entropy/security or real-world transfer conclusion follows from these distances. The audit does not change data, model selection, anomaly thresholds or authentication state.", "",
                  "## Artifacts", "",
                  "- `nearest-training.csv`: per-query full-input/physical distance and nearest reference IDs, both query splits/scopes.",
                  "- `summary.json`: all-class and per-class distance distributions.",
                  "- `training-normalization.json`: seven training-only means/SDs and ordered training window IDs.",
                  "- `audit-settings.json`: formulas, alignment, dtype, query/reference roles and historical reconciliation.",
                  "- `manifest.json`, `COMPLETE` and `.gitattributes`: input/source/artifact hashes, completion binding and byte-preserving checkouts.", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/generated/synthetic-windows.jsonl")
    parser.add_argument("--pilot", type=Path, default=ROOT / "configs/pilot.json")
    parser.add_argument("--reference", type=Path, default=ROOT / "results/week-4/keegan/data-diagnostics")
    parser.add_argument("--output", type=Path, default=ROOT / "results/week-5/keegan/sequence-neighbors")
    args = parser.parse_args()
    output, reference = args.output.resolve(), args.reference.resolve()
    if output == reference or reference in output.parents or output in reference.parents:
        raise ValueError("output must be separate from historical evidence")
    if output.exists():
        raise FileExistsError("output exists; preserve it and choose another --output directory")
    if not (reference / "COMPLETE").is_file():
        raise ValueError("historical diagnostic is incomplete")
    manifest = read_json(reference / "manifest.json")
    input_hash = sha256(args.input)
    if input_hash != manifest["input_sha256"]:
        raise ValueError("dataset differs from corrected historical data")
    original = historical_input(reference, manifest, "original-nearest-neighbors.json")
    corrected = historical_input(reference, manifest, "corrected-nearest-neighbors.json")
    historical_input(reference, manifest, "data-diagnostics.json")
    pilot = read_json(args.pilot)
    if pilot["project"]["random_seed"] != pilot["randomness"]["data_generation_seed"]:
        raise ValueError("data-generation seed roles disagree")
    if generated_hash(generate_records(pilot)) != input_hash:
        raise ValueError("current pilot does not regenerate the frozen dataset")
    source_hashes = historical_sources(manifest["git_commit"])
    source_commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    status = subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True).strip()
    records = sorted(load_records(args.input), key=lambda record: record["window_id"])
    assert_no_full_window_duplicates(records)
    offsets = audit.fixed_grid_offsets(records)
    datasets = build_snn_datasets(records)
    if {name: len(value["sequences"]) for name, value in datasets.items()} != {"train": 600, "validation": 600, "test": 600}:
        raise ValueError("expected the frozen 600/600/600 split")
    scaler = audit.fit_training_scaler(datasets["train"]["sequences"])
    rows = []
    for split in ("validation", "test"):
        rows.extend(audit.nearest_training_rows(datasets["train"]["sequences"], datasets[split]["sequences"],
                                               datasets["train"]["metadata"], datasets[split]["metadata"], scaler))
        print(f"Compared all {len(datasets[split]['sequences'])} {split} windows with training only", flush=True)
    difference = audit.reconcile_historical_orientation(rows, corrected)
    summaries = summarize(rows)
    output.mkdir(parents=True, exist_ok=False)
    with (output / "nearest-training.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    write_json(output / "summary.json", summaries)
    write_json(output / "training-normalization.json", {
        "fit_split": "train", "axis": [0, 1], "ddof": 0, "zero_variance_policy": "SD <= 1e-12 replaced with 1",
        "mean": scaler["mean"].tolist(), "standard_deviation": scaler["standard_deviation"].tolist(),
        "source_window_ids": [row["window_id"] for row in datasets["train"]["metadata"]],
    })
    write_json(output / "audit-settings.json", {
        "orientation": "RMS degrees of 2*acos(abs(normalized relative-quaternion dot)) over 120 aligned indexes",
        "full_sequence": "RMS over 840 normalized float32 model-input coordinates; float64 distance accumulation",
        "alignment": "shared sample-index grid after subtracting first sample timestamp; no resampling or DTW",
        "relative_sample_offsets_ns": offsets, "chunk_size": 8, "scaling_fit_split": "train",
        "source_split_counts": {name: len(value["sequences"]) for name, value in datasets.items()},
        "historical_test_scope_rows_reconciled": len(corrected),
        "historical_orientation_maximum_difference_deg": difference,
        "historical_orientation_tolerance_deg": 1e-5, "full_content_cross_split_duplicates": 0,
        "rng_used": False, "near_far_cutoff_selected": False,
    })
    (output / "sequence-neighbors.md").write_text(make_report(summaries, original, corrected, offsets, difference),
                                                encoding="utf-8", newline="\n")
    (output / ".gitattributes").write_text("* -text\n.gitattributes text eol=lf\n", encoding="utf-8", newline="\n")
    for path in (Path(__file__), Path(audit.__file__), ROOT / "src/python/puf_snn/data/generator.py"):
        source_hashes[path.relative_to(ROOT).as_posix()] = sha256(path)
    write_json(output / "manifest.json", {
        "run_type": "fixed_grid_complete_input_neighbors_v1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": source_commit, "source_worktree_dirty": bool(status),
        "command": subprocess.list2cmdline([sys.executable, *sys.argv]),
        "input_sha256": input_hash, "current_pilot_sha256": sha256(args.pilot),
        "historical_manifest_sha256": sha256(reference / "manifest.json"),
        "historical_inputs_sha256": {name: sha256(reference / name) for name in (
            "original-nearest-neighbors.json", "corrected-nearest-neighbors.json", "data-diagnostics.json")},
        "source_sha256": source_hashes, "query_window_count": 1200, "nearest_neighbor_rows": len(rows),
        "training_executed": False, "classifier_inference_executed": False,
        "authentication_executed": False, "threshold_selection_executed": False,
        "historical_files_modified": False,
        "environment": {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__},
        "artifacts": {path.name: sha256(path) for path in sorted(output.iterdir()) if path.is_file()},
    })
    write_json(output / "COMPLETE", {"manifest_sha256": sha256(output / "manifest.json"),
                                     "query_window_count": 1200, "nearest_neighbor_rows": len(rows)})
    print(f"PASS: all {len(corrected)} historical corrected orientation rows reconciled; {len(rows)} complete-input rows saved")
    print("No model fitting, threshold selection, classifier inference or authentication occurred")
    print(f"Saved results to {output}")


if __name__ == "__main__":
    main()
