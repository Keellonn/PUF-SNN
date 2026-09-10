# Week 2 Synthetic Data Validation

**Configuration:** `pilot.json`  
**Schema:** `quest-window.schema.json`  
**Python:** 3.12.7 through an MSYS-based virtual environment

## Goal

Test whether the scripted generator creates synthetic Quest-style head-motion windows that follow our data format and cross-session split rules.

## My commands

`python src/python/scripts/generate_data.py`

`python src/python/scripts/validate_data.py`

`python -m unittest discover -s tests -v`

The commands were run using `.venv/bin/python.exe`.

## Results

- Generated 1,800 independent windows
- Generated 120 samples per window
- Used 6 simulated devices and 3 sessions per device
- Used 20 trials per class in each session
- Produced 600 training, 600 validation, and 600 testing windows
- Produced 360 windows for each of the 5 motion classes
- The standalone validator completed without errors
- All 5 automated tests passed
- Unit-test runtime: 0.471 seconds

The tests confirmed that valid generated data passes, the generator is repeatable and balanced, and the validator catches bad quaternions, session leakage, and source trial leakage.

## Interpretation

The generator currently produces synthetic data that follows schema v0.2 and the planned cross-session split. The results also show that the implemented validation checks can catch the tested data and leakage problems.
This does not yet show that the synthetic motion matches real Quest 3 data or that a classifier can correctly identify the motions. Those will be tested later.

## How to do the test on your own, if you aren't using MSYS

Run these commands from the repository root using a normal Windows Python installation.
Create the virtual environment:

`python -m venv .venv`

Activate it in PowerShell:

`.\.venv\Scripts\Activate.ps1`

If PowerShell blocks the activation script, run:

`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

Then activate it again:

`.\.venv\Scripts\Activate.ps1`

Generate and validate the data:

`python src/python/scripts/generate_data.py`
`python src/python/scripts/validate_data.py`

Run the automated tests
`python -m unittest discover -s tests -v`

My computer used an MSYS Python installation, which created `.venv/bin` instead of the usual Windows `.venv/Scripts` folder. I ran `.venv/bin/python.exe` directly. This was an environment difference rather than a problem with the project code.