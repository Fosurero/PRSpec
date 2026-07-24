"""Tests for the GitHub code fetcher (caching, error handling, search, clone)."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.code_fetcher import CodeFetcher


def _response(text="package core\n", status=200, payload=None):
    response = mock.MagicMock()
    response.text = text
    response.status_code = status
    response.json.return_value = payload or {}
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(str(status))
    else:
        response.raise_for_status.return_value = None
    return response


class CodeFetcherTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="prspec_code_")
        self.fetcher = CodeFetcher(cache_dir=self.tmpdir)
        self.fetcher.session = mock.MagicMock()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestConstruction(unittest.TestCase):
    def test_default_cache_dir_is_created_in_cwd(self):
        tmpdir = tempfile.mkdtemp(prefix="prspec_cwd_")
        try:
            with mock.patch.object(Path, "cwd", return_value=Path(tmpdir)):
                fetcher = CodeFetcher()
            self.assertTrue(Path(tmpdir, ".code_cache").is_dir())
            self.assertEqual(fetcher.cache_dir, Path(tmpdir, ".code_cache"))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_token_sets_authorization_header(self):
        tmpdir = tempfile.mkdtemp(prefix="prspec_token_")
        try:
            fetcher = CodeFetcher(github_token="gh-token", cache_dir=tmpdir)
            self.assertEqual(fetcher.session.headers["Authorization"], "token gh-token")
            self.assertEqual(fetcher.session.headers["Accept"],
                             "application/vnd.github.v3+json")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestRegistryHelpers(unittest.TestCase):
    def test_supported_clients(self):
        self.assertIn("go-ethereum", CodeFetcher.supported_clients())

    def test_client_language(self):
        self.assertEqual(CodeFetcher.client_language("go-ethereum"), "go")

    def test_client_language_unknown_raises(self):
        with self.assertRaises(ValueError):
            CodeFetcher.client_language("erigon")

    def test_supported_eips_for_client_is_sorted(self):
        eips = CodeFetcher.supported_eips_for_client("go-ethereum")
        self.assertEqual(eips, sorted(eips))
        self.assertIn(1559, eips)

    def test_supported_eips_for_unknown_client_raises(self):
        with self.assertRaises(ValueError):
            CodeFetcher.supported_eips_for_client("erigon")


class TestFetchFile(CodeFetcherTestCase):
    def test_fetches_from_raw_github_and_caches(self):
        self.fetcher.session.get.return_value = _response("contents")
        content = self.fetcher.fetch_file("ethereum", "go-ethereum", "core/x.go")
        url = self.fetcher.session.get.call_args.args[0]
        self.assertEqual(content, "contents")
        self.assertEqual(
            url, "https://raw.githubusercontent.com/ethereum/go-ethereum/master/core/x.go")
        self.assertIn("ethereum_go-ethereum_core_x.go_master",
                      self.fetcher.list_cached_files())

    def test_cache_hit_skips_the_network(self):
        self.fetcher.session.get.return_value = _response("first")
        self.fetcher.fetch_file("ethereum", "go-ethereum", "core/x.go")
        self.fetcher.session.get.reset_mock()
        again = self.fetcher.fetch_file("ethereum", "go-ethereum", "core/x.go")
        self.assertEqual(again, "first")
        self.fetcher.session.get.assert_not_called()

    def test_use_cache_false_refetches(self):
        self.fetcher.session.get.return_value = _response("first")
        self.fetcher.fetch_file("ethereum", "go-ethereum", "core/x.go")
        self.fetcher.session.get.return_value = _response("second")
        again = self.fetcher.fetch_file("ethereum", "go-ethereum", "core/x.go",
                                        use_cache=False)
        self.assertEqual(again, "second")

    def test_branch_is_part_of_url_and_cache_key(self):
        self.fetcher.session.get.return_value = _response("dev contents")
        self.fetcher.fetch_file("hyperledger", "besu", "a/B.java", branch="main")
        self.assertIn("/besu/main/a/B.java", self.fetcher.session.get.call_args.args[0])
        self.assertIn("hyperledger_besu_a_B.java_main", self.fetcher.list_cached_files())

    def test_http_error_propagates(self):
        self.fetcher.session.get.return_value = _response(status=404)
        with self.assertRaises(requests.HTTPError):
            self.fetcher.fetch_file("ethereum", "go-ethereum", "missing.go")

    def test_fetch_geth_file_shortcut(self):
        self.fetcher.session.get.return_value = _response("geth")
        self.assertEqual(self.fetcher.fetch_geth_file("core/x.go"), "geth")
        self.assertIn("/ethereum/go-ethereum/master/core/x.go",
                      self.fetcher.session.get.call_args.args[0])


class TestFetchEipImplementation(CodeFetcherTestCase):
    def test_unknown_client_raises(self):
        with self.assertRaises(ValueError):
            self.fetcher.fetch_eip_implementation("erigon", 1559)

    def test_unmapped_eip_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.fetcher.fetch_eip_implementation("go-ethereum", 9999)
        self.assertIn("No file mappings for EIP-9999", str(ctx.exception))

    def test_returns_one_entry_per_mapped_file(self):
        self.fetcher.session.get.return_value = _response("code")
        files = self.fetcher.fetch_eip_implementation("go-ethereum", 1559)
        self.assertEqual(set(files),
                         set(CodeFetcher.CLIENTS["go-ethereum"]["eip_files"][1559]))
        self.assertTrue(all(v == "code" for v in files.values()))

    def test_uses_the_client_branch(self):
        self.fetcher.session.get.return_value = _response("code")
        self.fetcher.fetch_eip_implementation("reth", 7702)
        branch = CodeFetcher.CLIENTS["reth"].get("branch", "master")
        self.assertIn(f"/reth/{branch}/", self.fetcher.session.get.call_args.args[0])

    def test_failed_file_is_reported_inline(self):
        self.fetcher.session.get.return_value = _response(status=500)
        files = self.fetcher.fetch_eip_implementation("go-ethereum", 1559)
        self.assertTrue(all(v.startswith("# Error fetching file:")
                            for v in files.values()))

    def test_legacy_shortcuts_delegate(self):
        with mock.patch.object(self.fetcher, "fetch_eip_implementation",
                               return_value={}) as fetch:
            self.fetcher.fetch_eip1559_implementation()
            self.fetcher.fetch_eip4844_implementation("besu")
            self.fetcher.fetch_geth_eip1559()
            self.fetcher.fetch_geth_eip4844()
        self.assertEqual([c.args for c in fetch.call_args_list], [
            ("go-ethereum", 1559), ("besu", 4844),
            ("go-ethereum", 1559), ("go-ethereum", 4844),
        ])


class TestSearchAndClone(CodeFetcherTestCase):
    def test_search_builds_a_scoped_query(self):
        self.fetcher.session.get.return_value = _response(
            payload={"items": [{"path": "core/x.go"}]})
        items = self.fetcher.search_repository("ethereum", "go-ethereum",
                                               "CalcBaseFee", language="go")
        params = self.fetcher.session.get.call_args.kwargs["params"]
        self.assertEqual(params["q"],
                         "CalcBaseFee repo:ethereum/go-ethereum language:go")
        self.assertEqual(items, [{"path": "core/x.go"}])

    def test_search_without_language_filter(self):
        self.fetcher.session.get.return_value = _response(payload={})
        self.assertEqual(
            self.fetcher.search_repository("ethereum", "go-ethereum", "q"), [])
        self.assertNotIn("language:",
                         self.fetcher.session.get.call_args.kwargs["params"]["q"])

    def test_clone_shallow_by_default(self):
        with mock.patch("src.code_fetcher.GIT_AVAILABLE", True), \
                mock.patch("src.code_fetcher.Repo", create=True) as repo:
            target = self.fetcher.clone_repository(
                "https://github.com/ethereum/go-ethereum",
                target_dir=self.tmpdir, branch="main")
        self.assertEqual(target, self.tmpdir)
        self.assertEqual(repo.clone_from.call_args.kwargs,
                         {"branch": "main", "depth": 1})

    def test_clone_full_creates_a_temp_dir(self):
        with mock.patch("src.code_fetcher.GIT_AVAILABLE", True), \
                mock.patch("src.code_fetcher.Repo", create=True) as repo, \
                mock.patch("src.code_fetcher.tempfile.mkdtemp",
                           return_value="/tmp/prspec_clone"):
            target = self.fetcher.clone_repository("https://example/repo",
                                                   shallow=False)
        self.assertEqual(target, "/tmp/prspec_clone")
        self.assertNotIn("depth", repo.clone_from.call_args.kwargs)

    def test_clone_without_gitpython_raises(self):
        with mock.patch("src.code_fetcher.GIT_AVAILABLE", False):
            with self.assertRaises(RuntimeError):
                self.fetcher.clone_repository("https://example/repo")


class TestCacheManagement(CodeFetcherTestCase):
    def test_clear_cache_empties_but_keeps_the_directory(self):
        Path(self.tmpdir, "cached_file").write_text("x")
        self.fetcher.clear_cache()
        self.assertTrue(Path(self.tmpdir).is_dir())
        self.assertEqual(self.fetcher.list_cached_files(), [])

    def test_clear_cache_when_directory_is_absent(self):
        shutil.rmtree(self.tmpdir)
        self.fetcher.clear_cache()
        self.assertEqual(self.fetcher.list_cached_files(), [])

    def test_list_cached_files_ignores_subdirectories(self):
        Path(self.tmpdir, "a_file").write_text("x")
        Path(self.tmpdir, "a_dir").mkdir()
        self.assertEqual(self.fetcher.list_cached_files(), ["a_file"])


if __name__ == "__main__":
    unittest.main()
