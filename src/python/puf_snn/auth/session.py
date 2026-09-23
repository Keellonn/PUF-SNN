"""Wire 2.0 session primitives and isolated confirmation state.

Research credential4 has at most 32 bits of entropy; HKDF does not add entropy.
No window acceptance, replay engine, audit pipeline, or networking lives here.
"""
from dataclasses import dataclass, field
import hashlib
import hmac
import secrets
import time
from threading import RLock
from .binary_window import LP, U16, U32, U64, V, ProtocolError, Reader, identifier, raw

def hkdf_extract(salt, ikm):
    return hmac.new(raw(salt) or bytes(32), raw(ikm), hashlib.sha256).digest()

def hkdf_expand(prk, info, length):
    raw(prk)
    raw(info)
    if type(length) is not int or not 0 <= length <= 255 * 32:
        raise ProtocolError()
    previous = b""
    result = bytearray()
    for counter in range(1, (length + 31) // 32 + 1):
        previous = hmac.new(prk, previous + info + bytes([counter]), hashlib.sha256).digest()
        result += previous
    return bytes(result[:length])

@dataclass(frozen=True)
class Limits:
    handshake_timeout_ms: int = 10000
    session_ttl_ms: int = 300000
    max_windows: int = 10000

    def encode(self):
        result = U32(self.handshake_timeout_ms) + U32(self.session_ttl_ms) + U64(self.max_windows)
        if min(self.handshake_timeout_ms, self.session_ttl_ms, self.max_windows) < 1:
            raise ProtocolError()
        return result

    def __post_init__(self):
        self.encode()

@dataclass(frozen=True)
class Transcript:
    device_id: str
    client_nonce: bytes
    boot_id: bytes
    session_id: bytes
    server_nonce: bytes
    limits: Limits = Limits()

    def encode(self):
        if type(self.limits) is not Limits:
            raise ProtocolError()
        return (LP(b"PUF-SNN/L3/handshake/v2") + V(2, 0) + V(2, 0) + V(1, 0) + U16(1)
                + LP(identifier(self.device_id)) + raw(self.client_nonce, 32) + raw(self.boot_id, 16)
                + raw(self.session_id, 16) + raw(self.server_nonce, 32) + self.limits.encode())

    @classmethod
    def parse(cls, data):
        r = Reader(data)
        r.expect(LP(b"PUF-SNN/L3/handshake/v2"))
        r.expect(V(2, 0) + V(2, 0), "unsupported_protocol_version")
        r.expect(V(1, 0) + U16(1), "invalid_challenge")
        result = cls(r.id(), r.take(32), r.take(16), r.take(16), r.take(32),
                     Limits(r.integer(4), r.integer(4), r.integer(8)))
        r.done()
        return result

def derive_session_key(credential4, transcript, *, _timing_sink=None):
    raw(credential4, 4)
    t = Transcript.parse(raw(transcript))
    info = LP(b"PUF-SNN/L3/session-key/v2") + LP(transcript)
    start = time.perf_counter_ns() if _timing_sink is not None else None
    key = hkdf_expand(hkdf_extract(t.server_nonce, credential4), info, 32)
    if _timing_sink is not None:
        elapsed = time.perf_counter_ns() - start
        _timing_sink.append(elapsed)
    return key

def client_proof(key, transcript):
    Transcript.parse(transcript)
    return hmac.new(raw(key, 32), LP(b"PUF-SNN/L3/client-confirm/v2") + LP(transcript), hashlib.sha256).digest()

def server_proof(key, transcript, client):
    Transcript.parse(transcript)
    return hmac.new(raw(key, 32), LP(b"PUF-SNN/L3/server-confirm/v2") + LP(transcript)
                    + raw(client, 32), hashlib.sha256).digest()

def frame(body):
    raw(body)
    if len(body) > 4096:
        raise ProtocolError()
    return U32(len(body)) + body

def unframe(data):
    raw(data)
    if not 4 <= len(data) <= 4100:
        raise ProtocolError()
    r = Reader(data)
    size = r.integer(4)
    if size > 4096:
        raise ProtocolError()
    body = r.take(size)
    r.done()
    return Reader(body)

REFUSAL = frame(b"P3NO" + V(2, 0))

@dataclass(frozen=True)
class Failure:
    reason: str
    detail: str | None = None

@dataclass(frozen=True)
class SenderEnrollment:
    device_id: str
    enrollment_id: str
    helper_data: object
    protocol_profile: str = "puf-snn-l3-v1-wire2"

def provision_device(device_id, enrollment_id, helper_data):
    from puf_snn.reconstruction import HelperData
    identifier(device_id)
    identifier(enrollment_id)
    if type(helper_data) is not HelperData or helper_data.enrollment_id != enrollment_id:
        raise ProtocolError("internal_error")
    helper_data.validate()
    return SenderEnrollment(device_id, enrollment_id, helper_data)

@dataclass(frozen=True)
class RegistryEntry:
    device_id: str
    enrollment_id: str
    credential4: bytes = field(repr=False)
    reconstruction_id: str = "puf-snn-reconstruction-v1"
    enabled: bool = True

    def __post_init__(self):
        identifier(self.device_id)
        identifier(self.enrollment_id)
        raw(self.credential4, 4)
        if self.reconstruction_id != "puf-snn-reconstruction-v1" or type(self.enabled) is not bool:
            raise ProtocolError("internal_error")

@dataclass(frozen=True)
class SessionConfig:
    limits: Limits = Limits()
    max_pending_sessions: int = 128
    max_sessions_per_process: int = 10000

    def __post_init__(self):
        if type(self.limits) is not Limits:
            raise ProtocolError()
        self.limits.encode()
        if (type(self.max_pending_sessions) is not int or not 1 <= self.max_pending_sessions <= 10000
                or type(self.max_sessions_per_process) is not int
                or not self.max_pending_sessions <= self.max_sessions_per_process <= 1000000):
            raise ProtocolError()

@dataclass(frozen=True)
class _Pending:
    context: Transcript
    transcript: bytes
    key: bytes = field(repr=False)
    deadline: int

@dataclass(frozen=True)
class _Active:
    context: Transcript
    transcript: bytes
    key: bytes = field(repr=False)
    deadline: int
    accepted_count: int = 0
    last_accepted: int | None = None
    enrollment_id: str | None = None

@dataclass(frozen=True)
class Tombstone:
    device_id: str
    session_id: bytes
    state: str
    reason: str
    terminal_time_ns: int

class Sender:
    """One outstanding attempt. API accepts only the frozen Layer 2 result.

    Clock/random injection uses unittest.mock in explicit tests; runtime always
    calls the OS random provider. No retry or reconstruction occurs here.
    """
    def __init__(self, enrollment, limits=Limits()):
        if type(enrollment) is not SenderEnrollment or type(limits) is not Limits:
            raise ProtocolError("internal_error")
        # Revalidate trusted bindings, including material restored by a caller.
        self.enrollment = provision_device(enrollment.device_id, enrollment.enrollment_id, enrollment.helper_data)
        if enrollment.protocol_profile != self.enrollment.protocol_profile:
            raise ProtocolError("internal_error")
        self.limits = limits
        self.state = "IDLE"
        self.reason = None
        self._candidate = self._key = self._client = self._context = self._transcript = None
        self._nonce = None
        self._used_attempt_ids = set()

    def _fail(self, reason, detail=None):
        self._candidate = self._key = self._client = self._context = self._transcript = None
        self._nonce = None
        self.state, self.reason = "FAILED", reason
        return Failure(reason, detail)

    def begin_attempt(self, result, attempt_id):
        from puf_snn.reconstruction import ReconstructionResult
        if self.state == "PENDING":
            return Failure("session_busy")
        identifier(attempt_id)
        if attempt_id in self._used_attempt_ids:
            return Failure("internal_error")
        self._used_attempt_ids.add(attempt_id)
        self._candidate = self._key = self._client = self._context = self._transcript = None
        self.attempt_id = attempt_id
        if type(result) is not ReconstructionResult or type(result.reported_correction_count) is not int:
            return self._fail("internal_error")
        message = result.candidate_message
        valid_message = (type(message) is tuple and len(message) == 36
                         and all(type(bit) is int and bit in (0, 1) for bit in message))
        if result.outcome == "decoder_failure":
            if (result.decoder_status != "uncorrectable" or result.reported_correction_count != -1
                    or message is not None or result.candidate_credential is not None
                    or result.padding_valid is not None or result.failure_reason != "decoder_declared_failure"):
                return self._fail("internal_error")
            return self._fail("failed_reconstruction", result.outcome)
        if result.decoder_status != "decoded" or not 0 <= result.reported_correction_count <= 5 or not valid_message:
            return self._fail("internal_error")
        if result.outcome == "invalid_format_or_padding":
            if (result.candidate_credential is not None or result.padding_valid is not False
                    or message[-4:] == (0,)*4 or result.failure_reason != "nonzero_padding"):
                return self._fail("internal_error")
            return self._fail("failed_reconstruction", result.outcome)
        if (result.outcome != "candidate_valid_format" or result.padding_valid is not True
                or result.failure_reason is not None or message[-4:] != (0,)*4
                or type(result.candidate_credential) is not bytes or len(result.candidate_credential) != 4):
            return self._fail("internal_error")
        bits = tuple((byte >> shift) & 1 for byte in result.candidate_credential for shift in range(7, -1, -1))
        if bits != message[:32]:
            return self._fail("internal_error")
        self._start = time.monotonic_ns()
        self._deadline = self._start + self.limits.handshake_timeout_ms * 1_000_000
        try:
            self._nonce = raw(secrets.token_bytes(32), 32)
        except Exception:
            return self._fail("internal_error")
        self._candidate = result.candidate_credential
        self.state, self.reason = "PENDING", None
        return frame(b"P3RQ" + V(2, 0) + LP(identifier(self.enrollment.device_id)) + self._nonce)

    def _ready(self):
        if self.state != "PENDING":
            return Failure("inactive_session")
        if time.monotonic_ns() >= self._deadline:
            return self._fail("handshake_timeout")
        return None

    def _derive_key(self, credential4, transcript):
        return derive_session_key(credential4, transcript)

    def answer_challenge(self, data):
        failed = self._ready()
        if failed:
            return failed
        if data == REFUSAL:
            return self._fail("session_refused")
        if self._candidate is None:
            return self._fail("invalid_challenge")
        try:
            r = unframe(data)
            r.expect(b"P3CH")
            transcript = r.lp()
            r.done()
            context = Transcript.parse(transcript)
            if (context.device_id != self.enrollment.device_id or context.client_nonce != self._nonce
                    or context.limits != self.limits):
                raise ProtocolError("invalid_challenge")
            key = self._derive_key(self._candidate, transcript)
            proof = client_proof(key, transcript)
        except ProtocolError as error:
            return self._fail(error.reason)
        except Exception:
            return self._fail("internal_error")
        self._candidate = None
        self._context, self._transcript, self._key, self._client = context, transcript, key, proof
        return frame(b"P3CF" + V(2, 0) + context.session_id + proof)

    def finish_session(self, data):
        failed = self._ready()
        if failed:
            return failed
        if data == REFUSAL:
            return self._fail("session_refused")
        if self._context is None:
            return self._fail("invalid_challenge")
        try:
            sid, proof = _parse_confirmation(data, b"P3OK")
            if sid != self._context.session_id:
                raise ProtocolError("invalid_challenge")
            expected = server_proof(self._key, self._transcript, self._client)
            if not hmac.compare_digest(expected, proof):
                raise ProtocolError("key_confirmation_failed")
            if time.monotonic_ns() >= self._start + self.limits.session_ttl_ms * 1_000_000:
                raise ProtocolError("expired_session")
        except ProtocolError as error:
            return self._fail(error.reason)
        except Exception:
            return self._fail("internal_error")
        self._client = None
        self.state, self.reason = "ACTIVE", "accepted"
        return self

def _parse_confirmation(data, magic):
    r = unframe(data)
    r.expect(magic)
    r.expect(V(2, 0), "unsupported_protocol_version")
    sid, proof = r.take(16), r.take(32)
    r.done()
    return sid, proof

class Verifier:
    """Minimal handshake owner. Serial decisions; no verify_window API.

    last_reason and tombstones support local tests, not a full operational audit.
    Pending entries contain no sequence fields. No public method accepts a key.
    """
    def __init__(self, entries, config=SessionConfig()):
        if type(config) is not SessionConfig:
            raise ProtocolError()
        self._registry = {}
        for entry in entries:
            if type(entry) is not RegistryEntry or entry.device_id in self._registry:
                raise ProtocolError("internal_error")
            entry.__post_init__()
            self._registry[entry.device_id] = entry
        self.config = config
        try:
            self.boot_id = raw(secrets.token_bytes(16), 16)
        except Exception:
            raise ProtocolError("internal_error") from None
        self._pending, self._active, self._terminal = {}, {}, {}
        self._issued = set()
        self._lock = RLock()
        self.last_reason = None

    @property
    def active_session_ids(self):
        with self._lock:
            return tuple(active.context.session_id for active in self._active.values())

    @property
    def tombstones(self):
        with self._lock:
            return tuple(self._terminal.values())

    def _refuse(self, reason):
        self.last_reason = reason
        return REFUSAL

    def _derive_key(self, credential4, transcript):
        return derive_session_key(credential4, transcript)

    # Agent 3 extension boundary. All callers hold this owner's decision lock.
    # Snapshot/copy first, then publish by reference assignment; no secret state
    # is exposed by the public Layer 3 API.
    def _window_lookup(self, device, sid):
        entry = self._registry.get(device)
        active = next((a for a in self._active.values() if a.context.session_id == sid), None)
        terminal = self._terminal.get(sid)
        state = ("ACTIVE" if active else "PENDING" if sid in self._pending
                 else terminal.state if terminal else None)
        return entry, active, state

    def _prepare_window_state(self, active, replacement=None, terminal=None):
        active_map, terminal_map = self._active.copy(), self._terminal.copy()
        if replacement is not None:
            active_map[active.context.device_id] = replacement
        if terminal is not None:
            del active_map[active.context.device_id]
            terminal_map[terminal.session_id] = terminal
        return active_map, terminal_map

    def _publish_window_state(self, prepared):
        self._active, self._terminal = prepared

    def _active_snapshot(self):
        return tuple(self._active.values())

    def _before_activation_commit(self, active, old, now):
        """Optional in-memory audit reservation/commit; no I/O in this hook."""

    def _before_pending_terminal(self, pending, reason, now):
        """Optional terminal-attempt audit hook, before secret-state removal."""

    def _terminate_pending(self, sid, reason, now):
        pending = self._pending[sid]
        pending_map, terminal_map = self._pending.copy(), self._terminal.copy()
        del pending_map[sid]
        terminal_map[sid] = Tombstone(pending.context.device_id, sid, "FAILED", reason, now)
        self._before_pending_terminal(pending, reason, now)
        self._pending, self._terminal = pending_map, terminal_map

    def expire_pending(self):
        with self._lock:
            now = time.monotonic_ns()
            for sid, pending in tuple(self._pending.items()):
                if now >= pending.deadline:
                    self._terminate_pending(sid, "handshake_timeout", now)

    def begin_session(self, request, local_provenance=None):
        with self._lock:
            now = time.monotonic_ns()
            try:
                r = unframe(request)
                r.expect(b"P3RQ")
                version = r.take(4)
                device, nonce = r.id(), r.take(32)
                r.done()
                if version != V(2, 0):
                    raise ProtocolError("unsupported_protocol_version")
                entry = self._registry.get(device)
                if entry is None or not entry.enabled:
                    raise ProtocolError("unknown_device")
                if any(p.context.device_id == device for p in self._pending.values()):
                    raise ProtocolError("session_busy")
                if (len(self._pending) >= self.config.max_pending_sessions
                        or len(self._issued) >= self.config.max_sessions_per_process):
                    raise ProtocolError("resource_limit")
                sid = raw(secrets.token_bytes(16), 16)
                while sid in self._issued:
                    sid = raw(secrets.token_bytes(16), 16)
                server_nonce = raw(secrets.token_bytes(32), 32)
                context = Transcript(device, nonce, self.boot_id, sid, server_nonce, self.config.limits)
                transcript = context.encode()
                key = self._derive_key(entry.credential4, transcript)
                challenge = frame(b"P3CH" + LP(transcript))
                self._pending[sid] = _Pending(context, transcript, key, now + self.config.limits.handshake_timeout_ms * 1_000_000)
                self._issued.add(sid)
                self.last_reason = None
                return challenge
            except ProtocolError as error:
                return self._refuse(error.reason)
            except Exception:
                return self._refuse("internal_error")

    def confirm_session(self, confirmation):
        with self._lock:
            now = time.monotonic_ns()
            try:
                sid, proof = _parse_confirmation(confirmation, b"P3CF")
            except ProtocolError as error:
                return self._refuse(error.reason)
            pending = self._pending.get(sid)
            if pending is None:
                return self._refuse("inactive_session" if sid in self._issued else "unknown_session")
            if now >= pending.deadline:
                self._terminate_pending(sid, "handshake_timeout", now)
                return self._refuse("handshake_timeout")
            expected = client_proof(pending.key, pending.transcript)
            if not hmac.compare_digest(expected, proof):
                self._terminate_pending(sid, "key_confirmation_failed", now)
                return self._refuse("key_confirmation_failed")
            response = frame(b"P3OK" + V(2, 0) + sid + server_proof(pending.key, pending.transcript, proof))
            device = pending.context.device_id
            old = self._active.get(device)
            active_map, terminal_map, pending_map = self._active.copy(), self._terminal.copy(), self._pending.copy()
            if old is not None:
                old_sid = old.context.session_id
                terminal_map[old_sid] = Tombstone(device, old_sid, "CLOSED", "session_replaced", now)
            active = _Active(pending.context, pending.transcript, pending.key,
                             now + pending.context.limits.session_ttl_ms * 1_000_000,
                             enrollment_id=self._registry[device].enrollment_id)
            active_map[device] = active
            del pending_map[sid]
            self._before_activation_commit(active, old, now)
            self._active, self._terminal, self._pending = active_map, terminal_map, pending_map
            self.last_reason = "accepted"
            return response

def provision_verifier(registry_entries, config=SessionConfig()):
    return Verifier(registry_entries, config)