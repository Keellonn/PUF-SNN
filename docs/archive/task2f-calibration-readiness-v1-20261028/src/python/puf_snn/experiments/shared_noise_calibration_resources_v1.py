"""Calibration-only controller using the reviewed Windows containment primitives.

The legacy profiler's workload, authorization and output paths are never used.
Only its OS metrics, kill-on-close job, peer-verified pipe/lease and monitor are reused.
"""
from dataclasses import dataclass
from datetime import datetime
import importlib.util
import os
from pathlib import Path
import sys
import time

from . import shared_noise_calibration_v1 as study
from . import shared_noise_calibration_evidence_v1 as evidence

SIDECAR_ROOT = study.ROOT / "tmp/week9-shared-noise-calibration-v1"
CLI = study.ROOT / "src/python/scripts/run_shared_noise_calibration_v1.py"
TOKEN = "RUN-3840-SHARED-NOISE-CALIBRATION-V1"


def primitives():
    name = "_shared_noise_calibration_windows_primitives_v1"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, study.ROOT/"tools/profile_three_arm_resources_v1.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]


def freeze(config):
    plan = study.compile_plan(config)
    return dict(config_sha256=config.digest, plan_sha256=plan["plan_sha256"],
        source_id=study.object_digest(evidence.source_hashes()),
        environment_sha256=study.object_digest(evidence.environment()),
        specification_sha256=evidence.file_digest(study.ROOT/study.SPEC_PATH))


def validate_approval(config, approval):
    study.validate_schema("approval", approval)
    study.require(config.to_dict()["mode"] == "bounded-calibration", "scientific approval cannot authorize fixtures")
    expected = freeze(config)
    study.require(all(approval[k] == v for k, v in expected.items()), "approval differs from frozen source/config/plan/environment/specification")
    study.require(approval["resource_budgets"] == config.to_dict()["resource_budgets"], "approval budget mismatch")
    study.require(approval["approved_by"].strip() and approval["approved_by"] == approval["approved_by"].strip(), "named approval owner required")
    timestamp = datetime.fromisoformat(approval["approved_at"])
    study.require(timestamp.tzinfo is not None and timestamp <= datetime.now(timestamp.tzinfo), "valid dated approval required")
    return expected


@dataclass(frozen=True)
class ExecutionPermit:
    config_sha256: str
    directory: Path
    approval: dict
    supervision: object
    stop_path: Path

    def check(self):
        study.require(type(self.supervision) is primitives().WorkerSupervision,
                      "permit requires real peer-verified worker supervision")
        self.supervision.check()
        study.require(not self.stop_path.exists(), "calibration resource supervisor requested interruption")


def checked_worker(request, supervision):
    """Refuse direct workers without live OS-verified controller and frozen approval."""
    p = primitives()
    study.require(type(supervision) is p.WorkerSupervision and supervision.request == request,
                  "live calibration worker supervision required")
    supervision.check()
    study.require(request["kind"] == "shared-noise-calibration-v1" and request["controller_pid"] == os.getppid(),
                  "wrong calibration controller")
    sidecar = Path(request["worker_sidecar"]).absolute()
    study.require(sidecar.name == "worker" and sidecar.parent.parent.resolve() == SIDECAR_ROOT.resolve(), "worker sidecar escapes namespace")
    saved = p.read_json(sidecar.parent/"request.json")
    # Launch time/pipe/job are assigned by the live monitor after the saved request.
    stable = {k: v for k, v in request.items() if k not in ("worker_launch_monotonic", "supervision")}
    study.require(stable == saved, "worker request differs from reviewed controller request")
    config = study.StudyConfig.from_dict(request["config"])
    validate_approval(config, request["approval"])
    study.require(request["budgets"] == config.to_dict()["resource_budgets"], "worker budget mismatch")
    directory = evidence.checked_output_path(request["directory"], "bounded-calibration")
    return config, ExecutionPermit(config.digest, directory, request["approval"], supervision, sidecar/"STOP")


