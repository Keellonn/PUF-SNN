import csv
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "python"))

from scripts.run_puf_baseline import run_baseline, save_tables, simulate
from puf_snn.puf.variables import ReadConditions, load_config

class ExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = replace(load_config(ROOT / "configs/puf_baseline.json"),
                              number_of_devices=3, repeated_reads=8,
                              number_of_oscillators=16,
                              noise_sweep=(0.0, 0.1, 1.0))

    def test_reproducibility_and_seed_sensitivity(self) -> None:
        first = simulate(self.config)
        self.assertEqual(first, simulate(self.config))
        changed = simulate(replace(self.config, random_seed=4321))
        self.assertNotEqual(first["devices"], changed["devices"])

    def test_counts_aggregation_and_zero_noise(self) -> None:
        tables = simulate(self.config)
        self.assertEqual(len(tables["metrics"]), 24)
        self.assertEqual(len(tables["noise_sweep"]), 72)
        self.assertEqual(len(tables["uniqueness_pairs"]), 3)
        self.assertEqual(tables["noise_sweep_summary"][0]["mean_ber"], 0)
        for device in tables["devices"]:
            rows = [row for row in tables["metrics"]
                    if row["device_id"] == device["device_id"]]
            expected = sum(row["hamming_distance"] for row in rows) / (8 * 8)
            self.assertEqual(device["mean_ber"], expected)
            self.assertEqual(device["mean_reliability"], 1 - expected)

    def test_noisy_reference_and_sweep_persistence(self) -> None:
        config = replace(self.config,
                         reference_conditions=ReadConditions(0, 10))
        tables = simulate(config)
        self.assertGreater(tables["noise_sweep_summary"][0]["mean_ber"], 0)
        other = simulate(replace(config, noise_sweep=(2.0, 0.0)))
        self.assertEqual(tables["devices"], other["devices"])
        self.assertEqual(tables["uniqueness_pairs"], other["uniqueness_pairs"])

    def test_all_pairs_response_length(self) -> None:
        tables = simulate(replace(self.config, pairing_scheme="all_pairs"))
        self.assertEqual(tables["metrics"][0]["response_length"], 120)

    def test_outputs_reproduce_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first = run_baseline(self.config, Path(temporary))
            second = run_baseline(self.config, Path(temporary))
            self.assertNotEqual(first, second)
            for path in first.glob("*.csv"):
                self.assertEqual(path.read_bytes(),
                                 (second / path.name).read_bytes())
                with path.open(newline="", encoding="utf-8") as file:
                    self.assertTrue(list(csv.DictReader(file)))
            metadata = json.loads((first / "metadata.json").read_text())
            self.assertEqual(metadata["random_seed"], 1234)
            self.assertEqual(len(metadata["oscillator_pairs"]), 8)
            self.assertTrue(metadata["source_sha256"])
            expected_sources = {
                str(path.relative_to(ROOT))
                for path in (ROOT / "src/python/puf_snn/puf").glob("*.py")
            } | {str(Path("src/python/scripts/run_puf_baseline.py")),
                 "requirements.txt"}
            self.assertEqual(set(metadata["source_sha256"]), expected_sources)
            for source, fingerprint in metadata["source_sha256"].items():
                self.assertEqual(fingerprint, hashlib.sha256(
                    (ROOT / source).read_bytes()).hexdigest())
            self.assertTrue((first / "COMPLETE").exists())
            plots = list((first / "plots").glob("*.png"))
            self.assertEqual(len(plots), 3)
            for plot in plots:
                self.assertTrue(
                    plot.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
                )

    def test_failed_plotting_does_not_mark_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with patch("scripts.run_puf_baseline.plot_results",
                       side_effect=OSError("plot failure")):
                with self.assertRaises(OSError):
                    run_baseline(self.config, Path(temporary))
            self.assertFalse(list(Path(temporary).glob("*/COMPLETE")))

    def test_private_repo_baseline_csvs_match_exactly(self) -> None:
        # Captured from PUF_simulator/results/run-seed-1234-bp9sr2_0,
        # a completed private-repo baseline (Python 3.12.4). These hashes
        # cover every reference/read bit, metric, row order, and aggregate.
        expected = {
            "devices.csv":
                "0c3a22599e84c587691955a1ca6d976ff64dbaa3abfa2b817c55c9f469db5afe",
            "metrics.csv":
                "2b1f0a4b79deab7b29b1ea71bf70583dc2ca5f41e1620f089e3b7bb2ec56e814",
            "noise_sweep.csv":
                "21956f06b9f3e6081994743e74f45bd6b391ffdab7350e05f16b029368846b24",
            "noise_sweep_summary.csv":
                "da49f29603979b0efaf8d69bc608e45eb944421cb99ca83641e43ab422b4a5b7",
            "summary.csv":
                "ad95c9211712933a6dc7c24a5503e350a0a9e25359413bff454f87b77f4cd67b",
            "uniqueness_pairs.csv":
                "e57dbb259375e41b0f854c8a3740341cb15dff68ceaf2834fd9974fe50209e93",
        }
        config = load_config(ROOT / "configs/puf_baseline.json")
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            save_tables(directory, simulate(config))
            actual = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                      for path in directory.glob("*.csv")}
        self.assertEqual(actual, expected)

    def test_script_defaults_work_outside_repository(self) -> None:
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run(
                [sys.executable, str(ROOT / "src/python/scripts/run_puf_baseline.py"),
                 "--validate-config"],
                cwd=temporary, env=environment, capture_output=True, text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(ROOT / "configs/puf_baseline.json"), result.stdout)

    def test_script_preserves_explicit_relative_paths(self) -> None:
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "custom config.json").write_text(
                json.dumps(asdict(self.config)), encoding="utf-8"
            )
            result = subprocess.run(
                [sys.executable, str(ROOT / "src/python/scripts/run_puf_baseline.py"),
                 "--config", "custom config.json", "--output-dir", "custom output"],
                cwd=directory, env=environment, capture_output=True, text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            runs = list((directory / "custom output").glob("run-seed-1234-*"))
            self.assertEqual(len(runs), 1)
            self.assertTrue((runs[0] / "COMPLETE").exists())
            self.assertEqual(json.loads((runs[0] / "config.json").read_text()),
                             json.loads((directory / "custom config.json").read_text()))
