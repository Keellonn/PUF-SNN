"""Nonfinal literal fixtures: real BCH replay, no acquisition or reserved RNG draws."""

from copy import deepcopy
from dataclasses import asdict, replace
from hashlib import sha256
import json
import pickle
from types import MappingProxyType
import unittest
from unittest.mock import patch

from puf_snn.auth.stored_credential import StoredCredentialRecord
from puf_snn.reconstruction import BCHCodec, ReconstructionResult, enroll, reconstruct
from puf_snn.experiments import shared_noise_final_reconciliation_v1 as recon
from puf_snn.experiments import shared_noise_final_plan_v1 as planning
from puf_snn.experiments import shared_noise_final_analysis_v1 as analysis
from puf_snn.experiments import shared_noise_final_measurement_v1 as measurement

S, M, T = planning.POLICIES
ZERO = (0,)*64
CONFIG = sha256(b"isolated-reconciliation-config").hexdigest()
PLAN = sha256(b"isolated-reconciliation-plan").hexdigest()
SOURCE = sha256(b"isolated-reconciliation-source").hexdigest()
RUN = "isolated-reconciliation-fixture"


def envelope(row):
    raw = planning.canonical(row)
    return recon.RecordedExecution(raw, sha256(raw).hexdigest())


def parsed(record):
    return planning.read_json(record.raw)


def changed(records, index, mutate):
    result = list(records)
    row = parsed(result[index])
    mutate(row)
    result[index] = envelope(row)  # Rehashing a false claim must not make it trusted.
    return result


def metadata_schedule():
    """Six fixed profiles, one synthetic device/trial, no random calls or final streams."""
    bindings, blocks = [], []
    operating = None
    for c, (condition, sigma, rho, domain) in enumerate(planning.CONDITIONS):
        identity = planning.noise.AttemptIdentity(9173, "fixture-group", "fixture-device",
                                                "isolated-reconciliation:"+domain, 0)
        common = c == 5
        block = dict(schema_version=planning.VERSION+":planned-block", experiment_id=planning.VERSION,
            config_sha256=CONFIG, population_id="fixture-group", device_id="fixture-device",
            enrollment_id="fixture-device-enrollment", condition=condition, attempt_index=0,
            sigma=sigma, rho=rho, common_offset=1 if common else 0, noise_identity=asdict(identity),
            noise_shared_seed_sha256=planning.seed_digest(identity, planning.noise.SESSION),
            reading_seed_sha256=[planning.seed_digest(identity, planning.noise.READING, i) for i in range(3)],
            common_offset_seed_sha256=planning.seed_digest(identity, planning.noise.COMMON_MODE) if common else None,
            linked_operating_trial_id=operating if common else None)
        block["trial_id"] = planning.trial_id(block)
        if c == 0:
            operating = block["trial_id"]
        block.update(policy_order=[S, M, T], block_index=c)
        block["attempts"] = []
        for p, policy in enumerate((S, M, T)):
            indices = {S: [0], M: [0, 1, 2], T: []}[policy]
            block["attempts"].append(dict(schema_version=planning.VERSION+":planned-attempt",
                experiment_id=planning.VERSION, condition=condition, trial_id=block["trial_id"], policy=policy,
                policy_attempt_id=planning.attempt_id(block, policy), execution_index=3*c+p,
                reading_indices=indices, noise_shared_seed_sha256=block["noise_shared_seed_sha256"] if indices else None,
                reading_seed_sha256=[block["reading_seed_sha256"][i] for i in indices]))
        bindings.extend(recon.block_bindings(CONFIG, PLAN, block))
        blocks.append(block)
    return tuple(bindings), dict(blocks=blocks, config_sha256=CONFIG, plan_sha256=PLAN)


class IndependentFixtureInputs:
    """Hand-constructed source data, never read from the record under validation."""

    def __init__(self, inputs):
        self._inputs = MappingProxyType(dict(inputs))
        self.calls = []

    def inputs_for(self, planned):
        self.calls.append(planned.identity)
        return self._inputs[planned.identity]


