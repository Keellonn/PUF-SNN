"""Synthetic interval and accounting regressions only. No saved-file access."""
import copy
import random
import unittest

from puf_snn.windows_os_accounting import (Accounting, IntervalIndex, RecordIndex, build_schedule,
                               duration, intersect, interval_union, pair_operations,
                               retention_reasons, trace_intervals, trace_key)


def trace(begin=100, end=200, **changes):
    row = dict(condition="demo", phase="measured", path="full", attempt_index=0,
               decision="accept", reason="accepted", clock_start_ns=begin, clock_end_ns=end,
               elapsed_ns=end-begin, thread_cpu_ns=80, gc_events=[], gc_spanning_trace_end=[],
               spans=[dict(id=0, parent_id=None, stage="full", start_ns=0,
                           wall_ns=end-begin, exception=False)])
    row.update(changes)
    return row


def schedule():
    return build_schedule([(100, "switch_in", 0, 0, 0), (130, "switch_out", 0, 5, 6),
                           (150, "switch_in", 1, 0, 0), (200, "switch_out", 1, 4, 22)], [140])


class IntervalTests(unittest.TestCase):
    def test_union_merges_nested_overlapping_adjacent_and_zero_intervals(self):
        self.assertEqual(interval_union([(5, 8), (0, 6), (1, 2), (8, 9), (10, 10)]), [(0, 9)])

    def test_invalid_intervals_fail(self):
        for item in ((3, 2), (-1, 2), (1.0, 2), (True, 2)):
            with self.subTest(item=item), self.assertRaises(ValueError):
                interval_union([item])

    def test_half_open_clipping(self):
        index = IntervalIndex([(0, 5), (10, 20)])
        self.assertEqual(index.clipped(5, 10), [])
        self.assertEqual(index.clipped(3, 14), [(3, 5), (10, 14)])

    def test_intersection_excludes_touching_boundaries(self):
        self.assertEqual(intersect([(0, 10)], [(10, 20)]), [])
        self.assertEqual(intersect([(0, 10), (20, 30)], [(5, 25)]), [(5, 10), (20, 25)])

    def test_record_index_preserves_cpu_metadata(self):
        index = RecordIndex([(0, 5, 0), (5, 10, 1)])
        self.assertEqual(index.clipped(3, 8), [(3, 5, 0), (5, 8, 1)])
        with self.assertRaises(ValueError):
            RecordIndex([(0, 8, 0), (4, 10, 1)])

    def test_randomized_interval_duration_matches_integer_grid_oracle(self):
        rng = random.Random(17)
        for _ in range(100):
            left = [(a := rng.randrange(50), a + rng.randrange(20)) for _ in range(20)]
            right = [(a := rng.randrange(50), a + rng.randrange(20)) for _ in range(20)]
            a = {t for start, end in left for t in range(start, end)}
            b = {t for start, end in right for t in range(start, end)}
            self.assertEqual(duration(interval_union(left)), len(a))
            self.assertEqual(duration(intersect(interval_union(left), interval_union(right))), len(a & b))


