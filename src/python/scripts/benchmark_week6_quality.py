"""Bounded paired exact-quality comparison; does not alter the default v2 path."""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import gc
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
    checked_completion, new_output_path, read_job_traces, recheck_frozen_inputs, require_source_unchanged,
)
from puf_snn.pipeline_timing import (
    TimingCapture, instrument_pipeline, one_model_bundle, run_timed_attempt, select_outliers, summarize_traces,
)
from puf_snn.pipeline_v2 import V2InferencePipeline
from puf_snn.puf.ro_puf import generate_response
from puf_snn.quality_benchmark import (
    PublicLedger, build_jobs, cleanup, normal_gc_conditions, paired_rows, resource_snapshot,
    select_sources, sustained_burst, validate_config, validate_rows,
)
from puf_snn.quality_dyadic import quality_validator_mode
from puf_snn.snn.dataset import load_records
from puf_snn.stage_accounting import SavedStageAnalysis
from scripts.benchmark_week6_v2 import collect_machine, make_materials, write_csv
from scripts.run_week6_outlier_experiment import begin_directory, complete_directory
from scripts.run_week6_smoke import require_clean_source, rng_for, selected_bit_errors, write_json


ROOT = Path(__file__).resolve().parents[3]
LIMITATION = (
    "Paired bounded software arithmetic comparison, not a new independent held-out accuracy/FRR/security "
    "study or production adoption. Two blocks reuse 120 test sources across modes/models and 64 further "
    "preselected same-profile windows for unpaced closed-loop session reuse. Single-read baseline "
    "BCH(63,36,t=5), 32-bit pilot credential; NOT integrated majority-3. GC remains enabled. All roots "
    "include observer costs; streamed evidence is outside root timers but inside closed-loop throughput. "
    "Physical PUF/sensor acquisition, the two-second motion acquisition window, network, durable audit, "
    "enrollment/loading and evidence I/O are excluded from root latency. No hard deadline, Quest, "
    "cross-device/person generalization or isolated Windows/cache/power causality claim.")


def check_reference(root, config):
    for relative, digest in config["reference_source_hashes"].items():
        require_hash(scoped_path(root, relative), digest)


