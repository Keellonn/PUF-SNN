"""Bounded Week 9 calibration identities and planning; planning makes no observations."""
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from random import Random
import secrets

from jsonschema import Draft202012Validator

from puf_snn.auth.credential_verifier import CredentialVerifierRecord, InMemoryCredentialVerifierKeyProvider
from puf_snn.puf.device import create_device
from puf_snn.puf.ro_puf import generate_response
from puf_snn.puf.variables import ReadConditions
from puf_snn.reconstruction import enroll
from . import correlated_noise_v1 as noise
from . import majority3_auth_v1 as previous
from .majority3_auth_v1 import (ROOT, canonical, object_digest, read_json_bytes, require,
    DeviceEnrollment, public_enrollment_record, trial_noise_config)

VERSION = "week9-shared-noise-calibration-v1"
EVIDENCE_VERSION = VERSION + ":evidence-v1"
RULES_VERSION = VERSION + ":proposed-rules-v1"
CONFIG_PATH = ROOT / "configs/shared_noise_calibration_v1.json"
SPEC_PATH = "docs/week9-shared-noise-study-specification.md"
CONDITIONS = tuple((f"s{s:03d}", s / 100) for s in (10, 15, 20, 25))
POLICIES = tuple(previous.POLICIES)
STORED = "stored-provisioned-v1"  # Used only by inherited PUF semantic checks.


def validate_schema(kind, obj):
    path = ROOT / f"schemas/shared-noise-calibration-{kind}-v1.schema.json"
    validator = previous._checked_schema_validator(path.read_bytes(), Draft202012Validator)
    require(not list(validator.iter_errors(obj)), f"invalid calibration {kind} schema")


@dataclass(frozen=True)
class StudyConfig:
    payload: str

    def __post_init__(self):
        obj = read_json_bytes(self.payload)
        validate_schema("config", obj)
        a = obj["allocation"]
        counts = tuple(a[k] for k in ("groups", "devices_per_group", "trials_per_device_sigma"))
        if obj["mode"] == "bounded-calibration":
            require(counts == (4, 6, 20), "calibration allocation is frozen")
        else:
            require(all(type(n) is int and 1 <= n <= 2 for n in counts)
                    and counts[2] == 2, "fixtures require <=2 groups/devices and two trials")
        object.__setattr__(self, "payload", canonical(obj).decode("ascii"))

    @classmethod
    def from_dict(cls, obj):
        return cls(canonical(obj).decode("ascii"))

    @classmethod
    def load(cls, path=CONFIG_PATH):
        return cls(Path(path).read_text(encoding="utf-8"))

    def to_dict(self):
        return read_json_bytes(self.payload)

    @property
    def digest(self):
        return sha256(self.payload.encode("ascii")).hexdigest()


def phase_identity(phase, population, device, noise_domain, attempt=0):
    require(phase in ("calibration", "final"), "unknown phase")
    version = VERSION if phase == "calibration" else "week9-shared-noise-final-v1"
    master = 2026102801 if phase == "calibration" else 2026102811
    return noise.AttemptIdentity(master, population, device, version + ":" + noise_domain, attempt)


def study_seed(config, domain):
    field = {"schedule": "schedule_seed", "device-bootstrap": "bootstrap_seed",
             "group-bootstrap-sensitivity": "group_sensitivity_seed"}.get(domain)
    require(field is not None, "unsupported calibration RNG domain")
    return int(object_digest(dict(experiment_id=VERSION, domain=domain,
        seed=config.to_dict()[field], config_sha256=config.digest)), 16)


