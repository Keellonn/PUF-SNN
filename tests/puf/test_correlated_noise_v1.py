"""Deterministic model/algebra and real acquisition controls, not FRR trials.

Any credentials/keys below are public unit fixtures used through real admission.
The finite sign fixtures prove second-moment algebra; they are not Gaussian
Monte Carlo estimates or synthetic reliability results.
"""

from dataclasses import FrozenInstanceError, replace
from fractions import Fraction
from hashlib import sha256
from itertools import product
import random
import unittest
from unittest.mock import Mock, patch

from puf_snn.experiments import correlated_noise_v1 as noise
from puf_snn.puf.acquisition import MAJORITY_3, SINGLE_READ, acquire_response, majority_vote3
from puf_snn.puf.device import Device, create_device
from puf_snn.puf.ro_puf import calculate_frequencies, generate_response
from puf_snn.puf.variables import ReadConditions


IDENTITY = noise.AttemptIdentity(7301, "unit-population", "sim-device", "nominal", 0)
CONFIG = noise.NoiseConfig(noise.MODEL_VERSION, 128, 0.25, 0.36, 0.0)
ZERO = (0,) * 64
ZEROS = (0.0,) * 128
DEVICE = Device(IDENTITY.device_id, (-1.0, 1.0) * 64)


def fixture_measure(config, z, e, *, device=DEVICE, index=0):
    """Inject exact unit disturbances while running the real frequency loop."""
    shared = noise.SharedDisturbance(IDENTITY, z)
    values = iter(e)
    with patch.object(random.Random, "gauss", side_effect=lambda mu, sd: mu + sd * next(values)):
        return noise.measure_indexed(device, config, IDENTITY, shared, index)


def measured(config=CONFIG, identity=IDENTITY, *, device=DEVICE, index=0):
    return noise.measure_indexed(device, config, identity,
                                 noise.generate_shared_disturbance(identity), index)


class ConfigurationTests(unittest.TestCase):
    def test_complete_strict_round_trip(self):
        self.assertEqual(noise.NoiseConfig.from_dict(CONFIG.to_dict()), CONFIG)
        for obj in (None, [], {}, dict(CONFIG.to_dict(), policy="B0")):
            with self.subTest(obj=obj), self.assertRaisesRegex(ValueError, "exactly"):
                noise.NoiseConfig.from_dict(obj)
        for key in CONFIG.to_dict():
            obj = CONFIG.to_dict()
            del obj[key]
            with self.assertRaises(ValueError):
                noise.NoiseConfig.from_dict(obj)
        with self.assertRaises(TypeError):
            noise.NoiseConfig(sigma=0, rho=0)

    def test_invalid_magnitudes_and_types(self):
        for name in ("sigma", "rho", "common_offset"):
            for value in (True, False, None, "0", [], float("nan"), float("inf"),
                          -float("inf"), 10**400):
                with self.subTest(name=name, value=type(value)), self.assertRaisesRegex(ValueError, name):
                    replace(CONFIG, **{name: value})
        for changes in ({"sigma": -0.1}, {"rho": -0.1}, {"rho": 1.01}):
            with self.assertRaises(ValueError):
                replace(CONFIG, **changes)
        self.assertEqual(replace(CONFIG, common_offset=-12).common_offset, -12)

    def test_invalid_profile_counts_and_versions(self):
        for count in (0, 1, 2, 64, 127, 129, 256, 128.0, True, None):
            with self.assertRaisesRegex(ValueError, "128"):
                replace(CONFIG, oscillator_count=count)
        for version in (None, [], True, "v2", ""):
            with self.assertRaisesRegex(ValueError, "model_version"):
                replace(CONFIG, model_version=version)
            with self.assertRaisesRegex(ValueError, "model_version"):
                replace(IDENTITY, model_version=version)

    def test_invalid_identities(self):
        for name in ("master_seed", "attempt_id"):
            for value in (-1, True, 0.0, "0", None):
                with self.assertRaisesRegex(ValueError, name):
                    replace(IDENTITY, **{name: value})
        for name in ("population_id", "device_id", "noise_domain_id"):
            for value in (None, [], 1, "", " ", " trailing ", "a\nb", "\ud800"):
                with self.assertRaisesRegex(ValueError, name):
                    replace(IDENTITY, **{name: value})

    def test_shared_vector_validation(self):
        for vector in ([], list(ZEROS), (), ZEROS[:-1], ZEROS + (0.0,),
                       (True,) + ZEROS[1:], (float("nan"),) + ZEROS[1:]):
            with self.assertRaises(ValueError):
                noise.SharedDisturbance(IDENTITY, vector)
        with self.assertRaises(ValueError):
            noise.SharedDisturbance(None, ZEROS)

    def test_configuration_identity_and_shared_state_are_immutable(self):
        shared = noise.generate_shared_disturbance(IDENTITY)
        for obj, name, value in ((CONFIG, "sigma", 3), (IDENTITY, "attempt_id", 2),
                                 (shared, "standard_normals", ZEROS)):
            with self.assertRaises(FrozenInstanceError):
                setattr(obj, name, value)
        with self.assertRaises(TypeError):
            shared.standard_normals[0] = 0