def run_worker_timing(root, destination, job, config, frozen, bundle, records):
    measured, warmup, burst_sources = select_sources(records)
    puf, auth, pairs, materials = make_materials(root, frozen, sorted({r["device_id"] for r in measured}))
    capture, snapshots, bursts = TimingCapture(), [], []
    ledger = PublicLedger(capture)
    before = resource_snapshot(capture)
    start = time.perf_counter_ns()
    initial_callbacks, initial_thresholds = tuple(gc.callbacks), gc.get_threshold()
    with threadpool_limits(limits=1), quality_validator_mode(job["mode"]), ledger.observe_sender(), instrument_pipeline(capture):
        pools = threadpool_info()
        for condition in job["condition_order"]:
            selected = one_model_bundle(bundle, condition)
            snapshots.append(dict(condition=condition["name"], phase="before_condition", resource=resource_snapshot(capture)))
            with (destination / f"timings-{condition['name']}.jsonl").open("x", encoding="utf-8", newline="\n") as evidence:
                for cohort, sources in (("warmup", warmup), ("measured", measured)):
                    rngs = {device_id: rng_for(config["read_domain"].format(
                        block=job["block"], device_index=value[0], cohort=cohort))
                        for device_id, value in materials.items()}
                    for index, source in enumerate(sources):
                        phase = "condition_first_use" if cohort == "warmup" and index == 0 else cohort
                        _, device, reference, credential, enrollment_id, helper, service = materials[source["device_id"]]
                        sender = Sender(provision_device(source["device_id"], enrollment_id, helper),
                                        auth.session_config().limits, admission_service=service)
                        verifier = Verifier([RegistryEntry(source["device_id"], enrollment_id, credential)],
                                            auth.session_config(), admission_service=service)
                        pipeline = V2InferencePipeline(sender, verifier,
                            capture.wrap("prepare_both_model_inputs", ledger.observe("preprocessing", prepare_model_inputs)),
                            capture.wrap("motion_consumer_including_normalization", ledger.observe("motion", selected.motion_predictions)),
                            capture.wrap("anomaly_consumer_including_threshold", ledger.observe("anomaly", selected.anomaly_predictions)))
                        responses = []
                        def read_once():
                            response = generate_response(device, pairs, puf.nominal_frequency, puf.read_conditions,
                                                         rng=rngs[source["device_id"]])
                            responses.append(response)
                            return response
                        def emit(trace, window_source=source, ordinal=index, trace_phase=phase):
                            if capture.active or len(responses) != 1:
                                raise RuntimeError("evidence must follow exactly one response read and a completed root")
                            trace.update(condition=condition["name"], phase=trace_phase, attempt_index=ordinal,
                                source_window_id=window_source["window_id"], device_id=window_source["device_id"],
                                source_split=window_source["split"], selected_bit_error_count=selected_bit_errors(reference, responses[0]),
                                mode=job["mode"], block=job["block"], public_inference=ledger.finish(trace["model_calls"]))
                            # Hashes of nonsecret sensor/model inputs only; no raw wire payload or cryptographic material.
                            trace.pop("event_id", None)
                            evidence.write(json.dumps(trace, sort_keys=True, allow_nan=False) + "\n")
                            evidence.flush()
                        try:
                            attempt = run_timed_attempt(pipeline, source, read_once,
                                f"quality-{job['block']}-{job['mode']}-{condition['name']}-{cohort}-{index}", capture, emit)
                            if cohort == "measured" and index == 119:
                                if attempt.decision == "accept":
                                    def emit_burst(trace, window_source, ordinal):
                                        emit(trace, window_source, ordinal, "sustained")
                                    outcome = sustained_burst(pipeline, burst_sources, capture, emit_burst)
                                else:
                                    outcome = dict(planned_windows=64, completed_windows=0,
                                        closed_loop_wall_ns=None, windows_per_second=None,
                                        unavailable_reason="final_planned_admission_refused_no_retry")
                                bursts.append(dict(condition=condition["name"], block=job["block"], mode=job["mode"], **outcome))
                        finally:
                            if not verifier.incomplete:
                                verifier.close_all_sessions()
                    snapshots.append(dict(condition=condition["name"], phase=cohort, resource=resource_snapshot(capture)))
                    print(f"{job['job_id']} {condition['name']} {cohort}: {len(sources)} attempts retained", flush=True)
    if not gc.isenabled() or gc.get_threshold() != initial_thresholds or tuple(gc.callbacks) != initial_callbacks:
        raise RuntimeError("normal GC/callback policy drifted; preserve incomplete evidence")
    before_cleanup_ns = time.perf_counter_ns() - start
    cleanup_result = cleanup(capture, ledger)
    total_ns = time.perf_counter_ns() - start
    runtime = dict(before=before, snapshots=snapshots, final=cleanup_result,
        workload_before_cleanup_wall_ns=before_cleanup_ns, workload_including_cleanup_wall_ns=total_ns,
        workload_wall_includes_endpoint_creation_assertions_evidence_io_and_resource_snapshots=True,
        model_loading_and_enrollment_excluded=True, throughput_interpretation="unpaced serial software capacity, not sensor arrival rate",
        normal_automatic_gc=True, native_threadpools=pools, sustained=bursts)
    write_json(destination / "runtime-and-cleanup.json", runtime)
    # Reload trees ONLY after timing and cleanup; no growing cohort of trees in timed workers.
    traces = read_job_traces(destination, job)
    reconciliation = validate_rows(traces, job, config)
    summary = summarize_traces(traces)
    analysis = SavedStageAnalysis()
    for trace in traces:
        if trace["phase"] != "sustained":
            analysis.add(trace)
    stages = analysis.finalize([c["name"] for c in job["condition_order"]], measured=120, warmup=30)
    write_json(destination / "summary.json", summary)
    write_json(destination / "reconciliation.json", reconciliation)
    write_csv(destination / "direct-path-latency.csv", summary["root_paths"])
    write_csv(destination / "inclusive-stage-latency.csv", summary["nested_stages"])
    write_csv(destination / "exclusive-stage-accounting.csv", stages["exclusive_stages"])
    write_csv(destination / "per-observation-accounting.csv", stages["observations"])
    with (destination / "retained-outliers.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
        for row in select_outliers(traces):
            handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    accepted_windows = sum(trace["decision"] == "accept" for trace in traces)
    runtime["accepted_windows"] = accepted_windows
    runtime["mixed_workload_accepted_windows_per_second_including_cleanup"] = accepted_windows * 1e9 / total_ns
    # The first saved runtime is deliberately immutable. Derived capacity uses the saved denominator.
    write_json(destination / "mixed-workload-capacity.json", {
        key: runtime[key] for key in ("accepted_windows", "mixed_workload_accepted_windows_per_second_including_cleanup")})
    return reconciliation


def worker(root, config_path, output, index, control_hash):
    require_hash(output / "control.json", control_hash)
    control, config = read_json(output / "control.json"), read_json(config_path)
    validate_config(config)
    require_hash(config_path, control["configuration_sha256"])
    if control["jobs"] != build_jobs(config) or not 0 <= index < len(control["jobs"]):
        raise ValueError("worker is not in the predeclared plan")
    require_source_unchanged(root, control["source_commit"], output)
    check_reference(root, config)
    normal_gc_conditions(config)
    frozen_path = scoped_path(root, config["frozen_config"])
    require_hash(frozen_path, control["frozen_configuration_sha256"])
    frozen = read_json(frozen_path)
    for path, digest in control["supporting_configurations"].items():
        require_hash(scoped_path(root, path), digest)
    bundle = load_frozen_bundle(root, frozen)
    if bundle.artifact_hashes != control["frozen_input_hashes"]:
        raise ValueError("worker model/normalization/threshold bytes differ")
    records = load_records(scoped_path(root, frozen["input_path"]))
    job = control["jobs"][index]
    destination = output / "workers" / job["job_id"]
    begin_directory(destination)
    write_json(destination / "job.json", job)
    environment = dict(python=platform.python_version(), platform=platform.platform(), numpy=np.__version__,
        sklearn=sklearn.__version__, torch=torch.__version__, galois=galois.__version__, joblib=joblib.__version__,
        timers=normal_gc_conditions(config), machine_start=collect_machine(), power=control["power"],
        background=control["background"], torch_threads=torch.get_num_threads(),
        torch_interop_threads=torch.get_num_interop_threads(), automatic_gc_not_deferred=True,
        cpu_frequency_core_affinity_and_thermal_state_controlled=False)
    write_json(destination / "environment-start.json", environment)
    counts = run_worker_timing(root, destination, job, config, frozen, bundle, records)
    environment.update(machine_end=collect_machine(), timers_end=normal_gc_conditions(config))
    environment["power_plan_changed"] = (environment["machine_start"].get("ActivePowerPlan") !=
                                          environment["machine_end"].get("ActivePowerPlan"))
    write_json(destination / "environment.json", environment)
    require_source_unchanged(root, control["source_commit"], output)
    check_reference(root, config)
    recheck_frozen_inputs(root, frozen, bundle.artifact_hashes)
    complete_directory(destination, dict(run_type=config["config_version"], source_commit=control["source_commit"],
        source_worktree_dirty=False, job=job, configuration_sha256=control["configuration_sha256"],
        frozen_input_hashes=bundle.artifact_hashes, **counts, training_executed=False, threshold_selection_executed=False,
        default_pipeline_modified=False, recording_executed=False, durable_audit_measured=False,
        authentication_executed=True, model_inference_executed=True, latency_measured=True, limitation=LIMITATION))


def report_text(tables, throughput):
    lines = ["# Bounded exact-quality arithmetic comparison", "",
        "Only quality arithmetic changes between isolated workers. The default v2 path is unchanged.",
        "Two AB/BA paired noise blocks; three predeclared frozen configurations; 120 measured and",
        "30 validation warmup admissions per configuration/mode/block. All failures and first uses retained.", "",
        "## Direct accepted totals (conditional on successful admission)", "",
        "| Block | Mode | Configuration | Phase / path | n | p50 ms | p95 ms | p99 ms | max ms |",
        "|---|---|---|---|---:|---:|---:|---:|---:|"]
    for row in tables:
        if row["phase"] == "measured" and row["path"] in {"post_window_recurring", "fresh_to_first_window"} and row["decision"] == "accept":
            lines.append(f"| {row['block']} | {row['mode']} | {row['condition']} | {row['phase']} / {row['path']} | "
                         f"{row['count']} | {row['p50_ms']:.4f} | {row['p95_ms']:.4f} | {row['p99_ms']:.4f} | {row['max_ms']:.4f} |")
    lines += ["", "Compare candidate against its NEW matched reference, not against historical laptop percentiles.",
        "Per-block results are descriptive; two reused-source noise blocks do not supply a robust population CI.",
        "Paired deltas are candidate minus reference for identical inputs/outcomes, not differences of percentiles.",
        "Rejects/fresh admission failures have separate rows and denominators. Never add stage p95s for a total.", "",
        "## Sustained same-session processing", "",
        "| Block | Mode | Configuration | Planned / completed | Closed-loop windows/s |",
        "|---|---|---|---:|---:|"]
    for row in throughput:
        value = "N/A" if row["windows_per_second"] is None else f"{row['windows_per_second']:.3f}"
        lines.append(f"| {row['block']} | {row['mode']} | {row['condition']} | {row['planned_windows']} / {row['completed_windows']} | {value} |")
    lines += ["", "The 64-window burst reuses the final PLANNED admission. If it fails, report N/A; do not retry",
        "or replace that attempt. Bursts use 64 distinct same-profile preselected test windows. Automatic GC",
        "stays enabled; closed-loop throughput includes assertions, signatures and evidence writes but",
        "excludes admission, loading and final cleanup. Worker-wide mixed workload capacity includes cleanup",
        "and is reported separately: it is NOT recurring-only throughput. This is unpaced capacity, not a",
        "sensor-arrival/backpressure study. Coarse working-set/private-commit snapshots are not stage peaks.", "",
        "## Stage and interpretation boundaries", "",
        "Worker tables retain the SAME nested timers and per-root exclusive partition as the historical",
        "stage analysis. Sender serialization still includes quality; receiver quality is separately timed.",
        "Binding/sequence/locks/state and handshake/HKDF/confirmation remainders remain explicitly unisolated.",
        "Full in-memory audit calls are included; durable audit storage is not. Motion and anomaly consumer",
        "timings include their own scaling/normalization/dispatch work. Public input/output fingerprints are",
        "computed after roots; storing references inside callbacks is observer overhead in both modes.", "",
        "The wire comparison neutralizes ONLY the 16 fresh random session-ID bytes in a post-timer COPY;",
        "all other authenticated header/payload bytes remain in that hash. Actual packets/HMAC bindings",
        "are untouched. Random session IDs and cryptographic tags are not expected to match across workers.", "",
        "The provisional 20 ms boundary is complete post-window processing, not receiver-only, crypto-only",
        "or motion-only timing. Report any observed bounded-cohort attainment with its sample size and",
        "conditions, without declaring deployment qualification. Keep the original architecture's unmet",
        "target and historical evidence visible. The physical TWO-SECOND acquisition window is additional",
        "and excluded: these numbers are not total event-to-decision latency.", "",
        "This tests one shared application bottleneck; it cannot remove SNN or forest inference costs.",
        "Seed 7 was predeclared, not chosen for speed; other SNN seeds remain historical evidence.",
        "No fresh majority-3/correlated-noise study, conventional-key control, new security trial, model",
        "search, threshold adjustment, OS tracing or default authentication change occurred.", "", LIMITATION, ""]
    return "\n".join(lines)


def controller(root, config_path, requested_output, power, background):
    config = read_json(config_path)
    validate_config(config)
    if power != "ac" or background != "heavy_apps_closed":
        raise ValueError("confirm AC power and heavy apps closed before the actual benchmark")
    commit = require_clean_source(root)
    check_reference(root, config)
    normal_gc_conditions(config)
    output = new_output_path(root, requested_output)
    frozen_path = scoped_path(root, config["frozen_config"])
    frozen = read_json(frozen_path)
    print("Checking all frozen bytes; no training or threshold changes", flush=True)
    bundle = load_frozen_bundle(root, frozen)
    hashes = bundle.artifact_hashes
    del bundle
    records = load_records(scoped_path(root, frozen["input_path"]))
    measured, warmup, sustained = select_sources(records)
    selection = {phase: [{k: r[k] for k in ("window_id", "device_id", "label", "split")} for r in rows]
                 for phase, rows in (("measured", measured), ("warmup", warmup), ("sustained", sustained))}
    del records
    jobs = build_jobs(config)
    control = dict(source_commit=commit, jobs=jobs, configuration_sha256=sha256(config_path),
        frozen_configuration_sha256=sha256(frozen_path), frozen_input_hashes=hashes,
        power=power, background=background, supporting_configurations={
            frozen[key]: sha256(scoped_path(root, frozen[key])) for key in ("puf_config", "auth_config")})
    begin_directory(output)
    write_json(output / "config.json", config)
    write_json(output / "control.json", control)
    write_json(output / "source-selection.json", selection)
    for index, job in enumerate(jobs):
        require_source_unchanged(root, commit, output)
        print(f"Starting worker {index+1}/4: {job['job_id']}", flush=True)
        try:
            subprocess.run([sys.executable, "-u", str(Path(__file__).resolve()), "--config", str(config_path.resolve()),
                "--output", str(output), "--worker", str(index), "--control-hash", sha256(output / "control.json")],
                cwd=root, check=True)
        except BaseException:
            write_json(output / "execution-failure.json", dict(job_id=job["job_id"],
                reason="worker_error_not_ordinary_admission_refusal_preserve_evidence"))
            raise
    manifests, tables, throughput, paired = {}, [], [], []
    rows_by_job = {}
    for job in jobs:
        directory = output / "workers" / job["job_id"]
        manifests[job["job_id"]] = checked_completion(directory, expected_job=job, expected_commit=commit)
        rows = read_job_traces(directory, job)
        if validate_rows(rows, job, config) != read_json(directory / "reconciliation.json"):
            raise ValueError("worker saved reconciliation differs")
        summary = summarize_traces(rows)
        if summary != read_json(directory / "summary.json"):
            raise ValueError("worker saved quantiles differ")
        tables.extend(dict(row, block=job["block"], mode=job["mode"]) for row in summary["root_paths"])
        throughput.extend(read_json(directory / "runtime-and-cleanup.json")["sustained"])
        rows_by_job[job["job_id"]] = rows
    for block in range(2):
        paired.extend(paired_rows(rows_by_job[f"block-{block}-reference_fraction"],
                                  rows_by_job[f"block-{block}-candidate_dyadic"]))
    write_csv(output / "direct-path-latency.csv", tables)
    write_csv(output / "paired-root-deltas.csv", paired)
    write_json(output / "sustained-throughput.json", throughput)
    (output / "quality-benchmark.md").write_text(report_text(tables, throughput), encoding="utf-8", newline="\n")
    require_source_unchanged(root, commit, output)
    check_reference(root, config)
    recheck_frozen_inputs(root, frozen, hashes)
    counts = dict(worker_count=4, fresh_attempt_count=sum(m["fresh_attempt_count"] for m in manifests.values()),
        trace_count=sum(m["trace_count"] for m in manifests.values()),
        sustained_window_count=sum(m["sustained_window_count"] for m in manifests.values()),
        paired_public_input_output_and_state_signatures_match=True, rejected_window_model_calls=0,
        worker_manifest_hashes={name: sha256(output / "workers" / name / "manifest.json") for name in manifests})
    if counts["fresh_attempt_count"] != 1800:
        raise ValueError("master fresh-admission denominator differs")
    write_json(output / "reconciliation.json", counts)
    complete_directory(output, dict(run_type=config["config_version"], source_commit=commit, source_worktree_dirty=False,
        configuration_sha256=control["configuration_sha256"], frozen_input_hashes=hashes, **counts,
        training_executed=False, threshold_selection_executed=False, model_inference_executed=True,
        authentication_executed=True, latency_measured=True, automatic_gc_deferred=False,
        default_pipeline_modified=False, recording_executed=False, historical_files_modified=False,
        durable_audit_measured=False, limitation=LIMITATION))
    print("PASS: paired inputs/predictions/state, all attempts, stage partitions and cleanup reconciled", flush=True)
    print(json.dumps(counts, indent=2), flush=True)
    print(f"Saved bounded comparison to {output}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/week6_quality_benchmark.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/week-6/keegan/quality-benchmark")
    parser.add_argument("--power", choices=("ac", "unconfirmed"), default="unconfirmed")
    parser.add_argument("--background", choices=("heavy_apps_closed", "unconfirmed"), default="unconfirmed")
    parser.add_argument("--worker", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--control-hash", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker is None:
        if args.control_hash is not None:
            parser.error("control hash is internal to planned workers")
        controller(ROOT, args.config, args.output, args.power, args.background)
    else:
        scope = (ROOT / "results/week-6/keegan").resolve()
        if not args.control_hash or args.output.resolve() == scope or not args.output.resolve().is_relative_to(scope):
            parser.error("worker requires a scoped controller output and its hash")
        worker(ROOT, args.config, args.output.resolve(), args.worker, args.control_hash)


if __name__ == "__main__":
    main()
