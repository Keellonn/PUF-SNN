"""Final-only acquisition adapter; no runner, reconstruction or evidence writer.

The caller validates the complete planning contract before passing a condition
and its noise identity here. Scheduled trial/attempt IDs remain with the caller:
they must never replace the explicitly aliased measurement identity. This API
does not authorize scientific execution. Tests use isolated nonfinal identities.
"""

from dataclasses import dataclass
from typing import Literal

from puf_snn.puf import acquisition
from puf_snn.puf.device import Device
from puf_snn.reconstruction.bch import Bits
from . import correlated_noise_v1 as noise
from .shared_noise_final_plan_v1 import CONDITIONS, POLICIES

Policy = Literal["single-read-v1", "majority-3-v1", "stored-provisioned-v1"]


@dataclass(frozen=True)
class MeasurementSpec:
    """Narrow binding from a validated planned block, without schedule state.

    Use block.condition, AttemptIdentity(**block.noise_identity), and
    block.common_offset. The identity's phase prefix is caller-owned so isolated
    fixtures need no reserved identities. The condition's noise-domain suffix is
    checked, including the common-control alias to op:r000.
    """

    condition: str
    identity: noise.AttemptIdentity
    common_offset: float = 0.0

    def __post_init__(self) -> None:
        if type(self.identity) is not noise.AttemptIdentity:
            raise ValueError("validated AttemptIdentity required")
        profile = next((c for c in CONDITIONS if c[0] == self.condition), None)
        if type(self.condition) is not str or profile is None:
            raise ValueError("unknown final condition")
        if not self.identity.noise_domain_id.endswith(":" + profile[3]):
            raise ValueError("condition noise domain mismatch (common must alias op:r000)")
        # Reuse magnitude/type validation; the final profile is not tunable.
        _ = self.noise_config
        allowed = (-1, 1) if self.condition == "common_mode_op_rho000" else (0,)
        if self.common_offset not in allowed:
            raise ValueError("common_offset does not match the final condition")

    @property
    def noise_config(self) -> noise.NoiseConfig:
        _, sigma, rho, _ = next(c for c in CONDITIONS if c[0] == self.condition)
        return noise.NoiseConfig(noise.MODEL_VERSION, 128, sigma, rho, self.common_offset)


@dataclass(frozen=True)
class MeasurementResult:
    """Actual responses and completed acquisition operations, never truth labels.

    No reconstruction/decode occurs here. A future caller passes effective_response
    once to the existing reconstruct API. Stored-Provisioned has no PUF response;
    trusted credential retrieval remains outside this adapter.
    """

    spec: MeasurementSpec
    policy: Policy
    readings: tuple[Bits, ...]
    effective_response: Bits | None
    reading_count: int
    vote_count: int


def acquire_measurement(spec: MeasurementSpec, policy: Policy,
                        device: Device | None = None) -> MeasurementResult:
    """Perform one fresh S/M acquisition, or zero source operations for T.

    Exceptions propagate without an observation/result, retry or replacement read.
    Each call constructs a separate reader; responses are never cached or reused.
    """
    if type(spec) is not MeasurementSpec or type(policy) is not str or policy not in POLICIES:
        raise ValueError("MeasurementSpec and a supported final policy required")
    if policy == "stored-provisioned-v1":
        return MeasurementResult(spec, policy, (), None, 0, 0)
    config = acquisition.SINGLE_READ if policy == "single-read-v1" else acquisition.MAJORITY_3
    reader = noise.CorrelatedResponseReader(device, spec.noise_config, spec.identity, config)
    readings = []

    def read() -> Bits:
        response = reader()
        readings.append(response)
        return response

    effective = acquisition.acquire_response(read, config)
    if reader.measurement_count != config.read_count or len(readings) != config.read_count:
        raise RuntimeError("acquisition did not perform all required readings")
    return MeasurementResult(spec, policy, tuple(readings), effective,
                             reader.measurement_count, int(config == acquisition.MAJORITY_3))
