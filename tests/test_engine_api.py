"""Tests for the PRSpec Engine API."""

import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.engine import scan_path


class TestScanPathBasic(unittest.TestCase):
    """Basic contract tests for scan_path."""

    def setUp(self):
        """Create a temporary directory with small Go fixture files."""
        self.tmpdir = tempfile.mkdtemp(prefix="prspec_test_")

        # A Go file that references EIP-1559 keywords
        go_content = textwrap.dedent("""\
            package core

            import "math/big"

            // CalcBaseFee calculates the base fee for the next block per EIP-1559.
            func CalcBaseFee(parentBaseFee *big.Int, parentGasUsed uint64, parentGasLimit uint64) *big.Int {
                gasDelta := new(big.Int).SetUint64(parentGasUsed)
                feeDelta := new(big.Int).Mul(parentBaseFee, gasDelta)
                return feeDelta
            }

            // VerifyEip1559Header checks 1559-specific header constraints.
            func VerifyEip1559Header(header *Header) error {
                if header.BaseFee == nil {
                    return errMissingBaseFee
                }
                return nil
            }
        """)
        Path(self.tmpdir, "eip1559.go").write_text(go_content)

        # A Python file with NO EIP references
        py_content = textwrap.dedent("""\
            def hello():
                return "world"
        """)
        Path(self.tmpdir, "utils.py").write_text(py_content)

        # A file that should be ignored (no known extension)
        Path(self.tmpdir, "notes.txt").write_text("just some notes")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ---- Core contract checks ----

    def test_returns_dict(self):
        result = scan_path(self.tmpdir)
        self.assertIsInstance(result, dict)

    def test_required_top_level_keys(self):
        result = scan_path(self.tmpdir)
        for key in ("tool", "tool_version", "ruleset", "findings", "summary"):
            self.assertIn(key, result, f"Missing top-level key: {key}")

    def test_tool_name(self):
        result = scan_path(self.tmpdir)
        self.assertEqual(result["tool"], "PRSpec")

    def test_tool_version_present(self):
        result = scan_path(self.tmpdir)
        self.assertIsInstance(result["tool_version"], str)
        self.assertTrue(len(result["tool_version"]) > 0)

    def test_ruleset_default(self):
        result = scan_path(self.tmpdir)
        self.assertEqual(result["ruleset"], "ethereum")

    def test_summary_keys(self):
        result = scan_path(self.tmpdir)
        summary = result["summary"]
        for key in ("high", "med", "low", "files_scanned"):
            self.assertIn(key, summary, f"Missing summary key: {key}")

    def test_files_scanned_count(self):
        result = scan_path(self.tmpdir)
        # Should count the .go and .py files, not the .txt
        self.assertEqual(result["summary"]["files_scanned"], 2)

    def test_findings_are_list(self):
        result = scan_path(self.tmpdir)
        self.assertIsInstance(result["findings"], list)

    def test_finding_structure(self):
        result = scan_path(self.tmpdir)
        self.assertGreater(len(result["findings"]), 0,
                           "Expected at least one finding for EIP-1559 Go file")
        finding = result["findings"][0]
        for key in ("id", "severity", "title", "message", "file", "line", "hint"):
            self.assertIn(key, finding, f"Missing finding key: {key}")

    def test_eip1559_detected(self):
        result = scan_path(self.tmpdir)
        eip_ids = {f["title"] for f in result["findings"]}
        self.assertTrue(
            any("EIP-1559" in t for t in eip_ids),
            f"Expected EIP-1559 finding; got titles: {eip_ids}",
        )

    # ---- Edge cases ----

    def test_nonexistent_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            scan_path("/does/not/exist")

    def test_single_file_target(self):
        result = scan_path(os.path.join(self.tmpdir, "eip1559.go"))
        self.assertEqual(result["summary"]["files_scanned"], 1)
        self.assertGreater(len(result["findings"]), 0)

    def test_empty_dir(self):
        empty = tempfile.mkdtemp(prefix="prspec_empty_")
        try:
            result = scan_path(empty)
            self.assertEqual(result["summary"]["files_scanned"], 0)
            self.assertEqual(len(result["findings"]), 0)
        finally:
            os.rmdir(empty)

    def test_custom_ruleset_passthrough(self):
        result = scan_path(self.tmpdir, ruleset="custom")
        self.assertEqual(result["ruleset"], "custom")

    def test_json_pretty_output(self):
        result = scan_path(self.tmpdir, output="json-pretty")
        self.assertIn("_json", result)
        self.assertIsInstance(result["_json"], str)


class TestScanPathMultiEIP(unittest.TestCase):
    """Verify that multiple EIP keyword sets are checked."""

    def test_blob_keywords_detected(self):
        tmpdir = tempfile.mkdtemp(prefix="prspec_blob_")
        try:
            go_blob = textwrap.dedent("""\
                package core

                func CalcExcessBlobGas(parent uint64) uint64 {
                    return parent
                }
            """)
            Path(tmpdir, "blob.go").write_text(go_blob)

            result = scan_path(tmpdir)
            titles = [f["title"] for f in result["findings"]]
            self.assertTrue(
                any("EIP-4844" in t for t in titles),
                f"Expected EIP-4844 finding; got: {titles}",
            )
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
