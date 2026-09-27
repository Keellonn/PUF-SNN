"""these tests check binary mutations state preservation and JSON transport ordering"""

from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/python/scripts"))

from puf_snn.auth.binary_window import F32, encode_window, parse_envelope, window_tag
from puf_snn.auth.config import AuthConfig
from puf_snn.integration import ExactlyOnceClassifierRelease
from run_layer3_demo import establish, initialize_material, synthetic_window


def packet_with_bytes(packet: bytes, data: bytes) -> bytes:
    import base64
    envelope = json.loads(packet)
    envelope["protected"]["bytes_b64"] = base64.b64encode(data).decode("ascii")
    return json.dumps(envelope, separators=(",", ":")).encode("utf-8")


class ProtocolRejectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.material = initialize_material()

    def test_binary_mutations_reject_without_poisoning_next_window(self) -> None:
        for case in ("endian", "float", "field_order", "version", "length"):
            with self.subTest(case=case):
                sender, verifier, _ = establish(AuthConfig(), self.material)
                window = synthetic_window()
                first = replace(window.samples[0], position_m=(F32(0x3E800000), F32(0xBF000000), F32(0)))
                window = replace(window, samples=(first, *window.samples[1:]))
                packet = sender.seal_window(window)
                parsed = parse_envelope(packet)
                data = bytearray(parsed.authenticated_bytes)
                device_length = int.from_bytes(data[19:21], "big")
                window_offset = 21 + device_length + 24
                capture_offset = window_offset + 2 + int.from_bytes(data[window_offset:window_offset + 2], "big")
                position_offset = capture_offset + 32 + 3 + 10

                if case == "endian":
                    data[position_offset:position_offset + 4] = data[position_offset:position_offset + 4][::-1]
                elif case == "float":
                    data[position_offset + 3] ^= 1
                elif case == "field_order":
                    data[position_offset:position_offset + 8] = data[position_offset + 4:position_offset + 8] + data[position_offset:position_offset + 4]
                elif case == "version":
                    data[5] = 3
                else:
                    data[capture_offset + 31] ^= 1

                calls = []
                gate = ExactlyOnceClassifierRelease(verifier, lambda record: record, lambda record: calls.append(record))
                before = verifier.session_status(sender.session_id)
                rejected = verifier.verify_window(packet_with_bytes(packet, bytes(data)))
                self.assertEqual(rejected.result, "reject")
                with self.assertRaises(ValueError):
                    gate.deliver(rejected)
                self.assertEqual(calls, [])
                self.assertEqual(verifier.session_status(sender.session_id), before)
                accepted = verifier.verify_window(packet)
                self.assertEqual(accepted.result, "accept")
                gate.deliver(accepted)
                self.assertEqual(len(calls), 1)

    def test_outer_json_key_order_is_not_binary_field_order(self) -> None:
        sender, verifier, _ = establish(AuthConfig(), self.material)
        packet = sender.seal_window(synthetic_window())
        envelope = json.loads(packet)
        reordered = {"authentication": envelope["authentication"], "protected": envelope["protected"]}
        result = verifier.verify_window(json.dumps(reordered).encode("utf-8"))
        self.assertEqual(result.result, "accept")

    def test_invalid_tag_with_high_sequence_does_not_poison_valid_sequence(self) -> None:
        sender, verifier, _ = establish(AuthConfig(), self.material)
        packet = sender.seal_window(synthetic_window())
        parsed = parse_envelope(packet)
        changed = encode_window(replace(parsed.window, sequence_number=2 ** 63))
        before = verifier.session_status(sender.session_id)
        result = verifier.verify_window(packet_with_bytes(packet, changed))
        self.assertEqual(result.reason, "invalid_tag")
        self.assertEqual(verifier.session_status(sender.session_id), before)
        self.assertEqual(verifier.verify_window(packet).result, "accept")


if __name__ == "__main__":
    unittest.main()
