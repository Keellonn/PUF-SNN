"""
this script creates the evidence that supports the synthetic-data report
it
- reads the saved dataset and checks it against the schema and pilot settings
- counts every class by device and session and reports sample-quality failures
- lists every split's window, trial, source-trial, session, and device identifiers
- checks prohibited overlap and explains the intentional overlap of device groups
- compares the saved data with regeneration using the recorded configuration
- optionally runs the data and split tests and saves each actual outcome
- saves one synthetic sample window, two figures, and json and markdown evidence

the figures show scripted motion and group differences, not measured headset effects
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import platform
import subprocess
import sys
import unittest
from collections import Counter, defaultdict
from importlib.metadata import PackageNotFoundError, version
from itertools import combinations
from pathlib import Path

import matplotlib

# save figures without opening tkinter or another desktop plotting backend
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src" / "python"))

from puf_snn.data.generator import generate_records
from puf_snn.data.validation import make_schema_validator, validate_jsonl, validate_record


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def file_hash(path: Path) -> str:
    # identify the exact bytes used in the experiment
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(arguments: list[str]) -> str:
    # git failures should be recorded instead of invented commit information
    try:
        result = subprocess.run(
            ["git", *arguments], cwd=ROOT, check=True,
            capture_output=True, text=True,
        )
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "unavailable"


def package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not installed"


def save_json(path: Path, value: dict) -> None:
    # readable json is used for reports and the single example window
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


class EvidenceTestResult(unittest.TextTestResult):
    # keep the purpose and observed outcome of each test in the evidence json
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.outcomes = {}

    def startTest(self, test):
        super().startTest(test)
        self.outcomes[test.id()] = {
            "test": test.id(),
            "purpose": test.shortDescription() or test.id(),
            "expected": "all assertions pass, including the specified rejection checks",
            "actual": "started",
            "details": [],
        }

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes[test.id()]["actual"] = "passed"

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.outcomes[test.id()]["actual"] = "failed"
        self.outcomes[test.id()]["details"].append(self._exc_info_to_string(error, test))

    def addError(self, test, error):
        super().addError(test, error)
        self.outcomes[test.id()]["actual"] = "error"
        self.outcomes[test.id()]["details"].append(self._exc_info_to_string(error, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.outcomes[test.id()]["actual"] = "skipped"
        self.outcomes[test.id()]["details"].append(reason)

    def addSubTest(self, test, subtest, error):
        super().addSubTest(test, subtest, error)
        if error is not None:
            self.outcomes[test.id()]["actual"] = "failed"
            self.outcomes[test.id()]["details"].append(self._exc_info_to_string(error, test))


def run_data_tests() -> dict:
    # tests run only when the user requests --run-tests
    suite = unittest.TestSuite()
    for pattern in ("test_data.py", "test_splits.py"):
        loader = unittest.TestLoader()
        suite.addTests(loader.discover(str(ROOT / "tests"), pattern=pattern))

    captured_output = io.StringIO()
    result = unittest.TextTestRunner(
        stream=captured_output, verbosity=2, resultclass=EvidenceTestResult,
    ).run(suite)
    transcript = captured_output.getvalue()
    print(transcript)

    return {
        "status": "passed" if result.wasSuccessful() and not result.skipped and result.testsRun > 0 else "needs_review",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "results": list(result.outcomes.values()),
        "transcript": transcript,
    }


def split_evidence(records: list[dict]) -> tuple[dict, list[dict]]:
    # full identifier lists make the zero overlap claim inspectable
    identifiers = {}
    fields = ("window_id", "source_trial_id", "trial_id", "session_id", "device_id")

    for split in ("train", "validation", "test"):
        group = [record for record in records if record["split"] == split]
        identifiers[split] = {
            field: sorted({record[field] for record in group})
            for field in fields
        }
        # there are no human participants or separate profile records in this generator
        identifiers[split]["participant_id"] = []
        identifiers[split]["profile_id"] = list(identifiers[split]["device_id"])

    overlap = []
    for left, right in combinations(identifiers, 2):
        for field in (*fields, "participant_id", "profile_id"):
            shared = sorted(set(identifiers[left][field]) & set(identifiers[right][field]))
            overlap.append({
                "left_split": left,
                "right_split": right,
                "field": field,
                "prohibited": field not in ("device_id", "profile_id", "participant_id"),
                "shared_count": len(shared),
                "shared_identifiers": shared,
            })

    return identifiers, overlap


def motion_arrays(record: dict, axis_name: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # signed axis angle is for these single-axis synthetic figures only
    samples = record["samples"]
    times = np.asarray([
        (sample["capture_time_ns"] - record["window_start_ns"]) / 1_000_000_000
        for sample in samples
    ])
    positions = np.asarray([sample["position_m"] for sample in samples])
    quaternions = np.asarray([sample["orientation_xyzw"] for sample in samples])
    axis_index = {"x": 0, "y": 1, "z": 2}[axis_name]
    angles = np.degrees(2.0 * np.arctan2(quaternions[:, axis_index], quaternions[:, 3]))
    return times, positions, angles


def save_figures(records: list[dict], config: dict, directory: Path) -> None:
    # choose the first repetition from the first device-session for each class
    labels = config["task"]["labels"]
    classes = config["synthetic_motion"]["classes"]
    first_device = sorted({record["device_id"] for record in records})[0]
    first_session = f"{first_device}-session-01"
    by_trial = {record["trial_id"]: record for record in records}
    figure, axes = plt.subplots(len(labels), 2, figsize=(12, 13), sharex=True)

    for row, label in enumerate(labels):
        record = by_trial[f"{first_session}-{label}-001"]
        times, position, angles = motion_arrays(record, classes[label]["rotation_axis"])
        for channel, name in enumerate(("x", "y", "z")):
            axes[row, 0].plot(times, position[:, channel], label=name, linewidth=1)
        axes[row, 1].plot(times, angles, color="#2864a3", linewidth=1.5)
        axes[row, 0].set_ylabel("position (m)")
        axes[row, 1].set_ylabel("angle (degrees)")
        axes[row, 0].set_title(label.replace("_", " "))
        axes[row, 1].set_title(f"rotation around {classes[label]['rotation_axis']}")
        axes[row, 0].legend(loc="upper right", fontsize=8)

    for axis in axes.flat:
        axis.grid(alpha=0.2)
    for axis in axes[-1]:
        axis.set_xlabel("time from window start (s)")
    figure.suptitle("Representative synthetic trajectories — first trial per class", fontsize=14)
    figure.text(0.5, 0.01, "Scripted source poses; single-axis angle is a plotting view, not a model feature or proof of physical realism.", ha="center", fontsize=9)
    figure.tight_layout(rect=(0, 0.03, 1, 0.96))
    figure.savefig(directory / "representative-trajectories.png", dpi=160)
    plt.close(figure)

    # compare the same class and repetition across device and session groups
    label = "shake"
    figure, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    device_examples = [
        by_trial[f"{device}-session-01-{label}-001"]
        for device in sorted({record["device_id"] for record in records})
    ]
    session_examples = [
        by_trial[f"{session}-{label}-001"]
        for session in sorted({record["session_id"] for record in records if record["device_id"] == first_device})
    ]

    for row, group in enumerate((device_examples, session_examples)):
        for record in group:
            times, position, angles = motion_arrays(record, classes[label]["rotation_axis"])
            group_name = record["device_id"] if row == 0 else record["session_id"].split("-session-")[-1]
            axes[row, 0].plot(times, position[:, 0], label=group_name, linewidth=1, alpha=0.8)
            axes[row, 1].plot(times, angles, label=group_name, linewidth=1, alpha=0.8)
        axes[row, 0].set_ylabel("source x position (m)")
        axes[row, 1].set_ylabel("y-axis angle (degrees)")
        axes[row, 0].legend(fontsize=8)

    axes[0, 0].set_title("Device groups: session 1, shake repetition 1")
    axes[0, 1].set_title("Orientation curves overlap: identical templates")
    axes[1, 0].set_title("Session groups: device 1, shake repetition 1")
    axes[1, 1].set_title("No stable session rotation effect is modeled")
    for axis in axes.flat:
        axis.grid(alpha=0.2)
        axis.set_xlabel("time from window start (s)")
    figure.suptitle("Synthetic group comparison — no calibrated device or session effects", fontsize=13)
    figure.text(0.5, 0.01, "Position differences come from trial noise. Device/session ids select groups; they do not parameterize motion.", ha="center", fontsize=9)
    figure.tight_layout(rect=(0, 0.04, 1, 0.95))
    figure.savefig(directory / "device-session-variability.png", dpi=160)
    plt.close(figure)


def save_markdown(report: dict, path: Path) -> None:
    # the readable report draws every numerical result from the generated evidence
    quality = report["quality"]
    lines = [
        "# Synthetic data evidence",
        "",
        f"Status: {report['status']}",
        f"Generator seed: {report['config']['project']['random_seed']}",
        f"Code commit: `{report['provenance']['git_commit']}`",
        f"Working tree clean before report generation: {report['provenance']['working_tree_clean']}",
        f"Dataset SHA-256: `{report['provenance']['dataset_sha256']}`",
        f"Matches regeneration with the saved config: {report['matches_regenerated_dataset']}",
        "",
        "This is a synthetic software check. Group ids do not represent calibrated headset differences.",
        "The complete configuration, source hashes, environment, errors, test output, and identifier lists are in [keegan-evidence.json](keegan-evidence.json).",
        "",
        "## Class counts by device and session",
        "",
        "| Device | Session | Split | " + " | ".join(report["config"]["task"]["labels"]) + " | Total |",
        "|---|---|---|" + "---:|" * (len(report["config"]["task"]["labels"]) + 1),
    ]

    for group in report["class_counts_by_device_and_session"]:
        counts = [str(group["class_counts"].get(label, 0)) for label in report["config"]["task"]["labels"]]
        lines.append(f"| {group['device_id']} | {group['session_id']} | {group['split']} | " + " | ".join(counts) + f" | {group['window_count']} |")

    lines.extend([
        "", "## Data quality", "",
        "| Measurement | Observed value |", "|---|---:|",
        f"| Loaded windows | {report['window_count']} |",
        f"| Saved samples | {report['sample_count']} |",
        f"| Missing saved sample slots | {quality['missing_saved_samples']} |",
        f"| Extra saved samples | {quality['extra_saved_samples']} |",
        f"| Invalid tracking flags | {quality['invalid_tracking_samples']} |",
        f"| Windows failing individual validation | {quality['record_validation_rejects']} |",
        f"| Dataset validation errors | {quality['dataset_validation_error_count']} |",
        f"| Resampling events in verified generator | {report['resampling_events']} |",
        "",
        "Missing saved slots means fewer than 120 samples in a saved window. Raw acquisition loss is not measured because no raw capture occurred.",
        "Individual validation rejection is a data-quality result, not an authentication result. Dataset errors can also describe relationships between otherwise valid records.",
        "",
        "## Split identifiers", "",
        "| Split | Windows | Source trials | Trials | Sessions | Devices | Human participants |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])

    for split, values in report["split_identifiers"].items():
        counts = [len(values[field]) for field in ("window_id", "source_trial_id", "trial_id", "session_id", "device_id", "participant_id")]
        lines.append(f"| {split} | " + " | ".join(str(value) for value in counts) + " |")

    lines.extend([
        "", "| Split pair | Identifier | Prohibited overlap? | Shared ids |",
        "|---|---|---|---:|",
    ])
    for item in report["split_overlap"]:
        lines.append(f"| {item['left_split']} / {item['right_split']} | {item['field']} | {item['prohibited']} | {item['shared_count']} |")

    lines.extend([
        "", "Device ids overlap intentionally. Profile ids are aliases for these device groups; there are no separate human participant profiles.",
        "Unique ids alone do not prove statistical independence or prevent shared motion-template shortcuts.",
        "", "## Automated tests", "",
    ])
    if report["tests"]["status"] == "not_run":
        lines.append("Tests were not run by this command. Use `--run-tests` to include actual results.")
    else:
        lines.extend([
            "| Test | Purpose | Expected | Actual |",
            "|---|---|---|---|",
        ])
        for result in report["tests"]["results"]:
            lines.append(f"| {result['test']} | {result['purpose']} | Assertions pass | {result['actual']} |")
        lines.append(f"\nTests run: {report['tests']['tests_run']}. Full failure details are saved in the JSON if any test fails.")

    lines.extend(["", "## Figures", ""])
    if report["figures_written"]:
        lines.extend([
            "![Representative trajectories](representative-trajectories.png)", "",
            "![Device and session groups](device-session-variability.png)",
        ])
    else:
        lines.append("No new figures were produced because validation or regeneration checks failed. Existing figures, if present, belong to an earlier run.")

    lines.extend([
        "", "## Interpretation and limits", "",
        "- The current generator directly constructs 120 samples; it does not test a resampling algorithm.",
        "- Stable device and session effects are disabled and unimplemented. Position differences in the group figure are trial noise.",
        "- Nod, shake, and look-and-return angles share fixed templates within each class. This makes the class task easy and limits generalization claims.",
        "- The still class has a small random walk in orientation, and all classes have Gaussian position noise.",
        "- The split separates complete synthetic sessions but does not demonstrate cross-device, cross-person, or real-Quest generalization.",
        "- Inspect the figures before making any claim about physical plausibility; the generator is not calibrated against approved human motion data.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create reproducible evidence for the synthetic motion dataset.")
    parser.add_argument("--run-tests", action="store_true", help="run data and split tests and include their actual outcomes")
    parser.add_argument("--machine-model", default="not recorded; supply --machine-model", help="your computer manufacturer and model")
    arguments = parser.parse_args()

    config_path = ROOT / "configs" / "pilot.json"
    schema_path = ROOT / "schemas" / "quest-window.schema.json"
    config = read_json(config_path)
    schema = read_json(schema_path)
    data_path = ROOT / config["synthetic_data"]["output_path"]
    if not data_path.is_file():
        raise SystemExit(f"Dataset not found: {data_path}\nRun python src/python/scripts/generate_data.py first.")

    output_directory = ROOT / "results" / "week-2"
    output_directory.mkdir(parents=True, exist_ok=True)

    # record provenance before this script changes any result files
    source_paths = [
        config_path, schema_path,
        ROOT / "src/python/puf_snn/data/generator.py",
        ROOT / "src/python/puf_snn/data/validation.py",
        ROOT / "src/python/scripts/generate_data.py",
        ROOT / "src/python/scripts/validate_data.py",
        Path(__file__).resolve(),
        ROOT / "tests/test_data.py",
        ROOT / "tests/test_splits.py",
        ROOT / "pyproject.toml",
    ]
    status_text = git_output(["status", "--porcelain"])
    provenance = {
        "repository": "https://github.com/Keellonn/PUF-SNN",
        "git_commit": git_output(["rev-parse", "HEAD"]),
        "working_tree_clean": None if status_text == "unavailable" else status_text == "",
        "working_tree_status_before_run": status_text,
        "dataset_path": config["synthetic_data"]["output_path"],
        "dataset_sha256": file_hash(data_path),
        "source_sha256": {
            path.relative_to(ROOT).as_posix(): file_hash(path)
            for path in source_paths
        },
        "command_arguments": sys.argv[1:],
    }

    print("Validating the saved dataset...")
    gap_ms = float(config["capture"]["maximum_timestamp_gap_ms"])
    tracking = float(config["capture"]["minimum_tracking_valid_fraction"])
    tolerance = float(config["capture"]["quaternion_norm_tolerance"])
    records, errors = validate_jsonl(
        data_path, schema_path, gap_ms, tracking,
        config=config, quaternion_tolerance=tolerance,
    )

    validator = make_schema_validator(schema)
    record_failures = []
    structurally_valid = []
    for index, record in enumerate(records):
        individual_errors = validate_record(record, validator, gap_ms, tracking, tolerance)
        if individual_errors:
            record_failures.append({"record_index": index, "errors": individual_errors})
        if validator.is_valid(record):
            structurally_valid.append(record)

    print("Comparing the saved records with fixed-seed regeneration...")
    regenerated = generate_records(config)
    matches_regenerated = records == regenerated
    del regenerated

    samples_lists = [
        record["samples"]
        for record in records
        if isinstance(record, dict) and isinstance(record.get("samples"), list)
    ]
    expected_samples = int(config["capture"]["samples_per_window"])
    missing_slots = sum(max(0, expected_samples - len(samples)) for samples in samples_lists)
    missing_slots += (len(records) - len(samples_lists)) * expected_samples
    invalid_tracking = sum(
        sample.get("tracking_valid") is False
        for samples in samples_lists
        for sample in samples
        if isinstance(sample, dict)
    )

    grouped = defaultdict(Counter)
    for record in structurally_valid:
        grouped[(record["device_id"], record["session_id"], record["split"])][record["label"]] += 1

    identifiers, overlap = split_evidence(structurally_valid)
    tests = run_data_tests() if arguments.run_tests else {"status": "not_run", "results": []}
    validation_passed = not errors and matches_regenerated
    tests_passed = tests["status"] == "passed"
    environment = {
        "machine_model": arguments.machine_model,
        "processor": platform.processor(),
        "operating_system": platform.platform(),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "packages": {
            name: package_version(name)
            for name in ("numpy", "matplotlib", "jsonschema")
        },
    }

    report = {
        "status": "passed" if validation_passed and tests_passed else "checks_incomplete_or_failed",
        "provenance": provenance,
        "environment": environment,
        "config": config,
        "window_count": len(records),
        "sample_count": sum(len(samples) for samples in samples_lists),
        "generation_method": config["synthetic_motion"]["generation_method"],
        "resampling_events": 0 if matches_regenerated else None,
        "resampling_evidence": "zero resampling operations in the fixed-grid generator, conditional on matching regeneration",
        "matches_regenerated_dataset": matches_regenerated,
        "configured_device_effects": config["synthetic_motion"]["device_effects"]["enabled"],
        "configured_session_effects": config["synthetic_motion"]["session_effects"]["enabled"],
        "quality": {
            "missing_saved_samples": missing_slots,
            "extra_saved_samples": sum(max(0, len(samples) - expected_samples) for samples in samples_lists),
            "invalid_tracking_samples": invalid_tracking,
            "record_validation_rejects": len(record_failures),
            "record_failures": record_failures,
            "dataset_validation_error_count": len(errors),
            "dataset_validation_errors": errors,
            "raw_acquisition_missing_samples": None,
            "raw_acquisition_note": "not measured: there is no raw headset acquisition in this experiment",
        },
        "class_counts_by_device_and_session": [
            {
                "device_id": device_id,
                "session_id": session_id,
                "split": split,
                "class_counts": dict(counts),
                "window_count": sum(counts.values()),
            }
            for (device_id, session_id, split), counts in sorted(grouped.items())
        ],
        "identifier_report_population": "records passing structural schema validation; overall failures remain listed above",
        "profile_definition": "profile_id is an alias of the synthetic device grouping id; no separate participant profiles exist",
        "split_identifiers": identifiers,
        "split_overlap": overlap,
        "tests": tests,
        "figures_written": validation_passed,
    }

    if validation_passed:
        # create the example and plots only from a dataset that passed the checks
        save_json(ROOT / "data/examples/sample-window.json", records[0])
        save_figures(records, config, output_directory)

    save_json(output_directory / "keegan-evidence.json", report)
    save_markdown(report, output_directory / "keegan-evidence.md")
    print(f"Saved evidence to {output_directory}")
    print(f"Windows: {report['window_count']}; samples: {report['sample_count']}")
    print(f"Validation errors: {len(errors)}; regeneration matches: {matches_regenerated}")
    print(f"Automated tests: {tests['status']}")

    if not validation_passed or (arguments.run_tests and not tests_passed):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
