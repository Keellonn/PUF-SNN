"""Isolated synthetic outcome arithmetic, never final scientific attempts/seeds."""

from collections import Counter, defaultdict
from dataclasses import replace
from math import floor
from random import Random
import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from puf_snn.experiments import shared_noise_final_analysis_v1 as analysis
from puf_snn.experiments import shared_noise_final_plan_v1 as planning

S, M, T = analysis.S, analysis.M, analysis.T
CONDITIONS = analysis.CONDITIONS


def evaluated(category, response=(0,) * 64):
    facts = {"C": ("candidate_valid_format", b"test"),
             "D": ("decoder_failure", None), "I": ("invalid_format_or_padding", None),
             "W": ("candidate_valid_format", b"nope")}
    outcome, candidate = facts[category]
    return analysis.evaluate_reconstruction(outcome=outcome, candidate_credential=candidate,
        enrollment_truth=b"test", effective_response=response)


def fixture(groups=1, devices_per_group=2, override=None):
    """Two matched trials, six conditions, three arms, nonfinal opaque IDs.

    Hand totals at rho0: S=C,D,I,W; M=D,C,W,C. Thus Delta=1/4,
    beneficial=2 and harmful=1. Device benefits are 0 and 1/2.
    """
    rows = []
    for g in range(groups):
        for d in range(devices_per_group):
            patterns = {
                CONDITIONS[0]: (("C", "D"), ("D", "C")) if d % 2 == 0 else (("I", "W"), ("W", "C")),
                CONDITIONS[1]: (("C", "D"), ("C", "C")) if d % 2 == 0 else (("D", "C"), ("C", "C")),
                CONDITIONS[2]: (("C", "D"), ("C", "I")) if d % 2 == 0 else (("C", "W"), ("C", "C")),
                CONDITIONS[3]: (("D", "D"), ("C", "C")),
                CONDITIONS[4]: (("W", "C"), ("D", "C")),
            }
            # Group sensitivity fixture: one group with no rho0 benefit.
            if g % 2:
                patterns[CONDITIONS[0]] = (("C", "D"), ("C", "C"))
            if override:
                patterns.update(override)
            patterns[CONDITIONS[5]] = patterns[CONDITIONS[0]]
            for c in CONDITIONS:
                for t, categories in enumerate(patterns[c]):
                    trial = f"fixture-g{g}-d{d}-{c}-{t}"
                    for policy, category in ((S, categories[0]), (M, categories[1]), (T, None)):
                        rows.append(analysis.AttemptOutcome(config_sha256="fixture-config",
                            plan_sha256="fixture-plan", population_id=f"fixture-g{g}",
                            device_id=f"fixture-g{g}-d{d}", enrollment_id=f"fixture-g{g}-d{d}-enrollment",
                            condition=c, attempt_index=t, trial_id=trial, policy=policy,
                            policy_attempt_id=f"{trial}:{policy}", execution_index=len(rows),
                            reconstruction=evaluated(category) if category else None,
                            retrieval_outcome=("success", "unavailable")[t] if policy == T else None))
    return rows


def tiny_plan(rows):
    """Local diagnostic shape only; never a valid final planning contract."""
    blocks = {}
    for row in rows:
        block = blocks.setdefault(row.trial_id, {k: getattr(row, k) for k in (
            "population_id", "device_id", "enrollment_id", "condition", "attempt_index", "trial_id")})
        block.setdefault("attempts", []).append({k: getattr(row, k) for k in (
            "policy_attempt_id", "policy", "execution_index")})
    return dict(blocks=list(blocks.values()), config_sha256="fixture-config", plan_sha256="fixture-plan")


