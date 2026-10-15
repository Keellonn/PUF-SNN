"""Majority-3 functional controls; no FRR, model, or latency experiment.

All credentials, entropy, and response patterns here are NONSECRET fixtures.
Every candidate is produced by the real fixed BCH decoder, never fabricated.
"""

from dataclasses import replace
import itertools
from pathlib import Path
from random import Random
import unittest
from unittest.mock import Mock, patch

from auth.support import admission_for_entries, window, wrap
from puf_snn.auth.binary_window import F32, encode_window, parse_envelope
from puf_snn.auth.credential_verifier import CredentialAdmissionService
from puf_snn.auth.sender import Sender
from puf_snn.auth.session import RegistryEntry, provision_device, unframe
from puf_snn.auth.verifier import Verifier, VerificationResult
from puf_snn.pipeline_v2 import ModelCallCounts, PipelineExecutionError, V2InferencePipeline
from puf_snn.puf.acquisition import AcquisitionConfig, MAJORITY_3, SINGLE_READ, SimulatedResponseReader
from puf_snn.puf.device import create_device
from puf_snn.puf.ro_puf import generate_pairs, generate_response
from puf_snn.puf.variables import ReadConditions
from puf_snn.reconstruction import BCHCodec, DEFAULT_CONFIG, enroll, reconstruct


CREDENTIAL = bytes.fromhex('000001a5')
REFERENCE = (0,) * 64
DEVICE, ENROLLMENT = 'sim-device', 'unit-enrollment'
ROOT = Path(__file__).resolve().parents[1]


