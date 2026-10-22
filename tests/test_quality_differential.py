"""Bounded seeded differential fixtures, not accuracy, reliability or timing trials.

Compare reference Fraction and optional integer quality arithmetic through the
unchanged sender codec and real verifier/release gate. Consumer outputs below
are deterministic test probes, not predictions from the saved trained models.
"""

from dataclasses import replace
import math
import random
import struct
import unittest

import numpy as np

from auth.support import mutate, offsets, setup, window, wrap
from puf_snn.anomaly.features import record_to_anomaly_features
from puf_snn.auth import binary_window as codec
from puf_snn.integration import ExactlyOnceClassifierRelease
from puf_snn.quality_dyadic import quality_validator_mode
from puf_snn.snn.dataset import record_to_sequence


SEEDS = (8130, 8131, 8132)
MODES = ("reference_fraction", "candidate_dyadic")


def f32(value):
    """The fixture's existing binary32 encoding, identical in both modes."""
    return codec.F32(int.from_bytes(struct.pack(">f", value), "big"))


def random_window(seed, sid, seq=0):
    rng = random.Random(seed)
    start = 1_000_000_000 + seq * 2_000_000_000
    valid_count = rng.randint(114, 120)
    invalid_indexes = set(rng.sample(range(120), 120 - valid_count))
    axis = [rng.uniform(-1, 1) for _ in range(3)]
    length = math.sqrt(sum(value * value for value in axis))
    axis = [value / length for value in axis]
    samples = []
    for index in range(120):
        phase = index / 119
        angle = 0.5 * math.sin(phase * math.tau) + rng.uniform(-0.002, 0.002)
        rotation = tuple(f32(value * math.sin(angle / 2)) for value in axis) + (f32(math.cos(angle / 2)),)
        position = tuple(f32(0.05 * math.sin(phase * math.tau + dimension) + rng.uniform(-0.001, 0.001))
                         for dimension in range(3))
        jitter = rng.randint(0, 200_000) if index == 0 else rng.randint(-200_000, 200_000)
        samples.append(codec.Sample(index, start + index * 16_666_667 + jitter,
                                    position, rotation, index not in invalid_indexes))
    return replace(window(sid, seq), window_id=f"differential-{seed}-{seq}",
                   capture_start_ns=start, capture_end_ns=start + 2_000_000_000,
                   tracking_valid_count=valid_count,
                   tracking_valid_fraction_ppm=codec.tracking_ppm(valid_count), samples=tuple(samples))


def encode_decision(value):
    try:
        return "accept", codec.encode_window(value)
    except codec.ProtocolError as error:
        return "reject", error.reason


def status_projection(verifier, sid):
    state = verifier.session_status(sid)
    # Independent sessions correctly have different IDs and deadlines. Never
    # alter their real packets/keys; compare the relevant state values only.
    return state.state, state.accepted_count, state.last_accepted, verifier.incomplete