class Fixture:
    def __init__(self, material, *, responses=None, stored=None):
        self.bindings, self.plan = metadata_schedule()
        self.index = recon.ScheduleIndex(self.bindings)
        self.material = material
        self.inputs, self.records = {}, []
        for binding in self.bindings:
            obj = binding.to_dict()
            b, a = obj["block"], obj["attempt"]
            policy = a["policy"]
            key = b["condition"], policy
            bits = (responses or {}).get(key, ZERO)
            reads = () if policy == T else (bits,)*(1 if policy == S else 3)
            stored_value = (stored or {}).get(b["condition"], StoredCredentialRecord(
                material.device_id, material.enrollment_id, material.helper.config.version, material.credential)) if policy == T else None
            self.inputs[binding.identity] = recon.ReplayInputs(binding.digest, RUN, SOURCE, material, reads, stored_value)
            effective = None if policy == T else bits
            decoded = None if policy == T else reconstruct(effective, material.helper)
            retrieval = None
            if policy == T:
                retrieval = "unavailable" if stored_value is None else "success" if type(stored_value) is StoredCredentialRecord else "malformed"
            self.records.append(envelope(dict(schema_version=recon.VERSION+":record", planned=obj,
                run_id=RUN, source_id=SOURCE, enrollment_sha256=material.public_digest, state="completed", fault_code=None,
                operations=recon.expected_operations(policy), readings=[dict(index=i, response=list(r),
                    response_sha256=planning.object_digest(r), input_seed_sha256=a["reading_seed_sha256"][i]) for i, r in enumerate(reads)],
                effective_response=list(effective) if effective is not None else None,
                effective_sha256=planning.object_digest(effective) if effective is not None else None,
                decoder=recon.decoder_record(decoded) if decoded is not None else None, retrieval_outcome=retrieval,
                downstream=dict(verification="not_invoked", admission="not_invoked", session_active=False,
                                authorized_releases=0, inference_calls=0))))

    def verifier(self, inputs=None):
        provider = IndependentFixtureInputs(self.inputs if inputs is None else inputs)
        return recon.ReplayVerifier(provider, run_id=RUN, source_id=SOURCE), provider

    def reconcile(self, records=None, inputs=None):
        verifier, provider = self.verifier(inputs)
        assessment = recon.reconcile_ledger(self.index, iter(self.records if records is None else records), verifier=verifier)
        return assessment, verifier, provider


class ReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Fixed literals, not generated credentials or enrollment/noise streams.
        helper = enroll(ZERO, b"ABCD", enrollment_id="fixture-device-enrollment")
        cls.material = recon.EnrollmentMaterial("fixture-group", "fixture-device", helper.enrollment_id, ZERO, helper, b"ABCD")
        cls.fixture = Fixture(cls.material)
        codec = BCHCodec()
        def response(message):
            word = codec.encode(message)
            return tuple(h ^ w for h, w in zip(helper.helper_bits, word))+(0,)
        cls.wrong = response(tuple((byte >> s) & 1 for byte in b"WXYZ" for s in range(7, -1, -1))+(0,)*4)
        cls.invalid = response((0,)*35+(1,))
        cls.failure = (1,)*6+(0,)*58
        assert reconstruct(cls.failure, helper).outcome == "decoder_failure"

    def issue_codes(self, assessment):
        return {code for _, code in assessment.issues}

    def test_successful_local_reconciliation_and_analysis_projection(self):
        result, verifier, provider = self.fixture.reconcile()
        self.assertTrue(result.verified_scope_complete)
        self.assertEqual(result.counts, dict(planned=18, records=18, started=18, completed=18, pending=0,
            faulted=0, missing=0, duplicate=0, unknown=0, locally_verified=18))
        self.assertEqual(result.issues, ())
        self.assertEqual((result.replay_decodes, result.enrollment_check_decodes), (12, 1))
        self.assertEqual(len(provider.calls), 18)
        self.assertTrue(all(type(o) is analysis.AttemptOutcome for o in result.local_outcomes))
        self.assertEqual([o.policy for o in result.local_outcomes], [S, M, T]*6)
        diagnostics = analysis.coverage_diagnostics(self.fixture.plan, result.local_outcomes)
        self.assertTrue(all(diagnostics[k] == [] for k in ("missing", "duplicate", "unknown", "mismatched", "incomplete")))
        for outcome in result.local_outcomes:
            self.assertEqual((outcome.config_sha256, outcome.plan_sha256), (CONFIG, PLAN))
            if outcome.policy == T:
                self.assertIsNone(outcome.reconstruction)
                self.assertEqual(outcome.retrieval_outcome, "success")
            else:
                self.assertEqual(outcome.reconstruction.category, "C")

    def test_existing_decoder_replay_distinguishes_c_d_i_w(self):
        profiles = {planning.CONDITIONS[i][0]: bits for i, bits in enumerate((ZERO, self.failure, self.invalid, self.wrong))}
        profiles[planning.CONDITIONS[5][0]] = ZERO
        fixture = Fixture(self.material, responses={(c, p): bits for c, bits in profiles.items() for p in (S, M)})
        result, _, _ = fixture.reconcile()
        self.assertTrue(result.verified_scope_complete, result.issues)
        self.assertEqual([o.reconstruction.category for o in result.local_outcomes if o.policy == S], ["C", "D", "I", "W", "C", "C"])
        self.assertEqual([o.reconstruction.failure for o in result.local_outcomes if o.policy == S], [0, 1, 1, 1, 0, 0])

    def test_claimed_categories_and_fake_replay_booleans_are_rejected(self):
        for mutate in (lambda r: r.update(classification="C"),
                       lambda r: r["decoder"].update(classification="C"),
                       lambda r: r.update(replay_passed=True)):
            result, _, provider = self.fixture.reconcile(changed(self.fixture.records, 0, mutate))
            self.assertFalse(result.verified_scope_complete)
            self.assertEqual(result.local_outcomes, ())
            self.assertEqual(provider.calls, [])
        with self.assertRaisesRegex(recon.ReconciliationError, "replay-verifier-required"):
            recon.reconcile_ledger(self.fixture.index, self.fixture.records, verifier=True)
        with self.assertRaises(TypeError):
            recon.VerifiedFacts()

    def test_forged_existing_result_does_not_control_wrong_credential_classification(self):
        fixture = Fixture(self.material, responses={(c[0], p): self.wrong for c in planning.CONDITIONS for p in (S, M)})
        decoded = reconstruct(self.wrong, self.material.helper)
        forged = replace(decoded, candidate_credential=self.material.credential)
        self.assertIs(type(forged), ReconstructionResult)
        records = changed(fixture.records, 0, lambda r: r.update(decoder=recon.decoder_record(forged)))
        result, _, _ = fixture.reconcile(records)
        self.assertTrue(result.verified_scope_complete)
        self.assertEqual(result.local_outcomes[0].reconstruction.category, "W")

    def test_stored_success_unavailable_and_malformed_have_null_reconstruction(self):
        fixture = Fixture(self.material, stored={planning.CONDITIONS[0][0]: None, planning.CONDITIONS[1][0]: b"malformed-source-data"})
        result, _, _ = fixture.reconcile()
        self.assertTrue(result.verified_scope_complete)
        stored = [o for o in result.local_outcomes if o.policy == T]
        self.assertEqual([o.retrieval_outcome for o in stored], ["unavailable", "malformed"]+["success"]*4)
        self.assertTrue(all(o.reconstruction is None for o in stored))

    def test_stored_requires_explicit_source_result_and_zero_puf_operations(self):
        for mutate in (lambda r: r.update(retrieval_outcome=None),
                       lambda r: r.update(decoder=recon.decoder_record(reconstruct(ZERO, self.material.helper))),
                       lambda r: r.update(effective_response=list(ZERO)),
                       lambda r: r["operations"].update(readings=1),
                       lambda r: r["operations"].update(votes=1),
                       lambda r: r["operations"].update(bch_decodes=1),
                       lambda r: r["operations"].update(stored_retrievals=0)):
            with self.subTest(mutate=mutate):
                result, _, _ = self.fixture.reconcile(changed(self.fixture.records, 2, mutate))
                self.assertFalse(result.verified_scope_complete)
                self.assertFalse(any(o.execution_index == 2 for o in result.local_outcomes))

    def test_all_planned_identity_fields_are_exactly_bound(self):
        mutations = [lambda r: r["planned"].update(config_sha256="f"*64),
            lambda r: r["planned"].update(plan_sha256="f"*64),
            lambda r: r["planned"]["block"].update(experiment_id="calibration"),
            lambda r: r["planned"]["block"].update(population_id="wrong-group"),
            lambda r: r["planned"]["block"].update(device_id="wrong-device"),
            lambda r: r["planned"]["block"].update(enrollment_id="wrong-enrollment"),
            lambda r: r["planned"]["block"].update(condition=planning.CONDITIONS[1][0]),
            lambda r: r["planned"]["block"].update(attempt_index=1),
            lambda r: r["planned"]["block"].update(trial_id="f"*64),
            lambda r: r["planned"]["attempt"].update(policy=M),
            lambda r: r["planned"]["attempt"].update(execution_index=99),
            lambda r: r["planned"]["attempt"].update(execution_index=False),
            lambda r: r["planned"]["attempt"].update(reading_indices=[1]),
            lambda r: r["planned"]["attempt"].update(reading_seed_sha256=["f"*64]),
            lambda r: r["planned"]["block"].update(linked_operating_trial_id="f"*64)]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                result, _, provider = self.fixture.reconcile(changed(self.fixture.records, 0, mutation))
                self.assertIn("planned-binding-conflict", self.issue_codes(result))
                self.assertEqual(provider.calls, [])

    def test_run_source_enrollment_and_stored_material_are_not_verified_by_hash_alone(self):
        for key, value in (("run_id", "other-run"), ("source_id", "f"*64), ("enrollment_sha256", "f"*64)):
            result, _, _ = self.fixture.reconcile(changed(self.fixture.records, 0,
                lambda r, k=key, v=value: r.update({k: v})))
            self.assertFalse(result.verified_scope_complete)
            self.assertEqual(result.local_outcomes, ())
        inputs = dict(self.fixture.inputs)
        identity = self.fixture.bindings[2].identity
        inputs[identity] = replace(inputs[identity], stored_record=StoredCredentialRecord(
            self.material.device_id, self.material.enrollment_id, self.material.helper.config.version, b"WXYZ"))
        result, _, _ = self.fixture.reconcile(inputs=inputs)
        self.assertIn("stored-enrollment-credential-mismatch", self.issue_codes(result))
        self.assertFalse(any(o.execution_index == 2 for o in result.local_outcomes))

    def test_missing_duplicate_unknown_records_and_execution_order(self):
        records = self.fixture.records
        missing, _, _ = self.fixture.reconcile(records[:-1])
        self.assertEqual((missing.counts["missing"], missing.counts["completed"]), (1, 17))
        self.assertIn((self.fixture.bindings[-1].identity, "missing-attempt-record"), missing.issues)
        duplicate, _, _ = self.fixture.reconcile(records+[records[0]])
        self.assertEqual(duplicate.counts["duplicate"], 1)
        self.assertFalse(any(o.policy_attempt_id == self.fixture.bindings[0].identity for o in duplicate.local_outcomes))
        unknown, _, _ = self.fixture.reconcile(changed(records, 0, lambda r: r["planned"]["attempt"].update(policy_attempt_id="f"*64)))
        self.assertEqual((unknown.counts["unknown"], unknown.counts["missing"]), (1, 1))
        reordered = [records[1], records[0]]+records[2:]
        result, _, _ = self.fixture.reconcile(reordered)
        self.assertIn("ledger-execution-order-conflict", self.issue_codes(result))
        for result in (missing, duplicate, unknown, result):
            self.assertFalse(result.verified_scope_complete)

    def test_operation_counts_for_each_policy_and_strict_integer_types(self):
        for index in (0, 1, 2):
            for key in recon.OPERATIONS:
                for amount in (0, 99, True, 1.0):
                    expected = parsed(self.fixture.records[index])["operations"][key]
                    if type(amount) is int and amount == expected:
                        continue
                    with self.subTest(policy=index, key=key, amount=amount):
                        result, _, _ = self.fixture.reconcile(changed(self.fixture.records, index,
                            lambda r, k=key, v=amount: r["operations"].update({k: v})))
                        self.assertFalse(result.verified_scope_complete)

    def test_response_hash_seed_vote_and_decoder_disagreements(self):
        changes = [lambda r: r["readings"][0]["response"].__setitem__(0, 1),
            lambda r: r["readings"][0].update(response_sha256="f"*64),
            lambda r: r["readings"][0].update(input_seed_sha256="f"*64),
            lambda r: r["readings"][0].update(index=1),
            lambda r: r["effective_response"].__setitem__(0, 1),
            lambda r: r.update(effective_sha256="f"*64),
            lambda r: r["decoder"].update(outcome="decoder_failure"),
            lambda r: r["decoder"].update(reported_correction_count=1)]
        for mutate in changes:
            with self.subTest(mutate=mutate):
                result, _, _ = self.fixture.reconcile(changed(self.fixture.records, 0, mutate))
                self.assertFalse(result.verified_scope_complete)
                self.assertEqual(result.local_outcomes, ())
        # M's supplied effective response must be its actual three-reading vote.
        records = changed(self.fixture.records, 1, lambda r: r.update(effective_response=[1]*64,
                                                                 effective_sha256=planning.object_digest((1,)*64)))
        result, _, _ = self.fixture.reconcile(records)
        self.assertIn("effective-response-mismatch", self.issue_codes(result))

    def test_nontrivial_majority_vote_is_replayed_from_three_distinct_readings(self):
        first = (1,)+(0,)*63
        second = (0, 1)+(0,)*62
        voted = (1, 1)+(0,)*62
        records, inputs = list(self.fixture.records), dict(self.fixture.inputs)
        for index in (0, 1, 15, 16):  # Operating and common S/M retain their matching.
            binding = self.fixture.bindings[index]
            a = binding.to_dict()["attempt"]
            readings = (first,) if a["policy"] == S else (first, second, voted)
            effective = first if a["policy"] == S else voted  # Independent hand-computed vote.
            inputs[binding.identity] = replace(inputs[binding.identity], readings=readings)
            row = parsed(records[index])
            row.update(readings=[dict(index=i, response=list(bits), response_sha256=planning.object_digest(bits),
                input_seed_sha256=a["reading_seed_sha256"][i]) for i, bits in enumerate(readings)],
                effective_response=list(effective), effective_sha256=planning.object_digest(effective),
                decoder=recon.decoder_record(reconstruct(effective, self.material.helper)))
            records[index] = envelope(row)
        result, _, _ = self.fixture.reconcile(records, inputs)
        self.assertTrue(result.verified_scope_complete, result.issues)
        self.assertEqual(parsed(records[1])["decoder"]["reported_correction_count"], 2)
        self.assertEqual(result.local_outcomes[1].reconstruction.category, "C")

    def test_rho1_reading_identity_and_cross_arm_reading_zero(self):
        fixture = Fixture(self.material)
        identity = fixture.bindings[10].identity  # rho1 M
        inputs = dict(fixture.inputs)
        inputs[identity] = replace(inputs[identity], readings=(ZERO, (1,)*64, ZERO))
        records = changed(fixture.records, 10, lambda r: r["readings"][1].update(response=[1]*64,
            response_sha256=planning.object_digest((1,)*64)))
        result, _, _ = fixture.reconcile(records, inputs)
        self.assertIn("rho1-reading-identity-mismatch", self.issue_codes(result))
        # Bit 63 is ignored by BCH; it still must match across the two sources.
        bits = ZERO[:-1]+(1,)
        identity = fixture.bindings[1].identity
        inputs = dict(fixture.inputs)
        inputs[identity] = replace(inputs[identity], readings=(bits, ZERO, ZERO))
        records = changed(fixture.records, 1, lambda r: r["readings"][0].update(response=list(bits),
            response_sha256=planning.object_digest(bits)))
        result, _, provider = fixture.reconcile(records, inputs)
        self.assertIn("matched-reading-zero-mismatch", self.issue_codes(result))
        self.assertEqual(len(provider.calls), 2)  # No further replay after detection.

    def test_common_control_mismatch_is_integrity_fault_not_scientific_outcome(self):
        bits = ZERO[:-1]+(1,)
        fixture = Fixture(self.material, responses={(planning.CONDITIONS[5][0], p): bits for p in (S, M)})
        result, _, provider = fixture.reconcile()
        self.assertIn("common-control-identity-mismatch", self.issue_codes(result))
        self.assertFalse(result.verified_scope_complete)
        self.assertEqual(len(provider.calls), 16)  # Stops at common S, before M or T replay.

    def test_numerical_infrastructure_resource_and_integrity_faults_remain_faults(self):
        for fault in ("numerical_comparison", "infrastructure", "resource", "integrity", "operator_stop"):
            records = changed(self.fixture.records, 0, lambda r: r.update(state="fault", fault_code=fault))
            result, _, provider = self.fixture.reconcile(records)
            self.assertEqual((result.counts["faulted"], result.counts["completed"]), (1, 17))
            self.assertIn("fault:"+fault, self.issue_codes(result))
            self.assertEqual(result.local_outcomes, ())
            self.assertEqual(provider.calls, [])

    def test_incomplete_pending_and_started_counts_do_not_infer_success(self):
        for state in ("pending", "started"):
            records = changed(self.fixture.records, 0, lambda r: r.update(state=state,
                operations=dict.fromkeys(recon.OPERATIONS, 0), readings=[], effective_response=None,
                effective_sha256=None, decoder=None))
            result, _, provider = self.fixture.reconcile(records)
            self.assertEqual(result.counts["pending"], 1)
            self.assertEqual(result.counts["started"], 17 if state == "pending" else 18)
            self.assertEqual(result.local_outcomes, ())
            self.assertEqual(provider.calls, [])
            self.assertIn("incomplete-attempt-record", self.issue_codes(result))
        absent, _, _ = self.fixture.reconcile([])
        self.assertEqual(absent.counts["missing"], 18)
        self.assertEqual(absent.counts["completed"], 0)

    def test_schema_hash_and_source_verification_are_separate(self):
        result = recon.reconcile_ledger(self.fixture.index, self.fixture.records)
        summary = result.summary()
        self.assertFalse(result.verified_scope_complete)
        self.assertEqual(result.local_outcomes, ())
        self.assertFalse(summary["full_independent_verification"])
        self.assertEqual(summary["reconstruction_replay"], "not-performed")
        self.assertEqual(summary["acquisition_verification"], "not-performed")
        self.assertIn("unmet:trusted-replay-input-provider", self.issue_codes(result))
        bad_hash = [replace(self.fixture.records[0], expected_raw_sha256="f"*64)]+self.fixture.records[1:]
        result, _, provider = self.fixture.reconcile(bad_hash)
        self.assertIn("record-content-hash-mismatch", self.issue_codes(result))
        self.assertEqual(provider.calls, [])

    def test_protected_input_absence_wrong_binding_and_wrong_truth_fail_closed(self):
        for modify in (lambda i: True,
                       lambda i: replace(i, binding_sha256="f"*64),
                       lambda i: replace(i, run_id="other-run"),
                       lambda i: replace(i, source_id="f"*64),
                       lambda i: replace(i, enrollment=replace(self.material, population_id="other")),
                       lambda i: replace(i, enrollment=replace(self.material, credential=b"WXYZ"))):
            inputs = dict(self.fixture.inputs)
            first = self.fixture.bindings[0].identity
            inputs[first] = modify(inputs[first])
            result, _, _ = self.fixture.reconcile(inputs=inputs)
            self.assertFalse(result.verified_scope_complete)
            self.assertEqual(result.local_outcomes, ())
        verifier = recon.ReplayVerifier(IndependentFixtureInputs({}), run_id=RUN, source_id=SOURCE)
        result = recon.reconcile_ledger(self.fixture.index, self.fixture.records, verifier=verifier)
        self.assertIn("trusted-replay-inputs-unavailable", self.issue_codes(result))

    def test_handles_are_issuer_and_record_bound_and_not_serializable(self):
        verifier, _ = self.fixture.verifier()
        planned, record = self.fixture.bindings[0], self.fixture.records[0]
        handle = verifier.verify(planned, record)
        outcome = verifier.project(handle, planned, record.expected_raw_sha256)
        self.assertEqual(outcome.reconstruction.category, "C")
        other, _ = self.fixture.verifier()
        for bad in (True, object.__new__(recon.VerifiedFacts), handle):
            with self.assertRaises(recon.ReconciliationError):
                other.project(bad, planned, record.expected_raw_sha256)
        with self.assertRaises(recon.ReconciliationError):
            verifier.project(handle, planned, "f"*64)
        with self.assertRaises(recon.ReconciliationError):
            verifier.verify(planned, record)
        for value in (handle, self.material, self.fixture.inputs[planned.identity]):
            with self.assertRaises(TypeError):
                pickle.dumps(value)

    def test_downstream_stages_remain_distinct_from_reconstruction(self):
        result, _, _ = self.fixture.reconcile()
        self.assertEqual(result.local_outcomes[0].reconstruction.category, "C")
        self.assertFalse(hasattr(result.local_outcomes[0], "session_active"))
        for index in (0, 2):
            records = changed(self.fixture.records, index, lambda r: r.update(downstream=dict(
                verification="verified", admission="authorized", session_active=True, authorized_releases=1, inference_calls=0)))
            result, _, _ = self.fixture.reconcile(records)
            self.assertTrue(result.verified_scope_complete)
            # A recorded authorized release never manufactures an inference call.
            self.assertEqual(parsed(records[index])["downstream"]["inference_calls"], 0)
            self.assertFalse(result.summary()["full_independent_verification"])
        for modify in (dict(admission="authorized"), dict(session_active=True),
                       dict(authorized_releases=1), dict(inference_calls=1)):
            result, _, _ = self.fixture.reconcile(changed(self.fixture.records, 0,
                lambda r: r["downstream"].update(modify)))
            self.assertFalse(result.verified_scope_complete)

    def test_changed_or_missing_second_pass_is_detected_without_rewriting_records(self):
        originals = tuple(r.raw for r in self.fixture.records)
        first, _, _ = self.fixture.reconcile()
        second, _, _ = self.fixture.reconcile()
        self.assertTrue(recon.compare_passes(first, second)["consistent"])
        self.assertFalse(recon.compare_passes(first, second)["full_independent_verification"])
        modified = changed(self.fixture.records, 0, lambda r: r["decoder"].update(outcome="decoder_failure"))
        different, _, _ = self.fixture.reconcile(modified)
        comparison = recon.compare_passes(first, different)
        self.assertFalse(comparison["consistent"])
        self.assertEqual(comparison["changed"], [self.fixture.bindings[0].identity])
        partial, _, _ = self.fixture.reconcile(self.fixture.records[:-1])
        comparison = recon.compare_passes(first, partial)
        self.assertFalse(comparison["consistent"])
        self.assertEqual(comparison["removed"], [self.fixture.bindings[-1].identity])
        self.assertEqual(tuple(r.raw for r in self.fixture.records), originals)
        with self.assertRaises(recon.ReconciliationError):
            recon.compare_passes(first, first)

    def test_no_scientific_analysis_or_reserved_streams_and_no_final_handoff(self):
        with patch.object(analysis, "analyze_final", side_effect=AssertionError("no statistical execution")), \
             patch.object(planning, "Random", side_effect=AssertionError("no reserved RNG")), \
             patch.object(planning.noise, "Random", side_effect=AssertionError("no scientific RNG")), \
             patch.object(measurement, "acquire_measurement", side_effect=AssertionError("no measurements")):
            result, _, _ = self.fixture.reconcile()
            self.assertTrue(result.verified_scope_complete)
            with self.assertRaisesRegex(recon.ReconciliationError, "handoff-blocked"):
                result.analysis_handoff()
        summary = result.summary()
        self.assertFalse(summary["inference_eligible"])
        self.assertFalse(result.final_plan_checked)
        self.assertIn("validated-complete-final-planning-contract", result.unmet_prerequisites)
        self.assertEqual(summary["replay_work"]["new_scientific_attempts"], 0)
        self.assertIn("full-source-snapshot-and-environment-verification", result.unmet_prerequisites)
        text = json.dumps(summary)
        self.assertNotIn("ABCD", text)
        self.assertNotIn("41424344", text)
        self.assertNotIn("candidate_credential", text)
        self.assertNotIn("ABCD", repr(self.material))

    def test_invalid_json_versions_unknown_fields_and_nonbinary_data(self):
        bad = [recon.RecordedExecution(b'{"x":1,"x":2}', sha256(b'{"x":1,"x":2}').hexdigest()),
               recon.RecordedExecution(b'{"x":NaN}', sha256(b'{"x":NaN}').hexdigest()),
               recon.RecordedExecution(b'{"x":1e999}', sha256(b'{"x":1e999}').hexdigest())]
        for record in bad:
            result, _, _ = self.fixture.reconcile([record])
            self.assertIn("invalid-record-json", self.issue_codes(result))
        for mutate in (lambda r: r.update(schema_version="future"),
                       lambda r: r["readings"][0]["response"].__setitem__(0, True),
                       lambda r: r["readings"][0]["response"].__setitem__(0, None)):
            result, _, _ = self.fixture.reconcile(changed(self.fixture.records, 0, mutate))
            self.assertFalse(result.verified_scope_complete)

    def test_invalid_record_hashes_are_retained_and_decoder_types_are_strict(self):
        malformed = changed(self.fixture.records, 0, lambda r: r["decoder"].update(classification="C"))
        first, _, _ = self.fixture.reconcile(malformed)
        self.assertEqual(dict(first.record_hashes)[self.fixture.bindings[0].identity], malformed[0].expected_raw_sha256)
        altered = changed(malformed, 0, lambda r: r["decoder"].update(classification="W"))
        second, _, _ = self.fixture.reconcile(altered)
        self.assertEqual(recon.compare_passes(first, second)["changed"], [self.fixture.bindings[0].identity])
        for key, value in (("reported_correction_count", True), ("reported_correction_count", 0.0),
                           ("padding_valid", 1), ("outcome", "C"), ("decoder_status", "success")):
            result, _, provider = self.fixture.reconcile(changed(self.fixture.records, 0,
                lambda r, k=key, v=value: r["decoder"].update({k: v})))
            self.assertIn("invalid-decoder-values", self.issue_codes(result))
            self.assertEqual(provider.calls, [])

    def test_provider_and_decoder_exceptions_are_faults_with_secret_free_diagnostics(self):
        with patch.object(recon, "reconstruct", side_effect=RuntimeError("secret=ABCD")):
            result, _, _ = self.fixture.reconcile()
        self.assertIn("replay-infrastructure-fault", self.issue_codes(result))
        self.assertNotIn("ABCD", json.dumps(result.summary()))
        self.assertEqual(result.local_outcomes, ())