def worker(request):
    p = primitives()
    with p.WorkerSupervision(request) as supervision:
        config, permit = checked_worker(request, supervision)
        sidecar = Path(request["worker_sidecar"])
        p.save_json(sidecar/"progress.json", dict(name="calibration-through-finalization", started=request["session_started_monotonic"]))
        with evidence.EvidenceRun(permit.directory, config, permit=permit) as run:
            receipt = run.execute()
        permit.check()
        result = sidecar/"worker-result.json"
        p.save_json(result, dict(success=True, receipt=receipt, freeze=freeze(config),
                                manifest_sha256=evidence.file_digest(permit.directory/"manifest.json")))
        supervision.finish(result)


def launch_worker(arguments, **kwargs):
    p = primitives()
    study.require(arguments == [str(Path(p.__file__).resolve()), "_worker"], "unexpected monitor launch command")
    return p.launch_python([str(CLI), "_worker"], **kwargs)


def execute(config, directory, approval):
    study.require(os.name == "nt", "scientific execution requires the Windows resource supervisor")
    validate_approval(config, approval)
    output = evidence.checked_output_path(directory, "bounded-calibration")
    p = primitives()
    session = p.unlinked(SIDECAR_ROOT/output.name)
    study.require(not session.exists(), "sidecar collision; no automatic resume")
    session.mkdir(parents=True, exist_ok=False)
    sidecar = session/"worker"
    sidecar.mkdir()
    budgets = p.Budgets(**config.to_dict()["resource_budgets"])
    started = time.monotonic()
    request = dict(kind="shared-noise-calibration-v1", controller_pid=os.getpid(), directory=str(output),
        worker_sidecar=str(sidecar), session_started_monotonic=started,
        config=config.to_dict(), approval=approval, budgets=config.to_dict()["resource_budgets"])
    p.save_json(session/"request.json", request)
    result = p.monitor_worker(request, sidecar, budgets, started, [output], popen=launch_worker)
    p.save_json(session/"monitor-result.json", result)
    study.require(result["success"] and result["supervision_verified"] and not (sidecar/"STOP").exists(),
                  "calibration supervision failed; incomplete output retained")
    # No third replay. Compare the frozen identity and artifact digest after the
    # two-pass worker exits and the monitor has accepted its final resource sample.
    expected = freeze(config)
    study.require(result["worker"]["freeze"] == expected and all(approval[k] == v for k, v in expected.items()),
                  "source/environment changed before controller acceptance")
    study.require(evidence.file_digest(output/"manifest.json") == result["worker"]["manifest_sha256"], "manifest changed after worker validation")
    receipt = result["worker"]["receipt"]
    counts = study.compile_plan(config)["counts"]
    study.require(receipt["status"] == "PASS" and receipt["arm_attempts"] == counts["arm_attempts"]
        and receipt["actual_reads"] == counts["expected_reads"]
        and receipt["runtime_decodes"] == counts["expected_runtime_decodes"]
        and receipt["validation_passes_completed"] == 1,
        "worker receipt does not certify the complete calibration")
    def final_budget_check():
        sample = p.WindowsMetrics(os.getpid())
        try:
            final = sample.sample()
        finally:
            sample.close()
        import shutil
        final["free_disk_bytes"] = shutil.disk_usage(session).free
        violations = budgets.violations(final, phase_seconds=time.monotonic()-started,
            session_seconds=time.monotonic()-started, bundle_bytes=p.tree_size(output)["logical_bytes"],
            total_bytes=p.tree_size(output)["logical_bytes"]+p.tree_size(session)["logical_bytes"])
        study.require(not violations and not (sidecar/"STOP").exists(),
                      "final controller resource acceptance failed; output stays incomplete")
    p.save_json(session/"controller-validation.json", dict(status="validated-awaiting-completion-marker", **expected,
        certification="valid-only-with-calibration-completion-marker",
        manifest_sha256=evidence.file_digest(output/"manifest.json"), actual_completed_attempts=3840))
    final_budget_check()
    evidence.seal(output, receipt, config, boundary=final_budget_check)
    return dict(status="completed-calibration-only", directory=str(output), **expected)
