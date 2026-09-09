from dataclasses import replace
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "python"))

from scripts.run_puf_baseline import make_rng
from puf_snn.puf.device import Device, create_device
from puf_snn.puf.ro_puf import (
    calculate_frequencies,
    compare_oscillators,
    generate_pairs,
    generate_response,
)
from puf_snn.puf.variables import ReadConditions, load_config

CONFIG_PATH = ROOT / "configs" / "puf_baseline.json"

class ConfigurationTests(unittest.TestCase):
    def test_default_configuration(self) -> None:
        config = load_config(CONFIG_PATH)
        self.assertEqual(config.number_of_oscillators, 128)
        self.assertEqual(config.pairing_scheme, "adjacent")
        self.assertEqual(config.reference_conditions.measurement_noise_std, 0)

    def test_invalid_parameters(self) -> None:
        config = load_config(CONFIG_PATH)
        for changes in (
            {"number_of_devices": 1}, {"number_of_oscillators": 127},
            {"pairing_scheme": "unknown"}, {"nominal_frequency": 0},
            {"manufacturing_std": -1}, {"aging_std": 0.1},
            {"repeated_reads": True}, {"random_seed": -1},
            {"noise_sweep": ()}, {"noise_sweep": (float("inf"),)},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    replace(config, **changes)

    def test_read_conditions(self) -> None:
        self.assertEqual(ReadConditions(-0.5, 0).environmental_offset, -0.5)
        for offset, noise in ((float("nan"), 0), (0, -1), (0, True)):
            with self.subTest(offset=offset, noise=noise):
                with self.assertRaises(ValueError):
                    ReadConditions(offset, noise)

    def test_configuration_rejects_schema_errors(self) -> None:
        original = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        missing = dict(original)
        del missing["random_seed"]
        invalid_nested = dict(original, read_conditions={"noise": 0})
        for data in (missing, dict(original, typo=1), invalid_nested,
                     dict(original, noise_sweep="0.1")):
            with self.subTest(data=data), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "invalid.json"
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_config(path)

    def test_duplicate_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"random_seed": 1, "random_seed": 2}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                load_config(path)

class RandomnessTests(unittest.TestCase):
    def test_streams_reproduce_and_advance(self) -> None:
        first = make_rng(1234, 0, "measurement")
        second = make_rng(1234, 0, "measurement")
        values = [first.random() for _ in range(5)]
        self.assertEqual(values, [second.random() for _ in range(5)])
        self.assertGreater(len(set(values)), 1)

    def test_devices_and_phases_have_distinct_streams(self) -> None:
        values = [make_rng(1234, device, phase).random()
                  for device in (0, 1)
                  for phase in ("manufacturing", "enrollment", "measurement")]
        self.assertEqual(len(set(values)), 6)

    def test_measurement_consumption_does_not_change_manufacturing(self) -> None:
        manufacturing = make_rng(1234, 0, "manufacturing")
        expected = make_rng(1234, 0, "manufacturing")
        reading = make_rng(1234, 0, "measurement")
        for _ in range(100):
            reading.random()
        self.assertEqual(manufacturing.random(), expected.random())

    def test_no_global_random_state_is_consumed(self) -> None:
        before = random.getstate()
        make_rng(1234, 0, "measurement").random()
        self.assertEqual(random.getstate(), before)

    def test_invalid_stream_labels(self) -> None:
        for seed, index, phase in ((-1, 0, "measurement"),
                                   (1, True, "measurement"), (1, 0, "unknown")):
            with self.subTest(seed=seed, index=index, phase=phase):
                with self.assertRaises(ValueError):
                    make_rng(seed, index, phase)