class SeedTests(unittest.TestCase):
    def test_canonical_serialization_and_sha256_conversion_golden(self):
        expected = (b'{"attempt_id":0,"device_id":"sim-device",'
                    b'"domain":"independent-reading","master_seed":7301,'
                    b'"model_version":"puf-snn-correlated-noise-v1",'
                    b'"noise_domain_id":"nominal","population_id":"unit-population",'
                    b'"reading_index":0}')
        self.assertEqual(noise.canonical_seed_bytes(IDENTITY, noise.READING, 0), expected)
        self.assertEqual(noise.derive_seed(IDENTITY, noise.READING, 0),
                         int.from_bytes(sha256(expected).digest(), "big"))
        session = expected.replace(b'"domain":"independent-reading"',
                                   b'"domain":"session-correlated-oscillator"')
        session = session.replace(b',"reading_index":0', b'')
        self.assertEqual(noise.canonical_seed_bytes(IDENTITY, noise.SESSION), session)

    def test_unicode_is_escaped_without_normalization(self):
        first = replace(IDENTITY, population_id="caf\u00e9")
        second = replace(IDENTITY, population_id="cafe\u0301")
        self.assertIn(b'caf\\u00e9', noise.canonical_seed_bytes(first, noise.SESSION))
        self.assertNotEqual(noise.derive_seed(first, noise.SESSION),
                            noise.derive_seed(second, noise.SESSION))

    def test_six_domains_and_indices_are_separate(self):
        seeds = [noise.derive_seed(IDENTITY, domain) for domain in noise.RNG_DOMAINS
                 if domain != noise.READING]
        seeds += [noise.derive_seed(IDENTITY, noise.READING, index) for index in range(3)]
        self.assertEqual(len(seeds), 8)
        self.assertEqual(len(set(seeds)), 8)
        self.assertTrue(all(type(seed) is int and 0 <= seed < 2**256 for seed in seeds))

    def test_all_trial_identity_fields_participate(self):
        for changes in ({"master_seed": 7302}, {"population_id": "other-population"},
                        {"device_id": "other-device"}, {"noise_domain_id": "other-condition"},
                        {"attempt_id": 1}):
            other = replace(IDENTITY, **changes)
            for domain, index in ((noise.SESSION, None), (noise.READING, 0),
                                  (noise.COMMON_MODE, None), (noise.ENROLLMENT, None)):
                self.assertNotEqual(noise.derive_seed(IDENTITY, domain, index),
                                    noise.derive_seed(other, domain, index))

    def test_invalid_domains_and_indices(self):
        for domain in (None, [], "policy-B0", "unknown"):
            with self.assertRaisesRegex(ValueError, "domain"):
                noise.derive_seed(IDENTITY, domain)
        for index in (None, -1, 3, True, 0.0, "0"):
            with self.assertRaisesRegex(ValueError, "reading_index"):
                noise.derive_seed(IDENTITY, noise.READING, index)
        for domain in noise.RNG_DOMAINS:
            if domain != noise.READING:
                with self.assertRaisesRegex(ValueError, "only valid"):
                    noise.derive_seed(IDENTITY, domain, 0)
        with self.assertRaisesRegex(ValueError, "AttemptIdentity"):
            noise.derive_seed(None, noise.SESSION)

    def test_external_manufacturing_and_enrollment_are_explicit(self):
        # API example only: stable lifecycle identities are supplied by a future
        # planner. The reader never manufactures or enrolls anything itself.
        manufacture = replace(IDENTITY, noise_domain_id="manufacture-v1", attempt_id=0)
        enrollment = replace(IDENTITY, noise_domain_id="enrollment-fixture-1", attempt_id=0)
        device = create_device(IDENTITY.device_id, 128, 1,
                               rng=random.Random(noise.derive_seed(manufacture, noise.MANUFACTURING)))
        reference = generate_response(device, noise.PAIRS, 100, ReadConditions(0, 0),
                                      rng=random.Random(noise.derive_seed(enrollment, noise.ENROLLMENT)))
        reader = noise.CorrelatedResponseReader(device, replace(CONFIG, sigma=0), IDENTITY)
        self.assertEqual(reader(), reference)
        self.assertEqual(reader.identity, IDENTITY)


