"""Exploratory Layer 2 evaluation of one saved Layer 1 baseline (no simulation)."""

import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/python"))

from puf_snn.puf.variables import load_config
from puf_snn.reconstruction import DEFAULT_CONFIG, enroll, reconstruct
from scripts.analyze_week2_response_bits import digest, read_csv, require
from scripts.run_reconstruction import (
    CREDENTIAL_STREAM, bit_tuple, credential_for, environment, evaluate_result,
    git, grouped, input_record, source_hashes as experiment_source_hashes,
    summarize, write_json,
)

VERSION = "layer2-single-run-v1"
OUTPUT_ROOT = ROOT / "results/week-4/will/reconstruction"
INPUT_FILES = ("COMPLETE", "config.json", "metadata.json", "devices.csv", "metrics.csv")


def input_hashes(directory):
    return {name: digest(directory / name) for name in INPUT_FILES}


def load_saved_run(directory):
    """Validate saved baseline completeness and identities without generating bits.

    COMPLETE is the Layer 1 writer's completion contract. Sweep/plot data are
    outside this baseline-only workflow and are never used as reconstruction inputs.
    """
    directory = Path(directory).resolve()
    try:
        hashes = input_hashes(directory)
        require((directory / "COMPLETE").read_text(encoding="utf-8").strip()
                == "Experiment completed.", "Invalid Layer 1 COMPLETE marker")
        completed_ns = (directory / "COMPLETE").stat().st_mtime_ns
        config = load_config(directory / "config.json")
        require(config.pairing_scheme == "adjacent" and config.number_of_oscillators == 128,
                "Layer 2 requires the saved 64-bit adjacent-pair Layer 1 response")
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        require(isinstance(metadata, dict), "Invalid Layer 1 metadata")
        require(metadata.get("random_seed") == config.random_seed
                and metadata.get("response_length") == 64
                and metadata.get("rng_scheme") == "week2-v1"
                and metadata.get("oscillator_pairs") == [[i, i + 1] for i in range(0, 128, 2)],
                "Inconsistent Layer 1 seed, response length, RNG or pair order")
        devices = read_csv(directory / "devices.csv")
        readings = read_csv(directory / "metrics.csv")
        expected_devices = {f"device-{i}" for i in range(config.number_of_devices)}
        require(len(devices) == len(expected_devices)
                and {row["device_id"] for row in devices} == expected_devices,
                "Missing, duplicate or unexpected device enrollment")
        for row in devices:
            bit_tuple(row["reference_response"])
            require(int(row["response_length"]) == 64
                    and int(row["read_count"]) == config.repeated_reads,
                    "Invalid device response length or read count")
        expected_count = config.number_of_devices * config.repeated_reads
        require(len(readings) == expected_count, "Incomplete baseline reading count")
        identities = set()
        for row in readings:
            bit_tuple(row["response"])
            row["read_id"] = int(row["read_id"])
            row["measurement_noise_std"] = float(row["measurement_noise_std"])
            identity = (row["device_id"], row["read_id"])
            require(row["phase"] == "baseline" and row["sweep_index"] == "",
                    "metrics.csv must contain only baseline readings")
            require(int(row["response_length"]) == 64
                    and row["measurement_noise_std"] == config.read_conditions.measurement_noise_std,
                    "Reading response length or noise differs from saved configuration")
            require(row["device_id"] in expected_devices
                    and 0 <= row["read_id"] < config.repeated_reads
                    and identity not in identities, "Invalid or duplicate reading identity")
            identities.add(identity)
        require(input_hashes(directory) == hashes
                and (directory / "COMPLETE").stat().st_mtime_ns == completed_ns,
                "Layer 1 inputs changed while loading")
        return {"directory": directory, "seed": config.random_seed, "config": asdict(config),
                "metadata": metadata, "sha256": hashes, "completed_ns": completed_ns,
                "devices": devices, "readings": readings}
    except PermissionError as error:
        raise PermissionError(f"Cannot read Layer 1 run {directory}: {error}") from error
    except (ValueError, KeyError, TypeError, FileNotFoundError, NotADirectoryError) as error:
        raise ValueError(f"Invalid or incomplete Layer 1 run {directory}: {error}") from error


def select_run(input_run=None, archive=None):
    """Explicit input wins. Otherwise select the unique latest valid completion."""
    if input_run is not None:
        return load_saved_run(input_run)
    archive = Path(archive) if archive is not None else ROOT / "sim_results"
    require(archive.is_dir(), f"Layer 1 archive not found: {archive}; run .\\run_simulation.ps1 first")
    valid, rejected = [], []
    for directory in sorted(archive.iterdir()):
        if not directory.is_dir():
            continue
        try:
            valid.append(load_saved_run(directory))
        except ValueError as error:
            rejected.append(str(error))
    for reason in rejected:
        print(f"Skipping {reason}", file=sys.stderr)
    require(bool(valid), f"No valid completed Layer 1 run in {archive}; run .\\run_simulation.ps1 first")
    latest_ns = max(run["completed_ns"] for run in valid)
    latest = [run for run in valid if run["completed_ns"] == latest_ns]
    require(len(latest) == 1, "Ambiguous latest Layer 1 completion timestamps; use -InputRun: "
            + ", ".join(str(run["directory"]) for run in latest))
    return latest[0]