class PairingTests(unittest.TestCase):
    def test_adjacent_pair_order_and_response_length(self) -> None:
        pairs = generate_pairs(128, "adjacent")
        self.assertEqual(pairs, tuple((i, i + 1) for i in range(0, 128, 2)))
        response = compare_oscillators(tuple(range(128)), pairs)
        self.assertEqual(len(response), 64)
        self.assertEqual(response, (0,) * 64)
        self.assertEqual(len({index for pair in pairs for index in pair}), 128)

    def test_all_pairs_order_and_count(self) -> None:
        self.assertEqual(generate_pairs(3, "all_pairs"),
                         ((0, 1), (0, 2), (1, 2)))
        pairs = generate_pairs(128, "all_pairs")
        self.assertEqual(len(pairs), 8128)
        self.assertEqual(len(set(pairs)), 8128)
        self.assertTrue(all(0 <= first < second < 128
                            for first, second in pairs))
        response = compare_oscillators(tuple(range(128)), pairs)
        self.assertEqual(len(response), 8128)

    def test_invalid_pair_configuration(self) -> None:
        for count, scheme in ((1, "adjacent"), (True, "adjacent"),
                              (4.0, "adjacent"), (3, "adjacent"),
                              (4, "unknown")):
            with self.subTest(count=count, scheme=scheme):
                with self.assertRaises(ValueError):
                    generate_pairs(count, scheme)

    def test_comparison_rule_ties_and_custom_reuse(self) -> None:
        response = compare_oscillators(
            (3.0, 2.0, 2.0), ((0, 1), (1, 0), (1, 2), (0, 2), (0, 1))
        )
        self.assertEqual(response, (1, 0, 0, 1, 1))
        self.assertTrue(all(type(bit) is int for bit in response))

    def test_invalid_indices_and_pair_shapes(self) -> None:
        for pairs in ((), ((0, 0),), ((-1, 1),), ((0, 2),),
                      ((0.0, 1),), ((False, 1),), ((0,),),
                      ((0, 1, 2),), (None,), [(0, 1)]):
            with self.subTest(pairs=pairs):
                with self.assertRaises(ValueError):
                    compare_oscillators((1.0, 2.0), pairs)

    def test_invalid_frequencies(self) -> None:
        for frequencies in ((), (1.0,), [1.0, 2.0], (True, 1.0),
                            ("1", 2), (float("nan"), 2), (1, float("inf"))):
            with self.subTest(frequencies=frequencies):
                with self.assertRaises(ValueError):
                    compare_oscillators(frequencies, ((0, 1),))

