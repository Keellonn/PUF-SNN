"""Fresh simulated-response v2 admission and frozen composite CPU timing.

Serial, instrumented software measurements; no new training or success criteria.
Existing checkpoints/thresholds and nominal reconstruction policy remain frozen.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from contextlib import ExitStack
from datetime import datetime, timezone
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
from puf_snn.auth.config import AuthConfig
from puf_snn.auth.credential_verifier import (
    CredentialAdmissionService, CredentialVerifierRecord, CredentialVerifierStore,
    InMemoryCredentialVerifierKeyProvider,
)
from puf_snn.auth.sender import Sender
from puf_snn.auth.session import RegistryEntry, provision_device
from puf_snn.auth.verifier import Verifier
from puf_snn.frozen_pipeline import load_frozen_bundle, read_json, scoped_path, sha256
from puf_snn.pipeline_timing import (
    TimingCapture, instrument_pipeline, latency_statistics, one_model_bundle,
    reconcile_timing, run_timed_attempt, select_outliers, select_timing_sources,
    summarize_traces, validate_timing_config,
)
from puf_snn.pipeline_v2 import V2InferencePipeline
from puf_snn.puf.device import create_device
from puf_snn.puf.ro_puf import generate_pairs, generate_response
from puf_snn.puf.variables import load_config as load_puf_config
from puf_snn.reconstruction import enroll
from puf_snn.snn.dataset import load_records
from scripts.run_week6_smoke import require_clean_source, rng_for, selected_bit_errors, write_json, write_result_attributes


ROOT = Path(__file__).resolve().parents[3]
LIMITATION = (
    "Instrumented, single-process CPU software prototype with loaded synthetic windows, six fixed "
    "simulated PUF profiles and paired repeated sources/noise streams. Not hardware response acquisition, "
    "physical two-second motion capture, network transport, durable audit, an independent FRR/security "
    "study, real-time guarantee or Quest/cross-device/person generalization. Enrollment, loading, endpoint "
    "construction, result/progress I/O and orderly shutdown are outside the timed boundary. All nested "
    "spans include observer overhead. Outlier location/GC overlap/CPU gaps do not establish causation.")


def collect_machine():
    if platform.system() != "Windows":
        return {"collection_status": "not_windows", "cpu_frequency_controlled": False}
    command = (
        "$timingMachine = Get-CimInstance Win32_ComputerSystem; "
        "$timingWindows = Get-CimInstance Win32_OperatingSystem; "
        "[pscustomobject]@{Manufacturer=$timingMachine.Manufacturer; MachineModel=$timingMachine.Model; "
        "MemoryGiB=[math]::Round($timingMachine.TotalPhysicalMemory/1GB,1); "
        "Processors=@(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,CurrentClockSpeed); "
        "Windows=$timingWindows.Caption; WindowsVersion=$timingWindows.Version; "
        "ActivePowerPlan=(powercfg /getactivescheme | Out-String).Trim()} | ConvertTo-Json -Depth 5")
    try:
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                                capture_output=True, text=True, check=True, timeout=30)
        return {"collection_status": "collected", "cpu_frequency_controlled": False,
                "clock_speed_is_snapshot_not_fixed_frequency": True, **json.loads(result.stdout)}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"collection_status": "unavailable", "cpu_frequency_controlled": False}


def timer_conditions():
    timer = time.get_clock_info("perf_counter")
    if not timer.monotonic or timer.adjustable or not gc.isenabled():
        raise ValueError("benchmark requires enabled GC and a monotonic non-adjustable timer")
    return {"gc_enabled": gc.isenabled(), "gc_thresholds": list(gc.get_threshold()),
            "wall_timer": timer.implementation, "monotonic": timer.monotonic,
            "adjustable": timer.adjustable, "resolution_seconds": timer.resolution,
            "cpu_timer": time.get_clock_info("thread_time").implementation,
            "gc_callbacks": "overlap instrumentation; no forced collection or disabling"}


def write_csv(path, rows):
    with path.open("x", encoding="utf-8", newline="") as handle:
        if rows:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


def make_materials(root, frozen, device_ids):
    """Trusted enrollment only. Never serialize any returned object."""
    puf = load_puf_config(scoped_path(root, frozen["puf_config"]))
    if (puf.number_of_devices != 6 or puf.number_of_oscillators != 128 or puf.pairing_scheme != "adjacent"
            or puf.random_seed != 6767 or puf.nominal_frequency != 100 or puf.manufacturing_std != 1
            or puf.aging_std != 0 or puf.reference_conditions.environmental_offset != 0
            or puf.reference_conditions.measurement_noise_std != 0
            or puf.read_conditions.environmental_offset != 0 or puf.read_conditions.measurement_noise_std != .1):
        raise ValueError("the frozen nominal simulated PUF baseline changed")
    auth = AuthConfig.load(scoped_path(root, frozen["auth_config"]))
    if auth != AuthConfig():
        raise ValueError("do not extend TTL or change the current v2 admission/window policy")
    pairs = generate_pairs(puf.number_of_oscillators, puf.pairing_scheme)
    materials = {}
    for index, device_id in enumerate(device_ids):
        device = create_device(device_id, puf.number_of_oscillators, puf.manufacturing_std,
                               rng=rng_for(f"week2-v1:6767:{index}:manufacturing"))
        reference = generate_response(device, pairs, puf.nominal_frequency, puf.reference_conditions,
                                      rng=rng_for(f"week2-v1:6767:{index}:enrollment"))
        credential = rng_for(f"week6-timing-v1:6767:{index}:credential").getrandbits(32).to_bytes(4, "big")
        enrollment_id = f"week6-timing-enrollment-{index}"
        helper = enroll(reference, credential, enrollment_id=enrollment_id)
        key_id = f"week6-timing-verifier-key-{index}"
        provider = InMemoryCredentialVerifierKeyProvider.generate(key_id)
        record = CredentialVerifierRecord.enroll(
            device_id=device_id, enrollment_id=enrollment_id, reconstruction_id=helper.config.version,
            verifier_key_id=key_id, credential4=credential, key_provider=provider)
        service = CredentialAdmissionService(CredentialVerifierStore([record]), provider)
        materials[device_id] = (index, device, reference, credential, enrollment_id, helper, service)
    return puf, auth, pairs, materials


def source_unchanged(root, original_commit):
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    if head != original_commit:
        raise RuntimeError("source HEAD changed during timing; preserve incomplete evidence")
    for command in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        if subprocess.run(command, cwd=root).returncode != 0:
            raise RuntimeError("tracked source changed during timing; preserve incomplete evidence")


def report_text(source_commit, summary, reconciliation):
    lines = ["# Week 6 fresh v2 composite CPU timing", "", f"Source commit: `{source_commit}`", "",
             f"Recorded fresh attempts (including warmup/first use): {reconciliation['fresh_attempt_count']}.", "",
             "Each of six predeclared conditions has 600 measured single-read attempts and 20 retained",
             "validation warmups. The first warmup is condition-first-use, NOT a fully cold process.",
             "Trusted enrollment has already initialized code algebra, but no decoder/model inference",
             "warmup is hidden before the first condition. First decoder JIT overhead may appear there.", "",
             "## Direct outer-path summaries", "",
             "| Condition | Phase | Path | Decision/reason | n | p50 ms | p95 ms | p99 ms | max ms |",
             "|---|---|---|---|---:|---:|---:|---:|---:|"]
    for row in summary["root_paths"]:
        if row["phase"] not in ("measured", "condition_first_use"):
            continue
        lines.append(f"| {row['condition']} | {row['phase']} | {row['path']} | {row['decision']}/{row['reason']} | "
                     f"{row['count']} | {row['p50_ms']:.4f} | {row['p95_ms']:.4f} | {row['p99_ms']:.4f} | {row['max_ms']:.4f} |")
    lines += ["", "## Interpretation boundaries", "",
              "Fresh timing starts before the modeled response read and ends after refusal or the first",
              "composite inference. The source motion window is already loaded: physical capture is excluded.",
              "Recurring/after-refusal full-window paths include binary32 conversion, sender binding/quality/HMAC,",
              "receiver parser/HMAC/quality/sequence/audit commit, at-most-once conversion/preprocessing and both models.",
              "Receiver-only paths exclude packet construction and sender sealing; pre-tag refusal is not an HMAC rejection.", "",
              "The provisional 20 ms p95 target applies ONLY to complete post-window paths, including the anomaly",
              "consumer here. It does not apply to fresh admission totals, receiver-only timings, maxima or hard deadlines.",
              "Assess each recorded condition separately: no blanket meets-target claim, especially for random forest.", "",
              "Motion-consumer timing includes normalization/tensor construction/prediction decoding, not only forward compute.",
              "Credential verification, local admission, confirmation, serialization, HMAC and in-memory audit calls have",
              "nested spans. Current replay-state checks/publication remain inside verifier authentication, not isolated",
              "disjoint stages. Native HKDF values are nested in challenge/confirmation; never add nested percentiles.", "",
              "All warmups, natural admission failures, slow values and maxima are retained. Paired noise streams and",
              "sources are reused across conditions: 3,600 measured attempts are not 3,600 independent reliability trials.",
              "Functional bad-tag/replay/malformed/quality controls are NOT formal varied Tier-1 evaluation.", "",
              "Post-window distributions are conditional on successful admission; natural admission refusals remain",
              "in fresh-attempt totals. Model conditions run in fixed order, so thermal/background drift is not",
              "eliminated by pairing source/noise streams. This is not a causal hardware comparison.", "",
              "## Outlier evidence, not invented diagnoses", "",
              "The per-condition outliers-*.jsonl files retain every >20 ms observation, group p99 tail and maximum,",
              "with full stage trees, GC overlap, thread CPU and wall gaps. Disk/progress output is outside each span.",
              "A wall/thread-CPU gap can reflect waiting, worker work or descheduling; it does not prove OS scheduling.",
              "GC overlap does not prove that GC caused all delay. Allocation/cache/frequency/OS causes are unmeasured",
              "and explicitly unresolved. Further causal profiling is required before explaining every large outlier.", "",
              "Instrumentation uses temporary wrappers and GC callbacks. overhead.json records a no-op proxy, not a",
              "calibrated correction; no subtraction or claim of uninstrumented application latency is made.",
              "Read machine start/end snapshots and self-reported AC/background conditions in environment.json.",
              "Power plan is recorded, not changed; hybrid-core placement and CPU frequency are uncontrolled.", "",
              LIMITATION, "", "No training, selection, architecture expansion, reconstruction-policy or protocol change.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/week6_timing.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/week-6/keegan/fresh-v2-timing")
    parser.add_argument("--power", choices=("ac", "battery", "unconfirmed"), default="unconfirmed")
    parser.add_argument("--background", choices=("heavy_apps_closed", "unconfirmed"), default="unconfirmed")
    args = parser.parse_args()
    config = read_json(args.config)
    validate_timing_config(config)
    source_commit = require_clean_source(ROOT)
    output = args.output.resolve()
    scope = (ROOT / "results/week-6/keegan").resolve()
    if not output.is_relative_to(scope) or output == scope or output.exists():
        raise ValueError("choose a new scoped Week 6 output; never overwrite or automatically resume")
    timer = timer_conditions()
    frozen = read_json(scoped_path(ROOT, config["frozen_config"]))
    print("Verifying all frozen models; no fitting or threshold selection", flush=True)
    bundle = load_frozen_bundle(ROOT, frozen)
    test, warmup = select_timing_sources(load_records(scoped_path(ROOT, frozen["input_path"])))
    puf, auth, pairs, materials = make_materials(ROOT, frozen, sorted({r["device_id"] for r in test}))
    output.mkdir(parents=True)
    (output / "INCOMPLETE").write_text("Preserve all partial observations; no retry-until-success or overwrite.\n",
                                       encoding="utf-8", newline="\n")
    write_result_attributes(output / ".gitattributes")
    write_json(output / "config.json", config)
    write_json(output / "frozen-input-hashes.json", bundle.artifact_hashes)
    write_json(output / "source-selection.json", {
        "measured": [dict(window_id=r["window_id"], device_id=r["device_id"], label=r["label"], split=r["split"]) for r in test],
        "warmup": [dict(window_id=r["window_id"], device_id=r["device_id"], label=r["label"], split=r["split"]) for r in warmup]})
    environment = {"machine_start": collect_machine(), "timers": timer,
                   "self_reported_power": args.power, "self_reported_background": args.background,
                   "cpu_frequency_and_core_affinity_controlled": False,
                   "model_condition_order": "fixed predeclared order; thermal/background drift not controlled",
                   "python": platform.python_version(), "platform": platform.platform(), "numpy": np.__version__,
                   "scikit_learn": sklearn.__version__, "torch": torch.__version__,
                   "galois": galois.__version__, "joblib": joblib.__version__,
                   "torch_intraop_threads": torch.get_num_threads(), "torch_interop_threads": torch.get_num_interop_threads()}
    write_json(output / "environment-start.json", environment)
    capture, traces = TimingCapture(), []
    # A proxy for collector overhead is disclosed, never subtracted from results.
    proxy = []
    for _ in range(1000):
        capture.measure("noop_outer", capture.wrap("noop_nested", lambda: None))
        proxy.append(capture.last_trace["elapsed_ns"])
    write_json(output / "overhead.json", {"noop_outer_one_nested_span": latency_statistics(proxy),
                                         "method": "1000 no-op roots; not an estimate of all per-trial overhead; no subtraction"})
    with threadpool_limits(limits=config["native_threads"]), instrument_pipeline(capture), ExitStack() as evidence_files:
        environment["native_threadpools_during_run"] = threadpool_info()
        for condition in config["conditions"]:
            # Keep independently hash-bound condition files comfortably below a
            # single huge JSONL artifact; output remains outside every timer.
            evidence = evidence_files.enter_context((output / f"timings-{condition['name']}.jsonl").open(
                "x", encoding="utf-8", newline="\n"))
            selected_bundle = one_model_bundle(bundle, condition)
            for cohort, sources in (("warmup", warmup), ("measured", test)):
                # Reset to the SAME phase/device stream for each model condition;
                # different phase streams keep warmups from consuming study reads.
                read_rngs = {device_id: rng_for(f"week6-timing-v1:6767:{value[0]}:{cohort}:measurement")
                             for device_id, value in materials.items()}
                for index, source in enumerate(sources):
                    phase = "condition_first_use" if cohort == "warmup" and index == 0 else cohort
                    device_index, device, reference, credential, enrollment_id, helper, service = materials[source["device_id"]]
                    sender = Sender(provision_device(source["device_id"], enrollment_id, helper), auth.session_config().limits,
                                    admission_service=service)
                    verifier = Verifier([RegistryEntry(source["device_id"], enrollment_id, credential)],
                                        auth.session_config(), admission_service=service)
                    pipeline = V2InferencePipeline(sender, verifier,
                        capture.wrap("prepare_both_model_inputs", prepare_model_inputs),
                        capture.wrap("motion_consumer_including_normalization", selected_bundle.motion_predictions),
                        capture.wrap("anomaly_consumer_including_threshold", selected_bundle.anomaly_predictions))
                    responses = []

                    def read_once():
                        response = generate_response(device, pairs, puf.nominal_frequency, puf.read_conditions,
                                                     rng=read_rngs[source["device_id"]])
                        responses.append(response)
                        return response

                    def emit(trace):
                        if len(responses) != 1:
                            raise RuntimeError("one fresh response read is required, including failures")
                        trace.update(condition=condition["name"], phase=phase, attempt_index=index,
                                     source_window_id=source["window_id"], device_id=source["device_id"],
                                     source_split=source["split"], selected_bit_error_count=selected_bit_errors(reference, responses[0]))
                        evidence.write(json.dumps(trace, sort_keys=True, allow_nan=False) + "\n")
                        evidence.flush()
                        traces.append(trace)

                    try:
                        run_timed_attempt(pipeline, source, read_once,
                                          f"week6-time-{condition['name']}-{cohort}-{index}", capture, emit)
                    except BaseException:
                        if capture.last_trace is not None:
                            # Sanitized last trace only; no exception strings or provisioning objects.
                            write_json(output / "execution-failure.json", {
                                "condition": condition["name"], "phase": phase, "attempt_index": index,
                                "reason": "execution_error_not_ordinary_admission_refusal", "last_trace": capture.last_trace})
                        raise
                    finally:
                        if not verifier.incomplete:
                            verifier.close_all_sessions()
                    if (index + 1) % 50 == 0 or index + 1 == len(sources):
                        print(f"{condition['name']} {cohort}: {index + 1}/{len(sources)} attempts retained", flush=True)
    source_unchanged(ROOT, source_commit)
    environment["machine_end"] = collect_machine()
    environment["timers_end"] = timer_conditions()
    environment["power_plan_changed"] = environment["machine_start"].get("ActivePowerPlan") != environment["machine_end"].get("ActivePowerPlan")
    write_json(output / "environment.json", environment)
    reconciliation = reconcile_timing(traces, config["conditions"])
    summary = summarize_traces(traces)
    write_json(output / "reconciliation.json", reconciliation)
    write_json(output / "summary.json", summary)
    write_csv(output / "path-latency.csv", summary["root_paths"])
    write_csv(output / "nested-stage-latency.csv", summary["nested_stages"])
    outliers = select_outliers(traces, config["outlier_absolute_ms"])
    for condition in config["conditions"]:
        with (output / f"outliers-{condition['name']}.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
            for row in outliers:
                if row["trace"]["condition"] == condition["name"]:
                    handle.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
    (output / "timing-report.md").write_text(report_text(source_commit, summary, reconciliation), encoding="utf-8", newline="\n")
    manifest = {"run_type": config["config_version"], "source_commit": source_commit, "source_worktree_dirty": False,
                "completed_utc": datetime.now(timezone.utc).isoformat(), "command": sys.argv,
                "configuration_sha256": sha256(args.config), "frozen_configuration_sha256": sha256(scoped_path(ROOT, config["frozen_config"])),
                "input_sha256": frozen["input_sha256"], "supporting_configurations": {
                    key: sha256(scoped_path(ROOT, frozen[key])) for key in ("puf_config", "auth_config")},
                "randomness": {"manufacturing_domain": "week2-v1:6767:{device_index}:manufacturing",
                               "credential_domain": "week6-timing-v1:6767:{device_index}:credential",
                               "read_domain": "week6-timing-v1:6767:{device_index}:{warmup_or_measured}:measurement",
                               "condition_pairing": "same per-device phase streams reset for each condition",
                               "keys_and_handshake_nonces": "independent OS randomness"},
                "reconciliation": reconciliation, "outlier_count": len(outliers), "instrumentation_enabled": True,
                "training_executed": False, "threshold_selection_executed": False,
                "authentication_executed": True, "latency_measured": True, "durable_audit_measured": False,
                "limitation": LIMITATION,
                "artifacts": {p.name: sha256(p) for p in sorted(output.iterdir()) if p.is_file() and p.name != "INCOMPLETE"}}
    write_json(output / "manifest.json", manifest)
    write_json(output / "COMPLETE", {"manifest_sha256": sha256(output / "manifest.json"),
                                     "fresh_attempt_count": reconciliation["fresh_attempt_count"],
                                     "trace_count": len(traces), "outlier_count": len(outliers)})
    (output / "INCOMPLETE").unlink()
    print("PASS: fresh admission, composite deliveries, rejections and paired traces reconciled", flush=True)
    print("No retraining, threshold changes, formal Tier-1/FRR study or durable I/O timing", flush=True)
    print(json.dumps(reconciliation, indent=2), flush=True)
    print(f"Saved results to {output}", flush=True)


if __name__ == "__main__":
    main()
