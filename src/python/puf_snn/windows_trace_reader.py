"""Read ONLY our public marker payloads from an existing, finalized private ETL.

No capture, registry changes, model calls, shell commands or file writes.
Native layouts and consumer lifecycle are documented by Microsoft:
https://learn.microsoft.com/en-us/windows/win32/api/evntrace/ns-evntrace-event_trace_logfilew
https://learn.microsoft.com/en-us/windows/win32/api/evntrace/ns-evntrace-trace_logfile_header
https://learn.microsoft.com/en-us/windows/win32/api/evntcons/ns-evntcons-event_record
"""

from __future__ import annotations

import csv
import ctypes as c
import os
from pathlib import Path
import re
import uuid

from puf_snn.windows_trace import (
    PROVIDER_GUID, EVENT_ID, EVENT_VERSION, EVENT_LEVEL, EVENT_KEYWORD,
    MARKER_STRUCT, _Guid, _EventDescriptor, decode_marker, align_marker_clocks,
)


class _Header(c.Structure):
    _fields_ = [("size", c.c_uint16), ("header_type", c.c_uint16),
                ("flags", c.c_uint16), ("properties", c.c_uint16),
                ("tid", c.c_uint32), ("pid", c.c_uint32), ("timestamp", c.c_int64),
                ("provider", _Guid), ("descriptor", _EventDescriptor),
                ("processor_time", c.c_uint64), ("activity", _Guid)]


class _Record(c.Structure):
    _fields_ = [("header", _Header), ("buffer_context", c.c_uint32),
                ("extended_count", c.c_uint16), ("data_length", c.c_uint16),
                ("extended_data", c.c_void_p), ("user_data", c.c_void_p), ("context", c.c_void_p)]


class _LossInfo(c.Structure):
    _fields_ = [("start_buffers", c.c_uint32), ("pointer_size", c.c_uint32),
                ("events_lost", c.c_uint32), ("cpu_mhz", c.c_uint32)]


class _HeaderUnion(c.Union):
    _fields_ = [("guid", _Guid), ("loss", _LossInfo)]


class _LogHeader(c.Structure):
    _fields_ = [("buffer_size", c.c_uint32), ("version", c.c_uint32),
                ("provider_version", c.c_uint32), ("processors", c.c_uint32),
                ("end_time", c.c_int64), ("timer_resolution", c.c_uint32),
                ("max_file_size", c.c_uint32), ("log_mode", c.c_uint32),
                ("buffers_written", c.c_uint32), ("instance", _HeaderUnion),
                ("logger_name", c.c_void_p), ("log_name", c.c_void_p),
                ("timezone", c.c_ubyte * 172), ("boot_time", c.c_int64),
                ("perf_freq", c.c_int64), ("start_time", c.c_int64),
                ("clock_type", c.c_uint32), ("buffers_lost", c.c_uint32)]


class _LogFile(c.Structure):
    _fields_ = [("file_name", c.c_wchar_p), ("logger_name", c.c_wchar_p),
                ("current_time", c.c_int64), ("buffers_read", c.c_uint32),
                ("processing_mode", c.c_uint32), ("current_event", c.c_ubyte * 88),
                ("header", _LogHeader), ("buffer_callback", c.c_void_p),
                ("buffer_size", c.c_uint32), ("filled", c.c_uint32),
                ("unused_events_lost", c.c_uint32), ("event_callback", c.c_void_p),
                ("is_kernel", c.c_uint32), ("context", c.c_void_p)]


def require_reader_abi():
    if os.name != "nt" or c.sizeof(c.c_void_p) != 8:
        raise RuntimeError("saved ETL reader requires Windows x64")
    if (c.sizeof(_Header), c.sizeof(_Record), c.sizeof(_LogHeader), c.sizeof(_LogFile)) != (80, 112, 280, 448):
        raise RuntimeError("native ETL structure sizes differ")
    if (_Record.user_data.offset, _LogFile.header.offset, _LogFile.event_callback.offset) != (96, 120, 424):
        raise RuntimeError("native ETL structure offsets differ")