class PlanningBoundaryTests(unittest.TestCase):
    def test_no_generic_binding_index_can_claim_validated_final_plan(self):
        bindings, _ = metadata_schedule()
        self.assertFalse(recon.ScheduleIndex(bindings)._final_checked)
        with patch.object(planning, "validate_plan", side_effect=ValueError("invalid full plan")) as validator:
            with self.assertRaisesRegex(ValueError, "invalid full plan"):
                recon.ScheduleIndex.from_final_plan(None, {})
        validator.assert_called_once_with(None, {})

    def test_invalid_seed_alias_reading_index_and_duplicate_planned_bindings(self):
        bindings, _ = metadata_schedule()
        with self.assertRaises(recon.ReconciliationError):
            recon.ScheduleIndex(bindings+bindings[:1])
        with self.assertRaises(recon.ReconciliationError):
            recon.ScheduleIndex(bindings[:-1])
        for field, value in (("noise_shared_seed_sha256", "f"*64), ("reading_seed_sha256", ["f"*64]*3),
                             ("linked_operating_trial_id", "f"*64), ("enrollment_id", "other-enrollment")):
            revised = list(bindings)
            # Change all common-arm planned blocks, rehash attempts consistently;
            # even self-consistent IDs cannot disguise an invalid seed/alias link.
            block = deepcopy(revised[15].to_dict()["block"])
            block[field] = value
            block["trial_id"] = planning.trial_id(block)
            for i in range(15, 18):
                attempt = revised[i].to_dict()["attempt"]
                attempt["trial_id"] = block["trial_id"]
                attempt["policy_attempt_id"] = planning.attempt_id(block, attempt["policy"])
                revised[i] = recon.PlannedAttempt(CONFIG, PLAN, planning.canonical(block), planning.canonical(attempt))
            with self.subTest(field=field), self.assertRaises((recon.ReconciliationError, ValueError)):
                recon.ScheduleIndex(revised)


if __name__ == "__main__":
    unittest.main()
