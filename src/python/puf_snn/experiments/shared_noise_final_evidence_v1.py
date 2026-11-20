"""Fixture-only durable journal and prospective protected-custody boundary.

This is NOT a runner, enrollment store, final receipt or execution authorization.
Only artificial metadata in an isolated temporary namespace is writable. Planned
attempts live in an immutable header; events are started -> completed OR fault.
No event/filename absence establishes completion. A fault stops the entire writer.
An unresolved start, dirty writer lease or publication residue requires a separately
approved disposition. Reopening is inspection only: no resume/retry/repair API.

Publication: exclusive pending file, complete write, file fsync, atomic no-replace
hard link, directory fsync (when requested/supported), unlink pending, directory
fsync. A persistent exclusive writer lease covers failures at all these boundaries.
Failures poison the writer, retain evidence and never trigger retries or rollback.
On POSIX, directory-fsync requests fail closed on unsupported operations; filesystem,
mount and hardware semantics still require host qualification. On Windows the only
implemented mode explicitly reports fixture-process-only: file fsync is used but
directory-entry/power-loss durability is NOT established. Neither mode certifies
power-loss safety merely from successful system calls. No historical evidence
writer is reused: its overwrite/rename/sealing semantics are incompatible. The
tested planner canonical JSON, strict parser and object-digest recipe are reused.

Threat model: accidental faults and offline integrity comparison, with one trusted
filesystem owner during a write/read pass. Paths reject links and aliases, but
check/use races, malicious Python, admins and hostile concurrent filesystem writers
are NOT contained. Ordinary permissions are not a verified security boundary.
Raw PUF responses/device profiles (including simulated data) remain sensitive;
this journal stores neither. Hash chains prove consistency only, not execution,
researcher identity or tamper-proof storage. Even independent fixture anchor input
is unauthenticated. External retention/authentication is an unmet prerequisite.

ProtectedSourceCustodian is logically separate from this untrusted journal. A real
implementation still needs physical access control, reviewed storage permissions,
encryption/key custody where applicable, retention/deletion policy (including
backups), transient-data handling, and trusted independent replay provenance.
Redaction/pickle refusal do not provide secure memory, erasure or process isolation.
No actual persistent secret storage, signatures, remote services or scientific
source generation are implemented here. Closed public schemas have no arbitrary
payload, exception-text, credential, session-key, verifier-key or private-object slot.
"""

from dataclasses import asdict, dataclass, field
from functools import cached_property
from hashlib import sha256
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import tempfile
from types import MappingProxyType
from typing import Protocol

from . import shared_noise_final_plan_v1 as planning
from . import shared_noise_final_reconciliation_v1 as reconciliation

VERSION = "shared-noise-final-evidence-v1"
CUSTODY_VERSION = VERSION + ":protected-source-v1"
PREFIX = "fixture-evidence-"
FAULTS = ("numerical_comparison", "infrastructure", "resource", "integrity", "operator_stop")
MODES = ("directory-fsync", "fixture-process-only")
MAX_ATTEMPTS = 108_000
MAX_HEADER = 128 * 1024 * 1024
MAX_EVENT = 8192
canonical = planning.canonical
digest = planning.object_digest


class EvidenceError(ValueError):
    """Fixed secret-free code. Provider/OS exception text is never journaled."""


def check(ok, code):
    if not ok:
        raise EvidenceError(code)


def _exact(obj, fields):
    check(type(obj) is dict and set(obj) == set(fields), "invalid-fields")


def _hash(value):
    return type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None


def _fixture(value):
    return type(value) is str and re.fullmatch(r"fixture-[a-z0-9][a-z0-9-]{0,95}", value) is not None


@dataclass(frozen=True)
class JournalContext:
    experiment_id: str
    experiment_version: str
    source_version: str
    source_id: str
    config_sha256: str
    plan_sha256: str
    run_id: str

    def __post_init__(self):
        check(all(_fixture(v) for v in (self.experiment_id, self.experiment_version, self.source_version, self.run_id)),
              "fixture-context-required")
        check(all(_hash(v) for v in (self.source_id, self.config_sha256, self.plan_sha256)), "invalid-context-digest")


