"""Standalone enrollment credential comparison for the trusted software pilot.

No reconstruction, HKDF, networking, or persistence; handles are local only.
The 32-bit credential is research material, not production-strength entropy.
Private attributes and repr redaction do not isolate secrets from this process;
Python bytes are not securely erased. Never log provisioning inputs or records
via generic dataclass serialization (which includes the enrollment tag).
"""

from dataclasses import dataclass, field
import hashlib
import hmac
import re
import secrets
import time
from threading import RLock
from types import MappingProxyType
from typing import Iterable, Literal, Protocol


_DOMAIN = b"PUF-SNN/credential-verifier/v1"
_SCHEMA = "puf-snn-credential-verifier-v1"
_ALGORITHM = "HMAC-SHA-256"
_OUTCOMES = frozenset({
    "verified", "credential_mismatch", "record_missing", "record_disabled",
    "unsupported_record", "key_unavailable", "binding_mismatch",
    "invalid_input", "internal_error",
})


def _identifier(value: str) -> bytes:
    if (type(value) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value) is None):
        raise ValueError("invalid_input")
    return value.encode("ascii")


def _credential(value: bytes) -> None:
    if type(value) is not bytes or len(value) != 4:
        raise ValueError("invalid_input")


def _message(device_id, enrollment_id, reconstruction_id, verifier_key_id, credential4):
    _credential(credential4)
    parts = (_DOMAIN, *(_identifier(value) for value in (
        device_id, enrollment_id, reconstruction_id, verifier_key_id,
    )))
    return b"".join(len(part).to_bytes(2, "big") + part for part in parts) + credential4


class CredentialVerifierKeyProvider(Protocol):
    """Trusted key access only; callers must never log the returned key.

    Return exactly 32 bytes or raise on unavailable/unknown key IDs. This is
    not a public network API. Implementations must redact their representations.
    """

    def get_key(self, verifier_key_id: str) -> bytes: ...


class InMemoryCredentialVerifierKeyProvider:
    """One independently provisioned service key; no fallback or persistence.

    Use generate() for runtime/evaluation. Explicit keys support trusted import
    and clearly marked synthetic tests; their independent origin is the caller's
    responsibility and cannot be established from the key bytes themselves.
    """

    __slots__ = ("_key_id", "_key")

    def __init__(self, verifier_key_id: str, key: bytes):
        _identifier(verifier_key_id)
        if type(key) is not bytes or len(key) != 32:
            raise ValueError("invalid_input")
        self._key_id, self._key = verifier_key_id, key

    @classmethod
    def generate(cls, verifier_key_id: str) -> "InMemoryCredentialVerifierKeyProvider":
        """Generate a fresh OS-random key, unrelated to any credential or seed."""
        _identifier(verifier_key_id)
        try:
            key = secrets.token_bytes(32)
            return cls(verifier_key_id, key)
        except Exception:
            raise ValueError("key_unavailable") from None

    def get_key(self, verifier_key_id: str) -> bytes:
        _identifier(verifier_key_id)
        if verifier_key_id != self._key_id:
            raise LookupError("key_unavailable")
        return self._key

    def __repr__(self) -> str:
        return "InMemoryCredentialVerifierKeyProvider(<redacted>)"


def _get_key(provider: CredentialVerifierKeyProvider, key_id: str) -> bytes:
    try:
        key = provider.get_key(key_id)
        if type(key) is not bytes or len(key) != 32:
            raise ValueError
        return key
    except Exception:
        raise ValueError("key_unavailable") from None


@dataclass(frozen=True, slots=True, repr=False)
class CredentialVerifierRecord:
    """Provisioning data, not a validated admission decision.

    enroll() creates a valid record. Direct construction also permits imported
    malformed/unsupported records so verification can reject them explicitly.
    All fields are checked again at verification. The tag is hidden from repr,
    but trusted provisioning can explicitly serialize it; do not log asdict().
    """

    device_id: str
    enrollment_id: str
    reconstruction_id: str
    verifier_key_id: str
    tag: bytes = field(repr=False)
    schema: str = _SCHEMA
    algorithm: str = _ALGORITHM
    enabled: bool = True
    revoked: bool = False

    def __repr__(self) -> str:
        # Imported malformed fields must not turn repr into a secret dump.
        return "CredentialVerifierRecord(<redacted>)"

    @classmethod
    def enroll(
        cls, *, device_id: str, enrollment_id: str, reconstruction_id: str,
        verifier_key_id: str, credential4: bytes,
        key_provider: CredentialVerifierKeyProvider,
    ) -> "CredentialVerifierRecord":
        """Trusted enrollment only; returns no plaintext credential or key.

        Raises ValueError with only invalid_input, key_unavailable, or
        internal_error. Runtime verification never calls this method.
        """
        message = _message(device_id, enrollment_id, reconstruction_id, verifier_key_id, credential4)
        key = _get_key(key_provider, verifier_key_id)
        try:
            tag = hmac.new(key, message, hashlib.sha256).digest()
        except Exception:
            raise ValueError("internal_error") from None
        return cls(device_id, enrollment_id, reconstruction_id, verifier_key_id, tag)


