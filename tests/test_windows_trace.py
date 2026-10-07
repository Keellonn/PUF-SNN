import ctypes
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET

from puf_snn.windows_trace import (
    EVENT_ID, EVENT_KEYWORD, EVENT_LEVEL, EVENT_VERSION, MARKER_LABELS, MARKER_STRUCT,
    PROVIDER_GUID, REQUIRED_SCHEMAS, BracketedMarkers, NativeEtwWriter,
    _DataDescriptor, _EventDescriptor, _Guid, align_marker_clocks, decode_marker,
    encode_marker, inspect_setup_dump,
)


class FakeEtwApi:
    """No native API or recording is invoked by these tests."""

    def __init__(self):
        self.registration_status = self.write_status = self.unregister_status = 0
        self.enabled = True
        self.payloads, self.descriptors, self.unregisters = [], [], []

    def EventRegister(self, provider, callback, context, handle):
        self.provider = bytes(ctypes.cast(provider, ctypes.POINTER(_Guid)).contents)
        ctypes.cast(handle, ctypes.POINTER(ctypes.c_uint64)).contents.value = 0 if self.registration_status else 99
        return self.registration_status

    def EventProviderEnabled(self, handle, level, keyword):
        self.enable_arguments = (handle.value, level, keyword)
        return self.enabled

    def EventWrite(self, handle, descriptor, count, data):
        self.assert_count = count
        event = ctypes.cast(descriptor, ctypes.POINTER(_EventDescriptor)).contents
        self.descriptors.append(tuple(getattr(event, n) for n, _ in event._fields_))
        item = ctypes.cast(data, ctypes.POINTER(_DataDescriptor)).contents
        self.payloads.append(ctypes.string_at(item.pointer, item.size))
        return self.write_status

    def EventUnregister(self, handle):
        self.unregisters.append(handle.value)
        return self.unregister_status


def alignment_fixture():
    writer = Mock()
    clocks = iter([1_000_101_000, 1_000_111_000, 1_000_201_000, 1_000_211_000])
    markers = BracketedMarkers(writer, clock=lambda: next(clocks), pid=lambda: 123, tid=lambda: 456)
    markers.mark("capture_begin")
    markers.mark("capture_end")
    events = [dict(row, etw_timestamp_us=(i + 1) * 100) for i, row in enumerate(markers.rows)]
    return markers.rows, events


def setup_fixture():
    lines = ["BeginHeader\n"]
    for name, fields in REQUIRED_SCHEMAS.items():
        lines.append(name + ", TimeStamp, " + ", ".join(fields) + "\n")
    lines += ["Mark, TimeStamp, Mark\n", "EndHeader\n",
              "OS Version: 10.0.26200, Trace Size: 12KB, Events Lost: 0, Buffers lost: 0, Trace Start: 123\n"]
    for name in REQUIRED_SCHEMAS:
        lines.append(name + ", 100, private-other-process (100), private-file\n")
    lines += ["Mark, 120, PUF_SNN_WEEK6_SETUP_BEGIN\n", "Mark, 3120, PUF_SNN_WEEK6_SETUP_END\n"]
    return lines


