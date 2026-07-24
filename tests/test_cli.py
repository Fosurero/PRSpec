"""Tests for the PRSpec command-line interface.

Every command is driven through Click's ``CliRunner`` with the network-facing
pieces (spec/code fetchers and LLM analyzers) replaced by stubs.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import cli as cli_module
from src.cli import (
    _analyze_one_file,
    _build_analyzer,
    _build_verify_analyzer,
    _run_analysis,
    cli,
    main,
)


class FakeAnalysisResult:
    """Stands in for :class:`src.analyzer.AnalysisResult`."""

    def __init__(self, status="FULL_MATCH", issues=None):
        self.status = status
        self.issues = issues or []

    def to_dict(self):
        return {
            "status": self.status,
            "confidence": 90,
            "issues": self.issues,
            "summary": "Looks fine.",
        }


class FakeAnalyzer:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []

    def analyze_compliance(self, spec_text, code_text, context):
        self.calls.append((spec_text, code_text, context))
        return FakeAnalysisResult()

    def get_model_info(self):
        return {"provider": "fake", "model": "fake-model"}


class FakeConfig:
    """Minimal stand-in for :class:`src.config.Config`."""

    def __init__(self, config_path=None):
        self.config_path = config_path
        self.llm_provider = "gemini"
        self.github_token = None
        self.gemini_api_key = "gemini-key"
        self.openai_api_key = "openai-key"
        self.azure_api_key = "azure-key"
        self.gemini_config = {"model": "gemini-2.5-pro"}
        self.openai_config = {"model": "gpt-4-turbo-preview"}
        self.azure_config = {"endpoint": "https://example/v1", "model": "claude"}
        self.azure_verify_config = None
        self.output_config = {"format": "json", "directory": "output"}

    def get_eip_focus_areas(self, eip):
        return ["base_fee_calculation"]


SPEC_DATA = {
    "title": "EIP-1559: Fee market change",
    "eip_markdown": "the base fee MUST be burned",
    "execution_spec": "def calculate_base_fee(): ...",
    "execution_spec_mode": "diff",
}

CODE_FILES = {"a.go": "package core", "b.go": "package types"}


def _patch_pipeline(**overrides):
    """Patch the network-facing collaborators used by ``_run_analysis``."""
    spec_fetcher = mock.MagicMock()
    spec_fetcher.fetch_eip_spec.return_value = overrides.get("spec_data", SPEC_DATA)
    code_fetcher = mock.MagicMock()
    code_fetcher.fetch_eip_implementation.return_value = overrides.get(
        "code_files", CODE_FILES)
    return mock.patch.multiple(
        cli_module,
        SpecFetcher=mock.MagicMock(return_value=spec_fetcher),
        CodeFetcher=mock.MagicMock(
            return_value=code_fetcher,
            client_language=mock.MagicMock(return_value="go"),
            CLIENTS={"go-ethereum": {"eip_files": {1559: ["a.go", "b.go"]}}},
            supported_clients=mock.MagicMock(
                return_value=["go-ethereum", "nethermind", "besu"]),
            supported_eips_for_client=mock.MagicMock(return_value=[1559]),
        ),
    )


class TestHelpers(unittest.TestCase):
    def test_analyze_one_file_tags_the_file_name(self):
        analyzer = FakeAnalyzer()
        out = _analyze_one_file(analyzer, "spec", "path/to/x.go", "code", {"eip_number": 1559})
        self.assertEqual(out["file_name"], "path/to/x.go")
        self.assertEqual(out["status"], "FULL_MATCH")

    def test_build_analyzer_gemini(self):
        cfg = FakeConfig()
        with mock.patch.object(cli_module, "GeminiAnalyzer", FakeAnalyzer) as _:
            analyzer = _build_analyzer("gemini", cfg)
        self.assertEqual(analyzer.kwargs["api_key"], "gemini-key")
        self.assertEqual(analyzer.kwargs["model"], "gemini-2.5-pro")

    def test_build_analyzer_azure(self):
        with mock.patch.object(cli_module, "AzureAIAnalyzer", FakeAnalyzer):
            analyzer = _build_analyzer("azure", FakeConfig())
        self.assertEqual(analyzer.kwargs["api_key"], "azure-key")
        self.assertEqual(analyzer.kwargs["endpoint"], "https://example/v1")

    def test_build_analyzer_defaults_to_openai(self):
        with mock.patch.object(cli_module, "OpenAIAnalyzer", FakeAnalyzer):
            analyzer = _build_analyzer("openai", FakeConfig())
        self.assertEqual(analyzer.kwargs["api_key"], "openai-key")

    def test_verify_analyzer_reuses_primary_for_non_azure(self):
        primary = FakeAnalyzer()
        self.assertIs(_build_verify_analyzer("gemini", FakeConfig(), primary), primary)

    def test_verify_analyzer_reuses_primary_when_azure_has_no_override(self):
        primary = FakeAnalyzer()
        self.assertIs(_build_verify_analyzer("azure", FakeConfig(), primary), primary)

    def test_verify_analyzer_uses_separate_azure_deployment(self):
        cfg = FakeConfig()
        cfg.azure_verify_config = {"endpoint": "https://example/v1", "model": "sonnet"}
        primary = FakeAnalyzer()
        with mock.patch.object(cli_module, "AzureAIAnalyzer", FakeAnalyzer):
            verify = _build_verify_analyzer("azure", cfg, primary)
        self.assertIsNot(verify, primary)
        self.assertEqual(verify.kwargs["model"], "sonnet")


class TestRunAnalysis(unittest.TestCase):
    def test_results_follow_source_file_order(self):
        seen = []
        with _patch_pipeline(), mock.patch.object(cli_module, "GeminiAnalyzer", FakeAnalyzer):
            results, analyzer = _run_analysis(
                1559, "go-ethereum", FakeConfig(), "gemini",
                progress_callback=seen.append,
            )
        self.assertEqual([r["file_name"] for r in results], ["a.go", "b.go"])
        self.assertEqual(sorted(seen), ["a.go", "b.go"])
        self.assertIsInstance(analyzer, FakeAnalyzer)

    def test_spec_text_includes_fork_diff(self):
        with _patch_pipeline(), mock.patch.object(cli_module, "GeminiAnalyzer", FakeAnalyzer):
            _, analyzer = _run_analysis(1559, "go-ethereum", FakeConfig(), "gemini")
        spec_text = analyzer.calls[0][0]
        self.assertIn("the base fee MUST be burned", spec_text)
        self.assertIn("EXECUTION-SPEC FORK DIFF", spec_text)

    def test_spec_text_omits_fork_diff_when_not_a_diff(self):
        spec_data = dict(SPEC_DATA, execution_spec_mode="full")
        with _patch_pipeline(spec_data=spec_data), \
                mock.patch.object(cli_module, "GeminiAnalyzer", FakeAnalyzer):
            _, analyzer = _run_analysis(1559, "go-ethereum", FakeConfig(), "gemini")
        self.assertNotIn("EXECUTION-SPEC FORK DIFF", analyzer.calls[0][0])

    def test_context_passed_to_analyzer(self):
        with _patch_pipeline(), mock.patch.object(cli_module, "GeminiAnalyzer", FakeAnalyzer):
            _, analyzer = _run_analysis(1559, "go-ethereum", FakeConfig(), "gemini")
        context = analyzer.calls[0][2]
        self.assertEqual(context["eip_number"], 1559)
        self.assertEqual(context["language"], "go")
        self.assertEqual(context["focus_areas"], ["base_fee_calculation"])

    def test_verification_engine_invoked_when_verify_is_set(self):
        engine = mock.MagicMock()
        with _patch_pipeline(), \
                mock.patch.object(cli_module, "GeminiAnalyzer", FakeAnalyzer), \
                mock.patch("src.verifier.VerificationEngine", return_value=engine) as ctor:
            _run_analysis(1559, "go-ethereum", FakeConfig(), "gemini",
                          verify=True, verify_rounds=3)
        self.assertEqual(ctor.call_args.kwargs["rounds"], 3)
        engine.verify_results.assert_called_once()


class CliTestCase(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()


class TestAnalyzeCommand(CliTestCase):
    def _invoke(self, args, results=None):
        results = results if results is not None else [
            {"file_name": "a.go", "status": "FULL_MATCH", "confidence": 90,
             "issues": [], "summary": "Fine."},
        ]
        with self.runner.isolated_filesystem(), \
                mock.patch.object(cli_module, "Config", FakeConfig), \
                mock.patch.object(cli_module, "_run_analysis",
                                  return_value=(results, FakeAnalyzer())) as run:
            result = self.runner.invoke(cli, ["analyze"] + args)
        return result, run

    def test_writes_a_report(self):
        result, run = self._invoke(["--eip", "1559", "--client", "go-ethereum",
                                    "--no-verify"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Report saved to", result.output)
        self.assertEqual(run.call_args.args[0], 1559)
        self.assertFalse(run.call_args.kwargs["verify"])

    def test_verify_flag_forwards_rounds(self):
        result, run = self._invoke(["--verify", "--verify-rounds", "4"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(run.call_args.kwargs["verify"])
        self.assertEqual(run.call_args.kwargs["verify_rounds"], 4)
        self.assertIn("skeptic round", result.output)

    def test_markdown_output_format(self):
        with self.runner.isolated_filesystem() as fs, \
                mock.patch.object(cli_module, "Config", FakeConfig), \
                mock.patch.object(cli_module, "_run_analysis",
                                  return_value=([], FakeAnalyzer())):
            result = self.runner.invoke(cli, ["analyze", "--output", "markdown",
                                              "--no-verify"])
            reports = list(Path(fs, "output").glob("*.md"))
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(len(reports), 1)

    def test_failure_is_reported_and_aborts(self):
        with self.runner.isolated_filesystem(), \
                mock.patch.object(cli_module, "Config", FakeConfig), \
                mock.patch.object(cli_module, "_run_analysis",
                                  side_effect=RuntimeError("boom")):
            result = self.runner.invoke(cli, ["analyze", "--verbose"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("boom", result.output)


class TestDiffCommand(CliTestCase):
    def _run_analysis_stub(self, eip, client, cfg, provider, **kwargs):
        results = [{"file_name": f"{client}.go", "status": "FULL_MATCH",
                    "confidence": 90, "issues": [], "summary": "Fine."}]
        return results, FakeAnalyzer()

    def _invoke(self, args):
        with self.runner.isolated_filesystem(), _patch_pipeline(), \
                mock.patch.object(cli_module, "Config", FakeConfig), \
                mock.patch.object(cli_module, "_run_analysis",
                                  side_effect=self._run_analysis_stub):
            return self.runner.invoke(cli, ["diff"] + args)

    def test_explicit_client_list(self):
        result = self._invoke(["--eip", "1559",
                               "--clients", "go-ethereum,nethermind"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Differential report saved to", result.output)

    def test_defaults_to_every_client_with_mappings(self):
        result = self._invoke(["--eip", "1559"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("besu", result.output)

    def test_requires_two_usable_clients(self):
        result = self._invoke(["--eip", "1559", "--clients", "go-ethereum"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("at least 2 clients", result.output)

    def test_llm_synthesis_is_attached(self):
        with self.runner.isolated_filesystem(), _patch_pipeline(), \
                mock.patch.object(cli_module, "Config", FakeConfig), \
                mock.patch.object(cli_module, "_run_analysis",
                                  side_effect=self._run_analysis_stub), \
                mock.patch("src.differential.DifferentialEngine.synthesize",
                           return_value="Synthesised narrative.") as synth:
            result = self.runner.invoke(cli, ["diff", "--llm-synthesis"])
        self.assertEqual(result.exit_code, 0, result.output)
        synth.assert_called_once()
        self.assertIn("Synthesised narrative.", result.output)

    def test_failure_is_reported_and_aborts(self):
        with self.runner.isolated_filesystem(), _patch_pipeline(), \
                mock.patch.object(cli_module, "Config", FakeConfig), \
                mock.patch.object(cli_module, "_run_analysis",
                                  side_effect=RuntimeError("kaboom")):
            result = self.runner.invoke(cli, ["diff", "--verbose"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("kaboom", result.output)


class TestInformationalCommands(CliTestCase):
    def test_fetch_spec(self):
        fetcher = mock.MagicMock()
        fetcher.fetch_eip.return_value = "# EIP-1559\n\nBase fee text."
        with mock.patch.object(cli_module, "SpecFetcher", return_value=fetcher):
            result = self.runner.invoke(cli, ["fetch-spec", "--eip", "1559"])
        self.assertEqual(result.exit_code, 0, result.output)
        fetcher.fetch_eip.assert_called_once_with(1559)

    def test_fetch_spec_error(self):
        with mock.patch.object(cli_module, "SpecFetcher",
                               side_effect=RuntimeError("offline")):
            result = self.runner.invoke(cli, ["fetch-spec"])
        self.assertIn("offline", result.output)

    def test_list_files(self):
        fetcher = mock.MagicMock()
        fetcher.fetch_eip_implementation.return_value = {"a.go": "line\nline"}
        with mock.patch.object(cli_module, "CodeFetcher", return_value=fetcher):
            result = self.runner.invoke(cli, ["list-files", "--client",
                                              "go-ethereum", "--eip", "4844"])
        self.assertEqual(result.exit_code, 0, result.output)
        fetcher.fetch_eip_implementation.assert_called_once_with("go-ethereum", 4844)
        self.assertIn("a.go", result.output)

    def test_list_files_error(self):
        with mock.patch.object(cli_module, "CodeFetcher",
                               side_effect=RuntimeError("no mapping")):
            result = self.runner.invoke(cli, ["list-files"])
        self.assertIn("no mapping", result.output)

    def test_list_eips(self):
        spec_fetcher = mock.MagicMock()
        spec_fetcher.supported_eips.return_value = [1559]
        spec_fetcher.get_eip_title.return_value = "EIP-1559: Fee market change"
        code_fetcher = mock.MagicMock()
        code_fetcher.supported_clients.return_value = ["go-ethereum", "besu"]
        code_fetcher.supported_eips_for_client.side_effect = \
            lambda c: [1559] if c == "go-ethereum" else []
        with mock.patch.object(cli_module, "SpecFetcher", return_value=spec_fetcher), \
                mock.patch.object(cli_module, "CodeFetcher", return_value=code_fetcher):
            result = self.runner.invoke(cli, ["list-eips"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("1559", result.output)

    def test_list_eips_error(self):
        with mock.patch.object(cli_module, "SpecFetcher",
                               side_effect=RuntimeError("registry broken")):
            result = self.runner.invoke(cli, ["list-eips"])
        self.assertIn("registry broken", result.output)

    def test_clear_cache(self):
        spec_fetcher, code_fetcher = mock.MagicMock(), mock.MagicMock()
        with mock.patch.object(cli_module, "SpecFetcher", return_value=spec_fetcher), \
                mock.patch.object(cli_module, "CodeFetcher", return_value=code_fetcher):
            result = self.runner.invoke(cli, ["clear-cache"])
        self.assertEqual(result.exit_code, 0, result.output)
        spec_fetcher.clear_cache.assert_called_once()
        code_fetcher.clear_cache.assert_called_once()

    def test_clear_cache_error(self):
        with mock.patch.object(cli_module, "SpecFetcher",
                               side_effect=RuntimeError("permission denied")):
            result = self.runner.invoke(cli, ["clear-cache"])
        self.assertIn("permission denied", result.output)


class TestCheckConfigCommand(CliTestCase):
    def test_all_keys_present(self):
        cfg = FakeConfig()
        cfg.github_token = "gh-token"
        with mock.patch.object(cli_module, "Config", return_value=cfg):
            result = self.runner.invoke(cli, ["check-config"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Gemini API Key", result.output)
        self.assertIn("gemini", result.output)  # active provider

    def test_missing_keys_are_flagged(self):
        cfg = mock.MagicMock()
        type(cfg).gemini_api_key = mock.PropertyMock(side_effect=ValueError)
        type(cfg).openai_api_key = mock.PropertyMock(side_effect=ValueError)
        type(cfg).azure_api_key = mock.PropertyMock(side_effect=ValueError)
        cfg.github_token = None
        cfg.llm_provider = "gemini"
        with mock.patch.object(cli_module, "Config", return_value=cfg):
            result = self.runner.invoke(cli, ["check-config"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Not set", result.output)

    def test_azure_endpoint_missing_is_flagged(self):
        cfg = FakeConfig()
        cfg.azure_config = {"endpoint": "", "model": "claude"}
        with mock.patch.object(cli_module, "Config", return_value=cfg):
            result = self.runner.invoke(cli, ["check-config"])
        self.assertIn("endpoint missing", result.output)

    def test_config_load_failure(self):
        with mock.patch.object(cli_module, "Config",
                               side_effect=RuntimeError("bad yaml")):
            result = self.runner.invoke(cli, ["check-config"])
        self.assertIn("bad yaml", result.output)


class TestEntryPoint(CliTestCase):
    def test_version_option(self):
        result = self.runner.invoke(cli, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("PRSpec", result.output)

    def test_group_help_lists_commands(self):
        result = self.runner.invoke(cli, ["--help"])
        for command in ("analyze", "diff", "fetch-spec", "list-files",
                        "list-eips", "clear-cache", "check-config"):
            self.assertIn(command, result.output)

    def test_main_invokes_the_group(self):
        with mock.patch.object(cli_module, "cli") as group:
            main()
        group.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
