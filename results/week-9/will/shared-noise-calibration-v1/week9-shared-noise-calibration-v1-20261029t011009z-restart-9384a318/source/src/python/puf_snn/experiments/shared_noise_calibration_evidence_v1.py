"""Exclusive calibration bundles, complete deterministic replay and two-pass sealing."""
from collections import Counter
from pathlib import Path, PureWindowsPath
import os
import re
import tempfile

from puf_snn.puf.acquisition import majority_vote3
from puf_snn.reconstruction import reconstruct
from . import shared_noise_calibration_v1 as study
from . import shared_noise_calibration_analysis_v1 as analysis
from . import shared_noise_calibration_runtime_v1 as runtime
from . import three_arm_auth_evidence_v1 as old
from . import majority3_auth_evidence_v1 as base
from . import correlated_noise_v1 as noise
from . import shared_noise_calibration_provenance_v2 as provenance
from .majority3_auth_runtime_v1 import errors
from .majority3_auth_evidence_v1 import safe_path, write_json, read_json, file_digest, environment, git_state, DISCLOSURE

ROOT = study.ROOT
OUTPUT_ROOT = ROOT / "results/week-9/will/shared-noise-calibration-v1"
MARKER = "CALIBRATION_VALIDATED.json"
require = study.require


def source_paths():
    paths = set(old.source_paths()) - {"docs/week8-three-arm-auth-tests.patch"}
    paths.update({study.SPEC_PATH, "docs/week9-shared-noise-calibration-readiness.md",
        "docs/archive/week8-three-arm-auth-tests.patch", "configs/shared_noise_calibration_v1.json",
        "src/python/scripts/run_shared_noise_calibration_v1.py",
        "tools/profile_three_arm_resources_v1.py", "tests/tools/test_profile_three_arm_resources_v1.py",
        "tests/experiments/test_shared_noise_calibration_v1.py",
        "tests/experiments/test_shared_noise_calibration_monitor_v1.py",
        "tests/experiments/test_shared_noise_calibration_authorization_v2.py"})
    paths.update(f"schemas/shared-noise-calibration-{k}-v1.schema.json" for k in ("config", "plan", "attempt", "summary", "approval"))
    paths.update({"schemas/shared-noise-calibration-approval-v2.schema.json",
        "schemas/shared-noise-calibration-selection-v2.schema.json",
        "schemas/shared-noise-calibration-consumption-v1.schema.json",
        "schemas/shared-noise-calibration-acknowledgment-v1.schema.json"})
    return sorted(paths)


def source_hashes():
    base.source_hashes()  # Also refuses imported project modules from another checkout.
    require(all((ROOT/p).is_file() for p in source_paths()), "required calibration source artifact unavailable")
    return {p: file_digest(ROOT/p) for p in source_paths()}


def checked_output_path(directory, mode, *, test_output_root=None, require_new=True):
    raw = os.fspath(directory)
    win = PureWindowsPath(raw)
    require(not raw.startswith(("\\\\", "//")) and not (win.drive and not win.root)
            and ".." not in re.split(r"[/\\]", raw), "unsafe calibration path")
    candidate = Path(raw).absolute()
    require(mode in ("unit-test", "bounded-calibration"), "only calibration/fixtures allowed")
    prefix = study.VERSION + ("-unit-" if mode == "unit-test" else "-")
    require(re.fullmatch(re.escape(prefix)+r"[a-z0-9][a-z0-9-]{0,63}", candidate.name) is not None,
            "invalid calibration output prefix")
    require(not require_new or not candidate.exists(), "output must be exclusively new; no resume")
    if mode == "unit-test":
        require(test_output_root is not None, "isolated fixture root required")
        root = Path(test_output_root).absolute()
        require(any(root.resolve().is_relative_to(p.resolve()) and root.resolve() != p.resolve()
                    for p in (ROOT/"tmp", Path(tempfile.gettempdir()))), "fixture root must be temporary")
        require(not root.resolve().is_relative_to(ROOT/"results"), "fixtures cannot write research results")
    else:
        require(test_output_root is None, "scientific mode cannot use fixture root")
        root = OUTPUT_ROOT
    for path in (candidate, root):
        for ancestor in (path, *path.parents):
            require(not ancestor.is_symlink() and not ancestor.is_junction(), "linked output ancestor forbidden")
            require(ancestor.name.rstrip(" .") == ancestor.name and ":" not in ancestor.name, "path alias forbidden")
            require(ancestor.name.casefold() not in ("week-5", "week-6", "week-7", "week-8", "sim_results"),
                    "historical output forbidden")
            require((not require_new and ancestor == candidate) or not any((ancestor/n).is_file() for n in ("manifest.json", "source-manifest.json", "COMPLETE", "INCOMPLETE.json")),
                    "nested evidence forbidden")
    require(str(candidate.resolve().parent).casefold() == str(root.resolve()).casefold(), "output escapes namespace")
    return candidate.resolve()