def validate_trace_header(metadata):
    integers = ("events_lost", "buffers_lost", "pointer_size", "clock_type", "qpc_frequency_hz")
    if any(type(metadata.get(key)) is not int for key in integers):
        raise ValueError("trace header requires exact integer fields")
    if (metadata["events_lost"] != 0 or metadata["buffers_lost"] != 0
            or metadata["pointer_size"] != 8 or metadata["clock_type"] != 1
            or metadata["qpc_frequency_hz"] <= 0 or metadata.get("finalized") is not True):
        raise ValueError("final trace header/loss/QPC metadata does not permit correlation")


def read_native_markers(etl, *, maximum_markers=100, api=None):
    """Saved-file consumer. Filter provider BEFORE dereferencing UserData.

    EVENT_TRACE_LOGFILEW.EventsLost is unused; final LogfileHeader loss fields
    are authoritative here. No unrelated payloads, process names or paths are
    returned. Unknown versions of OUR marker fail closed, not silently skipped.
    The optional API argument supports tests with fabricated events only.
    """
    require_reader_abi()
    path = Path(etl)
    if not path.is_file() or path.is_symlink():
        raise ValueError("reader requires an existing ordinary saved ETL file")
    if type(maximum_markers) is not int or not 2 <= maximum_markers <= 4096:
        raise ValueError("invalid marker inventory bound")
    rows, errors = [], []
    provider_bytes = uuid.UUID(PROVIDER_GUID).bytes_le
    callback_type = c.WINFUNCTYPE(None, c.POINTER(_Record))

    @callback_type
    def receive(pointer):
        try:
            record = pointer.contents
            header = record.header
            if bytes(header.provider) != provider_bytes:
                return
            descriptor = header.descriptor
            if ((descriptor.id, descriptor.version, descriptor.level, descriptor.keyword,
                 descriptor.channel, descriptor.opcode, descriptor.task) !=
                    (EVENT_ID, EVENT_VERSION, EVENT_LEVEL, EVENT_KEYWORD, 0, 0, 0)
                    or record.data_length != MARKER_STRUCT.size or not record.user_data
                    or header.timestamp <= 0):
                raise ValueError("marker descriptor, clock or payload length differs")
            row = decode_marker(c.string_at(record.user_data, record.data_length))
            if row["process_id"] != header.pid or row["native_thread_id"] != header.tid:
                raise ValueError("marker payload identity differs from native event header")
            row.update(provider_guid=PROVIDER_GUID, event_id=descriptor.id, event_version=descriptor.version,
                       keyword=descriptor.keyword, raw_qpc_ticks=header.timestamp)
            if len(rows) >= maximum_markers:
                raise ValueError("unexpected marker inventory size")
            rows.append(row)
        except BaseException as error:
            if not errors:
                errors.append(type(error).__name__)  # Never serialize raw private exception text.

    if api is None:
        api = c.WinDLL("advapi32", use_last_error=True)
        api.OpenTraceW.argtypes = [c.POINTER(_LogFile)]
        api.OpenTraceW.restype = c.c_uint64
        api.ProcessTrace.argtypes = [c.POINTER(c.c_uint64), c.c_uint32, c.c_void_p, c.c_void_p]
        api.ProcessTrace.restype = c.c_uint32
        api.CloseTrace.argtypes = [c.c_uint64]
        api.CloseTrace.restype = c.c_uint32
    logfile = _LogFile()
    logfile.file_name = str(path)
    # EVENT_RECORD + RAW_TIMESTAMP, NOT REAL_TIME. LoggerName stays NULL.
    logfile.processing_mode = 0x10000000 | 0x00001000
    logfile.event_callback = c.cast(receive, c.c_void_p).value
    handle = api.OpenTraceW(c.byref(logfile))
    if handle == 2**64 - 1:
        raise RuntimeError("OpenTraceW could not open saved ETL")
    status = close_status = None
    try:
        handles = (c.c_uint64 * 1)(handle)
        status = api.ProcessTrace(handles, 1, None, None)
    finally:
        close_status = api.CloseTrace(handle)
    if status or close_status or errors:
        raise RuntimeError("saved ETL processing or marker callback failed")
    metadata = dict(events_lost=logfile.header.instance.loss.events_lost,
                    buffers_lost=logfile.header.buffers_lost, pointer_size=logfile.header.instance.loss.pointer_size,
                    clock_type=logfile.header.clock_type, qpc_frequency_hz=logfile.header.perf_freq,
                    finalized=logfile.header.end_time > 0, process_trace_exit_code=status,
                    close_trace_exit_code=close_status)
    validate_trace_header(metadata)
    return rows, metadata


