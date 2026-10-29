"""Exclusive nonformal evidence, source snapshots, and fail-closed reconciliation.

No formal execution or COMPLETE marker is implemented. Public artifacts contain
synthetic PUF observations and derived outcomes, never credentials or protocol keys.
"""
from collections import Counter
from hashlib import sha256
import importlib.metadata
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import platform
import re
import subprocess
import sys
import tempfile

from puf_snn.puf.acquisition import majority_vote3
from puf_snn.reconstruction import reconstruct
from . import correlated_noise_v1 as noise
from .majority3_auth_v1 import (
    VERSION, EVIDENCE_VERSION, ROOT, POLICIES, StudyConfig, attempt_id, canonical, compile_plan,
    object_digest, prepare_population, read_json_bytes, require, scheduled_attempts,
    validate_plan, validate_schema, enrollment_material, public_enrollment_record, trial_noise_config,
)
from .majority3_auth_runtime_v1 import STAGES, errors, execute_attempt
from .majority3_auth_analysis_v1 import summarize


# These phases drive execution as well as the planning estimate.
FINALIZATION_REPLAYS = ("pre_summary", "manifest_audit")
NONFORMAL_ROOT = ROOT / "results/week-7/will/majority3-auth-correlated-v1/nonformal"
RUN_PREFIX = "week7-majority3-auth-correlated-v1-nonformal-"
TEST_PREFIX = "week7-majority3-auth-correlated-v1-unit-"
DISCLOSURE = dict(literal_credential_fields_omitted=True, verifier_secret_keys_omitted=True,
    session_keys_omitted=True, authorization_capabilities_omitted=True,
    synthetic_pilot_credential_reconstructible_from_replay_inputs=True,
    research_evidence_audience="public_synthetic_research",
    replay_material_confidential=False)


def resource_estimate(plan, replay_phases=None):
    phases = FINALIZATION_REPLAYS if replay_phases is None else tuple(replay_phases)
    attempts = list(scheduled_attempts(plan))
    reads = sum(POLICIES[p].read_count for _, p, _ in attempts)
    devices = len({t["device_id"] for t in plan["blocks"]})
    return dict(basis="expected_on_successful_completion", policy_attempts=len(attempts),
        measured_trial_readings=reads, validation_replay_passes=list(phases),
        validation_replay_readings=reads*len(phases),
        enrollment_setup=dict(execution_reference_readings=devices,
            validation_reference_readings=devices*len(phases),
            manufacturing_constructions=devices*(1+len(phases)),
            credential_and_helper_constructions=devices*(1+len(phases)),
            execution_endpoint_pairs=len(attempts),
            shared_noise_vectors=len(attempts)*(1+len(phases))),
        total_simulator_measurement_invocations=(reads+devices)*(1+len(phases)),
        additional_audit=dict(validation_replay_readings=reads, reference_readings=devices,
                              statistical_samples_added=0))


def execution_resources(rows, catalog):
    return dict(policy_attempts_started=len(rows),
        policy_attempts_completed=sum(r["execution_status"] == "completed" for r in rows),
        measured_trial_invocations=sum(r["actual_reads"] for r in rows),
        measured_trial_observations=sum(len(r["observations"]) for r in rows),
        completed_enrollment_reference_readings=len(catalog))


def completion_resources(rows, catalog, passes):
    return dict(basis="observed_completed_work", execution=execution_resources(rows, catalog),
                validation_replays=passes, statistical_samples_added_by_replay=0)


