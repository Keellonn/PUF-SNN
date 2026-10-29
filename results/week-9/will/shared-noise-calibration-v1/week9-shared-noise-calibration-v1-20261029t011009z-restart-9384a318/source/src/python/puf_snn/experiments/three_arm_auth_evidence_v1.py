"""Exclusive Week 8 bundles and fail-closed semantic/replay reconciliation."""
from collections import Counter
from pathlib import Path, PureWindowsPath
import os
import re
import tempfile

from puf_snn.puf.acquisition import majority_vote3
from puf_snn.reconstruction import reconstruct
from . import majority3_auth_evidence_v1 as previous
from .majority3_auth_evidence_v1 import (
    safe_path, write_json, read_json, file_digest, git_state, environment, DISCLOSURE,
)
from .majority3_auth_analysis_v1 import duration_summary, ratio
from . import correlated_noise_v1 as noise
from . import three_arm_auth_v1 as study
from .three_arm_auth_runtime_v1 import STAGES, execute_attempt
from .majority3_auth_runtime_v1 import errors

ROOT = study.ROOT
NONFORMAL_ROOT = ROOT / "results/week-8/will/three-arm-auth-v1/nonformal"
RUN_PREFIX = study.VERSION+"-nonformal-"
TEST_PREFIX = study.VERSION+"-unit-"
require = study.require
VALIDATION_RECEIPT_VERSION = study.VERSION + ":validation-work-v2"
LEGACY_RECEIPT_FIELDS = ("status", "matched_trials", "arm_attempts", "actual_reads",
    "runtime_decodes", "stored_invocations", "unauthorized_releases", "validation_work")
VALIDATION_WORK_FIELDS = ("replay_measurements", "replay_decodes",
    "enrollment_reference_readings", "statistical_samples_added")


def per_pass_validation_work(receipt):
    """Read one-pass work, including historical unversioned receipts.

    This is interpretation only: it performs no replay and makes no claim that
    validation executed in this invocation. Never multiply the legacy field by
    an assumed audit history. Sealed historical receipts remain unchanged.
    """
    work = receipt["validation_work"]
    require(type(work) is dict and set(work) == set(VALIDATION_WORK_FIELDS)
        and all(type(v) is int and v >= 0 for v in work.values())
        and work["statistical_samples_added"] == 0, "invalid one-pass validation work")
    if "validation_receipt_version" in receipt:
        require(receipt["validation_receipt_version"] == VALIDATION_RECEIPT_VERSION
            and receipt["per_pass_validation_work"] == work, "validation receipt version/work mismatch")
    return dict(work)


def _scoped_validation_receipt(receipt, scope):
    """Describe completed reconciliation work at a single lifecycle boundary.

    Callers may select finalization only after BOTH reconciliation passes and
    the manifest audit succeed. Counts derive from completed operations, not
    independent wall-clock/resource instrumentation or statistical replication.
    """
    require(scope in ("reconciliation-pass", "finalization", "standalone-audit"),
            "invalid validation scope")
    work = per_pass_validation_work(receipt)
    result = {k: receipt[k] for k in LEGACY_RECEIPT_FIELDS}
    result["validation_work"] = dict(work)  # Retained one-pass compatibility alias.
    result.update(validation_receipt_version=VALIDATION_RECEIPT_VERSION,
        validation_scope=scope, validation_passes_completed=2 if scope == "finalization" else 1,
        validation_work_basis="derived-from-completed-reconciliation-operations",
        per_pass_validation_work=dict(work))
    if scope == "finalization":
        result["finalization_validation_work"] = {k: 2*v for k, v in work.items()}
    elif scope == "standalone-audit":
        result["standalone_audit_validation_work"] = dict(work)
    return result


