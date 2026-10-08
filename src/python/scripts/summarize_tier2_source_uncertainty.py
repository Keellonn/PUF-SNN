"""Add source-cluster uncertainty to saved Tier-2 evidence; never run models."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/python"))

from puf_snn.tier2_source_uncertainty import (
    BOOTSTRAP_REPETITIONS, BOOTSTRAP_SEED, build_source_analysis, check_historical_points,
)

INPUT_MANIFEST_SHA256 = "8c053eadacf67c97f4d886a8116df17f185afb818d2e25439090fb7d7275f13e"
INPUT_COMPLETE_SHA256 = "7f6b319dc09b8d85a9ff47c9c8110ddc96ebf5c8fade134640dd02d0bf5bc4cb"
SOURCE_FILES = (
    "src/python/puf_snn/tier2_source_uncertainty.py",
    "src/python/scripts/summarize_tier2_source_uncertainty.py",
    "tests/test_tier2_source_uncertainty.py", "docs/week6-tier2-source-uncertainty.md",
)
CONTEXT_FILES = ("src/python/puf_snn/attacks/reporting.py",)
EXECUTION_FLAGS = (
    "new_timing_executed", "model_loading_executed", "model_inference_executed",
    "training_executed", "threshold_selection_executed", "attack_generation_executed",
    "authentication_executed", "recording_executed", "etl_rescanned", "historical_files_modified",
)


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def write_csv(path, rows):
    if not rows:
        raise ValueError("refuse an empty evidence table")
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_weights(path, weights):
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["replicate", *(f"source_{i:03d}" for i in range(weights.shape[1]))])
        for i, row in enumerate(weights):
            writer.writerow([i, *row.tolist()])


def git_output(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def checked_output_path(root, directory, output):
    directory, output = directory.resolve(), output.resolve()
    input_scope = (root / "results/week-5/keegan").resolve()
    output_scope = (root / "results/week-6/keegan").resolve()
    if (directory == input_scope or not directory.is_relative_to(input_scope)
            or output == output_scope or not output.is_relative_to(output_scope)
            or output.exists() or output == directory or output.is_relative_to(directory)
            or directory.is_relative_to(output)):
        raise ValueError("require saved Week 5 input and a new scoped Week 6 output; never overwrite")
    return directory, output


def verify_population(data, result):
    cohort = result["cohort"]
    construction = cohort["construction"]
    totals = {field: sum(row[field] for row in construction) for field in (
        "planned_count", "quality_valid", "pre_tag_blocked_count", "timestamp_gap_blocks", "timestamp_order_blocks")}
    expected = dict(planned_count=50400, quality_valid=44899, pre_tag_blocked_count=5501,
                    timestamp_gap_blocks=3493, timestamp_order_blocks=2008)
    test = {field: sum(row[field] for row in construction if row["split"] == "test") for field in expected}
    expected_test = dict(planned_count=16800, quality_valid=14956, pre_tag_blocked_count=1844,
                         timestamp_gap_blocks=1160, timestamp_order_blocks=684)
    strata = Counter(row["stratum"] for row in cohort["sources"])
    medium_high_cases = sum(int(cohort["valid"][:, j].sum()) for j, (attack, severity) in enumerate(cohort["conditions"])
                            if attack != "clean" and severity in {"medium", "high"})
    if (totals != expected or test != expected_test or len(cohort["sources"]) != 600
            or len(strata) != 30 or set(strata.values()) != {20}
            or {row["source_session"] for row in cohort["sources"]} != {"session-03"}
            or len({row["synthetic_profile"] for row in cohort["sources"]}) != 6
            or len(cohort["conditions"]) != 28 or len(cohort["detectors"]) != 6
            or len(cohort["motion_models"]) != 9 or data["config"]["snn_hidden_neurons"] != 64
            or medium_high_cases != 9095
            or data["config"]["motion_model_seeds"] != [7, 17, 27]
            or data["config"]["anomaly_model_seeds"] != [6007, 6017, 6027]
            or data["config"]["validation_clean_fpr_limit"] != .05
            or data["config"]["medium_high_detection_target"] != .9):
        raise ValueError("saved cohort differs from the pinned historical evaluation")
    return dict(all_split_totals=totals, test_split_totals=test, test_source_count=600,
                stratum_count=30, sources_per_stratum=20,
                planned_derivatives_per_source=28, medium_high_quality_valid_cases=medium_high_cases,
                fixed_detector_count=6, fixed_motion_model_count=9,
                historical_points_reconciled=True, source_derivatives_remain_in_one_split=True)


def show_interval(row, point_key):
    if row[point_key] is None:
        return "N/A"
    if row["ci_low"] is None or row["ci_high"] is None:
        return f"{100*row[point_key]:.2f}% [interval undefined]"
    text = f"{100*row[point_key]:.2f}% [{100*row['ci_low']:.2f}, {100*row['ci_high']:.2f}]"
    return text + ("*" if row.get("small_eligible_cohort") or row["degenerate_bootstrap_interval"] else "")


def report_text(result, population):
    families = {(row["family"], row["metric"]): row for row in result["family_summary"]}
    conditions = {(row["family"], row["attack_type"], row["severity"]): row
                  for row in result["family_condition_uncertainty"]}
    tiny = conditions[("logistic_regression", "dropped_samples", "high")]
    lines = ["# Week 6 revision: source-aware historical Tier-2 outcomes", "",
        "This is an uncertainty/reporting addendum to the completed Week 5 experiment. "
        "The saved counts, predictions, models and validation-selected thresholds are unchanged. "
        "No attack generation, model loading, inference, training, authentication, timing or recording ran.", "",
        "## Scope and accounting", "",
        "The historical experiment used cross-session synthetic windows from six fixed profiles: "
        "Session 1 training, Session 2 validation, Session 3 test. Its motion SNN is SNN-64, NOT "
        "the SNN-32 in the newer v2 timing study. Its saved authenticated deliveries predate the "
        "current v2 independent-credential-verification integration; do not relabel them current-v2 tests.", "",
        "All splits: **50,400 planned = 44,899 quality-valid + 5,501 pre-tag blocks**. "
        "The blocks comprise **3,493 timestamp-gap + 2,008 non-increasing-timestamp cases**. "
        "Test only: **16,800 planned = 14,956 quality-valid/accepted + 1,844 pre-tag blocks** "
        "(1,160 gap, 684 order). The test contains 600 source windows, each with one clean "
        "control and 27 planned transformations. Saved delivery evidence confirms acceptance "
        "and identical paired model inputs/predictions for every quality-valid test case.", "",
        "A pre-tag quality block is a separate outcome: it has no authentication tag, "
        "accepted delivery or model prediction. It is not an anomaly true positive, "
        "authenticated rejection or detector miss. A missed anomaly is a quality-valid, "
        "authenticated transformation which the detector did not flag. The construction "
        "record's not_attempted field is an earlier-stage status, not the final delivery decision.", "",
        "## Frozen-family summary and unmet targets", "",
        "Family values are arithmetic means of three FIXED detector fits. Shared source "
        "bootstrap weights are used for every fit; seeds are not three independent datasets. "
        "Intervals are 95% stratified source-bootstrap percentile intervals, conditional on "
        "these six profiles, one held-out session and fixed class counts.", "",
        "| Detector family | All-quality-valid F1 [95% interval] | Medium/high recall [95% interval] | Clean FPR [95% interval] | Observed targets |",
        "|---|---|---|---|---|"]
    for family in sorted({key[0] for key in families}):
        f1, recall, fpr = (families[(family, key)] for key in ("all_quality_valid_f1", "medium_high_recall", "clean_fpr"))
        show = lambda row: show_interval(row, "mean_fixed_model_point_estimate")
        targets = f"recall {'met' if recall['mean_fixed_model_point_estimate'] >= .9 else 'missed'}; FPR {'met' if fpr['mean_fixed_model_point_estimate'] <= .05 else 'missed'}"
        lines.append(f"| {family} | {show(f1)} | {show(recall)} | {show(fpr)} | {targets} |")
    lines.extend(["", "Medium/high recall uses 9,095 quality-valid transformed cases; "
        "clean FPR uses 600 clean source controls, NOT 600 new controls per attack or seed. "
        "Neither detector family reaches the predeclared 90% medium/high recall target. "
        "Logistic also exceeds the 5% clean-FPR limit. These observed criteria and thresholds "
        "have not been changed because of test performance.", "",
        "## Every attack type / severity", "",
        "This compact table gives quality accounting and fixed-family flag rates. "
        "For transformed cases the flag rate is recall among quality-valid accepted cases; "
        "for clean it is FPR. Full exact per-seed detections, misses, clean false positives, "
        "rejection counts and frozen thresholds are in detector-outcomes.csv (168 rows). "
        "All test conditions planned 600 source cases; quality-valid = authenticated accepted.", "",
        "| Type | Severity | Eligible accepted | Gap blocks | Order blocks | LR rate [95% interval] | RF rate [95% interval] |",
        "|---|---|---:|---:|---:|---|---|"])
    for row in result["cohort"]["construction"]:
        if row["split"] != "test":
            continue
        key = (row["attack_type"], row["severity"])
        lr, rf = (conditions[(family, *key)] for family in ("logistic_regression", "random_forest"))
        lines.append(f"| {key[0]} | {key[1]} | {row['quality_valid']} | {row['timestamp_gap_blocks']} | {row['timestamp_order_blocks']} | {show_interval(lr, 'mean_fixed_model_flag_rate')} | {show_interval(rf, 'mean_fixed_model_flag_rate')} |")
    lines.extend(["", "*Small cohorts (<30 eligible sources) and/or degenerate empirical intervals "
        "are flagged, not evidence of certain detection. High dropped_samples has only "
        "four eligible sources: all four were flagged by each fit. Its [100%,100%] "
        f"bootstrap interval cannot reveal unseen misses. {tiny['undefined_bootstrap_draws']} of {BOOTSTRAP_REPETITIONS:,} draws contain no "
        "eligible case and are explicitly undefined, not retried. High timestamp_jitter "
        "has zero eligible cases: recall and its interval are N/A, not 100% or zero. "
        "Defined/undefined draw counts and degeneracy flags are saved for every rate.", "",
        "## Motion degradation is a separate objective", "",
        "motion-degradation.csv has 252 rows: all 28 conditions x nine frozen motion fits. "
        "Each transformed condition is compared with clean predictions from exactly its "
        "eligible source subset. Clean-minus-transformed accuracy loss has a source-paired "
        "95% bootstrap interval. Clean/transformed macro-F1 and its loss are descriptive "
        "points, using the fixed five-class label set; this report does not claim an F1 "
        "interval. Existing full confusion matrices remain in the historical breakdown. "
        "A classification error can choose the wrong motion action; an anomaly flag "
        "indicates suspect sensor semantics, not a failed HMAC. Legitimate low-amplitude "
        "nod/still ambiguity is a separate execution-variation analysis, not automatically "
        "an anomaly-detector failure. This report neither changes that interpretation "
        "nor claims an SNN advantage over conventional baselines.", "",
        "## Source-aware uncertainty protocol", "",
        f"Fixed reporting settings: PCG64 seed {BOOTSTRAP_SEED}, {BOOTSTRAP_REPETITIONS:,} draws; "
        "2.5th/97.5th percentiles with NumPy's linear quantile method. Resample source "
        "windows with replacement within each fixed profile/session/motion-class stratum "
        "(30 strata, 20 sources each). This saved dataset has exactly one window per "
        "source trial; a dataset with multiple windows per trial must use a revised "
        "trial-level cluster protocol rather than this script.", "",
        "For a sampled source, one multiplicity applies jointly to ALL its derivatives, "
        "quality outcomes, matched clean prediction and detector/motion fits. For each "
        "draw, aggregate source contributions before dividing: e.g. medium/high recall "
        "is summed flagged eligible medium/high cases divided by summed eligible "
        "medium/high cases. Thus the pooled cases are not resampled as independent "
        "messages. Clean FPR uses the same resampled source weights. Paired accuracy "
        "loss sums clean-correct minus transformed-correct over eligible derivatives.", "",
        "source-cohort.csv gives the canonical source-column mapping; "
        "bootstrap-source-weights.csv preserves every integer multiplicity for replay. "
        "The matrix hash uses little-endian uint16 C-order bytes. Bootstrap draws are "
        "statistical resampling, not new experiments, security trials or model fits. "
        "Undefined ratios have no eligible denominator and are omitted only from that "
        "metric's percentile calculation, with counts reported; no replacement draws "
        "are generated to force eligibility.", "",
        "These intervals assume exchangeable independently generated source trials "
        "within fixed strata. They handle dependence of derivatives and paired fits, "
        "not uncertainty across new devices, people, sessions or independently generated "
        "populations. There is only one held-out session per fixed profile: no "
        "cross-session-population or hardware generalization interval is estimable here. "
        "Systematic synthetic-generator artifacts, shared profile effects and training "
        "variation are outside these conditional intervals. Prior binomial intervals "
        "remain historical supplementary conditional descriptions, not evidence that "
        "all pooled transformed messages were independent.", "",
        "## Preservation and remaining work", "",
        "The pinned manifest, completion marker, nine saved input artifacts and source "
        "code hashes are checked before and after reporting. Recomputed detector "
        "counts/rates and every motion confusion matrix/F1 reconcile with the frozen "
        "results. Original threshold calibration, generation parameters and train/test "
        "splits are unchanged. This addendum does not re-audit generator cues through "
        "new data: metadata exclusion and source/split rules remain the recorded design.", "",
        "This completes the saved Tier-2 source-aware reporting revision only. It does "
        "not complete the narrow current-v2 stage measurements/one-bottleneck optimization, "
        "majority-3/correlated-noise integration, provisioned-credential control, release "
        "manifest, paper evaluation or hardware/institutional approval requirements.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results/week-5/keegan/stream-evaluation")
    parser.add_argument("--output", type=Path, default=ROOT / "results/week-6/keegan/tier2-source-uncertainty")
    args = parser.parse_args()
    directory, output = checked_output_path(ROOT, args.input, args.output)
    source_commit = git_output(ROOT, "rev-parse", "HEAD")
    if git_output(ROOT, "status", "--porcelain"):
        raise ValueError("require a clean committed checkout before generating new evidence")
    for name in SOURCE_FILES:
        if git_output(ROOT, "ls-files", "--", name) != name:
            raise ValueError("all reporting source/doc/test files must be committed first")
    source_hashes = {name: sha256(ROOT / name) for name in (*SOURCE_FILES, *CONTEXT_FILES)}
    pinned = {"manifest.json": INPUT_MANIFEST_SHA256, "COMPLETE": INPUT_COMPLETE_SHA256}
    if (directory / "INCOMPLETE").exists() or any(sha256(directory / name) != value for name, value in pinned.items()):
        raise ValueError("historical manifest/completion pin mismatch; preserve evidence and stop")
    # Load this pure saved-file module directly. Importing attacks.__init__ would
    # unnecessarily import the attack generator and its model/auth dependencies.
    specification = importlib.util.spec_from_file_location("saved_tier2_reporting", ROOT / CONTEXT_FILES[0])
    saved_reporting = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(saved_reporting)
    print("Checking pinned historical artifacts, source/split ownership, frozen thresholds and paired predictions", flush=True)
    data = saved_reporting.load_saved_run(directory)
    result = build_source_analysis(data)
    check_historical_points(result, data["historical_results"])
    population = verify_population(data, result)
    checked = {**pinned, **data["verified_input_sha256"]}
    output.mkdir(parents=True, exist_ok=False)
    (output / "INCOMPLETE").write_text("Reporting not yet fully reconciled. Preserve this directory on failure.\n", encoding="utf-8")
    (output / ".gitattributes").write_text("* text eol=lf\n", encoding="utf-8", newline="\n")
    write_csv(output / "case-accounting.csv", result["cohort"]["construction"])
    for key in ("detector_outcomes", "motion_degradation", "detector_summary", "family_condition_uncertainty", "family_summary"):
        write_csv(output / (key.replace("_", "-") + ".csv"), result[key])
    write_csv(output / "source-cohort.csv", [dict(source_index=i, **row) for i, row in enumerate(result["cohort"]["sources"])])
    write_weights(output / "bootstrap-source-weights.csv", result["weights"])
    write_json(output / "bootstrap-settings.json", dict(
        repetitions=BOOTSTRAP_REPETITIONS, seed=BOOTSTRAP_SEED, bit_generator="PCG64",
        unit="source_window (one window per trial verified)", strata="fixed synthetic profile / source session / motion class",
        interval="95% percentile; quantile method linear", undefined_draw_policy="count, do not redraw",
        shared_weights_for_all_derivatives_and_fits=True, source_weight_sha256=result["source_weight_sha256"],
        weight_hash_encoding="uint16 little-endian C-order; CSV mapping in source-cohort.csv",
        numpy_version=np.__version__, seed_fits_are_independent_source_trials=False,
        uncertainty_is_conditional_on_fixed_profiles_session_and_class_counts=True))
    write_json(output / "frozen-validation-thresholds.json", data["thresholds"])
    write_json(output / "reconciliation.json", dict(**population, historical_delivery_reconciliation=data["reconciliation"]))
    write_json(output / "checked-input-hashes.json", checked)
    (output / "tier2-source-uncertainty.md").write_text(report_text(result, population), encoding="utf-8", newline="\n")
    if (any(sha256(directory / name) != value for name, value in checked.items())
            or any(sha256(ROOT / name) != value for name, value in source_hashes.items())
            or git_output(ROOT, "rev-parse", "HEAD") != source_commit
            or git_output(ROOT, "diff", "--name-only") or git_output(ROOT, "diff", "--cached", "--name-only")):
        raise ValueError("input/source/HEAD changed during reporting; preserve INCOMPLETE and stop")
    artifacts = {path.name: sha256(path) for path in sorted(output.iterdir()) if path.name != "INCOMPLETE"}
    flags = {name: False for name in EXECUTION_FLAGS}
    manifest = dict(experiment_name="historical-tier2-source-uncertainty-report-v1",
        generated_utc=datetime.now(timezone.utc).isoformat(), source_commit=source_commit, source_worktree_dirty=False,
        historical_source_commit=data["manifest"]["source_commit"], historical_input_manifest_sha256=INPUT_MANIFEST_SHA256,
        historical_scope="Week 5 synthetic cross-session Tier-2; SNN-64; not current-v2 attack evaluation",
        source_dataset_sha256=data["config"]["source_dataset_sha256"], source_hashes=source_hashes,
        **population, bootstrap_repetitions=BOOTSTRAP_REPETITIONS, reporting_bootstrap_seed=BOOTSTRAP_SEED,
        source_weight_sha256=result["source_weight_sha256"], python=sys.version, numpy=np.__version__,
        artifacts=artifacts, **flags)
    write_json(output / "manifest.json", manifest)
    complete = dict(manifest_sha256=sha256(output / "manifest.json"), test_source_count=600,
                    detector_condition_rows=len(result["detector_outcomes"]),
                    motion_condition_rows=len(result["motion_degradation"]), historical_points_reconciled=True)
    write_json(output / "COMPLETE", complete)
    (output / "INCOMPLETE").unlink()
    print("PASS: all 50,400 planned cases, 14,956 accepted test cases and frozen point estimates reconcile")
    print("Saved 2,000 shared source-bootstrap draws; no refitting, threshold selection, inference or authentication")
    print(json.dumps(complete, indent=2))
    print(f"Saved results to {output}")


if __name__ == "__main__":
    main()
