"""NONFORMAL IMPLEMENTATION VALIDATION. Never runs or allocates formal evidence."""
from collections import Counter
from copy import deepcopy
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from puf_snn import tier1_v2 as h


class PlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.plan=h.compile_trial_plan(h.FROZEN_CONFIG)

    def test_formal_arithmetic(self):
        counts={r['role']:r['count'] for r in self.plan['counts']}
        for key,value in dict(primary_attack=6000,legitimate_control=1200,state_negative=1080,
                              parser_negative=1680,setup_window=23520,recovery_window=10200,
                              setup_handshake=11560,recovery_handshake=1040,lifecycle=10640).items():
            self.assertEqual(counts[key],value,key)
        self.assertEqual(sum(s['phase']=='measured' for s in self.plan['scenarios']),9840)
        self.assertEqual(sum(s['phase']=='warmup' for s in self.plan['scenarios']),20)
        self.assertEqual(counts['setup_window']+counts['legitimate_control']+counts['recovery_window'],34920)
        h.schema_validator('trial-plan').validate(self.plan)

    def test_determinism_and_balance(self):
        other=h.compile_trial_plan(h.FROZEN_CONFIG)
        self.assertEqual(self.plan,other)
        for group in ['A1','A2','A3','A4','A5','control']:
            rows=[s for s in self.plan['scenarios'] if s['group']==group and s['phase']=='measured']
            self.assertEqual(len(rows),1200)
            self.assertEqual(set(Counter((s['device_index'],s['enrollment_generation']) for s in rows).values()),{100})
            self.assertEqual(Counter(s['sequence_position'] for s in rows),{i:240 for i in range(5)})
            self.assertEqual(set(Counter((s['device_index'],s['source_window_index']) for s in rows).values()),{2})
            if group=='A3': self.assertEqual(set(Counter((s['device_index'],s['second_device_index']) for s in rows).values()),{40})
        rows=[s for s in self.plan['scenarios'] if s['group']=='A2']
        self.assertEqual(Counter(s['variant'] for s in rows),dict(replacement=400,expired_live=400,expired_cleanup=400))
        self.assertEqual(Counter(s['clock_mode'] for s in rows),dict(real=400,expiry_equality=400,expiry_plus_1ms=400))
        ids=[op['operation_id'] for s in self.plan['scenarios'] for op in s['operations']]
        self.assertEqual(len(ids),len(set(ids)))

    def test_designated_packet_source_frozen(self):
        for s in self.plan['scenarios']:
            if s['phase']!='measured': continue
            attack=next(o for o in s['operations'] if o['role'] in {'primary_attack','state_negative','parser_negative','legitimate_control'})
            if attack['boundary']=='pipeline.process_envelope':
                self.assertEqual(attack['source_window_index'],s['source_window_index'],s['scenario_id'])
            self.assertEqual(len({(p['sender_alias'],p['sequence_number']) for p in s['packet_plan']}),len(s['packet_plan']))

    def test_config_strict(self):
        h.validate_config(deepcopy(h.FROZEN_CONFIG))
        for key,value in [('primary_trials_per_group',12),('experiment_version',True),('device_count',True),
                          ('protocol_profile','v1'),('confidence_interval',dict(method='wilson',confidence=.95,sides=2)),
                          ('timing',{**h.FROZEN_CONFIG['timing'],'batch_size':True}),('unknown',1)]:
            config=deepcopy(h.FROZEN_CONFIG); config[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): h.validate_config(config)
        with self.assertRaises(ValueError): h.strict_json('{"a":1,"a":1}')
        with self.assertRaises(ValueError): h.strict_json('{"a":NaN}')
        with self.assertRaises(ValueError): h.validate_config(h.FROZEN_CONFIG,formal=True)
        with self.assertRaises(ValueError): h.validate_config(h.FROZEN_CONFIG,nonformal=True)

    def test_cp(self):
        from scipy.stats import binom
        self.assertEqual(h.clopper_pearson(0,0)['rate'],None)
        self.assertEqual(h.clopper_pearson(0,1200)['lower'],0)
        self.assertAlmostEqual(h.clopper_pearson(0,1200)['upper'],1-.025**(1/1200),14)
        self.assertAlmostEqual(h.clopper_pearson(0,1200)['upper']*100,.306933,5)
        self.assertEqual(h.clopper_pearson(1200,1200)['upper'],1)
        for x,n in [(1,10),(5,10),(17,83),(600,1200)]:
            r=h.clopper_pearson(x,n)
            self.assertAlmostEqual(binom.sf(x-1,n,r['lower']),.025,11)
            self.assertAlmostEqual(binom.cdf(x,n,r['upper']),.025,11)
        with self.assertRaises(ValueError): h.clopper_pearson(True,12)

    def test_formal_guards_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'never-created'
            with self.assertRaises(ValueError): h.formal_preflight(h.FROZEN_CONFIG,output)
            self.assertFalse(output.exists())
            config=deepcopy(h.FROZEN_CONFIG); config.update(execution_source_commit='0'*40,source_manifest_path='missing.json')
            with self.assertRaises(ValueError): h.formal_preflight(config,output,dummy_callbacks=True)
        with self.assertRaises(ValueError): h.EvidenceWriter(h.FORMAL_ROOT,h.nonformal_config(),{},nonformal=True)
        with self.assertRaises(ValueError): h.EvidenceWriter(h.ROOT/'results/nonformal',h.nonformal_config(),{},nonformal=True)
        self.assertFalse(h.FORMAL_ROOT.exists())