def checked_output_path(directory, mode, *, test_output_root=None):
    raw = os.fspath(directory)
    windows = PureWindowsPath(raw)
    require(not raw.startswith(("\\\\", "//")) and not (windows.drive and not windows.root)
            and ".." not in re.split(r"[/\\]", raw), "unsafe output path")
    candidate = Path(raw).absolute()
    prefix = TEST_PREFIX if mode == "unit-test" else RUN_PREFIX
    require(re.fullmatch(re.escape(prefix)+r"[a-z0-9][a-z0-9-]{0,63}", candidate.name) is not None,
            "incorrect Week 8 output prefix")
    require(not candidate.exists(), "output must be exclusively new")
    if mode == "unit-test":
        require(test_output_root is not None, "isolated test output root required")
        require(".." not in re.split(r"[/\\]", os.fspath(test_output_root)), "test root traversal")
        root = Path(test_output_root).absolute()
        require(any(root.resolve().is_relative_to(p.resolve()) and root.resolve() != p.resolve()
                    for p in (ROOT/"tmp", Path(tempfile.gettempdir()))), "test root must be beneath temporary storage")
        require(not root.resolve().is_relative_to(ROOT/"results"), "historical evidence tree forbidden")
    else:
        require(mode == "nonformal" and test_output_root is None, "invalid output mode")
        root = NONFORMAL_ROOT
    for path in (candidate, root):
        for ancestor in (path, *path.parents):
            require(not ancestor.is_symlink() and not ancestor.is_junction(), "linked output ancestor forbidden")
            require(ancestor.name.rstrip(" .") == ancestor.name and ":" not in ancestor.name, "path alias forbidden")
            require(ancestor.name.casefold() not in ("week-5","week-6","week-7","week5","week6","week7","sim_results"),
                    "historical evidence tree forbidden")
            require(not any((ancestor/name).is_file() for name in
                ("manifest.json","source-manifest.json","COMPLETE","INCOMPLETE.json")), "nested evidence forbidden")
    require(str(candidate.resolve().parent).casefold() == str(root.resolve()).casefold(), "output escapes namespace")
    return candidate.resolve()


def source_paths():
    return sorted(set(previous.source_paths()) | {
        "configs/three_arm_auth_v1.json", "src/python/scripts/run_three_arm_auth_v1.py",
        "tests/experiments/test_three_arm_auth_v1.py", "docs/week8-three-arm-auth-methodology.md",
        "docs/week8-three-arm-auth-tests.patch",
        *(f"schemas/three-arm-auth-{kind}-v1.schema.json" for kind in ("config","plan","attempt","summary"))})


def source_hashes():
    previous.source_hashes()  # Also checks imported code belongs to this checkout.
    require(all((ROOT/p).is_file() for p in source_paths()),
            "required source/test artifacts unavailable; experiment execution blocked")
    return {p:file_digest(ROOT/p) for p in source_paths()}