class CredentialVerifierStore:
    """Read-only enrollment snapshot, indexed by exact device/enrollment IDs.

    Duplicate bindings are rejected even if one record is disabled. No record
    replacement, re-enrollment, key search, or active-generation policy occurs
    here. The caller supplies the trusted current enrollment binding.
    """

    __slots__ = ("_records",)

    def __init__(self, records: Iterable[CredentialVerifierRecord] = ()):
        indexed = {}
        for record in records:
            if type(record) is not CredentialVerifierRecord:
                raise ValueError("unsupported_record")
            _identifier(record.device_id)
            _identifier(record.enrollment_id)
            binding = (record.device_id, record.enrollment_id)
            if binding in indexed:
                raise ValueError("duplicate_record")
            indexed[binding] = record
        self._records = MappingProxyType(indexed)

    def get(self, device_id: str, enrollment_id: str) -> CredentialVerifierRecord | None:
        _identifier(device_id)
        _identifier(enrollment_id)
        return self._records.get((device_id, enrollment_id))

    def __repr__(self) -> str:
        return "CredentialVerifierStore(<redacted>)"


@dataclass(frozen=True, slots=True)
class CredentialAdmissionResult:
    """Secret-free comparison outcome; not a session authorization handle."""

    outcome: Literal[
        "verified", "credential_mismatch", "record_missing", "record_disabled",
        "unsupported_record", "key_unavailable", "binding_mismatch",
        "invalid_input", "internal_error",
    ]

    def __post_init__(self):
        if type(self.outcome) is not str or self.outcome not in _OUTCOMES:
            raise ValueError("invalid_input")

    @property
    def verified(self) -> bool:
        return self.outcome == "verified"

    def __bool__(self) -> bool:
        return self.verified


def _supported(record) -> bool:
    if type(record) is not CredentialVerifierRecord:
        return False
    if (type(record.schema) is not str or record.schema != _SCHEMA
            or type(record.algorithm) is not str or record.algorithm != _ALGORITHM
            or type(record.tag) is not bytes or len(record.tag) != 32
            or type(record.enabled) is not bool or type(record.revoked) is not bool):
        return False
    try:
        for value in (record.device_id, record.enrollment_id,
                      record.reconstruction_id, record.verifier_key_id):
            _identifier(value)
    except ValueError:
        return False
    return True


class LocalAdmissionAuthorization:
    """Opaque in-process identity. Only a service's live issuance table grants authority.

    No fields, credential hash, key, wire representation, or transferable pickle.
    object.__new__ can allocate a lookalike in Python; it has no table entry.
    This is not isolation from malicious code inside the trusted process.
    """

    __slots__ = ()

    def __new__(cls):
        raise TypeError("admission_service_required")

    def __repr__(self):
        return "LocalAdmissionAuthorization(<opaque>)"

    def __reduce_ex__(self, protocol):
        raise TypeError("local_admission_not_serializable")


@dataclass(slots=True, repr=False)
class _Admission:
    candidate: bytes
    record: CredentialVerifierRecord
    attempt_id: str
    deadline_ns: int
    request: bytes | None = None
    consumed: bool = False
    transcript: bytes | None = None


