"""Fail-closed behaviour: pinned refs, local sources, fetch errors, exit codes."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from click.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent))

from src import cli as cli_mod
from src.code_fetcher import CodeFetcher, FetchError

BESU_1559 = CodeFetcher.CLIENTS["besu"]["eip_files"][1559]


def _ok_response(text="class X {}"):
    resp = Mock()
    resp.text = text
    resp.raise_for_status = Mock()
    return resp


class TestFetchFailClosed(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.fetcher = CodeFetcher(cache_dir=self.tmp)

    def test_failed_file_is_not_passed_off_as_code(self):
        bad = BESU_1559[0]

        def fake_get(url, timeout=None):
            if url.endswith(bad):
                raise requests.HTTPError("404 Not Found")
            return _ok_response()

        with patch("requests.Session.get", side_effect=fake_get):
            files = self.fetcher.fetch_eip_implementation("besu", 1559)
        self.assertNotIn(bad, files)
        self.assertEqual(len(files), len(BESU_1559) - 1)
        self.assertIn(bad, self.fetcher.last_fetch_errors)
        for content in files.values():
            self.assertNotIn("Error fetching file", content)

    def test_no_file_loaded_raises(self):
        with patch("requests.Session.get",
                   side_effect=requests.ConnectionError("offline")):
            with self.assertRaises(FetchError):
                self.fetcher.fetch_eip_implementation("besu", 1559)

    def test_ref_pins_url_and_cache_key(self):
        sha = "8f01c7a3200780b00163ab76d544e0ef6646da41"
        with patch("requests.Session.get", return_value=_ok_response()) as get:
            self.fetcher.fetch_eip_implementation("besu", 1559, ref=sha)
        for call in get.call_args_list:
            self.assertIn(f"/besu-eth/besu/{sha}/", call[0][0])
        self.assertTrue(all(name.endswith(sha) for name in self.fetcher.list_cached_files()))

    def test_requests_have_timeout(self):
        with patch("requests.Session.get", return_value=_ok_response()) as get:
            self.fetcher.fetch_eip_implementation("besu", 1559)
        for call in get.call_args_list:
            self.assertEqual(call[1].get("timeout"), CodeFetcher.REQUEST_TIMEOUT)

    def test_source_dir_reads_local_checkout(self):
        root = Path(tempfile.mkdtemp())
        for rel in BESU_1559:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(f"// local {rel}")
        with patch("requests.Session.get") as get:
            files = self.fetcher.fetch_eip_implementation("besu", 1559, source_dir=str(root))
        get.assert_not_called()
        self.assertEqual(files[BESU_1559[0]], f"// local {BESU_1559[0]}")

    def test_source_dir_missing_file_is_recorded(self):
        root = Path(tempfile.mkdtemp())
        rel = BESU_1559[0]
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("// only one")
        files = self.fetcher.fetch_eip_implementation("besu", 1559, source_dir=str(root))
        self.assertEqual(list(files), [rel])
        self.assertEqual(len(self.fetcher.last_fetch_errors), len(BESU_1559) - 1)


def _result(name, status="PARTIAL_MATCH", issues=None):
    return {"file_name": name, "status": status, "confidence": 80,
            "issues": issues or [], "summary": ""}


class TestExitCodes(unittest.TestCase):
    def test_outcome_counts_errors_and_findings(self):
        results = [_result("a", issues=[{"type": "X"}]), _result("b", status="ERROR")]
        out = cli_mod._run_outcome(results, verified=False)
        self.assertEqual(out["findings"], 1)
        self.assertEqual(out["incomplete_files"], ["b"])

    def test_verified_counts_only_confirmed(self):
        issues = [{"verification": {"verdict": "CONFIRMED"}},
                  {"verification": {"verdict": "REFUTED"}}]
        out = cli_mod._run_outcome([_result("a", issues=issues)], verified=True)
        self.assertEqual(out["findings"], 1)

    def test_exit_code_matrix(self):
        clean = {"files": 2, "incomplete_files": [], "findings": 0}
        found = {"files": 2, "incomplete_files": [], "findings": 3}
        partial = {"files": 2, "incomplete_files": ["b"], "findings": 3}
        ec = cli_mod._exit_code
        self.assertEqual(ec(clean, "findings"), 0)
        self.assertEqual(ec(found, "incomplete"), 0)
        self.assertEqual(ec(found, "findings"), cli_mod.EXIT_FINDINGS)
        self.assertEqual(ec(partial, "incomplete"), cli_mod.EXIT_INCOMPLETE)
        # incomplete wins over findings: a partial run never looks clean
        self.assertEqual(ec(partial, "findings"), cli_mod.EXIT_INCOMPLETE)
        self.assertEqual(ec(partial, "never"), 0)


class TestAnalyzeCommandExit(unittest.TestCase):
    def _invoke(self, results, *args):
        analyzer = Mock()
        analyzer.get_model_info.return_value = {"model": "test-model"}
        with patch.object(cli_mod, "_run_analysis", return_value=(results, analyzer)) as run, \
             patch.object(cli_mod, "ReportGenerator") as rg:
            rg.return_value.generate_report.return_value = "output/report.json"
            res = CliRunner().invoke(
                cli_mod.cli, ["analyze", "--eip", "1559", "--client", "besu",
                              "--provider", "gemini", "--no-verify", *args])
        return res, run

    def test_error_result_exits_incomplete(self):
        res, _ = self._invoke([_result("a"), _result("b", status="ERROR")])
        self.assertEqual(res.exit_code, cli_mod.EXIT_INCOMPLETE, res.output)
        self.assertIn("ANALYSIS INCOMPLETE", res.output)

    def test_findings_exit_only_when_requested(self):
        results = [_result("a", issues=[{"type": "X"}])]
        res, _ = self._invoke(results)
        self.assertEqual(res.exit_code, 0, res.output)
        res, _ = self._invoke(results, "--fail-on", "findings")
        self.assertEqual(res.exit_code, cli_mod.EXIT_FINDINGS, res.output)

    def test_clean_run_exits_zero(self):
        res, _ = self._invoke([_result("a", status="FULL_MATCH")], "--fail-on", "findings")
        self.assertEqual(res.exit_code, 0, res.output)

    def test_ref_and_source_dir_are_forwarded(self):
        src = tempfile.mkdtemp()
        res, run = self._invoke([_result("a")], "--ref", "abc123", "--source-dir", src)
        self.assertEqual(res.exit_code, 0, res.output)
        self.assertEqual(run.call_args.kwargs["ref"], "abc123")
        self.assertEqual(run.call_args.kwargs["source_dir"], src)


class TestPackaging(unittest.TestCase):
    def test_bundled_default_config_matches_repo_config(self):
        root = Path(__file__).parent.parent
        self.assertEqual((root / "src/default_config.yaml").read_text(),
                         (root / "config.yaml").read_text())

    def test_config_falls_back_to_bundled_defaults(self):
        from src.config import Config
        empty = tempfile.mkdtemp()
        with patch("src.config.Path.cwd", return_value=Path(empty) / "sub"), \
             patch("src.config.Path.exists", autospec=True,
                   side_effect=lambda p: p.name == "default_config.yaml"):
            path = Config()._find_config_file()
        self.assertTrue(path.endswith("default_config.yaml"))

    def test_src_package_is_declared(self):
        text = (Path(__file__).parent.parent / "pyproject.toml").read_text()
        self.assertIn("[tool.setuptools.packages.find]", text)
        self.assertIn('include = ["src", "src.*"]', text)


if __name__ == "__main__":
    unittest.main()
