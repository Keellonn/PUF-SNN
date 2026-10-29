"""Paired whole-device calibration analysis; no attenuation estimand or trial execution."""
from collections import Counter, defaultdict
from fractions import Fraction
from random import Random

from . import shared_noise_calibration_v1 as study
from .majority3_auth_analysis_v1 import percentile


def complete_cells(config, plan, rows):
    """Reject missing/duplicated/mismatched evidence before reducing device records."""
    study.validate_plan(config, plan)
    expected = list(study.scheduled_attempts(plan))
    study.require(len(rows) == len(expected), "incomplete calibration coverage")
    seen, cells = set(), defaultdict(lambda: defaultdict(dict))
    for row, (trial, policy, index) in zip(rows, expected):
        identity = study.attempt_id(trial, policy)
        study.require(identity not in seen, "duplicate scheduled policy identity")
        seen.add(identity)
        study.require(row["policy_attempt_id"] == identity and row["execution_index"] == index
            and row["policy"] == policy and row["execution_status"] == "completed"
            and row["fault_code"] is None, "invalid completed policy identity")
        for key in ("trial_id", "device_id", "population_id", "condition", "attempt_index", "config_sha256"):
            study.require(row[key] == trial[key], "mismatched paired trial evidence")
        classification = row["reconstruction"]["classification"]
        study.require(classification in ("C", "D", "I", "W"), "invalid reconstruction classification")
        cells[row["device_id"]][row["condition"]].setdefault(row["attempt_index"], {})[policy] = row
    for device in cells.values():
        for trials in device.values():
            study.require(all(set(pair) == set(study.POLICIES) for pair in trials.values()), "unpaired outcomes")
    return cells


def device_records(cells):
    records = {}
    s, m = study.POLICIES
    for device_id, conditions in sorted(cells.items()):
        record = {}
        for condition, trials in conditions.items():
            pairs = list(trials.values())
            failures = lambda p: sum(pair[p]["reconstruction"]["classification"] != "C" for pair in pairs)
            beneficial = sum(pair[s]["reconstruction"]["classification"] != "C"
                             and pair[m]["reconstruction"]["classification"] == "C" for pair in pairs)
            harmful = sum(pair[s]["reconstruction"]["classification"] == "C"
                          and pair[m]["reconstruction"]["classification"] != "C" for pair in pairs)
            record[condition] = dict(population_id=pairs[0][s]["population_id"], n=len(pairs),
                single_failures=failures(s), majority_failures=failures(m),
                single_frr=failures(s)/len(pairs), majority_frr=failures(m)/len(pairs),
                delta=(beneficial-harmful)/len(pairs),
                beneficial=beneficial, harmful=harmful,
                outcomes={p: {k: sum(pair[p]["reconstruction"]["classification"] == k for pair in pairs)
                               for k in "CDIW"} for p in study.POLICIES})
        records[device_id] = record
    return records


def estimates(records, weights):
    """Identical multiplicities for every condition and both members of each pair."""
    total = sum(weights.values())
    study.require(total > 0, "zero devices selected")
    result = {}
    for c, _ in study.CONDITIONS:
        rates = [sum(w * records[d][c][field] / records[d][c]["n"] for d, w in weights.items()) / total
                 for field in ("single_failures", "majority_failures")]
        result[c] = dict(single_frr=rates[0], majority_frr=rates[1], delta=rates[0]-rates[1])
    return result


def bootstrap_devices(records, *, seed, resamples=10000):
    study.require(type(resamples) is int and resamples == 10000, "exactly 10000 resamples required")
    study.require(type(seed) is int and seed >= 0, "nonnegative integer bootstrap seed required")
    ids = sorted(records)
    point = estimates(records, dict.fromkeys(ids, 1))
    samples = {c: {key: [] for key in point[c]} for c in point}
    rng = Random(seed)
    if len(ids) >= 2:
        for _ in range(resamples):
            weights = Counter(ids[rng.randrange(len(ids))] for _ in ids)
            draw = estimates(records, weights)
            for c in samples:
                for key in samples[c]:
                    samples[c][key].append(draw[c][key])
    result = {}
    for c in samples:
        result[c] = {}
        for key, values in samples[c].items():
            lower, upper = percentile(values, .025), percentile(values, .975)
            result[c][key] = dict(estimate=point[c][key], lower=lower, upper=upper,
                defined_resamples=len(values), degenerate=bool(values and lower == upper),
                unseen_events_limitation=bool(key != "delta" and point[c][key] == 0))
    return dict(cluster_unit="device", device_count=len(ids), resamples=resamples,
        performed_resamples=resamples if len(ids) >= 2 else 0, seed=seed,
        sorted_device_ids_sha256=study.object_digest(ids),
        confidence_level=.95 if len(ids) >= 2 else None,
        interval_status="estimated" if len(ids) >= 2 else "suppressed-insufficient-devices",
        interval_scope="pointwise-estimation-only",
        method="percentile-linear-(B-1)*p", conditions=result)


def conditional_interval(successes, denominators):
    """Conservative secondary-statistic handling: never discard undefined draws."""
    study.require(len(successes) == len(denominators) > 0, "invalid conditional samples")
    values = [n/d for n, d in zip(successes, denominators) if d]
    defined = len(values)
    return dict(defined_resamples=defined, undefined_resamples=len(denominators)-defined,
        lower=percentile(values, .025) if defined == len(denominators) else None,
        upper=percentile(values, .975) if defined == len(denominators) else None)


