"""Bounded current-source quality equivalence; not model selection or timing."""

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np

from puf_snn.frozen_pipeline import select_smoke_sources
from puf_snn.quality_benchmark import PRIMARY
from puf_snn.quality_dyadic import QUALITY_MODES


VERSION = "week8-quality-validation-v1"
POLICIES = ("single-read-v1", "majority-3-v1")


def fixed_config():
    return dict(config_version=VERSION, frozen_config="configs/week6_smoke.json",
        modes=list(QUALITY_MODES), conditions=deepcopy(list(PRIMARY)),
        acquisition_policies=list(POLICIES), source_split="validation", source_count=30,
        source_selection="first_sorted_window_per_device_and_label", semantic_control="position_jump:medium",
        controlled_read_flips=[[2, 8, 19], [2, 7, 22], [8, 7, 35]],
        native_threads=1, training=False, threshold_selection=False, latency_measurement=False)


def validate_config(config):
    if json.dumps(config, sort_keys=True) != json.dumps(fixed_config(), sort_keys=True):
        raise ValueError("configuration differs from the bounded functional protocol")


def select_sources(records):
    # Verify source trial/session ownership across the complete saved dataset,
    # not just the selected cohort. This does not test cross-person transfer.
    window_ids, trial_splits, session_splits = set(), {}, {}
    for row in records:
        if row["split"] not in ("train", "validation", "test") or row["window_id"] in window_ids:
            raise ValueError("sources require valid splits and unique window identifiers")
        window_ids.add(row["window_id"])
        for identity, mapping in ((row["source_trial_id"], trial_splits), (row["session_id"], session_splits)):
            if identity in mapping and mapping[identity] != row["split"]:
                raise ValueError("a source trial or session crosses dataset splits")
            mapping[identity] = row["split"]
    selected = select_smoke_sources(records)
    if len(selected) != 30 or len({row["window_id"] for row in selected}) != 30:
        raise ValueError("expected 30 unique validation sources")
    return selected


def fingerprint(array, shape):
    value = np.asarray(array, dtype="<f8")
    if value.shape != shape or not np.isfinite(value).all():
        raise ValueError("model input has an unexpected shape or nonfinite value")
    return hashlib.sha256(value.tobytes(order="C")).hexdigest()


def public_windows(rows):
    # Fresh event IDs are neither comparable model behavior nor output authority.
    # Actual verifier-minted events are checked by run_window_controls, unchanged.
    fields = ("condition", "decision", "stage", "reason", "sequence_number", "calls_before", "calls_after",
              "last_accepted_before", "last_accepted_after", "motion_predictions", "anomaly_predictions")
    return [{key: deepcopy(row[key]) for key in fields if key in row} for row in rows]


def cell_key(row):
    return row["acquisition_policy"], row["configuration"], row["source_window_id"]


def reconcile(cells, expected_keys):
    by_mode = {mode: {} for mode in QUALITY_MODES}
    for row in cells:
        mode, key = row["mode"], cell_key(row)
        if mode not in by_mode or key not in expected_keys or key in by_mode[mode]:
            raise ValueError("unknown, unexpected or duplicate comparison cell")
        expected_reads = 1 if key[0] == POLICIES[0] else 3
        if row["read_count"] != expected_reads or row["admission"]["decision"] != "accept":
            raise ValueError("controlled admission/read count did not match; no retry or replacement")
        windows = row["windows"]
        wanted = Counter({("bad_tag", "reject"): 1, ("clean", "accept"): 1,
            ("exact_replay", "reject"): 1, ("pre_tag_position_jump_medium", "accept"): 1,
            ("113_tracking_valid", "reject"): 1, ("next_valid_after_refusals", "accept"): 1})
        if Counter((w["condition"], w["decision"]) for w in windows) != wanted:
            raise ValueError("comparison omitted or duplicated a functional control")
        count = 0
        for window in windows:
            accepted = window["decision"] == "accept"
            if (window["calls_before"] != dict(preprocessing=count, motion=count, anomaly=count)
                    or window["last_accepted_before"] != (count - 1 if count else None)):
                raise ValueError("per-control starting state or call counts disagree")
            count += int(accepted)
            if (window["calls_after"] != dict(preprocessing=count, motion=count, anomaly=count)
                    or window["last_accepted_after"] != (count - 1 if count else None)):
                raise ValueError("refusal changed calls/state or acceptance did not advance once")
            if accepted != ("motion_predictions" in window and "anomaly_predictions" in window):
                raise ValueError("prediction presence disagrees with acceptance")
            if not accepted and any(k in window for k in ("motion_predictions", "anomaly_predictions")):
                raise ValueError("rejected control contains model output")
        if (row["consumer_calls"] != dict(preprocessing=3, motion=3, anomaly=3)
                or len(row["model_inputs"]) != 3 or row["final_state"] != dict(state="ACTIVE", accepted_count=3, last_accepted=2)
                or row["consumed_events"] != 3 or row["incomplete"]):
            raise ValueError("consumer, release or final session state does not reconcile")
        by_mode[mode][key] = row
    if any(set(rows) != expected_keys for rows in by_mode.values()):
        raise ValueError("one or more planned comparison cells are missing")
    for key in sorted(expected_keys):
        a, b = (by_mode[mode][key] for mode in QUALITY_MODES)
        if {k: v for k, v in a.items() if k != "mode"} != {k: v for k, v in b.items() if k != "mode"}:
            raise ValueError(f"quality implementations disagree for {key}; retain evidence and stop")
    # The recovery policies should be transparent to the accepted downstream data.
    for mode, rows in by_mode.items():
        for policy, configuration, source in sorted(expected_keys):
            if policy != POLICIES[0]:
                continue
            a, b = rows[(POLICIES[0], configuration, source)], rows[(POLICIES[1], configuration, source)]
            exclude = {"acquisition_policy", "read_count"}
            if {k: v for k, v in a.items() if k not in exclude} != {k: v for k, v in b.items() if k not in exclude}:
                raise ValueError("recovery-policy integration changed downstream behavior")
    return dict(planned_sessions=len(expected_keys) * 2, admitted_sessions=len(cells),
        matched_quality_pairs=len(expected_keys), matched_recovery_pairs=len(expected_keys),
        accepted_windows=len(cells) * 3, rejected_controls=len(cells) * 3,
        response_reads=sum(row["read_count"] for row in cells),
        rejected_control_model_calls=0, all_inputs_predictions_decisions_and_states_match=True)


def source_hashes(root):
    """Identify actual current code/config bytes, including uncommitted additions.

    An enclosing base commit is context, not a claim that these are its exact
    contents. Research logs and result outputs are deliberately outside this map.
    """
    root = Path(root).resolve()
    files = [*root.joinpath("src/python").rglob("*.py"), *root.joinpath("tests").rglob("*.py"),
             *root.joinpath("configs").glob("*.json"), root / "pyproject.toml", root / "requirements.txt",
             *root.joinpath("requirements").rglob("*.txt")]
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(files)}