def checked_output_path(directory, mode, *, test_output_root=None):
    """One direct child of the fixed namespace, or an explicit isolated test root.

    Reject aliases on every existing ancestor before resolve(), including Windows
    junctions. Namespace checks are case folded on all platforms. No untrusted
    concurrent filesystem writer is supported (path checks cannot prevent races).
    """
    raw = os.fspath(directory)
    windows = PureWindowsPath(raw)
    require(not raw.startswith(("\\\\", "//")) and not (windows.drive and not windows.root),
            "UNC/device/drive-relative output paths are unsupported")
    require(".." not in re.split(r"[/\\]", raw), "output traversal is forbidden")
    candidate = Path(raw).absolute()
    prefix = TEST_PREFIX if mode == "unit-test" else RUN_PREFIX
    require(re.fullmatch(re.escape(prefix)+r"[a-z0-9][a-z0-9-]{0,63}", candidate.name) is not None,
            "incorrect Week 7 nonformal/unit run-name prefix")
    require(not candidate.exists(), "output directory must be exclusively new")
    if mode == "unit-test":
        require(test_output_root is not None, "unit output requires an explicit test policy root")
        root = Path(test_output_root).absolute()
        require(".." not in re.split(r"[/\\]", os.fspath(test_output_root)), "test root traversal is forbidden")
        root_key = str(root.resolve()).casefold()
        historical_key = str((ROOT/"results").resolve()).casefold()
        require(root_key != historical_key and not root_key.startswith(historical_key+os.sep),
                "test output cannot use repository evidence trees")
        require(any(root_key.startswith(str(p.resolve()).casefold()+os.sep)
                    for p in (ROOT/"tmp", Path(tempfile.gettempdir()))),
                "test policy requires an isolated directory beneath a temporary root")
    else:
        require(test_output_root is None, "test output policy is restricted to unit-test mode")
        root = NONFORMAL_ROOT.absolute()
    for path in (candidate, root):
        for ancestor in (path, *path.parents):
            require(not ancestor.is_symlink() and not ancestor.is_junction(), "linked output ancestor is forbidden")
            require(ancestor.name.rstrip(" .") == ancestor.name and ":" not in ancestor.name,
                    "Windows path alias is forbidden")
            require(ancestor.name.casefold() not in ("week-5", "week-6", "week5", "week6", "sim_results")
                    and not ancestor.name.casefold().startswith(("tier1-v2-formal-", "week6-reconstruction-alternatives-")),
                    "historical evidence tree is forbidden")
            require(not any((ancestor/name).is_file() for name in
                    ("manifest.json", "source-manifest.json", "COMPLETE", "INCOMPLETE.json")),
                    "output nested inside existing evidence is forbidden")
    resolved, allowed = candidate.resolve(), root.resolve()
    require(str(resolved.parent).casefold() == str(allowed).casefold(), "output escapes permitted namespace")
    require(not candidate.exists(), "output directory must be exclusively new")
    return resolved


def file_digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def source_paths():
    files = {p.relative_to(ROOT).as_posix() for p in (ROOT/"src/python/puf_snn").rglob("*.py")}
    files.update(("src/python/scripts/run_majority3_auth_correlated.py", "pyproject.toml", "requirements.txt",
                  "configs/majority3_auth_correlated_v1.json", "configs/authentication_v2.json",
                  "configs/authentication_v2_majority3_acquisition.json"))
    files.update(f"schemas/majority3-auth-{kind}-v1.schema.json" for kind in ("config", "plan", "attempt", "summary"))
    files.update(f"schemas/majority3-auth-{kind}-v2.schema.json" for kind in ("attempt", "summary"))
    return sorted(files)


def source_hashes():
    for name, module in tuple(sys.modules.items()):
        if name == "puf_snn" or name.startswith("puf_snn."):
            path = getattr(module, "__file__", None)
            require(path is not None and Path(path).resolve().is_relative_to(ROOT/"src/python/puf_snn"),
                    "imported project source is outside the recorded checkout")
    return {path: file_digest(ROOT/path) for path in source_paths()}


def environment():
    return dict(executable=sys.executable, python=sys.version, implementation=platform.python_implementation(),
                platform=platform.platform(), packages={name: importlib.metadata.version(name)
                for name in ("galois", "numpy", "numba", "scipy", "jsonschema")})


