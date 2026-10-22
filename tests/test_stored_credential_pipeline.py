"""Bounded functional controls, not reliability/latency experiments.

All credential/key/response fixtures are public synthetic material. Handshake
randomness remains the OS default; transcript equality is deliberately untested.
"""
from contextlib import contextmanager, ExitStack
from dataclasses import asdict, FrozenInstanceError, replace
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from jsonschema import Draft202012Validator

from auth.support import window, wrap
from puf_snn.auth import session
from puf_snn.auth.audit import Provenance
from puf_snn.auth.binary_window import F32, encode_window, parse_envelope
from puf_snn.auth.credential_verifier import (
    CredentialAdmissionService, CredentialVerifierRecord, CredentialVerifierStore,
    InMemoryCredentialVerifierKeyProvider, LocalAdmissionAuthorization,
)
from puf_snn.auth.sender import Sender
from puf_snn.auth.stored_credential import (
    InMemoryStoredCredentialProvider, StoredCredentialRecord, StoredCredentialStatus,
)
from puf_snn.auth.verifier import Verifier, VerificationResult
from puf_snn.pipeline_v2 import ModelCallCounts, PipelineExecutionError, V2InferencePipeline
from puf_snn.puf.acquisition import MAJORITY_3, SINGLE_READ
from puf_snn.reconstruction import BCHCodec, enroll, reconstruct


CREDENTIAL = b"\x00\x00\x01\xa5"
REFERENCE = (0,) * 64
DEVICE, ENROLLMENT = "sim-device", "stored-control-enrollment"
BINDING = dict(device_id=DEVICE, enrollment_id=ENROLLMENT,
               reconstruction_id="puf-snn-reconstruction-v1")
ROOT = Path(__file__).resolve().parents[1]


def stored_record(credential=CREDENTIAL, **changes):
    return StoredCredentialRecord(**(BINDING | changes), credential4=credential)


def source(credential=CREDENTIAL):
    return InMemoryStoredCredentialProvider([stored_record(credential)])


class StoredProviderTests(unittest.TestCase):
    def test_exact_binding_persistent_lookup_and_redaction(self):
        record = stored_record()
        provider = InMemoryStoredCredentialProvider([record])
        self.assertIs(provider.get_credential(**BINDING), record)
        self.assertIs(provider.get_credential(**BINDING), record)
        for key in BINDING:
            self.assertIsNone(provider.get_credential(**(BINDING | {key: "other"})))
        self.assertEqual(repr(record), "StoredCredentialRecord(<redacted>)")
        self.assertEqual(repr(provider), "InMemoryStoredCredentialProvider(<redacted>)")
        with self.assertRaises(FrozenInstanceError):
            record.credential4 = bytes(4)
        with self.assertRaises(TypeError):
            provider._records[tuple(BINDING.values())] = record

    def test_strict_record_validation_and_no_secret_in_errors(self):
        for value in (None, "private-secret", bytearray(4), b"", bytes(3), bytes(5), 1234):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaisesRegex(ValueError, "^malformed_stored_credential$"):
                    stored_record(value)
        for key in BINDING:
            for value in (None, "", "invalid id", 123):
                with self.assertRaisesRegex(ValueError, "^malformed_stored_credential$"):
                    stored_record(**{key: value})

    def test_duplicate_and_nonrecord_provisioning_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate_stored_credential"):
            InMemoryStoredCredentialProvider([stored_record(), stored_record()])
        for value in (CREDENTIAL, {}, object()):
            with self.assertRaisesRegex(ValueError, "malformed_stored_credential"):
                InMemoryStoredCredentialProvider([value])


