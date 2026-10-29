"""
this file converts one validated Quest motion window into the shared protected message
it creates the exact deterministic bytes that the sender will tag and the verifier will check
"""

from __future__ import annotations

import json
import math
import re
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Any


PROTOCOL_VERSION = "1.0"
MESSAGE_SCHEMA_VERSION = "1.0"
PAYLOAD_ENCODING = "puf-snn-fixed-decimal-json-v1"
AUTHENTICATION_ALGORITHM = "HMAC-SHA-256"
MOTION_DECIMAL_PLACES = 8
MINIMUM_TRACKING_VALID_SAMPLES = 114
EXPECTED_SAMPLE_COUNT = 120


def _require_fields(record: dict[str, Any], required_fields: set[str], record_name: str) -> None:
    # this catches a missing field before the message can be serialized or tagged
    missing_fields = sorted(required_fields - set(record))

    if missing_fields:
        raise ValueError(f"{record_name} is missing required fields: {missing_fields}")


def _format_motion_value(value: Any) -> str:
    # fixed decimal strings avoid different float formatting between Python and Unity
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("motion values must be numbers")

    if not math.isfinite(float(value)):
        raise ValueError("motion values must be finite")

    quantum = Decimal(1).scaleb(-MOTION_DECIMAL_PLACES)
    decimal_value = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_EVEN)

    if decimal_value == Decimal("-0").quantize(quantum):
        decimal_value = Decimal("0").quantize(quantum)

    return format(decimal_value, f".{MOTION_DECIMAL_PLACES}f")


def _build_payload_sample(sample: dict[str, Any], expected_index: int) -> dict[str, Any]:
    # every protected sample keeps its order, time, pose, and tracking flag
    required_fields = {
        "sample_index",
        "capture_time_ns",
        "position_m",
        "orientation_xyzw",
        "tracking_valid",
    }
    _require_fields(sample, required_fields, f"sample {expected_index}")

    if sample["sample_index"] != expected_index:
        raise ValueError("sample indexes must be consecutive from zero")

    if not isinstance(sample["capture_time_ns"], int) or isinstance(sample["capture_time_ns"], bool):
        raise ValueError("sample timestamps must be integers")

    if not isinstance(sample["tracking_valid"], bool):
        raise ValueError("tracking_valid must be a boolean")

    position = sample["position_m"]
    orientation = sample["orientation_xyzw"]

    if not isinstance(position, list) or len(position) != 3:
        raise ValueError("position_m must contain three values")

    if not isinstance(orientation, list) or len(orientation) != 4:
        raise ValueError("orientation_xyzw must contain four values")

    return {
        "sample_index": expected_index,
        "capture_time_ns": sample["capture_time_ns"],
        "position_m": [_format_motion_value(value) for value in position],
        "orientation_xyzw": [_format_motion_value(value) for value in orientation],
        "tracking_valid": sample["tracking_valid"],
    }


def build_protected_message(window: dict[str, Any]) -> dict[str, Any]:
    # only the sender-created protected object is converted into HMAC input bytes
    required_fields = {
        "schema_version",
        "window_id",
        "device_id",
        "session_id",
        "sequence_number",
        "coordinate_frame",
        "target_sample_rate_hz",
        "window_start_ns",
        "window_end_ns",
        "samples",
    }
    _require_fields(window, required_fields, "window")

    samples = window["samples"]

    if not isinstance(samples, list) or len(samples) != EXPECTED_SAMPLE_COUNT:
        raise ValueError(f"window must contain exactly {EXPECTED_SAMPLE_COUNT} samples")

    payload_samples = [
        _build_payload_sample(sample, sample_index)
        for sample_index, sample in enumerate(samples)
    ]

    tracking_valid_count = sum(sample["tracking_valid"] for sample in payload_samples)

    if tracking_valid_count < MINIMUM_TRACKING_VALID_SAMPLES:
        raise ValueError("window does not meet the 95 percent tracking requirement")

    tracking_valid_fraction_ppm = round(tracking_valid_count * 1_000_000 / EXPECTED_SAMPLE_COUNT)

    return {
        "protocol_version": PROTOCOL_VERSION,
        "message_schema_version": MESSAGE_SCHEMA_VERSION,
        "payload_schema_version": window["schema_version"],
        "device_id": window["device_id"],
        "session_id": window["session_id"],
        "window_id": window["window_id"],
        "sequence_number": window["sequence_number"],
        "capture_start_ns": window["window_start_ns"],
        "capture_end_ns": window["window_end_ns"],
        "payload_encoding": PAYLOAD_ENCODING,
        "data_quality": {
            "status": "pass",
            "sample_count": EXPECTED_SAMPLE_COUNT,
            "tracking_valid_count": tracking_valid_count,
            "tracking_valid_fraction_ppm": tracking_valid_fraction_ppm,
        },
        "payload": {
            "coordinate_frame": window["coordinate_frame"],
            "target_sample_rate_hz": window["target_sample_rate_hz"],
            "samples": payload_samples,
        },
    }


def canonicalize_protected_message(protected_message: dict[str, Any]) -> bytes:
    # sorted compact UTF-8 JSON is the one byte representation used by both sides
    return json.dumps(
        protected_message,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def build_authenticated_envelope(protected_message: dict[str, Any], key_id: str, tag_hex: str) -> dict[str, Any]:
    # the partner authentication layer supplies the public key id and computed HMAC tag
    if not key_id:
        raise ValueError("key_id must not be empty")

    if re.fullmatch(r"[0-9a-f]{64}", tag_hex) is None:
        raise ValueError("tag_hex must contain exactly 64 lowercase hexadecimal characters")

    return {
        "protected": protected_message,
        "authentication": {
            "algorithm": AUTHENTICATION_ALGORITHM,
            "key_id": key_id,
            "tag_hex": tag_hex,
        },
    }
