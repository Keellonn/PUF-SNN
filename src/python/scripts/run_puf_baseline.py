import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
from random import Random
from statistics import mean, pstdev
import subprocess
import sys
import tempfile
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))

from puf_snn.puf.device import Device, create_device
from puf_snn.puf.metrics import (
    hamming_distance, pairwise_uniqueness, raw_ber, uniformity,
)
from puf_snn.puf.ro_puf import (
    OscillatorPairs, Response, generate_pairs, generate_response,
)
from puf_snn.puf.variables import ExperimentConfig, ReadConditions, load_config

def make_rng(
    random_seed: int,
    device_index: int,
    phase: Literal["manufacturing", "enrollment", "measurement"],
) -> Random:
    """Creates a stable device/phase stream once, then reuse it for reads."""
    if type(random_seed) is not int or random_seed < 0:
        raise ValueError("random_seed must be a nonnegative integer")
    if type(device_index) is not int or device_index < 0:
        raise ValueError("device_index must be a nonnegative integer")
    if phase not in ("manufacturing", "enrollment", "measurement"):
        raise ValueError("Unknown RNG phase")
    rng = Random()
    rng.seed(f"week2-v1:{random_seed}:{device_index}:{phase}", version=2)
    return rng

def collect_reads(
    config: ExperimentConfig, devices: list[Device],
    references: list[Response],
    pairs: OscillatorPairs, rngs: list[Random], conditions: ReadConditions,
    phase: str, sweep_index: int | str,
) -> list[dict]:
    """Retain each same-device observation; never resample device identity."""
    rows = []
    for device, reference, rng in zip(devices, references, rngs):
        for read_index in range(config.repeated_reads):
            response = generate_response(
                device, pairs, config.nominal_frequency, conditions, rng=rng
            )
            # BER always compares to this device's enrolled reference.
            ber = raw_ber(reference, response)
            rows.append({
                "phase": phase, "sweep_index": sweep_index,
                "device_id": device.device_id, "read_id": read_index,
                "measurement_noise_std": conditions.measurement_noise_std,
                "response_length": len(pairs),
                "hamming_distance": hamming_distance(reference, response),
                "ber": ber, "reliability": 1.0 - ber,
                "response": "".join(map(str, response)),
            })
    return rows

def summarize_reads(rows: list[dict]) -> dict:
    """Equal-weight read mean and descriptive population spread, not a CI."""
    bers = [row["ber"] for row in rows]
    average = mean(bers)
    return {"read_count": len(rows), "mean_ber": average,
            "mean_reliability": 1.0 - average, "ber_std": pstdev(bers),
            "min_ber": min(bers), "max_ber": max(bers)}

def simulate(config: ExperimentConfig) -> dict[str, list[dict]]:
    """Run baseline then sweep in configured order with continuing RNGs."""
    pairs = generate_pairs(config.number_of_oscillators, config.pairing_scheme)
    devices = [create_device(
        f"device-{index}", config.number_of_oscillators,
        config.manufacturing_std,
        rng=make_rng(config.random_seed, index, "manufacturing"),
    ) for index in range(config.number_of_devices)]
    references = [generate_response(
        device, pairs, config.nominal_frequency, config.reference_conditions,
        rng=make_rng(config.random_seed, index, "enrollment"),
    ) for index, device in enumerate(devices)]
    rngs = [make_rng(config.random_seed, index, "measurement")
            for index in range(config.number_of_devices)]
    baseline = collect_reads(config, devices, references, pairs, rngs,
                             config.read_conditions, "baseline", "")
    sweep_rows = []
    sweep_summary = []
    for index, noise in enumerate(config.noise_sweep):
        conditions = ReadConditions(
            config.read_conditions.environmental_offset, noise
        )
        rows = collect_reads(config, devices, references, pairs, rngs,
                             conditions, "noise_sweep", index)
        sweep_rows.extend(rows)
        sweep_summary.append({"sweep_index": index,
                              "measurement_noise_std": noise,
                              **summarize_reads(rows)})
    device_rows = []
    for device, reference in zip(devices, references):
        rows = [row for row in baseline
                if row["device_id"] == device.device_id]
        device_rows.append({"device_id": device.device_id,
                            "response_length": len(pairs),
                            "reference_response": "".join(map(str, reference)),
                            "uniformity": uniformity(reference),
                            **summarize_reads(rows)})
    pair_rows = [{
        "device_a": devices[first].device_id,
        "device_b": devices[second].device_id,
        "response_length": len(pairs),
        "hamming_distance": hamming_distance(
            references[first], references[second]
        ),
        "normalized_hamming_distance": distance,
    } for first, second, distance in pairwise_uniqueness(references)]
    return {
        "metrics": baseline, "devices": device_rows,
        "uniqueness_pairs": pair_rows, "noise_sweep": sweep_rows,
        "noise_sweep_summary": sweep_summary,
        "summary": [{**summarize_reads(baseline),
                     "mean_uniqueness": mean(
                         row["normalized_hamming_distance"]
                         for row in pair_rows
                     ), "device_pair_count": len(pair_rows)}],
    }

