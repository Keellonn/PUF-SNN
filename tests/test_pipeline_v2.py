"""Integration controls for the current admission-to-composite-inference path.

Fixed credentials/responses/keys below are NONSECRET fixtures, not PUF reliability
samples. The actual SNN forward-pass fixture is untrained, not a new baseline.
"""

from copy import deepcopy
from dataclasses import asdict, replace
import json
import unittest
from unittest.mock import Mock, patch

import numpy as np
import torch

from puf_snn.anomaly.features import record_to_anomaly_features
from puf_snn.auth.config import AuthConfig
from puf_snn.auth.credential_verifier import (
    CredentialAdmissionService, CredentialVerifierRecord, CredentialVerifierStore,
    InMemoryCredentialVerifierKeyProvider,
)
from puf_snn.auth.sender import Sender
from puf_snn.auth.session import RegistryEntry, provision_device
from puf_snn.auth.verifier import Verifier
from puf_snn.integration import processed_record_to_wire_window
from puf_snn.pipeline_v2 import (
    ModelCallCounts, PipelineExecutionError, V2InferencePipeline,
)
from puf_snn.reconstruction import ReconstructionResult, enroll, reconstruct
from puf_snn.snn.dataset import record_to_sequence
from puf_snn.snn.model import RecurrentLifClassifier


CREDENTIAL = bytes.fromhex("000001a5")
REFERENCE = (0,) * 64
DEVICE = "week6-test-device"
ENROLLMENT = "week6-test-enrollment"


def source_record():
    return {
        "window_id": "week6-control-window", "window_start_ns": 1_000_000_000,
        "window_end_ns": 3_000_000_000, "label": "nod", "split": "test",
        "device_id": "dataset-device", "session_id": "dataset-session", "sequence_number": 999,
        "samples": [{"sample_index": i, "capture_time_ns": 1_000_000_000 + i * 16_666_667,
                     "position_m": [i / 1000.0, 0.0, 0.1],
                     "orientation_xyzw": [0.0, 0.0, 0.0, 1.0], "tracking_valid": True}
                    for i in range(120)],
    }


def prepare(record):
    return record_to_sequence(record), record_to_anomaly_features(record)


def response_with_flips(indexes):
    return tuple(1 if index in indexes else 0 for index in range(64))