@dataclass(frozen=True)
class PlannedFixture:
    """Public planned binding; no scientific inputs or authoritative truth.

    Digests/indices match Task 7 PlannedAttempt. Fixture identities and domains
    are required even though Task 4/7 schema version names are retained there.
    Generic construction is metadata-only and cannot certify a scientific plan.
    """

    policy_attempt_id: str
    execution_index: int
    binding_sha256: str
    trial_id: str
    population_id: str
    device_id: str
    enrollment_id: str
    policy: str

    def __post_init__(self):
        check(all(_hash(v) for v in (self.policy_attempt_id, self.binding_sha256, self.trial_id)), "invalid-attempt-digest")
        check(type(self.execution_index) is int and 0 <= self.execution_index < MAX_ATTEMPTS, "invalid-execution-index")
        check(all(_fixture(v) for v in (self.population_id, self.device_id, self.enrollment_id)), "fixture-device-required")
        check(self.policy in planning.POLICIES, "invalid-policy")

    @classmethod
    def from_planned(cls, planned):
        check(type(planned) is reconciliation.PlannedAttempt, "planned-attempt-required")
        obj = planned.to_dict()
        b, a = obj["block"], obj["attempt"]
        planning.validate_schema("attempt", a)
        check(b["noise_identity"]["noise_domain_id"].startswith("fixture-"), "fixture-source-domain-required")
        check(b["trial_id"] == a["trial_id"] == planning.trial_id(b)
              and a["policy_attempt_id"] == planning.attempt_id(b, a["policy"]), "planned-identity-mismatch")
        return cls(a["policy_attempt_id"], a["execution_index"], planned.digest, b["trial_id"],
                   b["population_id"], b["device_id"], b["enrollment_id"], a["policy"])


def _checked_path(fixture_root, directory):
    """Fixed direct-child namespace; never create root or any results namespace."""
    for raw in (os.fspath(fixture_root), os.fspath(directory)):
        win = PureWindowsPath(raw)
        check(not raw.startswith(("\\\\", "//")) and not (win.drive and not win.root)
              and ".." not in re.split(r"[/\\]", raw), "unsafe-path")
    root, target = Path(fixture_root).absolute(), Path(directory).absolute()
    check(root.is_dir() and root != Path(tempfile.gettempdir()).absolute(), "isolated-temporary-root-required")
    check(any(root.resolve().is_relative_to(p.resolve()) and root.resolve() != p.resolve()
              for p in (Path(tempfile.gettempdir()), planning.ROOT / "tmp")), "temporary-root-required")
    check(target.parent == root and re.fullmatch(PREFIX + r"[a-z0-9][a-z0-9-]{0,63}", target.name), "invalid-fixture-namespace")
    for ancestor in (target, *target.parents):
        check(not ancestor.is_symlink() and not ancestor.is_junction(), "linked-path")
        check(ancestor.name.rstrip(" .") == ancestor.name and ":" not in ancestor.name, "path-alias")
        check(ancestor.name.casefold() not in ("results", "sim_results", ".git", ".codex", ".agents")
              and not re.fullmatch(r"week-?\d+", ancestor.name.casefold()), "prohibited-destination")
        check(not any((ancestor / name).exists() for name in
                      ("manifest.json", "source-manifest.json", "COMPLETE", "INCOMPLETE.json")), "nested-evidence")
    return target


def _read(path, limit):
    info = path.lstat()
    check(stat.S_ISREG(info.st_mode) and not path.is_symlink() and not path.is_junction()
          and info.st_nlink == 1 and info.st_size <= limit, "unsafe-existing-file")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    check(len(raw) <= limit, "oversize-file")
    return raw


def _json(raw):
    try:
        obj = planning.read_json(raw)
        check(canonical(obj) == raw, "noncanonical-json")
        return obj
    except (ValueError, TypeError, UnicodeError, OverflowError):
        raise EvidenceError("invalid-json") from None


class Durability:
    """Injectable OS boundaries; tests use real files and precise failures.

    directory-fsync is unavailable on Windows in this implementation. Explicit
    fixture-process-only mode cannot be mistaken for a power-loss guarantee.
    No operation is retried, including EINTR/sharing/disk-full errors.
    """

    def __init__(self, mode):
        check(mode in MODES, "unsupported-durability-mode")
        check(mode != "directory-fsync" or os.name == "posix", "directory-durability-unavailable")
        self.mode = mode

    def sync_file(self, descriptor):
        os.fsync(descriptor)

    def sync_directory(self, path):
        if self.mode == "directory-fsync":
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def write(self, descriptor, raw):
        return os.write(descriptor, raw)

    def publish(self, pending, target):
        # Atomic create-if-absent, unlike os.replace; no cross-filesystem move.
        os.link(pending, target)


