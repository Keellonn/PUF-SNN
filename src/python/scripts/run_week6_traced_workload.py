"""ONE private reference/traced worker; NEVER starts or stops WPR.

An owned Administrator PowerShell controller must orchestrate the separate
capture. This script does not provide an automatic recording/retry workflow.
--check-only reads pinned design/source files, without loading model binaries.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import platform
import re

from puf_snn.windows_trace import NativeEtwWriter
from puf_snn.windows_trace_workload import (
    LIMITATION, MarkerJournal, ac_power_status, cohort_marker_bridge,
    private_worker_path, selected_job, validate_marker_coverage, validate_trace_config,
)


ROOT = Path(__file__).resolve().parents[3]
PRIVATE_ROOT = Path("C:/Users/datbo/Documents/ChatGPT/SNN/private-traces")
FROZEN_CONFIG_HASH = "ff10c6b53ce8041f39bf26c99d793fda64a8cbde6cbe4dd6c05e28b3437a100f"


def checked_design(root, config_path):
    """Source/configuration-only check. No frozen binary deserialization."""
    from puf_snn.frozen_pipeline import read_json, require_hash, scoped_path
    from puf_snn.outlier_experiment import validate_experiment_config
    config = read_json(config_path)
    validate_trace_config(config)
    for path_key, hash_key in (("base_config", "base_config_sha256"),
                               ("base_runner", "base_runner_sha256"), ("profile", "profile_sha256")):
        require_hash(scoped_path(root, config[path_key]), config[hash_key])
    base = read_json(scoped_path(root, config["base_config"]))
    validate_experiment_config(base)
    frozen_path = scoped_path(root, base["frozen_config"])
    require_hash(frozen_path, FROZEN_CONFIG_HASH)
    job = selected_job(base)
    return config, base, frozen_path, job


def run_worker(root, config_path, requested_output, expected_commit, expected_config_hash):
    from puf_snn.frozen_pipeline import (
        load_frozen_bundle, read_json, require_hash, scoped_path, sha256,
    )
    from puf_snn.outlier_experiment import (
        checked_historical_inputs, read_job_traces, recheck_frozen_inputs,
        require_source_unchanged, validate_worker_traces,
    )
    from puf_snn.snn.dataset import load_records
    from scripts import run_week6_outlier_experiment as original
    from scripts.benchmark_week6_v2 import collect_machine
    from scripts.run_week6_smoke import require_clean_source, write_json

    require_hash(config_path, expected_config_hash)
    config, base, frozen_path, job = checked_design(root, config_path)
    destination = private_worker_path(requested_output, root, PRIVATE_ROOT)
    commit = require_clean_source(root)
    if commit != expected_commit:
        raise ValueError("worker HEAD differs from the controller's pinned source")
    power_start = ac_power_status()
    original.begin_directory(destination)
    write_json(destination / "job.json", job)
    write_json(destination / "trace-config.json", config)
    role = destination.name
    with ExitStack() as stack:
        evidence = stack.enter_context((destination / "marker-brackets.jsonl").open(
            "x", encoding="utf-8", newline="\n"))
        writer = stack.enter_context(NativeEtwWriter()) if role == "traced" else None
        markers = MarkerJournal(writer, evidence) if writer is not None else None
        if markers is not None:
            markers.mark("capture_begin")
        frozen = read_json(frozen_path)
        print(f"{role}: checking original timing inventory and all frozen model bytes", flush=True)
        historical_directory, _, historical_hashes = checked_historical_inputs(root, base)
        bundle = load_frozen_bundle(root, frozen)
        if len(bundle.artifact_hashes) < 11:
            raise ValueError("incomplete frozen input inventory")
        records = load_records(scoped_path(root, frozen["input_path"]))
        environment = dict(python=platform.python_version(), platform=platform.platform(),
                           numpy=original.np.__version__, scikit_learn=original.sklearn.__version__,
                           torch=original.torch.__version__, joblib=original.joblib.__version__,
                           galois=original.galois.__version__,
                           torch_intraop_threads=original.torch.get_num_threads(),
                           torch_interop_threads=original.torch.get_num_interop_threads(),
                           timers=original.timer_metadata(base), machine_start=collect_machine(),
                           power_start=power_start, model_loading_inside_etl_but_outside_roots=True,
                           self_reported_background="heavy_apps_closed",
                           cpu_frequency_core_affinity_and_thermal_state_controlled=False)
        write_json(destination / "environment-start.json", environment)
        write_json(destination / "input-binding.json", dict(
            source_commit=commit, configuration_sha256=sha256(config_path),
            frozen_configuration_sha256=sha256(frozen_path), frozen_input_hashes=bundle.artifact_hashes,
            source_dataset_sha256=frozen["input_sha256"], historical_hashes=historical_hashes,
            supporting_configuration_hashes={frozen[key]: sha256(scoped_path(root, frozen[key]))
                                            for key in ("puf_config", "auth_config")},
            original_runner_sha256=config["base_runner_sha256"]))
        require_source_unchanged(root, commit, destination)
        if markers is not None:
            markers.mark("inputs_verified")
        with cohort_marker_bridge(original, markers, job):
            counts = original.run_timing_worker(root, destination, job, base, frozen, bundle, records)
        if counts["fresh_attempt_count"] != config["planned_attempts_per_worker"]:
            raise ValueError("planned admission count differs")
        if counts["rejected_window_model_calls"] != 0:
            raise ValueError("rejected traffic invoked a model")
        if markers is not None:
            markers.mark("capture_end")
        saved_markers = [] if markers is None else list(markers.rows)
    # Provider has been unregistered; the controller still owns the WPR session.
    environment.update(machine_end=collect_machine(), power_end=ac_power_status(),
                       timers_end=original.timer_metadata(base),
                       provider_unregistered=writer is None or writer.unregister_status == 0)
    environment["power_plan_changed"] = (
        environment["machine_start"].get("ActivePowerPlan") != environment["machine_end"].get("ActivePowerPlan"))
    write_json(destination / "environment.json", environment)
    traces = read_job_traces(destination, job)
    validate_worker_traces(traces, job, base)
    coverage = validate_marker_coverage(saved_markers, traces, job) if role == "traced" else dict(
        marker_count=0, root_count=len(traces), etw_markers_written=False)
    write_json(destination / "marker-coverage.json", coverage)
    require_source_unchanged(root, commit, destination)
    recheck_frozen_inputs(root, frozen, bundle.artifact_hashes)
    for relative, digest in historical_hashes.items():
        require_hash(historical_directory / relative, digest)
    binding = read_json(destination / "input-binding.json")
    for relative, digest in binding["supporting_configuration_hashes"].items():
        require_hash(scoped_path(root, relative), digest)
    checked_design(root, config_path)
    require_hash(config_path, expected_config_hash)
    original.complete_directory(destination, dict(
        run_type=config["config_version"], worker_role=role, job=job, source_commit=commit,
        source_worktree_dirty=False, configuration_sha256=expected_config_hash,
        frozen_input_hashes=bundle.artifact_hashes, **counts, marker_count=coverage["marker_count"],
        training_executed=False, threshold_selection_executed=False,
        actual_saved_markers_validated=False, clock_alignment_validated=False,
        event_loss_validated=False, complete_causal_attribution_established=False,
        performance_target_claim=False, historical_files_modified=False,
        durable_audit_measured=False, raw_trace_is_private=True, limitation=LIMITATION))
    print(f"PASS: {role} application worker completed; OS capture/attribution still need review", flush=True)
    print(json.dumps(dict(counts, marker_count=coverage["marker_count"],
                          os_cause_established=False), indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/week6_traced_workload.json")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--configuration-sha256")
    args = parser.parse_args()
    if args.check_only:
        if any(value is not None for value in (args.output, args.source_commit, args.configuration_sha256)):
            parser.error("CheckOnly cannot be combined with worker/capture arguments")
        checked_design(ROOT, args.config)
        print("PASS: fixed traced-workload design and pinned original sources match")
        print("CheckOnly: no model deserialization, inference, ETW writes, recording, output or Git changes")
        return
    if (args.output is None or not re.fullmatch(r"[0-9a-f]{40}", args.source_commit or "")
            or not re.fullmatch(r"[0-9a-f]{64}", args.configuration_sha256 or "")):
        parser.error("worker requires private output plus controller-pinned commit/configuration hashes")
    run_worker(ROOT, args.config, args.output, args.source_commit, args.configuration_sha256)


if __name__ == "__main__":
    main()
