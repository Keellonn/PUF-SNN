"""Verifier-owned operational records and separately timed research JSONL I/O.
No crash durability or tamper evidence is claimed. Private records have nullable
measurement slots filled after commit. Public snapshots never alias those slots.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
from threading import RLock
import time

STAGES = ("reconstruction", "session_establishment", "kdf", "sender_prepare",
          "sender_hmac", "verifier_auth", "audit_io")

@dataclass(frozen=True)
class Provenance:
    run_id: str | None = None
    source_id: str | None = None
    config_sha256: str | None = None
    input_artifact_sha256: str | None = None
    source_record_id: str | None = None

    def __post_init__(self):
        if any(value is not None and type(value) is not str for value in asdict(self).values()):
            raise ValueError("provenance values must be strings or null")

def provenance(value=None):
    if value is None:
        return Provenance()
    if type(value) is not Provenance:
        raise ValueError("trusted local provenance must be Provenance")
    value.__post_init__()
    return value

def summarize_ns(values):
    values = list(values)
    if any(type(v) is not int or v < 0 for v in values):
        raise ValueError("timings require nonnegative integer nanoseconds")
    if not values:
        return dict(count=0, mean=None, median=None, p95=None, maximum=None)
    ordered = sorted(values)
    # Exact index 95*(n-1)/100, without a library-dependent percentile rule.
    low, remainder = divmod(95 * (len(ordered) - 1), 100)
    p95 = ordered[low] + (ordered[min(low + 1, len(ordered)-1)] - ordered[low]) * remainder / 100
    return dict(count=len(values), mean=statistics.mean(values), median=statistics.median(values),
                p95=p95, maximum=max(values))

def latency_summary(rows):
    """All observations retained; paired total is computed per row, never by p95."""
    stages = STAGES + ("total_layer3",)
    groups = {}
    for outcome in ("overall", "accept", "reject", "closed"):
        selected = [r for r in rows if outcome == "overall" or r["decision"] == outcome]
        groups[outcome] = {}
        for stage in stages:
            values = []
            for row in selected:
                if stage == "total_layer3":
                    a, b = row["latency_ns"].get("sender_prepare"), row["latency_ns"].get("verifier_auth")
                    value = a + b if a is not None and b is not None else None
                else:
                    value = row["latency_ns"].get(stage)
                if value is not None:
                    values.append(value)
            groups[outcome][stage] = summarize_ns(values)
    return {"units": "ns", "p95_method": "linear-index-0.95*(n-1)", "groups": groups}

class AuditUnavailable(RuntimeError):
    def __init__(self):
        super().__init__("audit_unavailable")

class AuditRecorder:
    def __init__(self, recorder_id, *, origin="verifier"):
        if origin not in ("sender", "verifier"):
            raise ValueError("invalid audit origin")
        self.origin = origin
        self.recorder_id = recorder_id.hex()
        self._records = ()
        self._ordinal = 0
        self.incomplete = False
        self._emergency_used = False
        # Reserved at initialization, before any session is admitted.
        self._emergency = self.record(reason="internal_error", detail="audit_unavailable")

    @property
    def records(self):
        rows = self._records + ((self._emergency,) if self._emergency_used else ())
        return deepcopy(rows)

    def record(self, **values):
        record = dict(
            audit_schema="puf-snn-auth-audit-v1", protocol_version="2.0", event_id=None,
            event_type="window", origin=self.origin, attempt_id=None, device_id=None,
            session_id=None, window_id=None, identity_authenticated=False, sequence_number=None,
            observed_protocol_version=None,
            recorded_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            recorded_monotonic_ns=time.monotonic_ns(), decision="reject", reason=None, detail=None,
            authentication_result="not_checked", order_result="not_checked", expected_sequence=None,
            last_accepted_before=None, last_accepted_after=None, missing_start=None, missing_end=None,
            missing_count=None, state_before=None, state_after=None, authenticated_bytes_sha256=None,
            latency_ns=dict.fromkeys(STAGES), provenance=asdict(Provenance()))
        if set(values) - set(record):
            raise ValueError("unknown audit field")
        record.update(values)
        return record

    def prepare(self, records):
        """Allocate append capacity before replay mutation; owner holds its mutex."""
        for index, record in enumerate(records, self._ordinal + 1):
            record["event_id"] = f"{self.recorder_id}:{index}"
        return self._records + tuple(records), self._ordinal + len(records)

    def commit(self, prepared):
        self._records, self._ordinal = prepared

    def emergency(self, detail="audit_unavailable", event_type="window"):
        self.incomplete = True
        if not self._emergency_used:
            self._emergency["event_id"] = f"{self.recorder_id}:{self._ordinal + 1}"
            self._emergency["recorded_monotonic_ns"] = time.monotonic_ns()
            self._emergency["recorded_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            self._emergency["detail"] = detail
            self._emergency["event_type"] = event_type
            self._emergency_used = True
        return self._emergency

class AuditJSONL:
    """Exclusive file, append batches once, stop permanently on any I/O failure.

    audit_io is a batch measurement in io_batches (no per-record allocation).
    Raw audit rows keep audit_io=null: measuring their own completed flush would
    require a second write and misrepresent that measurement boundary.
    """
    def __init__(self, directory):
        self.directory = Path(directory)
        self._written = 0
        self.io_batches = []
        self.failed = False
        self._io_lock = RLock()
        self._file = (self.directory / "audit.jsonl").open("x", encoding="utf-8", newline="\n")

    def _incomplete(self):
        self.failed = True
        try:
            (self.directory / "INCOMPLETE").write_text("audit_unavailable\n", encoding="utf-8")
        except OSError:
            pass  # The caller must also report incomplete evidence out of band.

    def flush(self, records):
        with self._io_lock:
            return self._flush(records)

    def _flush(self, records):
        if self.failed:
            raise AuditUnavailable()
        batch = records[self._written:]
        if not batch:
            return
        start = time.perf_counter_ns()
        try:
            for row in batch:
                self._file.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")
            self._file.flush()
        except Exception:
            self._incomplete()
            raise AuditUnavailable() from None
        elapsed = time.perf_counter_ns() - start
        self.io_batches.append(dict(batch_size=len(batch), audit_io_ns=elapsed, allocation="batch_only"))
        self._written += len(batch)

    def close(self):
        with self._io_lock:
            try:
                self._file.close()
            except Exception:
                self._incomplete()
                raise AuditUnavailable() from None