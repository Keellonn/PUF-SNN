"""Authorization/provenance remediation fixtures; no scientific credentials or study."""
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction
import json
import os
from pathlib import Path
from random import Random
import tempfile
import threading
import unittest
from unittest.mock import patch

from puf_snn.experiments import shared_noise_calibration_v1 as study
from puf_snn.experiments import shared_noise_calibration_evidence_v1 as evidence
from puf_snn.experiments import shared_noise_calibration_resources_v1 as resources
from puf_snn.experiments import shared_noise_calibration_authorization_v2 as auth
from puf_snn.experiments import shared_noise_calibration_provenance_v2 as provenance
from puf_snn.experiments import shared_noise_calibration_analysis_v1 as analysis


def fixture_config():
    obj = study.StudyConfig.load().to_dict()
    obj.update(mode="unit-test", allocation=dict(groups=1, devices_per_group=1, trials_per_device_sigma=2))
    return study.StudyConfig.from_dict(obj)


def fixture_approval(config, root, name="first", authorization_id=None, previous=None):
    context = auth.context_for(config, root)
    output = context.output_root/(study.VERSION+"-unit-"+name)
    approval = dict(schema_version=auth.APPROVAL_VERSION, experiment_id=study.VERSION,
        authorization=resources.FIXTURE_TOKEN, authorization_id=authorization_id or "fixture-"+name,
        run_id=output.name, output_directory=str(output.resolve()), fixture_only=True,
        approved_by="automated deterministic fixture; no researcher approval",
        approved_at=provenance.utc_now(), rules_version=study.RULES_VERSION,
        allocation_rules_and_resources_reviewed=False, resource_budgets=resources.FIXTURE_BUDGETS,
        previous_failed_authorization_id=previous, restart_reason="Explicit deterministic fixture restart after prior failure" if previous else None,
        **resources.freeze(config))
    return context, output, approval


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=study.ROOT/"tmp", prefix="task2g-authorization-")
        self.addCleanup(self.temp.cleanup)
        self.root, self.cfg = Path(self.temp.name), fixture_config()
        self.context, self.output, self.approval = fixture_approval(self.cfg, self.root)

    def reserve(self, approval=None, output=None):
        approval, output = approval or self.approval, output or self.output
        resources.validate_approval(self.cfg, approval, output, context=self.context)
        return auth.reserve_approval(self.cfg, approval, output, self.context)

    def test_exact_output_and_durable_consumption(self):
        receipt = self.reserve()
        self.assertTrue(receipt["fixture_only"])
        self.assertEqual(receipt, auth.check_consumption(self.cfg, self.approval, self.output, self.context))
        self.assertEqual(receipt["approval_sha256"], study.object_digest(self.approval))

    def test_reused_approval_other_output_or_modified_run_id_rejected(self):
        self.reserve()
        other = self.output.with_name(study.VERSION+"-unit-other")
        with self.assertRaises(ValueError): resources.validate_approval(self.cfg, self.approval, other, context=self.context)
        changed = dict(self.approval, run_id=other.name)
        with self.assertRaises(ValueError): resources.validate_approval(self.cfg, changed, self.output, context=self.context)
        changed["output_directory"] = str(other)
        with self.assertRaises(ValueError): self.reserve(changed, other)

    def test_modified_frozen_identities_and_versions_rejected(self):
        for key in ("config_sha256", "plan_sha256", "source_id", "environment_sha256", "specification_sha256"):
            changed = dict(self.approval, **{key: "0"*64})
            with self.subTest(key=key), self.assertRaises(ValueError):
                resources.validate_approval(self.cfg, changed, self.output, context=self.context)
        for key in ("experiment_id", "rules_version"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                resources.validate_approval(self.cfg, dict(self.approval, **{key:"wrong-version"}), self.output, context=self.context)

    def test_new_schema_definitions_are_valid(self):
        from jsonschema import Draft202012Validator
        for name in ("approval-v2", "selection-v2", "consumption-v1", "acknowledgment-v1"):
            Draft202012Validator.check_schema(evidence.read_json(study.ROOT/"schemas"/("shared-noise-calibration-"+name+".schema.json")))

    def test_worker_failure_and_interruption_consume_approval(self):
        for index, failure in enumerate((RuntimeError("fixture worker failure"), KeyboardInterrupt())):
            context, output, approval = fixture_approval(self.cfg, self.root, name=f"failed-{index}")
            with patch.object(resources, "_execute_reserved", side_effect=failure), self.assertRaises(type(failure)):
                resources.execute(self.cfg, output, approval, fixture_root=self.root)
            self.assertTrue((auth.reservation_path(context, approval["authorization_id"])/"failure.json").exists())
            with patch.object(resources, "_execute_reserved") as worker, self.assertRaises(ValueError):
                resources.execute(self.cfg, output, approval, fixture_root=self.root)
            worker.assert_not_called()

    def test_missing_or_corrupted_consumption_remains_consumed(self):
        for index, corruption in enumerate((None, b"{", b"{}")):
            context, output, approval = fixture_approval(self.cfg, self.root, name=f"corrupt-{index}")
            self.reserve(approval, output)
            path = auth.reservation_path(context, approval["authorization_id"])/"consumption.json"
            if corruption is None: path.unlink()
            else: path.write_bytes(corruption)
            with self.assertRaises((ValueError, KeyError)): auth.check_consumption(self.cfg, approval, output, context)
            with self.assertRaises(ValueError): self.reserve(approval, output)

    def test_receipt_write_failure_leaves_atomic_tombstone(self):
        resources.validate_approval(self.cfg, self.approval, self.output, context=self.context)
        with patch.object(evidence, "write_json", side_effect=OSError("fixture fsync/write failure")), self.assertRaises(OSError):
            auth.reserve_approval(self.cfg, self.approval, self.output, self.context)
        reservation = auth.reservation_path(self.context, self.approval["authorization_id"])
        self.assertTrue(reservation.is_dir())
        with self.assertRaises(ValueError): self.reserve()

    def test_reservation_mkdir_failure_never_launches_worker(self):
        target = auth.reservation_path(self.context, self.approval["authorization_id"])
        original = Path.mkdir
        def refused(path, *args, **kwargs):
            if path == target: raise PermissionError("fixture atomic reservation refusal")
            return original(path, *args, **kwargs)
        with patch.object(Path, "mkdir", refused), patch.object(resources, "_execute_reserved") as worker, self.assertRaises(PermissionError):
            resources.execute(self.cfg, self.output, self.approval, fixture_root=self.root)
        worker.assert_not_called()

    def test_concurrent_reservation_has_exactly_one_winner(self):
        barrier = threading.Barrier(2)
        def contender():
            barrier.wait()
            try: return auth.reserve_approval(self.cfg, self.approval, self.output, self.context)
            except ValueError: return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: contender(), range(2)))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(auth.load_consumption(self.context, self.approval["authorization_id"]), next(r for r in results if r))

    def test_separate_authorization_after_documented_failure(self):
        with patch.object(resources, "_execute_reserved", side_effect=RuntimeError("fixture")), self.assertRaises(RuntimeError):
            resources.execute(self.cfg, self.output, self.approval, fixture_root=self.root)
        prior = auth.reservation_path(self.context, self.approval["authorization_id"])/"consumption.json"
        preserved = prior.read_bytes()
        _, output, approval = fixture_approval(self.cfg, self.root, name="explicit-restart", previous=self.approval["authorization_id"])
        receipt = self.reserve(approval, output)
        self.assertEqual(receipt["approval"]["previous_failed_authorization_id"], self.approval["authorization_id"])
        self.assertEqual(prior.read_bytes(), preserved)

    def test_restart_cannot_reuse_prior_run_identity_or_completed_invocation(self):
        self.reserve()
        altered = dict(self.approval, authorization_id="fixture-restart", previous_failed_authorization_id=self.approval["authorization_id"],
            restart_reason="Recorded fixture restart")
        with self.assertRaises(ValueError): self.reserve(altered, self.output)
        self.output.mkdir(parents=True)
        (self.output/evidence.MARKER).write_text("fixture completed marker")
        _, output, approval = fixture_approval(self.cfg, self.root, name="completed-restart", previous=self.approval["authorization_id"])
        with self.assertRaises(ValueError): self.reserve(approval,output)

    def test_live_permit_rechecks_consumption_and_stop(self):
        receipt = self.reserve()
        p = resources.primitives()
        supervisor = p.WorkerSupervision(dict(budgets=resources.FIXTURE_BUDGETS))
        permit = resources.ExecutionPermit(self.cfg.digest, self.output, self.approval, supervisor,
            self.root/"STOP", self.context, receipt)
        with patch.object(supervisor, "check"):
            permit.check()
            permit.stop_path.touch()
            with self.assertRaises(ValueError): permit.check()
            permit.stop_path.unlink()
            (auth.reservation_path(self.context, self.approval["authorization_id"])/"consumption.json").unlink()
            with self.assertRaises(ValueError): permit.check()