def _publish(directory, name, raw, io):
    pending = directory / (name + ".pending")
    fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        offset = 0
        while offset < len(raw):
            written = io.write(fd, raw[offset:])
            check(type(written) is int and 0 < written <= len(raw) - offset, "short-write")
            offset += written
        io.sync_file(fd)
    finally:
        os.close(fd)
    io.publish(pending, directory / name)
    io.sync_directory(directory)
    pending.unlink()
    io.sync_directory(directory)


def _header(context, attempts, mode):
    check(type(context) is JournalContext, "journal-context-required")
    check(0 < len(attempts) <= MAX_ATTEMPTS and all(type(a) is PlannedFixture for a in attempts), "invalid-planned-fixtures")
    check([a.execution_index for a in attempts] == list(range(len(attempts))), "execution-index-conflict")
    check(len({a.policy_attempt_id for a in attempts}) == len(attempts), "duplicate-attempt-id")
    obj = dict(schema_version=VERSION + ":header", fixture_only=True, context=asdict(context),
               attempts=[asdict(a) for a in attempts], durability_mode=mode,
               power_loss_safety_established=False)
    obj["journal_id"] = digest(obj)
    return obj


def _parse_header(raw):
    obj = _json(raw)
    _exact(obj, ("schema_version", "fixture_only", "context", "attempts", "durability_mode",
                 "power_loss_safety_established", "journal_id"))
    check(obj["schema_version"] == VERSION + ":header", "unsupported-journal-version")
    check(obj["durability_mode"] in MODES and type(obj["attempts"]) is list, "invalid-header")
    try:
        expected = _header(JournalContext(**obj["context"]), tuple(PlannedFixture(**a) for a in obj["attempts"]), obj["durability_mode"])
    except (TypeError, KeyError):
        raise EvidenceError("invalid-header") from None
    check(canonical(expected) == raw, "header-identity-mismatch")
    return obj


def _transition(event, header, states, operations, previous, sequence, *, apply=True):
    _exact(event, ("schema_version", "journal_id", "context", "sequence", "event_type", "policy_attempt_id",
                   "execution_index", "binding_sha256", "previous_event_sha256", "event_sha256",
                   "from_state", "to_state", "fault_code", "operations", "record_sha256"))
    check(event["schema_version"] == VERSION + ":event", "unsupported-event-version")
    check(type(event["sequence"]) is int and event["sequence"] == sequence, "event-sequence-conflict")
    check(event["journal_id"] == header["journal_id"] and event["context"] == header["context"], "event-context-conflict")
    check(event["previous_event_sha256"] == previous, "broken-hash-chain")
    check(event["event_sha256"] == digest({k: v for k, v in event.items() if k != "event_sha256"}), "event-content-hash-mismatch")
    index = event["execution_index"]
    check(type(index) is int and 0 <= index < len(header["attempts"]), "unknown-execution-index")
    attempt = header["attempts"][index]
    identity = attempt["policy_attempt_id"]
    check(event["policy_attempt_id"] == identity and event["binding_sha256"] == attempt["binding_sha256"], "event-attempt-conflict")
    before, after = states.get(identity, "planned"), event["event_type"]
    check(event["from_state"] == before and event["to_state"] == after, "state-transition-conflict")
    check(after in ("started", "completed", "fault") and
          ((before == "planned" and after == "started") or (before == "started" and after in ("completed", "fault"))),
          "invalid-transition")
    if after == "started":
        check(index == len(states), "execution-order-conflict")
        check(index == 0 or states.get(header["attempts"][index - 1]["policy_attempt_id"]) == "completed", "stopping-condition")
    check(event["fault_code"] in FAULTS if after == "fault" else event["fault_code"] is None, "invalid-fault-code")
    counts = event["operations"]
    limits = reconciliation.expected_operations(attempt["policy"])
    _exact(counts, limits)
    check(all(type(v) is int and 0 <= v <= limits[k] for k, v in counts.items()), "operation-bound-exceeded")
    check(all(counts[k] >= operations.get(identity, {}).get(k, 0) for k in limits), "operation-count-regression")
    check(after != "started" or not any(counts.values()), "start-has-work")
    check(after != "completed" or counts == limits, "incomplete-operation-accounting")
    check(_hash(event["record_sha256"]) if after == "completed" else event["record_sha256"] is None, "invalid-record-digest")
    if apply:
        states[identity], operations[identity] = after, counts


