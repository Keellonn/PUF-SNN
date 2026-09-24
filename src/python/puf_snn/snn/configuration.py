"""
this file validates the SNN experiment settings and applies deterministic seeds
the same settings are used by training tests saved models and evaluation
"""

from __future__ import annotations

import json
import random

from pathlib import Path
from typing import Any

import numpy as np
import torch


EXPECTED_LABELS = (
    "nod",
    "shake",
    "look_left_return",
    "look_right_return",
    "still",
)

EXPECTED_CHANNELS = (
    "relative_position_x",
    "relative_position_y",
    "relative_position_z",
    "relative_orientation_x",
    "relative_orientation_y",
    "relative_orientation_z",
    "relative_orientation_w",
)


def _require_fields(value: dict[str, Any], required_fields: set[str], name: str) -> None:
    missing_fields = sorted(required_fields - set(value))

    if missing_fields:
        raise ValueError(f"{name} is missing required fields: {missing_fields}")


def load_snn_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    validate_snn_config(config)

    return config


def validate_snn_config(config: dict[str, Any]) -> None:
    _require_fields(config, {"experiment_name", "dataset", "model", "training", "evaluation", "output_directory"}, "SNN configuration")

    dataset = config["dataset"]
    model = config["model"]
    training = config["training"]
    evaluation = config["evaluation"]

    _require_fields(dataset, {"input_path", "labels", "splits", "time_steps", "input_channels", "channels", "normalization"}, "dataset configuration")
    _require_fields(model, {"type", "encoding", "hidden_neurons", "lif_beta", "lif_threshold", "surrogate_slope", "output_classes", "output_aggregation"}, "model configuration")
    _require_fields(training, {"device", "torch_threads", "loss", "optimizer", "learning_rate", "batch_size", "maximum_epochs", "gradient_clip_norm", "early_stopping_metric", "early_stopping_patience", "random_seeds"}, "training configuration")
    _require_fields(evaluation, {"metrics", "warmup_windows", "timed_windows", "timer", "latency_unit"}, "evaluation configuration")

    if tuple(dataset["labels"]) != EXPECTED_LABELS:
        raise ValueError("SNN labels must match the existing five-class task")

    if dataset["time_steps"] != 120 or dataset["input_channels"] != 7:
        raise ValueError("SNN input must contain 120 time steps and seven pose channels")

    if tuple(dataset["channels"]) != EXPECTED_CHANNELS:
        raise ValueError("SNN channel order does not match the authenticated classifier contract")

    if dataset["normalization"] != "training_split_per_channel":
        raise ValueError("SNN normalization must be fitted per channel from training data only")

    if model["type"] != "recurrent_lif" or model["encoding"] != "direct_continuous":
        raise ValueError("the first SNN baseline must use recurrent LIF neurons with direct continuous input")

    if model["hidden_neurons"] <= 0 or model["output_classes"] != len(EXPECTED_LABELS):
        raise ValueError("the SNN model size is invalid")

    if not 0.0 <= model["lif_beta"] < 1.0 or model["lif_threshold"] <= 0.0 or model["surrogate_slope"] <= 0.0:
        raise ValueError("the LIF beta threshold and surrogate slope are invalid")

    if training["device"] != "cpu":
        raise ValueError("the official laptop baseline must use the CPU")

    for field_name in ("torch_threads", "batch_size", "maximum_epochs", "early_stopping_patience"):
        if isinstance(training[field_name], bool) or not isinstance(training[field_name], int) or training[field_name] <= 0:
            raise ValueError(f"{field_name} must be a positive integer")

    if training["learning_rate"] <= 0.0 or training["gradient_clip_norm"] <= 0.0:
        raise ValueError("learning rate and gradient clip norm must be positive")

    random_seeds = training["random_seeds"]

    if not isinstance(random_seeds, list) or not random_seeds:
        raise ValueError("random_seeds must contain at least one seed")

    if any(isinstance(seed, bool) or not isinstance(seed, int) for seed in random_seeds):
        raise ValueError("every random seed must be an integer")

    if len(set(random_seeds)) != len(random_seeds):
        raise ValueError("random seeds must not contain duplicates")

    if evaluation["warmup_windows"] < 0 or evaluation["timed_windows"] <= 0:
        raise ValueError("evaluation timing counts are invalid")


def seed_everything(seed: int, torch_threads: int = 1) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")

    if isinstance(torch_threads, bool) or not isinstance(torch_threads, int) or torch_threads <= 0:
        raise ValueError("torch_threads must be a positive integer")

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(torch_threads)
    torch.use_deterministic_algorithms(True)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