def scoped_receipt(receipt, scope):
    require(scope in ("reconciliation-pass", "finalization", "standalone-audit"), "invalid validation scope")
    result = dict(receipt, validation_receipt_version=study.EVIDENCE_VERSION + ":validation-work-v1",
        validation_scope=scope, validation_passes_completed=2 if scope == "finalization" else 1,
        validation_work_basis="derived-from-completed-reconciliation-operations")
    if scope == "finalization":
        result["finalization_validation_work"] = {k: 2*v for k, v in receipt["validation_work"].items()}
    return result


def classify(decoded, credential):
    return ("D" if decoded.outcome == "decoder_failure" else
            "I" if decoded.outcome == "invalid_format_or_padding" else
            "C" if decoded.candidate_credential == credential else "W")


def reconcile(config, plan, rows, catalog, context, *, boundary=lambda: None):
    study.validate_plan(config, plan)
    expected = list(study.scheduled_attempts(plan))
    require(len(rows) == len(expected), "missing or additional policy attempts")
    for row in rows:
        study.validate_schema("attempt", row)
    analysis.complete_cells(config, plan, rows)
    require(len({r["policy_attempt_id"] for r in rows}) == len(rows), "duplicate policy attempts")
    require(set(catalog) == {t["device_id"] for t in plan["blocks"]}, "enrollment catalog mismatch")
    materials, firsts = {}, {}
    for row, (trial, policy, index) in zip(rows, expected):
        boundary()
        device_id = trial["device_id"]
        if device_id not in materials:
            material = study.enrollment_material(config, trial["population_id"], device_id)
            materials[device_id] = material
            require(catalog[device_id] == study.public_enrollment_record(trial["population_id"], *material[:3]),
                    "deterministic enrollment mismatch")
        require(row["execution_status"] == "completed" and row["fault_code"] is None, "faulted evidence prevents completion")
        for key in ("experiment_id", "trial_id", "population_id", "device_id", "enrollment_id", "condition", "attempt_index", "noise_shared_seed_sha256"):
            require(row[key] == trial[key], "trial identity mismatch")
        for key, value in dict(config_sha256=config.digest, plan_sha256=plan["plan_sha256"], **context).items():
            require(row[key] == value, "run/source/configuration mismatch")
        require(row["policy"] == row["credential_source"] == policy and row["execution_index"] == index
                and row["policy_attempt_id"] == study.attempt_id(trial, policy), "schedule mismatch")
        require(row["enrollment_sha256"] == study.object_digest(catalog[device_id]), "enrollment identity mismatch")
        count = study.previous.POLICIES[policy].read_count
        require(row["actual_reads"] == row["expected_reads"] == len(row["observations"]) == count,
                "source operation count mismatch")
        device, reference, helper, credential = materials[device_id]
        reader = noise.CorrelatedResponseReader(device, study.trial_noise_config(trial),
                    noise.AttemptIdentity(**trial["noise_identity"]), study.previous.POLICIES[policy])
        readings = tuple(reader() for _ in range(count))
        for i, (observation, bits) in enumerate(zip(row["observations"], readings)):
            require(observation == dict(index=i, response=list(bits), response_sha256=study.object_digest(bits),
                error_positions=errors(bits, reference), input_seed_sha256=trial["reading_seed_sha256"][i]), "reading replay mismatch")
        effective = readings[0] if count == 1 else majority_vote3(readings)
        require(row["effective_response"] == list(effective) and row["effective_sha256"] == study.object_digest(effective)
            and row["effective_error_positions"] == errors(effective, reference), "effective response mismatch")
        decoded = reconstruct(effective, helper)
        require(row["reconstruction"] == dict(outcome=decoded.outcome, decoder_status=decoded.decoder_status,
            corrections=decoded.reported_correction_count, classification=classify(decoded, credential)), "decoder/truth replay mismatch")
        if trial["trial_id"] in firsts:
            require(firsts[trial["trial_id"]] == row["observations"][0], "first reading pairing mismatch")
        firsts[trial["trial_id"]] = row["observations"][0]
        old.validate_protocol(row)
        old.validate_timing(row)
    require(sum(r["actual_reads"] for r in rows) == plan["counts"]["expected_reads"]
        and sum(r["operation_counts"]["bch_decode"] for r in rows) == plan["counts"]["expected_runtime_decodes"]
        and sum(r["operation_counts"]["voting"] for r in rows) == plan["counts"]["expected_votes"], "total operation mismatch")
    return scoped_receipt(dict(status="PASS", matched_trials=len(plan["blocks"]), arm_attempts=len(rows),
        actual_reads=plan["counts"]["expected_reads"], runtime_decodes=len(rows), stored_invocations=0, unauthorized_releases=0,
        validation_work=dict(replay_measurements=plan["counts"]["expected_reads"], replay_decodes=len(rows),
                             enrollment_reference_readings=len(materials), statistical_samples_added=0)), "reconciliation-pass")