class EquationTests(unittest.TestCase):
    def test_rho_zero_removes_shared_component(self):
        config = replace(CONFIG, sigma=5, rho=0)
        first = fixture_measure(config, (99.0, -99.0) * 64, (1.0, -1.0) * 64)
        other = fixture_measure(config, ZEROS, (1.0, -1.0) * 64)
        self.assertEqual(first.shared_noise, ZEROS)
        self.assertEqual(first, other)
        self.assertEqual(first.independent_noise, (5.0, -5.0) * 64)

    def test_rho_one_removes_independent_component_but_measures_three_times(self):
        reader = noise.CorrelatedResponseReader(DEVICE, replace(CONFIG, rho=1), IDENTITY, MAJORITY_3)
        with patch.object(random.Random, "gauss", side_effect=AssertionError("no independent draw")), \
             patch.object(noise, "calculate_frequencies", wraps=calculate_frequencies) as calculate:
            reads = tuple(reader() for _ in range(3))
        self.assertEqual(calculate.call_count, 3)
        self.assertEqual(reads, (reads[0],) * 3)
        self.assertEqual(majority_vote3(reads), reads[0])
        self.assertEqual(measured(replace(CONFIG, rho=1)).independent_noise, ZEROS)

    def test_sigma_zero_noiseless_ties_and_no_read_draws(self):
        tie_device = Device(IDENTITY.device_id, ZEROS)
        for rho in (0, 0.36, 1):
            shared = noise.generate_shared_disturbance(IDENTITY)
            with patch.object(random.Random, "gauss", side_effect=AssertionError("no read draw")):
                result = noise.measure_indexed(tie_device, replace(CONFIG, sigma=0, rho=rho),
                                               IDENTITY, shared, 0)
            self.assertEqual(result.response, ZERO)
            self.assertEqual(result.frequencies, (100.0,) * 128)
            self.assertEqual(result.shared_noise, ZEROS)
            self.assertEqual(result.independent_noise, ZEROS)

    def test_component_scaling_and_pair_difference_equation(self):
        config = replace(CONFIG, sigma=5, rho=0.36, common_offset=8)
        z, e = (2.0, -1.0) * 64, (-1.0, 2.0) * 64
        result = fixture_measure(config, z, e)
        self.assertEqual((config.shared_std, config.independent_std), (3.0, 4.0))
        self.assertEqual(result.shared_noise, (6.0, -3.0) * 64)
        self.assertEqual(result.independent_noise, (-4.0, 8.0) * 64)
        self.assertEqual(result.frequencies, (109.0, 114.0) * 64)
        for u, v in noise.PAIRS:
            expected = (DEVICE.manufacturing_variation[u] - DEVICE.manufacturing_variation[v]
                        + 3 * (z[u] - z[v]) + 4 * (e[u] - e[v]))
            self.assertEqual(result.frequencies[u] - result.frequencies[v], expected)

    def test_exact_finite_second_moment_algebra_across_rho(self):
        # Six independent +/-1 coordinates form an exhaustive orthogonal fixture.
        # They have exact unit variance and zero cross moments. These moments,
        # not the distribution's shape, determine the approved covariance.
        device = Device(IDENTITY.device_id, ZEROS)
        for rho in (0, 0.1, 0.36, 0.75, 1):
            config = replace(CONFIG, sigma=5, rho=rho)
            rows = []
            for zu, zv, e0u, e0v, e1u, e1v in product((-1.0, 1.0), repeat=6):
                z = (zu, zv) + ZEROS[2:]
                a = fixture_measure(config, z, (e0u, e0v) + ZEROS[2:], device=device, index=0)
                b = fixture_measure(config, z, (e1u, e1v) + ZEROS[2:], device=device, index=1)
                na = tuple(s + e for s, e in zip(a.shared_noise, a.independent_noise))
                nb = tuple(s + e for s, e in zip(b.shared_noise, b.independent_noise))
                da, db = na[0] - na[1], nb[0] - nb[1]
                self.assertAlmostEqual(a.frequencies[0] - a.frequencies[1], da)
                rows.append((na[0], nb[0], da, db))
            mean = lambda values: sum(values) / len(rows)
            with self.subTest(rho=rho):
                self.assertAlmostEqual(mean(a for a, _, _, _ in rows), 0)
                self.assertAlmostEqual(mean(a*a for a, _, _, _ in rows), 25)
                self.assertAlmostEqual(mean(a*b for a, b, _, _ in rows), 25*rho)
                self.assertAlmostEqual(mean(d*d for _, _, d, _ in rows), 50)
                self.assertAlmostEqual(mean(d*f for _, _, d, f in rows), 50*rho)
                self.assertAlmostEqual(mean(d*f for _, _, d, f in rows) / 50, rho)
                self.assertAlmostEqual(config.shared_std**2 + config.independent_std**2, 25)

    def test_near_margin_shared_disturbance_flips_comparison(self):
        device = Device(IDENTITY.device_id, (0.125, 0.0) + ZEROS[2:])
        config = replace(CONFIG, sigma=0.25, rho=1)
        nominal = fixture_measure(config, ZEROS, ZEROS, device=device)
        changed = fixture_measure(config, (-1.0, 1.0) + ZEROS[2:], ZEROS, device=device)
        self.assertEqual((nominal.response[0], changed.response[0]), (1, 0))
        self.assertEqual(changed.frequencies[0] - changed.frequencies[1], -0.375)

    def test_same_shared_vector_persists_and_next_attempt_has_own_state(self):
        shared = noise.generate_shared_disturbance(IDENTITY)
        expected_rng = random.Random(noise.derive_seed(IDENTITY, noise.SESSION))
        self.assertEqual(shared.standard_normals, tuple(expected_rng.gauss(0, 1) for _ in range(128)))
        reads = [noise.measure_indexed(DEVICE, CONFIG, IDENTITY, shared, i) for i in range(3)]
        self.assertTrue(all(r.shared_noise == reads[0].shared_noise for r in reads))
        self.assertEqual(len({r.independent_noise for r in reads}), 3)
        next_state = noise.generate_shared_disturbance(replace(IDENTITY, attempt_id=1))
        self.assertNotEqual(shared.standard_normals, next_state.standard_normals)
        self.assertEqual(shared, noise.generate_shared_disturbance(IDENTITY))


