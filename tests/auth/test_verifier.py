from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from threading import Barrier
import unittest
from unittest.mock import patch

from puf_snn.auth.binary_window import encode_window, parse_envelope, U64, U32, U16
from puf_snn.auth.session import Limits, SessionConfig, RegistryEntry
from puf_snn.auth.verifier import Verifier
try:
    from .support import setup, activate, packet, window, wrap, offsets, mutate, CREDENTIAL
except ImportError:
    from support import setup, activate, packet, window, wrap, offsets, mutate, CREDENTIAL


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.v, self.sid, self.key = setup()

    def check(self, data, reason):
        before = self.v.session_status(self.sid)
        n = len(self.v.audit_records)
        result = self.v.verify_window(data)
        self.assertEqual(result.reason, reason)
        self.assertEqual(result.result, "accept" if reason == "accepted" else "reject")
        self.assertIsNotNone(result.verifier_auth_ns)
        self.assertGreaterEqual(result.verifier_auth_ns, 0)
        if reason != "accepted":
            self.assertIsNone(result.accepted_window)
            self.assertIsNone(result.authenticated_bytes)
            self.assertEqual(before, self.v.session_status(self.sid))
        self.assertEqual(sum(r['event_type'] == 'window' for r in self.v.audit_records[n:]), 1)
        return result

    def test_valid_consecutive_zero_one_two(self):
        for seq in range(3): self.check(packet(self.sid, self.key, seq), "accepted")
        status = self.v.session_status(self.sid)
        self.assertEqual((status.accepted_count, status.last_accepted), (3, 2))

    def test_duplicate(self):
        p = packet(self.sid, self.key)
        self.check(p, "accepted")
        self.check(p, "duplicate_sequence")

    def test_stale(self):
        for seq in range(2): self.check(packet(self.sid, self.key, seq), "accepted")
        self.check(packet(self.sid, self.key), "stale_sequence")

    def test_gap_and_late_missing_no_automatic_reconsideration(self):
        self.check(packet(self.sid, self.key, 2), "future_sequence_gap")
        row = self.v.audit_records[-1]
        self.assertEqual((row['expected_sequence'], row['missing_start'], row['missing_end'], row['missing_count']), (0,0,1,2))
        self.check(packet(self.sid, self.key, 0), "accepted")
        self.check(packet(self.sid, self.key, 2), "future_sequence_gap")
        self.check(packet(self.sid, self.key, 1), "accepted")
        self.assertEqual(self.v.session_status(self.sid).accepted_count, 2)
        self.check(packet(self.sid, self.key, 2), "accepted")

    def test_u64_max_is_gap_without_wrap(self):
        self.check(packet(self.sid, self.key, 2**64-1), "future_sequence_gap")
        self.assertEqual(self.v.audit_records[-1]['missing_count'], 2**64-1)

    def test_invalid_tag_high_sequence_cannot_poison(self):
        p = packet(self.sid, self.key, 999999)
        obj = json.loads(p); obj['authentication']['tag_hex'] = '00'*32
        self.check(json.dumps(obj).encode(), "invalid_tag")
        self.assertFalse(self.v.audit_records[-1]['identity_authenticated'])
        self.assertIsNone(self.v.audit_records[-1]['last_accepted_before'])
        self.check(packet(self.sid, self.key), "accepted")

    def test_stale_tag_on_protected_mutations(self):
        e = parse_envelope(packet(self.sid, self.key)); a = e.authenticated_bytes; o = offsets(a)
        for offset, value in ((o['seq'], U64(999999)), (o['sample']+10,U32(0x3f800000)),
                              (o['end'],U64(3_000_000_001))):
            with self.subTest(offset=offset):
                self.check(wrap(mutate(a,offset,value),self.sid,self.key,tag=e.tag), 'invalid_tag')

    def test_device_mutation_precedence(self):
        e = parse_envelope(packet(self.sid,self.key))
        for device, reason in [('other-device','invalid_tag'), ('absent-device','unknown_device')]:
            a = encode_window(replace(window(self.sid),device_id=device))
            self.check(wrap(a,self.sid,self.key,tag=e.tag),reason)

    def test_session_mutation_precedence(self):
        other, _ = activate(self.v,'other-device')
        e = parse_envelope(packet(self.sid,self.key))
        for sid,reason in [(other,'invalid_tag'), (b'?'*16,'unknown_session')]:
            a = encode_window(window(sid))
            self.check(wrap(a,sid,self.key,tag=e.tag),reason)

    def test_valid_tag_wrong_owner(self):
        self.check(packet(self.sid,self.key,device_id='other-device'),'device_session_mismatch')
        row=self.v.audit_records[-1]
        self.assertEqual(row['authentication_result'],'pass')
        self.assertFalse(row['identity_authenticated'])
        self.assertIsNone(row['expected_sequence'])

    def test_key_id_never_selects_key(self):
        other,_=activate(self.v,'other-device')
        e=parse_envelope(packet(self.sid,self.key))
        self.check(wrap(e.authenticated_bytes,self.sid,self.key,key_id=other.hex()),'invalid_key_id')
        self.assertEqual(self.v.audit_records[-1]['authentication_result'],'pass')
        self.check(wrap(e.authenticated_bytes,self.sid,self.key,key_id=other.hex(),tag=bytes(32)),'invalid_tag')

    def test_disabled_device(self):
        self.v._registry['sim-device']=RegistryEntry('sim-device','enrollment-1',CREDENTIAL,enabled=False)
        self.check(packet(self.sid,self.key),'unknown_device')

    def test_enrollment_binding(self):
        self.v._registry['sim-device']=RegistryEntry('sim-device','different-enrollment',CREDENTIAL)
        self.check(packet(self.sid,self.key),'device_session_mismatch')

    def test_malformed_inputs_leave_state(self):
        valid=packet(self.sid,self.key)
        for bad in (b'',b'{}',valid+b'x',b'\xff',b' '*16385,bytearray(valid),
                    b'{"protected":{},"protected":{},"authentication":{}}',b'\xef\xbb\xbf'+valid):
            with self.subTest(kind=type(bad),size=len(bad)): self.check(bad,'malformed_message')

    def test_binary_float_representation_precedes_tag(self):
        a=encode_window(window(self.sid)); off=offsets(a)['sample']+10
        for word in (0x80000000,0x7f800000,0x7fc00000):
            self.check(wrap(mutate(a,off,U32(word)),self.sid,self.key,tag=bytes(32)),'invalid_payload_schema')

    def test_protocol_precedes_lookup(self):
        a=encode_window(window(self.sid))
        self.check(wrap(mutate(a,4,b'\x00\x03'),self.sid,self.key),'unsupported_protocol_version')

    def test_ttl_equality_rejection_does_not_expire_as_side_effect(self):
        deadline=self.v.session_status(self.sid).deadline_ns
        with patch('puf_snn.auth.verifier.time.monotonic_ns',return_value=deadline):
            self.check(packet(self.sid,self.key),'expired_session')
        self.assertEqual(self.v.session_status(self.sid).state,'ACTIVE')

    def test_expire_control_removes_key_and_retains_tombstone(self):
        deadline=self.v.session_status(self.sid).deadline_ns
        with patch('puf_snn.auth.verifier.time.monotonic_ns',return_value=deadline):
            self.assertEqual(len(self.v.expire_due_sessions()),1)
            self.assertEqual(self.v.expire_due_sessions(),[])
        self.assertNotIn(self.sid,self.v.active_session_ids)
        self.check(packet(self.sid,self.key),'expired_session')
        self.assertFalse(hasattr(self.v.tombstones[0],'key'))

    def test_traffic_never_refreshes_ttl(self):
        before=self.v.session_status(self.sid).deadline_ns
        self.check(packet(self.sid,self.key),'accepted')
        self.check(packet(self.sid,self.key,4),'future_sequence_gap')
        self.check(packet(self.sid,bytes(32),999999),'invalid_tag')
        self.assertEqual(self.v.session_status(self.sid).deadline_ns,before)

    def test_deadline_rechecked_after_quality(self):
        from puf_snn.auth.verifier import validate_quality
        deadline=self.v.session_status(self.sid).deadline_ns
        with patch('puf_snn.auth.verifier.time.monotonic_ns',return_value=deadline-1) as clock:
            def quality(w):
                validate_quality(w)
                clock.return_value=deadline
            with patch('puf_snn.auth.verifier.validate_quality',side_effect=quality):
                self.check(packet(self.sid,self.key),'expired_session')

    def test_deadline_rechecked_after_audit_allocation(self):
        deadline=self.v.session_status(self.sid).deadline_ns
        prepare=self.v._audit.prepare
        with patch('puf_snn.auth.verifier.time.monotonic_ns',return_value=deadline-1) as clock:
            def reserve(rows):
                result=prepare(rows);clock.return_value=deadline;return result
            with patch.object(self.v._audit,'prepare',side_effect=reserve):
                self.check(packet(self.sid,self.key),'expired_session')

    def test_local_close(self):
        self.assertEqual(self.v.close_session(self.sid).reason,'session_closed')
        self.assertIsNone(self.v.close_session(self.sid))
        self.check(packet(self.sid,self.key),'inactive_session')
        self.assertFalse(self.v.active_session_ids)

    def test_max_windows_last_accept_once(self):
        v,sid,key=setup(SessionConfig(Limits(max_windows=2)))
        self.assertEqual(v.verify_window(packet(sid,key,0)).reason,'accepted')
        final=packet(sid,key,1)
        self.assertEqual(v.verify_window(final).reason,'accepted')
        self.assertEqual(v.verify_window(final).reason,'inactive_session')
        self.assertFalse(v.active_session_ids)
        self.assertEqual(v.tombstones[-1].reason,'session_limit_reached')
        self.assertEqual([r['reason'] for r in v.audit_records if r['event_type']!='session_establishment'],
                         ['accepted','accepted','session_limit_reached','inactive_session'])

    def test_replacement_new_sequence_zero_old_cannot_reset(self):
        self.check(packet(self.sid,self.key),'accepted')
        new,key=activate(self.v)
        self.check(packet(self.sid,self.key,1),'inactive_session')
        self.assertEqual(self.v.verify_window(packet(new,key)).reason,'accepted')
        self.assertEqual(self.v.session_status(new).accepted_count,1)
        self.assertEqual([r['reason'] for r in self.v.audit_records if r['event_type']=='session_control'],['session_replaced'])

    def test_restart(self):
        v=Verifier([RegistryEntry('sim-device','enrollment-1',CREDENTIAL)])
        self.assertEqual(v.verify_window(packet(self.sid,self.key)).reason,'unknown_session')

    def test_concurrent_duplicate_barrier(self):
        ready=Barrier(3); data=packet(self.sid,self.key)
        def verify(): ready.wait();return self.v.verify_window(data)
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs=[pool.submit(verify) for _ in range(2)]
            ready.wait();results=[j.result(timeout=10) for j in jobs]
        self.assertEqual(sorted(r.reason for r in results),['accepted','duplicate_sequence'])
        self.assertEqual(self.v.session_status(self.sid).accepted_count,1)

    def test_immutable_exact_bytes_and_payload(self):
        data=packet(self.sid,self.key);source=json.loads(data)
        r=self.check(data,'accepted')
        source['protected']['bytes_b64']='changed'
        self.assertEqual(hashlib.sha256(r.authenticated_bytes).hexdigest(),r.authenticated_bytes_sha256)
        for target,name,value in [(r,'reason','changed'),(r.accepted_window,'window_id','changed'),
                                  (r.accepted_window.samples[0],'capture_time_ns',0),
                                  (r.accepted_window.samples[0].position_m[0],'bits',123)]:
            with self.assertRaises(FrozenInstanceError): setattr(target,name,value)
        self.assertEqual(self.v.release_accepted(r,lambda w:w),r.accepted_window)

    def test_substituted_payload_and_legacy_gate_cannot_release(self):
        r=self.check(packet(self.sid,self.key),'accepted')
        wrong=replace(r,accepted_window=replace(r.accepted_window,capture_end_ns=3_000_000_001))
        class EqualToAnything:
            def __eq__(self, other): return True
        for supplied in [wrong,replace(r,event_id='fake'),replace(r,accepted_window=EqualToAnything()),
                         replace(r),{'result':'accept','reason':'accepted'},
                         Verifier([]).verify_window(b'{}')]:
            with self.assertRaises(ValueError): self.v.release_accepted(supplied,lambda w:self.fail('released'))

    def test_consumer_failure_keeps_commit_and_stops(self):
        r=self.check(packet(self.sid,self.key),'accepted')
        def fail(window): raise OSError('local consumer failed')
        with self.assertRaisesRegex(RuntimeError,'incomplete evidence'): self.v.release_accepted(r,fail)
        self.assertEqual(self.v.session_status(self.sid).accepted_count,1)
        self.assertTrue(self.v.incomplete)
        self.assertEqual(self.v.audit_records[-1]['event_type'],'session_control')

    def test_audit_allocation_failure_no_acceptance(self):
        before=self.v.session_status(self.sid)
        with patch.object(self.v._audit,'prepare',side_effect=MemoryError):
            result=self.v.verify_window(packet(self.sid,self.key))
        self.assertEqual(result.reason,'internal_error')
        self.assertEqual(self.v.session_status(self.sid),before)
        self.assertTrue(self.v.incomplete)
        self.assertEqual(self.v.audit_records[-1]['detail'],'audit_unavailable')
        with self.assertRaises(RuntimeError): self.v.verify_window(packet(self.sid,self.key))

    def test_result_allocation_failure_no_acceptance(self):
        before=self.v.session_status(self.sid)
        with patch('puf_snn.auth.verifier.VerificationResult',side_effect=MemoryError):
            result=self.v.verify_window(packet(self.sid,self.key))
        self.assertEqual(result.reason,'internal_error')
        self.assertEqual(self.v.session_status(self.sid),before)

    def test_invariant_violation_fails_closed(self):
        a=self.v._active['sim-device'];self.v._active['sim-device']=replace(a,last_accepted=5)
        result=self.v.verify_window(packet(self.sid,self.key))
        self.assertEqual(result.reason,'internal_error')
        self.assertTrue(self.v.incomplete)
        self.assertEqual(self.v.audit_records[-1]['detail'],'invariant_failure')
