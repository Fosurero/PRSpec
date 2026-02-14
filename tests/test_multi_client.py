"""Tests for multi-client support (Nethermind, Besu) — Phase 2."""

import unittest
import sys
from pathlib import Path
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.code_fetcher import CodeFetcher
from src.parser import CodeParser, CodeBlock


# ---------------------------------------------------------------------------
# CodeFetcher registry tests
# ---------------------------------------------------------------------------

class TestNethermindRegistry(unittest.TestCase):
    """Ensure the Nethermind client registry has the expected EIP file lists."""

    def setUp(self):
        self.info = CodeFetcher.CLIENTS["nethermind"]

    def test_language_is_csharp(self):
        self.assertEqual(self.info["language"], "csharp")

    def test_eip1559_has_five_files(self):
        files = self.info["eip_files"].get(1559, [])
        self.assertEqual(len(files), 5)

    def test_eip4844_has_five_files(self):
        files = self.info["eip_files"].get(4844, [])
        self.assertEqual(len(files), 5)

    def test_eip1559_key_files_present(self):
        files = self.info["eip_files"][1559]
        names = [f.split("/")[-1] for f in files]
        self.assertIn("BaseFeeCalculator.cs", names)
        self.assertIn("Eip1559Constants.cs", names)

    def test_eip4844_key_files_present(self):
        files = self.info["eip_files"][4844]
        names = [f.split("/")[-1] for f in files]
        self.assertIn("BlobGasCalculator.cs", names)
        self.assertIn("KzgPolynomialCommitments.cs", names)


class TestBesuRegistry(unittest.TestCase):
    """Ensure the Besu client registry has the expected EIP file lists."""

    def setUp(self):
        self.info = CodeFetcher.CLIENTS["besu"]

    def test_language_is_java(self):
        self.assertEqual(self.info["language"], "java")

    def test_eip1559_has_five_files(self):
        files = self.info["eip_files"].get(1559, [])
        self.assertEqual(len(files), 5)

    def test_eip4844_has_five_files(self):
        files = self.info["eip_files"].get(4844, [])
        self.assertEqual(len(files), 5)

    def test_eip1559_key_files_present(self):
        files = self.info["eip_files"][1559]
        names = [f.split("/")[-1] for f in files]
        self.assertIn("LondonFeeMarket.java", names)
        self.assertIn("BaseFeeMarket.java", names)

    def test_eip4844_key_files_present(self):
        files = self.info["eip_files"][4844]
        names = [f.split("/")[-1] for f in files]
        self.assertIn("CancunGasCalculator.java", names)
        self.assertIn("BlobGas.java", names)


class TestSupportedClients(unittest.TestCase):
    """Cross-cutting client helper tests."""

    def test_supported_clients_includes_all(self):
        clients = CodeFetcher.supported_clients()
        for name in ("go-ethereum", "nethermind", "besu"):
            self.assertIn(name, clients)

    def test_client_language_nethermind(self):
        self.assertEqual(CodeFetcher.client_language("nethermind"), "csharp")

    def test_client_language_besu(self):
        self.assertEqual(CodeFetcher.client_language("besu"), "java")

    def test_unknown_client_raises(self):
        with self.assertRaises(ValueError):
            CodeFetcher.client_language("nonexistent")


# ---------------------------------------------------------------------------
# C# parser tests
# ---------------------------------------------------------------------------

