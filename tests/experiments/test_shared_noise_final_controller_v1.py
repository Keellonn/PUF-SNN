"""Isolated artificial callbacks only; no scientific operations or RNG draws."""

from contextlib import ExitStack
from dataclasses import asdict, fields, replace
import errno
from hashlib import sha256
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from puf_snn.experiments import shared_noise_final_controller_v1 as controller
from puf_snn.experiments import shared_noise_final_evidence_v1 as evidence
from puf_snn.experiments import shared_noise_final_plan_v1 as planning
from puf_snn.experiments import shared_noise_final_measurement_v1 as measurement
from puf_snn.experiments import shared_noise_final_reconciliation_v1 as reconciliation
from puf_snn.experiments import shared_noise_final_analysis_v1 as analysis
import puf_snn.reconstruction as reconstruction


def h(value):
    return sha256(value.encode("ascii")).hexdigest()


CONTEXT = evidence.JournalContext("fixture-controller", "fixture-controller-v1", "fixture-source-v1",
    h("fixture-source"), h("fixture-config"), h("fixture-plan"), "fixture-run")


class ControllerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fixture-controller-tests-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "fixture-evidence-controller"
        # Literal artificial bindings, without scientific plan generation or seeds.
        self.attempts = tuple(evidence.PlannedFixture(h(f"fixture-attempt-{i}"), i,
            h(f"fixture-binding-{i}"), h("fixture-trial"), "fixture-population", "fixture-device",
            "fixture-enrollment", policy) for i, policy in enumerate(planning.POLICIES))
        self.io = evidence.Durability("fixture-process-only")
        self.journals = []
        self.addCleanup(self.close_journals)
        self.callback = Mock(return_value=controller.ArtificialResult(7))
        # All controller paths run with these forbidden boundaries guarded.
        stack = self.enterContext(ExitStack())
        self.forbidden = []
        for module, name in ((measurement, "acquire_measurement"),
                (measurement, "Device"), (measurement.acquisition, "acquire_response"),
                (planning.noise, "CorrelatedResponseReader"), (planning.noise, "measure_indexed"),
                (reconciliation, "reconstruct"), (reconstruction, "reconstruct"),
                (reconciliation, "reconcile_ledger"), (analysis, "analyze_final"),
                (analysis, "evaluate_reconstruction"), (analysis, "bootstrap"),
                (analysis, "Random"), (planning.StudyConfig, "load"),
                (planning, "compile_plan"), (planning, "study_seed"),
                (planning, "seed_digest"), (planning, "Random"),
                (planning.noise, "derive_seed"), (planning.noise, "canonical_seed_bytes"),
                (planning.noise, "Random"),
                (evidence, "obtain_protected_inputs")):
            self.forbidden.append(stack.enter_context(patch.object(module, name,
                side_effect=AssertionError("forbidden-scientific-boundary"))))

    def tearDown(self):
        for forbidden in self.forbidden:
            forbidden.assert_not_called()

    def close_journals(self):
        for journal in self.journals:
            journal.close()

    def create(self):
        journal = evidence.FixtureJournal.create(self.root, self.path, CONTEXT, self.attempts,
            durability=self.io.mode, io=self.io)
        self.journals.append(journal)
        return journal

    def run_fixture(self, journal, index=0, callback=None, context=CONTEXT, attempt=None):
        return controller.execute_fixture(journal, context,
            self.attempts[index] if attempt is None else attempt,
            self.callback if callback is None else callback)

    def inspect(self):
        return evidence.inspect_journal(self.root, self.path)

    def events(self):
        return tuple(map(planning.read_json, self.inspect().events))

    def public_bytes(self):
        return b"".join(p.read_bytes() for p in self.path.iterdir() if p.is_file())

    def assert_blocked(self, journal, index=1):
        callback = Mock(return_value=controller.ArtificialResult(9))
        before = {p.name: p.read_bytes() for p in self.path.iterdir() if p.is_file()}
        with self.assertRaises((controller.ControllerError, evidence.EvidenceError)):
            self.run_fixture(journal, index, callback)
        callback.assert_not_called()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.path.iterdir() if p.is_file()})

    def test_callback_only_after_complete_start_publication_barrier(self):
        journal = self.create()
        order = []
        original = {name: getattr(self.io, name) for name in
                    ("write", "sync_file", "publish", "sync_directory")}

        def wrap(name):
            def call(*args):
                order.append(name)
                return original[name](*args)
            return call

        def work():
            order.append("callback")
            self.assertEqual(order, ["write", "sync_file", "publish", "sync_directory",
                                     "sync_directory", "callback"])
            self.assertFalse(any(p.name.endswith(".pending") for p in self.path.iterdir()))
            found = self.inspect()
            self.assertEqual(found.unresolved_started, (self.attempts[0].policy_attempt_id,))
            self.assertEqual([e["event_type"] for e in self.events()], ["started"])
            self.assertFalse(any(self.events()[0]["operations"].values()))
            return controller.ArtificialResult(7)

        callback = Mock(side_effect=work)
        with ExitStack() as stack:
            for name in original:
                stack.enter_context(patch.object(self.io, name, side_effect=wrap(name)))
            result = self.run_fixture(journal, callback=callback)
        callback.assert_called_once_with()
        self.assertIs(type(result), controller.CompletedFixture)

    def test_completed_order_binding_digest_and_narrow_result(self):
        journal = self.create()
        result = self.run_fixture(journal)
        self.callback.assert_called_once_with()
        start, end = self.events()
        expected_raw = evidence.canonical(dict(
            schema_version=controller.VERSION + ":artificial-record", fixture_only=True,
            journal_id=journal.header["journal_id"], planned=asdict(self.attempts[0]),
            artificial_value=7, operation_accounting="fixture-declaration-only"))
        self.assertEqual((start["event_type"], end["event_type"]), ("started", "completed"))
        self.assertEqual((start["sequence"], end["sequence"]), (1, 2))
        self.assertEqual(end["previous_event_sha256"], start["event_sha256"])
        self.assertEqual(end["record_sha256"], sha256(expected_raw).hexdigest())
        self.assertEqual(end["operations"], reconciliation.expected_operations(self.attempts[0].policy))
        for event in (start, end):
            self.assertEqual(event["binding_sha256"], self.attempts[0].binding_sha256)
            self.assertEqual(event["context"], asdict(CONTEXT))
            self.assertEqual(event["policy_attempt_id"], result.policy_attempt_id)
        self.assertEqual(asdict(result), dict(journal_id=journal.header["journal_id"],
            policy_attempt_id=self.attempts[0].policy_attempt_id, execution_index=0,
            started_event_sha256=start["event_sha256"], completed_event_sha256=end["event_sha256"]))
        self.assertEqual(len(fields(result)), 5)

    def test_start_failures_never_invoke_callback_including_visible_start(self):
        for boundary in ("write", "sync_file", "publish", "sync_directory"):
            with self.subTest(boundary=boundary):
                self.path = self.root / ("fixture-evidence-start-" + boundary.replace("_", "-"))
                journal = self.create()
                with patch.object(self.io, boundary, side_effect=OSError(errno.EIO, "SECRET")):
                    with self.assertRaisesRegex(controller.ControllerError, "^fixture-start-publication-uncertain$"):
                        self.run_fixture(journal)
                self.callback.assert_not_called()
                self.assertTrue(journal.poisoned)
                self.assertTrue(self.inspect().requires_stop)
                self.assert_blocked(journal, 0)

    def test_callback_exceptions_publish_fault_and_redact_details(self):
        for i, (error, code) in enumerate(((RuntimeError("SECRET key"), "infrastructure"),
                (FloatingPointError("SECRET numerical"), "numerical_comparison"),
                (MemoryError("SECRET resource"), "resource"))):
            with self.subTest(code=code):
                self.path = self.root / f"fixture-evidence-fault-{i}"
                journal = self.create()
                callback = Mock(side_effect=error)
                with self.assertRaisesRegex(controller.ControllerError, "^artificial-callback-failed$") as raised:
                    self.run_fixture(journal, callback=callback)
                self.assertTrue(raised.exception.__suppress_context__)
                callback.assert_called_once_with()
                journal.close()
                start, fault = self.events()
                self.assertEqual((start["event_type"], fault["event_type"]), ("started", "fault"))
                self.assertEqual(fault["fault_code"], code)
                self.assertIsNone(fault["record_sha256"])
                self.assertFalse(any(fault["operations"].values()))
                self.assertTrue(self.inspect().requires_stop)
                self.assertNotIn(b"SECRET", self.public_bytes())

    def test_terminal_fault_blocks_further_starts_on_open_writer(self):
        journal = self.create()
        with self.assertRaises(controller.ControllerError):
            self.run_fixture(journal, callback=Mock(side_effect=RuntimeError()))
        self.assertFalse(journal.closed)
        self.assertFalse(journal.poisoned)
        self.assert_blocked(journal)
        with self.assertRaises(evidence.EvidenceError):
            journal.append(self.attempts[1].policy_attempt_id, "started")

    def test_interruptions_propagate_once_with_operator_stop(self):
        for i, error in enumerate((KeyboardInterrupt("SECRET"), SystemExit(17), GeneratorExit())):
            with self.subTest(kind=type(error).__name__):
                self.path = self.root / f"fixture-evidence-interrupt-{i}"
                journal = self.create()
                callback = Mock(side_effect=error)
                with self.assertRaises(type(error)) as raised:
                    self.run_fixture(journal, callback=callback)
                self.assertIs(raised.exception, error)
                callback.assert_called_once_with()
                self.assertEqual(self.events()[-1]["fault_code"], "operator_stop")
                self.assert_blocked(journal)
                self.assertNotIn(b"SECRET", self.public_bytes())

    def test_process_loss_leaves_started_without_resume_or_inferred_completion(self):
        journal = self.create()
        journal.append(self.attempts[0].policy_attempt_id, "started")
        self.assert_blocked(journal, 0)
        self.assert_blocked(journal)
        journal.close()
        first = self.inspect()
        self.assertTrue(first.requires_stop)
        self.assertTrue(first.unknown_work_possible)
        self.assertEqual(first.unresolved_started, (self.attempts[0].policy_attempt_id,))
        self.assertEqual(len(first.planned_unstarted), 2)
        self.assertEqual(first, self.inspect())
        with self.assertRaises(FileExistsError):
            self.create()

    def test_completion_failure_preserves_incomplete_journal_and_never_retries(self):
        journal = self.create()
        real_publish = self.io.publish
        publications = []

        def publish(pending, target):
            publications.append(target.name)
            if target.name == "000000000002.event.json":
                raise OSError(errno.ENOSPC, "SECRET")
            real_publish(pending, target)

        with patch.object(self.io, "publish", side_effect=publish):
            with self.assertRaisesRegex(controller.ControllerError, "^fixture-completion-publication-uncertain$"):
                self.run_fixture(journal)
        self.callback.assert_called_once_with()
        self.assertEqual(publications, ["000000000001.event.json", "000000000002.event.json"])
        journal.close()
        found = self.inspect()
        self.assertTrue(found.requires_stop)
        self.assertTrue(found.unknown_work_possible)
        self.assertTrue(found.unresolved_started)
        self.assertIn("interrupted-publication", found.issues)
        self.assertTrue((self.path / "000000000002.event.json.pending").exists())
        self.assertEqual([e["event_type"] for e in self.events()], ["started"])
        self.assert_blocked(journal)

    def test_visible_completion_with_failed_final_barrier_still_stops(self):
        journal = self.create()
        syncs = []

        def sync(path):
            syncs.append(path)
            if len(syncs) == 4:  # second completion directory sync, after unlink
                raise OSError(errno.EIO, "SECRET")

        with patch.object(self.io, "sync_directory", side_effect=sync):
            with self.assertRaisesRegex(controller.ControllerError, "completion-publication-uncertain"):
                self.run_fixture(journal)
        self.callback.assert_called_once_with()
        self.assertTrue(journal.poisoned)
        self.assertEqual([e["event_type"] for e in self.events()], ["started", "completed"])
        self.assertTrue(self.inspect().requires_stop)  # visible is not accepted
        self.assertIn("unclean-or-active-writer", self.inspect().issues)
        self.assert_blocked(journal)

    def test_fault_publication_failure_leaves_unresolved_start_and_poison(self):
        journal = self.create()
        real_publish = self.io.publish
        publications = []

        def publish(pending, target):
            publications.append(target.name)
            if target.name == "000000000002.event.json":
                raise OSError(errno.EIO, "SECRET fault publication")
            real_publish(pending, target)

        callback = Mock(side_effect=RuntimeError("SECRET callback"))
        with patch.object(self.io, "publish", side_effect=publish):
            with self.assertRaisesRegex(controller.ControllerError, "^fixture-fault-publication-uncertain$"):
                self.run_fixture(journal, callback=callback)
        callback.assert_called_once_with()
        self.assertEqual(len(publications), 2)
        journal.close()
        self.assertTrue(journal.poisoned)
        self.assertTrue(self.inspect().unresolved_started)
        self.assertTrue(self.inspect().requires_stop)
        self.assertNotIn(b"SECRET", self.public_bytes())
        self.assert_blocked(journal)

    def test_interruption_during_publication_never_repeats_work(self):
        journal = self.create()
        real_publish = self.io.publish

        def publish(pending, target):
            if target.name == "000000000002.event.json":
                raise KeyboardInterrupt()
            real_publish(pending, target)

        with patch.object(self.io, "publish", side_effect=publish):
            with self.assertRaises(KeyboardInterrupt):
                self.run_fixture(journal)
        self.callback.assert_called_once_with()
        self.assertTrue(journal.poisoned)
        self.assertTrue(self.inspect().unresolved_started)
        self.assert_blocked(journal)

    def test_duplicate_invocation_refused(self):
        journal = self.create()
        self.run_fixture(journal)
        self.assert_blocked(journal, 0)
        self.callback.assert_called_once_with()

    def test_attempt_order_and_binding_conflicts_refused_before_work(self):
        journal = self.create()
        self.assert_blocked(journal, 1)
        for field, value in (("binding_sha256", h("wrong")), ("trial_id", h("wrong")),
                ("policy_attempt_id", h("unknown")), ("execution_index", 1),
                ("policy", planning.POLICIES[1]), ("device_id", "fixture-other")):
            with self.subTest(field=field), self.assertRaisesRegex(controller.ControllerError, "fixture-attempt-conflict"):
                self.run_fixture(journal, attempt=replace(self.attempts[0], **{field: value}))
        self.callback.assert_not_called()
        self.assertEqual(self.inspect().events, ())

    def test_context_and_nonfixture_inputs_refused_before_work(self):
        journal = self.create()
        with self.assertRaisesRegex(controller.ControllerError, "fixture-context-conflict"):
            self.run_fixture(journal, context=replace(CONTEXT, run_id="fixture-other"))
        for writer in (self.path, self.inspect(), Mock(), object()):
            with self.assertRaisesRegex(controller.ControllerError, "active-fixture-writer-required"):
                self.run_fixture(writer)
        for context in (asdict(CONTEXT), None, object()):
            with self.assertRaisesRegex(controller.ControllerError, "fixture-context-required"):
                self.run_fixture(journal, context=context)
        with self.assertRaisesRegex(controller.ControllerError, "planned-fixture-required"):
            self.run_fixture(journal, attempt=asdict(self.attempts[0]))
        with self.assertRaisesRegex(controller.ControllerError, "artificial-callback-required"):
            self.run_fixture(journal, callback=object())
        # Revalidation refuses mutated reserved identities despite the right type.
        context = replace(CONTEXT)
        object.__setattr__(context, "experiment_id", planning.VERSION)
        with self.assertRaises(evidence.EvidenceError):
            self.run_fixture(journal, context=context)
        attempt = replace(self.attempts[0])
        object.__setattr__(attempt, "device_id", "w9f-p000-d00")
        with self.assertRaises(evidence.EvidenceError):
            self.run_fixture(journal, attempt=attempt)
        self.callback.assert_not_called()
        self.assertEqual(self.inspect().events, ())

    def test_closed_and_poisoned_writers_refused(self):
        journal = self.create()
        journal.poisoned = True
        self.assert_blocked(journal, 0)
        journal.close()
        self.assert_blocked(journal, 0)
        self.path = self.root / "fixture-evidence-closed-clean"
        journal = self.create()
        journal.close()
        self.assertFalse(journal.poisoned)
        self.assert_blocked(journal, 0)

    def test_existing_journal_inspection_is_read_only_and_cannot_resume(self):
        journal = self.create()
        self.run_fixture(journal)
        journal.close()
        before = {p.name: p.read_bytes() for p in self.path.iterdir()}
        first, second = self.inspect(), self.inspect()
        self.assertEqual(first, second)
        self.assertFalse(hasattr(first, "append"))
        self.assertFalse(hasattr(evidence.FixtureJournal, "resume"))
        with self.assertRaises(FileExistsError):
            self.create()
        self.assert_blocked(journal)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.path.iterdir()})

    def test_missing_plans_not_completed_despite_no_stop_issues(self):
        journal = self.create()
        result = self.run_fixture(journal)
        journal.close()
        found = self.inspect()
        self.assertFalse(found.requires_stop)
        self.assertEqual(found.planned_unstarted, tuple(a.policy_attempt_id for a in self.attempts[1:]))
        self.assertEqual(len([e for e in self.events() if e["event_type"] == "completed"]), 1)
        self.assertEqual(result.policy_attempt_id, self.attempts[0].policy_attempt_id)
        self.assertFalse(hasattr(result, "all_planned_completed"))

    def test_full_fixture_coverage_requires_each_attempt_and_is_not_verification(self):
        journal = self.create()
        results = [self.run_fixture(journal, i) for i in range(3)]
        self.assertEqual(self.callback.call_count, 3)
        self.assertTrue(self.inspect().requires_stop)  # still an active writer
        journal.close()
        found = self.inspect()
        self.assertFalse(found.requires_stop)
        self.assertEqual(found.planned_unstarted, ())
        self.assertEqual(found.unresolved_started, ())
        self.assertEqual(found.faulted, ())
        self.assertEqual(len(results), 3)
        for i, event in enumerate(self.events()[1::2]):
            self.assertEqual(event["operations"], reconciliation.expected_operations(self.attempts[i].policy))
        # Hash-consistent complete fixture history still has no authentication.
        anchor = found.local_checkpoint("fixture-checkpoint")
        self.assertFalse(anchor.independently_authenticated)
        with self.assertRaisesRegex(evidence.EvidenceError, "self-generated"):
            evidence.validate_checkpoint(found, anchor, checkpoint_id="fixture-checkpoint")
        trust = evidence.validate_checkpoint(found, anchor, checkpoint_id="fixture-checkpoint",
                                             require_independent_input=False)
        for name in ("independently_authenticated", "scientific_execution_verified",
                     "power_loss_safety_established", "inference_eligible"):
            self.assertFalse(trust[name])

    def test_unstarted_empty_journal_is_explicitly_incomplete(self):
        self.create().close()
        found = self.inspect()
        self.assertFalse(found.requires_stop)
        self.assertEqual(found.events, ())
        self.assertEqual(found.planned_unstarted, tuple(a.policy_attempt_id for a in self.attempts))

    def test_result_contract_rejects_success_flags_payloads_and_secrets(self):
        bad = (True, {"success": True}, {"credential": b"SECRET"}, b"SECRET", object(),
               controller.ArtificialResult(True), controller.ArtificialResult(-1),
               controller.ArtificialResult(65536), controller.ArtificialResult(float("nan")),
               controller.ArtificialResult("SECRET"), controller.ArtificialResult(b"SECRET"))
        for i, value in enumerate(bad):
            with self.subTest(index=i):
                self.path = self.root / f"fixture-evidence-invalid-{i}"
                journal = self.create()
                callback = Mock(return_value=value)
                with self.assertRaisesRegex(controller.ControllerError, "^invalid-artificial-result$"):
                    self.run_fixture(journal, callback=callback)
                callback.assert_called_once_with()
                self.assertEqual(self.events()[-1]["fault_code"], "integrity")
                self.assertTrue(self.inspect().requires_stop)
                self.assertNotIn(b"SECRET", self.public_bytes())
                self.assert_blocked(journal)

    def test_no_credentials_keys_or_arbitrary_callback_data_are_serialized(self):
        journal = self.create()
        self.run_fixture(journal)
        journal.close()
        public = self.public_bytes()
        for value in (b"credential", b"session_key", b"verifier_key", b"SECRET", b"success",
                      b"manufacturing_state", b"authorization", b"seed"):
            self.assertNotIn(value, public)
        self.callback.assert_called_once_with()  # no input/custody/authorization objects
        self.assertEqual({p.name for p in self.path.iterdir()},
            {"journal.json", "000000000001.event.json", "000000000002.event.json"})

    def test_changed_disk_or_handle_history_refused_before_work(self):
        for i, change in enumerate((lambda j: setattr(j, "previous", h("wrong")),
                lambda j: j.header.update(fixture_only=False),
                lambda j: (self.path / "unexpected").write_bytes(b"fixture"),
                lambda j: (self.path / "journal.json").write_bytes(b"{}"))):
            with self.subTest(index=i):
                self.path = self.root / f"fixture-evidence-changed-{i}"
                journal = self.create()
                change(journal)
                self.assert_blocked(journal, 0)
        self.callback.assert_not_called()

    def test_strict_windows_durability_fails_before_callback(self):
        if os.name != "nt":
            self.skipTest("Windows strict durability guard")
        with self.assertRaisesRegex(evidence.EvidenceError, "directory-durability-unavailable"):
            journal = evidence.FixtureJournal.create(self.root, self.path, CONTEXT, self.attempts)
            self.run_fixture(journal)
        self.assertFalse(self.path.exists())
        self.callback.assert_not_called()

    def test_fixture_mode_makes_no_power_loss_claim(self):
        journal = self.create()
        self.run_fixture(journal)
        journal.close()
        header = planning.read_json(self.inspect().header)
        self.assertEqual(header["durability_mode"], "fixture-process-only")
        self.assertFalse(header["power_loss_safety_established"])


if __name__ == "__main__":
    unittest.main()