def validate_protocol(row):
    e = row["establishment"]
    require(e is not None, "missing establishment outcome")
    verified, authorized = row["verification_outcomes"], row["authorization_outcomes"]
    admissions, diagnostics = row["admission_outcomes"], row["authorization_diagnostics"]
    require(not any(d.endswith("fault") for d in diagnostics), "infrastructure fault prevents completion")
    require(verified in ([], ["verified"], ["credential_mismatch"], ["record_disabled"]), "verifier infrastructure fault")
    if verified:
        require(len(admissions) == len(authorized) == len(diagnostics) == 1, "missing admission observation")
        if authorized == [True]:
            require(verified == ["verified"] and admissions == ["authorized"] and diagnostics == ["issued"],
                    "admission lacks independent verification")
        else:
            require(authorized == [False] and admissions == ["refused"] and
                diagnostics == (["credential_mismatch"] if verified == ["credential_mismatch"] else ["policy_refusal"]),
                "refusal observation mismatch")
    else:
        require(authorized == admissions == diagnostics == [], "unverified admission")
    if row["policy"] == study.STORED:
        status = row["retrieval"]
        require(status is not None and status["attempt_id"] == row["policy_attempt_id"]
                and status["preparation_failure"] is None, "stored invocation identity mismatch")
        require(e.get("credential_status") == status, "latest invocation/status mismatch")
        require(row["reconstruction"] is None and e["reconstruction_outcome"] is None, "stored reconstruction is inapplicable")
        require(status["verification_outcome"] == (verified[0] if verified else None)
                and status["admission_outcome"] == (admissions[0] if admissions else "not_invoked"),
                "stored diagnostics contradict observed service calls")
        if status["retrieval_outcome"] != "success":
            reason = {"unavailable":"stored_credential_unavailable", "malformed":"stored_credential_malformed"}
            require(status["retrieval_outcome"] in reason and not verified
                    and (e["decision"], e["stage"], e["reason"]) ==
                    ("reject", "credential_retrieval", reason[status["retrieval_outcome"]]), "retrieval failure advanced authentication")
        else:
            require(bool(verified), "retrieved credential skipped independent verification")
    else:
        r = row["reconstruction"]
        require(row["retrieval"] is None and "credential_status" not in e
                and r is not None and e["reconstruction_outcome"] == r["outcome"],
                "PUF reconstruction/establishment mismatch")
        if r["classification"] in "DI":
            require(not verified and (e["decision"],e["stage"],e["reason"]) ==
                    ("reject","reconstruction","failed_reconstruction"), "failed decode advanced authentication")
        else:
            require(verified == (["credential_mismatch"] if r["classification"] == "W" else ["verified"])
                    or verified == ["record_disabled"], "truth/verifier contradiction")
    h = row["handshake"]
    stages = ["receiver_challenge","sender_confirmation","receiver_confirmation","sender_activation"]
    require([v["stage"] for v in h] in ([],stages[:2],stages), "invalid handshake order")
    rejection_reasons = {
        "receiver_challenge": {"unsupported_protocol_version","unknown_device","session_busy",
            "resource_limit","credential_verification_failed","malformed_message"},
        "sender_confirmation": {"handshake_timeout","session_refused","inactive_session","invalid_challenge",
            "unsupported_protocol_version","credential_verification_failed","malformed_message"},
        "receiver_confirmation": {"handshake_timeout","key_confirmation_failed","inactive_session",
            "unknown_session","unsupported_protocol_version","malformed_message"},
        "sender_activation": {"handshake_timeout","session_refused","inactive_session","invalid_challenge",
            "key_confirmation_failed","expired_session","unsupported_protocol_version","malformed_message"},
    }
    for v in h:
        require((v["result"] == "accept") == (v["reason"] == "accepted"), "handshake decision/reason contradiction")
        require(v["result"] == "accept" or v["reason"] in rejection_reasons[v["stage"]], "unsupported handshake refusal")
    if h:
        require(e["request_emitted"] and authorized == [True], "handshake before admission")
        if h[0]["result"] == "reject":
            expected = ("reject","receiver_admission",h[0]["reason"],False)
            require(len(h) == 2 and h[1]["result"] == "reject", "receiver refusal advanced handshake")
        elif h[1]["result"] == "reject":
            expected = ("reject","sender_confirmation",h[1]["reason"],False)
            require(len(h) == 2, "sender refusal advanced handshake")
        else:
            require(len(h) == 4, "missing mutual confirmation")
            if h[2]["result"] == "reject":
                require(h[3]["result"] == "reject", "activation after failed confirmation")
                expected = ("reject","mutual_confirmation",h[2]["reason"],False)
            elif h[3]["result"] == "reject":
                expected = ("reject","mutual_confirmation",h[3]["reason"],False)
            else:
                expected = ("accept","active_session","accepted",True)
        require(tuple(e[k] for k in ("decision","stage","reason","session_active")) == expected,
                "establishment contradicts handshake")
    else:
        require(not e["request_emitted"] and not e["session_active"] and e["decision"] == "reject", "session without handshake")
        if verified:
            require(e["stage"] == "credential_admission" and e["reason"] == "credential_verification_failed",
                    "missing admission refusal")
    require(row["endpoint_state"] == dict(sender_active=len(h)==4 and h[3]["result"]=="accept",
        receiver_active=len(h)==4 and h[2]["result"]=="accept"), "endpoint activation contradiction")
    window, v = row["window"], row["window_verifications"]
    require((window is not None) == e["session_active"], "window eligibility contradiction")
    accepted = False
    if window is None or window["stage"] == "sender_sealing":
        require(not v, "window verified after source/session/sealing failure")
        if window:
            require(window["decision"] == "reject" and window["sequence_number"] is None and window["reason"] in
                {"expired_session","inactive_session","session_limit_reached","invalid_payload_schema",
                 "data_quality_failure","sequence_out_of_range","malformed_message"}, "invalid sealing refusal")
    else:
        require(window["stage"] == "window_verification" and len(v) == 1, "missing real window verification")
        require(all(window[k] == v[0][k] for k in ("decision","reason","sequence_number")), "window observation mismatch")
        accepted = v[0]["decision"] == "accept"
        reject_reasons = {"expired_session","inactive_session","session_limit_reached","invalid_tag","unknown_device",
            "unknown_session","device_session_mismatch","invalid_key_id","invalid_payload_schema",
            "unsupported_protocol_version","duplicate_sequence","stale_sequence","future_sequence_gap",
            "data_quality_failure","sequence_out_of_range","malformed_message"}
        require(v[0]["authenticated"] == accepted and (accepted or v[0]["reason"] in reject_reasons), "window authentication contradiction")
        require((v[0]["reason"] == "accepted" and v[0]["sequence_number"] == 0) if accepted
                else v[0]["reason"] != "accepted" and v[0]["sequence_number"] is None, "window decision/sequence contradiction")
    require(row["unauthorized_release_count"] == 0 and
        all(row[k] == int(accepted) for k in ("release_count","authorized_release_count","release_attempts","release_completions")),
        "release accounting contradiction")
    require(row["model_calls"] == {k:int(accepted) for k in ("preprocessing","motion","anomaly")}
        and row["callbacks"] == {k:dict(invocations=int(accepted),completions=int(accepted))
                                  for k in ("preprocessing","motion","anomaly")}, "callback accounting contradiction")