class RealArtifactGuardTests(unittest.TestCase):
    def test_real_mode_rejects_results_and_formal_identity_before_hash_or_load(self):
        with patch.object(h,'artifact_inventory') as inventory:
            for path in (h.FORMAL_ROOT,h.ROOT/'results/nonformal-real',h.ROOT/'tmp'/h.FORMAL_ID):
                with self.subTest(path=path),self.assertRaises(ValueError): h.run_real_nonformal(path)
            inventory.assert_not_called()

    def test_real_mode_bad_hash_never_imports_loader_or_allocates_output(self):
        import builtins
        native=builtins.__import__
        def guarded(name,*args,**kwargs):
            if name=='puf_snn.frozen_pipeline': self.fail('loader imported before hash gate')
            return native(name,*args,**kwargs)
        with tempfile.TemporaryDirectory() as temporary,patch.object(h,'artifact_inventory',return_value={'missing':'0'*64}),patch.object(builtins,'__import__',side_effect=guarded):
            output=Path(temporary)/'blocked'
            with self.assertRaises(ValueError): h.run_real_nonformal(output)
            self.assertFalse(output.exists())

    def test_nonformal_writer_rejects_formal_label_before_allocation(self):
        config=h.nonformal_config(); plan=h.compact_nonformal_plan(config)
        plan['validation_label']='FORMAL'
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'blocked'
            with self.assertRaises(ValueError): h.EvidenceWriter(output,config,plan,nonformal=True)
            self.assertFalse(output.exists())


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.output=Path(cls.temp.name)/'NONFORMAL'
        cls.config=h.nonformal_config()
        cls.plan=h.compact_nonformal_plan(cls.config)
        cls.reconciliation,cls.summary=h.run_nonformal(cls.output,config=cls.config,plan=cls.plan)
        cls.rows=sorted([r for f in h.ATTEMPT_FILES for r in h.read_rows(cls.output/(f+'.jsonl'))],key=lambda r:r['execution_index'])

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_all_groups_first_reasons(self):
        for group in h.FROZEN_CONFIG['primary_groups']+h.FROZEN_CONFIG['state_groups']+h.FROZEN_CONFIG['parser_groups']+['control']:
            rows=[r for r in self.rows if r['attack_group']==group and r['role'] in {'primary_attack','state_negative','parser_negative','legitimate_control'}]
            self.assertTrue(rows,group)
            for row in rows:
                with self.subTest(group=group,variant=row['attack_variant'],id=row['trial_id']):
                    self.assertEqual(row['execution_status'],'completed',row['error'])
                    self.assertEqual(row['expected']['reason'],row['observed']['reason'])
                    self.assertFalse(row['violations'])
        self.assertTrue(self.reconciliation['evidence_complete'],self.reconciliation['checks'])
        self.assertTrue(self.summary['expected_behavior_observed'],self.summary['violations'])

    def test_full_nonformal_evidence(self):
        self.assertFalse((self.output/'COMPLETE').exists())
        self.assertTrue((self.output/'INCOMPLETE').exists())
        for row in self.rows: self.assertEqual(row['validation_label'],h.LABEL)
        manifest=h.strict_json((self.output/'manifest.json').read_text())
        self.assertTrue(h.verify_pins(self.output,manifest['files']))
        h.schema_validator('summary').validate(self.summary)

    def test_tombstones_and_u64(self):
        seen=[]
        for r in self.rows:
            if r['attack_group']=='S1' and r['role']=='state_negative': seen.append(r['submitted']['sequence_number'])
            if r['attack_group']=='A2' and r['role']=='primary_attack' and r['attack_variant']!='expired_live':
                old=next(s for s in r['state_before']['sessions'] if s['session_alias']=='source')
                self.assertIsNone(old['accepted_count']); self.assertIsNone(old['deadline_ns'])
                self.assertIsNotNone(old['last_observed_active'])
        self.assertEqual(set(seen),{2**63,2**64-1})

    def test_recovery_identity_and_no_double_consume(self):
        packets={r['packet_id']:r for r in h.read_rows(self.output/'traffic.jsonl')}
        for r in self.rows:
            if r['role']=='state_negative' and r['attack_group']=='S6':
                recovery=[x for x in self.rows if x['parent_attack_trial_id']==r['trial_id'] and x['role']=='recovery_window']
                self.assertEqual(recovery[-1]['submitted']['packet_id'],r['submitted']['packet_id'])
            if r['injection_boundary']=='pipeline.process_envelope' and r['execution_status']=='completed':
                want=int(r['observed']['result']=='accept')
                self.assertEqual(r['calls_delta'],dict.fromkeys(['release','preprocessing','motion','anomaly'],want))
                self.assertEqual(r['consumed_event_delta'],want)
                self.assertIn(r['submitted']['packet_id'],packets)

    def test_reconciliation_detects_deleted_or_duplicate_rows(self):
        target=self.output/'attempts.jsonl'; original=target.read_bytes()
        sources=h.strict_json((self.output/'source_manifest.json').read_text()); artifacts=h.strict_json((self.output/'artifact_manifest.json').read_text())
        try:
            target.write_bytes(original.split(b'\n',1)[1])
            result,_=h.reconcile(self.output,self.config,self.plan,sources,artifacts)
            self.assertFalse(result['evidence_complete'])
            target.write_bytes(original+original.split(b'\n')[0]+b'\n')
            result,_=h.reconcile(self.output,self.config,self.plan,sources,artifacts)
            self.assertFalse(result['evidence_complete'])
        finally: target.write_bytes(original)

    def test_schema_rejects_secret_fields(self):
        row=deepcopy(self.rows[0]); row['credential4']='SECRET_SENTINEL_DO_NOT_EXPORT'
        self.assertFalse(h.schema_validator('attempt').is_valid(row))
        row=deepcopy(self.rows[0]); row['state_after']['sessions'][0]['session_key']='SECRET_SENTINEL_DO_NOT_EXPORT'
        self.assertFalse(h.schema_validator('attempt').is_valid(row))


class ObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.materials=h.Materials()

    def fixture(self,group='control'):
        s=deepcopy(next(s for s in h.compact_nonformal_plan(h.nonformal_config())['scenarios'] if s['group']==group and s['phase']=='measured'))
        return h.Scenario(self.materials,s,(lambda r:(r,r),lambda x:None,lambda x:None),lambda d,i,p:h.nonformal_record(i,d))

    def test_pending_observer_keys_only(self):
        f=self.fixture('P27'); f.prepare_handshake('nonformal-pending')
        ids=h.pending_session_ids(f.verifier)
        self.assertEqual(len(ids),1); self.assertIs(type(ids[0]),bytes); self.assertEqual(len(ids[0]),16)
        self.assertEqual(ids,h.pending_session_ids(f.verifier))
        f.finish_handshake(); self.assertEqual(h.pending_session_ids(f.verifier),())

    def test_expiry_restores_on_exception(self):
        from puf_snn.auth import verifier as module
        original=module.time
        with self.assertRaisesRegex(RuntimeError,'test'):
            with h.expiry_clock(original.monotonic_ns()+100000,'expiry_equality'):
                self.assertIs(module.time.perf_counter_ns,original.perf_counter_ns)
                raise RuntimeError('test')
        self.assertIs(module.time,original)

    def test_wrappers_identity_arguments_returns_exceptions(self):
        from puf_snn.pipeline_timing import TimingCapture,instrument_pipeline
        from puf_snn.auth.verifier import Verifier
        f=self.fixture(); f.establish('source','nonformal-wrapper')
        capture=TimingCapture(); verify=Verifier.verify_window; release=Verifier.release_accepted
        prepare=f.pipeline._prepare; motion=f.pipeline._motion
        packet=f.seal('source',0,0)
        with instrument_pipeline(capture),h.observe_pipeline(f.pipeline,capture) as (entries,observations):
            result=capture.measure('receiver_path',lambda:f.pipeline.process_envelope(packet))
            self.assertEqual(result.decision,'accept'); self.assertEqual(len(observations),1)
            self.assertEqual(entries,dict(release=1,preprocessing=1,motion=1,anomaly=1))
            f.pipeline.process_envelope(packet)
            self.assertEqual(len(observations),2); self.assertEqual(entries['release'],1)
        self.assertIs(Verifier.verify_window,verify); self.assertIs(Verifier.release_accepted,release)
        self.assertIs(f.pipeline._prepare,prepare); self.assertIs(f.pipeline._motion,motion)
        with self.assertRaises(RuntimeError):
            with instrument_pipeline(capture),h.observe_pipeline(f.pipeline,capture): raise RuntimeError('test')
        self.assertIs(Verifier.verify_window,verify); self.assertIs(f.pipeline._prepare,prepare)

    def test_mutation_api_has_no_secret_inputs(self):
        signature=inspect.signature(h.mutate_public)
        self.assertEqual(set(signature.parameters),{'packet','group','variant','sample_index','component','bit','tag_bit','cut','selector','target_device','target_sid'})
        with self.assertRaises(TypeError): h.mutate_public(b'{}','A4','position',credential=b'SENT')
        self.assertNotIn('__dict__',inspect.getsource(h.mutate_public))

    def test_exact_stale_tag_payload_and_metadata_mutations(self):
        f=self.fixture(); f.establish('source','nonformal-mutations')
        packet=f.seal('source',0,0); env,a,offsets=h.wire_parts(packet)
        changed,record=h.mutate_public(packet,'A4','quaternion',sample_index=119,component=6,bit=22)
        altered,b,_=h.wire_parts(changed)
        self.assertEqual(sum((x^y).bit_count() for x,y in zip(a,b)),1)
        self.assertEqual(altered['authentication'],env['authentication'])
        self.assertEqual(record['byte_offset'],offsets['samples'][0]+119*39+10+6*4)
        for field in h.VARIANTS['A5']:
            changed,record=h.mutate_public(packet,'A5',field)
            altered,b,_=h.wire_parts(changed)
            off,width=offsets[field]
            self.assertEqual(a[:off],b[:off]); self.assertEqual(a[off+width:],b[off+width:])
            self.assertNotEqual(a[off:off+width],b[off:off+width])
            self.assertEqual(altered['authentication']['tag_hex'],env['authentication']['tag_hex'])

    def test_handshake_negatives_preserve_pending_and_kdf(self):
        from puf_snn.auth.session import REFUSAL
        for group in ['P25','P26','P27','P28']:
            with self.subTest(group=group):
                f=self.fixture(group); f.prepare_handshake('nonformal-'+group)
                before=h.pending_session_ids(f.verifier); count=len(f.verifier.kdf_timings_ns)
                source=f.request if group in {'P25','P26'} else f.confirmation
                changed,_=h.mutate_handshake(source,group,16)
                result=f.verifier.begin_session(changed,admission=f.senders['source'].admission) if group in {'P25','P26'} else f.verifier.confirm_session(changed)
                self.assertEqual(result,REFUSAL); self.assertEqual(f.verifier.last_reason,'malformed_message')
                self.assertEqual(h.pending_session_ids(f.verifier),before); self.assertEqual(len(f.verifier.kdf_timings_ns),count)
                f.finish_handshake(); self.assertEqual(f.senders['source'].state,'ACTIVE')

    def test_callback_failure_preserved_sanitized_not_retried(self):
        secret='SECRET_SENTINEL_credential_candidate_helper_key_handle'
        calls=[]
        def failing(value): calls.append(1); raise RuntimeError(secret)
        config=h.nonformal_config('nonformal-failure')
        plan=h.compact_nonformal_plan(config)
        plan['scenarios']=[next(s for s in plan['scenarios'] if s['group']=='A4')]
        for i,op in enumerate(plan['scenarios'][0]['operations']): op['execution_index']=i
        del plan['plan_sha256']; plan['plan_sha256']=h.digest(plan)
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)/'failure'
            rec,summary=h.run_nonformal(output,callbacks=(lambda r:(r,r),failing,lambda x:secret),config=config,plan=plan)
            self.assertFalse(rec['evidence_complete']); self.assertEqual(len(calls),1)
            rows=[r for name in h.ATTEMPT_FILES for r in h.read_rows(output/(name+'.jsonl'))]
            failed=[r for r in rows if r['execution_status']=='execution_failure']
            self.assertEqual(len(failed),1)
            self.assertEqual(failed[0]['observed']['result'],'accept')
            self.assertEqual(failed[0]['calls_delta'],dict(release=1,preprocessing=1,motion=1,anomaly=0))
            self.assertTrue(any(r['execution_status']=='not_submitted' for r in rows))
            for path in output.iterdir():
                if path.is_file(): self.assertNotIn(secret.encode(),path.read_bytes())

    def test_unexpected_acceptance_complete_evidence_failed_behavior(self):
        config=h.nonformal_config('nonformal-unexpected')
        plan=h.compact_nonformal_plan(config)
        plan['scenarios']=[next(s for s in plan['scenarios'] if s['group']=='A4')]
        for i,op in enumerate(plan['scenarios'][0]['operations']): op['execution_index']=i
        del plan['plan_sha256']; plan['plan_sha256']=h.digest(plan)
        # Deliberate harness test substitution, never a formal attack or protocol change.
        with tempfile.TemporaryDirectory() as temporary,patch.object(h,'mutate_public',side_effect=lambda packet,*a,**kw:(packet,h.mutation_record('test',None,'retain'))):
            rec,summary=h.run_nonformal(Path(temporary)/'unexpected',config=config,plan=plan)
            self.assertTrue(rec['evidence_complete'],rec['checks'])
            self.assertFalse(rec['expected_behavior_observed'])
            primary=next(r for r in summary['counts'] if r['role']=='primary_attack' and r['variant'] is None)
            self.assertEqual((primary['A'],primary['R'],primary['F'],primary['U']),(1,0,0,0))
            self.assertEqual(summary['recovery'][0]['rejected'],1)

    def test_provisioning_and_callback_secret_sentinels_not_exported(self):
        import base64
        native=h.secrets.token_bytes
        made=[]
        def token_bytes(n):
            if n==4 and not made:
                made.append(b'Q7!z'); return made[0]
            return native(n)
        with patch.object(h.secrets,'token_bytes',side_effect=token_bytes): materials=h.Materials()
        sentinel='SECRET_SENTINEL_ARBITRARY_MODEL_OBJECT_LOCALS'
        class SecretObject:
            def __init__(self): self.credential4=sentinel
        config=h.nonformal_config('nonformal-secrets'); plan=h.compact_nonformal_plan(config)
        plan['scenarios']=[next(s for s in plan['scenarios'] if s['group']=='control')]
        for i,op in enumerate(plan['scenarios'][0]['operations']): op['execution_index']=i
        del plan['plan_sha256']; plan['plan_sha256']=h.digest(plan)
        with tempfile.TemporaryDirectory() as temporary,patch.object(h,'Materials',return_value=materials):
            output=Path(temporary)/'secrets'
            rec,_=h.run_nonformal(output,config=config,plan=plan,callbacks=(lambda r:(r,r),lambda r:SecretObject(),lambda r:SecretObject()))
            self.assertTrue(rec['evidence_complete'])
            for path in output.iterdir():
                for forbidden in [sentinel.encode(),made[0],made[0].hex().encode(),base64.b64encode(made[0])]:
                    self.assertNotIn(forbidden,path.read_bytes())

    def test_evidence_io_failure_keeps_incomplete(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as temporary:
            writer=h.EvidenceWriter(Path(temporary)/'io',h.nonformal_config(),h.compact_nonformal_plan(h.nonformal_config()),nonformal=True)
            original=writer.handles['traffic']; writer.handles['traffic']=Mock()
            writer.handles['traffic'].write.side_effect=OSError('SECRET_ERROR_MESSAGE')
            try:
                with self.assertRaises(OSError): writer.traffic(b'public','endpoints')
                self.assertTrue(writer.failed)
                with self.assertRaises(RuntimeError): writer.traffic(b'public-again','endpoints')
                self.assertTrue((writer.path/'INCOMPLETE').exists()); self.assertFalse((writer.path/'COMPLETE').exists())
            finally: original.close(); writer.close()


if __name__=='__main__': unittest.main()
