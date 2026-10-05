"""Small fresh v2 integration run; not a reliability, security or latency study."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
from random import Random
import subprocess

import galois
import joblib
import numpy as np
import sklearn
import torch

from puf_snn.attacks.evaluation import prepare_model_inputs
from puf_snn.attacks.stream import apply_stream_attack, iter_attack_cases
from puf_snn.auth.config import AuthConfig
from puf_snn.auth.credential_verifier import (
    CredentialAdmissionService, CredentialVerifierRecord, CredentialVerifierStore,
    InMemoryCredentialVerifierKeyProvider,
)
from puf_snn.auth.sender import Sender
from puf_snn.auth.session import RegistryEntry, provision_device
from puf_snn.auth.verifier import Verifier
from puf_snn.frozen_pipeline import (
    load_frozen_bundle, read_json, run_window_controls, scoped_path,
    select_smoke_sources, sha256, validate_smoke_config,
)
from puf_snn.pipeline_v2 import ModelCallCounts, V2InferencePipeline
from puf_snn.puf.device import create_device
from puf_snn.puf.ro_puf import generate_pairs, generate_response
from puf_snn.puf.variables import load_config as load_puf_config
from puf_snn.reconstruction import DEFAULT_CONFIG, enroll
from puf_snn.snn.dataset import load_records


ROOT = Path(__file__).resolve().parents[3]
LIMITATION = (
    "Functional validation cohort: 30 predeclared single-read admission attempts on six fixed simulated "
    "PUF profiles, with paired repeated windows and boundary controls. This is not a new held-out "
    "accuracy/attack-recall estimate, an FRR study, formal Tier-1 evaluation or latency benchmark. "
    "No claim of Quest, cross-device/person generalization, hardware acquisition time or production security.")


def rng_for(identity: str) -> Random:
    rng = Random()
    rng.seed(identity, version=2)
    return rng


def selected_bit_errors(reference: tuple, response: tuple) -> int:
    if len(reference) != DEFAULT_CONFIG.response_length or len(response) != DEFAULT_CONFIG.response_length:
        raise ValueError("response error accounting requires the existing 64-bit response")
    return sum(response[bit] != reference[bit] for bit in DEFAULT_CONFIG.response_indices)


def write_json(path: Path, value) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def require_clean_source(root: Path) -> str:
    state = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                           text=True, capture_output=True, check=True).stdout
    if state:
        raise ValueError("commit the implementation first; worktree must be clean before the smoke run")
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                          text=True, capture_output=True, check=True).stdout.strip()


def public_audit(endpoint) -> list[dict]:
    allowed = {"event_id", "event_type", "decision", "reason", "sequence_number", "session_id",
               "device_id", "authenticated_bytes_sha256"}
    return [{key: value for key, value in row.items() if key in allowed}
            for row in endpoint.audit_records]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/week6_smoke.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/week-6/keegan/frozen-model-smoke")
    args = parser.parse_args()
    config = read_json(args.config)
    validate_smoke_config(config)
    source_commit = require_clean_source(ROOT)
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / "results/week-6/keegan") or output == ROOT / "results/week-6/keegan":
        raise ValueError("choose a new scoped Week 6 result directory")
    if output.exists():
        raise ValueError("output already exists; preserve it and stop, never overwrite a partial run")

    print("Checking pinned manifests, training-only normalization and all 11 frozen model binaries", flush=True)
    bundle = load_frozen_bundle(ROOT, config)
    selected = select_smoke_sources(load_records(scoped_path(ROOT, config["input_path"])))
    source_devices = sorted({record["device_id"] for record in selected})
    puf = load_puf_config(scoped_path(ROOT, config["puf_config"]))
    if (puf.number_of_devices != 6 or puf.number_of_oscillators != 128 or puf.pairing_scheme != "adjacent"
            or puf.random_seed != config["puf_seed"] or puf.nominal_frequency != 100
            or puf.manufacturing_std != 1 or puf.aging_std != 0
            or puf.reference_conditions.environmental_offset != 0
            or puf.reference_conditions.measurement_noise_std != 0
            or puf.read_conditions.environmental_offset != 0
            or puf.read_conditions.measurement_noise_std != .1):
        raise ValueError("PUF baseline changed; do not silently run another configuration")
    auth = AuthConfig.load(scoped_path(ROOT, config["auth_config"]))
    if auth != AuthConfig():
        raise ValueError("the existing v2 authentication limits must remain unchanged")
    attack_config = read_json(scoped_path(ROOT, config["attack_config"]))
    controls = {case["source_window_id"]: case for case in iter_attack_cases(selected, attack_config)
                if case["attack_type"] == "position_jump" and case["severity"] == "medium"}
    if len(controls) != 30 or len(selected) != 30:
        raise ValueError("smoke must contain exactly six devices by five classes")
    pairs = generate_pairs(puf.number_of_oscillators, puf.pairing_scheme)

    # Trusted enrollment is performed outside each session attempt. The fixed
    # manufacturing stream matches the old pilot; read/credential streams are
    # separate new domains. Never serialize these provisioning objects.
    materials = {}
    for index, device_id in enumerate(source_devices):
        device = create_device(device_id, puf.number_of_oscillators, puf.manufacturing_std,
                               rng=rng_for(f"week2-v1:{puf.random_seed}:{index}:manufacturing"))
        reference = generate_response(device, pairs, puf.nominal_frequency, puf.reference_conditions,
                                      rng=rng_for(f"week2-v1:{puf.random_seed}:{index}:enrollment"))
        credential = rng_for(f"week6-smoke-v1:{puf.random_seed}:{index}:credential").getrandbits(32).to_bytes(4, "big")
        enrollment_id = f"week6-smoke-enrollment-{index}"
        helper = enroll(reference, credential, enrollment_id=enrollment_id)
        key_id = f"week6-smoke-verifier-key-{index}"
        provider = InMemoryCredentialVerifierKeyProvider.generate(key_id)
        verifier_record = CredentialVerifierRecord.enroll(
            device_id=device_id, enrollment_id=enrollment_id, reconstruction_id=helper.config.version,
            verifier_key_id=key_id, credential4=credential, key_provider=provider)
        service = CredentialAdmissionService(CredentialVerifierStore([verifier_record]), provider)
        materials[device_id] = (device, reference, credential, enrollment_id, helper, service,
                                rng_for(f"week6-smoke-v1:{puf.random_seed}:{index}:measurement"))

    output.mkdir(parents=True)
    (output / "INCOMPLETE").write_text("Preserve partial evidence; no automatic retry or overwrite.\n", encoding="utf-8")
    (output / ".gitattributes").write_text("* text eol=lf\n", encoding="utf-8")
    write_json(output / "config.json", config)
    write_json(output / "frozen-input-hashes.json", bundle.artifact_hashes)
    write_json(output / "source-selection.json", [
        {key: record[key] for key in ("window_id", "device_id", "session_id", "source_trial_id", "split", "label")}
        for record in selected])
    attempts, window_counts = [], Counter()
    with (output / "attempts.jsonl").open("x", encoding="utf-8", newline="\n") as evidence:
        for index, source in enumerate(selected):
            device, reference, credential, enrollment_id, helper, service, read_rng = materials[source["device_id"]]
            sender = Sender(provision_device(source["device_id"], enrollment_id, helper),
                            auth.session_config().limits, admission_service=service)
            verifier = Verifier([RegistryEntry(source["device_id"], enrollment_id, credential)],
                                auth.session_config(), admission_service=service)
            pipeline = V2InferencePipeline(sender, verifier, prepare_model_inputs,
                                           bundle.motion_predictions, bundle.anomaly_predictions)
            captured = []

            def read_once():
                response = generate_response(device, pairs, puf.nominal_frequency, puf.read_conditions, rng=read_rng)
                captured.append(response)
                return response

            try:
                attempt = pipeline.establish(read_once, f"week6-smoke-attempt-{index}")
                if len(captured) != 1 or pipeline.calls != ModelCallCounts():
                    raise RuntimeError("admission must read once and perform no model inference")
                # BER/error-count accounting is performed only AFTER admission;
                # enrollment truth never selects/replaces the candidate or retries.
                errors = selected_bit_errors(reference, captured[0])
                row = {"attempt_index": index, "source_window_id": source["window_id"],
                       "device_id": source["device_id"], "source_split": source["split"],
                       "source_label": source["label"], "read_count": len(captured),
                       "selected_bit_error_count": errors, "admission": asdict(attempt), "windows": []}
                if attempt.decision == "accept":
                    changed = apply_stream_attack(source, controls[source["window_id"]])
                    if changed["status"] != "quality_valid":
                        raise RuntimeError("predeclared position-jump control unexpectedly failed quality")
                    row["semantic_control"] = controls[source["window_id"]]
                    row["windows"] = run_window_controls(pipeline, source, changed["record"],
                                                          set(bundle.motion), set(bundle.detectors))
                    window_counts.update(window["condition"] + ":" + window["decision"] for window in row["windows"])
                elif pipeline.calls != ModelCallCounts() or verifier.active_session_ids:
                    raise RuntimeError("failed admission authorized inference or an active session")
                row["consumer_calls"] = asdict(pipeline.calls)
                row["sender_audit"] = public_audit(sender)
                row["verifier_audit"] = public_audit(verifier)
                evidence.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
                evidence.flush()
                attempts.append(row)
            finally:
                verifier.close_all_sessions()
            print(f"Completed {index + 1}/30 fresh single-read attempts: {attempt.decision}, {errors} selected-bit errors", flush=True)

    accepted = sum(row["admission"]["decision"] == "accept" for row in attempts)
    if accepted == 0:
        raise RuntimeError("no session admitted; partial evidence is retained, but model integration was not exercised")
    counts = {key: sum(row["consumer_calls"][key] for row in attempts)
              for key in ("preprocessing", "motion", "anomaly")}
    if any(count != accepted * 3 for count in counts.values()):
        raise RuntimeError("accepted-delivery counts do not reconcile")
    summary = {"planned_admission_attempts": 30, "response_reads": sum(row["read_count"] for row in attempts),
               "accepted_sessions": accepted, "rejected_sessions": 30 - accepted,
               "admission_outcomes": dict(Counter(row["admission"]["stage"] + ":" + row["admission"]["reason"]
                                                  for row in attempts)),
               "window_control_counts": dict(sorted(window_counts.items())), "consumer_callback_counts": counts,
               "frozen_motion_model_count": len(bundle.motion), "frozen_detector_count": len(bundle.detectors),
               "individual_motion_forward_calls": counts["motion"] * len(bundle.motion),
               "individual_detector_forward_calls": counts["anomaly"] * len(bundle.detectors),
               "rejected_window_model_calls": 0, "thresholds_changed": False,
               "training_executed": False, "latency_measured": False, "limitation": LIMITATION}
    write_json(output / "summary.json", summary)
    report = ["# Week 6 frozen-model v2 functional smoke", "", f"Source commit: `{source_commit}`", "",
              f"Fresh single-read attempts: 30; admitted: {accepted}; refused: {30 - accepted}.", "",
              f"Accepted composite deliveries: {counts['motion']}; motion models: 5; frozen detectors: 6.", "",
              "Every active session exercised bad-tag rejection, clean acceptance, exact-replay rejection,",
              "authenticated pre-tag position-jump inference, a 113/120 tracking-valid sender refusal,",
              "and subsequent valid acceptance. Refusals preserved model-call and sequence state.", "",
              "An anomaly flag is downstream metadata, not an authentication rejection. No expected",
              "classification or anomaly flag was enforced. Conventional models are the existing",
              "recorded seed-7 storage refits; all three saved SNN-32 checkpoints were used.", "",
              LIMITATION, "", "Enrollment/model loading/backend cold-start behavior were not timed.",
              "Audit is in memory. Durable I/O, full timing/outlier analysis and formal attack/reliability",
              "evaluations remain pending. JSONL output is outside the inference path.", ""]
    (output / "smoke-report.md").write_text("\n".join(report), encoding="utf-8", newline="\n")
    artifacts = {path.name: sha256(path) for path in sorted(output.iterdir())
                 if path.is_file() and path.name != "INCOMPLETE"}
    manifest = {"run_type": "week6-frozen-model-v2-functional-smoke-v1", "source_commit": source_commit,
                "source_worktree_dirty": False, "completed_utc": datetime.now(timezone.utc).isoformat(),
                "input_sha256": config["input_sha256"], "configuration_sha256": sha256(args.config),
                "supporting_configurations": {name: sha256(scoped_path(ROOT, config[name]))
                                              for name in ("puf_config", "auth_config", "attack_config")},
                "randomness": {"puf_seed": puf.random_seed, "manufacturing_domain": "week2-v1",
                               "read_and_credential_domains": "week6-smoke-v1; separate phase-specific streams",
                               "verifier_keys_and_handshake_nonces": "independent unseeded OS randomness"},
                "environment": {"python": platform.python_version(), "platform": platform.platform(),
                                "numpy": np.__version__, "scikit_learn": sklearn.__version__,
                                "torch": torch.__version__, "torch_threads": torch.get_num_threads(),
                                "galois": galois.__version__, "joblib": joblib.__version__},
                "training_executed": False, "threshold_selection_executed": False,
                "authentication_executed": True, "latency_measured": False,
                "summary": summary, "artifacts": artifacts}
    write_json(output / "manifest.json", manifest)
    write_json(output / "COMPLETE", {"manifest_sha256": sha256(output / "manifest.json"),
                                     "planned_admission_attempts": 30, "accepted_sessions": accepted})
    (output / "INCOMPLETE").unlink()
    print("PASS: fresh v2 admission, frozen composite inference and rejection/state controls reconciled", flush=True)
    print("No training, threshold selection, formal attack evaluation or latency measurement occurred", flush=True)
    print(json.dumps(summary, indent=2), flush=True)
    print(f"Saved results to {output}", flush=True)


if __name__ == "__main__":
    main()
