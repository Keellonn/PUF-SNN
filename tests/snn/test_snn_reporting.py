"""these tests check the recorded seed roles model sizes and timing boundary"""

from copy import deepcopy
from pathlib import Path
import unittest

import numpy as np
import torch

from puf_snn.snn.configuration import load_snn_config, validate_snn_config
from puf_snn.snn.evaluation import measure_inference_latency
from puf_snn.snn.model import create_model

ROOT = Path(__file__).resolve().parents[2]


class SnnReportingTests(unittest.TestCase):
    def test_initialization_and_training_seeds_are_separate(self) -> None:
        config = load_snn_config(ROOT / "configs/snn_baseline.json")
        self.assertEqual(config["training"]["random_seeds"], [7, 17, 27])
        self.assertEqual(config["training"]["training_seeds"], [107, 117, 127])

    def test_shared_seed_role_is_rejected_when_explicit(self) -> None:
        config = load_snn_config(ROOT / "configs/snn_baseline.json")
        config["training"]["training_seeds"][0] = 7
        with self.assertRaises(ValueError):
            validate_snn_config(config)

    def test_model_parameter_counts(self) -> None:
        config = load_snn_config(ROOT / "configs/snn_baseline.json")

        for neurons, expected in ((64, 4933), (32, 1445)):
            settings = deepcopy(config["model"])
            settings["hidden_neurons"] = neurons
            model = create_model(settings)
            self.assertEqual(sum(parameter.numel() for parameter in model.parameters()), expected)

    def test_latency_identifies_its_exclusions_and_batch_size(self) -> None:
        config = load_snn_config(ROOT / "configs/snn_baseline.json")
        model = create_model(config["model"])
        result = measure_inference_latency(model, np.zeros((1, 120, 7), dtype=np.float32), 0, 1, torch.device("cpu"))
        self.assertEqual(result["batch_size"], 1)
        self.assertIn("tensor construction", result["scope"])


if __name__ == "__main__":
    unittest.main()
