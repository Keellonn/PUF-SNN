"""Actual isolated simulator/BCH execution and independently regenerated replay.

All writes use disposable fixture roots. No reserved final draws or inference.
Controlled-input tests change Gaussian inputs only, retaining the real oscillator
loop, comparisons, acquisition, vote, BCH, evidence and reconciliation machinery.
"""

from contextlib import ExitStack, contextmanager
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
import tempfile
import unittest
from unittest.mock import Mock, patch

from puf_snn.experiments import shared_noise_final_nonfinal_integration_v1 as integration
from puf_snn.experiments import shared_noise_final_analysis_v1 as analysis
from puf_snn.experiments import shared_noise_final_controller_v1 as artificial
from puf_snn.experiments import shared_noise_final_evidence_v1 as evidence
from puf_snn.experiments import shared_noise_final_plan_v1 as planning
from puf_snn.experiments import shared_noise_final_reconciliation_v1 as recon
from puf_snn.experiments import correlated_noise_v1 as noise
from puf_snn.puf import acquisition
from puf_snn.reconstruction import BCHCodec, reconstruct


@contextmanager
def controlled_inputs(custodian):
    """Retained deterministic Z/E vectors keyed ONLY by fixture seed identities.

    Frequencies are steered by input disturbances, never by replacing recorded
    responses, decoder results, the simulator, or the replay provider. Each pass
    consumes newly instantiated iterators over these independently retained inputs.
    """
    material = custodian.enrollment
    reference, helper = material.reference, material.helper
    codec = BCHCodec()
    def target(message):
        return tuple(a ^ b for a, b in zip(helper.helper_bits, codec.encode(message))) + (reference[63],)
    wrong = target(tuple((b >> s) & 1 for b in b"Wrng" for s in range(7, -1, -1)) + (0,)*4)
    invalid = target((0,)*35 + (1,))
    failure = tuple(bit ^ int(i < 6) for i, bit in enumerate(reference))
    assert reconstruct(failure, helper).outcome == "decoder_failure"
    targets = (wrong, invalid, failure, wrong, reference, wrong)
    inputs, shared_inputs = {}, {}
    for c in range(6):
        spec = integration._spec(custodian.bindings[3*c])
        # All target pairs are placed well away from comparison ties. Convert
        # desired centered offsets to standard-normal source input fixtures.
        def vector(bits, scale):
            offsets = tuple(v for bit in bits for v in ((1., -1.) if bit else (-1., 1.)))
            return tuple((v-m)/scale for v, m in zip(offsets, custodian.device.manufacturing_variation))
        shared_inputs[spec.identity] = vector(targets[c], .15) if spec.noise_config.rho == 1 else (0.,)*128
        for r in range(3):
            bits = targets[c] if r == 0 or c == 3 else reference
            scale = spec.noise_config.independent_std
            inputs[noise.derive_seed(spec.identity, noise.READING, r)] = vector(bits, scale) if scale else (0.,)*128
    base = noise._MeasurementRandom
    class ScriptedRandom(base):
        def __init__(self, seed):
            super().__init__(seed)
            self.values = iter(inputs[seed])
        def gauss(self, mu, sigma):
            value = mu + sigma * next(self.values)
            self.samples.append(value)
            return value
    def shared(identity):
        return noise.SharedDisturbance(identity, shared_inputs[identity])
    with patch.object(noise, "_MeasurementRandom", ScriptedRandom), \
         patch.object(noise, "generate_shared_disturbance", side_effect=shared):
        yield


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.stack = self.enterContext(ExitStack())
        self.controllers = []
        self.forbidden = []
        for module, name in ((planning, "compile_plan"), (planning, "study_seed"),
                (planning, "_identity"), (planning, "_enrollment"), (planning.StudyConfig, "load"),
                (analysis, "analyze_final"), (analysis, "bootstrap"), (analysis, "Random"),
                (artificial, "execute_fixture"), (evidence, "validate_checkpoint"),
                (evidence.Inspection, "local_checkpoint")):
            self.forbidden.append(self.stack.enter_context(patch.object(module, name,
                side_effect=AssertionError("forbidden-final-or-artificial-boundary"))))
        derive = noise.derive_seed
        def isolated(identity, domain, reading_index=None):
            self.assertEqual(identity.master_seed, integration.MASTER)
            self.assertTrue(identity.noise_domain_id.startswith("fixture-nonfinal-integration-v1:"))
            self.assertEqual((identity.population_id, identity.device_id), (integration.POPULATION, integration.DEVICE))
            return derive(identity, domain, reading_index)
        self.stack.enter_context(patch.object(noise, "derive_seed", side_effect=isolated))
        original_open = Path.open
        def guarded_open(path, *args, **kwargs):
            self.assertFalse(any(p in ("results", "sim_results") for p in path.parts))
            self.assertNotEqual(path, planning.CONFIG_PATH)
            return original_open(path, *args, **kwargs)
        self.stack.enter_context(patch.object(Path, "open", guarded_open))

    def tearDown(self):
        for boundary in self.forbidden:
            boundary.assert_not_called()

    def create(self):
        temporary = tempfile.TemporaryDirectory(prefix="fixture-nonfinal-integration-tests-")
        self.addCleanup(temporary.cleanup)
        controller = integration.NonfinalController(Path(temporary.name), integration.FixtureCustodian(),
            durability="fixture-process-only")
        self.addCleanup(controller.close)
        self.controllers.append(controller)
        return controller

    def complete(self, c):
        c.run()
        c.close()
        return c

    def events(self, c):
        return tuple(map(planning.read_json, evidence.inspect_journal(c.journal.root, c.journal.directory).events))

    def row(self, c, index=0):
        return planning.read_json((c.records / (c.bindings[index].identity + ".json")).read_bytes())

    def verify_changed(self, c, mutate, index=0, provider=None):
        row = self.row(c, index)
        mutate(row)
        raw = planning.canonical(row)
        verifier = recon.ReplayVerifier(provider or c.custodian.replay_provider(),
            run_id=c.context.run_id, source_id=c.context.source_id)
        return verifier.verify(c.bindings[index], recon.RecordedExecution(raw, sha256(raw).hexdigest()))

    def assert_stopped(self, c):
        with patch.object(noise, "measure_indexed") as measure, patch.object(integration, "reconstruct") as decode:
            with self.assertRaises(integration.IntegrationError):
                c.execute(c.bindings[1])
            measure.assert_not_called()
            decode.assert_not_called()
        c.close()
        with self.assertRaises(integration.IntegrationError):
            c.reconcile()

    def test_start_publication_returns_before_custody_and_scientific_work(self):
        c = self.create()
        original_measure, lookup = noise.measure_indexed, c.custodian.inputs_for
        order = []
        def measure(*args):
            self.assertEqual(c.journal.states[c.bindings[0].identity], "started")
            self.assertEqual(self.events(c)[-1]["event_type"], "started")
            self.assertEqual(len(list(c.journal.directory.glob("*.pending"))), 0)
            order.append("measurement")
            return original_measure(*args)
        def custody(request):
            self.assertEqual(self.events(c)[-1]["event_type"], "started")
            order.append("custody")
            return lookup(request)
        with patch.object(noise, "measure_indexed", side_effect=measure) as reads, \
             patch.object(c.custodian, "inputs_for", side_effect=custody):
            c.execute(c.bindings[0])
        self.assertEqual(order, ["custody", "measurement"])
        self.assertEqual(reads.call_count, 1)

    def test_positive_counts_and_replay(self):
        c = self.create()
        decode_impl = BCHCodec.decode
        store_type = type(c.custodian.store)
        retrieve_impl = store_type.get_credential
        with patch.object(noise, "measure_indexed", wraps=noise.measure_indexed) as reads, \
             patch.object(acquisition, "majority_vote3", wraps=acquisition.majority_vote3) as votes, \
             patch.object(BCHCodec, "decode", autospec=True, side_effect=decode_impl) as decodes, \
             patch.object(store_type, "get_credential", autospec=True, side_effect=retrieve_impl) as retrieves:
            self.complete(c)
            self.assertEqual((reads.call_count, votes.call_count, decodes.call_count, retrieves.call_count), (24, 6, 12, 6))
        found = evidence.inspect_journal(c.journal.root, c.journal.directory)
        self.assertFalse(found.requires_stop)
        self.assertEqual((len(found.events), found.planned_unstarted), (36, ()))
        for i, planned in enumerate(c.bindings):
            row = self.row(c, i)
            self.assertEqual(row["operations"], recon.expected_operations(planned.to_dict()["attempt"]["policy"]))
            self.assertEqual(sha256((c.records / (planned.identity + ".json")).read_bytes()).hexdigest(),
                self.events(c)[2*i+1]["record_sha256"])
        self.assertEqual(c.journal.header["durability_mode"], "fixture-process-only")
        self.assertFalse(c.journal.header["power_loss_safety_established"])
        before = {p: p.read_bytes() for directory in (c.records, c.journal.directory) for p in directory.iterdir()}
        provider = c.custodian.replay_provider()
        with patch.object(noise, "measure_indexed", wraps=noise.measure_indexed) as reads, \
             patch.object(BCHCodec, "decode", autospec=True, side_effect=decode_impl) as decodes, \
             patch.object(store_type, "get_credential", side_effect=AssertionError("relookup")):
            result = c.reconcile(provider=provider)
        self.assertTrue(result.verified_scope_complete, result.issues)
        self.assertEqual((reads.call_count, decodes.call_count, provider.source_readings), (24, 13, 24))
        self.assertEqual((result.replay_decodes, result.enrollment_check_decodes), (12, 1))
        self.assertEqual(result.counts["locally_verified"], 18)
        self.assertFalse(result.final_plan_checked)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        second = c.reconcile()
        self.assertTrue(recon.compare_passes(result, second)["consistent"])
        with self.assertRaisesRegex(recon.ReconciliationError, "final-analysis-handoff-blocked"):
            result.analysis_handoff()

    def test_actual_shared_noise_frequencies_reading_zero_vote_and_controls(self):
        c = self.create()
        observed, original = [], noise.measure_indexed
        def measure(*args):
            value = original(*args)
            observed.append((args, value))
            return value
        with patch.object(noise, "measure_indexed", side_effect=measure):
            self.complete(c)
        self.assertEqual(len(c.custodian.device.manufacturing_variation), 128)
        self.assertEqual(len(noise.PAIRS), 64)
        for condition in range(6):
            s, m, t = (self.row(c, 3*condition+i) for i in range(3))
            self.assertEqual(s["readings"][0], m["readings"][0])
            bits = tuple(tuple(r["response"]) for r in m["readings"])
            self.assertEqual(m["effective_response"], list(acquisition.majority_vote3(bits)))
            self.assertEqual(t["readings"], [])
            self.assertIsNone(t["decoder"])
            if condition == 3:
                self.assertEqual(bits, (bits[0],)*3)
        rho1 = [value for args, value in observed if args[1].rho == 1.]
        self.assertTrue(all(v.independent_noise == (0.,)*128 for v in rho1))
        op, common = observed[:4], observed[20:24]
        for (a, x), (b, y) in zip(op, common):
            self.assertEqual(a[2], b[2])
            self.assertEqual(x.shared_noise, y.shared_noise)
            self.assertEqual(x.independent_noise, y.independent_noise)
            self.assertEqual(y.frequencies, tuple(f + b[1].common_offset for f in x.frequencies))
            self.assertEqual(x.response, y.response)
        self.assertTrue(c.reconcile().verified_scope_complete)

    def test_controlled_simulator_inputs_produce_real_c_d_i_w_replay(self):
        c = self.create()
        with controlled_inputs(c.custodian):
            self.complete(c)
            result = c.reconcile()
        self.assertTrue(result.verified_scope_complete, result.issues)
        categories = [o.reconstruction.category for o in result.local_outcomes if o.reconstruction]
        self.assertEqual(categories, ["W", "C", "I", "C", "D", "C", "W", "W", "C", "C", "W", "C"])
        self.assertEqual(set(categories), set("CDIW"))
        for i in range(18):
            self.assertEqual(self.row(c, i)["downstream"], dict(verification="not_invoked", admission="not_invoked",
                session_active=False, authorized_releases=0, inference_calls=0))

    def test_failed_start_prevents_custody_measurement_vote_and_decode(self):
        c = self.create()
        with patch.object(c.journal.io, "publish", side_effect=OSError("private-error")), \
             patch.object(c.custodian, "inputs_for") as custody, \
             patch.object(noise, "measure_indexed") as measure, patch.object(integration, "reconstruct") as decode:
            with self.assertRaisesRegex(integration.IntegrationError, "fixture-execution-stopped"):
                c.execute(c.bindings[0])
            custody.assert_not_called()
            measure.assert_not_called()
            decode.assert_not_called()
        self.assertTrue(c.journal.poisoned)
        self.assert_stopped(c)
        self.assertNotIn(b"private-error", b"".join(p.read_bytes() for p in c.journal.directory.iterdir()))

    def test_custody_lookup_fault_after_start_has_no_puf_work(self):
        c = self.create()
        with patch.object(c.custodian, "inputs_for", side_effect=OSError("private-custody")), \
             patch.object(noise, "measure_indexed") as measure:
            with self.assertRaises(integration.IntegrationError):
                c.execute(c.bindings[0])
            measure.assert_not_called()
        self.assertEqual([e["event_type"] for e in self.events(c)], ["started", "fault"])
        self.assertEqual(self.events(c)[-1]["operations"], dict.fromkeys(recon.OPERATIONS, 0))
        self.assert_stopped(c)

    def test_wrong_custody_binding_prevents_start(self):
        c = self.create()
        c.custodian.context = replace(c.context, run_id="fixture-wrong-run")
        with self.assertRaises(integration.IntegrationError):
            c.execute(c.bindings[0])
        self.assertEqual(self.events(c), ())
        self.assert_stopped(c)

    def test_measurement_fault_types_stop_without_retry_or_outcome(self):
        for error, code in ((noise.CommonModeNumericalError("private"), "numerical_comparison"),
                (ArithmeticError("private"), "numerical_comparison"), (MemoryError(), "resource"),
                (OSError(), "infrastructure"), (KeyboardInterrupt(), "operator_stop")):
            with self.subTest(code=code):
                c = self.create()
                with patch.object(noise, "measure_indexed", side_effect=error) as measure:
                    with self.assertRaises(type(error) if isinstance(error, KeyboardInterrupt) else integration.IntegrationError):
                        c.execute(c.bindings[0])
                    self.assertEqual(measure.call_count, 1)
                self.assertEqual(self.events(c)[-1]["fault_code"], code)
                self.assertEqual(list(c.records.iterdir()), [])
                self.assert_stopped(c)

    def test_partial_majority_records_completed_read_without_replacement(self):
        c = self.create()
        c.execute(c.bindings[0])
        original = noise.measure_indexed
        def fail_second(*args):
            if args[-1] == 1:
                raise KeyboardInterrupt
            return original(*args)
        with patch.object(noise, "measure_indexed", side_effect=fail_second) as reads, \
             patch.object(integration, "reconstruct") as decode:
            with self.assertRaises(KeyboardInterrupt):
                c.execute(c.bindings[1])
            self.assertEqual(reads.call_count, 2)
            decode.assert_not_called()
        self.assertEqual(self.events(c)[-1]["operations"], dict(readings=1, votes=0, reconstructions=0,
            bch_decodes=0, stored_retrievals=0))
        self.assert_stopped(c)

    def test_partial_or_failed_evidence_publication_is_uncertain(self):
        for boundary in ("write", "sync_file", "publish", "sync_directory"):
            with self.subTest(boundary=boundary):
                c = self.create()
                publish = evidence._publish
                def fail(directory, name, raw, io):
                    if directory == c.records:
                        with patch.object(io, boundary, side_effect=OSError("fixture-disk-failure")):
                            return publish(directory, name, raw, io)
                    return publish(directory, name, raw, io)
                with patch.object(evidence, "_publish", side_effect=fail):
                    with self.assertRaises(integration.IntegrationError):
                        c.execute(c.bindings[0])
                self.assertEqual([e["event_type"] for e in self.events(c)], ["started"])
                self.assertTrue(c.journal.poisoned)
                self.assertTrue(list(c.records.iterdir()))
                self.assert_stopped(c)

    def test_short_write_leaves_partial_bytes_and_no_completion(self):
        c = self.create()
        publish, write = evidence._publish, c.journal.io.write
        def fail(directory, name, raw, io):
            if directory == c.records:
                calls = 0
                def partial(fd, data):
                    nonlocal calls
                    calls += 1
                    return write(fd, data[:19]) if calls == 1 else 0
                with patch.object(io, "write", side_effect=partial):
                    return publish(directory, name, raw, io)
            return publish(directory, name, raw, io)
        with patch.object(evidence, "_publish", side_effect=fail), self.assertRaises(integration.IntegrationError):
            c.execute(c.bindings[0])
        self.assertEqual(next(c.records.iterdir()).stat().st_size, 19)
        self.assertEqual([e["event_type"] for e in self.events(c)], ["started"])
        self.assert_stopped(c)

    def test_no_overwrite_evidence(self):
        c = self.create()
        target = c.records / (c.bindings[0].identity + ".json")
        target.write_bytes(b"prior-evidence")
        with self.assertRaises(integration.IntegrationError):
            c.execute(c.bindings[0])
        self.assertEqual(target.read_bytes(), b"prior-evidence")
        self.assertEqual([e["event_type"] for e in self.events(c)], ["started"])
        self.assert_stopped(c)

    def test_failed_completion_preserves_record_and_unresolved_start(self):
        c = self.create()
        append = c.journal.append
        def fail(identity, event_type, **kwargs):
            if event_type == "completed":
                raise OSError
            return append(identity, event_type, **kwargs)
        with patch.object(c.journal, "append", side_effect=fail), self.assertRaises(integration.IntegrationError):
            c.execute(c.bindings[0])
        self.assertEqual(len(list(c.records.iterdir())), 1)
        self.assertEqual([e["event_type"] for e in self.events(c)], ["started"])
        self.assert_stopped(c)

    def test_fault_publication_failure_preserves_uncertainty(self):
        c = self.create()
        append = c.journal.append
        def fail(identity, event_type, **kwargs):
            if event_type == "fault":
                raise OSError
            return append(identity, event_type, **kwargs)
        with patch.object(c.journal, "append", side_effect=fail), \
             patch.object(noise, "measure_indexed", side_effect=MemoryError), self.assertRaises(artificial.ControllerError):
            c.execute(c.bindings[0])
        self.assertTrue(c.stopped and c.journal.poisoned)
        self.assert_stopped(c)

    def test_digest_tampering_fails_before_source_replay(self):
        c = self.complete(self.create())
        target = c.records / (c.bindings[0].identity + ".json")
        target.write_bytes(target.read_bytes() + b" ")
        with patch.object(noise, "measure_indexed") as measure:
            with self.assertRaisesRegex(integration.IntegrationError, "evidence-digest-conflict"):
                c.reconcile()
            measure.assert_not_called()

    def test_journal_tampering_or_unresolved_start_refuses_replay(self):
        c = self.create()
        c.journal.append(c.bindings[0].identity, "started")
        c.close()
        with self.assertRaisesRegex(integration.IntegrationError, "journal-incomplete-or-uncertain"):
            c.reconcile()
        c = self.complete(self.create())
        path = c.journal.directory / "000000000002.event.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(integration.IntegrationError, "journal-incomplete-or-uncertain"):
            c.reconcile()

    def test_missing_record_or_publication_residue_refuses_replay(self):
        for residue in (False, True):
            c = self.complete(self.create())
            if residue:
                (c.records / "orphan.pending").write_bytes(b"partial")
            else:
                (c.records / (c.bindings[0].identity + ".json")).unlink()
            with self.assertRaisesRegex(integration.IntegrationError, "publication-unresolved"):
                c.reconcile()

    def test_changed_enrollment_identity_or_truth_fails_source_replay(self):
        c = self.complete(self.create())
        for material in (replace(c.custodian.enrollment, credential=b"Bad!"),
                replace(c.custodian.enrollment, enrollment_id="fixture-wrong-enrollment",
                    helper=replace(c.custodian.enrollment.helper, enrollment_id="fixture-wrong-enrollment"))):
            provider = c.custodian.replay_provider()
            provider.enrollment = material
            result = c.reconcile(provider=provider)
            self.assertFalse(result.verified_scope_complete)
            self.assertEqual(result.local_outcomes, ())

    def test_changed_manufacturing_or_source_identity_fails_replay(self):
        c = self.complete(self.create())
        provider = c.custodian.replay_provider()
        provider.device = replace(provider.device, manufacturing_variation=(0.,)*128)
        self.assertFalse(c.reconcile(provider=provider).verified_scope_complete)
        provider = c.custodian.replay_provider()
        retained = dict(provider.retained)
        material = retained[c.bindings[0].identity]
        source = material.deterministic_source_inputs
        source = replace(source, spec=replace(source.spec, identity=replace(source.spec.identity, attempt_id=1)))
        retained[c.bindings[0].identity] = replace(material, deterministic_source_inputs=source)
        provider.retained = MappingProxyType(retained)
        result = c.reconcile(provider=provider)
        self.assertFalse(result.verified_scope_complete)
        self.assertEqual(result.local_outcomes, ())

    def test_changed_independent_seed_implementation_fails_even_if_bits_match(self):
        c = self.complete(self.create())
        derive = noise.derive_seed
        def changed(identity, domain, r=None):
            return derive(identity, domain, r) + int(domain == noise.READING and r == 0)
        with patch.object(noise, "derive_seed", side_effect=changed):
            result = c.reconcile()
        self.assertFalse(result.verified_scope_complete)
        self.assertEqual(result.local_outcomes, ())

    def test_rehashed_reading_seed_effective_response_and_decoder_forgery_fail(self):
        c = self.complete(self.create())
        for mutate in (lambda row: row["readings"][0].update(input_seed_sha256="0"*64),
                lambda row: row["effective_response"].__setitem__(0, 1-row["effective_response"][0]),
                lambda row: row["decoder"].update(reported_correction_count=5),
                lambda row: row["readings"][0]["response"].__setitem__(0, 1-row["readings"][0]["response"][0])):
            with self.assertRaises(recon.ReconciliationError):
                self.verify_changed(c, mutate)

    def test_retrieval_replay_uses_original_invocation_without_relookup(self):
        c = self.complete(self.create())
        provider = c.custodian.replay_provider()
        c.custodian.store = Mock()
        c.custodian.store.get_credential.side_effect = AssertionError("new-lookup-forbidden")
        self.assertTrue(c.reconcile(provider=provider).verified_scope_complete)
        c.custodian.store.get_credential.assert_not_called()
        retained = dict(provider.retained)
        identity = c.bindings[2].identity
        original = retained[identity]
        new_record = replace(original.retrieval_evidence.stored_record)
        retained[identity] = replace(original, retrieval_evidence=replace(original.retrieval_evidence,
            stored_record=new_record), replay_inputs=replace(original.replay_inputs, stored_record=new_record))
        provider.retained = MappingProxyType(retained)
        self.assertFalse(c.reconcile(provider=provider).verified_scope_complete)

    def test_unavailable_and_malformed_retrieval_are_outcomes_without_puf_work(self):
        for stored, outcome in ((None, "unavailable"), (b"malformed", "malformed")):
            c = self.create()
            c.custodian.store = Mock()
            c.custodian.store.get_credential.return_value = stored
            self.complete(c)
            result = c.reconcile()
            self.assertTrue(result.verified_scope_complete, result.issues)
            self.assertEqual([o.retrieval_outcome for o in result.local_outcomes if o.policy == recon.T], [outcome]*6)

    def test_stored_lookup_failure_stops_without_read_or_decode(self):
        c = self.create()
        c.execute(c.bindings[0])
        c.execute(c.bindings[1])
        c.custodian.store = Mock()
        c.custodian.store.get_credential.side_effect = OSError("lookup-fault")
        with patch.object(noise, "measure_indexed") as reads, patch.object(integration, "reconstruct") as decode:
            with self.assertRaises(integration.IntegrationError):
                c.execute(c.bindings[2])
            reads.assert_not_called()
            decode.assert_not_called()
        self.assertEqual(self.events(c)[-1]["fault_code"], "infrastructure")
        self.assert_stopped(c)

    def test_duplicate_out_of_order_and_foreign_attempts_cannot_execute(self):
        for kind in ("duplicate", "out-of-order", "foreign"):
            c = self.create()
            planned = c.bindings[1]
            if kind == "duplicate":
                c.execute(c.bindings[0])
                planned = c.bindings[0]
            elif kind == "foreign":
                planned = replace(c.bindings[0], plan_sha256="0"*64)
            with patch.object(noise, "measure_indexed") as reads, self.assertRaises(integration.IntegrationError):
                c.execute(planned)
            reads.assert_not_called()
            self.assert_stopped(c)

    def test_no_reexecution_after_closed_run_or_early_reconciliation(self):
        c = self.create()
        with self.assertRaisesRegex(integration.IntegrationError, "close-journal"):
            c.reconcile()
        self.complete(c)
        with self.assertRaises(integration.IntegrationError):
            c.execute(c.bindings[0])

    def test_custody_repeated_request_and_changed_run_refused(self):
        c = self.create()
        c.execute(c.bindings[0])
        original = c.custodian._retained[c.bindings[0].identity]
        with self.assertRaisesRegex(integration.IntegrationError, "already-invoked"):
            c.custodian.inputs_for(original.request)
        with self.assertRaisesRegex(integration.IntegrationError, "binding-conflict"):
            c.custodian.inputs_for(replace(original.request,
                context=replace(c.context, run_id="fixture-different-run")))

    def test_source_success_does_not_grant_verification_admission_or_inference(self):
        c = self.complete(self.create())
        for mutate in (lambda r: r["downstream"].update(admission="authorized"),
                lambda r: r["downstream"].update(session_active=True),
                lambda r: r["downstream"].update(authorized_releases=1),
                lambda r: r["downstream"].update(inference_calls=1)):
            with self.assertRaises(recon.ReconciliationError):
                self.verify_changed(c, mutate)
        result = c.reconcile()
        self.assertFalse(result.summary()["inference_eligible"])
        self.assertFalse(result.summary()["full_independent_verification"])

    def test_temporary_only_paths_and_bounded_schedule(self):
        custodian = integration.FixtureCustodian()
        self.assertEqual(len(custodian.bindings), 18)
        self.assertEqual(len({p.to_dict()["block"]["device_id"] for p in custodian.bindings}), 1)
        self.assertEqual({p.to_dict()["block"]["attempt_index"] for p in custodian.bindings}, {0})
        with self.assertRaises(evidence.EvidenceError):
            integration.NonfinalController(planning.ROOT, custodian, durability="fixture-process-only")


if __name__ == "__main__":
    unittest.main()
