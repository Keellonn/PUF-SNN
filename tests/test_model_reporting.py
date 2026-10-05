"""Frozen metrics, seed-role, early-stopping and validation-only selection tests."""

from copy import deepcopy
import unittest

import numpy as np

from puf_snn import model_reporting as reporting


def metric(correct=9):
    matrix = np.eye(5, dtype=int) * 10
    matrix[0, 0], matrix[0, 4] = correct, 10 - correct
    return reporting.metrics_from_counts(matrix.tolist())


def config():
    return {"model": {"hidden_neurons": 64}, "training": {
        "maximum_epochs": 10, "early_stopping_patience": 2,
        "random_seeds": [7, 17, 27], "training_seeds": [107, 117, 127]}}


def history(scores=(.3, .4, .4, .35)):
    return [{"epoch": index, "training_loss": 1 / index,
             "validation_accuracy": score, "validation_macro_f1": score}
            for index, score in enumerate(scores, start=1)]


def run():
    return {"seed": 7, "training_seed": 107, "best_epoch": 2, "epochs_completed": 4,
            "trainable_parameters": 4933, "validation": {"macro_f1": .4}}


class ModelReportingTests(unittest.TestCase):
    def test_metrics_use_exact_counts(self):
        values = metric(9)
        self.assertEqual(values["sample_count"], 50)
        self.assertAlmostEqual(values["accuracy"], .98)
        self.assertAlmostEqual(values["per_class"]["nod"]["precision"], 1)
        self.assertAlmostEqual(values["per_class"]["nod"]["recall"], .9)
        self.assertAlmostEqual(values["per_class"]["nod"]["f1"], 18 / 19)

    def test_matrix_axis_order_is_true_then_predicted(self):
        values = metric(8)
        self.assertEqual(values["per_class"]["nod"]["support"], 10)
        self.assertAlmostEqual(values["per_class"]["still"]["precision"], 10 / 12)
        self.assertAlmostEqual(values["per_class"]["still"]["recall"], 1)

    def test_absent_class_metrics_are_zero_not_nan(self):
        matrix = np.zeros((5, 5), dtype=int)
        matrix[0, 0] = 1
        values = reporting.metrics_from_counts(matrix.tolist())
        self.assertEqual(values["macro_f1"], .2)
        self.assertEqual(values["per_class"]["still"]["f1"], 0)

    def test_bad_confusion_matrices_are_rejected(self):
        mixed_bool = np.eye(5, dtype=int).tolist()
        mixed_bool[0][0] = True
        for bad in (np.eye(4, dtype=int).tolist(), np.zeros((5, 5), dtype=int).tolist(),
                    np.full((5, 5), -1).tolist(), np.eye(5).tolist(), np.eye(5, dtype=bool).tolist(), mixed_bool):
            with self.subTest(matrix=bad):
                with self.assertRaises(ValueError):
                    reporting.metrics_from_counts(bad)

    def test_saved_metrics_are_reconciled(self):
        saved = metric()
        self.assertEqual(reporting.reconcile_metrics(saved), saved)

    def test_changed_accuracy_or_macro_f1_is_rejected(self):
        for field in ("accuracy", "macro_f1"):
            saved = metric()
            saved[field] += .1
            with self.assertRaises(ValueError):
                reporting.reconcile_metrics(saved)

    def test_changed_class_metric_or_support_is_rejected(self):
        for field in ("precision", "recall", "f1", "support"):
            saved = metric()
            saved["per_class"]["nod"][field] += 1
            with self.assertRaises(ValueError):
                reporting.reconcile_metrics(saved)

    def test_sample_count_and_class_set_must_match(self):
        for missing in (True, False):
            saved = metric()
            if missing:
                del saved["per_class"]["nod"]
            else:
                saved["sample_count"] += 1
            with self.assertRaises(ValueError):
                reporting.reconcile_metrics(saved)

    def test_nonfinite_saved_metric_is_rejected(self):
        saved = metric()
        saved["macro_f1"] = float("nan")
        with self.assertRaises(ValueError):
            reporting.reconcile_metrics(saved)

    def test_snn_parameter_counts_include_bias_and_recurrence(self):
        self.assertEqual(reporting.snn_parameter_count(64), 4933)
        self.assertEqual(reporting.snn_parameter_count(32), 1445)

    def test_no_new_architecture_is_permitted(self):
        for width in (True, 16, 128):
            with self.assertRaises(ValueError):
                reporting.snn_parameter_count(width)

    def test_early_stopping_reason_is_reconstructed(self):
        decision = reporting.training_decision(history(), config(), run())
        self.assertEqual(decision["selected_epoch"], 2)
        self.assertEqual(decision["stopping_epoch"], 4)
        self.assertEqual(decision["epochs_without_improvement"], 2)
        self.assertIn("2 consecutive epochs", decision["stopping_reason"])

    def test_maximum_epoch_stop_is_reported_separately(self):
        changed_config = config()
        changed_config["training"]["maximum_epochs"] = 3
        changed_run = run()
        changed_run.update(best_epoch=3, epochs_completed=3, validation={"macro_f1": .5})
        decision = reporting.training_decision(history((.3, .4, .5)), changed_config, changed_run)
        self.assertEqual(decision["stopping_reason"], "maximum epoch limit reached")

    def test_tied_validation_score_keeps_first_best_epoch(self):
        self.assertEqual(reporting.training_decision(history(), config(), run())["selected_epoch"], 2)

    def test_improvement_tolerance_matches_training_code(self):
        changed = history((.3, .4, .4 + 5e-13, .35))
        self.assertEqual(reporting.training_decision(changed, config(), run())["selected_epoch"], 2)

    def test_history_must_stop_when_patience_is_reached(self):
        changed_run = run()
        changed_run["epochs_completed"] = 5
        with self.assertRaises(ValueError):
            reporting.training_decision(history((.3, .4, .4, .35, .5)), config(), changed_run)

    def test_truncated_history_without_stopping_condition_is_rejected(self):
        changed_run = run()
        changed_run["epochs_completed"] = 3
        with self.assertRaises(ValueError):
            reporting.training_decision(history((.3, .4, .39)), config(), changed_run)

    def test_changed_selected_epoch_or_stopping_epoch_is_rejected(self):
        for field in ("best_epoch", "epochs_completed"):
            changed = run()
            changed[field] += 1
            with self.assertRaises(ValueError):
                reporting.training_decision(history(), config(), changed)

    def test_training_seed_pair_is_not_relabelled(self):
        changed = run()
        changed["training_seed"] = 7
        with self.assertRaises(ValueError):
            reporting.training_decision(history(), config(), changed)

    def test_parameter_count_must_match_configuration(self):
        changed = run()
        changed["trainable_parameters"] = 1445
        with self.assertRaises(ValueError):
            reporting.training_decision(history(), config(), changed)

    def test_selected_validation_score_must_match_history(self):
        changed = run()
        changed["validation"]["macro_f1"] = .8
        with self.assertRaises(ValueError):
            reporting.training_decision(history(), config(), changed)

    def test_missing_epoch_or_nonfinite_history_is_rejected(self):
        for field, value in (("epoch", 8), ("training_loss", float("nan")), ("validation_macro_f1", 1.1)):
            changed = history()
            changed[2][field] = value
            with self.assertRaises(ValueError):
                reporting.training_decision(changed, config(), run())

    def test_refit_confusion_counts_must_match_without_tuning(self):
        saved = metric()
        reporting.check_refit_counts(saved["confusion_matrix"], saved)
        with self.assertRaises(ValueError):
            reporting.check_refit_counts(metric(8)["confusion_matrix"], saved)

    def test_refit_tree_structure_must_match_not_just_accuracy(self):
        expected = {"trainable_parameters": None, "trees": 300, "nodes": 1000, "leaves": 650}
        reporting.validate_refit_complexity(expected, expected)
        changed = {**expected, "nodes": 1002}
        with self.assertRaises(ValueError):
            reporting.validate_refit_complexity(changed, expected)

    def test_selection_reads_validation_not_test(self):
        results = {32: {"per_seed": [{"validation": metric(10), "test": {"invalid": True}} for _ in range(3)]},
                   64: {"per_seed": [{"validation": metric(9), "test": {"better": 1}} for _ in range(3)]}}
        self.assertEqual(reporting.validation_selected_width(results), 32)

    def test_selection_retains_both_widths_and_all_three_seeds(self):
        results = {32: {"per_seed": [{"validation": metric()} for _ in range(3)]},
                   64: {"per_seed": [{"validation": metric()} for _ in range(2)]}}
        with self.assertRaises(ValueError):
            reporting.validation_selected_width(results)
        with self.assertRaises(ValueError):
            reporting.validation_selected_width({32: results[32]})

    def test_per_class_output_keeps_all_five_labels(self):
        rows = reporting.per_class_rows("snn_64", 7, "test", metric())
        self.assertEqual([row["class"] for row in rows], list(reporting.LABELS))
        self.assertTrue(all(row["model"] == "snn_64" and row["seed"] == 7 for row in rows))

    def test_reporting_does_not_mutate_saved_results(self):
        saved = metric()
        unchanged = deepcopy(saved)
        reporting.per_class_rows("random_forest", 7, "test", saved)
        self.assertEqual(saved, unchanged)


if __name__ == "__main__":
    unittest.main()
