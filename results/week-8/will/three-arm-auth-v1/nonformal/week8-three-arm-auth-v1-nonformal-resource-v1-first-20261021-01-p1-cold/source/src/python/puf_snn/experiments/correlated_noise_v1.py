"""Indexed, variance-preserving RO noise for matched acquisition controls.

This module has no enrollment, credential, verifier, or experiment-runner state.
The caller supplies a persistent Device and explicit trial identities. The
authentication-facing callback returns only the existing 64-bit response tuple.
"""

from dataclasses import asdict, dataclass, field, replace
from hashlib import sha256
import json
import math
from random import Random

from puf_snn.puf.acquisition import AcquisitionConfig, SINGLE_READ
from puf_snn.puf.device import Device
from puf_snn.puf.ro_puf import calculate_frequencies, compare_oscillators, generate_pairs
from puf_snn.puf.variables import ReadConditions
from puf_snn.reconstruction.bch import Bits, validate_bits


MODEL_VERSION = "puf-snn-correlated-noise-v1"
NOMINAL_FREQUENCY = 100.0
OSCILLATOR_COUNT = 128
PAIRS = generate_pairs(OSCILLATOR_COUNT, "adjacent")
MANUFACTURING = "manufacturing"
ENROLLMENT = "enrollment-reference"
CREDENTIAL = "credential-generation"
SESSION = "session-correlated-oscillator"
READING = "independent-reading"
COMMON_MODE = "common-mode-offset"
RNG_DOMAINS = (MANUFACTURING, ENROLLMENT, CREDENTIAL, SESSION, READING, COMMON_MODE)


def _finite(name: str, value: float) -> None:
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{name} must be a finite number (not bool)")


def _identifier(name: str, value: str) -> None:
    if (type(value) is not str or not value or value != value.strip()
            or any(not char.isprintable() for char in value)):
        raise ValueError(f"{name} must be a nonempty printable string without edge whitespace")


def _reading_index(value: int) -> None:
    if type(value) is not int or value not in (0, 1, 2):
        raise ValueError("reading_index must be an integer in {0, 1, 2}")


@dataclass(frozen=True)
class NoiseConfig:
    """Complete v1 profile. The fixed 128-RO, 64-bit profile is intentional."""

    model_version: str
    oscillator_count: int
    sigma: float
    rho: float
    common_offset: float

    def __post_init__(self) -> None:
        if type(self.model_version) is not str or self.model_version != MODEL_VERSION:
            raise ValueError("unsupported model_version")
        if type(self.oscillator_count) is not int or self.oscillator_count != OSCILLATOR_COUNT:
            raise ValueError("oscillator_count must be exactly 128 for the v1 acquisition profile")
        for name in ("sigma", "rho", "common_offset"):
            _finite(name, getattr(self, name))
        if self.sigma < 0:
            raise ValueError("sigma must be nonnegative")
        if not 0 <= self.rho <= 1:
            raise ValueError("rho must be in [0, 1]")

    @classmethod
    def from_dict(cls, obj: dict) -> "NoiseConfig":
        if type(obj) is not dict or set(obj) != set(cls.__dataclass_fields__):
            raise ValueError("noise configuration requires exactly model_version, oscillator_count, "
                             "sigma, rho, common_offset")
        return cls(**obj)

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def shared_std(self) -> float:
        return self.sigma * math.sqrt(self.rho)

    @property
    def independent_std(self) -> float:
        return self.sigma * math.sqrt(1 - self.rho)


def common_mode_control(nominal: NoiseConfig, common_offset: float) -> NoiseConfig:
    """Change ONLY C; use the same AttemptIdentity to explicitly alias noise.

    The planner may label the control differently in its evidence, but MUST
    retain the nominal noise_domain_id (and all other seed identity fields).
    """
    if type(nominal) is not NoiseConfig:
        raise ValueError("nominal must be a NoiseConfig")
    return replace(nominal, common_offset=common_offset)


