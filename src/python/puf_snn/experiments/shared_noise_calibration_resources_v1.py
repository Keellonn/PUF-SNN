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
from . import shared_noise_calibration_authorization_v2 as auth
from .shared_noise_calibration_provenance_v2 import checked_timestamp

SIDECAR_ROOT = study.ROOT / "tmp/week9-shared-noise-calibration-v1"
CLI = study.ROOT / "src/python/scripts/run_shared_noise_calibration_v1.py"
TOKEN = "RUN-3840-SHARED-NOISE-CALIBRATION-V1"
FIXTURE_TOKEN = "TEST-ONLY-SUPERVISION-FIXTURE-V2"
FIXTURE_BUDGETS = dict(bundle_seconds=60.0, session_seconds=60.0, memory_bytes=2*1024**3,
    min_free_ram_bytes=16*1024**2, min_free_disk_bytes=64*1024**2,
    bundle_growth_bytes=16*1024**2, total_growth_bytes=64*1024**2,
    sample_seconds=.05, stop_grace_seconds=.2)


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


def validate_approval(config, approval, directory=None, *, context=None, require_new=True):
    study.validate_schema("approval", approval)
    context = context or auth.context_for(config)
    fixture = config.to_dict()["mode"] == "unit-test"
    study.require(approval["fixture_only"] == fixture, "authorization scope does not match scientific/fixture mode")
    study.require(approval["authorization"] == (FIXTURE_TOKEN if fixture else TOKEN), "wrong execution authorization kind")
    if fixture:
        study.require(approval["approved_by"] == "automated deterministic fixture; no researcher approval", "fixture must not impersonate researcher approval")
    expected_budgets = FIXTURE_BUDGETS if fixture else config.to_dict()["resource_budgets"]
    output = auth.output_identity(config, directory or approval["output_directory"], context, require_new=require_new)
    study.require(approval["output_directory"] == str(output) and approval["run_id"] == output.name,
                  "approval differs from exact canonical output/run identity")
    expected = freeze(config)
    study.require(all(approval[k] == v for k, v in expected.items()), "approval differs from frozen source/config/plan/environment/specification")
    study.require(approval["resource_budgets"] == expected_budgets, "approval budget mismatch")
    study.require(approval["approved_by"].strip() and approval["approved_by"] == approval["approved_by"].strip(), "named approval owner required")
    checked_timestamp(approval["approved_at"])
    return expected


@dataclass(frozen=True)
class ExecutionPermit:
    config_sha256: str
    directory: Path
    approval: dict
    supervision: object
    stop_path: Path
    context: auth.ExecutionContext
    consumption: dict

    def check(self):
        study.require(type(self.supervision) is primitives().WorkerSupervision,
                      "permit requires real peer-verified worker supervision")
        self.supervision.check()
        study.require(not self.stop_path.exists(), "calibration resource supervisor requested interruption")
        current = auth.load_consumption(self.context, self.approval["authorization_id"])
        study.require(current == self.consumption, "authorization consumption changed or became unavailable")


def checked_worker(request, supervision):
    """Refuse direct workers without live OS-verified controller and frozen approval."""
    p = primitives()
    study.require(type(supervision) is p.WorkerSupervision and supervision.request == request,
                  "live calibration worker supervision required")
    supervision.check()
    study.require(request["kind"] == "shared-noise-calibration-v1" and request["controller_pid"] == os.getppid(),
                  "wrong calibration controller")
    config = study.StudyConfig.from_dict(request["config"])
    context = auth.context_for(config, request.get("fixture_root"))
    sidecar = Path(request["worker_sidecar"]).absolute()
    study.require(sidecar.name == "worker" and sidecar.parent.parent.resolve() == context.sidecar_root.resolve(), "worker sidecar escapes namespace")
    saved = p.read_json(sidecar.parent/"request.json")
    # Launch time/pipe/job are assigned by the live monitor after the saved request.
    stable = {k: v for k, v in request.items() if k not in ("worker_launch_monotonic", "supervision")}
    study.require(stable == saved, "worker request differs from reviewed controller request")
    validate_approval(config, request["approval"], request["directory"], context=context)
    study.require(request["budgets"] == request["approval"]["resource_budgets"], "worker budget mismatch")
    directory = auth.output_identity(config, request["directory"], context)
    consumption = auth.check_consumption(config, request["approval"], directory, context)
    study.require(consumption == request["consumption"], "worker consumption differs from controller reservation")
    return config, ExecutionPermit(config.digest, directory, request["approval"], supervision, sidecar/"STOP", context, consumption)


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


def execute(config, directory, approval, *, fixture_root=None):
    study.require(os.name == "nt", "scientific execution requires the Windows resource supervisor")
    context = auth.context_for(config, fixture_root)
    validate_approval(config, approval, directory, context=context)
    output = auth.output_identity(config, directory, context)
    p = primitives()
    session = p.unlinked(context.sidecar_root/output.name)
    study.require(not session.exists(), "sidecar collision; no automatic resume")
    consumption = auth.reserve_approval(config, approval, output, context)
    # Any exception after reservation leaves this ID consumed, including setup,
    # worker failure, interruption and final completion publication failure.
    try:
        return _execute_reserved(config, output, approval, context, consumption, session)
    except BaseException as exc:
        try:
            auth.record_lifecycle(context, approval["authorization_id"], "failure", error_type=type(exc).__name__)
        except (OSError, ValueError):
            pass  # The durable reservation still prevents reuse if diagnostics fail.
        raise


def _execute_reserved(config, output, approval, context, consumption, session):
    p = primitives()
    session.mkdir(parents=True, exist_ok=False)
    sidecar = session/"worker"
    sidecar.mkdir()
    budgets = p.Budgets(**approval["resource_budgets"])
    started = time.monotonic()
    request = dict(kind="shared-noise-calibration-v1", controller_pid=os.getpid(), directory=str(output),
        worker_sidecar=str(sidecar), session_started_monotonic=started,
        config=config.to_dict(), approval=approval, budgets=approval["resource_budgets"],
        consumption=consumption, fixture_root=str(context.fixture_root) if context.fixture_root else None)
    p.save_json(session/"request.json", request)
    auth.record_lifecycle(context, approval["authorization_id"], "launch", run_id=output.name)
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
        study.require(auth.check_consumption(config, approval, output, context) == consumption,
                      "authorization consumption changed before controller completion")
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
        manifest_sha256=evidence.file_digest(output/"manifest.json"), actual_completed_attempts=counts["arm_attempts"],
        fixture_only=context.fixture_root is not None))
    final_budget_check()
    # Lifecycle receipt is a candidate until the evidence marker commits. Its
    # existence also conservatively prevents classifying a completed run as a restart.
    auth.record_lifecycle(context, approval["authorization_id"], "completion",
        manifest_sha256=evidence.file_digest(output/"manifest.json"), certification="requires-calibration-completion-marker")
    evidence.seal(output, receipt, config, boundary=final_budget_check)
    return dict(status="completed-fixture-only" if context.fixture_root else "completed-calibration-only",
        directory=str(output), fixture_only=context.fixture_root is not None,
        scientific_execution_disabled=context.fixture_root is not None, **expected)
