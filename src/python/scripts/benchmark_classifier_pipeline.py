"""
this script compares classifier-only and authenticated post-window CPU paths
session setup uses the existing explicit synthetic candidate and is reported separately
"""

from __future__ import annotations

import argparse
import hmac
import json
import sys
import time

from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src/python/scripts"))

import train_baselines as baseline

from evaluate_motion import load_snn_models, provenance, sha256, write_json
from puf_snn.auth.binary_window import encode_window, parse_envelope, window_tag
from puf_snn.auth.config import AuthConfig
from puf_snn.auth.session import Failure
from puf_snn.integration import ExactlyOnceClassifierRelease, _accepted_window_to_classifier_record, processed_record_to_wire_window
from puf_snn.snn.dataset import LABELS, apply_channel_normalization, build_snn_datasets, load_records, record_to_sequence
from puf_snn.snn.evaluation import calculate_metrics
from run_layer3_demo import establish, initialize_material


def latency_summary(values: list[int]) -> dict:
    array = np.asarray(values, dtype=np.float64) / 1_000_000.0
    return {"count": len(values), "unit": "milliseconds", "median_ms": float(np.median(array)), "p95_ms": float(np.percentile(array, 95)), "maximum_ms": float(np.max(array))}


def timed(operation) -> tuple[object, int]:
    start = time.perf_counter_ns()
    result = operation()
    return result, time.perf_counter_ns() - start


def prediction_functions(model: object, normalization: dict) -> tuple[object, object]:
    if isinstance(model, torch.nn.Module):
        model.eval()

        def preprocess(record: dict) -> torch.Tensor:
            sequence = record_to_sequence(record)[None, :, :]
            return torch.from_numpy(apply_channel_normalization(sequence, normalization)).to("cpu")

        def classify(tensor: torch.Tensor) -> int:
            with torch.inference_mode():
                return int(model(tensor).argmax(dim=1).cpu().item())

        return preprocess, classify

    def preprocess(record: dict) -> np.ndarray:
        return baseline.record_to_features(record).reshape(1, -1)

    def classify(features: np.ndarray) -> int:
        return LABELS.index(str(model.predict(features)[0]))

    return preprocess, classify


def canonical_record(source: dict) -> dict:
    # both conditions consume the same binary32-quantized motion rather than mixing precisions
    return _accepted_window_to_classifier_record(processed_record_to_wire_window(source))


def measure_condition(model: object, records: list[dict], normalization: dict, authenticated: bool, config: AuthConfig, material: tuple, warmup: int, count: int) -> dict:
    preprocess, classify = prediction_functions(model, normalization)
    sender = verifier = gate = None
    session_ns = None
    setup = {}
    component_rows = []

    if authenticated:
        sender, verifier, session_ns = establish(config, material)
        setup = {"session_establishment_ns": session_ns, "sender_kdf_ns": list(sender.kdf_timings_ns), "verifier_kdf_ns": list(verifier.kdf_timings_ns), "reconstruction_ns": None, "independent_credential_verification_ns": None, "candidate_source": "explicit synthetic correct candidate; reconstruction reliability is not measured"}

    def measured_preprocess(record: dict):
        value, elapsed = timed(lambda: preprocess(record))
        component_rows[-1]["preprocessing_tensor_ns"] = elapsed
        return value

    def measured_classify(value):
        prediction, elapsed = timed(lambda: classify(value))
        component_rows[-1]["inference_decoding_ns"] = elapsed
        return prediction

    if authenticated:
        gate = ExactlyOnceClassifierRelease(verifier, measured_preprocess, measured_classify)

    rows = []
    expected = []
    predictions = []

    for index in range(warmup + count):
        source = records[index % len(records)]
        row = {"source_window_id": source["window_id"]}
        component_rows.append(row)
        start = time.perf_counter_ns()

        if authenticated:
            window, row["adapter_ns"] = timed(lambda: processed_record_to_wire_window(source))
            packet, row["sender_seal_including_audit_ns"] = timed(lambda: sender.seal_window(window))

            if isinstance(packet, Failure):
                raise RuntimeError(f"sender rejected legitimate window: {packet.reason}")

            result, row["verifier_including_audit_ns"] = timed(lambda: verifier.verify_window(packet))

            if result.result != "accept":
                raise RuntimeError(f"verifier rejected legitimate window: {result.reason}")

            prediction = gate.deliver(result)
            row["event_id"] = result.event_id
            row["sender_hmac_nested_ns"] = sender.last_window_timing.sender_hmac_ns
        else:
            record, row["common_binary32_conversion_ns"] = timed(lambda: canonical_record(source))
            prediction = measured_classify(measured_preprocess(record))

        row["total_ns"] = time.perf_counter_ns() - start

        if index >= warmup:
            expected.append(LABELS.index(source["label"]))
            predictions.append(prediction)
            rows.append(row)

    audit_examples = []

    if authenticated:
        audit_examples = [row for row in verifier.audit_records if row["event_type"] == "window"][:2]
        verifier.close_all_sessions()

    return {"rows": rows, "summary": {field: latency_summary([row[field] for row in rows if field in row]) for field in rows[0] if field.endswith("_ns")}, "classification": calculate_metrics(np.asarray(expected), np.asarray(predictions)), "predictions": predictions, "session_setup": setup, "audit_examples": audit_examples}


