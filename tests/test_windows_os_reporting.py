"""Synthetic public-export privacy/reconciliation checks; no private-file reads."""
import copy
import json
import unittest

from puf_snn.windows_os_accounting import Accounting, build_schedule
from puf_snn.windows_os_reporting import (MEAN_FIELDS, sanitize_root, sanitize_detail,
                                          reconcile_public, key)


def example(with_gap=False):
    trace = dict(condition="logistic_motion_logistic_anomaly", phase="measured",
        path="post_window_recurring", decision="accept", reason="accepted", attempt_index=0,
        clock_start_ns=100, clock_end_ns=200, elapsed_ns=100, thread_cpu_ns=80,
        gc_events=[dict(generation=0, start_ns=10, end_ns=20)], gc_spanning_trace_end=[],
        spans=[dict(id=0, parent_id=None, stage="post_window_recurring", start_ns=0, wall_ns=100, exception=False),
               dict(id=1, parent_id=0, stage="binary32_adapter", start_ns=10, wall_ns=40, exception=False)])
    events = [(100, "switch_in", 0, 0, 0), (200, "switch_out", 0, 4, 22)]
    if with_gap:
        events = [(100, "switch_in", 0, 0, 0), (120, "switch_out", 0, 2, 38),
                  (150, "switch_in", 0, 0, 0), (200, "switch_out", 0, 4, 22)]
    result = Accounting(build_schedule(events, []), {}, [], [], [], [110]).root(trace, stages=True)
    flags = ["group_p99_tail", "group_maximum"]
    identity = {field: trace[field] for field in ("condition", "phase", "path", "decision", "reason", "attempt_index")}
    root = {**identity, "retention_reasons": flags,
            **{field: value for field, value in result.items() if field not in ("observations", "nested_stage_observations")}}
    detail = dict(**identity, retention_reasons=flags, clock_start_ns=100, clock_end_ns=200, observations=result)
    return root, detail


def saved_group(root):
    values = {field: root[field] for field in ("condition", "phase", "path", "decision", "reason")}
    values.update(count=1, p50_ms=.0001, p95_ms=.0001, p99_ms=.0001, max_ms=.0001)
    values.update({field.removesuffix("_ns") + "_mean_ms": root[field]/1e6 for field in MEAN_FIELDS})
    values.update(paired_traced_minus_reference_p50_ms=-.0002,
                  paired_traced_minus_reference_p95_ms=.0003, tracing_overhead_isolated=False)
    return values


