"""
this script updates only the feedback sections in the existing results and research log
it reads completed evidence rather than filling in assumed scores or work hours
"""

from __future__ import annotations

import argparse
import json
import subprocess

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HEADING = "## Week 4 feedback evaluation"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require_complete(path: Path) -> None:
    if not (path / "COMPLETE").is_file():
        raise ValueError(f"experiment is not complete: {path}")


def verify_commit(commit: str) -> None:
    subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=ROOT, check=True, capture_output=True)


def replace_feedback_section(path: Path, section: str, research_log: bool = False) -> None:
    original = path.read_text(encoding="utf-8")

    if original.count(HEADING) != 1:
        raise ValueError(f"expected one existing feedback heading in {path}")

    start = original.index(HEADING)

    if research_log:
        end_marker = "---\n\n# Hours and Work Log"
        end = original.index(end_marker, start)
        updated = original[:start] + section.rstrip() + "\n\n" + original[end:]
        if updated[updated.index("# Hours and Work Log"):] != original[original.index("# Hours and Work Log"):]:
            raise AssertionError("hour-log preservation check failed")
    else:
        updated = original[:start] + section.rstrip() + "\n"

    path.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-commit", default=None)
    arguments = parser.parse_args()
    directories = {
        "data": ROOT / "results/week-4/keegan/data-diagnostics",
        "conventional": ROOT / "results/week-4/keegan/conventional-baselines",
        "original_snn_report": ROOT / "results/week-4/keegan/snn-original-report",
        "snn": ROOT / "results/week-4/keegan/snn-baseline-separate-seeds",
        "snn_report": ROOT / "results/week-4/keegan/snn-detailed-report",
        "small_snn": ROOT / "results/week-4/keegan/snn-architecture-32",
        "architecture": ROOT / "results/week-4/keegan/snn-architecture-comparison",
        "motion": ROOT / "results/week-4/keegan/motion-analysis",
        "pipeline": ROOT / "results/week-4/shared/pipeline-benchmark",
    }

    for directory in directories.values():
        require_complete(directory)

    data_manifest = read_json(directories["data"] / "manifest.json")
    source_commit = data_manifest["git_commit"]
    verify_commit(source_commit)
    conventional = read_json(directories["conventional"] / "baseline-diagnostics.json")
    snn = read_json(directories["snn"] / "summary.json")
    data = read_json(directories["data"] / "data-diagnostics.json")
    architecture = read_json(directories["architecture"] / "architecture-comparison.json")
    pipeline_manifest = read_json(directories["pipeline"] / "manifest.json")
    snn_manifest = read_json(directories["snn"] / "manifest.json")
    expected_hash = data_manifest["input_sha256"]

    if conventional["input"]["sha256"] != expected_hash or snn_manifest["input_sha256"] != expected_hash or pipeline_manifest["input_sha256"] != expected_hash:
        raise ValueError("evidence does not use the same input dataset")

    if snn_manifest["git"]["commit"] != source_commit or conventional["provenance"]["git_commit"] != source_commit or pipeline_manifest["git_commit"] != source_commit:
        raise ValueError("source commits differ across the runs; review provenance before recording a unified comparison")

    conventional_summary = conventional["multiseed_baselines"]["summary"]
    strongest = max(values["test_macro_f1"]["mean"] for values in conventional_summary.values())
    gap = (strongest - snn["test_macro_f1"]["mean"]) * 100.0
    threshold_met = gap <= 5.0
    conclusion = "The follow-up meets the provisional accuracy-gap target, but does not demonstrate overall superiority." if threshold_met else "The follow-up misses the provisional accuracy-gap target; do not describe this new run as meeting the competitive-baseline criterion."
    section = [HEADING, "", "The original Week 4 baseline above remains historical evidence. This follow-up uses the same corrected dataset, separate model-initialization/training seeds, and explicitly scoped diagnostics rather than overwriting that run.", "", "| Model | Test macro-F1 mean | SD |", "|---|---:|---:|"]

    for name, values in conventional_summary.items():
        section.append(f"| {name} | {values['test_macro_f1']['mean']:.4f} | {values['test_macro_f1']['standard_deviation']:.4f} |")

    section.append(f"| SNN 64, separate training seeds | {snn['test_macro_f1']['mean']:.4f} | {snn['test_macro_f1']['standard_deviation']:.4f} |")
    section.extend(["", f"The 64-neuron follow-up has mean test accuracy {snn['test_accuracy']['mean']:.4f}. Its macro-F1 gap to the strongest conventional model is {gap:.2f} percentage points; the provisional five-point target is {'met' if threshold_met else 'not met'}. Conventional SD uses the original diagnostic's sample-SD convention; SNN SD uses its saved population-SD convention. Neither estimates variation across independent human/device datasets.", "", f"Full-window cross-split duplicate check: {data['datasets']['corrected']['full_windows']['passed']}. All three split-pair counts and physical before/after nearest-neighbor distributions are in data-diagnostics.json; provisional sensitivity thresholds are not a universal no-leakage proof.", "", "The saved reports contain per-seed/pooled precision, recall, F1, support and complete confusion matrices, training loss/validation-F1 curves and best/stopping epochs. Pooled predictions reuse the same source test windows. LR's deterministic lbfgs procedure explains unchanged fixed-data results across model seeds.", "", f"The predefined 32-versus-64 comparison selected {architecture['selected_by_validation_only']} neurons using validation macro-F1 only. The existing 64-neuron baseline remains the baseline; Session-3 comparison did not drive another tuning loop.", "", "Nod/still trajectories, per-window motion statistics, intentional-amplitude/duration sweep, moderate paired stress tests and conventional feature ablations are recorded in motion-analysis. Initial-orientation changes are relative-pose invariance checks; low-amplitude nominal nod labels become ambiguous near still. Synthetic success does not establish realistic physical motion.", "", "Pipeline timing compares the same binary32-quantized motion through classifier-only and authenticated paths. Accepted predictions must match; the bad-tag timing path makes zero preprocessing/classifier calls and preserves sequence state. Total time is measured directly. Loading, capture, networking and durable audit I/O are excluded. Session setup uses a known-correct synthetic candidate, so reconstruction reliability and overall legitimate-window availability are not established.", "", f"Conclusion: {conclusion} These are CPU software-prototype results, with no measured energy advantage, physical Quest result, cross-person or cross-device classifier generalization.", "", "### Evidence", ""])

    for name, directory in directories.items():
        section.append(f"- {name}: `{directory.relative_to(ROOT).as_posix()}`")

    section.extend(["- C# negative protocol evidence: `results/week-4/shared/protocol-validation/negative-results.json`", "", "### Provenance", "", f"- Evaluation source commit: `{source_commit}`", f"- Dataset SHA-256: `{expected_hash}`", "- Commands, source/configuration hashes, seed roles, environment and figure paths are recorded in the run manifests and saved configurations.", "- Permanent methods: `docs/xr-snn-design.md`, `docs/authenticated-window-interface.md` and Will's `docs/puf-layer3-design.md`."])

    if arguments.results_commit:
        verify_commit(arguments.results_commit)
        section.append(f"- Pushed evaluation-results commit: `{arguments.results_commit}`")

    section.extend(["", "### Remaining shared requirements", "", "Will owns independent enrollment verification before HKDF, reconstruction FRR/miscorrection/noise/BER sensitivity and improvement comparisons, formal Tier-1 attack counts/uncertainty/state tests, and evidence-manifest reconciliation. Remaining shared work includes disjoint replay/audit/session-confirmation timing and any durable-storage benchmark. Final binary Unity execution must be reported separately from supplemental .NET execution. Human recording remains disabled."])
    protocol_path = ROOT / "results/week-4/shared/protocol-validation/negative-results.json"

    if not protocol_path.is_file():
        raise ValueError("negative C# protocol evidence is missing")

    protocol = read_json(protocol_path)
    if len(protocol["observations"]) != 5 or any(row["decision"] != "reject" or row["classifier_calls_after_rejection"] != 0 or not row["state_unchanged"] or not row["valid_next_window_accepted"] for row in protocol["observations"]):
        raise ValueError("negative protocol evidence does not satisfy all five controlled cases")

    text = "\n".join(section)
    replace_feedback_section(ROOT / "results/week-4/keegan/keegan.md", text)
    research_section = text.replace("The original Week 4 baseline above remains historical evidence.", "The original template-leakage finding and Week 4 baseline remain preserved in this log.")
    replace_feedback_section(ROOT / "docs/research-logs/keegan.md", research_section, research_log=True)
    print("Updated only the feedback sections in keegan.md and the research log; hours and historical entries are unchanged")


if __name__ == "__main__":
    main()
