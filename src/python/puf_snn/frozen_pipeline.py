"""Hash-checked existing model bundle and small v2 boundary smoke controls.

No fitting, checkpoint selection, threshold selection or timing benchmark.
Only load trusted LOCAL pickle artifacts after checking the pinned manifests.
Hashes preserve provenance; they do not make arbitrary downloaded pickles safe.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import torch

from puf_snn.anomaly.features import FEATURE_NAMES
from puf_snn.attacks.evaluation import predict_detectors, predict_motion_models
from puf_snn.auth.session import Failure
from puf_snn.integration import processed_record_to_wire_window
from puf_snn.nod_diagnostics import load_verified_detectors
from puf_snn.pipeline_v2 import V2InferencePipeline
from puf_snn.snn.dataset import LABELS
from puf_snn.snn.model import create_model


SNN_SEEDS = (7, 17, 27)
ANOMALY_SEEDS = (6007, 6017, 6027)
CONVENTIONAL_NAMES = ("logistic_regression", "random_forest")
DETECTOR_NAMES = frozenset(
    f"anomaly_{kind}_seed{seed}" for kind in CONVENTIONAL_NAMES for seed in ANOMALY_SEEDS)


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def scoped_path(root: Path, relative: str) -> Path:
    raw = Path(relative)
    root = root.resolve()
    result = (root / raw).resolve()
    if raw.is_absolute() or ".." in raw.parts or not result.is_relative_to(root) or result == root:
        raise ValueError("artifact paths must stay within their configured directory")
    return result


def require_hash(path: Path, expected: str) -> None:
    if not path.is_file() or sha256(path) != expected:
        raise ValueError(f"missing or hash-mismatched frozen artifact: {path}; do not refit or retune")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_smoke_config(config: dict) -> None:
    fixed = {"config_version": "week6-frozen-smoke-v1", "source_split": "validation",
             "source_selection": "first_sorted_window_per_device_and_label", "device_count": 6,
             "puf_seed": 6767, "semantic_control": "position_jump:medium", "torch_threads": 1}
    if any(config.get(key) != value for key, value in fixed.items()):
        raise ValueError("this runner supports only the predeclared small smoke protocol")
    if set(config.get("bundles", {})) != {"snn32", "conventional", "anomaly"}:
        raise ValueError("all three historical model bundles are required")


def validate_normalization(normalization: dict, config: dict) -> None:
    mean = np.asarray(normalization["mean"], dtype=float)
    standard = np.asarray(normalization["standard_deviation"], dtype=float)
    if (normalization.get("fitted_from") != "train"
            or normalization.get("channels") != config["dataset"]["channels"]
            or mean.shape != (7,) or standard.shape != (7,)
            or not np.all(np.isfinite(mean)) or not np.all(np.isfinite(standard))
            or np.any(standard <= 0)):
        raise ValueError("frozen normalization must be finite, positive and training-only")


def validate_thresholds(thresholds: dict) -> None:
    if set(thresholds) != DETECTOR_NAMES:
        raise ValueError("all six predeclared frozen detectors are required")
    for name, entry in thresholds.items():
        expected_name = f"anomaly_{entry['kind']}_seed{entry['seed']}"
        value = entry["threshold"]
        if (expected_name != name or entry.get("selected_from") != "validation"
                or entry.get("comparison") != "score >= threshold"
                or type(value) not in (int, float) or not np.isfinite(value) or not 0 <= value <= 1):
            raise ValueError("threshold metadata is not a frozen validation-only decision")


@dataclass
class FrozenModelBundle:
    motion: dict = field(repr=False)
    detectors: dict = field(repr=False)
    artifact_hashes: dict

    def motion_predictions(self, sequence: np.ndarray) -> dict:
        array = np.asarray(sequence)
        if array.shape != (120, 7) or not np.all(np.isfinite(array)):
            raise ValueError("motion consumer requires finite [120, 7] input")
        outputs = predict_motion_models(self.motion, array[None], 1)
        result = {}
        for name, values in outputs.items():
            if values.shape != (1,) or int(values[0]) != values[0] or not 0 <= values[0] < len(LABELS):
                raise ValueError("invalid motion prediction")
            result[name] = LABELS[int(values[0])]
        return result

    def anomaly_predictions(self, features: np.ndarray) -> dict:
        array = np.asarray(features)
        if array.shape != (48,) or not np.all(np.isfinite(array)):
            raise ValueError("anomaly consumer requires finite [48] input")
        outputs = predict_detectors(self.detectors, array[None])
        result = {}
        for name, values in outputs.items():
            score = float(values["scores"][0])
            if values["scores"].shape != (1,) or not np.isfinite(score) or not 0 <= score <= 1:
                raise ValueError("invalid anomaly score")
            flag = bool(values["flags"][0])
            if flag != (score >= self.detectors[name]["threshold"]["threshold"]):
                raise ValueError("prediction disagrees with frozen threshold")
            result[name] = {"score": score, "flag": flag}
        return result


def load_frozen_bundle(root: Path, config: dict) -> FrozenModelBundle:
    """Check ALL required files before any joblib/torch deserialization.

    Conventional artifacts are the already recorded seed-7 storage refits, not
    a new fit or the original Week 4 unsaved estimator. Local ignored binaries
    must be present; absence is an error, never an invitation to train again.
    """
    validate_smoke_config(config)
    require_hash(scoped_path(root, config["input_path"]), config["input_sha256"])
    directories, manifests, paths, hashes = {}, {}, {}, {}
    for role, settings in config["bundles"].items():
        directory = scoped_path(root, settings["directory"])
        manifest_path = directory / "manifest.json"
        require_hash(manifest_path, settings["manifest_sha256"])
        if not (directory / "COMPLETE").is_file():
            raise ValueError("a historical bundle lacks its completion record")
        manifest = read_json(manifest_path)
        if manifest.get("input_sha256") != config["input_sha256"]:
            raise ValueError("historical bundle belongs to a different source dataset")
        directories[role], manifests[role] = directory, manifest
        hashes[f"{role}/manifest.json"] = sha256(manifest_path)

    def check(role: str, relative: str, *, local=False) -> Path:
        manifest = manifests[role]
        expected = (manifest["local_model_artifacts"][relative]["sha256"]
                    if local else manifest["artifacts"][relative])
        path = scoped_path(directories[role], relative)
        require_hash(path, expected)
        paths[(role, relative)] = path
        hashes[f"{role}/{relative}"] = expected
        return path

    snn_config = read_json(check("snn32", "config.json"))
    normalization = read_json(check("snn32", "normalization.json"))
    if (snn_config["dataset"]["labels"] != list(LABELS)
            or snn_config["dataset"]["time_steps"] != 120
            or snn_config["dataset"]["input_channels"] != 7
            or snn_config["model"]["hidden_neurons"] != 32
            or snn_config["training"]["random_seeds"] != list(SNN_SEEDS)
            or snn_config["training"]["training_seeds"] != [107, 117, 127]):
        raise ValueError("saved SNN-32 contract/seed mapping changed")
    validate_normalization(normalization, snn_config)
    for seed in SNN_SEEDS:
        check("snn32", f"seed-{seed}/model-state.pt")
    for name in CONVENTIONAL_NAMES:
        check("conventional", f"models/{name}-seed-7-storage-refit.joblib", local=True)
    thresholds = read_json(check("anomaly", "frozen-validation-thresholds.json"))
    validate_thresholds(thresholds)
    features = json.loads(check("anomaly", "anomaly-feature-names.json").read_text(encoding="utf-8"))
    if features != list(FEATURE_NAMES):
        raise ValueError("saved anomaly feature order changed")
    for name in sorted(DETECTOR_NAMES):
        check("anomaly", f"models/{name}.joblib")

    # Nothing below is reached if even the final required binary fails its hash.
    torch.set_num_threads(config["torch_threads"])
    motion = {}
    for seed in SNN_SEEDS:
        saved = torch.load(paths[("snn32", f"seed-{seed}/model-state.pt")],
                           map_location="cpu", weights_only=True)
        if (saved["seed"] != seed or saved["training_seed"] != seed + 100
                or tuple(saved["labels"]) != LABELS or saved["model_config"] != snn_config["model"]):
            raise ValueError("checkpoint metadata differs from frozen training decisions")
        model = create_model(saved["model_config"])
        model.load_state_dict(saved["state_dict"], strict=True)
        model.eval()
        motion[f"snn_32_seed_{seed}"] = {"kind": "snn", "model": model, "normalization": normalization}
    for name in CONVENTIONAL_NAMES:
        model = joblib.load(paths[("conventional", f"models/{name}-seed-7-storage-refit.joblib")])
        if model.n_features_in_ != 840 or set(model.classes_) != set(LABELS):
            raise ValueError("conventional storage refit has a different input/label contract")
        motion[f"{name}_seed_7_storage_refit"] = {"kind": name, "model": model}
    fitted, _ = load_verified_detectors(directories["anomaly"], manifests["anomaly"],
                                       thresholds, FEATURE_NAMES, joblib.load)
    detectors = {name: {"model": model, "threshold": thresholds[name]} for name, model in fitted.items()}
    return FrozenModelBundle(motion, detectors, hashes)


def select_smoke_sources(records: list[dict], device_count: int = 6) -> list[dict]:
    """Predeclared functional cohort, not selected by prediction or PUF outcome."""
    validation = [record for record in records if record["split"] == "validation"]
    devices = sorted({record["device_id"] for record in validation})
    if len(devices) != device_count:
        raise ValueError("validation device cohort differs from the smoke protocol")
    selected = []
    for device in devices:
        for label in LABELS:
            matches = sorted((record for record in validation
                              if record["device_id"] == device and record["label"] == label),
                             key=lambda record: record["window_id"])
            if not matches:
                raise ValueError("validation cohort lacks a device/class pair")
            selected.append(matches[0])
    return selected


def bad_tag_packet(packet: bytes) -> bytes:
    envelope = json.loads(packet)
    tag = envelope["authentication"]["tag_hex"]
    envelope["authentication"]["tag_hex"] = ("1" if tag[0] == "0" else "0") + tag[1:]
    return json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")


def run_window_controls(pipeline: V2InferencePipeline, source: dict, altered: dict,
                        expected_motion_names: set, expected_detector_names: set) -> list[dict]:
    """Three accepts, bad-tag/replay rejects and one pre-tag quality refusal.

    No expected class or anomaly flag is enforced. A failed ML target cannot
    make a functional smoke fail or cause a threshold/model change.
    """
    rows = []
    initial = pipeline.calls
    events = set()

    def invoke(condition, action, expected, *, unchanged=False, stage=None, reason=None):
        before_calls = pipeline.calls
        before_status = pipeline.verifier.session_status(pipeline.sender.session_id)
        before_sequence = pipeline.sender.next_to_send
        outcome = action()
        after = pipeline.verifier.session_status(pipeline.sender.session_id)
        if outcome.decision != expected or (stage and outcome.stage != stage) or (reason and outcome.reason != reason):
            raise RuntimeError(f"unexpected smoke outcome for {condition}")
        row = {"condition": condition, "decision": outcome.decision, "stage": outcome.stage,
               "reason": outcome.reason, "event_id": outcome.event_id,
               "sequence_number": outcome.sequence_number, "calls_before": asdict(before_calls),
               "calls_after": asdict(pipeline.calls), "last_accepted_before": before_status.last_accepted,
               "last_accepted_after": after.last_accepted}
        if unchanged:
            if pipeline.calls != before_calls or after != before_status or pipeline.sender.next_to_send != before_sequence:
                raise RuntimeError("rejected control changed inference calls or sequence state")
        else:
            counts = pipeline.calls
            if (counts.preprocessing != before_calls.preprocessing + 1 or counts.motion != before_calls.motion + 1
                    or counts.anomaly != before_calls.anomaly + 1 or after.accepted_count != before_status.accepted_count + 1
                    or after.last_accepted != outcome.sequence_number or outcome.event_id in events):
                raise RuntimeError("accepted control did not have one committed composite delivery")
            if (set(outcome.inference.motion) != expected_motion_names
                    or set(outcome.inference.anomaly) != expected_detector_names):
                raise RuntimeError("composite inference omitted a frozen model")
            events.add(outcome.event_id)
            row["motion_predictions"] = outcome.inference.motion
            row["anomaly_predictions"] = outcome.inference.anomaly
        rows.append(row)

    packet = pipeline.sender.seal_window(processed_record_to_wire_window(source))
    if isinstance(packet, Failure):
        raise RuntimeError(f"clean smoke source refused: {packet.reason}")
    invoke("bad_tag", lambda: pipeline.process_envelope(bad_tag_packet(packet)), "reject",
           unchanged=True, stage="window_verification", reason="invalid_tag")
    invoke("clean", lambda: pipeline.process_envelope(packet), "accept")
    invoke("exact_replay", lambda: pipeline.process_envelope(packet), "reject", unchanged=True,
           stage="window_verification")
    invoke("pre_tag_position_jump_medium", lambda: pipeline.process_record(altered), "accept")
    low_quality = deepcopy(source)
    for index, sample in enumerate(low_quality["samples"]):
        sample["tracking_valid"] = index < 113
    invoke("113_tracking_valid", lambda: pipeline.process_record(low_quality), "reject",
           unchanged=True, stage="sender_sealing", reason="data_quality_failure")
    invoke("next_valid_after_refusals", lambda: pipeline.process_record(source), "accept")
    final = pipeline.calls
    if (final.preprocessing - initial.preprocessing != 3 or final.motion - initial.motion != 3
            or final.anomaly - initial.anomaly != 3 or len(pipeline.consumed_event_ids) != 3
            or set(pipeline.consumed_event_ids) != events or pipeline.sender.incomplete or pipeline.verifier.incomplete):
        raise RuntimeError("smoke consumption/audit evidence does not reconcile")
    return rows
