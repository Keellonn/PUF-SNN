"""Recomputable metrics and whole-population paired bootstrap; no trial execution."""
from collections import Counter, defaultdict
from random import Random

from .majority3_auth_v1 import CONDITIONS, POLICIES, require, study_seed
from .majority3_auth_runtime_v1 import STAGES


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def percentile(values, probability):
    require(0 <= probability <= 1, "invalid percentile")
    if not values:
        return None
    values = sorted(values)
    x = (len(values)-1)*probability
    lo = int(x)
    hi = min(lo+1, len(values)-1)
    return values[lo] + (values[hi]-values[lo])*(x-lo)


def duration_summary(values):
    return dict(count=len(values), mean_ns=ratio(sum(values), len(values)),
                median_ns=percentile(values, .5), p95_ns=percentile(values, .95),
                p99_ns=percentile(values, .99), maximum_ns=max(values) if values else None)


def group_metrics(rows):
    counts = Counter(r["reconstruction"]["classification"] for r in rows)
    raw = [len(o["error_positions"]) for r in rows for o in r["observations"]]
    first = [len(r["observations"][0]["error_positions"]) for r in rows]
    effective = [len(r["effective_error_positions"]) for r in rows]
    n = len(rows)
    sessions = sum(r["establishment"]["session_active"] for r in rows)
    wrong = [r for r in rows if r["reconstruction"]["classification"] == "W"]
    verification = [v for r in rows for v in r["verification_outcomes"]]
    authorization = [v for r in rows for v in r["authorization_outcomes"]]
    hist = lambda values: [values.count(i) for i in range(64)]
    return dict(attempts=n, outcomes={k: counts[k] for k in "CDIW"}, actual_reads=len(raw),
        reconstruction_failures=counts["D"]+counts["I"]+counts["W"], session_successes=sessions,
        reconstruction_frr=ratio(counts["D"]+counts["I"]+counts["W"], n), session_frr=ratio(n-sessions, n),
        raw_bit_errors=sum(raw), first_bit_errors=sum(first), effective_bit_errors=sum(effective),
        raw_ber=ratio(sum(raw), 63*len(raw)), first_ber=ratio(sum(first), 63*n), effective_ber=ratio(sum(effective), 63*n),
        raw_error_histogram=hist(raw), effective_error_histogram=hist(effective),
        raw_outside_radius=ratio(sum(e > 5 for e in raw), len(raw)),
        effective_outside_radius=ratio(sum(e > 5 for e in effective), n),
        verification_invocations=len(verification), correct_candidate_acceptances=sum(
            r["reconstruction"]["classification"] == "C" and r["verification_outcomes"] == ["verified"] for r in rows),
        wrong_candidate_refusals=sum(r["verification_outcomes"] == ["credential_mismatch"] for r in wrong),
        wrong_refusal_rate=ratio(sum(r["verification_outcomes"] == ["credential_mismatch"] for r in wrong), len(wrong)),
        wrong_refusal_observation="observed" if wrong else "not_observed",
        authorization_successes=sum(authorization), authorization_failures=len(authorization)-sum(authorization),
        window_successes=sum(r["window"] is not None and r["window"]["decision"] == "accept" for r in rows),
        window_failures=sum(r["window"] is not None and r["window"]["decision"] != "accept" for r in rows),
        authorized_releases=sum(r["authorized_release_count"] for r in rows),
        unauthorized_releases=sum(r["unauthorized_release_count"] for r in rows),
        session_failure_stages=dict(sorted(Counter(r["establishment"]["stage"] for r in rows
                                                  if not r["establishment"]["session_active"]).items())))


def population_cells(rows):
    cells = {}
    for population in sorted({r["population_id"] for r in rows}):
        group = [r for r in rows if r["population_id"] == population]
        cells[population] = {}
        for condition, *_ in CONDITIONS:
            for policy in POLICIES:
                selected = [r for r in group if r["condition"] == condition and r["policy"] == policy]
                cells[population][condition+"|"+policy] = (
                    sum(r["reconstruction"]["classification"] != "C" for r in selected),
                    sum(not r["establishment"]["session_active"] for r in selected), len(selected))
    return cells