def summarize(config, plan, rows, context):
    return dict(schema_version=study.VERSION + ":summary", **context, config_sha256=config.digest,
        plan_sha256=plan["plan_sha256"], fixture_only=config.to_dict()["mode"] == "unit-test",
        timing_profile=config.to_dict()["timing_profile"],
        groups={c+"|"+p: old.group_metrics([r for r in rows if r["condition"] == c and r["policy"] == p])
                for c, _ in study.CONDITIONS for p in study.POLICIES},
        analysis=analysis.analyze(config, plan, rows, coverage_certified=True))


def audit_evidence(directory, *, require_marker=True, boundary=lambda: None):
    directory = Path(directory).absolute()
    require(directory.is_dir() and not directory.is_symlink() and not directory.is_junction(), "invalid bundle directory")
    config = study.StudyConfig.from_dict(read_json(safe_path(directory, "config.json")))
    manifest = read_json(safe_path(directory, "manifest.json"))
    required = {"config.json", "trial-plan.json", "metadata.json", "source-manifest.json", "enrollments.json",
                "attempts.jsonl", "summary.json", "validation.json", "selection.json", "authorization-consumption.json"}
    require(set(manifest) == required | {"source/"+p for p in source_paths()}, "manifest member set mismatch")
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    allowed = set(manifest) | {"manifest.json", MARKER} | (set() if require_marker else {"INCOMPLETE.json"})
    require(set(manifest) <= actual <= allowed, "manifest closure failure")
    for relative, digest in manifest.items():
        boundary()
        require(file_digest(safe_path(directory, relative)) == digest, "artifact hash mismatch")
    source = read_json(directory/"source-manifest.json")
    metadata = read_json(directory/"metadata.json")
    require(source["files"] == source_hashes() and source["source_id"] == study.object_digest(source["files"])
            == metadata["source_id"], "source identity mismatch")
    for relative, digest in source["files"].items():
        require(file_digest(safe_path(directory, "source/"+relative)) == digest, "source snapshot mismatch")
    require(metadata["bundle_version"] == provenance.BUNDLE_VERSION
            and metadata["experiment_id"] == study.VERSION and metadata["environment"] == environment()
            and metadata["config_sha256"] == config.digest and metadata["mode"] == config.to_dict()["mode"]
            and metadata["disclosure"] == DISCLOSURE, "metadata/environment mismatch")
    require(metadata["run_id"] == directory.name, "run directory identity mismatch")
    if metadata["approval"] is not None:
        from .shared_noise_calibration_resources_v1 import validate_approval
        from . import shared_noise_calibration_authorization_v2 as auth
        context = auth.context_for(config, metadata["fixture_root"])
        validate_approval(config, metadata["approval"], directory, context=context, require_new=False)
        consumption = auth.check_consumption(config, metadata["approval"], directory, context)
        require(read_json(directory/"authorization-consumption.json") == consumption, "bundled/live consumption receipt mismatch")
    else:
        require(config.to_dict()["mode"] == "unit-test" and read_json(directory/"authorization-consumption.json") is None,
                "scientific evidence requires consumed authorization")
    plan = read_json(directory/"trial-plan.json")
    require(metadata["plan_sha256"] == plan["plan_sha256"], "metadata plan mismatch")
    rows = [study.read_json_bytes(line) for line in (directory/"attempts.jsonl").read_bytes().splitlines()]
    context = {k: metadata[k] for k in ("run_id", "source_id")}
    receipt = reconcile(config, plan, rows, read_json(directory/"enrollments.json"), context, boundary=boundary)
    summary = read_json(directory/"summary.json")
    study.validate_schema("summary", summary)
    require(summary == summarize(config, plan, rows, context) and read_json(directory/"validation.json") == receipt,
            "summary/reconciliation mismatch")
    provenance.validate_computed_selection(directory, summary, metadata, read_json(directory/"selection.json"))
    if require_marker:
        marker = read_json(directory/MARKER)
        require(marker == completion_receipt(directory, receipt, config, completed_at=marker["completed_at"]), "completion marker mismatch")
    return scoped_receipt(receipt, "standalone-audit") if require_marker else receipt