class StoredPipelineTests(unittest.TestCase):
    def peers(self, *, policy=SINGLE_READ, missing=False, disabled=False, revoked=False,
              device=DEVICE, enrollment=ENROLLMENT, other_device=False):
        # Enrollment/encoding/key provisioning are fixture setup, before spies.
        helper = enroll(REFERENCE, CREDENTIAL, enrollment_id=enrollment)
        key = InMemoryCredentialVerifierKeyProvider("stored-test-key", bytes(range(32)))
        record = CredentialVerifierRecord.enroll(
            device_id=device, enrollment_id=enrollment, reconstruction_id=helper.config.version,
            verifier_key_id="stored-test-key", credential4=CREDENTIAL, key_provider=key)
        record = replace(record, enabled=not disabled, revoked=revoked)
        service = CredentialAdmissionService(CredentialVerifierStore([] if missing else [record]), key)
        sender = Sender(session.provision_device(device, enrollment, helper), admission_service=service)
        entries = [session.RegistryEntry(device, enrollment, CREDENTIAL)]
        if other_device:
            entries.append(session.RegistryEntry("other-device", "other-enrollment", CREDENTIAL))
        verifier = Verifier(entries, admission_service=service)
        pipeline = V2InferencePipeline(sender, verifier, Mock(side_effect=lambda r: (r, r)),
                   Mock(return_value="motion"), Mock(return_value="anomaly"), acquisition_config=policy)
        return pipeline, service, key

    @contextmanager
    def no_source_work(self):
        names = ("puf_snn.pipeline_v2.acquire_response", "puf_snn.puf.acquisition.acquire_response",
                 "puf_snn.puf.acquisition.majority_vote3", "puf_snn.puf.ro_puf.generate_response",
                 "puf_snn.puf.ro_puf.calculate_frequencies", "puf_snn.pipeline_v2.reconstruct",
                 "puf_snn.reconstruction.credential.reconstruct",
                 "puf_snn.reconstruction.credential.ReconstructionResult")
        with ExitStack() as stack:
            spies = [stack.enter_context(patch(name, side_effect=AssertionError("forbidden source work")))
                     for name in names]
            spies += [stack.enter_context(patch.object(BCHCodec, name,
                      side_effect=AssertionError("forbidden BCH work"))) for name in ("encode", "decode")]
            yield
            for spy in spies:
                spy.assert_not_called()  # Also detect calls swallowed by fail-closed code.

    @contextmanager
    def no_protected_work(self, pipeline, *, expect_no_authority=True):
        names = ("puf_snn.auth.sender.derive_session_key", "puf_snn.auth.verifier.derive_session_key",
                 "puf_snn.auth.session.derive_session_key", "puf_snn.auth.session.hkdf_extract",
                 "puf_snn.auth.session.hkdf_expand", "puf_snn.auth.session._Pending",
                 "puf_snn.auth.session._Active", "puf_snn.auth.session.client_proof",
                 "puf_snn.auth.session.server_proof", "puf_snn.auth.session.frame")
        with ExitStack() as stack:
            spies = [stack.enter_context(patch(name, side_effect=AssertionError("forbidden protected work")))
                     for name in names]
            yield
            for spy in spies:
                spy.assert_not_called()
        if expect_no_authority:
            self.assert_no_authority(pipeline)

    def assert_no_authority(self, pipeline):
        self.assertIsNone(pipeline.sender._candidate)
        self.assertIsNone(pipeline.sender._request)
        self.assertIsNone(pipeline.sender._key)
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

    def active(self, **kwargs):
        pipeline, _, _ = self.peers(**kwargs)
        self.assertTrue(pipeline.establish_stored(source(), "stored-active").session_active)
        return pipeline

    def test_real_verification_authorization_handshake_and_release_without_puf_bch(self):
        pipeline, service, key = self.peers(policy=MAJORITY_3)
        with self.no_source_work(), ExitStack() as stack:
            spies = {name: stack.enter_context(patch.object(CredentialAdmissionService, name,
                                                          side_effect=getattr(service, name)))
                     for name in ("verify", "authorize_with_outcome", "bind_request", "consume",
                                  "bind_challenge", "claim_candidate")}
            key_lookup = stack.enter_context(patch.object(type(key), "get_key", autospec=True,
                                             side_effect=type(key).get_key))
            result = pipeline.establish_stored(source(), "stored-positive")
            self.assertEqual((result.decision, result.stage), ("accept", "active_session"))
            self.assertTrue(result.request_emitted)
            self.assertIsNone(result.reconstruction_outcome)
            self.assertEqual(result.credential_status, StoredCredentialStatus(
                "success", "verified", "authorized", attempt_id="stored-positive"))
            self.assertIs(result.credential_status, pipeline.sender.prepared_stored_credential_status)
            for spy in spies.values():
                self.assertEqual(spy.call_count, 1)
            key_lookup.assert_called_once()
        self.assertEqual(len(pipeline.sender.kdf_timings_ns), 1)
        self.assertEqual(len(pipeline.verifier.kdf_timings_ns), 1)
        self.assertFalse(service._admissions)  # Claimed/revoked after actual consumption.
        packet = pipeline.sender.seal_window(window(pipeline.sender.session_id))
        self.assertEqual(pipeline.process_envelope(packet).decision, "accept")
        self.assertEqual(pipeline.calls, ModelCallCounts(1, 1, 1))
        # v1 coarse control audit plus explicit secret-free source status; no BCH event/timing.
        rows = pipeline.sender.audit_records
        self.assertEqual(rows[0]["event_type"], "session_control")
        self.assertFalse(any(r["event_type"] == "reconstruction" for r in rows))
        self.assertTrue(all(r["latency_ns"]["reconstruction"] is None for r in rows))
        validator = Draft202012Validator(json.loads((ROOT/"schemas/auth-audit-v1.schema.json").read_text()))
        for row in rows:
            validator.validate(row)
        serialized = json.dumps(asdict(result)) + json.dumps(rows)
        self.assertNotIn(CREDENTIAL.hex(), serialized)
        self.assertNotIn("candidate_credential", serialized)

    def test_wrong_credential_rejected_by_real_verifier_before_request_and_hkdf(self):
        pipeline, service, _ = self.peers()
        with self.no_source_work(), self.no_protected_work(pipeline), \
             patch.object(CredentialAdmissionService, "verify", side_effect=service.verify) as verify:
            result = pipeline.establish_stored(source(bytes(4)), "stored-wrong")
            self.assertEqual(result.reason, "credential_verification_failed")
            self.assertEqual(result.credential_status.verification_outcome, "credential_mismatch")
            self.assertEqual(result.credential_status.admission_outcome, "refused")
            self.assertFalse(result.request_emitted)
            verify.assert_called_once()
        self.assertFalse(pipeline.sender.incomplete)

    def test_missing_lookup_never_verifies_or_falls_back(self):
        pipeline, service, _ = self.peers()
        with self.no_source_work(), self.no_protected_work(pipeline), patch.object(CredentialAdmissionService, "verify") as verify:
            result = pipeline.establish_stored(InMemoryStoredCredentialProvider(), "stored-missing")
            self.assertEqual((result.stage, result.reason),
                             ("credential_retrieval", "stored_credential_unavailable"))
            self.assertEqual(result.credential_status, StoredCredentialStatus("unavailable", attempt_id="stored-missing"))
            verify.assert_not_called()

    def test_each_mismatched_lookup_binding_is_unavailable(self):
        for key in BINDING:
            pipeline, _, _ = self.peers()
            provider = InMemoryStoredCredentialProvider([stored_record(**{key: "other"})])
            with self.no_source_work(), self.no_protected_work(pipeline):
                result = pipeline.establish_stored(provider, "wrong-binding")
                self.assertEqual(result.credential_status.retrieval_outcome, "unavailable")

    def test_malformed_provider_results_and_imported_records_never_verify(self):
        malformed = []
        for value in (None, bytearray(4), "private-secret", bytes(3), bytes(5)):
            record = stored_record()
            object.__setattr__(record, "credential4", value)  # Corrupt trusted import fixture.
            malformed.append(record)
        malformed += [CREDENTIAL, {}, object(), stored_record(device_id="wrong-device"),
                      stored_record(enrollment_id="wrong-enrollment"),
                      stored_record(reconstruction_id="wrong-profile")]
        for record in malformed:
            pipeline, service, _ = self.peers()
            with self.no_source_work(), self.no_protected_work(pipeline), patch.object(CredentialAdmissionService, "verify") as verify:
                result = pipeline.establish_stored(Mock(get_credential=Mock(return_value=record)), "malformed")
                self.assertEqual(result.reason, "stored_credential_malformed")
                self.assertEqual(result.credential_status.retrieval_outcome, "malformed")
                verify.assert_not_called()

    def test_disabled_revoked_and_service_revoked_enrollment_refuse(self):
        for options in ({"disabled": True}, {"revoked": True}, {}):
            pipeline, service, _ = self.peers(**options)
            if not options:
                service.revoke_enrollment(DEVICE, ENROLLMENT)
            with self.no_protected_work(pipeline):
                result = pipeline.establish_stored(source(), "disabled")
                self.assertEqual(result.credential_status.verification_outcome, "record_disabled")
                self.assertEqual(result.reason, "credential_verification_failed")
                self.assertFalse(pipeline.sender.incomplete)

    def test_missing_verifier_record_is_distinct_incomplete_configuration_fault(self):
        pipeline, _, _ = self.peers(missing=True)
        with self.no_protected_work(pipeline), self.assertRaises(PipelineExecutionError):
            pipeline.establish_stored(source(), "verifier-unavailable")
        self.assertEqual(pipeline.sender.stored_credential_status.verification_outcome, "record_missing")
        self.assertTrue(pipeline.sender.incomplete)

    def test_revocation_between_verification_and_issuance_is_policy_refusal(self):
        pipeline, service, _ = self.peers()
        original = service.verify

        def verify_then_revoke(*args, **kwargs):
            result = original(*args, **kwargs)
            service.revoke_enrollment(DEVICE, ENROLLMENT)
            return result

        with patch.object(CredentialAdmissionService, "verify", side_effect=verify_then_revoke), \
             self.no_protected_work(pipeline):
            result = pipeline.establish_stored(source(), "revoked-after-check")
        self.assertEqual(result.credential_status, StoredCredentialStatus(
            "success", "verified", "refused", attempt_id="revoked-after-check"))
        self.assertFalse(pipeline.sender.incomplete)

    def test_audit_failure_revokes_unemitted_stored_authorization(self):
        pipeline, _, _ = self.peers()
        with patch.object(pipeline.sender._audit, "prepare", side_effect=MemoryError("private-audit")), \
             self.assertRaises(PipelineExecutionError):
            pipeline.establish_stored(source(), "audit-fault")
        self.assert_no_authority(pipeline)
        self.assertTrue(pipeline.sender.incomplete)
        self.assertEqual(pipeline.sender.audit_records[0]["event_type"], "session_control")
        self.assertEqual(pipeline.sender.audit_records[0]["reason"], "internal_error")

    def test_reused_stored_attempt_id_clears_sender_keys_and_stops_audit(self):
        pipeline = self.active()
        receiver_state = pipeline.verifier.active_session_ids
        previous = pipeline.sender.stored_credential_status
        rows = pipeline.sender.audit_records
        timings = (pipeline.sender.kdf_timings_ns, pipeline.verifier.kdf_timings_ns)
        provider = Mock()
        with self.no_protected_work(pipeline, expect_no_authority=False), \
             patch.object(CredentialAdmissionService, "authorize_with_outcome") as authorize, \
             patch.object(pipeline.verifier, "begin_session") as begin_session:
            failure = pipeline.sender.begin_stored_attempt(provider, "stored-active")
            authorize.assert_not_called()
            begin_session.assert_not_called()
        self.assertEqual(failure.reason, "internal_error")
        self.assertEqual(pipeline.sender.stored_credential_status, StoredCredentialStatus(
            attempt_id="stored-active", preparation_failure="internal_error"))
        self.assertIs(pipeline.sender.prepared_stored_credential_status, previous)
        self.assertEqual(previous, StoredCredentialStatus(
            "success", "verified", "authorized", attempt_id="stored-active"))
        provider.get_credential.assert_not_called()
        self.assertEqual(pipeline.sender.state, "FAILED")
        self.assertIsNone(pipeline.sender._key)
        self.assertIsNone(pipeline.sender._candidate)
        self.assertIsNone(pipeline.sender.admission)
        self.assertTrue(pipeline.sender.incomplete)
        self.assertEqual(pipeline.verifier.active_session_ids, receiver_state)
        self.assertEqual((pipeline.sender.kdf_timings_ns, pipeline.verifier.kdf_timings_ns), timings)
        self.assertEqual(pipeline.sender.audit_records[:-1], rows)
        rejection = pipeline.sender.audit_records[-1]
        self.assertEqual((rejection["attempt_id"], rejection["decision"], rejection["reason"]),
                         ("stored-active", "reject", "internal_error"))
        self.assertIsNone(rejection["session_id"])
        self.assertFalse(pipeline.sender._admission_service._admissions)
        self.assertFalse(pipeline.verifier._pending)
        self.assertFalse(pipeline.verifier._accepted_results)
        self.assertEqual(pipeline.calls, ModelCallCounts())
        self.assertEqual(pipeline.consumed_event_ids, ())
        with self.assertRaises(RuntimeError):
            pipeline.sender.seal_window(window(receiver_state[0]))

    def test_busy_stored_invocation_preserves_pending_status_and_handshake(self):
        for sender_type in (session.Sender, Sender):
            for phase in ("request", "challenge"):
                for rejected_id in ("pending-stored", "busy-stored"):
                    with self.subTest(sender=sender_type.__module__, phase=phase, rejected_id=rejected_id):
                        pipeline, service, _ = self.peers()
                        sender = (pipeline.sender if sender_type is Sender else
                                  session.Sender(pipeline.sender.enrollment, admission_service=service))
                        local = {"local_provenance": Provenance(source_id="pending-source")} if sender_type is Sender else {}
                        request = sender.begin_stored_attempt(source(), "pending-stored", **local)
                        previous = sender.stored_credential_status
                        confirmation = None
                        if phase == "challenge":
                            challenge = pipeline.verifier.begin_session(request, admission=sender.admission)
                            confirmation = sender.answer_challenge(challenge)
                        fields = ("state", "reason", "attempt_id", "_admission", "_request", "_candidate",
                                  "_key", "_client", "_context", "_transcript", "_nonce", "_start", "_deadline")
                        pending = {name: getattr(sender, name) for name in fields}
                        admissions = {handle: asdict(state) for handle, state in service._admissions.items()}
                        used_ids = set(sender._used_attempt_ids)
                        if sender_type is Sender:
                            rows = sender.audit_records
                            lifecycle = (sender._local_provenance, sender._attempt_kdf_start,
                                         sender._establishment_start)
                        provider = Mock()
                        rejected_local = ({"local_provenance": Provenance(source_id="rejected-source")}
                                          if sender_type is Sender else {})
                        with self.no_protected_work(pipeline, expect_no_authority=False), \
                             patch.object(CredentialAdmissionService, "authorize_with_outcome") as authorize:
                            failure = sender.begin_stored_attempt(provider, rejected_id, **rejected_local)
                            authorize.assert_not_called()
                        self.assertEqual(failure, session.Failure("session_busy"))
                        provider.get_credential.assert_not_called()
                        rejected = sender.stored_credential_status
                        self.assertEqual(rejected, StoredCredentialStatus(
                            attempt_id=rejected_id, preparation_failure="session_busy"))
                        self.assertIs(sender.prepared_stored_credential_status, previous)
                        self.assertEqual(previous, StoredCredentialStatus(
                            "success", "verified", "authorized", attempt_id="pending-stored"))
                        self.assertEqual({name: getattr(sender, name) for name in fields}, pending)
                        self.assertEqual({handle: asdict(state) for handle, state in service._admissions.items()}, admissions)
                        self.assertEqual(sender._used_attempt_ids, used_ids)
                        if sender_type is Sender:
                            self.assertEqual(sender.audit_records[:-1], rows)
                            row = sender.audit_records[-1]
                            self.assertEqual((row["attempt_id"], row["reason"], row["state_after"]),
                                             (rejected_id, "session_busy", "PENDING"))
                            self.assertIsNone(row["session_id"])
                            self.assertEqual(row["provenance"]["source_id"], "rejected-source")
                            self.assertFalse(sender.incomplete)
                            self.assertEqual((sender._local_provenance, sender._attempt_kdf_start,
                                              sender._establishment_start), lifecycle)
                        if confirmation is None:
                            challenge = pipeline.verifier.begin_session(request, admission=sender.admission)
                            confirmation = sender.answer_challenge(challenge)
                        response = pipeline.verifier.confirm_session(confirmation)
                        self.assertIs(sender.finish_session(response), sender)
                        self.assertEqual(sender.state, "ACTIVE")
                        self.assertIs(sender.stored_credential_status, rejected)
                        self.assertIs(sender.prepared_stored_credential_status, previous)
                        self.assertFalse(service._admissions)
                        if sender_type is Sender:
                            self.assertEqual(sender.audit_records[-1]["attempt_id"], "pending-stored")
                            self.assertEqual(sender.audit_records[-1]["provenance"]["source_id"], "pending-source")
                            packet = sender.seal_window(window(sender.session_id))
                            self.assertEqual(pipeline.process_envelope(packet).decision, "accept")
                            self.assertEqual(pipeline.calls, ModelCallCounts(1, 1, 1))

    def test_early_rejection_does_not_reuse_previous_failure_diagnostics(self):
        for sender_type in (session.Sender, Sender):
            for provider in (source(bytes(4)), InMemoryStoredCredentialProvider()):
                with self.subTest(sender=sender_type.__module__, provider=type(provider).__name__):
                    pipeline, service, _ = self.peers()
                    sender = (pipeline.sender if sender_type is Sender else
                              session.Sender(pipeline.sender.enrollment, admission_service=service))
                    first = sender.begin_stored_attempt(provider, "failed-stored")
                    self.assertIsInstance(first, session.Failure)
                    previous = sender.stored_credential_status
                    self.assertIn(previous.retrieval_outcome, ("success", "unavailable"))
                    unused = Mock()
                    with self.no_protected_work(pipeline), \
                         patch.object(CredentialAdmissionService, "authorize_with_outcome") as authorize:
                        failure = sender.begin_stored_attempt(unused, "failed-stored")
                        authorize.assert_not_called()
                    self.assertEqual(failure, session.Failure("internal_error"))
                    unused.get_credential.assert_not_called()
                    self.assertEqual(sender.stored_credential_status, StoredCredentialStatus(
                        attempt_id="failed-stored", preparation_failure="internal_error"))
                    self.assertIs(sender.prepared_stored_credential_status, previous)
                    self.assertIsNone(sender.admission)
                    self.assertIsNone(sender._request)
                    self.assertIsNone(sender._candidate)
                    self.assertIsNone(sender._key)

    def test_base_sender_reused_id_after_success_has_separate_status(self):
        pipeline, service, _ = self.peers()
        sender = session.Sender(pipeline.sender.enrollment, admission_service=service)
        request = sender.begin_stored_attempt(source(), "base-success")
        challenge = pipeline.verifier.begin_session(request, admission=sender.admission)
        confirmation = sender.answer_challenge(challenge)
        self.assertIs(sender.finish_session(pipeline.verifier.confirm_session(confirmation)), sender)
        previous = sender.stored_credential_status
        context, key = sender._context, sender._key
        unused = Mock()
        with self.no_protected_work(pipeline, expect_no_authority=False), \
             patch.object(CredentialAdmissionService, "authorize_with_outcome") as authorize:
            failure = sender.begin_stored_attempt(unused, "base-success")
            authorize.assert_not_called()
        self.assertEqual(failure, session.Failure("internal_error"))
        unused.get_credential.assert_not_called()
        self.assertEqual(sender.stored_credential_status, StoredCredentialStatus(
            attempt_id="base-success", preparation_failure="internal_error"))
        self.assertIs(sender.prepared_stored_credential_status, previous)
        # Base sender's existing preparation-rejection lifecycle stays unchanged.
        self.assertEqual(sender.state, "ACTIVE")
        self.assertIs(sender._context, context)
        self.assertIs(sender._key, key)

    def test_provider_exception_is_infrastructure_fault_without_secret_diagnostic(self):
        pipeline, service, _ = self.peers()
        provider = Mock(get_credential=Mock(side_effect=RuntimeError("private-secret")))
        with self.no_source_work(), self.no_protected_work(pipeline), patch.object(CredentialAdmissionService, "verify") as verify:
            with self.assertRaises(PipelineExecutionError) as caught:
                pipeline.establish_stored(provider, "provider-fault")
            verify.assert_not_called()
        self.assertEqual(pipeline.sender.stored_credential_status.retrieval_outcome, "infrastructure_error")
        self.assertTrue(pipeline.sender.incomplete)
        self.assertNotIn("private-secret", str(caught.exception) + json.dumps(pipeline.sender.audit_records))

    def test_key_provider_failure_is_not_wrong_credential(self):
        pipeline, _, key = self.peers()
        with patch.object(type(key), "get_key", side_effect=RuntimeError("private-key")), \
             self.no_protected_work(pipeline), self.assertRaises(PipelineExecutionError):
            pipeline.establish_stored(source(), "key-fault")
        self.assertEqual(pipeline.sender.stored_credential_status.verification_outcome, "key_unavailable")
        self.assertTrue(pipeline.sender.incomplete)

    def test_issuance_fault_after_verified_candidate_is_not_mismatch(self):
        pipeline, service, _ = self.peers()
        with patch("puf_snn.auth.credential_verifier._Admission", side_effect=RuntimeError("private-error")), \
             patch.object(CredentialAdmissionService, "verify", side_effect=service.verify) as verify, \
             self.no_protected_work(pipeline), self.assertRaises(PipelineExecutionError):
            pipeline.establish_stored(source(), "issuance-fault")
        verify.assert_called_once()
        self.assertEqual(pipeline.sender.stored_credential_status.admission_outcome, "infrastructure_error")
        self.assertEqual(pipeline.sender.stored_credential_status.verification_outcome, "verified")
        self.assertTrue(pipeline.sender.incomplete)

    def test_admission_service_exception_is_incomplete(self):
        pipeline, service, _ = self.peers()
        with patch.object(CredentialAdmissionService, "authorize_with_outcome", side_effect=RuntimeError("private-error")), \
             self.no_protected_work(pipeline), self.assertRaises(PipelineExecutionError):
            pipeline.establish_stored(source(), "service-fault")
        self.assertTrue(pipeline.sender.incomplete)

    def test_missing_receiver_authorization_blocks_receiver_hkdf(self):
        pipeline, _, _ = self.peers()
        begin = pipeline.verifier.begin_session
        with patch.object(pipeline.verifier, "begin_session",
                          side_effect=lambda request, local, admission: begin(request, local, admission=None)):
            result = pipeline.establish_stored(source(), "missing-capability")
        self.assertEqual((result.stage, result.reason), ("receiver_admission", "credential_verification_failed"))
        self.assert_no_authority(pipeline)

    def test_forged_authorization_cannot_create_receiver_session(self):
        pipeline, _, _ = self.peers()
        request = pipeline.sender.begin_stored_attempt(source(), "forged-capability")
        forged = object.__new__(LocalAdmissionAuthorization)
        with patch("puf_snn.auth.verifier.derive_session_key") as derive:
            self.assertEqual(pipeline.verifier.begin_session(request, admission=forged), session.REFUSAL)
            derive.assert_not_called()
        self.assertFalse(pipeline.verifier._pending)
        self.assertFalse(pipeline.verifier.active_session_ids)

    def test_duplicate_gap_payload_metadata_and_cross_device_rejections_do_not_release(self):
        pipeline = self.active(other_device=True)
        sid = pipeline.sender.session_id
        packets = [pipeline.sender.seal_window(window(sid)) for _ in range(3)]
        parsed = parse_envelope(packets[0])
        sample = replace(parsed.window.samples[0], position_m=(F32(0x3f000000), F32(0), F32(0)))
        payload = replace(parsed.window, samples=(sample,)+parsed.window.samples[1:])
        metadata = replace(parsed.window, window_id="changed-metadata")

        def reject(packet, reason):
            before, calls = pipeline.verifier.session_status(sid), pipeline.calls
            self.assertEqual(pipeline.process_envelope(packet).reason, reason)
            self.assertEqual(pipeline.verifier.session_status(sid), before)
            self.assertEqual(pipeline.calls, calls)

        for changed in (payload, metadata):
            reject(wrap(encode_window(changed), sid, None, tag=parsed.tag), "invalid_tag")
        # Valid tags still do not override owner/session bindings.
        changed = replace(parsed.window, device_id="other-device")
        reject(wrap(encode_window(changed), sid, pipeline.sender._key), "device_session_mismatch")
        reject(packets[1], "future_sequence_gap")
        self.assertEqual(pipeline.process_envelope(packets[0]).decision, "accept")
        reject(packets[0], "duplicate_sequence")
        self.assertEqual(pipeline.process_envelope(packets[1]).decision, "accept")
        reject(packets[0], "stale_sequence")
        self.assertEqual(pipeline.process_envelope(packets[2]).decision, "accept")
        self.assertEqual(pipeline.calls, ModelCallCounts(3, 3, 3))

    def test_cross_session_packet_and_key_identifier_rejected(self):
        first, second = self.active(), self.active()
        packet = first.sender.seal_window(window(first.sender.session_id))
        self.assertEqual(second.process_envelope(packet).reason, "unknown_session")
        self.assertEqual(second.calls, ModelCallCounts())
        parsed = parse_envelope(packet)
        wrong_id = wrap(encode_window(parsed.window), first.sender.session_id, None,
                        tag=parsed.tag, key_id=second.sender.session_id.hex())
        self.assertEqual(first.process_envelope(wrong_id).reason, "invalid_key_id")
        self.assertEqual(first.calls, ModelCallCounts())

    def test_verifier_owned_exactly_once_release(self):
        pipeline = self.active()
        rejected = pipeline.verifier.verify_window(b"invalid")
        for result in (rejected, VerificationResult("accept", "accepted", event_id="fabricated")):
            with self.assertRaises(ValueError):
                pipeline.release(result)
        packet = pipeline.sender.seal_window(window(pipeline.sender.session_id))
        accepted = pipeline.verifier.verify_window(packet)
        with self.assertRaises(ValueError):
            pipeline.release(replace(accepted))
        self.assertEqual(pipeline.calls, ModelCallCounts())
        pipeline.release(accepted)
        with self.assertRaises(ValueError):
            pipeline.release(accepted)
        self.assertEqual(pipeline.calls, ModelCallCounts(1, 1, 1))

    def test_consumer_exception_remains_consumed_and_incomplete(self):
        pipeline = self.active()
        pipeline._motion.side_effect = RuntimeError("model-fault")
        packet = pipeline.sender.seal_window(window(pipeline.sender.session_id))
        accepted = pipeline.verifier.verify_window(packet)
        with self.assertRaises(RuntimeError):
            pipeline.release(accepted)
        with self.assertRaises(ValueError):
            pipeline.release(accepted)
        self.assertEqual(pipeline.calls, ModelCallCounts(1, 1, 0))
        self.assertTrue(pipeline.verifier.incomplete)

    def test_pipeline_cannot_retry_or_switch_source_after_attempt(self):
        for stored_first in (True, False):
            pipeline, _, _ = self.peers()
            if stored_first:
                pipeline.establish_stored(InMemoryStoredCredentialProvider(), "first")
            else:
                pipeline.establish(lambda: REFERENCE, "first")
            provider, reader = Mock(), Mock()
            with self.assertRaises(ValueError):
                pipeline.establish_stored(provider, "second")
            with self.assertRaises(ValueError):
                pipeline.establish(reader, "third")
            provider.get_credential.assert_not_called()
            reader.assert_not_called()

    def test_base_sender_entry_and_unchanged_puf_result_validation(self):
        pipeline, service, _ = self.peers()
        base = session.Sender(pipeline.sender.enrollment, admission_service=service)
        self.assertIsInstance(base.begin_stored_attempt(source(), "base-stored"), bytes)
        with patch.object(CredentialAdmissionService, "verify") as verify:
            self.assertEqual(base.begin_attempt(stored_record(), "not-layer2"), session.Failure("session_busy"))
            verify.assert_not_called()
        other, service, _ = self.peers()
        with patch.object(CredentialAdmissionService, "verify") as verify:
            result = other.sender.begin_attempt(stored_record(), "reject-record-as-layer2")
            self.assertEqual(result.reason, "internal_error")
            verify.assert_not_called()

    def test_single_and_majority_paths_still_decode_once_and_verify(self):
        for policy in (SINGLE_READ, MAJORITY_3):
            pipeline, service, _ = self.peers(policy=policy)
            read = Mock(return_value=REFERENCE)
            with patch("puf_snn.pipeline_v2.reconstruct", wraps=reconstruct) as decode, \
                 patch.object(CredentialAdmissionService, "verify", side_effect=service.verify) as verify:
                result = pipeline.establish(read, "puf-regression")
            self.assertTrue(result.session_active)
            self.assertEqual(result.reconstruction_outcome, "candidate_valid_format")
            self.assertEqual(read.call_count, policy.read_count)
            decode.assert_called_once()
            verify.assert_called_once()


if __name__ == "__main__":
    unittest.main()