def save_tables(directory: Path, tables: dict[str, list[dict]]) -> None:
    """Write complete observation tables with explicit column names."""
    for name, rows in tables.items():
        path = directory / f"{name}.csv"
        with path.open("x", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

def plot_results(directory: Path, tables: dict[str, list[dict]]) -> None:
    """Plot saved-table values; plotting consumes no random samples."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    directory.mkdir()
    same = [row["ber"] for row in tables["metrics"]]
    different = [row["normalized_hamming_distance"]
                 for row in tables["uniqueness_pairs"]]
    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    bins = [index / 20 for index in range(21)]
    # Each distribution sums to one despite different observation counts.
    for values, label in (
        (same, "Same device: baseline read vs own reference"),
        (different, "Different devices: unordered reference pairs"),
    ):
        ax.hist(values, bins=bins, weights=[1 / len(values)] * len(values),
                alpha=0.6, label=f"{label} (n={len(values)})")
    ax.set(xlabel="Normalized Hamming distance",
           ylabel="Fraction of observations",
           title="Same-device and inter-device distances", xlim=(0, 1))
    ax.legend(fontsize=8)
    fig.savefig(directory / "hamming_distributions.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    rows = tables["noise_sweep_summary"]
    # Preserve duplicates and nonmonotonicity in measured points.
    ax.scatter([row["measurement_noise_std"] for row in rows],
               [row["mean_ber"] for row in rows])
    ax.set(xlabel="Measurement-noise standard deviation (abstract units)",
           ylabel="Mean raw BER (fraction)", ylim=(0, 1),
           title="Noise sweep: pooled same-device reads vs fixed references")
    ax.grid(alpha=0.25)
    fig.savefig(directory / "ber_vs_noise.png", dpi=160)
    plt.close(fig)

    rows = tables["devices"]
    fig, ax = plt.subplots(figsize=(max(9, len(rows) * 0.35), 5),
                           layout="constrained")
    ax.bar([row["device_id"] for row in rows],
           [row["uniformity"] for row in rows])
    ax.axhline(0.5, color="black", linestyle="--",
               label="Balanced reference (0.5)")
    ax.set(ylabel="Fraction of reference bits equal to 1", ylim=(0, 1),
           xlabel="Device", title="Enrollment-response uniformity by device")
    ax.tick_params(axis="x", rotation=60)
    ax.legend()
    fig.savefig(directory / "uniformity_by_device.png", dpi=160)
    plt.close(fig)

def save_metadata(directory: Path, config: ExperimentConfig) -> None:
    """Record exact settings, pair order, runtime, and source fingerprints."""
    (directory / "config.json").write_text(
        json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8"
    )
    source_paths = sorted(
        (PROJECT_ROOT / "src" / "python" / "puf_snn" / "puf").glob("*.py")
    )
    source_paths.append(Path(__file__).resolve())
    source_paths.append(PROJECT_ROOT / "requirements.txt")
    fingerprints = {str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(
        path.read_bytes()).hexdigest() for path in source_paths}
    try:
        result = subprocess.run(
            ["git", "-c", f"safe.directory={PROJECT_ROOT.as_posix()}",
             "rev-parse", "HEAD"], cwd=PROJECT_ROOT,
            capture_output=True, text=True, check=False,
        )
        revision = result.stdout.strip() if result.returncode == 0 else None
    except OSError:
        revision = None
    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "random_seed": config.random_seed, "rng_scheme": "week2-v1",
        "draw_order": "device streams; baseline then configured sweep order",
        "python": platform.python_version(), "platform": platform.platform(),
        "dependencies": {dist.metadata["Name"]: dist.version
                         for dist in importlib.metadata.distributions()},
        "code_revision": revision, "source_sha256": fingerprints,
        "response_length": len(generate_pairs(
            config.number_of_oscillators, config.pairing_scheme)),
        "oscillator_pairs": generate_pairs(
            config.number_of_oscillators, config.pairing_scheme),
        "units": "abstract frequency units; metrics are fractions",
        "aggregation": "equal-weight means; ber_std is population SD",
    }
    (directory / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )

def run_baseline(config: ExperimentConfig, output_directory: Path) -> Path:
    """Save an isolated run; COMPLETE marks successful CSV and plots."""
    tables = simulate(config)
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(
        prefix=f"run-seed-{config.random_seed}-", dir=output_directory
    ))
    save_metadata(directory, config)
    save_tables(directory, tables)
    plot_results(directory / "plots", tables)
    (directory / "COMPLETE").write_text(
        "Experiment completed.\n", encoding="utf-8"
    )
    return directory

def main() -> None:
    """Validate configuration or run the complete baseline experiment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path,
                        default=PROJECT_ROOT / "configs" / "puf_baseline.json")
    parser.add_argument("--output-dir", type=Path,
                        default=PROJECT_ROOT / "sim_results")
    parser.add_argument("--validate-config", action="store_true")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        if args.validate_config:
            print(f"Configuration valid: {args.config}")
            return
        print(f"Results saved: {run_baseline(config, args.output_dir)}")
    except (OSError, ValueError, ImportError) as error:
        parser.exit(2, f"{error}\n")

if __name__ == "__main__":
    main()
