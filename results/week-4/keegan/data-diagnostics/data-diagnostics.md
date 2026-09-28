# Corrected-data diagnostics

| Original issue | Cause | Correction | Regression evidence |
|---|---|---|---|
| Repeated active-class orientations across splits | Fixed amplitude/rate/phase templates with position noise masking repetition | Trial-level motion variation, noise/drift/sway and group effects | Full-window split tests, physical nearest-neighbor distributions, existing quaternion/variation tests |

Original audit and original perfect-score results remain historical evidence, not the corrected baseline.

Distances use relative poses, position RMS in meters and sign-invariant quaternion geodesic RMS in degrees. The same physical units and procedure apply before and after correction. Combined distance uses the recorded fixed thresholds, not a scaler fitted separately to each dataset.

Full-window equality includes all samples, relative timing and tracking quality; labels and identifiers cannot hide a copy.

Corrected full-window duplicate check passed: True
Balanced class counts in every device/session: True

See data-diagnostics.json for all split-pair counts and distance summaries and the nearest-neighbor files for every observation. Small distances are reported rather than automatically declared leakage. The still distribution can naturally overlap.

Scope: fixed synthetic device profiles, cross-session only; no physical Quest or human calibration.
