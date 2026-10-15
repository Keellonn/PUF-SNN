"""Serial study-local observation of the real Authentication-v2 implementation."""
from contextlib import contextmanager, ExitStack
from dataclasses import asdict
from functools import wraps
from threading import Lock, get_ident
import time
from unittest.mock import patch

from puf_snn import pipeline_v2
from puf_snn.auth import sender as sender_module, verifier as verifier_module
from puf_snn.auth.binary_window import F32, Sample, Window
from puf_snn.auth.config import AuthConfig
from puf_snn.auth.credential_verifier import CredentialAdmissionService, CredentialVerifierStore
from puf_snn.auth.sender import Sender
from puf_snn.auth.session import Failure, REFUSAL, RegistryEntry, provision_device
from puf_snn.auth.verifier import Verifier
from puf_snn.puf import acquisition
from puf_snn.reconstruction import BCHCodec
from . import correlated_noise_v1 as noise
from .majority3_auth_v1 import VERSION, EVIDENCE_VERSION, POLICIES, attempt_id, object_digest, require, trial_noise_config

STAGES = ("establishment", "acquisition", "reading", "voting", "reconstruction", "bch_decode",
          "verification", "authorization", "admission_request", "mutual_handshake",
          "receiver_challenge", "sender_confirmation", "receiver_confirmation", "sender_activation",
          "sender_hkdf", "receiver_hkdf", "first_window", "window_seal", "window_verify", "release")
_SERIAL = Lock()


class Capture:
    """Inclusive spans plus parent links; exclusive durations are derived later."""
    def __init__(self, clock=None):
        self.clock = time.perf_counter_ns if clock is None else clock
        self.origin = self.clock()
        self.owner = get_ident()
        self.spans, self.stack = [], []
        self.handshake = None
        self.values = {}
        self.verifications, self.authorizations, self.handshake_outcomes = [], [], []
        self.authorization_diagnostics, self.window_verifications = [], []

    def open(self, stage):
        require(get_ident() == self.owner, "instrumentation requires owner-thread execution")
        require(stage in STAGES, "unknown timing stage")
        row = dict(id=len(self.spans), parent_id=self.stack[-1] if self.stack else None,
                   stage=stage, start_ns=self.clock()-self.origin, duration_ns=0, exception=False)
        self.spans.append(row)
        self.stack.append(row["id"])
        return row

    def close(self, row, exception=False):
        end = self.clock()-self.origin
        require(self.stack.pop() == row["id"], "timing stack mismatch")
        row.update(duration_ns=end-row["start_ns"], exception=exception)

    @contextmanager
    def span(self, stage):
        row = self.open(stage)
        try:
            yield
        except BaseException:
            self.close(row, True)
            raise
        else:
            self.close(row)

    def end_handshake(self, failed=False):
        if self.handshake is not None:
            self.close(self.handshake, failed)
            self.handshake = None

    def wrap(self, stage, function):
        @wraps(function)
        def measured(*args, **kwargs):
            require(get_ident() == self.owner, "instrumentation requires owner-thread execution")
            if stage == "receiver_challenge":
                require(self.handshake is None, "duplicate handshake")
                self.handshake = self.open("mutual_handshake")
            with self.span(stage):
                result = function(*args, **kwargs)
            # Capture returns unchanged. Secret-bearing objects stay in memory.
            if stage in ("acquisition", "reconstruction"):
                self.values[stage] = result
            elif stage == "verification":
                self.verifications.append(result.outcome)
            elif stage == "authorization":
                self.authorizations.append(result is not None)
                # Production authorize() deliberately swallows issuance exceptions.
                # In this serial, fresh enabled service there is no post-verification
                # policy refusal: verified + no handle is an infrastructure fault.
                # Explicit disabled/revoked verification is a distinct policy refusal.
                verified = self.verifications
                diagnostic = ("issued" if result is not None and verified == ["verified"] else
                              "credential_mismatch" if result is None and verified == ["credential_mismatch"] else
                              "policy_refusal" if result is None and verified == ["record_disabled"] else
                              "configuration_fault" if not verified or verified == ["record_missing"] else
                              "issuance_fault" if verified == ["verified"] else "verification_fault")
                self.authorization_diagnostics.append(diagnostic)
            elif stage == "window_verify":
                self.window_verifications.append(dict(decision=result.result, reason=result.reason,
                    sequence_number=result.sequence_number,
                    authenticated=result.accepted_window is not None and result.authenticated_bytes is not None))
            elif stage in ("receiver_challenge", "sender_confirmation", "receiver_confirmation", "sender_activation"):
                failed = isinstance(result, Failure) or result == REFUSAL
                reason = (result.reason if isinstance(result, Failure)
                          else args[0].last_reason if result == REFUSAL else "accepted")
                self.handshake_outcomes.append(dict(stage=stage, result="reject" if failed else "accept", reason=reason))
                if stage == "sender_activation" or stage == "sender_confirmation" and failed:
                    self.end_handshake()
            return result
        return measured


