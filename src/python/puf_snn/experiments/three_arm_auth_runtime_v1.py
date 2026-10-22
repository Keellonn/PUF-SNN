"""Source-aware observation of existing v2 entry points; no protocol changes."""
from contextlib import contextmanager, ExitStack
from dataclasses import asdict
from functools import wraps
from threading import get_ident
from unittest.mock import patch

from puf_snn import pipeline_v2
from puf_snn.auth import sender as sender_module, verifier as verifier_module
from puf_snn.auth.credential_verifier import CredentialAdmissionService
from puf_snn.auth.sender import Sender
from puf_snn.auth.session import Failure
from puf_snn.auth.verifier import Verifier
from puf_snn.puf import acquisition, ro_puf
from puf_snn.reconstruction import BCHCodec
from . import correlated_noise_v1 as noise
from . import majority3_auth_runtime_v1 as previous
from . import three_arm_auth_v1 as study

STAGES = (*previous.STAGES, "retrieval", "measurement")


class Capture(previous.Capture):
    def open(self, stage):
        if stage not in ("retrieval", "measurement"):
            return super().open(stage)
        study.require(get_ident() == self.owner, "instrumentation requires owner thread")
        row = dict(id=len(self.spans), parent_id=self.stack[-1] if self.stack else None,
                   stage=stage, start_ns=self.clock()-self.origin, duration_ns=0, exception=False)
        self.spans.append(row)
        self.stack.append(row["id"])
        return row

    def __init__(self, clock=None):
        super().__init__(clock)
        self.admissions = []
        self.callbacks = {name: dict(invocations=0, completions=0)
                          for name in ("preprocessing", "motion", "anomaly")}

    def wrap(self, stage, function):
        if stage != "authorization":
            return super().wrap(stage, function)

        @wraps(function)
        def measured(*args, **kwargs):
            with self.span(stage):
                result = function(*args, **kwargs)
            handle, verification, admission = result
            self.authorizations.append(handle is not None)
            self.admissions.append(admission)
            self.authorization_diagnostics.append(
                "issued" if handle is not None and verification == "verified" and admission == "authorized" else
                "credential_mismatch" if handle is None and verification == "credential_mismatch" and admission == "refused" else
                "policy_refusal" if handle is None and verification in ("verified", "record_disabled") and admission == "refused" else
                "issuance_fault")
            return result
        return measured

    def callback(self, name, function):
        def counted(*args, **kwargs):
            self.callbacks[name]["invocations"] += 1
            result = function(*args, **kwargs)
            self.callbacks[name]["completions"] += 1
            return result
        return counted


@contextmanager
def instrument(capture):
    # Share the historical lock so the two observation scopes cannot overlap.
    study.require(previous._SERIAL.acquire(blocking=False), "another instrumentation scope is active")
    targets = (
        (pipeline_v2, "acquire_response", "acquisition"),
        (noise, "calculate_frequencies", "measurement"),
        (ro_puf, "calculate_frequencies", "measurement"),
        (acquisition, "majority_vote3", "voting"),
        (pipeline_v2, "reconstruct", "reconstruction"), (BCHCodec, "decode", "bch_decode"),
        (CredentialAdmissionService, "verify", "verification"),
        # authorize() delegates here. Wrapping ONLY this entry avoids duplicates.
        (CredentialAdmissionService, "authorize_with_outcome", "authorization"),
        (Sender, "begin_attempt", "admission_request"),
        (Sender, "begin_stored_attempt", "admission_request"),
        (Verifier, "begin_session", "receiver_challenge"),
        (Sender, "answer_challenge", "sender_confirmation"),
        (Verifier, "confirm_session", "receiver_confirmation"),
        (Sender, "finish_session", "sender_activation"),
        (sender_module, "derive_session_key", "sender_hkdf"),
        (verifier_module, "derive_session_key", "receiver_hkdf"),
        (Sender, "seal_window", "window_seal"), (Verifier, "verify_window", "window_verify"),
        (pipeline_v2.V2InferencePipeline, "release", "release"),
    )
    try:
        with ExitStack() as stack:
            for owner, name, stage in targets:
                stack.enter_context(patch.object(owner, name, capture.wrap(stage, getattr(owner, name))))
            yield
    finally:
        previous._SERIAL.release()


class ObservedProvider:
    """Delegate a trusted provider without bypassing its binding checks."""
    def __init__(self, provider, capture):
        self.provider, self.capture = provider, capture

    def get_credential(self, **binding):
        with self.capture.span("retrieval"):
            return self.provider.get_credential(**binding)


