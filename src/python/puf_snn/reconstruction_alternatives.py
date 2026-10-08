"""Isolated research BCH(63,30,t=6) and temporal voting; no authentication state."""
from dataclasses import dataclass, fields
from functools import lru_cache
from importlib.metadata import version
from numbers import Integral

import galois

from .reconstruction.bch import Bits, BCHDecodeResult, validate_bits
from .reconstruction.credential import ReconstructionResult


@dataclass(frozen=True)
class ExperimentalConfig:
    version: str = "w6-recon-bch63-30-v1"
    n: int = 63
    k: int = 30
    t: int = 6
    designed_distance: int = 13
    field_order: int = 64
    primitive_polynomial: int = 0x43
    primitive_element: int = 2
    first_root_exponent: int = 1
    generator_polynomial: int = 0x37CD0EB67
    systematic: bool = True
    response_length: int = 64
    response_indices: tuple = tuple(range(63))
    credential_bytes: int = 4
    credential_bits: int = 30
    representation: str = "big-endian-four-bytes-top-two-bits-zero"
    bit_order: str = "msb-first"
    coefficient_order: str = "highest-degree-first"
    backend: str = "galois"
    backend_version: str = "0.4.11"

    def __post_init__(self):
        self.validate()

    def validate(self):
        for f in fields(self):
            value = getattr(self, f.name)
            if (type(value) is not type(f.default) or value != f.default
                    or isinstance(value, tuple) and any(type(x) is not int for x in value)):
                raise ValueError(f"Unsupported experimental parameter: {f.name}")


CONFIG = ExperimentalConfig()


def majority_vote(reads: tuple[Bits, ...]) -> Bits:
    """Exactly three or five full responses, no selection or adaptive retries."""
    if type(reads) is not tuple or len(reads) not in (3, 5):
        raise ValueError("majority requires a tuple of exactly 3 or 5 readings")
    for reading in reads:
        validate_bits(reading, 64, "reading")
    threshold = len(reads) // 2 + 1
    return tuple(int(sum(r[j] for r in reads) >= threshold) for j in range(64))


def remainder(word: Bits) -> int:
    value = 0
    for bit in word:
        value = (value << 1) | bit
    generator = CONFIG.generator_polynomial
    while value.bit_length() >= generator.bit_length():
        value ^= generator << (value.bit_length() - generator.bit_length())
    return value


def _bits(vector, length):
    if getattr(vector, "shape", None) != (length,):
        raise RuntimeError("unexpected experimental backend shape")
    result = tuple(vector.tolist())
    try:
        validate_bits(result, length, "backend output")
    except ValueError as error:
        raise RuntimeError("nonbinary experimental backend output") from error
    return result


@lru_cache(maxsize=1)
def _backend():
    if version("galois") != CONFIG.backend_version:
        raise RuntimeError("experimental codec requires galois==0.4.11")
    field = galois.GF(64, irreducible_poly=0x43, primitive_element=2)
    code = galois.BCH(63, 30, d=13, field=galois.GF2, extension_field=field,
                      alpha=field(2), c=1, systematic=True)
    identity = (code.n, code.k, code.t, code.d, int(field.irreducible_poly),
                int(code.alpha), code.c, int(code.generator_poly),
                code.is_systematic, code.is_primitive, code.is_narrow_sense)
    if identity != (63, 30, 6, 13, 0x43, 2, 1, 0x37CD0EB67, True, True, True):
        raise RuntimeError("experimental BCH identity mismatch")
    return code


class ExperimentalBCHCodec:
    __slots__ = ()
    n, k, t = 63, 30, 6
    parameters = CONFIG

    def initialize(self):
        _backend()

    def encode(self, message: Bits) -> Bits:
        validate_bits(message, 30, "message")
        word = _bits(_backend().encode(galois.GF2(message)), 63)
        if word[:30] != message or remainder(word):
            raise RuntimeError("inconsistent experimental encoding")
        return word

    def decode(self, received: Bits) -> BCHDecodeResult:
        validate_bits(received, 63, "received")
        raw, count = _backend().decode(galois.GF2(received), output="codeword", errors=True)
        if isinstance(count, bool) or not isinstance(count, Integral):
            raise RuntimeError("noninteger correction count")
        count = int(count)
        if count == -1:
            return BCHDecodeResult("uncorrectable", -1, None, None, "decoder_declared_failure")
        if not 0 <= count <= 6:
            raise RuntimeError("impossible correction count")
        word = _bits(raw, 63)
        if remainder(word) or sum(x != y for x, y in zip(received, word)) != count:
            raise RuntimeError("inconsistent experimental decoded codeword")
        return BCHDecodeResult("decoded", count, word[:30], word, None)


def credential_to_message(credential: bytes) -> Bits:
    if type(credential) is not bytes or len(credential) != 4 or credential[0] & 0xC0:
        raise ValueError("30-bit credential requires four bytes with top two bits zero")
    value = int.from_bytes(credential, "big")
    return tuple((value >> j) & 1 for j in range(29, -1, -1))


def message_to_credential(message: Bits) -> bytes:
    validate_bits(message, 30, "message")
    value = 0
    for bit in message:
        value = (value << 1) | bit
    return value.to_bytes(4, "big")


@dataclass(frozen=True)
class ExperimentalHelper:
    helper_bits: Bits
    enrollment_id: str
    config: ExperimentalConfig = CONFIG

    def __post_init__(self):
        self.validate()

    def validate(self):
        if type(self.config) is not ExperimentalConfig:
            raise ValueError("experimental config required")
        self.config.validate()
        validate_bits(self.helper_bits, 63, "helper")
        if type(self.enrollment_id) is not str or not self.enrollment_id.strip():
            raise ValueError("enrollment ID required")


_CODEC = ExperimentalBCHCodec()


def enroll(reference64: Bits, credential30: bytes, *, enrollment_id: str) -> ExperimentalHelper:
    validate_bits(reference64, 64, "reference")
    message = credential_to_message(credential30)
    # Validate identifiers before algebra; no implicit production helper conversion.
    ExperimentalHelper((0,) * 63, enrollment_id)
    word = _CODEC.encode(message)
    return ExperimentalHelper(tuple(a ^ b for a, b in zip(reference64[:63], word)), enrollment_id)


def reconstruct(noisy64: Bits, helper: ExperimentalHelper) -> ReconstructionResult:
    if type(helper) is not ExperimentalHelper:
        raise ValueError("experimental helper required")
    helper.validate()
    validate_bits(noisy64, 64, "response")
    result = _CODEC.decode(tuple(a ^ b for a, b in zip(noisy64[:63], helper.helper_bits)))
    if result.status == "uncorrectable":
        return ReconstructionResult("decoder_failure", result.status, -1, None, None,
                                    None, result.failure_reason)
    candidate = message_to_credential(result.candidate_message)
    # No BCH padding: None explicitly means not applicable, not a failed check.
    return ReconstructionResult("candidate_valid_format", result.status,
                                result.reported_correction_count, result.candidate_message,
                                candidate, None, None)