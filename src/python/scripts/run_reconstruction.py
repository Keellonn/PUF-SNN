"""Frozen Layer 2 evaluation: one retained reconstruction per legitimate read.

Evaluator ground truth never enters reconstruct(). The CLI admits only the
documented cohort; small in-memory fixtures are used by the accounting tests.
"""

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
from random import Random
from statistics import mean, median, stdev
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/python"))

from puf_snn.puf.variables import load_config
from puf_snn.reconstruction import BCHCodec, DEFAULT_CONFIG, enroll, reconstruct
from scripts.analyze_week2_response_bits import (
    BASELINE, RUN_NAMES, analyze, digest, inspect_runs, require,
)
from scripts.run_puf_baseline import simulate

VERSION = "layer2-experiment-v1"
SEEDS = tuple(int(name.split("-")[2]) for name in RUN_NAMES)
NOISE_LEVELS = tuple(BASELINE["noise_sweep"])
CREDENTIAL_STREAM = "layer2-v1:{simulation_seed}:{device_index}:credential"


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def bit_tuple(value):
    require(len(value) == 64 and set(value) <= {"0", "1"}, "Invalid PUF response")
    return tuple(int(bit) for bit in value)


def credential_for(seed, device_index):
    identity = CREDENTIAL_STREAM.format(simulation_seed=seed, device_index=device_index)
    rng = Random()
    rng.seed(identity, version=2)
    return identity, rng.getrandbits(32).to_bytes(4, "big")


def source_hashes():
    paths = [Path(__file__), ROOT / "src/python/scripts/run_puf_baseline.py",
             ROOT / "src/python/scripts/analyze_week2_response_bits.py",
             ROOT / "configs/puf_baseline.json", ROOT / "pyproject.toml",
             ROOT / "requirements.txt"]
    for package in ("puf", "reconstruction"):
        paths.extend((ROOT / "src/python/puf_snn" / package).glob("*.py"))
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(paths)}


def git(*args):
    result = subprocess.run(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args], cwd=ROOT,
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def environment():
    # Read-only machine inventory; unavailable details are explicitly marked.
    hardware = {"model": "unavailable", "processor": platform.processor()}
    if os.name == "nt":
        try:
            result = subprocess.run([
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_ComputerSystem | "
                "Select-Object Manufacturer,Model,TotalPhysicalMemory | ConvertTo-Json -Compress",
            ], capture_output=True, text=True, check=True, timeout=10)
            hardware.update(json.loads(result.stdout))
            hardware["model"] = hardware["Model"]
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            hardware["inventory_error"] = str(error)
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "machine": platform.node(), "architecture": platform.machine(),
        "hardware": hardware, "operating_system": platform.platform(),
        "python": sys.version, "python_executable": sys.executable,
        "packages": {name: importlib.metadata.version(name)
                     for name in ("galois", "numpy", "numba", "llvmlite", "matplotlib")},
        "timing_method": "time.perf_counter_ns; reconstruct call only",
        "timer": vars(time.get_clock_info("perf_counter")),
        "timing_scope": "Windows Python software prototype; all legitimate outcomes",
    }


def load_plan(path):
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = {"experiment_version", "checkpoint", "simulation_seeds", "layer1_config",
                "credential_stream", "bootstrap_seed", "bootstrap_resamples"}
    require(set(plan) == expected, "Unexpected experiment configuration fields")
    require(plan["experiment_version"] == VERSION, "Wrong experiment version")
    require(plan["simulation_seeds"] == list(SEEDS), "The 20 cohort seeds are fixed")
    require(plan["credential_stream"] == CREDENTIAL_STREAM, "Credential stream is fixed")
    require(plan["layer1_config"] == "configs/puf_baseline.json", "Layer 1 config is fixed")
    for key in ("bootstrap_seed", "bootstrap_resamples"):
        require(type(plan[key]) is int and plan[key] >= (1 if key.endswith("resamples") else 0),
                f"Invalid {key}")
    config = load_config(ROOT / plan["layer1_config"])
    actual = asdict(config)
    actual.pop("random_seed")
    actual["noise_sweep"] = list(actual["noise_sweep"])
    require(actual == BASELINE, "Layer 1 settings differ from the frozen baseline")
    # A checkpoint alone is insufficient: source hashes preserve uncommitted work.
    git("merge-base", "--is-ancestor", plan["checkpoint"], "HEAD")
    return plan, config


def csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def prepare_cohort(config, archive):
    """Verify all generated bits AND sweep ordering against all 20 archives."""
    archives = inspect_runs(archive)
    _, _, baseline = analyze(archives)
    require(baseline["total_flips"] == 24634, "Baseline flip count changed")
    runs, provenance = [], []
    for saved in archives:
        tables = simulate(replace(config, random_seed=saved["seed"]))
        hashes = {}
        for name, rows in tables.items():
            path = saved["directory"] / f"{name}.csv"
            generated = hashlib.sha256(csv_bytes(rows)).hexdigest()
            require(generated == digest(path), f"Archive mismatch: {path}")
            hashes[path.name] = generated
        runs.append({"seed": saved["seed"], "tables": tables})
        provenance.append({"seed": saved["seed"], "archive": str(saved["directory"]),
                           "sha256": {**saved["sha256"], **hashes}})
    return runs, {"archive_validation": baseline, "runs": provenance}


def warm_up():
    """Fixed synthetic probes, separate from every experimental PUF/RNG stream."""
    start = time.perf_counter_ns()
    BCHCodec().initialize()
    initialized = time.perf_counter_ns()
    reference = tuple(index % 2 for index in range(64))
    helper = enroll(reference, bytes(4), enrollment_id="synthetic-warm-up")
    masks = [(), (0,), (0, 1, 2, 3, 4), tuple(range(6)),
             (31, 36, 37, 39, 40, 41), (35, 40, 41, 43, 44, 45)]
    outcomes = []
    for mask in masks:
        response = tuple(bit ^ int(i in mask) for i, bit in enumerate(reference))
        outcomes.append(reconstruct(response, helper, DEFAULT_CONFIG).outcome)
    return {"algebra_initialization_ns": initialized - start,
            "synthetic_warm_up_ns": time.perf_counter_ns() - initialized,
            "synthetic_probe_count": len(masks), "masks": masks, "outcomes": outcomes,
            "excludes_backend_import_time": True,
            "experimental_readings_consumed": 0}


def enroll_runs(runs):
    materials, records = {}, []
    for run in runs:
        for device in run["tables"]["devices"]:
            seed, device_id = run["seed"], device["device_id"]
            index = int(device_id.removeprefix("device-"))
            stream, credential = credential_for(seed, index)
            reference = bit_tuple(device["reference_response"])
            enrollment_id = f"{VERSION}:{seed}:{device_id}"
            helper = enroll(reference, credential, DEFAULT_CONFIG, enrollment_id=enrollment_id)
            require((seed, device_id) not in materials, "Duplicate enrollment identity")
            materials[seed, device_id] = (helper, reference, credential, stream)
            records.append({"simulation_seed": seed, "device_id": device_id,
                            "device_index": index, "enrollment_id": enrollment_id,
                            "credential_stream_identity": stream,
                            "helper63": "".join(map(str, helper.helper_bits)),
                            "evaluator_reference64": device["reference_response"],
                            "evaluator_enrolled_credential_hex": credential.hex()})
    return materials, records


def attempt_inputs(runs):
    # Complete the entire primary baseline before evaluating any sweep condition.
    for run in runs:
        for row in run["tables"]["metrics"]:
            yield run["seed"], row
    for index in sorted({row["sweep_index"] for run in runs
                         for row in run["tables"]["noise_sweep"]}):
        for run in runs:
            for row in run["tables"]["noise_sweep"]:
                if row["sweep_index"] == index:
                    yield run["seed"], row


def input_record(seed, row, material, source_id):
    helper, reference, _, stream = material
    response = bit_tuple(row["response"])
    errors64 = sum(a != b for a, b in zip(response, reference))
    errors63 = sum(a != b for a, b in zip(response[:63], reference[:63]))
    record = {
        "experiment_version": VERSION, "source_id": source_id,
        "simulation_seed": seed, "device_id": row["device_id"],
        "device_index": int(row["device_id"].removeprefix("device-")),
        "enrollment_id": helper.enrollment_id, "attempt_number": row["read_id"],
        "phase": row["phase"], "sweep_index": row["sweep_index"],
        "measurement_noise_std": row["measurement_noise_std"],
        "credential_stream_identity": stream, "response64": row["response"],
        "selected_response63": row["response"][:63],
        "evaluator_error_count64": errors64, "evaluator_error_count63": errors63,
        "evaluator_ber64": errors64 / 64, "evaluator_ber63": errors63 / 63,
    }
    return record, response


def evaluate_result(result, credential):
    """Called only AFTER reconstruction returns; no feedback path into decoding."""
    candidate = result.candidate_credential
    if result.outcome == "candidate_valid_format" and candidate is not None:
        success = candidate == credential
        evaluator = "evaluator_correct_match" if success else "evaluator_wrong_match"
    else:
        success, evaluator = False, "no_valid_candidate"
    return {
        "reconstruction_outcome": result.outcome, "decoder_status": result.decoder_status,
        "reported_correction_count": result.reported_correction_count,
        "candidate_message36": (None if result.candidate_message is None else
                                "".join(map(str, result.candidate_message))),
        "candidate_credential_hex": None if candidate is None else candidate.hex(),
        "padding_valid": result.padding_valid, "reconstruction_failure_reason": result.failure_reason,
        "evaluator_outcome": evaluator, "evaluator_success": success,
        "evaluator_failure_reason": (None if success else
                                     "credential_mismatch" if evaluator == "evaluator_wrong_match"
                                     else result.failure_reason),
        "backend_exception": None,
    }


