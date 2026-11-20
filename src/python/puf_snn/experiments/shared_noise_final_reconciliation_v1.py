"""Read-only final-study reconciliation candidate, not an execution controller.

Four boundaries: planned bindings, untrusted JSON execution records, independently
supplied replay inputs, and opaque verifier-issued facts projected to AttemptOutcome.
No acquisition, enrollment generation, sessions, bootstrap, I/O or completion marker.

ReplayInputs must come from a trusted, separate evidence/enrollment custodian,
NEVER by copying the ledger being checked. No final custodian implementation exists
here. Comparing preserved readings is not regeneration of simulator measurements;
replaying BCH is not verification of historical execution, source/environment or
authorization. Those unmet prerequisites always block final analysis handoff.

The closed Python record validator versions this narrow evidence projection without
changing the planner's metadata-only JSON schema. Decoder records contain public
decoder metadata only, never candidate messages/credentials or evaluator categories.
Private replay inputs follow the existing in-memory, redacted stored-credential
convention: no secure storage/erasure or isolation from malicious Python is claimed.
"""

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from types import MappingProxyType
from typing import Protocol

from puf_snn.auth.stored_credential import StoredCredentialRecord
from puf_snn.puf.acquisition import majority_vote3
from puf_snn.reconstruction import HelperData, ReconstructionResult, reconstruct
from puf_snn.reconstruction.bch import validate_bits
from . import shared_noise_final_plan_v1 as planning
from . import shared_noise_final_analysis_v1 as analysis

VERSION = "shared-noise-final-reconciliation-v1"
S, M, T = planning.POLICIES
CONDITIONS = tuple(c[0] for c in planning.CONDITIONS)
OPERATIONS = ("readings", "votes", "reconstructions", "bch_decodes", "stored_retrievals")
PREREQUISITES = (
    "protected-enrollment-and-per-invocation-source-custody",
    "deterministic-measurement-and-enrollment-source-replay",
    "full-source-snapshot-and-environment-verification",
    "downstream-protocol-audit-and-protected-controller-acceptance",
)


class ReconciliationError(ValueError):
    """Fixed, secret-free diagnostic code; never log arbitrary provider errors."""


def check(condition, code):
    if not condition:
        raise ReconciliationError(code)


def _exact(obj, keys, code):
    check(type(obj) is dict and set(obj) == set(keys), code)


