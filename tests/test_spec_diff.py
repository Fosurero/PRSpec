"""Tests for fork-to-fork execution-spec diff extraction."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.spec_fetcher import SpecFetcher


class TestForkDiff(unittest.TestCase):
    def _fetcher(self):
        return SpecFetcher(cache_dir=tempfile.mkdtemp(prefix="prspec_diff_"))

    def test_diff_isolates_the_delta(self):
        f = self._fetcher()

        def fake_exec(path, branch="master", use_cache=True):
            if "london" in path:
                return "line a\nline b\nintroduced by 1559\nline c\n"
            if "berlin" in path:
                return "line a\nline b\nline c\n"
            raise requests.HTTPError("404")

        with patch.object(f, "fetch_execution_spec", side_effect=fake_exec):
            diff = f.fetch_execution_spec_diff(1559)

        self.assertIsNotNone(diff)
        self.assertIn("introduced by 1559", diff)
        self.assertIn("london", diff)   # tofile header
        self.assertIn("berlin", diff)   # fromfile header

    def test_mode_diff_populates_spec_and_marks_it(self):
        f = self._fetcher()

        def fake_exec(path, branch="master", use_cache=True):
            return "AFTER\n" if "london" in path else "BEFORE\n"

        with patch.object(f, "fetch_eip", return_value="# EIP-1559"), \
             patch.object(f, "fetch_execution_spec", side_effect=fake_exec):
            res = f.fetch_eip_spec(1559, mode="diff")

        self.assertEqual(res["execution_spec_mode"], "diff")
        self.assertIn("AFTER", res["execution_spec"])

    def test_mode_full_keeps_whole_file(self):
        f = self._fetcher()
        with patch.object(f, "fetch_eip", return_value="# EIP-1559"), \
             patch.object(f, "fetch_execution_spec", return_value="WHOLE FORK FILE\n"):
            res = f.fetch_eip_spec(1559)  # default mode="full"

        self.assertEqual(res["execution_spec_mode"], "full")
        self.assertIn("WHOLE FORK FILE", res["execution_spec"])

    def test_diff_falls_back_to_full_when_predecessor_missing(self):
        f = self._fetcher()

        def fake_exec(path, branch="master", use_cache=True):
            if "berlin" in path:
                raise requests.HTTPError("404 predecessor missing")
            return "LONDON FULL SPEC\n"

        with patch.object(f, "fetch_eip", return_value="# EIP-1559"), \
             patch.object(f, "fetch_execution_spec", side_effect=fake_exec):
            res = f.fetch_eip_spec(1559, mode="diff")

        self.assertEqual(res["execution_spec_mode"], "full")
        self.assertIn("LONDON FULL SPEC", res["execution_spec"])

    def test_no_predecessor_returns_none(self):
        f = self._fetcher()
        # EIP-7251 is consensus-only with no predecessor fork registered.
        self.assertIsNone(f.fetch_execution_spec_diff(7251))

    def test_identical_forks_produce_no_diff(self):
        f = self._fetcher()
        with patch.object(f, "fetch_execution_spec", return_value="same\ncontent\n"):
            self.assertIsNone(f.fetch_execution_spec_diff(1559))

    def test_registry_predecessors_are_registered(self):
        # Every EIP that ships an execution spec should know its predecessor
        # fork so the diff path is available.
        for eip, info in SpecFetcher.EIP_REGISTRY.items():
            if info.get("execution_spec_paths"):
                self.assertIn(
                    "predecessor_fork", info,
                    f"EIP-{eip} has execution specs but no predecessor_fork",
                )


if __name__ == "__main__":
    unittest.main()
