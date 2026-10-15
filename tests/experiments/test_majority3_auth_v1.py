"""Small deterministic developer fixtures, never statistical research evidence."""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import io
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from puf_snn import pipeline_v2
from puf_snn.auth.credential_verifier import CredentialAdmissionService
from puf_snn.auth.sender import Sender
from puf_snn.auth.verifier import Verifier
from puf_snn.puf.device import Device
from puf_snn.reconstruction import BCHCodec, enroll
from puf_snn.experiments import majority3_auth_v1 as study
from puf_snn.experiments import majority3_auth_runtime_v1 as runtime
from puf_snn.experiments import majority3_auth_evidence_v1 as evidence
from puf_snn.experiments import majority3_auth_analysis_v1 as analysis
from puf_snn.experiments import correlated_noise_v1 as noise


def fixture_config(**changes):
    obj = study.StudyConfig.load().to_dict()
    obj.update(mode="unit-test", allocation=dict(populations=1,devices_per_population=1,attempts_per_device_condition=2))
    obj.update(changes)
    return study.StudyConfig.from_dict(obj)


def trial_for(plan, condition="independent_nominal", attempt=0):
    return next(t for t in plan["blocks"] if t["condition"] == condition and t["attempt_index"] == attempt)


def execute(config, plan, trial, policy, enrollment, index=0):
    return runtime.execute_attempt(config, trial, policy, enrollment, run_id="unit-fixture",
                                   source_id="0"*64, plan_sha256=plan["plan_sha256"], execution_index=index)


