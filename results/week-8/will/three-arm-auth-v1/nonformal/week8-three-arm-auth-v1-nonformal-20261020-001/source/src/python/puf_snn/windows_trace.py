"""Private Windows-trace support; importing this module never starts tracing.

Markers contain fixed public identifiers, not sensor values, credentials,
keys, command lines or paths. Writing a marker is NOT evidence that a decoder
observed it. The saved ETL, event loss, schemas and clock bounds need review.
"""

from __future__ import annotations

import ctypes
import os
import re
import struct
from threading import get_native_id
import time
import uuid


PROVIDER_GUID = "90553497-2ec7-49fa-a284-ade0159054fe"
EVENT_ID = 1
EVENT_VERSION = 1
EVENT_LEVEL = 4
EVENT_KEYWORD = 1
MARKER_LABELS = ("capture_begin", "inputs_verified", "condition_begin", "condition_end", "capture_end")
MARKER_STRUCT = struct.Struct("<8sQIII")
MARKER_MAGIC = b"PUFSNN6\0"
REQUIRED_SCHEMAS = {
    "CSwitch": ("New TID", "Old TID", "OldState", "Wait Reason", "CPU"),
    "ReadyThread": ("Rdy TID", "CPU"),
    "SampledProfile": ("ThreadID", "PrgrmCtr", "CPU"),
    "FileIoRead": ("ThreadID", "IrpPtr", "Size"),
    "FileIoWrite": ("ThreadID", "IrpPtr", "Size"),
    "FileIoOpEnd": ("IrpPtr", "ElapsedTime", "Status"),
    "DiskRead": ("ThreadID", "IrpPtr", "ElapsedTime"),
    "DiskWrite": ("ThreadID", "IrpPtr", "ElapsedTime"),
    "HardFault": ("ThreadID", "ElapsedTime"),
}


def positive_integer(value, name, maximum=None):
    if type(value) is not int or value <= 0 or (maximum is not None and value > maximum):
        raise ValueError(f"invalid {name}")
    return value


def encode_marker(index, process_id, native_thread_id, label):
    if label not in MARKER_LABELS:
        raise ValueError("marker label must be a fixed public phase")
    return MARKER_STRUCT.pack(MARKER_MAGIC, positive_integer(index, "marker index", 2**64 - 1),
                              positive_integer(process_id, "process id", 2**32 - 1),
                              positive_integer(native_thread_id, "thread id", 2**32 - 1),
                              MARKER_LABELS.index(label))


def decode_marker(payload):
    if type(payload) is not bytes or len(payload) != MARKER_STRUCT.size:
        raise ValueError("marker payload length differs")
    magic, index, pid, tid, phase = MARKER_STRUCT.unpack(payload)
    if magic != MARKER_MAGIC or not 0 <= phase < len(MARKER_LABELS):
        raise ValueError("marker magic or phase differs")
    positive_integer(index, "marker index")
    positive_integer(pid, "process id")
    positive_integer(tid, "thread id")
    return dict(marker_index=index, process_id=pid, native_thread_id=tid, label=MARKER_LABELS[phase])


class _Guid(ctypes.Structure):
    _fields_ = [("data1", ctypes.c_uint32), ("data2", ctypes.c_uint16),
                ("data3", ctypes.c_uint16), ("data4", ctypes.c_ubyte * 8)]


class _EventDescriptor(ctypes.Structure):
    _fields_ = [("id", ctypes.c_uint16), ("version", ctypes.c_ubyte), ("channel", ctypes.c_ubyte),
                ("level", ctypes.c_ubyte), ("opcode", ctypes.c_ubyte), ("task", ctypes.c_uint16),
                ("keyword", ctypes.c_uint64)]


class _DataDescriptor(ctypes.Structure):
    _fields_ = [("pointer", ctypes.c_uint64), ("size", ctypes.c_uint32), ("reserved", ctypes.c_uint32)]


