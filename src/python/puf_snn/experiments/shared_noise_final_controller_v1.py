"""One artificial callback behind Task 8's fixture publication barrier.

This is not a scientific runner or an execution authorization. The caller owns
the newly created FixtureJournal and closes it explicitly. Existing directories
are inspect-only; this module has no create, reopen, recovery or retry API.

planned -> started (append must return) -> callback once -> completed OR fault.
Any publication failure poisons the handle and leaves evidence untouched. A
process loss can leave a started event without a terminal event; inspection and
a separate recovery disposition are then required. No work is ever repeated.

ArtificialResult has only a bounded integer, with no payload, success flag,
credentials, seed or scientific outcome. Callbacks receive no arguments. They
are trusted artificial Python code, not sandboxed against malicious closures.
Operation counts are fixture declarations, NOT independently observed source
operations. Fault counts impute no partial source work.

A CompletedFixture identifies one callback completion only. After close, use
inspect_journal: full fixture coverage additionally requires no stopping issues,
unresolved starts, faults OR planned_unstarted attempts. requires_stop=False by
itself is insufficient. Hash consistency is not independent authentication or
scientific verification, and neither establishes study authorization. Windows
fixture-process-only publication does not establish power-loss durability.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Callable

from . import shared_noise_final_evidence_v1 as evidence
from .shared_noise_final_reconciliation_v1 import expected_operations

VERSION = "shared-noise-final-controller-v1"


class ControllerError(ValueError):
    """Fixed public diagnostic; callback exception text is never journaled."""


def _check(ok, code):
    if not ok:
        raise ControllerError(code)


@dataclass(frozen=True, slots=True)
class ArtificialResult:
    """Artificial metadata only, validated after the callback returns."""

    value: int


@dataclass(frozen=True, slots=True)
class CompletedFixture:
    """Local event references, never a coverage or verification receipt."""

    journal_id: str
    policy_attempt_id: str
    execution_index: int
    started_event_sha256: str
    completed_event_sha256: str


def _active_fixture(journal, context, attempt):
    _check(type(journal) is evidence.FixtureJournal, "active-fixture-writer-required")
    _check(not journal.closed and not journal.poisoned, "writer-closed-or-poisoned")
    _check(type(context) is evidence.JournalContext, "fixture-context-required")
    _check(type(attempt) is evidence.PlannedFixture, "planned-fixture-required")
    # Revalidate even accidentally altered frozen objects. Task 8 owns these
    # contracts, the path checks, canonical parser and all publication semantics.
    evidence.JournalContext(**asdict(context))
    evidence.PlannedFixture(**asdict(attempt))
    found = evidence.inspect_journal(journal.root, journal.directory)
    _check(found.issues == ("unclean-or-active-writer",)
           and not found.unresolved_started and not found.faulted,
           "fixture-journal-requires-disposition")
    header = evidence.planning.read_json(found.header)
    _check(header["context"] == asdict(context), "fixture-context-conflict")
    _check(evidence.canonical(journal.header) == found.header, "writer-header-conflict")
    attempts = {a["policy_attempt_id"]: a for a in header["attempts"]}
    _check(attempts.get(attempt.policy_attempt_id) == asdict(attempt), "fixture-attempt-conflict")
    history = tuple(map(evidence.planning.read_json, found.events))
    _check(journal.attempts == attempts
           and journal.sequence == len(history) and journal.previous == found.head_sha256
           and journal.last_raw == (found.events[-1] if history else None)
           and journal.states == {e["policy_attempt_id"]: e["to_state"] for e in history}
           and journal.operations == {e["policy_attempt_id"]: e["operations"] for e in history},
           "writer-history-conflict")
    _check(attempt.policy_attempt_id in found.planned_unstarted, "fixture-already-invoked")
    _check(found.planned_unstarted[0] == attempt.policy_attempt_id, "fixture-execution-order-conflict")


def _append(journal, identity, event_type, failure_code, **metadata):
    try:
        return journal.append(identity, event_type, **metadata)
    except BaseException as error:
        # Also stop if failure occurred before the journal could poison itself.
        # Never remove residue, publish a replacement terminal event or retry.
        journal.poisoned = True
        if isinstance(error, Exception):
            raise ControllerError(failure_code) from None
        raise


def execute_fixture(journal: evidence.FixtureJournal, context: evidence.JournalContext,
                    attempt: evidence.PlannedFixture,
                    callback: Callable[[], ArtificialResult]) -> CompletedFixture:
    """Execute exactly one explicitly supplied artificial callback, without retry.

    Ordinary callback failures are redacted and raised after attempting a fault.
    ArithmeticError -> numerical_comparison; MemoryError -> resource; other
    Exception -> infrastructure. BaseException interruptions -> operator_stop,
    then re-raise the original interruption. Exception text is never serialized.
    Invalid return metadata -> integrity fault. A fault publication failure
    instead raises its own stopping error; the handle remains poisoned.
    """
    _active_fixture(journal, context, attempt)
    _check(callable(callback), "artificial-callback-required")
    identity = attempt.policy_attempt_id
    started = _append(journal, identity, "started", "fixture-start-publication-uncertain")
    # This line is reachable only after the journal's complete start barrier.
    try:
        result = callback()
    except BaseException as error:
        code = ("resource" if isinstance(error, MemoryError) else
                "numerical_comparison" if isinstance(error, ArithmeticError) else
                "infrastructure" if isinstance(error, Exception) else "operator_stop")
        _append(journal, identity, "fault", "fixture-fault-publication-uncertain", fault_code=code)
        if isinstance(error, Exception):
            raise ControllerError("artificial-callback-failed") from None
        raise
    try:
        _check(type(result) is ArtificialResult and type(result.value) is int
               and 0 <= result.value <= 65535, "invalid-artificial-result")
        # Fixed closed record, constructed here. Raw callback data is not written.
        raw = evidence.canonical(dict(schema_version=VERSION + ":artificial-record",
            fixture_only=True, journal_id=journal.header["journal_id"],
            planned=asdict(attempt), artificial_value=result.value,
            operation_accounting="fixture-declaration-only"))
        record_sha256 = sha256(raw).hexdigest()
    except BaseException as error:
        _append(journal, identity, "fault", "fixture-fault-publication-uncertain",
                fault_code="integrity" if isinstance(error, Exception) else "operator_stop")
        if isinstance(error, Exception):
            raise ControllerError("invalid-artificial-result") from None
        raise
    completed = _append(journal, identity, "completed", "fixture-completion-publication-uncertain",
                        operations=expected_operations(attempt.policy), record_sha256=record_sha256)
    return CompletedFixture(journal.header["journal_id"], identity, attempt.execution_index,
        evidence.planning.read_json(started)["event_sha256"],
        evidence.planning.read_json(completed)["event_sha256"])