def execute_attempt(config, trial, policy, enrollment, *, run_id, source_id,
                    plan_sha256, execution_index, provider=None):
    study.require(config.to_dict()["mode"] in ("unit-test", "nonformal"), "formal execution is disabled")
    study.require(policy in study.POLICIES and trial["config_sha256"] == config.digest, "trial/config mismatch")
    study.require(enrollment.device.device_id == trial["device_id"]
        and enrollment.population_id == trial["population_id"]
        and enrollment.helper.enrollment_id == trial["enrollment_id"], "enrollment binding mismatch")
    stored = policy == study.STORED
    study.require(provider is None or stored, "PUF cannot use stored provider")
    # All source provisioning, correlated shared-Z setup and endpoints excluded.
    provider = study.stored_provider(enrollment) if stored and provider is None else provider
    reader = None if stored else noise.CorrelatedResponseReader(enrollment.device,
        study.trial_noise_config(trial), noise.AttemptIdentity(**trial["noise_identity"]),
        study.previous.POLICIES[policy])
    pipeline, consumer = previous.fresh_pipeline(config, enrollment, "single-read-v1" if stored else policy)
    capture = Capture()
    pipeline._prepare = capture.callback("preprocessing", pipeline._prepare)
    pipeline._motion = capture.callback("motion", pipeline._motion)
    pipeline._anomaly = capture.callback("anomaly", pipeline._anomaly)
    window = previous.fixed_window()
    identity = study.attempt_id(trial, policy)
    reads = []
    session = window_result = activation = fault = None

    def read():
        with capture.span("reading"):
            response = reader()
        reads.append(response)
        return response

    try:
        with instrument(capture):
            with capture.span("establishment"):
                try:
                    session = (pipeline.establish_stored(ObservedProvider(provider, capture), identity)
                               if stored else pipeline.establish(read, identity))
                finally:
                    capture.end_handshake(failed=session is None)
            activation = dict(sender_active=pipeline.sender.state == "ACTIVE",
                              receiver_active=bool(pipeline.verifier.active_session_ids))
            if session.session_active:
                with capture.span("first_window"):
                    packet = pipeline.sender.seal_window(window)
                    if isinstance(packet, Failure):
                        window_result = dict(stage="sender_sealing", decision="reject", reason=packet.reason, sequence_number=None)
                    else:
                        result = pipeline.process_envelope(packet)
                        window_result = dict(stage="window_verification", decision=result.decision,
                                             reason=result.reason, sequence_number=result.sequence_number)
    except Exception:
        fault = "execution_fault"
    if pipeline.sender.incomplete or pipeline.verifier.incomplete:
        fault = "endpoint_evidence_incomplete"
    if any(v not in ("verified", "credential_mismatch", "record_disabled") for v in capture.verifications):
        fault = "verification_infrastructure_fault"
    if any(d.endswith("fault") for d in capture.authorization_diagnostics):
        fault = "admission_infrastructure_fault"
    if any(s["exception"] for s in capture.spans):
        fault = "instrumented_execution_fault"
    if window_result and window_result["reason"] == "internal_error":
        fault = "window_infrastructure_fault"
    reconstruction = capture.values.get("reconstruction")
    effective = capture.values.get("acquisition")
    status = asdict(pipeline.sender.stored_credential_status) if stored else None
    if stored and (status["attempt_id"] != identity or status["preparation_failure"] is not None):
        fault = "stored_invocation_binding_fault"
    classification = None
    if reconstruction is not None:
        classification = ("D" if reconstruction.outcome == "decoder_failure" else
                          "I" if reconstruction.outcome == "invalid_format_or_padding" else
                          "C" if reconstruction.candidate_credential == enrollment.credential else "W")
    if not stored and reconstruction is None:
        fault = "missing_reconstruction"
    count = len(consumer.records)
    accepted = bool(capture.window_verifications and capture.window_verifications[0]["decision"] == "accept")
    if count != int(accepted) or (accepted and not (session and session.session_active)):
        fault = "release_invariant"
    counts = {stage: sum(s["stage"] == stage for s in capture.spans) for stage in STAGES}
    durations = {stage: (sum(s["duration_ns"] for s in capture.spans if s["stage"] == stage)
                         if counts[stage] else None) for stage in STAGES}
    return dict(schema_version=study.EVIDENCE_VERSION+":attempt", experiment_id=study.VERSION,
        run_id=run_id, source_id=source_id, config_sha256=config.digest, plan_sha256=plan_sha256,
        trial_id=trial["trial_id"], policy_attempt_id=identity, execution_index=execution_index,
        population_id=trial["population_id"], device_id=trial["device_id"], enrollment_id=trial["enrollment_id"],
        enrollment_sha256=study.object_digest(enrollment.public_record()), condition=trial["condition"],
        attempt_index=trial["attempt_index"], policy=policy, credential_source=policy,
        expected_reads=0 if stored else study.previous.POLICIES[policy].read_count,
        actual_reads=counts["measurement"],
        noise_shared_seed_sha256=trial["noise_shared_seed_sha256"],
        observations=[dict(index=i, response=list(r), response_sha256=study.object_digest(r),
            error_positions=previous.errors(r, enrollment.reference), input_seed_sha256=trial["reading_seed_sha256"][i])
                      for i, r in enumerate(reads)],
        effective_response=list(effective) if effective is not None else None,
        effective_sha256=study.object_digest(effective) if effective is not None else None,
        effective_error_positions=previous.errors(effective, enrollment.reference) if effective is not None else None,
        reconstruction=dict(outcome=reconstruction.outcome, decoder_status=reconstruction.decoder_status,
            corrections=reconstruction.reported_correction_count, classification=classification) if reconstruction else None,
        retrieval=status, verification_outcomes=capture.verifications, authorization_outcomes=capture.authorizations,
        authorization_diagnostics=capture.authorization_diagnostics, admission_outcomes=capture.admissions,
        handshake=capture.handshake_outcomes, establishment=asdict(session) if session else None,
        endpoint_state=activation or dict(sender_active=pipeline.sender.state == "ACTIVE",
                                         receiver_active=bool(pipeline.verifier.active_session_ids)),
        window=window_result, window_verifications=capture.window_verifications,
        release_count=count, authorized_release_count=int(accepted), unauthorized_release_count=max(0, count-int(accepted)),
        release_attempts=counts["release"], release_completions=sum(s["stage"] == "release" and not s["exception"] for s in capture.spans),
        callbacks=capture.callbacks, model_calls=asdict(pipeline.calls), timing=capture.spans,
        operation_counts=counts, stage_duration_ns=durations, execution_status="fault" if fault else "completed", fault_code=fault)
