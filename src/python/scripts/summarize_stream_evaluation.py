"""Create a new, hash-linked Tier-2 reporting addendum from the completed run."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/python"))

import numpy as np
from puf_snn.attacks import reporting


def write_json(path: Path, value) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"empty output table: {path.name}")
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def number(value) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def average(rows: list[dict], field: str):
    values = [row[field] for row in rows if row[field] is not None]
    return float(np.mean(values)) if values else None


def git_value(repository: Path, *arguments):
    try:
        return subprocess.check_output(["git", "--work-tree", str(repository), "-C", str(repository), *arguments],
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def check_recomputed_metrics(breakdown: dict, historical: dict) -> None:
    for row in breakdown["detectors"]:
        condition = f'{row["attack_type"]}:{row["severity"]}'
        saved = historical["authenticated"]["anomaly"][row["detector"]].get(condition)
        if not row["accepted_count"]:
            if saved is not None:
                raise ValueError("historical detector summary includes an empty condition")
            continue
        clean = row["attack_type"] == "clean"
        observed = {"sample_count": row["accepted_count"],
                    "true_positives": 0 if clean else row["flagged_count"],
                    "false_positives": row["flagged_count"] if clean else 0,
                    "true_negatives": row["accepted_count"] - row["flagged_count"] if clean else 0,
                    "false_negatives": 0 if clean else row["accepted_count"] - row["flagged_count"]}
        if saved is None or any(saved[key] != value for key, value in observed.items()):
            raise ValueError("recomputed detector counts differ from historical results")
    for key, detail in breakdown["motion_detail"].items():
        name, attack, severity = key.split(":")
        measured = detail["changed"]
        saved = historical["authenticated"]["motion"][name].get(f"{attack}:{severity}")
        if not measured["sample_count"]:
            if saved is not None:
                raise ValueError("historical motion summary includes an empty condition")
        elif (saved is None or measured["confusion_matrix"] != saved["confusion_matrix"]
              or abs(measured["macro_f1"] - saved["macro_f1"]) > 1e-12
              or abs(measured["accuracy"] - saved["accuracy"]) > 1e-12):
            raise ValueError("recomputed motion metrics differ from historical results")


def make_report(data: dict, breakdown: dict) -> str:
    outcomes = data["outcomes"]
    construction = breakdown["construction"]
    planned = sum(row["planned"] for row in construction)
    valid = sum(row["quality_valid"] for row in construction)
    blocked = sum(row["pre_tag_blocked"] for row in construction)
    lines = ["# Week 5 Tier-2 accounting and held-out breakdown", "",
             "This is a read-only reporting addendum to the completed historical run. No attack, model, threshold, authentication policy or historical artifact was changed.", "",
             "## Complete case accounting", "",
             f"All splits: {planned:,} planned = {valid:,} quality-valid + {blocked:,} pre-tag blocked cases. Held-out test: "
             f'{data["reconciliation"]["accepted_test_cases"]:,} accepted of '
             f'{sum(row["planned"] for row in construction if row["split"] == "test"):,} planned cases.', "",
             "`construction_failure` means interpolation did not produce a processed window; `quality_failure` means the constructed window failed final canonical/quality validation. Neither means verifier rejection or anomaly detection. A quality-valid construction row's historical `authentication: not_attempted` value records its construction-stage state, not the later delivery result.", "",
             "| Failure reason | All splits | Held-out test | Boundary |",
             "|---|---:|---:|---|"]
    reasons = sorted({row["reason"] for row in outcomes if row["status"] != "quality_valid"})
    for reason in reasons:
        affected = [row for row in outcomes if row["status"] != "quality_valid" and row["reason"] == reason]
        lines.append(f'| `{reason}` | {len(affected):,} | {sum(row["split"] == "test" for row in affected):,} | Before tagging/model input |')
    lines.extend(["", "The unchanged resampling policy rejects source gaps above 50 ms and non-increasing source timestamps. With the legacy 16,666,667 ns grid, a three-interval gap is 50,000,001 ns and fails that rule. These are recorded data-quality/construction blocks; they were not retried until passing. Final quality failures are counted separately in the accompanying tables.", "",
                  "## Held-out attack and severity breakdown", "",
                  "Counts below are unique cases, not summed over model seeds. Recall is conditional on quality-valid, accepted cases. A failed construction is not an anomaly-model true positive. N/A means there was no eligible case.", "",
                  "| Attack | Severity | Planned | Valid/accepted | Pre-tag blocked | LR recall/FPR mean | RF recall/FPR mean |",
                  "|---|---|---:|---:|---:|---:|---:|"])
    for stage in construction:
        if stage["split"] != "test":
            continue
        detector_rows = [row for row in breakdown["detectors"] if row["attack_type"] == stage["attack_type"] and row["severity"] == stage["severity"]]
        values = [average([row for row in detector_rows if f"anomaly_{kind}_seed" in row["detector"]], "flag_rate")
                  for kind in ("logistic_regression", "random_forest")]
        lines.append(f'| {stage["attack_type"]} | {stage["severity"]} | {stage["planned"]} | {stage["quality_valid"]} | {stage["pre_tag_blocked"]} | {number(values[0])} | {number(values[1])} |')
    lines.extend(["", "The clean row reports false-positive rate, not attack recall. `detector-breakdown.csv` supplies each seed's detected/missed counts, confidence bounds, target verdict, and the same clean-control FPR (repeated for context, not additional controls). `construction-breakdown.csv` and `failure-reasons.csv` retain all three splits and every blocked case's stage/reason.", "",
                  "## Paired motion-classification degradation", "",
                  "`motion-breakdown.csv` compares each condition with clean predictions for exactly the same eligible source windows. This matters for dropout conditions with only a subset passing quality checks. Positive loss means worse classification; negative loss means improvement. The five-class macro-F1 always uses the fixed label set, including classes with zero support. `motion-detail.json` retains per-class precision/recall/F1/support and full confusion matrices.", "",
                  "| Motion family | Clean macro-F1 mean | All quality-valid macro-F1 mean |",
                  "|---|---:|---:|"])
    motion = data["historical_results"]["authenticated"]["motion"]
    for family in ("logistic_regression", "random_forest", "snn"):
        entries = [value for name, value in motion.items() if f"motion_{family}_seed" in name]
        lines.append(f'| {family} | {np.mean([value["clean:clean"]["macro_f1"] for value in entries]):.4f} | {np.mean([value["all_quality_valid"]["macro_f1"] for value in entries]):.4f} |')
    lines.extend(["", "## Calibration and frozen decisions", "",
                  "Training uses Session 1 only, with equal total source weights and equal clean/transformed mass per source. The LR scaler is fitted on weighted training only. Session 2 chooses the maximum source-weighted F1 threshold subject to clean FPR <= 5%; ties use the higher threshold and scores equal to it are flagged. Session 3 is used only after freezing these choices. This addendum loads the saved thresholds; it does not select new ones.", "",
                  "| Detector | Frozen threshold | Validation clean FP / n | Test clean FP / n | Test FPR | Test <=5% |",
                  "|---|---:|---:|---:|---:|---|"])
    for row in breakdown["calibration"]:
        lines.append(f'| {row["detector"]} | {row["threshold"]:.6f} | {row["validation_clean_false_positives"]}/{row["validation_clean_count"]} | {row["test_clean_false_positives"]}/{row["test_clean_count"]} | {row["test_clean_fpr"]:.4f} | {row["test_fpr_target_met"]} |')
    anomaly = data["historical_results"]["authenticated"]["anomaly"]
    for family in ("logistic_regression", "random_forest"):
        entries = [value for name, value in anomaly.items() if f"anomaly_{family}_seed" in name]
        lines.extend(["", f'{family}: mean F1 {np.mean([value["all_quality_valid"]["f1"] for value in entries]):.4f}; '
                      f'mean clean test FPR {np.mean([value["clean:clean"]["clean_false_positive_rate"] for value in entries]):.4f}; '
                      f'mean medium/high recall {np.mean([value["medium_high_quality_valid"]["recall"] for value in entries]):.4f}.'])
    lines.extend(["", "Neither detector reaches the predeclared 90% medium/high recall target. Logistic regression also exceeds the 5% clean test FPR target. The random forest is promising but does not meet the full criterion. Test results do not justify lowering a threshold or changing an attack's severity.", "",
                  "## Uncertainty, variation and cue controls", "",
                  "Per-condition detector recall and clean FPR use two-sided 95% Clopper-Pearson binomial intervals, separately for each fixed model. There is one case per source in each condition. These intervals assume exchangeable independent source trials; shared simulated device/session profiles limit that assumption. They are conditional descriptive intervals, not evidence of cross-device, cross-person or real-world generalization. All-pass/zero-pass rates retain finite uncertainty; zero eligible cases have no interval.", "",
                  f'Paired accuracy-loss intervals use {breakdown["bootstrap_repetitions"]} source-paired bootstrap resamples with reporting seed {breakdown["bootstrap_seed"]} (PCG64). The clean and transformed predictions stay paired; the same resampling indices are used across models for a condition. This is conditional on the subset that passed construction. Very small cohorts can produce degenerate percentile intervals; consult counts and do not interpret them as population certainty.', "",
                  "The fixed clean dataset, attack-generation seed 5007, motion seeds 7/17/27, detector seeds 6007/6017/6027, and uncertainty seed have separate roles. Changing a model seed does not regenerate motion. Seed means are repeated fits on the same cases, not independent datasets or three times as many test trials. Logistic regression uses deterministic lbfgs; its configured random_state does not create independent fitting variation. Zero seed SD describes identical outcomes, not a reliability guarantee.", "",
                  "Identifiers, labels, splits, severity, attack magnitudes, raw jitter/drop indices, tracking flags and construction outcomes are not detector inputs. Clean and attacked windows undergo the same canonical binary32 conversion and relative-pose feature path. Jitter/drop is resampled onto the original grid, so the detector cannot see discarded source timing directly. However exact frozen-pose repeats can be an artificial cue, and transformation labels do not establish malicious intent. These controls reduce obvious leakage but do not prove artifact-free detection on physical Quest data.", "",
                  "## Authentication evidence and limitations", "",
                  f'The saved delivery evidence reconciles {data["reconciliation"]["accepted_test_cases"]:,} distinct accepted events across {data["reconciliation"]["fresh_sessions"]} synthetic sessions, each with 9 motion and 6 detector calls. Paired inputs match; motion predictions and anomaly flags match; maximum score difference is {data["reconciliation"]["maximum_anomaly_score_difference"]:.17g}. The verifier sequence was committed before model calls. This is at-most-once event release, not guaranteed callback completion.', "",
                  "Quality-valid pre-tag anomalies authenticate because the legitimate sender tags them. The anomaly decision stays downstream; it does not rewrite authentication or roll back state. This historical run used known-correct synthetic credential material and predates Will's new pre-HKDF gate. Reading it does not validate the updated gate, noisy reconstruction availability, or fresh end-to-end v2 timing. Detector-inclusive latency, durable audit I/O, approved human recordings and Quest deployment remain outside this addendum.", "",
                  "## Provenance and generated files", "",
                  f'Historical evaluation source commit: `{data["manifest"]["source_commit"]}`. Dataset SHA-256: `{data["manifest"]["input_sha256"]}`.', "",
                  "The new manifest lists exactly the historical inputs checked, their byte hashes, this reporting code's hashes, reporting settings and environment. Unused joblib files are neither loaded nor required. Historical source hashes describe the old run and are not replaced by today's updated authentication code. The original run and manifest are unchanged.", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=ROOT / "results/week-5/keegan/stream-evaluation")
    parser.add_argument("--output", type=Path, default=ROOT / "results/week-5/keegan/tier2-breakdown")
    parser.add_argument("--repository", type=Path, default=ROOT)
    parser.add_argument("--bootstrap-repetitions", type=int, default=400)
    parser.add_argument("--bootstrap-seed", type=int, default=7017)
    args = parser.parse_args()
    run, output = args.run.resolve(), args.output.resolve()
    if output == run or run in output.parents or output in run.parents:
        raise ValueError("addendum must be separate from the historical run")
    if output.exists():
        raise FileExistsError("output exists; preserve it and choose a new --output directory")
    data = reporting.load_saved_run(run)
    reserved_seeds = data["config"]["motion_model_seeds"] + data["config"]["anomaly_model_seeds"] + [
        data["config"]["bootstrap_seed"], data["attack_config"]["attack_generation_seed"]]
    if args.bootstrap_seed in reserved_seeds:
        raise ValueError("reporting bootstrap seed must have a separate role")
    breakdown = reporting.build_breakdown(data, args.bootstrap_repetitions, args.bootstrap_seed)
    check_recomputed_metrics(breakdown, data["historical_results"])
    git_status = git_value(args.repository, "status", "--porcelain")
    # Create only after all historical checks and numerical reconciliation pass.
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output / "construction-breakdown.csv", breakdown["construction"])
    write_csv(output / "failure-reasons.csv", breakdown["failure_reasons"])
    write_csv(output / "detector-breakdown.csv", breakdown["detectors"])
    write_csv(output / "motion-breakdown.csv", breakdown["motion"])
    write_csv(output / "calibration.csv", breakdown["calibration"])
    write_json(output / "motion-detail.json", breakdown["motion_detail"])
    write_json(output / "reconciliation.json", breakdown["reconciliation"])
    (output / "tier2-breakdown.md").write_text(make_report(data, breakdown), encoding="utf-8", newline="\n")
    (output / ".gitattributes").write_text("* -text\n.gitattributes text eol=lf\n", encoding="utf-8", newline="\n")
    manifest = {
        "run_type": "tier2_saved_evidence_reporting_addendum_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "historical_run": str(run), "historical_manifest_sha256": reporting.sha256(run / "manifest.json"),
        "historical_complete_sha256": reporting.sha256(run / "COMPLETE"),
        "historical_source_commit": data["manifest"]["source_commit"],
        "input_artifacts_sha256": data["verified_input_sha256"],
        "source_commit": git_value(args.repository, "rev-parse", "HEAD"),
        "source_worktree_dirty": None if git_status is None else bool(git_status),
        "source_sha256": {"reporting.py": reporting.sha256(Path(reporting.__file__)),
                          "summarize_stream_evaluation.py": reporting.sha256(Path(__file__))},
        "command": subprocess.list2cmdline([sys.executable, *sys.argv]),
        "environment": {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__},
        "settings": {"binomial_ci": "Clopper-Pearson two-sided 95%, per fixed model/condition",
                     "paired_accuracy_ci": "source-paired percentile bootstrap 95%",
                     "bootstrap_seed": args.bootstrap_seed, "bootstrap_repetitions": args.bootstrap_repetitions},
        "models_executed": False, "authentication_executed": False, "historical_files_modified": False,
        "artifacts": {path.name: reporting.sha256(path) for path in sorted(output.iterdir()) if path.is_file()},
    }
    write_json(output / "manifest.json", manifest)
    write_json(output / "COMPLETE", {"manifest_sha256": reporting.sha256(output / "manifest.json"),
                                     "planned_cases": breakdown["reconciliation"]["planned_cases"],
                                     "accepted_test_cases": breakdown["reconciliation"]["accepted_test_cases"]})
    print(f'PASS: reconciled {breakdown["reconciliation"]["planned_cases"]:,} planned cases and '
          f'{breakdown["reconciliation"]["accepted_test_cases"]:,} accepted test deliveries')
    print(f"PASS: verified {len(data['verified_input_sha256'])} historical input artifact hashes; original run unchanged")
    print("Saved construction/failure, detector, paired-motion and calibration tables; no model or authentication rerun")
    print(f"Saved results to {output}")


if __name__ == "__main__":
    main()