def reference_estimates(rows, selected_devices):
    """Independent raw-fixture calculation, explicitly repeating sampled devices."""
    by_device = defaultdict(lambda: defaultdict(dict))
    for row in rows:
        if row.policy != T:
            by_device[row.device_id][row.condition].setdefault(row.attempt_index, {})[row.policy] = (
                row.reconstruction.category != "C")
    benefits = {}
    result = {}
    for c in CONDITIONS:
        means = []
        for d in selected_devices:
            pairs = list(by_device[d][c].values())
            means.append((sum(p[S] for p in pairs)/len(pairs), sum(p[M] for p in pairs)/len(pairs),
                          sum(int(p[S])-int(p[M]) for p in pairs)/len(pairs)))
        result[f"single_frr:{c}"] = sum(v[0] for v in means)/len(means)
        result[f"majority_frr:{c}"] = sum(v[1] for v in means)/len(means)
        if c in analysis.OPERATING:
            benefits[c] = [v[2] for v in means]
            result[f"delta:{c}"] = sum(benefits[c])/len(means)
            result[f"attenuation:{c}"] = sum(b0-b for b0, b in zip(benefits[CONDITIONS[0]], benefits[c]))/len(means)
    return result


def reference_percentile(values, p):
    ordered = sorted(values)
    position = (len(ordered)-1)*p
    left = floor(position)
    right = min(left+1, len(ordered)-1)
    return (1-(position-left))*ordered[left] + (position-left)*ordered[right]


