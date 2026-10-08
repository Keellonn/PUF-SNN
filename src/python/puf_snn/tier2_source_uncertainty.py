"""Source-aware reporting of frozen Tier-2 predictions; no attack/model execution.

Each bootstrap weight applies to one source AND all its transformations, paired
clean predictions and frozen model fits. Device/session/class strata stay fixed.
The intervals describe the observed synthetic fixtures, not new populations.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import re

import numpy as np

LABELS = ("nod", "shake", "look_left_return", "look_right_return", "still")
BOOTSTRAP_REPETITIONS = 2000
BOOTSTRAP_SEED = 7027
SOURCE_PATTERN = re.compile(
    r"^(sim-device-\d{2})-(session-\d{2})-(nod|shake|look_left_return|look_right_return|still)-\d{3}-window-\d{3}$"
)
STATUSES = ("quality_valid", "construction_failure", "quality_failure")
GAP_REASON = "source_gap_exceeds_50_ms"
ORDER_REASON = "source_timestamps_not_increasing"


def source_metadata(source, trial):
    match = SOURCE_PATTERN.fullmatch(source)
    if match is None or source.rsplit("-window-", 1)[0] != trial:
        raise ValueError("unsupported source/trial identifier; do not guess its stratum")
    profile, session, label = match.groups()
    return dict(source_window_id=source, source_trial_id=trial,
                synthetic_profile=profile, source_session=session, motion_label=label,
                stratum=f"{profile}:{session}:{label}")


def fixed_family(name):
    prefix = name.rsplit("_seed", 1)[0]
    if prefix not in {"anomaly_logistic_regression", "anomaly_random_forest"}:
        raise ValueError("unknown frozen detector family")
    return prefix.removeprefix("anomaly_")


def case_accounting(outcomes):
    counts, owners, trial_owners, seen = defaultdict(Counter), {}, {}, set()
    for row in outcomes:
        if row["case_id"] in seen or row["split"] not in {"train", "validation", "test"} or row["status"] not in STATUSES:
            raise ValueError("duplicate case or unknown split/status")
        seen.add(row["case_id"])
        source = row["source_window_id"]
        meta = source_metadata(source, row["source_trial_id"])
        if meta["source_session"] != {"train": "session-01", "validation": "session-02", "test": "session-03"}[row["split"]]:
            raise ValueError("source session differs from the historical split policy")
        if source in owners and owners[source] != row["split"]:
            raise ValueError("source derivatives cross splits")
        owners[source] = row["split"]
        trial = row["source_trial_id"]
        if trial in trial_owners and trial_owners[trial] != source:
            raise ValueError("multiple windows per source trial require a different cluster unit")
        trial_owners[trial] = source
        group = counts[(row["split"], row["attack_type"], row["severity"])]
        group["planned_count"] += 1
        group[row["status"]] += 1
        if row["status"] != "quality_valid":
            group["timestamp_gap_blocks" if row["reason"] == GAP_REASON else
                  "timestamp_order_blocks" if row["reason"] == ORDER_REASON else "other_quality_blocks"] += 1
    fields = ("planned_count", *STATUSES, "timestamp_gap_blocks", "timestamp_order_blocks", "other_quality_blocks")
    return [dict(split=key[0], attack_type=key[1], severity=key[2],
                 **{field: value[field] for field in fields},
                 pre_tag_blocked_count=value["construction_failure"] + value["quality_failure"])
            for key, value in sorted(counts.items())]


def prepare_cohort(data):
    construction = case_accounting(data["outcomes"])
    conditions = [("clean", "clean")] + [(attack["name"], severity)
        for attack in sorted(data["attack_config"]["attacks"], key=lambda row: row["name"])
        for severity in data["attack_config"]["severity_names"]]
    if len(set(conditions)) != len(conditions):
        raise ValueError("duplicate registered condition")
    condition_index = {condition: index for index, condition in enumerate(conditions)}
    accepted = {}
    for row in data["authenticated"]:
        if row["case_id"] in accepted:
            raise ValueError("duplicate saved prediction")
        accepted[row["case_id"]] = row
    clean = {}
    for row in accepted.values():
        if row["attack_type"] == "clean":
            if row["severity"] != "clean" or row["source_window_id"] in clean:
                raise ValueError("duplicate/invalid clean control")
            clean[row["source_window_id"]] = row
    if not clean:
        raise ValueError("missing clean source cohort")
    sources = sorted({row["source_window_id"] for row in data["outcomes"] if row["split"] == "test"})
    if set(sources) != set(clean):
        raise ValueError("every test source requires one eligible clean control")
    source_index = {source: index for index, source in enumerate(sources)}
    first = clean[sources[0]]
    detectors, motion_models = sorted(first["anomaly"]), sorted(first["motion"])
    if set(detectors) != set(data["thresholds"]):
        raise ValueError("saved detector set differs from frozen thresholds")
    for name in detectors:
        fixed_family(name)
        threshold = data["thresholds"][name]["threshold"]
        if (data["thresholds"][name]["selected_from"] != "validation"
                or type(threshold) not in (int, float) or not np.isfinite(threshold)
                or not 0 <= threshold <= 1):
            raise ValueError("threshold was not selected on validation")
    n, c, d, m = len(sources), len(conditions), len(detectors), len(motion_models)
    valid = np.zeros((n, c), dtype=bool)
    flags = np.zeros((n, c, d), dtype=float)
    predictions = np.full((n, c, m), -1, dtype=np.int8)
    truth = np.empty(n, dtype=np.int8)
    metadata, seen_slots, eligible_cases = [], set(), set()
    label_index = {label: index for index, label in enumerate(LABELS)}
    for source in sources:
        row = clean[source]
        meta = source_metadata(source, row["source_trial_id"])
        if row["motion_label"] != meta["motion_label"]:
            raise ValueError("ground truth differs from source identifier")
        metadata.append(meta)
        truth[source_index[source]] = label_index[meta["motion_label"]]
    for outcome in data["outcomes"]:
        if outcome["split"] != "test":
            continue
        condition = (outcome["attack_type"], outcome["severity"])
        if condition not in condition_index:
            raise ValueError("unexpected source transformation")
        i, j = source_index[outcome["source_window_id"]], condition_index[condition]
        if (i, j) in seen_slots:
            raise ValueError("duplicate condition for a source")
        seen_slots.add((i, j))
        if outcome["status"] != "quality_valid":
            if outcome["case_id"] in accepted:
                raise ValueError("quality-blocked case has model predictions")
            continue
        eligible_cases.add(outcome["case_id"])
        if outcome["case_id"] not in accepted:
            raise ValueError("quality-valid case lacks saved accepted prediction")
        row = accepted[outcome["case_id"]]
        for field in ("source_window_id", "source_trial_id", "attack_type", "severity"):
            if row[field] != outcome[field]:
                raise ValueError("prediction identity differs from construction")
        if row["motion_label"] != LABELS[int(truth[i])] or row["is_anomaly"] is not (condition[0] != "clean"):
            raise ValueError("changed label or anomaly identity")
        if set(row["motion"]) != set(motion_models) or set(row["anomaly"]) != set(detectors):
            raise ValueError("model set changes between cases")
        valid[i, j] = True
        for k, name in enumerate(detectors):
            entry = row["anomaly"][name]
            if (type(entry["flag"]) is not bool or type(entry["score"]) not in (int, float)
                    or not np.isfinite(entry["score"]) or not 0 <= entry["score"] <= 1
                    or entry["flag"] != (entry["score"] >= data["thresholds"][name]["threshold"])):
                raise ValueError("saved detector flag differs from frozen threshold")
            flags[i, j, k] = int(entry["flag"])
        for k, name in enumerate(motion_models):
            if row["motion"][name] not in label_index:
                raise ValueError("unknown motion prediction")
            predictions[i, j, k] = label_index[row["motion"][name]]
    if len(seen_slots) != n * c or set(accepted) != eligible_cases or not valid[:, 0].all():
        raise ValueError("incomplete planned/eligible source-condition cohort")
    for index, meta in enumerate(metadata):
        meta.update(planned_derivative_count=c, quality_valid_derivative_count=int(valid[index].sum()))
    return dict(construction=construction, conditions=conditions, detectors=detectors,
        motion_models=motion_models, sources=metadata, valid=valid, flags=flags,
        predictions=predictions, truth=truth)


def source_bootstrap_weights(metadata, repetitions=BOOTSTRAP_REPETITIONS, seed=BOOTSTRAP_SEED):
    if type(repetitions) is not int or repetitions < 20 or type(seed) is not int or seed < 0 or not metadata:
        raise ValueError("invalid reporting bootstrap settings")
    if len({row["source_window_id"] for row in metadata}) != len(metadata):
        raise ValueError("duplicate source in bootstrap cohort")
    strata = defaultdict(list)
    for index, row in enumerate(metadata):
        strata[row["stratum"]].append(index)
    weights = np.zeros((repetitions, len(metadata)), dtype=np.uint16)
    rng = np.random.Generator(np.random.PCG64(seed))
    for name in sorted(strata):
        indices = np.asarray(strata[name], dtype=np.int64)
        if len(indices) > np.iinfo(np.uint16).max:
            raise ValueError("stratum too large for registered weight format")
        draws = indices[rng.integers(0, len(indices), size=(repetitions, len(indices)))]
        np.add.at(weights, (np.arange(repetitions)[:, None], draws), 1)
    validate_weights(weights, metadata)
    return weights


def validate_weights(weights, metadata):
    if (weights.ndim != 2 or weights.shape[1] != len(metadata) or weights.shape[0] < 20
            or weights.dtype.kind not in "iu" or (weights < 0).any()):
        raise ValueError("invalid source-weight matrix")
    strata = defaultdict(list)
    for index, row in enumerate(metadata):
        strata[row["stratum"]].append(index)
    for indices in strata.values():
        if not np.all(weights[:, indices].sum(axis=1) == len(indices)):
            raise ValueError("bootstrap weights changed fixed stratum size")


def ratio(numerator, denominator):
    numerator, denominator = np.broadcast_arrays(np.asarray(numerator, dtype=float), np.asarray(denominator, dtype=float))
    result = np.full(numerator.shape, np.nan, dtype=float)
    np.divide(numerator, denominator, out=result, where=denominator > 0)
    return result


def interval(values):
    values = np.asarray(values, dtype=float)
    selected = values[np.isfinite(values)]
    low, high = (np.quantile(selected, [.025, .975], method="linear") if len(selected) else (None, None))
    return dict(ci_low=float(low) if low is not None else None,
                ci_high=float(high) if high is not None else None,
                defined_bootstrap_draws=int(len(selected)),
                undefined_bootstrap_draws=int(len(values) - len(selected)),
                degenerate_bootstrap_interval=bool(len(selected) and low == high))


def motion_metrics(truth, prediction):
    if len(truth) != len(prediction):
        raise ValueError("unpaired motion labels")
    if not len(truth):
        return dict(sample_count=0, accuracy=None, macro_f1=None, confusion_matrix=None)
    truth, prediction = np.asarray(truth), np.asarray(prediction)
    if (truth.ndim != 1 or prediction.ndim != 1 or truth.dtype.kind not in "iu"
            or prediction.dtype.kind not in "iu" or (truth < 0).any() or (prediction < 0).any()
            or (truth >= len(LABELS)).any() or (prediction >= len(LABELS)).any()):
        raise ValueError("unknown motion label index")
    matrix = np.bincount(truth * len(LABELS) + prediction,
                         minlength=len(LABELS)**2).reshape(len(LABELS), len(LABELS))
    denominator = matrix.sum(axis=0) + matrix.sum(axis=1)
    f1 = np.zeros(len(LABELS), dtype=float)
    np.divide(2 * np.diag(matrix), denominator, out=f1, where=denominator > 0)
    return dict(sample_count=len(truth), accuracy=float(np.trace(matrix) / matrix.sum()),
                macro_f1=float(f1.mean()), confusion_matrix=matrix.tolist())


def build_source_analysis(data, repetitions=BOOTSTRAP_REPETITIONS, seed=BOOTSTRAP_SEED):
    cohort = prepare_cohort(data)
    weights = source_bootstrap_weights(cohort["sources"], repetitions, seed)
    w = weights.astype(float)
    valid, flags, predictions, truth = (cohort[key] for key in ("valid", "flags", "predictions", "truth"))
    n, c, d = flags.shape
    m = predictions.shape[2]
    valid_counts = valid.sum(axis=0)
    boot_valid = w @ valid.astype(float)
    boot_flags = (w @ flags.reshape(n, c*d)).reshape(repetitions, c, d)
    clean_correct = predictions[:, 0, :] == truth[:, None]
    changed_correct = predictions == truth[:, None, None]
    differences = valid[:, :, None] * (clean_correct[:, None, :].astype(float) - changed_correct.astype(float))
    boot_loss = (w @ differences.reshape(n, c*m)).reshape(repetitions, c, m)
    test_counts = {(row["attack_type"], row["severity"]): row for row in cohort["construction"] if row["split"] == "test"}
    detector_rows, motion_rows, family_conditions = [], [], []
    families = {family: [index for index, name in enumerate(cohort["detectors"]) if fixed_family(name) == family]
                for family in sorted({fixed_family(name) for name in cohort["detectors"]})}
    for j, (attack, severity) in enumerate(cohort["conditions"]):
        counts = test_counts[(attack, severity)]
        eligible = int(valid_counts[j])
        for k, name in enumerate(cohort["detectors"]):
            flagged = int(flags[:, j, k].sum())
            row = dict(detector=name, attack_type=attack, severity=severity,
                planned_count=counts["planned_count"], unique_eligible_sources=eligible,
                quality_valid_count=eligible, pre_tag_blocked_count=counts["pre_tag_blocked_count"],
                timestamp_gap_blocks=counts["timestamp_gap_blocks"], timestamp_order_blocks=counts["timestamp_order_blocks"],
                other_quality_blocks=counts["other_quality_blocks"], authenticated_accepted_count=eligible,
                authenticated_rejected_before_inference_count=0,
                anomaly_detected_count=flagged if attack != "clean" else 0,
                anomaly_missed_count=eligible-flagged if attack != "clean" else 0,
                clean_false_positive_count=flagged if attack == "clean" else 0,
                flagged_count=flagged, flag_rate=flagged/eligible if eligible else None,
                rate_kind="clean_false_positive_rate" if attack == "clean" else "recall_conditional_on_quality_valid",
                **interval(ratio(boot_flags[:, j, k], boot_valid[:, j])),
                small_eligible_cohort=eligible < 30,
                test_clean_false_positives=int(flags[:, 0, k].sum()), test_clean_source_count=n,
                test_clean_fpr=float(flags[:, 0, k].mean()),
                frozen_validation_threshold=data["thresholds"][name]["threshold"])
            detector_rows.append(row)
        for family, indices in families.items():
            rates = ratio(boot_flags[:, j, indices], boot_valid[:, j, None]).mean(axis=1)
            family_conditions.append(dict(family=family, attack_type=attack, severity=severity,
                fixed_model_count=len(indices), planned_unique_sources=n, unique_eligible_sources=eligible,
                mean_fixed_model_flag_rate=float(flags[:, j, indices].sum() / (eligible*len(indices))) if eligible else None,
                **interval(rates), small_eligible_cohort=eligible < 30,
                seed_fits_are_independent_source_trials=False))
        mask = valid[:, j]
        for k, name in enumerate(cohort["motion_models"]):
            clean = motion_metrics(truth[mask], predictions[mask, 0, k])
            changed = motion_metrics(truth[mask], predictions[mask, j, k])
            motion_rows.append(dict(model=name, attack_type=attack, severity=severity,
                unique_eligible_sources=eligible, clean_subset_accuracy=clean["accuracy"],
                transformed_accuracy=changed["accuracy"],
                paired_accuracy_loss=clean["accuracy"]-changed["accuracy"] if eligible else None,
                **interval(ratio(boot_loss[:, j, k], boot_valid[:, j])),
                clean_subset_macro_f1=clean["macro_f1"], transformed_macro_f1=changed["macro_f1"],
                macro_f1_loss=clean["macro_f1"]-changed["macro_f1"] if eligible else None,
                macro_f1_interval_provided=False, small_eligible_cohort=eligible < 30))
    attacks = [j for j, (name, _) in enumerate(cohort["conditions"]) if name != "clean"]
    medium_high = [j for j, (name, severity) in enumerate(cohort["conditions"]) if name != "clean" and severity in {"medium", "high"}]
    attack_valid = valid[:, attacks].sum(axis=1)
    medium_valid = valid[:, medium_high].sum(axis=1)
    tp = flags[:, attacks, :].sum(axis=1)
    medium_tp = flags[:, medium_high, :].sum(axis=1)
    fp = flags[:, 0, :]
    fn = attack_valid[:, None] - tp
    boot_tp, boot_fp, boot_fn = w @ tp, w @ fp, w @ fn
    summary_boot = dict(
        medium_high_recall=ratio(w @ medium_tp, (w @ medium_valid)[:, None]),
        clean_fpr=ratio(boot_fp, n),
        all_attack_recall=ratio(boot_tp, (w @ attack_valid)[:, None]),
        all_quality_valid_precision=ratio(boot_tp, boot_tp+boot_fp),
        all_quality_valid_f1=ratio(2*boot_tp, 2*boot_tp+boot_fp+boot_fn))
    detector_summary, family_summary = [], []
    for k, name in enumerate(cohort["detectors"]):
        total_tp, total_fp, total_fn = (int(array[:, k].sum()) for array in (tp, fp, fn))
        points = dict(medium_high_recall=float(medium_tp[:, k].sum()/medium_valid.sum()) if medium_valid.sum() else None,
            clean_fpr=total_fp/n, all_attack_recall=total_tp/int(attack_valid.sum()) if attack_valid.sum() else None,
            all_quality_valid_precision=total_tp/(total_tp+total_fp) if total_tp+total_fp else 0.0,
            all_quality_valid_f1=2*total_tp/(2*total_tp+total_fp+total_fn) if 2*total_tp+total_fp+total_fn else 0.0)
        for metric, value in points.items():
            population = ("clean_sources" if metric == "clean_fpr" else "medium_high_quality_valid" if metric == "medium_high_recall"
                          else "all_attack_quality_valid" if metric == "all_attack_recall" else "all_quality_valid")
            eligible_count = (n if metric == "clean_fpr" else int(medium_valid.sum()) if metric == "medium_high_recall"
                              else int(attack_valid.sum()) if metric == "all_attack_recall" else int(valid.sum()))
            unique_sources = n if metric == "clean_fpr" else int((medium_valid > 0).sum()) if metric == "medium_high_recall" else n
            target = data["config"]["validation_clean_fpr_limit"] if metric == "clean_fpr" else data["config"]["medium_high_detection_target"] if metric == "medium_high_recall" else None
            detector_summary.append(dict(detector=name, population=population, metric=metric,
                point_estimate=value, eligible_case_count=eligible_count, unique_source_count=unique_sources,
                medium_high_detected_count=int(medium_tp[:, k].sum()), medium_high_missed_count=int(medium_valid.sum()-medium_tp[:, k].sum()),
                all_attack_true_positives=total_tp, clean_false_positives=total_fp, all_attack_false_negatives=total_fn,
                **interval(summary_boot[metric][:, k]), target=target,
                observed_point_target_met=(value <= target if metric == "clean_fpr" else value >= target) if target is not None and value is not None else None))
    for family, indices in families.items():
        for metric in summary_boot:
            points = [row["point_estimate"] for row in detector_summary if row["metric"] == metric and row["detector"] in {cohort["detectors"][k] for k in indices}]
            family_summary.append(dict(family=family, metric=metric, fixed_model_count=len(indices),
                mean_fixed_model_point_estimate=float(np.mean(points)) if all(value is not None for value in points) else None,
                **interval(summary_boot[metric][:, indices].mean(axis=1)),
                unique_source_count=n, seed_fits_are_independent_source_trials=False))
    return dict(cohort=cohort, weights=weights, detector_outcomes=detector_rows,
        motion_degradation=motion_rows, detector_summary=detector_summary,
        family_condition_uncertainty=family_conditions, family_summary=family_summary,
        repetitions=repetitions, reporting_seed=seed,
        source_weight_sha256=hashlib.sha256(weights.astype("<u2").tobytes(order="C")).hexdigest())


def check_historical_points(result, historical):
    for row in result["detector_outcomes"]:
        condition = f"{row['attack_type']}:{row['severity']}"
        saved = historical["authenticated"]["anomaly"][row["detector"]].get(condition)
        if row["quality_valid_count"] == 0:
            if saved is not None:
                raise ValueError("historical summary contains an empty condition")
            continue
        clean = row["attack_type"] == "clean"
        observed = dict(sample_count=row["quality_valid_count"], true_positives=0 if clean else row["flagged_count"],
            false_positives=row["flagged_count"] if clean else 0,
            true_negatives=row["quality_valid_count"]-row["flagged_count"] if clean else 0,
            false_negatives=0 if clean else row["quality_valid_count"]-row["flagged_count"])
        if saved is None or any(saved[key] != value for key, value in observed.items()):
            raise ValueError("recomputed detector counts differ from frozen results")
    for row in result["detector_summary"]:
        saved = historical["authenticated"]["anomaly"][row["detector"]]
        group, field = ("medium_high_quality_valid", "recall") if row["metric"] == "medium_high_recall" else (
            ("clean:clean", "clean_false_positive_rate") if row["metric"] == "clean_fpr" else
            ("all_quality_valid", row["metric"].removeprefix("all_quality_valid_").replace("all_attack_recall", "recall")))
        if abs(saved[group][field] - row["point_estimate"]) > 1e-12:
            raise ValueError("pooled detector point estimate differs from historical results")
    cohort = result["cohort"]
    for j, (attack, severity) in enumerate(cohort["conditions"]):
        mask = cohort["valid"][:, j]
        for k, name in enumerate(cohort["motion_models"]):
            observed = motion_metrics(cohort["truth"][mask], cohort["predictions"][mask, j, k])
            saved = historical["authenticated"]["motion"][name].get(f"{attack}:{severity}")
            if not observed["sample_count"]:
                if saved is not None:
                    raise ValueError("historical motion includes an empty condition")
            elif (saved is None or observed["confusion_matrix"] != saved["confusion_matrix"]
                    or abs(observed["macro_f1"] - saved["macro_f1"]) > 1e-12):
                raise ValueError("motion confusion/F1 differs from historical results")
