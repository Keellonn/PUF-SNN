"""Research-only provisioned credential source; no persistence or authorization.

Provision once with the same four bytes as the corresponding PUF enrollment.
This is trusted in-process storage, not secure hardware or a production vault.
Never serialize records with asdict(): repr redaction is not secret isolation.
"""
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Iterable, Literal, Protocol

from .binary_window import identifier


@dataclass(frozen=True, slots=True, repr=False)
class StoredCredentialRecord:
    device_id: str
    enrollment_id: str
    reconstruction_id: str
    credential4: bytes = field(repr=False)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        try:
            for value in (self.device_id, self.enrollment_id, self.reconstruction_id):
                identifier(value)
            if type(self.credential4) is not bytes or len(self.credential4) != 4:
                raise ValueError
        except Exception:
            raise ValueError("malformed_stored_credential") from None

    def __repr__(self) -> str:
        return "StoredCredentialRecord(<redacted>)"


class StoredCredentialProvider(Protocol):
    """Trusted lookup only. None means unavailable; exceptions mean a source fault."""

    def get_credential(self, *, device_id: str, enrollment_id: str,
                       reconstruction_id: str) -> StoredCredentialRecord | None: ...


class InMemoryStoredCredentialProvider:
    __slots__ = ("_records",)

    def __init__(self, records: Iterable[StoredCredentialRecord] = ()):
        indexed = {}
        for record in records:
            if type(record) is not StoredCredentialRecord:
                raise ValueError("malformed_stored_credential")
            record.validate()
            binding = (record.device_id, record.enrollment_id, record.reconstruction_id)
            if binding in indexed:
                raise ValueError("duplicate_stored_credential")
            indexed[binding] = record
        self._records = MappingProxyType(indexed)

    def get_credential(self, *, device_id: str, enrollment_id: str,
                       reconstruction_id: str) -> StoredCredentialRecord | None:
        for value in (device_id, enrollment_id, reconstruction_id):
            identifier(value)
        return self._records.get((device_id, enrollment_id, reconstruction_id))

    def __repr__(self) -> str:
        return "InMemoryStoredCredentialProvider(<redacted>)"


@dataclass(frozen=True, slots=True)
class StoredCredentialStatus:
    """Secret-free source/admission observation, never a grant of authority.

    No decoder/correction/PUF timing fields apply to this source. Infrastructure
    faults use internal_error and incomplete evidence, rather than ordinary FRR.
    attempt_id identifies the invocation; preparation_failure distinguishes an
    early rejection even when its ID duplicates a previously prepared attempt.
    """

    retrieval_outcome: Literal[
        "not_attempted", "success", "unavailable", "malformed", "infrastructure_error"
    ] = "not_attempted"
    verification_outcome: str | None = None
    admission_outcome: Literal[
        "not_invoked", "authorized", "refused", "infrastructure_error"
    ] = "not_invoked"
    credential_source: str = field(default="stored-provisioned-v1", init=False)
    attempt_id: str | None = field(default=None, kw_only=True)
    preparation_failure: str | None = field(default=None, kw_only=True)
