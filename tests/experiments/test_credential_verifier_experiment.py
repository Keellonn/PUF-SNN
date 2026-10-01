"""Synthetic harness tests only; no saved candidate is evaluated here."""
from contextlib import ExitStack
import copy
import io
import unittest
from unittest.mock import patch

from scripts import run_credential_verifier_experiment as runner
from scripts import audit_credential_verifier_experiment as auditor


class EvaluationHarnessTests(unittest.TestCase):
    def fixture(self, wrong=False):
        config=runner.read_json(runner.CONFIG)
        enrollment={'device_id':'synthetic-device','device_index':0,'simulation_seed':0,
            'enrollment_id':'synthetic-enrollment','helper63':'0'*63,'evaluator_enrolled_credential_hex':'000001a5'}
        value=bytes(4) if wrong else bytes.fromhex('000001a5')
        bits=''.join(f'{b:08b}' for b in value)+'0000'
        row=dict(enrollment_id='synthetic-enrollment',device_id='synthetic-device',device_index=0,simulation_seed=0,
            phase='baseline',sweep_index=None,measurement_noise_std=.05,attempt_number=0,
            reconstruction_outcome='candidate_valid_format',decoder_status='decoded',reported_correction_count=0,
            candidate_message36=bits,candidate_credential_hex=value.hex(),padding_valid=True,reconstruction_failure_reason=None,
            evaluator_outcome='evaluator_wrong_match' if wrong else 'evaluator_correct_match')
        return config,{'synthetic-enrollment':enrollment},row

    def test_instrumented_synthetic_pass_and_rejection_no_reconstruction(self):
        for wrong in (False,True):
            config,enrolled,row=self.fixture(wrong)
            with ExitStack() as stack:
                guards=runner.reconstruction_guards(stack)
                service=runner.provision(enrolled,config)
                result=runner.integration(row,1,enrolled,service,config)
            self.assertTrue(result['invariant_passed'])
            self.assertEqual(result['counters']['sender_derive_session_key'],0 if wrong else 1)
            self.assertEqual(result['counters']['receiver_derive_session_key'],0 if wrong else 1)
            self.assertEqual(guards['forbidden_reconstruction_calls'],0)
            self.assertEqual(set(result),runner.INTEGRATION_FIELDS)

    def test_unexpected_derivation_is_counted_even_when_its_error_is_caught(self):
        from puf_snn.auth.credential_verifier import CredentialAdmissionService
        from puf_snn.auth import session
        config,enrolled,row=self.fixture(True); service=runner.provision(enrolled,config)
        actual=CredentialAdmissionService.verify
        def contaminated(*args,**kwargs):
            try: session.derive_session_key(bytes(4),b'invalid-synthetic-transcript')
            except Exception: pass
            return actual(*args,**kwargs)
        with patch.object(CredentialAdmissionService,'verify',new=contaminated):
            result=runner.integration(row,1,enrolled,service,config)
        self.assertFalse(result['invariant_passed'])
        self.assertEqual(result['counters']['common_derive_session_key'],1)

    def test_guard_counts_and_blocks_codec_use(self):
        from puf_snn.reconstruction import reconstruct
        from puf_snn.reconstruction.bch import BCHCodec
        with ExitStack() as stack:
            guards=runner.reconstruction_guards(stack)
            with self.assertRaisesRegex(RuntimeError,'reconstruction_forbidden'): BCHCodec().decode(())
            self.assertEqual(guards['forbidden_reconstruction_calls'],1)

    def test_statistics_retains_outlier_and_interpolates(self):
        s=runner.statistics([1,2,3,1000])
        self.assertEqual(s['n'],4); self.assertEqual(s['max_ns'],1000)
        self.assertEqual(s['median_ns'],2.5); self.assertAlmostEqual(s['p95_ns'],850.45)
        self.assertEqual(runner.statistics([])['mean_ns'],None)

    def test_wilson_finite_sample_uncertainty(self):
        low,high=runner.wilson(430,430)
        self.assertAlmostEqual(low,430/(430+1.959963984540054**2))
        self.assertAlmostEqual(high,1); self.assertGreater(1-low,0)
        low,high=runner.wilson(0,430); self.assertEqual(low,0); self.assertGreater(high,0)

    def test_output_allowlist_rejects_secret_field(self):
        with self.assertRaisesRegex(ValueError,'unsafe_output_fields'):
            runner.emit(io.StringIO(),{'candidate_credential':'synthetic'},runner.ATTEMPT_FIELDS)

    def test_auditor_rejects_skipped_verification_or_composite_tampering(self):
        config,enrolled,row=self.fixture(False)
        row.update(source_id=config['source_id'],reconstruction_latency_ns=100)
        record=dict(runner.locator(row,1),schema_version=config['output_version'],source_id=config['source_id'],
            source_manifest_sha256=config['source_manifest_sha256'],source_artifact_sha256='0'*64,
            reconstruction_outcome=row['reconstruction_outcome'],evaluator_label='correct',verification_invoked=True,
            verification_calls=1,verifier_result='verified',verification_latency_ns=10,admission_result='admitted',
            archived_reconstruction_ns=100,composite_latency_ns=110)
        def audit(r): auditor.audit_attempt(r,row,1,enrolled[row['enrollment_id']],config,'0'*64,runner.ATTEMPT_FIELDS)
        audit(record)
        for field,value in [('verification_calls',0),('composite_latency_ns',109),('source_row_number',2),('evaluator_label','wrong')]:
            changed=dict(record); changed[field]=value
            with self.assertRaises(ValueError): audit(changed)


if __name__=='__main__': unittest.main()
