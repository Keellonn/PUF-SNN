"""Shared Wire-2 boundary for processed motion and classifier delivery.

This module deliberately owns neither authentication decisions nor classifier
preprocessing.  It converts the repository's existing processed-window dicts to
immutable Wire-2 values, converts an accepted Window back to that classifier
record shape, and gates one classifier delivery through Verifier.release_accepted().
"""

from collections.abc import Callable
import math
import struct
from threading import RLock
from typing import Any

from puf_snn.auth.binary_window import F32, ProtocolError, Sample, Window, tracking_ppm
from puf_snn.auth.verifier import VerificationResult, Verifier


UNBOUND_DEVICE_ID = "unbound"
UNBOUND_SESSION_ID = bytes(16)
UNBOUND_SEQUENCE_NUMBER = 0


def _binary32(value: object) -> F32:
    """Round one ordinary JSON number once to finite IEEE-754 binary32.

    Python's big-endian ``struct`` conversion supplies the deterministic
    round-to-nearest/even conversion.  Wire-2 canonical positive zero replaces
    a negative-zero input.  Booleans, non-numbers, nonfinite values and binary32
    overflow are rejected rather than coerced into a payload.
    """
    if type(value) not in (int, float):
        raise ValueError("motion values must be Python int or float values")
    try:
        number = float(value)
    except (OverflowError, ValueError):
        raise ValueError("motion value is outside the supported numeric range") from None
    if not math.isfinite(number):
        raise ValueError("motion values must be finite")
    try:
        encoded = struct.pack(">f", number)
    except (OverflowError, struct.error):
        raise ValueError("motion value is outside finite binary32 range") from None
    bits = int.from_bytes(encoded, "big")
    return F32(0 if bits == 0x80000000 else bits)


def _required(record: dict[str, Any], name: str) -> Any:
    if name not in record:
        raise ValueError(f"processed window is missing {name}")
    return record[name]


def processed_record_to_wire_window(record: dict[str, Any]) -> Window:
    """Convert one existing Quest-style processed record to an unbound Window.

    ``record`` is the JSON-decoded dict consumed by the existing data and
    classifier code.  Dataset device/session/sequence fields are intentionally
    ignored.  Sender.seal_window() supplies their cryptographic replacements.
    Motion components are rounded exactly once to canonical binary32 here.
    """
    if type(record) is not dict:
        raise ValueError("processed window must be a dict")
    window_id = _required(record, "window_id")
    start = _required(record, "window_start_ns")
    end = _required(record, "window_end_ns")
    rows = _required(record, "samples")
    if type(window_id) is not str or not window_id:
        raise ValueError("window_id must be a nonempty string")
    if type(start) is not int or isinstance(start, bool):
        raise ValueError("window_start_ns must be an integer")
    if type(end) is not int or isinstance(end, bool):
        raise ValueError("window_end_ns must be an integer")
    if type(rows) is not list or len(rows) != 120:
        raise ValueError("processed window must contain exactly 120 samples")

    samples = []
    for expected, row in enumerate(rows):
        if type(row) is not dict:
            raise ValueError(f"sample {expected} must be a dict")
        index = row.get("sample_index")
        capture = row.get("capture_time_ns")
        position = row.get("position_m")
        orientation = row.get("orientation_xyzw")
        tracking = row.get("tracking_valid")
        if type(index) is not int or isinstance(index, bool) or index != expected:
            raise ValueError("sample indexes must be consecutive from zero")
        if type(capture) is not int or isinstance(capture, bool):
            raise ValueError(f"sample {expected} capture_time_ns must be an integer")
        if type(position) is not list or len(position) != 3:
            raise ValueError(f"sample {expected} position_m must contain three values")
        if type(orientation) is not list or len(orientation) != 4:
            raise ValueError(f"sample {expected} orientation_xyzw must contain four values")
        if type(tracking) is not bool:
            raise ValueError(f"sample {expected} tracking_valid must be a boolean")
        samples.append(Sample(
            expected,
            capture,
            tuple(_binary32(value) for value in position),
            tuple(_binary32(value) for value in orientation),
            tracking,
        ))

    sample_tuple = tuple(samples)
    valid = sum(sample.tracking_valid for sample in sample_tuple)
    try:
        return Window(
            UNBOUND_DEVICE_ID,
            UNBOUND_SESSION_ID,
            UNBOUND_SEQUENCE_NUMBER,
            window_id,
            start,
            end,
            valid,
            tracking_ppm(valid),
            sample_tuple,
        )
    except ProtocolError as error:
        raise ValueError(error.reason) from error


def _float(value: F32) -> float:
    if type(value) is not F32:
        raise ValueError("accepted motion component must be F32")
    return struct.unpack(">f", value.encode())[0]


def _accepted_window_to_classifier_record(window: Window) -> dict[str, Any]:
    """Restore an immutable accepted Window to the existing classifier record API.

    Binary32 values widen exactly to Python binary64 floats.  The record contains
    no label or dataset split.  The current ``record_to_features()`` consumes its
    sample list and produces 840 values (120 samples x 7 pose channels); tracking
    validity remains authenticated metadata but is not a current model channel.
    """
    if type(window) is not Window or type(window.samples) is not tuple or len(window.samples) != 120:
        raise ValueError("accepted Window required")
    samples = []
    for expected, sample in enumerate(window.samples):
        if type(sample) is not Sample or sample.sample_index != expected:
            raise ValueError("accepted Window has invalid sample structure")
        samples.append({
            "sample_index": expected,
            "capture_time_ns": sample.capture_time_ns,
            "position_m": [_float(value) for value in sample.position_m],
            "orientation_xyzw": [_float(value) for value in sample.orientation_xyzw],
            "tracking_valid": sample.tracking_valid,
        })
    return {
        "schema_version": "1.0",
        "window_id": window.window_id,
        "device_id": window.device_id,
        "session_id": window.session_id.hex(),
        "sequence_number": window.sequence_number,
        "coordinate_frame": "unity_device_origin",
        "target_sample_rate_hz": 60,
        "window_start_ns": window.capture_start_ns,
        "window_end_ns": window.capture_end_ns,
        "samples": samples,
    }


class ExactlyOnceClassifierRelease:
    """Deliver each accepted event to preprocessing/classification at most once.

    Authentication authority remains entirely in the bound Verifier.  An event is
    consumed immediately before preprocessing begins, so a preprocessing or
    classifier exception cannot cause the authenticated payload to be delivered a
    second time by retrying this wrapper.
    """

    def __init__(self, verifier: Verifier, preprocess: Callable[[dict[str, Any]], Any],
                 classifier: Callable[[Any], Any]):
        if type(verifier) is not Verifier or not callable(preprocess) or not callable(classifier):
            raise ValueError("verifier and callable preprocessing/classifier are required")
        self._verifier = verifier
        self._preprocess = preprocess
        self._classifier = classifier
        self._consumed: set[str] = set()
        self._lock = RLock()

    @property
    def consumed_event_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._consumed))

    def deliver(self, result: VerificationResult) -> Any:
        if type(result) is not VerificationResult or type(result.event_id) is not str:
            raise ValueError("verifier acceptance required")
        with self._lock:
            if result.event_id in self._consumed:
                raise ValueError("accepted event was already delivered")

            def consume(window: Window) -> Any:
                self._consumed.add(result.event_id)
                record = _accepted_window_to_classifier_record(window)
                return self._classifier(self._preprocess(record))

            return self._verifier.release_accepted(result, consume)


__all__ = [
    "ExactlyOnceClassifierRelease",
    "processed_record_to_wire_window",
]