@dataclass(frozen=True)
class Inspection:
    """Exact canonical history prefix, plus deterministic stopping diagnostics.

    Even valid completed metadata asserts only an artificial fixture transition;
    it is never a verified scientific outcome. Corruption stops prefix parsing.
    All file fingerprints remain available for separate read-pass comparison.
    planned_unstarted means no start in the validated prefix, never proof that
    work did not happen. Any corrupt/interrupted prefix implies unknown work.
    """

    header: bytes
    events: tuple[bytes, ...]
    file_hashes: tuple[tuple[str, str], ...]
    issues: tuple[str, ...]
    planned_unstarted: tuple[str, ...]
    unresolved_started: tuple[str, ...]
    faulted: tuple[str, ...]

    @property
    def requires_stop(self):
        return bool(self.issues or self.unresolved_started or self.faulted)

    @property
    def unknown_work_possible(self):
        return bool(self.issues or self.unresolved_started)

    @cached_property
    def _metadata(self):
        # One linear indexing pass, not a full-header parse per Task 7 record.
        obj = _parse_header(self.header)
        return MappingProxyType(dict(journal_id=obj["journal_id"], context=JournalContext(**obj["context"]),
            attempts=MappingProxyType({a["policy_attempt_id"]: canonical(a) for a in obj["attempts"]})))

    @cached_property
    def _completed_hashes(self):
        return MappingProxyType({event["policy_attempt_id"]: event["record_sha256"]
            for event in map(_json, self.events) if event["event_type"] == "completed"})

    @cached_property
    def header_sha256(self):
        return sha256(self.header).hexdigest()

    @cached_property
    def head_sha256(self):
        return _json(self.events[-1])["event_sha256"] if self.events else self.header_sha256

    def local_checkpoint(self, checkpoint_id):
        """Self-generated hashes are explicitly NOT independent anchor input."""
        return FixtureAnchor(Checkpoint(checkpoint_id, self._metadata["journal_id"],
            self.header_sha256, len(self.events), self.head_sha256), "local-self-generated")


def inspect_journal(fixture_root, directory):
    """Read only; never repair, remove residue, resume work or emit a receipt."""
    directory = _checked_path(fixture_root, directory)
    check(directory.is_dir(), "journal-directory-required")
    raw = _read(directory / "journal.json", MAX_HEADER)
    header = _parse_header(raw)
    issues, history, hashes, states, operations = [], [], [], {}, {}
    previous = sha256(raw).hexdigest()
    files = sorted(directory.iterdir(), key=lambda p: p.name)
    check(len(files) <= 4 * len(header["attempts"]) + 5, "journal-file-cap-exceeded")
    event_files = []
    for path in files:
        try:
            data = _read(path, MAX_HEADER if path.name == "journal.json" else MAX_EVENT)
            hashes.append((path.name, sha256(data).hexdigest()))
        except (OSError, EvidenceError):
            issues.append("unsafe-or-unreadable-file:" + (path.name if re.fullmatch(r"[a-z0-9.-]{1,80}", path.name) else "unknown"))
            continue
        if path.name == "writer.lock":
            issues.append("unclean-or-active-writer")
        elif path.name.endswith(".pending"):
            issues.append("interrupted-publication")
        elif re.fullmatch(r"[0-9]{12}\.event\.json", path.name):
            event_files.append((path.name, data))
        elif path.name != "journal.json":
            issues.append("unexpected-file")
    for sequence, (name, data) in enumerate(event_files, 1):
        try:
            check(name == f"{sequence:012d}.event.json", "missing-or-reordered-event")
            event = _json(data)
            _transition(event, header, states, operations, previous, sequence)
            history.append(data)
            previous = event["event_sha256"]
        except EvidenceError as error:
            issues.append(str(error))
            break
    attempts = header["attempts"]
    return Inspection(raw, tuple(history), tuple(hashes), tuple(sorted(set(issues))),
        tuple(a["policy_attempt_id"] for a in attempts if a["policy_attempt_id"] not in states),
        tuple(a["policy_attempt_id"] for a in attempts if states.get(a["policy_attempt_id"]) == "started"),
        tuple(a["policy_attempt_id"] for a in attempts if states.get(a["policy_attempt_id"]) == "fault"))


