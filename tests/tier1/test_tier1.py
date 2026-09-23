"""Runner checks and deliberate fault injection; never formal pilot evidence."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/python'))
sys.path.insert(0, str(ROOT / 'src/python/scripts'))
import run_tier1_attacks as t
from jsonschema import Draft202012Validator, ValidationError


def small_config():
    obj = json.loads((ROOT / t.CONFIG).read_text())
    for key in ('trials_per_primary_attack', 'legitimate_control_trials', 'supporting_cross_session_trials'):
        obj[key] = 1
    return obj


class ConfigAndMathTests(unittest.TestCase):
    def test_baseline_all_frozen_files(self):
        self.assertEqual(t.check_baseline()['checked'], 32)

    def test_baseline_mismatch_reports_expected_observed(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'docs').mkdir()
            (root / 'fixture').write_bytes(b'changed')
            (root / t.BASELINE).write_text(json.dumps(dict(baseline='Layer 3 Authentication Baseline v1', wire_protocol='2.0', file_sha256={'fixture': '0'*64})))
            with self.assertRaises(t.BaselineMismatch) as caught:
                t.check_baseline(root)
            self.assertEqual(caught.exception.report['mismatches'], [dict(file='fixture', expected='0'*64, observed=t.digest(b'changed'))])

    def test_baseline_missing_file(self):
        with patch.object(t, 'file_hash', return_value='0'*64):
            with self.assertRaises(t.BaselineMismatch):
                t.check_baseline()

    def test_config_unknown_missing_keys(self):
        for obj in ({**small_config(), 'extra': 1}, {k: v for k, v in small_config().items() if k != 'experiment_seed'}):
            with self.assertRaises(ValueError):
                t.Config.from_dict(obj)

    def test_config_strict_types_ranges(self):
        for key, values in [('trials_per_primary_attack', [True, 1.0, 0, -1, 10001]), ('experiment_seed', [False, -1, 2**64]), ('warmup_count', [True, 0, 19])]:
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    t.Config.from_dict({**small_config(), key: value})

    def test_config_wrong_constants_attacks(self):
        for key, value in [('protocol_profile', 'wrong'), ('primary_metadata_field', 'window_id'), ('expected_attack_names', list(reversed(t.PRIMARY)))]:
            with self.assertRaises(ValueError):
                t.Config.from_dict({**small_config(), key: value})

    def test_duplicate_config_keys(self):
        with self.assertRaises(ValueError):
            t.strict_json('{"a":1,"a":2}')

    def test_plan_deterministic_counts_and_order(self):
        config = t.Config.load(ROOT / t.CONFIG)
        plan = t.plan_trials(config)
        self.assertEqual(plan, t.plan_trials(config))
        self.assertEqual(len(plan), 700)
        self.assertEqual([p['attack_type'] for p in plan[:7]], [t.CONTROL, *t.PRIMARY, t.SUPPORT])
        self.assertEqual([p['trial_index'] for p in plan], list(range(700)))
        self.assertEqual(len({p['trial_id'] for p in plan}), 700)

    def test_plan_seed_changes_motion_not_order(self):
        config = t.Config.from_dict(small_config())
        a = t.plan_trials(config)
        b = t.plan_trials(t.replace(config, experiment_seed=config.experiment_seed+1))
        self.assertEqual([p['attack_type'] for p in a], [p['attack_type'] for p in b])
        self.assertNotEqual([p['motion_seed'] for p in a], [p['motion_seed'] for p in b])

    def test_reason_precedence(self):
        self.assertEqual(t.expected('same_session_replay'), ('reject', 'duplicate_sequence', 'pass', 'duplicate'))
        self.assertEqual(t.expected('prior_session_replay'), ('reject', 'inactive_session', 'not_checked', 'not_checked'))
        for kind in (*t.PRIMARY[2:], t.SUPPORT):
            self.assertEqual(t.expected(kind), ('reject', 'invalid_tag', 'fail', 'not_checked'))

    def test_p95_linear_and_outlier(self):
        result = t.summarize_ns([0, 10, 20, 1000])
        self.assertEqual(result['p95'], 853)
        self.assertEqual(result['maximum'], 1000)
        self.assertEqual(result['median'], 15)
        self.assertEqual(result['mean'], 257.5)

    def test_empty_latency(self):
        self.assertEqual(t.summarize_ns([]), dict(count=0, mean=None, median=None, p95=None, maximum=None))

    def test_wilson_all_success(self):
        lo, hi = t.wilson(100, 100)
        self.assertAlmostEqual(lo, 0.9630065017930143)
        self.assertAlmostEqual(hi, 1.0)

    def test_wilson_half_and_none(self):
        lo, hi = t.wilson(50, 100)
        self.assertAlmostEqual(lo, 0.4038315303659956)
        self.assertAlmostEqual(hi, 0.5961684696340044)
        self.assertEqual(t.wilson(0, 0), (None, None))
        self.assertAlmostEqual(t.wilson(0, 100)[1], 0.03699349820698568)

    def test_wilson_invalid(self):
        for successes, n in ((2, 1), (-1, 1), (1, 0), (True, 1)):
            with self.assertRaises(ValueError):
                t.wilson(successes, n)


class TrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = t.Config.from_dict(small_config())
        cls.plan = t.plan_trials(cls.config)
        cls.context = dict(run_id='unit-test-only', config_sha256='1'*64,
                           baseline_manifest_sha256='2'*64, source_hashes={'runner': '3'*64},
                           experiment_seed=cls.config.experiment_seed, temperature='warm')
        cls.rows, cls.setup, cls.audits, cls.sender_audits = [], [], [], []
        def emit(group, row):
            (cls.rows if group == 'formal' else cls.setup).append(row)
        def flush(v, senders):
            cls.audits.extend(v.audit_records)
            cls.sender_audits.extend(r for s in senders for r in s.audit_records)
        for spec in cls.plan:
            t.execute_trial(spec, cls.config, t.AuthConfig(), cls.context, emit, flush)
        cls.schema = Draft202012Validator(json.loads((ROOT / t.SCHEMA).read_text()))

    def row(self, kind):
        return next(r for r in self.rows if r['attack_type'] == kind)

    def test_legitimate_accept_and_exact_release(self):
        r = self.row(t.CONTROL)
        self.assertEqual((r['actual_decision'], r['actual_reason']), ('accept', 'accepted'))
        self.assertTrue(r['exact_payload_release'])
        self.assertEqual((r['accepted_count_before'], r['accepted_count_after']), (0, 1))
        self.assertEqual((r['last_accepted_before'], r['last_accepted_after']), (None, 0))
        self.assertEqual(r['total_layer3_ns'], r['sender_prepare_ns'] + r['verifier_auth_ns'])

    def test_replay_complete_bytes_identical(self):
        r = self.row('same_session_replay')
        self.assertEqual(r['original_envelope_b64'], r['submitted_envelope_b64'])
        self.assertEqual(r['original_authenticated_bytes_sha256'], r['mutated_authenticated_bytes_sha256'])
        self.assertEqual(r['actual_reason'], 'duplicate_sequence')
        self.assertEqual(r['authentication_result'], 'pass')
        self.assertEqual(r['accepted_count_before'], 1)

    def test_prior_session_replaced_fixture(self):
        r = self.row('prior_session_replay')
        self.assertEqual(r['original_envelope_b64'], r['submitted_envelope_b64'])
        self.assertEqual(r['actual_reason'], 'inactive_session')
        self.assertEqual(r['lifecycle_terminal_state'], 'CLOSED')
        self.assertEqual(r['lifecycle_terminal_reason'], 'session_replaced')
        self.assertIsNone(r['accepted_count_before'])
        self.assertIsNone(r['last_accepted_before'])
        self.assertEqual(t.state_entry(r['state_before'], r['target_session_id'])['state'], 'ACTIVE')

    def test_cross_device_exact_identity_only(self):
        r = self.row('cross_device_substitution')
        a = t.parse_envelope(base64.b64decode(r['original_envelope_b64']))
        b = t.parse_envelope(base64.b64decode(r['submitted_envelope_b64']))
        self.assertEqual(b.window, t.replace(a.window, device_id='sim-tier1-B'))
        self.assertEqual(b.tag, a.tag)
        self.assertEqual(b.key_id, a.key_id)
        self.assertEqual(len(r['state_before']['sessions']), 2)

    def test_cross_session_substitution_known_target(self):
        r = self.row(t.SUPPORT)
        a = t.parse_envelope(base64.b64decode(r['original_envelope_b64']))
        b = t.parse_envelope(base64.b64decode(r['submitted_envelope_b64']))
        self.assertEqual(b.window, t.replace(a.window, session_id=bytes.fromhex(r['target_session_id'])))
        self.assertEqual(b.key_id, r['target_session_id'])
        self.assertEqual(b.tag, a.tag)
        self.assertFalse(r['is_primary'])

    def test_payload_bit_exactness(self):
        r = self.row('payload_modification')
        m = r['mutation']
        self.assertEqual(int(m['before_hex'], 16) ^ int(m['after_hex'], 16), 1 << m['bit'])
        a = t.parse_envelope(base64.b64decode(r['original_envelope_b64']))
        b = t.parse_envelope(base64.b64decode(r['submitted_envelope_b64']))
        differences = [(i, j) for i in range(120) for j in range(3) if a.window.samples[i].position_m[j] != b.window.samples[i].position_m[j]]
        self.assertEqual(differences, [(m['sample_index'], m['component'])])
        t.validate_quality(b.window)

    def test_metadata_exact_sequence_only(self):
        r = self.row('metadata_modification')
        a = t.parse_envelope(base64.b64decode(r['original_envelope_b64']))
        b = t.parse_envelope(base64.b64decode(r['submitted_envelope_b64']))
        self.assertEqual(b.window, t.replace(a.window, sequence_number=1))
        self.assertEqual(b.tag, a.tag)

    def test_one_field_only_and_original_tag_for_all_mutations(self):
        for r in self.rows:
            if r['mutation']['byte_offset'] is None:
                continue
            a = t.parse_envelope(base64.b64decode(r['original_envelope_b64']))
            b = t.parse_envelope(base64.b64decode(r['submitted_envelope_b64']))
            offset = r['mutation']['byte_offset']
            width = len(bytes.fromhex(r['mutation']['before_hex']))
            self.assertEqual(a.authenticated_bytes[:offset], b.authenticated_bytes[:offset])
            self.assertEqual(a.authenticated_bytes[offset+width:], b.authenticated_bytes[offset+width:])
            self.assertEqual(a.tag, b.tag)

    def test_attack_state_unchanged_and_no_inference(self):
        for r in self.rows[1:]:
            self.assertEqual(r['state_before'], r['state_after'])
            self.assertFalse(r['unexpected_behavior'])
            self.assertFalse(r['payload_reached_inference'])
            self.assertIsNone(r['sender_prepare_ns'])
            self.assertIsNone(r['total_layer3_ns'])

    def test_release_attempted_for_every_rejection(self):
        for r in self.rows[1:]:
            self.assertTrue(r['payload_release_attempted'])
            self.assertFalse(r['payload_released'])
            self.assertEqual(r['release_callback_count'], 0)
            self.assertEqual(r['release_error'], 'acceptance_required')

    def test_raw_schema_all_records(self):
        Draft202012Validator.check_schema(self.schema.schema)
        for row in self.rows + self.setup:
            self.schema.validate(row)

    def test_raw_schema_rejects_unknown_missing_wrong_type(self):
        for mutation in ('extra', 'missing', 'type'):
            row = deepcopy(self.rows[0])
            if mutation == 'extra': row['credential'] = 'forbidden'
            if mutation == 'missing': del row['trial_id']
            if mutation == 'type': row['trial_index'] = True
            with self.assertRaises(ValidationError):
                self.schema.validate(row)

    def test_no_secret_fields_in_any_records(self):
        forbidden = {'credential', 'credential4', 'candidate_credential', 'candidate_message', 'session_key', 'key', 'prk', 'helper', 'helper_data', 'reference', 'noisy64'}
        def inspect(obj):
            if isinstance(obj, dict):
                self.assertFalse(set(k.lower() for k in obj) & forbidden)
                for value in obj.values(): inspect(value)
            elif isinstance(obj, (list, tuple)):
                for value in obj: inspect(value)
        inspect([self.rows, self.setup, self.audits, self.sender_audits])

    def test_aggregation_denominators(self):
        summaries = t.aggregate(self.rows)
        self.assertEqual(sum(r['attempts'] for r in summaries['attack_summary.csv']), 5)
        self.assertEqual(summaries['supporting_summary.csv'][0]['attempts'], 1)
        self.assertEqual(summaries['control_summary.csv'][0]['accepted'], 1)
        self.assertEqual(sum(r['count'] for r in summaries['reason_summary.csv']), 7)

    def test_reconciliation(self):
        result = t.reconcile(self.rows, self.setup, self.audits, self.plan, t.aggregate(self.rows))
        self.assertTrue(result['passed'])
        self.assertEqual(result['matched_window_audits'], 15)

    def test_reconciliation_missing_trial(self):
        with self.assertRaises(ValueError):
            t.reconcile(self.rows[:-1], self.setup, self.audits, self.plan, t.aggregate(self.rows[:-1]))

    def test_reconciliation_wrong_summary(self):
        summaries = t.aggregate(self.rows)
        summaries['attack_summary.csv'][0]['attempts'] += 1
        with self.assertRaises(ValueError):
            t.reconcile(self.rows, self.setup, self.audits, self.plan, summaries)

    def test_reconciliation_missing_audit(self):
        with self.assertRaises(ValueError):
            t.reconcile(self.rows, self.setup, [r for r in self.audits if r['event_type'] != 'window'], self.plan, t.aggregate(self.rows))

    def test_reconciliation_duplicate_ids(self):
        rows = deepcopy(self.rows)
        rows[-1]['trial_id'] = rows[0]['trial_id']
        with self.assertRaises(ValueError):
            t.reconcile(rows, self.setup, self.audits, self.plan, t.aggregate(rows))

    def test_reconciliation_audit_reason_mismatch(self):
        audits = deepcopy(self.audits)
        next(r for r in audits if r['event_type'] == 'window')['reason'] = 'invalid_tag'
        with self.assertRaises(ValueError):
            t.reconcile(self.rows, self.setup, audits, self.plan, t.aggregate(self.rows))

    def test_reconciliation_missing_session_audit(self):
        audits = [r for r in self.audits if r['event_type'] != 'session_control']
        with self.assertRaises(ValueError):
            t.reconcile(self.rows, self.setup, audits, self.plan, t.aggregate(self.rows))

    def test_state_detector_catches_deadline_change(self):
        spec = self.plan[1]
        saved = t.snapshot
        calls = 0
        def changed(v, ids):
            nonlocal calls
            calls += 1
            result = saved(v, ids)
            # Two setup snapshots, then attack before and after.
            if calls == 4:
                result['sessions'][0]['deadline_ns'] += 1
            return result
        captured = []
        with patch.object(t, 'snapshot', side_effect=changed):
            t.execute_trial(spec, self.config, t.AuthConfig(), self.context,
                            lambda group, row: captured.append(row), lambda v, s: None)
        self.assertTrue(captured[-1]['state_mutation_violation'])
        self.assertIn('state', captured[-1]['invariant_violations'])

    def test_release_detector_catches_rejected_callback(self):
        saved = t.Verifier.release_accepted
        def faulty(v, result, consumer):
            if result.result == 'reject':
                consumer(None)  # Fault injection only; formal runner has no patches.
                return None
            return saved(v, result, consumer)
        captured = []
        with patch.object(t.Verifier, 'release_accepted', new=faulty):
            t.execute_trial(self.plan[1], self.config, t.AuthConfig(), self.context,
                            lambda group, row: captured.append(row), lambda v, s: None)
        self.assertTrue(captured[-1]['payload_release_violation'])
        self.assertEqual(captured[-1]['release_callback_count'], 1)

    def test_attacker_function_has_no_secret_arguments(self):
        import inspect
        self.assertEqual(list(inspect.signature(t.mutate_envelope).parameters),
                         ['envelope_bytes', 'spec', 'target_device', 'target_session'])
        source = inspect.getsource(t.mutate_envelope)
        self.assertNotIn('window_tag(', source)
        self.assertNotIn('._key', source)

    def test_aggregation_keeps_unexpected_accept(self):
        rows = deepcopy(self.rows)
        rows[1].update(actual_decision='accept', actual_reason='accepted', state_mutation_violation=True,
                       payload_release_violation=True, unexpected_behavior=True)
        s = t.aggregate(rows)['attack_summary.csv'][0]
        self.assertEqual((s['unexpected_accepts'], s['unexpected_reason_count'], s['state_mutation_violations'], s['payload_release_violations']), (1, 1, 1, 1))


class RunLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.config_path = self.parent / 'test-config.json'
        self.config_path.write_text(json.dumps(small_config()))
        self.output = self.parent / 'unit-test-run'

    def run_small(self):
        return t.run_experiment(self.output, self.config_path, execution_command='unit-test-only')

    def test_complete_manifest_artifact_hashes(self):
        self.run_small()
        self.assertTrue((self.output / 'COMPLETE').is_file())
        self.assertFalse((self.output / 'INCOMPLETE.json').exists())
        manifest = json.loads((self.output / 'manifest.json').read_text())
        for name, digest in manifest['files'].items():
            self.assertEqual(t.file_hash(self.output / name), digest)
        self.assertEqual(manifest['reconciliation']['formal_rows'], 7)
        self.assertEqual(len(t.read_jsonl(self.output / 'warmup_attempts.jsonl')), 20)
        self.assertEqual(json.loads((self.output / 'baseline-before.json').read_text()), json.loads((self.output / 'baseline-after.json').read_text()))

    def test_no_overwrite_existing_directory(self):
        self.output.mkdir()
        (self.output / 'marker').write_text('preserve')
        with self.assertRaises(FileExistsError): self.run_small()
        self.assertEqual(list(self.output.iterdir()), [self.output / 'marker'])

    def test_pre_baseline_mismatch_no_execution(self):
        with patch.object(t, 'check_baseline', side_effect=t.BaselineMismatch({'mismatches': []})), patch.object(t, 'execute_trial') as execute:
            with self.assertRaises(t.BaselineMismatch): self.run_small()
        execute.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_post_baseline_mismatch_incomplete_preserves_all_trials(self):
        before = t.check_baseline()
        with patch.object(t, 'check_baseline', side_effect=[before, t.BaselineMismatch({'mismatches': [{'file': 'test-only'}]})]):
            with self.assertRaises(t.BaselineMismatch): self.run_small()
        self.assertTrue((self.output / 'INCOMPLETE.json').exists())
        self.assertFalse((self.output / 'COMPLETE').exists())
        self.assertEqual(len(t.read_jsonl(self.output / 'attempts.jsonl')), 7)

    def test_reconciliation_failure_incomplete(self):
        with patch.object(t, 'reconcile', side_effect=ValueError('test-only')):
            with self.assertRaises(ValueError): self.run_small()
        self.assertTrue((self.output / 'INCOMPLETE.json').exists())
        self.assertFalse((self.output / 'manifest.json').exists())

    def test_write_failure_incomplete(self):
        original = t.write_json
        def fail(path, value):
            if Path(path).name == 'metadata.json': raise OSError('test-only')
            return original(path, value)
        with patch.object(t, 'write_json', side_effect=fail):
            with self.assertRaises(OSError): self.run_small()
        self.assertTrue((self.output / 'INCOMPLETE.json').exists())
        self.assertFalse((self.output / 'COMPLETE').exists())
        self.assertEqual(len(t.read_jsonl(self.output / 'attempts.jsonl')), 7)

    def test_audit_failure_incomplete(self):
        with patch.object(t.AuditJSONL, 'flush', side_effect=OSError('test-only')):
            with self.assertRaises(OSError): self.run_small()
        self.assertTrue((self.output / 'INCOMPLETE.json').exists())
        self.assertFalse((self.output / 'COMPLETE').exists())

    def test_anomaly_preserved_and_run_flagged(self):
        original = t.observe
        def anomaly(*args, **kwargs):
            row = original(*args, **kwargs)
            if row['attack_type'] == 'payload_modification':
                row.update(state_mutation_violation=True, unexpected_behavior=True, invariant_violations=['state'])
            return row
        with patch.object(t, 'observe', side_effect=anomaly): self.run_small()
        rows = t.read_jsonl(self.output / 'attempts.jsonl')
        self.assertTrue(next(r for r in rows if r['attack_type'] == 'payload_modification')['unexpected_behavior'])
        self.assertTrue(json.loads((self.output / 'COMPLETE').read_text())['unexpected_behavior'])


if __name__ == '__main__':
    unittest.main()