class CommonModeTests(unittest.TestCase):
    def test_exact_rational_cancellation(self):
        # Includes magnitudes at which binary64 cannot retain small differences.
        for common in (Fraction(0), Fraction(1, 7), Fraction(10**30)):
            first, second = Fraction(17, 13), Fraction(-5, 11)
            self.assertEqual((first + common) - (second + common), first - second)

    def test_control_explicitly_aliases_components_and_responses(self):
        for rho in (0, 0.36, 1):
            nominal = replace(CONFIG, sigma=5, rho=rho)
            control = noise.common_mode_control(nominal, 8)
            self.assertEqual(replace(control, common_offset=0), nominal)
            for i in range(3):
                first = measured(nominal, index=i)
                second = measured(control, index=i)
                self.assertEqual(first.shared_noise, second.shared_noise)
                self.assertEqual(first.independent_noise, second.independent_noise)
                self.assertEqual(first.response, second.response)
                for u, v in noise.PAIRS:
                    self.assertAlmostEqual(first.frequencies[u] - first.frequencies[v],
                                           second.frequencies[u] - second.frequencies[v], places=12)

    def test_binary_exact_fixture_cancels_without_roundoff(self):
        first = fixture_measure(replace(CONFIG, sigma=5), (2.0, -1.0)*64, (-1.0, 2.0)*64)
        other = fixture_measure(noise.common_mode_control(replace(CONFIG, sigma=5), -8),
                                (2.0, -1.0)*64, (-1.0, 2.0)*64)
        self.assertEqual(tuple(f - g for f, g in zip(first.frequencies, other.frequencies)),
                         (8.0,)*128)
        self.assertEqual(first.response, other.response)

    def test_roundoff_comparison_collapse_is_reported_not_a_physical_effect(self):
        device = Device(IDENTITY.device_id, (0.125, 0.0) + ZEROS[2:])
        config = replace(CONFIG, sigma=0, common_offset=1e20)
        self.assertEqual(measured(replace(config, common_offset=0), device=device).response[0], 1)
        with self.assertRaisesRegex(noise.CommonModeNumericalError, "floating-point"):
            measured(config, device=device)

    def test_nonfinite_modeled_frequencies_rejected(self):
        device = Device(IDENTITY.device_id, (1e308,) * 128)
        with self.assertRaisesRegex(ValueError, "finite"):
            measured(replace(CONFIG, sigma=0, common_offset=1e308), device=device)
        with self.assertRaisesRegex(ValueError, "finite"):
            fixture_measure(replace(CONFIG, sigma=1e308, rho=1), (1e308,) * 128, ZEROS)


