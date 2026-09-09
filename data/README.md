# Data

This folder explains what project data can and can't be stored in GitHub.

## Files that may be committed

We may commit
- Small synthetic examples
- Data schemas
- Generator and validator code
- Data dictionaries
- Aggregate results
- Results that can't identify a participant

## Files that we won't be committed

Don't commit
- Raw participant motion data
- Processed participant motion data
- Names or direct identifiers
- Files that connect participant IDs to real identities
- Headset serial numbers
- Meta account information
- PUF responses
- Reconstructed PUF secrets
- Session keys
- Authentication secrets
- Large generated datasets
- Model checkpoints
- Temporary data exports

## Generated data

The synthetic generator creates
`data/generated/synthetic-windows.jsonl`

The folder is ignored by Git because the dataset can be recreated from the committed code and configuration

The current default dataset contains
- 1,800 windows
- 120 samples per window
- 216,000 total samples
- 6 simulated devices
- 18 sessions
- 5 motion classes
- 360 windows per class
- 600 training windows
- 600 validation windows
- 600 testing windows

Each JSONL line contains one complete 2 second motion window that follows
`schemas/quest-window.schema.json`

## Future participant data

If human motion data is approved later, it won't belong in this repository

Before saving any participant data, we need faculty-approved rules covering
- Storage location
- Who may access it
- Participant identifiers
- Retention period
- Backups
- De-identification
- Deletion

Approved participant data should be stored in a restricted location, not in the public GitHub repository.