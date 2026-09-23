"""Stateful wire-2 verifier. The inherited Agent 2 owner alone runs handshake.

One owner/registry/lock covers replacement, window decisions and lifecycle.
Private copy-on-commit maps/audit tuples reserve all allocating work before the
reference assignments that publish a decision. Persistent I/O is never here.
"""
from dataclasses import asdict, dataclass, replace
import hashlib
import hmac
import time
from .audit import AuditRecorder, Provenance, provenance
from .binary_window import ProtocolError, Window, parse_envelope, raw, validate_quality, window_tag
from .session import REFUSAL, SessionConfig, Tombstone, Verifier as SessionVerifier, derive_session_key

@dataclass(frozen=True)
class VerificationResult:
    result: str
    reason: str
    device_id: str | None = None
    session_id: str | None = None
    window_id: str | None = None
    sequence_number: int | None = None
    authenticated_bytes_sha256: str | None = None
    accepted_window: Window | None = None
    authenticated_bytes: bytes | None = None
    verifier_auth_ns: int | None = None
    provenance: Provenance = Provenance()
    event_id: str | None = None

@dataclass(frozen=True)
class ControlResult:
    session_id: str
    state: str
    reason: str
    event_id: str

@dataclass(frozen=True)
class SessionStatus:
    session_id: str
    state: str | None
    accepted_count: int | None
    last_accepted: int | None
    deadline_ns: int | None

