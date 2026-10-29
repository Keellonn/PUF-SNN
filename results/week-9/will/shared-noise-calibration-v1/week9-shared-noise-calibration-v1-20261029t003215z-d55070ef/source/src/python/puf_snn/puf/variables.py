from dataclasses import dataclass, fields
import json
import math
from pathlib import Path

def _nonnegative(name: str, value: float) -> None:
    """Reject invalid magnitudes before they can silently corrupt results."""
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0):
        raise ValueError(f"{name} must be a finite nonnegative number")

@dataclass(frozen=True)
class ReadConditions:
    """Inputs for one reading; noise samples themselves must be fresh per read.

    The environmental offset is a common additive oscillator offset. Such an
    offset alone cannot change pair ordering; differential sensitivity would
    require an explicit future model change. Enrollment has its own conditions.
    """

    environmental_offset: float
    measurement_noise_std: float

    def __post_init__(self) -> None:
        if (isinstance(self.environmental_offset, bool)
                or not isinstance(self.environmental_offset, (int, float))
                or not math.isfinite(self.environmental_offset)):
            raise ValueError("environmental_offset must be finite")
        _nonnegative("measurement_noise_std", self.measurement_noise_std)

@dataclass(frozen=True)
class ExperimentConfig:
    """Complete baseline inputs; no random state or simulated device state."""

    number_of_devices: int
    number_of_oscillators: int
    pairing_scheme: str
    nominal_frequency: float
    manufacturing_std: float
    aging_std: float
    repeated_reads: int
    random_seed: int
    reference_conditions: ReadConditions
    read_conditions: ReadConditions
    noise_sweep: tuple[float, ...]

    def __post_init__(self) -> None:
        for name, minimum in (("number_of_devices", 2),
                              ("number_of_oscillators", 2),
                              ("repeated_reads", 1), ("random_seed", 0)):
            value = getattr(self, name)
            if type(value) is not int or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}")
        if self.pairing_scheme not in ("adjacent", "all_pairs"):
            raise ValueError("pairing_scheme must be 'adjacent' or 'all_pairs'")
        if (self.pairing_scheme == "adjacent"
                and self.number_of_oscillators % 2):
            raise ValueError("adjacent pairing requires an even oscillator count")
        for name in ("nominal_frequency", "manufacturing_std", "aging_std"):
            _nonnegative(name, getattr(self, name))
        if self.nominal_frequency == 0:
            raise ValueError("nominal_frequency must be positive")
        # Aging is reserved, not silently treated as implemented science.
        if self.aging_std != 0:
            raise ValueError("aging_std must be zero until aging is implemented")
        for name in ("reference_conditions", "read_conditions"):
            if not isinstance(getattr(self, name), ReadConditions):
                raise ValueError(f"{name} must be ReadConditions")
        if not isinstance(self.noise_sweep, tuple) or not self.noise_sweep:
            raise ValueError("noise_sweep must be a nonempty tuple")
        for value in self.noise_sweep:
            _nonnegative("noise_sweep value", value)

def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """A duplicated setting is usually a typo, not an intentional override."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate configuration key: {key}")
        result[key] = value
    return result

def load_config(path: str | Path) -> ExperimentConfig:
    """Load strict JSON, rejecting missing/unknown fields and invalid values."""
    data = json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=_unique_keys)
    expected = {field.name for field in fields(ExperimentConfig)}
    if not isinstance(data, dict) or set(data) != expected:
        raise ValueError(f"Configuration must contain exactly: {sorted(expected)}")
    for name in ("reference_conditions", "read_conditions"):
        conditions = data[name]
        if (not isinstance(conditions, dict)
                or set(conditions) != {"environmental_offset",
                                       "measurement_noise_std"}):
            raise ValueError(f"Invalid fields in {name}")
        data[name] = ReadConditions(**conditions)
    if not isinstance(data["noise_sweep"], list):
        raise ValueError("noise_sweep must be a JSON array")
    data["noise_sweep"] = tuple(data["noise_sweep"])
    return ExperimentConfig(**data)