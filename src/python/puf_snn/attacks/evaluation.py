"""
this file keeps stream construction, model inputs and authenticated delivery separate
the same accepted record supplies motion classification and downstream anomaly scores
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from itertools import zip_longest
from pathlib import Path
import time

import numpy as np
import torch

from puf_snn.anomaly.detector import anomaly_scores, binary_metrics, source_cluster_intervals
from puf_snn.anomaly.features import record_to_anomaly_features
from puf_snn.attacks.stream import apply_stream_attack, iter_attack_cases
from puf_snn.auth.config import AuthConfig
from puf_snn.auth.session import Failure
from puf_snn.integration import ExactlyOnceClassifierRelease, processed_record_to_wire_window
from puf_snn.snn.dataset import LABELS, apply_channel_normalization, record_to_sequence
from puf_snn.snn.evaluation import calculate_metrics, predict_indexes


def assert_plan_matches(records: list[dict], config: dict, planned_cases: list[dict]) -> None:
    # regenerate metadata to catch omissions, edited seeds and cases moved to another split
    for expected, saved in zip_longest(iter_attack_cases(records, config), planned_cases):
        if expected != saved:
            raise ValueError("saved attack plan differs from the complete reproducible source/configuration plan")


def assert_case_split_separation(cases: list[dict]) -> None:
    owners = {}
    identifiers = set()
    for case in cases:
        if case["case_id"] in identifiers:
            raise ValueError("duplicate case identifier")
        identifiers.add(case["case_id"])
        if case["split"] not in ("train", "validation", "test"):
            raise ValueError("invalid derived-case split")
        for field in ("source_window_id", "source_trial_id"):
            key = (field, case[field])
            if key in owners and owners[key] != case["split"]:
                raise ValueError(f"{field} crosses splits")
            owners[key] = case["split"]


def prepare_model_inputs(record: dict) -> tuple[np.ndarray, np.ndarray]:
    return record_to_sequence(record), record_to_anomaly_features(record)


def construct_cohorts(records: list[dict], planned_cases: list[dict], progress=None) -> tuple[dict, list[dict]]:
    assert_case_split_separation(planned_cases)
    sources = {record["window_id"]: record for record in records}
    groups = {split: {"cases": [], "sequences": [], "anomaly_features": []} for split in ("train", "validation", "test")}
    outcomes = []
    for index, case in enumerate(planned_cases):
        outcome = apply_stream_attack(sources[case["source_window_id"]], case)
        row = {"case_id": case["case_id"], "source_window_id": case["source_window_id"], "source_trial_id": case["source_trial_id"], "split": case["split"], "attack_type": case["attack_type"], "severity": case["severity"], "status": outcome["status"], "reason": outcome["reason"], "details": outcome["details"], "authentication": "not_attempted"}
        if outcome["status"] == "quality_valid":
            sequence, features = prepare_model_inputs(outcome["record"])
            group = groups[case["split"]]
            group["cases"].append(case)
            group["sequences"].append(sequence)
            group["anomaly_features"].append(features)
        outcomes.append(row)
        if progress is not None and (index + 1) % 500 == 0:
            progress(index + 1, len(planned_cases))
    for split, group in groups.items():
        if not group["cases"]:
            raise ValueError(f"no quality-valid {split} cases")
        group["sequences"] = np.stack(group["sequences"])
        group["anomaly_features"] = np.stack(group["anomaly_features"])
        clean_count = sum(not case["is_anomaly"] for case in group["cases"])
        expected_clean = sum(record["split"] == split for record in records)
        if clean_count != expected_clean:
            raise ValueError("a clean control failed construction; investigate before training")
    return groups, outcomes


def predict_motion_models(models: dict, sequences: np.ndarray, batch_size: int) -> dict[str, np.ndarray]:
    predictions = {}
    label_indexes = {label: index for index, label in enumerate(LABELS)}
    for name, entry in models.items():
        if entry["kind"] == "snn":
            normalized = apply_channel_normalization(sequences, entry["normalization"])
            predictions[name] = predict_indexes(entry["model"], normalized, batch_size, torch.device("cpu"))
        else:
            labels = entry["model"].predict(sequences.reshape(len(sequences), -1))
            predictions[name] = np.asarray([label_indexes[label] for label in labels], dtype=np.int64)
    return predictions


def predict_detectors(detectors: dict, features: np.ndarray) -> dict[str, dict]:
    results = {}
    for name, entry in detectors.items():
        scores = anomaly_scores(entry["model"], features)
        results[name] = {"scores": scores, "flags": scores >= entry["threshold"]["threshold"]}
    return results


def composite_consumer(models: dict, detectors: dict):
    def consume(inputs: tuple[np.ndarray, np.ndarray]) -> dict:
        sequence, features = inputs
        # both results come from this one released record; the anomaly flag is not an authentication decision
        motion = predict_motion_models(models, sequence[None], 1)
        anomaly = predict_detectors(detectors, features[None])
        return {"motion": {name: int(values[0]) for name, values in motion.items()}, "anomaly": {name: {"score": float(values["scores"][0]), "flag": bool(values["flags"][0])} for name, values in anomaly.items()}}
    return consume


def _checkpoint_digest(row: dict) -> str:
    encoded = json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_authentication_checkpoint(path: Path | None, cases: list[dict], models: dict, detectors: dict) -> tuple[list[dict], str]:
    rows = []
    previous = "0" * 64
    events = set()
    sequences = set()
    if path is None or not path.exists():
        return rows, previous
    with path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if not line.endswith("\n"):
                raise ValueError("authentication checkpoint has an incomplete final line; preserve it and stop")
            row = json.loads(line)
            saved_hash = row.pop("row_sha256")
            if row.get("previous_sha256") != previous or _checkpoint_digest(row) != saved_hash:
                raise ValueError("authentication checkpoint hash chain does not match")
            if index >= len(cases) or row["case_id"] != cases[index]["case_id"]:
                raise ValueError("authentication checkpoint does not match the ordered test cases")
            prediction = row["prediction"]
            if set(prediction["motion"]) != set(models) or set(prediction["anomaly"]) != set(detectors):
                raise ValueError("checkpoint model names differ from the frozen experiment")
            for value in prediction["motion"].values():
                if type(value) is not int or not 0 <= value < len(LABELS):
                    raise ValueError("invalid checkpoint motion prediction")
            for name, value in prediction["anomaly"].items():
                score = value["score"]
                if type(score) not in (int, float) or not np.isfinite(score) or not 0 <= score <= 1 or type(value["flag"]) is not bool or value["flag"] != (score >= detectors[name]["threshold"]["threshold"]):
                    raise ValueError("invalid checkpoint anomaly prediction")
            evidence = row["evidence"]
            sequence = (evidence["session_id"], evidence["sequence_number"])
            if evidence["case_id"] != row["case_id"] or evidence["source_window_id"] != cases[index]["source_window_id"] or evidence["decision"] != "accept" or evidence["accepted_model_inputs_match"] is not True or evidence["event_id"] in events or sequence in sequences:
                raise ValueError("invalid or duplicated accepted-delivery checkpoint")
            events.add(evidence["event_id"])
            sequences.add(sequence)
            rows.append(row)
            previous = saved_hash
    return rows, previous


def evaluate_authenticated_cases(records: list[dict], cohort: dict, models: dict, detectors: dict, auth_config: AuthConfig, establish_session, material, case_limit: int, progress=None, checkpoint_path: Path | None = None, session_events_path: Path | None = None) -> dict:
    if type(case_limit) is not int or not 1 <= case_limit <= 100 or case_limit >= auth_config.max_windows:
        raise ValueError("session batches must be at most 100 and below the configured window limit")
    sources = {record["window_id"]: record for record in records}
    motion = {name: [] for name in models}
    anomaly = {name: {"scores": [], "flags": []} for name in detectors}
    evidence = []
    saved_rows, previous_hash = read_authentication_checkpoint(checkpoint_path, cohort["cases"], models, detectors)
    consumer = composite_consumer(models, detectors)
    sender = verifier = gate = None
    session_started = 0
    session_cases = 0
    matched = [0]
    current_index = 0
    expected_inputs = None
    renewal_age_ns = int(auth_config.session_ttl_ms * 1_000_000 * 0.8)
    checkpoint = checkpoint_path.open("a", encoding="utf-8", newline="\n") if checkpoint_path is not None else None
    session_events = session_events_path.open("a", encoding="utf-8", newline="\n") if session_events_path is not None else None

    def record_session_event(stage: str, reason: str, case_id: str | None, session_id: str | None) -> None:
        if session_events is not None:
            row = {"stage": stage, "reason": reason, "case_id": case_id, "session_id": session_id, "classifier_calls_for_failed_attempt": 0, "anomaly_calls_for_failed_attempt": 0}
            session_events.write(json.dumps(row, sort_keys=True, allow_nan=False) + "\n")
            session_events.flush()

    def close_session() -> None:
        nonlocal sender, verifier, gate
        if verifier is not None:
            if matched[0] != len(gate.consumed_event_ids):
                raise RuntimeError("at-most-once delivery evidence does not reconcile")
            if verifier.incomplete or sender.incomplete:
                raise RuntimeError("authentication evidence is incomplete")
            verifier.close_all_sessions()
        sender = verifier = gate = None

    def preprocess(record: dict) -> tuple[np.ndarray, np.ndarray]:
        inputs = prepare_model_inputs(record)
        if not np.array_equal(inputs[0], expected_inputs[0]) or not np.array_equal(inputs[1], expected_inputs[1]):
            raise RuntimeError("accepted sensor data does not match the paired unauthenticated inputs")
        matched[0] += 1
        return inputs

    def open_session() -> None:
        nonlocal sender, verifier, gate, session_started, session_cases
        close_session()
        # start the age estimate before the handshake so it is conservative for the sender's TTL
        session_started = time.monotonic_ns()
        sender, verifier, _ = establish_session(auth_config, material)
        gate = ExactlyOnceClassifierRelease(verifier, preprocess, consumer)
        session_cases = 0
        matched[0] = 0

    def append_prediction(prediction: dict, row: dict) -> None:
        for name in motion:
            motion[name].append(prediction["motion"][name])
        for name in anomaly:
            anomaly[name]["scores"].append(prediction["anomaly"][name]["score"])
            anomaly[name]["flags"].append(prediction["anomaly"][name]["flag"])
        evidence.append(row)

    try:
        for saved in saved_rows:
            append_prediction(saved["prediction"], saved["evidence"])
        if saved_rows and progress is not None:
            progress(len(evidence), len(cohort["cases"]))
        for current_index in range(len(saved_rows), len(cohort["cases"])):
            case = cohort["cases"][current_index]
            outcome = apply_stream_attack(sources[case["source_window_id"]], case)
            if outcome["status"] != "quality_valid":
                raise RuntimeError("deterministic reconstruction changed between paired evaluation conditions")
            # recovery reconstructs test windows only and never fits a model or chooses another threshold
            expected_inputs = prepare_model_inputs(outcome["record"])
            if "sequences" in cohort and (not np.array_equal(expected_inputs[0], cohort["sequences"][current_index]) or not np.array_equal(expected_inputs[1], cohort["anomaly_features"][current_index])):
                raise RuntimeError("reconstructed inputs differ from the original cohort")
            window = processed_record_to_wire_window(outcome["record"])
            for attempt in range(2):
                if sender is None or session_cases >= case_limit or time.monotonic_ns() - session_started >= renewal_age_ns:
                    open_session()
                session_id = sender.session_id.hex()
                packet = sender.seal_window(window)
                if isinstance(packet, Failure):
                    record_session_event("sender", packet.reason, case["case_id"], session_id)
                    if packet.reason == "expired_session" and attempt == 0:
                        open_session()
                        continue
                    raise RuntimeError(f"sender unexpectedly rejected a constructed case: {packet.reason}")
                result = verifier.verify_window(packet)
                if result.result != "accept":
                    record_session_event("verifier", result.reason, case["case_id"], session_id)
                    if result.reason == "expired_session" and attempt == 0:
                        open_session()
                        continue
                    raise RuntimeError(f"a legitimate tagged Tier 2 window was rejected: {result.reason}; stop and investigate the harness")
                committed = verifier.session_status(sender.session_id)
                if committed.last_accepted != result.sequence_number:
                    raise RuntimeError("authentication sequence was not committed before model execution")
                prediction = gate.deliver(result)
                status = verifier.session_status(sender.session_id)
                if status.last_accepted is not None and status.last_accepted != result.sequence_number:
                    raise RuntimeError("downstream inference changed the committed authentication sequence")
                row = {"case_id": case["case_id"], "source_window_id": case["source_window_id"], "decision": result.result, "reason": result.reason, "event_id": result.event_id, "device_id": result.device_id, "session_id": session_id, "sequence_number": result.sequence_number, "authenticated_bytes_sha256": result.authenticated_bytes_sha256, "verifier_last_accepted_before_models": committed.last_accepted, "verifier_last_accepted_after_models": status.last_accepted, "session_state_after_models": status.state, "accepted_model_inputs_match": True, "motion_model_calls": len(models), "anomaly_model_calls": len(detectors)}
                if checkpoint is not None:
                    saved = {"case_id": case["case_id"], "prediction": prediction, "evidence": row, "previous_sha256": previous_hash}
                    previous_hash = _checkpoint_digest(saved)
                    saved["row_sha256"] = previous_hash
                    checkpoint.write(json.dumps(saved, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
                    checkpoint.flush()
                append_prediction(prediction, row)
                session_cases += 1
                break
            if progress is not None and (len(evidence) % case_limit == 0 or len(evidence) == len(cohort["cases"])):
                progress(len(evidence), len(cohort["cases"]))
    finally:
        try:
            close_session()
        finally:
            if checkpoint is not None:
                checkpoint.close()
            if session_events is not None:
                session_events.close()
    return {"motion": {name: np.asarray(values, dtype=np.int64) for name, values in motion.items()}, "anomaly": {name: {"scores": np.asarray(values["scores"]), "flags": np.asarray(values["flags"], dtype=bool)} for name, values in anomaly.items()}, "evidence": evidence, "session_count": len({row["session_id"] for row in evidence}), "reused_checkpoint_cases": len(saved_rows)}


def summarize_construction(outcomes: list[dict]) -> dict:
    groups = {}
    for row in outcomes:
        name = f"{row['split']}:{row['attack_type']}:{row['severity']}"
        groups.setdefault(name, Counter())[row["status"]] += 1
    return {name: {"planned": sum(counts.values()), "quality_valid": counts["quality_valid"], "construction_failure": counts["construction_failure"], "quality_failure": counts["quality_failure"]} for name, counts in sorted(groups.items())}


def summarize_predictions(cases: list[dict], motion: dict, anomaly: dict, config: dict) -> dict:
    expected_motion = np.asarray([LABELS.index(case["motion_label"]) for case in cases])
    expected_anomaly = np.asarray([case["is_anomaly"] for case in cases])
    groups = {"all_quality_valid": np.arange(len(cases))}
    for index, case in enumerate(cases):
        name = f"{case['attack_type']}:{case['severity']}"
        groups.setdefault(name, []).append(index)
    groups = {name: np.asarray(indexes, dtype=np.int64) for name, indexes in groups.items()}
    motion_results = {name: {group: calculate_metrics(expected_motion[indexes], predictions[indexes]) for group, indexes in groups.items()} for name, predictions in motion.items()}
    anomaly_results = {}
    medium_high = np.asarray([case["severity"] in ("medium", "high") for case in cases])
    for name, predictions in anomaly.items():
        flags = predictions["flags"]
        measured = {group: binary_metrics(expected_anomaly[indexes], flags[indexes]) for group, indexes in groups.items()}
        for group, indexes in groups.items():
            if group.endswith(":medium") or group.endswith(":high"):
                measured[group]["recall_target"] = config["medium_high_detection_target"]
                measured[group]["recall_target_met"] = measured[group]["recall"] >= config["medium_high_detection_target"]
        if medium_high.any():
            measured["medium_high_quality_valid"] = binary_metrics(expected_anomaly[medium_high], flags[medium_high])
            measured["medium_high_quality_valid"]["recall_target"] = config["medium_high_detection_target"]
            measured["medium_high_quality_valid"]["recall_target_met"] = measured["medium_high_quality_valid"]["recall"] >= config["medium_high_detection_target"]
        measured["source_cluster_uncertainty"] = source_cluster_intervals(cases, flags, config["bootstrap_repetitions"], config["bootstrap_seed"])
        anomaly_results[name] = measured
    return {"source_count": len({case["source_window_id"] for case in cases}), "quality_valid_case_count": len(cases), "motion": motion_results, "anomaly": anomaly_results}
