"""One-reading code-offset reconstruction with no evaluator ground truth."""

from dataclasses import dataclass, fields
from typing import Literal
from .bch import BCH_PARAMETERS, BCHCodec, Bits, DecoderStatus, validate_bits

@dataclass(frozen=True)
class ReconstructionConfig:
    """Versioned identity of the frozen construction, not tunable parameters.

    Alternative designs require a new version and separate experimental evidence.
    Construction and API validation reject changed fields instead of ignoring them.
    """

    version: str = "puf-snn-reconstruction-v1"
    response_length: int = 64
    response_indices: tuple[int, ...] = tuple(range(63))
    credential_bytes: int = 4
    padding: Bits = (0, 0, 0, 0)
    code_id: str = BCH_PARAMETERS.code_id
    n: int = BCH_PARAMETERS.n
    k: int = BCH_PARAMETERS.k
    t: int = BCH_PARAMETERS.t
    designed_distance: int = BCH_PARAMETERS.designed_distance
    field_order: int = BCH_PARAMETERS.field_order
    primitive_polynomial: int = BCH_PARAMETERS.primitive_polynomial
    primitive_element: int = BCH_PARAMETERS.primitive_element
    first_root_exponent: int = BCH_PARAMETERS.first_root_exponent
    generator_polynomial: int = BCH_PARAMETERS.generator_polynomial
    systematic: bool = BCH_PARAMETERS.systematic
    bit_order: str = BCH_PARAMETERS.bit_order
    coefficient_order: str = BCH_PARAMETERS.coefficient_order
    backend: str = BCH_PARAMETERS.backend
    backend_version: str = BCH_PARAMETERS.backend_version

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for field in fields(ReconstructionConfig):
            value, expected = getattr(self, field.name), field.default
            if (type(value) is not type(expected) or value != expected
                    or (isinstance(value, tuple)
                        and any(type(item) is not int for item in value))):
                raise ValueError(f"Unsupported reconstruction configuration: {field.name}")

DEFAULT_CONFIG = ReconstructionConfig()
_CODEC = BCHCodec()

def _validate_config(config: ReconstructionConfig) -> None:
    if type(config) is not ReconstructionConfig:
        raise ValueError("config must be a ReconstructionConfig")
    config.validate()


def _validate_enrollment_id(enrollment_id: str | None) -> None:
    if enrollment_id is not None and (
        type(enrollment_id) is not str or not enrollment_id.strip()
    ):
        raise ValueError("enrollment_id must be None or a nonempty string")


@dataclass(frozen=True)
class HelperData:
    """Public material only. Routing labels provide no authenticity guarantee."""

    helper_bits: Bits
    config: ReconstructionConfig = DEFAULT_CONFIG
    enrollment_id: str | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _validate_config(self.config)
        validate_bits(self.helper_bits, self.config.n, "helper_bits")
        _validate_enrollment_id(self.enrollment_id)

@dataclass(frozen=True)
class ReconstructionResult:
    """Candidate production only; evaluator match/mismatch is intentionally absent."""
    outcome: Literal[
        "decoder_failure", "invalid_format_or_padding", "candidate_valid_format"
    ]
    decoder_status: DecoderStatus
    reported_correction_count: int
    candidate_message: Bits | None
    candidate_credential: bytes | None
    padding_valid: bool | None
    failure_reason: str | None

def enroll(
    reference64: Bits,
    credential32: bytes,
    config: ReconstructionConfig = DEFAULT_CONFIG,
    *,
    enrollment_id: str | None = None,
) -> HelperData:
    """Use trusted enrollment inputs transiently; return only public helper data.

    Credential generation belongs to the caller and must use a separate stream
    from Layer 1. This function never generates or samples a PUF response.
    """
    _validate_config(config)
    validate_bits(reference64, config.response_length, "reference64")
    if type(credential32) is not bytes or len(credential32) != config.credential_bytes:
        raise ValueError("credential32 must be exactly four bytes")
    _validate_enrollment_id(enrollment_id)
    message = tuple((byte >> shift) & 1 for byte in credential32
                    for shift in range(7, -1, -1)) + config.padding
    codeword = _CODEC.encode(message)
    helper = tuple(reference64[index] ^ bit
                   for index, bit in zip(config.response_indices, codeword))
    return HelperData(helper, config, enrollment_id)


def reconstruct(
    noisy64: Bits,
    helper_data: HelperData,
    config: ReconstructionConfig | None = None,
) -> ReconstructionResult:
    """Exactly one decode of one reading, using only public enrollment material.

    If supplied, config must match the helper's supported configuration. No
    retries, voting, read regeneration, reference comparisons or credential
    verification take place here. Invalid inputs raise ValueError; implementation
    and dependency errors propagate instead of becoming ordinary decoder failures.
    """
    if type(helper_data) is not HelperData:
        raise ValueError("helper_data must be HelperData")
    helper_data.validate()
    if config is None:
        config = helper_data.config
    _validate_config(config)
    if config != helper_data.config:
        raise ValueError("config does not match helper_data.config")
    validate_bits(noisy64, config.response_length, "noisy64")
    received = tuple(
        noisy64[index] ^ bit
        for index, bit in zip(config.response_indices, helper_data.helper_bits)
    )
    decoded = _CODEC.decode(received)
    if decoded.status == "uncorrectable":
        return ReconstructionResult(
            "decoder_failure", decoded.status, decoded.reported_correction_count,
            None, None, None, decoded.failure_reason,
        )
    message = decoded.candidate_message
    if message is None:
        raise RuntimeError("Decoded BCH result lacks a candidate message")
    if message[-len(config.padding):] != config.padding:
        return ReconstructionResult(
            "invalid_format_or_padding", decoded.status,
            decoded.reported_correction_count, message, None, False,
            "nonzero_padding",
        )
    value = 0
    for bit in message[:config.credential_bytes * 8]:
        value = (value << 1) | bit
    return ReconstructionResult(
        "candidate_valid_format", decoded.status, decoded.reported_correction_count,
        message, value.to_bytes(config.credential_bytes, "big"), True, None,
    )