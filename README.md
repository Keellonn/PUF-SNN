# PUF-SNN

PUF-SNN is a research project based on protecting Quest 3 head motion data before it reaches a motion classification model.

The project combines 2 parts:

1. A simulated noisy PUF helps create a device-bound session credential. That credential is used to protect each sensor window.
2. A conventional classifier or spiking neural network identifies the motion. A separate abnormality detector checks for unusual sensor patterns.

The Quest 3 doesn't give us access to a physical PUF. All PUF work in the first version is simulated.

## Current validation checkpoint

October 27 Week 9 work adds a durable trial ledger to the Quest controller and
a read-only Python reconciler, tested with artificial poses. The ledger keeps
rejected, skipped, stopped and interrupted trials in the accounting. Recording
remains disabled by default; headset readiness and institutional review are
still pending. No new model, recovery-reliability or timing result is claimed.

- [Week 9 logger evidence](results/week-9/keegan/README.md)
- [Readiness checklist and remaining weekly work](docs/week9-logger-readiness.md)
- [Ledger behavior, denominators and commands](docs/quest-trial-ledger.md)

Keegan's October 22 Week 8 work adds behavioral-equivalence checks for the
optional faster quality arithmetic using frozen models and both existing
credential-recovery policies. The bounded comparison completed 360 controlled
sessions, and the selected root-discovery regression passed 1,085 tests.
No default was changed, and this is not a new timing, reconstruction-reliability,
or real-headset result.

- [Week 8 results and receipts](results/week-8/keegan/README.md)
- [Optimization decision and remaining limits](docs/week8-keegan-validation.md)
- [Reproduction instructions and frozen-input requirements](docs/week8-keegan-reproduction.md)

Earlier week-specific reports remain records of their own dated checkpoints.

## Research question

Can a software prototype using a simulated noisy PUF-derived session credential reject replayed, modified, or misattributed Quest 3 head-motion windows before SNN inference while meeting our attack-rejection, macro-F1-loss, and latency targets?

## Initial task

The first experiment uses 5 head motion classes
- nod
- shake
- look_left_return
- look_right_return
- still

Each window lasts 2 seconds and contains 120 samples after resampling to 60 Hz

## What each part does

Authentication checks
- Device and session identity
- Data integrity
- Freshness
- Sequence order
- Replays and duplicates

The motion classifier predicts one of the 5 head-motion classes.

The abnormality detector separately checks for unusual but correctly authenticated sensor behavior, including
- Noise
- Drift
- Missing samples
- Frozen poses
- Timestamp changes
- Sudden pose jumps

A replayed window may look normal to the SNN, so abnormality detection doesn't replace authentication

## Pilot scope

The first version uses
- Quest 3 head position
- Quaternion orientation
- Capture timestamps
- Tracking-valid status
- Fixed 2-second windows
- Logistic regression and random forest before the SNN
- A simulated PUF before any physical hardware work
- Synthetic data until headset access is approved

We won't collect human subject data until faculty confirms the correct institutional process

## Repository

- `docs/project-specification.md` contains the current project specification.
- `docs/xr-snn-design.md` contains Keegan's Quest, data, model, and abnormality plan
- `docs/puf-auth-design.md` contains Will's PUF and authentication plan
- `docs/literature-review.md` contains the literature matrix and research gap
- `docs/implementation-plans/week-2.md` contains week 2 tasks and owners
- `docs/faculty-decision-memo.md` contains questions that require faculty approval
- `docs/research-logs/` contains our individual research logs
- `configs/pilot.json` contains the experiment settings
- `schemas/` contains the machine readable data formats
- `src/quest-logger/` - contains the Unity Quest head-motion logger, automated tests, and setup documentation
- `src/python/` contains the Python prototype
- `tests/` contains data and leakage tests
- `data/` explains the data storage rules
- `results/` contains small result summaries and approved figures

## Recreate Keegan's synthetic-data baseline

From the repository root

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python src/python/scripts/generate_data.py
python src/python/scripts/validate_data.py
python src/python/scripts/analyze_synthetic_data.py --run-tests --machine-model "YOUR LAPTOP MODEL"

## Repository 

Repository: https://github.com/Keellonn/PUF-SNN
