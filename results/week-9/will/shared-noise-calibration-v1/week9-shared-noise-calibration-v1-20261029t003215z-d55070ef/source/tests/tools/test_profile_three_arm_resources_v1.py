"""Only stdlib stubs and tiny temporary files; never import or run the study."""
import copy
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import weakref
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools import profile_three_arm_resources_v1 as profiler


class Validator:
    def __init__(self, schema):
        self.schema = schema

    @classmethod
    def check_schema(cls, schema):
        return cls(schema)


def configuration():
    return dict(mode='nonformal', allocation=dict(populations=1, devices_per_population=1,
        attempts_per_device_condition=10),
        execution_limits=dict(formal_execution_enabled=False, nonformal_max_matched_trials=50,
            nonformal_max_arm_attempts=150, retries=0),
        timing_methodology=dict(profile='cold-process-no-harness-warmup-v1'),
        authentication=dict(warmup_iterations=0))


def config_stub(obj=None):
    return SimpleNamespace(to_dict=lambda: copy.deepcopy(obj or configuration()), digest='config-hash')


def stub_modules(config=None):
    config = config or config_stub()
    study = SimpleNamespace(StudyConfig=SimpleNamespace(load=Mock(return_value=config)),
        compile_plan=Mock(return_value=dict(plan_sha256='reviewed', counts=dict(arm_attempts=150, matched_trials=50))),
        validate_plan=Mock(), Draft202012Validator=Validator, prepare_population=Mock(),
        validate_schema=Mock(), canonical=lambda obj: json.dumps(obj, sort_keys=True).encode(),
        previous=SimpleNamespace(validate_schema=Mock(), canonical=Mock()))
    evidence = SimpleNamespace(checked_output_path=Mock(), source_hashes=Mock(return_value={'p': 'hash'}),
        file_digest=Mock(), previous=SimpleNamespace(source_hashes=Mock(), file_digest=Mock()),
        execute_attempt=Mock(), reconcile=Mock(), summarize=Mock(), audit_evidence=Mock(),
        write_json=Mock(), EvidenceRun=Mock())
    evidence.previous.canonical = study.canonical
    return study, evidence


class StubSupervision:
    """Explicit unit-test seam; real Windows protocol is tested separately."""
    def __init__(self, request):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def check(self):
        pass

    def finish(self, path):
        pass


class StubController:
    def __init__(self, *args):
        pass

    def pulse(self):
        pass

    def completed(self, path):
        return True

    def close(self):
        pass


def run_supervised_stub():
    """Child interpreter entry: genuine supervision, tiny fake scientific lifecycle."""
    request = json.load(sys.stdin)
    child = Path(request['worker_sidecar'])
    profiler.EVIDENCE_ROOT = Path(request['directories'][0]).parent
    profiler.SIDECAR_ROOT = child.parent.parent
    study, evidence = stub_modules()

    class Run:
        def __init__(self, directory, *args, **kwargs):
            self.directory = Path(directory)
            self.directory.mkdir(parents=True, exist_ok=False)
            (self.directory/'INCOMPLETE.json').write_text('{}')

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

        def execute(self):
            evidence.execute_attempt()
            return self.finalize()

        def append(self, row):
            pass

        def finalize(self):
            (self.directory/'NONFORMAL_VALIDATED.json').write_text('{}')
            (self.directory/'INCOMPLETE.json').unlink()
            return dict(status='PASS', arm_attempts=150, validation_passes_completed=2)

    evidence.EvidenceRun = Run
    def load():
        # Reached only after request approval, native supervision, and slot claim.
        profiler.save_json(child/'supervised-ready.json', dict(pid=os.getpid(), parent_pid=os.getppid(),
            executable=sys.executable, prefix=sys.prefix, base_prefix=sys.base_prefix))
        return study, evidence
    profiler.worker(request, loader=load)


class ProfilerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='resource-profiler-unit-')
        self.root = Path(self.temp.name)
        self.paths = patch.multiple(profiler, EVIDENCE_ROOT=self.root/'evidence', SIDECAR_ROOT=self.root/'sidecars')
        self.paths.start()
        self.config_path = self.root/'config.json'
        self.config_path.write_text('{}', encoding='utf-8')
        self.args = profiler.parser().parse_args(['dry-run', '--session', 'unit',
            '--config', str(self.config_path), '--reviewed-plan-sha256', 'reviewed'])
        self.budgets = profiler.Budgets(10, 20, 1000000000, 1, 1, 1000000, 10000000, .01, .02)
        self.sample = dict(rss_bytes=10, private_bytes=10, os_peak_rss_bytes=10,
            free_ram_bytes=100, free_disk_bytes=100, cpu_seconds=None, logical_io=None)

    def tearDown(self):
        self.paths.stop()
        self.temp.cleanup()

    def test_dry_run_never_constructs_run_audits_launches_or_writes(self):
        study, evidence = stub_modules()
        with patch.object(profiler.subprocess, 'Popen', side_effect=AssertionError('launch')):
            result = profiler.preflight(self.args, loader=lambda: (study, evidence))
        self.assertFalse(result['experiment_executed'])
        evidence.EvidenceRun.assert_not_called()
        evidence.audit_evidence.assert_not_called()
        study.prepare_population.assert_not_called()
        self.assertFalse((self.root/'evidence').exists())
        self.assertFalse((self.root/'sidecars').exists())

    def test_preflight_without_review_is_read_only(self):
        self.args.action, self.args.reviewed_plan_sha256 = 'preflight', None
        self.assertEqual(profiler.preflight(self.args, loader=stub_modules)['plan_sha256'], 'reviewed')

    def test_invalid_reviewed_plan(self):
        study, evidence = stub_modules()
        self.args.reviewed_plan_sha256 = 'wrong'
        with self.assertRaisesRegex(ValueError, 'reviewed plan'):
            profiler.preflight(self.args, loader=lambda: (study, evidence))
        evidence.EvidenceRun.assert_not_called()

    def test_authorization_rejected_before_import_or_launch(self):
        self.args.action = 'execute'
        loader = Mock()
        with self.assertRaisesRegex(ValueError, 'approval'):
            profiler.preflight(self.args, loader=loader)
        loader.assert_not_called()
        for request, message in ((dict(approval=profiler.APPROVAL), 'nonformal authorization'),
                (dict(approval=profiler.APPROVAL, authorization=profiler.AUTHORIZATION, audits=1), 'audit')):
            with self.assertRaisesRegex(ValueError, message):
                profiler.check_approval(request)
        with self.assertRaisesRegex(ValueError, 'approval'):
            profiler.worker({}, loader=loader)
        loader.assert_not_called()

    def test_wrong_attempt_limit_and_larger_or_formal_allocations(self):
        for field, value in (('nonformal_max_arm_attempts', 151), ('nonformal_max_matched_trials', 51),
                             ('retries', 1), ('formal_execution_enabled', True)):
            obj = configuration()
            obj['execution_limits'][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'attempt limit'):
                profiler.check_config(stub_modules()[0], config_stub(obj), 'reviewed')
        for mode, count in (('planned-formal', 20), ('unit-test', 1), ('nonformal', 2)):
            obj = configuration()
            obj['mode'], obj['allocation']['populations'] = mode, count
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                profiler.check_config(stub_modules()[0], config_stub(obj), 'reviewed')

    def test_wrong_plan_count_and_timing_profile(self):
        study, _ = stub_modules()
        study.compile_plan.return_value['counts']['arm_attempts'] = 151
        with self.assertRaisesRegex(ValueError, '150 arms'):
            profiler.check_config(study, config_stub(), 'reviewed')
        obj = configuration()
        obj['authentication']['warmup_iterations'] = 20
        with self.assertRaisesRegex(ValueError, 'timing profile'):
            profiler.check_config(stub_modules()[0], config_stub(obj), 'reviewed')

    def test_historical_token_alias_collision_and_separate_sidecars(self):
        for session in ('../week-7', 'UPPER', 'a/old', 'a'*25, ''):
            with self.subTest(session=session), self.assertRaises(ValueError):
                profiler.layout(session, 1, 1, 0)
        sidecar, bundles = profiler.layout('unit', 1, 1, 0)
        self.assertFalse(sidecar.is_relative_to(bundles[0][0]))
        self.assertFalse(bundles[0][0].is_relative_to(sidecar))
        bundles[0][0].mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'collision'):
            profiler.layout('unit', 1, 1, 0)
        sidecar.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'session collision'):
            profiler.layout('unit', 1, 1, 0)
        with patch.object(Path, 'is_symlink', return_value=True):
            with self.assertRaisesRegex(ValueError, 'linked'):
                profiler.layout('new', 1, 1, 0)

    def test_existing_protected_path_checker_is_delegated(self):
        study, evidence = stub_modules()
        evidence.checked_output_path.side_effect = ValueError('historical tree forbidden')
        with self.assertRaisesRegex(ValueError, 'historical'):
            profiler.preflight(self.args, loader=lambda: (study, evidence))

    def test_six_bundle_three_audit_caps(self):
        _, bundles = profiler.layout('unit', 3, 2, 3)
        self.assertEqual(sum(map(len, bundles)), 6)
        for p, r, a in ((4, 2, 3), (3, 3, 0), (3, 2, 4), (1, 2, 2), (1, 1, 1), (0, 1, 0)):
            with self.subTest(p=p, r=r, a=a), self.assertRaises(ValueError):
                profiler.layout('unit', p, r, a)

    def violations(self, sample=None, **changes):
        values = dict(phase_seconds=1, session_seconds=1, bundle_bytes=1, total_bytes=1)
        values.update(changes)
        return self.budgets.violations(sample or self.sample, **values)

    def test_all_budget_boundaries(self):
        self.assertEqual(self.violations(), [])
        for name, value, label in (('phase_seconds', 10, 'bundle/audit deadline'),
                ('session_seconds', 20, 'session deadline'), ('bundle_bytes', 1000000, 'bundle growth'),
                ('total_bytes', 10000000, 'aggregate growth')):
            with self.subTest(name=name):
                self.assertIn(label, self.violations(**{name: value}))
        for key, value, label in (('rss_bytes', 1000000000, 'process memory'),
                ('private_bytes', 1000000000, 'process memory'), ('os_peak_rss_bytes', 1000000000, 'process memory'),
                ('free_ram_bytes', 1, 'free_ram_bytes'), ('free_disk_bytes', 1, 'free_disk_bytes')):
            with self.subTest(key=key):
                self.assertIn(label, self.violations(dict(self.sample, **{key: value})))

    def test_unavailable_is_not_zero_and_required_metrics_fail_closed(self):
        peaks = dict(cpu_seconds=None, rss_bytes=None)
        profiler.peak_update(peaks, dict(cpu_seconds=None, rss_bytes=0))
        self.assertIsNone(peaks['cpu_seconds'])
        self.assertEqual(peaks['rss_bytes'], 0)
        unknown = dict(self.sample, rss_bytes=None, private_bytes=None, os_peak_rss_bytes=None)
        self.assertIn('required process memory metric unavailable', self.violations(unknown))
        self.assertIn('required free_ram_bytes unavailable', self.violations(dict(self.sample, free_ram_bytes=None)))

    def test_explicit_finite_budgets_required(self):
        for key, value in (('memory_bytes', None), ('bundle_seconds', float('nan')),
                           ('min_free_ram_bytes', 0), ('sample_seconds', 10)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                replace(self.budgets, **{key: value})

    def test_dry_run_checks_supplied_budgets_without_importing_or_launching(self):
        self.args.bundle_seconds = 900
        loader = Mock()
        with self.assertRaisesRegex(ValueError, 'all budgets'):
            profiler.preflight(self.args, loader=loader)
        loader.assert_not_called()

    def test_inclusive_exclusive_and_duplicate_hash_accounting(self):
        ticks = iter((0, 10, 30, 50))
        m = profiler.Measurements(clock=lambda: next(ticks))
        outer = m.begin('source_hashes_week8')
        child = m.begin('file_hash_week8', 8)
        m.end(child)
        m.end(outer)
        self.assertEqual(m.totals['source_hashes_week8']['inclusive_ns'], 50)
        self.assertEqual(m.totals['source_hashes_week8']['exclusive_ns'], 30)
        self.assertEqual(m.totals['source_hashes_week8']['logical_input_bytes'], 8)
        self.assertEqual(m.totals['file_hash_week8']['inclusive_ns'], 20)

    def test_both_hashing_paths_count_overlapping_input_without_skipping_calls(self):
        study, evidence = stub_modules()
        source = self.root/'source'
        source.write_bytes(b'fixture')
        evidence.previous.file_digest = profiler.digest
        evidence.previous.source_hashes = lambda: evidence.previous.file_digest(source)
        evidence.file_digest = profiler.digest
        def outer():
            evidence.previous.source_hashes()
            return evidence.file_digest(source)
        evidence.source_hashes = outer
        m = profiler.Measurements()
        hash_bindings = [b for b in profiler.instrument_bindings(study, evidence)
                         if b[1] in ('source_hashes', 'file_digest')]
        with profiler.patched(m, hash_bindings):
            self.assertEqual(evidence.source_hashes(), profiler.digest(source))
        self.assertEqual(m.totals['source_hashes_week8']['calls'], 1)
        self.assertEqual(m.totals['source_hashes_week7']['calls'], 1)
        self.assertEqual(m.totals['source_hashes_week8']['logical_input_bytes'], 14)
        self.assertEqual(m.totals['source_hashes_week7']['logical_input_bytes'], 7)
        self.assertEqual(m.totals['file_hash_week8']['calls'], 1)
        self.assertEqual(m.totals['file_hash_week7']['calls'], 1)

    def test_wrappers_preserve_args_identity_returns_exception_and_call_count(self):
        result, a, b, calls = object(), object(), object(), []
        def original(*args, **kwargs):
            calls.append((args, kwargs))
            return result
        owner = SimpleNamespace(fn=original)
        m = profiler.Measurements()
        with profiler.patched(m, [(owner, 'fn', 'delegated', None, False)]):
            self.assertIs(owner.fn(a, optional=b), result)
        self.assertIs(owner.fn, original)
        self.assertEqual(calls, [((a,), dict(optional=b))])
        failure = RuntimeError('fixture')
        def fault():
            raise failure
        owner.fn = fault
        with self.assertRaises(RuntimeError) as caught:
            with profiler.patched(m, [(owner, 'fn', 'failure', None, False)]):
                owner.fn()
        self.assertIs(caught.exception, failure)
        self.assertIs(owner.fn, fault)
        self.assertEqual(m.totals['failure']['calls'], 1)
        self.assertEqual(m.totals['failure']['failures'], 1)

    def test_restore_on_baseexception_and_patch_installation_failure(self):
        original = lambda: None
        owner = SimpleNamespace(fn=original)
        with self.assertRaises(profiler.StopRequested):
            with profiler.patched(profiler.Measurements(), [(owner, 'fn', 'x', None, False)]):
                raise profiler.StopRequested()
        self.assertIs(owner.fn, original)
        with self.assertRaises(AttributeError):
            with profiler.patched(profiler.Measurements(), [(owner, 'fn', 'x', None, False),
                                                          (owner, 'missing', 'y', None, False)]):
                pass
        self.assertIs(owner.fn, original)

    def test_io_hook_keeps_serialized_bytes_and_counts_and_restores(self):
        m = profiler.Measurements()
        path = self.root/'tiny.jsonl'
        canonical = lambda o: json.dumps(o, sort_keys=True, separators=(',', ':')).encode()
        wrapped = m.wrapper(canonical, 'serialize')
        obj = dict(z=1, a='fixture')
        with profiler.io_schema_profile(m, Validator):
            Validator.check_schema({})
            with path.open('xb') as stream:
                stream.write(wrapped(obj)+b'\n')
                stream.flush()
                os.fsync(stream.fileno())
        self.assertEqual(path.read_bytes(), canonical(obj)+b'\n')
        self.assertEqual(m.totals['write']['calls'], 1)
        self.assertEqual(m.totals['flush']['calls'], 1)
        self.assertEqual(m.totals['fsync']['calls'], 1)
        self.assertEqual(m.totals['validator_construction']['calls'], 1)
        self.assertEqual(m.totals['schema_self_check']['calls'], 1)
        self.assertIsNone(sys.getprofile())
        with self.assertRaises(RuntimeError):
            with profiler.io_schema_profile(m, Validator):
                raise RuntimeError()
        self.assertIsNone(sys.getprofile())

    def worker_fixture(self, *, fail_second=False, audits=0, fake_supervision=True):
        study, evidence = stub_modules()
        sidecar, bundles = profiler.layout('unit', 1, 2, audits)
        child = sidecar/'pair-1'
        child.mkdir(parents=True)
        references, endpoint_tokens = [], []
        receipt = dict(status='PASS', arm_attempts=150, validation_passes_completed=2)
        class Run:
            def __init__(inner, directory, config, **kwargs):
                # Fixture only: no study/runtime/PUF/auth imports or allocation loop.
                if references:
                    self.assertIsNone(references[-1](), 'prior active run leaked')
                references.append(weakref.ref(inner))
                inner.directory = Path(directory)
                inner.directory.mkdir(parents=True)
                (inner.directory/'INCOMPLETE.json').write_text('{}')
                endpoint_tokens.append(object())
            def __enter__(inner):
                return inner
            def __exit__(inner, *exc):
                pass
            def append(inner, row):
                pass
            def execute(inner):
                study.prepare_population()
                evidence.execute_attempt()
                inner.append({})
                return inner.finalize()
            def finalize(inner):
                evidence.reconcile()
                if fail_second and len(references) == 2:
                    raise RuntimeError('fixture finalization fault')
                evidence.reconcile()
                evidence.summarize()
                (inner.directory/'NONFORMAL_VALIDATED.json').write_text('{}')
                (inner.directory/'INCOMPLETE.json').unlink()
                return dict(receipt)
        evidence.EvidenceRun = Run
        request = dict(approval=profiler.APPROVAL, authorization=profiler.AUTHORIZATION,
            profiler_sha256=profiler.digest(profiler.__file__), session='unit', pair=1, pairs=1,
            runs_per_pair=2, audits=audits, kind='pair', worker_sidecar=str(child),
            directories=[str(p) for p in bundles[0]], config=str(self.config_path),
            config_byte_sha256=profiler.digest(self.config_path), config_sha256='config-hash',
            source_hashes={'p': 'hash'}, reviewed_plan_sha256='reviewed',
            worker_launch_monotonic=time.monotonic())
        request.update(action='execute', sidecar=str(sidecar), bundles=[[str(p) for p in bundles[0]]],
            controller_pid=os.getppid(), session_started_monotonic=time.monotonic()-1,
            budgets=profiler.asdict(self.budgets), **profiler.asdict(self.budgets))
        if audits:
            request['audit_approval'] = 'AUDIT-RESOURCE-V1'
        self.approve_fixture(request)
        if fake_supervision:
            seam = patch.object(profiler, 'WorkerSupervision', StubSupervision)
            seam.start()
            self.addCleanup(seam.stop)
        return request, study, evidence, child, references, endpoint_tokens

    def approve_fixture(self, request):
        dynamic = {'kind', 'pair', 'directories', 'worker_sidecar', 'worker_launch_monotonic', 'supervision'}
        approved = {k: v for k, v in request.items() if k not in dynamic}
        profiler.save_json(Path(request['sidecar'])/'request.json',
                           dict(request=approved, budgets=request['budgets']))

    def test_worker_reuses_process_releases_objects_restores_and_separates_passes(self):
        request, study, evidence, child, references, tokens = self.worker_fixture()
        original = evidence.execute_attempt
        profiler.worker(request, loader=lambda: (study, evidence))
        result = profiler.read_json(child/'worker-result.json')
        self.assertTrue(result['success'])
        self.assertEqual(len(result['receipts']), 2)
        self.assertEqual(result['measurements']['execute_attempt']['calls'], 2)
        self.assertEqual(result['measurements_by_phase']['process-cold']['execute_attempt']['calls'], 1)
        self.assertEqual(result['measurements_by_phase']['process-reused']['execute_attempt']['calls'], 1)
        self.assertEqual(sum(p['name'] == 'reconcile' for p in result['separate_passes']), 4)
        self.assertIs(evidence.execute_attempt, original)
        self.assertTrue(all(ref() is None for ref in references))
        self.assertIsNot(tokens[0], tokens[1])
        self.assertFalse((Path(request['directories'][0])/'worker-result.json').exists())
        self.assertIsNone(sys.getprofile())

    def test_worker_failed_second_finalization_reports_only_completed_receipt(self):
        request, study, evidence, child, _, _ = self.worker_fixture(fail_second=True)
        original = evidence.reconcile
        with self.assertRaisesRegex(RuntimeError, 'finalization fault'):
            profiler.worker(request, loader=lambda: (study, evidence))
        result = profiler.read_json(child/'worker-result.json')
        self.assertFalse(result['success'])
        self.assertEqual(len(result['receipts']), 1)
        self.assertTrue((Path(request['directories'][1])/'INCOMPLETE.json').exists())
        self.assertIs(evidence.reconcile, original)
        self.assertIsNone(sys.getprofile())

    def test_stop_request_before_delegation_and_config_drift(self):
        request, study, evidence, child, _, _ = self.worker_fixture()
        (child/'STOP').write_text('fixture stop')
        with self.assertRaises(profiler.StopRequested):
            profiler.worker(request, loader=lambda: (study, evidence))
        self.assertFalse(profiler.read_json(child/'worker-result.json')['success'])
        evidence.execute_attempt.assert_not_called()
        # Failed slots cannot be executed again, even through the internal entry.
        with self.assertRaises(FileExistsError):
            profiler.worker(request, loader=lambda: (study, evidence))

    def test_config_drift_refused_before_execution(self):
        request, study, evidence, child, _, _ = self.worker_fixture()
        self.config_path.write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError, 'configuration drift'):
            profiler.worker(request, loader=lambda: (study, evidence))
        evidence.execute_attempt.assert_not_called()

    def test_worker_refuses_arbitrary_historical_audit_target_before_imports(self):
        request, _, _, _, _, _ = self.worker_fixture()
        request['directories'] = [str(self.root/'week-7')]
        loader = Mock()
        with self.assertRaisesRegex(ValueError, 'targets'):
            profiler.worker(request, loader=loader)
        loader.assert_not_called()

    def test_authorized_audit_only_delegates_once_to_second_new_bundle(self):
        request, study, evidence, child, references, _ = self.worker_fixture(audits=1)
        audit_sidecar = child.parent/'audit-1'
        audit_sidecar.mkdir()
        request.update(kind='audit', audits=1, audit_approval='AUDIT-RESOURCE-V1',
                       worker_sidecar=str(audit_sidecar))
        evidence.audit_evidence = Mock(return_value=dict(status='PASS', arm_attempts=150,
            validation_scope='standalone-audit', validation_passes_completed=1))
        audit = evidence.audit_evidence
        profiler.worker(request, loader=lambda: (study, evidence))
        audit.assert_called_once_with(request['directories'][1])
        self.assertEqual(references, [])
        result = profiler.read_json(audit_sidecar/'worker-result.json')
        self.assertTrue(result['success'])
        self.assertEqual(len(result['receipts']), 1)

    def test_finalization_failure_has_no_success_receipt_and_retains_incomplete(self):
        directory = self.root/'tiny-incomplete'
        directory.mkdir()
        incomplete = directory/'INCOMPLETE.json'
        incomplete.write_text('{}')
        class Run:
            def __init__(self, *args, **kwargs):
                self.closed = False
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                self.closed = True
            def execute(self):
                raise RuntimeError('second reconciliation failed')
        evidence = SimpleNamespace(EvidenceRun=Run)
        request = dict(authorization=profiler.AUTHORIZATION, reviewed_plan_sha256='reviewed')
        with self.assertRaisesRegex(RuntimeError, 'second reconciliation'):
            profiler.run_bundle(evidence, config_stub(), directory, request)
        self.assertTrue(incomplete.exists())
        self.assertFalse((directory/'NONFORMAL_VALIDATED.json').exists())

    def test_incomplete_even_if_delegate_claims_pass(self):
        directory = self.root/'partial'
        directory.mkdir()
        run = Mock()
        run.__enter__ = Mock(return_value=run)
        run.__exit__ = Mock()
        run.execute.return_value = dict(status='PASS', arm_attempts=150, validation_passes_completed=2)
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            profiler.run_bundle(SimpleNamespace(EvidenceRun=lambda *a, **k: run), config_stub(), directory,
                dict(authorization=profiler.AUTHORIZATION, reviewed_plan_sha256='reviewed'))

    def test_session_stops_after_failed_worker_and_never_launches_audits(self):
        self.args.action, self.args.pairs, self.args.runs_per_pair, self.args.audits = 'execute', 3, 2, 3
        self.args.approval, self.args.authorization = profiler.APPROVAL, profiler.AUTHORIZATION
        self.args.audit_approval = 'AUDIT-RESOURCE-V1'
        for key, value in profiler.asdict(self.budgets).items():
            setattr(self.args, key, value)
        checked = profiler.preflight(self.args, loader=stub_modules)
        with patch.object(profiler, 'monitor_worker', return_value=dict(success=False)) as monitor:
            result = profiler.execute(self.args, checked, self.budgets)
        self.assertFalse(result['success'])
        self.assertEqual(monitor.call_count, 1)
        self.assertFalse(profiler.read_json(Path(checked['sidecar'])/'summary.json')['success'])

    def test_final_summary_growth_prohibits_success(self):
        self.args.action = 'execute'
        self.args.approval, self.args.authorization = profiler.APPROVAL, profiler.AUTHORIZATION
        tiny = replace(self.budgets, total_growth_bytes=1)
        for key, value in profiler.asdict(tiny).items():
            setattr(self.args, key, value)
        checked = profiler.preflight(self.args, loader=stub_modules)
        with patch.object(profiler, 'monitor_worker', return_value=dict(success=True)):
            result = profiler.execute(self.args, checked, tiny)
        self.assertFalse(result['success'])
        summary = profiler.read_json(Path(checked['sidecar'])/'summary.json')
        self.assertFalse(summary['success'])
        self.assertIn('aggregate growth at session completion', summary['violations'])

    def test_monitor_terminates_noncooperative_stub_and_preserves_partial_file(self):
        child = self.root/'session'/'pair-1'
        child.mkdir(parents=True)
        evidence = self.root/'tiny-evidence'
        script = "import sys,time,pathlib; sys.stdin.buffer.read(); p=pathlib.Path(sys.argv[1]); p.mkdir(); (p/'INCOMPLETE.json').write_text('{}'); time.sleep(30)"
        processes = []
        def popen(*args, **kwargs):
            process = profiler.launch_python(['-c', script, str(evidence)], **kwargs)
            processes.append(process)
            return process
        class Metrics:
            closed = False
            def __init__(self, pid):
                pass
            def sample(inner):
                return dict(self.sample)
            def close(inner):
                inner.closed = True
        budget = replace(self.budgets, bundle_seconds=.15)
        result = profiler.monitor_worker({}, child, budget, time.monotonic(), [evidence],
                                         popen=popen, metrics_factory=Metrics, supervision_factory=StubController)
        self.assertFalse(result['success'])
        self.assertIn('bundle/audit deadline', result['violations'])
        self.assertIsNotNone(processes[0].poll())
        self.assertTrue((evidence/'INCOMPLETE.json').exists())
        self.assertFalse((evidence/'NONFORMAL_VALIDATED.json').exists())

    def test_containment_failure_cleans_up_gated_process(self):
        child = self.root/'session'/'pair-1'
        child.mkdir(parents=True)
        processes = []
        def popen(*args, **kwargs):
            process = profiler.launch_python(['-c', 'import sys; sys.stdin.buffer.read()'], **kwargs)
            processes.append(process)
            return process
        with patch.object(profiler, 'ProcessTree', side_effect=OSError('containment unavailable')):
            with self.assertRaisesRegex(OSError, 'containment'):
                profiler.monitor_worker({}, child, self.budgets, time.monotonic(), [], popen=popen)
        self.assertIsNotNone(processes[0].poll())

    @unittest.skipUnless(os.name == 'nt', 'Windows process-tree containment')
    def test_windows_job_terminates_descendant_stub(self):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        script = ("import sys,subprocess,time; sys.stdin.buffer.read(); "
                  "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
                  "print(p.pid,flush=True); time.sleep(30)")
        process = profiler.launch_python(['-c', script], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        tree, handle = None, None
        try:
            tree = profiler.ProcessTree(process)
            process.stdin.close()
            pid = int(process.stdout.readline())
            handle = kernel.OpenProcess(0x1000, False, pid)
            self.assertTrue(handle)
            profiler.terminate(process, tree)
            code = wintypes.DWORD(259)
            for _ in range(100):
                kernel.GetExitCodeProcess(handle, ctypes.byref(code))
                if code.value != 259:
                    break
                time.sleep(.01)
            self.assertNotEqual(code.value, 259, 'descendant survived job close')
        finally:
            profiler.terminate(process, tree)
            if handle:
                kernel.CloseHandle(handle)
            process.stdout.close()
            process.stderr.close()

    @unittest.skipUnless(os.name == 'nt', 'Windows OS counters')
    def test_monitor_healthy_stub_exit_with_real_windows_metrics(self):
        child = self.root/'session'/'pair-1'
        child.mkdir(parents=True)
        script = ("import sys,time,pathlib,json; from tools import profile_three_arm_resources_v1 as p; "
                  "r=json.load(sys.stdin)\n"
                  "with p.WorkerSupervision(r) as s:\n"
                  " path=pathlib.Path(r['worker_sidecar'])/'worker-result.json'\n"
                  " path.write_text(json.dumps({'success':True,'pid':__import__('os').getpid(),"
                  "'parent_pid':__import__('os').getppid(),'executable':sys.executable,'prefix':sys.prefix}))\n"
                  " s.finish(path)\n")
        processes = []
        def popen(*args, **kwargs):
            process = profiler.launch_python(['-c', script], **kwargs)
            processes.append(process)
            return process
        request = dict(controller_pid=os.getpid(), worker_sidecar=str(child), budgets=profiler.asdict(self.budgets))
        result = profiler.monitor_worker(request, child, self.budgets, time.monotonic(), [], popen=popen)
        self.assertTrue(result['success'], (result, (child/'stderr.txt').read_text()))
        self.assertTrue(result['supervision_verified'])
        self.assertEqual(result['worker']['pid'], processes[0].pid)
        self.assertEqual(result['worker']['parent_pid'], os.getpid())
        self.assertEqual(result['worker']['executable'], sys.executable)
        self.assertEqual(result['worker']['prefix'], sys.prefix)
        self.assertIsNotNone(result['final_os_counters']['cpu_seconds'])

    @unittest.skipUnless(os.name == 'nt', 'Windows OS counters')
    def test_windows_metrics_on_test_process_only(self):
        metrics = profiler.WindowsMetrics(os.getpid())
        try:
            sample = metrics.sample()
        finally:
            metrics.close()
        self.assertGreater(sample['rss_bytes'], 0)
        self.assertGreaterEqual(sample['os_peak_rss_bytes'], sample['rss_bytes'])
        self.assertGreater(sample['free_ram_bytes'], 0)
        self.assertIsNotNone(sample['logical_io'])

    @unittest.skipUnless(os.name == 'nt', 'Windows interpreter process identity')
    def test_direct_interpreter_launch_preserves_venv_and_native_process_identity(self):
        import ctypes
        from ctypes import wintypes
        script = ("import json,os,sys; print(json.dumps(dict(pid=os.getpid(),parent_pid=os.getppid(),"
                  "executable=sys.executable,prefix=sys.prefix,base_prefix=sys.base_prefix,"
                  "sentinel=os.environ.get('RESOURCE_PROFILER_TEST_VALUE'))),flush=True); sys.stdin.read()")
        environment = dict(os.environ, RESOURCE_PROFILER_TEST_VALUE='preserved')
        original_environment = dict(environment)
        process = profiler.launch_python(['-B', '-c', script], env=environment,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            identity = json.loads(process.stdout.readline())
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetProcessId.argtypes = [wintypes.HANDLE]
            kernel.GetProcessId.restype = wintypes.DWORD
            kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                         wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
            image, size = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
            self.assertTrue(kernel.QueryFullProcessImageNameW(int(process._handle), 0, image, ctypes.byref(size)))
            expected_image = sys._base_executable if sys.prefix != sys.base_prefix else sys.executable
            self.assertEqual(Path(image.value), Path(expected_image))
            self.assertEqual(kernel.GetProcessId(int(process._handle)), identity['pid'])
            self.assertEqual(identity['pid'], process.pid)
            self.assertEqual(identity['parent_pid'], os.getpid())
            self.assertEqual(identity['executable'], sys.executable)
            self.assertEqual(identity['prefix'], sys.prefix)
            self.assertEqual(identity['base_prefix'], sys.base_prefix)
            self.assertEqual(identity['sentinel'], 'preserved')
            self.assertEqual(environment, original_environment)
        finally:
            profiler.terminate(process, None)
            process.stdout.close()
            process.stderr.close()

    def test_unavailable_diagnostic_storage_is_best_effort(self):
        path = self.root/'missing-directory'/'supervision-error.json'
        profiler.diagnostic(path, profiler.error_detail('supervision-lost', OSError('fixture lost pipe')))
        self.assertFalse(path.exists())

    def test_worker_rejects_missing_invalid_and_incomplete_budgets(self):
        request, _, _, child, _, _ = self.worker_fixture()
        for value in (None, {}, dict(profiler.asdict(self.budgets), memory_bytes=None),
                      dict(profiler.asdict(self.budgets), bundle_seconds=float('nan')),
                      dict(profiler.asdict(self.budgets), memory_bytes=True)):
            with self.subTest(budgets=value), self.assertRaises((ValueError, TypeError)):
                profiler.worker(dict(request, budgets=value), loader=Mock(side_effect=AssertionError('import')))
        self.assertFalse((child/'worker-claimed.json').exists())

    def test_worker_rejects_changed_approved_arrangement_and_budget(self):
        request, _, _, child, _, _ = self.worker_fixture()
        changes = [dict(pairs=2), dict(audits=1, audit_approval='AUDIT-RESOURCE-V1'),
                   dict(budgets=dict(request['budgets'], session_seconds=999))]
        for change in changes:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'approved'):
                profiler.worker(dict(request, **change), loader=Mock(side_effect=AssertionError('import')))
        self.assertFalse((child/'worker-claimed.json').exists())

    def test_worker_rejects_controller_identity_and_unapproved_audit_slot(self):
        request, _, _, child, _, _ = self.worker_fixture()
        request['controller_pid'] = -1
        self.approve_fixture(request)
        with self.assertRaisesRegex(ValueError, 'live parent'):
            profiler.worker(request, loader=Mock(side_effect=AssertionError('import')))
        self.assertFalse((child/'worker-claimed.json').exists())

    def test_supervision_loss_at_boundary_restores_bindings_and_prevents_success(self):
        request, study, evidence, child, _, _ = self.worker_fixture()
        original = evidence.execute_attempt
        guard = Mock(wraps=StubSupervision(request))
        guard.check.side_effect = profiler.StopRequested('fixture lost supervisor')
        with self.assertRaises(profiler.StopRequested):
            profiler.supervised_worker(request, child, request['directories'], guard, lambda: (study, evidence))
        evidence.execute_attempt.assert_not_called()
        self.assertIs(evidence.execute_attempt, original)
        self.assertFalse((child/'worker-result.json').exists())

    def test_direct_worker_cli_approval_strings_are_insufficient(self):
        for request in ({}, dict(approval=profiler.APPROVAL, authorization=profiler.AUTHORIZATION)):
            result = subprocess.run([sys.executable, '-B', str(Path(profiler.__file__)), '_worker'],
                input=json.dumps(request), capture_output=True, text=True, cwd=profiler.ROOT)
            self.assertNotEqual(result.returncode, 0)
        # Full budgeted request, approved fixture, correct parent PID; no live pipe/controller.
        request, _, _, child, _, _ = self.worker_fixture(fake_supervision=False)
        request['controller_pid'] = os.getpid()
        self.approve_fixture(request)
        script = ("import json,sys; from pathlib import Path; from tools import profile_three_arm_resources_v1 as p; "
                  "r=json.load(sys.stdin); p.SIDECAR_ROOT=Path(r['sidecar']).parent; "
                  "p.EVIDENCE_ROOT=Path(r['directories'][0]).parent; p.worker(r)")
        result = subprocess.run([sys.executable, '-B', '-c', script], input=json.dumps(request),
                                capture_output=True, text=True, cwd=profiler.ROOT)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((child/'worker-claimed.json').exists())
        self.assertFalse((child/'worker-result.json').exists())
        self.assertFalse((Path(request['sidecar'])/'summary.json').exists())
        self.assertTrue(all(not Path(p).exists() for p in request['directories']))

    def test_inherited_evidence_canonical_bytes_attribution_and_restoration(self):
        study, evidence = stub_modules()
        namespace = dict(canonical=study.canonical)
        exec("def write_json(path, obj):\n    data = canonical(obj) + b'\\n'\n    path.write_bytes(data)\n    return data", namespace)
        # Function globals must be the patched module namespace, just as in the real writer.
        class Module:
            def __getattr__(self, name):
                return namespace[name]
            def __setattr__(self, name, value):
                namespace[name] = value
        evidence.previous = Module()
        namespace.update(source_hashes=Mock(), file_digest=Mock())
        evidence.write_json = namespace['write_json']
        original = namespace['canonical']
        payload = dict(z=2, a='fixture')
        expected = original(payload)+b'\n'
        measurements = profiler.Measurements()
        bindings = [b for b in profiler.instrument_bindings(study, evidence) if b[1] in ('canonical', 'write_json')]
        with profiler.patched(measurements, bindings):
            self.assertEqual(evidence.write_json(self.root/'serialized.json', payload), expected)
            with self.assertRaises(OSError):
                evidence.write_json(self.root/'missing'/'file', payload)
        self.assertEqual((self.root/'serialized.json').read_bytes(), expected)
        self.assertIs(namespace['canonical'], original)
        self.assertEqual(measurements.totals['canonical_evidence_week7']['calls'], 2)
        self.assertNotIn('canonical_week7', measurements.totals)
        self.assertNotIn('canonical_week8', measurements.totals)

    def execution_fixture(self):
        self.args.action = 'execute'
        self.args.approval, self.args.authorization = profiler.APPROVAL, profiler.AUTHORIZATION
        for key, value in profiler.asdict(self.budgets).items():
            setattr(self.args, key, value)
        checked = profiler.preflight(self.args, loader=stub_modules)
        return checked, Path(checked['sidecar'])/'summary.json'

    def test_success_is_published_once_after_all_final_checks(self):
        checked, summary_path = self.execution_fixture()
        transitions = []
        original = Path.replace
        def replace(path, target):
            if target == summary_path:
                transitions.append(profiler.read_json(path)['success'])
            return original(path, target)
        with patch.object(profiler, 'monitor_worker', return_value=dict(success=True)), \
                patch.object(Path, 'replace', replace):
            result = profiler.execute(self.args, checked, self.budgets)
        self.assertTrue(result['success'])
        self.assertEqual(transitions, [False, False, True])
        self.assertEqual(profiler.read_json(summary_path)['state'], 'accepted')

    def test_interruptions_and_filesystem_errors_between_final_checks_never_publish_success(self):
        original_size, original_disk, original_clock = profiler.tree_size, profiler.shutil.disk_usage, time.monotonic
        cases = [('growth', KeyboardInterrupt()), ('growth', OSError('scan failed')),
                 ('disk', KeyboardInterrupt()), ('disk', OSError('disk API failed')),
                 ('deadline', KeyboardInterrupt())]
        for index, (boundary, failure) in enumerate(cases):
            with self.subTest(boundary=boundary, failure=type(failure).__name__):
                self.args.session = f'final-{index}'
                checked, summary_path = self.execution_fixture()
                deadline_armed = [False]
                def size(path):
                    if boundary == 'growth':
                        raise failure
                    return original_size(path)
                def disk(path):
                    if boundary == 'disk':
                        raise failure
                    if boundary == 'deadline':
                        deadline_armed[0] = True
                    return original_disk(path)
                def clock():
                    if deadline_armed[0]:
                        deadline_armed[0] = False
                        raise failure
                    return original_clock()
                with patch.object(profiler, 'monitor_worker', return_value=dict(success=True)), \
                        patch.object(profiler, 'tree_size', side_effect=size), \
                        patch.object(profiler.shutil, 'disk_usage', side_effect=disk), \
                        patch.object(profiler.time, 'monotonic', side_effect=clock), \
                        self.assertRaises(type(failure)):
                    profiler.execute(self.args, checked, self.budgets)
                persisted = profiler.read_json(summary_path)
                self.assertFalse(persisted['success'])
                self.assertEqual(persisted['errors'][-1]['stage'], 'final-acceptance')
                self.assertEqual(persisted['errors'][-1]['type'], type(failure).__name__)

    def test_failed_success_replace_leaves_unsuccessful_receipt(self):
        checked, summary_path = self.execution_fixture()
        original = Path.replace
        def replace(path, target):
            if target == summary_path and profiler.read_json(path)['success']:
                raise OSError('fixture acceptance replace failed')
            return original(path, target)
        with patch.object(profiler, 'monitor_worker', return_value=dict(success=True)), \
                patch.object(Path, 'replace', replace), self.assertRaisesRegex(OSError, 'acceptance replace'):
            profiler.execute(self.args, checked, self.budgets)
        self.assertFalse(profiler.read_json(summary_path)['success'])

    def test_failed_success_staging_leaves_unsuccessful_receipt(self):
        checked, summary_path = self.execution_fixture()
        original = Path.write_text
        def write(path, data, *args, **kwargs):
            if path == summary_path.with_suffix('.json.new') and json.loads(data)['success']:
                raise OSError('fixture staging failed')
            return original(path, data, *args, **kwargs)
        with patch.object(profiler, 'monitor_worker', return_value=dict(success=True)), \
                patch.object(Path, 'write_text', write), self.assertRaisesRegex(OSError, 'staging'):
            profiler.execute(self.args, checked, self.budgets)
        self.assertFalse(profiler.read_json(summary_path)['success'])

    def test_final_deadline_violation_prevents_success(self):
        checked, summary_path = self.execution_fixture()
        original_clock = time.monotonic
        expired = [False]
        def disk(path):
            expired[0] = True
            return SimpleNamespace(free=10000000000)
        def clock():
            return original_clock() + (self.budgets.session_seconds+1 if expired[0] else 0)
        with patch.object(profiler, 'monitor_worker', return_value=dict(success=True)), \
                patch.object(profiler.shutil, 'disk_usage', side_effect=disk), \
                patch.object(profiler.time, 'monotonic', side_effect=clock):
            result = profiler.execute(self.args, checked, self.budgets)
        self.assertFalse(result['success'])
        self.assertIn('session deadline at completion', profiler.read_json(summary_path)['violations'])

    def test_final_disk_violation_preserves_completed_fixture_evidence(self):
        checked, summary_path = self.execution_fixture()
        directory = Path(checked['bundles'][0][0])
        directory.mkdir(parents=True)
        marker = directory/'NONFORMAL_VALIDATED.json'
        marker.write_bytes(b'{"fixture":true}')
        with patch.object(profiler, 'monitor_worker', return_value=dict(success=True)), \
                patch.object(profiler.shutil, 'disk_usage', return_value=SimpleNamespace(free=0)):
            result = profiler.execute(self.args, checked, self.budgets)
        self.assertFalse(result['success'])
        self.assertFalse(profiler.read_json(summary_path)['success'])
        self.assertEqual(marker.read_bytes(), b'{"fixture":true}')

    def test_monitor_exception_and_keyboard_interrupt_are_structured_and_cleanup(self):
        for index, failure in enumerate((OSError('metric unavailable'), KeyboardInterrupt())):
            child = self.root/f'errors-{index}'/'pair-1'
            child.mkdir(parents=True)
            processes = []
            def popen(*args, **kwargs):
                process = profiler.launch_python(['-c', 'import sys,time; sys.stdin.read(); time.sleep(30)'],
                                           **kwargs)
                processes.append(process)
                return process
            class Metrics:
                def __init__(inner, pid):
                    inner.calls = 0
                def sample(inner):
                    inner.calls += 1
                    if inner.calls > 1:
                        raise failure
                    return dict(self.sample)
                def close(inner):
                    pass
            with self.assertRaises(type(failure)):
                profiler.monitor_worker({}, child, self.budgets, time.monotonic(), [], popen=popen,
                    metrics_factory=Metrics, supervision_factory=StubController)
            self.assertIsNotNone(processes[0].poll())
            error = profiler.read_json(child/'controller-error.json')
            self.assertFalse(error['success'])
            self.assertEqual(error['error']['type'], type(failure).__name__)

    def test_session_records_escaping_monitor_error(self):
        checked, summary_path = self.execution_fixture()
        with patch.object(profiler, 'monitor_worker', side_effect=OSError('fixture monitor failed')), \
                self.assertRaises(OSError):
            profiler.execute(self.args, checked, self.budgets)
        summary = profiler.read_json(summary_path)
        self.assertFalse(summary['success'])
        self.assertEqual(summary['errors'][-1]['stage'], 'worker-pair-1')

    @unittest.skipUnless(os.name == 'nt', 'Windows supervised worker integration')
    def test_real_supervised_worker_with_stub_lifecycle_and_slot_reuse_refusal(self):
        request, _, _, child, _, _ = self.worker_fixture(fake_supervision=False)
        request['controller_pid'] = os.getpid()
        self.approve_fixture(request)
        script = "import runpy; runpy.run_path(__import__('sys').argv[1])['run_supervised_stub']()"
        processes = []
        def popen(*args, **kwargs):
            process = profiler.launch_python(['-B', '-c', script, str(Path(__file__).resolve())], **kwargs)
            processes.append(process)
            return process
        result = profiler.monitor_worker(request, child, self.budgets, time.monotonic(),
                                         [Path(p) for p in request['directories']], popen=popen)
        self.assertTrue(result['success'], (result, (child/'stderr.txt').read_text()))
        self.assertTrue(result['supervision_verified'])
        identity = profiler.read_json(child/'supervised-ready.json')
        self.assertEqual(identity['pid'], processes[0].pid)
        self.assertEqual(identity['parent_pid'], os.getpid())
        self.assertEqual(identity['executable'], sys.executable)
        self.assertEqual(identity['prefix'], sys.prefix)
        self.assertEqual(identity['base_prefix'], sys.base_prefix)
        self.assertEqual(len(result['worker']['receipts']), 2)
        # New real supervised process with the same claimed slot must fail before a new run.
        (child/'stdout.txt').rename(child/'first-stdout.txt')
        (child/'stderr.txt').rename(child/'first-stderr.txt')
        result = profiler.monitor_worker(request, child, self.budgets, time.monotonic(), [], popen=popen)
        self.assertFalse(result['success'])
        self.assertIn('worker-claimed.json', (child/'stderr.txt').read_text())

    @unittest.skipUnless(os.name == 'nt', 'Windows job verification')
    def test_worker_rejects_missing_or_unrelated_named_job(self):
        with self.assertRaisesRegex(ValueError, 'job unavailable'):
            profiler.verified_job('Local\\puf-snn-resource-does-not-exist')
        # A real job containing a different sleeping child must not satisfy this process's membership.
        process = profiler.launch_python(['-c', 'import time; time.sleep(30)'])
        tree = profiler.ProcessTree(process)
        try:
            with self.assertRaisesRegex(ValueError, 'not in controller job'):
                profiler.verified_job(tree.name)
        finally:
            profiler.terminate(process, tree)

    @unittest.skipUnless(os.name == 'nt', 'Windows worker handshake refusal')
    def test_containment_verification_and_pipe_peer_failure_prevent_worker_claim(self):
        for index, fault in enumerate(('job', 'peer')):
            with self.subTest(fault=fault):
                # Separate temporary fixture roots keep each request exclusive.
                with patch.multiple(profiler, EVIDENCE_ROOT=self.root/f'evidence-{index}',
                                    SIDECAR_ROOT=self.root/f'sidecars-{index}'):
                    request, _, _, child, _, _ = self.worker_fixture(fake_supervision=False)
                    request['controller_pid'] = os.getpid()
                    self.approve_fixture(request)
                    inject = ("p.verified_job=lambda *a,**k: (_ for _ in ()).throw(ValueError('fixture job refusal')); "
                              if fault == 'job' else "p.pipe_peer_pid=lambda *a,**k: -1; ")
                    script = ("import runpy,sys; from tools import profile_three_arm_resources_v1 as p; "
                              + inject + "runpy.run_path(sys.argv[1])['run_supervised_stub']()")
                    def popen(*args, **kwargs):
                        return profiler.launch_python(['-B', '-c', script, str(Path(__file__).resolve())],
                                                **kwargs)
                    result = profiler.monitor_worker(request, child, self.budgets, time.monotonic(), [], popen=popen)
                    self.assertFalse(result['success'])
                    self.assertFalse((child/'worker-claimed.json').exists())
                    self.assertTrue(all(not Path(p).exists() for p in request['directories']))

    @unittest.skipUnless(os.name == 'nt', 'Windows heartbeat watchdog')
    def test_loss_of_monitor_heartbeats_terminates_worker_without_success(self):
        child = self.root/'lease'/'pair-1'
        child.mkdir(parents=True)
        request = dict(controller_pid=os.getpid(), budgets=profiler.asdict(self.budgets), worker_sidecar=str(child))
        script = ("import json,sys,time,pathlib; from tools import profile_three_arm_resources_v1 as p; r=json.load(sys.stdin)\n"
                   "with p.WorkerSupervision(r) as s:\n"
                   " p.save_json(pathlib.Path(r['worker_sidecar'])/'ready.json', {'pid':__import__('os').getpid()})\n"
                  " time.sleep(30)\n"
                  " pathlib.Path(r['worker_sidecar'],'UNSAFE-CONTINUATION').write_text('bad')\n")
        class StalledController(profiler.ControllerSupervision):
            pulses = 0
            def pulse(inner):
                # Allow handshake, then keep the controller alive while simulating a stalled monitor loop.
                if not inner.verified.is_set() or not (child/'ready.json').exists():
                    super().pulse()
        def popen(*args, **kwargs):
            return profiler.launch_python(['-B', '-c', script], **kwargs)
        result = profiler.monitor_worker(request, child, self.budgets, time.monotonic(), [],
                                         popen=popen, supervision_factory=StalledController)
        self.assertFalse(result['success'])
        self.assertTrue((child/'ready.json').exists(), (result, (child/'stderr.txt').read_text()))
        self.assertEqual(result['exit_code'], 70, result)
        self.assertEqual(result['violations'], [])
        self.assertFalse((child/'UNSAFE-CONTINUATION').exists())
        self.assertFalse((child/'worker-result.json').exists())
        # Emergency termination is mandatory; diagnostic persistence is best effort.
        error_path = child/'supervision-error.json'
        if error_path.exists():
            self.assertEqual(profiler.read_json(error_path)['error']['stage'], 'supervision-lost')

    @unittest.skipUnless(os.name == 'nt', 'Windows pending pipe cleanup')
    def test_unconnected_supervision_listener_is_cleaned_up(self):
        child = self.root/'unconnected'/'pair-1'
        child.mkdir(parents=True)
        before = {t.ident for t in threading.enumerate() if t.name == 'profiler-controller-pipe'}
        def popen(*args, **kwargs):
            return profiler.launch_python(['-c', 'import sys,time; sys.stdin.read(); time.sleep(30)'], **kwargs)
        result = profiler.monitor_worker({}, child, replace(self.budgets, bundle_seconds=.15),
            time.monotonic(), [], popen=popen)
        self.assertFalse(result['success'])
        self.assertEqual({t.ident for t in threading.enumerate() if t.name == 'profiler-controller-pipe'}, before)

    @unittest.skipUnless(os.name == 'nt', 'Windows abrupt controller exit')
    def test_abrupt_controller_exit_kills_verified_worker_and_descendant(self):
        import ctypes
        from ctypes import wintypes
        child = self.root/'controller-exit'/'pair-1'
        child.mkdir(parents=True)
        worker_script = (
            "import json,sys,time,pathlib,subprocess,os; from tools import profile_three_arm_resources_v1 as p; "
            "r=json.load(sys.stdin)\n"
            "with p.WorkerSupervision(r):\n"
            " c=p.launch_python(['-c','import time; time.sleep(30)'])\n"
            " p.save_json(pathlib.Path(r['worker_sidecar'])/'ready.json', "
            "{'pids':[os.getpid(),c.pid], 'controller_pid':r['controller_pid'], 'worker_parent_pid':os.getppid()})\n"
            " time.sleep(30)\n")
        controller_script = (
            "import json,sys,os,time,subprocess,pathlib; from tools import profile_three_arm_resources_v1 as p; "
            "child=pathlib.Path(sys.argv[1]); b=p.Budgets(**json.loads(sys.argv[2])); "
            "r=dict(controller_pid=os.getpid(),budgets=p.asdict(b),worker_sidecar=str(child))\n"
            "def launch(*a,**kw):\n"
            " return p.launch_python(['-B','-c',sys.argv[3]],**kw)\n"
            "p.monitor_worker(r,child,b,time.monotonic(),[],popen=launch)\n")
        controller = profiler.launch_python(['-B', '-c', controller_script, str(child),
            json.dumps(profiler.asdict(self.budgets)), worker_script], cwd=profiler.ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handles = []
        try:
            deadline = time.monotonic()+5
            ready = child/'ready.json'
            while not ready.exists() and controller.poll() is None and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(ready.exists(), (controller.poll(), (child/'stderr.txt').read_text()
                if (child/'stderr.txt').exists() else 'supervised stub did not become ready'))
            identity = profiler.read_json(ready)
            self.assertEqual(identity['controller_pid'], controller.pid)
            self.assertEqual(identity['worker_parent_pid'], controller.pid)
            for pid in identity['pids']:
                handle = kernel.OpenProcess(0x1000 | 0x0001, False, pid)
                self.assertTrue(handle)
                handles.append(handle)
            controller.kill()  # No Python finally/ProcessTree.close runs in this process.
            controller.wait(timeout=5)
            for handle in handles:
                code = wintypes.DWORD(259)
                deadline = time.monotonic()+3
                while code.value == 259 and time.monotonic() < deadline:
                    kernel.GetExitCodeProcess(handle, ctypes.byref(code))
                    time.sleep(.01)
                self.assertNotEqual(code.value, 259, 'worker/descendant survived last controller job handle')
            self.assertFalse((child/'worker-result.json').exists())
        finally:
            if controller.poll() is None:
                controller.kill()
            controller.wait()
            for handle in handles:
                kernel.TerminateProcess(handle, 1)
                kernel.CloseHandle(handle)
            controller.stdout.close()
            controller.stderr.close()


if __name__ == '__main__':
    unittest.main()
