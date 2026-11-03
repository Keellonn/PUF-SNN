# Week 10 first half: accepted-source replay candidate

November 3, 2026. Synthetic development inputs only. This checkpoint prepares an
offline source-file proposal for the planned PC-hosted Quest Link workflow.
It does not enable source retention in a scene or the live trial controller.

| Check | Recorded result |
|---|---|
| Native Unity EditMode | 61/61 passed: 50 existing and 11 new cases |
| Native source reload | Processed-window JSON and source metrics matched for 20 synthetic seeds |
| Focused Python checks | 42 passed: 10 new candidate, 15 source-summary and 17 ledger tests |
| Independent Python inspection of native fixture | COMPLETE: original timing/metrics, window identity, 60 Hz grid and tracking brackets checked |
| File preservation | Read-only checker left inputs unchanged; existing-file export was refused |
| Refused outcomes | Rejected, stopped and processing-failed exports created no source file |
| Live recording | Candidate is not called by the controller; saved scene and existing user XR settings are preserved |

The native fixture has 181 artificial source samples and 120 processed samples.
Float32 bit patterns preserve the source's captured precision. The existing
processor is replayed; no quality thresholds, model weights or alert cutoffs changed.
The Python checker does not independently implement quaternion interpolation.

The 42 focused Python checks are a scoped run, not a new full-regression total
to add to the historical 1,117. The native assembly includes the earlier 50 core
EditMode tests; the separate ten bench tests were not rerun in this checkpoint.
The 20 seeds are software cases, not participants, visits or observations of
headset performance. Raw native XML/logs remain private; their XML hash is retained.

See [the source plan](../../../../docs/week10/week10-source-recording-plan.md),
[current study decisions](../../../../docs/week10/week10-study-status.md),
[verification receipt](verification.json) and [Python inspection](python-inspection.json).

## Recheck the saved artificial fixture

From the repository root:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_accepted_source.py
.\.venv\Scripts\python.exe -B src/python/scripts/validate_accepted_source_candidate.py results/week-10/keegan/source-replay-20261103-001/fixture/accepted-source.json results/week-10/keegan/source-replay-20261103-001/fixture/windows.jsonl results/week-10/keegan/source-replay-20261103-001/fixture/source-metrics.json
```

The second work group will connect a reviewed retention policy to live acquisition,
versioned ledger/source receipts and interruption handling, and align the protocol,
consent and data inventory. Real Link/device checks, actual SharePoint controls,
training and institutional authorization remain outstanding.