def selection_receipt(summary, metadata, directory, *, computed_at=None):
    return provenance.computed_selection(directory, summary, metadata, computed_at=computed_at or provenance.utc_now())


def completion_receipt(directory, receipt, config, *, completed_at=None):
    completed_at = completed_at or provenance.utc_now()
    selection_path = Path(directory)/"selection.json"
    provenance.checked_timestamp(completed_at,
        not_before=read_json(selection_path)["computation_timestamp"] if selection_path.exists() else None)
    return dict(experiment_id=study.VERSION, bundle_version=provenance.BUNDLE_VERSION, mode=config.to_dict()["mode"],
        completed_at=completed_at, manifest_sha256=file_digest(Path(directory)/"manifest.json"), **scoped_receipt(receipt, "finalization"))


def seal(directory, receipt, config, *, boundary=lambda: None):
    """Publish the final marker last. Absence of a marker ALWAYS means incomplete."""
    directory = Path(directory)
    sentinel, staging, marker = directory/"INCOMPLETE.json", directory/"completion.pending", directory/MARKER
    require(sentinel.is_file() and not marker.exists(), "missing incomplete sentinel or existing marker")
    try:
        write_json(staging, completion_receipt(directory, receipt, config))
        boundary()
        sentinel.unlink()
        os.replace(staging, marker)  # Commit point, after durable staging and all checks.
    except BaseException:
        if not marker.exists():
            if not sentinel.exists():
                write_json(sentinel, dict(reason="completion-publication-failed", interrupted_work="unknown"))
            if staging.exists():
                staging.unlink()
        raise


