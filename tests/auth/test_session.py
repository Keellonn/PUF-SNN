"""Public synthetic handshake and unchanged Layer 2 integration tests."""
from dataclasses import replace, fields
import hashlib
import inspect
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from puf_snn.auth.binary_window import LP, V, ProtocolError
from puf_snn.auth.session import (
    Transcript, Limits, SessionConfig, RegistryEntry, Sender, Verifier, Failure,
    provision_device, provision_verifier, derive_session_key, client_proof, server_proof,
    hkdf_extract, hkdf_expand, frame, REFUSAL,
)
from puf_snn.reconstruction import enroll, reconstruct, ReconstructionResult

F = json.loads((Path(__file__).parent/'fixtures/binary-v2/vectors.json').read_text())['H0']
REFERENCE = (0,)*64


def candidate(credential):
    bits = tuple((byte >> shift) & 1 for byte in credential for shift in range(7,-1,-1)) + (0,)*4
    return ReconstructionResult('candidate_valid_format','decoded',0,bits,credential,True,None)


def sender(credential=bytes.fromhex('00000001'), limits=Limits()):
    helper = enroll(REFERENCE, credential, enrollment_id='enrollment-1')
    return Sender(provision_device('quest-02','enrollment-1',helper), limits)


def verifier(credential=bytes.fromhex('00000001'), config=SessionConfig()):
    return provision_verifier([RegistryEntry('quest-02','enrollment-1',credential)],config)


