"""Fabricated saved-file API/events; no real capture, models or private payloads."""

from copy import deepcopy
import ctypes as c
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from puf_snn.windows_trace import (
    PROVIDER_GUID, _Guid, _EventDescriptor, encode_marker,
)
from puf_snn.windows_trace_reader import (
    _Record, _LogFile, read_native_markers, require_reader_abi,
    validate_trace_header, validate_qpc_brackets, correlate_marker_export,
)


def fixture():
    brackets, events, lines = [], [], []
    for index, label in enumerate(("capture_begin", "capture_end"), 1):
        ticks = 10_000_205 + (index - 1) * 10_000
        nanos = ticks * 100
        common = dict(marker_index=index, process_id=77, native_thread_id=88, label=label,
                      provider_guid=PROVIDER_GUID, event_id=1, event_version=1, keyword=1)
        brackets.append(dict(common, perf_before_ns=nanos - 200, perf_after_ns=nanos + 200,
                             write_succeeded=True))
        events.append(dict(common, raw_qpc_ticks=ticks))
        relative_ns = 20_500 + (index - 1) * 1_000_000
        lines += [f"# 3 # {ticks:#x} # {relative_ns}\n",
                  f"UnknownEvent/Crimson, {relative_ns // 1000}, private.exe(77), 88, 3, "
                  f"{{{PROVIDER_GUID}}}, 0x1, 0, 0, 0x1, 0, 0x4, 0x1, 28\n"]
    metadata = dict(events_lost=0, buffers_lost=0, pointer_size=8, clock_type=1,
                    qpc_frequency_hz=10_000_000, finalized=True)
    return brackets, events, lines, metadata


class FakeSavedApi:
    def __init__(self, events=None, *, open_fail=False, process_status=0, close_status=0,
                 loss=0, buffer_loss=0, raise_processing=False):
        self.events = events or []
        self.open_fail, self.process_status, self.close_status = open_fail, process_status, close_status
        self.loss, self.buffer_loss, self.raise_processing = loss, buffer_loss, raise_processing
        self.closed = []
        self.buffers = []

    def OpenTraceW(self, pointer):
        self.log = c.cast(pointer, c.POINTER(_LogFile)).contents
        if self.open_fail:
            return 2**64 - 1
        self.log.header.end_time = 1
        self.log.header.instance.loss.pointer_size = 8
        self.log.header.instance.loss.events_lost = self.loss
        self.log.header.buffers_lost = self.buffer_loss
        self.log.header.clock_type = 1
        self.log.header.perf_freq = 10_000_000
        self.log.unused_events_lost = 999  # Must NOT be confused with LogfileHeader.EventsLost.
        self.callback = c.WINFUNCTYPE(None, c.POINTER(_Record))(self.log.event_callback)
        return 123

    def ProcessTrace(self, handles, count, start, end):
        if self.raise_processing:
            raise RuntimeError("fabricated native API failure")
        for event in self.events:
            self.callback(c.pointer(event))
        return self.process_status

    def CloseTrace(self, handle):
        self.closed.append(handle)
        return self.close_status

    def event(self, index=1, label="capture_begin", provider=PROVIDER_GUID, **changes):
        payload = encode_marker(index, 77, 88, label)
        buffer = c.create_string_buffer(payload, len(payload))
        self.buffers.append(buffer)
        row = _Record()
        row.header.provider = _Guid.from_buffer_copy(uuid.UUID(provider).bytes_le)
        row.header.descriptor = _EventDescriptor(1, 1, 0, 4, 0, 0, 1)
        row.header.pid, row.header.tid, row.header.timestamp = 77, 88, 10_000_205 + index
        row.data_length, row.user_data = len(payload), c.addressof(buffer)
        for key, value in changes.items():
            if key in ("pid", "tid", "timestamp"):
                setattr(row.header, key, value)
            elif key == "version":
                row.header.descriptor.version = value
            else:
                setattr(row, key, value)
        return row


