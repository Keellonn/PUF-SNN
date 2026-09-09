# PUF-SNN

PUF-SNN is a research project based on protecting Quest 3 head motion data before it reaches a motion classification model.

The project combines 2 parts:

1. A simulated noisy PUF helps create a device-bound session credential. That credential is used to protect each sensor window.
2. A conventional classifier or spiking neural network identifies the motion. A separate abnormality detector checks for unusual sensor patterns.

The Quest 3 doesn't give us access to a physical PUF. All PUF work in the first version is simulated.

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

- `docs/spec.md` contains the current project specification.
- `docs/xr-snn-design.md` contains Keegan's Quest, data, model, and abnormality plan
- `docs/puf-auth-design.md` contains Will's PUF and authentication plan
- `docs/literature-review.md` contains the literature matrix and research gap
- `docs/week2-implementation-plan.md` contains this week's tasks and owners
- `docs/faculty-decision-memo.md` contains questions that require faculty approval
- `docs/research-logs/` contains our individual research logs
- `configs/pilot.json` contains the experiment settings
- `schemas/` contains the machine readable data formats
- `src/quest-logger/` contains the future Unity logger
- `src/python/` contains the Python prototype
- `tests/` contains data and leakage tests
- `data/` explains the data storage rules
- `results/` contains small result summaries and approved figures