def validate_timing(row):
    spans = row["timing"]
    require([s["id"] for s in spans] == list(range(len(spans))), "nonconsecutive timing IDs")
    parents = dict(acquisition="establishment",reading="acquisition",voting="acquisition",
        measurement="reading",reconstruction="establishment",bch_decode="reconstruction",admission_request="establishment",
        retrieval="admission_request",authorization="admission_request",verification="authorization",
        mutual_handshake="establishment",receiver_challenge="mutual_handshake",sender_confirmation="mutual_handshake",
        receiver_confirmation="mutual_handshake",sender_activation="mutual_handshake",sender_hkdf="sender_confirmation",
        receiver_hkdf="receiver_challenge",window_seal="first_window",window_verify="first_window",release="first_window")
    for s in spans:
        require(s["stage"] in STAGES and not s["exception"] and s["duration_ns"] >= 0, "invalid completed span")
        parent = s["parent_id"]
        if parent is None:
            require(s["stage"] in ("establishment","first_window"), "unexpected timing root")
        else:
            require(0 <= parent < s["id"], "invalid timing parent")
            p = spans[parent]
            require(p["stage"] == parents[s["stage"]] and p["start_ns"] <= s["start_ns"]
                and s["start_ns"]+s["duration_ns"] <= p["start_ns"]+p["duration_ns"], "invalid timing nesting")
    for parent in [None]+list(range(len(spans))):
        children = sorted((s for s in spans if s["parent_id"] == parent), key=lambda s:s["start_ns"])
        require(all(a["start_ns"]+a["duration_ns"] <= b["start_ns"] for a,b in zip(children,children[1:])), "overlapping spans")
    counts = Counter(s["stage"] for s in spans)
    require(row["operation_counts"] == {k:counts[k] for k in STAGES}, "operation counts disagree with spans")
    require(row["stage_duration_ns"] == {k:sum(s["duration_ns"] for s in spans if s["stage"]==k)
        if counts[k] else None for k in STAGES}, "stage durations disagree with spans")
    stored = row["policy"] == study.STORED
    e = row["establishment"]
    expected = dict(establishment=1, acquisition=int(not stored), reading=row["expected_reads"],
        measurement=row["actual_reads"],
        voting=int(row["expected_reads"]==3), reconstruction=int(not stored), bch_decode=int(not stored),
        admission_request=1, retrieval=int(stored), verification=len(row["verification_outcomes"]),
        authorization=len(row["authorization_outcomes"]), mutual_handshake=int(e["request_emitted"]),
        first_window=int(e["session_active"]),window_seal=int(e["session_active"]),
        window_verify=len(row["window_verifications"]),release=row["release_attempts"],
        sender_hkdf=int(bool(row["handshake"]) and row["handshake"][1]["result"]=="accept"),
        receiver_hkdf=int(bool(row["handshake"]) and row["handshake"][0]["result"]=="accept"))
    for name in ("receiver_challenge","sender_confirmation","receiver_confirmation","sender_activation"):
        expected[name] = sum(h["stage"] == name for h in row["handshake"])
    require({k:counts[k] for k in STAGES} == expected, "source/stage invocation count mismatch")
    order = ("establishment","acquisition","reading","voting","reconstruction","bch_decode","admission_request",
        "retrieval","authorization","verification","mutual_handshake","receiver_challenge","receiver_hkdf",
        "sender_confirmation","sender_hkdf","receiver_confirmation","sender_activation","first_window","window_seal","window_verify","release")
    # Each reading contains its own actual simulator measurement.
    ordered = [name for name in order for _ in range(counts[name])]
    actual_order = [s["stage"] for s in spans if s["stage"] != "measurement"]
    require(actual_order == ordered, "timing stage order mismatch")
    for s in spans:
        if s["stage"] == "reading":
            require(sum(c["parent_id"] == s["id"] and c["stage"] == "measurement" for c in spans)==1,
                    "reading lacks actual measurement")
    for s in spans:
        if s["stage"].endswith("hkdf"):
            v = [v for v in spans if v["stage"] == "authorization"]
            require(row["verification_outcomes"] == ["verified"] and row["authorization_outcomes"] == [True]
                and len(v)==1 and v[0]["start_ns"]+v[0]["duration_ns"] <= s["start_ns"], "HKDF before verified admission")


