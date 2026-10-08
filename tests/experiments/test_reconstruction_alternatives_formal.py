"""Formal readiness safety tests. No formal measurements; fixtures/mocks only."""
from copy import deepcopy
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import run_reconstruction_alternatives as e


class FormalReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=e.load_config()
        cls.plan=e.compile_plan(cls.config,'compile')
        cls.smoke_plan=e.compile_plan(cls.config,'smoke')
        cls.saved_rows=[json.loads(line) for line in (e.SMOKE_DIRECTORY/'attempts.jsonl').read_text().splitlines()]

    def tearDown(self):
        self.assertFalse((e.ROOT/e.FORMAL_RELATIVE).exists(),'Test must never create actual formal directory')

    def test_exact_compiled_counts_and_unchanged_digests(self):
        counts=e.validate_formal_plan(self.plan)
        self.assertEqual(counts['attempts'],48000)
        self.assertEqual(counts['devices'],120)
        self.assertEqual(counts['enrollments'],240)
        self.assertEqual(counts['read_calls'],120000)
        self.assertEqual(counts['unique_readings'],60000)
        self.assertEqual(e.digest(e.ROOT/self.config['plan_path']),e.PLAN_SHA256)
        self.assertEqual(e.digest(e.CONFIG_PATH),e.CONFIG_SHA256)

    def test_reduced_population_and_rehashed_schedule_rejected(self):
        with self.assertRaises(ValueError):e.validate_formal_plan(self.smoke_plan)
        changed=deepcopy(self.plan);changed['schedule']=changed['schedule'][:4]
        with self.assertRaises(ValueError):e.validate_formal_plan(changed)
        changed['trial_plan_sha256']=e.object_digest({k:v for k,v in changed.items() if k!='trial_plan_sha256'})
        with self.assertRaises(ValueError):e.validate_formal_plan(changed)

    def test_seed_order_and_parameter_changes_rejected(self):
        for field,value in [('expected_attempts',80),('prefix','w6ra-smoke-v1'),('mode','FORMAL')]:
            changed=dict(self.plan);changed[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):e.validate_formal_plan(changed)
        changed=deepcopy(self.plan);changed['schedule'][0]['read_labels'][0]+=':altered'
        with self.assertRaises(ValueError):e.validate_formal_plan(changed)

    def test_formal_record_schema_acceptance_and_mode_separation(self):
        row=deepcopy(self.saved_rows[0]);trial=self.plan['schedule'][0]
        row.update(trial)
        row.update(e.new_record(trial,self.plan,'a'*64))
        e.validator().validate(row)
        self.assertEqual(row['mode'],'FORMAL')
        for key,value in [('population_seed',1),('device_index',6),('attempt',50),
                          ('trial_plan_sha256','a'*64),('read_labels',['w6ra-smoke-v1:read:1']),('extra',1)]:
            bad=dict(row);bad[key]=value
            with self.subTest(key=key),self.assertRaises(Exception):e.validator().validate(bad)
        e.validator().validate(self.saved_rows[0])
        mislabeled=deepcopy(self.saved_rows[0]);mislabeled['mode']='FORMAL'
        with self.assertRaises(Exception):e.validator().validate(mislabeled)

    def test_nonformal_schedule_cannot_reconcile_formal_record(self):
        rows=deepcopy(self.saved_rows);rows[0]['mode']='FORMAL'
        entries=json.loads((e.SMOKE_DIRECTORY/'enrollments.json').read_text())
        truth={(r['population_seed'],r['device_index'],r['code']):r for r in entries}
        with self.assertRaises(Exception):e.reconcile(rows,self.smoke_plan,truth)

    def test_output_path_existing_and_historical_refused(self):
        for path in (e.ROOT/'results/week-5',e.ROOT/'tmp/not-formal',e.ROOT/e.FORMAL_RELATIVE/'child'):
            with self.assertRaises(ValueError):e.formal_output(path)
        with patch.object(Path,'exists',return_value=True):
            with self.assertRaisesRegex(ValueError,'already exists'):e.formal_output(e.ROOT/e.FORMAL_RELATIVE)
        self.assertEqual(e.formal_output(e.ROOT/e.FORMAL_RELATIVE),e.ROOT/e.FORMAL_RELATIVE)

    def test_dummy_runtime_callback_rejected(self):
        with patch.object(e.CredentialAdmissionService,'verify',return_value=True):
            with self.assertRaisesRegex(ValueError,'Dummy'):e.assert_real_runtime()
        with patch.object(e,'generate_response',return_value=(0,)*64):
            with self.assertRaises(ValueError):e.assert_real_runtime()
        e.assert_real_runtime()

    def test_missing_packages_and_wrong_code_parameters_rejected(self):
        with patch.object(e.importlib.metadata,'version',side_effect=e.importlib.metadata.PackageNotFoundError):
            with self.assertRaises(e.importlib.metadata.PackageNotFoundError):e.verify_packages()
        with patch.object(e.BCHCodec,'t',6),patch.object(e,'verify_prior_validation',return_value={'status':'PASS'}):
            with self.assertRaisesRegex(ValueError,'Code parameters'):e.formal_preflight(e.ROOT/e.FORMAL_RELATIVE)

    def test_missing_source_dependency_rejected(self):
        with patch.object(e,'source_dependencies',return_value=('src/missing-required-file.py',)):
            with self.assertRaisesRegex(ValueError,'Missing'):e.source_hashes()

    def test_snapshot_exact_bytes_allowlist_and_tamper_rejection(self):
        hashes=e.source_hashes()
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'source'
            e.create_source_snapshot(directory,hashes,{'status':'TEST_FIXTURE'})
            self.assertEqual(e.verify_source_snapshot(directory,hashes),e.digest(directory/'manifest.json'))
            for path in hashes:
                self.assertEqual((directory/'files'/path).read_bytes(),(e.ROOT/path).read_bytes())
                self.assertNotIn('.venv',path)
                self.assertFalse(path.startswith('results/'))
            with self.assertRaises(FileExistsError):e.create_source_snapshot(directory,hashes,{})
            copied=directory/'files'/next(iter(hashes));copied.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'snapshot hash'):e.verify_source_snapshot(directory,hashes)

    def test_snapshot_manifest_extra_files_and_source_change_rejected(self):
        hashes=e.source_hashes()
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'source'
            e.create_source_snapshot(directory,hashes,{})
            (directory/'unapproved-secret.txt').write_text('synthetic-only')
            with self.assertRaisesRegex(ValueError,'Unexpected'):e.verify_source_snapshot(directory,hashes)
        changed=dict(hashes);changed[next(iter(changed))]='0'*64
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'Source changed'):e.create_source_snapshot(Path(tmp)/'source',changed,{})

    def test_readonly_preflight_never_enters_measurement_or_provisioning(self):
        with patch.object(e,'verify_prior_validation',return_value={'status':'TEST_FIXTURE'}),patch.object(e,'provision',side_effect=AssertionError('Forbidden enrollment')) as provision,patch.object(e,'measured_attempt',side_effect=AssertionError('Forbidden measurement')) as attempt,patch.object(e,'warm_up',side_effect=AssertionError('Forbidden warmup')) as warm:
            result=e.formal_preflight(e.ROOT/e.FORMAL_RELATIVE)
        self.assertEqual(result['executed_attempts'],0)
        self.assertFalse(result['output_exists'])
        provision.assert_not_called();attempt.assert_not_called();warm.assert_not_called()

    def test_readonly_preflight_checks_optional_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'source';hashes=e.source_hashes()
            e.create_source_snapshot(directory,hashes,{})
            copied=directory/'files'/next(iter(hashes));copied.write_bytes(b'bad')
            with patch.object(e,'verify_prior_validation',return_value={'status':'TEST_FIXTURE'}):
                with self.assertRaisesRegex(ValueError,'snapshot hash'):e.formal_preflight(e.ROOT/e.FORMAL_RELATIVE,directory)

    def test_cli_dispatch_without_running_formal(self):
        with patch.object(e,'run_formal',return_value={'reconciliation':{'status':'MOCK_ONLY'},'runtime':{}}) as run,redirect_stdout(io.StringIO()):
            e.main(['formal','--output',str(e.ROOT/e.FORMAL_RELATIVE)])
        run.assert_called_once_with(e.ROOT/e.FORMAL_RELATIVE)
        with patch.object(e,'formal_preflight',return_value={'status':'MOCK_ONLY'}) as preflight,patch.object(e,'run_formal',side_effect=AssertionError('No formal execution')) as run,redirect_stdout(io.StringIO()):
            e.main(['preflight','--output',str(e.ROOT/e.FORMAL_RELATIVE)])
        preflight.assert_called_once();run.assert_not_called()

    def test_prerequisites_missing_failed_stale_and_log_hash_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'validation.json'
            with patch.object(e,'VALIDATION_PATH',path):
                with self.assertRaises(FileNotFoundError):e.verify_prior_validation()
                path.write_text(json.dumps({'status':'FAIL','mode':'TESTS_ONLY','source_sha256':e.source_hashes()}))
                with self.assertRaises(ValueError):e.verify_prior_validation()
                path.write_text(json.dumps({'status':'PASS','mode':'TESTS_ONLY','source_sha256':{}}))
                with self.assertRaises(ValueError):e.verify_prior_validation()
                path.write_text(json.dumps({'status':'PASS','mode':'TESTS_ONLY','source_sha256':e.source_hashes(),'suites':{}}))
                with self.assertRaisesRegex(ValueError,'Missing required'):e.verify_prior_validation()

    def test_failed_smoke_prerequisite_refused(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(e,'SMOKE_DIRECTORY',Path(tmp)):
            with self.assertRaises(FileNotFoundError):e.verify_prior_validation()

    def test_formal_interruption_creates_incomplete_before_any_measurement(self):
        hashes=e.source_hashes()
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'formal-fixture-only'
            with patch.object(e,'formal_preflight',return_value={'source_sha256':hashes,'prerequisites':{'status':'TEST_FIXTURE'}}),patch.object(e,'formal_output',return_value=directory),patch.object(e,'warm_up',side_effect=KeyboardInterrupt),patch.object(e,'measured_attempt',side_effect=AssertionError('No measurements')) as attempt:
                with self.assertRaises(KeyboardInterrupt):e.run_formal(directory)
            attempt.assert_not_called()
            incomplete=json.loads((directory/'INCOMPLETE.json').read_text())
            self.assertEqual(incomplete['mode'],'FORMAL')
            self.assertEqual(incomplete['completed_attempts'],0)
            self.assertFalse((directory/'COMPLETE').exists())
            self.assertTrue((directory/'source_snapshot/manifest.json').exists())

    def test_formal_first_attempt_error_retained_without_retry(self):
        # Use one real synthetic enrollment as fixture; enrollment population gate
        # is mocked independently, and measurement MUST throw on its first call.
        fixture_runtime,fixture_truth=e.provision(self.smoke_plan)
        trial=self.plan['schedule'][0]
        code='B1' if trial['group']=='B1' else 'baseline'
        key=(trial['population_seed'],trial['device_index'],code)
        material=next(m for k,m in fixture_runtime.items() if k[2]==code)
        hashes=e.source_hashes()
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'first-error-fixture'
            with patch.object(e,'formal_preflight',return_value={'source_sha256':hashes,'prerequisites':{'status':'TEST_FIXTURE'}}),patch.object(e,'formal_output',return_value=directory),patch.object(e,'warm_up',return_value={'mode':'TEST_FIXTURE'}),patch.object(e,'provision',return_value=({key:material},fixture_truth)),patch.object(e,'validate_enrollments'),patch.object(e,'measured_attempt',side_effect=RuntimeError('synthetic failure')) as attempt:
                with self.assertRaises(RuntimeError):e.run_formal(directory)
            self.assertEqual(attempt.call_count,1)
            rows=[json.loads(line) for line in (directory/'attempts.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['mode'],'FORMAL')
            self.assertEqual(rows[0]['execution_error'],'RuntimeError')
            e.validator().validate(rows[0])
            self.assertTrue((directory/'INCOMPLETE.json').exists())
            self.assertFalse((directory/'COMPLETE').exists())

    def test_loaded_source_change_rejected_before_output(self):
        changed=dict(e.source_hashes())
        changed['src/python/scripts/run_reconstruction_alternatives.py']='0'*64
        with patch.object(e,'source_hashes',return_value=changed):
            with self.assertRaisesRegex(ValueError,'since import'):e.formal_preflight(e.ROOT/e.FORMAL_RELATIVE)

    def test_invalid_credential_representation_rejected_in_preflight(self):
        with patch.object(e.alt,'credential_to_message',side_effect=ValueError('Invalid credential format')):
            with self.assertRaisesRegex(ValueError,'credential format'):e.formal_preflight(e.ROOT/e.FORMAL_RELATIVE)

    def test_failed_preflight_creates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'never-created'
            with patch.object(e,'formal_preflight',side_effect=ValueError('fixture rejection')),patch.object(e,'provision') as provision:
                with self.assertRaises(ValueError):e.run_formal(directory)
            provision.assert_not_called();self.assertFalse(directory.exists())

    def test_reduced_evidence_never_reaches_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            e.write_json(directory/'trial_plan.json',self.plan)
            (directory/'config.json').write_bytes(e.CONFIG_PATH.read_bytes())
            (directory/'attempts.jsonl').write_text('\n'.join(json.dumps(r) for r in self.saved_rows)+'\n')
            with self.assertRaisesRegex(ValueError,'Reduced/nonformal'):e.seal_formal(directory,e.source_hashes())
            self.assertFalse((directory/'COMPLETE').exists())

    def test_seal_binds_snapshot_manifest_with_mocked_audit_receipt(self):
        # Exercise only seal mechanics. Full-population audit is mocked, never bypassed by production options.
        hashes=e.source_hashes()
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            e.create_source_snapshot(directory/'source_snapshot',hashes,{'status':'TEST_FIXTURE'})
            receipt=dict(mode='FORMAL',status='PASS',attempt_count=48000,
                         source_snapshot_manifest_sha256=e.digest(directory/'source_snapshot/manifest.json'))
            with patch.object(e,'audit_formal_evidence',return_value=receipt):e.seal_formal(directory,hashes)
            marker=json.loads((directory/'COMPLETE').read_text())
            manifest=json.loads((directory/'manifest.json').read_text())
            self.assertEqual(marker['manifest_sha256'],e.digest(directory/'manifest.json'))
            self.assertEqual(manifest['source_snapshot/manifest.json'],marker['source_snapshot_manifest_sha256'])
            self.assertTrue(all(e.digest(directory/name)==h for name,h in manifest.items()))
            with patch.object(e,'audit_formal_evidence',return_value=receipt):
                with self.assertRaises(ValueError):e.seal_formal(directory,hashes)

    def test_incomplete_or_changed_source_prevents_seal(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);e.write_json(directory/'INCOMPLETE.json',{})
            with self.assertRaisesRegex(ValueError,'Incomplete'):e.seal_formal(directory,e.source_hashes())
            self.assertFalse((directory/'COMPLETE').exists())
        hashes=e.source_hashes();changed=dict(hashes);changed[next(iter(changed))]='0'*64
        with tempfile.TemporaryDirectory() as tmp,patch.object(e,'source_hashes',return_value=changed):
            with self.assertRaisesRegex(ValueError,'source changed'):e.audit_formal_evidence(Path(tmp),hashes)

    def test_csv_all_fields_and_latency_readback(self):
        rows=[{'n':1,'nested':{'failure':0},'missing':None,'duration':1.5}]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'fixture.csv';e.write_csv(path,rows);e.verify_csv(path,rows)
            path.write_text(path.read_text().replace('1.5','2.5'))
            with self.assertRaisesRegex(ValueError,'CSV readback'):e.verify_csv(path,rows)
        timing=e.latency_rows(self.saved_rows)
        self.assertEqual(len(timing),8*8*6)

    def test_independent_enrollment_readback_rejects_tampered_helper(self):
        entries=json.loads((e.SMOKE_DIRECTORY/'enrollments.json').read_text())
        e.validate_enrollments(self.smoke_plan,entries)
        entries[0]['helper_bits']='0'*63
        with self.assertRaisesRegex(ValueError,'helper mismatch'):e.validate_enrollments(self.smoke_plan,entries)

    def test_wrong_plan_hash_stops_preflight(self):
        altered=deepcopy(self.config);altered['plan_sha256']='0'*64
        with patch.object(e,'load_config',return_value=altered):
            with self.assertRaisesRegex(ValueError,'plan hash'):e.formal_preflight(e.ROOT/e.FORMAL_RELATIVE)


if __name__=='__main__':unittest.main()