class Majority3PipelineTests(unittest.TestCase):
    def setUp(self):
        # Scoped fixture entropy and time; runtime OS entropy is unchanged.
        counter = itertools.count(1)
        self.enterContext(patch('puf_snn.auth.session.secrets.token_bytes',
                                side_effect=lambda size: next(counter).to_bytes(size, 'big')))
        self.enterContext(patch('puf_snn.auth.session.time.monotonic_ns', return_value=1_000_000_000))

    def peers(self, config=MAJORITY_3, *, reference=REFERENCE, missing_record=False):
        helper = enroll(reference, CREDENTIAL, enrollment_id=ENROLLMENT)
        entries = [RegistryEntry(DEVICE, ENROLLMENT, CREDENTIAL)]
        admission = admission_for_entries([] if missing_record else entries)
        sender = Sender(provision_device(DEVICE, ENROLLMENT, helper), admission_service=admission)
        verifier = Verifier(entries, admission_service=admission)
        prepare = Mock(side_effect=lambda record: (record, record))
        motion, anomaly = Mock(return_value='fixture-motion'), Mock(return_value='fixture-anomaly')
        kwargs = {} if config is None else {'acquisition_config': config}
        return V2InferencePipeline(sender, verifier, prepare, motion, anomaly, **kwargs)

    def active(self, config=MAJORITY_3):
        pipeline = self.peers(config)
        result = pipeline.establish(Mock(side_effect=[REFERENCE] * pipeline.acquisition_config.read_count),
                                    'unit-attempt')
        self.assertEqual((result.decision, result.stage), ('accept', 'active_session'))
        return pipeline

    def assert_no_authority(self, pipeline):
        self.assertNotEqual(pipeline.sender.state, 'ACTIVE')
        self.assertIsNone(pipeline.sender.session_id)
        self.assertIsNone(pipeline.sender._key)
        self.assertIsNone(pipeline.sender._request)
        self.assertIsNone(pipeline.sender.admission)
        self.assertEqual(pipeline.sender.kdf_timings_ns, ())
        self.assertEqual(pipeline.verifier.kdf_timings_ns, ())
        self.assertFalse(pipeline.verifier._pending)
        self.assertFalse(pipeline.verifier.active_session_ids)
        self.assertFalse(pipeline.verifier._accepted_results)
        self.assertFalse(pipeline.sender._admission_service._admissions)
        self.assertEqual(pipeline.calls, ModelCallCounts())
        self.assertEqual(pipeline.consumed_event_ids, ())
        for callback in (pipeline._prepare, pipeline._motion, pipeline._anomaly):
            callback.assert_not_called()

    def test_candidate_votes_before_one_decode_and_one_admission_then_mutual_handshake(self):
        profile = AcquisitionConfig.load(ROOT / 'configs/authentication_v2_majority3_acquisition.json')
        pipeline = self.peers(profile)
        # Three distinct reads. Disjoint errors vanish; five shared errors still
        # require real BCH correction. Bit 63 is voted but excluded by BCH.
        masks = ({0, 1, 2, 3, 4, 10, 11, 63}, {0, 1, 2, 3, 4, 20, 21, 63},
                 {0, 1, 2, 3, 4, 30, 31})
        reads = [tuple(int(i in mask) for i in range(64)) for mask in masks]
        voted = (1,) * 5 + (0,) * 58 + (1,)
        read = Mock(side_effect=reads)
        verify_impl, authorize_impl = CredentialAdmissionService.verify, CredentialAdmissionService.authorize
        with patch('puf_snn.pipeline_v2.reconstruct', wraps=reconstruct) as reconstruction, \
             patch.object(BCHCodec, 'decode', autospec=True, side_effect=BCHCodec.decode) as decode, \
             patch.object(CredentialAdmissionService, 'verify', autospec=True,
                          side_effect=verify_impl) as verify, \
             patch.object(CredentialAdmissionService, 'authorize', autospec=True,
                          side_effect=authorize_impl) as authorize, \
             patch.object(pipeline.sender, 'begin_attempt', wraps=pipeline.sender.begin_attempt) as begin, \
             patch.object(pipeline.verifier, 'begin_session', wraps=pipeline.verifier.begin_session) as request:
            outcome = pipeline.establish(read, 'voted-unit-attempt')
        self.assertEqual(read.call_count, 3)
        reconstruction.assert_called_once_with(voted, pipeline.sender.enrollment.helper_data)
        decode.assert_called_once()
        verify.assert_called_once()
        authorize.assert_called_once()
        begin.assert_called_once()
        request.assert_called_once()
        result = begin.call_args.args[0]
        self.assertEqual(result.candidate_credential, CREDENTIAL)
        self.assertEqual(result.reported_correction_count, 5)
        self.assertEqual(result.candidate_message[-4:], (0,) * 4)
        self.assertTrue(outcome.session_active and outcome.request_emitted)
        self.assertEqual(pipeline.sender.enrollment.helper_data.config, DEFAULT_CONFIG)
        self.assertEqual(pipeline.acquisition_config.to_dict(), profile.to_dict())
        self.assertEqual(len(pipeline.sender.kdf_timings_ns), 1)
        self.assertEqual(len(pipeline.verifier.kdf_timings_ns), 1)
        self.assertEqual(pipeline.calls, ModelCallCounts())
        packet = pipeline.sender.seal_window(window(pipeline.sender.session_id))
        accepted = pipeline.process_envelope(packet)
        self.assertEqual((accepted.decision, accepted.sequence_number), ('accept', 0))
        self.assertEqual(pipeline.calls, ModelCallCounts(1, 1, 1))
        self.assertEqual(accepted.inference.motion, 'fixture-motion')

    def test_default_and_explicit_single_read_preserve_baseline(self):
        for config in (None, SINGLE_READ):
            pipeline = self.peers(config)
            read = Mock(return_value=REFERENCE)
            with patch('puf_snn.pipeline_v2.reconstruct', wraps=reconstruct) as decode:
                result = pipeline.establish(read, 'baseline-attempt')
            read.assert_called_once_with()
            decode.assert_called_once_with(REFERENCE, pipeline.sender.enrollment.helper_data)
            self.assertTrue(result.session_active)
            self.assertEqual(pipeline.acquisition_config, SINGLE_READ)
            packet = pipeline.sender.seal_window(window(pipeline.sender.session_id))
            self.assertEqual(pipeline.process_envelope(packet).decision, 'accept')

    def test_pipeline_rejects_invalid_configuration_at_construction(self):
        for config in ('majority-3-v1', {}, object()):
            with self.assertRaisesRegex(ValueError, 'AcquisitionConfig'):
                self.peers(config)

    def test_actual_persistent_simulator_reader_reaches_active_session(self):
        device = create_device(DEVICE, 128, 1.0, rng=Random(7301))
        reference = generate_response(device, generate_pairs(128, 'adjacent'), 100.0,
                                      ReadConditions(0, 0), rng=Random(7303))
        pipeline = self.peers(reference=reference)
        noise = Random(7302)
        reader = SimulatedResponseReader(device, 100.0, ReadConditions(0, 0.000001), noise)
        with patch('puf_snn.puf.acquisition.generate_response', wraps=generate_response) as read:
            outcome = pipeline.establish(reader, 'simulator-control')
        self.assertTrue(outcome.session_active)
        self.assertEqual(read.call_count, 3)
        self.assertTrue(all(call.args[0] is device for call in read.call_args_list))

    def assert_reconstruction_rejected(self, pipeline, response, expected_outcome, *, verification=False):
        read = Mock(side_effect=[response] * 3)
        with patch('puf_snn.pipeline_v2.reconstruct', wraps=reconstruct) as decode, \
             patch.object(pipeline.verifier, 'begin_session') as request, \
             patch('puf_snn.auth.sender.derive_session_key') as sender_kdf, \
             patch('puf_snn.auth.verifier.derive_session_key') as verifier_kdf, \
             patch.object(CredentialAdmissionService, 'verify', autospec=True,
                          side_effect=CredentialAdmissionService.verify) as verify:
            outcome = pipeline.establish(read, 'rejected-attempt')
        self.assertEqual(outcome.reconstruction_outcome, expected_outcome)
        self.assertEqual(outcome.reason, 'credential_verification_failed' if verification else 'failed_reconstruction')
        self.assertFalse(outcome.request_emitted or outcome.session_active)
        self.assertEqual(read.call_count, 3)
        decode.assert_called_once()
        self.assertEqual(verify.call_count, int(verification))
        request.assert_not_called()
        sender_kdf.assert_not_called()
        verifier_kdf.assert_not_called()
        self.assert_no_authority(pipeline)
        with self.assertRaisesRegex(ValueError, 'one attempt'):
            pipeline.establish(read, 'no-retry')
        self.assertEqual(read.call_count, 3)

    def test_real_decoder_failure_blocks_admission_and_hkdf_without_retry(self):
        pipeline = self.peers()
        # Fixed received word outside the decoding sphere; no mocked result.
        received = (1,) * 6 + (0,) * 57
        response = tuple(a ^ b for a, b in zip(received, pipeline.sender.enrollment.helper_data.helper_bits)) + (0,)
        self.assert_reconstruction_rejected(pipeline, response, 'decoder_failure')

    def test_real_invalid_padding_blocks_admission(self):
        pipeline = self.peers()
        word = BCHCodec().encode((0,) * 35 + (1,))
        response = tuple(a ^ b for a, b in zip(word, pipeline.sender.enrollment.helper_data.helper_bits)) + (0,)
        self.assert_reconstruction_rejected(pipeline, response, 'invalid_format_or_padding')

    def test_real_wrong_valid_format_candidate_fails_independent_verification(self):
        pipeline = self.peers()
        wrong_helper = enroll(REFERENCE, bytes(4), enrollment_id=ENROLLMENT)
        response = tuple(a ^ b for a, b in zip(wrong_helper.helper_bits,
                                              pipeline.sender.enrollment.helper_data.helper_bits)) + (0,)
        self.assertEqual(reconstruct(response, pipeline.sender.enrollment.helper_data).candidate_credential, bytes(4))
        self.assert_reconstruction_rejected(pipeline, response, 'candidate_valid_format', verification=True)

    def test_missing_verifier_record_blocks_admission(self):
        self.assert_reconstruction_rejected(self.peers(missing_record=True), REFERENCE,
                                            'candidate_valid_format', verification=True)

    def test_each_acquisition_failure_or_malformed_read_fails_closed(self):
        for config in (SINGLE_READ, MAJORITY_3):
            for position in range(config.read_count):
                for bad in ((0,) * 63, (0,) * 65, (False,) + REFERENCE[1:],
                            (2,) + REFERENCE[1:], None, RuntimeError('private-response-material')):
                    with self.subTest(policy=config.policy, position=position, bad=type(bad)):
                        pipeline = self.peers(config)
                        read = Mock(side_effect=[REFERENCE] * position + [bad] + [REFERENCE] * 3)
                        with patch('puf_snn.pipeline_v2.reconstruct') as decode, \
                             patch.object(CredentialAdmissionService, 'authorize') as authorize, \
                             patch.object(pipeline.verifier, 'begin_session') as request:
                            with self.assertRaisesRegex(PipelineExecutionError, 'response_acquisition: internal_error'):
                                pipeline.establish(read, 'acquisition-error')
                        self.assertEqual(read.call_count, position + 1)
                        decode.assert_not_called()
                        authorize.assert_not_called()
                        request.assert_not_called()
                        self.assert_no_authority(pipeline)
                        self.assertTrue(pipeline.sender.incomplete)
                        self.assertNotIn('private-response-material', repr(pipeline.sender.audit_records))
                        with self.assertRaisesRegex(ValueError, 'one attempt'):
                            pipeline.establish(read, 'no-retry')
                        self.assertEqual(read.call_count, position + 1)

    def test_decoder_exception_does_not_reread_or_admit(self):
        pipeline = self.peers()
        read = Mock(side_effect=[REFERENCE] * 3)
        with patch('puf_snn.pipeline_v2.reconstruct', side_effect=RuntimeError('private-backend')) as decode, \
             patch.object(CredentialAdmissionService, 'authorize') as authorize:
            with self.assertRaisesRegex(PipelineExecutionError, 'reconstruction: internal_error'):
                pipeline.establish(read, 'backend-error')
        self.assertEqual(read.call_count, 3)
        decode.assert_called_once()
        authorize.assert_not_called()
        self.assert_no_authority(pipeline)
        self.assertNotIn('private-backend', repr(pipeline.sender.audit_records))

    def test_missing_local_authorization_is_refused_before_receiver_hkdf(self):
        pipeline = self.peers()
        begin = pipeline.verifier.begin_session
        with patch.object(pipeline.verifier, 'begin_session',
                          side_effect=lambda request, local, admission: begin(request, local, admission=None)):
            result = pipeline.establish(lambda: REFERENCE, 'no-local-authorization')
        self.assertEqual((result.stage, result.reason), ('receiver_admission', 'credential_verification_failed'))
        self.assert_no_authority(pipeline)

    def test_mutation_replay_gap_and_recovery_preserve_state_for_both_policies(self):
        for config in (SINGLE_READ, MAJORITY_3):
            with self.subTest(policy=config.policy):
                pipeline = self.active(config)
                sid = pipeline.sender.session_id
                packets = [pipeline.sender.seal_window(window(sid)) for _ in range(3)]
                parsed = parse_envelope(packets[0])
                sample = replace(parsed.window.samples[0], position_m=(F32(0x3f000000), F32(0), F32(0)))
                changed = replace(parsed.window, samples=(sample,) + parsed.window.samples[1:])
                tampered = wrap(encode_window(changed), sid, None, tag=parsed.tag)

                def reject(packet, reason):
                    before = pipeline.verifier.session_status(sid)
                    calls = pipeline.calls
                    consumed = pipeline.consumed_event_ids
                    outcome = pipeline.process_envelope(packet)
                    self.assertEqual((outcome.decision, outcome.reason), ('reject', reason))
                    self.assertEqual(pipeline.verifier.session_status(sid), before)
                    self.assertEqual(pipeline.calls, calls)
                    self.assertEqual(pipeline.consumed_event_ids, consumed)

                reject(tampered, 'invalid_tag')
                reject(packets[1], 'future_sequence_gap')
                self.assertEqual(pipeline.process_envelope(packets[0]).decision, 'accept')
                reject(packets[0], 'duplicate_sequence')
                self.assertEqual(pipeline.process_envelope(packets[1]).decision, 'accept')
                reject(packets[0], 'stale_sequence')
                self.assertEqual(pipeline.process_envelope(packets[2]).decision, 'accept')
                self.assertEqual(pipeline.calls, ModelCallCounts(3, 3, 3))
                status = pipeline.verifier.session_status(sid)
                self.assertEqual((status.accepted_count, status.last_accepted), (3, 2))

    def test_only_verifier_issued_acceptance_can_release_once(self):
        pipeline = self.active()
        rejected = pipeline.verifier.verify_window(b'not-json')
        for result in (rejected, VerificationResult('accept', 'accepted', event_id='forged')):
            with self.assertRaises(ValueError):
                pipeline.release(result)
        packet = pipeline.sender.seal_window(window(pipeline.sender.session_id))
        accepted = pipeline.verifier.verify_window(packet)
        with self.assertRaisesRegex(ValueError, 'not bound'):
            pipeline.release(replace(accepted))
        self.assertEqual(pipeline.calls, ModelCallCounts())
        pipeline.release(accepted)
        with self.assertRaisesRegex(ValueError, 'already delivered'):
            pipeline.release(accepted)
        self.assertEqual(pipeline.calls, ModelCallCounts(1, 1, 1))

    def test_consumer_failure_is_consumed_without_rollback_or_retry(self):
        pipeline = self.active()
        pipeline._motion.side_effect = RuntimeError('unit-model-failure')
        packet = pipeline.sender.seal_window(window(pipeline.sender.session_id))
        accepted = pipeline.verifier.verify_window(packet)
        with self.assertRaisesRegex(RuntimeError, 'consumer failure'):
            pipeline.release(accepted)
        with self.assertRaisesRegex(ValueError, 'already delivered'):
            pipeline.release(accepted)
        self.assertEqual(pipeline.calls, ModelCallCounts(1, 1, 0))
        self.assertEqual(pipeline.verifier.session_status(pipeline.sender.session_id).accepted_count, 1)
        self.assertTrue(pipeline.verifier.incomplete)

    def test_handshake_bytes_and_credential_format_identical_under_fixed_entropy(self):
        transcripts = []
        for config in (SINGLE_READ, MAJORITY_3):
            counter = itertools.count(1)
            with patch('puf_snn.auth.session.secrets.token_bytes',
                       side_effect=lambda size: next(counter).to_bytes(size, 'big')):
                pipeline = self.peers(config)
                with patch.object(pipeline.verifier, 'begin_session', wraps=pipeline.verifier.begin_session) as request, \
                     patch.object(pipeline.sender, 'answer_challenge', wraps=pipeline.sender.answer_challenge) as challenge, \
                     patch.object(pipeline.verifier, 'confirm_session', wraps=pipeline.verifier.confirm_session) as confirm, \
                     patch.object(pipeline.sender, 'finish_session', wraps=pipeline.sender.finish_session) as finish:
                    self.assertTrue(pipeline.establish(lambda: REFERENCE, 'wire-control').session_active)
                messages = tuple(mock.call_args.args[0] for mock in (request, challenge, confirm, finish))
                self.assertEqual(tuple(unframe(message).take(4) for message in messages),
                                 (b'P3RQ', b'P3CH', b'P3CF', b'P3OK'))
                packet = pipeline.sender.seal_window(window(pipeline.sender.session_id))
                transcripts.append((pipeline.sender.enrollment.helper_data, messages, packet))
        self.assertEqual(transcripts[0], transcripts[1])


if __name__ == '__main__':
    unittest.main()
