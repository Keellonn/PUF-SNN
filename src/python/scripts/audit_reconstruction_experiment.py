"""Independent read-only accounting audit; no decoder or simulator imports."""
from collections import Counter, defaultdict
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median

root = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--evidence", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    parser.error(f"Audit output already exists: {args.output}")
evidence = args.evidence

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))

def condition(r):
    return r["phase"], str(r["sweep_index"]), float(r["measurement_noise_std"])

def key(r, extra):
    return (*condition(r), *(str(r[k]) for k in extra))

complete = read_json(evidence / "COMPLETE")
assert complete["attempt_count"] == 84000
assert sha(evidence / "manifest.json") == complete["manifest_sha256"]
for name, fingerprint in read_json(evidence / "manifest.json").items():
    assert sha(evidence / name) == fingerprint, name
metadata = read_json(evidence / "metadata.json")
for name, fingerprint in metadata["source_sha256"].items():
    assert sha(root / name) == fingerprint, name
enrollments = read_json(evidence / "enrollments.json")
enrollment = {(r["simulation_seed"], r["device_id"]): r for r in enrollments}
assert len(enrollment) == len(enrollments) == 120
archived = {}
for run in metadata["runs"]:
    archive = Path(run["archive"])
    for name in ("metrics.csv", "noise_sweep.csv"):
        for r in read_csv(archive / name):
            identity = run["seed"], r["device_id"], r["phase"], r["sweep_index"], int(r["read_id"])
            assert identity not in archived
            archived[identity] = r["response"]
with (evidence / "attempts.jsonl").open(encoding="utf-8") as stream:
    rows = [json.loads(line) for line in stream]
assert len(rows) == len(archived) == 84000
seen = set()
within, beyond, exceptions = 0, 0, 0
for r in rows:
    identity = r["simulation_seed"], r["device_id"], r["phase"], str(r["sweep_index"]), r["attempt_number"]
    assert identity not in seen
    seen.add(identity)
    assert r["response64"] == archived[identity]
    e = enrollment[r["simulation_seed"], r["device_id"]]
    assert r["enrollment_id"] == e["enrollment_id"]
    assert r["credential_stream_identity"] == e["credential_stream_identity"]
    errors = [a != b for a, b in zip(r["response64"], e["evaluator_reference64"])]
    assert r["selected_response63"] == r["response64"][:63]
    assert r["evaluator_error_count64"] == sum(errors)
    assert r["evaluator_error_count63"] == sum(errors[:63])
    assert r["evaluator_ber63"] == sum(errors[:63]) / 63
    assert r["evaluator_ber64"] == sum(errors) / 64
    match = r["candidate_credential_hex"] == e["evaluator_enrolled_credential_hex"]
    assert r["evaluator_success"] is match
    assert r["backend_exception"] is None
    assert r["reconstruction_latency_ns"] >= 0
    if r["reconstruction_outcome"] == "decoder_failure":
        assert r["reported_correction_count"] == -1
        assert r["candidate_message36"] is None
        assert r["candidate_credential_hex"] is None
        assert r["evaluator_outcome"] == "no_valid_candidate"
    elif r["reconstruction_outcome"] == "invalid_format_or_padding":
        assert r["candidate_message36"][-4:] != "0000"
        assert r["candidate_credential_hex"] is None
        assert r["evaluator_outcome"] == "no_valid_candidate"
    else:
        assert r["reconstruction_outcome"] == "candidate_valid_format"
        assert r["candidate_message36"][-4:] == "0000"
        assert f"{int(r['candidate_message36'][:32], 2):08x}" == r["candidate_credential_hex"]
        assert r["evaluator_outcome"] == ("evaluator_correct_match" if match else "evaluator_wrong_match")
    if r["evaluator_error_count63"] <= 5:
        within += 1
        assert match
    else:
        beyond += 1
assert seen == set(archived)
assert all(r["phase"] == "baseline" for r in rows[:12000])
assert all(r["phase"] == "noise_sweep" for r in rows[12000:])
groups = defaultdict(list)
for r in rows:
    groups[condition(r)].append(r)