class SessionTests(unittest.TestCase):
    def test_h0_literals(self):
        t = Transcript('quest-02',bytes(range(32)),bytes(range(32,48)),bytes(range(16)),bytes(range(64,96))).encode()
        self.assertEqual(t,bytes.fromhex(F['transcript_hex']))
        self.assertEqual(len(t),161)
        self.assertEqual(hashlib.sha256(t).hexdigest(),F['sha256'])
        k = derive_session_key(bytes.fromhex('00000001'),t)
        c = client_proof(k,t)
        self.assertEqual(k.hex(),F['key'])
        self.assertEqual(c.hex(),F['client_proof'])
        self.assertEqual(server_proof(k,t,c).hex(),F['server_proof'])

    def test_context_and_kdf_validation(self):
        t = Transcript.parse(bytes.fromhex(F['transcript_hex']))
        credential = bytes.fromhex('00000001')
        key = derive_session_key(credential,t.encode())
        for change in ({'device_id':'quest-03'},{'client_nonce':b'x'*32},{'server_nonce':b'y'*32},
                       {'boot_id':b'z'*16},{'session_id':b'j'*16},
                       {'limits':Limits(10001,300000,10000)},{'limits':Limits(10000,300001,10000)},
                       {'limits':Limits(10000,300000,10001)}):
            with self.subTest(change=change): self.assertNotEqual(key,derive_session_key(credential,replace(t,**change).encode()))
        self.assertEqual(key,derive_session_key(credential,t.encode()))
        self.assertNotEqual(key,derive_session_key(bytes(4),t.encode()))
        self.assertNotEqual(key,hkdf_expand(hkdf_extract(t.server_nonce,credential),LP(b'other-domain')+LP(t.encode()),32))
        for bad in (b'\x01',bytes(3),bytes(5),'00000001',bytearray(4)):
            with self.assertRaises(ProtocolError): derive_session_key(bad,t.encode())
        for name,size in (('client_nonce',32),('server_nonce',32),('boot_id',16),('session_id',16)):
            for value in (bytes(size-1),bytes(size+1),'x'*size):
                with self.assertRaises(ProtocolError): replace(t,**{name:value}).encode()
        for device in ('','a b','é','x'*129):
            with self.assertRaises(ProtocolError): replace(t,device_id=device).encode()
        for offset in (25,29,33,37):
            data=bytearray(t.encode());data[offset]^=1
            with self.assertRaises(ProtocolError): derive_session_key(credential,bytes(data))
        for args in ((True,1,1),(0,1,1),(1,0,1),(1,1,0),(2**32,1,1),(1,1,2**64)):
            with self.assertRaises(ProtocolError): Limits(*args)

    def test_correct_candidate_independent_keys_and_activation(self):
        s,v=sender(),verifier()
        r=reconstruct(REFERENCE,s.enrollment.helper_data)
        request=s.begin_attempt(r,'attempt-1')
        self.assertEqual(s.state,'PENDING')
        challenge=v.begin_session(request)
        self.assertFalse(v.active_session_ids)
        confirmation=s.answer_challenge(challenge)
        self.assertEqual(s.state,'PENDING')
        pending=next(iter(v._pending.values()))
        self.assertEqual(s._transcript,pending.transcript)
        self.assertEqual(s._key,pending.key)
        self.assertIsNone(s._candidate)
        response=v.confirm_session(confirmation)
        self.assertEqual(len(v.active_session_ids),1)
        self.assertEqual(s.state,'PENDING')
        self.assertIs(s.finish_session(response),s)
        self.assertEqual(s.state,'ACTIVE')
        self.assertEqual(v.confirm_session(confirmation),REFUSAL)
        self.assertEqual(v.last_reason,'inactive_session')
        self.assertEqual(next(iter(v._active.values())).accepted_count,0)

    def test_real_six_error_miscorrection_no_retry_or_active_state(self):
        enrolled=bytes(4)
        s,v=sender(enrolled),verifier(enrolled)
        response=tuple(1 if i in [31,36,37,39,40,41] else 0 for i in range(64))
        result=reconstruct(response,s.enrollment.helper_data)
        self.assertEqual(result.outcome,'candidate_valid_format')
        with patch('puf_snn.reconstruction.reconstruct',side_effect=AssertionError('retry')):
            request=s.begin_attempt(result,'miscorrection-1')
            challenge=v.begin_session(request)
            confirmation=s.answer_challenge(challenge)
            self.assertNotEqual(s._key,next(iter(v._pending.values())).key)
            self.assertEqual(v.confirm_session(confirmation),REFUSAL)
        self.assertEqual(v.last_reason,'key_confirmation_failed')
        self.assertFalse(v.active_session_ids)
        self.assertFalse(v._pending)
        self.assertEqual(len(v.tombstones),1)
        self.assertEqual(v.tombstones[0].state,'FAILED')
        self.assertFalse({'key','accepted_count','last_accepted'} & {f.name for f in fields(v.tombstones[0])})
        self.assertEqual(s.finish_session(REFUSAL),Failure('session_refused'))
        self.assertIsNone(s._key)
        # Evaluator-only assertion occurs after runtime rejection.
        self.assertEqual(result.candidate_credential,bytes.fromhex('00000001'))
        self.assertNotEqual(result.candidate_credential,enrolled)
        self.assertEqual(result.outcome,'candidate_valid_format')
        self.assertEqual(len(s._used_attempt_ids),1)

    def test_reconstruction_failure_and_malformed_results(self):
        s=sender()
        failures=[ReconstructionResult('decoder_failure','uncorrectable',-1,None,None,None,'decoder_declared_failure'),
                  ReconstructionResult('invalid_format_or_padding','decoded',5,(0,)*35+(1,),None,False,'nonzero_padding')]
        with patch('puf_snn.auth.session.secrets.token_bytes',side_effect=AssertionError('no handshake')):
            for i,result in enumerate(failures):
                self.assertEqual(s.begin_attempt(result,'failure-'+str(i)),Failure('failed_reconstruction',result.outcome))
        good=candidate(bytes(4))
        for i,result in enumerate((None,replace(good,padding_valid=False),replace(good,candidate_credential=b'x'),replace(good,candidate_message=(1,)*36))):
            self.assertEqual(s.begin_attempt(result,'invalid-'+str(i)),Failure('internal_error'))

    def test_altered_challenge_and_transcript(self):
        for offset in (10,49,59,91,107,123,155):
            s,v=sender(),verifier()
            challenge=v.begin_session(s.begin_attempt(candidate(bytes.fromhex('00000001')),'a'))
            bad=bytearray(challenge);bad[offset]^=1
            answer=s.answer_challenge(bytes(bad))
            if isinstance(answer,bytes): self.assertEqual(v.confirm_session(answer),REFUSAL)
            else: self.assertIsInstance(answer,Failure)
            self.assertFalse(v.active_session_ids)

    def test_wrong_length_proofs_and_reflection(self):
        for trim in (-1,1):
            s,v=sender(),verifier()
            confirm=s.answer_challenge(v.begin_session(s.begin_attempt(candidate(bytes.fromhex('00000001')),'a')))
            malformed=frame(confirm[4:-1] if trim<0 else confirm[4:]+b'x')
            self.assertEqual(v.confirm_session(malformed),REFUSAL)
            self.assertEqual(v.last_reason,'malformed_message')
            self.assertEqual(len(v._pending),1)
            ack=v.confirm_session(confirm)
            malformed=frame(ack[4:-1] if trim<0 else ack[4:]+b'x')
            self.assertEqual(s.finish_session(malformed),Failure('malformed_message'))
            self.assertIsNone(s._key)
        s,v=sender(),verifier()
        confirm=s.answer_challenge(v.begin_session(s.begin_attempt(candidate(bytes.fromhex('00000001')),'a')))
        reflected=frame(b'P3OK'+confirm[8:])
        self.assertEqual(s.finish_session(reflected),Failure('key_confirmation_failed'))
        self.assertFalse(v.active_session_ids)

    def test_old_proofs_fail_fresh_context(self):
        s,v=sender(),verifier()
        c=s.answer_challenge(v.begin_session(s.begin_attempt(candidate(bytes.fromhex('00000001')),'a')))
        ack=v.confirm_session(c)
        s.finish_session(ack)
        original=v.active_session_ids
        fresh=sender()
        fresh_c=fresh.answer_challenge(v.begin_session(fresh.begin_attempt(candidate(bytes.fromhex('00000001')),'b')))
        self.assertEqual(v.confirm_session(fresh_c[:-32]+c[-32:]),REFUSAL)
        self.assertEqual(v.last_reason,'key_confirmation_failed')
        self.assertEqual(v.active_session_ids,original)
        stale_ack=frame(b'P3OK'+V(2,0)+fresh._context.session_id+ack[-32:])
        self.assertEqual(fresh.finish_session(stale_ack),Failure('key_confirmation_failed'))

    def test_deadlines_busy_limits_and_replacement(self):
        with patch('puf_snn.auth.session.time.monotonic_ns',return_value=0) as clock:
            s,v=sender(),verifier()
            request=s.begin_attempt(candidate(bytes.fromhex('00000001')),'a')
            challenge=v.begin_session(request)
            self.assertEqual(v.begin_session(request),REFUSAL)
            self.assertEqual(v.last_reason,'session_busy')
            confirm=s.answer_challenge(challenge)
            clock.return_value=10_000_000_000
            self.assertEqual(v.confirm_session(confirm),REFUSAL)
            self.assertEqual(v.last_reason,'handshake_timeout')
            self.assertEqual(s.finish_session(REFUSAL),Failure('handshake_timeout'))
        s,v=sender(),verifier()
        c=s.answer_challenge(v.begin_session(s.begin_attempt(candidate(bytes.fromhex('00000001')),'a')))
        s.finish_session(v.confirm_session(c))
        old=v.active_session_ids
        s2=sender()
        c2=s2.answer_challenge(v.begin_session(s2.begin_attempt(candidate(bytes.fromhex('00000001')),'b')))
        s2.finish_session(v.confirm_session(c2))
        self.assertNotEqual(v.active_session_ids,old)
        self.assertEqual(len(v.active_session_ids),1)
        self.assertEqual(v.tombstones[0].reason,'session_replaced')

    def test_api_boundaries_and_random_failure(self):
        self.assertEqual(set(inspect.signature(Verifier.confirm_session).parameters),{'self','confirmation'})
        self.assertFalse(hasattr(Verifier,'verify_window'))
        s=sender()
        self.assertEqual(s.finish_session(b''),Failure('inactive_session'))
        with patch('puf_snn.auth.session.secrets.token_bytes',side_effect=OSError('unavailable')):
            self.assertEqual(s.begin_attempt(candidate(bytes(4)),'a'),Failure('internal_error'))
            with self.assertRaisesRegex(ProtocolError,'internal_error'): verifier()

    def test_reflection_unknown_sessions_and_no_sender_key_api(self):
        s,v=sender(),verifier()
        c=s.answer_challenge(v.begin_session(s.begin_attempt(candidate(bytes.fromhex('00000001')),'a')))
        with self.assertRaises(TypeError): v.confirm_session(c,key=s._key)
        with self.assertRaises(TypeError): v.confirm_session(c,candidate_credential=bytes(4))
        self.assertFalse(v.active_session_ids)
        reflected=server_proof(s._key,s._transcript,s._client)
        self.assertEqual(v.confirm_session(c[:-32]+reflected),REFUSAL)
        self.assertEqual(v.last_reason,'key_confirmation_failed')
        self.assertEqual(v.confirm_session(frame(b'P3CF'+V(2,0)+b'?'*16+b'?'*32)),REFUSAL)
        self.assertEqual(v.last_reason,'unknown_session')

    def test_resource_limits_collision_and_ttl_equality(self):
        s=sender()
        v=verifier(config=SessionConfig(max_pending_sessions=1,max_sessions_per_process=1))
        request=s.begin_attempt(candidate(bytes.fromhex('00000001')),'a')
        c=s.answer_challenge(v.begin_session(request))
        s.finish_session(v.confirm_session(c))
        self.assertEqual(v.begin_session(request),REFUSAL)
        self.assertEqual(v.last_reason,'resource_limit')
        with self.assertRaises(ProtocolError): SessionConfig(max_pending_sessions=True)
        with self.assertRaises(ProtocolError): SessionConfig(max_pending_sessions=2,max_sessions_per_process=1)
        with self.assertRaises(ProtocolError): provision_verifier([RegistryEntry('x','e',bytes(4))]*2)
        v=verifier()
        v._issued.add(b'x'*16)
        with patch('puf_snn.auth.session.secrets.token_bytes',side_effect=[b'x'*16,b'y'*16,b'z'*32]) as rng:
            v.begin_session(request)
        self.assertEqual(rng.call_count,3)
        self.assertIn(b'y'*16,v._pending)
        limits=Limits(10000,1,10)
        with patch('puf_snn.auth.session.time.monotonic_ns',return_value=0) as clock:
            s=sender(limits=limits);v=verifier(config=SessionConfig(limits))
            c=s.answer_challenge(v.begin_session(s.begin_attempt(candidate(bytes.fromhex('00000001')),'a')))
            ack=v.confirm_session(c)
            clock.return_value=1_000_000
            self.assertEqual(s.finish_session(ack),Failure('expired_session'))
            self.assertIsNone(s._key)

    def test_framing_and_version_rejection(self):
        s,v=sender(),verifier()
        request=s.begin_attempt(candidate(bytes.fromhex('00000001')),'a')
        for bad in (b'',request[:-1],request+b'x',b'\x00\x00\x10\x01'+bytes(4097)):
            self.assertEqual(v.begin_session(bad),REFUSAL)
            self.assertEqual(v.last_reason,'malformed_message')
        bad=bytearray(request);bad[9]=1
        self.assertEqual(v.begin_session(bytes(bad)),REFUSAL)
        self.assertEqual(v.last_reason,'unsupported_protocol_version')
        self.assertFalse(v._pending)
        self.assertFalse(v.active_session_ids)
