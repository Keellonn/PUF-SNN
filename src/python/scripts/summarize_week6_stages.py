"""Report saved Week 6 stage accounting; no models, authentication or new timing."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/python"))

from puf_snn.stage_accounting import (
    BENCHMARK_COMMIT, CONDITIONS, INPUT_MANIFEST_SHA256, PRIMARY_CONDITIONS,
    RESULTS_COMMIT, STAGE_DEFINITIONS, read_checked_run, sha256,
)

SOURCE_FILES = (
    "src/python/puf_snn/stage_accounting.py",
    "src/python/scripts/summarize_week6_stages.py",
    "tests/test_stage_accounting.py", "docs/week6-stage-accounting.md",
)
CONTEXT_FILES = (
    "docs/week6-tier1-v2-experiment.md", "src/python/puf_snn/auth/verifier.py",
    "src/python/puf_snn/pipeline_timing.py",
)
FLAG_NAMES = ("new_latency_measurement_executed", "response_reads_executed",
              "authentication_executed", "model_loading_executed", "model_inference_executed",
              "training_executed", "threshold_selection_executed", "recording_executed",
              "etl_rescanned", "historical_files_modified")


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def write_csv(path, rows):
    if not rows:
        raise ValueError("refuse empty evidence table")
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def git_output(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def checked_output_path(root, directory, output):
    scope = (root / "results/week-6/keegan").resolve()
    directory, output = directory.resolve(), output.resolve()
    if (directory == scope or output == scope or not directory.is_relative_to(scope)
            or not output.is_relative_to(scope) or output == directory
            or output.is_relative_to(directory) or directory.is_relative_to(output)
            or output.exists()):
        raise ValueError("require scoped saved input and a new non-overlapping output; never overwrite")
    return directory, output


def report_text(result):
    summary = result["summary"]
    direct = {(row["condition"], row["phase"], row["path"], row["decision"]): row
              for row in summary["root_paths"]}
    inclusive = {(row["condition"], row["phase"], row["path"], row["decision"], row["stage"]): row
                 for row in summary["nested_stages"]}
    exclusive = {(row["condition"], row["phase"], row["path"], row["decision"], row["category"]): row
                 for row in result["exclusive_stages"]}
    lines = ["# Week 6 saved-data stage-accounting revision", "",
        f"Original benchmark: `{BENCHMARK_COMMIT}`; original results: `{RESULTS_COMMIT}`.", "",
        "This is reporting of unchanged saved evidence, not a new timing or reliability experiment. "
        "All original hashes, admission/control counts and direct/inclusive quantiles were checked. "
        "No models, response reads, authentication, fitting, threshold selection, ETL scan or recording ran.", "",
        "## Current integrated conclusion", "",
        "The evaluated baseline software pipeline enforced the tested admission and inference-release "
        "policies, but none of its complete motion-plus-anomaly post-window configurations met the "
        "provisional 20 ms p95 target. Reconstruction alternatives are a separate experiment; "
        "improved reliability is not demonstrated by these single-read integrated timings.", "",
        "## Directly measured totals", "",
        "Primary SNN seed 7 is the first SNN checkpoint in the original predeclared condition list, "
        "not selected for favorable latency. All three seeds and the forest-motion comparison remain "
        "in the machine-readable evidence and comparison table below.", "",
        "| Condition | Accepted n | Fresh first-window p50 / p95 / p99 / max ms | Recurring p50 / p95 / p99 / max ms | Recurring p95 <=20 ms |",
        "|---|---:|---|---|---|"]
    for name in (*PRIMARY_CONDITIONS, *(name for name in CONDITIONS if name not in PRIMARY_CONDITIONS)):
        fresh = direct[(name, "measured", "fresh_to_first_window", "accept")]
        recurring = direct[(name, "measured", "post_window_recurring", "accept")]
        show = lambda row: " / ".join(f"{row[key]:.4f}" for key in ("p50_ms", "p95_ms", "p99_ms", "max_ms"))
        lines.append(f"| {name} | {fresh['count']} | {show(fresh)} | {show(recurring)} | {'yes' if recurring['p95_ms'] <= 20 else 'no'} |")
    lines.extend(["", "These are directly measured totals. Do not add stage medians or percentiles. "
        "Fresh timing includes modeled response generation, one reconstruction attempt, verification/admission, "
        "session establishment and the first full window. Recurring timing does not repeat session setup.", "",
        "## Primary configurations: nested measured boundaries", "",
        "Values are p50 / p95 milliseconds. Inclusive rows overlap their children and are NOT additive. "
        "All accepted measured rows have the same 599 successful attempts per condition.", ""])
    requested = (
        ("Reconstruction", "fresh_to_first_window", "reconstruction"),
        ("Independent credential verification (recorded calls)", "fresh_to_first_window", "independent_credential_verification"),
        ("Whole admission/session setup (inclusive)", "fresh_to_first_window", "admission_total"),
        ("First complete post-window processing (inclusive)", "fresh_to_first_window", "first_post_window_total"),
        ("Binary32 adapter", "post_window_recurring", "binary32_adapter"),
        ("Sender sealing including serialization/quality/HMAC/audit (inclusive)", "post_window_recurring", "sender_seal_total"),
        ("Receiver parsing", "post_window_recurring", "envelope_and_binary_parser"),
        ("Receiver HMAC calculation only", "post_window_recurring", "window_hmac_verification_calculation"),
        ("Receiver quality check", "post_window_recurring", "verifier_quality_check"),
        ("Complete receiver authentication (inclusive)", "post_window_recurring", "verifier_authentication_total"),
        ("Shared preprocessing", "post_window_recurring", "prepare_both_model_inputs"),
        ("Motion consumer including normalization/decoding", "post_window_recurring", "motion_consumer_including_normalization"),
        ("Anomaly consumer including threshold", "post_window_recurring", "anomaly_consumer_including_threshold"),
    )
    for name in PRIMARY_CONDITIONS:
        lines.extend([f"### {name}", "", "| Measured boundary | p50 / p95 ms |", "|---|---|"])
        for label, path, stage in requested:
            row = inclusive[(name, "measured", path, "accept", stage)]
            lines.append(f"| {label} | {row['p50_ms']:.4f} / {row['p95_ms']:.4f} |")
        lines.append("")
    lines.extend(["## Disjoint per-observation accounting", "",
        "For each serial span, exclusive duration = its duration minus its direct child durations. "
        "Children must be contained, non-overlapping siblings. Exclusive categories sum exactly to "
        "the direct root for each observation. Category percentiles do not sum to the total percentile. "
        "Unisolated remainders include wrapper/observer overhead and are not pure application timings.", "",
        "stage-accounting.csv includes every condition/phase/path/decision/reason/category, presence counts "
        "and p50/p95/p99/max. per-observation-accounting.csv retains the integer-nanosecond partition for "
        "every root. A zero for an absent stage means it was outside that path, not a measured zero-cost operation.", "",
        "| Primary recurring condition | Measured in-memory audit p50 / p95 ms | Unisolated receiver binding/sequence/state remainder p50 / p95 ms |",
        "|---|---|---|"])
    for name in PRIMARY_CONDITIONS:
        audit = exclusive[(name, "measured", "post_window_recurring", "accept", "in_memory_audit_measured")]
        remainder = exclusive[(name, "measured", "post_window_recurring", "accept", "receiver_binding_sequence_state_unisolated")]
        lines.append(f"| {name} | {audit['p50_ms']:.4f} / {audit['p95_ms']:.4f} | {remainder['p50_ms']:.4f} / {remainder['p95_ms']:.4f} |")
    lines.extend(["", "Session establishment/key confirmation can likewise be located in the recorded handshake "
        "spans and exclusive session remainder. Credential-verification/admission/audit children are removed "
        "from that remainder, but HKDF and confirmation computation are not separately isolated. The recorded "
        "native HKDF durations lack span boundaries and are not injected into the partition.", "",
        "## Admission configuration, denominators and pairing", "",
        "The 599/600 admissions per measured condition use six fixed simulated PUF profiles, seed 6767, "
        "128 adjacent-paired oscillators, 63 selected bits, BCH(63,36,t=5), a 32-bit pilot credential and "
        "one response read/one decode. Majority-3 was not integrated in this run; no retry-until-success "
        "or enrolled-credential substitution was used. The same one reconstruction refusal recurs across "
        "paired conditions and is not six independent failure observations.", "",
        "Fresh quantiles are reported separately for accepted and refused outcomes in direct-path-latency.csv. "
        "The accepted table excludes admission failures by conditioning, not by deleting them: all 600 "
        "measured attempts per condition remain in admission-accounting.csv and reconciliation.json. "
        "First-use and 19 other warmups remain separate; first use is not a fully cold process.", "",
        "All model conditions use the same predeclared source/noise streams and timing-wrapper protocol, "
        "but run in fixed order: thermal/background/CPU drift is not isolated. Receiver-only bad-tag/replay "
        "controls exclude sender sealing and return before accepted release/inference. They are not identical "
        "execution paths to accepted full-window processing. GC-deferral and Windows-traced experiments "
        "are separate diagnostic cohorts, not interchangeable measurements in this table.", "",
        "## What the 5.17 ms figure means", "",
        "Will's docs/week6-tier1-v2-experiment.md reports native verifier p50 = 5.1700 ms for 1,200 legitimate "
        "controls, versus receiver-to-return p50 = 19.4579 ms. This addendum records that DOCUMENTED "
        "cross-experiment context; it does not independently recompute Will's raw Tier-1 measurements. "
        "The verifier's native timer starts before mutex acquisition and ends after parsing, binding, "
        "HMAC/quality/order checks and audit/state commit on the accepted path, excluding accepted release "
        "and model inference. The saved external authentication wrapper has a different boundary/observer cost.", "",
        "Historical bad-tag p95 = 0.981 ms is an earlier early-rejection benchmark, not the accepted verifier "
        "median and not a matched estimate of current complete-path cost. The original current-run bad-tag "
        "receiver distributions are retained below; their direct totals still exclude sender sealing.", "",
        "| Condition | Current measured bad-tag receiver n | p50 / p95 / p99 / max ms |",
        "|---|---:|---|"])
    for name in PRIMARY_CONDITIONS:
        row = direct[(name, "measured", "bad_tag_receiver", "reject")]
        lines.append(f"| {name} | {row['count']} | " + " / ".join(f"{row[key]:.4f}" for key in ("p50_ms", "p95_ms", "p99_ms", "max_ms")) + " |")
    lines.extend(["", "## Coverage gaps and next bounded experiment", "",
        "1. Sequence checking, locking and state publication are not individually timed. Keep the receiver "
        "remainder labeled unisolated; add narrow consistent instrumentation only if separate values are required.",
        "2. Measured audit calls are not the whole audit-related system cost and do not include durable persistence.",
        "3. Shared preprocessing and consumer-specific normalization have different boundaries; preserve them.",
        "4. Review typical measured stages and choose one bottleneck; this report performs no optimization or "
        "new timing. Any optimized comparison must retain frozen models, thresholds, protocol checks, failures "
        "and full totals, and include cleanup time, sustained throughput and memory/resource behavior.", "",
        "## Scope and limitations", "",
        "The two-second motion acquisition window remains visible but is NOT timed here. Processing p95 is "
        "not total event-to-decision latency. Physical sensor/PUF acquisition, network transmission, durable "
        "audit storage, loading/enrollment and evidence/progress I/O remain excluded. All saved measurements "
        "include observer effects, enabled automatic GC, fixed condition order and uncontrolled CPU frequency/core "
        "placement. GC overlap is not sole-cause proof. No real Quest, cross-device/person, production-security, "
        "hard-real-time or optimized-latency claim follows. Historical partial benchmarks remain historical.", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "results/week-6/keegan/fresh-v2-timing")
    parser.add_argument("--output", type=Path, default=ROOT / "results/week-6/keegan/stage-accounting")
    args = parser.parse_args()
    if git_output(ROOT, "status", "--porcelain"):
        raise ValueError("commit the reporting source first; require a clean worktree")
    source_commit = git_output(ROOT, "rev-parse", "HEAD")
    directory, output = checked_output_path(ROOT, args.input, args.output)
    source_hashes = {name: sha256(ROOT / name) for name in SOURCE_FILES}
    context_hashes = {name: sha256(ROOT / name) for name in CONTEXT_FILES}
    context = (ROOT / CONTEXT_FILES[0]).read_text(encoding="utf-8")
    if "5.1700" not in context or "19.4579" not in context:
        raise ValueError("Tier-1 documentation changed; review cross-experiment context before reporting")
    print("Checking original artifact hashes, saved roots, span partitions and admission/control outcomes", flush=True)
    result = read_checked_run(directory)
    if git_output(ROOT, "rev-parse", "HEAD") != source_commit:
        raise ValueError("source HEAD changed during analysis")
    output.mkdir(parents=True)
    (output / "INCOMPLETE").write_text("Preserve partial reporting output; do not overwrite.\n", encoding="utf-8", newline="\n")
    (output / ".gitattributes").write_text("* text eol=lf\n", encoding="utf-8", newline="\n")
    write_json(output / "checked-input-hashes.json", result["checked_input_hashes"])
    write_json(output / "reconciliation.json", result["reconciliation"])
    write_json(output / "stage-definitions.json", STAGE_DEFINITIONS)
    write_csv(output / "stage-accounting.csv", result["exclusive_stages"])
    write_csv(output / "inclusive-stage-latency.csv", result["summary"]["nested_stages"])
    write_csv(output / "direct-path-latency.csv", result["summary"]["root_paths"])
    write_csv(output / "per-observation-accounting.csv", result["observations"])
    admissions = []
    reconciliation = result["reconciliation"]
    for name in CONDITIONS:
        for phase, planned in (("measured", 600), ("warmup", 19), ("condition_first_use", 1)):
            accepts = sum(row["count"] for row in reconciliation["accepted_by_condition_phase"]
                          if (row["condition"], row["phase"]) == (name, phase))
            refusals = sum(row["count"] for row in reconciliation["refused_by_condition_phase_reason"]
                          if (row["condition"], row["phase"]) == (name, phase))
            admissions.append(dict(condition=name, phase=phase, planned_attempts=planned,
                accepted_admissions=accepts, refused_admissions=refusals,
                accepted_quantiles_conditioned_on_admission=True, response_reads_per_attempt=1))
    write_csv(output / "admission-accounting.csv", admissions)
    (output / "stage-accounting.md").write_text(report_text(result), encoding="utf-8", newline="\n")
    # Do not mix evidence/source revisions or alter historical bytes while reporting.
    for name, expected in result["checked_input_hashes"].items():
        if sha256(directory / name) != expected:
            raise ValueError("historical input changed during analysis; preserve partial report")
    for name, expected in {**source_hashes, **context_hashes}.items():
        if sha256(ROOT / name) != expected:
            raise ValueError("reporting source/context changed during analysis")
    if git_output(ROOT, "rev-parse", "HEAD") != source_commit:
        raise ValueError("source HEAD changed while reporting")
    subprocess.check_call(["git", "-C", str(ROOT), "diff", "--exit-code"])
    subprocess.check_call(["git", "-C", str(ROOT), "diff", "--cached", "--exit-code"])
    manifest = dict(run_type="week6-saved-stage-accounting-v1", source_commit=source_commit,
        source_worktree_dirty=False, completed_utc=datetime.now(timezone.utc).isoformat(), command=sys.argv,
        benchmark_source_commit=BENCHMARK_COMMIT, historical_results_commit=RESULTS_COMMIT,
        input_directory=directory.relative_to(ROOT).as_posix(), input_manifest_sha256=INPUT_MANIFEST_SHA256,
        trace_count=len(result["observations"]), fresh_attempt_count=reconciliation["fresh_attempt_count"],
        partition_reconciled_for_every_observation=True, original_quantiles_reconciled=True,
        sequence_checks_individually_isolated=False, complete_causal_attribution_established=False,
        primary_conditions=list(PRIMARY_CONDITIONS), source_sha256=source_hashes,
        context_sha256=context_hashes, **{name: False for name in FLAG_NAMES},
        artifacts={path.name: sha256(path) for path in sorted(output.iterdir())
                   if path.is_file() and path.name != "INCOMPLETE"})
    write_json(output / "manifest.json", manifest)
    write_json(output / "COMPLETE", dict(manifest_sha256=sha256(output / "manifest.json"),
        trace_count=len(result["observations"]), fresh_attempt_count=reconciliation["fresh_attempt_count"],
        partition_reconciled_for_every_observation=True))
    (output / "INCOMPLETE").unlink()
    print(f"PASS: {len(result['observations']):,} original roots and every exclusive partition reconcile", flush=True)
    print("No new timing, model loading/inference, authentication, training, recording or threshold selection", flush=True)
    print(f"Saved results to {output}", flush=True)


if __name__ == "__main__":
    main()
