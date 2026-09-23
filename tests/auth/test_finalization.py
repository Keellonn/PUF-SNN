"""Sender operational audit and trusted shutdown; no attack experiment."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from puf_snn.auth.audit import AuditJSONL, Provenance
from puf_snn.auth.binary_window import parse_envelope
from puf_snn.auth.config import AuthConfig
from puf_snn.auth.sender import Sender
from puf_snn.auth.session import Failure, REFUSAL, hkdf_extract
from puf_snn.reconstruction import ReconstructionResult

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/python/scripts"))
from run_layer3_demo import initialize_material, establish, synthetic_window, run_demo
try:
    from .support import setup, activate
    from .test_lifecycle_audit import pending
except ImportError:
    from support import setup, activate
    from test_lifecycle_audit import pending


class FinalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.material = initialize_material()
        cls.schema = json.loads((ROOT / "schemas/auth-audit-v1.schema.json").read_text())

    def sender(self):
        return Sender(self.material[0])

    def active(self, **config):
        return establish(AuthConfig(**config), self.material)[:2]

    def validate(self, sender):
        import jsonschema
        for row in sender.audit_records:
            jsonschema.validate(row, self.schema)
            self.assertEqual(row["origin"], "sender")

    def failure(self, result):
        s = self.sender()
        with patch("puf_snn.reconstruction.reconstruct", side_effect=AssertionError("retry")) as retry:
            with patch("puf_snn.auth.session.secrets.token_bytes", side_effect=AssertionError("handshake")) as rng:
                self.assertEqual(s.begin_attempt(result, "attempt"), Failure("failed_reconstruction", result.outcome))
        retry.assert_not_called()
        rng.assert_not_called()
        self.assertEqual(len(s.audit_records), 1)
        row = s.audit_records[0]
        self.assertEqual((row["event_type"], row["decision"], row["reason"], row["detail"]),
                         ("reconstruction", "reject", "failed_reconstruction", result.outcome))
        self.assertFalse(row["identity_authenticated"])
        self.assertIsNone(s._candidate)
        self.validate(s)

    def test_decoder_failure(self):
        self.failure(ReconstructionResult("decoder_failure", "uncorrectable", -1, None, None, None, "decoder_declared_failure"))

    def test_invalid_padding(self):
        self.failure(ReconstructionResult("invalid_format_or_padding", "decoded", 5, (0,)*35+(1,), None, False, "nonzero_padding"))

    def test_candidate_admission_is_not_authentication(self):
        s = self.sender()
        self.assertIsInstance(s.begin_attempt(self.material[2], "one"), bytes)
        row, = s.audit_records
        self.assertEqual((row["event_type"], row["decision"], row["reason"], row["state_after"]),
                         ("reconstruction", "accept", "accepted", "PENDING"))
        self.assertEqual(row["authentication_result"], "not_checked")
        self.assertFalse(row["identity_authenticated"])
        self.assertIsNone(row["detail"])
        self.validate(s)

    def test_malformed_result_marks_incomplete(self):
        s = self.sender()
        self.assertEqual(s.begin_attempt(None, "one"), Failure("internal_error"))
        self.assertTrue(s.incomplete)
        self.assertEqual(s.audit_records[0]["detail"], "invariant_failure")
        with self.assertRaises(RuntimeError): s.begin_attempt(self.material[2], "two")

    def test_reconstruction_timing_and_provenance(self):
        s = self.sender()
        local = Provenance(run_id="test", source_record_id="scheduled-1")
        s.begin_attempt(self.material[2], "one", reconstruction_ns=123, local_provenance=local)
        self.assertEqual(s.audit_records[0]["latency_ns"]["reconstruction"], 123)
        self.assertEqual(s.audit_records[0]["provenance"]["run_id"], "test")
        for bad in (True, -1, 1.0):
            with self.assertRaises(ValueError): self.sender().begin_attempt(self.material[2], "one", reconstruction_ns=bad)

    def test_backend_exception_is_incomplete_not_frr(self):
        s = self.sender()
        self.assertEqual(s.record_reconstruction_exception("one", reconstruction_ns=17), Failure("internal_error"))
        self.assertEqual(s.audit_records[0]["detail"], "backend_exception")
        self.assertEqual(s.audit_records[0]["latency_ns"]["reconstruction"], 17)
        self.assertTrue(s.incomplete)
        self.validate(s)

    def test_sender_prepare_excludes_audit_work(self):
        s, _ = self.active()
        ticks = [100]
        original = s._append
        def slow_audit(rows):
            ticks[0] += 10000
            original(rows)
        with patch("puf_snn.auth.sender.time.perf_counter_ns", side_effect=lambda: ticks[0]):
            with patch.object(s, "_append", side_effect=slow_audit):
                s.seal_window(synthetic_window())
        self.assertEqual(s.audit_records[-1]["latency_ns"]["sender_prepare"], 0)

    def test_sealing_backend_exception_stops_without_secret_dump(self):
        s, _ = self.active()
        with patch("puf_snn.auth.sender.window_tag", side_effect=RuntimeError("secret must not appear")):
            self.assertEqual(s.seal_window(synthetic_window()), Failure("internal_error"))
        self.assertEqual(s.audit_records[-1]["detail"], "backend_exception")
        self.assertNotIn("secret must not appear", json.dumps(s.audit_records))
        self.assertTrue(s.incomplete)

    def test_busy_attempt_does_not_finalize_pending(self):
        s = self.sender()
        request = s.begin_attempt(self.material[2], "one")
        self.assertEqual(s.begin_attempt(self.material[2], "two"), Failure("session_busy"))
        self.assertEqual(s.state, "PENDING")
        self.assertEqual(s.attempt_id, "one")
        self.assertEqual(s.audit_records[-1]["event_type"], "session_message")
        self.assertIsInstance(request, bytes)

    def test_reused_attempt_id_stops_with_actual_audited_state(self):
        s, _ = self.active()
        self.assertEqual(s.begin_attempt(self.material[2], "synthetic-attempt"), Failure("internal_error"))
        self.assertTrue(s.incomplete)
        self.assertEqual(s.audit_records[-1]["state_after"], s.state)
        self.assertEqual(s.state, "FAILED")
        self.assertIsNone(s._key)

    def test_terminal_handshake_success_once(self):
        s, v = self.active()
        rows = s.audit_records
        self.assertEqual([r["event_type"] for r in rows], ["reconstruction", "session_establishment"])
        self.assertTrue(rows[-1]["identity_authenticated"])
        self.assertEqual(rows[-1]["authentication_result"], "pass")
        self.assertIsNotNone(rows[-1]["latency_ns"]["session_establishment"])
        self.assertEqual(rows[-1]["latency_ns"]["kdf"], s.kdf_timings_ns[-1])
        self.assertNotEqual(rows[-1]["event_id"].split(":")[0], v.boot_id.hex())
        s.finish_session(REFUSAL)
        self.assertEqual(s.audit_records[-1]["event_type"], "session_message")
        self.validate(s)

    def test_terminal_refusal_not_inferred_verifier_reason(self):
        s = self.sender()
        s.begin_attempt(self.material[2], "one")
        self.assertEqual(s.answer_challenge(REFUSAL), Failure("session_refused"))
        self.assertEqual(s.audit_records[-1]["reason"], "session_refused")
        self.assertEqual(s.audit_records[-1]["authentication_result"], "not_checked")
        self.assertIsNone(s._candidate)

    def test_terminal_timeout(self):
        s = self.sender()
        s.begin_attempt(self.material[2], "one")
        with patch("puf_snn.auth.session.time.monotonic_ns", return_value=s._deadline):
            self.assertEqual(s.answer_challenge(REFUSAL), Failure("handshake_timeout"))
        self.assertEqual(s.audit_records[-1]["event_type"], "session_establishment")
        self.validate(s)

    def test_sender_recorder_random_failure_fails_closed(self):
        with patch("puf_snn.auth.sender.secrets.token_bytes", side_effect=OSError("rng")):
            with self.assertRaisesRegex(ValueError, "internal_error"): self.sender()

    def test_handshake_failure_audits(self):
        from puf_snn.auth.verifier import Verifier
        for case in ("malformed", "version", "binding", "proof"):
            with self.subTest(case=case):
                s = self.sender()
                v = Verifier([self.material[1]])
                challenge = v.begin_session(s.begin_attempt(self.material[2], "one"))
                if case == "malformed":
                    result = s.answer_challenge(b"bad")
                    reason = "malformed_message"
                elif case == "version":
                    # Transcript's protocol follows LP(domain) in the challenge.
                    bad = bytearray(challenge)
                    domain_length = int.from_bytes(bad[10:12], "big")
                    bad[12+domain_length+1] = 3
                    result = s.answer_challenge(bytes(bad))
                    reason = "unsupported_protocol_version"
                elif case == "binding":
                    s._nonce = b"different".ljust(32, b"0")
                    result = s.answer_challenge(challenge)
                    reason = "invalid_challenge"
                else:
                    response = v.confirm_session(s.answer_challenge(challenge))
                    result = s.finish_session(response[:-32]+bytes(32))
                    reason = "key_confirmation_failed"
                self.assertEqual(result, Failure(reason))
                row = s.audit_records[-1]
                self.assertEqual((row["event_type"], row["reason"]), ("session_establishment", reason))
                self.assertEqual(row["authentication_result"], "fail" if case == "proof" else "not_checked")
                self.assertIsNone(s._key)
                self.validate(s)

    def test_window_success_is_seal_only(self):
        s, v = self.active()
        before = v.session_status(s.session_id)
        result = s.seal_window(synthetic_window())
        row = s.audit_records[-1]
        self.assertEqual((row["event_type"], row["decision"], row["reason"]), ("sender_window", "accept", "accepted"))
        self.assertEqual(row["sequence_number"], 0)
        self.assertEqual(parse_envelope(result).window.sequence_number, 0)
        self.assertEqual(v.session_status(s.session_id), before)
        for field in ("last_accepted_before", "last_accepted_after", "expected_sequence", "authenticated_bytes_sha256"):
            self.assertIsNone(row[field])
        self.assertEqual(row["authentication_result"], "not_checked")
        self.assertFalse(row["identity_authenticated"])
        self.assertGreaterEqual(row["latency_ns"]["sender_prepare"], row["latency_ns"]["sender_hmac"])
        self.validate(s)

    def test_invalid_schema_no_sequence_consumed(self):
        s, _ = self.active()
        self.assertEqual(s.seal_window({}), Failure("invalid_payload_schema"))
        self.assertEqual(s.next_to_send, 0)
        self.assertEqual(s.audit_records[-1]["reason"], "invalid_payload_schema")
        self.assertIsNone(s.audit_records[-1]["latency_ns"]["sender_hmac"])
        self.validate(s)

    def test_malformed_identifier_not_copied_to_audit(self):
        s, _ = self.active()
        self.assertEqual(s.seal_window(replace(synthetic_window(), window_id="bad id")), Failure("malformed_message"))
        self.assertIsNone(s.audit_records[-1]["window_id"])
        self.assertEqual(s.next_to_send, 0)
        self.validate(s)

    def test_quality_failure_no_sequence_consumed(self):
        s, _ = self.active()
        self.assertEqual(s.seal_window(replace(synthetic_window(), tracking_valid_count=113)), Failure("data_quality_failure"))
        self.assertEqual(s.next_to_send, 0)
        self.assertEqual(s.audit_records[-1]["reason"], "data_quality_failure")
        self.assertEqual(parse_envelope(s.seal_window(synthetic_window())).window.sequence_number, 0)

    def test_inactive(self):
        s = self.sender()
        self.assertEqual(s.seal_window(synthetic_window()), Failure("inactive_session"))
        self.assertIsNone(s.audit_records[-1]["sequence_number"])
        self.validate(s)

    def test_expiration(self):
        s, _ = self.active()
        with patch("puf_snn.auth.sender.time.monotonic_ns", return_value=s._start+s.limits.session_ttl_ms*1_000_000):
            self.assertEqual(s.seal_window(synthetic_window()), Failure("expired_session"))
        self.assertEqual(s.audit_records[-1]["state_after"], "CLOSED")
        self.assertIsNone(s._key)
        self.assertEqual(s.next_to_send, 0)
        self.validate(s)

    def test_max_window_audits_close_then_inactive(self):
        s, _ = self.active(max_windows=1)
        self.assertIsInstance(s.seal_window(synthetic_window()), bytes)
        self.assertEqual(s.audit_records[-1]["reason"], "session_limit_reached")
        self.assertEqual(s.audit_records[-1]["event_type"], "session_control")
        self.assertIsNone(s._key)
        self.assertEqual(s.seal_window(synthetic_window()), Failure("inactive_session"))
        self.assertEqual(s.next_to_send, 1)
        self.validate(s)

    def test_missing_delivery_does_not_reuse_sequence(self):
        s, _ = self.active()
        s.seal_window(synthetic_window())
        self.assertEqual(parse_envelope(s.seal_window(synthetic_window())).window.sequence_number, 1)
        self.assertEqual([r["sequence_number"] for r in s.audit_records if r["event_type"] == "sender_window"], [0, 1])

    def test_secret_hygiene_serialization(self):
        s, _ = self.active()
        key = s._key
        prk = hkdf_extract(s._context.server_nonce, self.material[1].credential4)
        s.seal_window(synthetic_window())
        serialized = json.dumps(s.audit_records)
        for secret in (self.material[2].candidate_credential, self.material[1].credential4, key, prk):
            self.assertNotIn(secret.hex(), serialized)
            self.assertNotIn(hashlib.sha256(secret).hexdigest(), serialized)
            self.assertNotIn(repr(secret), serialized)
        for field in ("candidate_credential", "candidate_message", "credential4", "PRK", "K", "session_key",
                      "puf_reference", "raw_puf", "noisy64", "helper_data", "helper_bits", "correct_match",
                      "wrong_match", "evaluator_wrong_match", "true_error_count", "ground_truth", "samples"):
            self.assertNotIn('"'+field+'"', serialized)
        self.assertNotIn(json.dumps(self.material[0].helper_data.helper_bits), serialized)
        self.assertNotIn(json.dumps((0,)*64), serialized)

    def test_audit_failure_never_returns_unaudited_envelope_or_reuses_sequence(self):
        s, _ = self.active()
        with patch.object(s._audit, "prepare", side_effect=MemoryError):
            self.assertEqual(s.seal_window(synthetic_window()), Failure("internal_error"))
        self.assertTrue(s.incomplete)
        self.assertEqual(s.next_to_send, 1)
        self.assertIsNone(s._key)
        self.assertEqual(s.audit_records[-1]["origin"], "sender")
        with self.assertRaises(RuntimeError): s.seal_window(synthetic_window())

    def test_reconstruction_audit_failure_blocks_handshake(self):
        s = self.sender()
        with patch.object(s._audit, "prepare", side_effect=MemoryError):
            self.assertEqual(s.begin_attempt(self.material[2], "one"), Failure("internal_error"))
        self.assertTrue(s.incomplete)
        self.assertIsNone(s._candidate)

    def test_sender_disk_failure_stops(self):
        s, _ = self.active()
        with TemporaryDirectory() as directory:
            writer = AuditJSONL(directory)
            writer._file.close()
            with self.assertRaises(RuntimeError): s.flush_audit(writer)
            self.assertTrue(s.incomplete)
            self.assertTrue((Path(directory)/"INCOMPLETE").exists())
            self.assertIsNone(s._key)

    def test_sender_snapshot_is_independent(self):
        s, _ = self.active()
        snapshot = s.audit_records
        snapshot[0]["reason"] = "changed"
        self.assertEqual(s.audit_records[0]["reason"], "accepted")

    def test_shutdown_all_active_and_pending_preserves_tombstones(self):
        v, old, _ = setup()
        current, _ = activate(v)
        other, _ = activate(v, "other-device")
        _, waiting, _ = pending(v)
        old_tombstone = next(t for t in v.tombstones if t.session_id == old)
        n = len(v.audit_records)
        closed = v.close_all_sessions()
        self.assertEqual({r.session_id for r in closed}, {current.hex(), other.hex()})
        self.assertFalse(v.active_session_ids)
        self.assertFalse(v._active)
        self.assertFalse(v._pending)
        self.assertEqual(next(t for t in v.tombstones if t.session_id == old), old_tombstone)
        rows = v.audit_records[n:]
        self.assertEqual(len(rows), 3)
        self.assertEqual(sum(r["event_type"] == "session_control" for r in rows), 2)
        self.assertEqual(sum(r["event_type"] == "session_establishment" for r in rows), 1)
        self.assertTrue(all(r["reason"] == "session_closed" for r in rows))
        self.assertEqual(v.session_status(waiting.session_id).state, "FAILED")
        self.assertTrue(all(not hasattr(t, "key") for t in v.tombstones))
        issued, tombstones, audit = v._issued.copy(), v.tombstones, v.audit_records
        self.assertEqual(v.close_all_sessions(), [])
        self.assertEqual((v._issued, v.tombstones, v.audit_records), (issued, tombstones, audit))

    def test_shutdown_audit_failure_stops_without_reset(self):
        v, sid, _ = setup()
        before = v.session_status(sid)
        with patch.object(v._audit, "prepare", side_effect=MemoryError):
            with self.assertRaisesRegex(ValueError, "internal_error"): v.close_all_sessions()
        self.assertEqual(v.session_status(sid), before)
        self.assertTrue(v.incomplete)

    def test_demo_keeps_endpoint_audits_distinct(self):
        with TemporaryDirectory() as parent:
            output = Path(parent)/"demo"
            run_demo(output)
            sender = [json.loads(line) for line in (output/"sender/audit.jsonl").read_text().splitlines()]
            verifier = [json.loads(line) for line in (output/"audit.jsonl").read_text().splitlines()]
            self.assertTrue(all(r["origin"] == "sender" for r in sender))
            self.assertTrue(all(r["origin"] == "verifier" for r in verifier))
            self.assertEqual([r["sequence_number"] for r in sender if r["event_type"] == "sender_window"], [0, 1, 2])
            manifest = json.loads((output/"manifest.json").read_text())
            self.assertEqual(manifest["sender_audit_records"], len(sender))
            self.assertEqual(manifest["files"]["sender/audit.jsonl"], hashlib.sha256((output/"sender/audit.jsonl").read_bytes()).hexdigest())