class MatchingAndReaderTests(unittest.TestCase):
    def test_identical_trials_reproduce_components_and_bits(self):
        for i in range(3):
            self.assertEqual(measured(index=i), measured(index=i))
        self.assertEqual(len({measured(index=i).independent_noise for i in range(3)}), 3)

    def test_legacy_exact_frequency_response_and_draw_order_compatibility(self):
        device = create_device(IDENTITY.device_id, 128, 1, rng=random.Random(1201))
        for sigma in (0, 0.125, 0.9, 8):
            config = replace(CONFIG, rho=0, sigma=sigma)
            for i in range(3):
                seed = noise.derive_seed(IDENTITY, noise.READING, i)
                result = measured(config, device=device, index=i)
                expected = calculate_frequencies(device, 100, ReadConditions(0, sigma),
                                                 rng=random.Random(seed))
                self.assertEqual(result.frequencies, expected)
                self.assertEqual(result.response, generate_response(device, noise.PAIRS, 100,
                                 ReadConditions(0, sigma), rng=random.Random(seed)))
                rng = random.Random(seed)
                draws = tuple(rng.gauss(0, sigma) for _ in range(128)) if sigma else ZEROS
                self.assertEqual(result.independent_noise, draws)

    def test_policy_order_and_matched_reading_zero_across_identities(self):
        for device_index, attempt in product(range(3), range(3)):
            identity = replace(IDENTITY, device_id=f"device-{device_index}", attempt_id=attempt)
            device = replace(DEVICE, device_id=identity.device_id)
            outputs = []
            for order in ((SINGLE_READ, MAJORITY_3), (MAJORITY_3, SINGLE_READ)):
                observed = {}
                for profile in order:
                    reader = noise.CorrelatedResponseReader(device, CONFIG, identity, profile)
                    captures = []
                    with patch.object(noise, "calculate_frequencies", wraps=calculate_frequencies) as calc:
                        # Record full components separately from the callback return.
                        actual_measure = noise.measure_indexed
                        def record(*args):
                            result = actual_measure(*args)
                            captures.append(result)
                            return result
                        with patch.object(noise, "measure_indexed", side_effect=record):
                            response = acquire_response(reader, profile)
                    self.assertEqual(calc.call_count, profile.read_count)
                    self.assertEqual([r.reading_index for r in captures], list(range(profile.read_count)))
                    observed[profile.policy] = (response, tuple(captures))
                b0, m3 = observed[SINGLE_READ.policy], observed[MAJORITY_3.policy]
                self.assertEqual(b0[1][0], m3[1][0])
                self.assertEqual(b0[0], m3[1][0].response)
                outputs.append(observed)
            self.assertEqual(outputs[0], outputs[1])

    def test_failed_trial_and_unrelated_executions_do_not_perturb_later_trials(self):
        later = replace(IDENTITY, attempt_id=20)
        expected = measured(identity=later)
        reader = noise.CorrelatedResponseReader(DEVICE, CONFIG, IDENTITY, MAJORITY_3)
        with patch.object(noise, "calculate_frequencies", side_effect=RuntimeError("fixture failure")):
            with self.assertRaisesRegex(RuntimeError, "fixture failure"):
                acquire_response(reader, MAJORITY_3)
        for index in (7, 2, 19):
            acquire_response(noise.CorrelatedResponseReader(DEVICE, CONFIG,
                             replace(IDENTITY, attempt_id=index), MAJORITY_3), MAJORITY_3)
        self.assertEqual(measured(identity=later), expected)

    def test_no_global_rng_state_used(self):
        before = random.getstate()
        acquire_response(noise.CorrelatedResponseReader(DEVICE, CONFIG, IDENTITY, MAJORITY_3), MAJORITY_3)
        self.assertEqual(random.getstate(), before)

    def test_actual_measurements_count_order_and_persistent_device(self):
        offsets = DEVICE.manufacturing_variation
        for profile in (SINGLE_READ, MAJORITY_3):
            reader = noise.CorrelatedResponseReader(DEVICE, CONFIG, IDENTITY, profile)
            shared = reader.shared
            with patch.object(noise, "calculate_frequencies", wraps=calculate_frequencies) as calc, \
                 patch.object(noise, "measure_indexed", wraps=noise.measure_indexed) as measure:
                response = acquire_response(reader, profile)
                self.assertEqual(type(response), tuple)
                self.assertEqual(len(response), 64)
                self.assertTrue(all(type(bit) is int and bit in (0, 1) for bit in response))
                self.assertEqual((calc.call_count, measure.call_count, reader.measurement_count),
                                 (profile.read_count,) * 3)
                self.assertEqual([c.args[-1] for c in measure.call_args_list], list(range(profile.read_count)))
                self.assertTrue(all(c.args[3] is shared for c in measure.call_args_list))
                self.assertTrue(all(c.args[0] is DEVICE for c in calc.call_args_list))
                self.assertEqual(len({id(c.kwargs["rng"]) for c in calc.call_args_list}), profile.read_count)
                self.assertTrue(all(len(c.kwargs["rng"].samples) == 128 for c in calc.call_args_list))
                with self.assertRaisesRegex(RuntimeError, "limit"):
                    reader()
                self.assertEqual(calc.call_count, profile.read_count)
            self.assertIs(reader.device.manufacturing_variation, offsets)

    def test_equal_response_bits_do_not_replace_measurements(self):
        config = replace(CONFIG, sigma=0)
        reader = noise.CorrelatedResponseReader(DEVICE, config, IDENTITY, MAJORITY_3)
        with patch.object(noise, "calculate_frequencies", wraps=calculate_frequencies) as calc:
            reads = tuple(reader() for _ in range(3))
        self.assertEqual(reads, (ZERO,) * 3)
        self.assertEqual(calc.call_count, 3)

    def test_reader_binding_and_invalid_measurement_arguments(self):
        for changes in ({"device": None}, {"device": Device("wrong", ZEROS)},
                        {"device": Device(IDENTITY.device_id, (0.0, 0.0))},
                        {"device": replace(DEVICE, aging_state=(1.0,)*128)},
                        {"config": None}, {"identity": None}, {"acquisition": None}):
            kwargs = dict(device=DEVICE, config=CONFIG, identity=IDENTITY)
            kwargs.update(changes)
            with self.assertRaises(ValueError):
                noise.CorrelatedResponseReader(**kwargs)
        shared = noise.generate_shared_disturbance(IDENTITY)
        for i in (None, -1, 3, True, 0.0):
            with self.assertRaisesRegex(ValueError, "reading_index"):
                noise.measure_indexed(DEVICE, CONFIG, IDENTITY, shared, i)
        for invalid in (None, replace(shared, identity=replace(IDENTITY, attempt_id=1))):
            with self.assertRaisesRegex(ValueError, "same attempt"):
                noise.measure_indexed(DEVICE, CONFIG, IDENTITY, invalid, 0)

    def test_reader_inputs_frozen_and_invalid_invocation_does_not_measure(self):
        reader = noise.CorrelatedResponseReader(DEVICE, CONFIG, IDENTITY)
        for field, value in (("device", DEVICE), ("identity", IDENTITY), ("shared", reader.shared),
                             ("acquisition", MAJORITY_3), ("config", CONFIG)):
            with self.assertRaises(FrozenInstanceError):
                setattr(reader, field, value)
        with self.assertRaises(TypeError):
            reader(0)
        self.assertEqual(reader.measurement_count, 0)

    def test_failures_at_each_position_latch_without_retry(self):
        for position in range(3):
            reader = noise.CorrelatedResponseReader(DEVICE, CONFIG, IDENTITY, MAJORITY_3)
            for _ in range(position):
                reader()
            with patch.object(noise, "calculate_frequencies", side_effect=RuntimeError("fixture failure")) as calc:
                with self.assertRaisesRegex(RuntimeError, "fixture failure"):
                    reader()
                with self.assertRaisesRegex(RuntimeError, "no retries"):
                    reader()
                calc.assert_called_once()
            self.assertEqual(reader.measurement_count, position + 1)

    def test_malformed_response_latches_without_retry(self):
        for bad in (None, (0,)*63, (False,) + ZERO[1:], (2,) + ZERO[1:]):
            reader = noise.CorrelatedResponseReader(DEVICE, CONFIG, IDENTITY, MAJORITY_3)
            with patch.object(noise, "measure_indexed", return_value=Mock(response=bad)) as measure:
                with self.assertRaises(ValueError):
                    acquire_response(reader, MAJORITY_3)
                with self.assertRaisesRegex(RuntimeError, "no retries"):
                    reader()
            measure.assert_called_once()
            self.assertEqual(reader.measurement_count, 1)

    def test_mismatched_acquisition_cannot_get_extra_read(self):
        reader = noise.CorrelatedResponseReader(DEVICE, CONFIG, IDENTITY)  # Default is one.
        with self.assertRaisesRegex(RuntimeError, "limit"):
            acquire_response(reader, MAJORITY_3)
        self.assertEqual(reader.measurement_count, 1)


