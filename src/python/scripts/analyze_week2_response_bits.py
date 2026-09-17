"""Analyze the frozen, corrected Week 2 archives without running the simulator.

Only the Python standard library and matplotlib are required. All inputs are
validated before an output directory is created; existing outputs are refused.
Bit zero is the leftmost CSV character, corresponding to oscillator pair (0, 1).
"""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
from statistics import mean, median


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUN_NAMES = (
    "run-seed-1111-vpo3sh6h", "run-seed-1122-lgur9fjd",
    "run-seed-1234-v1xoukxp", "run-seed-2121-usfoatqu",
    "run-seed-2222-db2lx0kk", "run-seed-2391-03wppo_e",
    "run-seed-3232-wj3a0_6t", "run-seed-3333-l3mtfhzs",
    "run-seed-4321-r4669ysl", "run-seed-4433-6zxhrlva",
    "run-seed-4444-nu3ol6ct", "run-seed-5426-i67ho8lf",
    "run-seed-5555-d6jxf7n6", "run-seed-6543-kq_0si3y",
    "run-seed-6666-s33zjn8w", "run-seed-7654-ewr1xcke",
    "run-seed-7777-uzkvg0an", "run-seed-8231-9rst2dey",
    "run-seed-8888-j0tqcdu5", "run-seed-9999-at7p2ufs",
)
# These two archives are consulted ONLY to explain the historical BER figure.
EXCLUDED_NAMES = ("run-seed-1234-ud43sry0", "run-seed-4321-zf9zi47r")
BASELINE = {
    "number_of_devices": 6, "number_of_oscillators": 128,
    "pairing_scheme": "adjacent", "nominal_frequency": 100.0,
    "manufacturing_std": 1.0, "aging_std": 0.0, "repeated_reads": 100,
    "reference_conditions": {"environmental_offset": 0.0,
                             "measurement_noise_std": 0.0},
    "read_conditions": {"environmental_offset": 0.0,
                        "measurement_noise_std": 0.1},
    "noise_sweep": [0.0, 0.05, 0.1, 0.25, 0.5, 1.0],
}
BIT_COUNT = 64


def require(condition, message):
    if not condition:
        raise ValueError(message)


def close(actual, expected, context):
    require(math.isclose(float(actual), expected, rel_tol=0, abs_tol=1e-12),
            f"{context}: saved {actual}, recalculated {expected}")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        require(reader.fieldnames is not None
                and len(reader.fieldnames) == len(set(reader.fieldnames))
                and all(None not in row and None not in row.values() for row in rows),
                f"Malformed CSV: {path}")
        return rows


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bit_string(value, context):
    require(len(value) == BIT_COUNT and set(value) <= {"0", "1"},
            f"Expected a 64-character binary response: {context}")
    return value


def inspect_runs(archive):
    """Pin directory identity explicitly; never substitute a newer/older run."""
    runs = []
    for name in RUN_NAMES:
        directory = archive / name
        seed = int(name.split("-")[2])
        config = read_json(directory / "config.json")
        require(config == {**BASELINE, "random_seed": seed},
                f"Inconsistent configuration in {name}: {config}")
        require((directory / "COMPLETE").is_file(), f"Incomplete run: {name}")
        metadata = read_json(directory / "metadata.json")
        require(metadata["random_seed"] == seed
                and metadata["response_length"] == BIT_COUNT
                and metadata["rng_scheme"] == "week2-v1"
                and metadata["oscillator_pairs"] == [[i, i + 1] for i in range(0, 128, 2)],
                f"Inconsistent seed, response length, RNG or pair order: {name}")
        hashes = {p: digest(directory / p) for p in (
            "config.json", "metadata.json", "devices.csv", "metrics.csv",
            "summary.csv", "COMPLETE")}
        runs.append({"seed": seed, "directory": directory,
                     "metadata": metadata, "sha256": hashes})
    require(len(runs) == 20 and len({r["seed"] for r in runs}) == 20,
            "Expected 20 distinct seeds")
    require(len({json.dumps(r["metadata"]["source_sha256"], sort_keys=True)
                 for r in runs}) == 1, "Selected runs have different simulator sources")
    return runs


