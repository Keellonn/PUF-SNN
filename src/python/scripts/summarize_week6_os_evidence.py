"""Hash-check a private saved accounting review and publish numeric evidence.

No ETL reader, recording, model loading, training, authentication or new timing.
Never copies raw traces, exports, absolute clocks, OS identities or I/O tokens.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/python"))
from puf_snn.windows_os_reporting import sanitize_root, sanitize_detail, key, reconcile_public

PRIVATE_MANIFEST_SHA256 = "1515d91aa9462d6d25cc18a410b0cf54ffd2e234404b8b665782e4fa9668e667"
CAPTURE_SOURCE_COMMIT = "624807b9095b7be41f7c3bbe7d18a31d50f95478"
ETL_SHA256 = "ed8fcef567d3522448f4222b4e77e2b118df062e4e8be5e83b3e3c3207c97268"
OUTPUT_RELATIVE = "results/week-6/keegan/windows-os-evidence"
PRIVATE_ARTIFACTS = frozenset(("INCOMPLETE", "accounting-review.md", "checked-input-hashes.json",
    "group-observations.csv", "io-boundaries.csv", "retained-root-detail.jsonl", "root-accounting.csv", "summary.json"))


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def ordinary(path):
    if path.is_symlink() or getattr(path.stat(), "st_file_attributes", 0) & 0x400:
        raise ValueError("input/output path is a link or junction")


def verify_inputs(directory):
    path = directory.resolve()
    if (not directory.is_absolute() or directory != path or path.is_relative_to(ROOT.resolve())
            or not re.fullmatch(r"root-accounting-[0-9a-f]{32}", path.name)
            or not re.fullmatch(r"week6-model-trace-[0-9a-f]{32}", path.parent.name)
            or path.parent.parent.name != "private-traces"):
        raise ValueError("input must be a named private accounting directory outside Git")
    for ancestor in (path, path.parent, path.parent.parent):
        ordinary(ancestor)
    manifest_path = path / "manifest.json"
    ordinary(manifest_path)
    ordinary(path / "REVIEW_COMPLETE")
    if digest(manifest_path) != PRIVATE_MANIFEST_SHA256:
        raise ValueError("private review manifest differs from the pinned completed review")
    manifest = read_json(manifest_path)
    complete = read_json(path / "REVIEW_COMPLETE")
    if (complete["manifest_sha256"] != PRIVATE_MANIFEST_SHA256 or complete["accounting_completed"] is not True
            or complete["complete_causal_attribution_established"] is not False
            or manifest["source_commit"] != CAPTURE_SOURCE_COMMIT or manifest["etl_sha256"] != ETL_SHA256
            or manifest["complete_causal_attribution_established"] is not False
            or manifest["experimental_records_modified"] is not False
            or manifest["recording_executed"] is not False or manifest["model_calls"] != 0
            or manifest["etl_rescanned"] is not False or set(manifest["artifacts"]) != PRIVATE_ARTIFACTS):
        raise ValueError("private completed-accounting scope differs")
    for name, expected in manifest["artifacts"].items():
        source = path / name
        ordinary(source)
        if not source.is_file() or digest(source) != expected:
            raise ValueError("private reviewed artifact bytes changed")
    return path, manifest


def build_public(directory):
    directory, manifest = verify_inputs(directory)
    with (directory / "root-accounting.csv").open(encoding="utf-8") as handle:
        roots = [sanitize_root(row, index) for index, row in enumerate(csv.DictReader(handle), 1)]
    by_key = {key(row): row for row in roots}
    with (directory / "retained-root-detail.jsonl").open(encoding="utf-8") as handle:
        details = [sanitize_detail(json.loads(line), by_key) for line in handle]
    saved = read_json(directory / "summary.json")
    summary, groups, large = reconcile_public(roots, details, saved["group_observations"])
    for name, value in summary.items():
        if name in saved and saved[name] != value:
            raise ValueError("saved summary does not reconcile with numeric root accounting")
    if (len(roots) != 4320 or len(details) != 2106 or len(groups) != 144 or len(large) != 8
            or summary["roots_fully_schedule_covered"] != 4320):
        raise ValueError("completed capture inventory differs from the pinned cohort")
    summary.update(capture_source_commit=CAPTURE_SOURCE_COMMIT, reference_fresh_attempts=540,
        traced_fresh_attempts=540, reference_root_count=4320, rejected_window_model_calls=0,
        actual_marker_count=27, native_qpc_frequency_hz=10000000,
        export_relative_clock_uncertainty_ns=31100, actual_saved_markers_validated=True,
        native_qpc_python_brackets_validated=True, final_header_events_lost=0, final_header_buffers_lost=0,
        process_thread_lifetimes_validated=True, cswitch_common_prefix_sample_events=24495,
        cswitch_full_native_schema_validated=False, opaque_byte13_used_for_accounting=False,
        quantile_method="linear interpolation at q*(n-1)", new_timing_executed=False,
        new_authentication_executed=False, model_loading_executed=False, recording_executed=False,
        etl_rescanned=False, experimental_records_modified=False, training_executed=False,
        threshold_selection_executed=False, durable_audit_measured=False, performance_target_claim=False,
        privacy_filter="allowlisted project labels and numeric durations/counts only; no OS IDs, raw clocks, addresses, paths, IRP tokens or free-text kernel payloads")
    io = saved["io_boundary_counts"]
    if (set(io) != {"scoped_operations", "operations_with_positive_root_overlap", "operations_without_positive_root_overlap"}
            or any(type(value) is not int or value < 0 for value in io.values())
            or io["scoped_operations"] != io["operations_with_positive_root_overlap"] + io["operations_without_positive_root_overlap"]):
        raise ValueError("scoped operation counts do not reconcile")
    summary["io_boundary_counts"] = dict(io)
    retained = {row["public_root_index"]: row for row in details}
    large_details = [dict(root=root, nested_stage_observations=retained[root["public_root_index"]]["nested_stage_observations"])
                     for root in large]
    verify_inputs(directory)  # source bytes are unchanged after reading/filtering
    return roots, details, summary, groups, large_details, manifest


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def write_text(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def write_csv(path, rows):
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value
                             for name, value in row.items()})


def markdown(summary, large):
    lines = ["# Week 6 Windows OS evidence", "",
        "Separate serial tracing diagnostic; not a replacement benchmark or a target-passing result.", "",
        "The two fresh processes each retained 540 one-read admissions and 4,320 root timings. Functional signatures matched and refused messages had zero model calls. No fitting or threshold change occurred.", "",
        "All 27 actual native markers, exact QPC/Python clock brackets, final event-loss header and main-thread lifetimes were checked. CSwitch v5 full TDH metadata remains unavailable: a 24,495-event selected-prefix cross-check is not validation of the entire schema. An incorrect 0/1 interpretation in the original review was corrected separately, preserving the extracted bytes. Opaque byte13 is not used here.", "",
        "## Accounted observations", "",
        f"- All {summary['application_root_count']:,} traced roots have full scheduling coverage and reconciled disjoint wall partitions.",
        f"- Retained {summary['retained_root_count']:,} distinct absolute/tail/maxima observations across {summary['group_count']} groups, including all eight roots above 100 ms.",
        f"- GC callback overlap occurred in {summary['roots_with_gc_overlap']:,} roots; ready-but-not-dispatched time occurred in {summary['roots_with_ready_delay']:,} roots.",
        "- One root overlaps scoped main-thread file read/write operations; none overlaps the scoped disk or hard-fault intervals. This does not rule out cached/metadata/other-thread I/O or prove blocking.", "",
        "## Every root above 100 ms", "",
        "Durations are milliseconds. GC, ready delay, I/O and nested-stage values overlap and must not be summed as independent causes.", "",
        "| Condition / phase / path | Wall | GC union | Ready delay | Largest nested stage | Stage wall |",
        "|---|---:|---:|---:|---|---:|"]
    for row in large:
        root = row["root"]
        largest = max(row["nested_stage_observations"], key=lambda item: item["wall_union_ns"])
        lines.append(f"| {root['condition']} / {root['phase']} / {root['path']} | {root['elapsed_ns']/1e6:.4f} | {root['gc_wall_union_ns']/1e6:.4f} | {(root['off_ready_at_switchout_ns']+root['off_ready_after_event_ns'])/1e6:.4f} | {largest['stage']} | {largest['wall_union_ns']/1e6:.4f} |")
    lines.extend(["", "The 3,735.7236 ms first-condition-use root spends 3,690.2300 ms in reconstruction, with 274.7025 ms GC overlap inside that stage. The remaining reconstruction duration is not automatically a cache/JIT/allocation diagnosis. Model loading and enrollment precede root timers; first condition use is not fully cold system startup.", "",
        "Four other long pauses have 286.4601–432.8645 ms GC overlap (about 90–98% of each root); the previous paired GC controls support a collector contribution, not proof of a sole cause. The 142.4030 ms forest/forest case instead has only 0.3193 ms GC but 56.1910 ms of ready-but-not-dispatched time. The two roughly 102–107 ms SNN cases have under 1 ms GC and 9.6164–12.4648 ms ready delay; the residual consumer/reconstruction work remains unisolated. All eight therefore overlapping GC does not mean GC dominates all eight.", "",
        "## Timing interpretation and limits", "",
        "The disjoint partition prioritizes same-CPU interrupt union during scheduled residency, then scheduled GC excluding those interrupts, then other scheduled residency. Off-CPU time is split by documented ready-at-switchout state, observed ReadyThread-to-dispatch intervals, not-yet-observed readiness and unresolved state. Raw unknown states/reasons remain numeric and are not assigned guessed meanings. Scheduled residency is not useful CPU execution; GetThreadTimes is coarse on this host.", "",
        "GC, scoped I/O operations, hard faults and nested stages are separately clipped interval-union overlays. Outstanding I/O does not prove a blocking dependency. ISR/DPC accounting joins the worker's current CPU, not global interrupt totals; nested interruptions are counted once. Exact native QPC conversion uses validated 10 MHz ticks, not a fitted export clock; the old export-relative uncertainty was 31.1 microseconds.", "",
        "The paired reference precedes traced in fresh processes. Reported differences are observed right-minus-left contrasts, not isolated tracing overhead: order, marker/recorder cost, cache, frequency, hybrid-core placement, thermals and background activity are confounded. Group p50/p95/p99/max are descriptive for this diagnostic and do not replace the original complete-path target results.", "",
        "Allocation stacks, cache misses, frequency/thermal transitions, dependency-specific waits and all other-thread activity were not fully instrumented. CPU sample counts do not establish these causes. New tracing cannot retroactively prove OS causes for earlier untraced roots. Complete causal attribution remains false; unknown residuals are retained, never relabeled as scheduling or removed.", "",
        "No durable audit I/O, Quest deployment, real-data generalization, new FRR/Tier-1 study or hard real-time guarantee is established.", "",
        "## Files and provenance", "",
        "`root-accounting.csv` contains all allowlisted numeric root records; `retained-root-detail.jsonl` contains nested-stage observations for every retained root; `large-root-detail.json` retains all eight >100 ms cases; `group-observations.csv` retains separate accepted/refused paths, warmup, first use and measured p50/p95/p99/max. `provenance.json` binds the private review and original capture without copying private content. The public COMPLETE marker confirms reconciled export, not complete causality.", "",
        "The original fresh-v2 run, timing addendum and [controlled GC/observer study](../observer-experiment/diagnostic-report.md) remain unchanged. Raw ETL, decoded kernel exports, absolute times, OS IDs, addresses, paths and IRP tokens remain private. Retain the private originals for a controlled evidence review; the public checkout cannot recreate the original OS capture without them.", "",
        "Readiness/state interpretation follows [Microsoft's context-switch explanation](https://learn.microsoft.com/en-us/windows/win32/procthread/context-switches) and [CSwitch prefix documentation](https://learn.microsoft.com/en-us/windows/win32/etw/cswitch). DPC/ISR/hard-fault InitialTime conversion follows Microsoft's [TraceEvent implementation](https://github.com/microsoft/perfview/blob/main/src/TraceEvent/Parsers/KernelTraceEventParser.cs), with actual available fields checked against this capture's TDH metadata.", ""])
    return "\n".join(lines)


def git(*arguments):
    result = subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-accounting", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    source = None
    if not args.check_only:
        if git("status", "--porcelain", "--untracked-files=all"):
            raise RuntimeError("Commit the reporting source/test evidence first; worktree must be clean")
        source = git("rev-parse", "HEAD")
        if not re.fullmatch(r"[0-9a-f]{40}", source):
            raise ValueError("invalid source commit")
    roots, details, summary, groups, large, private_manifest = build_public(args.private_accounting)
    if args.check_only:
        print("PASS: pinned private accounting reconciles and privacy whitelist passes; no output written.", flush=True)
    else:
        output = ROOT / OUTPUT_RELATIVE
        if output.exists():
            raise ValueError("new public result directory already exists; preserve it")
        parent = output.parent
        while parent != ROOT:
            if parent.exists():
                ordinary(parent)
            parent = parent.parent
        output.mkdir(parents=True, exist_ok=False)
        write_text(output / "INCOMPLETE", "Public export started; preserve all files on failure.\n")
        write_text(output / ".gitattributes", "* -text\n")
        write_csv(output / "root-accounting.csv", roots)
        write_csv(output / "group-observations.csv", groups)
        with (output / "retained-root-detail.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
            for row in details:
                handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
        write_json(output / "large-root-detail.json", large)
        write_json(output / "summary.json", summary)
        write_text(output / "windows-os-evidence.md", markdown(summary, large))
        provenance = dict(private_review_manifest_sha256=PRIVATE_MANIFEST_SHA256,
            original_etl_sha256=ETL_SHA256, original_etl_bytes=11848908800,
            capture_source_commit=CAPTURE_SOURCE_COMMIT,
            reviewed_private_artifact_hashes=private_manifest["artifacts"],
            private_accounting_helper_sha256=private_manifest["input_hashes"]["review_week6_root_accounting.py"],
            private_interval_module_sha256=private_manifest["input_hashes"]["kernel_accounting.py"],
            original_decoder_review_sha256=private_manifest["input_hashes"]["decoder-and-lifetime-review.json"],
            raw_content_copied=False, raw_paths_exported=False,
            absolute_clocks_exported=False, os_process_thread_ids_exported=False,
            raw_addresses_or_irp_tokens_exported=False)
        write_json(output / "provenance.json", provenance)
        source_files = ("src/python/puf_snn/windows_os_accounting.py", "src/python/puf_snn/windows_os_reporting.py",
                        "src/python/scripts/summarize_week6_os_evidence.py")
        artifact_hashes = {path.name: digest(path) for path in output.iterdir() if path.is_file() and path.name != "INCOMPLETE"}
        manifest = dict(report_version="week6-sanitized-windows-os-evidence-v1", source_commit=source,
            source_worktree_dirty=False, source_file_hashes={name: digest(ROOT/name) for name in source_files},
            capture_source_commit=CAPTURE_SOURCE_COMMIT, command="python src/python/scripts/summarize_week6_os_evidence.py --private-accounting <private-accounting-directory>",
            completed_utc=datetime.now(timezone.utc).isoformat(), artifacts=artifact_hashes,
            application_root_count=4320, retained_root_count=2106, group_count=144,
            large_root_count_above_100ms=8, complete_causal_attribution_established=False,
            tracing_overhead_isolated=False, privacy_filter_applied=True,
            recording_executed=False, etl_rescanned=False, model_calls=0, training_executed=False,
            threshold_selection_executed=False, historical_files_modified=False,
            new_timing_executed=False, durable_audit_measured=False, performance_target_claim=False)
        write_json(output / "manifest.json", manifest)
        verify_inputs(args.private_accounting)
        write_json(output / "COMPLETE", dict(manifest_sha256=digest(output/"manifest.json"),
            export_completed=True, complete_causal_attribution_established=False))
        (output / "INCOMPLETE").unlink()  # only our newly created export marker, never private evidence
        print("Saved sanitized numeric evidence to " + str(output), flush=True)
    print(json.dumps({name: summary[name] for name in (
        "application_root_count", "retained_root_count", "group_count", "large_root_count_above_100ms",
        "roots_fully_schedule_covered", "disjoint_root_partitions_reconciled",
        "complete_causal_attribution_established", "new_timing_executed", "model_loading_executed")}, indent=2), flush=True)


if __name__ == "__main__":
    main()