NATIVE_FIXTURE_RESULT = None


@unittest.skipUnless(os.name == "nt", "Native Windows fixture")
class NativeSupervisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=study.ROOT/"tmp", prefix="task2g-native-")
        cls.root, cls.cfg = Path(cls.temp.name), fixture_config()
        cls.context, cls.output, cls.approval = fixture_approval(cls.cfg, cls.root, name="native-success")
        try:
            cls.result = resources.execute(cls.cfg, cls.output, cls.approval, fixture_root=cls.root)
        except BaseException:
            child = cls.context.sidecar_root/cls.output.name/"worker"
            for name in ("stderr.txt", "monitor.json", "worker-result.json"):
                if (child/name).exists(): print(name, (child/name).read_text()[-7000:])
            raise
        cls.monitor = evidence.read_json(cls.context.sidecar_root/cls.output.name/"monitor-result.json")
        cls.summary = evidence.read_json(cls.output/"summary.json")
        global NATIVE_FIXTURE_RESULT
        NATIVE_FIXTURE_RESULT = dict(status=cls.result["status"], fixture_only=True, policy_attempts=16,
            actual_reads=cls.monitor["worker"]["receipt"]["actual_reads"],
            runtime_decodes=cls.monitor["worker"]["receipt"]["runtime_decodes"],
            supervision_verified=cls.monitor["supervision_verified"], samples=cls.monitor["samples"],
            violations=cls.monitor["violations"], sampled_peaks=cls.monitor["sampled_peaks"],
            wall_seconds=cls.monitor["launch_to_exit_wall_seconds"],
            finalization=evidence.read_json(cls.output/evidence.MARKER)["finalization_validation_work"])

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_actual_native_approval_worker_controller_and_two_pass_completion(self):
        self.assertEqual(self.result["status"], "completed-fixture-only")
        self.assertTrue(self.monitor["success"] and self.monitor["supervision_verified"])
        self.assertGreater(self.monitor["samples"], 0)
        self.assertEqual(self.monitor["violations"], [])
        self.assertTrue(self.summary["fixture_only"])
        self.assertEqual(self.monitor["worker"]["receipt"]["arm_attempts"], 16)
        marker = evidence.read_json(self.output/evidence.MARKER)
        self.assertEqual(marker["validation_passes_completed"], 2)
        self.assertEqual(marker["finalization_validation_work"], dict(replay_measurements=64,replay_decodes=32,
            enrollment_reference_readings=2,statistical_samples_added=0))
        self.assertEqual(evidence.audit_evidence(self.output)["status"], "PASS")

    def test_successful_native_approval_cannot_be_reused(self):
        with patch.object(resources, "_execute_reserved") as worker, self.assertRaises(ValueError):
            resources.execute(self.cfg, self.output, self.approval, fixture_root=self.root)
        worker.assert_not_called()
        other = self.output.with_name(study.VERSION+"-unit-another-output")
        changed = dict(self.approval, output_directory=str(other), run_id=other.name)
        with self.assertRaises(ValueError): resources.execute(self.cfg, other, changed, fixture_root=self.root)

    def test_audit_rejects_missing_live_or_altered_bundled_consumption(self):
        live = auth.reservation_path(self.context, self.approval["authorization_id"])/"consumption.json"
        original = live.read_bytes()
        try:
            live.unlink()
            with self.assertRaises(ValueError): evidence.audit_evidence(self.output)
        finally: live.write_bytes(original)
        bundled = self.output/"authorization-consumption.json"
        original = bundled.read_bytes()
        try:
            bundled.write_bytes(b"{}")
            with self.assertRaises(ValueError): evidence.audit_evidence(self.output)
        finally: bundled.write_bytes(original)


