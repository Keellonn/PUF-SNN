"""
this script records the seeded Tier 2 cases without duplicating the full motion dataset
it checks the clean source, saves reproducible case metadata, and constructs a small example sweep
it does not train a detector or claim that any window has passed authentication
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/python"))

import numpy as np

import puf_snn.attacks.stream as stream_module
from puf_snn.attacks.stream import apply_stream_attack, iter_attack_cases, validate_attack_config
from puf_snn.data.validation import validate_dataset
from puf_snn.motion_diagnostics import assert_no_full_window_duplicates
from puf_snn.snn.dataset import load_records


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: dict | list) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def git_value(*arguments: str) -> str:
    result = subprocess.run(["git", "-c", f"safe.directory={ROOT.as_posix()}", "-C", str(ROOT), *arguments], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the permanent seeded stream-attack plan and example evidence")
    parser.add_argument("--input", type=Path, default=ROOT / "data/generated/synthetic-windows.jsonl")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/stream_attacks.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/week-5/keegan/stream-attacks")
    args = parser.parse_args()

    input_path = args.input.resolve()
    config_path = args.config.resolve()
    output_path = args.output.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    validate_attack_config(config)
    if output_path.exists():
        raise FileExistsError(f"output already exists; preserve it and choose a new directory: {output_path}")
    input_hash = file_hash(input_path)
    if input_hash != config["source_dataset_sha256"]:
        raise ValueError("source dataset differs from the frozen Week 4 dataset; stop and investigate before creating attacks")

    records = load_records(input_path)
    schema_path = ROOT / "schemas/quest-window.schema.json"
    pilot_path = ROOT / "configs/pilot.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    pilot = json.loads(pilot_path.read_text(encoding="utf-8"))
    errors = validate_dataset(records, schema, config=pilot)
    if errors:
        raise ValueError("source dataset failed validation: " + "; ".join(errors[:5]))
    assert_no_full_window_duplicates(records)

    # all source validation and provenance checks finish before creating the output directory
    source_commit = git_value("rev-parse", "HEAD")
    worktree_dirty = bool(git_value("status", "--porcelain"))
    sources = [
        Path(__file__).resolve(),
        Path(stream_module.__file__).resolve(),
        ROOT / "src/python/puf_snn/integration.py",
        ROOT / "src/python/puf_snn/auth/binary_window.py",
        ROOT / "src/python/puf_snn/data/validation.py",
        ROOT / "src/python/puf_snn/motion_diagnostics.py",
        ROOT / "src/python/puf_snn/snn/dataset.py",
        schema_path,
        pilot_path,
    ]
    source_hashes = {str(path): file_hash(path) for path in sources}
    output_path.mkdir(parents=True, exist_ok=False)
    write_json(output_path / "config.json", config)

    example_sources = set()
    split_examples = Counter()
    for record in records:
        split = record["split"]
        if split_examples[split] < config["examples_per_split"]:
            example_sources.add(record["window_id"])
            split_examples[split] += 1

    by_split = Counter()
    by_condition = Counter()
    example_statuses = Counter()
    examples = []
    case_ids = set()
    sources_by_id = {record["window_id"]: record for record in records}
    with (output_path / "attack-plan.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
        for case in iter_attack_cases(records, config):
            if case["case_id"] in case_ids:
                raise ValueError("duplicate derived attack identifier")
            case_ids.add(case["case_id"])
            by_split[case["split"]] += 1
            by_condition[f"{case['attack_type']}:{case['severity']}"] += 1
            handle.write(json.dumps(case, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
            if case["source_window_id"] in example_sources:
                outcome = apply_stream_attack(sources_by_id[case["source_window_id"]], case)
                example_statuses[outcome["status"]] += 1
                examples.append({
                    "case": case,
                    "status": outcome["status"],
                    "reason": outcome["reason"],
                    "details": outcome["details"],
                    "authentication_result": outcome["authentication_result"],
                    "output_motion_sha256": stream_module.full_window_hash(outcome["record"]) if outcome["record"] is not None else None,
                })

    summary = {
        "source_window_count": len(records),
        "source_windows_by_split": dict(Counter(record["split"] for record in records)),
        "planned_case_count": len(case_ids),
        "planned_cases_by_split": dict(sorted(by_split.items())),
        "planned_cases_by_condition": dict(sorted(by_condition.items())),
        "source_dataset_sha256": input_hash,
        "source_validation_passed": True,
        "source_full_window_cross_split_duplicates": 0,
        "example_case_count": len(examples),
        "example_outcomes": dict(sorted(example_statuses.items())),
        "authentication_executed": False,
        "models_executed": False,
        "limitation": "planned transformed copies are paired with their original source, not independent recordings; example outcomes are a smoke check, not complete attack or detector results",
    }
    write_json(output_path / "summary.json", summary)
    write_json(output_path / "example-outcomes.json", examples)

    report = [
        "# Tier 2 Stream Attack Plan",
        "",
        f"Clean source windows: {len(records):,}",
        f"Planned cases: {len(case_ids):,}",
        "",
        "Each source has one clean control and nine attacks at three severity levels. Seeded magnitudes vary within the predefined 0.8-1.2 multiplier range, with different directions/onsets/random samples. Clean and transformed copies retain their source split.",
        "",
        "The plan stores metadata rather than repeated full motion windows. Evaluation regenerates each case from the frozen source and recorded seed. Attack names, labels, severities and seeds never become sensor/model features.",
        "",
        f"Constructed example cases: {len(examples)}",
        f"Example outcomes: {dict(sorted(example_statuses.items()))}",
        "",
        "Timestamp jitter and dropped samples are applied to synthetic source samples and reconstructed onto the original 120-point grid using linear position interpolation and quaternion SLERP. Non-increasing source times, gaps above 50 ms, or missing grid coverage cause a construction failure. The endpoints are retained/anchored, so this experiment does not measure boundary dropout or clock drift.",
        "",
        "The output checks canonical binary32 quality but does not generate HMAC tags, invoke a verifier, run a classifier, or train an anomaly detector. COMPLETE means this plan and its example checks finished, not that Week 5 evaluation is complete.",
        "",
        "Original motion labels describe the intended source task. Severe corruption can make the observed movement ambiguous; classification loss is measured relative to that source task. The anomaly label means a documented synthetic transform was applied, not that real malicious activity has been proven.",
        "",
        "No reconstruction reliability, pre-HKDF credential verification, formal Tier-1 rejection rate, physical Quest behavior, or full-system availability is established here.",
        "",
    ]
    with (output_path / "stream-attacks.md").open("x", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(report))

    artifacts = {path.name: file_hash(path) for path in sorted(output_path.iterdir()) if path.is_file()}
    manifest = {
        "run_type": "tier2_stream_attack_plan",
        "source_commit": source_commit,
        "source_worktree_dirty": worktree_dirty,
        "sources_outside_checkout": any(not path.is_relative_to(ROOT) for path in sources),
        "source_sha256": source_hashes,
        "input_path": str(input_path),
        "input_sha256": input_hash,
        "config_path": str(config_path),
        "config_sha256": file_hash(config_path),
        "command": [sys.executable, *sys.argv],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "rng": "numpy PCG64; per-case parameter and transform seeds derived with SHA-256",
        },
        "artifacts": artifacts,
        "scope": "attack plan and example construction checks only; no authentication/model evaluation",
    }
    write_json(output_path / "manifest.json", manifest)
    with (output_path / "COMPLETE").open("x", encoding="utf-8", newline="\n") as handle:
        handle.write("tier2 stream-attack plan and example construction checks completed\n")
    print(f"Source dataset validated: {len(records):,} windows")
    print(f"Planned cases: {len(case_ids):,}; splits: {dict(sorted(by_split.items()))}")
    print(f"Example outcomes: {dict(sorted(example_statuses.items()))}")
    print("Authentication and model evaluation have not run")
    print(f"Saved results to {output_path}")


if __name__ == "__main__":
    main()
