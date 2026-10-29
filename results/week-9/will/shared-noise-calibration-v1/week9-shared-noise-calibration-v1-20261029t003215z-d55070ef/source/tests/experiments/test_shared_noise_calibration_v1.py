"""Small deterministic fixtures only. Never execute the 3,840-attempt calibration."""
from collections import Counter
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from puf_snn.experiments import shared_noise_calibration_v1 as study
from puf_snn.experiments import shared_noise_calibration_analysis_v1 as analysis
from puf_snn.experiments import shared_noise_calibration_evidence_v1 as evidence
from puf_snn.experiments import shared_noise_calibration_runtime_v1 as runtime
from puf_snn.experiments import shared_noise_calibration_resources_v1 as resources
from puf_snn.puf.device import Device
from puf_snn.reconstruction import BCHCodec, enroll


def fixture_config(groups=1, devices=1):
    obj = study.StudyConfig.load().to_dict()
    obj.update(mode="unit-test", allocation=dict(groups=groups, devices_per_group=devices, trials_per_device_sigma=2))
    return study.StudyConfig.from_dict(obj)


def synthetic_rows(config, plan):
    """Analysis records only, explicitly not simulated acquisitions or evidence bundles."""
    rows = []
    for trial, policy, index in study.scheduled_attempts(plan):
        fail = ((policy == study.POLICIES[0] and trial["condition"] == "s010")
                or (policy == study.POLICIES[1] and trial["condition"] == "s015"))
        rows.append(dict(trial, policy=policy, policy_attempt_id=study.attempt_id(trial, policy),
            execution_index=index, execution_status="completed", fault_code=None,
            reconstruction=dict(classification="D" if fail else "C")))
    return rows


def passing_candidate(condition="s010", sigma=.10):
    return dict(condition=condition, sigma=sigma, n=480, single_failures=48, majority_failures=24,
        beneficial=24, harmful=0, discordant_devices=8, discordant_groups=4,
        single_failure_devices=8, single_failure_groups=4, group_benefits=[.05]*4,
        leave_one_device_out=[.05]*24, intervals=dict(
            single_frr=dict(lower=.02, upper=.20), majority_frr=dict(lower=0, upper=.1),
            delta=dict(lower=.01, upper=.10)))


