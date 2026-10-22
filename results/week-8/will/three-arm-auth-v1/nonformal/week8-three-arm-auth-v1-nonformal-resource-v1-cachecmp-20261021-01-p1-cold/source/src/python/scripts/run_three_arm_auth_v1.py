"""Inspect a plan, audit evidence, or explicitly run ONE bounded nonformal pilot."""
import argparse
import json
from pathlib import Path

from puf_snn.experiments import three_arm_auth_v1 as study
from puf_snn.experiments import three_arm_auth_evidence_v1 as evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "run-nonformal", "audit"))
    parser.add_argument("--config", type=Path, default=study.CONFIG_PATH)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--authorization")
    parser.add_argument("--reviewed-plan-sha256")
    args = parser.parse_args()
    if args.action == "audit":
        study.require(args.output is not None, "audit requires output")
        result = evidence.audit_evidence(args.output)
    else:
        config = study.StudyConfig.load(args.config)
        plan = study.compile_plan(config)
        if args.action == "plan":
            result = dict(experiment_id=study.VERSION, config_sha256=config.digest,
                plan_sha256=plan["plan_sha256"], counts=plan["counts"], formal_execution_enabled=False)
        else:
            study.require(config.to_dict()["mode"] == "nonformal", "run requires bounded nonformal configuration")
            study.require(args.output is not None, "run requires exclusive output")
            with evidence.EvidenceRun(args.output,config,authorization=args.authorization,
                    reviewed_plan_sha256=args.reviewed_plan_sha256) as run:
                result = run.execute()
    print(json.dumps(result,sort_keys=True,indent=2,allow_nan=False))


if __name__ == "__main__":
    main()
