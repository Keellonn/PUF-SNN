"""
this file fits separate anomaly baselines and selects thresholds from validation only
paired transforms share their source's training weight rather than becoming independent trials
"""

from __future__ import annotations

from collections import defaultdict
import math

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def validate_evaluation_config(config: dict) -> None:
    if config.get("anomaly_features") != "relative-pose-kinematics-48-v1" or config.get("training_weights") != "equal_source_equal_clean_and_transformed_mass":
        raise ValueError("unsupported anomaly feature or weighting policy")
    for name in ("motion_model_seeds", "anomaly_model_seeds"):
        values = config.get(name)
        if not isinstance(values, list) or len(values) != 3 or len(set(values)) != 3 or any(type(value) is not int or value < 0 for value in values):
            raise ValueError(f"{name} must contain three distinct nonnegative integer seeds")
    roles = config["motion_model_seeds"] + config["anomaly_model_seeds"] + [config.get("bootstrap_seed"), 5007]
    if any(type(value) is not int or value < 0 for value in roles) or len(set(roles)) != len(roles):
        raise ValueError("motion, attack, detector and bootstrap seed roles must be distinct")
    for name in ("bootstrap_repetitions", "unauthenticated_prediction_batch_size", "authenticated_session_case_limit", "torch_threads"):
        if type(config.get(name)) is not int or config[name] < 1:
            raise ValueError(f"{name} must be a positive integer")
    if config["authenticated_session_case_limit"] > 100:
        raise ValueError("authenticate at most 100 cases per fresh pilot session")
    if config.get("snn_hidden_neurons") != 64:
        raise ValueError("the frozen reference remains the 64-neuron Week 4 baseline")
    for name in ("validation_clean_fpr_limit", "medium_high_detection_target"):
        value = config.get(name)
        if type(value) not in (int, float) or not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"invalid {name}")
    for name in ("C", "max_iter"):
        value = config["logistic_regression"][name]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"invalid logistic regression {name}")
    if type(config["logistic_regression"]["max_iter"]) is not int:
        raise ValueError("max_iter must be an integer")
    for name in ("n_estimators", "min_samples_leaf"):
        if type(config["random_forest"][name]) is not int or config["random_forest"][name] < 1:
            raise ValueError(f"invalid random forest {name}")


def _check_cases(cases: list[dict], split: str) -> None:
    if not cases or any(case.get("split") != split for case in cases):
        raise ValueError(f"only nonempty {split} cases are permitted here")
    if len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("duplicate case identifiers")
    for case in cases:
        if type(case.get("is_anomaly")) is not bool or case["is_anomaly"] != (case.get("attack_type") != "clean"):
            raise ValueError("invalid binary anomaly supervision")


def source_balanced_weights(cases: list[dict]) -> np.ndarray:
    groups = defaultdict(list)
    for index, case in enumerate(cases):
        groups[case["source_window_id"]].append(index)
    if not groups:
        raise ValueError("source weighting requires cases")
    weights = np.zeros(len(cases), dtype=np.float64)
    for indexes in groups.values():
        clean = [index for index in indexes if not cases[index]["is_anomaly"]]
        transformed = [index for index in indexes if cases[index]["is_anomaly"]]
        if len(clean) != 1 or not transformed:
            raise ValueError("each source needs exactly one clean case and at least one constructed transform")
        weights[clean[0]] = 0.5
        weights[transformed] = 0.5 / len(transformed)
    return weights * (len(cases) / weights.sum())


def create_anomaly_models(config: dict, seed: int) -> dict[str, object]:
    logistic = Pipeline([("scaler", StandardScaler()), ("classifier", LogisticRegression(C=config["logistic_regression"]["C"], max_iter=config["logistic_regression"]["max_iter"], solver="lbfgs", random_state=seed))])
    forest = RandomForestClassifier(n_estimators=config["random_forest"]["n_estimators"], min_samples_leaf=config["random_forest"]["min_samples_leaf"], random_state=seed, n_jobs=1)
    return {"logistic_regression": logistic, "random_forest": forest}


def fit_anomaly_models(features: np.ndarray, cases: list[dict], config: dict, seed: int) -> dict[str, object]:
    _check_cases(cases, "train")
    values = np.asarray(features, dtype=np.float64)
    if values.shape != (len(cases), 48) or not np.all(np.isfinite(values)):
        raise ValueError("training features must be finite with shape [cases, 48]")
    expected = np.asarray([case["is_anomaly"] for case in cases], dtype=np.int64)
    weights = source_balanced_weights(cases)
    models = create_anomaly_models(config, seed)
    # the scaler is fitted from weighted training data, never from validation or test windows
    models["logistic_regression"].fit(values, expected, scaler__sample_weight=weights, classifier__sample_weight=weights)
    models["random_forest"].fit(values, expected, sample_weight=weights)
    return models


