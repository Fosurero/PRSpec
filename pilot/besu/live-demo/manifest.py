#!/usr/bin/env python3
"""Write manifest.json for an evidence folder; refuse to publish a leaked secret.

Every file is hashed and scanned for the raw values of the secrets present in
the environment. Files containing one are deleted and the exit status is 1, so
the publish step (gated on success) never pushes them.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

SECRET_ENV = ("GEMINI_API_KEY", "MODEL_API_KEY", "GH_TOKEN", "GITHUB_TOKEN")
CONTEXT_ENV = ("GITHUB_RUN_ID", "GITHUB_SHA", "PRSPEC_REPO", "PRSPEC_COMMIT", "EIPS_COMMIT",
               "BEFORE_SHA", "AFTER_SHA", "PRSPEC_MODELS", "PILOT_RUN_ID")


def main(root: str) -> int:
    base = Path(root)
    secrets = [os.environ[n].encode() for n in SECRET_ENV if len(os.environ.get(n, "")) >= 8]
    files, leaks = {}, []
    for path in sorted(p for p in base.rglob("*") if p.is_file() and p.name != "manifest.json"):
        data = path.read_bytes()
        rel = str(path.relative_to(base))
        files[rel] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        if any(s in data for s in secrets):
            leaks.append(rel)
    manifest = {k.lower(): os.environ[k] for k in CONTEXT_ENV if os.environ.get(k)}
    manifest["secret_scan"] = {"secret_values_checked": len(secrets),
                               "files_scanned": len(files), "files_with_secret": len(leaks)}
    manifest["files"] = files
    (base / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if leaks:
        for rel in leaks:
            (base / rel).unlink()
        print(f"secret value found in {len(leaks)} file(s); removed, refusing to publish",
              file=sys.stderr)
        return 1
    print(f"manifest: {len(files)} files; secret scan clean ({len(secrets)} values checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
