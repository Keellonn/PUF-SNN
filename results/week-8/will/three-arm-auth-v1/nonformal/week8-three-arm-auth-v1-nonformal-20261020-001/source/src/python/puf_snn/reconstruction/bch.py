"""Exact full-length BCH(63,36,t=5) adapter; no PUF or enrollment state.

All bit vectors are immutable tuples of Python ints, highest degree first.
No shortening, erasures, byte padding, randomness, or decoding retries are used.
"""
from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import version
from numbers import Integral
from typing import Literal

import galois

Bits = tuple[int, ...]
DecoderStatus = Literal["decoded", "uncorrectable"]

@dataclass(frozen=True)
class BCHParameters:
    code_id: str = "binary-primitive-narrow-sense-bch-63-36-5-v1"
    n: int = 63
    k: int = 36
    t: int = 5
    designed_distance: int = 11
    field_order: int = 64
    primitive_polynomial: int = 0x43  # x^6 + x + 1
    primitive_element: int = 2       # x in the polynomial basis
    first_root_exponent: int = 1
    generator_polynomial: int = 0x86E8113
    systematic: bool = True
    bit_order: str = "msb-first"
    coefficient_order: str = "highest-degree-first"
    backend: str = "galois"
    backend_version: str = "0.4.11"

BCH_PARAMETERS = BCHParameters()

@dataclass(frozen=True)
class BCHDecodeResult:
    """A decoded codeword is a candidate, never proof of the enrolled message.

    reported_correction_count is the backend's count (0..5), or -1 for a
    declared failure. It is NOT the true number of errors relative to enrollment.
    Backend output on declared failure is deliberately not exposed as a candidate.
    """

    status: DecoderStatus
    reported_correction_count: int
    candidate_message: Bits | None
    corrected_codeword: Bits | None
    failure_reason: str | None

def validate_bits(value: Bits, length: int, name: str) -> None:
    """Reject coercions, nonbinary values and implicit shortening/padding."""
    if not isinstance(value, tuple) or len(value) != length:
        raise ValueError(f"{name} must be a tuple of exactly {length} bits")
    if any(type(bit) is not int or bit not in (0, 1) for bit in value):
        raise ValueError(f"{name} must contain only Python integer bits 0 or 1")

def _remainder(word: Bits) -> int:
    """Check a returned codeword independently of backend decode status."""
    value = 0
    for bit in word:
        value = (value << 1) | bit
    generator = BCH_PARAMETERS.generator_polynomial
    while value.bit_length() >= generator.bit_length():
        value ^= generator << (value.bit_length() - generator.bit_length())
    return value

def _backend_bits(vector, length: int) -> Bits:
    if vector.shape != (length,):
        raise RuntimeError("BCH backend returned an unexpected vector shape")
    result = tuple(vector.tolist())
    try:
        validate_bits(result, length, "backend output")
    except ValueError as error:
        raise RuntimeError("BCH backend returned nonbinary output") from error
    return result

@lru_cache(maxsize=1)
def _backend():
    """Cache only fixed code algebra, never a response, helper or credential."""
    p = BCH_PARAMETERS
    installed = version(p.backend)
    if installed != p.backend_version:
        raise RuntimeError(
            f"This codec requires {p.backend}=={p.backend_version}; found {installed}"
        )
    field = galois.GF(p.field_order, irreducible_poly=p.primitive_polynomial,
                      primitive_element=p.primitive_element)
    backend = galois.BCH(
        p.n, p.k, d=p.designed_distance, field=galois.GF2,
        extension_field=field, alpha=field(p.primitive_element),
        c=p.first_root_exponent, systematic=p.systematic,
    )
    actual = (backend.n, backend.k, backend.t, backend.d,
              int(field.irreducible_poly), int(backend.alpha), backend.c,
              int(backend.generator_poly), backend.is_systematic,
              backend.is_primitive, backend.is_narrow_sense)
    expected = (p.n, p.k, p.t, p.designed_distance, p.primitive_polynomial,
                p.primitive_element, p.first_root_exponent,
                p.generator_polynomial, True, True, True)
    if actual != expected:
        raise RuntimeError("BCH backend does not match the frozen codec parameters")
    return backend

class BCHCodec:
    """Stateless public adapter for the single approved code.

    Call initialize() to account for algebra setup separately from warm-up and
    reconstruction timing. The first encode/decode may also compile Numba code.
    Unexpected backend exceptions propagate; they are not noise-related failures.
    """

    __slots__ = ()
    parameters = BCH_PARAMETERS
    n = BCH_PARAMETERS.n
    k = BCH_PARAMETERS.k
    t = BCH_PARAMETERS.t

    def initialize(self) -> None:
        _backend()

    def encode(self, message: Bits) -> Bits:
        validate_bits(message, self.k, "message")
        word = _backend_bits(_backend().encode(galois.GF2(message)), self.n)
        if word[:self.k] != message or _remainder(word) != 0:
            raise RuntimeError("BCH backend violated systematic encoding")
        return word

    def decode(self, received: Bits) -> BCHDecodeResult:
        validate_bits(received, self.n, "received codeword")
        raw_word, raw_count = _backend().decode(
            galois.GF2(received), output="codeword", errors=True,
        )
        if isinstance(raw_count, bool) or not isinstance(raw_count, Integral):
            raise RuntimeError("BCH backend returned a noninteger correction count")
        count = int(raw_count)
        if count == -1:
            return BCHDecodeResult("uncorrectable", -1, None, None,
                                   "decoder_declared_failure")
        if not 0 <= count <= self.t:
            raise RuntimeError("BCH backend returned an impossible correction count")
        word = _backend_bits(raw_word, self.n)
        # This compares only received data with the returned candidate. There is
        # no enrollment oracle, and a wrong nearby codeword still passes.
        distance = sum(a != b for a, b in zip(received, word))
        if _remainder(word) != 0 or distance != count:
            raise RuntimeError("BCH backend returned an inconsistent decoded codeword")
        return BCHDecodeResult("decoded", count, word[:self.k], word, None)