"""Live-demo helpers: secret redaction on the recorded screen and the evidence scan."""
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "pilot" / "besu" / "live-demo"
SECRET = "AIzaFAKE-demo-secret-0123456789abcdef"


def _scrub(tmp_path, code):
    transcript = tmp_path / "transcript.txt"
    proc = subprocess.run(
        [sys.executable, str(DEMO / "scrubtty.py"), str(transcript), "--",
         sys.executable, "-c", code],
        env=dict(os.environ, GEMINI_API_KEY=SECRET), capture_output=True, timeout=60)
    return proc, transcript.read_bytes()


def test_scrubtty_redacts_secret_even_when_split_across_writes(tmp_path):
    proc, log = _scrub(tmp_path, (
        "import os, sys, time; k = os.environ['GEMINI_API_KEY']; print('key=' + k);"
        "sys.stdout.write(k[:7]); sys.stdout.flush(); time.sleep(0.4);"
        "print(k[7:]); print('done')"))
    assert proc.returncode == 0
    for blob in (proc.stdout, log):
        assert SECRET.encode() not in blob and SECRET[:7].encode() not in blob
        assert blob.count(b"[REDACTED]") == 2 and b"done" in blob


def test_scrubtty_propagates_exit_code(tmp_path):
    proc, log = _scrub(tmp_path, "import sys; print('x'); sys.exit(3)")
    assert proc.returncode == 3 and b"x" in log


def test_manifest_refuses_to_publish_a_leaked_secret(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "ok.txt").write_text("fine")
    (evidence / "leak.txt").write_text("token " + SECRET)
    proc = subprocess.run([sys.executable, str(DEMO / "manifest.py"), str(evidence)],
                          env=dict(os.environ, GEMINI_API_KEY=SECRET),
                          capture_output=True, text=True)
    assert proc.returncode == 1 and not (evidence / "leak.txt").exists()
    text = (evidence / "manifest.json").read_text()
    assert SECRET not in text and json.loads(text)["secret_scan"]["files_with_secret"] == 1


def test_recorder_is_fork_only_and_publishes_only_after_a_clean_scan():
    job = yaml.safe_load((DEMO / "record-live-demo.yml").read_text())["jobs"]["record"]
    assert "besu-eth/besu" in job["if"]
    publish = next(s for s in job["steps"] if s.get("name", "").startswith("Publish"))
    assert "steps.scan.outputs.clean == 'true'" in publish["if"]
    for step in job["steps"]:
        if "secrets." in yaml.safe_dump(step):
            assert step["name"].startswith(("Record", "Gather"))
