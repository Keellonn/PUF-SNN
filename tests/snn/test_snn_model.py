"""This file checks the recurrent LIF model gradients outputs and evaluation."""

from __future__ import annotations

import unittest

import numpy as np
import torch

from puf_snn.snn.configuration import seed_everything
from puf_snn.snn.evaluation import calculate_metrics, measure_inference_latency
from puf_snn.snn.model import RecurrentLifClassifier


def create_test_model() -> RecurrentLifClassifier:
    return RecurrentLifClassifier(input_channels=7, hidden_neurons=16, output_classes=5, beta=0.9, threshold=1.0, surrogate_slope=25.0)


class SnnModelTests(unittest.TestCase):
    # one class score is returned for each window and each motion class
    def test_output_shape(self) -> None:
        seed_everything(7)
        model = create_test_model()
        output = model(torch.zeros((4, 120, 7), dtype=torch.float32))

        self.assertEqual(tuple(output.shape), (4, 5))
        self.assertTrue(torch.isfinite(output).all())

    # surrogate gradients allow the recurrent spiking layer to train
    def test_backward_pass_has_finite_gradients(self) -> None:
        seed_everything(7)
        model = create_test_model()
        sequences = torch.randn((3, 120, 7), dtype=torch.float32)
        labels = torch.tensor([0, 1, 2], dtype=torch.int64)
        loss = torch.nn.CrossEntropyLoss()(model(sequences), labels)
        loss.backward()

        gradients = [parameter.grad for parameter in model.parameters() if parameter.grad is not None]
        self.assertTrue(gradients)
        self.assertTrue(all(torch.isfinite(gradient).all() for gradient in gradients))

    # recreating the model with the same seed produces the same output
    def test_model_initialization_is_reproducible(self) -> None:
        sequences = torch.linspace(-1.0, 1.0, steps=2 * 120 * 7, dtype=torch.float32).reshape(2, 120, 7)
        seed_everything(17)
        first_model = create_test_model()
        first_output = first_model(sequences)
        seed_everything(17)
        second_model = create_test_model()
        second_output = second_model(sequences)

        torch.testing.assert_close(first_output, second_output, rtol=0.0, atol=0.0)

    # incorrect time or channel counts fail before inference
    def test_model_rejects_wrong_input_shape(self) -> None:
        model = create_test_model()

        with self.assertRaisesRegex(ValueError, r"\[batch, 120, 7\]"):
            model(torch.zeros((2, 119, 7)))

        with self.assertRaisesRegex(ValueError, r"\[batch, 120, 7\]"):
            model(torch.zeros((2, 120, 8)))

    # evaluation reports five-class metrics and one-window inference latency
    def test_evaluation_outputs(self) -> None:
        metrics = calculate_metrics(np.array([0, 1, 2, 3, 4]), np.array([0, 1, 2, 4, 4]))

        self.assertAlmostEqual(metrics["accuracy"], 0.8)
        self.assertEqual(np.asarray(metrics["confusion_matrix"]).shape, (5, 5))

        seed_everything(7)
        model = create_test_model()
        sequences = np.zeros((2, 120, 7), dtype=np.float32)
        latency = measure_inference_latency(model, sequences, warmup_windows=1, timed_windows=2, device=torch.device("cpu"))

        self.assertEqual(latency["timed_prediction_count"], 2)
        self.assertGreaterEqual(latency["p95_ms"], 0.0)


if __name__ == "__main__":
    unittest.main()