class CredentialAdmissionService:
    """Compare a candidate with enrollment state, without consulting truth.

    Verification remains the Phase 1 primitive. Local authorization operations
    retain a private candidate until claim, revocation, or lazy expiry cleanup.
    Authorization validity is bounded by the handshake lifetime. No HKDF,
    networking, or evaluator truth is used here.
    """

    __slots__ = ("_store", "_key_provider", "_admissions", "_lock", "_revoked")

    def __init__(self, store: CredentialVerifierStore, key_provider: CredentialVerifierKeyProvider):
        if type(store) is not CredentialVerifierStore:
            raise ValueError("invalid_input")
        self._store, self._key_provider = store, key_provider
        self._admissions = {}
        self._lock = RLock()
        self._revoked = set()

    def __repr__(self) -> str:
        return "CredentialAdmissionService(<redacted>)"

    def _live(self, authorization):
        if type(authorization) is not LocalAdmissionAuthorization:
            return None
        state = self._admissions.get(authorization)
        if state is None:
            return None
        record = state.record
        current = self._store.get(record.device_id, record.enrollment_id)
        if (time.monotonic_ns() >= state.deadline_ns or current is not record
                or not _supported(current) or not current.enabled or current.revoked
                or (record.device_id, record.enrollment_id) in self._revoked):
            self._admissions.pop(authorization, None)
            return None
        return state

    def authorize(self, candidate_credential4, *, device_id, enrollment_id,
                  reconstruction_id, attempt_id, timeout_ms):
        """Verify first; mint one local identity on pass. Never allocate a request."""
        try:
            _identifier(attempt_id)
            if type(timeout_ms) is not int or not 1 <= timeout_ms <= 0xffffffff:
                return None
            with self._lock:
                # Lazy cleanup: expired handles cannot authorize any operation.
                for handle in tuple(self._admissions):
                    self._live(handle)
                result = self.verify(candidate_credential4, device_id=device_id,
                                     enrollment_id=enrollment_id, reconstruction_id=reconstruction_id)
                if not result.verified or (device_id, enrollment_id) in self._revoked:
                    return None
                record = self._store.get(device_id, enrollment_id)
                handle = object.__new__(LocalAdmissionAuthorization)
                self._admissions[handle] = _Admission(candidate_credential4, record, attempt_id,
                                                      time.monotonic_ns() + timeout_ms * 1_000_000)
                return handle
        except Exception:
            return None

    def bind_request(self, authorization, request, *, attempt_id):
        """One immutable request per issued authorization, after verification."""
        with self._lock:
            state = self._live(authorization)
            if (state is None or state.request is not None or state.attempt_id != attempt_id
                    or type(request) is not bytes):
                return False
            state.request = request
            return True

    def consume(self, authorization, request, *, device_id, enrollment_id, reconstruction_id):
        """Atomically consume for exactly one receiver before its key derivation."""
        with self._lock:
            state = self._live(authorization)
            if (state is None or state.consumed or state.request is None
                    or type(request) is not bytes or state.request != request
                    or (state.record.device_id, state.record.enrollment_id, state.record.reconstruction_id)
                    != (device_id, enrollment_id, reconstruction_id)):
                return False
            state.consumed = True
            return True

    def bind_challenge(self, authorization, transcript):
        """Bind receiver-generated session fields; no second challenge is allowed."""
        with self._lock:
            state = self._live(authorization)
            if state is None or not state.consumed or state.transcript is not None or type(transcript) is not bytes:
                return False
            state.transcript = transcript
            return True

    def claim_candidate(self, authorization, candidate, *, attempt_id, request, transcript,
                        device_id, enrollment_id, reconstruction_id):
        """One sender use, only after receiver consumption, for unchanged bytes.

        Remove authorization on every claim, including a failed swap attempt.
        Return the candidate verified by Phase 1, never the receiver reference.
        """
        with self._lock:
            state = self._live(authorization)
            self.revoke(authorization)
            if (state is None or not state.consumed or state.transcript is None
                    or state.attempt_id != attempt_id or state.request != request
                    or state.transcript != transcript or type(candidate) is not bytes
                    or not hmac.compare_digest(state.candidate, candidate)
                    or (state.record.device_id, state.record.enrollment_id, state.record.reconstruction_id)
                    != (device_id, enrollment_id, reconstruction_id)):
                return None
            return state.candidate

    def revoke(self, authorization):
        with self._lock:
            if type(authorization) is LocalAdmissionAuthorization:
                self._admissions.pop(authorization, None)

    def revoke_enrollment(self, device_id, enrollment_id):
        """Local irreversible revocation of this generation; no rotation service."""
        _identifier(device_id)
        _identifier(enrollment_id)
        with self._lock:
            self._revoked.add((device_id, enrollment_id))
            for handle, state in tuple(self._admissions.items()):
                if (state.record.device_id, state.record.enrollment_id) == (device_id, enrollment_id):
                    del self._admissions[handle]

    def verify(
        self, candidate_credential4: bytes, *, device_id: str,
        enrollment_id: str, reconstruction_id: str,
    ) -> CredentialAdmissionResult:
        """Fail closed, with enum-only diagnostics; never retry or enroll."""
        try:
            _credential(candidate_credential4)
            for value in (device_id, enrollment_id, reconstruction_id):
                _identifier(value)
        except ValueError:
            return CredentialAdmissionResult("invalid_input")
        try:
            record = self._store.get(device_id, enrollment_id)
            if record is None:
                return CredentialAdmissionResult("record_missing")
            if not _supported(record):
                return CredentialAdmissionResult("unsupported_record")
            if (record.device_id != device_id or record.enrollment_id != enrollment_id
                    or record.reconstruction_id != reconstruction_id):
                return CredentialAdmissionResult("binding_mismatch")
            if not record.enabled or record.revoked or (device_id, enrollment_id) in self._revoked:
                return CredentialAdmissionResult("record_disabled")
            try:
                key = _get_key(self._key_provider, record.verifier_key_id)
            except ValueError:
                return CredentialAdmissionResult("key_unavailable")
            message = _message(device_id, enrollment_id, reconstruction_id,
                               record.verifier_key_id, candidate_credential4)
            tag = hmac.new(key, message, hashlib.sha256).digest()
            return CredentialAdmissionResult(
                "verified" if hmac.compare_digest(tag, record.tag) else "credential_mismatch"
            )
        except Exception:
            return CredentialAdmissionResult("internal_error")