assert len(groups) == 7 and {len(g) for g in groups.values()} == {12000}

def metrics(group):
    n = len(group)
    successes = sum(r["evaluator_success"] for r in group)
    categories = Counter(r["reconstruction_outcome"] for r in group)
    latency = sorted(r["reconstruction_latency_ns"] for r in group)
    position = (n - 1) * 0.95
    lower = int(position)
    p95 = latency[lower] + (latency[min(n - 1, lower + 1)] - latency[lower]) * (position - lower)
    return {"attempt_count": n, "success_count": successes, "failure_count": n - successes,
            "success_rate": successes / n, "frr": (n - successes) / n,
            "decoder_failures": categories["decoder_failure"],
            "invalid_format": categories["invalid_format_or_padding"],
            "miscorrections": sum(r["evaluator_outcome"] == "evaluator_wrong_match" for r in group),
            "mean_ber63": sum(r["evaluator_error_count63"] for r in group) / (63 * n),
            "mean_ber64": sum(r["evaluator_error_count64"] for r in group) / (64 * n),
            "latency_sample_count": n, "latency_mean_ns": mean(latency),
            "latency_median_ns": median(latency), "latency_p95_ns": p95, "latency_max_ns": max(latency)}

group_count = 0
for name, extra in [("baseline_summary", []), ("noise_sweep_summary", []),
                    ("per_run_summary", ["simulation_seed"]),
                    ("per_device_summary", ["simulation_seed", "device_id"]),
                    ("error_count_summary", ["evaluator_error_count63"]), ("latency_summary", [])]:
    grouped = defaultdict(list)
    for r in rows:
        if name == "baseline_summary" and r["phase"] != "baseline":
            continue
        if name == "noise_sweep_summary" and r["phase"] != "noise_sweep":
            continue
        grouped[key(r, extra)].append(r)
    saved = read_csv(evidence / f"{name}.csv")
    assert {key(r, extra) for r in saved} == set(grouped)
    for saved_row in saved:
        group = grouped[key(saved_row, extra)]
        expected = metrics(group)
        for metric, value in expected.items():
            if name == "latency_summary" and not metric.startswith("latency_"):
                continue
            assert math.isclose(float(saved_row[metric]), value, rel_tol=1e-14, abs_tol=1e-12), (name, metric)
        if name != "latency_summary":
            assert json.loads(saved_row["error_count_distribution"]) == dict(Counter(
                str(r["evaluator_error_count63"]) for r in group))
        group_count += 1
for saved in read_json(evidence / "summary.json")["conditions"]:
    for metric, value in metrics(groups[condition(saved)]).items():
        assert saved[metric] == value
nominal = rows[:12000]
device_failures = Counter((r["simulation_seed"], r["device_id"]) for r in nominal if not r["evaluator_success"])
report = {"status": "PASS", "attempt_count": len(rows), "unique_readings": len(seen),
          "archive_response_matches": len(rows), "enrollment_count": len(enrollment),
          "condition_counts": [{"phase": c[0], "sweep_index": c[1], "noise": c[2],
                                "count": len(g)} for c, g in groups.items()],
          "summary_groups_independently_reconciled": group_count,
          "within_radius_successes": within, "within_radius_failures": 0,
          "beyond_radius_attempts": beyond,
          "beyond_radius_successes": sum(r["evaluator_success"] for r in rows if r["evaluator_error_count63"] > 5),
          "baseline_devices_with_failures": len(device_failures),
          "baseline_devices_above_1_percent_frr": sum(n > 1 for n in device_failures.values()),
          "baseline_wrong_credentials": [r for r in nominal if r["evaluator_outcome"] == "evaluator_wrong_match"],
          "backend_exceptions": 0,
          "evidence_manifest_sha256": sha(evidence / "manifest.json"),
          "audit_source_sha256": sha(Path(__file__))}
output = args.output
with output.open("x", encoding="utf-8") as stream:
    json.dump(report, stream, indent=2)
    stream.write("\n")
print(json.dumps(report, indent=2))
