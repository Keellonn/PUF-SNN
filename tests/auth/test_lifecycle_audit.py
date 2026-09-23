import unittest
from unittest.mock import patch

from puf_snn.auth.binary_window import LP, V
from puf_snn.auth.session import (REFUSAL, RegistryEntry, Transcript, frame, unframe,
                                 client_proof, derive_session_key)
from puf_snn.auth.verifier import Verifier
try:
    from .support import setup, packet, CREDENTIAL
except ImportError:
    from support import setup, packet, CREDENTIAL


def pending(v):
    request=frame(b'P3RQ'+V(2,0)+LP(b'sim-device')+bytes(32))
    r=unframe(v.begin_session(request));r.expect(b'P3CH');t=r.lp()
    context=Transcript.parse(t);key=derive_session_key(CREDENTIAL,t)
    return request,context,frame(b'P3CF'+V(2,0)+context.session_id+client_proof(key,t))


class LifecycleAuditTests(unittest.TestCase):
    def fresh(self): return Verifier([RegistryEntry('sim-device','enrollment-1',CREDENTIAL)])

    def test_activation_once_duplicate_confirmation_message(self):
        v=self.fresh();_,c,confirmation=pending(v)
        self.assertEqual(v.audit_records,())
        v.confirm_session(confirmation)
        self.assertEqual(v.audit_records[0]['event_type'],'session_establishment')
        self.assertTrue(v.audit_records[0]['identity_authenticated'])
        self.assertEqual(v.confirm_session(confirmation),REFUSAL)
        self.assertEqual(v.audit_records[-1]['event_type'],'session_message')
        self.assertEqual(v.audit_records[-1]['reason'],'inactive_session')
        self.assertEqual(sum(r['event_type']=='session_establishment' for r in v.audit_records),1)

    def test_rejected_requests_and_unmatched_confirmations(self):
        v=self.fresh()
        self.assertEqual(v.begin_session(b'{}'),REFUSAL)
        self.assertEqual(v.audit_records[-1]['event_type'],'session_establishment')
        v.confirm_session(b'{}')
        self.assertEqual(v.audit_records[-1]['event_type'],'session_message')
        self.assertEqual(len(v.audit_records),2)

    def test_pending_busy_does_not_finalize_original(self):
        v=self.fresh();request,c,confirmation=pending(v)
        v.begin_session(request)
        self.assertEqual(v.audit_records[-1]['reason'],'session_busy')
        v.confirm_session(confirmation)
        self.assertEqual(v.audit_records[-1]['reason'],'accepted')
        self.assertEqual(v.active_session_ids,(c.session_id,))

    def test_invalid_proof_and_pending_window(self):
        v=self.fresh();_,c,confirmation=pending(v)
        self.assertEqual(v.verify_window(packet(c.session_id,bytes(32))).reason,'inactive_session')
        v.confirm_session(confirmation[:-32]+bytes(32))
        self.assertEqual(v.audit_records[-1]['reason'],'key_confirmation_failed')
        self.assertEqual(v.audit_records[-1]['authentication_result'],'fail')
        self.assertFalse(v.active_session_ids)
        self.assertEqual(v.verify_window(packet(c.session_id,bytes(32))).reason,'inactive_session')

    def test_pending_expiry_one_terminal_record(self):
        v=self.fresh()
        with patch('puf_snn.auth.session.time.monotonic_ns',return_value=0) as clock:
            _,c,_=pending(v)
            clock.return_value=10_000_000_000
            v.expire_pending();v.expire_pending()
        self.assertEqual(len(v.audit_records),1)
        self.assertEqual(v.audit_records[0]['reason'],'handshake_timeout')
        self.assertEqual(v.tombstones[0].state,'FAILED')

    def test_activation_audit_failure_does_not_replace_old(self):
        v,sid,_=setup();_,c,confirmation=pending(v)
        before=v.session_status(sid)
        with patch.object(v._audit,'prepare',side_effect=MemoryError):
            self.assertEqual(v.confirm_session(confirmation),REFUSAL)
        self.assertEqual(v.session_status(sid),before)
        self.assertEqual(v.active_session_ids,(sid,))
        self.assertEqual(v.session_status(c.session_id).state,'PENDING')
        self.assertTrue(v.incomplete)

    def test_close_audit_failure_preserves_active_state(self):
        v,sid,_=setup();before=v.session_status(sid)
        with patch.object(v._audit,'prepare',side_effect=MemoryError):
            with self.assertRaisesRegex(ValueError,'internal_error'): v.close_session(sid)
        self.assertEqual(v.session_status(sid),before)
        self.assertEqual(v.audit_records[-1]['event_type'],'session_control')

    def test_utc_does_not_control_admission(self):
        from datetime import datetime, timezone
        v,sid,key=setup()
        with patch('puf_snn.auth.audit.datetime') as wall:
            wall.now.return_value=datetime(1970,1,1,tzinfo=timezone.utc)
            self.assertEqual(v.verify_window(packet(sid,key)).reason,'accepted')
        self.assertTrue(v.audit_records[-1]['recorded_utc'].startswith('1970-01-01'))