class EvaluatorTests(unittest.TestCase):
    def test_exact_categories_and_failure_indicator(self):
        for category, failure in (("C", 0), ("D", 1), ("I", 1), ("W", 1)):
            with self.subTest(category=category):
                result = evaluated(category)
                self.assertEqual((result.category, result.failure), (category, failure))
                self.assertNotIn(b"test".hex(), result.identity_sha256)

    def test_truth_controls_correctness_not_candidate_claim(self):
        result = analysis.evaluate_reconstruction(outcome="candidate_valid_format",
            candidate_credential=b"nope", enrollment_truth=b"nope", effective_response=(0,)*64)
        self.assertEqual(result.category, "C")
        self.assertEqual(evaluated("W").category, "W")
        for category in ("C", "D", "I", "W", "X", "", None):
            with self.subTest(category=category), self.assertRaises(ValueError):
                analysis.EvaluatedReconstruction(category, "0"*64, object())

    def test_inconsistent_decoder_facts_and_untrusted_claims_rejected(self):
        base = dict(outcome="candidate_valid_format", candidate_credential=b"test",
                    enrollment_truth=b"test", effective_response=(0,)*64)
        for changes in (dict(outcome="C"), dict(outcome="decoder_failure"),
                        dict(outcome="invalid_format_or_padding"), dict(candidate_credential=None),
                        dict(candidate_credential=b"short"), dict(enrollment_truth=None),
                        dict(effective_response=(True,)*64)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                analysis.evaluate_reconstruction(**dict(base, **changes))
        with self.assertRaises(ValueError):
            replace(fixture()[0], reconstruction="C")

    def test_stored_inapplicable_and_source_record_required(self):
        stored = next(r for r in fixture() if r.policy == T)
        with self.assertRaises(ValueError):
            replace(stored, reconstruction=evaluated("C"))
        with self.assertRaises(ValueError):
            replace(stored, retrieval_outcome=None)
        with self.assertRaises(ValueError):
            replace(stored, retrieval_outcome="correct-credential")
        with self.assertRaises(ValueError):
            replace(fixture()[0], retrieval_outcome="success")


class MathematicalTests(unittest.TestCase):
    def setUp(self):
        self.rows = fixture()
        self.records = analysis.paired_records(self.rows)
        self.result = analysis.summarize(self.records)

    def test_exact_counts_frr_discordances_and_denominators(self):
        condition = self.result["conditions"][CONDITIONS[0]]
        self.assertEqual(condition["arms"][S]["counts"], dict(C=1, D=1, I=1, W=1))
        self.assertEqual(condition["arms"][M]["counts"], dict(C=2, D=1, I=0, W=1))
        self.assertEqual(condition["arms"][S]["reconstruction_frr"], .75)
        self.assertEqual(condition["arms"][M]["reconstruction_frr"], .5)
        self.assertEqual((condition["beneficial"], condition["harmful"], condition["matched_denominator"]), (2, 1, 4))
        self.assertEqual(condition["discordance_net_proportion"], .25)
        self.assertTrue(condition["discordance_identity_verified"])
        self.assertEqual(condition["arms"][S]["denominator"], 4)

    def test_positive_negative_zero_delta_and_principal_attenuation(self):
        point = self.result["estimands"]
        self.assertEqual([point[f"delta:{c}"] for c in analysis.OPERATING], [.25, 0, -.75, 0])
        self.assertEqual([point[f"attenuation:{c}"] for c in analysis.OPERATING], [0, .25, 1, .25])
        self.assertEqual(self.result["principal_contrast"], "attenuation:op_rho090")

    def test_negative_and_zero_attenuation(self):
        rows = fixture(override={CONDITIONS[1]: (("D", "C"), ("I", "C"))})
        point = analysis.estimands(analysis.paired_records(rows))
        self.assertEqual(point[f"attenuation:{CONDITIONS[1]}"], -.75)
        rows = [replace(r, reconstruction=evaluated("C")) if r.policy != T else r for r in self.rows]
        self.assertTrue(all(v == 0 for v in analysis.estimands(analysis.paired_records(rows)).values()))

    def test_fresh_operating_rho0_not_nominal_or_calibration(self):
        point = self.result["estimands"]
        self.assertEqual(point["attenuation:op_rho090"], 1)
        # Nominal benefit is 1, which would give the incorrect answer 1.75.
        self.assertNotEqual(point["attenuation:op_rho090"], 1.75)
        self.assertFalse(any("nominal" in k or "common" in k for k in point if k.startswith(("delta:", "attenuation:"))))
        with self.assertRaises(ValueError):
            analysis.paired_records([r for r in self.rows if r.condition != CONDITIONS[0]])

    def test_rho1_nonzero_absolute_frr_and_exact_zero_delta(self):
        point = self.result["estimands"]
        self.assertEqual(point["single_frr:op_rho100"], .5)
        self.assertEqual(point["majority_frr:op_rho100"], .5)
        self.assertEqual(point["delta:op_rho100"], 0)

    def test_device_level_pairs_and_independent_raw_reference(self):
        self.assertEqual([r.cells[0].benefit for r in self.records], [0, .5])
        self.assertEqual(self.records[0].cells[0].paired_failures, ((0, 0, 1), (1, 1, 0)))
        self.assertEqual(self.records[1].cells[0].paired_failures, ((0, 1, 1), (1, 1, 0)))
        self.assertEqual(self.result["paired_failure_indicators"][self.records[0].device_id][CONDITIONS[0]],
                         ((0, 0, 1), (1, 1, 0)))
        self.assertEqual(analysis.estimands(self.records), reference_estimates(self.rows, [r.device_id for r in self.records]))
        weights = {self.records[0].device_id: 3, self.records[1].device_id: 1}
        self.assertEqual(analysis.estimands(self.records, weights)["delta:op_rho000"], .125)
        self.assertEqual(analysis.estimands(self.records, weights), reference_estimates(self.rows,
            [self.records[0].device_id]*3 + [self.records[1].device_id]))

    def test_t_null_semantics_and_separate_retrieval_denominator(self):
        for c in CONDITIONS:
            stored = self.result["conditions"][c]["arms"][T]
            self.assertEqual(stored["status"], "inapplicable")
            for key in ("counts", "denominator", "reconstruction_frr", "ber", "decoder_outcomes"):
                self.assertIsNone(stored[key])
            self.assertEqual(stored["source_denominator"], 4)
            self.assertEqual(stored["retrieval_counts"], dict(success=2, unavailable=2, malformed=0))

    def test_group_and_leave_out_estimates_preserve_membership(self):
        rows = fixture(groups=2, devices_per_group=6)
        records = analysis.paired_records(rows)
        result = analysis.summarize(records)
        for group, estimates in result["group_estimates"].items():
            devices = [r.device_id for r in records if r.population_id == group]
            self.assertEqual(estimates, reference_estimates(rows, devices))
            remaining = [r.device_id for r in records if r.population_id != group]
            self.assertEqual(result["leave_one_group_out"][group], reference_estimates(rows, remaining))
        first = records[0].device_id
        self.assertEqual(result["leave_one_device_out"][first], reference_estimates(rows,
            [r.device_id for r in records if r.device_id != first]))

    def test_proportions_and_percentage_points_remain_distinct(self):
        self.assertEqual(self.result["units"], "proportion")
        self.assertEqual(self.result["estimands"]["delta:op_rho000"], .25)
        self.assertEqual(self.result["percentage_points_multiplier"]*.25, 25)

    def test_zero_events_and_undefined_denominators(self):
        records = analysis.paired_records(fixture(override={c: (("C", "C"), ("C", "C")) for c in CONDITIONS}))
        result = analysis.bootstrap(records, seed=2718, resamples=9)
        interval = result["intervals"]["single_frr:op_rho000"]
        self.assertEqual((interval["lower"], interval["upper"]), (0, 0))
        self.assertTrue(interval["degenerate"] and interval["unseen_events_limitation"])
        self.assertFalse(result["intervals"]["delta:op_rho000"]["unseen_events_limitation"])
        empty = analysis.summarize(analysis.paired_records([]))
        self.assertTrue(all(v is None for v in empty["estimands"].values()))
        self.assertEqual(empty["conditions"][CONDITIONS[0]]["arms"][S]["status"], "undefined-zero-denominator")
        self.assertIsNone(empty["conditions"][CONDITIONS[0]]["discordance_net_proportion"])
        self.assertTrue(all(v is None for v in analysis.estimands(records, {}).values()))


class PairingValidationTests(unittest.TestCase):
    def setUp(self):
        self.rows = fixture()

    def test_duplicates_missing_and_unknown_identities_rejected(self):
        for rows in (self.rows + self.rows[:1], self.rows[1:],
                     [r for r in self.rows if r.attempt_index == 0 and r.condition == CONDITIONS[0]],
                     [replace(self.rows[0], execution_index=self.rows[1].execution_index)] + self.rows[1:],
                     [replace(self.rows[0], trial_id="unknown")] + self.rows[1:]):
            with self.subTest(size=len(rows)), self.assertRaises(ValueError):
                analysis.paired_records(rows)
        with self.assertRaises(ValueError):
            replace(self.rows[0], policy="unknown")
        with self.assertRaises(ValueError):
            replace(self.rows[0], condition="week9-calibration")

    def test_inconsistent_group_enrollment_contract_and_status(self):
        for changes in (dict(population_id="wrong-group"), dict(enrollment_id="wrong-enrollment"),
                        dict(config_sha256="wrong-config"), dict(plan_sha256="wrong-plan"),
                        dict(execution_status="pending"), dict(fault_code="infrastructure-fault")):
            rows = [replace(self.rows[0], **changes)] + self.rows[1:]
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                analysis.paired_records(rows)
        for changes in (dict(experiment_id="calibration"), dict(schema_version="future"),
                        dict(attempt_index=True), dict(execution_index=1.0)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.rows[0], **changes)

    def test_cross_condition_trial_sets_must_match(self):
        rows = [replace(r, attempt_index=2) if r.condition == CONDITIONS[1] and r.attempt_index == 0 else r
                for r in self.rows]
        with self.assertRaises(ValueError):
            analysis.paired_records(rows)

    def test_rho1_and_common_identity_violations_rejected_even_equal_failure_rates(self):
        for c, policy, reconstruction in ((CONDITIONS[3], S, evaluated("I")),
                (CONDITIONS[3], S, evaluated("D", (1,)*64)),
                (CONDITIONS[5], M, evaluated("I"))):
            rows = [replace(r, reconstruction=reconstruction) if r.condition == c and r.policy == policy
                    and r.attempt_index == 0 and r.device_id.endswith("d0") else r for r in self.rows]
            with self.subTest(condition=c), self.assertRaises(ValueError):
                analysis.paired_records(rows)

    def test_diagnostics_retain_missing_unknown_duplicate_misplaced_and_pending(self):
        plan = tiny_plan(self.rows)
        rows = self.rows[1:] + [self.rows[1], replace(self.rows[0], policy_attempt_id="unknown")]
        rows[0] = replace(rows[0], enrollment_id="misplaced", execution_status="pending")
        report = analysis.coverage_diagnostics(plan, rows)
        self.assertEqual(report["missing"], [self.rows[0].policy_attempt_id])
        self.assertEqual(report["duplicate"], [self.rows[1].policy_attempt_id])
        self.assertEqual(report["unknown"], ["unknown"])
        self.assertEqual(report["mismatched"], [self.rows[1].policy_attempt_id])
        self.assertEqual(report["incomplete"], [self.rows[1].policy_attempt_id])
        self.assertFalse(report["inference_eligible"])

    def test_all_planned_binding_fields_are_checked(self):
        plan = tiny_plan(self.rows)
        for field, value in (("device_id", "other"), ("population_id", "other"),
                ("enrollment_id", "other"), ("condition", CONDITIONS[1]), ("attempt_index", 3),
                ("trial_id", "other"), ("policy", M), ("execution_index", 999),
                ("config_sha256", "other"), ("plan_sha256", "other")):
            with self.subTest(field=field):
                rows = [replace(self.rows[0], **{field: value})] + self.rows[1:]
                self.assertEqual(analysis.coverage_diagnostics(plan, rows)["mismatched"],
                                 [self.rows[0].policy_attempt_id])

    def test_small_fixture_cannot_be_certified_even_with_mocked_plan_validation(self):
        with patch.object(planning, "validate_plan"), self.assertRaisesRegex(ValueError, "120 devices"):
            analysis.validate_complete(None, tiny_plan(self.rows), self.rows)

    def test_reconciliation_faults_refuse_inference_and_retain_diagnostics(self):
        plan = tiny_plan(self.rows)
        variants = [self.rows[1:], self.rows + self.rows[:1],
            [replace(self.rows[0], policy_attempt_id="unknown")] + self.rows[1:],
            [replace(self.rows[0], enrollment_id="wrong")] + self.rows[1:],
            [replace(self.rows[0], execution_status="pending")] + self.rows[1:]]
        for rows in variants:
            with patch.object(planning, "validate_plan"), self.assertRaises(analysis.IncompleteStudyError) as caught:
                analysis.validate_complete(None, plan, rows)
            self.assertFalse(caught.exception.diagnostics["inference_eligible"])

    def test_aggregate_count_and_pairing_consistency(self):
        records = analysis.paired_records(self.rows)
        cell = records[0].cells[0]
        for changes in (dict(single_counts=(0, 0, 0, 0)), dict(retrieval_counts=(0, 0, 0)),
                        dict(beneficial=99), dict(harmful=0), dict(n=0),
                        dict(paired_failures=((0, 1, 1), (1, 0, 0))),
                        dict(paired_failures=((0, 0, 1), (0, 1, 0)))):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(cell, **changes)
        with self.assertRaises(ValueError):
            replace(records[0], cells=records[0].cells[:-1])


class BootstrapTests(unittest.TestCase):
    def check_reference(self, rows, unit, seed, resamples):
        records = analysis.paired_records(rows)
        result = analysis.bootstrap(records, seed=seed, unit=unit, resamples=resamples)
        rng = Random(seed)
        ids = sorted({r.device_id if unit == "device" else r.population_id for r in rows})
        members = {g: sorted({r.device_id for r in rows if r.population_id == g}) for g in ids} if unit == "group" else None
        draws = []
        for _ in range(resamples):
            selected = [ids[rng.randrange(len(ids))] for _ in ids]
            devices = selected if unit == "device" else [d for g in selected for d in members[g]]
            draws.append(reference_estimates(rows, devices))
        for key, interval in result["intervals"].items():
            values = [draw[key] for draw in draws]
            self.assertAlmostEqual(interval["lower"], reference_percentile(values, .025), places=15, msg=key)
            self.assertAlmostEqual(interval["upper"], reference_percentile(values, .975), places=15, msg=key)
            self.assertEqual(interval["defined_resamples"], resamples)
            self.assertEqual(interval["undefined_resamples"], 0)
        return result

    def test_device_bootstrap_matches_independent_raw_reference_all_metrics(self):
        result = self.check_reference(fixture(), "device", seed=73, resamples=19)
        self.assertEqual(result["role"], "primary")
        self.assertEqual(result["sampling_units"], 2)
        self.assertEqual(result["seed"], 73)

    def test_group_bootstrap_matches_independent_reference_all_six_devices(self):
        result = self.check_reference(fixture(groups=2, devices_per_group=6), "group", seed=37, resamples=13)
        self.assertEqual(result["role"], "group-level-sensitivity")
        self.assertEqual(result["sampling_units"], 2)

    def test_device_and_group_multiplicities_and_rng_call_sequence(self):
        records = analysis.paired_records(fixture(groups=2, devices_per_group=6))
        for unit in ("device", "group"):
            seen = []
            original = analysis.estimands
            def capture(records, weights=None):
                if weights is not None:
                    seen.append(dict(weights))
                return original(records, weights)
            with patch.object(analysis, "estimands", side_effect=capture):
                analysis.bootstrap(records, seed=2, unit=unit, resamples=3)
            ids = sorted(r.device_id for r in records) if unit == "device" else ["fixture-g0", "fixture-g1"]
            rng = Random(2)
            for weights in seen:
                expected = Counter(ids[rng.randrange(len(ids))] for _ in ids)
                if unit == "group":
                    expected = {r.device_id: expected[r.population_id] for r in records if expected[r.population_id]}
                    self.assertEqual(sum(weights.values()), 12)
                    for g in ("fixture-g0", "fixture-g1"):
                        self.assertEqual(len({weights.get(r.device_id, 0) for r in records if r.population_id == g}), 1)
                self.assertEqual(weights, expected)
            self.assertEqual(len(seen), 3)
            if unit == "group":
                self.assertEqual(set(seen[0].values()), {2})  # First draw retains six devices twice.

    def test_determinism_sorting_and_separate_streams(self):
        records = analysis.paired_records(fixture(groups=2, devices_per_group=6))
        for unit in ("device", "group"):
            a = analysis.bootstrap(records, seed=919, unit=unit, resamples=11)
            b = analysis.bootstrap(tuple(reversed(records)), seed=919, unit=unit, resamples=11)
            self.assertEqual(a, b)
            self.assertEqual(a["method"], "percentile-linear-(B-1)*p")
            self.assertEqual(a["resamples"], a["performed_resamples"])
            self.assertEqual(a["interval_scope"], "two-sided-pointwise-estimation-only")

    def test_exact_interpolation_with_hand_calculated_expected_values(self):
        self.assertAlmostEqual(analysis.percentile([20, 0, 30, 10], .025), .75, places=14)
        self.assertAlmostEqual(analysis.percentile([20, 0, 30, 10], .975), 29.25, places=14)
        self.assertEqual(analysis.percentile([7], .025), 7)
        self.assertIsNone(analysis.percentile([], .975))

    def test_insufficient_units_and_invalid_bootstrap_inputs(self):
        records = analysis.paired_records(fixture(devices_per_group=1))
        for selected, unit in ((records, "device"), (records, "group"), ((), "device")):
            with patch.object(analysis, "Random", side_effect=AssertionError("must not draw")):
                result = analysis.bootstrap(selected, seed=41, unit=unit, resamples=3)
            self.assertEqual(result["performed_resamples"], 0)
            self.assertEqual(result["interval_status"], "suppressed-insufficient-sampling-units")
            self.assertTrue(all(i["lower"] is None and i["upper"] is None for i in result["intervals"].values()))
        for changes in (dict(seed=-1), dict(seed=True), dict(resamples=0), dict(resamples=True), dict(unit="trial")):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                analysis.bootstrap(records, **dict(dict(seed=1), **changes))
        for weights in ({"unknown": 1}, {records[0].device_id: -1}, {records[0].device_id: True}):
            with self.assertRaises(ValueError):
                analysis.estimands(records, weights)

    def test_production_default_is_fixed_and_no_override_on_final_api(self):
        self.assertEqual(inspect.signature(analysis.bootstrap).parameters["resamples"].default, 10000)
        self.assertEqual(list(inspect.signature(analysis.analyze_final).parameters), ["config", "plan", "rows"])


class FinalBoundaryTests(unittest.TestCase):
    def test_final_wiring_uses_separate_derived_domains_and_fixed_counts_without_drawing(self):
        # Wiring-only mock: no incomplete fixture is actually certified and the
        # real bootstrap is replaced, so no reserved stream can be consumed.
        records = analysis.paired_records(fixture())
        boundary = SimpleNamespace(records=records, config_sha256="fixture-config", plan_sha256="fixture-plan")
        with patch.object(analysis, "validate_complete", return_value=boundary), \
             patch.object(planning, "study_seed", side_effect=[1001, 1002]) as seeds, \
             patch.object(analysis, "bootstrap", side_effect=[{}, {}]) as bootstrap:
            result = analysis.analyze_final(None, {}, [])
        self.assertEqual([call.args[1] for call in seeds.call_args_list],
                         ["device-bootstrap", "group-bootstrap-sensitivity"])
        self.assertEqual(bootstrap.call_args_list[0].kwargs, dict(seed=1001, resamples=10000))
        self.assertEqual(bootstrap.call_args_list[1].kwargs, dict(seed=1002, unit="group", resamples=10000))
        self.assertEqual(result["primary"]["seed_domain"], "device-bootstrap")
        self.assertEqual(result["group_sensitivity"]["seed_domain"], "group-bootstrap-sensitivity")

    def test_real_plan_validator_refuses_fixture_contract_without_any_reserved_rng(self):
        # Exercise the real contract validator's refusal without regenerating
        # even a reserved schedule or offset-sign stream. All fixture IDs are
        # isolated; the actual final allocation is never manufactured for tests.
        config = planning.StudyConfig.load()
        with patch.object(analysis, "Random", side_effect=AssertionError("reserved stream forbidden")), \
             patch.object(planning, "Random", side_effect=AssertionError("schedule/offset stream forbidden")), \
             patch.object(planning, "study_seed", side_effect=AssertionError("reserved seed forbidden")):
            with self.assertRaisesRegex(ValueError, "unsupported final plan version"):
                analysis.analyze_final(config, tiny_plan(fixture()), [])

    def test_invalid_plan_cannot_reach_statistical_validation(self):
        with patch.object(planning, "validate_plan", side_effect=ValueError("invalid contract")), \
             patch.object(analysis, "coverage_diagnostics", side_effect=AssertionError("must not analyze")):
            with self.assertRaisesRegex(ValueError, "invalid contract"):
                analysis.analyze_final(None, {}, fixture())


if __name__ == "__main__":
    unittest.main()