class Verifier(SessionVerifier):
    def __init__(self, entries, config=SessionConfig()):
        super().__init__(entries, config)
        self._audit = AuditRecorder(self.boot_id)
        self._emergency_result = VerificationResult("reject", "internal_error")
        self._attempt_provenance = {}
        self._accepted_results = {}
        self._kdf_timings = []
        self._attempt_kdf = {}

    @property
    def kdf_timings_ns(self):
        with self._lock:
            return tuple(self._kdf_timings)

    def _derive_key(self, credential4, transcript):
        return derive_session_key(credential4, transcript, _timing_sink=self._kdf_timings)

    @property
    def audit_records(self):
        with self._lock:
            return self._audit.records

    @property
    def incomplete(self):
        return self._audit.incomplete

    def session_status(self, session_id):
        raw(session_id, 16)
        with self._lock:
            _, active, state = self._window_lookup(None, session_id)
            return SessionStatus(session_id.hex(), state, active.accepted_count if active else None,
                                 active.last_accepted if active else None, active.deadline if active else None)

    def _ensure_running(self):
        if self.incomplete:
            raise RuntimeError("verifier stopped: incomplete evidence")

    def begin_session(self, request, local_provenance=None):
        with self._lock:
            self._ensure_running()
            try:
                local = provenance(local_provenance)
                response = super().begin_session(request, local)
                if response == REFUSAL:
                    self._append_session_rejection("session_establishment", self.last_reason, local)
                else:
                    # Challenge carries public T; no duplicate handshake logic.
                    from .session import Transcript, unframe
                    reader = unframe(response)
                    reader.expect(b"P3CH")
                    sid = Transcript.parse(reader.lp()).session_id
                    self._attempt_provenance[sid] = local
                    self._attempt_kdf[sid] = self._kdf_timings[-1]
                return response
            except Exception:
                self._audit.emergency(event_type="session_establishment")
                return self._refuse("internal_error")

    def confirm_session(self, confirmation):
        with self._lock:
            self._ensure_running()
            ordinal = self._audit._ordinal
            try:
                response = super().confirm_session(confirmation)
                if response == REFUSAL and ordinal == self._audit._ordinal:
                    self._append_session_rejection("session_message", self.last_reason, Provenance())
                return response
            except Exception:
                self._audit.emergency(event_type="session_message")
                return self._refuse("internal_error")

    def _append_session_rejection(self, event_type, reason, local):
        row = self._audit.record(event_type=event_type, reason=reason, provenance=asdict(local))
        self._audit.commit(self._audit.prepare([row]))
        if reason == "internal_error":
            self._audit.incomplete = True

    def _attempt_record(self, session, **values):
        sid = session.context.session_id
        row = self._audit.record(event_type="session_establishment", attempt_id=sid.hex(),
                                  device_id=session.context.device_id, session_id=sid.hex(),
                                  observed_protocol_version="2.0", state_before="PENDING",
                                  provenance=asdict(self._attempt_provenance.get(sid, Provenance())), **values)
        row["latency_ns"]["kdf"] = self._attempt_kdf.get(sid)
        return row

    def _before_pending_terminal(self, pending, reason, now):
        row = self._attempt_record(pending, state_after="FAILED", reason=reason,
                                   authentication_result="fail" if reason == "key_confirmation_failed" else "not_checked",
                                   recorded_monotonic_ns=now)
        self._audit.commit(self._audit.prepare([row]))

    def expire_pending(self):
        with self._lock:
            self._ensure_running()
            try:
                return super().expire_pending()
            except Exception:
                self._audit.emergency(event_type="session_establishment")
                raise ProtocolError("internal_error") from None

    def _control_record(self, active, reason, now):
        state = "EXPIRED" if reason == "expired_session" else "CLOSED"
        return self._audit.record(event_type="session_control", decision="closed", reason=reason,
                                  attempt_id=active.context.session_id.hex(),
                                  device_id=active.context.device_id,
                                  session_id=active.context.session_id.hex(),
                                  state_before="ACTIVE", state_after=state,
                                  provenance=asdict(self._attempt_provenance.get(active.context.session_id, Provenance())),
                                  recorded_monotonic_ns=now)

    def _before_activation_commit(self, active, old, now):
        # Replacement is authenticated by the unchanged Agent 2 proof decision.
        rows = []
        if old is not None:
            rows.append(self._control_record(old, "session_replaced", now))
        rows.append(self._attempt_record(active, decision="accept", reason="accepted", state_after="ACTIVE",
                                         authentication_result="pass", identity_authenticated=True,
                                         recorded_monotonic_ns=now))
        self._audit.commit(self._audit.prepare(rows))

    def verify_window(self, envelope_bytes: bytes, local_provenance: Provenance | None = None) -> VerificationResult:
        start = time.perf_counter_ns()  # includes mutex wait
        with self._lock:
            self._ensure_running()
            now = time.monotonic_ns()
            row = None
            committed = False
            failure_detail = "backend_exception"
            try:
                local = provenance(local_provenance)
                row = self._audit.record(recorded_monotonic_ns=now, provenance=asdict(local))
                active = envelope = None
                try:
                    envelope = parse_envelope(envelope_bytes)
                    window = envelope.window
                    row.update(device_id=window.device_id, session_id=window.session_id.hex(),
                               window_id=window.window_id, sequence_number=window.sequence_number,
                               observed_protocol_version="2.0")
                    entry, active, state = self._window_lookup(window.device_id, window.session_id)
                    if entry is None or not entry.enabled:
                        raise ProtocolError("unknown_device")
                    row.update(state_before=state, state_after=state)
                    if state is None:
                        raise ProtocolError("unknown_session")
                    if state == "EXPIRED":
                        raise ProtocolError("expired_session")
                    if state != "ACTIVE":
                        raise ProtocolError("inactive_session")
                    if now >= active.deadline:
                        raise ProtocolError("expired_session")
                    if active.accepted_count >= active.context.limits.max_windows:
                        raise ProtocolError("session_limit_reached")
                    if not hmac.compare_digest(window_tag(active.key, envelope.authenticated_bytes), envelope.tag):
                        row["authentication_result"] = "fail"
                        raise ProtocolError("invalid_tag")
                    row.update(authentication_result="pass",
                               authenticated_bytes_sha256=hashlib.sha256(envelope.authenticated_bytes).hexdigest())
                    if (entry.device_id != active.context.device_id
                            or entry.enrollment_id != active.enrollment_id or not entry.enabled):
                        raise ProtocolError("device_session_mismatch")
                    envelope.check_key_id()
                    row["identity_authenticated"] = True
                    row["attempt_id"] = active.context.session_id.hex()
                    count, last = active.accepted_count, active.last_accepted
                    if ((count == 0 and last is not None) or (count > 0 and last != count - 1)
                            or type(count) is not int or count < 0):
                        failure_detail = "invariant_failure"
                        raise RuntimeError("invariant_failure")
                    row.update(last_accepted_before=last, last_accepted_after=last,
                               expected_sequence=count)
                    validate_quality(window)
                    seq = window.sequence_number
                    if last is not None and seq == last:
                        row["order_result"] = "duplicate"
                        raise ProtocolError("duplicate_sequence")
                    if last is not None and seq < last:
                        row["order_result"] = "stale"
                        raise ProtocolError("stale_sequence")
                    if seq > count:
                        row.update(order_result="gap", missing_start=count, missing_end=seq-1,
                                   missing_count=seq-count)
                        raise ProtocolError("future_sequence_gap")
                    row["order_result"] = "pass"
                    if time.monotonic_ns() >= active.deadline:
                        raise ProtocolError("expired_session")
                    row.update(decision="accept", reason="accepted", last_accepted_after=seq)
                except ProtocolError as error:
                    row["reason"] = error.reason

                accepted = row["decision"] == "accept"
                rows = [row]
                prepared_state = None
                if accepted:
                    updated = replace(active, accepted_count=active.accepted_count + 1,
                                      last_accepted=envelope.window.sequence_number)
                    terminal = None
                    if updated.accepted_count == active.context.limits.max_windows:
                        terminal = Tombstone(active.context.device_id, active.context.session_id,
                                             "CLOSED", "session_limit_reached", time.monotonic_ns())
                        rows.append(self._control_record(updated, terminal.reason, terminal.terminal_time_ns))
                    prepared_state = self._prepare_window_state(active, updated, terminal)
                failure_detail = "audit_unavailable"
                prepared_audit = self._audit.prepare(rows)
                # Failure identities stay audit-only; successful identities are trusted.
                result = VerificationResult(
                    row["decision"], row["reason"],
                    row["device_id"] if accepted else None, row["session_id"] if accepted else None,
                    row["window_id"] if accepted else None, row["sequence_number"] if accepted else None,
                    row["authenticated_bytes_sha256"], envelope.window if accepted else None,
                    envelope.authenticated_bytes if accepted else None, provenance=local, event_id=row["event_id"])
                prepared_results = None
                if accepted:
                    prepared_results = self._accepted_results.copy()
                    prepared_results[result.event_id] = result
                # Allocation can itself take time. Recheck immediately before
                # publication, after reserving the result and audit capacity.
                if accepted and time.monotonic_ns() >= active.deadline:
                    row.update(decision="reject", reason="expired_session",
                               last_accepted_after=active.last_accepted)
                    prepared_state = None
                    prepared_results = None
                    prepared_audit = self._audit.prepare([row])
                    result = VerificationResult("reject", "expired_session",
                                                authenticated_bytes_sha256=row["authenticated_bytes_sha256"],
                                                provenance=local, event_id=row["event_id"])
                # All allocating work is done. Publish under the same mutex.
                self._audit.commit(prepared_audit)
                if prepared_state is not None:
                    self._publish_window_state(prepared_state)
                if prepared_results is not None:
                    self._accepted_results = prepared_results
                committed = True
                elapsed = time.perf_counter_ns() - start
                row["latency_ns"]["verifier_auth"] = elapsed
                object.__setattr__(result, "verifier_auth_ns", elapsed)
                return result
            except Exception:
                if committed:
                    self._audit.incomplete = True
                    raise RuntimeError("post-commit failure: incomplete evidence") from None
                emergency = self._audit.emergency(failure_detail)
                elapsed = time.perf_counter_ns() - start
                emergency["latency_ns"]["verifier_auth"] = elapsed
                object.__setattr__(self._emergency_result, "verifier_auth_ns", elapsed)
                object.__setattr__(self._emergency_result, "event_id", emergency["event_id"])
                return self._emergency_result

    def _close_active(self, active, reason, now):
        row = self._control_record(active, reason, now)
        terminal = Tombstone(active.context.device_id, active.context.session_id, row["state_after"], reason, now)
        prepared_state = self._prepare_window_state(active, terminal=terminal)
        prepared_audit = self._audit.prepare([row])
        result = ControlResult(terminal.session_id.hex(), terminal.state, reason, row["event_id"])
        self._audit.commit(prepared_audit)
        self._publish_window_state(prepared_state)
        return result

    def close_session(self, session_id: bytes, trusted_local_reason="session_closed") -> ControlResult | None:
        raw(session_id, 16)
        if trusted_local_reason != "session_closed":
            raise ValueError("local close reason must be session_closed")
        with self._lock:
            self._ensure_running()
            _, active, _ = self._window_lookup(None, session_id)
            if active is None:
                return None
            try:
                return self._close_active(active, trusted_local_reason, time.monotonic_ns())
            except Exception:
                self._audit.emergency(event_type="session_control")
                raise ProtocolError("internal_error") from None

    def expire_due_sessions(self) -> list[ControlResult]:
        with self._lock:
            self._ensure_running()
            now = time.monotonic_ns()
            try:
                return [self._close_active(active, "expired_session", now)
                        for active in self._active_snapshot() if now >= active.deadline]
            except Exception:
                self._audit.emergency(event_type="session_control")
                raise ProtocolError("internal_error") from None

    def close_all_sessions(self) -> list[ControlResult]:
        """Trusted orderly shutdown: finalize ACTIVE and admitted PENDING work.

        Terminal tombstones and issued IDs survive; this API never processes a
        remote packet and never resets replay state for reuse.
        """
        with self._lock:
            self._ensure_running()
            now = time.monotonic_ns()
            try:
                closed = [self._close_active(active, "session_closed", now)
                          for active in self._active_snapshot()]
                for sid in tuple(self._pending):
                    self._terminate_pending(sid, "session_closed", now)
                return closed
            except Exception:
                self._audit.emergency(event_type="session_control")
                raise ProtocolError("internal_error") from None

    def flush_audit(self, writer):
        # Snapshot only under the decision mutex. Never hold it during disk I/O:
        # a concurrent verifier's lock-wait timing must not include that I/O.
        with self._lock:
            records = self._audit.records
        try:
            writer.flush(records)
        except Exception:
            with self._lock:
                self._audit.incomplete = True
            raise

    def release_accepted(self, result, consumer):
        """Trusted local inference boundary; never takes a second payload/IDs.

        Require the exact object minted at commit, so even caller-controlled
        equality methods or a copied dataclass cannot substitute a payload.
        Python process-memory compromise remains outside this boundary.
        """
        with self._lock:
            self._ensure_running()
            if type(result) is not VerificationResult or result.result != "accept" or result.reason != "accepted":
                raise ValueError("verifier acceptance required")
            if self._accepted_results.get(result.event_id) is not result:
                raise ValueError("result is not bound to a committed acceptance")
        try:
            return consumer(result.accepted_window)
        except Exception:
            with self._lock:
                self._audit.incomplete = True
                try:
                    row = self._audit.record(event_type="session_control", reason="internal_error",
                                             detail="backend_exception", device_id=result.device_id,
                                             session_id=result.session_id)
                    self._audit.commit(self._audit.prepare([row]))
                except Exception:
                    self._audit.emergency(event_type="session_control")
            raise RuntimeError("consumer failure: incomplete evidence") from None


def provision_verifier(registry_entries, config=SessionConfig()):
    return Verifier(registry_entries, config)