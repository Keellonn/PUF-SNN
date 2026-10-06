"""Saved-timing reporting checks; artificial fixtures are not timing evidence."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from puf_snn.pipeline_timing import ACCEPTED_PATHS, REJECTED_PATHS, CONDITIONS, reconcile_timing
from scripts import summarize_week6_timing as reporting


def trace(elapsed=10_000_000, *, condition="condition", phase="measured", path="post_window_recurring", index=0):
    accepted = path in ACCEPTED_PATHS
    row = {"condition": condition, "phase": phase, "path": path, "attempt_index": index,
           "decision": "accept" if accepted else "reject", "reason": "accepted" if accepted else "invalid_tag",
           "stage": "inference" if accepted else "authentication", "elapsed_ns": elapsed,
           "thread_cpu_ns": elapsed, "source_window_id": f"{phase}-{index}", "selected_bit_error_count": 1,
           "model_calls": {name: int(accepted) for name in ("preprocessing", "motion", "anomaly")},
           "spans": [{"id": 0, "parent_id": None, "stage": path, "start_ns": 100,
                      "wall_ns": elapsed, "thread_cpu_ns": elapsed, "exception": False}], "gc_events": []}
    if path == "fresh_to_first_window":
        row.update(read_count=1, admission={"decision": "accept", "reason": "accepted"})
    return row


def small_cohort():
    rows = []
    for condition, _, _ in CONDITIONS:
        for phase, index in (("condition_first_use", 0), ("warmup", 1), ("measured", 0)):
            for path in sorted(ACCEPTED_PATHS | REJECTED_PATHS):
                rows.append(trace(condition=condition, phase=phase, index=index, path=path))
    return rows


def input_fixture(directory):
    config = json.loads((Path(reporting.ROOT) / "configs/week6_timing.json").read_text(encoding="utf-8"))
    rows = small_cohort()
    reporting.write_json(directory / "config.json", config)
    for condition, _, _ in CONDITIONS:
        subset = [row for row in rows if row["condition"] == condition]
        (directory / f"timings-{condition}.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in subset), encoding="utf-8", newline="\n")
        (directory / f"outliers-{condition}.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in reporting.select_outliers(subset)), encoding="utf-8", newline="\n")
    reconciliation = reconcile_timing(rows, config["conditions"], measured=1, warmup=2)
    reporting.write_json(directory / "reconciliation.json", reconciliation)
    reporting.write_json(directory / "summary.json", reporting.summarize_traces(rows))
    manifest = {"source_commit": "TEST-NOT-BENCHMARK", "reconciliation": reconciliation,
                "outlier_count": len(reporting.select_outliers(rows)),
                "artifacts": {p.name: reporting.sha256(p) for p in directory.iterdir() if p.is_file()}}
    reporting.write_json(directory / "manifest.json", manifest)
    expected = reporting.sha256(directory / "manifest.json")
    reporting.write_json(directory / "COMPLETE", {"manifest_sha256": expected,
                         "fresh_attempt_count": reconciliation["fresh_attempt_count"], "trace_count": len(rows),
                         "outlier_count": manifest["outlier_count"]})
    return expected


class PipelineTimingReportingTests(unittest.TestCase):
    def test_gc_overlap_clips_to_actual_root_start_and_end(self):
        events = [dict(start_ns=0, end_ns=150), dict(start_ns=180, end_ns=300)]
        self.assertEqual(reporting.union_overlap_ns(events, 100, 200), 70)

    def test_duplicate_and_nested_gc_intervals_are_not_added(self):
        events = [dict(start_ns=110, end_ns=190), dict(start_ns=120, end_ns=140),
                  dict(start_ns=110, end_ns=190)]
        self.assertEqual(reporting.union_overlap_ns(events, 100, 200), 80)

    def test_disjoint_and_touching_gc_intervals(self):
        events = [dict(start_ns=120, end_ns=130), dict(start_ns=130, end_ns=140), dict(start_ns=160, end_ns=170)]
        self.assertEqual(reporting.union_overlap_ns(events, 100, 200), 30)

    def test_gc_outside_root_and_empty_intervals_do_not_count(self):
        events = [dict(start_ns=0, end_ns=50), dict(start_ns=300, end_ns=400)]
        self.assertEqual(reporting.union_overlap_ns(events, 100, 200), 0)
        self.assertEqual(reporting.union_overlap_ns([], 100, 100), 0)

    def test_invalid_or_boolean_gc_intervals_rejected(self):
        for event in (dict(start_ns=200, end_ns=100), dict(start_ns=True, end_ns=200)):
            with self.assertRaises(ValueError):
                reporting.union_overlap_ns([event], 100, 200)

    def test_trace_outer_span_and_elapsed_must_agree(self):
        row = trace()
        row["elapsed_ns"] += 1
        with self.assertRaises(ValueError):
            reporting.validate_span_tree(row)

    def test_child_span_cannot_escape_parent(self):
        row = trace()
        row["spans"].append(dict(id=1, parent_id=0, stage="child", start_ns=0,
                                  wall_ns=10, thread_cpu_ns=0, exception=False))
        with self.assertRaises(ValueError):
            reporting.validate_span_tree(row)

    def test_missing_parent_or_duplicate_span_rejected(self):
        for child in (dict(id=1, parent_id=9, exception=False), dict(id=0, parent_id=0, exception=False)):
            row = trace()
            row["spans"].append(dict(start_ns=100, wall_ns=10, thread_cpu_ns=0, stage="child", **child))
            with self.assertRaises(ValueError):
                reporting.validate_span_tree(row)

    def test_caught_parser_or_quality_exception_is_a_completed_refusal(self):
        row = trace(path="malformed_json_receiver")
        row["spans"].append(dict(id=1, parent_id=0, stage="envelope_and_binary_parser", start_ns=100,
                                  wall_ns=1000, thread_cpu_ns=0, exception=True))
        reporting.validate_span_tree(row)
        detail = reporting.observation_row(row, row["elapsed_ns"], 20)
        self.assertEqual(detail["nested_exception_span_count"], 1)

    def test_uncaught_outer_exception_is_not_a_completed_observation(self):
        row = trace()
        row["spans"][0]["exception"] = True
        with self.assertRaises(ValueError):
            reporting.validate_span_tree(row)

    def test_cpu_exceeding_wall_is_not_silently_called_negative_delay(self):
        row = trace()
        row["thread_cpu_ns"] *= 2
        row["spans"][0]["thread_cpu_ns"] = row["thread_cpu_ns"]
        detail = reporting.observation_row(row, row["elapsed_ns"], 20)
        self.assertEqual(detail["wall_minus_thread_cpu_ms"], 0)
        self.assertIn("unresolved", detail["attribution"])

    def test_generation_two_overlap_is_subset_not_added_to_total(self):
        row = trace(elapsed=1000)
        row["gc_events"] = [dict(generation=2, start_ns=200, end_ns=600),
                            dict(generation=0, start_ns=300, end_ns=400)]
        detail = reporting.observation_row(row, 1000, 20)
        self.assertEqual(detail["gc_overlap_ms"], .0004)
        self.assertEqual(detail["generation2_overlap_ms"], .0004)

    def test_operational_threshold_is_strictly_greater_than_twenty(self):
        exact = reporting.observation_row(trace(20_000_000), 30_000_000, 20)
        larger = reporting.observation_row(trace(20_000_001), 30_000_000, 20)
        self.assertFalse(exact["absolute_threshold_exceeded"])
        self.assertTrue(larger["absolute_threshold_exceeded"])

    def test_fast_small_group_maximum_is_still_retained(self):
        diagnostics = reporting.analyze_traces([trace(1000)])
        self.assertEqual(len(diagnostics["outlier_details"]), 1)
        self.assertFalse(diagnostics["outlier_details"][0]["absolute_threshold_exceeded"])

    def test_absolute_and_tail_overlap_counts_are_not_summed(self):
        rows = [trace(30_000_000, index=0), trace(40_000_000, index=1)]
        summary = reporting.analyze_traces(rows)["outlier_summary"][0]
        self.assertEqual(summary["absolute_threshold_exceeded_count"], 2)
        self.assertEqual(summary["p99_tail_count"], 1)
        self.assertEqual(summary["retained_outlier_count"], 2)

    def test_phase_and_rejection_groups_remain_separate(self):
        rows = [trace(), trace(phase="condition_first_use"), trace(path="bad_tag_receiver")]
        diagnostics = reporting.analyze_traces(rows)
        self.assertEqual(len(diagnostics["group_maxima"]), 3)

    def test_empty_or_duplicate_evidence_is_rejected(self):
        for rows in ([], [trace(), trace()]):
            with self.assertRaises(ValueError):
                reporting.analyze_traces(rows)

    def test_target_only_applies_to_complete_measured_post_window_paths(self):
        summary = reporting.summarize_traces([trace(), trace(path="fresh_to_first_window"),
                    trace(path="valid_receiver_after_bad_tag"), trace(path="bad_tag_receiver"), trace(phase="warmup")])
        rows = reporting.complete_path_rows(summary)
        self.assertEqual(sum(row["target_applies"] for row in rows), 1)
        self.assertTrue(next(row for row in rows if row["target_applies"])["meets_provisional_p95_target"])
        self.assertTrue(all(row["meets_provisional_p95_target"] is None for row in rows if not row["target_applies"]))

    def test_first_post_window_is_measured_span_not_sum_of_percentiles(self):
        row = trace(path="fresh_to_first_window", elapsed=50_000_000)
        row["spans"].append(dict(id=1, parent_id=0, stage="first_post_window_total", start_ns=1000,
                                  wall_ns=30_000_000, thread_cpu_ns=0, exception=False))
        paths = reporting.complete_path_rows(reporting.summarize_traces([row]))
        first = next(r for r in paths if r["path"] == "first_post_window_total")
        self.assertEqual(first["p95_ms"], 30)
        self.assertFalse(first["meets_provisional_p95_target"])

    def test_scoped_paths_reject_parent_or_absolute_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            for relative in ("../outside", str(Path(temporary).resolve()), "."):
                with self.assertRaises(ValueError):
                    reporting.scoped_path(Path(temporary), relative)

    def test_completed_input_hashes_and_saved_metrics_reconcile(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            expected = input_fixture(directory)
            with patch.object(reporting, "reconcile_timing", side_effect=lambda rows, conditions:
                              reconcile_timing(rows, conditions, measured=1, warmup=2)):
                _, _, traces, outliers, _, checked = reporting.read_checked_inputs(directory, expected)
            self.assertEqual(len(traces), 144)
            self.assertEqual(len(outliers), 144)
            self.assertIn("COMPLETE", checked)

    def test_missing_or_modified_source_artifact_stops_analysis(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            expected = input_fixture(directory)
            reporting.write_json(directory / "summary.json", {"modified": True})
            with self.assertRaises(ValueError):
                reporting.read_checked_inputs(directory, expected)

    def test_completion_binding_and_incomplete_marker_rejected(self):
        for mutation in ("complete", "incomplete"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                expected = input_fixture(directory)
                if mutation == "complete":
                    reporting.write_json(directory / "COMPLETE", {"manifest_sha256": "0" * 64})
                else:
                    (directory / "INCOMPLETE").write_text("partial", encoding="utf-8")
                with self.assertRaises(ValueError):
                    reporting.read_checked_inputs(directory, expected)

    def test_artifact_writers_use_lf_and_refuse_empty_csv(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            reporting.write_json(directory / "result.json", {"n": 1})
            reporting.write_csv(directory / "result.csv", [dict(n=1, flag=True)])
            for path in directory.iterdir():
                self.assertNotIn(b"\r", path.read_bytes())
            with self.assertRaises(ValueError):
                reporting.write_csv(directory / "empty.csv", [])


if __name__ == "__main__":
    unittest.main()
