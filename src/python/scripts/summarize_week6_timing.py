"""Reconcile saved v2 timing evidence; never run inference or a new benchmark."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/python"))

from puf_snn.pipeline_timing import (
    quantile, reconcile_timing, select_outliers, summarize_traces, validate_timing_config,
)

INPUT_MANIFEST_SHA256 = "10135c6e3849015c6afcfb96c91d9bc25bdeabdbdc1da2531b1ec65501403b50"
INPUT_RESULTS_COMMIT = "a4a9e2548fd30ee2383923dbd0de6cd5c45c587f"
GROUP_FIELDS = ("condition", "phase", "path", "decision", "reason")


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def scoped_path(root, relative):
    raw, root = Path(relative), root.resolve()
    path = (root / raw).resolve()
    if raw.is_absolute() or ".." in raw.parts or path == root or not path.is_relative_to(root):
        raise ValueError("file paths must stay inside their configured root")
    return path


def require_hash(path, expected):
    if not path.is_file() or sha256(path) != expected:
        raise ValueError(f"missing or hash-mismatched evidence: {path.name}; preserve the source run")


def union_overlap_ns(events, start, end):
    """Clip GC intervals to a requested span and count their union, not their sum."""
    if type(start) is not int or type(end) is not int or end < start:
        raise ValueError("invalid requested interval")
    intervals = []
    for event in events:
        low, high = event["start_ns"], event["end_ns"]
        if type(low) is not int or type(high) is not int or high < low:
            raise ValueError("invalid GC interval")
        low, high = max(start, low), min(end, high)
        if high > low:
            intervals.append((low, high))
    total, active_end = 0, start
    for low, high in sorted(intervals):
        total += max(0, high - max(low, active_end))
        active_end = max(active_end, high)
    return total


def trace_key(trace):
    return tuple(trace[name] for name in ("condition", "phase", "attempt_index", "path"))


def validate_span_tree(trace):
    spans = trace["spans"]
    if (not spans or spans[0]["parent_id"] is not None or spans[0]["stage"] != trace["path"]
            or spans[0]["exception"]):
        raise ValueError("invalid outer timing span")
    if spans[0]["wall_ns"] != trace["elapsed_ns"] or spans[0]["thread_cpu_ns"] != trace["thread_cpu_ns"]:
        raise ValueError("outer timing values disagree")
    seen = {}
    for span in spans:
        for field in ("id", "start_ns", "wall_ns", "thread_cpu_ns"):
            if type(span[field]) is not int or span[field] < 0:
                raise ValueError("span times and identifiers must be nonnegative integers")
        if span["id"] in seen:
            raise ValueError("duplicate span in completed timing evidence")
        parent = span["parent_id"]
        if parent is not None:
            if parent not in seen:
                raise ValueError("span parent must exist before its child")
            owner = seen[parent]
            if (span["start_ns"] < owner["start_ns"] or
                    span["start_ns"] + span["wall_ns"] > owner["start_ns"] + owner["wall_ns"]):
                raise ValueError("child span extends outside its parent")
        elif seen:
            raise ValueError("a timing trace must have only one root")
        seen[span["id"]] = span


def observation_row(trace, cutoff_ns, absolute_ms):
    validate_span_tree(trace)
    root = trace["spans"][0]
    wall = trace["elapsed_ns"]
    start = root["start_ns"]
    overlap = union_overlap_ns(trace["gc_events"], start, start + wall)
    gen2 = union_overlap_ns([e for e in trace["gc_events"] if e["generation"] == 2], start, start + wall)
    largest = max(trace["spans"][1:], key=lambda s: s["wall_ns"], default=None)
    stage_gc = union_overlap_ns(trace["gc_events"], largest["start_ns"],
                               largest["start_ns"] + largest["wall_ns"]) if largest else 0
    row = {name: trace[name] for name in GROUP_FIELDS}
    row.update(attempt_index=trace["attempt_index"], source_window_id=trace["source_window_id"],
               selected_bit_error_count=trace["selected_bit_error_count"], wall_ms=wall / 1e6,
               thread_cpu_ms=trace["thread_cpu_ns"] / 1e6,
               wall_minus_thread_cpu_ms=max(0, wall - trace["thread_cpu_ns"]) / 1e6,
               gc_overlap_ms=overlap / 1e6, gc_fraction=overlap / wall if wall else 0.0,
               generation2_overlap_ms=gen2 / 1e6,
               gc_spanning_trace_end=bool(trace.get("gc_spanning_trace_end")),
               nested_exception_span_count=sum(s["exception"] for s in trace["spans"][1:]),
               absolute_threshold_exceeded=wall > absolute_ms * 1e6,
               in_group_p99_tail=wall >= cutoff_ns,
               largest_nested_stage=largest["stage"] if largest else "none",
               largest_nested_ms=largest["wall_ns"] / 1e6 if largest else 0.0,
               largest_nested_gc_overlap_ms=stage_gc / 1e6,
               reconstruction_ms=sum(s["wall_ns"] for s in trace["spans"] if s["stage"] == "reconstruction") / 1e6,
               attribution="observed overlap/location; complete causal attribution unresolved")
    return row


def analyze_traces(traces, absolute_ms=20):
    if not traces:
        raise ValueError("saved timing observations must not be empty")
    groups = defaultdict(list)
    keys = set()
    for trace in traces:
        key = trace_key(trace)
        if key in keys:
            raise ValueError("duplicate timing observation")
        keys.add(key)
        groups[tuple(trace[name] for name in GROUP_FIELDS)].append(trace)
    details, summaries, maxima = [], [], []
    zero_cpu, span_count = 0, 0
    for key, rows in sorted(groups.items()):
        cutoff = quantile([r["elapsed_ns"] for r in rows], .99)
        observations = [observation_row(row, cutoff, absolute_ms) for row in rows]
        selected = [r for r in observations if r["absolute_threshold_exceeded"] or r["in_group_p99_tail"]]
        worst = max(observations, key=lambda r: r["wall_ms"])
        maxima.append(dict(worst, group_count=len(rows)))
        details.extend(selected)
        summary = dict(zip(GROUP_FIELDS, key))
        summary.update(trace_count=len(rows), retained_outlier_count=len(selected),
                       absolute_threshold_exceeded_count=sum(r["absolute_threshold_exceeded"] for r in observations),
                       p99_tail_count=sum(r["in_group_p99_tail"] for r in observations),
                       gc_overlap_outlier_count=sum(r["gc_overlap_ms"] > 0 for r in selected),
                       gc_at_least_half_outlier_count=sum(r["gc_fraction"] >= .5 for r in selected),
                       gen2_overlap_outlier_count=sum(r["generation2_overlap_ms"] > 0 for r in selected),
                       max_wall_ms=worst["wall_ms"], max_observation_gc_overlap_ms=worst["gc_overlap_ms"],
                       max_observation_gc_fraction=worst["gc_fraction"],
                       max_observation_largest_nested_stage=worst["largest_nested_stage"])
        summaries.append(summary)
        for trace in rows:
            span_count += len(trace["spans"])
            zero_cpu += sum(s["thread_cpu_ns"] == 0 for s in trace["spans"])
    return {"outlier_summary": summaries, "outlier_details": details, "group_maxima": maxima,
            "thread_cpu_observation": {"span_count": span_count, "zero_cpu_span_count": zero_cpu,
                                       "interpretation": "Zero recorded thread-CPU time in short spans does not establish waiting. The original environment did not record thread-CPU clock resolution; wall/CPU gaps alone do not establish scheduling or allocation causes."}}


def complete_path_rows(summary, target_ms=20):
    rows = []
    for entry in summary["root_paths"]:
        rows.append(dict(entry, timing_boundary="direct outer path",
                         target_applies=entry["phase"] == "measured" and entry["decision"] == "accept"
                         and entry["path"] in {"post_window_recurring", "post_window_after_refusals"}))
    for entry in summary["nested_stages"]:
        if entry["path"] == "fresh_to_first_window" and entry["stage"] == "first_post_window_total":
            row = {key: value for key, value in entry.items() if key != "stage"}
            rows.append(dict(row, path="first_post_window_total", timing_boundary="directly measured nested complete post-window span",
                             target_applies=entry["phase"] == "measured" and entry["decision"] == "accept"))
    for row in rows:
        row["provisional_target_ms"] = target_ms if row["target_applies"] else None
        row["meets_provisional_p95_target"] = row["p95_ms"] <= target_ms if row["target_applies"] else None
    return rows


def read_checked_inputs(directory, expected_manifest=INPUT_MANIFEST_SHA256):
    require_hash(directory / "manifest.json", expected_manifest)
    manifest = read_json(directory / "manifest.json")
    complete = read_json(directory / "COMPLETE")
    if complete["manifest_sha256"] != expected_manifest or (directory / "INCOMPLETE").exists():
        raise ValueError("source run is not a matching completed experiment")
    checked = {"manifest.json": expected_manifest, "COMPLETE": sha256(directory / "COMPLETE")}
    for relative, expected in manifest["artifacts"].items():
        require_hash(scoped_path(directory, relative), expected)
        checked[relative] = expected
    config = read_json(directory / "config.json")
    validate_timing_config(config)
    traces, saved_outliers = [], []
    for condition in config["conditions"]:
        name = condition["name"]
        for prefix, destination in (("timings", traces), ("outliers", saved_outliers)):
            with (directory / f"{prefix}-{name}.jsonl").open(encoding="utf-8") as handle:
                for line in handle:
                    row = json.loads(line)
                    evidence = row if prefix == "timings" else row["trace"]
                    if evidence["condition"] != name:
                        raise ValueError("condition file contains a different condition")
                    destination.append(row)
    reconciled = reconcile_timing(traces, config["conditions"])
    if reconciled != manifest["reconciliation"] or reconciled != read_json(directory / "reconciliation.json"):
        raise ValueError("saved admission/delivery counts do not reconcile")
    summary = summarize_traces(traces)
    if summary != read_json(directory / "summary.json"):
        raise ValueError("saved latency quantiles do not match the traces")
    if select_outliers(traces, config["outlier_absolute_ms"]) != saved_outliers:
        raise ValueError("retained outlier rows/diagnoses do not match the traces")
    if (len(traces) != complete["trace_count"] or len(saved_outliers) != complete["outlier_count"]
            or len(saved_outliers) != manifest["outlier_count"] or reconciled["fresh_attempt_count"] != complete["fresh_attempt_count"]):
        raise ValueError("completion-marker counts do not reconcile")
    return manifest, config, traces, saved_outliers, summary, checked


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def write_csv(path, rows):
    if not rows:
        raise ValueError("cannot silently write an empty result table")
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def report_text(input_manifest, reconciliation, conditions, paths, diagnostics):
    measured = [r for r in paths if r["phase"] == "measured" and r["decision"] == "accept"]
    index = {(r["condition"], r["path"]): r for r in measured}
    lines = ["# Saved Week 6 v2 timing and outlier addendum", "",
             f"Benchmark source commit: `{input_manifest['source_commit']}`. Results commit: `{INPUT_RESULTS_COMMIT}`.", "",
             "This is a read-only analysis of the completed instrumented run. It performs no new timing, response reads, authentication, model loading/inference, fitting or threshold selection. Original files remain unchanged.", "",
             "## Complete-path comparison (measured accepted attempts only)", "",
             "| Condition | n | Fresh-to-first p95 ms | First post-window p95 ms | Recurring p50 / p95 / p99 / max ms | After-refusal p95 ms | All three post-window p95 <=20 ms? |",
             "|---|---:|---:|---:|---|---:|---|"]
    for condition in conditions:
        name = condition["name"]
        fresh, first, recurring, after = [index[(name, path)] for path in (
            "fresh_to_first_window", "first_post_window_total", "post_window_recurring", "post_window_after_refusals")]
        meets = all(r["meets_provisional_p95_target"] for r in (first, recurring, after))
        values = " / ".join(f"{recurring[key]:.4f}" for key in ("p50_ms", "p95_ms", "p99_ms", "max_ms"))
        lines.append(f"| {name} | {recurring['count']} | {fresh['p95_ms']:.4f} | {first['p95_ms']:.4f} | {values} | {after['p95_ms']:.4f} | {'yes' if meets else 'no'} |")
    lines.extend(["", "The 20 ms software-prototype p95 target applies to directly measured complete post-window paths, including both consumers. It does not apply to admission totals, receiver-only controls, maxima or hard real-time deadlines. These instrumented CPU observations do not establish uninstrumented/headset latency or a causal advantage of one model; condition order, CPU frequency and core placement were uncontrolled.", "",
                  "## Accounting and denominators", "",
                  f"All {reconciliation['fresh_attempt_count']:,} fresh attempts and {reconciliation['trace_count']:,} root traces reconcile. Each condition has 20 retained validation warmups and 600 test-source attempts. First use is separate from the other 19 warmups. Admission failures stay in the fresh-attempt denominator; post-window timings are conditional on successful admission. Rejected traffic has zero model calls.", "",
                  "The same source/noise streams are paired across conditions. The repeated failure is not six independent reliability observations, and this run is not an FRR or formal Tier-1 study. Every refused admission is tabulated in reconciliation.json. Existing Tier-2 recall/FPR and historical Week 4 timing results are separate experiments.", "",
                  "## Retained slow/tail observations", "",
                  "An observation is retained if wall time is >20 ms OR at least the p99 of its condition/phase/path/decision/reason group. Counts overlap and must not be added. With tiny groups, the maximum is retained even if fast; with slow model paths, many ordinary observations exceed 20 ms. This is not an estimate of a rare-fault rate.", "",
                  "outlier-summary.csv gives every group's denominator and absolute/tail/GC counts. retained-outlier-detail.csv lists every retained observation. group-maxima.csv keeps all root-group maxima, including rejection controls and first use. complete-path-latency.csv includes all direct roots and directly timed first-post-window spans, with p50/p95/p99/max. Original nested spans and raw trees remain in fresh-v2-timing.", "",
                  "## Largest measured root observation in each condition", "",
                  "| Condition | Path | Wall ms | GC overlap ms | GC / wall | Largest nested stage |",
                  "|---|---|---:|---:|---:|---|"])
    for condition in conditions:
        rows = [r for r in diagnostics["group_maxima"] if r["condition"] == condition["name"] and r["phase"] == "measured"]
        row = max(rows, key=lambda r: r["wall_ms"])
        lines.append(f"| {condition['name']} | {row['path']} | {row['wall_ms']:.4f} | {row['gc_overlap_ms']:.4f} | {100 * row['gc_fraction']:.2f}% | {row['largest_nested_stage']} |")
    first_use = [r for r in diagnostics["group_maxima"] if r["phase"] == "condition_first_use" and r["path"] == "fresh_to_first_window"]
    worst = max(first_use, key=lambda r: r["wall_ms"])
    lines.extend(["", f"The largest retained condition-first-use fresh path is {worst['wall_ms']:.4f} ms in {worst['condition']}, with {worst['reconstruction_ms']:.4f} ms in reconstruction. This is a separate first-use observation, not part of measured p95. Backend compilation/cache effects are possible but were not separately isolated.", "",
                  "## What the GC evidence does and does not show", "",
                  "GC overlap is the union of recorded GC intervals clipped to the actual root or named stage. Duplicate/overlapping intervals are not double-counted. Generation-2 overlap is reported separately and is already contained in total GC overlap; do not add it again. Nested-stage durations overlap too and cannot be summed into end-to-end latency. Nested exception flags from a parser/quality function can be caught by the normal rejection path; they are retained and are not automatically labeled benchmark failures. An uncaught outer-span exception is not a completed observation.", "",
                  "Large measured maxima coincide with substantial GC activity. This is an observed contributor/location, not proof that GC explains all latency or that all GC originates in application code. The benchmark's collectors, retained trace trees and temporary wrappers may themselves affect allocations and heap scanning; that contribution was not isolated. No-op observer timings are not a calibrated correction and are never subtracted.", "",
                  "Wall/thread-CPU gaps do not distinguish scheduling, waiting, worker work, allocation or clock granularity. Many short spans have zero recorded thread-CPU time; the original metadata did not record its clock resolution. GC remains enabled, and timing/progress output and disk writes are outside the measured roots. Durable application audit storage, physical acquisition and network transport are still excluded.", "",
                  "## Remaining causal work (not completed by this addendum)", "",
                  "A separately declared diagnostic experiment must isolate collector/retention effects and GC pauses before attributing the historical maxima to application latency. Scheduling/power, allocation and cache causes remain unresolved without direct measurements. Any diagnostic repeats must preserve this run, keep the same models/thresholds/admission policy and retain refusals; do not remove slow values or disable GC merely to manufacture a passing p95.", "",
                  "Expanded varied Tier-1 evaluation, controlled reconstruction improvements, precise trust/key specification, durable audit performance and approved Quest logger validation remain separate/shared work. No SNN architecture or anomaly-model expansion follows from this report.", ""])
    return "\n".join(lines)


def git_output(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def require_clean_source(root):
    if git_output(root, "status", "--porcelain"):
        raise ValueError("commit the reporting source first; require a clean worktree")
    return git_output(root, "rev-parse", "HEAD")


def source_unchanged(root, commit):
    if git_output(root, "rev-parse", "HEAD") != commit:
        raise ValueError("source HEAD changed while reporting")
    subprocess.check_call(["git", "-C", str(root), "diff", "--exit-code"])
    subprocess.check_call(["git", "-C", str(root), "diff", "--cached", "--exit-code"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results/week-6/keegan/fresh-v2-timing")
    parser.add_argument("--output", type=Path, default=ROOT / "results/week-6/keegan/timing-diagnostics")
    args = parser.parse_args()
    source_commit = require_clean_source(ROOT)
    directory, output = args.input.resolve(), args.output.resolve()
    scope = (ROOT / "results/week-6/keegan").resolve()
    if (not directory.is_relative_to(scope) or directory == scope or
            not output.is_relative_to(scope) or output == scope or output.exists()):
        raise ValueError("require an existing scoped input and a new scoped output; never overwrite")
    print("Checking completed-run hashes, admission traces, quantiles and every retained outlier", flush=True)
    input_manifest, config, traces, original_outliers, summary, checked = read_checked_inputs(directory)
    diagnostics = analyze_traces(traces, config["outlier_absolute_ms"])
    if {trace_key(r) for r in diagnostics["outlier_details"]} != {trace_key(r["trace"]) for r in original_outliers}:
        raise ValueError("outlier inventory does not reconcile")
    paths = complete_path_rows(summary, config["post_window_p95_target_ms"])
    source_unchanged(ROOT, source_commit)
    output.mkdir(parents=True)
    (output / "INCOMPLETE").write_text("Preserve partial reporting output; do not overwrite.\n", encoding="utf-8", newline="\n")
    (output / ".gitattributes").write_text("* text eol=lf\n", encoding="utf-8", newline="\n")
    write_json(output / "checked-input-hashes.json", checked)
    write_json(output / "reconciliation.json", input_manifest["reconciliation"])
    write_csv(output / "complete-path-latency.csv", paths)
    write_csv(output / "outlier-summary.csv", diagnostics["outlier_summary"])
    write_csv(output / "retained-outlier-detail.csv", diagnostics["outlier_details"])
    write_csv(output / "group-maxima.csv", diagnostics["group_maxima"])
    write_json(output / "thread-cpu-observations.json", diagnostics["thread_cpu_observation"])
    (output / "timing-diagnostics.md").write_text(report_text(
        input_manifest, input_manifest["reconciliation"], config["conditions"], paths, diagnostics), encoding="utf-8", newline="\n")
    source_unchanged(ROOT, source_commit)
    # Recheck input bytes after analysis; a report cannot silently mix revisions.
    for relative, expected in checked.items():
        require_hash(directory / relative, expected)
    manifest = {"run_type": "week6-saved-timing-diagnostics-v1", "source_commit": source_commit,
                "source_worktree_dirty": False, "completed_utc": datetime.now(timezone.utc).isoformat(),
                "command": sys.argv, "input_directory": directory.relative_to(ROOT).as_posix(),
                "input_manifest_sha256": INPUT_MANIFEST_SHA256, "input_results_commit": INPUT_RESULTS_COMMIT,
                "benchmark_source_commit": input_manifest["source_commit"],
                "fresh_attempt_count": input_manifest["reconciliation"]["fresh_attempt_count"],
                "trace_count": len(traces), "retained_outlier_count": len(diagnostics["outlier_details"]),
                "group_maximum_count": len(diagnostics["group_maxima"]), "complete_path_rows": len(paths),
                "training_executed": False, "threshold_selection_executed": False,
                "model_loading_executed": False, "model_inference_executed": False,
                "authentication_executed": False, "new_latency_measurement_executed": False,
                "historical_files_modified": False, "complete_causal_attribution_established": False,
                "source_sha256": {relative: sha256(ROOT / relative) for relative in (
                    "src/python/scripts/summarize_week6_timing.py", "src/python/puf_snn/pipeline_timing.py",
                    "tests/test_pipeline_timing_reporting.py")},
                "artifacts": {p.name: sha256(p) for p in sorted(output.iterdir()) if p.is_file() and p.name != "INCOMPLETE"}}
    write_json(output / "manifest.json", manifest)
    write_json(output / "COMPLETE", {"manifest_sha256": sha256(output / "manifest.json"),
                                     "trace_count": len(traces), "retained_outlier_count": len(diagnostics["outlier_details"]),
                                     "group_maximum_count": len(diagnostics["group_maxima"])})
    (output / "INCOMPLETE").unlink()
    print(f"PASS: {len(traces):,} saved traces, {len(diagnostics['outlier_details']):,} retained outliers and {len(diagnostics['group_maxima'])} group maxima reconciled", flush=True)
    print("No benchmark, model loading/inference, authentication, training or threshold selection occurred", flush=True)
    print(f"Saved results to {output}", flush=True)


if __name__ == "__main__":
    main()