class NativeEtwWriter:
    """Process-local EventRegister/EventWrite; no manifest/registry installation.

    Disabled providers can return success without recording anything. Check
    enablement before every write, then separately verify actual saved events.
    This diagnostic fails closed on API errors instead of treating them as data.
    """

    def __init__(self, api=None):
        self.handle = ctypes.c_uint64(0)
        self.api = api

    def __enter__(self):
        if self.handle.value:
            raise RuntimeError("marker writer is already registered")
        if self.api is None:
            if os.name != "nt":
                raise RuntimeError("native ETW markers require Windows")
            self.api = ctypes.WinDLL("advapi32", use_last_error=True)
            self.api.EventRegister.argtypes = [ctypes.POINTER(_Guid), ctypes.c_void_p,
                                               ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64)]
            self.api.EventRegister.restype = ctypes.c_uint32
            self.api.EventProviderEnabled.argtypes = [ctypes.c_uint64, ctypes.c_ubyte, ctypes.c_uint64]
            self.api.EventProviderEnabled.restype = ctypes.c_ubyte
            self.api.EventWrite.argtypes = [ctypes.c_uint64, ctypes.POINTER(_EventDescriptor),
                                           ctypes.c_uint32, ctypes.POINTER(_DataDescriptor)]
            self.api.EventWrite.restype = ctypes.c_uint32
            self.api.EventUnregister.argtypes = [ctypes.c_uint64]
            self.api.EventUnregister.restype = ctypes.c_uint32
        provider = _Guid.from_buffer_copy(uuid.UUID(PROVIDER_GUID).bytes_le)
        status = self.api.EventRegister(ctypes.byref(provider), None, None, ctypes.byref(self.handle))
        if status or not self.handle.value:
            # EventRegister promises a zero handle on failure. Be defensive
            # about an anomalous nonzero handle without leaving it registered.
            if self.handle.value:
                self.api.EventUnregister(self.handle)
                self.handle.value = 0
            raise RuntimeError(f"ETW provider registration failed ({status})")
        return self

    def emit(self, payload):
        decode_marker(payload)  # Reject arbitrary/sensitive event payloads.
        if not self.handle.value:
            raise RuntimeError("marker writer is not registered")
        if not self.api.EventProviderEnabled(self.handle, EVENT_LEVEL, EVENT_KEYWORD):
            raise RuntimeError("the marker provider is not enabled by a trace session")
        buffer = ctypes.create_string_buffer(payload, len(payload))
        descriptor = _EventDescriptor(EVENT_ID, EVENT_VERSION, 0, EVENT_LEVEL, 0, 0, EVENT_KEYWORD)
        data = _DataDescriptor(ctypes.addressof(buffer), len(payload), 0)
        status = self.api.EventWrite(self.handle, ctypes.byref(descriptor), 1, ctypes.byref(data))
        if status:
            raise RuntimeError(f"ETW marker write failed ({status})")

    def __exit__(self, exc_type, exc, traceback):
        status = self.api.EventUnregister(self.handle) if self.handle.value else 0
        self.unregister_status = status
        self.handle.value = 0
        if status and exc is None:
            raise RuntimeError(f"ETW provider unregister failed ({status})")
        return False


class BracketedMarkers:
    """Bound the ETW write with the same absolute perf_counter_ns as roots.

    Brackets include enablement/API preparation as a conservative uncertainty
    bound. These calls belong BETWEEN roots, never inside authentication or
    inference timers. No wall-clock timestamp is used for correlation.
    """

    def __init__(self, writer, clock=time.perf_counter_ns, pid=os.getpid, tid=get_native_id):
        self.writer, self.clock, self.pid, self.tid = writer, clock, pid, tid
        self.rows = []

    def mark(self, label, capture=None):
        if capture is not None and capture.active:
            raise RuntimeError("ETW marker must remain outside a root timer")
        index, pid, tid = len(self.rows) + 1, self.pid(), self.tid()
        payload = encode_marker(index, pid, tid, label)
        before = self.clock()
        self.writer.emit(payload)
        after = self.clock()
        if type(before) is not int or type(after) is not int or before <= 0 or after < before:
            raise RuntimeError("invalid monotonic marker bracket")
        row = dict(decode_marker(payload), provider_guid=PROVIDER_GUID, event_id=EVENT_ID,
                   event_version=EVENT_VERSION, keyword=EVENT_KEYWORD,
                   perf_before_ns=before, perf_after_ns=after, write_succeeded=True)
        self.rows.append(row)
        return dict(row)


