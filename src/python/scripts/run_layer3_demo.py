"""Legitimate synthetic Layer 3 path only; no PUF readings or attack trials."""
from dataclasses import asdict
from datetime import datetime, timezone
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import secrets
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/python"))

from puf_snn.auth.audit import AuditJSONL, Provenance, latency_summary, summarize_ns
from puf_snn.auth.binary_window import F32, Sample, Window
from puf_snn.auth.config import AuthConfig
from puf_snn.auth.sender import Sender
from puf_snn.auth.session import Failure, RegistryEntry, provision_device
from puf_snn.auth.verifier import Verifier


def synthetic_window():
    zero, one = F32(0), F32(0x3f800000)
    samples = tuple(Sample(i, 1_000_000_000 + i*16_666_667, (zero,)*3, (zero,zero,zero,one), True)
                    for i in range(120))
    return Window("synthetic-device", bytes(16), 0, "synthetic-window", 1_000_000_000,
                  3_000_000_000, 120, 1_000_000, samples)


def initialize_material():
    # Explicit synthetic candidate, not a claimed reconstruction observation.
    # Enrollment initializes the frozen algebra outside the measured stages.
    from puf_snn.reconstruction import ReconstructionResult, enroll
    credential = bytes.fromhex("00000001")
    helper = enroll((0,)*64, credential, enrollment_id="synthetic-enrollment")
    bits = tuple((byte >> shift) & 1 for byte in credential for shift in range(7,-1,-1)) + (0,)*4
    candidate = ReconstructionResult("candidate_valid_format", "decoded", 0, bits, credential, True, None)
    return (provision_device("synthetic-device", "synthetic-enrollment", helper),
            RegistryEntry("synthetic-device", "synthetic-enrollment", credential), candidate)