def analyze(runs):
    ones, flips, comparisons = ([0] * BIT_COUNT for _ in range(3))
    reference_count = read_count = 0
    saved_bers, run_rows = [], []
    for run in runs:
        directory = run["directory"]
        devices = read_csv(directory / "devices.csv")
        require(len(devices) == 6 and {d["device_id"] for d in devices}
                == {f"device-{i}" for i in range(6)}, f"Invalid devices: {directory}")
        references = {}
        for device in devices:
            device_id = device["device_id"]
            ref = bit_string(device["reference_response"], f"{directory}/{device_id}")
            require(int(device["response_length"]) == BIT_COUNT
                    and int(device["read_count"]) == 100, f"Invalid device counts: {directory}")
            close(device["uniformity"], ref.count("1") / BIT_COUNT, "Device uniformity")
            references[device_id] = ref
            reference_count += 1
            for index, value in enumerate(ref):
                ones[index] += int(value)

        metrics = read_csv(directory / "metrics.csv")
        require(len(metrics) == 600, f"Expected 600 baseline reads: {directory}")
        read_ids = {device_id: set() for device_id in references}
        device_flips = {device_id: 0 for device_id in references}
        for row in metrics:
            device_id, read_id = row["device_id"], int(row["read_id"])
            require(device_id in references, f"Unknown device: {directory}/{device_id}")
            require(read_id not in read_ids[device_id] and 0 <= read_id < 100,
                    f"Duplicate or invalid read ID: {directory}/{device_id}/{read_id}")
            read_ids[device_id].add(read_id)
            require(row["phase"] == "baseline" and row["sweep_index"] == ""
                    and float(row["measurement_noise_std"]) == 0.1
                    and int(row["response_length"]) == BIT_COUNT,
                    f"Non-baseline or invalid measurement: {directory}/{device_id}/{read_id}")
            response = bit_string(row["response"], f"{directory}/{device_id}/{read_id}")
            distance = 0
            for index, (observed, reference) in enumerate(zip(response, references[device_id])):
                mismatch = int(observed != reference)
                flips[index] += mismatch
                comparisons[index] += 1
                distance += mismatch
            require(int(row["hamming_distance"]) == distance, "Saved Hamming distance mismatch")
            close(row["ber"], distance / BIT_COUNT, "Read BER")
            close(row["reliability"], 1 - distance / BIT_COUNT, "Read reliability")
            saved_bers.append(float(row["ber"]))
            device_flips[device_id] += distance
            read_count += 1
        require(all(ids == set(range(100)) for ids in read_ids.values()),
                f"Incomplete device reads: {directory}")
        for device in devices:
            ber = device_flips[device["device_id"]] / (100 * BIT_COUNT)
            close(device["mean_ber"], ber, "Device mean BER")
            close(device["mean_reliability"], 1 - ber, "Device mean reliability")
        summary = read_csv(directory / "summary.csv")
        require(len(summary) == 1 and int(summary[0]["read_count"]) == len(metrics),
                f"Invalid run summary: {directory}")
        total_flips = sum(device_flips.values())
        run_ber = total_flips / (len(metrics) * BIT_COUNT)
        close(summary[0]["mean_ber"], run_ber, "Run mean BER")
        close(summary[0]["mean_reliability"], 1 - run_ber, "Run mean reliability")
        run_rows.append({"seed": run["seed"], "result_directory": f"sim_results/{directory.name}",
                         "device_count": len(devices), "baseline_read_count": len(metrics),
                         "flip_count": total_flips, "raw_ber": run_ber,
                         "saved_mean_ber": float(summary[0]["mean_ber"])})
    require(reference_count == 120 and read_count == 12000
            and set(comparisons) == {12000}, "Incomplete pooled data")
    rows = [{"bit_index": i, "reference_one_count": ones[i],
             "reference_response_count": reference_count,
             "reference_one_fraction": ones[i] / reference_count,
             "flip_count": flips[i], "comparison_count": comparisons[i],
             "flip_rate": flips[i] / comparisons[i]} for i in range(BIT_COUNT)]
    rates = [row["flip_rate"] for row in rows]
    raw_ber = sum(flips) / sum(comparisons)
    close(mean(rates), raw_ber, "Mean per-bit flip rate")
    close(mean(saved_bers), raw_ber, "Mean saved read BER")
    close(mean(r["saved_mean_ber"] for r in run_rows), raw_ber, "Mean saved run BER")
    summary = {
        "run_count": len(runs), "reference_response_count": reference_count,
        "total_noisy_reads": read_count, "comparisons_per_bit": comparisons[0],
        "total_bit_comparisons": sum(comparisons), "total_flips": sum(flips),
        "minimum_reference_one_fraction": min(ones) / reference_count,
        "maximum_reference_one_fraction": max(ones) / reference_count,
        "mean_reference_one_fraction": sum(ones) / (reference_count * BIT_COUNT),
        "most_biased_toward_zero": [i for i, value in enumerate(ones) if value == min(ones)],
        "most_biased_toward_one": [i for i, value in enumerate(ones) if value == max(ones)],
        "minimum_flip_rate": min(rates), "maximum_flip_rate": max(rates),
        "mean_flip_rate": mean(rates), "median_flip_rate": median(rates),
        "aggregate_raw_ber": raw_ber, "mean_saved_read_ber": mean(saved_bers),
        "mean_saved_run_ber": mean(r["saved_mean_ber"] for r in run_rows),
        "five_most_unstable": sorted(rows, key=lambda r: (-r["flip_count"], r["bit_index"]))[:5],
        "five_most_stable": sorted(rows, key=lambda r: (r["flip_count"], r["bit_index"]))[:5],
    }
    cutoff = summary["five_most_stable"][-1]["flip_count"]
    summary["stable_fifth_place_ties"] = [r["bit_index"] for r in rows if r["flip_count"] == cutoff]
    return rows, run_rows, summary


