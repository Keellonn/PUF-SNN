"""Pure reconstruction analysis candidate; no acquisition, sessions or persistence.

Only ``analyze_final`` produces complete-cohort inference. Mathematical helpers
accept small balanced fixtures but never certify them as a final study. The
trusted evidence reconciler must call ``evaluate_reconstruction`` with actual
decoder facts, effective response and enrollment truth; never deserialize a
credential's claimed category. Python objects are not a hostile-process trust
boundary. Replay/source/enrollment verification belongs to that future caller.

The narrow, versioned in-memory outcome contract intentionally excludes session,
admission, BER and release endpoints. T records carry only a retrieval outcome;
no reconstruction, decoder, or BER values are manufactured for T.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from random import Random
import platform

from . import shared_noise_final_plan_v1 as plan_contract
from .majority3_auth_analysis_v1 import percentile

VERSION = "shared-noise-final-analysis-v1"
CONDITIONS = tuple(c[0] for c in plan_contract.CONDITIONS)
OPERATING = CONDITIONS[:4]
S, M, T = plan_contract.POLICIES
RESAMPLES = 10000
require = plan_contract.require
_EVALUATOR = object()


@dataclass(frozen=True)
class EvaluatedReconstruction:
    """Evaluator-only output. No credential bytes or enrollment truth retained."""

    category: str
    identity_sha256: str
    _origin: object

    def __post_init__(self):
        require(self._origin is _EVALUATOR and self.category in "CDIW"
                and len(self.category) == 1, "trusted evaluator C/D/I/W required")

    @property
    def failure(self):
        return int(self.category != "C")


def evaluate_reconstruction(*, outcome, candidate_credential, enrollment_truth,
                            effective_response):
    """Classify actual decoder output using trusted, transient enrollment truth.

    Outcome names match ReconstructionResult.outcome. Input-format validation
    and BCH decoding happen upstream, once; this function performs no decoding.
    The fingerprint lets reconciliation reject rho1/common identity violations
    even when both reconstructions happen to have the same failure indicator.
    """
    require(type(enrollment_truth) is bytes and len(enrollment_truth) == 4,
            "trusted 32-bit enrollment truth required")
    require(type(effective_response) is tuple and len(effective_response) == 64
            and all(type(b) is int and b in (0, 1) for b in effective_response),
            "effective response must be 64 binary bits")
    require(outcome in ("decoder_failure", "invalid_format_or_padding", "candidate_valid_format"),
            "unknown decoder outcome")
    if outcome == "candidate_valid_format":
        require(type(candidate_credential) is bytes and len(candidate_credential) == 4,
                "valid-format candidate must contain 32 bits")
        category = "C" if candidate_credential == enrollment_truth else "W"
    else:
        require(candidate_credential is None, "failed/invalid decoder cannot supply a credential")
        category = "D" if outcome == "decoder_failure" else "I"
    fingerprint = plan_contract.object_digest(dict(outcome=outcome,
        candidate=candidate_credential.hex() if candidate_credential is not None else None,
        effective_response=effective_response))
    return EvaluatedReconstruction(category, fingerprint, _EVALUATOR)


@dataclass(frozen=True)
class AttemptOutcome:
    """Analysis projection supplied by a trusted reconciler, not a raw ledger row.

    IDs bind to the planned invocation even for unavailable/malformed T retrieval.
    Completion means completed source/reconstruction evaluation, not session
    admission or verifier acceptance. Faults/pending work are diagnostic only.
    """

    config_sha256: str
    plan_sha256: str
    population_id: str
    device_id: str
    enrollment_id: str
    condition: str
    attempt_index: int
    trial_id: str
    policy: str
    policy_attempt_id: str
    execution_index: int
    reconstruction: EvaluatedReconstruction | None
    retrieval_outcome: str | None = None
    execution_status: str = "completed"
    fault_code: str | None = None
    experiment_id: str = plan_contract.VERSION
    schema_version: str = VERSION + ":outcome"

    def __post_init__(self):
        require(self.schema_version == VERSION + ":outcome"
                and self.experiment_id == plan_contract.VERSION, "wrong outcome version/phase")
        require(self.condition in CONDITIONS and self.policy in (S, M, T), "unknown condition/policy")
        require(type(self.attempt_index) is int and 0 <= self.attempt_index < 50
                and type(self.execution_index) is int and self.execution_index >= 0,
                "invalid attempt indices")
        for field in ("config_sha256", "plan_sha256", "population_id", "device_id",
                      "enrollment_id", "trial_id", "policy_attempt_id"):
            require(type(getattr(self, field)) is str and bool(getattr(self, field)), "missing outcome identity")
        require(self.execution_status in ("completed", "pending", "fault"), "unknown execution status")
        if self.policy == T:
            require(self.reconstruction is None, "T reconstruction is inapplicable")
            require(self.retrieval_outcome in ("success", "unavailable", "malformed", None),
                    "unknown T source outcome")
            if self.execution_status == "completed" and self.fault_code is None:
                require(self.retrieval_outcome is not None, "completed T requires source outcome")
        else:
            require(self.retrieval_outcome is None, "PUF arm cannot carry T retrieval")
            if self.reconstruction is not None:
                require(type(self.reconstruction) is EvaluatedReconstruction
                        and self.reconstruction._origin is _EVALUATOR, "trusted evaluator result required")
            if self.execution_status == "completed" and self.fault_code is None:
                require(self.reconstruction is not None, "completed PUF requires reconstruction")


@dataclass(frozen=True)
class DeviceCell:
    condition: str
    n: int
    single_counts: tuple[int, int, int, int]
    majority_counts: tuple[int, int, int, int]
    beneficial: int
    harmful: int
    # T is counted as source invocations, never as reconstructed credentials.
    retrieval_counts: tuple[int, int, int]
    # (trial index, F_S, F_M), preserved for inspection, never resampled alone.
    paired_failures: tuple[tuple[int, int, int], ...]

    def __post_init__(self):
        require(self.condition in CONDITIONS and type(self.n) is int and self.n > 0,
                "positive matched denominator required")
        for counts, length in ((self.single_counts, 4), (self.majority_counts, 4), (self.retrieval_counts, 3)):
            require(type(counts) is tuple and len(counts) == length
                    and all(type(v) is int and v >= 0 for v in counts) and sum(counts) == self.n,
                    "inconsistent category/source denominator")
        require(all(type(v) is int and v >= 0 for v in (self.beneficial, self.harmful))
                and self.beneficial + self.harmful <= self.n
                and self.beneficial <= min(self.single_failures, self.majority_counts[0])
                and self.harmful <= min(self.majority_failures, self.single_counts[0])
                and self.beneficial-self.harmful == self.single_failures-self.majority_failures,
                "inconsistent paired discordance counts")
        require(type(self.paired_failures) is tuple and len(self.paired_failures) == self.n
                and all(type(pair) is tuple and len(pair) == 3
                        and type(pair[0]) is int and 0 <= pair[0] < 50
                        and all(type(v) is int and v in (0, 1) for v in pair[1:])
                        for pair in self.paired_failures), "invalid matched failure indicators")
        require(tuple(sorted(self.paired_failures)) == self.paired_failures
                and len({pair[0] for pair in self.paired_failures}) == self.n
                and sum(pair[1] for pair in self.paired_failures) == self.single_failures
                and sum(pair[2] for pair in self.paired_failures) == self.majority_failures
                and sum(fs == 1 and fm == 0 for _, fs, fm in self.paired_failures) == self.beneficial
                and sum(fs == 0 and fm == 1 for _, fs, fm in self.paired_failures) == self.harmful,
                "failure indicators disagree with paired aggregates")

    @property
    def single_failures(self):
        return sum(self.single_counts[1:])

    @property
    def majority_failures(self):
        return sum(self.majority_counts[1:])

    @property
    def benefit(self):
        return (self.beneficial - self.harmful) / self.n


@dataclass(frozen=True)
class DeviceRecord:
    device_id: str
    population_id: str
    cells: tuple[DeviceCell, ...]

    def __post_init__(self):
        require(type(self.device_id) is str and bool(self.device_id)
                and type(self.population_id) is str and bool(self.population_id), "device/group IDs required")
        require(type(self.cells) is tuple and tuple(c.condition for c in self.cells) == CONDITIONS
                and len({c.n for c in self.cells}) == 1, "complete ordered device conditions required")


def paired_records(rows):
    """Reduce balanced, cross-condition paired data; no final-cohort certificate.

    This small-fixture mathematical boundary still rejects duplicates, inconsistent
    identities, missing arms/conditions/trials, and violated reconstruction
    identities. Final planned coverage is checked separately by validate_complete.
    """
    pairs, devices, seen, indices = {}, {}, set(), set()
    binding = None
    for row in rows:
        require(type(row) is AttemptOutcome, "analysis AttemptOutcome required")
        require(row.execution_status == "completed" and row.fault_code is None,
                "incomplete/faulted outcomes are diagnostic only")
        current = (row.config_sha256, row.plan_sha256)
        binding = current if binding is None else binding
        require(binding == current, "mixed planning contracts")
        require(row.policy_attempt_id not in seen and row.execution_index not in indices,
                "duplicate outcome identity/index")
        seen.add(row.policy_attempt_id)
        indices.add(row.execution_index)
        device_binding = (row.population_id, row.enrollment_id)
        require(devices.setdefault(row.device_id, device_binding) == device_binding,
                "inconsistent group/device/enrollment")
        key = row.device_id, row.condition, row.attempt_index
        pair = pairs.setdefault(key, {})
        require(row.policy not in pair, "duplicate matched arm")
        require(not pair or next(iter(pair.values())).trial_id == row.trial_id,
                "inconsistent matched trial ID")
        pair[row.policy] = row
    if not pairs:
        return ()
    require(all(set(pair) == {S, M, T} for pair in pairs.values()), "missing matched arm")
    require(len({next(iter(p.values())).trial_id for p in pairs.values()}) == len(pairs),
            "misplaced/duplicate trial identity")
    trial_sets = defaultdict(lambda: defaultdict(set))
    for d, c, t in pairs:
        trial_sets[d][c].add(t)
    expected_trials = next(iter(trial_sets.values())).get(OPERATING[0])
    require(bool(expected_trials), "fresh final rho0 reference required")
    for d, cells in trial_sets.items():
        require(set(cells) == set(CONDITIONS) and all(ts == expected_trials for ts in cells.values()),
                "missing/mismatched cross-condition trials")
        for t in expected_trials:
            rho1 = pairs[d, OPERATING[3], t]
            require(rho1[S].reconstruction == rho1[M].reconstruction,
                    "rho1 reconstruction identity violated")
            for policy in (S, M):
                require(pairs[d, CONDITIONS[5], t][policy].reconstruction
                        == pairs[d, OPERATING[0], t][policy].reconstruction,
                        "common-mode reconstruction identity violated")
    records = []
    for d in sorted(devices):
        cells = []
        for c in CONDITIONS:
            selected = [pairs[d, c, t] for t in sorted(expected_trials)]
            counts = [Counter(p[policy].reconstruction.category for p in selected) for policy in (S, M)]
            beneficial = sum(p[S].reconstruction.failure and not p[M].reconstruction.failure for p in selected)
            harmful = sum(not p[S].reconstruction.failure and p[M].reconstruction.failure for p in selected)
            retrieval = Counter(p[T].retrieval_outcome for p in selected)
            cells.append(DeviceCell(c, len(selected), *(tuple(count[k] for k in "CDIW") for count in counts),
                beneficial, harmful, tuple(retrieval[k] for k in ("success", "unavailable", "malformed")),
                tuple((p[S].attempt_index, p[S].reconstruction.failure, p[M].reconstruction.failure)
                      for p in selected)))
        records.append(DeviceRecord(d, devices[d][0], tuple(cells)))
    return tuple(records)


def coverage_diagnostics(plan, rows):
    """Identity diagnostics only; does not validate a plan or authorize inference.

    Missing/unknown IDs are retained explicitly. Started/persisted work and unknown
    unrecorded work belong to future evidence reconciliation, not these projections.
    """
    expected = {a["policy_attempt_id"]: (b, a) for b in plan["blocks"] for a in b["attempts"]}
    seen, duplicates, unknown, mismatched, incomplete = set(), [], [], [], []
    for row in rows:
        require(type(row) is AttemptOutcome, "analysis AttemptOutcome required")
        identity = row.policy_attempt_id
        if identity in seen:
            duplicates.append(identity)
        seen.add(identity)
        if identity not in expected:
            unknown.append(identity)
            continue
        block, attempt = expected[identity]
        if (row.plan_sha256 != plan["plan_sha256"] or row.config_sha256 != plan["config_sha256"]
                or any(getattr(row, k) != block[k] for k in ("population_id", "device_id", "enrollment_id",
                    "condition", "attempt_index", "trial_id"))
                or any(getattr(row, k) != attempt[k] for k in ("policy", "execution_index"))):
            mismatched.append(identity)
        if row.execution_status != "completed" or row.fault_code is not None:
            incomplete.append(identity)
    return dict(expected=len(expected), observed=len(rows), missing=sorted(set(expected) - seen),
        duplicate=sorted(duplicates), unknown=sorted(unknown), mismatched=sorted(mismatched),
        incomplete=sorted(incomplete), inference_eligible=False)


class IncompleteStudyError(ValueError):
    def __init__(self, diagnostics):
        super().__init__("invalid/incomplete final cohort; complete-study inference refused")
        self.diagnostics = diagnostics


@dataclass(frozen=True, init=False)
class CompleteDataset:
    """Immutable statistical coverage boundary, not an evidence completion receipt."""

    records: tuple[DeviceRecord, ...]
    config_sha256: str
    plan_sha256: str


def validate_complete(config, plan, rows):
    """No fixture flag or reduced-cohort mode. Validates the actual final plan."""
    plan_contract.validate_plan(config, plan)
    rows = tuple(rows)
    diagnostics = coverage_diagnostics(plan, rows)
    if any(diagnostics[k] for k in ("missing", "duplicate", "unknown", "mismatched", "incomplete")):
        raise IncompleteStudyError(diagnostics)
    records = paired_records(rows)
    groups = Counter(r.population_id for r in records)
    require(len(records) == 120 and len(groups) == 20 and set(groups.values()) == {6},
            "final cohort requires 120 devices in 20 groups of six")
    require(all(c.n == 50 for r in records for c in r.cells), "50 final matched trials required")
    result = object.__new__(CompleteDataset)
    for name, value in (("records", records), ("config_sha256", config.digest),
                        ("plan_sha256", plan["plan_sha256"])):
        object.__setattr__(result, name, value)
    return result


def estimands(records, weights=None):
    """Equal-device paired means; returned values are proportions, never percents.

    Undefined/empty denominators return None, including A(0) without any devices.
    No attempt-level pooling or independent contrast weighting occurs here.
    """
    ids = {r.device_id for r in records}
    require(len(ids) == len(records), "duplicate device records")
    weights = dict.fromkeys(ids, 1) if weights is None else weights
    require(set(weights) <= ids and all(type(w) is int and w >= 0 for w in weights.values()),
            "unknown device or invalid multiplicity")
    total = sum(weights.values())
    result = {}
    for i, c in enumerate(CONDITIONS):
        for field, key in (("single_failures", "single_frr"), ("majority_failures", "majority_frr")):
            result[f"{key}:{c}"] = (sum(weights.get(r.device_id, 0) * getattr(r.cells[i], field)
                / r.cells[i].n for r in records) / total) if total else None
        if c in OPERATING:
            result[f"delta:{c}"] = (sum(weights.get(r.device_id, 0) * r.cells[i].benefit
                for r in records) / total) if total else None
            result[f"attenuation:{c}"] = (sum(weights.get(r.device_id, 0)
                * (r.cells[0].benefit - r.cells[i].benefit) for r in records) / total) if total else None
    return result


def summarize(records):
    point = estimands(records)
    conditions = {}
    for i, c in enumerate(CONDITIONS):
        cells = [r.cells[i] for r in records]
        n = sum(cell.n for cell in cells)
        arms = {}
        for policy, field, key in ((S, "single_counts", "single_frr"), (M, "majority_counts", "majority_frr")):
            counts = {category: sum(getattr(cell, field)[j] for cell in cells) for j, category in enumerate("CDIW")}
            arms[policy] = dict(counts=counts, denominator=n, reconstruction_frr=point[f"{key}:{c}"],
                zero_events=(sum(counts[k] for k in "DIW") == 0) if n else None,
                status="defined" if n else "undefined-zero-denominator")
        arms[T] = dict(counts=None, denominator=None, reconstruction_frr=None, ber=None,
            decoder_outcomes=None, status="inapplicable", source_denominator=n,
            retrieval_counts={k: sum(cell.retrieval_counts[j] for cell in cells)
                              for j, k in enumerate(("success", "unavailable", "malformed"))})
        beneficial, harmful = sum(cell.beneficial for cell in cells), sum(cell.harmful for cell in cells)
        # An exact rational check, separate from floating-point display values.
        identity_verified = (Fraction(beneficial-harmful, n) == sum(
            (Fraction(cell.beneficial-cell.harmful, cell.n) for cell in cells), Fraction()) / len(cells)) if n else None
        require(identity_verified is not False, "unbalanced discordance/device denominators")
        conditions[c] = dict(arms=arms, matched_denominator=n, beneficial=beneficial, harmful=harmful,
            discordance_net_proportion=(beneficial-harmful)/n if n else None,
            discordance_identity_verified=identity_verified,
            discordant_devices=sum(cell.beneficial+cell.harmful > 0 for cell in cells),
            discordant_groups=len({r.population_id for r in records
                                   if r.cells[i].beneficial+r.cells[i].harmful > 0}))
    groups = sorted({r.population_id for r in records})
    return dict(status="mathematical-summary-only", units="proportion", percentage_points_multiplier=100,
        device_count=len(records), sampling_unit="whole-device", conditions=conditions, estimands=point,
        principal_contrast="attenuation:op_rho090",
        device_benefits={r.device_id: {cell.condition: cell.benefit for cell in r.cells} for r in records},
        paired_failure_columns=("trial_index", "single_failure", "majority_failure"),
        paired_failure_indicators={r.device_id: {cell.condition: cell.paired_failures for cell in r.cells}
                                   for r in records},
        device_groups={r.device_id: r.population_id for r in records},
        group_estimates={g: estimands(records, {r.device_id: 1 for r in records if r.population_id == g}) for g in groups},
        leave_one_device_out={r.device_id: estimands(records,
            {other.device_id: 1 for other in records if other.device_id != r.device_id}) for r in records},
        leave_one_group_out={g: estimands(records,
            {r.device_id: 1 for r in records if r.population_id != g}) for g in groups})


def bootstrap(records, *, seed, unit="device", resamples=RESAMPLES):
    """Mathematical bootstrap engine; fixture seeds/counts are explicitly supplied.

    Production entry point fixes B=10000 and derives each seed from the plan.
    Each resample applies one multiplicity vector to all metrics. Only aggregate
    per-device records are read, never raw attempts, noise or reconstruction.
    """
    require(type(seed) is int and seed >= 0, "nonnegative integer fixture/derived seed required")
    require(type(resamples) is int and resamples > 0, "positive integer resample count required")
    require(unit in ("device", "group"), "unknown bootstrap sampling unit")
    records = tuple(sorted(records, key=lambda r: r.device_id))
    point = estimands(records)
    groups = defaultdict(list)
    for record in records:
        groups[record.population_id].append(record.device_id)
    ids = sorted(r.device_id for r in records) if unit == "device" else sorted(groups)
    samples = {key: [] for key in point}
    performed = 0
    if len(ids) >= 2:
        rng = Random(seed)
        for _ in range(resamples):
            counts = Counter(ids[rng.randrange(len(ids))] for _ in ids)
            weights = counts if unit == "device" else {d: w for g, w in counts.items() for d in groups[g]}
            draw = estimands(records, weights)
            for key, value in draw.items():
                samples[key].append(value)
        performed = resamples
    intervals = {}
    for key, values in samples.items():
        defined = [v for v in values if v is not None]
        lower = percentile(defined, .025) if len(defined) == performed and performed else None
        upper = percentile(defined, .975) if len(defined) == performed and performed else None
        intervals[key] = dict(estimate=point[key], lower=lower, upper=upper,
            defined_resamples=len(defined), undefined_resamples=performed-len(defined),
            degenerate=lower is not None and lower == upper,
            unseen_events_limitation=bool("_frr:" in key and point[key] == 0))
    return dict(status="mathematical-bootstrap-only", role="primary" if unit == "device" else "group-level-sensitivity",
        sampling_unit=unit, sampling_units=len(ids), seed=seed, resamples=resamples, performed_resamples=performed,
        algorithm="random.Random/MT19937; sorted IDs; N calls to randrange(N) per resample",
        python_implementation=platform.python_implementation(), python_version=platform.python_version(),
        sorted_unit_ids_sha256=plan_contract.object_digest(ids),
        method="percentile-linear-(B-1)*p", confidence_level=.95,
        interval_scope="two-sided-pointwise-estimation-only", units="proportion",
        zero_event_caution="A degenerate [0,0] zero-event interval does not establish zero underlying failure probability.",
        interval_status="estimated" if performed else "suppressed-insufficient-sampling-units", intervals=intervals)


def analyze_final(config, plan, rows):
    """Complete statistical analysis only; not permission or evidence certification.

    It consumes reserved final bootstrap streams only AFTER exact cohort
    validation. Tests exercise wiring with mocks or incomplete-input refusal,
    never its successful final-stream path. No seed/count override is exposed.
    """
    dataset = validate_complete(config, plan, rows)
    result = summarize(dataset.records)
    result.update(status="complete-cohort-statistical-analysis", schema_version=VERSION,
        config_sha256=dataset.config_sha256, plan_sha256=dataset.plan_sha256,
        trials_per_device_condition=50, devices=120, groups=20, devices_per_group=6,
        matched_blocks_per_condition=6000, source_attempts_per_condition=18000,
        primary=bootstrap(dataset.records, seed=plan_contract.study_seed(config, "device-bootstrap"), resamples=RESAMPLES),
        group_sensitivity=bootstrap(dataset.records, unit="group",
            seed=plan_contract.study_seed(config, "group-bootstrap-sensitivity"), resamples=RESAMPLES))
    for key, domain in (("primary", "device-bootstrap"), ("group_sensitivity", "group-bootstrap-sensitivity")):
        result[key].update(status="complete-cohort-intervals", seed_domain=domain,
            seed_derivation="planning-v1 study_seed; SHA256 canonical experiment/domain/root/config")
    return result
