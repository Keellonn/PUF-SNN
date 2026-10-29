"""Versioned observation adapter; unchanged noise and production protocol entry points."""
from dataclasses import asdict
from . import shared_noise_calibration_v1 as study
from . import correlated_noise_v1 as noise
from . import majority3_auth_runtime_v1 as previous
from .three_arm_auth_runtime_v1 import Capture, instrument, STAGES
from puf_snn.auth.session import Failure

def execute_attempt(config, trial, policy, enrollment, *, run_id, source_id,
                    plan_sha256, execution_index, permit=None):
    study.require(config.to_dict()["mode"] == "unit-test" or permit is not None, "supervised calibration permit required")
    if permit is not None:
        permit.check()
    study.require(policy in study.POLICIES and trial["config_sha256"] == config.digest, "trial/config mismatch")
    study.require(enrollment.device.device_id == trial["device_id"]
        and enrollment.population_id == trial["population_id"]
        and enrollment.helper.enrollment_id == trial["enrollment_id"], "enrollment binding mismatch")
    # Correlated shared-Z preparation and endpoints are outside measured roots.
    reader = noise.CorrelatedResponseReader(enrollment.device,
        study.trial_noise_config(trial), noise.AttemptIdentity(**trial["noise_identity"]),
        study.previous.POLICIES[policy])
    pipeline, consumer = previous.fresh_pipeline(config, enrollment, policy)
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
                    session = pipeline.establish(read, identity)
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
    classification = None
    if reconstruction is not None:
        classification = ("D" if reconstruction.outcome == "decoder_failure" else
                          "I" if reconstruction.outcome == "invalid_format_or_padding" else
                          "C" if reconstruction.candidate_credential == enrollment.credential else "W")
    if reconstruction is None:
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
        expected_reads=study.previous.POLICIES[policy].read_count,
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
        retrieval=None, verification_outcomes=capture.verifications, authorization_outcomes=capture.authorizations,
        authorization_diagnostics=capture.authorization_diagnostics, admission_outcomes=capture.admissions,
        handshake=capture.handshake_outcomes, establishment=asdict(session) if session else None,
        endpoint_state=activation or dict(sender_active=pipeline.sender.state == "ACTIVE",
                                         receiver_active=bool(pipeline.verifier.active_session_ids)),
        window=window_result, window_verifications=capture.window_verifications,
        release_count=count, authorized_release_count=int(accepted), unauthorized_release_count=max(0, count-int(accepted)),
        release_attempts=counts["release"], release_completions=sum(s["stage"] == "release" and not s["exception"] for s in capture.spans),
        callbacks=capture.callbacks, model_calls=asdict(pipeline.calls), timing=capture.spans,
        operation_counts=counts, stage_duration_ns=durations, execution_status="fault" if fault else "completed", fault_code=fault)
