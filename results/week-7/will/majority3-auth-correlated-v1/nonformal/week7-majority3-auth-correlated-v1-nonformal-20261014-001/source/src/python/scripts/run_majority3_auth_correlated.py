"""Read-only by default. Formal execution is not implemented."""
import argparse
import json
from pathlib import Path

from puf_snn.experiments.majority3_auth_v1 import CONFIG_PATH, StudyConfig, compile_plan, validate_plan
from puf_snn.experiments.majority3_auth_evidence_v1 import EvidenceRun, audit_evidence, resource_estimate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "plan", "estimate", "audit", "run-nonformal"))
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--nonformal-plan", action="store_true", help="inspect the separately authorized 100-attempt plan")
    parser.add_argument("--directory", type=Path, help="explicit existing audit directory or exclusively new execution output")
    parser.add_argument("--authorize-nonformal", choices=("RUN-100-NONFORMAL",))
    parser.add_argument("--reviewed-plan-sha256")
    args = parser.parse_args(argv)
    if args.command == "audit":
        if args.directory is None:
            parser.error("audit requires --directory")
        result = audit_evidence(args.directory)
    else:
        config = StudyConfig.load(args.config)
        if args.nonformal_plan or args.command == "run-nonformal":
            obj = config.to_dict()
            obj.update(mode="nonformal", allocation=dict(populations=1, devices_per_population=1,
                                                         attempts_per_device_condition=10))
            config = StudyConfig.from_dict(obj)
        if args.command == "validate":
            result = dict(status="VALID_CONFIGURATION", config_sha256=config.digest, executed_attempts=0)
        else:
            plan = compile_plan(config)
            if args.command == "run-nonformal":
                if args.directory is None:
                    parser.error("execution requires an exclusively new --directory")
                with EvidenceRun(args.directory, config, authorization=args.authorize_nonformal,
                                 reviewed_plan_sha256=args.reviewed_plan_sha256) as run:
                    result = run.execute()
            elif args.command == "plan":
                validate_plan(config, plan)
                result = dict(config=config.to_dict(), plan=plan, executed_attempts=0)
            else:
                result = dict(**plan["counts"], resources=resource_estimate(plan),
                    config_sha256=config.digest, plan_sha256=plan["plan_sha256"],
                    minimum_raw_response_bytes=plan["counts"]["expected_reads"]*8,
                    note="expected_reads counts measured trials only; resources separates replay and setup. Raw response bytes exclude JSON/filesystem overhead. No runtime estimate.",
                    executed_attempts=0, formal_execution="disabled")
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
