"""
Tests for EIP-1559 Compliance Checking
Author: Safi El-Hassanine

Unit tests for PRSpec EIP-1559 analysis functionality.
"""

import unittest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Pre-import so that patch('google.generativeai') can resolve the namespace
import google.generativeai  # noqa: F401

from src.analyzer import GeminiAnalyzer, OpenAIAnalyzer, get_analyzer, AnalysisResult
from src.spec_fetcher import SpecFetcher
from src.code_fetcher import CodeFetcher
from src.parser import CodeParser, CodeBlock
from src.config import Config


class TestAnalyzer(unittest.TestCase):
    """Tests for the LLM analyzer"""
    
    def test_analysis_result_creation(self):
        """Test AnalysisResult dataclass"""
        result = AnalysisResult(
            status="FULL_MATCH",
            confidence=95,
            issues=[],
            summary="Code fully implements the specification"
        )
        
        self.assertEqual(result.status, "FULL_MATCH")
        self.assertEqual(result.confidence, 95)
        self.assertFalse(result.has_issues)
        self.assertEqual(len(result.high_severity_issues), 0)
    
    def test_analysis_result_with_issues(self):
        """Test AnalysisResult with issues"""
        issues = [
            {"type": "MISSING_CHECK", "severity": "HIGH", "description": "Test issue 1"},
            {"type": "EDGE_CASE", "severity": "LOW", "description": "Test issue 2"},
        ]
        
        result = AnalysisResult(
            status="PARTIAL_MATCH",
            confidence=70,
            issues=issues,
            summary="Some issues found"
        )
        
        self.assertTrue(result.has_issues)
        self.assertEqual(len(result.high_severity_issues), 1)
    
    def test_get_analyzer_gemini(self):
        """Test get_analyzer factory for Gemini"""
        with patch('google.generativeai') as mock_genai:
            analyzer = get_analyzer("gemini", api_key="test_key")
            self.assertIsInstance(analyzer, GeminiAnalyzer)
    
    def test_get_analyzer_invalid_provider(self):
        """Test get_analyzer with invalid provider"""
        with self.assertRaises(ValueError):
            get_analyzer("invalid_provider", api_key="test")
    
    @patch('google.generativeai')
    def test_gemini_analyzer_initialization(self, mock_genai):
        """Test GeminiAnalyzer initialization"""
        analyzer = GeminiAnalyzer(api_key="test_key", model="gemini-1.5-pro-latest")
        
        mock_genai.configure.assert_called_once_with(api_key="test_key")
        self.assertEqual(analyzer.model_name, "gemini-1.5-pro-latest")
    
    @patch('google.generativeai')
    def test_gemini_analyze_compliance(self, mock_genai):
        """Test GeminiAnalyzer.analyze_compliance"""
        # Mock the model response
        mock_response = Mock()
        mock_response.text = '{"status": "FULL_MATCH", "confidence": 90, "issues": [], "summary": "Test"}'
        
        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        analyzer = GeminiAnalyzer(api_key="test_key")
        result = analyzer.analyze_compliance(
            spec_text="Test spec",
            code_text="Test code",
            context={"file_name": "test.go"}
        )
        
        self.assertEqual(result.status, "FULL_MATCH")
        self.assertEqual(result.confidence, 90)


class TestSpecFetcher(unittest.TestCase):
    """Tests for the specification fetcher"""
    
    def setUp(self):
        self.fetcher = SpecFetcher(cache_dir="/tmp/prspec_test_cache")
    
    def tearDown(self):
        self.fetcher.clear_cache()
    
    @patch('requests.Session.get')
    def test_fetch_eip(self, mock_get):
        """Test fetching an EIP"""
        mock_response = Mock()
        mock_response.text = "# EIP-1559\n\nTest content"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        content = self.fetcher.fetch_eip(1559, use_cache=False)
        
        self.assertIn("EIP-1559", content)
        mock_get.assert_called()
    
    def test_extract_eip_sections(self):
        """Test extracting sections from EIP markdown"""
        eip_content = """# EIP-1559

## Abstract
This is the abstract.

## Specification
This is the specification.

## Rationale
This is the rationale.
"""
        sections = self.fetcher.extract_eip_sections(eip_content)
        
        self.assertIn("abstract", sections)
        self.assertIn("specification", sections)
        self.assertIn("rationale", sections)
    
    def test_list_cached_specs(self):
        """Test listing cached specs"""
        specs = self.fetcher.list_cached_specs()
        self.assertIsInstance(specs, list)


class TestCodeFetcher(unittest.TestCase):
    """Tests for the code fetcher"""
    
    def setUp(self):
        self.fetcher = CodeFetcher(cache_dir="/tmp/prspec_test_code_cache")
    
    def tearDown(self):
        self.fetcher.clear_cache()
    
    @patch('requests.Session.get')
    def test_fetch_file(self, mock_get):
        """Test fetching a file from GitHub"""
        mock_response = Mock()
        mock_response.text = "package main\n\nfunc main() {}"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response
        
        content = self.fetcher.fetch_file(
            "ethereum", "go-ethereum", "main.go", use_cache=False
        )
        
        self.assertIn("package main", content)
    
    def test_get_file_functions_go(self):
        """Test extracting Go functions"""
        go_code = """
package eip1559

func CalcBaseFee(parent *Header) *big.Int {
    return big.NewInt(0)
}

func (h *Header) BaseFee() *big.Int {
    return h.baseFee
}
"""
        functions = self.fetcher.get_file_functions(go_code, "go")
        
        self.assertEqual(len(functions), 2)
        self.assertEqual(functions[0]["name"], "CalcBaseFee")
    
    def test_client_info(self):
        """Test that client info is available"""
        self.assertIn("go-ethereum", self.fetcher.CLIENTS)
        self.assertIn("url", self.fetcher.CLIENTS["go-ethereum"])


