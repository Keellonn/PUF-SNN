from collections.abc import Sequence
from itertools import combinations

def _validate_response(response: Sequence[int]) -> None:
    """Reject empty, nonbinary, or multidimensional responses."""
    if not isinstance(response, Sequence) or not response:
        raise ValueError("response must be a nonempty binary sequence")
    if any(not isinstance(bit, int) or bit not in (0, 1) for bit in response):
        raise ValueError("response must contain only binary integers")

def hamming_distance(reference: Sequence[int], reading: Sequence[int]) -> int:
    """Count differing bits (0 to N), within/across equal-length responses."""
    _validate_response(reference)
    _validate_response(reading)
    if len(reference) != len(reading):
        raise ValueError("responses must have equal lengths")
    return sum(first != second for first, second in zip(reference, reading))

def normalized_hamming_distance(
    reference: Sequence[int], reading: Sequence[int],
) -> float:
    """Differing bits / N in [0, 1], within or across device responses."""
    return hamming_distance(reference, reading) / len(reference)

def raw_ber(reference: Sequence[int], reading: Sequence[int]) -> float:
    """Differing bits / N in [0, 1] for a SAME-device binary reference/read."""
    return normalized_hamming_distance(reference, reading)

def reliability(reference: Sequence[int], reading: Sequence[int]) -> float:
    """Return 1 - BER in [0, 1] for one SAME-device binary reference/read."""
    return 1.0 - raw_ber(reference, reading)

def pairwise_uniqueness(
    reference_responses: Sequence[Sequence[int]],
) -> list[tuple[int, int, float]]:
    """Return (i, j, normalized distance) for distinct-device pairs i < j.

    Supply one nonempty binary reference per device, at least two devices,
    equal response lengths and a shared oscillator-pair order. Scale: [0, 1].
    Identical bit patterns from distinct devices are valid and retained.
    """
    if (not isinstance(reference_responses, Sequence)
            or len(reference_responses) < 2):
        raise ValueError("uniqueness requires at least two device references")
    for response in reference_responses:
        _validate_response(response)
        if len(response) != len(reference_responses[0]):
            raise ValueError("responses must have equal lengths")
    return [
        (first, second, normalized_hamming_distance(
            reference_responses[first], reference_responses[second]
        ))
        for first, second in combinations(range(len(reference_responses)), 2)
    ]

def uniqueness(reference_responses: Sequence[Sequence[int]]) -> float:
    """Mean inter-device distance in [0, 1]; one reference per device."""
    pairs = pairwise_uniqueness(reference_responses)
    return sum(distance for _, _, distance in pairs) / len(pairs)

def uniformity(response: Sequence[int]) -> float:
    """Fraction of ones in one device's nonempty binary response, in [0, 1]."""
    _validate_response(response)
    return sum(response) / len(response)