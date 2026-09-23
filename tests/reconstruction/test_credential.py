from dataclasses import FrozenInstanceError, asdict, fields, replace
import inspect
from itertools import combinations
import json
from pathlib import Path
import random
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/python"))
sys.path.insert(0, str(ROOT / "tests"))

from puf_snn.puf.device import create_device
from puf_snn.puf.ro_puf import generate_pairs, generate_response
from puf_snn.puf.variables import ReadConditions
from puf_snn.reconstruction import (
    BCHCodec, BCHDecodeResult, DEFAULT_CONFIG, HelperData, ReconstructionConfig,
    enroll, reconstruct,
)
from reconstruction.reference import bits, encode, flip
from scripts.run_puf_baseline import make_rng

CREDENTIALS = tuple(bytes.fromhex(value) for value in
                    ("00000000", "00000001", "12345678", "ffffffff", "80000000"))
REFERENCE = tuple(index % 2 for index in range(64))


class CredentialTests(unittest.TestCase):
    def assert_candidate_matches(self, result, credential, errors):
        self.assertEqual(result.outcome, "candidate_valid_format")
        self.assertEqual(result.decoder_status, "decoded")
        self.assertEqual(result.reported_correction_count, errors)
        self.assertTrue(result.padding_valid)
        self.assertIsNone(result.failure_reason)
        # This is evaluator/test code; production reconstruction never sees this.
        self.assertEqual(result.candidate_credential, credential)
        self.assertEqual(result.candidate_message,
                         bits(int.from_bytes(credential, "big") << 4, 36))

    def test_enrollment_matches_independent_code_offset(self):
        for credential in CREDENTIALS:
            with self.subTest(credential=credential.hex()):
                helper = enroll(REFERENCE, credential, enrollment_id="test-device")
                codeword = bits(encode(int.from_bytes(credential, "big") << 4), 63)
                self.assertEqual(helper.helper_bits,
                                 tuple(a ^ b for a, b in zip(REFERENCE[:63], codeword)))
                self.assertEqual(helper.config, DEFAULT_CONFIG)
                self.assertEqual(helper.enrollment_id, "test-device")

    def test_identical_response_preserves_credential_patterns(self):
        credentials = CREDENTIALS + (bytes.fromhex("00120000"), bytes.fromhex("a500a500"))
        for credential in credentials:
            with self.subTest(credential=credential.hex()):
                result = reconstruct(REFERENCE, enroll(REFERENCE, credential))
                self.assert_candidate_matches(result, credential, 0)
                self.assertEqual(len(result.candidate_credential), 4)

    def test_actual_layer1_zero_noise_path(self):
        pairs = generate_pairs(128, "adjacent")
        for index, credential in enumerate(CREDENTIALS):
            device = create_device(f"device-{index}", 128, 1.0,
                                   rng=make_rng(1234, index, "manufacturing"))
            reference = generate_response(device, pairs, 100.0, ReadConditions(0, 0),
                                          rng=make_rng(1234, index, "enrollment"))
            reading = generate_response(device, pairs, 100.0, ReadConditions(0, 0),
                                        rng=make_rng(1234, index, "measurement"))
            with self.subTest(device=index):
                self.assertEqual(len(reference), 64)
                self.assert_candidate_matches(reconstruct(reading, enroll(reference, credential)),
                                              credential, 0)

    def test_every_single_bit_position_across_five_credentials(self):
        for credential in CREDENTIALS:
            helper = enroll(REFERENCE, credential)
            for index in range(63):
                with self.subTest(credential=credential.hex(), index=index):
                    self.assert_candidate_matches(reconstruct(flip(REFERENCE, (index,)), helper),
                                                  credential, 1)

    def test_all_1953_two_bit_patterns(self):
        credential = bytes.fromhex("12345678")
        helper = enroll(REFERENCE, credential)
        for mask in combinations(range(63), 2):
            with self.subTest(mask=mask):
                self.assert_candidate_matches(reconstruct(flip(REFERENCE, mask), helper),
                                              credential, 2)

    def test_seeded_three_four_five_bit_errors_across_credentials(self):
        rng = random.Random(20260922)
        for credential in CREDENTIALS:
            helper = enroll(REFERENCE, credential)
            for weight in (3, 4, 5):
                for _ in range(50):
                    mask = tuple(sorted(rng.sample(range(63), weight)))
                    with self.subTest(credential=credential.hex(), mask=mask):
                        self.assert_candidate_matches(reconstruct(flip(REFERENCE, mask), helper),
                                                      credential, weight)

    def test_fixed_subset_and_omitted_bit(self):
        self.assertEqual(DEFAULT_CONFIG.response_indices, tuple(range(63)))
        credential = bytes.fromhex("01230000")
        helper = enroll(REFERENCE, credential)
        changed = flip(REFERENCE, (63,))
        self.assertEqual(helper, enroll(changed, credential))
        self.assertEqual(reconstruct(REFERENCE, helper), reconstruct(changed, helper))
        for index in range(63):
            with self.subTest(index=index):
                changed_helper = enroll(flip(REFERENCE, (index,)), credential)
                self.assertEqual(changed_helper.helper_bits, flip(helper.helper_bits, (index,)))

    def test_six_error_valid_padding_miscorrection_fixture(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/bch63_vectors.json").read_text())
        example = fixture["six_error_miscorrection"]
        credential = bytes.fromhex(example["enrolled_credential_hex"])
        response = flip(REFERENCE, example["flipped_indices"])
        result = reconstruct(response, enroll(REFERENCE, credential))
        self.assertEqual(sum(a != b for a, b in zip(response, REFERENCE)), 6)
        self.assertEqual(result.outcome, "candidate_valid_format")
        self.assertEqual(result.reported_correction_count, 5)
        self.assertTrue(result.padding_valid)
        self.assertEqual(result.candidate_credential.hex(), example["candidate_credential_hex"])
        self.assertNotEqual(result.candidate_credential, credential)

    def test_six_error_miscorrection_with_invalid_padding(self):
        wrong_codeword = bits(encode(1), 63)  # message ends in 0001
        support = tuple(i for i, bit in enumerate(wrong_codeword) if bit)
        self.assertEqual(len(support), 11)
        result = reconstruct(flip(REFERENCE, support[:6]), enroll(REFERENCE, bytes(4)))
        self.assertEqual(result.outcome, "invalid_format_or_padding")
        self.assertEqual(result.decoder_status, "decoded")
        self.assertEqual(result.reported_correction_count, 5)
        self.assertEqual(result.candidate_message, bits(1, 36))
        self.assertIsNone(result.candidate_credential)
        self.assertFalse(result.padding_valid)
        self.assertEqual(result.failure_reason, "nonzero_padding")

    def test_nonzero_padding_rejected_even_for_valid_codewords(self):
        helper = enroll((0,) * 64, bytes(4))
        for padding in range(1, 16):
            message = (0x12345678 << 4) | padding
            with self.subTest(padding=padding):
                result = reconstruct(bits(encode(message), 63) + (0,), helper)
                self.assertEqual(result.outcome, "invalid_format_or_padding")
                self.assertEqual(result.reported_correction_count, 0)
                self.assertEqual(result.candidate_message, bits(message, 36))
                self.assertIsNone(result.candidate_credential)

    def test_declared_failure_is_a_single_attempt_without_candidate(self):
        helper = enroll(REFERENCE, CREDENTIALS[2])
        failure = BCHDecodeResult("uncorrectable", -1, None, None, "decoder_declared_failure")
        with patch.object(BCHCodec, "decode", return_value=failure) as decode:
            result = reconstruct(REFERENCE, helper)
        decode.assert_called_once()
        self.assertEqual(result.outcome, "decoder_failure")
        self.assertEqual(result.decoder_status, "uncorrectable")
        self.assertEqual(result.reported_correction_count, -1)
        self.assertIsNone(result.candidate_message)
        self.assertIsNone(result.candidate_credential)
        self.assertIsNone(result.padding_valid)

    def test_unexpected_backend_failure_is_not_false_rejection(self):
        helper = enroll(REFERENCE, CREDENTIALS[2])
        with patch.object(BCHCodec, "decode", side_effect=RuntimeError("backend bug")) as decode:
            with self.assertRaisesRegex(RuntimeError, "backend bug"):
                reconstruct(REFERENCE, helper)
        decode.assert_called_once()

    def test_response_validation_for_both_apis(self):
        helper = enroll(REFERENCE, bytes(4))
        invalid = [None, list(REFERENCE), "0" * 64, (0,) * 63, (0,) * 65, ()]
        invalid += [(0,) * 63 + (value,) for value in (2, -1, True, False, 0.0, "0", None)]
        with patch.object(BCHCodec, "encode", side_effect=AssertionError("encoded")), \
             patch.object(BCHCodec, "decode", side_effect=AssertionError("decoded")):
            for response in invalid:
                with self.subTest(response=response):
                    with self.assertRaises(ValueError):
                        enroll(response, bytes(4))
                    with self.assertRaises(ValueError):
                        reconstruct(response, helper)

    def test_invalid_credentials_rejected(self):
        for credential in (None, b"", bytes(3), bytes(5), 0, "1234", bytearray(4), (0,) * 32):
            with self.subTest(credential=credential), self.assertRaises(ValueError):
                enroll(REFERENCE, credential)

    def test_invalid_helper_bits_rejected(self):
        invalid = [None, [0] * 63, (0,) * 62, (0,) * 64, "0" * 63]
        invalid += [(0,) * 62 + (value,) for value in (2, -1, True, 0.0, None)]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                HelperData(value)

    def test_invalid_enrollment_identifiers_rejected_before_encoding(self):
        with patch.object(BCHCodec, "encode", side_effect=AssertionError("encoded")):
            for identifier in ("", "  ", 1, True, b"device"):
                with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                    enroll(REFERENCE, bytes(4), enrollment_id=identifier)

    def test_every_configuration_field_is_fixed(self):
        for field in fields(DEFAULT_CONFIG):
            original = getattr(DEFAULT_CONFIG, field.name)
            changed = (not original if type(original) is bool else
                       original + 1 if type(original) is int else
                       original + "-other" if type(original) is str else original + (1,))
            with self.subTest(field=field.name), self.assertRaises(ValueError):
                replace(DEFAULT_CONFIG, **{field.name: changed})

    def test_configuration_types_are_strict(self):
        for change in ({"response_length": 64.0}, {"systematic": 1},
                       {"response_indices": list(range(63))},
                       {"response_indices": (False,) + tuple(range(1, 63))},
                       {"padding": (False, 0, 0, 0)}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                ReconstructionConfig(**change)

    def test_wrong_config_or_helper_object_rejected(self):
        helper = enroll(REFERENCE, bytes(4))
        for config in ({}, "v1", 1):
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    enroll(REFERENCE, bytes(4), config)
                with self.assertRaises(ValueError):
                    reconstruct(REFERENCE, helper, config)
                with self.assertRaises(ValueError):
                    HelperData((0,) * 63, config)
        for invalid_helper in (None, {}, helper.helper_bits):
            with self.subTest(helper=invalid_helper), self.assertRaises(ValueError):
                reconstruct(REFERENCE, invalid_helper)

    def test_stale_config_identity_revalidated_at_api_boundary(self):
        # Emulate material restored without dataclass constructor validation.
        stale = ReconstructionConfig()
        object.__setattr__(stale, "version", "puf-snn-reconstruction-v0")
        helper = enroll(REFERENCE, bytes(4))
        with self.assertRaisesRegex(ValueError, "version"):
            reconstruct(REFERENCE, helper, stale)
        object.__setattr__(helper, "config", stale)
        with self.assertRaisesRegex(ValueError, "version"):
            reconstruct(REFERENCE, helper)

    def test_modified_helper_bit_is_correctable_not_integrity_protected(self):
        credential = CREDENTIALS[2]
        helper = enroll(REFERENCE, credential)
        changed = replace(helper, helper_bits=flip(helper.helper_bits, (20,)))
        self.assert_candidate_matches(reconstruct(REFERENCE, changed), credential, 1)

    def test_wrong_helper_can_still_produce_matching_credential(self):
        credential = CREDENTIALS[2]
        other_helper = enroll(flip(REFERENCE, (20,)), credential, enrollment_id="other")
        self.assert_candidate_matches(reconstruct(REFERENCE, other_helper), credential, 1)

    def test_routing_identity_is_not_authentication(self):
        helper = enroll(REFERENCE, CREDENTIALS[2], enrollment_id="device-A")
        changed = replace(helper, enrollment_id="device-B")
        self.assertEqual(reconstruct(REFERENCE, helper), reconstruct(REFERENCE, changed))

    def test_reproducible_outputs_and_explicit_config(self):
        credential = CREDENTIALS[2]
        first = enroll(REFERENCE, credential, ReconstructionConfig(), enrollment_id="device-A")
        second = enroll(REFERENCE, credential, ReconstructionConfig(), enrollment_id="device-A")
        reading = flip(REFERENCE, (1, 3, 62))
        self.assertEqual(first, second)
        self.assertEqual(reconstruct(reading, first), reconstruct(reading, second, DEFAULT_CONFIG))

    def test_immutable_helper_config_and_result(self):
        helper = enroll(REFERENCE, CREDENTIALS[2])
        result = reconstruct(REFERENCE, helper)
        for obj, attribute, value in ((helper, "helper_bits", (0,) * 63),
                                      (helper.config, "version", "other"),
                                      (result, "candidate_credential", bytes(4))):
            with self.subTest(attribute=attribute), self.assertRaises(FrozenInstanceError):
                setattr(obj, attribute, value)

    def test_public_helper_and_result_have_no_ground_truth_fields(self):
        helper = enroll(REFERENCE, CREDENTIALS[2])
        self.assertEqual(set(asdict(helper)), {"helper_bits", "config", "enrollment_id"})
        result = reconstruct(REFERENCE, helper)
        self.assertEqual(set(asdict(result)), {
            "outcome", "decoder_status", "reported_correction_count", "candidate_message",
            "candidate_credential", "padding_valid", "failure_reason",
        })
        self.assertEqual(set(inspect.signature(reconstruct).parameters),
                         {"noisy64", "helper_data", "config"})
        for forbidden in ("reference64", "enrolled_credential", "expected_error_count", "ground_truth"):
            with self.subTest(forbidden=forbidden), self.assertRaises(TypeError):
                reconstruct(REFERENCE, helper, **{forbidden: object()})

    def test_fresh_process_reconstructs_using_only_public_material(self):
        credential = bytes.fromhex("0000ab00")
        helper = enroll(REFERENCE, credential)
        payload = {"response": flip(REFERENCE, (0, 17, 62)),
                   "helper": asdict(helper)}
        # The child never enrolls, and receives neither credential nor reference.
        code = """
import json, sys
sys.path.insert(0, sys.argv[1])
from puf_snn.reconstruction import HelperData, ReconstructionConfig, reconstruct
data = json.load(sys.stdin)
config = data['helper']['config']
config['response_indices'] = tuple(config['response_indices'])
config['padding'] = tuple(config['padding'])
helper = HelperData(tuple(data['helper']['helper_bits']), ReconstructionConfig(**config))
result = reconstruct(tuple(data['response']), helper)
print(json.dumps({'candidate': result.candidate_credential.hex(), 'outcome': result.outcome}))
"""
        process = subprocess.run([sys.executable, "-B", "-c", code, str(ROOT / "src/python")],
                                 input=json.dumps(payload), capture_output=True,
                                 text=True, check=False)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout),
                         {"candidate": credential.hex(), "outcome": "candidate_valid_format"})

    def test_layer1_device_and_rng_streams_are_unchanged(self):
        manufacturing = make_rng(1234, 0, "manufacturing")
        enrollment = make_rng(1234, 0, "enrollment")
        measurement = make_rng(1234, 0, "measurement")
        device = create_device("isolation", 128, 1.0, rng=manufacturing)
        pairs = generate_pairs(128, "adjacent")
        reference = generate_response(device, pairs, 100.0, ReadConditions(0, 0), rng=enrollment)
        reading = generate_response(device, pairs, 100.0, ReadConditions(0, 0.1), rng=measurement)
        streams = (manufacturing, enrollment, measurement)
        states = tuple(rng.getstate() for rng in streams)
        offsets, original_device = device.manufacturing_variation, asdict(device)
        global_state = random.getstate()
        for _ in range(3):
            helper = enroll(reference, CREDENTIALS[2])
            reconstruct(reading, helper)  # No assertion of favorable noisy-PUF outcome.
        self.assertEqual(tuple(rng.getstate() for rng in streams), states)
        self.assertEqual(asdict(device), original_device)
        self.assertIs(device.manufacturing_variation, offsets)
        self.assertEqual(random.getstate(), global_state)
        untouched = random.Random()
        untouched.setstate(states[2])
        self.assertEqual(
            generate_response(device, pairs, 100.0, ReadConditions(0, 0.1), rng=measurement),
            generate_response(device, pairs, 100.0, ReadConditions(0, 0.1), rng=untouched),
        )


if __name__ == "__main__":
    unittest.main()