def align_marker_clocks(brackets, decoded_events, *, timestamp_quantization_ns=1000,
                       maximum_uncertainty_ns=100_000):
    """Intersection of offset bounds; xperf timestamps are relative microseconds.

    decoded_events MUST come from matching provider/id/version and payload,
    not a process command line containing marker text. All markers are kept.
    Bounds permit +/- one exported microsecond; no fitted scale or result-based
    outlier deletion. A failed/nonspecific alignment blocks interval attribution.
    """
    positive_integer(timestamp_quantization_ns, "timestamp quantization")
    positive_integer(maximum_uncertainty_ns, "uncertainty bound")
    if len(brackets) < 2 or len(brackets) != len(decoded_events):
        raise ValueError("at least two markers with the exact same inventory are required")
    low, high, previous_before, previous_etw = None, None, None, None
    pid_tid = set()
    for index, (bracket, event) in enumerate(zip(brackets, decoded_events), start=1):
        for record in (bracket, event):
            if (record.get("provider_guid") != PROVIDER_GUID or record.get("event_id") != EVENT_ID
                    or record.get("event_version") != EVENT_VERSION or record.get("keyword") != EVENT_KEYWORD):
                raise ValueError("wrong marker provider or event descriptor")
        for field in ("marker_index", "process_id", "native_thread_id", "label"):
            if bracket[field] != event[field]:
                raise ValueError("marker payload/identity differs")
        if bracket["marker_index"] != index or bracket.get("write_succeeded") is not True:
            raise ValueError("marker inventory is not ordered, complete and successful")
        before, after = bracket["perf_before_ns"], bracket["perf_after_ns"]
        micros = event["etw_timestamp_us"]
        if (type(before) is not int or type(after) is not int or before <= 0 or after < before
                or type(micros) is not int or micros < 0):
            raise ValueError("invalid marker clocks")
        if previous_before is not None and (before < previous_before or micros < previous_etw):
            raise ValueError("marker clocks run backward")
        pid_tid.add((bracket["process_id"], bracket["native_thread_id"]))
        one_low = before - micros * 1000 - timestamp_quantization_ns
        one_high = after - micros * 1000 + timestamp_quantization_ns
        low = one_low if low is None else max(low, one_low)
        high = one_high if high is None else min(high, one_high)
        previous_before, previous_etw = after, micros
    if len(pid_tid) != 1 or low > high or high - low > maximum_uncertainty_ns:
        raise ValueError("marker identities or clock-offset bounds do not support precise correlation")
    return dict(offset_low_ns=low, offset_high_ns=high, uncertainty_ns=high - low,
                marker_count=len(brackets), first_perf_ns=brackets[0]["perf_before_ns"],
                last_perf_ns=brackets[-1]["perf_after_ns"],
                etw_timestamp_unit="microseconds", perf_timestamp_unit="nanoseconds",
                os_cause_established=False)


def inspect_setup_dump(lines, warning_text=""):
    """Streaming, sanitized capability review of an EXISTING xperf dump.

    No recording/export/model calls occur. A zero loss count does not mean
    every Windows event version was decoded. Warnings remain explicit.
    No unrelated process name, command line, file path or raw event is returned.
    """
    in_header, schemas, counts, markers, loss = False, {}, {}, [], None
    unknown_count = invalid_count = 0
    for line in lines:
        stripped = line.strip()
        if stripped == "BeginHeader":
            in_header = True
            continue
        if stripped == "EndHeader":
            in_header = False
            continue
        loss_match = re.match(r"^OS Version:.*?Events Lost:\s*(\d+),\s*Buffers lost:\s*(\d+),", stripped)
        if loss_match:
            if loss is not None:
                raise ValueError("multiple trace summary headers")
            loss = dict(events_lost=int(loss_match[1]), buffers_lost=int(loss_match[2]))
        name, separator, rest = stripped.partition(",")
        if not separator:
            continue
        if in_header and name in REQUIRED_SCHEMAS:
            if name in schemas:
                raise ValueError("duplicate required event schema")
            schemas[name] = [field.strip() for field in rest.split(",")]
        elif not in_header and name in REQUIRED_SCHEMAS:
            counts[name] = counts.get(name, 0) + 1
        elif not in_header and name.startswith("UnknownEvent/"):
            unknown_count += 1
        elif not in_header and name.startswith("InvalidEvent/"):
            invalid_count += 1
        elif not in_header and name == "Mark":
            timestamp, comma, label = rest.strip().partition(",")
            if comma and label.strip() in ("PUF_SNN_WEEK6_SETUP_BEGIN", "PUF_SNN_WEEK6_SETUP_END"):
                markers.append(dict(label=label.strip(), etw_timestamp_us=int(timestamp)))
    if loss is None or loss != dict(events_lost=0, buffers_lost=0):
        raise ValueError("loss metadata absent or nonzero; do not infer absence from exit code")
    for name, fields in REQUIRED_SCHEMAS.items():
        if name not in schemas or "TimeStamp" not in schemas[name] or any(f not in schemas[name] for f in fields):
            raise ValueError(f"required event schema unavailable: {name}")
    if not all(counts.get(name, 0) > 0 for name in ("CSwitch", "ReadyThread", "SampledProfile")):
        raise ValueError("CPU/scheduling schemas exist but actual events are absent")
    if ([m["label"] for m in markers] != ["PUF_SNN_WEEK6_SETUP_BEGIN", "PUF_SNN_WEEK6_SETUP_END"]
            or markers[1]["etw_timestamp_us"] <= markers[0]["etw_timestamp_us"]):
        raise ValueError("actual setup marker events are missing, duplicated or out of order")
    warning_count = len(re.findall(r"(?im)^\s*warning:", warning_text))
    return dict(events_lost=0, buffers_lost=0, required_schemas=schemas,
                required_event_counts={name: counts.get(name, 0) for name in REQUIRED_SCHEMAS},
                setup_markers=markers, decoder_warning_count=warning_count,
                unknown_event_rows=unknown_count, invalid_event_rows=invalid_count,
                all_event_versions_decoded=False,  # Only the required subset was inspected.
                event_loss_validated=True, model_calls=0, latency_result=False,
                model_clock_alignment_validated=False, complete_causal_attribution_established=False)