def output_path(run, name=None):
    if name is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        name = f"{VERSION}-seed-{run['seed']}-{timestamp}-{uuid4().hex[:8]}"
    require(bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name))
            and not name.endswith("."), "OutputName must be a single directory name, not a path")
    base = OUTPUT_ROOT.resolve()
    output = base / name
    require(output.resolve().parent == base, "Output must remain under the reconstruction directory")
    return output


def source_hashes():
    hashes = experiment_source_hashes()
    for path in (Path(__file__), ROOT / "run_layer2.ps1"):
        hashes[path.relative_to(ROOT).as_posix()] = digest(path)
    return hashes


def write_csv(path, rows):
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({key: json.dumps(value, sort_keys=True) if isinstance(value, dict) else value
                          for key, value in row.items()} for row in rows)


def run_single(run, name=None):
    directory = output_path(run, name)
    require(not directory.exists(), f"Output already exists; never overwritten: {directory}")
    require(input_hashes(run["directory"]) == run["sha256"], "Layer 1 inputs changed after loading")
    directory.mkdir(parents=True, exist_ok=False)
    current, completed = None, 0
    try:
        hashes = source_hashes()
        source_id = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
        try:
            revision = git("rev-parse", "HEAD")
        except (OSError, subprocess.SubprocessError):
            revision = None
        write_json(directory / "metadata.json", {
            **environment(), "workflow_version": VERSION,
            "result_kind": "exploratory/single-run", "reading_scope": "metrics.csv baseline only",
            "layer1_run_path": str(run["directory"]), "layer1_seed": run["seed"],
            "layer1_config": run["config"], "layer1_metadata": run["metadata"],
            "layer1_input_sha256": run["sha256"], "layer1_complete_mtime_ns": run["completed_ns"],
            "layer2_config": asdict(DEFAULT_CONFIG), "credential_stream": CREDENTIAL_STREAM,
            "source_sha256": hashes, "source_id": source_id, "git_head": revision,
            "timing_note": "No warm-up or extra reconstruction calls; first decode includes cold-start compilation",
            "interpretation": "Exploratory single run; not the formal 20-seed experiment or its confidence interval",
        })
        materials, enrollments = {}, []
        for device in run["devices"]:
            device_id = device["device_id"]
            index = int(device_id.removeprefix("device-"))
            stream, credential = credential_for(run["seed"], index)
            reference = bit_tuple(device["reference_response"])
            helper = enroll(reference, credential, DEFAULT_CONFIG,
                            enrollment_id=f"{VERSION}:{run['seed']}:{device_id}")
            materials[device_id] = (helper, reference, credential, stream)
            enrollments.append({"device_id": device_id, "credential_stream_identity": stream,
                                "enrollment_id": helper.enrollment_id,
                                "helper63": "".join(map(str, helper.helper_bits)),
                                "evaluator_reference64": device["reference_response"],
                                "evaluator_enrolled_credential_hex": credential.hex()})
        write_json(directory / "enrollments.json", enrollments)
        with (directory / "attempts.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for reading in run["readings"]:
                material = materials[reading["device_id"]]
                helper, _, credential, _ = material
                response = bit_tuple(reading["response"])
                current = {"device_id": reading["device_id"], "attempt_number": reading["read_id"],
                           "response64": reading["response"]}
                started = time.perf_counter_ns()
                try:
                    result = reconstruct(response, helper, DEFAULT_CONFIG)
                except BaseException as error:
                    current.update(reconstruction_latency_ns=time.perf_counter_ns() - started,
                                   backend_exception={"type": type(error).__name__, "message": str(error)},
                                   evaluator_success=None)
                    stream.write(json.dumps(current, sort_keys=True) + "\n")
                    stream.flush()
                    raise
                elapsed = time.perf_counter_ns() - started
                # The shared record builder computes ground-truth distances: AFTER decoding only.
                current, _ = input_record(run["seed"], reading, material, source_id)
                current.pop("experiment_version")
                current.update(workflow_version=VERSION, result_kind="exploratory/single-run",
                               reconstruction_latency_ns=elapsed,
                               **evaluate_result(result, credential))
                stream.write(json.dumps(current, sort_keys=True, allow_nan=False) + "\n")
                stream.flush()
                completed += 1
        rows = [json.loads(line) for line in (directory / "attempts.jsonl").read_text().splitlines()]
        expected = [(r["device_id"], r["read_id"], r["response"]) for r in run["readings"]]
        require([(r["device_id"], r["attempt_number"], r["response64"]) for r in rows] == expected,
                "Saved attempt identities do not reconcile with Layer 1")
        summary = {"workflow_version": VERSION, "result_kind": "exploratory/single-run",
                   "reading_scope": "metrics.csv baseline only", **summarize(rows)}
        devices = grouped(rows, ("device_id",))
        errors = sorted(grouped(rows, ("evaluator_error_count63",)),
                        key=lambda r: r["evaluator_error_count63"])
        for groups in (devices, errors):
            for key in ("attempt_count", "success_count", "failure_count"):
                require(sum(row[key] for row in groups) == summary[key], "Summary totals do not reconcile")
        write_json(directory / "summary.json", summary)
        write_csv(directory / "per_device.csv", devices)
        write_csv(directory / "error_count.csv", errors)
        write_csv(directory / "latency_summary.csv", [
            {key: value for key, value in summary.items() if key.startswith("latency_")}])
        require(input_hashes(run["directory"]) == run["sha256"], "Layer 1 inputs changed during evaluation")
        require(source_hashes() == hashes, "Source files changed during evaluation")
        write_json(directory / "COMPLETE", {"workflow_version": VERSION, "attempt_count": completed})
        return directory, summary, devices, errors
    except BaseException as error:
        write_json(directory / "INCOMPLETE.json", {
            "completed_reconstructions": completed, "current_attempt": current,
            "error": str(error), "traceback": traceback.format_exc(),
            "interpretation": "Incomplete run; do not use any partial summary as full-run FRR",
        })
        raise


def print_summary(run, directory, summary, devices, errors):
    print("\n" + "-" * 50 + "\nLAYER 2 CREDENTIAL RECONSTRUCTION\n" + "-" * 50)
    print("Exploratory / single-run baseline results (not formal 20-seed evidence)")
    print(f"\nSource Layer 1 Run: {run['directory']}\nSeed: {run['seed']}")
    print(f"Devices: {len(devices)}\nReadings per Device: {run['config']['repeated_reads']}")
    print("\nBCH: BCH(63,36,t=5)\n\nOVERALL")
    for label, key in (("Attempts", "attempt_count"), ("Successful Reconstructions", "success_count"),
                       ("Failed Reconstructions", "failure_count")):
        print(f"{label}: {summary[key]}")
    print(f"Success Rate: {summary['success_rate']:.4%}\nFRR: {summary['frr']:.4%}")
    print(f"Decoder Failures: {summary['decoder_failures']}\nInvalid Padding: {summary['invalid_format']}")
    print(f"Valid-Format Wrong Credentials: {summary['miscorrections']}")
    print(f"Selected 63-bit BER: {summary['mean_ber63']:.6%}\n\nPER DEVICE")
    for row in devices:
        print(f"{row['device_id']}:\n    Attempts: {row['attempt_count']}\n    Successes: {row['success_count']}"
              f"\n    Failures: {row['failure_count']}\n    FRR: {row['frr']:.4%}"
              f"\n    Mean BER63: {row['mean_ber63']:.6%}")
    print("\nERROR COUNT\nErrors | Attempts | Successes | Failures | Success Rate")
    for row in errors:
        print(f"{row['evaluator_error_count63']:6} | {row['attempt_count']:8} | {row['success_count']:9}"
              f" | {row['failure_count']:8} | {row['success_rate']:.4%}")
    print("\nLATENCY (reconstruct call only; includes first-decode cold start)")
    for label, key in (("Mean", "mean"), ("Median", "median"), ("p95", "p95"), ("Maximum", "max")):
        print(f"{label}: {summary[f'latency_{key}_ns'] / 1_000_000:.6f} ms")
    print(f"Samples: {summary['latency_sample_count']}\n\nSaved results:\n{directory}")


def print_compact_summary(run, directory, summary):
    print("Exploratory single-run result")
    print(f"Source Layer 1 Run: {run['directory']}\nSeed: {run['seed']}")
    print(f"Attempts: {summary['attempt_count']}")
    print(f"Successes / Failures: {summary['success_count']} / {summary['failure_count']}")
    print(f"Success Rate: {summary['success_rate']:.4%}\nFRR: {summary['frr']:.4%}")
    print(f"Selected BER63: {summary['mean_ber63']:.6%}")
    print(f"Decoder Failures / Invalid Padding / Wrong Credentials: "
          f"{summary['decoder_failures']} / {summary['invalid_format']} / {summary['miscorrections']}")
    print(f"p95 Reconstruction Latency: {summary['latency_p95_ns'] / 1_000_000:.6f} ms")
    print(f"Saved results: {directory}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-run", type=Path, help="Explicit saved Layer 1 run; overrides latest selection")
    parser.add_argument("--output-name", help="New directory name under results/week-4/will/reconstruction")
    parser.add_argument("--verbose-results", action="store_true", help="Print detailed device, error-count and latency tables")
    args = parser.parse_args(argv)
    try:
        run = select_run(args.input_run)
        if args.verbose_results:
            print(f"Evaluating saved baseline: {run['directory']} (BCH startup may take a moment)", flush=True)
        directory, summary, devices, errors = run_single(run, args.output_name)
        if args.verbose_results:
            print_summary(run, directory, summary, devices, errors)
        else:
            print_compact_summary(run, directory, summary)
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        parser.exit(2, f"Layer 2: {error}\n")


if __name__ == "__main__":
    main()