def fixture_attestation(directory, token="ack-one"):
    return dict(schema_version=provenance.ACK_VERSION, attestation_id=token,
        attestation_kind="automated-test-attestation", acknowledged_by="automated deterministic fixture; no researcher acknowledgment",
        acknowledged_at=provenance.utc_now(),
        statement="I acknowledge the computed result and certified evidence identified by this record.",
        **provenance.acknowledgment_bindings(directory))


class SelectionProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=study.ROOT/"tmp", prefix="task2g-selection-")
        cls.root, cls.cfg = Path(cls.temp.name), fixture_config()
        cls.output = cls.root/(study.VERSION+"-unit-selection")
        with evidence.EvidenceRun(cls.output, cls.cfg, test_output_root=cls.root) as run: run.execute()
        cls.summary = evidence.read_json(cls.output/"summary.json")
        cls.metadata = evidence.read_json(cls.output/"metadata.json")
        cls.selection = evidence.read_json(cls.output/"selection.json")

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_complete_evidence_and_computed_selection_without_acknowledgment(self):
        status = provenance.selection_status(self.output)
        self.assertEqual(status["calibration_evidence"], "certified-complete")
        self.assertEqual(status["acknowledgment"], "missing")
        self.assertFalse(status["eligible_for_final_planning"] or status["final_evaluation_enabled"])
        with self.assertRaises(ValueError): provenance.require_acknowledged_selection(self.output)

    def test_computation_timestamp_rules_and_all_candidate_bindings(self):
        provenance.validate_computed_selection(self.output, self.summary, self.metadata, self.selection)
        self.assertEqual(len(self.selection["candidates"]), 4)
        self.assertEqual(self.selection["analysis_sha256"], study.object_digest(self.summary["analysis"]))
        self.assertEqual(self.selection["algorithm_version"], provenance.ALGORITHM_VERSION)
        for field in ("computation_timestamp", "analysis_sha256", "plan_sha256", "rules_version"):
            altered = deepcopy(self.selection)
            if field == "computation_timestamp": del altered[field]
            else: altered[field] = "wrong"
            with self.subTest(field=field), self.assertRaises(ValueError):
                provenance.validate_computed_selection(self.output, self.summary, self.metadata, altered)

    def test_altered_candidates_or_selected_sigma_rejected(self):
        for mutation in (lambda x: x["candidates"][0].__setitem__("single_failures", 123),
                         lambda x: x["result"].__setitem__("selected_sigma", .25)):
            altered = deepcopy(self.selection); mutation(altered)
            with self.assertRaises(ValueError): provenance.validate_computed_selection(self.output, self.summary, self.metadata, altered)

    def test_named_dated_acknowledgment_stored_outside_sealed_bundle(self):
        attestation = fixture_attestation(self.output)
        manifest = (self.output/"manifest.json").read_bytes()
        target = provenance.record_acknowledgment(self.output, attestation, fixture_root=self.root)
        self.assertFalse(target.is_relative_to(self.output))
        self.assertEqual((self.output/"manifest.json").read_bytes(), manifest)
        self.assertEqual(provenance.selection_status(self.output, target)["acknowledgment"], "recorded-attestation")

    def test_no_qualification_acknowledged_without_forcing_sigma(self):
        self.assertEqual(self.selection["result"]["status"], "no-qualifying-operating-point")
        self.assertIsNone(self.selection["result"]["selected_sigma"])
        attestation = fixture_attestation(self.output, "ack-no-qualification")
        provenance.validate_acknowledgment(self.output, attestation)
        self.assertIsNone(attestation["selected_sigma"])
        altered = dict(attestation, selected_sigma=.25)
        with self.assertRaises(ValueError): provenance.validate_acknowledgment(self.output, altered)

    def test_missing_mismatched_or_copied_execution_approval_rejected(self):
        _, _, approval = fixture_approval(self.cfg, self.root, name="not-a-selection-signoff")
        with self.assertRaises(ValueError): provenance.validate_acknowledgment(self.output, approval)
        changes_to_check = [dict(acknowledged_by=""), dict(acknowledged_at="2020-01-01T00:00:00+00:00")]
        changes_to_check += [{key:"0"*64} for key in ("config_sha256", "plan_sha256", "source_id", "analysis_sha256",
            "completed_evidence_sha256", "manifest_sha256", "completion_marker_sha256", "selection_sha256")]
        for changes in changes_to_check:
            altered = dict(fixture_attestation(self.output), **changes)
            with self.assertRaises(ValueError): provenance.validate_acknowledgment(self.output, altered)
        with self.assertRaises(FileNotFoundError): provenance.selection_status(self.output, self.root/"missing.json")


