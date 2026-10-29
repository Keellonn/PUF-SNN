"""Run-bound local authorization and fail-closed, one-time consumption.

An exclusively created reservation directory is the tombstone. Missing/partial
receipts never make an ID reusable. These are local recorded authorizations,
not cryptographic signatures or protection against an administrator deleting state.
"""
from dataclasses import dataclass
from pathlib import Path
import re
import tempfile

from . import shared_noise_calibration_v1 as study
from .shared_noise_calibration_provenance_v2 import utc_now, checked_timestamp

AUTHORIZATION_ROOT = study.ROOT/"results/week-9/will/shared-noise-calibration-authorizations-v2"
SIDECAR_ROOT = study.ROOT/"tmp/week9-shared-noise-calibration-v1"
ACKNOWLEDGMENT_ROOT = study.ROOT/"results/week-9/will/shared-noise-calibration-acknowledgments-v1"
APPROVAL_VERSION = study.VERSION+":approval-v2"


def unlinked_namespace(path):
    path = Path(path).absolute()
    for ancestor in (path, *path.parents):
        study.require(not ancestor.is_symlink() and not ancestor.is_junction(), "linked authorization/provenance path forbidden")
        study.require(ancestor.name.rstrip(" .") == ancestor.name and ":" not in ancestor.name, "namespace alias forbidden")
        study.require(not any((ancestor/n).is_file() for n in ("manifest.json", "source-manifest.json", "INCOMPLETE.json")),
                      "authorization/provenance cannot nest inside evidence")
    return path.resolve()


@dataclass(frozen=True)
class ExecutionContext:
    fixture_root: Path | None
    output_root: Path
    sidecar_root: Path
    authorization_root: Path
    acknowledgment_root: Path


def context_for(config, fixture_root=None):
    from . import shared_noise_calibration_evidence_v1 as evidence
    if config.to_dict()["mode"] == "bounded-calibration":
        study.require(fixture_root is None, "scientific execution cannot use fixture namespaces")
        return ExecutionContext(None, evidence.OUTPUT_ROOT, SIDECAR_ROOT, AUTHORIZATION_ROOT, ACKNOWLEDGMENT_ROOT)
    study.require(fixture_root is not None, "supervised fixtures require an isolated temporary root")
    root = unlinked_namespace(fixture_root)
    study.require(any(root.is_relative_to(p.resolve()) and root != p.resolve()
                      for p in (study.ROOT/"tmp", Path(tempfile.gettempdir()))), "fixture namespaces must be temporary")
    study.require(not root.is_relative_to(study.ROOT/"results"), "fixtures cannot write scientific results")
    return ExecutionContext(root, root/"evidence", root/"sidecars", root/"authorizations", root/"acknowledgments")


def output_identity(config, directory, context, *, require_new=True):
    from . import shared_noise_calibration_evidence_v1 as evidence
    return evidence.checked_output_path(directory, config.to_dict()["mode"],
        test_output_root=context.output_root if context.fixture_root else None, require_new=require_new)


def reservation_path(context, authorization_id):
    study.require(type(authorization_id) is str and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", authorization_id),
                  "invalid unique authorization identity")
    root = unlinked_namespace(context.authorization_root)
    return unlinked_namespace(root/authorization_id)


def load_consumption(context, authorization_id):
    from . import shared_noise_calibration_evidence_v1 as evidence
    directory = reservation_path(context, authorization_id)
    study.require(directory.is_dir(), "missing authorization reservation; execution prohibited")
    receipt_path = directory/"consumption.json"
    study.require(receipt_path.is_file() and not receipt_path.is_symlink(), "missing authorization consumption receipt")
    receipt = evidence.read_json(receipt_path)
    study.validate_schema("consumption", receipt)
    payload = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    study.require(receipt["receipt_sha256"] == study.object_digest(payload), "corrupted consumption receipt")
    study.require(receipt["authorization_id"] == authorization_id
                  and receipt["approval_sha256"] == study.object_digest(receipt["approval"]), "consumption approval identity mismatch")
    study.validate_schema("approval", receipt["approval"])
    study.require(receipt["run_id"] == receipt["approval"]["run_id"]
        and receipt["output_directory"] == receipt["approval"]["output_directory"], "consumption run/output mismatch")
    checked_timestamp(receipt["consumed_at"], not_before=receipt["approval"]["approved_at"])
    return receipt


def check_consumption(config, approval, directory, context):
    receipt = load_consumption(context, approval["authorization_id"])
    study.require(receipt["approval"] == approval and receipt["config_sha256"] == config.digest
        and receipt["output_directory"] == str(directory) and receipt["run_id"] == directory.name,
        "consumed authorization differs from invocation")
    return receipt


def reserve_approval(config, approval, directory, context):
    """The atomic mkdir wins exactly once, including interrupted receipt writes."""
    from . import shared_noise_calibration_evidence_v1 as evidence
    reservation = reservation_path(context, approval["authorization_id"])
    reservation.parent.mkdir(parents=True, exist_ok=True)
    previous = approval["previous_failed_authorization_id"]
    if previous is not None:
        prior = load_consumption(context, previous)
        study.require(approval["run_id"] != prior["run_id"]
            and str(directory) != prior["output_directory"], "restart requires a new run/output identity")
        study.require(not (Path(prior["output_directory"])/evidence.MARKER).exists(),
                      "completed invocation is not a failed-run restart")
        study.require(approval["restart_reason"].strip(), "restart requires an explicitly recorded reason")
    else:
        study.require(approval["restart_reason"] is None, "restart reason requires prior authorization identity")
    try:
        reservation.mkdir(exist_ok=False)
    except FileExistsError:
        raise ValueError("authorization already consumed/reserved; a new approval is required") from None
    # Never remove this directory, even if open/write/flush/fsync fails.
    payload = dict(schema_version=study.VERSION+":consumption-v1", status="consumed-before-worker-launch",
        authorization_id=approval["authorization_id"], approval_sha256=study.object_digest(approval), approval=approval,
        run_id=directory.name, output_directory=str(directory), config_sha256=config.digest,
        consumed_at=utc_now(), fixture_only=context.fixture_root is not None)
    receipt = dict(payload, receipt_sha256=study.object_digest(payload))
    evidence.write_json(reservation/"consumption.json", receipt)
    study.require(check_consumption(config, approval, directory, context) == receipt, "consumption receipt read-back mismatch")
    return receipt


def record_lifecycle(context, authorization_id, event, **details):
    from . import shared_noise_calibration_evidence_v1 as evidence
    study.require(event in ("launch", "failure", "completion"), "invalid authorization lifecycle event")
    evidence.write_json(reservation_path(context, authorization_id)/(event+".json"),
        dict(event=event, recorded_at=utc_now(), authorization_id=authorization_id, **details))
