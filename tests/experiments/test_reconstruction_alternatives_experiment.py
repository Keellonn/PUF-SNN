"""Accounting tests use deterministic noiseless fixtures, never formal trials."""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/python'))
from scripts import run_reconstruction_alternatives as e
from puf_snn.reconstruction import ReconstructionResult
from puf_snn.auth.credential_verifier import CredentialAdmissionService,CredentialVerifierStore


class ExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=e.load_config()
        cls.plan=e.compile_plan(cls.config,'smoke')
        cls.runtime,cls.truth=e.provision(cls.plan)
        cls.rows=[]
        for trial in cls.plan['schedule']:
            material,truth=cls.material(trial)
            row=e.new_record(trial,cls.plan,'a'*64)
            with patch.object(e,'generate_response',return_value=tuple(map(int,truth['reference64']))):
                e.measured_attempt(trial,material,row)
            cls.rows.append(e.score(row,truth))

    @classmethod
    def material(cls,trial):
        key=(trial['population_seed'],trial['device_index'],'B1' if trial['group']=='B1' else 'baseline')
        return cls.runtime[key],cls.truth[key]

    def test_frozen_formal_schedule_and_digest(self):
        p=e.compile_plan(self.config,'compile')
        self.assertEqual(p['trial_plan_sha256'],'d22e5eebe6ec55c9f890e02b4f010833e4f32ff9d64b5c777b22e9f794a26f10')
        self.assertEqual((p['expected_attempts'],p['expected_read_calls'],p['expected_unique_readings']),(48000,120000,60000))
        counts=Counter((t['condition'],t['group']) for t in p['schedule'])
        self.assertEqual(set(counts.values()),{6000})
        self.assertEqual(set(Counter((t['group'],t['slot']) for t in p['schedule']).values()),{3000})
        self.assertEqual(len({(t['population_seed'],t['device_index']) for t in p['schedule']}),120)
        self.assertEqual({t['population_seed'] for t in p['schedule']},set(range(2026100701,2026100721)))
        self.assertEqual(e.compile_plan(self.config,'compile'),p)

    def test_fixed_stream_derivation_and_namespace(self):
        label='w6ra-v1:read:2026100701:0:0:nominal:0:0'
        from random import Random
        self.assertEqual(e.rng(label).getrandbits(128),Random(int.from_bytes(hashlib.sha256(label.encode('ascii')).digest(),'big')).getrandbits(128))
        self.assertTrue(all(t['read_labels'][0].startswith('w6ra-smoke-v1:') for t in self.plan['schedule']))
        for block in e.group_rows(self.plan['schedule'],('block_id',)).values():
            indexed={t['group']:t for t in block}
            for g in e.GROUPS:
                self.assertEqual(indexed[g]['read_labels'],indexed['A2']['read_labels'][:e.READS[g]])
            self.assertEqual(len(set(indexed['A2']['read_labels'])),5)

    def test_configuration_changes_rejected(self):
        config=deepcopy(self.config);config['conditions']['nominal']=.05
        with self.assertRaises(ValueError):e.compile_plan(config,'smoke')
        with self.assertRaises(ValueError):e.compile_plan(self.config,'formal')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'config.json';path.write_text(json.dumps(config))
            with self.assertRaises(ValueError):e.load_config(path)

    def test_formal_fail_closed_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'formal'
            with self.assertRaises(SystemExit),patch.object(e,'provision') as provision:
                e.main(['formal','--output',str(out)])
            provision.assert_not_called()
            self.assertFalse(out.exists())

    def test_output_isolation_and_exclusive_creation(self):
        with self.assertRaises(ValueError):e.safe_output(ROOT/'results'/'prohibited-smoke')
        with self.assertRaises(ValueError):e.safe_output(ROOT/'tmp'/'..'/'results'/'prohibited-smoke')
        with self.assertRaises(ValueError):e.safe_output(ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):e.safe_output(tmp)

    def test_exact_read_calls_and_independent_rngs(self):
        for group in e.GROUPS:
            trial=next(t for t in self.plan['schedule'] if t['group']==group)
            material,truth=self.material(trial)
            randoms=[]
            def reading(*args,**kwargs):
                randoms.append(kwargs['rng'])
                return tuple(map(int,truth['reference64']))
            with patch.object(e,'generate_response',side_effect=reading) as reads:
                e.measured_attempt(trial,material,{})
            self.assertEqual(reads.call_count,e.READS[group])
            self.assertEqual(len({id(r) for r in randoms}),e.READS[group])
            self.assertEqual([r.getstate() for r in randoms],[e.rng(s).getstate() for s in trial['read_labels']])

    def test_production_api_for_baseline_groups(self):
        for group in ('B0','A1','A2'):
            trial=next(t for t in self.plan['schedule'] if t['group']==group)
            material,truth=self.material(trial)
            with patch.object(e,'generate_response',return_value=tuple(map(int,truth['reference64']))),patch.object(e,'reconstruct',wraps=e.reconstruct) as baseline,patch.object(e.alt,'reconstruct',wraps=e.alt.reconstruct) as alternative:
                e.measured_attempt(trial,material,{})
            baseline.assert_called_once();alternative.assert_not_called()

    def test_enrollment_truth_separate_and_counts(self):
        self.assertEqual(len(self.truth),4)
        for material in self.runtime.values():
            self.assertFalse(hasattr(material,'credential'))
            self.assertFalse(hasattr(material,'reference'))
            self.assertFalse(hasattr(material.helper,'credential'))
        for row in self.rows:
            key=(row['population_seed'],row['device_index'],'B1' if row['group']=='B1' else 'baseline')
            self.assertEqual(row['binding'],self.truth[key]['binding'])

    def test_reconciliation_and_timing_accounting(self):
        result=e.reconcile(self.rows,self.plan,self.truth)
        self.assertEqual((result['attempt_count'],result['read_calls'],result['verifier_calls']),(80,200,80))
        self.assertEqual(result['unique_readings'],100)
        self.assertEqual(set(result['cell_counts'].values()),{10})
        for row in self.rows:
            self.assertGreaterEqual(row['total_ns'],sum(row[k] for k in ['read_ns','vote_ns','reconstruction_ns','verification_ns']))
            self.assertEqual(row['verification_ns']>0,row['verifier_invoked'])

    def test_schema_and_tamper_rejection(self):
        for field,value in [('extra',1),('read_count',9),('raw_ber_numerator',99),('total_ns',0),
                            ('candidate_credential_hex','ffffffff'),('effective_response64','1'*64),('mode','FORMAL')]:
            rows=deepcopy(self.rows);rows[0][field]=value
            with self.subTest(field=field),self.assertRaises(Exception):e.reconcile(rows,self.plan,self.truth)
        with self.assertRaises(ValueError):e.reconcile(self.rows[:-1],self.plan,self.truth)
        rows=deepcopy(self.rows);rows[1]=rows[0]
        with self.assertRaises(ValueError):e.reconcile(rows,self.plan,self.truth)

    def test_failure_wrong_candidate_and_verifier_semantics(self):
        trial=next(t for t in self.plan['schedule'] if t['group']=='B0')
        material,truth=self.material(trial)
        wrong=(int(truth['credential_hex'],16)^1).to_bytes(4,'big')
        wrong_message=tuple(map(int,f'{int.from_bytes(wrong,"big"):032b}'))+(0,)*4
        fixtures=[ReconstructionResult('decoder_failure','uncorrectable',-1,None,None,None,'decoder_declared_failure'),
                  ReconstructionResult('invalid_format_or_padding','decoded',5,(0,)*35+(1,),None,False,'nonzero_padding'),
                  ReconstructionResult('candidate_valid_format','decoded',5,wrong_message,wrong,True,None)]
        for expected,result in zip('DIW',fixtures):
            with patch.object(e,'generate_response',return_value=tuple(map(int,truth['reference64']))),patch.object(e,'reconstruct',return_value=result),patch.object(CredentialAdmissionService,'verify',autospec=True,side_effect=CredentialAdmissionService.verify) as verify:
                row=e.score(e.measured_attempt(trial,material,{}),truth)
            self.assertEqual(row['outcome'],expected)
            self.assertFalse(row['legitimate_admitted'])
            self.assertEqual(verify.call_count,int(expected=='W'))
            report=e.summarize([dict(row,read_count=1)])
            self.assertEqual(report['frr']['rate'],1)
            self.assertEqual(report['legitimate_admission_failure']['rate'],1)
            if expected=='W':self.assertEqual(row['verifier_outcome'],'credential_mismatch')

    def test_missing_verifier_record_is_not_success(self):
        trial=self.plan['schedule'][0];material,truth=self.material(trial)
        # Real verification with a missing trusted record, preserving independent key source.
        missing=replace(material,service=CredentialAdmissionService(CredentialVerifierStore(),e.InMemoryCredentialVerifierKeyProvider.generate('missing')))
        with patch.object(e,'generate_response',return_value=tuple(map(int,truth['reference64']))):
            row=e.score(e.measured_attempt(trial,missing,{}),truth)
        self.assertEqual(row['outcome'],'C');self.assertEqual(row['verifier_outcome'],'record_missing')
        self.assertFalse(row['legitimate_admitted'])

    def test_summary_intervals_and_paired_counts(self):
        summary=e.summarize(self.rows)
        self.assertEqual(summary['correct'],80)
        self.assertEqual(summary['frr']['ci_low'],0)
        self.assertAlmostEqual(summary['frr']['ci_high'],1-.025**(1/80))
        self.assertIsNone(summary['wrong_candidate_catch']['rate'])
        self.assertEqual(summary['raw_ber']['denominator'],12600)
        self.assertEqual(summary['effective_ber']['denominator'],5040)
        self.assertEqual(len(e.paired(self.rows)),6)
        self.assertTrue(all(r['paired_blocks']==10 for r in e.paired(self.rows)))
        self.assertEqual(e.cluster_intervals(self.rows,self.config)['status'],'not_estimable_single_smoke_population')

    def test_cluster_bootstrap_keeps_paired_populations(self):
        rows=deepcopy(self.rows)
        second=deepcopy(self.rows)
        for row in second:
            row['population_seed']+=1
            row['outcome']='W'
            row['verifier_outcome']='credential_mismatch'
            row['legitimate_admitted']=False
        result=e.cluster_intervals(rows+second,self.config)
        self.assertEqual(result['resamples'],10000)
        for interval in result['intervals']:
            if interval['metric']=='frr':self.assertEqual(interval['ci'],[0.0,1.0])
            if interval['metric'].endswith('-minus-B0'):self.assertEqual(interval['ci'],[0.0,0.0])

    def test_source_change_prevents_nonformal_seal(self):
        real_generate=e.generate_response
        def noiseless(device,pairs,frequency,conditions,*,rng):
            return real_generate(device,pairs,frequency,e.ReadConditions(0.0,0.0),rng=rng)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'changed'
            with patch.object(e,'warm_up',return_value={'test_fixture':True}),patch.object(e,'generate_response',side_effect=noiseless),patch.object(e,'source_hashes',side_effect=[{'a':'a'},{'a':'b'}]):
                with self.assertRaisesRegex(ValueError,'source changed'):e.run_smoke(out)
            self.assertTrue((out/'INCOMPLETE.json').exists())
            self.assertFalse((out/'NONFORMAL_VALIDATED.json').exists())
            self.assertEqual(len((out/'attempts.jsonl').read_text().splitlines()),80)

    def test_interrupted_execution_retains_one_error_no_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'interrupted'
            with patch.object(e,'warm_up',return_value={'test_fixture':True}),patch.object(e,'generate_response',side_effect=RuntimeError('secret-must-not-be-logged')):
                # Provisioning also calls generate_response; patch provision to isolate attempt failure.
                with patch.object(e,'provision',return_value=(self.runtime,self.truth)):
                    with self.assertRaises(RuntimeError):e.run_smoke(out)
            rows=[json.loads(s) for s in (out/'attempts.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['execution_error'],'RuntimeError')
            e.validator().validate(rows[0])
            self.assertTrue((out/'INCOMPLETE.json').exists())
            self.assertFalse((out/'NONFORMAL_VALIDATED.json').exists())
            self.assertFalse((out/'COMPLETE').exists())
            self.assertNotIn('secret-must-not-be-logged',''.join(p.read_text() for p in out.iterdir() if p.is_file()))

    def test_fixture_evidence_roundtrip_manifest_and_nonformal_only(self):
        real_generate=e.generate_response
        def noiseless(device,pairs,frequency,conditions,*,rng):
            return real_generate(device,pairs,frequency,e.ReadConditions(0.0,0.0),rng=rng)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'fixture'
            with patch.object(e,'warm_up',return_value={'test_fixture':True}),patch.object(e,'generate_response',side_effect=noiseless):
                result=e.run_smoke(out)
            self.assertEqual(result['reconciliation']['attempt_count'],80)
            self.assertFalse((out/'COMPLETE').exists())
            self.assertTrue((out/'NONFORMAL_VALIDATED.json').exists())
            self.assertEqual(e.digest(out/'config.json'),e.CONFIG_SHA256)
            manifest=json.loads((out/'manifest.json').read_text())
            self.assertTrue(all(e.digest(out/k)==v for k,v in manifest.items()))
            rows=[json.loads(line) for line in (out/'attempts.jsonl').read_text().splitlines()]
            self.assertEqual([r['candidate_credential_hex'] for r in rows],[r['candidate_credential_hex'] for r in self.rows])
            self.assertTrue(all(r['mode']=='NONFORMAL' for r in rows))


if __name__=='__main__':unittest.main()