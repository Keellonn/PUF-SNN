# Simulated PUF and Authentication Design

**Owner:** Will Wallace  
**Version:** 0.2  
**Last updated:** September 11, 2026

# How to run as of Week 2

## Prerequisites
Windows 10/11
Python 3.10+
Git
Python packages listed in requirements.txt

## First Time Setup
1. Clone the repository

2. Setup a Python virtual environment,
python -m venv .venv
*If this puts the location of Activate.ps1 into "bin" and not "scripts" follow the error workflow.
3. Activate the environment,
.\.venv\Scripts\Activate.ps1
*If PowerShell blocks 'Activate.ps1' with an execution error, allow scripts for the current terminal session using,
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

4. Install packages from requirements.txt
python -m pip install -r requirements.txt

Error at 2,
py -0p
For the version you see use that after resetting your bad virtual environment,
py -3.12 -m venv .venv
This will fix your environment using the windows python launcher. Good to proceed to step 3.

## Running the Simulator
After the first time setup is complete, you have to configure your sim.
The simulator uses the .json file,
config/baseline.json

Within this file you can change the
- Number of devices
- Number of ring oscillators
- The oscillator pairing scheme
- Manufacturing variation
- Measurement noise
- Number of repeated readings
- Random seed
- Noise sweep values

After configuring the sim, run the experiment with
.\run_simulation.ps1
*If PowerShell blocks 'run_simulation.ps1' with an execution error, allow scripts for the current terminal session using,
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

## Results
Sucessful runs save,
- BER and reliability measurements
- Per-device reference responses and uniformity
- Inter-device uniqueness measurements
- Noise-sweep results
- Experiment summaries
- Configuration metadata
- Generated plots

# Project Overview
This simulation implements a configurable simulation of a ring_oscillator PUF. Currently the simulation generates device-specfic noisy response bits and then evaulating their behavior. Soon authentication and key-reconstruction layers will be added. 

## Scope
The current simulator only has the PUF behavior layer only. It is able to model manufacturing variation, configurable read conditions, repeated noisy measurements, enrollment references, and BER, reliability, uniqueness, and uniformity metrics.

## Structure of Repository
config/    Simulation configuration files 
experiments/    Simulation runner and output creation
src/    PUF model with metric implementation
tests/    Unit and simulation tests
results/    Generated simulation results

## Results
With each successful simulation, a new directory is created within "results/"
Generated simulation results create,
- BER and reliability measurements
- Per-device reference responses and uniformity
- Inter-device uniqueness measurements
- Noise-sweep results
- Experiment summaries
- Configuration metadata
- Generated plots

## Reproducibility
The simulator uses fixed random seeds and seperate random streams for manufacturing, enrollment, and measurement noise. If you were to run the exact same seed and configuration, you should get the same results.