"""Dry-plan, preflight, audit, or explicitly authorized supervised calibration only."""
import argparse
import json
from pathlib import Path
import sys

# Run directly from a checkout without installation; source-integrity checks
# subsequently verify all imported puf_snn modules belong to this checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main(argv=None):
    # A worker blocks on stdin before importing the scientific package. It then
    # proves peer identity, job membership and monitor lease before any acquisition.
    args_list = sys.argv[1:] if argv is None else argv
    if args_list == ["_worker"]:
        request = json.loads(sys.stdin.buffer.read(1024*1024))
        from puf_snn.experiments.shared_noise_calibration_resources_v1 import worker
        worker(request)
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "preflight", "run-calibration", "audit", "acknowledge-selection", "audit-selection"))
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--approval-file", type=Path)
    parser.add_argument("--acknowledgment-file", type=Path)
    args = parser.parse_args(args_list)
    from puf_snn.experiments import shared_noise_calibration_v1 as study
    config = study.StudyConfig.load(args.config or study.CONFIG_PATH)
    if args.action == "plan":
        result = study.dry_plan(config)
    elif args.action == "preflight":
        from puf_snn.experiments.shared_noise_calibration_resources_v1 import freeze
        result = dict(study.dry_plan(config), **{k:v for k,v in freeze(config).items()
                      if k not in ("config_sha256", "plan_sha256")}, execution_authorized=False)
    elif args.action == "audit":
        from puf_snn.experiments.shared_noise_calibration_evidence_v1 import audit_evidence
        study.require(args.output is not None, "audit needs an existing completed bundle")
        result = audit_evidence(args.output)
    elif args.action in ("acknowledge-selection", "audit-selection"):
        from puf_snn.experiments import shared_noise_calibration_provenance_v2 as provenance
        study.require(args.output is not None, "selection action requires a certified calibration bundle")
        if args.action == "acknowledge-selection":
            study.require(args.acknowledgment_file is not None, "a separately supplied named dated attestation is required")
            attestation = study.read_json_bytes(args.acknowledgment_file.read_bytes())
            target = provenance.record_acknowledgment(args.output, attestation)
            result = dict(recorded_attestation=str(target), final_evaluation_enabled=False)
        else:
            result = provenance.selection_status(args.output, args.acknowledgment_file)
    else:
        from puf_snn.experiments.shared_noise_calibration_resources_v1 import execute
        study.require(config.to_dict()["mode"] == "bounded-calibration", "scientific CLI cannot launch fixture mode")
        study.require(args.output is not None and args.approval_file is not None,
                      "reviewed frozen approval and exclusive output are required")
        approval = study.read_json_bytes(args.approval_file.read_bytes())
        result = execute(config, args.output, approval)
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