def candidate_gates(candidate, rules, *, coverage_certified):
    """All scientific thresholds come from the schema-frozen proposed rules object."""
    c, r = candidate, rules
    q = lambda x: Fraction(str(x))
    # Fractions keep observed count-based boundary decisions exact. CI endpoints
    # remain the specified unrounded floating-point percentile values.
    sf, mf, n = c["single_failures"], c["majority_failures"], c["n"]
    delta = Fraction(sf-mf, n)
    ci = c["intervals"]
    defined = all(ci[k]["lower"] is not None and ci[k]["upper"] is not None for k in ci)
    groups = c["group_benefits"]
    return dict(
        coverage_correctness=bool(coverage_certified),
        baseline_region=q(r["single_frr_min"]) <= Fraction(sf, n) <= q(r["single_frr_max"])
            and sf >= r["single_failures_min"] and n-sf >= r["single_correct_min"],
        majority_region=Fraction(mf, n) <= q(r["majority_frr_max"]),
        minimum_benefit=delta >= q(r["delta_min"]),
        informative_counts=c["beneficial"]+c["harmful"] >= r["discordances_min"]
            and c["discordant_devices"] >= r["event_devices_min"]
            and c["discordant_groups"] >= r["event_groups_min"]
            and c["single_failure_devices"] >= r["event_devices_min"]
            and c["single_failure_groups"] >= r["event_groups_min"],
        uncertainty=defined and ci["single_frr"]["lower"] >= r["single_ci_lower_min"]
            and ci["single_frr"]["upper"] <= r["single_ci_upper_max"]
            and ci["delta"]["lower"] > 0
            and q(ci["delta"]["upper"])-q(ci["delta"]["lower"]) <= q(r["delta_ci_width_max"]),
        heterogeneity=bool(c["leave_one_device_out"])
            and all(q(x) >= q(r["leave_device_delta_min"]) for x in c["leave_one_device_out"])
            and sum(q(x) > 0 for x in groups) >= r["positive_groups_min"]
            and all(q(x) >= q(r["group_delta_min"]) for x in groups))


def select_candidates(candidates, rules, *, coverage_certified):
    study.require([c["condition"] for c in candidates] == [c for c, _ in study.CONDITIONS],
                  "selection requires all four ordered calibration candidates")
    assessed = []
    for c in candidates:
        gates = candidate_gates(c, rules, coverage_certified=coverage_certified)
        assessed.append(dict(condition=c["condition"], sigma=c["sigma"], gates=gates,
                             failed_criteria=[k for k, v in gates.items() if not v], qualifies=all(gates.values())))
    qualified = [c for c in assessed if c["qualifies"]]
    return dict(rules_version=study.RULES_VERSION, rules_status="proposed-defaults-require-review",
        status=("incomplete-selection-prohibited" if not coverage_certified else
                "qualifying-operating-point" if qualified else "no-qualifying-operating-point"),
        selected_sigma=qualified[0]["sigma"] if coverage_certified and qualified else None,
        candidates=assessed)


def analyze(config, plan, rows, *, coverage_certified):
    records = device_records(complete_cells(config, plan, rows))
    bootstrap = bootstrap_devices(records, seed=study.study_seed(config, "device-bootstrap"))
    candidates = []
    for condition, sigma in study.CONDITIONS:
        cell = {d: v[condition] for d, v in records.items()}
        groups = sorted({v["population_id"] for v in cell.values()})
        benefit = lambda entries: float(sum((Fraction(v["single_failures"]-v["majority_failures"], v["n"])
                                             for v in entries), Fraction()) / len(entries))
        group_stats = {g: {"benefit": benefit([v for v in cell.values() if v["population_id"] == g]),
                          "n": sum(v["n"] for v in cell.values() if v["population_id"] == g),
                          "single_failures": sum(v["single_failures"] for v in cell.values() if v["population_id"] == g),
                          "majority_failures": sum(v["majority_failures"] for v in cell.values() if v["population_id"] == g)} for g in groups}
        for g, stats in group_stats.items():
            stats["single_frr"] = stats["single_failures"]/stats["n"]
            stats["majority_frr"] = stats["majority_failures"]/stats["n"]
            stats["outcomes"] = {p: {k: sum(v["outcomes"][p][k] for v in cell.values() if v["population_id"] == g)
                                     for k in "CDIW"} for p in study.POLICIES}
        c = dict(condition=condition, sigma=sigma, n=sum(v["n"] for v in cell.values()),
            single_failures=sum(v["single_failures"] for v in cell.values()),
            majority_failures=sum(v["majority_failures"] for v in cell.values()),
            beneficial=sum(v["beneficial"] for v in cell.values()), harmful=sum(v["harmful"] for v in cell.values()),
            discordant_devices=sum(v["beneficial"]+v["harmful"] > 0 for v in cell.values()),
            discordant_groups=len({v["population_id"] for v in cell.values() if v["beneficial"]+v["harmful"] > 0}),
            single_failure_devices=sum(v["single_failures"] > 0 for v in cell.values()),
            single_failure_groups=len({v["population_id"] for v in cell.values() if v["single_failures"] > 0}),
            intervals=bootstrap["conditions"][condition], group_statistics=group_stats,
            group_benefits=[v["benefit"] for v in group_stats.values()],
            leave_one_device_out=[benefit([v for other, v in cell.items() if other != d]) for d in cell] if len(cell) > 1 else [],
            leave_one_group_out=[benefit([v for v in cell.values() if v["population_id"] != g]) for g in groups] if len(groups) > 1 else [],
            outcomes={p: {k: sum(v["outcomes"][p][k] for v in cell.values()) for k in "CDIW"} for p in study.POLICIES})
        candidates.append(c)
    return dict(bootstrap=bootstrap, devices=records, candidates=candidates,
        selection=select_candidates(candidates, config.to_dict()["selection_rules"], coverage_certified=coverage_certified))