class FixtureJournal:
    """Single-use writer. Durable start returns before future work may begin.

    No work callbacks, completion marker or reopened writable handle exist.
    Accounting is cumulative completed operations; unknown interrupted work is
    never imputed. Terminal faults stop future starts, regardless of outcome.
    """

    def __init__(self):
        raise TypeError("use-create")

    @classmethod
    def create(cls, fixture_root, directory, context, attempts, *, durability="directory-fsync", io=None):
        directory = _checked_path(fixture_root, directory)
        barrier = Durability(durability) if io is None else io
        check(type(barrier) is Durability and barrier.mode == durability, "durability-interface-required")
        header = _header(context, tuple(attempts), durability)
        raw = canonical(header)
        check(len(raw) <= MAX_HEADER, "header-size-cap")
        directory.mkdir(exist_ok=False)
        result = object.__new__(cls)
        result.directory, result.root, result.io = directory, fixture_root, barrier
        result.header, result.states, result.operations = header, {}, {}
        result.attempts = {a["policy_attempt_id"]: a for a in header["attempts"]}
        result.sequence, result.previous = 0, sha256(raw).hexdigest()
        result.last_raw = None
        result.poisoned, result.closed = True, False
        try:
            barrier.sync_directory(directory.parent)
            fd = os.open(directory / "writer.lock", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                check(barrier.write(fd, b"fixture-writer-active") == 21, "lease-write-failed")
                barrier.sync_file(fd)
            finally:
                os.close(fd)
            barrier.sync_directory(directory)
            _publish(directory, "journal.json", raw, barrier)
            result.poisoned = False
        except BaseException:
            # Partial directory/lease/header are preserved, never auto-replaced.
            raise
        return result

    def append(self, policy_attempt_id, event_type, *, operations=None, record_sha256=None, fault_code=None):
        check(not self.closed and not self.poisoned, "writer-closed-or-poisoned")
        check(_hash(policy_attempt_id), "invalid-attempt-id")
        # Constant work per append; full history checks belong to read-only passes.
        # One trusted filesystem owner is required (see module threat model).
        try:
            check(_read(self.directory / "writer.lock", MAX_EVENT) == b"fixture-writer-active", "journal-changed")
            if self.sequence:
                check(_read(self.directory / f"{self.sequence:012d}.event.json", MAX_EVENT) == self.last_raw, "journal-changed")
        except BaseException:
            self.poisoned = True
            raise
        attempt = self.attempts.get(policy_attempt_id)
        check(attempt is not None, "unknown-attempt-id")
        event = dict(schema_version=VERSION + ":event", journal_id=self.header["journal_id"], context=self.header["context"],
            sequence=self.sequence + 1, event_type=event_type, policy_attempt_id=policy_attempt_id,
            execution_index=attempt["execution_index"], binding_sha256=attempt["binding_sha256"],
            previous_event_sha256=self.previous, from_state=self.states.get(policy_attempt_id, "planned"),
            to_state=event_type, fault_code=fault_code, operations=dict(operations) if type(operations) is dict else
            dict.fromkeys(reconciliation.OPERATIONS, 0), record_sha256=record_sha256)
        check(operations is None or type(operations) is dict, "invalid-operation-fields")
        try:
            event["event_sha256"] = digest(event)
        except (TypeError, ValueError, OverflowError):
            raise EvidenceError("invalid-public-event") from None
        _transition(event, self.header, self.states, self.operations, self.previous, self.sequence + 1, apply=False)
        raw = canonical(event)
        check(len(raw) <= MAX_EVENT, "event-size-cap")
        try:
            _publish(self.directory, f"{self.sequence + 1:012d}.event.json", raw, self.io)
        except BaseException:
            self.poisoned = True
            raise
        self.states[policy_attempt_id] = event_type
        self.operations[policy_attempt_id] = event["operations"]
        self.sequence, self.previous = event["sequence"], event["event_sha256"]
        self.last_raw = raw
        return raw

    def close(self):
        if not self.closed:
            self.closed = True
            if not self.poisoned:
                try:
                    self.io.sync_directory(self.directory)
                    (self.directory / "writer.lock").unlink()
                    self.io.sync_directory(self.directory)
                except BaseException:
                    self.poisoned = True
                    raise

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        if kind is not None:
            self.poisoned = True
        self.close()


@dataclass(frozen=True)
class Checkpoint:
    checkpoint_id: str
    journal_id: str
    header_sha256: str
    event_count: int
    head_sha256: str

    def __post_init__(self):
        check(_fixture(self.checkpoint_id) and all(_hash(v) for v in
              (self.journal_id, self.header_sha256, self.head_sha256)), "invalid-checkpoint-identity")
        check(type(self.event_count) is int and 0 <= self.event_count <= 2 * MAX_ATTEMPTS, "invalid-checkpoint-count")


@dataclass(frozen=True)
class FixtureAnchor:
    """Provenance label supplied outside the journal, NOT authentication.

    A future independent custodian retains Checkpoint bytes/identity out of band.
    independent-fixture-input records that separate input path only; a caller can
    lie about this label. No identity proof, signature or institutional integration
    is implemented. This object is never loaded from journal files.
    """

    checkpoint: Checkpoint
    provenance: str

    def __post_init__(self):
        check(type(self.checkpoint) is Checkpoint and self.provenance in
              ("independent-fixture-input", "local-self-generated"), "invalid-anchor")

    @property
    def independently_authenticated(self):
        return False


def validate_checkpoint(inspection, anchor, *, checkpoint_id, require_independent_input=True):
    """Exact-head checkpoint comparison, not scientific execution verification."""
    check(type(inspection) is Inspection and type(anchor) is FixtureAnchor, "missing-external-checkpoint")
    check(_fixture(checkpoint_id) and anchor.checkpoint.checkpoint_id == checkpoint_id, "checkpoint-identity-conflict")
    check(not inspection.issues, "journal-integrity-unresolved")
    expected = inspection.local_checkpoint(checkpoint_id).checkpoint
    check(anchor.checkpoint == expected, "checkpoint-content-conflict")
    independent = anchor.provenance == "independent-fixture-input"
    check(independent or not require_independent_input, "self-generated-anchor-not-independent")
    return dict(checkpoint_id=checkpoint_id, independent_input=independent,
                independently_authenticated=False, scientific_execution_verified=False,
                power_loss_safety_established=False, inference_eligible=False)


def compare_inspections(first, second):
    """Separate read-only passes can detect removal/modification, including tail loss."""
    check(type(first) is Inspection and type(second) is Inspection and first is not second, "distinct-inspections-required")
    a, b = dict(first.file_hashes), dict(second.file_hashes)
    return dict(changed=tuple(sorted(k for k in a.keys() & b.keys() if a[k] != b[k])),
                removed=tuple(sorted(a.keys() - b.keys())), added=tuple(sorted(b.keys() - a.keys())),
                independently_authenticated=False)


@dataclass(frozen=True)
class CheckpointBoundExecution:
    """Task 7 envelope plus explicit out-of-band anchor provenance sidecar.

    Pass record to Task 7 and retain anchor separately for later reconciliation.
    Task 7's RecordedExecution alone cannot convey/authenticate this provenance.
    """

    record: reconciliation.RecordedExecution
    anchor: FixtureAnchor

    def checkpoint_metadata(self):
        return dict(checkpoint=asdict(self.anchor.checkpoint), provenance=self.anchor.provenance,
                    independently_authenticated=False, scientific_execution_verified=False)


def recorded_execution(inspection, planned, raw, anchor, *, checkpoint_id):
    """Task 7 envelope with expected hash bound to a separately supplied checkpoint.

    The raw Task 7 record stays outside this journal; its hash alone is journaled.
    Task 7 must still validate schema, actual source/decoder replay and all unmet
    prerequisites. This adapter performs no decoding and supplies no truth/result.
    """
    validate_checkpoint(inspection, anchor, checkpoint_id=checkpoint_id)
    spec = PlannedFixture.from_planned(planned)
    metadata = inspection._metadata
    check(metadata["attempts"].get(spec.policy_attempt_id) == canonical(asdict(spec))
          and planned.config_sha256 == metadata["context"].config_sha256
          and planned.plan_sha256 == metadata["context"].plan_sha256, "record-planning-conflict")
    check(type(raw) is bytes and len(raw) <= 1_048_576, "invalid-record-envelope")
    expected_hash = inspection._completed_hashes.get(spec.policy_attempt_id)
    check(expected_hash is not None, "no-completed-event")
    check(sha256(raw).hexdigest() == expected_hash, "record-content-conflict")
    return CheckpointBoundExecution(reconciliation.RecordedExecution(raw, expected_hash), anchor)


@dataclass(frozen=True)
class CustodyRequest:
    """Invocation-specific identities, never authoritative enrollment truth."""

    version: str
    context: JournalContext
    planned: PlannedFixture
    invocation_id: str

    def __post_init__(self):
        check(self.version == CUSTODY_VERSION and type(self.context) is JournalContext
              and type(self.planned) is PlannedFixture and _hash(self.invocation_id), "invalid-custody-request")


@dataclass(frozen=True, repr=False)
class InvocationRetrievalEvidence:
    """Private per-invocation result/provenance, including None=unavailable.

    The future custodian must retain the original result independently. A new
    lookup cannot substitute for this invocation's evidence. A provenance hash
    alone is not independent replay or authenticated custody.
    """

    request: CustodyRequest
    stored_record: object = field(repr=False)
    provenance_sha256: str

    def __post_init__(self):
        check(type(self.request) is CustodyRequest and _hash(self.provenance_sha256), "invalid-retrieval-evidence")

    def __repr__(self):
        return "InvocationRetrievalEvidence(<redacted; independent custody required>)"

    def __reduce_ex__(self, protocol):
        raise TypeError("private-retrieval-evidence-not-serializable")


@dataclass(frozen=True, repr=False)
class ProtectedInputs:
    """Transient custodian-owned material; MUST NOT enter public serialization.

    manufacturing_state is persistent across that device's invocations in the
    future protected store. deterministic_source_inputs carries replayable source
    inputs/provenance, not a boolean replay claim. retrieval_evidence identifies
    THIS Stored-Provisioned invocation, including unavailable/malformed results.
    Existing Task 7 ReplayInputs is the only replay projection accepted here.
    """

    request: CustodyRequest
    replay_inputs: reconciliation.ReplayInputs = field(repr=False)
    manufacturing_state: object = field(repr=False)
    deterministic_source_inputs: object = field(repr=False)
    retrieval_evidence: object = field(default=None, repr=False)

    def __repr__(self):
        return "ProtectedInputs(<redacted; protected custody unimplemented>)"

    def __reduce_ex__(self, protocol):
        raise TypeError("protected-inputs-not-serializable")


class ProtectedSourceCustodian(Protocol):
    """Separate trusted implementation, never backed by journal truth claims.

    Must bind device/reference/helper/transient truth, durable manufacturing
    state, deterministic inputs and invocation retrieval evidence to the request.
    Owns versions, access policy and independent replay provenance. Journal
    records cannot implement this authority or supply a replay verification result.
    """

    def inputs_for(self, request: CustodyRequest) -> ProtectedInputs: ...


def obtain_protected_inputs(custodian: ProtectedSourceCustodian, request, planned):
    """Validate bindings only; no source generation, storage or replay is performed."""
    check(type(request) is CustodyRequest and request.planned == PlannedFixture.from_planned(planned)
          and (request.context.config_sha256, request.context.plan_sha256) ==
          (planned.config_sha256, planned.plan_sha256), "custody-planning-conflict")
    try:
        material = custodian.inputs_for(request)
    except Exception:
        raise EvidenceError("protected-inputs-unavailable") from None
    check(type(material) is ProtectedInputs and material.request == request, "custody-identity-version-conflict")
    replay = material.replay_inputs
    check(type(replay) is reconciliation.ReplayInputs and replay.binding_sha256 == planned.digest
          and (replay.run_id, replay.source_id) == (request.context.run_id, request.context.source_id), "custody-replay-binding-conflict")
    enrollment = replay.enrollment
    check(type(enrollment) is reconciliation.EnrollmentMaterial and
          (enrollment.population_id, enrollment.device_id, enrollment.enrollment_id) ==
          (request.planned.population_id, request.planned.device_id, request.planned.enrollment_id), "custody-enrollment-conflict")
    check(material.manufacturing_state is not None and material.deterministic_source_inputs is not None,
          "missing-protected-source-inputs")
    if request.planned.policy == planning.POLICIES[2]:
        evidence = material.retrieval_evidence
        check(type(evidence) is InvocationRetrievalEvidence and evidence.request == request
              and evidence.stored_record is replay.stored_record, "missing-invocation-retrieval-evidence")
    else:
        check(material.retrieval_evidence is None and replay.stored_record is None, "unexpected-retrieval-evidence")
    return material
