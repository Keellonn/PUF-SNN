"""Standalone credential-verifier tests. All keys/credentials here are synthetic.

The fixed vector was calculated independently with struct.pack('>H', ...) and
the SHA-256 HMAC inner/outer pad construction, then cross-checked with stdlib
HMAC. It is public, nonsecret test material, never a runtime provisioning key.
"""

from dataclasses import FrozenInstanceError, asdict, fields, replace
import hashlib
import hmac
import inspect
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import Mock, patch

from puf_snn.auth import (
    CredentialAdmissionResult, CredentialAdmissionService,
    CredentialVerifierRecord, CredentialVerifierStore,
    InMemoryCredentialVerifierKeyProvider,
)


MODULE = "puf_snn.auth.credential_verifier"
# SYNTHETIC / NONSECRET: explicit deterministic fixtures, not operational keys.
TEST_KEY = bytes(range(32))
TEST_CREDENTIAL = bytes.fromhex("000001a5")
DEVICE = "Device-A"
ENROLLMENT = "enrollment-01"
PROFILE = "puf-snn-reconstruction-v1"
KEY_ID = "synthetic-key-1"
BINDING = dict(device_id=DEVICE, enrollment_id=ENROLLMENT, reconstruction_id=PROFILE)
VECTOR_MESSAGE_HEX = (
    "001e5055462d534e4e2f63726564656e7469616c2d76657269666965722f7631"
    "00084465766963652d41000d656e726f6c6c6d656e742d3031"
    "00197075662d736e6e2d7265636f6e737472756374696f6e2d7631"
    "000f73796e7468657469632d6b65792d31000001a5"
)
VECTOR_TAG_HEX = "a98b73a20b15520ee5c5c7f4c57482268dcd5639d819158a8e3923cf45b038ba"


