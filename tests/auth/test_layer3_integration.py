from dataclasses import replace
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from puf_snn.auth.binary_window import parse_envelope, F32, ProtocolError
from puf_snn.auth.config import AuthConfig
from puf_snn.auth.session import Failure, Limits, REFUSAL, SessionConfig
from puf_snn.reconstruction import reconstruct

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/python/scripts'))
from run_layer3_demo import initialize_material, establish, synthetic_window, run_demo


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.material=initialize_material()

    def test_actual_reconstruction_and_seal_verify_release(self):
        binding,entry,_=self.material
        result=reconstruct((0,)*64,binding.helper_data)
        s,v,_=establish(AuthConfig(),(binding,entry,result))
        self.assertEqual(len(s.kdf_timings_ns),1)
        self.assertEqual(len(v.kdf_timings_ns),1)
        self.assertGreaterEqual(s.kdf_timings_ns[0],0)
        self.assertEqual(v.audit_records[0]['latency_ns']['kdf'],v.kdf_timings_ns[0])
        sid=s.session_id
        for seq in range(3):
            envelope=s.seal_window(synthetic_window())
            accepted=v.verify_window(envelope)
            self.assertEqual(accepted.result,'accept')
            self.assertEqual(v.release_accepted(accepted,lambda w:w.sequence_number),seq)
            self.assertEqual(parse_envelope(envelope).window,accepted.accepted_window)
            self.assertGreaterEqual(s.last_window_timing.sender_prepare_ns,s.last_window_timing.sender_hmac_ns)
        self.assertEqual(v.session_status(sid).accepted_count,3)

    def test_wrong_candidate_rejected_no_active_session(self):
        from puf_snn.auth.sender import Sender
        from puf_snn.auth.verifier import Verifier
        binding,entry,_=self.material
        s=Sender(binding);v=Verifier([entry])
        good=reconstruct((0,)*64,binding.helper_data)
        bad=replace(good,candidate_credential=bytes(4),candidate_message=(0,)*36)
        c=s.answer_challenge(v.begin_session(s.begin_attempt(bad,'wrong-test')))
        self.assertEqual(v.confirm_session(c),REFUSAL)
        self.assertEqual(v.last_reason,'key_confirmation_failed')
        self.assertFalse(v.active_session_ids)
        self.assertEqual(s.finish_session(REFUSAL),Failure('session_refused'))

    def test_sender_quality_failure_does_not_consume_sequence(self):
        s,v,_=establish(AuthConfig(),self.material)
        bad=replace(synthetic_window(),capture_end_ns=3000000121)
        self.assertEqual(s.seal_window(bad),Failure('data_quality_failure'))
        self.assertEqual(s.next_to_send,0)
        self.assertEqual(s.last_window_timing.result,'reject')
        self.assertEqual(v.verify_window(s.seal_window(synthetic_window())).reason,'accepted')

    def test_sender_consumes_sequence_even_without_delivery(self):
        s,v,_=establish(AuthConfig(),self.material)
        s.seal_window(synthetic_window())
        self.assertEqual(v.verify_window(s.seal_window(synthetic_window())).reason,'future_sequence_gap')
        self.assertEqual(s.next_to_send,2)

    def test_sender_max_window_removes_key(self):
        s,v,_=establish(AuthConfig(max_windows=1),self.material)
        envelope=s.seal_window(synthetic_window())
        self.assertIsNone(s._key)
        self.assertEqual(v.verify_window(envelope).reason,'accepted')
        self.assertEqual(s.seal_window(synthetic_window()),Failure('inactive_session'))

    def test_sender_deadline(self):
        s,_,_=establish(AuthConfig(),self.material)
        with patch('puf_snn.auth.sender.time.monotonic_ns',return_value=s._start+s.limits.session_ttl_ms*1000000):
            self.assertEqual(s.seal_window(synthetic_window()),Failure('expired_session'))
        self.assertIsNone(s._key)

    def test_demo_complete_exclusive_evidence(self):
        import jsonschema
        with TemporaryDirectory() as parent:
            output=Path(parent)/'demo'
            run_demo(output)
            self.assertTrue((output/'COMPLETE').exists())
            self.assertFalse((output/'INCOMPLETE').exists())
            manifest=json.loads((output/'manifest.json').read_text())
            self.assertEqual(manifest['accepted_windows'],3)
            self.assertEqual(manifest['last_accepted'],2)
            meta=json.loads((output/'metadata.json').read_text())
            self.assertEqual(meta['warmup_iterations'],20)
            self.assertEqual(manifest['warmup_rows_in_denominator'],0)
            rows=[json.loads(line) for line in (output/'audit.jsonl').read_text().splitlines()]
            schema=json.loads((ROOT/'schemas/auth-audit-v1.schema.json').read_text())
            for row in rows: jsonschema.validate(row,schema)
            self.assertEqual([r['sequence_number'] for r in rows if r['event_type']=='window'],[0,1,2])
            with self.assertRaises(FileExistsError): run_demo(output)

    def test_demo_failure_incomplete_preserves_partial_evidence(self):
        with TemporaryDirectory() as parent:
            output=Path(parent)/'failed'
            with patch('run_layer3_demo.write_json',side_effect=OSError):
                with self.assertRaises(OSError): run_demo(output)
            self.assertTrue((output/'INCOMPLETE').exists())
            self.assertFalse((output/'COMPLETE').exists())
            self.assertTrue((output/'config.json').exists())