def reconcile(config, plan, rows, catalog, context):
    study.validate_plan(config, plan)
    expected = list(study.scheduled_attempts(plan))
    require(len(rows)==len(expected), "missing or additional arm attempts")
    # Validate before indexing IDs so malformed rows fail as evidence errors.
    for row in rows:
        study.validate_schema("attempt", row)
    require(len({r["policy_attempt_id"] for r in rows})==len(rows), "duplicate arm attempts")
    require(set(catalog)=={t["device_id"] for t in plan["blocks"]}, "enrollment catalog mismatch")
    materials = {}
    for t in plan["blocks"]:
        if t["device_id"] not in materials:
            material = study.enrollment_material(config,t["population_id"],t["device_id"])
            materials[t["device_id"]] = material
            require(catalog[t["device_id"]] == study.public_enrollment_record(t["population_id"],*material[:3]), "deterministic enrollment mismatch")
    firsts = {}
    for row,(t,policy,index) in zip(rows,expected):
        require(row["execution_status"]=="completed" and row["fault_code"] is None, "faulted evidence prevents completion")
        for key in ("experiment_id","trial_id","population_id","device_id","enrollment_id","condition","attempt_index","noise_shared_seed_sha256"):
            require(row[key]==t[key], "trial identity mismatch")
        require(row["policy"]==row["credential_source"]==policy and row["execution_index"]==index
            and row["policy_attempt_id"]==study.attempt_id(t,policy), "execution schedule mismatch")
        for key,value in dict(config_sha256=config.digest,plan_sha256=plan["plan_sha256"],**context).items():
            require(row[key]==value, "run/source/configuration mismatch")
        require(row["enrollment_sha256"]==study.object_digest(catalog[t["device_id"]]), "enrollment identity mismatch")
        stored = policy==study.STORED
        count = 0 if stored else study.previous.POLICIES[policy].read_count
        require(row["actual_reads"]==row["expected_reads"]==len(row["observations"])==count, "source reading count mismatch")
        device,reference,helper,credential = materials[t["device_id"]]
        if stored:
            require(all(row[k] is None for k in ("reconstruction","effective_response","effective_sha256","effective_error_positions")),
                    "stored reconstruction fields must be null")
        else:
            replay = noise.CorrelatedResponseReader(device,study.trial_noise_config(t),noise.AttemptIdentity(**t["noise_identity"]),study.previous.POLICIES[policy])
            readings = tuple(replay() for _ in range(count))
            for i,(o,r) in enumerate(zip(row["observations"],readings)):
                require(o==dict(index=i,response=list(r),response_sha256=study.object_digest(r),error_positions=errors(r,reference),
                    input_seed_sha256=t["reading_seed_sha256"][i]), "deterministic reading replay mismatch")
            effective = readings[0] if count==1 else majority_vote3(readings)
            require(row["effective_response"]==list(effective) and row["effective_sha256"]==study.object_digest(effective)
                and row["effective_error_positions"]==errors(effective,reference), "effective response mismatch")
            decoded = reconstruct(effective,helper)
            classification = ("D" if decoded.outcome=="decoder_failure" else "I" if decoded.outcome=="invalid_format_or_padding"
                              else "C" if decoded.candidate_credential==credential else "W")
            require(row["reconstruction"]==dict(outcome=decoded.outcome,decoder_status=decoded.decoder_status,
                corrections=decoded.reported_correction_count,classification=classification), "decoder/truth replay mismatch")
            if t["trial_id"] in firsts:
                require(firsts[t["trial_id"]]==row["observations"][0], "first PUF reading pairing mismatch")
            firsts[t["trial_id"]] = row["observations"][0]
        validate_protocol(row)
        validate_timing(row)
    require(sum(r["actual_reads"] for r in rows)==plan["counts"]["expected_reads"] and
        sum(r["operation_counts"]["bch_decode"] for r in rows)==plan["counts"]["expected_runtime_decodes"], "total source counts mismatch")
    return _scoped_validation_receipt(dict(status="PASS",matched_trials=len(plan["blocks"]),arm_attempts=len(rows),
        actual_reads=sum(r["actual_reads"] for r in rows),runtime_decodes=sum(r["operation_counts"]["bch_decode"] for r in rows),
        stored_invocations=sum(r["operation_counts"]["retrieval"] for r in rows),unauthorized_releases=0,
        validation_work=dict(replay_measurements=plan["counts"]["expected_reads"], replay_decodes=plan["counts"]["expected_runtime_decodes"],
            enrollment_reference_readings=len(materials), statistical_samples_added=0)), "reconciliation-pass")


