"""Tests for the cross-client differential engine."""

import sys
import unittest
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.differential import (
    ClientAnalysis,
    DifferentialEngine,
    DifferentialResult,
    summarize_results,
)


def _file_result(file_name, status="FULL_MATCH", confidence=90, issues=None):
    """Build a per-file analysis dict like the analyzer pipeline emits."""
    return {
        "file_name": file_name,
        "status": status,
        "confidence": confidence,
        "issues": issues or [],
        "summary": f"Analysis of {file_name}.",
    }


def _issue(itype="DEVIATION", severity="HIGH", description="An issue."):
    return {
        "type": itype,
        "severity": severity,
        "description": description,
        "spec_reference": "spec text",
        "code_location": "func foo",
        "potential_impact": "impact",
        "suggestion": "fix it",
    }


class TestSummarizeResults(unittest.TestCase):
    def test_compliant_when_all_full_match(self):
        results = [_file_result("a.go"), _file_result("b.go")]
        s = summarize_results(results)
        self.assertEqual(s["overall_status"], "COMPLIANT")
        self.assertEqual(s["total_issues"], 0)

    def test_issues_found_with_high_severity(self):
        results = [_file_result("a.go", status="PARTIAL_MATCH",
                                issues=[_issue(severity="HIGH")])]
        s = summarize_results(results)
        self.assertEqual(s["overall_status"], "ISSUES FOUND")
        self.assertEqual(s["high_severity"], 1)

    def test_issue_type_counts(self):
        results = [_file_result("a.go", issues=[
            _issue(itype="DEVIATION"), _issue(itype="EDGE_CASE", severity="LOW"),
        ])]
        s = summarize_results(results)
        self.assertEqual(s["issue_types"]["DEVIATION"], 1)
        self.assertEqual(s["issue_types"]["EDGE_CASE"], 1)

    def test_average_confidence(self):
        results = [_file_result("a.go", confidence=80),
                   _file_result("b.go", confidence=100)]
        self.assertEqual(summarize_results(results)["average_confidence"], 90)


class TestClientAnalysis(unittest.TestCase):
    def test_all_issue_text_is_lowercased_and_joined(self):
        ca = ClientAnalysis("geth", "go", [
            _file_result("a.go", issues=[_issue(description="BaseFee Burn")]),
        ])
        text = ca.all_issue_text()
        self.assertIn("basefee burn", text)
        self.assertEqual(text, text.lower())


