"""Fake cohort callbacks and marker writers; no model workload or real ETW."""

from copy import deepcopy
import ctypes
import io
from itertools import count
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from puf_snn.windows_trace import decode_marker
from puf_snn.windows_trace_workload import (
    FIXED_CONFIG, MarkerJournal, ac_power_status, cohort_marker_bridge, private_worker_path,
    selected_job, validate_marker_coverage, validate_trace_config,
)


def job_fixture():
    return dict(block=0, mode="nested_stream_gc_on", condition_order=[
        dict(name=f"condition-{index}") for index in range(6)])


def coverage_fixture():
    job, markers, traces = job_fixture(), [], []
    contexts = [(condition["name"], cohort) for condition in job["condition_order"]
                for cohort in ("warmup", "measured")]
    labels = ["capture_begin", "inputs_verified"] + [
        label for _ in contexts for label in ("condition_begin", "condition_end")] + ["capture_end"]
    for index, label in enumerate(labels, 1):
        start = 1_000_000 + index * 1000
        row = dict(marker_index=index, process_id=77, native_thread_id=88, label=label,
                   perf_before_ns=start, perf_after_ns=start + 10, write_succeeded=True)
        if 3 <= index <= 26:
            row.update(condition=contexts[(index - 3) // 2][0], cohort=contexts[(index - 3) // 2][1])
        markers.append(row)
    for index, (condition, cohort) in enumerate(contexts):
        start = markers[2 + 2 * index]["perf_after_ns"] + 50
        traces.append(dict(condition=condition, phase=cohort, process_id=77, native_thread_id=88,
                           clock_start_ns=start, clock_end_ns=start + 100, elapsed_ns=100))
    return markers, traces, job


class FakeWriter:
    def __init__(self):
        self.payloads = []

    def emit(self, payload):
        self.payloads.append(decode_marker(payload))


class WorkloadTests(unittest.TestCase):
    def journal(self):
        writer, evidence = FakeWriter(), io.StringIO()
        ticks = count(1_000_000, 100)
        return MarkerJournal(writer, evidence, clock=lambda: next(ticks), pid=lambda: 77, tid=lambda: 88), writer, evidence

    def call_cohort(self, runner, condition, cohort, *, active=False):
        return runner.run_condition(None, condition, [None] * (30 if cohort == "warmup" else 60),
                                    None, "fixed", 0, SimpleNamespace(active=active), None, None, cohort)

    def test_fixed_design_rejects_tuning_unknown_keys_and_bool_block(self):
        validate_trace_config(deepcopy(FIXED_CONFIG))
        for changes in ({"block": 1}, {"block": False}, {"planned_attempts_per_worker": 20},
                        {"mode": "nested_stream_gc_deferred"}, {"new": 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_trace_config(dict(FIXED_CONFIG, **changes))

    def test_selected_original_job_is_only_block_zero_stream_gc_on(self):
        from puf_snn.outlier_experiment import MODE_ORDERS, build_jobs
        from scripts.run_week6_outlier_experiment import ROOT
        config = json.loads((ROOT / "configs/week6_outlier_experiment.json").read_text(encoding="utf-8"))
        selected = selected_job(config)
        self.assertEqual(selected["job_id"], "block-0-mode-1")
        self.assertEqual(selected["position"], MODE_ORDERS[0].index(1))
        self.assertIn(selected, build_jobs(config))

    def test_public_journal_context_only_and_sequential_payloads(self):
        markers, writer, evidence = self.journal()
        markers.mark("capture_begin")
        markers.mark("condition_begin", condition="fixed-condition", cohort="warmup")
        rows = [json.loads(line) for line in evidence.getvalue().splitlines()]
        self.assertEqual(rows[1]["cohort"], "warmup")
        self.assertEqual([row["marker_index"] for row in writer.payloads], [1, 2])
        self.assertNotIn("condition", writer.payloads[1])

    def test_active_timer_blocks_native_write_and_journal(self):
        markers, writer, evidence = self.journal()
        with self.assertRaises(RuntimeError):
            markers.mark("capture_begin", SimpleNamespace(active=True))
        self.assertEqual(writer.payloads, [])
        self.assertEqual(evidence.getvalue(), "")

    def test_bad_context_rejected_before_marker_write(self):
        markers, writer, _ = self.journal()
        with self.assertRaises(ValueError):
            markers.mark("condition_begin", condition="c", cohort="test")
        self.assertEqual(writer.payloads, [])

    def test_all_twelve_cohorts_use_original_callback_and_restore(self):
        calls = []
        def original(*args):
            calls.append((args[1]["name"], args[9]))
            return "original-result"
        runner, job = SimpleNamespace(run_condition=original), job_fixture()
        markers, writer, _ = self.journal()
        with cohort_marker_bridge(runner, markers, job):
            for condition in job["condition_order"]:
                for cohort in ("warmup", "measured"):
                    self.assertEqual(self.call_cohort(runner, condition, cohort), "original-result")
        self.assertIs(runner.run_condition, original)
        self.assertEqual(len(calls), 12)
        self.assertEqual(len(writer.payloads), 24)

    def test_reference_bridge_emits_no_etw_events(self):
        original = lambda *args: None
        runner, job = SimpleNamespace(run_condition=original), job_fixture()
        with cohort_marker_bridge(runner, None, job):
            for condition in job["condition_order"]:
                for cohort in ("warmup", "measured"):
                    self.call_cohort(runner, condition, cohort)
        self.assertIs(runner.run_condition, original)

    def test_error_restores_original_and_does_not_forge_end_marker(self):
        def original(*args):
            raise RuntimeError("fabricated workload failure")
        runner, job = SimpleNamespace(run_condition=original), job_fixture()
        markers, writer, _ = self.journal()
        with self.assertRaisesRegex(RuntimeError, "fabricated"), cohort_marker_bridge(runner, markers, job):
            self.call_cohort(runner, job["condition_order"][0], "warmup")
        self.assertIs(runner.run_condition, original)
        self.assertEqual([row["label"] for row in writer.payloads], ["condition_begin"])

    def test_missing_cohort_does_not_complete_bridge(self):
        original = lambda *args: None
        runner = SimpleNamespace(run_condition=original)
        with self.assertRaisesRegex(RuntimeError, "twelve"), cohort_marker_bridge(runner, None, job_fixture()):
            pass
        self.assertIs(runner.run_condition, original)

    def test_wrong_order_or_active_root_fails_and_restores(self):
        original = lambda *args: None
        for active, cohort in ((True, "warmup"), (False, "measured")):
            runner, job = SimpleNamespace(run_condition=original), job_fixture()
            with self.subTest(active=active, cohort=cohort):
                with self.assertRaises(RuntimeError), cohort_marker_bridge(runner, None, job):
                    self.call_cohort(runner, job["condition_order"][0], cohort, active=active)
                self.assertIs(runner.run_condition, original)

    def test_nested_bridge_rejected_without_mutating_original(self):
        original = lambda *args: None
        runner, job = SimpleNamespace(run_condition=original), job_fixture()
        with self.assertRaises(RuntimeError), cohort_marker_bridge(runner, None, job):
            with cohort_marker_bridge(runner, None, job):
                pass
        self.assertIs(runner.run_condition, original)

    def test_complete_root_coverage_does_not_claim_os_cause(self):
        markers, traces, job = coverage_fixture()
        result = validate_marker_coverage(markers, traces, job)
        self.assertEqual(result["marker_count"], 27)
        self.assertTrue(result["all_roots_within_markers"])
        self.assertFalse(result["os_cause_established"])

    def test_every_marker_context_and_root_identity_must_match(self):
        for mutation in ("context", "pid", "tid", "time", "elapsed", "phase"):
            markers, traces, job = coverage_fixture()
            if mutation == "context":
                markers[2]["condition"] = "wrong"
            else:
                field = {"pid": "process_id", "tid": "native_thread_id", "time": "clock_end_ns",
                         "elapsed": "elapsed_ns", "phase": "phase"}[mutation]
                traces[0][field] = "test" if mutation == "phase" else 9999999
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_marker_coverage(markers, traces, job)

    def test_missing_excess_or_reordered_marker_blocks_coverage(self):
        markers, traces, job = coverage_fixture()
        for changed in (markers[:-1], markers + [markers[-1]], list(reversed(markers))):
            with self.subTest(changed=len(changed)), self.assertRaises(ValueError):
                validate_marker_coverage(changed, traces, job)

    def test_missing_cohort_or_overlapping_roots_fail(self):
        markers, traces, job = coverage_fixture()
        for changed in (traces[1:], traces + [deepcopy(traces[0])]):
            with self.subTest(changed=len(changed)), self.assertRaises(ValueError):
                validate_marker_coverage(markers, changed, job)

    def test_first_use_maps_only_to_validation_warmup(self):
        markers, traces, job = coverage_fixture()
        traces[0]["phase"] = "condition_first_use"
        validate_marker_coverage(markers, traces, job)

    def test_power_requires_confirmed_ac_and_no_system_mutation(self):
        class FakePower:
            def __init__(self, ac, success=True):
                self.ac, self.success = ac, success
            def GetSystemPowerStatus(self, pointer):
                ctypes.memset(pointer, 0, 12)
                buffer = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_ubyte * 12)).contents
                buffer[0], buffer[2] = self.ac, 100
                return self.success
        self.assertTrue(ac_power_status(FakePower(1))["ac_online"])
        for fake in (FakePower(0), FakePower(255), FakePower(1, False)):
            with self.assertRaises(RuntimeError):
                ac_power_status(fake)

    def test_private_destination_scope_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            scope = Path(temporary).resolve() / "private-traces"
            parent = scope / ("week6-model-trace-" + "a" * 32)
            parent.mkdir(parents=True)
            repo = Path(temporary).resolve() / "repo"
            repo.mkdir()
            target = parent / "reference"
            self.assertEqual(private_worker_path(target, repo, scope), target)
            for bad in (parent / "other", repo / "traced", scope / "traced", Path("reference")):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    private_worker_path(bad, repo, scope)
            target.mkdir()
            with self.assertRaises(ValueError):
                private_worker_path(target, repo, scope)


if __name__ == "__main__":
    unittest.main()
