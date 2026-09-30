"""Current local admission profile; synthetic fixtures except two saved regressions.

No formal reconstruction/evaluation run. Deterministic keys below are nonsecret.
"""
from contextlib import ExitStack, contextmanager
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import pickle
import unittest
from unittest.mock import patch

from puf_snn.auth import session
from puf_snn.auth.sender import Sender
from puf_snn.auth.verifier import Verifier
from puf_snn.auth.credential_verifier import (
    CredentialAdmissionService, CredentialVerifierRecord, CredentialVerifierStore,
    InMemoryCredentialVerifierKeyProvider, LocalAdmissionAuthorization,
)
from puf_snn.auth.binary_window import F32, Sample, Window
from puf_snn.reconstruction import HelperData, ReconstructionResult, enroll, reconstruct

ROOT = Path(__file__).resolve().parents[2]
CREDENTIAL = b"\x00\x00\x01\xa5"  # SYNTHETIC / NONSECRET
PROFILE = "puf-snn-reconstruction-v1"


def candidate(value=CREDENTIAL):
    bits = tuple((byte >> shift) & 1 for byte in value for shift in range(7, -1, -1)) + (0,)*4
    return ReconstructionResult("candidate_valid_format", "decoded", 0, bits, value, True, None)


def provisioning(device="Device-A", enrollment="enrollment-1", credential=CREDENTIAL):
    provider = InMemoryCredentialVerifierKeyProvider("synthetic-key", bytes(range(32)))
    record = CredentialVerifierRecord.enroll(
        device_id=device, enrollment_id=enrollment, reconstruction_id=PROFILE,
        verifier_key_id="synthetic-key", credential4=credential, key_provider=provider,
    )
    return record, provider