class WindowsOsReportingTests(unittest.TestCase):
    def test_valid_numeric_root_is_sanitized_without_mutation(self):
        root, detail = example()
        original = copy.deepcopy(root)
        public = sanitize_root(root, 1)
        self.assertEqual(public["elapsed_ns"], 100)
        self.assertEqual(public["logical_cpu_count_observed"], 1)
        self.assertNotIn("cpu_indices_observed", public)
        self.assertNotIn("clock_start_ns", public)
        self.assertEqual(root, original)

    def test_csv_representation_roundtrips_without_type_coercion(self):
        root, _ = example()
        encoded = {field: json.dumps(value) if isinstance(value, (list, dict)) else str(value) for field, value in root.items()}
        self.assertEqual(sanitize_root(root, 1), sanitize_root(encoded, 1))

    def test_added_sensitive_or_unknown_root_columns_fail(self):
        for field in ("process_id", "clock_start_ns", "filename", "raw_irp_address"):
            root, _ = example()
            root[field] = "DO_NOT_EXPORT"
            with self.subTest(field=field), self.assertRaises(ValueError):
                sanitize_root(root, 1)

    def test_unapproved_labels_fail(self):
        for field in ("condition", "phase", "path", "reason"):
            root, _ = example()
            root[field] = "PRIVATE_PROCESS_NAME"
            with self.subTest(field=field), self.assertRaises(ValueError):
                sanitize_root(root, 1)

    def test_exact_numeric_and_boolean_types_required(self):
        for field, value in (("elapsed_ns", True), ("elapsed_ns", 100.0),
                             ("elapsed_ns", "1e2"), ("off_cpu_ns", -1),
                             ("schedule_fully_covered", 1), ("complete_causal_attribution_established", True)):
            root, _ = example()
            root[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                sanitize_root(root, 1)

    def test_partition_and_overlay_mismatches_fail(self):
        for field, value in (("scheduled_other_ns", 0), ("off_cpu_ns", 1),
                             ("gc_wall_union_ns", 101), ("scheduled_interrupt_ns", 1),
                             ("gc_interrupt_overlap_ns", 1)):
            root, _ = example()
            root[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                sanitize_root(root, 1)

    def test_raw_unknown_state_reason_are_retained_without_guessed_semantics(self):
        root, _ = example(with_gap=True)
        public = sanitize_root(root, 1)
        self.assertEqual(public["raw_switchout_reason_offcpu_ns"], {"38": 30})
        self.assertEqual(public["off_state_unresolved_ns"], 30)
        self.assertNotIn("wait_mode", json.dumps(public))

    def test_bad_histogram_or_cpu_inventory_fails(self):
        for field, value in (("raw_switchout_state_offcpu_ns", {"filename": 0}),
                             ("raw_switchout_reason_offcpu_ns", {"256": 0}),
                             ("raw_switchout_reason_offcpu_ns", {"5": 1}),
                             ("cpu_indices_observed", [22]), ("cpu_indices_observed", [0, 0])):
            root, _ = example()
            root[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                sanitize_root(root, 1)

    def test_coarse_thread_cpu_timer_is_not_forced_to_equal_residency(self):
        root, _ = example()
        root["thread_cpu_ns"] = 200
        public = sanitize_root(root, 1)
        self.assertEqual(public["thread_cpu_ns"], 200)
        self.assertEqual(public["scheduled_residency_ns"], 100)

    def test_detail_excludes_raw_clocks_and_arbitrary_observation_text(self):
        root, detail = example()
        public_root = sanitize_root(root, 1)
        detail["observations"]["observations"] = ["PRIVATE_PATH_DO_NOT_COPY"]
        public = sanitize_detail(detail, {key(public_root): public_root})
        text = json.dumps(public)
        self.assertNotIn("clock_start_ns", text)
        self.assertNotIn("clock_end_ns", text)
        self.assertNotIn("PRIVATE_PATH_DO_NOT_COPY", text)
        self.assertEqual(public["nested_stage_observations"][0]["stage"], "binary32_adapter")

    def test_extra_detail_or_nested_fields_fail(self):
        root, detail = example()
        public_root = sanitize_root(root, 1)
        detail["raw_os_payload"] = "DO_NOT_COPY"
        with self.assertRaises(ValueError):
            sanitize_detail(detail, {key(public_root): public_root})
        _, detail = example()
        detail["observations"]["nested_stage_observations"][0]["symbol"] = "DO_NOT_COPY"
        with self.assertRaises(ValueError):
            sanitize_detail(detail, {key(public_root): public_root})

    def test_unknown_stage_or_mismatched_detail_duration_fails(self):
        root, detail = example()
        public_root = sanitize_root(root, 1)
        detail["observations"]["nested_stage_observations"][0]["stage"] = "UNRELATED_APP_NAME"
        with self.assertRaises(ValueError):
            sanitize_detail(detail, {key(public_root): public_root})
        _, detail = example()
        detail["clock_end_ns"] = 201
        with self.assertRaises(ValueError):
            sanitize_detail(detail, {key(public_root): public_root})

    def test_detail_accounting_must_match_root(self):
        root, detail = example()
        public_root = sanitize_root(root, 1)
        detail["observations"]["thread_cpu_ns"] = 81
        with self.assertRaises(ValueError):
            sanitize_detail(detail, {key(public_root): public_root})

    def test_retention_flags_whitelist_and_duplicates(self):
        for flags in (["upload_raw_trace"], ["group_maximum", "group_maximum"], [["bad"]]):
            root, _ = example()
            root["retention_reasons"] = flags
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                sanitize_root(root, 1)

    def test_groups_quantiles_counts_and_retained_singleton_reconcile(self):
        root, detail = example()
        clean = sanitize_root(root, 1)
        clean_detail = sanitize_detail(detail, {key(clean): clean})
        summary, groups, large = reconcile_public([clean], [clean_detail], [saved_group(clean)])
        self.assertEqual(summary["application_root_count"], 1)
        self.assertEqual(summary["retained_root_count"], 1)
        self.assertFalse(summary["tracing_overhead_isolated"])
        self.assertFalse(summary["complete_causal_attribution_established"])
        self.assertEqual(large, [])

    def test_missing_duplicate_details_or_omitted_groups_fail(self):
        root, detail = example()
        clean = sanitize_root(root, 1)
        clean_detail = sanitize_detail(detail, {key(clean): clean})
        for details, groups in (([], [saved_group(clean)]), ([clean_detail, clean_detail], [saved_group(clean)]), ([clean_detail], [])):
            with self.subTest(details=len(details), groups=len(groups)), self.assertRaises(ValueError):
                reconcile_public([clean], details, groups)

    def test_changed_quantile_or_false_overhead_claim_fails(self):
        root, detail = example()
        clean = sanitize_root(root, 1)
        clean_detail = sanitize_detail(detail, {key(clean): clean})
        for field, value in (("p95_ms", 1.0), ("count", True), ("tracing_overhead_isolated", True),
                             ("paired_traced_minus_reference_p95_ms", float("nan"))):
            group = saved_group(clean)
            group[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                reconcile_public([clean], [clean_detail], [group])

    def test_group_maximum_flag_cannot_be_omitted(self):
        root, detail = example()
        root["retention_reasons"] = ["group_p99_tail"]
        detail["retention_reasons"] = ["group_p99_tail"]
        clean = sanitize_root(root, 1)
        clean_detail = sanitize_detail(detail, {key(clean): clean})
        with self.assertRaises(ValueError):
            reconcile_public([clean], [clean_detail], [saved_group(clean)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
