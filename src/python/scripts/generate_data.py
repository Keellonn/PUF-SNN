"""
this script builds the complete scripted dataset from the pilot settings
it
- finds the project
- loads the pilot / experiment settings
- generates the synthetic data / windows
- saves the windows to a jsonl file

our decisions for the experiment settings are
- 5 motion labels
- 60 Hz sampling
- 120 samples per window
- 6 devices
- 3 sessions
- 20 trials per class
- random seed 7
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src" / "python"))

from puf_snn.data.generator import generate_records, write_jsonl


def main() -> None:
    # this loads the shared settings so the run can be repeated later
    config_path = ROOT / "configs" / "pilot.json"

    with config_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    # this creates the windows and saves them outside version control
    records = generate_records(config)
    output_path = ROOT / config["synthetic_data"]["output_path"]
    count = write_jsonl(records, output_path)

    # this prints simple counts
    label_counts = Counter(
        record["label"]
        for record in records
    )

    split_counts = Counter(
        record["split"]
        for record in records
    )

    # lil summary
    print(f"Wrote {count} windows to {output_path}")
    print(f"Labels: {dict(sorted(label_counts.items()))}")
    print(f"Splits: {dict(sorted(split_counts.items()))}")


if __name__ == "__main__":
    main()
