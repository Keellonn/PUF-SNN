"""Artificial metadata only; all writes use TemporaryDirectory.

No acquisition, enrollment construction, BCH, sessions, analysis or reserved RNG.
"""
from contextlib import ExitStack
from dataclasses import asdict, replace
import errno
from hashlib import sha256
import os
from pathlib import Path
import pickle
import tempfile
import unittest
from unittest.mock import Mock, patch

from puf_snn.experiments import shared_noise_final_evidence_v1 as ev
from puf_snn.experiments import shared_noise_final_reconciliation_v1 as recon
from puf_snn.experiments import shared_noise_final_plan_v1 as plan
from puf_snn.reconstruction import HelperData


def h(value):
    return sha256(value.encode("ascii")).hexdigest()


CONTEXT = ev.JournalContext("fixture-experiment", "fixture-experiment-v1", "fixture-source-v1", h("source"),
                          h("config"), h("plan"), "fixture-run")
RAW = b'{"artificial_fixture":"no-scientific-result"}'


def bindings():
    """Literal fixture identities; derive hashes only, never draw random numbers."""
    identity = plan.noise.AttemptIdentity(9173, "fixture-group", "fixture-device", "fixture-noise:op:r000", 0)
    b = dict(schema_version=plan.VERSION+":planned-block", experiment_id=plan.VERSION,
        config_sha256=CONTEXT.config_sha256, population_id="fixture-group", device_id="fixture-device",
        enrollment_id="fixture-enrollment", condition="op_rho000", attempt_index=0,
        sigma=.15, rho=.0, common_offset=0, noise_identity=asdict(identity),
        noise_shared_seed_sha256=plan.seed_digest(identity, plan.noise.SESSION),
        reading_seed_sha256=[plan.seed_digest(identity, plan.noise.READING, r) for r in range(3)],
        common_offset_seed_sha256=None, linked_operating_trial_id=None)
    b["trial_id"] = plan.trial_id(b)
    b.update(policy_order=list(plan.POLICIES), block_index=0, attempts=[])
    for i, policy in enumerate(plan.POLICIES):
        indices = ([0], [0, 1, 2], [])[i]
        b["attempts"].append(dict(schema_version=plan.VERSION+":planned-attempt", experiment_id=plan.VERSION,
            condition=b["condition"], trial_id=b["trial_id"], policy=policy,
            policy_attempt_id=plan.attempt_id(b, policy), execution_index=i, reading_indices=indices,
            noise_shared_seed_sha256=b["noise_shared_seed_sha256"] if indices else None,
            reading_seed_sha256=[b["reading_seed_sha256"][r] for r in indices]))
    return recon.block_bindings(CONTEXT.config_sha256, CONTEXT.plan_sha256, b)


class JournalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fixture-journal-tests-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "fixture-evidence-main"
        self.planned = bindings()
        self.attempts = tuple(ev.PlannedFixture.from_planned(p) for p in self.planned)
        self.io = ev.Durability("fixture-process-only")

    def create(self, attempts=None):
        return ev.FixtureJournal.create(self.root, self.path, CONTEXT,
            self.attempts if attempts is None else attempts, durability=self.io.mode, io=self.io)

    def inspect(self):
        return ev.inspect_journal(self.root, self.path)

    def start(self, j, i=0):
        return j.append(self.attempts[i].policy_attempt_id, "started")

    def complete(self, j, i=0):
        return j.append(self.attempts[i].policy_attempt_id, "completed",
            operations=recon.expected_operations(self.attempts[i].policy), record_sha256=sha256(RAW).hexdigest())

    def fault(self, j, i=0):
        return j.append(self.attempts[i].policy_attempt_id, "fault", fault_code="infrastructure")

    def event(self, i):
        return self.path / f"{i:012d}.event.json"

    def change(self, sequence, mutate, rehash=False):
        obj = plan.read_json(self.event(sequence).read_bytes())
        mutate(obj)
        if rehash:
            obj["event_sha256"] = ev.digest({k: v for k, v in obj.items() if k != "event_sha256"})
        self.event(sequence).write_bytes(ev.canonical(obj))

    def anchor(self, header, history):
        # Expected values retained by an independent fixture caller, not read
        # from inspect/local_checkpoint or the record envelope being checked.
        head = plan.read_json(history[-1])["event_sha256"] if history else sha256(header).hexdigest()
        return ev.FixtureAnchor(ev.Checkpoint("fixture-checkpoint", plan.read_json(header)["journal_id"],
            sha256(header).hexdigest(), len(history), head), "independent-fixture-input")

    def test_fixture_demonstration_and_task7_metadata(self):
        j = self.create()
        header = ev.canonical(ev._header(CONTEXT, self.attempts, self.io.mode))
        history = (self.start(j), self.complete(j), self.start(j, 1))
        j.close()
        first, second = self.inspect(), self.inspect()
        self.assertEqual(first.events, history)
        self.assertEqual(first.unresolved_started, (self.attempts[1].policy_attempt_id,))
        self.assertEqual(first.planned_unstarted, (self.attempts[2].policy_attempt_id,))
        self.assertTrue(first.requires_stop)
        self.assertEqual(first.issues, ())
        anchor = self.anchor(header, history)
        trust = ev.validate_checkpoint(second, anchor, checkpoint_id="fixture-checkpoint")
        self.assertTrue(trust["independent_input"])
        self.assertFalse(trust["independently_authenticated"])
        self.assertFalse(trust["scientific_execution_verified"])
        bound = ev.recorded_execution(second, self.planned[0], RAW, anchor, checkpoint_id="fixture-checkpoint")
        self.assertEqual(bound.checkpoint_metadata()["provenance"], "independent-fixture-input")
        self.assertFalse(bound.checkpoint_metadata()["independently_authenticated"])
        record = bound.record
        self.assertIsInstance(record, recon.RecordedExecution)
        self.assertEqual(record.expected_raw_sha256, sha256(RAW).hexdigest())
        with self.assertRaises(recon.ReconciliationError):
            recon._parse(record)  # Artificial metadata cannot pass as a result.
        self.assertEqual(ev.compare_inspections(first, second)["changed"], ())
        self.assertEqual(set(p.name for p in self.path.iterdir()),
                         {"journal.json", *(f"{i:012d}.event.json" for i in range(1, 4))})
        with self.assertRaises(FileExistsError):
            self.create()
        # A separate journal demonstrates fault without ever continuing after it.
        self.path = self.root / "fixture-evidence-fault"
        with self.create() as j:
            self.start(j)
            self.fault(j)
            with self.assertRaises(ev.EvidenceError):
                self.start(j, 1)
        found = self.inspect()
        self.assertEqual(found.faulted, (self.attempts[0].policy_attempt_id,))
        self.assertEqual(len(found.events), 2)
        self.assertTrue(found.requires_stop)

    def test_normal_start_completion_for_all_policies(self):
        with self.create() as j:
            for i in range(3):
                self.start(j, i)
                self.complete(j, i)
        self.assertEqual(len(self.inspect().events), 6)
        self.assertFalse(self.inspect().requires_stop)

    def test_planned_does_not_imply_started_or_completed(self):
        self.create().close()
        found = self.inspect()
        self.assertEqual(found.events, ())
        self.assertEqual(found.planned_unstarted, tuple(a.policy_attempt_id for a in self.attempts))
        self.assertEqual(found.unresolved_started, ())

    def test_completed_and_fault_are_terminal(self):
        for terminal in ("completed", "fault"):
            self.path = self.root / ("fixture-evidence-"+terminal)
            with self.subTest(terminal=terminal), self.create() as j:
                self.start(j)
                self.complete(j) if terminal == "completed" else self.fault(j)
                for action in (lambda: self.start(j), lambda: self.complete(j), lambda: self.fault(j)):
                    with self.assertRaises(ev.EvidenceError):
                        action()
            self.assertEqual(len(self.inspect().events), 2)

    def test_without_start_duplicate_and_out_of_order_rejected(self):
        with self.create() as j:
            for action in (lambda: self.complete(j), lambda: self.fault(j), lambda: self.start(j, 1)):
                with self.assertRaises(ev.EvidenceError):
                    action()
            self.start(j)
            for action in (lambda: self.start(j), lambda: self.start(j, 1)):
                with self.assertRaises(ev.EvidenceError):
                    action()
        self.assertEqual(len(self.inspect().events), 1)

    def test_duplicate_ids_and_execution_index_conflicts(self):
        bad = ((self.attempts[0], replace(self.attempts[1], policy_attempt_id=self.attempts[0].policy_attempt_id)),
               (self.attempts[0], replace(self.attempts[1], execution_index=0)), tuple(reversed(self.attempts)))
        for attempts in bad:
            with self.assertRaises(ev.EvidenceError):
                self.create(attempts)
            self.assertFalse(self.path.exists())

    def test_operation_bounds_types_and_fault_reasons(self):
        with self.create() as j:
            self.start(j)
            limits = recon.expected_operations(self.attempts[0].policy)
            for counts in ({**limits, "readings": 2}, {**limits, "readings": True}, {**limits, "votes": -1},
                           {}, {**limits, "credential": b"SECRET"}, b"SECRET"):
                with self.assertRaises(ev.EvidenceError):
                    j.append(self.attempts[0].policy_attempt_id, "completed", operations=counts, record_sha256=h("row"))
            for reason in (None, "SECRET provider detail", b"KEY"):
                with self.assertRaises(ev.EvidenceError):
                    j.append(self.attempts[0].policy_attempt_id, "fault", fault_code=reason)
            self.fault(j)

    def test_no_payload_or_credentials_and_counts_snapshotted(self):
        with self.create() as j:
            self.start(j)
            with self.assertRaises(TypeError):
                j.append(self.attempts[0].policy_attempt_id, "completed", credential=b"SECRET")
            counts = recon.expected_operations(self.attempts[0].policy)
            j.append(self.attempts[0].policy_attempt_id, "completed", operations=counts, record_sha256=h("row"))
            counts["readings"] = 999
            self.assertEqual(j.operations[self.attempts[0].policy_attempt_id]["readings"], 1)
        public = b"".join(p.read_bytes() for p in self.path.iterdir())
        for forbidden in (b"SECRET", b"session_key", b"verifier_key", b"credential", b"reference", b"manufacturing_state"):
            self.assertNotIn(forbidden, public)

    def test_invalid_header_versions_fields_and_noncanonical_json(self):
        self.create().close()
        path = self.path / "journal.json"
        original = path.read_bytes()
        for mutate in (lambda o: o.update(schema_version="v999"), lambda o: o.update(secret="SECRET"),
                       lambda o: o.update(fixture_only=False), lambda o: o.update(durability_mode="guaranteed")):
            obj = plan.read_json(original)
            mutate(obj)
            path.write_bytes(ev.canonical(obj))
            with self.assertRaises(ev.EvidenceError):
                self.inspect()
        path.write_bytes(b'{"a":1,"a":2}')
        with self.assertRaises(ev.EvidenceError):
            self.inspect()

    def test_invalid_event_versions_transitions_and_hash_links(self):
        with self.create() as j:
            self.start(j)
            self.complete(j)
        original = self.event(2).read_bytes()
        cases = (lambda e: e.update(schema_version="v999"), lambda e: e.update(previous_event_sha256=h("wrong")),
                 lambda e: e.update(sequence=1), lambda e: e.update(execution_index=True),
                 lambda e: e.update(binding_sha256=h("wrong")), lambda e: e.update(to_state="fault"),
                 lambda e: e.update(record_sha256=None), lambda e: e.update(credential="SECRET"))
        for mutate in cases:
            self.event(2).write_bytes(original)
            self.change(2, mutate, rehash=True)
            found = self.inspect()
            self.assertTrue(found.issues)
            self.assertEqual(len(found.events), 1)
            self.assertEqual(found.unresolved_started, (self.attempts[0].policy_attempt_id,))

    def test_truncated_torn_and_invalid_event_data(self):
        with self.create() as j:
            self.start(j)
            self.complete(j)
        original = self.event(2).read_bytes()
        for raw in (original[:len(original)//2], original+b"\n", b"", b"{}", b'{"a":1,"a":2}',
                    b'{"a":NaN}', b'{"a":1e999}', b"\xff"):
            with self.subTest(raw=raw[:16]):
                self.event(2).write_bytes(raw)
                self.assertTrue(self.inspect().issues)
                self.assertEqual(len(self.inspect().events), 1)

    def test_missing_reordered_modified_events_and_separate_pass(self):
        with self.create() as j:
            self.start(j)
            self.complete(j)
            self.start(j, 1)
        first = self.inspect()
        a, b = self.event(1).read_bytes(), self.event(2).read_bytes()
        self.event(2).unlink()
        second = self.inspect()
        self.assertIn("missing-or-reordered-event", second.issues)
        self.assertEqual(ev.compare_inspections(first, second)["removed"], (self.event(2).name,))
        self.event(1).write_bytes(b)
        self.event(2).write_bytes(a)
        self.assertTrue(self.inspect().issues)
        self.event(1).write_bytes(a)
        self.event(2).write_bytes(b)
        self.change(2, lambda e: e.update(record_sha256=h("tampered")))
        second = self.inspect()
        self.assertIn("event-content-hash-mismatch", second.issues)
        self.assertEqual(ev.compare_inspections(first, second)["changed"], (self.event(2).name,))

    def test_external_checkpoint_missing_conflicting_and_self_generated(self):
        with self.create() as j:
            header = ev.canonical(j.header)
            history = (self.start(j), self.complete(j))
        found = self.inspect()
        anchor = self.anchor(header, history)
        changes = dict(checkpoint_id="fixture-other", journal_id=h("other"), header_sha256=h("other"),
                       event_count=1, head_sha256=h("other"))
        bad = [None, found.local_checkpoint("fixture-checkpoint")]
        bad.extend(replace(anchor, checkpoint=replace(anchor.checkpoint, **{k: v})) for k, v in changes.items())
        for supplied in bad:
            with self.assertRaises(ev.EvidenceError):
                ev.validate_checkpoint(found, supplied, checkpoint_id="fixture-checkpoint")
        local = ev.validate_checkpoint(found, found.local_checkpoint("fixture-checkpoint"),
            checkpoint_id="fixture-checkpoint", require_independent_input=False)
        self.assertFalse(local["independent_input"])
        self.assertFalse(local["independently_authenticated"])

    def test_checkpoint_detects_tail_loss_and_same_journal_recomputation(self):
        with self.create() as j:
            header = ev.canonical(j.header)
            history = (self.start(j), self.complete(j))
        anchor = self.anchor(header, history)
        self.change(2, lambda e: e.update(record_sha256=h("tampered")), rehash=True)
        found = self.inspect()
        self.assertEqual(found.issues, ())
        with self.assertRaisesRegex(ev.EvidenceError, "checkpoint-content-conflict"):
            ev.validate_checkpoint(found, anchor, checkpoint_id="fixture-checkpoint")
        with self.assertRaisesRegex(ev.EvidenceError, "self-generated"):
            ev.validate_checkpoint(found, found.local_checkpoint("fixture-checkpoint"), checkpoint_id="fixture-checkpoint")
        self.event(2).unlink()
        found = self.inspect()
        self.assertEqual(found.issues, ())
        self.assertTrue(found.unresolved_started)
        with self.assertRaises(ev.EvidenceError):
            ev.validate_checkpoint(found, anchor, checkpoint_id="fixture-checkpoint")

    def test_task7_adapter_rejects_modified_raw_wrong_binding_and_unstarted(self):
        with self.create() as j:
            header = ev.canonical(j.header)
            history = (self.start(j), self.complete(j))
        found, anchor = self.inspect(), self.anchor(header, history)
        for planned, raw in ((self.planned[0], RAW+b" "), (self.planned[1], RAW),
                             (replace(self.planned[0], plan_sha256=h("wrong")), RAW)):
            with self.assertRaises(ev.EvidenceError):
                ev.recorded_execution(found, planned, raw, anchor, checkpoint_id="fixture-checkpoint")

    def test_task7_index_preserves_each_record_binding_and_provenance(self):
        payloads = [ev.canonical(dict(artificial_fixture_index=i)) for i in range(3)]
        history = []
        with self.create() as j:
            header = ev.canonical(j.header)
            for i, raw in enumerate(payloads):
                history.append(self.start(j, i))
                history.append(j.append(self.attempts[i].policy_attempt_id, "completed",
                    operations=recon.expected_operations(self.attempts[i].policy), record_sha256=sha256(raw).hexdigest()))
        found, anchor = self.inspect(), self.anchor(header, history)
        for i in (2, 0, 1):
            bound = ev.recorded_execution(found, self.planned[i], payloads[i], anchor, checkpoint_id="fixture-checkpoint")
            self.assertEqual(bound.record.expected_raw_sha256, sha256(payloads[i]).hexdigest())
            self.assertEqual(bound.anchor, anchor)
            self.assertFalse(bound.checkpoint_metadata()["scientific_execution_verified"])
            with self.assertRaisesRegex(ev.EvidenceError, "record-content-conflict"):
                ev.recorded_execution(found, self.planned[i], payloads[(i+1) % 3], anchor, checkpoint_id="fixture-checkpoint")

    def test_partial_write_disk_full_io_error_and_interruption(self):
        for number, error in enumerate((OSError(errno.ENOSPC, "SECRET disk full"), OSError(errno.EIO, "SECRET"), KeyboardInterrupt())):
            self.path = self.root / ("fixture-evidence-fail-"+str(number))
            j = self.create()
            self.start(j)
            real_write, calls = self.io.write, []
            def torn(fd, raw):
                calls.append(len(raw))
                if len(calls) == 1:
                    return real_write(fd, raw[:23])
                raise error
            with patch.object(self.io, "write", side_effect=torn):
                with self.assertRaises(type(error)):
                    self.complete(j)
            j.close()
            found = self.inspect()
            self.assertEqual(len(calls), 2)
            self.assertIn("interrupted-publication", found.issues)
            self.assertIn("unclean-or-active-writer", found.issues)
            self.assertEqual(len(found.events), 1)
            self.assertEqual((self.path / "000000000002.event.json.pending").stat().st_size, 23)
            self.assertFalse(self.event(2).exists())
            with self.assertRaises(ev.EvidenceError):
                self.complete(j)
            self.assertTrue(found.unresolved_started)

    def test_zero_write_and_short_successful_writes(self):
        j = self.create()
        real = self.io.write
        with patch.object(self.io, "write", side_effect=lambda fd, raw: real(fd, raw[:17])):
            self.start(j)
        with patch.object(self.io, "write", return_value=0):
            with self.assertRaisesRegex(ev.EvidenceError, "short-write"):
                self.complete(j)
        j.close()
        self.assertTrue(self.inspect().requires_stop)

    def test_failed_sync_publication_and_cleanup_boundaries(self):
        for boundary in ("sync_file", "publish", "after_publish", "cleanup_sync", "unlink"):
            self.path = self.root / ("fixture-evidence-"+boundary.replace("_", "-"))
            j = self.create()
            self.start(j)
            error, calls = OSError(errno.EIO, "fixture"), []
            def sync(path):
                calls.append(path)
                if boundary == "after_publish" or len(calls) == 2:
                    raise error
            with ExitStack() as stack:
                if boundary in ("sync_file", "publish"):
                    stack.enter_context(patch.object(self.io, boundary, side_effect=error))
                elif boundary == "unlink":
                    stack.enter_context(patch.object(Path, "unlink", side_effect=error))
                else:
                    stack.enter_context(patch.object(self.io, "sync_directory", side_effect=sync))
                with self.assertRaises(OSError):
                    self.complete(j)
            j.close()
            found = self.inspect()
            self.assertIn("unclean-or-active-writer", found.issues)
            self.assertTrue(found.requires_stop)
            self.assertTrue(j.poisoned)
            with self.assertRaises(ev.EvidenceError):
                self.start(j, 1)
            if boundary == "cleanup_sync":
                self.assertEqual(len(found.events), 2)  # Visible, still blocked.
            else:
                self.assertTrue(any("publication" in i or "unsafe" in i for i in found.issues))

    def test_crash_before_or_after_start_never_resumes(self):
        for started in (False, True):
            self.path = self.root / ("fixture-evidence-crash-"+str(started).lower())
            j = self.create()
            if started:
                self.start(j)
            del j  # No destructor cleanup: emulate process loss.
            first, second = self.inspect(), self.inspect()
            self.assertEqual(first, second)
            self.assertIn("unclean-or-active-writer", first.issues)
            self.assertEqual(len(first.events), int(started))
            with self.assertRaises(FileExistsError):
                self.create()
            self.assertFalse(hasattr(first, "append"))
            self.assertFalse(hasattr(ev.FixtureJournal, "resume"))

    def test_failed_start_barrier_returns_no_work_permission(self):
        j = self.create()
        work = Mock()
        with patch.object(self.io, "sync_file", side_effect=OSError(errno.EIO, "fixture")):
            with self.assertRaises(OSError):
                self.start(j)
                work()  # A future guarded caller can only proceed after return.
        work.assert_not_called()
        j.close()
        found = self.inspect()
        self.assertEqual(found.events, ())
        self.assertTrue(found.unknown_work_possible)
        self.assertTrue(found.requires_stop)

    def test_read_io_failure_and_changed_tail_block_writer(self):
        j = self.create()
        self.start(j)
        with patch.object(ev, "_read", side_effect=OSError(errno.EIO, "fixture")):
            with self.assertRaises(OSError):
                self.complete(j)
        self.assertTrue(j.poisoned)
        j.close()
        self.assertTrue(self.inspect().requires_stop)
        self.path = self.root / "fixture-evidence-changed-tail"
        j = self.create()
        self.start(j)
        self.event(1).write_bytes(b"{}")
        with self.assertRaises(ev.EvidenceError):
            self.complete(j)
        self.assertTrue(j.poisoned)
        j.close()

    def test_close_directory_sync_failure_blocks_future_calls(self):
        j = self.create()
        self.start(j)
        with patch.object(self.io, "sync_directory", side_effect=OSError(errno.EIO, "fixture")):
            with self.assertRaises(OSError):
                j.close()
        self.assertTrue(j.poisoned)
        self.assertIn("unclean-or-active-writer", self.inspect().issues)
        with self.assertRaises(ev.EvidenceError):
            self.complete(j)

    def test_interrupted_header_creation_never_replaced(self):
        with patch.object(self.io, "publish", side_effect=OSError(errno.EIO, "fixture")):
            with self.assertRaises(OSError):
                self.create()
        self.assertTrue((self.path / "writer.lock").exists())
        self.assertTrue((self.path / "journal.json.pending").exists())
        with self.assertRaises(FileNotFoundError):
            self.inspect()
        with self.assertRaises(FileExistsError):
            self.create()

    def test_no_overwrite_on_atomic_publication_race(self):
        j = self.create()
        real = self.io.publish
        def race(pending, target):
            target.write_bytes(b"preexisting fixture content")
            real(pending, target)
        with patch.object(self.io, "publish", side_effect=race):
            with self.assertRaises(FileExistsError):
                self.start(j)
        self.assertEqual(self.event(1).read_bytes(), b"preexisting fixture content")
        j.close()
        self.assertTrue(self.inspect().requires_stop)

    def test_platform_durability_limits_and_barrier_order(self):
        if os.name == "nt":
            with self.assertRaisesRegex(ev.EvidenceError, "directory-durability-unavailable"):
                ev.FixtureJournal.create(self.root, self.path, CONTEXT, self.attempts)
            self.assertFalse(self.path.exists())
        j = self.create()
        calls = []
        original = {name: getattr(self.io, name) for name in ("write", "sync_file", "publish", "sync_directory")}
        def wrap(name):
            def invoke(*args):
                calls.append(name)
                return original[name](*args)
            return invoke
        with ExitStack() as stack:
            for name in original:
                stack.enter_context(patch.object(self.io, name, side_effect=wrap(name)))
            self.start(j)
        self.assertEqual(calls, ["write", "sync_file", "publish", "sync_directory", "sync_directory"])
        j.close()
        self.assertFalse(plan.read_json(self.inspect().header)["power_loss_safety_established"])

    @unittest.skipUnless(os.name == "posix", "POSIX directory-fsync integration only")
    def test_native_directory_fsync_and_unsupported_operation_fail_closed(self):
        with ev.FixtureJournal.create(self.root, self.path, CONTEXT, self.attempts) as j:
            self.start(j)
            self.complete(j)
        self.assertFalse(self.inspect().requires_stop)
        self.path = self.root / "fixture-evidence-unsupported"
        with patch.object(ev.Durability, "sync_directory", side_effect=OSError(errno.EINVAL, "unsupported")):
            with self.assertRaises(OSError):
                ev.FixtureJournal.create(self.root, self.path, CONTEXT, self.attempts)

    def test_path_traversal_aliases_history_and_reserved_destinations(self):
        cases = ((self.root, self.root / ".." / self.path.name), (self.root, self.root / "wrong-name"),
                 (self.root, self.root / "fixture-evidence-x."), (self.root, self.root / "fixture-evidence-x:stream"),
                 (plan.ROOT / "results", plan.ROOT / "results" / self.path.name),
                 (Path(tempfile.gettempdir()), Path(tempfile.gettempdir()) / self.path.name))
        for root, target in cases:
            with self.assertRaises(ev.EvidenceError):
                ev.FixtureJournal.create(root, target, CONTEXT, self.attempts, durability=self.io.mode)
        for name in ("results", "week-9", "shared-noise-final-v1"):
            root = self.root / name
            root.mkdir()
            target = root / ("reserved-final-run" if name == "shared-noise-final-v1" else self.path.name)
            with self.assertRaises(ev.EvidenceError):
                ev.FixtureJournal.create(root, target, CONTEXT, self.attempts, durability=self.io.mode)
            self.assertFalse(target.exists())
        root = self.root / "nested"
        root.mkdir()
        (root / "manifest.json").write_bytes(b"{}")
        with self.assertRaises(ev.EvidenceError):
            ev.FixtureJournal.create(root, root / self.path.name, CONTEXT, self.attempts, durability=self.io.mode)

    def test_unsafe_existing_files_and_hardlinks(self):
        self.path.write_bytes(b"preexisting")
        with self.assertRaises(FileExistsError):
            self.create()
        self.assertEqual(self.path.read_bytes(), b"preexisting")
        self.path.unlink()
        with self.create() as j:
            self.start(j)
        alias = self.root / "linked-file"
        os.link(self.event(1), alias)
        self.assertTrue(any("unsafe" in i for i in self.inspect().issues))
        alias.unlink()
        self.event(1).unlink()
        self.event(1).mkdir()
        self.assertTrue(self.inspect().issues)

    def test_linked_root_rejected_if_symlinks_supported(self):
        alias = self.root / "alias"
        try:
            alias.symlink_to(self.root, target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation unavailable without platform privilege")
        with self.assertRaises(ev.EvidenceError):
            ev.FixtureJournal.create(alias, alias / self.path.name, CONTEXT, self.attempts, durability=self.io.mode)

    def test_reserved_context_and_source_identities_rejected(self):
        for key, value in (("experiment_id", plan.VERSION), ("experiment_version", "v999"),
                           ("source_version", "final-v1"), ("run_id", "final-run")):
            with self.assertRaises(ev.EvidenceError):
                replace(CONTEXT, **{key: value})
        with self.assertRaises(ev.EvidenceError):
            replace(self.attempts[0], device_id="w9f-p000-d00")
        obj = self.planned[0].to_dict()
        obj["block"]["noise_identity"]["noise_domain_id"] = plan.VERSION+":op:r000"
        with self.assertRaises(ev.EvidenceError):
            ev.PlannedFixture.from_planned(replace(self.planned[0], block_json=ev.canonical(obj["block"])))


class CustodyTests(unittest.TestCase):
    def setUp(self):
        self.planned = bindings()[0]
        spec = ev.PlannedFixture.from_planned(self.planned)
        self.request = ev.CustodyRequest(ev.CUSTODY_VERSION, CONTEXT, spec, h("invocation"))
        # All-zero literal codeword/reference/helper: no enroll/encode/decode call.
        helper = HelperData((0,)*63, enrollment_id="fixture-enrollment")
        self.enrollment = recon.EnrollmentMaterial("fixture-group", "fixture-device", "fixture-enrollment",
                                                   (0,)*64, helper, b"\x00"*4)
        self.replay = recon.ReplayInputs(self.planned.digest, CONTEXT.run_id, CONTEXT.source_id, self.enrollment)
        self.material = ev.ProtectedInputs(self.request, self.replay, object(), object())

    def obtain(self, material):
        provider = Mock()
        provider.inputs_for.return_value = material
        return ev.obtain_protected_inputs(provider, self.request, self.planned)

    def test_transient_interface_redaction_and_serialization_refusal(self):
        self.assertIs(self.obtain(self.material), self.material)
        self.assertNotIn("SECRET", repr(self.material))
        with self.assertRaises(TypeError):
            pickle.dumps(self.material)
        with self.assertRaises(TypeError):
            ev.canonical(self.material)

    def test_version_source_enrollment_and_invocation_mismatches(self):
        with self.assertRaises(ev.EvidenceError):
            replace(self.request, version="v999")
        wrong = replace(self.enrollment, device_id="fixture-other")
        cases = (replace(self.material, request=replace(self.request, invocation_id=h("other"))),
            replace(self.material, request=replace(self.request, context=replace(CONTEXT, source_version="fixture-other-v1"))),
            replace(self.material, replay_inputs=replace(self.replay, source_id=h("other"))),
            replace(self.material, replay_inputs=replace(self.replay, binding_sha256=h("other"))),
            replace(self.material, replay_inputs=replace(self.replay, run_id="fixture-other")),
            replace(self.material, replay_inputs=replace(self.replay, enrollment=wrong)),
            replace(self.material, replay_inputs={"replay_passed": True, "credential": b"SECRET"}),
            replace(self.material, manufacturing_state=None), replace(self.material, deterministic_source_inputs=None))
        for material in cases:
            with self.assertRaises(ev.EvidenceError):
                self.obtain(material)

    def test_stored_invocation_requires_its_own_evidence(self):
        planned = bindings()[2]
        request = replace(self.request, planned=ev.PlannedFixture.from_planned(planned))
        provider = Mock()
        provider.inputs_for.return_value = replace(self.material, request=request,
            replay_inputs=replace(self.replay, binding_sha256=planned.digest))
        with self.assertRaisesRegex(ev.EvidenceError, "missing-invocation"):
            ev.obtain_protected_inputs(provider, request, planned)
        receipt = ev.InvocationRetrievalEvidence(request, provider.inputs_for.return_value.replay_inputs.stored_record,
                                                h("fixture-retrieval-provenance"))
        supplied = replace(provider.inputs_for.return_value, retrieval_evidence=receipt)
        provider.inputs_for.return_value = supplied
        self.assertIs(ev.obtain_protected_inputs(provider, request, planned), supplied)
        for receipt in (object(), replace(receipt, request=replace(request, invocation_id=h("other"))),
                        replace(receipt, stored_record=object())):
            provider.inputs_for.return_value = replace(supplied, retrieval_evidence=receipt)
            with self.assertRaises(ev.EvidenceError):
                ev.obtain_protected_inputs(provider, request, planned)

    def test_provider_errors_redacted_and_wrong_plan_refused_before_call(self):
        provider = Mock()
        provider.inputs_for.side_effect = RuntimeError("SECRET enrollment")
        with self.assertRaisesRegex(ev.EvidenceError, "^protected-inputs-unavailable$"):
            ev.obtain_protected_inputs(provider, self.request, self.planned)
        provider.reset_mock()
        request = replace(self.request, context=replace(CONTEXT, plan_sha256=h("other")))
        with self.assertRaises(ev.EvidenceError):
            ev.obtain_protected_inputs(provider, request, self.planned)
        provider.inputs_for.assert_not_called()


if __name__ == "__main__":
    unittest.main()