def rejected_path(source: dict, config: AuthConfig, material: tuple, warmup: int, count: int) -> dict:
    sender, verifier, _ = establish(config, material)
    packet = sender.seal_window(processed_record_to_wire_window(source))
    envelope = json.loads(packet)
    envelope["authentication"]["tag_hex"] = "00" * 32
    bad_tag = json.dumps(envelope, separators=(",", ":")).encode("utf-8")
    calls = []
    gate = ExactlyOnceClassifierRelease(verifier, lambda record: calls.append("preprocess"), lambda features: calls.append("classifier"))
    rows = []
    status_before = verifier.session_status(sender.session_id)

    for index in range(warmup + count):
        start = time.perf_counter_ns()
        result = verifier.verify_window(bad_tag)

        try:
            gate.deliver(result)
            raise AssertionError("rejected decision reached the release gate")
        except ValueError:
            pass

        elapsed = time.perf_counter_ns() - start

        if result.result != "reject" or result.reason != "invalid_tag" or calls:
            raise RuntimeError("bad-tag path violated rejection-before-classification")

        if index >= warmup:
            rows.append(elapsed)

    if verifier.session_status(sender.session_id) != status_before:
        raise RuntimeError("rejection changed valid sequence state")

    examples = [row for row in verifier.audit_records if row["event_type"] == "window"][:2]
    verifier.close_all_sessions()
    return {"summary": latency_summary(rows), "raw_total_ns": rows, "reason": "invalid_tag", "classifier_calls": len(calls), "state_unchanged": True, "audit_examples": examples, "scope": "receiver-side bad-tag timing repetitions, not independent Tier-1 security trials; attacker packet preparation and sender work excluded"}


def primitive_timings(source: dict, config: AuthConfig, material: tuple, warmup: int, count: int) -> dict:
    sender, verifier, _ = establish(config, material)
    packet = sender.seal_window(processed_record_to_wire_window(source))
    parsed = parse_envelope(packet)
    operations = {"canonical_serialization": lambda: encode_window(parsed.window), "hmac_generation": lambda: window_tag(sender._key, parsed.authenticated_bytes), "hmac_verification": lambda: hmac.compare_digest(window_tag(sender._key, parsed.authenticated_bytes), parsed.tag)}
    result = {}

    for name, operation in operations.items():
        values = []

        for index in range(warmup + count):
            _, elapsed = timed(operation)

            if index >= warmup:
                values.append(elapsed)

        result[name] = {"summary": latency_summary(values), "raw_ns": values}

    verifier.close_all_sessions()
    return {"stages": result, "scope": "isolated primitive microbenchmarks; serialization includes codec quality checks; nested/composite timings must not be added or relabeled as disjoint stages; no key material is saved"}