def group_metrics(rows):
    n = len(rows)
    stored = rows[0]["policy"]==study.STORED
    outcomes = Counter(r["reconstruction"]["classification"] for r in rows) if not stored else None
    retrieved = Counter(r["retrieval"]["retrieval_outcome"] for r in rows) if stored else None
    verified = sum(r["verification_outcomes"]==["verified"] for r in rows)
    authorized = sum(r["authorization_outcomes"]==[True] for r in rows)
    sessions = sum(r["establishment"]["session_active"] for r in rows)
    return dict(completed_attempts=n,verified_credentials=verified,authorized_admissions=authorized,successful_sessions=sessions,
        accepted_windows=sum(bool(r["window_verifications"]) and r["window_verifications"][0]["decision"]=="accept" for r in rows),
        authorized_releases=sum(r["authorized_release_count"] for r in rows),
        release_attempts=sum(r["release_attempts"] for r in rows),release_completions=sum(r["release_completions"] for r in rows),
        actual_reads=sum(r["actual_reads"] for r in rows),runtime_decodes=sum(r["operation_counts"]["bch_decode"] for r in rows),
        candidate_mismatches=sum(r["verification_outcomes"]==["credential_mismatch"] for r in rows),
        policy_refusals=sum(r["authorization_diagnostics"]==["policy_refusal"] for r in rows),
        reconstruction_outcomes={k:outcomes[k] for k in "CDIW"} if outcomes is not None else None,
        retrieval_outcomes={k:retrieved[k] for k in ("success","unavailable","malformed")} if retrieved is not None else None,
        reconstruction_frr=ratio(sum(outcomes[k] for k in "DIW"),n) if outcomes is not None else None,
        retrieval_failure_rate=ratio(n-retrieved["success"],n) if retrieved is not None else None,
        admission_failure_rate=ratio(n-authorized,n),session_failure_rate=ratio(n-sessions,n),
        callbacks={k:{field:sum(r["callbacks"][k][field] for r in rows) for field in ("invocations","completions")}
                   for k in ("preprocessing","motion","anomaly")},
        all_attempt_establishment=duration_summary([r["stage_duration_ns"]["establishment"] for r in rows]),
        successful_session_establishment=duration_summary([r["stage_duration_ns"]["establishment"] for r in rows if r["establishment"]["session_active"]]),
        timing={stage:dict(
            inclusive=duration_summary([s["duration_ns"] for r in rows for s in r["timing"] if s["stage"]==stage]),
            exclusive=duration_summary([s["duration_ns"]-sum(c["duration_ns"] for c in r["timing"] if c["parent_id"]==s["id"])
                for r in rows for s in r["timing"] if s["stage"]==stage])) for stage in STAGES})


def summarize(config,plan,rows,context):
    return dict(schema_version=study.EVIDENCE_VERSION+":summary",experiment_id=study.VERSION,**context,
        config_sha256=config.digest,plan_sha256=plan["plan_sha256"],
        groups={c+"|"+p:group_metrics([r for r in rows if r["condition"]==c and r["policy"]==p])
                for c,*_ in study.CONDITIONS for p in study.POLICIES},
        independent_populations=plan["counts"]["independent_populations"],matched_trials=len(plan["blocks"]),arm_attempts=len(rows),
        interval_status="not-computed-nonformal",formal_execution_enabled=False,
        timing_profile=config.to_dict()["timing_methodology"]["profile"])


