"""
this script checks C# generated mutations against the real Python verifier
all keys and motion fixtures are explicitly synthetic and test only
"""

import argparse
import base64
import hashlib
import hmac
import json
import sys

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/python"))
sys.path.insert(0, str(ROOT / "src/python/scripts"))

from puf_snn.auth.binary_window import encode_window, parse_window, window_tag
from puf_snn.auth.config import AuthConfig
from puf_snn.integration import ExactlyOnceClassifierRelease
from run_layer3_demo import establish, initialize_material


def envelope(data: bytes, session_id: bytes, tag: bytes) -> bytes:
    return json.dumps({"protected": {"encoding": "puf-snn-binary32-be-v2", "bytes_b64": base64.b64encode(data).decode("ascii")}, "authentication": {"algorithm": "HMAC-SHA-256", "key_id": session_id.hex(), "tag_hex": tag.hex()}}, separators=(",", ":")).encode("utf-8")


def check_vectors(fixture: dict) -> dict:
    original = bytes.fromhex(fixture["canonical_hex"])
    key = bytes.fromhex(fixture["key_hex"])

    if hashlib.sha256(original).hexdigest() != fixture["sha256"] or hmac.new(key, original, hashlib.sha256).hexdigest() != fixture["tag_hex"]:
        raise ValueError("C# hashes do not match independently computed Python hashes")

    if encode_window(parse_window(original)) != original:
        raise ValueError("C# canonical bytes do not round trip through Python")

    material = initialize_material()
    observations = []
    device_length = int.from_bytes(original[19:21], "big")
    session_offset = 21 + device_length

    for vector in fixture["vectors"]:
        sender, verifier, _ = establish(AuthConfig(), material)
        canonical = bytearray(original)
        canonical[session_offset:session_offset + 16] = sender.session_id
        changed = bytearray.fromhex(vector["changed_hex"])
        changed[session_offset:session_offset + 16] = sender.session_id
        tag = window_tag(sender._key, bytes(canonical))
        calls = []
        gate = ExactlyOnceClassifierRelease(verifier, lambda record: record, lambda record: calls.append(record["window_id"]))
        before = verifier.session_status(sender.session_id)
        result = verifier.verify_window(envelope(bytes(changed), sender.session_id, tag))

        if result.result != "reject":
            raise AssertionError(f"mutation was accepted: {vector['name']}")

        try:
            gate.deliver(result)
            raise AssertionError("rejection reached the classifier")
        except ValueError:
            pass

        if calls or verifier.session_status(sender.session_id) != before:
            raise AssertionError("mutation changed classifier calls or sequence state")

        accepted = verifier.verify_window(envelope(bytes(canonical), sender.session_id, tag))

        if accepted.result != "accept":
            raise AssertionError("valid next window failed after rejection")

        gate.deliver(accepted)

        if len(calls) != 1:
            raise AssertionError("valid next window was not delivered once")

        observations.append({"mutation": vector["name"], "decision": result.result, "reason": result.reason, "classifier_calls_after_rejection": 0, "state_unchanged": True, "valid_next_window_accepted": True})
        verifier.close_all_sessions()

    return {"source": fixture["source"], "canonical_sha256": fixture["sha256"], "observations": observations, "scope": "five deterministic cross-language negative cases, not independent attack-rate estimates; outer JSON key order is not authenticated binary field order"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vectors", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = check_vectors(json.loads(arguments.vectors.read_text(encoding="utf-8")))

    with arguments.output.open("x", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
        output.write("\n")

    print("PASS: five C# mutations rejected, no classifier calls, sequence preserved and valid next window accepted")


if __name__ == "__main__":
    main()
