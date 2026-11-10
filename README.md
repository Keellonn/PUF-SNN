# PUF-SNN

PUF-SNN is a research project based on protecting Quest 3 head motion data before
it reaches a motion classification model.

The project combines two parts:

1. A simulated noisy PUF helps reconstruct a device-bound session credential used
   to authenticate sensor windows.
2. A conventional classifier or spiking neural network identifies the motion.
   A separate anomaly detector checks for unusual sensor patterns.

The Quest 3 does not expose a physical PUF for this project. The PUF work is simulated.

## Start here

- [Documentation and weekly reports](docs/README.md)
- [Current study decisions and remaining work](docs/week10/week10-study-status.md)
- [Results by week](results/README.md)
- [Keegan's research log](docs/research-logs/keegan.md) and [Will's research log](docs/research-logs/will.md)
- [Quest logger setup](src/quest-logger/README.md)

## Current checkpoint

The [Week 11 technical review](docs/week11/README.md) adds a focus-loss stop
safeguard and clarifies source replay, test counts, finalized metric replay and
historical timing. Actual Quest Link and storage checks remain open.

The [Week 10 source integration](results/week-10/keegan/source-integration-20261103-001/README.md)
connects optional accepted-source retention to the logger with versioned policies,
durable receipts and interrupted-file checks, tested using artificial poses.
The default policy and saved scenes keep source retention off. The planned study
route is laptop-hosted Unity through Quest Link. Device readiness, staff training,
storage arrangements and institutional review remain open; see the
[study-status page](docs/week10/week10-study-status.md).

Earlier [Week 9](docs/week9/README.md) and [Week 8](docs/week8/README.md) reports
retain their original software, model, timing and reliability scopes. Use their
receipts for test counts and source identities.

## Research question

Can a software prototype using a simulated noisy PUF-derived session credential
reject replayed, modified or misattributed Quest 3 head-motion windows before
inference while meeting the study's attack-rejection, model-quality and timing targets?

## Data and models

The five prompted classes are `nod`, `shake`, `look_left_return`,
`look_right_return` and `still`. Each window lasts two seconds and contains
120 samples after resampling to 60 Hz.

Authentication checks device/session identity, integrity, freshness and sequence
order before release to the model pipeline. The motion classifier predicts one
of the five classes. The separate anomaly detector checks sensor perturbations
such as noise, drift, missing samples, frozen poses, timestamp changes and jumps.
Correct authentication alone does not establish that the sensor content is normal.

Current findings come from software and synthetic-data experiments. Research
motion collection requires the applicable institutional authorization.

## Repository layout

| Folder | Contents |
|---|---|
| [docs](docs/README.md) | Design documents, weekly report indexes, plans and research logs |
| [configs](configs/) | Experiment configurations |
| [schemas](schemas/) | Machine-readable data formats |
| [src/quest-logger](src/quest-logger/README.md) | Unity logger, source processing and native tests |
| [src/python](src/python/) | Authentication, data, models, analysis and validation code |
| [tests](tests/) | Python implementation and experiment tests |
| [tools](tools/README.md) | Scoped reproduction, test-receipt and resource-profile tools |
| [requirements](requirements/) | Retained dependency profiles |
| [data](data/README.md) | Storage rules; generated/private data are excluded |
| [results](results/README.md) | Dated result bundles and receipts |
| [presentations](presentations/README.md) | Retained presentation PDFs |

The root PowerShell entry points keep their existing names and locations:
`run_simulation.ps1`, `run_layer2.ps1`, `run_layer3.ps1` and `run_tier1.ps1`.

## Recreate Keegan's synthetic-data baseline

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python src/python/scripts/generate_data.py
python src/python/scripts/validate_data.py
python src/python/scripts/analyze_synthetic_data.py --run-tests --machine-model "YOUR LAPTOP MODEL"
```

These commands generate a new baseline. Historical frozen experiments have their
own inputs, dependencies and reproduction instructions in the weekly reports.

[GitHub repository](https://github.com/Keellonn/PUF-SNN)
