#!/usr/bin/env python3
"""Print the two live PRSpec results side by side (reads the JSON reports only)."""
import json
import sys
from pathlib import Path

for side in sys.argv[1:]:
    report = next(Path(side).glob("output/prspec_eip*_besu*.json"), None)
    if report is None:
        print(f"{Path(side).name:>6}: no complete report")
        continue
    data = json.loads(report.read_text())
    for r in data.get("results", []):
        issues = r.get("issues", [])
        print(f"{Path(side).name:>6}  besu@{str(r.get('client_ref', ''))[:12]}  "
              f"{data.get('metadata', {}).get('analyzer', '?')}  "
              f"status={r.get('status')}  issues={len(issues)}")
        for i in issues:
            print(f"        [{i.get('severity', '?')}] {str(i.get('code_location', ''))[:110]}")
            print(f"          {str(i.get('description', ''))[:230]}")