@dataclass(frozen=True)
class AttemptIdentity:
    """Canonical noise identity, independent of policy and execution position.

    noise_domain_id is a condition ID or an explicitly shared noise-domain ID.
    For future enrollment/manufacturing/credential use, the planner must supply
    fixed, designated identities instead of reusing a changing measurement trial.
    No credential or key material belongs in any field here.
    """

    master_seed: int
    population_id: str
    device_id: str
    noise_domain_id: str
    attempt_id: int
    model_version: str = MODEL_VERSION

    def __post_init__(self) -> None:
        if type(self.model_version) is not str or self.model_version != MODEL_VERSION:
            raise ValueError("unsupported model_version")
        for name in ("master_seed", "attempt_id"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer (not bool)")
        for name in ("population_id", "device_id", "noise_domain_id"):
            _identifier(name, getattr(self, name))


def canonical_seed_bytes(identity: AttemptIdentity, domain: str,
                         reading_index: int | None = None) -> bytes:
    """Frozen encoding: sorted compact ASCII-escaped JSON, UTF-8, no newline.

    Exactly the identity fields plus 'domain'; add 'reading_index' ONLY for
    independent-reading. No floats, config magnitudes, policy, Python hash(),
    timestamps, enrollment secrets, or stream-consumption state enter the seed.
    Strings are preserved verbatim (no Unicode normalization).
    """
    if type(identity) is not AttemptIdentity:
        raise ValueError("identity must be an AttemptIdentity")
    if type(domain) is not str or domain not in RNG_DOMAINS:
        raise ValueError("unsupported RNG domain")
    if domain == READING:
        _reading_index(reading_index)
    elif reading_index is not None:
        raise ValueError("reading_index is only valid for the independent-reading domain")
    obj = asdict(identity)
    obj["domain"] = domain
    if domain == READING:
        obj["reading_index"] = reading_index
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def derive_seed(identity: AttemptIdentity, domain: str,
                reading_index: int | None = None) -> int:
    """Use all 32 SHA-256 digest bytes as an unsigned big-endian Python int."""
    return int.from_bytes(sha256(canonical_seed_bytes(identity, domain, reading_index)).digest(),
                          byteorder="big", signed=False)


@dataclass(frozen=True)
class SharedDisturbance:
    """One standard-normal Z per oscillator, frozen for one attempt."""

    identity: AttemptIdentity
    standard_normals: tuple[float, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.identity) is not AttemptIdentity:
            raise ValueError("identity must be an AttemptIdentity")
        if type(self.standard_normals) is not tuple or len(self.standard_normals) != OSCILLATOR_COUNT:
            raise ValueError("standard_normals must be a tuple of 128 finite numbers")
        for value in self.standard_normals:
            _finite("standard_normals entry", value)


def generate_shared_disturbance(identity: AttemptIdentity) -> SharedDisturbance:
    rng = Random(derive_seed(identity, SESSION))
    return SharedDisturbance(identity, tuple(rng.gauss(0.0, 1.0)
                                           for _ in range(OSCILLATOR_COUNT)))


class CommonModeNumericalError(ValueError):
    """Finite-precision addition changed a comparison; not a physical effect."""


class _MeasurementRandom(Random):
    """Record actual scaled draws made by the existing frequency calculator."""

    def __init__(self, seed: int):
        super().__init__(seed)
        self.samples: list[float] = []

    def gauss(self, mu: float, sigma: float) -> float:
        sample = super().gauss(mu, sigma)
        self.samples.append(sample)
        return sample


@dataclass(frozen=True)
class Measurement:
    """Simulation diagnostics, never the authentication callback's return type.

    shared_noise and independent_noise are already scaled in frequency units.
    Frequencies include C. Diagnostics contain no enrollment response/credential.
    """

    reading_index: int
    shared_noise: tuple[float, ...]
    independent_noise: tuple[float, ...]
    frequencies: tuple[float, ...]

    @property
    def response(self) -> Bits:
        return compare_oscillators(self.frequencies, PAIRS)


def _validate_binding(device: Device, config: NoiseConfig, identity: AttemptIdentity) -> None:
    if type(config) is not NoiseConfig or type(identity) is not AttemptIdentity:
        raise ValueError("NoiseConfig and AttemptIdentity are required")
    if type(device) is not Device or len(device.manufacturing_variation) != config.oscillator_count:
        raise ValueError("a persistent 128-RO Device is required")
    if device.device_id != identity.device_id:
        raise ValueError("device_id must match the supplied Device")
    if device.aging_state is not None and any(value != 0 for value in device.aging_state):
        raise ValueError("nonzero aging_state is unsupported")


def measure_indexed(device: Device, config: NoiseConfig, identity: AttemptIdentity,
                    shared: SharedDisturbance, reading_index: int) -> Measurement:
    """Make an actual indexed measurement, without mutation or response caching.

    Reuse the legacy oscillator loop and Random.gauss order for independent
    noise, at sigma*sqrt(1-rho). Then add sigma*sqrt(rho)*Z and finally C. These
    additions are algebraically the approved model; zero additions are skipped
    for exact rho=0, C=0 legacy compatibility. No transient Device is constructed.
    """
    _validate_binding(device, config, identity)
    _reading_index(reading_index)
    if type(shared) is not SharedDisturbance or shared.identity != identity:
        raise ValueError("shared disturbance must belong to the same attempt identity")
    rng = _MeasurementRandom(derive_seed(identity, READING, reading_index))
    base = calculate_frequencies(device, NOMINAL_FREQUENCY,
                                 ReadConditions(0.0, config.independent_std), rng=rng)
    independent_noise = tuple(rng.samples) if rng.samples else (0.0,) * OSCILLATOR_COUNT
    shared_noise = tuple(config.shared_std * z for z in shared.standard_normals)
    centered = (tuple(f + z for f, z in zip(base, shared_noise))
                if config.shared_std else base)
    centered_response = compare_oscillators(centered, PAIRS)  # Also rejects nonfinite sums.
    frequencies = (tuple(f + config.common_offset for f in centered)
                   if config.common_offset else centered)
    if compare_oscillators(frequencies, PAIRS) != centered_response:
        raise CommonModeNumericalError(
            "common_offset changed response bits through floating-point rounding; "
            "this measurement is invalid, not a physical common-mode effect")
    return Measurement(reading_index, shared_noise, independent_noise, frequencies)


@dataclass(frozen=True)
class CorrelatedResponseReader:
    """One sequential, trusted acquisition from a fixed Device and attempt.

    The acquisition profile limits calls to one or three; it never enters RNG
    derivation. No arguments are accepted by the callback. A failed/malformed
    measurement permanently closes this reader. Counts include failed simulator
    invocations. Use separate readers with identical identities for matched
    policies. This local adapter is not a thread-safe source or remote attestation.
    """

    device: Device = field(repr=False)
    config: NoiseConfig
    identity: AttemptIdentity
    acquisition: AcquisitionConfig = SINGLE_READ
    shared: SharedDisturbance = field(init=False, repr=False)
    _measurement_count: int = field(init=False, default=0, repr=False, compare=False)
    _failed: bool = field(init=False, default=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _validate_binding(self.device, self.config, self.identity)
        if type(self.acquisition) is not AcquisitionConfig:
            raise ValueError("acquisition must be an AcquisitionConfig")
        self.acquisition.validate()
        object.__setattr__(self, "shared", generate_shared_disturbance(self.identity))

    @property
    def measurement_count(self) -> int:
        return self._measurement_count

    def __call__(self) -> Bits:
        if self._failed:
            raise RuntimeError("reader failed; no retries are permitted")
        if self._measurement_count >= self.acquisition.read_count:
            raise RuntimeError("acquisition reading limit exhausted")
        index = self._measurement_count
        object.__setattr__(self, "_measurement_count", index + 1)
        # Latch before measuring: exceptions (including malformed output) never
        # permit replacement reads, and reentrant calls cannot start a new read.
        object.__setattr__(self, "_failed", True)
        response = measure_indexed(self.device, self.config, self.identity,
                                   self.shared, index).response
        validate_bits(response, 64, "reading")
        object.__setattr__(self, "_failed", False)
        return response
