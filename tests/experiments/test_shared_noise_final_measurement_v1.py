"""Week 11 exact boundary fixtures, outside every scientific seed/cohort.

No planner compilation, reserved draws, evidence persistence or sessions occur.
Controlled Z/E enter the real indexed frequency/comparison/acquisition path.
"""

from contextlib import contextmanager
from dataclasses import asdict, replace
from fractions import Fraction
from random import Random
import unittest
from unittest.mock import patch

from puf_snn.experiments import correlated_noise_v1 as noise
from puf_snn.experiments import shared_noise_final_measurement_v1 as adapter
from puf_snn.experiments import shared_noise_final_plan_v1 as plan
from puf_snn.puf import acquisition
from puf_snn.puf.device import Device
from puf_snn.puf.ro_puf import generate_response
from puf_snn.puf.variables import ReadConditions
from puf_snn.reconstruction import BCHCodec, enroll, reconstruct
from puf_snn.reconstruction.bch import BCHDecodeResult
from puf_snn.reconstruction import credential


PREFIX = "isolated-measurement-boundary-v1"
IDENTITY = noise.AttemptIdentity(731903, PREFIX, "fixture-device", PREFIX + ":op:r000", 7)
DEVICE = Device(IDENTITY.device_id, (.25, -.25) * 64)
ZERO = (0.0,) * 128
RC = (1,) * 64
S, M, T = plan.POLICIES


def spec(condition="op_rho000", common=0):
    domain = next(c[3] for c in plan.CONDITIONS if c[0] == condition)
    return adapter.MeasurementSpec(condition, replace(IDENTITY, noise_domain_id=PREFIX + ":" + domain), common)


def disturbance(target):
    return tuple(value for bit in target for value in ((0., 0.) if bit else (-4., 4.)))


def classify(result):
    # Evaluator-only truth comparison; never enters acquisition/reconstruction.
    if result.outcome == "decoder_failure":
        return "D"
    if result.outcome == "invalid_format_or_padding":
        return "I"
    if result.outcome != "candidate_valid_format":
        raise AssertionError("unknown reconstruction outcome")
    return "C" if result.candidate_credential == bytes(4) else "W"


@contextmanager
def controlled_draws(binding, z, es):
    """Replace draw inputs only, retaining the real frequency loop and reader.

    At rho1 the nonzero E sentinels remain available, but gauss must not be
    called. Diagnostics and exact frequencies also detect accidental E use.
    """
    seeds = {noise.derive_seed(binding.identity, noise.READING, r): r for r in range(3)}
    gauss_calls, measurements, shared_calls = [], [], []
    original_random, original_measure = noise._MeasurementRandom, noise.measure_indexed

    class FixedRandom(original_random):
        def __init__(self, seed):
            super().__init__(seed)
            self.index = seeds[seed]  # A wrong/unaliasing seed fails immediately.
            self.values = iter(es[self.index])

        def gauss(self, mu, sigma):
            value = mu + sigma * next(self.values)
            self.samples.append(value)
            gauss_calls.append(self.index)
            return value

    def shared(identity):
        if identity != binding.identity:
            raise AssertionError("shared Z identity changed")
        value = noise.SharedDisturbance(identity, z)
        shared_calls.append(value)
        return value

    def measure(*args):
        value = original_measure(*args)
        measurements.append((args, value))
        return value

    with patch.object(noise, "_MeasurementRandom", FixedRandom), \
         patch.object(noise, "generate_shared_disturbance", side_effect=shared), \
         patch.object(noise, "measure_indexed", side_effect=measure):
        yield measurements, shared_calls, gauss_calls


class BoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reference = generate_response(DEVICE, noise.PAIRS, 100., ReadConditions(0, 0), rng=Random(731904))
        if reference != RC:
            raise AssertionError("noiseless fixture reference changed")
        cls.helper = enroll(reference, bytes(4), enrollment_id=PREFIX)
        codec = BCHCodec()
        cw = codec.encode((0,) * 31 + (1,) + (0,) * 4)
        ci = codec.encode((0,) * 35 + (1,))
        cls.targets = {"C": RC, "W": tuple(1 ^ b for b in cw) + (1,),
                       "I": tuple(1 ^ b for b in ci) + (1,)}
        if cls.helper.helper_bits != (1,) * 63 or codec.encode((0,) * 36) != (0,) * 63:
            raise AssertionError("fixture enrollment/codeword changed")

    def run_pair(self, binding, z, es, expected, categories, *, device=DEVICE):
        """Assert actual operations independently of adapter's reported counts."""
        reader_type, decode_impl = noise.CorrelatedResponseReader, BCHCodec.decode
        readers = []

        def reader(*args):
            value = reader_type(*args)
            readers.append(value)
            return value

        with controlled_draws(binding, z, es) as trace, \
             patch.object(noise, "CorrelatedResponseReader", side_effect=reader), \
             patch.object(acquisition, "majority_vote3", wraps=acquisition.majority_vote3) as vote, \
             patch.object(credential, "reconstruct", wraps=reconstruct) as reconstruction, \
             patch.object(BCHCodec, "decode", autospec=True, side_effect=decode_impl) as decode:
            results = [adapter.acquire_measurement(binding, policy, device) for policy in (S, M)]
            decoded = [credential.reconstruct(r.effective_response, self.helper) for r in results]
        measurements, shared, draws = trace
        self.assertEqual([r.reading_count for r in results], [1, 3])
        self.assertEqual([r.vote_count for r in results], [0, 1])
        self.assertEqual(len(readers), 2)
        self.assertIsNot(readers[0], readers[1])
        self.assertEqual([r.measurement_count for r in readers], [1, 3])
        self.assertEqual(len(measurements), 4)
        self.assertEqual([v.reading_index for _, v in measurements], [0, 0, 1, 2])
        self.assertEqual(len(shared), 2)  # Once per reader, never once per read.
        self.assertEqual(shared[0], shared[1])
        for args, _ in measurements:
            self.assertIs(args[0], device)
            self.assertEqual(args[2], binding.identity)
        self.assertTrue(all(args[3] is shared[1] for args, _ in measurements[1:]))
        self.assertEqual(results[0].readings, (expected[0],))
        self.assertEqual(results[1].readings, expected)
        self.assertEqual(results[0].readings[0], results[1].readings[0])
        self.assertEqual(results[0].effective_response, expected[0])
        self.assertEqual(results[1].effective_response, RC if categories[1] == "C" else expected[0])
        vote.assert_called_once_with(expected)
        self.assertEqual(reconstruction.call_count, 2)
        self.assertEqual(decode.call_count, 2)
        self.assertEqual(tuple(classify(r) for r in decoded), categories)
        return results, measurements, draws, decoded

    def test_rho1_encoder_derived_cwi_identity_and_nonzero_frr(self):
        failures = [0, 0]
        binding = spec("op_rho100")
        for category, target in self.targets.items():
            with self.subTest(category=category):
                z = disturbance(target)
                results, measured, draws, decoded = self.run_pair(binding, z,
                    tuple((float(r + 1),) * 128 for r in range(3)),
                    (target,) * 3, (category,) * 2)
                expected = tuple(100 + m + .15 * v for m, v in zip(DEVICE.manufacturing_variation, z))
                for _, value in measured:
                    self.assertEqual(value.frequencies, expected)
                    self.assertEqual(value.independent_noise, ZERO)
                self.assertEqual(draws, [])
                for i, result in enumerate(decoded):
                    failures[i] += classify(result) != "C"
        self.assertEqual(failures, [2, 2])
        frr_s, frr_m = (Fraction(n, 3) for n in failures)
        self.assertEqual((frr_s, frr_m, frr_s - frr_m), (Fraction(2, 3), Fraction(2, 3), 0))

    def test_common_mode_exact_frequencies_bits_and_cwi_categories(self):
        for category, target in self.targets.items():
            es = (disturbance(target), ZERO, ZERO)
            with self.subTest(category=category):
                _, reference, draws, _ = self.run_pair(spec(), ZERO, es, (target, RC, RC), (category, "C"))
                self.assertEqual(draws, [0] * 256 + [1] * 128 + [2] * 128)
                for offset in (-1, 1):
                    _, shifted, _, _ = self.run_pair(spec("common_mode_op_rho000", offset), ZERO, es,
                                                   (target, RC, RC), (category, "C"))
                    for (_, a), (_, b) in zip(reference, shifted):
                        self.assertEqual(b.frequencies, tuple(f + offset for f in a.frequencies))
                        self.assertEqual(tuple(g - f for f, g in zip(a.frequencies, b.frequencies)),
                                         (offset,) * 128)
                        self.assertEqual(a.response, b.response)
                        self.assertEqual(a.shared_noise, b.shared_noise)
                        self.assertEqual(a.independent_noise, b.independent_noise)

    def test_decoder_declared_failure_is_d_for_both_policies_and_offsets(self):
        failure = BCHDecodeResult("uncorrectable", -1, None, None, "decoder_declared_failure")
        for binding in (spec("op_rho100"), spec(), spec("common_mode_op_rho000", -1),
                        spec("common_mode_op_rho000", 1)):
            with self.subTest(condition=binding.condition, offset=binding.common_offset), \
                 controlled_draws(binding, ZERO, (ZERO,) * 3), \
                 patch.object(BCHCodec, "decode", return_value=failure) as decode, \
                 patch.object(acquisition, "majority_vote3", wraps=acquisition.majority_vote3) as vote:
                for policy, count in ((S, 1), (M, 3)):
                    result = adapter.acquire_measurement(binding, policy, DEVICE)
                    self.assertEqual((result.reading_count, len(result.readings)), (count, count))
                    decoded = reconstruct(result.effective_response, self.helper)
                    self.assertEqual(classify(decoded), "D")
                    self.assertEqual(decoded.failure_reason, "decoder_declared_failure")
                    self.assertIsNone(decoded.candidate_credential)
                self.assertEqual(decode.call_count, 2)
                vote.assert_called_once()

    def test_prescribed_binary64_fault_never_reaches_reconstruction(self):
        centered = (128., 128. - 2.**-46) + (100.,) * 126
        self.assertGreater(centered[0], centered[1])
        self.assertEqual(centered[0] + 1, centered[1] + 1)
        # The manufacturing offsets make the REAL frequency loop yield the
        # prescribed centered pair; no comparison/frequency function is mocked.
        device = replace(DEVICE, manufacturing_variation=tuple(f - 100 for f in centered))
        binding = spec("common_mode_op_rho000", 1)
        for policy in (S, M):
            with self.subTest(policy=policy), controlled_draws(binding, ZERO, (ZERO,) * 3) as trace, \
                 patch.object(credential, "reconstruct", wraps=reconstruct) as reconstruction, \
                 patch.object(acquisition, "majority_vote3", wraps=acquisition.majority_vote3) as vote:
                with self.assertRaises(noise.CommonModeNumericalError):
                    result = adapter.acquire_measurement(binding, policy, device)
                    credential.reconstruct(result.effective_response, self.helper)
                reconstruction.assert_not_called()
                vote.assert_not_called()
                self.assertEqual(trace[2], [0] * 128)  # First fault, no later read.

    def test_less_than_collapsing_to_equality_is_also_a_numerical_fault(self):
        offsets = (28. - 2.**-46, 28.) + (0.,) * 126
        device = replace(DEVICE, manufacturing_variation=offsets)
        binding = spec("common_mode_op_rho000", 1)
        with controlled_draws(binding, ZERO, (ZERO,) * 3), self.assertRaises(noise.CommonModeNumericalError):
            adapter.acquire_measurement(binding, S, device)

    def test_acceptance_detects_broken_reading_zero(self):
        real_measure = noise.measure_indexed

        def shifted(device, config, identity, shared, r):
            return real_measure(device, config, identity, shared, (r + 1) % 3)

        with patch.object(noise, "measure_indexed", side_effect=shifted), self.assertRaises(AssertionError):
            self.run_pair(spec(), ZERO, (disturbance(self.targets["W"]), ZERO, ZERO),
                          (self.targets["W"], RC, RC), ("W", "C"))

    def test_acceptance_detects_shared_z_regenerated_per_read(self):
        real_measure = noise.measure_indexed

        def regenerated(device, config, identity, shared, r):
            return real_measure(device, config, identity, noise.generate_shared_disturbance(identity), r)

        with patch.object(noise, "measure_indexed", side_effect=regenerated), self.assertRaises(AssertionError):
            self.run_pair(spec("op_rho100"), ZERO, (ZERO,) * 3, (RC,) * 3, ("C", "C"))

    def test_acceptance_detects_nonzero_independent_term_at_rho1(self):
        real_measure = noise.measure_indexed
        leaked_measurements = []

        def leaked(device, config, identity, shared, r):
            value = real_measure(device, replace(config, rho=.9), identity, shared, r)
            leaked_measurements.append(value)
            return value

        # These uniform E sentinels need not change bits. Their forbidden
        # contribution is detected by the exact frequency/diagnostic assertion.
        binding = spec("op_rho100")
        with controlled_draws(binding, ZERO, tuple((r + 1.,) * 128 for r in range(3))), \
             patch.object(noise, "measure_indexed", side_effect=leaked):
            result = adapter.acquire_measurement(binding, M, DEVICE)
            self.assertEqual(result.readings, (RC,) * 3)
            expected = tuple(100 + m for m in DEVICE.manufacturing_variation)
            with self.assertRaises(AssertionError):
                self.assertEqual(leaked_measurements[0].frequencies, expected)
            with self.assertRaises(AssertionError):
                self.assertEqual(leaked_measurements[0].independent_noise, ZERO)

    def test_acceptance_detects_changed_common_comparison(self):
        real_measure = noise.measure_indexed

        def changed(*args):
            measured = real_measure(*args)
            if args[1].common_offset:
                frequencies = list(measured.frequencies)
                frequencies[0], frequencies[1] = frequencies[1], frequencies[0]
                return replace(measured, frequencies=tuple(frequencies))
            return measured

        with patch.object(noise, "measure_indexed", side_effect=changed), self.assertRaises(AssertionError):
            self.run_pair(spec("common_mode_op_rho000", 1), ZERO, (ZERO,) * 3,
                          (RC,) * 3, ("C", "C"))

    def test_acceptance_detects_silently_accepted_rounding_fault(self):
        real_measure = noise.measure_indexed
        binding = spec("common_mode_op_rho000", 1)
        centered = (128., 128. - 2.**-46) + (100.,) * 126
        device = replace(DEVICE, manufacturing_variation=tuple(f - 100 for f in centered))

        def suppressed(*args):
            try:
                return real_measure(*args)
            except noise.CommonModeNumericalError:
                return noise.Measurement(args[-1], ZERO, ZERO, tuple(f + 1 for f in centered))

        with controlled_draws(binding, ZERO, (ZERO,) * 3), \
             patch.object(noise, "measure_indexed", side_effect=suppressed):
            with self.assertRaises(AssertionError):
                with self.assertRaises(noise.CommonModeNumericalError):
                    adapter.acquire_measurement(binding, S, device)

    def test_skipped_majority_acquisition_is_refused(self):
        def skipped(read, config):
            return acquisition.majority_vote3((read(), read(), RC))

        with controlled_draws(spec(), ZERO, (ZERO,) * 3), \
             patch.object(acquisition, "acquire_response", side_effect=skipped), \
             self.assertRaisesRegex(RuntimeError, "all required readings"):
            adapter.acquire_measurement(spec(), M, DEVICE)