class WindowsTraceTests(unittest.TestCase):
    def test_marker_layout_and_all_phase_round_trips(self):
        self.assertEqual(MARKER_STRUCT.size, 28)
        for label in MARKER_LABELS:
            payload = encode_marker(1, 2, 3, label)
            self.assertEqual(decode_marker(payload), dict(marker_index=1, process_id=2, native_thread_id=3, label=label))

    def test_marker_rejects_arbitrary_labels_and_boolean_ids(self):
        for args in ((1, 2, 3, "candidate-credential"), (True, 2, 3, "capture_begin"),
                     (1, -1, 3, "capture_begin"), (1, 2**32, 3, "capture_begin"),
                     (2**64, 2, 3, "capture_begin")):
            with self.subTest(args=args), self.assertRaises(ValueError):
                encode_marker(*args)

    def test_marker_rejects_length_magic_zero_and_unknown_phase(self):
        valid = encode_marker(1, 2, 3, "capture_begin")
        invalid = (valid[:-1], valid + b"x", b"badmagic" + valid[8:],
                   MARKER_STRUCT.pack(b"PUFSNN6\0", 0, 2, 3, 0),
                   MARKER_STRUCT.pack(b"PUFSNN6\0", 1, 2, 3, 99), bytearray(valid))
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                decode_marker(payload)

    def test_native_structure_sizes_and_little_endian_guid(self):
        import uuid
        self.assertEqual(ctypes.sizeof(_Guid), 16)
        self.assertEqual(ctypes.sizeof(_EventDescriptor), 16)
        self.assertEqual(ctypes.sizeof(_DataDescriptor), 16)
        api = FakeEtwApi()
        with NativeEtwWriter(api):
            self.assertEqual(api.provider, uuid.UUID(PROVIDER_GUID).bytes_le)

    def test_mocked_native_write_checks_descriptor_and_unregistration(self):
        api = FakeEtwApi()
        payload = encode_marker(1, 2, 3, "capture_begin")
        with NativeEtwWriter(api) as writer:
            writer.emit(payload)
        self.assertEqual(api.payloads, [payload])
        self.assertEqual(api.descriptors, [(EVENT_ID, EVENT_VERSION, 0, EVENT_LEVEL, 0, 0, EVENT_KEYWORD)])
        self.assertEqual(api.enable_arguments, (99, EVENT_LEVEL, EVENT_KEYWORD))
        self.assertEqual(api.unregisters, [99])
        self.assertEqual(writer.handle.value, 0)

    def test_disabled_provider_cannot_be_mistaken_for_a_successful_event(self):
        api = FakeEtwApi()
        api.enabled = False
        with NativeEtwWriter(api) as writer, self.assertRaises(RuntimeError):
            writer.emit(encode_marker(1, 2, 3, "capture_begin"))
        self.assertEqual(api.payloads, [])
        self.assertEqual(api.unregisters, [99])

    def test_registration_failure_blocks_write(self):
        api = FakeEtwApi()
        api.registration_status = 5
        with self.assertRaises(RuntimeError):
            with NativeEtwWriter(api):
                self.fail("must not enter after failed registration")
        self.assertEqual(api.payloads, [])

    def test_write_failure_still_unregisters(self):
        api = FakeEtwApi()
        api.write_status = 8
        with self.assertRaises(RuntimeError):
            with NativeEtwWriter(api) as writer:
                writer.emit(encode_marker(1, 2, 3, "capture_begin"))
        self.assertEqual(api.unregisters, [99])

    def test_unregistered_and_arbitrary_payload_writes_rejected(self):
        writer = NativeEtwWriter(FakeEtwApi())
        with self.assertRaises(RuntimeError):
            writer.emit(encode_marker(1, 2, 3, "capture_begin"))
        with self.assertRaises(ValueError):
            writer.emit(b"secret")

    def test_nested_registration_rejected_and_original_handle_closed(self):
        api = FakeEtwApi()
        with NativeEtwWriter(api) as writer:
            with self.assertRaises(RuntimeError):
                writer.__enter__()
        self.assertEqual(api.unregisters, [99])

    def test_unregister_failure_recorded_without_masking_existing_failure(self):
        api = FakeEtwApi()
        api.unregister_status = 5
        with self.assertRaisesRegex(ValueError, "original"):
            with NativeEtwWriter(api) as writer:
                raise ValueError("original")
        self.assertEqual(writer.unregister_status, 5)
        with self.assertRaisesRegex(RuntimeError, "unregister"):
            with NativeEtwWriter(api):
                pass

    def test_bracket_uses_absolute_clocks_and_fixed_identities(self):
        rows, events = alignment_fixture()
        self.assertEqual([r["marker_index"] for r in rows], [1, 2])
        self.assertEqual(rows[0]["perf_after_ns"] - rows[0]["perf_before_ns"], 10_000)
        self.assertEqual(events[0]["process_id"], 123)

    def test_marker_rejected_inside_active_root(self):
        writer = Mock()
        markers = BracketedMarkers(writer)
        with self.assertRaises(RuntimeError):
            markers.mark("capture_begin", SimpleNamespace(active=True))
        writer.emit.assert_not_called()
        self.assertEqual(markers.rows, [])

    def test_failed_marker_not_added_to_successful_inventory(self):
        writer = Mock()
        writer.emit.side_effect = RuntimeError("failed")
        markers = BracketedMarkers(writer)
        with self.assertRaises(RuntimeError):
            markers.mark("capture_begin")
        self.assertEqual(markers.rows, [])

    def test_backward_marker_bracket_rejected(self):
        clocks = iter([200, 100])
        markers = BracketedMarkers(Mock(), clock=lambda: next(clocks))
        with self.assertRaises(RuntimeError):
            markers.mark("capture_begin")

    def test_alignment_intersects_all_quantization_bounds(self):
        rows, events = alignment_fixture()
        result = align_marker_clocks(rows, events)
        self.assertEqual(result["offset_low_ns"], 1_000_000_000)
        self.assertEqual(result["offset_high_ns"], 1_000_012_000)
        self.assertEqual(result["uncertainty_ns"], 12_000)
        self.assertFalse(result["os_cause_established"])

    def test_alignment_rejects_missing_duplicate_and_wrong_identity_events(self):
        for change in ("missing", "duplicate", "label", "thread", "provider", "id", "version", "keyword"):
            rows, events = alignment_fixture()
            if change == "missing":
                events.pop()
            elif change == "duplicate":
                events[1] = dict(events[0])
            else:
                key, value = {"label": ("label", "condition_end"), "thread": ("native_thread_id", 999),
                              "provider": ("provider_guid", "wrong"), "id": ("event_id", 2),
                              "version": ("event_version", 2), "keyword": ("keyword", 2)}[change]
                events[1][key] = value
            with self.subTest(change=change), self.assertRaises(ValueError):
                align_marker_clocks(rows, events)

    def test_alignment_rejects_inconsistent_offsets_and_backward_time(self):
        for time_value in (1, 9999, True):
            rows, events = alignment_fixture()
            events[1]["etw_timestamp_us"] = time_value
            with self.subTest(time_value=time_value), self.assertRaises(ValueError):
                align_marker_clocks(rows, events)

    def test_alignment_rejects_wide_brackets_instead_of_fitting_them_away(self):
        rows, events = alignment_fixture()
        for row in rows:
            row["perf_after_ns"] = row["perf_before_ns"] + 300_000
        rows[1]["perf_before_ns"] = rows[0]["perf_after_ns"]
        events[1]["etw_timestamp_us"] = 400
        with self.assertRaises(ValueError):
            align_marker_clocks(rows, events)

    def test_setup_review_uses_actual_marker_events_and_final_loss_metadata(self):
        result = inspect_setup_dump(iter(setup_fixture()))
        self.assertTrue(result["event_loss_validated"])
        self.assertFalse(result["latency_result"])
        self.assertFalse(result["model_clock_alignment_validated"])
        self.assertEqual(result["model_calls"], 0)

    def test_setup_marker_text_in_command_line_is_not_a_marker(self):
        lines = [line for line in setup_fixture() if not line.startswith("Mark, ") or "TimeStamp" in line]
        lines += ["P-Start, 120, powershell -marker PUF_SNN_WEEK6_SETUP_BEGIN\n",
                  "P-Start, 3120, powershell -marker PUF_SNN_WEEK6_SETUP_END\n"]
        with self.assertRaises(ValueError):
            inspect_setup_dump(lines)

    def test_setup_rejects_nonzero_or_absent_final_loss_counts(self):
        for change in ("missing", "events", "buffers"):
            lines = setup_fixture()
            lines = [line.replace("Events Lost: 0", "Events Lost: 1") if change == "events" else
                     line.replace("Buffers lost: 0", "Buffers lost: 1") if change == "buffers" else line
                     for line in lines if change != "missing" or not line.startswith("OS Version:")]
            with self.subTest(change=change), self.assertRaises(ValueError):
                inspect_setup_dump(lines)

    def test_setup_rejects_missing_schema_field_or_cpu_events(self):
        for change in ("schema", "field", "actual_events"):
            lines = setup_fixture()
            if change == "schema":
                lines = [line for line in lines if not line.startswith("CSwitch, TimeStamp")]
            elif change == "field":
                lines = [line.replace("Old TID", "Unsupported") for line in lines]
            else:
                lines = [line for line in lines if not line.startswith("CSwitch, 100")]
            with self.subTest(change=change), self.assertRaises(ValueError):
                inspect_setup_dump(lines)

    def test_setup_rejects_duplicate_or_backward_actual_markers(self):
        for change in ("duplicate", "backward"):
            lines = setup_fixture()
            if change == "duplicate":
                lines.append("Mark, 3300, PUF_SNN_WEEK6_SETUP_END\n")
            else:
                lines[-1] = "Mark, 100, PUF_SNN_WEEK6_SETUP_END\n"
            with self.subTest(change=change), self.assertRaises(ValueError):
                inspect_setup_dump(lines)

    def test_setup_keeps_decoder_warnings_without_exporting_private_strings(self):
        result = inspect_setup_dump(io.StringIO("".join(setup_fixture())),
                                    "warning: unsupported event\nprivate-file secret-process\nwarning: another\n")
        self.assertEqual(result["decoder_warning_count"], 2)
        self.assertFalse(result["all_event_versions_decoded"])
        self.assertNotIn("private-file", str(result))
        self.assertNotIn("secret-process", str(result))

    def test_profile_has_only_system_and_public_marker_providers(self):
        profile = ET.parse(Path(__file__).resolve().parents[1] / "configs/week6_windows_trace.wprp").getroot()
        providers = profile.findall("./Profiles/EventProvider")
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0].get("Name"), PROVIDER_GUID)
        self.assertEqual(providers[0].find("./Keywords/Keyword").get("Value"), "0x1")
        keywords = {k.get("Value") for k in profile.findall("./Profiles/SystemProvider/Keywords/Keyword")}
        self.assertTrue({"CSwitch", "ReadyThread", "SampledProfile", "DiskIO", "FileIO", "DPC", "Interrupt"} <= keywords)
        self.assertFalse(any("Heap" in key or "PMC" in key for key in keywords))
        self.assertEqual(profile.findall(".//HeapEventCollector"), [])
        self.assertEqual(profile.find("./Profiles/Profile").get("LoggingMode"), "File")


if __name__ == "__main__":
    unittest.main()
