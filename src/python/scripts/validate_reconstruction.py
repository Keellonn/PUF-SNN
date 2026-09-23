"""Record synthetic reconstruction controls, not the primary PUF experiment.

No baseline archives are loaded and no success/FRR/latency suitability claim is
made. Every configured probe is retained, including failures and miscorrections.
Ground truth exists only in this evaluator script, outside the reconstruction API.
"""

import argparse
from collections import Counter
from dataclasses import asdict, replace
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
from random import Random
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))

from puf_snn.puf.device import create_device
from puf_snn.puf.ro_puf import generate_pairs, generate_response
from puf_snn.puf.variables import ReadConditions
from puf_snn.reconstruction import (
    BCHCodec, DEFAULT_CONFIG, HelperData, enroll, reconstruct,
)
from scripts.run_puf_baseline import make_rng


def _flip(response, indices):
    changed = list(response)
    for index in indices:
        changed[index] ^= 1
    return tuple(changed)


def _record(case_id, group, response, helper, reference, credential):
    # The production routine receives exactly these two public/input objects.
    result = reconstruct(response, helper)
    expected_message = tuple(int(bit) for bit in f"{int.from_bytes(credential, 'big'):032b}") + (0,) * 4
    match = (None if result.candidate_credential is None
             else result.candidate_credential == credential)
    evaluator_outcome = ("no_valid_candidate" if match is None else
                         "evaluator_correct_match" if match else "evaluator_wrong_match")
    return {
        "case_id": case_id, "group": group,
        "reference64": "".join(map(str, reference)),
        "response64": "".join(map(str, response)),
        "helper63": "".join(map(str, helper.helper_bits)),
        "enrollment_id": helper.enrollment_id,
        "enrolled_credential_hex": credential.hex(),
        "response_hamming_distance63": sum(a != b for a, b in zip(response[:63], reference[:63])),
        "response_hamming_distance64": sum(a != b for a, b in zip(response, reference)),
        "decoder_status": result.decoder_status,
        "reported_correction_count": result.reported_correction_count,
        "candidate_message36": (None if result.candidate_message is None
                                else "".join(map(str, result.candidate_message))),
        "candidate_credential_hex": (None if result.candidate_credential is None
                                     else result.candidate_credential.hex()),
        "padding_valid": result.padding_valid, "outcome": result.outcome,
        "failure_reason": result.failure_reason, "credential_match": match,
        "evaluator_outcome": evaluator_outcome,
        "miscorrection": (result.decoder_status == "decoded"
                           and result.candidate_message != expected_message),
    }


def characterize(seed: int = 20260922, samples_per_weight: int = 100) -> dict:
    """Reproducible diagnostic masks; neither argument tunes a PUF parameter."""
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if type(samples_per_weight) is not int or samples_per_weight < 1:
        raise ValueError("samples_per_weight must be a positive integer")
    zero = (0,) * 64
    credential = bytes.fromhex("12345678")
    helper = enroll(zero, credential, enrollment_id="synthetic-patterns")
    records = []
    for weight in range(6, 13):
        rng = Random(f"reconstruction-validation-v1:{seed}:weight-{weight}")
        for index in range(samples_per_weight):
            mask = tuple(sorted(rng.sample(range(63), weight)))
            record = _record(f"weight-{weight}/{index}", f"weight-{weight}",
                             _flip(zero, mask), helper, zero, credential)
            record["flipped_indices"] = mask
            records.append(record)

    # Both target codewords have weight 11. Six of their set bits put the
    # received word closer to the wrong codeword than to the enrolled zero word.
    codec = BCHCodec()
    zero_helper = enroll(zero, bytes(4), enrollment_id="synthetic-zero")
    for name, message_integer in (("six-errors-valid-padding", 16),
                                  ("six-errors-invalid-padding", 1)):
        word = codec.encode(tuple(int(bit) for bit in f"{message_integer:036b}"))
        support = tuple(index for index, bit in enumerate(word) if bit)
        if len(support) != 11:
            raise RuntimeError("Boundary fixture no longer has weight 11")
        records.append(_record(name, "boundary", _flip(zero, support[:6]),
                               zero_helper, zero, bytes(4)))
    records.append(_record("six-adjacent-errors", "boundary", _flip(zero, range(6)),
                           zero_helper, zero, bytes(4)))

    # Two deterministic, zero-noise Layer 1 device references as controls only.
    # These are not a sample of the 12,000 legitimate baseline readings.
    references = []
    pairs = generate_pairs(128, "adjacent")
    for index in range(2):
        device = create_device(f"control-{index}", 128, 1.0,
                               rng=make_rng(1234, index, "manufacturing"))
        references.append(generate_response(
            device, pairs, 100.0, ReadConditions(0.0, 0.0),
            rng=make_rng(1234, index, "enrollment"),
        ))
    credential_a, credential_b = bytes.fromhex("01234567"), bytes.fromhex("89abcdef")
    helper_a = enroll(references[0], credential_a, enrollment_id="control-0")
    helper_b = enroll(references[1], credential_b, enrollment_id="control-1")
    controls = (
        ("wrong-helper", references[0], helper_b),
        ("wrong-device", references[1], helper_a),
        ("one-helper-bit-changed", references[0],
         replace(helper_a, helper_bits=_flip(helper_a.helper_bits, (0,)))),
        ("routing-label-changed", references[0],
         replace(helper_a, enrollment_id="different-label")),
    )
    for name, response, public_helper in controls:
        records.append(_record(name, "controls", response, public_helper,
                               references[0], credential_a))

    summaries = []
    for group in dict.fromkeys(row["group"] for row in records):
        rows = [row for row in records if row["group"] == group]
        summaries.append({
            "group": group, "attempts": len(rows),
            "outcomes": dict(sorted(Counter(row["outcome"] for row in rows).items())),
            "evaluator_outcomes": dict(sorted(Counter(row["evaluator_outcome"] for row in rows).items())),
            "miscorrections": sum(row["miscorrection"] for row in rows),
        })
    paths = sorted((PROJECT_ROOT / "src/python/puf_snn/reconstruction").glob("*.py"))
    paths += sorted((PROJECT_ROOT / "src/python/puf_snn/puf").glob("*.py"))
    paths += [Path(__file__), PROJECT_ROOT / "src/python/scripts/run_puf_baseline.py"]
    return {
        "schema_version": "reconstruction-implementation-validation-v1",
        "scope": "Synthetic decoder probes and isolated controls; not PUF FRR or suitability evidence",
        "config": asdict(DEFAULT_CONFIG), "seed": seed,
        "mask_rng_scheme": "Random('reconstruction-validation-v1:{seed}:weight-{weight}')",
        "samples_per_weight": samples_per_weight, "attempt_count": len(records),
        "python": platform.python_version(), "platform": platform.platform(),
        "packages": {name: version(name) for name in
                     ("galois", "numpy", "numba", "llvmlite", "typing_extensions")},
        "source_sha256": {path.relative_to(PROJECT_ROOT).as_posix():
                          hashlib.sha256(path.read_bytes()).hexdigest() for path in paths},
        "summary": summaries, "attempts": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260922)
    parser.add_argument("--samples-per-weight", type=int, default=100)
    parser.add_argument("--output", type=Path,
                        help="New JSON file; existing evidence is never overwritten")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error(f"Output already exists: {args.output}")
    report = characterize(args.seed, args.samples_per_weight)
    if args.output is None:
        print(json.dumps(report, indent=2))
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
        print(json.dumps({"output": str(args.output), "attempt_count": report["attempt_count"],
                          "summary": report["summary"]}, indent=2))


if __name__ == "__main__":
    main()
