"""Computed selections and separate, explicitly recorded reviewer attestations."""
from datetime import datetime, timezone
from pathlib import Path

from . import shared_noise_calibration_v1 as study

BUNDLE_VERSION = study.VERSION+":bundle-v2"
SELECTION_VERSION = study.VERSION+":selection-v2"
ALGORITHM_VERSION = study.VERSION+":selection-algorithm-v1"
ACK_VERSION = study.VERSION+":acknowledgment-v1"
CORE_FILES = ("config.json", "trial-plan.json", "metadata.json", "source-manifest.json",
              "enrollments.json", "attempts.jsonl", "validation.json", "authorization-consumption.json")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def checked_timestamp(value, *, not_before=None):
    study.require(type(value) is str, "timestamp must be a string")
    timestamp = datetime.fromisoformat(value)
    study.require(timestamp.tzinfo is not None and timestamp <= datetime.now(timezone.utc), "dated timezone-aware nonfuture record required")
    if not_before is not None:
        lower = datetime.fromisoformat(not_before)
        study.require(lower.tzinfo is not None and timestamp >= lower, "record predates the computation/authorization it acknowledges")
    return timestamp


def computed_selection(directory, summary, metadata, *, computed_at):
    from . import shared_noise_calibration_evidence_v1 as evidence
    checked_timestamp(computed_at, not_before=metadata["approval"]["approved_at"] if metadata["approval"] else None)
    core = {name: evidence.file_digest(Path(directory)/name) for name in CORE_FILES}
    payload = dict(schema_version=SELECTION_VERSION, algorithm_version=ALGORITHM_VERSION,
        rules_version=study.RULES_VERSION, run_id=metadata["run_id"], source_id=metadata["source_id"],
        config_sha256=metadata["config_sha256"], plan_sha256=metadata["plan_sha256"],
        completed_evidence_sha256=study.object_digest(core), evidence_files=core,
        analysis_sha256=study.object_digest(summary["analysis"]),
        summary_sha256=evidence.file_digest(Path(directory)/"summary.json"),
        computation_timestamp=computed_at, computed_by=ALGORITHM_VERSION,
        candidates=summary["analysis"]["candidates"], result=summary["analysis"]["selection"],
        fixture_only=metadata["mode"] == "unit-test",
        acknowledgment_status="not-recorded-in-computational-receipt",
        certification="requires-certified-calibration-marker-and-separate-acknowledgment-for-planning")
    return dict(payload, selection_sha256=study.object_digest(payload))


def validate_computed_selection(directory, summary, metadata, selection):
    study.validate_schema("selection", selection)
    expected = computed_selection(directory, summary, metadata, computed_at=selection["computation_timestamp"])
    study.require(selection == expected, "computed selection/evidence/analysis/rules mismatch")


def acknowledgment_bindings(directory):
    from . import shared_noise_calibration_evidence_v1 as evidence
    directory = Path(directory)
    selection = evidence.read_json(directory/"selection.json")
    return dict(run_id=selection["run_id"], config_sha256=selection["config_sha256"],
        plan_sha256=selection["plan_sha256"], source_id=selection["source_id"], rules_version=selection["rules_version"],
        algorithm_version=selection["algorithm_version"], selection_sha256=selection["selection_sha256"],
        analysis_sha256=selection["analysis_sha256"], completed_evidence_sha256=selection["completed_evidence_sha256"],
        manifest_sha256=evidence.file_digest(directory/"manifest.json"),
        completion_marker_sha256=evidence.file_digest(directory/evidence.MARKER),
        selected_sigma=selection["result"]["selected_sigma"], result_status=selection["result"]["status"],
        fixture_only=selection["fixture_only"])


def validate_acknowledgment(directory, acknowledgment):
    from . import shared_noise_calibration_evidence_v1 as evidence
    study.validate_schema("acknowledgment", acknowledgment)
    binding = acknowledgment_bindings(directory)
    study.require(all(acknowledgment[k] == v for k, v in binding.items()), "selection acknowledgment binding mismatch")
    name = acknowledgment["acknowledged_by"]
    study.require(name.strip() and name == name.strip(), "named selection acknowledgment required")
    selection = evidence.read_json(Path(directory)/"selection.json")
    checked_timestamp(acknowledgment["acknowledged_at"], not_before=selection["computation_timestamp"])
    marker = evidence.read_json(Path(directory)/evidence.MARKER)
    checked_timestamp(acknowledgment["acknowledged_at"], not_before=marker["completed_at"])
    return binding


def record_acknowledgment(directory, acknowledgment, *, fixture_root=None):
    """Copy an explicitly supplied attestation outside immutable experimental evidence."""
    from . import shared_noise_calibration_evidence_v1 as evidence
    from . import shared_noise_calibration_authorization_v2 as auth
    evidence.audit_evidence(directory)
    config = study.StudyConfig.from_dict(evidence.read_json(Path(directory)/"config.json"))
    context = auth.context_for(config, fixture_root)
    validate_acknowledgment(directory, acknowledgment)
    root = auth.unlinked_namespace(context.acknowledgment_root/Path(directory).name)
    root.mkdir(parents=True, exist_ok=True)
    target = root/(acknowledgment["attestation_id"]+".json")
    evidence.write_json(target, acknowledgment)  # Exclusive, durable; never change bundle bytes.
    return target


def selection_status(directory, acknowledgment_file=None):
    from . import shared_noise_calibration_evidence_v1 as evidence
    evidence.audit_evidence(directory)
    selection = evidence.read_json(Path(directory)/"selection.json")
    acknowledged = acknowledgment_file is not None
    if acknowledged:
        acknowledgment = evidence.read_json(acknowledgment_file)
        validate_acknowledgment(directory, acknowledgment)
    qualifying = selection["result"]["status"] == "qualifying-operating-point"
    return dict(calibration_evidence="certified-complete", computational_selection="verified",
        acknowledgment="recorded-attestation" if acknowledged else "missing",
        result_status=selection["result"]["status"], selected_sigma=selection["result"]["selected_sigma"],
        fixture_only=selection["fixture_only"],
        eligible_for_final_planning=acknowledged and qualifying and not selection["fixture_only"],
        final_evaluation_enabled=False)


def require_acknowledged_selection(directory, acknowledgment_file=None):
    status = selection_status(directory, acknowledgment_file)
    study.require(status["eligible_for_final_planning"], "unacknowledged, nonqualifying or fixture selection cannot support final-study planning")
    return status
