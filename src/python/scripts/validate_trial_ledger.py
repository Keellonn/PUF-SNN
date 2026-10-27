"""Read-only trial accounting; use synthetic fixtures until research collection is approved."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/python"))
from puf_snn.trial_ledger import inspect_ledger


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--output", type=Path, help="New report file; existing files are never overwritten")
    args = parser.parse_args()
    report = inspect_ledger(args.ledger)
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(json.dumps({key: report[key] for key in ("status", "closed", "counts", "issues")}, indent=2))
    return 0 if report["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
