"""Week 8 unit fixtures only; no formal or nonformal study execution."""
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
from unittest.mock import Mock, patch

from experiments import test_majority3_auth_v1 as oldfixtures
from puf_snn import pipeline_v2
from puf_snn.auth import credential_verifier as admission
from puf_snn.auth.stored_credential import InMemoryStoredCredentialProvider, StoredCredentialRecord
from puf_snn.auth.verifier import Verifier
from puf_snn.puf import acquisition
from puf_snn.reconstruction import BCHCodec, enroll
from puf_snn.experiments import majority3_auth_runtime_v1 as oldruntime
from puf_snn.experiments import three_arm_auth_v1 as study
from puf_snn.experiments import three_arm_auth_runtime_v1 as runtime
from puf_snn.experiments import three_arm_auth_evidence_v1 as evidence


def config(**changes):
    obj = study.StudyConfig.load().to_dict()
    obj.update(mode="unit-test", allocation=dict(populations=1, devices_per_population=1,
                                                attempts_per_device_condition=2))
    obj.update(changes)
    return study.StudyConfig.from_dict(obj)


def execute(cfg, plan, trial, policy, enrollment, **kwargs):
    return runtime.execute_attempt(cfg, trial, policy, enrollment, run_id="unit-fixture",
        source_id="0" * 64, plan_sha256=plan["plan_sha256"], execution_index=0, **kwargs)