class PipelineV2Tests(unittest.TestCase):
    def peers(self, *, missing_record=False, receiver_credential=CREDENTIAL,
              prepare_callback=None, motion_callback=None, anomaly_callback=None, config=None):
        config = AuthConfig() if config is None else config
        helper = enroll(REFERENCE, CREDENTIAL, enrollment_id=ENROLLMENT)
        provider = InMemoryCredentialVerifierKeyProvider("nonsecret-test-key", bytes(range(32)))
        record = CredentialVerifierRecord.enroll(
            device_id=DEVICE, enrollment_id=ENROLLMENT, reconstruction_id=helper.config.version,
            verifier_key_id="nonsecret-test-key", credential4=CREDENTIAL, key_provider=provider,
        )
        admission = CredentialAdmissionService(
            CredentialVerifierStore([] if missing_record else [record]), provider)
        sender = Sender(provision_device(DEVICE, ENROLLMENT, helper), config.session_config().limits,
                        admission_service=admission)
        verifier = Verifier([RegistryEntry(DEVICE, ENROLLMENT, receiver_credential)],
                            config.session_config(), admission_service=admission)
        preprocessing = Mock(side_effect=prepare if prepare_callback is None else prepare_callback)
        motion = Mock(side_effect=(lambda _: "nod") if motion_callback is None else motion_callback)
        anomaly = Mock(side_effect=(lambda _: {"score": 0.1, "flag": False})
                       if anomaly_callback is None else anomaly_callback)
        pipeline = V2InferencePipeline(sender, verifier, preprocessing, motion, anomaly)
        return pipeline, preprocessing, motion, anomaly

    def active(self, **kwargs):
        peers = self.peers(**kwargs)
        self.assertEqual(peers[0].establish(lambda: response_with_flips({2, 8, 19}), "attempt-1").decision,
                         "accept")
        return peers

    def assert_no_models(self, peers):
        self.assertEqual(peers[0].calls, ModelCallCounts())
        for callback in peers[1:]:
            callback.assert_not_called()

    def test_real_noisy_response_is_acquired_and_reconstructed_once(self):
        peers = self.peers()
        pipeline = peers[0]
        noisy = response_with_flips({1, 7, 17, 39, 62})
        read = Mock(return_value=noisy)
        with patch("puf_snn.pipeline_v2.reconstruct", wraps=reconstruct) as decode:
            result = pipeline.establish(read, "single-read")
        read.assert_called_once_with()
        decode.assert_called_once_with(noisy, pipeline.sender.enrollment.helper_data)
        self.assertTrue(result.session_active)
        self.assertTrue(result.request_emitted)
        self.assertEqual(result.reconstruction_outcome, "candidate_valid_format")
        self.assertEqual(len(pipeline.sender.kdf_timings_ns), 1)
        self.assertEqual(len(pipeline.verifier.kdf_timings_ns), 1)
        self.assert_no_models(peers)

    def test_zero_through_five_selected_bit_errors_admit(self):
        for count in range(6):
            with self.subTest(selected_errors=count):
                pipeline = self.peers()[0]
                result = pipeline.establish(lambda: response_with_flips(set(range(count))), "bounded-noise")
                self.assertEqual(result.decision, "accept")

    def test_real_wrong_valid_format_reconstruction_is_blocked_before_hkdf(self):
        peers = self.peers()
        pipeline = peers[0]
        # Controlled received alternate codeword, not random-noise trial evidence.
        wrong_helper = enroll(REFERENCE, bytes(4), enrollment_id=ENROLLMENT)
        helper = pipeline.sender.enrollment.helper_data
        noisy = tuple(a ^ b for a, b in zip(helper.helper_bits, wrong_helper.helper_bits)) + (0,)
        self.assertGreater(sum(noisy[:63]), 5)
        reconstructed = reconstruct(noisy, helper)
        self.assertEqual(reconstructed.outcome, "candidate_valid_format")
        self.assertEqual(reconstructed.candidate_credential, bytes(4))
        with patch("puf_snn.auth.sender.derive_session_key") as sender_kdf, \
             patch("puf_snn.auth.verifier.derive_session_key") as verifier_kdf:
            result = pipeline.establish(lambda: noisy, "wrong-codeword")
        self.assertEqual((result.stage, result.reason),
                         ("credential_admission", "credential_verification_failed"))
        self.assertFalse(result.request_emitted)
        self.assertFalse(result.session_active)
        sender_kdf.assert_not_called()
        verifier_kdf.assert_not_called()
        self.assertFalse(pipeline.verifier._pending)
        self.assertFalse(pipeline.verifier.active_session_ids)
        self.assert_no_models(peers)

    def test_decoder_failure_does_not_attempt_verification_or_hkdf(self):
        peers = self.peers()
        failed = ReconstructionResult("decoder_failure", "uncorrectable", -1, None, None, None,
                                      "decoder_declared_failure")
        with patch("puf_snn.pipeline_v2.reconstruct", return_value=failed), \
             patch.object(CredentialAdmissionService, "verify") as verify:
            outcome = peers[0].establish(lambda: REFERENCE, "decoder-failure")
        self.assertEqual((outcome.stage, outcome.reason), ("reconstruction", "failed_reconstruction"))
        verify.assert_not_called()
        self.assertFalse(outcome.request_emitted)
        self.assertEqual(peers[0].sender.kdf_timings_ns, ())
        self.assertEqual(peers[0].verifier.kdf_timings_ns, ())
        self.assert_no_models(peers)

    def test_padding_failure_does_not_emit_request(self):
        peers = self.peers()
        failed = ReconstructionResult("invalid_format_or_padding", "decoded", 1,
                                      (0,) * 35 + (1,), None, False, "nonzero_padding")
        with patch("puf_snn.pipeline_v2.reconstruct", return_value=failed):
            outcome = peers[0].establish(lambda: REFERENCE, "padding-failure")
        self.assertEqual(outcome.stage, "reconstruction")
        self.assertFalse(outcome.request_emitted)
        self.assert_no_models(peers)

    def test_missing_verifier_record_fails_closed(self):
        peers = self.peers(missing_record=True)
        result = peers[0].establish(lambda: REFERENCE, "missing-record")
        self.assertEqual(result.reason, "credential_verification_failed")
        self.assertFalse(result.request_emitted)
        self.assertEqual(peers[0].sender.kdf_timings_ns, ())
        self.assertEqual(peers[0].verifier.kdf_timings_ns, ())
        self.assert_no_models(peers)

    def test_acquisition_exception_is_error_not_false_rejection(self):
        peers = self.peers()
        read = Mock(side_effect=RuntimeError("sensitive-input-do-not-record"))
        with patch("puf_snn.pipeline_v2.reconstruct") as decode:
            with self.assertRaisesRegex(PipelineExecutionError, "response_acquisition: internal_error"):
                peers[0].establish(read, "read-error")
        read.assert_called_once()
        decode.assert_not_called()
        self.assertNotIn("sensitive-input", repr(peers[0].sender.audit_records))
        self.assert_no_models(peers)

    def test_reconstruction_exception_is_error_without_retry_or_secret_text(self):
        peers = self.peers()
        with patch("puf_snn.pipeline_v2.reconstruct", side_effect=RuntimeError("sensitive-backend")) as decode:
            with self.assertRaisesRegex(PipelineExecutionError, "reconstruction: internal_error"):
                peers[0].establish(lambda: REFERENCE, "decode-error")
        decode.assert_called_once()
        self.assertNotIn("sensitive-backend", repr(peers[0].sender.audit_records))
        self.assert_no_models(peers)

    def test_no_implicit_reconstruction_retry(self):
        pipeline = self.peers()[0]
        pipeline.establish(lambda: REFERENCE, "first")
        read_again = Mock(return_value=REFERENCE)
        with self.assertRaisesRegex(ValueError, "one attempt"):
            pipeline.establish(read_again, "second")
        read_again.assert_not_called()

    def test_receiver_refusal_without_authorization_invokes_no_models(self):
        peers = self.peers()
        actual = peers[0].verifier.begin_session
        with patch.object(peers[0].verifier, "begin_session",
                          side_effect=lambda request, local, admission: actual(request, local, admission=None)):
            result = peers[0].establish(lambda: REFERENCE, "missing-authorization")
        self.assertEqual((result.stage, result.reason),
                         ("receiver_admission", "credential_verification_failed"))
        self.assertFalse(peers[0].verifier._pending)
        self.assertEqual(peers[0].verifier.kdf_timings_ns, ())
        self.assert_no_models(peers)

    def test_mutual_confirmation_failure_does_not_authorize_models(self):
        peers = self.peers(receiver_credential=bytes(4))
        result = peers[0].establish(lambda: REFERENCE, "mismatched-registry")
        self.assertEqual((result.stage, result.reason), ("mutual_confirmation", "key_confirmation_failed"))
        self.assertFalse(result.session_active)
        self.assertFalse(peers[0].verifier.active_session_ids)
        self.assert_no_models(peers)

    def test_accepted_record_runs_both_consumers_once(self):
        peers = self.active()
        result = peers[0].process_record(source_record())
        self.assertEqual((result.decision, result.stage, result.sequence_number), ("accept", "inference", 0))
        self.assertEqual(result.inference.motion, "nod")
        self.assertEqual(result.inference.anomaly, {"score": 0.1, "flag": False})
        self.assertEqual(peers[0].calls, ModelCallCounts(1, 1, 1))
        self.assertEqual(peers[0].consumed_event_ids, (result.event_id,))
        self.assertEqual(peers[2].call_args.args[0].shape, (120, 7))
        self.assertEqual(peers[3].call_args.args[0].shape, (48,))

    def test_labels_splits_and_dataset_binding_do_not_reach_preprocessing(self):
        peers = self.active()
        peers[0].process_record(source_record())
        accepted = peers[1].call_args.args[0]
        for name in ("label", "split", "trial_id", "source_trial_id", "attack_type", "severity"):
            self.assertNotIn(name, accepted)
        self.assertEqual(accepted["device_id"], DEVICE)
        self.assertEqual(accepted["session_id"], peers[0].sender.session_id.hex())
        self.assertEqual(accepted["sequence_number"], 0)

    def test_metadata_changes_do_not_change_model_inputs(self):
        first = self.active()
        second = self.active()
        original = source_record()
        changed = deepcopy(original)
        changed.update(label="still", split="train", device_id="other", session_id="other", sequence_number=42,
                       attack_type="fake", severity="fake")
        first[0].process_record(original)
        second[0].process_record(changed)
        np.testing.assert_array_equal(first[2].call_args.args[0], second[2].call_args.args[0])
        np.testing.assert_array_equal(first[3].call_args.args[0], second[3].call_args.args[0])

    def test_models_run_after_sequence_commit(self):
        seen = []
        peers = self.active(motion_callback=lambda _: seen.append(
            peers[0].verifier.session_status(peers[0].sender.session_id).last_accepted))
        peers[0].process_record(source_record())
        self.assertEqual(seen, [0])

    def test_anomaly_flag_does_not_rewrite_authentication(self):
        peers = self.active(anomaly_callback=lambda _: {"score": 0.99, "flag": True})
        result = peers[0].process_record(source_record())
        self.assertEqual(result.decision, "accept")
        self.assertTrue(result.inference.anomaly["flag"])
        status = peers[0].verifier.session_status(peers[0].sender.session_id)
        self.assertEqual((status.accepted_count, status.last_accepted), (1, 0))
        rows = [row for row in peers[0].verifier.audit_records if row["event_type"] == "window"]
        self.assertEqual(rows[-1]["decision"], "accept")
        self.assertNotIn("anomaly", rows[-1])

    def test_bad_tag_calls_neither_model_and_next_valid_packet_still_accepts(self):
        peers = self.active()
        pipeline = peers[0]
        packet = pipeline.sender.seal_window(processed_record_to_wire_window(source_record()))
        envelope = json.loads(packet)
        tag = envelope["authentication"]["tag_hex"]
        envelope["authentication"]["tag_hex"] = ("1" if tag[0] == "0" else "0") + tag[1:]
        before = pipeline.verifier.session_status(pipeline.sender.session_id)
        rejected = pipeline.process_envelope(json.dumps(envelope).encode())
        self.assertEqual(rejected.reason, "invalid_tag")
        self.assertEqual(pipeline.verifier.session_status(pipeline.sender.session_id), before)
        self.assert_no_models(peers)
        self.assertEqual(pipeline.process_envelope(packet).decision, "accept")

    def test_malformed_packet_never_preprocesses(self):
        peers = self.active()
        result = peers[0].process_envelope(b"not-json")
        self.assertEqual(result.decision, "reject")
        self.assert_no_models(peers)

    def test_replayed_packet_does_not_repeat_either_consumer(self):
        peers = self.active()
        pipeline = peers[0]
        packet = pipeline.sender.seal_window(processed_record_to_wire_window(source_record()))
        self.assertEqual(pipeline.process_envelope(packet).decision, "accept")
        before = pipeline.verifier.session_status(pipeline.sender.session_id)
        self.assertEqual(pipeline.process_envelope(packet).decision, "reject")
        self.assertEqual(pipeline.calls, ModelCallCounts(1, 1, 1))
        self.assertEqual(pipeline.verifier.session_status(pipeline.sender.session_id), before)

    def test_same_accepted_result_cannot_be_released_twice(self):
        peers = self.active()
        pipeline = peers[0]
        packet = pipeline.sender.seal_window(processed_record_to_wire_window(source_record()))
        result = pipeline.verifier.verify_window(packet)
        pipeline.release(result)
        with self.assertRaisesRegex(ValueError, "already delivered"):
            pipeline.release(result)
        self.assertEqual(pipeline.calls, ModelCallCounts(1, 1, 1))

    def test_copied_accepted_result_is_not_authority(self):
        peers = self.active()
        packet = peers[0].sender.seal_window(processed_record_to_wire_window(source_record()))
        result = peers[0].verifier.verify_window(packet)
        with self.assertRaisesRegex(ValueError, "not bound"):
            peers[0].release(replace(result))
        self.assert_no_models(peers)
        peers[0].release(result)

    def test_invalid_source_shape_is_adapter_failure_not_model_detection(self):
        peers = self.active()
        source = source_record()
        source["samples"].pop()
        result = peers[0].process_record(source)
        self.assertEqual((result.stage, result.reason),
                         ("processed_record_adapter", "invalid_processed_record"))
        self.assertIsNone(result.event_id)
        self.assertEqual(peers[0].sender.next_to_send, 0)
        self.assert_no_models(peers)

    def test_low_tracking_is_sender_quality_failure_before_tag(self):
        peers = self.active()
        source = source_record()
        for sample in source["samples"][:7]:
            sample["tracking_valid"] = False
        result = peers[0].process_record(source)
        self.assertEqual((result.stage, result.reason), ("sender_sealing", "data_quality_failure"))
        self.assertIsNone(result.event_id)
        self.assertEqual(peers[0].sender.next_to_send, 0)
        self.assert_no_models(peers)

    def test_motion_callback_failure_is_consumed_without_anomaly_or_rollback(self):
        peers = self.active(motion_callback=lambda _: (_ for _ in ()).throw(RuntimeError("model-error")))
        pipeline = peers[0]
        packet = pipeline.sender.seal_window(processed_record_to_wire_window(source_record()))
        result = pipeline.verifier.verify_window(packet)
        with self.assertRaisesRegex(RuntimeError, "consumer failure"):
            pipeline.release(result)
        self.assertEqual(pipeline.calls, ModelCallCounts(1, 1, 0))
        self.assertTrue(pipeline.verifier.incomplete)
        self.assertEqual(pipeline.verifier.session_status(pipeline.sender.session_id).last_accepted, 0)
        with self.assertRaisesRegex(ValueError, "already delivered"):
            pipeline.release(result)
        self.assertEqual(pipeline.calls, ModelCallCounts(1, 1, 0))

    def test_anomaly_callback_failure_is_consumed_without_retry(self):
        peers = self.active(anomaly_callback=lambda _: (_ for _ in ()).throw(RuntimeError("anomaly-error")))
        pipeline = peers[0]
        packet = pipeline.sender.seal_window(processed_record_to_wire_window(source_record()))
        result = pipeline.verifier.verify_window(packet)
        with self.assertRaisesRegex(RuntimeError, "consumer failure"):
            pipeline.release(result)
        with self.assertRaisesRegex(ValueError, "already delivered"):
            pipeline.release(result)
        self.assertEqual(pipeline.calls, ModelCallCounts(1, 1, 1))
        self.assertTrue(pipeline.verifier.incomplete)

    def test_actual_snn_forward_path_and_real_anomaly_features(self):
        # Untrained architecture fixture: verifies execution/shape, NOT accuracy.
        model = RecurrentLifClassifier(7, 32, 5, 0.9, 1.0, 25.0).eval()
        def motion(sequence):
            with torch.inference_mode():
                scores = model(torch.from_numpy(sequence[None]).to(dtype=torch.float32))
            self.assertEqual(tuple(scores.shape), (1, 5))
            self.assertTrue(torch.isfinite(scores).all().item())
            return int(scores.argmax(dim=1).item())
        def anomaly(features):
            self.assertEqual(features.shape, (48,))
            self.assertTrue(np.isfinite(features).all())
            return {"fixture_only": True}
        peers = self.active(motion_callback=motion, anomaly_callback=anomaly)
        result = peers[0].process_record(source_record())
        self.assertIn(result.inference.motion, range(5))
        self.assertEqual(peers[0].calls, ModelCallCounts(1, 1, 1))

    def test_public_attempt_summary_has_no_candidate_or_response_material(self):
        pipeline = self.peers()[0]
        result = pipeline.establish(lambda: REFERENCE, "public-summary")
        self.assertEqual(set(asdict(result)), {"decision", "stage", "reason", "reconstruction_outcome",
                                              "request_emitted", "session_active"})
        self.assertNotIn(CREDENTIAL.hex(), json.dumps(asdict(result)))


if __name__ == "__main__":
    unittest.main()
