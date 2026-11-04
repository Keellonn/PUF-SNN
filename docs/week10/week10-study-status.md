# Study decisions and remaining work

Updated November 3, 2026 from the PI's latest written feedback and Keegan's
acquisition choice. This is a planning/status record, not institutional approval.

## Confirmed planning decisions

- Use VT SharePoint. Dr. Christiana Chamon Garcia retains custody of study records
  and must have access. Warren can help verify the IT arrangements.
- List Christiana Chamon Garcia as faculty PI for submission, oversight, readiness,
  safety review and data/access approval.
- List Keegan Hoyne for the logger, acquisition workflow, models and assigned
  collection/analysis. List William Wallace for authentication/reconstruction,
  validation and assigned collection/analysis.
- Propose Keegan and Will to obtain consent after verified required training,
  protocol instruction, a consent rehearsal and the PI's authorization. An assigned
  role does not automatically grant access to all records or duties.
- Up to 12 adults: up to three Phase 1 participants and up to nine **different**
  Phase 2 participants. One visit per person, at most 45 minutes.
- At most 25 recorded Phase 1 trials or 75 Phase 2 trials; no replacement/repeated
  recorded trials. Keep development and primary-evaluation groups separate.
- Exclude directly graded/supervised individuals, current PI lab members and the
  student research team from this initial pilot.
- Gentle seated tasks, stationary display, breaks and stop rules; no same-day
  restart following a symptom-related stop. Remove the headset by minute 35 and
  limit wear to 25 minutes. Reduce trial counts when preparation/breaks take longer.
- Written PI readiness confirmation before Phase 2. A 14-day motion-withdrawal
  window is conditional on verified storage and records procedures.
- Plan acquisition through laptop-hosted Quest Link, saving app files on the
  laptop. Actual tracking/control/file behavior remains to be validated.

## Current open items

| Item | Next step |
|---|---|
| Source-data reproducibility | Review the accepted-source proposal and [optional development integration](week10-source-integration.md); saved scenes keep it off |
| Live integration | Versioned development policy, controller wiring and read-only ledger/source reconciliation implemented and tested synthetically; actual Link/storage checks and PI source-retention review remain |
| SharePoint details | Verify actual site/folders, staff permissions, authentication/encryption, backups, temporary copies and deletion/withdrawal handling with PI/IT |
| CITI and staff preparation | Keegan has not completed the required HSR course; obtain Will's current record, then PI verification, instruction, rehearsal and authorization |
| Headset input/Link | Controller pointing/highlighting observed, but selection failed in system menus; restarts did not resolve it. USB test reported USB 2, 369 Mbps. No successful headset logger run claimed |
| Administrative decisions | Finalize funding, injury wording, retention requirements, recruitment channel, room availability and actual equipment/storage arrangements |
| Coordinated packet | Version 1.4 working copies now align protocol, consent, data flow, forms and PI checklist; review accepted-source retention and remaining blanks before submission. Word copies stay outside public Git |
| Institutional review | Obtain applicable written determination/approval before covered research activities; this planning decision authorizes no recruitment or research collection |

The proposed headset is Quest 3 and the proposed room is Torgersen 2015. Room
availability and the actual study configuration still need confirmation. The
ten-trial development scene is not the proposed 25/75-trial study configuration.

Will owns calibration/shared-noise specification, three-arm accounting and his
detector replay reviewer record. Keegan does not repeat those experiments here.
The returned local saved-score replay and its matching CSVs remain scoped evidence;
they do not regenerate model predictions or reproduce the complete pipeline.

No participant motion, certificates, consent forms, code keys or access secrets
belong in this public repository. The software checkpoint uses artificial poses.
