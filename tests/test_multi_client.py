"""Tests for multi-client support (Nethermind, Besu) — Phase 2."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.code_fetcher import CodeFetcher
from src.parser import CodeParser

# ---------------------------------------------------------------------------
# CodeFetcher registry tests
# ---------------------------------------------------------------------------

class TestNethermindRegistry(unittest.TestCase):
    """Ensure the Nethermind client registry has the expected EIP file lists."""

    def setUp(self):
        self.info = CodeFetcher.CLIENTS["nethermind"]

    def test_language_is_csharp(self):
        self.assertEqual(self.info["language"], "csharp")

    def test_eip1559_file_count(self):
        files = self.info["eip_files"].get(1559, [])
        self.assertGreaterEqual(len(files), 5)

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
        for name in ("go-ethereum", "nethermind", "besu", "reth"):
            self.assertIn(name, clients)

    def test_client_language_nethermind(self):
        self.assertEqual(CodeFetcher.client_language("nethermind"), "csharp")

    def test_client_language_besu(self):
        self.assertEqual(CodeFetcher.client_language("besu"), "java")

    def test_client_language_reth(self):
        self.assertEqual(CodeFetcher.client_language("reth"), "rust")

    def test_unknown_client_raises(self):
        with self.assertRaises(ValueError):
            CodeFetcher.client_language("nonexistent")


class TestRethRegistry(unittest.TestCase):
    """Ensure Reth (Rust) client registry is correctly configured."""

    def setUp(self):
        self.info = CodeFetcher.CLIENTS["reth"]

    def test_language_is_rust(self):
        self.assertEqual(self.info["language"], "rust")

    def test_branch_is_main(self):
        self.assertEqual(self.info.get("branch", "master"), "main")

    def test_eip1559_files_present(self):
        files = self.info["eip_files"].get(1559, [])
        self.assertGreater(len(files), 0)
        # Reth uses shared validation.rs and eth.rs; no dedicated eip1559.rs
        self.assertTrue(any("validation.rs" in f or "eth.rs" in f for f in files))

    def test_eip4844_files_present(self):
        files = self.info["eip_files"].get(4844, [])
        self.assertGreater(len(files), 0)
        # Reth uses shared validation.rs, blobstore, and eth.rs; no dedicated eip4844.rs
        self.assertTrue(any("validation.rs" in f or "blobstore" in f or "eth.rs" in f for f in files))

    def test_eip7702_files_present(self):
        files = self.info["eip_files"].get(7702, [])
        self.assertGreater(len(files), 0)
        # Reth 7702 pool/consensus validation lives in eth.rs and validation.rs
        self.assertTrue(any("validation.rs" in f or "eth.rs" in f for f in files))


class TestPectraEipMappings(unittest.TestCase):
    """Verify Pectra EIP file mappings exist for all execution clients."""

    PECTRA_EIPS = [7702, 2935]

    def test_geth_has_pectra_mappings(self):
        eip_files = CodeFetcher.CLIENTS["go-ethereum"]["eip_files"]
        for eip in self.PECTRA_EIPS:
            self.assertIn(eip, eip_files, f"go-ethereum missing EIP-{eip} mappings")
            self.assertGreater(len(eip_files[eip]), 0)

    def test_nethermind_has_pectra_mappings(self):
        eip_files = CodeFetcher.CLIENTS["nethermind"]["eip_files"]
        for eip in self.PECTRA_EIPS:
            self.assertIn(eip, eip_files, f"nethermind missing EIP-{eip} mappings")
            self.assertGreater(len(eip_files[eip]), 0)

    def test_besu_has_pectra_mappings(self):
        eip_files = CodeFetcher.CLIENTS["besu"]["eip_files"]
        for eip in self.PECTRA_EIPS:
            self.assertIn(eip, eip_files, f"besu missing EIP-{eip} mappings")
            self.assertGreater(len(eip_files[eip]), 0)

    def test_reth_has_7702_mapping(self):
        eip_files = CodeFetcher.CLIENTS["reth"]["eip_files"]
        self.assertIn(7702, eip_files)
        self.assertGreater(len(eip_files[7702]), 0)


class TestStakingRequestEipMappings(unittest.TestCase):
    """Verify EIP-7002 (withdrawals) and EIP-7251 (consolidation) mappings exist.

    These are the execution-layer "requests" EIPs that staking protocols
    (Lido, Ether.fi, EigenLayer) depend on for the validator exit/consolidation
    path, so every execution client must carry file mappings for them.
    """

    STAKING_EIPS = [7002, 7251]

    def test_all_clients_have_staking_request_mappings(self):
        for client in ("go-ethereum", "nethermind", "besu", "reth"):
            eip_files = CodeFetcher.CLIENTS[client]["eip_files"]
            for eip in self.STAKING_EIPS:
                self.assertIn(eip, eip_files, f"{client} missing EIP-{eip} mappings")
                self.assertGreater(
                    len(eip_files[eip]), 0, f"{client} EIP-{eip} mapping is empty"
                )

    def test_geth_7002_uses_state_processor(self):
        # geth processes the withdrawal queue system call in state_processor.go
        files = CodeFetcher.CLIENTS["go-ethereum"]["eip_files"][7002]
        self.assertTrue(any("state_processor.go" in f for f in files))

    def test_nethermind_7002_uses_execution_requests_processor(self):
        # Nethermind's EL-triggerable withdrawals live in ExecutionRequestsProcessor,
        # NOT the EIP-4895 WithdrawalProcessor — guard against the wrong file.
        files = CodeFetcher.CLIENTS["nethermind"]["eip_files"][7002]
        self.assertTrue(any("ExecutionRequestsProcessor.cs" in f for f in files))
        self.assertFalse(any("Withdrawals/WithdrawalProcessor.cs" in f for f in files))

    def test_besu_7251_uses_system_call_request_processor(self):
        files = CodeFetcher.CLIENTS["besu"]["eip_files"][7251]
        self.assertTrue(any("SystemCallRequestProcessor.java" in f for f in files))


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
        self.assertGreaterEqual(len(files), 5)
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

    @patch("requests.Session.get")
    def test_fetch_reth_uses_main_branch(self, mock_get):
        mock_resp = Mock()
        mock_resp.text = "pub fn validate_transaction() {}"
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp

        self.fetcher.fetch_eip_implementation("reth", 1559)
        # Verify all calls used the "main" branch in the raw URL
        for call in mock_get.call_args_list:
            url = call[0][0] if call[0] else call[1].get("url", "")
            self.assertIn("/main/", url, f"Expected main branch in URL: {url}")

    @patch("requests.Session.get")
    def test_fetch_reth_eip7702(self, mock_get):
        mock_resp = Mock()
        mock_resp.text = "pub struct Authorization { chain_id: u64 }"
        mock_resp.raise_for_status = Mock()
        mock_get.return_value = mock_resp

        files = self.fetcher.fetch_eip_implementation("reth", 7702)
        self.assertGreater(len(files), 0)


# ---------------------------------------------------------------------------
# Rust parser tests
# ---------------------------------------------------------------------------

class TestRustParser(unittest.TestCase):
    """Unit tests for the Rust regex parser."""

    def setUp(self):
        self.parser = CodeParser(use_tree_sitter=False)

    def test_parse_fn(self):
        code = """
