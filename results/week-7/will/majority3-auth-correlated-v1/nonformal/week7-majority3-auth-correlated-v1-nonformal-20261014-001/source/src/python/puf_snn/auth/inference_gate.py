"""
this file controls whether a verifier result is allowed to reach motion inference
it does not verify HMAC tags or maintain authentication state because those belong to the verifier
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def _check_verifier_binding(protected_message: dict[str, Any], verification_result: dict[str, Any]) -> None:
    # the decision must identify the exact protected message that was checked
    required_fields = {
        "result",
        "reason",
        "device_id",
        "session_id",
        "window_id",
        "sequence_number",
    }
    missing_fields = sorted(required_fields - set(verification_result))

    if missing_fields:
        raise ValueError(f"verification result is missing fields: {missing_fields}")

    for field in ("device_id", "session_id", "window_id", "sequence_number"):
        if verification_result[field] != protected_message[field]:
            raise ValueError(f"verification result does not match protected {field}")


def protected_payload_to_motion_record(protected_message: dict[str, Any]) -> dict[str, Any]:
    # this restores the protected fixed-decimal payload to the numeric format used by preprocessing
    payload = protected_message["payload"]
    samples = []

    for sample in payload["samples"]:
        samples.append(
            {
                "sample_index": sample["sample_index"],
                "capture_time_ns": sample["capture_time_ns"],
                "position_m": [float(value) for value in sample["position_m"]],
                "orientation_xyzw": [float(value) for value in sample["orientation_xyzw"]],
                "tracking_valid": sample["tracking_valid"],
            }
        )

    return {
        "schema_version": protected_message["payload_schema_version"],
        "window_id": protected_message["window_id"],
        "device_id": protected_message["device_id"],
        "session_id": protected_message["session_id"],
        "sequence_number": protected_message["sequence_number"],
        "coordinate_frame": payload["coordinate_frame"],
        "target_sample_rate_hz": payload["target_sample_rate_hz"],
        "window_start_ns": protected_message["capture_start_ns"],
        "window_end_ns": protected_message["capture_end_ns"],
        "samples": samples,
    }


def route_verified_window(envelope: dict[str, Any], verification_result: dict[str, Any], accepted_consumer: Callable[[dict[str, Any]], Any]) -> dict[str, Any]:
    # only a separately supplied verifier acceptance may call preprocessing or inference
    protected_message = envelope["protected"]
    _check_verifier_binding(protected_message, verification_result)

    result = verification_result["result"]
    reason = verification_result["reason"]

    if result not in {"accept", "reject"}:
        raise ValueError("verification result must be accept or reject")

    if result == "accept" and reason != "accepted":
        raise ValueError("an accepted verification result must use the accepted reason")

    if result == "reject" and reason == "accepted":
        raise ValueError("a rejected verification result cannot use the accepted reason")

    if result == "reject":
        return {
            "forwarded": False,
            "authentication_result": result,
            "reason": reason,
            "window_id": protected_message["window_id"],
            "consumer_result": None,
        }

    motion_record = protected_payload_to_motion_record(protected_message)
    consumer_result = accepted_consumer(motion_record)

    return {
        "forwarded": True,
        "authentication_result": result,
        "reason": reason,
        "window_id": protected_message["window_id"],
        "consumer_result": consumer_result,
    }
