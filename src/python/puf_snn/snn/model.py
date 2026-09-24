"""
this file implements the recurrent leaky integrate and fire motion classifier
the hidden spikes use a surrogate gradient while outputs remain membrane scores
"""

from __future__ import annotations

import torch

from torch import nn


class SurrogateSpike(torch.autograd.Function):
    @staticmethod
    def forward(ctx, membrane_difference: torch.Tensor, slope: float) -> torch.Tensor:
        ctx.save_for_backward(membrane_difference)
        ctx.slope = slope

        return (membrane_difference >= 0.0).to(membrane_difference.dtype)

    @staticmethod
    def backward(ctx, output_gradient: torch.Tensor) -> tuple[torch.Tensor, None]:
        membrane_difference, = ctx.saved_tensors
        slope = ctx.slope
        surrogate_gradient = 1.0 / (1.0 + slope * membrane_difference.abs()).pow(2)

        return output_gradient * surrogate_gradient, None


def surrogate_spike(membrane_difference: torch.Tensor, slope: float) -> torch.Tensor:
    return SurrogateSpike.apply(membrane_difference, slope)


class RecurrentLifClassifier(nn.Module):
    def __init__(self, input_channels: int, hidden_neurons: int, output_classes: int, beta: float, threshold: float, surrogate_slope: float) -> None:
        super().__init__()

        if input_channels <= 0 or hidden_neurons <= 0 or output_classes <= 0:
            raise ValueError("model dimensions must be positive")

        if not 0.0 <= beta < 1.0 or threshold <= 0.0 or surrogate_slope <= 0.0:
            raise ValueError("LIF beta threshold and surrogate slope are invalid")

        self.input_channels = input_channels
        self.hidden_neurons = hidden_neurons
        self.output_classes = output_classes
        self.beta = beta
        self.threshold = threshold
        self.surrogate_slope = surrogate_slope
        self.input_layer = nn.Linear(input_channels, hidden_neurons)
        self.recurrent_layer = nn.Linear(hidden_neurons, hidden_neurons, bias=False)
        self.output_layer = nn.Linear(hidden_neurons, output_classes)

    def forward(self, sequences: torch.Tensor) -> torch.Tensor:
        if sequences.ndim != 3:
            raise ValueError("SNN input must have shape [batch, time, channels]")

        if sequences.shape[1] != 120 or sequences.shape[2] != self.input_channels:
            raise ValueError(f"SNN input must have shape [batch, 120, {self.input_channels}]")

        batch_size = sequences.shape[0]
        hidden_membrane = sequences.new_zeros((batch_size, self.hidden_neurons))
        hidden_spikes = sequences.new_zeros((batch_size, self.hidden_neurons))
        output_membrane = sequences.new_zeros((batch_size, self.output_classes))
        output_membrane_history = []

        for time_index in range(sequences.shape[1]):
            input_current = self.input_layer(sequences[:, time_index, :])
            recurrent_current = self.recurrent_layer(hidden_spikes)
            hidden_membrane = self.beta * hidden_membrane + input_current + recurrent_current
            hidden_spikes = surrogate_spike(hidden_membrane - self.threshold, self.surrogate_slope)
            hidden_membrane = hidden_membrane - hidden_spikes.detach() * self.threshold
            output_membrane = self.beta * output_membrane + self.output_layer(hidden_spikes)
            output_membrane_history.append(output_membrane)

        return torch.stack(output_membrane_history, dim=1).mean(dim=1)


def create_model(model_config: dict) -> RecurrentLifClassifier:
    return RecurrentLifClassifier(
        input_channels=7,
        hidden_neurons=model_config["hidden_neurons"],
        output_classes=model_config["output_classes"],
        beta=model_config["lif_beta"],
        threshold=model_config["lif_threshold"],
        surrogate_slope=model_config["surrogate_slope"],
    )