class FrequencyModelTests(unittest.TestCase):
    def test_additive_environment_and_zero_aging(self) -> None:
        device = Device("d", (1.0, -2.0, 0.5, -0.5), (0.0,) * 4)
        rng = make_rng(1234, 0, "measurement")
        baseline = calculate_frequencies(device, 100, ReadConditions(0, 0),
                                         rng=rng)
        shifted = calculate_frequencies(device, 100, ReadConditions(-3, 0),
                                        rng=rng)
        self.assertEqual(baseline, (101.0, 98.0, 100.5, 99.5))
        self.assertEqual(shifted, tuple(value - 3 for value in baseline))
        pairs = generate_pairs(4, "adjacent")
        self.assertEqual(compare_oscillators(baseline, pairs),
                         compare_oscillators(shifted, pairs))

    def test_nonzero_aging_rejected_without_consuming_noise(self) -> None:
        rng = make_rng(1234, 0, "measurement")
        before = rng.getstate()
        with self.assertRaisesRegex(ValueError, "aging_state"):
            calculate_frequencies(Device("d", (1.0, -1.0), (0.1, 0.0)),
                                  100, ReadConditions(0, 1), rng=rng)
        self.assertEqual(rng.getstate(), before)

    def test_noiseless_reads_match_reference_without_rng_draws(self) -> None:
        config = load_config(CONFIG_PATH)
        device = create_device(
            "d", config.number_of_oscillators, config.manufacturing_std,
            rng=make_rng(config.random_seed, 0, "manufacturing")
        )
        pairs = generate_pairs(config.number_of_oscillators,
                               config.pairing_scheme)
        reference = generate_response(
            device, pairs, config.nominal_frequency,
            config.reference_conditions,
            rng=make_rng(config.random_seed, 0, "enrollment")
        )
        rng = make_rng(config.random_seed, 0, "measurement")
        before = rng.getstate()
        for _ in range(20):
            self.assertEqual(generate_response(
                device, pairs, config.nominal_frequency,
                ReadConditions(0, 0), rng=rng
            ), reference)
        self.assertEqual(rng.getstate(), before)
        self.assertEqual(set(reference), {0, 1})

    def test_noise_changes_frequencies_and_responses(self) -> None:
        # Tied noiseless ROs expose read noise directly, avoiding an assertion
        # that every nonzero noise level must flip a well-separated pair.
        device = Device("d", (0.0,) * 128)
        pairs = generate_pairs(128, "adjacent")
        rng = make_rng(1234, 0, "measurement")
        frequencies = [calculate_frequencies(device, 100, ReadConditions(0, 1),
                                             rng=rng) for _ in range(5)]
        self.assertEqual(len(set(frequencies)), 5)
        responses = [compare_oscillators(values, pairs)
                     for values in frequencies]
        self.assertEqual(len(set(responses)), 5)
        self.assertTrue(all(set(response) <= {0, 1} for response in responses))

    def test_seed_reproduces_devices_enrollment_and_read_sequence(self) -> None:
        def simulate() -> list[tuple]:
            records = []
            for index in range(3):
                device = create_device(
                    f"d-{index}", 128, 1,
                    rng=make_rng(1234, index, "manufacturing")
                )
                pairs = generate_pairs(128, "adjacent")
                # Nonzero reference noise must also be reproducible and honored.
                reference = generate_response(
                    device, pairs, 100, ReadConditions(0, 0.2),
                    rng=make_rng(1234, index, "enrollment")
                )
                rng = make_rng(1234, index, "measurement")
                reads = [generate_response(device, pairs, 100,
                                           ReadConditions(0.5, 1), rng=rng)
                         for _ in range(5)]
                records.append((device, reference, reads))
            return records

        global_state = random.getstate()
        self.assertEqual(simulate(), simulate())
        self.assertEqual(random.getstate(), global_state)

    def test_reference_conditions_honor_nonzero_noise(self) -> None:
        device = Device("d", (0.0,) * 128)
        pairs = generate_pairs(128, "adjacent")
        rng = make_rng(1234, 0, "enrollment")
        reference = generate_response(device, pairs, 100, ReadConditions(0, 1),
                                      rng=rng)
        self.assertEqual(set(reference), {0, 1})
        self.assertNotEqual(reference, (0,) * len(pairs))

    def test_invalid_frequency_arguments(self) -> None:
        device = Device("d", (0.0, 1.0))
        for nominal in (0, -1, True, float("nan"), float("inf"), "100"):
            with self.subTest(nominal=nominal):
                with self.assertRaises(ValueError):
                    calculate_frequencies(device, nominal, ReadConditions(0, 0),
                                          rng=random.Random(1))
        for subject, conditions, rng in (
            (None, ReadConditions(0, 0), random.Random(1)),
            (device, None, random.Random(1)),
            (device, ReadConditions(0, 0), None),
        ):
            with self.assertRaises(ValueError):
                calculate_frequencies(subject, 100, conditions, rng=rng)

    def test_overflow_and_negative_abstract_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            calculate_frequencies(Device("d", (1e308, 0.0)), 1e308,
                                  ReadConditions(0, 0), rng=random.Random(1))
        self.assertEqual(calculate_frequencies(
            Device("d", (-3.0, -2.0)), 1, ReadConditions(0, 0),
            rng=random.Random(1)
        ), (-2.0, -1.0))

    def test_invalid_response_pairs_do_not_consume_noise(self) -> None:
        rng = make_rng(1234, 0, "measurement")
        before = rng.getstate()
        with self.assertRaises(ValueError):
            generate_response(Device("d", (0.0, 1.0)), ((0, 2),), 100,
                              ReadConditions(0, 1), rng=rng)
        self.assertEqual(rng.getstate(), before)

    def test_noise_scale_and_environment_are_separate_terms(self) -> None:
        device = Device("d", (1.0, -1.0, 0.5, -0.5))
        # Matched RNG streams isolate the controlled terms: doubling sigma
        # doubles the noise residual; shifting environment adds a fixed amount.
        baseline = calculate_frequencies(
            device, 100, ReadConditions(0, 0), rng=random.Random(1)
        )
        first = calculate_frequencies(
            device, 100, ReadConditions(0, 1), rng=random.Random(1)
        )
        second = calculate_frequencies(
            device, 100, ReadConditions(3, 2), rng=random.Random(1)
        )
        for fixed, noisy, shifted in zip(baseline, first, second):
            self.assertAlmostEqual(shifted - fixed - 3, 2 * (noisy - fixed))