class PlannerTests(unittest.TestCase):
    def test_formal_counts_balancing_and_unique_identities_without_execution(self):
        config = study.StudyConfig.load()
        with patch.object(runtime, "execute_attempt", side_effect=AssertionError("no execution")):
            plan = study.compile_plan(config)
        self.assertEqual(plan["counts"], dict(matched_trials=30000,policy_attempts=60000,expected_reads=120000))
        self.assertEqual(len({b["trial_id"] for b in plan["blocks"]}), 30000)
        self.assertEqual(len({study.attempt_id(t,p) for t,p,_ in study.scheduled_attempts(plan)}),60000)
        orders = Counter((t["device_id"],t["condition"],t["policy_order"][0]) for t in plan["blocks"])
        self.assertEqual(set(orders.values()), {25})

    def test_deterministic_plan_and_indexed_streams(self):
        config = fixture_config()
        first, second = study.compile_plan(config), study.compile_plan(config)
        self.assertEqual(first, second)
        study.validate_plan(config, first)
        for trial in first["blocks"]:
            self.assertEqual(len(set(trial["reading_seed_sha256"])),3)
            self.assertNotIn(trial["session_seed_sha256"], trial["reading_seed_sha256"])
        self.assertEqual([n for _,_,n in study.scheduled_attempts(first)],list(range(20)))

    def test_common_mode_aliases_all_noise_inputs(self):
        plan = study.compile_plan(fixture_config())
        for i in range(2):
            a,b = trial_for(plan,attempt=i), trial_for(plan,"common_control",i)
            for key in ("noise_identity","reading_seed_sha256","session_seed_sha256","sigma","rho"):
                self.assertEqual(a[key],b[key])
            self.assertEqual(a["common_offset"],0)
            self.assertIn(b["common_offset"],(-1,1))
            self.assertNotEqual(a["trial_id"],b["trial_id"])

    def test_config_changes_are_recorded_in_trial_identity(self):
        a,b = fixture_config(),fixture_config(manufacturing_std=2)
        self.assertNotEqual(a.digest,b.digest)
        self.assertNotEqual(trial_for(study.compile_plan(a))["trial_id"],trial_for(study.compile_plan(b))["trial_id"])
        detached = a.to_dict()
        detached["manufacturing_std"] = 7
        self.assertEqual(a.to_dict()["manufacturing_std"],1)

    def test_strict_configuration_rejects_unknown_missing_and_invalid_fields(self):
        original = fixture_config().to_dict()
        for key in original:
            obj = deepcopy(original)
            del obj[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                study.StudyConfig.from_dict(obj)
        for change in ({"extra":1},{"master_seed":True},{"master_seed":-1},{"experiment_id":"week6"},
                       {"noise_model_id":"unknown"},{"policies":["majority-5-v1"]},
                       {"bootstrap_resamples":9999},{"confidence_level":.9},{"interval_scope":"simultaneous"},
                       {"primary_rho":.5},{"manufacturing_std":float("nan")},{"conditions":[]}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                study.StudyConfig.from_dict(dict(original,**change))
        with self.assertRaisesRegex(ValueError,"duplicate"):
            study.StudyConfig('{"a":1,"a":2}')

    def test_allocation_and_condition_changes_rejected(self):
        obj = fixture_config().to_dict()
        for count in (0,1,3,True,2.0,50):
            changed=deepcopy(obj)
            changed["allocation"]["attempts_per_device_condition"]=count
            with self.assertRaises(ValueError): study.StudyConfig.from_dict(changed)
        for field,value in (("sigma",.2),("rho",.8),("common_offsets",[2])):
            changed=deepcopy(obj)
            changed["conditions"][0][field]=value
            with self.assertRaises(ValueError): study.StudyConfig.from_dict(changed)

    def test_schema_validation_and_tampered_plan(self):
        config=fixture_config()
        plan=study.compile_plan(config)
        for name in ("config","plan","attempt","summary"):
            schema=study.read_json_bytes((study.ROOT/f"schemas/majority3-auth-{name}-v1.schema.json").read_bytes())
            study.Draft202012Validator.check_schema(schema)
        plan["blocks"][0]["policy_order"].reverse()
        with self.assertRaises(ValueError): study.validate_plan(config,plan)

    def test_cli_read_only_and_formal_execution_absent(self):
        from scripts.run_majority3_auth_correlated import main
        with patch.object(evidence.EvidenceRun,"execute",side_effect=AssertionError("no execution")), \
             patch("sys.stdout",new_callable=io.StringIO) as output:
            self.assertEqual(main(["validate"]),0)
        self.assertEqual(json.loads(output.getvalue())["executed_attempts"],0)
        with patch("sys.stderr",new_callable=io.StringIO),self.assertRaises(SystemExit):
            main(["run-formal"])


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=fixture_config()
        cls.plan=study.compile_plan(cls.config)
        cls.trial=trial_for(cls.plan)
        cls.enrollment=study.prepare_enrollment(cls.config,cls.trial["population_id"],cls.trial["device_id"])

    def controlled(self, response=(0,)*64):
        # Deliberately constructed public fault fixtures; still actual oscillator
        # measurements, real BCH and normal independent admission, never a fake
        # accepted ReconstructionResult. Not used as research-plan evidence.
        offsets=tuple(v for bit in response for v in ((16.,-16.) if bit else (-16.,16.)))
        return replace(self.enrollment,device=Device(self.trial["device_id"],offsets),reference=(0,)*64,
                       helper=enroll((0,)*64,self.enrollment.credential,enrollment_id=self.trial["enrollment_id"]))

    def run_control(self, kind, policy="majority-3-v1"):
        enrollment=self.controlled()
        helper=enrollment.helper
        if kind == "C": response=(0,)*64
        else:
            if kind == "D": word=(1,)*6+(0,)*57
            elif kind == "I": word=BCHCodec().encode((0,)*35+(1,))
            else:
                wrong=bytes(v ^ 0xff for v in enrollment.credential)
                word=enroll((0,)*64,wrong,enrollment_id=helper.enrollment_id).helper_bits
            response=tuple(a ^ b for a,b in zip(helper.helper_bits,word))+(0,)
            enrollment=self.controlled(response)
        row=execute(self.config,self.plan,self.trial,policy,enrollment)
        study.validate_schema("attempt",row)
        self.assertEqual(row["execution_status"],"completed")
        self.assertEqual(row["reconstruction"]["classification"],kind)
        runtime_count=Counter(s["stage"] for s in row["timing"])
        self.assertEqual(runtime_count["reconstruction"],1)
        self.assertEqual(runtime_count["bch_decode"],1)
        evidence.validate_timing(row)
        evidence.validate_protocol(row)
        return row

    def test_correct_real_reconstruction_mutual_handshake_and_window_release(self):
        for policy,count in (("single-read-v1",1),("majority-3-v1",3)):
            row=self.run_control("C",policy)
            self.assertEqual(row["actual_reads"],count)
            self.assertEqual(row["verification_outcomes"],["verified"])
            self.assertEqual(row["authorization_outcomes"],[True])
            self.assertTrue(row["establishment"]["session_active"])
            self.assertEqual([h["result"] for h in row["handshake"]],["accept"]*4)
            self.assertEqual(row["window"],dict(stage="window_verification",decision="accept",reason="accepted",sequence_number=0))
            self.assertEqual((row["release_count"],row["unauthorized_release_count"]),(1,0))

    def test_real_decoder_failure_and_conditional_stages(self):
        row=self.run_control("D")
        self.assertEqual(row["verification_outcomes"],[])
        self.assertEqual(row["authorization_outcomes"],[])
        self.assertEqual(row["handshake"],[])
        self.assertIsNone(row["window"])
        self.assertEqual(row["release_count"],0)
        self.assertNotIn("verification",[s["stage"] for s in row["timing"]])

    def test_real_invalid_padding(self):
        row=self.run_control("I")
        self.assertEqual(row["reconstruction"]["outcome"],"invalid_format_or_padding")
        self.assertFalse(row["establishment"]["request_emitted"])
        self.assertEqual(row["release_count"],0)

    def test_real_wrong_valid_format_credential_refused_before_hkdf(self):
        row=self.run_control("W")
        self.assertEqual(row["verification_outcomes"],["credential_mismatch"])
        self.assertEqual(row["authorization_outcomes"],[False])
        self.assertFalse(row["establishment"]["request_emitted"])
        self.assertEqual(row["release_count"],0)
        self.assertFalse(any(s["stage"].endswith("hkdf") for s in row["timing"]))

    def test_local_authorization_consume_is_enforced(self):
        with patch.object(CredentialAdmissionService,"consume",return_value=False):
            row=execute(self.config,self.plan,self.trial,"single-read-v1",self.controlled())
        self.assertEqual(row["reconstruction"]["classification"],"C")
        self.assertFalse(row["establishment"]["session_active"])
        self.assertEqual(row["release_count"],0)
        self.assertIsNone(row["window"])
        self.assertFalse(any(s["stage"].endswith("hkdf") for s in row["timing"]))

    def test_rejected_protected_window_cannot_release(self):
        original=Verifier.verify_window
        def tamper(owner,packet,*args,**kwargs):
            obj=json.loads(packet)
            tag=obj["authentication"]["tag_hex"]
            obj["authentication"]["tag_hex"]=("0" if tag[0] != "0" else "1")+tag[1:]
            return original(owner,study.canonical(obj),*args,**kwargs)
        with patch.object(Verifier,"verify_window",tamper):
            row=execute(self.config,self.plan,self.trial,"majority-3-v1",self.controlled())
        self.assertTrue(row["establishment"]["session_active"])
        self.assertEqual(row["window"]["reason"],"invalid_tag")
        self.assertEqual(row["release_count"],0)
        self.assertEqual(row["execution_status"],"completed")

    def test_real_timeout_remains_separate_from_reconstruction_failure(self):
        now=[1_000_000_000]
        original=Verifier.begin_session
        def delayed(owner,*args,**kwargs):
            result=original(owner,*args,**kwargs)
            now[0]+=11_000_000_000
            return result
        with patch("puf_snn.auth.session.time.monotonic_ns",side_effect=lambda:now[0]), \
             patch.object(Verifier,"begin_session",delayed):
            row=execute(self.config,self.plan,self.trial,"single-read-v1",self.controlled())
        self.assertEqual(row["execution_status"],"completed")
        self.assertEqual(row["reconstruction"]["classification"],"C")
        self.assertFalse(row["establishment"]["session_active"])
        self.assertNotEqual(row["establishment"]["reason"],"failed_reconstruction")
        self.assertEqual(row["release_count"],0)

    def test_policy_order_matching_and_fresh_runtime_state(self):
        created=[]
        original=runtime.fresh_pipeline
        def observe(*args):
            result=original(*args)
            created.append(result[0])
            return result
        outputs=[]
        with patch.object(runtime,"fresh_pipeline",side_effect=observe):
            for order in (list(study.POLICIES),list(reversed(study.POLICIES))):
                outputs.append({p:execute(self.config,self.plan,self.trial,p,self.enrollment) for p in order})
        self.assertEqual(len({id(p.sender) for p in created}),4)
        self.assertEqual(len({id(p.verifier) for p in created}),4)
        self.assertEqual(len({id(p.sender._admission_service) for p in created}),4)
        self.assertTrue(all(p.sender.enrollment.helper_data is self.enrollment.helper for p in created))
        for policy in study.POLICIES:
            self.assertEqual(outputs[0][policy]["observations"],outputs[1][policy]["observations"])
        b0,m3=(outputs[0][p] for p in study.POLICIES)
        self.assertEqual(b0["observations"][0],m3["observations"][0])
        self.assertEqual(b0["enrollment_sha256"],m3["enrollment_sha256"])
        self.assertEqual(b0["session_seed_sha256"],m3["session_seed_sha256"])

    def test_window_expiry_does_not_reclassify_successful_establishment(self):
        now=[1_000_000_000]
        original=Sender.seal_window
        def expired(owner,*args,**kwargs):
            now[0]+=301_000_000_000
            return original(owner,*args,**kwargs)
        with patch("puf_snn.auth.session.time.monotonic_ns",side_effect=lambda:now[0]), \
             patch.object(Sender,"seal_window",expired):
            row=execute(self.config,self.plan,self.trial,"single-read-v1",self.controlled())
        self.assertEqual(row["execution_status"],"completed")
        self.assertTrue(row["establishment"]["session_active"])
        self.assertTrue(all(row["endpoint_state"].values()))
        self.assertEqual(row["window"]["stage"],"sender_sealing")
        self.assertEqual(row["window"]["reason"],"expired_session")
        self.assertEqual(row["release_count"],0)
        evidence.validate_timing(row)

    def test_failed_intervening_execution_does_not_change_inputs(self):
        before=execute(self.config,self.plan,self.trial,"single-read-v1",self.enrollment)
        with patch.object(noise,"calculate_frequencies",side_effect=RuntimeError("private-secret")):
            failed=execute(self.config,self.plan,self.trial,"majority-3-v1",self.enrollment)
        self.assertEqual(failed["execution_status"],"fault")
        self.assertEqual(failed["actual_reads"],1)
        self.assertNotIn("private-secret",json.dumps(failed))
        after=execute(self.config,self.plan,self.trial,"single-read-v1",self.enrollment)
        self.assertEqual(before["observations"],after["observations"])

    def test_default_pipeline_remains_single_read(self):
        p,_=runtime.fresh_pipeline(self.config,self.enrollment,"single-read-v1")
        plain=pipeline_v2.V2InferencePipeline(p.sender,p.verifier,lambda r:(r,r),lambda r:r,lambda r:r)
        self.assertEqual(plain.acquisition_config,study.POLICIES["single-read-v1"])

    def test_trial_identity_preparation_is_outside_instrumented_boundary(self):
        original=runtime.attempt_id
        def outside(*args):
            self.assertFalse(runtime._SERIAL.locked())
            return original(*args)
        with patch.object(runtime,"attempt_id",side_effect=outside) as identity:
            row=execute(self.config,self.plan,self.trial,"single-read-v1",self.controlled())
        identity.assert_called_once()
        self.assertEqual(row["execution_status"],"completed")


class TimingTests(unittest.TestCase):
    def test_preserves_return_exception_count_and_restores_patches(self):
        original=pipeline_v2.reconstruct
        capture=runtime.Capture()
        with self.assertRaisesRegex(RuntimeError,"sentinel"):
            with runtime.instrument(capture):
                self.assertIsNot(pipeline_v2.reconstruct,original)
                raise RuntimeError("sentinel")
        self.assertIs(pipeline_v2.reconstruct,original)
        called=[]
        obj=object()
        def function(): called.append(1); return obj
        self.assertIs(capture.wrap("reading",function)(),obj)
        self.assertEqual(called,[1])
        error=RuntimeError("sentinel")
        def broken(): raise error
        with self.assertRaises(RuntimeError) as caught: capture.wrap("reading",broken)()
        self.assertIs(caught.exception,error)
        self.assertTrue(capture.spans[-1]["exception"])

    def test_nested_instrumentation_and_foreign_thread_rejected(self):
        capture=runtime.Capture()
        errors=[]
        with runtime.instrument(capture):
            with self.assertRaisesRegex(ValueError,"active"):
                with runtime.instrument(runtime.Capture()): pass
            def worker():
                try: capture.wrap("reading",lambda:None)()
                except ValueError: errors.append(True)
            thread=Thread(target=worker); thread.start(); thread.join()
        self.assertEqual(errors,[True])

    def test_root_p95_uses_complete_durations_not_stage_quantile_sum(self):
        full=analysis.duration_summary([110,110])
        a=analysis.duration_summary([10,100]); b=analysis.duration_summary([100,10])
        self.assertEqual(full["p95_ns"],110)
        self.assertNotEqual(full["p95_ns"],a["p95_ns"]+b["p95_ns"])
        self.assertEqual(analysis.duration_summary([]),dict(count=0,mean_ns=None,median_ns=None,p95_ns=None,p99_ns=None,maximum_ns=None))


class StatisticalTests(unittest.TestCase):
    def cells(self):
        return {p:{c+"|"+policy:(0,0,2) for c,*_ in study.CONDITIONS for policy in study.POLICIES}
                for p in ("p0","p1")}

    def test_analytic_paired_delta_and_attenuation(self):
        cells=self.cells()
        cells["p0"]["independent_nominal|single-read-v1"]=(2,2,2)
        values=analysis.estimands(cells)
        self.assertEqual(values["reconstruction:delta:independent_nominal"],.5)
        self.assertEqual(values["reconstruction:attenuation:rho90"],.5)
        result=analysis.bootstrap_populations(cells,seed=42,resamples=200)
        self.assertEqual(result,analysis.bootstrap_populations(cells,seed=42,resamples=200))
        interval=result["intervals"]["reconstruction:delta:independent_nominal"]
        self.assertEqual((interval["lower"],interval["upper"]),(0,1))

    def test_population_resampling_keeps_all_conditions_together(self):
        cells=self.cells()
        for c,*_ in study.CONDITIONS:
            cells["p0"][c+"|single-read-v1"]=(2,2,2)
        result=analysis.bootstrap_populations(cells,seed=4,resamples=200)
        for rho in ("50","90"):
            interval=result["intervals"]["session:attenuation:rho"+rho]
            self.assertEqual((interval["estimate"],interval["lower"],interval["upper"]),(0,0,0))

    def test_zero_events_and_zero_denominators(self):
        empty=analysis.group_metrics([])
        self.assertIsNone(empty["raw_ber"])
        self.assertIsNone(empty["reconstruction_frr"])
        self.assertIsNone(empty["wrong_refusal_rate"])
        self.assertEqual(empty["wrong_refusal_observation"],"not_observed")
        result=analysis.bootstrap_populations(self.cells(),seed=1,resamples=20)
        self.assertTrue(result["zero_observed_failures_is_not_zero_probability"])
        self.assertEqual(result["intervals"]["session:delta:independent_nominal"]["estimate"],0)
        no_data=analysis.bootstrap_populations({},seed=1,resamples=20)
        self.assertIsNone(no_data["intervals"]["session:delta:independent_nominal"]["lower"])


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Exactly twenty policy attempts in one unit-test fixture. This is neither
        # the 100-attempt smoke nor the 60,000-attempt formal study.
        cls.temp=TemporaryDirectory(prefix="week7-harness-tests-",dir=study.ROOT/"tmp")
        cls.directory=Path(cls.temp.name)/(evidence.TEST_PREFIX+"evidence")
        cls.config=fixture_config()
        with evidence.EvidenceRun(cls.directory,cls.config,test_output_root=Path(cls.temp.name)) as run:
            cls.receipt=run.execute()
            cls.rows=deepcopy(run.rows)
            cls.plan=run.plan
            cls.catalog=run.catalog
            cls.context=dict(run_id=run.metadata["run_id"],source_id=run.metadata["source_id"])
        cls.addClassCleanup(cls.temp.cleanup)

    def clone(self):
        tmp=self.enterContext(TemporaryDirectory(dir=study.ROOT/"tmp"))
        target=Path(tmp)/"copy"
        shutil.copytree(self.directory,target)
        return target

    def reclose(self,directory):
        manifest=evidence.read_json(directory/"manifest.json")
        for path in manifest: manifest[path]=evidence.file_digest(directory/path)
        (directory/"manifest.json").write_bytes(study.canonical(manifest))
        marker=directory/"UNIT_TEST_VALIDATED.json"
        obj=evidence.read_json(marker)
        obj["manifest_sha256"]=evidence.file_digest(directory/"manifest.json")
        marker.write_bytes(study.canonical(obj))

    def test_complete_unit_fixture_audits_and_has_no_formal_marker(self):
        self.assertEqual(evidence.audit_evidence(self.directory),self.receipt)
        self.assertEqual(self.receipt["policy_attempts"],20)
        self.assertEqual(self.receipt["actual_reads"],40)
        self.assertFalse((self.directory/"COMPLETE").exists())
        self.assertFalse((self.directory/"NONFORMAL_VALIDATED.json").exists())

    def test_missing_duplicate_and_misordered_attempts_fail(self):
        for rows in (self.rows[:-1],self.rows+[self.rows[0]],
                     [self.rows[0],self.rows[0]]+self.rows[2:],list(reversed(self.rows))):
            with self.assertRaises(ValueError): evidence.reconcile(self.config,self.plan,rows,self.catalog,self.context)

    def test_tampered_responses_errors_outcomes_and_read_counts_fail(self):
        for field,value in (("actual_reads",0),("effective_sha256","f"*64),("unauthorized_release_count",1),
                            ("source_id","f"*64),("config_sha256","f"*64),("enrollment_sha256","f"*64)):
            rows=deepcopy(self.rows); rows[0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                evidence.reconcile(self.config,self.plan,rows,self.catalog,self.context)
        rows=deepcopy(self.rows)
        rows[0]["observations"][0]["error_positions"]=[] if rows[0]["observations"][0]["error_positions"] else [0]
        with self.assertRaises(ValueError): evidence.reconcile(self.config,self.plan,rows,self.catalog,self.context)

    def test_timing_nesting_and_counts_reconcile(self):
        row=deepcopy(self.rows[0]); row["timing"][1]["parent_id"]=None
        with self.assertRaises(ValueError): evidence.validate_timing(row)
        row=deepcopy(self.rows[0]); row["timing"][0]["duration_ns"]=0
        with self.assertRaises(ValueError): evidence.validate_timing(row)
        for row in self.rows: evidence.validate_timing(row)

    def test_consistently_changed_noise_and_decoder_outcome_are_replayed(self):
        rows=deepcopy(self.rows)
        row=rows[0]
        observation=row["observations"][0]
        observation["response"][0]^=1
        observation["response_sha256"]=study.object_digest(observation["response"])
        observation["error_positions"]=runtime.errors(observation["response"],self.catalog[row["device_id"]]["reference"])
        with self.assertRaisesRegex(ValueError,"deterministic replay"):
            evidence.reconcile(self.config,self.plan,rows,self.catalog,self.context)
        rows=deepcopy(self.rows)
        rows[0]["reconstruction"]["corrections"]=(rows[0]["reconstruction"]["corrections"]+1)%6
        with self.assertRaisesRegex(ValueError,"decoder/truth replay"):
            evidence.reconcile(self.config,self.plan,rows,self.catalog,self.context)

    def test_catalog_must_match_deterministic_manufacturing_and_enrollment(self):
        catalog=deepcopy(self.catalog)
        catalog[next(iter(catalog))]["manufacturing_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"deterministic enrollment"):
            evidence.reconcile(self.config,self.plan,self.rows,catalog,self.context)

    def test_invalid_append_never_publishes_a_completion_marker(self):
        directory=Path(self.enterContext(TemporaryDirectory(dir=study.ROOT/"tmp")))/(evidence.TEST_PREFIX+"malformed")
        with evidence.EvidenceRun(directory,self.config,test_output_root=directory.parent) as run:
            with self.assertRaises(ValueError): run.append({"malformed":True})
        self.assertTrue((directory/"INCOMPLETE.json").exists())
        self.assertFalse((directory/"UNIT_TEST_VALIDATED.json").exists())

    def test_manifest_missing_artifact_extra_artifact_and_hash_tampering_fail(self):
        for variant in ("missing","extra","changed"):
            directory=self.clone()
            if variant=="missing": (directory/"summary.json").unlink()
            elif variant=="extra": (directory/"unexpected.json").write_text('{}')
            else: (directory/"summary.json").write_text('{}')
            with self.subTest(variant=variant),self.assertRaises((ValueError,FileNotFoundError)):
                evidence.audit_evidence(directory)

    def test_rehashed_result_tampering_still_fails_semantic_reconciliation(self):
        directory=self.clone()
        rows=deepcopy(self.rows); rows[0]["actual_reads"]=0
        (directory/"attempts.jsonl").write_bytes(b'\n'.join(study.canonical(r) for r in rows)+b'\n')
        self.reclose(directory)
        with self.assertRaisesRegex(ValueError,"reading count"):
            evidence.audit_evidence(directory)

    def test_source_snapshot_and_configuration_tampering_fail(self):
        directory=self.clone()
        source=directory/"source/src/python/puf_snn/puf/device.py"
        source.write_bytes(source.read_bytes()+b'\n# changed\n')
        self.reclose(directory)
        with self.assertRaisesRegex(ValueError,"source snapshot"):
            evidence.audit_evidence(directory)
        directory=self.clone()
        obj=evidence.read_json(directory/"config.json"); obj["master_seed"]+=1
        (directory/"config.json").write_bytes(study.canonical(obj)); self.reclose(directory)
        with self.assertRaisesRegex(ValueError,"configuration"):
            evidence.audit_evidence(directory)

    def test_incomplete_missing_marker_and_faulted_rows_prevent_completion(self):
        directory=self.clone(); (directory/"UNIT_TEST_VALIDATED.json").unlink()
        with self.assertRaises(FileNotFoundError): evidence.audit_evidence(directory)
        directory=self.clone(); (directory/"INCOMPLETE.json").write_text('{}')
        with self.assertRaises(ValueError): evidence.audit_evidence(directory)
        rows=deepcopy(self.rows); rows[0]["execution_status"]="fault"; rows[0]["fault_code"]="execution_fault"
        with self.assertRaises(ValueError): evidence.reconcile(self.config,self.plan,rows,self.catalog,self.context)

    def test_exclusive_output_and_execution_guards(self):
        with self.assertRaisesRegex(ValueError,"exclusively"):
            evidence.EvidenceRun(self.directory,self.config,test_output_root=self.directory.parent)
        with self.assertRaisesRegex(ValueError,"formal execution"):
            evidence.EvidenceRun(self.directory/"never",study.StudyConfig.load())
        obj=self.config.to_dict(); obj.update(mode="nonformal",allocation=dict(populations=1,devices_per_population=1,attempts_per_device_condition=10))
        with self.assertRaisesRegex(ValueError,"authorization"):
            evidence.EvidenceRun(self.directory/"never",study.StudyConfig.from_dict(obj))
        self.assertFalse((self.directory/"never").exists())

    def test_interrupted_writer_retains_incomplete_sentinel(self):
        directory=Path(self.enterContext(TemporaryDirectory(dir=study.ROOT/"tmp")))/(evidence.TEST_PREFIX+"interrupted")
        with self.assertRaises(RuntimeError):
            with evidence.EvidenceRun(directory,self.config,test_output_root=directory.parent): raise RuntimeError("unit interruption")
        self.assertTrue((directory/"INCOMPLETE.json").exists())
        self.assertFalse((directory/"UNIT_TEST_VALIDATED.json").exists())

    def test_summary_denominators_histograms_and_complete_session_percentile(self):
        summary=evidence.read_json(self.directory/"summary.json")["analysis"]
        self.assertEqual(summary["completed_attempts"],20)
        self.assertEqual(sum(g["actual_reads"] for g in summary["groups"].values()),40)
        for group in summary["groups"].values():
            self.assertEqual(sum(group["outcomes"].values()),group["attempts"])
            self.assertEqual(sum(group["raw_error_histogram"]),group["actual_reads"])
            self.assertEqual(sum(group["effective_error_histogram"]),group["attempts"])
            self.assertEqual(group["raw_ber"],group["raw_bit_errors"]/(63*group["actual_reads"]))
            if not group["outcomes"]["W"]: self.assertIsNone(group["wrong_refusal_rate"])
        rows=[r for r in self.rows if r["condition"]=="independent_nominal" and r["policy"]=="single-read-v1"]
        durations=[s["duration_ns"] for r in rows for s in r["timing"] if s["stage"]=="establishment"]
        self.assertEqual(summary["timing"]["inclusive"]["independent_nominal|single-read-v1|establishment"]["p95_ns"],
                         analysis.percentile(durations,.95))

    def test_public_records_have_no_credential_key_or_capability_fields(self):
        prohibited={"credential","credential4","candidate_credential","candidate_message","verifier_key",
                    "session_key","authorization_capability","tag","tag_hex","key_provider"}
        def walk(obj):
            if isinstance(obj,dict):
                self.assertFalse(set(obj)&prohibited)
                for value in obj.values(): walk(value)
            elif isinstance(obj,list):
                for value in obj: walk(value)
        for row in self.rows: walk(row)
        walk(self.catalog)
        walk(evidence.read_json(self.directory/"metadata.json"))

    def test_paths_cannot_escape_evidence_directory(self):
        for relative in ("../outside","/absolute","C:/outside","a\\b","a/../b"):
            with self.assertRaises(ValueError): evidence.safe_path(self.directory,relative)


if __name__ == "__main__":
    unittest.main()