def validate_qpc_brackets(brackets, native_events, metadata):
    """Check EVERY actual native QPC tick falls inside its own Python bracket."""
    validate_trace_header(metadata)
    if len(brackets) < 2 or len(brackets) != len(native_events):
        raise ValueError("missing or excess native markers")
    identities, previous_after, previous_ticks = set(), 0, 0
    for index, (bracket, event) in enumerate(zip(brackets, native_events), 1):
        for record in (bracket, event):
            if (record.get("provider_guid"), record.get("event_id"), record.get("event_version"),
                    record.get("keyword")) != (PROVIDER_GUID, EVENT_ID, EVENT_VERSION, EVENT_KEYWORD):
                raise ValueError("marker provider or descriptor differs")
        for field in ("marker_index", "process_id", "native_thread_id", "label"):
            if bracket[field] != event[field]:
                raise ValueError("marker inventory or identity differs")
        if bracket["marker_index"] != index or bracket.get("write_succeeded") is not True:
            raise ValueError("marker order or API-write record differs")
        before, after, ticks = bracket["perf_before_ns"], bracket["perf_after_ns"], event["raw_qpc_ticks"]
        if (any(type(value) is not int for value in (before, after, ticks))
                or before <= 0 or after < before or before < previous_after or ticks <= previous_ticks):
            raise ValueError("marker clocks are invalid or run backward")
        native_ns = ticks * 1_000_000_000 // metadata["qpc_frequency_hz"]
        if not before <= native_ns <= after:
            raise ValueError("native QPC marker lies outside its Python bracket")
        identities.add((bracket["process_id"], bracket["native_thread_id"]))
        previous_after, previous_ticks = after, ticks
    if len(identities) != 1:
        raise ValueError("mixed native marker identities")
    return dict(actual_native_marker_payloads_validated=True, native_qpc_brackets_validated=True,
                marker_count=len(brackets), event_loss_validated=True, os_cause_established=False)


def correlate_marker_export(lines, brackets, native_events, metadata):
    """Bind xperf relative times to independently decoded actual payloads.

    xperf -add_rawdata provides timestamp metadata, NOT the UserData payload.
    Never infer payload/index from CSV order alone. All provider events must
    match the native reader; one missing or extra event blocks attribution.
    """
    validated = validate_qpc_brackets(brackets, native_events, metadata)
    indexed = {row["raw_qpc_ticks"]: row for row in native_events}
    if len(indexed) != len(native_events):
        raise ValueError("duplicate native QPC timestamp")
    exported, seen, raw = [], set(), None
    for line in lines:
        match = re.match(r"^#\s*\d+\s*#\s*(0x[0-9a-fA-F]+)\s*#\s*(\d+)", line)
        if match:
            raw = (int(match[1], 16), int(match[2]))
            continue
        if not line.strip().startswith("UnknownEvent/Crimson,"):
            continue
        fields = [part.strip() for part in next(csv.reader([line], skipinitialspace=True))]
        if len(fields) != 14 or fields[5].strip("{}").lower() != PROVIDER_GUID:
            raw = None
            continue
        if (raw is None or raw[0] not in indexed or raw[0] in seen
                or tuple(int(fields[i], 0) for i in (6, 9, 11, 12, 13)) != (1, 1, 4, 1, 28)
                or tuple(int(fields[i], 0) for i in (7, 8, 10)) != (0, 0, 0)):
            raise ValueError("native and exported marker headers differ")
        row = dict(indexed[raw[0]], etw_timestamp_us=int(fields[1]), etw_timestamp_ns=raw[1])
        pid = re.search(r"\((\d+)\)$", fields[2])
        if (not pid or int(pid[1]) != row["process_id"] or int(fields[3]) != row["native_thread_id"]
                or abs(row["etw_timestamp_us"] * 1000 - raw[1]) > 1000):
            raise ValueError("exported identity or quantized clock differs")
        exported.append(row)
        seen.add(raw[0])
        raw = None
    alignment = align_marker_clocks(brackets, exported)
    return dict(validated, clock_alignment_validated=True, alignment=alignment)