def marker_name(config):
    require(config.to_dict()["mode"] in ("unit-test","nonformal"), "formal completion disabled")
    return "UNIT_TEST_VALIDATED.json" if config.to_dict()["mode"]=="unit-test" else "NONFORMAL_VALIDATED.json"


def audit_evidence(directory, *, require_marker=True):
    directory = Path(directory).absolute()
    require(directory.is_dir() and not directory.is_symlink() and not directory.is_junction(), "invalid evidence directory")
    config = study.StudyConfig.from_dict(read_json(safe_path(directory,"config.json")))
    marker = marker_name(config)
    manifest = read_json(safe_path(directory,"manifest.json"))
    required = {"config.json","trial-plan.json","metadata.json","source-manifest.json","enrollments.json","attempts.jsonl","summary.json","validation.json"}
    require(set(manifest)==required | {"source/"+p for p in source_paths()}, "manifest member set mismatch")
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    allowed = set(manifest)|{"manifest.json",marker}
    if not require_marker:
        allowed.add("INCOMPLETE.json")
    require(set(manifest)<=actual<=allowed, "manifest closure failure")
    for relative,digest in manifest.items():
        require(file_digest(safe_path(directory,relative))==digest, "artifact hash mismatch")
    source = read_json(directory/"source-manifest.json")
    metadata = read_json(directory/"metadata.json")
    require(source["files"]==source_hashes() and source["source_id"]==study.object_digest(source["files"])==metadata["source_id"], "source identity mismatch")
    for relative,digest in source["files"].items():
        require(file_digest(safe_path(directory,"source/"+relative))==digest, "source snapshot mismatch")
    require(metadata["experiment_id"]==study.VERSION and metadata["evidence_version"]==study.EVIDENCE_VERSION
        and metadata["config_sha256"]==config.digest and metadata["mode"]==config.to_dict()["mode"]
        and metadata["timing_methodology"]==config.to_dict()["timing_methodology"]
        and metadata["disclosure"]==DISCLOSURE and metadata["environment"]==environment(), "metadata/configuration mismatch")
    prefix = TEST_PREFIX if config.to_dict()["mode"]=="unit-test" else RUN_PREFIX
    require(re.fullmatch(re.escape(prefix)+r"[a-z0-9][a-z0-9-]{0,63}",metadata["run_id"]) is not None,"invalid run identity")
    plan = read_json(directory/"trial-plan.json")
    require(metadata["plan_sha256"]==plan["plan_sha256"], "metadata plan mismatch")
    rows = [study.read_json_bytes(line) for line in (directory/"attempts.jsonl").read_bytes().splitlines()]
    context = {k:metadata[k] for k in ("run_id","source_id")}
    receipt = reconcile(config,plan,rows,read_json(directory/"enrollments.json"),context)
    summary = read_json(directory/"summary.json")
    study.validate_schema("summary",summary)
    saved_receipt = read_json(directory/"validation.json")
    # Historical validation.json and markers carried an unversioned ONE-pass
    # receipt. Compare that exact projection; never relabel or rewrite it.
    legacy = "validation_receipt_version" not in saved_receipt
    expected_receipt = {k: receipt[k] for k in LEGACY_RECEIPT_FIELDS} if legacy else receipt
    require(summary==summarize(config,plan,rows,context) and saved_receipt==expected_receipt, "summary/reconciliation mismatch")
    if require_marker:
        sealed_receipt = expected_receipt if legacy else _scoped_validation_receipt(receipt, "finalization")
        require(read_json(directory/marker)==dict(experiment_id=study.VERSION,mode=config.to_dict()["mode"],
            manifest_sha256=file_digest(directory/"manifest.json"),validation_passes=2,**sealed_receipt), "completion marker mismatch")
        return _scoped_validation_receipt(receipt, "standalone-audit")
    return receipt  # Internal finalization audit: exactly one completed pass.


