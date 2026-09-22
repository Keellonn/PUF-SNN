"""
this script creates an inspectable authenticated-window example from one synthetic motion window
the fixed key is public test material for cross-language verification and is never a real session key
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT / "src" / "python"))

from puf_snn.auth.window_message import build_authenticated_envelope
from puf_snn.auth.window_message import build_protected_message
from puf_snn.auth.window_message import canonicalize_protected_message


DEFAULT_SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "authenticated-window.schema.json"
DEFAULT_OUTPUT_DIRECTORY = REPOSITORY_ROOT / "results" / "week-4" / "shared" / "golden-vector"
TEST_KEY_ID = "week4-test-session-key-001"
TEST_SESSION_KEY_HEX = "11" * 32


def make_golden_window() -> dict:
    # this fixed artificial window is shared by Python and Unity and contains no human data
    samples = []
    start_time_ns = 1_000_000_000

    for sample_index in range(120):
        position = [0.0, 0.0, 0.0]

        if sample_index == 0:
            position = [0.125, -0.25, 0.0]

        samples.append(
            {
                "sample_index": sample_index,
                "capture_time_ns": start_time_ns + sample_index * 16_666_667,
                "position_m": position,
                "orientation_xyzw": [0.0, 0.0, 0.0, 1.0],
                "tracking_valid": True,
            }
        )

    return {
        "schema_version": "0.2",
        "window_id": "quest-02-session-01-nod-000-window-000",
        "device_id": "quest-02",
        "session_id": "quest-02-session-01",
        "sequence_number": 0,
        "coordinate_frame": "unity_device_origin",
        "target_sample_rate_hz": 60,
        "window_start_ns": start_time_ns,
        "window_end_ns": 3_000_000_000,
        "samples": samples,
    }


def create_vector(schema_path: Path, output_directory: Path) -> dict:
    # this produces canonical bytes, a schema-valid envelope, and reproducibility metadata
    window = make_golden_window()
    protected_message = build_protected_message(window)
    canonical_bytes = canonicalize_protected_message(protected_message)
    test_session_key = bytes.fromhex(TEST_SESSION_KEY_HEX)
    tag_hex = hmac.new(test_session_key, canonical_bytes, hashlib.sha256).hexdigest()
    envelope = build_authenticated_envelope(protected_message, TEST_KEY_ID, tag_hex)

    with schema_path.open("r", encoding="utf-8") as schema_file:
        schema = json.load(schema_file)

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    schema_errors = sorted(validator.iter_errors(envelope), key=lambda error: list(error.absolute_path))

    if schema_errors:
        messages = [f"{list(error.absolute_path)}: {error.message}" for error in schema_errors]
        raise ValueError("authenticated envelope failed schema validation: " + "; ".join(messages))

    output_directory.mkdir(parents=True, exist_ok=True)
    canonical_path = output_directory / "canonical-protected-message.json"
    envelope_path = output_directory / "authenticated-window-example.json"
    vector_path = output_directory / "golden-vector.json"

    canonical_path.write_bytes(canonical_bytes)

    with envelope_path.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump(envelope, output_file, indent=2, ensure_ascii=False, allow_nan=False)
        output_file.write("\n")

    vector = {
        "purpose": "public test-only cross-language vector; never use this key for a real session",
        "source": "fixed artificial Python and Unity test window",
        "source_window_id": window["window_id"],
        "protocol_version": protected_message["protocol_version"],
        "message_schema_version": protected_message["message_schema_version"],
        "payload_encoding": protected_message["payload_encoding"],
        "key_id": TEST_KEY_ID,
        "test_session_key_hex": TEST_SESSION_KEY_HEX,
        "canonical_byte_count": len(canonical_bytes),
        "canonical_sha256": hashlib.sha256(canonical_bytes).hexdigest(),
        "expected_hmac_sha256": tag_hex,
        "canonical_file": canonical_path.name,
        "envelope_file": envelope_path.name,
    }

    with vector_path.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump(vector, output_file, indent=2)
        output_file.write("\n")

    return vector


def main() -> None:
    vector = create_vector(DEFAULT_SCHEMA_PATH, DEFAULT_OUTPUT_DIRECTORY)

    print(f"wrote golden vector to {DEFAULT_OUTPUT_DIRECTORY}")
    print(f"source window: {vector['source_window_id']}")
    print(f"canonical bytes: {vector['canonical_byte_count']}")
    print(f"canonical SHA-256: {vector['canonical_sha256']}")
    print(f"expected HMAC-SHA-256: {vector['expected_hmac_sha256']}")


if __name__ == "__main__":
    main()
