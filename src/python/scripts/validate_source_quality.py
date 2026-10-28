"""Reconcile source diagnostics and trial accounting without modifying either file."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"src/python"))
from puf_snn.source_quality import inspect_source_quality

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger",type=Path)
    parser.add_argument("source_quality",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    report=inspect_source_quality(args.ledger,args.source_quality)
    if args.output:
        with args.output.open("x",encoding="utf-8",newline="\n") as f:
            json.dump(report,f,indent=2,sort_keys=True);f.write("\n")
    print(json.dumps({k:report[k] for k in ("status","ledger_status","counts","issues")},indent=2))
    return 0 if report["status"]=="COMPLETE" else 1

if __name__=="__main__":raise SystemExit(main())
