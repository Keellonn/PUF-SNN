"""Fixed diagnostic design and evidence reconciliation, not model selection."""

from __future__ import annotations

from collections import defaultdict
import json

from puf_snn.frozen_pipeline import read_json, require_hash, scoped_path, sha256
from puf_snn.pipeline_diagnostics import MODES, diagnostic_mode
from puf_snn.pipeline_timing import CONDITIONS, quantile, reconcile_timing, select_timing_sources
from scripts.summarize_week6_timing import validate_span_tree


HISTORICAL_MANIFEST = "10135c6e3849015c6afcfb96c91d9bc25bdeabdbdc1da2531b1ec65501403b50"
MODE_ORDERS = ((0, 1, 3, 2), (1, 2, 0, 3), (2, 3, 1, 0), (3, 0, 2, 1))
CONTRASTS = (
    ("trace_retention", "nested_retained_gc_on", "nested_stream_gc_on"),
    ("nested_observer", "nested_stream_gc_on", "outer_stream_gc_on"),
    ("automatic_gc_deferral", "nested_stream_gc_on", "nested_stream_gc_deferred"),
)


def validate_experiment_config(config):
    fixed = {
        "config_version": "week6-observer-experiment-v1", "frozen_config": "configs/week6_smoke.json",
        "historical_directory": "results/week-6/keegan/fresh-v2-timing",
        "historical_manifest_sha256": HISTORICAL_MANIFEST,
        "source_selection": "first_two_sorted_test_windows_per_device_class",
        "warmup_selection": "first_sorted_validation_window_per_device_class",
        "measured_attempts_per_condition": 60, "warmup_attempts_per_condition": 30,
        "blocks": 4, "native_threads": 1, "batch_size": 1, "gc_thresholds": [2000, 10, 10],
        "modes": [m.name for m in MODES],
        "conditions": [dict(name=n, motion=m, anomaly=a) for n, m, a in CONDITIONS],
        "historical_heap_trace_counts": [0, 5000, 15000, 29718], "full_gc_probes_per_heap": 5,
        "read_domain": "week6-diagnostic-v1:6767:{block}:{device_index}:{cohort}:measurement",
    }
    # Canonical JSON also distinguishes bools from integer protocol fields.
    if json.dumps(config, sort_keys=True) != json.dumps(fixed, sort_keys=True):
        raise ValueError("diagnostic design is fixed; no result-dependent sample/model/GC tuning")


def select_experiment_sources(records):
    test, _ = select_timing_sources(records)  # Validate unchanged full source splits.
    validation = sorted((r for r in records if r["split"] == "validation"),
                        key=lambda r: (r["device_id"], r["label"], r["window_id"]))
    def first_per_group(rows, count):
        groups = defaultdict(list)
        for row in rows:
            groups[(row["device_id"], row["label"])].append(row)
        return [r for key in sorted(groups) for r in groups[key][:count]]
    measured, warmup = first_per_group(test, 2), first_per_group(validation, 1)
    if len(measured) != 60 or len(warmup) != 30:
        raise ValueError("expected sixty test sources and thirty disjoint validation warmups")
    return measured, warmup


def build_jobs(config):
    validate_experiment_config(config)
    jobs = []
    for block, order in enumerate(MODE_ORDERS):
        for position, mode_index in enumerate(order):
            rotation = (block * 4 + position) % len(config["conditions"])
            conditions = config["conditions"][rotation:] + config["conditions"][:rotation]
            jobs.append(dict(job_id=f"block-{block}-mode-{mode_index}", kind="timing",
                             block=block, position=position, mode=config["modes"][mode_index],
                             condition_order=conditions))
    for count in config["historical_heap_trace_counts"]:
        jobs.append(dict(job_id=f"heap-{count}", kind="historical_heap_probe", retained_trace_count=count))
    return jobs


def checked_historical_inputs(root, config):
    """Hash-check the closed saved inventory without retaining its trace trees."""
    directory = scoped_path(root, config["historical_directory"])
    require_hash(directory / "manifest.json", config["historical_manifest_sha256"])
    manifest, complete = read_json(directory / "manifest.json"), read_json(directory / "COMPLETE")
    if ((directory / "INCOMPLETE").exists()
            or complete["manifest_sha256"] != config["historical_manifest_sha256"]
            or complete["trace_count"] != 29718 or manifest["reconciliation"]["trace_count"] != 29718):
        raise ValueError("historical timing input is not the pinned completed run")
    checked = {"manifest.json": config["historical_manifest_sha256"], "COMPLETE": sha256(directory / "COMPLETE")}
    for relative, digest in manifest["artifacts"].items():
        require_hash(scoped_path(directory, relative), digest)
        checked[relative] = digest
    return directory, manifest, checked


def recheck_frozen_inputs(root, frozen, hashes):
    """Post-run byte checks only; never deserialize, fit or select models."""
    require_hash(scoped_path(root, frozen["input_path"]), frozen["input_sha256"])
    for identity, digest in hashes.items():
        role, relative = identity.split("/", 1)
        if role not in frozen["bundles"]:
            raise ValueError("unknown role in the frozen input inventory")
        directory = scoped_path(root, frozen["bundles"][role]["directory"])
        require_hash(scoped_path(directory, relative), digest)


