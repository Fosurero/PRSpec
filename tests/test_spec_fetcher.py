"""Tests for spec fetching, caching, fork diffing, and section extraction."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.spec_fetcher import SpecFetcher

EIP_MARKDOWN = """---
eip: 1559
---

Preamble text.

## Abstract

A fee market change.

## Specification

The base fee is burned.

More base fee rules here.
Line three.
Line four.
Line five.

Trailing paragraph.

## Rationale

Because.
"""


def _response(text="content", status=200):
    response = mock.MagicMock()
    response.text = text
    response.status_code = status
    if status >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(str(status))
    else:
        response.raise_for_status.return_value = None
    return response


class SpecFetcherTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="prspec_spec_")
        self.fetcher = SpecFetcher(cache_dir=self.tmpdir)
        self.fetcher.session = mock.MagicMock()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)


class TestConstruction(unittest.TestCase):
    def test_default_cache_dir_is_created_in_cwd(self):
        tmpdir = tempfile.mkdtemp(prefix="prspec_spec_cwd_")
        try:
            with mock.patch.object(Path, "cwd", return_value=Path(tmpdir)):
                fetcher = SpecFetcher()
            self.assertEqual(fetcher.cache_dir, Path(tmpdir, ".spec_cache"))
            self.assertTrue(fetcher.cache_dir.is_dir())
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_token_sets_authorization_header(self):
        tmpdir = tempfile.mkdtemp(prefix="prspec_spec_token_")
        try:
            fetcher = SpecFetcher(github_token="gh-token", cache_dir=tmpdir)
            self.assertEqual(fetcher.session.headers["Authorization"], "token gh-token")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestRegistryHelpers(unittest.TestCase):
    def test_supported_eips_sorted(self):
        eips = SpecFetcher.supported_eips()
        self.assertEqual(eips, sorted(eips))
        self.assertIn(1559, eips)

    def test_known_title(self):
        self.assertTrue(SpecFetcher.get_eip_title(1559).startswith("EIP-1559:"))

    def test_unknown_title_falls_back(self):
        self.assertEqual(SpecFetcher.get_eip_title(9999), "EIP-9999")


class TestFetchers(SpecFetcherTestCase):
    def test_fetch_eip_hits_the_eips_repo_and_caches(self):
        self.fetcher.session.get.return_value = _response(EIP_MARKDOWN)
        content = self.fetcher.fetch_eip(1559)
        self.assertEqual(content, EIP_MARKDOWN)
        self.assertIn("EIPS/eip-1559.md", self.fetcher.session.get.call_args.args[0])
        self.assertIn("eip-1559.md", self.fetcher.list_cached_specs())

        self.fetcher.session.get.reset_mock()
        self.assertEqual(self.fetcher.fetch_eip(1559), EIP_MARKDOWN)
        self.fetcher.session.get.assert_not_called()

    def test_fetch_eip_ignoring_cache(self):
        self.fetcher.session.get.return_value = _response("first")
        self.fetcher.fetch_eip(1559)
        self.fetcher.session.get.return_value = _response("second")
        self.assertEqual(self.fetcher.fetch_eip(1559, use_cache=False), "second")

    def test_fetch_eip_http_error_propagates(self):
        self.fetcher.session.get.return_value = _response(status=404)
        with self.assertRaises(requests.HTTPError):
            self.fetcher.fetch_eip(9999)

    def test_fetch_execution_spec(self):
        self.fetcher.session.get.return_value = _response("def fork(): ...")
        content = self.fetcher.fetch_execution_spec("src/ethereum/forks/london/fork.py")
        self.assertEqual(content, "def fork(): ...")
        self.assertIn("execution-specs/master/src/ethereum/forks/london/fork.py",
                      self.fetcher.session.get.call_args.args[0])
        self.fetcher.session.get.reset_mock()
        self.fetcher.fetch_execution_spec("src/ethereum/forks/london/fork.py")
        self.fetcher.session.get.assert_not_called()

    def test_fetch_consensus_spec_defaults_to_the_dev_branch(self):
        self.fetcher.session.get.return_value = _response("# Deneb")
        self.fetcher.fetch_consensus_spec("specs/deneb/beacon-chain.md")
        self.assertIn("consensus-specs/dev/specs/deneb/beacon-chain.md",
                      self.fetcher.session.get.call_args.args[0])


class TestForkDiff(SpecFetcherTestCase):
    def test_diff_isolates_the_fork_delta(self):
        with mock.patch.object(self.fetcher, "fetch_execution_spec",
                               side_effect=["new line\ncommon\n", "common\n"]):
            diff = self.fetcher.fetch_execution_spec_diff(1559)
        self.assertIn("+new line", diff)
        self.assertIn("forks/london/fork.py", diff)
        self.assertIn("forks/berlin/fork.py", diff)

    def test_identical_forks_produce_no_diff(self):
        with mock.patch.object(self.fetcher, "fetch_execution_spec",
                               return_value="same\n"):
            self.assertIsNone(self.fetcher.fetch_execution_spec_diff(1559))

    def test_missing_predecessor_returns_none(self):
        # EIP-7251 has no predecessor_fork registered.
        self.assertIsNone(self.fetcher.fetch_execution_spec_diff(7251))

    def test_unknown_eip_returns_none(self):
        self.assertIsNone(self.fetcher.fetch_execution_spec_diff(9999))

    def test_fetch_failure_returns_none(self):
        with mock.patch.object(self.fetcher, "fetch_execution_spec",
                               side_effect=requests.ConnectionError("offline")):
            self.assertIsNone(self.fetcher.fetch_execution_spec_diff(1559))


class TestFetchEipSpec(SpecFetcherTestCase):
    def setUp(self):
        super().setUp()
        self.eip = mock.patch.object(self.fetcher, "fetch_eip",
                                     return_value=EIP_MARKDOWN)
        self.eip.start()
        self.addCleanup(self.eip.stop)

    def test_full_mode_uses_the_first_fetchable_spec_file(self):
        with mock.patch.object(self.fetcher, "fetch_execution_spec",
                               side_effect=[requests.HTTPError("404"), "fork source"]):
            spec = self.fetcher.fetch_eip_spec(1559)
        self.assertEqual(spec["execution_spec"], "fork source")
        self.assertEqual(spec["execution_spec_mode"], "full")
        self.assertTrue(spec["title"].startswith("EIP-1559:"))

    def test_diff_mode_prefers_the_fork_diff(self):
        with mock.patch.object(self.fetcher, "fetch_execution_spec_diff",
                               return_value="@@ diff @@"), \
                mock.patch.object(self.fetcher, "fetch_execution_spec") as full:
            spec = self.fetcher.fetch_eip_spec(1559, mode="diff")
        self.assertEqual(spec["execution_spec"], "@@ diff @@")
        self.assertEqual(spec["execution_spec_mode"], "diff")
        full.assert_not_called()

    def test_diff_mode_falls_back_to_the_full_file(self):
        with mock.patch.object(self.fetcher, "fetch_execution_spec_diff",
                               return_value=None), \
                mock.patch.object(self.fetcher, "fetch_execution_spec",
                                  return_value="fork source"):
            spec = self.fetcher.fetch_eip_spec(1559, mode="diff")
        self.assertEqual(spec["execution_spec_mode"], "full")
        self.assertEqual(spec["execution_spec"], "fork source")

    def test_consensus_specs_are_concatenated(self):
        with mock.patch.object(self.fetcher, "fetch_execution_spec",
                               return_value="fork source"), \
                mock.patch.object(self.fetcher, "fetch_consensus_spec",
                                  side_effect=["beacon", requests.HTTPError("404")]):
            spec = self.fetcher.fetch_eip_spec(4844)
        self.assertEqual(spec["consensus_spec"], "beacon")

    def test_unknown_eip_has_no_spec_paths(self):
        spec = self.fetcher.fetch_eip_spec(9999)
        self.assertIsNone(spec["execution_spec"])
        self.assertIsNone(spec["consensus_spec"])
        self.assertEqual(spec["title"], "EIP-9999")

    def test_legacy_shortcuts_delegate(self):
        with mock.patch.object(self.fetcher, "fetch_eip_spec",
                               return_value={}) as fetch:
            self.fetcher.fetch_eip1559_spec()
            self.fetcher.fetch_eip4844_spec()
        self.assertEqual([c.args for c in fetch.call_args_list], [(1559,), (4844,)])


class TestSectionExtraction(SpecFetcherTestCase):
    def test_sections_are_keyed_by_slugified_heading(self):
        sections = self.fetcher.extract_eip_sections(EIP_MARKDOWN)
        self.assertEqual(set(sections), {"header", "abstract", "specification",
                                         "rationale"})
        self.assertIn("The base fee is burned.", sections["specification"])

    def test_specification_section_is_returned(self):
        with mock.patch.object(self.fetcher, "fetch_eip", return_value=EIP_MARKDOWN):
            section = self.fetcher.get_eip_specification_section(1559)
        self.assertIn("The base fee is burned.", section)

    def test_specification_section_falls_back_to_the_head_of_the_document(self):
        with mock.patch.object(self.fetcher, "fetch_eip", return_value="no headings"):
            self.assertEqual(
                self.fetcher.get_eip_specification_section(1559), "no headings")

    def test_base_fee_extract_starts_at_the_first_mention(self):
        with mock.patch.object(self.fetcher, "fetch_eip", return_value=EIP_MARKDOWN):
            text = self.fetcher.get_eip1559_base_fee_spec()
        self.assertTrue(text.startswith("The base fee is burned."))
        self.assertIn("Line five.", text)
        self.assertNotIn("Trailing paragraph.", text)

    def test_base_fee_extract_falls_back_to_whole_section(self):
        markdown = "## Specification\n\nNothing relevant here.\n"
        with mock.patch.object(self.fetcher, "fetch_eip", return_value=markdown):
            self.assertIn("Nothing relevant here.",
                          self.fetcher.get_eip1559_base_fee_spec())


class TestCacheManagement(SpecFetcherTestCase):
    def test_clear_cache_empties_but_keeps_the_directory(self):
        Path(self.tmpdir, "eip-1559.md").write_text("x")
        self.fetcher.clear_cache()
        self.assertTrue(Path(self.tmpdir).is_dir())
        self.assertEqual(self.fetcher.list_cached_specs(), [])

    def test_clear_cache_when_directory_is_absent(self):
        shutil.rmtree(self.tmpdir)
        self.fetcher.clear_cache()
        self.assertEqual(self.fetcher.list_cached_specs(), [])

    def test_list_cached_specs_ignores_subdirectories(self):
        Path(self.tmpdir, "eip-1559.md").write_text("x")
        Path(self.tmpdir, "sub").mkdir()
        self.assertEqual(self.fetcher.list_cached_specs(), ["eip-1559.md"])


if __name__ == "__main__":
    unittest.main()
