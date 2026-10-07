"""Separate fixed observer/GC experiment; never replaces historical timing."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import gc
from itertools import islice
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

import galois
import joblib
import numpy as np
import sklearn
import torch
from threadpoolctl import threadpool_info, threadpool_limits

from puf_snn.attacks.evaluation import prepare_model_inputs
from puf_snn.auth.sender import Sender
from puf_snn.auth.session import RegistryEntry, provision_device
from puf_snn.auth.verifier import Verifier
from puf_snn.frozen_pipeline import load_frozen_bundle, read_json, require_hash, scoped_path, sha256
from puf_snn.outlier_experiment import (
    CONTRASTS, build_jobs, checked_completion, checked_historical_inputs,
    iter_historical_traces, new_output_path, paired_comparison, read_job_traces,
    recheck_frozen_inputs, require_source_unchanged, select_experiment_sources, validate_experiment_config,
    validate_worker_traces,
)
from puf_snn.pipeline_diagnostics import (
    OuterDiagnosticCapture, TraceRetention, diagnostic_gc_policy, diagnostic_instrumentation,
    diagnostic_mode, make_diagnostic_capture, runtime_snapshot,
)
from puf_snn.pipeline_timing import one_model_bundle, run_timed_attempt, select_outliers, summarize_traces
from puf_snn.pipeline_v2 import V2InferencePipeline
from puf_snn.puf.ro_puf import generate_response
from puf_snn.snn.dataset import load_records
from scripts.benchmark_week6_v2 import collect_machine, make_materials, write_csv
from scripts.run_week6_smoke import require_clean_source, rng_for, selected_bit_errors, write_json, write_result_attributes


ROOT = Path(__file__).resolve().parents[3]
LIMITATION = (
    "Diagnostic contrasts on sixty preselected test sources, repeated in four paired noise blocks, "
    "not a replacement held-out performance/FRR/security study. Normal-GC modes are references; "
    "GC deferral is a counterfactual with separately reported cleanup. All clocks/callbacks and "
    "orchestration impose observer costs. Windows scheduling, native allocation, cache, power/core "
    "placement and historical single-event root causes remain unresolved without additional evidence. "
    "No target-passing, hardware acquisition, Quest, network or durable-audit claim.")


def timer_metadata(config):
    wall, cpu = time.get_clock_info("perf_counter"), time.get_clock_info("thread_time")
    if not wall.monotonic or wall.adjustable or not gc.isenabled():
        raise ValueError("worker must begin with monotonic timing and enabled automatic GC")
    if list(gc.get_threshold()) != config["gc_thresholds"]:
        raise ValueError("GC thresholds differ; record and stop rather than tune them")
    return {"wall": dict(implementation=wall.implementation, resolution=wall.resolution,
                         monotonic=wall.monotonic, adjustable=wall.adjustable),
            "thread_cpu": dict(implementation=cpu.implementation, resolution=cpu.resolution,
                               monotonic=cpu.monotonic, adjustable=cpu.adjustable),
            "resolution_is_api_reported_not_empirically_calibrated": True,
            "gc_thresholds": list(gc.get_threshold()), "gc_enabled_on_entry": True}


def begin_directory(path):
    path.mkdir(parents=True, exist_ok=False)
    (path / "INCOMPLETE").write_text("Preserve partial evidence; no overwrite, resume or retry-until-success.\n",
                                    encoding="utf-8", newline="\n")
    write_result_attributes(path / ".gitattributes")


def complete_directory(path, metadata):
    if (path / "manifest.json").exists() or (path / "COMPLETE").exists():
        raise ValueError("completion already exists; never replace it")
    manifest = dict(metadata, completed_utc=datetime.now(timezone.utc).isoformat(),
                    artifacts={p.name: sha256(p) for p in sorted(path.iterdir())
                               if p.is_file() and p.name != "INCOMPLETE"})
    write_json(path / "manifest.json", manifest)
    write_json(path / "COMPLETE", {"manifest_sha256": sha256(path / "manifest.json")})
    (path / "INCOMPLETE").unlink()


def run_condition(pipeline_factory, condition, sources, materials, read_domain, block,
                  capture, evidence, retention, cohort):
    """Same per-device/cohort stream reset for every model/mode in this block."""
    rngs = {device_id: rng_for(read_domain.format(block=block, device_index=value[0], cohort=cohort))
            for device_id, value in materials.items()}
    for index, source in enumerate(sources):
        phase = "condition_first_use" if cohort == "warmup" and index == 0 else cohort
        responses = []
        pipeline, reference, read_response = pipeline_factory(source, rngs[source["device_id"]], capture)
        def read_once():
            response = read_response()
            responses.append(response)
            return response
        def emit(trace):
            if capture.active or len(responses) != 1:
                raise RuntimeError("evidence must follow one read and stay outside root timers")
            trace.update(condition=condition["name"], phase=phase, attempt_index=index,
                         source_window_id=source["window_id"], device_id=source["device_id"],
                         source_split=source["split"], selected_bit_error_count=selected_bit_errors(reference, responses[0]),
                         mode=retention.mode.name, block=block)
            evidence.write(json.dumps(trace, sort_keys=True, allow_nan=False) + "\n")
            evidence.flush()
            retention.record(trace, capture)
        try:
            run_timed_attempt(pipeline, source, read_once,
                              f"week6-diag-{block}-{retention.mode.name}-{condition['name']}-{cohort}-{index}",
                              capture, emit)
        finally:
            if not pipeline.verifier.incomplete:
                pipeline.verifier.close_all_sessions()


def run_timing_worker(root, output, job, config, frozen, bundle, records):
    measured, warmup = select_experiment_sources(records)
    puf, auth, pairs, materials = make_materials(root, frozen, sorted({r["device_id"] for r in measured}))
    mode = diagnostic_mode(job["mode"])
    capture, retention = make_diagnostic_capture(mode), TraceRetention(mode)
    snapshots = []
    # No preparatory decoder/inference warmup or forced collection is hidden.
    with threadpool_limits(limits=config["native_threads"]), diagnostic_gc_policy(mode, capture) as policy:
        pools = threadpool_info()
        with diagnostic_instrumentation(mode, capture):
            for condition in job["condition_order"]:
                selected_bundle = one_model_bundle(bundle, condition)
                def factory(source, rng, observer):
                    _, device, reference, credential, enrollment_id, helper, service = materials[source["device_id"]]
                    sender = Sender(provision_device(source["device_id"], enrollment_id, helper),
                                    auth.session_config().limits, admission_service=service)
                    verifier = Verifier([RegistryEntry(source["device_id"], enrollment_id, credential)],
                                        auth.session_config(), admission_service=service)
                    pipeline = V2InferencePipeline(sender, verifier,
                        observer.wrap("prepare_both_model_inputs", prepare_model_inputs),
                        observer.wrap("motion_consumer_including_normalization", selected_bundle.motion_predictions),
                        observer.wrap("anomaly_consumer_including_threshold", selected_bundle.anomaly_predictions))
                    read = lambda: generate_response(device, pairs, puf.nominal_frequency, puf.read_conditions, rng=rng)
                    return pipeline, reference, read
                with (output / f"timings-{condition['name']}.jsonl").open("x", encoding="utf-8", newline="\n") as evidence:
                    for cohort, sources in (("warmup", warmup), ("measured", measured)):
                        run_condition(factory, condition, sources, materials, config["read_domain"], job["block"],
                                      capture, evidence, retention, cohort)
                        snapshots.append(dict(condition=condition["name"], cohort=cohort,
                                              runtime=runtime_snapshot(capture), retention=retention.snapshot(capture)))
                        print(f"{job['job_id']} {condition['name']} {cohort}: {len(sources)} attempts retained", flush=True)
        # Retention is measured across all six conditions, then released outside
        # timers. Deferred GC cleanup occurs when the policy context exits.
        before_release = retention.release(capture)
        capture.last_trace = None
    if not policy["policy_consistent"] or not gc.isenabled():
        raise RuntimeError("GC/callback policy drifted during the worker")
    write_json(output / "runtime-and-cleanup.json", dict(policy=policy, snapshots=snapshots,
                                                       final_retention_before_release=before_release,
                                                       native_threadpools=pools))
    # Loading full trees for analysis happens only AFTER all worker timing and
    # deferred cleanup; streamed modes never retain the full cohort mid-run.
    traces = read_job_traces(output, job)
    reconciliation = validate_worker_traces(traces, job, config)
    summary = summarize_traces(traces)
    write_json(output / "reconciliation.json", reconciliation)
    write_json(output / "summary.json", summary)
    write_csv(output / "path-latency.csv", summary["root_paths"])
    with (output / "retained-outliers.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
        for row in select_outliers(traces):
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    return {"fresh_attempt_count": reconciliation["fresh_attempt_count"], "trace_count": len(traces),
            "rejected_window_model_calls": reconciliation["rejected_window_model_calls"],
            "authentication_executed": True, "model_inference_executed": True,
            "latency_measured": True, "historical_trace_replay_executed": False}


def load_heap_prefix(directory, conditions, count):
    # The replay contains public trace dictionaries, NOT live sender/verifier
    # objects, responses, models reconstructed from traces, or new traffic.
    rows = []
    if count:
        with closing(iter_historical_traces(directory, conditions)) as stream:
            rows.extend(islice(stream, count))
    if len(rows) != count:
        raise ValueError("historical heap prefix is shorter than declared")
    return rows


def run_heap_worker(output, job, config, historical_directory):
    retained = load_heap_prefix(historical_directory, config["conditions"], job["retained_trace_count"])
    span_count = sum(len(r["spans"]) for r in retained)
    capture = OuterDiagnosticCapture()
    start_snapshot, probes = runtime_snapshot(capture), []
    for index in range(config["full_gc_probes_per_heap"]):
        collected = capture.measure("explicit_full_gc_probe", lambda: gc.collect(2))
        row = dict(capture.last_trace, probe_index=index,
                   phase="first_full_collection" if index == 0 else "repeat_full_collection",
                   collected_objects=collected, retained_trace_count=len(retained), retained_span_count=span_count)
        probes.append(row)
    write_json(output / "gc-probes.json", probes)
    write_json(output / "runtime.json", dict(before=start_snapshot, after=runtime_snapshot(capture),
                                             retained_trace_count=len(retained), retained_span_count=span_count,
                                             frozen_models_and_complete_dataset_resident=True,
                                             replay_is_metadata_not_original_application_heap=True))
    return {"fresh_attempt_count": 0, "trace_count": len(probes), "rejected_window_model_calls": 0,
            "authentication_executed": False, "model_inference_executed": False,
            "latency_measured": True, "historical_trace_replay_executed": True}


def worker(root, config_path, output, index, control_hash):
    require_hash(output / "control.json", control_hash)
    control = read_json(output / "control.json")
    config = read_json(config_path)
    validate_experiment_config(config)
    require_hash(config_path, control["configuration_sha256"])
    if control["jobs"] != build_jobs(config) or not 0 <= index < len(control["jobs"]):
        raise ValueError("worker index/control plan differs")
    require_source_unchanged(root, control["source_commit"], output)
    frozen_path = scoped_path(root, config["frozen_config"])
    require_hash(frozen_path, control["frozen_configuration_sha256"])
    for relative, digest in control["supporting_configurations"].items():
        require_hash(scoped_path(root, relative), digest)
    frozen = read_json(frozen_path)
    bundle = load_frozen_bundle(root, frozen)
    if bundle.artifact_hashes != control["frozen_input_hashes"]:
        raise ValueError("frozen worker artifacts differ from controller pins")
    records = load_records(scoped_path(root, frozen["input_path"]))
    historical_directory, _, historical_hashes = checked_historical_inputs(root, config)
    if historical_hashes != control["historical_hashes"]:
        raise ValueError("historical input inventory differs")
    job = control["jobs"][index]
    destination = output / "workers" / job["job_id"]
    begin_directory(destination)
    write_json(destination / "job.json", job)
    environment = {"python": platform.python_version(), "platform": platform.platform(),
                   "numpy": np.__version__, "scikit_learn": sklearn.__version__, "galois": galois.__version__,
                   "joblib": joblib.__version__, "torch": torch.__version__,
                   "timers": timer_metadata(config), "machine_start": collect_machine(),
                   "torch_intraop_threads": torch.get_num_threads(), "torch_interop_threads": torch.get_num_interop_threads(),
                   "self_reported_power": control["power"], "self_reported_background": control["background"],
                   "cpu_frequency_core_affinity_and_thermal_state_controlled": False}
    write_json(destination / "environment-start.json", environment)
    if job["kind"] == "timing":
        counts = run_timing_worker(root, destination, job, config, frozen, bundle, records)
    else:
        # Keep bundle and the complete loaded dataset alive through each probe.
        counts = run_heap_worker(destination, job, config, historical_directory)
    environment["machine_end"] = collect_machine()
    environment["gc_restored"] = gc.isenabled()
    environment["timers_end"] = timer_metadata(config)
    environment["power_plan_changed"] = (environment["machine_start"].get("ActivePowerPlan")
                                          != environment["machine_end"].get("ActivePowerPlan"))
    write_json(destination / "environment.json", environment)
    require_source_unchanged(root, control["source_commit"], output)
    recheck_frozen_inputs(root, frozen, bundle.artifact_hashes)
    for relative, digest in historical_hashes.items():
        require_hash(historical_directory / relative, digest)
    complete_directory(destination, dict(run_type=config["config_version"], job=job,
        source_commit=control["source_commit"], source_worktree_dirty=False,
        configuration_sha256=control["configuration_sha256"], frozen_input_hashes=bundle.artifact_hashes,
        **counts, training_executed=False, threshold_selection_executed=False,
        historical_files_modified=False, durable_audit_measured=False,
        complete_causal_attribution_established=False, performance_target_claim=False, limitation=LIMITATION))


def reconcile_workers(output, jobs, config, commit):
    manifests, tables, pairs, heaps = {}, [], [], []
    for job in jobs:
        directory = output / "workers" / job["job_id"]
        manifests[job["job_id"]] = checked_completion(directory, expected_job=job, expected_commit=commit)
        if job["kind"] == "timing":
            traces = read_job_traces(directory, job)
            reconciliation = validate_worker_traces(traces, job, config)
            if reconciliation != read_json(directory / "reconciliation.json"):
                raise ValueError("saved worker reconciliation differs from its traces")
            summary = summarize_traces(traces)
            if summary != read_json(directory / "summary.json"):
                raise ValueError("saved worker quantiles differ from its traces")
            tables.extend(dict(row, mode=job["mode"], block=job["block"]) for row in summary["root_paths"])
        else:
            probes = read_json(directory / "gc-probes.json")
            if len(probes) != config["full_gc_probes_per_heap"]:
                raise ValueError("heap probe count differs")
            for index, row in enumerate(probes):
                if (row["probe_index"] != index or row["retained_trace_count"] != job["retained_trace_count"]
                        or row["spans"][0]["exception"]):
                    raise ValueError("heap probe inventory differs")
                heaps.append(dict(retained_trace_count=row["retained_trace_count"],
                                  retained_span_count=row["retained_span_count"], phase=row["phase"], probe_index=index,
                                  wall_ms=row["elapsed_ns"] / 1e6, thread_cpu_ms=row["thread_cpu_ns"] / 1e6,
                                  collected_objects=row["collected_objects"]))
    timing_jobs = [j for j in jobs if j["kind"] == "timing"]
    for block in range(config["blocks"]):
        by_mode = {j["mode"]: j for j in timing_jobs if j["block"] == block}
        for contrast, left, right in CONTRASTS:
            left_rows = read_job_traces(output / "workers" / by_mode[left]["job_id"], by_mode[left])
            right_rows = read_job_traces(output / "workers" / by_mode[right]["job_id"], by_mode[right])
            pairs.extend(paired_comparison(left_rows, right_rows, contrast, block))
    count = sum(m["fresh_attempt_count"] for m in manifests.values())
    if count != (config["blocks"] * len(config["modes"]) * len(config["conditions"])
                 * (config["measured_attempts_per_condition"] + config["warmup_attempts_per_condition"])):
        raise ValueError("master fresh-attempt denominator differs")
    return manifests, tables, pairs, heaps


def report_text(config, tables, heaps):
    lines = ["# Separate Week 6 observer/GC diagnostic", "",
        "Four paired noise blocks, four diagnostic modes and six unchanged model conditions.",
        "Each worker/model keeps 30 validation warmups and 60 preselected test-source attempts.",
        "16 fresh timing workers retain all 8,640 natural admission attempts; four additional",
        "fresh processes probe historical trace metadata at 0/5,000/15,000/29,718 retained rows.", "",
        "## Measured recurring path (conditional on successful admission)", "",
        "| Block | Mode | Model condition | n | p50 ms | p95 ms | p99 ms | max ms |",
        "|---|---|---|---:|---:|---:|---:|---:|"]
    for row in tables:
        if row["phase"] == "measured" and row["path"] == "post_window_recurring" and row["decision"] == "accept":
            lines.append(f"| {row['block']} | {row['mode']} | {row['condition']} | {row['count']} | "
                         f"{row['p50_ms']:.4f} | {row['p95_ms']:.4f} | {row['p99_ms']:.4f} | {row['max_ms']:.4f} |")
    lines += ["", "## Interpretation and controls", "",
        "paired-deltas.csv gives RIGHT minus LEFT differences for each source/noise/path pair,",
        "separately by block, phase, condition, decision and reason. Negative values mean the right",
        "mode was faster in those observations. Delta quantiles are not differences of path percentiles.",
        "The contrasts are conditional, not a complete factorial design. Repeated synthetic sources",
        "and model conditions are paired, not independent security/reliability or accuracy samples.", "",
        "Mode order is position- and adjacent-predecessor-balanced across four blocks. Each mode/block",
        "gets a fresh Python process. Model order is rotated, not completely position-balanced;",
        "frequency, hybrid-core placement, thermal/OS drift and OS/file/backend caches remain uncontrolled.",
        "First warmup per condition is condition-first-use, not fully cold system startup. Loading and",
        "trusted enrollment are outside roots; no decoder/model warmup is hidden before the first root.", "",
        "Normal-GC modes are references. The deferred-GC mode is diagnostic only; its full cleanup",
        "is reported in each worker's runtime-and-cleanup.json, outside root times. It is not a",
        "deployable 20 ms success claim. No values, slow observations, first uses or refusals are discarded.",
        "Streaming writes EVERY raw trace before dropping it; reloading for analysis happens after",
        "timing and cleanup. Full retained mode owns growing trees across all six conditions.",
        "The shorter worker cohort is not a reproduction of the old 29,718-tree application history.", "",
        "Root-only mode has no separately timed first-post-window nested span. Compare matched roots",
        "only: fresh, recurring, after-refusal and receiver controls have the same functional boundaries.",
        "Nested stage percentiles must not be added; no no-op timing is subtracted. All clocks and",
        "GC callbacks remain observers, including root-only mode. In-memory audit is included; durable",
        "audit, physical capture/acquisition, network, progress and result I/O are excluded from roots.", "",
        "## Explicit full-GC heap probes", "",
        "| Retained old traces | Phase | Probe | Wall ms | Thread CPU ms | Collected objects |",
        "|---:|---|---:|---:|---:|---:|"]
    for row in heaps:
        lines.append(f"| {row['retained_trace_count']} | {row['phase']} | {row['probe_index']} | "
                     f"{row['wall_ms']:.4f} | {row['thread_cpu_ms']:.4f} | {row['collected_objects']} |")
    lines += ["", "Each heap dose runs in a fresh process with all frozen models and the complete dataset",
        "resident. Five explicit generation-2 collections are measured: first versus subsequent",
        "collections are separate. Metadata replay is not the original live authentication/application",
        "heap. Full GC may clear free lists as well as scan/collect cycles. These probes test a",
        "possible retained-metadata mechanism; they do not reconstruct historical pause causation.", "",
        "## Still unresolved", "",
        "This experiment does not establish Windows scheduling/I/O wait, native allocation stacks,",
        "CPU-cache/power causes or the precise root cause of every historical event. Stage location",
        "and GC overlap alone are not complete attribution. Follow-up OS tracing and evidence-qualified",
        "historical row accounting remain separate checkpoints; raw ETL must not go in public Git.", "",
        LIMITATION, ""]
    return "\n".join(lines)


def controller(root, config_path, requested_output, power, background):
    config = read_json(config_path)
    validate_experiment_config(config)
    commit = require_clean_source(root)
    output = new_output_path(root, requested_output)
    timer_metadata(config)
    historical_directory, _, historical_hashes = checked_historical_inputs(root, config)
    frozen_path = scoped_path(root, config["frozen_config"])
    frozen = read_json(frozen_path)
    print("Verifying frozen inputs and the original completed timing inventory", flush=True)
    bundle = load_frozen_bundle(root, frozen)
    frozen_hashes = bundle.artifact_hashes
    del bundle
    jobs = build_jobs(config)
    control = dict(source_commit=commit, configuration_sha256=sha256(config_path),
                   frozen_configuration_sha256=sha256(frozen_path), frozen_input_hashes=frozen_hashes,
                   historical_hashes=historical_hashes, jobs=jobs, power=power, background=background,
                   supporting_configurations={frozen[k]: sha256(scoped_path(root, frozen[k]))
                                              for k in ("puf_config", "auth_config")})
    begin_directory(output)
    write_json(output / "config.json", config)
    write_json(output / "control.json", control)
    control_hash = sha256(output / "control.json")
    for index, job in enumerate(jobs):
        require_source_unchanged(root, commit, output)
        print(f"Starting fresh worker {index + 1}/{len(jobs)}: {job['job_id']}", flush=True)
        try:
            subprocess.run([sys.executable, "-u", str(Path(__file__).resolve()), "--config", str(config_path.resolve()),
                            "--output", str(output), "--worker", str(index), "--control-hash", control_hash],
                           cwd=root, check=True)
        except BaseException:
            write_json(output / "execution-failure.json", dict(job_id=job["job_id"],
                       reason="worker_execution_failed_not_ordinary_admission_refusal"))
            raise
    manifests, tables, pairs, heaps = reconcile_workers(output, jobs, config, commit)
    write_csv(output / "path-latency.csv", tables)
    write_csv(output / "paired-deltas.csv", pairs)
    write_csv(output / "historical-heap-probes.csv", heaps)
    (output / "diagnostic-report.md").write_text(report_text(config, tables, heaps), encoding="utf-8", newline="\n")
    require_source_unchanged(root, commit, output)
    recheck_frozen_inputs(root, frozen, frozen_hashes)
    for relative, digest in historical_hashes.items():
        require_hash(historical_directory / relative, digest)
    worker_manifests = {job_id: sha256(output / "workers" / job_id / "manifest.json") for job_id in manifests}
    counts = dict(worker_count=len(jobs), timing_worker_count=16, historical_heap_worker_count=4,
                  fresh_attempt_count=sum(m["fresh_attempt_count"] for m in manifests.values()),
                  rejected_window_model_calls=0, paired_functional_signatures_match=True,
                  explicit_full_gc_probe_count=len(heaps), worker_manifest_hashes=worker_manifests)
    write_json(output / "reconciliation.json", counts)
    complete_directory(output, dict(run_type=config["config_version"], source_commit=commit,
        source_worktree_dirty=False, configuration_sha256=control["configuration_sha256"],
        frozen_input_hashes=frozen_hashes, historical_manifest_sha256=config["historical_manifest_sha256"],
        **counts, training_executed=False, threshold_selection_executed=False, authentication_executed=True,
        model_inference_executed=True, latency_measured=True, durable_audit_measured=False,
        complete_causal_attribution_established=False, performance_target_claim=False,
        historical_files_modified=False, limitation=LIMITATION))
    print("PASS: all workers, paired functional evidence, natural refusals and cleanup reconciled", flush=True)
    print(json.dumps(counts, indent=2), flush=True)
    print(f"Saved separate diagnostic results to {output}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/week6_outlier_experiment.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/week-6/keegan/observer-experiment")
    parser.add_argument("--power", choices=("ac", "battery", "unconfirmed"), default="unconfirmed")
    parser.add_argument("--background", choices=("heavy_apps_closed", "unconfirmed"), default="unconfirmed")
    parser.add_argument("--worker", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--control-hash", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker is None:
        if args.control_hash is not None:
            parser.error("control hash is internal to a planned worker")
        controller(ROOT, args.config, args.output, args.power, args.background)
    else:
        scope = (ROOT / "results/week-6/keegan").resolve()
        if not args.control_hash or args.output.resolve() == scope or not args.output.resolve().is_relative_to(scope):
            parser.error("worker requires a scoped existing controller output and hash")
        worker(ROOT, args.config, args.output.resolve(), args.worker, args.control_hash)


if __name__ == "__main__":
    main()
