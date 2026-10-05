"""Current v2 reconstruction/admission flow and one composite model consumer.

This connector uses the existing owners' APIs; it is not another authenticator.
It performs one response acquisition and one reconstruction per isolated attempt.
It neither provisions enrollment records nor substitutes evaluator credentials.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from puf_snn.auth.binary_window import identifier
from puf_snn.auth.sender import Sender
from puf_snn.auth.session import Failure, REFUSAL
from puf_snn.auth.verifier import VerificationResult, Verifier
from puf_snn.integration import ExactlyOnceClassifierRelease, processed_record_to_wire_window
from puf_snn.reconstruction import reconstruct


class PipelineExecutionError(RuntimeError):
    """An implementation/acquisition error, never an ordinary FRR observation."""


@dataclass(frozen=True)
class SessionAttempt:
    decision: str
    stage: str
    reason: str
    reconstruction_outcome: str
    request_emitted: bool
    session_active: bool


@dataclass(frozen=True)
class ModelCallCounts:
    preprocessing: int = 0
    motion: int = 0
    anomaly: int = 0


@dataclass(frozen=True)
class InferenceOutput:
    # Arbitrary model returns are downstream data, not authentication decisions.
    motion: Any = field(repr=False)
    anomaly: Any = field(repr=False)


@dataclass(frozen=True)
class WindowOutcome:
    decision: str
    stage: str
    reason: str
    event_id: str | None = None
    sequence_number: int | None = None
    inference: InferenceOutput | None = field(default=None, repr=False)


class V2InferencePipeline:
    """Single-attempt, trusted co-located software integration connector.

    Pass fresh audited Sender/Verifier endpoints provisioned through the existing
    v2 admission service. ``prepare_inputs`` must derive BOTH inputs before either
    model runs and return ``(motion_input, anomaly_input)``. It receives only the
    record reconstructed from the exact verifier-minted accepted Window.

    Model callbacks may be frozen SNN/conventional inference functions. Unit-test
    spies are allowed, but their results are not classifier performance evidence.
    This object offers no retries, resynchronization or session-policy changes.
    """

    def __init__(
        self,
        sender: Sender,
        verifier: Verifier,
        prepare_inputs: Callable[[dict], tuple[Any, Any]],
        motion_model: Callable[[Any], Any],
        anomaly_model: Callable[[Any], Any],
    ) -> None:
        if type(sender) is not Sender or type(verifier) is not Verifier:
            raise ValueError("audited v2 Sender and Verifier endpoints are required")
        if not all(callable(value) for value in (prepare_inputs, motion_model, anomaly_model)):
            raise ValueError("preprocessing and both model callbacks must be callable")
        if (sender.state != "IDLE" or sender.kdf_timings_ns
                or verifier.kdf_timings_ns or verifier.active_session_ids):
            raise ValueError("fresh isolated endpoints are required")
        self.sender = sender
        self.verifier = verifier
        self._prepare = prepare_inputs
        self._motion = motion_model
        self._anomaly = anomaly_model
        self._attempted = False
        self._preprocessing_calls = self._motion_calls = self._anomaly_calls = 0
        self._gate = ExactlyOnceClassifierRelease(verifier, self._prepare_counted, self._consume)

    @property
    def calls(self) -> ModelCallCounts:
        return ModelCallCounts(self._preprocessing_calls, self._motion_calls, self._anomaly_calls)

    @property
    def consumed_event_ids(self) -> tuple[str, ...]:
        return self._gate.consumed_event_ids

    def _prepare_counted(self, record: dict) -> tuple[Any, Any]:
        self._preprocessing_calls += 1
        inputs = self._prepare(record)
        if type(inputs) is not tuple or len(inputs) != 2:
            raise ValueError("prepare_inputs must return a two-element tuple")
        return inputs

    def _consume(self, inputs: tuple[Any, Any]) -> InferenceOutput:
        motion_input, anomaly_input = inputs
        self._motion_calls += 1
        motion = self._motion(motion_input)
        self._anomaly_calls += 1
        anomaly = self._anomaly(anomaly_input)
        return InferenceOutput(motion, anomaly)

    def _failure(self, stage: str, failure: Failure, outcome: str, emitted: bool) -> SessionAttempt:
        if failure.reason == "internal_error" or self.sender.incomplete or self.verifier.incomplete:
            raise PipelineExecutionError(f"{stage}: internal_error; preserve incomplete evidence")
        return SessionAttempt("reject", stage, failure.reason, outcome, emitted, False)

    def establish(self, read_response: Callable[[], tuple[int, ...]], attempt_id: str,
                  *, local_provenance=None) -> SessionAttempt:
        """Acquire once, decode once, admit the exact candidate, then confirm.

        ``read_response`` supplies a fresh simulated read in the eventual study.
        The hook does not receive enrollment truth from this connector. Fixed or
        explicitly corrupted responses used in tests are only integration controls.
        Enrollment and endpoint construction happen BEFORE this method.
        """
        if not callable(read_response):
            raise ValueError("read_response must be callable")
        identifier(attempt_id)
        if self._attempted:
            raise ValueError("one attempt per pipeline; create fresh endpoints for another attempt")
        self._attempted = True
        try:
            noisy_response = read_response()
        except Exception:
            self.sender.record_reconstruction_exception(attempt_id, local_provenance=local_provenance)
            raise PipelineExecutionError("response_acquisition: internal_error; no retry") from None
        try:
            result = reconstruct(noisy_response, self.sender.enrollment.helper_data)
        except Exception:
            self.sender.record_reconstruction_exception(attempt_id, local_provenance=local_provenance)
            raise PipelineExecutionError("reconstruction: internal_error; no retry") from None
        request = self.sender.begin_attempt(result, attempt_id, local_provenance=local_provenance)
        if isinstance(request, Failure):
            stage = "reconstruction" if request.reason == "failed_reconstruction" else "credential_admission"
            return self._failure(stage, request, result.outcome, False)
        challenge = self.verifier.begin_session(request, local_provenance, admission=self.sender.admission)
        confirmation = self.sender.answer_challenge(challenge)
        if isinstance(confirmation, Failure):
            reason = self.verifier.last_reason if challenge == REFUSAL else confirmation.reason
            stage = "receiver_admission" if challenge == REFUSAL else "sender_confirmation"
            return self._failure(stage, Failure(reason), result.outcome, True)
        response = self.verifier.confirm_session(confirmation)
        active = self.sender.finish_session(response)
        if isinstance(active, Failure):
            reason = self.verifier.last_reason if response == REFUSAL else active.reason
            return self._failure("mutual_confirmation", Failure(reason), result.outcome, True)
        if (active is not self.sender or self.sender.session_id is None
                or self.sender.session_id not in self.verifier.active_session_ids):
            raise PipelineExecutionError("mutual_confirmation: incoherent activation")
        return SessionAttempt("accept", "active_session", "accepted", result.outcome, True, True)

    def release(self, result: VerificationResult) -> InferenceOutput:
        """At-most-once composite consumption, NOT guaranteed callback completion.

        Callback failures propagate through the existing verifier and leave the
        event consumed, sequence committed and evidence incomplete. No rollback.
        """
        return self._gate.deliver(result)

    def process_envelope(self, envelope: bytes, *, local_provenance=None) -> WindowOutcome:
        result = self.verifier.verify_window(envelope, local_provenance)
        if result.reason == "internal_error" or self.verifier.incomplete:
            raise PipelineExecutionError("window_verification: internal_error; preserve incomplete evidence")
        if result.result != "accept":
            return WindowOutcome("reject", "window_verification", result.reason,
                                 result.event_id, result.sequence_number)
        inferred = self.release(result)
        return WindowOutcome("accept", "inference", result.reason,
                             result.event_id, result.sequence_number, inferred)

    def process_record(self, source: dict, *, local_provenance=None) -> WindowOutcome:
        """Pre-tag adapter and normal sender quality checks stay separate.

        Adapter failures have no authenticated decision/event. A sender refusal
        means no tag was emitted, NOT a verifier rejection or anomaly detection.
        Source labels/splits/identity fields are never passed to the model callbacks.
        """
        try:
            window = processed_record_to_wire_window(source)
        except ValueError:
            return WindowOutcome("reject", "processed_record_adapter", "invalid_processed_record")
        packet = self.sender.seal_window(window, local_provenance=local_provenance)
        if isinstance(packet, Failure):
            if packet.reason == "internal_error" or self.sender.incomplete:
                raise PipelineExecutionError("sender_sealing: internal_error; preserve incomplete evidence")
            return WindowOutcome("reject", "sender_sealing", packet.reason)
        return self.process_envelope(packet, local_provenance=local_provenance)
