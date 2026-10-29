import math
from random import Random
from .device import Device
from .variables import ReadConditions, _nonnegative

OscillatorPairs = tuple[tuple[int, int], ...]
Response = tuple[int, ...]

def generate_pairs(number_of_oscillators: int, scheme: str) -> OscillatorPairs:
    """Return ordered pairs, shared across devices and enrollment/read phases.

    adjacent: (0, 1), (2, 3), ...; requires an even oscillator count.
    all_pairs: every i < j, in lexicographic order. Length is len(pairs).
    Adjacent pairs never reuse oscillators. All-pairs comparisons reuse them,
    so the resulting bits are correlated, not independent entropy claims.
    """
    if type(number_of_oscillators) is not int or number_of_oscillators < 2:
        raise ValueError("number_of_oscillators must be an integer >= 2")
    if scheme == "adjacent":
        if number_of_oscillators % 2:
            raise ValueError(
                "adjacent pairing requires an even oscillator count"
            )
        return tuple((index, index + 1)
                     for index in range(0, number_of_oscillators, 2))
    if scheme == "all_pairs":
        return tuple((first, second)
                     for first in range(number_of_oscillators)
                     for second in range(first + 1, number_of_oscillators))
    raise ValueError("scheme must be 'adjacent' or 'all_pairs'")

def _validate_pairs(pairs: OscillatorPairs, oscillator_count: int) -> None:
    """Reject malformed comparisons before indexing or consuming read noise."""
    if not isinstance(pairs, tuple) or not pairs:
        raise ValueError("pairs must be a nonempty tuple of index pairs")
    for pair in pairs:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise ValueError("each pair must be a tuple of two indices")
        if any(type(index) is not int or not 0 <= index < oscillator_count
               for index in pair):
            raise ValueError(
                "pair indices must be integers in oscillator range"
            )
        if pair[0] == pair[1]:
            raise ValueError("an oscillator cannot be compared with itself")

def calculate_frequencies(
    device: Device,
    nominal_frequency: float,
    conditions: ReadConditions,
    *,
    rng: Random,
) -> tuple[float, ...]:
    """Return one frequency per oscillator without modifying persistent state.

    Frequency = nominal + manufacturing + environment + aging + read noise.
    Environment is a controlled common additive offset; it cannot change pair
    ordering mathematically. Noise is independent zero-mean Gaussian per RO
    and read. Zero noise consumes no RNG draws. Aging remains disabled: None
    or an all-zero tuple is accepted, and nonzero state is rejected explicitly.

    Gaussian tails are unbounded; finite negative values remain abstract model
    values (not physical oscillation rates). Clipping would bias comparisons.
    """
    if not isinstance(device, Device):
        raise ValueError("device must be a Device")
    _nonnegative("nominal_frequency", nominal_frequency)
    if nominal_frequency == 0:
        raise ValueError("nominal_frequency must be positive")
    if not isinstance(conditions, ReadConditions):
        raise ValueError("conditions must be ReadConditions")
    if not isinstance(rng, Random):
        raise ValueError("rng must be a random.Random instance")

    oscillator_count = len(device.manufacturing_variation)
    aging_offsets = device.aging_state
    if aging_offsets is None:
        aging_offsets = (0.0,) * oscillator_count
    if any(offset != 0 for offset in aging_offsets):
        raise ValueError(
            "nonzero aging_state is unsupported until aging is implemented"
        )

    frequencies = []
    for manufacturing_offset, aging_offset in zip(
        device.manufacturing_variation, aging_offsets
    ):
        # Only short-term measurement noise is sampled during a read.
        # Manufacturing, environment, and aging are never resampled here.
        measurement_noise = 0.0
        if conditions.measurement_noise_std > 0:
            measurement_noise = rng.gauss(
                0.0, conditions.measurement_noise_std
            )
        frequency = (
            nominal_frequency
            + manufacturing_offset
            + conditions.environmental_offset
            + aging_offset
            + measurement_noise
        )
        if not math.isfinite(frequency):
            raise ValueError(
                "modeled frequency is nonfinite; reduce input magnitudes"
            )
        frequencies.append(frequency)
    return tuple(frequencies)

def compare_oscillators(
    frequencies: tuple[float, ...], pairs: OscillatorPairs,
) -> Response:
    """Return int(a > b) for each ordered pair; equal frequencies produce zero.

    Custom pairs may reuse oscillators, repeat comparisons, and reverse order;
    they are evaluated exactly as supplied. This operation uses no RNG.
    """
    if not isinstance(frequencies, tuple) or len(frequencies) < 2:
        raise ValueError("frequencies must be a tuple of >= 2 finite numbers")
    if any(isinstance(value, bool) or not isinstance(value, (int, float))
           or not math.isfinite(value) for value in frequencies):
        raise ValueError("frequencies must contain only finite numbers")
    _validate_pairs(pairs, len(frequencies))
    return tuple(int(frequencies[first] > frequencies[second])
                 for first, second in pairs)

def generate_response(
    device: Device,
    pairs: OscillatorPairs,
    nominal_frequency: float,
    conditions: ReadConditions,
    *,
    rng: Random,
) -> Response:
    """Read one binary tuple using the caller's continuing noise RNG.

    For enrollment, pass configured reference conditions and a separate
    enrollment RNG, then retain the returned tuple as the reference. Reference
    noise is honored, including when nonzero; there is no hidden averaging.
    """
    if not isinstance(device, Device):
        raise ValueError("device must be a Device")
    _validate_pairs(pairs, len(device.manufacturing_variation))
    frequencies = calculate_frequencies(
        device, nominal_frequency, conditions, rng=rng
    )
    return compare_oscillators(frequencies, pairs)