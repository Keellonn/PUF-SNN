from dataclasses import asdict
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from puf_snn.auth.audit import AuditJSONL, AuditUnavailable, Provenance, latency_summary, summarize_ns
from puf_snn.auth.config import AuthConfig
try:
    from .support import setup, packet
except ImportError:
    from support import setup, packet

ROOT=Path(__file__).resolve().parents[2]


class AuditTests(unittest.TestCase):
    def test_disk_io_does_not_hold_decision_lock(self):
        v,sid,key=setup();v.verify_window(packet(sid,key))
        io_started,finish_io=Event(),Event()
        class Writer:
            def flush(self, records):
                io_started.set()
                if not finish_io.wait(5): raise RuntimeError('test IO timeout')
        with ThreadPoolExecutor(max_workers=2) as pool:
            flush=pool.submit(v.flush_audit,Writer())
            self.assertTrue(io_started.wait(5))
            try:
                result=pool.submit(v.verify_window,packet(sid,key,1)).result(timeout=3)
                self.assertEqual(result.result,'accept')
            finally:
                finish_io.set()
            flush.result(timeout=5)

    def test_verifier_timer_includes_lock_wait(self):
        v,sid,key=setup();data=packet(sid,key)
        entered=Event();counter=[100]
        def clock():
            value=counter[0]
            entered.set()
            return value
        with ThreadPoolExecutor(max_workers=1) as pool:
            with patch('puf_snn.auth.verifier.time.perf_counter_ns',side_effect=clock):
                with v._lock:
                    job=pool.submit(v.verify_window,data)
                    self.assertTrue(entered.wait(5))
                    counter[0]=10100
                result=job.result(timeout=5)
        self.assertEqual(result.verifier_auth_ns,10000)

    def test_schema_all_decisions_nullable_fields_and_ids(self):
        import jsonschema
        v,sid,key=setup()
        provenance=Provenance(run_id='synthetic-test',source_record_id='row-0')
        v.verify_window(packet(sid,key),provenance)
        v.verify_window(packet(sid,key))
        v.verify_window(packet(sid,key,3))
        v.verify_window(packet(sid,key,1))
        v.verify_window(packet(sid,key))
        v.verify_window(packet(sid,bytes(32),999999))
        v.verify_window(b'{}')
        v.close_session(sid)
        v.verify_window(packet(sid,key))
        schema=json.loads((ROOT/'schemas/auth-audit-v1.schema.json').read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        for i,row in enumerate(v.audit_records,1):
            jsonschema.validate(row,schema)
            self.assertEqual(row['event_id'],f'{v.boot_id.hex()}:{i}')
            self.assertEqual(set(row),set(schema['required']))
        windows=[r for r in v.audit_records if r['event_type']=='window']
        accepted=windows[0]
        self.assertTrue(accepted['identity_authenticated'])
        self.assertEqual(accepted['provenance'],asdict(provenance))
        self.assertEqual((accepted['last_accepted_before'],accepted['last_accepted_after']),(None,0))
        self.assertEqual((accepted['state_before'],accepted['state_after']),('ACTIVE','ACTIVE'))
        self.assertEqual(windows[2]['missing_count'],2)
        invalid=windows[5]
        self.assertIsNone(invalid['authenticated_bytes_sha256'])
        self.assertIsNone(invalid['last_accepted_before'])
        self.assertEqual(windows[6]['reason'],'malformed_message')
        self.assertEqual(v.audit_records[-2]['decision'],'closed')

    def test_public_audit_snapshot_cannot_change_committed_records(self):
        v,sid,key=setup();v.verify_window(packet(sid,key))
        rows=v.audit_records;rows[0]['latency_ns']['verifier_auth']=999
        rows[0]['reason']='tampered'
        self.assertEqual(v.audit_records[0]['reason'],'accepted')
        self.assertNotEqual(v.audit_records[0]['latency_ns']['verifier_auth'],999)

    def test_secret_hygiene(self):
        v,sid,key=setup();v.verify_window(packet(sid,key))
        data=json.dumps(v.audit_records)
        self.assertNotIn(key.hex(),data)
        for forbidden in ('credential','candidate','PRK','helper','raw_puf','ground_truth','traceback'):
            self.assertNotIn(forbidden,data)
        self.assertNotIn('samples',data)

    def test_schema_rejects_unknown_missing_and_invalid_fields(self):
        import jsonschema
        v,sid,key=setup();v.verify_window(packet(sid,key))
        schema=json.loads((ROOT/'schemas/auth-audit-v1.schema.json').read_text())
        for mutation in [lambda r:r.update(secret='bad'),lambda r:r.pop('detail'),
                         lambda r:r.update(reason='wrong_credential'),lambda r:r.update(sequence_number=True)]:
            row=v.audit_records[0];mutation(row)
            with self.assertRaises(jsonschema.ValidationError): jsonschema.validate(row,schema)

    def test_envelope_schema(self):
        import jsonschema
        _,sid,key=setup()
        schema=json.loads((ROOT/'schemas/authenticated-window-v2.schema.json').read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(json.loads(packet(sid,key)),schema)

    def test_disk_flush_separate_and_append_once(self):
        v,sid,key=setup()
        with TemporaryDirectory() as directory:
            writer=AuditJSONL(directory)
            result=v.verify_window(packet(sid,key))
            before=result.verifier_auth_ns
            with patch('puf_snn.auth.audit.time.perf_counter_ns',side_effect=[100,10100]):
                v.flush_audit(writer)
            self.assertEqual(result.verifier_auth_ns,before)
            self.assertEqual(writer.io_batches,[dict(batch_size=2,audit_io_ns=10000,allocation='batch_only')])
            v.flush_audit(writer)
            v.verify_window(packet(sid,key))
            v.flush_audit(writer);writer.close()
            rows=(Path(directory)/'audit.jsonl').read_text().splitlines()
            self.assertEqual(len(rows),3)
            self.assertIsNone(json.loads(rows[0])['latency_ns']['audit_io'])
            with self.assertRaises(FileExistsError): AuditJSONL(directory)

    def test_disk_failure_after_acceptance_stops_without_rollback(self):
        v,sid,key=setup()
        with TemporaryDirectory() as directory:
            writer=AuditJSONL(directory);v.verify_window(packet(sid,key))
            writer._file.close()
            with self.assertRaises(AuditUnavailable): v.flush_audit(writer)
            self.assertEqual(v.session_status(sid).accepted_count,1)
            self.assertTrue(v.incomplete)
            self.assertTrue((Path(directory)/'INCOMPLETE').exists())
            self.assertFalse((Path(directory)/'COMPLETE').exists())
            with self.assertRaises(RuntimeError): v.verify_window(packet(sid,key))

    def test_p95_exact_hand_computed_outlier_retained(self):
        self.assertEqual(summarize_ns([0,10,20,30]),dict(count=4,mean=15,median=15,p95=28.5,maximum=30))
        self.assertEqual(summarize_ns([0,0,10000])['maximum'],10000)
        self.assertEqual(summarize_ns([5])['p95'],5)

    def test_empty_summary(self):
        self.assertEqual(summarize_ns([]),dict(count=0,mean=None,median=None,p95=None,maximum=None))

    def test_paired_totals_not_summed_percentiles_and_rejects_retained(self):
        rows=[dict(decision='accept',latency_ns=dict(sender_prepare=0,verifier_auth=100)),
              dict(decision='reject',latency_ns=dict(sender_prepare=100,verifier_auth=0)),
              dict(decision='reject',latency_ns=dict(sender_prepare=None,verifier_auth=300))]
        s=latency_summary(rows)['groups']
        self.assertEqual(s['overall']['total_layer3']['p95'],100)
        self.assertEqual(s['overall']['total_layer3']['count'],2)
        self.assertEqual(s['reject']['verifier_auth']['count'],2)
        self.assertEqual(s['closed']['verifier_auth']['count'],0)

    def test_config_exact_keys_and_bounds(self):
        config=AuthConfig.load(ROOT/'configs/authentication_v1.json')
        self.assertEqual(config,AuthConfig())
        for name in ('handshake_timeout_ms','session_ttl_ms','max_windows','max_pending_sessions',
                     'max_sessions_per_process','warmup_iterations'):
            for value in (True,False,1.0,'1',-1):
                with self.subTest(name=name,value=value):
                    obj=config.to_dict();obj[name]=value
                    with self.assertRaises(ValueError): AuthConfig.from_dict(obj)
        for name,value in [('handshake_timeout_ms',2**32),('session_ttl_ms',0),('max_windows',2**64),
                           ('max_pending_sessions',10001),('max_sessions_per_process',1000001),
                           ('warmup_iterations',10001),('protocol_profile','other')]:
            obj=config.to_dict();obj[name]=value
            with self.assertRaises(ValueError): AuthConfig.from_dict(obj)
        for obj in ({},{**config.to_dict(),'algorithm':'other'}):
            with self.assertRaises(ValueError): AuthConfig.from_dict(obj)
