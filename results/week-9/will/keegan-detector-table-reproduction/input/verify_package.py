"""Read-only byte verification for this supplied handoff."""
from pathlib import Path
import hashlib
import json

root=Path(__file__).resolve().parent
manifest=json.loads((root/"package-manifest.json").read_text(encoding="utf-8"))
bad=[]
for name,entry in manifest["files"].items():
    path=(root/name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        bad.append(name)
        continue
    data=path.read_bytes()
    if len(data)!=entry["bytes"] or hashlib.sha256(data).hexdigest()!=entry["sha256"]:
        bad.append(name)
print(json.dumps(dict(status="PASS" if not bad else "FAIL",files_checked=len(manifest["files"]),mismatches=bad,scope="Package byte integrity; not authentication or operator verification"),indent=2))
raise SystemExit(1 if bad else 0)