class PlanningTests(unittest.TestCase):
    def test_full_plan_counts_without_generation_or_decode(self):
        with patch.object(study, "create_device", side_effect=AssertionError("no devices")), \
             patch.object(study.noise, "measure_indexed", side_effect=AssertionError("no observations")), \
             patch.object(BCHCodec, "decode", side_effect=AssertionError("no decoding")):
            cfg = study.StudyConfig.load()
            result = study.dry_plan(cfg)
        self.assertEqual(result["observations_generated"], 0)
        self.assertEqual(result["counts"], dict(groups=4, simulated_devices=24, matched_trials=1920,
            arm_attempts=3840, expected_reads=7680, expected_runtime_decodes=3840, expected_votes=1920,
            enrollment_reference_readings=24, two_pass_replay_measurements=15360,
            two_pass_replay_decodes=7680, two_pass_reference_readings=48, statistical_samples_added_by_replay=0))
        self.assertFalse(result["scientific_execution_authorized"])

    def test_plan_determinism_balance_unique_ids(self):
        cfg = study.StudyConfig.load()
        plan = study.compile_plan(cfg)
        self.assertEqual(plan, study.compile_plan(cfg))
        cells = {}
        for t in plan["blocks"]:
            cells.setdefault((t["device_id"], t["condition"]), Counter())[tuple(t["policy_order"])] += 1
            self.assertEqual((t["rho"], t["common_offset"]), (0, 0))
        self.assertEqual(len(cells), 96)
        self.assertTrue(all(set(c.values()) == {10} for c in cells.values()))
        self.assertEqual(len({study.attempt_id(t,p) for t,p,_ in study.scheduled_attempts(plan)}), 3840)

    def test_phase_and_domain_separation(self):
        cal = study.phase_identity("calibration", "w9c-p000", "w9c-p000-d00", "enrollment-v1")
        final = study.phase_identity("final", "w9c-p000", "w9c-p000-d00", "enrollment-v1")
        for domain in (study.noise.MANUFACTURING, study.noise.ENROLLMENT, study.noise.CREDENTIAL):
            self.assertNotEqual(study.noise.derive_seed(cal, domain), study.noise.derive_seed(final, domain))
        plan = study.compile_plan(fixture_config())
        self.assertEqual(len({t["noise_shared_seed_sha256"] for t in plan["blocks"]}), 8)
        for t in plan["blocks"]:
            self.assertEqual(len(set(t["reading_seed_sha256"])), 3)
        cfg = fixture_config()
        self.assertNotEqual(study.study_seed(cfg,"schedule"), study.study_seed(cfg,"device-bootstrap"))
        self.assertTrue(all(t["device_id"].startswith("w9u-") for t in plan["blocks"]))

    def test_frozen_rules_allocation_and_no_formal_mode(self):
        original = study.StudyConfig.load().to_dict()
        for key, value in (("mode","planned-formal"),("policies",["stored-provisioned-v1"]),
                           ("bootstrap_resamples",9999),("master_seed",1),("manufacturing_std",2)):
            obj = deepcopy(original); obj[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                study.StudyConfig.from_dict(obj)
        for field in original["selection_rules"]:
            obj = deepcopy(original); obj["selection_rules"][field] += .001
            with self.subTest(field=field), self.assertRaises(ValueError):
                study.StudyConfig.from_dict(obj)
        obj = deepcopy(original); obj["allocation"]["groups"] = 3
        with self.assertRaises(ValueError): study.StudyConfig.from_dict(obj)
        obj["mode"] = "unit-test"
        with self.assertRaises(ValueError): study.StudyConfig.from_dict(obj)
        with self.assertRaises(ValueError): study.StudyConfig('{"a":1,"a":2}')

    def test_all_schema_definitions(self):
        for kind in ("config","plan","attempt","summary","approval"):
            schema = study.read_json_bytes((study.ROOT/f"schemas/shared-noise-calibration-{kind}-v1.schema.json").read_bytes())
            study.Draft202012Validator.check_schema(schema)

    def test_cli_plan_and_forbidden_actions(self):
        from scripts.run_shared_noise_calibration_v1 import main
        with patch.object(evidence.EvidenceRun,"execute",side_effect=AssertionError("no execution")), \
             patch("sys.stdout",new_callable=io.StringIO) as output:
            main(["plan"])
        self.assertEqual(json.loads(output.getvalue())["counts"]["arm_attempts"],3840)
        for action in ("run-formal","run-nonformal","select-final"):
            with patch("sys.stderr",new_callable=io.StringIO), self.assertRaises(SystemExit): main([action])
        with self.assertRaises(ValueError): main(["run-calibration"])


class StatisticalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = fixture_config(groups=2)
        cls.plan = study.compile_plan(cls.cfg)
        cls.rows = synthetic_rows(cls.cfg, cls.plan)
        cls.records = analysis.device_records(analysis.complete_cells(cls.cfg,cls.plan,cls.rows))

    def test_positive_negative_zero_differences(self):
        result = analysis.estimates(self.records,dict.fromkeys(self.records,1))
        self.assertEqual([result[c]["delta"] for c,_ in study.CONDITIONS],[1,-1,0,0])

    def test_whole_device_multiplicities_shared_across_conditions(self):
        seen = []
        original = analysis.estimates
        def capture(records,weights):
            seen.append(tuple(sorted(weights.items())))
            return original(records,weights)
        with patch.object(analysis,"estimates",side_effect=capture):
            result = analysis.bootstrap_devices(self.records,seed=1234)
        self.assertEqual(len(seen),10001)
        self.assertTrue(all(sum(w for _,w in draw)==2 for draw in seen))
        self.assertTrue(any(len(draw)==1 and draw[0][1]==2 for draw in seen[1:]))
        self.assertEqual(result["performed_resamples"],10000)
        self.assertEqual(result["conditions"]["s015"]["delta"]["estimate"],-1)
        self.assertEqual(result,analysis.bootstrap_devices(self.records,seed=1234))

    def test_exact_weighted_device_effect_not_trial_resampling(self):
        records = deepcopy(self.records)
        ids = sorted(records)
        records[ids[1]]["s010"]["single_failures"] = 0
        out = analysis.estimates(records,{ids[0]:2,ids[1]:1})
        self.assertAlmostEqual(out["s010"]["delta"],2/3)
        self.assertEqual(out["s015"]["delta"],-1)

    def test_missing_duplicate_mismatched_pairs_rejected(self):
        for mutation in (lambda rows: rows.pop(), lambda rows: rows.__setitem__(1,deepcopy(rows[0])),
                         lambda rows: rows[0].__setitem__("condition","s999"),
                         lambda rows: rows[0].__setitem__("execution_status","fault")):
            rows = deepcopy(self.rows); mutation(rows)
            with self.assertRaises(ValueError): analysis.complete_cells(self.cfg,self.plan,rows)

    def test_zero_failure_and_undefined_intervals(self):
        result = analysis.bootstrap_devices(self.records,seed=3)
        zero = result["conditions"]["s020"]["single_frr"]
        self.assertEqual((zero["lower"],zero["upper"]),(0,0))
        self.assertTrue(zero["degenerate"] and zero["unseen_events_limitation"])
        one = {next(iter(self.records)):next(iter(self.records.values()))}
        self.assertEqual(analysis.bootstrap_devices(one,seed=3)["performed_resamples"],0)
        out = analysis.conditional_interval([0,1],[0,1])
        self.assertEqual((out["defined_resamples"],out["undefined_resamples"],out["lower"]),(1,1,None))
        self.assertEqual(analysis.conditional_interval([0,2],[2,2])["upper"],.975)

    def test_percentile_linear_convention_and_resample_count(self):
        self.assertAlmostEqual(analysis.percentile([0,10,20,30],.95),28.5)
        with self.assertRaises(ValueError): analysis.bootstrap_devices(self.records,seed=1,resamples=5)

    def test_group_variation_discordance_and_no_attenuation(self):
        result = analysis.analyze(self.cfg,self.plan,self.rows,coverage_certified=True)
        c = result["candidates"][0]
        self.assertEqual((c["beneficial"],c["harmful"],c["discordant_devices"],c["discordant_groups"]),(4,0,2,2))
        self.assertEqual(c["group_benefits"],[1,1])
        self.assertEqual(c["leave_one_device_out"],[1,1])
        self.assertNotIn("attenuation",str(result))


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.rules = study.StudyConfig.load().to_dict()["selection_rules"]
        self.c = passing_candidate()

    def gates(self,c=None,coverage=True):
        return analysis.candidate_gates(c or self.c,self.rules,coverage_certified=coverage)

    def test_all_passing_and_coverage_guard(self):
        self.assertTrue(all(self.gates().values()))
        self.assertFalse(self.gates(coverage=False)["coverage_correctness"])

    def test_baseline_inclusive_boundaries_and_failure_counts(self):
        for sf in (24,336):
            c=deepcopy(self.c);c["single_failures"]=sf
            self.assertTrue(self.gates(c)["baseline_region"])
        for sf in (23,337,480):
            c=deepcopy(self.c);c["single_failures"]=sf
            self.assertFalse(self.gates(c)["baseline_region"])
        c=deepcopy(self.c);c.update(n=30,single_failures=15)
        self.assertFalse(self.gates(c)["baseline_region"])

    def test_majority_and_exact_benefit_boundary(self):
        c=deepcopy(self.c);c["majority_failures"]=240
        self.assertTrue(self.gates(c)["majority_region"])
        c["majority_failures"]=241
        self.assertFalse(self.gates(c)["majority_region"])
        # Synthetic gate arithmetic only; this does not change any study allocation.
        c.update(n=500,single_failures=35,majority_failures=25)
        self.assertTrue(self.gates(c)["minimum_benefit"])
        c["single_failures"]=34
        self.assertFalse(self.gates(c)["minimum_benefit"])

    def test_each_event_coverage_boundary(self):
        fields = dict(beneficial=20,discordant_devices=6,discordant_groups=3,
                      single_failure_devices=6,single_failure_groups=3)
        c=deepcopy(self.c);c.update(fields)
        self.assertTrue(self.gates(c)["informative_counts"])
        for key,value in fields.items():
            bad=deepcopy(c);bad[key]=value-1
            self.assertFalse(self.gates(bad)["informative_counts"],key)

    def test_uncertainty_inclusive_and_strict_boundaries(self):
        c=deepcopy(self.c);c["intervals"]["single_frr"].update(lower=.01,upper=.85)
        c["intervals"]["delta"].update(lower=.01,upper=.21)
        self.assertTrue(self.gates(c)["uncertainty"])
        for key,field,value in (("single_frr","lower",.0099),("single_frr","upper",.8501),
                                ("delta","lower",0),("delta","upper",.2101),("delta","lower",None)):
            bad=deepcopy(c);bad["intervals"][key][field]=value
            self.assertFalse(self.gates(bad)["uncertainty"])

    def test_heterogeneity_boundaries_and_concentration(self):
        c=deepcopy(self.c);c.update(group_benefits=[.01,.02,.03,-.02],leave_one_device_out=[.01]*24)
        self.assertTrue(self.gates(c)["heterogeneity"])
        for changes in (dict(group_benefits=[0,0,.1,.1]),dict(group_benefits=[.1,.1,.1,-.0201]),
                        dict(leave_one_device_out=[.0099]+[.01]*23)):
            bad=deepcopy(c);bad.update(changes)
            self.assertFalse(self.gates(bad)["heterogeneity"])

    def test_lowest_sigma_no_qualification_and_incomplete(self):
        candidates=[passing_candidate(c,s) for c,s in study.CONDITIONS]
        selected=analysis.select_candidates(candidates,self.rules,coverage_certified=True)
        self.assertEqual(selected["selected_sigma"],.10)
        candidates[0]["single_failures"]=0
        self.assertEqual(analysis.select_candidates(candidates,self.rules,coverage_certified=True)["selected_sigma"],.15)
        for c in candidates:c["single_failures"]=0
        out=analysis.select_candidates(candidates,self.rules,coverage_certified=True)
        self.assertEqual(out["status"],"no-qualifying-operating-point")
        self.assertIsNone(out["selected_sigma"])
        self.assertTrue(all(c["failed_criteria"] for c in out["candidates"]))
        self.assertEqual(analysis.select_candidates(candidates,self.rules,coverage_certified=False)["status"],"incomplete-selection-prohibited")
        with self.assertRaises(ValueError):analysis.select_candidates(candidates[:3],self.rules,coverage_certified=True)


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg=fixture_config();cls.plan=study.compile_plan(cls.cfg);cls.trial=cls.plan["blocks"][0]
        cls.enrollment=study.prepare_enrollment(cls.cfg,cls.trial["population_id"],cls.trial["device_id"])

    def controlled(self,response=(0,)*64):
        offsets=tuple(v for bit in response for v in ((16.,-16.) if bit else (-16.,16.)))
        return replace(self.enrollment,device=Device(self.trial["device_id"],offsets),reference=(0,)*64,
            helper=enroll((0,)*64,self.enrollment.credential,enrollment_id=self.trial["enrollment_id"]))

    def execute(self,policy,enrollment):
        return runtime.execute_attempt(self.cfg,self.trial,policy,enrollment,run_id="fixture",source_id="0"*64,
            plan_sha256=self.plan["plan_sha256"],execution_index=0)

    def test_real_cdiw_and_independent_refusal(self):
        for policy in study.POLICIES:
            for kind in "CDIW":
                enrollment=self.controlled();helper=enrollment.helper
                if kind != "C":
                    if kind == "D": word=(1,)*6+(0,)*57
                    elif kind == "I": word=BCHCodec().encode((0,)*35+(1,))
                    else: word=enroll((0,)*64,bytes(v^255 for v in enrollment.credential),enrollment_id=helper.enrollment_id).helper_bits
                    enrollment=self.controlled(tuple(a^b for a,b in zip(helper.helper_bits,word))+(0,))
                row=self.execute(policy,enrollment)
                study.validate_schema("attempt",row);evidence.old.validate_protocol(row);evidence.old.validate_timing(row)
                self.assertEqual(row["reconstruction"]["classification"],kind)
                self.assertEqual(row["actual_reads"],1 if policy==study.POLICIES[0] else 3)
                self.assertEqual(row["operation_counts"]["bch_decode"],1)
                if kind=="W":self.assertEqual(row["verification_outcomes"],["credential_mismatch"])
                if kind in "DI":self.assertEqual(row["verification_outcomes"],[])
                self.assertEqual(row["release_completions"],int(kind=="C"))
                if kind!="C":self.assertFalse(any(row["operation_counts"][k] for k in ("sender_hkdf","receiver_hkdf")))

    def test_matched_reading_zero_and_security_fault(self):
        rows=[self.execute(p,self.controlled()) for p in study.POLICIES]
        self.assertEqual(rows[0]["observations"][0],rows[1]["observations"][0])
        with patch.object(runtime.noise,"calculate_frequencies",side_effect=RuntimeError("fixture fault")):
            row=self.execute(study.POLICIES[0],self.controlled())
        self.assertEqual(row["execution_status"],"fault")
        self.assertEqual(row["release_count"],0)

    def test_no_unsupervised_scientific_or_stored_runtime(self):
        cfg=study.StudyConfig.load()
        with self.assertRaises(ValueError):runtime.execute_attempt(cfg,{},study.POLICIES[0],None,
            run_id="x",source_id="0"*64,plan_sha256="0"*64,execution_index=0)
        with self.assertRaises(ValueError):self.execute("stored-provisioned-v1",self.controlled())


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(dir=study.ROOT/"tmp",prefix="calibration-unit-")
        cls.root=Path(cls.temp.name);cls.cfg=fixture_config()
        cls.directory=cls.root/(study.VERSION+"-unit-complete")
        with evidence.EvidenceRun(cls.directory,cls.cfg,test_output_root=cls.root) as run:
            cls.receipt=run.execute()
        cls.plan=evidence.read_json(cls.directory/"trial-plan.json")
        cls.catalog=evidence.read_json(cls.directory/"enrollments.json")
        cls.rows=[json.loads(line) for line in (cls.directory/"attempts.jsonl").read_text().splitlines()]
        metadata=evidence.read_json(cls.directory/"metadata.json")
        cls.context={k:metadata[k] for k in ("run_id","source_id")}

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_two_pass_fixture_receipt_and_standalone_audit(self):
        self.assertTrue((self.directory/evidence.MARKER).is_file())
        self.assertFalse((self.directory/"INCOMPLETE.json").exists())
        marker=evidence.read_json(self.directory/evidence.MARKER)
        self.assertEqual(marker["validation_passes_completed"],2)
        self.assertEqual(marker["finalization_validation_work"],dict(replay_measurements=64,replay_decodes=32,
            enrollment_reference_readings=2,statistical_samples_added=0))
        receipt=evidence.audit_evidence(self.directory)
        self.assertEqual(receipt["validation_scope"],"standalone-audit")
        self.assertEqual(receipt["validation_passes_completed"],1)
        self.assertTrue(evidence.read_json(self.directory/"selection.json")["fixture_only"])

    def test_replay_rejects_response_truth_and_protocol_tampering(self):
        for field,value in (("actual_reads",9),("source_id","f"*64),("noise_shared_seed_sha256","f"*64)):
            rows=deepcopy(self.rows);rows[0][field]=value
            with self.assertRaises(ValueError):evidence.reconcile(self.cfg,self.plan,rows,self.catalog,self.context)
        rows=deepcopy(self.rows);rows[0]["observations"][0]["response"][0]^=1
        with self.assertRaises(ValueError):evidence.reconcile(self.cfg,self.plan,rows,self.catalog,self.context)

    def test_failed_first_or_second_pass_never_seals(self):
        for pass_number in (1,2):
            directory=self.root/(study.VERSION+f"-unit-fail-{pass_number}")
            with evidence.EvidenceRun(directory,self.cfg,test_output_root=self.root) as run:
                run.catalog=deepcopy(self.catalog)
                evidence.write_json(directory/"enrollments.json",run.catalog)
                for original in self.rows:
                    row=deepcopy(original);row.update(run_id=run.metadata["run_id"],source_id=run.metadata["source_id"])
                    run.append(row)
                target="reconcile" if pass_number==1 else "audit_evidence"
                with patch.object(evidence,target,side_effect=ValueError("fixture reconciliation failure")),self.assertRaises(ValueError):run.finalize()
            self.assertFalse((directory/evidence.MARKER).exists())
            self.assertTrue((directory/"INCOMPLETE.json").exists())

    def test_missing_rows_source_change_and_interruption(self):
        for label in ("missing","changed","interrupted"):
            directory=self.root/(study.VERSION+"-unit-"+label)
            with evidence.EvidenceRun(directory,self.cfg,test_output_root=self.root) as run:
                if label=="missing":
                    with self.assertRaises(ValueError):run.finalize()
                elif label=="changed":
                    with patch.object(evidence,"source_hashes",return_value={}),self.assertRaises(ValueError):run.execute()
                else:
                    with patch.object(run,"boundary",side_effect=KeyboardInterrupt),self.assertRaises(KeyboardInterrupt):run.execute()
            self.assertFalse((directory/evidence.MARKER).exists())
            self.assertTrue((directory/"INCOMPLETE.json").exists())

    def test_completion_publication_failure_restores_incomplete(self):
        directory=self.root/(study.VERSION+"-unit-publication-fault")
        directory.mkdir()
        evidence.write_json(directory/"INCOMPLETE.json",dict(reason="fixture"))
        evidence.write_json(directory/"manifest.json",{})
        with patch.object(evidence.os,"replace",side_effect=OSError("fixture rename failure")),self.assertRaises(OSError):
            evidence.seal(directory,self.receipt,self.cfg)
        self.assertTrue((directory/"INCOMPLETE.json").exists())
        self.assertFalse((directory/evidence.MARKER).exists())
        self.assertFalse((directory/"completion.pending").exists())

    def test_manifest_extra_file_and_current_source_drift(self):
        rogue=self.directory/"extra.txt";rogue.write_text("fixture")
        try:
            with self.assertRaises(ValueError):evidence.audit_evidence(self.directory)
        finally:rogue.unlink()
        with patch.object(evidence,"source_hashes",return_value={}),self.assertRaises(ValueError):evidence.audit_evidence(self.directory)


class SafetyTests(unittest.TestCase):
    def test_archived_patch_required_no_historical_path(self):
        paths=evidence.source_paths()
        self.assertIn("docs/archive/week8-three-arm-auth-tests.patch",paths)
        self.assertNotIn("docs/week8-three-arm-auth-tests.patch",paths)
        self.assertTrue(all((study.ROOT/p).is_file() for p in paths))
        self.assertTrue(evidence.source_hashes())
        with patch.object(evidence,"source_paths",return_value=["missing-source-fixture"]),self.assertRaises(ValueError):evidence.source_hashes()

    def test_output_exclusive_namespace_traversal_and_historical_roots(self):
        with tempfile.TemporaryDirectory(dir=study.ROOT/"tmp") as temp:
            root=Path(temp);good=root/(study.VERSION+"-unit-new")
            self.assertEqual(evidence.checked_output_path(good,"unit-test",test_output_root=root),good.resolve())
            good.mkdir()
            with self.assertRaises(ValueError):evidence.checked_output_path(good,"unit-test",test_output_root=root)
            for path in (root/".."/(study.VERSION+"-unit-escape"),study.ROOT/"results/week-8"/(study.VERSION+"-bad")):
                with self.assertRaises(ValueError):evidence.checked_output_path(path,"unit-test",test_output_root=root)
            (root/"manifest.json").write_text("{}")
            with self.assertRaises(ValueError):evidence.checked_output_path(root/(study.VERSION+"-unit-nested"),"unit-test",test_output_root=root)

    def test_no_scientific_writer_without_live_permit(self):
        with self.assertRaises(ValueError):evidence.EvidenceRun(evidence.OUTPUT_ROOT/(study.VERSION+"-forbidden"),study.StudyConfig.load())

    def test_resource_budget_boundaries_fail_closed(self):
        p=resources.primitives();b=p.Budgets(**study.StudyConfig.load().to_dict()["resource_budgets"])
        sample=dict(rss_bytes=1,private_bytes=1,os_peak_rss_bytes=1,free_ram_bytes=b.min_free_ram_bytes+1,
                    free_disk_bytes=b.min_free_disk_bytes+1)
        def violations(s=sample,**changes):
            args=dict(phase_seconds=0,session_seconds=0,bundle_bytes=0,total_bytes=0);args.update(changes)
            return b.violations(s,**args)
        self.assertEqual(violations(),[])
        for key,limit in (("phase_seconds",b.bundle_seconds),("session_seconds",b.session_seconds),
                          ("bundle_bytes",b.bundle_growth_bytes),("total_bytes",b.total_growth_bytes)):
            self.assertTrue(violations(**{key:limit}))
        self.assertTrue(violations(dict(sample,private_bytes=b.memory_bytes)))
        self.assertTrue(violations(dict(sample,free_disk_bytes=None)))
        self.assertTrue(violations(dict(sample,free_ram_bytes=b.min_free_ram_bytes)))

    def test_permit_stop_and_supervision_loss(self):
        from experiments.test_shared_noise_calibration_authorization_v2 import fixture_approval, fixture_config
        from puf_snn.experiments import shared_noise_calibration_authorization_v2 as auth
        with tempfile.TemporaryDirectory(dir=study.ROOT/"tmp") as temp:
            stop=Path(temp)/"STOP"
            cfg=fixture_config();context,output,approval=fixture_approval(cfg,Path(temp))
            receipt=auth.reserve_approval(cfg,approval,output,context)
            p=resources.primitives()
            supervision=p.WorkerSupervision(dict(budgets=resources.FIXTURE_BUDGETS))
            permit=resources.ExecutionPermit(cfg.digest,output,approval,supervision,stop,context,receipt)
            with patch.object(supervision,"check") as check:
                permit.check();stop.touch()
                with self.assertRaises(ValueError):permit.check()
                stop.unlink();check.side_effect=RuntimeError("lease lost")
                with self.assertRaises(RuntimeError):permit.check()
            with self.assertRaises(p.StopRequested):permit.check()
        with self.assertRaises(ValueError):resources.checked_worker({},Mock())

    def test_approval_frozen_identities_and_explicit_review(self):
        from experiments.test_shared_noise_calibration_authorization_v2 import fixture_approval, fixture_config
        with tempfile.TemporaryDirectory(dir=study.ROOT/"tmp") as temp:
            cfg=fixture_config();context,output,approval=fixture_approval(cfg,Path(temp))
            resources.validate_approval(cfg,approval,output,context=context)
            for key,value in (("source_id","f"*64),("allocation_rules_and_resources_reviewed",False),
                              ("authorization","RUN-150-NONFORMAL"),("approved_at","2030-01-01T00:00:00+00:00")):
                if key=="allocation_rules_and_resources_reviewed":value=True
                bad=dict(approval,**{key:value})
                with self.assertRaises(ValueError):resources.validate_approval(cfg,bad,output,context=context)
            with self.assertRaises(ValueError):resources.validate_approval(cfg,dict(approval,schema_version=study.VERSION+":approval-v1"),output,context=context)

    def test_monitor_launch_adapts_only_calibration_worker(self):
        p=resources.primitives()
        with patch.object(p,"launch_python") as launch:
            resources.launch_worker([str(Path(p.__file__).resolve()),"_worker"],stdin="fixture")
        self.assertEqual(launch.call_args.args[0],[str(resources.CLI),"_worker"])
        with self.assertRaises(ValueError):resources.launch_worker(["unexpected","_worker"])


    @unittest.skipUnless(os.name=="nt","Windows supervised worker refusal")
    def test_real_new_worker_refuses_unreviewed_request_before_output(self):
        # Live new CLI + real job/pipe/lease, deliberately invalid approval/path.
        # No Device, enrollment, PUF reading or decode is permitted here.
        import time
        p=resources.primitives();cfg=study.StudyConfig.load()
        with tempfile.TemporaryDirectory(dir=study.ROOT/"tmp") as temp:
            root=Path(temp);child=root/"worker";child.mkdir()
            output=root/"must-not-exist"
            budgets=p.Budgets(20,20,4*1024**3,1,1,1024**2,1024**3)
            request=dict(kind="shared-noise-calibration-v1",controller_pid=os.getpid(),
                directory=str(output),worker_sidecar=str(child),session_started_monotonic=time.monotonic(),
                config=cfg.to_dict(),approval={},budgets=p.asdict(budgets))
            p.save_json(root/"request.json",request)
            result=p.monitor_worker(request,child,budgets,time.monotonic(),[],popen=resources.launch_worker)
            self.assertFalse(result["success"])
            self.assertFalse(output.exists())
            self.assertFalse((child/"worker-result.json").exists())
            self.assertIn("worker sidecar escapes namespace",(child/"stderr.txt").read_text())


class ControllerAcceptanceTests(unittest.TestCase):
    """Negative controller fixtures only; native success is tested unmocked."""
    def run_controller_fixture(self, fault=None):
        from contextlib import ExitStack
        from experiments.test_shared_noise_calibration_authorization_v2 import fixture_approval, fixture_config
        cfg=fixture_config();p=resources.primitives()
        with tempfile.TemporaryDirectory(dir=study.ROOT/"tmp") as temp,ExitStack() as stack:
            root=Path(temp);context,output,approval=fixture_approval(cfg,root)
            frozen=resources.freeze(cfg)
            metrics=SimpleNamespace(sample=lambda:dict(rss_bytes=1,private_bytes=1,os_peak_rss_bytes=1,
                free_ram_bytes=16*1024**3),close=lambda:None)
            stack.enter_context(patch.object(p,"WindowsMetrics",return_value=metrics))
            stack.enter_context(patch("shutil.disk_usage",return_value=SimpleNamespace(free=0 if fault=="disk" else 2*1024**3)))
            def monitor(*args,**kwargs):
                output.mkdir(parents=True)
                evidence.write_json(output/"INCOMPLETE.json",dict(reason="fake-worker-fixture"))
                evidence.write_json(output/"manifest.json",{})
                receipt=dict(status="PASS",arm_attempts=15 if fault=="partial" else 16,
                    actual_reads=32,runtime_decodes=16,validation_passes_completed=1,
                    validation_work=dict(replay_measurements=32,replay_decodes=16,
                        enrollment_reference_readings=1,statistical_samples_added=0))
                return dict(success=fault!="monitor",supervision_verified=fault!="lease",worker=dict(receipt=receipt,
                    freeze={} if fault=="source" else frozen,manifest_sha256=evidence.file_digest(output/"manifest.json")))
            stack.enter_context(patch.object(p,"monitor_worker",side_effect=monitor))
            if fault=="deadline":stack.enter_context(patch.object(resources.time,"monotonic",side_effect=[0,2000,2000]))
            with self.assertRaises(ValueError):resources.execute(cfg,output,approval,fixture_root=root)
            self.assertFalse((output/evidence.MARKER).exists())
            self.assertTrue((output/"INCOMPLETE.json").exists())

    def test_monitor_failure_blocks_completion(self):self.run_controller_fixture("monitor")

    def test_supervision_failure_blocks_completion(self):self.run_controller_fixture("lease")

    def test_source_drift_blocks_completion(self):self.run_controller_fixture("source")

    def test_partial_receipt_blocks_completion(self):self.run_controller_fixture("partial")

    def test_final_disk_limit_blocks_completion(self):self.run_controller_fixture("disk")

    def test_final_deadline_blocks_completion(self):self.run_controller_fixture("deadline")


if __name__=="__main__":unittest.main()
