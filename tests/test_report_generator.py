"""Tests for JSON / Markdown / HTML report generation."""

import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import __version__
from src.differential import ClientAnalysis, DifferentialEngine
from src.report_generator import ReportGenerator, ReportMetadata


def _issue(severity="HIGH", itype="DEVIATION", verification=None, **overrides):
    issue = {
        "type": itype,
        "severity": severity,
        "description": "Base fee is not burned.",
        "spec_reference": "the base fee MUST be burned",
        "code_location": "CalcBaseFee",
        "potential_impact": "consensus failure",
        "suggestion": "burn it",
    }
    if verification is not None:
        issue["verification"] = verification
    issue.update(overrides)
    return issue


def _result(file_name="eip1559.go", status="PARTIAL_MATCH", confidence=80, issues=None):
    return {
        "file_name": file_name,
        "status": status,
        "confidence": confidence,
        "issues": issues if issues is not None else [],
        "summary": f"Analysis of {file_name}.",
    }


def _metadata(eip=1559, client="go-ethereum"):
    return ReportMetadata(
        title=f"EIP-{eip} Compliance Report - {client}",
        eip_number=eip,
        client=client,
        timestamp=datetime(2024, 5, 1, 12, 30, 45),
        analyzer="Gemini (gemini-2.5-pro)",
    )


def _differential(llm_synthesis=None):
    per_client = {
        "go-ethereum": ClientAnalysis("go-ethereum", "go", [
            _result("eip1559.go", status="FULL_MATCH", issues=[]),
        ]),
        "nethermind": ClientAnalysis("nethermind", "csharp", [
            _result("BaseFeeCalculator.cs", status="PARTIAL_MATCH", issues=[_issue()]),
        ]),
    }
    differential = DifferentialEngine(
        focus_areas=["base_fee_calculation"]
    ).build(per_client, 1559, "EIP-1559: Fee market change")
    differential.llm_synthesis = llm_synthesis
    return differential


class ReportTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="prspec_report_")
        self.gen = ReportGenerator(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestSummary(ReportTestCase):
    def test_empty_results(self):
        s = self.gen._generate_summary([])
        self.assertEqual(s["files_analyzed"], 0)
        self.assertEqual(s["average_confidence"], 0)
        self.assertEqual(s["total_issues"], 0)

    def test_severity_counts(self):
        results = [_result(issues=[
            _issue(severity="HIGH"), _issue(severity="MEDIUM"),
            _issue(severity="LOW"), _issue(severity="INFO"),
        ])]
        s = self.gen._generate_summary(results)
        self.assertEqual((s["high_severity"], s["medium_severity"], s["low_severity"]),
                         (1, 1, 1))
        self.assertEqual(s["total_issues"], 4)

    def test_lowercase_severity_is_normalised(self):
        s = self.gen._generate_summary([_result(issues=[_issue(severity="high")])])
        self.assertEqual(s["high_severity"], 1)

    def test_status_compliant(self):
        results = [_result(status="FULL_MATCH"), _result("b.go", status="FULL_MATCH")]
        self.assertEqual(self.gen._generate_summary(results)["overall_status"], "COMPLIANT")

    def test_status_issues_found_for_missing(self):
        results = [_result(status="MISSING")]
        self.assertEqual(self.gen._generate_summary(results)["overall_status"], "ISSUES FOUND")

    def test_status_issues_found_for_high_severity(self):
        results = [_result(status="FULL_MATCH", issues=[_issue(severity="HIGH")])]
        self.assertEqual(self.gen._generate_summary(results)["overall_status"], "ISSUES FOUND")

    def test_status_partial(self):
        results = [_result(status="PARTIAL_MATCH")]
        self.assertEqual(self.gen._generate_summary(results)["overall_status"], "PARTIAL")

    def test_status_uncertain(self):
        results = [_result(status="UNCERTAIN")]
        self.assertEqual(self.gen._generate_summary(results)["overall_status"], "UNCERTAIN")

    def test_average_confidence_is_rounded(self):
        results = [_result(confidence=80), _result("b.go", confidence=85)]
        self.assertEqual(self.gen._generate_summary(results)["average_confidence"], 82)

    def test_verification_counts(self):
        results = [_result(issues=[
            _issue(verification={"verdict": "CONFIRMED"}),
            _issue(verification={"verdict": "DISPUTED"}),
            _issue(verification={"verdict": "REFUTED"}),
            _issue(verification={"verdict": "UNKNOWN_VERDICT"}),
        ])]
        v = self.gen._generate_summary(results)["verification"]
        self.assertTrue(v["verified"])
        self.assertEqual((v["confirmed"], v["disputed"], v["refuted"]), (1, 1, 1))

    def test_verification_absent_when_unverified(self):
        v = self.gen._generate_summary([_result(issues=[_issue()])])["verification"]
        self.assertFalse(v["verified"])


class TestNarrative(ReportTestCase):
    def test_singular_file_wording_and_no_issues(self):
        text = self.gen._build_narrative([_result(status="FULL_MATCH")], _metadata())
        self.assertIn("analysed 1 file from", text)
        self.assertIn("No compliance issues were detected.", text)

    def test_plural_files_and_severity_breakdown(self):
        results = [
            _result(issues=[_issue(severity="HIGH"), _issue(severity="MEDIUM")]),
            _result("b.go", issues=[_issue(severity="LOW")]),
        ]
        text = self.gen._build_narrative(results, _metadata())
        self.assertIn("analysed 2 files", text)
        self.assertIn("3 issues detected (1 high, 1 medium, 1 low)", text)

    def test_per_file_lines_included(self):
        text = self.gen._build_narrative([_result("eip1559.go")], _metadata())
        self.assertIn("eip1559.go — PARTIAL_MATCH (0 issues)", text)

    def test_mentions_client_and_eip(self):
        text = self.gen._build_narrative([_result()], _metadata(eip=4844, client="besu"))
        self.assertIn("besu", text)
        self.assertIn("EIP-4844", text)


class TestVerdictRendering(ReportTestCase):
    def test_text_empty_when_unverified(self):
        self.assertEqual(self.gen._verdict_text(_issue()), "")
        self.assertEqual(self.gen._verdict_text(_issue(verification={})), "")

    def test_text_grounded(self):
        text = self.gen._verdict_text(_issue(verification={
            "verdict": "CONFIRMED", "verification_score": 90, "grounded": True}))
        self.assertIn("CONFIRMED", text)
        self.assertIn("90/100", text)
        self.assertIn("grounded", text)

    def test_text_ungrounded(self):
        text = self.gen._verdict_text(_issue(verification={
            "verdict": "DISPUTED", "verification_score": 40, "grounded": False}))
        self.assertIn("ungrounded", text)

    def test_badge_empty_when_unverified(self):
        self.assertEqual(self.gen._verdict_badge_html(_issue()), "")

    def test_badge_uses_verdict_colour(self):
        badge = self.gen._verdict_badge_html(_issue(verification={
            "verdict": "CONFIRMED", "verification_score": 88, "grounded": True}))
        self.assertIn(ReportGenerator._VERDICT_COLORS["CONFIRMED"], badge)
        self.assertIn("88/100", badge)

    def test_badge_falls_back_for_unknown_verdict(self):
        badge = self.gen._verdict_badge_html(_issue(verification={"verdict": "WEIRD"}))
        self.assertIn("#888", badge)


class TestGenerateReport(ReportTestCase):
    def test_creates_output_directory(self):
        target = Path(self.tmpdir, "nested", "reports")
        ReportGenerator(str(target))
        self.assertTrue(target.is_dir())

    def test_unsupported_format_raises(self):
        with self.assertRaises(ValueError):
            self.gen.generate_report([_result()], _metadata(), "pdf")

    def test_json_report_contents(self):
        path = self.gen.generate_report([_result(issues=[_issue()])], _metadata(), "JSON")
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(data["metadata"]["eip_number"], 1559)
        self.assertEqual(data["metadata"]["version"], __version__)
        self.assertEqual(data["metadata"]["timestamp"], "2024-05-01T12:30:45")
        self.assertEqual(data["summary"]["total_issues"], 1)
        self.assertEqual(len(data["results"]), 1)

    def test_filename_encodes_eip_client_and_timestamp(self):
        path = Path(self.gen.generate_report([_result()], _metadata(), "json"))
        self.assertEqual(path.name,
                         "prspec_eip1559_go-ethereum_20240501_123045.json")

    def test_markdown_report_contents(self):
        results = [_result(issues=[_issue(verification={
            "verdict": "CONFIRMED", "verification_score": 95, "grounded": True})])]
        path = self.gen.generate_report(results, _metadata(), "markdown")
        md = Path(path).read_text(encoding="utf-8")
        self.assertTrue(path.endswith(".md"))
        self.assertIn("# EIP-1559 Compliance Report - go-ethereum", md)
        self.assertIn("### 1. eip1559.go", md)
        self.assertIn("**Verification**: CONFIRMED", md)
        self.assertIn("| Verified | 1 confirmed, 0 disputed, 0 refuted |", md)
        self.assertIn("`CalcBaseFee`", md)

    def test_markdown_md_alias(self):
        path = self.gen.generate_report([_result()], _metadata(), "md")
        self.assertTrue(path.endswith(".md"))

    def test_markdown_without_issues_or_verification(self):
        md = Path(self.gen.generate_report(
            [_result(status="FULL_MATCH")], _metadata(), "markdown")
        ).read_text(encoding="utf-8")
        self.assertIn("No issues found in this file.", md)
        self.assertNotIn("| Verified |", md)

    def test_html_report_contents(self):
        results = [_result(issues=[_issue(verification={
            "verdict": "CONFIRMED", "verification_score": 95, "grounded": True})])]
        path = self.gen.generate_report(results, _metadata(), "html")
        page = Path(path).read_text(encoding="utf-8")
        self.assertTrue(path.endswith(".html"))
        self.assertIn("<!DOCTYPE html>", page)
        self.assertIn("issue issue-high", page)
        self.assertIn("Confirmed", page)  # verified KPI card
        self.assertIn("#ffc107", page)  # PARTIAL_MATCH badge colour

    def test_html_escapes_user_content(self):
        results = [_result(issues=[_issue(description="<script>alert(1)</script>")])]
        page = Path(self.gen.generate_report(results, _metadata(), "html")
                    ).read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_html_unknown_status_uses_default_colour(self):
        page = Path(self.gen.generate_report(
            [_result(status="WEIRD")], _metadata(), "html")
        ).read_text(encoding="utf-8")
        self.assertIn("#6c757d", page)
        self.assertIn("No issues found.", page)


class TestDifferentialReports(ReportTestCase):
    def test_unsupported_format_raises(self):
        with self.assertRaises(ValueError):
            self.gen.generate_differential_report(_differential(), "pdf")

    def test_json_differential(self):
        path = self.gen.generate_differential_report(_differential(), "json")
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertIn("prspec_diff_eip1559_", Path(path).name)
        self.assertEqual(data["eip"], 1559)
        self.assertEqual(set(data["clients"]), {"go-ethereum", "nethermind"})

    def test_markdown_differential(self):
        path = self.gen.generate_differential_report(
            _differential(llm_synthesis="Clients disagree on the burn."), "md")
        md = Path(path).read_text(encoding="utf-8")
        self.assertIn("# Cross-Client Differential — EIP-1559: Fee market change", md)
        self.assertIn("| go-ethereum |", md)
        self.assertIn("### LLM Synthesis", md)
        self.assertIn("Clients disagree on the burn.", md)
        self.assertIn("## Divergences", md)
        self.assertIn(f"*Generated by PRSpec v{__version__}*", md)

    def test_markdown_differential_lists_agreements(self):
        per_client = {
            "go-ethereum": ClientAnalysis("go-ethereum", "go", [
                _result("eip1559.go", status="FULL_MATCH")]),
            "besu": ClientAnalysis("besu", "java", [
                _result("BaseFee.java", status="FULL_MATCH")]),
        }
        agreeing = DifferentialEngine().build(per_client, 1559, "EIP-1559")
        md = Path(self.gen.generate_differential_report(agreeing, "md")
                  ).read_text(encoding="utf-8")
        self.assertIn("## Agreements", md)
        self.assertNotIn("## Divergences", md)

    def test_markdown_differential_without_synthesis(self):
        md = Path(self.gen.generate_differential_report(_differential(), "markdown")
                  ).read_text(encoding="utf-8")
        self.assertNotIn("### LLM Synthesis", md)

    def test_html_differential(self):
        path = self.gen.generate_differential_report(
            _differential(llm_synthesis="Synthesis text."), "html")
        page = Path(path).read_text(encoding="utf-8")
        self.assertIn("Cross-Client Differential", page)
        self.assertIn("<h2>LLM Synthesis</h2>", page)
        self.assertIn("<h2>Divergences</h2>", page)
        self.assertIn("table class=\"matrix\"", page)
        self.assertIn("nethermind", page)

    def test_html_differential_without_synthesis(self):
        page = Path(self.gen.generate_differential_report(_differential(), "html")
                    ).read_text(encoding="utf-8")
        self.assertNotIn("LLM Synthesis", page)


class TestConsoleOutput(ReportTestCase):
    """The Rich console paths should render without raising."""

    def test_print_summary(self):
        results = [_result(issues=[_issue(verification={
            "verdict": "CONFIRMED", "verification_score": 95, "grounded": True})])]
        self.gen.console.begin_capture()
        try:
            self.gen.print_summary(results, _metadata())
            out = self.gen.console.end_capture()
        except BaseException:
            self.gen.console.end_capture()
            raise
        self.assertIn("Overall Status", out)
        self.assertIn("Verified", out)

    def test_print_summary_without_issues(self):
        self.gen.console.begin_capture()
        try:
            self.gen.print_summary([_result(status="FULL_MATCH")], _metadata())
            out = self.gen.console.end_capture()
        except BaseException:
            self.gen.console.end_capture()
            raise
        self.assertIn("Total Issues", out)

    def test_print_differential_summary(self):
        self.gen.console.begin_capture()
        try:
            self.gen.print_differential_summary(_differential("Synthesis text."))
            out = self.gen.console.end_capture()
        except BaseException:
            self.gen.console.end_capture()
            raise
        self.assertIn("Comparison Matrix", out)
        self.assertIn("Divergences", out)


class TestWithoutRich(ReportTestCase):
    """Fallbacks used when the optional rich dependency is missing."""

    def test_console_is_none(self):
        with mock.patch("src.report_generator.RICH_AVAILABLE", False):
            self.assertIsNone(ReportGenerator(self.tmpdir).console)

    def test_print_summary_notes_missing_dependency(self):
        with mock.patch("src.report_generator.RICH_AVAILABLE", False), \
                mock.patch("builtins.print") as printed:
            ReportGenerator(self.tmpdir).print_summary([_result()], _metadata())
        self.assertIn("Rich library not available", printed.call_args[0][0])

    def test_print_differential_summary_falls_back_to_narrative(self):
        differential = _differential()
        with mock.patch("src.report_generator.RICH_AVAILABLE", False), \
                mock.patch("builtins.print") as printed:
            ReportGenerator(self.tmpdir).print_differential_summary(differential)
        printed.assert_called_once_with(differential.narrative)


if __name__ == "__main__":
    unittest.main()
