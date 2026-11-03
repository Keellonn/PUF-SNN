# Repository tools

These tools keep their existing filenames and locations. Check the linked scope
before running one; their output locations and input requirements differ.

| Tool | Purpose | Instructions |
|---|---|---|
| [reproduce_saved_detector_table.py](reproduce_saved_detector_table.py) | Replay the compact detector table from saved scores and fixed thresholds | [Bounded reproduction](../docs/week9-bounded-reproduction.md) |
| [run_keegan_week8_checks.py](run_keegan_week8_checks.py) | Save a scoped Python test receipt under the existing Week 8 output boundary | [Week 8 validation](../docs/week8-keegan-validation.md) |
| [profile_three_arm_resources_v1.py](profile_three_arm_resources_v1.py) | Opt-in bounded experiment-workflow resource profiling | [Retained profiler report](../docs/archive/week8-three-arm-resource-profiler-v1.md) |

The logger's read-only validators live in `src/python/scripts/`; see the
[trial-ledger guide](../docs/quest-trial-ledger.md) and
[current source candidate](../docs/week10/week10-source-recording-plan.md).