CROSS_SIGMA_REFERENCE_RESULT = None


class CrossSigmaReferenceTests(unittest.TestCase):
    def test_independent_non_degenerate_reference_and_common_draws(self):
        # Counts are independently specified sufficient statistics for 8 actual
        # paired outcomes/device/condition; no simulated PUF or scientific data.
        beneficial = ((5,1,3,0),(1,4,0,2),(2,0,5,1),(0,2,1,4))
        harmful = ((1,3,0,4),(3,0,4,1),(0,4,1,3),(4,1,3,0))
        records = {}
        for d in range(4):
            records[f"reference-{d}"] = {c: dict(n=8, single_failures=beneficial[d][i]+1,
                majority_failures=harmful[d][i]+1, population_id=f"group-{d//2}") for i,(c,_) in enumerate(study.CONDITIONS)}
        ids = sorted(records)
        expected_points = {c: sum((Fraction(beneficial[d][i]-harmful[d][i],8) for d in range(4)),Fraction())/4
                           for i,(c,_) in enumerate(study.CONDITIONS)}
        seed = 71829
        rng = Random(seed)
        reference = {c: {k: [] for k in ("single_frr","majority_frr","delta")} for c,_ in study.CONDITIONS}
        reference_weights = []
        for _ in range(10000):
            draw = [rng.randrange(4) for _ in range(4)]
            reference_weights.append(dict(Counter(ids[d] for d in draw)))
            for i,(c,_) in enumerate(study.CONDITIONS):
                s = sum((Fraction(beneficial[d][i]+1,8) for d in draw),Fraction())/4
                m = sum((Fraction(harmful[d][i]+1,8) for d in draw),Fraction())/4
                for key, value in (("single_frr",s),("majority_frr",m),("delta",s-m)):
                    reference[c][key].append(float(value))
        def quantile(values, numerator):
            values = sorted(values)
            position = Fraction(9999*numerator,1000)
            low = position.numerator//position.denominator
            return values[low]+float(position-low)*(values[min(low+1,9999)]-values[low])
        # Observe the real estimator inputs without replacing its calculations.
        with patch.object(analysis,"estimates",wraps=analysis.estimates) as calls:
            actual = analysis.bootstrap_devices(records, seed=seed)
        self.assertEqual(len(calls.call_args_list),10001)
        self.assertEqual([dict(call.args[1]) for call in calls.call_args_list[1:]],reference_weights)
        for c,_ in study.CONDITIONS:
            self.assertEqual(actual["conditions"][c]["delta"]["estimate"], float(expected_points[c]))
            for key in reference[c]:
                self.assertAlmostEqual(actual["conditions"][c][key]["lower"],quantile(reference[c][key],25))
                self.assertAlmostEqual(actual["conditions"][c][key]["upper"],quantile(reference[c][key],975))
        self.assertEqual(actual, analysis.bootstrap_devices(records, seed=seed))
        self.assertTrue(any(actual["conditions"][c]["delta"]["lower"] < actual["conditions"][c]["delta"]["upper"] for c,_ in study.CONDITIONS))
        global CROSS_SIGMA_REFERENCE_RESULT
        CROSS_SIGMA_REFERENCE_RESULT = dict(devices=4,groups=2,trials_per_device_condition=8,resamples=10000,seed=seed,
            paired_point_estimates={c:float(x) for c,x in expected_points.items()},
            common_multiplicities_verified_for_all_10000_draws=True,
            intervals={c: actual["conditions"][c]["delta"] for c,_ in study.CONDITIONS},
            reference="Independent Fraction arithmetic, shared index draws, and order-statistic interpolation; no production estimator/quantile used")


if __name__ == "__main__": unittest.main()
