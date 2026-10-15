"""Audit corrections: bounded deterministic fixtures only, no research execution."""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import io
import json
import os
from pathlib import Path
from random import Random
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from experiments import test_majority3_auth_v1 as fixtures
from puf_snn.auth import credential_verifier as admission
from puf_snn.auth.sender import Sender
from puf_snn.auth.verifier import Verifier
from puf_snn.experiments import majority3_auth_v1 as study
from puf_snn.experiments import majority3_auth_runtime_v1 as runtime
from puf_snn.experiments import majority3_auth_evidence_v1 as evidence
from puf_snn.experiments import majority3_auth_analysis_v1 as analysis
from puf_snn.experiments import correlated_noise_v1 as noise


def remove_spans(row, stages):
    spans = [s for s in row['timing'] if s['stage'] not in stages]
    mapping = {s['id']: i for i, s in enumerate(spans)}
    for s in spans:
        s['id'] = mapping[s['id']]
        s['parent_id'] = mapping[s['parent_id']] if s['parent_id'] is not None else None
    row['timing'] = spans


class RuntimeCorrectionTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.RuntimeTests.setUpClass.__func__)
    controlled = fixtures.RuntimeTests.controlled
    run_control = fixtures.RuntimeTests.run_control

    def run_attempt(self, enrollment=None):
        return fixtures.execute(self.config, self.plan, self.trial, 'single-read-v1',
                                self.controlled() if enrollment is None else enrollment)

    def assert_no_admission(self, row):
        self.assertFalse(row['establishment']['request_emitted'])
        self.assertFalse(row['establishment']['session_active'])
        self.assertFalse(any(row['endpoint_state'].values()))
        self.assertEqual(row['handshake'], [])
        self.assertEqual(row['window_verifications'], [])
        self.assertIsNone(row['window'])
        self.assertEqual(row['release_count'], 0)
        self.assertEqual(row['model_calls'], dict(preprocessing=0, motion=0, anomaly=0))
        self.assertFalse(any(s['stage'].endswith('hkdf') for s in row['timing']))

    def test_correct_and_wrong_credential_classification(self):
        for kind, diagnostic in (('C', 'issued'), ('W', 'credential_mismatch')):
            row = self.run_control(kind)
            self.assertEqual(row['authorization_diagnostics'], [diagnostic])
            evidence.validate_protocol(row)
            if kind == 'W':
                self.assert_no_admission(row)

    def test_swallowed_issuance_exception_after_verification_is_a_fault(self):
        with patch.object(admission, '_Admission', side_effect=RuntimeError('private sentinel')):
            row = self.run_attempt()
        self.assertEqual(row['verification_outcomes'], ['verified'])
        self.assertEqual(row['authorization_outcomes'], [False])
        self.assertEqual(row['authorization_diagnostics'], ['issuance_fault'])
        self.assertEqual(row['fault_code'], 'authorization_issuance_fault')
        self.assertEqual(row['execution_status'], 'fault')
        self.assertNotIn('private sentinel', json.dumps(row))
        self.assert_no_admission(row)
        with self.assertRaisesRegex(ValueError, 'execution fault'):
            evidence.validate_protocol(row)
        # Erasing the fault label/diagnostic cannot turn verified + no handle
        # into a legitimate credential-mismatch FRR observation.
        row.update(execution_status='completed', fault_code=None)
        row['authorization_diagnostics'] = ['credential_mismatch']
        with self.assertRaisesRegex(ValueError, 'authorization issuance'):
            evidence.validate_protocol(row)

    def test_disabled_and_revoked_policy_refusals_are_not_issuance_faults(self):
        for change in (dict(enabled=False), dict(revoked=True)):
            enrollment = self.controlled()
            enrollment = replace(enrollment, verifier_record=replace(enrollment.verifier_record, **change))
            row = self.run_attempt(enrollment)
            self.assertEqual(row['execution_status'], 'completed')
            self.assertEqual(row['verification_outcomes'], ['record_disabled'])
            self.assertEqual(row['authorization_diagnostics'], ['policy_refusal'])
            self.assert_no_admission(row)
            evidence.validate_protocol(row, fresh_enabled_study=False)
            with self.assertRaisesRegex(ValueError, 'outside the fresh enabled study'):
                evidence.validate_protocol(row)

    def test_missing_record_and_missing_verification_are_configuration_faults(self):
        for target, replacement in ((admission.CredentialVerifierStore, 'get'),
                                    (admission.CredentialAdmissionService, 'authorize')):
            with patch.object(target, replacement, return_value=None):
                row = self.run_attempt()
            self.assertEqual(row['execution_status'], 'fault')
            self.assertEqual(row['fault_code'], 'authorization_configuration_fault')
            self.assert_no_admission(row)

    def test_verifier_infrastructure_failure_is_not_credential_mismatch(self):
        with patch.object(admission, '_get_key', side_effect=ValueError('unavailable')):
            row = self.run_attempt()
        self.assertEqual(row['execution_status'], 'fault')
        self.assertEqual(row['authorization_diagnostics'], ['verification_fault'])
        self.assert_no_admission(row)

    def test_real_partial_handshake_timeouts_reconcile_endpoint_and_hkdf_states(self):
        cases = ((Verifier, 'begin_session', True, (False, False), (0, 1)),
                 (Verifier, 'confirm_session', False, (False, False), (1, 1)),
                 (Verifier, 'confirm_session', True, (False, True), (1, 1)))
        for owner, name, after, endpoints, kdfs in cases:
            now = [1_000_000_000]
            original = getattr(owner, name)
            def delayed(instance, *args, **kwargs):
                if not after:
                    now[0] += 11_000_000_000
                result = original(instance, *args, **kwargs)
                if after:
                    now[0] += 11_000_000_000
                return result
            with self.subTest(stage=name, after=after), \
                 patch('puf_snn.auth.session.time.monotonic_ns', side_effect=lambda: now[0]), \
                 patch.object(owner, name, delayed):
                row = self.run_attempt()
            self.assertEqual(row['execution_status'], 'completed')
            self.assertEqual(row['establishment']['reason'], 'handshake_timeout')
            self.assertEqual(tuple(row['endpoint_state'].values()), endpoints)
            counts = Counter(s['stage'] for s in row['timing'])
            self.assertEqual((counts['sender_hkdf'], counts['receiver_hkdf']), kdfs)
            evidence.validate_protocol(row)
            evidence.validate_timing(row)
            self.assertEqual(row['release_count'], 0)

    def test_timeout_before_request_and_after_request_remain_legitimate(self):
        # Capability expiry at bind_request is legitimate, even after issuance.
        for owner, name in ((admission.CredentialAdmissionService, 'bind_request'),
                            (Verifier, 'begin_session')):
            now = [1_000_000_000]
            original = getattr(owner, name)
            def delayed(instance, *args, **kwargs):
                now[0] += 11_000_000_000
                return original(instance, *args, **kwargs)
            with patch('puf_snn.auth.session.time.monotonic_ns', side_effect=lambda: now[0]), \
                 patch.object(owner, name, delayed):
                row = self.run_attempt()
            self.assertEqual(row['execution_status'], 'completed')
            self.assertEqual(row['authorization_diagnostics'], ['issued'])
            evidence.validate_protocol(row)
            evidence.validate_timing(row)

    def test_rejected_window_and_verifier_expiry_remain_valid(self):
        original = Verifier.verify_window
        for expired in (False, True):
            now = [1_000_000_000]
            def changed(instance, packet, *args, **kwargs):
                if expired:
                    now[0] += 301_000_000_000
                else:
                    obj = json.loads(packet)
                    tag = obj['authentication']['tag_hex']
                    obj['authentication']['tag_hex'] = ('0' if tag[0] != '0' else '1') + tag[1:]
                    packet = study.canonical(obj)
                return original(instance, packet, *args, **kwargs)
            with patch('puf_snn.auth.session.time.monotonic_ns', side_effect=lambda: now[0]), \
                 patch.object(Verifier, 'verify_window', changed):
                row = self.run_attempt()
            evidence.validate_protocol(row)
            evidence.validate_timing(row)
            self.assertEqual(row['window']['decision'], 'reject')
            self.assertIsNone(row['window']['sequence_number'])
            bad = deepcopy(row)
            bad['window'].update(decision='accept', reason='accepted', sequence_number=0)
            with self.assertRaisesRegex(ValueError, 'window/verifier'):
                evidence.validate_protocol(bad)

    def test_authorization_fault_stops_writer_and_preserves_actual_counts(self):
        root = Path(self.enterContext(TemporaryDirectory(dir=study.ROOT/'tmp')))
        directory = root/(evidence.TEST_PREFIX+'issuance-fault')
        with evidence.EvidenceRun(directory, self.config, test_output_root=root) as run:
            with patch.object(admission, '_Admission', side_effect=RuntimeError('private sentinel')), \
                 self.assertRaisesRegex(ValueError, 'execution fault'):
                run.execute()
            self.assertEqual(len(run.rows), 1)
            self.assert_no_admission(run.rows[0])
        incomplete = evidence.read_json(directory/'INCOMPLETE.json')
        self.assertEqual(incomplete['observed_execution']['policy_attempts_completed'], 0)
        self.assertEqual(incomplete['observed_execution']['measured_trial_invocations'], run.rows[0]['actual_reads'])
        self.assertFalse((directory/'UNIT_TEST_VALIDATED.json').exists())
        self.assertFalse((directory/'summary.json').exists())
        with self.assertRaises((ValueError, FileNotFoundError)):
            evidence.audit_evidence(directory)

    def test_failed_acquisition_counts_invocations_separately_from_observations(self):
        with patch.object(noise, 'calculate_frequencies', side_effect=RuntimeError('test fault')):
            row = self.run_attempt()
        resources = evidence.execution_resources([row], {})
        self.assertEqual(resources['measured_trial_invocations'], 1)
        self.assertEqual(resources['measured_trial_observations'], 0)
        self.assertEqual(resources['policy_attempts_completed'], 0)

    def test_missing_service_during_setup_retains_incomplete_evidence(self):
        root = Path(self.enterContext(TemporaryDirectory(dir=study.ROOT/'tmp')))
        directory = root/(evidence.TEST_PREFIX+'missing-service')
        original = runtime.fresh_pipeline
        def missing_service(config, enrollment, policy):
            pipeline, consumer = original(config, enrollment, policy)
            Sender(pipeline.sender.enrollment, pipeline.sender.limits, admission_service=None)
            return pipeline, consumer
        with evidence.EvidenceRun(directory, self.config, test_output_root=root) as run:
            with patch.object(runtime, 'fresh_pipeline', missing_service), self.assertRaises(ValueError):
                run.execute()
            self.assertEqual(run.rows, [])
        incomplete = evidence.read_json(directory/'INCOMPLETE.json')
        self.assertEqual(incomplete['observed_execution']['measured_trial_invocations'], 0)
        self.assertEqual(incomplete['unrecorded_or_interrupted_work'], 'unknown')
        self.assertFalse((directory/'UNIT_TEST_VALIDATED.json').exists())


class SemanticEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = TemporaryDirectory(dir=study.ROOT/'tmp')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name)/(evidence.TEST_PREFIX+'corrections')
        cls.config = fixtures.fixture_config()
        with evidence.EvidenceRun(cls.directory, cls.config, test_output_root=cls.temp.name) as run:
            cls.receipt = run.execute()
            cls.rows, cls.catalog, cls.plan = deepcopy(run.rows), run.catalog, run.plan
            cls.context = dict(run_id=run.metadata['run_id'], source_id=run.metadata['source_id'])

    def mutated(self):
        rows = deepcopy(self.rows)
        return rows, next(r for r in rows if r['establishment']['session_active'])

    def reconcile(self, rows):
        return evidence.reconcile(self.config, self.plan, rows, self.catalog, self.context)

    def test_original_counterexample_rehashed_and_resummarized_is_rejected(self):
        root = Path(self.enterContext(TemporaryDirectory(dir=study.ROOT/'tmp')))
        target = root/'copy'
        shutil.copytree(self.directory, target)
        rows, row = self.mutated()
        row['establishment'].update(session_active=False, decision='reject')
        row.update(window=None, window_verifications=[], release_count=0, authorized_release_count=0)
        row['model_calls'] = dict(preprocessing=0, motion=0, anomaly=0)
        remove_spans(row, {'first_window', 'window_seal', 'window_verify', 'release'})
        # All four successful stages and both active flags remain, as in F1.
        (target/'attempts.jsonl').write_bytes(b''.join(study.canonical(r)+b'\n' for r in rows))
        summary = evidence.read_json(target/'summary.json')
        summary['analysis'] = analysis.summarize(self.config, rows)
        (target/'summary.json').write_bytes(study.canonical(summary))
        manifest = evidence.read_json(target/'manifest.json')
        manifest = {p: evidence.file_digest(target/p) for p in manifest}
        (target/'manifest.json').write_bytes(study.canonical(manifest))
        marker = evidence.read_json(target/'UNIT_TEST_VALIDATED.json')
        marker['manifest_sha256'] = evidence.file_digest(target/'manifest.json')
        (target/'UNIT_TEST_VALIDATED.json').write_bytes(study.canonical(marker))
        with self.assertRaisesRegex(ValueError, 'terminal protocol outcome'):
            evidence.audit_evidence(target)

    def test_only_final_decision_change_is_rejected(self):
        rows, row = self.mutated()
        row['establishment']['decision'] = 'reject'
        with self.assertRaisesRegex(ValueError, 'terminal protocol outcome'):
            self.reconcile(rows)

    def test_missing_terminal_success_and_endpoint_contradictions(self):
        for mutation in ('terminal', 'sender', 'receiver', 'terminal-reason'):
            rows, row = self.mutated()
            if mutation == 'terminal':
                row['handshake'].pop()
            elif mutation == 'terminal-reason':
                row['handshake'][-1]['reason'] = 'handshake_timeout'
            else:
                row['endpoint_state'][mutation+'_active'] = False
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.reconcile(rows)

    def test_window_reasons_verifier_acceptance_and_release_are_bidirectional(self):
        for mutation in ('accept-with-rejection-reason', 'reject-with-accepted-reason', 'verifier-reject',
                         'unauthenticated-verifier', 'release-without-acceptance', 'sequence', 'missing-hkdf'):
            rows, row = self.mutated()
            if mutation == 'accept-with-rejection-reason':
                row['window']['reason'] = row['window_verifications'][0]['reason'] = 'invalid_tag'
            elif mutation == 'reject-with-accepted-reason':
                row['window']['decision'] = row['window_verifications'][0]['decision'] = 'reject'
            elif mutation == 'verifier-reject':
                row['window_verifications'][0].update(decision='reject', reason='invalid_tag',
                                                     sequence_number=None, authenticated=False)
            elif mutation == 'unauthenticated-verifier':
                row['window_verifications'][0]['authenticated'] = False
            elif mutation == 'release-without-acceptance':
                row['window'].update(decision='reject', reason='invalid_tag', sequence_number=None)
                row['window_verifications'][0].update(decision='reject', reason='invalid_tag',
                                                     sequence_number=None, authenticated=False)
            elif mutation == 'sequence':
                row['window']['sequence_number'] = row['window_verifications'][0]['sequence_number'] = 1
            else:
                remove_spans(row, {'receiver_hkdf'})
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.reconcile(rows)

    def test_real_partial_timeouts_pass_full_reconciliation(self):
        for name, after in (('begin_session', True), ('confirm_session', False), ('confirm_session', True)):
            rows, row = self.mutated()
            trial = next(t for t in self.plan['blocks'] if t['trial_id'] == row['trial_id'])
            enrollment = study.prepare_enrollment(self.config, row['population_id'], row['device_id'])
            original = getattr(Verifier, name)
            now = [1_000_000_000]
            def delayed(instance, *args, **kwargs):
                if not after:
                    now[0] += 11_000_000_000
                result = original(instance, *args, **kwargs)
                if after:
                    now[0] += 11_000_000_000
                return result
            with patch('puf_snn.auth.session.time.monotonic_ns', side_effect=lambda: now[0]), \
                 patch.object(Verifier, name, delayed):
                replacement = runtime.execute_attempt(self.config, trial, row['policy'], enrollment,
                    **self.context, plan_sha256=self.plan['plan_sha256'], execution_index=row['execution_index'])
            self.assertEqual(replacement['establishment']['reason'], 'handshake_timeout')
            rows[row['execution_index']] = replacement
            self.assertEqual(self.reconcile(rows)['status'], 'PASS')

    def test_erasing_authorization_fault_cannot_create_valid_frr_evidence(self):
        rows, row = self.mutated()
        row['authorization_outcomes'] = [False]
        row['authorization_diagnostics'] = ['credential_mismatch']
        row['establishment'].update(decision='reject', stage='credential_admission',
                                   reason='credential_verification_failed', session_active=False, request_emitted=False)
        row.update(handshake=[], window=None, window_verifications=[], release_count=0, authorized_release_count=0,
                   endpoint_state=dict(sender_active=False, receiver_active=False),
                   model_calls=dict(preprocessing=0, motion=0, anomaly=0))
        remove_spans(row, {'mutual_handshake', 'receiver_challenge', 'receiver_hkdf', 'sender_confirmation',
                          'sender_hkdf', 'receiver_confirmation', 'sender_activation', 'first_window',
                          'window_seal', 'window_verify', 'release'})
        with self.assertRaisesRegex(ValueError, 'authorization issuance'):
            self.reconcile(rows)

    def test_replay_counts_and_audit_do_not_modify_evidence_or_statistics(self):
        before = {p.relative_to(self.directory): evidence.file_digest(p)
                  for p in self.directory.rglob('*') if p.is_file()}
        with patch.object(noise, 'measure_indexed', wraps=noise.measure_indexed) as reads, \
             patch.object(study, 'generate_response', wraps=study.generate_response) as references:
            receipt = evidence.audit_evidence(self.directory)
        self.assertEqual(reads.call_count, 40)
        self.assertEqual(references.call_count, 1)
        self.assertEqual(receipt['policy_attempts'], 20)
        self.assertEqual(receipt['validation_work']['replay_measurement_invocations'], 40)
        self.assertEqual(receipt['validation_work']['statistical_samples_added'], 0)
        self.assertEqual(sum(p['replay_measurement_invocations'] for p in
                             receipt['resource_accounting']['validation_replays']), 80)
        after = {p.relative_to(self.directory): evidence.file_digest(p)
                 for p in self.directory.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_disclosure_and_new_evidence_revision(self):
        metadata = evidence.read_json(self.directory/'metadata.json')
        self.assertNotIn('secrets_persisted', metadata)
        self.assertEqual(metadata['disclosure'], evidence.DISCLOSURE)
        self.assertTrue(metadata['disclosure']['synthetic_pilot_credential_reconstructible_from_replay_inputs'])
        self.assertFalse(metadata['disclosure']['replay_material_confidential'])
        row = deepcopy(self.rows[0])
        row['schema_version'] = study.VERSION+':attempt'
        with self.assertRaisesRegex(ValueError, 'schema'):
            study.validate_schema('attempt', row)

    def test_rehashed_disclosure_claim_is_rejected(self):
        root = Path(self.enterContext(TemporaryDirectory(dir=study.ROOT/'tmp')))
        directory = root/'copy'
        shutil.copytree(self.directory, directory)
        metadata = evidence.read_json(directory/'metadata.json')
        metadata['disclosure']['synthetic_pilot_credential_reconstructible_from_replay_inputs'] = False
        (directory/'metadata.json').write_bytes(study.canonical(metadata))
        manifest = evidence.read_json(directory/'manifest.json')
        manifest['metadata.json'] = evidence.file_digest(directory/'metadata.json')
        (directory/'manifest.json').write_bytes(study.canonical(manifest))
        with self.assertRaisesRegex(ValueError, 'disclosure'):
            evidence.audit_evidence(directory)


class ResourceAndPathTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory(dir=study.ROOT/'tmp')))
        self.config = fixtures.fixture_config()

    def test_smoke_plan_counts_without_executing_attempts(self):
        config = fixtures.fixture_config(mode='nonformal', allocation=dict(
            populations=1, devices_per_population=1, attempts_per_device_condition=10))
        with patch.object(runtime, 'execute_attempt', side_effect=AssertionError('no research execution')):
            plan = study.compile_plan(config)
            estimate = evidence.resource_estimate(plan)
        self.assertEqual(plan['counts'], dict(matched_trials=50, policy_attempts=100, expected_reads=200))
        self.assertEqual(estimate['measured_trial_readings'], 200)
        self.assertEqual(estimate['validation_replay_readings'], 400)
        self.assertEqual(estimate['enrollment_setup']['execution_reference_readings'], 1)
        self.assertEqual(estimate['enrollment_setup']['validation_reference_readings'], 2)
        self.assertEqual(estimate['total_simulator_measurement_invocations'], 603)
        self.assertEqual(estimate['additional_audit']['validation_replay_readings'], 200)

    def test_counts_follow_supported_allocations_and_replay_workflow(self):
        for populations, devices in ((1, 1), (1, 2), (2, 1), (2, 2)):
            config = fixtures.fixture_config(allocation=dict(populations=populations,
                devices_per_population=devices, attempts_per_device_condition=2))
            plan = study.compile_plan(config)
            for passes in (2, 3):
                phases = ('pre_summary',)+('manifest_audit',)*(passes-1)
                with patch.object(evidence, 'FINALIZATION_REPLAYS', phases):
                    result = evidence.resource_estimate(plan)
                expected = sum(study.POLICIES[p].read_count for t in plan['blocks'] for p in t['policy_order'])
                self.assertEqual(result['measured_trial_readings'], expected)
                self.assertEqual(result['validation_replay_readings'], expected*passes)
                self.assertEqual(result['enrollment_setup']['validation_reference_readings'], populations*devices*passes)

    def test_three_replay_phases_are_measured_not_hardcoded(self):
        directory = self.root/(evidence.TEST_PREFIX+'three-passes')
        phases = ('pre_summary', 'manifest_audit', 'manifest_audit')
        with patch.object(evidence, 'FINALIZATION_REPLAYS', phases), \
             patch.object(noise, 'measure_indexed', wraps=noise.measure_indexed) as reads, \
             patch.object(study, 'generate_response', wraps=study.generate_response) as references:
            with evidence.EvidenceRun(directory, self.config, test_output_root=self.root) as run:
                receipt = run.execute()
        self.assertEqual(reads.call_count, 40*(1+len(phases)))
        self.assertEqual(references.call_count, 1+len(phases))
        self.assertEqual(receipt['actual_reads'], 40)
        self.assertEqual(len(receipt['resource_accounting']['validation_replays']), 3)

    def test_historical_ids_in_other_parents_and_wrong_prefixes_are_rejected(self):
        for name in ('tier1-v2-formal-001', 'week6-reconstruction-alternatives-v1-formal-001',
                     'smoke-001', evidence.RUN_PREFIX+'001', evidence.TEST_PREFIX.upper()+'001'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                evidence.EvidenceRun(self.root/name, self.config, test_output_root=self.root)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_historical_roots_and_existing_evidence_ancestors_are_rejected(self):
        for root in (study.ROOT/'results/week-5/will/authentication',
                     study.ROOT/'results/week-6/will/reconstruction-alternatives',
                     self.root/'WEEK-5'/'historical', self.root/'week6'/'history'):
            with self.assertRaises(ValueError):
                evidence.checked_output_path(root/(evidence.TEST_PREFIX+'001'), 'unit-test', test_output_root=root)
        (self.root/'manifest.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'existing evidence'):
            evidence.checked_output_path(self.root/(evidence.TEST_PREFIX+'001'), 'unit-test', test_output_root=self.root)

    def test_traversal_windows_aliases_and_wrong_parents_are_rejected(self):
        name = evidence.TEST_PREFIX+'001'
        for path in (self.root/'..'/name, self.root/'nested'/'..'/name,
                     self.root/'nested'/name, self.root/(name+'.'), self.root/(name+' '),
                     self.root/(name+':stream'), 'C:relative/'+name, '//server/share/'+name):
            with self.subTest(path=path), self.assertRaises(ValueError):
                evidence.checked_output_path(path, 'unit-test', test_output_root=self.root)

    def test_linked_ancestor_is_rejected(self):
        target, alias = self.root/'target', self.root/'alias'
        target.mkdir()
        if os.name == 'nt':
            import _winapi
            _winapi.CreateJunction(str(target), str(alias))
        else:
            alias.symlink_to(target, target_is_directory=True)
        # TemporaryDirectory removes the link itself, not its target recursively.
        with self.assertRaisesRegex(ValueError, 'linked output ancestor'):
            evidence.checked_output_path(alias/(evidence.TEST_PREFIX+'001'), 'unit-test', test_output_root=alias)

    def test_valid_namespaces_and_exclusive_creation(self):
        nonformal = evidence.NONFORMAL_ROOT/(evidence.RUN_PREFIX+'001')
        self.assertEqual(evidence.checked_output_path(nonformal, 'nonformal'), nonformal.resolve())
        self.assertFalse(nonformal.exists())  # No nonformal writer or experiment.
        directory = self.root/(evidence.TEST_PREFIX+'001')
        with evidence.EvidenceRun(directory, self.config, test_output_root=self.root):
            pass
        with self.assertRaisesRegex(ValueError, 'exclusively new'):
            evidence.EvidenceRun(directory, self.config, test_output_root=self.root)
        with self.assertRaisesRegex(ValueError, 'explicit test policy'):
            evidence.EvidenceRun(self.root/(evidence.TEST_PREFIX+'002'), self.config)

    def test_correct_token_wrong_plan_hash_fails_independently_in_cli(self):
        from scripts.run_majority3_auth_correlated import main
        directory = evidence.NONFORMAL_ROOT/(evidence.RUN_PREFIX+'never-created')
        with patch.object(evidence.EvidenceRun, 'execute', side_effect=AssertionError('no execution')), \
             self.assertRaisesRegex(ValueError, 'incorrect reviewed plan hash'):
            main(['run-nonformal', '--directory', str(directory),
                  '--authorize-nonformal', 'RUN-100-NONFORMAL', '--reviewed-plan-sha256', '0'*64])
        self.assertFalse(directory.exists())

    def test_cli_estimate_labels_replay_and_setup(self):
        from scripts.run_majority3_auth_correlated import main
        with patch.object(evidence.EvidenceRun, 'execute', side_effect=AssertionError('no execution')), \
             patch('sys.stdout', new_callable=io.StringIO) as output:
            main(['estimate', '--nonformal-plan'])
        result = json.loads(output.getvalue())
        self.assertEqual(result['executed_attempts'], 0)
        self.assertEqual(result['resources']['validation_replay_readings'], 400)


class StatisticalCorrectionTests(unittest.TestCase):
    def test_one_population_suppresses_inferential_interval(self):
        cells = {'p0': {c+'|'+p: (int(p == 'single-read-v1'), int(p == 'majority-3-v1'), 2)
                        for c, *_ in study.CONDITIONS for p in study.POLICIES}}
        result = analysis.bootstrap_populations(cells, seed=7, resamples=19)
        self.assertEqual(result['interval_status'], 'suppressed_insufficient_populations')
        self.assertIsNone(result['confidence_level'])
        self.assertEqual(result['performed_resamples'], 0)
        for interval in result['intervals'].values():
            self.assertIsNone(interval['lower'])
            self.assertIsNone(interval['upper'])
            self.assertEqual(interval['defined_resamples'], 0)
        self.assertEqual(result['intervals']['reconstruction:delta:independent_nominal']['estimate'], .5)

    def test_every_draw_pairs_both_policies_and_all_conditions(self):
        # Both policies vary, with different population patterns per condition.
        cells = {f'p{i}': {c+'|'+policy: ((i+2*j+k)%5, (2*i+j+3*k)%5, 5)
                           for j, (c, *_) in enumerate(study.CONDITIONS)
                           for k, policy in enumerate(study.POLICIES)} for i in range(3)}
        seed, resamples = 41, 37
        original = analysis.estimands
        observed = []
        def observe(data, weights=None):
            if weights is not None:
                observed.append(dict(weights))
            return original(data, weights)
        with patch.object(analysis, 'estimands', side_effect=observe):
            actual = analysis.bootstrap_populations(cells, seed=seed, resamples=resamples)
        rng = Random(seed)
        populations = sorted(cells)
        draws = []
        for _ in range(resamples):
            indices = [populations[rng.randrange(3)] for _ in populations]
            weights = Counter(indices)
            self.assertEqual(observed[len(draws)], weights)
            # Independent expansion of each paired draw, not estimands(weights).
            draw = {}
            for metric, column in (('reconstruction', 0), ('session', 1)):
                for c, *_ in study.CONDITIONS:
                    rates = [sum(cells[p][c+'|'+policy][column] for p in indices)/15
                             for policy in study.POLICIES]
                    draw[metric+':delta:'+c] = rates[0]-rates[1]
                for rho in ('50', '90'):
                    draw[metric+':attenuation:rho'+rho] = (
                        draw[metric+':delta:independent_nominal']-draw[metric+':delta:differential_rho'+rho])
            draws.append(draw)
        self.assertEqual(len(observed), resamples)
        for key, interval in actual['intervals'].items():
            values = [d[key] for d in draws]
            self.assertEqual(interval['lower'], analysis.percentile(values, .025))
            self.assertEqual(interval['upper'], analysis.percentile(values, .975))
        self.assertEqual(actual['performed_resamples'], resamples)
        self.assertEqual(actual['confidence_level'], .95)


if __name__ == '__main__':
    unittest.main()