def session_timings(config: AuthConfig, material: tuple, warmup: int, count: int) -> dict:
    rows = []

    for index in range(warmup + count):
        sender, verifier, elapsed = establish(config, material)

        if index >= warmup:
            rows.append({"session_establishment_ns": elapsed, "sender_kdf_ns": sender.kdf_timings_ns[-1], "verifier_kdf_ns": verifier.kdf_timings_ns[-1]})

        verifier.close_all_sessions()

    return {"rows": rows, "summary": {field: latency_summary([row[field] for row in rows]) for field in rows[0]}, "scope": "fresh sessions with OS randomness and an explicit known-correct synthetic candidate; sender/verifier creation and trusted enrollment are outside establish's timer; reconstruction and independent credential verification are not measured; KDF is nested inside session establishment"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/generated/synthetic-windows.jsonl")
    parser.add_argument("--snn-baseline", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/authentication_v1.json")
    parser.add_argument("--motion-config", type=Path, default=ROOT / "configs/motion_evaluation.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--machine-model", required=True)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--timed-windows", type=int, default=600)
    arguments = parser.parse_args()

    if arguments.warmup < 0 or arguments.timed_windows <= 0:
        raise ValueError("timing counts are invalid")

    config = AuthConfig.load(arguments.config)

    if config.max_windows <= arguments.warmup + arguments.timed_windows:
        raise ValueError("session window limit is too small for the benchmark")

    arguments.output.mkdir(parents=True, exist_ok=False)

    try:
        datasets = build_snn_datasets(load_records(arguments.input))
        models, normalization = load_snn_models(arguments.snn_baseline, arguments.input)
        settings = json.loads(arguments.motion_config.read_text(encoding="utf-8"))
        train = datasets["train"]
        train_x = train["sequences"].reshape(len(train["sequences"]), -1)
        train_labels = np.asarray([record["label"] for record in train["records"]])

        for seed in settings["model_seeds"]:
            for name, model in baseline.create_models(seed).items():
                model.fit(train_x, train_labels)
                models.append((f"{name}_seed_{seed}", model))

        material = initialize_material()
        results = {}
        metrics_lines = ["# Post-window pipeline benchmark", "", "Synthetic CPU/in-memory comparison. The same binary32-quantized motion, source order, split and models are used within each paired condition.", "", "| Model | Condition | Median (ms) | p95 (ms) | Max (ms) |", "|---|---|---:|---:|---:|"]

        for name, model in models:
            results[name] = {}

            for condition, authenticated in (("classifier_only", False), ("authentication_plus_classifier", True)):
                print(f"Timing {name}: {condition}")
                measured = measure_condition(model, datasets["test"]["records"], normalization, authenticated, config, material, arguments.warmup, arguments.timed_windows)
                results[name][condition] = measured
                summary = measured["summary"]["total_ns"]
                metrics_lines.append(f"| {name} | {condition} | {summary['median_ms']:.4f} | {summary['p95_ms']:.4f} | {summary['maximum_ms']:.4f} |")

            first = results[name]["classifier_only"]
            second = results[name]["authentication_plus_classifier"]

            if first["predictions"] != second["predictions"]:
                raise RuntimeError("authentication changed an accepted classification prediction")

            second["paired_total_difference_ns"] = [after["total_ns"] - before["total_ns"] for before, after in zip(first["rows"], second["rows"])]
            second["accepted_predictions_identical"] = True

        rejected = rejected_path(datasets["test"]["records"][0], config, material, arguments.warmup, arguments.timed_windows)
        primitives = primitive_timings(datasets["test"]["records"][0], config, material, arguments.warmup, arguments.timed_windows)
        sessions = session_timings(config, material, arguments.warmup, arguments.timed_windows)
        write_json(arguments.output / "accepted-paths.json", results)
        write_json(arguments.output / "rejected-path.json", rejected)
        write_json(arguments.output / "authentication-primitives.json", primitives)
        write_json(arguments.output / "session-setup.json", sessions)
        metrics_lines.extend(["", "Total time is measured directly per window, never assembled from stage percentiles. Preprocessing/tensor creation, inference/output decoding and actual in-memory authentication audit generation are included. Loading, training, capture, network transfer and persistent audit I/O are excluded. Nested component timers add measurement overhead; these are instrumented software measurements.", "", "Session establishment and KDF are separate from recurring windows. They use the existing explicit synthetic correct candidate, not a PUF reliability experiment. Independent credential verification, reconstruction, disjoint replay-state/audit stage instrumentation and durable audit-storage costs remain shared/Will follow-up requirements.", "", "The bad-tag receiver path makes zero preprocessing/classifier calls and preserves sequence state. These are repeated timing observations, not the formal independent Tier-1 attack evaluation."])
        (arguments.output / "pipeline-benchmark.md").write_text("\n".join(metrics_lines) + "\n", encoding="utf-8")
        record = provenance(arguments)
        record.update(warmup=arguments.warmup, timed_windows=arguments.timed_windows, timer="time.perf_counter_ns", timer_resolution_seconds=time.get_clock_info("perf_counter").resolution, authentication_configuration_sha256=sha256(arguments.config), snn_manifest_sha256=sha256(arguments.snn_baseline / "manifest.json"))
        write_json(arguments.output / "manifest.json", record)
        (arguments.output / "COMPLETE").write_text("complete\n", encoding="utf-8")
    except Exception as error:
        write_json(arguments.output / "INCOMPLETE.json", {"error_type": type(error).__name__, "error": str(error)})
        raise

    print(f"Saved pipeline evidence to {arguments.output}")


if __name__ == "__main__":
    main()
