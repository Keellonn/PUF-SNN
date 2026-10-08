"""Tier-1 v2 plan validation / NONFORMAL smoke / explicitly requested formal run."""
import argparse
from pathlib import Path
from puf_snn.tier1_v2 import (ROOT, FORMAL_ROOT, strict_json, validate_config, compile_trial_plan,
                            run_nonformal, run_real_nonformal, run_formal, canonical)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument("--validate-plan",action="store_true")
    mode.add_argument("--nonformal-smoke",action="store_true")
    mode.add_argument("--nonformal-real-artifacts",action="store_true")
    mode.add_argument("--formal",action="store_true")
    parser.add_argument("--config",type=Path,default=ROOT/"configs/tier1_v2_experiment_v1.json")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args(argv)
    if not any((args.validate_plan,args.nonformal_smoke,args.nonformal_real_artifacts,args.formal)):
        parser.print_help(); return 0
    try:
        if args.nonformal_real_artifacts:
            if args.output is None: parser.error("--nonformal-real-artifacts requires a fresh temporary --output")
            reconciliation,_=run_real_nonformal(args.output)
            print(canonical(reconciliation)); return 0 if reconciliation["evidence_complete"] and reconciliation["expected_behavior_observed"] else 1
        if args.nonformal_smoke:
            if args.output is None: parser.error("--nonformal-smoke requires a fresh temporary --output")
            reconciliation,_=run_nonformal(args.output)
            print(canonical(reconciliation)); return 0 if reconciliation["evidence_complete"] and reconciliation["expected_behavior_observed"] else 1
        config=strict_json(args.config.read_text(encoding="utf-8")); validate_config(config)
        if args.validate_plan:
            plan=compile_trial_plan(config)
            print(canonical(dict(mode="PLAN ONLY; no execution",plan_sha256=plan["plan_sha256"],counts=plan["counts"],
                                 scenarios=sum(s["phase"]=="measured" for s in plan["scenarios"]))))
            return 0
        reconciliation,_=run_formal(config,args.output or FORMAL_ROOT)
        print(canonical(reconciliation)); return 0 if reconciliation["evidence_complete"] else 1
    except Exception as error:
        # Deliberately no traceback or arbitrary exception arguments in evidence.
        public_reasons={"unresolved execution source pins","formal output already exists",
            "execution provenance requires clean pinned source","missing/mismatched source pins",
            "missing exact frozen artifacts; restore archives, never regenerate","config hash mismatch",
            "preregistered config/profile/populations/settings changed","protocol baseline changed; re-audit required",
            "nonformal output must be temporary, outside results","nonformal output cannot target formal identity"}
        reason=str(error) if type(error) is ValueError and str(error) in public_reasons else "execution_failure_or_invalid_input"
        print(canonical(dict(status="refused_or_incomplete",error_category=type(error).__name__,reason=reason)))
        return 2


if __name__=="__main__": raise SystemExit(main())