@unittest.skipUnless(os.name == "nt" and c.sizeof(c.c_void_p) == 8, "Windows x64 API fixtures")
class NativeReaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.etl = Path(self.temporary.name) / "fixture.etl"
        self.etl.write_bytes(b"fabricated placeholder, not an ETL")

    def test_abi_sizes_and_offsets(self):
        require_reader_abi()

    def test_saved_file_mode_and_actual_payload(self):
        api = FakeSavedApi()
        api.events = [api.event()]
        rows, metadata = read_native_markers(self.etl, api=api)
        self.assertEqual(rows[0]["label"], "capture_begin")
        self.assertEqual(rows[0]["process_id"], 77)
        self.assertEqual(metadata["events_lost"], 0)
        self.assertEqual(api.log.processing_mode, 0x10001000)
        self.assertIsNone(api.log.logger_name)
        self.assertEqual(api.closed, [123])

    def test_unrelated_provider_skipped_before_payload_access(self):
        api = FakeSavedApi()
        api.events = [api.event(provider="00000000-0000-0000-0000-000000000001", user_data=1)]
        with patch("puf_snn.windows_trace_reader.c.string_at", side_effect=AssertionError("not our payload")) as access:
            rows, _ = read_native_markers(self.etl, api=api)
        access.assert_not_called()
        self.assertEqual(rows, [])

    def test_unknown_own_version_fails_and_closes(self):
        api = FakeSavedApi()
        api.events = [api.event(version=2)]
        with self.assertRaisesRegex(RuntimeError, "callback failed"):
            read_native_markers(self.etl, api=api)
        self.assertEqual(api.closed, [123])

    def test_payload_length_and_header_identity_fail(self):
        for changes in ({"data_length": 27}, {"pid": 79}, {"tid": 89}, {"timestamp": 0}):
            with self.subTest(changes=changes):
                api = FakeSavedApi()
                api.events = [api.event(**changes)]
                with self.assertRaises(RuntimeError):
                    read_native_markers(self.etl, api=api)
                self.assertEqual(api.closed, [123])

    def test_marker_bound_fails_without_silently_truncating(self):
        api = FakeSavedApi()
        api.events = [api.event(index=index) for index in (1, 2, 3)]
        with self.assertRaises(RuntimeError):
            read_native_markers(self.etl, maximum_markers=2, api=api)

    def test_final_loss_fields_fail_closed(self):
        for changes in ({"loss": 1}, {"buffer_loss": 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                read_native_markers(self.etl, api=FakeSavedApi(**changes))

    def test_open_failure_does_not_close_invalid_handle(self):
        api = FakeSavedApi(open_fail=True)
        with self.assertRaises(RuntimeError):
            read_native_markers(self.etl, api=api)
        self.assertEqual(api.closed, [])

    def test_processing_failure_always_closes_own_handle(self):
        for changes in ({"process_status": 5}, {"close_status": 5}, {"raise_processing": True}):
            with self.subTest(changes=changes):
                api = FakeSavedApi(**changes)
                with self.assertRaises(RuntimeError):
                    read_native_markers(self.etl, api=api)
                self.assertEqual(api.closed, [123])

    def test_missing_file_and_bad_inventory_bound(self):
        with self.assertRaises(ValueError):
            read_native_markers(self.etl.with_name("absent.etl"), api=FakeSavedApi())
        for bound in (True, 1, 4097):
            with self.subTest(bound=bound), self.assertRaises(ValueError):
                read_native_markers(self.etl, maximum_markers=bound, api=FakeSavedApi())


class CorrelationTests(unittest.TestCase):
    def test_actual_payload_qpc_and_relative_export_reconcile(self):
        brackets, events, lines, metadata = fixture()
        result = correlate_marker_export(lines, brackets, events, metadata)
        self.assertTrue(result["clock_alignment_validated"])
        self.assertEqual(result["alignment"]["marker_count"], 2)
        self.assertFalse(result["os_cause_established"])

    def test_final_header_validation_requires_exact_types_and_zero_loss(self):
        metadata = fixture()[3]
        for key, value in (("events_lost", True), ("buffers_lost", 1), ("pointer_size", 4),
                           ("clock_type", 2), ("qpc_frequency_hz", 0), ("finalized", False)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_trace_header(dict(metadata, **{key: value}))

    def test_actual_native_timestamp_must_be_in_own_bracket(self):
        brackets, events, _, metadata = fixture()
        events[0]["raw_qpc_ticks"] -= 3
        with self.assertRaisesRegex(ValueError, "outside"):
            validate_qpc_brackets(brackets, events, metadata)

    def test_duplicate_missing_or_reordered_actual_markers_fail(self):
        brackets, events, _, metadata = fixture()
        for changed in (events[:1], list(reversed(events)), [events[0], events[0]]):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                validate_qpc_brackets(brackets, changed, metadata)

    def test_wrong_native_descriptor_or_identity_fails(self):
        brackets, events, _, metadata = fixture()
        for key, value in (("process_id", 9), ("native_thread_id", 9), ("event_version", 2)):
            changed = deepcopy(events)
            changed[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_qpc_brackets(brackets, changed, metadata)

    def test_mixed_matched_identities_still_fail(self):
        brackets, events, _, metadata = fixture()
        brackets[1]["process_id"] = events[1]["process_id"] = 78
        with self.assertRaises(ValueError):
            validate_qpc_brackets(brackets, events, metadata)

    def test_missing_export_is_not_inferred_from_order(self):
        brackets, events, lines, metadata = fixture()
        with self.assertRaises(ValueError):
            correlate_marker_export(lines[:2], brackets, events, metadata)

    def test_extra_export_and_duplicate_raw_timestamp_fail(self):
        brackets, events, lines, metadata = fixture()
        with self.assertRaises(ValueError):
            correlate_marker_export(lines + lines[:2], brackets, events, metadata)

    def test_export_requires_matching_raw_line(self):
        brackets, events, lines, metadata = fixture()
        with self.assertRaises(ValueError):
            correlate_marker_export(lines[1:], brackets, events, metadata)

    def test_export_header_pid_and_quantization_must_match(self):
        brackets, events, lines, metadata = fixture()
        for old, new in (("private.exe(77)", "private.exe(78)"), ("0x4, 0x1, 28", "0x5, 0x1, 28"),
                         (", 20,", ", 30,")):
            changed = [line.replace(old, new) for line in lines]
            with self.subTest(old=old), self.assertRaises(ValueError):
                correlate_marker_export(changed, brackets, events, metadata)

    def test_sanitized_result_has_no_process_name_or_raw_rows(self):
        brackets, events, lines, metadata = fixture()
        result = str(correlate_marker_export(lines, brackets, events, metadata))
        self.assertNotIn("private.exe", result)
        self.assertNotIn("raw_qpc_ticks", result)


if __name__ == "__main__":
    unittest.main()