class ScheduleTests(unittest.TestCase):
    def test_switch_pairs_migrations_and_ready_tail(self):
        result = schedule()
        self.assertEqual(result.runs.rows, [(100, 130, 0), (150, 200, 1)])
        self.assertEqual(result.off_categories["off_not_yet_observed_ready"].rows, [(130, 140)])
        self.assertEqual(result.off_categories["off_ready_after_event"].rows, [(140, 150)])

    def test_initial_ready_state_does_not_double_count_later_ready_events(self):
        events = [(0, "switch_in", 0, 0, 0), (10, "switch_out", 0, 1, 32),
                  (30, "switch_in", 0, 0, 0), (40, "switch_out", 0, 4, 22)]
        result = build_schedule(events, [15, 20])
        self.assertEqual(result.off_categories["off_ready_at_switchout"].rows, [(10, 30)])
        self.assertFalse(result.off_categories["off_ready_after_event"].rows)

    def test_no_ready_event_preserves_unresolved_state(self):
        events = [(0, "switch_in", 0, 0, 0), (10, "switch_out", 0, 2, 38),
                  (30, "switch_in", 0, 0, 0), (40, "switch_out", 0, 4, 22)]
        result = build_schedule(events, [])
        self.assertEqual(result.off_categories["off_state_unresolved"].rows, [(10, 30)])
        self.assertEqual(result.gaps.rows, [(10, 30, 2, 38)])

    def test_same_tick_self_switch_is_ordered_out_then_in(self):
        result = build_schedule([(0, "switch_in", 0, 0, 0), (10, "switch_in", 0, 0, 0),
                                 (10, "switch_out", 0, 2, 33), (20, "switch_out", 0, 4, 22)], [])
        self.assertEqual(result.tied_out_in_pairs, 1)
        self.assertFalse(result.gaps.rows)
        self.assertEqual(duration(interval_union((a, b) for a, b, _ in result.runs.rows)), 20)

    def test_unpaired_duplicate_cpu_mismatch_or_open_end_fails(self):
        cases = [[], [(0, "switch_out", 0, 5, 0)], [(0, "switch_in", 0, 0, 0)],
                 [(0, "switch_in", 0, 0, 0), (5, "switch_in", 0, 0, 0)],
                 [(0, "switch_in", 0, 0, 0), (5, "switch_out", 1, 5, 0)]]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                build_schedule(case, [])