def _digest(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def expected_operations(policy):
    check(policy in (S, M, T), "unknown-policy")
    return dict(zip(OPERATIONS, {S: (1, 0, 1, 1, 0), M: (3, 1, 1, 1, 0), T: (0, 0, 0, 0, 1)}[policy]))


@dataclass(frozen=True)
class PlannedAttempt:
    """Immutable narrow binding. Its existence alone does not validate a plan."""

    config_sha256: str
    plan_sha256: str
    block_json: bytes = field(repr=False)
    attempt_json: bytes = field(repr=False)

    def to_dict(self):
        return dict(config_sha256=self.config_sha256, plan_sha256=self.plan_sha256,
                    block=planning.read_json(self.block_json), attempt=planning.read_json(self.attempt_json))

    @property
    def digest(self):
        return planning.object_digest(self.to_dict())

    @property
    def identity(self):
        return planning.read_json(self.attempt_json)["policy_attempt_id"]


def block_bindings(config_sha256, plan_sha256, block):
    """Metadata only. Share one immutable block snapshot across its three arms."""
    snapshot = planning.canonical({k: v for k, v in block.items() if k != "attempts"})
    return tuple(PlannedAttempt(config_sha256, plan_sha256, snapshot, planning.canonical(a)) for a in block["attempts"])


class ScheduleIndex:
    """Indexed bindings for local checking; generic construction cannot certify final allocation.

    from_final_plan is the only path that checks the actual full planner contract.
    Small fixtures use the same binding checks, with no final-cohort bypass flag.
    """

    def __init__(self, bindings):
        attempts, blocks, indices, devices = {}, {}, set(), {}
        contract = None
        for binding in bindings:
            check(type(binding) is PlannedAttempt, "planned-binding-required")
            obj = binding.to_dict()
            b, a = obj["block"], obj["attempt"]
            check(_digest(binding.config_sha256) and _digest(binding.plan_sha256), "invalid-plan-digest")
            current = binding.config_sha256, binding.plan_sha256
            contract = current if contract is None else contract
            check(current == contract, "mixed-planning-contracts")
            planning.validate_schema("attempt", a)
            _exact(b, ("schema_version", "experiment_id", "config_sha256", "population_id", "device_id",
                "enrollment_id", "condition", "attempt_index", "sigma", "rho", "common_offset", "noise_identity",
                "noise_shared_seed_sha256", "reading_seed_sha256", "common_offset_seed_sha256",
                "linked_operating_trial_id", "trial_id", "policy_order", "block_index"), "invalid-planned-block")
            check(b["schema_version"] == planning.VERSION+":planned-block"
                  and b["experiment_id"] == a["experiment_id"] == planning.VERSION
                  and b["config_sha256"] == binding.config_sha256, "planned-phase-config-mismatch")
            check(type(b["attempt_index"]) is int and 0 <= b["attempt_index"] < 50
                  and type(b["block_index"]) is int and b["block_index"] >= 0
                  and type(a["execution_index"]) is int, "invalid-planned-index")
            for key in ("population_id", "device_id", "enrollment_id"):
                check(type(b[key]) is str and bool(b[key]), "invalid-device-enrollment")
            check(devices.setdefault(b["device_id"], (b["population_id"], b["enrollment_id"]))
                  == (b["population_id"], b["enrollment_id"]), "planned-device-enrollment-conflict")
            profile = next((c for c in planning.CONDITIONS if c[0] == b["condition"]), None)
            check(profile is not None and type(b["sigma"]) is float and type(b["rho"]) is float
                  and (b["sigma"], b["rho"]) == profile[1:3], "planned-condition-profile-mismatch")
            common = b["condition"] == CONDITIONS[5]
            check(type(b["common_offset"]) is int and b["common_offset"] in ((-1, 1) if common else (0,)),
                  "planned-common-offset-mismatch")
            identity = planning.noise.AttemptIdentity(**b["noise_identity"])
            check((identity.population_id, identity.device_id, identity.attempt_id)
                  == (b["population_id"], b["device_id"], b["attempt_index"])
                  and identity.noise_domain_id.endswith(":"+profile[3]), "planned-noise-binding-mismatch")
            check(b["noise_shared_seed_sha256"] == planning.seed_digest(identity, planning.noise.SESSION)
                  and b["reading_seed_sha256"] == [planning.seed_digest(identity, planning.noise.READING, i) for i in range(3)]
                  and b["common_offset_seed_sha256"] == (planning.seed_digest(identity, planning.noise.COMMON_MODE) if common else None),
                  "planned-seed-mismatch")
            check(b["trial_id"] == planning.trial_id(b) == a["trial_id"]
                  and a["condition"] == b["condition"] and a["policy_attempt_id"] == planning.attempt_id(b, a["policy"]),
                  "planned-attempt-identity-mismatch")
            check(type(b["policy_order"]) is list and len(b["policy_order"]) == 3
                  and set(b["policy_order"]) == {S, M, T}
                  and a["execution_index"] == 3*b["block_index"]+b["policy_order"].index(a["policy"]), "planned-policy-order-mismatch")
            readings = {S: [0], M: [0, 1, 2], T: []}[a["policy"]]
            check(a["reading_indices"] == readings
                  and a["reading_seed_sha256"] == [b["reading_seed_sha256"][i] for i in readings]
                  and a["noise_shared_seed_sha256"] == (b["noise_shared_seed_sha256"] if readings else None),
                  "planned-reading-binding-mismatch")
            check(binding.identity not in attempts and a["execution_index"] not in indices, "duplicate-planned-attempt")
            indices.add(a["execution_index"])
            attempts[binding.identity] = binding
            key = b["device_id"], b["condition"], b["attempt_index"]
            entry = blocks.setdefault(key, (binding.block_json, set()))
            check(entry[0] == binding.block_json, "conflicting-planned-block")
            entry[1].add(a["policy"])
        check(bool(attempts) and indices == set(range(len(attempts))), "incomplete-planned-schedule")
        check(all(policies == {S, M, T} for _, policies in blocks.values()), "missing-planned-arm")
        check(len({planning.read_json(raw)["trial_id"] for raw, _ in blocks.values()}) == len(blocks), "duplicate-planned-trial")
        trial_sets = defaultdict(lambda: defaultdict(set))
        for d, c, t in blocks:
            trial_sets[d][c].add(t)
        reference = next(iter(trial_sets.values())).get(CONDITIONS[0])
        check(bool(reference) and all(set(cells) == set(CONDITIONS)
              and all(ts == reference for ts in cells.values()) for cells in trial_sets.values()), "unmatched-planned-conditions")
        for d, _, t in blocks:
            op = planning.read_json(blocks[d, CONDITIONS[0], t][0])
            common = planning.read_json(blocks[d, CONDITIONS[5], t][0])
            check(common["linked_operating_trial_id"] == op["trial_id"]
                  and all(common[k] == op[k] for k in ("noise_identity", "noise_shared_seed_sha256", "reading_seed_sha256")),
                  "planned-common-alias-mismatch")
        check(all(planning.read_json(raw)["linked_operating_trial_id"] is None for (d, c, t), (raw, _) in blocks.items()
                  if c != CONDITIONS[5]), "misplaced-common-link")
        self.attempts = MappingProxyType(attempts)
        self.config_sha256, self.plan_sha256 = contract
        self._final_checked = False

    @classmethod
    def from_final_plan(cls, config, plan):
        planning.validate_plan(config, plan)
        result = cls(b for block in plan["blocks"] for b in block_bindings(config.digest, plan["plan_sha256"], block))
        result._final_checked = True
        return result


@dataclass(frozen=True)
class RecordedExecution:
    """Untrusted UTF-8 JSON plus separately supplied raw-byte hash expectation."""

    raw: bytes = field(repr=False)
    expected_raw_sha256: str


def decoder_record(decoded):
    """Public metadata projection of the existing real decoder result, never C/D/I/W."""
    check(type(decoded) is ReconstructionResult, "existing-reconstruction-result-required")
    return {key: getattr(decoded, key) for key in ("outcome", "decoder_status", "reported_correction_count", "padding_valid", "failure_reason")}


def _parse(envelope):
    check(type(envelope) is RecordedExecution and type(envelope.raw) is bytes
          and len(envelope.raw) <= 1_048_576, "invalid-record-envelope")
    try:
        row = planning.read_json(envelope.raw)
        # Re-encoding also rejects NaN/Inf parsed from an overflowing exponent.
        planning.canonical(row)
    except (ValueError, TypeError, UnicodeError, OverflowError):
        raise ReconciliationError("invalid-record-json") from None
    _exact(row, ("schema_version", "planned", "run_id", "source_id", "enrollment_sha256", "state", "fault_code",
                 "operations", "readings", "effective_response", "effective_sha256", "decoder", "retrieval_outcome", "downstream"), "invalid-record-fields")
    check(row["schema_version"] == VERSION+":record", "unsupported-record-version")
    _exact(row["planned"], ("config_sha256", "plan_sha256", "block", "attempt"), "invalid-record-planned-binding")
    check(type(row["planned"]["attempt"]) is dict and _digest(row["planned"]["attempt"].get("policy_attempt_id")),
          "missing-record-attempt-id")
    check(row["state"] in ("pending", "started", "completed", "fault"), "invalid-record-state")
    check(row["fault_code"] in (None, "numerical_comparison", "infrastructure", "resource", "integrity", "operator_stop"), "unknown-fault-code")
    check((row["state"] == "fault") == (row["fault_code"] is not None), "inconsistent-fault-state")
    check(type(row["run_id"]) is str and bool(row["run_id"]) and _digest(row["source_id"])
          and _digest(row["enrollment_sha256"]), "invalid-record-context")
    _exact(row["operations"], OPERATIONS, "invalid-operation-fields")
    check(all(type(v) is int and v >= 0 for v in row["operations"].values()), "invalid-operation-count")
    check(type(row["readings"]) is list and len(row["readings"]) <= 3, "invalid-reading-list")
    for reading in row["readings"]:
        _exact(reading, ("index", "response", "response_sha256", "input_seed_sha256"), "invalid-reading-fields")
        check(type(reading["index"]) is int and 0 <= reading["index"] < 3 and type(reading["response"]) is list
              and _digest(reading["response_sha256"]) and _digest(reading["input_seed_sha256"]), "invalid-reading-data")
        try:
            validate_bits(tuple(reading["response"]), 64, "reading")
        except ValueError:
            raise ReconciliationError("invalid-reading-bits") from None
    if row["effective_response"] is not None:
        check(type(row["effective_response"]) is list, "invalid-effective-response")
        try:
            validate_bits(tuple(row["effective_response"]), 64, "effective")
        except ValueError:
            raise ReconciliationError("invalid-effective-bits") from None
    if row["decoder"] is not None:
        _exact(row["decoder"], ("outcome", "decoder_status", "reported_correction_count", "padding_valid", "failure_reason"), "invalid-decoder-fields")
        decoder = row["decoder"]
        check(decoder["outcome"] in ("decoder_failure", "invalid_format_or_padding", "candidate_valid_format")
              and decoder["decoder_status"] in ("uncorrectable", "decoded")
              and type(decoder["reported_correction_count"]) is int and -1 <= decoder["reported_correction_count"] <= 5
              and (decoder["padding_valid"] is None or type(decoder["padding_valid"]) is bool)
              and (decoder["failure_reason"] is None or type(decoder["failure_reason"]) is str), "invalid-decoder-values")
    check(row["retrieval_outcome"] in (None, "success", "unavailable", "malformed"), "invalid-retrieval-outcome")
    return row


@dataclass(frozen=True, repr=False)
class EnrollmentMaterial:
    """Trusted transient input, obtained independently of execution records.

    Never serialize via asdict. Redaction does not provide protected custody.
    Public anchor deliberately follows existing reference/helper digest conventions.
    """

    population_id: str
    device_id: str
    enrollment_id: str
    reference: tuple[int, ...]
    helper: HelperData
    credential: bytes

    def __post_init__(self):
        validate_bits(self.reference, 64, "trusted-reference")
        check(type(self.helper) is HelperData and self.helper.enrollment_id == self.enrollment_id,
              "trusted-helper-enrollment-mismatch")
        self.helper.validate()
        check(type(self.credential) is bytes and len(self.credential) == 4, "invalid-trusted-enrollment")

    @property
    def public_digest(self):
        return planning.object_digest(dict(population_id=self.population_id, device_id=self.device_id,
            enrollment_id=self.enrollment_id, reference_sha256=planning.object_digest(self.reference),
            helper_sha256=planning.object_digest(self.helper.helper_bits), reconstruction=asdict(self.helper.config)))

    def __repr__(self):
        return "EnrollmentMaterial(<redacted; trusted custody required>)"

    def __reduce_ex__(self, protocol):
        raise TypeError("trusted-enrollment-not-serializable")


@dataclass(frozen=True, repr=False)
class ReplayInputs:
    """Actual independent input data, not a replay_passed assertion.

    readings must come from a separate source replay/preserved-input custodian.
    stored_record is the preserved result of THIS invocation, not a current-store
    relookup: None=unavailable, malformed provider data=malformed. No retrieval is
    performed here. Credential/source generation and protected custody are absent.
    """

    binding_sha256: str
    run_id: str
    source_id: str
    enrollment: EnrollmentMaterial
    readings: tuple[tuple[int, ...], ...] = ()
    stored_record: object = None

    def __repr__(self):
        return "ReplayInputs(<redacted; independent provenance required>)"

    def __reduce_ex__(self, protocol):
        raise TypeError("private-replay-inputs-not-serializable")


class ReplayInputProvider(Protocol):
    def inputs_for(self, planned: PlannedAttempt) -> ReplayInputs: ...


class VerifiedFacts:
    """Opaque in-process handle; only its issuing verifier's table recognizes it."""

    __slots__ = ()

    def __new__(cls):
        raise TypeError("replay-verifier-required")

    def __repr__(self):
        return "VerifiedFacts(<opaque; local reconstruction/source comparison only>)"

    def __reduce_ex__(self, protocol):
        raise TypeError("verified-facts-not-serializable")


class ReplayVerifier:
    """One read-only pass. No retrial/replacement; exceptions become unmet/fault diagnostics.

    Provider is trusted input infrastructure, not a caller-asserted verifier result.
    Handles are issued only after real BCH replay (PUF) or invocation-specific
    source comparison (T). No supplied boolean or claimed category is accepted.
    """

    def __init__(self, provider: ReplayInputProvider, *, run_id, source_id):
        check(type(run_id) is str and bool(run_id) and _digest(source_id), "invalid-replay-context")
        self._provider, self.run_id, self.source_id = provider, run_id, source_id
        self._issued, self._attempted, self._enrollments = {}, set(), {}
        self.replay_decodes, self.enrollment_check_decodes = 0, 0

    def verify(self, planned, envelope):
        check(planned.identity not in self._attempted, "duplicate-replay-invocation")
        self._attempted.add(planned.identity)
        row = _parse(envelope)
        raw_sha256 = sha256(envelope.raw).hexdigest()
        check(_digest(envelope.expected_raw_sha256) and raw_sha256 == envelope.expected_raw_sha256,
              "record-content-hash-mismatch")
        check(planning.canonical(row["planned"]) == planning.canonical(planned.to_dict()), "planned-binding-conflict")
        check(row["state"] == "completed" and row["fault_code"] is None, "incomplete-source-attempt")
        check((row["run_id"], row["source_id"]) == (self.run_id, self.source_id), "replay-context-mismatch")
        try:
            inputs = self._provider.inputs_for(planned)
        except Exception:
            raise ReconciliationError("trusted-replay-inputs-unavailable") from None
        check(type(inputs) is ReplayInputs, "trusted-replay-inputs-required")
        check(inputs.binding_sha256 == planned.digest and (inputs.run_id, inputs.source_id) == (self.run_id, self.source_id),
              "trusted-replay-input-binding-mismatch")
        material = inputs.enrollment
        check(type(material) is EnrollmentMaterial, "trusted-enrollment-required")
        obj = planned.to_dict()
        b, a = obj["block"], obj["attempt"]
        check((material.population_id, material.device_id, material.enrollment_id)
              == (b["population_id"], b["device_id"], b["enrollment_id"])
              and row["enrollment_sha256"] == material.public_digest, "trusted-enrollment-binding-mismatch")
        if material.device_id in self._enrollments:
            check(self._enrollments[material.device_id] == material, "changed-trusted-enrollment")
        else:
            # Additional replay setup work, never counted as an original attempt decode.
            decoded_reference = reconstruct(material.reference, material.helper)
            self.enrollment_check_decodes += 1
            check(decoded_reference.outcome == "candidate_valid_format"
                  and decoded_reference.candidate_credential == material.credential, "trusted-enrollment-truth-mismatch")
            self._enrollments[material.device_id] = material
        expected = expected_operations(a["policy"])
        check(row["operations"] == expected, "policy-operation-count-mismatch")
        check(type(inputs.readings) is tuple and len(inputs.readings) == expected["readings"], "trusted-reading-count-mismatch")
        for reading in inputs.readings:
            validate_bits(reading, 64, "trusted-reading")
        check(len(row["readings"]) == expected["readings"], "recorded-reading-count-mismatch")
        for i, (recorded, bits) in enumerate(zip(row["readings"], inputs.readings)):
            check(recorded == dict(index=i, response=list(bits), response_sha256=planning.object_digest(bits),
                  input_seed_sha256=a["reading_seed_sha256"][i]), "reading-source-comparison-mismatch")
        reconstructed, retrieval = None, None
        if a["policy"] == T:
            check(not row["readings"] and row["decoder"] is None and row["effective_response"] is None
                  and row["effective_sha256"] is None, "stored-reconstruction-inapplicable")
            stored = inputs.stored_record
            if stored is None:
                retrieval = "unavailable"
            elif type(stored) is not StoredCredentialRecord:
                retrieval = "malformed"
            else:
                try:
                    stored.validate()
                except ValueError:
                    retrieval = "malformed"
                else:
                    if (stored.device_id, stored.enrollment_id, stored.reconstruction_id) != (
                            material.device_id, material.enrollment_id, material.helper.config.version):
                        retrieval = "malformed"
                    else:
                        check(stored.credential4 == material.credential, "stored-enrollment-credential-mismatch")
                        retrieval = "success"
            check(row["retrieval_outcome"] == retrieval, "stored-source-comparison-mismatch")
        else:
            check(inputs.stored_record is None and row["retrieval_outcome"] is None, "unexpected-stored-source")
            effective = inputs.readings[0] if a["policy"] == S else majority_vote3(inputs.readings)
            check(row["effective_response"] == list(effective)
                  and row["effective_sha256"] == planning.object_digest(effective), "effective-response-mismatch")
            if b["condition"] == CONDITIONS[3]:
                check(all(reading == inputs.readings[0] for reading in inputs.readings), "rho1-reading-identity-mismatch")
            decoded = reconstruct(effective, material.helper)
            self.replay_decodes += 1
            check(planning.canonical(row["decoder"]) == planning.canonical(decoder_record(decoded)), "decoder-replay-mismatch")
            reconstructed = analysis.evaluate_reconstruction(outcome=decoded.outcome,
                candidate_credential=decoded.candidate_credential, enrollment_truth=material.credential,
                effective_response=effective)
        _check_downstream(row["downstream"], reconstructed, retrieval)
        fields = {key: b[key] for key in ("population_id", "device_id", "enrollment_id", "condition", "attempt_index", "trial_id")}
        outcome = analysis.AttemptOutcome(**fields, config_sha256=planned.config_sha256, plan_sha256=planned.plan_sha256,
            policy=a["policy"], policy_attempt_id=a["policy_attempt_id"], execution_index=a["execution_index"],
            reconstruction=reconstructed, retrieval_outcome=retrieval)
        handle = object.__new__(VerifiedFacts)
        self._issued[handle] = planned.digest, raw_sha256, outcome
        return handle

    def project(self, handle, planned, raw_sha256):
        check(type(handle) is VerifiedFacts and handle in self._issued, "unrecognized-replay-facts")
        binding, digest, outcome = self._issued[handle]
        check(binding == planned.digest and digest == raw_sha256, "replay-facts-record-binding-mismatch")
        return outcome


def _check_downstream(downstream, reconstructed, retrieval):
    """Consistency only, not protocol replay or a claim that inference occurred."""
    _exact(downstream, ("verification", "admission", "session_active", "authorized_releases", "inference_calls"), "invalid-downstream-fields")
    check(downstream["verification"] in ("not_invoked", "verified", "credential_mismatch", "record_disabled")
          and downstream["admission"] in ("not_invoked", "authorized", "refused")
          and type(downstream["session_active"]) is bool
          and all(type(downstream[k]) is int and downstream[k] >= 0 for k in ("authorized_releases", "inference_calls")),
          "invalid-downstream-values")
    blocked = (reconstructed is not None and reconstructed.category in ("D", "I")) or retrieval in ("unavailable", "malformed")
    check(not blocked or downstream["verification"] == "not_invoked", "source-refusal-advanced-verification")
    check(reconstructed is None or reconstructed.category != "W" or downstream["verification"] != "verified", "wrong-credential-reported-verified")
    check(downstream["admission"] != "authorized" or downstream["verification"] == "verified", "admission-without-verification")
    check(not downstream["session_active"] or downstream["admission"] == "authorized", "session-without-admission")
    check(downstream["authorized_releases"] == 0 or downstream["session_active"], "release-without-session")
    check(downstream["inference_calls"] <= downstream["authorized_releases"], "inference-without-release")


@dataclass(frozen=True)
class ReconciliationAssessment:
    counts: dict
    issues: tuple[tuple[str, str], ...]
    record_hashes: tuple[tuple[str, str], ...]
    local_outcomes: tuple[analysis.AttemptOutcome, ...]
    verified_scope_complete: bool
    final_plan_checked: bool
    replay_decodes: int
    enrollment_check_decodes: int
    verified_record_replays: int
    unmet_prerequisites: tuple[str, ...]

    def analysis_handoff(self):
        # No caller boolean can supply the missing protected execution contract.
        raise ReconciliationError("final-analysis-handoff-blocked-unmet-execution-prerequisites")

    def summary(self):
        """Secret-free diagnostics; no raw records, candidates or replay inputs."""
        return dict(schema_version=VERSION+":assessment", counts=dict(self.counts), issues=self.issues,
            counts_basis="unique schema-readable recorded states; execution is not established by these counts",
            verified_scope_complete=self.verified_scope_complete, final_plan_checked=self.final_plan_checked,
            inference_eligible=False, full_independent_verification=False,
            record_validation="closed-versioned-Python-contract", content_hashes="raw-SHA256-consistency-only",
            reconstruction_replay="existing-BCH-with-independent-inputs" if self.replay_decodes else "not-performed",
            acquisition_verification="preserved-input-comparison-only" if self.verified_record_replays else "not-performed",
            source_environment_verification="unmet",
            unmet_prerequisites=self.unmet_prerequisites,
            replay_work=dict(completed_decodes=self.replay_decodes, enrollment_check_decodes=self.enrollment_check_decodes,
                             verified_record_replays=self.verified_record_replays, interrupted_work_status="not-certified",
                             new_scientific_attempts=0, new_statistical_samples=0))


def reconcile_ledger(index, records, *, verifier=None):
    """Streaming-compatible read-only pass; retain IDs/hashes and narrow projections.

    After the first fault, continue diagnosing raw records but perform no more
    replay work. Pending/missing attempts are never assigned successful outcomes.
    Duplicate identities revoke earlier local projections; no selective omission
    can produce verified_scope_complete. Independent passes need fresh verifiers.
    """
    check(type(index) is ScheduleIndex, "schedule-index-required")
    check(verifier is None or type(verifier) is ReplayVerifier, "replay-verifier-required")
    counts = Counter(planned=len(index.attempts), records=0, started=0, completed=0, pending=0, faulted=0,
                     missing=0, duplicate=0, unknown=0, locally_verified=0)
    issues, seen, hashes, outcomes, readings, stopped = [], set(), {}, {}, {}, False
    previous_index = -1
    for ordinal, envelope in enumerate(records):
        counts["records"] += 1
        identity = f"record:{ordinal:06d}"
        try:
            # Recover an ID for diagnostics even when the closed contract fails.
            if type(envelope) is RecordedExecution and type(envelope.raw) is bytes and len(envelope.raw) <= 1_048_576:
                try:
                    candidate = planning.read_json(envelope.raw)
                    claimed = candidate.get("planned", {}).get("attempt", {}).get("policy_attempt_id")
                    if type(claimed) is str and _digest(claimed):
                        identity = claimed
                except (ValueError, TypeError, AttributeError, UnicodeError):
                    pass
                # Retain a content fingerprint even for malformed records, for
                # comparison in a later pass. It conveys no validation success.
                hashes[identity] = sha256(envelope.raw).hexdigest()
            if identity in seen:
                counts["duplicate"] += 1
                outcomes.pop(identity, None)
                raise ReconciliationError("duplicate-attempt-record")
            seen.add(identity)
            row = _parse(envelope)
            identity = row["planned"]["attempt"]["policy_attempt_id"]
            state = row["state"]
            counts["started"] += int(state in ("started", "completed", "fault"))
            counts["completed"] += int(state == "completed")
            counts["pending"] += int(state in ("pending", "started"))
            counts["faulted"] += int(state == "fault")
            raw_digest = sha256(envelope.raw).hexdigest()
            hashes[identity] = raw_digest
            check(_digest(envelope.expected_raw_sha256) and raw_digest == envelope.expected_raw_sha256, "record-content-hash-mismatch")
            if identity not in index.attempts:
                counts["unknown"] += 1
                raise ReconciliationError("unknown-attempt-record")
            planned = index.attempts[identity]
            expected = planned.to_dict()
            check(planning.canonical(row["planned"]) == planning.canonical(expected), "planned-binding-conflict")
            b, a = expected["block"], expected["attempt"]
            check(a["execution_index"] > previous_index, "ledger-execution-order-conflict")
            previous_index = a["execution_index"]
            operations = expected_operations(a["policy"])
            check(all(row["operations"][key] <= operations[key] for key in OPERATIONS), "policy-operation-count-mismatch")
            check(len(row["readings"]) == row["operations"]["readings"], "recorded-reading-count-mismatch")
            if state != "completed":
                if state == "pending":
                    check(not any(row["operations"].values()) and row["decoder"] is None
                          and row["effective_response"] is None and row["effective_sha256"] is None
                          and row["retrieval_outcome"] is None, "pending-record-has-results")
                raise ReconciliationError("fault:"+row["fault_code"] if state == "fault" else "incomplete-attempt-record")
            check(row["operations"] == operations, "policy-operation-count-mismatch")
            check(not stopped, "after-stopping-fault-replay-not-performed")
            check(verifier is not None, "unmet:trusted-replay-input-provider")
            handle = verifier.verify(planned, envelope)
            outcome = verifier.project(handle, planned, raw_digest)
            outcomes[identity] = outcome
            if a["policy"] != T:
                readings[b["device_id"], b["condition"], b["attempt_index"], a["policy"]] = (
                    identity, tuple(tuple(r["response"]) for r in row["readings"]), outcome.reconstruction)
                bits = readings[b["device_id"], b["condition"], b["attempt_index"], a["policy"]][1]
                peer = readings.get((b["device_id"], b["condition"], b["attempt_index"], M if a["policy"] == S else S))
                if peer and bits[0] != peer[1][0]:
                    issues.append((peer[0], "matched-reading-zero-mismatch"))
                    raise ReconciliationError("matched-reading-zero-mismatch")
                if peer and b["condition"] == CONDITIONS[3] and outcome.reconstruction != peer[2]:
                    issues.append((peer[0], "rho1-reconstruction-identity-mismatch"))
                    raise ReconciliationError("rho1-reconstruction-identity-mismatch")
                if b["condition"] in (CONDITIONS[0], CONDITIONS[5]):
                    linked_condition = CONDITIONS[5] if b["condition"] == CONDITIONS[0] else CONDITIONS[0]
                    linked = readings.get((b["device_id"], linked_condition, b["attempt_index"], a["policy"]))
                    if linked and (bits != linked[1] or outcome.reconstruction != linked[2]):
                        issues.append((linked[0], "common-control-identity-mismatch"))
                        raise ReconciliationError("common-control-identity-mismatch")
        except ReconciliationError as error:
            issues.append((identity, str(error)))
            stopped = True
        except Exception:
            # Faults are never converted to D/I/W. Do not leak decoder/provider inputs.
            issues.append((identity, "replay-infrastructure-fault"))
            stopped = True
    # Comparison edges are indexed; no all-pairs search through 108,000 records.
    for (d, c, t, policy), (identity, bits, decoded) in sorted(readings.items()):
        peer = readings.get((d, c, t, M if policy == S else S))
        if peer and bits[0] != peer[1][0]:
            issues.append((identity, "matched-reading-zero-mismatch"))
        if c == CONDITIONS[3] and peer and decoded != peer[2]:
            issues.append((identity, "rho1-reconstruction-identity-mismatch"))
        if c == CONDITIONS[5]:
            op = readings.get((d, CONDITIONS[0], t, policy))
            if op and (bits != op[1] or decoded != op[2]):
                issues.append((identity, "common-control-identity-mismatch"))
                issues.append((op[0], "common-control-identity-mismatch"))
    for identity, _ in issues:
        outcomes.pop(identity, None)
    missing = set(index.attempts)-seen
    issues.extend((identity, "missing-attempt-record") for identity in sorted(missing))
    counts["missing"], counts["locally_verified"] = len(missing), len(outcomes)
    complete = not issues and len(outcomes) == len(index.attempts)
    prerequisites = PREREQUISITES + (() if index._final_checked else ("validated-complete-final-planning-contract",))
    if verifier is None:
        prerequisites += ("trusted-replay-input-provider",)
    return ReconciliationAssessment(dict(counts), tuple(sorted(set(issues))), tuple(sorted(hashes.items())),
        tuple(sorted(outcomes.values(), key=lambda o: o.execution_index)), complete, index._final_checked,
        verifier.replay_decodes if verifier else 0, verifier.enrollment_check_decodes if verifier else 0,
        len(verifier._issued) if verifier else 0, prerequisites)


def compare_passes(first, second):
    """Compare independently rerun read-only assessments; never seal or rewrite evidence."""
    check(type(first) is ReconciliationAssessment and type(second) is ReconciliationAssessment, "assessments-required")
    check(first is not second, "distinct-reconciliation-passes-required")
    a, b = dict(first.record_hashes), dict(second.record_hashes)
    changed = sorted(identity for identity in set(a) & set(b) if a[identity] != b[identity])
    removed, added = sorted(set(a)-set(b)), sorted(set(b)-set(a))
    facts_equal = first.local_outcomes == second.local_outcomes
    return dict(scope="two-local-reconciliation-passes-only", full_independent_verification=False,
        consistent=first.verified_scope_complete and second.verified_scope_complete
                   and not (changed or removed or added) and facts_equal,
        changed=changed, removed=removed, added=added, replayed_facts_equal=facts_equal,
        unmet_prerequisites=tuple(sorted(set(first.unmet_prerequisites+second.unmet_prerequisites))))