class QualityDifferentialTests(unittest.TestCase):
    def test_seeded_windows_are_reproducible_and_not_all_identical(self):
        sid = bytes(range(16))
        values = [random_window(seed, sid) for seed in SEEDS]
        self.assertEqual(values, [random_window(seed, sid) for seed in SEEDS])
        self.assertEqual(len(set(values)), len(SEEDS))

    def test_randomized_valid_sender_bytes_and_tags_match_exactly(self):
        sid, key = bytes(range(16)), bytes(range(32))  # Public synthetic fixtures.
        for seed in SEEDS:
            for index in range(8):
                value = random_window(seed + index * 100, sid, index)
                observations = []
                for mode in MODES:
                    with quality_validator_mode(mode):
                        encoded = codec.encode_window(value)
                        self.assertEqual(codec.parse_window(encoded), value)
                        observations.append((encoded, codec.encode_envelope(encoded, key), codec.window_tag(key, encoded)))
                with self.subTest(seed=seed, index=index):
                    self.assertEqual(observations[0], observations[1])

    def test_randomized_sender_refusals_preserve_exact_reason(self):
        for seed in SEEDS:
            value = random_window(seed, bytes(range(16)))
            index = random.Random(seed).randrange(1, 119)
            samples = list(value.samples)
            samples[index] = replace(samples[index], capture_time_ns=samples[index - 1].capture_time_ns)
            cases = [
                (replace(value, capture_end_ns=value.capture_end_ns + 121), "data_quality_failure"),
                (replace(value, tracking_valid_fraction_ppm=999999), "data_quality_failure"),
                (replace(value, samples=tuple(samples)), "data_quality_failure"),
                (replace(value, samples=value.samples[:-1]), "invalid_payload_schema"),
                (replace(value, sequence_number=-1), "sequence_out_of_range"),
                (replace(value, samples=(replace(value.samples[0], sample_index=1),) + value.samples[1:]),
                 "invalid_payload_schema"),
            ]
            for case_index, (invalid, expected) in enumerate(cases):
                observations = []
                for mode in MODES:
                    with quality_validator_mode(mode):
                        observations.append(encode_decision(invalid))
                with self.subTest(seed=seed, case=case_index):
                    self.assertEqual(observations[0], ("reject", expected))
                    self.assertEqual(observations[0], observations[1])

    def test_boundary_words_at_seeded_sample_positions_match(self):
        # Adjacent binary32 words on each side of the existing exact limits.
        boundaries = [
            ((0, 0, 0, 0x3f800008), True),
            ((0, 0, 0, 0x3f800009), False),
            ((0, 0, 0, 0x3f7ff973), True),
            ((0, 0, 0, 0x3f7ff972), False),
            ((0x3c67b5e6, 0, 0, 0x3f800000), True),
            ((0x3c67b5e7, 0, 0, 0x3f800000), False),
            ((0, 0, 0, 0), False),
            ((0, 0, 0, 0xbf800000), False),
        ]
        for seed in SEEDS:
            value = window(bytes(range(16)))
            rng = random.Random(seed)
            for words, accepted in boundaries:
                index = rng.randrange(1, 119)
                samples = list(value.samples)
                samples[index] = replace(samples[index], orientation_xyzw=tuple(codec.F32(word) for word in words))
                changed = replace(value, samples=tuple(samples))
                outcomes = []
                for mode in MODES:
                    with quality_validator_mode(mode):
                        outcomes.append(encode_decision(changed))
                with self.subTest(seed=seed, words=words, index=index):
                    self.assertEqual(outcomes[0], outcomes[1])
                    self.assertEqual(outcomes[0][0], "accept" if accepted else "reject")
                    if not accepted:
                        self.assertEqual(outcomes[0][1], "data_quality_failure")

    def run_mixed_stream(self, mode, seed):
        verifier, sid, key = setup()
        inputs, outputs, decisions = [], [], []

        def prepare(record):
            sequence = record_to_sequence(record)
            anomaly = record_to_anomaly_features(record)
            self.assertEqual(sequence.shape, (120, 7))
            self.assertEqual(anomaly.shape, (48,))
            self.assertTrue(np.isfinite(sequence).all() and np.isfinite(anomaly).all())
            inputs.append((sequence.dtype.str, sequence.tobytes(), anomaly.dtype.str, anomaly.tobytes()))
            return sequence, anomaly

        def consumer(features):
            sequence, anomaly = features
            result = (int(np.argmax(np.ptp(sequence[:, :3], axis=0))),
                      float(anomaly[0]), bool(anomaly[0] > 0.05))
            outputs.append(result)  # Deterministic probes, not trained models.
            return result

        gate = ExactlyOnceClassifierRelease(verifier, prepare, consumer)
        accepted_packets = []
        with quality_validator_mode(mode):
            for seq in range(8):
                value = random_window(seed + seq * 100, sid, seq)
                encoded = codec.encode_window(value)
                location = offsets(encoded)
                tag = codec.window_tag(key, encoded)
                invalid_tag = bytes([tag[0] ^ 1]) + tag[1:]
                refused = [
                    ("quality", wrap(mutate(encoded, location["ppm"], codec.U32(999999)), sid, key), "data_quality_failure"),
                    ("tag", wrap(encoded, sid, key, tag=invalid_tag), "invalid_tag"),
                    ("schema", wrap(mutate(encoded, location["sample"] + 22, codec.U32(0x7fc00000)), sid, key),
                     "invalid_payload_schema"),
                    ("malformed", b"{", "malformed_message"),
                    ("gap", wrap(codec.encode_window(replace(value, sequence_number=seq + 1)), sid, key), "future_sequence_gap"),
                ]
                if accepted_packets:
                    refused.append(("duplicate", accepted_packets[-1], "duplicate_sequence"))
                if len(accepted_packets) >= 2:
                    refused.append(("stale", accepted_packets[0], "stale_sequence"))
                random.Random(seed + seq).shuffle(refused)
                for name, packet, reason in refused:
                    before = verifier.session_status(sid)
                    result = verifier.verify_window(packet)
                    self.assertEqual((result.result, result.reason), ("reject", reason))
                    self.assertEqual(verifier.session_status(sid), before)
                    with self.assertRaises(ValueError):
                        gate.deliver(result)
                    self.assertEqual((len(inputs), len(outputs), len(gate.consumed_event_ids)), (seq, seq, seq))
                    decisions.append((seq, name, result.result, result.reason, status_projection(verifier, sid)))
                packet = wrap(encoded, sid, key)
                result = verifier.verify_window(packet)
                self.assertEqual((result.result, result.reason), ("accept", "accepted"))
                self.assertEqual(result.accepted_window, codec.parse_window(encoded))
                gate.deliver(result)
                with self.assertRaises(ValueError):
                    gate.deliver(result)
                self.assertEqual((len(inputs), len(outputs), len(gate.consumed_event_ids)), (seq + 1,) * 3)
                decisions.append((seq, "valid", result.result, result.reason, status_projection(verifier, sid)))
                accepted_packets.append(packet)
        return decisions, inputs, outputs

    def test_seeded_authenticated_streams_preserve_state_features_and_probe_outputs(self):
        for seed in SEEDS:
            with self.subTest(seed=seed):
                reference = self.run_mixed_stream(MODES[0], seed)
                candidate = self.run_mixed_stream(MODES[1], seed)
                self.assertEqual(reference, candidate)
                self.assertEqual(len(reference[1]), 8)
                self.assertGreater(len(set(reference[2])), 1)

    def test_authenticated_boundary_rejections_allow_exact_next_continuation(self):
        observations = []
        for mode in MODES:
            verifier, sid, key = setup()
            seen = []
            gate = ExactlyOnceClassifierRelease(verifier, lambda record: record["sequence_number"], seen.append)
            rows = []
            with quality_validator_mode(mode):
                for seq, word in enumerate((0x3f800009, 0x3f7ff972, 0, 0xbf800000, 0x80000000, 0x7f800000)):
                    value = window(sid, seq)
                    encoded = codec.encode_window(value)
                    sample_index = random.Random(8133 + seq).randrange(1, 119)
                    # 39 bytes/sample; quaternion w follows x/y/z at offset 34.
                    bad = mutate(encoded, offsets(encoded)["sample"] + sample_index * 39 + 34, codec.U32(word))
                    before = verifier.session_status(sid)
                    result = verifier.verify_window(wrap(bad, sid, key))
                    expected = "invalid_payload_schema" if word in (0x80000000, 0x7f800000) else "data_quality_failure"
                    self.assertEqual((result.result, result.reason), ("reject", expected))
                    self.assertEqual(verifier.session_status(sid), before)
                    with self.assertRaises(ValueError):
                        gate.deliver(result)
                    self.assertEqual(len(seen), seq)
                    good = verifier.verify_window(wrap(encoded, sid, key))
                    self.assertEqual((good.result, good.reason), ("accept", "accepted"))
                    gate.deliver(good)
                    rows.append((result.reason, good.reason, status_projection(verifier, sid)))
            self.assertEqual(seen, list(range(6)))
            observations.append(rows)
        self.assertEqual(observations[0], observations[1])


if __name__ == "__main__":
    unittest.main()
