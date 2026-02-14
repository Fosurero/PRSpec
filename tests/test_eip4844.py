"""Tests for EIP-4844 (blob transactions) support."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Pre-import so that patch('google.genai') resolves at mock-time
try:
    from google import genai  # noqa: F401
except ImportError:
    pass

from src.analyzer import BaseAnalyzer, GeminiAnalyzer
from src.code_fetcher import CodeFetcher
from src.config import Config
from src.parser import CodeParser
from src.spec_fetcher import SpecFetcher

SAMPLE_BLOB_TX_GO = """
package types

import (
    "math/big"
    "github.com/ethereum/go-ethereum/common"
    "github.com/ethereum/go-ethereum/crypto/kzg4844"
)

// BlobTx represents an EIP-4844 blob transaction.
type BlobTx struct {
    ChainID    *uint256.Int
    Nonce      uint64
    GasTipCap  *uint256.Int
    GasFeeCap  *uint256.Int
    Gas        uint64
    To         common.Address
    Value      *uint256.Int
    Data       []byte
    BlobFeeCap *uint256.Int
    BlobHashes []common.Hash
    Sidecar    *BlobTxSidecar
}

// BlobTxSidecar contains sidecar data for blob transactions.
type BlobTxSidecar struct {
    Blobs       []kzg4844.Blob
    Commitments []kzg4844.Commitment
    Proofs      []kzg4844.Proof
}

func CalcBlobFee(excessBlobGas uint64) *big.Int {
    return fakeExponential(minBlobGasPrice, excessBlobGas, blobGasPriceUpdateFraction)
}

func ValidateBlobSidecar(hashes []common.Hash, sidecar *BlobTxSidecar) error {
    if len(sidecar.Blobs) != len(hashes) {
        return errors.New("blob count mismatch")
    }
    for i := range sidecar.Blobs {
        if err := kzg4844.VerifyBlobProof(sidecar.Blobs[i], sidecar.Commitments[i], sidecar.Proofs[i]); err != nil {
            return err
        }
    }
    return nil
}

func CalcExcessBlobGas(parent *Header) uint64 {
    if parent.ExcessBlobGas+parent.BlobGasUsed < params.TargetBlobGasPerBlock {
        return 0
    }
    return parent.ExcessBlobGas + parent.BlobGasUsed - params.TargetBlobGasPerBlock
}
"""


class TestSpecFetcherEIP4844(unittest.TestCase):
    """Tests for SpecFetcher EIP-4844 support."""

    def test_eip4844_in_registry(self):
        """EIP-4844 must be present in supported_eips."""
        self.assertIn(4844, SpecFetcher.supported_eips())

    def test_eip4844_title(self):
        """EIP-4844 title must mention blobs or shard."""
        title = SpecFetcher.get_eip_title(4844)
        self.assertTrue(
            any(kw in title.lower() for kw in ["blob", "shard"]),
            f"Title does not mention blob/shard: {title}",
        )

    @patch("requests.Session.get")
    def test_fetch_eip4844_spec_returns_dict(self, mock_get):
        """fetch_eip_spec(4844) should return a dict with eip_markdown."""
        mock_resp = Mock()
        mock_resp.text = "# EIP-4844\n\n## Abstract\nBlob txs\n## Specification\nDetails"
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp

        fetcher = SpecFetcher(cache_dir="/tmp/prspec_test_4844_cache")
        try:
            result = fetcher.fetch_eip_spec(4844)
            self.assertIn("eip_markdown", result)
            self.assertIn("4844", result["eip_markdown"])
        finally:
            fetcher.clear_cache()

    @patch("requests.Session.get")
    def test_fetch_eip4844_convenience(self, mock_get):
        """fetch_eip4844_spec() should delegate to fetch_eip_spec."""
        mock_resp = Mock()
        mock_resp.text = "# EIP-4844\nblob stuff"
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp

        fetcher = SpecFetcher(cache_dir="/tmp/prspec_test_4844_cache2")
        try:
            result = fetcher.fetch_eip4844_spec()
            self.assertIsInstance(result, dict)
        finally:
            fetcher.clear_cache()

    def test_unregistered_eip_falls_back(self):
        """Requesting an unregistered EIP should still try to fetch the markdown."""
        fetcher = SpecFetcher()
        # It won't raise; it falls back to fetching the EIP markdown.
        # We just check it doesn't crash and returns a dict with eip_markdown key.
        with patch("requests.Session.get") as mock_get:
            mock_resp = Mock()
            mock_resp.text = "# EIP-99999 - Hypothetical"
            mock_resp.raise_for_status = Mock()
            mock_get.return_value = mock_resp
            result = fetcher.fetch_eip_spec(99999)
            self.assertIn("eip_markdown", result)


class TestCodeFetcherEIP4844(unittest.TestCase):
    """Tests for CodeFetcher EIP-4844 support."""

    def test_geth_supports_4844(self):
        """go-ethereum should list 4844 as a supported EIP."""
        self.assertIn(4844, CodeFetcher.supported_eips_for_client("go-ethereum"))

    def test_client_language_go(self):
        """go-ethereum language should be 'go'."""
        self.assertEqual(CodeFetcher.client_language("go-ethereum"), "go")

    def test_supported_clients_not_empty(self):
        """At least one client should be registered."""
        self.assertGreater(len(CodeFetcher.supported_clients()), 0)

    @patch("requests.Session.get")
    def test_fetch_eip4844_implementation(self, mock_get):
        """fetch_eip_implementation('go-ethereum', 4844) should return dict of file contents."""
        mock_resp = Mock()
        mock_resp.text = "package types\n\ntype BlobTx struct{}"
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp

        fetcher = CodeFetcher(cache_dir="/tmp/prspec_test_code_4844")
        try:
            files = fetcher.fetch_eip_implementation("go-ethereum", 4844)
            self.assertIsInstance(files, dict)
            self.assertGreater(len(files), 0)
        finally:
            fetcher.clear_cache()

    @patch("requests.Session.get")
    def test_fetch_eip4844_convenience(self, mock_get):
        """fetch_eip4844_implementation() delegates correctly."""
        mock_resp = Mock()
        mock_resp.text = "package types"
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp

        fetcher = CodeFetcher(cache_dir="/tmp/prspec_test_code_4844_b")
        try:
            files = fetcher.fetch_eip4844_implementation("go-ethereum")
            self.assertIsInstance(files, dict)
        finally:
            fetcher.clear_cache()

    def test_unsupported_client_raises(self):
        """Requesting files for a non-existent client should raise ValueError."""
        fetcher = CodeFetcher()
        with self.assertRaises(ValueError):
            fetcher.fetch_eip_implementation("nonexistent-client", 4844)


class TestParserEIP4844(unittest.TestCase):
    """Tests for CodeParser EIP-4844 keyword matching."""

    def setUp(self):
        self.parser = CodeParser(use_tree_sitter=False)

    def test_find_eip4844_functions(self):
        """find_eip_functions with eip=4844 should detect blob-related functions."""
        blocks = self.parser.find_eip_functions(SAMPLE_BLOB_TX_GO, "go", 4844)
        names = [b.name for b in blocks]
        self.assertIn("CalcBlobFee", names)
        self.assertIn("ValidateBlobSidecar", names)
        self.assertIn("CalcExcessBlobGas", names)

    def test_find_eip4844_convenience(self):
        """find_eip4844_functions() convenience wrapper should work."""
        blocks = self.parser.find_eip4844_functions(SAMPLE_BLOB_TX_GO, "go")
        names = [b.name for b in blocks]
        self.assertIn("CalcBlobFee", names)

    def test_eip4844_does_not_match_unrelated(self):
        """Functions without blob/kzg keywords should not match EIP-4844."""
        code = """
