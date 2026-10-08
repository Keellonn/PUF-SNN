"""Synthetic reporting fixtures only; no authentication, models or recording."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from puf_snn import stage_accounting as accounting


def span(ordinal, parent, stage, start, elapsed):
    return dict(id=ordinal, parent_id=parent, stage=stage, start_ns=start,
                wall_ns=elapsed, thread_cpu_ns=0, exception=False)


def trace(path="post_window_recurring", phase="measured", decision="accept", index=0):
    row = dict(condition=accounting.CONDITIONS[0], phase=phase, path=path, decision=decision,
        reason="accepted" if decision == "accept" else "invalid_tag", attempt_index=index,
        device_id="sim-device-01", source_window_id=f"{phase}-source-{index}",
        source_split="test" if phase == "measured" else "validation", selected_bit_error_count=1,
        elapsed_ns=100, thread_cpu_ns=0,
        model_calls={name: int(decision == "accept") for name in ("preprocessing", "motion", "anomaly")},
        spans=[span(0, None, path, 0, 100)])
    if path == "fresh_to_first_window":
        row.update(read_count=1, stage="inference" if decision == "accept" else "reconstruction",
                   admission=dict(decision=decision, reason=row["reason"]))
        row["spans"].extend([span(1, 0, "admission_total", 0, 45),
                            span(2, 1, "reconstruction", 0, 40)])
        if decision == "accept":
            row["spans"].append(span(3, 0, "first_post_window_total", 50, 50))
    return row


def full_attempt(phase="measured", index=0):
    return [trace(path, phase, "reject" if path in accounting.REJECTED_PATHS else "accept", index)
            for path in sorted(accounting.ACCEPTED_PATHS | accounting.REJECTED_PATHS)]


def load_script():
    source = Path(__file__).resolve().parents[1] / "src/python/scripts/summarize_week6_stages.py"
    spec = importlib.util.spec_from_file_location("stage_report_script", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StageAccountingTests(unittest.TestCase):
    def test_nested_intervals_are_partitioned_not_double_counted(self):
        row = trace()
        row["spans"].extend([span(1, 0, "verifier_authentication_total", 10, 70),
            span(2, 1, "envelope_and_binary_parser", 12, 20),
            span(3, 1, "window_hmac_verification_calculation", 35, 5),
            span(4, 1, "verifier_quality_check", 42, 30),
            span(5, 0, "accepted_release_and_consumers", 80, 15),
            span(6, 5, "motion_consumer_including_normalization", 82, 10)])
        exclusive, inclusive, _ = accounting.partition_trace(row)
        self.assertEqual(sum(exclusive.values()), 100)
        self.assertEqual(exclusive["receiver_binding_sequence_state_unisolated"], 15)
        self.assertEqual(exclusive["outer_orchestration_unisolated"], 15)
        self.assertEqual(exclusive["release_conversion_unisolated"], 5)
        self.assertEqual(inclusive["verifier_authentication_total"], 70)
        self.assertGreater(sum(inclusive.values()), 100)

    def test_nested_credential_verification_is_not_counted_twice(self):
        row = trace()
        row["spans"].extend([span(1, 0, "sender_admission_and_request", 0, 90),
            span(2, 1, "local_authorization_including_verification", 10, 70),
            span(3, 2, "independent_credential_verification", 20, 50)])
        parts, _, _ = accounting.partition_trace(row)
        self.assertEqual(parts["credential_verification"], 50)
        self.assertEqual(parts["local_admission_checks"], 20)
        self.assertEqual(parts["session_establishment_unisolated"], 20)
        self.assertEqual(sum(parts.values()), 100)

    def test_repeated_audit_spans_sum_within_observation(self):
        row = trace()
        row["spans"].extend([span(1, 0, "sender_audit_record", 0, 15),
                            span(2, 0, "verifier_audit_record", 20, 25)])
        parts, _, counts = accounting.partition_trace(row)
        self.assertEqual(parts["in_memory_audit_measured"], 40)
        self.assertEqual(counts["in_memory_audit_measured"], 2)

    def test_child_outside_parent_rejected(self):
        row = trace()
        row["spans"].append(span(1, 0, "reconstruction", 90, 11))
        with self.assertRaisesRegex(ValueError, "outside"):
            accounting.partition_trace(row)

    def test_overlapping_siblings_rejected(self):
        row = trace()
        row["spans"].extend([span(1, 0, "binary32_adapter", 0, 60),
                            span(2, 0, "sender_seal_total", 50, 30)])
        with self.assertRaisesRegex(ValueError, "overlapping"):
            accounting.partition_trace(row)

    def test_touching_siblings_and_zero_length_are_valid(self):
        row = trace()
        row["spans"].extend([span(1, 0, "binary32_adapter", 0, 50),
                            span(2, 0, "sender_seal_total", 50, 50),
                            span(3, 0, "sender_audit_commit", 100, 0)])
        self.assertEqual(sum(accounting.partition_trace(row)[0].values()), 100)

    def test_unknown_stage_fails_instead_of_disappearing(self):
        row = trace()
        row["spans"].append(span(1, 0, "made_up_stage", 0, 10))
        with self.assertRaisesRegex(ValueError, "unregistered"):
            accounting.partition_trace(row)

    def test_bad_parent_duplicate_id_and_multiple_roots_rejected(self):
        for child in (span(1, 4, "binary32_adapter", 0, 10),
                      span(0, 0, "binary32_adapter", 0, 10),
                      span(1, None, "binary32_adapter", 0, 10)):
            with self.subTest(child=child), self.assertRaises(ValueError):
                row = trace()
                row["spans"].append(child)
                accounting.partition_trace(row)

    def test_boolean_negative_or_float_times_rejected(self):
        for value in (True, -1, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                row = trace()
                row["spans"][0]["start_ns"] = value
                accounting.partition_trace(row)

    def test_outer_time_disagreement_rejected(self):
        row = trace()
        row["elapsed_ns"] = 99
        with self.assertRaises(ValueError):
            accounting.partition_trace(row)

    def test_root_exception_rejected_but_nested_exception_retained(self):
        row = trace()
        row["spans"].append(span(1, 0, "envelope_and_binary_parser", 0, 50))
        row["spans"][1]["exception"] = True
        self.assertEqual(sum(accounting.partition_trace(row)[0].values()), 100)
        row["spans"][0]["exception"] = True
        with self.assertRaises(ValueError):
            accounting.partition_trace(row)

    def test_linear_quantiles_match_original_method(self):
        result = accounting.statistics([0, 1000000, 2000000])
        self.assertEqual(result, dict(count=3, p50_ms=1.0, p95_ms=1.9, p99_ms=1.98, max_ms=2.0))

    def test_empty_noninteger_or_negative_statistics_rejected(self):
        for values in ([], [True], [-1], [1.2]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                accounting.statistics(values)

    def test_stage_percentiles_are_not_summed_to_make_total(self):
        rows = []
        for index, a in enumerate((90, 10)):
            row = trace(index=index)
            row["spans"].extend([span(1, 0, "binary32_adapter", 0, a),
                                span(2, 0, "window_hmac_generation", a, 100-a)])
            rows.append(accounting.partition_trace(row)[0])
        combined_p95 = sum(accounting.statistics([parts[name] for parts in rows])["p95_ms"]
                           for name in ("binary32_adapter", "sender_window_hmac"))
        self.assertGreater(combined_p95, accounting.statistics([100, 100])["p95_ms"])

    def test_duplicate_observation_rejected(self):
        analyzer = accounting.SavedStageAnalysis()
        analyzer.add(trace())
        with self.assertRaisesRegex(ValueError, "duplicate"):
            analyzer.add(trace())

    def test_rejected_window_cannot_have_consumer_calls(self):
        row = trace("bad_tag_receiver", decision="reject")
        row["model_calls"]["motion"] = 1
        with self.assertRaisesRegex(ValueError, "consumer"):
            accounting.SavedStageAnalysis().add(row)

    def test_wrong_control_decision_and_bool_counter_rejected(self):
        for row in (trace("bad_tag_receiver"), trace()):
            if row["path"] == "post_window_recurring":
                row["model_calls"]["motion"] = True
            with self.assertRaises(ValueError):
                accounting.SavedStageAnalysis().add(row)

    def test_recurring_path_cannot_hide_new_reconstruction(self):
        row = trace()
        row["spans"].append(span(1, 0, "reconstruction", 0, 10))
        with self.assertRaisesRegex(ValueError, "must not include"):
            accounting.SavedStageAnalysis().add(row)

    def test_first_window_span_required_only_after_success(self):
        row = trace("fresh_to_first_window")
        row["spans"].pop()
        with self.assertRaisesRegex(ValueError, "first-window"):
            accounting.SavedStageAnalysis().add(row)

    def test_denominators_keep_refusals_separate_from_accepted_quantiles(self):
        analyzer = accounting.SavedStageAnalysis()
        for row in full_attempt("condition_first_use"):
            analyzer.add(row)
        rejected = trace("fresh_to_first_window", decision="reject")
        rejected["reason"] = rejected["admission"]["reason"] = "failed_reconstruction"
        analyzer.add(rejected)
        result = analyzer.finalize((accounting.CONDITIONS[0],), measured=1, warmup=1)
        self.assertEqual(result["reconciliation"]["fresh_attempt_count"], 2)
        self.assertEqual(result["reconciliation"]["trace_count"], 9)
        self.assertEqual(result["reconciliation"]["refused_by_condition_phase_reason"][0]["count"], 1)
        self.assertTrue(all(row["count"] == 1 for row in result["summary"]["root_paths"]))

    def test_missing_control_missing_admission_and_wrong_split_rejected(self):
        for kind in ("control", "admission", "split"):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                analyzer = accounting.SavedStageAnalysis()
                rows = full_attempt("condition_first_use") + full_attempt()
                if kind == "control":
                    rows = [row for row in rows if row["path"] != "exact_replay_receiver"]
                elif kind == "admission":
                    rows = [row for row in rows if row["path"] != "fresh_to_first_window"]
                else:
                    rows[0]["source_split"] = "test"
                for row in rows:
                    analyzer.add(row)
                analyzer.finalize((accounting.CONDITIONS[0],), measured=1, warmup=1)

    def test_changed_source_within_attempt_rejected(self):
        analyzer = accounting.SavedStageAnalysis()
        rows = full_attempt("condition_first_use") + full_attempt()
        rows[0]["source_window_id"] = "different"
        for row in rows:
            analyzer.add(row)
        with self.assertRaisesRegex(ValueError, "source/noise"):
            analyzer.finalize((accounting.CONDITIONS[0],), measured=1, warmup=1)

    def test_pairing_mismatch_across_conditions_rejected(self):
        attempts = {}
        for name in accounting.CONDITIONS[:2]:
            for phase in ("measured", "condition_first_use"):
                row = trace("fresh_to_first_window", phase, "reject")
                row["condition"] = name
                if name == accounting.CONDITIONS[1]:
                    row["selected_bit_error_count"] = 3
                attempts[(name, phase, 0)] = {"fresh_to_first_window": row}
        with self.assertRaisesRegex(ValueError, "paired"):
            accounting.reconcile_attempts(attempts, accounting.CONDITIONS[:2], measured=1, warmup=1)

    def test_boolean_response_read_count_rejected(self):
        attempts = {}
        for phase in ("measured", "condition_first_use"):
            row = trace("fresh_to_first_window", phase, "reject")
            row["read_count"] = True
            attempts[(accounting.CONDITIONS[0], phase, 0)] = {"fresh_to_first_window": row}
        with self.assertRaises(ValueError):
            accounting.reconcile_attempts(attempts, (accounting.CONDITIONS[0],), 1, 1)

    def test_fresh_admission_decision_mismatch_rejected(self):
        row = trace("fresh_to_first_window")
        row["admission"]["decision"] = "reject"
        with self.assertRaises(ValueError):
            accounting.SavedStageAnalysis().add(row)

    def test_artifact_paths_cannot_escape_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            for path in ("../outside", "C:/outside", "\\outside", "", ".", "x/../../z"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    accounting.scoped_path(temporary, path)

    def test_saved_file_tampering_and_incomplete_marker_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            evidence = directory / "evidence.json"
            evidence.write_text("{}\n", encoding="utf-8")
            manifest = directory / "manifest.json"
            manifest.write_text(json.dumps(dict(artifacts={"evidence.json": accounting.sha256(evidence)})), encoding="utf-8")
            expected = accounting.sha256(manifest)
            (directory / "COMPLETE").write_text(json.dumps(dict(manifest_sha256=expected)), encoding="utf-8")
            self.assertEqual(len(accounting.verify_completed_input(directory, expected)[2]), 3)
            evidence.write_text("{\"changed\":true}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                accounting.verify_completed_input(directory, expected)
            (directory / "INCOMPLETE").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "incomplete"):
                accounting.verify_completed_input(directory, expected)

    def test_wrong_pinned_manifest_or_completion_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            manifest = directory / "manifest.json"
            manifest.write_text('{"artifacts":{}}', encoding="utf-8")
            (directory / "COMPLETE").write_text('{"manifest_sha256":"bad"}', encoding="utf-8")
            with self.assertRaises(ValueError):
                accounting.verify_completed_input(directory)
            with self.assertRaisesRegex(ValueError, "completion"):
                accounting.verify_completed_input(directory, accounting.sha256(manifest))

    def test_reporting_has_no_model_or_authentication_imports(self):
        import ast
        for name in (accounting.__file__, Path(__file__).resolve().parents[1] / "src/python/scripts/summarize_week6_stages.py"):
            tree = ast.parse(Path(name).read_text(encoding="utf-8"))
            imported = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            imported += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
            self.assertFalse(any(name.startswith(("torch", "numpy", "joblib", "sklearn", "galois", "puf_snn.auth", "puf_snn.pipeline")) for name in imported))

    def test_new_output_must_not_overlap_input_or_overwrite(self):
        script = load_script()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "results/week-6/keegan/fresh-v2-timing"
            source.mkdir(parents=True)
            destination = root / "results/week-6/keegan/stage-accounting"
            self.assertEqual(script.checked_output_path(root, source, destination)[1], destination)
            for path in (source, source / "nested", source.parent, root / "outside"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    script.checked_output_path(root, source, path)
            destination.mkdir()
            with self.assertRaises(ValueError):
                script.checked_output_path(root, source, destination)

    def test_writers_preserve_lf_bytes_and_refuse_overwrite(self):
        script = load_script()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            script.write_json(directory / "result.json", dict(n=1))
            script.write_csv(directory / "result.csv", [dict(n=1)])
            for path in directory.iterdir():
                self.assertNotIn(b"\r", path.read_bytes())
            with self.assertRaises(FileExistsError):
                script.write_json(directory / "result.json", dict(n=2))
            with self.assertRaises(ValueError):
                script.write_csv(directory / "empty.csv", [])


if __name__ == "__main__":
    unittest.main()