def quantile(values, fraction):
    """Linear interpolation at (n-1)*q; also used for bootstrap percentiles."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def summarize(rows):
    require(bool(rows), "Cannot summarize empty observations")
    require(all(row["backend_exception"] is None for row in rows),
            "An exception is an incomplete run, not an FRR observation")
    n = len(rows)
    successes = sum(row["evaluator_success"] for row in rows)
    outcomes = Counter(row["reconstruction_outcome"] for row in rows)
    wrong = sum(row["evaluator_outcome"] == "evaluator_wrong_match" for row in rows)
    failures = n - successes
    require(failures == outcomes["decoder_failure"] + outcomes["invalid_format_or_padding"] + wrong,
            "Failure accounting does not reconcile")
    latency = [row["reconstruction_latency_ns"] for row in rows]
    return {
        "attempt_count": n, "success_count": successes, "failure_count": failures,
        "success_rate": successes / n, "frr": failures / n,
        "decoder_failures": outcomes["decoder_failure"],
        "invalid_format": outcomes["invalid_format_or_padding"], "miscorrections": wrong,
        "mean_ber63": sum(row["evaluator_error_count63"] for row in rows) / (63 * n),
        "mean_ber64": sum(row["evaluator_error_count64"] for row in rows) / (64 * n),
        "error_count_distribution": dict(sorted(Counter(
            row["evaluator_error_count63"] for row in rows).items())),
        "latency_sample_count": n, "latency_mean_ns": mean(latency),
        "latency_median_ns": median(latency), "latency_p95_ns": quantile(latency, 0.95),
        "latency_max_ns": max(latency),
    }


def grouped(rows, keys):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    return [{**dict(zip(keys, key)), **summarize(group)} for key, group in groups.items()]


def run_uncertainty(run_rows, seed, resamples):
    # Repeated experimental units are simulation runs, never individual reads.
    rng = Random(seed)
    n = len(run_rows)
    boot = []
    for _ in range(resamples):
        chosen = [run_rows[rng.randrange(n)] for _ in range(n)]
        boot.append(sum(r["failure_count"] for r in chosen) / sum(r["attempt_count"] for r in chosen))
    frrs = [row["frr"] for row in run_rows]
    return {"run_count": n, "mean_run_frr": mean(frrs),
            "sample_sd_run_frr": stdev(frrs) if n > 1 else None,
            "minimum_run_frr": min(frrs), "maximum_run_frr": max(frrs),
            "bootstrap_seed": seed, "bootstrap_resamples": resamples,
            "bootstrap_unit": "simulation run; all device/read observations retained",
            "bootstrap_method": "percentile 95%; linear quantile interpolation",
            "frr_ci95": [quantile(boot, 0.025), quantile(boot, 0.975)]}


def save_summaries(directory, rows, plan):
    condition = ("phase", "sweep_index", "measurement_noise_std")
    conditions = grouped(rows, condition)
    per_run = grouped(rows, (*condition, "simulation_seed"))
    per_device = grouped(rows, (*condition, "simulation_seed", "device_id"))
    errors = grouped(rows, (*condition, "evaluator_error_count63"))
    tables = {
        "baseline_summary": [r for r in conditions if r["phase"] == "baseline"],
        "noise_sweep_summary": [r for r in conditions if r["phase"] == "noise_sweep"],
        "per_run_summary": per_run, "per_device_summary": per_device,
        "error_count_summary": errors,
        "latency_summary": [{k: v for k, v in row.items()
                             if k in condition or k.startswith("latency_")} for row in conditions],
    }
    for name, table in tables.items():
        with (directory / f"{name}.csv").open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(table[0]))
            writer.writeheader()
            writer.writerows({k: json.dumps(v, sort_keys=True) if isinstance(v, dict) else v
                              for k, v in row.items()} for row in table)
    uncertainty = []
    for row in conditions:
        selected = [r for r in per_run if all(r[k] == row[k] for k in condition)]
        uncertainty.append({**{k: row[k] for k in condition}, **run_uncertainty(
            selected, plan["bootstrap_seed"], plan["bootstrap_resamples"])})
    summary = {"experiment_version": VERSION, "attempt_count": len(rows),
               "conditions": conditions, "run_uncertainty": uncertainty,
               "miscorrection_definition": "valid-format wrong credential; invalid padding separate",
               "independent_units": "20 simulation runs; 120 devices; repeated readings",
               "sweep_nominal_note": "noise=0.1 sweep uses later measurement RNG draws than baseline"}
    write_json(directory / "summary.json", summary)
    return summary


def attempt_key(row):
    return (row["simulation_seed"], row["device_id"], row["phase"],
            row["sweep_index"], row["attempt_number"])


def run_evaluation(directory, runs, plan, provenance):
    """Exclusive directory, flushed raw evidence, COMPLETE only after reconciliation."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    current = None
    completed = 0
    try:
        hashes = source_hashes()
        source_id = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
        write_json(directory / "config.json", {**plan, "reconstruction": asdict(DEFAULT_CONFIG),
                   "layer1_frozen_settings": BASELINE})
        metadata = {**environment(), "git_head": git("rev-parse", "HEAD"),
                    "git_status_before_run": git("status", "--short"),
                    "source_sha256": hashes, "source_id": source_id, **provenance}
        write_json(directory / "metadata.json", metadata)
        write_json(directory / "warm_up.json", warm_up())
        materials, enrollment_records = enroll_runs(runs)
        write_json(directory / "enrollments.json", enrollment_records)
        expected = {}
        for seed, row in attempt_inputs(runs):
            key = (seed, row["device_id"], row["phase"], row["sweep_index"], row["read_id"])
            require(key not in expected, f"Duplicate input reading: {key}")
            expected[key] = row["response"]
        with (directory / "attempts.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for seed, row in attempt_inputs(runs):
                material = materials[seed, row["device_id"]]
                current, response = input_record(seed, row, material, source_id)
                helper, _, credential, _ = material
                started = time.perf_counter_ns()
                try:
                    result = reconstruct(response, helper, DEFAULT_CONFIG)
                except BaseException as error:
                    elapsed = time.perf_counter_ns() - started
                    current.update(reconstruction_latency_ns=elapsed,
                                   backend_exception={"type": type(error).__name__, "message": str(error)},
                                   reconstruction_outcome="backend_exception",
                                   evaluator_outcome="not_evaluated", evaluator_success=None)
                    stream.write(json.dumps(current, sort_keys=True) + "\n")
                    stream.flush()
                    raise
                elapsed = time.perf_counter_ns() - started
                current.update(evaluate_result(result, credential))
                current["reconstruction_latency_ns"] = elapsed
                stream.write(json.dumps(current, sort_keys=True, allow_nan=False) + "\n")
                stream.flush()
                completed += 1
                if current["evaluator_error_count63"] <= 5 and not current["evaluator_success"]:
                    raise RuntimeError(
                        "Unexpected failure within t=5; retained evidence, stop for correctness review"
                    )
                if completed % 600 == 0:
                    print(f"Retained {completed}/{len(expected)} attempts", flush=True)
        # Summaries are made from evidence read BACK from disk, not parallel counters.
        with (directory / "attempts.jsonl").open(encoding="utf-8") as stream:
            rows = [json.loads(line) for line in stream]
        require(len(rows) == len(expected) == completed, "Incomplete attempt count")
        actual = {attempt_key(row): row["response64"] for row in rows}
        require(actual == expected and len(actual) == len(rows), "Reading identity mismatch")
        summary = save_summaries(directory, rows, plan)
        require(source_hashes() == hashes, "Source files changed during evaluation")
        artifacts = {path.name: digest(path) for path in sorted(directory.iterdir()) if path.is_file()}
        write_json(directory / "manifest.json", artifacts)
        write_json(directory / "COMPLETE", {"experiment_version": VERSION,
                   "attempt_count": completed, "source_id": source_id,
                   "manifest_sha256": digest(directory / "manifest.json")})
        return summary
    except BaseException as error:
        write_json(directory / "INCOMPLETE.json", {
            "completed_reconstructions": completed, "current_attempt": current,
            "error_type": type(error).__name__, "error": str(error),
            "traceback": traceback.format_exc(),
            "interpretation": "Incomplete experimental run; do not compute full-cohort FRR",
        })
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/reconstruction_experiment_v1.json")
    parser.add_argument("--archive", type=Path, default=ROOT / "sim_results")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Output already exists; evidence is never overwritten: {args.output}")
    plan, config = load_plan(args.config)
    print("Validating complete cohort and reproducing all archived CSVs...", flush=True)
    runs, provenance = prepare_cohort(config, args.archive)
    provenance["experiment_config_sha256"] = digest(args.config)
    summary = run_evaluation(args.output, runs, plan, provenance)
    print(json.dumps(summary["conditions"], indent=2))
    print(f"COMPLETE: {args.output}")


if __name__ == "__main__":
    main()
