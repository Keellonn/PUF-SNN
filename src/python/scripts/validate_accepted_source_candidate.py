"""Read-only check of the synthetic source-export candidate and paired outputs."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/python"))
from puf_snn.accepted_source import inspect_candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("windows", type=Path)
    parser.add_argument("metrics", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = inspect_candidate(args.source, args.windows, args.metrics)
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(report, output, indent=2, sort_keys=True)
            output.write("\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
