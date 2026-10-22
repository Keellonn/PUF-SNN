"""Functional frozen-model comparison; no clean-commit prerequisite or default change.

Current source/config bytes are pinned before and rechecked after execution.
Uncommitted code is identified explicitly so work can be committed once per
session. This runner never rewrites a historical source manifest or result.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import gc
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess

from threadpoolctl import threadpool_limits

from puf_snn.attacks.evaluation import prepare_model_inputs
from puf_snn.attacks.stream import apply_stream_attack, iter_attack_cases
from puf_snn.auth.config import AuthConfig
from puf_snn.auth import binary_window, verifier as verifier_module
from puf_snn.auth.credential_verifier import (CredentialAdmissionService, CredentialVerifierRecord,
    CredentialVerifierStore, InMemoryCredentialVerifierKeyProvider)
from puf_snn.auth.sender import Sender
from puf_snn.auth.session import RegistryEntry, provision_device
from puf_snn.auth.verifier import Verifier
from puf_snn.frozen_pipeline import (FrozenModelBundle, load_frozen_bundle, read_json, require_hash,
    run_window_controls, scoped_path, sha256)
from puf_snn.pipeline_v2 import V2InferencePipeline
from puf_snn.puf.acquisition import SINGLE_READ, MAJORITY_3
from puf_snn.quality_dyadic import QUALITY_MODES, REFERENCE_VALIDATE_QUALITY, quality_validator_mode
from puf_snn.quality_validation import (VERSION, POLICIES, fingerprint, public_windows, reconcile,
    select_sources, source_hashes, validate_config)
from puf_snn.reconstruction import enroll
from puf_snn.snn.dataset import load_records


ROOT = Path(__file__).resolve().parents[3]


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def preflight(root, config):
    validate_config(config)
    frozen = read_json(scoped_path(root, config["frozen_config"]))
    bundle = load_frozen_bundle(root, frozen)
    sources = select_sources(load_records(scoped_path(root, frozen["input_path"])))
    auth = AuthConfig.load(scoped_path(root, frozen["auth_config"]))
    if auth != AuthConfig():
        raise ValueError("existing authentication policy changed")
    attack_config = read_json(scoped_path(root, frozen["attack_config"]))
    cases = {row["source_window_id"]: row for row in iter_attack_cases(sources, attack_config)
             if row["attack_type"] == "position_jump" and row["severity"] == "medium"}
    altered = {}
    for source in sources:
        outcome = apply_stream_attack(source, cases[source["window_id"]])
        if outcome["status"] != "quality_valid":
            raise ValueError("planned semantic control failed quality; do not replace it")
        altered[source["window_id"]] = outcome["record"]
    return frozen, bundle, sources, auth, altered


def public_preflight(bundle, sources):
    return dict(protocol=VERSION, checked_artifact_hashes=len(bundle.artifact_hashes),
        validation_sources=len(sources), configurations=3, acquisition_policies=2, quality_modes=2,
        planned_sessions=360, planned_quality_pairs=180, admissions_executed_by_preflight=0,
        note="controlled functional admissions, not noise/reliability samples or new accuracy estimates")


def make_peers(source, selected, auth, acquisition, captured):
    # Explicit nonsecret all-zero PUF-response control. This exercises real BCH,
    # verification/admission and confirmation, not the RO/shared-noise simulator.
    reference, credential = (0,) * 64, bytes.fromhex("000001a5")
    device, enrollment_id = source["device_id"], "week8-quality-functional-enrollment"
    helper = enroll(reference, credential, enrollment_id=enrollment_id)
    key_id = "week8-quality-functional-verifier"
    provider = InMemoryCredentialVerifierKeyProvider.generate(key_id)
    record = CredentialVerifierRecord.enroll(device_id=device, enrollment_id=enrollment_id,
        reconstruction_id=helper.config.version, verifier_key_id=key_id,
        credential4=credential, key_provider=provider)
    service = CredentialAdmissionService(CredentialVerifierStore([record]), provider)
    sender = Sender(provision_device(device, enrollment_id, helper), auth.session_config().limits,
                    admission_service=service)
    verifier = Verifier([RegistryEntry(device, enrollment_id, credential)], auth.session_config(), admission_service=service)

    def prepare(record):
        motion, anomaly = prepare_model_inputs(record)
        captured.append(dict(motion_sha256=fingerprint(motion, (120, 7)), anomaly_sha256=fingerprint(anomaly, (48,))))
        return motion, anomaly

    return V2InferencePipeline(sender, verifier, prepare, selected.motion_predictions, selected.anomaly_predictions,
                               acquisition_config=acquisition)


def run(root, config_path, output):
    config = read_json(config_path)
    validate_config(config)
    output = output.resolve()
    scope = (root / "results/week-8/keegan").resolve()
    if output == scope or not output.is_relative_to(scope) or output.exists():
        raise ValueError("choose an exclusively new output below results/week-8/keegan")
    # Reject symlink/junction ancestors rather than accidentally writing through
    # an evidence alias. No existing result directory is removed or overwritten.
    for parent in (output, *output.parents):
        if parent.is_symlink() or parent.is_junction():
            raise ValueError("linked output ancestors are unsupported")
        if parent == root:
            break
        if any((parent / name).exists() for name in ("manifest.json", "INCOMPLETE", "COMPLETE")):
            raise ValueError("do not nest this run in another evidence bundle")
    output.mkdir(parents=True, exist_ok=False)
    (output / ".gitattributes").write_text("* text eol=lf\n", encoding="utf-8", newline="\n")
    write_json(output / "INCOMPLETE", dict(protocol=VERSION, note="retain this directory on any failure"))
    pinned = source_hashes(root)
    write_json(output / "source-hashes.json", pinned)
    write_json(output / "config.json", config)
    try:
        if not gc.isenabled():
            raise ValueError("keep automatic garbage collection enabled")
        frozen, bundle, sources, auth, altered = preflight(root, config)
        write_json(output / "preflight.json", public_preflight(bundle, sources))
        write_json(output / "frozen-input-hashes.json", bundle.artifact_hashes)
        write_json(output / "source-selection.json", [{key: row[key] for key in
                   ("window_id", "source_trial_id", "device_id", "session_id", "split", "label")} for row in sources])
        keys = {(policy, condition["name"], source["window_id"]) for policy in POLICIES
                for condition in config["conditions"] for source in sources}
        cells = []
        policies = {SINGLE_READ.policy: SINGLE_READ, MAJORITY_3.policy: MAJORITY_3}
        with threadpool_limits(limits=1), (output / "cells.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for mode in QUALITY_MODES:
                with quality_validator_mode(mode):
                    for policy in POLICIES:
                        for condition in config["conditions"]:
                            selected = FrozenModelBundle({condition["motion"]: bundle.motion[condition["motion"]]},
                                {condition["anomaly"]: bundle.detectors[condition["anomaly"]]}, bundle.artifact_hashes)
                            for index, source in enumerate(sources):
                                captured = []
                                pipeline = make_peers(source, selected, auth, policies[policy], captured)
                                reads = []

                                def read_once():
                                    flips = config["controlled_read_flips"][len(reads)]
                                    value = tuple(int(bit in flips) for bit in range(64))
                                    reads.append(value)
                                    return value

                                try:
                                    attempt = pipeline.establish(read_once, f"week8-quality-{index}")
                                    if attempt.decision != "accept":
                                        raise ValueError("controlled admission failed; do not retry")
                                    rows = run_window_controls(pipeline, source, altered[source["window_id"]],
                                                              set(selected.motion), set(selected.detectors))
                                    status = pipeline.verifier.session_status(pipeline.sender.session_id)
                                    cell = dict(mode=mode, acquisition_policy=policy, configuration=condition["name"],
                                        source_window_id=source["window_id"], read_count=len(reads), admission=asdict(attempt),
                                        windows=public_windows(rows), model_inputs=captured, consumer_calls=asdict(pipeline.calls),
                                        final_state={key: getattr(status, key) for key in ("state", "accepted_count", "last_accepted")},
                                        consumed_events=len(pipeline.consumed_event_ids),
                                        incomplete=pipeline.sender.incomplete or pipeline.verifier.incomplete)
                                    cells.append(cell)
                                    stream.write(json.dumps(cell, sort_keys=True, allow_nan=False) + "\n")
                                    stream.flush()
                                finally:
                                    pipeline.verifier.close_all_sessions()
                            print(f"Checked {mode} / {policy} / {condition['name']}: 30 controlled sessions", flush=True)
        summary = reconcile(cells, keys)
        if (binary_window.validate_quality is not REFERENCE_VALIDATE_QUALITY
                or verifier_module.validate_quality is not REFERENCE_VALIDATE_QUALITY or not gc.isenabled()):
            raise ValueError("reference validator restoration or enabled-GC check failed")
        if source_hashes(root) != pinned:
            raise ValueError("source/config changed during validation")
        require_hash(scoped_path(root, frozen["input_path"]), frozen["input_sha256"])
        for name, digest in bundle.artifact_hashes.items():
            role, relative = name.split("/", 1)
            require_hash(scoped_path(root, frozen["bundles"][role]["directory"]) / relative, digest)
        write_json(output / "summary.json", summary)
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True)
        artifacts = {path.name: sha256(path) for path in output.iterdir() if path.is_file() and path.name != "INCOMPLETE"}
        write_json(output / "manifest.json", dict(protocol=VERSION, status="PASS", base_commit=result.stdout.strip(),
            source_commit_is_complete_identity=False, current_source_hashes_sha256=sha256(output / "source-hashes.json"),
            environment=dict(python=platform.python_version(), system=platform.system(), architecture=platform.machine(),
                packages={name: importlib.metadata.version(name) for name in
                    ("numpy", "scikit-learn", "torch", "galois", "numba", "scipy", "jsonschema")}),
            artifacts=artifacts, summary=summary, training_executed=False, threshold_selection_executed=False,
            latency_measured=False, default_changed=False, noise_reliability_measured=False, automatic_gc_enabled=True,
            limitation="Fixed validation sources and controlled correctable reads; no new accuracy, reliability, security or latency claim."))
        write_json(output / "COMPLETE", dict(manifest_sha256=sha256(output / "manifest.json")))
        (output / "INCOMPLETE").unlink()  # Remove only this run's own completed sentinel.
        print(json.dumps(dict(status="PASS", **summary), indent=2), flush=True)
    except BaseException as error:
        if not (output / "failure.json").exists():
            write_json(output / "failure.json", dict(status="INCOMPLETE", exception=type(error).__name__,
                       note="See local terminal; no historical file was modified and no automatic retry occurred."))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/week8_quality_validation.json")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.preflight:
        if args.output is not None:
            parser.error("preflight writes no result bundle; omit --output")
        config = read_json(args.config)
        _, bundle, sources, _, _ = preflight(ROOT, config)
        print(json.dumps(public_preflight(bundle, sources), indent=2))
    elif args.output is None:
        parser.error("provide a new --output directory or request --preflight")
    else:
        run(ROOT, args.config, args.output)


if __name__ == "__main__":
    main()
