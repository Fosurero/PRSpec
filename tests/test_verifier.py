"""Tests for the finding verification engine and spec grounding."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer import AnalysisResult
from src.verifier import (
    SpecGrounding,
    VerificationEngine,
    confirmed_issues,
)


def _issue(description="A real deviation from the spec",
           spec_reference="base fee must be burned"):
    return {
        "type": "DEVIATION",
        "severity": "HIGH",
        "description": description,
        "spec_reference": spec_reference,
        "code_location": "func calcBaseFee",
        "potential_impact": "consensus split",
        "suggestion": "burn the fee",
    }


class KeywordAnalyzer:
    """Stand-in analyzer whose vote depends on the finding text, not call order.

    ``_build_refutation_prompt`` hands the finding's description straight to
    ``analyze_compliance``; a description containing 'real' is confirmed
    (PARTIAL_MATCH), anything else is refuted (FULL_MATCH).  Because the vote is
    a pure function of the finding, results stay deterministic even when the
    engine fans verification out across threads.
    """

    def _build_refutation_prompt(self, finding, spec_text, context):
        return finding.get("description", "")

    def analyze_compliance(self, spec_text, code_text, context):
        if "real" in spec_text.lower():
            return AnalysisResult("PARTIAL_MATCH", 80, [{"d": 1}], "confirmed")
        return AnalysisResult("FULL_MATCH", 80, [], "no issue")


class BrokenAnalyzer:
    def _build_refutation_prompt(self, finding, spec_text, context):
        return "x"

    def analyze_compliance(self, *args, **kwargs):
        raise RuntimeError("no api key")


class TestSpecGrounding(unittest.TestCase):
    SPEC = ("The base fee per gas must be burned and not transferred "
            "to any address. The gas target is the gas limit divided by 2.")

    def test_exact_substring_is_fully_grounded(self):
        g = SpecGrounding()
        res = g.check({"spec_reference": "base fee per gas must be burned"}, self.SPEC)
        self.assertTrue(res.grounded)
        self.assertEqual(res.score, 1.0)

    def test_word_containment_grounds_reordered_quote(self):
        g = SpecGrounding()
        res = g.check({"spec_reference": "base fee gas burned"}, self.SPEC)
        self.assertTrue(res.grounded)

    def test_hallucinated_reference_is_not_grounded(self):
        g = SpecGrounding()
        res = g.check(
            {"spec_reference": "validators receive quantum rewards xyzzy"},
            self.SPEC,
        )
        self.assertFalse(res.grounded)

    def test_partial_overlap_below_threshold(self):
        g = SpecGrounding()
        res = g.check({"spec_reference": "base fee unicorn rainbow sparkle"}, self.SPEC)
        self.assertFalse(res.grounded)

    def test_empty_reference_or_spec(self):
        g = SpecGrounding()
        self.assertFalse(g.check({"spec_reference": ""}, self.SPEC).grounded)
        self.assertFalse(g.check({"spec_reference": "anything"}, "").grounded)


class TestVerifyFinding(unittest.TestCase):
    def setUp(self):
        self.engine = VerificationEngine(KeywordAnalyzer(), rounds=2)

    def test_confirmed_when_voted_real_and_grounded(self):
        v = self.engine.verify_finding(
            _issue(description="real deviation", spec_reference="base fee must be burned"),
            "the base fee must be burned, never transferred", "code", {},
        )
        self.assertEqual(v.verdict, "CONFIRMED")
        self.assertTrue(v.grounded)
        self.assertEqual(v.verification_score, 100)

    def test_ungrounded_finding_cannot_be_confirmed(self):
        # Skeptics vote 'real', but the quote is nowhere in the spec.
        v = self.engine.verify_finding(
            _issue(description="real deviation", spec_reference="base fee must be burned"),
            "completely unrelated text about something else entirely", "code", {},
        )
        self.assertFalse(v.grounded)
        self.assertEqual(v.verdict, "DISPUTED")

    def test_refuted_when_skeptics_reject(self):
        v = self.engine.verify_finding(
            _issue(description="probably nothing", spec_reference="base fee must be burned"),
            "the base fee must be burned", "code", {},
        )
        self.assertEqual(v.verdict, "REFUTED")
        self.assertEqual(v.verification_score, 0)

    def test_analyzer_errors_become_disputed(self):
        engine = VerificationEngine(BrokenAnalyzer(), rounds=2)
        v = engine.verify_finding(_issue(), "spec", "code", {})
        self.assertEqual(v.verdict, "DISPUTED")
        self.assertEqual(v.votes["unsure"], 2)

    def test_rounds_must_be_positive(self):
        with self.assertRaises(ValueError):
            VerificationEngine(KeywordAnalyzer(), rounds=0)


class TestVerifyResults(unittest.TestCase):
    def test_annotates_every_issue_and_rolls_up(self):
        engine = VerificationEngine(KeywordAnalyzer(), rounds=2)
        results = [{
            "file_name": "BaseFeeCalculator.cs",
            "issues": [
                _issue(description="real burn deviation"),
                _issue(description="benign formatting nit"),
            ],
        }]
        spec = "base fee must be burned"
        engine.verify_results(results, spec, {"BaseFeeCalculator.cs": "code"}, {})

        issues = results[0]["issues"]
        self.assertTrue(all("verification" in i for i in issues))
        verdicts = {i["description"]: i["verification"]["verdict"] for i in issues}
        self.assertEqual(verdicts["real burn deviation"], "CONFIRMED")
        self.assertEqual(verdicts["benign formatting nit"], "REFUTED")

        rollup = results[0]["verification"]
        self.assertEqual(rollup["total"], 2)
        self.assertEqual(rollup["confirmed"], 1)
        self.assertEqual(rollup["refuted"], 1)

    def test_result_with_no_issues_gets_empty_rollup(self):
        engine = VerificationEngine(KeywordAnalyzer(), rounds=1)
        results = [{"file_name": "clean.go", "issues": []}]
        engine.verify_results(results, "spec", {"clean.go": "code"}, {})
        self.assertEqual(results[0]["verification"]["total"], 0)


class TestConfirmedIssues(unittest.TestCase):
    def test_unverified_result_returns_all(self):
        result = {"issues": [_issue(), _issue()]}
        self.assertEqual(len(confirmed_issues(result)), 2)

    def test_verified_result_returns_only_confirmed(self):
        result = {"issues": [
            {**_issue(), "verification": {"verdict": "CONFIRMED"}},
            {**_issue(), "verification": {"verdict": "REFUTED"}},
            {**_issue(), "verification": {"verdict": "DISPUTED"}},
        ]}
        self.assertEqual(len(confirmed_issues(result)), 1)


if __name__ == "__main__":
    unittest.main()
