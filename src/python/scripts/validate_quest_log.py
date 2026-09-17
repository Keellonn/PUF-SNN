"""
this file validates JSONL windows copied from the Unity Quest logger
it uses the shared schema and quality limits without applying synthetic device-count rules
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src" / "python"))

from puf_snn.data.validation import validate_jsonl


def parse_arguments() -> argparse.Namespace:
    # this accepts an absolute path or a path relative to the repository root
    parser = argparse.ArgumentParser(
        description="validate JSONL windows copied from the Unity Quest logger",
    )

    parser.add_argument(
        "input",
        type=Path,
        help="path to the Quest logger JSONL file",
    )

    return parser.parse_args()


def main() -> None:
    # this loads the same quality limits used by the synthetic pipeline
    arguments = parse_arguments()
    input_path = arguments.input

    if not input_path.is_absolute():
        input_path = ROOT / input_path

    config_path = ROOT / "configs" / "pilot.json"
    schema_path = ROOT / "schemas" / "quest-window.schema.json"

    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    records, errors = validate_jsonl(
        input_path,
        schema_path,
        maximum_gap_ms=float(config["capture"]["maximum_timestamp_gap_ms"]),
        minimum_tracking=float(config["capture"]["minimum_tracking_valid_fraction"]),
        quaternion_tolerance=float(config["capture"]["quaternion_norm_tolerance"]),
    )

    if errors:
        print(f"Quest log validation failed with {len(errors)} error(s):")

        for error in errors[:50]:
            print(f"- {error}")

        raise SystemExit(1)

    label_counts = Counter(record["label"] for record in records)
    split_counts = Counter(record["split"] for record in records)

    print(f"Quest log validation passed for {len(records)} windows")
    print(f"Labels: {dict(sorted(label_counts.items()))}")
    print(f"Splits: {dict(sorted(split_counts.items()))}")


if __name__ == "__main__":
    main()