func DoNothing() {}
func HandleTransaction(tx *Transaction) error { return nil }
"""
        blocks = self.parser.find_eip_functions(code, "go", 4844)
        self.assertEqual(len(blocks), 0)

    def test_eip1559_keywords_still_work(self):
        """EIP-1559 matching should remain unaffected by 4844 additions."""
        code = """
func CalcBaseFee(parent *Header) *big.Int {
    return nil
}
"""
        blocks = self.parser.find_eip_functions(code, "go", 1559)
        names = [b.name for b in blocks]
        self.assertIn("CalcBaseFee", names)


class _ConcreteAnalyzer(BaseAnalyzer):
    """Minimal concrete subclass so we can test _build_analysis_prompt
    without needing a real Gemini/OpenAI connection."""

    def analyze_compliance(self, spec_text, code_text, context):
        raise NotImplementedError


class TestAnalyzerEIP4844Context(unittest.TestCase):
    """Tests that the analyzer prompt correctly incorporates EIP-4844 context."""

    def test_prompt_mentions_eip4844(self):
        """_build_analysis_prompt should include EIP-4844 in the prompt."""
        analyzer = _ConcreteAnalyzer()
        prompt = analyzer._build_analysis_prompt(
            spec_text="blob gas pricing spec",
            code_text="func CalcBlobFee() {}",
            context={
                "file_name": "tx_blob.go",
                "language": "go",
                "eip_number": 4844,
                "eip_title": "Shard Blob Transactions",
            },
        )
        self.assertIn("4844", prompt)
        self.assertIn("Shard Blob Transactions", prompt)

    def test_prompt_defaults_without_eip_number(self):
        """When eip_number is absent, prompt should still work."""
        analyzer = _ConcreteAnalyzer()
        prompt = analyzer._build_analysis_prompt(
            spec_text="some spec",
            code_text="some code",
            context={"file_name": "test.go", "language": "go"},
        )
        # Should not crash; should contain default label
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)


class TestConfigEIP4844(unittest.TestCase):
    """Tests for per-EIP focus areas in Config."""

    def test_eip4844_focus_areas(self):
        """get_eip_focus_areas(4844) should return 4844-specific areas if configured."""
        config = Config()
        areas = config.get_eip_focus_areas(4844)
        self.assertIsInstance(areas, list)
        # Should return *something* (either 4844-specific or the default fallback)
        self.assertGreater(len(areas), 0)

    def test_fallback_focus_areas(self):
        """get_eip_focus_areas for an unconfigured EIP should return default areas."""
        config = Config()
        areas = config.get_eip_focus_areas(99999)
        self.assertIsInstance(areas, list)


class TestEIP4844Integration(unittest.TestCase):
    """Integration test for the full EIP-4844 pipeline (requires API key)."""

    @unittest.skipIf(not os.getenv("GEMINI_API_KEY"), "GEMINI_API_KEY not set")
    def test_full_4844_analysis(self):
        """End-to-end analysis of sample EIP-4844 code."""
        config = Config()
        analyzer = GeminiAnalyzer(api_key=config.gemini_api_key)

        spec = (
            "Blob transactions carry KZG commitments and proofs. "
            "The blob gas price is calculated from excess blob gas using "
            "a fake exponential function."
        )

        result = analyzer.analyze_compliance(
            spec, SAMPLE_BLOB_TX_GO,
            {
                "file_name": "tx_blob.go",
                "language": "go",
                "eip_number": 4844,
                "eip_title": "Shard Blob Transactions",
            },
        )

        self.assertIn(
            result.status,
            ["FULL_MATCH", "PARTIAL_MATCH", "MISSING", "UNCERTAIN"],
        )
        self.assertIsInstance(result.confidence, int)


if __name__ == "__main__":
    unittest.main(verbosity=2)