class PipelineCompatibilityTests(unittest.TestCase):
    def setUp(self):
        from itertools import count
        entropy = count(1)
        self.enterContext(patch("puf_snn.auth.session.secrets.token_bytes",
                                side_effect=lambda size: next(entropy).to_bytes(size, "big")))
        self.enterContext(patch("puf_snn.auth.session.time.monotonic_ns", return_value=1_000_000_000))

    def pipeline(self, profile=None):
        from auth.support import admission_for_entries
        from puf_snn.auth.sender import Sender
        from puf_snn.auth.session import RegistryEntry, provision_device
        from puf_snn.auth.verifier import Verifier
        from puf_snn.pipeline_v2 import V2InferencePipeline
        from puf_snn.reconstruction import enroll
        credential, enrollment = bytes.fromhex("000001a5"), "unit-enrollment"
        helper = enroll(ZERO, credential, enrollment_id=enrollment)
        entries = [RegistryEntry(DEVICE.device_id, enrollment, credential)]
        admission = admission_for_entries(entries)
        sender = Sender(provision_device(DEVICE.device_id, enrollment, helper), admission_service=admission)
        verifier = Verifier(entries, admission_service=admission)
        kwargs = {} if profile is None else {"acquisition_config": profile}
        return V2InferencePipeline(sender, verifier, Mock(), Mock(), Mock(), **kwargs)

    def test_reader_default_one_read_and_majority_one_vote_one_real_decode(self):
        from puf_snn.auth.credential_verifier import CredentialAdmissionService
        from puf_snn.reconstruction import BCHCodec, DEFAULT_CONFIG, reconstruct
        for profile in (None, MAJORITY_3):
            pipeline = self.pipeline(profile)
            selected = SINGLE_READ if profile is None else profile
            reader = noise.CorrelatedResponseReader(DEVICE, replace(CONFIG, sigma=1e-6), IDENTITY, selected)
            with patch("puf_snn.puf.acquisition.majority_vote3", wraps=majority_vote3) as vote, \
                 patch("puf_snn.pipeline_v2.reconstruct", wraps=reconstruct) as reconstruction, \
                 patch.object(BCHCodec, "decode", autospec=True, side_effect=BCHCodec.decode) as decode, \
                 patch.object(CredentialAdmissionService, "verify", autospec=True,
                              side_effect=CredentialAdmissionService.verify) as verify:
                result = pipeline.establish(reader, "unit-correlated-attempt")
            self.assertTrue(result.session_active)
            self.assertEqual(reader.measurement_count, selected.read_count)
            self.assertEqual(vote.call_count, int(selected == MAJORITY_3))
            reconstruction.assert_called_once_with(ZERO, pipeline.sender.enrollment.helper_data)
            decode.assert_called_once()
            verify.assert_called_once()
            self.assertEqual(pipeline.sender.enrollment.helper_data.config, DEFAULT_CONFIG)
            self.assertEqual(pipeline.acquisition_config, selected)

    def test_real_wrong_credential_still_fails_independent_verification(self):
        from puf_snn.reconstruction import enroll, reconstruct
        pipeline = self.pipeline(MAJORITY_3)
        helper = pipeline.sender.enrollment.helper_data
        wrong = enroll(ZERO, bytes(4), enrollment_id=helper.enrollment_id)
        response = tuple(a ^ b for a, b in zip(helper.helper_bits, wrong.helper_bits)) + (0,)
        offsets = tuple(x for bit in response for x in ((1.0, -1.0) if bit else (-1.0, 1.0)))
        device = Device(DEVICE.device_id, offsets)
        reader = noise.CorrelatedResponseReader(device, replace(CONFIG, sigma=0), IDENTITY, MAJORITY_3)
        self.assertEqual(reconstruct(response, helper).candidate_credential, bytes(4))
        with patch("puf_snn.auth.sender.derive_session_key") as sender_kdf, \
             patch("puf_snn.auth.verifier.derive_session_key") as verifier_kdf, \
             patch.object(pipeline.verifier, "begin_session") as request:
            result = pipeline.establish(reader, "unit-wrong-credential")
        self.assertEqual(result.reason, "credential_verification_failed")
        self.assertFalse(result.request_emitted or result.session_active)
        self.assertEqual(reader.measurement_count, 3)
        sender_kdf.assert_not_called()
        verifier_kdf.assert_not_called()
        request.assert_not_called()
        self.assertFalse(pipeline.verifier.active_session_ids)
        self.assertIsNone(pipeline.sender.admission)

    def test_reader_failure_reaches_existing_fail_closed_path(self):
        from puf_snn.pipeline_v2 import PipelineExecutionError
        pipeline = self.pipeline(MAJORITY_3)
        reader = noise.CorrelatedResponseReader(DEVICE, CONFIG, IDENTITY, MAJORITY_3)
        with patch.object(noise, "calculate_frequencies", side_effect=RuntimeError("fixture")) as calc, \
             patch("puf_snn.pipeline_v2.reconstruct") as decode, \
             patch.object(pipeline.verifier, "begin_session") as request:
            with self.assertRaisesRegex(PipelineExecutionError, "response_acquisition"):
                pipeline.establish(reader, "unit-failed-reading")
        calc.assert_called_once()
        decode.assert_not_called()
        request.assert_not_called()
        self.assertEqual(reader.measurement_count, 1)
        self.assertEqual(pipeline.sender.kdf_timings_ns, ())
        self.assertEqual(pipeline.verifier.kdf_timings_ns, ())
        self.assertFalse(pipeline.verifier.active_session_ids)


if __name__ == "__main__":
    unittest.main()
