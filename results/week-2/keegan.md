# Week 2 Synthetic Data Validation

**Configuration:** `configs/pilot.json`  
**Schema:** `schemas/quest-window.schema.json`  
**Generator seed:** 7  
**Python:** 3.12.7 through an MSYS-based virtual environment

## Goal

Test whether the scripted generator creates synthetic Quest-style head-motion windows that follow our data format and cross-session split rules.

## Original commands

`python src/python/scripts/generate_data.py`

`python src/python/scripts/validate_data.py`

`python -m unittest discover -s tests -v`

The commands were run using `.venv/bin/python.exe`.

## Results

- Generated 1,800 synthetic windows 
- Generated 120 samples per window
- Used 6 synthetic device groups and 3 sessions per device
- Used 20 trials per class in each session
- Produced 600 training, 600 validation, and 600 testing windows
- Produced 360 windows for each of the 5 motion classes
- The standalone validator completed without errors
- All 5 automated tests passed
- Unit-test runtime: 0.471 seconds

The 5 original tests confirmed that valid generated data passes, the generator is repeatable and balanced, and the validator catches bad quaternions, session leakage, and source trial leakage.

## Interpretation

The generator currently produces synthetic data that follows schema v0.2 and the planned cross-session split. The results also show that the implemented validation checks can catch the tested data and leakage problems.
This does not show that the synthetic motion matches real Quest 3 data. The later conventional-classifier results are reported separately as Week 3 work.

The current generator directly creates 120 fixed-grid samples and doesn't perform resampling. It doesn't apply stable device-specific or session-specific motion effects. Device IDs are grouping identifiers, and the fixed class templates may make classification artificially easy.

The 1,800 windows are 1,800 synthetic windows across 6 device groups and 18 device-session groups. They aren't claimed to be statistically independent.

## Expanded evidence required after Week 2 feedback

Dr. Garcia requested evidence that can be inspected and reproduced instead of only a statement that validation passed. The updated analysis should produce
- a table of class counts for every device and session
- missing-sample, invalid-tracking, rejected-window, fixed-grid/resampling, and data-quality counts
- each test's purpose, expected result, and actual result
- the complete identifier lists and overlap checks for every split
- representative position and orientation trajectories
- a device/session comparison that shows the current lack of stable group effects
- one complete example window
- the configuration, environment, repository link, source commit, commands, and interpretation

The original results above remain the recorded 5-test run. The expanded tests and evidence must be rerun before their results are reported as passing.

## Repository and provenance

- Repository: https://github.com/Keellonn/PUF-SNN
- Original Week 2 source commit: not recorded in the original result file
- Updated source commit: add the commit ID containing the revised generator, validator, configuration, schema, and tests after committing them
- Evidence commit: add the later commit ID containing the generated tables, figures, and updated results

## Recreate my synthetic data baseline

From the repository root:

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
python src/python/scripts/generate_data.py
python src/python/scripts/validate_data.py
python src/python/scripts/analyze_synthetic_data.py --run-tests --machine-model "YOUR LAPTOP MODEL"


The final command runs the updated data and split tests and records their actual outcomes. Replace the machine-model text with the actual computer model. Stop and investigate any failing command before reporting the results.
