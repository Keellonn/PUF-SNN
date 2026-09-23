from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/python"))

from scripts.validate_reconstruction import characterize


class ValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = characterize()

    def test_all_synthetic_attempts_are_retained(self):
        report = self.report
        self.assertEqual(report["attempt_count"], 707)
        self.assertEqual(len(report["attempts"]), 707)
        self.assertEqual(len({row["case_id"] for row in report["attempts"]}), 707)
        self.assertEqual(sum(row["attempts"] for row in report["summary"]), 707)
        for weight in range(6, 13):
            rows = [row for row in report["attempts"] if row["group"] == f"weight-{weight}"]
            self.assertEqual(len(rows), 100)
            self.assertEqual({row["response_hamming_distance63"] for row in rows}, {weight})

    def test_outcome_categories_remain_separate(self):
        outcomes = Counter(row["outcome"] for row in self.report["attempts"])
        self.assertEqual(set(outcomes),
                         {"decoder_failure", "invalid_format_or_padding", "candidate_valid_format"})
        evaluators = {row["evaluator_outcome"] for row in self.report["attempts"]}
        self.assertEqual(evaluators,
                         {"no_valid_candidate", "evaluator_correct_match", "evaluator_wrong_match"})
        for row in self.report["attempts"]:
            with self.subTest(case=row["case_id"]):
                if row["outcome"] == "decoder_failure":
                    self.assertEqual(row["reported_correction_count"], -1)
                    self.assertIsNone(row["candidate_message36"])
                    self.assertIsNone(row["credential_match"])
                elif row["outcome"] == "invalid_format_or_padding":
                    self.assertFalse(row["padding_valid"])
                    self.assertIsNone(row["candidate_credential_hex"])
                    self.assertTrue(row["miscorrection"])
                else:
                    self.assertTrue(row["padding_valid"])
                    self.assertEqual(row["credential_match"],
                                     row["candidate_credential_hex"] == row["enrolled_credential_hex"])

    def test_six_error_boundary_examples_are_preserved(self):
        rows = {row["case_id"]: row for row in self.report["attempts"]}
        valid = rows["six-errors-valid-padding"]
        self.assertEqual(valid["response_hamming_distance63"], 6)
        self.assertEqual(valid["reported_correction_count"], 5)
        self.assertEqual(valid["candidate_credential_hex"], "00000001")
        self.assertEqual(valid["evaluator_outcome"], "evaluator_wrong_match")
        self.assertEqual(rows["six-errors-invalid-padding"]["outcome"], "invalid_format_or_padding")
        self.assertEqual(rows["six-adjacent-errors"]["outcome"], "decoder_failure")

    def test_wrong_device_and_helper_controls_are_recorded_without_universal_rejection(self):
        rows = {row["case_id"]: row for row in self.report["attempts"] if row["group"] == "controls"}
        self.assertEqual(set(rows), {"wrong-helper", "wrong-device", "one-helper-bit-changed",
                                     "routing-label-changed"})
        for name in ("wrong-helper", "wrong-device"):
            row = rows[name]
            self.assertIn(row["evaluator_outcome"],
                          ("no_valid_candidate", "evaluator_correct_match", "evaluator_wrong_match"))
            if row["candidate_credential_hex"] is not None:
                self.assertEqual(row["credential_match"],
                                 row["candidate_credential_hex"] == row["enrolled_credential_hex"])
        self.assertEqual(rows["one-helper-bit-changed"]["reported_correction_count"], 1)
        self.assertTrue(rows["one-helper-bit-changed"]["credential_match"])
        self.assertTrue(rows["routing-label-changed"]["credential_match"])

    def test_non_timing_report_is_reproducible_and_json_serializable(self):
        self.assertEqual(characterize(samples_per_weight=2), characterize(samples_per_weight=2))
        encoded = json.dumps(self.report)
        self.assertEqual(json.loads(encoded)["attempt_count"], 707)
        self.assertTrue(self.report["source_sha256"])
        self.assertEqual(self.report["packages"]["galois"], "0.4.11")

    def test_invalid_diagnostic_settings_rejected(self):
        for args in ({"seed": -1}, {"seed": True}, {"samples_per_weight": 0},
                     {"samples_per_weight": True}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                characterize(**args)

    def test_cli_refuses_to_overwrite_existing_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "existing.json"
            output.write_text("existing evidence", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "src/python/scripts/validate_reconstruction.py"),
                 "--output", str(output)], capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Output already exists", result.stderr)
            self.assertEqual(output.read_text(), "existing evidence")


if __name__ == "__main__":
    unittest.main()