class TestCSharpParser(unittest.TestCase):
    """Unit tests for the C# regex parser."""

    def setUp(self):
        self.parser = CodeParser(use_tree_sitter=False)

    def test_parse_class(self):
        code = """
namespace Nethermind.Core;

public class BaseFeeCalculator
{
    // implementation
}
"""
        blocks = self.parser.parse_file(code, "csharp")
        names = [b.name for b in blocks]
        self.assertIn("BaseFeeCalculator", names)
        cls = next(b for b in blocks if b.name == "BaseFeeCalculator")
        self.assertEqual(cls.type, "class")
        self.assertEqual(cls.language, "csharp")

    def test_parse_method(self):
        code = """
public class Foo
{
    public static UInt256 Calculate(BlockHeader parent)
    {
        return UInt256.Zero;
    }
}
"""
        blocks = self.parser.parse_file(code, "csharp")
        names = [b.name for b in blocks]
        self.assertIn("Calculate", names)
        m = next(b for b in blocks if b.name == "Calculate")
        self.assertEqual(m.type, "method")

    def test_parse_interface(self):
        code = """
public interface IEip1559Spec
{
    bool IsEip1559Enabled { get; }
}
"""
        blocks = self.parser.parse_file(code, "csharp")
        names = [b.name for b in blocks]
        self.assertIn("IEip1559Spec", names)

    def test_csharp_language_aliases(self):
        simple = "public class A { }"
        for alias in ("csharp", "c#", "cs"):
            blocks = self.parser.parse_file(simple, alias)
            self.assertTrue(any(b.name == "A" for b in blocks),
                            f"Alias '{alias}' did not route to C# parser")

    def test_find_eip1559_functions_csharp(self):
        code = """
public class BaseFeeCalculator
{
    public static UInt256 Calculate(BlockHeader parent)
    {
        var baseFee = parent.BaseFeePerGas;
        return baseFee;
    }
}

public class Unrelated
{
    public void DoStuff() { }
}
"""
        blocks = self.parser.find_eip_functions(code, "csharp", 1559)
        names = [b.name for b in blocks]
        self.assertIn("BaseFeeCalculator", names)
        self.assertIn("Calculate", names)
        self.assertNotIn("DoStuff", names)


# ---------------------------------------------------------------------------
# Java parser tests
# ---------------------------------------------------------------------------

class TestJavaParser(unittest.TestCase):
    """Unit tests for the Java regex parser."""

    def setUp(self):
        self.parser = CodeParser(use_tree_sitter=False)

    def test_parse_class(self):
        code = """
package org.hyperledger.besu.ethereum.mainnet.feemarket;

public class LondonFeeMarket implements BaseFeeMarket {
    // implementation
}
"""
        blocks = self.parser.parse_file(code, "java")
        names = [b.name for b in blocks]
        self.assertIn("LondonFeeMarket", names)
        cls = next(b for b in blocks if b.name == "LondonFeeMarket")
        self.assertEqual(cls.type, "class")
        self.assertEqual(cls.language, "java")

    def test_parse_method(self):
        code = """
public class FeeMarket {
    public long getBasefee(long parentBaseFee, long parentGasUsed, long parentGasTarget) {
        return 0L;
    }
}
"""
        blocks = self.parser.parse_file(code, "java")
        names = [b.name for b in blocks]
        self.assertIn("getBasefee", names)
        m = next(b for b in blocks if b.name == "getBasefee")
        self.assertEqual(m.type, "method")

    def test_parse_interface(self):
        code = """
public interface FeeMarket {
    long getBasefee();
}
"""
        blocks = self.parser.parse_file(code, "java")
        names = [b.name for b in blocks]
        self.assertIn("FeeMarket", names)

    def test_find_eip4844_functions_java(self):
        code = """
public class CancunGasCalculator extends ShanghaiGasCalculator {
    public long blobGasCost(int blobCount) {
        return blobCount * GAS_PER_BLOB;
    }
}

public class Util {
    public void helper() { }
}
"""
        blocks = self.parser.find_eip_functions(code, "java", 4844)
        names = [b.name for b in blocks]
        self.assertIn("blobGasCost", names)
        self.assertNotIn("helper", names)


# ---------------------------------------------------------------------------
# CodeFetcher fetch integration (mocked HTTP)
# ---------------------------------------------------------------------------

class TestCodeFetcherMultiClient(unittest.TestCase):
    """Verify CodeFetcher.fetch_eip_files works for new clients via mocked HTTP."""

    def setUp(self):
        self.fetcher = CodeFetcher(cache_dir="/tmp/prspec_test_mc")

    def tearDown(self):
        self.fetcher.clear_cache()

    @patch("requests.Session.get")
    def test_fetch_nethermind_eip1559(self, mock_get):
        mock_resp = Mock()
        mock_resp.text = "public class BaseFeeCalculator { }"
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp

        files = self.fetcher.fetch_eip_implementation("nethermind", 1559)
        self.assertEqual(len(files), 5)
        self.assertTrue(mock_get.called)

    @patch("requests.Session.get")
    def test_fetch_besu_eip4844(self, mock_get):
        mock_resp = Mock()
        mock_resp.text = "public class CancunGasCalculator { }"
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp

        files = self.fetcher.fetch_eip_implementation("besu", 4844)
        self.assertEqual(len(files), 5)
        self.assertTrue(mock_get.called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
