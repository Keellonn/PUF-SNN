"""Versioned response acquisition before the unchanged credential decoder.

No enrollment truth, retries, authentication decisions, or RNG creation live here.
The Week 6 experimental runner and its three/five-read utility remain untouched.
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from random import Random

from puf_snn.reconstruction.bch import Bits, validate_bits
from .device import Device
from .ro_puf import generate_pairs, generate_response
from .variables import ReadConditions, _nonnegative


@dataclass(frozen=True)
class AcquisitionConfig:
    """Local acquisition identity, separate from AuthConfig and wire versions."""

    config_version: str = "puf-snn-acquisition-v1"
    policy: str = "single-read-v1"
    read_count: int = 1

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if (type(self.config_version) is not str
                or self.config_version != "puf-snn-acquisition-v1"
                or type(self.policy) is not str or type(self.read_count) is not int
                or (self.policy, self.read_count) not in (
                    ("single-read-v1", 1), ("majority-3-v1", 3))):
            raise ValueError("unsupported acquisition configuration")

    @classmethod
    def from_dict(cls, obj: dict) -> "AcquisitionConfig":
        if type(obj) is not dict or set(obj) != set(cls.__dataclass_fields__):
            raise ValueError("acquisition configuration requires exact keys")
        return cls(**obj)

    @classmethod
    def load(cls, path: str | Path) -> "AcquisitionConfig":
        def unique_keys(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("duplicate acquisition configuration key")
                result[key] = value
            return result
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8"),
                                       object_pairs_hook=unique_keys))

    def to_dict(self) -> dict:
        self.validate()
        return asdict(self)


SINGLE_READ = AcquisitionConfig()
MAJORITY_3 = AcquisitionConfig(policy="majority-3-v1", read_count=3)


def majority_vote3(reads: tuple[Bits, ...]) -> Bits:
    """Exactly three 64-bit tuples; at least two ones elect a one at each bit.

    Same rule as reconstruction_alternatives.majority_vote for three inputs,
    restricted to this candidate without importing experimental dependencies.
    """
    if type(reads) is not tuple or len(reads) != 3:
        raise ValueError("majority-3 requires a tuple of exactly 3 readings")
    for reading in reads:
        validate_bits(reading, 64, "reading")
    return tuple(int(sum(reading[i] for reading in reads) >= 2) for i in range(64))


def acquire_response(read_response: Callable[[], Bits],
                     config: AcquisitionConfig = SINGLE_READ) -> Bits:
    """Call one bound source once or three times, then return one response.

    The trusted callback must perform a fresh read of the SAME persistent device
    on each invocation, advancing its existing caller-owned measurement RNG.
    SimulatedResponseReader supplies this binding for the current RO simulator.
    Malformed/failed reads stop immediately, with no replacement read or decode.
    """
    if type(config) is not AcquisitionConfig:
        raise ValueError("config must be an AcquisitionConfig")
    config.validate()
    if not callable(read_response):
        raise ValueError("read_response must be callable")
    reads = []
    for _ in range(config.read_count):
        reading = read_response()
        validate_bits(reading, 64, "reading")
        reads.append(reading)
    return reads[0] if config.read_count == 1 else majority_vote3(tuple(reads))


@dataclass(frozen=True)
class SimulatedResponseReader:
    """Bind 128 persistent ROs, adjacent pairs, and a continuing seeded RNG.

    Manufacturing and enrollment happen elsewhere. The caller supplies its
    measurement RNG, separately from manufacturing/enrollment streams; this
    adapter neither creates nor reseeds any randomness. Independent per-RO,
    per-read Gaussian noise (or no draws at zero noise) remains the simulator's
    contract. A callback cannot attest device identity across a trust boundary.
    """

    device: Device
    nominal_frequency: float
    conditions: ReadConditions
    rng: Random

    def __post_init__(self) -> None:
        if not isinstance(self.device, Device) or len(self.device.manufacturing_variation) != 128:
            raise ValueError("the acquisition profile requires a persistent 128-RO Device")
        if not isinstance(self.conditions, ReadConditions) or not isinstance(self.rng, Random):
            raise ValueError("ReadConditions and a caller-owned Random are required")
        _nonnegative("nominal_frequency", self.nominal_frequency)
        if self.nominal_frequency == 0:
            raise ValueError("nominal_frequency must be positive")

    def __call__(self) -> Bits:
        return generate_response(self.device, generate_pairs(128, "adjacent"),
                                 self.nominal_frequency, self.conditions, rng=self.rng)