class EvidenceRun:
    def __init__(self, directory, config, *, permit=None, test_output_root=None):
        self.config, self.permit = config, permit
        mode = config.to_dict()["mode"]
        if permit is not None:
            from .shared_noise_calibration_resources_v1 import ExecutionPermit, validate_approval
            require(type(permit) is ExecutionPermit, "reviewed live supervision permit required")
            permit.check()
            validate_approval(config, permit.approval, directory, context=permit.context)
            require(permit.config_sha256 == config.digest and permit.directory == Path(directory).absolute(), "permit/config/output mismatch")
            test_output_root = permit.context.output_root if permit.context.fixture_root else None
        else:
            require(mode == "unit-test", "scientific evidence requires a reviewed live supervision permit")
        self.plan = study.compile_plan(config)
        self.directory = checked_output_path(directory, mode, test_output_root=test_output_root)
        self.hashes = source_hashes()
        self.metadata = dict(experiment_id=study.VERSION, bundle_version=provenance.BUNDLE_VERSION, mode=mode, run_id=self.directory.name,
            source_id=study.object_digest(self.hashes), config_sha256=config.digest, plan_sha256=self.plan["plan_sha256"],
            git=git_state(), environment=environment(), disclosure=DISCLOSURE,
            approval=permit.approval if permit else None,
            fixture_root=str(permit.context.fixture_root) if permit and permit.context.fixture_root else None)
        self.rows, self.catalog, self.stream = [], {}, None
        self.directory.mkdir(parents=True, exist_ok=False)
        write_json(self.directory/"INCOMPLETE.json", dict(reason="not-finalized", interrupted_work="unknown"))
        try:
            for name, value in (("config", config.to_dict()), ("trial-plan", self.plan), ("metadata", self.metadata),
                                ("authorization-consumption", permit.consumption if permit else None)):
                write_json(self.directory/(name+".json"), value)
            for relative, digest in self.hashes.items():
                data = (ROOT/relative).read_bytes()
                require(study.sha256(data).hexdigest() == digest, "source changed during snapshot")
                target = safe_path(self.directory, "source/"+relative)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(data)
            write_json(self.directory/"source-manifest.json", dict(source_id=self.metadata["source_id"], files=self.hashes))
            self.stream = (self.directory/"attempts.jsonl").open("xb")
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self.stream and not self.stream.closed:
            self.stream.flush()
            os.fsync(self.stream.fileno())
            self.stream.close()

    def boundary(self):
        if self.permit:
            self.permit.check()

    def append(self, row):
        self.boundary()
        require(len(self.rows) < self.plan["counts"]["arm_attempts"], "policy attempt cap exceeded")
        study.validate_schema("attempt", row)
        require(self.stream is not None and not self.stream.closed, "evidence stream closed")
        self.stream.write(study.canonical(row)+b"\n")
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.rows.append(row)

    def execute(self):
        self.boundary()
        enrollments = study.prepare_population(self.config, self.plan)
        self.catalog = {d: e.public_record() for d, e in enrollments.items()}
        write_json(self.directory/"enrollments.json", self.catalog)
        for trial, policy, index in study.scheduled_attempts(self.plan):
            self.boundary()
            require(source_hashes() == self.hashes, "source changed before attempt")
            row = runtime.execute_attempt(self.config, trial, policy, enrollments[trial["device_id"]],
                run_id=self.metadata["run_id"], source_id=self.metadata["source_id"],
                plan_sha256=self.plan["plan_sha256"], execution_index=index, permit=self.permit)
            self.append(row)
            require(row["execution_status"] == "completed", "execution fault; incomplete evidence retained")
        return self.finalize()

    def finalize(self):
        self.boundary()
        self.close()
        require(source_hashes() == self.hashes, "source changed during execution")
        context = {k: self.metadata[k] for k in ("run_id", "source_id")}
        receipt = reconcile(self.config, self.plan, self.rows, self.catalog, context, boundary=self.boundary)
        summary = summarize(self.config, self.plan, self.rows, context)
        study.validate_schema("summary", summary)
        for name, obj in (("summary", summary), ("validation", receipt)):
            write_json(self.directory/(name+".json"), obj)
        selection = selection_receipt(summary, self.metadata, self.directory)
        study.validate_schema("selection", selection)
        write_json(self.directory/"selection.json", selection)
        manifest = {p.relative_to(self.directory).as_posix(): file_digest(p) for p in self.directory.rglob("*")
                    if p.is_file() and p.name != "INCOMPLETE.json"}
        write_json(self.directory/"manifest.json", manifest)
        require(audit_evidence(self.directory, require_marker=False, boundary=self.boundary) == receipt, "second pass mismatch")
        self.boundary()
        require(source_hashes() == self.hashes, "source changed before completion")
        if self.config.to_dict()["mode"] == "unit-test" and self.permit is None:
            seal(self.directory, receipt, self.config)
        # Scientific bundles remain INCOMPLETE until the controller independently
        # accepts live resource supervision, worker exit and final budget checks.
        return receipt