def establish(config, material, local_provenance=None):
    binding, entry, candidate = material
    sender = Sender(binding, config.session_config().limits)
    verifier = Verifier([entry], config.session_config())
    start = time.perf_counter_ns()
    request = sender.begin_attempt(candidate, "synthetic-attempt", local_provenance=local_provenance)
    challenge = verifier.begin_session(request, local_provenance)
    confirmation = sender.answer_challenge(challenge)
    response = verifier.confirm_session(confirmation)
    active = sender.finish_session(response)
    elapsed = time.perf_counter_ns() - start
    if isinstance(active, Failure):
        raise RuntimeError("synthetic session establishment failed")
    return sender, verifier, elapsed


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_demo(output, config_path=ROOT / "configs/authentication_v1.json"):
    config = AuthConfig.load(config_path)
    if config.max_windows < 3:
        raise ValueError("the legitimate sequence demo requires max_windows >= 3")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    writer = None
    sender_writer = None
    sender = None
    verifier = None
    try:
        startup = time.perf_counter_ns()
        material = initialize_material()
        motion = synthetic_window()
        config_bytes = Path(config_path).read_bytes()
        config_hash = hashlib.sha256(config_bytes).hexdigest()
        (output / "config.json").write_bytes(config_bytes)
        sources = list((ROOT / "src/python/puf_snn/auth").glob("*.py")) + [Path(__file__),
                   ROOT / "schemas/auth-audit-v1.schema.json", ROOT / "schemas/authenticated-window-v2.schema.json"]
        source_hashes = {str(path.relative_to(ROOT)).replace('\\','/'): sha256(path) for path in sources}
        startup_ns = time.perf_counter_ns() - startup
        # Each iteration owns fresh isolated state and OS session randomness.
        # Fixed synthetic motion/candidate, no experimental PUF read consumption.
        for _ in range(config.warmup_iterations):
            warm_sender, warm_verifier, _ = establish(config, material)
            result = warm_verifier.verify_window(warm_sender.seal_window(motion))
            if result.result != "accept":
                raise RuntimeError("synthetic warmup failed")
            warm_verifier.close_all_sessions()
        if config.warmup_iterations:
            del warm_sender, warm_verifier, result

        session_provenance = Provenance(run_id=output.name, source_id="fixed-synthetic-binary32-v1",
                                        config_sha256=config_hash, source_record_id="synthetic-attempt")
        sender, verifier, establishment_ns = establish(config, material, session_provenance)
        sid = sender.session_id
        metadata = dict(run_id=output.name, source="fixed-synthetic-binary32-v1",
                        candidate_source="explicit-synthetic-correct-candidate; no reconstruction measured",
                        warmup_iterations=config.warmup_iterations,
                        temperature="warm" if config.warmup_iterations else "cold",
                        startup_ns=startup_ns, session_establishment_ns=establishment_ns,
                        sender_kdf_ns=sender.kdf_timings_ns, verifier_kdf_ns=verifier.kdf_timings_ns,
                        reconstruction_ns=None, config_sha256=config_hash,
                        source_hashes=source_hashes, python=sys.version, platform=platform.platform(),
                        machine=platform.machine(), processor=platform.processor(),
                        backend_versions={name: version(name) for name in ("galois", "numpy")},
                        timer="time.perf_counter_ns", timer_resolution_seconds=time.get_clock_info("perf_counter").resolution,
                        audit_io_allocation="batch_only; audit row slots remain null",
                        performance_target_verdict=None)
        write_json(output / "metadata.json", metadata)
        writer = AuditJSONL(output)
        (output / "sender").mkdir()
        sender_writer = AuditJSONL(output / "sender")
        latency_rows = []
        for seq in range(3):
            local = Provenance(run_id=output.name, source_id=metadata['source'],
                               config_sha256=config_hash, source_record_id=f"window-{seq}")
            envelope = sender.seal_window(motion, local_provenance=local)
            if isinstance(envelope, Failure):
                raise RuntimeError("synthetic sender failed")
            result = verifier.verify_window(envelope, local)
            # Release only through the verifier-owned immutable result boundary.
            if result.result != "accept":
                raise RuntimeError("legitimate synthetic window rejected")
            verifier.release_accepted(result, lambda accepted: accepted.sequence_number)
            row = next(r for r in verifier.audit_records if r['event_id'] == result.event_id)
            paired = dict(row['latency_ns'])
            paired.update(sender_prepare=sender.last_window_timing.sender_prepare_ns,
                          sender_hmac=sender.last_window_timing.sender_hmac_ns)
            latency_rows.append(dict(event_id=result.event_id, decision=result.result,
                                     reason=result.reason, source_record_id=local.source_record_id, latency_ns=paired))
            verifier.flush_audit(writer)
            sender.flush_audit(sender_writer)
        status = verifier.session_status(sid)
        if (status.accepted_count, status.last_accepted) != (3, 2):
            # max_windows=3 closes after final acceptance; validate via audit.
            accepted = [r for r in verifier.audit_records if r['event_type']=='window' and r['decision']=='accept']
            if config.max_windows != 3 or [r['sequence_number'] for r in accepted] != [0,1,2]:
                raise RuntimeError("consecutive state invariant failed")
        verifier.close_all_sessions()
        verifier.flush_audit(writer)
        sender.flush_audit(sender_writer)
        writer.close()
        sender_writer.close()
        write_json(output / "latency-records.json", latency_rows)
        write_json(output / "audit-io.json", writer.io_batches)
        write_json(output / "sender/audit-io.json", sender_writer.io_batches)
        summary = latency_summary(latency_rows)
        summary['session_establishment'] = summarize_ns([establishment_ns])
        summary['sender_kdf'] = summarize_ns(sender.kdf_timings_ns)
        summary['verifier_kdf'] = summarize_ns(verifier.kdf_timings_ns)
        summary['audit_io_batches'] = summarize_ns([b['audit_io_ns'] for b in writer.io_batches])
        write_json(output / "latency-summary.json", summary)
        if verifier.incomplete or sender.incomplete or writer.failed or sender_writer.failed:
            raise RuntimeError("incomplete evidence")
        audit = verifier.audit_records
        manifest = dict(run_id=output.name, config_sha256=config_hash, source_hashes=source_hashes,
                        window_decisions=3, accepted_windows=3, last_accepted=2,
                        audit_records=len(audit), warmup_rows_in_denominator=0,
                        sender_audit_records=len(sender.audit_records),
                        files={p.relative_to(output).as_posix(): sha256(p) for p in sorted(output.rglob("*")) if p.is_file()})
        write_json(output / "manifest.json", manifest)
        write_json(output / "COMPLETE", dict(accepted_windows=3, last_accepted=2))
        return output
    except BaseException:
        if sender_writer is not None:
            try:
                if sender is not None: sender.flush_audit(sender_writer)
                sender_writer.close()
            except Exception:
                pass
        if writer is not None:
            try:
                if verifier is not None: verifier.flush_audit(writer)
                writer.close()
            except Exception:
                pass
        try:
            (output / "INCOMPLETE").write_text("Layer 3 synthetic demo incomplete; preserve partial evidence.\n", encoding="utf-8")
        except OSError:
            pass
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/authentication_v1.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "results/week-4/will/authentication" / (
        datetime.now(timezone.utc).strftime("synthetic-%Y%m%dT%H%M%SZ-") + secrets.token_hex(4))
    try:
        result = run_demo(output, args.config)
    except Exception:
        print("Layer 3 demo failed; evidence is incomplete.", file=sys.stderr)
        return 1
    print(f"Synthetic seq 0, 1, 2 accepted. Evidence: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