class TestDifferentialEngine(unittest.TestCase):
    def _two_clients(self):
        geth = ClientAnalysis("go-ethereum", "go", [
            _file_result("eip1559.go", status="FULL_MATCH"),
        ])
        neth = ClientAnalysis("nethermind", "csharp", [
            _file_result("BaseFeeCalculator.cs", status="PARTIAL_MATCH",
                         issues=[_issue(itype="DEVIATION", severity="HIGH",
                                        description="FeeCollector deviates")]),
        ])
        return {"go-ethereum": geth, "nethermind": neth}

    def test_requires_two_clients(self):
        engine = DifferentialEngine()
        with self.assertRaises(ValueError):
            engine.build({"geth": ClientAnalysis("geth", "go", [])}, 1559)

    def test_build_returns_differential_result(self):
        engine = DifferentialEngine()
        diff = engine.build(self._two_clients(), 1559, "EIP-1559")
        self.assertIsInstance(diff, DifferentialResult)
        self.assertEqual(diff.eip, 1559)
        self.assertEqual(set(diff.clients), {"go-ethereum", "nethermind"})

    def test_status_row_diverges(self):
        engine = DifferentialEngine()
        diff = engine.build(self._two_clients(), 1559)
        status_rows = [r for r in diff.rows if r.category == "status"]
        self.assertEqual(len(status_rows), 1)
        self.assertEqual(status_rows[0].verdict, "DIVERGE")

    def test_status_row_agrees_when_identical(self):
        engine = DifferentialEngine()
        per_client = {
            "a": ClientAnalysis("a", "go", [_file_result("x", status="FULL_MATCH")]),
            "b": ClientAnalysis("b", "java", [_file_result("y", status="FULL_MATCH")]),
        }
        diff = engine.build(per_client, 1559)
        status_rows = [r for r in diff.rows if r.category == "status"]
        self.assertEqual(status_rows[0].verdict, "AGREE")

    def test_issue_type_row_present_when_reported(self):
        engine = DifferentialEngine()
        diff = engine.build(self._two_clients(), 1559)
        type_rows = [r for r in diff.rows if r.category == "issue_type"]
        self.assertTrue(any("Deviation" in r.dimension for r in type_rows))

    def test_focus_area_rows_match_keywords(self):
        # nethermind text mentions "fee" + "collector"; focus area "fee_cap_check"
        # needs both "fee" and "cap" -> only matches if both present.
        geth = ClientAnalysis("geth", "go", [_file_result("a.go")])
        neth = ClientAnalysis("neth", "csharp", [
            _file_result("b.cs", status="PARTIAL_MATCH", issues=[
                _issue(description="base fee cap exceeded for gas limit"),
            ]),
        ])
        engine = DifferentialEngine(focus_areas=["fee_cap_check", "gas_limit_validation"])
        diff = engine.build({"geth": geth, "neth": neth}, 1559)
        focus_rows = {r.dimension: r for r in diff.rows if r.category == "focus_area"}
        self.assertIn("Fee Cap Check", focus_rows)
        # neth flagged, geth clean -> diverge
        self.assertEqual(focus_rows["Fee Cap Check"].verdict, "DIVERGE")
        self.assertEqual(focus_rows["Fee Cap Check"].per_client["neth"], "flagged")
        self.assertEqual(focus_rows["Fee Cap Check"].per_client["geth"], "clean")

    def test_divergences_recorded(self):
        engine = DifferentialEngine()
        diff = engine.build(self._two_clients(), 1559)
        self.assertTrue(diff.divergences)
        self.assertGreater(diff.divergence_count, 0)

    def test_to_dict_shape(self):
        engine = DifferentialEngine(focus_areas=["base_fee_calculation"])
        diff = engine.build(self._two_clients(), 1559, "EIP-1559")
        d = diff.to_dict()
        for key in ("eip", "eip_title", "clients", "client_summaries",
                    "comparison", "divergences", "agreements", "narrative", "stats"):
            self.assertIn(key, d)
        self.assertIsInstance(d["comparison"], list)

    def test_narrative_mentions_clients(self):
        engine = DifferentialEngine()
        diff = engine.build(self._two_clients(), 1559, "EIP-1559")
        self.assertIn("go-ethereum", diff.narrative)
        self.assertIn("nethermind", diff.narrative)

    def test_three_client_comparison(self):
        per_client = {
            "go-ethereum": ClientAnalysis("go-ethereum", "go", [
                _file_result("a.go", status="FULL_MATCH")]),
            "nethermind": ClientAnalysis("nethermind", "csharp", [
                _file_result("b.cs", status="PARTIAL_MATCH",
                             issues=[_issue(itype="DEVIATION")])]),
            "besu": ClientAnalysis("besu", "java", [
                _file_result("c.java", status="FULL_MATCH")]),
        }
        engine = DifferentialEngine()
        diff = engine.build(per_client, 1559)
        self.assertEqual(len(diff.clients), 3)
        status_row = [r for r in diff.rows if r.category == "status"][0]
        self.assertEqual(len(status_row.per_client), 3)
        self.assertEqual(status_row.verdict, "DIVERGE")


class TestSynthesizeFallback(unittest.TestCase):
    def test_synthesize_returns_none_on_failure(self):
        class BrokenAnalyzer:
            def analyze_compliance(self, *a, **k):
                raise RuntimeError("no api key")

        engine = DifferentialEngine()
        per_client = {
            "a": ClientAnalysis("a", "go", [_file_result("x")]),
            "b": ClientAnalysis("b", "java", [_file_result("y")]),
        }
        diff = engine.build(per_client, 1559)
        self.assertIsNone(engine.synthesize(BrokenAnalyzer(), diff, per_client))

    def test_synthesize_uses_analyzer_summary(self):
        class FakeResult:
            summary = "geth and besu agree; nethermind diverges on fee burn."

        class FakeAnalyzer:
            def analyze_compliance(self, spec, code, ctx):
                return FakeResult()

        engine = DifferentialEngine()
        per_client = {
            "a": ClientAnalysis("a", "go", [_file_result("x")]),
            "b": ClientAnalysis("b", "java", [_file_result("y")]),
        }
        diff = engine.build(per_client, 1559)
        out = engine.synthesize(FakeAnalyzer(), diff, per_client)
        self.assertIn("nethermind diverges", out)


if __name__ == "__main__":
    unittest.main()