class BindingTests(unittest.TestCase):
    def test_fixed_final_profiles_and_block_binding(self):
        for condition, sigma, rho, domain in plan.CONDITIONS:
            binding = spec(condition, 1 if condition.startswith("common") else 0)
            self.assertEqual((binding.noise_config.sigma, binding.noise_config.rho), (sigma, rho))
            self.assertEqual(binding.identity.noise_domain_id, PREFIX + ":" + domain)

    def test_invalid_bindings_rejected_before_draws(self):
        with patch.object(noise, "generate_shared_disturbance", side_effect=AssertionError("draw")):
            for args in (("other", IDENTITY), ("op_rho000", {}), ("op_rho100", IDENTITY),
                         ("op_rho000", IDENTITY, 1), ("op_rho000", IDENTITY, True),
                         ("common_mode_op_rho000", IDENTITY, 0),
                         ("common_mode_op_rho000", replace(IDENTITY, noise_domain_id=PREFIX + ":common:fresh"), 1)):
                with self.subTest(args=args), self.assertRaises(ValueError):
                    adapter.MeasurementSpec(*args)
            for policy in ("majority-2", None, []):
                with self.assertRaises(ValueError):
                    adapter.acquire_measurement(spec(), policy, DEVICE)

    def test_stored_has_no_response_draw_vote_or_decode(self):
        with patch.object(noise, "CorrelatedResponseReader", side_effect=AssertionError("reader")), \
             patch.object(acquisition, "majority_vote3", side_effect=AssertionError("vote")), \
             patch.object(BCHCodec, "decode", side_effect=AssertionError("decode")):
            result = adapter.acquire_measurement(spec(), T)
        self.assertEqual((result.readings, result.effective_response, result.reading_count, result.vote_count),
                         ((), None, 0, 0))

    def test_indexed_streams_share_z_and_reading_zero_with_independent_e(self):
        binding = spec("op_rho050")
        values, original = [], noise.measure_indexed

        def record(*args):
            value = original(*args)
            values.append((args, value))
            return value

        with patch.object(noise, "measure_indexed", side_effect=record), \
             patch.object(noise, "generate_shared_disturbance", wraps=noise.generate_shared_disturbance) as shared:
            single = adapter.acquire_measurement(binding, S, DEVICE)
            majority = adapter.acquire_measurement(binding, M, DEVICE)
        self.assertEqual(shared.call_count, 2)
        self.assertEqual(single.readings[0], majority.readings[0])
        self.assertEqual(values[0][1], values[1][1])
        self.assertEqual(len({v.independent_noise for _, v in values[1:]}), 3)
        self.assertEqual(len({v.shared_noise for _, v in values}), 1)
        for r, (args, value) in enumerate(values[1:]):
            self.assertIs(args[3], values[1][0][3])
            rng = Random(noise.derive_seed(binding.identity, noise.READING, r))
            self.assertEqual(value.independent_noise,
                             tuple(rng.gauss(0, binding.noise_config.independent_std) for _ in range(128)))

    def test_common_alias_all_seed_domains_but_distinct_scheduled_ids(self):
        operating, common = spec(), spec("common_mode_op_rho000", 1)
        # Exercise the planner's actual metadata/hash helpers with isolated IDs.
        op_block = dict(condition=operating.condition, noise_identity=asdict(operating.identity))
        op_block["trial_id"] = plan.trial_id(op_block)
        common_block = dict(condition=common.condition, noise_identity=asdict(common.identity),
                            linked_operating_trial_id=op_block["trial_id"])
        common_block["trial_id"] = plan.trial_id(common_block)
        self.assertNotEqual(op_block["trial_id"], common_block["trial_id"])
        for policy in plan.POLICIES:
            self.assertNotEqual(plan.attempt_id(op_block, policy), plan.attempt_id(common_block, policy))
        self.assertEqual(operating.identity, common.identity)
        for domain, r in ((noise.SESSION, None), *((noise.READING, r) for r in range(3))):
            self.assertEqual(plan.seed_digest(operating.identity, domain, r),
                             plan.seed_digest(common.identity, domain, r))
        self.assertNotEqual(noise.derive_seed(common.identity, noise.COMMON_MODE),
                            noise.derive_seed(common.identity, noise.SESSION))

    def test_independently_redrawn_common_noise_fails_alias_identity(self):
        operating = spec()
        redrawn = replace(operating.identity, attempt_id=operating.identity.attempt_id + 1)
        for domain, r in ((noise.SESSION, None), *((noise.READING, r) for r in range(3))):
            with self.subTest(domain=domain, r=r), self.assertRaises(AssertionError):
                self.assertEqual(plan.seed_digest(operating.identity, domain, r),
                                 plan.seed_digest(redrawn, domain, r))

    def test_acceptance_detects_one_common_control_e_seed_changed(self):
        original_measure, original_seed = noise.measure_indexed, noise.derive_seed
        measurements = []

        def record(*args):
            value = original_measure(*args)
            measurements.append(value)
            return value

        def corrupted(identity, domain, r=None):
            return original_seed(identity, domain, r) + int(domain == noise.READING and r == 2)

        with patch.object(noise, "measure_indexed", side_effect=record):
            adapter.acquire_measurement(spec(), M, DEVICE)
            with patch.object(noise, "derive_seed", side_effect=corrupted):
                adapter.acquire_measurement(spec("common_mode_op_rho000", 1), M, DEVICE)
        self.assertEqual(measurements[0].independent_noise, measurements[3].independent_noise)
        self.assertEqual(measurements[1].independent_noise, measurements[4].independent_noise)
        with self.assertRaises(AssertionError):
            self.assertEqual(measurements[2].independent_noise, measurements[5].independent_noise)


if __name__ == "__main__":
    unittest.main()
