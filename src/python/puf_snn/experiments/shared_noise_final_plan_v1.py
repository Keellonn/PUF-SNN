"""Planning contract candidate v1; NOT an adopted or executable study contract.

Contract (also expressed by the closed JSON schemas):
* canonical: sorted compact ASCII-escaped JSON, UTF-8, no newline, no NaN/Inf;
  strings are verbatim. Config sigma/rho and the three physical magnitudes are
  normalized to binary64 floats; all other numeric types follow the schema.
* config_sha256: SHA-256 of the entire validated, normalized config. No digest
  field is permitted in config. Raw file hashes are separate, not ID inputs.
* trial_id: SHA-256 of every block field EXCEPT trial_id, policy_order,
  block_index and attempts. This includes schema/phase/config, device/enrollment,
  condition/t, sigma/rho/C, full noise identity, Z/all E seed digests, offset
  seed digest and linked operating trial ID (null for non-common blocks).
* policy_attempt_id: SHA-256 of exactly {trial_id, policy}. Schedule position,
  record schema version, reading references and phase are validated bindings,
  not additional attempt-ID inputs. Enrollment records contain only planned
  identities and seed digests, never manufactured offsets or credential bytes.
* plan_sha256: SHA-256 of the entire plan except plan_sha256, including ordered
  blocks, attempts, enrollment identities, counts and recorded Python version.
  Block policy order/indices/attempts are excluded from trial hashes to prevent
  circular references; they ARE covered by the plan digest. The common link
  points only to the already hashed operating block, which has a null link.

Simulation encoding/derivation is reused unchanged from correlated_noise_v1.
Only offset-sign randrange and schedule shuffle consume RNG here. No Gaussian,
measurement, credential, enrollment construction, protocol or bootstrap draws
are made. Python/RNG version is recorded for independent schedule replay; exact
interpreter acceptance and this schema/hash recipe still require review/freeze.
There is deliberately no runner, CLI execution action, or output writer.
"""

from dataclasses import asdict, dataclass
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import platform
from random import Random

from jsonschema import Draft202012Validator

from . import correlated_noise_v1 as noise

VERSION = "week9-shared-noise-final-v1"
CONTRACT_VERSION = "shared-noise-final-planning-v1"
STATUS = "implementation-candidate-pending-independent-review"
ROOT = Path(__file__).resolve().parents[4]
CONFIG_PATH = ROOT / "configs/shared_noise_final_v1.json"
POLICIES = ("single-read-v1", "majority-3-v1", "stored-provisioned-v1")
POLICY_ORDERS = (
    (POLICIES[0], POLICIES[1], POLICIES[2]),
    (POLICIES[0], POLICIES[2], POLICIES[1]),
    (POLICIES[1], POLICIES[0], POLICIES[2]),
    (POLICIES[1], POLICIES[2], POLICIES[0]),
    (POLICIES[2], POLICIES[0], POLICIES[1]),
    (POLICIES[2], POLICIES[1], POLICIES[0]),
)
CONDITIONS = (
    ("op_rho000", .15, .0, "op:r000"),
    ("op_rho050", .15, .5, "op:r050"),
    ("op_rho090", .15, .9, "op:r090"),
    ("op_rho100", .15, 1., "op:r100"),
    ("nominal_s010", .10, .0, "nominal:s010:r000"),
    ("common_mode_op_rho000", .15, .0, "op:r000"),
)
TRIAL_EXCLUSIONS = frozenset(("trial_id", "policy_order", "block_index", "attempts"))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def object_digest(obj):
    return sha256(canonical(obj)).hexdigest()


