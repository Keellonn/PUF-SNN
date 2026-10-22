from dataclasses import dataclass
import math
from random import Random
from .variables import _nonnegative

@dataclass(frozen=True)
class Device:
    """One manufactured device with immutable per-oscillator frequency offsets.
    Tuples prevent accidental in-place changes between readings. Aging is an
    optional future per-oscillator state; None means aging is disabled.
    """

    device_id: str
    manufacturing_variation: tuple[float, ...]
    aging_state: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.device_id, str) or not self.device_id.strip():
            raise ValueError("device_id must be a nonempty string")
        offsets = self.manufacturing_variation
        if not isinstance(offsets, tuple) or len(offsets) < 2:
            raise ValueError(
                "manufacturing_variation must be a tuple of >= 2 offsets"
            )
        for name, values in (("manufacturing_variation", offsets),
                             ("aging_state", self.aging_state)):
            if values is None:
                continue
            if not isinstance(values, tuple) or len(values) != len(offsets):
                raise ValueError(f"{name} must have one offset per oscillator")
            if any(isinstance(value, bool)
                   or not isinstance(value, (int, float))
                   or not math.isfinite(value) for value in values):
                raise ValueError(f"{name} must contain only finite numbers")

def create_device(
    device_id: str,
    number_of_oscillators: int,
    manufacturing_std: float,
    *,
    rng: Random,
) -> Device:
    """Sample manufacturing offsets ONCE using the supplied manufacturing RNG.

    Offsets are independent zero-mean Gaussian samples in abstract frequency
    units. This is an uncalibrated Week 2 assumption, not measured hardware.
    Zero spread creates identical zero offsets and consumes no random draws.
    Reads receive the resulting Device, never this factory's RNG.
    """
    if not isinstance(device_id, str) or not device_id.strip():
        raise ValueError("device_id must be a nonempty string")
    if type(number_of_oscillators) is not int or number_of_oscillators < 2:
        raise ValueError("number_of_oscillators must be an integer >= 2")
    _nonnegative("manufacturing_std", manufacturing_std)
    if not isinstance(rng, Random):
        raise ValueError("rng must be a random.Random instance")

    # Sample fabrication mismatch only here. The immutable tuple is reused
    # throughout the device lifetime, preserving its simulated identity.
    if manufacturing_std == 0:
        offsets = (0.0,) * number_of_oscillators
    else:
        offsets = tuple(rng.gauss(0.0, manufacturing_std)
                        for _ in range(number_of_oscillators))
    return Device(device_id, offsets)