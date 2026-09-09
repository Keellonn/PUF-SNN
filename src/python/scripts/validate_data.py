"""
this file checks the generated data and prints a short results summary
it
it should verify the full 1,800 window dataset and print:
- # of windows
- # of devices
- # of sessions
- # of independent source trials
- label counts
- split counts
- any errors found
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src" / "python"))

from puf_snn.data.validation import validate_jsonl


def main() -> None:
    # this loads the same settings used by the generator
    config_path = ROOT / "configs" / "pilot-v0.2.json"

    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    data_path = ROOT / config["synthetic_data"]["output_path"]
    schema_path = ROOT / "schemas" / "quest-window-v0.2.schema.json"

    # this checks the file before any model is allowed to use it
    records, errors = validate_jsonl(
        data_path,
        schema_path,
        maximum_gap_ms=float(config["capture"]["maximum_timestamp_gap_ms"]),
        minimum_tracking=float(config["capture"]["minimum_tracking_valid_fraction"]),
    )

    if errors:
        print(f"Validation failed with {len(errors)} error(s):")

        for error in errors[:50]:
            print(f"- {error}")

        raise SystemExit(1)

    # this makes the successful run easy to verify and document
    label_counts = Counter(
        record["label"]
        for record in records
    )

    split_counts = Counter(
        record["split"]
        for record in records
    )

    device_ids = {
        record["device_id"]
        for record in records
    }

    session_ids = {
        record["session_id"]
        for record in records
    }

    source_trial_ids = {
        record["source_trial_id"]
        for record in records
    }

    print(f"Validation passed for {len(records)} windows")
    print(f"Labels: {dict(sorted(label_counts.items()))}")
    print(f"Splits: {dict(sorted(split_counts.items()))}")
    print(f"Devices: {len(device_ids)}")
    print(f"Sessions: {len(session_ids)}")
    print(f"Independent source trials: {len(source_trial_ids)}")


if __name__ == "__main__":
    main()
