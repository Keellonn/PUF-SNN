"""Opt-in exact-arithmetic candidate for the existing wire-2 quality policy.

No protocol, parser, threshold, HMAC, session or inference-release policy change.
The reference Fraction implementation remains untouched. Mode selection is an
isolated serial-process experiment control, not a production configuration API.
"""

from contextlib import contextmanager, ExitStack
from unittest.mock import patch

from puf_snn.auth import binary_window, verifier as verifier_module

ProtocolError = binary_window.ProtocolError
REFERENCE_VALIDATE_QUALITY = binary_window.validate_quality
QUALITY_MODES = ("reference_fraction", "candidate_dyadic")

# Every finite binary32 is an integer multiple of 2**-149. These integer
# inequalities exactly reproduce the reference's rational comparisons.
UNIT = 1 << 149
UNIT_SQUARED = UNIT * UNIT
COMPONENT_LIMIT = 1_000_001 * UNIT
NORM_DENOMINATOR_SQUARED = 10_000**2
NORM_LOWER = 9_999**2 * UNIT_SQUARED
NORM_UPPER = 10_001**2 * UNIT_SQUARED
_mode_active = False


def binary32_units(word):
    """Return exact signed units of 2**-149; reject nonfinite/schema words."""
    if type(word) is not int or not 0 <= word < 1 << 32:
        raise ProtocolError("invalid_payload_schema")
    exponent = (word >> 23) & 255
    if exponent == 255:
        raise ProtocolError("invalid_payload_schema")
    mantissa = word & 0x7fffff
    if exponent:
        mantissa = (mantissa | (1 << 23)) << (exponent - 1)
    return -mantissa if word >> 31 else mantissa


def validate_quality_dyadic(window):
    """Exact counterpart of validate_quality on its structurally typed input.

Representation validation remains in encode_window/parse_window. There is no
float conversion, approximation, cache, quality bypass or threshold relaxation.
Keep check order and the reference data_quality_failure reason unchanged.
"""
    def require(condition):
        if not condition:
            raise ProtocolError("data_quality_failure")

    require(abs(window.capture_end_ns - window.capture_start_ns - 2_000_000_000) <= 120)
    count = sum(sample.tracking_valid for sample in window.samples)
    require(114 <= count <= 120 and count == window.tracking_valid_count)
    require(binary_window.tracking_ppm(count) == window.tracking_valid_fraction_ppm)
    previous_time = None
    previous_q = None
    for sample in window.samples:
        capture_time = sample.capture_time_ns
        require(window.capture_start_ns <= capture_time < window.capture_end_ns)
        require(previous_time is None or 0 < capture_time - previous_time <= 50_000_000)
        q = tuple(binary32_units(value.bits) for value in sample.orientation_xyzw)
        require(all(abs(value) * 1_000_000 <= COMPONENT_LIMIT for value in q))
        scaled_norm = sum(value * value for value in q) * NORM_DENOMINATOR_SQUARED
        require(NORM_LOWER <= scaled_norm <= NORM_UPPER)
        require(previous_q is None or sum(a*b for a, b in zip(q, previous_q)) >= 0)
        previous_time, previous_q = capture_time, q


@contextmanager
def quality_validator_mode(mode):
    """Temporary serial-only selection, restored on normal/exceptional exit.

Enter this BEFORE instrument_pipeline, so both reference and candidate use the
same outer timing wrappers. The codec global handles sender encoding; the
verifier's imported alias handles its post-HMAC quality check. Nothing else is
patched. Concurrent threads or overlapping mode selections are unsupported.
"""
    global _mode_active
    if mode not in QUALITY_MODES:
        raise ValueError("unknown quality experiment mode")
    if _mode_active:
        raise RuntimeError("quality experiment modes cannot overlap")
    if (binary_window.validate_quality is not REFERENCE_VALIDATE_QUALITY
            or verifier_module.validate_quality is not REFERENCE_VALIDATE_QUALITY):
        raise RuntimeError("unexpected quality wrappers; select mode before instrumentation")
    _mode_active = True
    try:
        with ExitStack() as stack:
            if mode == "candidate_dyadic":
                stack.enter_context(patch.object(binary_window, "validate_quality", validate_quality_dyadic))
                stack.enter_context(patch.object(verifier_module, "validate_quality", validate_quality_dyadic))
            yield
    finally:
        _mode_active = False
