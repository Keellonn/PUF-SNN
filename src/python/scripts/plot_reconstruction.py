"""Render scientific figures from completed Layer 2 evidence; never rerun PUFs."""

import argparse
import csv
import hashlib
import json
from pathlib import Path


def read_csv(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def plot(evidence, output):
    complete = json.loads((evidence / "COMPLETE").read_text())
    manifest_path = evidence / "manifest.json"
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != complete["manifest_sha256"]:
        raise ValueError("Evidence manifest changed")
    manifest = json.loads(manifest_path.read_text())
    for name, fingerprint in manifest.items():
        if hashlib.sha256((evidence / name).read_bytes()).hexdigest() != fingerprint:
            raise ValueError(f"Evidence changed: {name}")
    summary = json.loads((evidence / "summary.json").read_text())
    baseline = next(r for r in summary["conditions"] if r["phase"] == "baseline")
    sweep = [r for r in summary["conditions"] if r["phase"] == "noise_sweep"]
    errors = read_csv(evidence / "error_count_summary.csv")
    output.mkdir(parents=True, exist_ok=False)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "savefig.dpi": 180})
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), layout="constrained")
    panels = [("measurement_noise_std", "success_rate", "Measurement-noise SD", "Success (%)"),
              ("measurement_noise_std", "frr", "Measurement-noise SD", "FRR (%)"),
              ("mean_ber63", "success_rate", "Measured 63-bit BER (%)", "Success (%)")]
    for ax, (x, y, xlabel, ylabel) in zip(axes, panels):
        scale = 100 if x == "mean_ber63" else 1
        ax.plot([r[x] * scale for r in sweep], [r[y] * 100 for r in sweep],
                "o-", color="#176b91", label="Fixed sweep (later RNG draws)")
        ax.scatter([baseline[x] * scale], [baseline[y] * 100], marker="x", s=70,
                   linewidths=2, color="#b84c23", label="Primary nominal baseline", zorder=4)
        ax.set(xlabel=xlabel, ylabel=ylabel, ylim=(-2, 102))
        ax.grid(alpha=0.2)
        ax.legend(fontsize=8, loc="best")
    fig.suptitle("Frozen BCH(63,36,t=5): 12,000 legitimate attempts per condition\n"
                 "20 seeded runs / 120 simulated devices; no retries or filtered readings", fontsize=13)
    fig.savefig(output / "performance_vs_noise.png")
    fig.savefig(output / "performance_vs_noise.svg")
    plt.close(fig)

    colors = ["#176b91", "#ba512b", "#b89a37", "#625b82"]
    categories = [("success_count", "Correct credential"), ("decoder_failures", "Decoder failure"),
                  ("invalid_format", "Invalid padding"), ("miscorrections", "Wrong credential")]
    nominal = sorted([r for r in errors if r["phase"] == "baseline"],
                     key=lambda r: int(r["evaluator_error_count63"]))
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout="constrained")
    x = [int(r["evaluator_error_count63"]) for r in nominal]
    bottom = [0] * len(x)
    for (key, label), color in zip(categories, colors):
        values = [int(r[key]) for r in nominal]
        axes[0].bar(x, values, bottom=bottom, color=color, label=label)
        bottom = [a + b for a, b in zip(bottom, values)]
    for count, total in zip(x, bottom):
        axes[0].annotate(str(total), (count, total), xytext=(0, 4),
                         textcoords="offset points", ha="center", fontsize=8)
    axes[0].set(ylabel="Attempt count", ylim=(0, max(bottom) * 1.16))
    bottom = [0] * len(x)
    for (key, label), color in zip(categories[1:], colors[1:]):
        values = [100 * int(r[key]) / int(r["attempt_count"]) for r in nominal]
        axes[1].bar(x, values, bottom=bottom, color=color, label=label)
        bottom = [a + b for a, b in zip(bottom, values)]
    axes[1].set(ylabel="Failure fraction within error count (%)", ylim=(0, 105))
    for ax in axes:
        ax.axvline(5.5, color="black", linestyle="--", linewidth=1)
        ax.set(xlabel="Actual selected 63-bit errors", xticks=x)
        ax.legend(fontsize=8)
    fig.suptitle("Primary nominal baseline: outcomes over the full error distribution\n"
                 "Dashed line separates <=5 errors from beyond the correction radius", fontsize=13)
    fig.savefig(output / "baseline_error_outcomes.png")
    fig.savefig(output / "baseline_error_outcomes.svg")
    plt.close(fig)

    fig, axes = plt.subplots(2, 3, figsize=(14, 8), layout="constrained")
    for ax, condition in zip(axes.flat, sweep):
        rows = sorted([r for r in errors if r["phase"] == "noise_sweep"
                       and int(r["sweep_index"]) == condition["sweep_index"]],
                      key=lambda r: int(r["evaluator_error_count63"]))
        x = [int(r["evaluator_error_count63"]) for r in rows]
        bottom = [0] * len(x)
        for (key, label), color in zip(categories, colors):
            values = [int(r[key]) for r in rows]
            ax.bar(x, values, bottom=bottom, color=color, label=label)
            bottom = [a + b for a, b in zip(bottom, values)]
        ax.axvline(5.5, color="black", linestyle="--", linewidth=1)
        ax.set(title=f"Noise SD {condition['measurement_noise_std']:g}; FRR {100*condition['frr']:.3f}%",
               xlabel="Actual selected 63-bit errors", ylabel="Attempt count")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=4)
    fig.suptitle("Noise sweep: every observed error count and all reconstruction outcomes\n"
                 "Same devices, references, credentials and helpers across conditions", fontsize=13)
    fig.savefig(output / "sweep_error_outcomes.png")
    fig.savefig(output / "sweep_error_outcomes.svg")
    plt.close(fig)
    (output / "provenance.json").write_text(json.dumps({
        "evidence_directory": str(evidence), "evidence_manifest_sha256": complete["manifest_sha256"],
        "plot_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "matplotlib_version": matplotlib.__version__,
        "authority": "Original CSV/JSON records; plots are derived views, no additional observations",
    }, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plot(args.evidence, args.output)


if __name__ == "__main__":
    main()
