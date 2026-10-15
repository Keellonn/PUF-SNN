"""Deterministic acquisition controls, not reliability measurements."""

from dataclasses import FrozenInstanceError, replace
from itertools import product
import json
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from puf_snn.auth.config import AuthConfig
from puf_snn.puf.acquisition import (
    AcquisitionConfig, MAJORITY_3, SINGLE_READ, SimulatedResponseReader,
    acquire_response, majority_vote3,
)
from puf_snn.puf.device import create_device
from puf_snn.puf.ro_puf import generate_pairs, generate_response
from puf_snn.puf.variables import ReadConditions


ROOT = Path(__file__).resolve().parents[2]
ZERO, ONE = (0,) * 64, (1,) * 64


class MajorityVoteTests(unittest.TestCase):
    def test_three_identical_responses(self):
        for response in (ZERO, ONE, (0, 1) * 32):
            self.assertEqual(majority_vote3((response,) * 3), response)

    def test_single_differing_read_in_every_position(self):
        for position in range(3):
            reads = [ZERO] * 3
            reads[position] = ONE
            self.assertEqual(majority_vote3(tuple(reads)), ZERO)

    def test_two_agreeing_reads_in_every_position(self):
        for position in range(3):
            reads = [ONE] * 3
            reads[position] = ZERO
            self.assertEqual(majority_vote3(tuple(reads)), ONE)

    def test_all_bit_truth_tables_and_week6_parity(self):
        # Experimental imports are test-only; the authentication path has none.
        from puf_snn.reconstruction_alternatives import majority_vote
        for pattern in product((0, 1), repeat=3):
            reads = tuple((bit,) * 64 for bit in pattern)
            expected = (int(sum(pattern) >= 2),) * 64
            self.assertEqual(majority_vote3(reads), expected)
            self.assertEqual(majority_vote3(reads), majority_vote(reads))

    def test_mixed_patterns_and_no_input_mutation(self):
        reads = ((0, 0, 1, 1) * 16, (0, 1, 0, 1) * 16, (1, 0, 1, 0) * 16)
        before = tuple(tuple(read) for read in reads)
        self.assertEqual(majority_vote3(reads), (0, 0, 1, 1) * 16)
        self.assertEqual(reads, before)

    def test_exactly_three_tuple_inputs_required(self):
        for reads in (None, [], [ZERO] * 3, iter((ZERO,) * 3),
                      *((ZERO,) * count for count in (0, 1, 2, 4, 5, 6))):
            with self.subTest(reads=type(reads)), self.assertRaises(ValueError):
                majority_vote3(reads)

    def test_invalid_lengths_in_each_read(self):
        for position in range(3):
            for length in (0, 1, 63, 65, 128):
                reads = [ZERO] * 3
                reads[position] = (0,) * length
                with self.subTest(position=position, length=length), self.assertRaises(ValueError):
                    majority_vote3(tuple(reads))

    def test_invalid_values_and_containers_in_each_read(self):
        for position in range(3):
            for bad in (None, list(ZERO), bytes(64),
                        *((value,) + ZERO[1:] for value in (True, False, 2, -1, 0.0, 1.0, '1', None))):
                reads = [ZERO] * 3
                reads[position] = bad
                with self.subTest(position=position, bad=type(bad)), self.assertRaises(ValueError):
                    majority_vote3(tuple(reads))


