"""Protocol/accounting controls, using fixtures rather than saved model runs."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from puf_snn.quality_validation import (POLICIES, fingerprint, fixed_config, public_windows,
    reconcile, select_sources, source_hashes, validate_config)
from puf_snn.quality_dyadic import QUALITY_MODES
from puf_snn.snn.dataset import LABELS


def source_cohort():
    return [dict(window_id=f"{split}-{device}-{label}-{index}", split=split, device_id=f"device-{device}",
                 label=label, source_trial_id=f"{split}-{device}-{label}-{index}", session_id=f"{split}-{device}")
            for split in ("train", "validation", "test") for device in range(6) for label in LABELS for index in range(2)]


def cells():
    rows = []
    for mode in QUALITY_MODES:
        for policy in POLICIES:
            windows, count = [], 0
            for name, decision in (("bad_tag", "reject"), ("clean", "accept"), ("exact_replay", "reject"),
                                   ("pre_tag_position_jump_medium", "accept"), ("113_tracking_valid", "reject"),
                                   ("next_valid_after_refusals", "accept")):
                row = dict(condition=name, decision=decision,
                    calls_before=dict(preprocessing=count, motion=count, anomaly=count),
                    last_accepted_before=count - 1 if count else None)
                count += int(decision == "accept")
                row.update(calls_after=dict(preprocessing=count, motion=count, anomaly=count),
                           last_accepted_after=count - 1 if count else None)
                if decision == "accept":
                    row.update(motion_predictions={"fixture": "nod"}, anomaly_predictions={"fixture": dict(score=.1, flag=False)})
                windows.append(row)
            rows.append(dict(mode=mode, acquisition_policy=policy, configuration="fixture", source_window_id="source",
                read_count=1 if policy == POLICIES[0] else 3, admission=dict(decision="accept"),
                windows=windows, model_inputs=[dict(motion_sha256="a", anomaly_sha256="b")] * 3,
                consumer_calls=dict(preprocessing=3, motion=3, anomaly=3),
                final_state=dict(state="ACTIVE", accepted_count=3, last_accepted=2), consumed_events=3, incomplete=False))
    return rows


KEYS = {(policy, "fixture", "source") for policy in POLICIES}


class Week8QualityValidationTests(unittest.TestCase):
    def test_checked_in_protocol_matches_fixed_scope(self):
        root = Path(__file__).resolve().parents[1]
        validate_config(json.loads((root / "configs/week8_quality_validation.json").read_text(encoding="utf-8")))

    def test_model_mode_policy_source_and_experiment_changes_are_refused(self):
        for field, value in (("source_count", 600), ("training", True), ("threshold_selection", True),
                             ("latency_measurement", True), ("modes", []), ("acquisition_policies", [POLICIES[0]])):
            cfg = fixed_config()
            cfg[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_config(cfg)
        cfg = fixed_config()
        cfg["conditions"][0]["motion"] = "other"
        with self.assertRaises(ValueError):
            validate_config(cfg)

    def test_selection_is_validation_only_unique_balanced_and_order_independent(self):
        rows = source_cohort()
        selected = select_sources(rows)
        self.assertEqual(select_sources(rows[::-1]), selected)
        self.assertEqual(len(selected), 30)
        self.assertEqual({row["split"] for row in selected}, {"validation"})
        self.assertEqual(len({(row["device_id"], row["label"]) for row in selected}), 30)

    def test_source_trial_and_session_may_not_cross_splits(self):
        for field in ("source_trial_id", "session_id"):
            rows = source_cohort()
            validation = next(row for row in rows if row["split"] == "validation")
            validation[field] = rows[0][field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                select_sources(rows)

    def test_missing_class_duplicate_id_and_invalid_split_are_refused(self):
        for change in ("missing", "duplicate", "split"):
            rows = source_cohort()
            if change == "missing":
                rows = [row for row in rows if not (row["split"] == "validation" and row["device_id"] == "device-0" and row["label"] == LABELS[0])]
            elif change == "duplicate":
                rows.append(deepcopy(rows[0]))
            else:
                rows[0]["split"] = "unknown"
            with self.subTest(change=change), self.assertRaises(ValueError):
                select_sources(rows)

    def test_complete_paired_accounting_and_read_counts(self):
        summary = reconcile(cells(), KEYS)
        self.assertEqual(summary["admitted_sessions"], 4)
        self.assertEqual(summary["matched_quality_pairs"], 2)
        self.assertEqual(summary["response_reads"], 8)
        self.assertEqual(summary["accepted_windows"], 12)

    def test_missing_duplicate_or_unexpected_cells_are_refused(self):
        for change in ("missing", "duplicate", "unexpected", "mode"):
            rows = cells()
            if change == "missing":
                rows.pop()
            elif change == "duplicate":
                rows.append(deepcopy(rows[0]))
            elif change == "unexpected":
                rows[0]["source_window_id"] = "other"
            else:
                rows[0]["mode"] = "unknown"
            with self.subTest(change=change), self.assertRaises(ValueError):
                reconcile(rows, KEYS)

    def test_input_prediction_reason_and_state_disagreement_are_refused(self):
        for field in ("inputs", "prediction", "reason", "state", "reads", "calls", "control", "admission"):
            rows = cells()
            row = rows[-1]
            if field == "inputs": row["model_inputs"][0]["motion_sha256"] = "changed"
            elif field == "prediction": row["windows"][1]["motion_predictions"]["fixture"] = "still"
            elif field == "reason": row["windows"][0]["reason"] = "changed"
            elif field == "state": row["final_state"]["accepted_count"] = 2
            elif field == "reads": row["read_count"] = 1
            elif field == "calls": row["consumer_calls"]["motion"] = 4
            elif field == "control": row["windows"].pop()
            elif field == "admission": row["admission"]["decision"] = "reject"
            with self.subTest(field=field), self.assertRaises(ValueError):
                reconcile(rows, KEYS)

    def test_recovery_policy_cannot_silently_change_downstream_outputs(self):
        rows = cells()
        for row in rows:
            if row["acquisition_policy"] == POLICIES[1]:
                row["windows"][1]["motion_predictions"]["fixture"] = "still"
        with self.assertRaisesRegex(ValueError, "recovery-policy"):
            reconcile(rows, KEYS)

    def test_public_rows_exclude_fresh_event_ids_and_unapproved_fields(self):
        row = dict(condition="clean", decision="accept", event_id="fresh", key="not-exported", raw_packet="not-exported")
        self.assertEqual(public_windows([row]), [dict(condition="clean", decision="accept")])

    def test_rejected_control_model_calls_and_outputs_are_refused(self):
        for field in ("calls", "prediction", "sequence"):
            rows = cells()
            rejected = rows[0]["windows"][0]
            if field == "calls": rejected["calls_after"]["motion"] = 1
            elif field == "prediction": rejected["motion_predictions"] = {"fixture": "nod"}
            else: rejected["last_accepted_after"] = 0
            with self.subTest(field=field), self.assertRaises(ValueError):
                reconcile(rows, KEYS)

    def test_fingerprints_are_exact_and_reject_wrong_shapes_or_nonfinite_values(self):
        values = np.zeros((120, 7))
        before = fingerprint(values, (120, 7))
        values[1, 1] = 1e-20
        self.assertNotEqual(fingerprint(values, (120, 7)), before)
        with self.assertRaises(ValueError): fingerprint(values, (48,))
        values[0, 0] = np.nan
        with self.assertRaises(ValueError): fingerprint(values, (120, 7))

    def test_source_pins_include_uncommitted_files_but_not_results_or_log_hours(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("src/python/new.py", "tests/new.py", "configs/new.json", "pyproject.toml", "requirements.txt",
                         "docs/research-logs/keegan.md", "results/unrelated.json"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")
            observed = source_hashes(root)
            self.assertIn("src/python/new.py", observed)
            self.assertIn("tests/new.py", observed)
            self.assertNotIn("docs/research-logs/keegan.md", observed)
            self.assertNotIn("results/unrelated.json", observed)


if __name__ == "__main__":
    unittest.main()