class PlanningTests(unittest.TestCase):
    def test_three_sources_deterministic_schedule_and_sample_units(self):
        cfg = config()
        plan = study.compile_plan(cfg)
        self.assertEqual(plan, study.compile_plan(cfg))
        study.validate_plan(cfg, plan)
        self.assertEqual(plan["counts"], dict(matched_trials=10, arm_attempts=30,
            expected_reads=40, expected_runtime_decodes=20, stored_invocations=10,
            independent_populations=1, simulated_devices=1))
        self.assertEqual(len({t["trial_id"] for t in plan["blocks"]}), 10)
        self.assertEqual(len({study.attempt_id(t, p) for t, p, _ in study.scheduled_attempts(plan)}), 30)
        self.assertEqual([i for _, _, i in study.scheduled_attempts(plan)], list(range(30)))
        for trial in plan["blocks"]:
            self.assertEqual(set(trial["policy_order"]), set(study.POLICIES))
            self.assertNotIn("session_seed_sha256", trial)

    def test_formal_planning_only_counts_and_six_order_balance(self):
        with patch.object(runtime, "execute_attempt", side_effect=AssertionError("no execution")):
            plan = study.compile_plan(study.StudyConfig.load())
        self.assertEqual(plan["counts"], dict(matched_trials=30000, arm_attempts=90000,
            expected_reads=120000, expected_runtime_decodes=60000, stored_invocations=30000,
            independent_populations=20, simulated_devices=120))
        cells = {}
        for trial in plan["blocks"]:
            cells.setdefault((trial["device_id"], trial["condition"]), Counter())[
                tuple(trial["policy_order"])] += 1
        self.assertEqual(len({t["trial_id"] for t in plan["blocks"]}), 30000)
        for counts in cells.values():
            self.assertEqual(len(counts), 6)
            self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)

    def test_bounded_nonformal_allocation_without_execution(self):
        cfg = config(mode="nonformal", allocation=dict(populations=1,
                     devices_per_population=1, attempts_per_device_condition=10))
        self.assertEqual(study.compile_plan(cfg)["counts"]["arm_attempts"], 150)
        for n in (2, 12, 50):
            with self.subTest(n=n), self.assertRaises(ValueError):
                config(mode="nonformal", allocation=dict(populations=1,
                       devices_per_population=1, attempts_per_device_condition=n))

    def test_strict_configuration_missing_unknown_and_ambiguous_fields(self):
        original = config().to_dict()
        for field in original:
            changed = deepcopy(original)
            del changed[field]
            with self.subTest(missing=field), self.assertRaises(ValueError):
                study.StudyConfig.from_dict(changed)
        for change in ({"extra": 1}, {"master_seed": True}, {"master_seed": -1},
                       {"master_seed": 2.0}, {"policies": [study.STORED]},
                       {"stored_schedule": "independent-noise-samples"},
                       {"manufacturing_std": float("nan")}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                study.StudyConfig.from_dict(dict(original, **change))
        for section, key, value in (
            ("execution_limits", "formal_execution_enabled", True),
            ("timing_methodology", "warmup_attempts", 20),
            ("authentication", "warmup_iterations", 20),
            ("source_configuration", study.STORED, {})):
            changed = deepcopy(original)
            changed[section][key] = value
            with self.subTest(section=section), self.assertRaises(ValueError):
                study.StudyConfig.from_dict(changed)
        with self.assertRaises(ValueError):
            study.StudyConfig('{"a":1,"a":2}')

    def test_noise_identity_alias_and_plan_tampering(self):
        cfg = config()
        plan = study.compile_plan(cfg)
        for i in range(2):
            a = oldfixtures.trial_for(plan, attempt=i)
            b = oldfixtures.trial_for(plan, "common_control", i)
            for field in ("noise_identity", "noise_shared_seed_sha256", "reading_seed_sha256"):
                self.assertEqual(a[field], b[field])
            self.assertTrue(a["noise_identity"]["noise_domain_id"].startswith(study.VERSION))
            self.assertEqual(len(set(a["reading_seed_sha256"])), 3)
        plan["blocks"][0]["policy_order"].reverse()
        with self.assertRaises(ValueError):
            study.validate_plan(cfg, plan)

    def test_config_detachment_and_new_identity(self):
        a, b = config(), config(manufacturing_std=2)
        self.assertNotEqual(a.digest, b.digest)
        self.assertNotEqual(study.compile_plan(a)["plan_sha256"], study.compile_plan(b)["plan_sha256"])
        detached = a.to_dict()
        detached["manufacturing_std"] = 7
        self.assertEqual(a.to_dict()["manufacturing_std"], 1)

    def test_schemas_have_valid_draft202012_contracts(self):
        for kind in ("config", "plan", "attempt", "summary"):
            schema = study.read_json_bytes(
                (study.ROOT / f"schemas/three-arm-auth-{kind}-v1.schema.json").read_bytes())
            study.Draft202012Validator.check_schema(schema)

    def test_cli_has_no_formal_action_and_plan_is_read_only(self):
        from scripts.run_three_arm_auth_v1 import main
        with patch("sys.argv", ["runner", "plan"]), patch("sys.stdout", new_callable=io.StringIO) as out, \
             patch.object(evidence.EvidenceRun, "execute", side_effect=AssertionError("no execution")):
            main()
        result = json.loads(out.getvalue())
        self.assertFalse(result["formal_execution_enabled"])
        self.assertEqual(result["counts"]["arm_attempts"], 90000)
        with patch("sys.argv", ["runner", "run-formal"]), patch("sys.stderr", new_callable=io.StringIO), \
             self.assertRaises(SystemExit):
            main()


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = config()
        cls.plan = study.compile_plan(cls.config)
        cls.trial = oldfixtures.trial_for(cls.plan)
        cls.enrollment = study.prepare_enrollment(cls.config,
            cls.trial["population_id"], cls.trial["device_id"])

    # Reuse public manufactured-device controls, with real measurements/BCH.
    controlled = oldfixtures.RuntimeTests.controlled

    def run_attempt(self, policy=study.STORED, enrollment=None, **kwargs):
        return execute(self.config, self.plan, self.trial, policy,
            self.controlled() if enrollment is None else enrollment, **kwargs)

    def validate(self, row):
        study.validate_schema("attempt", row)
        self.assertEqual(row["execution_status"], "completed")
        evidence.validate_protocol(row)
        evidence.validate_timing(row)

    def assert_no_release(self, row):
        self.assertFalse(row["establishment"]["session_active"])
        self.assertEqual(row["release_attempts"], 0)
        self.assertEqual(row["callbacks"], {k: dict(invocations=0, completions=0)
            for k in ("preprocessing", "motion", "anomaly")})
        self.assertFalse(any(row["operation_counts"][k] for k in ("sender_hkdf", "receiver_hkdf")))

    def test_real_independent_verification_and_confirmed_release_all_arms(self):
        original = admission.CredentialAdmissionService.verify
        with patch.object(admission.CredentialAdmissionService, "verify",
                          autospec=True, side_effect=original) as verify:
            for policy in study.POLICIES:
                row = self.run_attempt(policy)
                self.validate(row)
                self.assertEqual(row["verification_outcomes"], ["verified"])
                self.assertEqual(row["authorization_outcomes"], [True])
                self.assertEqual(row["admission_outcomes"], ["authorized"])
                self.assertEqual(row["operation_counts"]["verification"], 1)
                self.assertEqual(row["operation_counts"]["authorization"], 1)
                self.assertEqual([h["result"] for h in row["handshake"]], ["accept"] * 4)
                self.assertEqual(row["release_completions"], 1)
        self.assertEqual(verify.call_count, 3)

    def test_stored_zero_acquisition_measurements_votes_and_decodes(self):
        enrollment = self.controlled()
        with patch.object(pipeline_v2, "acquire_response", side_effect=AssertionError("PUF forbidden")) as acquire, \
             patch.object(pipeline_v2, "reconstruct", side_effect=AssertionError("BCH forbidden")) as decode, \
             patch.object(BCHCodec, "decode", side_effect=AssertionError("decode forbidden")) as bch, \
             patch.object(acquisition, "majority_vote3", side_effect=AssertionError("vote forbidden")) as vote, \
             patch.object(runtime.noise, "calculate_frequencies", side_effect=AssertionError("read forbidden")) as read:
            row = self.run_attempt(enrollment=enrollment)
        self.validate(row)
        for spy in (acquire, decode, bch, vote, read):
            spy.assert_not_called()
        self.assertEqual(row["actual_reads"], 0)
        for stage in ("acquisition", "measurement", "reading", "voting", "bch_decode", "reconstruction"):
            self.assertEqual(row["operation_counts"][stage], 0)
            self.assertIsNone(row["stage_duration_ns"][stage])
        self.assertIsNone(row["reconstruction"])
        self.assertEqual(row["retrieval"]["retrieval_outcome"], "success")

    def test_real_puf_cdiw_partition_and_original_acquisition_behavior(self):
        for policy in study.POLICIES[:2]:
            for kind in "CDIW":
                with self.subTest(policy=policy, kind=kind):
                    enrollment = self.controlled()
                    helper = enrollment.helper
                    if kind != "C":
                        if kind == "D":
                            word = (1,) * 6 + (0,) * 57
                        elif kind == "I":
                            word = BCHCodec().encode((0,) * 35 + (1,))
                        else:
                            word = enroll((0,) * 64, bytes(v ^ 255 for v in enrollment.credential),
                                          enrollment_id=helper.enrollment_id).helper_bits
                        response = tuple(a ^ b for a, b in zip(helper.helper_bits, word)) + (0,)
                        enrollment = self.controlled(response)
                    row = self.run_attempt(policy, enrollment)
                    self.validate(row)
                    self.assertEqual(row["reconstruction"]["classification"], kind)
                    self.assertEqual(row["actual_reads"], 1 if policy == study.POLICIES[0] else 3)
                    self.assertEqual(row["operation_counts"]["bch_decode"], 1)
                    self.assertEqual(row["operation_counts"]["voting"], int(policy == study.POLICIES[1]))
                    if kind != "C":
                        self.assert_no_release(row)

    def test_first_read_matching_and_fresh_endpoint_state(self):
        created = []
        original = oldruntime.fresh_pipeline
        def fresh(*args):
            result = original(*args)
            created.append(result[0])
            return result
        with patch.object(oldruntime, "fresh_pipeline", side_effect=fresh):
            rows = {p: self.run_attempt(p) for p in study.POLICIES}
        self.assertEqual(len({id(p.sender) for p in created}), 3)
        self.assertEqual(len({id(p.verifier) for p in created}), 3)
        self.assertEqual(rows[study.POLICIES[0]]["observations"][0],
                         rows[study.POLICIES[1]]["observations"][0])
        self.assertEqual(len({r["enrollment_sha256"] for r in rows.values()}), 1)

    def test_provisioned_bytes_and_cross_device_binding(self):
        enrollment = self.enrollment
        provider = study.stored_provider(enrollment)
        binding = dict(device_id=enrollment.device.device_id,
            enrollment_id=enrollment.helper.enrollment_id,
            reconstruction_id=enrollment.helper.config.version)
        self.assertEqual(provider.get_credential(**binding).credential4, enrollment.credential)
        self.assertIsNone(provider.get_credential(**dict(binding, device_id="other-device")))
        foreign = StoredCredentialRecord("other-device", enrollment.helper.enrollment_id,
                                         enrollment.helper.config.version, enrollment.credential)
        row = self.run_attempt(provider=Mock(get_credential=Mock(return_value=foreign)))
        self.validate(row)
        self.assert_no_release(row)
        self.assertEqual(row["retrieval"]["retrieval_outcome"], "malformed")
        with self.assertRaises(ValueError):
            self.run_attempt(enrollment=replace(enrollment, population_id="other"))

    def test_unavailable_malformed_and_wrong_stored_credentials(self):
        enrollment = self.controlled()
        wrong = StoredCredentialRecord(enrollment.device.device_id,
            enrollment.helper.enrollment_id, enrollment.helper.config.version,
            bytes(v ^ 255 for v in enrollment.credential))
        cases = ((InMemoryStoredCredentialProvider(), "unavailable"),
                 (Mock(get_credential=Mock(return_value=object())), "malformed"),
                 (InMemoryStoredCredentialProvider([wrong]), "success"))
        for provider, outcome in cases:
            row = self.run_attempt(enrollment=enrollment, provider=provider)
            self.validate(row)
            self.assert_no_release(row)
            self.assertEqual(row["retrieval"]["retrieval_outcome"], outcome)
            self.assertIsNone(row["reconstruction"])
            self.assertEqual(row["verification_outcomes"],
                             ["credential_mismatch"] if outcome == "success" else [])

    def test_disabled_policy_and_failed_capability_consumption_all_sources(self):
        for policy in study.POLICIES:
            enrollment = self.controlled()
            disabled = replace(enrollment, verifier_record=replace(enrollment.verifier_record, enabled=False))
            row = self.run_attempt(policy, disabled)
            self.validate(row)
            self.assert_no_release(row)
            self.assertEqual(row["authorization_diagnostics"], ["policy_refusal"])
            with patch.object(admission.CredentialAdmissionService, "consume", return_value=False):
                row = self.run_attempt(policy, enrollment)
            self.validate(row)
            self.assert_no_release(row)

    def test_revocation_after_verification_is_policy_refusal_not_infrastructure_fault(self):
        original = admission.CredentialAdmissionService.verify
        def revoke(owner, candidate, **binding):
            result = original(owner, candidate, **binding)
            owner.revoke_enrollment(binding["device_id"], binding["enrollment_id"])
            return result
        with patch.object(admission.CredentialAdmissionService, "verify", revoke):
            for policy in study.POLICIES:
                row = self.run_attempt(policy)
                self.validate(row)
                self.assert_no_release(row)
                self.assertEqual(row["verification_outcomes"], ["verified"])
                self.assertEqual(row["admission_outcomes"], ["refused"])
                self.assertEqual(row["authorization_diagnostics"], ["policy_refusal"])

    def test_source_and_issuance_faults_are_not_ordinary_false_rejections(self):
        for scope in (
            patch.object(admission, "_Admission", side_effect=RuntimeError("private-secret")),
            patch.object(admission.CredentialAdmissionService, "verify",
                         side_effect=RuntimeError("private-secret"))):
            with scope:
                for policy in study.POLICIES:
                    row = self.run_attempt(policy)
                    self.assertEqual(row["execution_status"], "fault")
                    self.assertNotIn("private-secret", json.dumps(row))
                    with self.assertRaises(ValueError):
                        evidence.validate_protocol(row)
        row = self.run_attempt(provider=Mock(get_credential=Mock(side_effect=RuntimeError("private-secret"))))
        self.assertEqual(row["execution_status"], "fault")
        self.assertEqual(row["retrieval"]["retrieval_outcome"], "infrastructure_error")
        self.assertNotIn("private-secret", json.dumps(row))

    def test_callback_invocation_and_completion_are_separate_on_failure(self):
        original = oldruntime.fresh_pipeline
        def broken(*args):
            pipeline, consumer = original(*args)
            pipeline._motion = Mock(side_effect=RuntimeError("private-secret"))
            return pipeline, consumer
        with patch.object(oldruntime, "fresh_pipeline", side_effect=broken):
            row = self.run_attempt()
        study.validate_schema("attempt", row)
        self.assertEqual(row["execution_status"], "fault")
        self.assertEqual(row["callbacks"]["motion"], dict(invocations=1, completions=0))
        self.assertEqual(row["callbacks"]["anomaly"], dict(invocations=0, completions=0))
        self.assertEqual((row["release_attempts"], row["release_completions"]), (1, 0))

    def test_invalid_hmac_never_releases_for_any_source(self):
        original = Verifier.verify_window
        def tamper(owner, packet, *args, **kwargs):
            obj = json.loads(packet)
            tag = obj["authentication"]["tag_hex"]
            obj["authentication"]["tag_hex"] = ("0" if tag[0] != "0" else "1") + tag[1:]
            return original(owner, study.canonical(obj), *args, **kwargs)
        with patch.object(Verifier, "verify_window", tamper):
            for policy in study.POLICIES:
                row = self.run_attempt(policy)
                self.validate(row)
                self.assertEqual(row["window"]["reason"], "invalid_tag")
                self.assertEqual(row["release_attempts"], 0)

    def test_latest_invocation_cannot_inherit_prepared_attempt_authorization(self):
        enrollment = self.controlled()
        pipeline, _ = oldruntime.fresh_pipeline(self.config, enrollment, study.POLICIES[0])
        self.assertIsInstance(pipeline.sender.begin_stored_attempt(
            study.stored_provider(enrollment), "prepared"), bytes)
        prepared = pipeline.sender.prepared_stored_credential_status
        failure = pipeline.sender.begin_stored_attempt(study.stored_provider(enrollment), "rejected")
        status = pipeline.sender.stored_credential_status
        self.assertEqual(failure.reason, "session_busy")
        self.assertEqual(status.attempt_id, "rejected")
        self.assertEqual(status.preparation_failure, "session_busy")
        self.assertIsNone(status.verification_outcome)
        self.assertEqual(status.admission_outcome, "not_invoked")
        self.assertIs(pipeline.sender.prepared_stored_credential_status, prepared)

    def test_shared_instrumentation_lock_restoration_and_thread_guard(self):
        original = admission.CredentialAdmissionService.authorize_with_outcome
        with self.assertRaises(RuntimeError):
            with runtime.instrument(runtime.Capture()):
                raise RuntimeError("fixture")
        self.assertIs(admission.CredentialAdmissionService.authorize_with_outcome, original)
        capture = runtime.Capture()
        errors = []
        with runtime.instrument(capture):
            with self.assertRaises(ValueError):
                with oldruntime.instrument(oldruntime.Capture()):
                    pass
            def worker():
                try:
                    capture.open("retrieval")
                except ValueError:
                    errors.append(True)
            thread = Thread(target=worker)
            thread.start()
            thread.join()
        self.assertEqual(errors, [True])

    def test_formal_runtime_rejected_before_provisioning_or_source_work(self):
        cfg = study.StudyConfig.load()
        with patch.object(study, "stored_provider", side_effect=AssertionError("no provisioning")):
            with self.assertRaisesRegex(ValueError, "formal"):
                execute(cfg, self.plan, self.trial, study.STORED, self.enrollment)


    def test_exact_next_replay_rule_applies_to_every_source(self):
        for policy in study.POLICIES:
            enrollment = self.controlled()
            pipeline, _ = oldruntime.fresh_pipeline(self.config, enrollment,
                study.POLICIES[0] if policy == study.STORED else policy)
            if policy == study.STORED:
                result = pipeline.establish_stored(study.stored_provider(enrollment), "replay-test")
            else:
                reader = runtime.noise.CorrelatedResponseReader(enrollment.device,
                    study.trial_noise_config(self.trial),
                    runtime.noise.AttemptIdentity(**self.trial["noise_identity"]),
                    study.previous.POLICIES[policy])
                result = pipeline.establish(reader, "replay-test")
            self.assertTrue(result.session_active)
            packet = pipeline.sender.seal_window(oldruntime.fixed_window())
            self.assertEqual(pipeline.process_envelope(packet).decision, "accept")
            duplicate = pipeline.process_envelope(packet)
            self.assertEqual((duplicate.decision, duplicate.reason), ("reject", "duplicate_sequence"))
            self.assertEqual(pipeline.calls.preprocessing, 1)
            self.assertEqual(pipeline.calls.motion, 1)
            self.assertEqual(pipeline.calls.anomaly, 1)


class EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = TemporaryDirectory(prefix="week8-three-arm-tests-", dir=study.ROOT / "tmp")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name) / (evidence.TEST_PREFIX + "bundle")
        cls.config = config()
        with evidence.EvidenceRun(cls.directory, cls.config, test_output_root=Path(cls.temp.name)) as run:
            cls.receipt = run.execute()
            cls.rows, cls.plan, cls.catalog = deepcopy(run.rows), run.plan, run.catalog
            cls.context = {k: run.metadata[k] for k in ("run_id", "source_id")}

    def check(self, rows=None, catalog=None):
        return evidence.reconcile(self.config, self.plan,
            self.rows if rows is None else rows, self.catalog if catalog is None else catalog, self.context)

    def clone(self):
        temporary = self.enterContext(TemporaryDirectory(dir=study.ROOT / "tmp"))
        target = Path(temporary) / "copy"
        shutil.copytree(self.directory, target)
        return target

    def rehash(self, directory):
        manifest = evidence.read_json(directory / "manifest.json")
        for relative in manifest:
            manifest[relative] = evidence.file_digest(directory / relative)
        (directory / "manifest.json").write_bytes(study.canonical(manifest))
        marker = directory / "UNIT_TEST_VALIDATED.json"
        value = evidence.read_json(marker)
        value["manifest_sha256"] = evidence.file_digest(directory / "manifest.json")
        marker.write_bytes(study.canonical(value))

    def test_complete_unit_fixture_audits_all_three_sources(self):
        self.assertEqual(evidence.audit_evidence(self.directory), self.receipt)
        self.assertEqual(self.receipt["arm_attempts"], 30)
        self.assertEqual(self.receipt["matched_trials"], 10)
        self.assertEqual(self.receipt["actual_reads"], 40)
        self.assertEqual(self.receipt["runtime_decodes"], 20)
        self.assertEqual(self.receipt["stored_invocations"], 10)
        self.assertFalse((self.directory / "COMPLETE").exists())
        self.assertFalse((self.directory / "NONFORMAL_VALIDATED.json").exists())

    def test_missing_duplicate_extra_and_misordered_rows_rejected(self):
        for rows in (self.rows[:-1], self.rows + [self.rows[0]],
                     list(reversed(self.rows)), [self.rows[0]] * len(self.rows)):
            with self.assertRaises(ValueError):
                self.check(rows)
        rows = deepcopy(self.rows)
        rows[0] = {}
        with self.assertRaises(ValueError):
            self.check(rows)

    def test_identity_source_count_and_fault_tampering_rejected(self):
        for field, value in (
            ("source_id", "f" * 64), ("config_sha256", "f" * 64),
            ("enrollment_sha256", "f" * 64), ("device_id", "other-device"),
            ("actual_reads", 9), ("release_attempts", 99),
            ("unauthorized_release_count", 1), ("fault_code", "infrastructure_error"),
            ("timing", []), ("execution_status", "fault")):
            rows = deepcopy(self.rows)
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(rows)
        rows = deepcopy(self.rows)
        rows[0]["credential_source"] = next(p for p in study.POLICIES if p != rows[0]["policy"])
        with self.assertRaises(ValueError):
            self.check(rows)

    def test_stored_never_claims_reconstruction_or_prior_invocation_success(self):
        for field, value in (
            ("reconstruction", next(r["reconstruction"] for r in self.rows if r["reconstruction"])),
            ("effective_response", [0] * 64)):
            rows = deepcopy(self.rows)
            row = next(r for r in rows if r["policy"] == study.STORED)
            row[field] = value
            with self.assertRaises(ValueError):
                self.check(rows)
        for key, value in (("attempt_id", "f" * 64), ("verification_outcome", None),
                           ("admission_outcome", "not_invoked")):
            rows = deepcopy(self.rows)
            row = next(r for r in rows if r["policy"] == study.STORED)
            row["retrieval"][key] = value
            row["establishment"]["credential_status"] = deepcopy(row["retrieval"])
            with self.assertRaises(ValueError):
                self.check(rows)

    def test_replay_timing_operations_and_callback_contradictions_rejected(self):
        for variant in ("response", "decoder", "timing-parent", "timing-duration", "operation-count", "callback"):
            rows = deepcopy(self.rows)
            row = next(r for r in rows if r["policy"] != study.STORED)
            if variant == "response":
                row["observations"][0]["response"][0] ^= 1
            elif variant == "decoder":
                row["reconstruction"]["corrections"] = (row["reconstruction"]["corrections"] + 1) % 6
            elif variant == "timing-parent":
                row["timing"][1]["parent_id"] = None
            elif variant == "timing-duration":
                row["timing"][0]["duration_ns"] = 0
            elif variant == "operation-count":
                row["operation_counts"]["bch_decode"] = 0
            else:
                row["callbacks"]["motion"]["completions"] = 99
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                self.check(rows)

    def test_catalog_requires_the_deterministic_device_enrollment(self):
        catalog = deepcopy(self.catalog)
        catalog[next(iter(catalog))]["manufacturing_sha256"] = "f" * 64
        with self.assertRaises(ValueError):
            self.check(catalog=catalog)

    def test_source_specific_summary_denominators_and_no_intervals(self):
        summary = evidence.read_json(self.directory / "summary.json")
        self.assertEqual(summary["independent_populations"], 1)
        self.assertEqual(summary["interval_status"], "not-computed-nonformal")
        for key, group in summary["groups"].items():
            self.assertEqual(group["completed_attempts"], 2)
            if key.endswith(study.STORED):
                self.assertIsNone(group["reconstruction_outcomes"])
                self.assertIsNone(group["reconstruction_frr"])
                self.assertEqual(sum(group["retrieval_outcomes"].values()), 2)
                self.assertIsNone(group["timing"]["bch_decode"]["inclusive"]["p95_ns"])
            else:
                self.assertEqual(sum(group["reconstruction_outcomes"].values()), 2)
                self.assertIsNone(group["retrieval_failure_rate"])
            selected = [r for r in self.rows if r["condition"] + "|" + r["policy"] == key]
            durations = [r["stage_duration_ns"]["establishment"] for r in selected]
            self.assertEqual(group["all_attempt_establishment"], evidence.duration_summary(durations))

    def test_manifest_closure_incomplete_missing_marker_and_rehashed_tampering(self):
        for variant in ("missing", "extra", "changed", "incomplete", "marker", "rehashed"):
            directory = self.clone()
            if variant == "missing":
                (directory / "summary.json").unlink()
            elif variant == "extra":
                (directory / "extra.json").write_text("{}")
            elif variant == "changed":
                (directory / "summary.json").write_text("{}")
            elif variant == "incomplete":
                (directory / "INCOMPLETE.json").write_text("{}")
            elif variant == "marker":
                (directory / "UNIT_TEST_VALIDATED.json").unlink()
            else:
                rows = deepcopy(self.rows)
                rows[0]["release_attempts"] = 99
                (directory / "attempts.jsonl").write_bytes(
                    b"\n".join(study.canonical(row) for row in rows) + b"\n")
                self.rehash(directory)
            with self.subTest(variant=variant), self.assertRaises((ValueError, FileNotFoundError)):
                evidence.audit_evidence(directory)

    def test_source_snapshot_and_metadata_tampering_even_when_manifest_rehashed(self):
        directory = self.clone()
        source = directory / "source/src/python/puf_snn/puf/device.py"
        source.write_bytes(source.read_bytes() + b"\n# changed\n")
        self.rehash(directory)
        with self.assertRaises(ValueError):
            evidence.audit_evidence(directory)
        directory = self.clone()
        metadata = evidence.read_json(directory / "metadata.json")
        metadata["timing_methodology"]["warmup_attempts"] = 1
        (directory / "metadata.json").write_bytes(study.canonical(metadata))
        self.rehash(directory)
        with self.assertRaises(ValueError):
            evidence.audit_evidence(directory)

    def test_exclusive_namespace_historical_paths_and_formal_guards(self):
        with self.assertRaises(ValueError):
            evidence.EvidenceRun(self.directory, self.config, test_output_root=self.directory.parent)
        with self.assertRaisesRegex(ValueError, "formal"):
            evidence.EvidenceRun(self.directory / "never", study.StudyConfig.load())
        for path in (study.ROOT / "results/week-7" / (evidence.RUN_PREFIX + "bad"),
                     study.ROOT / "results/week-5" / (evidence.TEST_PREFIX + "bad"),
                     evidence.NONFORMAL_ROOT / ".." / (evidence.RUN_PREFIX + "bad")):
            with self.assertRaises(ValueError):
                evidence.checked_output_path(path, "nonformal")
        cfg = config(mode="nonformal", allocation=dict(populations=1,
                     devices_per_population=1, attempts_per_device_condition=10))
        with self.assertRaisesRegex(ValueError, "authorization"):
            evidence.EvidenceRun(self.directory / "never", cfg)

    def test_interruption_infrastructure_fault_and_malformed_append_never_complete(self):
        for variant in ("interruption", "fault", "malformed"):
            temporary = self.enterContext(TemporaryDirectory(dir=study.ROOT / "tmp"))
            directory = Path(temporary) / (evidence.TEST_PREFIX + variant)
            with self.assertRaises((ValueError, RuntimeError)):
                with evidence.EvidenceRun(directory, self.config, test_output_root=Path(temporary)) as run:
                    if variant == "interruption":
                        raise RuntimeError("fixture")
                    if variant == "malformed":
                        run.append({})
                    else:
                        original = evidence.execute_attempt
                        def fault(*args, **kwargs):
                            row = original(*args, **kwargs)
                            row.update(execution_status="fault", fault_code="fixture_fault")
                            return row
                        with patch.object(evidence, "execute_attempt", side_effect=fault):
                            run.execute()
            self.assertTrue((directory / "INCOMPLETE.json").exists())
            self.assertFalse((directory / "UNIT_TEST_VALIDATED.json").exists())

    def test_public_records_do_not_contain_credential_key_or_capability_fields(self):
        forbidden = {"credential", "credential4", "candidate_credential", "verifier_key",
                     "session_key", "authorization_capability", "key_provider"}
        def walk(value):
            if isinstance(value, dict):
                self.assertFalse(set(value) & forbidden)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(self.rows)
        walk(self.catalog)


if __name__ == "__main__":
    unittest.main()