def anomaly_scores(model: object, features: np.ndarray) -> np.ndarray:
    values = np.asarray(features, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 48 or not np.all(np.isfinite(values)):
        raise ValueError("anomaly scoring requires finite [cases, 48] features")
    classes = np.asarray(model.classes_)
    positive = np.flatnonzero(classes == 1)
    if len(positive) != 1:
        raise ValueError("the fitted detector is missing its transformed-input class")
    return np.asarray(model.predict_proba(values)[:, positive[0]], dtype=np.float64)


def select_validation_threshold(scores: np.ndarray, cases: list[dict], clean_fpr_limit: float) -> dict:
    _check_cases(cases, "validation")
    scores = np.asarray(scores, dtype=np.float64)
    if scores.shape != (len(cases),) or not np.all(np.isfinite(scores)) or np.any((scores < 0.0) | (scores > 1.0)):
        raise ValueError("validation scores must be finite probabilities")
    if not 0.0 <= clean_fpr_limit <= 1.0:
        raise ValueError("invalid validation FPR limit")
    expected = np.asarray([case["is_anomaly"] for case in cases], dtype=bool)
    weights = source_balanced_weights(cases)
    clean_count = int((~expected).sum())
    total_positive = float(weights[expected].sum())
    order = np.argsort(-scores, kind="stable")
    selected = {"threshold": float(np.nextafter(scores.max(), np.inf)), "validation_clean_fpr": 0.0, "validation_source_weighted_f1": 0.0, "validation_clean_false_positives": 0, "validation_clean_count": clean_count, "selected_from": "validation", "comparison": "score >= threshold"}
    weighted_tp = 0.0
    weighted_fp = 0.0
    clean_fp = 0
    for offset, index in enumerate(order):
        if expected[index]:
            weighted_tp += float(weights[index])
        else:
            weighted_fp += float(weights[index])
            clean_fp += 1
        # tied probabilities move together because the deployed comparison includes equality
        if offset + 1 < len(order) and scores[order[offset + 1]] == scores[index]:
            continue
        fpr = clean_fp / clean_count
        denominator = 2.0 * weighted_tp + weighted_fp + total_positive - weighted_tp
        objective = 2.0 * weighted_tp / denominator if denominator else 0.0
        if fpr <= clean_fpr_limit + 1e-12 and objective > selected["validation_source_weighted_f1"] + 1e-12:
            selected.update(threshold=float(scores[index]), validation_clean_fpr=fpr, validation_source_weighted_f1=objective, validation_clean_false_positives=clean_fp)
    return selected


def metrics_from_counts(tp: int, fp: int, tn: int, fn: int) -> dict:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    return {"sample_count": tp + fp + tn + fn, "true_positives": tp, "false_positives": fp, "true_negatives": tn, "false_negatives": fn, "precision": precision, "recall": recall, "f1": f1, "clean_false_positive_rate": fp / (fp + tn) if fp + tn else None}


def binary_metrics(expected: np.ndarray, flagged: np.ndarray) -> dict:
    expected = np.asarray(expected)
    flagged = np.asarray(flagged)
    if expected.ndim != 1 or len(expected) == 0 or flagged.shape != expected.shape or not np.all(np.isin(expected, (0, 1))) or not np.all(np.isin(flagged, (0, 1))):
        raise ValueError("binary metrics need matching nonempty binary vectors")
    expected = expected.astype(bool)
    flagged = flagged.astype(bool)
    return metrics_from_counts(int((expected & flagged).sum()), int((~expected & flagged).sum()), int((~expected & ~flagged).sum()), int((expected & ~flagged).sum()))


def source_cluster_intervals(cases: list[dict], flagged: np.ndarray, repetitions: int, seed: int) -> dict:
    expected = np.asarray([case["is_anomaly"] for case in cases], dtype=bool)
    binary_metrics(expected, flagged)
    grouped = defaultdict(lambda: np.zeros(4, dtype=np.int64))
    for case, anomaly, flag in zip(cases, expected, np.asarray(flagged, dtype=bool)):
        count_index = 0 if anomaly and flag else 1 if not anomaly and flag else 2 if not anomaly else 3
        grouped[case["source_window_id"]][count_index] += 1
    counts = np.stack([grouped[name] for name in sorted(grouped)])
    generator = np.random.Generator(np.random.PCG64(seed))
    samples = {name: [] for name in ("precision", "recall", "f1", "clean_false_positive_rate")}
    for _ in range(repetitions):
        total = counts[generator.integers(0, len(counts), size=len(counts))].sum(axis=0)
        measured = metrics_from_counts(*(int(value) for value in total))
        for name in samples:
            if measured[name] is not None:
                samples[name].append(measured[name])
    return {"method": "paired source-window cluster bootstrap; conditional on these synthetic devices/sessions", "source_count": len(counts), "repetitions": repetitions, "seed": seed, "percentile_95_intervals": {name: np.percentile(values, [2.5, 97.5]).tolist() if values else None for name, values in samples.items()}}