class CredentialAdmissionTests(unittest.TestCase):
    def peers(self, *, record=None, provider=None, base=False, device="Device-A",
              enrollment="enrollment-1", credential=CREDENTIAL, missing=False, helper=None):
        original, default_provider = provisioning(device, enrollment, credential)
        provider = provider if provider is not None else default_provider
        record = record if record is not None else original
        service = CredentialAdmissionService(CredentialVerifierStore([] if missing else [record]), provider)
        binding = session.provision_device(device, enrollment,
            enroll((0,)*64, credential, enrollment_id=enrollment) if helper is None else helper)
        sender_type, receiver_type = (session.Sender, session.Verifier) if base else (Sender, Verifier)
        sender = sender_type(binding, admission_service=service)
        receiver = receiver_type([session.RegistryEntry(device, enrollment, credential)], admission_service=service)
        return sender, receiver, service

    @contextmanager
    def zero_work(self):
        """Assert calls after execution too: production can catch a raised spy."""
        names = ["session.derive_session_key", "sender.derive_session_key", "verifier.derive_session_key",
                 "session.hkdf_extract", "session.hkdf_expand", "session.client_proof", "session.server_proof",
                 "session._Pending", "session._Active"]
        with ExitStack() as stack:
            spies = [stack.enter_context(patch("puf_snn.auth." + name,
                     side_effect=AssertionError("unexpected protected operation"))) for name in names]
            frame = stack.enter_context(patch("puf_snn.auth.session.frame", wraps=session.frame))
            yield
            for name, spy in zip(names, spies):
                self.assertEqual(spy.call_count, 0, name)
            self.assertEqual(frame.call_count, 0, "request/challenge/confirmation frame created")

    def reject_candidate(self, sender, receiver, result, reason="credential_verification_failed"):
        with self.zero_work(), patch("puf_snn.auth.session.secrets.token_bytes",
                                      side_effect=AssertionError("request randomness")) as random:
            self.assertEqual(sender.begin_attempt(result, "negative-attempt"), session.Failure(reason))
            random.assert_not_called()
        self.assertEqual(sender.state, "FAILED")
        self.assertIsNone(sender.admission)
        self.assertIsNone(sender._candidate)
        self.assertIsNone(sender._key)
        self.assertIsNone(sender._request)
        self.assertFalse(receiver._pending)
        self.assertFalse(receiver.active_session_ids)

    def reject_request(self, receiver, request, authorization=None):
        pending, active = dict(receiver._pending), dict(receiver._active)
        with self.zero_work():
            self.assertEqual(receiver.begin_session(request, admission=authorization), session.REFUSAL)
        self.assertEqual(receiver.last_reason, "credential_verification_failed")
        self.assertEqual(receiver._pending, pending)
        self.assertEqual(receiver._active, active)

    def test_correct_reconstructed_candidate_one_derivation_each_and_window(self):
        sender, receiver, service = self.peers()
        result = reconstruct((0,)*64, sender.enrollment.helper_data)
        targets = ["session.derive_session_key", "sender.derive_session_key", "verifier.derive_session_key",
                   "session.hkdf_extract", "session.hkdf_expand", "session.client_proof", "session.server_proof",
                   "session._Pending", "session._Active", "session.frame"]
        import importlib
        original_verify = CredentialAdmissionService.verify
        with ExitStack() as stack:
            spies = {}
            for target in targets:
                module, attr = target.split(".")
                actual = getattr(importlib.import_module("puf_snn.auth."+module), attr)
                spies[target] = stack.enter_context(patch("puf_snn.auth."+target, wraps=actual))
            verify = stack.enter_context(patch.object(CredentialAdmissionService, "verify", autospec=True,
                                                      side_effect=original_verify))
            request = sender.begin_attempt(result, "positive-attempt")
            authorization = sender.admission
            self.assertIs(type(authorization), LocalAdmissionAuthorization)
            self.assertEqual(len(service._admissions), 1)
            self.assertIs(sender._candidate, result.candidate_credential)
            challenge = receiver.begin_session(request, admission=authorization)
            self.assertTrue(service._admissions[authorization].consumed)
            proof = sender.answer_challenge(challenge)
            self.assertNotIn(authorization, service._admissions)
            self.assertIs(sender.finish_session(receiver.confirm_session(proof)), sender)
            self.assertEqual(verify.call_count, 1)
            # Audited endpoints use their imported aliases, not the original name.
            for name, count in {"session.derive_session_key": 0, "sender.derive_session_key": 1,
                                "verifier.derive_session_key": 1, "session.hkdf_extract": 2,
                                "session.hkdf_expand": 2, "session.client_proof": 2,
                                "session.server_proof": 2, "session._Pending": 1, "session._Active": 1}.items():
                self.assertEqual(spies[name].call_count, count, name)
            self.assertEqual([call.args[0][:4] for call in spies["session.frame"].call_args_list],
                             [b"P3RQ", b"P3CH", b"P3CF", b"P3OK"])
        zero, one = F32(0), F32(0x3f800000)
        samples = tuple(Sample(i, 1_000_000_000+i*16_666_667, (zero,)*3, (zero,zero,zero,one), True)
                        for i in range(120))
        window = Window("unused", bytes(16), 0, "window-1", 1_000_000_000, 3_000_000_000,
                        120, 1_000_000, samples)
        accepted = receiver.verify_window(sender.seal_window(window))
        self.assertEqual(accepted.result, "accept")
        self.assertEqual(receiver.release_accepted(accepted, lambda w: w.sequence_number), 0)

    def test_correct_base_endpoints_use_common_derivation_twice(self):
        sender, receiver, _ = self.peers(base=True)
        with patch("puf_snn.auth.session.derive_session_key", wraps=session.derive_session_key) as derive:
            request = sender.begin_attempt(candidate(), "base-positive")
            proof = sender.answer_challenge(receiver.begin_session(request, admission=sender.admission))
            self.assertIs(sender.finish_session(receiver.confirm_session(proof)), sender)
            self.assertEqual(derive.call_count, 2)

    def test_wrong_valid_format_zero_work_base_and_audited(self):
        for base in (False, True):
            with self.subTest(base=base):
                sender, receiver, _ = self.peers(base=base)
                self.reject_candidate(sender, receiver, candidate(bytes(4)))

    def saved_miscorrection(self, seed, device_index, attempt, line_number):
        directory = ROOT / "results/week-5/will/reconstruction/layer2-experiment-v1-formal-001"
        manifest = json.loads((directory / "manifest.json").read_text())
        selected = None
        # Verify this checkout's known CRLF representation without writing it.
        for name in ("attempts.jsonl", "enrollments.json"):
            data = (directory/name).read_bytes()
            self.assertIn(manifest[name], (hashlib.sha256(data).hexdigest(),
                                          hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()))
            if name == "attempts.jsonl":
                selected = json.loads(data.splitlines()[line_number-1])
        self.assertEqual((selected["simulation_seed"], selected["device_index"], selected["attempt_number"]),
                         (seed, device_index, attempt))
        self.assertEqual(selected["evaluator_outcome"], "evaluator_wrong_match")
        enrolled = next(r for r in json.loads((directory/"enrollments.json").read_text())
                        if r["enrollment_id"] == selected["enrollment_id"])
        credential = bytes.fromhex(enrolled["evaluator_enrolled_credential_hex"])
        sender, receiver, _ = self.peers(device=selected["device_id"], enrollment=selected["enrollment_id"],
            credential=credential, helper=HelperData(tuple(map(int, enrolled["helper63"])),
                                                      enrollment_id=selected["enrollment_id"]))
        result = ReconstructionResult(selected["reconstruction_outcome"], selected["decoder_status"],
            selected["reported_correction_count"], tuple(map(int, selected["candidate_message36"])),
            bytes.fromhex(selected["candidate_credential_hex"]), selected["padding_valid"],
            selected["reconstruction_failure_reason"])
        with patch("puf_snn.reconstruction.reconstruct", side_effect=AssertionError("no reconstruction")) as decode:
            self.reject_candidate(sender, receiver, result)
            decode.assert_not_called()

    def test_nominal_seed_2222_device_3_attempt_88(self):
        self.saved_miscorrection(2222, 3, 88, 2789)

    def test_nominal_seed_6543_device_1_attempt_75(self):
        self.saved_miscorrection(6543, 1, 75, 7976)

    def test_decoder_failure_never_invokes_verifier(self):
        sender, receiver, _ = self.peers()
        result = ReconstructionResult("decoder_failure", "uncorrectable", -1, None, None, None, "decoder_declared_failure")
        with self.zero_work(), patch.object(CredentialAdmissionService, "verify") as verify:
            self.assertEqual(sender.begin_attempt(result, "decoder-fail"),
                             session.Failure("failed_reconstruction", "decoder_failure"))
            verify.assert_not_called()
        self.assertFalse(receiver._pending)

    def test_padding_failure_never_invokes_verifier(self):
        sender, receiver, _ = self.peers()
        result = ReconstructionResult("invalid_format_or_padding", "decoded", 1, (0,)*35+(1,), None, False, "nonzero_padding")
        with self.zero_work(), patch.object(CredentialAdmissionService, "verify") as verify:
            self.assertEqual(sender.begin_attempt(result, "padding-fail"),
                             session.Failure("failed_reconstruction", "invalid_format_or_padding"))
            verify.assert_not_called()
        self.assertFalse(receiver._pending)

    def test_missing_record(self):
        sender, receiver, _ = self.peers(missing=True)
        self.reject_candidate(sender, receiver, candidate())

    def test_disabled_record(self):
        record, _ = provisioning()
        sender, receiver, _ = self.peers(record=replace(record, enabled=False))
        self.reject_candidate(sender, receiver, candidate())

    def test_revoked_record(self):
        record, _ = provisioning()
        sender, receiver, _ = self.peers(record=replace(record, revoked=True))
        self.reject_candidate(sender, receiver, candidate())

    def test_wrong_verifier_key(self):
        sender, receiver, _ = self.peers(provider=InMemoryCredentialVerifierKeyProvider("synthetic-key", b"z"*32))
        self.reject_candidate(sender, receiver, candidate())

    def test_device_binding_mismatch(self):
        record, _ = provisioning()
        sender, receiver, _ = self.peers(record=replace(record, device_id="Device-B"))
        self.reject_candidate(sender, receiver, candidate())

    def test_enrollment_binding_mismatch(self):
        record, _ = provisioning()
        sender, receiver, _ = self.peers(record=replace(record, enrollment_id="enrollment-2"))
        self.reject_candidate(sender, receiver, candidate())

    def test_reconstruction_binding_mismatch(self):
        record, _ = provisioning()
        sender, receiver, _ = self.peers(record=replace(record, reconstruction_id="other-profile"))
        self.reject_candidate(sender, receiver, candidate())

    def test_receiver_missing_authorization_base_and_audited(self):
        for base in (False, True):
            with self.subTest(base=base):
                sender, receiver, _ = self.peers(base=base)
                request = sender.begin_attempt(candidate(), "attempt-1")
                self.reject_request(receiver, request)

    def test_forged_authorization_and_boolean(self):
        sender, receiver, _ = self.peers()
        request = sender.begin_attempt(candidate(), "attempt-1")
        for fake in (True, {"verified": True}, object.__new__(LocalAdmissionAuthorization)):
            self.reject_request(receiver, request, fake)
        with self.assertRaises(TypeError):
            LocalAdmissionAuthorization()

    def test_foreign_service_authorization(self):
        sender, _, _ = self.peers()
        _, receiver, _ = self.peers()
        self.reject_request(receiver, sender.begin_attempt(candidate(), "attempt-1"), sender.admission)

    def test_request_swap(self):
        sender, receiver, _ = self.peers()
        request = sender.begin_attempt(candidate(), "attempt-1")
        self.reject_request(receiver, request[:-1] + bytes([request[-1]^1]), sender.admission)

    def test_authorization_device_swap_at_receiver(self):
        sender, receiver, _ = self.peers()
        receiver._registry["Device-B"] = session.RegistryEntry("Device-B", "enrollment-1", CREDENTIAL)
        request = sender.begin_attempt(candidate(), "attempt-1").replace(b"Device-A", b"Device-B")
        self.reject_request(receiver, request, sender.admission)

    def test_receiver_enrollment_generation_changed(self):
        sender, receiver, _ = self.peers()
        request = sender.begin_attempt(candidate(), "attempt-1")
        receiver._registry["Device-A"] = session.RegistryEntry("Device-A", "enrollment-2", CREDENTIAL)
        self.reject_request(receiver, request, sender.admission)

    def test_authorization_replay_across_receivers(self):
        sender, receiver, service = self.peers()
        request = sender.begin_attempt(candidate(), "attempt-1")
        authorization = sender.admission
        challenge = receiver.begin_session(request, admission=authorization)
        self.assertEqual(challenge[4:8], b"P3CH")
        second = Verifier(list(receiver._registry.values()), admission_service=service)
        self.reject_request(second, request, authorization)
        proof = sender.answer_challenge(challenge)
        self.assertIs(sender.finish_session(receiver.confirm_session(proof)), sender)

    def test_stale_authorization(self):
        sender, receiver, service = self.peers()
        request = sender.begin_attempt(candidate(), "attempt-1")
        expiry = service._admissions[sender.admission].deadline_ns
        with patch("puf_snn.auth.credential_verifier.time.monotonic_ns", return_value=expiry):
            self.reject_request(receiver, request, sender.admission)

    def test_revoked_authorization(self):
        sender, receiver, service = self.peers()
        request = sender.begin_attempt(candidate(), "attempt-1")
        service.revoke(sender.admission)
        self.reject_request(receiver, request, sender.admission)

    def test_revoked_enrollment_rejects_handle_and_future_candidates(self):
        sender, receiver, service = self.peers()
        request = sender.begin_attempt(candidate(), "attempt-1")
        service.revoke_enrollment("Device-A", "enrollment-1")
        self.reject_request(receiver, request, sender.admission)
        fresh = Sender(sender.enrollment, admission_service=service)
        self.reject_candidate(fresh, receiver, candidate())

    def test_candidate_swap_detected_before_sender_hkdf(self):
        sender, receiver, _ = self.peers()
        request = sender.begin_attempt(candidate(), "attempt-1")
        challenge = receiver.begin_session(request, admission=sender.admission)
        # Receiver already derived once from its enrolled credential. No sender
        # derivation may follow a swap, and no confirmation/activation occurs.
        sender._candidate = bytes(4)
        with self.zero_work():
            self.assertEqual(sender.answer_challenge(challenge), session.Failure("credential_verification_failed"))
        self.assertEqual(len(receiver.kdf_timings_ns), 1)
        self.assertEqual(sender.kdf_timings_ns, ())
        self.assertFalse(receiver.active_session_ids)

    def test_challenge_session_context_swap(self):
        sender, receiver, _ = self.peers()
        request = sender.begin_attempt(candidate(), "attempt-1")
        challenge = receiver.begin_session(request, admission=sender.admission)
        reader = session.unframe(challenge); reader.expect(b"P3CH")
        transcript = session.Transcript.parse(reader.lp())
        forged = session.frame(b"P3CH" + session.LP(replace(transcript, session_id=b"q"*16).encode()))
        with self.zero_work():
            self.assertEqual(sender.answer_challenge(forged), session.Failure("credential_verification_failed"))

    def test_sender_cannot_derive_before_receiver_consumption(self):
        sender, receiver, _ = self.peers()
        sender.begin_attempt(candidate(), "attempt-1")
        context = session.Transcript("Device-A", sender._nonce, bytes(16), b"q"*16, bytes(32))
        challenge = session.frame(b"P3CH" + session.LP(context.encode()))
        with self.zero_work():
            self.assertEqual(sender.answer_challenge(challenge), session.Failure("credential_verification_failed"))
        self.assertFalse(receiver._pending)

    def test_existing_active_session_survives_failed_new_candidate(self):
        sender, receiver, service = self.peers()
        request = sender.begin_attempt(candidate(), "attempt-1")
        proof = sender.answer_challenge(receiver.begin_session(request, admission=sender.admission))
        sender.finish_session(receiver.confirm_session(proof))
        before = dict(receiver._active)
        fresh = Sender(sender.enrollment, admission_service=service)
        with self.zero_work():
            self.assertEqual(fresh.begin_attempt(candidate(bytes(4)), "attempt-2"),
                             session.Failure("credential_verification_failed"))
        self.assertEqual(receiver._active, before)

    def test_client_confirmation_tamper_still_rejected(self):
        sender, receiver, _ = self.peers()
        request = sender.begin_attempt(candidate(), "attempt-1")
        proof = sender.answer_challenge(receiver.begin_session(request, admission=sender.admission))
        self.assertEqual(receiver.confirm_session(proof[:-1]+bytes([proof[-1]^1])), session.REFUSAL)
        self.assertEqual(receiver.last_reason, "key_confirmation_failed")
        self.assertFalse(receiver.active_session_ids)

    def test_server_confirmation_tamper_still_rejected(self):
        sender, receiver, _ = self.peers()
        request = sender.begin_attempt(candidate(), "attempt-1")
        proof = sender.answer_challenge(receiver.begin_session(request, admission=sender.admission))
        ack = receiver.confirm_session(proof)
        self.assertEqual(sender.finish_session(ack[:-1]+bytes([ack[-1]^1])), session.Failure("key_confirmation_failed"))
        self.assertEqual(sender.state, "FAILED")

    def test_handle_repr_serialization_and_no_wire_addition(self):
        sender, _, service = self.peers()
        request = sender.begin_attempt(candidate(), "attempt-1")
        handle = sender.admission
        self.assertEqual(request, session.frame(b"P3RQ"+session.V(2,0)+session.LP(b"Device-A")+sender._nonce))
        for value in (handle, service):
            self.assertNotIn(CREDENTIAL.hex(), repr(value))
        with self.assertRaises(TypeError):
            pickle.dumps(handle)
        with self.assertRaises(AttributeError):
            handle.verified = True

    def test_sender_audit_failure_revokes_unemitted_authorization(self):
        sender, receiver, service = self.peers()
        with patch.object(sender._audit, "prepare", side_effect=MemoryError):
            self.assertEqual(sender.begin_attempt(candidate(), "attempt-1"), session.Failure("internal_error"))
        self.assertFalse(service._admissions)
        self.assertIsNone(sender.admission)
        self.assertFalse(receiver._pending)

    def test_request_construction_failure_clears_base_admission(self):
        sender, receiver, service = self.peers(base=True)
        with patch("puf_snn.auth.session.frame", side_effect=MemoryError):
            self.assertEqual(sender.begin_attempt(candidate(), "frame-failure"), session.Failure("internal_error"))
        self.assertEqual(sender.state, "FAILED")
        self.assertIsNone(sender._candidate)
        self.assertIsNone(sender.admission)
        self.assertFalse(service._admissions)
        self.assertFalse(receiver._pending)

    def test_sender_attempt_identity_swap(self):
        sender, receiver, _ = self.peers()
        request = sender.begin_attempt(candidate(), "attempt-1")
        challenge = receiver.begin_session(request, admission=sender.admission)
        sender.attempt_id = "attempt-2"
        with self.zero_work():
            self.assertEqual(sender.answer_challenge(challenge), session.Failure("credential_verification_failed"))
        self.assertEqual(sender.kdf_timings_ns, ())

    def test_missing_service_cannot_create_supported_endpoint(self):
        sender, _, _ = self.peers()
        with self.assertRaises(TypeError):
            Sender(sender.enrollment)
        with self.assertRaises(TypeError):
            Verifier([])


if __name__ == "__main__":
    unittest.main()