class EvidenceRun:
    def __init__(self,directory,config,*,authorization=None,reviewed_plan_sha256=None,test_output_root=None):
        mode = config.to_dict()["mode"]
        require(mode in ("unit-test","nonformal"), "formal execution is disabled")
        self.plan = study.compile_plan(config)
        if mode=="nonformal":
            require(authorization=="RUN-150-NONFORMAL" and reviewed_plan_sha256==self.plan["plan_sha256"], "bounded nonformal authorization/plan required")
        self.config = config
        self.directory = checked_output_path(directory,mode,test_output_root=test_output_root)
        self.hashes = source_hashes()
        self.metadata = dict(experiment_id=study.VERSION,evidence_version=study.EVIDENCE_VERSION,mode=mode,
            run_id=self.directory.name,config_sha256=config.digest,plan_sha256=self.plan["plan_sha256"],
            source_id=study.object_digest(self.hashes),git=git_state(),environment=environment(),disclosure=dict(DISCLOSURE),
            timing_methodology=config.to_dict()["timing_methodology"])
        self.rows,self.catalog,self.stream = [],{},None
        self.directory.mkdir(parents=True,exist_ok=False)
        write_json(self.directory/"INCOMPLETE.json",dict(reason="not-finalized",interrupted_work="unknown"))
        try:
            for name,value in (("config",config.to_dict()),("trial-plan",self.plan),("metadata",self.metadata)):
                write_json(self.directory/(name+".json"),value)
            for relative,digest in self.hashes.items():
                data = (ROOT/relative).read_bytes()
                require(file_digest(ROOT/relative)==digest,"source changed during snapshot")
                target = safe_path(self.directory,"source/"+relative)
                target.parent.mkdir(parents=True,exist_ok=True)
                with target.open("xb") as stream:
                    stream.write(data)
            write_json(self.directory/"source-manifest.json",dict(source_id=self.metadata["source_id"],files=self.hashes))
            self.stream = (self.directory/"attempts.jsonl").open("xb")
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self,*exc):
        self.close()

    def close(self):
        if self.stream and not self.stream.closed:
            self.stream.flush()
            os.fsync(self.stream.fileno())
            self.stream.close()

    def append(self,row):
        study.validate_schema("attempt",row)
        require(self.stream is not None and not self.stream.closed,"evidence stream closed")
        self.stream.write(study.canonical(row)+b"\n")
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.rows.append(row)

    def execute(self):
        enrollments = study.prepare_population(self.config,self.plan)
        providers = {d:study.stored_provider(e) for d,e in enrollments.items()}
        self.catalog = {d:e.public_record() for d,e in enrollments.items()}
        write_json(self.directory/"enrollments.json",self.catalog)
        for trial,policy,index in study.scheduled_attempts(self.plan):
            require(source_hashes()==self.hashes,"source changed before attempt")
            row = execute_attempt(self.config,trial,policy,enrollments[trial["device_id"]],
                run_id=self.metadata["run_id"],source_id=self.metadata["source_id"],
                plan_sha256=self.plan["plan_sha256"],execution_index=index,
                provider=providers[trial["device_id"]] if policy==study.STORED else None)
            self.append(row)
            require(row["execution_status"]=="completed","execution fault; incomplete evidence retained")
        return self.finalize()

    def finalize(self):
        self.close()
        require(source_hashes()==self.hashes,"source changed during run")
        context = {k:self.metadata[k] for k in ("run_id","source_id")}
        receipt = reconcile(self.config,self.plan,self.rows,self.catalog,context)
        summary = summarize(self.config,self.plan,self.rows,context)
        study.validate_schema("summary",summary)
        write_json(self.directory/"summary.json",summary)
        write_json(self.directory/"validation.json",receipt)
        manifest = {p.relative_to(self.directory).as_posix():file_digest(p) for p in self.directory.rglob("*")
                    if p.is_file() and p.name!="INCOMPLETE.json"}
        write_json(self.directory/"manifest.json",manifest)
        require(audit_evidence(self.directory,require_marker=False)==receipt,"final audit mismatch")
        require(source_hashes()==self.hashes,"source changed before completion")
        finalization_receipt = _scoped_validation_receipt(receipt, "finalization")
        write_json(self.directory/marker_name(self.config),dict(experiment_id=study.VERSION,mode=self.config.to_dict()["mode"],
            manifest_sha256=file_digest(self.directory/"manifest.json"),validation_passes=2,**finalization_receipt))
        (self.directory/"INCOMPLETE.json").unlink()
        return finalization_receipt