pub fn validate_transaction(tx: &Transaction) -> Result<()> {
    Ok(())
}
"""
        blocks = self.parser.parse_file(code, "rust")
        names = [b.name for b in blocks]
        self.assertIn("validate_transaction", names)
        fn_block = next(b for b in blocks if b.name == "validate_transaction")
        self.assertEqual(fn_block.language, "rust")

    def test_parse_struct(self):
        code = """
pub struct Authorization {
    pub chain_id: u64,
    pub address: Address,
    pub nonce: u64,
}
"""
        blocks = self.parser.parse_file(code, "rust")
        names = [b.name for b in blocks]
        self.assertIn("Authorization", names)

    def test_parse_impl(self):
        code = """
impl Authorization {
    pub fn new(chain_id: u64, address: Address) -> Self {
        Self { chain_id, address, nonce: 0 }
    }
}
"""
        blocks = self.parser.parse_file(code, "rust")
        names = [b.name for b in blocks]
        self.assertTrue(any("Authorization" in n for n in names))

    def test_parse_trait(self):
        code = """
pub trait FeeMarket {
    fn base_fee_per_gas(&self) -> u128;
}
"""
        blocks = self.parser.parse_file(code, "rust")
        names = [b.name for b in blocks]
        self.assertIn("FeeMarket", names)

    def test_find_eip7702_functions_rust(self):
        code = """
pub fn validate_set_code_authorization(auth: &Authorization) -> bool {
    auth.chain_id != 0
}

pub fn unrelated_fn() -> u64 {
    42
}
"""
        blocks = self.parser.find_eip_functions(code, "rust", 7702)
        names = [b.name for b in blocks]
        self.assertIn("validate_set_code_authorization", names)
        self.assertNotIn("unrelated_fn", names)

    def test_find_eip1559_functions_rust(self):
        code = """
pub fn calculate_base_fee(parent: &Header) -> u128 {
    parent.base_fee_per_gas.unwrap_or(0)
}
"""
        blocks = self.parser.find_eip_functions(code, "rust", 1559)
        names = [b.name for b in blocks]
        self.assertIn("calculate_base_fee", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
