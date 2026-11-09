"""Pre-registered scoring rules and the mutation definitions themselves."""

import importlib.util
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.code_fetcher import CodeFetcher  # noqa: E402

spec = importlib.util.spec_from_file_location("sb", ROOT / "scripts/mutation_scoreboard.py")
sb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sb)

KW = ["SLACK_COEFFICIENT", "elasticity"]


def res(issues, status="PARTIAL_MATCH"):
    return {"status": status, "issues": issues}


class TestClassify(unittest.TestCase):
    hit = {"description": "Elasticity multiplier is 3, spec says 2"}
    other = {"description": "unrelated logging"}

    def test_missed(self):
        self.assertEqual(sb.classify(res([self.other]), res([]), KW, False)["outcome"], "missed")

    def test_flagged_without_verify(self):
        self.assertEqual(sb.classify(res([self.hit]), res([]), KW, False)["outcome"], "flagged")

    def test_confirmed_requires_confirmed_verdict(self):
        unverified = dict(self.hit, verification={"verdict": "DISPUTED"})
        confirmed = dict(self.hit, verification={"verdict": "CONFIRMED"})
        self.assertEqual(sb.classify(res([unverified]), res([]), KW, True)["outcome"], "flagged")
        self.assertEqual(sb.classify(res([confirmed]), res([]), KW, True)["outcome"], "confirmed")

    def test_baseline_noise_is_inconclusive_not_detected(self):
        out = sb.classify(res([self.hit]), res([self.hit]), KW, False)
        self.assertEqual(out["outcome"], "inconclusive")

    def test_error_is_never_scored(self):
        self.assertEqual(sb.classify(res([], "ERROR"), res([]), KW, False)["outcome"], "error")
        self.assertEqual(sb.classify(res([self.hit]), res([], "ERROR"), KW, False)["outcome"], "error")


class TestMutationDefinitions(unittest.TestCase):
    def setUp(self):
        self.exp = yaml.safe_load((ROOT / "pilot/besu/mutations.yaml").read_text())

    def test_ten_unique_mutations(self):
        ids = [m["id"] for m in self.exp["mutations"]]
        self.assertEqual(len(ids), 10)
        self.assertEqual(len(set(ids)), 10)

    def test_commit_is_full_sha(self):
        self.assertRegex(self.exp["besu"]["commit"], r"^[0-9a-f]{40}$")

    def test_every_mutation_targets_a_registered_file(self):
        reg = CodeFetcher.CLIENTS["besu"]["eip_files"]
        for m in self.exp["mutations"]:
            self.assertIn(m["file"], reg[m["eip"]], m["id"])
            self.assertNotEqual(m["find"], m["replace"], m["id"])
            self.assertTrue(m["keywords"], m["id"])


if __name__ == "__main__":
    unittest.main()
