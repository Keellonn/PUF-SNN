"""Reconcile saved Tier-2 evidence without constructing attacks or running models.

The historical run is read-only. Counts use cases, not model-seed replications.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np


LABELS = ("nod", "shake", "look_left_return", "look_right_return", "still")
STATUSES = ("quality_valid", "construction_failure", "quality_failure")
INPUT_ARTIFACTS = (
    "config.json", "attack-config.json", "construction-summary.json",
    "construction-outcomes.jsonl", "frozen-validation-thresholds.json",
    "unauthenticated-test-predictions.jsonl", "authenticated-test-predictions.jsonl",
    "accepted-delivery-evidence.jsonl", "results.json",
)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path):
    def invalid_constant(value):
        raise ValueError(f"nonfinite JSON constant in {path.name}: {value}")
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key in {path.name}: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=invalid_constant,
                      object_pairs_hook=unique_object)


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError(f"blank line in {path.name}:{number}")
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"non-object row in {path.name}:{number}")
            rows.append(row)
    return rows


def unique_index(rows: list[dict], field: str) -> dict:
    result = {}
    for row in rows:
        value = row[field]
        if value in result:
            raise ValueError(f"duplicate {field}: {value}")
        result[value] = row
    return result


@lru_cache(maxsize=64)
def _log_binomial_coefficients(trials: int) -> np.ndarray:
    return np.asarray([math.lgamma(trials + 1) - math.lgamma(index + 1)
                       - math.lgamma(trials - index + 1) for index in range(trials + 1)])


def _binomial_upper(successes: int, trials: int) -> float:
    if successes == trials:
        return 1.0
    if successes == 0:
        return -math.expm1(math.log(.025) / trials)
    indexes = np.arange(successes + 1)
    coefficients = _log_binomial_coefficients(trials)[:successes + 1]
    lower, upper = 0.0, 1.0
    # Invert P[X <= successes] = .025. Log-PMF evaluation avoids overflow.
    for _ in range(64):
        probability = (lower + upper) / 2
        cdf = float(np.exp(coefficients + indexes * math.log(probability)
                           + (trials - indexes) * math.log1p(-probability)).sum())
        if cdf > .025:
            lower = probability
        else:
            upper = probability
    return (lower + upper) / 2


def binomial_interval(successes: int, trials: int) -> list[float] | None:
    """Two-sided 95% Clopper-Pearson interval; N/A when no cases were eligible.

    This is a descriptive conditional binomial interval, not an adjustment for
    shared device/session effects or a real-world generalization guarantee.
    """
    if not 0 <= successes <= trials:
        raise ValueError("invalid binomial counts")
    if trials == 0:
        return None
    lower = 0.0 if successes == 0 else 1 - _binomial_upper(trials - successes, trials)
    upper = _binomial_upper(successes, trials)
    return [lower, upper]


def classification_metrics(truth: list[str], prediction: list[str]) -> dict:
    if len(truth) != len(prediction):
        raise ValueError("unpaired motion predictions")
    if not truth:
        return {"sample_count": 0, "accuracy": None, "macro_f1": None,
                "confusion_matrix": None, "per_class": None}
    indexes = {label: index for index, label in enumerate(LABELS)}
    matrix = np.zeros((len(LABELS), len(LABELS)), dtype=np.int64)
    for expected, predicted in zip(truth, prediction):
        if expected not in indexes or predicted not in indexes:
            raise ValueError("unknown motion label")
        matrix[indexes[expected], indexes[predicted]] += 1
    per_class = {}
    for index, label in enumerate(LABELS):
        tp, support, predicted_count = int(matrix[index, index]), int(matrix[index].sum()), int(matrix[:, index].sum())
        per_class[label] = {
            "precision": tp / predicted_count if predicted_count else 0.0,
            "recall": tp / support if support else 0.0,
            "f1": 2 * tp / (support + predicted_count) if support + predicted_count else 0.0,
            "support": support,
        }
    return {"sample_count": len(truth), "accuracy": float(np.trace(matrix) / matrix.sum()),
            "macro_f1": float(np.mean([row["f1"] for row in per_class.values()])),
            "confusion_matrix": matrix.tolist(), "per_class": per_class}


def construction_counts(outcomes: list[dict]) -> dict:
    groups = defaultdict(Counter)
    owners = {}
    unique_index(outcomes, "case_id")
    for row in outcomes:
        if row["split"] not in ("train", "validation", "test") or row["status"] not in STATUSES:
            raise ValueError("unknown construction split or status")
        for field in ("source_window_id", "source_trial_id"):
            key = (field, row[field])
            if key in owners and owners[key] != row["split"]:
                raise ValueError(f"{field} crosses splits")
            owners[key] = row["split"]
        counts = groups[f'{row["split"]}:{row["attack_type"]}:{row["severity"]}']
        counts["planned"] += 1
        counts[row["status"]] += 1
    return {key: {name: counts[name] for name in ("planned", *STATUSES)}
            for key, counts in sorted(groups.items())}


def reconcile(outcomes, authenticated, unprotected, evidence, thresholds, config, attack_config) -> dict:
    """Fail closed on incomplete cohorts, changed labels, thresholds or delivery evidence."""
    construction = construction_counts(outcomes)
    by_case = unique_index(outcomes, "case_id")
    conditions = [("clean", "clean")] + [
        (attack["name"], severity) for attack in attack_config["attacks"]
        for severity in attack_config["severity_names"]
    ]
    if len(set(conditions)) != len(conditions):
        raise ValueError("duplicate configured attack condition")
    source_conditions = defaultdict(set)
    trial_sources = {}
    for row in outcomes:
        key = (row["split"], row["source_window_id"])
        condition = (row["attack_type"], row["severity"])
        if condition not in conditions or condition in source_conditions[key]:
            raise ValueError("duplicate or unexpected source condition")
        source_conditions[key].add(condition)
        trial = row["source_trial_id"]
        if trial in trial_sources and trial_sources[trial] != row["source_window_id"]:
            raise ValueError("source trial contains multiple windows; interval assumptions need revision")
        trial_sources[trial] = row["source_window_id"]
    if any(values != set(conditions) for values in source_conditions.values()):
        raise ValueError("incomplete planned source cohort")
    expected = {row["case_id"] for row in outcomes if row["split"] == "test" and row["status"] == "quality_valid"}
    auth = unique_index(authenticated, "case_id")
    plain = unique_index(unprotected, "case_id")
    deliveries = unique_index(evidence, "case_id")
    if not expected or set(auth) != expected or set(plain) != expected or set(deliveries) != expected:
        raise ValueError("quality-valid test cases, predictions and delivery evidence do not match")
    motion_names = {f"motion_{kind}_seed{seed}" for kind in ("logistic_regression", "random_forest", "snn")
                    for seed in config["motion_model_seeds"]}
    anomaly_names = {f"anomaly_{kind}_seed{seed}" for kind in ("logistic_regression", "random_forest")
                     for seed in config["anomaly_model_seeds"]}
    if set(thresholds) != anomaly_names:
        raise ValueError("unexpected frozen detector set")
    for name, threshold in thresholds.items():
        if (threshold["selected_from"] != "validation" or threshold["comparison"] != "score >= threshold"
                or not math.isfinite(threshold["threshold"])
                or not 0 <= threshold["validation_clean_fpr"] <= config["validation_clean_fpr_limit"]):
            raise ValueError(f"invalid validation-only threshold: {name}")
        if threshold["validation_clean_false_positives"] / threshold["validation_clean_count"] != threshold["validation_clean_fpr"]:
            raise ValueError("validation FPR does not match its counts")
    clean_sources = {}
    events, sequences, max_difference = set(), set(), 0.0
    for case_id, prediction in auth.items():
        outcome, paired, delivery = by_case[case_id], plain[case_id], deliveries[case_id]
        for field in ("source_window_id", "source_trial_id", "attack_type", "severity"):
            if prediction[field] != outcome[field] or paired[field] != outcome[field]:
                raise ValueError("case metadata differs from construction")
        if prediction["motion_label"] != paired["motion_label"] or prediction["motion_label"] not in LABELS:
            raise ValueError("paired motion labels differ or are unknown")
        for record in (prediction, paired):
            if type(record["is_anomaly"]) is not bool or record["is_anomaly"] != (outcome["attack_type"] != "clean"):
                raise ValueError("invalid anomaly label")
            if set(record["motion"]) != motion_names or set(record["anomaly"]) != anomaly_names:
                raise ValueError("inconsistent model set")
            if any(label not in LABELS for label in record["motion"].values()):
                raise ValueError("unknown predicted motion label")
            for name, value in record["anomaly"].items():
                if (type(value["flag"]) is not bool or type(value["score"]) not in (int, float)
                        or not math.isfinite(value["score"]) or not 0 <= value["score"] <= 1):
                    raise ValueError("invalid saved anomaly score or flag")
                if value["flag"] != (value["score"] >= thresholds[name]["threshold"]):
                    raise ValueError("saved flag differs from frozen threshold")
        if prediction["motion"] != paired["motion"]:
            raise ValueError("authenticated motion predictions differ")
        for name in anomaly_names:
            left, right = prediction["anomaly"][name], paired["anomaly"][name]
            difference = abs(left["score"] - right["score"])
            max_difference = max(max_difference, difference)
            if left["flag"] != right["flag"] or difference > 1e-12:
                raise ValueError("authenticated anomaly outputs differ")
        event, sequence = delivery["event_id"], (delivery["session_id"], delivery["sequence_number"])
        if event in events or sequence in sequences:
            raise ValueError("duplicate accepted event or session sequence")
        events.add(event)
        sequences.add(sequence)
        if (delivery["decision"] != "accept" or delivery["reason"] != "accepted"
                or delivery["source_window_id"] != prediction["source_window_id"]
                or delivery["accepted_model_inputs_match"] is not True
                or delivery["motion_model_calls"] != len(motion_names)
                or delivery["anomaly_model_calls"] != len(anomaly_names)
                or delivery["verifier_last_accepted_before_models"] != delivery["sequence_number"]
                or delivery["verifier_last_accepted_after_models"] != delivery["sequence_number"]):
            raise ValueError("accepted-delivery evidence does not match model execution")
        if outcome["attack_type"] == "clean":
            source = prediction["source_window_id"]
            if source in clean_sources:
                raise ValueError("duplicate clean source")
            clean_sources[source] = prediction
    test_sources = {source for split, source in source_conditions if split == "test"}
    if set(clean_sources) != test_sources:
        raise ValueError("missing clean test source")
    for prediction in auth.values():
        if prediction["motion_label"] != clean_sources[prediction["source_window_id"]]["motion_label"]:
            raise ValueError("transformed label differs from clean source")
    return {"planned_cases": len(outcomes), "accepted_test_cases": len(auth),
            "test_source_count": len(test_sources), "fresh_sessions": len({sid for sid, _ in sequences}),
            "maximum_anomaly_score_difference": max_difference, "construction": construction}


def load_saved_run(run: Path) -> dict:
    manifest = read_json(run / "manifest.json")
    complete = read_json(run / "COMPLETE")
    verified = {}
    for name in INPUT_ARTIFACTS:
        digest = sha256(run / name)
        if digest != manifest["artifacts"].get(name):
            raise ValueError(f"historical artifact hash mismatch: {name}; do not edit its manifest")
        verified[name] = digest
    config = read_json(run / "config.json")
    attack_config = read_json(run / "attack-config.json")
    if config["source_dataset_sha256"] != manifest["input_sha256"] or attack_config["source_dataset_sha256"] != manifest["input_sha256"]:
        raise ValueError("saved source dataset hashes differ")
    data = {"outcomes": read_jsonl(run / "construction-outcomes.jsonl"),
            "authenticated": read_jsonl(run / "authenticated-test-predictions.jsonl"),
            "unprotected": read_jsonl(run / "unauthenticated-test-predictions.jsonl"),
            "evidence": read_jsonl(run / "accepted-delivery-evidence.jsonl"),
            "thresholds": read_json(run / "frozen-validation-thresholds.json"),
            "config": config, "attack_config": attack_config}
    reconciliation = reconcile(**data)
    results = read_json(run / "results.json")
    if reconciliation["construction"] != read_json(run / "construction-summary.json") or reconciliation["construction"] != results["construction"]:
        raise ValueError("construction totals differ from historical summaries")
    if results["thresholds"] != data["thresholds"]:
        raise ValueError("historical thresholds disagree")
    boundary = results["boundary"]
    if (complete["planned_cases"] != reconciliation["planned_cases"]
            or complete["test_accepted_cases"] != reconciliation["accepted_test_cases"]
            or complete["source_commit"] != manifest["source_commit"]
            or boundary["accepted_test_cases"] != reconciliation["accepted_test_cases"]
            or boundary["fresh_sessions"] != reconciliation["fresh_sessions"]
            or boundary["paired_model_inputs_match"] is not True
            or any(boundary[key][name] != 0 for key in ("motion_prediction_differences", "anomaly_flag_differences") for name in boundary[key])):
        raise ValueError("completion marker or boundary totals disagree")
    data.update(manifest=manifest, verified_input_sha256=verified,
                reconciliation=reconciliation, historical_results=results)
    return data


def paired_accuracy_interval(clean_correct, changed_correct, repetitions: int, seed: int):
    """Source-paired bootstrap of clean minus changed accuracy on eligible sources."""
    if len(clean_correct) != len(changed_correct):
        raise ValueError("unpaired accuracy cohort")
    if not len(clean_correct):
        return None
    difference = np.asarray(clean_correct, dtype=float) - np.asarray(changed_correct, dtype=float)
    rng = np.random.default_rng(seed)
    sampled = rng.integers(0, len(difference), size=(repetitions, len(difference)))
    return np.quantile(difference[sampled].mean(axis=1), [.025, .975]).tolist()


def build_breakdown(data: dict, repetitions: int = 400, bootstrap_seed: int = 7017) -> dict:
    if type(repetitions) is not int or repetitions < 1 or type(bootstrap_seed) is not int or bootstrap_seed < 0:
        raise ValueError("invalid bootstrap settings")
    outcomes, predictions = data["outcomes"], data["authenticated"]
    counts = construction_counts(outcomes)
    construction_rows = [{"split": key.split(":")[0], "attack_type": key.split(":")[1],
                          "severity": key.split(":")[2], **value,
                          "pre_tag_blocked": value["construction_failure"] + value["quality_failure"]}
                         for key, value in counts.items()]
    failure_counts = Counter((row["split"], row["attack_type"], row["severity"], row["status"], row["reason"])
                             for row in outcomes if row["status"] != "quality_valid")
    failure_rows = [dict(zip(("split", "attack_type", "severity", "stage", "reason"), key), count=value)
                    for key, value in sorted(failure_counts.items())]
    clean = {row["source_window_id"]: row for row in predictions if row["attack_type"] == "clean"}
    grouped = defaultdict(list)
    for row in predictions:
        grouped[f'{row["attack_type"]}:{row["severity"]}'].append(row)
    detector_rows, motion_rows, calibration = [], [], []
    details = {}
    for name, threshold in sorted(data["thresholds"].items()):
        fp = sum(row["anomaly"][name]["flag"] for row in clean.values())
        interval = binomial_interval(fp, len(clean))
        calibration.append({"detector": name, **threshold,
                            "test_clean_false_positives": fp, "test_clean_count": len(clean),
                            "test_clean_fpr": fp / len(clean),
                            "test_clean_fpr_ci_low": interval[0], "test_clean_fpr_ci_high": interval[1],
                            "test_fpr_target_met": fp / len(clean) <= data["config"]["validation_clean_fpr_limit"]})
    for stage in construction_rows:
        if stage["split"] != "test":
            continue
        condition = f'{stage["attack_type"]}:{stage["severity"]}'
        rows = sorted(grouped[condition], key=lambda row: row["source_window_id"])
        is_clean = stage["attack_type"] == "clean"
        for name in sorted(data["thresholds"]):
            flagged = sum(row["anomaly"][name]["flag"] for row in rows)
            interval = binomial_interval(flagged, len(rows))
            control = next(value for value in calibration if value["detector"] == name)
            detector_rows.append({"detector": name, "attack_type": stage["attack_type"], "severity": stage["severity"],
                                  "planned_count": stage["planned"], "quality_valid_count": len(rows),
                                  "construction_failure_count": stage["construction_failure"],
                                  "quality_failure_count": stage["quality_failure"],
                                  "pre_tag_blocked_count": stage["pre_tag_blocked"], "verifier_rejected_count": 0,
                                  "accepted_count": len(rows), "anomaly_detected_count": None if is_clean else flagged,
                                  "missed_count": None if is_clean else len(rows) - flagged,
                                  "flagged_count": flagged, "flag_rate": flagged / len(rows) if rows else None,
                                  "rate_kind": "clean_false_positive_rate" if is_clean else "recall_among_quality_valid",
                                  "ci_low": interval[0] if interval else None, "ci_high": interval[1] if interval else None,
                                  "test_clean_fpr": control["test_clean_fpr"],
                                  "medium_high_recall_target_met": (flagged / len(rows) >= data["config"]["medium_high_detection_target"])
                                  if rows and stage["severity"] in ("medium", "high") else None})
        for name in sorted(clean[next(iter(clean))]["motion"]):
            labels = [row["motion_label"] for row in rows]
            changed = [row["motion"][name] for row in rows]
            paired_clean = [clean[row["source_window_id"]]["motion"][name] for row in rows]
            measured, reference = classification_metrics(labels, changed), classification_metrics(labels, paired_clean)
            seed_key = hashlib.sha256(f"{bootstrap_seed}:{condition}".encode()).digest()
            interval = paired_accuracy_interval([left == right for left, right in zip(labels, paired_clean)],
                                                [left == right for left, right in zip(labels, changed)],
                                                repetitions, int.from_bytes(seed_key[:8], "big"))
            motion_rows.append({"model": name, "attack_type": stage["attack_type"], "severity": stage["severity"],
                                "quality_valid_count": len(rows), "matched_clean_accuracy": reference["accuracy"],
                                "changed_accuracy": measured["accuracy"], "accuracy_loss": reference["accuracy"] - measured["accuracy"] if rows else None,
                                "accuracy_loss_ci_low": interval[0] if interval else None,
                                "accuracy_loss_ci_high": interval[1] if interval else None,
                                "matched_clean_macro_f1": reference["macro_f1"], "changed_macro_f1": measured["macro_f1"],
                                "macro_f1_loss": reference["macro_f1"] - measured["macro_f1"] if rows else None})
            details[f"{name}:{condition}"] = {"matched_clean": reference, "changed": measured}
    return {"construction": construction_rows, "failure_reasons": failure_rows, "detectors": detector_rows,
            "motion": motion_rows, "motion_detail": details, "calibration": calibration,
            "bootstrap_seed": bootstrap_seed, "bootstrap_repetitions": repetitions,
            "reconciliation": data["reconciliation"]}
