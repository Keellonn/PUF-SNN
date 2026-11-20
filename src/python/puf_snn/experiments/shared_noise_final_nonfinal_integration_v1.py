"""Bounded, opt-in, temporary scientific fixture; never a final-study runner.

Exactly one isolated device/trial across six conditions (ScheduleIndex requires
all six). No final configuration, cohort generator, bootstrap, protocol endpoint,
completion receipt or checkpoint is used. The Task 4/7 schema names are retained
for compatibility; every source/device/run identity is fixture-only.

The in-memory custodian is a logical separation from untrusted evidence, NOT
protected persistence or independently authenticated provenance. Replay regenerates
manufacturing, noiseless enrollment and actual indexed measurements from retained
fixture inputs, then uses Task 7's real BCH verifier. Retrieval replay uses the
original invocation result, never another store lookup. One trusted filesystem
owner and trusted Python code are assumed, as in Task 8.

Evidence uses Task 8's exclusive pending-file / fsync / no-replace publication
primitive in a separate temporary directory. Windows explicitly remains
fixture-process-only; successful calls do not establish power-loss durability.
Faults preserve residue and stop the controller permanently. Counts describe
completed operations; an interrupted operation may have unknown partial work.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import os
from random import Random
from types import MappingProxyType

from puf_snn.auth.stored_credential import (
    InMemoryStoredCredentialProvider, StoredCredentialRecord,
)
from puf_snn.puf import acquisition
from puf_snn.puf.device import create_device
from puf_snn.puf.ro_puf import generate_response
from puf_snn.puf.variables import ReadConditions
from puf_snn.reconstruction import enroll, reconstruct
from . import correlated_noise_v1 as noise
from . import shared_noise_final_controller_v1 as barrier
from . import shared_noise_final_evidence_v1 as evidence
from . import shared_noise_final_measurement_v1 as measurement
from . import shared_noise_final_plan_v1 as planning
from . import shared_noise_final_reconciliation_v1 as recon

VERSION = "fixture-nonfinal-integration-v1"
MASTER = 86753091
POPULATION = "fixture-integration-group"
DEVICE = "fixture-integration-device"
ENROLLMENT = "fixture-integration-enrollment"
CREDENTIAL = b"Fxt1"
SOURCE = planning.object_digest(dict(version=VERSION, model=noise.MODEL_VERSION,
    implementation="local-fixture-source-label-not-a-source-snapshot"))
CONFIG = planning.object_digest(dict(version=VERSION, master=MASTER, population=POPULATION,
    device=DEVICE, enrollment=ENROLLMENT, oscillators=128, manufacturing_std=1.,
    conditions=planning.CONDITIONS, credential="fixed-32-bit-fixture", trial_count=1))


class IntegrationError(ValueError):
    """Fixed, secret-free stopping diagnostic."""


def check(ok, code):
    if not ok:
        raise IntegrationError(code)


def _identity(domain):
    return noise.AttemptIdentity(MASTER, POPULATION, DEVICE, VERSION + ":" + domain, 0)


def fixture_schedule():
    """Only metadata for 18 fixture arms. Never call compile_plan/study_seed."""
    blocks = []
    for c, (condition, sigma, rho, domain) in enumerate(planning.CONDITIONS):
        identity = _identity(domain)
        common = c == 5
        block = dict(schema_version=planning.VERSION + ":planned-block",
            experiment_id=planning.VERSION, config_sha256=CONFIG,
            population_id=POPULATION, device_id=DEVICE, enrollment_id=ENROLLMENT,
            condition=condition, attempt_index=0, sigma=sigma, rho=rho,
            common_offset=(-1, 1)[Random(_checked_seed(identity, noise.COMMON_MODE)).randrange(2)] if common else 0,
            noise_identity=asdict(identity),
            noise_shared_seed_sha256=planning.seed_digest(identity, noise.SESSION),
            reading_seed_sha256=[planning.seed_digest(identity, noise.READING, r) for r in range(3)],
            common_offset_seed_sha256=planning.seed_digest(identity, noise.COMMON_MODE) if common else None,
            linked_operating_trial_id=blocks[0]["trial_id"] if common else None)
        block["trial_id"] = planning.trial_id(block)
        block.update(policy_order=list(planning.POLICIES), block_index=c)
        attempts = []
        for p, policy in enumerate(planning.POLICIES):
            indices = {recon.S: [0], recon.M: [0, 1, 2], recon.T: []}[policy]
            attempts.append(dict(schema_version=planning.VERSION + ":planned-attempt",
                experiment_id=planning.VERSION, condition=condition, trial_id=block["trial_id"],
                policy=policy, policy_attempt_id=planning.attempt_id(block, policy), execution_index=3*c+p,
                reading_indices=indices,
                noise_shared_seed_sha256=block["noise_shared_seed_sha256"] if indices else None,
                reading_seed_sha256=[block["reading_seed_sha256"][r] for r in indices]))
        block["attempts"] = attempts
        blocks.append(block)
    plan_digest = planning.object_digest(dict(version=VERSION, blocks=blocks))
    bindings = tuple(b for block in blocks for b in recon.block_bindings(CONFIG, plan_digest, block))
    recon.ScheduleIndex(bindings)
    return bindings


def _spec(planned):
    b = planned.to_dict()["block"]
    return measurement.MeasurementSpec(b["condition"], noise.AttemptIdentity(**b["noise_identity"]), b["common_offset"])


def _device():
    return create_device(DEVICE, 128, 1., rng=Random(_checked_seed(_identity("enrollment-v1"), noise.MANUFACTURING)))


def _checked_seed(identity, domain, reading=None):
    value = noise.derive_seed(identity, domain, reading)
    check(value == int(planning.seed_digest(identity, domain, reading), 16), "fixture-seed-derivation-conflict")
    return value


def _enrollment(device):
    identity = _identity("enrollment-v1")
    # Noiseless reference uses the existing simulator, separate from trial reads.
    reference = generate_response(device, noise.PAIRS, noise.NOMINAL_FREQUENCY, ReadConditions(0., 0.),
        rng=Random(_checked_seed(identity, noise.ENROLLMENT)))
    helper = enroll(reference, CREDENTIAL, enrollment_id=ENROLLMENT)
    return recon.EnrollmentMaterial(POPULATION, DEVICE, ENROLLMENT, reference, helper, CREDENTIAL)


@dataclass(frozen=True)
class SourceInputs:
    """Retained deterministic source identity; contains no recorded responses."""

    spec: measurement.MeasurementSpec
    shared_seed_sha256: str
    reading_seed_sha256: tuple[str, ...]


def _source(planned):
    spec = _spec(planned)
    _checked_seed(spec.identity, noise.SESSION)
    for r in range(3):
        _checked_seed(spec.identity, noise.READING, r)
    return SourceInputs(spec, planning.seed_digest(spec.identity, noise.SESSION),
        tuple(planning.seed_digest(spec.identity, noise.READING, r) for r in range(3)))


def _invocation(context, planned):
    return planning.object_digest(dict(version=VERSION, context=asdict(context), binding=planned.digest))


class FixtureCustodian:
    """Nonpersistent, one-use inputs; not secure storage or hostile-code isolation.

    Setup performs one manufacturing/reference/enrollment construction. inputs_for
    performs no PUF acquisition or BCH decoding. T lookup occurs only when called
    after the controller's started barrier, and its exact result is retained.
    """

    def __init__(self, *, run_id="fixture-integration-run"):
        self.bindings = fixture_schedule()
        self.context = evidence.JournalContext(VERSION, VERSION, VERSION, SOURCE,
            CONFIG, self.bindings[0].plan_sha256, run_id)
        self.device = _device()
        self.enrollment = _enrollment(self.device)
        self.store = InMemoryStoredCredentialProvider((StoredCredentialRecord(DEVICE, ENROLLMENT,
            self.enrollment.helper.config.version, CREDENTIAL),))
        self._attempted, self._retained, self._retrievals = set(), {}, {}
        self._planned = MappingProxyType({p.identity: p for p in self.bindings})

    def validate(self, request, planned):
        check(type(request) is evidence.CustodyRequest and request.context == self.context
              and self._planned.get(planned.identity) == planned
              and request.planned == evidence.PlannedFixture.from_planned(planned)
              and request.invocation_id == _invocation(self.context, planned), "fixture-custody-binding-conflict")

    def inputs_for(self, request):
        planned = self._planned.get(request.planned.policy_attempt_id)
        check(planned is not None, "unknown-fixture-custody-attempt")
        self.validate(request, planned)
        check(planned.identity not in self._attempted, "fixture-custody-already-invoked")
        self._attempted.add(planned.identity)
        stored, retrieval = None, None
        if request.planned.policy == recon.T:
            stored = self.store.get_credential(device_id=DEVICE, enrollment_id=ENROLLMENT,
                reconstruction_id=self.enrollment.helper.config.version)
            retrieval = evidence.InvocationRetrievalEvidence(request, stored,
                planning.object_digest(dict(invocation_id=request.invocation_id, source_id=SOURCE)))
            self._retrievals[planned.identity] = retrieval
        replay = recon.ReplayInputs(planned.digest, self.context.run_id, SOURCE, self.enrollment, (), stored)
        result = evidence.ProtectedInputs(request, replay, self.device, _source(planned), retrieval)
        self._retained[planned.identity] = result
        return result

    def replay_provider(self):
        # Snapshot original invocation objects; replay cannot perform store lookups.
        return FixtureReplayProvider(self.context, self.bindings, self.device,
            self.enrollment, MappingProxyType(dict(self._retained)), MappingProxyType(dict(self._retrievals)))

    def __repr__(self):
        return "FixtureCustodian(<redacted; in-memory fixture only>)"


class FixtureReplayProvider:
    """Independent source regeneration from custody, never from evidence rows."""

    def __init__(self, context, bindings, device, enrollment, retained, retrievals):
        self.context, self.bindings = context, bindings
        self.device, self.enrollment, self.retained = device, enrollment, retained
        self._retrievals = retrievals
        self.source_readings = 0
        self._regenerated = None

    def inputs_for(self, planned):
        check(planned in self.bindings, "replay-planning-conflict")
        material = self.retained[planned.identity]
        request = material.request
        check(request.context == self.context and request.planned == evidence.PlannedFixture.from_planned(planned)
              and request.invocation_id == _invocation(self.context, planned), "replay-invocation-conflict")
        check(material.manufacturing_state == self.device and material.deterministic_source_inputs == _source(planned),
              "replay-source-seed-conflict")
        check(material.replay_inputs.enrollment == self.enrollment, "replay-enrollment-conflict")
        check((material.replay_inputs.binding_sha256, material.replay_inputs.run_id, material.replay_inputs.source_id)
              == (planned.digest, self.context.run_id, self.context.source_id), "replay-retained-binding-conflict")
        if self._regenerated is None:
            device = _device()
            check(device == self.device, "replay-manufacturing-conflict")
            enrollment = _enrollment(device)
            check(enrollment == self.enrollment, "replay-enrollment-truth-conflict")
            self._regenerated = device, enrollment
        device, enrollment = self._regenerated
        policy = planned.to_dict()["attempt"]["policy"]
        reads, stored = [], None
        if policy == recon.T:
            retrieval = material.retrieval_evidence
            check(type(retrieval) is evidence.InvocationRetrievalEvidence
                  and retrieval is self._retrievals.get(planned.identity) and retrieval.request == request
                  and retrieval.stored_record is material.replay_inputs.stored_record
                  and retrieval.provenance_sha256 == planning.object_digest(dict(
                      invocation_id=request.invocation_id, source_id=SOURCE)), "replay-retrieval-invocation-conflict")
            stored = retrieval.stored_record
        else:
            source = material.deterministic_source_inputs
            shared = noise.generate_shared_disturbance(source.spec.identity)
            for r in range(1 if policy == recon.S else 3):
                # Use the actual indexed simulator, not the execution's readings.
                reads.append(noise.measure_indexed(device, source.spec.noise_config, source.spec.identity, shared, r).response)
                self.source_readings += 1
        return recon.ReplayInputs(planned.digest, self.context.run_id, self.context.source_id,
            enrollment, tuple(reads), stored)


def _retrieval_outcome(stored, enrollment):
    if stored is None:
        return "unavailable"
    if type(stored) is not StoredCredentialRecord:
        return "malformed"
    try:
        stored.validate()
    except ValueError:
        return "malformed"
    if (stored.device_id, stored.enrollment_id, stored.reconstruction_id) != (
            DEVICE, ENROLLMENT, enrollment.helper.config.version):
        return "malformed"
    check(stored.credential4 == enrollment.credential, "stored-credential-integrity-fault")
    return "success"


class NonfinalController:
    """Single-use 18-attempt controller. Caller closes it even after failure."""

    def __init__(self, fixture_root, custodian, *, durability=None):
        check(type(custodian) is FixtureCustodian, "fixture-custodian-required")
        # Exact fixed schedule prevents reduced/expanded/foreign fixture execution.
        check(custodian.bindings == fixture_schedule(), "fixture-schedule-conflict")
        self.custodian, self.context, self.bindings = custodian, custodian.context, custodian.bindings
        self.stopped = False
        mode = durability or ("fixture-process-only" if os.name == "nt" else "directory-fsync")
        self.records = evidence._checked_path(fixture_root, os.path.join(fixture_root, "fixture-evidence-records"))
        self.records.mkdir(exist_ok=False)
        self.journal = evidence.FixtureJournal.create(fixture_root,
            os.path.join(fixture_root, "fixture-evidence-journal"), self.context,
            tuple(evidence.PlannedFixture.from_planned(p) for p in self.bindings), durability=mode)
        self.journal.io.sync_directory(self.records.parent)

    def execute(self, planned):
        check(not self.stopped, "fixture-controller-stopped")
        counts = dict.fromkeys(recon.OPERATIONS, 0)
        started = False
        try:
            check(planned in self.bindings, "fixture-planning-conflict")
            spec = evidence.PlannedFixture.from_planned(planned)
            barrier._active_fixture(self.journal, self.context, spec)
            request = evidence.CustodyRequest(evidence.CUSTODY_VERSION, self.context, spec,
                _invocation(self.context, planned))
            self.custodian.validate(request, planned)
            barrier._append(self.journal, planned.identity, "started", "fixture-start-publication-uncertain")
            started = True
            inputs = evidence.obtain_protected_inputs(self.custodian, request, planned)
            check(inputs.manufacturing_state == self.custodian.device
                  and inputs.deterministic_source_inputs == _source(planned)
                  and inputs.replay_inputs.enrollment == self.custodian.enrollment, "fixture-transient-input-conflict")
            material = inputs.replay_inputs.enrollment
            readings, effective, decoded, retrieval = [], None, None, None
            if spec.policy == recon.T:
                counts["stored_retrievals"] += 1
                retrieval = _retrieval_outcome(inputs.retrieval_evidence.stored_record, material)
            else:
                source = inputs.deterministic_source_inputs.spec
                config = acquisition.SINGLE_READ if spec.policy == recon.S else acquisition.MAJORITY_3
                reader = noise.CorrelatedResponseReader(inputs.manufacturing_state,
                    source.noise_config, source.identity, config)

                def read():
                    response = reader()
                    readings.append(response)
                    counts["readings"] += 1
                    return response

                # Compose Task 5's underlying reader/acquisition interfaces so
                # completed reads remain countable if a later read interrupts.
                # acquire_measurement exposes only a fully completed result.
                effective = acquisition.acquire_response(read, config)
                counts["votes"] += int(spec.policy == recon.M)
                check(reader.measurement_count == config.read_count and len(readings) == config.read_count,
                      "fixture-acquisition-count-conflict")
                decoded = reconstruct(effective, material.helper)
                counts["reconstructions"] += 1
                counts["bch_decodes"] += 1
            check(counts == recon.expected_operations(spec.policy), "fixture-operation-count-conflict")
            a = planned.to_dict()["attempt"]
            raw = planning.canonical(dict(schema_version=recon.VERSION + ":record", planned=planned.to_dict(),
                run_id=self.context.run_id, source_id=self.context.source_id, enrollment_sha256=material.public_digest,
                state="completed", fault_code=None, operations=counts,
                readings=[dict(index=r, response=list(bits), response_sha256=planning.object_digest(bits),
                    input_seed_sha256=a["reading_seed_sha256"][r]) for r, bits in enumerate(readings)],
                effective_response=list(effective) if effective is not None else None,
                effective_sha256=planning.object_digest(effective) if effective is not None else None,
                decoder=recon.decoder_record(decoded) if decoded is not None else None,
                retrieval_outcome=retrieval, downstream=dict(verification="not_invoked", admission="not_invoked",
                    session_active=False, authorized_releases=0, inference_calls=0)))
            # Evidence bytes are outside the metadata journal. No overwrite, retry,
            # rollback or successful terminal event after uncertain publication.
            try:
                evidence._publish(self.records, planned.identity + ".json", raw, self.journal.io)
            except BaseException:
                self.journal.poisoned = True
                raise
            barrier._append(self.journal, planned.identity, "completed", "fixture-completion-publication-uncertain",
                operations=counts, record_sha256=sha256(raw).hexdigest())
            return sha256(raw).hexdigest()
        except BaseException as error:
            self.stopped = True
            if started and not self.journal.poisoned:
                code = ("resource" if isinstance(error, MemoryError) else
                    "numerical_comparison" if isinstance(error, (ArithmeticError, noise.CommonModeNumericalError)) else
                    "integrity" if isinstance(error, (IntegrationError, recon.ReconciliationError)) else
                    "infrastructure" if isinstance(error, Exception) else "operator_stop")
                barrier._append(self.journal, planned.identity, "fault", "fixture-fault-publication-uncertain",
                    operations=counts, fault_code=code)
            if isinstance(error, Exception):
                raise IntegrationError("fixture-execution-stopped") from None
            raise

    def run(self):
        """The one fixed schedule; failures propagate, and nothing is retried."""
        for planned in self.bindings:
            self.execute(planned)

    def close(self):
        self.journal.close()

    def reconcile(self, *, provider=None):
        """Read-only local verification; no anchor/receipt or inference authority.

        Journal and evidence must both be complete before any replay work. The
        journal hash supplies consistency only; no authentication is inferred.
        A new provider/verifier is used for each independent read-only pass.
        """
        check(self.journal.closed, "close-journal-before-replay")
        found = evidence.inspect_journal(self.journal.root, self.journal.directory)
        check(not found.requires_stop and not found.planned_unstarted, "fixture-journal-incomplete-or-uncertain")
        header = planning.read_json(found.header)
        check(header["context"] == asdict(self.context)
              and header["attempts"] == [asdict(evidence.PlannedFixture.from_planned(p)) for p in self.bindings],
              "fixture-journal-binding-conflict")
        expected = {p.identity + ".json" for p in self.bindings}
        evidence._checked_path(self.journal.root, self.records)
        check({p.name for p in self.records.iterdir()} == expected, "fixture-evidence-publication-unresolved")
        completed = {e["policy_attempt_id"]: e for e in map(planning.read_json, found.events)
                     if e["event_type"] == "completed"}
        records = []
        for planned in self.bindings:
            raw = evidence._read(self.records / (planned.identity + ".json"), 1_048_576)
            digest = completed[planned.identity]["record_sha256"]
            check(sha256(raw).hexdigest() == digest, "fixture-evidence-digest-conflict")
            records.append(recon.RecordedExecution(raw, digest))
        provider = self.custodian.replay_provider() if provider is None else provider
        check(type(provider) is FixtureReplayProvider, "fixture-replay-provider-required")
        verifier = recon.ReplayVerifier(provider, run_id=self.context.run_id, source_id=self.context.source_id)
        return recon.reconcile_ledger(recon.ScheduleIndex(self.bindings), records, verifier=verifier)