class CredentialVerifierTests(unittest.TestCase):
    def setUp(self):
        self.provider = InMemoryCredentialVerifierKeyProvider(KEY_ID, TEST_KEY)
        self.record = self.enroll()
        self.store = CredentialVerifierStore([self.record])
        self.service = CredentialAdmissionService(self.store, self.provider)

    def enroll(self, credential=TEST_CREDENTIAL, provider=None, **changes):
        inputs = dict(BINDING, verifier_key_id=KEY_ID, credential4=credential,
                      key_provider=self.provider if provider is None else provider)
        inputs.update(changes)
        return CredentialVerifierRecord.enroll(**inputs)

    def verify(self, credential=TEST_CREDENTIAL, record=None, provider=None, **changes):
        service = self.service
        if record is not None or provider is not None:
            service = CredentialAdmissionService(
                CredentialVerifierStore([self.record if record is None else record]),
                self.provider if provider is None else provider,
            )
        return service.verify(credential, **(BINDING | changes))

    def assertOutcome(self, result, outcome):
        self.assertIs(type(result), CredentialAdmissionResult)
        self.assertEqual(result.outcome, outcome)
        self.assertEqual(result.verified, outcome == "verified")
        self.assertEqual(bool(result), outcome == "verified")

    def test_fixed_independent_vector_and_full_tag(self):
        with patch(MODULE + ".hmac.new", wraps=hmac.new) as mac:
            record = self.enroll()
        self.assertEqual(mac.call_count, 1)
        self.assertEqual(mac.call_args.args[0], TEST_KEY)
        self.assertEqual(mac.call_args.args[1].hex(), VECTOR_MESSAGE_HEX)
        self.assertIs(mac.call_args.args[2], hashlib.sha256)
        self.assertEqual(record.tag.hex(), VECTOR_TAG_HEX)
        self.assertEqual(len(record.tag), 32)

    def test_correct_credential(self):
        self.assertOutcome(self.verify(), "verified")

    def test_one_bit_wrong_credential(self):
        wrong = TEST_CREDENTIAL[:-1] + bytes([TEST_CREDENTIAL[-1] ^ 1])
        self.assertOutcome(self.verify(wrong), "credential_mismatch")

    def test_completely_different_credential(self):
        self.assertOutcome(self.verify(b"\xff" * 4), "credential_mismatch")

    def test_leading_zero_and_all_zero_credentials(self):
        for credential in (TEST_CREDENTIAL, bytes(4), b"\x00\x00\x00\x01"):
            with self.subTest(credential=credential.hex()):
                record = self.enroll(credential)
                self.assertOutcome(self.verify(credential, record=record), "verified")
                self.assertOutcome(self.verify(credential.lstrip(b"\x00"), record=record), "invalid_input")

    def test_device_binding_uses_distinct_device_record(self):
        other = self.enroll(b"\x19\x27\x38\x49", device_id="Device-B")
        service = CredentialAdmissionService(CredentialVerifierStore([self.record, other]), self.provider)
        self.assertOutcome(service.verify(TEST_CREDENTIAL, **BINDING), "verified")
        self.assertOutcome(service.verify(TEST_CREDENTIAL, **(BINDING | {"device_id": "Device-B"})),
                           "credential_mismatch")
        self.assertOutcome(self.verify(device_id="Device-B"), "record_missing")

    def test_identical_credentials_across_devices_are_not_origin_proof(self):
        other = self.enroll(device_id="Device-B")
        self.assertNotEqual(other.tag, self.record.tag)
        service = CredentialAdmissionService(CredentialVerifierStore([self.record, other]), self.provider)
        for device in (DEVICE, "Device-B"):
            self.assertOutcome(service.verify(TEST_CREDENTIAL, **(BINDING | {"device_id": device})), "verified")

    def test_enrollment_id_binding_and_lookup(self):
        self.assertOutcome(self.verify(enrollment_id="enrollment-02"), "record_missing")
        relabeled = replace(self.record, enrollment_id="enrollment-02")
        self.assertOutcome(self.verify(record=relabeled, enrollment_id="enrollment-02"), "credential_mismatch")
        fresh = self.enroll(enrollment_id="enrollment-02")
        self.assertNotEqual(fresh.tag, self.record.tag)
        self.assertOutcome(self.verify(record=fresh, enrollment_id="enrollment-02"), "verified")

    def test_reconstruction_profile_binding(self):
        self.assertOutcome(self.verify(reconstruction_id="different-profile"), "binding_mismatch")
        relabeled = replace(self.record, reconstruction_id="different-profile")
        self.assertOutcome(self.verify(record=relabeled, reconstruction_id="different-profile"),
                           "credential_mismatch")

    def test_key_id_is_in_mac_even_when_key_bytes_match(self):
        other_provider = InMemoryCredentialVerifierKeyProvider("synthetic-key-2", TEST_KEY)
        relabeled = replace(self.record, verifier_key_id="synthetic-key-2")
        self.assertOutcome(self.verify(record=relabeled, provider=other_provider), "credential_mismatch")
        fresh = self.enroll(provider=other_provider, verifier_key_id="synthetic-key-2")
        self.assertNotEqual(fresh.tag, self.record.tag)
        self.assertOutcome(self.verify(record=fresh, provider=other_provider), "verified")

    def test_relabeled_device_record_fails(self):
        relabeled = replace(self.record, device_id="Device-B")
        self.assertOutcome(self.verify(record=relabeled, device_id="Device-B"), "credential_mismatch")

    def test_store_returning_wrong_binding_fails(self):
        for change in ({"device_id": "Device-B"}, {"enrollment_id": "enrollment-02"}):
            with self.subTest(change=change), patch.object(
                CredentialVerifierStore, "get", return_value=replace(self.record, **change)
            ):
                self.assertOutcome(self.verify(), "binding_mismatch")

    def test_corrupted_tag(self):
        tag = bytes([self.record.tag[0] ^ 1]) + self.record.tag[1:]
        self.assertOutcome(self.verify(record=replace(self.record, tag=tag)), "credential_mismatch")

    def test_truncated_extended_and_nonbytes_tags(self):
        for tag in (b"", self.record.tag[:-1], self.record.tag + b"x", self.record.tag.hex(),
                    bytearray(self.record.tag), memoryview(self.record.tag), None):
            with self.subTest(tag_type=type(tag).__name__), patch(MODULE + ".hmac.new") as mac:
                self.assertOutcome(self.verify(record=replace(self.record, tag=tag)), "unsupported_record")
                mac.assert_not_called()

    def test_missing_record_no_provider_access_or_auto_enrollment(self):
        provider = Mock()
        service = CredentialAdmissionService(CredentialVerifierStore(), provider)
        with patch.object(CredentialVerifierRecord, "enroll", side_effect=AssertionError("auto enrollment")):
            self.assertOutcome(service.verify(TEST_CREDENTIAL, **BINDING), "record_missing")
        provider.get_key.assert_not_called()

    def test_disabled_and_revoked_records(self):
        provider = Mock()
        for change in ({"enabled": False}, {"revoked": True}, {"enabled": False, "revoked": True}):
            with self.subTest(change=change):
                self.assertOutcome(self.verify(record=replace(self.record, **change), provider=provider),
                                   "record_disabled")
        provider.get_key.assert_not_called()

    def test_lifecycle_flags_must_be_exact_bools(self):
        for field_name in ("enabled", "revoked"):
            for value in (0, 1, "true", None):
                with self.subTest(field=field_name, value=value):
                    self.assertOutcome(self.verify(record=replace(self.record, **{field_name: value})),
                                       "unsupported_record")

    def test_unknown_key_id(self):
        record = replace(self.record, verifier_key_id="unavailable-key")
        self.assertOutcome(self.verify(record=record), "key_unavailable")

    def test_wrong_verifier_key(self):
        provider = InMemoryCredentialVerifierKeyProvider(KEY_ID, b"\xa6" * 32)
        self.assertOutcome(self.verify(provider=provider), "credential_mismatch")

    def test_provider_exception_is_redacted(self):
        provider = Mock()
        provider.get_key.side_effect = RuntimeError(TEST_KEY.hex() + TEST_CREDENTIAL.hex())
        result = self.verify(provider=provider)
        self.assertOutcome(result, "key_unavailable")
        provider.get_key.assert_called_once_with(KEY_ID)
        self.assertNotIn(TEST_KEY.hex(), repr(result))
        with self.assertRaisesRegex(ValueError, "^key_unavailable$") as caught:
            self.enroll(provider=provider)
        self.assertNotIn(TEST_KEY.hex(), str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)

    def test_unavailable_or_malformed_provider_key(self):
        for key in (None, b"", bytes(31), bytes(33), TEST_KEY.hex(), bytearray(TEST_KEY), memoryview(TEST_KEY)):
            with self.subTest(key_type=type(key).__name__):
                provider = Mock(get_key=Mock(return_value=key))
                self.assertOutcome(self.verify(provider=provider), "key_unavailable")
                with self.assertRaisesRegex(ValueError, "^key_unavailable$"):
                    self.enroll(provider=provider)

    def test_invalid_identifier_syntax_and_types(self):
        for value in ("", " A", "A ", "a b", "a/b", "a\nb", "a\n", "-first", "a\x00b", b"A", None, 3, True):
            for name in BINDING:
                with self.subTest(name=name, value=value):
                    self.assertOutcome(self.verify(**{name: value}), "invalid_input")
                    with self.assertRaisesRegex(ValueError, "^invalid_input$"):
                        self.enroll(**{name: value})
            with self.assertRaisesRegex(ValueError, "^invalid_input$"):
                self.enroll(verifier_key_id=value)

    def test_non_ascii_identifiers_are_rejected_without_normalization(self):
        for value in ("D\u00e9vice", "\uff21", "A\u0301", "dev\u2011one"):
            for name in (*BINDING, "verifier_key_id"):
                with self.subTest(name=name, value=value):
                    with self.assertRaisesRegex(ValueError, "^invalid_input$"):
                        self.enroll(**{name: value})
                    if name in BINDING:
                        self.assertOutcome(self.verify(**{name: value}), "invalid_input")

    def test_identifier_length_boundary_and_unsigned_big_endian_framing(self):
        longest = "A" * 128
        with patch(MODULE + ".hmac.new", wraps=hmac.new) as mac:
            record = self.enroll(device_id=longest)
        # Domain occupies 2+30 bytes; 128 must be unsigned 0x0080, not 0x8000.
        self.assertEqual(mac.call_args.args[1][32:34], b"\x00\x80")
        self.assertOutcome(self.verify(record=record, device_id=longest), "verified")
        for name in (*BINDING, "verifier_key_id"):
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "^invalid_input$"):
                    self.enroll(**{name: "A" * 129})
                if name in BINDING:
                    self.assertOutcome(self.verify(**{name: "A" * 129}), "invalid_input")

    def test_valid_identifier_punctuation_and_case_sensitivity(self):
        record = self.enroll(device_id="A.z_9:-")
        self.assertOutcome(self.verify(record=record, device_id="A.z_9:-"), "verified")
        self.assertOutcome(self.verify(device_id=DEVICE.lower()), "record_missing")
        changed = replace(self.record, device_id=DEVICE.lower())
        self.assertOutcome(self.verify(record=changed, device_id=DEVICE.lower()), "credential_mismatch")

    def test_wrong_credential_lengths(self):
        for credential in (b"", bytes(1), bytes(3), bytes(5), bytes(128)):
            with self.subTest(length=len(credential)), patch(MODULE + ".hmac.new") as mac:
                self.assertOutcome(self.verify(credential), "invalid_input")
                with self.assertRaisesRegex(ValueError, "^invalid_input$"):
                    self.enroll(credential)
                mac.assert_not_called()

    def test_nonbytes_credentials_and_bytes_subclass(self):
        class DerivedBytes(bytes):
            pass
        for credential in (TEST_CREDENTIAL.hex(), bytearray(TEST_CREDENTIAL), memoryview(TEST_CREDENTIAL),
                           list(TEST_CREDENTIAL), None, 0, DerivedBytes(TEST_CREDENTIAL)):
            with self.subTest(kind=type(credential).__name__):
                self.assertOutcome(self.verify(credential), "invalid_input")
                with self.assertRaisesRegex(ValueError, "^invalid_input$"):
                    self.enroll(credential)

    def test_unsupported_algorithm_and_schema(self):
        for change in ({"algorithm": "SHA-256"}, {"algorithm": "HMAC-SHA-512"},
                       {"schema": "puf-snn-credential-verifier-v2"}, {"schema": 1}, {"algorithm": None}):
            with self.subTest(change=change):
                self.assertOutcome(self.verify(record=replace(self.record, **change)), "unsupported_record")

    def test_malformed_record_identifiers(self):
        for field_name in ("reconstruction_id", "verifier_key_id"):
            with self.subTest(field=field_name):
                self.assertOutcome(self.verify(record=replace(self.record, **{field_name: "bad id"})),
                                   "unsupported_record")

    def test_length_prefix_prevents_concatenation_ambiguity(self):
        self.assertEqual(b"ab" + b"c", b"a" + b"bc")
        with patch(MODULE + ".hmac.new", wraps=hmac.new) as mac:
            first = self.enroll(device_id="ab", enrollment_id="c")
            second = self.enroll(device_id="a", enrollment_id="bc")
        self.assertNotEqual(mac.call_args_list[0].args[1], mac.call_args_list[1].args[1])
        self.assertNotEqual(first.tag, second.tag)
        substitute = replace(first, device_id="a", enrollment_id="bc")
        self.assertOutcome(self.verify(record=substitute, device_id="a", enrollment_id="bc"),
                           "credential_mismatch")

    def test_compare_digest_checks_full_tags_on_pass_and_failure(self):
        with patch(MODULE + ".hmac.compare_digest", wraps=hmac.compare_digest) as compare:
            self.assertOutcome(self.verify(), "verified")
            self.assertOutcome(self.verify(bytes(4)), "credential_mismatch")
        self.assertEqual(compare.call_count, 2)
        for call in compare.call_args_list:
            self.assertEqual(tuple(map(len, call.args)), (32, 32))
            self.assertTrue(all(type(arg) is bytes for arg in call.args))
            self.assertEqual(call.args[1], self.record.tag)

    def test_no_retry_or_key_search_on_mismatch(self):
        provider = Mock(get_key=Mock(return_value=TEST_KEY))
        with patch(MODULE + ".hmac.new", wraps=hmac.new) as mac:
            self.assertOutcome(self.verify(bytes(4), provider=provider), "credential_mismatch")
        provider.get_key.assert_called_once_with(KEY_ID)
        self.assertEqual(mac.call_count, 1)

    def test_duplicate_bindings_rejected_even_if_disabled_or_other_profile(self):
        for duplicate in (self.record, replace(self.record, enabled=False),
                          replace(self.record, reconstruction_id="other-profile")):
            with self.subTest(duplicate=duplicate):
                with self.assertRaisesRegex(ValueError, "^duplicate_record$"):
                    CredentialVerifierStore([self.record, duplicate])

    def test_store_snapshot_and_distinct_enrollment_lookup(self):
        second = self.enroll(bytes(4), enrollment_id="enrollment-02")
        records = [self.record, second]
        store = CredentialVerifierStore(records)
        records.clear()
        service = CredentialAdmissionService(store, self.provider)
        self.assertOutcome(service.verify(TEST_CREDENTIAL, **BINDING), "verified")
        self.assertOutcome(service.verify(bytes(4), **(BINDING | {"enrollment_id": "enrollment-02"})), "verified")
        with self.assertRaises(FrozenInstanceError):
            self.record.enabled = False
        with self.assertRaises(TypeError):
            store._records[(DEVICE, ENROLLMENT)] = second

    def test_invalid_store_inputs_and_service_store(self):
        with self.assertRaisesRegex(ValueError, "^unsupported_record$"):
            CredentialVerifierStore([{}])
        for field_name in ("device_id", "enrollment_id"):
            with self.assertRaisesRegex(ValueError, "^invalid_input$"):
                CredentialVerifierStore([replace(self.record, **{field_name: "bad id"})])
        with self.assertRaisesRegex(ValueError, "^invalid_input$"):
            CredentialAdmissionService({}, self.provider)

    def test_internal_store_and_crypto_errors_are_redacted(self):
        for target in (MODULE + ".CredentialVerifierStore.get", MODULE + ".hmac.new",
                       MODULE + ".hmac.compare_digest"):
            with self.subTest(target=target), patch(target, side_effect=RuntimeError(TEST_KEY.hex())):
                result = self.verify()
                self.assertOutcome(result, "internal_error")
                self.assertNotIn(TEST_KEY.hex(), repr(result))
        with patch(MODULE + ".hmac.new", side_effect=RuntimeError(TEST_CREDENTIAL.hex())):
            with self.assertRaisesRegex(ValueError, "^internal_error$") as caught:
                self.enroll()
            self.assertTrue(caught.exception.__suppress_context__)

    def test_unexpected_store_record_fails_closed(self):
        with patch.object(CredentialVerifierStore, "get", return_value={"tag": self.record.tag}):
            self.assertOutcome(self.verify(), "unsupported_record")

    def test_record_fields_have_no_plaintext_or_public_credential_hash(self):
        self.assertEqual({f.name for f in fields(self.record)}, {
            "device_id", "enrollment_id", "reconstruction_id", "verifier_key_id",
            "tag", "schema", "algorithm", "enabled", "revoked",
        })
        values = asdict(self.record)  # Trusted provisioning inspection only.
        self.assertEqual([v for v in values.values() if type(v) is bytes], [self.record.tag])
        for name, expected in BINDING.items():
            self.assertEqual(values[name], expected)
        self.assertEqual(values["verifier_key_id"], KEY_ID)
        for digest in (hashlib.sha256(TEST_CREDENTIAL).digest(), hashlib.sha256(TEST_CREDENTIAL).hexdigest()):
            self.assertNotIn(digest, values.values())
        self.assertEqual(asdict(self.verify()), {"outcome": "verified"})

    def test_normal_representations_hide_credentials_keys_and_tags(self):
        objects = (self.provider, self.record, self.store, self.service, self.verify(), self.verify(bytes(4)))
        for obj in objects:
            for text in (str(obj), repr(obj), repr([obj]), f"value={obj!r}"):
                for secret in (TEST_CREDENTIAL, TEST_KEY, self.record.tag):
                    self.assertNotIn(repr(secret), text)
                    self.assertNotIn(secret.hex(), text)
        malformed = replace(self.record, algorithm=TEST_KEY, device_id=TEST_CREDENTIAL, tag=TEST_KEY)
        self.assertEqual(repr(malformed), "CredentialVerifierRecord(<redacted>)")

    def test_verification_and_enrollment_write_no_console_output(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.enroll()
            self.verify()
            self.verify(bytes(4))
            self.verify(provider=Mock(get_key=Mock(side_effect=ValueError(TEST_KEY.hex()))))
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "")

    def test_result_cannot_hold_arbitrary_exception_text(self):
        with self.assertRaisesRegex(ValueError, "^invalid_input$"):
            CredentialAdmissionResult(TEST_KEY.hex())
        result = self.verify()
        with self.assertRaises(FrozenInstanceError):
            result.outcome = "internal_error"

    def test_provider_exact_key_length_and_type(self):
        for key in (b"", bytes(31), bytes(33), bytearray(TEST_KEY), TEST_KEY.hex(), None):
            with self.subTest(kind=type(key).__name__):
                with self.assertRaisesRegex(ValueError, "^invalid_input$"):
                    InMemoryCredentialVerifierKeyProvider(KEY_ID, key)
        self.assertEqual(self.provider.get_key(KEY_ID), TEST_KEY)
        with self.assertRaisesRegex(LookupError, "^key_unavailable$"):
            self.provider.get_key("unknown-key")

    def test_generate_uses_os_random_exactly_once_without_credential_input(self):
        # Mocked OS output is an explicitly synthetic fixture, not runtime seeding.
        with patch(MODULE + ".secrets.token_bytes", return_value=TEST_KEY) as random:
            provider = InMemoryCredentialVerifierKeyProvider.generate(KEY_ID)
        random.assert_called_once_with(32)
        self.assertEqual(provider.get_key(KEY_ID), TEST_KEY)
        record = self.enroll(provider=provider)
        self.assertOutcome(self.verify(record=record, provider=provider), "verified")

    def test_generate_rejects_invalid_id_before_random_access(self):
        with patch(MODULE + ".secrets.token_bytes") as random:
            for key_id in ("bad id", "\u00e9", "K" * 129, None):
                with self.assertRaisesRegex(ValueError, "^invalid_input$"):
                    InMemoryCredentialVerifierKeyProvider.generate(key_id)
            random.assert_not_called()

    def test_generate_failure_has_no_fallback_or_secret_exception(self):
        with patch(MODULE + ".secrets.token_bytes", side_effect=OSError(TEST_KEY.hex())) as random:
            with self.assertRaisesRegex(ValueError, "^key_unavailable$") as caught:
                InMemoryCredentialVerifierKeyProvider.generate(KEY_ID)
            random.assert_called_once_with(32)
            self.assertTrue(caught.exception.__suppress_context__)
        with patch(MODULE + ".secrets.token_bytes", return_value=bytes(31)):
            with self.assertRaisesRegex(ValueError, "^key_unavailable$"):
                InMemoryCredentialVerifierKeyProvider.generate(KEY_ID)

    def test_verify_api_has_no_evaluator_truth_or_key_parameter(self):
        self.assertEqual(list(inspect.signature(CredentialAdmissionService.verify).parameters),
                         ["self", "candidate_credential4", "device_id", "enrollment_id", "reconstruction_id"])

    def test_standalone_primitive_never_calls_session_derivation(self):
        with patch("puf_snn.auth.session.derive_session_key", side_effect=AssertionError("HKDF")) as derive:
            record = self.enroll()
            self.assertOutcome(self.verify(record=record), "verified")
            self.assertOutcome(self.verify(bytes(4), record=record), "credential_mismatch")
            derive.assert_not_called()

    def test_exports_do_not_replace_existing_window_verification_result(self):
        import puf_snn.auth as auth
        from puf_snn.auth.verifier import VerificationResult
        self.assertIs(auth.VerificationResult, VerificationResult)
        self.assertIs(auth.CredentialAdmissionResult, CredentialAdmissionResult)
        self.assertFalse(any(name.startswith("_") for name in auth.__all__))


if __name__ == "__main__":
    unittest.main()