class TestCodeParser(unittest.TestCase):
    """Tests for the code parser"""
    
    def setUp(self):
        self.parser = CodeParser(use_tree_sitter=False)
    
    def test_parse_go_function(self):
        """Test parsing Go functions"""
        go_code = """package eip1559

// CalcBaseFee calculates the base fee for a block
func CalcBaseFee(config *ChainConfig, parent *Header) *big.Int {
    if !config.IsLondon(parent.Number) {
        return nil
    }
    return calculateBaseFee(parent)
}
"""
        blocks = self.parser.parse_file(go_code, "go")
        
        self.assertGreater(len(blocks), 0)
        self.assertEqual(blocks[0].name, "CalcBaseFee")
        self.assertEqual(blocks[0].type, "function")
        self.assertEqual(blocks[0].language, "go")
    
    def test_parse_python_function(self):
        """Test parsing Python functions"""
        python_code = '''
def calculate_base_fee(parent_gas_used: int, parent_gas_limit: int) -> int:
    """Calculate the base fee for the next block."""
    if parent_gas_used == parent_gas_limit:
        return BASE_FEE_MAX_CHANGE
    return 0
'''
        blocks = self.parser.parse_file(python_code, "python")
        
        self.assertGreater(len(blocks), 0)
        self.assertEqual(blocks[0].name, "calculate_base_fee")
    
    def test_find_eip1559_functions(self):
        """Test finding EIP-1559 related functions"""
        code = """
func CalcBaseFee(parent *Header) *big.Int {
    return nil
}

func DoSomethingElse() {
    // Not related to EIP-1559
}

func ValidateGasLimit(header *Header) bool {
    return true
}
"""
        blocks = self.parser.find_eip1559_functions(code, "go")
        
        # Should find CalcBaseFee and ValidateGasLimit
        names = [b.name for b in blocks]
        self.assertIn("CalcBaseFee", names)
    
    def test_extract_go_comments(self):
        """Test extracting Go comments"""
        code = """
// This is a single line comment
func Test() {
    /* This is a
    multi-line comment */
}
"""
        comments = self.parser.extract_comments(code, "go")
        
        single_comments = [c for c in comments if c["type"] == "single"]
        self.assertGreater(len(single_comments), 0)


class TestCodeBlock(unittest.TestCase):
    """Tests for CodeBlock dataclass"""
    
    def test_code_block_creation(self):
        """Test creating a CodeBlock"""
        block = CodeBlock(
            name="TestFunc",
            type="function",
            content="func TestFunc() {}",
            start_line=1,
            end_line=1,
            language="go",
            signature="func TestFunc()"
        )
        
        self.assertEqual(block.name, "TestFunc")
        self.assertEqual(block.type, "function")
    
    def test_code_block_to_dict(self):
        """Test CodeBlock.to_dict()"""
        block = CodeBlock(
            name="Test",
            type="function",
            content="test",
            start_line=1,
            end_line=5,
            language="go"
        )
        
        d = block.to_dict()
        
        self.assertIn("name", d)
        self.assertIn("type", d)
        self.assertIn("start_line", d)


class TestIntegration(unittest.TestCase):
    """Integration tests"""
    
    @unittest.skipIf(not os.getenv("GEMINI_API_KEY"), "GEMINI_API_KEY not set")
    def test_full_analysis_flow(self):
        """Test full analysis flow with real API (skipped if no API key)"""
        from src.config import Config
        
        config = Config()
        
        # This test requires actual API key and network access
        analyzer = GeminiAnalyzer(api_key=config.gemini_api_key)
        
        spec = "The base fee must increase by 12.5% when blocks are full"
        code = """
func CalcBaseFee(parent *Header) *big.Int {
    baseFee := new(big.Int).Set(parent.BaseFee)
    gasUsed := parent.GasUsed
    gasTarget := parent.GasLimit / 2
    
    if gasUsed > gasTarget {
        // Increase base fee
        gasUsedDelta := gasUsed - gasTarget
        baseFee.Mul(baseFee, big.NewInt(int64(gasUsedDelta)))
        baseFee.Div(baseFee, big.NewInt(int64(gasTarget)))
        baseFee.Div(baseFee, big.NewInt(8))
    }
    return baseFee
}
"""
        
        result = analyzer.analyze_compliance(spec, code, {"file_name": "test.go"})
        
        self.assertIn(result.status, ["FULL_MATCH", "PARTIAL_MATCH", "MISSING", "UNCERTAIN"])
        self.assertIsInstance(result.confidence, int)


if __name__ == "__main__":
    unittest.main(verbosity=2)
