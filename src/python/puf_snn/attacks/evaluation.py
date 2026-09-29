"""
this file keeps stream construction, model inputs and authenticated delivery separate
the same accepted record supplies motion classification and downstream anomaly scores
"""

from __future__ import annotations

from collections import Counter
from itertools import zip_longest

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


def evaluate_authenticated_cases(records: list[dict], cohort: dict, models: dict, detectors: dict, auth_config: AuthConfig, establish_session, material, case_limit: int, progress=None) -> dict:
    if type(case_limit) is not int or not 1 <= case_limit <= 100 or case_limit >= auth_config.max_windows:
        raise ValueError("session batches must be at most 100 and below the configured window limit")
    sources = {record["window_id"]: record for record in records}
    motion = {name: [] for name in models}
    anomaly = {name: {"scores": [], "flags": []} for name in detectors}
    evidence = []
    consumer = composite_consumer(models, detectors)
    session_count = 0
    for start in range(0, len(cohort["cases"]), case_limit):
        sender, verifier, _ = establish_session(auth_config, material)
        session_count += 1
        matched = [0]
        def preprocess(record: dict) -> tuple[np.ndarray, np.ndarray]:
            inputs = prepare_model_inputs(record)
            index = current_index
            if not np.array_equal(inputs[0], cohort["sequences"][index]) or not np.array_equal(inputs[1], cohort["anomaly_features"][index]):
                raise RuntimeError("accepted sensor data does not match the paired unauthenticated inputs")
            matched[0] += 1
            return inputs
        gate = ExactlyOnceClassifierRelease(verifier, preprocess, consumer)
        try:
            for current_index in range(start, min(start + case_limit, len(cohort["cases"]))):
                case = cohort["cases"][current_index]
                outcome = apply_stream_attack(sources[case["source_window_id"]], case)
                if outcome["status"] != "quality_valid":
                    raise RuntimeError("deterministic reconstruction changed between paired evaluation conditions")
                packet = sender.seal_window(processed_record_to_wire_window(outcome["record"]))
                if isinstance(packet, Failure):
                    raise RuntimeError(f"sender unexpectedly rejected a constructed case: {packet.reason}")
                result = verifier.verify_window(packet)
                if result.result != "accept":
                    raise RuntimeError(f"a legitimate tagged Tier 2 window was rejected: {result.reason}; stop and investigate the harness")
                prediction = gate.deliver(result)
                for name in motion:
                    motion[name].append(prediction["motion"][name])
                for name in anomaly:
                    anomaly[name]["scores"].append(prediction["anomaly"][name]["score"])
                    anomaly[name]["flags"].append(prediction["anomaly"][name]["flag"])
                status = verifier.session_status(sender.session_id)
                if status.last_accepted != result.sequence_number:
                    raise RuntimeError("downstream inference changed the committed authentication sequence")
                evidence.append({"case_id": case["case_id"], "source_window_id": case["source_window_id"], "decision": result.result, "reason": result.reason, "event_id": result.event_id, "device_id": result.device_id, "session_id": sender.session_id.hex(), "sequence_number": result.sequence_number, "authenticated_bytes_sha256": result.authenticated_bytes_sha256, "verifier_last_accepted_after_models": status.last_accepted, "accepted_model_inputs_match": True, "motion_model_calls": len(models), "anomaly_model_calls": len(detectors)})
            if matched[0] != len(gate.consumed_event_ids):
                raise RuntimeError("at-most-once delivery evidence does not reconcile")
            if verifier.incomplete or sender.incomplete:
                raise RuntimeError("authentication evidence is incomplete")
        finally:
            verifier.close_all_sessions()
        if progress is not None:
            progress(len(evidence), len(cohort["cases"]))
    return {"motion": {name: np.asarray(values, dtype=np.int64) for name, values in motion.items()}, "anomaly": {name: {"scores": np.asarray(values["scores"]), "flags": np.asarray(values["flags"], dtype=bool)} for name, values in anomaly.items()}, "evidence": evidence, "session_count": session_count}


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
