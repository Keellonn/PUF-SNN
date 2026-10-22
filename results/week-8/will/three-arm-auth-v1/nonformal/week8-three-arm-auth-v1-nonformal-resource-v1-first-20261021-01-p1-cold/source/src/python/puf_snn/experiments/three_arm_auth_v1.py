"""Week 8 source comparison: planning only; formal execution remains disabled."""
from dataclasses import asdict, dataclass
from hashlib import sha256
from itertools import permutations
from pathlib import Path
from random import Random

from jsonschema import Draft202012Validator

from puf_snn.auth.stored_credential import InMemoryStoredCredentialProvider, StoredCredentialRecord
from . import correlated_noise_v1 as noise
from . import majority3_auth_v1 as previous
from .majority3_auth_v1 import (
    ROOT, CONDITIONS, canonical, object_digest, read_json_bytes, require,
    enrollment_material, prepare_enrollment, public_enrollment_record, trial_noise_config,
)

VERSION = "week8-three-arm-auth-v1"
EVIDENCE_VERSION = VERSION + ":evidence-v1"
STORED = "stored-provisioned-v1"
POLICIES = (*previous.POLICIES, STORED)
CONFIG_PATH = ROOT / "configs/three_arm_auth_v1.json"
EXTENSIONS = {"source_configuration", "stored_schedule", "execution_limits", "timing_methodology"}


def validate_schema(kind, obj):
    schema = read_json_bytes((ROOT / f"schemas/three-arm-auth-{kind}-v1.schema.json").read_bytes())
    Draft202012Validator.check_schema(schema)
    require(not list(Draft202012Validator(schema).iter_errors(obj)), f"invalid three-arm {kind} schema")


@dataclass(frozen=True)
class StudyConfig:
    payload: str

    def __post_init__(self):
        require(type(self.payload) is str, "configuration requires JSON text")
        obj = read_json_bytes(self.payload)
        validate_schema("config", obj)
        # Reuse the approved allocation, AuthConfig and five-condition checks.
        legacy = {k: v for k, v in obj.items() if k not in EXTENSIONS}
        legacy.update(schema_version=previous.VERSION+":config", experiment_id=previous.VERSION,
                      policies=list(previous.POLICIES))
        legacy["authentication"] = dict(obj["authentication"], warmup_iterations=20)
        previous.StudyConfig.from_dict(legacy)
        for field in ("master_seed", "schedule_seed", "bootstrap_seed"):
            require(type(obj[field]) is int, "seeds require integers")
        require(obj["authentication"]["warmup_iterations"] == 0,
                "cold-start contract requires zero configured warmup")
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


def compile_plan(config):
    obj = config.to_dict()
    a = obj["allocation"]
    orders = list(permutations(POLICIES))
    blocks = []
    for p in range(a["populations"]):
        population = f"w8-p{p:03d}"
        for d in range(a["devices_per_population"]):
            device = f"{population}-d{d:02d}"
            for c, (name, sigma, rho, offsets) in enumerate(CONDITIONS):
                for attempt in range(a["attempts_per_device_condition"]):
                    alias = "independent_nominal" if name == "common_control" else name
                    identity = noise.AttemptIdentity(obj["master_seed"], population, device,
                                                     VERSION+":"+alias, attempt)
                    common = offsets[Random(noise.derive_seed(identity, noise.COMMON_MODE)).randrange(len(offsets))]
                    trial = dict(experiment_id=VERSION, config_sha256=config.digest,
                        population_id=population, device_id=device, enrollment_id=device+"-enroll-v1",
                        condition=name, attempt_index=attempt, sigma=sigma, rho=rho, common_offset=common,
                        noise_identity=asdict(identity),
                        noise_shared_seed_sha256=sha256(noise.canonical_seed_bytes(identity, noise.SESSION)).hexdigest(),
                        reading_seed_sha256=[sha256(noise.canonical_seed_bytes(identity, noise.READING, i)).hexdigest()
                                             for i in range(3)])
                    trial["trial_id"] = object_digest(trial)
                    # Cycle all six orders. Counts differ by at most one per cell;
                    # condition/device offsets spread the incomplete final cycle.
                    trial["policy_order"] = list(orders[(attempt+2*c+d+p) % len(orders)])
                    blocks.append(trial)
    Random(int(object_digest(dict(version=VERSION, seed=obj["schedule_seed"], config=config.digest)), 16)).shuffle(blocks)
    plan = dict(schema_version=VERSION+":plan", experiment_id=VERSION, config_sha256=config.digest,
        blocks=blocks, counts=dict(matched_trials=len(blocks), arm_attempts=3*len(blocks),
            expected_reads=4*len(blocks), expected_runtime_decodes=2*len(blocks),
            stored_invocations=len(blocks), independent_populations=a["populations"],
            simulated_devices=a["populations"]*a["devices_per_population"]))
    plan["plan_sha256"] = object_digest(plan)
    return plan


def validate_plan(config, plan):
    validate_schema("plan", plan)
    require(plan == compile_plan(config), "plan differs from canonical three-arm schedule")


def scheduled_attempts(plan):
    index = 0
    for trial in plan["blocks"]:
        for policy in trial["policy_order"]:
            yield trial, policy, index
            index += 1


def attempt_id(trial, policy):
    require(policy in POLICIES, "unknown credential source")
    return object_digest(dict(trial_id=trial["trial_id"], policy=policy))


def prepare_population(config, plan):
    return {d: prepare_enrollment(config, p, d)
            for p, d in sorted({(t["population_id"], t["device_id"]) for t in plan["blocks"]})}


def stored_provider(enrollment):
    """Provision outside timing; same bound credential, no fallback or substitution."""
    return InMemoryStoredCredentialProvider([StoredCredentialRecord(
        enrollment.device.device_id, enrollment.helper.enrollment_id,
        enrollment.helper.config.version, enrollment.credential)])
