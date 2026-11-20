"""Metadata-only final planning tests. No reserved measurement streams are drawn."""

from collections import Counter, defaultdict
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import builtins
import io
import json
import os
from pathlib import Path
from random import Random
import socket
import unittest
from unittest.mock import patch

from puf_snn.experiments import shared_noise_final_plan_v1 as study
from puf_snn.experiments import correlated_noise_v1 as noise
from puf_snn.puf import device, ro_puf
from puf_snn import reconstruction


def independent_digest(obj):
    return sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("utf-8")).hexdigest()


def independent_seed_digest(identity, domain, reading=None):
    obj = dict(identity, domain=domain)
    if reading is not None:
        obj["reading_index"] = reading
    return independent_digest(obj)


class ConfigTests(unittest.TestCase):
    def test_exact_conditions_profiles_roots_and_fail_closed_state(self):
        cfg = study.StudyConfig.load()
        obj = cfg.to_dict()
        self.assertEqual([(c["name"], c["sigma"], c["rho"]) for c in obj["conditions"]], [
            ("op_rho000", .15, 0), ("op_rho050", .15, .5), ("op_rho090", .15, .9),
            ("op_rho100", .15, 1), ("nominal_s010", .1, 0), ("common_mode_op_rho000", .15, 0)])
        self.assertEqual(obj["policies"], ["single-read-v1", "majority-3-v1", "stored-provisioned-v1"])
        self.assertEqual([obj[f] for f in ("master_seed", "schedule_seed", "bootstrap_seed", "group_sensitivity_seed")],
                         [2026102811, 2026102812, 2026102813, 2026102814])
        self.assertEqual((obj["oscillator_count"],obj["response_bits"],obj["pairing"]), (128,64,"adjacent"))
        r = obj["reconstruction"]
        self.assertEqual((r["n"],r["k"],r["t"],r["credential_bits"],r["padding_bits"]), (63,36,5,32,[0]*4))
        self.assertFalse(obj["scientific_execution_authorized"] or obj["final_execution_enabled"])
        self.assertEqual(obj["mode"], "planning-only")
        # Read-only compatibility check; do not import or run historical runners.
        legacy = json.loads((study.ROOT / "configs/three_arm_auth_v1.json").read_text())
        self.assertEqual(obj["authentication"], legacy["authentication"])

    def test_reject_versions_phase_modes_roots_allocations_and_unknown_fields(self):
        original = study.StudyConfig.load().to_dict()
        mutations = [
            ("schema_version", "week9-shared-noise-final-v2:config"),
            ("contract_version", "future-v2"), ("contract_status", "frozen"),
            ("experiment_id", "week9-shared-noise-calibration-v1"),
            ("model_version", "unknown-v2"), ("mode", "unit-test"),
            ("mode", "run-final"), ("final_execution_enabled", True),
            ("scientific_execution_authorized", True), ("master_seed", 2026102801),
            ("schedule_seed", 1), ("bootstrap_seed", 1), ("group_sensitivity_seed", 1),
            ("retries", 1), ("manufacturing_std", 2), ("extra", "unknown"),
            ("config_sha256", "0"*64), ("policies", list(reversed(study.POLICIES)))]
        for key, value in mutations:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                study.StudyConfig.from_dict(dict(original, **{key:value}))
        for key in original["allocation"]:
            for value in (1, True, float(original["allocation"][key])):
                obj = deepcopy(original)
                obj["allocation"][key] = value
                with self.subTest(allocation=key, value=value), self.assertRaises(ValueError):
                    study.StudyConfig.from_dict(obj)

    def test_reject_condition_changes_duplicates_and_wrong_alias(self):
        for mutate in (
            lambda cs: cs.reverse(), lambda cs: cs.append(cs[0]),
            lambda cs: cs.__setitem__(1, deepcopy(cs[0])),
            lambda cs: cs[0].__setitem__("sigma", .1),
            lambda cs: cs[3].__setitem__("rho", .99),
            lambda cs: cs[5].__setitem__("noise_alias_of", "nominal_s010"),
            lambda cs: cs[5].__setitem__("noise_domain", "common:fresh"),
            lambda cs: cs[5].__setitem__("common_offsets", [1])):
            obj = study.StudyConfig.load().to_dict()
            mutate(obj["conditions"])
            with self.assertRaises(ValueError):
                study.StudyConfig.from_dict(obj)

    def test_canonical_config_digest_numeric_normalization_and_json_rejection(self):
        cfg = study.StudyConfig.load()
        text = json.dumps(cfg.to_dict(), indent=7, sort_keys=False)
        self.assertEqual(study.StudyConfig(text).digest, independent_digest(cfg.to_dict()))
        obj = cfg.to_dict()
        obj["conditions"][0]["rho"] = 0
        obj["manufacturing_std"] = 1
        self.assertEqual(study.StudyConfig.from_dict(obj).digest, cfg.digest)
        obj["master_seed"] = float(obj["master_seed"])
        with self.assertRaises(ValueError): study.StudyConfig.from_dict(obj)
        for bad in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.assertRaises(ValueError): study.StudyConfig(bad)
        with self.assertRaises(ValueError): study.canonical(float("nan"))
        with self.assertRaises(ValueError): study.validate_schema("future", {})

    def test_existing_seed_primitive_matches_independent_isolated_identity(self):
        # Isolated metadata fixture, never a reserved enrollment/noise realization.
        identity = noise.AttemptIdentity(902, "unit-final-plan-p", "unit-final-plan-d", "unit-final-plan:noise", 7)
        for domain in noise.RNG_DOMAINS:
            indices = range(3) if domain == noise.READING else (None,)
            for index in indices:
                expected = independent_seed_digest(asdict(identity), domain, index)
                self.assertEqual(study.seed_digest(identity, domain, index), expected)
                self.assertEqual(noise.derive_seed(identity, domain, index), int(expected, 16))


class PlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = study.StudyConfig.load()
        fail = AssertionError("planning attempted scientific generation, traffic or output")
        builtin_open, io_open, os_open = builtins.open, io.open, os.open
        getrandbits = Random.getrandbits
        def guard_open(original):
            def guarded(file, mode="r", *args, **kwargs):
                if any(c in mode for c in "wax+"):
                    raise fail
                return original(file, mode, *args, **kwargs)
            return guarded
        def guard_os_open(path, flags, *args, **kwargs):
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
                raise fail
            return os_open(path, flags, *args, **kwargs)
        def guard_bits(rng, count):
            if count > 16:  # shuffle <=36,000 needs <=16 bits; a credential needs 32
                raise fail
            return getrandbits(rng, count)
        with ExitStack() as guards:
            for target, attr in ((noise,"measure_indexed"),(noise,"generate_shared_disturbance"),
                (noise,"CorrelatedResponseReader"),(device,"create_device"),(ro_puf,"generate_response"),
                (ro_puf,"calculate_frequencies"),(reconstruction,"enroll"),(reconstruction,"reconstruct"),
                (reconstruction.BCHCodec,"encode"),(reconstruction.BCHCodec,"decode"),
                (Random,"gauss"),(Random,"normalvariate"),(Random,"randbytes"),
                (socket,"socket"),(os,"mkdir"),(os,"makedirs")):
                guards.enter_context(patch.object(target,attr,side_effect=fail))
            guards.enter_context(patch.object(builtins,"open",side_effect=guard_open(builtin_open)))
            guards.enter_context(patch.object(io,"open",side_effect=guard_open(io_open)))
            guards.enter_context(patch.object(os,"open",side_effect=guard_os_open))
            guards.enter_context(patch.object(Random,"getrandbits",new=guard_bits))
            cls.plan = study.compile_plan(cls.cfg)
        cls.by_key = {(b["device_id"],b["condition"],b["attempt_index"]):b for b in cls.plan["blocks"]}

    def test_complete_plan_repeatability_and_strict_schema_validation(self):
        self.assertEqual(self.plan, study.compile_plan(self.cfg))
        study.validate_plan(self.cfg, self.plan)
        self.assertFalse(self.plan["scientific_execution_authorized"])
        for forbidden in ("execute_attempt", "run", "prepare_population", "enrollment_material", "main"):
            self.assertFalse(hasattr(study, forbidden))

    def test_exact_counts_unique_ids_and_group_enrollment_relationships(self):
        blocks = self.plan["blocks"]
        self.assertEqual(len(blocks),36000)
        self.assertEqual(len(self.by_key),36000)
        self.assertEqual(len({b["trial_id"] for b in blocks}),36000)
        self.assertEqual(Counter(b["condition"] for b in blocks),dict.fromkeys([c[0] for c in study.CONDITIONS],6000))
        enrollments = self.plan["enrollments"]
        self.assertEqual(len(enrollments),120)
        self.assertEqual(len({e["enrollment_id"] for e in enrollments}),120)
        self.assertEqual(Counter(e["population_id"] for e in enrollments), {f"w9f-p{p:03d}":6 for p in range(20)})
        self.assertEqual({e["device_id"] for e in enrollments}, {f"w9f-p{p:03d}-d{d:02d}" for p in range(20) for d in range(6)})
        attempts = [a for b in blocks for a in b["attempts"]]
        self.assertEqual(len(attempts),108000)
        self.assertEqual(len({a["policy_attempt_id"] for a in attempts}),108000)
        self.assertEqual(Counter(a["policy"] for a in attempts),dict.fromkeys(study.POLICIES,36000))
        self.assertEqual(Counter(a["condition"] for a in attempts),dict.fromkeys([c[0] for c in study.CONDITIONS],18000))
        catalog = {e["device_id"]:e for e in enrollments}
        for block in blocks:
            self.assertEqual(block["enrollment_id"],catalog[block["device_id"]]["enrollment_id"])
            self.assertEqual(block["population_id"],catalog[block["device_id"]]["population_id"])
        for e in enrollments:
            identity = e["noise_identity"]
            self.assertEqual(identity["noise_domain_id"],study.VERSION+":enrollment-v1")
            self.assertEqual(identity["attempt_id"],0)
            for field, domain in (("manufacturing_seed_sha256",noise.MANUFACTURING),
                ("reference_seed_sha256",noise.ENROLLMENT),("credential_seed_sha256",noise.CREDENTIAL)):
                self.assertEqual(e[field],independent_seed_digest(identity,domain))

    def test_cross_condition_matching_noise_separation_and_complete_common_alias(self):
        for e in self.plan["enrollments"]:
            for t in range(50):
                cells = [self.by_key[e["device_id"],c[0],t] for c in study.CONDITIONS]
                op, *_, common = cells
                self.assertEqual(len({b["trial_id"] for b in cells}),6)
                self.assertEqual(len({b["noise_shared_seed_sha256"] for b in cells[:5]}),5)
                self.assertEqual(len({tuple(b["reading_seed_sha256"]) for b in cells[:5]}),5)
                self.assertEqual(len({b["enrollment_id"] for b in cells}),1)
                for field in ("noise_identity","noise_shared_seed_sha256","reading_seed_sha256"):
                    self.assertEqual(common[field],op[field])
                self.assertEqual(common["linked_operating_trial_id"],op["trial_id"])
                self.assertTrue(all(b["linked_operating_trial_id"] is None for b in cells[:5]))
                op_attempts = {a["policy"]:a for a in op["attempts"]}
                for a in common["attempts"]:
                    self.assertNotEqual(a["policy_attempt_id"],op_attempts[a["policy"]]["policy_attempt_id"])
        # Distinct trial-index streams, not only distinct condition domains.
        self.assertEqual(len({b["noise_shared_seed_sha256"] for b in self.plan["blocks"]}),30000)
        self.assertEqual(len({s for b in self.plan["blocks"] for s in b["reading_seed_sha256"]}),90000)

    def test_s_m_reading_zero_identity_and_stored_null_semantics(self):
        for b in self.plan["blocks"]:
            arms = {a["policy"]:a for a in b["attempts"]}
            s,m,t = [arms[p] for p in study.POLICIES]
            self.assertEqual(s["reading_indices"],[0])
            self.assertEqual(m["reading_indices"],[0,1,2])
            self.assertEqual(s["reading_seed_sha256"],[m["reading_seed_sha256"][0]])
            self.assertEqual(s["noise_shared_seed_sha256"],m["noise_shared_seed_sha256"])
            self.assertEqual(m["reading_seed_sha256"],b["reading_seed_sha256"])
            self.assertEqual(t["reading_indices"],[])
            self.assertEqual(t["reading_seed_sha256"],[])
            self.assertIsNone(t["noise_shared_seed_sha256"])

    def test_seeded_offset_and_exact_noise_seed_identity_inputs(self):
        signs = Counter()
        for b in self.plan["blocks"]:
            identity = b["noise_identity"]
            self.assertEqual(identity["master_seed"],2026102811)
            self.assertEqual(identity["attempt_id"],b["attempt_index"])
            if b["condition"] == "common_mode_op_rho000":
                digest = independent_seed_digest(identity,"common-mode-offset")
                expected = (-1,1)[Random(int(digest,16)).randrange(2)]
                self.assertEqual((b["common_offset_seed_sha256"],b["common_offset"]),(digest,expected))
                signs[expected] += 1
            else:
                self.assertEqual(b["common_offset"],0)
                self.assertIsNone(b["common_offset_seed_sha256"])
        self.assertEqual(set(signs),{-1,1})
        self.assertEqual(sum(signs.values()),6000)
        # Independently check indexed domains/digests on each condition.
        for condition,_,_,domain in study.CONDITIONS:
            b = self.by_key["w9f-p003-d02",condition,19]
            identity = dict(master_seed=2026102811,population_id="w9f-p003",device_id="w9f-p003-d02",
                noise_domain_id=study.VERSION+":"+domain,attempt_id=19,model_version="puf-snn-correlated-noise-v1")
            self.assertEqual(b["noise_identity"],identity)
            self.assertEqual(b["noise_shared_seed_sha256"],independent_seed_digest(identity,noise.SESSION))
            self.assertEqual(b["reading_seed_sha256"],[independent_seed_digest(identity,noise.READING,r) for r in range(3)])

    def test_exact_policy_permutations_selection_shuffle_and_contiguous_indices(self):
        S,M,T = study.POLICIES
        orders = [(S,M,T),(S,T,M),(M,S,T),(M,T,S),(T,S,M),(T,M,S)]
        self.assertEqual(study.POLICY_ORDERS,tuple(orders))
        enumerated, order_counts = [], defaultdict(Counter)
        for p in range(20):
            for d in range(6):
                for c,(condition,*_) in enumerate(study.CONDITIONS):
                    for t in range(50):
                        b = self.by_key[f"w9f-p{p:03d}-d{d:02d}",condition,t]
                        self.assertEqual(tuple(b["policy_order"]),orders[(t+c+d+p)%6])
                        order_counts[b["device_id"],condition][tuple(b["policy_order"])] += 1
                        enumerated.append(b["trial_id"])
        self.assertTrue(all(sorted(cs.values())==[8,8,8,8,9,9] for cs in order_counts.values()))
        seed_obj = dict(experiment_id=study.VERSION,domain="schedule",seed=2026102812,config_sha256=self.cfg.digest)
        Random(int(independent_digest(seed_obj),16)).shuffle(enumerated)
        self.assertEqual(enumerated,[b["trial_id"] for b in self.plan["blocks"]])
        self.assertEqual([i for _,_,i in study.scheduled_attempts(self.plan)],list(range(108000)))
        for i,b in enumerate(self.plan["blocks"]):
            self.assertEqual(b["block_index"],i)
            self.assertEqual([a["execution_index"] for a in b["attempts"]],[3*i,3*i+1,3*i+2])
            self.assertEqual([a["policy"] for a in b["attempts"]],b["policy_order"])
        seeds = [study.study_seed(self.cfg,domain) for domain in ("schedule","device-bootstrap","group-bootstrap-sensitivity")]
        self.assertEqual(len(set(seeds)),3)
        for domain,root in (("device-bootstrap",2026102813),("group-bootstrap-sensitivity",2026102814)):
            self.assertEqual(study.study_seed(self.cfg,domain),int(independent_digest(dict(
                experiment_id=study.VERSION,domain=domain,seed=root,config_sha256=self.cfg.digest)),16))
        with self.assertRaises(ValueError): study.study_seed(self.cfg,"bootstrap")

    def test_trial_attempt_and_plan_hash_contract(self):
        for condition,*_ in study.CONDITIONS:
            b = self.by_key["w9f-p000-d00",condition,0]
            scientific = {k:v for k,v in b.items() if k not in {"trial_id","policy_order","block_index","attempts"}}
            self.assertEqual(b["trial_id"],independent_digest(scientific))
            for a in b["attempts"]:
                study.validate_schema("attempt",a)
                self.assertEqual(a["policy_attempt_id"],independent_digest(dict(trial_id=b["trial_id"],policy=a["policy"])))
            changed = dict(b,block_index=999,policy_order=list(reversed(b["policy_order"])),attempts=[])
            self.assertEqual(study.trial_id(changed),b["trial_id"])
            for key,value in (("common_offset",2),("condition","wrong"),("linked_operating_trial_id","f"*64)):
                self.assertNotEqual(study.trial_id(dict(b,**{key:value})),b["trial_id"])
        self.assertEqual(self.plan["plan_sha256"],independent_digest({k:v for k,v in self.plan.items() if k!="plan_sha256"}))
        with self.assertRaises(ValueError): study.attempt_id(b,"unknown")

    def test_reject_corrupted_schedule_duplicate_ids_and_alias_links(self):
        # Copy only modified records: preserve the canonical plan fixture and
        # avoid retaining multiple full metadata graphs.
        common_index = next(i for i,b in enumerate(self.plan["blocks"]) if b["condition"]=="common_mode_op_rho000")
        for mutation in (
            lambda b: b.__setitem__("linked_operating_trial_id","0"*64),
            lambda b: b["reading_seed_sha256"].__setitem__(1,"0"*64),
            lambda b: b.__setitem__("enrollment_id","w9f-p000-d00-enroll-v1"),
            lambda b: b.__setitem__("schema_version","future"),
            lambda b: b.__setitem__("condition","unknown"),
            lambda b: b.__setitem__("attempt_index",float(b["attempt_index"])),
            lambda b: b["policy_order"].reverse(),
            lambda b: b["attempts"][0].__setitem__("policy_attempt_id",b["attempts"][1]["policy_attempt_id"])):
            bad = dict(self.plan,blocks=list(self.plan["blocks"]))
            changed = deepcopy(bad["blocks"][common_index])
            mutation(changed)
            bad["blocks"][common_index] = changed
            with self.assertRaises(ValueError): study.validate_plan(self.cfg,bad)
        for field in ("blocks","enrollments"):
            bad = dict(self.plan,**{field:list(self.plan[field])})
            bad[field][1] = bad[field][0]
            with self.assertRaises(ValueError): study.validate_plan(self.cfg,bad)

    def test_reject_plan_and_attempt_versions_phase_and_extra_outcomes(self):
        for field,value in (("schema_version","future"),("contract_version","future"),
            ("experiment_id","calibration"),("config_sha256","0"*64),("scientific_execution_authorized",True),
            ("unexpected","outcome"),("counts",{})):
            with self.subTest(field=field), self.assertRaises(ValueError):
                study.validate_plan(self.cfg,dict(self.plan,**{field:value}))
        attempt = self.plan["blocks"][0]["attempts"][0]
        for field,value in (("schema_version","future"),("experiment_id","calibration"),
            ("condition","unknown"),("policy","unknown"),("result","C")):
            with self.subTest(field=field), self.assertRaises(ValueError):
                study.validate_schema("attempt",dict(attempt,**{field:value}))


if __name__ == "__main__":
    unittest.main()