def estimands(cells, weights=None):
    """FRR_B0 - FRR_M3; attenuation = nominal delta - correlated delta."""
    weights = {p: 1 for p in cells} if weights is None else weights
    result = {}
    for metric, column in (("reconstruction", 0), ("session", 1)):
        for condition, *_ in CONDITIONS:
            rates = []
            for policy in POLICIES:
                entries = [(weights.get(p, 0), row[condition+"|"+policy]) for p, row in cells.items()]
                rates.append(ratio(sum(w*v[column] for w, v in entries), sum(w*v[2] for w, v in entries)))
            result[metric+":delta:"+condition] = rates[0]-rates[1] if all(v is not None for v in rates) else None
        for rho in ("50", "90"):
            nominal = result[metric+":delta:independent_nominal"]
            correlated = result[metric+":delta:differential_rho"+rho]
            result[metric+":attenuation:rho"+rho] = (nominal-correlated
                                                     if nominal is not None and correlated is not None else None)
    return result


def bootstrap_populations(cells, *, seed, resamples=10000):
    """Resample whole populations together across every condition and policy.

    This consumes aggregate population counts only, never creates simulated
    devices/attempts and never resamples device repetitions as independent units.
    """
    require(type(resamples) is int and resamples > 0, "positive integer resamples required")
    require(type(seed) is int and seed >= 0, "nonnegative bootstrap seed required")
    populations = sorted(cells)
    point = estimands(cells)
    samples = {k: [] for k in point}
    inferential = len(populations) >= 2
    if inferential:
        rng = Random(seed)
        for _ in range(resamples):
            weights = Counter(populations[rng.randrange(len(populations))] for _ in populations)
            draw = estimands(cells, weights)
            for key, value in draw.items():
                if value is not None:
                    samples[key].append(value)
    return dict(resamples=resamples, performed_resamples=resamples if inferential else 0,
                population_count=len(populations),
                interval_status="estimated" if inferential else "suppressed_insufficient_populations",
                seed=seed, cluster_unit="whole_population",
                confidence_level=0.95 if inferential else None,
                interval_scope="pointwise", primary_rho=0.90, secondary_rho=0.50,
                zero_observed_failures_is_not_zero_probability=True,
                intervals={k: dict(estimate=point[k], lower=percentile(v, .025), upper=percentile(v, .975),
                                   defined_resamples=len(v)) for k, v in samples.items()})


def timing_analysis(rows):
    inclusive, exclusive, stratified = defaultdict(list), defaultdict(list), defaultdict(list)
    per_trial = defaultdict(dict)
    for r in rows:
        classification = r["reconstruction"]["classification"]
        for s in r["timing"]:
            key = r["condition"]+"|"+r["policy"]+"|"+s["stage"]
            inclusive[key].append(s["duration_ns"])
            children = [c for c in r["timing"] if c["parent_id"] == s["id"]]
            exclusive[key].append(s["duration_ns"]-sum(c["duration_ns"] for c in children))
            strata = key+"|"+classification+"|"+("established" if r["establishment"]["session_active"] else "refused")
            stratified[strata].append(s["duration_ns"])
            if s["stage"] in ("establishment", "acquisition", "reconstruction", "first_window"):
                per_trial[(r["trial_id"], r["condition"], s["stage"])][r["policy"]] = s["duration_ns"]
    paired = defaultdict(list)
    first, second = POLICIES
    for (_, condition, stage), values in per_trial.items():
        if set(values) == set(POLICIES):
            paired[condition+"|"+stage].append(values[second]-values[first])
    keys = [c+"|"+p+"|"+s for c, *_ in CONDITIONS for p in POLICIES for s in STAGES]
    return dict(inclusive={k: duration_summary(inclusive[k]) for k in keys},
                exclusive={k: duration_summary(exclusive[k]) for k in keys},
                outcome_stratified={k: duration_summary(v) for k, v in sorted(stratified.items())},
                paired_majority_minus_single={k: duration_summary(v) for k, v in sorted(paired.items())})


def summarize(config, rows):
    require(all(r["execution_status"] == "completed" for r in rows), "faulted rows cannot enter completed summary")
    groups = {}
    for condition, *_ in CONDITIONS:
        for policy in POLICIES:
            groups[condition+"|"+policy] = group_metrics([r for r in rows if r["condition"] == condition and r["policy"] == policy])
    device, population = {}, {}
    for field, output in (("device_id", device), ("population_id", population)):
        for identity in sorted({r[field] for r in rows}):
            for condition, *_ in CONDITIONS:
                for policy in POLICIES:
                    selected = [r for r in rows if r[field] == identity and r["condition"] == condition and r["policy"] == policy]
                    output[identity+"|"+condition+"|"+policy] = group_metrics(selected)
    cells = population_cells(rows)
    return dict(completed_attempts=len(rows), groups=groups, device_groups=device, population_groups=population,
                timing=timing_analysis(rows), comparisons=estimands(cells),
                bootstrap=bootstrap_populations(cells, seed=study_seed(config, "population-bootstrap"),
                                                 resamples=config.to_dict()["bootstrap_resamples"]))