def read_json(data):
    def unique(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


@lru_cache(maxsize=4)
def _validator(schema_bytes):
    schema = read_json(schema_bytes)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_schema(kind, obj):
    require(kind in ("config", "plan", "attempt"), "unsupported planning schema")
    path = ROOT / f"schemas/shared-noise-final-{kind}-v1.schema.json"
    error = next(_validator(path.read_bytes()).iter_errors(obj), None)
    require(error is None, f"invalid final planning {kind} schema")


@dataclass(frozen=True)
class StudyConfig:
    """Validated immutable planning config; no fixture or execution mode."""

    payload: str

    def __post_init__(self):
        require(type(self.payload) is str, "configuration requires JSON text")
        obj = read_json(self.payload)
        validate_schema("config", obj)
        # JSON Schema's integer type also accepts 20.0. Identity integers must
        # use actual Python ints, and bool must never stand in for a number.
        def check_types(value, template):
            if isinstance(template, dict):
                for key in template:
                    check_types(value[key], template[key])
            elif isinstance(template, list):
                for actual, expected in zip(value, template):
                    check_types(actual, expected)
            elif type(template) is int:
                require(type(value) is int, "integer configuration field required")
            elif type(template) is float:
                require(type(value) in (int, float), "numeric configuration field required")
        # Schema const is the versioned engineering baseline, independent of
        # the editable config file. Normalize only documented float positions.
        template = read_json((ROOT / "schemas/shared-noise-final-config-v1.schema.json").read_bytes())["const"]
        check_types(obj, template)
        for field in ("nominal_frequency", "manufacturing_std", "enrollment_noise_std"):
            obj[field] = float(obj[field])
        for condition in obj["conditions"]:
            condition["sigma"] = float(condition["sigma"])
            condition["rho"] = float(condition["rho"])
        object.__setattr__(self, "payload", canonical(obj).decode("ascii"))

    @classmethod
    def from_dict(cls, obj):
        return cls(canonical(obj).decode("ascii"))

    @classmethod
    def load(cls, path=CONFIG_PATH):
        return cls(Path(path).read_text(encoding="utf-8"))

    def to_dict(self):
        return read_json(self.payload)

    @property
    def digest(self):
        return sha256(self.payload.encode("ascii")).hexdigest()


def study_seed(config, domain):
    field = {"schedule": "schedule_seed", "device-bootstrap": "bootstrap_seed",
             "group-bootstrap-sensitivity": "group_sensitivity_seed"}.get(domain)
    require(field is not None, "unsupported final RNG domain")
    return int(object_digest(dict(experiment_id=VERSION, domain=domain,
        seed=config.to_dict()[field], config_sha256=config.digest)), 16)


def seed_digest(identity, domain, reading_index=None):
    return sha256(noise.canonical_seed_bytes(identity, domain, reading_index)).hexdigest()


def trial_id(block):
    return object_digest({k: v for k, v in block.items() if k not in TRIAL_EXCLUSIONS})


def attempt_id(block, policy):
    require(policy in POLICIES, "unknown final policy")
    return object_digest(dict(trial_id=block["trial_id"], policy=policy))


def _identity(population, device, domain, t=0):
    return noise.AttemptIdentity(2026102811, population, device, VERSION + ":" + domain, t)


def _enrollment(population, device):
    identity = _identity(population, device, "enrollment-v1")
    return dict(schema_version=VERSION + ":planned-enrollment", experiment_id=VERSION,
        population_id=population, device_id=device, enrollment_id=device + "-enroll-v1",
        noise_identity=asdict(identity),
        manufacturing_seed_sha256=seed_digest(identity, noise.MANUFACTURING),
        reference_seed_sha256=seed_digest(identity, noise.ENROLLMENT),
        credential_seed_sha256=seed_digest(identity, noise.CREDENTIAL))


def _attempt(block, policy, index):
    readings = {POLICIES[0]: [0], POLICIES[1]: [0, 1, 2], POLICIES[2]: []}[policy]
    return dict(schema_version=VERSION + ":planned-attempt", experiment_id=VERSION,
        condition=block["condition"], trial_id=block["trial_id"], policy=policy,
        policy_attempt_id=attempt_id(block, policy), execution_index=index,
        reading_indices=readings,
        noise_shared_seed_sha256=block["noise_shared_seed_sha256"] if readings else None,
        reading_seed_sha256=[block["reading_seed_sha256"][r] for r in readings])


def compile_plan(config):
    """Return the full in-memory schedule; no scientific material is constructed."""
    require(type(config) is StudyConfig, "validated final StudyConfig required")
    config_digest = config.digest
    blocks, enrollments = [], []
    for p in range(20):
        population = f"w9f-p{p:03d}"
        for d in range(6):
            device = f"{population}-d{d:02d}"
            enrollments.append(_enrollment(population, device))
            operating = {}
            for c, (condition, sigma, rho, domain) in enumerate(CONDITIONS):
                for t in range(50):
                    identity = _identity(population, device, domain, t)
                    common = condition == "common_mode_op_rho000"
                    offset = (-1, 1)[Random(noise.derive_seed(identity, noise.COMMON_MODE)).randrange(2)] if common else 0
                    block = dict(schema_version=VERSION + ":planned-block", experiment_id=VERSION,
                        config_sha256=config_digest, population_id=population, device_id=device,
                        enrollment_id=device + "-enroll-v1", condition=condition, attempt_index=t,
                        sigma=sigma, rho=rho, common_offset=offset,
                        noise_identity=asdict(identity),
                        noise_shared_seed_sha256=seed_digest(identity, noise.SESSION),
                        reading_seed_sha256=[seed_digest(identity, noise.READING, r) for r in range(3)],
                        common_offset_seed_sha256=seed_digest(identity, noise.COMMON_MODE) if common else None,
                        linked_operating_trial_id=operating[t] if common else None)
                    block["trial_id"] = trial_id(block)
                    if c == 0:
                        operating[t] = block["trial_id"]
                    block["policy_order"] = list(POLICY_ORDERS[(t+c+d+p) % 6])
                    blocks.append(block)
    Random(study_seed(config, "schedule")).shuffle(blocks)
    for index, block in enumerate(blocks):
        block["block_index"] = index
        block["attempts"] = [_attempt(block, policy, 3*index+i)
                             for i, policy in enumerate(block["policy_order"])]
    plan = dict(schema_version=VERSION + ":plan", contract_version=CONTRACT_VERSION,
        contract_status=STATUS, experiment_id=VERSION, mode="planning-only",
        scientific_execution_authorized=False, config_sha256=config_digest,
        rng=dict(implementation=platform.python_implementation(), python_version=platform.python_version(),
            generator="random.Random/MT19937", schedule_algorithm="Random.shuffle",
            offset_algorithm="Random.randrange(2)"),
        enrollments=enrollments, blocks=blocks,
        counts=dict(groups=20, simulated_devices=120, planned_enrollments=120,
            matched_trials=36000, arm_attempts=108000,
            blocks_per_condition=6000, attempts_per_condition=18000, attempts_per_policy=36000))
    plan["plan_sha256"] = object_digest(plan)
    return plan


def validate_plan(config, plan):
    """Fail closed on shape, duplicate IDs, pairing, aliases, seeds and schedule.

    Regeneration is metadata-only. Canonical-byte equality also rejects alternate
    numeric encodings (e.g. an integer index replaced by 0.0) and stale hashes.
    """
    require(type(plan) is dict and plan.get("schema_version") == VERSION + ":plan",
            "unsupported final plan version")
    expected = compile_plan(config)
    require(plan.keys() == expected.keys(), "incorrect final plan fields")
    # Compare metadata before traversing large collections. Comparing records
    # individually avoids allocating two complete serialized plan graphs.
    for key in expected:
        if key not in ("blocks", "enrollments"):
            require(canonical(plan[key]) == canonical(expected[key]), "final plan metadata mismatch")
    for key in ("enrollments", "blocks"):
        require(type(plan[key]) is list and len(plan[key]) == len(expected[key]), "incomplete final plan")
        for actual, wanted in zip(plan[key], expected[key]):
            require(canonical(actual) == canonical(wanted), "plan differs from canonical final schedule")
    # Exact regeneration above enforces uniqueness and all relational contracts,
    # including alias links. Schema validation is additional structural defense.
    validate_schema("plan", plan)


def scheduled_attempts(plan):
    """Yield planned block/policy/global index, compatible with planner interfaces."""
    for block in plan["blocks"]:
        for attempt in block["attempts"]:
            yield block, attempt["policy"], attempt["execution_index"]