class AcquisitionTests(unittest.TestCase):
    def test_default_calls_once_and_preserves_response(self):
        read = Mock(return_value=ZERO)
        self.assertIs(acquire_response(read), ZERO)
        read.assert_called_once_with()

    def test_majority_calls_exactly_three_times(self):
        read = Mock(side_effect=(ZERO, ONE, ZERO))
        self.assertEqual(acquire_response(read, MAJORITY_3), ZERO)
        self.assertEqual(read.call_args_list, [unittest.mock.call()] * 3)

    def test_failed_or_malformed_read_aborts_without_replacement(self):
        for config in (SINGLE_READ, MAJORITY_3):
            for position in range(config.read_count):
                for bad in ((0,) * 63, (True,) + ZERO[1:], RuntimeError('test read failure')):
                    read = Mock(side_effect=[ZERO] * position + [bad] + [ONE] * 3)
                    with self.subTest(config=config, position=position), \
                            self.assertRaises((ValueError, RuntimeError)):
                        acquire_response(read, config)
                    self.assertEqual(read.call_count, position + 1)

    def test_invalid_policy_and_callback_fail_before_read(self):
        for config in (None, {}, 'majority-3-v1'):
            read = Mock(return_value=ZERO)
            with self.assertRaises(ValueError):
                acquire_response(read, config)
            read.assert_not_called()
        with self.assertRaises(ValueError):
            acquire_response(ZERO)

    def test_same_device_and_continuing_noise_stream_match_three_direct_reads(self):
        manufacturing = Random(7301)
        device = create_device('unit-device', 128, 1.0, rng=manufacturing)
        manufacturing_after = manufacturing.getstate()
        offsets = device.manufacturing_variation
        noise, control = Random(7302), Random(7302)
        conditions = ReadConditions(0, 0.25)
        pairs = generate_pairs(128, 'adjacent')
        expected_reads = tuple(generate_response(device, pairs, 100.0, conditions, rng=control)
                               for _ in range(3))
        reader = SimulatedResponseReader(device, 100.0, conditions, noise)
        with patch('puf_snn.puf.acquisition.generate_response', wraps=generate_response) as read, \
             patch.object(noise, 'gauss', wraps=noise.gauss) as gauss:
            effective = acquire_response(reader, MAJORITY_3)
        self.assertEqual(read.call_count, 3)
        self.assertEqual(gauss.call_count, 128 * 3)
        for call in read.call_args_list:
            self.assertIs(call.args[0], device)
            self.assertEqual(call.args[1], pairs)
            self.assertIs(call.args[3], conditions)
            self.assertIs(call.kwargs['rng'], noise)
        self.assertEqual(noise.getstate(), control.getstate())
        self.assertEqual(manufacturing.getstate(), manufacturing_after)
        self.assertIs(device.manufacturing_variation, offsets)
        self.assertEqual(effective, majority_vote3(expected_reads))
        self.assertGreater(len(set(expected_reads)), 1)  # Fixed nonzero-noise fixture.

    def test_zero_noise_consumes_no_random_draws(self):
        device = create_device('unit-device', 128, 1.0, rng=Random(7301))
        noise = Random(7302)
        before = noise.getstate()
        reader = SimulatedResponseReader(device, 100.0, ReadConditions(0, 0), noise)
        with patch.object(noise, 'gauss', wraps=noise.gauss) as gauss:
            effective = acquire_response(reader, MAJORITY_3)
        self.assertEqual(effective, reader())
        gauss.assert_not_called()
        self.assertEqual(noise.getstate(), before)

    def test_simulator_binding_validation_and_immutability(self):
        device = create_device('unit-device', 128, 1.0, rng=Random(7301))
        reader = SimulatedResponseReader(device, 100.0, ReadConditions(0, 0), Random(7302))
        for changes in ({'device': None}, {'device': replace(device, manufacturing_variation=(0.,) * 64)},
                        {'rng': None}, {'conditions': None}, {'nominal_frequency': 0},
                        {'nominal_frequency': float('nan')}):
            with self.assertRaises(ValueError):
                replace(reader, **changes)
        with self.assertRaises(FrozenInstanceError):
            reader.device = device


class AcquisitionConfigTests(unittest.TestCase):
    def test_default_and_candidate_identity_round_trip(self):
        self.assertEqual(AcquisitionConfig(), SINGLE_READ)
        self.assertEqual((SINGLE_READ.policy, SINGLE_READ.read_count), ('single-read-v1', 1))
        path = ROOT / 'configs/authentication_v2_majority3_acquisition.json'
        self.assertEqual(AcquisitionConfig.load(path), MAJORITY_3)
        self.assertEqual(AcquisitionConfig.from_dict(MAJORITY_3.to_dict()), MAJORITY_3)
        self.assertEqual(set(MAJORITY_3.to_dict()), {'config_version', 'policy', 'read_count'})

    def test_unsupported_or_inconsistent_fields_rejected(self):
        for changes in ({'config_version': 'v2'}, {'policy': 'majority-5-v1', 'read_count': 5},
                        {'policy': 'majority-3-v1'}, {'read_count': 3}, {'policy': None},
                        {'policy': []}, {'read_count': True}, {'read_count': 1.0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                AcquisitionConfig(**changes)

    def test_missing_extra_and_duplicate_json_keys_rejected(self):
        for obj in (None, [], {}, {'policy': 'majority-3-v1'},
                    dict(MAJORITY_3.to_dict(), retry=True)):
            with self.assertRaises(ValueError):
                AcquisitionConfig.from_dict(obj)
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'invalid.json'
            path.write_text(json.dumps(MAJORITY_3.to_dict())[:-1] + ', "read_count": 3}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                AcquisitionConfig.load(path)

    def test_authentication_schema_stays_separate_and_strict(self):
        baseline = AuthConfig.load(ROOT / 'configs/authentication_v2.json')
        self.assertEqual(baseline, AuthConfig())
        with self.assertRaises(ValueError):
            AuthConfig.from_dict(dict(baseline.to_dict(), acquisition=MAJORITY_3.to_dict()))
        with self.assertRaises(ValueError):
            AuthConfig.load(ROOT / 'configs/authentication_v2_majority3_acquisition.json')


if __name__ == '__main__':
    unittest.main()
