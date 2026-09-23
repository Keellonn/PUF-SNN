"""Window sealing extension of the frozen Agent 2 handshake sender."""
from dataclasses import asdict, dataclass, replace
import base64
import json
import secrets
from threading import RLock
import time

from .audit import AuditRecorder, Provenance, provenance
from .binary_window import ProtocolError, Window, encode_window, identifier, raw, window_tag
from .session import Failure, Sender as SessionSender, derive_session_key


@dataclass(frozen=True)
class SenderTiming:
    sender_prepare_ns: int
    sender_hmac_ns: int | None
    result: str
    reason: str


class Sender(SessionSender):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._seal_lock = RLock()
        self.next_to_send = 0
        self.last_window_timing = None
        self._kdf_timings = []
        try:
            self._audit = AuditRecorder(raw(secrets.token_bytes(16), 16), origin="sender")
        except Exception:
            raise ProtocolError("internal_error") from None
        self._local_provenance = Provenance()
        self._establishment_start = None
        self._attempt_kdf_start = 0

    @property
    def audit_records(self):
        with self._seal_lock:
            return self._audit.records

    @property
    def incomplete(self):
        return self._audit.incomplete

    def _ensure_running(self):
        if self.incomplete:
            raise RuntimeError("sender stopped: incomplete evidence")

    def _record(self, event_type, **values):
        state = self.state if self.state != "IDLE" else None
        defaults = dict(event_type=event_type, attempt_id=getattr(self, "attempt_id", None),
                        device_id=self.enrollment.device_id,
                        session_id=self._context.session_id.hex() if self._context else None,
                        state_before=state, state_after=state,
                        provenance=asdict(self._local_provenance))
        defaults.update(values)
        return self._audit.record(**defaults)

    def _append(self, rows):
        self._audit.commit(self._audit.prepare(rows))

    def _audit_failure(self, event_type, detail="audit_unavailable"):
        self._audit.emergency(detail, event_type)
        return self._fail("internal_error")

    def begin_attempt(self, result, attempt_id, *, local_provenance=None, reconstruction_ns=None):
        """Observe one scheduled result; never reconstruct, compare or retry.

        A reconstruction accept means admission to a handshake only. It has no
        authenticated identity, proof result, payload hash or replay state.
        """
        return self._begin_attempt(result, attempt_id, local_provenance, reconstruction_ns, "invariant_failure")

    def _begin_attempt(self, result, attempt_id, local_provenance, reconstruction_ns, error_detail):
        with self._seal_lock:
            self._ensure_running()
            identifier(attempt_id)
            local = provenance(local_provenance)
            if reconstruction_ns is not None and (type(reconstruction_ns) is not int or reconstruction_ns < 0):
                raise ValueError("reconstruction timing requires nonnegative integer nanoseconds")
            before = self.state if self.state != "IDLE" else None
            busy = self.state == "PENDING"
            try:
                if not busy:
                    self._local_provenance = local
                    self._attempt_kdf_start = len(self._kdf_timings)
                start = time.perf_counter_ns()
                response = super().begin_attempt(result, attempt_id)
                failed = isinstance(response, Failure)
                if failed and response.reason == "internal_error":
                    self._fail("internal_error")
                row = self._record("session_message" if busy else "reconstruction",
                                   attempt_id=attempt_id, provenance=asdict(local),
                                   state_before=before, decision="reject" if failed else "accept",
                                   reason=response.reason if failed else "accepted",
                                   detail=(response.detail or (error_detail if response.reason == "internal_error" else None)) if failed else None)
                row["latency_ns"]["reconstruction"] = reconstruction_ns if not busy else None
                self._append([row])
                if not failed:
                    self._establishment_start = start
                elif response.reason == "internal_error":
                    self._audit.incomplete = True
                return response
            except Exception:
                return self._audit_failure("reconstruction")

    def record_reconstruction_exception(self, attempt_id, *, local_provenance=None, reconstruction_ns=None):
        """Trusted harness reports a reconstruct() exception without its contents.

        No retry, ordinary FRR label, exception string or secret input is stored.
        """
        return self._begin_attempt(None, attempt_id, local_provenance, reconstruction_ns, "backend_exception")

    def _response(self, operation, data):
        with self._seal_lock:
            self._ensure_running()
            before = self.state if self.state != "IDLE" else None
            sid = self._context.session_id.hex() if self._context else None
            try:
                result = operation(data)
                failed = isinstance(result, Failure)
                terminal = before == "PENDING" and self.state != "PENDING"
                if terminal or failed:
                    row = self._record("session_establishment" if terminal else "session_message",
                                       state_before=before, session_id=(self._context.session_id.hex() if self._context else sid),
                                       decision="reject" if failed else "accept",
                                       reason=result.reason if failed else "accepted",
                                       detail="backend_exception" if failed and result.reason == "internal_error" else None,
                                       identity_authenticated=not failed,
                                       authentication_result=("fail" if failed and result.reason == "key_confirmation_failed"
                                                              else "not_checked" if failed else "pass"),
                                       observed_protocol_version="2.0" if not failed else None)
                    if terminal and len(self._kdf_timings) > self._attempt_kdf_start:
                        row["latency_ns"]["kdf"] = self._kdf_timings[-1]
                    self._append([row])
                    if terminal and self._establishment_start is not None:
                        row["latency_ns"]["session_establishment"] = time.perf_counter_ns() - self._establishment_start
                        self._establishment_start = None
                    if failed and result.reason == "internal_error":
                        self._audit.incomplete = True
                return result
            except Exception:
                return self._audit_failure("session_establishment")

    def answer_challenge(self, data):
        return self._response(super().answer_challenge, data)

    def flush_audit(self, writer):
        with self._seal_lock:
            records = self._audit.records
        try:
            writer.flush(records)
        except Exception:
            with self._seal_lock:
                self._audit.incomplete = True
                self._fail("internal_error")
            raise

    @property
    def kdf_timings_ns(self):
        return tuple(self._kdf_timings)

    def _derive_key(self, credential4, transcript):
        return derive_session_key(credential4, transcript, _timing_sink=self._kdf_timings)

    def finish_session(self, data):
        with self._seal_lock:
            result = self._response(super().finish_session, data)
            if result is self:
                self.next_to_send = 0
            return result

    @property
    def session_id(self):
        return self._context.session_id if self.state == "ACTIVE" else None

    def _window_record(self, processed_window, local, before, sequence):
        timing = self.last_window_timing
        row = self._record("sender_window", provenance=asdict(local), state_before=before,
                           sequence_number=sequence if type(sequence) is int and 0 <= sequence < 2**64 else None,
                           decision=timing.result, reason=timing.reason)
        if type(processed_window) is Window:
            try:
                identifier(processed_window.window_id)
                row["window_id"] = processed_window.window_id
            except ProtocolError:
                pass
        row["latency_ns"].update(sender_prepare=timing.sender_prepare_ns, sender_hmac=timing.sender_hmac_ns)
        return row

    def seal_window(self, processed_window: Window, *, local_provenance=None) -> bytes | Failure:
        start = time.perf_counter_ns()
        hmac_ns = None
        with self._seal_lock:
            self._ensure_running()
            local = provenance(local_provenance) if local_provenance is not None else self._local_provenance
            before = self.state if self.state != "IDLE" else None
            sequence = self.next_to_send if self.state == "ACTIVE" else None
            failure_detail = "backend_exception"
            try:
                if self.state != "ACTIVE":
                    raise ProtocolError("inactive_session")
                if time.monotonic_ns() >= self._start + self.limits.session_ttl_ms * 1_000_000:
                    self._key = None
                    self.state = "CLOSED"
                    raise ProtocolError("expired_session")
                if self.next_to_send >= self.limits.max_windows:
                    self._key = None
                    self.state = "CLOSED"
                    raise ProtocolError("session_limit_reached")
                if type(processed_window) is not Window:
                    raise ProtocolError("invalid_payload_schema")
                window = replace(processed_window, device_id=self.enrollment.device_id,
                                 session_id=self._context.session_id, sequence_number=self.next_to_send)
                data = encode_window(window)
                hmac_start = time.perf_counter_ns()
                tag = window_tag(self._key, data)
                hmac_ns = time.perf_counter_ns() - hmac_start
                envelope = json.dumps({
                    "protected": {"encoding": "puf-snn-binary32-be-v2", "bytes_b64": base64.b64encode(data).decode("ascii")},
                    "authentication": {"algorithm": "HMAC-SHA-256", "key_id": self._context.session_id.hex(),
                                       "tag_hex": tag.hex()}}, separators=(",", ":")).encode("utf-8")
                self.next_to_send += 1
                if self.next_to_send == self.limits.max_windows:
                    self._key = None
                    self.state = "CLOSED"
                self.last_window_timing = SenderTiming(time.perf_counter_ns()-start, hmac_ns, "accept", "accepted")
                # Tag creation is not tag verification. No verifier acceptance,
                # authenticated identity/hash or replay fields are asserted here.
                failure_detail = "audit_unavailable"
                row = self._window_record(processed_window, local, before, sequence)
                rows = [row]
                if self.state == "CLOSED":
                    rows.append(self._record("session_control", decision="closed", reason="session_limit_reached",
                                             state_before="ACTIVE"))
                self._append(rows)
                return envelope
            except ProtocolError as error:
                self.last_window_timing = SenderTiming(time.perf_counter_ns()-start, hmac_ns, "reject", error.reason)
                try:
                    row = self._window_record(processed_window, local, before, sequence)
                    self._append([row])
                except Exception:
                    return self._audit_failure("sender_window")
                return Failure(error.reason)
            except Exception:
                # If sealing consumed a sequence, never roll it back on audit
                # failure. Stop this sender; no unaudited envelope is returned.
                return self._audit_failure("sender_window", failure_detail)
