"""Trusted-loader checks and boundary controls, not new model evaluation."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from puf_snn.anomaly.features import FEATURE_NAMES
from puf_snn.attacks.evaluation import prepare_model_inputs
from puf_snn.auth.config import AuthConfig
from puf_snn.auth.credential_verifier import (
    CredentialAdmissionService, CredentialVerifierRecord, CredentialVerifierStore,
    InMemoryCredentialVerifierKeyProvider,
)
from puf_snn.auth.sender import Sender
from puf_snn.auth.session import RegistryEntry, provision_device
from puf_snn.auth.verifier import Verifier
from puf_snn.frozen_pipeline import (
    DETECTOR_NAMES, FrozenModelBundle, bad_tag_packet, load_frozen_bundle,
    run_window_controls, scoped_path, select_smoke_sources, sha256,
    validate_normalization, validate_smoke_config, validate_thresholds,
)
from puf_snn.integration import processed_record_to_wire_window
from puf_snn.pipeline_v2 import ModelCallCounts, V2InferencePipeline
from puf_snn.reconstruction import enroll
from puf_snn.snn.dataset import LABELS
from scripts.run_week6_smoke import public_audit, require_clean_source, rng_for, selected_bit_errors


CHANNELS = [f"channel-{index}" for index in range(7)]


def config_fixture():
    return {"config_version": "week6-frozen-smoke-v1", "source_split": "validation",
            "source_selection": "first_sorted_window_per_device_and_label", "device_count": 6,
            "puf_seed": 6767, "semantic_control": "position_jump:medium", "torch_threads": 1,
            "input_path": "dataset.jsonl", "input_sha256": "",
            "bundles": {role: {"directory": role, "manifest_sha256": ""}
                        for role in ("snn32", "conventional", "anomaly")}}


def threshold_fixture():
    return {name: {"kind": name.removeprefix("anomaly_").split("_seed")[0],
                   "seed": int(name.split("_seed")[1]), "threshold": .5,
                   "selected_from": "validation", "comparison": "score >= threshold"}
            for name in DETECTOR_NAMES}


def write_fixture_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def bundle_fixture(root):
    config = config_fixture()
    (root / "dataset.jsonl").write_bytes(b"nonsecret-test-data\n")
    config["input_sha256"] = sha256(root / "dataset.jsonl")
    snn_config = {"dataset": {"labels": list(LABELS), "channels": CHANNELS,
                               "time_steps": 120, "input_channels": 7},
                  "model": {"hidden_neurons": 32},
                  "training": {"random_seeds": [7, 17, 27], "training_seeds": [107, 117, 127]}}
    normal = {"fitted_from": "train", "channels": CHANNELS,
              "mean": [0.] * 7, "standard_deviation": [1.] * 7}
    thresholds = threshold_fixture()
    specifications = {
        "snn32": {"config.json": snn_config, "normalization.json": normal,
                  **{f"seed-{seed}/model-state.pt": None for seed in (7, 17, 27)}},
        "conventional": {f"models/{name}-seed-7-storage-refit.joblib": None
                         for name in ("logistic_regression", "random_forest")},
        "anomaly": {"frozen-validation-thresholds.json": thresholds,
                    "anomaly-feature-names.json": list(FEATURE_NAMES),
                    **{f"models/{name}.joblib": None for name in DETECTOR_NAMES}},
    }
    for role, files in specifications.items():
        directory = root / role
        manifest = {"input_sha256": config["input_sha256"], "artifacts": {}, "local_model_artifacts": {}}
        for relative, value in files.items():
            path = directory / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if value is None:
                path.write_bytes(b"not-a-real-pickle; loaders are mocks\n")
            else:
                write_fixture_json(path, value)
            if role == "conventional":
                manifest["local_model_artifacts"][relative] = {"sha256": sha256(path)}
            else:
                manifest["artifacts"][relative] = sha256(path)
        (directory / "COMPLETE").write_text("test fixture", encoding="utf-8")
        write_fixture_json(directory / "manifest.json", manifest)
        config["bundles"][role]["manifest_sha256"] = sha256(directory / "manifest.json")
    return config, snn_config, thresholds


def record_fixture():
    return {"window_id": "smoke-unit-window", "device_id": "source-device", "session_id": "source-session",
            "label": "nod", "split": "validation", "window_start_ns": 1_000_000_000,
            "window_end_ns": 3_000_000_000, "sequence_number": 999,
            "samples": [{"sample_index": index, "capture_time_ns": 1_000_000_000 + index * 16_666_667,
                         "position_m": [index * .0001, 0., .1],
                         "orientation_xyzw": [0., 0., 0., 1.], "tracking_valid": True}
                        for index in range(120)]}


class FrozenPipelineTests(unittest.TestCase):
    def test_smoke_config_rejects_test_split_or_new_selection(self):
        for key, value in (("source_split", "test"), ("puf_seed", 10), ("semantic_control", "position_jump:high")):
            config = config_fixture()
            config[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_smoke_config(config)

    def test_smoke_config_requires_every_bundle(self):
        config = config_fixture()
        del config["bundles"]["anomaly"]
        with self.assertRaises(ValueError):
            validate_smoke_config(config)

    def test_artifact_paths_cannot_escape_directory(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for path in ("../outside", str(root.parent / "outside"), "."):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    scoped_path(root, path)

    def test_final_binary_hash_failure_precedes_all_deserialization(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, _, _ = bundle_fixture(root)
            (root / "anomaly/models" / f"{sorted(DETECTOR_NAMES)[-1]}.joblib").write_bytes(b"changed")
            with patch("puf_snn.frozen_pipeline.joblib.load") as pickle_load, \
                 patch("puf_snn.frozen_pipeline.torch.load") as torch_load:
                with self.assertRaisesRegex(ValueError, "hash-mismatched"):
                    load_frozen_bundle(root, config)
                pickle_load.assert_not_called()
                torch_load.assert_not_called()

    def test_missing_ignored_storage_model_never_triggers_refit(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, _, _ = bundle_fixture(root)
            (root / "conventional/models/logistic_regression-seed-7-storage-refit.joblib").unlink()
            with patch("puf_snn.frozen_pipeline.joblib.load") as loader:
                with self.assertRaisesRegex(ValueError, "do not refit"):
                    load_frozen_bundle(root, config)
                loader.assert_not_called()

    def test_pinned_manifest_change_is_rejected(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, _, _ = bundle_fixture(root)
            (root / "snn32/manifest.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash-mismatched"):
                load_frozen_bundle(root, config)

    def test_wrong_source_hash_is_rejected(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, _, _ = bundle_fixture(root)
            (root / "dataset.jsonl").write_bytes(b"different")
            with self.assertRaises(ValueError):
                load_frozen_bundle(root, config)

    def test_frozen_loader_restores_all_models_and_exact_thresholds(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            config, snn_config, thresholds = bundle_fixture(root)

            def load_pickle(path):
                if "storage-refit" in path.name:
                    return SimpleNamespace(n_features_in_=840, classes_=np.asarray(LABELS))
                name = path.stem
                entry = thresholds[name]
                return {"model": object(), "seed": entry["seed"], "feature_names": FEATURE_NAMES,
                        "threshold": {key: value for key, value in entry.items() if key not in ("kind", "seed")}}

            def load_checkpoint(path, **kwargs):
                self.assertTrue(kwargs["weights_only"])
                self.assertEqual(kwargs["map_location"], "cpu")
                seed = int(path.parent.name.split("-")[1])
                return {"seed": seed, "training_seed": seed + 100, "labels": LABELS,
                        "model_config": snn_config["model"], "state_dict": {}}

            with patch("puf_snn.frozen_pipeline.joblib.load", side_effect=load_pickle) as pickle_load, \
                 patch("puf_snn.frozen_pipeline.torch.load", side_effect=load_checkpoint) as checkpoint_load, \
                 patch("puf_snn.frozen_pipeline.create_model", side_effect=lambda _: Mock()):
                bundle = load_frozen_bundle(root, config)
            self.assertEqual(len(bundle.motion), 5)
            self.assertEqual(len(bundle.detectors), 6)
            self.assertEqual(pickle_load.call_count, 8)
            self.assertEqual(checkpoint_load.call_count, 3)
            for name, entry in bundle.detectors.items():
                self.assertEqual(entry["threshold"], thresholds[name])

    def test_normalization_is_training_only_and_finite(self):
        config = {"dataset": {"channels": CHANNELS}}
        original = {"fitted_from": "train", "channels": CHANNELS, "mean": [0.] * 7, "standard_deviation": [1.] * 7}
        validate_normalization(original, config)
        for key, value in (("fitted_from", "test"), ("mean", [float("nan")] * 7),
                           ("standard_deviation", [0.] * 7), ("channels", list(reversed(CHANNELS)))):
            changed = deepcopy(original)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_normalization(changed, config)

    def test_thresholds_require_validation_selection_and_all_six_models(self):
        thresholds = threshold_fixture()
        validate_thresholds(thresholds)
        name = sorted(thresholds)[0]
        for key, value in (("selected_from", "test"), ("comparison", "score > threshold"),
                           ("threshold", float("nan")), ("seed", 7)):
            changed = deepcopy(thresholds)
            changed[name][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_thresholds(changed)
        del thresholds[name]
        with self.assertRaises(ValueError):
            validate_thresholds(thresholds)

    def test_cohort_is_validation_only_and_order_independent(self):
        records = [{"device_id": f"device-{device}", "label": label, "split": split,
                    "window_id": f"{split}-{device}-{label}-{suffix}"}
                   for device in range(6) for label in LABELS for split in ("validation", "test")
                   for suffix in ("b", "a")]
        selected = select_smoke_sources(records)
        self.assertEqual(len(selected), 30)
        self.assertTrue(all(row["split"] == "validation" and row["window_id"].endswith("-a") for row in selected))
        self.assertEqual(selected, select_smoke_sources(list(reversed(records))))

    def test_missing_class_does_not_silently_shrink_cohort(self):
        records = [{"device_id": f"device-{device}", "label": label, "split": "validation", "window_id": f"{device}-{label}"}
                   for device in range(6) for label in LABELS if not (device == 0 and label == "still")]
        with self.assertRaises(ValueError):
            select_smoke_sources(records)

    def test_bad_tag_mutation_changes_only_tag(self):
        envelope = {"data": "unchanged", "authentication": {"tag_hex": "0" * 64, "other": 2}}
        changed = json.loads(bad_tag_packet(json.dumps(envelope).encode()))
        self.assertEqual(changed["data"], envelope["data"])
        self.assertEqual(changed["authentication"]["other"], 2)
        self.assertEqual(changed["authentication"]["tag_hex"], "1" + "0" * 63)

    def active_pipeline(self):
        # Explicit NONSECRET synthetic fixtures, not noise-study observations.
        credential, reference = bytes.fromhex("000001a5"), (0,) * 64
        helper = enroll(reference, credential, enrollment_id="smoke-fixture-enrollment")
        provider = InMemoryCredentialVerifierKeyProvider("smoke-fixture-key", bytes(range(32)))
        record = CredentialVerifierRecord.enroll(device_id="smoke-fixture-device",
            enrollment_id=helper.enrollment_id, reconstruction_id=helper.config.version,
            verifier_key_id="smoke-fixture-key", credential4=credential, key_provider=provider)
        service = CredentialAdmissionService(CredentialVerifierStore([record]), provider)
        auth = AuthConfig()
        sender = Sender(provision_device("smoke-fixture-device", helper.enrollment_id, helper),
                        auth.session_config().limits, admission_service=service)
        verifier = Verifier([RegistryEntry("smoke-fixture-device", helper.enrollment_id, credential)],
                            auth.session_config(), admission_service=service)
        motion = Mock(return_value={"motion": "still"})
        anomaly = Mock(return_value={"detector": {"score": .9, "flag": True}})
        pipeline = V2InferencePipeline(sender, verifier, prepare_model_inputs, motion, anomaly)
        self.assertEqual(pipeline.establish(lambda: reference, "smoke-fixture-attempt").decision, "accept")
        self.addCleanup(verifier.close_all_sessions)
        return pipeline, motion, anomaly

    def test_real_boundary_smoke_has_three_composite_deliveries_and_zero_reject_calls(self):
        pipeline, motion, anomaly = self.active_pipeline()
        source = record_fixture()
        changed = deepcopy(source)
        for row in changed["samples"][60:]:
            row["position_m"][0] += .05
        rows = run_window_controls(pipeline, source, changed, {"motion"}, {"detector"})
        self.assertEqual(len(rows), 6)
        self.assertEqual(sum(row["decision"] == "accept" for row in rows), 3)
        self.assertEqual(pipeline.calls, ModelCallCounts(3, 3, 3))
        self.assertEqual(motion.call_count, 3)
        self.assertEqual(anomaly.call_count, 3)
        self.assertEqual(pipeline.verifier.session_status(pipeline.sender.session_id).last_accepted, 2)
        for row in rows:
            if row["decision"] == "reject":
                self.assertEqual(row["calls_before"], row["calls_after"])
                self.assertEqual(row["last_accepted_before"], row["last_accepted_after"])

    def test_no_class_or_flag_expectation_is_imposed_by_smoke(self):
        pipeline, _, _ = self.active_pipeline()
        rows = run_window_controls(pipeline, record_fixture(), record_fixture(), {"motion"}, {"detector"})
        self.assertEqual(rows[1]["motion_predictions"], {"motion": "still"})
        self.assertEqual(rows[3]["decision"], "accept")
        self.assertTrue(rows[3]["anomaly_predictions"]["detector"]["flag"])

    def test_composite_omission_is_not_a_pass(self):
        pipeline, _, _ = self.active_pipeline()
        with self.assertRaisesRegex(RuntimeError, "omitted"):
            run_window_controls(pipeline, record_fixture(), record_fixture(), {"missing-model"}, {"detector"})

    def test_bundle_rejects_wrong_model_input_shapes(self):
        bundle = FrozenModelBundle({}, {}, {})
        for sequence in (np.zeros((119, 7)), np.full((120, 7), np.nan)):
            with self.assertRaises(ValueError):
                bundle.motion_predictions(sequence)
        for features in (np.zeros(47), np.full(48, np.inf)):
            with self.assertRaises(ValueError):
                bundle.anomaly_predictions(features)

    def test_public_audit_filter_drops_any_unknown_secret_field(self):
        endpoint = SimpleNamespace(audit_records=[{"reason": "accepted", "candidate_credential": "do-not-export",
                                                  "key": "do-not-export", "sequence_number": 0}])
        self.assertEqual(public_audit(endpoint), [{"reason": "accepted", "sequence_number": 0}])

    def test_separate_seed_domains_do_not_share_read_or_credential_streams(self):
        first = [rng_for("week6-smoke-v1:6767:0:measurement").getrandbits(64) for _ in range(2)]
        self.assertEqual(first[0], first[1])
        self.assertNotEqual(first[0], rng_for("week6-smoke-v1:6767:0:credential").getrandbits(64))

    def test_dirty_source_stops_before_an_experiment(self):
        with patch("scripts.run_week6_smoke.subprocess.run", return_value=SimpleNamespace(stdout=" M changed.py\n")):
            with self.assertRaisesRegex(ValueError, "commit the implementation first"):
                require_clean_source(Path("."))

    def test_error_accounting_uses_only_frozen_selected_response_bits(self):
        reference = (0,) * 64
        self.assertEqual(selected_bit_errors(reference, (1,) * 64), 63)
        self.assertEqual(selected_bit_errors(reference, (0,) * 63 + (1,)), 0)
        with self.assertRaises(ValueError):
            selected_bit_errors(reference, (0,) * 63)


if __name__ == "__main__":
    unittest.main()
