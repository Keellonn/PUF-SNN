# Python Prototype

This folder contains the Week 2 syntheticdata generator and validator
The code creates Quest style head motion windows and checks that they follow our data and dataset-split rules.

## Current features

- Generates 5 head motion classes
- Creates 1,800 synthetic windows
- Stores 120 samples in each window
- Validates timestamps, quaternions, tracking, IDs, and sequences
- Checks for trial and session leakage

The current code only uses Python's built-in libraries. No extra packages are needed yet.

## 1. Run the data tests

in powershell
python -m unittest discover -s tests -p "test_data.py" -v

These tests check that the generator is repeatable, the data is balanced, clean data passes validation, and bad quaternions are rejected.

## 2. Run the leakage tests

in powershell
python -m unittest discover -s tests -p "test_splits.py" -v


These tests check that a trial or session can't appear in multiple dataset splits.

## 3. Generate the full dataset

in powershell
python src/python/scripts/generate_data.py


This creates
data/generated/synthetic-windows.jsonl

Expected output
1,800 total windows
360 windows per motion class
600 training windows
600 validation windows
600 testing windows


## 4. Validate the full dataset

in powershell
python src/python/scripts/validate_data.py


A successful run should report
Validation passed for 1800 windows
Devices: 6
Sessions: 18
Independent source trials: 1800

## 5. Run all tests

in powershell
python -m unittest discover -s tests -v


## After testing

Add your real commands and results to your research log

Don't commit
.venv/
data/generated/
__pycache__/
tmp/

To myself and anyone who want's to commit something, check what Git sees before committing
in powershell
git status --short

## Next step

After the generator and validator work
1. Agree on the final window format with Will
2. Train logistic regression
3. Train random forest
4. Build the SNN
5. Build the abnormality detector