@contextmanager
def instrument(capture):
    """Global wrappers require exclusive, serial use; ExitStack always restores."""
    require(_SERIAL.acquire(blocking=False), "another study instrumentation scope is active")
    targets = (
        (pipeline_v2, "acquire_response", "acquisition"),
        (acquisition, "majority_vote3", "voting"),
        (pipeline_v2, "reconstruct", "reconstruction"),
        (BCHCodec, "decode", "bch_decode"),
        (CredentialAdmissionService, "verify", "verification"),
        (CredentialAdmissionService, "authorize", "authorization"),
        (Sender, "begin_attempt", "admission_request"),
        (Verifier, "begin_session", "receiver_challenge"),
        (Sender, "answer_challenge", "sender_confirmation"),
        (Verifier, "confirm_session", "receiver_confirmation"),
        (Sender, "finish_session", "sender_activation"),
        (sender_module, "derive_session_key", "sender_hkdf"),
        (verifier_module, "derive_session_key", "receiver_hkdf"),
        (Sender, "seal_window", "window_seal"),
        (Verifier, "verify_window", "window_verify"),
        (pipeline_v2.V2InferencePipeline, "release", "release"),
    )
    try:
        with ExitStack() as stack:
            for owner, name, stage in targets:
                stack.enter_context(patch.object(owner, name, capture.wrap(stage, getattr(owner, name))))
            yield
    finally:
        _SERIAL.release()


def fixed_window():
    """One public stationary legitimate 120-sample sequence-0 template."""
    zero, one = F32(0), F32(0x3f800000)
    samples = tuple(Sample(i, 1_000_000_000+i*16_666_667, (zero,)*3,
                           (zero, zero, zero, one), True) for i in range(120))
    return Window("unbound", bytes(16), 0, "week7-fixed-window-v1", 1_000_000_000,
                  3_000_000_000, 120, 1_000_000, samples)


class RecordingConsumer:
    """Release probe, explicitly not an SNN/anomaly accuracy evaluation."""
    def __init__(self):
        self.records = []

    def prepare(self, record):
        self.records.append((record["device_id"], record["sequence_number"]))
        return record, record

    @staticmethod
    def consume(record):
        return "recording-consumer-v1"


def fresh_pipeline(config, enrollment, policy):
    profile = AuthConfig.from_dict(config.to_dict()["authentication"]).session_config()
    service = CredentialAdmissionService(CredentialVerifierStore([enrollment.verifier_record]),
                                         enrollment.key_provider)
    entry = RegistryEntry(enrollment.device.device_id, enrollment.helper.enrollment_id, enrollment.credential)
    sender = Sender(provision_device(entry.device_id, entry.enrollment_id, enrollment.helper),
                    profile.limits, admission_service=service)
    verifier = Verifier([entry], profile, admission_service=service)
    consumer = RecordingConsumer()
    pipeline = pipeline_v2.V2InferencePipeline(sender, verifier, consumer.prepare,
                consumer.consume, consumer.consume, acquisition_config=POLICIES[policy])
    return pipeline, consumer


def errors(response, reference):
    return [i for i in range(63) if response[i] != reference[i]]