class OperationTests(unittest.TestCase):
    def test_tokens_pair_without_inferring_blocked_time(self):
        rows = pair_operations([(100, "file_read_begin", 1, 4096), (150, "file_end", 1, 0)])
        self.assertEqual(rows[0]["end_ns"] - rows[0]["start_ns"], 50)
        self.assertNotIn("blocked_ns", rows[0])

    def test_zero_duration_operation_is_kept(self):
        rows = pair_operations([(100, "disk_read_begin", 1, 0), (100, "disk_end", 1, 4096)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["start_ns"], rows[0]["end_ns"])

    def test_unmatched_reused_wrong_family_or_invalid_token_fails(self):
        cases = [[(100, "file_end", 1, 0)], [(100, "file_read_begin", 1, 0)],
                 [(100, "file_read_begin", 1, 0), (101, "file_write_begin", 1, 0)],
                 [(100, "file_read_begin", 1, 0), (101, "disk_end", 1, 0)],
                 [(100, "file_read_begin", 0, 0)]]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                pair_operations(case)


class RootAccountingTests(unittest.TestCase):
    def accounting(self):
        return Accounting(schedule(), {0: {"dpc": [(115, 125), (150, 160)], "isr": [(120, 128)]},
                                       1: {"dpc": [(150, 155)]}},
                          [dict(start_ns=110, end_ns=160)], [dict(start_ns=170, end_ns=180)],
                          [(120, 140)], [99, 100, 129, 200])

    def test_union_masks_do_not_double_count_gc_or_interrupts(self):
        root = trace(gc_events=[dict(generation=2, start_ns=10, end_ns=60),
                                dict(generation=0, start_ns=15, end_ns=25)])
        row = self.accounting().root(root)
        self.assertEqual(row["elapsed_ns"], 100)
        self.assertEqual(row["scheduled_residency_ns"], 80)
        self.assertEqual(row["off_cpu_ns"], 20)
        self.assertEqual(row["scheduled_interrupt_ns"], 18)
        self.assertEqual(row["gc_wall_union_ns"], 50)
        self.assertEqual(row["scheduled_gc_without_interrupt_ns"], 12)
        self.assertEqual(row["scheduled_other_ns"], 50)
        self.assertEqual(row["gc_while_offcpu_ns"], 20)
        self.assertEqual(row["cpu_profile_sample_count"], 2)

    def test_only_same_cpu_interrupts_join_and_union_is_not_sum(self):
        row = self.accounting().root(trace())
        self.assertEqual(row["dpc_while_scheduled_ns"], 15)
        self.assertEqual(row["isr_while_scheduled_ns"], 8)
        self.assertEqual(row["scheduled_interrupt_ns"], 18)

    def test_io_and_faults_are_nonadditive_overlays(self):
        row = self.accounting().root(trace())
        self.assertEqual(row["file_operation_overlap_ns"], 50)
        self.assertEqual(row["file_operation_offcpu_overlap_ns"], 20)
        self.assertEqual(row["disk_operation_overlap_ns"], 10)
        self.assertEqual(row["hard_fault_interval_overlap_ns"], 20)
        self.assertEqual(row["hard_fault_offcpu_overlap_ns"], 10)
        self.assertFalse(row["complete_causal_attribution_established"])

    def test_missing_boundary_coverage_is_explicit_not_extrapolated(self):
        row = self.accounting().root(trace(begin=90, end=210))
        self.assertEqual(row["schedule_uncovered_ns"], 20)
        self.assertFalse(row["schedule_fully_covered"])

    def test_nested_spans_are_unioned_by_stage_not_added_across_stages(self):
        root = trace()
        root["spans"].extend([dict(id=1, parent_id=0, stage="outer", start_ns=10, wall_ns=60, exception=False),
                              dict(id=2, parent_id=1, stage="inner", start_ns=20, wall_ns=30, exception=False)])
        row = self.accounting().root(root, stages=True)
        spans = {item["stage"]: item for item in row["nested_stage_observations"]}
        self.assertEqual(spans["outer"]["wall_union_ns"], 60)
        self.assertEqual(spans["inner"]["wall_union_ns"], 30)
        self.assertEqual(spans["inner"]["off_cpu_ns"], 20)

    def test_root_and_input_gc_are_not_mutated(self):
        root = trace(gc_events=[dict(generation=0, start_ns=5, end_ns=20)])
        original = copy.deepcopy(root)
        self.accounting().root(root)
        self.assertEqual(root, original)

    def test_expected_caught_rejection_exception_is_preserved(self):
        root = trace(decision="reject", reason="data_quality_failure")
        root["spans"].append(dict(id=1, parent_id=0, stage="quality", start_ns=10,
                                  wall_ns=20, exception=True))
        row = self.accounting().root(root, stages=True)
        self.assertEqual(row["caught_nested_exception_count"], 1)
        self.assertEqual(row["nested_stage_observations"][0]["exception_span_count"], 1)
        root["spans"][0]["exception"] = True
        with self.assertRaises(ValueError):
            self.accounting().root(root)

    def test_gc_origin_offset_and_half_open_clipping(self):
        root = trace()
        root["spans"][0]["start_ns"] = 5
        root["gc_events"] = [dict(generation=0, start_ns=0, end_ns=15)]
        begin, end, gc, stages = trace_intervals(root)
        self.assertEqual(gc, [(100, 110)])

    def test_bad_gc_root_and_parent_bounds_fail(self):
        cases = [trace(clock_end_ns=199), trace(gc_spanning_trace_end=[2]),
                 trace(gc_events=[dict(generation=0, start_ns=20, end_ns=10)])]
        root = trace()
        root["spans"].append(dict(id=1, parent_id=0, stage="bad", start_ns=50, wall_ns=60, exception=False))
        cases.append(root)
        root = trace()
        root["spans"].append(dict(id=1, parent_id=1, stage="bad", start_ns=10, wall_ns=20, exception=False))
        cases.append(root)
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                trace_intervals(case)

    def test_p99_absolute_and_maximum_retention_overlap_not_duplicate(self):
        roots = [trace(end=100+value, attempt_index=i) for i, value in enumerate((1, 2, 2, 30_000_000, 110_000_000))]
        flags = retention_reasons(roots)
        self.assertEqual(len(flags), 5)
        self.assertEqual(len(flags[trace_key(roots[-1])]), 4)
        self.assertIn("above_20ms_diagnostic_cutoff_not_target_claim", flags[trace_key(roots[-2])])

    def test_tied_maxima_and_singletons_are_retained(self):
        roots = [trace(attempt_index=0), trace(attempt_index=1)]
        flags = retention_reasons(roots)
        self.assertTrue(all("group_maximum" in value for value in flags.values()))
        self.assertIn("group_maximum", retention_reasons([roots[0]])[trace_key(roots[0])])
        with self.assertRaises(ValueError):
            retention_reasons([roots[0], roots[0]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