def compile_plan(config):
    obj = config.to_dict()
    a = obj["allocation"]
    prefix = "w9c" if obj["mode"] == "bounded-calibration" else "w9u"
    blocks = []
    for p in range(a["groups"]):
        population = f"{prefix}-p{p:03d}"
        for d in range(a["devices_per_group"]):
            device = f"{population}-d{d:02d}"
            for c, (condition, sigma) in enumerate(CONDITIONS):
                for attempt in range(a["trials_per_device_sigma"]):
                    identity = phase_identity("calibration", population, device, condition + ":r000", attempt)
                    trial = dict(experiment_id=VERSION, config_sha256=config.digest,
                        population_id=population, device_id=device, enrollment_id=device + "-enroll-v1",
                        condition=condition, attempt_index=attempt, sigma=sigma, rho=0.0, common_offset=0,
                        noise_identity=asdict(identity),
                        noise_shared_seed_sha256=sha256(noise.canonical_seed_bytes(identity, noise.SESSION)).hexdigest(),
                        reading_seed_sha256=[sha256(noise.canonical_seed_bytes(identity, noise.READING, i)).hexdigest()
                                             for i in range(3)])
                    trial["trial_id"] = object_digest(trial)
                    trial["policy_order"] = list(POLICIES if (attempt+c+d+p) % 2 == 0 else reversed(POLICIES))
                    blocks.append(trial)
    Random(study_seed(config, "schedule")).shuffle(blocks)
    devices = a["groups"] * a["devices_per_group"]
    plan = dict(schema_version=VERSION + ":plan", experiment_id=VERSION, config_sha256=config.digest,
        blocks=blocks, counts=dict(groups=a["groups"], simulated_devices=devices,
            matched_trials=len(blocks), arm_attempts=2*len(blocks), expected_reads=4*len(blocks),
            expected_runtime_decodes=2*len(blocks), expected_votes=len(blocks),
            enrollment_reference_readings=devices,
            two_pass_replay_measurements=8*len(blocks), two_pass_replay_decodes=4*len(blocks),
            two_pass_reference_readings=2*devices, statistical_samples_added_by_replay=0))
    plan["plan_sha256"] = object_digest(plan)
    return plan


def validate_plan(config, plan):
    validate_schema("plan", plan)
    require(plan == compile_plan(config), "plan differs from complete canonical calibration schedule")


def scheduled_attempts(plan):
    index = 0
    for trial in plan["blocks"]:
        for policy in trial["policy_order"]:
            yield trial, policy, index
            index += 1


def attempt_id(trial, policy):
    require(policy in POLICIES, "calibration permits S/M only")
    return object_digest(dict(trial_id=trial["trial_id"], policy=policy))


def enrollment_material(config, population, device_id):
    identity = phase_identity("calibration", population, device_id, "enrollment-v1")
    device = create_device(device_id, 128, 1.0, rng=Random(noise.derive_seed(identity, noise.MANUFACTURING)))
    reference = generate_response(device, noise.PAIRS, 100, ReadConditions(0, 0),
                                  rng=Random(noise.derive_seed(identity, noise.ENROLLMENT)))
    credential = Random(noise.derive_seed(identity, noise.CREDENTIAL)).getrandbits(32).to_bytes(4, "big")
    helper = enroll(reference, credential, enrollment_id=device_id + "-enroll-v1")
    return device, reference, helper, credential


def prepare_enrollment(config, population, device_id):
    device, reference, helper, credential = enrollment_material(config, population, device_id)
    provider = InMemoryCredentialVerifierKeyProvider(VERSION, secrets.token_bytes(32))
    record = CredentialVerifierRecord.enroll(device_id=device_id, enrollment_id=helper.enrollment_id,
        reconstruction_id=helper.config.version, verifier_key_id=VERSION, credential4=credential, key_provider=provider)
    return DeviceEnrollment(population, device, reference, helper, credential, record, provider)


def prepare_population(config, plan):
    return {d: prepare_enrollment(config, p, d)
            for p, d in sorted({(t["population_id"], t["device_id"]) for t in plan["blocks"]})}


def dry_plan(config):
    plan = compile_plan(config)
    validate_plan(config, plan)
    return dict(experiment_id=VERSION, mode=config.to_dict()["mode"], observations_generated=0,
        config_sha256=config.digest, plan_sha256=plan["plan_sha256"], counts=plan["counts"],
        rules_status="proposed-pending-review", scientific_execution_authorized=False,
        final_execution_enabled=False)