def historical_comparison(archive, run_rows):
    """Read excluded summary statistics separately; never pool their responses."""
    excluded = []
    for name in EXCLUDED_NAMES:
        directory = archive / name
        config = read_json(directory / "config.json")
        seed = int(name.split("-")[2])
        require(config == {**BASELINE, "number_of_devices": 10, "random_seed": seed},
                f"Unexpected legacy configuration: {name}")
        rows = read_csv(directory / "summary.csv")
        require(len(rows) == 1 and int(rows[0]["read_count"]) == 1000,
                f"Invalid legacy summary: {name}")
        excluded.append({"seed": seed, "result_directory": f"sim_results/{name}",
                         "device_count": 10, "reason": "Superseded 10-device run",
                         "saved_mean_ber": float(rows[0]["mean_ber"]),
                         "sha256": {p: digest(directory / p) for p in ("config.json", "summary.csv")}})
    mixed_mean = mean([r["saved_mean_ber"] for r in run_rows if r["seed"] not in (1234, 4321)]
                      + [r["saved_mean_ber"] for r in excluded])
    return {"excluded_runs": excluded, "historical_mixed_run_mean_ber": mixed_mean,
            "research_log_reported_ber_percent": 3.2271,
            "corrected_minus_historical_percentage_points":
                100 * (mean(r["raw_ber"] for r in run_rows) - mixed_mean)}


def write_csv(path, rows):
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def research_summary(s):
    unstable = ", ".join(f"{r['bit_index']} ({r['flip_rate']:.4%}; {r['flip_count']} flips)"
                         for r in s["five_most_unstable"])
    return [
        "The corrected Week 2 response-bit analysis used 20 archived runs with six simulated "
        "devices per run, 128 ROs per device, adjacent disjoint pairing and 64-bit responses. "
        "Manufacturing standard deviation was 1.0, baseline measurement-noise standard "
        "deviation was 0.1, and each device had 100 baseline reads. Enrollment was noiseless, "
        "environmental offsets were zero and aging was disabled. The selected seed 1234 and "
        "4321 directories were run-seed-1234-v1xoukxp and run-seed-4321-r4669ysl; their older "
        "10-device runs were excluded. Completeness checks confirmed 120 reference responses "
        "and 12,000 baseline noisy reads, providing 12,000 comparisons for each bit.",
        f"Across the 64 bit positions, reference-one fractions ranged from "
        f"{s['minimum_reference_one_fraction']:.6f} to {s['maximum_reference_one_fraction']:.6f} "
        f"({s['minimum_reference_one_fraction']:.4%} to {s['maximum_reference_one_fraction']:.4%}), "
        f"with a mean of {s['mean_reference_one_fraction']:.6f} "
        f"({s['mean_reference_one_fraction']:.4%}). Bit 56 was most biased toward zero "
        "(47/120 ones), and bit 15 was most biased toward one (73/120 ones). No position was "
        "near an all-zero or all-one population. These descriptive deviations from 0.5 do "
        "not establish systematic position bias: only 120 device references were sampled, "
        "and the extrema were selected across 64 positions.",
        f"Per-bit flip rates ranged from {s['minimum_flip_rate']:.4%} (bit 46; 184 flips) "
        f"to {s['maximum_flip_rate']:.4%} (bit 61; 637 flips), with mean "
        f"{s['mean_flip_rate']:.6%} and median {s['median_flip_rate']:.6%}. The five most "
        f"unstable positions were {unstable}. The five most stable positions, breaking ties "
        "by index, were 46 (184 flips; 1.5333%), 55 (239; 1.9917%), 43 (254; 2.1167%), "
        "50 (255; 2.1250%) and 13 (260; 2.1667%); bit 35 tied bit 13. The highest pooled "
        f"rate was {s['maximum_flip_rate'] / s['minimum_flip_rate']:.2f} times the lowest. "
        "This is appreciable sample variation, but does not show that these software "
        "positions are intrinsically less stable across new devices or seeds.",
        f"The {s['total_flips']:,} flips across {s['total_bit_comparisons']:,} bit comparisons "
        f"gave aggregate raw BER {s['aggregate_raw_ber']:.6%}, matching the mean per-bit "
        "rate, the mean saved read BER and the mean of the 20 selected run summaries. "
        "The research log's earlier 3.2271% is reproduced, after rounding, by the mean of "
        "the 18 unchanged run summaries and the two superseded 10-device summaries "
        f"({s['historical_mixed_run_mean_ber']:.6%}); the corrected value is "
        f"{abs(s['corrected_minus_historical_percentage_points']):.6f} percentage points lower. "
        "These results characterize balance and repeatability only for the archived synthetic "
        "baseline and verify metric consistency. Repeated reads share device-specific "
        "manufacturing variation, so 12,000 reads are not 12,000 independent device samples. "
        "Oscillator indices are software indices rather than physical chip locations; "
        "manufacturing and read-noise distributions are synthetic and enrollment is noiseless. "
        "The analysis cannot establish physical FPGA/ASIC behavior, environmental or aging "
        "robustness, bit independence, cryptographic entropy, physical PUF security or "
        "credential-reconstruction success.",
    ]


