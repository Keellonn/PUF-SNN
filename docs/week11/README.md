# Week 11 technical review

November 10, 2026. This checkpoint closes the repository reporting work that can
be checked on the laptop. It adds one small stop safeguard and four native tests.
It does not claim a completed Quest Link acquisition run or study authorization.

- [Controller issue and staff-operated workflow](week11-quest-link-troubleshooting.md)
- [Accepted source replay and partial-file handling](week11-source-replay-and-disposition.md)
- [Test counts, finalized reproduction and historical timing labels](week11-evidence-and-timing.md)
- [Results and read-only checks](../../results/week-11/keegan/technical-review-20261110-001/README.md)

| Open item | Owner | Evidence needed to close it |
|---|---|---|
| Headset system-menu selection | Keegan with lab support | Controller selection or an authorized operator route into Link works |
| Staff-operated Link acquisition | Keegan | Actual prompts, tracking, mouse/Escape stop, interruptions and file accounting checked without human research motion |
| SharePoint | Keegan with PI/IT | Actual site, PI ownership, allowed/denied access, artificial transfer hashes and version/deletion/backup checks |
| Consent and safety preparation | Keegan, Will and PI | Training verification, protocol instruction, rehearsal and authorization |
| Source retention and interrupted motion files | PI with study team | Matching approved protocol/data plan and a verified restricted disposition workflow |

## Repeat the software checks

From the repository root in the existing documented Python environment:

```powershell
$env:PYTHONPATH = "$PWD\src\python;$PWD\tests"
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test*.py"
.\.venv\Scripts\python.exe -B -m pip check
.\.venv\Scripts\python.exe -B src/python/scripts/validate_accepted_source_visit.py results/week-10/keegan/source-integration-20261103-001/fixture/ledger.jsonl
```

For the native checks, save and close the Unity Editor first. Use a fresh local
output directory outside public Git. With Unity 6000.6.1f1 installed:

```powershell
$taskCheckRoot = Join-Path $env:TEMP ('puf-snn-week11-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $taskCheckRoot | Out-Null
& 'C:\Program Files\Unity\Hub\Editor\6000.6.1f1\Editor\Unity.exe' -batchmode -nographics -projectPath "$PWD\src\quest-logger\QuestLogger" -runTests -testPlatform EditMode -testResults "$taskCheckRoot\unity-results.xml" -logFile "$taskCheckRoot\unity.private.log" -pufStaffControlsFixtureRoot "$taskCheckRoot\staff" -pufAcceptedSourceFixtureRoot "$taskCheckRoot\source" -pufAcceptedSourceVisitFixtureRoot "$taskCheckRoot\visit"
```

Inspect the XML's actual pass/failure counts. A launched process is not a pass.
The staff fixtures contain runtime visit codes and stay local. Public summaries
use dates only; do not remove timestamps from historical evidence.

Will owns the correlation specification and calibration provenance. Their
scientific conclusions are not changed or rerun here. Institutional Word drafts
and training certificates stay outside public Git. No commit or push is part of
this checkpoint's verification commands.