def execute_attempt(config, trial, policy, enrollment, *, run_id, source_id,
                    plan_sha256, execution_index):
    """One real attempt, no retries. Unexpected faults return incomplete evidence.

    Preparation, frozen shared Z, enrollment, endpoint allocation and window
    construction are outside establishment timing. Every actual E draw occurs
    inside the reading span. Truth classification occurs after the real path.
    """
    require(policy in POLICIES and trial["config_sha256"] == config.digest, "trial/config mismatch")
    require(enrollment.device.device_id == trial["device_id"]
            and enrollment.population_id == trial["population_id"]
            and enrollment.helper.enrollment_id == trial["enrollment_id"], "enrollment binding mismatch")
    identity = noise.AttemptIdentity(**trial["noise_identity"])
    reader = noise.CorrelatedResponseReader(enrollment.device, trial_noise_config(trial), identity, POLICIES[policy])
    pipeline, consumer = fresh_pipeline(config, enrollment, policy)
    window = fixed_window()
    policy_attempt_id = attempt_id(trial, policy)
    capture = Capture()
    reads = []
    session, window_result, fault = None, None, None
    activation_state = None

    def read():
        with capture.span("reading"):
            response = reader()
        # Raw observations are retained in memory; hashes/errors are computed
        # after establishment so per-read timing does not include those operations.
        reads.append(response)
        return response

    try:
        with instrument(capture):
            with capture.span("establishment"):
                try:
                    session = pipeline.establish(read, policy_attempt_id)
                finally:
                    capture.end_handshake(failed=session is None)
            activation_state = dict(sender_active=pipeline.sender.state == "ACTIVE",
                                    receiver_active=bool(pipeline.verifier.active_session_ids))
            if session.session_active:
                with capture.span("first_window"):
                    packet = pipeline.sender.seal_window(window)
                    if isinstance(packet, Failure):
                        window_result = dict(stage="sender_sealing", decision="reject", reason=packet.reason, sequence_number=None)
                    else:
                        result = pipeline.process_envelope(packet)
                        window_result = dict(stage="window_verification", decision=result.decision, reason=result.reason,
                                             sequence_number=result.sequence_number)
    except Exception:
        fault = "execution_fault"  # Do not serialize exception messages or objects.
    if pipeline.sender.incomplete or pipeline.verifier.incomplete:
        fault = "endpoint_evidence_incomplete"
    if any(v in ("internal_error", "key_unavailable", "invalid_input", "unsupported_record", "binding_mismatch")
           for v in capture.verifications):
        fault = "verification_execution_fault"
    if "record_missing" in capture.verifications:
        fault = "authorization_configuration_fault"
    for diagnostic in capture.authorization_diagnostics:
        if diagnostic.endswith("fault"):
            fault = "authorization_" + diagnostic
    if window_result is not None and window_result["reason"] == "internal_error":
        fault = "window_execution_fault"
    if fault is None and any(s["exception"] for s in capture.spans):
        fault = "instrumented_execution_fault"

    reconstruction = capture.values.get("reconstruction")
    classification = None
    if reconstruction is not None:
        if reconstruction.outcome == "decoder_failure":
            classification = "D"
        elif reconstruction.outcome == "invalid_format_or_padding":
            classification = "I"
        elif reconstruction.outcome == "candidate_valid_format":
            classification = "C" if reconstruction.candidate_credential == enrollment.credential else "W"
        else:
            fault = "unknown_reconstruction_outcome"
    effective = capture.values.get("acquisition")
    count = len(consumer.records)
    authorized = (session is not None and session.session_active and window_result is not None
                  and window_result["decision"] == "accept")
    unauthorized = count if not authorized else max(0, count-1)
    if unauthorized or authorized and count != 1:
        fault = "release_invariant"
    if fault is None and classification is None:
        fault = "missing_reconstruction"
    observations = [dict(index=i, response=list(r), response_sha256=object_digest(r),
                         error_positions=errors(r, enrollment.reference),
                         input_seed_sha256=trial["reading_seed_sha256"][i]) for i, r in enumerate(reads)]
    return dict(schema_version=EVIDENCE_VERSION + ":attempt", experiment_id=VERSION, run_id=run_id,
        source_id=source_id, config_sha256=config.digest, plan_sha256=plan_sha256,
        trial_id=trial["trial_id"], policy_attempt_id=policy_attempt_id,
        execution_index=execution_index, population_id=trial["population_id"], device_id=trial["device_id"],
        enrollment_id=trial["enrollment_id"], enrollment_sha256=object_digest(enrollment.public_record()),
        condition=trial["condition"], attempt_index=trial["attempt_index"], policy=policy,
        expected_reads=POLICIES[policy].read_count, actual_reads=reader.measurement_count,
        session_seed_sha256=trial["session_seed_sha256"], observations=observations,
        effective_response=list(effective) if effective is not None else None,
        effective_sha256=object_digest(effective) if effective is not None else None,
        effective_error_positions=errors(effective, enrollment.reference) if effective is not None else None,
        reconstruction=dict(outcome=reconstruction.outcome, decoder_status=reconstruction.decoder_status,
                            corrections=reconstruction.reported_correction_count, classification=classification)
                       if reconstruction is not None else None,
        verification_outcomes=capture.verifications, authorization_outcomes=capture.authorizations,
        authorization_diagnostics=capture.authorization_diagnostics,
        handshake=capture.handshake_outcomes, establishment=asdict(session) if session is not None else None,
        endpoint_state=activation_state or dict(sender_active=pipeline.sender.state == "ACTIVE",
                                               receiver_active=bool(pipeline.verifier.active_session_ids)),
        window=window_result, window_verifications=capture.window_verifications,
        release_count=count, authorized_release_count=count-unauthorized,
        unauthorized_release_count=unauthorized, model_calls=asdict(pipeline.calls),
        timing=capture.spans, execution_status="completed" if fault is None else "fault", fault_code=fault)