def iter_historical_traces(directory, conditions):
    for condition in conditions:
        with (directory / f"timings-{condition['name']}.jsonl").open(encoding="utf-8") as handle:
            for line in handle:
                trace = json.loads(line)
                if trace["condition"] != condition["name"]:
                    raise ValueError("historical condition/file mismatch")
                validate_span_tree(trace)
                yield trace


def require_source_unchanged(root, commit, output):
    """Only this diagnostic's untracked output is permitted while workers run."""
    import subprocess
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if head != commit:
        raise ValueError("source HEAD changed; preserve partial diagnostic output")
    for command in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        subprocess.run(command, cwd=root, check=True)
    names = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"],
                                    cwd=root, text=True).split("\0")
    for name in filter(None, names):
        if not scoped_path(root, name).is_relative_to(output.resolve()):
            raise ValueError("untracked files outside the declared diagnostic output appeared")


def new_output_path(root, output):
    output, scope = output.resolve(), (root / "results/week-6/keegan").resolve()
    if output == scope or not output.is_relative_to(scope) or output.exists():
        raise ValueError("choose a new scoped output; never overwrite or automatically resume")
    return output


def worker_trace_key(trace):
    return tuple(trace[k] for k in ("condition", "phase", "attempt_index", "path"))


def functional_signature(trace):
    public = {k: trace[k] for k in ("source_window_id", "device_id", "source_split",
                                   "selected_bit_error_count", "decision", "stage", "reason", "model_calls")}
    for name in ("sequence_number", "last_accepted_before", "last_accepted_after", "read_count"):
        if name in trace:
            public[name] = trace[name]
    if trace["path"] == "fresh_to_first_window":
        public["admission"] = {k: trace["admission"][k] for k in ("decision", "stage", "reason")}
    return json.dumps(public, sort_keys=True, allow_nan=False)


def validate_worker_traces(traces, job, config):
    mode = diagnostic_mode(job["mode"])
    for trace in traces:
        validate_span_tree(trace)
        if (trace["mode"] != job["mode"] or trace["block"] != job["block"]
                or trace["observer"] != ("nested" if mode.nested_spans else "outer_only")):
            raise ValueError("worker identity or observer differs from its predeclared job")
        if not mode.nested_spans and len(trace["spans"]) != 1:
            raise ValueError("lightweight mode unexpectedly contains nested timing spans")
        if (trace["clock_end_ns"] - trace["clock_start_ns"] != trace["elapsed_ns"]
                or trace["process_id"] <= 0 or trace["native_thread_id"] <= 0):
            raise ValueError("invalid public clock/process correlation fields")
    return reconcile_timing(traces, job["condition_order"],
                            measured=config["measured_attempts_per_condition"],
                            warmup=config["warmup_attempts_per_condition"])


def signed_delta_statistics(values):
    if not values or any(type(v) is not int for v in values):
        raise ValueError("paired differences require signed integer nanoseconds")
    return {"count": len(values), "mean_delta_ms": sum(values) / len(values) / 1e6,
            "p50_delta_ms": quantile(values, .5) / 1e6, "p95_delta_ms": quantile(values, .95) / 1e6,
            "min_delta_ms": min(values) / 1e6, "max_delta_ms": max(values) / 1e6}


def paired_comparison(left, right, contrast, block):
    def indexed(rows):
        result = {}
        for row in rows:
            key = worker_trace_key(row)
            if key in result:
                raise ValueError("duplicate trace in paired worker evidence")
            result[key] = row
        return result
    a, b = indexed(left), indexed(right)
    if set(a) != set(b):
        raise ValueError("paired diagnostic modes have different admission/control inventories")
    groups = defaultdict(list)
    for key in sorted(a):
        one, two = a[key], b[key]
        if functional_signature(one) != functional_signature(two):
            raise ValueError("paired modes differ in source/noise/decision/callback/sequence evidence")
        group = (one["condition"], one["phase"], one["path"], one["decision"], one["reason"])
        groups[group].append(two["elapsed_ns"] - one["elapsed_ns"])
    return [dict(contrast=contrast, block=block,
                 **dict(zip(("condition", "phase", "path", "decision", "reason"), key)),
                 **signed_delta_statistics(values), direction="right_minus_left",
                 independent_reliability_trials=False)
            for key, values in sorted(groups.items())]


def read_job_traces(directory, job):
    traces = []
    for condition in job["condition_order"]:
        with (directory / f"timings-{condition['name']}.jsonl").open(encoding="utf-8") as handle:
            traces.extend(json.loads(line) for line in handle)
    return traces


def checked_completion(directory, *, expected_job=None, expected_commit=None):
    manifest, complete = read_json(directory / "manifest.json"), read_json(directory / "COMPLETE")
    if (directory / "INCOMPLETE").exists() or complete["manifest_sha256"] != sha256(directory / "manifest.json"):
        raise ValueError("worker is not a hash-bound completed result")
    if expected_job is not None and manifest["job"] != expected_job:
        raise ValueError("worker completed a different job")
    if expected_commit is not None and manifest["source_commit"] != expected_commit:
        raise ValueError("worker source commit differs")
    for relative, digest in manifest["artifacts"].items():
        require_hash(scoped_path(directory, relative), digest)
    inventory = {p.name for p in directory.iterdir() if p.is_file()}
    if inventory != set(manifest["artifacts"]) | {"manifest.json", "COMPLETE"}:
        raise ValueError("worker file inventory differs from its manifest")
    return manifest
