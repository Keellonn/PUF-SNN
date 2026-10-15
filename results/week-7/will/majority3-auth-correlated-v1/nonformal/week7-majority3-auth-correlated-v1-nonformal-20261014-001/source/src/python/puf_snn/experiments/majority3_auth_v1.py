"""Week 7 matched study configuration, planning and immutable enrollment inputs.

Planning never runs authentication. Formal execution is intentionally absent.
Credential truth stays in memory, outside the acquisition callback and traces.
"""
from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from random import Random
import secrets

from jsonschema import Draft202012Validator

from puf_snn.auth.config import AuthConfig
from puf_snn.auth.credential_verifier import (
    CredentialVerifierRecord, InMemoryCredentialVerifierKeyProvider,
)
from puf_snn.puf.acquisition import SINGLE_READ, MAJORITY_3
from puf_snn.puf.device import Device, create_device
from puf_snn.puf.ro_puf import generate_response
from puf_snn.puf.variables import ReadConditions
from puf_snn.reconstruction import HelperData, enroll
from . import correlated_noise_v1 as noise

VERSION = "week7-majority3-auth-correlated-v1"
# Evidence revisions must not change the reviewed RNG/configuration identities.
EVIDENCE_VERSION = VERSION + ":evidence-v2"
ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = ROOT / "configs/majority3_auth_correlated_v1.json"
POLICIES = {p.policy: p for p in (SINGLE_READ, MAJORITY_3)}
CONDITIONS = (
    ("independent_nominal", 0.10, 0.00, (0,)),
    ("independent_stress", 0.25, 0.00, (0,)),
    ("common_control", 0.10, 0.00, (-1, 1)),
    ("differential_rho50", 0.10, 0.50, (0,)),
    ("differential_rho90", 0.10, 0.90, (0,)),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def object_digest(obj):
    return sha256(canonical(obj)).hexdigest()


def read_json_bytes(data):
    def unique(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def validate_schema(kind, obj):
    revision = 2 if kind in ("attempt", "summary") else 1
    path = ROOT / f"schemas/majority3-auth-{kind}-v{revision}.schema.json"
    schema = read_json_bytes(path.read_bytes())
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(obj))
    # No input/exception repr: malformed evidence may contain sensitive material.
    require(not errors, f"invalid {kind} schema")


@dataclass(frozen=True)
class StudyConfig:
    """Canonical immutable JSON; to_dict returns a fresh detached value."""
    payload: str

    def __post_init__(self):
        require(type(self.payload) is str, "configuration must be JSON text")
        obj = read_json_bytes(self.payload)
        validate_schema("config", obj)
        expected = [dict(name=n, sigma=s, rho=r, common_offsets=list(c)) for n, s, r, c in CONDITIONS]
        require(obj["conditions"] == expected, "exactly the five approved conditions are required")
        for c in obj["conditions"]:
            for offset in c["common_offsets"]:
                noise.NoiseConfig(noise.MODEL_VERSION, 128, c["sigma"], c["rho"], offset)
        AuthConfig.from_dict(obj["authentication"])
        a = obj["allocation"]
        counts = (a["populations"], a["devices_per_population"], a["attempts_per_device_condition"])
        require(all(type(v) is int for v in counts), "allocation requires integer counts")
        require(counts[2] % 2 == 0, "paired order balancing requires an even attempt count")
        if obj["mode"] == "planned-formal":
            require(counts == (20, 6, 50), "formal allocation is fixed at 20 x 6 x 50")
        elif obj["mode"] == "nonformal":
            require(counts == (1, 1, 10), "separately authorized nonformal allocation is 100 policy attempts")
        else:
            require(counts[0] <= 2 and counts[1] <= 2 and counts[2] <= 2,
                    "unit-test allocation must remain a small deterministic fixture")
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


def study_seed(config, domain):
    require(domain in ("schedule", "population-bootstrap"), "unsupported study RNG domain")
    obj = config.to_dict()
    seed = obj["schedule_seed" if domain == "schedule" else "bootstrap_seed"]
    return int(object_digest(dict(experiment_id=VERSION, domain=domain,
                                  seed=seed, config_sha256=config.digest)), 16)


def noise_identity(config, population_id, device_id, condition, attempt_index):
    require(condition in {c[0] for c in CONDITIONS}, "unknown condition")
    alias = "independent_nominal" if condition == "common_control" else condition
    return noise.AttemptIdentity(config.to_dict()["master_seed"], population_id, device_id,
                                 VERSION + ":" + alias, attempt_index)


def trial_noise_config(trial):
    return noise.NoiseConfig(noise.MODEL_VERSION, 128, trial["sigma"], trial["rho"],
                             trial["common_offset"])


def compile_plan(config):
    """Deterministic shuffled paired blocks; no Device, enrollment, or reads."""
    obj = config.to_dict()
    a = obj["allocation"]
    blocks = []
    for p in range(a["populations"]):
        population = f"w7-p{p:03d}"
        for d in range(a["devices_per_population"]):
            device = f"{population}-d{d:02d}"
            for name, sigma, rho, offsets in CONDITIONS:
                for attempt in range(a["attempts_per_device_condition"]):
                    identity = noise_identity(config, population, device, name, attempt)
                    common = offsets[Random(noise.derive_seed(identity, noise.COMMON_MODE)).randrange(len(offsets))]
                    trial = dict(experiment_id=VERSION, config_sha256=config.digest,
                                 population_id=population, device_id=device, enrollment_id=f"{device}-enroll-v1",
                                 condition=name, attempt_index=attempt, sigma=sigma, rho=rho,
                                 common_offset=common, noise_identity=asdict(identity),
                                 session_seed_sha256=sha256(noise.canonical_seed_bytes(identity, noise.SESSION)).hexdigest(),
                                 reading_seed_sha256=[sha256(noise.canonical_seed_bytes(identity, noise.READING, i)).hexdigest()
                                                      for i in range(3)])
                    trial["trial_id"] = object_digest(trial)
                    order = list(POLICIES)
                    if attempt % 2:
                        order.reverse()
                    trial["policy_order"] = order
                    blocks.append(trial)
    Random(study_seed(config, "schedule")).shuffle(blocks)
    plan = dict(schema_version=VERSION + ":plan", experiment_id=VERSION,
                config_sha256=config.digest, blocks=blocks,
                counts=dict(matched_trials=len(blocks),
                            policy_attempts=sum(len(t["policy_order"]) for t in blocks),
                            expected_reads=sum(POLICIES[p].read_count for t in blocks for p in t["policy_order"])))
    plan["plan_sha256"] = object_digest(plan)
    return plan


def validate_plan(config, plan):
    validate_schema("plan", plan)
    require(plan == compile_plan(config), "trial plan differs from canonical complete schedule")


def scheduled_attempts(plan):
    ordinal = 0
    for trial in plan["blocks"]:
        for policy in trial["policy_order"]:
            yield trial, policy, ordinal
            ordinal += 1


def attempt_id(trial, policy):
    require(policy in POLICIES, "unknown policy")
    return object_digest(dict(trial_id=trial["trial_id"], policy=policy))


@dataclass(frozen=True, repr=False)
class DeviceEnrollment:
    population_id: str
    device: Device
    reference: tuple[int, ...]
    helper: HelperData
    credential: bytes = field(repr=False)
    verifier_record: CredentialVerifierRecord = field(repr=False)
    key_provider: InMemoryCredentialVerifierKeyProvider = field(repr=False)

    def public_record(self):
        return public_enrollment_record(self.population_id, self.device, self.reference, self.helper)


def enrollment_material(config, population_id, device_id):
    """Replayable simulation inputs. Credential truth is transient, never exported."""
    obj = config.to_dict()
    identity = noise.AttemptIdentity(obj["master_seed"], population_id, device_id,
                                     VERSION + ":enrollment-v1", 0)
    device = create_device(device_id, 128, obj["manufacturing_std"],
                           rng=Random(noise.derive_seed(identity, noise.MANUFACTURING)))
    reference = generate_response(device, noise.PAIRS, 100,
                                  ReadConditions(0, obj["enrollment_noise_std"]),
                                  rng=Random(noise.derive_seed(identity, noise.ENROLLMENT)))
    credential = Random(noise.derive_seed(identity, noise.CREDENTIAL)).getrandbits(32).to_bytes(4, "big")
    enrollment_id = f"{device_id}-enroll-v1"
    helper = enroll(reference, credential, enrollment_id=enrollment_id)
    return device, reference, helper, credential


def public_enrollment_record(population_id, device, reference, helper):
    return dict(population_id=population_id, device_id=device.device_id,
                enrollment_id=helper.enrollment_id, reference=list(reference),
                manufacturing_sha256=object_digest(device.manufacturing_variation),
                helper_sha256=object_digest(asdict(helper)))


def prepare_enrollment(config, population_id, device_id):
    """Sample immutable inputs once, outside timing. Verifier key is OS entropy.

    Synthetic credential is seeded solely for reproducibility; never export it
    or verifier tags/keys. Public config enables simulation replay, not secrecy.
    """
    device, reference, helper, credential = enrollment_material(config, population_id, device_id)
    provider = InMemoryCredentialVerifierKeyProvider("week7-local-verifier", secrets.token_bytes(32))
    record = CredentialVerifierRecord.enroll(device_id=device_id, enrollment_id=helper.enrollment_id,
             reconstruction_id=helper.config.version, verifier_key_id="week7-local-verifier",
             credential4=credential, key_provider=provider)
    return DeviceEnrollment(population_id, device, reference, helper, credential, record, provider)


def prepare_population(config, plan):
    identities = sorted({(b["population_id"], b["device_id"]) for b in plan["blocks"]})
    return {device: prepare_enrollment(config, population, device) for population, device in identities}