def git_state():
    def git(*args):
        return subprocess.run(["git", "-c", f"safe.directory={ROOT.as_posix()}", *args],
                              cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
    return dict(head=git("rev-parse", "HEAD"), branch=git("branch", "--show-current"),
                status=git("status", "--porcelain=v1", "--untracked-files=all"))


def safe_path(directory, relative):
    require(type(relative) is str and relative and "\\" not in relative and ":" not in relative,
            "unsafe evidence path")
    parts = PurePosixPath(relative)
    require(not parts.is_absolute() and all(p not in (".", "..") for p in parts.parts)
            and parts.as_posix() == relative, "unsafe evidence path")
    target = directory.joinpath(*parts.parts)
    require(target.resolve().is_relative_to(directory.resolve()), "evidence path escapes directory")
    for path in (target, *target.parents):
        if path == directory.parent:
            break
        require(not path.is_symlink() and not path.is_junction(), "linked evidence is unsupported")
    return target


def write_json(path, obj):
    with Path(path).open("xb") as stream:
        stream.write(canonical(obj)+b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_json(path):
    return read_json_bytes(Path(path).read_bytes())


def validate_protocol(row, *, fresh_enabled_study=True):
    """Reconcile both directions of the supported serial production path.

    Endpoint flags are sampled immediately after establish(), before a window
    can expire/close a session. A receiver may be active when the sender times out.
    This is semantic consistency, not remote attestation of unsigned records.
    """
    r, e = row["reconstruction"], row["establishment"]
    require(r is not None and e is not None, "missing completed runtime outcome")
    kind = r["classification"]
    verification, authorization = row["verification_outcomes"], row["authorization_outcomes"]
    diagnostics, handshake = row["authorization_diagnostics"], row["handshake"]
    require(e["reconstruction_outcome"] == r["outcome"], "reconstruction/establishment mismatch")
    require(not any(d.endswith("fault") for d in diagnostics), "authorization execution fault prevents completion")
    if kind in "DI":
        require(verification == authorization == diagnostics == [], "failed reconstruction advanced admission")
        expected = ("reject", "reconstruction", "failed_reconstruction", False, False)
    else:
        if diagnostics == ["policy_refusal"]:
            require(verification == ["record_disabled"] and authorization == [False], "invalid policy refusal")
            require(not fresh_enabled_study, "policy refusal is outside the fresh enabled study design")
        else:
            require(verification == (["verified"] if kind == "C" else ["credential_mismatch"]),
                    "truth classification inconsistent with independent verification")
            require(authorization == [kind == "C"] and
                    diagnostics == (["issued"] if kind == "C" else ["credential_mismatch"]),
                    "authorization issuance contradicts verification")
        if not e["request_emitted"]:
            # Even a minted capability can expire during bind_request().
            expected = ("reject", "credential_admission", "credential_verification_failed", False, False)
        else:
            require(kind == "C" and authorization == [True], "request lacks authorization")
            names = [h["stage"] for h in handshake]
            stages = ["receiver_challenge", "sender_confirmation", "receiver_confirmation", "sender_activation"]
            require(names in (stages[:2], stages), "handshake stage ordering mismatch")
            rejection_reasons = {
                "receiver_challenge": {"unsupported_protocol_version", "unknown_device", "session_busy",
                    "resource_limit", "credential_verification_failed", "malformed_message"},
                "sender_confirmation": {"handshake_timeout", "session_refused", "inactive_session",
                    "invalid_challenge", "unsupported_protocol_version", "credential_verification_failed",
                    "malformed_message"},
                "receiver_confirmation": {"handshake_timeout", "key_confirmation_failed", "inactive_session",
                    "unknown_session", "unsupported_protocol_version", "malformed_message"},
                "sender_activation": {"handshake_timeout", "session_refused", "inactive_session",
                    "invalid_challenge", "key_confirmation_failed", "expired_session",
                    "unsupported_protocol_version", "malformed_message"},
            }
            for h in handshake:
                require((h["result"] == "accept" and h["reason"] == "accepted") or
                        (h["result"] == "reject" and h["reason"] in rejection_reasons[h["stage"]]),
                        "handshake decision/reason mismatch")
            challenge, confirmation = handshake[:2]
            if challenge["result"] == "reject":
                require(len(handshake) == 2 and confirmation["result"] == "reject"
                        and confirmation["reason"] in ("session_refused", "handshake_timeout"),
                        "receiver refusal advanced handshake")
                expected = ("reject", "receiver_admission", challenge["reason"], True, False)
            elif confirmation["result"] == "reject":
                require(len(handshake) == 2 and confirmation["reason"] != "session_refused",
                        "sender refusal advanced handshake")
                expected = ("reject", "sender_confirmation", confirmation["reason"], True, False)
            else:
                require(len(handshake) == 4, "successful session lacks terminal handshake")
                receiver, sender = handshake[2:]
                if receiver["result"] == "reject":
                    require(sender["result"] == "reject" and sender["reason"] in ("session_refused", "handshake_timeout"),
                            "receiver rejection contradicts sender activation")
                    expected = ("reject", "mutual_confirmation", receiver["reason"], True, False)
                elif sender["result"] == "reject":
                    require(sender["reason"] != "session_refused", "successful receiver confirmation recorded as refusal")
                    expected = ("reject", "mutual_confirmation", sender["reason"], True, False)
                else:
                    expected = ("accept", "active_session", "accepted", True, True)
    require(tuple(e[k] for k in ("decision", "stage", "reason", "request_emitted", "session_active")) == expected,
            "establishment contradicts terminal protocol outcome")
    if not e["request_emitted"]:
        require(not handshake, "refused request has handshake state")
    sender_active = len(handshake) == 4 and handshake[3]["result"] == "accept"
    receiver_active = len(handshake) == 4 and handshake[2]["result"] == "accept"
    require(row["endpoint_state"] == dict(sender_active=sender_active, receiver_active=receiver_active),
            "handshake contradicts endpoint activation")
    counts = Counter(s["stage"] for s in row["timing"])
    require(counts["receiver_hkdf"] == int(bool(handshake) and handshake[0]["result"] == "accept")
            and counts["sender_hkdf"] == int(bool(handshake) and handshake[1]["result"] == "accept"),
            "conditional HKDF/handshake mismatch")
    window, verified = row["window"], row["window_verifications"]
    require((window is not None) == e["session_active"], "protected-window eligibility mismatch")
    accepted = False
    if window is None:
        require(verified == [], "failed establishment verified a window")
    elif window["stage"] == "sender_sealing":
        require(window["decision"] == "reject" and window["reason"] in
                ("expired_session", "inactive_session", "session_limit_reached", "invalid_payload_schema",
                 "data_quality_failure", "sequence_out_of_range", "malformed_message")
                and window["sequence_number"] is None and verified == [], "invalid sender window refusal")
    else:
        require(window["stage"] == "window_verification" and len(verified) == 1,
                "window lacks real verifier outcome")
        v = verified[0]
        require({k: window[k] for k in ("decision", "reason", "sequence_number")} ==
                {k: v[k] for k in ("decision", "reason", "sequence_number")}, "window/verifier outcome mismatch")
        accepted = v["decision"] == "accept"
        # VerificationResult deliberately omits untrusted sequence IDs on reject.
        reject_reasons = {"expired_session", "inactive_session", "session_limit_reached", "invalid_tag",
            "unknown_device", "unknown_session", "device_session_mismatch", "invalid_key_id",
            "invalid_payload_schema", "unsupported_protocol_version", "duplicate_sequence", "stale_sequence",
            "future_sequence_gap", "data_quality_failure", "sequence_out_of_range", "malformed_message"}
        require((accepted and v["reason"] == "accepted" and v["sequence_number"] == 0 and v["authenticated"])
                or (not accepted and v["reason"] in reject_reasons and v["sequence_number"] is None
                    and not v["authenticated"]), "window decision/reason/authentication mismatch")
    require(row["unauthorized_release_count"] == 0 and
            row["release_count"] == row["authorized_release_count"] == int(accepted),
            "session/release consistency failure")
    require(row["model_calls"] == {k: int(accepted) for k in ("preprocessing", "motion", "anomaly")},
            "consumer invocation mismatch")


def validate_timing(row):
    spans = row["timing"]
    require([s["id"] for s in spans] == list(range(len(spans))), "timing identities are not consecutive")
    parents = {"acquisition":"establishment", "reading":"acquisition", "voting":"acquisition",
        "reconstruction":"establishment", "bch_decode":"reconstruction", "admission_request":"establishment",
        "verification":"authorization", "authorization":"admission_request", "mutual_handshake":"establishment",
        "receiver_challenge":"mutual_handshake", "sender_confirmation":"mutual_handshake",
        "receiver_confirmation":"mutual_handshake", "sender_activation":"mutual_handshake",
        "sender_hkdf":"sender_confirmation", "receiver_hkdf":"receiver_challenge",
        "window_seal":"first_window", "window_verify":"first_window", "release":"first_window"}
    for s in spans:
        require(s["stage"] in STAGES and not s["exception"], "exceptional or unknown completed timing span")
        parent = s["parent_id"]
        if parent is None:
            require(s["stage"] in ("establishment", "first_window"), "unexpected timing root")
        else:
            require(0 <= parent < s["id"], "invalid timing parent")
            p = spans[parent]
            require(p["stage"] == parents[s["stage"]], "incorrect timing nesting")
            require(p["start_ns"] <= s["start_ns"] and s["start_ns"]+s["duration_ns"] <= p["start_ns"]+p["duration_ns"],
                    "timing child outside parent")
    for parent in [None] + list(range(len(spans))):
        children = sorted((s for s in spans if s["parent_id"] == parent), key=lambda s: s["start_ns"])
        require(all(a["start_ns"]+a["duration_ns"] <= b["start_ns"] for a,b in zip(children,children[1:])),
                "overlapping sibling timing spans")
    counts = Counter(s["stage"] for s in spans)
    expected = dict(establishment=1, acquisition=1, reading=row["expected_reads"],
                    voting=int(row["expected_reads"] == 3), reconstruction=1, bch_decode=1,
                    admission_request=1, verification=len(row["verification_outcomes"]),
                    authorization=len(row["authorization_outcomes"]),
                    mutual_handshake=int(row["establishment"]["request_emitted"]),
                    first_window=int(row["establishment"]["session_active"]),
                    window_seal=int(row["establishment"]["session_active"]),
                    window_verify=int(row["window"] is not None and row["window"]["stage"] == "window_verification"),
                    release=row["release_count"])
    for stage, count in expected.items():
        require(counts[stage] == count, "timing invocation count mismatch: "+stage)
    for stage in ("receiver_challenge","sender_confirmation","receiver_confirmation","sender_activation"):
        require(counts[stage] == sum(h["stage"] == stage for h in row["handshake"]), "handshake/span mismatch")
    for stage in ("sender_hkdf", "receiver_hkdf", "window_verify"):
        require(counts[stage] <= 1, "duplicate conditional stage")
    for s in spans:
        if s["stage"] in ("sender_hkdf", "receiver_hkdf"):
            verified = [v for v in spans if v["stage"] == "verification"]
            require(len(verified) == 1 and row["verification_outcomes"] == ["verified"]
                    and row["authorization_outcomes"] == [True]
                    and verified[0]["start_ns"]+verified[0]["duration_ns"] <= s["start_ns"],
                    "HKDF preceded independent verification/authorization")
    if row["establishment"]["session_active"]:
        require(counts["sender_hkdf"] == counts["receiver_hkdf"] == 1, "active session lacks real HKDF")
    order = ("establishment", "acquisition", "reading", "voting", "reconstruction", "bch_decode",
             "admission_request", "authorization", "verification", "mutual_handshake", "receiver_challenge",
             "receiver_hkdf", "sender_confirmation", "sender_hkdf", "receiver_confirmation", "sender_activation",
             "first_window", "window_seal", "window_verify", "release")
    require([s["stage"] for s in spans] == [stage for stage in order for _ in range(counts[stage])],
            "timing execution order mismatch")


def reconcile(config, plan, rows, catalog, context):
    validate_plan(config, plan)
    expected = list(scheduled_attempts(plan))
    require(len(rows) == len(expected), "missing or additional policy attempts")
    require(len({r["policy_attempt_id"] for r in rows}) == len(rows), "duplicate policy attempts")
    require(set(catalog) == {t["device_id"] for t in plan["blocks"]}, "enrollment catalog mismatch")
    materials = {}
    for trial in plan["blocks"]:
        device_id = trial["device_id"]
        if device_id not in materials:
            material = enrollment_material(config, trial["population_id"], device_id)
            materials[device_id] = material
            require(catalog[device_id] == public_enrollment_record(trial["population_id"], *material[:3]),
                    "catalog does not match deterministic enrollment inputs")
    paired, common = {}, {}
    replay_readings = 0
    for row, (trial, policy, ordinal) in zip(rows, expected):
        validate_schema("attempt", row)
        require(row["execution_status"] == "completed" and row["fault_code"] is None, "faulted attempt prevents completion")
        for key in ("experiment_id","population_id","device_id","enrollment_id","condition","attempt_index","trial_id"):
            require(row[key] == trial[key], "trial identity mismatch")
        require(row["policy"] == policy and row["execution_index"] == ordinal
                and row["policy_attempt_id"] == attempt_id(trial, policy), "execution schedule mismatch")
        for key, value in dict(config_sha256=config.digest, plan_sha256=plan["plan_sha256"], **context).items():
            require(row[key] == value, "source/configuration/run identity mismatch")
        enrollment = catalog[row["device_id"]]
        require(row["enrollment_sha256"] == object_digest(enrollment), "enrollment identity mismatch")
        require(row["expected_reads"] == row["actual_reads"] == len(row["observations"]) == POLICIES[policy].read_count,
                "policy-specific reading count mismatch")
        require(row["session_seed_sha256"] == trial["session_seed_sha256"], "shared state identity mismatch")
        reference = enrollment["reference"]
        require(type(reference) is list and len(reference) == 64
                and all(type(b) is int and b in (0,1) for b in reference), "malformed reference")
        for i, observation in enumerate(row["observations"]):
            require(observation["index"] == i and observation["input_seed_sha256"] == trial["reading_seed_sha256"][i],
                    "reading input identity mismatch")
            require(observation["response_sha256"] == object_digest(observation["response"])
                    and observation["error_positions"] == errors(observation["response"], reference),
                    "raw response/error evidence mismatch")
        readings = tuple(tuple(o["response"]) for o in row["observations"])
        device, _, helper, credential = materials[row["device_id"]]
        replay = noise.CorrelatedResponseReader(device, trial_noise_config(trial),
                     noise.AttemptIdentity(**trial["noise_identity"]), POLICIES[policy])
        require(readings == tuple(replay() for _ in range(POLICIES[policy].read_count)),
                "recorded PUF inputs differ from deterministic replay")
        replay_readings += replay.measurement_count
        effective = readings[0] if len(readings) == 1 else majority_vote3(readings)
        require(row["effective_response"] == list(effective) and row["effective_sha256"] == object_digest(effective)
                and row["effective_error_positions"] == errors(effective, reference), "effective response mismatch")
        r, e = row["reconstruction"], row["establishment"]
        require(r is not None and e is not None, "missing completed runtime outcome")
        classification = r["classification"]
        decoded = reconstruct(effective, helper)
        expected_class = ("D" if decoded.outcome == "decoder_failure" else
                          "I" if decoded.outcome == "invalid_format_or_padding" else
                          "C" if decoded.candidate_credential == credential else "W")
        require(r == dict(outcome=decoded.outcome, decoder_status=decoded.decoder_status,
                          corrections=decoded.reported_correction_count, classification=expected_class),
                "reconstruction does not match independent decoder/truth replay")
        require(r["outcome"] == {"C":"candidate_valid_format","W":"candidate_valid_format",
                                 "D":"decoder_failure","I":"invalid_format_or_padding"}[classification]
                and e["reconstruction_outcome"] == r["outcome"], "invalid reconstruction partition")
        require((r["decoder_status"], r["corrections"]) == ("uncorrectable",-1) if classification == "D"
                else r["decoder_status"] == "decoded" and 0 <= r["corrections"] <= 5, "invalid decoder metadata")
        validate_protocol(row)
        validate_timing(row)
        key = row["trial_id"]
        first = (row["observations"][0], row["session_seed_sha256"], row["enrollment_sha256"])
        if key in paired:
            require(paired[key] == first, "policies do not share reading zero/enrollment/session input")
        paired[key] = first
        if row["condition"] in ("independent_nominal","common_control"):
            alias = (row["population_id"], row["device_id"], row["attempt_index"], policy)
            match = (row["observations"], row["session_seed_sha256"])
            if alias in common:
                require(common[alias] == match, "common-mode control does not alias nominal realization")
            common[alias] = match
    require(sum(r["actual_reads"] for r in rows) == plan["counts"]["expected_reads"], "total reading count mismatch")
    return dict(status="PASS", policy_attempts=len(rows), matched_trials=len(paired),
                actual_reads=sum(r["actual_reads"] for r in rows), unauthorized_releases=0,
                evidence_version=EVIDENCE_VERSION,
                validation_work=dict(replay_measurement_invocations=replay_readings,
                                     enrollment_reference_readings=len(materials),
                                     manufacturing_constructions=len(materials),
                                     credential_and_helper_constructions=len(materials),
                                     shared_noise_vectors=len(rows), statistical_samples_added=0))


def marker_name(config):
    require(config.to_dict()["mode"] != "planned-formal", "formal completion is not implemented")
    return "UNIT_TEST_VALIDATED.json" if config.to_dict()["mode"] == "unit-test" else "NONFORMAL_VALIDATED.json"


def audit_evidence(directory, *, require_marker=True):
    """Does not write evidence; replays simulator/decoder work and may warm caches.

    Interpreter/Numba caches outside the evidence directory are environment
    dependent. Hash closure is integrity evidence, not a signature.
    """
    directory = Path(directory).absolute()
    require(directory.is_dir() and not directory.is_symlink() and not directory.is_junction(), "invalid evidence directory")
    manifest = read_json(safe_path(directory, "manifest.json"))
    require(type(manifest) is dict and manifest, "missing artifact manifest")
    required_files = {"config.json","trial-plan.json","metadata.json","source-manifest.json",
                      "enrollments.json","attempts.jsonl","summary.json","validation.json"}
    require(set(manifest) == required_files | {"source/"+p for p in source_paths()}, "manifest member set mismatch")
    config = StudyConfig.from_dict(read_json(safe_path(directory, "config.json")))
    marker = marker_name(config)
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
    allowed = set(manifest) | {"manifest.json", marker}
    if not require_marker:
        allowed.add("INCOMPLETE.json")
    require(actual <= allowed and set(manifest) <= actual, "manifest closure failure")
    require(not {"manifest.json",marker,"INCOMPLETE.json","COMPLETE"} & set(manifest), "invalid manifest members")
    for relative, digest in manifest.items():
        require(file_digest(safe_path(directory, relative)) == digest, "artifact hash mismatch")
    metadata = read_json(safe_path(directory, "metadata.json"))
    require(metadata["experiment_id"] == VERSION and metadata["config_sha256"] == config.digest,
            "metadata configuration mismatch")
    require(metadata.get("evidence_version") == EVIDENCE_VERSION, "unsupported evidence revision")
    require(metadata.get("mode") == config.to_dict()["mode"]
            and metadata.get("consumer_id") == "recording-consumer-v1", "metadata execution profile mismatch")
    require(metadata.get("disclosure") == DISCLOSURE and "secrets_persisted" not in metadata,
            "incorrect synthetic credential disclosure")
    prefix = TEST_PREFIX if config.to_dict()["mode"] == "unit-test" else RUN_PREFIX
    require(re.fullmatch(re.escape(prefix)+r"[a-z0-9][a-z0-9-]{0,63}", metadata["run_id"]) is not None,
            "incorrect evidence run identity")
    source = read_json(safe_path(directory, "source-manifest.json"))
    require(source["source_id"] == object_digest(source["files"]) == metadata["source_id"], "source identity mismatch")
    require(source["files"] == source_hashes(), "current source differs from recorded execution source")
    for relative, digest in source["files"].items():
        require(file_digest(safe_path(directory, "source/"+relative)) == digest, "source snapshot mismatch")
    require(metadata["environment"] == environment(), "executing environment differs from recorded environment")
    plan = read_json(safe_path(directory, "trial-plan.json"))
    require(metadata["plan_sha256"] == plan["plan_sha256"], "metadata plan mismatch")
    require(metadata.get("resource_estimate") == resource_estimate(plan), "resource estimate mismatch")
    catalog = read_json(safe_path(directory, "enrollments.json"))
    lines = safe_path(directory, "attempts.jsonl").read_bytes().splitlines()
    require(all(line.strip() for line in lines), "blank attempt record")
    rows = [read_json_bytes(line) for line in lines]
    context = dict(run_id=metadata["run_id"], source_id=metadata["source_id"])
    receipt = reconcile(config, plan, rows, catalog, context)
    summary = read_json(safe_path(directory, "summary.json"))
    validate_schema("summary", summary)
    expected = dict(schema_version=EVIDENCE_VERSION+":summary", experiment_id=VERSION, **context,
                    config_sha256=config.digest, plan_sha256=plan["plan_sha256"], analysis=summarize(config, rows))
    require(summary == expected, "summary is not recomputable from recorded attempts")
    require(read_json(safe_path(directory, "validation.json")) == receipt, "validation receipt mismatch")
    if require_marker:
        require(not (directory/"INCOMPLETE.json").exists(), "run is incomplete")
        passes = [dict(phase=phase, **receipt["validation_work"]) for phase in FINALIZATION_REPLAYS]
        expected_marker = dict(experiment_id=VERSION, mode=config.to_dict()["mode"],
            manifest_sha256=file_digest(directory/"manifest.json"),
            resource_accounting=completion_resources(rows, catalog, passes), **receipt)
        require(read_json(safe_path(directory, marker)) == expected_marker, "completion marker mismatch")
        return dict(**receipt, resource_accounting=expected_marker["resource_accounting"])
    return receipt


class EvidenceRun:
    """Exclusive output owner. Unit fixtures and separately authorized nonformal only."""
    def __init__(self, directory, config, *, authorization=None, reviewed_plan_sha256=None, test_output_root=None):
        mode = config.to_dict()["mode"]
        require(mode in ("unit-test","nonformal"), "formal execution is disabled")
        plan = compile_plan(config)
        if mode == "nonformal":
            require(authorization == "RUN-100-NONFORMAL", "nonformal execution requires explicit authorization")
            require(reviewed_plan_sha256 == plan["plan_sha256"], "incorrect reviewed plan hash")
        self.config, self.plan = config, plan
        self.directory = checked_output_path(directory, mode, test_output_root=test_output_root)
        self.hashes = source_hashes()
        self.metadata = dict(experiment_id=VERSION, run_id=self.directory.name, source_id=object_digest(self.hashes),
            config_sha256=config.digest, plan_sha256=plan["plan_sha256"], git=git_state(), environment=environment(),
            mode=mode, consumer_id="recording-consumer-v1", evidence_version=EVIDENCE_VERSION,
            disclosure=dict(DISCLOSURE), resource_estimate=resource_estimate(plan))
        self.rows, self.catalog = [], {}
        self.stream = None
        self.directory.mkdir(parents=True, exist_ok=False)
        write_json(self.directory/"INCOMPLETE.json", dict(experiment_id=VERSION, reason="not_finalized"))
        try:
            write_json(self.directory/"config.json", config.to_dict())
            write_json(self.directory/"trial-plan.json", plan)
            write_json(self.directory/"metadata.json", self.metadata)
            for relative, digest in self.hashes.items():
                data = (ROOT/relative).read_bytes()
                require(sha256(data).hexdigest() == digest, "source changed during snapshot")
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
        if self.stream is not None and not self.stream.closed:
            self.stream.flush()
            os.fsync(self.stream.fileno())
            self.stream.close()

    def append(self, row):
        validate_schema("attempt", row)
        require(self.stream is not None and not self.stream.closed, "evidence stream is closed")
        self.stream.write(canonical(row)+b"\n")
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.rows.append(row)

    def execute(self):
        """Never called by validation/inspection. No automatic retry/resume."""
        try:
            enrollments = prepare_population(self.config, self.plan)
            self.catalog = {d:e.public_record() for d,e in enrollments.items()}
            write_json(self.directory/"enrollments.json", self.catalog)
            for trial, policy, index in scheduled_attempts(self.plan):
                require(source_hashes() == self.hashes, "source changed before attempt")
                row = execute_attempt(self.config, trial, policy, enrollments[trial["device_id"]],
                    run_id=self.metadata["run_id"], source_id=self.metadata["source_id"],
                    plan_sha256=self.plan["plan_sha256"], execution_index=index)
                self.append(row)
                require(row["execution_status"] == "completed", "execution fault; incomplete evidence retained")
            return self.finalize()
        except Exception:
            # Only replace this owner's sentinel. Counts cover persisted rows;
            # work interrupted before observation/append is explicitly unknown.
            with (self.directory/"INCOMPLETE.json").open("wb") as stream:
                stream.write(canonical(dict(experiment_id=VERSION, evidence_version=EVIDENCE_VERSION,
                    reason="execution_or_validation_fault", observed_execution=execution_resources(self.rows, self.catalog),
                    unrecorded_or_interrupted_work="unknown"))+b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            raise

    def finalize(self):
        self.close()
        require(source_hashes() == self.hashes, "source changed during execution")
        context = dict(run_id=self.metadata["run_id"], source_id=self.metadata["source_id"])
        require(FINALIZATION_REPLAYS and FINALIZATION_REPLAYS[0] == "pre_summary"
                and all(p == "manifest_audit" for p in FINALIZATION_REPLAYS[1:])
                and len(FINALIZATION_REPLAYS) >= 2, "independent finalization audit is required")
        receipt = reconcile(self.config, self.plan, self.rows, self.catalog, context)
        passes = [dict(phase=FINALIZATION_REPLAYS[0], **receipt["validation_work"])]
        summary = dict(schema_version=EVIDENCE_VERSION+":summary", experiment_id=VERSION, **context,
                       config_sha256=self.config.digest, plan_sha256=self.plan["plan_sha256"],
                       analysis=summarize(self.config, self.rows))
        validate_schema("summary", summary)
        write_json(self.directory/"summary.json", summary)
        write_json(self.directory/"validation.json", receipt)
        manifest = {p.relative_to(self.directory).as_posix():file_digest(p) for p in sorted(self.directory.rglob("*"))
                    if p.is_file() and p.name != "INCOMPLETE.json"}
        write_json(self.directory/"manifest.json", manifest)
        for phase in FINALIZATION_REPLAYS[1:]:
            audited = audit_evidence(self.directory, require_marker=False)
            passes.append(dict(phase=phase, **audited["validation_work"]))
        require(source_hashes() == self.hashes, "source changed before completion")
        write_json(self.directory/marker_name(self.config), dict(experiment_id=VERSION,
            mode=self.config.to_dict()["mode"],
            manifest_sha256=file_digest(self.directory/"manifest.json"),
            resource_accounting=completion_resources(self.rows, self.catalog, passes), **receipt))
        # Only this run's own initial sentinel is removed, after full validation.
        (self.directory/"INCOMPLETE.json").unlink()
        return dict(**receipt, resource_accounting=completion_resources(self.rows, self.catalog, passes))