def plot_results(output, rows, summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 11, "axes.spines.top": False,
                         "axes.spines.right": False, "savefig.dpi": 300})
    for column, filename, title, ylabel, line, legend, limit in (
        ("reference_one_fraction", "response_bit_bias.png",
         "Simulated RO-PUF: response-bit reference balance",
         "Fraction of enrollment/reference responses equal to 1",
         0.5, "Balanced reference (0.5)", 1.0),
        ("flip_rate", "response_bit_instability.png",
         "Simulated RO-PUF: response-bit instability",
         "Repeated-read flip rate", summary["aggregate_raw_ber"],
         f"Aggregate raw BER = {summary['aggregate_raw_ber']:.6f} ({summary['aggregate_raw_ber']:.4%})",
         max(r["flip_rate"] for r in rows) * 1.25),
    ):
        fig, ax = plt.subplots(figsize=(11, 5.5), layout="constrained")
        ax.bar([r["bit_index"] for r in rows], [r[column] for r in rows],
               color="#315f82", width=0.72, zorder=3)
        ax.axhline(line, color="#222222", linewidth=1.4, linestyle="--", label=legend, zorder=4)
        ax.set(xlabel="Response bit index (0\u201363)", ylabel=ylabel,
               xlim=(-1, 64), ylim=(0, limit), xticks=[*range(0, 64, 4), 63])
        ax.set_title(title + "\n20 runs, 120 devices; " +
                     ("120 noiseless references per bit" if column == "reference_one_fraction"
                      else "12,000 baseline comparisons per bit; noise SD = 0.1"),
                     fontsize=13, loc="left", pad=12)
        ax.grid(axis="y", color="#dddddd", linewidth=0.7, zorder=0)
        ax.legend(loc="upper right", frameon=False, fontsize=9)
        fig.savefig(output / filename)
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", type=Path, default=PROJECT_ROOT / "sim_results")
    parser.add_argument("--output-dir", type=Path,
                        help="Must not exist; default is a new timestamped Week 2 directory")
    parser.add_argument("--validate-only", action="store_true", help="Check and analyze without writing")
    args = parser.parse_args()
    try:
        runs = inspect_runs(args.archive_dir)
        rows, run_rows, summary = analyze(runs)
        summary.update(historical_comparison(args.archive_dir, run_rows))
        # Detect changes during analysis before writing anything.
        for run in runs:
            require(all(digest(run["directory"] / p) == h for p, h in run["sha256"].items()),
                    f"Input changed during analysis: {run['directory']}")
        if args.validate_only:
            print(json.dumps(summary, indent=2))
            return
        import matplotlib
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = args.output_dir or (PROJECT_ROOT / "results" / "week-2" /
                                    f"response-bit-analysis-{timestamp}")
        require(not output.resolve().is_relative_to(args.archive_dir.resolve()),
                "Output must be outside the archived simulation directory")
        output.mkdir(parents=True, exist_ok=False)
        write_csv(output / "response_bit_analysis.csv", rows)
        write_csv(output / "selected_runs.csv", run_rows)
        manifest = {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "analysis_script": "src/python/scripts/analyze_week2_response_bits.py",
            "analysis_script_sha256": digest(Path(__file__)),
            "python": platform.python_version(), "matplotlib": matplotlib.__version__,
            "archive_directory": str(args.archive_dir.resolve()),
            "selection": "Explicit frozen directory list; missing runs cause failure, never substitution",
            "verified_configuration_except_seed": BASELINE,
            "bit_indexing": "Zero-based CSV character order; bit i compares ROs (2*i, 2*i+1)",
            "simulator_source_sha256": runs[0]["metadata"]["source_sha256"],
            "selected_runs": [{**row, "created_utc": run["metadata"]["created_utc"],
                               "code_revision": run["metadata"]["code_revision"],
                               "input_sha256": run["sha256"]} for run, row in zip(runs, run_rows)],
            "excluded_runs": summary["excluded_runs"],
            "checks": ["All selected configs identical except seed; exact adjacent pair order",
                       "Six distinct device IDs and 100 unique reads numbered 0-99 per device",
                       "All responses binary with length 64; only baseline phase at noise SD 0.1",
                       "Recomputed every saved read Hamming distance, BER and reliability",
                       "Reconciled device and run mean BER/reliability; checked reference uniformity",
                       "120 references; 12000 comparisons at every bit; saved input hashes unchanged"],
        }
        for filename, value in (("analysis_summary.json", summary), ("input_manifest.json", manifest)):
            with (output / filename).open("x", encoding="utf-8") as stream:
                json.dump(value, stream, indent=2, allow_nan=False)
                stream.write("\n")
        command = r".\.venv\Scripts\python.exe -B .\src\python\scripts\analyze_week2_response_bits.py"
        paragraphs = research_summary(summary)
        report = ["# Week 2 response-bit bias and stability", "",
                  "## RESEARCH LOG READY SUMMARY", "", "\n\n".join(paragraphs), "",
                  "## Verified run selection", "",
                  "All selected directories below are relative to the repository root. "
                  "The configuration, pair map and CSV contents were validated before output creation. "
                  "The full configuration and input SHA-256 hashes are in input_manifest.json. "
                  "Each selected run contributes six references and 600 baseline reads.", ""]
        report.extend(f"- Seed {r['seed']}: `{r['result_directory']}`" for r in run_rows)
        report += ["", "## Counting and interpretation", "",
                   "Bit indices are zero-based and follow the string order in devices.csv and metrics.csv: "
                   "bit i compares software oscillators (2i, 2i+1). Device IDs are scoped to their run; "
                   "device-0 from different seeds is never treated as the same device. Leading zeroes "
                   "are preserved. Each reference contributes once to bias; each baseline read "
                   "contributes once per bit to instability. Noise-sweep data are excluded, including "
                   "sweep reads with noise SD 0.1.", "",
                   "reference_one_fraction[i] = reference_one_count[i] / 120. "
                   "flip_rate[i] = flip_count[i] / 12000. Aggregate BER = total_flips / 768000. "
                   "All responses have 64 bits and each run and device contributes the same number "
                   "of reads, so pooled bit, read, device and run means agree. There is no weighting "
                   "difference within the corrected data. Historical excluded summaries are used "
                   "only for the separate BER discrepancy check, never for the 64-row output or plots.", "",
                   "No statistical significance or entropy claim is made. No threshold for 'strong' "
                   "bias or 'unusual' instability was specified in advance. The reported extrema and "
                   "rankings describe this sample. Establishing persistent position effects would "
                   "require additional independent device samples and an analysis accounting for "
                   "device-level heterogeneity and selection across 64 positions.", "",
                   "## Reproduce", "", "From the repository root, using the existing environment:", "",
                   "```powershell", command, "```", "",
                   "The command creates a new timestamped directory under results/week-2/. "
                   "Use --output-dir with a new path to choose the destination, or --validate-only "
                   "to compute and check without writing. An existing destination is refused. "
                   "No simulator functions are imported or called; no simulations are regenerated.", ""]
        with (output / "README.md").open("x", encoding="utf-8") as stream:
            stream.write("\n".join(report))
        plot_results(output, rows, summary)
        print(f"Results saved: {output.resolve()}")
        print(f"120 references; 12000 noisy reads; {summary['total_flips']} flips / 768000 bit comparisons")
        print(f"Aggregate raw BER: {summary['aggregate_raw_ber']:.9%}")
    except (OSError, ValueError, KeyError, ImportError) as error:
        parser.exit(2, f"Analysis stopped: {error}\n")


if __name__ == "__main__":
    main()
